"""R235-A: 提取所有 production 文件的 bus.publish 事件名"""
import re
import os
import sys
from pathlib import Path

PROD_DIRS = ['core', 'gui', 'web', 'backtest', 'plugins', 'distributed_node', 'utils', 'data']
TEST_DIR = 'tests'

EXCLUDE_PATTERNS = [
    r'\.bak\.', r'\.r\d+', r'__pycache__', r'\\tools\\',
    r'_archive', r'_r\d+_', r'_audit', r'_debug', r'_probe',
    r'_tmp', r'_verify', r'logs\\',
]

def is_production(path):
    return not any(re.search(p, path) for p in EXCLUDE_PATTERNS)

def is_test(path):
    return TEST_DIR in path

def extract_events_from_file(filepath):
    """提取 .py 文件中所有 bus.publish 事件"""
    events = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception:
        return events

    for i, line in enumerate(lines, 1):
        # 跳过注释行 (整行注释)
        stripped = line.strip()
        if stripped.startswith('#') and '.publish(' not in stripped:
            continue

        # 模式 1: bus.publish('event_name', ...) 或 bus.publish("event_name", ...)
        patterns = [
            r'\.bus\.publish\s*\(\s*["\']([^"\']+)["\']',
            r'\.event_bus\.publish\s*\(\s*["\']([^"\']+)["\']',
            r'\._event_bus\.publish\s*\(\s*["\']([^"\']+)["\']',
            r'bus\.publish\s*\(\s*["\']([^"\']+)["\']',
            r'Bus\.publish\s*\(\s*["\']([^"\']+)["\']',
        ]
        matched = False
        for pat in patterns:
            m = re.search(pat, line)
            if m:
                event_name = m.group(1)
                events.append((event_name, i, 'string_event'))
                matched = True
                break
        if matched:
            continue

        # 模式 2: .publish(EventClass(...)) 或 .publish(EventClass)
        m = re.search(r'\.publish\s*\(\s*([A-Z][A-Za-z0-9_]+)\s*[\(\,]', line)
        if m:
            event_class = m.group(1)
            # 过滤非事件类
            if event_class not in ('MagicMock', 'BaseException', 'Test', 'Dict', 'List', 'Optional', 'Any'):
                # 排除 helper 函数 (publish_xxx)
                if not event_class.startswith('publish_'):
                    events.append((event_class, i, 'dataclass_event'))

    return events


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui'

    # 1) 收集 production publish
    prod_results = {}
    for prod_dir in PROD_DIRS:
        full_dir = os.path.join(base, prod_dir)
        if not os.path.isdir(full_dir):
            continue
        for root, dirs, files in os.walk(full_dir):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', 'node_modules', '.git', 'dist', 'build')]
            for f in files:
                if not f.endswith('.py'):
                    continue
                full_path = os.path.join(root, f)
                if not is_production(full_path):
                    continue
                evts = extract_events_from_file(full_path)
                if evts:
                    rel = os.path.relpath(full_path, base)
                    prod_results[rel] = evts

    # 2) 收集 test publish
    test_results = {}
    test_dir = os.path.join(base, TEST_DIR)
    if os.path.isdir(test_dir):
        for root, dirs, files in os.walk(test_dir):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', 'logs')]
            for f in files:
                if not f.endswith('.py'):
                    continue
                full_path = os.path.join(root, f)
                if not is_production(full_path):
                    continue
                evts = extract_events_from_file(full_path)
                if evts:
                    rel = os.path.relpath(full_path, base)
                    test_results[rel] = evts

    print(f"=== PRODUCTION ({len(prod_results)} files) ===")
    for fp, evts in sorted(prod_results.items()):
        print(f"\n## {fp}")
        for evt, line, kind in evts:
            print(f"  L{line} [{kind}] {evt}")

    print(f"\n\n=== TESTS ({len(test_results)} files) ===")
    for fp, evts in sorted(test_results.items()):
        print(f"\n## {fp}")
        for evt, line, kind in evts:
            print(f"  L{line} [{kind}] {evt}")


if __name__ == '__main__':
    main()
