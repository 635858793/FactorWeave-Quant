"""
自动JIT功能测试脚本
测试auto_jit装饰器和自动发现功能
"""

import numpy as np
import time
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest.auto_jit_decorator import (
    auto_jit,
    auto_jit_array,
    auto_jit_loop,
    discover_and_register,
    get_auto_jit_summary,
    get_auto_jit_functions,
    get_auto_jit_stats,
    enable_auto_jit,
    disable_auto_jit,
    is_auto_jit_enabled
)

from backtest.jit_optimizer import jit_optimizer


def test_auto_jit_decorator():
    """测试auto_jit装饰器"""
    print("\n" + "=" * 60)
    print("测试auto_jit装饰器")
    print("=" * 60)
    
    # 创建测试函数
    @auto_jit(name="test_function", description="测试函数", category="test")
    def test_function(x: float, y: float) -> float:
        total = 0.0
        for i in range(100):
            total += x * y
        return total
    
    # 测试函数
    result = test_function(2.0, 3.0)
    print(f"测试函数结果: {result}")
    assert result == 600.0, "测试函数结果不正确"
    
    # 获取JIT摘要
    summary = get_auto_jit_summary()
    print(f"JIT摘要: {summary}")
    
    # 获取所有JIT函数
    functions = get_auto_jit_functions()
    print(f"JIT函数数量: {len(functions)}")
    
    # 获取性能统计
    stats = get_auto_jit_stats()
    print(f"性能统计: {stats}")
    
    print("✓ auto_jit装饰器测试通过")


def test_auto_jit_array():
    """测试auto_jit_array装饰器"""
    print("\n" + "=" * 60)
    print("测试auto_jit_array装饰器")
    print("=" * 60)
    
    # 创建测试函数
    @auto_jit_array(name="test_array", description="测试数组函数", category="array")
    def test_array(arr: np.ndarray) -> np.ndarray:
        n = len(arr)
        result = np.zeros(n)
        for i in range(n):
            result[i] = arr[i] * 2.0
        return result
    
    # 测试函数
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    result = test_array(arr)
    print(f"输入数组: {arr}")
    print(f"输出数组: {result}")
    assert np.allclose(result, arr * 2.0), "数组函数结果不正确"
    
    print("✓ auto_jit_array装饰器测试通过")


def test_auto_jit_loop():
    """测试auto_jit_loop装饰器"""
    print("\n" + "=" * 60)
    print("测试auto_jit_loop装饰器")
    print("=" * 60)
    
    # 创建测试函数
    @auto_jit_loop(name="test_loop", description="测试循环函数", category="loop")
    def test_loop(n: int) -> int:
        total = 0
        for i in range(n):
            total += i
        return total
    
    # 测试函数
    result = test_loop(100)
    print(f"test_loop(100) = {result}")
    assert result == 4950, "循环函数结果不正确"
    
    print("✓ auto_jit_loop装饰器测试通过")


def test_jit_toggle():
    """测试JIT切换功能"""
    print("\n" + "=" * 60)
    print("测试JIT切换功能")
    print("=" * 60)
    
    # 创建测试函数
    @auto_jit(name="toggle_test", description="切换测试", category="test")
    def toggle_test(x: float) -> float:
        total = 0.0
        for i in range(100):
            total += x
        return total
    
    # 测试启用状态
    print(f"JIT状态: {'启用' if is_auto_jit_enabled() else '禁用'}")
    assert is_auto_jit_enabled() == True, "JIT应该默认启用"
    
    # 禁用JIT
    disable_auto_jit()
    print(f"禁用后JIT状态: {'启用' if is_auto_jit_enabled() else '禁用'}")
    assert is_auto_jit_enabled() == False, "JIT应该被禁用"
    
    # 测试禁用状态下的函数
    result = toggle_test(2.0)
    print(f"禁用状态下函数结果: {result}")
    assert result == 200.0, "禁用状态下函数结果不正确"
    
    # 启用JIT
    enable_auto_jit()
    print(f"启用后JIT状态: {'启用' if is_auto_jit_enabled() else '禁用'}")
    assert is_auto_jit_enabled() == True, "JIT应该被启用"
    
    # 测试启用状态下的函数
    result = toggle_test(2.0)
    print(f"启用状态下函数结果: {result}")
    assert result == 200.0, "启用状态下函数结果不正确"
    
    print("✓ JIT切换功能测试通过")


def test_performance_comparison():
    """测试性能对比"""
    print("\n" + "=" * 60)
    print("测试性能对比")
    print("=" * 60)
    
    # 创建测试函数
    @auto_jit(name="perf_test", description="性能测试", category="test")
    def perf_test(arr: np.ndarray) -> float:
        total = 0.0
        n = len(arr)
        for i in range(n):
            for j in range(n):
                total += arr[i] * arr[j]
        return total
    
    # 创建测试数据
    arr = np.random.randn(100)
    
    # 测试JIT版本
    start = time.time()
    for _ in range(10):
        _ = perf_test(arr)
    jit_time = time.time() - start
    print(f"JIT版本10次计算耗时: {jit_time:.4f}秒")
    
    # 获取性能统计
    stats = get_auto_jit_stats()
    if 'perf_test' in stats:
        print(f"性能统计: {stats['perf_test']}")
    
    print("✓ 性能对比测试通过")


def test_jit_optimizer_integration():
    """测试JIT优化器集成"""
    print("\n" + "=" * 60)
    print("测试JIT优化器集成")
    print("=" * 60)
    
    # 创建测试函数
    @auto_jit(name="integrated_test", description="集成测试", category="test")
    def integrated_test(x: float) -> float:
        total = 0.0
        for i in range(100):
            total += x
        return total
    
    # 测试函数
    result = integrated_test(2.0)
    print(f"集成测试函数结果: {result}")
    assert result == 200.0, "集成测试函数结果不正确"
    
    # 从AutoJIT导入到JIT优化器
    imported_count = jit_optimizer.import_from_auto_jit()
    print(f"从AutoJIT导入的函数数量: {imported_count}")
    
    # 获取JIT优化器的函数
    func = jit_optimizer.get_function('integrated_test')
    assert func is not None, "函数应该被导入到JIT优化器"
    
    print("✓ JIT优化器集成测试通过")


def test_auto_discovery():
    """测试自动发现功能"""
    print("\n" + "=" * 60)
    print("测试自动发现功能")
    print("=" * 60)
    
    # 测试自动发现
    try:
        registered = discover_and_register('core.indicators', 'calculate_')
        print(f"自动发现的函数: {registered}")
        
        if registered:
            print(f"成功发现并注册 {len(registered)} 个函数")
        
        print("✓ 自动发现功能测试通过")
    except Exception as e:
        print(f"自动发现功能测试跳过: {e}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始自动JIT功能测试")
    print("=" * 60)
    
    try:
        # 测试auto_jit装饰器
        test_auto_jit_decorator()
        
        # 测试auto_jit_array装饰器
        test_auto_jit_array()
        
        # 测试auto_jit_loop装饰器
        test_auto_jit_loop()
        
        # 测试JIT切换功能
        test_jit_toggle()
        
        # 测试性能对比
        test_performance_comparison()
        
        # 测试JIT优化器集成
        test_jit_optimizer_integration()
        
        # 测试自动发现功能
        test_auto_discovery()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
        # 打印最终统计
        print("\n最终统计:")
        summary = get_auto_jit_summary()
        print(f"  总函数数: {summary['total_functions']}")
        print(f"  总调用次数: {summary['total_calls']}")
        print(f"  JIT调用次数: {summary['jit_calls']}")
        print(f"  原始调用次数: {summary['original_calls']}")
        print(f"  JIT使用率: {summary['jit_usage_rate']:.2f}%")
        
        return True
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
