#!/usr/bin/env python3
"""
验证策略签名和调用逻辑的正确性
"""

import sys
import inspect
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("策略签名验证")
print("=" * 80)
print()

# 策略列表
strategies = {
    'adaptive_strategy': ('plugins.strategies.adaptive_strategy', 'AdaptivePandasStrategy'),
    'moving_average': ('plugins.strategies.moving_average_strategy', 'MovingAverageStrategyPlugin'),
    'mean_reversion': ('plugins.strategies.mean_reversion_strategy', 'MeanReversionStrategyPlugin'),
    'vwap_reversion': ('plugins.strategies.vwap_reversion_plugin', 'VWAPReversionPlugin'),
    'adj_momentum': ('plugins.strategies.adj_momentum_plugin', 'AdjustedMomentumStrategyPlugin'),
    'trend_following': ('plugins.strategies.trend_following', 'TrendFollowingStrategy'),
    'breakout': ('plugins.strategies.trend_following', 'BreakoutStrategy'),
    'momentum': ('plugins.strategies.trend_following', 'MomentumStrategy'),
    'adaptive_trend': ('plugins.strategies.trend_following', 'AdaptiveTrendStrategy'),
}

print("检查策略签名：")
print("-" * 80)

results = []

for strategy_key, (module_name, class_name) in strategies.items():
    try:
        # 导入模块
        module = __import__(module_name, fromlist=[class_name])
        strategy_class = getattr(module, class_name)
        
        # 创建实例
        instance = strategy_class()
        
        # 获取 generate_signals 方法的签名
        sig = inspect.signature(instance.generate_signals)
        params = list(sig.parameters.keys())  # 不包含 self
        
        # 分析参数
        param_count = len(params)
        param_names = ', '.join(params) if params else '无'
        
        # 判断调用方式
        if param_count == 1:
            call_method = "generate_signals(data)"
            expected_params = 1
        elif param_count == 2:
            call_method = "generate_signals(data, context)"
            expected_params = 2
        else:
            call_method = f"未知签名：{param_names}"
            expected_params = param_count
        
        # 检查策略服务调用逻辑
        # 当前逻辑：if len(params) >= 3: call(data, context) else: call(data)
        if expected_params == 2:
            # 2 参数的策略会被错误地调用为 1 参数
            would_fail = "❌ 会失败（需要异常回退）"
        else:
            would_fail = "✅ 正确"
        
        result = {
            'key': strategy_key,
            'class': class_name,
            'params': param_count,
            'param_names': param_names,
            'call_method': call_method,
            'status': would_fail
        }
        results.append(result)
        
        print(f"{strategy_key:20} | {class_name:40} | 参数：{param_count} | {call_method:40} | {would_fail}")
        
    except Exception as e:
        print(f"{strategy_key:20} | 错误：{e}")
        results.append({
            'key': strategy_key,
            'error': str(e)
        })

print()
print("=" * 80)
print("策略服务调用逻辑分析")
print("=" * 80)
print()

print("当前策略服务逻辑：")
print("```python")
print("if len(params) >= 3:")
print("    return plugin.generate_signals(market_data_df, context)")
print("else:")
print("    return plugin.generate_signals(market_data_df)")
print("```")
print()

print("问题分析：")
print("-" * 80)

# 统计
two_param_strategies = [r for r in results if r.get('params') == 2]
one_param_strategies = [r for r in results if r.get('params') == 1]

print(f"2 个参数的策略（需要 context）：{len(two_param_strategies)} 个")
for r in two_param_strategies:
    print(f"  - {r['key']}: {r['call_method']}")

print()
print(f"1 个参数的策略（不需要 context）：{len(one_param_strategies)} 个")
for r in one_param_strategies:
    print(f"  - {r['key']}: {r['call_method']}")

print()
print("结论：")
print("-" * 80)

if two_param_strategies:
    print("⚠️  警告：发现 2 个参数的策略，当前调用逻辑会导致 TypeError")
    print("   但异常处理会捕获错误并尝试正确的调用方式")
    print("   建议修复调用逻辑以提高效率和代码质量")
else:
    print("✅ 所有策略都是 1 个参数，调用逻辑正确")

print()
print("=" * 80)
print("验证完成")
print("=" * 80)
