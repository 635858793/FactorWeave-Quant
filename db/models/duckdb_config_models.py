#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB配置数据库模型

管理DuckDB性能优化配置的存储和检索
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from loguru import logger
from core.database.unified_sqlite_access import UnifiedSQLiteAccess


@dataclass
class DuckDBConfigProfile:
    """DuckDB配置配置文件"""
    id: Optional[int] = None
    profile_name: str = ""
    description: str = ""
    workload_type: str = "OLAP"  # OLAP, OLTP, MIXED

    # 内存配置
    memory_limit: str = "4.0GB"
    max_memory: str = "4.4GB"
    buffer_pool_size: str = "1GB"
    temp_memory_limit: str = "2GB"

    # 线程配置
    threads: int = 4
    io_threads: int = 2
    parallel_tasks: int = 4
    worker_threads: int = 3

    # 存储配置
    checkpoint_threshold: str = "512MB"
    wal_autocheckpoint: int = 5000
    temp_directory_size: str = "20GB"
    enable_fsync: bool = True
    enable_mmap: bool = True

    # 查询配置
    enable_optimizer: bool = True
    enable_profiling: bool = False
    enable_progress_bar: bool = True
    enable_object_cache: bool = True
    max_expression_depth: int = 1000
    enable_external_access: bool = True
    enable_httpfs: bool = True
    enable_parquet_statistics: bool = True
    preserve_insertion_order: bool = False
    enable_verification: bool = False

    # 高级配置
    force_parallelism: bool = True
    enable_join_order_optimizer: bool = True
    enable_unnest_rewriter: bool = True
    enable_object_cache_map: bool = True
    enable_auto_analyze: bool = True
    auto_analyze_sample_size: int = 100000
    enable_compression: bool = True
    compression_level: int = 6
    http_timeout: int = 30000
    http_retries: int = 3

    # 元数据
    is_active: bool = False
    is_default: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DuckDBConfigProfile':
        """从字典创建实例"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'DuckDBConfigProfile':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class DuckDBConfigManager:
    """DuckDB配置管理器"""

    def __init__(self, db_path: str = 'data/factorweave_system.sqlite'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _init_tables(self):
        """初始化配置表"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS duckdb_config_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        workload_type TEXT DEFAULT 'OLAP',
                        
                        -- 内存配置
                        memory_limit TEXT DEFAULT '4.0GB',
                        max_memory TEXT DEFAULT '4.4GB',
                        buffer_pool_size TEXT DEFAULT '1GB',
                        temp_memory_limit TEXT DEFAULT '2GB',
                        
                        -- 线程配置
                        threads INTEGER DEFAULT 4,
                        io_threads INTEGER DEFAULT 2,
                        parallel_tasks INTEGER DEFAULT 4,
                        worker_threads INTEGER DEFAULT 3,
                        
                        -- 存储配置
                        checkpoint_threshold TEXT DEFAULT '512MB',
                        wal_autocheckpoint INTEGER DEFAULT 5000,
                        temp_directory_size TEXT DEFAULT '20GB',
                        enable_fsync BOOLEAN DEFAULT 1,
                        enable_mmap BOOLEAN DEFAULT 1,
                        
                        -- 查询配置
                        enable_optimizer BOOLEAN DEFAULT 1,
                        enable_profiling BOOLEAN DEFAULT 0,
                        enable_progress_bar BOOLEAN DEFAULT 1,
                        enable_object_cache BOOLEAN DEFAULT 1,
                        max_expression_depth INTEGER DEFAULT 1000,
                        enable_external_access BOOLEAN DEFAULT 1,
                        enable_httpfs BOOLEAN DEFAULT 1,
                        enable_parquet_statistics BOOLEAN DEFAULT 1,
                        preserve_insertion_order BOOLEAN DEFAULT 0,
                        enable_verification BOOLEAN DEFAULT 0,
                        
                        -- 高级配置
                        force_parallelism BOOLEAN DEFAULT 1,
                        enable_join_order_optimizer BOOLEAN DEFAULT 1,
                        enable_unnest_rewriter BOOLEAN DEFAULT 1,
                        enable_object_cache_map BOOLEAN DEFAULT 1,
                        enable_auto_analyze BOOLEAN DEFAULT 1,
                        auto_analyze_sample_size INTEGER DEFAULT 100000,
                        enable_compression BOOLEAN DEFAULT 1,
                        compression_level INTEGER DEFAULT 6,
                        http_timeout INTEGER DEFAULT 30000,
                        http_retries INTEGER DEFAULT 3,
                        
                        -- 元数据
                        is_active BOOLEAN DEFAULT 0,
                        is_default BOOLEAN DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT 'system'
                    )
                """)

                # 创建配置历史表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS duckdb_config_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_id INTEGER,
                        action TEXT NOT NULL,  -- 'create', 'update', 'activate', 'deactivate'
                        old_config TEXT,       -- JSON格式的旧配置
                        new_config TEXT,       -- JSON格式的新配置
                        changed_by TEXT DEFAULT 'system',
                        changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        FOREIGN KEY (profile_id) REFERENCES duckdb_config_profiles (id)
                    )
                """)

                # 创建性能测试结果表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS duckdb_performance_tests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_id INTEGER,
                        test_name TEXT NOT NULL,
                        test_type TEXT DEFAULT 'benchmark',  -- 'benchmark', 'stress', 'compatibility'
                        
                        -- 测试结果
                        success_rate REAL DEFAULT 0.0,
                        average_query_time REAL DEFAULT 0.0,
                        total_test_time REAL DEFAULT 0.0,
                        memory_usage_mb REAL DEFAULT 0.0,
                        cpu_usage_percent REAL DEFAULT 0.0,
                        
                        -- 测试详情
                        test_queries_count INTEGER DEFAULT 0,
                        successful_queries INTEGER DEFAULT 0,
                        failed_queries INTEGER DEFAULT 0,
                        test_data_size INTEGER DEFAULT 0,
                        
                        -- 系统信息
                        system_memory_gb REAL DEFAULT 0.0,
                        system_cpu_cores INTEGER DEFAULT 0,
                        system_info TEXT,      -- JSON格式的系统信息
                        
                        -- 测试配置和结果
                        test_config TEXT,      -- JSON格式的测试配置
                        test_results TEXT,     -- JSON格式的详细结果
                        
                        -- 元数据
                        tested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        tested_by TEXT DEFAULT 'system',
                        notes TEXT,
                        
                        FOREIGN KEY (profile_id) REFERENCES duckdb_config_profiles (id)
                    )
                """)
                logger.info("DuckDB配置表初始化完成")

        except Exception as e:
            logger.error(f" 初始化DuckDB配置表失败: {e}")
            raise

    def create_profile(self, profile: DuckDBConfigProfile) -> int:
        """创建配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                # 如果设置为默认配置，先取消其他默认配置
                if profile.is_default:
                    conn.execute("UPDATE duckdb_config_profiles SET is_default = 0")

                # 如果设置为活动配置，先取消其他活动配置
                if profile.is_active:
                    conn.execute("UPDATE duckdb_config_profiles SET is_active = 0")

                # 插入新配置
                profile.created_at = datetime.now().isoformat()
                profile.updated_at = profile.created_at

                cursor = conn.execute("""
                    INSERT INTO duckdb_config_profiles (
                        profile_name, description, workload_type,
                        memory_limit, max_memory, buffer_pool_size, temp_memory_limit,
                        threads, io_threads, parallel_tasks, worker_threads,
                        checkpoint_threshold, wal_autocheckpoint, temp_directory_size,
                        enable_fsync, enable_mmap,
                        enable_optimizer, enable_profiling, enable_progress_bar,
                        enable_object_cache, max_expression_depth, enable_external_access,
                        enable_httpfs, enable_parquet_statistics, preserve_insertion_order,
                        enable_verification, force_parallelism, enable_join_order_optimizer,
                        enable_unnest_rewriter, enable_object_cache_map, enable_auto_analyze,
                        auto_analyze_sample_size, enable_compression, compression_level,
                        http_timeout, http_retries, is_active, is_default,
                        created_at, updated_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile.profile_name, profile.description, profile.workload_type,
                    profile.memory_limit, profile.max_memory, profile.buffer_pool_size, profile.temp_memory_limit,
                    profile.threads, profile.io_threads, profile.parallel_tasks, profile.worker_threads,
                    profile.checkpoint_threshold, profile.wal_autocheckpoint, profile.temp_directory_size,
                    profile.enable_fsync, profile.enable_mmap,
                    profile.enable_optimizer, profile.enable_profiling, profile.enable_progress_bar,
                    profile.enable_object_cache, profile.max_expression_depth, profile.enable_external_access,
                    profile.enable_httpfs, profile.enable_parquet_statistics, profile.preserve_insertion_order,
                    profile.enable_verification, profile.force_parallelism, profile.enable_join_order_optimizer,
                    profile.enable_unnest_rewriter, profile.enable_object_cache_map, profile.enable_auto_analyze,
                    profile.auto_analyze_sample_size, profile.enable_compression, profile.compression_level,
                    profile.http_timeout, profile.http_retries, profile.is_active, profile.is_default,
                    profile.created_at, profile.updated_at, profile.created_by
                ))

                profile_id = cursor.lastrowid

                # 记录历史
                self._record_history(profile_id, 'create', None, profile.to_json(), profile.created_by)
                logger.info(f" 创建DuckDB配置配置文件: {profile.profile_name} (ID: {profile_id})")
                return profile_id

        except Exception as e:
            logger.error(f" 创建配置配置文件失败: {e}")
            raise

    def get_profile(self, profile_id: int) -> Optional[DuckDBConfigProfile]:
        """获取配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM duckdb_config_profiles WHERE id = ?",
                    (profile_id,)
                )
                row = cursor.fetchone()

                if row:
                    return DuckDBConfigProfile(**dict(row))
                return None

        except Exception as e:
            logger.error(f" 获取配置配置文件失败: {e}")
            return None

    def get_profile_by_name(self, profile_name: str) -> Optional[DuckDBConfigProfile]:
        """根据名称获取配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM duckdb_config_profiles WHERE profile_name = ?",
                    (profile_name,)
                )
                row = cursor.fetchone()

                if row:
                    return DuckDBConfigProfile(**dict(row))
                return None

        except Exception as e:
            logger.error(f" 根据名称获取配置配置文件失败: {e}")
            return None

    def get_active_profile(self) -> Optional[DuckDBConfigProfile]:
        """获取当前活动的配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM duckdb_config_profiles WHERE is_active = 1 LIMIT 1"
                )
                row = cursor.fetchone()

                if row:
                    return DuckDBConfigProfile(**dict(row))
                return None

        except Exception as e:
            logger.error(f" 获取活动配置配置文件失败: {e}")
            return None

    def get_default_profile(self) -> Optional[DuckDBConfigProfile]:
        """获取默认配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM duckdb_config_profiles WHERE is_default = 1 LIMIT 1"
                )
                row = cursor.fetchone()

                if row:
                    return DuckDBConfigProfile(**dict(row))
                return None

        except Exception as e:
            logger.error(f" 获取默认配置配置文件失败: {e}")
            return None

    def list_profiles(self, workload_type: str = None) -> List[DuckDBConfigProfile]:
        """列出所有配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row

                if workload_type:
                    cursor = conn.execute(
                        "SELECT * FROM duckdb_config_profiles WHERE workload_type = ? ORDER BY created_at DESC",
                        (workload_type,)
                    )
                else:
                    cursor = conn.execute(
                        "SELECT * FROM duckdb_config_profiles ORDER BY created_at DESC"
                    )

                profiles = []
                for row in cursor.fetchall():
                    profiles.append(DuckDBConfigProfile(**dict(row)))

                return profiles

        except Exception as e:
            logger.error(f" 列出配置配置文件失败: {e}")
            return []

    def update_profile(self, profile: DuckDBConfigProfile, updated_by: str = 'system') -> bool:
        """更新配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                # 获取旧配置
                old_profile = self.get_profile(profile.id)
                if not old_profile:
                    logger.error(f"配置配置文件不存在: {profile.id}")
                    return False

                # 如果设置为默认配置，先取消其他默认配置
                if profile.is_default and not old_profile.is_default:
                    conn.execute("UPDATE duckdb_config_profiles SET is_default = 0")

                # 如果设置为活动配置，先取消其他活动配置
                if profile.is_active and not old_profile.is_active:
                    conn.execute("UPDATE duckdb_config_profiles SET is_active = 0")

                # 更新配置
                profile.updated_at = datetime.now().isoformat()

                conn.execute("""
                    UPDATE duckdb_config_profiles SET
                        profile_name = ?, description = ?, workload_type = ?,
                        memory_limit = ?, max_memory = ?, buffer_pool_size = ?, temp_memory_limit = ?,
                        threads = ?, io_threads = ?, parallel_tasks = ?, worker_threads = ?,
                        checkpoint_threshold = ?, wal_autocheckpoint = ?, temp_directory_size = ?,
                        enable_fsync = ?, enable_mmap = ?,
                        enable_optimizer = ?, enable_profiling = ?, enable_progress_bar = ?,
                        enable_object_cache = ?, max_expression_depth = ?, enable_external_access = ?,
                        enable_httpfs = ?, enable_parquet_statistics = ?, preserve_insertion_order = ?,
                        enable_verification = ?, force_parallelism = ?, enable_join_order_optimizer = ?,
                        enable_unnest_rewriter = ?, enable_object_cache_map = ?, enable_auto_analyze = ?,
                        auto_analyze_sample_size = ?, enable_compression = ?, compression_level = ?,
                        http_timeout = ?, http_retries = ?, is_active = ?, is_default = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    profile.profile_name, profile.description, profile.workload_type,
                    profile.memory_limit, profile.max_memory, profile.buffer_pool_size, profile.temp_memory_limit,
                    profile.threads, profile.io_threads, profile.parallel_tasks, profile.worker_threads,
                    profile.checkpoint_threshold, profile.wal_autocheckpoint, profile.temp_directory_size,
                    profile.enable_fsync, profile.enable_mmap,
                    profile.enable_optimizer, profile.enable_profiling, profile.enable_progress_bar,
                    profile.enable_object_cache, profile.max_expression_depth, profile.enable_external_access,
                    profile.enable_httpfs, profile.enable_parquet_statistics, profile.preserve_insertion_order,
                    profile.enable_verification, profile.force_parallelism, profile.enable_join_order_optimizer,
                    profile.enable_unnest_rewriter, profile.enable_object_cache_map, profile.enable_auto_analyze,
                    profile.auto_analyze_sample_size, profile.enable_compression, profile.compression_level,
                    profile.http_timeout, profile.http_retries, profile.is_active, profile.is_default,
                    profile.updated_at, profile.id
                ))

                # 记录历史
                self._record_history(profile.id, 'update', old_profile.to_json(), profile.to_json(), updated_by)
                logger.info(f" 更新DuckDB配置配置文件: {profile.profile_name}")
                return True

        except Exception as e:
            logger.error(f" 更新配置配置文件失败: {e}")
            return False

    def activate_profile(self, profile_id: int, activated_by: str = 'system') -> bool:
        """激活配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                # 取消所有活动配置
                conn.execute("UPDATE duckdb_config_profiles SET is_active = 0")

                # 激活指定配置
                cursor = conn.execute(
                    "UPDATE duckdb_config_profiles SET is_active = 1, updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), profile_id)
                )

                if cursor.rowcount > 0:
                    # 记录历史
                    profile = self.get_profile(profile_id)
                    if profile:
                        self._record_history(profile_id, 'activate', None, profile.to_json(), activated_by)
                    logger.info(f" 激活DuckDB配置配置文件: {profile_id}")
                    return True
                else:
                    logger.error(f"配置配置文件不存在: {profile_id}")
                    return False

        except Exception as e:
            logger.error(f" 激活配置配置文件失败: {e}")
            return False

    def delete_profile(self, profile_id: int, deleted_by: str = 'system') -> bool:
        """删除配置配置文件"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                # 获取配置信息
                profile = self.get_profile(profile_id)
                if not profile:
                    logger.error(f"配置配置文件不存在: {profile_id}")
                    return False

                # 如果是活动配置，不允许删除
                if profile.is_active:
                    logger.error(f"不能删除活动配置配置文件: {profile.profile_name}")
                    return False

                # 记录历史
                self._record_history(profile_id, 'delete', profile.to_json(), None, deleted_by)

                # 删除配置
                cursor = conn.execute("DELETE FROM duckdb_config_profiles WHERE id = ?", (profile_id,))

                if cursor.rowcount > 0:
                    logger.info(f" 删除DuckDB配置配置文件: {profile.profile_name}")
                    return True
                else:
                    return False

        except Exception as e:
            logger.error(f" 删除配置配置文件失败: {e}")
            return False

    def _record_history(self, profile_id: int, action: str, old_config: str, new_config: str, changed_by: str, notes: str = None):
        """记录配置历史"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO duckdb_config_history (
                        profile_id, action, old_config, new_config, changed_by, changed_at, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile_id, action, old_config, new_config, changed_by,
                    datetime.now().isoformat(), notes
                ))
        except Exception as e:
            logger.warning(f"记录配置历史失败: {e}")

    def get_profile_history(self, profile_id: int) -> List[Dict[str, Any]]:
        """获取配置历史"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM duckdb_config_history 
                    WHERE profile_id = ? 
                    ORDER BY changed_at DESC
                """, (profile_id,))

                history = []
                for row in cursor.fetchall():
                    history.append(dict(row))

                return history

        except Exception as e:
            logger.error(f" 获取配置历史失败: {e}")
            return []

    def save_performance_test(self, test_result: Dict[str, Any]) -> int:
        """保存性能测试结果"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO duckdb_performance_tests (
                        profile_id, test_name, test_type, success_rate, average_query_time,
                        total_test_time, memory_usage_mb, cpu_usage_percent,
                        test_queries_count, successful_queries, failed_queries, test_data_size,
                        system_memory_gb, system_cpu_cores, system_info,
                        test_config, test_results, tested_at, tested_by, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    test_result.get('profile_id'),
                    test_result.get('test_name', 'Performance Test'),
                    test_result.get('test_type', 'benchmark'),
                    test_result.get('success_rate', 0.0),
                    test_result.get('average_query_time', 0.0),
                    test_result.get('total_test_time', 0.0),
                    test_result.get('memory_usage_mb', 0.0),
                    test_result.get('cpu_usage_percent', 0.0),
                    test_result.get('test_queries_count', 0),
                    test_result.get('successful_queries', 0),
                    test_result.get('failed_queries', 0),
                    test_result.get('test_data_size', 0),
                    test_result.get('system_memory_gb', 0.0),
                    test_result.get('system_cpu_cores', 0),
                    json.dumps(test_result.get('system_info', {})),
                    json.dumps(test_result.get('test_config', {})),
                    json.dumps(test_result.get('test_results', {})),
                    datetime.now().isoformat(),
                    test_result.get('tested_by', 'system'),
                    test_result.get('notes', '')
                ))

                test_id = cursor.lastrowid
                logger.info(f" 保存性能测试结果: {test_id}")
                return test_id

        except Exception as e:
            logger.error(f" 保存性能测试结果失败: {e}")
            return 0

    def get_performance_tests(self, profile_id: int = None) -> List[Dict[str, Any]]:
        """获取性能测试结果"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row

                if profile_id:
                    cursor = conn.execute("""
                        SELECT * FROM duckdb_performance_tests 
                        WHERE profile_id = ? 
                        ORDER BY tested_at DESC
                    """, (profile_id,))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM duckdb_performance_tests 
                        ORDER BY tested_at DESC
                    """)

                tests = []
                for row in cursor.fetchall():
                    test_data = dict(row)
                    # 解析JSON字段
                    try:
                        test_data['system_info'] = json.loads(test_data['system_info'] or '{}')
                        test_data['test_config'] = json.loads(test_data['test_config'] or '{}')
                        test_data['test_results'] = json.loads(test_data['test_results'] or '{}')
                    except json.JSONDecodeError:
                        pass

                    tests.append(test_data)

                return tests

        except Exception as e:
            logger.error(f" 获取性能测试结果失败: {e}")
            return []


# 全局配置管理器实例
_config_manager = None


def get_duckdb_config_manager() -> DuckDBConfigManager:
    """获取DuckDB配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = DuckDBConfigManager()
    return _config_manager


def create_default_profiles():
    """创建默认配置配置文件"""
    manager = get_duckdb_config_manager()

    # 检查是否已有默认配置
    if manager.get_default_profile():
        return

    # OLAP优化配置
    olap_profile = DuckDBConfigProfile(
        profile_name="OLAP优化",
        description="针对分析型工作负载优化的配置，适合大数据查询和聚合操作",
        workload_type="OLAP",
        memory_limit="8.0GB",
        max_memory="9.0GB",
        threads=8,
        enable_object_cache=True,
        enable_parquet_statistics=True,
        preserve_insertion_order=False,
        is_default=True,
        created_by="system"
    )

    # OLTP优化配置
    oltp_profile = DuckDBConfigProfile(
        profile_name="OLTP优化",
        description="针对事务型工作负载优化的配置，适合频繁的增删改查操作",
        workload_type="OLTP",
        memory_limit="4.0GB",
        max_memory="4.5GB",
        threads=4,
        checkpoint_threshold="256MB",
        wal_autocheckpoint=1000,
        preserve_insertion_order=True,
        created_by="system"
    )

    # 混合工作负载配置
    mixed_profile = DuckDBConfigProfile(
        profile_name="混合负载",
        description="平衡的配置，适合同时包含分析和事务操作的工作负载",
        workload_type="MIXED",
        memory_limit="6.0GB",
        max_memory="7.0GB",
        threads=6,
        checkpoint_threshold="512MB",
        wal_autocheckpoint=5000,
        created_by="system"
    )

    try:
        manager.create_profile(olap_profile)
        manager.create_profile(oltp_profile)
        manager.create_profile(mixed_profile)

        # 激活OLAP配置作为默认活动配置
        olap_id = manager.get_profile_by_name("OLAP优化").id
        manager.activate_profile(olap_id, "system")

        logger.info("创建默认DuckDB配置配置文件完成")

    except Exception as e:
        logger.error(f" 创建默认配置配置文件失败: {e}")


if __name__ == '__main__':
    # 测试配置管理器
    # Loguru配置在core.loguru_config中统一管理

    # 创建默认配置
    create_default_profiles()

    # 测试配置管理
    manager = get_duckdb_config_manager()

    # 列出所有配置
    profiles = manager.list_profiles()
    logger.info(f"总共 {len(profiles)} 个配置配置文件:")
    for profile in profiles:
        status = []
        if profile.is_active:
            status.append("活动")
        if profile.is_default:
            status.append("默认")
        status_str = f" ({', '.join(status)})" if status else ""
        logger.info(f"  - {profile.profile_name}: {profile.description}{status_str}")

    # 获取活动配置
    active_profile = manager.get_active_profile()
    if active_profile:
        logger.info(f"\n当前活动配置: {active_profile.profile_name}")
        logger.info(f"内存限制: {active_profile.memory_limit}")
        logger.info(f"线程数: {active_profile.threads}")
        logger.info(f"工作负载类型: {active_profile.workload_type}")
