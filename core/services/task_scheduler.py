from loguru import logger
#!/usr/bin/env python3
"""
任务调度器

支持定时和计划任务功能，包括：
- Cron表达式调度
- 一次性定时任务
- 重复任务
- 任务依赖管理
- 任务历史记录
"""

import time
import json
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import re
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

class TaskType(Enum):
    """任务类型"""
    ONE_TIME = "one_time"  # 一次性任务
    RECURRING = "recurring"  # 重复任务
    CRON = "cron"  # Cron表达式任务
    INTERVAL = "interval"  # 间隔任务

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消
    PAUSED = "paused"  # 已暂停

@dataclass
class TaskExecution:
    """任务执行记录"""
    execution_id: str
    scheduled_time: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    name: str
    task_type: TaskType
    task_function: str  # 任务函数名称
    task_data: dict

    # 调度配置
    schedule_expression: Optional[str] = None  # Cron表达式或时间表达式
    start_time: Optional[str] = None  # 开始时间
    end_time: Optional[str] = None  # 结束时间
    interval_seconds: Optional[int] = None  # 间隔秒数
    max_executions: Optional[int] = None  # 最大执行次数

    # 任务状态
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = None
    last_execution_at: Optional[str] = None
    next_execution_at: Optional[str] = None
    execution_count: int = 0

    # 执行历史
    executions: List[TaskExecution] = None

    # 依赖关系
    dependencies: List[str] = None  # 依赖的任务ID列表

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.executions is None:
            self.executions = []
        if self.dependencies is None:
            self.dependencies = []

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['task_type'] = self.task_type.value
        data['status'] = self.status.value
        data['executions'] = [exec.to_dict() for exec in self.executions]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ScheduledTask':
        """从字典创建"""
        executions_data = data.pop('executions', [])
        task_type = TaskType(data.pop('task_type'))
        status = TaskStatus(data.pop('status'))

        executions = []
        for exec_data in executions_data:
            exec_status = TaskStatus(exec_data.pop('status'))
            execution = TaskExecution(status=exec_status, **exec_data)
            executions.append(execution)

        task = cls(task_type=task_type, status=status, executions=executions, **data)
        return task

class CronParser:
    """Cron表达式解析器"""

    @staticmethod
    def parse_cron(cron_expression: str) -> dict:
        """解析Cron表达式"""
        # 简化的Cron解析器，支持基本格式：分 时 日 月 周
        parts = cron_expression.strip().split()

        if len(parts) != 5:
            raise ValueError(f"无效的Cron表达式: {cron_expression}")

        return {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'weekday': parts[4]
        }

    @staticmethod
    def get_next_execution_time(cron_expression: str, from_time: datetime = None) -> datetime:
        """计算下次执行时间"""
        if from_time is None:
            from_time = datetime.now()

        try:
            cron_parts = CronParser.parse_cron(cron_expression)

            # 简化实现：每分钟检查一次
            next_time = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

            # 检查未来24小时内的时间点
            for _ in range(24 * 60):  # 最多检查24小时
                if CronParser._matches_cron(next_time, cron_parts):
                    return next_time
                next_time += timedelta(minutes=1)

            # 如果24小时内没有匹配，返回明天同一时间
            return from_time + timedelta(days=1)

        except Exception as e:
            logger.error(f"计算Cron执行时间失败: {e}")
            return from_time + timedelta(hours=1)  # 默认1小时后

    @staticmethod
    def _matches_cron(check_time: datetime, cron_parts: dict) -> bool:
        """检查时间是否匹配Cron表达式"""
        try:
            # 检查分钟
            if not CronParser._matches_field(check_time.minute, cron_parts['minute'], 0, 59):
                return False

            # 检查小时
            if not CronParser._matches_field(check_time.hour, cron_parts['hour'], 0, 23):
                return False

            # 检查日期
            if not CronParser._matches_field(check_time.day, cron_parts['day'], 1, 31):
                return False

            # 检查月份
            if not CronParser._matches_field(check_time.month, cron_parts['month'], 1, 12):
                return False

            # 检查星期（0=周日，1=周一，...，6=周六）
            weekday = check_time.weekday() + 1  # Python的weekday是0=周一
            if weekday == 7:
                weekday = 0  # 转换为Cron格式的周日=0
            if not CronParser._matches_field(weekday, cron_parts['weekday'], 0, 6):
                return False

            return True

        except Exception as e:
            logger.error(f"匹配Cron表达式失败: {e}")
            return False

    @staticmethod
    def _matches_field(value: int, pattern: str, min_val: int, max_val: int) -> bool:
        """检查字段是否匹配"""
        if pattern == '*':
            return True

        if ',' in pattern:
            # 处理逗号分隔的值
            values = [int(v.strip()) for v in pattern.split(',')]
            return value in values

        if '/' in pattern:
            # 处理步长值
            if pattern.startswith('*/'):
                step = int(pattern[2:])
                return value % step == 0
            else:
                range_part, step_part = pattern.split('/')
                step = int(step_part)
                if range_part == '*':
                    return value % step == 0
                else:
                    start, end = map(int, range_part.split('-'))
                    return start <= value <= end and (value - start) % step == 0

        if '-' in pattern:
            # 处理范围值
            start, end = map(int, pattern.split('-'))
            return start <= value <= end

        # 处理单个值
        return value == int(pattern)

class TaskScheduler(QObject):
    """任务调度器"""

    # 信号定义
    task_added = pyqtSignal(str)  # 任务ID
    task_started = pyqtSignal(str, str)  # 任务ID, 执行ID
    task_completed = pyqtSignal(str, str, bool)  # 任务ID, 执行ID, 是否成功
    task_failed = pyqtSignal(str, str, str)  # 任务ID, 执行ID, 错误消息
    task_cancelled = pyqtSignal(str)  # 任务ID

    def __init__(self, storage_path: str = "cache/scheduled_tasks.json", parent=None):
        super().__init__(parent)
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self.tasks: Dict[str, ScheduledTask] = {}
        self.task_timers: Dict[str, QTimer] = {}
        self.task_executors: Dict[str, Callable] = {}

        # 主调度定时器 - 延迟初始化
        self.scheduler_timer = None

        # 保存定时器 - 延迟初始化
        self.save_timer = None

        # 加载持久化任务
        self._load_tasks()

    def _ensure_timers(self):
        """确保定时器已初始化"""
        if self.scheduler_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建调度定时器")
                return
            self.scheduler_timer = QTimer()
            self.scheduler_timer.timeout.connect(self._check_scheduled_tasks)
            self.scheduler_timer.start(60000)  # 每分钟检查一次

        if self.save_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建保存定时器")
                return
            self.save_timer = QTimer()
            self.save_timer.timeout.connect(self._save_tasks)
            self.save_timer.start(300000)  # 每5分钟保存一次

    def register_task_executor(self, function_name: str, executor: Callable):
        """注册任务执行器"""
        self.task_executors[function_name] = executor
        logger.info(f"注册任务执行器: {function_name}")

    def schedule_one_time_task(self, task_id: str, name: str, function_name: str,
                               task_data: dict, execution_time: datetime) -> bool:
        """调度一次性任务"""
        try:
            task = ScheduledTask(
                task_id=task_id,
                name=name,
                task_type=TaskType.ONE_TIME,
                task_function=function_name,
                task_data=task_data,
                start_time=execution_time.isoformat(),
                next_execution_at=execution_time.isoformat(),
                max_executions=1
            )

            return self._add_task(task)

        except Exception as e:
            logger.error(f"调度一次性任务失败: {e}")
            return False

    def schedule_recurring_task(self, task_id: str, name: str, function_name: str,
                                task_data: dict, interval_seconds: int,
                                start_time: datetime = None, end_time: datetime = None,
                                max_executions: int = None) -> bool:
        """调度重复任务"""
        try:
            if start_time is None:
                start_time = datetime.now()

            task = ScheduledTask(
                task_id=task_id,
                name=name,
                task_type=TaskType.INTERVAL,
                task_function=function_name,
                task_data=task_data,
                interval_seconds=interval_seconds,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat() if end_time else None,
                next_execution_at=start_time.isoformat(),
                max_executions=max_executions
            )

            return self._add_task(task)

        except Exception as e:
            logger.error(f"调度重复任务失败: {e}")
            return False

    def schedule_cron_task(self, task_id: str, name: str, function_name: str,
                           task_data: dict, cron_expression: str,
                           start_time: datetime = None, end_time: datetime = None) -> bool:
        """调度Cron任务"""
        try:
            if start_time is None:
                start_time = datetime.now()

            # 计算下次执行时间
            next_execution = CronParser.get_next_execution_time(cron_expression, start_time)

            task = ScheduledTask(
                task_id=task_id,
                name=name,
                task_type=TaskType.CRON,
                task_function=function_name,
                task_data=task_data,
                schedule_expression=cron_expression,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat() if end_time else None,
                next_execution_at=next_execution.isoformat()
            )

            return self._add_task(task)

        except Exception as e:
            logger.error(f"调度Cron任务失败: {e}")
            return False

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            if task_id not in self.tasks:
                logger.warning(f"任务不存在: {task_id}")
                return False

            # 取消定时器
            if task_id in self.task_timers:
                self.task_timers[task_id].stop()
                del self.task_timers[task_id]

            # 更新任务状态
            self.tasks[task_id].status = TaskStatus.CANCELLED
            self.task_cancelled.emit(task_id)

            logger.info(f"取消任务: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return False

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        try:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED

                # 取消定时器
                if task_id in self.task_timers:
                    self.task_timers[task_id].stop()
                    del self.task_timers[task_id]

                logger.info(f"暂停任务: {task_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False

    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        try:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task.status == TaskStatus.PAUSED:
                task.status = TaskStatus.PENDING
                self._schedule_next_execution(task)

                logger.info(f"恢复任务: {task_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            return False

    def get_task_info(self, task_id: str) -> Optional[dict]:
        """获取任务信息"""
        if task_id in self.tasks:
            return self.tasks[task_id].to_dict()
        return None

    def get_all_tasks(self) -> List[dict]:
        """获取所有任务"""
        return [task.to_dict() for task in self.tasks.values()]

    def get_active_tasks(self) -> List[dict]:
        """获取活跃任务"""
        return [
            task.to_dict()
            for task in self.tasks.values()
            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
        ]

    def _add_task(self, task: ScheduledTask) -> bool:
        """添加任务"""
        try:
            if task.task_id in self.tasks:
                logger.warning(f"任务已存在: {task.task_id}")
                return False

            self.tasks[task.task_id] = task
            self.task_added.emit(task.task_id)

            # 调度下次执行
            self._schedule_next_execution(task)

            logger.info(f"添加任务: {task.task_id}")
            return True

        except Exception as e:
            logger.error(f"添加任务失败: {e}")
            return False

    def _schedule_next_execution(self, task: ScheduledTask):
        """调度下次执行"""
        try:
            if task.status not in [TaskStatus.PENDING]:
                return

            if not task.next_execution_at:
                return

            next_time = datetime.fromisoformat(task.next_execution_at)
            now = datetime.now()

            if next_time <= now:
                # 立即执行
                self._execute_task(task.task_id)
            else:
                # 延迟执行
                delay_ms = int((next_time - now).total_seconds() * 1000)

                # 确保定时器已初始化
                self._ensure_timers()

                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(lambda: self._execute_task(task.task_id))
                timer.start(delay_ms)

                self.task_timers[task.task_id] = timer

                logger.info(f"调度任务 {task.task_id}，执行时间: {next_time}")

        except Exception as e:
            logger.error(f"调度任务执行失败: {e}")

    def _execute_task(self, task_id: str):
        """执行任务"""
        try:
            if task_id not in self.tasks:
                return

            task = self.tasks[task_id]

            # 检查任务状态
            if task.status != TaskStatus.PENDING:
                return

            # 检查依赖
            if not self._check_dependencies(task):
                logger.warning(f"任务依赖未满足: {task_id}")
                return

            # 创建执行记录
            execution_id = f"{task_id}_{int(time.time())}"
            execution = TaskExecution(
                execution_id=execution_id,
                scheduled_time=task.next_execution_at,
                start_time=datetime.now().isoformat(),
                status=TaskStatus.RUNNING
            )

            task.executions.append(execution)
            task.status = TaskStatus.RUNNING
            task.execution_count += 1
            task.last_execution_at = execution.start_time

            # 发送开始信号
            self.task_started.emit(task_id, execution_id)

            # 执行任务
            success, result, error_message = self._run_task_function(task)

            # 更新执行记录
            execution.end_time = datetime.now().isoformat()
            execution.result = result
            execution.error_message = error_message
            execution.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

            # 发送完成信号
            if success:
                self.task_completed.emit(task_id, execution_id, True)
            else:
                self.task_failed.emit(task_id, execution_id, error_message)

            # 计算下次执行时间
            self._calculate_next_execution(task)

            # 清理定时器
            if task_id in self.task_timers:
                del self.task_timers[task_id]

        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            if task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.FAILED
                self.task_failed.emit(task_id, "", str(e))

    def _run_task_function(self, task: ScheduledTask) -> tuple[bool, Any, str]:
        """运行任务函数"""
        try:
            if task.task_function not in self.task_executors:
                return False, None, f"未找到任务执行器: {task.task_function}"

            executor = self.task_executors[task.task_function]
            result = executor(task.task_data)

            return True, result, ""

        except Exception as e:
            return False, None, str(e)

    def _calculate_next_execution(self, task: ScheduledTask):
        """计算下次执行时间"""
        try:
            # 检查是否已达到最大执行次数
            if task.max_executions and task.execution_count >= task.max_executions:
                task.status = TaskStatus.COMPLETED
                task.next_execution_at = None
                return

            now = datetime.now()

            # 检查结束时间
            if task.end_time:
                end_time = datetime.fromisoformat(task.end_time)
                if now >= end_time:
                    task.status = TaskStatus.COMPLETED
                    task.next_execution_at = None
                    return

            # 根据任务类型计算下次执行时间
            if task.task_type == TaskType.ONE_TIME:
                task.status = TaskStatus.COMPLETED
                task.next_execution_at = None

            elif task.task_type == TaskType.INTERVAL:
                if task.interval_seconds:
                    next_time = now + timedelta(seconds=task.interval_seconds)
                    task.next_execution_at = next_time.isoformat()
                    task.status = TaskStatus.PENDING
                    self._schedule_next_execution(task)

            elif task.task_type == TaskType.CRON:
                if task.schedule_expression:
                    next_time = CronParser.get_next_execution_time(task.schedule_expression, now)
                    task.next_execution_at = next_time.isoformat()
                    task.status = TaskStatus.PENDING
                    self._schedule_next_execution(task)

        except Exception as e:
            logger.error(f"计算下次执行时间失败: {e}")
            task.status = TaskStatus.FAILED

    def _check_dependencies(self, task: ScheduledTask) -> bool:
        """检查任务依赖"""
        try:
            for dep_task_id in task.dependencies:
                if dep_task_id not in self.tasks:
                    return False

                dep_task = self.tasks[dep_task_id]
                if dep_task.status not in [TaskStatus.COMPLETED]:
                    return False

            return True

        except Exception as e:
            logger.error(f"检查任务依赖失败: {e}")
            return False

    def _check_scheduled_tasks(self):
        """检查调度任务"""
        try:
            now = datetime.now()

            for task in self.tasks.values():
                if (task.status == TaskStatus.PENDING and
                    task.next_execution_at and
                        task.task_id not in self.task_timers):

                    next_time = datetime.fromisoformat(task.next_execution_at)
                    if next_time <= now:
                        self._execute_task(task.task_id)

        except Exception as e:
            logger.error(f"检查调度任务失败: {e}")

    def _load_tasks(self):
        """加载持久化任务"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for task_data in data.get('tasks', []):
                    task = ScheduledTask.from_dict(task_data)
                    self.tasks[task.task_id] = task

                logger.info(f"加载了 {len(self.tasks)} 个调度任务")

                # 恢复待执行的任务
                self._resume_pending_tasks()

        except Exception as e:
            logger.error(f"加载调度任务失败: {e}")

    def _save_tasks(self):
        """保存任务到文件"""
        try:
            data = {
                'tasks': [task.to_dict() for task in self.tasks.values()],
                'saved_at': datetime.now().isoformat()
            }

            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存调度任务失败: {e}")

    def _resume_pending_tasks(self):
        """恢复待执行的任务"""
        try:
            for task in self.tasks.values():
                if task.status == TaskStatus.PENDING:
                    self._schedule_next_execution(task)

        except Exception as e:
            logger.error(f"恢复待执行任务失败: {e}")

# 全局服务实例
_task_scheduler = None

def get_task_scheduler() -> TaskScheduler:
    """获取任务调度器实例"""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler
