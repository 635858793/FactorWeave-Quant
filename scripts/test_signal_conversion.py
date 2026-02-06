"""
测试信号转换逻辑（详细版）
"""

import pandas as pd
import numpy as np
from datetime import datetime
from analysis.pattern_recognition import PatternRecognizer
from analysis.pattern_base import PatternConfig, SignalType
from backtest.unified_backtest_engine import UnifiedBacktestEngine

# 创建测试数据 - 模拟锤子线形态
np.random.seed(42)
n = 100

# 创建基础价格数据
close_prices = np.random.randn(n).cumsum() + 100

# 创建锤子线形态（下影线长，上影线短，实体小）
data = pd.DataFrame({
    'open': close_prices + np.random.randn(n) * 0.5,
    'high': close_prices + np.random.rand(n) * 2,
    'low': close_prices - np.random.rand(n) * 5,  # 较长的下影线
    'close': close_prices,
    'volume': np.random.randint(1000, 10000, n)
})

# 确保high >= max(open, close)和low <= min(open, close)
data['high'] = data[['open', 'close']].max(axis=1) + np.random.rand(n) * 0.5
data['low'] = data[['open', 'close']].min(axis=1) - np.random.rand(n) * 3

# 创建形态配置
config = PatternConfig(
    id=1,
    name="测试形态",
    english_name="test_pattern",
    category="candlestick",
    signal_type=SignalType.NEUTRAL,
    description="测试形态",
    min_periods=1,
    max_periods=10,
    confidence_threshold=0.5,
    algorithm_code="basic",
    parameters={
        'min_body_ratio': 0.1,
        'shadow_ratio_threshold': 2.0,
        'body_ratio_threshold': 0.1,
        'confidence_threshold': 0.7
    },
    is_active=True
)

# 创建形态识别器
recognizer = PatternRecognizer(config)

# 识别形态
results = recognizer.recognize(data)

print(f"识别到 {len(results)} 个形态")

# 统计信号类型
signal_counts = {}
for result in results:
    signal = result.signal_type.value
    signal_counts[signal] = signal_counts.get(signal, 0) + 1

print(f"\n信号类型分布:")
for signal, count in signal_counts.items():
    print(f"  {signal}: {count}")

# 转换为交易信号
from optimization.algorithm_optimizer import PerformanceEvaluator

evaluator = PerformanceEvaluator()
signals = evaluator._convert_patterns_to_signals(results, data)

print(f"\n交易信号统计:")
print(f"  无信号(0): {(signals['signal'] == 0).sum()}")
print(f"  买入信号(1): {(signals['signal'] == 1).sum()}")
print(f"  卖出信号(-1): {(signals['signal'] == -1).sum()}")

# 打印信号分布
print(f"\n信号分布（前30行）:")
print(signals.head(30))

# 打印买入信号的索引
buy_signals = signals[signals['signal'] == 1].index.tolist()
print(f"\n买入信号索引: {buy_signals}")

# 打印卖出信号的索引
sell_signals = signals[signals['signal'] == -1].index.tolist()
print(f"卖出信号索引: {sell_signals}")

# 合并信号和价格数据
backtest_data = data.copy()
backtest_data['signal'] = signals['signal']

print(f"\n回测数据前10行:")
print(backtest_data.head(10))

# 使用回测系统评估
engine = UnifiedBacktestEngine()

# 运行回测
print(f"\n开始回测...")
backtest_results = engine.run_backtest(backtest_data)

print(f"\n回测结果:")
for key, value in backtest_results.items():
    if isinstance(value, (int, float)):
        print(f"  {key}: {value}")
    elif isinstance(value, (list, dict)) and len(value) < 10:
        print(f"  {key}: {value}")
    else:
        print(f"  {key}: {type(value).__name__} (长度: {len(value) if hasattr(value, '__len__') else 'N/A'})")

# 尝试访问性能指标
print(f"\n尝试访问性能指标:")
print(f"  total_return: {backtest_results.get('total_return', 'N/A')}")
print(f"  annual_return: {backtest_results.get('annual_return', 'N/A')}")
print(f"  sharpe_ratio: {backtest_results.get('sharpe_ratio', 'N/A')}")
print(f"  max_drawdown: {backtest_results.get('max_drawdown', 'N/A')}")
print(f"  win_rate: {backtest_results.get('win_rate', 'N/A')}")
print(f"  profit_factor: {backtest_results.get('profit_factor', 'N/A')}")
print(f"  total_trades: {backtest_results.get('total_trades', 'N/A')}")
print(f"  winning_trades: {backtest_results.get('winning_trades', 'N/A')}")
print(f"  losing_trades: {backtest_results.get('losing_trades', 'N/A')}")
print(f"  avg_win: {backtest_results.get('avg_win', 'N/A')}")
print(f"  avg_loss: {backtest_results.get('avg_loss', 'N/A')}")

# 打印equity曲线
if 'equity' in backtest_results:
    equity = backtest_results['equity']
    print(f"\nEquity曲线（前10个值）:")
    print(equity.head(10))
    print(f"Equity曲线（最后10个值）:")
    print(equity.tail(10))
