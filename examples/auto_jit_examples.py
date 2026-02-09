"""
使用auto_jit装饰器的示例
展示如何使用auto_jit装饰器来自动优化函数
"""

import numpy as np
from backtest.auto_jit_decorator import (
    auto_jit,
    auto_jit_array,
    auto_jit_loop,
    get_auto_jit_summary,
    get_auto_jit_functions,
    get_auto_jit_stats,
    enable_auto_jit,
    disable_auto_jit,
    is_auto_jit_enabled
)


# 示例1：基本使用
@auto_jit()
def simple_add(x: float, y: float) -> float:
    """简单的加法函数"""
    return x + y


# 示例2：带参数的装饰器
@auto_jit(
    name="my_multiply",
    description="乘法计算",
    category="math"
)
def multiply(a: float, b: float) -> float:
    """乘法函数"""
    return a * b


# 示例3：数组操作（使用auto_jit_array）
@auto_jit_array(
    name="vector_add",
    description="向量加法",
    category="array"
)
def vector_add(arr1: np.ndarray, arr2: np.ndarray) -> np.ndarray:
    """向量加法"""
    n = len(arr1)
    result = np.zeros(n)
    for i in range(n):
        result[i] = arr1[i] + arr2[i]
    return result


# 示例4：循环密集型操作（使用auto_jit_loop）
@auto_jit_loop(
    name="compute_sum",
    description="计算数组总和",
    category="loop"
)
def compute_sum(arr: np.ndarray) -> float:
    """计算数组总和"""
    total = 0.0
    for i in range(len(arr)):
        total += arr[i]
    return total


# 示例5：技术指标计算
@auto_jit(
    name="custom_sma",
    description="自定义简单移动平均",
    category="技术指标"
)
def custom_sma(prices: np.ndarray, period: int) -> np.ndarray:
    """自定义简单移动平均"""
    n = len(prices)
    sma = np.zeros(n)
    
    for i in range(period - 1, n):
        total = 0.0
        for j in range(i - period + 1, i + 1):
            total += prices[j]
        sma[i] = total / period
    
    return sma


# 示例6：复杂计算
@auto_jit(
    name="compute_rsi_custom",
    description="自定义RSI计算",
    category="技术指标"
)
def compute_rsi_custom(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """自定义RSI计算"""
    n = len(prices)
    rsi = np.zeros(n)
    
    if n < period + 1:
        return rsi
    
    # 计算价格变化
    deltas = np.zeros(n - 1)
    for i in range(1, n):
        deltas[i - 1] = prices[i] - prices[i - 1]
    
    # 分离涨跌
    gains = np.zeros(n - 1)
    losses = np.zeros(n - 1)
    for i in range(n - 1):
        if deltas[i] > 0:
            gains[i] = deltas[i]
        else:
            losses[i] = -deltas[i]
    
    # 计算初始平均涨跌幅
    avg_gain = 0.0
    avg_loss = 0.0
    for i in range(period):
        avg_gain += gains[i]
        avg_loss += losses[i]
    avg_gain /= period
    avg_loss /= period
    
    # 计算RSI
    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi


# 示例7：批量计算
@auto_jit(
    name="batch_calculate_sma",
    description="批量计算多个周期的SMA",
    category="批量计算"
)
def batch_calculate_sma(prices: np.ndarray, periods: list) -> dict:
    """批量计算多个周期的SMA"""
    results = {}
    n = len(prices)
    
    for period in periods:
        sma = np.zeros(n)
        for i in range(period - 1, n):
            total = 0.0
            for j in range(i - period + 1, i + 1):
                total += prices[j]
            sma[i] = total / period
        results[period] = sma
    
    return results


def demonstrate_auto_jit():
    """演示auto_jit功能"""
    print("=" * 60)
    print("AutoJIT装饰器功能演示")
    print("=" * 60)
    
    # 检查JIT状态
    print(f"\nJIT优化状态: {'启用' if is_auto_jit_enabled() else '禁用'}")
    
    # 测试基本函数
    print("\n测试基本函数:")
    result = simple_add(10.0, 20.0)
    print(f"  simple_add(10.0, 20.0) = {result}")
    
    result = multiply(5.0, 6.0)
    print(f"  multiply(5.0, 6.0) = {result}")
    
    # 测试数组操作
    print("\n测试数组操作:")
    arr1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    arr2 = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    result = vector_add(arr1, arr2)
    print(f"  vector_add({arr1}, {arr2}) = {result}")
    
    # 测试循环操作
    print("\n测试循环操作:")
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    result = compute_sum(arr)
    print(f"  compute_sum({arr}) = {result}")
    
    # 测试技术指标
    print("\n测试技术指标:")
    prices = np.array([100.0, 101.0, 99.0, 102.0, 98.0, 103.0, 97.0, 104.0, 96.0, 105.0])
    sma = custom_sma(prices, 5)
    print(f"  SMA(5) = {sma}")
    
    rsi = compute_rsi_custom(prices, 5)
    print(f"  RSI(5) = {rsi}")
    
    # 测试批量计算
    print("\n测试批量计算:")
    periods = [3, 5, 7]
    results = batch_calculate_sma(prices, periods)
    print(f"  批量SMA计算:")
    for period, sma in results.items():
        print(f"    SMA({period}) = {sma}")
    
    # 获取JIT摘要
    print("\nJIT摘要:")
    summary = get_auto_jit_summary()
    print(f"  总函数数: {summary['total_functions']}")
    print(f"  总调用次数: {summary['total_calls']}")
    print(f"  JIT调用次数: {summary['jit_calls']}")
    print(f"  原始调用次数: {summary['original_calls']}")
    print(f"  JIT使用率: {summary['jit_usage_rate']:.2f}%")
    
    # 获取所有JIT函数
    print("\n所有JIT函数:")
    functions = get_auto_jit_functions()
    for name, info in functions.items():
        print(f"  {name}: {info['description']} ({info['category']})")
    
    # 获取性能统计
    print("\n性能统计:")
    stats = get_auto_jit_stats()
    for name, stat in stats.items():
        if stat['calls'] > 0:
            print(f"  {name}:")
            print(f"    调用次数: {stat['calls']}")
            print(f"    JIT调用: {stat['jit_calls']}")
            print(f"    原始调用: {stat['original_calls']}")
            print(f"    总时间: {stat['total_time']:.6f}秒")
            print(f"    JIT时间: {stat['jit_time']:.6f}秒")
            print(f"    原始时间: {stat['original_time']:.6f}秒")
    
    # 测试切换JIT
    print("\n测试切换JIT:")
    print("  禁用JIT...")
    disable_auto_jit()
    print(f"  JIT状态: {'启用' if is_auto_jit_enabled() else '禁用'}")
    
    result = simple_add(10.0, 20.0)
    print(f"  simple_add(10.0, 20.0) = {result}")
    
    print("  启用JIT...")
    enable_auto_jit()
    print(f"  JIT状态: {'启用' if is_auto_jit_enabled() else '禁用'}")
    
    result = simple_add(10.0, 20.0)
    print(f"  simple_add(10.0, 20.0) = {result}")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demonstrate_auto_jit()
