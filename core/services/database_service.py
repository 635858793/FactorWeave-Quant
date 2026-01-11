"""
统一数据库服务 - 架构精简重构版本

整合所有数据库管理器功能，提供统一的数据库接口。
整合DuckDBConnectionManager、SQLiteExtensionManager、AssetSeparatedDatabaseManager等。
完全重构以符合15个核心服务的架构精简目标。
"""

import asyncio
import threading
import time
import contextlib
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union, Callable, Generator, Tuple
import sqlite3
import duckdb
import uuid
from collections import defaultdict

from loguru import logger

from .base_service import BaseService
from ..database.duckdb_manager import DuckDBConnectionManager
from ..database.duckdb_operations import DuckDBOperations
from ..database.sqlite_extensions import SQLiteExtensionManager
from ..database.duckdb_performance_optimizer import (
    DuckDBPerformanceOptimizer, WorkloadType, DuckDBConfig
)
from ..asset_database_manager import AssetSeparatedDatabaseManager
# from ..enhanced_asset_database_manager import EnhancedAssetDatabaseManager  # 已集成到DatabaseService
from ..database.factorweave_analytics_db import FactorWeaveAnalyticsDB
from ..events import EventBus, get_event_bus
from ..containers import ServiceContainer, get_service_container
# from ..plugin_types import AssetType  # 延迟导入，避免循环依赖
from .metrics_base import add_dict_interface


class DatabaseType(Enum):
    """数据库类型"""
    DUCKDB = "duckdb"
    SQLITE = "sqlite"


class ConnectionPoolType(Enum):
    """连接池类型"""
    SHARED = "shared"       # 共享连接池
    ISOLATED = "isolated"   # 隔离连接池
    TRANSACTIONAL = "transactional"  # 事务连接池


class TransactionIsolationLevel(Enum):
    """事务隔离级别"""
    READ_UNCOMMITTED = "READ_UNCOMMITTED"
    READ_COMMITTED = "READ_COMMITTED"
    REPEATABLE_READ = "REPEATABLE_READ"
    SERIALIZABLE = "SERIALIZABLE"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_type: DatabaseType
    db_path: str
    pool_size: int = 10
    max_pool_size: int = 50
    timeout: float = 30.0
    enable_wal: bool = True
    enable_optimization: bool = True
    memory_limit: str = "2GB"
    thread_count: int = 4
    checkpoint_threshold: int = 1000
    auto_vacuum: bool = True


@dataclass
class ConnectionMetrics:
    """连接指标"""
    active_connections: int = 0
    total_connections: int = 0
    peak_connections: int = 0
    connection_errors: int = 0
    avg_connection_time: float = 0.0
    last_connection_time: Optional[datetime] = None


@dataclass
class QueryMetrics:
    """查询指标"""
    query_id: str
    sql: str
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time: float = 0.0
    rows_affected: int = 0
    success: bool = False
    error: Optional[str] = None


@dataclass
class TransactionMetrics:
    """事务指标"""
    transaction_id: str
    start_time: datetime
    isolation_level: TransactionIsolationLevel
    end_time: Optional[datetime] = None
    operations_count: int = 0
    success: bool = False
    rollback_reason: Optional[str] = None


@add_dict_interface
@dataclass
class DatabaseMetrics:
    """数据库服务指标"""
    # 基础指标字段（与BaseService一致）
    initialization_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    operation_count: int = 0

    # 数据库特定字段
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    active_transactions: int = 0
    total_transactions: int = 0
    database_connections: int = 0
    last_update: datetime = field(default_factory=datetime.now)


class DatabaseConnection:
    """数据库连接包装器"""

    def __init__(self, connection: Any, db_type: DatabaseType, pool_name: str):
        self.connection = connection
        self.db_type = db_type
        self.pool_name = pool_name
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.query_count = 0
        self.is_active = True

    def execute(self, sql: str, parameters: Optional[Union[Dict[str, Any], List[Any], Tuple[Any, ...]]] = None) -> Any:
        """执行SQL"""
        self.last_used = datetime.now()
        self.query_count += 1

        try:
            sql_upper = sql.strip().upper()
            is_select = sql_upper.startswith('SELECT') or sql_upper.startswith('PRAGMA') or sql_upper.startswith('EXPLAIN')
            
            if self.db_type == DatabaseType.DUCKDB:
                if parameters is not None:
                    # DuckDB 支持位置参数（列表/元组）和命名参数（字典）
                    # 如果是列表，转换为元组以确保兼容性
                    if isinstance(parameters, list):
                        parameters = tuple(parameters)
                    result = self.connection.execute(sql, parameters)
                else:
                    result = self.connection.execute(sql)
                return result.fetchall() if is_select else None
            elif self.db_type == DatabaseType.SQLITE:
                cursor = self.connection.cursor()
                if parameters:
                    result = cursor.execute(sql, parameters)
                else:
                    result = cursor.execute(sql)
                return result.fetchall() if is_select else None
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def cursor(self):
        """获取数据库游标 - 代理方法以支持SQLite API兼容性"""
        if self.db_type == DatabaseType.SQLITE:
            # 对于SQLite，直接返回原生cursor
            return self.connection.cursor()
        elif self.db_type == DatabaseType.DUCKDB:
            # 对于DuckDB，返回包装的cursor对象以提供兼容的API
            return DuckDBCursorWrapper(self.connection)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def commit(self):
        """提交事务"""
        try:
            if self.db_type == DatabaseType.SQLITE:
                self.connection.commit()
            elif self.db_type == DatabaseType.DUCKDB:
                # DuckDB自动提交，但为了兼容性保留此方法
                pass
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            raise

    def rollback(self):
        """回滚事务"""
        try:
            if self.db_type == DatabaseType.SQLITE:
                self.connection.rollback()
            elif self.db_type == DatabaseType.DUCKDB:
                # DuckDB不支持显式回滚
                pass
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise

    def close(self):
        """关闭连接"""
        try:
            if self.connection and self.is_active:
                self.connection.close()
                self.is_active = False
        except Exception as e:
            logger.error(f"Error closing connection: {e}")


class DuckDBCursorWrapper:
    """DuckDB游标包装器，提供SQLite兼容的API"""

    def __init__(self, connection: Any):
        self.connection = connection

    def execute(self, sql: str, parameters: Optional[Tuple] = None):
        """执行SQL查询"""
        try:
            if parameters:
                return self.connection.execute(sql, parameters)
            else:
                return self.connection.execute(sql)
        except Exception as e:
            logger.error(f"DuckDB execute failed: {e}")
            raise

    def fetchall(self):
        """获取所有结果"""
        # DuckDB的execute()已经返回结果，这里直接返回
        return []

    def fetchone(self):
        """获取单个结果"""
        return None

    def commit(self):
        """提交事务（DuckDB自动提交）"""
        pass

    def close(self):
        """关闭游标（无操作）"""
        pass


class DatabaseService(BaseService):
    """
    统一数据库服务 - 架构精简重构版本

    整合所有数据库管理器功能：
    - DuckDBConnectionManager: DuckDB连接管理
    - SQLiteExtensionManager: SQLite扩展管理
    - AssetSeparatedDatabaseManager: 资产分离数据库
    - EnhancedAssetDatabaseManager: 增强资产数据库
    - FactorWeaveAnalyticsDB: 分析数据库
    - OptimizationDatabaseManager: 优化数据库
    - StrategyDatabaseManager: 策略数据库

    提供统一的数据库访问接口，支持：
    1. 多数据库类型支持（DuckDB、SQLite）
    2. 智能连接池管理
    3. 事务管理和隔离级别控制
    4. 查询优化和性能监控
    5. 资产数据分离存储
    6. 分析和策略数据管理
    7. 自动备份和恢复
    8. 并发控制和资源管理
    """

    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """
        初始化数据库服务

        Args:
            service_container: 服务容器
        """
        super().__init__()
        self.service_name = "DatabaseService"

        # 依赖注入
        self._service_container = service_container or get_service_container()

        # 核心组件
        self._duckdb_manager: Optional[DuckDBConnectionManager] = None
        self._duckdb_operations: Optional[DuckDBOperations] = None
        self._sqlite_manager: Optional[SQLiteExtensionManager] = None
        self._asset_db_manager: Optional[AssetSeparatedDatabaseManager] = None
        # self._enhanced_asset_manager: Optional[EnhancedAssetDatabaseManager] = None  # 已集成
        self._analytics_db: Optional[FactorWeaveAnalyticsDB] = None

        # 连接池管理
        self._connection_pools: Dict[str, List[DatabaseConnection]] = {}
        self._pool_configs: Dict[str, DatabaseConfig] = {}
        self._pool_metrics: Dict[str, ConnectionMetrics] = {}
        self._pool_locks: Dict[str, threading.RLock] = {}

        # 性能优化器
        self._performance_optimizers: Dict[str, DuckDBPerformanceOptimizer] = {}

        # 事务管理
        self._active_transactions: Dict[str, TransactionMetrics] = {}
        self._transaction_connections: Dict[str, DatabaseConnection] = {}
        self._transaction_counter = 0
        self._transaction_lock = threading.RLock()

        # 查询缓存和指标
        self._query_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._query_metrics: Dict[str, QueryMetrics] = {}
        self._query_counter = 0
        self._query_lock = threading.RLock()

        # 服务指标
        self._metrics = DatabaseMetrics()
        self._service_lock = threading.RLock()

        # 配置参数（v2.4性能优化：增加连接池大小）
        self._config = {
            "default_pool_size": 20,  # 从10增加到20
            "max_pool_size": 100,     # 从50增加到100
            "connection_timeout": 30.0,
            "query_timeout": 60.0,
            "transaction_timeout": 300.0,
            "enable_query_cache": True,
            "cache_ttl": 300,  # 5分钟
            "enable_performance_monitoring": True,
            "enable_auto_optimization": True,
            "checkpoint_interval": 300,  # 5分钟
            "backup_interval": 3600  # 1小时
        }

        # 默认数据库配置
        self._default_db_configs = {
            "analytics_duckdb": DatabaseConfig(
                db_type=DatabaseType.DUCKDB,
                db_path="data/factorweave_analytics.duckdb",
                pool_size=15,      # 从5增加到15
                max_pool_size=40   # 从20增加到40
            ),
            "strategy_sqlite": DatabaseConfig(
                db_type=DatabaseType.SQLITE,
                db_path="data/strategy.sqlite",
                pool_size=10,      # 从5增加到10
                max_pool_size=30   # 从15增加到30
            ),
            "tradeaccount_sqlite": DatabaseConfig(
                db_type=DatabaseType.SQLITE,
                db_path="data/tradeaccount.sqlite",
                pool_size=10,
                max_pool_size=30
            )
        }

        # 订单数据库配置（多资产支持）
        self._order_db_configs = {}
        # 延迟导入AssetType，避免循环依赖
        try:
            from core.plugin_types import AssetType
            for asset_type in AssetType:
                pool_name = f"{asset_type.value.lower()}_orders"
                db_path = f"data/databases/{asset_type.value.lower()}/{pool_name}.duckdb"
                self._order_db_configs[pool_name] = DatabaseConfig(
                    db_type=DatabaseType.DUCKDB,
                    db_path=db_path,
                    pool_size=5,
                    max_pool_size=15
                )
        except Exception as e:
            logger.warning(f"初始化订单数据库配置失败: {e}")

        # 监控和统计
        self._start_time = datetime.now()
        self._last_checkpoint = datetime.now()
        self._last_backup = datetime.now()

        logger.info("DatabaseService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing DatabaseService core components...")

            # 1. 初始化DuckDB管理器
            self._initialize_duckdb_managers()

            # 2. 初始化SQLite管理器
            self._initialize_sqlite_managers()

            # 3. 初始化资产数据库管理器
            self._initialize_asset_managers()

            # 4. 创建默认连接池（必须在其他初始化之前）
            self._create_default_pools()

            # 5. 初始化分析数据库
            self._initialize_analytics_db()

            # 6. 初始化AI选股相关数据表
            self._initialize_ai_tables()
            
            # 7. 初始化策略配置相关数据表
            self._initialize_strategy_tables()

            # 8. 初始化交易账户相关数据表
            self._initialize_trade_account_tables()

            # 9. 初始化性能优化器
            self._initialize_performance_optimizers()

            # 10. 启动后台任务
            self._start_background_tasks()

            # 11. 验证数据库连接
            self._validate_database_connections()

            logger.info("✅ DatabaseService initialized successfully with full database management capabilities")

        except Exception as e:
            logger.error(f"❌ Failed to initialize DatabaseService: {e}")
            raise

    def _initialize_duckdb_managers(self) -> None:
        """初始化DuckDB管理器"""
        try:
            # 创建DuckDB连接管理器
            self._duckdb_manager = DuckDBConnectionManager()

            # 创建DuckDB操作器
            self._duckdb_operations = DuckDBOperations()

            logger.info("✓ DuckDB managers initialized")

        except Exception as e:
            logger.error(f"Failed to initialize DuckDB managers: {e}")
            raise

    def _initialize_sqlite_managers(self) -> None:
        """初始化SQLite管理器"""
        try:
            # 创建SQLite扩展管理器
            self._sqlite_manager = SQLiteExtensionManager()

            logger.info("✓ SQLite managers initialized")

        except Exception as e:
            logger.error(f"Failed to initialize SQLite managers: {e}")
            raise

    def _initialize_asset_managers(self) -> None:
        """初始化资产数据库管理器"""
        try:
            # 创建资产分离数据库管理器
            if hasattr(AssetSeparatedDatabaseManager, '__init__'):
                self._asset_db_manager = AssetSeparatedDatabaseManager()

            # 增强资产数据库管理器功能已集成到DatabaseService

            # (原EnhancedAssetDatabaseManager已合并)

            logger.info("✓ Asset database managers initialized")

        except Exception as e:
            logger.warning(f"Some asset managers could not be initialized: {e}")

    def _initialize_analytics_db(self) -> None:
        """初始化分析数据库"""
        try:
            # 创建FactorWeave分析数据库
            self._analytics_db = FactorWeaveAnalyticsDB()

            logger.info("✓ Analytics database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize analytics database: {e}")
            raise

    def _create_default_pools(self) -> None:
        """创建默认连接池"""
        try:
            for pool_name, config in self._default_db_configs.items():
                self.create_connection_pool(pool_name, config)

            logger.info(f"✓ Created {len(self._default_db_configs)} default connection pools")

            # 创建订单数据库连接池
            for pool_name, config in self._order_db_configs.items():
                try:
                    self.create_connection_pool(pool_name, config)
                except Exception as e:
                    logger.warning(f"Failed to create order database pool {pool_name}: {e}")

            logger.info(f"✓ Created {len(self._order_db_configs)} order database connection pools")

            # 初始化订单数据库表和索引
            self._initialize_order_databases()

        except Exception as e:
            logger.error(f"Failed to create default pools: {e}")
            raise

    def _initialize_order_databases(self) -> None:
        """初始化订单数据库表和索引"""
        try:
            logger.info("Initializing order database tables and indexes...")

            for pool_name in self._order_db_configs.keys():
                try:
                    # 创建订单表
                    self._create_orders_table(pool_name)
                    
                    # 创建订单成交记录表
                    self._create_order_fills_table(pool_name)
                    
                    logger.debug(f"✓ Initialized order database: {pool_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize order database {pool_name}: {e}")

            logger.info(f"✓ Order database tables and indexes initialized for {len(self._order_db_configs)} databases")

        except Exception as e:
            logger.error(f"Failed to initialize order databases: {e}")
            raise

    def _initialize_performance_optimizers(self) -> None:
        """初始化性能优化器（临时禁用 - v2.2架构修复）"""
        try:
            # TODO v2.2: 重新设计optimizer架构
            # DuckDBPerformanceOptimizer需要db_path参数，不是config对象
            # 当前optimizer在FactorWeaveAnalyticsDB中已经使用
            # 这里暂时跳过创建，避免参数错误

            logger.info(f"✓ Performance optimizers initialization skipped (architecture refactoring)")
            # 注释掉原有的错误代码
            # for pool_name, config in self._pool_configs.items():
            #     if config.db_type == DatabaseType.DUCKDB and config.enable_optimization:
            #         try:
            #             optimizer_config = DuckDBConfig(
            #                 memory_limit=config.memory_limit,
            #                 threads=config.thread_count
            #             )
            #             self._performance_optimizers[pool_name] = DuckDBPerformanceOptimizer(optimizer_config)
            #         except Exception as e:
            #             logger.warning(f"Failed to create optimizer for pool {pool_name}: {e}")

            # logger.info(f"✓ Created {len(self._performance_optimizers)} performance optimizers")

        except Exception as e:
            logger.error(f"Failed to initialize performance optimizers: {e}")

    def _start_background_tasks(self) -> None:
        """启动后台任务"""
        try:
            # 启动检查点任务
            if hasattr(self, '_data_executor'):
                self._data_executor.submit(self._checkpoint_loop)

                # 启动备份任务
                self._data_executor.submit(self._backup_loop)

                # 启动连接池维护任务
                self._data_executor.submit(self._pool_maintenance_loop)

            logger.info("✓ Background tasks started")

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    def _validate_database_connections(self) -> None:
        """验证数据库连接"""
        try:
            total_pools = len(self._connection_pools)
            healthy_pools = 0

            for pool_name in self._connection_pools.keys():
                try:
                    # 测试连接
                    with self.get_connection(pool_name) as conn:
                        if conn.db_type == DatabaseType.DUCKDB:
                            conn.execute("SELECT 1")
                        elif conn.db_type == DatabaseType.SQLITE:
                            conn.execute("SELECT 1")
                    healthy_pools += 1

                except Exception as e:
                    logger.warning(f"Pool {pool_name} connection test failed: {e}")

            if healthy_pools == 0:
                raise Exception("No healthy database connections found")

            logger.info(f"✓ Database connection validation: {healthy_pools}/{total_pools} pools healthy")

        except Exception as e:
            logger.error(f"Database connection validation failed: {e}")
            raise

    def create_connection_pool(self, pool_name: str, config: DatabaseConfig) -> None:
        """
        创建连接池

        Args:
            pool_name: 连接池名称
            config: 数据库配置
        """
        try:
            with self._service_lock:
                if pool_name in self._connection_pools:
                    logger.warning(f"Connection pool {pool_name} already exists")
                    return

                # 创建连接池
                self._connection_pools[pool_name] = []
                self._pool_configs[pool_name] = config
                self._pool_metrics[pool_name] = ConnectionMetrics()
                self._pool_locks[pool_name] = threading.RLock()

                # 创建初始连接
                self._populate_pool(pool_name, config.pool_size)

                logger.info(f"✓ Created connection pool {pool_name} with {config.pool_size} connections")

        except Exception as e:
            logger.error(f"Failed to create connection pool {pool_name}: {e}")
            raise

    def _populate_pool(self, pool_name: str, target_size: int) -> None:
        """填充连接池"""
        config = self._pool_configs[pool_name]

        while len(self._connection_pools[pool_name]) < target_size:
            try:
                connection = self._create_connection(config)
                db_conn = DatabaseConnection(connection, config.db_type, pool_name)
                self._connection_pools[pool_name].append(db_conn)

            except Exception as e:
                logger.error(f"Failed to create connection for pool {pool_name}: {e}")
                break

    def _create_connection(self, config: DatabaseConfig) -> Any:
        """创建数据库连接"""
        try:
            if config.db_type == DatabaseType.DUCKDB:
                # 确保目录存在
                db_path = Path(config.db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)

                # 创建DuckDB连接
                connection = duckdb.connect(str(db_path))

                # 应用配置
                connection.execute(f"SET memory_limit='{config.memory_limit}'")
                connection.execute(f"SET threads={config.thread_count}")

                if config.enable_wal:
                    try:
                        connection.execute("PRAGMA journal_mode=WAL")
                    except:
                        pass  # DuckDB可能不支持WAL

                return connection

            elif config.db_type == DatabaseType.SQLITE:
                # 确保目录存在
                db_path = Path(config.db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)

                # 创建SQLite连接
                connection = sqlite3.connect(
                    str(db_path),
                    timeout=config.timeout,
                    check_same_thread=False,
                    autocommit=True
                )

                # 应用配置
                if config.enable_wal:
                    connection.execute("PRAGMA journal_mode=WAL")

                if config.auto_vacuum:
                    connection.execute("PRAGMA auto_vacuum=INCREMENTAL")

                connection.execute(f"PRAGMA synchronous=NORMAL")
                connection.execute(f"PRAGMA cache_size=10000")

                return connection

            else:
                raise ValueError(f"Unsupported database type: {config.db_type}")

        except Exception as e:
            logger.error(f"Failed to create {config.db_type} connection: {e}")
            raise

    @contextmanager
    def get_connection(self, pool_name: str = "analytics_duckdb") -> Generator[DatabaseConnection, None, None]:
        """
        获取数据库连接（上下文管理器）

        Args:
            pool_name: 连接池名称，可选值：
                - "analytics_duckdb": 分析数据库（默认）
                - "strategy_sqlite": 策略数据库

        Note:
            - 资产数据（K线等）请使用 AssetSeparatedDatabaseManager
            - 配置数据请使用 ConfigService

        Args:
            pool_name: 连接池名称

        Yields:
            数据库连接
        """
        connection = None
        try:
            connection = self._get_connection_from_pool(pool_name)
            yield connection

        except Exception as e:
            logger.error(f"Error using connection from pool {pool_name}: {e}")
            raise

        finally:
            if connection:
                self._return_connection_to_pool(pool_name, connection)

    def _get_connection_from_pool(self, pool_name: str) -> DatabaseConnection:
        """从连接池获取连接"""
        if pool_name not in self._connection_pools:
            available_pools = list(self._connection_pools.keys())
            raise ValueError(
                f"连接池 '{pool_name}' 不存在。"
                f"可用的连接池: {available_pools}"
            )

        pool_lock = self._pool_locks[pool_name]

        with pool_lock:
            pool = self._connection_pools[pool_name]
            metrics = self._pool_metrics[pool_name]

            # 查找可用连接
            for connection in pool:
                if connection.is_active:
                    metrics.active_connections += 1
                    metrics.last_connection_time = datetime.now()
                    return connection

            # 如果没有可用连接，尝试创建新连接
            config = self._pool_configs[pool_name]
            if len(pool) < config.max_pool_size:
                try:
                    raw_connection = self._create_connection(config)
                    db_connection = DatabaseConnection(raw_connection, config.db_type, pool_name)
                    pool.append(db_connection)

                    metrics.active_connections += 1
                    metrics.total_connections += 1
                    metrics.peak_connections = max(metrics.peak_connections, metrics.active_connections)
                    metrics.last_connection_time = datetime.now()

                    return db_connection

                except Exception as e:
                    metrics.connection_errors += 1
                    logger.error(f"Failed to create new connection for pool {pool_name}: {e}")
                    raise

            raise Exception(f"No available connections in pool {pool_name} and max pool size reached")

    def _return_connection_to_pool(self, pool_name: str, connection: DatabaseConnection) -> None:
        """归还连接到连接池"""
        if pool_name not in self._pool_metrics:
            return

        pool_lock = self._pool_locks[pool_name]

        with pool_lock:
            metrics = self._pool_metrics[pool_name]
            metrics.active_connections = max(0, metrics.active_connections - 1)

    def execute_query(self, sql: str, parameters: Optional[Dict[str, Any]] = None,
                      pool_name: str = "analytics_duckdb") -> Any:
        """
        执行查询

        Args:
            sql: SQL查询语句
            parameters: 查询参数
            pool_name: 连接池名称（默认："analytics_duckdb"）

        Args:
            sql: SQL语句
            parameters: 查询参数
            pool_name: 连接池名称

        Returns:
            查询结果
        """
        query_id = str(uuid.uuid4())
        start_time = datetime.now()

        try:
            with self._query_lock:
                self._metrics.total_queries += 1
                self._query_counter += 1

            # 检查查询缓存
            if self._config["enable_query_cache"]:
                cache_key = self._generate_query_cache_key(sql, parameters)
                cached_result = self._get_from_query_cache(cache_key)
                if cached_result is not None:
                    return cached_result

            # 执行查询
            with self.get_connection(pool_name) as conn:
                result = conn.execute(sql, parameters)

                # 更新缓存
                if self._config["enable_query_cache"]:
                    self._update_query_cache(cache_key, result)

                # 记录指标
                execution_time = (datetime.now() - start_time).total_seconds()
                query_metrics = QueryMetrics(
                    query_id=query_id,
                    sql=sql,
                    start_time=start_time,
                    end_time=datetime.now(),
                    execution_time=execution_time,
                    rows_affected=len(result) if result else 0,
                    success=True
                )

                with self._query_lock:
                    self._query_metrics[query_id] = query_metrics
                    self._metrics.successful_queries += 1

                    # 更新平均查询时间
                    total_time = (self._metrics.avg_query_time * (self._metrics.successful_queries - 1) +
                                  execution_time)
                    self._metrics.avg_query_time = total_time / self._metrics.successful_queries

                return result

        except Exception as e:
            # 记录错误
            execution_time = (datetime.now() - start_time).total_seconds()
            query_metrics = QueryMetrics(
                query_id=query_id,
                sql=sql,
                start_time=start_time,
                end_time=datetime.now(),
                execution_time=execution_time,
                success=False,
                error=str(e)
            )

            with self._query_lock:
                self._query_metrics[query_id] = query_metrics
                self._metrics.failed_queries += 1

            logger.error(f"Query execution failed: {e}")
            raise

    def fetch_all(self, sql: str, parameters: Optional[Dict[str, Any]] = None,
                  pool_name: str = "analytics_duckdb") -> List[Dict[str, Any]]:
        """
        执行查询并返回所有结果

        Args:
            sql: SQL查询语句
            parameters: 查询参数
            pool_name: 连接池名称（默认："analytics_duckdb"）

        Returns:
            查询结果列表
        """
        result = self.execute_query(sql, parameters, pool_name)
        
        # 如果结果已经是列表，直接返回
        if isinstance(result, list):
            return result
        
        # 如果结果是DuckDB的ArrowTable或类似对象，转换为列表
        try:
            if hasattr(result, 'to_pydict'):
                # DuckDB ArrowTable
                data = result.to_pydict()
                return [dict(zip(data.keys(), row)) for row in zip(*data.values())]
            elif hasattr(result, 'fetchall'):
                # 游标对象
                return result.fetchall()
            else:
                # 其他情况，尝试转换为列表
                return list(result)
        except Exception as e:
            logger.error(f"Failed to convert query result: {e}")
            return []

    def fetch_one(self, sql: str, parameters: Optional[Dict[str, Any]] = None,
                  pool_name: str = "analytics_duckdb") -> Optional[Dict[str, Any]]:
        """
        执行查询并返回单个结果

        Args:
            sql: SQL查询语句
            parameters: 查询参数
            pool_name: 连接池名称（默认："analytics_duckdb"）

        Returns:
            查询结果字典，如果没有结果则返回None
        """
        results = self.fetch_all(sql, parameters, pool_name)
        return results[0] if results else None

    @contextmanager
    def begin_transaction(self, pool_name: str = "analytics_duckdb",
                          isolation_level: TransactionIsolationLevel = TransactionIsolationLevel.READ_COMMITTED) -> Generator[str, None, None]:
        """
        开始事务（上下文管理器）

        Args:
            pool_name: 连接池名称（默认："analytics_duckdb"）
            isolation_level: 事务隔离级别

        Yields:
            事务ID
        """
        transaction_id = str(uuid.uuid4())
        connection = None

        try:
            with self._transaction_lock:
                self._transaction_counter += 1
                self._metrics.active_transactions += 1
                self._metrics.total_transactions += 1

            # 获取事务连接
            connection = self._get_connection_from_pool(pool_name)
            self._transaction_connections[transaction_id] = connection

            # 开始事务
            if connection.db_type == DatabaseType.DUCKDB:
                connection.execute("BEGIN TRANSACTION")
            elif connection.db_type == DatabaseType.SQLITE:
                connection.execute("BEGIN")

            # 记录事务指标
            transaction_metrics = TransactionMetrics(
                transaction_id=transaction_id,
                start_time=datetime.now(),
                isolation_level=isolation_level
            )

            with self._transaction_lock:
                self._active_transactions[transaction_id] = transaction_metrics

            yield transaction_id

            # 提交事务
            if connection.db_type == DatabaseType.DUCKDB:
                connection.execute("COMMIT")
            elif connection.db_type == DatabaseType.SQLITE:
                connection.connection.commit()

            # 更新事务指标
            transaction_metrics.end_time = datetime.now()
            transaction_metrics.success = True

        except Exception as e:
            # 回滚事务
            if connection:
                try:
                    if connection.db_type == DatabaseType.DUCKDB:
                        connection.execute("ROLLBACK")
                    elif connection.db_type == DatabaseType.SQLITE:
                        connection.connection.rollback()
                except:
                    pass

            # 更新事务指标
            if transaction_id in self._active_transactions:
                transaction_metrics = self._active_transactions[transaction_id]
                transaction_metrics.end_time = datetime.now()
                transaction_metrics.success = False
                transaction_metrics.rollback_reason = str(e)

            logger.error(f"Transaction {transaction_id} failed: {e}")
            raise

        finally:
            # 清理事务资源
            with self._transaction_lock:
                if transaction_id in self._active_transactions:
                    del self._active_transactions[transaction_id]
                if transaction_id in self._transaction_connections:
                    self._return_connection_to_pool(pool_name, self._transaction_connections[transaction_id])
                    del self._transaction_connections[transaction_id]

                self._metrics.active_transactions = max(0, self._metrics.active_transactions - 1)

    def execute_in_transaction(self, transaction_id: str, sql: str,
                               parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        在事务中执行查询

        Args:
            transaction_id: 事务ID
            sql: SQL语句
            parameters: 查询参数

        Returns:
            查询结果
        """
        if transaction_id not in self._transaction_connections:
            raise ValueError(f"Transaction {transaction_id} not found")

        connection = self._transaction_connections[transaction_id]

        try:
            result = connection.execute(sql, parameters)

            # 更新事务操作计数
            if transaction_id in self._active_transactions:
                self._active_transactions[transaction_id].operations_count += 1

            return result

        except Exception as e:
            logger.error(f"Query in transaction {transaction_id} failed: {e}")
            raise

    def _generate_query_cache_key(self, sql: str, parameters: Optional[Dict[str, Any]]) -> str:
        """生成查询缓存键"""
        import hashlib

        key_data = sql
        if parameters:
            param_str = str(sorted(parameters.items()))
            key_data += param_str

        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_from_query_cache(self, cache_key: str) -> Optional[Any]:
        """从查询缓存获取结果"""
        if cache_key in self._query_cache:
            result, timestamp = self._query_cache[cache_key]

            # 检查TTL
            if (datetime.now() - timestamp).total_seconds() < self._config["cache_ttl"]:
                return result
            else:
                # 清理过期缓存
                del self._query_cache[cache_key]

        return None

    def _update_query_cache(self, cache_key: str, result: Any) -> None:
        """更新查询缓存"""
        self._query_cache[cache_key] = (result, datetime.now())

        # 限制缓存大小
        if len(self._query_cache) > 1000:
            # 删除最旧的缓存项
            oldest_key = min(self._query_cache.keys(),
                             key=lambda k: self._query_cache[k][1])
            del self._query_cache[oldest_key]

    def _checkpoint_loop(self) -> None:
        """检查点循环"""
        while not self._shutdown_event.is_set():
            try:
                self._perform_checkpoint()
                self._shutdown_event.wait(self._config["checkpoint_interval"])
            except Exception as e:
                logger.error(f"Error in checkpoint loop: {e}")
                self._shutdown_event.wait(60)

    def _backup_loop(self) -> None:
        """备份循环"""
        while not self._shutdown_event.is_set():
            try:
                self._perform_backup()
                self._shutdown_event.wait(self._config["backup_interval"])
            except Exception as e:
                logger.error(f"Error in backup loop: {e}")
                self._shutdown_event.wait(300)

    def _pool_maintenance_loop(self) -> None:
        """连接池维护循环"""
        while not self._shutdown_event.is_set():
            try:
                self._maintain_connection_pools()
                self._shutdown_event.wait(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"Error in pool maintenance loop: {e}")
                self._shutdown_event.wait(60)

    def _perform_checkpoint(self) -> None:
        """执行检查点"""
        try:
            for pool_name, config in self._pool_configs.items():
                if config.db_type == DatabaseType.SQLITE:
                    try:
                        with self.get_connection(pool_name) as conn:
                            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

                    except Exception as e:
                        logger.warning(f"Checkpoint failed for pool {pool_name}: {e}")

            self._last_checkpoint = datetime.now()

        except Exception as e:
            logger.error(f"Checkpoint operation failed: {e}")

    def _perform_backup(self) -> None:
        """执行备份"""
        try:
            backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir.mkdir(parents=True, exist_ok=True)

            for pool_name, config in self._pool_configs.items():
                try:
                    source_path = Path(config.db_path)
                    backup_path = backup_dir / f"{pool_name}_{source_path.name}"

                    if source_path.exists():
                        import shutil
                        shutil.copy2(source_path, backup_path)
                        logger.info(f"Backed up {pool_name} to {backup_path}")

                except Exception as e:
                    logger.warning(f"Backup failed for pool {pool_name}: {e}")

            self._last_backup = datetime.now()

        except Exception as e:
            logger.error(f"Backup operation failed: {e}")

    def _maintain_connection_pools(self) -> None:
        """维护连接池"""
        try:
            for pool_name, pool in self._connection_pools.items():
                pool_lock = self._pool_locks[pool_name]

                with pool_lock:
                    # 清理无效连接
                    valid_connections = []
                    for conn in pool:
                        if conn.is_active:
                            # 检查连接是否仍然有效
                            try:
                                if conn.db_type == DatabaseType.DUCKDB:
                                    conn.execute("SELECT 1")
                                elif conn.db_type == DatabaseType.SQLITE:
                                    conn.execute("SELECT 1")
                                valid_connections.append(conn)
                            except:
                                conn.close()

                    self._connection_pools[pool_name] = valid_connections

                    # 如果连接数不足，补充新连接
                    config = self._pool_configs[pool_name]
                    target_size = min(config.pool_size, len(valid_connections) + 5)
                    self._populate_pool(pool_name, target_size)

        except Exception as e:
            logger.error(f"Pool maintenance failed: {e}")

    def get_database_metrics(self) -> DatabaseMetrics:
        """获取数据库服务指标"""
        with self._service_lock:
            self._metrics.last_update = datetime.now()
            self._metrics.database_connections = sum(len(pool) for pool in self._connection_pools.values())
            return self._metrics

    def get_pool_metrics(self, pool_name: str) -> Optional[ConnectionMetrics]:
        """获取连接池指标"""
        return self._pool_metrics.get(pool_name)

    def get_query_history(self, limit: int = 100) -> List[QueryMetrics]:
        """获取查询历史"""
        with self._query_lock:
            sorted_queries = sorted(
                self._query_metrics.values(),
                key=lambda q: q.start_time,
                reverse=True
            )
            return sorted_queries[:limit]

    def clear_query_cache(self) -> int:
        """清理查询缓存"""
        cleared_count = len(self._query_cache)
        self._query_cache.clear()
        logger.info(f"Cleared {cleared_count} query cache entries")
        return cleared_count

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            total_pools = len(self._connection_pools)
            healthy_pools = 0

            for pool_name in self._connection_pools.keys():
                try:
                    with self.get_connection(pool_name) as conn:
                        if conn.db_type == DatabaseType.DUCKDB:
                            conn.execute("SELECT 1")
                        elif conn.db_type == DatabaseType.SQLITE:
                            conn.execute("SELECT 1")
                    healthy_pools += 1
                except:
                    pass

            return {
                "status": "healthy" if healthy_pools > 0 else "unhealthy",
                "total_pools": total_pools,
                "healthy_pools": healthy_pools,
                "active_transactions": self._metrics.active_transactions,
                "query_cache_size": len(self._query_cache),
                "avg_query_time": self._metrics.avg_query_time,
                "total_queries": self._metrics.total_queries,
                "success_rate": (
                    self._metrics.successful_queries / max(1, self._metrics.total_queries) * 100
                )
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing DatabaseService resources...")

            # 关闭所有连接
            for pool_name, pool in self._connection_pools.items():
                for connection in pool:
                    connection.close()
                pool.clear()

            # 清理缓存
            self._query_cache.clear()

            # 清理事务
            self._active_transactions.clear()
            self._transaction_connections.clear()

            logger.info("DatabaseService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing DatabaseService: {e}")

    def _initialize_ai_tables(self) -> None:
        """初始化AI选股相关数据表"""
        try:
            logger.info("Initializing AI selection database tables...")

            # 创建AI选股策略表
            self._create_ai_strategy_table()
            
            # 创建AI选股结果表
            self._create_ai_selection_results_table()
            
            # 创建AI策略回测结果表
            self._create_ai_backtest_results_table()
            
            # 创建AI选股解释表
            self._create_ai_explanations_table()
            
            # 创建用户画像表
            self._create_user_profiles_table()

            logger.info("✓ AI selection database tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize AI selection tables: {e}")
            raise
            
    def _initialize_strategy_tables(self) -> None:
        """初始化策略配置相关数据表"""
        try:
            logger.info("Initializing strategy configuration database tables...")

            # 创建策略配置表
            self._create_strategy_config_table()

            # 创建策略表
            self._create_strategies_table()

            # 注意：订单表现在由多资产支持系统管理，不再在此处创建
            # 订单表会根据资产类型路由到对应的数据库中
            # 请使用 scripts/init_order_databases_auto.py 初始化订单数据库

            logger.info("✓ Strategy configuration database tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize strategy configuration tables: {e}")
            raise

    def _initialize_trade_account_tables(self) -> None:
        """初始化交易账户相关数据表"""
        try:
            logger.info("Initializing trade account database tables...")

            # 创建账户表
            self._create_accounts_table()

            logger.info("✓ Trade account database tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize trade account tables: {e}")
            raise

    def _create_accounts_table(self) -> None:
        """创建账户表"""
        sql = """
        CREATE TABLE IF NOT EXISTS accounts (
            account_id VARCHAR(36) PRIMARY KEY,
            account_name VARCHAR(100) NOT NULL,
            account_type VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT 'active',
            balance DECIMAL(20, 8) DEFAULT 0.0,
            available_balance DECIMAL(20, 8) DEFAULT 0.0,
            frozen_balance DECIMAL(20, 8) DEFAULT 0.0,
            market_value DECIMAL(20, 8) DEFAULT 0.0,
            total_assets DECIMAL(20, 8) DEFAULT 0.0,
            profit_loss DECIMAL(20, 8) DEFAULT 0.0,
            profit_loss_ratio DECIMAL(10, 4) DEFAULT 0.0,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id VARCHAR(100),
            trading_day DATE,
            risk_level VARCHAR(50) DEFAULT 'normal',
            margin_ratio DECIMAL(10, 4) DEFAULT 0.0,
            maintenance_margin DECIMAL(20, 8) DEFAULT 0.0,
            metadata TEXT DEFAULT '{}',
            
            -- 机构信息
            institution_name VARCHAR(128) DEFAULT '',
            institution_type VARCHAR(32) DEFAULT 'broker',
            
            -- 交易接口类型
            trading_interface_type VARCHAR(32) DEFAULT 'mock',
            
            ctp_broker_id VARCHAR(50),
            ctp_investor_id VARCHAR(50),
            ctp_password TEXT,
            ctp_trade_front VARCHAR(200),
            ctp_quote_front VARCHAR(200),
            ctp_app_id VARCHAR(50),
            ctp_auth_code TEXT,
            ctp_product_info VARCHAR(50),
            xtp_account_id VARCHAR(50),
            xtp_password TEXT,
            xtp_server_address VARCHAR(200),
            
            -- 交易接口（已废弃，使用 trading_interface_type 替代）
            trading_interface VARCHAR(32) DEFAULT ''
        )
        """

        with self.get_connection("tradeaccount_sqlite") as conn:
            conn.execute(sql)

        # 创建索引
        index_sqls = [
            "CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_accounts_account_type ON accounts(account_type)",
            "CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)",
            "CREATE INDEX IF NOT EXISTS idx_accounts_trading_day ON accounts(trading_day)"
        ]

        for index_sql in index_sqls:
            with self.get_connection("tradeaccount_sqlite") as conn:
                conn.execute(index_sql)

        logger.info("✓ Accounts table created")
            
    def _create_strategy_config_table(self) -> None:
        """创建策略配置表"""
        sql = """
        CREATE TABLE IF NOT EXISTS strategy_configs (
            strategy_id VARCHAR(36) PRIMARY KEY,
            plugin_type VARCHAR(50) NOT NULL,
            parameters JSON NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON DEFAULT '{}'
        )
        """
        
        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_strategy_configs_plugin_type ON strategy_configs(plugin_type)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_configs_enabled ON strategy_configs(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_configs_created ON strategy_configs(created_at)"
        ]
        
        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_strategies_table(self) -> None:
        """创建策略表"""
        sql = """
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            strategy_type TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0.0',
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            metadata TEXT DEFAULT '{}',
            class_path TEXT NOT NULL
        )
        """

        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql)

        indices = [
            "CREATE INDEX IF NOT EXISTS idx_strategies_type ON strategies(strategy_type)",
            "CREATE INDEX IF NOT EXISTS idx_strategies_active ON strategies(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_strategies_category ON strategies(category)"
        ]

        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_ai_strategy_table(self) -> None:
        """创建AI选股策略表"""
        sql = """
        CREATE TABLE IF NOT EXISTS ai_strategies (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            strategy_type VARCHAR(50) NOT NULL,
            parameters JSON NOT NULL,
            weight_config JSON,
            risk_config JSON,
            performance_metrics JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            version INTEGER DEFAULT 1,
            created_by VARCHAR(100),
            tags TEXT,
            status VARCHAR(20) DEFAULT 'draft'
        )
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_ai_strategies_type ON ai_strategies(strategy_type)",
            "CREATE INDEX IF NOT EXISTS idx_ai_strategies_active ON ai_strategies(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_ai_strategies_created ON ai_strategies(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_ai_strategies_status ON ai_strategies(status)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_ai_selection_results_table(self) -> None:
        """创建AI选股结果表"""
        sql = """
        CREATE TABLE IF NOT EXISTS ai_selection_results (
            id VARCHAR(36) PRIMARY KEY,
            strategy_id VARCHAR(36) NOT NULL,
            selection_date DATE NOT NULL,
            stock_code VARCHAR(20) NOT NULL,
            stock_name VARCHAR(255),
            industry VARCHAR(100),
            selection_reason JSON,
            score DECIMAL(10,4),
            weight DECIMAL(8,6),
            confidence DECIMAL(5,4),
            risk_level VARCHAR(20),
            expected_return DECIMAL(10,4),
            volatility DECIMAL(10,4),
            sharpe_ratio DECIMAL(8,4),
            max_drawdown DECIMAL(8,4),
            market_cap DECIMAL(20,2),
            pe_ratio DECIMAL(10,2),
            pb_ratio DECIMAL(10,2),
            turnover_rate DECIMAL(8,4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            backtested BOOLEAN DEFAULT FALSE,
            performance_updated_at TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES ai_strategies(id)
        )
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_ai_results_strategy ON ai_selection_results(strategy_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_results_date ON ai_selection_results(selection_date)",
            "CREATE INDEX IF NOT EXISTS idx_ai_results_stock ON ai_selection_results(stock_code)",
            "CREATE INDEX IF NOT EXISTS idx_ai_results_score ON ai_selection_results(score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ai_results_risk ON ai_selection_results(risk_level)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_ai_backtest_results_table(self) -> None:
        """创建AI策略回测结果表"""
        sql = """
        CREATE TABLE IF NOT EXISTS ai_backtest_results (
            id VARCHAR(36) PRIMARY KEY,
            strategy_id VARCHAR(36) NOT NULL,
            backtest_period_start DATE NOT NULL,
            backtest_period_end DATE NOT NULL,
            total_return DECIMAL(10,4),
            annual_return DECIMAL(10,4),
            volatility DECIMAL(10,4),
            sharpe_ratio DECIMAL(8,4),
            max_drawdown DECIMAL(8,4),
            win_rate DECIMAL(5,4),
            profit_loss_ratio DECIMAL(8,4),
            calmar_ratio DECIMAL(8,4),
            sortino_ratio DECIMAL(8,4),
            beta DECIMAL(8,4),
            alpha DECIMAL(8,4),
            information_ratio DECIMAL(8,4),
            tracking_error DECIMAL(8,4),
            benchmark_return DECIMAL(10,4),
            excess_return DECIMAL(10,4),
            turnover_rate DECIMAL(8,4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            backtest_config JSON,
            daily_returns JSON,
            monthly_returns JSON,
            trade_records JSON,
            FOREIGN KEY (strategy_id) REFERENCES ai_strategies(id)
        )
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_ai_backtest_strategy ON ai_backtest_results(strategy_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_backtest_period ON ai_backtest_results(backtest_period_start, backtest_period_end)",
            "CREATE INDEX IF NOT EXISTS idx_ai_backtest_sharpe ON ai_backtest_results(sharpe_ratio DESC)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_ai_explanations_table(self) -> None:
        """创建AI选股解释表"""
        sql = """
        CREATE TABLE IF NOT EXISTS ai_explanations (
            id VARCHAR(36) PRIMARY KEY,
            selection_result_id VARCHAR(36) NOT NULL,
            explanation_type VARCHAR(50) NOT NULL,
            factor_name VARCHAR(100) NOT NULL,
            factor_value DECIMAL(15,6),
            contribution_score DECIMAL(8,4),
            importance_rank INTEGER,
            explanation_text TEXT,
            visualization_data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (selection_result_id) REFERENCES ai_selection_results(id)
        )
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_ai_explain_result ON ai_explanations(selection_result_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_explain_type ON ai_explanations(explanation_type)",
            "CREATE INDEX IF NOT EXISTS idx_ai_explain_factor ON ai_explanations(factor_name)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_user_profiles_table(self) -> None:
        """创建用户画像表"""
        sql = """
        CREATE TABLE IF NOT EXISTS user_profiles (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL UNIQUE,
            risk_tolerance VARCHAR(20),
            investment_horizon VARCHAR(20),
            investment_style VARCHAR(50),
            preferred_industries TEXT,
            excluded_industries TEXT,
            max_position_size DECIMAL(5,4),
            min_market_cap DECIMAL(20,2),
            max_pe_ratio DECIMAL(10,2),
            max_pb_ratio DECIMAL(10,2),
            max_volatility DECIMAL(8,4),
            preferred_stock_count INTEGER,
            rebalance_frequency VARCHAR(20),
            custom_constraints JSON,
            performance_history JSON,
            feedback_data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_user ON user_profiles(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_risk ON user_profiles(risk_tolerance)",
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_style ON user_profiles(investment_style)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def create_ai_strategy(self, strategy_data: Dict[str, Any]) -> str:
        """
        创建AI选股策略
        
        Args:
            strategy_data: 策略数据
            
        Returns:
            策略ID
        """
        strategy_id = str(uuid.uuid4())
        
        sql = """
        INSERT INTO ai_strategies (
            id, name, description, strategy_type, parameters, weight_config, 
            risk_config, performance_metrics, created_by, tags, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            strategy_id,
            strategy_data.get('name', ''),
            strategy_data.get('description', ''),
            strategy_data.get('strategy_type', 'comprehensive'),
            json.dumps(strategy_data.get('parameters', {})),
            json.dumps(strategy_data.get('weight_config', {})),
            json.dumps(strategy_data.get('risk_config', {})),
            json.dumps(strategy_data.get('performance_metrics', {})),
            strategy_data.get('created_by', 'system'),
            strategy_data.get('tags', ''),
            strategy_data.get('status', 'draft')
        )
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql, params)
            
        logger.info(f"Created AI strategy: {strategy_id}")
        return strategy_id

    def save_ai_selection_results(self, results: List[Dict[str, Any]]) -> None:
        """
        保存AI选股结果
        
        Args:
            results: 选股结果列表
        """
        if not results:
            return
            
        sql = """
        INSERT OR REPLACE INTO ai_selection_results (
            id, strategy_id, selection_date, stock_code, stock_name, industry,
            selection_reason, score, weight, confidence, risk_level,
            expected_return, volatility, sharpe_ratio, max_drawdown,
            market_cap, pe_ratio, pb_ratio, turnover_rate, backtested
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            for result in results:
                result_id = result.get('id', str(uuid.uuid4()))
                params = (
                    result_id,
                    result.get('strategy_id'),
                    result.get('selection_date'),
                    result.get('stock_code'),
                    result.get('stock_name'),
                    result.get('industry'),
                    json.dumps(result.get('selection_reason', {})),
                    result.get('score'),
                    result.get('weight'),
                    result.get('confidence'),
                    result.get('risk_level'),
                    result.get('expected_return'),
                    result.get('volatility'),
                    result.get('sharpe_ratio'),
                    result.get('max_drawdown'),
                    result.get('market_cap'),
                    result.get('pe_ratio'),
                    result.get('pb_ratio'),
                    result.get('turnover_rate'),
                    result.get('backtested', False)
                )
                conn.execute(sql, params)
                
        logger.info(f"Saved {len(results)} AI selection results")

    def get_ai_strategies(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        获取AI策略列表
        
        Args:
            active_only: 是否只获取活跃策略
            
        Returns:
            策略列表
        """
        sql = """
        SELECT * FROM ai_strategies
        """
        
        params = ()
        if active_only:
            sql += " WHERE is_active = TRUE"
            
        sql += " ORDER BY created_at DESC"
        
        with self.get_connection("analytics_duckdb") as conn:
            rows = conn.execute(sql, params).fetchall()
            
        strategies = []
        for row in rows:
            strategy = dict(row)
            # 解析JSON字段
            strategy['parameters'] = json.loads(strategy['parameters']) if strategy['parameters'] else {}
            strategy['weight_config'] = json.loads(strategy['weight_config']) if strategy['weight_config'] else {}
            strategy['risk_config'] = json.loads(strategy['risk_config']) if strategy['risk_config'] else {}
            strategy['performance_metrics'] = json.loads(strategy['performance_metrics']) if strategy['performance_metrics'] else {}
            strategies.append(strategy)
            
        return strategies

    def get_latest_selection_results(self, strategy_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取最新的选股结果
        
        Args:
            strategy_id: 策略ID
            limit: 返回数量限制
            
        Returns:
            选股结果列表
        """
        sql = """
        SELECT * FROM ai_selection_results 
        WHERE strategy_id = ?
        ORDER BY selection_date DESC, score DESC
        LIMIT ?
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            rows = conn.execute(sql, (strategy_id, limit)).fetchall()
            
        results = []
        for row in rows:
            result = dict(row)
            result['selection_reason'] = json.loads(result['selection_reason']) if result['selection_reason'] else {}
            results.append(result)
            
        return results

    def save_ai_backtest_results(self, backtest_data: Dict[str, Any]) -> str:
        """
        保存AI策略回测结果
        
        Args:
            backtest_data: 回测数据
            
        Returns:
            回测结果ID
        """
        backtest_id = str(uuid.uuid4())
        
        sql = """
        INSERT INTO ai_backtest_results (
            id, strategy_id, backtest_period_start, backtest_period_end,
            total_return, annual_return, volatility, sharpe_ratio, max_drawdown,
            win_rate, profit_loss_ratio, calmar_ratio, sortino_ratio,
            beta, alpha, information_ratio, tracking_error,
            benchmark_return, excess_return, turnover_rate,
            backtest_config, daily_returns, monthly_returns, trade_records
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            backtest_id,
            backtest_data.get('strategy_id'),
            backtest_data.get('backtest_period_start'),
            backtest_data.get('backtest_period_end'),
            backtest_data.get('total_return'),
            backtest_data.get('annual_return'),
            backtest_data.get('volatility'),
            backtest_data.get('sharpe_ratio'),
            backtest_data.get('max_drawdown'),
            backtest_data.get('win_rate'),
            backtest_data.get('profit_loss_ratio'),
            backtest_data.get('calmar_ratio'),
            backtest_data.get('sortino_ratio'),
            backtest_data.get('beta'),
            backtest_data.get('alpha'),
            backtest_data.get('information_ratio'),
            backtest_data.get('tracking_error'),
            backtest_data.get('benchmark_return'),
            backtest_data.get('excess_return'),
            backtest_data.get('turnover_rate'),
            json.dumps(backtest_data.get('backtest_config', {})),
            json.dumps(backtest_data.get('daily_returns', [])),
            json.dumps(backtest_data.get('monthly_returns', [])),
            json.dumps(backtest_data.get('trade_records', []))
        )
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql, params)
            
        logger.info(f"Saved AI backtest results: {backtest_id}")
        return backtest_id

    def save_ai_explanations(self, explanations: List[Dict[str, Any]]) -> None:
        """
        保存AI选股解释
        
        Args:
            explanations: 解释列表
        """
        if not explanations:
            return
            
        sql = """
        INSERT OR REPLACE INTO ai_explanations (
            id, selection_result_id, explanation_type, factor_name,
            factor_value, contribution_score, importance_rank,
            explanation_text, visualization_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            for explanation in explanations:
                explanation_id = explanation.get('id', str(uuid.uuid4()))
                params = (
                    explanation_id,
                    explanation.get('selection_result_id'),
                    explanation.get('explanation_type'),
                    explanation.get('factor_name'),
                    explanation.get('factor_value'),
                    explanation.get('contribution_score'),
                    explanation.get('importance_rank'),
                    explanation.get('explanation_text'),
                    json.dumps(explanation.get('visualization_data', {}))
                )
                conn.execute(sql, params)
                
        logger.info(f"Saved {len(explanations)} AI explanations")

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户画像
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户画像数据
        """
        sql = """
        SELECT * FROM user_profiles 
        WHERE user_id = ? AND is_active = TRUE
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            row = conn.execute(sql, (user_id,)).fetchone()
            
        if not row:
            return None
            
        profile = dict(row)
        profile['preferred_industries'] = profile['preferred_industries'].split(',') if profile['preferred_industries'] else []
        profile['excluded_industries'] = profile['excluded_industries'].split(',') if profile['excluded_industries'] else []
        profile['custom_constraints'] = json.loads(profile['custom_constraints']) if profile['custom_constraints'] else {}
        profile['performance_history'] = json.loads(profile['performance_history']) if profile['performance_history'] else {}
        profile['feedback_data'] = json.loads(profile['feedback_data']) if profile['feedback_data'] else {}
        
        return profile

    def save_user_profile(self, profile_data: Dict[str, Any]) -> str:
        """
        保存用户画像
        
        Args:
            profile_data: 用户画像数据
            
        Returns:
            用户画像ID
        """
        user_id = profile_data.get('user_id')
        if not user_id:
            raise ValueError("user_id is required")
            
        # 检查用户画像是否已存在
        existing = self.get_user_profile(user_id)
        profile_id = existing['id'] if existing else str(uuid.uuid4())
        
        sql = """
        INSERT OR REPLACE INTO user_profiles (
            id, user_id, risk_tolerance, investment_horizon, investment_style,
            preferred_industries, excluded_industries, max_position_size,
            min_market_cap, max_pe_ratio, max_pb_ratio, max_volatility,
            preferred_stock_count, rebalance_frequency, custom_constraints,
            performance_history, feedback_data, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            profile_id,
            user_id,
            profile_data.get('risk_tolerance'),
            profile_data.get('investment_horizon'),
            profile_data.get('investment_style'),
            ','.join(profile_data.get('preferred_industries', [])),
            ','.join(profile_data.get('excluded_industries', [])),
            profile_data.get('max_position_size'),
            profile_data.get('min_market_cap'),
            profile_data.get('max_pe_ratio'),
            profile_data.get('max_pb_ratio'),
            profile_data.get('max_volatility'),
            profile_data.get('preferred_stock_count'),
            profile_data.get('rebalance_frequency'),
            json.dumps(profile_data.get('custom_constraints', {})),
            json.dumps(profile_data.get('performance_history', {})),
            json.dumps(profile_data.get('feedback_data', {})),
            profile_data.get('is_active', True)
        )
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql, params)
            
        logger.info(f"Saved user profile: {user_id}")
        return profile_id

    @property
    def metrics(self) -> Dict[str, Any]:
        """返回数据库服务指标的字典表示"""
        if not hasattr(self, '_database_metrics'):
            self._database_metrics = self._metrics

        return {
            'total_queries': self._database_metrics.total_queries,
            'successful_queries': self._database_metrics.successful_queries,
            'failed_queries': self._database_metrics.failed_queries,
            'avg_query_time': self._database_metrics.avg_query_time,
            'active_transactions': self._database_metrics.active_transactions,
            'total_transactions': self._database_metrics.total_transactions,
            'database_connections': self._database_metrics.database_connections,
            'last_update': self._database_metrics.last_update.isoformat()
        }

    def get_connection_pool(self, pool_name: str) -> Optional[List[DatabaseConnection]]:
        """
        获取指定连接池
        
        Args:
            pool_name: 连接池名称
            
        Returns:
            连接池列表，如果连接池不存在则返回 None
        """
        return self._connection_pools.get(pool_name)

    def _create_orders_table(self, pool_name: str) -> None:
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

        with self.get_connection(pool_name) as conn:
            conn.execute(sql)

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
            "CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders(account_id)"
        ]

        with self.get_connection(pool_name) as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_order_fills_table(self, pool_name: str) -> None:
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

        with self.get_connection(pool_name) as conn:
            conn.execute(sql)

        indices = [
            "CREATE INDEX IF NOT EXISTS idx_order_fills_order_id ON order_fills(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_order_fills_stock_code ON order_fills(stock_code)",
            "CREATE INDEX IF NOT EXISTS idx_order_fills_fill_time ON order_fills(fill_time)"
        ]

        with self.get_connection(pool_name) as conn:
            for index_sql in indices:
                conn.execute(index_sql)
