#!/usr/bin/env python3
"""
逐步导入每个标签页 - 定位崩溃原因
"""

import sys
import os
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")

def test_import_each_tab():
    """逐步导入每个标签页"""
    logger.info("=" * 80)
    logger.info("逐步导入每个标签页")
    logger.info("=" * 80)

    try:
        # 1. 导入PyQt5
        logger.info("1. 导入PyQt5.QtWidgets...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5.QtWidgets导入成功")

        # 2. 创建QApplication
        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        # 3. 导入核心模块
        logger.info("3. 导入核心模块...")
        from core.containers import get_service_container
        from core.events import get_event_bus
        logger.info("✓ 核心模块导入成功")

        # 4. 导入性能监控模块
        logger.info("4. 导入性能监控模块...")
        from core.performance import get_performance_monitor
        logger.info("✓ 性能监控模块导入成功")

        # 5. 逐步导入每个标签页
        logger.info("5. 导入系统监控标签页...")
        from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
        logger.info("✓ 系统监控标签页导入成功")

        logger.info("6. 导入策略性能标签页...")
        from gui.widgets.performance.tabs.strategy_performance_tab import ModernStrategyPerformanceTab
        logger.info("✓ 策略性能标签页导入成功")

        logger.info("7. 导入算法优化标签页...")
        from gui.widgets.performance.tabs.algorithm_optimization_tab import ModernAlgorithmOptimizationTab
        logger.info("✓ 算法优化标签页导入成功")

        logger.info("8. 导入风险控制中心标签页...")
        from gui.widgets.performance.tabs.risk_control_center_tab import ModernRiskControlCenterTab
        logger.info("✓ 风险控制中心标签页导入成功")

        logger.info("9. 导入交易执行监控标签页...")
        from gui.widgets.performance.tabs.trading_execution_monitor_tab import ModernTradingExecutionMonitorTab
        logger.info("✓ 交易执行监控标签页导入成功")

        logger.info("10. 导入数据质量监控标签页...")
        from gui.widgets.enhanced_ui.data_quality_monitor_tab import DataQualityMonitorTab
        logger.info("✓ 数据质量监控标签页导入成功")

        logger.info("11. 导入系统健康检查标签页...")
        from gui.widgets.performance.tabs.system_health_tab import ModernSystemHealthTab
        logger.info("✓ 系统健康检查标签页导入成功")

        logger.info("12. 导入统一性能监控组件...")
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        logger.info("✓ 统一性能监控组件导入成功")

        logger.info("13. 导入性能监控入口...")
        from gui.widgets.modern_performance_widget import show_modern_performance_monitor
        logger.info("✓ 性能监控入口导入成功")

        logger.info("=" * 80)
        logger.info("✓ 所有导入测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 导入测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("开始逐步导入每个标签页...")

    result = test_import_each_tab()

    if result:
        logger.info("测试通过！")
        sys.exit(0)
    else:
        logger.error("测试失败")
        sys.exit(1)
