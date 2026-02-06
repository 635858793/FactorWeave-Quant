#!/usr/bin/env python3
"""
统一任务调度器
统一调度所有异步任务，支持任务优先级、依赖关系、取消和超时等功能
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from collections import defaultdict, deque
from loguru import logger
import heapq
import weakref

from PyQt5.QtCore import QObject, pyqtSignal

from .thread_pool_manager import UnifiedThreadPoolManager, get_thread_pool_manager, TaskPriority
from .timer_manager import UnifiedTimerManager, get_timer_manager


class TaskStatus(Enum):
    """任务状态"""
    PENDING = auto()      # 等待中
    READY = auto()        # 准备执行
    RUNNING = auto()      # 运行中
    COMPLETED = auto()    # 已完成
    FAILED = auto()       # 失败
    CANCELLED = auto()    # 已取消
    TIMEOUT = auto()      # 超时


@dataclass
class TaskDependency:
    """任务依赖"""
    task_id: str
    depends_on: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)

    def is_ready(self, completed_tasks: Set[str]) -> bool:
        """检查任务是否准备好执行"""
        return all(dep in completed_tasks for dep in self.depends_on)


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    func: Callable
    submit_time: float = field(default_factory=time.time)
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    timeout: Optional[float] = None
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    status: TaskStatus = TaskStatus.PENDING
    dependencies: Set[str] = field(default_factory=set)
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 0

    def __lt__(self, other):
        """小于比较，用于优先级队列"""
        if not isinstance(other, ScheduledTask):
            return NotImplemented
        return self.submit_time < other.submit_time

    def __le__(self, other):
        """小于等于比较，用于优先级队列"""
        if not isinstance(other, ScheduledTask):
            return NotImplemented
        return self.submit_time <= other.submit_time

    def __gt__(self, other):
        """大于比较，用于优先级队列"""
        if not isinstance(other, ScheduledTask):
            return NotImplemented
        return self.submit_time > other.submit_time

    def __ge__(self, other):
        """大于等于比较，用于优先级队列"""
        if not isinstance(other, ScheduledTask):
            return NotImplemented
        return self.submit_time >= other.submit_time

    def __eq__(self, other):
        """等于比较，用于优先级队列"""
        if not isinstance(other, ScheduledTask):
            return NotImplemented
        return self.submit_time == other.submit_time

    def update_priority(self, priority: int):
        """更新优先级"""
        pass


class UnifiedTaskScheduler(QObject):
    """
    统一任务调度器

    功能：
    1. 统一调度所有异步任务
    2. 支持任务优先级
    3. 支持任务依赖关系
    4. 支持任务取消和超时
    5. 提供任务统计信息
    """

    # 信号
    task_scheduled = pyqtSignal(str)  # 任务已调度
    task_started = pyqtSignal(str)  # 任务已开始
    task_completed = pyqtSignal(str, object)  # 任务已完成
    task_failed = pyqtSignal(str, str)  # 任务已失败
    task_cancelled = pyqtSignal(str)  # 任务已取消
    task_timeout = pyqtSignal(str)  # 任务已超时

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化任务调度器"""
        if self._initialized:
            return

        super().__init__()

        self._initialized = True
        self._tasks: Dict[str, ScheduledTask] = {}
        self._task_dependencies: Dict[str, TaskDependency] = {}
        self._ready_queue: List[ScheduledTask] = []
        self._queue_lock = threading.RLock()
        self._task_counter = 0
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()

        # 获取管理器实例
        self._thread_pool_manager = get_thread_pool_manager()
        self._timer_manager = get_timer_manager()

        # 统计信息
        self._stats = {
            'total_tasks': 0,
            'pending_tasks': 0,
            'ready_tasks': 0,
            'running_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0,
            'timeout_tasks': 0,
            'total_execution_time': 0.0
        }

        # 事件总线引用（延迟加载）
        self._event_bus = None

        logger.info("统一任务调度器已初始化")

    def set_event_bus(self, event_bus):
        """设置事件总线"""
        self._event_bus = event_bus

    def schedule_task(self,
                      func: Callable,
                      args: tuple = (),
                      kwargs: dict = None,
                      priority: TaskPriority = TaskPriority.NORMAL,
                      timeout: Optional[float] = None,
                      callback: Optional[Callable] = None,
                      error_callback: Optional[Callable] = None,
                      dependencies: Optional[List[str]] = None,
                      max_retries: int = 0) -> str:
        """
        调度任务

        Args:
            func: 任务函数
            args: 位置参数
            kwargs: 关键字参数
            priority: 任务优先级
            timeout: 超时时间（秒）
            callback: 成功回调
            error_callback: 错误回调
            dependencies: 依赖的任务ID列表
            max_retries: 最大重试次数

        Returns:
            任务ID
        """
        try:
            with self._queue_lock:
                self._task_counter += 1
                task_id = f"scheduled_task_{self._task_counter}"

                task = ScheduledTask(
                    submit_time=time.time(),
                    task_id=task_id,
                    func=func,
                    args=args,
                    kwargs=kwargs or {},
                    timeout=timeout,
                    callback=callback,
                    error_callback=error_callback,
                    dependencies=set(dependencies) if dependencies else set(),
                    max_retries=max_retries
                )

                self._tasks[task_id] = task

                # 创建任务依赖关系
                if dependencies:
                    task_dep = TaskDependency(task_id=task_id, depends_on=set(dependencies))
                    self._task_dependencies[task_id] = task_dep

                    # 更新依赖任务
                    for dep_id in dependencies:
                        if dep_id not in self._task_dependencies:
                            self._task_dependencies[dep_id] = TaskDependency(task_id=dep_id)
                        self._task_dependencies[dep_id].dependents.add(task_id)

                # 检查任务是否准备好执行
                if self._is_task_ready(task):
                    task.status = TaskStatus.READY
                    heapq.heappush(self._ready_queue, task)
                    self._stats['ready_tasks'] += 1
                else:
                    task.status = TaskStatus.PENDING
                    self._stats['pending_tasks'] += 1

                self._stats['total_tasks'] += 1

            # 发送信号
            self.task_scheduled.emit(task_id)

            # 尝试执行任务（在锁外调用，避免死锁）
            self._try_execute_tasks()

            logger.debug(f"任务已调度: {task_id}, 优先级: {priority.name}, 依赖: {dependencies}, 状态: {task.status}")
            return task_id

        except Exception as e:
            logger.error(f"调度任务失败: {e}")
            return ""

    def _is_task_ready(self, task: ScheduledTask) -> bool:
        """检查任务是否准备好执行"""
        if not task.dependencies:
            return True

        return all(dep in self._completed_tasks for dep in task.dependencies)

    def _try_execute_tasks(self):
        """尝试执行准备好的任务"""
        tasks_to_execute = []

        # 先收集要执行的任务
        with self._queue_lock:
            while self._ready_queue:
                task = self._ready_queue[0]

                if task.status != TaskStatus.READY:
                    heapq.heappop(self._ready_queue)
                    continue

                # 检查任务是否仍然准备好
                if not self._is_task_ready(task):
                    heapq.heappop(self._ready_queue)
                    task.status = TaskStatus.PENDING
                    self._stats['pending_tasks'] += 1
                    self._stats['ready_tasks'] -= 1
                    continue

                # 从队列中取出任务并标记为运行中
                heapq.heappop(self._ready_queue)
                task.status = TaskStatus.RUNNING
                task.start_time = time.time()
                self._stats['running_tasks'] += 1
                self._stats['ready_tasks'] -= 1
                tasks_to_execute.append(task)

        logger.debug(f"_try_execute_tasks: 准备执行 {len(tasks_to_execute)} 个任务")

        # 在锁外执行任务，避免死锁
        for task in tasks_to_execute:
            self._execute_task(task)

    def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        try:
            logger.debug(f"_execute_task: 开始执行任务: {task.task_id}")

            # 发送信号
            self.task_started.emit(task.task_id)

            # 提交任务到线程池
            task_id = self._thread_pool_manager.submit_task(
                func=task.func,
                args=task.args,
                kwargs=task.kwargs,
                priority=TaskPriority.NORMAL,
                timeout=task.timeout,
                callback=lambda result, tid=task.task_id: self._on_task_completed(tid, result),
                error_callback=lambda error, tid=task.task_id: self._on_task_failed(tid, error)
            )

            logger.debug(f"任务开始执行: {task.task_id}")

        except Exception as e:
            logger.error(f"执行任务失败: {task.task_id}, 错误: {e}")
            self._on_task_failed(task.task_id, e)

    def _on_task_completed(self, task_id: str, result: Any):
        """任务完成回调"""
        try:
            with self._queue_lock:
                if task_id not in self._tasks:
                    return

                task = self._tasks[task_id]
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.end_time = time.time()

                self._stats['running_tasks'] -= 1
                self._stats['completed_tasks'] += 1
                self._stats['total_execution_time'] += (task.end_time - task.start_time)

                self._completed_tasks.add(task_id)

            # 调用成功回调
            if task.callback:
                try:
                    task.callback(result)
                except Exception as e:
                    logger.error(f"任务回调执行失败: {task_id}, 错误: {e}")

            # 发送信号
            self.task_completed.emit(task_id, result)

            # 发布事件
            if self._event_bus:
                try:
                    from core.events.types import BaseEvent

                    class ScheduledTaskCompletedEvent(BaseEvent):
                        def __init__(self, task_id: str, result: Any):
                            super().__init__()
                            self.task_id = task_id
                            self.result = result

                    event = ScheduledTaskCompletedEvent(task_id, result)
                    self._event_bus.publish(event)
                except Exception as e:
                    logger.debug(f"发布任务完成事件失败: {e}")

            # 检查并执行依赖此任务的任务
            self._check_dependent_tasks(task_id)

            # 尝试执行准备好的任务
            self._try_execute_tasks()

            logger.debug(f"任务已完成: {task_id}, 耗时: {task.end_time - task.start_time:.3f}s")

        except Exception as e:
            logger.error(f"处理任务完成失败: {task_id}, 错误: {e}")

    def _on_task_failed(self, task_id: str, error: Exception):
        """任务失败回调"""
        try:
            with self._queue_lock:
                if task_id not in self._tasks:
                    return

                task = self._tasks[task_id]
                task.status = TaskStatus.FAILED
                task.error = error
                task.end_time = time.time()

                self._stats['running_tasks'] -= 1
                self._stats['failed_tasks'] += 1

                self._failed_tasks.add(task_id)

            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                logger.info(f"重试任务: {task_id}, 重试次数: {task.retry_count}/{task.max_retries}")

                # 重新调度任务
                self.schedule_task(
                    func=task.func,
                    args=task.args,
                    kwargs=task.kwargs,
                    priority=TaskPriority.NORMAL,
                    timeout=task.timeout,
                    callback=task.callback,
                    error_callback=task.error_callback,
                    dependencies=list(task.dependencies),
                    max_retries=task.max_retries - task.retry_count
                )
                return

            # 调用错误回调
            if task.error_callback:
                try:
                    task.error_callback(error)
                except Exception as e:
                    logger.error(f"任务错误回调执行失败: {task_id}, 错误: {e}")

            # 发送信号
            self.task_failed.emit(task_id, str(error))

            # 发布事件
            if self._event_bus:
                try:
                    from core.events.types import BaseEvent

                    class ScheduledTaskFailedEvent(BaseEvent):
                        def __init__(self, task_id: str, error: str):
                            super().__init__()
                            self.task_id = task_id
                            self.error = error

                    event = ScheduledTaskFailedEvent(task_id, str(error))
                    self._event_bus.publish(event)
                except Exception as e:
                    logger.debug(f"发布任务失败事件失败: {e}")

            logger.error(f"任务执行失败: {task_id}, 错误: {error}")

        except Exception as e:
            logger.error(f"处理任务失败失败: {task_id}, 错误: {e}")

    def _check_dependent_tasks(self, completed_task_id: str):
        """检查并执行依赖此任务的任务"""
        try:
            with self._queue_lock:
                if completed_task_id not in self._task_dependencies:
                    return

                task_dep = self._task_dependencies[completed_task_id]

                # 检查所有依赖此任务的任务
                for dependent_id in list(task_dep.dependents):
                    if dependent_id not in self._tasks:
                        continue

                    dependent_task = self._tasks[dependent_id]

                    # 检查任务是否准备好执行
                    if self._is_task_ready(dependent_task) and dependent_task.status == TaskStatus.PENDING:
                        dependent_task.status = TaskStatus.READY
                        heapq.heappush(self._ready_queue, dependent_task)
                        self._stats['pending_tasks'] -= 1
                        self._stats['ready_tasks'] += 1

                        logger.debug(f"任务已准备好执行: {dependent_id}")

        except Exception as e:
            logger.error(f"检查依赖任务失败: {completed_task_id}, 错误: {e}")

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否取消成功
        """
        try:
            with self._queue_lock:
                if task_id not in self._tasks:
                    logger.warning(f"任务不存在: {task_id}")
                    return False

                task = self._tasks[task_id]

                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    logger.warning(f"任务已完成或已取消，无法取消: {task_id}")
                    return False

                # 取消任务
                task.status = TaskStatus.CANCELLED
                task.end_time = time.time()

                self._stats['cancelled_tasks'] += 1

                if task.status == TaskStatus.RUNNING:
                    self._stats['running_tasks'] -= 1
                elif task.status == TaskStatus.READY:
                    self._stats['ready_tasks'] -= 1
                elif task.status == TaskStatus.PENDING:
                    self._stats['pending_tasks'] -= 1

            # 发送信号
            self.task_cancelled.emit(task_id)

            logger.info(f"任务已取消: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消任务失败: {task_id}, 错误: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态
        """
        with self._queue_lock:
            if task_id not in self._tasks:
                return None

            return self._tasks[task_id].status

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """
        获取任务结果

        Args:
            task_id: 任务ID

        Returns:
            任务结果
        """
        with self._queue_lock:
            if task_id not in self._tasks:
                return None

            task = self._tasks[task_id]

            if task.status != TaskStatus.COMPLETED:
                return None

            return task.result

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._queue_lock:
            return {
                **self._stats,
                'pending_tasks': len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING]),
                'ready_tasks': len([t for t in self._tasks.values() if t.status == TaskStatus.READY]),
                'running_tasks': len([t for t in self._tasks.values() if t.status == TaskStatus.RUNNING])
            }

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        with self._queue_lock:
            if task_id not in self._tasks:
                return None

            task = self._tasks[task_id]

            return {
                'task_id': task.task_id,
                'status': task.status.name,
                'submit_time': task.submit_time,
                'start_time': task.start_time,
                'end_time': task.end_time,
                'timeout': task.timeout,
                'dependencies': list(task.dependencies),
                'retry_count': task.retry_count,
                'max_retries': task.max_retries,
                'result': task.result if task.status == TaskStatus.COMPLETED else None,
                'error': str(task.error) if task.error else None
            }


# 全局实例
_task_scheduler_instance: Optional[UnifiedTaskScheduler] = None
_task_scheduler_lock = threading.Lock()


def get_task_scheduler() -> UnifiedTaskScheduler:
    """获取任务调度器实例"""
    global _task_scheduler_instance

    if _task_scheduler_instance is None:
        with _task_scheduler_lock:
            if _task_scheduler_instance is None:
                _task_scheduler_instance = UnifiedTaskScheduler()

    return _task_scheduler_instance


def initialize_task_scheduler(event_bus=None) -> UnifiedTaskScheduler:
    """初始化任务调度器"""
    scheduler = get_task_scheduler()
    scheduler.set_event_bus(event_bus)
    return scheduler
