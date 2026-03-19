#!/usr/bin/env python3
"""测试策略信号生成"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from plugins.strategies.adaptive_strategy import AdaptivePandasStrategy

def generate_test_data(days=300):
    """生成测试数据"""
    # 生成日期索引
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq='B')  # 工作日
    
    # 生成模拟价格数据（随机游走）
    np.random.seed(42)
    returns = np.random.randn(len(dates)) * 0.02  # 日收益率
    price = 100 * (1 + returns).cumprod()
    
    # 生成 High, Low, Close, Volume
    data = pd.DataFrame({
        'open': price * (1 + np.random.randn(len(price)) * 0.01),
        'high': price * (1 + np.abs(np.random.randn(len(price)) * 0.015)),
        'low': price * (1 - np.abs(np.random.randn(len(price)) * 0.015)),
        'close': price,
        'volume': np.random.randint(1000000, 10000000, len(price))
    }, index=dates)
    
    return data

def test_strategy():
    """测试策略信号生成"""
    print("=" * 60)
    print("策略信号生成测试")
    print("=" * 60)
    
    # 生成测试数据
    print("\n1. 生成测试数据...")
    data = generate_test_data(300)
    print(f"   数据量：{len(data)}条")
    print(f"   日期范围：{data.index[0].date()} 至 {data.index[-1].date()}")
    print(f"   价格范围：{data['close'].min():.2f} - {data['close'].max():.2f}")
    
    # 创建策略实例
    print("\n2. 创建策略实例...")
    strategy = AdaptivePandasStrategy()
    print(f"   策略名称：{strategy.name}")
    
    # 生成信号
    print("\n3. 开始生成信号...")
    signals = strategy.generate_signals(data)
    
    print(f"\n4. 信号生成结果:")
    print(f"   总信号数：{len(signals)}")
    
    if signals:
        buy_signals = [s for s in signals if s.signal_type.name == 'BUY']
        sell_signals = [s for s in signals if s.signal_type.name == 'SELL']
        
        print(f"   买入信号：{len(buy_signals)}")
        print(f"   卖出信号：{len(sell_signals)}")
        
        # 显示前 5 个信号
        print(f"\n5. 前 5 个信号详情:")
        for i, signal in enumerate(signals[:5], 1):
            print(f"   信号{i}: {signal.timestamp.date()} | {signal.signal_type.name:4} | "
                  f"价格：{signal.price:.2f} | 置信度：{signal.confidence:.2f} | "
                  f"原因：{signal.reason}")
    else:
        print("   ⚠️  未生成任何信号！")
        print("   可能原因:")
        print("   1. 数据量不足（需要至少 50 条）")
        print("   2. 信号条件过于严格")
        print("   3. 市场无明显趋势")
        print("   4. 指标值不满足阈值")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return len(signals) > 0

if __name__ == "__main__":
    try:
        success = test_strategy()
        if success:
            print("\n✅ 测试通过：策略成功生成信号")
        else:
            print("\n❌ 测试失败：策略未生成任何信号")
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
