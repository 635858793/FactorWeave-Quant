#!/usr/bin/env python3
"""
增量更新调度器

提供定时增量更新功能，支持智能调度和任务管理
"""

import asyncio
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from loguru import logger
from concurrent.futures import ThreadPoolExecutor

from core.services.incremental_data_analyzer import IncrementalDataAnalyzer
from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
from core.services.incremental_update_recorder import IncrementalUpdateRecorder
from ..events import EventBus


class ScheduleType(Enum):
    """调度类型"""
    DAILY = "daily"          # 每日定时
    WEEKLY = "weekly"        # 每周定时
    MONTHLY = "monthly"      # 每月定时
    CUSTOM = "custom"        # 自定义调度
    MARKET_OPEN = "market_open"  # 市场开盘时
    MARKET_CLOSE = "market_close"  # 市场收盘时


@dataclass
class ScheduledTask:
    """定时任务配置"""
    task_id: str
    name: str
    symbols: List[str]
    data_type: str
    frequency: str
    schedule_time: str
    schedule_days: List[str]
    schedule_type: ScheduleType = ScheduleType.WEEKLY
    incremental_days: int = 7
    gap_threshold: int = 30
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


class IncrementalUpdateScheduler(QObject):
    """增量更新调度器"""

    # 信号定义
    task_scheduled = pyqtSignal(str, str)
    task_started = pyqtSignal(str)
    task_completed = pyqtSignal(str, dict)
    task_failed = pyqtSignal(str, str)
    task_enabled = pyqtSignal(str, bool)
    schedule_updated = pyqtSignal()

    TASKS_FILE = "config/scheduled_tasks.json"

    def __init__(self,
                 analyzer: IncrementalDataAnalyzer,
                 downloader: EnhancedDuckDBDataDownloader,
                 recorder: IncrementalUpdateRecorder,
                 event_bus: EventBus,
                 parent=None):
        super().__init__(parent)
        self.analyzer = analyzer
        self.downloader = downloader
        self.recorder = recorder
        self.event_bus = event_bus
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="IncrementalScheduler")
        self.check_timer = None
        self._lock = threading.Lock()
        self._tasks_file = Path(self.TASKS_FILE)
        self._init_scheduler()

    def _ensure_check_timer(self):
        """确保检查定时器已初始化"""
        if self.check_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建检查定时器")
                return
            self.check_timer = QTimer()
            self.check_timer.timeout.connect(self._check_scheduled_tasks)
            self.check_timer.start(60000)  # 1分钟检查一次

    def _init_scheduler(self):
        """初始化调度器"""
        try:
            self._load_tasks()
            logger.info("增量更新调度器初始化完成")

        except Exception as e:
            logger.error(f"调度器初始化失败: {e}")

    def create_scheduled_task(self,
                             name: str,
                             symbols: List[str],
                             data_type: str = "K线数据",
                             frequency: str = "日线",
                             schedule_time: str = "09:30",
                             schedule_days: List[str] = None,
                             schedule_type: ScheduleType = ScheduleType.WEEKLY,
                             incremental_days: int = 7,
                             gap_threshold: int = 30,
                             enabled: bool = True) -> str:
        """创建定时任务"""
        try:
            if schedule_days is None:
                schedule_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
            task_id = f"scheduled_task_{int(datetime.now().timestamp())}"

            task = ScheduledTask(
                task_id=task_id,
                name=name,
                symbols=symbols,
                data_type=data_type,
                frequency=frequency,
                schedule_time=schedule_time,
                schedule_days=schedule_days,
                schedule_type=schedule_type,
                incremental_days=incremental_days,
                gap_threshold=gap_threshold,
                enabled=enabled
            )

            self.tasks[task_id] = task
            self._setup_task_schedule(task)
            self._save_tasks()
            self.task_scheduled.emit(task_id, name)
            logger.info(f"创建定时任务成功: {name} ({task_id})")

            return task_id

        except Exception as e:
            logger.error(f"创建定时任务失败: {e}")
            raise

    def _setup_task_schedule(self, task: ScheduledTask):
        """设置任务调度"""
        try:
            if not task.enabled:
                return

            # 计算下一次运行时间
            task.next_run = self._calculate_next_run_time(task)
            logger.info(f"任务 {task.task_id} 已调度，下次运行时间: {task.next_run}")

        except Exception as e:
            logger.error(f"设置任务调度失败: {e}")

    def _execute_scheduled_task(self, task_id: str):
        """执行定时任务"""
        try:
            if task_id not in self.tasks:
                logger.error(f"任务不存在: {task_id}")
                return

            task = self.tasks[task_id]
            if not task.enabled:
                logger.info(f"任务已禁用，跳过执行: {task_id}")
                return

            self.task_started.emit(task_id)
            logger.info(f"开始执行定时任务: {task.name}")

            # 在线程池中执行异步任务
            self.executor.submit(self._execute_task_in_thread, task)

        except Exception as e:
            self.task_failed.emit(task_id, str(e))
            logger.error(f"定时任务执行失败: {e}")

    def _execute_task_in_thread(self, task: ScheduledTask):
        """在线程中执行任务"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                success_stats = loop.run_until_complete(self._execute_incremental_update(task))

                # 更新任务执行时间
                with self._lock:
                    task.last_run = datetime.now()
                    task.next_run = self._calculate_next_run_time(task)
                
                self._save_tasks()

                self.task_completed.emit(task.task_id, {
                    'success': True,
                    'success_count': success_stats.get('success_count', 0),
                    'failed_count': success_stats.get('failed_count', 0),
                    'skipped_count': success_stats.get('skipped_count', 0),
                    'timestamp': datetime.now().isoformat()
                })

                logger.info(f"定时任务执行完成: {task.name}")

            finally:
                loop.close()

        except Exception as e:
            self.task_failed.emit(task.task_id, str(e))
            logger.error(f"定时任务执行失败: {e}")

    async def _execute_incremental_update(self, task: ScheduledTask):
        """执行增量更新"""
        try:
            from core.plugin_types import DataFrequency, Period

            period_to_data_freq = {
                Period.DAY.value: DataFrequency.DAILY,
                Period.WEEK.value: DataFrequency.WEEKLY,
                Period.MONTH.value: DataFrequency.MONTHLY,
                Period.MIN5.value: DataFrequency.MINUTE_5,
                Period.MIN15.value: DataFrequency.MINUTE_15,
                Period.MIN30.value: DataFrequency.MINUTE_30,
                Period.MIN60.value: DataFrequency.HOUR_1
            }
            period_value = Period.normalize(task.frequency)
            frequency = period_to_data_freq.get(period_value, DataFrequency.DAILY)
            end_date = datetime.now()

            download_plan = await self.analyzer.analyze_incremental_requirements(
                task.symbols,
                end_date,
                strategy='latest_only',
                skip_weekends=True,
                skip_holidays=True
            )

            task_id = self.recorder.create_update_task(
                task_name=task.name,
                symbols=download_plan.symbols_to_download,
                date_range=(end_date - timedelta(days=task.incremental_days), end_date),
                update_type=self.recorder.UpdateType.SCHEDULED,
                strategy='latest_only'
            )

            success_stats = await self.downloader.download_incremental_update_all_data(
                days=task.incremental_days
            )

            execution_time = 0.0
            if success_stats:
                execution_time = success_stats.get('execution_time', 0.0)
                self.recorder.complete_task(
                    task_id,
                    success_stats.get('total_records', 0),
                    execution_time
                )

            return success_stats

        except Exception as e:
            logger.error(f"增量更新执行失败: {e}")
            raise

    def _calculate_next_run_time(self, task: ScheduledTask) -> Optional[datetime]:
        """计算下次运行时间"""
        try:
            now = datetime.now()
            hour, minute = 9, 30
            if task.schedule_time:
                try:
                    parts = task.schedule_time.split(':')
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                except (ValueError, IndexError):
                    pass

            if task.schedule_type == ScheduleType.DAILY:
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run

            elif task.schedule_type == ScheduleType.WEEKLY:
                weekday_map = {
                    'monday': 0, 'tuesday': 1, 'wednesday': 2,
                    'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
                }
                allowed_days = [weekday_map.get(d.lower(), -1) for d in task.schedule_days]
                allowed_days = [d for d in allowed_days if d >= 0]
                if not allowed_days:
                    allowed_days = [0, 1, 2, 3, 4]

                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                while next_run.weekday() not in allowed_days:
                    next_run += timedelta(days=1)
                return next_run

            elif task.schedule_type == ScheduleType.MONTHLY:
                next_run = now.replace(day=1, hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    if now.month == 12:
                        next_run = next_run.replace(year=now.year + 1, month=1)
                    else:
                        next_run = next_run.replace(month=now.month + 1)
                return next_run

            elif task.schedule_type == ScheduleType.MARKET_OPEN:
                next_run = now.replace(hour=9, minute=30, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                while next_run.weekday() not in [0, 1, 2, 3, 4]:
                    next_run += timedelta(days=1)
                return next_run

            elif task.schedule_type == ScheduleType.MARKET_CLOSE:
                next_run = now.replace(hour=15, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                while next_run.weekday() not in [0, 1, 2, 3, 4]:
                    next_run += timedelta(days=1)
                return next_run

            elif task.schedule_type == ScheduleType.CUSTOM:
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run

            return None

        except Exception as e:
            logger.error(f"计算下次运行时间失败: {e}")
            return None

    def _daily_market_open_task(self):
        """每日市场开盘任务"""
        logger.info("执行每日市场开盘检查任务")
        self._execute_all_enabled_tasks()

    def _daily_market_close_task(self):
        """每日市场收盘任务"""
        logger.info("执行每日市场收盘更新任务")
        self._execute_all_enabled_tasks()

    def _weekly_update_task(self):
        """每周更新任务"""
        logger.info("执行每周更新任务")
        self._execute_all_enabled_tasks()

    def _monthly_update_task(self):
        """每月更新任务"""
        logger.info("执行每月更新任务")
        self._execute_all_enabled_tasks()

    def _execute_all_enabled_tasks(self):
        """执行所有启用的任务"""
        for task_id, task in self.tasks.items():
            if task.enabled:
                self._execute_scheduled_task(task_id)

    def _check_scheduled_tasks(self):
        """检查定时任务（每分钟调用）"""
        try:
            now = datetime.now()
            
            tasks_to_execute = []
            with self._lock:
                for task_id, task in self.tasks.items():
                    if task.enabled and task.next_run and now >= task.next_run:
                        tasks_to_execute.append(task_id)

            for task_id in tasks_to_execute:
                logger.info(f"定时任务准备执行: {self.tasks[task_id].name}")
                self._execute_scheduled_task(task_id)

        except Exception as e:
            logger.error(f"检查定时任务失败: {e}")

    def enable_task(self, task_id: str) -> bool:
        """启用任务"""
        try:
            if task_id in self.tasks:
                self.tasks[task_id].enabled = True
                self._save_tasks()
                self.task_enabled.emit(task_id, True)
                logger.info(f"任务已启用: {task_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"启用任务失败: {e}")
            return False

    def disable_task(self, task_id: str) -> bool:
        """禁用任务"""
        try:
            if task_id in self.tasks:
                self.tasks[task_id].enabled = False
                self._save_tasks()
                self.task_enabled.emit(task_id, False)
                logger.info(f"任务已禁用: {task_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"禁用任务失败: {e}")
            return False

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        try:
            if task_id in self.tasks:
                del self.tasks[task_id]
                logger.info(f"任务已删除: {task_id}")
                self.schedule_updated.emit()
                return True
            return False
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        try:
            if task_id not in self.tasks:
                return None

            task = self.tasks[task_id]
            return {
                'task_id': task.task_id,
                'name': task.name,
                'enabled': task.enabled,
                'last_run': task.last_run.isoformat() if task.last_run else None,
                'next_run': task.next_run.isoformat() if task.next_run else None,
                'created_at': task.created_at.isoformat(),
                'symbols': task.symbols,
                'symbols_count': len(task.symbols),
                'data_type': task.data_type,
                'frequency': task.frequency,
                'schedule_type': task.schedule_type,
                'schedule_time': task.schedule_time,
                'schedule_days': task.schedule_days,
                'incremental_days': task.incremental_days,
                'gap_threshold': task.gap_threshold
            }
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return None

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        try:
            tasks = []
            for task_id, task in self.tasks.items():
                tasks.append(self.get_task_status(task_id))
            return tasks
        except Exception as e:
            logger.error(f"获取所有任务失败: {e}")
            return []

    def start_scheduler(self):
        """启动调度器"""
        try:
            if not self.running:
                self.running = True
                self._ensure_check_timer()
                logger.info("增量更新调度器已启动")
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")

    def stop_scheduler(self):
        """停止调度器"""
        try:
            if self.running:
                self.running = False
                if self.check_timer:
                    self.check_timer.stop()
                    self.check_timer = None
                self.executor.shutdown(wait=False)
                self._save_tasks()
                logger.info("增量更新调度器已停止")
        except Exception as e:
            logger.error(f"停止调度器失败: {e}")
    
    def _save_tasks(self):
        """保存任务到文件"""
        try:
            self._tasks_file.parent.mkdir(parents=True, exist_ok=True)
            
            tasks_data = []
            with self._lock:
                for task in self.tasks.values():
                    task_dict = {
                        'task_id': task.task_id,
                        'name': task.name,
                        'symbols': task.symbols,
                        'data_type': task.data_type,
                        'frequency': task.frequency,
                        'schedule_time': task.schedule_time,
                        'schedule_days': task.schedule_days,
                        'schedule_type': task.schedule_type.value if task.schedule_type else None,
                        'incremental_days': task.incremental_days,
                        'gap_threshold': task.gap_threshold,
                        'enabled': task.enabled,
                        'last_run': task.last_run.isoformat() if task.last_run else None,
                        'next_run': task.next_run.isoformat() if task.next_run else None,
                        'created_at': task.created_at.isoformat() if task.created_at else None
                    }
                    tasks_data.append(task_dict)
            
            with open(self._tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存 {len(tasks_data)} 个定时任务到 {self._tasks_file}")
            
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
    
    def _load_tasks(self):
        """从文件加载任务"""
        try:
            if not self._tasks_file.exists():
                logger.info("任务文件不存在，跳过加载")
                return
            
            with open(self._tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            
            with self._lock:
                for task_dict in tasks_data:
                    schedule_type_value = task_dict.get('schedule_type')
                    schedule_type = ScheduleType(schedule_type_value) if schedule_type_value else ScheduleType.WEEKLY
                    
                    task = ScheduledTask(
                        task_id=task_dict['task_id'],
                        name=task_dict['name'],
                        symbols=task_dict.get('symbols', []),
                        data_type=task_dict.get('data_type', 'K线数据'),
                        frequency=task_dict.get('frequency', '日线'),
                        schedule_time=task_dict.get('schedule_time', '09:30'),
                        schedule_days=task_dict.get('schedule_days', []),
                        schedule_type=schedule_type,
                        incremental_days=task_dict.get('incremental_days', 7),
                        gap_threshold=task_dict.get('gap_threshold', 30),
                        enabled=task_dict.get('enabled', True),
                        last_run=datetime.fromisoformat(task_dict['last_run']) if task_dict.get('last_run') else None,
                        next_run=datetime.fromisoformat(task_dict['next_run']) if task_dict.get('next_run') else None,
                        created_at=datetime.fromisoformat(task_dict['created_at']) if task_dict.get('created_at') else datetime.now()
                    )
                    
                    self.tasks[task.task_id] = task
                    
                    if task.enabled and task.next_run is None:
                        task.next_run = self._calculate_next_run_time(task)
            
            logger.info(f"已加载 {len(self.tasks)} 个定时任务")
            
        except Exception as e:
            logger.error(f"加载任务失败: {e}")
    
    def remove_task(self, task_id: str) -> bool:
        """删除任务并保存"""
        result = self.delete_task(task_id)
        if result:
            self._save_tasks()
        return result