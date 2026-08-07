#!/usr/bin/env python3
"""
定时任务执行服务

负责定时扫描和执行配置了定时规则的任务
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from loguru import logger

from core.importdata.import_config_manager import ImportConfigManager


class CronParser:
    """Cron表达式解析器（简化版）"""

    @staticmethod
    def is_valid(cron_expr: str) -> bool:
        """验证Cron表达式是否有效"""
        try:
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def should_execute(cron_expr: str, last_executed: Optional[datetime], now: datetime) -> bool:
        """判断当前时间是否应该执行"""
        try:
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                return False

            minute_expr, hour_expr, day_expr, month_expr, weekday_expr = parts

            if not CronParser._match_field(now.minute, minute_expr, 0, 59):
                return False
            if not CronParser._match_field(now.hour, hour_expr, 0, 23):
                return False
            if not CronParser._match_field(now.day, day_expr, 1, 31):
                return False
            if not CronParser._match_field(now.month, month_expr, 1, 12):
                return False
            if not CronParser._match_field(now.weekday(), weekday_expr, 0, 6):
                return False

            if last_executed:
                if last_executed.year == now.year and last_executed.month == now.month and last_executed.day == now.day:
                    if last_executed.hour == now.hour and last_executed.minute == now.minute:
                        return False

            return True

        except Exception as e:
            logger.error(f"Cron匹配失败: {e}")
            return False

    @staticmethod
    def _match_field(value: int, expr: str, min_val: int, max_val: int) -> bool:
        """匹配单个字段"""
        if expr == '*':
            return True

        if ',' in expr:
            values = [int(v.strip()) for v in expr.split(',')]
            return value in values

        if '/' in expr:
            if expr.startswith('*/'):
                step = int(expr[2:])
                return value % step == 0
            else:
                range_part, step_part = expr.split('/')
                step = int(step_part)
                if range_part == '*':
                    return value % step == 0
                else:
                    start, end = map(int, range_part.split('-'))
                    return start <= value <= end and (value - start) % step == 0

        if '-' in expr:
            start, end = map(int, expr.split('-'))
            return start <= value <= end

        return value == int(expr)


class ScheduledTaskExecutor(QObject):
    """定时任务执行器"""

    task_triggered = pyqtSignal(str, str)  # task_id, task_name
    task_executed = pyqtSignal(str, bool, str)  # task_id, success, message
    schedule_checked = pyqtSignal(int)  # checked_count

    def __init__(self, config_manager: ImportConfigManager = None):
        super().__init__()
        self.config_manager = config_manager or ImportConfigManager()
        self.import_engine = None
        self.running = False
        self.check_timer: Optional[QTimer] = None
        self.last_executed: Dict[str, datetime] = {}
        self._lock = threading.Lock()

        logger.info("定时任务执行器初始化完成")

    def set_import_engine(self, import_engine):
        """设置导入引擎"""
        self.import_engine = import_engine
        logger.info("导入引擎已绑定到定时任务执行器")

    def start(self):
        """启动定时任务执行器"""
        if self.running:
            logger.warning("定时任务执行器已在运行")
            return

        self.running = True
        self._start_timer()
        logger.info("定时任务执行器已启动")

    def stop(self):
        """停止定时任务执行器"""
        self.running = False
        if self.check_timer:
            self.check_timer.stop()
            self.check_timer = None
        logger.info("定时任务执行器已停止")

    def _start_timer(self):
        """启动定时检查"""
        try:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建定时器")
                return

            self.check_timer = QTimer()
            self.check_timer.timeout.connect(self.check_and_execute)
            self.check_timer.start(60000)  # 每分钟检查一次
        except Exception as e:
            logger.error(f"启动定时器失败: {e}")

    def check_and_execute(self):
        """检查并执行到期的任务"""
        if not self.running:
            return

        try:
            tasks = self.config_manager.get_import_tasks()
            checked_count = 0
            scheduled_count = 0
            disabled_count = 0
            no_cron_count = 0
            now = datetime.now()

            for task in tasks:
                checked_count += 1

                if not task.enabled:
                    disabled_count += 1
                    continue

                if not hasattr(task, 'schedule_cron') or not task.schedule_cron:
                    no_cron_count += 1
                    continue

                scheduled_count += 1
                if self._should_execute(task.schedule_cron, task.task_id, now):
                    self._execute_task(task.task_id)

            if scheduled_count > 0:
                logger.info(f"定时任务检查: 共{checked_count}个任务, {scheduled_count}个定时任务, {disabled_count}个已禁用, {no_cron_count}个无定时配置")

            self.schedule_checked.emit(checked_count)

        except Exception as e:
            logger.error(f"检查定时任务失败: {e}")

    def _should_execute(self, cron_expr: str, task_id: str, now: datetime) -> bool:
        """判断任务是否应该执行"""
        try:
            with self._lock:
                last_exec = self.last_executed.get(task_id)

                if not CronParser.is_valid(cron_expr):
                    logger.warning(f"无效的Cron表达式: {cron_expr}")
                    return False

                return CronParser.should_execute(cron_expr, last_exec, now)

        except Exception as e:
            logger.error(f"判断任务执行失败: {e}")
            return False

    def _execute_task(self, task_id: str):
        """执行任务"""
        try:
            task = self.config_manager.get_import_task(task_id)
            if not task:
                logger.error(f"任务不存在: {task_id}")
                self.task_executed.emit(task_id, False, "任务不存在")
                return

            with self._lock:
                self.last_executed[task_id] = datetime.now()

            self.task_triggered.emit(task_id, task.name)
            logger.info(f"触发定时任务: {task.name} ({task_id})")

            if not self.import_engine:
                # 懒加载导入引擎：构造可能较慢且会连接增强服务，失败不影响定时器继续运行
                try:
                    from core.importdata.import_execution_engine import DataImportExecutionEngine
                    logger.info("导入引擎未设置，自动创建导入引擎实例...")
                    self.import_engine = DataImportExecutionEngine(
                        config_manager=self.config_manager,
                        max_workers=8
                    )
                    logger.info("导入引擎自动创建成功")
                except Exception as e:
                    logger.error(f"创建导入引擎失败: {e}")
                    self.task_executed.emit(task_id, False, f"导入引擎创建失败: {e}")
                    return

            success = self.import_engine.start_task(task_id)
            if success:
                logger.info(f"定时任务启动成功: {task_id}")
                self.task_executed.emit(task_id, True, "任务已启动")
            else:
                logger.error(f"定时任务启动失败: {task_id}")
                self.task_executed.emit(task_id, False, "任务启动失败")

        except Exception as e:
            logger.error(f"执行定时任务失败: {e}")
            self.task_executed.emit(task_id, False, str(e))

    def get_scheduled_tasks(self) -> List[Dict]:
        """获取所有定时任务"""
        try:
            tasks = self.config_manager.get_import_tasks()
            scheduled = []

            for task in tasks:
                if hasattr(task, 'schedule_cron') and task.schedule_cron and task.enabled:
                    scheduled.append({
                        'task_id': task.task_id,
                        'task_name': task.name,
                        'schedule_cron': task.schedule_cron,
                        'enabled': task.enabled,
                        'data_source': task.data_source,
                        'asset_type': task.asset_type
                    })

            return scheduled

        except Exception as e:
            logger.error(f"获取定时任务列表失败: {e}")
            return []

    def trigger_now(self, task_id: str) -> bool:
        """立即触发任务"""
        try:
            task = self.config_manager.get_import_task(task_id)
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return False

            self._execute_task(task_id)
            return True

        except Exception as e:
            logger.error(f"立即触发任务失败: {e}")
            return False


_scheduled_task_executor: Optional[ScheduledTaskExecutor] = None


def get_scheduled_task_executor() -> ScheduledTaskExecutor:
    """获取定时任务执行器实例"""
    global _scheduled_task_executor
    if _scheduled_task_executor is None:
        _scheduled_task_executor = ScheduledTaskExecutor()
    return _scheduled_task_executor


def start_scheduled_task_executor(import_engine=None):
    """启动定时任务执行器"""
    executor = get_scheduled_task_executor()
    if import_engine:
        executor.set_import_engine(import_engine)
    executor.start()
    return executor


def stop_scheduled_task_executor():
    """停止定时任务执行器"""
    global _scheduled_task_executor
    if _scheduled_task_executor:
        _scheduled_task_executor.stop()
        _scheduled_task_executor = None
