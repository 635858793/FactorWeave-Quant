#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查所有资产数据库的表结构
"""

import sys
import os

def check_all_tables():
    """检查所有资产数据库的表结构"""
    try:
        import duckdb
        
        # 资产类型列表
        asset_types = [
            'stock_a', 'stock_b', 'stock_h', 'stock_hk', 'stock_us',
            'crypto', 'fund', 'bond', 'index', 'commodity', 'futures',
            'warrant', 'option', 'sector', 'macro'
        ]
        
        print("检查所有资产数据库的表结构...")
        print("=" * 60)
        
        for asset_type in asset_types:
            db_path = f'data/databases/{asset_type}/{asset_type}_data.duckdb'
            
            if not os.path.exists(db_path):
                continue
            
            print(f"\n=== {asset_type} ===")
            
            try:
                conn = duckdb.connect(db_path)
                
                # 获取所有表
                tables = conn.execute("SHOW TABLES").fetchall()
                print(f"表数量: {len(tables)}")
                
                # 检查是否有 stock_list 或 asset_metadata 表
                table_names = [table[0] for table in tables]
                
                if 'stock_list' in table_names:
                    print("  ✓ 有 stock_list 表")
                    # 检查表结构
                    columns = conn.execute("DESCRIBE stock_list").fetchall()
                    print(f"  列: {[col[0] for col in columns]}")
                elif 'asset_metadata' in table_names:
                    print("  ✓ 有 asset_metadata 表")
                    # 检查表结构
                    columns = conn.execute("DESCRIBE asset_metadata").fetchall()
                    print(f"  列: {[col[0] for col in columns]}")
                else:
                    print(f"  ✗ 没有 stock_list 或 asset_metadata 表")
                    print(f"  表列表: {table_names}")
                
                conn.close()
                
            except Exception as e:
                print(f"检查失败: {e}")
        
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(check_all_tables())
