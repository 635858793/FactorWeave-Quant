#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中的资产数据
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 禁用日志
os.environ['LOGURU_LEVEL'] = 'CRITICAL'

def main():
    try:
        from core.containers import get_service_container
        from core.services.service_bootstrap import ServiceBootstrap
        from core.services.unified_data_manager import UnifiedDataManager
        
        # 引导服务
        bootstrap = ServiceBootstrap()
        bootstrap.bootstrap()
        
        # 获取服务容器
        container = get_service_container()
        
        # 获取数据管理器
        data_manager = container.resolve(UnifiedDataManager)
        
        # 检查股票列表
        print("检查股票列表...")
        stock_list = data_manager.get_asset_list('stock_a')
        print(f"股票列表行数: {len(stock_list)}")
        print(f"股票列表列: {list(stock_list.columns)}")
        
        if not stock_list.empty:
            print("\n前5只股票:")
            print(stock_list.head())
        else:
            print("\n股票列表为空!")
        
        # 检查其他资产类型
        asset_types = ['stock_a', 'stock_b', 'stock_h', 'stock_us', 'stock_hk', 'crypto', 'fund', 'bond', 'index']
        
        print("\n检查其他资产类型:")
        for asset_type in asset_types:
            asset_list = data_manager.get_asset_list(asset_type)
            print(f"{asset_type}: {len(asset_list)} 个资产")
        
        # 检查 DuckDB 数据库
        print("\n检查 DuckDB 数据库...")
        if data_manager.duckdb_available and data_manager.duckdb_operations:
            try:
                import duckdb
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
                        for row in rows:
                            print(row)
                
                conn.close()
            except Exception as e:
                print(f"检查 DuckDB 失败: {e}")
        
        # 检查 SQLite 数据库
        print("\n检查 SQLite 数据库...")
        try:
            import sqlite3
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