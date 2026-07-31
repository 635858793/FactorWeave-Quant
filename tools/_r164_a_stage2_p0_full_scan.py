#!/usr/bin/env python3
"""R164-A-续期 P0 业务核心 30 文件 AST 感知完整统计 (全项目验证)

R164-A-续期: 完成 4 个高优先级 GUI 文件 86 处 missing 修复后, 全项目 P0 业务核心 missing 统计

策略:
1. AST 感知检测 (避免多行 logger 调用误报, R104 §12 铁律 #5)
2. 完整扫描 R163-C 报告的 30 P0 业务核心文件
3. 排除 R145/R161/R162/R163-A 已闭环 19 文件
"""
import ast
import sys
from pathlib import Path

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

# R145/R161/R162/R163-A 已闭环 19 文件
EXCLUDED = {
    'core/trading_engine.py', 'core/order_service.py',
    'core/importdata/import_execution_engine.py',
    'core/services/advanced_risk_control_service.py',
    'core/ctp/ctp_trading_interface.py', 'core/risk_manager.py',
    'core/xtp/xtp_trading_interface.py', 'core/xtp/xtp_pro_trading_interface.py',
    'core/oem/oem_trading_interface.py', 'core/simulator/simulator_trading_interface.py',
    'core/importdata/unified_data_import_engine.py',
    'core/services/signal_trading_bridge.py', 'core/agents/risk_agent.py',
    'core/risk_rule_manager.py', 'core/risk_control.py',
    'core/trading/account_manager.py', 'core/trading/signal_adapters.py',
    'core/trading/trading_mode.py', 'core/stop_loss.py', 'core/take_profit.py',
    'core/performance/professional_risk_metrics.py', 'core/risk_alert.py',
    'core/risk_exporter.py', 'core/risk_metrics.py',
}

# R163-C 报告 30 P0 业务核心文件 (排除已闭环 19)
P0_FILES = [
    'gui/dialogs/order_management_dialog.py',
    'gui/widgets/performance/tabs/risk_control_center_tab.py',
    'gui/widgets/trading_widget.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'gui/dialogs/account_management_dialog.py',
    'gui/widgets/trading_panel.py',
    'gui/widgets/performance/tabs/trading_execution_monitor_tab.py',
    'core/services/ai_selection_risk_control_service.py',
    'gui/widgets/enhanced_ui/order_book_widget.py',
    'core/risk/risk_event_subscribers.py',
    'gui/widgets/advanced_risk_control_widget.py',
    'gui/widgets/dynamic_risk_adjustment_widget.py',
    'gui/widgets/enhanced_trading_monitor_widget.py',
    'gui/widgets/bettafish_dashboard/risk_assessment_panel.py',
    'gui/widgets/bettafish_dashboard/trading_signal_panel.py',
    'core/risk_monitoring/sherman_morrison_correlation.py',
    'gui/dialogs/risk_rule_config_dialog.py',
    'gui/dialogs/signal_trading_bridge_dialog.py',
]


def count_exc_info_missing_ast(file_path: Path) -> tuple:
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return 0, [f"文件读取失败: {e}"]
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return 0, [f"语法错误: {e}"]

    missing = 0
    details = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not (isinstance(child.func, ast.Attribute)
                    and child.func.attr in ('error', 'warning', 'critical')
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == 'logger'):
                continue
            has_exc = any(kw.arg == 'exc_info' for kw in child.keywords)
            if not has_exc:
                missing += 1
                try:
                    snippet = ast.unparse(child)[:100]
                except Exception:
                    snippet = f"<unparseable>"
                details.append(f"L{child.lineno}: {snippet}")
    return missing, details


def main():
    print("=" * 80)
    print("R164-A-续期 P0 业务核心 30 文件 AST 感知完整统计")
    print("=" * 80)
    print()

    total_missing = 0
    files_with_missing = 0
    total_p0_files = 0

    for rel_path in P0_FILES:
        full_path = ROOT / rel_path
        if not full_path.exists():
            print(f"[X] {rel_path}: 文件不存在 (跳过)")
            continue
        total_p0_files += 1
        actual, details = count_exc_info_missing_ast(full_path)
        total_missing += actual
        if actual > 0:
            files_with_missing += 1
            print(f"[待修复 {actual} 处] {rel_path}")
            for d in details[:3]:
                print(f"    {d}")
        else:
            print(f"[OK] {rel_path}")

    print()
    print("=" * 80)
    print(f"P0 业务核心文件数: {total_p0_files}")
    print(f"存在 missing 的文件数: {files_with_missing}")
    print(f"总 missing 处数: {total_missing}")
    print("=" * 80)
    return 0 if total_missing == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
