"""
测试风险指标显示
"""
import sys
import numpy as np
import pandas as pd

# 模拟回测数据
timestamps = pd.date_range('2024-01-01', periods=100, freq='D')
cumulative_returns = np.cumsum(np.random.randn(100) * 0.01)
# 计算回撤（使用 pandas 的 cummin）
cumulative_returns_series = pd.Series(cumulative_returns)
running_max = cumulative_returns_series.cummax()
drawdowns = (cumulative_returns_series - running_max) / (1 + running_max)
sharpe_ratios = np.ones(100) * 0.5  # 夏普比率恒定为 0.5
var_values = np.ones(100) * -0.02  # VaR 恒定为 -2%
cvar_values = np.ones(100) * -0.03  # CVaR 恒定为 -3%

# 创建 DataFrame
df = pd.DataFrame({
    'timestamp': timestamps,
    'cumulative_return': cumulative_returns,
    'drawdown': drawdowns,
    'sharpe_ratio': sharpe_ratios,
    'var_95': var_values,
    'cvar_95': cvar_values
})

print("=" * 80)
print("测试数据生成完成")
print("=" * 80)
print(f"\nDataFrame 列：{df.columns.tolist()}")
print(f"\n数据形状：{df.shape}")
print(f"\n前 5 行数据:")
print(df.head())
print(f"\n统计信息:")
print(df.describe())

# 检查关键指标
print("\n" + "=" * 80)
print("关键指标检查")
print("=" * 80)
print(f"var_95 最终值：{df['var_95'].iloc[-1]:.6f} ({df['var_95'].iloc[-1]*100:.4f}%)")
print(f"cvar_95 最终值：{df['cvar_95'].iloc[-1]:.6f} ({df['cvar_95'].iloc[-1]*100:.4f}%)")
print(f"sharpe_ratio 最终值：{df['sharpe_ratio'].iloc[-1]:.3f}")
print(f"drawdown 最终值：{df['drawdown'].iloc[-1]:.6f}")

# 模拟图表绘制逻辑
print("\n" + "=" * 80)
print("模拟图表绘制逻辑")
print("=" * 80)

var_offset = -5
cvar_offset = -5
sharpe_offset = -10

var_final = df['var_95'].iloc[-1]
cvar_final = df['cvar_95'].iloc[-1]

print(f"\nVaR 水平线位置：{var_final * 100 + var_offset:.2f}")
print(f"CVaR 水平线位置：{cvar_final * 100 + cvar_offset:.2f}")
print(f"夏普比率偏移后范围：[{df['sharpe_ratio'].min() + sharpe_offset:.3f}, {df['sharpe_ratio'].max() + sharpe_offset:.3f}]")

print("\n✅ 测试完成！数据应该可以正常显示。")
