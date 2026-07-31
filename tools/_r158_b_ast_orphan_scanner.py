#!/usr/bin/env python3
"""R158-B AST-based 精确 ORPHAN_PUB/SUB 扫描器

使用 AST 解析, 准确识别 publish/subscribe 调用, 避免字符串误报
"""
import ast
from pathlib import Path
from collections import defaultdict

ROOT = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui')

publish_events = defaultdict(list)  # event_name -> [(file, line, type)]
subscribe_events = defaultdict(list)

EXCLUDE_DIRS = {'.pytest_cache', '__pycache__', '.git', 'node_modules', 'dist', 'build', '.venv'}

def get_call_name(node):
    """获取函数调用名 (a.b().c() → 链式最后一个)"""
    if isinstance(node, ast.Call):
        return get_call_name(node.func)
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None

def extract_first_arg_str(node):
    """提取 publish/subscribe 的第一个参数 (字符串字面量)"""
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return ('string', first.value)
    if isinstance(first, ast.Name):
        return ('name', first.id)
    if isinstance(first, ast.Attribute):
        return ('attr', ast.unparse(first))
    return None

def extract_kwargs(node):
    """提取 kwargs (publish("event", data=X))"""
    kwargs = []
    for kw in node.keywords:
        if isinstance(kw.value, ast.Constant):
            kwargs.append((kw.arg, 'const', kw.value.value))
        elif isinstance(kw.value, ast.Name):
            kwargs.append((kw.arg, 'name', kw.value.id))
        else:
            kwargs.append((kw.arg, 'expr', ast.unparse(kw.value)[:30]))
    return kwargs

def is_publish_or_subscribe(node):
    """检查是否是 publish/subscribe 调用"""
    name = get_call_name(node)
    return name in ('publish', 'subscribe', 'unsubscribe')

# 第一遍: 找出所有字符串字面量
string_to_files_publish = defaultdict(list)  # 字符串事件名 → 源文件列表
string_to_files_subscribe = defaultdict(list)

# 第二遍: 找出所有 Name 引用 (变量, 可能是 class)
class_known = {}  # 类名 → [文件]

all_class_uses = defaultdict(list)  # 类名 → [(file, line, kind)] where kind is publish/subscribe/import/definition

for filepath in ROOT.rglob('*.py'):
    parts = filepath.parts
    if any(ex in parts for ex in EXCLUDE_DIRS):
        continue
    try:
        source = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    rel = filepath.relative_to(ROOT)
    try:
        tree = ast.parse(source)
    except Exception:
        continue

    for node in ast.walk(tree):
        # 找类定义
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id.endswith('Event'):
                    class_known[base.id] = str(rel)
                if isinstance(base, ast.Attribute) and base.attr.endswith('Event'):
                    class_known[base.attr] = str(rel)
            if node.name.endswith('Event'):
                class_known[node.name] = str(rel)

        # 找 from ... import ...
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name.endswith('Event'):
                    class_known[alias.name] = str(rel)

        # 找 publish/subscribe
        if isinstance(node, ast.Call) and is_publish_or_subscribe(node):
            name = get_call_name(node)
            arg_info = extract_first_arg_str(node)
            line = getattr(node, 'lineno', 0)
            if not arg_info:
                continue
            kind, ev = arg_info
            if kind == 'string':
                if name == 'publish':
                    string_to_files_publish[ev].append((str(rel), line))
                else:
                    string_to_files_subscribe[ev].append((str(rel), line))
            else:
                # 变量/属性引用
                if name == 'publish':
                    all_class_uses[ev].append((str(rel), line, 'publish', name))
                else:
                    all_class_uses[ev].append((str(rel), line, 'subscribe', name))

print('=== R158-B AST 精确 ORPHAN_PUB/SUB 扫描结果 ===\n')

print(f'字符串 publish 事件: {len(string_to_files_publish)} 个')
print(f'字符串 subscribe 事件: {len(string_to_files_subscribe)} 个')
print()

# 字符串事件 ORPHAN 分析
pub_str_set = set(string_to_files_publish.keys())
sub_str_set = set(string_to_files_subscribe.keys())
str_orphan_pub = pub_str_set - sub_str_set
str_orphan_sub = sub_str_set - pub_str_set
str_paired = pub_str_set & sub_str_set

print(f'=== 字符串事件 PAIRED: {len(str_paired)} 个 ===')
for e in sorted(str_paired):
    p = len(string_to_files_publish[e])
    s = len(string_to_files_subscribe[e])
    print(f'  {e}: publish {p} / subscribe {s}')

print(f'\n=== 字符串事件 ORPHAN_PUB: {len(str_orphan_pub)} 个 ===')
for e in sorted(str_orphan_pub):
    print(f'\n  {e}:')
    for f, ln in string_to_files_publish[e][:5]:
        print(f'    -> {f}:{ln}')

print(f'\n=== 字符串事件 ORPHAN_SUB: {len(str_orphan_sub)} 个 ===')
for e in sorted(str_orphan_sub):
    print(f'\n  {e}:')
    for f, ln in string_to_files_subscribe[e][:5]:
        print(f'    -> {f}:{ln}')

# 类事件分析 (Name/Attr 形式)
print(f'\n\n=== 类事件 (Name/Attr 形式) ===')
print(f'已发现的可能 Event 类: {len(class_known)} 个')

# 过滤: 只看 *Event 后缀的变量使用
class_event_uses = {k: v for k, v in all_class_uses.items() if k.endswith('Event')}
class_event_uses_set = set(class_event_uses.keys())

class_pub = {k for k, v in class_event_uses.items() if any(u[2] == 'publish' for u in v)}
class_sub = {k for k, v in class_event_uses.items() if any(u[2] == 'subscribe' for u in v)}

class_orphan_pub = class_pub - class_sub
class_orphan_sub = class_sub - class_pub
class_paired = class_pub & class_sub

print(f'\n类事件 PAIRED: {len(class_paired)}')
for e in sorted(class_paired):
    pubs = [u for u in class_event_uses[e] if u[2] == 'publish']
    subs = [u for u in class_event_uses[e] if u[2] == 'subscribe']
    print(f'  {e}: publish {len(pubs)} / subscribe {len(subs)}')

print(f'\n类事件 ORPHAN_PUB: {len(class_orphan_pub)}')
for e in sorted(class_orphan_pub):
    pubs = [u for u in class_event_uses[e] if u[2] == 'publish']
    print(f'\n  {e}: {len(pubs)} publish sites')
    for f, ln, _, _ in pubs[:3]:
        print(f'    -> {f}:{ln}')

print(f'\n类事件 ORPHAN_SUB: {len(class_orphan_sub)}')
for e in sorted(class_orphan_sub):
    subs = [u for u in class_event_uses[e] if u[2] == 'subscribe']
    print(f'\n  {e}: {len(subs)} subscribe sites')
    for f, ln, _, _ in subs[:3]:
        print(f'    -> {f}:{ln}')
