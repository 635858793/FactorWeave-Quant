"""
对比两种版本生成的具体信号
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, 'd:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui')

from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy

# 创建测试数据
def create_test_data(n_points=243):
    dates = pd.date_range(start='2023-01-01', periods=n_points, freq='D')
    np.random.seed(42)
    
    close_prices = 100 + np.cumsum(np.random.randn(n_points) * 0.5)
    high_prices = close_prices + np.abs(np.random.randn(n_points) * 0.3)
    low_prices = close_prices - np.abs(np.random.randn(n_points) * 0.3)
    open_prices = close_prices + np.random.randn(n_points) * 0.1
    volume = np.random.randint(1000, 10000, n_points)
    
    data = pd.DataFrame({
        'timestamp': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volume
    }, index=dates)
    
    return data

# 创建策略实例
strategy = AdaptivePandasStrategy()

# 生成测试数据
data = create_test_data(243)

# 计算技术指标
indicators = strategy._calculate_technical_indicators(data)

# 分别调用两种版本
loop_signals = strategy._loop_generate_signals(data, indicators)
vec_signals = strategy._vectorized_generate_signals(data, indicators)

print(f"循环版本生成 {len(loop_signals)} 个信号")
print(f"向量化版本生成 {len(vec_signals)} 个信号")

print("\n循环版本的信号:")
for i, sig in enumerate(loop_signals[:10]):
    print(f"  {i+1}. {sig.timestamp.date()} {sig.signal_type.name} @ {sig.price:.2f} - {sig.reason[:50]}")

print("\n向量化版本的信号:")
for i, sig in enumerate(vec_signals[:10]):
    print(f"  {i+1}. {sig.timestamp.date()} {sig.signal_type.name} @ {sig.price:.2f} - {sig.reason[:50]}")

# 对比时间戳
loop_dates = set([s.timestamp for s in loop_signals])
vec_dates = set([s.timestamp for s in vec_signals])

common_dates = loop_dates & vec_dates
only_loop = loop_dates - vec_dates
only_vec = vec_dates - loop_dates

print(f"\n共同信号数：{len(common_dates)}")
print(f"仅循环版本有：{len(only_loop)} 个")
print(f"仅向量化版本有：{len(only_vec)} 个")

if only_loop:
    print("\n仅循环版本有的信号日期:")
    for d in sorted(list(only_loop))[:5]:
        print(f"  {d.date()}")

if only_vec:
    print("\n仅向量化版本有的信号日期:")
    for d in sorted(list(only_vec))[:5]:
        print(f"  {d.date()}")
