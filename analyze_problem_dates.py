"""
检查特定日期的指标值，找出 RSI 和布林带判断的差异
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

# 检查特定日期
problem_dates = [
    pd.Timestamp('2023-04-15'),
    pd.Timestamp('2023-06-29'),
    pd.Timestamp('2023-06-30')
]

print("问题日期分析:")
print("=" * 120)

for target_date in problem_dates:
    if target_date not in data.index:
        print(f"\n{target_date.date()} - 不在数据中")
        continue
        
    i = data.index.get_loc(target_date)
    
    current_price = data['close'].iloc[i]
    current_rsi = indicators['rsi_14'].iloc[i]
    current_boll_upper = indicators['boll_upper'].iloc[i]
    current_boll_lower = indicators['boll_lower'].iloc[i]
    current_ma = indicators['ma_20'].iloc[i]
    current_macd = indicators['macd'].iloc[i]
    current_macd_signal = indicators['macd_signal'].iloc[i]
    
    # 检查条件
    rsi_oversold = current_rsi < 30
    rsi_overbought = current_rsi > 70
    boll_breakout_upper = current_price > current_boll_upper
    boll_breakout_lower = current_price < current_boll_lower
    
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
    buy_signal = buy_score >= signal_threshold
    sell_signal = sell_score >= signal_threshold
    
    print(f"\n{target_date.date()} (索引{i}):")
    print(f"  价格={current_price:.2f}, RSI={current_rsi:.2f}")
    print(f"  布林带上轨={current_boll_upper:.2f}, 下轨={current_boll_lower:.2f}")
    print(f"  MA20={current_ma:.2f}, MACD={current_macd:.4f}, Signal={current_macd_signal:.4f}")
    print(f"  RSI 超卖={rsi_oversold} ({current_rsi:.2f} < 30)")
    print(f"  RSI 超买={rsi_overbought} ({current_rsi:.2f} > 70)")
    print(f"  布林带突破上={boll_breakout_upper} ({current_price:.2f} > {current_boll_upper:.2f})")
    print(f"  布林带突破下={boll_breakout_lower} ({current_price:.2f} < {current_boll_lower:.2f})")
    print(f"  MA 趋势 bull={ma_trend_bull}, bear={ma_trend_bear}")
    print(f"  MACD bull={macd_bull}, bear={macd_bear}")
    print(f"  → buy_score={buy_score:.2f}, sell_score={sell_score:.2f}")
    print(f"  → buy_signal={buy_signal}, sell_signal={sell_signal}")

print("\n" + "=" * 120)
print("分析完成")
