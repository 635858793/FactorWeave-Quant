"""
详细检查所有条件
"""

import sys
import pandas as pd
import numpy as np

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

# 测试特定日期
target_date = pd.Timestamp('2023-04-15')
i = data.index.get_loc(target_date)

current_price = data['close'].iloc[i]
current_ma = indicators['ma_20'].iloc[i]
current_macd = indicators['macd'].iloc[i]
current_macd_signal = indicators['macd_signal'].iloc[i]
current_rsi = indicators['rsi_14'].iloc[i]
current_boll_upper = indicators['boll_upper'].iloc[i]
current_boll_lower = indicators['boll_lower'].iloc[i]

# 检查 MA 趋势
prev_ma = indicators['ma_20'].iloc[i-1]
ma_trend_bull = current_price > current_ma and current_ma > prev_ma
ma_trend_bear = current_price < current_ma and current_ma < prev_ma

# 检查 MACD
prev_macd = indicators['macd'].iloc[i-1]
prev_macd_signal = indicators['macd_signal'].iloc[i-1]
macd_bull = current_macd > current_macd_signal and (prev_macd <= prev_macd_signal)
macd_bear = current_macd < current_macd_signal and (prev_macd >= prev_macd_signal)

# 检查 RSI
rsi_oversold = current_rsi < 30
rsi_overbought = current_rsi > 70

# 检查布林带
boll_breakout_upper = current_price > current_boll_upper
boll_breakout_lower = current_price < current_boll_lower

print(f"{target_date.date()} (索引{i}) 详细分析:")
print(f"  价格={current_price:.2f}")
print(f"  MA20={current_ma:.2f}, 前一日 MA={prev_ma:.2f}")
print(f"  MACD={current_macd:.4f}, Signal={current_macd_signal:.4f}")
print(f"  前一日 MACD={prev_macd:.4f}, Signal={prev_macd_signal:.4f}")
print(f"  RSI={current_rsi:.2f}")
print(f"  布林带上轨={current_boll_upper:.2f}, 下轨={current_boll_lower:.2f}")
print()
print(f"  MA 趋势 bull: {current_price} > {current_ma} and {current_ma} > {prev_ma} = {ma_trend_bull}")
print(f"  MA 趋势 bear: {current_price} < {current_ma} and {current_ma} < {prev_ma} = {ma_trend_bear}")
print(f"  MACD bull: {current_macd} > {current_macd_signal} and {prev_macd} <= {prev_macd_signal} = {macd_bull}")
print(f"  MACD bear: {current_macd} < {current_macd_signal} and {prev_macd} >= {prev_macd_signal} = {macd_bear}")
print(f"  RSI oversold: {current_rsi} < 30 = {rsi_oversold}")
print(f"  RSI overbought: {current_rsi} > 70 = {rsi_overbought}")
print(f"  Bollinger upper: {current_price} > {current_boll_upper} = {boll_breakout_upper}")
print(f"  Bollinger lower: {current_price} < {current_boll_lower} = {boll_breakout_lower}")
print()

# 计算分数
buy_conditions = []
sell_conditions = []
confidence_score = 0.0

if ma_trend_bull:
    buy_conditions.append("MA 趋势向上")
    confidence_score += 0.25
if macd_bull:
    buy_conditions.append("MACD 金叉")
    confidence_score += 0.25
if rsi_oversold:
    buy_conditions.append("RSI 超卖反弹")
    confidence_score += 0.2
if boll_breakout_lower:
    buy_conditions.append("布林带反弹")
    confidence_score += 0.15

if ma_trend_bear:
    sell_conditions.append("MA 趋势向下")
    confidence_score += 0.25
if macd_bear:
    sell_conditions.append("MACD 死叉")
    confidence_score += 0.25
if rsi_overbought:
    sell_conditions.append("RSI 超买回调")
    confidence_score += 0.2
if boll_breakout_upper:
    sell_conditions.append("布林带突破")
    confidence_score += 0.15

print(f"  买入条件：{buy_conditions}")
print(f"  卖出条件：{sell_conditions}")
print(f"  总分数：{confidence_score}")
print(f"  买入条件数：{len(buy_conditions)}")
print(f"  卖出条件数：{len(sell_conditions)}")

signal_threshold = 0.4
buy_signal = len(buy_conditions) >= 2 and confidence_score >= signal_threshold
sell_signal = len(sell_conditions) >= 2 and confidence_score >= signal_threshold

print(f"\n  最终信号：buy={buy_signal}, sell={sell_signal}")
