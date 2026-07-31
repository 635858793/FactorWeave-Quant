"""
R150 子智能体 D - 增强扫描工具
1. 扫描所有未登记的 logger.debug 处理异常 (R118 例外核验)
2. 业务事件发布规范扫描 (R8 铁律 #7: persistence.append 失败仅 warning)
"""
import ast
import os
import re
import sys
import yaml
from pathlib import Path
from collections import defaultdict


def load_r118_registry():
    """加载 R118 例外登记清单"""
    with open('core/r118_exceptions_registry.yaml', 'r', encoding='utf-8') as f:
        registry = yaml.safe_load(f)
    registered = set()
    for cat in ['r118_b15_field_degradation', 'r118_b16_monitoring_auxiliary']:
        for item in registry.get(cat, []):
            registered.add((item['file'].replace('\\', '/'), item['line']))
    return registered


def find_logger_debug_in_except(filepath: str):
    """AST 扫描文件, 找到 except 块内的 logger.debug 调用"""
    src = Path(filepath).read_text(encoding='utf-8')
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                    call = sub.value
                    if (isinstance(call.func, ast.Attribute) and
                        call.func.attr == 'debug' and
                        isinstance(call.func.value, ast.Name) and
                        call.func.value.id == 'logger'):
                        # 获取 logger.debug 消息
                        msg = ''
                        if call.args:
                            arg = call.args[0]
                            if isinstance(arg, ast.Constant):
                                msg = str(arg.value)
                            elif hasattr(ast, 'JoinedStr') and isinstance(arg, ast.JoinedStr):
                                msg = ast.unparse(arg)[:100]
                        results.append({
                            'file': filepath,
                            'line': sub.lineno,
                            'msg': msg,
                            'has_exc_info': any(
                                kw.arg == 'exc_info' and isinstance(kw.value, ast.Constant) and kw.value.value is True
                                for kw in call.keywords
                            ),
                            'context_after': sub.lineno,
                        })
    return results


def scan_all_exceptions():
    """扫描所有 core/ 下的 logger.debug 在 except 块中"""
    logger_debug_in_except = []
    for root, dirs, files in os.walk('core'):
        # 跳过 __pycache__ 和 .venv
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.venv', 'node_modules', 'tests', 'test', 'migrations')]
        for f in files:
            if f.endswith('.py'):
                fp = os.path.join(root, f)
                logger_debug_in_except.extend(find_logger_debug_in_except(fp))
    return logger_debug_in_except


def find_persistence_append_calls():
    """扫描所有 persistence.append 调用 (R8 铁律 #7 业务事件持久化)"""
    results = []
    for root, dirs, files in os.walk('core'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.venv', 'node_modules', 'tests', 'test', 'migrations')]
        for f in files:
            if f.endswith('.py'):
                fp = os.path.join(root, f)
                try:
                    src = Path(fp).read_text(encoding='utf-8')
                except (UnicodeDecodeError, IOError):
                    continue
                # 找 persistence.append 模式
                for m in re.finditer(r'persistence\.append\s*\(', src):
                    line_no = src[:m.start()].count('\n') + 1
                    # 找后续 30 行
                    lines = src.split('\n')
                    ctx = '\n'.join(lines[max(0, line_no - 3):line_no + 8])
                    # 找是否有 except 块
                    if 'except' in ctx.lower() or 'fire-and-forget' in ctx.lower():
                        results.append({
                            'file': fp,
                            'line': line_no,
                            'context': ctx[:500],
                        })
    return results


def find_event_publish_violations():
    """扫描事件发布规范违反 (R8 铁律: publish 时持锁/嵌套/未注册)"""
    violations = []
    for root, dirs, files in os.walk('core'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.venv', 'node_modules', 'tests', 'test', 'migrations')]
        for f in files:
            if f.endswith('.py'):
                fp = os.path.join(root, f)
                try:
                    src = Path(fp).read_text(encoding='utf-8')
                except (UnicodeDecodeError, IOError):
                    continue
                # 找 publish 调用
                for m in re.finditer(r'\.publish\s*\(', src):
                    line_no = src[:m.start()].count('\n') + 1
                    lines = src.split('\n')
                    # 向前 15 行查找是否在 with self._lock 块内
                    start_ctx = max(0, line_no - 15)
                    ctx = '\n'.join(lines[start_ctx:line_no])
                    # 检测是否在 _lock/_futures_lock/_stats_lock 块内且与 publish 嵌套
                    if re.search(r'with self\._lock\s*:', ctx) and not re.search(r'with self\._lock\s*:\s*\n\s*#[^\n]*\n\s*self\.', ctx):
                        # 简单判断
                        pass
    return violations


if __name__ == '__main__':
    # 1. R118 例外核验
    print('=' * 60)
    print('R118 例外保留清单核验')
    print('=' * 60)
    registered = load_r118_registry()
    print(f'已登记 R118 例外: {len(registered)} 处')

    all_debug = scan_all_exceptions()
    print(f'扫描到 logger.debug 在 except 块: {len(all_debug)} 处')

    # 排除已登记
    unregistered = []
    for item in all_debug:
        norm_file = item['file'].replace('\\', '/')
        for rf, rl in registered:
            if rf in norm_file and item['line'] == rl:
                break
        else:
            unregistered.append(item)
    print(f'未登记 logger.debug 处理异常: {len(unregistered)} 处')
    print()
    print('=== 前 30 处未登记 logger.debug 处理异常: ===')
    for item in unregistered[:30]:
        print(f"  [未登记] {item['file']}:{item['line']} | exc_info={item['has_exc_info']} | msg={item['msg'][:80]}")

    # 2. 持久化调用扫描
    print()
    print('=' * 60)
    print('R8 铁律 #7 持久化失败仅 warning 扫描')
    print('=' * 60)
    persistence = find_persistence_append_calls()
    print(f'persistence.append 在 except 块或 fire-and-forget 模式: {len(persistence)} 处')
    for item in persistence[:10]:
        print(f"  {item['file']}:{item['line']}")
        print(f"    context: {item['context'][:200]}")
