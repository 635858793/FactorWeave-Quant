#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试性能监控窗口创建
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
    from gui.widgets.modern_performance_widget import show_modern_performance_monitor
    
    logger.info("开始测试性能监控窗口创建...")
    
    # 调用函数
    try:
        result = show_modern_performance_monitor(app)
    except Exception as e:
        logger.error(f"调用 show_modern_performance_monitor 失败: {e}")
        traceback.print_exc()
        result = None
    
    if result is not None:
        logger.info(f"性能监控窗口创建成功: {result}")
        logger.info(f"窗口类型: {type(result)}")
        logger.info(f"窗口标题: {result.windowTitle()}")
        
        # 显示窗口
        result.show()
        logger.info("窗口已显示")
        
        # 不等待用户关闭窗口，直接退出
        logger.info("测试成功完成")
        
    else:
        logger.error("性能监控窗口创建失败，返回None")
        
except Exception as e:
    logger.error(f"测试失败: {e}")
    traceback.print_exc()
finally:
    logger.info("测试结束")
