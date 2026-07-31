#!/usr/bin/env python3
"""R158-B 5+1 服务一致性验证 + 核心业务事件闭环审计

5+1 服务架构 (R120/R125/R128/R129/R158):
- RiskManager (core/risk_manager.py)
- TradingService (core/services/trading_service.py)
- AccountManager (core/trading/account_manager.py)
- MoneyManager (core/money_manager.py)
- TradingController (core/trading_controller.py)
+ TradingPanel (gui/widgets/trading_panel.py) - GUI 展示
+ AccountManagementDialog (gui/dialogs/account_management_dialog.py) - GUI 入口

每个服务都应:
1. 有 _current_account_id 字段
2. 有 set_current_account_id() / get_current_account_id() 方法
3. 订阅 AccountSwitchedEvent
4. 有 _check_5_service_consistency() 方法 (P1)
"""
import ast
from pathlib import Path

ROOT = Path(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui')

SERVICES = {
    'RiskManager': {
        'file': 'core/risk_manager.py',
        'expected_class': 'RiskManager',
    },
    'TradingService': {
        'file': 'core/services/trading_service.py',
        'expected_class': 'TradingService',
    },
    'AccountManager': {
        'file': 'core/trading/account_manager.py',
        'expected_class': 'AccountManager',
    },
    'MoneyManager': {
        'file': 'core/money_manager.py',
        'expected_class': 'MoneyManager',
    },
    'TradingController': {
        'file': 'core/trading_controller.py',
        'expected_class': 'TradingController',
    },
    'TradingPanel': {
        'file': 'gui/widgets/trading_panel.py',
        'expected_class': 'TradingPanel',
    },
    'AccountManagementDialog': {
        'file': 'gui/dialogs/account_management_dialog.py',
        'expected_class': 'AccountManagementDialog',
    },
}

print('=== R158-B 5+1 服务一致性验证 ===\n')

results = {}
for svc_name, info in SERVICES.items():
    file_path = ROOT / info['file']
    if not file_path.exists():
        print(f'❌ {svc_name}: 文件不存在 ({info["file"]})')
        results[svc_name] = {'exists': False}
        continue

    source = file_path.read_text(encoding='utf-8', errors='ignore')
    try:
        tree = ast.parse(source)
    except Exception as e:
        print(f'❌ {svc_name}: AST parse failed: {e}')
        results[svc_name] = {'exists': True, 'parse_ok': False}
        continue

    # 找到类
    target_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == info['expected_class']:
            target_class = node
            break

    if not target_class:
        print(f'❌ {svc_name}: 类 {info["expected_class"]} 不存在')
        results[svc_name] = {'exists': True, 'parse_ok': True, 'class_found': False}
        continue

    # 找方法
    methods = {}
    for node in target_class.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods[node.name] = node.lineno

    # 找 _current_account_id 字段
    has_field = '_current_account_id' in source
    has_setter = 'set_current_account_id' in methods
    has_getter = 'get_current_account_id' in methods
    has_on_account_switched = '_on_account_switched' in methods
    has_subscribe_method = any('_subscribe_account_switched' in m for m in methods)
    has_consistency = '_check_5_service_consistency' in methods

    # 找 AccountSwitchedEvent 订阅
    has_event_sub = 'AccountSwitchedEvent' in source and 'subscribe' in source

    results[svc_name] = {
        'exists': True,
        'parse_ok': True,
        'class_found': True,
        'has_field': has_field,
        'has_setter': has_setter,
        'has_getter': has_getter,
        'has_on_account_switched': has_on_account_switched,
        'has_subscribe_method': has_subscribe_method,
        'has_consistency': has_consistency,
        'has_event_sub': has_event_sub,
        'methods': methods,
    }

    print(f'=== {svc_name} ({info["file"]}) ===')
    print(f'  Class: {info["expected_class"]} (L{target_class.lineno})')
    print(f'  _current_account_id 字段: {"✅" if has_field else "❌"}')
    print(f'  set_current_account_id: {"✅" if has_setter else "❌"} (L{methods.get("set_current_account_id", "?")})')
    print(f'  get_current_account_id: {"✅" if has_getter else "❌"} (L{methods.get("get_current_account_id", "?")})')
    print(f'  _on_account_switched: {"✅" if has_on_account_switched else "❌"} (L{methods.get("_on_account_switched", "?")})')
    print(f'  _subscribe_account_switched_*: {"✅" if has_subscribe_method else "❌"}')
    print(f'  _check_5_service_consistency: {"✅" if has_consistency else "❌"} (L{methods.get("_check_5_service_consistency", "?")})')
    print(f'  AccountSwitchedEvent.subscribe 调用: {"✅" if has_event_sub else "❌"}')
    print()

# 总结
print('\n=== 5+1 服务一致性总结 ===')
all_passed = True
for svc_name, info in SERVICES.items():
    r = results.get(svc_name, {})
    if not r.get('class_found'):
        all_passed = False
        print(f'  ❌ {svc_name}: 类未找到')
        continue
    checks = [
        r.get('has_field'),
        r.get('has_setter'),
        r.get('has_getter'),
        r.get('has_on_account_switched'),
        r.get('has_subscribe_method'),
    ]
    if all(checks):
        print(f'  ✅ {svc_name}: 5+1 关键字段/方法齐备 (字段 + setter + getter + 事件订阅)')
    else:
        all_passed = False
        missing = []
        if not r.get('has_field'): missing.append('_current_account_id 字段')
        if not r.get('has_setter'): missing.append('set_current_account_id')
        if not r.get('has_getter'): missing.append('get_current_account_id')
        if not r.get('has_on_account_switched'): missing.append('_on_account_switched')
        if not r.get('has_subscribe_method'): missing.append('_subscribe_account_switched_*')
        print(f'  ❌ {svc_name}: 缺失 {missing}')

print(f'\n5+1 服务整体: {"✅ 100% 通过" if all_passed else "❌ 有缺失"}')
