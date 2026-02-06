#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试优化仪表板模块导入（详细）
"""

import sys
from pathlib import Path
from loguru import logger
import time

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_optimization_dashboard_detailed():
    """测试优化仪表板模块导入（详细）"""
    logger.info("=" * 80)
    logger.info("测试优化仪表板模块导入（详细）")
    logger.info("=" * 80)

    try:
        logger.info("1. 导入Qt模块...")
        from PyQt5.QtWidgets import QApplication
        logger.info("✓ Qt模块导入成功")

        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        logger.info("3. 逐步导入优化仪表板的依赖...")
        
        start_time = time.time()
        logger.info("3.1 导入算法优化器...")
        from optimization.algorithm_optimizer import AlgorithmOptimizer, PerformanceEvaluator
        logger.info(f"✓ 算法优化器导入成功 ({time.time() - start_time:.2f}秒)")
        
        start_time = time.time()
        logger.info("3.2 导入版本管理器...")
        from optimization.version_manager import VersionManager
        logger.info(f"✓ 版本管理器导入成功 ({time.time() - start_time:.2f}秒)")
        
        start_time = time.time()
        logger.info("3.3 导入数据库管理器...")
        from optimization.database_schema import OptimizationDatabaseManager
        logger.info(f"✓ 数据库管理器导入成功 ({time.time() - start_time:.2f}秒)")
        
        start_time = time.time()
        logger.info("3.4 导入自动调优器...")
        from optimization.auto_tuner import AlgorithmAutoTuner
        logger.info(f"✓ 自动调优器导入成功 ({time.time() - start_time:.2f}秒)")
        
        start_time = time.time()
        logger.info("3.5 导入优化仪表板...")
        from optimization.optimization_dashboard import create_optimization_dashboard
        logger.info(f"✓ 优化仪表板导入成功 ({time.time() - start_time:.2f}秒)")

        logger.info("✓ 所有测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_optimization_dashboard_detailed()
    logger.info(f"测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)