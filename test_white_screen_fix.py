#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证白屏问题修复效果
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from loguru import logger

def test_style_protection():
    """测试样式表保护机制"""
    print("=" * 60)
    print("测试样式表保护机制")
    print("=" * 60)
    
    try:
        from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
        from core.events import EventBus
        
        # 创建应用
        app = QApplication(sys.argv)
        
        # 创建事件总线
        event_bus = EventBus()
        
        # 创建性能监控窗口
        widget = ModernUnifiedPerformanceWidget(event_bus=event_bus)
        widget.show()
        
        # 检查样式表是否正确设置
        style_sheet = widget.styleSheet()
        if not style_sheet:
            print("❌ 样式表未设置")
            return False
        
        # 检查背景颜色是否正确
        if "background: #2c3e50" in style_sheet:
            print("✅ 背景颜色正确设置为 #2c3e50（深蓝色）")
        else:
            print("❌ 背景颜色未正确设置")
            return False
        
        # 检查 _original_stylesheet 是否保存了正确的样式表
        if hasattr(widget, '_original_stylesheet'):
            if widget._original_stylesheet and "background: #2c3e50" in widget._original_stylesheet:
                print("✅ _original_stylesheet 正确保存了样式表")
            else:
                print("❌ _original_stylesheet 未正确保存样式表")
                return False
        else:
            print("❌ _original_stylesheet 不存在")
            return False
        
        # 检查样式检查定时器是否启动
        if hasattr(widget, '_style_check_timer'):
            if widget._style_check_timer.isActive():
                print("✅ 样式检查定时器已启动")
            else:
                print("❌ 样式检查定时器未启动")
                return False
        else:
            print("❌ _style_check_timer 不存在")
            return False
        
        print("\n" + "=" * 60)
        print("样式表保护机制测试通过！")
        print("=" * 60)
        
        # 模拟样式表丢失并恢复
        print("\n模拟样式表丢失...")
        widget.setStyleSheet("")
        print("样式表已清空")
        
        # 等待样式检查定时器触发
        QTimer.singleShot(6000, lambda: check_style_restored(widget, app))
        
        # 运行应用
        app.exec_()
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_style_restored(widget, app):
    """检查样式表是否恢复"""
    style_sheet = widget.styleSheet()
    if style_sheet and "background: #2c3e50" in style_sheet:
        print("✅ 样式表已成功恢复！")
        print("✅ 背景颜色已恢复为深蓝色")
        print("\n白屏问题修复验证成功！")
    else:
        print("❌ 样式表未能恢复")
    
    # 关闭应用
    app.quit()

if __name__ == "__main__":
    success = test_style_protection()
    sys.exit(0 if success else 1)
