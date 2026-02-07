#!/usr/bin/env python3
"""
统一定时器管理器

统一管理所有定时器，避免多个定时器同时触发导致的资源消耗问题。支持定时器优先级、暂停和恢复等功能。
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from collections import defaultdict
from loguru import logger
import heapq
import weakref

# 延迟导入PyQt5，避免在没有QApplication时初始化失败
QTimer = None
QObject = None
pyqtSignal = None


def _ensure_qt_imports():
    """确保Qt模块已导入"""
    global QTimer, QObject, pyqtSignal
    if QTimer is None:
        try:
            # 检查是否有QApplication实例
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                # 没有QApplication实例，不导入Qt模块
                raise RuntimeError("QApplication实例不存在，无法导入Qt模块")
            from PyQt5.QtCore import QTimer, QObject, pyqtSignal
        except ImportError:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                raise RuntimeError("QApplication实例不存在，无法导入Qt模块")
            from PyQt5.QtCore import QTimer, QObject, pyqtSignal


class TimerPriority(Enum):
    """定时器优先级"""
    CRITICAL = auto()  # 关键任务，必须执行
    HIGH = auto()      # 高优先级
    NORMAL = auto()    # 正常优先级
    LOW = auto()       # 低优先级


@dataclass(order=True)
class TimerTask:
    """定时器任务"""
    priority: int = field(init=False)
    next_run_time: float
    interval: float
    callback: Callable
    name: str
    enabled: bool = True
    last_run_time: float = 0.0
    run_count: int = 0
    total_run_time: float = 0.0

    def __post_init__(self):
        self.priority = self.next_run_time

    def update_next_run_time(self):
        """更新下次运行时间"""
        self.next_run_time = time.time() + self.interval
        self.priority = self.next_run_time


class UnifiedTimerManager:
    """
    统一定时器管理器

    功能：
    1. 统一管理所有定时器
    2. 支持定时器优先级
    3. 避免定时器同时触发
    4. 支持定时器暂停和恢复
    5. 提供定时器统计信息
    """

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
        """初始化定时器管理器"""
        if self._initialized:
            return

        # 确保Qt模块已导入
        _ensure_qt_imports()

        # 创建信号发射器（延迟创建）
        global QObject, pyqtSignal
        class TimerSignalEmitter(QObject):
            """定时器信号发射器"""
            timer_triggered = pyqtSignal(str)  # 定时器触发信号
            timer_error = pyqtSignal(str, str)  # 定时器错误信号

        self._signal_emitter = TimerSignalEmitter()

        self._initialized = True
        self._tasks: Dict[str, TimerTask] = {}
        self._task_heap: List[TimerTask] = []
        self._heap_lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 统计信息
        self._stats = {
            'total_tasks': 0,
            'active_tasks': 0,
            'paused_tasks': 0,
            'total_runs': 0,
            'total_run_time': 0.0,
            'errors': 0
        }

        # 最小触发间隔（毫秒），避免定时器同时触发
        self._min_trigger_interval = 100  # 100ms

        # 事件总线引用（延迟加载）
        self._event_bus = None

        logger.info("统一定时器管理器已初始化")

    def set_event_bus(self, event_bus):
        """设置事件总线"""
        self._event_bus = event_bus

    def register_timer(self,
                       name: str,
                       interval: float,
                       callback: Callable,
                       priority: TimerPriority = TimerPriority.NORMAL,
                       enabled: bool = True) -> bool:
        """
        注册定时器

        Args:
            name: 定时器名称
            interval: 间隔时间（秒）
            callback: 回调函数
            priority: 优先级
            enabled: 是否启用

        Returns:
            是否注册成功
        """
        try:
            if name in self._tasks:
                logger.warning(f"定时器已存在: {name}")
                return False

            # 创建定时器任务
            task = TimerTask(
                next_run_time=time.time() + interval,
                interval=interval,
                callback=callback,
                name=name,
                enabled=enabled
            )

            self._tasks[name] = task

            if enabled:
                with self._heap_lock:
                    heapq.heappush(self._task_heap, task)

            self._stats['total_tasks'] += 1
            if enabled:
                self._stats['active_tasks'] += 1

            logger.info(f"定时器已注册: {name}, 间隔: {interval}s, 优先级: {priority.name}")
            return True

        except Exception as e:
            logger.error(f"注册定时器失败: {name}, 错误: {e}")
            return False

    def unregister_timer(self, name: str) -> bool:
        """
        注销定时器

        Args:
            name: 定时器名称

        Returns:
            是否注销成功
        """
        try:
            if name not in self._tasks:
                logger.warning(f"定时器不存在: {name}")
                return False

            task = self._tasks[name]
            del self._tasks[name]

            if task.enabled:
                self._stats['active_tasks'] -= 1
            else:
                self._stats['paused_tasks'] -= 1

            self._stats['total_tasks'] -= 1

            logger.info(f"定时器已注销: {name}")
            return True

        except Exception as e:
            logger.error(f"注销定时器失败: {name}, 错误: {e}")
            return False

    def pause_timer(self, name: str) -> bool:
        """
        暂停定时器

        Args:
            name: 定时器名称

        Returns:
            是否暂停成功
        """
        try:
            if name not in self._tasks:
                logger.warning(f"定时器不存在: {name}")
                return False

            task = self._tasks[name]
            if not task.enabled:
                logger.warning(f"定时器已暂停: {name}")
                return False

            task.enabled = False
            self._stats['active_tasks'] -= 1
            self._stats['paused_tasks'] += 1

            logger.info(f"定时器已暂停: {name}")
            return True

        except Exception as e:
            logger.error(f"暂停定时器失败: {name}, 错误: {e}")
            return False

    def resume_timer(self, name: str) -> bool:
        """
        恢复定时器

        Args:
            name: 定时器名称

        Returns:
            是否恢复成功
        """
        try:
            if name not in self._tasks:
                logger.warning(f"定时器不存在: {name}")
                return False

            task = self._tasks[name]
            if task.enabled:
                logger.warning(f"定时器已启用: {name}")
                return False

            task.enabled = True
            task.update_next_run_time()

            with self._heap_lock:
                heapq.heappush(self._task_heap, task)

            self._stats['active_tasks'] += 1
            self._stats['paused_tasks'] -= 1

            logger.info(f"定时器已恢复: {name}")
            return True

        except Exception as e:
            logger.error(f"恢复定时器失败: {name}, 错误: {e}")
            return False

    def start(self):
        """启动定时器管理器"""
        if self._running:
            logger.warning("定时器管理器已在运行")
            return

        self._running = True
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()

        logger.info("定时器管理器已启动")

    def stop(self):
        """停止定时器管理器"""
        if not self._running:
            logger.warning("定时器管理器未运行")
            return

        self._running = False
        self._stop_event.set()

        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)

        logger.info("定时器管理器已停止")

    def _run_loop(self):
        """运行循环"""
        last_trigger_time = 0.0

        while self._running:
            try:
                current_time = time.time()

                # 检查是否需要触发定时器
                with self._heap_lock:
                    while self._task_heap and self._task_heap[0].next_run_time <= current_time:
                        task = heapq.heappop(self._task_heap)

                        if not task.enabled:
                            continue

                        # 避免定时器同时触发
                        time_since_last_trigger = (current_time - last_trigger_time) * 1000
                        if time_since_last_trigger < self._min_trigger_interval:
                            time.sleep((self._min_trigger_interval - time_since_last_trigger) / 1000.0)

                        # 执行回调
                        self._execute_task(task)

                        last_trigger_time = time.time()

                        # 更新下次运行时间
                        if task.enabled:
                            task.update_next_run_time()
                            heapq.heappush(self._task_heap, task)

                # 等待下一次检查
                sleep_time = 0.1  # 100ms
                self._stop_event.wait(sleep_time)

            except Exception as e:
                logger.error(f"定时器管理器运行错误: {e}")

    def _execute_task(self, task: TimerTask):
        """执行定时器任务"""
        try:
            start_time = time.time()

            # 执行回调
            task.callback()

            # 更新统计信息
            run_time = time.time() - start_time
            task.last_run_time = start_time
            task.run_count += 1
            task.total_run_time += run_time

            self._stats['total_runs'] += 1
            self._stats['total_run_time'] += run_time

            # 发送信号
            self._signal_emitter.timer_triggered.emit(task.name)

            # 发布事件
            if self._event_bus:
                try:
                    from core.events.types import BaseEvent

                    class TimerTriggerEvent(BaseEvent):
                        def __init__(self, timer_name: str, run_time: float):
                            super().__init__()
                            self.timer_name = timer_name
                            self.run_time = run_time

                    event = TimerTriggerEvent(task.name, run_time)
                    self._event_bus.publish(event)
                except Exception as e:
                    logger.debug(f"发布定时器触发事件失败: {e}")

            logger.debug(f"定时器任务已执行: {task.name}, 耗时: {run_time:.3f}s")

        except Exception as e:
            logger.error(f"执行定时器任务失败: {task.name}, 错误: {e}")
            self._stats['errors'] += 1
            self._signal_emitter.timer_error.emit(task.name, str(e))

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            'tasks': {
                name: {
                    'interval': task.interval,
                    'enabled': task.enabled,
                    'run_count': task.run_count,
                    'total_run_time': task.total_run_time,
                    'avg_run_time': task.total_run_time / task.run_count if task.run_count > 0 else 0.0
                }
                for name, task in self._tasks.items()
            }
        }

    def get_task_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        if name not in self._tasks:
            return None

        task = self._tasks[name]
        return {
            'name': task.name,
            'interval': task.interval,
            'enabled': task.enabled,
            'last_run_time': task.last_run_time,
            'next_run_time': task.next_run_time,
            'run_count': task.run_count,
            'total_run_time': task.total_run_time,
            'avg_run_time': task.total_run_time / task.run_count if task.run_count > 0 else 0.0
        }


# 全局实例
_timer_manager_instance: Optional[UnifiedTimerManager] = None
_timer_manager_lock = threading.Lock()


def get_timer_manager() -> UnifiedTimerManager:
    """获取定时器管理器实例"""
    global _timer_manager_instance

    if _timer_manager_instance is None:
        with _timer_manager_lock:
            if _timer_manager_instance is None:
                _timer_manager_instance = UnifiedTimerManager()

    return _timer_manager_instance


def initialize_timer_manager(event_bus=None) -> UnifiedTimerManager:
    """初始化定时器管理器"""
    manager = get_timer_manager()
    manager.set_event_bus(event_bus)
    return manager
