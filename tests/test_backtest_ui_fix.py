#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试回测 UI 更新修复
验证 QTimer.singleShot 是否正确调用 _on_backtest_completed
"""

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ['QT_QPA_PLATFORM'] = 'offscreen'  # 无头模式运行

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QEventLoop
import asyncio

def test_qtimer_in_main_thread():
    """测试 QTimer.singleShot 在主线程中的行为"""
    print("=" * 70)
    print("测试 1: QTimer.singleShot 在主线程中的行为")
    print("=" * 70)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    callback_executed = False
    
    def test_callback():
        nonlocal callback_executed
        callback_executed = True
        print(f"[回调执行] QTimer.singleShot 回调已执行: {time.time()}")
    
    print(f"[主线程] 计划回调: {time.time()}")
    QTimer.singleShot(0, test_callback)
    print(f"[主线程] 已计划，开始处理事件...")
    
    # 处理事件
    app.processEvents()
    time.sleep(0.1)
    app.processEvents()
    
    if callback_executed:
        print("✅ 测试 1 通过：QTimer.singleShot 回调正常执行")
    else:
        print("❌ 测试 1 失败：QTimer.singleShot 回调未执行")
    
    return callback_executed


def test_qtimer_in_worker_thread():
    """测试在 worker 线程中使用 QTimer.singleShot"""
    print("\n" + "=" * 70)
    print("测试 2: 在 worker 线程中使用 QTimer.singleShot")
    print("=" * 70)
    
    import threading
    
    callback_executed_in_main = False
    callback_scheduled = False
    
    def main_thread_callback():
        nonlocal callback_executed_in_main
        print(f"[主线程回调] 执行回调：{time.time()}")
        callback_executed_in_main = True
    
    def worker_thread_func():
        nonlocal callback_scheduled
        print(f"[工作线程] 开始调度回调：{time.time()}")
        QTimer.singleShot(0, main_thread_callback)
        callback_scheduled = True
        print(f"[工作线程] 已调度，等待主线程处理...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 启动工作线程
    worker = threading.Thread(target=worker_thread_func, daemon=True)
    worker.start()
    worker.join(timeout=2.0)
    
    if callback_scheduled:
        print(f"[主线程] 检测到回调已调度，处理事件...")
        app.processEvents()
        time.sleep(0.2)
        app.processEvents()
        
        if callback_executed_in_main:
            print("✅ 测试 2 通过：工作线程调度的回调在主线程执行")
        else:
            print("❌ 测试 2 失败：回调未在主线程执行")
            return False
    else:
        print("❌ 测试 2 失败：回调未被调度")
        return False
    
    return True


def test_backtest_widget_structure():
    """测试 BacktestWidget 的结构"""
    print("\n" + "=" * 70)
    print("测试 3: 检查 BacktestWidget 结构")
    print("=" * 70)
    
    try:
        from gui.widgets.backtest_widget import ProfessionalBacktestWidget
        
        # 检查方法是否存在
        required_methods = [
            '_on_backtest_completed',
            '_validate_backtest_results',
            'start_monitoring',
            'stop_backtest'
        ]
        
        missing_methods = []
        for method in required_methods:
            if not hasattr(ProfessionalBacktestWidget, method):
                missing_methods.append(method)
        
        if missing_methods:
            print(f"❌ 测试 3 失败：缺少方法：{missing_methods}")
            return False
        else:
            print(f"✅ 测试 3 通过：所有必需方法都存在")
            
        # 检查 _on_backtest_completed 方法的实现
        import inspect
        source = inspect.getsource(ProfessionalBacktestWidget._on_backtest_completed)
        
        # 检查是否包含 metrics_panel.update_metrics 调用
        if 'metrics_panel.update_metrics' in source:
            print("✅ _on_backtest_completed 包含 metrics_panel.update_metrics 调用")
        else:
            print("❌ _on_backtest_completed 缺少 metrics_panel.update_metrics 调用")
            return False
        
        # 检查是否包含 chart_widget.update_charts 调用
        if 'chart_widget.update_charts' in source:
            print("✅ _on_backtest_completed 包含 chart_widget.update_charts 调用")
        else:
            print("❌ _on_backtest_completed 缺少 chart_widget.update_charts 调用")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试 3 失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_monitoring_loop_flow():
    """测试 monitoring_loop 的执行流程"""
    print("\n" + "=" * 70)
    print("测试 4: 分析 monitoring_loop 执行流程")
    print("=" * 70)
    
    try:
        from gui.widgets.backtest_widget import ProfessionalBacktestWidget
        import inspect
        
        source = inspect.getsource(ProfessionalBacktestWidget.start_monitoring)
        
        # 检查关键步骤
        checks = {
            'QTimer.singleShot.*_on_backtest_completed': '调用 _on_backtest_completed',
            '_validate_backtest_results': '验证回测结果',
            'control_panel.update_progress.*100': '更新进度到 100%',
        }
        
        all_passed = True
        for pattern, description in checks.items():
            import re
            if re.search(pattern, source):
                print(f"✅ 包含：{description}")
            else:
                print(f"❌ 缺少：{description}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ 测试 4 失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("回测 UI 更新修复验证测试")
    print("=" * 70)
    
    results = {
        'QTimer 主线程测试': test_qtimer_in_main_thread(),
        'QTimer 工作线程测试': test_qtimer_in_worker_thread(),
        'BacktestWidget 结构测试': test_backtest_widget_structure(),
        'monitoring_loop 流程测试': test_monitoring_loop_flow(),
    }
    
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} | {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ 所有测试通过！修复应该有效。")
    else:
        print("\n❌ 部分测试失败，需要进一步检查。")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
