"""R176-B-4 重新验证: service_bootstrap.py 业务关键路径 logger.debug 违规"""
import ast

fp = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\service_bootstrap.py'
with open(fp, 'r', encoding='utf-8') as f:
    source = f.read()
tree = ast.parse(source)

violations = []


def visit(node, current_func=None):
    if isinstance(node, ast.FunctionDef):
        current_func = node.name
    if isinstance(node, ast.ExceptHandler):
        block_text = ast.unparse(node)
        # 移除注释
        lines = [l for l in block_text.split('\n') if not l.strip().startswith('#')]
        code_only = '\n'.join(lines)
        if 'logger.debug' in code_only and 'exc_info=True' not in code_only:
            # 业务关键路径
            is_business = any(kw in code_only for kw in [
                'publish', 'service.', 'order', 'risk', 'trade', 'position', 'started', 'stopped', 'error', 'shut'
            ])
            if is_business:
                violations.append({
                    'line': node.lineno,
                    'func': current_func,
                    'preview': block_text[:200].replace('\n', ' | '),
                })
    for child in ast.iter_child_nodes(node):
        visit(child, current_func)


visit(tree)
print(f'业务关键路径 logger.debug 违规: {len(violations)}')
for v in violations:
    print(f'  L{v["line"]} {v["func"]}: {v["preview"]}')
print('✅ 0 违规' if len(violations) == 0 else '❌ 仍有违规')
