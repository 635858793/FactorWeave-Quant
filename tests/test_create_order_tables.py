"""
直接测试订单数据库表创建
"""

import sys
from pathlib import Path
import duckdb

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.plugin_types import AssetType

def create_order_tables():
    """创建订单数据库表"""
    base_path = Path("data/databases")
    
    print("创建订单数据库表...")
    
    for asset_type in AssetType:
        asset_dir = base_path / asset_type.value.lower()
        asset_dir.mkdir(parents=True, exist_ok=True)
        
        pool_name = f"{asset_type.value.lower()}_orders"
        db_path = asset_dir / f"{pool_name}.duckdb"
        
        print(f"\n处理: {asset_type.value} -> {db_path}")
        
        try:
            conn = duckdb.connect(str(db_path))
            
            # 创建订单表
            orders_sql = """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                order_type TEXT NOT NULL,
                order_category TEXT NOT NULL,
                order_price REAL NOT NULL,
                order_quantity INTEGER NOT NULL,
                order_status TEXT NOT NULL,
                create_time TEXT NOT NULL,
                update_time TEXT NOT NULL,
                execute_time TEXT,
                filled_quantity INTEGER DEFAULT 0,
                filled_price REAL DEFAULT 0.0,
                commission REAL DEFAULT 0.0,
                error_message TEXT,
                stop_price REAL,
                user_id TEXT DEFAULT 'system',
                account_id TEXT DEFAULT 'default',
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                contract_multiplier INTEGER DEFAULT 1,
                margin_ratio REAL DEFAULT 0.0,
                strike_price REAL,
                expiry_date TEXT,
                option_type TEXT
            )
            """
            conn.execute(orders_sql)
            
            # 创建索引
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_orders_strategy_id ON orders(strategy_id)",
                "CREATE INDEX IF NOT EXISTS idx_orders_asset_type ON orders(asset_type)",
                "CREATE INDEX IF NOT EXISTS idx_orders_stock_code ON orders(stock_code)",
                "CREATE INDEX IF NOT EXISTS idx_orders_order_type ON orders(order_type)",
                "CREATE INDEX IF NOT EXISTS idx_orders_order_category ON orders(order_category)",
                "CREATE INDEX IF NOT EXISTS idx_orders_order_status ON orders(order_status)",
                "CREATE INDEX IF NOT EXISTS idx_orders_create_time ON orders(create_time)",
                "CREATE INDEX IF NOT EXISTS idx_orders_update_time ON orders(update_time)",
                "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders(account_id)"
            ]
            
            for index_sql in indexes:
                conn.execute(index_sql)
            
            # 创建订单成交记录表
            order_fills_sql = """
            CREATE TABLE IF NOT EXISTS order_fills (
                fill_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                fill_price REAL NOT NULL,
                fill_quantity INTEGER NOT NULL,
                fill_time TEXT NOT NULL,
                commission REAL DEFAULT 0.0,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
            """
            conn.execute(order_fills_sql)
            
            # 创建索引
            fill_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_order_fills_order_id ON order_fills(order_id)",
                "CREATE INDEX IF NOT EXISTS idx_order_fills_stock_code ON order_fills(stock_code)",
                "CREATE INDEX IF NOT EXISTS idx_order_fills_fill_time ON order_fills(fill_time)"
            ]
            
            for index_sql in fill_indexes:
                conn.execute(index_sql)
            
            conn.close()
            
            print(f"  [OK] 表和索引创建成功")
            
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    print("\n创建完成！")

if __name__ == "__main__":
    create_order_tables()
