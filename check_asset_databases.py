#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查独立资产数据库的内容
"""

import sys
import os

def check_stock_a_database():
    """检查A股数据库的表结构和数据"""
    try:
        import duckdb
        
        print("检查 stock_a_data.duckdb 数据库...")
        print("=" * 60)
        
        # 连接数据库
        conn = duckdb.connect('data/databases/stock_a/stock_a_data.duckdb')
        
        # 获取所有表
        print("\n=== 所有表 ===")
        tables = conn.execute("SHOW TABLES").fetchall()
        print(f"表数量: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 检查每个表的结构和数据
        for table in tables:
            table_name = table[0]
            print(f"\n=== 表: {table_name} ===")
            
            # 获取表结构
            print("\n表结构:")
            columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
            for col in columns:
                print(f"  {col[0]}: {col[1]}")
            
            # 获取行数
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"\n行数: {count}")
            
            # 如果有数据，显示前几行
            if count > 0:
                print(f"\n前5行数据:")
                rows = conn.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchall()
                for row in rows:
                    print(f"  {row}")
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

def check_all_asset_databases():
    """检查所有资产数据库"""
    try:
        import duckdb
        
        # 资产类型列表
        asset_types = [
            'stock_a', 'stock_b', 'stock_h', 'stock_hk', 'stock_us',
            'crypto', 'fund', 'bond', 'index', 'commodity', 'futures',
            'forex', 'warrant', 'option', 'sector', 'macro'
        ]
        
        print("\n检查所有资产数据库...")
        print("=" * 60)
        
        for asset_type in asset_types:
            db_path = f'data/databases/{asset_type}/{asset_type}_data.duckdb'
            
            if not os.path.exists(db_path):
                print(f"\n{asset_type}: 数据库文件不存在")
                continue
            
            print(f"\n=== {asset_type} ===")
            
            try:
                conn = duckdb.connect(db_path)
                
                # 获取所有表
                tables = conn.execute("SHOW TABLES").fetchall()
                print(f"表数量: {len(tables)}")
                
                # 获取总数据量
                total_rows = 0
                for table in tables:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
                    total_rows += count
                
                print(f"总数据量: {total_rows} 行")
                
                conn.close()
                
            except Exception as e:
                print(f"检查失败: {e}")
        
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """主函数"""
    try:
        # 检查A股数据库的详细信息
        check_stock_a_database()
        
        # 检查所有资产数据库的概览
        check_all_asset_databases()
        
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
