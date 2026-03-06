from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB性能优化器

基于2024年最新DuckDB最佳实践的性能优化器
"""

import duckdb
import psutil
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional
from pathlib import Path
import time
import threading

class WorkloadType(Enum):
    """工作负载类型"""
    OLAP = "olap"      # 分析型工作负载
    OLTP = "oltp"      # 事务型工作负载
    MIXED = "mixed"    # 混合工作负载

@dataclass
class DuckDBConfig:
    """DuckDB配置参数（统一定义，带默认值）"""
    memory_limit: str = "8GB"
    threads: int = 4
    max_memory: str = "16GB"
    temp_directory: str = "temp"
    enable_object_cache: bool = True
    enable_progress_bar: bool = False
    checkpoint_threshold: str = "16MB"
    wal_autocheckpoint: int = 10000
    enable_optimizer: bool = True
    enable_profiling: bool = False
    max_expression_depth: int = 1000
    enable_external_access: bool = True
    force_parallelism: bool = True
    enable_join_order_optimizer: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'memory_limit': self.memory_limit,
            'threads': self.threads,
            'max_memory': self.max_memory,
            'temp_directory': self.temp_directory,
            'enable_object_cache': self.enable_object_cache,
            'enable_progress_bar': self.enable_progress_bar,
            'checkpoint_threshold': self.checkpoint_threshold,
            'wal_autocheckpoint': self.wal_autocheckpoint,
            'enable_optimizer': self.enable_optimizer,
            'enable_profiling': self.enable_profiling,
            'max_expression_depth': self.max_expression_depth,
            'enable_external_access': self.enable_external_access,
            'force_parallelism': self.force_parallelism,
            'enable_join_order_optimizer': self.enable_join_order_optimizer
        }

class DuckDBPerformanceOptimizer:
    """DuckDB性能优化器"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = None
        self.current_config: Optional[DuckDBConfig] = None
        self._lock = threading.Lock()

        # 获取系统信息
        self.system_memory_gb = psutil.virtual_memory().total / (1024**3)
        self.cpu_cores = psutil.cpu_count(logical=True)

        logger.info(f"系统信息: 内存={self.system_memory_gb:.1f}GB, CPU核心={self.cpu_cores}")

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """获取优化的DuckDB连接"""
        with self._lock:
            if self.conn is None:
                # 确保路径使用正确的编码，避免中文字符问题
                try:
                    # 使用绝对路径并确保编码正确
                    db_path_str = str(self.db_path.resolve())
                    self.conn = duckdb.connect(db_path_str)
                    logger.info(f"创建DuckDB连接: {self.db_path}")
                except UnicodeDecodeError as e:
                    logger.warning(f"DuckDB路径编码问题，尝试使用ASCII安全路径: {e}")
                    # 如果路径包含中文，使用内存数据库作为回退
                    self.conn = duckdb.connect(":memory:")
                    logger.info("使用内存DuckDB连接作为回退方案")
            return self.conn

    def optimize_for_workload(self, workload_type: WorkloadType) -> bool:
        """为特定工作负载优化配置"""
        try:
            logger.info(f"为{workload_type.value}工作负载优化DuckDB配置")

            config = self._generate_config_for_workload(workload_type)

            success = self._apply_config(config)

            if success:
                self.current_config = config
                logger.info(f" {workload_type.value}工作负载优化完成")
            else:
                logger.error(f" {workload_type.value}工作负载优化失败")

            return success

        except Exception as e:
            logger.error(f"工作负载优化失败: {e}")
            return False

    def apply_custom_config(self, memory_limit_gb: float = None, threads: int = None,
                            workload_type: WorkloadType = None) -> bool:
        """应用用户自定义配置

        Args:
            memory_limit_gb: 内存限制(GB)，None则自动计算
            threads: 线程数，None则自动计算
            workload_type: 工作负载类型，用于确定其他优化参数

        Returns:
            bool: 是否应用成功
        """
        try:
            logger.info("应用用户自定义DuckDB配置")

            if not hasattr(self, 'system_memory_gb') or self.system_memory_gb <= 0:
                self.system_memory_gb = 16.0

            if not hasattr(self, 'cpu_cores') or self.cpu_cores <= 0:
                self.cpu_cores = 4

            if memory_limit_gb is None:
                memory_limit_gb = max(2.0, self.system_memory_gb * 0.7)
            else:
                memory_limit_gb = max(1.0, min(memory_limit_gb, self.system_memory_gb * 0.9))

            if threads is None:
                if workload_type == WorkloadType.OLAP:
                    threads = min(self.cpu_cores, 16)
                elif workload_type == WorkloadType.OLTP:
                    threads = min(self.cpu_cores // 2, 8)
                else:
                    threads = min(self.cpu_cores, 12)
            else:
                threads = max(1, min(threads, self.cpu_cores * 2))

            max_memory_gb = max(memory_limit_gb * 1.2, 4.0)

            try:
                temp_dir = str(self.db_path.parent / "temp")
                Path(temp_dir).mkdir(exist_ok=True, parents=True)
            except Exception as e:
                logger.warning(f"创建临时目录失败: {e}，使用默认路径")
                temp_dir = "temp"

            if workload_type == WorkloadType.OLAP:
                checkpoint_threshold = "1GB"
                wal_autocheckpoint = 10000
            elif workload_type == WorkloadType.OLTP:
                checkpoint_threshold = "256MB"
                wal_autocheckpoint = 1000
            else:
                checkpoint_threshold = "512MB"
                wal_autocheckpoint = 5000

            memory_limit_str = f"{memory_limit_gb:.1f}GB"
            max_memory_str = f"{max_memory_gb:.1f}GB"

            config = DuckDBConfig(
                memory_limit=memory_limit_str,
                threads=threads,
                max_memory=max_memory_str,
                temp_directory=temp_dir,
                enable_object_cache=True,
                enable_progress_bar=True,
                checkpoint_threshold=checkpoint_threshold,
                wal_autocheckpoint=wal_autocheckpoint
            )

            logger.info(f"用户自定义配置: 内存={memory_limit_str}, 线程={threads}")

            success = self._apply_config(config)

            if success:
                self.current_config = config
                logger.info("用户自定义DuckDB配置应用成功")
            else:
                logger.error("用户自定义DuckDB配置应用失败")

            return success

        except Exception as e:
            logger.error(f"应用用户自定义配置失败: {e}")
            return False

    def _generate_config_for_workload(self, workload_type: WorkloadType) -> DuckDBConfig:
        """为工作负载生成配置"""
        try:
            # 基础内存配置（保守策略，使用70%系统内存）
            # 添加安全检查
            if not hasattr(self, 'system_memory_gb') or self.system_memory_gb <= 0:
                logger.warning("系统内存信息无效，使用默认值")
                self.system_memory_gb = 16.0  # 默认16GB
            
            if not hasattr(self, 'cpu_cores') or self.cpu_cores <= 0:
                logger.warning("CPU核心数无效，使用默认值")
                self.cpu_cores = 4  # 默认4核
            
            memory_limit_gb = max(2.0, self.system_memory_gb * 0.7)
            max_memory_gb = max(4.0, self.system_memory_gb * 0.8)

            # 线程配置
            if workload_type == WorkloadType.OLAP:
                # OLAP: 使用更多线程进行并行分析
                threads = min(self.cpu_cores, 16)  # 最多16线程
            elif workload_type == WorkloadType.OLTP:
                # OLTP: 使用较少线程减少竞争
                threads = min(self.cpu_cores // 2, 8)  # 最多8线程
            else:  # MIXED
                # 混合: 平衡配置
                threads = min(self.cpu_cores, 12)  # 最多12线程

            # 临时目录配置
            try:
                temp_dir = str(self.db_path.parent / "temp")
                Path(temp_dir).mkdir(exist_ok=True, parents=True)
            except Exception as e:
                logger.warning(f"创建临时目录失败: {e}，使用默认路径")
                temp_dir = "temp"

            # 检查点配置
            if workload_type == WorkloadType.OLAP:
                checkpoint_threshold = "1GB"  # OLAP较大的检查点
                wal_autocheckpoint = 10000
            elif workload_type == WorkloadType.OLTP:
                checkpoint_threshold = "256MB"  # OLTP较小的检查点
                wal_autocheckpoint = 1000
            else:  # MIXED
                checkpoint_threshold = "512MB"
                wal_autocheckpoint = 5000

            # 确保配置值不为空
            memory_limit_str = f"{memory_limit_gb:.1f}GB"
            max_memory_str = f"{max_memory_gb:.1f}GB"
            
            # 验证生成的字符串
            if not memory_limit_str or memory_limit_str.strip() == 'GB':
                logger.error(f"内存限制生成异常: {memory_limit_str}，使用默认值")
                memory_limit_str = "4GB"
            
            if not max_memory_str or max_memory_str.strip() == 'GB':
                logger.error(f"最大内存生成异常: {max_memory_str}，使用默认值")
                max_memory_str = "8GB"

            config = DuckDBConfig(
                memory_limit=memory_limit_str,
                threads=threads,
                max_memory=max_memory_str,
                temp_directory=temp_dir,
                enable_object_cache=True,
                enable_progress_bar=True,
                checkpoint_threshold=checkpoint_threshold,
                wal_autocheckpoint=wal_autocheckpoint
            )

            logger.info(f"内存配置: {config.memory_limit} (系统内存: {self.system_memory_gb:.1f}GB)")
            logger.info(f"线程配置: {config.threads} (CPU核心: {self.cpu_cores})")

            return config
            
        except Exception as e:
            logger.error(f"生成配置失败: {e}，使用默认配置")
            # 返回安全的默认配置
            return DuckDBConfig(
                memory_limit="4GB",
                threads=4,
                max_memory="8GB",
                temp_directory="temp",
                enable_object_cache=True,
                enable_progress_bar=True,
                checkpoint_threshold="512MB",
                wal_autocheckpoint=5000
            )

    def _apply_config(self, config: DuckDBConfig) -> bool:
        """应用配置到DuckDB"""
        try:
            conn = self.get_connection()

            # 验证配置参数
            if not config.memory_limit or config.memory_limit.strip() == '':
                logger.warning("内存限制配置为空，使用默认值 4GB")
                config.memory_limit = "4GB"
            
            if not config.checkpoint_threshold or config.checkpoint_threshold.strip() == '':
                logger.warning("检查点阈值配置为空，使用默认值 512MB")
                config.checkpoint_threshold = "512MB"

            # 应用配置参数
            # 根据DuckDB官方文档(2024)配置有效参数
            # 参考: https://duckdb.org/docs/stable/configuration/overview
            config_commands = [
                f"SET memory_limit = '{config.memory_limit}'",
                f"SET threads = {config.threads}",
                f"SET max_temp_directory_size = '8GB'",
            ]

            for cmd in config_commands:
                try:
                    conn.execute(cmd)
                    logger.debug(f"应用配置: {cmd}")
                except Exception as e:
                    logger.warning(f"配置应用失败: {cmd} - {e}")

            try:
                if config.checkpoint_threshold:
                    conn.execute(f"PRAGMA checkpoint_threshold = '{config.checkpoint_threshold}'")
            except Exception as e:
                logger.warning(f"配置应用失败: checkpoint_threshold - {e}")

            try:
                wal_size = config.wal_autocheckpoint
                if isinstance(wal_size, int):
                    wal_size = f"{wal_size // 1000}GB"
                conn.execute(f"PRAGMA wal_autocheckpoint = '{wal_size}'")
            except Exception as e:
                logger.warning(f"配置应用失败: wal_autocheckpoint - {e}")

            try:
                if config.enable_optimizer:
                    conn.execute("SET disabled_optimizers = ''")
                else:
                    conn.execute("SET disabled_optimizers = 'all'")
            except Exception as e:
                logger.warning(f"配置应用失败: enable_optimizer - {e}")

            try:
                if config.enable_profiling:
                    conn.execute("SET enable_profiling = 'no_output'")
            except Exception as e:
                logger.warning(f"配置应用失败: enable_profiling - {e}")

            # 验证关键配置
            try:
                # 验证内存配置
                result = conn.execute("SELECT current_setting('memory_limit')").fetchone()
                if result:
                    logger.info(f"当前内存限制: {result[0]}")

                # 验证线程配置
                result = conn.execute("SELECT current_setting('threads')").fetchone()
                if result:
                    logger.info(f"当前线程数: {result[0]}")

            except Exception as e:
                logger.warning(f"配置验证失败: {e}")

            return True

        except Exception as e:
            logger.error(f"应用DuckDB配置失败: {e}")
            return False

    def get_performance_recommendations(self) -> List[str]:
        """获取性能优化建议"""
        recommendations = []

        try:
            # 基于系统资源的建议
            if self.system_memory_gb < 8:
                recommendations.append("系统内存较少(<8GB)，建议增加内存或减少并发查询")
            elif self.system_memory_gb > 32:
                recommendations.append("系统内存充足(>32GB)，可以考虑增加内存缓存配置")

            if self.cpu_cores < 4:
                recommendations.append("CPU核心较少(<4核)，建议减少并行度或升级CPU")
            elif self.cpu_cores > 16:
                recommendations.append("CPU核心充足(>16核)，可以考虑增加并行查询线程")

            # 基于当前配置的建议
            if self.current_config:
                config = self.current_config

                # 内存配置建议
                memory_gb = float(config.memory_limit.replace('GB', ''))
                if memory_gb / self.system_memory_gb > 0.8:
                    recommendations.append("内存配置较高(>80%系统内存)，注意监控内存使用")
                elif memory_gb / self.system_memory_gb < 0.5:
                    recommendations.append("内存配置保守(<50%系统内存)，可以考虑增加内存限制")

                # 线程配置建议
                if config.threads > self.cpu_cores:
                    recommendations.append("线程数超过CPU核心数，可能导致上下文切换开销")
                elif config.threads < self.cpu_cores // 2:
                    recommendations.append("线程数较少，可以考虑增加并行度")

            # 通用优化建议
            recommendations.extend([
                "定期执行VACUUM和ANALYZE以维护统计信息",
                "为频繁查询的列创建适当的索引",
                "使用列式存储格式(Parquet)存储大数据集",
                "考虑数据分区策略以提升查询性能",
                "监控查询执行计划，优化慢查询"
            ])

        except Exception as e:
            logger.error(f"生成性能建议失败: {e}")
            recommendations.append("无法生成性能建议，请检查系统配置")

        return recommendations

    def benchmark_configuration(self, test_queries: List[str] = None) -> Dict[str, Any]:
        """基准测试当前配置"""
        if test_queries is None:
            test_queries = [
                "SELECT 1",
                "SELECT COUNT(*) FROM (SELECT 1 as x FROM generate_series(1, 10000))",
                "SELECT x, x*2, x*3 FROM generate_series(1, 1000) as t(x) ORDER BY x DESC LIMIT 100"
            ]

        results = {
            'config': self.current_config.to_dict() if self.current_config else None,
            'system_info': {
                'memory_gb': self.system_memory_gb,
                'cpu_cores': self.cpu_cores
            },
            'query_results': [],
            'summary': {}
        }

        try:
            conn = self.get_connection()

            total_time = 0
            successful_queries = 0

            for i, query in enumerate(test_queries):
                start_time = time.time()
                try:
                    result = conn.execute(query).fetchall()
                    execution_time = time.time() - start_time

                    results['query_results'].append({
                        'query_index': i + 1,
                        'query': query[:100] + "..." if len(query) > 100 else query,
                        'execution_time': execution_time,
                        'result_count': len(result),
                        'success': True
                    })

                    total_time += execution_time
                    successful_queries += 1

                except Exception as e:
                    execution_time = time.time() - start_time
                    results['query_results'].append({
                        'query_index': i + 1,
                        'query': query[:100] + "..." if len(query) > 100 else query,
                        'execution_time': execution_time,
                        'error': str(e),
                        'success': False
                    })

            # 计算汇总统计
            results['summary'] = {
                'total_queries': len(test_queries),
                'successful_queries': successful_queries,
                'success_rate': successful_queries / len(test_queries) * 100,
                'total_time': total_time,
                'average_time': total_time / successful_queries if successful_queries > 0 else 0
            }

        except Exception as e:
            logger.error(f"基准测试失败: {e}")
            results['error'] = str(e)

        return results

    def close(self):
        """关闭连接"""
        with self._lock:
            if self.conn:
                try:
                    self.conn.close()
                    logger.info("DuckDB连接已关闭")
                except Exception as e:
                    logger.warning(f"关闭DuckDB连接失败: {e}")
                finally:
                    self.conn = None

def get_optimized_duckdb_connection(
    db_path: str,
    workload_type: WorkloadType = WorkloadType.OLAP
) -> duckdb.DuckDBPyConnection:
    """获取优化的DuckDB连接"""
    optimizer = DuckDBPerformanceOptimizer(db_path)
    optimizer.optimize_for_workload(workload_type)
    return optimizer.get_connection()

def create_performance_optimized_config(
    workload_type: WorkloadType = WorkloadType.OLAP,
    custom_memory_gb: Optional[float] = None,
    custom_threads: Optional[int] = None
) -> DuckDBConfig:
    """创建性能优化配置"""

    # 获取系统信息
    system_memory_gb = psutil.virtual_memory().total / (1024**3)
    cpu_cores = psutil.cpu_count(logical=True)

    # 使用自定义配置或自动配置
    if custom_memory_gb:
        memory_limit_gb = custom_memory_gb
        max_memory_gb = custom_memory_gb * 1.2
    else:
        memory_limit_gb = max(2.0, system_memory_gb * 0.7)
        max_memory_gb = max(4.0, system_memory_gb * 0.8)

    if custom_threads:
        threads = custom_threads
    else:
        if workload_type == WorkloadType.OLAP:
            threads = min(cpu_cores, 16)
        elif workload_type == WorkloadType.OLTP:
            threads = min(cpu_cores // 2, 8)
        else:  # MIXED
            threads = min(cpu_cores, 12)

    return DuckDBConfig(
        memory_limit=f"{memory_limit_gb:.1f}GB",
        threads=threads,
        max_memory=f"{max_memory_gb:.1f}GB",
        temp_directory="temp",
        enable_object_cache=True,
        enable_progress_bar=True,
        checkpoint_threshold="512MB",
        wal_autocheckpoint=5000
    )
