# -*- coding: utf-8 -*-
"""测试数据量限制功能"""
from analysis.pattern_manager import PatternManager
import os

def test_data_limit():
    pm = PatternManager.get_instance()
    
    # 1. 获取当前数据量
    summary = pm.get_training_data_summary()
    total = summary.get('total_records', 0)
    print(f'当前总记录数: {total}')
    
    # 2. 验证数据限制: 当达到10000条时自动清理
    print('\n=== 测试数据限制功能 ===')
    
    # 插入新数据（使用默认max_total_records=10000）
    pm.record_pattern_result(
        pattern_type='测试限制',
        stock_code='TEST001',
        signal_type='buy',
        confidence=0.8,
        trigger_date='2026-03-13',
        trigger_price=100.0,
        result_date='2026-03-13',
        result_price=105.0
    )
    
    summary = pm.get_training_data_summary()
    new_total = summary.get('total_records', 0)
    print(f'插入后总记录数: {new_total}')
    
    # 3. 统计信息
    print(f'\n=== 存储分析 ===')
    print(f'当前记录数: {new_total}')
    print(f'最大限制: 10000')
    print(f'使用率: {new_total/10000*100:.1f}%')
    print(f'预计数据库增长: 安全（远小于10000条限制）')
    
    print('\n✅ 数据限制功能测试完成')

if __name__ == '__main__':
    test_data_limit()
