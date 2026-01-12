#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 asset_metadata 表的查询
"""

import sys

def test_asset_metadata_query():
    """测试 asset_metadata 表的查询"""
    try:
        import duckdb
        
        print("测试 asset_metadata 表的查询...")
        print("=" * 60)
        
        # 连接数据库
        conn = duckdb.connect('data/databases/stock_a/stock_a_data.duckdb')
        
        # 测试 1: 查询所有数据
        print("\n测试 1: 查询所有数据")
        query1 = """
        SELECT 
            symbol as code,
            name,
            market,
            CASE WHEN industry IS NOT NULL AND industry != '' THEN industry ELSE NULL END as industry,
            CASE WHEN sector IS NOT NULL AND sector != '' THEN sector ELSE NULL END as sector,
            listing_date as list_date,
            listing_status as status
        FROM asset_metadata
        """
        result1 = conn.execute(query1).fetchall()
        print(f"结果: {len(result1)} 行")
        if result1:
            print("前 3 行:")
            for row in result1[:3]:
                print(f"  {row}")
        
        # 测试 2: 查询 listing_status = 'active' 的数据
        print("\n测试 2: 查询 listing_status = 'active' 的数据")
        query2 = """
        SELECT 
            symbol as code,
            name,
            market,
            CASE WHEN industry IS NOT NULL AND industry != '' THEN industry ELSE NULL END as industry,
            CASE WHEN sector IS NOT NULL AND sector != '' THEN sector ELSE NULL END as sector,
            listing_date as list_date,
            listing_status as status
        FROM asset_metadata
        WHERE listing_status = 'active'
        """
        result2 = conn.execute(query2).fetchall()
        print(f"结果: {len(result2)} 行")
        if result2:
            print("前 3 行:")
            for row in result2[:3]:
                print(f"  {row}")
        
        # 测试 3: 查询 asset_type = 'stock_a' 的数据
        print("\n测试 3: 查询 asset_type = 'stock_a' 的数据")
        query3 = """
        SELECT 
            symbol as code,
            name,
            market,
            CASE WHEN industry IS NOT NULL AND industry != '' THEN industry ELSE NULL END as industry,
            CASE WHEN sector IS NOT NULL AND sector != '' THEN sector ELSE NULL END as sector,
            listing_date as list_date,
            listing_status as status
        FROM asset_metadata
        WHERE asset_type = 'stock_a'
        """
        result3 = conn.execute(query3).fetchall()
        print(f"结果: {len(result3)} 行")
        if result3:
            print("前 3 行:")
            for row in result3[:3]:
                print(f"  {row}")
        
        # 测试 4: 查询同时满足 listing_status = 'active' 和 asset_type = 'stock_a' 的数据
        print("\n测试 4: 查询同时满足 listing_status = 'active' 和 asset_type = 'stock_a' 的数据")
        query4 = """
        SELECT 
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
        """
        result4 = conn.execute(query4).fetchall()
        print(f"结果: {len(result4)} 行")
        if result4:
            print("前 3 行:")
            for row in result4[:3]:
                print(f"  {row}")
        
        # 测试 5: 检查 listing_status 字段的值
        print("\n测试 5: 检查 listing_status 字段的值")
        status_values = conn.execute("SELECT DISTINCT listing_status FROM asset_metadata").fetchall()
        print(f"listing_status 的值: {status_values}")
        
        # 测试 6: 检查 asset_type 字段的值
        print("\n测试 6: 检查 asset_type 字段的值")
        asset_type_values = conn.execute("SELECT DISTINCT asset_type FROM asset_metadata").fetchall()
        print(f"asset_type 的值: {asset_type_values}")
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(test_asset_metadata_query())
