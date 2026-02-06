#!/usr/bin/env python3
"""
逐步测试性能监控中心崩溃问题
逐步导入模块，定位崩溃原因
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
logger.add("logs/test_performance_crash_step.log", rotation="10 MB", retention="7 days", level="DEBUG")

def test_imports_step_by_step():
    """逐步导入模块，定位崩溃原因"""
    logger.info("=" * 80)
    logger.info("逐步导入模块测试")
    logger.info("=" * 80)

    try:
        # 1. 导入PyQt5
        logger.info("1. 导入PyQt5...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ PyQt5导入成功")

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

        # 5. 导入性能监控组件
        logger.info("5. 导入性能监控组件...")
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        logger.info("✓ 性能监控组件导入成功")

        # 6. 导入性能监控入口
        logger.info("6. 导入性能监控入口...")
        from gui.widgets.modern_performance_widget import show_modern_performance_monitor
        logger.info("✓ 性能监控入口导入成功")

        # 7. 尝试创建性能监控窗口
        logger.info("7. 创建性能监控窗口...")
        try:
            performance_widget = show_modern_performance_monitor()
            logger.info("✓ 性能监控窗口创建成功")
        except Exception as e:
            logger.error(f"✗ 性能监控窗口创建失败: {e}")
            logger.error(traceback.format_exc())
            return False

        # 8. 检查窗口是否正常
        if performance_widget is None:
            logger.error("✗ 性能监控窗口为None")
            return False

        logger.info(f"✓ 性能监控窗口类型: {type(performance_widget).__name__}")

        # 9. 测试窗口显示
        logger.info("8. 测试窗口显示...")
        try:
            performance_widget.show()
            logger.info("✓ 窗口显示成功")

            # 强制刷新UI
            app.processEvents()
            logger.info("✓ UI刷新成功")

            # 等待一段时间
            logger.info("9. 等待2秒...")
            import time
            time.sleep(2)

            logger.info("✓ 2秒等待完成")

        except Exception as e:
            logger.error(f"✗ 窗口显示失败: {e}")
            logger.error(traceback.format_exc())
            return False

        # 10. 测试窗口关闭
        logger.info("10. 测试窗口关闭...")
        try:
            performance_widget.close()
            logger.info("✓ 窗口关闭成功")

            # 强制刷新UI
            app.processEvents()
            logger.info("✓ UI刷新成功")

        except Exception as e:
            logger.error(f"✗ 窗口关闭失败: {e}")
            logger.error(traceback.format_exc())
            return False

        logger.info("=" * 80)
        logger.info("✓ 所有测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("开始逐步测试性能监控中心崩溃问题...")

    result = test_imports_step_by_step()

    if result:
        logger.info("测试通过！")
        sys.exit(0)
    else:
        logger.error("测试失败")
        sys.exit(1)
