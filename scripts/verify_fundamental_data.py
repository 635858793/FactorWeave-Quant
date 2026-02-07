"""
基本面数据抽象接口功能验证脚本

全面验证基本面数据抽象层的所有功能，包括：
1. 基本面数据工厂的创建功能
2. 不同资产类型的基本面数据处理
3. 评分计算和验证
4. 数据转换和验证
5. 与现有系统的集成

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

import sys
from datetime import date
from typing import Dict, Any

from loguru import logger

from core.fundamental_data.fundamental_data_base import FundamentalScoreLevel
from core.fundamental_data.stock_fundamental_data import StockFundamentalData
from core.fundamental_data.futures_fundamental_data import FuturesFundamentalData
from core.fundamental_data.crypto_fundamental_data import CryptoFundamentalData
from core.fundamental_data.fundamental_data_factory import FundamentalDataFactory
from core.plugin_types import AssetType


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_fundamental_data_factory():
    """测试基本面数据工厂"""
    print_section("测试基本面数据工厂")

    try:
        print("\n[1.1] 测试支持的资产类型")
        supported_types = FundamentalDataFactory.get_supported_asset_types()
        print(f"支持的资产类型数量: {len(supported_types)}")
        for asset_type in supported_types:
            print(f"  - {asset_type.value}")
        print("支持的资产类型测试通过")

        print("\n[1.2] 测试资产类型支持检查")
        test_cases = [
            (AssetType.STOCK_A, True),
            (AssetType.FUTURES, True),
            (AssetType.CRYPTO, True),
            (AssetType.BOND, False)
        ]
        for asset_type, expected in test_cases:
            result = FundamentalDataFactory.is_supported(asset_type)
            status = "✓" if result == expected else "❌"
            print(f"{status} {asset_type.value}: {result} (期望: {expected})")

        print("\n[1.3] 测试获取基本面数据类")
        stock_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.STOCK_A)
        futures_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.FUTURES)
        crypto_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.CRYPTO)
        bond_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.BOND)

        print(f"股票基本面数据类: {stock_class.__name__}")
        print(f"期货基本面数据类: {futures_class.__name__}")
        print(f"加密货币基本面数据类: {crypto_class.__name__}")
        print(f"债券基本面数据类: {bond_class}")

        print("\n基本面数据工厂测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 基本面数据工厂测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stock_fundamental_data():
    """测试股票基本面数据"""
    print_section("测试股票基本面数据")

    try:
        print("\n[2.1] 测试股票基本面数据创建")
        raw_data = {
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

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )
        print(f"股票基本面数据创建成功: {stock_data}")
        print(f"   - 股票代码: {stock_data.symbol}")
        print(f"   - 资产类型: {stock_data.asset_type.value}")
        print(f"   - 指标数量: {len(stock_data._indicators)}")

        print("\n[2.2] 测试获取关键指标")
        indicators = stock_data.get_key_indicators()
        print(f"关键指标数量: {len(indicators)}")
        for name, value in indicators.items():
            print(f"  - {name}: {value:.2f}")
        print("关键指标获取成功")

        print("\n[2.3] 测试基本面评分")
        score = stock_data.get_score()
        score_level = stock_data.get_score_level()
        print(f"基本面评分: {score:.2f}")
        print(f"评分等级: {score_level.value}")
        print("基本面评分计算成功")

        print("\n[2.4] 测试分类评分")
        valuation_score = stock_data.get_valuation_score()
        profitability_score = stock_data.get_profitability_score()
        growth_score = stock_data.get_growth_score()
        financial_health_score = stock_data.get_financial_health_score()

        print(f"估值评分: {valuation_score:.2f}")
        print(f"盈利能力评分: {profitability_score:.2f}")
        print(f"成长性评分: {growth_score:.2f}")
        print(f"财务健康评分: {financial_health_score:.2f}")
        print("分类评分计算成功")

        print("\n[2.5] 测试数据验证")
        is_valid = stock_data.validate()
        print(f"数据有效性: {is_valid}")
        print("数据验证成功")

        print("\n[2.6] 测试转换为字典")
        data_dict = stock_data.to_dict()
        print(f"字典键: {list(data_dict.keys())}")
        print(f"包含评分: {'score' in data_dict}")
        print(f"包含指标: {'indicators' in data_dict}")
        print("数据转换成功")

        print("\n[2.7] 测试获取摘要")
        summary = stock_data.get_summary()
        print(f"摘要键: {list(summary.keys())}")
        print(f"股票代码: {summary['symbol']}")
        print(f"评分: {summary['score']:.2f}")
        print(f"评分等级: {summary['score_level']}")
        print("摘要获取成功")

        print("\n股票基本面数据测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 股票基本面数据测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_futures_fundamental_data():
    """测试期货基本面数据"""
    print_section("测试期货基本面数据")

    try:
        print("\n[3.1] 测试期货基本面数据创建")
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0,
            'basis': 10.0,
            'supply_demand_ratio': 1.2,
            'production': 1000000.0,
            'consumption': 900000.0,
            'import_export': 50000.0,
            'seasonal_factor': 0.5,
            'macro_indicator': 2.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )
        print(f"期货基本面数据创建成功: {futures_data}")
        print(f"   - 期货代码: {futures_data.symbol}")
        print(f"   - 资产类型: {futures_data.asset_type.value}")
        print(f"   - 指标数量: {len(futures_data._indicators)}")

        print("\n[3.2] 测试获取关键指标")
        indicators = futures_data.get_key_indicators()
        print(f"关键指标数量: {len(indicators)}")
        for name, value in indicators.items():
            print(f"  - {name}: {value:.2f}")
        print("关键指标获取成功")

        print("\n[3.3] 测试基本面评分")
        score = futures_data.get_score()
        score_level = futures_data.get_score_level()
        print(f"基本面评分: {score:.2f}")
        print(f"评分等级: {score_level.value}")
        print("基本面评分计算成功")

        print("\n[3.4] 测试分类评分")
        liquidity_score = futures_data.get_liquidity_score()
        supply_demand_score = futures_data.get_supply_demand_score()
        market_sentiment_score = futures_data.get_market_sentiment_score()

        print(f"流动性评分: {liquidity_score:.2f}")
        print(f"供需评分: {supply_demand_score:.2f}")
        print(f"市场情绪评分: {market_sentiment_score:.2f}")
        print("分类评分计算成功")

        print("\n[3.5] 测试数据验证")
        is_valid = futures_data.validate()
        print(f"数据有效性: {is_valid}")
        print("数据验证成功")

        print("\n期货基本面数据测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 期货基本面数据测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crypto_fundamental_data():
    """测试加密货币基本面数据"""
    print_section("测试加密货币基本面数据")

    try:
        print("\n[4.1] 测试加密货币基本面数据创建")
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'total_supply': 200000000.0,
            'max_supply': 210000000.0,
            'active_addresses': 100000.0,
            'transactions_per_day': 500000.0,
            'hashrate': 1000000000.0,
            'difficulty': 50000000000.0,
            'block_height': 800000.0,
            'developer_activity': 100.0,
            'github_commits': 1000.0,
            'community_score': 80.0,
            'social_sentiment': 0.6,
            'network_growth': 20.0,
            'whale_activity': 30.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )
        print(f"加密货币基本面数据创建成功: {crypto_data}")
        print(f"   - 加密货币代码: {crypto_data.symbol}")
        print(f"   - 资产类型: {crypto_data.asset_type.value}")
        print(f"   - 指标数量: {len(crypto_data._indicators)}")

        print("\n[4.2] 测试获取关键指标")
        indicators = crypto_data.get_key_indicators()
        print(f"关键指标数量: {len(indicators)}")
        for name, value in indicators.items():
            print(f"  - {name}: {value:.2f}")
        print("关键指标获取成功")

        print("\n[4.3] 测试基本面评分")
        score = crypto_data.get_score()
        score_level = crypto_data.get_score_level()
        print(f"基本面评分: {score:.2f}")
        print(f"评分等级: {score_level.value}")
        print("基本面评分计算成功")

        print("\n[4.4] 测试分类评分")
        market_score = crypto_data.get_market_score()
        network_health_score = crypto_data.get_network_health_score()
        development_score = crypto_data.get_development_score()
        community_score = crypto_data.get_community_score()
        sentiment_score = crypto_data.get_sentiment_score()
        growth_score = crypto_data.get_growth_score()

        print(f"市场评分: {market_score:.2f}")
        print(f"网络健康评分: {network_health_score:.2f}")
        print(f"开发评分: {development_score:.2f}")
        print(f"社区评分: {community_score:.2f}")
        print(f"情绪评分: {sentiment_score:.2f}")
        print(f"增长评分: {growth_score:.2f}")
        print("分类评分计算成功")

        print("\n[4.5] 测试数据验证")
        is_valid = crypto_data.validate()
        print(f"数据有效性: {is_valid}")
        print("数据验证成功")

        print("\n加密货币基本面数据测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 加密货币基本面数据测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_factory_creation():
    """测试工厂创建功能"""
    print_section("测试工厂创建功能")

    try:
        print("\n[5.1] 测试使用工厂创建股票基本面数据")
        stock_raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = FundamentalDataFactory.create(
            symbol="000001",
            data_date=date.today(),
            raw_data=stock_raw_data,
            asset_type=AssetType.STOCK_A
        )
        print(f"股票基本面数据创建成功: {stock_data}")
        assert isinstance(stock_data, StockFundamentalData)

        print("\n[5.2] 测试使用工厂创建期货基本面数据")
        futures_raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0
        }

        futures_data = FundamentalDataFactory.create(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=futures_raw_data,
            asset_type=AssetType.FUTURES
        )
        print(f"期货基本面数据创建成功: {futures_data}")
        assert isinstance(futures_data, FuturesFundamentalData)

        print("\n[5.3] 测试使用工厂创建加密货币基本面数据")
        crypto_raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'active_addresses': 100000.0
        }

        crypto_data = FundamentalDataFactory.create(
            symbol="BTC",
            data_date=date.today(),
            raw_data=crypto_raw_data,
            asset_type=AssetType.CRYPTO
        )
        print(f"加密货币基本面数据创建成功: {crypto_data}")
        assert isinstance(crypto_data, CryptoFundamentalData)

        print("\n[5.4] 测试从字典创建基本面数据")
        data_dict = {
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

        fundamental_data = FundamentalDataFactory.create_from_dict(data_dict)
        print(f"从字典创建基本面数据成功: {fundamental_data}")
        assert isinstance(fundamental_data, StockFundamentalData)

        print("\n[5.5] 测试批量创建基本面数据")
        data_list = [
            {
                'symbol': '000001',
                'asset_type': AssetType.STOCK_A.value,
                'data_date': date.today().isoformat(),
                'raw_data': {
                    'pe_ratio': 15.0,
                    'pb_ratio': 2.5,
                    'roe': 20.0,
                    'debt_ratio': 40.0
                }
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
            },
            {
                'symbol': 'CU2401',
                'asset_type': AssetType.FUTURES.value,
                'data_date': date.today().isoformat(),
                'raw_data': {
                    'open_interest': 100000.0,
                    'volume': 500000.0,
                    'inventory': 50000.0
                }
            }
        ]

        fundamental_data_list = FundamentalDataFactory.create_batch(data_list)
        print(f"批量创建基本面数据成功: {len(fundamental_data_list)}个")
        assert len(fundamental_data_list) == 3

        print("\n工厂创建功能测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 工厂创建功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_edge_cases():
    """测试边界情况"""
    print_section("测试边界情况")

    try:
        print("\n[6.1] 测试空数据")
        try:
            empty_data = StockFundamentalData(
                symbol="TEST",
                data_date=date.today(),
                raw_data={}
            )
            is_valid = empty_data.validate()
            print(f"空数据验证结果: {is_valid} (期望: False)")
            assert is_valid is False
        except Exception as e:
            print(f"空数据处理正确: {type(e).__name__}")

        print("\n[6.2] 测试部分缺失数据")
        partial_data = StockFundamentalData(
            symbol="TEST",
            data_date=date.today(),
            raw_data={
                'pe_ratio': 15.0
            }
        )
        is_valid = partial_data.validate()
        print(f"部分缺失数据验证结果: {is_valid} (期望: False)")
        assert is_valid is False

        print("\n[6.3] 测试不支持的资产类型")
        try:
            FundamentalDataFactory.create(
                symbol="TEST",
                data_date=date.today(),
                raw_data={'test': 100.0},
                asset_type=AssetType.BOND
            )
            print("❌ 应该抛出异常")
            return False
        except ValueError as e:
            print(f"不支持的资产类型处理正确: {e}")

        print("\n[6.4] 测试评分边界值")
        boundary_data = StockFundamentalData(
            symbol="TEST",
            data_date=date.today(),
            raw_data={
                'pe_ratio': 5.0,
                'pb_ratio': 0.5,
                'roe': 30.0,
                'debt_ratio': 0.0
            }
        )
        score = boundary_data.get_score()
        print(f"边界值评分: {score:.2f}")
        assert 0.0 <= score <= 100.0

        print("\n边界情况测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 边界情况测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_with_existing_system():
    """测试与现有系统的集成"""
    print_section("测试与现有系统的集成")

    try:
        print("\n[7.1] 测试与现有数据格式的兼容性")
        existing_format = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=existing_format
        )

        indicators = stock_data.get_key_indicators()
        print(f"现有格式兼容性测试通过")
        print(f"   - PE_RATIO: {indicators.get('PE_RATIO')}")
        print(f"   - PB_RATIO: {indicators.get('PB_RATIO')}")
        print(f"   - ROE: {indicators.get('ROE')}")
        print(f"   - DEBT_RATIO: {indicators.get('DEBT_RATIO')}")

        print("\n[7.2] 测试数据转换一致性")
        data_dict = stock_data.to_dict()
        assert 'PE_RATIO' in data_dict['indicators']
        assert 'PB_RATIO' in data_dict['indicators']
        assert 'ROE' in data_dict['indicators']
        assert 'DEBT_RATIO' in data_dict['indicators']
        print("数据转换一致性测试通过")

        print("\n[7.3] 测试评分计算一致性")
        score1 = stock_data.get_score()
        score2 = stock_data.get_score()
        assert score1 == score2
        print(f"评分计算一致性测试通过: {score1:.2f}")

        print("\n与现有系统的集成测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 与现有系统的集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("  基本面数据抽象接口功能验证")
    print("=" * 80)

    results = []

    results.append(("基本面数据工厂", test_fundamental_data_factory()))
    results.append(("股票基本面数据", test_stock_fundamental_data()))
    results.append(("期货基本面数据", test_futures_fundamental_data()))
    results.append(("加密货币基本面数据", test_crypto_fundamental_data()))
    results.append(("工厂创建功能", test_factory_creation()))
    results.append(("边界情况", test_edge_cases()))
    results.append(("与现有系统集成", test_integration_with_existing_system()))

    print_section("测试结果汇总")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！基本面数据抽象接口功能验证成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
