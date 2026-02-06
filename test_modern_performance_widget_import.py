#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试ModernUnifiedPerformanceWidget导入
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_modern_performance_widget_import():
    """测试ModernUnifiedPerformanceWidget导入"""
    logger.info("=" * 80)
    logger.info("测试ModernUnifiedPerformanceWidget导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入async_workers...")
        from gui.widgets.performance.workers.async_workers import AsyncDataWorker, AsyncStrategyWorker, AsyncDataSignals
        logger.info("✓ async_workers导入成功")

        logger.info("4. 导入system_monitor_tab...")
        from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
        logger.info("✓ system_monitor_tab导入成功")

        logger.info("5. 导入strategy_performance_tab...")
        from gui.widgets.performance.tabs.strategy_performance_tab import ModernStrategyPerformanceTab
        logger.info("✓ strategy_performance_tab导入成功")

        logger.info("6. 导入algorithm_optimization_tab...")
        from gui.widgets.performance.tabs.algorithm_optimization_tab import ModernAlgorithmOptimizationTab
        logger.info("✓ algorithm_optimization_tab导入成功")

        logger.info("7. 导入risk_control_center_tab...")
        from gui.widgets.performance.tabs.risk_control_center_tab import ModernRiskControlCenterTab
        logger.info("✓ risk_control_center_tab导入成功")

        logger.info("8. 导入trading_execution_monitor_tab...")
        from gui.widgets.performance.tabs.trading_execution_monitor_tab import ModernTradingExecutionMonitorTab
        logger.info("✓ trading_execution_monitor_tab导入成功")

        logger.info("9. 导入data_quality_monitor_tab...")
        from gui.widgets.enhanced_ui.data_quality_monitor_tab import DataQualityMonitorTab
        logger.info("✓ data_quality_monitor_tab导入成功")

        logger.info("10. 导入system_health_tab...")
        from gui.widgets.performance.tabs.system_health_tab import ModernSystemHealthTab
        logger.info("✓ system_health_tab导入成功")

        logger.info("11. 导入unified_performance_widget模块...")
        import gui.widgets.performance.unified_performance_widget
        logger.info("✓ unified_performance_widget模块导入成功")

        logger.info("12. 导入ModernUnifiedPerformanceWidget类...")
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        logger.info("✓ ModernUnifiedPerformanceWidget类导入成功")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_modern_performance_widget_import()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)