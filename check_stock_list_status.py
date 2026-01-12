#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查 stock_list 表中的数据状态
"""

import sys

def check_stock_list_status():
    """检查 stock_list 表中的数据状态"""
    try:
        import duckdb
        
        print("检查 stock_list 表中的数据状态...")
        print("=" * 60)
        
        # 连接数据库
        conn = duckdb.connect('data/databases/stock_a/stock_a_data.duckdb')
        
        # 检查总行数
        total_count = conn.execute("SELECT COUNT(*) FROM stock_list").fetchone()[0]
        print(f"\n总行数: {total_count}")
        
        # 检查 status 字段的分布
        print("\nstatus 字段分布:")
        status_dist = conn.execute("SELECT status, COUNT(*) FROM stock_list GROUP BY status").fetchall()
        for status, count in status_dist:
            print(f"  {status}: {count}")
        
        # 检查 market 字段的分布
        print("\nmarket 字段分布:")
        market_dist = conn.execute("SELECT market, COUNT(*) FROM stock_list GROUP BY market").fetchall()
        for market, count in market_dist:
            print(f"  {market}: {count}")
        
        # 检查是否有 status = 'active' 的数据
        active_count = conn.execute("SELECT COUNT(*) FROM stock_list WHERE status = 'active'").fetchone()[0]
        print(f"\nstatus = 'active' 的行数: {active_count}")
        
        # 显示前 5 行数据
        print("\n前 5 行数据:")
        rows = conn.execute("SELECT * FROM stock_list LIMIT 5").fetchall()
        columns = [desc[0] for desc in conn.description]
        print(f"列: {columns}")
        for row in rows:
            print(f"  {row}")
        
        # 检查是否有其他状态值
        print("\n所有不同的 status 值:")
        status_values = conn.execute("SELECT DISTINCT status FROM stock_list").fetchall()
        for status in status_values:
            print(f"  {status[0]}")
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(check_stock_list_status())
