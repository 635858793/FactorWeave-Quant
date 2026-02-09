"""
逻辑正确性检查脚本

检查多资产类型AI选股系统的逻辑正确性。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

import sys
from datetime import date
from typing import Dict, Any, List

from loguru import logger

from core.fundamental_data import (
    FundamentalDataFactory,
    StockFundamentalData,
    FuturesFundamentalData,
    CryptoFundamentalData
)
from core.selection_strategies import (
    StockValueStrategy,
    FuturesMomentumStrategy,
    CryptoGrowthStrategy,
    SelectionCriteria
)
from core.plugin_types import AssetType

def check_fundamental_data_factory_logic():
    """检查基本面数据工厂的逻辑"""
    print("\n[1] 检查基本面数据工厂逻辑")
    print("-" * 80)
    
    errors = []
    
    try:
        # 检查支持的资产类型
        supported_types = FundamentalDataFactory.get_supported_asset_types()
        print(f"支持的资产类型数量: {len(supported_types)}")
        
        expected_types = [
            AssetType.STOCK_A,
            AssetType.STOCK_B,
            AssetType.STOCK_H,
            AssetType.STOCK_US,
            AssetType.STOCK_HK,
            AssetType.FUTURES,
            AssetType.CRYPTO
        ]
        
        for asset_type in expected_types:
            if not FundamentalDataFactory.is_supported(asset_type):
                errors.append(f"资产类型 {asset_type.value} 未注册")
            else:
                print(f"  {asset_type.value}")
        
        # 测试创建股票基本面数据
        stock_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }
        stock_fundamental = FundamentalDataFactory.create(
            symbol="600000",
            data_date=date.today(),
            raw_data=stock_data,
            asset_type=AssetType.STOCK_A
        )
        
        if not isinstance(stock_fundamental, StockFundamentalData):
            errors.append("股票基本面数据类型不正确")
        else:
            print(f"  股票基本面数据创建成功: {stock_fundamental}")
        
        # 测试创建期货基本面数据
        futures_data = {
            'open_interest': 100000.0,
            'volume': 50000.0,
            'inventory': 10000.0
        }
        futures_fundamental = FundamentalDataFactory.create(
            symbol="CU2400",
            data_date=date.today(),
            raw_data=futures_data,
            asset_type=AssetType.FUTURES
        )
        
        if not isinstance(futures_fundamental, FuturesFundamentalData):
            errors.append("期货基本面数据类型不正确")
        else:
            print(f"  期货基本面数据创建成功: {futures_fundamental}")
        
        # 测试创建加密货币基本面数据
        crypto_data = {
            'market_cap': 1000000000.0,
            'active_addresses': 100000.0,
            'transactions_per_day': 500000.0
        }
        crypto_fundamental = FundamentalDataFactory.create(
            symbol="BTC",
            data_date=date.today(),
            raw_data=crypto_data,
            asset_type=AssetType.CRYPTO
        )
        
        if not isinstance(crypto_fundamental, CryptoFundamentalData):
            errors.append("加密货币基本面数据类型不正确")
        else:
            print(f"  加密货币基本面数据创建成功: {crypto_fundamental}")
        
        # 测试不支持的资产类型
        try:
            FundamentalDataFactory.create(
                symbol="TEST",
                data_date=date.today(),
                raw_data={},
                asset_type=AssetType.BOND
            )
            errors.append("应该抛出异常但不支持的资产类型没有抛出")
        except ValueError:
            print(f"  不支持的资产类型正确抛出异常")
        
        if errors:
            print(f"\n❌ 发现 {len(errors)} 个错误:")
            for error in errors:
                print(f"  - {error}")
            return False
        else:
            print("\n基本面数据工厂逻辑检查通过")
            return True
    
    except Exception as e:
        print(f"\n❌ 基本面数据工厂逻辑检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_fundamental_data_scoring_logic():
    """检查基本面数据评分逻辑"""
    print("\n[2] 检查基本面数据评分逻辑")
    print("-" * 80)
    
    errors = []
    
    try:
        # 测试股票基本面数据评分
        stock_data = {
            'pe_ratio': 15.0,  # 中等估值
            'pb_ratio': 2.5,   # 中等估值
            'roe': 20.0,       # 高盈利能力
            'debt_ratio': 40.0,  # 中等负债
            'roa': 10.0,       # 高资产回报
            'gross_margin': 30.0,  # 中等毛利率
            'net_margin': 15.0,    # 中等净利率
            'revenue_growth': 10.0,  # 正增长
            'profit_growth': 15.0,   # 正增长
            'market_cap': 1000.0    # 中等市值
        }
        
        stock_fundamental = FundamentalDataFactory.create(
            symbol="600000",
            data_date=date.today(),
            raw_data=stock_data,
            asset_type=AssetType.STOCK_A
        )
        
        score = stock_fundamental.get_score()
        score_level = stock_fundamental.get_score_level()
        
        print(f"股票基本面评分: {score:.2f}")
        print(f"评分等级: {score_level.value}")
        
        if not (0 <= score <= 100):
            errors.append(f"股票评分超出范围: {score}")
        
        if not stock_fundamental.validate():
            errors.append("股票基本面数据验证失败")
        
        # 测试期货基本面数据评分
        futures_data = {
            'open_interest': 100000.0,
            'volume': 50000.0,
            'inventory': 10000.0,
            'basis': 10.0,
            'supply_demand_ratio': 1.0
        }
        
        futures_fundamental = FundamentalDataFactory.create(
            symbol="CU2400",
            data_date=date.today(),
            raw_data=futures_data,
            asset_type=AssetType.FUTURES
        )
        
        futures_score = futures_fundamental.get_score()
        futures_score_level = futures_fundamental.get_score_level()
        
        print(f"期货基本面评分: {futures_score:.2f}")
        print(f"评分等级: {futures_score_level.value}")
        
        if not (0 <= futures_score <= 100):
            errors.append(f"期货评分超出范围: {futures_score}")
        
        if not futures_fundamental.validate():
            errors.append("期货基本面数据验证失败")
        
        # 测试加密货币基本面数据评分
        crypto_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'active_addresses': 100000.0,
            'transactions_per_day': 500000.0,
            'hashrate': 100000000000.0,
            'developer_activity': 100.0,
            'github_commits': 1000.0,
            'community_score': 80.0,
            'social_sentiment': 0.5,
            'network_growth': 10.0
        }
        
        crypto_fundamental = FundamentalDataFactory.create(
            symbol="BTC",
            data_date=date.today(),
            raw_data=crypto_data,
            asset_type=AssetType.CRYPTO
        )
        
        crypto_score = crypto_fundamental.get_score()
        crypto_score_level = crypto_fundamental.get_score_level()
        
        print(f"加密货币基本面评分: {crypto_score:.2f}")
        print(f"评分等级: {crypto_score_level.value}")
        
        if not (0 <= crypto_score <= 100):
            errors.append(f"加密货币评分超出范围: {crypto_score}")
        
        if not crypto_fundamental.validate():
            errors.append("加密货币基本面数据验证失败")
        
        if errors:
            print(f"\n❌ 发现 {len(errors)} 个错误:")
            for error in errors:
                print(f"  - {error}")
            return False
        else:
            print("\n基本面数据评分逻辑检查通过")
            return True
    
    except Exception as e:
        print(f"\n❌ 基本面数据评分逻辑检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_selection_strategy_logic():
    """检查选股策略逻辑"""
    print("\n[3] 检查选股策略逻辑")
    print("-" * 80)
    
    errors = []
    
    try:
        # 测试股票价值策略
        stock_strategy = StockValueStrategy()
        
        # 创建测试数据
        stock_fundamentals = []
        for i in range(5):
            stock_data = {
                'pe_ratio': 10.0 + i * 5.0,
                'pb_ratio': 1.5 + i * 0.5,
                'roe': 25.0 - i * 2.0,
                'debt_ratio': 30.0 + i * 5.0
            }
            stock_fundamental = FundamentalDataFactory.create(
                symbol=f"60000{i}",
                data_date=date.today(),
                raw_data=stock_data,
                asset_type=AssetType.STOCK_A
            )
            stock_fundamentals.append(stock_fundamental)
        
        # 测试选股
        criteria = SelectionCriteria(
            asset_type=AssetType.STOCK_A,
            strategy_type=stock_strategy.strategy_type,
            max_assets=3,
            min_score=0.0
        )
        
        result = stock_strategy.select_assets(stock_fundamentals, criteria)
        
        print(f"股票价值选股结果:")
        print(f"  总资产数: {result.metadata['total_assets']}")
        print(f"  过滤后资产数: {result.metadata['filtered_assets']}")
        print(f"  选中资产数: {result.metadata['selected_assets']}")
        print(f"  选中资产: {result.selected_assets}")
        
        if len(result.selected_assets) != 3:
            errors.append(f"选中资产数量不正确: 期望3, 实际{len(result.selected_assets)}")
        
        if not stock_strategy.validate_criteria(criteria):
            errors.append("选股标准验证失败")
        
        # 测试期货动量策略
        futures_strategy = FuturesMomentumStrategy()
        
        futures_fundamentals = []
        for i in range(5):
            futures_data = {
                'open_interest': 50000.0 + i * 10000.0,
                'volume': 30000.0 + i * 5000.0,
                'inventory': 8000.0 + i * 1000.0,
                'basis': 5.0 + i * 2.0
            }
            futures_fundamental = FundamentalDataFactory.create(
                symbol=f"CU240{i}",
                data_date=date.today(),
                raw_data=futures_data,
                asset_type=AssetType.FUTURES
            )
            futures_fundamentals.append(futures_fundamental)
        
        futures_criteria = SelectionCriteria(
            asset_type=AssetType.FUTURES,
            strategy_type=futures_strategy.strategy_type,
            max_assets=3,
            min_score=0.0
        )
        
        futures_result = futures_strategy.select_assets(futures_fundamentals, futures_criteria)
        
        print(f"\n期货动量选股结果:")
        print(f"  总资产数: {futures_result.metadata['total_assets']}")
        print(f"  过滤后资产数: {futures_result.metadata['filtered_assets']}")
        print(f"  选中资产数: {futures_result.metadata['selected_assets']}")
        print(f"  选中资产: {futures_result.selected_assets}")
        
        if not futures_strategy.validate_criteria(futures_criteria):
            errors.append("期货选股标准验证失败")
        
        # 测试加密货币成长策略
        crypto_strategy = CryptoGrowthStrategy()
        
        crypto_fundamentals = []
        for i in range(5):
            crypto_data = {
                'market_cap': 500000000.0 + i * 100000000.0,
                'active_addresses': 50000.0 + i * 10000.0,
                'transactions_per_day': 300000.0 + i * 50000.0,
                'developer_activity': 50.0 + i * 10.0,
                'community_score': 70.0 + i * 5.0,
                'network_growth': 5.0 + i * 2.0
            }
            crypto_fundamental = FundamentalDataFactory.create(
                symbol=f"CRYPTO{i}",
                data_date=date.today(),
                raw_data=crypto_data,
                asset_type=AssetType.CRYPTO
            )
            crypto_fundamentals.append(crypto_fundamental)
        
        crypto_criteria = SelectionCriteria(
            asset_type=AssetType.CRYPTO,
            strategy_type=crypto_strategy.strategy_type,
            max_assets=3,
            min_score=0.0
        )
        
        crypto_result = crypto_strategy.select_assets(crypto_fundamentals, crypto_criteria)
        
        print(f"\n加密货币成长选股结果:")
        print(f"  总资产数: {crypto_result.metadata['total_assets']}")
        print(f"  过滤后资产数: {crypto_result.metadata['filtered_assets']}")
        print(f"  选中资产数: {crypto_result.metadata['selected_assets']}")
        print(f"  选中资产: {crypto_result.selected_assets}")
        
        if not crypto_strategy.validate_criteria(crypto_criteria):
            errors.append("加密货币选股标准验证失败")
        
        if errors:
            print(f"\n❌ 发现 {len(errors)} 个错误:")
            for error in errors:
                print(f"  - {error}")
            return False
        else:
            print("\n选股策略逻辑检查通过")
            return True
    
    except Exception as e:
        print(f"\n❌ 选股策略逻辑检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 80)
    print("逻辑正确性检查")
    print("=" * 80)
    
    results = []
    
    # 检查基本面数据工厂逻辑
    results.append(("基本面数据工厂逻辑", check_fundamental_data_factory_logic()))
    
    # 检查基本面数据评分逻辑
    results.append(("基本面数据评分逻辑", check_fundamental_data_scoring_logic()))
    
    # 检查选股策略逻辑
    results.append(("选股策略逻辑", check_selection_strategy_logic()))
    
    # 汇总报告
    print("\n" + "=" * 80)
    print("汇总报告")
    print("=" * 80)
    
    for name, result in results:
        status = "通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 所有逻辑检查通过！")
        return 0
    else:
        print("\n⚠️  部分逻辑检查失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
