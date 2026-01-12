#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

检查所有股票类型数据库的 asset_metadata 表数据量
"""

import sys

def check_all_stock_databases():
    """检查所有股票类型数据库的 asset_metadata 表数据量"""
    try:
        import duckdb
        
        print("检查所有股票类型数据库的 asset_metadata 表数据量...")
        print("=" * 60)
        
        stock_types = ['stock_a', 'stock_b', 'stock_h', 'stock_hk', 'stock_us']
        
        for stock_type in stock_types:
            db_path = f'data/databases/{stock_type}/{stock_type}_data.duckdb'
            
            if not os.path.exists(db_path):
                print(f"\n{stock_type}: 数据库文件不存在")
                continue
            
            try:
                conn = duckdb.connect(db_path)
                
                # 检查 asset_metadata 表是否存在
                tables = conn.execute("SHOW TABLES").fetchall()
                table_names = [table[0] for table in tables]
                
                if 'asset_metadata' not in table_names:
                    print(f"\n{stock_type}: 没有 asset_metadata 表")
                    conn.close()
                    continue
                
                # 检查 asset_metadata 表的数据量
                count = conn.execute("SELECT COUNT(*) FROM asset_metadata").fetchone()[0]
                print(f"\n{stock_type}: {count} 行数据")
                
                if count > 0:
                    # 显示前 3 行数据
                    rows = conn.execute("SELECT * FROM asset_metadata LIMIT 3").fetchall()
                    print("  前 3 行:")
                    for row in rows:
                        print(f"    {row}")
                
                conn.close()
                
            except Exception as e:
                print(f"\n{stock_type}: 检查失败 - {e}")
        
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    import os
    sys.exit(check_all_stock_databases())
