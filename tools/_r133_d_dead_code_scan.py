"""R133 子智能体 D: 全项目死代码深度分析 (R6 §6.1 8+2 铁律 + R104 §12 5 铁律)

跨 5+ 子目录 AST 扫描:
1. 提取每个模块的 top-level functions + classes
2. 全项目 import 关系索引
3. 排除: 启动入口 (main.py/quick_start.py) + 工具脚本 (tools/) + 测试文件 (tests/)
4. 标记: 模块 0 外部 import + 0 外部 class 引用 = 死模块候选
"""
import ast
import os
import sys
import json
from pathlib import Path
from typing import Dict, Set, List, Tuple

ROOT = Path('.').resolve()
SEARCH_DIRS = ['core', 'tests', 'plugins', 'gui', 'scripts', 'backtest', 'optimization']
SKIP_DIRS = ['__pycache__', '.git', '.pytest_cache', '.cache', 'node_modules']
EXCLUDE_PATTERNS = [
    'main.py', 'quick_start.py', 'install_dependencies.py', 'verify_r111_refactor.py',
    'api_server.py', 'conftest.py',
    '/tools/', '/_audit_', '/_r',  # 工具脚本
    '/tests/',  # 测试文件
    'setup.py', '__init__.py',  # 初始化文件
]

def path_to_module(rel_path: str) -> str:
    if rel_path.endswith('.py'):
        rel_path = rel_path[:-3]
    if rel_path.endswith('__init__'):
        rel_path = rel_path[:-9]
    return rel_path.replace(os.sep, '.').replace('/', '.')

def iter_py_files() -> List[str]:
    result = []
    for sdir in SEARCH_DIRS:
        dp = ROOT / sdir
        if not dp.exists(): continue
        for root, dirs, files in os.walk(dp):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith('.py'):
                    result.append(os.path.join(root, f))
    # 根目录
    for f in os.listdir(ROOT):
        if f.endswith('.py') and f != 'setup.py':
            full = ROOT / f
            if full.is_file() and str(full) not in result:
                result.append(str(full))
    return result

def extract_symbols(fp: str) -> Tuple[List[str], List[str]]:
    """提取模块的 top-level classes + functions. 返回 ([ClassName...], [func_name...])"""
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return [], []
    classes, functions = [], []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
    return classes, functions

def is_excluded(fp: str) -> bool:
    fp_norm = fp.replace('\\', '/')
    return any(pat in fp_norm for pat in EXCLUDE_PATTERNS)

def main():
    py_files = iter_py_files()
    print(f"Total py files: {len(py_files)}", file=sys.stderr)

    # 索引 1: 所有 import 关系
    importers: Dict[str, Set[str]] = {}  # module_name -> set of importing files
    symbol_refs: Dict[str, Set[Tuple[str, str]]] = {}  # symbol_name -> set of (file, import_type)

    for fp in py_files:
        rel = os.path.relpath(fp, ROOT)
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
                importers.setdefault(target, set()).add(fp)
                for alias in node.names:
                    sym = alias.asname or alias.name
                    symbol_refs.setdefault(sym, set()).add((fp, 'import_from'))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    importers.setdefault(target, set()).add(fp)
                    sym = alias.asname or alias.name
                    symbol_refs.setdefault(sym, set()).add((fp, 'import'))

    # 索引 2: 跨文件 name/attr 引用 (类/函数使用)
    for fp in py_files:
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not (node.id.startswith('__') and node.id.endswith('__')):
                symbol_refs.setdefault(node.id, set()).add((fp, 'name'))
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    symbol_refs.setdefault(node.value.id, set()).add((fp, 'attr'))

    # 找死模块
    dead_candidates = []
    total_modules = 0
    for fp in py_files:
        if is_excluded(fp):
            continue
        rel = os.path.relpath(fp, ROOT)
        module = path_to_module(rel)
        total_modules += 1

        classes, functions = extract_symbols(fp)
        if not classes and not functions:
            continue  # 空模块

        # 检查导入
        importers_of_module = importers.get(module, set())
        # 排除自身
        importers_of_module.discard(fp)

        # 排除父包导入 (e.g. core.services 导入 core.services.service_bootstrap)
        if importers_of_module:
            dead = False
        else:
            # 检查类名/函数名是否被其他文件引用
            all_syms = set(classes) | set(functions)
            external_refs = set()
            for sym in all_syms:
                for ref_fp, ref_type in symbol_refs.get(sym, set()):
                    if ref_fp != fp:
                        external_refs.add(ref_fp)
            if not external_refs:
                dead = True
            else:
                dead = False

        if dead:
            dead_candidates.append({
                'file': rel,
                'module': module,
                'classes': classes,
                'functions': functions,
            })

    print(f"Total production modules: {total_modules}")
    print(f"Truly dead modules: {len(dead_candidates)}")
    for d in dead_candidates:
        print(f"  - {d['file']}  (classes={len(d['classes'])}, functions={len(d['functions'])})")

    # 保存 JSON
    with open('.audit_r133_d_dead_candidates.json', 'w', encoding='utf-8') as f:
        json.dump(dead_candidates, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
