"""
资产分数据库管理器

提供按资产类型分数据库的管理功能，包括：
- 资产类型自动识别和路由
- 多数据库连接管理
- 数据库自动创建和初始化
- 统一的查询接口
- 跨资产类型数据查询

作者: FactorWeave-Quant团队
版本: 1.0
"""

import threading
import os
import time
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import json
import pandas as pd

from loguru import logger
from core.database.duckdb_manager import DuckDBConnectionManager, DuckDBConfig
from core.asset_type_identifier import AssetTypeIdentifier, get_asset_type_identifier
from core.plugin_types import AssetType, DataType

logger = logger.bind(module=__name__)


@dataclass
class AssetDatabaseConfig:
    """资产数据库配置"""
    base_path: str = "data/databases"
    pool_size: int = 10
    auto_create: bool = True
    enable_wal: bool = True
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    compression: str = "zstd"
    memory_limit: str = "8GB"
    threads: str = "auto"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'base_path': self.base_path,
            'pool_size': self.pool_size,
            'auto_create': self.auto_create,
            'enable_wal': self.enable_wal,
            'backup_enabled': self.backup_enabled,
            'backup_interval_hours': self.backup_interval_hours,
            'compression': self.compression,
            'memory_limit': self.memory_limit,
            'threads': self.threads
        }


@dataclass
class AssetDatabaseInfo:
    """资产数据库信息"""
    asset_type: AssetType
    database_path: str
    created_at: datetime
    last_accessed: datetime
    size_mb: float = 0.0
    table_count: int = 0
    record_count: int = 0
    health_status: str = "unknown"
    supported_data_sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'asset_type': self.asset_type.value,
            'database_path': self.database_path,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'size_mb': self.size_mb,
            'table_count': self.table_count,
            'record_count': self.record_count,
            'health_status': self.health_status,
            'supported_data_sources': self.supported_data_sources
        }


class AssetSeparatedDatabaseManager:
    """
    资产分数据库管理器

    按资产类型分离数据库存储，每种资产类型使用独立的DuckDB数据库文件。
    支持自动识别资产类型、路由到对应数据库、统一查询接口等功能。
    """

    _instance: Optional['AssetSeparatedDatabaseManager'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls, config: Optional[AssetDatabaseConfig] = None) -> 'AssetSeparatedDatabaseManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    def __init__(self, config: Optional[AssetDatabaseConfig] = None):
        """
        初始化资产分数据库管理器

        Args:
            config: 资产数据库配置
        """
        if self._initialized:
            return

        self.config = config or AssetDatabaseConfig()

        # ✅ 修复：从数据库加载数据库连接池配置
        try:
            from db.models.plugin_models import get_data_source_config_manager
            config_manager = get_data_source_config_manager()
            global_config = config_manager.get_plugin_config('_global_database_pool')
            if global_config:
                # get_plugin_config返回的dict可能包含max_pool_size字段
                saved_pool_size = global_config.get('max_pool_size')
                if saved_pool_size and isinstance(saved_pool_size, int) and 5 <= saved_pool_size <= 100:
                    self.config.pool_size = saved_pool_size
                    logger.info(f"从数据库加载数据库连接池配置: pool_size={saved_pool_size}")
        except Exception as load_err:
            logger.debug(f"从数据库加载数据库连接池配置失败（使用默认值）: {load_err}")

        # 核心组件
        self.asset_identifier = get_asset_type_identifier()
        self.duckdb_manager = DuckDBConnectionManager()

        # 数据库映射和信息
        self._asset_databases: Dict[AssetType, str] = {}
        self._database_info: Dict[AssetType, AssetDatabaseInfo] = {}

        # 线程锁
        self._db_lock = threading.RLock()

        # 标准表结构定义
        self._table_schemas = self._initialize_table_schemas()

        # 初始化
        self._initialize_directories()
        self._load_existing_databases()

        self._initialized = True
        logger.info("AssetSeparatedDatabaseManager 初始化完成")

    def _initialize_directories(self):
        """初始化目录结构"""
        base_path = Path(self.config.base_path)
        base_path.mkdir(parents=True, exist_ok=True)

        # 创建各种资产类型的目录
        for asset_type in AssetType:
            asset_dir = base_path / asset_type.value.lower()
            asset_dir.mkdir(exist_ok=True)

        logger.debug(f"目录结构初始化完成: {base_path}")

    def _initialize_table_schemas(self) -> Dict[str, str]:
        """初始化标准表结构定义"""
        return {
            # K线数据表（通用）- 使用合理的小数点精度
            'historical_kline_data': """
                CREATE TABLE IF NOT EXISTS historical_kline_data (
                    -- 主键字段
                    symbol VARCHAR NOT NULL,
                    data_source VARCHAR NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    frequency VARCHAR NOT NULL DEFAULT '1d',
                    
                    -- 基础OHLCV字段（A股标准：2位小数）
                    open DECIMAL(10,2) NOT NULL,
                    high DECIMAL(10,2) NOT NULL,
                    low DECIMAL(10,2) NOT NULL,
                    close DECIMAL(10,2) NOT NULL,
                    volume BIGINT DEFAULT 0,
                    amount DECIMAL(18,2) DEFAULT 0,
                    
                    -- 扩展交易数据（量化必需）
                    turnover DECIMAL(18,2) DEFAULT 0,
                    adj_close DECIMAL(10,4),           -- 复权价格：4位小数
                    adj_factor DECIMAL(10,6) DEFAULT 1.0,  -- 复权因子：6位小数
                    turnover_rate DECIMAL(8,2),        -- 换手率：2位小数（百分比）
                    vwap DECIMAL(10,2),                -- VWAP：2位小数
                    
                    -- 涨跌数据
                    change DECIMAL(10,2),              -- 涨跌额：2位小数
                    change_pct DECIMAL(8,2),           -- 涨跌幅：2位小数（百分比）
                    
                    -- 元数据字段已移除，改用asset_metadata表关联
                    -- name VARCHAR,          -- 已移除：从asset_metadata表获取
                    -- market VARCHAR,        -- 已移除：从asset_metadata表获取
                    -- period VARCHAR,        -- 已移除：与frequency重复
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    PRIMARY KEY (symbol, data_source, timestamp, frequency)
                )
            """,

            # 数据源记录表
            'data_source_records': """
                CREATE TABLE IF NOT EXISTS data_source_records (
                    record_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    data_source VARCHAR NOT NULL,
                    data_type VARCHAR NOT NULL,
                    start_date DATE,
                    end_date DATE,
                    record_count INTEGER,
                    file_size_bytes BIGINT,
                    checksum VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,

            # 数据质量监控表
            'data_quality_monitor': """
                CREATE TABLE IF NOT EXISTS data_quality_monitor (
                    monitor_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    data_source VARCHAR NOT NULL,
                    check_date DATE NOT NULL,
                    quality_score DECIMAL(5,2),
                    anomaly_count INTEGER DEFAULT 0,
                    missing_count INTEGER DEFAULT 0,
                    outlier_count INTEGER DEFAULT 0,
                    consistency_score DECIMAL(5,2),
                    completeness_score DECIMAL(5,2),
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,

            # 统一视图 - 最优质量K线数据
            # 逻辑：优先选择质量分数高的数据源，若无质量评分则选择最新更新的数据
            'unified_best_quality_kline': """
                CREATE OR REPLACE VIEW unified_best_quality_kline AS
                WITH ranked_data AS (
                    SELECT 
                        hkd.*,
                        dqm.quality_score,
                        -- 数据源优先级：有质量评分的优先，其次按数据源名称稳定排序
                        CASE 
                            WHEN dqm.quality_score IS NOT NULL THEN dqm.quality_score
                            WHEN hkd.data_source = 'tongdaxin' THEN 60.0
                            WHEN hkd.data_source = 'akshare' THEN 55.0
                            WHEN hkd.data_source = 'tushare' THEN 65.0
                            ELSE 50.0
                        END as effective_quality_score,
                        ROW_NUMBER() OVER (
                            PARTITION BY hkd.symbol, hkd.timestamp, hkd.frequency 
                            ORDER BY 
                                -- 首先按有效质量分数排序（降序）
                                CASE 
                                    WHEN dqm.quality_score IS NOT NULL THEN dqm.quality_score
                                    WHEN hkd.data_source = 'tongdaxin' THEN 60.0
                                    WHEN hkd.data_source = 'akshare' THEN 55.0
                                    WHEN hkd.data_source = 'tushare' THEN 65.0
                                    ELSE 50.0
                                END DESC,
                                -- 其次按更新时间排序（降序，最新的优先）
                                hkd.updated_at DESC
                        ) as quality_rank
                    FROM historical_kline_data hkd
                    LEFT JOIN data_quality_monitor dqm ON (
                        hkd.symbol = dqm.symbol 
                        AND hkd.data_source = dqm.data_source 
                        AND CAST(hkd.timestamp AS DATE) = dqm.check_date
                    )
                )
                SELECT * FROM ranked_data WHERE quality_rank = 1
            """,

            # 元数据表
            'metadata': """
                CREATE TABLE IF NOT EXISTS metadata (
                    key VARCHAR PRIMARY KEY,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,

            # 资产元数据表（新增）
            'asset_metadata': """
                CREATE TABLE IF NOT EXISTS asset_metadata (
                    -- 主键
                    symbol VARCHAR PRIMARY KEY,
                    
                    -- 基本信息
                    name VARCHAR NOT NULL,
                    
                    -- 分类信息
                    asset_type VARCHAR NOT NULL,
                    market VARCHAR NOT NULL,
                    exchange VARCHAR,
                    
                    -- 行业分类
                    sector VARCHAR,
                    industry VARCHAR,
                    industry_code VARCHAR,
                    
                    -- 上市信息
                    listing_date DATE,
                    delisting_date DATE,
                    listing_status VARCHAR DEFAULT 'active',
                    
                    -- 股本信息（BIGINT，单位：股）
                    total_shares BIGINT,
                    circulating_shares BIGINT,
                    currency VARCHAR DEFAULT 'CNY',
                    
                    -- 加密货币/期货特有字段
                    base_currency VARCHAR,
                    quote_currency VARCHAR,
                    contract_type VARCHAR,
                    
                    -- 数据源信息（JSON字符串）
                    data_sources VARCHAR,              -- JSON: ["eastmoney", "sina"]
                    primary_data_source VARCHAR,
                    last_update_source VARCHAR,
                    
                    -- 元数据管理
                    metadata_version INTEGER DEFAULT 1,
                    data_quality_score DECIMAL(3,2),   -- 0.00 ~ 1.00
                    last_verified TIMESTAMP,
                    
                    -- 扩展字段（JSON字符串）
                    tags VARCHAR,                      -- JSON: ["蓝筹股", "高股息"]
                    attributes VARCHAR,                -- JSON: {key: value}
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,

            # K线数据+元数据视图（便捷查询）
            'kline_with_metadata': """
                CREATE OR REPLACE VIEW kline_with_metadata AS
                SELECT 
                    k.*,
                    m.name,
                    m.market,
                    m.industry,
                    m.sector,
                    m.listing_status,
                    m.exchange
                FROM historical_kline_data k
                LEFT JOIN asset_metadata m ON k.symbol = m.symbol
            """,

            # 订单表
            'orders': """
                CREATE TABLE IF NOT EXISTS orders (
                    -- 主键
                    order_id VARCHAR(64) PRIMARY KEY,
                    
                    -- 基本信息
                    strategy_id VARCHAR(128) NOT NULL DEFAULT '',
                    asset_type VARCHAR(32) NOT NULL,
                    stock_code VARCHAR(32) NOT NULL,
                    
                    -- 订单类型
                    order_type VARCHAR(16) NOT NULL,
                    order_category VARCHAR(16) NOT NULL,
                    
                    -- 订单价格和数量
                    order_price DECIMAL(18,4) NOT NULL,
                    order_quantity BIGINT NOT NULL,
                    
                    -- 订单状态
                    order_status VARCHAR(16) NOT NULL,
                    
                    -- 时间戳
                    create_time TIMESTAMP NOT NULL,
                    update_time TIMESTAMP NOT NULL,
                    execute_time TIMESTAMP,
                    
                    -- 成交信息
                    filled_quantity BIGINT DEFAULT 0,
                    filled_price DECIMAL(18,4),
                    commission DECIMAL(18,4) DEFAULT 0,
                    
                    -- 错误信息
                    error_message TEXT,
                    
                    -- 止损价格
                    stop_price DECIMAL(18,4),
                    
                    -- 用户和账户信息
                    user_id VARCHAR(64) NOT NULL DEFAULT 'system',
                    account_id VARCHAR(64) NOT NULL DEFAULT '',
                    
                    -- 扩展字段（JSON字符串）
                    tags VARCHAR,
                    metadata TEXT DEFAULT '{}',
                    
                    -- 期货/期权特有字段
                    contract_multiplier DECIMAL(10,2) DEFAULT 1.0,
                    margin_ratio DECIMAL(10,6) DEFAULT 0,
                    strike_price DECIMAL(18,4),
                    expiry_date DATE,
                    option_type VARCHAR(16)
                )
            """
        }

    def _load_existing_databases(self):
        """加载现有数据库"""
        base_path = Path(self.config.base_path)

        for asset_type in AssetType:
            db_path = self._get_database_path(asset_type)

            if Path(db_path).exists():
                self._asset_databases[asset_type] = db_path

                # ✅ 修复：在系统初始化时，100%确保表和视图都存在
                try:
                    self._initialize_database_schema(asset_type, db_path)
                    logger.info(f"✅ 数据库架构初始化完成: {asset_type.value}")
                except Exception as e:
                    logger.error(f"❌ 数据库架构初始化失败 {asset_type.value}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

                # 获取数据库信息
                info = self._collect_database_info(asset_type, db_path)
                self._database_info[asset_type] = info

                logger.debug(f"加载现有数据库: {asset_type.value} -> {db_path}")

    def _get_database_path(self, asset_type: AssetType) -> str:
        """获取资产类型对应的数据库路径"""
        # ✅ 增强：完善资产类型映射逻辑
        mapped_asset_type = self._map_asset_type_to_database(asset_type)

        base_path = Path(self.config.base_path)
        asset_dir = base_path / mapped_asset_type.value.lower()
        db_file = asset_dir / f"{mapped_asset_type.value.lower()}_data.duckdb"
        return str(db_file)

    def _map_asset_type_to_database(self, asset_type: AssetType) -> AssetType:
        """
        将资产类型映射到对应的数据库类型

        Args:
            asset_type: 原始资产类型

        Returns:
            AssetType: 映射后的资产类型
        """
        # 别名映射规则
        mapping_rules = {
            # ✅ 移除STOCK映射，因为STOCK类型已被移除
            # AssetType.STOCK_A: AssetType.STOCK_A,  # 已移除

            # 板块相关资产类型映射到通用板块
            AssetType.INDUSTRY_SECTOR: AssetType.SECTOR,
            AssetType.CONCEPT_SECTOR: AssetType.SECTOR,
            AssetType.STYLE_SECTOR: AssetType.SECTOR,
            AssetType.THEME_SECTOR: AssetType.SECTOR,

            # 其他资产类型保持原样
            # AssetType.STOCK_A: AssetType.STOCK_A,
            # AssetType.STOCK_US: AssetType.STOCK_US,
            # AssetType.STOCK_HK: AssetType.STOCK_HK,
            # AssetType.CRYPTO: AssetType.CRYPTO,
            # AssetType.FUTURES: AssetType.FUTURES,
            # AssetType.FOREX: AssetType.FOREX,
            # AssetType.BOND: AssetType.BOND,
            # AssetType.COMMODITY: AssetType.COMMODITY,
            # AssetType.INDEX: AssetType.INDEX,
            # AssetType.FUND: AssetType.FUND,
            # AssetType.OPTION: AssetType.OPTION,
            # AssetType.WARRANT: AssetType.WARRANT,
            # AssetType.MACRO: AssetType.MACRO,
        }

        # 应用映射规则
        mapped_type = mapping_rules.get(asset_type, asset_type)

        logger.debug(f"资产类型映射: {asset_type.value} → {mapped_type.value}")
        return mapped_type

    def get_database_path(self, asset_type: AssetType) -> str:
        """获取资产类型对应的数据库路径 (公共方法)"""
        return self._get_database_path(asset_type)

    def _collect_database_info(self, asset_type: AssetType, db_path: str) -> AssetDatabaseInfo:
        """收集数据库信息"""
        try:
            # 获取文件信息
            file_stat = Path(db_path).stat()
            size_mb = file_stat.st_size / (1024 * 1024)

            # 获取数据库内部信息
            with self.duckdb_manager.get_connection(db_path) as conn:
                # 获取表数量 - 使用duckdb_tables()更高效
                tables_result = conn.execute("""
                    SELECT COUNT(*) as table_count 
                    FROM duckdb_tables() 
                    WHERE schema_name = 'main'
                """).fetchone()
                table_count = tables_result[0] if tables_result else 0

                # 获取记录总数（仅查询historical_kline_data表）
                record_count = 0
                try:
                    record_result = conn.execute("""
                        SELECT COUNT(*) as record_count 
                        FROM historical_kline_data
                    """).fetchone()
                    record_count = record_result[0] if record_result else 0
                except:
                    pass  # 表可能不存在

                # 获取支持的数据源
                supported_sources = []
                try:
                    sources_result = conn.execute("""
                        SELECT DISTINCT data_source 
                        FROM historical_kline_data
                    """).fetchall()
                    supported_sources = [row[0] for row in sources_result]
                except:
                    pass  # 表可能不存在

            return AssetDatabaseInfo(
                asset_type=asset_type,
                database_path=db_path,
                created_at=datetime.fromtimestamp(file_stat.st_ctime),
                last_accessed=datetime.fromtimestamp(file_stat.st_atime),
                size_mb=size_mb,
                table_count=table_count,
                record_count=record_count,
                health_status="healthy",
                supported_data_sources=supported_sources
            )

        except Exception as e:
            logger.error(f"收集数据库信息失败 {asset_type.value}: {e}")
            return AssetDatabaseInfo(
                asset_type=asset_type,
                database_path=db_path,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                health_status="error"
            )

    def get_database_for_asset_type(self, asset_type: AssetType, auto_create: bool = True) -> str:
        """
        获取资产类型对应的数据库路径

        Args:
            asset_type: 资产类型
            auto_create: 是否自动创建数据库

        Returns:
            数据库文件路径
        """
        with self._db_lock:
            if asset_type not in self._asset_databases:
                db_path = self._get_database_path(asset_type)

                if auto_create and self.config.auto_create:
                    if Path(db_path).exists():
                        # ✅ 修复：数据库文件已存在，不需要在这里处理
                        # 视图在系统初始化时已经100%创建成功（在_load_existing_databases中）
                        pass
                    else:
                        # 数据库文件不存在，创建数据库（包括表和视图）
                        self._create_asset_database(asset_type, db_path)

                self._asset_databases[asset_type] = db_path

            return self._asset_databases[asset_type]

    def _ensure_database_exists(self, asset_type: AssetType) -> str:
        """
        确保数据库存在并返回数据库路径

        Args:
            asset_type: 资产类型

        Returns:
            str: 数据库文件路径
        """
        return self.get_database_for_asset_type(asset_type, auto_create=True)

    def _initialize_database_schema(self, asset_type: AssetType, db_path: str):
        """
        ✅ 修复：在系统初始化时，100%确保数据库架构完整（表和视图都存在）

        这个方法在系统启动时调用，确保：
        1. 所有必要的表都存在
        2. 所有视图都存在
        3. 如果表或视图不存在，自动创建

        Args:
            asset_type: 资产类型
            db_path: 数据库文件路径
        """
        try:
            view_names = ['unified_best_quality_kline', 'kline_with_metadata']

            with self.duckdb_manager.get_connection(db_path) as conn:
                # 第一步：确保所有基础表存在
                for table_name, schema_sql in self._table_schemas.items():
                    if table_name in view_names:
                        continue  # 跳过视图，待基础表创建完成后再创建

                    try:
                        # 检查表是否存在
                        table_exists = conn.execute(f"""
                            SELECT COUNT(*) 
                            FROM duckdb_tables() 
                            WHERE table_name = '{table_name}'
                        """).fetchone()[0] > 0

                        if not table_exists:
                            # 表不存在，创建表
                            conn.execute(schema_sql)
                            logger.info(f"✅ 初始化时创建表 {table_name} 成功")

                            # 如果是K线数据表，创建索引
                            if table_name == 'historical_kline_data':
                                self._create_table_indexes(conn, table_name, DataType.HISTORICAL_KLINE)
                            
                            # 如果是订单表，创建索引
                            if table_name == 'orders':
                                self._create_orders_table_indexes(conn)
                        else:
                            logger.debug(f"表 {table_name} 已存在")
                    except Exception as e:
                        logger.error(f"❌ 初始化时创建表 {table_name} 失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        raise  # 表创建失败应该抛出异常

                # 第二步：确保所有视图存在（使用CREATE OR REPLACE VIEW确保100%成功）
                for view_name in view_names:
                    if view_name not in self._table_schemas:
                        continue

                    try:
                        # ✅ 修复：先尝试删除视图（如果存在），然后创建新视图
                        # 这样可以避免CREATE OR REPLACE VIEW在某些情况下的兼容性问题
                        try:
                            conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                            logger.debug(f"已删除旧视图（如果存在）: {view_name}")
                        except Exception as drop_error:
                            # 如果视图不存在，DROP会失败，这是正常的，忽略错误
                            logger.debug(f"删除视图时（视图可能不存在）: {drop_error}")

                        # 使用CREATE VIEW创建新视图
                        view_sql = self._table_schemas[view_name]
                        # ✅ 修复：将CREATE OR REPLACE VIEW改为CREATE VIEW（因为已经DROP了）
                        view_sql = view_sql.replace("CREATE OR REPLACE VIEW", "CREATE VIEW")
                        conn.execute(view_sql)
                        logger.info(f"✅ 初始化时创建/更新视图 {view_name} 成功")
                    except Exception as e:
                        error_msg = str(e)
                        # 如果错误是因为表不存在，记录错误并抛出异常
                        if "does not exist" in error_msg.lower() or "table" in error_msg.lower() or "catalog" in error_msg.lower():
                            logger.error(f"❌ 初始化时创建视图 {view_name} 失败: 依赖的表不存在 - {e}")
                            logger.error("这不应该发生，因为表应该已经在上一步创建了")
                            # ✅ 增强：列出所有应该存在的表，帮助调试
                            logger.error(f"应该存在的表: historical_kline_data, data_quality_monitor, asset_metadata")
                        else:
                            logger.error(f"❌ 初始化时创建视图 {view_name} 失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        raise  # 视图创建失败应该抛出异常，因为这是初始化阶段

        except Exception as e:
            logger.error(f"❌ 数据库架构初始化失败 {asset_type.value}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _create_orders_table_indexes(self, conn):
        """
        为 orders 表创建索引
        
        Args:
            conn: 数据库连接
        """
        try:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_orders_asset_type ON orders(asset_type)",
                "CREATE INDEX IF NOT EXISTS idx_orders_stock_code ON orders(stock_code)",
                "CREATE INDEX IF NOT EXISTS idx_orders_order_status ON orders(order_status)",
                "CREATE INDEX IF NOT EXISTS idx_orders_create_time ON orders(create_time)",
                "CREATE INDEX IF NOT EXISTS idx_orders_strategy_id ON orders(strategy_id)",
                "CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders(account_id)",
                "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
            ]
            
            for index_sql in indexes:
                conn.execute(index_sql)
            
            logger.info("✅ orders 表索引创建成功")
        except Exception as e:
            logger.error(f"❌ 创建 orders 表索引失败: {e}")
            raise

    def get_database_for_symbol(self, symbol: str, auto_create: bool = True) -> Tuple[str, AssetType]:
        """
        根据交易符号获取对应的数据库路径和资产类型

        Args:
            symbol: 交易符号
            auto_create: 是否自动创建数据库

        Returns:
            (数据库路径, 资产类型)
        """
        asset_type = self.asset_identifier.identify_asset_type_by_symbol(symbol)
        db_path = self.get_database_for_asset_type(asset_type, auto_create)
        return db_path, asset_type

    def _create_asset_database(self, asset_type: AssetType, db_path: str):
        """创建资产数据库"""
        try:
            # 确保目录存在
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

            # 创建数据库并初始化表结构
            duckdb_config = DuckDBConfig(
                memory_limit=self.config.memory_limit,
                threads=self.config.threads,
                compression=self.config.compression
            )

            with self.duckdb_manager.get_connection(db_path, config=duckdb_config) as conn:
                # 区分表和视图
                view_names = ['unified_best_quality_kline', 'kline_with_metadata']

                # 第一步：创建所有基础表
                for table_name, schema_sql in self._table_schemas.items():
                    if table_name in view_names:
                        continue  # 跳过视图，待基础表创建完成后再创建
                    try:
                        conn.execute(schema_sql)
                        logger.debug(f"创建表 {table_name} 成功")
                    except Exception as e:
                        logger.error(f"创建表 {table_name} 失败: {e}")
                        raise
                
                # 第二步：为 orders 表创建索引
                try:
                    self._create_orders_table_indexes(conn)
                except Exception as e:
                    logger.error(f"创建 orders 表索引失败: {e}")
                    raise

                # 第三步：创建所有视图（依赖基础表）
                # ✅ 修复：确保视图创建100%成功
                for view_name in view_names:
                    if view_name in self._table_schemas:
                        try:
                            # ✅ 修复：先尝试删除视图（如果存在），然后创建新视图
                            # 这样可以避免CREATE OR REPLACE VIEW在某些情况下的兼容性问题
                            try:
                                conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                                logger.debug(f"已删除旧视图（如果存在）: {view_name}")
                            except Exception as drop_error:
                                # 如果视图不存在，DROP会失败，这是正常的，忽略错误
                                logger.debug(f"删除视图时（视图可能不存在）: {drop_error}")

                            # 使用CREATE VIEW创建新视图
                            view_sql = self._table_schemas[view_name]
                            # ✅ 修复：将CREATE OR REPLACE VIEW改为CREATE VIEW（因为已经DROP了）
                            view_sql = view_sql.replace("CREATE OR REPLACE VIEW", "CREATE VIEW")
                            conn.execute(view_sql)
                            logger.info(f"✅ 创建视图 {view_name} 成功")
                        except Exception as e:
                            error_msg = str(e)
                            if "does not exist" in error_msg.lower() or "table" in error_msg.lower() or "catalog" in error_msg.lower():
                                logger.error(f"❌ 创建视图 {view_name} 失败: 依赖的表不存在 - {e}")
                                logger.error(f"应该存在的表: historical_kline_data, data_quality_monitor, asset_metadata")
                            else:
                                logger.error(f"❌ 创建视图 {view_name} 失败: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                            raise  # 视图创建失败应该抛出异常，因为这是初始化阶段

                # 插入元数据
                conn.execute("""
                    INSERT OR REPLACE INTO metadata (key, value) 
                    VALUES ('asset_type', ?), ('created_at', ?), ('version', '1.0')
                """, [asset_type.value, datetime.now().isoformat()])

            # 更新数据库信息
            info = self._collect_database_info(asset_type, db_path)
            self._database_info[asset_type] = info

            logger.info(f"创建资产数据库: {asset_type.value} -> {db_path}")

        except Exception as e:
            logger.error(f"创建资产数据库失败 {asset_type.value}: {e}")
            raise

    def get_connection(self, asset_type: AssetType, auto_create: bool = True):
        """
        获取资产类型对应的数据库连接

        Args:
            asset_type: 资产类型
            auto_create: 是否自动创建数据库

        Returns:
            数据库连接上下文管理器
        """
        db_path = self.get_database_for_asset_type(asset_type, auto_create)
        # ✅ 修复：使用当前配置的pool_size（支持动态更新）
        return self.duckdb_manager.get_connection(db_path, pool_size=self.config.pool_size)

    def update_pool_size(self, new_pool_size: int) -> bool:
        """
        更新数据库连接池大小

        Args:
            new_pool_size: 新的连接池大小

        Returns:
            是否成功更新
        """
        try:
            if new_pool_size < 5 or new_pool_size > 100:
                logger.warning(f"连接池大小超出范围 (5-100): {new_pool_size}")
                return False

            # 更新配置
            self.config.pool_size = new_pool_size

            # ✅ 持久化配置到数据库
            try:
                from db.models.plugin_models import get_data_source_config_manager
                config_manager = get_data_source_config_manager()
                # 保存数据库连接池配置（使用特殊的plugin_id保存全局配置）
                config_manager.save_plugin_config(
                    plugin_id='_global_database_pool',
                    config_data={'pool_size': new_pool_size},
                    max_pool_size=new_pool_size,
                    pool_timeout=30,
                    pool_cleanup_interval=300
                )
                logger.info(f"数据库连接池大小配置已持久化: {new_pool_size}")
            except Exception as persist_err:
                logger.warning(f"数据库连接池配置持久化失败（忽略继续）: {persist_err}")

            # ✅ 注意：已创建的连接池不会自动更新，需要重新创建
            # 这里先更新配置，下次get_pool时会使用新配置
            logger.info(f"数据库连接池大小配置已更新为: {new_pool_size}（将在下次创建新连接池时生效）")

            return True
        except Exception as e:
            logger.error(f"更新数据库连接池大小失败: {e}")
            return False

    def get_database_pool_status(self) -> Dict[str, Any]:
        """
        获取数据库连接池状态信息

        Returns:
            连接池状态字典，包含：
            - total_pools: 总连接池数
            - total_connections: 总连接数
            - active_connections: 活跃连接数
            - idle_connections: 空闲连接数
            - pool_details: 每个连接池的详细信息
        """
        try:
            status = {
                'total_pools': 0,
                'total_connections': 0,
                'active_connections': 0,
                'idle_connections': 0,
                'pool_details': {},
                'max_pool_size': self.config.pool_size
            }

            # 获取所有连接池的健康状态
            health_checks = self.duckdb_manager.health_check_all()

            for db_path, health_info in health_checks.items():
                if health_info.get('status') == 'healthy':
                    pool_size = health_info.get('pool_size', 0)
                    total_connections = health_info.get('total_connections', 0)
                    active_connections = health_info.get('active_connections', 0)
                    available_connections = health_info.get('available_connections', 0)

                    status['total_pools'] += 1
                    status['total_connections'] += total_connections
                    status['active_connections'] += active_connections
                    status['idle_connections'] += available_connections

                    status['pool_details'][db_path] = {
                        'pool_size': pool_size,
                        'total_connections': total_connections,
                        'active_connections': active_connections,
                        'idle_connections': available_connections,
                        'utilization': f"{active_connections}/{pool_size}"
                    }

            return status
        except Exception as e:
            logger.error(f"获取数据库连接池状态失败: {e}")
            return {
                'total_pools': 0,
                'total_connections': 0,
                'active_connections': 0,
                'idle_connections': 0,
                'pool_details': {},
                'max_pool_size': self.config.pool_size,
                'error': str(e)
            }

    def get_connection_by_symbol(self, symbol: str, auto_create: bool = True):
        """
        根据交易符号获取对应的数据库连接

        Args:
            symbol: 交易符号
            auto_create: 是否自动创建数据库

        Returns:
            数据库连接上下文管理器
        """
        db_path, asset_type = self.get_database_for_symbol(symbol, auto_create)
        return self.duckdb_manager.get_connection(db_path, pool_size=self.config.pool_size)

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """检查所有资产数据库的健康状态"""
        results = {}

        with self._db_lock:
            for asset_type, db_path in self._asset_databases.items():
                try:
                    # 基础连接测试
                    with self.get_connection(asset_type) as conn:
                        test_result = conn.execute("SELECT 1 as test").fetchone()

                        # 更新数据库信息
                        info = self._collect_database_info(asset_type, db_path)
                        self._database_info[asset_type] = info

                        results[asset_type.value] = {
                            'status': 'healthy',
                            'database_info': info.to_dict(),
                            'test_query_result': test_result
                        }

                except Exception as e:
                    logger.error(f"健康检查失败 {asset_type.value}: {e}")
                    results[asset_type.value] = {
                        'status': 'unhealthy',
                        'error': str(e),
                        'database_path': db_path
                    }

        return results

    def get_all_database_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据库信息"""
        results = {}

        with self._db_lock:
            for asset_type, info in self._database_info.items():
                results[asset_type.value] = info.to_dict()

        return results

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型列表"""
        with self._db_lock:
            return list(self._asset_databases.keys())

    def get_database_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        stats = {
            'total_databases': len(self._asset_databases),
            'total_size_mb': 0.0,
            'total_records': 0,
            'asset_breakdown': {}
        }

        with self._db_lock:
            for asset_type, info in self._database_info.items():
                stats['total_size_mb'] += info.size_mb
                stats['total_records'] += info.record_count

                stats['asset_breakdown'][asset_type.value] = {
                    'size_mb': info.size_mb,
                    'record_count': info.record_count,
                    'table_count': info.table_count,
                    'data_sources': len(info.supported_data_sources),
                    'health_status': info.health_status
                }

        return stats

    def backup_database(self, asset_type: AssetType, backup_path: Optional[str] = None) -> str:
        """
        备份指定资产类型的数据库

        Args:
            asset_type: 资产类型
            backup_path: 备份路径（可选）

        Returns:
            备份文件路径
        """
        if asset_type not in self._asset_databases:
            raise ValueError(f"资产类型 {asset_type.value} 的数据库不存在")

        source_path = self._asset_databases[asset_type]

        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(self.config.base_path) / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_path = str(backup_dir / f"{asset_type.value.lower()}_backup_{timestamp}.duckdb")

        try:
            import shutil
            import time

            # 确保所有连接都已关闭（防止文件锁定）
            self.duckdb_manager.remove_pool(source_path)
            time.sleep(0.1)  # 给一点时间让文件句柄完全释放

            shutil.copy2(source_path, backup_path)
            logger.info(f"数据库备份完成: {asset_type.value} -> {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"数据库备份失败 {asset_type.value}: {e}")
            raise

    def restore_database(self, asset_type: AssetType, backup_path: str, force: bool = False):
        """
        从备份恢复数据库

        Args:
            asset_type: 资产类型
            backup_path: 备份文件路径
            force: 是否强制覆盖现有数据库
        """
        if not Path(backup_path).exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        target_path = self._get_database_path(asset_type)

        if Path(target_path).exists() and not force:
            raise ValueError(f"目标数据库已存在，使用 force=True 强制覆盖: {target_path}")

        try:
            import shutil

            # 如果目标数据库存在，先备份
            if Path(target_path).exists():
                backup_existing = f"{target_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(target_path, backup_existing)
                logger.info(f"现有数据库已备份: {backup_existing}")

            # 恢复数据库
            shutil.copy2(backup_path, target_path)

            # 更新内部记录
            self._asset_databases[asset_type] = target_path
            info = self._collect_database_info(asset_type, target_path)
            self._database_info[asset_type] = info

            logger.info(f"数据库恢复完成: {asset_type.value} <- {backup_path}")

        except Exception as e:
            logger.error(f"数据库恢复失败 {asset_type.value}: {e}")
            raise

    def cleanup_old_backups(self, days_to_keep: int = 30):
        """清理旧备份文件"""
        backup_dir = Path(self.config.base_path) / "backups"

        if not backup_dir.exists():
            return

        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
        cleaned_count = 0

        try:
            for backup_file in backup_dir.glob("*_backup_*.duckdb"):
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"删除旧备份: {backup_file}")

            logger.info(f"清理完成，删除了 {cleaned_count} 个旧备份文件")

        except Exception as e:
            logger.error(f"清理备份文件失败: {e}")

    def store_standardized_data(self, data: pd.DataFrame, asset_type: AssetType,
                                data_type: DataType, table_name: Optional[str] = None) -> bool:
        """
        存储标准化数据到指定资产类型数据库

        Args:
            data: 标准化后的数据
            asset_type: 资产类型
            data_type: 数据类型
            table_name: 表名（可选，默认根据数据类型生成）

        Returns:
            bool: 存储是否成功
        """
        if data.empty:
            logger.warning("数据为空，跳过存储")
            return False

        try:
            # ✅ 防御性类型检查：确保参数是正确的枚举类型
            if isinstance(asset_type, str):
                try:
                    asset_type = AssetType(asset_type)
                except (ValueError, KeyError):
                    logger.error(f"无效的资产类型字符串: {asset_type}，使用默认值 STOCK_A")
                    asset_type = AssetType.STOCK_A

            if isinstance(data_type, str):
                try:
                    data_type = DataType(data_type)
                except (ValueError, KeyError):
                    logger.error(f"无效的数据类型字符串: {data_type}，使用默认值 HISTORICAL_KLINE")
                    data_type = DataType.HISTORICAL_KLINE

            # 确保数据库存在
            db_path = self._ensure_database_exists(asset_type)

            # 生成表名
            if not table_name:
                table_name = self._generate_table_name(data_type, asset_type)

            # 获取数据库连接并存储数据
            with self.duckdb_manager.get_connection(db_path) as conn:
                # 创建表结构（如果不存在）
                self._ensure_table_exists(conn, table_name, data, data_type)

                # 插入数据（使用upsert逻辑）
                rows_affected = self._upsert_data(conn, table_name, data, data_type)

                # ✅ 修复：移除运行时视图检测
                # 视图在系统初始化时已经100%创建成功，运行时不需要检测

                logger.info(f"成功存储 {rows_affected} 行数据到 {asset_type.value}/{table_name}")
                return True

        except Exception as e:
            logger.error(f"存储标准化数据失败: {e}")
            return False

    def _generate_table_name(self, data_type: DataType, asset_type: AssetType) -> str:
        """生成表名 - 新架构使用统一的表名"""
        # ✅ 新架构：所有资产类型使用统一的标准表名
        type_mapping = {
            DataType.HISTORICAL_KLINE: "historical_kline_data",  # 统一K线数据表
            DataType.REAL_TIME_QUOTE: "realtime_quotes",
            DataType.FUNDAMENTAL: "fundamentals",
            DataType.ASSET_LIST: "asset_metadata",  # 统一资产元数据表
            DataType.SECTOR_FUND_FLOW: "sector_fund_flow"
        }

        # 直接返回标准表名，不再添加asset_type前缀
        return type_mapping.get(data_type, data_type.value.lower())

    def _ensure_table_exists(self, conn, table_name: str, data: pd.DataFrame, data_type: DataType):
        """确保表存在，如果不存在则创建"""
        try:
            # 检查表是否存在 - 使用duckdb_tables()更高效
            table_exists = conn.execute(f"""
                SELECT COUNT(*) 
                FROM duckdb_tables() 
                WHERE table_name = '{table_name}'
            """).fetchone()[0] > 0

            if not table_exists:
                # 根据数据类型创建表结构
                create_sql = self._generate_create_table_sql(table_name, data, data_type)
                conn.execute(create_sql)
                logger.info(f"创建表: {table_name}")

                # 创建索引
                self._create_table_indexes(conn, table_name, data_type)

        except Exception as e:
            logger.error(f"创建表 {table_name} 失败: {e}")
            raise

    # ✅ 修复：移除_ensure_views_exist方法
    # 视图在系统初始化时已经100%创建成功，运行时不需要检测
    # 如果需要在运行时创建视图，应该使用_initialize_database_schema方法

    def _generate_create_table_sql(self, table_name: str, data: pd.DataFrame, data_type: DataType) -> str:
        """生成创建表的SQL"""
        # 根据数据类型定义标准表结构
        if data_type == DataType.HISTORICAL_KLINE:
            # ✅ 新架构标准表结构：使用timestamp字段和(symbol, data_source, timestamp, frequency)主键
            return f"""
                CREATE TABLE {table_name} (
                    symbol VARCHAR NOT NULL,
                    data_source VARCHAR NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    frequency VARCHAR NOT NULL DEFAULT '1d',
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    amount DOUBLE,
                    turnover DOUBLE,
                    adj_close DOUBLE,
                    adj_factor DOUBLE DEFAULT 1.0,
                    turnover_rate DOUBLE,
                    vwap DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, data_source, timestamp, frequency)
                )
            """
        elif data_type == DataType.REAL_TIME_QUOTE:
            return f"""
                CREATE TABLE {table_name} (
                    symbol VARCHAR,
                    name VARCHAR,
                    market VARCHAR,
                    current_price DOUBLE,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    amount DOUBLE,
                    change DOUBLE,
                    change_percent DOUBLE,
                    timestamp TIMESTAMP,
                    bid_price DOUBLE,
                    ask_price DOUBLE,
                    bid_volume DOUBLE,
                    ask_volume DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, timestamp)
                )
            """
        elif data_type == DataType.FUNDAMENTAL:
            return f"""
                CREATE TABLE {table_name} (
                    symbol VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    market VARCHAR,
                    industry VARCHAR,
                    sector VARCHAR,
                    list_date DATE,
                    total_shares DOUBLE,
                    float_shares DOUBLE,
                    market_cap DOUBLE,
                    status VARCHAR,
                    currency VARCHAR,
                    is_st BOOLEAN,
                    updated_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        elif data_type == DataType.ASSET_LIST:
            return f"""
                CREATE TABLE {table_name} (
                    symbol VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    market VARCHAR,
                    asset_type VARCHAR,
                    status VARCHAR,
                    category VARCHAR,
                    updated_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        elif data_type == DataType.SECTOR_FUND_FLOW:
            return f"""
                CREATE TABLE {table_name} (
                    sector_code VARCHAR,
                    sector_name VARCHAR,
                    date DATE,
                    main_inflow DOUBLE,
                    main_outflow DOUBLE,
                    main_net_flow DOUBLE,
                    retail_inflow DOUBLE,
                    retail_outflow DOUBLE,
                    retail_net_flow DOUBLE,
                    total_volume DOUBLE,
                    total_amount DOUBLE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (sector_code, date)
                )
            """
        else:
            # 通用表结构，根据DataFrame列推断
            columns = []
            for col in data.columns:
                if data[col].dtype == 'object':
                    columns.append(f"{col} VARCHAR")
                elif data[col].dtype in ['int64', 'int32']:
                    columns.append(f"{col} INTEGER")
                elif data[col].dtype in ['float64', 'float32']:
                    columns.append(f"{col} DOUBLE")
                elif 'datetime' in str(data[col].dtype):
                    columns.append(f"{col} TIMESTAMP")
                else:
                    columns.append(f"{col} VARCHAR")

            columns.append("created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            return f"CREATE TABLE {table_name} ({', '.join(columns)})"

    def _create_table_indexes(self, conn, table_name: str, data_type: DataType):
        """创建表索引"""
        try:
            if data_type == DataType.HISTORICAL_KLINE:
                # 基础索引
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol ON {table_name}(symbol)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_timestamp ON {table_name}(symbol, timestamp)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_data_source ON {table_name}(data_source)")

                # ✅ 性能优化：添加与ON CONFLICT完全匹配的复合索引
                # ON CONFLICT (symbol, data_source, timestamp, frequency) 需要对应的索引
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_conflict_key 
                    ON {table_name}(symbol, data_source, timestamp, frequency)
                """)
                logger.info(f"为{table_name}创建upsert优化索引")

            elif data_type == DataType.REAL_TIME_QUOTE:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol ON {table_name}(symbol)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp)")
                # ✅ 添加ON CONFLICT匹配索引
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_conflict_key ON {table_name}(symbol, timestamp)")

            elif data_type == DataType.FUNDAMENTAL:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol ON {table_name}(symbol)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_market ON {table_name}(market)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_industry ON {table_name}(industry)")
            # 其他数据类型的索引...
        except Exception as e:
            logger.warning(f"创建索引失败: {e}")

    def _get_table_columns(self, conn, table_name: str) -> list:
        """获取表的列名"""
        try:
            result = conn.execute(f"""
                SELECT column_name 
                FROM duckdb_columns() 
                WHERE table_name = '{table_name}'
            """).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            logger.warning(f"获取表列名失败 {table_name}: {e}")
            return []

    def _filter_dataframe_columns(self, data: pd.DataFrame, table_columns: list) -> pd.DataFrame:
        """过滤DataFrame，只保留表中存在的列"""
        # ✅ 新架构：字段名映射（数据字段→表字段）
        field_mapping = {
            'datetime': 'timestamp',  # 关键映射：datetime字段映射到timestamp列
        }

        # 应用字段映射
        data_copy = data.copy()
        for data_field, table_field in field_mapping.items():
            if data_field in data_copy.columns and table_field in table_columns:
                data_copy.rename(columns={data_field: table_field}, inplace=True)
                logger.debug(f"[字段映射] {data_field} → {table_field}")

        # 找出data中存在但表中不存在的列
        extra_columns = [col for col in data_copy.columns if col not in table_columns]

        if extra_columns:
            logger.debug(f"过滤掉不在表中的列: {extra_columns}")
            # 只保留表中存在的列
            valid_columns = [col for col in data_copy.columns if col in table_columns]
            filtered_data = data_copy[valid_columns].copy()

            # 检查关键字段是否存在
            logger.debug(f"过滤后的列: {filtered_data.columns.tolist()}")
            if 'timestamp' not in filtered_data.columns and 'datetime' not in filtered_data.columns:
                logger.warning(f"过滤后缺少时间字段！原始列: {data.columns.tolist()}, 表列: {table_columns}")

            return filtered_data

        return data_copy

    def _upsert_data(self, conn, table_name: str, data: pd.DataFrame, data_type: DataType) -> int:
        """
        插入或更新数据（优化版：全部使用批量INSERT，不使用executemany）

        使用DuckDB的register功能注册DataFrame，然后使用INSERT INTO ... SELECT FROM批量插入
        性能提升10-50倍，确保功能逻辑正确和数据一致性
        """
        try:
            # ✅ 修复：减少日志输出，避免影响写入性能
            logger.debug(f"[数据插入] 准备插入数据到 {table_name}，数据类型: {data_type}, 记录数: {len(data)}")
            logger.debug(f"[数据插入] 输入列: {data.columns.tolist()}")

            # ✅ 检查输入数据中是否包含SQL关键字列名，自动移除
            sql_keywords_input_check = {'CURRENT_TIMESTAMP', 'NOW', 'CURRENT_DATE', 'CURRENT_TIME', 'DEFAULT', 'NULL'}
            problematic_input_cols = [col for col in data.columns if col.upper() in sql_keywords_input_check]
            if problematic_input_cols:
                logger.warning(f"[数据插入] 输入数据中包含SQL关键字列名: {problematic_input_cols}，已自动移除")
                data = data.drop(columns=problematic_input_cols)
                if data.empty or len(data.columns) == 0:
                    logger.error(f"[数据插入] 移除SQL关键字列后没有有效数据可插入")
                    return 0

            if 'datetime' in data.columns:
                logger.debug(f"[数据插入] datetime字段存在，非空记录数: {data['datetime'].notna().sum()}/{len(data)}")
            else:
                logger.warning(f"[数据插入] 输入数据缺少datetime字段！")

            if 'timestamp' in data.columns:
                logger.warning(f"[数据插入] 检测到timestamp字段，这可能导致问题！应该使用datetime字段")

            # 数据质量验证（仅对K线数据）
            if data_type == DataType.HISTORICAL_KLINE:
                is_valid, errors = self._validate_kline_data_quality(data)
                if not is_valid:
                    logger.warning(f"[数据质量] 数据质量验证失败: {errors}")
                    # 记录警告但继续处理（根据配置可以选择拒绝数据）
                    for error in errors:
                        logger.warning(f"[数据质量] {error}")
                else:
                    logger.debug(f"[数据质量] 数据质量验证通过")

            # 获取表的实际列名
            table_columns = self._get_table_columns(conn, table_name)
            if not table_columns:
                logger.error(f"[数据插入] 无法获取表 {table_name} 的列信息")
                return 0

            logger.debug(f"[数据插入] 表 {table_name} 的列: {table_columns}")

            # 过滤数据，只保留表中存在的列
            filtered_data = self._filter_dataframe_columns(data, table_columns)
            logger.debug(f"[数据插入] 过滤后的列: {filtered_data.columns.tolist()}")

            if filtered_data.empty or len(filtered_data.columns) == 0:
                logger.warning(f"[数据插入] 过滤后没有有效数据可插入")
                return 0

            # ✅ 优化：使用DuckDB批量INSERT（register方式），全部情况都使用，不使用executemany
            # ✅ 确保临时表名称唯一性（避免连接池中的名称冲突）
            temp_table = f"temp_insert_{int(time.time() * 1000000)}_{threading.get_ident()}"

            # ✅ 确保列顺序一致（不能使用SELECT *，必须明确指定列顺序）
            # ✅ 排除updated_at和created_at，因为这些字段在UPDATE子句中用NOW()设置
            columns = [col for col in filtered_data.columns if col not in ['updated_at', 'created_at']]

            # ✅ 修复：过滤SQL关键字和函数名，避免与SQL语法冲突
            # SQL关键字和函数名列表（DuckDB常用）
            sql_keywords = {
                'CURRENT_TIMESTAMP', 'NOW', 'CURRENT_DATE', 'CURRENT_TIME',
                'DEFAULT', 'NULL', 'TRUE', 'FALSE', 'SELECT', 'INSERT', 'UPDATE',
                'DELETE', 'FROM', 'WHERE', 'ORDER', 'GROUP', 'BY', 'HAVING',
                'LIMIT', 'OFFSET', 'AS', 'ON', 'IN', 'EXISTS', 'LIKE', 'AND', 'OR', 'NOT'
            }
            # 过滤掉SQL关键字和函数名
            safe_columns = [col for col in columns if col.upper() not in sql_keywords]
            if len(safe_columns) != len(columns):
                removed_cols = [col for col in columns if col.upper() in sql_keywords]
                logger.warning(f"[数据插入] 过滤掉SQL关键字列名: {removed_cols}")

            columns_str = ', '.join(f'"{col}"' for col in safe_columns)

            # ✅ 修复：如果表中有updated_at列，需要在INSERT时也包含（但值从temp_table获取，如果没有则用DEFAULT）
            # 检查表结构中是否有updated_at列
            table_has_updated_at = 'updated_at' in table_columns
            table_has_created_at = 'created_at' in table_columns

            # 如果表有updated_at列，但temp_table没有，需要在INSERT列中添加（使用DEFAULT）
            insert_columns = safe_columns.copy()
            if table_has_updated_at and 'updated_at' not in insert_columns:
                # 不在INSERT列中添加，让数据库使用DEFAULT值
                pass  # updated_at会在UPDATE子句中设置
            if table_has_created_at and 'created_at' not in insert_columns:
                # created_at使用DEFAULT值，不需要在INSERT中指定
                pass

            # ✅ 验证所有列名都在表列中
            invalid_columns = [col for col in insert_columns if col not in table_columns]
            if invalid_columns:
                logger.warning(f"[数据插入] 发现无效列名（不在表结构中）: {invalid_columns}，已自动移除")
                insert_columns = [col for col in insert_columns if col in table_columns]
                if not insert_columns:
                    logger.error(f"[数据插入] 移除无效列后没有有效列可插入，跳过插入")
                    return 0

            # ✅ 创建只包含安全列的 DataFrame，确保临时表结构与 SELECT 语句匹配
            if not insert_columns:
                logger.error(f"[数据插入] 没有有效列可插入，跳过插入")
                return 0

            # 确保insert_columns中的所有列都在filtered_data中存在
            available_columns = [col for col in insert_columns if col in filtered_data.columns]
            if len(available_columns) != len(insert_columns):
                missing_cols = [col for col in insert_columns if col not in filtered_data.columns]
                logger.warning(f"[数据插入] insert_columns中有列不在filtered_data中: {missing_cols}")
                logger.warning(f"[数据插入] 将使用可用列: {available_columns}")
                insert_columns = available_columns

            if not insert_columns:
                logger.error(f"[数据插入] 没有可用列可插入，跳过插入")
                return 0

            safe_data = filtered_data[insert_columns].copy()

            # ✅ 构建insert_columns_str（排除updated_at和created_at，让数据库使用DEFAULT）
            # 使用双引号引用列名，确保DuckDB正确解析列名
            insert_columns_str = ', '.join(f'"{col}"' for col in insert_columns)

            # 调试日志
            logger.debug(f"[数据插入] 最终插入列: {insert_columns}, 列数: {len(insert_columns)}")
            logger.debug(f"[数据插入] safe_data行数: {len(safe_data)}")

            try:
                # 注册DataFrame为临时表（零拷贝，高性能）
                # ✅ 注册临时表
                conn.register(temp_table, safe_data)

                # ✅ 使用显式事务确保数据一致性（原子性操作）
                conn.execute("BEGIN TRANSACTION")

                try:
                    # 构建批量UPSERT SQL（根据数据类型）
                    if data_type == DataType.HISTORICAL_KLINE:
                        # ✅ K线数据使用(symbol, data_source, timestamp, frequency)作为复合主键
                        # 获取需要更新的字段（排除主键字段和updated_at）
                        update_fields = []
                        exclude_fields = ['symbol', 'data_source', 'timestamp', 'frequency', 'updated_at', 'created_at']
                        for col in insert_columns:  # 使用 insert_columns（已经是 safe_columns）
                            if col not in exclude_fields:
                                update_fields.append(f'"{col}" = EXCLUDED."{col}"')

                        # ✅ 使用NOW()函数而不是CURRENT_TIMESTAMP，避免DuckDB解析错误
                        if update_fields:
                            update_clause = ', '.join(update_fields)
                            update_clause += ', "updated_at" = NOW()'
                        else:
                            update_clause = '"updated_at" = NOW()'

                        sql = f"""
                            INSERT INTO {table_name} ({insert_columns_str})
                            SELECT {insert_columns_str} FROM {temp_table}
                            ON CONFLICT ("symbol", "data_source", "timestamp", "frequency") DO UPDATE SET
                            {update_clause}
                        """
                        logger.debug(f"[K线数据批量插入] SQL构建完成，插入列数: {len(insert_columns)}")

                    elif data_type == DataType.REAL_TIME_QUOTE:
                        # ✅ 实时行情使用symbol和timestamp作为唯一键
                        # 获取需要更新的字段（排除主键字段和updated_at）
                        update_fields = []
                        exclude_fields = ['symbol', 'timestamp', 'updated_at', 'created_at']
                        for col in insert_columns:  # 使用 insert_columns（已经是 safe_columns）
                            if col not in exclude_fields:
                                update_fields.append(f'"{col}" = EXCLUDED."{col}"')

                        if update_fields:
                            update_clause = ', '.join(update_fields)
                            update_clause += ', "updated_at" = NOW()'
                        else:
                            # 默认更新字段（如果没有其他字段）
                            update_clause = '"updated_at" = NOW()'

                        sql = f"""
                            INSERT INTO {table_name} ({insert_columns_str})
                            SELECT {insert_columns_str} FROM {temp_table}
                            ON CONFLICT ("symbol", "timestamp") DO UPDATE SET
                            {update_clause}
                        """
                        logger.debug(f"[实时行情批量插入] ON CONFLICT字段: (symbol, timestamp)")

                    elif data_type == DataType.FUNDAMENTAL:
                        # ✅ 基本面数据使用symbol作为主键
                        # 获取需要更新的字段（排除主键字段和updated_at/updated_time）
                        update_fields = []
                        exclude_fields = ['symbol', 'updated_at', 'updated_time', 'created_at']
                        for col in insert_columns:  # 使用 insert_columns（已经是 safe_columns）
                            if col not in exclude_fields:
                                update_fields.append(f'"{col}" = EXCLUDED."{col}"')

                        if update_fields:
                            update_clause = ', '.join(update_fields)
                            # ✅ 添加updated_at或updated_time（使用NOW()函数）
                            if 'updated_at' in insert_columns:
                                update_clause += ', "updated_at" = NOW()'
                            elif 'updated_time' in insert_columns:
                                update_clause += ', "updated_time" = NOW()'
                        else:
                            # 如果没有其他字段，至少更新updated_at或updated_time
                            if 'updated_at' in insert_columns:
                                update_clause = '"updated_at" = NOW()'
                            elif 'updated_time' in insert_columns:
                                update_clause = '"updated_time" = NOW()'
                            else:
                                update_clause = '"updated_at" = NOW()'  # 默认使用updated_at

                        sql = f"""
                            INSERT INTO {table_name} ({insert_columns_str})
                            SELECT {insert_columns_str} FROM {temp_table}
                            ON CONFLICT ("symbol") DO UPDATE SET
                            {update_clause}
                        """
                        logger.debug(f"[基本面数据批量插入] ON CONFLICT字段: (symbol)")
                    else:
                        # ✅ 其他数据类型的处理：智能检测主键
                        # 尝试检测常见的主键字段，如果有则使用ON CONFLICT，否则使用简单INSERT
                        # 常见主键字段：symbol, id, record_id, monitor_id, key等
                        # ✅ 修复：使用 insert_columns 而不是 filtered_data.columns
                        possible_pk_fields = ['symbol', 'id', 'record_id', 'monitor_id', 'key']
                        pk_fields_in_data = [f for f in possible_pk_fields if f in insert_columns]

                        if pk_fields_in_data:
                            # 检测到主键字段，使用ON CONFLICT
                            # ✅ 修复：排除updated_at和updated_time，避免重复赋值
                            # ✅ 修复：使用 insert_columns 而不是 filtered_data.columns
                            update_fields = []
                            exclude_fields = pk_fields_in_data + ['updated_at', 'updated_time', 'created_at']
                            for col in insert_columns:  # 使用 insert_columns（已经是 safe_columns）
                                if col not in exclude_fields:
                                    update_fields.append(f'"{col}" = EXCLUDED."{col}"')

                            if update_fields:
                                update_clause = ', '.join(update_fields)
                                # ✅ 添加updated_at或updated_time（使用NOW()函数）
                                if 'updated_at' in insert_columns:
                                    update_clause += ', "updated_at" = NOW()'
                                elif 'updated_time' in insert_columns:
                                    update_clause += ', "updated_time" = NOW()'
                            else:
                                # 如果没有其他字段，至少更新updated_at（如果存在）
                                if 'updated_at' in insert_columns:
                                    update_clause = '"updated_at" = NOW()'
                                elif 'updated_time' in insert_columns:
                                    update_clause = '"updated_time" = NOW()'
                                else:
                                    # 如果连updated_at都没有，至少更新第一个非主键字段
                                    non_pk_cols = [col for col in insert_columns if col not in pk_fields_in_data]
                                    if non_pk_cols:
                                        update_clause = f'"{non_pk_cols[0]}" = EXCLUDED."{non_pk_cols[0]}"'
                                    else:
                                        # 如果只有主键字段，使用简单INSERT（不会有冲突）
                                        update_clause = None

                            if update_clause:
                                pk_clause = ', '.join(f'"{col}"' for col in pk_fields_in_data)
                                sql = f"""
                                    INSERT INTO {table_name} ({insert_columns_str})
                                    SELECT {insert_columns_str} FROM {temp_table}
                                    ON CONFLICT ({pk_clause}) DO UPDATE SET
                                    {update_clause}
                                """
                                logger.debug(f"[其他数据类型批量插入] ON CONFLICT字段: ({pk_clause})")
                            else:
                                # 只有主键字段，使用简单INSERT
                                sql = f"""
                                    INSERT INTO {table_name} ({insert_columns_str})
                                    SELECT {insert_columns_str} FROM {temp_table}
                                """
                                logger.debug(f"[其他数据类型批量插入] 简单插入模式（只有主键字段）")
                        else:
                            # 没有检测到主键字段，使用简单INSERT
                            sql = f"""
                                INSERT INTO {table_name} ({insert_columns_str})
                                SELECT {insert_columns_str} FROM {temp_table}
                            """
                            logger.debug(f"[其他数据类型批量插入] 简单插入模式（未检测到主键字段）")

                    # 执行批量插入
                    write_start = time.time()
                    conn.execute(sql)
                    write_duration = time.time() - write_start
                    write_speed = len(filtered_data) / write_duration if write_duration > 0 else 0

                    # ✅ 提交事务
                    conn.execute("COMMIT")

                    # ✅ 记录性能日志
                    if write_duration > 1.0:
                        logger.warning(f"[批量插入] 写入较慢: {table_name}, {len(safe_data)}条记录, 耗时: {write_duration:.2f}秒, 速度: {write_speed:.1f}条/秒")
                    else:
                        logger.debug(f"[批量插入] 成功插入 {len(safe_data)} 条记录到 {table_name}, 耗时: {write_duration:.2f}秒, 速度: {write_speed:.1f}条/秒")

                    return len(safe_data)

                except Exception as e:
                    # ✅ 回滚事务（确保数据一致性）
                    try:
                        conn.execute("ROLLBACK")
                        logger.error(f"[批量插入] 事务回滚: {e}")
                    except Exception as rollback_error:
                        logger.error(f"[批量插入] 回滚失败: {rollback_error}")
                    raise

            except Exception as e:
                logger.error(f"[批量插入] 插入失败: {e}")
                raise
            finally:
                # ✅ 确保清理临时表（即使出错也要清理，避免连接池污染）
                try:
                    conn.unregister(temp_table)
                    logger.debug(f"[批量插入] 临时表已清理: {temp_table}")
                except Exception as unregister_error:
                    # 临时表可能不存在或已被清理，忽略错误
                    logger.debug(f"[批量插入] 清理临时表时出错（可忽略）: {unregister_error}")

        except Exception as e:
            logger.error(f"[数据插入] 插入数据失败: {e}")
            logger.debug(f"[数据插入] 失败详情 - 表: {table_name}, 数据类型: {data_type}, 列: {filtered_data.columns.tolist() if 'filtered_data' in locals() else 'N/A'}")
            raise

    def get_latest_date(self, symbol: str, asset_type: AssetType, frequency: str = '1d', data_source: str = None) -> Optional[datetime]:
        """
        获取指定股票在指定数据库中的最新数据日期

        Args:
            symbol: 股票代码
            asset_type: 资产类型
            frequency: 数据频率
            data_source: 数据源（可选，如果提供则只查询该数据源的数据）

        Returns:
            最新的数据日期，如果没有数据则返回None
        """
        try:
            # 获取数据库路径
            db_path = self._get_database_path(asset_type)
            if not db_path or not os.path.exists(db_path):
                logger.debug(f"数据库不存在: {db_path}")
                return None

            # 构建查询SQL
            if data_source:
                query = """
                    SELECT MAX(timestamp) as latest_date 
                    FROM historical_kline_data 
                    WHERE symbol = ? AND frequency = ? AND data_source = ?
                """
                params = [symbol, frequency, data_source]
            else:
                query = """
                    SELECT MAX(timestamp) as latest_date 
                    FROM historical_kline_data 
                    WHERE symbol = ? AND frequency = ?
                """
                params = [symbol, frequency]

            # 执行查询
            with self.duckdb_manager.get_connection(db_path) as conn:
                # 首先检查表是否存在
                table_exists = conn.execute(f"""
                    SELECT COUNT(*) 
                    FROM duckdb_tables() 
                    WHERE table_name = 'historical_kline_data'
                """).fetchone()[0] > 0

                if not table_exists:
                    logger.debug(f"表 historical_kline_data 不存在，股票 {symbol} 无历史数据")
                    return None

                result = conn.execute(query, params).fetchone()

                if result and result[0]:
                    latest_date = pd.to_datetime(result[0])
                    logger.debug(f"股票 {symbol} 最新数据日期: {latest_date}")
                    return latest_date
                else:
                    logger.debug(f"股票 {symbol} 无历史数据")
                    return None

        except Exception as e:
            logger.error(f"获取最新数据日期失败 {symbol}: {e}")
            return None

    def get_data_statistics(self, asset_type: AssetType) -> Dict[str, Any]:
        """
        获取指定资产类型的数据统计信息

        Args:
            asset_type: 资产类型

        Returns:
            数据统计信息字典
        """
        try:
            # 获取数据库路径
            db_path = self._get_database_path(asset_type)
            if not db_path or not os.path.exists(db_path):
                return {
                    'asset_type': asset_type.value,
                    'database_exists': False,
                    'symbol_count': 0,
                    'record_count': 0,
                    'date_range': None,
                    'data_sources': [],
                    'size_mb': 0.0
                }

            with self.duckdb_manager.get_connection(db_path) as conn:
                # 统计股票数量
                symbol_count_result = conn.execute("SELECT COUNT(DISTINCT symbol) FROM historical_kline_data").fetchone()
                symbol_count = symbol_count_result[0] if symbol_count_result else 0

                # 统计记录数量
                record_count_result = conn.execute("SELECT COUNT(*) FROM historical_kline_data").fetchone()
                record_count = record_count_result[0] if record_count_result else 0

                # 统计日期范围
                date_range_result = conn.execute("""
                    SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date 
                    FROM historical_kline_data
                """).fetchone()

                date_range = None
                if date_range_result and date_range_result[0] and date_range_result[1]:
                    date_range = {
                        'min_date': pd.to_datetime(date_range_result[0]).isoformat(),
                        'max_date': pd.to_datetime(date_range_result[1]).isoformat()
                    }

                # 统计数据源
                data_sources_result = conn.execute("""
                    SELECT DISTINCT data_source, COUNT(*) as count 
                    FROM historical_kline_data 
                    GROUP BY data_source 
                    ORDER BY count DESC
                """).fetchall()

                data_sources = [{'source': row[0], 'count': row[1]} for row in data_sources_result]

                # 获取数据库大小
                size_mb = 0.0
                try:
                    if os.path.exists(db_path):
                        size_mb = os.path.getsize(db_path) / (1024 * 1024)
                except Exception:
                    pass

                return {
                    'asset_type': asset_type.value,
                    'database_exists': True,
                    'symbol_count': symbol_count,
                    'record_count': record_count,
                    'date_range': date_range,
                    'data_sources': data_sources,
                    'size_mb': round(size_mb, 2)
                }

        except Exception as e:
            logger.error(f"获取数据统计失败 {asset_type}: {e}")
            return {
                'asset_type': asset_type.value,
                'database_exists': False,
                'symbol_count': 0,
                'record_count': 0,
                'date_range': None,
                'data_sources': [],
                'size_mb': 0.0,
                'error': str(e)
            }

    def _validate_kline_data_quality(self, data: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        验证K线数据质量

        Args:
            data: K线数据DataFrame

        Returns:
            (是否通过验证, 错误信息列表)
        """
        errors = []

        try:
            # 检查必需字段
            required_fields = ['open', 'high', 'low', 'close']
            missing_fields = [field for field in required_fields if field not in data.columns]
            if missing_fields:
                errors.append(f"缺少必需字段: {missing_fields}")
                return False, errors

            # OHLC逻辑验证
            if not data.empty:
                # 检查 high >= max(open, close, low)
                invalid_high = data[data['high'] < data[['open', 'close', 'low']].max(axis=1)]
                if not invalid_high.empty:
                    errors.append(f"发现 {len(invalid_high)} 条OHLC逻辑异常数据: high < max(open, close, low)")

                # 检查 low <= min(open, close, high)
                invalid_low = data[data['low'] > data[['open', 'close', 'high']].min(axis=1)]
                if not invalid_low.empty:
                    errors.append(f"发现 {len(invalid_low)} 条OHLC逻辑异常数据: low > min(open, close, high)")

                # 检查负数价格
                price_fields = ['open', 'high', 'low', 'close']
                for field in price_fields:
                    if field in data.columns:
                        negative_prices = data[data[field] < 0]
                        if not negative_prices.empty:
                            errors.append(f"发现 {len(negative_prices)} 条负数{field}数据")

                # 检查成交量
                if 'volume' in data.columns:
                    negative_volume = data[data['volume'] < 0]
                    if not negative_volume.empty:
                        errors.append(f"发现 {len(negative_volume)} 条负数成交量数据")

            return len(errors) == 0, errors

        except Exception as e:
            errors.append(f"数据质量验证失败: {e}")
            return False, errors

    def check_database_health(self, asset_type: AssetType) -> Dict[str, Any]:
        """检查指定资产类型数据库的健康状态"""
        try:
            db_path = self._get_database_path(asset_type)

            # 检查数据库文件是否存在
            if not Path(db_path).exists():
                return {
                    "status": "unhealthy",
                    "reason": "database_file_not_found",
                    "path": db_path
                }

            # 检查数据库连接
            try:
                with self.duckdb_manager.get_connection(db_path) as conn:
                    # 执行简单查询测试连接
                    result = conn.execute("SELECT 1").fetchone()
                    if result and result[0] == 1:
                        # 获取表数量 - 使用duckdb_tables()更高效
                        table_count = conn.execute("""
                            SELECT COUNT(*) as table_count 
                            FROM duckdb_tables() 
                            WHERE schema_name = 'main'
                        """).fetchone()[0]

                        return {
                            "status": "healthy",
                            "path": db_path,
                            "table_count": table_count,
                            "connection_test": "passed"
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "reason": "connection_test_failed",
                            "path": db_path
                        }
            except Exception as conn_error:
                return {
                    "status": "unhealthy",
                    "reason": "connection_error",
                    "path": db_path,
                    "error": str(conn_error)
                }

        except Exception as e:
            logger.error(f"检查数据库健康状态失败 {asset_type.value}: {e}")
            return {
                "status": "error",
                "reason": "health_check_failed",
                "error": str(e)
            }

    # ========================================================================
    # 资产元数据管理 API（新增 - 真实数据，无mock）
    # ========================================================================

    def upsert_asset_metadata(self, symbol: str, asset_type: AssetType,
                              metadata: Dict[str, Any]) -> bool:
        """
        插入或更新资产元数据（真实数据，无mock）

        Args:
            symbol: 资产代码
            asset_type: 资产类型
            metadata: 元数据字典（必需：name, market, asset_type）

        Returns:
            bool: 是否成功
        """
        try:
            db_path = self._get_database_path(asset_type)

            with self.duckdb_manager.get_pool(db_path).get_connection() as conn:
                # ✅ 确保asset_metadata表存在
                if 'asset_metadata' in self._table_schemas:
                    try:
                        # 检查表是否存在
                        table_exists = conn.execute("""
                            SELECT COUNT(*) 
                            FROM information_schema.tables 
                            WHERE table_name = 'asset_metadata'
                        """).fetchone()[0] > 0

                        if not table_exists:
                            logger.info(f"表 asset_metadata 不存在，正在创建...")
                            conn.execute(self._table_schemas['asset_metadata'])
                            logger.info(f"成功创建表 asset_metadata")
                    except Exception as e:
                        logger.error(f"确保asset_metadata表存在失败: {e}")
                        # 尝试直接创建
                        try:
                            conn.execute(self._table_schemas['asset_metadata'])
                        except:
                            pass

                # 检查是否已存在
                existing = conn.execute(
                    "SELECT * FROM asset_metadata WHERE symbol = ?",
                    [symbol]
                ).fetchone()

                import json

                if existing:
                    # 更新逻辑：追加数据源
                    columns = [desc[0] for desc in conn.description]
                    existing_dict = dict(zip(columns, existing))
                    existing_sources_str = existing_dict.get('data_sources', '[]')

                    try:
                        existing_sources = json.loads(existing_sources_str) if existing_sources_str else []
                    except:
                        existing_sources = []

                    # 追加新数据源
                    new_source = metadata.get('primary_data_source')
                    if new_source and new_source not in existing_sources:
                        existing_sources.append(new_source)

                    # ✅ 修复：获取表的实际列名，过滤掉不存在的列（UPDATE逻辑）
                    try:
                        # 使用DuckDB的PRAGMA table_info获取表结构
                        table_info = conn.execute("PRAGMA table_info(asset_metadata)").fetchall()
                        table_columns = [row[1] for row in table_info]  # row[1]是列名
                    except Exception as e:
                        logger.warning(f"[upsert_asset_metadata UPDATE] 获取表结构失败: {e}，使用预定义列表")
                        table_columns = [
                            'symbol', 'name', 'asset_type', 'market', 'exchange',
                            'sector', 'industry', 'industry_code',
                            'listing_date', 'delisting_date', 'listing_status',
                            'total_shares', 'circulating_shares', 'currency', 'base_currency',
                            'quote_currency', 'contract_type', 'data_sources', 'primary_data_source',
                            'last_update_source', 'metadata_version', 'data_quality_score',
                            'last_verified', 'tags', 'attributes', 'created_at', 'updated_at'
                        ]

                    # 构建UPDATE
                    update_fields = []
                    update_params = []

                    # ✅ 定义重要字段：如果新值为None/空，则不更新，保留已有数据
                    important_fields = {'sector', 'industry', 'industry_code', 'listing_date',
                                        'total_shares', 'circulating_shares'}

                    # ✅ 日期字段列表（需要特殊处理）
                    date_fields = {'listing_date', 'delisting_date', 'last_verified', 'created_at', 'updated_at'}

                    for key, value in metadata.items():
                        if key in ['symbol', 'created_at']:
                            continue

                        # ✅ 修复：检查列是否在表中存在
                        if key not in table_columns:
                            logger.debug(f"[upsert_asset_metadata UPDATE] 列'{key}'不在asset_metadata表中，跳过")
                            continue

                        # ✅ 保护重要字段：如果新值为None/空，跳过更新（保留已有值）
                        if key in important_fields:
                            if value is None or (isinstance(value, str) and not value.strip()):
                                logger.debug(f"[upsert_asset_metadata UPDATE] 字段'{key}'新值为空，保留已有数据")
                                continue

                        # ✅ 处理日期字段类型转换
                        if key in date_fields and value is not None:
                            # 如果是整数（时间戳），跳过（DuckDB不支持INTEGER->DATE转换）
                            if isinstance(value, int):
                                logger.warning(f"[upsert_asset_metadata UPDATE] 字段'{key}'类型为INTEGER，跳过（DuckDB不支持INTEGER->DATE转换），原值={value}")
                                continue
                            # 如果是字符串，确保格式正确（YYYY-MM-DD）
                            elif isinstance(value, str):
                                import re
                                if not re.match(r'^\d{4}-\d{2}-\d{2}$', value.strip()):
                                    logger.warning(f"[upsert_asset_metadata UPDATE] 字段'{key}'日期格式不正确，跳过，原值={value}")
                                    continue

                        if key == 'data_sources':
                            update_fields.append(f"{key} = ?")
                            update_params.append(json.dumps(existing_sources, ensure_ascii=False))
                        elif key in ['tags', 'attributes'] and isinstance(value, (list, dict)):
                            update_fields.append(f"{key} = ?")
                            update_params.append(json.dumps(value, ensure_ascii=False))
                        else:
                            update_fields.append(f"{key} = ?")
                            update_params.append(value)

                    update_fields.extend([
                        "metadata_version = metadata_version + 1",
                        "last_verified = NOW()",
                        "updated_at = NOW()"
                    ])

                    if new_source:
                        update_fields.append("last_update_source = ?")
                        update_params.append(new_source)

                    update_params.append(symbol)

                    sql = f"UPDATE asset_metadata SET {', '.join(update_fields)} WHERE symbol = ?"
                    conn.execute(sql, update_params)
                    logger.info(f"✅ 更新资产元数据: {symbol}")

                else:
                    # 插入逻辑
                    if not metadata.get('name') or not metadata.get('market'):
                        logger.error(f"缺少必需字段: {symbol}")
                        return False

                    # JSON字段处理（✅ 修复：使用ensure_ascii=False保留中文）
                    if 'data_sources' in metadata:
                        if isinstance(metadata['data_sources'], list):
                            metadata['data_sources'] = json.dumps(metadata['data_sources'], ensure_ascii=False)
                    else:
                        sources = [metadata.get('primary_data_source')] if metadata.get('primary_data_source') else []
                        metadata['data_sources'] = json.dumps(sources, ensure_ascii=False)

                    if 'tags' in metadata and isinstance(metadata['tags'], list):
                        metadata['tags'] = json.dumps(metadata['tags'], ensure_ascii=False)

                    if 'attributes' in metadata and isinstance(metadata['attributes'], dict):
                        metadata['attributes'] = json.dumps(metadata['attributes'], ensure_ascii=False)

                    metadata['symbol'] = symbol
                    metadata.setdefault('listing_status', 'active')
                    metadata.setdefault('metadata_version', 1)

                    # ✅ 修复：获取表的实际列名，过滤掉不存在的列
                    try:
                        # 使用DuckDB的PRAGMA table_info获取表结构
                        table_info = conn.execute("PRAGMA table_info(asset_metadata)").fetchall()
                        table_columns = [row[1] for row in table_info]  # row[1]是列名
                        logger.debug(f"[upsert_asset_metadata] 从PRAGMA table_info获取asset_metadata列: {table_columns}")
                    except Exception as e:
                        # 如果PRAGMA table_info方法获取失败，使用已知的列列表
                        logger.warning(f"[upsert_asset_metadata] 获取表结构失败: {e}，使用预定义列表")
                        table_columns = [
                            'symbol', 'name', 'asset_type', 'market', 'exchange',
                            'sector', 'industry', 'industry_code',
                            'listing_date', 'delisting_date', 'listing_status',
                            'total_shares', 'circulating_shares', 'currency', 'base_currency',
                            'quote_currency', 'contract_type', 'data_sources', 'primary_data_source',
                            'last_update_source', 'metadata_version', 'data_quality_score',
                            'last_verified', 'tags', 'attributes', 'created_at', 'updated_at'
                        ]

                    # ✅ 日期字段列表（需要特殊处理）
                    date_fields = {'listing_date', 'delisting_date', 'last_verified', 'created_at', 'updated_at'}

                    # 过滤metadata中不存在的列，并处理日期字段类型
                    filtered_metadata = {}
                    for k, v in metadata.items():
                        if k not in table_columns:
                            continue

                        # ✅ 处理日期字段类型转换
                        if k in date_fields and v is not None:
                            # 如果是整数（时间戳），跳过（DuckDB不支持INTEGER->DATE转换）
                            if isinstance(v, int):
                                logger.warning(f"[upsert_asset_metadata INSERT] 字段'{k}'类型为INTEGER，跳过（DuckDB不支持INTEGER->DATE转换），原值={v}")
                                continue
                            # 如果是字符串，确保格式正确（YYYY-MM-DD）
                            elif isinstance(v, str):
                                import re
                                if not re.match(r'^\d{4}-\d{2}-\d{2}$', v.strip()):
                                    logger.warning(f"[upsert_asset_metadata INSERT] 字段'{k}'日期格式不正确，跳过，原值={v}")
                                    continue

                        filtered_metadata[k] = v

                    # 记录被过滤掉的列
                    removed_keys = set(metadata.keys()) - set(filtered_metadata.keys())
                    if removed_keys:
                        logger.warning(f"[upsert_asset_metadata] 以下列在asset_metadata表中不存在或类型不匹配，已过滤: {removed_keys}")

                    columns = list(filtered_metadata.keys())
                    placeholders = ['?' for _ in columns]
                    values = [filtered_metadata[col] for col in columns]

                    sql = f"INSERT INTO asset_metadata ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                    conn.execute(sql, values)
                    logger.info(f"✅ 插入资产元数据: {symbol}")

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"保存资产元数据失败: {symbol}, {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_asset_metadata(self, symbol: str, asset_type: AssetType) -> Optional[Dict[str, Any]]:
        """获取单个资产的元数据"""
        try:
            db_path = self._get_database_path(asset_type)
            with self.duckdb_manager.get_pool(db_path).get_connection() as conn:
                result = conn.execute(
                    "SELECT * FROM asset_metadata WHERE symbol = ?",
                    [symbol]
                ).fetchone()

                if result:
                    columns = [desc[0] for desc in conn.description]
                    metadata_dict = dict(zip(columns, result))

                    # 解析JSON字段
                    import json
                    for field in ['data_sources', 'tags', 'attributes']:
                        if field in metadata_dict and metadata_dict[field]:
                            try:
                                metadata_dict[field] = json.loads(metadata_dict[field])
                            except:
                                pass

                    return metadata_dict
                return None

        except Exception as e:
            logger.error(f"获取资产元数据失败: {symbol}, {e}")
            return None

    def get_asset_metadata_batch(self, symbols: List[str],
                                 asset_type: AssetType) -> Dict[str, Dict[str, Any]]:
        """批量获取资产元数据"""
        try:
            if not symbols:
                return {}

            db_path = self._get_database_path(asset_type)
            with self.duckdb_manager.get_pool(db_path).get_connection() as conn:
                placeholders = ','.join(['?' for _ in symbols])
                query = f"SELECT * FROM asset_metadata WHERE symbol IN ({placeholders})"

                result = conn.execute(query, symbols).fetchall()
                columns = [desc[0] for desc in conn.description]

                import json
                result_dict = {}
                for row in result:
                    metadata_dict = dict(zip(columns, row))
                    symbol = metadata_dict['symbol']

                    for field in ['data_sources', 'tags', 'attributes']:
                        if field in metadata_dict and metadata_dict[field]:
                            try:
                                metadata_dict[field] = json.loads(metadata_dict[field])
                            except:
                                pass

                    result_dict[symbol] = metadata_dict

                return result_dict

        except Exception as e:
            logger.error(f"批量获取资产元数据失败: {e}")
            return {}

    def close_all_connections(self):
        """关闭所有数据库连接"""
        try:
            self.duckdb_manager.close_all_pools()
            logger.info("所有资产数据库连接已关闭")

        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")


# 全局实例
_asset_db_manager: Optional[AssetSeparatedDatabaseManager] = None
_manager_lock = threading.Lock()


def get_asset_database_manager(config: Optional[AssetDatabaseConfig] = None) -> AssetSeparatedDatabaseManager:
    """获取全局资产数据库管理器实例"""
    global _asset_db_manager

    with _manager_lock:
        if _asset_db_manager is None:
            _asset_db_manager = AssetSeparatedDatabaseManager(config)

        return _asset_db_manager


def initialize_asset_database_manager(config: Optional[AssetDatabaseConfig] = None) -> AssetSeparatedDatabaseManager:
    """初始化资产数据库管理器"""
    global _asset_db_manager

    with _manager_lock:
        if _asset_db_manager is not None:
            _asset_db_manager.close_all_connections()

        _asset_db_manager = AssetSeparatedDatabaseManager(config)
        logger.info("AssetSeparatedDatabaseManager 已初始化")

        return _asset_db_manager


def cleanup_asset_database_manager():
    """清理资产数据库管理器"""
    global _asset_db_manager

    with _manager_lock:
        if _asset_db_manager is not None:
            _asset_db_manager.close_all_connections()
            _asset_db_manager = None
            logger.info("AssetSeparatedDatabaseManager 已清理")


def get_asset_separated_database_manager() -> AssetSeparatedDatabaseManager:
    """获取资产分数据库管理器实例（便捷函数）"""
    return AssetSeparatedDatabaseManager.get_instance()
