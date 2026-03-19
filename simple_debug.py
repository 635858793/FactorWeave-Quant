"""
简化的信号一致性调试脚本
"""

import pandas as pd
import numpy as np

# 创建测试数据
np.random.seed(42)
n_points = 243
dates = pd.date_range(start='2023-01-01', periods=n_points, freq='D')
close_prices = 100 + np.cumsum(np.random.randn(n_points) * 0.5)

data = pd.DataFrame({
    'close': close_prices
}, index=dates)

# 计算 MA20
ma_20 = data['close'].rolling(20).mean()

# 测试 MA 趋势判断的关键差异
print("MA 趋势判断对比:")
print("=" * 80)

for i in range(20, 30):
    current_price = data['close'].iloc[i]
    current_ma = ma_20.iloc[i]
    prev_ma = ma_20.iloc[i-1] if i > 0 else current_ma
    
    # 循环版本的逻辑
    ma_trend_bull_loop = current_price > current_ma and current_ma > prev_ma
    ma_trend_bear_loop = current_price < current_ma and current_ma < prev_ma
    
    # 向量化版本的逻辑
    ma_array = ma_20.values
    close_array = data['close'].values
    
    ma_trend_bull_vec = (close_array > ma_array) & (ma_array > np.roll(ma_array, 1))
    ma_trend_bear_vec = (close_array < ma_array) & (ma_array < np.roll(ma_array, 1))
    ma_trend_bull_vec[0] = False
    ma_trend_bear_vec[0] = False
    
    match_bull = ma_trend_bull_loop == ma_trend_bull_vec[i]
    match_bear = ma_trend_bear_loop == ma_trend_bear_vec[i]
    
    status = "✅" if (match_bull and match_bear) else "❌"
    print(f"{status} i={i}: price={current_price:.2f}, MA={current_ma:.2f}, prev_MA={prev_ma:.2f}")
    print(f"   循环：bull={ma_trend_bull_loop}, bear={ma_trend_bear_loop}")
    print(f"   向量：bull={ma_trend_bull_vec[i]}, bear={ma_trend_bear_vec[i]}")
    if not match_bull or not match_bear:
        print(f"   ⚠️ 不匹配！")

print("\n" + "=" * 80)
print("调试完成")
