"""R176-B-3 验证: risk_rule_manager.py R51 #5 0 剩余违规"""
import ast

fp = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\risk_rule_manager.py'
with open(fp, 'r', encoding='utf-8') as f:
    source = f.read()
tree = ast.parse(source)

violations = []
total_except = 0


def visit(node):
    global total_except
    if isinstance(node, ast.ExceptHandler):
        total_except += 1
        block_text = ast.unparse(node)
        for log_func in ['logger.warning', 'logger.error', 'logger.exception']:
            if log_func in block_text and 'exc_info=True' not in block_text:
                violations.append({'line': node.lineno, 'log_func': log_func})
    for child in ast.iter_child_nodes(node):
        visit(child)


visit(tree)
print(f'Total except: {total_except}, Violations: {len(violations)}')
for v in violations:
    line = v['line']
    func = v['log_func']
    print(f'  L{line} {func}')
if len(violations) == 0:
    print('✅ R51 #5 100% 合规 (R176-B-3 修复成功)')
else:
    print('❌ 仍有违规, 需继续修复')
