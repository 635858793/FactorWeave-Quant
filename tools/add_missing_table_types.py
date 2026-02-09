#!/usr/bin/env python3
"""
为量化系统添加缺失的表类型
基于深度分析结果，扩展TableType枚举和Schema定义
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def show_missing_table_types():
    """显示量化系统中缺失的重要表类型"""

    print("🔍 量化系统中缺失的重要表类型分析")
    print("="*60)

    missing_types = [
        {
            "name": "OPTION_DATA",
            "description": "期权数据表",
            "fields": ["symbol", "underlying", "strike_price", "expiry_date", "option_type", "greeks"],
            "importance": "高 - 衍生品交易必需"
        },
        {
            "name": "FUTURES_DATA",
            "description": "期货数据表",
            "fields": ["symbol", "contract_month", "delivery_date", "open_interest", "settlement_price"],
            "importance": "高 - 期货交易必需"
        },
        {
            "name": "BOND_DATA",
            "description": "债券数据表",
            "fields": ["symbol", "coupon_rate", "maturity_date", "yield_to_maturity", "credit_rating"],
            "importance": "中 - 固收投资需要"
        },
        {
            "name": "INDEX_DATA",
            "description": "指数数据表",
            "fields": ["symbol", "constituents", "weights", "divisor", "calculation_method"],
            "importance": "高 - 指数基金和ETF必需"
        },
        {
            "name": "PORTFOLIO_DATA",
            "description": "组合数据表",
            "fields": ["portfolio_id", "symbol", "quantity", "weight", "cost_basis", "market_value"],
            "importance": "高 - 组合管理核心"
        },
        {
            "name": "ORDER_DATA",
            "description": "订单数据表",
            "fields": ["order_id", "symbol", "side", "quantity", "price", "order_type", "status"],
            "importance": "高 - 交易执行核心"
        },
        {
            "name": "ACCOUNT_DATA",
            "description": "账户数据表",
            "fields": ["account_id", "cash", "total_value", "buying_power", "margin_used"],
            "importance": "高 - 资金管理核心"
        },
        {
            "name": "STRATEGY_DATA",
            "description": "策略数据表",
            "fields": ["strategy_id", "signal_type", "signal_value", "confidence", "timestamp"],
            "importance": "高 - 量化策略核心"
        },
        {
            "name": "RISK_METRICS",
            "description": "风险指标表",
            "fields": ["symbol", "var", "cvar", "beta", "volatility", "correlation_matrix"],
            "importance": "高 - 风险管理必需"
        },
        {
            "name": "EVENT_DATA",
            "description": "事件数据表",
            "fields": ["symbol", "event_type", "ex_date", "record_date", "amount", "announcement_date"],
            "importance": "中 - 除权除息处理"
        },
        {
            "name": "FACTOR_DATA",
            "description": "因子数据表",
            "fields": ["symbol", "factor_name", "factor_value", "factor_exposure", "date"],
            "importance": "高 - 多因子模型核心"
        },
        {
            "name": "ASSET_LIST",
            "description": "资产列表表",
            "fields": ["symbol", "name", "asset_type", "exchange", "listing_status", "sector"],
            "importance": "中 - 资产管理基础"
        },
        {
            "name": "SECTOR_DATA",
            "description": "板块数据表",
            "fields": ["sector_code", "sector_name", "constituents", "market_cap", "performance"],
            "importance": "中 - 板块分析需要"
        },
        {
            "name": "PATTERN_RECOGNITION",
            "description": "形态识别表",
            "fields": ["symbol", "pattern_type", "pattern_score", "start_date", "end_date"],
            "importance": "中 - 技术分析增强"
        },
        {
            "name": "INTRADAY_DATA",
            "description": "分时数据表",
            "fields": ["symbol", "minute", "price", "volume", "vwap", "bid_ask_spread"],
            "importance": "高 - 日内交易必需"
        }
    ]

    print(f"发现 {len(missing_types)} 种重要的缺失表类型：")
    print()

    for i, table_type in enumerate(missing_types, 1):
        print(f"{i:2d}. {table_type['name']}")
        print(f"    描述: {table_type['description']}")
        print(f"    重要性: {table_type['importance']}")
        print(f"    关键字段: {', '.join(table_type['fields'][:5])}...")
        print()

    print("📊 优先级分析：")
    high_priority = [t for t in missing_types if t['importance'].startswith('高')]
    medium_priority = [t for t in missing_types if t['importance'].startswith('中')]

    print(f"🔴 高优先级 ({len(high_priority)}个): 量化交易核心功能")
    for t in high_priority:
        print(f"   - {t['name']}: {t['description']}")

    print(f"\n🟡 中优先级 ({len(medium_priority)}个): 功能增强和完善")
    for t in medium_priority:
        print(f"   - {t['name']}: {t['description']}")

    print("\n💡 建议：")
    print("1. 优先实现高优先级表类型以支持核心量化交易功能")
    print("2. 逐步添加中优先级表类型以完善系统功能")
    print("3. 考虑表之间的关联关系和数据一致性")
    print("4. 针对高频数据优化索引和分区策略")

def show_existing_table_issues():
    """显示现有表结构的问题"""

    print("\n🔧 现有表结构问题分析")
    print("="*60)

    issues = [
        {
            "table": "KLINE_DATA",
            "issues": [
                "缺少复权类型字段 (adj_type)",
                "缺少交易状态字段 (trade_status)",
                "缺少市场类型字段 (market_type)",
                "缺少币种字段 (currency)",
                "复权因子历史记录机制缺失"
            ],
            "severity": "中"
        },
        {
            "table": "REAL_TIME_QUOTE",
            "issues": [
                "缺少委比委差字段",
                "缺少实时市值字段",
                "缺少实时PE/PB字段",
                "缺少振幅字段",
                "缺少5分钟涨幅字段"
            ],
            "severity": "中"
        },
        {
            "table": "TRADE_TICK",
            "issues": [
                "时间精度不足(缺少毫秒级)",
                "seq_number唯一性保证不足",
                "缺少交易所原始时间戳",
                "主键设计不利于时间查询"
            ],
            "severity": "高"
        },
        {
            "table": "TECHNICAL_INDICATOR",
            "issues": [
                "只有5个value字段，复杂指标存储困难",
                "缺少指标依赖关系记录",
                "缺少指标有效期管理",
                "缺少指标计算状态跟踪"
            ],
            "severity": "中"
        },
        {
            "table": "全局问题",
            "issues": [
                "缺少交易日历表",
                "symbol命名规范不统一",
                "时区处理不一致",
                "跨表数据一致性保证不足",
                "外键关系定义缺失",
                "数据去重策略不明确"
            ],
            "severity": "高"
        }
    ]

    for issue_group in issues:
        severity_color = "🔴" if issue_group["severity"] == "高" else "🟡"
        print(f"{severity_color} {issue_group['table']} (严重程度: {issue_group['severity']})")
        for issue in issue_group["issues"]:
            print(f"   - {issue}")
        print()

def show_datatype_mapping_issues():
    """显示DataType映射不一致问题"""

    print("\n🔗 DataType映射不一致问题")
    print("="*60)

    # plugin_types.py中定义但TableType中没有对应的DataType
    missing_mappings = [
        "ASSET_LIST",
        "FUNDAMENTAL",
        "SECTOR_FUND_FLOW",
        "INDIVIDUAL_FUND_FLOW",
        "MAIN_FUND_FLOW",
        "SECTOR_DATA",
        "CONCEPT_DATA",
        "INDUSTRY_DATA",
        "PATTERN_RECOGNITION",
        "SENTIMENT_DATA",
        "REAL_TIME_FUND_FLOW",
        "REAL_TIME_SECTOR",
        "INTRADAY_DATA"
    ]

    print("❌ plugin_types.py中定义但TableType中无对应的DataType:")
    for i, dt in enumerate(missing_mappings, 1):
        print(f"{i:2d}. {dt}")

    print(f"\n统计: {len(missing_mappings)} 个DataType缺少对应的TableType")

    print("\n⚠️ 名称不一致:")
    print("- DataType.TECHNICAL_INDICATORS vs TableType.TECHNICAL_INDICATOR")

    print("\n💡 建议:")
    print("1. 为所有DataType创建对应的TableType")
    print("2. 统一命名规范（单数vs复数）")
    print("3. 确保DataType到TableType的映射完整性")

def main():
    """主函数"""
    print("🎯 量化系统表结构深度分析工具")
    print("基于对现有11种表类型的深度分析，识别量化系统中的缺失和问题")
    print()

    # 显示缺失的表类型
    show_missing_table_types()

    # 显示现有表结构问题
    show_existing_table_issues()

    # 显示DataType映射问题
    show_datatype_mapping_issues()

    print("\n" + "="*60)
    print("📋 总结")
    print("="*60)
    print("已实现: 11种基础表类型")
    print("❌ 缺失: 约15种量化系统核心表类型")
    print("⚠️ 问题: 现有表结构设计和映射不完整")
    print("🎯 覆盖率: 约40% (11/26种需求表类型)")

    print("\n🚀 下一步行动建议:")
    print("1. 优先添加高优先级的缺失表类型")
    print("2. 修复现有表结构的设计问题")
    print("3. 完善DataType到TableType的映射")
    print("4. 添加表关系约束和业务逻辑")
    print("5. 优化索引和分区策略")

if __name__ == "__main__":
    main()
