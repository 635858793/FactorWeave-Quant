#!/usr/bin/env python3
"""
回测UI功能快速验证脚本 - 简化版
只测试导入和类结构，不加载完整系统
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试导入"""
    print("="*60)
    print("测试1: 验证核心模块导入")
    print("="*60)

    results = []
    passed = 0
    failed = 0

    # 测试ProfessionalBacktestWidget
    try:
        from gui.widgets.backtest_widget import ProfessionalBacktestWidget
        from gui.widgets.backtest_widget import RealTimeChart, MetricsPanel, ControlPanel
        print("✅ ProfessionalBacktestWidget导入: PASS")
        print(f"   - ProfessionalBacktestWidget: {ProfessionalBacktestWidget.__name__}")
        print(f"   - RealTimeChart: {RealTimeChart.__name__}")
        print(f"   - MetricsPanel: {MetricsPanel.__name__}")
        print(f"   - ControlPanel: {ControlPanel.__name__}")
        passed += 1
    except Exception as e:
        print(f"❌ ProfessionalBacktestWidget导入: FAIL - {e}")
        failed += 1

    # 测试ModernUnifiedPerformanceWidget
    try:
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        print("✅ ModernUnifiedPerformanceWidget导入: PASS")
        passed += 1
    except Exception as e:
        print(f"❌ ModernUnifiedPerformanceWidget导入: FAIL - {e}")
        failed += 1

    # 测试RightPanel
    try:
        from core.ui.panels.right_panel import RightPanel
        print("✅ RightPanel导入: PASS")
        passed += 1
    except Exception as e:
        print(f"❌ RightPanel导入: FAIL - {e}")
        failed += 1

    # 测试BacktestUILauncher
    try:
        from gui.backtest_ui_launcher import BacktestUILauncher
        print("✅ BacktestUILauncher导入: PASS")
        passed += 1
    except Exception as e:
        print(f"❌ BacktestUILauncher导入: FAIL - {e}")
        failed += 1

    # 测试RealTimeBacktestMonitor
    try:
        from backtest.real_time_backtest_monitor import RealTimeBacktestMonitor
        print("✅ RealTimeBacktestMonitor导入: PASS")
        passed += 1
    except Exception as e:
        print(f"❌ RealTimeBacktestMonitor导入: FAIL - {e}")
        failed += 1

    # 测试ProfessionalUISystem
    try:
        from backtest.professional_ui_system import ProfessionalUISystem
        print("✅ ProfessionalUISystem导入: PASS")
        passed += 1
    except Exception as e:
        print(f"❌ ProfessionalUISystem导入: FAIL - {e}")
        failed += 1

    # 测试StrategyPerformanceMonitor
    try:
        from gui.widgets.strategy_performance_monitor import StrategyPerformanceMonitor
        print("✅ StrategyPerformanceMonitor导入: PASS")
        passed += 1
    except Exception as e:
        print(f"❌ StrategyPerformanceMonitor导入: FAIL - {e}")
        failed += 1

    return passed, failed

def test_integration():
    """测试集成点"""
    print("\n" + "="*60)
    print("测试2: 验证集成点")
    print("="*60)

    results = []
    passed = 0
    failed = 0

    # 测试MainWindowCoordinator
    try:
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        methods = [
            '_create_professional_backtest_widget',
            '_on_professional_backtest',
            '_create_standalone_backtest_window',
            '_on_performance_center'
        ]
        for method in methods:
            if hasattr(MainWindowCoordinator, method):
                print(f"✅ MainWindowCoordinator.{method}(): PASS")
                passed += 1
            else:
                print(f"❌ MainWindowCoordinator.{method}(): FAIL - 方法不存在")
                failed += 1
    except Exception as e:
        print(f"❌ MainWindowCoordinator测试: FAIL - {e}")
        failed += 4

    # 测试MenuBar
    try:
        from gui.menu_bar import MenuBar
        attrs = [
            'professional_backtest_action',
            'backtest_action',
            'performance_menu'
        ]
        for attr in attrs:
            if hasattr(MenuBar, attr):
                print(f"✅ MenuBar.{attr}: PASS")
                passed += 1
            else:
                print(f"❌ MenuBar.{attr}: FAIL - 属性不存在")
                failed += 1
    except Exception as e:
        print(f"❌ MenuBar测试: FAIL - {e}")
        failed += 3

    return passed, failed

def test_tabs():
    """测试性能Tab组件"""
    print("\n" + "="*60)
    print("测试3: 验证性能监控Tab组件")
    print("="*60)

    passed = 0
    failed = 0

    tabs = [
        ("gui.widgets.performance.tabs.strategy_performance_tab", "ModernStrategyPerformanceTab"),
        ("gui.widgets.performance.tabs.system_monitor_tab", "ModernSystemMonitorTab"),
        ("gui.widgets.performance.tabs.algorithm_optimization_tab", "ModernAlgorithmOptimizationTab"),
        ("gui.widgets.performance.tabs.risk_control_center_tab", "ModernRiskControlCenterTab"),
        ("gui.widgets.performance.tabs.trading_execution_monitor_tab", "ModernTradingExecutionMonitorTab"),
    ]

    for module_path, class_name in tabs:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✅ {class_name}导入: PASS")
            passed += 1
        except Exception as e:
            print(f"❌ {class_name}导入: FAIL - {str(e)[:60]}")
            failed += 1

    return passed, failed

def main():
    print("\n" + "="*70)
    print("         FactorWeave-Quant 回测UI功能快速验证")
    print("="*70)
    print()

    total_passed = 0
    total_failed = 0

    # 运行测试
    p, f = test_imports()
    total_passed += p
    total_failed += f

    p, f = test_integration()
    total_passed += p
    total_failed += f

    p, f = test_tabs()
    total_passed += p
    total_failed += f

    # 输出摘要
    print("\n" + "="*70)
    print("                    测试摘要")
    print("="*70)
    print(f"通过: {total_passed} ✅")
    print(f"失败: {total_failed} ❌")
    print(f"总计: {total_passed + total_failed}")
    if total_passed + total_failed > 0:
        print(f"通过率: {total_passed/(total_passed+total_failed)*100:.1f}%")
    print("="*70)

    return total_failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
