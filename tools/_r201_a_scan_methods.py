"""R201-A 方法扫描工具: 扫描 order_service.py 和 risk_event_subscribers.py 所有方法"""
import ast
import sys

TARGETS = {
    'order_service': 'core/trading/order_service.py',
    'risk_event_subscribers': 'core/risk/risk_event_subscribers.py',
}

def scan(path, target_class=None):
    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if target_class and node.name != target_class:
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    args = [a.arg for a in item.args.args]
                    has_account = 'account_id' in args
                    results.append({
                        'class': node.name,
                        'line': item.lineno,
                        'name': item.name,
                        'args': args,
                        'has_account_id': has_account,
                    })
    return results

if __name__ == '__main__':
    for name, path in TARGETS.items():
        print(f'=== {name} ({path}) ===')
        results = scan(path)
        for r in results:
            marker = ' [HAS account_id]' if r['has_account_id'] else ''
            print(f"L{r['line']:>5} {r['class']}.{r['name']}({', '.join(r['args'][:6])}){marker}")
        print(f'Total: {len(results)} methods')
        print()
