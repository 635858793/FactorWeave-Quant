#!/usr/bin/env python3
"""
回测信号诊断脚本

验证为什么回测图表前 150 个点是直线
"""

import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level=logging.INFO, format="{time:HH:mm:ss.SSS} | {level} | {message}")


def simulate_adaptive_strategy_signals():
    """模拟自适应策略的信号生成逻辑"""
    print("\n" + "="*80)
    print("测试 1: 模拟 adaptive_strategy.py 的信号生成逻辑")
    print("="*80)
    
    # 模拟 243 个数据点
    total_bars = 243
    np.random.seed(42)
    close_prices = 100 + np.cumsum(np.random.randn(total_bars))  # 随机游走价格
    
    # 计算 MA20
    ma20 = pd.Series(close_prices).rolling(20).mean()
    
    # 找到 MA20 有效的起始索引
    ma_valid_count = ma20.notna().sum()
    start_idx = max(20, total_bars - 100) if ma_valid_count >= 20 else max(20, ma_valid_count)
    
    print(f"\n数据总量：{total_bars} 个点")
    print(f"MA20 有效数据量：{ma_valid_count} 个点")
    print(f"信号检查起始索引：start_idx = max(20, {total_bars} - 100) = {start_idx}")
    print(f"\n这意味着：")
    print(f"  - 前 {start_idx} 个点不会检查信号")
    print(f"  - 只检查第 {start_idx} 到 {total_bars-1} 个点（共 {total_bars - start_idx} 个点）")
    
    # 模拟信号生成
    signals = []
    for i in range(start_idx, total_bars):
        # 简化信号条件：价格上穿 MA20
        if i > start_idx:
            prev_price = close_prices[i-1]
            prev_ma = ma20.iloc[i-1]
            curr_price = close_prices[i]
            curr_ma = ma20.iloc[i]
            
            # 金叉信号
            if prev_price <= prev_ma and curr_price > curr_ma:
                signals.append({
                    'index': i,
                    'type': 'BUY',
                    'price': curr_price
                })
    
    print(f"\n生成的信号数量：{len(signals)}")
    if signals:
        print(f"第一个信号位置：index={signals[0]['index']}")
        print(f"最后一个信号位置：index={signals[-1]['index']}")
    
    # 可视化
    print(f"\n信号分布（每 10 个点用 * 表示有信号）:")
    for i in range(total_bars):
        has_signal = any(s['index'] == i for s in signals)
        if i % 10 == 0:
            print(f"\n{i:3d}: ", end="")
        print("*" if has_signal else ".", end="")
    print()
    
    return start_idx, signals


def analyze_equity_curve():
    """分析资金曲线"""
    print("\n" + "="*80)
    print("测试 2: 分析资金曲线为什么前 150 个点是直线")
    print("="*80)
    
    # 根据实际日志数据
    initial_capital = 1000000.0
    total_bars = 243
    
    # 模拟：前 150 个点没有交易，后面有交易
    equity_curve = [initial_capital] * 150  # 前 150 个点是初始值
    
    # 后面 93 个点有波动
    np.random.seed(42)
    returns = np.random.normal(-0.0003, 0.001, 93)  # 平均每天亏损 0.03%
    remaining_equity = initial_capital * np.cumprod(1 + returns)
    equity_curve.extend(remaining_equity.tolist())
    
    print(f"\n资金曲线统计:")
    print(f"  前 150 个点：全部 = {initial_capital}")
    print(f"  后 93 个点：min={min(remaining_equity):.2f}, max={max(remaining_equity):.2f}")
    print(f"  最终值：{equity_curve[-1]:.2f}")
    print(f"  总收益：{(equity_curve[-1]/initial_capital - 1)*100:.4f}%")
    
    # 计算回撤
    running_max = initial_capital
    drawdowns = []
    for value in equity_curve:
        if value > running_max:
            running_max = value
        drawdown = (value - running_max) / running_max
        drawdowns.append(drawdown)
    
    print(f"\n回撤统计:")
    print(f"  前 150 个点：全部 = {max(drawdowns[:150]):.6f}")
    print(f"  后 93 个点：min={min(drawdowns[150:]):.6f}, max={max(drawdowns[150:]):.6f}")
    
    # 可视化
    print(f"\n资金曲线形状（每 10 个点）:")
    for i in range(0, total_bars, 10):
        value = equity_curve[i]
        change = (value - initial_capital) / initial_capital * 100
        bar = "█" * int(abs(change) * 100)
        direction = "▼" if change < 0 else "▲" if change > 0 else "─"
        print(f"{i:3d}: {direction} {bar} ({change:+.4f}%)")


def check_strategy_parameters():
    """检查策略参数"""
    print("\n" + "="*80)
    print("测试 3: 检查策略参数对信号生成的影响")
    print("="*80)
    
    print("\nadaptive_strategy.py 的关键参数:")
    print("  - ma_period: MA 周期（默认 20）")
    print("  - 信号检查范围：最后 100 个点")
    print("  - 信号条件：需要同时满足 MA 趋势、MACD、RSI、布林带等条件")
    
    print("\n如果总数据量 = 243:")
    print("  start_idx = max(20, 243 - 100) = 143")
    print("  所以前 143 个点不会检查信号！")
    
    print("\n这解释了为什么图表前 150 个点是直线：")
    print("  1. 策略只检查最后 100 个点")
    print("  2. 前 143 个点根本没有检查信号")
    print("  3. 所以没有交易，资金曲线是平的")


def propose_solutions():
    """提出解决方案"""
    print("\n" + "="*80)
    print("测试 4: 解决方案")
    print("="*80)
    
    print("\n方案 1: 修改策略，检查所有有效数据点")
    print("  优点：不会错过早期的交易机会")
    print("  缺点：可能增加计算时间")
    print("  修改位置：plugins/strategies/adaptive_strategy.py")
    print("  修改内容：start_idx = max(20, len(data) - 100)")
    print("           改为：start_idx = 20  # 或第一个 MA 有效的索引")
    
    print("\n方案 2: 增加回溯窗口大小")
    print("  优点：保持性能优化，同时增加检查范围")
    print("  缺点：仍然会错过早期信号")
    print("  修改内容：将 100 改为更大的值，如 200")
    
    print("\n方案 3: 移除限制，从第一个有效点开始检查")
    print("  优点：最全面，不会错过任何信号")
    print("  缺点：计算时间可能增加")
    print("  推荐：这是最佳方案")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("回测信号诊断脚本 - 为什么前 150 个点是直线")
    print("="*80)
    
    # 运行所有测试
    start_idx, signals = simulate_adaptive_strategy_signals()
    analyze_equity_curve()
    check_strategy_parameters()
    propose_solutions()
    
    print("\n" + "="*80)
    print("✅ 诊断完成！")
    print("="*80)
    print("\n结论:")
    print("  1. 前 150 个点是直线是**策略设计的结果**，不是 bug")
    print("  2. adaptive_strategy.py 只检查最后 100 个数据点")
    print("  3. 对于 243 个数据点，只检查第 143-242 个点")
    print("  4. 前 143 个点没有检查信号，所以没有交易")
    
    print("\n建议:")
    print("  - 如果希望从数据开头就开始交易，需要修改策略代码")
    print("  - 将 start_idx 的计算逻辑改为从第一个 MA 有效的点开始")
    print("="*80 + "\n")
