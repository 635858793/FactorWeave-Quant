"""R183-A AST 精确分析工具"""
import ast

with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\service_bootstrap.py", 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

# Find the ServiceBootstrap class
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'ServiceBootstrap':
        sb = node
        break

# Find all _register_* methods
print(f"{'Method':<55} {'Start':>6} {'End':>6} {'Lines':>6} {'BodyLines':>9}")
print('-'*88)
register_methods = []
for item in sb.body:
    if isinstance(item, ast.FunctionDef) and item.name.startswith('_register_'):
        end_line = item.end_lineno
        start_line = item.lineno
        body_lines = (item.end_lineno - item.body[0].lineno + 1) if item.body else 0
        register_methods.append((item.name, start_line, end_line, end_line - start_line + 1, body_lines))
        print(f"{item.name:<55} {start_line:>6} {end_line:>6} {end_line - start_line + 1:>6} {body_lines:>9}")

print(f"\nTotal _register_* methods: {len(register_methods)}")

# Find bootstrap() main call sequence
print("\n\n--- bootstrap() main sequence (bootstrap() method, look for self._register_* calls) ---")
for item in sb.body:
    if isinstance(item, ast.FunctionDef) and item.name == 'bootstrap':
        for sub in ast.walk(item):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute) and func.attr.startswith('_register_'):
                    print(f"  L{sub.lineno}: self.{func.attr}()")

# Find health_check methods
print("\n\n--- health_check methods in ServiceBootstrap ---")
for item in sb.body:
    if isinstance(item, ast.FunctionDef) and 'health' in item.name.lower():
        print(f"  {item.name}: L{item.lineno}-{item.end_lineno}")
