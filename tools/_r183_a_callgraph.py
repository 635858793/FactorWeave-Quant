"""R183-A 分析 _register_* 阶段实际调用关系"""
import ast

with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\service_bootstrap.py", 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

# Find the ServiceBootstrap class
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'ServiceBootstrap':
        sb = node
        break

# Collect all _register_* method names
register_methods = [item.name for item in sb.body if isinstance(item, ast.FunctionDef) and item.name.startswith('_register_')]

# Find all calls to _register_* methods (anywhere in the class)
called_methods = set()
for item in sb.body:
    if isinstance(item, ast.FunctionDef):
        for sub in ast.walk(item):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute) and func.attr.startswith('_register_') and func.attr in register_methods:
                    called_methods.add((func.attr, sub.lineno, item.name))

print(f"Total _register_* methods defined: {len(register_methods)}")
print(f"Total _register_* call sites: {len(called_methods)}")
print()

# Find methods that are NEVER called
called_method_names = {c[0] for c in called_methods}
never_called = [m for m in register_methods if m not in called_method_names]
print(f"=== _register_* methods NEVER called from anywhere === ({len(never_called)})")
for m in never_called:
    print(f"  {m}")

print()
print("=== Call sites detail (caller -> callee, line) ===")
for callee, line, caller in sorted(called_methods, key=lambda x: (x[2], x[1])):
    print(f"  {caller:35} -> {callee:50} @ L{line}")
