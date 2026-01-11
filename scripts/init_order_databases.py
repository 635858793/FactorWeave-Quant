"""
订单数据库初始化脚本

为不同资产类型创建对应的订单数据库和表结构
"""

import sqlite3
from pathlib import Path
from typing import List
from loguru import logger

from core.plugin_types import AssetType


class OrderDatabaseInitializer:
    """订单数据库初始化器"""

    def __init__(self, base_path: str = "data/databases"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def initialize_all_asset_databases(self):
        """初始化所有资产类型的数据库"""
        logger.info("开始初始化所有资产类型的订单数据库...")

        for asset_type in AssetType:
            self.initialize_asset_database(asset_type)

        logger.info("所有资产类型的订单数据库初始化完成")

    def initialize_asset_database(self, asset_type: AssetType):
        """初始化指定资产类型的数据库"""
        asset_dir = self.base_path / asset_type.value.lower()
        asset_dir.mkdir(exist_ok=True)

        db_path = asset_dir / f"{asset_type.value.lower()}_orders.duckdb"

        logger.info(f"初始化资产类型数据库: {asset_type.value} -> {db_path}")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        try:
            self._create_orders_table(cursor)
            self._create_order_fills_table(cursor)
            self._create_indices(cursor)
            conn.commit()
            logger.success(f"资产类型数据库初始化成功: {asset_type.value}")
        except Exception as e:
            conn.rollback()
            logger.error(f"资产类型数据库初始化失败: {asset_type.value} - {e}")
        finally:
            conn.close()

    def _create_orders_table(self, cursor: sqlite3.Cursor):
        """创建订单表"""
        sql = """
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
        cursor.execute(sql)

    def _create_order_fills_table(self, cursor: sqlite3.Cursor):
        """创建订单成交记录表"""
        sql = """
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
        cursor.execute(sql)

    def _create_indices(self, cursor: sqlite3.Cursor):
        """创建索引"""
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_orders_strategy_id ON orders(strategy_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_asset_type ON orders(asset_type)",
            "CREATE INDEX IF NOT EXISTS idx_orders_stock_code ON orders(stock_code)",
            "CREATE INDEX IF NOT EXISTS idx_orders_order_type ON orders(order_type)",
            "CREATE INDEX IF NOT EXISTS idx_orders_order_category ON orders(order_category)",
            "CREATE INDEX IF NOT EXISTS idx_orders_order_status ON orders(order_status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_create_time ON orders(create_time)",
            "CREATE INDEX IF NOT EXISTS idx_orders_update_time ON orders(update_time)",
            "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_order_fills_order_id ON order_fills(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_order_fills_stock_code ON order_fills(stock_code)",
            "CREATE INDEX IF NOT EXISTS idx_order_fills_fill_time ON order_fills(fill_time)"
        ]

        for index_sql in indices:
            cursor.execute(index_sql)

    def get_database_paths(self) -> List[str]:
        """获取所有数据库路径"""
        db_paths = []
        for asset_type in AssetType:
            db_path = self.base_path / asset_type.value.lower() / f"{asset_type.value.lower()}_orders.duckdb"
            if db_path.exists():
                db_paths.append(str(db_path))
        return db_paths

    def drop_all_databases(self):
        """删除所有数据库（慎用！）"""
        logger.warning("开始删除所有资产类型的订单数据库...")

        for asset_type in AssetType:
            asset_dir = self.base_path / asset_type.value.lower()
            db_path = asset_dir / f"{asset_type.value.lower()}_orders.duckdb"
            if db_path.exists():
                db_path.unlink()
                logger.warning(f"已删除数据库: {db_path}")

        logger.warning("所有资产类型的订单数据库已删除")


def main():
    """主函数"""
    initializer = OrderDatabaseInitializer()
    
    print("=" * 80)
    print("订单数据库初始化工具")
    print("=" * 80)
    print()
    print("1. 初始化所有资产类型的数据库")
    print("2. 查看所有数据库路径")
    print("3. 删除所有数据库（慎用！）")
    print("0. 退出")
    print()
    
    choice = input("请选择操作: ")
    
    if choice == "1":
        initializer.initialize_all_asset_databases()
    elif choice == "2":
        db_paths = initializer.get_database_paths()
        print("\n数据库路径列表:")
        for path in db_paths:
            print(f"  - {path}")
    elif choice == "3":
        confirm = input("确认删除所有数据库？(yes/no): ")
        if confirm.lower() == "yes":
            initializer.drop_all_databases()
        else:
            print("操作已取消")
    elif choice == "0":
        print("退出")
    else:
        print("无效的选择")


if __name__ == "__main__":
    main()
