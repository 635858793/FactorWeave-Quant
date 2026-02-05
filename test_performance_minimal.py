#!/usr/bin/env python3
"""
最小化测试性能监控中心崩溃问题
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

def test_minimal():
    """最小化测试"""
    logger.info("=" * 80)
    logger.info("最小化测试")
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

        # 3. 导入性能监控组件
        logger.info("3. 导入性能监控组件...")
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        logger.info("✓ 性能监控组件导入成功")

        # 4. 创建性能监控窗口
        logger.info("4. 创建性能监控窗口...")
        widget = ModernUnifiedPerformanceWidget()
        logger.info("✓ 性能监控窗口创建成功")

        # 5. 测试窗口显示
        logger.info("5. 测试窗口显示...")
        widget.show()
        logger.info("✓ 窗口显示成功")

        # 6. 强制刷新UI
        logger.info("6. 强制刷新UI...")
        app.processEvents()
        logger.info("✓ UI刷新成功")

        # 7. 等待一段时间
        logger.info("7. 等待2秒...")
        import time
        time.sleep(2)
        logger.info("✓ 2秒等待完成")

        # 8. 测试窗口关闭
        logger.info("8. 测试窗口关闭...")
        widget.close()
        logger.info("✓ 窗口关闭成功")

        # 9. 强制刷新UI
        logger.info("9. 强制刷新UI...")
        app.processEvents()
        logger.info("✓ UI刷新成功")

        logger.info("=" * 80)
        logger.info("✓ 最小化测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 最小化测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("开始最小化测试...")

    result = test_minimal()

    if result:
        logger.info("测试通过！")
        sys.exit(0)
    else:
        logger.error("测试失败")
        sys.exit(1)
