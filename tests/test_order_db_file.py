"""
直接测试订单数据库文件创建
"""

import sqlite3
from pathlib import Path
from core.plugin_types import AssetType

def main():
    """主函数"""
    print("测试订单数据库文件创建...")
    
    base_path = Path("data/databases")
    base_path.mkdir(parents=True, exist_ok=True)
    
    test_types = [AssetType.STOCK_A, AssetType.FUTURES, AssetType.OPTION]
    
    for asset_type in test_types:
        asset_dir = base_path / asset_type.value.lower()
        asset_dir.mkdir(exist_ok=True)
        
        pool_name = f"{asset_type.value.lower()}_orders"
        db_path = asset_dir / f"{pool_name}.duckdb"
        
        print(f"\n创建数据库: {db_path}")
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 创建测试表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
            """)
            
            # 插入测试数据
            cursor.execute("INSERT INTO test_table (name) VALUES (?)", (asset_type.value,))
            
            conn.commit()
            conn.close()
            
            print(f"  [OK] 数据库创建成功: {pool_name}")
            
        except Exception as e:
            print(f"  [ERROR] 数据库创建失败: {e}")
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()
