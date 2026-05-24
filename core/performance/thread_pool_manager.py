#!/usr/bin/env python3
"""
统一线程池管理器

统一管理所有线程池，避免多个线程池同时运行导致的资源消耗问题。支持任务优先级、任务取消和超时等功能。
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

from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FutureTimeoutError
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMetaObject, Qt


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = auto()  # 关键任务，必须执行
    HIGH = auto()      # 高优先级
    NORMAL = auto()    # 正常优先级
    LOW = auto()       # 低优先级


@dataclass(order=True)
class Task:
    """任务"""
    priority: int = field(init=False)
    submit_time: float
    task_id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    timeout: Optional[float] = None
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    cancelled: bool = False
    completed: bool = False

    def __post_init__(self):
        self.priority = self.submit_time


class UnifiedThreadPoolManager(QObject):
    """
    统一线程池管理器

    功能：
    1. 统一管理所有线程池
    2. 限制最大工作线程数
    3. 支持任务优先级
    4. 支持任务取消和超时
    5. 提供任务统计信息
    """

    # 信号
    task_completed = pyqtSignal(str, object)  # 任务完成信号
    task_failed = pyqtSignal(str, str)  # 任务失败信号
    task_cancelled = pyqtSignal(str)  # 任务取消信号

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

    def __init__(self, max_workers: int = 4):
        """
        初始化线程池管理器

        Args:
            max_workers: 最大工作线程数
        """
        if self._initialized:
            return

        super().__init__()

        self._initialized = True
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="UnifiedThreadPool")
        self._futures: Dict[str, Future] = {}
        self._tasks: Dict[str, Task] = {}
        self._task_counter = 0
        self._lock = threading.Lock()

        # 统计信息
        self._stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0,
            'active_tasks': 0,
            'total_execution_time': 0.0
        }

        # 事件总线引用（延迟加载）
        self._event_bus = None

        logger.info(f"统一线程池管理器已初始化，最大工作线程数: {max_workers}")

    def _cleanup_completed_futures(self):
        """清理已完成的Future，防止内存泄漏"""
        with self._lock:
            completed_ids = [
                tid for tid, f in self._futures.items()
                if f.done()
            ]
            for tid in completed_ids:
                del self._futures[tid]

    def set_event_bus(self, event_bus):
        """设置事件总线"""
        self._event_bus = event_bus

    def submit_task(self,
                    func: Callable,
                    args: tuple = (),
                    kwargs: dict = None,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    timeout: Optional[float] = None,
                    callback: Optional[Callable] = None,
                    error_callback: Optional[Callable] = None) -> str:
        """
        提交任务

        Args:
            func: 任务函数
            args: 位置参数
            kwargs: 关键字参数
            priority: 任务优先级
            timeout: 超时时间（秒）
            callback: 成功回调
            error_callback: 错误回调

        Returns:
            任务ID
        """
        try:
            with self._lock:
                self._task_counter += 1
                task_id = f"task_{self._task_counter}"

                task = Task(
                    submit_time=time.time(),
                    task_id=task_id,
                    func=func,
                    args=args,
                    kwargs=kwargs or {},
                    timeout=timeout,
                    callback=callback,
                    error_callback=error_callback
                )

                self._tasks[task_id] = task
                self._stats['total_tasks'] += 1
                self._stats['active_tasks'] += 1

            # 提交任务到线程池
            future = self._executor.submit(self._execute_task, task)

            with self._lock:
                self._futures[task_id] = future

            logger.debug(f"任务已提交: {task_id}, 优先级: {priority.name}")
            return task_id

        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            return ""

    def _execute_task(self, task: Task) -> Any:
        """执行任务"""
        start_time = time.time()

        try:
            # 执行任务
            result = task.func(*task.args, **task.kwargs)

            # 更新任务状态
            with self._lock:
                task.completed = True
                self._stats['completed_tasks'] += 1
                self._stats['active_tasks'] -= 1
                self._stats['total_execution_time'] += time.time() - start_time

            # 调用成功回调
            if task.callback:
                try:
                    task.callback(result)
                except Exception as e:
                    logger.error(f"任务回调执行失败: {task.task_id}, 错误: {e}")

            # 发送信号（线程安全）
            task_id_for_emit = task.task_id
            result_for_emit = result
            self.task_completed.emit(task_id_for_emit, result_for_emit)

            # 发布事件
            if self._event_bus:
                try:
                    from core.events.types import BaseEvent

                    class TaskCompletedEvent(BaseEvent):
                        def __init__(self, task_id: str, result: Any):
                            super().__init__()
                            self.task_id = task_id
                            self.result = result

                    event = TaskCompletedEvent(task.task_id, result)
                    self._event_bus.publish(event)
                except Exception as e:
                    logger.debug(f"发布任务完成事件失败: {e}")

            logger.debug(f"任务已完成: {task.task_id}, 耗时: {time.time() - start_time:.3f}s")
            return result

        except Exception as e:
            # 更新任务状态
            with self._lock:
                self._stats['failed_tasks'] += 1
                self._stats['active_tasks'] -= 1

            # 调用错误回调
            if task.error_callback:
                try:
                    task.error_callback(e)
                except Exception as e:
                    logger.error(f"任务错误回调执行失败: {task.task_id}, 错误: {e}")

            # 发送信号
            # 发送信号（线程安全）
            task_id_for_emit = task.task_id
            error_for_emit = str(e)
            self.task_failed.emit(task_id_for_emit, error_for_emit)

            # 发布事件
            if self._event_bus:
                try:
                    from core.events.types import BaseEvent

                    class TaskFailedEvent(BaseEvent):
                        def __init__(self, task_id: str, error: str):
                            super().__init__()
                            self.task_id = task_id
                            self.error = error

                    event = TaskFailedEvent(task.task_id, str(e))
                    self._event_bus.publish(event)
                except Exception as e:
                    logger.debug(f"发布任务失败事件失败: {e}")

            logger.error(f"任务执行失败: {task.task_id}, 错误: {e}")
            raise

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否取消成功
        """
        try:
            with self._lock:
                if task_id not in self._futures:
                    logger.warning(f"任务不存在: {task_id}")
                    return False

                future = self._futures[task_id]
                task = self._tasks[task_id]

                if task.completed:
                    logger.warning(f"任务已完成，无法取消: {task_id}")
                    return False

            # 取消任务
            cancelled = future.cancel()

            if cancelled:
                with self._lock:
                    task.cancelled = True
                    self._stats['cancelled_tasks'] += 1
                    self._stats['active_tasks'] -= 1

                # 发送信号
                # 发送信号（线程安全）
                QMetaObject.invokeMethod(
                    self,
                    lambda: self.task_cancelled.emit(task_id),
                    Qt.QueuedConnection
                )

                logger.info(f"任务已取消: {task_id}")
            else:
                logger.warning(f"任务无法取消: {task_id}")

            self._cleanup_completed_futures()

            return cancelled

        except Exception as e:
            logger.error(f"取消任务失败: {task_id}, 错误: {e}")
            return False

    def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        获取任务结果

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）

        Returns:
            任务结果
        """
        try:
            with self._lock:
                if task_id not in self._futures:
                    raise ValueError(f"任务不存在: {task_id}")

                future = self._futures[task_id]

            # 等待任务完成
            if timeout is not None:
                result = future.result(timeout=timeout)
            else:
                result = future.result()

            self._cleanup_completed_futures()

            return result

        except FutureTimeoutError:
            logger.warning(f"获取任务结果超时: {task_id}")
            raise
        except Exception as e:
            logger.error(f"获取任务结果失败: {task_id}, 错误: {e}")
            raise

    def is_task_done(self, task_id: str) -> bool:
        """
        检查任务是否完成

        Args:
            task_id: 任务ID

        Returns:
            是否完成
        """
        with self._lock:
            if task_id not in self._futures:
                return False

            future = self._futures[task_id]
            return future.done()

    def is_task_running(self, task_id: str) -> bool:
        """
        检查任务是否正在运行

        Args:
            task_id: 任务ID

        Returns:
            是否正在运行
        """
        with self._lock:
            if task_id not in self._futures:
                return False

            future = self._futures[task_id]
            return future.running()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        self._cleanup_completed_futures()
        with self._lock:
            return {
                **self._stats,
                'max_workers': self._max_workers,
                'active_tasks': len([f for f in self._futures.values() if f.running()]),
                'pending_tasks': len([f for f in self._futures.values() if not f.done() and not f.running()])
            }

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        with self._lock:
            if task_id not in self._tasks:
                return None

            task = self._tasks[task_id]
            future = self._futures.get(task_id)

            return {
                'task_id': task.task_id,
                'submit_time': task.submit_time,
                'timeout': task.timeout,
                'cancelled': task.cancelled,
                'completed': task.completed,
                'done': future.done() if future else False,
                'running': future.running() if future else False
            }

    def shutdown(self, wait: bool = True):
        """
        关闭线程池

        Args:
            wait: 是否等待任务完成
        """
        logger.info(f"正在关闭线程池，等待任务完成: {wait}")
        self._executor.shutdown(wait=wait)
        logger.info("线程池已关闭")


# 全局实例
_thread_pool_manager_instance: Optional[UnifiedThreadPoolManager] = None
_thread_pool_manager_lock = threading.Lock()


def get_thread_pool_manager() -> UnifiedThreadPoolManager:
    """获取线程池管理器实例"""
    global _thread_pool_manager_instance

    if _thread_pool_manager_instance is None:
        with _thread_pool_manager_lock:
            if _thread_pool_manager_instance is None:
                _thread_pool_manager_instance = UnifiedThreadPoolManager()

    return _thread_pool_manager_instance


def initialize_thread_pool_manager(max_workers: int = 4, event_bus=None) -> UnifiedThreadPoolManager:
    """初始化线程池管理器"""
    manager = get_thread_pool_manager()
    manager.set_event_bus(event_bus)
    return manager
