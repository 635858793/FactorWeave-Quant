#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据质量监控标签页导入
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from PyQt5.QtWidgets import QApplication
from loguru import logger

# 创建QApplication
app = QApplication(sys.argv)

try:
    logger.info("开始测试数据质量监控标签页导入...")
    
    # 测试1：导入模块
    logger.info("步骤1: 导入 DataQualityMonitorTab...")
    try:
        from gui.widgets.enhanced_ui.data_quality_monitor_tab import DataQualityMonitorTab
        logger.info("✓ 导入成功")
    except Exception as e:
        logger.error(f"✗ 导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试2：创建实例
    logger.info("步骤2: 创建 DataQualityMonitorTab 实例...")
    try:
        tab = DataQualityMonitorTab()
        logger.info("✓ 创建实例成功")
    except Exception as e:
        logger.error(f"✗ 创建实例失败: {e}")
        traceback.print_exc()
        raise
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")