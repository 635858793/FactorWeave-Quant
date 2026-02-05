#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试matplotlib详细导入
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

try:
    logger.info("开始测试matplotlib详细导入...")
    
    # 测试1：导入matplotlib
    logger.info("步骤1: 导入matplotlib...")
    try:
        import matplotlib
        logger.info(f"✓ matplotlib导入成功，版本: {matplotlib.__version__}")
    except Exception as e:
        logger.error(f"✗ matplotlib导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试2：设置matplotlib后端
    logger.info("步骤2: 设置matplotlib后端...")
    try:
        matplotlib.use('Agg')
        logger.info("✓ matplotlib后端设置成功")
    except Exception as e:
        logger.error(f"✗ matplotlib后端设置失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试3：导入pyplot
    logger.info("步骤3: 导入pyplot...")
    try:
        import matplotlib.pyplot as plt
        logger.info("✓ pyplot导入成功")
    except Exception as e:
        logger.error(f"✗ pyplot导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试4：导入FigureCanvas
    logger.info("步骤4: 导入FigureCanvas...")
    try:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        logger.info("✓ FigureCanvas导入成功")
    except Exception as e:
        logger.error(f"✗ FigureCanvas导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试5：导入Figure
    logger.info("步骤5: 导入Figure...")
    try:
        from matplotlib.figure import Figure
        logger.info("✓ Figure导入成功")
    except Exception as e:
        logger.error(f"✗ Figure导入失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试6：创建Figure
    logger.info("步骤6: 创建Figure...")
    try:
        fig = Figure(figsize=(10, 6), dpi=100, facecolor='white')
        logger.info("✓ Figure创建成功")
    except Exception as e:
        logger.error(f"✗ Figure创建失败: {e}")
        traceback.print_exc()
        raise
    
    # 测试7：创建FigureCanvas
    logger.info("步骤7: 创建FigureCanvas...")
    try:
        canvas = FigureCanvas(fig)
        logger.info("✓ FigureCanvas创建成功")
    except Exception as e:
        logger.error(f"✗ FigureCanvas创建失败: {e}")
        traceback.print_exc()
        raise
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")