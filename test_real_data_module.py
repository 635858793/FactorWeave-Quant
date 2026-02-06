#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试data_quality_monitor_tab_real_data模块导入
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

try:
    logger.info("开始测试data_quality_monitor_tab_real_data模块导入...")
    
    # 测试1：导入模块（不调用get_real_data_provider）
    logger.info("步骤1: 导入data_quality_monitor_tab_real_data模块...")
    try:
        import gui.widgets.enhanced_ui.data_quality_monitor_tab_real_data as module
        logger.info("✓ 模块导入成功")
    except Exception as e:
        logger.error(f"✗ 模块导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试2：检查模块内容
    logger.info("步骤2: 检查模块内容...")
    try:
        logger.info(f"  - RealDataQualityProvider: {hasattr(module, 'RealDataQualityProvider')}")
        logger.info(f"  - get_real_data_provider: {hasattr(module, 'get_real_data_provider')}")
        logger.info("✓ 模块内容检查成功")
    except Exception as e:
        logger.error(f"✗ 模块内容检查失败: {e}")
        traceback.print_exc()
        raise
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")