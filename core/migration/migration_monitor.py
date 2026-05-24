#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorWeave-Quant 迁移监控和日志系统

该模块提供传统数据源迁移过程的实时监控、进度跟踪和详细日志记录功能。
集成现有的Loguru日志系统和指标收集服务。

作者: FactorWeave-Quant Migration Team
日期: 2025-09-20
"""

import os
import sys
import json
import time
import threading
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, asdict
import queue
import traceback

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from core.loguru_interface import get_logger
    from core.metrics.app_metrics_service import AppMetricsService
except ImportError:
    # 备用日志记录
    from loguru import logger

    def get_logger(name):
        return logger

    class AppMetricsService:
        def __init__t__(self):
            pass
            pass

class MigrationPhase(Enum):
    """迁移阶段枚举"""
    PREPARATION = "preparation"
    DECOUPLING = "decoupling"
    ENHANCEMENT = "enhancement"
    CLEANUP = "cleanup"


class MigrationStatus(Enum):
    """迁移状态枚举"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    ROLLED_BACK = "rolled_back"


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MigrationTask:
    """迁移任务数据类"""
    task_id: str
    name: str
    description: str
    phase: MigrationPhase
    status: TaskStatus
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    progress_percentage: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MigrationEvent:
    """迁移事件数据类"""
    event_id: str
    timestamp: datetime.datetime
    event_type: str
    task_id: Optional[str]
    phase: Optional[MigrationPhase]
    message: str
    level: str  # INFO, WARNING, ERROR, CRITICAL
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MigrationMonitor:
    """迁移监控器"""

    def __init__(self, log_dir: str = None, enable_metrics: bool = True):
        """
        初始化迁移监控器

        Args:
            log_dir: 日志目录，默认为项目根目录下的logs/migration
            enable_metrics: 是否启用指标收集
        """
        self.logger = get_logger("MigrationMonitor")

        # 设置日志目录
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = project_root / "logs" / "migration"

        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.enable_metrics = enable_metrics
        if enable_metrics:
            try:
                self.metrics_service = AppMetricsService()
            except Exception as e:
                self.logger.warning(f"指标服务初始化失败: {e}")
                self.metrics_service = None
        else:
            self.metrics_service = None

        # 迁移状态
        self.migration_id = f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.migration_status = MigrationStatus.NOT_STARTED
        self.current_phase = None
        self.start_time = None
        self.end_time = None

        # 任务和事件存储
        self.tasks: Dict[str, MigrationTask] = {}
        self.events: List[MigrationEvent] = []
        self.event_queue = queue.Queue()

        # 监控配置
        self.monitoring_enabled = True
        self.auto_save_interval = 30  # 秒
        self.max_events_in_memory = 10000

        # 回调函数
        self.event_callbacks: List[Callable[[MigrationEvent], None]] = []
        self.task_callbacks: List[Callable[[MigrationTask], None]] = []

        # 线程控制
        self._stop_event = threading.Event()
        self._monitor_thread = None
        self._auto_save_thread = None

        # 启动监控
        self._start_monitoring()

        self.logger.info(f"迁移监控器初始化完成: {self.migration_id}")

    def _start_monitoring(self):
        """启动监控线程"""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="MigrationMonitor",
                daemon=True
            )
            self._monitor_thread.start()

        if self._auto_save_thread is None or not self._auto_save_thread.is_alive():
            self._auto_save_thread = threading.Thread(
                target=self._auto_save_loop,
                name="MigrationAutoSave",
                daemon=True
            )
            self._auto_save_thread.start()

    def _monitor_loop(self):
        """监控主循环"""
        while not self._stop_event.is_set():
            try:
                # 处理事件队列
                while not self.event_queue.empty():
                    try:
                        event = self.event_queue.get_nowait()
                        self._process_event(event)
                    except queue.Empty:
                        break

                # 更新任务进度
                self._update_task_progress()

                # 记录指标
                if self.metrics_service:
                    self._record_metrics()

                time.sleep(1)  # 1秒检查一次

            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                time.sleep(5)

    def _auto_save_loop(self):
        """自动保存循环"""
        while not self._stop_event.is_set():
            try:
                time.sleep(self.auto_save_interval)
                if not self._stop_event.is_set():
                    self.save_state()
            except Exception as e:
                self.logger.error(f"自动保存异常: {e}")

    def _process_event(self, event: MigrationEvent):
        """处理迁移事件"""
        # 添加到事件列表
        self.events.append(event)

        # 限制内存中的事件数量
        if len(self.events) > self.max_events_in_memory:
            self.events = self.events[-self.max_events_in_memory:]

        # 记录日志
        log_level = event.level.lower()
        log_message = f"[{event.event_type}] {event.message}"

        if hasattr(self.logger, log_level):
            getattr(self.logger, log_level)(log_message)
        else:
            self.logger.info(log_message)

        # 调用回调函数
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"事件回调异常: {e}")

    def _update_task_progress(self):
        """更新任务进度"""
        for task in self.tasks.values():
            if task.status == TaskStatus.IN_PROGRESS:
                # 计算任务持续时间
                if task.start_time:
                    task.duration = (datetime.datetime.now() - task.start_time).total_seconds()

    def _record_metrics(self):
        """记录指标"""
        if not self.metrics_service:
            return

        try:
            # 记录总体进度
            total_tasks = len(self.tasks)
            completed_tasks = sum(1 for task in self.tasks.values()
                                  if task.status == TaskStatus.COMPLETED)

            if total_tasks > 0:
                overall_progress = (completed_tasks / total_tasks) * 100
                self.metrics_service.record_metric(
                    "migration.overall_progress",
                    overall_progress,
                    {"migration_id": self.migration_id}
                )

            # 记录各阶段进度
            for phase in MigrationPhase:
                phase_tasks = [task for task in self.tasks.values() if task.phase == phase]
                if phase_tasks:
                    phase_completed = sum(1 for task in phase_tasks
                                          if task.status == TaskStatus.COMPLETED)
                    phase_progress = (phase_completed / len(phase_tasks)) * 100

                    self.metrics_service.record_metric(
                        f"migration.phase_progress.{phase.value}",
                        phase_progress,
                        {"migration_id": self.migration_id}
                    )

            # 记录任务状态统计
            status_counts = {}
            for status in TaskStatus:
                count = sum(1 for task in self.tasks.values() if task.status == status)
                status_counts[status.value] = count

                self.metrics_service.record_metric(
                    f"migration.task_status.{status.value}",
                    count,
                    {"migration_id": self.migration_id}
                )

        except Exception as e:
            self.logger.error(f"记录指标失败: {e}")

    def start_migration(self, phase: MigrationPhase = None):
        """开始迁移"""
        self.migration_status = MigrationStatus.IN_PROGRESS
        self.start_time = datetime.datetime.now()
        self.current_phase = phase

        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="migration_started",
            task_id=None,
            phase=phase,
            message=f"开始迁移: {self.migration_id}",
            level="INFO"
        )

        self.add_event(event)
        self.logger.info(f"迁移开始: {self.migration_id}")

    def complete_migration(self, success: bool = True):
        """完成迁移"""
        self.end_time = datetime.datetime.now()

        if success:
            self.migration_status = MigrationStatus.COMPLETED
            message = f"迁移成功完成: {self.migration_id}"
            level = "INFO"
        else:
            self.migration_status = MigrationStatus.FAILED
            message = f"迁移失败: {self.migration_id}"
            level = "ERROR"

        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="migration_completed" if success else "migration_failed",
            task_id=None,
            phase=self.current_phase,
            message=message,
            level=level
        )

        self.add_event(event)
        self.save_state()
        self.logger.info(message)

    def add_task(self, task: MigrationTask):
        """添加迁移任务"""
        self.tasks[task.task_id] = task

        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="task_added",
            task_id=task.task_id,
            phase=task.phase,
            message=f"添加任务: {task.name}",
            level="INFO"
        )

        self.add_event(event)

    def start_task(self, task_id: str):
        """开始任务"""
        if task_id not in self.tasks:
            raise ValueError(f"任务不存在: {task_id}")

        task = self.tasks[task_id]
        task.status = TaskStatus.IN_PROGRESS
        task.start_time = datetime.datetime.now()
        task.progress_percentage = 0.0

        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="task_started",
            task_id=task_id,
            phase=task.phase,
            message=f"开始任务: {task.name}",
            level="INFO"
        )

        self.add_event(event)

        # 调用任务回调
        for callback in self.task_callbacks:
            try:
                callback(task)
            except Exception as e:
                self.logger.error(f"任务回调异常: {e}")

    def update_task_progress(self, task_id: str, progress: float, message: str = None):
        """更新任务进度"""
        if task_id not in self.tasks:
            raise ValueError(f"任务不存在: {task_id}")

        task = self.tasks[task_id]
        task.progress_percentage = max(0, min(100, progress))

        if message:
            event = MigrationEvent(
                event_id=f"event_{int(time.time() * 1000)}",
                timestamp=datetime.datetime.now(),
                event_type="task_progress",
                task_id=task_id,
                phase=task.phase,
                message=f"任务进度 {progress:.1f}%: {message}",
                level="INFO"
            )

            self.add_event(event)

    def complete_task(self, task_id: str, success: bool = True, error_message: str = None):
        """完成任务"""
        if task_id not in self.tasks:
            raise ValueError(f"任务不存在: {task_id}")

        task = self.tasks[task_id]
        task.end_time = datetime.datetime.now()

        if task.start_time:
            task.duration = (task.end_time - task.start_time).total_seconds()

        if success:
            task.status = TaskStatus.COMPLETED
            task.progress_percentage = 100.0
            message = f"任务完成: {task.name}"
            level = "INFO"
        else:
            task.status = TaskStatus.FAILED
            task.error_message = error_message
            message = f"任务失败: {task.name}"
            if error_message:
                message += f" - {error_message}"
            level = "ERROR"

        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="task_completed" if success else "task_failed",
            task_id=task_id,
            phase=task.phase,
            message=message,
            level=level
        )

        self.add_event(event)

        # 调用任务回调
        for callback in self.task_callbacks:
            try:
                callback(task)
            except Exception as e:
                self.logger.error(f"任务回调异常: {e}")

    def add_event(self, event: MigrationEvent):
        """添加事件"""
        self.event_queue.put(event)

    def log_info(self, message: str, task_id: str = None, phase: MigrationPhase = None):
        """记录信息日志"""
        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="info",
            task_id=task_id,
            phase=phase,
            message=message,
            level="INFO"
        )

        self.add_event(event)

    def log_warning(self, message: str, task_id: str = None, phase: MigrationPhase = None):
        """记录警告日志"""
        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="warning",
            task_id=task_id,
            phase=phase,
            message=message,
            level="WARNING"
        )

        self.add_event(event)

    def log_error(self, message: str, task_id: str = None, phase: MigrationPhase = None,
                  exception: Exception = None):
        """记录错误日志"""
        if exception:
            message += f"\n{traceback.format_exc()}"

        event = MigrationEvent(
            event_id=f"event_{int(time.time() * 1000)}",
            timestamp=datetime.datetime.now(),
            event_type="error",
            task_id=task_id,
            phase=phase,
            message=message,
            level="ERROR"
        )

        self.add_event(event)

    def add_event_callback(self, callback: Callable[[MigrationEvent], None]):
        """添加事件回调"""
        self.event_callbacks.append(callback)

    def add_task_callback(self, callback: Callable[[MigrationTask], None]):
        """添加任务回调"""
        self.task_callbacks.append(callback)

    def get_migration_summary(self) -> Dict[str, Any]:
        """获取迁移摘要"""
        total_tasks = len(self.tasks)
        completed_tasks = sum(1 for task in self.tasks.values()
                              if task.status == TaskStatus.COMPLETED)
        failed_tasks = sum(1 for task in self.tasks.values()
                           if task.status == TaskStatus.FAILED)
        in_progress_tasks = sum(1 for task in self.tasks.values()
                                if task.status == TaskStatus.IN_PROGRESS)

        overall_progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        duration = None
        if self.start_time:
            end_time = self.end_time or datetime.datetime.now()
            duration = (end_time - self.start_time).total_seconds()

        return {
            "migration_id": self.migration_id,
            "status": self.migration_status.value,
            "current_phase": self.current_phase.value if self.current_phase else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": duration,
            "overall_progress": overall_progress,
            "task_summary": {
                "total": total_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
                "in_progress": in_progress_tasks,
                "pending": total_tasks - completed_tasks - failed_tasks - in_progress_tasks
            },
            "recent_events": len(self.events)
        }

    def get_task_summary(self, phase: MigrationPhase = None) -> List[Dict[str, Any]]:
        """获取任务摘要"""
        tasks = self.tasks.values()
        if phase:
            tasks = [task for task in tasks if task.phase == phase]

        return [
            {
                "task_id": task.task_id,
                "name": task.name,
                "phase": task.phase.value,
                "status": task.status.value,
                "progress": task.progress_percentage,
                "duration": task.duration,
                "error_message": task.error_message
            }
            for task in tasks
        ]

    def save_state(self, file_path: str = None):
        """保存状态到文件"""
        if not file_path:
            file_path = self.log_dir / f"{self.migration_id}_state.json"

        try:
            state = {
                "migration_summary": self.get_migration_summary(),
                "tasks": [asdict(task) for task in self.tasks.values()],
                "recent_events": [asdict(event) for event in self.events[-100:]]  # 只保存最近100个事件
            }

            # 处理datetime序列化
            def json_serializer(obj):
                if isinstance(obj, datetime.datetime):
                    return obj.isoformat()
                elif isinstance(obj, (MigrationPhase, MigrationStatus, TaskStatus)):
                    return obj.value
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False, default=json_serializer)

            self.logger.debug(f"状态保存完成: {file_path}")

        except Exception as e:
            self.logger.error(f"保存状态失败: {e}")

    def load_state(self, file_path: str):
        """从文件加载状态"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            # 恢复任务状态
            for task_data in state.get("tasks", []):
                # 转换datetime字符串
                if task_data.get("start_time"):
                    task_data["start_time"] = datetime.datetime.fromisoformat(task_data["start_time"])
                if task_data.get("end_time"):
                    task_data["end_time"] = datetime.datetime.fromisoformat(task_data["end_time"])

                # 转换枚举
                task_data["phase"] = MigrationPhase(task_data["phase"])
                task_data["status"] = TaskStatus(task_data["status"])

                task = MigrationTask(**task_data)
                self.tasks[task.task_id] = task

            self.logger.info(f"状态加载完成: {file_path}")

        except Exception as e:
            self.logger.error(f"加载状态失败: {e}")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_enabled = False
        self._stop_event.set()

        # 等待线程结束
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

        if self._auto_save_thread and self._auto_save_thread.is_alive():
            self._auto_save_thread.join(timeout=5)

        # 最后保存状态
        self.save_state()

        self.logger.info("迁移监控已停止")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_monitoring()


# 全局监控器实例
_global_monitor: Optional[MigrationMonitor] = None


def get_migration_monitor() -> MigrationMonitor:
    """获取全局迁移监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = MigrationMonitor()
    return _global_monitor


def initialize_migration_monitor(log_dir: str = None, enable_metrics: bool = True) -> MigrationMonitor:
    """初始化全局迁移监控器"""
    global _global_monitor
    if _global_monitor is not None:
        _global_monitor.stop_monitoring()

    _global_monitor = MigrationMonitor(log_dir=log_dir, enable_metrics=enable_metrics)
    return _global_monitor

# 便捷函数


def log_migration_info(message: str, task_id: str = None, phase: MigrationPhase = None):
    """记录迁移信息日志"""
    monitor = get_migration_monitor()
    monitor.log_info(message, task_id, phase)


def log_migration_warning(message: str, task_id: str = None, phase: MigrationPhase = None):
    """记录迁移警告日志"""
    monitor = get_migration_monitor()
    monitor.log_warning(message, task_id, phase)


def log_migration_error(message: str, task_id: str = None, phase: MigrationPhase = None,
                        exception: Exception = None):
    """记录迁移错误日志"""
    monitor = get_migration_monitor()
    monitor.log_error(message, task_id, phase, exception)


if __name__ == "__main__":
    # 测试代码
    with MigrationMonitor() as monitor:
        # 开始迁移
        monitor.start_migration(MigrationPhase.PREPARATION)

        # 添加测试任务
        task = MigrationTask(
            task_id="test_task_1",
            name="测试任务1",
            description="这是一个测试任务",
            phase=MigrationPhase.PREPARATION,
            status=TaskStatus.PENDING
        )

        monitor.add_task(task)
        monitor.start_task("test_task_1")

        # 模拟任务进度
        for i in range(0, 101, 20):
            monitor.update_task_progress("test_task_1", i, f"处理步骤 {i//20 + 1}")
            time.sleep(1)

        monitor.complete_task("test_task_1", success=True)
        monitor.complete_migration(success=True)

        # 打印摘要
        summary = monitor.get_migration_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
