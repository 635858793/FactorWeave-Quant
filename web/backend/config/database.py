"""
数据库配置
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional
import duckdb
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend.config.settings import settings

Base = declarative_base()


SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {},
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    获取数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DuckDBManager:
    """
    DuckDB管理器
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DUCKDB_PATH
        self.connection = None
    
    def connect(self):
        """
        连接数据库
        """
        if not self.connection:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.connection = duckdb.connect(self.db_path)
        
        return self.connection
    
    def disconnect(self):
        """
        断开数据库连接
        """
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute_query(self, query: str, params: dict = None) -> list:
        """
        执行查询
        """
        conn = self.connect()
        
        cursor = conn.cursor()
        
        if params:
            for key, value in params.items():
                query = query.replace(f":{key}", f"'{value}'")
        
        cursor.execute(query)
        
        if query.strip().upper().startswith("SELECT"):
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        else:
            conn.commit()
            return []
    
    def execute_script(self, script: str):
        """
        执行脚本
        """
        conn = self.connect()
        conn.execute(script)
        conn.commit()


_duckdb_manager: Optional[DuckDBManager] = None


def get_duckdb_manager() -> DuckDBManager:
    """
    获取DuckDB管理器
    """
    global _duckdb_manager
    
    if _duckdb_manager is None:
        _duckdb_manager = DuckDBManager()
    
    return _duckdb_manager


def init_db():
    """
    初始化数据库
    """
    Base.metadata.create_all(bind=engine)
    
    duckdb_manager = get_duckdb_manager()
    
    init_duckdb_schema(duckdb_manager)


def init_duckdb_schema(duckdb_manager: DuckDBManager):
    """
    初始化DuckDB表结构
    """
    schema = """
    CREATE TABLE IF NOT EXISTS orders (
        order_id VARCHAR(50) PRIMARY KEY,
        account_id INTEGER,
        asset_type VARCHAR(50),
        symbol VARCHAR(50),
        side VARCHAR(20),
        order_type VARCHAR(20),
        quantity FLOAT,
        price FLOAT,
        stop_price FLOAT,
        filled_quantity FLOAT,
        avg_fill_price FLOAT,
        status VARCHAR(20),
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        time_in_force VARCHAR(20),
        remark TEXT
    );
    
    CREATE TABLE IF NOT EXISTS fills (
        id INTEGER PRIMARY KEY,
        fill_id VARCHAR(50) UNIQUE,
        order_id VARCHAR(50),
        account_id INTEGER,
        asset_type VARCHAR(50),
        symbol VARCHAR(50),
        side VARCHAR(20),
        price FLOAT,
        quantity FLOAT,
        commission FLOAT,
        fill_time TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY,
        account_name VARCHAR(100),
        account_type VARCHAR(50),
        institution VARCHAR(100),
        account_code VARCHAR(50),
        is_active BOOLEAN,
        created_by INTEGER,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY,
        account_id INTEGER,
        asset_type VARCHAR(50),
        symbol VARCHAR(50),
        side VARCHAR(20),
        quantity FLOAT,
        available_quantity FLOAT,
        avg_price FLOAT,
        current_price FLOAT,
        market_value FLOAT,
        profit_loss FLOAT,
        profit_loss_ratio FLOAT,
        updated_at TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS balances (
        id INTEGER PRIMARY KEY,
        account_id INTEGER,
        total_balance FLOAT,
        available_balance FLOAT,
        frozen_balance FLOAT,
        market_value FLOAT,
        total_asset FLOAT,
        profit_loss FLOAT,
        profit_loss_ratio FLOAT,
        updated_at TIMESTAMP
    );
    """
    
    duckdb_manager.execute_script(schema)
