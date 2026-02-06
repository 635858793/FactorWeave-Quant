#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐步测试主窗口协调器导入
"""

import sys
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_step_by_step_import():
    """逐步测试主窗口协调器导入"""
    logger.info("=" * 80)
    logger.info("逐步测试主窗口协调器导入")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 逐步导入主窗口协调器的依赖...")
        
        logger.info("3.1 导入性能监控...")
        from core.performance.unified_monitor import PerformanceAutoTuner
        logger.info("✓ 性能监控导入成功")

        logger.info("3.2 导入插件管理器...")
        from core.plugin_manager import PluginManager
        logger.info("✓ 插件管理器导入成功")

        logger.info("3.3 导入优化仪表板...")
        from optimization.optimization_dashboard import create_optimization_dashboard
        logger.info("✓ 优化仪表板导入成功")

        logger.info("3.4 导入性能组件...")
        from gui.widgets.modern_performance_widget import ModernUnifiedPerformanceWidget
        logger.info("✓ 性能组件导入成功")

        logger.info("3.5 导入菜单栏...")
        from gui.menu_bar import MainMenuBar
        logger.info("✓ 菜单栏导入成功")

        logger.info("3.6 导入基础协调器...")
        from core.coordinators.base_coordinator import BaseCoordinator
        logger.info("✓ 基础协调器导入成功")

        logger.info("3.7 导入主窗口协调器...")
        from core.coordinators.main_window_coordinator import MainWindowCoordinator
        logger.info("✓ 主窗口协调器导入成功")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_step_by_step_import()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)