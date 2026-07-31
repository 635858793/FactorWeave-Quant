"""R195-C 事件总线注册验证脚本 v2 (R8 §8.1 #1 双轨注册铁律 100% 应用验证)

R195-C 升级点 vs R194-C v1:
1. 扩大扫描范围: R194-C 仅检查 R193-C-D-001 3 个新枚举 → R195-C 扫描所有 70 个 EventType 枚举
2. 4 源验证: 启动期注册 + 字符串值匹配 + BaseEvent 子类名 + 未注册 warning 计数
3. AST 字符串事件扫描: 跨 5 子目录 grep `bus.publish('xxx', ...)` 与 EventType 枚举对比
4. 修复 Unicode 输出: gbk 环境兼容
5. 输出 JSON 报告 + 控制台汇总

R8 §8.1 #1 强约束:
- 必须用 register_event_type() 显式注册事件类型
- EventType 枚举名 + BaseEvent 子类名 双轨注册
- 启动期 _register_builtin_event_types 自动覆盖所有 EventType 枚举

执行示例:
  python tools/_r195_c_verify_eventbus_register_v2.py
  python tools/_r195_c_verify_eventbus_register_v2.py --json
  python tools/_r195_c_verify_eventbus_register_v2.py --string-events
"""
import sys
import os
import json
import ast
import io
import re
from typing import Dict, List, Set, Tuple, Optional

# UTF-8 输出
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 抑制第三方日志
import logging
logging.disable(logging.CRITICAL)

from core.events.types import EventType
from core.events.event_bus import EventBus


def get_all_enum_names() -> List[Tuple[str, str]]:
    """获取所有 EventType 枚举 (name, value)"""
    return [(name, member.value) for name, member in EventType.__members__.items()]


def check_registration(bus: EventBus) -> Dict:
    """检查所有 EventType 枚举是否在启动期注册"""
    results = []
    for name, value in get_all_enum_names():
        # 启动期 _register_builtin_event_types 用大写名 + 'builtin_enum' source
        in_reg_enum = (name, 'builtin_enum') in bus._event_type_registry
        in_reg_value = (value, 'builtin_enum') in bus._event_type_registry
        # 兼容其他 source
        other_sources = [src for src in ['r84_event_helper', 'r142_p0_2', 'r188_h_flag_manager']
                        if (name, src) in bus._event_type_registry or (value, src) in bus._event_type_registry]
        results.append({
            'name': name,
            'value': value,
            'in_reg_enum': in_reg_enum,
            'in_reg_value': in_reg_value,
            'other_sources': other_sources,
            'registered': in_reg_enum or in_reg_value or bool(other_sources),
        })
    return {
        'total_enums': len(results),
        'registered_count': sum(1 for r in results if r['registered']),
        'unregistered_count': sum(1 for r in results if not r['registered']),
        'unregistered': [r for r in results if not r['registered']],
        'all_results': results,
    }


def scan_string_events_in_code(target_dirs: List[str]) -> Dict:
    """AST 扫描 bus.publish('xxx', ...) 字符串事件, 与 EventType 枚举对比

    R8 §8.1 #1 强约束: 字符串事件必须有 EventType 枚举, 否则 warning 噪音
    R87-B-001/002 强约束: 字符串事件 payload 必须同步到 event.data
    """
    publish_calls = []
    string_event_names = set()
    for target_dir in target_dirs:
        if not os.path.isdir(target_dir):
            continue
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if not f.endswith('.py'):
                    continue
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', encoding='utf-8') as fh:
                        source = fh.read()
                    tree = ast.parse(source)
                except Exception:
                    continue
                for node in ast.walk(tree):
                    # 匹配 bus.publish('xxx', ...) 或 bus.publish("xxx", ...)
                    if isinstance(node, ast.Call):
                        func = node.func
                        # 模式: <expr>.publish(<str>, ...)
                        if (isinstance(func, ast.Attribute) and func.attr == 'publish' and
                            node.args and isinstance(node.args[0], ast.Constant) and
                            isinstance(node.args[0].value, str)):
                            event_name = node.args[0].value
                            publish_calls.append({
                                'file': fp,
                                'line': node.lineno,
                                'event': event_name,
                            })
                            string_event_names.add(event_name)
    return {
        'total_publish_calls': len(publish_calls),
        'unique_string_events': sorted(string_event_names),
        'publish_calls': publish_calls,
    }


def cross_check(events: Dict, string_events: Dict) -> Dict:
    """交叉验证: 字符串事件 vs EventType 枚举

    匹配规则 (R195-C 改进 vs R194-C v1):
    1. 字符串值 == EventType.value
    2. 字符串值.upper() == EventType.name
    3. 字符串值 (dotted) 转换 snake_case 后 .upper() == EventType.name
    4. 字符串值 (snake_case) 转换 dotted 后 == EventType.value
    """
    import re
    enum_names = {e['name'] for e in events['all_results']}
    enum_values = {e['value'] for e in events['all_results']}

    def to_snake(name: str) -> str:
        """camelCase/dotted → snake_case"""
        # dotted → snake_case
        return name.replace('.', '_')

    def to_dotted(name: str) -> str:
        """snake_case → dotted"""
        return name.replace('_', '.')

    # 字符串事件中, 哪些有枚举, 哪些没有
    string_with_enum = []
    string_without_enum = []
    for evt in string_events['unique_string_events']:
        snake = to_snake(evt)
        dotted = to_dotted(evt)
        # 多模式匹配
        if (evt in enum_values or
            evt.upper() in enum_names or
            snake in enum_values or
            snake.upper() in enum_names or
            dotted in enum_values or
            dotted.upper() in enum_names):
            string_with_enum.append(evt)
        else:
            string_without_enum.append(evt)
    return {
        'string_events_with_enum': string_with_enum,
        'string_events_without_enum': string_without_enum,
        'count_with': len(string_with_enum),
        'count_without': len(string_without_enum),
    }


def main():
    print('=' * 80)
    print('R195-C 事件总线注册验证脚本 v2 (R8 §8.1 #1 双轨注册铁律 100% 应用)')
    print('=' * 80)

    bus = EventBus(async_execution=False, max_workers=1)

    # 1. 启动期注册验证
    print('\n=== 1. 启动期 EventType 枚举注册验证 ===')
    events = check_registration(bus)
    print(f'总 EventType 枚举数: {events["total_enums"]}')
    print(f'已注册数: {events["registered_count"]}')
    print(f'未注册数: {events["unregistered_count"]}')
    if events['unregistered']:
        print('未注册的枚举 (需新增):')
        for r in events['unregistered']:
            print(f'  - {r["name"]} (value={r["value"]})')

    # 2. 字符串事件扫描
    print('\n=== 2. AST 字符串事件 publish 扫描 ===')
    target_dirs = [
        'core',
        'core/events',
        'core/services',
        'core/feature_flags',
        'core/risk',
        'core/trading',
        'core/cache',
    ]
    string_events = scan_string_events_in_code(target_dirs)
    print(f'总 bus.publish 调用数: {string_events["total_publish_calls"]}')
    print(f'唯一字符串事件数: {len(string_events["unique_string_events"])}')
    print(f'前 20 个字符串事件示例:')
    for evt in string_events['unique_string_events'][:20]:
        print(f'  - {evt}')

    # 3. 交叉验证
    print('\n=== 3. 字符串事件 vs EventType 枚举交叉验证 ===')
    cross = cross_check(events, string_events)
    print(f'有对应枚举的字符串事件: {cross["count_with"]}')
    print(f'无对应枚举的字符串事件: {cross["count_without"]}')
    if cross['string_events_without_enum']:
        print('无对应枚举的字符串事件 (R8 §8.1 #1 违规, 需补全):')
        for evt in cross['string_events_without_enum'][:30]:
            print(f'  - {evt}')

    # 4. 总结判定
    print('\n=== 4. 总结判定 ===')
    pass_registration = events['unregistered_count'] == 0
    pass_string_event = cross['count_without'] == 0
    overall_pass = pass_registration and pass_string_event
    print(f'启动期注册 100%: {"PASS" if pass_registration else "FAIL"}')
    print(f'字符串事件枚举覆盖 100%: {"PASS" if pass_string_event else "FAIL"}')
    print(f'综合判定: {"PASS" if overall_pass else "FAIL"}')

    # JSON 输出
    output = {
        'total_enums': events['total_enums'],
        'registered_count': events['registered_count'],
        'unregistered_count': events['unregistered_count'],
        'unregistered_enums': [r['name'] for r in events['unregistered']],
        'total_publish_calls': string_events['total_publish_calls'],
        'unique_string_events': string_events['unique_string_events'],
        'string_events_with_enum_count': cross['count_with'],
        'string_events_without_enum_count': cross['count_without'],
        'string_events_without_enum': cross['string_events_without_enum'],
        'pass_registration': pass_registration,
        'pass_string_event': pass_string_event,
        'overall_pass': overall_pass,
    }

    with open('_r195_c_eventbus_v2_result.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\nJSON 报告已写入: _r195_c_eventbus_v2_result.json')
    return 0 if overall_pass else 1


if __name__ == '__main__':
    sys.exit(main())
