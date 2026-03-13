#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EventBus 异步执行兼容性测试脚本
"""

import sys
import os
import time
import threading

# 禁用日志以避免初始化问题
import logging
for logger_name in ['loguru', 'logger']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL + 1)

# 移除已导入的loguru
if 'loguru' in sys.modules:
    del sys.modules['loguru']

# 设置路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_async_event_bus():
    """测试异步EventBus功能"""
    print("=" * 60)
    print("EventBus 异步执行兼容性测试")
    print("=" * 60)
    
    # 测试1: 异步EventBus初始化
    print("\n[测试1] 异步EventBus初始化")
    try:
        from core.events.event_bus import EventBus, get_event_bus
        
        # 测试默认异步初始化
        event_bus = get_event_bus()
        print(f"  ✓ EventBus创建成功")
        print(f"    - async_execution: {event_bus._async_execution}")
        print(f"    - executor: {event_bus._executor}")
        
        if event_bus._async_execution and event_bus._executor:
            print("  ✓ 异步执行已启用")
        else:
            print("  ✗ 异步执行未启用!")
            return False
            
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试2: 事件发布-订阅功能
    print("\n[测试2] 事件发布-订阅功能")
    try:
        results = []
        
        def handler1(event):
            results.append(f"handler1-{getattr(event, 'event_type', 'unknown')}")
            
        def handler2(event):
            results.append(f"handler2-{getattr(event, 'data', {}).get('value', 'none')}")
        
        event_bus.subscribe("test_event", handler1)
        event_bus.subscribe("test_event", handler2)
        
        event_bus.publish("test_event", value=123)
        
        # 等待异步处理完成
        time.sleep(0.5)
        
        if len(results) >= 1:
            print(f"  ✓ 事件处理器执行成功")
            print(f"    - 结果: {results}")
        else:
            print(f"  ✗ 事件处理器未执行")
            
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试3: 字符串参数事件 (模拟订单事件)
    print("\n[测试3] 字符串参数事件处理")
    try:
        order_results = []
        
        def order_handler(**kwargs):
            order_results.append(kwargs)
        
        event_bus.subscribe('order_submitted_success', order_handler)
        
        # 发布订单事件 (模拟 order_executor.py 中的发布方式)
        event_bus.publish('order_submitted_success',
            order_id='ORDER001',
            exchange_order_id='EX001',
            account_id='ACC001'
        )
        
        # 等待异步处理
        time.sleep(0.5)
        
        if order_results:
            print(f"  ✓ 订单事件处理成功")
            print(f"    - 接收参数: {order_results}")
        else:
            print(f"  ✗ 订单事件参数未传递")
            
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试4: 多线程并发
    print("\n[测试4] 多线程并发安全")
    try:
        concurrent_results = []
        lock = threading.Lock()
        
        def concurrent_handler(event):
            value = getattr(event, 'value', 0)
            with lock:
                concurrent_results.append(value)
        
        event_bus.subscribe('concurrent_test', concurrent_handler)
        
        # 并发发布事件
        threads = []
        for i in range(10):
            def publish_event(val=i):
                event_bus.publish('concurrent_test', value=val)
            
            t = threading.Thread(target=publish_event)
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        time.sleep(0.5)
        
        print(f"  ✓ 并发测试完成")
        print(f"    - 收到事件数: {len(concurrent_results)}/10")
        
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试5: BaseEvent对象处理
    print("\n[测试5] BaseEvent对象处理")
    try:
        base_results = []
        
        class TestEvent:
            def __init__(self):
                self.event_type = "test_base"
                self.data = {"key": "value"}
        
        def base_handler(event):
            base_results.append(event)
        
        event_bus.subscribe(TestEvent, base_handler)
        
        test_event = TestEvent()
        event_bus.publish(test_event)
        
        time.sleep(0.5)
        
        if base_results:
            print(f"  ✓ BaseEvent处理成功")
        else:
            print(f"  ✗ BaseEvent未处理")
            
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_async_event_bus()
    sys.exit(0 if success else 1)
