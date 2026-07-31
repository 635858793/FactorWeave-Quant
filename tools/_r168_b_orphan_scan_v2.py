"""R168-B v2: 支持 _subscribe_event / _publish_event 等包装方法"""
import os
import ast
from collections import defaultdict

publish_events = defaultdict(list)
subscribe_events = defaultdict(list)

# 已知会调用 publish/subscribe 的方法名 (含包装)
PUBLISH_FUNCS = {'publish', '_publish', '_publish_event', 'publish_event', 'safe_publish',
                 'bus_publish', 'bus.publish', 'event_bus.publish'}
SUBSCRIBE_FUNCS = {'subscribe', '_subscribe', '_subscribe_event', 'subscribe_event', 'safe_subscribe',
                   'bus_subscribe', 'bus.subscribe', 'event_bus.subscribe'}

def extract_string_literals_from_python(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return [], []
    pubs = []
    subs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            # 也支持 self._subscribe_event / self._publish_event
            if func_name not in ('publish', 'subscribe', '_publish_event', '_subscribe_event'):
                continue
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                event_name = node.args[0].value
                line_no = node.lineno
                if func_name in ('publish', '_publish_event'):
                    pubs.append((event_name, file_path, line_no))
                else:
                    subs.append((event_name, file_path, line_no))
    return pubs, subs

target_dirs = ['core', 'plugins', 'gui', 'tests', 'scripts', 'web', 'components']
file_count = 0
for target in target_dirs:
    if not os.path.isdir(target):
        continue
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules', 'migrations')]
        for f in files:
            if not f.endswith('.py'):
                continue
            if f.endswith('.bak') or '.bak_' in f:
                continue
            # 排除 .rXXX_pre 备份文件
            if any(part.startswith('r') and part[1:].isdigit() and part.endswith('_pre')
                   for part in f.split('.')):
                continue
            fp = os.path.join(root, f)
            pubs, subs = extract_string_literals_from_python(fp)
            for ev, p, l in pubs:
                publish_events[ev].append(f'{p}:{l}')
            for ev, p, l in subs:
                subscribe_events[ev].append(f'{p}:{l}')
            file_count += 1

print(f'=== 文件扫描统计 ===')
print(f'扫描文件数: {file_count}')
print(f'Total publish: {sum(len(v) for v in publish_events.values())}')
print(f'Total subscribe: {sum(len(v) for v in subscribe_events.values())}')
print(f'Unique publish event names: {len(publish_events)}')
print(f'Unique subscribe event names: {len(subscribe_events)}')

print()
print('=== ORPHAN_PUB (有发布无订阅) ===')
orphan_pub_count = 0
for ev, locs in sorted(publish_events.items()):
    if ev not in subscribe_events:
        print(f'  {ev}: {len(locs)} publish')
        for loc in locs[:5]:
            print(f'    {loc}')
        if len(locs) > 5:
            print(f'    ... +{len(locs)-5} more')
        orphan_pub_count += 1
print(f'  Total ORPHAN_PUB: {orphan_pub_count}')

print()
print('=== ORPHAN_SUB (有订阅无发布) ===')
orphan_sub_count = 0
for ev, locs in sorted(subscribe_events.items()):
    if ev not in publish_events:
        print(f'  {ev}: {len(locs)} subscribe')
        for loc in locs[:5]:
            print(f'    {loc}')
        if len(locs) > 5:
            print(f'    ... +{len(locs)-5} more')
        orphan_sub_count += 1
print(f'  Total ORPHAN_SUB: {orphan_sub_count}')
