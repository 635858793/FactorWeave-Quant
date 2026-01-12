#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 industry、market、concept 表的结构
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        import sqlite3
        
        # 检查 SQLite 数据库
        print("检查 SQLite 数据库表结构...")
        try:
            conn = sqlite3.connect('data/factorweave_system.sqlite')
            cursor = conn.cursor()
            
            # 检查 industry 表
            print("\n=== industry 表 ===")
            cursor.execute("PRAGMA table_info(industry)")
            columns = cursor.fetchall()
            print(f"列: {[col[1] for col in columns]}")
            
            cursor.execute("SELECT COUNT(*) FROM industry")
            count = cursor.fetchone()[0]
            print(f"行数: {count}")
            
            if count > 0:
                print("前5行:")
                cursor.execute("SELECT * FROM industry LIMIT 5")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  {row}")
            
            # 检查 market 表
            print("\n=== market 表 ===")
            cursor.execute("PRAGMA table_info(market)")
            columns = cursor.fetchall()
            print(f"列: {[col[1] for col in columns]}")
            
            cursor.execute("SELECT COUNT(*) FROM market")
            count = cursor.fetchone()[0]
            print(f"行数: {count}")
            
            if count > 0:
                print("前5行:")
                cursor.execute("SELECT * FROM market LIMIT 5")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  {row}")
            
            # 检查 concept 表
            print("\n=== concept 表 ===")
            cursor.execute("PRAGMA table_info(concept)")
            columns = cursor.fetchall()
            print(f"列: {[col[1] for col in columns]}")
            
            cursor.execute("SELECT COUNT(*) FROM concept")
            count = cursor.fetchone()[0]
            print(f"行数: {count}")
            
            if count > 0:
                print("前5行:")
                cursor.execute("SELECT * FROM concept LIMIT 5")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  {row}")
            
            # 检查 data_source 表
            print("\n=== data_source 表 ===")
            cursor.execute("PRAGMA table_info(data_source)")
            columns = cursor.fetchall()
            print(f"列: {[col[1] for col in columns]}")
            
            cursor.execute("SELECT COUNT(*) FROM data_source")
            count = cursor.fetchone()[0]
            print(f"行数: {count}")
            
            if count > 0:
                print("前5行:")
                cursor.execute("SELECT * FROM data_source LIMIT 5")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  {row}")
            
            conn.close()
        except Exception as e:
            print(f"检查 SQLite 失败: {e}")
            import traceback
            traceback.print_exc()
        
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())