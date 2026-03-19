#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试信号机制修复
验证从工作线程发射信号是否能正确触发主线程的槽函数
"""

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal, QThread, Qt
import threading


class TestWidget(QThread):
    """测试用 Widget"""
    
    # 定义信号
    request_update = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.callback_executed = False
        self.callback_data = None
        
        # 连接信号到槽
        self.request_update.connect(self.on_update_requested, Qt.QueuedConnection)
    
    def on_update_requested(self, data):
        """槽函数"""
        self.callback_executed = True
        self.callback_data = data
        print(f"[槽函数] 收到数据：{data}")
    
    def run(self):
        """工作线程中发射信号"""
        print(f"[工作线程] 开始发射信号...")
        test_data = {'test': 'data', 'value': 123}
        self.request_update.emit(test_data)
        print(f"[工作线程] 信号已发射")
        time.sleep(0.5)


def test_signal_from_worker():
    """测试从工作线程发射信号"""
    print("=" * 70)
    print("测试：从工作线程发射信号触发主线程槽函数")
    print("=" * 70)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    widget = TestWidget()
    
    print(f"[主线程] 启动工作线程...")
    widget.start()
    
    # 等待工作线程完成
    widget.wait(5000)
    
    # 处理事件，确保信号被处理
    print(f"[主线程] 处理事件队列...")
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    
    if widget.callback_executed:
        print(f"✅ 测试通过：槽函数已执行，收到数据：{widget.callback_data}")
        return True
    else:
        print("❌ 测试失败：槽函数未执行")
        return False


def test_backtest_widget_signal():
    """测试 BacktestWidget 的信号机制"""
    print("\n" + "=" * 70)
    print("测试：BacktestWidget 的信号机制")
    print("=" * 70)
    
    try:
        from gui.widgets.backtest_widget import ProfessionalBacktestWidget
        
        # 检查信号是否存在
        if hasattr(ProfessionalBacktestWidget, 'request_ui_update'):
            print("✅ request_ui_update 信号存在")
        else:
            print("❌ request_ui_update 信号不存在")
            return False
        
        # 检查信号连接
        import inspect
        source = inspect.getsource(ProfessionalBacktestWidget.__init__)
        
        if 'request_ui_update.connect' in source:
            print("✅ request_ui_update 信号已连接")
        else:
            print("❌ request_ui_update 信号未连接")
            return False
        
        if 'Qt.QueuedConnection' in source:
            print("✅ 使用 Qt.QueuedConnection（正确的跨线程连接方式）")
        else:
            print("❌ 未使用 Qt.QueuedConnection")
            return False
        
        # 检查 monitoring_loop 中是否使用信号
        source = inspect.getsource(ProfessionalBacktestWidget.start_monitoring)
        
        if 'request_ui_update.emit' in source:
            print("✅ monitoring_loop 中使用 request_ui_update.emit()")
        else:
            print("❌ monitoring_loop 中未使用 request_ui_update.emit()")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("信号机制修复验证测试")
    print("=" * 70)
    
    results = {
        '工作线程信号测试': test_signal_from_worker(),
        'BacktestWidget 信号测试': test_backtest_widget_signal(),
    }
    
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} | {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ 所有测试通过！信号机制修复成功。")
        print("\n修复说明：")
        print("1. 添加了 request_ui_update 信号用于跨线程通信")
        print("2. 使用 Qt.QueuedConnection 确保槽函数在主线程执行")
        print("3. monitoring_loop 中使用 emit() 替代 QTimer.singleShot()")
    else:
        print("\n❌ 部分测试失败，需要进一步检查。")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
