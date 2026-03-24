"""
检查实际的阈值和分数
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

# 检查策略参数
print("策略参数:")
for param in ['signal_threshold', 'init_cash', 'vectorized_enabled']:
    try:
        val = strategy.get_parameter(param, 'NOT_FOUND')
        print(f"  {param} = {val}")
    except:
        pass

# 生成测试数据
data = create_test_data(243)

# 计算技术指标
indicators = strategy._calculate_technical_indicators(data)

# 测试特定日期
target_date = pd.Timestamp('2023-04-15')
i = data.index.get_loc(target_date)

# 调用循环版本的方法
result = strategy._evaluate_signal_conditions(
    data.iloc[:i+1],
    indicators.iloc[:i+1],
    i
)

print(f"\n{target_date.date()} 的评估结果:")
print(f"  buy_signal={result['buy_signal']}")
print(f"  sell_signal={result['sell_signal']}")
print(f"  confidence={result['confidence']}")
print(f"  reason={result['reason']}")

# 手动验证
current_price = data['close'].iloc[i]
current_rsi = indicators['rsi_14'].iloc[i]
current_boll_lower = indicators['boll_lower'].iloc[i]

rsi_oversold = current_rsi < 30
boll_breakout_lower = current_price < current_boll_lower

print(f"\n手动验证:")
print(f"  RSI={current_rsi:.2f} < 30 = {rsi_oversold}")
print(f"  Price={current_price:.2f} < Bollinger={current_boll_lower:.2f} = {boll_breakout_lower}")
print(f"  条件数 = {sum([rsi_oversold, boll_breakout_lower])}")
print(f"  分数 = 0.2 + 0.15 = 0.35")
