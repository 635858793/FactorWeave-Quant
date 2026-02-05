#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试性能监控窗口创建 - 最简化版
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 首先创建QApplication（必须在任何Qt相关导入之前）
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

# 然后导入logger
from loguru import logger

try:
    from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
    
    logger.info("开始测试性能监控窗口创建...")
    
    # 调用函数
    try:
        logger.info("步骤1: 开始创建 ModernUnifiedPerformanceWidget...")
        widget = ModernUnifiedPerformanceWidget()
        logger.info(f"步骤2: 性能监控窗口创建成功: {widget}")
        logger.info(f"步骤3: 窗口类型: {type(widget)}")
        logger.info(f"步骤4: 窗口标题: {widget.windowTitle()}")
        
        # 不显示窗口，只创建对象
        logger.info("步骤5: 测试成功完成")
        
    except Exception as e:
        logger.error(f"创建 ModernUnifiedPerformanceWidget 失败: {e}")
        traceback.print_exc()
        sys.exit(1)
        
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
    sys.exit(1)
finally:
    logger.info("测试结束")