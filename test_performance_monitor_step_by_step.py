#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试性能监控窗口创建 - 逐步初始化
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
    logger.info("开始测试性能监控窗口创建...")
    
    # 测试1：导入模块
    logger.info("步骤1: 导入 ModernUnifiedPerformanceWidget...")
    from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
    logger.info("✓ 导入成功")
    
    # 测试2：创建widget
    logger.info("步骤2: 创建 ModernUnifiedPerformanceWidget 实例...")
    widget = ModernUnifiedPerformanceWidget()
    logger.info("✓ 创建成功")
    
    # 测试3：设置标题
    logger.info("步骤3: 设置窗口标题...")
    widget.setWindowTitle("测试窗口")
    logger.info("✓ 设置标题成功")
    
    # 测试4：显示窗口
    logger.info("步骤4: 显示窗口...")
    widget.show()
    logger.info("✓ 显示窗口成功")
    
    # 测试5：检查widget属性
    logger.info("步骤5: 检查widget属性...")
    logger.info(f"  - 窗口类型: {type(widget)}")
    logger.info(f"  - 窗口标题: {widget.windowTitle()}")
    logger.info(f"  - 是否可见: {widget.isVisible()}")
    logger.info("✓ 属性检查成功")
    
    logger.info("测试成功完成")
    
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")