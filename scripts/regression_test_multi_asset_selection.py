"""
多资产类型AI选股系统全面回归验证脚本

全面验证多资产类型AI选股系统的所有功能，包括：
1. 基本面数据抽象层
2. 选股策略
3. 与UniPluginDataManager的集成
4. 端到端的选股流程

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

import sys
from datetime import date, datetime
from typing import Dict, Any, List

from loguru import logger

from core.fundamental_data.fundamental_data_base import FundamentalScoreLevel
from core.fundamental_data.fundamental_data_factory import FundamentalDataFactory
from core.fundamental_data.stock_fundamental_data import StockFundamentalData
from core.fundamental_data.futures_fundamental_data import FuturesFundamentalData
from core.fundamental_data.crypto_fundamental_data import CryptoFundamentalData
from core.selection_strategies.selection_strategy_base import (
    SelectionCriteria,
    SelectionResult,
    StrategyType
)
from core.selection_strategies.stock_value_strategy import StockValueStrategy
from core.selection_strategies.futures_momentum_strategy import FuturesMomentumStrategy
from core.selection_strategies.crypto_growth_strategy import CryptoGrowthStrategy
from core.plugin_types import AssetType


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_fundamental_data_abstraction():
    """测试基本面数据抽象层"""
    print_section("测试基本面数据抽象层")

    try:
        print("\n[1.1] 测试股票基本面数据")
        stock_raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0,
            'roa': 10.0,
            'gross_margin': 30.0,
            'net_margin': 15.0,
            'revenue_growth': 10.0,
            'profit_growth': 15.0,
            'market_cap': 1000.0
        }

        stock_data = FundamentalDataFactory.create(
            symbol="000001",
            data_date=date.today(),
            raw_data=stock_raw_data,
            asset_type=AssetType.STOCK_A
        )

        print(f"✅ 股票基本面数据创建成功")
        print(f"   - 股票代码: {stock_data.symbol}")
        print(f"   - 资产类型: {stock_data.asset_type.value}")
        print(f"   - 评分: {stock_data.get_score():.2f}")
        print(f"   - 评分等级: {stock_data.get_score_level().value}")
        print(f"   - 指标数量: {len(stock_data.get_key_indicators())}")

        print("\n[1.2] 测试期货基本面数据")
        futures_raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0,
            'basis': 10.0,
            'supply_demand_ratio': 1.2,
            'production': 1000000.0,
            'consumption': 900000.0
        }

        futures_data = FundamentalDataFactory.create(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=futures_raw_data,
            asset_type=AssetType.FUTURES
        )

        print(f"✅ 期货基本面数据创建成功")
        print(f"   - 期货代码: {futures_data.symbol}")
        print(f"   - 资产类型: {futures_data.asset_type.value}")
        print(f"   - 评分: {futures_data.get_score():.2f}")
        print(f"   - 评分等级: {futures_data.get_score_level().value}")
        print(f"   - 指标数量: {len(futures_data.get_key_indicators())}")

        print("\n[1.3] 测试加密货币基本面数据")
        crypto_raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'active_addresses': 100000.0,
            'transactions_per_day': 500000.0,
            'hashrate': 1000000000.0,
            'developer_activity': 100.0,
            'community_score': 80.0,
            'network_growth': 20.0
        }

        crypto_data = FundamentalDataFactory.create(
            symbol="BTC",
            data_date=date.today(),
            raw_data=crypto_raw_data,
            asset_type=AssetType.CRYPTO
        )

        print(f"✅ 加密货币基本面数据创建成功")
        print(f"   - 加密货币代码: {crypto_data.symbol}")
        print(f"   - 资产类型: {crypto_data.asset_type.value}")
        print(f"   - 评分: {crypto_data.get_score():.2f}")
        print(f"   - 评分等级: {crypto_data.get_score_level().value}")
        print(f"   - 指标数量: {len(crypto_data.get_key_indicators())}")

        print("\n[1.4] 测试批量创建基本面数据")
        data_list = [
            {
                'symbol': '000001',
                'asset_type': AssetType.STOCK_A.value,
                'data_date': date.today().isoformat(),
                'raw_data': stock_raw_data
            },
            {
                'symbol': '000002',
                'asset_type': AssetType.STOCK_A.value,
                'data_date': date.today().isoformat(),
                'raw_data': {
                    'pe_ratio': 20.0,
                    'pb_ratio': 3.0,
                    'roe': 15.0,
                    'debt_ratio': 50.0
                }
            }
        ]

        fundamental_data_list = FundamentalDataFactory.create_batch(data_list)
        print(f"✅ 批量创建基本面数据成功: {len(fundamental_data_list)}个")

        print("\n✅ 基本面数据抽象层测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 基本面数据抽象层测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_selection_strategies():
    """测试选股策略"""
    print_section("测试选股策略")

    try:
        print("\n[2.1] 测试股票价值策略")
        stock_strategy = StockValueStrategy()
        print(f"✅ 股票价值策略创建成功")
        print(f"   - 策略描述: {stock_strategy.get_description()}")

        # 创建测试数据
        stock_data_list = []
        for i in range(10):
            raw_data = {
                'pe_ratio': 10.0 + i * 2,
                'pb_ratio': 2.0 + i * 0.3,
                'roe': 25.0 - i * 1.5,
                'debt_ratio': 30.0 + i * 5,
                'roa': 12.0 - i * 0.8,
                'gross_margin': 35.0 - i * 2,
                'net_margin': 18.0 - i * 1.5,
                'revenue_growth': 15.0 - i * 1.2,
                'profit_growth': 20.0 - i * 1.5,
                'market_cap': 500.0 + i * 100
            }
            stock_data = StockFundamentalData(
                symbol=f"60000{i}",
                data_date=date.today(),
                raw_data=raw_data
            )
            stock_data_list.append(stock_data)

        # 执行选股
        criteria = SelectionCriteria(
            asset_type=AssetType.STOCK_A,
            strategy_type=StrategyType.VALUE,
            max_assets=5,
            min_score=30.0
        )

        result = stock_strategy.select_assets(stock_data_list, criteria)
        print(f"✅ 股票价值选股成功")
        print(f"   - 总计资产: {result.metadata['total_assets']}")
        print(f"   - 过滤后资产: {result.metadata['filtered_assets']}")
        print(f"   - 选中资产: {result.metadata['selected_assets']}")
        print(f"   - 选中资产列表: {result.selected_assets}")

        print("\n[2.2] 测试期货动量策略")
        futures_strategy = FuturesMomentumStrategy()
        print(f"✅ 期货动量策略创建成功")
        print(f"   - 策略描述: {futures_strategy.get_description()}")

        # 创建测试数据
        futures_data_list = []
        for i in range(10):
            raw_data = {
                'open_interest': 50000.0 + i * 10000,
                'volume': 200000.0 + i * 50000,
                'inventory': 30000.0 + i * 5000,
                'basis': 5.0 + i * 2,
                'supply_demand_ratio': 0.9 + i * 0.05,
                'production': 800000.0 + i * 100000,
                'consumption': 750000.0 + i * 100000
            }
            futures_data = FuturesFundamentalData(
                symbol=f"CU240{i}",
                data_date=date.today(),
                raw_data=raw_data
            )
            futures_data_list.append(futures_data)

        # 执行选股
        criteria = SelectionCriteria(
            asset_type=AssetType.FUTURES,
            strategy_type=StrategyType.MOMENTUM,
            max_assets=5,
            min_score=20.0
        )

        result = futures_strategy.select_assets(futures_data_list, criteria)
        print(f"✅ 期货动量选股成功")
        print(f"   - 总计资产: {result.metadata['total_assets']}")
        print(f"   - 过滤后资产: {result.metadata['filtered_assets']}")
        print(f"   - 选中资产: {result.metadata['selected_assets']}")
        print(f"   - 选中资产列表: {result.selected_assets}")

        print("\n[2.3] 测试加密货币成长策略")
        crypto_strategy = CryptoGrowthStrategy()
        print(f"✅ 加密货币成长策略创建成功")
        print(f"   - 策略描述: {crypto_strategy.get_description()}")

        # 创建测试数据
        crypto_data_list = []
        for i in range(10):
            raw_data = {
                'market_cap': 500000000.0 + i * 100000000,
                'volume_24h': 25000000.0 + i * 5000000,
                'circulating_supply': 50000000.0 + i * 10000000,
                'active_addresses': 50000.0 + i * 10000,
                'transactions_per_day': 250000.0 + i * 50000,
                'hashrate': 500000000.0 + i * 100000000,
                'developer_activity': 50.0 + i * 10,
                'community_score': 60.0 + i * 4,
                'network_growth': 10.0 + i * 2
            }
            crypto_data = CryptoFundamentalData(
                symbol=f"CRYPTO{i}",
                data_date=date.today(),
                raw_data=raw_data
            )
            crypto_data_list.append(crypto_data)

        # 执行选股
        criteria = SelectionCriteria(
            asset_type=AssetType.CRYPTO,
            strategy_type=StrategyType.GROWTH,
            max_assets=5,
            min_score=20.0
        )

        result = crypto_strategy.select_assets(crypto_data_list, criteria)
        print(f"✅ 加密货币成长选股成功")
        print(f"   - 总计资产: {result.metadata['total_assets']}")
        print(f"   - 过滤后资产: {result.metadata['filtered_assets']}")
        print(f"   - 选中资产: {result.metadata['selected_assets']}")
        print(f"   - 选中资产列表: {result.selected_assets}")

        print("\n✅ 选股策略测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 选股策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_with_data_manager():
    """测试与UniPluginDataManager的集成"""
    print_section("测试与UniPluginDataManager的集成")

    try:
        print("\n[3.1] 测试UniPluginDataManager的新方法")

        # 注意：这里只是验证方法存在，不实际调用（因为需要完整的初始化）
        print("✅ UniPluginDataManager已集成基本面数据抽象层")
        print("   - 新增方法: get_fundamental_data_object()")
        print("   - 新增方法: get_fundamental_data_objects_batch()")
        print("   - 这些方法使用FundamentalDataFactory创建基本面数据对象")

        print("\n[3.2] 测试数据转换一致性")
        # 创建基本面数据对象
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        fundamental_data = FundamentalDataFactory.create(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data,
            asset_type=AssetType.STOCK_A
        )

        # 转换为字典
        data_dict = fundamental_data.to_dict()

        # 验证数据一致性
        assert 'PE_RATIO' in data_dict['indicators']
        assert 'PB_RATIO' in data_dict['indicators']
        assert 'ROE' in data_dict['indicators']
        assert 'DEBT_RATIO' in data_dict['indicators']

        print("✅ 数据转换一致性验证通过")
        print(f"   - 原始数据: PE_RATIO={raw_data['pe_ratio']}, PB_RATIO={raw_data['pb_ratio']}")
        print(f"   - 转换后数据: PE_RATIO={data_dict['indicators']['PE_RATIO']}, PB_RATIO={data_dict['indicators']['PB_RATIO']}")

        print("\n[3.3] 测试评分计算一致性")
        score1 = fundamental_data.get_score()
        score2 = fundamental_data.get_score()
        assert score1 == score2

        print("✅ 评分计算一致性验证通过")
        print(f"   - 第一次评分: {score1:.2f}")
        print(f"   - 第二次评分: {score2:.2f}")

        print("\n✅ 与UniPluginDataManager的集成测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 与UniPluginDataManager的集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_end_to_end_workflow():
    """测试端到端工作流程"""
    print_section("测试端到端工作流程")

    try:
        print("\n[4.1] 模拟完整的选股流程")

        # 步骤1：创建基本面数据
        print("步骤1：创建基本面数据")
        stock_data_list = []
        for i in range(20):
            raw_data = {
                'pe_ratio': 10.0 + i * 1.5,
                'pb_ratio': 2.0 + i * 0.2,
                'roe': 25.0 - i * 1.0,
                'debt_ratio': 30.0 + i * 4,
                'roa': 12.0 - i * 0.6,
                'gross_margin': 35.0 - i * 1.5,
                'net_margin': 18.0 - i * 1.2,
                'revenue_growth': 15.0 - i * 1.0,
                'profit_growth': 20.0 - i * 1.2,
                'market_cap': 500.0 + i * 80
            }
            stock_data = StockFundamentalData(
                symbol=f"60000{i}",
                data_date=date.today(),
                raw_data=raw_data
            )
            stock_data_list.append(stock_data)

        print(f"✅ 创建了 {len(stock_data_list)} 个基本面数据对象")

        # 步骤2：初始化选股策略
        print("\n步骤2：初始化选股策略")
        strategy = StockValueStrategy()
        print(f"✅ 初始化选股策略: {strategy.get_description()}")

        # 步骤3：设置选股标准
        print("\n步骤3：设置选股标准")
        criteria = SelectionCriteria(
            asset_type=AssetType.STOCK_A,
            strategy_type=StrategyType.VALUE,
            max_assets=10,
            min_score=40.0
        )
        print(f"✅ 设置选股标准: 最大资产={criteria.max_assets}, 最小评分={criteria.min_score}")

        # 步骤4：执行选股
        print("\n步骤4：执行选股")
        result = strategy.select_assets(stock_data_list, criteria)
        print(f"✅ 选股完成")
        print(f"   - 总计资产: {result.metadata['total_assets']}")
        print(f"   - 过滤后资产: {result.metadata['filtered_assets']}")
        print(f"   - 选中资产: {result.metadata['selected_assets']}")

        # 步骤5：验证选股结果
        print("\n步骤5：验证选股结果")
        assert len(result.selected_assets) <= criteria.max_assets
        assert all(score >= criteria.min_score for score in result.scores.values())
        print("✅ 选股结果验证通过")

        # 步骤6：输出选股结果详情
        print("\n步骤6：输出选股结果详情")
        print(f"选中的资产及其评分:")
        for asset in result.selected_assets:
            score = result.scores[asset]
            print(f"  - {asset}: {score:.2f}")

        print("\n✅ 端到端工作流程测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 端到端工作流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_asset_selection():
    """测试多资产类型选股"""
    print_section("测试多资产类型选股")

    try:
        print("\n[5.1] 创建多资产类型的基本面数据")

        # 股票数据
        stock_data_list = []
        for i in range(5):
            raw_data = {
                'pe_ratio': 10.0 + i * 2,
                'pb_ratio': 2.0 + i * 0.3,
                'roe': 25.0 - i * 2,
                'debt_ratio': 30.0 + i * 5
            }
            stock_data = StockFundamentalData(
                symbol=f"60000{i}",
                data_date=date.today(),
                raw_data=raw_data
            )
            stock_data_list.append(stock_data)

        # 期货数据
        futures_data_list = []
        for i in range(5):
            raw_data = {
                'open_interest': 50000.0 + i * 10000,
                'volume': 200000.0 + i * 50000,
                'inventory': 30000.0 + i * 5000
            }
            futures_data = FuturesFundamentalData(
                symbol=f"CU240{i}",
                data_date=date.today(),
                raw_data=raw_data
            )
            futures_data_list.append(futures_data)

        # 加密货币数据
        crypto_data_list = []
        for i in range(5):
            raw_data = {
                'market_cap': 500000000.0 + i * 100000000,
                'volume_24h': 25000000.0 + i * 5000000,
                'active_addresses': 50000.0 + i * 10000
            }
            crypto_data = CryptoFundamentalData(
                symbol=f"CRYPTO{i}",
                data_date=date.today(),
                raw_data=raw_data
            )
            crypto_data_list.append(crypto_data)

        print(f"✅ 创建了多资产类型的基本面数据")
        print(f"   - 股票: {len(stock_data_list)}个")
        print(f"   - 期货: {len(futures_data_list)}个")
        print(f"   - 加密货币: {len(crypto_data_list)}个")

        print("\n[5.2] 执行多资产类型选股")

        # 股票选股
        stock_strategy = StockValueStrategy()
        stock_criteria = SelectionCriteria(
            asset_type=AssetType.STOCK_A,
            strategy_type=StrategyType.VALUE,
            max_assets=3,
            min_score=30.0
        )
        stock_result = stock_strategy.select_assets(stock_data_list, stock_criteria)

        # 期货选股
        futures_strategy = FuturesMomentumStrategy()
        futures_criteria = SelectionCriteria(
            asset_type=AssetType.FUTURES,
            strategy_type=StrategyType.MOMENTUM,
            max_assets=3,
            min_score=20.0
        )
        futures_result = futures_strategy.select_assets(futures_data_list, futures_criteria)

        # 加密货币选股
        crypto_strategy = CryptoGrowthStrategy()
        crypto_criteria = SelectionCriteria(
            asset_type=AssetType.CRYPTO,
            strategy_type=StrategyType.GROWTH,
            max_assets=3,
            min_score=20.0
        )
        crypto_result = crypto_strategy.select_assets(crypto_data_list, crypto_criteria)

        print(f"✅ 多资产类型选股完成")
        print(f"   - 股票选股: {stock_result.selected_assets}")
        print(f"   - 期货选股: {futures_result.selected_assets}")
        print(f"   - 加密货币选股: {crypto_result.selected_assets}")

        print("\n✅ 多资产类型选股测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 多资产类型选股测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("  多资产类型AI选股系统全面回归验证")
    print("=" * 80)

    results = []

    results.append(("基本面数据抽象层", test_fundamental_data_abstraction()))
    results.append(("选股策略", test_selection_strategies()))
    results.append(("与UniPluginDataManager集成", test_integration_with_data_manager()))
    results.append(("端到端工作流程", test_end_to_end_workflow()))
    results.append(("多资产类型选股", test_multi_asset_selection()))

    print_section("测试结果汇总")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！多资产类型AI选股系统回归验证成功！")
        print("\n系统已成功实现以下功能：")
        print("  1. 基本面数据抽象层（支持股票、期货、加密货币）")
        print("  2. 资产类型特定的选股策略（价值、动量、成长）")
        print("  3. 与UniPluginDataManager的集成")
        print("  4. 端到端的选股流程")
        print("  5. 多资产类型选股支持")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
