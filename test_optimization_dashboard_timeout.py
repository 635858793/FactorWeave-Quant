#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试优化仪表板模块导入（带超时）
"""

import sys
import signal
from pathlib import Path
from loguru import logger

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置超时处理
def timeout_handler(signum, frame):
    raise TimeoutError("导入超时")

signal.signal(signal.SIGALRM, timeout_handler)

def test_optimization_dashboard_with_timeout():
    """测试优化仪表板模块导入（带超时）"""
    logger.info("=" * 80)
    logger.info("测试优化仪表板模块导入（带超时）")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 导入优化仪表板模块（设置30秒超时）...")
        signal.alarm(30)  # 30秒超时
        
        try:
            from optimization.optimization_dashboard import create_optimization_dashboard
            signal.alarm(0)  # 取消超时
            logger.info("✓ 优化仪表板模块导入成功")
        except TimeoutError:
            logger.error("✗ 优化仪表板模块导入超时")
            return False

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        signal.alarm(0)  # 取消超时
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_optimization_dashboard_with_timeout()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)