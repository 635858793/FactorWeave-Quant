"""
测试订单数据库自动创建
"""

import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.services.database_service import DatabaseService

def main():
    """主函数"""
    print("测试订单数据库自动创建...")
    
    try:
        # 初始化数据库服务
        db_service = DatabaseService.get_instance()
        
        # 检查订单数据库连接池是否创建
        print("\n检查订单数据库连接池...")
        order_pools = [pool_name for pool_name in db_service._connection_pools.keys() if "_orders" in pool_name]
        
        if order_pools:
            print(f"找到 {len(order_pools)} 个订单数据库连接池:")
            for pool_name in order_pools:
                print(f"  - {pool_name}: OK")
        else:
            print("未找到订单数据库连接池")
        
        # 检查订单数据库文件是否存在
        print("\n检查订单数据库文件...")
        base_path = Path("data/databases")
        order_db_files = list(base_path.glob("*/*_orders.duckdb"))
        
        if order_db_files:
            print(f"找到 {len(order_db_files)} 个订单数据库文件:")
            for db_file in order_db_files:
                print(f"  - {db_file}")
                
                # 检查表是否存在
                try:
                    import duckdb
                    conn = duckdb.connect(str(db_file))
                    
                    # 检查orders表
                    tables = conn.execute("SHOW TABLES").fetchall()
                    table_names = [t[0] for t in tables]
                    
                    print(f"    表: {', '.join(table_names)}")
                    
                    conn.close()
                except Exception as e:
                    print(f"    错误: {e}")
        else:
            print("未找到订单数据库文件")
        
        print("\n测试完成！")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
