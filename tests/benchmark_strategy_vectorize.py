"""性能验证: builtin_strategies.py 5策略向量化加速比"""

import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def generate_trend_data(n_rows=50000):
    np.random.seed(42)
    data = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(n_rows) * 0.8),
        'volume': np.abs(np.random.randn(n_rows) * 1e6 + 5e6).astype(int),
        'code': ['000001'] * n_rows,
    }, index=pd.date_range('2020-01-01', periods=n_rows, freq='h'))
    data['open'] = data['close'] + np.random.randn(n_rows) * 0.2
    data['high'] = data['close'] + np.abs(np.random.randn(n_rows) * 0.5)
    data['low'] = data['close'] - np.abs(np.random.randn(n_rows) * 0.5)
    data['close'] = np.maximum(data['close'], 1)
    return data


def old_style_loop_ma(data, short_period=5, long_period=20):
    """原始for-range全量遍历模拟(仅计数,不构建对象)"""
    data = data.copy()
    data['ma_short'] = data['close'].rolling(window=short_period).mean()
    data['ma_long'] = data['close'].rolling(window=long_period).mean()
    data['signal'] = 0
    data.loc[data['ma_short'] > data['ma_long'], 'signal'] = 1
    data.loc[data['ma_short'] < data['ma_long'], 'signal'] = -1
    data['signal_change'] = data['signal'].diff()
    count = 0
    for i in range(long_period, len(data)):
        sc = data['signal_change'].iloc[i]
        if sc == 2 or sc == -2:
            count += 1
    return count


def new_style_vec_ma(data, short_period=5, long_period=20):
    """向量化信号检测(仅计数)"""
    data = data.copy()
    data['ma_short'] = data['close'].rolling(window=short_period).mean()
    data['ma_long'] = data['close'].rolling(window=long_period).mean()
    data['signal'] = 0
    data.loc[data['ma_short'] > data['ma_long'], 'signal'] = 1
    data.loc[data['ma_short'] < data['ma_long'], 'signal'] = -1
    data['signal_change'] = data['signal'].diff()
    buy_mask = data['signal_change'] == 2
    sell_mask = data['signal_change'] == -2
    signal_indices = data.index[buy_mask | sell_mask]
    count = 0
    for idx in signal_indices:
        i = data.index.get_loc(idx)
        if i >= long_period:
            count += 1
    return count


def run_benchmark():
    sizes = [10000, 30000, 50000, 100000]

    print("=" * 65)
    print("for-range全量遍历 vs 向量化boolean-indexing 对比")
    print("=" * 65)

    for size in sizes:
        data = generate_trend_data(size)
        data_copy1 = data.copy()
        data_copy2 = data.copy()

        # 重置随机种子确保数据一致
        np.random.seed(42)

        # old-style
        t0 = time.perf_counter()
        c1 = old_style_loop_ma(data_copy1)
        t_old = time.perf_counter() - t0

        # new-style
        t0 = time.perf_counter()
        c2 = new_style_vec_ma(data_copy2)
        t_new = time.perf_counter() - t0

        assert c1 == c2, f"结果不一致: old={c1} new={c2}"
        speedup = t_old / t_new if t_new > 0 else 0
        print(f"  {size:6d}行 | old={t_old*1000:6.2f}ms | new={t_new*1000:6.2f}ms | "
              f"signals={c1:4d} | 加速 {speedup:.1f}x")

    print(f"\n{'='*65}")
    print("完整策略 generate_signals() 耗时 (含pandas计算+confidence+对象构造)")
    print("=" * 65)
    from core.strategy.builtin_strategies import (
        MAStrategy, MACDStrategy, RSIStrategy, KDJStrategy, BollingerBandsStrategy
    )

    for size in [10000, 50000]:
        data = generate_trend_data(size)
        print(f"\n  {size}行:")
        for name, strat in [('MA', MAStrategy()), ('MACD', MACDStrategy()),
                              ('RSI', RSIStrategy()), ('KDJ', KDJStrategy()),
                              ('BOLL', BollingerBandsStrategy())]:
            t0 = time.perf_counter()
            signals = strat.generate_signals(data.copy())
            elapsed = time.perf_counter() - t0
            print(f"    {name:5s}: {elapsed:.4f}s | {len(signals):4d}信号")

    print(f"\n{'='*65}")
    print("开销分解 (50k行 MACD, 均值)")
    print("=" * 65)
    data = generate_trend_data(50000)
    macd = MACDStrategy()
    trials = []
    for _ in range(3):
        t0 = time.perf_counter()
        _ = macd.generate_signals(data.copy())
        trials.append(time.perf_counter() - t0)
    avg_time = sum(trials) / len(trials)
    print(f"    平均耗时: {avg_time:.4f}s")
    print(f"    等效每行: {avg_time/50000*1000:.4f}ms")
    print(f"    核心优化: 循环N行→K信号行, N>>K, 消除无效迭代")


if __name__ == '__main__':
    run_benchmark()