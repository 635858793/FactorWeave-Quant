#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据预处理各环节耗时分析
"""
import time
import numpy as np
import pandas as pd
from backtest.backtest_validator import ProfessionalBacktestValidator, BacktestValidationLevel

def create_test_data(size):
    """创建测试数据（仅包含close和signal）"""
    dates = pd.date_range('2020-01-01', periods=size, freq='5min')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(size) * 0.5)
    signals = np.random.choice([0, 1, -1], size=size, p=[0.7, 0.2, 0.1])
    signals[0] = 0
    signals[100] = 1
    
    data = pd.DataFrame({
        'date': dates,
        'close': prices,
        'signal': signals
    })
    data.set_index('date', inplace=True)
    return data

def analyze_preprocessing_steps():
    """分析数据预处理各环节耗时"""
    sizes = [10000, 50000, 100000, 250000]
    
    print("\n" + "="*80)
    print("数据预处理各环节耗时分析")
    print("="*80)
    
    validator = ProfessionalBacktestValidator(BacktestValidationLevel.PROFESSIONAL)
    
    for size in sizes:
        print(f"\n{'='*60}")
        print(f"数据量: {size:,} 条")
        print("="*60)
        
        data = create_test_data(size)
        
        # 步骤1: DataFrame复制
        start = time.time()
        processed_data = data.copy()
        step1 = time.time() - start
        print(f"1. DataFrame复制:      {step1*1000:>10.2f}ms")
        
        # 步骤2: 数据验证器
        start = time.time()
        validation_result = validator.validate_backtest_data(processed_data, 'signal', 'close')
        step2 = time.time() - start
        print(f"2. 数据验证(完整):    {step2*1000:>10.2f}ms")
        
        # 步骤3: 数据预处理(kdata_preprocess)
        start = time.time()
        from utils.data_preprocessing import kdata_preprocess
        processed_data = kdata_preprocess(processed_data, context="测试")
        step3 = time.time() - start
        print(f"3. kdata_preprocess:  {step3*1000:>10.2f}ms")
        
        # 步骤4: 日期索引确保
        start = time.time()
        if not isinstance(processed_data.index, pd.DatetimeIndex):
            processed_data.index = pd.to_datetime(processed_data.index)
        step4 = time.time() - start
        print(f"4. 日期索引确保:      {step4*1000:>10.2f}ms")
        
        total = step1 + step2 + step3 + step4
        print(f"\n总耗时:               {total*1000:>10.2f}ms")
        
        # 占比
        print(f"\n耗时占比:")
        print(f"  - DataFrame复制:    {step1/total*100:>5.1f}%")
        print(f"  - 数据验证:          {step2/total*100:>5.1f}%")
        print(f"  - kdata_preprocess: {step3/total*100:>5.1f}%")
        print(f"  - 日期索引:         {step4/total*100:>5.1f}%")

def analyze_validation_breakdown():
    """分析数据验证内部各步骤"""
    print("\n" + "="*80)
    print("数据验证内部各步骤分析")
    print("="*80)
    
    sizes = [10000, 50000, 100000, 250000]
    validator = ProfessionalBacktestValidator(BacktestValidationLevel.PROFESSIONAL)
    
    for size in sizes:
        print(f"\n数据量: {size:,}")
        
        data = create_test_data(size)
        
        # 仅测试数据结构验证（这是触发缺少字段警告的部分）
        start = time.time()
        errors, warnings = [], []
        from backtest.backtest_validator import BacktestValidationResult
        result = validator._validate_data_structure(data, errors, warnings)
        step1 = time.time() - start
        print(f"  数据结构验证: {step1*1000:.2f}ms (errors={errors})")
        
        # 测试数据质量验证
        start = time.time()
        result2 = validator._validate_data_quality(data, errors, warnings)
        step2 = time.time() - start
        print(f"  数据质量验证: {step2*1000:.2f}ms")

def analyze_missing_fields_handling():
    """分析缺失字段处理"""
    print("\n" + "="*80)
    print("缺失字段处理分析")
    print("="*80)
    
    from utils.data_preprocessing import kdata_preprocess
    
    sizes = [10000, 50000, 100000, 250000]
    
    for size in sizes:
        print(f"\n数据量: {size:,}")
        
        # 仅有close和signal（触发字段补全）
        data = create_test_data(size)
        
        start = time.time()
        result = kdata_preprocess(data, context="测试")
        step = time.time() - start
        print(f"  补全OHLC字段: {step*1000:.2f}ms")
        print(f"  补全后列: {list(result.columns)}")
        
        # 已有完整字段（不触发补全）
        data_full = data.copy()
        data_full['open'] = data_full['close']
        data_full['high'] = data_full['close']
        data_full['low'] = data_full['close']
        data_full['volume'] = 1000000
        
        start = time.time()
        result2 = kdata_preprocess(data_full, context="测试")
        step2 = time.time() - start
        print(f"  完整字段处理: {step2*1000:.2f}ms")

if __name__ == '__main__':
    analyze_preprocessing_steps()
    analyze_validation_breakdown()
    analyze_missing_fields_handling()
