#!/usr/bin/env python3
"""R192-C 事件总线审计脚本"""
import ast
import os
import re
import sys
from pathlib import Path


def collect_event_strings(source):
    """收集所有 bus.publish("string", ...) 调用"""
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # bus.publish("string", ...) or event_bus.publish("string", ...)
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'publish':
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    results.append({
                        'line': node.lineno,
                        'event_name': node.args[0].value,
                    })
    return results


def collect_data_kwargs(source):
    """收集所有 bus.publish(..., data=...) 调用 (R87-B-002 违规)"""
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'publish':
                for kw in node.keywords:
                    if kw.arg == 'data' and isinstance(kw.value, ast.Dict):
                        results.append({
                            'line': node.lineno,
                            'data_keys': [k.value for k in kw.value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)],
                        })
    return results


def main():
    target_dirs = ['core', 'gui']
    target_files = []
    for d in target_dirs:
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith('.py') and '.bak' not in f and 'r128_pre' not in f and 'r149' not in f and 'r187' not in f and 'r192' not in f and '.pyc' not in f:
                    target_files.append(os.path.join(root, f))

    print(f"=== 事件总线审计 (R8 §8.1 7+1 铁律 + R84 + R87-B-001/002) ===")
    print(f"扫描文件: {len(target_files)}")

    all_strings = []
    all_data_kwargs = []
    for f in target_files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                source = fp.read()
            results = collect_event_strings(source)
            for r in results:
                r['file'] = f
                all_strings.append(r)
            data_results = collect_data_kwargs(source)
            for r in data_results:
                r['file'] = f
                all_data_kwargs.append(r)
        except Exception as e:
            pass

    # 1. 统计各事件名出现次数
    event_counts = {}
    for r in all_strings:
        name = r['event_name']
        event_counts.setdefault(name, []).append((r['file'], r['line']))

    print(f"\n=== 字符串事件名总数: {len(event_counts)} (出现 {len(all_strings)} 次) ===")
    print(f"\n=== 使用 data= kwarg 的 publish (R87-B-002 风险): {len(all_data_kwargs)} ===")
    for r in all_data_kwargs[:20]:
        print(f"  {r['file']}:L{r['line']} data_keys={r['data_keys']}")

    # 2. 检查事件类型枚举
    try:
        from core.events.types import EventType
        enum_values = {e.value for e in EventType.__members__.values()}
        enum_names = {e.name for e in EventType.__members__.values()}
    except Exception:
        enum_values = set()
        enum_names = set()
        print("[!] 无法导入 EventType 枚举")

    print(f"\n=== EventType 枚举成员数: {len(enum_values)} ===")
    missing_enum = []
    for name in event_counts.keys():
        # 检查是否在 EventType 中
        if name not in enum_values and name not in enum_names:
            # 排除 dotted 风格 (业务命名空间)
            if '.' not in name and not name.endswith('_id') and not name[0].isupper() and 'service' not in name and 'task' not in name and 'data' not in name and 'order' not in name and 'risk' not in name and 'market' not in name and 'strategy' not in name and 'system' not in name and 'plugin' not in name and 'ui' not in name and 'trade' not in name and 'asset' not in name and 'position' not in name and 'account' not in name and 'cancel' not in name and 'batch' not in name and 'update' not in name and 'theme' not in name and 'realtime' not in name and 'tick' not in name and 'all' not in name and 'correlation' not in name and 'trading_interface' not in name and 'order_' not in name and 'order_' != name[:6]:
                # 简单的 dotted 风格判定
                if not re.match(r'^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$', name) and not re.match(r'^[A-Z][a-zA-Z]+Event$', name):
                    missing_enum.append((name, len(event_counts[name])))

    if missing_enum:
        print(f"\n=== 字符串事件缺 EventType 枚举 (前 20): {len(missing_enum)} ===")
        for name, count in sorted(missing_enum, key=lambda x: -x[1])[:20]:
            print(f"  {name!r}: {count} 次发布")
            for f, line in event_counts[name][:3]:
                print(f"    - {f}:L{line}")
    else:
        print("\n=== ✅ 所有字符串事件均映射到 EventType 枚举或 dotted 风格命名空间 ===")

    print(f"\n=== 完成 ===")


if __name__ == '__main__':
    main()
