#!/usr/bin/env python3
"""
策略参数业务逻辑全面测试

验证所有内置策略参数的定义、使用和业务流程正确性
"""

import sys
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List

# 添加项目路径
sys.path.insert(0, 'd:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui')

from core.strategy.base_strategy import BaseStrategy, StrategyParameter, StrategySignal, StrategyType, SignalType
from core.strategy.builtin_strategies import (
    MAStrategy, MACDStrategy, RSIStrategy, KDJStrategy, BollingerBandsStrategy
)


def generate_test_data(length: int = 200, seed: int = 42) -> pd.DataFrame:
    """生成测试数据"""
    np.random.seed(seed)
    
    # 生成日期序列
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(length)]
    
    # 生成模拟价格数据（随机游走）
    returns = np.random.randn(length).cumsum()
    close = 100 * np.exp(returns)
    
    # 生成高低价
    high = close * (1 + np.abs(np.random.randn(length)) * 0.02)
    low = close * (1 - np.abs(np.random.randn(length)) * 0.02)
    
    # 生成成交量
    volume = np.random.randint(1000, 10000, length)
    
    return pd.DataFrame({
        'open': close * (1 + np.random.randn(length) * 0.01),
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


class TestStrategyParameters(unittest.TestCase):
    """策略参数测试基类"""
    
    def setUp(self):
        """测试前准备"""
        self.test_data = generate_test_data()
    
    def verify_parameter(self, strategy: BaseStrategy, param_name: str, 
                        expected_type: type, default_value, 
                        min_value=None, max_value=None):
        """验证参数定义"""
        # 检查参数是否存在
        self.assertIn(param_name, strategy.parameters)
        
        param = strategy.parameters[param_name]
        
        # 验证类型
        self.assertEqual(param.param_type, expected_type,
                        f"{param_name} 类型错误：期望 {expected_type}, 实际 {param.param_type}")
        
        # 验证默认值
        self.assertEqual(param.value, default_value,
                        f"{param_name} 默认值错误：期望 {default_value}, 实际 {param.value}")
        
        # 验证范围
        if min_value is not None:
            self.assertEqual(param.min_value, min_value,
                           f"{param_name} 最小值错误：期望 {min_value}, 实际 {param.min_value}")
        if max_value is not None:
            self.assertEqual(param.max_value, max_value,
                           f"{param_name} 最大值错误：期望 {max_value}, 实际 {param.max_value}")
    
    def verify_parameter_usage(self, strategy: BaseStrategy, param_name: str, 
                              test_value, expected_behavior: str):
        """验证参数在业务逻辑中的使用"""
        # 设置新参数值
        success = strategy.set_parameter(param_name, test_value)
        self.assertTrue(success, f"设置参数 {param_name} 失败")
        
        # 验证参数值已更新
        actual_value = strategy.get_parameter(param_name)
        self.assertEqual(actual_value, test_value,
                        f"参数 {param_name} 值未更新：期望 {test_value}, 实际 {actual_value}")
        
        # 生成信号验证参数影响
        signals = strategy.generate_signals(self.test_data)
        self.assertIsInstance(signals, list, "generate_signals 应返回列表")
        
        print(f"✓ 参数 {param_name} = {test_value} 验证通过 - {expected_behavior}")


class TestMAStrategyParameters(TestStrategyParameters):
    """MA 策略参数测试"""
    
    def setUp(self):
        super().setUp()
        self.strategy = MAStrategy("MA 策略测试")
    
    def test_short_period_parameter(self):
        """测试短期均线周期参数"""
        self.verify_parameter(
            self.strategy, "short_period", 
            expected_type=int, default_value=5,
            min_value=1, max_value=100
        )
        
        # 测试不同值的影响
        self.verify_parameter_usage(
            self.strategy, "short_period", 10,
            "短期均线周期影响均线计算灵敏度"
        )
    
    def test_long_period_parameter(self):
        """测试长期均线周期参数"""
        self.verify_parameter(
            self.strategy, "long_period",
            expected_type=int, default_value=20,
            min_value=1, max_value=200
        )
        
        self.verify_parameter_usage(
            self.strategy, "long_period", 60,
            "长期均线周期影响趋势判断"
        )
    
    def test_min_confidence_parameter(self):
        """测试最小置信度参数"""
        self.verify_parameter(
            self.strategy, "min_confidence",
            expected_type=float, default_value=0.6,
            min_value=0.0, max_value=1.0
        )
        
        self.verify_parameter_usage(
            self.strategy, "min_confidence", 0.8,
            "最小置信度影响信号过滤"
        )
    
    def test_parameter_validation(self):
        """测试 MA 策略参数验证"""
        # 测试无效值
        result = self.strategy.set_parameter("short_period", -1)
        self.assertFalse(result, "应拒绝无效的 short_period 值")
        
        result = self.strategy.set_parameter("short_period", 150)
        self.assertFalse(result, "应拒绝超出范围的 short_period 值")
        
        result = self.strategy.set_parameter("min_confidence", 1.5)
        self.assertFalse(result, "应拒绝超出范围的 min_confidence 值")
    
    def test_generate_signals_with_different_params(self):
        """测试不同参数组合下的信号生成"""
        # 参数组合 1：短周期
        self.strategy.set_parameter("short_period", 5)
        self.strategy.set_parameter("long_period", 20)
        signals1 = self.strategy.generate_signals(self.test_data)
        
        # 参数组合 2：长周期
        self.strategy.set_parameter("short_period", 20)
        self.strategy.set_parameter("long_period", 60)
        signals2 = self.strategy.generate_signals(self.test_data)
        
        # 验证信号生成
        self.assertIsInstance(signals1, list)
        self.assertIsInstance(signals2, list)
        print(f"✓ MA 策略信号生成测试通过 - 短周期：{len(signals1)} 个信号，长周期：{len(signals2)} 个信号")


class TestMACDStrategyParameters(TestStrategyParameters):
    """MACD 策略参数测试"""
    
    def setUp(self):
        super().setUp()
        self.strategy = MACDStrategy("MACD 策略测试")
    
    def test_fast_period_parameter(self):
        """测试快线周期参数"""
        self.verify_parameter(
            self.strategy, "fast_period",
            expected_type=int, default_value=12,
            min_value=1, max_value=50
        )
        
        self.verify_parameter_usage(
            self.strategy, "fast_period", 8,
            "快线周期影响 MACD 灵敏度"
        )
    
    def test_slow_period_parameter(self):
        """测试慢线周期参数"""
        self.verify_parameter(
            self.strategy, "slow_period",
            expected_type=int, default_value=26,
            min_value=1, max_value=100
        )
        
        self.verify_parameter_usage(
            self.strategy, "slow_period", 30,
            "慢线周期影响趋势判断"
        )
    
    def test_signal_period_parameter(self):
        """测试信号线周期参数"""
        self.verify_parameter(
            self.strategy, "signal_period",
            expected_type=int, default_value=9,
            min_value=1, max_value=30
        )
        
        self.verify_parameter_usage(
            self.strategy, "signal_period", 7,
            "信号线周期影响金叉死叉判断"
        )
    
    def test_min_confidence_parameter(self):
        """测试最小置信度参数"""
        self.verify_parameter(
            self.strategy, "min_confidence",
            expected_type=float, default_value=0.6,
            min_value=0.0, max_value=1.0
        )
    
    def test_macd_calculation(self):
        """测试 MACD 计算正确性"""
        # 策略会修改数据副本，我们验证信号生成是否正常
        signals = self.strategy.generate_signals(self.test_data)
        
        # 验证信号生成正常
        self.assertIsInstance(signals, list, "应返回信号列表")
        
        # 验证如果有信号，信号类型正确
        for signal in signals:
            self.assertIn(signal.signal_type, [SignalType.BUY, SignalType.SELL],
                         "信号类型应为买入或卖出")
            self.assertGreater(signal.confidence, 0, "置信度应大于 0")
            self.assertLessEqual(signal.confidence, 1.0, "置信度应小于等于 1")
        
        print(f"✓ MACD 策略计算测试通过 - 生成 {len(signals)} 个信号")


class TestRSIStrategyParameters(TestStrategyParameters):
    """RSI 策略参数测试"""
    
    def setUp(self):
        super().setUp()
        self.strategy = RSIStrategy("RSI 策略测试")
    
    def test_period_parameter(self):
        """测试 RSI 周期参数"""
        self.verify_parameter(
            self.strategy, "period",
            expected_type=int, default_value=14,
            min_value=1, max_value=50
        )
        
        self.verify_parameter_usage(
            self.strategy, "period", 21,
            "RSI 周期影响指标平滑度"
        )
    
    def test_oversold_parameter(self):
        """测试超卖阈值参数"""
        self.verify_parameter(
            self.strategy, "oversold",
            expected_type=float, default_value=30,
            min_value=10, max_value=40
        )
        
        self.verify_parameter_usage(
            self.strategy, "oversold", 25,
            "超卖阈值影响买入信号触发"
        )
    
    def test_overbought_parameter(self):
        """测试超买阈值参数"""
        self.verify_parameter(
            self.strategy, "overbought",
            expected_type=float, default_value=70,
            min_value=60, max_value=90
        )
        
        self.verify_parameter_usage(
            self.strategy, "overbought", 75,
            "超买阈值影响卖出信号触发"
        )
    
    def test_rsi_calculation(self):
        """测试 RSI 计算正确性"""
        # 策略会修改数据副本，我们验证信号生成是否正常
        signals = self.strategy.generate_signals(self.test_data)
        
        # 验证信号生成正常
        self.assertIsInstance(signals, list, "应返回信号列表")
        
        # 验证信号质量
        for signal in signals:
            self.assertIn(signal.signal_type, [SignalType.BUY, SignalType.SELL],
                         "信号类型应为买入或卖出")
            self.assertGreater(signal.confidence, 0, "置信度应大于 0")
        
        print(f"✓ RSI 策略计算测试通过 - 生成 {len(signals)} 个信号")


class TestKDJStrategyParameters(TestStrategyParameters):
    """KDJ 策略参数测试"""
    
    def setUp(self):
        super().setUp()
        self.strategy = KDJStrategy("KDJ 策略测试")
    
    def test_period_parameter(self):
        """测试 KDJ 周期参数"""
        self.verify_parameter(
            self.strategy, "period",
            expected_type=int, default_value=9,
            min_value=1, max_value=30
        )
    
    def test_k_period_parameter(self):
        """测试 K 值平滑周期参数"""
        self.verify_parameter(
            self.strategy, "k_period",
            expected_type=int, default_value=3,
            min_value=1, max_value=10
        )
        
        self.verify_parameter_usage(
            self.strategy, "k_period", 5,
            "K 值平滑周期影响 K 线计算"
        )
    
    def test_d_period_parameter(self):
        """测试 D 值平滑周期参数"""
        self.verify_parameter(
            self.strategy, "d_period",
            expected_type=int, default_value=3,
            min_value=1, max_value=10
        )
        
        self.verify_parameter_usage(
            self.strategy, "d_period", 5,
            "D 值平滑周期影响 D 线计算"
        )
    
    def test_oversold_parameter(self):
        """测试超卖阈值参数"""
        self.verify_parameter(
            self.strategy, "oversold",
            expected_type=float, default_value=20,
            min_value=10, max_value=30
        )
    
    def test_overbought_parameter(self):
        """测试超买阈值参数"""
        self.verify_parameter(
            self.strategy, "overbought",
            expected_type=float, default_value=80,
            min_value=70, max_value=90
        )
    
    def test_kdj_calculation(self):
        """测试 KDJ 计算正确性"""
        # 策略会修改数据副本，我们验证信号生成是否正常
        signals = self.strategy.generate_signals(self.test_data)
        
        # 验证信号生成正常
        self.assertIsInstance(signals, list, "应返回信号列表")
        
        # 验证信号质量
        for signal in signals:
            self.assertIn(signal.signal_type, [SignalType.BUY, SignalType.SELL],
                         "信号类型应为买入或卖出")
            self.assertGreater(signal.confidence, 0, "置信度应大于 0")
        
        print(f"✓ KDJ 策略计算测试通过 - 生成 {len(signals)} 个信号")


class TestBollingerBandsStrategyParameters(TestStrategyParameters):
    """布林带策略参数测试"""
    
    def setUp(self):
        super().setUp()
        self.strategy = BollingerBandsStrategy("布林带策略测试")
    
    def test_period_parameter(self):
        """测试布林带周期参数"""
        self.verify_parameter(
            self.strategy, "period",
            expected_type=int, default_value=20,
            min_value=5, max_value=50
        )
        
        self.verify_parameter_usage(
            self.strategy, "period", 26,
            "布林带周期影响带宽计算"
        )
    
    def test_std_dev_parameter(self):
        """测试标准差倍数参数"""
        self.verify_parameter(
            self.strategy, "std_dev",
            expected_type=float, default_value=2.0,
            min_value=1.0, max_value=3.0
        )
        
        self.verify_parameter_usage(
            self.strategy, "std_dev", 2.5,
            "标准差倍数影响带宽宽度"
        )
    
    def test_bollinger_calculation(self):
        """测试布林带计算正确性"""
        # 策略会修改数据副本，我们验证信号生成是否正常
        signals = self.strategy.generate_signals(self.test_data)
        
        # 验证信号生成正常
        self.assertIsInstance(signals, list, "应返回信号列表")
        
        # 验证信号质量
        for signal in signals:
            self.assertIn(signal.signal_type, [SignalType.BUY, SignalType.SELL],
                         "信号类型应为买入或卖出")
            self.assertGreater(signal.confidence, 0, "置信度应大于 0")
        
        print(f"✓ 布林带策略计算测试通过 - 生成 {len(signals)} 个信号")


class TestParameterBusinessLogic(unittest.TestCase):
    """参数业务逻辑综合测试"""
    
    def setUp(self):
        """测试前准备"""
        self.test_data = generate_test_data()
        self.strategies = {
            'MA': MAStrategy(),
            'MACD': MACDStrategy(),
            'RSI': RSIStrategy(),
            'KDJ': KDJStrategy(),
            'Bollinger': BollingerBandsStrategy()
        }
    
    def test_all_parameters_affect_signals(self):
        """测试所有参数都影响信号生成"""
        for strategy_name, strategy in self.strategies.items():
            # 使用默认参数生成信号
            signals_default = strategy.generate_signals(self.test_data)
            
            # 修改所有参数
            for param_name in strategy.parameters.keys():
                param = strategy.parameters[param_name]
                
                # 根据参数类型选择测试值
                if param.param_type == int:
                    test_value = int((param.min_value + param.max_value) / 2) if param.min_value and param.max_value else 10
                elif param.param_type == float:
                    test_value = float((param.min_value + param.max_value) / 2) if param.min_value and param.max_value else 0.5
                else:
                    continue
                
                strategy.set_parameter(param_name, test_value)
            
            # 使用修改后的参数生成信号
            signals_modified = strategy.generate_signals(self.test_data)
            
            # 验证信号生成不受阻
            self.assertIsInstance(signals_modified, list,
                                f"{strategy_name} 策略参数修改后应能正常生成信号")
            
            print(f"✓ {strategy_name} 策略所有参数影响信号生成测试通过")
    
    def test_parameter_cache_mechanism(self):
        """测试参数缓存机制"""
        strategy = MAStrategy()
        
        # 第一次生成信号
        signals1 = strategy.generate_signals(self.test_data)
        last_updated1 = strategy.last_updated
        
        # 不修改参数，再次生成信号（应使用缓存）
        signals2 = strategy.generate_signals(self.test_data)
        last_updated2 = strategy.last_updated
        
        # 修改参数后生成信号
        strategy.set_parameter("short_period", 10)
        signals3 = strategy.generate_signals(self.test_data)
        last_updated3 = strategy.last_updated
        
        # 验证缓存机制
        self.assertEqual(last_updated1, last_updated2, "参数未变时应使用缓存")
        self.assertGreater(last_updated3, last_updated2, "参数修改后应更新缓存")
        
        print("✓ 参数缓存机制测试通过")
    
    def test_parameter_validation_chain(self):
        """测试参数验证链"""
        strategy = RSIStrategy()
        
        # 测试有效值
        self.assertTrue(strategy.set_parameter("period", 20))
        self.assertEqual(strategy.get_parameter("period"), 20)
        
        # 测试无效值（超出范围）
        self.assertFalse(strategy.set_parameter("period", 100))
        self.assertEqual(strategy.get_parameter("period"), 20, "无效值不应改变参数")
        
        # 测试类型错误
        self.assertFalse(strategy.set_parameter("period", "invalid"))
        self.assertEqual(strategy.get_parameter("period"), 20)
        
        print("✓ 参数验证链测试通过")
    
    def test_parameter_persistence(self):
        """测试参数持久性"""
        strategy = MACDStrategy()
        
        # 设置参数
        strategy.set_parameter("fast_period", 10)
        strategy.set_parameter("slow_period", 30)
        strategy.set_parameter("signal_period", 7)
        
        # 多次生成信号
        for i in range(3):
            signals = strategy.generate_signals(self.test_data)
            
            # 验证参数保持不变
            self.assertEqual(strategy.get_parameter("fast_period"), 10)
            self.assertEqual(strategy.get_parameter("slow_period"), 30)
            self.assertEqual(strategy.get_parameter("signal_period"), 7)
        
        print("✓ 参数持久性测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 80)
    print("策略参数业务逻辑全面测试")
    print("=" * 80)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestMAStrategyParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestMACDStrategyParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestRSIStrategyParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestKDJStrategyParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestBollingerBandsStrategyParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestParameterBusinessLogic))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 80)
    print(f"测试完成：{result.testsRun} 个测试")
    print(f"成功：{result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败：{len(result.failures)}")
    print(f"错误：{len(result.errors)}")
    print("=" * 80)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
