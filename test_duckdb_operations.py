#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 duckdb_operations.query_data 方法
"""

import sys

def test_duckdb_operations():
    """测试 duckdb_operations.query_data 方法"""
    try:
        from core.database.duckdb_operations import get_duckdb_operations
        from core.plugin_types import AssetType
        
        print("测试 duckdb_operations.query_data 方法...")
        print("=" * 60)
        
        # 获取 DuckDB 操作器
        duckdb_ops = get_duckdb_operations()
        
        print("✅ DuckDB 操作器初始化成功")
        
        # 构建查询
        query = """
        SELECT DISTINCT 
            symbol as code,
            name,
            market,
            CASE WHEN industry IS NOT NULL AND industry != '' THEN industry ELSE NULL END as industry,
            CASE WHEN sector IS NOT NULL AND sector != '' THEN sector ELSE NULL END as sector,
            listing_date as list_date,
            listing_status as status
        FROM asset_metadata 
        WHERE listing_status = 'active'
          AND asset_type = 'stock_a'
        ORDER BY symbol
        """
        
        # 执行查询
        print("\n执行查询...")
        result = duckdb_ops.query_data(
            database_path='data/databases/stock_a/stock_a_data.duckdb',
            table_name='asset_metadata',
            custom_sql=query
        )
        
        print(f"查询结果:")
        print(f"  success: {result.success}")
        print(f"  row_count: {result.row_count}")
        print(f"  execution_time: {result.execution_time:.3f}秒")
        print(f"  columns: {result.columns}")
        
        if result.success and not result.data.empty:
            print(f"\n✅ 查询成功，返回 {len(result.data)} 行数据")
            print("\n前 5 行数据:")
            print(result.data.head())
        else:
            print(f"\n❌ 查询失败")
            if result.error_message:
                print(f"错误信息: {result.error_message}")
        
        return 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(test_duckdb_operations())
