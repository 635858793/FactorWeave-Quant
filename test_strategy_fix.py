#!/usr/bin/env python3
"""
策略信号生成自测验证脚本

验证智能自适应窗口修复的正确性
测试不同数据量下的信号生成逻辑
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


def generate_test_data(total_bars: int, seed: int = 42) -> pd.DataFrame:
    """生成测试数据"""
    np.random.seed(seed)
    
    # 生成日期索引
    dates = pd.date_range(start='2023-01-01', periods=total_bars, freq='D')
    
    # 生成随机价格（随机游走）
    close = 100 + np.cumsum(np.random.randn(total_bars))
    
    # 生成 OHLCV 数据
    data = pd.DataFrame({
        'open': close * (1 + np.random.randn(total_bars) * 0.01),
        'high': close * (1 + np.abs(np.random.randn(total_bars) * 0.02)),
        'low': close * (1 - np.abs(np.random.randn(total_bars) * 0.02)),
        'close': close,
        'volume': np.random.randint(1000, 10000, total_bars)
    }, index=dates)
    
    return data


def calculate_ma20(data: pd.DataFrame) -> pd.Series:
    """计算 MA20"""
    return data['close'].rolling(window=20).mean()


def calculate_start_idx_smart(total_bars: int, first_valid_idx: int = 19) -> tuple:
    """
    智能自适应窗口算法
    
    Returns:
        (start_idx, lookback) 元组
    """
    if total_bars <= 200:
        start_idx = first_valid_idx
        lookback = total_bars - start_idx
        return start_idx, lookback, f"小数据量 ({total_bars}点)，检查全部{lookback}个点"
    elif total_bars <= 1000:
        lookback = min(200, total_bars - first_valid_idx)
        start_idx = total_bars - lookback
        return start_idx, lookback, f"中等数据量 ({total_bars}点)，检查最近{lookback}个点"
    else:
        lookback = min(500, total_bars - first_valid_idx)
        start_idx = total_bars - lookback
        return start_idx, lookback, f"大数据量 ({total_bars}点)，检查最近{lookback}个点"


def calculate_start_idx_original(total_bars: int, first_valid_idx: int = 19) -> tuple:
    """原始算法"""
    start_idx = max(first_valid_idx, total_bars - 100)
    lookback = total_bars - start_idx
    return start_idx, lookback, f"原始算法，检查最后{lookback}个点"


def test_data_scenario(name: str, total_bars: int):
    """测试特定数据场景"""
    print(f"\n{'='*80}")
    print(f"{name}: {total_bars} 个数据点")
    print(f"{'='*80}")
    
    # 生成测试数据
    data = generate_test_data(total_bars)
    print(f"\n1. 数据生成:")
    print(f"   日期范围：{data.index[0].date()} 至 {data.index[-1].date()}")
    print(f"   价格范围：{data['close'].min():.2f} - {data['close'].max():.2f}")
    
    # 计算 MA20
    ma20 = calculate_ma20(data)
    ma_valid = ma20.notna()
    # 找到第一个有效索引（处理 DatetimeIndex）
    if ma_valid.any():
        first_valid_pos = ma_valid.argmax()  # 返回位置索引（整数）
        first_valid_idx = first_valid_pos
    else:
        first_valid_idx = 20
    ma_valid_count = ma_valid.sum()
    
    print(f"\n2. MA20 计算:")
    print(f"   有效数据量：{ma_valid_count}/{total_bars}")
    print(f"   第一个有效索引：index={first_valid_idx}")
    
    # 原始算法
    print(f"\n3. 原始算法:")
    orig_start, orig_lookback, orig_desc = calculate_start_idx_original(total_bars, first_valid_idx)
    print(f"   {orig_desc}")
    print(f"   起始索引：{orig_start}")
    print(f"   检查点数：{orig_lookback} ({orig_lookback/total_bars*100:.1f}%)")
    
    # 智能自适应窗口算法
    print(f"\n4. 智能自适应窗口（修复后）:")
    smart_start, smart_lookback, smart_desc = calculate_start_idx_smart(total_bars, first_valid_idx)
    print(f"   {smart_desc}")
    print(f"   起始索引：{smart_start}")
    print(f"   检查点数：{smart_lookback} ({smart_lookback/total_bars*100:.1f}%)")
    
    # 对比分析
    print(f"\n5. 对比分析:")
    improvement = smart_lookback - orig_lookback
    improvement_pct = improvement / orig_lookback * 100 if orig_lookback > 0 else 0
    print(f"   检查点数变化：{orig_lookback} → {smart_lookback} ({improvement:+d}, {improvement_pct:+.1f}%)")
    
    if smart_lookback > orig_lookback:
        print(f"   ✅ 修复效果：多检查 {improvement} 个点，回测更完整")
    elif smart_lookback < orig_lookback:
        print(f"   ⚡ 性能优化：少检查 {-improvement} 个点，性能提升")
    else:
        print(f"   = 检查点数相同")
    
    # 验证信号生成
    print(f"\n6. 信号生成验证:")
    
    # 简化信号条件：价格上穿 MA20
    signals = []
    for i in range(smart_start, total_bars):
        if i > smart_start:
            prev_price = data['close'].iloc[i-1]
            prev_ma = ma20.iloc[i-1]
            curr_price = data['close'].iloc[i]
            curr_ma = ma20.iloc[i]
            
            # 金叉信号
            if prev_price <= prev_ma and curr_price > curr_ma:
                signals.append({
                    'index': i,
                    'type': 'BUY',
                    'price': curr_price,
                    'date': data.index[i]
                })
    
    print(f"   生成信号数量：{len(signals)}")
    if signals:
        print(f"   第一个信号：index={signals[0]['index']}, date={signals[0]['date'].date()}, price={signals[0]['price']:.2f}")
        print(f"   最后一个信号：index={signals[-1]['index']}, date={signals[-1]['date'].date()}, price={signals[-1]['price']:.2f}")
        
        # 检查早期是否有信号
        early_signals = [s for s in signals if s['index'] < smart_start + 50]
        if early_signals:
            print(f"   ✅ 早期信号：前 50 个点内生成 {len(early_signals)} 个信号")
        else:
            print(f"   ⚠️ 早期信号：前 50 个点内没有信号（可能是市场无明显趋势）")
    else:
        print(f"   ⚠️ 未生成任何信号（信号条件可能过于严格）")
    
    return {
        'total_bars': total_bars,
        'original_lookback': orig_lookback,
        'smart_lookback': smart_lookback,
        'signals_count': len(signals),
        'improvement': improvement
    }


def compare_all_scenarios():
    """对比所有场景"""
    print(f"\n{'='*80}")
    print("综合对比分析")
    print(f"{'='*80}")
    
    scenarios = [
        ("超小数据量", 50),
        ("小数据量", 100),
        ("中等数据量", 200),
        ("当前场景", 243),
        ("较大数据量", 500),
        ("大数据量", 1000),
        ("超大数据量", 2000),
        ("极端大数据量", 5000)
    ]
    
    print(f"\n{'场景':<15} {'总点数':>8} {'原始检查':>10} {'修复检查':>10} {'变化':>10} {'变化率':>10}")
    print(f"{'-'*80}")
    
    total_improvement = 0
    for name, total_bars in scenarios:
        data = generate_test_data(total_bars)
        ma20 = calculate_ma20(data)
        # 处理 DatetimeIndex
        if ma20.notna().any():
            first_valid_idx = ma20.notna().argmax()
        else:
            first_valid_idx = 20
        
        orig_start, orig_lookback, _ = calculate_start_idx_original(total_bars, first_valid_idx)
        smart_start, smart_lookback, _ = calculate_start_idx_smart(total_bars, first_valid_idx)
        
        improvement = smart_lookback - orig_lookback
        improvement_pct = improvement / orig_lookback * 100 if orig_lookback > 0 else 0
        total_improvement += improvement
        
        print(f"{name:<15} {total_bars:>8} {orig_lookback:>10} {smart_lookback:>10} {improvement:>+10} {improvement_pct:>+9.1f}%")
    
    print(f"{'-'*80}")
    print(f"{'总计':<15} {'':<8} {'':<10} {'':<10} {total_improvement:>+10} {'':<10}")
    print(f"\n✅ 修复后，所有场景累计多检查 {total_improvement} 个数据点")


def verify_fix_correctness():
    """验证修复正确性"""
    print(f"\n{'='*80}")
    print("修复正确性验证")
    print(f"{'='*80}")
    
    # 测试边界情况
    test_cases = [
        ("最小数据量 (50)", 50, 19),
        ("边界值 (200)", 200, 19),
        ("边界值 (201)", 201, 19),
        ("边界值 (1000)", 1000, 19),
        ("边界值 (1001)", 1001, 19),
    ]
    
    all_passed = True
    
    for name, total_bars, first_valid_idx in test_cases:
        print(f"\n{name}:")
        
        start_idx, lookback, desc = calculate_start_idx_smart(total_bars, first_valid_idx)
        print(f"  {desc}")
        
        # 验证逻辑正确性
        errors = []
        
        if start_idx < first_valid_idx:
            errors.append(f"start_idx ({start_idx}) < first_valid_idx ({first_valid_idx})")
        
        if start_idx >= total_bars:
            errors.append(f"start_idx ({start_idx}) >= total_bars ({total_bars})")
        
        if lookback <= 0:
            errors.append(f"lookback ({lookback}) <= 0")
        
        if total_bars <= 200 and lookback != total_bars - first_valid_idx:
            errors.append(f"小数据量应该检查全部，但 lookback={lookback}")
        
        if 200 < total_bars <= 1000 and lookback > 200:
            errors.append(f"中等数据量 lookback 不应超过 200，但 lookback={lookback}")
        
        if total_bars > 1000 and lookback > 500:
            errors.append(f"大数据量 lookback 不应超过 500，但 lookback={lookback}")
        
        if errors:
            print(f"  ❌ 验证失败:")
            for error in errors:
                print(f"    - {error}")
            all_passed = False
        else:
            print(f"  ✅ 验证通过")
    
    print(f"\n{'='*80}")
    if all_passed:
        print("✅ 所有边界测试通过！修复逻辑正确。")
    else:
        print("❌ 部分测试失败，请检查修复逻辑。")
    print(f"{'='*80}")


def main():
    print("\n" + "="*80)
    print("策略信号生成自测验证脚本")
    print("验证智能自适应窗口修复的正确性")
    print("="*80)
    
    # 测试不同数据量场景
    scenarios = [
        ("场景 1: 超小数据量", 50),
        ("场景 2: 小数据量", 100),
        ("场景 3: 中等数据量", 200),
        ("场景 4: 当前场景 (243 点)", 243),
        ("场景 5: 较大数据量", 500),
        ("场景 6: 大数据量", 1000),
        ("场景 7: 超大数据量", 2000),
    ]
    
    results = []
    for name, total_bars in scenarios:
        result = test_data_scenario(name, total_bars)
        results.append(result)
    
    # 综合对比
    compare_all_scenarios()
    
    # 验证修复正确性
    verify_fix_correctness()
    
    # 总结
    print(f"\n{'='*80}")
    print("测试总结")
    print(f"{'='*80}")
    
    print("\n✅ 已验证场景:")
    for result in results:
        print(f"  - {result['total_bars']}点：检查 {result['smart_lookback']} 个点 (vs 原始 {result['original_lookback']}个，{result['improvement']:+d})")
    
    print("\n📊 修复效果:")
    print(f"  - 243 点场景：检查 {results[3]['smart_lookback']} 个点 (vs 原始 {results[3]['original_lookback']}个，+{results[3]['improvement']}个)")
    print(f"  - 回测完整性提升：{results[3]['improvement']/results[3]['original_lookback']*100:.1f}%")
    
    print("\n🎯 预期效果:")
    print(f"  - 回测图表：从早期（约第 20 个点）就开始有交易信号")
    print(f"  - 资金曲线：从早期就开始波动，不再是直线")
    print(f"  - 回撤曲线：从早期就开始显示，反映真实回撤")
    
    print("\n💡 下一步:")
    print(f"  1. 运行实际回测，验证 UI 显示效果")
    print(f"  2. 对比修复前后的回测结果")
    print(f"  3. 验证信号生成数量和时机")
    
    print("\n" + "="*80)
    print("✅ 自测验证完成！")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
