"""R130 子智能体 D 5+1 服务架构现状扫描工具"""
import re
import os
import sys

# 7+1 服务架构: R130 实施后预期
FILES = {
    'core/risk_manager.py': 'RiskManager',
    'core/services/trading_service.py': 'TradingService',
    'core/trading/account_manager.py': 'AccountManager',
    'core/money_manager.py': 'MoneyManager',
    'core/trading_controller.py': 'TradingController',
    'gui/widgets/trading_panel.py': 'TradingPanel',
    'gui/dialogs/account_management_dialog.py': 'AccountManagementDialog',
}

KEY_METHODS = [
    '_check_5_service_consistency',
    'set_current_account_id',
    '_on_account_switched',
    'get_current_account_id',
    '_current_account_id',
    '_subscribe_account_switched_event',
    '_unsubscribe_account_switched_event',
]


def parse_class_methods(content, class_name):
    """提取类的所有 def 方法名 (不依赖缩进正则, 用 AST)"""
    import ast
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}
    classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods[item.name] = item.lineno
            classes[node.name] = methods
    return classes


def main():
    print("=" * 100)
    print("R130 5+1 服务架构现状扫描 (R130 实施前基线)")
    print("=" * 100)
    results = []
    for rel, cls_name in FILES.items():
        try:
            with open(rel, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            classes = parse_class_methods(content, cls_name)
            if cls_name not in classes:
                print(f"\n[!] {rel}: class {cls_name} NOT FOUND")
                continue
            methods = classes[cls_name]
            print(f"\n[*] {rel} ({cls_name}):")
            for km in KEY_METHODS:
                if km in methods:
                    print(f"    OK  {km}() L{methods[km]}")
                    results.append((rel, km, 'OK', methods[km]))
                else:
                    print(f"    XX  {km}() MISSING")
                    results.append((rel, km, 'MISSING', None))
        except Exception as e:
            print(f"\n[!] {rel}: ERROR {e}")
            results.append((rel, '*', 'ERROR', str(e)))

    print("\n" + "=" * 100)
    print("汇总 (R130 实施前):")
    print("=" * 100)
    miss = sum(1 for r in results if r[2] == 'MISSING')
    print(f"  缺失关键方法总数: {miss}")
    for r in results:
        if r[2] == 'MISSING':
            print(f"    - {r[0]}: {r[1]}")


if __name__ == '__main__':
    main()
