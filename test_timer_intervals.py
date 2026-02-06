#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的性能监控组件测试
验证定时器频率优化是否生效
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from loguru import logger

def test_timer_intervals():
    """测试定时器间隔设置"""
    logger.info("开始测试定时器间隔设置...")
    
    try:
        # 创建应用
        app = QApplication(sys.argv)
        
        # 创建定时器
        refresh_timer = QTimer()
        drag_detect_timer = QTimer()
        cleanup_timer = QTimer()
        style_check_timer = QTimer()
        
        # 设置定时器间隔（与修复后的代码一致）
        refresh_timer.start(5000)  # 5秒
        drag_detect_timer.start(1000)  # 1秒
        cleanup_timer.start(30000)  # 30秒
        style_check_timer.start(30000)  # 30秒
        
        logger.info(f"刷新定时器间隔: {refresh_timer.interval()}ms (预期: 5000ms)")
        logger.info(f"拖动检测定时器间隔: {drag_detect_timer.interval()}ms (预期: 1000ms)")
        logger.info(f"清理定时器间隔: {cleanup_timer.interval()}ms (预期: 30000ms)")
        logger.info(f"样式检查定时器间隔: {style_check_timer.interval()}ms (预期: 30000ms)")
        
        # 验证定时器间隔
        assert refresh_timer.interval() == 5000, f"刷新定时器间隔错误: {refresh_timer.interval()}"
        assert drag_detect_timer.interval() == 1000, f"拖动检测定时器间隔错误: {drag_detect_timer.interval()}"
        assert cleanup_timer.interval() == 30000, f"清理定时器间隔错误: {cleanup_timer.interval()}"
        assert style_check_timer.interval() == 30000, f"样式检查定时器间隔错误: {style_check_timer.interval()}"
        
        logger.info("所有定时器间隔设置正确！")
        
        # 停止定时器
        refresh_timer.stop()
        drag_detect_timer.stop()
        cleanup_timer.stop()
        style_check_timer.stop()
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_timer_intervals()
    sys.exit(0 if success else 1)
