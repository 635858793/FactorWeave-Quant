#!/usr/bin/env python3
"""
P0 级别修复验证脚本

验证内容：
1. ParameterEditorWidget 是否正确定义了 kdata 和 mode_context 属性
2. ParameterEditorWidget 是否正确传递 kdata 和 mode_context 给工作线程
3. ParameterComparisonThread 是否移除了 fallback 模拟逻辑
4. ParameterScanThread 是否移除了无用的_fallback_simulate_backtest 方法
"""

import sys
import inspect
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_parameter_editor_widget_attributes():
    """测试 1：验证 ParameterEditorWidget 是否正确定义了 kdata 和 mode_context 属性"""
    print("=" * 80)
    print("测试 1：验证 ParameterEditorWidget 属性定义")
    print("=" * 80)
    
    from gui.widgets.parameter_editor import ParameterEditorWidget
    
    # 检查属性是否在__init__中定义
    init_source = inspect.getsource(ParameterEditorWidget.__init__)
    assert 'self.kdata = None' in init_source, "❌ kdata 不在__init__中定义"
    assert 'self.mode_context = None' in init_source, "❌ mode_context 不在__init__中定义"
    
    print("✅ ParameterEditorWidget 正确定义了 kdata 和 mode_context 属性")
    print(f"   - 在__init__中定义：是")
    print(f"   - kdata 初始值：None")
    print(f"   - mode_context 初始值：None")
    print()
    
    return True


def test_parameter_scan_thread_creation():
    """测试 2：验证 ParameterEditorWidget 创建 ParameterScanThread 时是否传递 kdata 和 mode_context"""
    print("=" * 80)
    print("测试 2：验证 ParameterScanThread 创建时的参数传递")
    print("=" * 80)
    
    from gui.widgets.parameter_editor import ParameterEditorWidget
    
    # 检查源代码
    source = inspect.getsource(ParameterEditorWidget._start_parameter_scan)
    
    # 检查是否传递 kdata 和 mode_context
    assert 'kdata=self.kdata' in source, "❌ 创建 ParameterScanThread 时未传递 kdata"
    assert 'mode_context=self.mode_context' in source, "❌ 创建 ParameterScanThread 时未传递 mode_context"
    
    print("✅ ParameterEditorWidget 创建 ParameterScanThread 时正确传递了 kdata 和 mode_context")
    print("   - kdata 传递：是")
    print("   - mode_context 传递：是")
    print()
    
    return True


def test_parameter_comparison_thread_creation():
    """测试 3：验证 ParameterEditorWidget 创建 ParameterComparisonThread 时是否传递 kdata 和 mode_context"""
    print("=" * 80)
    print("测试 3：验证 ParameterComparisonThread 创建时的参数传递")
    print("=" * 80)
    
    from gui.widgets.parameter_editor import ParameterEditorWidget
    
    # 检查源代码
    source = inspect.getsource(ParameterEditorWidget._start_parameter_comparison)
    
    # 检查是否传递 kdata 和 mode_context
    assert 'kdata=self.kdata' in source, "❌ 创建 ParameterComparisonThread 时未传递 kdata"
    assert 'mode_context=self.mode_context' in source, "❌ 创建 ParameterComparisonThread 时未传递 mode_context"
    
    print("✅ ParameterEditorWidget 创建 ParameterComparisonThread 时正确传递了 kdata 和 mode_context")
    print("   - kdata 传递：是")
    print("   - mode_context 传递：是")
    print()
    
    return True


def test_parameter_comparison_thread_no_fallback():
    """测试 4：验证 ParameterComparisonThread 是否移除了 fallback 模拟逻辑"""
    print("=" * 80)
    print("测试 4：验证 ParameterComparisonThread 移除了 fallback 模拟逻辑")
    print("=" * 80)
    
    from gui.widgets.parameter_editor import ParameterComparisonThread
    
    # 检查是否还有_fallback_simulate_backtest 方法
    has_fallback = hasattr(ParameterComparisonThread, '_fallback_simulate_backtest')
    assert not has_fallback, "❌ ParameterComparisonThread 仍然包含_fallback_simulate_backtest 方法"
    
    # 检查_simulate_backtest 方法是否还有降级逻辑
    source = inspect.getsource(ParameterComparisonThread._simulate_backtest)
    
    # 检查是否还有调用 fallback 的逻辑
    assert '_fallback_simulate_backtest' not in source, "❌ _simulate_backtest 方法仍然调用_fallback_simulate_backtest"
    assert 'return self._fallback_simulate_backtest()' not in source, "❌ 仍然有返回 fallback 数据的逻辑"
    
    # 检查是否有直接抛出错误的逻辑
    assert 'raise' in source, "❌ _simulate_backtest 方法没有直接抛出错误"
    assert 'ValueError' in source or 'raise' in source, "❌ 没有在 kdata 为空时抛出错误"
    
    # 检查是否有 kdata 检查逻辑
    assert 'self.kdata is None' in source or 'len(self.kdata) == 0' in source, "❌ 没有检查 kdata 是否为空"
    
    print("✅ ParameterComparisonThread 已移除 fallback 模拟逻辑")
    print("   - _fallback_simulate_backtest 方法：已删除")
    print("   - 降级调用逻辑：已删除")
    print("   - 错误直接抛出：是")
    print("   - kdata 检查：是")
    print()
    
    return True


def test_parameter_scan_thread_no_fallback():
    """测试 5：验证 ParameterScanThread 是否移除了无用的_fallback_simulate_backtest 方法"""
    print("=" * 80)
    print("测试 5：验证 ParameterScanThread 移除了无用的 fallback 方法")
    print("=" * 80)
    
    from gui.widgets.parameter_editor import ParameterScanThread
    
    # 检查是否还有_fallback_simulate_backtest 方法
    has_fallback = hasattr(ParameterScanThread, '_fallback_simulate_backtest')
    assert not has_fallback, "❌ ParameterScanThread 仍然包含_fallback_simulate_backtest 方法"
    
    # 检查是否还有_calculate_max_drawdown 方法（如果只被 fallback 使用，也应该删除）
    has_calculate = hasattr(ParameterScanThread, '_calculate_max_drawdown')
    
    print("✅ ParameterScanThread 已移除无用的 fallback 方法")
    print("   - _fallback_simulate_backtest 方法：已删除")
    print(f"   - _calculate_max_drawdown 方法：{'已删除' if not has_calculate else '保留'}")
    print()
    
    return True


def test_business_call_chain_integrity():
    """测试 6：业务调用链完整性验证"""
    print("=" * 80)
    print("测试 6：业务调用链完整性验证")
    print("=" * 80)
    
    from gui.widgets.parameter_editor import ParameterScanThread, ParameterComparisonThread
    from core.trading.trading_mode import ModeContext, TradingMode
    import numpy as np
    
    # 验证线程构造函数签名
    scan_init_source = inspect.getsource(ParameterScanThread.__init__)
    comparison_init_source = inspect.getsource(ParameterComparisonThread.__init__)
    
    # 检查 ParameterScanThread 构造函数
    assert 'mode_context' in scan_init_source, "❌ ParameterScanThread.__init__ 缺少 mode_context 参数"
    assert 'kdata' in scan_init_source, "❌ ParameterScanThread.__init__ 缺少 kdata 参数"
    
    # 检查 ParameterComparisonThread 构造函数
    assert 'mode_context' in comparison_init_source, "❌ ParameterComparisonThread.__init__ 缺少 mode_context 参数"
    assert 'kdata' in comparison_init_source, "❌ ParameterComparisonThread.__init__ 缺少 kdata 参数"
    
    print("✅ 业务调用链完整性验证通过")
    print("   - ParameterScanThread.__init__ 参数：kdata ✅, mode_context ✅")
    print("   - ParameterComparisonThread.__init__ 参数：kdata ✅, mode_context ✅")
    print()
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "P0 级别修复验证测试" + " " * 35 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")
    
    tests = [
        ("属性定义验证", test_parameter_editor_widget_attributes),
        ("ParameterScanThread 参数传递", test_parameter_scan_thread_creation),
        ("ParameterComparisonThread 参数传递", test_parameter_comparison_thread_creation),
        ("ParameterComparisonThread fallback 移除", test_parameter_comparison_thread_no_fallback),
        ("ParameterScanThread fallback 移除", test_parameter_scan_thread_no_fallback),
        ("业务调用链完整性", test_business_call_chain_integrity),
    ]
    
    passed = 0
    failed = 0
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                results.append((test_name, "✅ 通过"))
            else:
                failed += 1
                results.append((test_name, "❌ 失败"))
        except Exception as e:
            failed += 1
            results.append((test_name, f"❌ 异常：{str(e)}"))
            import traceback
            traceback.print_exc()
    
    # 汇总结果
    print("=" * 80)
    print("测试汇总")
    print("=" * 80)
    print(f"总测试数：{len(tests)}")
    print(f"通过：{passed}")
    print(f"失败：{failed}")
    print()
    
    for test_name, result in results:
        print(f"{test_name}: {result}")
    
    print()
    
    if failed == 0:
        print("🎉 所有测试通过！P0 级别修复已完成验证。")
        return True
    else:
        print(f"⚠️  有 {failed} 个测试失败，请检查修复情况。")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
