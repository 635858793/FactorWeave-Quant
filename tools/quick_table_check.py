#!/usr/bin/env python3
"""
快速表结构检查脚本
检查所有表类型的Schema定义和索引配置
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.table_manager import TableType, TableSchemaRegistry

def main():
    print("🔍 检查表结构和索引配置...")
    
    # 初始化Schema注册表
    registry = TableSchemaRegistry()
    
    # 获取所有表类型
    all_table_types = [
        TableType.STOCK_BASIC_INFO,
        TableType.KLINE_DATA,
        TableType.FINANCIAL_STATEMENT,
        TableType.MACRO_ECONOMIC,
        TableType.REAL_TIME_QUOTE,
        TableType.MARKET_DEPTH,
        TableType.TRADE_TICK,
        TableType.NEWS,
        TableType.ANNOUNCEMENT,
        TableType.FUND_FLOW,
        TableType.TECHNICAL_INDICATOR
    ]
    
    print(f"📊 系统定义了 {len(all_table_types)} 种表类型")
    print()
    
    missing_schemas = []
    incomplete_schemas = []
    complete_schemas = []
    
    for table_type in all_table_types:
        print(f"检查表类型: {table_type.value}")
        
        # 获取Schema
        schema = registry.get_schema(table_type)
        
        if schema is None:
            missing_schemas.append(table_type.value)
            print(f"  ❌ Schema定义: 缺失")
            continue
        
        # 检查必要字段
        required_fields = ['data_source', 'created_at', 'data_quality_score', 'plugin_specific_data']
        missing_fields = [f for f in required_fields if f not in schema.columns]
        
        # 检查主键
        has_primary_key = len(schema.primary_key) > 0
        
        # 检查索引
        has_indexes = len(schema.indexes) > 0
        has_data_source_index = any('data_source' in idx.get('columns', []) for idx in schema.indexes)
        
        print(f"  Schema定义: 存在")
        print(f"  📊 字段数量: {len(schema.columns)}")
        print(f"  🔑 主键: {schema.primary_key if has_primary_key else '❌ 缺失'}")
        print(f"  📇 索引数量: {len(schema.indexes)}")
        print(f"  🏷️ 数据源索引: {'存在' if has_data_source_index else '❌ 缺失'}")
        
        if missing_fields:
            print(f"  ⚠️ 缺失必要字段: {missing_fields}")
        
        # 显示分区信息
        if schema.partitions:
            print(f"  📂 分区策略: {schema.partitions['type']} by {schema.partitions['column']} ({schema.partitions['interval']})")
        else:
            print(f"  📂 分区策略: 无")
        
        # 评估完整性
        issues = []
        if missing_fields:
            issues.append(f"缺失字段: {missing_fields}")
        if not has_primary_key:
            issues.append("无主键")
        if not has_indexes:
            issues.append("无索引")
        if not has_data_source_index:
            issues.append("无数据源索引")
        
        if issues:
            incomplete_schemas.append({'type': table_type.value, 'issues': issues})
            print(f"  ⚠️ 存在问题: {'; '.join(issues)}")
        else:
            complete_schemas.append(table_type.value)
            print(f"  配置完整")
        
        print()
    
    # 总结报告
    print("="*60)
    print("📋 表结构检查总结")
    print("="*60)
    print(f"完整配置: {len(complete_schemas)}/{len(all_table_types)} 种表类型")
    print(f"⚠️ 不完整配置: {len(incomplete_schemas)} 种表类型")
    print(f"❌ 缺失Schema: {len(missing_schemas)} 种表类型")
    
    if complete_schemas:
        print(f"\n完整配置的表类型:")
        for table_type in complete_schemas:
            print(f"  - {table_type}")
    
    if incomplete_schemas:
        print(f"\n⚠️ 不完整配置的表类型:")
        for item in incomplete_schemas:
            print(f"  - {item['type']}: {'; '.join(item['issues'])}")
    
    if missing_schemas:
        print(f"\n❌ 缺失Schema的表类型:")
        for table_type in missing_schemas:
            print(f"  - {table_type}")
    
    print()
    
    # 计算成功率
    success_rate = len(complete_schemas) / len(all_table_types) * 100
    print(f"🎯 整体完整性: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("🎉 所有表结构配置完整！")
    elif success_rate >= 90:
        print("表结构基本完整，存在少量问题")
    elif success_rate >= 70:
        print("⚠️ 表结构大部分完整，需要关注一些问题")
    else:
        print("❌ 表结构存在较多问题，需要修复")

if __name__ == "__main__":
    main()
