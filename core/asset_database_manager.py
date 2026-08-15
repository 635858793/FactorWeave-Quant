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
# R292-HVD-A: 收敛为 get_connection_manager() 模块级单例 — 原直接构造
# DuckDBConnectionManager() 会绕过单例, 与运行时 get_connection_manager()
# 消费者 (unified_data_manager / backtest_result_manager 等) 各自建池,
# 同 DB 双池 + 配置 (R288/R289 apply_default_config 仅注入单例) 不共享。
from core.database.duckdb_manager import get_connection_manager, DuckDBConfig
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
        elif not getattr(cls._instance, '_initialized', False):
            # 防御：__new__ 直建裸实例（测试或异常路径绕过 __init__）被注册为单例时，
            # 补齐初始化，否则 get_database_path 等访问 self.config 会 AttributeError，
            # 且可能携带 __new__ 后临时打上的 MagicMock 属性污染运行期。
            cls._instance.__init__(config)
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

        # 修复：从数据库加载数据库连接池配置
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
        # R292-HVD-A: 收敛为模块级单例 (duckdb_manager.py:851 get_connection_manager),
        # 全局唯一连接池 + 配置统一生效; initialize_duckdb_manager 已幂等化,
        # SectorDataService 懒加载重建不会使本引用失效。
        self.duckdb_manager = get_connection_manager()

        # 数据库映射和信息
        self._asset_databases: Dict[AssetType, str] = {}
        self._database_info: Dict[AssetType, AssetDatabaseInfo] = {}

        # 线程锁
        self._db_lock = threading.RLock()

        # 关键修复：数据库级别写入锁，防止并发写入导致DuckDB ART索引冲突
        # DuckDB不支持真正的并发写入，必须串行化写入操作
        self._write_lock = threading.Lock()

        # HVD-C: monitor_latest 历史预填并发上限。旧库升级时最多 16 个 db 文件
        # (asset/sector 别名映射) 各 spawn 一个预填线程 (L977-982), 若同时执行
        # 全表 GROUP BY 聚合会放大 IO/CPU 争用。Semaphore(2) 保证同时最多 2 个
        # 回填在执行, 其余线程排队错峰 (首启升级一次性场景, 无长尾)。
        self._backfill_semaphore = threading.Semaphore(2)

        # R237 HVD-237-B-001: dispose 幂等标志 (R78 铁律 #6)
        self._disposed = False

        # 标准表结构定义
        self._table_schemas = self._initialize_table_schemas()

        # R287 P1-2：表结构/列元数据会话级缓存（key=db_path|table_name）。
        # 每次落库 store_standardized_data 都触发 _ensure_table_exists 的
        # duckdb_tables() 查询 + _migrate_table_schema 的 DESCRIBE，以及
        # _upsert_data 内 _get_table_columns 的 duckdb_columns() 查询，
        # 单次落库 3 次元数据查询、零缓存。此处按库+表缓存"已确认存在"与
        # 列名列表，命中直接跳过（表结构在会话内由本类独占维护，不失效）。
        self._table_exists_cache: Dict[str, bool] = {}
        self._table_columns_cache: Dict[str, List[str]] = {}

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
                    frequency VARCHAR NOT NULL DEFAULT '1d',
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

            # R287 P0-2：质量最近评估物化表。
            # data_quality_monitor 按 check_date 逐日累积（每 symbol+source+frequency 每天
            # 一条），视图内 latest 子查询需全表 GROUP BY，聚合成本随天数线性增长。
            # monitor_latest 每 symbol+data_source+frequency 仅保留最近一次评估（INSERT OR
            # REPLACE 幂等维护），视图/查询直接 JOIN 该精简表，避免每次全表聚合。
            'monitor_latest': """
                CREATE TABLE IF NOT EXISTS monitor_latest (
                    symbol VARCHAR NOT NULL,
                    data_source VARCHAR NOT NULL,
                    frequency VARCHAR NOT NULL DEFAULT '1d',
                    check_date DATE NOT NULL,
                    quality_score DECIMAL(5,2),
                    anomaly_count INTEGER DEFAULT 0,
                    missing_count INTEGER DEFAULT 0,
                    completeness_score DECIMAL(5,2),
                    details TEXT,
                    PRIMARY KEY (symbol, data_source, frequency)
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
                    -- R285 修复：JOIN 断链——原条件 DATE(hkd.timestamp) = dqm.check_date
                    -- 中 check_date 是"落库评估当天"（store_standardized_data 落库时写
                    -- date.today()），而 hkd.timestamp 是 K 线交易日，历史 K 线永远无法
                    -- 命中 → quality_score 恒 NULL → 回退硬编码数据源优先级，"质量优选"
                    -- 对历史数据名存实亡。改为关联"每 symbol+data_source+frequency 最近
                    -- 一次评估记录"（质量分代表该源最近一次落库的整体质量，与交易日解耦）。
                    -- R287 P0-2：JOIN 目标由"全表 GROUP BY 最近评估子查询"改为物化表
                    -- monitor_latest（每 symbol+data_source+frequency 仅一行，落库时
                    -- INSERT OR REPLACE 同步维护），消除每次查询的全表聚合开销。
                    LEFT JOIN monitor_latest dqm ON (
                        hkd.symbol = dqm.symbol
                        AND hkd.data_source = dqm.data_source
                        AND hkd.frequency = dqm.frequency
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

            # 基本面数据+元数据视图（便捷查询）
            'fundamental_with_metadata': """
                CREATE OR REPLACE VIEW fundamental_with_metadata AS
                SELECT 
                    f.*,
                    m.name,
                    m.exchange,
                    m.listing_status,
                    m.sector,
                    m.industry as metadata_industry
                FROM fundamentals f
                LEFT JOIN asset_metadata m ON f.symbol = m.symbol
            """,

            # 基本面数据表（新增）
            'fundamentals': """
                CREATE TABLE IF NOT EXISTS fundamentals (
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
                    error_code TEXT,
                    
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
            """,

            # 股票股本数据表
            'stock_shares': """
                CREATE TABLE IF NOT EXISTS stock_shares (
                    -- 主键
                    id INTEGER PRIMARY KEY,
                    
                    -- 股票标识
                    stock_code VARCHAR(20) NOT NULL,
                    stock_name VARCHAR(100),
                    
                    -- 股本数据（BIGINT，单位：股）
                    total_shares BIGINT NOT NULL,
                    circulating_shares BIGINT NOT NULL,
                    
                    -- 市值数据（DECIMAL，单位：元）
                    total_market_cap DECIMAL(18,2),
                    circulating_market_cap DECIMAL(18,2),
                    
                    -- 更新信息
                    update_date DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 唯一约束：同一股票在同一日期只能有一条记录
                    UNIQUE(stock_code, update_date)
                )
            """,

            # 期货合约数据表
            'futures_contracts': """
                CREATE TABLE IF NOT EXISTS futures_contracts (
                    -- 主键
                    id INTEGER PRIMARY KEY,
                    
                    -- 合约标识
                    contract_code VARCHAR(20) NOT NULL,
                    contract_name VARCHAR(100),
                    underlying_asset VARCHAR(20) NOT NULL,
                    
                    -- 合约规格
                    contract_multiplier DECIMAL(10,2) NOT NULL,
                    contract_size DECIMAL(10,2) NOT NULL,
                    tick_size DECIMAL(10,4) NOT NULL,
                    
                    -- 合约信息
                    contract_type VARCHAR(20),
                    exchange VARCHAR(20),
                    delivery_month VARCHAR(10),
                    expiry_date DATE,
                    
                    -- 交易信息
                    trading_hours VARCHAR(100),
                    margin_ratio DECIMAL(10,6),
                    
                    -- 更新信息
                    update_date DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 唯一约束：同一合约在同一日期只能有一条记录
                    UNIQUE(contract_code, update_date)
                )
            """,

            # 期权合约数据表
            'option_contracts': """
                CREATE TABLE IF NOT EXISTS option_contracts (
                    -- 主键
                    id INTEGER PRIMARY KEY,
                    
                    -- 合约标识
                    contract_code VARCHAR(20) NOT NULL,
                    contract_name VARCHAR(100),
                    underlying_asset VARCHAR(20) NOT NULL,
                    
                    -- 期权类型
                    option_type VARCHAR(10) NOT NULL,
                    strike_price DECIMAL(18,4) NOT NULL,
                    
                    -- 合约规格
                    contract_multiplier DECIMAL(10,2) NOT NULL,
                    contract_size DECIMAL(10,2) NOT NULL,
                    tick_size DECIMAL(10,4) NOT NULL,
                    
                    -- 合约信息
                    exchange VARCHAR(20),
                    expiry_date DATE,
                    exercise_type VARCHAR(20),
                    
                    -- 交易信息
                    trading_hours VARCHAR(100),
                    margin_ratio DECIMAL(10,6),
                    
                    -- 更新信息
                    update_date DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 唯一约束：同一合约在同一日期只能有一条记录
                    UNIQUE(contract_code, update_date)
                )
            """,

            # 权证合约数据表
            'warrant_contracts': """
                CREATE TABLE IF NOT EXISTS warrant_contracts (
                    -- 主键
                    id INTEGER PRIMARY KEY,
                    
                    -- 合约标识
                    warrant_code VARCHAR(20) NOT NULL,
                    warrant_name VARCHAR(100),
                    underlying_asset VARCHAR(20) NOT NULL,
                    
                    -- 权证类型
                    warrant_type VARCHAR(20),
                    
                    -- 合约规格
                    contract_multiplier DECIMAL(10,2) NOT NULL,
                    contract_size DECIMAL(10,2) NOT NULL,
                    tick_size DECIMAL(10,4) NOT NULL,
                    
                    -- 合约信息
                    exchange VARCHAR(20),
                    expiry_date DATE,
                    
                    -- 行权信息
                    exercise_price DECIMAL(18,4),
                    exercise_ratio DECIMAL(10,6),
                    
                    -- 交易信息
                    trading_hours VARCHAR(100),
                    margin_ratio DECIMAL(10,6),
                    
                    -- 更新信息
                    update_date DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 唯一约束：同一权证在同一日期只能有一条记录
                    UNIQUE(warrant_code, update_date)
                )
            """,

            # 加密货币供应量数据表
            'crypto_supply': """
                CREATE TABLE IF NOT EXISTS crypto_supply (
                    -- 主键
                    id INTEGER PRIMARY KEY,
                    
                    -- 加密货币标识
                    crypto_code VARCHAR(20) NOT NULL,
                    crypto_name VARCHAR(100),
                    
                    -- 供应量数据（BIGINT，单位：最小单位）
                    total_supply BIGINT NOT NULL,
                    circulating_supply BIGINT NOT NULL,
                    max_supply BIGINT,
                    
                    -- 市值数据（DECIMAL，单位：美元）
                    market_cap DECIMAL(18,2),
                    circulating_market_cap DECIMAL(18,2),
                    
                    -- 更新信息
                    update_date DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 唯一约束：同一加密货币在同一日期只能有一条记录
                    UNIQUE(crypto_code, update_date)
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

                # 修复：在系统初始化时，100%确保表和视图都存在
                try:
                    self._initialize_database_schema(asset_type, db_path)
                    logger.info(f"数据库架构初始化完成: {asset_type.value}")
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
        # 增强：完善资产类型映射逻辑
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
            # 移除STOCK映射，因为STOCK类型已被移除
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
            with self.duckdb_manager.get_connection(db_path, pool_size=self.config.pool_size) as conn:
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
                except Exception:
                    pass  # 表可能不存在

                # 获取支持的数据源
                supported_sources = []
                try:
                    sources_result = conn.execute("""
                        SELECT DISTINCT data_source 
                        FROM historical_kline_data
                    """).fetchall()
                    supported_sources = [row[0] for row in sources_result]
                except Exception:
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
                        # 修复：数据库文件已存在，不需要在这里处理
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
        修复：在系统初始化时，100%确保数据库架构完整（表和视图都存在）

        这个方法在系统启动时调用，确保：
        1. 所有必要的表都存在
        2. 所有视图都存在
        3. 如果表或视图不存在，自动创建

        Args:
            asset_type: 资产类型
            db_path: 数据库文件路径
        """
        try:
            view_names = ['unified_best_quality_kline', 'kline_with_metadata', 'fundamental_with_metadata']

            # R292-HVD-B: 预热建池显式传 self.config.pool_size (默认10, 可被数据库
            # max_pool_size 配置 5-100 覆盖), 池由首个调用者定容, 此处是启动
            # 预热决定性入口 (原默认15 → 8库×15=120 连接)
            with self.duckdb_manager.get_connection(db_path, pool_size=self.config.pool_size) as conn:
                # 数据库迁移：为现有的data_quality_monitor表添加frequency字段
                # 只在表已存在且缺少frequency字段时才执行迁移
                try:
                    # 检查表是否存在
                    table_exists = conn.execute("""
                        SELECT COUNT(*) 
                        FROM duckdb_tables() 
                        WHERE table_name = 'data_quality_monitor'
                    """).fetchone()[0] > 0
                    
                    if table_exists:
                        # 检查frequency字段是否存在
                        check_column = conn.execute("""
                            SELECT COUNT(*) 
                            FROM information_schema.columns 
                            WHERE table_name = 'data_quality_monitor' 
                            AND column_name = 'frequency'
                        """).fetchone()
                        
                        if check_column[0] == 0:
                            # 字段不存在，添加frequency字段
                            conn.execute("ALTER TABLE data_quality_monitor ADD COLUMN frequency VARCHAR DEFAULT '1d'")
                            logger.info("数据库迁移：为现有的data_quality_monitor表添加frequency字段")
                        else:
                            logger.debug("data_quality_monitor表已包含frequency字段，跳过迁移")
                    else:
                        logger.debug("data_quality_monitor表不存在，跳过迁移（新建数据库时会自动创建）")
                except Exception as migration_error:
                    logger.warning(f"数据库迁移检查失败: {migration_error}")

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
                            logger.info(f"初始化时创建表 {table_name} 成功")

                            # 如果是K线数据表，创建索引
                            if table_name == 'historical_kline_data':
                                self._create_table_indexes(conn, table_name, DataType.HISTORICAL_KLINE)
                            
                            # 如果是数据质量监控表，创建索引
                            if table_name == 'data_quality_monitor':
                                self._create_table_indexes(conn, table_name, None)
                            
                            # 如果是订单表，创建索引
                            if table_name == 'orders':
                                self._create_orders_table_indexes(conn)
                            
                            # 为新增的股本/合约表创建索引
                            if table_name in ['stock_shares', 'futures_contracts', 'option_contracts', 'warrant_contracts', 'crypto_supply']:
                                self._create_table_indexes(conn, table_name, None)
                        else:
                            logger.debug(f"表 {table_name} 已存在")
                    except Exception as e:
                        logger.error(f"❌ 初始化时创建表 {table_name} 失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        raise  # 表创建失败应该抛出异常

                # R287 P0-2 + R288：monitor_latest 历史预填（旧库升级场景）。
                # data_quality_monitor 已积累历史记录而 monitor_latest 为空时，
                # 视图 JOIN 会回退硬编码数据源优先级，失去质量优选。此处用
                # data_quality_monitor 最近一次评估一次性回填（INSERT OR REPLACE
                # 幂等，后续由 _evaluate_and_record_quality / import_execution_engine
                # 落库时同步维护）。
                # R288 修复：a) 空表守卫——monitor_latest 非空直接跳过，避免每次启动
                # 都全表 GROUP BY 重算（二次启动起零开销）；b) 旧库首次升级（表空）时
                # 预填放后台线程执行——初始化运行在 Qt 主线程、事件循环启动前，
                # data_quality_monitor 数十万行时全表聚合可阻塞主线程数秒~十几秒。
                try:
                    existing = conn.execute(
                        "SELECT COUNT(*) FROM monitor_latest"
                    ).fetchone()[0]
                    if existing > 0:
                        self._monitor_latest_table_ready = True
                        logger.debug(f"monitor_latest 已有 {existing} 条数据，跳过历史预填")
                    else:
                        threading.Thread(
                            target=self._async_backfill_monitor_latest,
                            args=(db_path,),
                            daemon=True,
                            name="monitor-latest-backfill",
                        ).start()
                except Exception as e:
                    logger.warning(f"monitor_latest 预填检查失败（表不存在属正常）: {e}")

                # 第二步：确保所有视图存在（使用CREATE OR REPLACE VIEW确保100%成功）
                for view_name in view_names:
                    if view_name not in self._table_schemas:
                        continue

                    try:
                        # 修复：先尝试删除视图（如果存在），然后创建新视图
                        # 这样可以避免CREATE OR REPLACE VIEW在某些情况下的兼容性问题
                        try:
                            conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                            logger.debug(f"已删除旧视图（如果存在）: {view_name}")
                        except Exception as drop_error:
                            # 如果视图不存在，DROP会失败，这是正常的，忽略错误
                            logger.debug(f"删除视图时（视图可能不存在）: {drop_error}")

                        # 使用CREATE VIEW创建新视图
                        view_sql = self._table_schemas[view_name]
                        # 修复：将CREATE OR REPLACE VIEW改为CREATE VIEW（因为已经DROP了）
                        view_sql = view_sql.replace("CREATE OR REPLACE VIEW", "CREATE VIEW")
                        conn.execute(view_sql)
                        logger.info(f"初始化时创建/更新视图 {view_name} 成功")
                    except Exception as e:
                        error_msg = str(e)
                        # 如果错误是因为表不存在，记录错误并抛出异常
                        if "does not exist" in error_msg.lower() or "table" in error_msg.lower() or "catalog" in error_msg.lower():
                            logger.error(f"❌ 初始化时创建视图 {view_name} 失败: 依赖的表不存在 - {e}")
                            logger.error("这不应该发生，因为表应该已经在上一步创建了")
                            # 增强：列出所有应该存在的表，帮助调试
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
            
            logger.info("orders 表索引创建成功")
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

            # R292-HVD-B: 新建库建池显式传 pool_size (原默认15)
            with self.duckdb_manager.get_connection(db_path, pool_size=self.config.pool_size,
                                                    config=duckdb_config) as conn:
                # 数据库迁移：为现有的data_quality_monitor表添加frequency字段
                # 只在表已存在且缺少frequency字段时才执行迁移
                try:
                    # 检查表是否存在
                    table_exists = conn.execute("""
                        SELECT COUNT(*) 
                        FROM duckdb_tables() 
                        WHERE table_name = 'data_quality_monitor'
                    """).fetchone()[0] > 0
                    
                    if table_exists:
                        # 检查frequency字段是否存在
                        check_column = conn.execute("""
                            SELECT COUNT(*) 
                            FROM information_schema.columns 
                            WHERE table_name = 'data_quality_monitor' 
                            AND column_name = 'frequency'
                        """).fetchone()
                        
                        if check_column[0] == 0:
                            # 字段不存在，添加frequency字段
                            conn.execute("ALTER TABLE data_quality_monitor ADD COLUMN frequency VARCHAR DEFAULT '1d'")
                            logger.info("数据库迁移：为现有的data_quality_monitor表添加frequency字段")
                        else:
                            logger.debug("data_quality_monitor表已包含frequency字段，跳过迁移")
                    else:
                        logger.debug("data_quality_monitor表不存在，跳过迁移（新建数据库时会自动创建）")
                except Exception as migration_error:
                    logger.warning(f"数据库迁移检查失败: {migration_error}")

                # 区分表和视图
                view_names = ['unified_best_quality_kline', 'kline_with_metadata', 'fundamental_with_metadata']

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
                
                # 第三步：为新增的股本/合约表创建索引
                for table_name in ['stock_shares', 'futures_contracts', 'option_contracts', 'warrant_contracts', 'crypto_supply']:
                    try:
                        self._create_table_indexes(conn, table_name, None)
                    except Exception as e:
                        logger.error(f"创建 {table_name} 表索引失败: {e}")
                        # 索引创建失败不中断流程，记录警告即可

                # 第四步：创建所有视图（依赖基础表）
                # 修复：确保视图创建100%成功
                for view_name in view_names:
                    if view_name in self._table_schemas:
                        try:
                            # 修复：先尝试删除视图（如果存在），然后创建新视图
                            # 这样可以避免CREATE OR REPLACE VIEW在某些情况下的兼容性问题
                            try:
                                conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                                logger.debug(f"已删除旧视图（如果存在）: {view_name}")
                            except Exception as drop_error:
                                # 如果视图不存在，DROP会失败，这是正常的，忽略错误
                                logger.debug(f"删除视图时（视图可能不存在）: {drop_error}")

                            # 使用CREATE VIEW创建新视图
                            view_sql = self._table_schemas[view_name]
                            # 修复：将CREATE OR REPLACE VIEW改为CREATE VIEW（因为已经DROP了）
                            view_sql = view_sql.replace("CREATE OR REPLACE VIEW", "CREATE VIEW")
                            conn.execute(view_sql)
                            logger.info(f"创建视图 {view_name} 成功")
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
        # 修复：使用当前配置的pool_size（支持动态更新）
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

            # 持久化配置到数据库
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

            # HVD-E: 运行时立即重建全部池为新容量（不再"下次建池生效"）。
            # rebuild_all_pools 必须显式传 pool_size——apply_default_config
            # (duckdb_manager.py:659) 重建不传参的教训是落回默认 50。
            # 重建中断窗口内业务连接短暂排队（池满有 30s 临时逃生通道），不中断业务。
            try:
                self.duckdb_manager.rebuild_all_pools(new_pool_size)
                logger.info(f"数据库连接池大小已更新为: {new_pool_size}（已立即生效）")
            except Exception as rebuild_err:
                logger.error(f"连接池重建失败（下次建池时按新配置生效）: {rebuild_err}")

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
            # 防御性类型检查：确保参数是正确的枚举类型
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

            # R275 兜底：所有插件（东财/baostock/akshare/tongdaxin/sina/crypto/期货等 11 文件 12 处
            # set_index('datetime')/set_index('date')）返回的 K 线 df 均以时间为索引，
            # 此处统一在落库入口兼容，覆盖全部 store_standardized_data 调用方（含导入/HTTP 桥接路径），
            # 避免 timestamp 列缺失违反 NOT NULL 约束导致落库失败。
            if data_type == DataType.HISTORICAL_KLINE:
                if ('timestamp' not in data.columns
                        and 'datetime' not in data.columns
                        and 'date' not in data.columns
                        and (isinstance(data.index, pd.DatetimeIndex)
                             or data.index.name in ('datetime', 'date'))):
                    data = data.reset_index()
                    # R292 修复：无命名 DatetimeIndex reset_index 后新列为 'index'，
                    # 统一改名为 datetime（与 unified_data_manager._persist_kdata_to_duckdb 一致），
                    # 否则 timestamp 列缺失 → 违反 NOT NULL 约束落库失败。
                    if 'index' in data.columns and 'datetime' not in data.columns:
                        data = data.rename(columns={'index': 'datetime'})

                # R278 数据治理：落库质量门禁。
                # 统一对所有经 store_standardized_data 落库的 K 线数据做多维质量评估，
                # 并将质量分写入 data_quality_monitor 表（此前仅 import_execution_engine
                # 路径写该表，TET 主链路 / HTTP 桥接等路径落库不评估 →
                # unified_best_quality_kline 视图对大部分数据回退硬编码数据源优先级 50-65）。
                # 严重质量缺陷记录警告，默认不阻断落库（保持现有兼容行为）。
                # R285 修复2：落库质量准入——捕获质量分，开启配置
                # data.reject_low_quality_kline 后，低质量 K 线（<60 分）拒绝落库；
                # 默认 False 保持"只记录不拦截"兼容行为，坏数据至少写入 monitor 可追溯。
                try:
                    quality_score = self._evaluate_and_record_quality(data, asset_type)
                    if (quality_score is not None
                            and self._reject_low_quality_kline_enabled()
                            and quality_score < self._QUALITY_REJECT_THRESHOLD):
                        symbol = str(data['symbol'].iloc[0]) if 'symbol' in data.columns else '?'
                        logger.warning(f"[数据质量] 低质量K线拒绝落库 symbol={symbol} "
                                       f"score={quality_score:.1f} < {self._QUALITY_REJECT_THRESHOLD}")
                        return False
                except Exception as quality_error:
                    logger.debug(f"落库质量评估/记录失败: {quality_error}")

            # 确保数据库存在
            db_path = self._ensure_database_exists(asset_type)

            # 生成表名
            if not table_name:
                table_name = self._generate_table_name(data_type, asset_type)

            # 关键修复：使用写入锁保护数据库写入操作
            # DuckDB不支持真正的并发写入，必须串行化写入操作以避免ART索引冲突
            with self._write_lock:
                # 获取数据库连接并存储数据
                with self.duckdb_manager.get_connection(db_path) as conn:
                    # 创建表结构（如果不存在）
                    self._ensure_table_exists(conn, table_name, data, data_type)

                    # 插入数据（使用upsert逻辑）
                    rows_affected = self._upsert_data(conn, table_name, data, data_type)

                    # 修复：移除运行时视图检测
                    # 视图在系统初始化时已经100%创建成功，运行时不需要检测

                    logger.info(f"成功存储 {rows_affected} 行数据到 {asset_type.value}/{table_name}")
                    return True

        except Exception as e:
            logger.error(f"存储标准化数据失败: {e}")
            return False

    def _evaluate_and_record_quality(self, data: pd.DataFrame, asset_type: AssetType) -> float:
        """R278 数据治理：落库质量门禁实现

        1) 对 K 线数据做多维质量评估（完整性/准确性/一致性/唯一性 + OHLC 逻辑，
           委托 DataQualityRiskManager → DataQualityMonitor，data_type='kline'
           触发 K 线跳变/量能专项检测）。
        2) OHLC 必需字段缺失或严重逻辑异常 → 记录 warning（默认不阻断，兼容现状）。
        3) 质量分写入 data_quality_monitor 表（INSERT OR REPLACE 幂等），
           使 unified_best_quality_kline 视图用真实评分排序。

        Returns:
            float: 质量分 0-100
        """
        from datetime import date
        _eval_start = time.perf_counter()
        quality_manager = self._get_quality_manager()
        report = quality_manager.assess_quality(data, 'kline', {
            'source': 'store_standardized_data',
            # R285 修复6：落库评估属于历史回填/增量补库场景，K 线最新交易日早于
            # 当天是正常状态（场景B 拉更早历史），标记 backfill 让 timeliness 给
            # 中性分，避免"历史回填被当质量缺陷惩罚"。
            'backfill': True,
        })
        score = float(report.get('quality_score', 0) or 0)
        _eval_elapsed = (time.perf_counter() - _eval_start) * 1000
        logger.debug(f"[质量评估] {len(data)} 条记录六维评估耗时 {_eval_elapsed:.1f}ms, score={score:.1f}")

        # OHLC 必需字段/逻辑校验（严重缺陷给出明确警告）
        try:
            ohlc_valid, ohlc_errors = self._validate_kline_data_quality(data)
            if not ohlc_valid:
                logger.warning(f"[数据质量] K线落库OHLC校验未通过 (score={score:.1f}): {ohlc_errors}")
        except Exception as e:
            logger.debug(f"OHLC校验异常: {e}")

        # 质量分写库（供 unified_best_quality_kline 视图真实评分）
        try:
            if 'symbol' not in data.columns:
                return score
            symbol = str(data['symbol'].iloc[0])
            if not symbol:
                return score
            source = str(data['data_source'].iloc[0]) if 'data_source' in data.columns else 'tet_plugin'
            freq = str(data['frequency'].iloc[0]) if 'frequency' in data.columns else '1d'
            monitor_id = f"{symbol}_{source}_{date.today().isoformat()}_{freq}"
            missing_count = int(data.isnull().sum().sum())
            completeness = float(report.get('completeness', 0) or 0) / 100.0
            anomaly_count = int(report.get('issues', 0) or 0)
            total_records = int(len(data))

            with self._write_lock:
                _write_start = time.perf_counter()
                with self.duckdb_manager.get_connection(self._ensure_database_exists(asset_type)) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO data_quality_monitor
                        (monitor_id, symbol, data_source, check_date, frequency,
                         quality_score, anomaly_count, missing_count,
                         completeness_score, details)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [monitor_id, symbol, source, date.today(), freq,
                         round(score, 2), anomaly_count, missing_count,
                         round(completeness, 4),
                         f"Records: {total_records}, Quality: {score:.2f}"]
                    )
                    # R287 P0-2：同步维护 monitor_latest 物化表（每 symbol+data_source+
                    # frequency 仅保留最近一次评估，替代视图/查询内全表 GROUP BY 子查询）
                    self._ensure_monitor_latest_table(conn)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO monitor_latest
                        (symbol, data_source, frequency, check_date, quality_score,
                         anomaly_count, missing_count, completeness_score, details)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [symbol, source, freq, date.today(),
                         round(score, 2), anomaly_count, missing_count,
                         round(completeness, 4),
                         f"Records: {total_records}, Quality: {score:.2f}"]
                    )
                _write_elapsed = (time.perf_counter() - _write_start) * 1000
                logger.debug(f"[质量分写库] {symbol}/{freq} monitor+monitor_latest 写库耗时 {_write_elapsed:.1f}ms")
        except Exception as write_error:
            logger.debug(f"质量分写库失败: {write_error}")

        return score

    def _ensure_monitor_latest_table(self, conn) -> None:
        """R287 P0-2：确保 monitor_latest 物化表存在（会话级标志缓存，仅首建时执行 DDL）

        monitor_latest 随 _table_schemas 在系统初始化时自动创建；此处兜底兼容
        旧库升级/未走初始化路径的场景，CREATE TABLE IF NOT EXISTS 幂等。
        """
        if getattr(self, '_monitor_latest_table_ready', False):
            return
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitor_latest (
                    symbol VARCHAR NOT NULL,
                    data_source VARCHAR NOT NULL,
                    frequency VARCHAR NOT NULL DEFAULT '1d',
                    check_date DATE NOT NULL,
                    quality_score DECIMAL(5,2),
                    anomaly_count INTEGER DEFAULT 0,
                    missing_count INTEGER DEFAULT 0,
                    completeness_score DECIMAL(5,2),
                    details TEXT,
                    PRIMARY KEY (symbol, data_source, frequency)
                )
            """)
            self._monitor_latest_table_ready = True
        except Exception as e:
            logger.debug(f"确保 monitor_latest 表存在失败: {e}")

    def _async_backfill_monitor_latest(self, db_path: str) -> None:
        """R288：后台线程回填 monitor_latest（旧库升级首次触发）

        初始化（_initialize_database_schema）运行在 Qt 主线程、事件循环启动前，
        预填 SQL 对 data_quality_monitor 全表 GROUP BY，数据量大（数十万行）时
        可阻塞主线程数秒~十几秒。仅在 monitor_latest 为空（旧库首次升级）时触发
        一次；线程内用独立连接（DuckDB 连接不跨线程共享，不能复用初始化 conn）。
        回填完成前视图 JOIN 空 monitor_latest 走 LEFT JOIN + 硬编码优先级回退
        （unified_best_quality_kline 定义注释明示此兜底行为），功能不丢失，
        仅质量优选延迟生效（后台秒级完成）。
        """
        # HVD-C: 信号量限并发错峰——多 db 文件同时升级时, 最多 2 个回填并行,
        # 其余排队, 避免 16 线程同时对各自 data_quality_monitor 全表 GROUP BY。
        with self._backfill_semaphore:
            try:
                with self.duckdb_manager.get_connection(db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO monitor_latest
                        (symbol, data_source, frequency, check_date, quality_score,
                         anomaly_count, missing_count, completeness_score, details)
                        SELECT dqm2.symbol, dqm2.data_source, dqm2.frequency, dqm2.check_date,
                               dqm2.quality_score, dqm2.anomaly_count, dqm2.missing_count,
                               dqm2.completeness_score, dqm2.details
                        FROM data_quality_monitor dqm2
                        INNER JOIN (
                            SELECT symbol, data_source, frequency,
                                   MAX(check_date) AS max_check_date
                            FROM data_quality_monitor
                            GROUP BY symbol, data_source, frequency
                        ) latest_dqm ON dqm2.symbol = latest_dqm.symbol
                            AND dqm2.data_source = latest_dqm.data_source
                            AND dqm2.frequency = latest_dqm.frequency
                            AND dqm2.check_date = latest_dqm.max_check_date
                    """)
                    self._monitor_latest_table_ready = True
                    logger.info(f"monitor_latest 物化表历史预填完成（后台线程）: {db_path}")
            except Exception as e:
                logger.warning(f"monitor_latest 历史预填失败（后台线程）: {db_path} - {e}")

    def _get_quality_manager(self):
        """R278：惰性获取 DataQualityRiskManager 单例（模块内复用，避免每次落库 new）"""
        quality_manager = getattr(self, '_quality_manager', None)
        if quality_manager is None:
            from core.data_quality_risk_manager import DataQualityRiskManager
            quality_manager = DataQualityRiskManager()
            self._quality_manager = quality_manager
        return quality_manager

    # R285 修复2：落库质量准入阈值（0-100 口径，与视图硬编码 tushare=65 同量级）
    _QUALITY_REJECT_THRESHOLD = 60.0

    def _reject_low_quality_kline_enabled(self) -> bool:
        """R285 修复2：低质量 K 线落库拒绝开关（config data.reject_low_quality_kline）

        默认 False：保持"只记录不拦截"兼容行为（历史 import / HTTP 桥接链路不受影响）；
        开启后 store_standardized_data 对质量分 < _QUALITY_REJECT_THRESHOLD 的
        K 线批次直接拒绝落库（返回 False），从源头阻断坏数据入库。
        """
        try:
            from core.config import get_config_manager
            config_mgr = get_config_manager()
            data_cfg = config_mgr.get('data')
            if isinstance(data_cfg, dict):
                return bool(data_cfg.get('reject_low_quality_kline', False))
        except Exception:
            pass
        return False

    def _generate_table_name(self, data_type: DataType, asset_type: AssetType) -> str:
        """生成表名 - 新架构使用统一的表名"""
        # 新架构：所有资产类型使用统一的标准表名
        type_mapping = {
            DataType.HISTORICAL_KLINE: "historical_kline_data",  # 统一K线数据表
            DataType.REAL_TIME_QUOTE: "realtime_quotes",
            DataType.FUNDAMENTAL: "fundamentals",
            DataType.ASSET_LIST: "asset_metadata",  # 统一资产元数据表
            DataType.SECTOR_FUND_FLOW: "sector_fund_flow"
        }

        # 直接返回标准表名，不再添加asset_type前缀
        return type_mapping.get(data_type, data_type.value.lower())

    def _schema_cache_key(self, conn, table_name: str) -> str:
        """R287 P1-2：生成表结构/列元数据缓存的 key（db_path|table_name）"""
        db_path = getattr(conn, 'database_path', None)
        if db_path:
            return f"{db_path}|{table_name}"
        return f"conn_{id(conn)}|{table_name}"

    def _ensure_table_exists(self, conn, table_name: str, data: pd.DataFrame, data_type: DataType):
        """确保表存在，如果不存在则创建；如已存在则检查并迁移表结构

        R287 P1-2：会话级缓存（self._table_exists_cache）命中时直接返回，
        跳过 duckdb_tables() 存在性查询与 _migrate_table_schema 的 DESCRIBE。
        表结构在本类会话内独占维护（仅本类建表/迁移），缓存不失效。
        """
        try:
            # R287 P1-2：命中缓存直接跳过元数据查询
            cache_key = self._schema_cache_key(conn, table_name)
            if cache_key in self._table_exists_cache:
                logger.debug(f"[表结构-缓存] 命中 {table_name}，跳过 duckdb_tables/DESCRIBE")
                return

            # 检查表是否存在 - 使用duckdb_tables()更高效
            _q_start = time.perf_counter()
            table_exists = conn.execute(f"""
                SELECT COUNT(*) 
                FROM duckdb_tables() 
                WHERE table_name = '{table_name}'
            """).fetchone()[0] > 0
            _q_elapsed = (time.perf_counter() - _q_start) * 1000
            logger.debug(f"[表结构-DB] {table_name} 存在性查询耗时 {_q_elapsed:.1f}ms, exists={table_exists}")

            if not table_exists:
                # 根据数据类型创建表结构
                create_sql = self._generate_create_table_sql(table_name, data, data_type)
                conn.execute(create_sql)
                logger.info(f"创建表: {table_name}")

                # 创建索引
                self._create_table_indexes(conn, table_name, data_type)
                # 表新建，列集与最新结构一致 → 同步失效列缓存
                self._table_columns_cache.pop(cache_key, None)
            else:
                # 表已存在，检查并迁移表结构（添加缺失的复权字段）
                self._migrate_table_schema(conn, table_name)
                # 迁移可能增列 → 同步失效列缓存
                self._table_columns_cache.pop(cache_key, None)

            # 已确认存在且结构就绪
            self._table_exists_cache[cache_key] = True

        except Exception as e:
            logger.error(f"创建表 {table_name} 失败: {e}")
            raise

    def _migrate_table_schema(self, conn, table_name: str):
        """迁移表结构，添加缺失的复权字段"""
        try:
            # 获取当前表的所有列
            current_columns = conn.execute(f"DESCRIBE {table_name}").fetchall()
            column_names = {col[0] for col in current_columns}

            # 需要添加的复权字段
            migration_columns = {
                'adj_type': 'VARCHAR(10)',
                'adj_source': 'VARCHAR(20)'
            }

            # 检查并添加缺失的字段
            for column_name, column_type in migration_columns.items():
                if column_name not in column_names:
                    # 添加新列
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    conn.execute(alter_sql)
                    logger.info(f"[表结构迁移] {table_name} 添加字段: {column_name} {column_type}")

        except Exception as e:
            logger.warning(f"表结构迁移失败 {table_name}: {e}")

    # 修复：移除_ensure_views_exist方法
    # 视图在系统初始化时已经100%创建成功，运行时不需要检测
    # 如果需要在运行时创建视图，应该使用_initialize_database_schema方法

    def _generate_create_table_sql(self, table_name: str, data: pd.DataFrame, data_type: DataType) -> str:
        """生成创建表的SQL"""
        # 根据数据类型定义标准表结构
        if data_type == DataType.HISTORICAL_KLINE:
            # 新架构标准表结构：使用timestamp字段和(symbol, data_source, timestamp, frequency)主键
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
                    adj_type VARCHAR(10),    -- 复权类型 (qfq/hfq/none)
                    adj_source VARCHAR(20),  -- 复权数据来源 (plugin/calculated)
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

                # 性能优化：添加与ON CONFLICT完全匹配的复合索引
                # ON CONFLICT (symbol, data_source, timestamp, frequency) 需要对应的索引
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_conflict_key 
                    ON {table_name}(symbol, data_source, timestamp, frequency)
                """)
                logger.info(f"为{table_name}创建upsert优化索引")

                # 优化unified_best_quality_kline视图查询性能
                # 为常用查询条件添加索引：symbol + frequency, symbol + timestamp + frequency
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_frequency 
                    ON {table_name}(symbol, frequency)
                """)
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_timestamp_frequency 
                    ON {table_name}(symbol, timestamp, frequency)
                """)
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_frequency_timestamp 
                    ON {table_name}(frequency, timestamp)
                """)
                logger.info(f"为{table_name}创建视图查询优化索引（支持frequency）")

            elif data_type == DataType.REAL_TIME_QUOTE:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol ON {table_name}(symbol)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp)")
                # 添加ON CONFLICT匹配索引
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_conflict_key ON {table_name}(symbol, timestamp)")

            elif data_type == DataType.FUNDAMENTAL:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol ON {table_name}(symbol)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_market ON {table_name}(market)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_industry ON {table_name}(industry)")
            
            # 为数据质量监控表创建索引（优化unified_best_quality_kline视图性能）
            elif table_name == 'data_quality_monitor':
                # 完全匹配JOIN条件的复合索引（包含frequency）
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_data_source_check_date_frequency 
                    ON {table_name}(symbol, data_source, check_date, frequency)
                """)
                # 用于按股票和日期查询的索引（包含frequency）
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_check_date_frequency ON {table_name}(symbol, check_date, frequency)")
                # 用于按日期查询的索引（包含frequency）
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_check_date_frequency ON {table_name}(check_date, frequency)")
                # 保留旧索引以确保向后兼容
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_data_source_check_date 
                    ON {table_name}(symbol, data_source, check_date)
                """)
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_check_date ON {table_name}(symbol, check_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_check_date ON {table_name}(check_date)")
                logger.info(f"为{table_name}创建索引（优化视图JOIN性能，支持frequency）")
            
            # 为新增的股本/合约表创建索引
            elif table_name == 'stock_shares':
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_stock_code ON {table_name}(stock_code)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_update_date ON {table_name}(update_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_stock_code_update_date ON {table_name}(stock_code, update_date)")
                logger.info(f"为{table_name}创建索引")
            
            elif table_name == 'futures_contracts':
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_contract_code ON {table_name}(contract_code)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_underlying_asset ON {table_name}(underlying_asset)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_update_date ON {table_name}(update_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_contract_code_update_date ON {table_name}(contract_code, update_date)")
                logger.info(f"为{table_name}创建索引")
            
            elif table_name == 'option_contracts':
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_contract_code ON {table_name}(contract_code)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_underlying_asset ON {table_name}(underlying_asset)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_expiry_date ON {table_name}(expiry_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_update_date ON {table_name}(update_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_contract_code_update_date ON {table_name}(contract_code, update_date)")
                logger.info(f"为{table_name}创建索引")
            
            elif table_name == 'warrant_contracts':
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_warrant_code ON {table_name}(warrant_code)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_underlying_asset ON {table_name}(underlying_asset)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_expiry_date ON {table_name}(expiry_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_update_date ON {table_name}(update_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_warrant_code_update_date ON {table_name}(warrant_code, update_date)")
                logger.info(f"为{table_name}创建索引")
            
            elif table_name == 'crypto_supply':
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_crypto_code ON {table_name}(crypto_code)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_update_date ON {table_name}(update_date)")
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_crypto_code_update_date ON {table_name}(crypto_code, update_date)")
                logger.info(f"为{table_name}创建索引")
            
            # 其他数据类型的索引...
        except Exception as e:
            logger.warning(f"创建索引失败: {e}")

    def _get_table_columns(self, conn, table_name: str) -> list:
        """获取表的列名（R287 P1-2：会话级缓存，命中跳过 duckdb_columns() 查询）"""
        cache_key = self._schema_cache_key(conn, table_name)
        if cache_key in self._table_columns_cache:
            logger.debug(f"[列名-缓存] 命中 {table_name}，跳过 duckdb_columns() 查询")
            return self._table_columns_cache[cache_key]
        try:
            _q_start = time.perf_counter()
            result = conn.execute(f"""
                SELECT column_name 
                FROM duckdb_columns() 
                WHERE table_name = '{table_name}'
            """).fetchall()
            _q_elapsed = (time.perf_counter() - _q_start) * 1000
            columns = [row[0] for row in result]
            self._table_columns_cache[cache_key] = columns
            logger.debug(f"[列名-DB] {table_name} 查询耗时 {_q_elapsed:.1f}ms, {len(columns)} 列")
            return columns
        except Exception as e:
            logger.warning(f"获取表列名失败 {table_name}: {e}")
            return []

    def _filter_dataframe_columns(self, data: pd.DataFrame, table_columns: list) -> pd.DataFrame:
        """过滤DataFrame，只保留表中存在的列"""
        # 新架构：字段名映射（数据字段→表字段）
        field_mapping = {
            'datetime': 'timestamp',  # 关键映射：datetime字段映射到timestamp列
        }

        # 应用字段映射
        data_copy = data.copy()
        for data_field, table_field in field_mapping.items():
            if data_field in data_copy.columns and table_field in table_columns:
                if table_field in data_copy.columns:
                    # R290 防御：数据已同时携带 data_field 与 table_field 两列时，
                    # rename 会产生重复列 → DuckDB "Duplicate column name" 报错。
                    # 原逻辑直接删除源列保留目标列；R292 修复：若目标列为垃圾
                    # （可解析日期数量明显少于源列），反用源列覆盖目标列，避免把
                    # 损坏/伪造的 timestamp 写入数据库（日线日期集中的隐患之一）。
                    try:
                        _tf_valid = pd.to_datetime(
                            data_copy[table_field], errors='coerce').notna().sum()
                        _df_valid = pd.to_datetime(
                            data_copy[data_field], errors='coerce').notna().sum()
                    except Exception:
                        _tf_valid = _df_valid = 0
                    if _df_valid > _tf_valid:
                        logger.warning(
                            f"[字段映射] {table_field} 列有效日期({_tf_valid}条) 少于 "
                            f"{data_field}({_df_valid}条)，用 {data_field} 覆盖 {table_field}")
                        data_copy = data_copy.drop(columns=[table_field])
                        data_copy = data_copy.rename(columns={data_field: table_field})
                    else:
                        logger.debug(f"[字段映射] {data_field} 与 {table_field} 并存，删除冗余列 {data_field}")
                        data_copy = data_copy.drop(columns=[data_field])
                else:
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
            # 修复：减少日志输出，避免影响写入性能
            logger.debug(f"[数据插入] 准备插入数据到 {table_name}，数据类型: {data_type}, 记录数: {len(data)}")
            logger.debug(f"[数据插入] 输入列: {data.columns.tolist()}")

            # 检查输入数据中是否包含SQL关键字列名，自动移除
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
                # R292 清理：timestamp 已是 DuckDB K线表标准列名（datetime 会经字段
                # 映射转为 timestamp），此告警文案过时会误导，降为 debug 提示。
                logger.debug(f"[数据插入] 数据含 timestamp 列（标准列名，datetime 映射后正常落库）")

            # R287 P1-1：移除此处重复的数据质量验证。
            # store_standardized_data 在落库前已统一调用 _evaluate_and_record_quality
            # （内部含六维质量评估 + _validate_kline_data_quality OHLC 校验，结果写入
            # data_quality_monitor/monitor_latest）。同一批数据在 _upsert_data 内被
            # 再次做同款 OHLC 校验属重复计算（原链路同一批数据最多被评估 5 次）。
            # 移除后校验/记录行为不变（_evaluate_and_record_quality 仅对
            # HISTORICAL_KLINE 生效，与此处原条件范围一致）。

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

            # 优化：使用DuckDB批量INSERT（register方式），全部情况都使用，不使用executemany
            # 确保临时表名称唯一性（避免连接池中的名称冲突）
            temp_table = f"temp_insert_{int(time.time() * 1000000)}_{threading.get_ident()}"

            # 确保列顺序一致（不能使用SELECT *，必须明确指定列顺序）
            # 排除updated_at和created_at，因为这些字段在UPDATE子句中用NOW()设置
            columns = [col for col in filtered_data.columns if col not in ['updated_at', 'created_at']]

            # 修复：过滤SQL关键字和函数名，避免与SQL语法冲突
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

            # 修复：如果表中有updated_at列，需要在INSERT时也包含（但值从temp_table获取，如果没有则用DEFAULT）
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

            # 验证所有列名都在表列中
            invalid_columns = [col for col in insert_columns if col not in table_columns]
            if invalid_columns:
                logger.warning(f"[数据插入] 发现无效列名（不在表结构中）: {invalid_columns}，已自动移除")
                insert_columns = [col for col in insert_columns if col in table_columns]
                if not insert_columns:
                    logger.error(f"[数据插入] 移除无效列后没有有效列可插入，跳过插入")
                    return 0

            # 创建只包含安全列的 DataFrame，确保临时表结构与 SELECT 语句匹配
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

            # 构建insert_columns_str（排除updated_at和created_at，让数据库使用DEFAULT）
            # 使用双引号引用列名，确保DuckDB正确解析列名
            insert_columns_str = ', '.join(f'"{col}"' for col in insert_columns)

            # 调试日志
            logger.debug(f"[数据插入] 最终插入列: {insert_columns}, 列数: {len(insert_columns)}")
            logger.debug(f"[数据插入] safe_data行数: {len(safe_data)}")

            try:
                # 注册DataFrame为临时表（零拷贝，高性能）
                # 注册临时表
                conn.register(temp_table, safe_data)

                # 关键修复：使用更可靠的事务管理策略
                # 策略：始终使用显式事务，确保数据一致性
                # 不依赖不可靠的事务状态检测
                started_transaction = False
                
                try:
                    # 开始事务
                    conn.execute("BEGIN TRANSACTION")
                    started_transaction = True

                    # 构建批量UPSERT SQL（根据数据类型）
                    # 修复：使用 INSERT OR REPLACE 替代 ON CONFLICT DO UPDATE
                    # 避免 DuckDB ART 索引的唯一性检查过严问题（DELETE + INSERT 内部实现）
                    if data_type == DataType.HISTORICAL_KLINE:
                        # K线数据使用(symbol, data_source, timestamp, frequency)作为复合主键
                        # 使用 INSERT OR REPLACE 避免 ART 索引冲突
                        # 获取需要插入的字段（排除updated_at，使用数据库默认值）
                        insert_fields = [col for col in insert_columns if col not in ['updated_at', 'created_at']]
                        
                        sql = f"""
                            INSERT OR REPLACE INTO {table_name} ({', '.join(f'"{col}"' for col in insert_fields)})
                            SELECT {', '.join(f'"{col}"' for col in insert_fields)} FROM {temp_table}
                        """
                        logger.debug(f"[K线数据批量插入] 使用 INSERT OR REPLACE，插入列数: {len(insert_fields)}")

                    elif data_type == DataType.REAL_TIME_QUOTE:
                        # 实时行情使用symbol和timestamp作为唯一键
                        # 使用 INSERT OR REPLACE 避免 ART 索引冲突
                        insert_fields = [col for col in insert_columns if col not in ['updated_at', 'created_at']]
                        
                        sql = f"""
                            INSERT OR REPLACE INTO {table_name} ({', '.join(f'"{col}"' for col in insert_fields)})
                            SELECT {', '.join(f'"{col}"' for col in insert_fields)} FROM {temp_table}
                        """
                        logger.debug(f"[实时行情批量插入] 使用 INSERT OR REPLACE")

                    elif data_type == DataType.FUNDAMENTAL:
                        # 基本面数据使用symbol作为主键
                        # 使用 INSERT OR REPLACE 避免 ART 索引冲突
                        insert_fields = [col for col in insert_columns if col not in ['updated_at', 'updated_time', 'created_at']]
                        
                        sql = f"""
                            INSERT OR REPLACE INTO {table_name} ({', '.join(f'"{col}"' for col in insert_fields)})
                            SELECT {', '.join(f'"{col}"' for col in insert_fields)} FROM {temp_table}
                        """
                        logger.debug(f"[基本面数据批量插入] 使用 INSERT OR REPLACE")
                    else:
                        # 其他数据类型的处理：智能检测主键
                        # 尝试检测常见的主键字段，如果有则使用 INSERT OR REPLACE
                        possible_pk_fields = ['symbol', 'id', 'record_id', 'monitor_id', 'key']
                        pk_fields_in_data = [f for f in possible_pk_fields if f in insert_columns]

                        if pk_fields_in_data:
                            # 检测到主键字段，使用 INSERT OR REPLACE 避免 ART 索引冲突
                            insert_fields = [col for col in insert_columns if col not in ['updated_at', 'updated_time', 'created_at']]
                            
                            sql = f"""
                                INSERT OR REPLACE INTO {table_name} ({', '.join(f'"{col}"' for col in insert_fields)})
                                SELECT {', '.join(f'"{col}"' for col in insert_fields)} FROM {temp_table}
                            """
                            logger.debug(f"[其他数据类型批量插入] 使用 INSERT OR REPLACE")
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

                    # 提交事务
                    if started_transaction:
                        conn.execute("COMMIT")

                    # 记录性能日志
                    if write_duration > 1.0:
                        logger.warning(f"[批量插入] 写入较慢: {table_name}, {len(safe_data)}条记录, 耗时: {write_duration:.2f}秒, 速度: {write_speed:.1f}条/秒")
                    else:
                        logger.debug(f"[批量插入] 成功插入 {len(safe_data)} 条记录到 {table_name}, 耗时: {write_duration:.2f}秒, 速度: {write_speed:.1f}条/秒")

                    return len(safe_data)

                except Exception as e:
                    # 回滚事务（确保数据一致性）
                    if started_transaction:
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
                # 确保清理临时表（即使出错也要清理，避免连接池污染）
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

            with self.duckdb_manager.get_pool(db_path, pool_size=self.config.pool_size).get_connection() as conn:
                if 'asset_metadata' in self._table_schemas:
                    try:
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
                        try:
                            conn.execute(self._table_schemas['asset_metadata'])
                        except Exception:
                            pass

                import json

                if not metadata.get('name') or not metadata.get('market'):
                    logger.error(f"缺少必需字段: {symbol}")
                    return False

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

                try:
                    table_info = conn.execute("PRAGMA table_info(asset_metadata)").fetchall()
                    table_columns = [row[1] for row in table_info]
                except Exception as e:
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

                date_fields = {'listing_date', 'delisting_date', 'last_verified', 'created_at', 'updated_at'}
                important_fields = {'sector', 'industry', 'industry_code', 'listing_date',
                                   'total_shares', 'circulating_shares'}

                existing = conn.execute(
                    "SELECT * FROM asset_metadata WHERE symbol = ?",
                    [symbol]
                ).fetchone()

                if existing:
                    columns = [desc[0] for desc in conn.description]
                    existing_dict = dict(zip(columns, existing))
                    existing_sources_str = existing_dict.get('data_sources', '[]')

                    try:
                        existing_sources = json.loads(existing_sources_str) if existing_sources_str else []
                    except Exception:
                        existing_sources = []

                    new_source = metadata.get('primary_data_source')
                    if new_source and new_source not in existing_sources:
                        existing_sources.append(new_source)
                    metadata['data_sources'] = json.dumps(existing_sources, ensure_ascii=False)

                filtered_metadata = {}
                for k, v in metadata.items():
                    if k not in table_columns:
                        continue

                    if k in date_fields and v is not None:
                        if isinstance(v, int):
                            logger.warning(f"[upsert_asset_metadata] 字段'{k}'类型为INTEGER，跳过")
                            continue
                        elif isinstance(v, str):
                            import re
                            if not re.match(r'^\d{4}-\d{2}-\d{2}$', v.strip()):
                                logger.warning(f"[upsert_asset_metadata] 字段'{k}'日期格式不正确，跳过")
                                continue

                    if existing and k in important_fields:
                        if v is None or (isinstance(v, str) and not v.strip()):
                            continue

                    filtered_metadata[k] = v

                removed_keys = set(metadata.keys()) - set(filtered_metadata.keys())
                if removed_keys:
                    logger.debug(f"[upsert_asset_metadata] 过滤不存在的列: {removed_keys}")

                columns = list(filtered_metadata.keys())
                placeholders = ['?' for _ in columns]
                values = [filtered_metadata[col] for col in columns]

                update_parts = []
                for col in columns:
                    if col != 'symbol':
                        update_parts.append(f"{col} = EXCLUDED.{col}")

                if update_parts:
                    sql = f"""INSERT INTO asset_metadata ({', '.join(columns)})
                              VALUES ({', '.join(placeholders)})
                              ON CONFLICT (symbol) DO UPDATE SET {', '.join(update_parts)}"""
                else:
                    sql = f"""INSERT INTO asset_metadata ({', '.join(columns)})
                              VALUES ({', '.join(placeholders)})
                              ON CONFLICT (symbol) DO NOTHING"""

                conn.execute(sql, values)
                logger.info(f"Upsert资产元数据: {symbol} (ON CONFLICT DO)")

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
            with self.duckdb_manager.get_pool(db_path, pool_size=self.config.pool_size).get_connection() as conn:
                if 'asset_metadata' in self._table_schemas:
                    try:
                        table_exists = conn.execute("""
                            SELECT COUNT(*)
                            FROM information_schema.tables
                            WHERE table_name = 'asset_metadata'
                        """).fetchone()[0] > 0

                        if not table_exists:
                            logger.debug(f"asset_metadata表不存在，跳过查询")
                            return None
                    except Exception:
                        return None

                result = conn.execute(
                    "SELECT * FROM asset_metadata WHERE symbol = ?",
                    [symbol]
                ).fetchone()

                if result:
                    columns = [desc[0] for desc in conn.description]
                    metadata_dict = dict(zip(columns, result))

                    import json
                    for field in ['data_sources', 'tags', 'attributes']:
                        if field in metadata_dict and metadata_dict[field]:
                            try:
                                metadata_dict[field] = json.loads(metadata_dict[field])
                            except Exception:
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
            with self.duckdb_manager.get_pool(db_path, pool_size=self.config.pool_size).get_connection() as conn:
                if 'asset_metadata' in self._table_schemas:
                    try:
                        table_exists = conn.execute("""
                            SELECT COUNT(*)
                            FROM information_schema.tables
                            WHERE table_name = 'asset_metadata'
                        """).fetchone()[0] > 0

                        if not table_exists:
                            logger.debug(f"asset_metadata表不存在，返回空字典")
                            return {}
                    except Exception:
                        return {}

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
                            except Exception:
                                pass

                    result_dict[symbol] = metadata_dict

                return result_dict

        except Exception as e:
            logger.error(f"批量获取资产元数据失败: {e}")
            return {}

    def load_fundamental_data(self, symbol: str, asset_type: AssetType) -> Optional[Dict[str, Any]]:
        """从数据库加载基本面数据

        Args:
            symbol: 标的代码
            asset_type: 资产类型

        Returns:
            Dict[str, Any]: 基本面数据字典，如果不存在则返回None
        """
        try:
            db_path = self._get_database_path(asset_type)
            with self.duckdb_manager.get_pool(db_path, pool_size=self.config.pool_size).get_connection() as conn:
                if 'fundamentals' in self._table_schemas:
                    try:
                        table_exists = conn.execute("""
                            SELECT COUNT(*)
                            FROM information_schema.tables
                            WHERE table_name = 'fundamentals'
                        """).fetchone()[0] > 0

                        if not table_exists:
                            logger.debug(f"fundamentals表不存在，跳过查询")
                            return None
                    except Exception:
                        return None

                result = conn.execute(
                    "SELECT * FROM fundamentals WHERE symbol = ?",
                    [symbol]
                ).fetchone()

                if result:
                    columns = [desc[0] for desc in conn.description]
                    fundamental_dict = dict(zip(columns, result))

                    for field in ['attributes', 'tags']:
                        if field in fundamental_dict and fundamental_dict[field]:
                            try:
                                import json
                                fundamental_dict[field] = json.loads(fundamental_dict[field])
                            except Exception:
                                pass

                    logger.debug(f"从数据库加载基本面数据成功: {symbol}")
                    return fundamental_dict
                else:
                    logger.debug(f"数据库中未找到基本面数据: {symbol}")
                    return None

        except Exception as e:
            logger.error(f"从数据库加载基本面数据失败: {symbol}, {e}")
            return None

    def load_kline_data(self, symbol: str, asset_type: AssetType,
                        start_date=None, end_date=None,
                        frequency: Optional[str] = None) -> pd.DataFrame:
        """从数据库加载K线数据（DB优先架构：DuckDB有数据时直查，避免直调插件走网络）

        R254 修复：新增K线 DB 优先读方法，供 UniPluginDataManager 的 K 线 DB 优先分支使用。

        Args:
            symbol: 标的代码
            asset_type: 资产类型
            start_date: 开始日期（可选，datetime/date/str）
            end_date: 结束日期（可选）
            frequency: 频率（可选，DuckDB frequency 格式，如 '1d'/'5min'）

        Returns:
            pd.DataFrame: 查询结果（含 symbol/frequency/timestamp/open/high/low/close/volume 列，
            按 timestamp 升序），无数据或异常时返回空 DataFrame
        """
        try:
            db_path = self._get_database_path(asset_type)
            with self.duckdb_manager.get_pool(db_path, pool_size=self.config.pool_size).get_connection() as conn:
                # 表不存在则直接返回空（避免查询报错）
                try:
                    table_exists = conn.execute("""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = 'historical_kline_data'
                    """).fetchone()[0] > 0
                    if not table_exists:
                        logger.debug("historical_kline_data 表不存在，跳过查询")
                        return pd.DataFrame()
                except Exception:
                    return pd.DataFrame()

                conditions = ["symbol = ?"]
                params = [symbol]
                if frequency:
                    conditions.append("frequency = ?")
                    params.append(frequency)
                if start_date is not None:
                    conditions.append("timestamp >= ?")
                    params.append(pd.Timestamp(start_date))
                if end_date is not None:
                    conditions.append("timestamp <= ?")
                    params.append(pd.Timestamp(end_date))

                query = f"""
                    SELECT symbol, data_source, timestamp, frequency,
                           open, high, low, close, volume, amount,
                           adj_close, adj_factor
                    FROM historical_kline_data
                    WHERE {' AND '.join(conditions)}
                    ORDER BY timestamp ASC
                """
                result = conn.execute(query, params).fetchdf()

                if result is None or result.empty:
                    logger.debug(f"数据库中未找到K线数据: {symbol}, frequency={frequency}")
                    return pd.DataFrame()

                logger.debug(f"从数据库加载K线数据成功: {symbol}, 记录数={len(result)}")
                return result

        except Exception as e:
            logger.error(f"从数据库加载K线数据失败: {symbol}, {e}")
            return pd.DataFrame()

    def load_fundamental_data_batch(self, symbols: List[str], asset_type: AssetType) -> Dict[str, Dict[str, Any]]:
        """批量从数据库加载基本面数据

        Args:
            symbols: 标的代码列表
            asset_type: 资产类型

        Returns:
            Dict[symbol, Dict[str, Any]]: 基本面数据字典
        """
        try:
            if not symbols:
                return {}

            db_path = self._get_database_path(asset_type)
            with self.duckdb_manager.get_pool(db_path, pool_size=self.config.pool_size).get_connection() as conn:
                if 'fundamentals' in self._table_schemas:
                    try:
                        table_exists = conn.execute("""
                            SELECT COUNT(*)
                            FROM information_schema.tables
                            WHERE table_name = 'fundamentals'
                        """).fetchone()[0] > 0

                        if not table_exists:
                            logger.debug(f"fundamentals表不存在，返回空字典")
                            return {}
                    except Exception:
                        return {}

                placeholders = ','.join(['?' for _ in symbols])
                query = f"SELECT * FROM fundamentals WHERE symbol IN ({placeholders})"

                results = conn.execute(query, symbols).fetchall()
                columns = [desc[0] for desc in conn.description]

                import json
                result_dict = {}
                for row in results:
                    fundamental_dict = dict(zip(columns, row))
                    symbol = fundamental_dict['symbol']

                    for field in ['attributes', 'tags']:
                        if field in fundamental_dict and fundamental_dict[field]:
                            try:
                                fundamental_dict[field] = json.loads(fundamental_dict[field])
                            except Exception:
                                pass

                    result_dict[symbol] = fundamental_dict

                logger.info(f"批量加载基本面数据成功: {len(result_dict)}/{len(symbols)}")
                return result_dict

        except Exception as e:
            logger.error(f"批量加载基本面数据失败: {e}")
            return {}

    def close_all_connections(self):
        """关闭所有数据库连接 (R292-HVD-A: 收敛后池归全局单例管理)

        原实现调 self.duckdb_manager.close_all_pools() 关闭自持实例的池;
        收敛为 get_connection_manager() 模块级单例后, 此处若仍 close_all_pools
        会一次性关闭所有组件 (unified_data_manager / backtest_result_manager /
        enhanced_duckdb_data_downloader 等) 共享的池, 提前杀掉在用连接。
        连接池收尾统一由 main.py 注册的 cleanup_duckdb_manager
        (duckdb_manager.py:886) 在 graceful_shutdown LIFO 中执行, 本方法
        仅保留幂等安全语义, 不再关闭连接。
        """
        try:
            logger.debug("AssetSeparatedDatabaseManager: 连接池归全局单例管理, 关闭动作交由 cleanup_duckdb_manager 统一执行")

        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")

    # ========================================================================
    # R237 HVD-237-B-001: 4 链 dispose 治理 (R78 铁律)
    # 业务影响: 10+ 业务方 (DatabaseService, ImportExecutionEngine, EnhancedDuckDBDataDownloader,
    #          EastMoneyPlugin, AKSharePlugin, FreeStockDBPlugin, DataMissingManager 等)
    # 业务资源: DuckDB 连接池 + _asset_databases + _database_info + _table_schemas
    # ========================================================================
    def dispose(self) -> None:
        """R237 HVD-237-B-001: 4 链 dispose 入口 (R78 铁律 #6 幂等短路)"""
        # 幂等短路: 已 dispose 则直接返回 (R78 铁律 #6)
        if getattr(self, '_disposed', False):
            return
        try:
            # 4 链依次执行 (R236-B 模板)
            self.shutdown()
            self.close()
            self.cleanup()
        except Exception as e:
            # R117-HVD-69 P1 模板: 失败仅 warning + exc_info, 不抛错
            logger.warning(
                f"AssetSeparatedDatabaseManager.dispose 异常: {e}",
                exc_info=True,
            )
        finally:
            # 无论成败, 标记 _disposed = True (R78 铁律 #6)
            self._disposed = True

    def shutdown(self) -> None:
        """R237 HVD-237-B-001: shutdown - 业务数据清空 (R234 业务锁内清空)"""
        try:
            # 业务锁内清空 _asset_databases / _database_info (R234 强化经验)
            with self._db_lock:
                if hasattr(self, '_asset_databases') and self._asset_databases is not None:
                    self._asset_databases.clear()
                if hasattr(self, '_database_info') and self._database_info is not None:
                    self._database_info.clear()
        except Exception as e:
            logger.warning(
                f"AssetSeparatedDatabaseManager.shutdown 异常: {e}",
                exc_info=True,
            )

    def close(self) -> None:
        """R237 HVD-237-B-001: close - 子组件引用释放 + DuckDB 连接池关闭"""
        try:
            # 关闭所有 DuckDB 连接池
            self.close_all_connections()
            # 释放 duckdb_manager 引用
            if hasattr(self, 'duckdb_manager'):
                self.duckdb_manager = None
            # 释放 asset_identifier 引用
            if hasattr(self, 'asset_identifier'):
                self.asset_identifier = None
        except Exception as e:
            logger.warning(
                f"AssetSeparatedDatabaseManager.close 异常: {e}",
                exc_info=True,
            )

    def cleanup(self) -> None:
        """R237 HVD-237-B-001: cleanup - 资源引用置 None + 单例重置"""
        try:
            # 释放 _table_schemas 引用
            if hasattr(self, '_table_schemas'):
                self._table_schemas = None
            # 重置配置引用
            if hasattr(self, 'config'):
                self.config = None
            # 清理旧的 backup 资源 (R235 子智能体 B 已有 cleanup_old_backups)
            try:
                if hasattr(self, 'cleanup_old_backups'):
                    self.cleanup_old_backups(days_to_keep=0)
            except Exception:
                pass
        except Exception as e:
            logger.warning(
                f"AssetSeparatedDatabaseManager.cleanup 异常: {e}",
                exc_info=True,
            )


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
