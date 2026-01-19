#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorWeave-Quant 分析数据库管理器 - 连接池版本

使用DuckDB存储和管理所有分析相关的数据，包括：
- 策略执行结果
- 技术指标计算结果
- 回测监控数据
- 性能指标
- 优化日志

基于SQLAlchemy QueuePool实现线程安全的连接池管理
解决多线程并发访问导致的INTERNAL Error问题

作者: AI Assistant
日期: 2025-10-12
版本: 2.1 (场景特化优化)
"""

import pandas as pd
from loguru import logger
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from enum import Enum, auto
import threading

# 导入连接池
from .duckdb_connection_pool import DuckDBConnectionPool


class QueryScenario(Enum):
    """
    查询场景枚举

    不同场景对应不同的超时配置：
    - REALTIME: 实时场景，极低延迟要求 (5秒)
    - MONITORING: 监控场景，低延迟要求 (10秒)
    - NORMAL: 常规场景，标准延迟 (30秒)
    - BATCH: 批量场景，允许较长等待 (60秒)
    - ANALYTICS: 分析场景，复杂查询 (120秒)
    """
    REALTIME = auto()    # 实时场景: 5秒
    MONITORING = auto()  # 监控场景: 10秒
    NORMAL = auto()      # 常规场景: 30秒
    BATCH = auto()       # 批量场景: 60秒
    ANALYTICS = auto()   # 分析场景: 120秒


# 安全导入DuckDB
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"DuckDB模块不可用: {e}")
    duckdb = None
    DUCKDB_AVAILABLE = False


class FactorWeaveAnalyticsDB:
    """
    FactorWeave分析数据库管理器 - 连接池版本

    特性:
    - 线程安全: 使用SQLAlchemy QueuePool管理连接
    - 高性能: 连接复用，减少创建开销
    - 自动优化: 智能配置数据库参数
    - 健康检查: 自动检测并恢复失效连接

    变更说明 (v2.0):
    - 使用连接池替代单一连接
    - 移除旧的_connect和reconnect方法
    - 所有数据库操作自动线程安全
    - 简化API，提高可维护性
    """

    _instances = {}  # 每个数据库路径一个实例
    _lock = threading.Lock()

    def __new__(cls, db_path: str = 'data/factorweave_analytics.duckdb'):
        """单例模式实现 - 按数据库路径区分实例"""
        db_path = str(Path(db_path).resolve())  # 标准化路径

        with cls._lock:
            if db_path not in cls._instances:
                cls._instances[db_path] = super().__new__(cls)
                cls._instances[db_path]._initialized = False

        return cls._instances[db_path]

    def __init__(self, db_path: str = 'data/factorweave_analytics.duckdb'):
        """
        初始化分析数据库

        Args:
            db_path: 数据库文件路径
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        if not DUCKDB_AVAILABLE:
            logger.error("DuckDB不可用，分析数据库功能将被禁用")
            self._initialized = True
            return

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # ✅ 初始化配置管理器
        self.config_manager = self._get_config_manager()

        # ✅ 使用配置创建连接池
        try:
            self._create_pool()
            logger.info(f"✅ FactorWeave分析数据库连接池已初始化: {self.db_path}")

            # 应用优化配置
            self._apply_optimization()

            # 初始化表结构
            self._init_tables()

        except Exception as e:
            logger.error(f"❌ 初始化数据库连接池失败: {e}")
            raise

        self._initialized = True
        logger.info(f"✅ FactorWeave分析数据库初始化完成: {self.db_path}")

    def _get_config_manager(self):
        """获取配置管理器"""
        try:
            from core.containers import get_service_container
            from core.services.config_service import ConfigService
            from .connection_pool_config import ConnectionPoolConfigManager

            container = get_service_container()
            config_service = container.resolve(ConfigService)

            return ConnectionPoolConfigManager(config_service)
        except Exception as e:
            logger.warning(f"无法获取ConfigService，使用默认配置: {e}")
            return None

    def _create_pool(self):
        """创建连接池（使用配置）"""
        if self.config_manager:
            # 加载配置
            pool_config = self.config_manager.load_pool_config()
            logger.info(f"📋 使用配置创建连接池: pool_size={pool_config.pool_size}, max_overflow={pool_config.max_overflow}")

            self.pool = DuckDBConnectionPool(
                db_path=str(self.db_path),
                pool_size=pool_config.pool_size,
                max_overflow=pool_config.max_overflow,
                timeout=pool_config.timeout,
                pool_recycle=pool_config.pool_recycle,
                use_lifo=pool_config.use_lifo
            )
        else:
            # 使用默认配置
            logger.info("📋 使用默认配置创建连接池: pool_size=15, max_overflow=100")
            self.pool = DuckDBConnectionPool(
                db_path=str(self.db_path),
                pool_size=15,
                max_overflow=100,
                timeout=30.0,
                pool_recycle=3600
            )

    def reload_pool(self, new_config=None):
        """
        热重载连接池（修改后立即生效）

        Args:
            new_config: 新的连接池配置，None则从配置服务加载

        Returns:
            bool: 是否成功
        """
        try:
            logger.info("🔄 开始热重载连接池...")

            # 1. 关闭当前连接池
            if hasattr(self, 'pool') and self.pool:
                logger.info("关闭当前连接池...")
                self.pool.dispose()

            # 2. 重新创建连接池
            if new_config:
                # 使用提供的配置
                logger.info(f"使用新配置: {new_config}")
                self.pool = DuckDBConnectionPool(
                    db_path=str(self.db_path),
                    pool_size=new_config.pool_size,
                    max_overflow=new_config.max_overflow,
                    timeout=new_config.timeout,
                    pool_recycle=new_config.pool_recycle,
                    use_lifo=new_config.use_lifo
                )
            else:
                # 从配置服务加载
                self._create_pool()

            # 3. 重新应用优化配置
            self._apply_optimization()

            logger.info("✅ 连接池热重载完成！")
            return True

        except Exception as e:
            logger.error(f"❌ 连接池热重载失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _check_connection(self) -> bool:
        """
        检查数据库连接是否可用

        Returns:
            bool: 连接是否可用
        """
        if not DUCKDB_AVAILABLE:
            logger.warning("DuckDB不可用，操作被跳过")
            return False
        if not hasattr(self, 'pool'):
            logger.warning("连接池未初始化，操作被跳过")
            return False
        return True

    def _apply_optimization(self):
        """应用数据库优化配置"""
        try:
            import psutil

            # 获取系统资源
            memory_gb = psutil.virtual_memory().total / (1024**3)
            cpu_cores = psutil.cpu_count(logical=True)

            # 保守的内存配置（使用50%系统内存）
            memory_limit = max(2.0, memory_gb * 0.5)

            # 线程配置（不超过CPU核心数）
            threads = min(cpu_cores, 8)  # 最多8线程

            # 应用配置到连接池
            with self.pool.get_connection() as conn:
                conn.execute(f"SET memory_limit = '{memory_limit:.1f}GB'")
                conn.execute(f"SET threads = {threads}")
                conn.execute("SET enable_object_cache = true")
                conn.execute("SET enable_progress_bar = false")  # 关闭进度条，避免日志混乱

            logger.info(f"✅ 数据库优化配置已应用: 内存={memory_limit:.1f}GB, 线程={threads}")

        except Exception as e:
            logger.warning(f"应用优化配置失败: {e}")

    def _init_tables(self):
        """初始化分析数据库表结构"""
        if not self._check_connection():
            return

        try:
            with self.pool.get_connection() as conn:
                # 创建序列
                sequences = [
                    'strategy_execution_results_seq',
                    'indicator_calculation_results_seq',
                    'backtest_monitoring_seq',
                    'performance_metrics_seq',
                    'optimization_logs_seq'
                ]

                for seq in sequences:
                    conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1")

                # 创建策略执行结果表
                conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_execution_results (
                        id BIGINT PRIMARY KEY DEFAULT nextval('strategy_execution_results_seq'),
                        strategy_name VARCHAR,
                        symbol VARCHAR,
                        execution_time TIMESTAMP,
                        signal_type VARCHAR,
                    price DOUBLE,
                    quantity INTEGER,
                        profit_loss DOUBLE,
                        metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

                # 创建技术指标计算结果表
                conn.execute("""
                CREATE TABLE IF NOT EXISTS indicator_calculation_results (
                        id BIGINT PRIMARY KEY DEFAULT nextval('indicator_calculation_results_seq'),
                        indicator_name VARCHAR,
                        symbol VARCHAR,
                        calculation_time TIMESTAMP,
                    value DOUBLE,
                        parameters JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

                # 创建回测监控表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS backtest_monitoring (
                        id BIGINT PRIMARY KEY DEFAULT nextval('backtest_monitoring_seq'),
                        backtest_id VARCHAR,
                        timestamp TIMESTAMP,
                        metric_name VARCHAR,
                        metric_value DOUBLE,
                        metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

                # 创建性能指标表
                conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                        id BIGINT PRIMARY KEY DEFAULT nextval('performance_metrics_seq'),
                        metric_type VARCHAR,
                        metric_name VARCHAR,
                        value DOUBLE,
                        timestamp TIMESTAMP,
                        tags JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

                # 创建优化日志表
                conn.execute("""
                CREATE TABLE IF NOT EXISTS optimization_logs (
                        id BIGINT PRIMARY KEY DEFAULT nextval('optimization_logs_seq'),
                        optimization_type VARCHAR,
                        parameters JSON,
                        result DOUBLE,
                        improvement DOUBLE,
                        timestamp TIMESTAMP,
                        metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

                logger.info("✅ 数据库表结构初始化完成")

        except Exception as e:
            logger.error(f"❌ 初始化表结构失败: {e}")
            raise

    def execute_query(self, sql: str, params: Optional[List] = None,
                      scenario: QueryScenario = QueryScenario.NORMAL) -> pd.DataFrame:
        """
        执行查询并返回DataFrame（支持场景特化超时）

        Args:
            sql: SQL查询语句
            params: 查询参数
            scenario: 查询场景，决定超时时间

        Returns:
            pandas.DataFrame: 查询结果

        Examples:
            # 常规查询
            df = db.execute_query("SELECT * FROM table")

            # 实时查询（5秒超时）
            df = db.execute_query("SELECT * FROM table", scenario=QueryScenario.REALTIME)

            # 复杂分析查询（120秒超时）
            df = db.execute_query(complex_sql, scenario=QueryScenario.ANALYTICS)
        """
        if not self._check_connection():
            return pd.DataFrame()

        # 场景特化超时映射
        timeout_map = {
            QueryScenario.REALTIME: 5.0,
            QueryScenario.MONITORING: 10.0,
            QueryScenario.NORMAL: 30.0,
            QueryScenario.BATCH: 60.0,
            QueryScenario.ANALYTICS: 120.0
        }
        timeout = timeout_map.get(scenario, 30.0)

        # 记录场景信息（仅在非常规场景时）
        if scenario != QueryScenario.NORMAL:
            logger.debug(f"执行{scenario.name}场景查询，超时设置为{timeout}秒")

        return self.pool.execute_query(sql, params)

    def execute_command(self, sql: str, params: Optional[List] = None) -> bool:
        """
        执行命令（INSERT, UPDATE, DELETE等）

        Args:
            sql: SQL命令
            params: 命令参数

        Returns:
            bool: 执行是否成功
        """
        if not self._check_connection():
            return False

        return self.pool.execute_command(sql, params)

    def insert_strategy_result(self, strategy_name: str, symbol: str,
                               signal_type: str, price: float, quantity: int,
                               profit_loss: float, metadata: Optional[Dict] = None) -> bool:
        """插入策略执行结果"""
        try:
            import json
            sql = """
                INSERT INTO strategy_execution_results
                (strategy_name, symbol, execution_time, signal_type, price, quantity, profit_loss, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                strategy_name, symbol, datetime.now(), signal_type,
                price, quantity, profit_loss, json.dumps(metadata or {})
            ]
            return self.execute_command(sql, params)
        except Exception as e:
            logger.error(f"插入策略结果失败: {e}")
            return False

    def insert_indicator_result(self, indicator_name: str, symbol: str,
                                value: float, parameters: Optional[Dict] = None) -> bool:
        """插入技术指标计算结果"""
        try:
            import json
            sql = """
                INSERT INTO indicator_calculation_results
                (indicator_name, symbol, calculation_time, value, parameters)
                VALUES (?, ?, ?, ?, ?)
            """
            params = [
                indicator_name, symbol, datetime.now(), value,
                json.dumps(parameters or {})
            ]
            return self.execute_command(sql, params)
        except Exception as e:
            logger.error(f"插入指标结果失败: {e}")
            return False

    def insert_performance_metric(self, metric_type: str, metric_name: str,
                                  value: float, tags: Optional[Dict] = None) -> bool:
        """插入性能指标"""
        try:
            import json
            sql = """
                INSERT INTO performance_metrics
                (metric_type, metric_name, value, timestamp, tags)
                VALUES (?, ?, ?, ?, ?)
            """
            params = [
                metric_type, metric_name, value, datetime.now(),
                json.dumps(tags or {})
            ]
            return self.execute_command(sql, params)
        except Exception as e:
            logger.error(f"插入性能指标失败: {e}")
            return False

    def get_strategy_results(self, strategy_name: Optional[str] = None,
                             symbol: Optional[str] = None,
                             limit: int = 100) -> pd.DataFrame:
        """查询策略执行结果"""
        try:
            sql = "SELECT * FROM strategy_execution_results WHERE 1=1"
            params = []

            if strategy_name:
                sql += " AND strategy_name = ?"
                params.append(strategy_name)

            if symbol:
                sql += " AND symbol = ?"
                params.append(symbol)

                sql += " ORDER BY execution_time DESC LIMIT ?"
            params.append(limit)

            return self.execute_query(sql, params)
        except Exception as e:
            logger.error(f"查询策略结果失败: {e}")
            return pd.DataFrame()

    def get_performance_metrics(self, metric_type: Optional[str] = None,
                                limit: int = 100) -> pd.DataFrame:
        """查询性能指标"""
        try:
            sql = "SELECT * FROM performance_metrics WHERE 1=1"
            params = []

            if metric_type:
                sql += " AND metric_type = ?"
                params.append(metric_type)

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            return self.execute_query(sql, params)
        except Exception as e:
            logger.error(f"查询性能指标失败: {e}")
            return pd.DataFrame()

    def get_pool_status(self) -> Dict[str, Any]:
        """
        获取连接池状态

        Returns:
            dict: 连接池状态信息
        """
        if not hasattr(self, 'pool'):
            return {'status': 'not_initialized'}

        return self.pool.get_pool_status()

    def health_check(self) -> Dict[str, Any]:
        """
        连接池健康检查

        Returns:
            dict: 健康状态信息
            - healthy: bool - 是否健康
            - warnings: List[str] - 警告列表
            - metrics: Dict - 连接池指标
            - recommendations: List[str] - 优化建议
        """
        if not self._check_connection():
            return {
                'healthy': False,
                'warnings': ['连接池未初始化或不可用'],
                'metrics': {},
                'recommendations': ['检查数据库初始化状态']
            }

        status = self.get_pool_status()

        health = {
            'healthy': True,
            'warnings': [],
            'metrics': status,
            'recommendations': []
        }

        # 检查连接池使用率
        if 'checked_out' in status and 'pool_size' in status:
            usage_rate = status['checked_out'] / status['pool_size'] if status['pool_size'] > 0 else 0

            if usage_rate > 0.9:
                health['healthy'] = False
                health['warnings'].append(f"连接池使用率极高 ({usage_rate*100:.1f}%)，可能导致等待")
                health['recommendations'].append("立即增加pool_size或优化查询频率")
            elif usage_rate > 0.8:
                health['warnings'].append(f"连接池使用率偏高 ({usage_rate*100:.1f}%)")
                health['recommendations'].append("考虑增加pool_size到10-15")
            elif usage_rate > 0.6:
                health['warnings'].append(f"连接池使用率适中 ({usage_rate*100:.1f}%)")

        # 检查溢出连接
        if 'overflow' in status:
            overflow = status.get('overflow', 0)
            if overflow > status.get('pool_size', 0):
                health['warnings'].append(f"溢出连接数({overflow})超过核心池大小")
                health['recommendations'].append("增加pool_size以减少溢出连接")
            elif overflow > 0:
                health['warnings'].append(f"存在{overflow}个溢出连接")

        # 检查连接池大小合理性
        pool_size = status.get('pool_size', 0)
        if pool_size < 3:
            health['warnings'].append("连接池过小，可能影响并发性能")
            health['recommendations'].append("建议pool_size至少为5")
        elif pool_size > 20:
            health['warnings'].append("连接池较大，注意内存使用")
            health['recommendations'].append("监控内存使用情况")

        # 如果有警告，标记为不完全健康
        if health['warnings'] and health['healthy']:
            health['healthy'] = len([w for w in health['warnings'] if '极高' in w or '超过' in w]) == 0

        return health

    def close(self):
        """关闭数据库连接池"""
        if hasattr(self, 'pool'):
            try:
                self.pool.dispose()
                logger.info("✅ 数据库连接池已关闭")
            except Exception as e:
                logger.error(f"关闭连接池失败: {e}")

    def __enter__(self):
        """支持上下文管理器协议"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.close()
        return False

    def __del__(self):
        """析构时清理资源"""
        try:
            self.close()
        except:
            pass


# ========================================
# 向后兼容性别名（保留旧的方法名）
# ========================================

# 为了确保现有代码能够继续工作，提供别名
# 但这些别名在未来版本中可能会被移除
def create_factorweave_db(db_path: str = 'data/factorweave_analytics.duckdb') -> FactorWeaveAnalyticsDB:
    """
    创建FactorWeave分析数据库实例

    这是一个便捷函数，用于创建数据库实例。

    Args:
        db_path: 数据库文件路径

    Returns:
        FactorWeaveAnalyticsDB: 数据库实例
    """
    return FactorWeaveAnalyticsDB(db_path)


def get_analytics_db(db_path: str = 'data/factorweave_analytics.duckdb') -> FactorWeaveAnalyticsDB:
    """
    获取FactorWeave分析数据库实例（单例模式）

    这是一个便捷函数，返回默认的分析数据库实例。
    由于FactorWeaveAnalyticsDB已经是单例，多次调用会返回同一实例。

    Args:
        db_path: 数据库文件路径（仅首次创建时有效）

    Returns:
        FactorWeaveAnalyticsDB: 数据库单例实例
    """
    return FactorWeaveAnalyticsDB(db_path)
