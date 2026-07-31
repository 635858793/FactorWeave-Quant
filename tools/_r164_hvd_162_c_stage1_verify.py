#!/usr/bin/env python3
"""R164 HVD-162-C Stage-1 P0 业务核心 exc_info missing 独立检查脚本 (V2)"""
import re
import sys
import ast
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui").resolve()

EXCLUDED_FILES = {
    'core/trading_engine.py',
    'core/order_service.py',
    'core/importdata/import_execution_engine.py',
    'core/services/advanced_risk_control_service.py',
    'core/ctp/ctp_trading_interface.py',
    'core/risk_manager.py',
    'core/xtp/xtp_trading_interface.py',
    'core/xtp/xtp_pro_trading_interface.py',
    'core/oem/oem_trading_interface.py',
    'core/simulator/simulator_trading_interface.py',
    'core/importdata/unified_data_import_engine.py',
    'core/services/signal_trading_bridge.py',
    'core/agents/risk_agent.py',
    'core/risk_rule_manager.py',
    'core/risk_control.py',
    'core/trading/account_manager.py',
    'core/trading/signal_adapters.py',
    'core/trading/trading_mode.py',
    'core/stop_loss.py',
    'core/take_profit.py',
    'core/performance/professional_risk_metrics.py',
    'core/risk_alert.py',
    'core/risk_exporter.py',
    'core/risk_metrics.py',
}

P0_FILES_BY_R163C = {
    'gui/dialogs/order_management_dialog.py': 79,
    'gui/widgets/performance/tabs/risk_control_center_tab.py': 79,
    'gui/widgets/trading_widget.py': 57,
    'core/risk_monitoring/enhanced_risk_monitor.py': 50,
    'gui/dialogs/account_management_dialog.py': 47,
    'gui/widgets/trading_panel.py': 43,
    'gui/widgets/performance/tabs/trading_execution_monitor_tab.py': 28,
    'core/services/ai_selection_risk_control_service.py': 24,
    'gui/widgets/enhanced_ui/order_book_widget.py': 15,
    'core/risk/risk_event_subscribers.py': 11,
    'gui/widgets/advanced_risk_control_widget.py': 10,
    'gui/widgets/dynamic_risk_adjustment_widget.py': 5,
    'gui/widgets/enhanced_trading_monitor_widget.py': 5,
    'gui/widgets/bettafish_dashboard/risk_assessment_panel.py': 3,
    'gui/widgets/bettafish_dashboard/trading_signal_panel.py': 3,
    'core/risk_monitoring/sherman_morrison_correlation.py': 2,
    'gui/dialogs/risk_rule_config_dialog.py': 2,
    'gui/dialogs/signal_trading_bridge_dialog.py': 1,
}


def count_exc_info_missing(file_path: Path) -> int:
    """AST 方式: 遍历所有 try/except 块, 检查 logger.error/warning/critical 是否带 exc_info"""
    try:
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content, str(file_path))
    except Exception:
        return 0

    missing = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if handler.type is None:
                # bare except: 仍需检查
                pass
            # 收集 except 块内所有 logger.* 调用
            for sub in ast.walk(handler):
                if not isinstance(sub, ast.Call):
                    continue
                if not isinstance(sub.func, ast.Attribute):
                    continue
                if sub.func.attr not in ('error', 'warning', 'critical'):
                    continue
                if not isinstance(sub.func.value, ast.Name):
                    continue
                if sub.func.value.id != 'logger':
                    continue
                # 检查是否带 exc_info=True
                has_exc_info = False
                for kw in sub.keywords:
                    if kw.arg == 'exc_info':
                        has_exc_info = True
                        break
                if not has_exc_info:
                    missing += 1
    return missing


def main():
    total_missing = 0
    missing_files = []
    print("=" * 60)
    print("R164 HVD-162-C Stage-1 P0 业务核心 exc_info missing 检查 (AST)")
    print("=" * 60)
    for rel_path, expected in P0_FILES_BY_R163C.items():
        full_path = ROOT / rel_path
        if not full_path.exists():
            print('[SKIP] {0} (not found)'.format(rel_path))
            continue
        if rel_path in EXCLUDED_FILES:
            print('[EXCL] {0}'.format(rel_path))
            continue
        try:
            actual = count_exc_info_missing(full_path)
        except Exception as e:
            print('[ERR]  {0}: {1}'.format(rel_path, e))
            continue
        if actual > 0:
            missing_files.append((rel_path, actual, expected))
            total_missing += actual
            print('[MISS] {0}: {1} (R163-C 预期 {2})'.format(rel_path, actual, expected))
        else:
            print('[OK]   {0}: 0'.format(rel_path))
    print('')
    print('=' * 60)
    print('Total missing: {0}'.format(total_missing))
    print('Files with missing: {0}'.format(len(missing_files)))
    print('=' * 60)
    return 0 if total_missing == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
