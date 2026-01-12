#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
重新检查 stock_a_data.duckdb 数据库的表结构
"""

import sys

def check_stock_a_tables():
    """检查 stock_a_data.duckdb 数据库的表结构"""
    try:
        import duckdb
        
        print("重新检查 stock_a_data.duckdb 数据库的表结构...")
        print("=" * 60)
        
        # 连接数据库
        conn = duckdb.connect('data/databases/stock_a/stock_a_data.duckdb')
        
        # 获取所有表
        print("\n所有表:")
        tables = conn.execute("SHOW TABLES").fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        
        # 检查每个表的行数
        print("\n每个表的行数:")
        for table in tables:
            table_name = table[0]
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                print(f"  {table_name}: {count}")
            except Exception as e:
                print(f"  {table_name}: 查询失败 - {e}")
        
        # 检查是否有包含股票列表信息的表
        print("\n查找包含股票列表信息的表...")
        for table in tables:
            table_name = table[0]
            try:
                # 检查表结构
                columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
                column_names = [col[0] for col in columns]
                
                # 检查是否包含关键字段
                if 'symbol' in column_names and 'name' in column_names:
                    print(f"\n  表 {table_name} 可能包含股票列表信息:")
                    print(f"    列: {column_names}")
                    
                    # 显示前 3 行数据
                    rows = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchall()
                    print(f"    前 3 行数据:")
                    for row in rows:
                        print(f"      {row}")
            except Exception as e:
                pass
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(check_stock_a_tables())
