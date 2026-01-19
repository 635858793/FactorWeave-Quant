from loguru import logger
"""
DuckDB连接管理器

提供DuckDB数据库连接的统一管理，包括：
- 连接池管理
- 数据库初始化
- 性能配置应用
- 连接健康检查
- 异常处理和重连机制

作者: FactorWeave-Quant团队
版本: 1.0
"""

import duckdb
import threading
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
from contextlib import contextmanager
from queue import Queue, Empty
import json
import os


@dataclass
class DuckDBConfig:
    """DuckDB配置参数"""
    memory_limit: str = '8GB'
    threads: str = 'auto'
    max_memory: str = '6GB'  # 修改为绝对单位，避免百分比解析错误
    checkpoint_threshold: str = '16MB'
    enable_progress_bar: bool = True
    enable_profiling: bool = False  # 禁用profiling以避免JSON输出污染日志
    preserve_insertion_order: bool = False
    enable_external_access: bool = True
    enable_fsst_vectors: bool = True  # 启用FSST字符串压缩
    compression: str = 'zstd'        # 使用ZSTD压缩

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'memory_limit': self.memory_limit,
            'threads': self.threads,
            'max_memory': self.max_memory,
            'checkpoint_threshold': self.checkpoint_threshold,
            'enable_progress_bar': self.enable_progress_bar,
            'enable_profiling': self.enable_profiling,
            'preserve_insertion_order': self.preserve_insertion_order,
            'enable_external_access': self.enable_external_access,
            'enable_fsst_vectors': self.enable_fsst_vectors,
            'compression': self.compression
        }


@dataclass
class ConnectionInfo:
    """连接信息"""
    connection_id: str
    database_path: str
    created_at: float
    last_used_at: float
    is_active: bool
    query_count: int = 0
    error_count: int = 0


class DuckDBConnectionPool:
    """DuckDB连接池"""

    def __init__(self, database_path: str, pool_size: int = 50, config: DuckDBConfig = None):
        """
        初始化连接池

        Args:
            database_path: 数据库文件路径
            pool_size: 连接池大小（默认50，从原来的50保持不变，已经足够大）
            config: DuckDB配置
        """
        self.database_path = database_path
        self.pool_size = pool_size
        self.config = config or DuckDBConfig()

        # 连接池
        self._pool = Queue(maxsize=pool_size)
        self._all_connections: Dict[str, duckdb.DuckDBPyConnection] = {}
        self._connection_info: Dict[str, ConnectionInfo] = {}
        self._conn_id_mapping: Dict[int, str] = {}  # 连接对象ID到连接ID的映射

        # 线程锁
        self._lock = threading.RLock()

        # 统计信息
        self._total_connections = 0
        self._active_connections = 0

        # 初始化连接池
        self._initialize_pool()

        logger.info(f"DuckDB连接池初始化完成: {database_path}, 池大小: {pool_size}")

    def _initialize_pool(self):
        """初始化连接池"""
        try:
            # 确保数据库目录存在
            db_dir = Path(self.database_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            # 创建初始连接 - 使用智能策略避免重复失败
            first_connection_failed = False
            for i in range(self.pool_size):
                # 如果第一个连接失败（通常是数据库文件损坏），不再尝试创建更多连接
                if first_connection_failed:
                    logger.warning(f"跳过剩余连接创建（首次连接失败），已创建 {i} 个连接")
                    break

                conn = self._create_connection()
                if conn:
                    self._pool.put(conn)
                elif i == 0:
                    # 第一个连接创建失败，标记并停止
                    first_connection_failed = True
                    logger.error("首次连接创建失败，停止初始化更多连接")

        except Exception as e:
            logger.error(f"连接池初始化失败: {e}")
            raise

    def _create_connection(self) -> Optional[duckdb.DuckDBPyConnection]:
        """创建新的数据库连接"""
        try:
            # 确保路径使用正确的编码
            db_path = str(Path(self.database_path).resolve())

            # 检查数据库文件是否存在
            db_file = Path(db_path)
            db_exists = db_file.exists()

            if db_exists:
                logger.debug(f"数据库文件已存在: {db_path}, 大小: {db_file.stat().st_size} bytes")
            else:
                logger.info(f"创建新数据库文件: {db_path}")

            # 创建连接 - 使用显式的UTF-8编码处理
            try:
                # DuckDB可能在读取现有数据库时遇到编码问题
                # 尝试使用read_only=False确保可以修复可能的编码问题

                # 捕获DuckDB的输出
                import sys
                import io
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                captured_stdout = io.StringIO()
                captured_stderr = io.StringIO()

                try:
                    sys.stdout = captured_stdout
                    sys.stderr = captured_stderr
                    conn = duckdb.connect(db_path, read_only=False)
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

                    # 检查捕获的输出
                    stdout_content = captured_stdout.getvalue()
                    stderr_content = captured_stderr.getvalue()

                    if stdout_content and '{"result"' in stdout_content:
                        logger.warning(f"[DUCKDB OUTPUT] DuckDB connect() produced output: {stdout_content!r}")
                    if stderr_content and '{"result"' in stderr_content:
                        logger.warning(f"[DUCKDB ERROR] DuckDB connect() produced error: {stderr_content!r}")

            except UnicodeDecodeError as ude:
                # UTF-8解码错误 - 可能是数据库文件损坏或包含无效字符
                logger.error(f"UTF-8解码错误: {ude}")
                logger.error(f"数据库路径: {db_path}")

                # 如果是现有数据库文件损坏，尝试备份并重建
                if db_exists:
                    import os
                    backup_path = db_path + f".corrupted_backup_{int(time.time())}"
                    logger.warning(f"检测到数据库文件可能损坏，尝试处理: {backup_path}")

                    try:
                        # 尝试使用 os.replace 进行快速重命名（不复制）
                        # 这避免了读取损坏文件内容，也不会因为文件锁定而失败
                        os.replace(db_path, backup_path)
                        logger.info(f"✅ 已将损坏文件重命名为备份: {backup_path}")

                        # 尝试创建新的数据库
                        conn = duckdb.connect(db_path, read_only=False)
                        logger.info("✅ 成功创建新数据库文件")

                    except PermissionError as pe:
                        # 文件被其他进程锁定，尝试直接删除
                        logger.warning(f"⚠️ 无法重命名文件（可能被锁定），尝试直接删除: {pe}")
                        try:
                            db_file.unlink(missing_ok=True)
                            logger.info("✅ 已删除损坏的数据库文件")

                            # 尝试创建新的数据库
                            conn = duckdb.connect(db_path, read_only=False)
                            logger.info("✅ 成功创建新数据库文件")

                        except Exception as delete_error:
                            logger.error(f"❌ 删除损坏文件失败: {delete_error}")
                            logger.error(f"💡 解决方案: 请手动停止所有Python进程，然后删除文件: {db_path}")
                            # 不抛出异常，而是返回None，让上层处理
                            return None

                    except Exception as backup_error:
                        logger.error(f"❌ 处理损坏文件失败: {backup_error}")
                        logger.error(f"💡 解决方案: 请手动删除损坏的数据库文件: {db_path}")
                        # 不抛出异常，而是返回None，让上层处理
                        return None
                else:
                    # 新建数据库时出现编码错误，可能是路径问题
                    logger.error("创建新数据库时出现UTF-8编码错误")
                    logger.error("可能原因: 1) 路径包含特殊字符 2) 磁盘权限问题 3) 文件系统编码问题")
                    return None

            except Exception as conn_error:
                error_msg = str(conn_error)
                error_type = type(conn_error).__name__

                # 检查是否是WAL文件相关错误
                is_wal_error = (
                    'WAL' in error_msg or
                    'wal' in error_msg or
                    'Catalog' in error_msg and 'does not exist' in error_msg or
                    'Failure while replaying WAL file' in error_msg
                )

                if is_wal_error and db_exists:
                    logger.warning(f"检测到WAL文件错误: {error_type}: {error_msg}")
                    logger.warning(f"尝试清理WAL文件并重试...")

                    # 尝试清理WAL文件
                    wal_file = db_file.with_suffix('.duckdb.wal')
                    wal_shm_file = db_file.with_suffix('.duckdb-wal')

                    try:
                        # 删除WAL文件
                        if wal_file.exists():
                            logger.info(f"删除WAL文件: {wal_file}")
                            wal_file.unlink()

                        if wal_shm_file.exists():
                            logger.info(f"删除WAL共享内存文件: {wal_shm_file}")
                            wal_shm_file.unlink()

                        logger.info("✅ WAL文件清理完成，重新尝试连接...")

                        # 重新尝试连接
                        conn = duckdb.connect(db_path, read_only=False)
                        logger.info("✅ 成功连接数据库（清理WAL后）")

                    except Exception as wal_error:
                        logger.error(f"❌ 清理WAL文件失败: {wal_error}")
                        logger.error(f"💡 解决方案: 请手动删除WAL文件: {wal_file}")
                        # 继续抛出原始错误
                        raise conn_error
                else:
                    # 非WAL错误，直接抛出
                    logger.error(f"创建DuckDB连接时出错: {error_type}: {error_msg}")
                    raise

            # 生成连接ID
            conn_id = f"conn_{self._total_connections}_{int(time.time())}"

            # 应用配置
            self._apply_config(conn)

            # 记录连接信息
            with self._lock:
                self._all_connections[conn_id] = conn
                self._connection_info[conn_id] = ConnectionInfo(
                    connection_id=conn_id,
                    database_path=self.database_path,
                    created_at=time.time(),
                    last_used_at=time.time(),
                    is_active=True
                )
                self._total_connections += 1
                self._active_connections += 1

            # 使用字典来存储连接ID映射，而不是直接设置属性
            if not hasattr(self, '_conn_id_mapping'):
                self._conn_id_mapping = {}
            self._conn_id_mapping[id(conn)] = conn_id

            logger.debug(f"创建DuckDB连接: {conn_id}")
            return conn

        except Exception as e:
            logger.error(f"创建DuckDB连接失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return None

    def _apply_config(self, conn: duckdb.DuckDBPyConnection):
        """应用配置到连接"""
        try:
            config_dict = self.config.to_dict()

            # 设置内存限制
            conn.execute(f"SET memory_limit='{config_dict['memory_limit']}'")

            # 设置线程数
            if config_dict['threads'] != 'auto':
                conn.execute(f"SET threads={config_dict['threads']}")

            # 设置最大内存使用
            conn.execute(f"SET max_memory='{config_dict['max_memory']}'")

            # 设置检查点阈值
            conn.execute(f"SET checkpoint_threshold='{config_dict['checkpoint_threshold']}'")

            # 启用进度条
            if config_dict['enable_progress_bar']:
                conn.execute("SET enable_progress_bar=1")

            # 启用性能分析
            if config_dict['enable_profiling']:
                conn.execute("SET enable_profiling='json'")

            # 设置插入顺序保持
            conn.execute(f"SET preserve_insertion_order={str(config_dict['preserve_insertion_order']).lower()}")

            # 启用外部访问（注意：此设置不能在数据库运行时更改）
            # if config_dict['enable_external_access']:
            #     conn.execute("SET enable_external_access=true")

            # 启用FSST字符串压缩
            if config_dict['enable_fsst_vectors']:
                conn.execute("SET enable_fsst_vectors=true")

            # 设置默认压缩（DuckDB不支持default_compression参数）
            # conn.execute(f"SET default_compression='{config_dict['compression']}'")

            logger.debug("DuckDB配置应用完成")

        except Exception as e:
            logger.warning(f"应用DuckDB配置失败: {e}")

    @contextmanager
    def get_connection(self):
        """获取连接（上下文管理器）"""
        conn = None
        try:
            # 从池中获取连接
            try:
                conn = self._pool.get(timeout=30)  # 30秒超时
            except Empty:
                logger.warning("连接池已满，创建临时连接")
                conn = self._create_connection()
                if not conn:
                    raise Exception("无法创建数据库连接")

            # 更新连接信息
            if hasattr(self, '_conn_id_mapping') and id(conn) in self._conn_id_mapping:
                conn_id = self._conn_id_mapping[id(conn)]
                with self._lock:
                    if conn_id in self._connection_info:
                        self._connection_info[conn_id].last_used_at = time.time()
                        self._connection_info[conn_id].query_count += 1

            yield conn

        except Exception as e:
            # 记录错误
            if conn and hasattr(self, '_conn_id_mapping') and id(conn) in self._conn_id_mapping:
                conn_id = self._conn_id_mapping[id(conn)]
                with self._lock:
                    if conn_id in self._connection_info:
                        self._connection_info[conn_id].error_count += 1

            # 表不存在是正常的降级情况，使用debug级别
            if "does not exist" in str(e) or "Table with name" in str(e):
                logger.debug(f"数据库表不存在（正常降级）: {e}")
            else:
                logger.error(f"数据库连接使用错误: {e}")
            raise

        finally:
            # 归还连接到池中
            if conn:
                try:
                    # 检查连接是否仍然有效
                    if self._is_connection_valid(conn):
                        self._pool.put(conn)
                    else:
                        # 连接无效，创建新连接替换
                        logger.warning("连接无效，创建新连接替换")
                        new_conn = self._create_connection()
                        if new_conn:
                            self._pool.put(new_conn)
                except Exception as e:
                    logger.error(f"归还连接到池中失败: {e}")

    def _is_connection_valid(self, conn: duckdb.DuckDBPyConnection) -> bool:
        """检查连接是否有效"""
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # ✅ 修复：先获取统计信息，再获取连接（避免health_check本身占用连接影响统计）
            with self._lock:
                available_connections = self._pool.qsize()
                total_connections = self._total_connections
                # ✅ 修复：活跃连接数 = 总连接数 - 池中可用连接数
                # 因为连接要么在池中（可用），要么正在使用（活跃）
                active_connections = max(0, total_connections - available_connections)
            
            # 执行健康检查查询
            with self.get_connection() as conn:
                # 执行简单查询测试
                result = conn.execute("SELECT 1 as test").fetchone()

                # 获取数据库信息
                db_info = conn.execute("PRAGMA database_list").fetchall()

                # ✅ 修复：健康检查完成后，重新获取统计信息（因为get_connection可能改变了连接状态）
                with self._lock:
                    available_connections_after = self._pool.qsize()
                    total_connections_after = self._total_connections
                    active_connections_after = max(0, total_connections_after - available_connections_after)
                    
                    stats = {
                        'status': 'healthy',
                        'database_path': self.database_path,
                        'pool_size': self.pool_size,
                        'total_connections': total_connections_after,
                        'active_connections': active_connections_after,
                        'available_connections': available_connections_after,
                        'database_info': db_info,
                        'test_query_result': result,
                        'config': self.config.to_dict()
                    }

                return stats

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            # ✅ 修复：即使健康检查失败，也返回当前的连接池统计信息
            try:
                with self._lock:
                    available_connections = self._pool.qsize()
                    total_connections = self._total_connections
                    active_connections = max(0, total_connections - available_connections)
                    return {
                        'status': 'unhealthy',
                        'error': str(e),
                        'database_path': self.database_path,
                        'pool_size': self.pool_size,
                        'total_connections': total_connections,
                        'active_connections': active_connections,
                        'available_connections': available_connections
                    }
            except Exception:
                return {
                    'status': 'unhealthy',
                    'error': str(e),
                    'database_path': self.database_path
                }

    def get_connection_stats(self) -> List[Dict[str, Any]]:
        """获取连接统计信息"""
        with self._lock:
            return [
                {
                    'connection_id': info.connection_id,
                    'database_path': info.database_path,
                    'created_at': info.created_at,
                    'last_used_at': info.last_used_at,
                    'is_active': info.is_active,
                    'query_count': info.query_count,
                    'error_count': info.error_count,
                    'uptime_seconds': time.time() - info.created_at
                }
                for info in self._connection_info.values()
            ]

    def close_all_connections(self):
        """
        关闭所有连接（优雅关闭）

        执行流程：
        1. 提交所有未完成的事务
        2. 执行CHECKPOINT（将WAL合并到主文件）
        3. 关闭所有连接
        """
        try:
            logger.info(f"🔄 关闭DuckDB连接池: {self.database_path}")
            logger.info(f"   活跃连接: {self._active_connections}/{self._total_connections}")

            with self._lock:
                # 1. 关闭池中的连接（带checkpoint）
                closed_from_pool = 0
                while not self._pool.empty():
                    try:
                        conn = self._pool.get_nowait()
                        # 提交事务
                        try:
                            conn.commit()
                        except:
                            pass  # 可能没有活跃事务

                        # 执行checkpoint（合并WAL）
                        try:
                            conn.execute("CHECKPOINT")
                            logger.debug(f"   ✅ Checkpoint完成")
                        except Exception as e:
                            logger.warning(f"   ⚠️ Checkpoint失败: {e}")

                        # 关闭连接
                        conn.close()
                        closed_from_pool += 1
                    except Empty:
                        break
                    except Exception as e:
                        logger.error(f"   ❌ 关闭连接失败: {e}")

                # 2. 关闭所有记录的连接
                closed_from_registry = 0
                for conn_id, conn in list(self._all_connections.items()):
                    try:
                        # 提交事务
                        try:
                            conn.commit()
                        except:
                            pass

                        # Checkpoint
                        try:
                            conn.execute("CHECKPOINT")
                        except:
                            pass

                        # 关闭
                        conn.close()
                        self._connection_info[conn_id].is_active = False
                        closed_from_registry += 1
                    except Exception as e:
                        logger.error(f"   ❌ 关闭连接 {conn_id} 失败: {e}")

                self._active_connections = 0
                logger.info(f"   ✅ 已关闭连接: 池={closed_from_pool}, 注册={closed_from_registry}")

        except Exception as e:
            logger.error(f"关闭连接时出错: {e}")


class DuckDBConnectionManager:
    """DuckDB连接管理器"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化连接管理器

        Args:
            config_file: 配置文件路径
        """
        self._pools: Dict[str, DuckDBConnectionPool] = {}
        self._lock = threading.RLock()
        self._config_file = config_file
        self._default_config = DuckDBConfig()

        # 加载配置
        if config_file and Path(config_file).exists():
            self._load_config()

        logger.info("DuckDB连接管理器初始化完成")

    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self._config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 更新默认配置
            if 'duckdb' in config_data:
                duckdb_config = config_data['duckdb']
                for key, value in duckdb_config.items():
                    if hasattr(self._default_config, key):
                        setattr(self._default_config, key, value)

            logger.info(f"配置文件加载完成: {self._config_file}")

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")

    def get_pool(self, database_path: str, pool_size: int = 10,
                 config: Optional[DuckDBConfig] = None) -> DuckDBConnectionPool:
        """
        获取或创建连接池

        Args:
            database_path: 数据库文件路径
            pool_size: 连接池大小
            config: DuckDB配置

        Returns:
            DuckDB连接池
        """
        # 标准化路径
        database_path = str(Path(database_path).resolve())

        with self._lock:
            if database_path not in self._pools:
                # 使用提供的配置或默认配置
                pool_config = config or self._default_config

                # 创建新的连接池
                pool = DuckDBConnectionPool(
                    database_path=database_path,
                    pool_size=pool_size,
                    config=pool_config
                )

                self._pools[database_path] = pool
                logger.info(f"创建新的连接池: {database_path}")

            return self._pools[database_path]

    @contextmanager
    def get_connection(self, database_path: str, pool_size: int = 15,
                       config: Optional[DuckDBConfig] = None):
        """
        获取数据库连接

        Args:
            database_path: 数据库文件路径
            pool_size: 连接池大小（默认15，从10增加到15，支持批量查询）
            config: DuckDB配置
        """
        pool = self.get_pool(database_path, pool_size, config)
        with pool.get_connection() as conn:
            yield conn

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """检查所有连接池的健康状态"""
        results = {}

        with self._lock:
            for db_path, pool in self._pools.items():
                try:
                    results[db_path] = pool.health_check()
                except Exception as e:
                    results[db_path] = {
                        'status': 'error',
                        'error': str(e)
                    }

        return results

    def get_all_stats(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有连接池的统计信息"""
        results = {}

        with self._lock:
            for db_path, pool in self._pools.items():
                try:
                    results[db_path] = pool.get_connection_stats()
                except Exception as e:
                    logger.error(f"获取连接池统计信息失败 {db_path}: {e}")
                    results[db_path] = []

        return results

    def close_all_pools(self):
        """关闭所有连接池"""
        with self._lock:
            for db_path, pool in self._pools.items():
                try:
                    pool.close_all_connections()
                    logger.info(f"连接池已关闭: {db_path}")
                except Exception as e:
                    logger.error(f"关闭连接池失败 {db_path}: {e}")

            self._pools.clear()

        logger.info("所有DuckDB连接池已关闭")

    def remove_pool(self, database_path: str):
        """移除指定的连接池"""
        database_path = str(Path(database_path).resolve())

        with self._lock:
            if database_path in self._pools:
                try:
                    self._pools[database_path].close_all_connections()
                    del self._pools[database_path]
                    logger.info(f"连接池已移除: {database_path}")
                except Exception as e:
                    logger.error(f"移除连接池失败 {database_path}: {e}")

    def restart_pool(self, database_path: str, pool_size: int = 15,
                    config: Optional[DuckDBConfig] = None) -> bool:
        """
        重启数据库连接池（用于DuckDB进入受限模式时）

        Args:
            database_path: 数据库文件路径
            pool_size: 连接池大小
            config: DuckDB配置

        Returns:
            是否成功重启
        """
        database_path = str(Path(database_path).resolve())

        try:
            logger.warning(f"🔄 正在重启数据库连接池: {database_path}")

            with self._lock:
                # 关闭并移除旧的连接池
                if database_path in self._pools:
                    try:
                        self._pools[database_path].close_all_connections()
                        del self._pools[database_path]
                        logger.info(f"旧连接池已关闭: {database_path}")
                    except Exception as e:
                        logger.error(f"关闭旧连接池失败: {e}")

                # 创建新的连接池
                pool_config = config or self._default_config
                pool = DuckDBConnectionPool(
                    database_path=database_path,
                    pool_size=pool_size,
                    config=pool_config
                )

                self._pools[database_path] = pool
                logger.info(f"✅ 新连接池已创建: {database_path}")

            logger.info(f"✅ 数据库连接池重启成功: {database_path}")
            return True

        except Exception as e:
            logger.error(f"❌ 重启数据库连接池失败 {database_path}: {e}")
            return False


# 全局连接管理器实例
_connection_manager: Optional[DuckDBConnectionManager] = None
_manager_lock = threading.Lock()


def get_connection_manager(config_file: Optional[str] = None) -> DuckDBConnectionManager:
    """获取全局连接管理器实例"""
    global _connection_manager

    with _manager_lock:
        if _connection_manager is None:
            _connection_manager = DuckDBConnectionManager(config_file)

        return _connection_manager


def initialize_duckdb_manager(config_file: Optional[str] = None) -> DuckDBConnectionManager:
    """初始化DuckDB连接管理器"""
    global _connection_manager

    with _manager_lock:
        if _connection_manager is not None:
            _connection_manager.close_all_pools()

        _connection_manager = DuckDBConnectionManager(config_file)
        logger.info("DuckDB连接管理器已初始化")

        return _connection_manager


def cleanup_duckdb_manager():
    """清理DuckDB连接管理器"""
    global _connection_manager

    with _manager_lock:
        if _connection_manager is not None:
            _connection_manager.close_all_pools()
            _connection_manager = None
            logger.info("DuckDB连接管理器已清理")
