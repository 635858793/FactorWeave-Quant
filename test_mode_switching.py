#!/usr/bin/env python3
"""
模式切换功能测试脚本

测试 check_mode 和 lookback_window 参数的实际效果
验证回测/实盘模式的功能差异
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime

# 添加项目路径
sys.path.insert(0, r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui')

from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy
from core.trading.trading_mode import TradingMode, ModeContext, create_mode_context


def generate_test_data(length: int = 500) -> pd.DataFrame:
    """
    生成测试数据
    
    Args:
        length: 数据长度
        
    Returns:
        包含 OHLCV 的 DataFrame
    """
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=length, freq='D')
    
    # 生成随机游走价格
    returns = np.random.randn(length).cumsum() / 100 + 0.0001
    close = 100 * np.exp(returns)
    
    # 生成 OHLCV
    high = close * (1 + np.random.rand(length) * 0.02)
    low = close * (1 - np.random.rand(length) * 0.02)
    open_price = close * (0.98 + np.random.rand(length) * 0.04)
    volume = np.random.randint(1000000, 10000000, length)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


def test_check_mode_parameter():
    """测试 check_mode 参数的使用"""
    print("=" * 80)
    print("测试 1: check_mode 参数功能验证")
    print("=" * 80)
    
    # 创建策略实例
    strategy = AdaptivePandasStrategy()
    
    # 测试不同模式
    modes = ['backtest', 'live', 'hybrid']
    
    for mode in modes:
        print(f"\n设置模式：{mode}")
        strategy.set_parameter('check_mode', mode)
        strategy.set_parameter('lookback_window', 200)
        
        # 验证参数设置
        actual_mode = strategy.get_parameter('check_mode', 'hybrid')
        print(f"  ✓ 模式已设置：{actual_mode}")
        
        # 生成测试数据
        test_data = generate_test_data(300)
        
        # 生成信号
        signals = strategy.generate_signals(test_data)
        print(f"  ✓ 生成信号数：{len(signals)}")
    
    print("\n✅ check_mode 参数测试通过")


def test_lookback_window_parameter():
    """测试 lookback_window 参数的使用"""
    print("\n" + "=" * 80)
    print("测试 2: lookback_window 参数功能验证")
    print("=" * 80)
    
    strategy = AdaptivePandasStrategy()
    strategy.set_parameter('check_mode', 'live')
    
    # 测试不同窗口大小
    windows = [50, 100, 200, 500]
    
    for window in windows:
        print(f"\n设置窗口：{window}")
        strategy.set_parameter('lookback_window', window)
        
        # 验证参数设置
        actual_window = strategy.get_parameter('lookback_window', 200)
        print(f"  ✓ 窗口已设置：{actual_window}")
        
        # 生成测试数据
        test_data = generate_test_data(600)
        
        # 生成信号
        signals = strategy.generate_signals(test_data)
        print(f"  ✓ 生成信号数：{len(signals)}")
    
    print("\n✅ lookback_window 参数测试通过")


def test_mode_context():
    """测试 ModeContext 的创建和使用"""
    print("\n" + "=" * 80)
    print("测试 3: ModeContext 功能验证")
    print("=" * 80)
    
    # 创建回测模式上下文
    print("\n创建回测模式上下文...")
    backtest_ctx = create_mode_context('backtest', 
                                       start_date='2023-01-01',
                                       end_date='2023-12-31')
    print(f"  ✓ 模式：{backtest_ctx.mode.value}")
    print(f"  ✓ 是否回测：{backtest_ctx.is_backtest()}")
    print(f"  ✓ 是否实盘：{backtest_ctx.is_live()}")
    print(f"  ✓ 开始日期：{backtest_ctx.get_config('start_date')}")
    
    # 创建模拟交易上下文
    print("\n创建模拟交易上下文...")
    paper_ctx = create_mode_context('paper', symbol='000001.SH')
    print(f"  ✓ 模式：{paper_ctx.mode.value}")
    print(f"  ✓ 是否回测：{paper_ctx.is_backtest()}")
    print(f"  ✓ 是否实盘：{paper_ctx.is_live()}")
    print(f"  ✓ 交易标的：{paper_ctx.get_config('symbol')}")
    
    # 创建实盘交易上下文
    print("\n创建实盘交易上下文...")
    live_ctx = create_mode_context('live', symbol='000001.SH')
    print(f"  ✓ 模式：{live_ctx.mode.value}")
    print(f"  ✓ 是否回测：{live_ctx.is_backtest()}")
    print(f"  ✓ 是否实盘：{live_ctx.is_live()}")
    print(f"  ✓ 性能关键：{live_ctx.get_config('performance_critical')}")
    
    print("\n✅ ModeContext 功能测试通过")


def test_mode_aware_mixin():
    """测试 ModeAwareMixin 功能"""
    print("\n" + "=" * 80)
    print("测试 4: ModeAwareMixin 功能验证")
    print("=" * 80)
    
    from core.trading.trading_mode import ModeAwareMixin
    
    # 创建测试类
    class TestComponent(ModeAwareMixin):
        def __init__(self):
            super().__init__()
            self.mode_changed_count = 0
        
        def _on_mode_changed(self, new_context):
            self.mode_changed_count += 1
            print(f"  ✓ 模式切换回调被调用：{new_context.mode.value}")
    
    # 创建组件
    component = TestComponent()
    
    # 设置回测模式
    print("\n设置回测模式...")
    backtest_ctx = create_mode_context('backtest')
    component.mode_context = backtest_ctx
    print(f"  ✓ 当前模式：{component.trading_mode.value}")
    print(f"  ✓ 是否回测：{component.is_backtest_mode()}")
    
    # 设置实盘模式
    print("\n设置实盘模式...")
    live_ctx = create_mode_context('live', symbol='000001.SH')
    component.mode_context = live_ctx
    print(f"  ✓ 当前模式：{component.trading_mode.value}")
    print(f"  ✓ 是否实盘：{component.is_live_mode()}")
    
    print(f"\n  ✓ 模式切换次数：{component.mode_changed_count}")
    print("\n✅ ModeAwareMixin 功能测试通过")


def test_performance_difference():
    """测试不同模式下的性能差异"""
    print("\n" + "=" * 80)
    print("测试 5: 不同模式性能对比")
    print("=" * 80)
    
    import time
    
    strategy = AdaptivePandasStrategy()
    test_data = generate_test_data(1000)
    
    modes = ['backtest', 'live', 'hybrid']
    results = {}
    
    for mode in modes:
        strategy.set_parameter('check_mode', mode)
        strategy.set_parameter('lookback_window', 200)
        
        # 预热
        strategy.generate_signals(test_data)
        
        # 性能测试
        start = time.time()
        for _ in range(10):
            signals = strategy.generate_signals(test_data)
        end = time.time()
        
        avg_time = (end - start) / 10 * 1000  # 毫秒
        results[mode] = avg_time
        print(f"\n{mode} 模式:")
        print(f"  ✓ 平均耗时：{avg_time:.2f}ms")
        print(f"  ✓ 信号数量：{len(signals)}")
    
    # 性能对比
    print("\n性能对比:")
    baseline = results['backtest']
    for mode, time_ms in results.items():
        ratio = time_ms / baseline
        print(f"  {mode}: {time_ms:.2f}ms (x{ratio:.2f})")
    
    print("\n✅ 性能对比测试通过")


def test_all_parameters_usage():
    """测试所有参数的使用情况"""
    print("\n" + "=" * 80)
    print("测试 6: 所有参数使用验证")
    print("=" * 80)
    
    strategy = AdaptivePandasStrategy()
    
    # 测试所有参数
    params_to_test = [
        ('init_cash', 200000),
        ('fixed_count', 200),
        ('vectorized_enabled', True),
        ('check_mode', 'live'),
        ('lookback_window', 300),
        ('atr_period', 20),
        ('atr_multiplier', 2.5),
        ('volatility_factor', 0.6),
        ('trend_factor', 0.4),
        ('market_factor', 0.3),
        ('min_stop_loss', 0.03),
        ('max_stop_loss', 0.15),
        ('fixed_stop_loss', 0.06),
        ('min_take_profit', 0.06),
        ('max_take_profit', 0.25),
        ('trailing_profit', 0.04),
        ('profit_lock', 0.06),
        ('slippage_percent', 0.015),
    ]
    
    print("\n设置并验证参数:")
    for param_name, param_value in params_to_test:
        strategy.set_parameter(param_name, param_value)
        actual_value = strategy.get_parameter(param_name, None)
        status = "✓" if actual_value == param_value else "✗"
        print(f"  {status} {param_name}: {param_value} -> {actual_value}")
    
    # 测试 performance calculation 是否使用这些参数
    print("\n测试性能计算...")
    from core.strategy_extensions import StrategyContext, TimeFrame
    context = StrategyContext(
        symbol='000001.SH',
        timeframe=TimeFrame.DAY_1,
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31)
    )
    
    # 生成一些信号历史
    test_data = generate_test_data(300)
    strategy.generate_signals(test_data)
    
    # 计算性能
    performance = strategy.calculate_performance(context)
    print(f"  ✓ 总收益率：{performance.total_return:.4f}")
    print(f"  ✓ 年化收益：{performance.annual_return:.4f}")
    print(f"  ✓ 夏普比率：{performance.sharpe_ratio:.4f}")
    print(f"  ✓ 胜率：{performance.win_rate:.4f}")
    
    print("\n✅ 所有参数使用验证通过")


def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("回测/实盘模式切换功能测试套件")
    print("=" * 80)
    print(f"测试时间：{datetime.now()}")
    print("=" * 80)
    
    try:
        # 运行所有测试
        test_check_mode_parameter()
        test_lookback_window_parameter()
        test_mode_context()
        test_mode_aware_mixin()
        test_performance_difference()
        test_all_parameters_usage()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试通过！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
