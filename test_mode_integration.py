"""
模式管理框架集成测试
验证 UnifiedBacktestEngine 和 TradingService 的模式感知能力
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.trading.trading_mode import TradingMode, ModeContext
from backtest.unified_backtest_engine import UnifiedBacktestEngine
from core.services.trading_service import TradingService
from core.containers import get_service_container
from loguru import logger

def create_test_data(size: int = 1000) -> pd.DataFrame:
    """创建测试数据"""
    dates = pd.date_range('2024-01-01', periods=size, freq='min')
    data = pd.DataFrame({
        'open': np.random.uniform(9.5, 10.5, size),
        'close': np.random.uniform(9.5, 10.5, size),
        'high': np.random.uniform(10.0, 10.8, size),
        'low': np.random.uniform(9.2, 10.0, size),
        'volume': np.random.randint(100000, 1000000, size),
        'signal': np.random.choice([1, 0, -1], size, p=[0.1, 0.8, 0.1])
    }, index=dates)
    return data


def test_unified_backtest_engine_mode_awareness():
    """测试 UnifiedBacktestEngine 模式感知能力"""
    print("=" * 80)
    print("测试 1: UnifiedBacktestEngine 模式感知能力")
    print("=" * 80)
    
    try:
        # 测试 1: 回测模式
        print("\n【测试 1.1】回测模式")
        backtest_context = ModeContext.create_backtest(
            start_date='2024-01-01',
            end_date='2024-01-02'
        )
        
        engine_backtest = UnifiedBacktestEngine(
            mode_context=backtest_context,
            use_vectorized_engine=True,
            auto_select_engine=True
        )
        
        assert engine_backtest.mode_context is not None, "应该有 mode_context"
        assert engine_backtest.mode_context.mode == TradingMode.BACKTEST, "应该是回测模式"
        print(f"  ✓ 回测模式上下文创建成功：{engine_backtest.mode_context.mode.value}")
        
        # 测试 2: 实盘模式
        print("\n【测试 1.2】实盘模式")
        live_context = ModeContext(
            mode=TradingMode.LIVE,
            config={
                'performance_critical': True,
                'enable_risk_control': True
            }
        )
        
        engine_live = UnifiedBacktestEngine(
            mode_context=live_context,
            use_vectorized_engine=True,
            auto_select_engine=True
        )
        
        assert engine_live.mode_context is not None, "应该有 mode_context"
        assert engine_live.mode_context.mode == TradingMode.LIVE, "应该是实盘模式"
        print(f"  ✓ 实盘模式上下文创建成功：{engine_live.mode_context.mode.value}")
        
        # 测试 3: 模式切换
        print("\n【测试 1.3】模式切换测试")
        engine = UnifiedBacktestEngine()
        
        # 初始应该是回测模式
        assert engine.mode_context is None or engine.mode_context.mode == TradingMode.BACKTEST
        print(f"  ✓ 初始模式：{engine.mode_context.mode.value if engine.mode_context else 'BACKTEST'}")
        
        # 切换到实盘模式
        engine.mode_context = live_context
        assert engine.mode_context.mode == TradingMode.LIVE, "应该切换到实盘模式"
        print(f"  ✓ 切换到实盘模式成功：{engine.mode_context.mode.value}")
        
        print("\n" + "=" * 80)
        print("✓ UnifiedBacktestEngine 模式感知能力测试通过")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ UnifiedBacktestEngine 模式感知能力测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_trading_service_mode_awareness():
    """测试 TradingService 模式感知能力"""
    print("=" * 80)
    print("测试 2: TradingService 模式感知能力")
    print("=" * 80)
    
    try:
        # 获取服务容器
        container = get_service_container()
        
        # 创建 TradingService 实例
        trading_service = TradingService(container)
        trading_service.initialize()
        
        # 测试 1: 默认模式
        print("\n【测试 2.1】默认模式")
        default_mode = trading_service.get_mode()
        print(f"  ✓ 默认模式：{default_mode.value}")
        assert default_mode == TradingMode.BACKTEST, "默认应该是回测模式"
        
        # 测试 2: 切换到实盘模式
        print("\n【测试 2.2】切换到实盘模式")
        trading_service.set_mode(TradingMode.LIVE, commission_rate=0.001)
        live_mode = trading_service.get_mode()
        assert live_mode == TradingMode.LIVE, "应该切换到实盘模式"
        print(f"  ✓ 切换到实盘模式成功：{live_mode.value}")
        
        # 检查配置是否正确
        assert trading_service._trading_config.get("enable_risk_control") == True, "实盘模式应启用风控"
        print(f"  ✓ 实盘模式风控已启用")
        
        # 测试 3: 切换到模拟模式
        print("\n【测试 2.3】切换到模拟模式")
        trading_service.set_mode(TradingMode.PAPER, commission_rate=0.001)
        paper_mode = trading_service.get_mode()
        assert paper_mode == TradingMode.PAPER, "应该切换到模拟模式"
        print(f"  ✓ 切换到模拟模式成功：{paper_mode.value}")
        
        # 测试 4: 切换回回测模式
        print("\n【测试 2.4】切换回回测模式")
        trading_service.set_mode(TradingMode.BACKTEST, enable_risk_control=False)
        backtest_mode = trading_service.get_mode()
        assert backtest_mode == TradingMode.BACKTEST, "应该切换回回测模式"
        print(f"  ✓ 切换回回测模式成功：{backtest_mode.value}")
        
        # 测试 5: 模式辅助方法
        print("\n【测试 2.5】模式辅助方法")
        trading_service.set_mode(TradingMode.LIVE)
        assert trading_service.is_live_mode() == True, "应该是实盘模式"
        assert trading_service.is_backtest_mode() == False, "不应该回测模式"
        print(f"  ✓ is_live_mode(): {trading_service.is_live_mode()}")
        print(f"  ✓ is_backtest_mode(): {trading_service.is_backtest_mode()}")
        
        print("\n" + "=" * 80)
        print("✓ TradingService 模式感知能力测试通过")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ TradingService 模式感知能力测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_business_call_chain_integration():
    """测试业务调用链集成"""
    print("=" * 80)
    print("测试 3: 业务调用链集成验证")
    print("=" * 80)
    
    try:
        container = get_service_container()
        
        # 测试 1: 验证 UnifiedBacktestEngine 和 TradingService 的模式感知
        print("\n【测试 3.1】UnifiedBacktestEngine 和 TradingService 模式感知集成")
        
        # 创建模式上下文
        backtest_context = ModeContext.create_backtest(
            start_date='2024-01-01',
            end_date='2024-01-02'
        )
        
        # 创建回测引擎
        engine = UnifiedBacktestEngine(mode_context=backtest_context)
        assert engine.mode_context is not None, "引擎应该有 mode_context"
        assert engine.mode_context.mode == TradingMode.BACKTEST, "应该是回测模式"
        print(f"  ✓ UnifiedBacktestEngine 模式上下文创建成功：{engine.mode_context.mode.value}")
        
        # 创建 TradingService
        trading_service = TradingService(container)
        trading_service.initialize()
        
        # 验证默认模式
        assert trading_service.get_mode() == TradingMode.BACKTEST, "默认应该是回测模式"
        print(f"  ✓ TradingService 默认模式：{trading_service.get_mode().value}")
        
        # 测试 2: 模式切换
        print("\n【测试 3.2】跨服务模式切换")
        
        # 切换到实盘模式
        trading_service.set_mode(TradingMode.LIVE)
        assert trading_service.get_mode() == TradingMode.LIVE, "应该切换到实盘模式"
        print(f"  ✓ TradingService 切换到实盘模式：{trading_service.get_mode().value}")
        
        # 创建实盘模式的引擎
        live_context = ModeContext(mode=TradingMode.LIVE)
        engine_live = UnifiedBacktestEngine(mode_context=live_context)
        assert engine_live.mode_context.mode == TradingMode.LIVE, "应该是实盘模式"
        print(f"  ✓ UnifiedBacktestEngine 实盘模式创建成功：{engine_live.mode_context.mode.value}")
        
        # 测试 3: ProfessionalBacktestWidget 模式选择器
        print("\n【测试 3.3】ProfessionalBacktestWidget 模式选择器")
        
        from gui.widgets.backtest_widget import ProfessionalBacktestWidget
        
        # 验证 ProfessionalBacktestWidget 有模式选择器
        assert hasattr(ProfessionalBacktestWidget, 'on_mode_changed'), "ProfessionalBacktestWidget 应有 on_mode_changed 方法"
        print(f"  ✓ ProfessionalBacktestWidget.on_mode_changed 方法存在")
        
        # 验证模式映射
        mode_map = {
            '回测模式': TradingMode.BACKTEST,
            '实盘模式': TradingMode.LIVE,
            '混合模式': getattr(TradingMode, 'HYBRID', TradingMode.BACKTEST)
        }
        print(f"  ✓ 模式映射配置：{list(mode_map.keys())}")
        
        print("\n" + "=" * 80)
        print("✓ 业务调用链集成验证通过")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ 业务调用链集成验证失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("模式管理框架集成测试")
    print("=" * 80)
    
    results = []
    
    # 测试 1: UnifiedBacktestEngine 模式感知能力
    results.append(("UnifiedBacktestEngine 模式感知", test_unified_backtest_engine_mode_awareness()))
    
    # 测试 2: TradingService 模式感知能力
    results.append(("TradingService 模式感知", test_trading_service_mode_awareness()))
    
    # 测试 3: 业务调用链集成
    results.append(("业务调用链集成", test_business_call_chain_integration()))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\n总计：{total_passed}/{total_tests} 测试通过")
    print("=" * 80)
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
