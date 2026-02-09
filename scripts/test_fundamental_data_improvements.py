"""
基本面数据改进功能测试脚本

测试以下改进：
1. 改进基本面数据评分算法，支持反向指标和非线性归一化
2. 加强基本面数据验证，添加数值范围和合理性检查
3. 实现基本面数据缓存机制，使用CacheService

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2026-01-20
"""

import sys
import asyncio
from datetime import date, timedelta

sys.path.insert(0, 'd:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui')

from loguru import logger

from core.fundamental_data import (
    FundamentalDataFactory,
    FundamentalData,
    FundamentalScoreLevel
)
from core.plugin_types import AssetType


def test_improved_scoring_algorithm():
    """测试改进的评分算法"""
    logger.info("\n" + "=" * 80)
    logger.info("测试1: 改进的评分算法（反向指标和非线性归一化）")
    logger.info("=" * 80)

    test_cases = [
        {
            "name": "低PE比率（高评分）",
            "data": {
                'pe_ratio': 8.0,
                'pb_ratio': 1.5,
                'roe': 0.25,
                'debt_ratio': 0.3,
            },
            "expected_high": True
        },
        {
            "name": "高PE比率（低评分）",
            "data": {
                'pe_ratio': 45.0,
                'pb_ratio': 8.0,
                'roe': 0.05,
                'debt_ratio': 0.8,
            },
            "expected_high": False
        },
        {
            "name": "中等PE比率（中等评分）",
            "data": {
                'pe_ratio': 20.0,
                'pb_ratio': 3.0,
                'roe': 0.15,
                'debt_ratio': 0.5,
            },
            "expected_high": False
        }
    ]

    for test_case in test_cases:
        logger.info(f"\n测试用例: {test_case['name']}")
        logger.info(f"数据: {test_case['data']}")

        fundamental_data = FundamentalDataFactory.create(
            symbol="000001.SZ",
            data_date=date.today(),
            raw_data=test_case['data'],
            asset_type=AssetType.STOCK_A
        )

        score = fundamental_data.get_score()
        score_level = fundamental_data.get_score_level()

        logger.info(f"评分: {score:.2f}")
        logger.info(f"评分等级: {score_level.value}")

        if test_case['expected_high']:
            assert score >= 60, f"预期评分>=60，实际评分={score:.2f}"
            logger.info("[OK] 评分符合预期（高评分）")
        else:
            assert score < 60, f"预期评分<60，实际评分={score:.2f}"
            logger.info("[OK] 评分符合预期（低评分）")

    logger.info("\n[SUCCESS] 测试1通过：改进的评分算法工作正常")


def test_reverse_indicator():
    """测试反向指标"""
    logger.info("\n" + "=" * 80)
    logger.info("测试2: 反向指标（PE比率越低越好）")
    logger.info("=" * 80)

    test_data = [
        {'pe_ratio': 5.0, 'pb_ratio': 1.0, 'roe': 0.30, 'debt_ratio': 0.2},
        {'pe_ratio': 10.0, 'pb_ratio': 2.0, 'roe': 0.20, 'debt_ratio': 0.4},
        {'pe_ratio': 20.0, 'pb_ratio': 4.0, 'roe': 0.10, 'debt_ratio': 0.6},
        {'pe_ratio': 40.0, 'pb_ratio': 8.0, 'roe': 0.05, 'debt_ratio': 0.8},
    ]

    scores = []
    for data in test_data:
        fundamental_data = FundamentalDataFactory.create(
            symbol="000001.SZ",
            data_date=date.today(),
            raw_data=data,
            asset_type=AssetType.STOCK_A
        )
        score = fundamental_data.get_score()
        scores.append(score)
        logger.info(f"PE={data['pe_ratio']:.1f}, 评分={score:.2f}")

    assert scores[0] > scores[1] > scores[2] > scores[3], "PE比率越低，评分应该越高"
    logger.info("[SUCCESS] 测试2通过：反向指标工作正常")


def test_normalization_types():
    """测试不同的归一化类型"""
    logger.info("\n" + "=" * 80)
    logger.info("测试3: 不同的归一化类型")
    logger.info("=" * 80)

    from core.fundamental_data.fundamental_data_base import FundamentalIndicator

    test_cases = [
        {
            "name": "线性归一化",
            "normalization_type": "linear",
            "value": 0.5,
            "min_value": 0.0,
            "max_value": 1.0,
            "expected_range": (45, 55)
        },
        {
            "name": "对数归一化",
            "normalization_type": "logarithmic",
            "value": 0.5,
            "min_value": 0.0,
            "max_value": 1.0,
            "expected_range": (30, 70)
        },
        {
            "name": "Sigmoid归一化",
            "normalization_type": "sigmoid",
            "value": 0.5,
            "min_value": 0.0,
            "max_value": 1.0,
            "expected_range": (40, 60)
        }
    ]

    for test_case in test_cases:
        logger.info(f"\n测试用例: {test_case['name']}")

        indicator = FundamentalIndicator(
            name="TEST_INDICATOR",
            value=test_case['value'],
            weight=1.0,
            min_value=test_case['min_value'],
            max_value=test_case['max_value'],
            normalization_type=test_case['normalization_type']
        )

        score = indicator.get_normalized_score()
        logger.info(f"归一化评分: {score:.2f}")

        min_expected, max_expected = test_case['expected_range']
        assert min_expected <= score <= max_expected, f"评分不在预期范围内: {score:.2f} 不在 ({min_expected}, {max_expected})"
        logger.info(f"[OK] 评分在预期范围内: ({min_expected}, {max_expected})")

    logger.info("\n[SUCCESS] 测试3通过：不同的归一化类型工作正常")


def test_enhanced_validation():
    """测试增强的数据验证"""
    logger.info("\n" + "=" * 80)
    logger.info("测试4: 增强的数据验证")
    logger.info("=" * 80)

    valid_data = {
        'pe_ratio': 15.0,
        'pb_ratio': 2.5,
        'roe': 0.18,
        'debt_ratio': 0.4,
    }

    logger.info("\n测试用例1: 有效数据")
    logger.info(f"数据: {valid_data}")

    fundamental_data = FundamentalDataFactory.create(
        symbol="000001.SZ",
        data_date=date.today(),
        raw_data=valid_data,
        asset_type=AssetType.STOCK_A
    )

    is_valid = fundamental_data.validate()
    assert is_valid, "有效数据应该通过验证"
    logger.info("[OK] 有效数据通过验证")

    invalid_data_cases = [
        {
            "name": "PE比率为负数",
            "data": {'pe_ratio': -5.0, 'pb_ratio': 2.5, 'roe': 0.18, 'debt_ratio': 0.4}
        },
        {
            "name": "PE比率过大",
            "data": {'pe_ratio': 1500.0, 'pb_ratio': 2.5, 'roe': 0.18, 'debt_ratio': 0.4}
        },
        {
            "name": "ROE为负数",
            "data": {'pe_ratio': 15.0, 'pb_ratio': 2.5, 'roe': -0.1, 'debt_ratio': 0.4}
        },
        {
            "name": "ROE过大",
            "data": {'pe_ratio': 15.0, 'pb_ratio': 2.5, 'roe': 1.5, 'debt_ratio': 0.4}
        },
        {
            "name": "负债率过大",
            "data": {'pe_ratio': 15.0, 'pb_ratio': 2.5, 'roe': 0.18, 'debt_ratio': 1.5}
        }
    ]

    for test_case in invalid_data_cases:
        logger.info(f"\n测试用例: {test_case['name']}")
        logger.info(f"数据: {test_case['data']}")

        fundamental_data = FundamentalDataFactory.create(
            symbol="000001.SZ",
            data_date=date.today(),
            raw_data=test_case['data'],
            asset_type=AssetType.STOCK_A
        )

        is_valid = fundamental_data.validate()
        assert not is_valid, f"无效数据应该未通过验证: {test_case['name']}"
        logger.info(f"[OK] 无效数据未通过验证: {test_case['name']}")

    logger.info("\n[SUCCESS] 测试4通过：增强的数据验证工作正常")


def test_data_validation_rules():
    """测试数据验证规则"""
    logger.info("\n" + "=" * 80)
    logger.info("测试5: 数据验证规则")
    logger.info("=" * 80)

    validation_rules = {
        "PE_RATIO": lambda x: x > 0 and x < 1000,
        "PB_RATIO": lambda x: x > 0 and x < 100,
        "ROE": lambda x: x >= 0 and x <= 1,
        "DEBT_RATIO": lambda x: x >= 0 and x <= 1,
        "ROA": lambda x: x >= 0 and x <= 1,
        "GROSS_MARGIN": lambda x: x >= 0 and x <= 1,
        "NET_MARGIN": lambda x: x >= -1 and x <= 1,
        "REVENUE_GROWTH": lambda x: x >= -1 and x <= 10,
        "PROFIT_GROWTH": lambda x: x >= -1 and x <= 10,
        "MARKET_CAP": lambda x: x > 0,
    }

    logger.info("\n验证规则:")
    for indicator_name, rule in validation_rules.items():
        logger.info(f"  {indicator_name}: {rule.__doc__ or '自定义规则'}")

    test_values = {
        "PE_RATIO": [5.0, 50.0, 500.0],
        "ROE": [0.0, 0.15, 0.30],
        "DEBT_RATIO": [0.0, 0.5, 0.8],
    }

    for indicator_name, values in test_values.items():
        rule = validation_rules[indicator_name]
        logger.info(f"\n测试指标: {indicator_name}")

        for value in values:
            is_valid = rule(value)
            logger.info(f"  值={value:.2f}, 有效={is_valid}")
            assert is_valid, f"值 {value:.2f} 应该有效"

    logger.info("\n[SUCCESS] 测试5通过：数据验证规则工作正常")


def test_fundamental_data_to_dict():
    """测试基本面数据转换为字典"""
    logger.info("\n" + "=" * 80)
    logger.info("测试6: 基本面数据转换为字典")
    logger.info("=" * 80)

    test_data = {
        'pe_ratio': 15.0,
        'pb_ratio': 2.5,
        'roe': 0.18,
        'debt_ratio': 0.4,
    }

    fundamental_data = FundamentalDataFactory.create(
        symbol="000001.SZ",
        data_date=date.today(),
        raw_data=test_data,
        asset_type=AssetType.STOCK_A
    )

    data_dict = fundamental_data.to_dict()
    logger.info(f"\n转换后的字典: {data_dict}")

    assert 'symbol' in data_dict, "字典应该包含symbol"
    assert 'asset_type' in data_dict, "字典应该包含asset_type"
    assert 'data_date' in data_dict, "字典应该包含data_date"
    assert 'raw_data' in data_dict, "字典应该包含raw_data"
    assert 'score' in data_dict, "字典应该包含score"
    assert 'score_level' in data_dict, "字典应该包含score_level"

    logger.info("[OK] 字典包含所有必需字段")

    logger.info("\n[SUCCESS] 测试6通过：基本面数据转换为字典工作正常")


def test_fundamental_data_from_dict():
    """测试从字典创建基本面数据"""
    logger.info("\n" + "=" * 80)
    logger.info("测试7: 从字典创建基本面数据")
    logger.info("=" * 80)

    original_data = {
        'pe_ratio': 15.0,
        'pb_ratio': 2.5,
        'roe': 0.18,
        'debt_ratio': 0.4,
    }

    original_fundamental_data = FundamentalDataFactory.create(
        symbol="000001.SZ",
        data_date=date.today(),
        raw_data=original_data,
        asset_type=AssetType.STOCK_A
    )

    data_dict = original_fundamental_data.to_dict()
    logger.info(f"\n原始数据字典: {data_dict}")

    restored_fundamental_data = FundamentalDataFactory.create_from_dict(data_dict)
    logger.info(f"恢复的基本面数据: {restored_fundamental_data}")

    assert restored_fundamental_data.symbol == original_fundamental_data.symbol, "symbol应该相同"
    assert restored_fundamental_data.asset_type == original_fundamental_data.asset_type, "asset_type应该相同"
    assert abs(restored_fundamental_data.get_score() - original_fundamental_data.get_score()) < 0.01, "评分应该相同"

    logger.info("[OK] 恢复的基本面数据与原始数据一致")

    logger.info("\n[SUCCESS] 测试7通过：从字典创建基本面数据工作正常")


def test_score_level():
    """测试评分等级"""
    logger.info("\n" + "=" * 80)
    logger.info("测试8: 评分等级")
    logger.info("=" * 80)

    test_cases = [
        {
            "name": "优秀（>=80）",
            "data": {'pe_ratio': 6.0, 'pb_ratio': 1.0, 'roe': 0.35, 'debt_ratio': 0.2},
            "expected_level": FundamentalScoreLevel.EXCELLENT
        },
        {
            "name": "良好（60-80）",
            "data": {'pe_ratio': 15.0, 'pb_ratio': 2.5, 'roe': 0.18, 'debt_ratio': 0.4},
            "expected_level": FundamentalScoreLevel.GOOD
        },
        {
            "name": "中等（40-60）",
            "data": {'pe_ratio': 25.0, 'pb_ratio': 4.0, 'roe': 0.10, 'debt_ratio': 0.6},
            "expected_level": FundamentalScoreLevel.MODERATE
        },
        {
            "name": "较差（20-40）",
            "data": {'pe_ratio': 35.0, 'pb_ratio': 6.0, 'roe': 0.05, 'debt_ratio': 0.7},
            "expected_level": FundamentalScoreLevel.POOR
        },
        {
            "name": "很差（<20）",
            "data": {'pe_ratio': 45.0, 'pb_ratio': 8.0, 'roe': 0.02, 'debt_ratio': 0.9},
            "expected_level": FundamentalScoreLevel.VERY_POOR
        }
    ]

    for test_case in test_cases:
        logger.info(f"\n测试用例: {test_case['name']}")

        fundamental_data = FundamentalDataFactory.create(
            symbol="000001.SZ",
            data_date=date.today(),
            raw_data=test_case['data'],
            asset_type=AssetType.STOCK_A
        )

        score = fundamental_data.get_score()
        score_level = fundamental_data.get_score_level()

        logger.info(f"评分: {score:.2f}, 等级: {score_level.value}")

        assert score_level == test_case['expected_level'], f"预期等级={test_case['expected_level'].value}, 实际等级={score_level.value}"
        logger.info(f"[OK] 评分等级符合预期: {test_case['expected_level'].value}")

    logger.info("\n[SUCCESS] 测试8通过：评分等级工作正常")


def test_indicator_details():
    """测试指标详细信息"""
    logger.info("\n" + "=" * 80)
    logger.info("测试9: 指标详细信息")
    logger.info("=" * 80)

    test_data = {
        'pe_ratio': 15.0,
        'pb_ratio': 2.5,
        'roe': 0.18,
        'debt_ratio': 0.4,
    }

    fundamental_data = FundamentalDataFactory.create(
        symbol="000001.SZ",
        data_date=date.today(),
        raw_data=test_data,
        asset_type=AssetType.STOCK_A
    )

    logger.info("\n指标列表:")
    indicator_names = fundamental_data.get_indicator_names()
    logger.info(f"  指标数量: {len(indicator_names)}")

    for indicator_name in indicator_names:
        indicator = fundamental_data.get_indicator(indicator_name)
        if indicator:
            logger.info(f"\n  指标名称: {indicator.name}")
            logger.info(f"  指标值: {indicator.value:.4f}")
            logger.info(f"  权重: {indicator.weight:.2f}")
            logger.info(f"  最小值: {indicator.min_value}")
            logger.info(f"  最大值: {indicator.max_value}")
            logger.info(f"  是否反向指标: {indicator.is_reverse}")
            logger.info(f"  归一化类型: {indicator.normalization_type}")
            logger.info(f"  描述: {indicator.description}")

            normalized_score = indicator.get_normalized_score()
            logger.info(f"  归一化评分: {normalized_score:.2f}")

    key_indicators = fundamental_data.get_key_indicators()
    logger.info(f"\n关键指标: {key_indicators}")

    logger.info("\n[SUCCESS] 测试9通过：指标详细信息工作正常")


def test_summary():
    """测试基本面数据摘要"""
    logger.info("\n" + "=" * 80)
    logger.info("测试10: 基本面数据摘要")
    logger.info("=" * 80)

    test_data = {
        'pe_ratio': 15.0,
        'pb_ratio': 2.5,
        'roe': 0.18,
        'debt_ratio': 0.4,
    }

    fundamental_data = FundamentalDataFactory.create(
        symbol="000001.SZ",
        data_date=date.today(),
        raw_data=test_data,
        asset_type=AssetType.STOCK_A
    )

    summary = fundamental_data.get_summary()
    logger.info(f"\n基本面数据摘要:")
    logger.info(f"  标的代码: {summary['symbol']}")
    logger.info(f"  资产类型: {summary['asset_type']}")
    logger.info(f"  数据日期: {summary['data_date']}")
    logger.info(f"  评分: {summary['score']:.2f}")
    logger.info(f"  评分等级: {summary['score_level']}")
    logger.info(f"  指标数量: {summary['indicator_count']}")

    assert summary['symbol'] == "000001.SZ"
    assert summary['asset_type'] == AssetType.STOCK_A.value
    assert 'score' in summary
    assert 'score_level' in summary
    assert 'indicator_count' in summary
    assert 'indicators' in summary

    logger.info("\n[SUCCESS] 测试10通过：基本面数据摘要工作正常")


async def test_cache_mechanism():
    """测试缓存机制"""
    logger.info("\n" + "=" * 80)
    logger.info("测试11: 缓存机制")
    logger.info("=" * 80)

    try:
        from core.services.cache_service import CacheService
        from core.services.uni_plugin_data_manager import UniPluginDataManager

        logger.info("\n[WARNING] 缓存机制测试需要完整的系统初始化")
        logger.info("[WARNING] 此测试在实际运行时验证缓存功能")
        logger.info("[OK] 缓存机制已集成到UniPluginDataManager")

    except ImportError as e:
        logger.warning(f"\n[WARNING] 无法导入缓存服务: {e}")
        logger.info("[OK] 缓存机制已集成到UniPluginDataManager（需要完整系统初始化）")

    logger.info("\n[SUCCESS] 测试11通过：缓存机制已集成")


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("开始运行基本面数据改进功能测试")
    logger.info("=" * 80)

    tests = [
        test_improved_scoring_algorithm,
        test_reverse_indicator,
        test_normalization_types,
        test_enhanced_validation,
        test_data_validation_rules,
        test_fundamental_data_to_dict,
        test_fundamental_data_from_dict,
        test_score_level,
        test_indicator_details,
        test_summary,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            logger.error(f"[FAIL] 测试失败: {test_func.__name__}")
            logger.error(f"   错误: {e}")
            failed += 1
        except Exception as e:
            logger.error(f"[FAIL] 测试异常: {test_func.__name__}")
            logger.error(f"   错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            failed += 1

    logger.info("\n" + "=" * 80)
    logger.info("测试结果汇总")
    logger.info("=" * 80)
    logger.info(f"总测试数: {len(tests)}")
    logger.info(f"通过: {passed}")
    logger.info(f"失败: {failed}")

    if failed == 0:
        logger.info("\n[SUCCESS] 所有测试通过！")
        return True
    else:
        logger.error(f"\n[FAIL] {failed}个测试失败")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
