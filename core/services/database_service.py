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
from typing import Any, Dict, List, Optional, Type, Union, Callable, Generator, Tuple, TYPE_CHECKING
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
import numpy as np


def _serialize_for_json(value: Any) -> Any:
    """
    将值序列化为 JSON 兼容格式
    
    处理 numpy 数组和其他不可序列化的类型
    """
    if value is None:
        return None
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, dict):
        return {k: _serialize_for_json(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_serialize_for_json(item) for item in value]
    else:
        return value

# 延迟导入以避免循环依赖
if TYPE_CHECKING:
    from ..database.adaptive_connection_pool import AdaptiveConnectionPoolManager


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
                
                # 对于 SELECT 查询，将元组列表转换为字典列表
                if is_select and result is not None:
                    # 尝试使用 fetchdf 获取 DataFrame 并转换为字典列表
                    try:
                        df = result.fetchdf()
                        return df.to_dict('records')
                    except Exception as e:
                        # 如果 fetchdf 失败，尝试其他方法
                        logger.debug(f"fetchdf failed: {e}, trying alternative method")
                        try:
                            # 尝试获取列名并转换
                            if hasattr(result, 'description'):
                                columns = [col[0] for col in result.description]
                            elif hasattr(result, 'columns'):
                                columns = result.columns
                            else:
                                columns = None
                            
                            if columns:
                                rows = result.fetchall()
                                return [dict(zip(columns, row)) for row in rows]
                            else:
                                return result.fetchall()
                        except Exception as e2:
                            logger.warning(f"Alternative conversion failed: {e2}, returning raw result")
                            return result.fetchall()
                else:
                    return None
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

    def executemany(self, sql: str, parameters: List[Union[Tuple, List]]) -> None:
        """批量执行SQL
        
        Args:
            sql: SQL语句
            parameters: 参数列表，每个元素是一个参数元组或列表
        
        Note:
            DuckDB原生支持executemany方法
            SQLite的cursor也支持executemany方法
        """
        self.last_used = datetime.now()
        self.query_count += len(parameters)

        try:
            if self.db_type == DatabaseType.DUCKDB:
                # DuckDB原生支持executemany
                if isinstance(parameters, list) and all(isinstance(p, (tuple, list)) for p in parameters):
                    # 确保每个参数都是元组或列表
                    result = self.connection.executemany(sql, parameters)
                else:
                    # 如果参数格式不对，回退到循环执行
                    logger.warning("DuckDB executemany参数格式不正确，使用循环执行")
                    for params in parameters:
                        self.connection.execute(sql, params)
            elif self.db_type == DatabaseType.SQLITE:
                # SQLite通过cursor执行
                cursor = self.connection.cursor()
                cursor.executemany(sql, parameters)
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
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
        self._last_result = None

    def execute(self, sql: str, parameters: Optional[Tuple] = None):
        """执行SQL查询"""
        try:
            if parameters:
                self._last_result = self.connection.execute(sql, parameters)
            else:
                self._last_result = self.connection.execute(sql)
            return self
        except Exception as e:
            logger.error(f"DuckDB execute failed: {e}")
            raise

    def fetchall(self):
        """获取所有结果"""
        if self._last_result is None:
            return []
        
        try:
            # 尝试转换为字典列表
            if hasattr(self._last_result, 'fetchdf'):
                df = self._last_result.fetchdf()
                return df.to_dict('records')
            elif hasattr(self._last_result, '__iter__'):
                # 如果是可迭代对象，转换为列表
                return list(self._last_result)
            else:
                return []
        except Exception as e:
            logger.error(f"DuckDB fetchall failed: {e}")
            return []

    def fetchone(self):
        """获取单个结果"""
        if self._last_result is None:
            return None
        
        try:
            # 尝试获取第一行
            if hasattr(self._last_result, 'fetchdf'):
                df = self._last_result.fetchdf()
                if len(df) > 0:
                    return df.iloc[0].to_dict()
                return None
            elif hasattr(self._last_result, '__iter__'):
                # 如果是可迭代对象，获取第一个元素
                result_list = list(self._last_result)
                if len(result_list) > 0:
                    return result_list[0]
                return None
            else:
                return None
        except Exception as e:
            logger.error(f"DuckDB fetchone failed: {e}")
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
    # 支持订单的资产类型（复用 AssetType 枚举）
    # 延迟初始化，避免循环依赖
    _ORDER_SUPPORTED_ASSET_TYPES = None
    
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
        
        # 自适应连接池管理器（支持多个连接池）
        self._adaptive_managers: Dict[str, 'AdaptiveConnectionPoolManager'] = {}

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
            "factorweave_system_sqlite": DatabaseConfig(
                db_type=DatabaseType.SQLITE,
                db_path="data/factorweave_system.sqlite",
                pool_size=10,
                max_pool_size=30
            ),
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
            
            # 初始化支持订单的资产类型集合
            DatabaseService._ORDER_SUPPORTED_ASSET_TYPES = {
                AssetType.STOCK_A,
                AssetType.STOCK_B,
                AssetType.STOCK_HK,
                AssetType.STOCK_US,
                AssetType.FUTURES,
                AssetType.OPTION,
                AssetType.CRYPTO,
                AssetType.FOREX,
                AssetType.BOND,
                AssetType.COMMODITY,
                AssetType.INDEX,
                AssetType.FUND,
                AssetType.WARRANT
            }
            
            # 只为支持订单的资产类型创建配置
            for asset_type in AssetType:
                if asset_type in DatabaseService._ORDER_SUPPORTED_ASSET_TYPES:
                    pool_name = f"{asset_type.value.lower()}_orders"
                    db_path = f"data/databases/{asset_type.value.lower()}/{pool_name}.duckdb"
                    self._order_db_configs[pool_name] = DatabaseConfig(
                        db_type=DatabaseType.DUCKDB,
                        db_path=db_path,
                        pool_size=5,
                        max_pool_size=15
                    )
                    logger.debug(f"✓ Added order database config for {asset_type.value}")
                else:
                    logger.debug(f"⊘ Skipped {asset_type.value} (orders not supported)")
                    
        except Exception as e:
            logger.warning(f"初始化订单数据库配置失败: {e}")

        # 监控和统计
        self._start_time = datetime.now()
        self._last_checkpoint = datetime.now()
        self._last_backup = datetime.now()

        logger.info("DatabaseService initialized for architecture simplification")

    def initialize(self) -> None:
        """
        初始化数据库服务（公开方法，供服务容器调用）
        """
        self._do_initialize()

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

            # 6. 初始化分析数据库
            self._initialize_analytics_db()

            # 7. 初始化AI选股相关数据表
            self._initialize_ai_tables()
            
            # 8. 初始化系统配置相关数据表
            self._initialize_system_config_tables()
            
            # 9. 初始化策略配置相关数据表
            self._initialize_strategy_tables()

            # 10. 初始化交易账户相关数据表
            self._initialize_trade_account_tables()

            # 11. 初始化性能优化器
            self._initialize_performance_optimizers()

            # 12. 启动后台任务
            self._start_background_tasks()

            # 13. 验证数据库连接
            self._validate_database_connections()

            logger.info("DatabaseService initialized successfully with full database management capabilities")

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
            # 创建默认数据库连接池
            for pool_name, config in self._default_db_configs.items():
                self.create_connection_pool(pool_name, config)

            logger.info(f"✓ Created {len(self._default_db_configs)} default connection pools")

            # 创建订单数据库连接池
            order_pools_created = 0
            order_pools_failed = 0
            
            for pool_name, config in self._order_db_configs.items():
                try:
                    self.create_connection_pool(pool_name, config)
                    order_pools_created += 1
                    logger.debug(f"✓ Created order pool: {pool_name}")
                except Exception as e:
                    order_pools_failed += 1
                    logger.warning(f"Failed to create order database pool {pool_name}: {e}")

            logger.info(f"✓ Created {order_pools_created}/{len(self._order_db_configs)} order database connection pools")
            if order_pools_failed > 0:
                logger.warning(f"⊘ {order_pools_failed} order pools failed to create")

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

        metrics = self._pool_metrics[pool_name]
        metrics.total_connections = len(self._connection_pools[pool_name])

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
                    except (AttributeError, duckdb.IOException, Exception) as e:
                        logger.debug(f"DuckDB不支持WAL模式: {e}")

                return connection

            elif config.db_type == DatabaseType.SQLITE:
                # 确保目录存在
                db_path = Path(config.db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)

                # 创建SQLite连接
                connection = sqlite3.connect(
                    str(db_path),
                    timeout=config.timeout,
                    check_same_thread=False
                )

                # 设置行工厂，使查询结果返回字典格式
                connection.row_factory = sqlite3.Row

                # 设置自动提交模式（相当于 autocommit=True）
                connection.isolation_level = None

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
                    connection.is_active = False
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
            connection.is_active = True
            metrics.active_connections = max(0, metrics.active_connections - 1)

    def execute_query(self, sql: str, parameters: Optional[Union[Dict[str, Any], List[Any]]] = None,
                      pool_name: str = "analytics_duckdb") -> Any:
        """
        执行查询

        Args:
            sql: SQL查询语句
            parameters: 查询参数（支持字典或列表）
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

        # 检测是否为写操作
        sql_upper = sql.strip().upper()
        is_write_operation = any(sql_upper.startswith(prefix) for prefix in 
                                ['INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'REPLACE'])

        try:
            with self._query_lock:
                self._metrics.total_queries += 1
                self._query_counter += 1

            # 检查查询缓存（仅针对读操作）
            if self._config["enable_query_cache"] and not is_write_operation:
                cache_key = self._generate_query_cache_key(sql, parameters)
                cached_result = self._get_from_query_cache(cache_key)
                if cached_result is not None:
                    return cached_result

            # 执行查询
            with self.get_connection(pool_name) as conn:
                result = conn.execute(sql, parameters)

                # 如果是写操作，提交事务
                if is_write_operation:
                    conn.commit()
                    logger.debug(f"事务已提交: {sql[:100]}...")

                # 对于读操作，获取所有结果（避免游标在连接归还后失效）
                if not is_write_operation:
                    if hasattr(result, 'fetchall'):
                        # 游标对象，获取所有结果
                        result = result.fetchall()
                    elif not isinstance(result, list):
                        # 其他情况，转换为列表
                        result = list(result)

                # 更新缓存（仅针对读操作）
                if self._config["enable_query_cache"] and not is_write_operation:
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

    def fetch_all(self, sql: str, parameters: Optional[Union[Dict[str, Any], List[Any]]] = None,
                  pool_name: str = "analytics_duckdb") -> List[Dict[str, Any]]:
        """
        执行查询并返回所有结果

        Args:
            sql: SQL查询语句
            parameters: 查询参数（支持字典或列表）
            pool_name: 连接池名称（默认："analytics_duckdb"）

        Returns:
            查询结果列表
        """
        result = self.execute_query(sql, parameters, pool_name)
        
        logger.debug(f"fetch_all: result type = {type(result)}, has fetchall = {hasattr(result, 'fetchall')}")
        
        # 如果结果已经是列表，检查是否需要转换 sqlite3.Row 对象
        if isinstance(result, list):
            # 检查列表中的元素是否是 sqlite3.Row 对象
            if result and hasattr(result[0], 'keys'):
                # SQLite Row 对象，转换为字典
                return [dict(row) for row in result]
            return result
        
        # 如果结果是DuckDB的ArrowTable或类似对象，转换为列表
        try:
            if hasattr(result, 'to_pydict'):
                # DuckDB ArrowTable
                data = result.to_pydict()
                if not data or not isinstance(data, dict):
                    logger.warning(f"to_pydict returned invalid data: {type(data)}")
                    return []
                
                # 检查数据格式
                keys = list(data.keys())
                values = list(data.values())
                
                # 确保所有值都是列表
                if not all(isinstance(v, list) for v in values):
                    logger.warning(f"to_pydict returned non-list values: {[type(v) for v in values]}")
                    return []
                
                # 转换为字典列表
                result_list = []
                for i in range(len(values[0]) if values else 0):
                    row_dict = {}
                    for j, key in enumerate(keys):
                        if j < len(values) and i < len(values[j]):
                            row_dict[key] = values[j][i]
                    result_list.append(row_dict)
                
                logger.debug(f"Converted DuckDB result: {len(result_list)} rows")
                return result_list
            elif hasattr(result, 'fetchall'):
                # 游标对象
                rows = result.fetchall()
                # 检查是否是 sqlite3.Row 对象
                if rows and hasattr(rows[0], 'keys'):
                    # SQLite Row 对象，转换为字典
                    return [dict(row) for row in rows]
                return rows
            else:
                # 其他情况，尝试转换为列表
                return list(result)
        except Exception as e:
            logger.error(f"Failed to convert query result: {e}, result type: {type(result)}")
            return []

    def fetch_one(self, sql: str, parameters: Optional[Union[Dict[str, Any], List[Any]]] = None,
                  pool_name: str = "analytics_duckdb") -> Optional[Dict[str, Any]]:
        """
        执行查询并返回单个结果

        Args:
            sql: SQL查询语句
            parameters: 查询参数（支持字典或列表）
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
                except Exception as e:
                    logger.warning(f"事务回滚失败: {e}")

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
                               parameters: Optional[Union[Dict[str, Any], List[Any]]] = None) -> Any:
        """
        在事务中执行查询

        Args:
            transaction_id: 事务ID
            sql: SQL语句
            parameters: 查询参数（支持字典或列表）

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

    def _generate_query_cache_key(self, sql: str, parameters: Optional[Union[Dict[str, Any], List[Any]]]) -> str:
        """生成查询缓存键"""
        import hashlib

        key_data = sql
        if parameters:
            if isinstance(parameters, dict):
                param_str = str(sorted(parameters.items()))
            else:
                param_str = str(parameters)
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
                            except Exception as e:
                                logger.debug(f"连接验证失败，关闭连接: {e}")
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

    def create_adaptive_manager(self, pool_name: str, config: dict) -> 'Optional[AdaptiveConnectionPoolManager]':
        """为指定连接池创建自适应管理器
        
        Args:
            pool_name: 连接池名称
            config: 自适应配置字典
            
        Returns:
            AdaptiveConnectionPoolManager实例或None（如果失败）
        """
        try:
            from .database.adaptive_connection_pool import AdaptiveConnectionPoolManager
            from .database.factorweave_analytics_db import get_analytics_db
            from .database.connection_pool_config import ConnectionPoolConfig
            
            # 检查是否启用自适应
            from core.services.config_service import ConfigService
            from core.containers import get_service_container
            container = get_service_container()
            config_service = container.resolve(ConfigService)
            from .database.connection_pool_config import ConnectionPoolConfigManager
            config_manager = ConnectionPoolConfigManager(config_service)
            
            pool_config = config_manager.load_adaptive_pool_config(pool_name)
            
            if not pool_config.get('enabled', False):
                logger.info(f"连接池 {pool_name} 未启用自适应管理")
                return None
            
            # 获取数据库实例
            if pool_name == "analytics_duckdb":
                db = get_analytics_db()
            else:
                logger.warning(f"连接池 {pool_name} 不支持自适应管理（仅 analytics_duckdb 支持）")
                return None
            
            # 创建自适应配置
            from .database.adaptive_connection_pool import AdaptivePoolConfig
            adaptive_config = AdaptivePoolConfig(**pool_config)
            
            # 创建并启动管理器
            manager = AdaptiveConnectionPoolManager(db, adaptive_config)
            manager.start()
            
            # 保存到管理器字典
            self._adaptive_managers[pool_name] = manager
            
            logger.info(f"连接池 {pool_name} 的自适应管理器已创建并启动")
            return manager
            
        except Exception as e:
            logger.error(f"创建自适应管理器失败: {e}")
            return None

    def get_adaptive_manager(self, pool_name: str) -> 'Optional[AdaptiveConnectionPoolManager]':
        """获取指定连接池的自适应管理器
        
        Args:
            pool_name: 连接池名称
            
        Returns:
            AdaptiveConnectionPoolManager实例或None
        """
        return self._adaptive_managers.get(pool_name)

    def stop_adaptive_manager(self, pool_name: str) -> None:
        """停止指定连接池的自适应管理器
        
        Args:
            pool_name: 连接池名称
        """
        manager = self._adaptive_managers.get(pool_name)
        if manager:
            manager.stop()
            del self._adaptive_managers[pool_name]
            logger.info(f"连接池 {pool_name} 的自适应管理器已停止")
        else:
            logger.warning(f"连接池 {pool_name} 没有自适应管理器")

    def get_all_adaptive_managers(self) -> Dict[str, 'AdaptiveConnectionPoolManager']:
        """获取所有自适应管理器
        
        Returns:
            所有自适应管理器的字典
        """
        return self._adaptive_managers.copy()

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
                except Exception as e:
                    logger.warning(f"连接池 {pool_name} 健康检查失败: {e}")

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
            
            # 创建用户交互表
            self._create_user_interactions_table()
            
            # 创建内容项表
            self._create_content_items_table()

            # 初始化默认AI策略
            self._initialize_default_ai_strategies()

            logger.info("✓ AI selection database tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize AI selection tables: {e}")
            raise
            
    def _initialize_system_config_tables(self) -> None:
        """初始化系统配置相关数据表"""
        try:
            logger.info("Initializing system configuration database tables...")

            # 创建用户偏好表
            self._create_user_preferences_table()
            
            # 创建用户反馈表
            self._create_user_feedback_table()

            # 创建趋势预警配置表
            self._create_trend_alert_config_table()

            # 创建数据源表
            self._create_data_source_table()

            logger.info("✓ System configuration database tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize system configuration tables: {e}")
            raise
            
    def _initialize_strategy_tables(self) -> None:
        """初始化策略配置相关数据表"""
        try:
            logger.info("Initializing strategy configuration database tables...")

            # 创建策略配置表
            self._create_strategy_config_table()

            # 创建策略表
            self._create_strategies_table()

            # 创建策略参数表
            self._create_strategy_parameters_table()

            # 创建策略执行历史表
            self._create_strategy_executions_table()

            # 创建策略信号表
            self._create_strategy_signals_table()

            # 创建模型训练相关表
            self._create_model_training_tables()

            # 创建预测跟踪相关表
            self._create_prediction_tracking_tables()

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

    def _create_strategy_parameters_table(self) -> None:
        """创建策略参数表"""
        sql = """
        CREATE TABLE IF NOT EXISTS strategy_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            param_name TEXT NOT NULL,
            param_value TEXT NOT NULL,
            param_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            min_value TEXT DEFAULT NULL,
            max_value TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE,
            UNIQUE(strategy_id, param_name)
        )
        """
        
        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_strategy_parameters_strategy_id ON strategy_parameters(strategy_id)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_parameters_param_name ON strategy_parameters(param_name)"
        ]
        
        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_strategy_executions_table(self) -> None:
        """创建策略执行历史表"""
        sql = """
        CREATE TABLE IF NOT EXISTS strategy_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_hash TEXT NOT NULL,
            signals_count INTEGER DEFAULT 0,
            execution_duration REAL DEFAULT 0.0,
            success BOOLEAN DEFAULT 1,
            error_message TEXT DEFAULT NULL,
            performance_metrics TEXT DEFAULT '{}',
            FOREIGN KEY (strategy_id) REFERENCES strategies (id) ON DELETE CASCADE
        )
        """
        
        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_strategy_executions_strategy_id ON strategy_executions(strategy_id)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_executions_execution_time ON strategy_executions(execution_time)"
        ]
        
        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_strategy_signals_table(self) -> None:
        """创建策略信号表"""
        sql = """
        CREATE TABLE IF NOT EXISTS strategy_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            signal_type TEXT NOT NULL,
            price REAL NOT NULL,
            confidence REAL NOT NULL,
            reason TEXT DEFAULT '',
            stop_loss REAL DEFAULT NULL,
            take_profit REAL DEFAULT NULL,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (execution_id) REFERENCES strategy_executions (id) ON DELETE CASCADE
        )
        """
        
        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql)
            
        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_strategy_signals_execution_id ON strategy_signals(execution_id)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_signals_timestamp ON strategy_signals(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_signals_signal_type ON strategy_signals(signal_type)"
        ]
        
        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_model_training_tables(self) -> None:
        """创建模型训练相关表"""
        # 训练任务表
        sql_tasks = """
        CREATE TABLE IF NOT EXISTS training_tasks (
            task_id TEXT PRIMARY KEY,
            task_name TEXT NOT NULL,
            task_description TEXT,
            model_type TEXT NOT NULL,
            status TEXT NOT NULL,
            config_json TEXT NOT NULL,
            progress REAL DEFAULT 0.0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
        """
        
        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql_tasks)
            
        indices_tasks = [
            "CREATE INDEX IF NOT EXISTS idx_training_tasks_status ON training_tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_training_tasks_model_type ON training_tasks(model_type)",
            "CREATE INDEX IF NOT EXISTS idx_training_tasks_created_at ON training_tasks(created_at)"
        ]
        
        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices_tasks:
                conn.execute(index_sql)
        
        # 模型版本表
        sql_versions = """
        CREATE TABLE IF NOT EXISTS model_versions (
            version_id TEXT PRIMARY KEY,
            version_number TEXT NOT NULL UNIQUE,
            model_type TEXT NOT NULL,
            model_file_path TEXT NOT NULL,
            training_task_id TEXT,
            performance_metrics_json TEXT,
            config_json TEXT,
            is_current INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            description TEXT,
            FOREIGN KEY (training_task_id) REFERENCES training_tasks(task_id)
        )
        """
        
        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql_versions)
            
        indices_versions = [
            "CREATE INDEX IF NOT EXISTS idx_model_versions_task_id ON model_versions(training_task_id)",
            "CREATE INDEX IF NOT EXISTS idx_model_versions_is_current ON model_versions(is_current)"
        ]
        
        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices_versions:
                conn.execute(index_sql)
        
        # 训练日志表
        sql_logs = """
        CREATE TABLE IF NOT EXISTS training_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_task_id TEXT NOT NULL,
            log_level TEXT NOT NULL,
            log_message TEXT NOT NULL,
            log_data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (training_task_id) REFERENCES training_tasks(task_id)
        )
        """
        
        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql_logs)
            
        indices_logs = [
            "CREATE INDEX IF NOT EXISTS idx_training_logs_task_id ON training_logs(training_task_id)",
            "CREATE INDEX IF NOT EXISTS idx_training_logs_level ON training_logs(log_level)"
        ]
        
        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices_logs:
                conn.execute(index_sql)

    def _create_prediction_tracking_tables(self) -> None:
        """创建预测跟踪相关表"""
        sql_prediction_records = """
        CREATE TABLE IF NOT EXISTS prediction_records (
            record_id TEXT PRIMARY KEY,
            model_version_id TEXT NOT NULL,
            prediction_type TEXT NOT NULL,
            prediction_time TIMESTAMP NOT NULL,
            prediction_result_json TEXT NOT NULL,
            confidence REAL NOT NULL,
            actual_result_json TEXT,
            accuracy REAL,
            calculated_at TIMESTAMP,
            FOREIGN KEY (model_version_id) REFERENCES model_versions(version_id)
        )
        """

        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql_prediction_records)

        indices_prediction_records = [
            "CREATE INDEX IF NOT EXISTS idx_prediction_records_model_version ON prediction_records(model_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_prediction_records_type_time ON prediction_records(prediction_type, prediction_time)",
            "CREATE INDEX IF NOT EXISTS idx_prediction_records_time ON prediction_records(prediction_time)"
        ]

        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices_prediction_records:
                conn.execute(index_sql)

        sql_accuracy_statistics = """
        CREATE TABLE IF NOT EXISTS accuracy_statistics (
            stat_id TEXT PRIMARY KEY,
            model_version_id TEXT NOT NULL,
            prediction_type TEXT NOT NULL,
            time_period TEXT NOT NULL,
            total_predictions INTEGER DEFAULT 0,
            correct_predictions INTEGER DEFAULT 0,
            accuracy_rate REAL DEFAULT 0.0,
            avg_confidence REAL DEFAULT 0.0,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (model_version_id) REFERENCES model_versions(version_id),
            UNIQUE(model_version_id, prediction_type, time_period)
        )
        """

        with self.get_connection("strategy_sqlite") as conn:
            conn.execute(sql_accuracy_statistics)

        indices_accuracy_statistics = [
            "CREATE INDEX IF NOT EXISTS idx_accuracy_statistics_model_version ON accuracy_statistics(model_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_accuracy_statistics_type_period ON accuracy_statistics(prediction_type, time_period)"
        ]

        with self.get_connection("strategy_sqlite") as conn:
            for index_sql in indices_accuracy_statistics:
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

    def _initialize_default_ai_strategies(self) -> None:
        """初始化默认AI策略记录"""
        try:
            logger.info("Initializing default AI strategies...")
            
            # 定义默认策略配置
            default_strategies = [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "name": "动量策略",
                    "description": "基于价格动量和趋势的选股策略",
                    "strategy_type": "momentum",
                    "parameters": json.dumps({"lookback_period": 20, "momentum_threshold": 0.05}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "momentum,trend",
                    "status": "active"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "name": "价值策略",
                    "description": "基于估值指标的选股策略",
                    "strategy_type": "value",
                    "parameters": json.dumps({"pe_threshold": 15, "pb_threshold": 2.0}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "value,valuation",
                    "status": "active"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440003",
                    "name": "成长策略",
                    "description": "基于成长性指标的选股策略",
                    "strategy_type": "growth",
                    "parameters": json.dumps({"revenue_growth_threshold": 0.2, "earnings_growth_threshold": 0.15}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "growth,revenue",
                    "status": "active"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440004",
                    "name": "质量策略",
                    "description": "基于财务质量的选股策略",
                    "strategy_type": "quality",
                    "parameters": json.dumps({"roe_threshold": 0.15, "debt_to_equity_threshold": 0.5}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "quality,financial",
                    "status": "active"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440005",
                    "name": "股息策略",
                    "description": "基于股息收益的选股策略",
                    "strategy_type": "dividend",
                    "parameters": json.dumps({"dividend_yield_threshold": 0.03, "payout_ratio_threshold": 0.6}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "dividend,yield",
                    "status": "active"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440006",
                    "name": "技术分析策略",
                    "description": "基于技术指标的选股策略",
                    "strategy_type": "technical",
                    "parameters": json.dumps({"indicators": ["MA", "MACD", "RSI", "KDJ"]}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "technical,indicators",
                    "status": "active"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440007",
                    "name": "量化策略",
                    "description": "基于多因子模型的量化选股策略",
                    "strategy_type": "quantitative",
                    "parameters": json.dumps({"factors": ["momentum", "value", "quality", "growth"]}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "quantitative,factors",
                    "status": "active"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440008",
                    "name": "混合策略",
                    "description": "综合多种策略的混合选股策略",
                    "strategy_type": "hybrid",
                    "parameters": json.dumps({"strategies": ["momentum", "value", "quality"]}),
                    "weight_config": json.dumps({"equal_weight": True}),
                    "risk_config": json.dumps({"max_position_size": 0.1}),
                    "performance_metrics": json.dumps({}),
                    "is_active": True,
                    "version": 1,
                    "created_by": "system",
                    "tags": "hybrid,combined",
                    "status": "active"
                }
            ]
            
            # 插入默认策略（如果不存在）
            with self.get_connection("analytics_duckdb") as conn:
                for strategy in default_strategies:
                    # 检查策略是否已存在
                    check_sql = "SELECT id FROM ai_strategies WHERE id = ?"
                    result = conn.execute(check_sql, (strategy["id"],))
                    existing = result[0] if result else None
                    
                    if not existing:
                        # 插入新策略
                        insert_sql = """
                        INSERT INTO ai_strategies (
                            id, name, description, strategy_type, parameters,
                            weight_config, risk_config, performance_metrics,
                            is_active, version, created_by, tags, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        conn.execute(insert_sql, (
                            strategy["id"],
                            strategy["name"],
                            strategy["description"],
                            strategy["strategy_type"],
                            strategy["parameters"],
                            strategy["weight_config"],
                            strategy["risk_config"],
                            strategy["performance_metrics"],
                            strategy["is_active"],
                            strategy["version"],
                            strategy["created_by"],
                            strategy["tags"],
                            strategy["status"]
                        ))
                        logger.info(f"Created default strategy: {strategy['name']} ({strategy['strategy_type']})")
                    else:
                        logger.debug(f"Strategy already exists: {strategy['name']} ({strategy['strategy_type']})")
            
            logger.info("✓ Default AI strategies initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize default AI strategies: {e}")
            raise

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
            asset_type VARCHAR(50) DEFAULT 'stock_a',
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
            "CREATE INDEX IF NOT EXISTS idx_ai_results_risk ON ai_selection_results(risk_level)",
            "CREATE INDEX IF NOT EXISTS idx_ai_results_asset_type ON ai_selection_results(asset_type)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"创建索引失败（可能已存在）: {e}")

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
            asset_type VARCHAR(50) DEFAULT 'stock_a',
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
            "CREATE INDEX IF NOT EXISTS idx_ai_explain_factor ON ai_explanations(factor_name)",
            "CREATE INDEX IF NOT EXISTS idx_ai_explain_asset_type ON ai_explanations(asset_type)"
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
            asset_type VARCHAR(50) DEFAULT 'stock_a',
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
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_style ON user_profiles(investment_style)",
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_asset_type ON user_profiles(asset_type)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                conn.execute(index_sql)

    def _create_user_preferences_table(self) -> None:
        """创建用户偏好表"""
        sql = """
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(100) NOT NULL,
            preference_key VARCHAR(100) NOT NULL,
            preference_value TEXT NOT NULL,
            asset_type VARCHAR(50) DEFAULT 'stock_a',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, preference_key, asset_type)
        )
        """

        with self.get_connection("factorweave_system_sqlite") as conn:
            conn.execute(sql)

        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_preferences_key ON user_preferences(preference_key)",
            "CREATE INDEX IF NOT EXISTS idx_user_preferences_asset_type ON user_preferences(asset_type)"
        ]
        
        with self.get_connection("factorweave_system_sqlite") as conn:
            for index_sql in indices:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"创建索引失败（可能已存在）: {e}")

    def _create_user_feedback_table(self) -> None:
        """创建用户反馈表"""
        sql = """
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(100) NOT NULL,
            recommendation_id VARCHAR(100) NOT NULL,
            feedback_type VARCHAR(50) NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            asset_type VARCHAR(50) DEFAULT 'stock_a',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        with self.get_connection("factorweave_system_sqlite") as conn:
            conn.execute(sql)

        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_user_feedback_user_id ON user_feedback(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_feedback_recommendation_id ON user_feedback(recommendation_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_feedback_feedback_type ON user_feedback(feedback_type)",
            "CREATE INDEX IF NOT EXISTS idx_user_feedback_timestamp ON user_feedback(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_user_feedback_asset_type ON user_feedback(asset_type)"
        ]
        
        with self.get_connection("factorweave_system_sqlite") as conn:
            for index_sql in indices:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"创建索引失败（可能已存在）: {e}")

    def _create_trend_alert_config_table(self) -> None:
        """创建趋势预警配置表"""
        sql = """
        CREATE TABLE IF NOT EXISTS trend_alert_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL,
            config_value TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        with self.get_connection("factorweave_system_sqlite") as conn:
            conn.execute(sql)

        indices = [
            "CREATE INDEX IF NOT EXISTS idx_trend_alert_config_key ON trend_alert_config(config_key)",
            "CREATE INDEX IF NOT EXISTS idx_trend_alert_config_active ON trend_alert_config(is_active)"
        ]

        with self.get_connection("factorweave_system_sqlite") as conn:
            for index_sql in indices:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"创建索引失败（可能已存在）: {e}")

    def _create_data_source_table(self) -> None:
        """创建数据源表"""
        sql = """
        CREATE TABLE IF NOT EXISTS data_source (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            config TEXT,
            is_active INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 50,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        with self.get_connection("factorweave_system_sqlite") as conn:
            conn.execute(sql)

        indices = [
            "CREATE INDEX IF NOT EXISTS idx_data_source_name ON data_source(name)",
            "CREATE INDEX IF NOT EXISTS idx_data_source_type ON data_source(type)",
            "CREATE INDEX IF NOT EXISTS idx_data_source_active ON data_source(is_active)"
        ]

        with self.get_connection("factorweave_system_sqlite") as conn:
            for index_sql in indices:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"创建索引失败（可能已存在）: {e}")

    def save_trend_alert_config(self, config_key: str, config_value: dict) -> bool:
        """保存趋势预警配置"""
        try:
            import json
            value_json = json.dumps(config_value, ensure_ascii=False)

            sql = """
            REPLACE INTO trend_alert_config (config_key, config_value, is_active, created_at, updated_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """

            with self.get_connection("factorweave_system_sqlite") as conn:
                conn.execute(sql, (config_key, value_json))

            logger.info(f"趋势预警配置已保存: {config_key}")
            return True
        except Exception as e:
            logger.error(f"保存趋势预警配置失败: {e}")
            return False

    def get_trend_alert_config(self, config_key: str) -> dict:
        """获取趋势预警配置"""
        try:
            import json

            sql = """
            SELECT config_value FROM trend_alert_config
            WHERE config_key = ? AND is_active = 1
            """

            with self.get_connection("factorweave_system_sqlite") as conn:
                result = conn.execute(sql, (config_key,))

            if result and len(result) > 0:
                return json.loads(result[0][0])
            return {}
        except Exception as e:
            logger.error(f"获取趋势预警配置失败: {e}")
            return {}

    def get_data_source_stats(self) -> dict:
        """获取数据源统计信息"""
        try:
            sql = """
            SELECT COUNT(*) as total, SUM(is_active) as active
            FROM data_source
            """

            with self.get_connection("factorweave_system_sqlite") as conn:
                result = conn.execute(sql)

            if result and len(result) > 0:
                total = result[0][0] or 0
                active = result[0][1] or 0
                return {
                    'total': total,
                    'active': active,
                    'active_rate': (active / total) if total > 0 else 0.0
                }
            return {'total': 0, 'active': 0, 'active_rate': 0.0}
        except Exception as e:
            logger.error(f"获取数据源统计失败: {e}")
            return {'total': 0, 'active': 0, 'active_rate': 0.0}

    def _create_user_interactions_table(self) -> None:
        """创建用户交互表"""
        sql = """
        CREATE TABLE IF NOT EXISTS user_interactions (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            item_id VARCHAR(100) NOT NULL,
            interaction_type VARCHAR(50) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            duration DECIMAL(10,2),
            rating DECIMAL(5,4),
            context JSON,
            asset_type VARCHAR(50) DEFAULT 'stock_a',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql)

        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_interactions_item_id ON user_interactions(item_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_interactions_type ON user_interactions(interaction_type)",
            "CREATE INDEX IF NOT EXISTS idx_user_interactions_timestamp ON user_interactions(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_user_interactions_asset_type ON user_interactions(asset_type)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"创建索引失败（可能已存在）: {e}")

    def _create_content_items_table(self) -> None:
        """创建内容项表"""
        sql = """
        CREATE TABLE IF NOT EXISTS content_items (
            id VARCHAR(36) PRIMARY KEY,
            item_id VARCHAR(100) NOT NULL UNIQUE,
            item_type VARCHAR(50) NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            tags JSON,
            categories JSON,
            keywords JSON,
            view_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            rating DECIMAL(5,4) DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            feature_vector JSON,
            metadata JSON,
            asset_type VARCHAR(50) DEFAULT 'stock_a'
        )
        """

        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql)

        # 创建索引
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_content_items_item_id ON content_items(item_id)",
            "CREATE INDEX IF NOT EXISTS idx_content_items_type ON content_items(item_type)",
            "CREATE INDEX IF NOT EXISTS idx_content_items_asset_type ON content_items(asset_type)",
            "CREATE INDEX IF NOT EXISTS idx_content_items_rating ON content_items(rating DESC)"
        ]
        
        with self.get_connection("analytics_duckdb") as conn:
            for index_sql in indices:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"创建索引失败（可能已存在）: {e}")

    def get_ai_strategy(self, strategy_identifier: str) -> Optional[Dict[str, Any]]:
        """
        根据策略类型或策略ID获取AI策略
        
        Args:
            strategy_identifier: 策略类型（如 "technical", "momentum" 等）或策略ID（UUID）
            
        Returns:
            策略配置字典，如果不存在则返回None
        """
        # 判断传入的是策略ID（UUID）还是策略类型
        # 策略ID通常是36字符的UUID，策略类型是简短的字符串
        if len(strategy_identifier) == 36 and '-' in strategy_identifier:
            # 传入的是策略ID，使用id字段查询
            sql = """
            SELECT * FROM ai_strategies 
            WHERE id = ? AND is_active = TRUE
            """
            params = (strategy_identifier,)
        else:
            # 传入的是策略类型，使用strategy_type字段查询
            sql = """
            SELECT * FROM ai_strategies 
            WHERE strategy_type = ? AND is_active = TRUE
            ORDER BY 
                CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT 1
            """
            params = (strategy_identifier,)
        
        with self.get_connection("analytics_duckdb") as conn:
            results = conn.execute(sql, params)
            
        if results and len(results) > 0:
            result = results[0]
            strategy = dict(result)
            # 解析JSON字段
            if strategy.get('parameters'):
                strategy['parameters'] = json.loads(strategy['parameters'])
            if strategy.get('weight_config'):
                strategy['weight_config'] = json.loads(strategy['weight_config'])
            if strategy.get('risk_config'):
                strategy['risk_config'] = json.loads(strategy['risk_config'])
            if strategy.get('performance_metrics'):
                strategy['performance_metrics'] = json.loads(strategy['performance_metrics'])
            logger.debug(f"返回策略: {strategy['name']} (ID: {strategy['id']}, status: {strategy['status']}, is_active: {strategy['is_active']})")
            return strategy
        
        # 如果找不到策略，且传入的是策略类型，则尝试创建默认策略
        if len(strategy_identifier) != 36:
            logger.warning(f"未找到策略类型 '{strategy_identifier}' 的活跃策略，尝试创建默认策略")
            try:
                default_strategy = self._create_and_save_default_strategy(strategy_identifier)
                if default_strategy:
                    logger.info(f"成功创建默认策略: {default_strategy['name']} (ID: {default_strategy['id']})")
                    return default_strategy
            except Exception as e:
                logger.error(f"创建默认策略失败: {e}")
        else:
            logger.warning(f"未找到策略ID '{strategy_identifier}'")
        
        return None

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

    def update_ai_strategy(self, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
        """
        更新AI选股策略
        
        Args:
            strategy_id: 策略ID
            strategy_data: 策略数据
            
        Returns:
            是否更新成功
        """
        sql = """
        UPDATE ai_strategies SET
            name = ?,
            description = ?,
            strategy_type = ?,
            parameters = ?,
            weight_config = ?,
            risk_config = ?,
            performance_metrics = ?,
            tags = ?,
            status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """
        
        params = (
            strategy_data.get('name', ''),
            strategy_data.get('description', ''),
            strategy_data.get('strategy_type', 'comprehensive'),
            json.dumps(strategy_data.get('parameters', {})),
            json.dumps(strategy_data.get('weight_config', {})),
            json.dumps(strategy_data.get('risk_config', {})),
            json.dumps(strategy_data.get('performance_metrics', {})),
            strategy_data.get('tags', ''),
            strategy_data.get('status', 'draft'),
            strategy_id
        )
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql, params)
            
        logger.info(f"Updated AI strategy: {strategy_id}")
        return True

    def get_all_ai_strategies(self) -> List[Dict[str, Any]]:
        """
        获取所有AI选股策略
        
        Returns:
            策略列表
        """
        sql = """
        SELECT * FROM ai_strategies 
        WHERE is_active = TRUE
        ORDER BY created_at DESC
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            results = conn.execute(sql)
            
        strategies = []
        if results:
            for result in results:
                strategy = dict(result)
                # 解析JSON字段
                if strategy.get('parameters'):
                    strategy['parameters'] = json.loads(strategy['parameters'])
                if strategy.get('weight_config'):
                    strategy['weight_config'] = json.loads(strategy['weight_config'])
                if strategy.get('risk_config'):
                    strategy['risk_config'] = json.loads(strategy['risk_config'])
                if strategy.get('performance_metrics'):
                    strategy['performance_metrics'] = json.loads(strategy['performance_metrics'])
                strategies.append(strategy)
        
        logger.debug(f"返回 {len(strategies)} 个策略")
        return strategies

    def delete_ai_strategy(self, strategy_id: str) -> bool:
        """
        删除AI选股策略（软删除，设置is_active为FALSE）
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否删除成功
        """
        sql = """
        UPDATE ai_strategies SET
            is_active = FALSE,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql, (strategy_id,))
            
        logger.info(f"Deleted AI strategy: {strategy_id}")
        return True

    def save_ai_selection_results(self, results: List[Dict[str, Any]]) -> None:
        """
        保存AI选股结果
        
        Args:
            results: 选股结果列表
        """
        if not results:
            return
            
        def convert_to_serializable(obj):
            """将不可序列化的对象转换为可序列化的格式"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            else:
                return obj
        
        sql = """
        INSERT OR REPLACE INTO ai_selection_results (
            id, strategy_id, selection_date, stock_code, stock_name, industry,
            selection_reason, score, weight, confidence, risk_level,
            expected_return, volatility, sharpe_ratio, max_drawdown,
            market_cap, pe_ratio, pb_ratio, turnover_rate, backtested
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # 准备批量插入的参数
        params_list = []
        for result in results:
            result_id = result.get('id', str(uuid.uuid4()))
            selection_reason = result.get('selection_reason', {})
            selection_reason = convert_to_serializable(selection_reason)
            
            params = (
                result_id,
                result.get('strategy_id'),
                result.get('selection_date'),
                result.get('stock_code'),
                result.get('stock_name'),
                result.get('industry'),
                json.dumps(selection_reason),
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
            params_list.append(params)
        
        # 使用批量插入
        with self.get_connection("analytics_duckdb") as conn:
            conn.executemany(sql, params_list)
                
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
            rows = conn.execute(sql, params)
            
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
            rows = conn.execute(sql, (strategy_id, limit))
            
        results = []
        for row in rows:
            result = dict(row)
            result['selection_reason'] = json.loads(result['selection_reason']) if result['selection_reason'] else {}
            results.append(result)
            
        return results

    def get_selection_results_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        按日期范围查询选股结果
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制
            
        Returns:
            选股结果列表
        """
        sql = """
        SELECT * FROM ai_selection_results 
        WHERE selection_date BETWEEN ? AND ?
        ORDER BY selection_date DESC, score DESC
        LIMIT ?
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            results = conn.execute(sql, (start_date.isoformat(), end_date.isoformat(), limit))
            
        for result in results:
            result['selection_reason'] = json.loads(result['selection_reason']) if result['selection_reason'] else {}
            
        return results

    def get_selection_result_by_result_id(self, result_id: str) -> List[Dict[str, Any]]:
        """
        按result_id查询选股结果（返回同一result_id的所有股票）
        
        Args:
            result_id: 结果ID（前36位）
            
        Returns:
            选股结果列表（同一result_id的所有股票记录）
        """
        sql = """
        SELECT * FROM ai_selection_results 
        WHERE SUBSTR(id, 1, 36) = ?
        ORDER BY score DESC
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            results = conn.execute(sql, (result_id,))
            
        for result in results:
            result['selection_reason'] = json.loads(result['selection_reason']) if result['selection_reason'] else {}
            
        return results

    def get_all_selection_results(
        self,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取所有历史选股记录（分页）
        
        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            
        Returns:
            包含数据和分页信息的字典：
            {
                'data': List[Dict],  # 选股记录列表
                'total': int,         # 总记录数
                'page': int,          # 当前页码
                'page_size': int,      # 每页数量
                'total_pages': int     # 总页数
            }
        """
        offset = (page - 1) * page_size
        
        # 查询总数
        count_sql = """
        SELECT COUNT(DISTINCT SUBSTR(id, 1, 36)) as total
        FROM ai_selection_results
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            count_result = conn.execute(count_sql)
            total_rows = count_result[0]['total'] if count_result else 0
        
        # 查询数据（按result_id分组）
        sql = """
        SELECT 
            SUBSTR(id, 1, 36) as result_id,
            strategy_id,
            MIN(selection_date) as selection_date,
            COUNT(*) as stock_count,
            AVG(score) as avg_score,
            MIN(score) as min_score,
            MAX(score) as max_score
        FROM ai_selection_results
        GROUP BY SUBSTR(id, 1, 36), strategy_id
        ORDER BY selection_date DESC
        LIMIT ? OFFSET ?
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            results = conn.execute(sql, (page_size, offset))
        
        total_pages = (total_rows + page_size - 1) // page_size
        
        return {
            'data': results,
            'total': total_rows,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }

    def get_strategy_by_id(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        获取策略配置
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            策略配置字典，如果不存在则返回None
        """
        sql = """
        SELECT * FROM ai_strategies 
        WHERE id = ?
        """
        
        with self.get_connection("analytics_duckdb") as conn:
            results = conn.execute(sql, (strategy_id,))
            
        if results and len(results) > 0:
            result = results[0]
            # 解析JSON字段
            if result.get('parameters'):
                result['parameters'] = json.loads(result['parameters'])
            if result.get('weight_config'):
                result['weight_config'] = json.loads(result['weight_config'])
            if result.get('risk_config'):
                result['risk_config'] = json.loads(result['risk_config'])
            if result.get('performance_metrics'):
                result['performance_metrics'] = json.loads(result['performance_metrics'])
            return result
        
        return None

    def compare_selection_results(self, result_ids: List[str]) -> Dict[str, Any]:
        """
        对比多个选股结果
        
        Args:
            result_ids: 结果ID列表
            
        Returns:
            对比报告字典：
            {
                'results': List[Dict],  # 各个结果的详细信息
                'comparison': Dict,      # 对比指标
                'overlap': Dict,         # 股票重叠度分析
                'metrics': Dict          # 性能指标对比
            }
        """
        # 获取所有结果的数据
        all_results = {}
        for result_id in result_ids:
            results = self.get_selection_result_by_result_id(result_id)
            if results:
                all_results[result_id] = results
        
        if not all_results:
            return {
                'results': [],
                'comparison': {},
                'overlap': {},
                'metrics': {}
            }
        
        # 计算对比指标
        comparison = {
            'stock_counts': {},
            'avg_scores': {},
            'score_ranges': {},
            'risk_levels': {},
            'date_ranges': {}
        }
        
        for result_id, results in all_results.items():
            comparison['stock_counts'][result_id] = len(results)
            comparison['avg_scores'][result_id] = sum(r['score'] for r in results) / len(results)
            comparison['score_ranges'][result_id] = {
                'min': min(r['score'] for r in results),
                'max': max(r['score'] for r in results)
            }
            comparison['risk_levels'][result_id] = [r['risk_level'] for r in results if r['risk_level']]
            comparison['date_ranges'][result_id] = results[0]['selection_date'] if results else None
        
        # 计算股票重叠度
        stock_sets = {}
        for result_id, results in all_results.items():
            stock_sets[result_id] = set(r['stock_code'] for r in results)
        
        overlap = {}
        result_id_list = list(all_results.keys())
        for i in range(len(result_id_list)):
            for j in range(i + 1, len(result_id_list)):
                id1 = result_id_list[i]
                id2 = result_id_list[j]
                intersection = stock_sets[id1] & stock_sets[id2]
                union = stock_sets[id1] | stock_sets[id2]
                overlap_ratio = len(intersection) / len(union) if union else 0
                
                overlap[f"{id1}_vs_{id2}"] = {
                    'intersection': list(intersection),
                    'union': list(union),
                    'overlap_ratio': overlap_ratio,
                    'intersection_count': len(intersection),
                    'union_count': len(union)
                }
        
        # 性能指标对比
        metrics = {}
        for result_id, results in all_results.items():
            if results and results[0].get('selection_reason', {}).get('criteria'):
                criteria = results[0]['selection_reason']['criteria']
                metrics[result_id] = {
                    'strategy_type': criteria.get('strategy_type'),
                    'risk_level': criteria.get('risk_level'),
                    'max_stocks': criteria.get('max_stocks'),
                    'market_cap_range': {
                        'min': criteria.get('market_cap_min'),
                        'max': criteria.get('market_cap_max')
                    }
                }
        
        return {
            'results': all_results,
            'comparison': comparison,
            'overlap': overlap,
            'metrics': metrics
        }

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
        保存AI选股解释（优化版 - 使用executemany批量插入）
        
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
        
        # 准备批量插入的参数
        params_list = []
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
            params_list.append(params)
        
        # 使用批量插入
        with self.get_connection("analytics_duckdb") as conn:
            conn.executemany(sql, params_list)
                
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
            rows = conn.execute(sql, (user_id,))
            
        if not rows or len(rows) == 0:
            return None
            
        profile = rows[0]
        profile['preferred_industries'] = profile['preferred_industries'].split(',') if profile['preferred_industries'] else []
        profile['excluded_industries'] = profile['excluded_industries'].split(',') if profile['excluded_industries'] else []
        profile['custom_constraints'] = json.loads(profile['custom_constraints']) if profile['custom_constraints'] else {}
        profile['performance_history'] = json.loads(profile['performance_history']) if profile['performance_history'] else {}
        profile['feedback_data'] = json.loads(profile['feedback_data']) if profile['feedback_data'] else {}
        
        return profile

    def get_user_interactions(self, user_id: Optional[str] = None, item_id: Optional[str] = None, 
                           interaction_type: Optional[str] = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        获取用户交互数据
        
        Args:
            user_id: 用户ID（可选）
            item_id: 内容项ID（可选）
            interaction_type: 交互类型（可选）
            limit: 返回的最大记录数（可选）
            
        Returns:
            用户交互数据列表
        """
        sql = "SELECT * FROM user_interactions WHERE 1=1"
        params = []
        
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        
        if item_id:
            sql += " AND item_id = ?"
            params.append(item_id)
        
        if interaction_type:
            sql += " AND interaction_type = ?"
            params.append(interaction_type)
        
        sql += " ORDER BY timestamp DESC"
        
        if limit:
            sql += f" LIMIT {limit}"
        
        with self.get_connection("analytics_duckdb") as conn:
            rows = conn.execute(sql, tuple(params))
        
        results = []
        for row in rows:
            interaction = dict(row)
            interaction['context'] = json.loads(interaction['context']) if interaction['context'] else {}
            results.append(interaction)
        
        return results

    def get_content_items(self, item_id: Optional[str] = None, item_type: Optional[str] = None,
                        limit: int = None) -> List[Dict[str, Any]]:
        """
        获取内容项数据
        
        Args:
            item_id: 内容项ID（可选）
            item_type: 内容类型（可选）
            limit: 返回的最大记录数（可选）
            
        Returns:
            内容项数据列表
        """
        sql = "SELECT * FROM content_items WHERE 1=1"
        params = []
        
        if item_id:
            sql += " AND item_id = ?"
            params.append(item_id)
        
        if item_type:
            sql += " AND item_type = ?"
            params.append(item_type)
        
        sql += " ORDER BY created_at DESC"
        
        if limit:
            sql += f" LIMIT {limit}"
        
        with self.get_connection("analytics_duckdb") as conn:
            rows = conn.execute(sql, tuple(params))
        
        results = []
        for row in rows:
            item = dict(row)
            item['tags'] = json.loads(item['tags']) if item['tags'] else []
            item['categories'] = json.loads(item['categories']) if item['categories'] else []
            item['keywords'] = json.loads(item['keywords']) if item['keywords'] else []
            item['feature_vector'] = json.loads(item['feature_vector']) if item['feature_vector'] else None
            item['metadata'] = json.loads(item['metadata']) if item['metadata'] else {}
            results.append(item)
        
        return results

    def save_user_interaction(self, interaction_data: Dict[str, Any]) -> str:
        """
        保存用户交互数据
        
        Args:
            interaction_data: 交互数据
            
        Returns:
            交互ID
        """
        interaction_id = interaction_data.get('id', str(uuid.uuid4()))
        
        sql = """
        INSERT OR REPLACE INTO user_interactions (
            id, user_id, item_id, interaction_type, timestamp, duration, rating, context, asset_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            interaction_id,
            interaction_data.get('user_id'),
            interaction_data.get('item_id'),
            interaction_data.get('interaction_type'),
            interaction_data.get('timestamp'),
            interaction_data.get('duration'),
            interaction_data.get('rating'),
            json.dumps(interaction_data.get('context', {})),
            interaction_data.get('asset_type', 'stock_a')
        )
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql, params)
            
        logger.info(f"Saved user interaction: {interaction_id}")
        return interaction_id

    def save_content_item(self, item_data: Dict[str, Any]) -> str:
        """
        保存内容项数据
        
        Args:
            item_data: 内容项数据
            
        Returns:
            内容项ID
        """
        item_id = item_data.get('item_id', str(uuid.uuid4()))
        id_value = item_data.get('id') or str(uuid.uuid4())
        
        sql = """
        INSERT INTO content_items (
            id, item_id, item_type, title, description, tags, categories, keywords,
            view_count, like_count, share_count, rating, created_at, updated_at,
            feature_vector, metadata, asset_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (item_id) DO UPDATE SET
            item_type = EXCLUDED.item_type,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            tags = EXCLUDED.tags,
            categories = EXCLUDED.categories,
            keywords = EXCLUDED.keywords,
            view_count = EXCLUDED.view_count,
            like_count = EXCLUDED.like_count,
            share_count = EXCLUDED.share_count,
            rating = EXCLUDED.rating,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at,
            feature_vector = EXCLUDED.feature_vector,
            metadata = EXCLUDED.metadata,
            asset_type = EXCLUDED.asset_type
        """
        
        params = (
            id_value,
            item_id,
            item_data.get('item_type'),
            item_data.get('title'),
            item_data.get('description'),
            json.dumps(_serialize_for_json(item_data.get('tags', []))),
            json.dumps(_serialize_for_json(item_data.get('categories', []))),
            json.dumps(_serialize_for_json(item_data.get('keywords', []))),
            item_data.get('view_count',0),
            item_data.get('like_count', 0),
            item_data.get('share_count', 0),
            item_data.get('rating', 0.0),
            item_data.get('created_at'),
            item_data.get('updated_at'),
            json.dumps(_serialize_for_json(item_data.get('feature_vector'))),
            json.dumps(_serialize_for_json(item_data.get('metadata', {}))),
            item_data.get('asset_type', 'stock_a')
        )
        
        with self.get_connection("analytics_duckdb") as conn:
            conn.execute(sql, params)
            
        return item_id

    def get_all_user_profiles(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        获取所有用户画像
        
        Args:
            limit: 返回的最大记录数（可选）
            
        Returns:
            用户画像数据列表
        """
        sql = "SELECT * FROM user_profiles WHERE is_active = TRUE ORDER BY updated_at DESC"
        
        if limit:
            sql += f" LIMIT {limit}"
        
        with self.get_connection("analytics_duckdb") as conn:
            rows = conn.execute(sql).fetchall()
        
        results = []
        for row in rows:
            profile = dict(row)
            profile['preferred_industries'] = profile['preferred_industries'].split(',') if profile['preferred_industries'] else []
            profile['excluded_industries'] = profile['excluded_industries'].split(',') if profile['excluded_industries'] else []
            profile['custom_constraints'] = json.loads(profile['custom_constraints']) if profile['custom_constraints'] else {}
            profile['performance_history'] = json.loads(profile['performance_history']) if profile['performance_history'] else {}
            profile['feedback_data'] = json.loads(profile['feedback_data']) if profile['feedback_data'] else {}
            results.append(profile)
        
        return results

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
        profile_id = existing['id'] if existing and existing.get('id') else str(uuid.uuid4())
        
        sql = """
        INSERT INTO user_profiles (
            id, user_id, risk_tolerance, investment_horizon, investment_style,
            preferred_industries, excluded_industries, max_position_size,
            min_market_cap, max_pe_ratio, max_pb_ratio, max_volatility,
            preferred_stock_count, rebalance_frequency, custom_constraints,
            performance_history, feedback_data, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id) DO UPDATE SET
            risk_tolerance = EXCLUDED.risk_tolerance,
            investment_horizon = EXCLUDED.investment_horizon,
            investment_style = EXCLUDED.investment_style,
            preferred_industries = EXCLUDED.preferred_industries,
            excluded_industries = EXCLUDED.excluded_industries,
            max_position_size = EXCLUDED.max_position_size,
            min_market_cap = EXCLUDED.min_market_cap,
            max_pe_ratio = EXCLUDED.max_pe_ratio,
            max_pb_ratio = EXCLUDED.max_pb_ratio,
            max_volatility = EXCLUDED.max_volatility,
            preferred_stock_count = EXCLUDED.preferred_stock_count,
            rebalance_frequency = EXCLUDED.rebalance_frequency,
            custom_constraints = EXCLUDED.custom_constraints,
            performance_history = EXCLUDED.performance_history,
            feedback_data = EXCLUDED.feedback_data,
            is_active = EXCLUDED.is_active
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

    def register_strategy(self, strategy_class: type, metadata: Dict[str, Any]) -> int:
        """
        注册策略到数据库

        Args:
            strategy_class: 策略类
            metadata: 策略元数据

        Returns:
            策略ID
        """
        try:
            sql = """
            INSERT INTO strategies (name, strategy_type, version, author, description, category, metadata, class_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                strategy_type = excluded.strategy_type,
                version = excluded.version,
                author = excluded.author,
                description = excluded.description,
                category = excluded.category,
                metadata = excluded.metadata,
                class_path = excluded.class_path,
                updated_at = CURRENT_TIMESTAMP
            """

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (
                    metadata['name'],
                    metadata['strategy_type'],
                    metadata.get('version', '1.0.0'),
                    metadata.get('author', ''),
                    metadata.get('description', ''),
                    metadata.get('category', ''),
                    json.dumps(metadata),  # 存储完整的metadata字典
                    f"{strategy_class.__module__}.{strategy_class.__name__}"
                ))
                conn.commit()

                strategy_id = cursor.lastrowid
                logger.info(f"策略注册成功: {metadata['name']} (ID: {strategy_id})")
                return strategy_id

        except Exception as e:
            logger.error(f"策略注册失败: {e}")
            raise

    def get_strategy_info(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """
        获取策略信息

        Args:
            strategy_id: 策略ID

        Returns:
            策略信息字典
        """
        try:
            sql = """SELECT id, name, strategy_type, version, author, description,
                           category, created_at, updated_at, is_active, metadata, class_path
                    FROM strategies WHERE id = ?"""

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (strategy_id,))
                result = cursor.fetchone()

            if result:
                result_dict = dict(result)
                return {
                    'id': result_dict['id'],
                    'name': result_dict['name'],
                    'strategy_type': result_dict['strategy_type'],
                    'version': result_dict['version'],
                    'author': result_dict['author'],
                    'description': result_dict['description'],
                    'category': result_dict['category'],
                    'created_at': result_dict['created_at'],
                    'updated_at': result_dict['updated_at'],
                    'is_active': result_dict['is_active'],
                    'metadata': self._safe_json_parse(result_dict['metadata']),
                    'class_path': result_dict['class_path']
                }
            return None

        except Exception as e:
            logger.error(f"获取策略信息失败: {e}")
            return None

    def list_strategies(self, strategy_type: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        列出策略

        Args:
            strategy_type: 策略类型过滤
            is_active: 是否活跃过滤

        Returns:
            策略列表
        """
        try:
            sql = """SELECT id, name, strategy_type, version, author, description,
                           category, created_at, updated_at, is_active, metadata, class_path
                    FROM strategies WHERE 1=1"""
            params = []

            if strategy_type:
                sql += " AND strategy_type = ?"
                params.append(strategy_type)

            if is_active is not None:
                sql += " AND is_active = ?"
                params.append(is_active)

            sql += " ORDER BY created_at DESC"

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                results = cursor.fetchall()

            strategies = []
            for result in results:
                result_dict = dict(result)
                strategies.append({
                    'id': result_dict['id'],
                    'name': result_dict['name'],
                    'strategy_type': result_dict['strategy_type'],
                    'version': result_dict['version'],
                    'author': result_dict['author'],
                    'description': result_dict['description'],
                    'category': result_dict['category'],
                    'created_at': result_dict['created_at'],
                    'updated_at': result_dict['updated_at'],
                    'is_active': result_dict['is_active'],
                    'metadata': self._safe_json_parse(result_dict['metadata']),
                    'class_path': result_dict['class_path']
                })

            return strategies

        except Exception as e:
            logger.error(f"列出策略失败: {e}")
            return []

    def save_strategy_parameters(self, strategy_id: int, parameters: Dict[str, Any]) -> bool:
        """
        保存策略参数

        Args:
            strategy_id: 策略ID
            parameters: 参数字典

        Returns:
            是否保存成功
        """
        try:
            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()

                for param_name, param_value in parameters.items():
                    param_type = type(param_value).__name__
                    param_value_str = self._serialize_value(param_value)

                    sql = """
                    INSERT INTO strategy_parameters (strategy_id, param_name, param_value, param_type)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(strategy_id, param_name) DO UPDATE SET
                        param_value = excluded.param_value,
                        param_type = excluded.param_type
                    """
                    cursor.execute(sql, (strategy_id, param_name, param_value_str, param_type))

                conn.commit()
                logger.info(f"策略参数保存成功: strategy_id={strategy_id}, 参数数={len(parameters)}")
                return True

        except Exception as e:
            logger.error(f"保存策略参数失败: {e}")
            return False

    def get_strategy_parameters(self, strategy_id: int) -> Dict[str, Any]:
        """
        获取策略参数

        Args:
            strategy_id: 策略ID

        Returns:
            参数字典
        """
        try:
            sql = "SELECT param_name, param_value, param_type FROM strategy_parameters WHERE strategy_id = ?"

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (strategy_id,))
                results = cursor.fetchall()

            parameters = {}
            for result in results:
                param_name, param_value_str, param_type = result
                parameters[param_name] = self._deserialize_value(param_value_str, param_type)

            return parameters

        except Exception as e:
            logger.error(f"获取策略参数失败: {e}")
            return {}

    def delete_strategy_parameters(self, strategy_id: int, param_names: Optional[List[str]] = None) -> bool:
        """
        删除策略参数

        Args:
            strategy_id: 策略ID
            param_names: 参数名称列表，None表示删除所有参数

        Returns:
            是否删除成功
        """
        try:
            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()

                if param_names:
                    placeholders = ','.join(['?' for _ in param_names])
                    sql = f"DELETE FROM strategy_parameters WHERE strategy_id = ? AND param_name IN ({placeholders})"
                    cursor.execute(sql, [strategy_id] + param_names)
                else:
                    sql = "DELETE FROM strategy_parameters WHERE strategy_id = ?"
                    cursor.execute(sql, (strategy_id,))

                conn.commit()
                logger.info(f"策略参数删除成功: strategy_id={strategy_id}")
                return True

        except Exception as e:
            logger.error(f"删除策略参数失败: {e}")
            return False

    def save_execution_result(self, execution_data: Dict[str, Any]) -> bool:
        """
        保存策略执行结果

        Args:
            execution_data: 执行数据字典

        Returns:
            是否保存成功
        """
        try:
            sql = """
            INSERT INTO strategy_executions (strategy_id, execution_time, data_hash, signals_count, execution_duration, success, error_message, performance_metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (
                    execution_data['strategy_id'],
                    execution_data['execution_time'],
                    execution_data['data_hash'],
                    execution_data.get('signals_count', 0),
                    execution_data.get('execution_duration', 0.0),
                    execution_data.get('success', True),
                    execution_data.get('error_message'),
                    json.dumps(execution_data.get('performance_metrics', {}))
                ))
                conn.commit()

                execution_id = cursor.lastrowid
                logger.debug(f"策略执行结果保存成功: execution_id={execution_id}")
                return True

        except Exception as e:
            logger.error(f"保存策略执行结果失败: {e}")
            return False

    def get_execution_history(self, strategy_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取策略执行历史

        Args:
            strategy_id: 策略ID
            limit: 返回记录数限制

        Returns:
            执行历史列表
        """
        try:
            sql = """
            SELECT * FROM strategy_executions
            WHERE strategy_id = ?
            ORDER BY execution_time DESC
            LIMIT ?
            """

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (strategy_id, limit))
                results = cursor.fetchall()

            executions = []
            for result in results:
                executions.append({
                    'id': result[0],
                    'strategy_id': result[1],
                    'execution_time': result[2],
                    'data_hash': result[3],
                    'signals_count': result[4],
                    'execution_duration': result[5],
                    'success': result[6],
                    'error_message': result[7],
                    'performance_metrics': json.loads(result[8]) if result[8] else {}
                })

            return executions

        except Exception as e:
            logger.error(f"获取执行历史失败: {e}")
            return []

    def delete_strategy(self, strategy_id: int) -> bool:
        """
        删除策略（软删除）

        Args:
            strategy_id: 策略ID

        Returns:
            是否删除成功
        """
        try:
            sql = "UPDATE strategies SET is_active = 0 WHERE id = ?"

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (strategy_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"策略删除成功: strategy_id={strategy_id}")
                    return True
                else:
                    logger.warning(f"策略不存在: strategy_id={strategy_id}")
                    return False

        except Exception as e:
            logger.error(f"删除策略失败: {e}")
            return False

    def import_strategies(self, strategies_data: List[Dict[str, Any]]) -> int:
        """
        批量导入策略

        Args:
            strategies_data: 策略数据列表

        Returns:
            成功导入的策略数
        """
        try:
            success_count = 0

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()

                for strategy_data in strategies_data:
                    try:
                        sql = """
                        INSERT INTO strategies (name, strategy_type, version, author, description, category, metadata, class_path, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            strategy_type = excluded.strategy_type,
                            version = excluded.version,
                            author = excluded.author,
                            description = excluded.description,
                            category = excluded.category,
                            metadata = excluded.metadata,
                            class_path = excluded.class_path,
                            is_active = excluded.is_active,
                            updated_at = CURRENT_TIMESTAMP
                        """
                        cursor.execute(sql, (
                            strategy_data['name'],
                            strategy_data['strategy_type'],
                            strategy_data.get('version', '1.0.0'),
                            strategy_data.get('author', ''),
                            strategy_data.get('description', ''),
                            strategy_data.get('category', ''),
                            json.dumps(strategy_data.get('metadata', {})),
                            strategy_data['class_path'],
                            strategy_data.get('is_active', True)
                        ))
                        success_count += 1
                    except Exception as e:
                        logger.warning(f"导入策略失败: {strategy_data.get('name', 'unknown')} - {e}")

                conn.commit()
                logger.info(f"策略批量导入成功: {success_count}/{len(strategies_data)}")
                return success_count

        except Exception as e:
            logger.error(f"批量导入策略失败: {e}")
            return 0

    def export_strategies(self, strategy_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        导出策略数据

        Args:
            strategy_ids: 策略ID列表，None表示导出所有策略

        Returns:
            策略数据列表
        """
        try:
            sql = """SELECT id, name, strategy_type, version, author, description,
                           category, created_at, updated_at, is_active, metadata, class_path
                    FROM strategies WHERE 1=1"""
            params = []

            if strategy_ids:
                placeholders = ','.join(['?' for _ in strategy_ids])
                sql += f" AND id IN ({placeholders})"
                params.extend(strategy_ids)

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                results = cursor.fetchall()

            strategies = []
            for result in results:
                result_dict = dict(result)
                strategies.append({
                    'id': result_dict['id'],
                    'name': result_dict['name'],
                    'strategy_type': result_dict['strategy_type'],
                    'version': result_dict['version'],
                    'author': result_dict['author'],
                    'description': result_dict['description'],
                    'category': result_dict['category'],
                    'created_at': result_dict['created_at'],
                    'updated_at': result_dict['updated_at'],
                    'is_active': result_dict['is_active'],
                    'metadata': self._safe_json_parse(result_dict['metadata']),
                    'class_path': result_dict['class_path']
                })

            logger.info(f"策略导出成功: {len(strategies)}个策略")
            return strategies

        except Exception as e:
            logger.error(f"导出策略失败: {e}")
            return []

    def cleanup_old_data(self, days: int = 30) -> int:
        """
        清理旧数据

        Args:
            days: 保留天数

        Returns:
            清理的记录数
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            sql = "DELETE FROM strategy_executions WHERE execution_time < ?"

            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()

            logger.info(f"清理旧数据成功: 删除了{deleted_count}条记录")
            return deleted_count

        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
            return 0

    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息

        Returns:
            统计信息字典
        """
        try:
            stats = {}

            # 策略统计
            with self.get_connection("strategy_sqlite") as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM strategies")
                stats['total_strategies'] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM strategies WHERE is_active = 1")
                stats['active_strategies'] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM strategy_executions")
                stats['total_executions'] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM strategy_signals")
                stats['total_signals'] = cursor.fetchone()[0]

            # AI策略统计
            with self.get_connection("analytics_duckdb") as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM ai_strategies")
                stats['total_ai_strategies'] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM ai_strategies WHERE is_active = TRUE")
                stats['active_ai_strategies'] = cursor.fetchone()[0]

            return stats

        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return {}

    def _safe_json_parse(self, value: Any, default: Any = None) -> Any:
        """
        安全地解析JSON字符串

        Args:
            value: 要解析的值
            default: 解析失败时返回的默认值

        Returns:
            解析后的对象或默认值
        """
        if default is None:
            default = {}

        if value is None:
            return default

        if isinstance(value, (dict, list)):
            return value

        if isinstance(value, (bytes, bytearray)):
            if not value:
                return default
            value = value.decode('utf-8')

        if not value:
            return default

        value_str = str(value).strip()
        if not value_str:
            return default

        # 快速检查：如果是类路径字符串（包含点号但不是JSON对象），直接返回默认值
        # 这避免了对策略类路径字符串产生不必要的警告
        if '.' in value_str and not value_str.startswith(('{', '[', '"')):
            # 可能是类路径字符串，如 'core.strategy.builtin_strategies.MAStrategy'
            if value_str.count('.') >= 1 and not value_str.startswith('{'):
                return default

        try:
            return json.loads(value_str)
        except (json.JSONDecodeError, TypeError):
            return default

    def _serialize_value(self, value: Any) -> str:
        """
        序列化参数值

        Args:
            value: 参数值

        Returns:
            序列化后的字符串
        """
        if value is None:
            return 'null'
        elif isinstance(value, (int, float, str, bool)):
            return str(value)
        elif isinstance(value, (list, dict)):
            return json.dumps(value)
        else:
            return str(value)

    def _deserialize_value(self, value_str: str, value_type: str) -> Any:
        """
        反序列化参数值

        Args:
            value_str: 序列化后的字符串
            value_type: 值类型

        Returns:
            反序列化后的值
        """
        if value_str == 'null':
            return None

        try:
            if value_type in ['int', 'integer']:
                return int(value_str)
            elif value_type in ['float', 'double', 'decimal']:
                return float(value_str)
            elif value_type == 'bool':
                return value_str.lower() in ['true', '1', 'yes']
            elif value_type in ['list', 'dict', 'json']:
                return json.loads(value_str)
            else:
                return value_str
        except Exception:
            return value_str

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
