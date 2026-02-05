#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试真实数据提供者导入
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

try:
    logger.info("开始测试真实数据提供者导入...")
    
    # 测试1：导入模块
    logger.info("步骤1: 导入 RealDataQualityProvider...")
    try:
        from gui.widgets.enhanced_ui.data_quality_monitor_tab_real_data import RealDataQualityProvider, get_real_data_provider
        logger.info("✓ 导入成功")
    except Exception as e:
        logger.error(f"✗ 导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试2：创建实例
    logger.info("步骤2: 创建 RealDataQualityProvider 实例...")
    try:
        provider = RealDataQualityProvider()
        logger.info("✓ 创建实例成功")
    except Exception as e:
        logger.error(f"✗ 创建实例失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试3：调用 get_real_data_provider
    logger.info("步骤3: 调用 get_real_data_provider()...")
    try:
        provider = get_real_data_provider()
        logger.info("✓ 获取提供者成功")
    except Exception as e:
        logger.error(f"✗ 获取提供者失败: {e}")
        traceback.print_exc()
        raise
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")