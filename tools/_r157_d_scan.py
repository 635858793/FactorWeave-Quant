"""R157-D 扫描 9 项 R51 软解析 logger.debug 升级目标"""
import ast
import re

target_file = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\importdata\unified_data_import_engine.py"

with open(target_file, "r", encoding="utf-8") as f:
    source = f.read()
    lines = source.splitlines()

tree = ast.parse(source)

candidates = []

# AST 递归找 except 块后的 logger.debug 调用
def visit_node(node, parent_except=None):
    if isinstance(node, ast.ExceptHandler):
        parent_except = node
        # 检查 except 块中的第一个 stmt
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call):
            call = node.body[0].value
            if (isinstance(call.func, ast.Attribute) and
                isinstance(call.func.value, ast.Name) and
                call.func.value.id == "logger" and
                call.func.attr == "debug"):
                candidates.append({
                    "line": node.lineno,
                    "col": node.col_offset,
                    "exc_type": ast.unparse(node.type) if node.type else "Exception",
                    "msg": ast.unparse(call),
                })
    for child in ast.iter_child_nodes(node):
        visit_node(child, parent_except)

visit_node(tree)

print(f"Found {len(candidates)} candidates with except + logger.debug in {target_file}:")
print()
for c in candidates:
    # 提取 logger.debug 调用的内容
    line_content = lines[c["line"] - 1] if c["line"] - 1 < len(lines) else ""
    print(f"L{c['line']:>4} (col={c['col']:>3}) exc={c['exc_type']}")
    print(f"        {line_content.strip()[:200]}")
    print()
