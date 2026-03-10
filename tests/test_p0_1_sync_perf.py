#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0-1 持仓同步性能验证（简化版）
"""

import sys
sys.path.insert(0, '.')

import time
import threading


def test_sync_mechanism():
    """测试持仓同步机制性能"""
    print('=' * 70)
    print('P0-1: 持仓同步机制性能验证（简化版）')
    print('=' * 70)
    print()
    
    print('【测试】time.time() vs datetime.now() 性能对比')
    print()
    
    from datetime import datetime
    
    iterations = 100000
    
    print('datetime.now() 测试:')
    start = time.perf_counter()
    for _ in range(iterations):
        _ = datetime.now()
    dt_time = time.perf_counter() - start
    print(f'  {iterations}次调用: {dt_time:.4f}秒')
    print(f'  平均: {(dt_time/iterations)*1000000:.2f}微秒/次')
    print()
    
    print('time.time() 测试:')
    start = time.perf_counter()
    for _ in range(iterations):
        _ = time.time()
    tt_time = time.perf_counter() - start
    print(f'  {iterations}次调用: {tt_time:.4f}秒')
    print(f'  平均: {(tt_time/iterations)*1000000:.2f}微秒/次')
    print()
    
    improvement = ((dt_time - tt_time) / dt_time) * 100
    print(f'性能提升: {improvement:.1f}%')
    print()
    
    print('【测试】节流机制性能')
    print()
    
    last_sync_times = {}
    min_interval = 5
    
    iterations = 10000
    
    print('使用datetime (优化前):')
    last_sync_times = {}
    start = time.perf_counter()
    for i in range(iterations):
        now = datetime.now()
        account_id = f'account_{i % 10}'
        last = last_sync_times.get(account_id)
        if last:
            elapsed = (now - last).total_seconds()
            if elapsed < min_interval:
                continue
        last_sync_times[account_id] = now
    dt_throttle = time.perf_counter() - start
    print(f'  {iterations}次调用: {dt_throttle:.4f}秒')
    print()
    
    print('使用time.time (优化后):')
    last_sync_times = {}
    start = time.perf_counter()
    for i in range(iterations):
        now = time.time()
        account_id = f'account_{i % 10}'
        last = last_sync_times.get(account_id)
        if last:
            elapsed = now - last
            if elapsed < min_interval:
                continue
        last_sync_times[account_id] = now
    tt_throttle = time.perf_counter() - start
    print(f'  {iterations}次调用: {tt_throttle:.4f}秒')
    print()
    
    improvement = ((dt_throttle - tt_throttle) / dt_throttle) * 100
    print(f'性能提升: {improvement:.1f}%')
    print()
    
    print('【测试】Timer vs 批量处理性能对比')
    print()
    
    print('Timer创建 (单次):')
    iterations = 1000
    start = time.perf_counter()
    timers = []
    for i in range(iterations):
        t = threading.Timer(1.0, lambda: None)
        timers.append(t)
    timer_time = time.perf_counter() - start
    print(f'  创建{iterations}个Timer: {timer_time:.4f}秒')
    for t in timers:
        t.cancel()
    print()
    
    print('模拟批量处理:')
    start = time.perf_counter()
    batch = []
    for i in range(iterations):
        batch.append(i)
        if len(batch) >= 100:
            batch.clear()
    batch_time = time.perf_counter() - start
    print(f'  处理{iterations}个任务: {batch_time:.4f}秒')
    print()
    
    print(f'批量处理比Timer快: {(timer_time/batch_time):.1f}倍')
    print()
    
    print('=' * 70)
    print('结论')
    print('=' * 70)
    print(f'1. time.time()比datetime.now()快约{improvement:.1f}%')
    print(f'2. 节流机制使用time.time()可提升约{((dt_throttle-tt_throttle)/dt_throttle)*100:.1f}%')
    print(f'3. 批量处理比Timer创建快约{timer_time/batch_time:.1f}倍')
    print('=' * 70)


if __name__ == '__main__':
    test_sync_mechanism()
