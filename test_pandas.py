#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试pandas导入
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

try:
    logger.info("开始测试pandas导入...")
    
    # 测试1：导入pandas
    logger.info("步骤1: 导入pandas...")
    try:
        import pandas as pd
        logger.info(f"✓ pandas导入成功，版本: {pd.__version__}")
    except Exception as e:
        logger.error(f"✗ pandas导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试2：使用pandas
    logger.info("步骤2: 使用pandas...")
    try:
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        logger.info(f"✓ pandas使用成功，DataFrame: {df}")
    except Exception as e:
        logger.error(f"✗ pandas使用失败: {e}")
        traceback.print_exc()
        raise
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")