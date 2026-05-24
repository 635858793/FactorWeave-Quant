#!/usr/bin/env python3
"""
统一任务状态管理器

提供线程安全的任务状态跟踪、持久化和恢复功能
支持任务创建、执行、暂停、取消和完成的完整生命周期管理
"""

import json
import sqlite3
import threading
import time
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from loguru import logger

from ..database.unified_sqlite_access import UnifiedSQLiteAccess


class TaskStatus(Enum):
    """任务状态枚举"""
    CREATED = "created"           # 已创建
    PENDING = "pending"           # 等待执行
    INITIALIZING = "initializing"  # 初始化中
    RUNNING = "running"           # 运行中
    PAUSED = "paused"            # 已暂停
    RESUMING = "resuming"        # 恢复中
    COMPLETING = "completing"    # 完成中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消
    TIMEOUT = "timeout"          # 超时
    ERROR = "error"              # 错误


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class TaskStatusInfo:
    """任务状态信息"""
    task_id: str
    status: TaskStatus
    priority: TaskPriority = TaskPriority.NORMAL
    created_time: datetime = field(default_factory=datetime.now)
    updated_time: datetime = field(default_factory=datetime.now)
    started_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    progress: float = 0.0
    message: str = ""
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理枚举类型
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        # 处理日期时间
        for key in ['created_time', 'updated_time', 'started_time', 'completed_time']:
            if data[key]:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskStatusInfo':
        """从字典创建"""
        # 处理枚举类型
        data['status'] = TaskStatus(data['status'])
        data['priority'] = TaskPriority(data['priority'])
        # 处理日期时间
        for key in ['created_time', 'updated_time', 'started_time', 'completed_time']:
            if data[key]:
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)

    @property
    def is_active(self) -> bool:
        """是否为活跃状态"""
        return self.status in [TaskStatus.PENDING, TaskStatus.INITIALIZING,
                               TaskStatus.RUNNING, TaskStatus.RESUMING]

    @property
    def is_finished(self) -> bool:
        """是否已结束"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED,
                               TaskStatus.CANCELLED, TaskStatus.TIMEOUT, TaskStatus.ERROR]

    @property
    def execution_time(self) -> Optional[float]:
        """执行时间（秒）"""
        if self.started_time and self.completed_time:
            return (self.completed_time - self.started_time).total_seconds()
        elif self.started_time and not self.completed_time:
            return (datetime.now() - self.started_time).total_seconds()
        return None


class TaskStatusTransition:
    """任务状态转换规则"""

    # 定义合法的状态转换
    VALID_TRANSITIONS = {
        TaskStatus.CREATED: [TaskStatus.PENDING, TaskStatus.CANCELLED],
        TaskStatus.PENDING: [TaskStatus.INITIALIZING, TaskStatus.CANCELLED],
        TaskStatus.INITIALIZING: [TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.RUNNING: [TaskStatus.PAUSED, TaskStatus.COMPLETING, TaskStatus.FAILED,
                             TaskStatus.CANCELLED, TaskStatus.TIMEOUT],
        TaskStatus.PAUSED: [TaskStatus.RESUMING, TaskStatus.CANCELLED],
        TaskStatus.RESUMING: [TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.COMPLETING: [TaskStatus.COMPLETED, TaskStatus.FAILED],
        TaskStatus.COMPLETED: [],  # 终态
        TaskStatus.FAILED: [TaskStatus.PENDING],  # 可重试
        TaskStatus.CANCELLED: [],  # 终态
        TaskStatus.TIMEOUT: [TaskStatus.PENDING],  # 可重试
        TaskStatus.ERROR: [TaskStatus.PENDING]  # 可重试
    }

    @classmethod
    def is_valid_transition(cls, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """检查状态转换是否合法"""
        return to_status in cls.VALID_TRANSITIONS.get(from_status, [])

    @classmethod
    def get_valid_next_states(cls, current_status: TaskStatus) -> List[TaskStatus]:
        """获取当前状态的合法后续状态"""
        return cls.VALID_TRANSITIONS.get(current_status, [])


class TaskStatusManager:
    """
    统一任务状态管理器

    功能特性：
    1. 线程安全的状态管理
    2. 状态转换验证
    3. 持久化存储
    4. 状态变更通知
    5. 任务恢复和清理
    6. 性能监控
    7. 状态查询和统计
    """

    def __init__(self, db_path: Optional[str] = None, enable_persistence: bool = True):
        """
        初始化任务状态管理器

        Args:
            db_path: 数据库路径
            enable_persistence: 是否启用持久化
        """
        # 状态存储
        self._task_states: Dict[str, TaskStatusInfo] = {}
        self._state_lock = threading.RLock()

        # 持久化配置
        self.enable_persistence = enable_persistence
        self.db_path = db_path or "data/task_status.sqlite"
        self._db_lock = threading.Lock()

        # 状态变更监听器
        self._status_listeners: List[Callable[[str, TaskStatus, TaskStatus], None]] = []
        self._listener_lock = threading.Lock()

        # 统计信息
        self._stats = {
            'total_created': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cancelled': 0,
            'active_tasks': 0
        }

        # 初始化持久化存储
        if self.enable_persistence:
            self._init_database()
            self._load_tasks_from_db()

        logger.info(f"任务状态管理器初始化完成 - 持久化: {'启用' if enable_persistence else '禁用'}")

    def _init_database(self):
        """初始化数据库"""
        try:
            # 确保数据目录存在
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS task_status (
                        task_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        created_time TEXT NOT NULL,
                        updated_time TEXT NOT NULL,
                        started_time TEXT,
                        completed_time TEXT,
                        progress REAL DEFAULT 0.0,
                        message TEXT DEFAULT '',
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        timeout_seconds INTEGER DEFAULT 300,
                        metadata TEXT DEFAULT '{}'
                    )
                """)

                # 创建索引
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON task_status(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_created_time ON task_status(created_time)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON task_status(priority)")

            logger.info(f"任务状态数据库初始化完成: {self.db_path}")

        except Exception as e:
            logger.error(f"初始化数据库失败: {e}")
            self.enable_persistence = False

    def _load_tasks_from_db(self):
        """从数据库加载任务状态"""
        if not self.enable_persistence:
            return

        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM task_status")

                loaded_count = 0
                for row in cursor:
                    try:
                        # 转换数据
                        data = dict(row)
                        data['metadata'] = json.loads(data['metadata'])

                        # 创建状态信息对象
                        status_info = TaskStatusInfo.from_dict(data)

                        with self._state_lock:
                            self._task_states[status_info.task_id] = status_info

                        loaded_count += 1

                    except Exception as e:
                        logger.warning(f"加载任务状态失败 {row['task_id']}: {e}")

                logger.info(f"从数据库加载了 {loaded_count} 个任务状态")

        except Exception as e:
            logger.error(f"从数据库加载任务状态失败: {e}")

    def _save_task_to_db(self, status_info: TaskStatusInfo):
        """保存任务状态到数据库"""
        if not self.enable_persistence:
            return

        try:
            with self._db_lock:
                db = UnifiedSQLiteAccess.get_instance(self.db_path)
                with db.get_connection() as conn:
                    data = status_info.to_dict()

                    conn.execute("""
                        INSERT OR REPLACE INTO task_status (
                            task_id, status, priority, created_time, updated_time,
                            started_time, completed_time, progress, message,
                            error_message, retry_count, max_retries, timeout_seconds, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        data['task_id'], data['status'], data['priority'],
                        data['created_time'], data['updated_time'],
                        data['started_time'], data['completed_time'],
                        data['progress'], data['message'], data['error_message'],
                        data['retry_count'], data['max_retries'], data['timeout_seconds'],
                        json.dumps(data['metadata'])
                    ])

        except Exception as e:
            logger.error(f"保存任务状态到数据库失败 {status_info.task_id}: {e}")

    def create_task(self, task_id: str, priority: TaskPriority = TaskPriority.NORMAL,
                    timeout_seconds: int = 300, max_retries: int = 3,
                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        创建新任务

        Args:
            task_id: 任务ID
            priority: 任务优先级
            timeout_seconds: 超时时间（秒）
            max_retries: 最大重试次数
            metadata: 元数据

        Returns:
            bool: 是否创建成功
        """
        try:
            with self._state_lock:
                if task_id in self._task_states:
                    logger.warning(f"任务已存在: {task_id}")
                    return False

                # 创建任务状态信息
                status_info = TaskStatusInfo(
                    task_id=task_id,
                    status=TaskStatus.CREATED,
                    priority=priority,
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                    metadata=metadata or {}
                )

                self._task_states[task_id] = status_info
                self._stats['total_created'] += 1

            # 保存到数据库
            self._save_task_to_db(status_info)

            # 通知监听器
            self._notify_status_change(task_id, None, TaskStatus.CREATED)

            logger.info(f"创建任务: {task_id} (优先级: {priority.name})")
            return True

        except Exception as e:
            logger.error(f"创建任务失败 {task_id}: {e}")
            return False

    def update_status(self, task_id: str, new_status: TaskStatus,
                      message: str = "", error_message: Optional[str] = None,
                      progress: Optional[float] = None) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            new_status: 新状态
            message: 状态消息
            error_message: 错误消息
            progress: 进度（0-100）

        Returns:
            bool: 是否更新成功
        """
        try:
            with self._state_lock:
                if task_id not in self._task_states:
                    logger.error(f"任务不存在: {task_id}")
                    return False

                status_info = self._task_states[task_id]
                old_status = status_info.status

                # 验证状态转换
                if not TaskStatusTransition.is_valid_transition(old_status, new_status):
                    logger.error(f"非法状态转换: {task_id} {old_status.value} -> {new_status.value}")
                    return False

                # 更新状态信息
                status_info.status = new_status
                status_info.updated_time = datetime.now()
                status_info.message = message

                if error_message:
                    status_info.error_message = error_message

                if progress is not None:
                    status_info.progress = max(0.0, min(100.0, progress))

                # 更新特殊时间戳
                if new_status == TaskStatus.RUNNING and not status_info.started_time:
                    status_info.started_time = datetime.now()
                elif new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED,
                                    TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                    if not status_info.completed_time:
                        status_info.completed_time = datetime.now()

                # 更新统计
                self._update_stats(old_status, new_status)

            # 保存到数据库
            self._save_task_to_db(status_info)

            # 通知监听器
            self._notify_status_change(task_id, old_status, new_status)

            logger.info(f"更新任务状态: {task_id} {old_status.value} -> {new_status.value}")
            return True

        except Exception as e:
            logger.error(f"更新任务状态失败 {task_id}: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[TaskStatusInfo]:
        """获取任务状态信息"""
        with self._state_lock:
            return self._task_states.get(task_id)

    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskStatusInfo]:
        """根据状态获取任务列表"""
        with self._state_lock:
            return [info for info in self._task_states.values() if info.status == status]

    def get_active_tasks(self) -> List[TaskStatusInfo]:
        """获取活跃任务列表"""
        with self._state_lock:
            return [info for info in self._task_states.values() if info.is_active]

    def get_finished_tasks(self) -> List[TaskStatusInfo]:
        """获取已结束任务列表"""
        with self._state_lock:
            return [info for info in self._task_states.values() if info.is_finished]

    def get_all_tasks(self) -> List[TaskStatusInfo]:
        """获取所有任务列表"""
        with self._state_lock:
            return list(self._task_states.values())

    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        try:
            with self._state_lock:
                if task_id not in self._task_states:
                    return False

                status_info = self._task_states[task_id]

                # 只能移除已结束的任务
                if not status_info.is_finished:
                    logger.warning(f"不能移除活跃任务: {task_id}")
                    return False

                del self._task_states[task_id]

            # 从数据库删除
            if self.enable_persistence:
                with self._db_lock:
                    db = UnifiedSQLiteAccess.get_instance(self.db_path)
                    with db.get_connection() as conn:
                        conn.execute("DELETE FROM task_status WHERE task_id = ?", [task_id])

            logger.info(f"移除任务: {task_id}")
            return True

        except Exception as e:
            logger.error(f"移除任务失败 {task_id}: {e}")
            return False

    def cleanup_finished_tasks(self, older_than_hours: int = 24) -> int:
        """清理已完成的旧任务"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
            removed_count = 0

            with self._state_lock:
                tasks_to_remove = []
                for task_id, status_info in self._task_states.items():
                    if (status_info.is_finished and
                        status_info.completed_time and
                            status_info.completed_time < cutoff_time):
                        tasks_to_remove.append(task_id)

                for task_id in tasks_to_remove:
                    del self._task_states[task_id]
                    removed_count += 1

            # 从数据库批量删除
            if self.enable_persistence and tasks_to_remove:
                with self._db_lock:
                    db = UnifiedSQLiteAccess.get_instance(self.db_path)
                    with db.get_connection() as conn:
                        placeholders = ','.join(['?'] * len(tasks_to_remove))
                        conn.execute(f"DELETE FROM task_status WHERE task_id IN ({placeholders})",
                                     tasks_to_remove)

            logger.info(f"清理了 {removed_count} 个旧任务")
            return removed_count

        except Exception as e:
            logger.error(f"清理旧任务失败: {e}")
            return 0

    def add_status_listener(self, listener: Callable[[str, TaskStatus, TaskStatus], None]):
        """添加状态变更监听器"""
        with self._listener_lock:
            self._status_listeners.append(listener)

    def remove_status_listener(self, listener: Callable[[str, TaskStatus, TaskStatus], None]):
        """移除状态变更监听器"""
        with self._listener_lock:
            if listener in self._status_listeners:
                self._status_listeners.remove(listener)

    def _notify_status_change(self, task_id: str, old_status: Optional[TaskStatus],
                              new_status: TaskStatus):
        """通知状态变更"""
        with self._listener_lock:
            for listener in self._status_listeners:
                try:
                    listener(task_id, old_status, new_status)
                except Exception as e:
                    logger.error(f"状态监听器执行失败: {e}")

    def _update_stats(self, old_status: TaskStatus, new_status: TaskStatus):
        """更新统计信息"""
        # 更新完成统计
        if new_status == TaskStatus.COMPLETED:
            self._stats['total_completed'] += 1
        elif new_status == TaskStatus.FAILED:
            self._stats['total_failed'] += 1
        elif new_status == TaskStatus.CANCELLED:
            self._stats['total_cancelled'] += 1

        # 更新活跃任务数
        old_active = old_status in [TaskStatus.PENDING, TaskStatus.INITIALIZING,
                                    TaskStatus.RUNNING, TaskStatus.RESUMING] if old_status else False
        new_active = new_status in [TaskStatus.PENDING, TaskStatus.INITIALIZING,
                                    TaskStatus.RUNNING, TaskStatus.RESUMING]

        if new_active and not old_active:
            self._stats['active_tasks'] += 1
        elif old_active and not new_active:
            self._stats['active_tasks'] = max(0, self._stats['active_tasks'] - 1)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._state_lock:
            stats = self._stats.copy()

            # 计算成功率
            total_finished = stats['total_completed'] + stats['total_failed'] + stats['total_cancelled']
            if total_finished > 0:
                stats['success_rate'] = (stats['total_completed'] / total_finished) * 100
            else:
                stats['success_rate'] = 0.0

            # 按状态统计
            status_counts = {}
            for status in TaskStatus:
                status_counts[status.value] = len(self.get_tasks_by_status(status))

            stats['status_counts'] = status_counts

            return stats

    def get_task_summary(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务摘要信息"""
        status_info = self.get_task_status(task_id)
        if not status_info:
            return None

        return {
            'task_id': status_info.task_id,
            'status': status_info.status.value,
            'priority': status_info.priority.name,
            'progress': status_info.progress,
            'message': status_info.message,
            'execution_time': status_info.execution_time,
            'retry_count': status_info.retry_count,
            'created_time': status_info.created_time.isoformat(),
            'is_active': status_info.is_active,
            'is_finished': status_info.is_finished
        }

    def shutdown(self):
        """关闭管理器"""
        try:
            logger.info("关闭任务状态管理器...")

            # 清理监听器
            with self._listener_lock:
                self._status_listeners.clear()

            # 保存所有任务状态到数据库
            if self.enable_persistence:
                with self._state_lock:
                    for status_info in self._task_states.values():
                        self._save_task_to_db(status_info)

            logger.info("任务状态管理器已关闭")

        except Exception as e:
            logger.error(f"关闭任务状态管理器失败: {e}")


# 全局单例实例
_task_status_manager: Optional[TaskStatusManager] = None
_manager_lock = threading.Lock()


def get_task_status_manager() -> TaskStatusManager:
    """获取全局任务状态管理器实例"""
    global _task_status_manager

    if _task_status_manager is None:
        with _manager_lock:
            if _task_status_manager is None:
                _task_status_manager = TaskStatusManager()

    return _task_status_manager


def initialize_task_status_manager(db_path: Optional[str] = None,
                                   enable_persistence: bool = True) -> TaskStatusManager:
    """初始化全局任务状态管理器"""
    global _task_status_manager

    with _manager_lock:
        if _task_status_manager is not None:
            _task_status_manager.shutdown()

        _task_status_manager = TaskStatusManager(db_path, enable_persistence)

    return _task_status_manager
