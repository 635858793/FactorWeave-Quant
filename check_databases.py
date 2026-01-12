#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接检查数据库文件
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        import duckdb
        import sqlite3
        
        # 检查 DuckDB 数据库
        print("检查 DuckDB 数据库...")
        try:
            conn = duckdb.connect('data/factorweave_analytics.duckdb')
            
            # 检查表
            tables = conn.execute("SHOW TABLES").fetchall()
            print(f"DuckDB 表: {[t[0] for t in tables]}")
            
            # 检查 stocks 表
            if 'stocks' in [t[0] for t in tables]:
                count = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
                print(f"stocks 表行数: {count}")
                
                if count > 0:
                    print("\nstocks 表前5行:")
                    rows = conn.execute("SELECT * FROM stocks LIMIT 5").fetchall()
                    columns = [desc[0] for desc in conn.description]
                    print(f"列: {columns}")
                    for row in rows:
                        print(row)
            
            conn.close()
        except Exception as e:
            print(f"检查 DuckDB 失败: {e}")
        
        # 检查 SQLite 数据库
        print("\n检查 SQLite 数据库...")
        try:
            conn = sqlite3.connect('data/factorweave_system.sqlite')
            cursor = conn.cursor()
            
            # 检查表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"SQLite 表: {[t[0] for t in tables]}")
            
            # 检查 stocks 表
            if ('stocks',) in tables:
                cursor.execute("SELECT COUNT(*) FROM stocks")
                count = cursor.fetchone()[0]
                print(f"stocks 表行数: {count}")
                
                if count > 0:
                    print("\nstocks 表前5行:")
                    cursor.execute("SELECT * FROM stocks LIMIT 5")
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    print(f"列: {columns}")
                    for row in rows:
                        print(row)
            
            conn.close()
        except Exception as e:
            print(f"检查 SQLite 失败: {e}")
        
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())