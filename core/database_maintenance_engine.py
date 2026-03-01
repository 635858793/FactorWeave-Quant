"""
数据库维护和优化引擎

提供数据库的健康检查、性能优化、数据清理、索引管理、统计信息收集等功能。
支持跨资产类型的数据库维护，确保系统的高效运行和数据质量。

作者: FactorWeave-Quant团队
版本: 1.0
"""

import threading
import time
import os
import shutil
from typing import Dict, Any, Optional, List, Union, Callable, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sqlite3

from loguru import logger
from .plugin_types import AssetType, DataType
from .asset_database_manager import get_asset_database_manager
from .cross_asset_query_engine import get_cross_asset_query_engine

logger = logger.bind(module=__name__)

class MaintenanceTaskType(Enum):
    """维护任务类型枚举"""
    HEALTH_CHECK = "health_check"           # 健康检查
    PERFORMANCE_ANALYSIS = "performance_analysis"  # 性能分析
    INDEX_OPTIMIZATION = "index_optimization"      # 索引优化
    DATA_CLEANUP = "data_cleanup"           # 数据清理
    STATISTICS_UPDATE = "statistics_update"  # 统计信息更新
    VACUUM = "vacuum"                       # 数据库压缩
    INTEGRITY_CHECK = "integrity_check"     # 完整性检查
    BACKUP = "backup"                       # 数据备份
    ARCHIVE = "archive"                     # 数据归档

class MaintenanceStatus(Enum):
    """维护状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MaintenancePriority(Enum):
    """维护优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class MaintenanceTask:
    """维护任务"""
    task_id: str
    task_type: MaintenanceTaskType
    asset_type: Optional[AssetType] = None
    priority: MaintenancePriority = MaintenancePriority.NORMAL
    status: MaintenanceStatus = MaintenanceStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    progress: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type.value,
            'asset_type': self.asset_type.value if self.asset_type else None,
            'priority': self.priority.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'parameters': self.parameters,
            'result': self.result,
            'error_message': self.error_message,
            'progress': self.progress
        }

@dataclass
class DatabaseHealthReport:
    """数据库健康报告"""
    asset_type: AssetType
    database_path: str
    file_size_mb: float
    table_count: int
    record_count: int
    index_count: int
    last_vacuum: Optional[datetime]
    fragmentation_ratio: float
    performance_score: float
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'asset_type': self.asset_type.value,
            'database_path': self.database_path,
            'file_size_mb': self.file_size_mb,
            'table_count': self.table_count,
            'record_count': self.record_count,
            'index_count': self.index_count,
            'last_vacuum': self.last_vacuum.isoformat() if self.last_vacuum else None,
            'fragmentation_ratio': self.fragmentation_ratio,
            'performance_score': self.performance_score,
            'issues': self.issues,
            'recommendations': self.recommendations
        }

@dataclass
class MaintenanceSchedule:
    """维护计划"""
    schedule_id: str
    task_type: MaintenanceTaskType
    asset_type: Optional[AssetType] = None
    cron_expression: str = "0 2 * * *"  # 默认每天凌晨2点
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'schedule_id': self.schedule_id,
            'task_type': self.task_type.value,
            'asset_type': self.asset_type.value if self.asset_type else None,
            'cron_expression': self.cron_expression,
            'enabled': self.enabled,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'parameters': self.parameters
        }

class DatabaseMaintenanceEngine:
    """
    数据库维护和优化引擎

    核心功能：
    1. 数据库健康检查和监控
    2. 性能分析和优化建议
    3. 索引管理和优化
    4. 数据清理和归档
    5. 自动化维护任务调度
    6. 备份和恢复管理
    """

    def __init__(self, max_workers: int = 2):
        """初始化数据库维护引擎"""
        # 核心组件
        self.asset_db_manager = get_asset_database_manager()
        self.query_engine = get_cross_asset_query_engine()

        # 任务管理
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, MaintenanceTask] = {}
        self._schedules: Dict[str, MaintenanceSchedule] = {}

        # 维护历史
        self._maintenance_history: List[MaintenanceTask] = []
        self._max_history_size = 1000

        # 配置
        self._config = {
            'backup_retention_days': 30,
            'archive_threshold_days': 365,
            'vacuum_threshold_ratio': 0.3,
            'health_check_interval_hours': 24,
            'performance_threshold_ms': 1000,
            'max_concurrent_tasks': max_workers
        }

        # 线程锁
        self._engine_lock = threading.RLock()
        self._tasks_lock = threading.RLock()

        # 初始化默认维护计划
        self._initialize_default_schedules()

        logger.info("DatabaseMaintenanceEngine 初始化完成")

    def _initialize_default_schedules(self):
        """初始化默认维护计划"""
        default_schedules = [
            MaintenanceSchedule(
                schedule_id="daily_health_check",
                task_type=MaintenanceTaskType.HEALTH_CHECK,
                cron_expression="0 2 * * *",  # 每天凌晨2点
                parameters={'full_check': False}
            ),
            MaintenanceSchedule(
                schedule_id="weekly_vacuum",
                task_type=MaintenanceTaskType.VACUUM,
                cron_expression="0 3 * * 0",  # 每周日凌晨3点
                parameters={'analyze_after': True}
            ),
            MaintenanceSchedule(
                schedule_id="monthly_full_check",
                task_type=MaintenanceTaskType.HEALTH_CHECK,
                cron_expression="0 4 1 * *",  # 每月1号凌晨4点
                parameters={'full_check': True}
            ),
            MaintenanceSchedule(
                schedule_id="monthly_backup",
                task_type=MaintenanceTaskType.BACKUP,
                cron_expression="0 5 1 * *",  # 每月1号凌晨5点
                parameters={'compress': True}
            )
        ]

        with self._engine_lock:
            for schedule in default_schedules:
                self._schedules[schedule.schedule_id] = schedule

        logger.debug(f"初始化了 {len(default_schedules)} 个默认维护计划")

    def create_maintenance_task(self, task_type: MaintenanceTaskType,
                                asset_type: Optional[AssetType] = None,
                                priority: MaintenancePriority = MaintenancePriority.NORMAL,
                                parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        创建维护任务

        Args:
            task_type: 任务类型
            asset_type: 资产类型（None表示所有资产）
            priority: 优先级
            parameters: 任务参数

        Returns:
            任务ID
        """
        task_id = f"{task_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(object())}"

        task = MaintenanceTask(
            task_id=task_id,
            task_type=task_type,
            asset_type=asset_type,
            priority=priority,
            parameters=parameters or {}
        )

        with self._engine_lock:
            self._tasks[task_id] = task

        logger.info(f"创建维护任务: {task_id} ({task_type.value})")
        return task_id

    def execute_task(self, task_id: str) -> bool:
        """
        执行维护任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功提交执行
        """
        with self._engine_lock:
            task = self._tasks.get(task_id)

        if not task:
            logger.error(f"任务不存在: {task_id}")
            return False

        if task.status != MaintenanceStatus.PENDING:
            logger.warning(f"任务状态不允许执行: {task_id} ({task.status.value})")
            return False

        # 提交到线程池执行
        future = self.executor.submit(self._execute_task_internal, task)

        logger.info(f"提交维护任务执行: {task_id}")
        return True

    def _execute_task_internal(self, task: MaintenanceTask):
        """内部任务执行方法"""
        task.status = MaintenanceStatus.RUNNING
        task.started_at = datetime.now()
        task.progress = 0.0

        try:
            logger.info(f"开始执行维护任务: {task.task_id} ({task.task_type.value})")

            # 根据任务类型执行相应的维护操作
            if task.task_type == MaintenanceTaskType.HEALTH_CHECK:
                result = self._execute_health_check(task)
            elif task.task_type == MaintenanceTaskType.PERFORMANCE_ANALYSIS:
                result = self._execute_performance_analysis(task)
            elif task.task_type == MaintenanceTaskType.INDEX_OPTIMIZATION:
                result = self._execute_index_optimization(task)
            elif task.task_type == MaintenanceTaskType.DATA_CLEANUP:
                result = self._execute_data_cleanup(task)
            elif task.task_type == MaintenanceTaskType.STATISTICS_UPDATE:
                result = self._execute_statistics_update(task)
            elif task.task_type == MaintenanceTaskType.VACUUM:
                result = self._execute_vacuum(task)
            elif task.task_type == MaintenanceTaskType.INTEGRITY_CHECK:
                result = self._execute_integrity_check(task)
            elif task.task_type == MaintenanceTaskType.BACKUP:
                result = self._execute_backup(task)
            elif task.task_type == MaintenanceTaskType.ARCHIVE:
                result = self._execute_archive(task)
            else:
                raise ValueError(f"不支持的任务类型: {task.task_type}")

            task.result = result
            task.status = MaintenanceStatus.COMPLETED
            task.progress = 100.0

            logger.info(f"维护任务执行完成: {task.task_id}")

        except Exception as e:
            task.error_message = str(e)
            task.status = MaintenanceStatus.FAILED
            logger.error(f"维护任务执行失败: {task.task_id}, {e}")

        finally:
            task.completed_at = datetime.now()

            # 添加到历史记录
            with self._engine_lock:
                self._maintenance_history.append(task)

                # 限制历史记录大小
                if len(self._maintenance_history) > self._max_history_size:
                    self._maintenance_history = self._maintenance_history[-self._max_history_size:]

    def _execute_health_check(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行健康检查"""
        full_check = task.parameters.get('full_check', False)
        target_assets = self._get_target_assets(task.asset_type)

        health_reports = []

        for i, asset_type in enumerate(target_assets):
            try:
                task.progress = (i / len(target_assets)) * 100

                report = self._check_database_health(asset_type, full_check)
                health_reports.append(report.to_dict())

            except Exception as e:
                logger.error(f"健康检查失败 {asset_type.value}: {e}")
                health_reports.append({
                    'asset_type': asset_type.value,
                    'error': str(e)
                })

        return {
            'health_reports': health_reports,
            'overall_health': self._calculate_overall_health(health_reports),
            'check_time': datetime.now().isoformat(),
            'full_check': full_check
        }

    def _check_database_health(self, asset_type: AssetType, full_check: bool = False) -> DatabaseHealthReport:
        """检查单个数据库健康状况"""
        db_path = self.asset_db_manager.get_database_path(asset_type)

        # 基本信息
        file_size_mb = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0

        issues = []
        recommendations = []

        with self.asset_db_manager.get_connection(asset_type) as conn:
            # 获取表信息
            tables_result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_count = len(tables_result)

            # 获取索引信息
            indexes_result = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
            index_count = len(indexes_result)

            # 获取记录总数
            record_count = 0
            for table in tables_result:
                table_name = table[0]
                try:
                    count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                    record_count += count_result[0] if count_result else 0
                except Exception as e:
                    issues.append(f"无法统计表 {table_name} 的记录数: {e}")

            # 检查碎片化程度
            fragmentation_ratio = 0.0
            try:
                pragma_result = conn.execute("PRAGMA freelist_count").fetchone()
                free_pages = pragma_result[0] if pragma_result else 0

                page_count_result = conn.execute("PRAGMA page_count").fetchone()
                total_pages = page_count_result[0] if page_count_result else 1

                fragmentation_ratio = free_pages / total_pages if total_pages > 0 else 0

                if fragmentation_ratio > self._config['vacuum_threshold_ratio']:
                    issues.append(f"数据库碎片化严重: {fragmentation_ratio:.2%}")
                    recommendations.append("建议执行VACUUM操作")

            except Exception as e:
                issues.append(f"无法检查碎片化程度: {e}")

            # 尝试获取上次vacuum时间
            last_vacuum = None
            try:
                # 尝试从元数据表获取
                metadata_result = conn.execute("""
                    SELECT last_vacuum FROM system_metadata 
                    WHERE table_name = 'main' LIMIT 1
                """).fetchone()
                if metadata_result:
                    last_vacuum = datetime.fromisoformat(metadata_result[0])
            except Exception as e:
                # 元数据表不存在或查询失败，尝试从vacuum记录表获取
                try:
                    vacuum_result = conn.execute("""
                        SELECT MAX(completed_at) FROM maintenance_tasks 
                        WHERE task_type = 'vacuum'
                    """).fetchone()
                    if vacuum_result and vacuum_result[0]:
                        last_vacuum = vacuum_result[0]
                except Exception:
                    pass

            # 如果都无法获取，记录警告
            if last_vacuum is None:
                logger.debug(f"无法获取 {asset_type.value} 数据库的上次vacuum时间")
            if full_check:
                try:
                    integrity_result = conn.execute("PRAGMA integrity_check").fetchone()
                    if integrity_result and integrity_result[0] != "ok":
                        issues.append(f"数据库完整性问题: {integrity_result[0]}")
                        recommendations.append("建议进行数据库修复")
                except Exception as e:
                    issues.append(f"完整性检查失败: {e}")

        # 计算性能分数
        performance_score = self._calculate_performance_score(
            file_size_mb, fragmentation_ratio, len(issues)
        )

        # 文件大小检查
        if file_size_mb > 1000:  # 超过1GB
            recommendations.append("考虑数据归档以减小数据库大小")

        return DatabaseHealthReport(
            asset_type=asset_type,
            database_path=db_path,
            file_size_mb=file_size_mb,
            table_count=table_count,
            record_count=record_count,
            index_count=index_count,
            last_vacuum=last_vacuum,
            fragmentation_ratio=fragmentation_ratio,
            performance_score=performance_score,
            issues=issues,
            recommendations=recommendations
        )

    def _calculate_performance_score(self, file_size_mb: float,
                                     fragmentation_ratio: float,
                                     issue_count: int) -> float:
        """计算性能分数"""
        score = 100.0

        # 文件大小影响
        if file_size_mb > 1000:
            score -= 10
        elif file_size_mb > 500:
            score -= 5

        # 碎片化影响
        score -= fragmentation_ratio * 50

        # 问题数量影响
        score -= issue_count * 5

        return max(0.0, min(100.0, score))

    def _calculate_overall_health(self, health_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算整体健康状况"""
        if not health_reports:
            return {'status': 'unknown', 'score': 0.0}

        valid_reports = [r for r in health_reports if 'error' not in r]
        if not valid_reports:
            return {'status': 'error', 'score': 0.0}

        avg_score = sum(r.get('performance_score', 0) for r in valid_reports) / len(valid_reports)
        total_issues = sum(len(r.get('issues', [])) for r in valid_reports)

        if avg_score >= 90 and total_issues == 0:
            status = 'excellent'
        elif avg_score >= 80 and total_issues <= 2:
            status = 'good'
        elif avg_score >= 60 and total_issues <= 5:
            status = 'fair'
        else:
            status = 'poor'

        return {
            'status': status,
            'score': avg_score,
            'total_issues': total_issues,
            'database_count': len(valid_reports)
        }

    def _execute_performance_analysis(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行性能分析"""
        target_assets = self._get_target_assets(task.asset_type)
        analysis_results = []

        for i, asset_type in enumerate(target_assets):
            try:
                task.progress = (i / len(target_assets)) * 100

                # 执行性能测试查询
                test_queries = [
                    "SELECT COUNT(*) FROM historical_kline_data",
                    "SELECT symbol, COUNT(*) FROM historical_kline_data GROUP BY symbol LIMIT 10",
                    "SELECT * FROM historical_kline_data ORDER BY timestamp DESC LIMIT 100"
                ]

                query_performance = []
                for query in test_queries:
                    start_time = time.time()
                    try:
                        with self.asset_db_manager.get_connection(asset_type) as conn:
                            conn.execute(query).fetchall()

                        execution_time_ms = (time.time() - start_time) * 1000
                        query_performance.append({
                            'query': query,
                            'execution_time_ms': execution_time_ms,
                            'status': 'success'
                        })
                    except Exception as e:
                        query_performance.append({
                            'query': query,
                            'error': str(e),
                            'status': 'failed'
                        })

                analysis_results.append({
                    'asset_type': asset_type.value,
                    'query_performance': query_performance,
                    'avg_query_time_ms': np.mean([q.get('execution_time_ms', 0)
                                                  for q in query_performance
                                                  if q['status'] == 'success'])
                })

            except Exception as e:
                logger.error(f"性能分析失败 {asset_type.value}: {e}")
                analysis_results.append({
                    'asset_type': asset_type.value,
                    'error': str(e)
                })

        return {
            'analysis_results': analysis_results,
            'analysis_time': datetime.now().isoformat()
        }

    def _execute_vacuum(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行数据库压缩"""
        target_assets = self._get_target_assets(task.asset_type)
        analyze_after = task.parameters.get('analyze_after', True)

        vacuum_results = []

        for i, asset_type in enumerate(target_assets):
            try:
                task.progress = (i / len(target_assets)) * 90  # 留10%给analyze

                # 获取压缩前的大小
                db_path = self.asset_db_manager.get_database_path(asset_type)
                size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0

                start_time = time.time()

                with self.asset_db_manager.get_connection(asset_type) as conn:
                    # 执行VACUUM
                    conn.execute("VACUUM")

                    # 可选：更新统计信息
                    if analyze_after:
                        conn.execute("ANALYZE")

                execution_time_ms = (time.time() - start_time) * 1000
                size_after = os.path.getsize(db_path) if os.path.exists(db_path) else 0

                vacuum_results.append({
                    'asset_type': asset_type.value,
                    'size_before_mb': size_before / (1024 * 1024),
                    'size_after_mb': size_after / (1024 * 1024),
                    'space_saved_mb': (size_before - size_after) / (1024 * 1024),
                    'execution_time_ms': execution_time_ms,
                    'analyze_executed': analyze_after,
                    'status': 'success'
                })

                logger.info(f"VACUUM完成 {asset_type.value}: "
                            f"节省空间 {(size_before - size_after) / (1024 * 1024):.2f}MB")

            except Exception as e:
                logger.error(f"VACUUM失败 {asset_type.value}: {e}")
                vacuum_results.append({
                    'asset_type': asset_type.value,
                    'error': str(e),
                    'status': 'failed'
                })

        task.progress = 100.0

        return {
            'vacuum_results': vacuum_results,
            'total_space_saved_mb': sum(r.get('space_saved_mb', 0) for r in vacuum_results),
            'vacuum_time': datetime.now().isoformat()
        }

    def _execute_backup(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行数据备份"""
        target_assets = self._get_target_assets(task.asset_type)
        compress = task.parameters.get('compress', False)
        backup_dir = task.parameters.get('backup_dir', 'backups')

        # 确保备份目录存在
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        backup_results = []

        for i, asset_type in enumerate(target_assets):
            try:
                task.progress = (i / len(target_assets)) * 100

                # 使用AssetSeparatedDatabaseManager的备份功能
                backup_file = self.asset_db_manager.backup_database(asset_type)

                backup_results.append({
                    'asset_type': asset_type.value,
                    'backup_file': backup_file,
                    'status': 'success'
                })

                logger.info(f"备份完成 {asset_type.value}: {backup_file}")

            except Exception as e:
                logger.error(f"备份失败 {asset_type.value}: {e}")
                backup_results.append({
                    'asset_type': asset_type.value,
                    'error': str(e),
                    'status': 'failed'
                })

        return {
            'backup_results': backup_results,
            'backup_time': datetime.now().isoformat(),
            'backup_directory': str(backup_path)
        }

    def _execute_integrity_check(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行完整性检查"""
        target_assets = self._get_target_assets(task.asset_type)
        integrity_results = []

        for i, asset_type in enumerate(target_assets):
            try:
                task.progress = (i / len(target_assets)) * 100

                with self.asset_db_manager.get_connection(asset_type) as conn:
                    # 执行完整性检查
                    integrity_result = conn.execute("PRAGMA integrity_check").fetchall()

                    is_ok = len(integrity_result) == 1 and integrity_result[0][0] == "ok"

                    integrity_results.append({
                        'asset_type': asset_type.value,
                        'status': 'ok' if is_ok else 'issues_found',
                        'issues': [] if is_ok else [row[0] for row in integrity_result],
                        'check_result': 'success'
                    })

            except Exception as e:
                logger.error(f"完整性检查失败 {asset_type.value}: {e}")
                integrity_results.append({
                    'asset_type': asset_type.value,
                    'error': str(e),
                    'check_result': 'failed'
                })

        return {
            'integrity_results': integrity_results,
            'check_time': datetime.now().isoformat()
        }

    def _execute_index_optimization(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行索引优化"""
        # 简化实现，主要是重建统计信息
        return self._execute_statistics_update(task)

    def _execute_data_cleanup(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行数据清理"""
        target_assets = self._get_target_assets(task.asset_type)
        cleanup_threshold_days = task.parameters.get('cleanup_threshold_days',
                                                     self._config['archive_threshold_days'])

        cleanup_results = []

        for i, asset_type in enumerate(target_assets):
            try:
                task.progress = (i / len(target_assets)) * 100

                cutoff_date = datetime.now() - timedelta(days=cleanup_threshold_days)

                with self.asset_db_manager.get_connection(asset_type) as conn:
                    # 清理过期数据（示例：清理超过阈值的历史数据）
                    delete_result = conn.execute(
                        "DELETE FROM historical_kline_data WHERE timestamp < ?",
                        (cutoff_date,)
                    )

                    deleted_count = delete_result.rowcount

                    cleanup_results.append({
                        'asset_type': asset_type.value,
                        'deleted_records': deleted_count,
                        'cutoff_date': cutoff_date.isoformat(),
                        'status': 'success'
                    })

            except Exception as e:
                logger.error(f"数据清理失败 {asset_type.value}: {e}")
                cleanup_results.append({
                    'asset_type': asset_type.value,
                    'error': str(e),
                    'status': 'failed'
                })

        return {
            'cleanup_results': cleanup_results,
            'cleanup_time': datetime.now().isoformat()
        }

    def _execute_statistics_update(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行统计信息更新"""
        target_assets = self._get_target_assets(task.asset_type)
        update_results = []

        for i, asset_type in enumerate(target_assets):
            try:
                task.progress = (i / len(target_assets)) * 100

                start_time = time.time()

                with self.asset_db_manager.get_connection(asset_type) as conn:
                    # 更新统计信息
                    conn.execute("ANALYZE")

                execution_time_ms = (time.time() - start_time) * 1000

                update_results.append({
                    'asset_type': asset_type.value,
                    'execution_time_ms': execution_time_ms,
                    'status': 'success'
                })

            except Exception as e:
                logger.error(f"统计信息更新失败 {asset_type.value}: {e}")
                update_results.append({
                    'asset_type': asset_type.value,
                    'error': str(e),
                    'status': 'failed'
                })

        return {
            'update_results': update_results,
            'update_time': datetime.now().isoformat()
        }

    def _execute_archive(self, task: MaintenanceTask) -> Dict[str, Any]:
        """执行数据归档"""
        # 简化实现，实际应该将旧数据移动到归档存储
        return {
            'message': '数据归档功能待实现',
            'archive_time': datetime.now().isoformat()
        }

    def _get_target_assets(self, asset_type: Optional[AssetType]) -> List[AssetType]:
        """获取目标资产类型列表"""
        if asset_type:
            return [asset_type]
        else:
            # 返回所有有数据库的资产类型
            available_assets = []
            for at in AssetType:
                try:
                    db_path = self.asset_db_manager.get_database_path(at)
                    if os.path.exists(db_path):
                        available_assets.append(at)
                except Exception:
                    continue
            return available_assets

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with self._engine_lock:
            task = self._tasks.get(task_id)

        return task.to_dict() if task else None

    def list_tasks(self, status_filter: Optional[MaintenanceStatus] = None) -> List[Dict[str, Any]]:
        """列出任务"""
        with self._engine_lock:
            tasks = list(self._tasks.values())

        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]

        return [task.to_dict() for task in tasks]

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """列出所有活跃任务"""
        active_tasks = []
        with self._tasks_lock:
            for task_id, task in self._tasks.items():
                if task.status in [MaintenanceStatus.PENDING, MaintenanceStatus.RUNNING]:
                    active_tasks.append({
                        'task_id': task_id,
                        'task_type': task.task_type.value,
                        'status': task.status.value,
                        'created_at': task.created_at.isoformat(),
                        'asset_type': task.asset_type.value if task.asset_type else None
                    })
        return active_tasks

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._engine_lock:
            task = self._tasks.get(task_id)

        if not task:
            return False

        if task.status == MaintenanceStatus.PENDING:
            task.status = MaintenanceStatus.CANCELLED
            return True

        return False

    def get_maintenance_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取维护历史"""
        with self._engine_lock:
            history = self._maintenance_history[-limit:]

        return [task.to_dict() for task in history]

    def get_system_health_summary(self) -> Dict[str, Any]:
        """获取系统健康摘要"""
        # 创建并执行健康检查任务
        task_id = self.create_maintenance_task(
            MaintenanceTaskType.HEALTH_CHECK,
            parameters={'full_check': False}
        )

        # 同步执行
        with self._engine_lock:
            task = self._tasks[task_id]

        result = self._execute_health_check(task)

        return {
            'overall_health': result.get('overall_health', {}),
            'database_count': len(result.get('health_reports', [])),
            'last_check': datetime.now().isoformat(),
            'issues_count': sum(len(r.get('issues', [])) for r in result.get('health_reports', []))
        }

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """列出所有活跃任务"""
        active_tasks = []
        with self._tasks_lock:
            for task_id, task in self._tasks.items():
                if task.status in [MaintenanceStatus.PENDING, MaintenanceStatus.RUNNING]:
                    active_tasks.append({
                        'task_id': task_id,
                        'task_type': task.task_type.value,
                        'status': task.status.value,
                        'created_at': task.created_at.isoformat(),
                        'asset_type': task.asset_type.value if task.asset_type else None
                    })
        return active_tasks

    def close(self):
        """关闭维护引擎"""
        self.executor.shutdown(wait=True)
        logger.info("DatabaseMaintenanceEngine 已关闭")

# 全局实例
_maintenance_engine: Optional[DatabaseMaintenanceEngine] = None
_engine_lock = threading.Lock()

def get_database_maintenance_engine() -> DatabaseMaintenanceEngine:
    """获取全局数据库维护引擎实例"""
    global _maintenance_engine

    with _engine_lock:
        if _maintenance_engine is None:
            _maintenance_engine = DatabaseMaintenanceEngine()

        return _maintenance_engine

def initialize_database_maintenance_engine(max_workers: int = 2) -> DatabaseMaintenanceEngine:
    """初始化数据库维护引擎"""
    global _maintenance_engine

    with _engine_lock:
        if _maintenance_engine:
            _maintenance_engine.close()

        _maintenance_engine = DatabaseMaintenanceEngine(max_workers=max_workers)
        logger.info("DatabaseMaintenanceEngine 已初始化")

        return _maintenance_engine
