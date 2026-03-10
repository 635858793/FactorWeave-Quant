# -*- coding: utf-8 -*-
"""验证RightPanel删除风险评估后的代码正确性"""

from core.ui.panels.right_panel import RightPanel

methods_to_check = [
    '_create_signal_tab',
    '_create_backtest_tab', 
    '_update_signal_analysis_safe',
    '_clear_backtest_results',
    '_update_backtest_results_safe'
]

deleted_methods = [
    '_create_risk_tab',
    '_update_risk_analysis_safe'
]

print('=== 保留的方法 ===')
for method in methods_to_check:
    exists = hasattr(RightPanel, method)
    status = 'OK' if exists else 'MISSING'
    print(f'{method}: {status}')

print()
print('=== 已删除的方法 ===')
for method in deleted_methods:
    exists = hasattr(RightPanel, method)
    status = 'DELETED' if not exists else 'STILL EXISTS!'
    print(f'{method}: {status}')

print()
print('=== 类基本信息 ===')
print(f'类名: {RightPanel.__name__}')
print(f'基类: {RightPanel.__bases__}')
print('验证完成!')
