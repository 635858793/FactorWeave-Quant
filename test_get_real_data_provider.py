#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试get_real_data_provider导入
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

try:
    logger.info("开始测试get_real_data_provider导入...")
    
    # 测试1：导入get_real_data_provider
    logger.info("步骤1: 导入get_real_data_provider...")
    try:
        from gui.widgets.enhanced_ui.data_quality_monitor_tab_real_data import get_real_data_provider
        logger.info("✓ get_real_data_provider导入成功")
    except Exception as e:
        logger.error(f"✗ get_real_data_provider导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试2：调用get_real_data_provider
    logger.info("步骤2: 调用get_real_data_provider()...")
    try:
        provider = get_real_data_provider()
        logger.info("✓ get_real_data_provider调用成功")
    except Exception as e:
        logger.error(f"✗ get_real_data_provider调用失败: {e}")
        traceback.print_exc()
        raise
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")