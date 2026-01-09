"""
简单测试订单数据库自动创建（不初始化完整系统）
"""

import sys
from pathlib import Path
import duckdb

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.plugin_types import AssetType

def main():
    """主函数"""
    print("测试订单数据库自动创建...")
    
    base_path = Path("data/databases")
    
    # 检查订单数据库文件是否存在
    print("\n检查订单数据库文件...")
    order_db_files = list(base_path.glob("*/*_orders.duckdb"))
    
    if order_db_files:
        print(f"找到 {len(order_db_files)} 个订单数据库文件:")
        for db_file in order_db_files:
            print(f"  - {db_file}")
            
            # 检查表是否存在
            try:
                conn = duckdb.connect(str(db_file))
                
                # 检查orders表
                tables = conn.execute("SHOW TABLES").fetchall()
                table_names = [t[0] for t in tables]
                
                print(f"    表: {', '.join(table_names)}")
                
                # 检查索引
                indexes = conn.execute("SELECT index_name FROM duckdb_indexes()").fetchall()
                index_names = [i[0] for i in indexes]
                
                print(f"    索引: {', '.join(index_names)}")
                
                conn.close()
            except Exception as e:
                print(f"    错误: {e}")
    else:
        print("未找到订单数据库文件")
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()
