"""检查 BettaFishMonitoringService._do_dispose 实现."""
import ast
from pathlib import Path

fp = Path('core/services/bettafish_monitoring_service.py')
content = fp.read_text(encoding='utf-8')
tree = ast.parse(content)
for node in ast.iter_child_nodes(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'BettaFishMonitoringService':
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == '_do_dispose':
                print('=== _do_dispose found ===')
                src = ast.unparse(item)
                print(src)
                # Check if has super()._do_dispose()
                has_super = 'super()._do_dispose' in src
                print(f'\n=== Has super()._do_dispose(): {has_super} ===')
                break
        break
