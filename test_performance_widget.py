#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控中心测试脚本
验证修复后的性能监控中心是否正常工作
"""

import sys
import time
from PyQt5.QtWidgets import QApplication
from loguru import logger

def test_performance_widget():
    """测试性能监控组件"""
    logger.info("开始测试性能监控组件...")
    
    try:
        # 导入必要的模块
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        from core.events import EventBus
        
        # 创建应用
        app = QApplication(sys.argv)
        
        # 创建事件总线
        event_bus = EventBus()
        
        # 创建性能监控组件
        widget = ModernUnifiedPerformanceWidget(event_bus=event_bus)
        
        # 显示窗口
        widget.show()
        
        logger.info("性能监控组件已创建并显示")
        
        # 测试定时器是否正常启动
        logger.info("等待定时器启动...")
        time.sleep(5)
        
        # 检查定时器状态
        if hasattr(widget, 'refresh_timer') and widget.refresh_timer.isActive():
            logger.info(f"刷新定时器运行正常，间隔: {widget.refresh_timer.interval()}ms")
        else:
            logger.error("刷新定时器未启动")
            return False
        
        if hasattr(widget, 'drag_detect_timer') and widget.drag_detect_timer.isActive():
            logger.info(f"拖动检测定时器运行正常，间隔: {widget.drag_detect_timer.interval()}ms")
        else:
            logger.error("拖动检测定时器未启动")
            return False
        
        if hasattr(widget, '_cleanup_timer') and widget._cleanup_timer.isActive():
            logger.info(f"清理定时器运行正常，间隔: {widget._cleanup_timer.interval()}ms")
        else:
            logger.error("清理定时器未启动")
            return False
        
        if hasattr(widget, '_style_check_timer') and widget._style_check_timer.isActive():
            logger.info(f"样式检查定时器运行正常，间隔: {widget._style_check_timer.interval()}ms")
        else:
            logger.error("样式检查定时器未启动")
            return False
        
        # 测试数据更新
        logger.info("测试数据更新...")
        widget.update_current_tab_data_async()
        
        # 等待一段时间，观察是否有卡死现象
        logger.info("运行30秒，观察系统状态...")
        start_time = time.time()
        while time.time() - start_time < 30:
            app.processEvents()
            time.sleep(0.1)
        
        logger.info("测试完成，系统运行正常")
        
        # 清理资源
        widget.cleanup()
        widget.close()
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_performance_widget()
    sys.exit(0 if success else 1)
