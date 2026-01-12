#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找包含股票数据的表
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        import duckdb
        import sqlite3
        
        # 检查 SQLite 数据库中的表
        print("检查 SQLite 数据库中的表...")
        try:
            conn = sqlite3.connect('data/factorweave_system.sqlite')
            cursor = conn.cursor()
            
            # 检查表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"SQLite 表: {[t[0] for t in tables]}")
            
            # 检查每个表的行数
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    print(f"{table_name}: {count} 行")
                    
                    # 如果表有数据，显示前几行
                    if count > 0 and count < 100:
                        print(f"  前5行:")
                        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                        rows = cursor.fetchall()
                        columns = [desc[0] for desc in cursor.description]
                        print(f"  列: {columns}")
                        for row in rows:
                            print(f"  {row}")
                except Exception as e:
                    print(f"{table_name}: 查询失败 - {e}")
            
            conn.close()
        except Exception as e:
            print(f"检查 SQLite 失败: {e}")
        
        # 检查 DuckDB 数据库中的表
        print("\n检查 DuckDB 数据库中的表...")
        try:
            conn = duckdb.connect('data/factorweave_analytics.duckdb')
            
            # 检查表
            tables = conn.execute("SHOW TABLES").fetchall()
            print(f"DuckDB 表: {[t[0] for t in tables]}")
            
            # 检查每个表的行数
            for table in tables:
                table_name = table[0]
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                    print(f"{table_name}: {count} 行")
                    
                    # 如果表有数据，显示前几行
                    if count > 0 and count < 100:
                        print(f"  前5行:")
                        rows = conn.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchall()
                        columns = [desc[0] for desc in conn.description]
                        print(f"  列: {columns}")
                        for row in rows:
                            print(f"  {row}")
                except Exception as e:
                    print(f"{table_name}: 查询失败 - {e}")
            
            conn.close()
        except Exception as e:
            print(f"检查 DuckDB 失败: {e}")
        
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())