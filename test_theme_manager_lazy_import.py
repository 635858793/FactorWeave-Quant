#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试主题管理器延迟导入
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_theme_manager_lazy_import():
    """测试主题管理器延迟导入"""
    logger.info("=" * 80)
    logger.info("测试主题管理器延迟导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 测试直接导入主题管理器（应该失败）...")
        try:
            from utils.theme import get_theme_manager
            logger.warning("✗ 直接导入成功，这不应该发生")
            return False
        except Exception as e:
            logger.info(f"✓ 直接导入失败（预期行为）: {type(e).__name__}")

        logger.info("2. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("3. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("4. 测试导入实现了延迟导入的模块...")
        from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
        logger.info("✓ system_monitor_tab导入成功")

        logger.info("5. 测试导入其他实现了延迟导入的模块...")
        from gui.widgets.performance.tabs.algorithm_optimization_tab import ModernAlgorithmOptimizationTab
        from gui.widgets.performance.tabs.trading_execution_monitor_tab import ModernTradingExecutionMonitorTab
        from gui.widgets.performance.tabs.strategy_performance_tab import ModernStrategyPerformanceTab
        logger.info("✓ 所有性能标签页导入成功")

        logger.info("6. 测试导入主窗口协调器...")
        from core.coordinators import MainWindowCoordinator
        logger.info("✓ 主窗口协调器导入成功")

        logger.info("7. 测试导入GUI组件...")
        from gui.menu_bar import MainMenuBar
        from gui.tool_bar import MainToolBar
        from gui.widgets.chart_widget import ChartWidget
        from gui.widgets.trading_widget import TradingWidget
        logger.info("✓ GUI组件导入成功")

        logger.info("8. 测试导入对话框...")
        from gui.dialogs.enhanced_strategy_manager_dialog_v2 import EnhancedStrategyManagerDialogV2
        logger.info("✓ 对话框导入成功")

        logger.info("9. 测试导入服务...")
        from core.services.unified_chart_service import UnifiedChartService
        logger.info("✓ 服务导入成功")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_theme_manager_lazy_import()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)