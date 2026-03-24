"""
信号一致性调试脚本 - 逐点对比循环和向量化版本
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, 'd:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui')

from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy

# 创建测试数据
def create_test_data(n_points=243):
    """创建测试数据"""
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
strategy.initialize()

# 生成测试数据
data = create_test_data(243)
print(f"测试数据量：{len(data)} 点")

# 计算技术指标
indicators = strategy._calculate_technical_indicators(data)
print(f"指标计算完成：{list(indicators.columns)}")

# 找到起始索引
ma_valid_indices = indicators['ma_20'].notna()
first_valid_idx = int(ma_valid_indices.argmax())
print(f"MA20 第一个有效索引：{first_valid_idx}")

# 测试前 10 个点的详细对比
test_start = first_valid_idx
test_end = min(first_valid_idx + 10, len(data))

print(f"\n逐点对比（索引 {test_start} 到 {test_end-1}）：")
print("=" * 120)

for i in range(test_start, test_end):
    print(f"\n索引 {i} ({data.index[i]}):")
    print("-" * 120)
    
    # 循环版本
    loop_conditions = strategy._evaluate_signal_conditions(
        data.iloc[:i+1], 
        indicators.iloc[:i+1], 
        i
    )
    
    # 获取当前指标值
    current_price = data['close'].iloc[i]
    current_ma = indicators['ma_20'].iloc[i]
    current_macd = indicators['macd'].iloc[i]
    current_macd_signal = indicators['macd_signal'].iloc[i]
    current_rsi = indicators['rsi_14'].iloc[i]
    current_boll_upper = indicators['boll_upper'].iloc[i]
    current_boll_lower = indicators['boll_lower'].iloc[i]
    
    # 手动计算向量化版本的条件
    ma_trend_bull = current_price > current_ma
    ma_trend_bear = current_price < current_ma
    
    if i > 0:
        prev_ma = indicators['ma_20'].iloc[i-1]
        prev_macd = indicators['macd'].iloc[i-1]
        prev_macd_signal = indicators['macd_signal'].iloc[i-1]
        
        ma_trend_bull = ma_trend_bull and (current_ma > prev_ma)
        ma_trend_bear = ma_trend_bear and (current_ma < prev_ma)
        
        macd_bull = (current_macd > current_macd_signal) and (prev_macd <= prev_macd_signal)
        macd_bear = (current_macd < current_macd_signal) and (prev_macd >= prev_macd_signal)
    else:
        ma_trend_bull = False
        ma_trend_bear = False
        macd_bull = False
        macd_bear = False
    
    rsi_oversold = current_rsi < 30
    rsi_overbought = current_rsi > 70
    boll_breakout_upper = current_price > current_boll_upper
    boll_breakout_lower = current_price < current_boll_lower
    
    # 计算分数
    buy_score = 0.0
    sell_score = 0.0
    
    if ma_trend_bull: buy_score += 0.25
    if macd_bull: buy_score += 0.25
    if rsi_oversold: buy_score += 0.2
    if boll_breakout_lower: buy_score += 0.15
    
    if ma_trend_bear: sell_score += 0.25
    if macd_bear: sell_score += 0.25
    if rsi_overbought: sell_score += 0.2
    if boll_breakout_upper: sell_score += 0.15
    
    signal_threshold = 0.4
    manual_buy = buy_score >= signal_threshold
    manual_sell = sell_score >= signal_threshold
    
    print(f"  价格={current_price:.2f}, MA20={current_ma:.2f}, RSI={current_rsi:.2f}")
    print(f"  MACD={current_macd:.4f}, Signal={current_macd_signal:.4f}")
    print(f"  循环版本：buy={loop_conditions['buy_signal']}, sell={loop_conditions['sell_signal']}, score={loop_conditions['confidence']:.2f}")
    print(f"  手动计算：buy={manual_buy}, sell={manual_sell}, buy_score={buy_score:.2f}, sell_score={sell_score:.2f}")
    
    if loop_conditions['buy_signal'] != manual_buy or loop_conditions['sell_signal'] != manual_sell:
        print(f"  ⚠️ 不一致！")
        print(f"    MA 趋势：bull={ma_trend_bull}, bear={ma_trend_bear}")
        print(f"    MACD: bull={macd_bull}, bear={macd_bear}")
        print(f"    RSI: oversold={rsi_oversold}, overbought={rsi_overbought}")
        print(f"    布林带：upper={boll_breakout_upper}, lower={boll_breakout_lower}")

print("\n" + "=" * 120)
print("调试完成")
