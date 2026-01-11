#!/usr/bin/env python3
"""
增量更新调度器

提供定时增量更新功能，支持智能调度和任务管理
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
from loguru import logger
from concurrent.futures import ThreadPoolExecutor

# 配置管理
from core.importdata.import_config_manager import ImportTaskConfig
from core.database.table_manager import TableType

# 核心服务
from core.services.unified_data_manager import UnifiedDataManager
from core.services.incremental_data_analyzer import IncrementalDataAnalyzer
from core.services.enhanced_duckdb_data_downloader import get_enhanced_duckdb_downloader
from core.services.incremental_update_recorder import IncrementalUpdateRecorder

# 事件系统
from ..events import get_event_bus


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
    incremental_days: int = 7
    gap_threshold: int = 30
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


class ScheduleType(Enum):
    """调度类型"""
    DAILY = "daily"          # 每日定时
    WEEKLY = "weekly"        # 每周定时
    MONTHLY = "monthly"      # 每月定时
    CUSTOM = "custom"        # 自定义调度
    MARKET_OPEN = "market_open"  # 市场开盘时
    MARKET_CLOSE = "market_close"  # 市场收盘时


class IncrementalUpdateScheduler(QObject):
    """增量更新调度器"""

    # 信号定义
    task_scheduled = pyqtSignal(str, str)     # 任务ID, 任务名称
    task_started = pyqtSignal(str)           # 任务ID
    task_completed = pyqtSignal(str, dict)   # 任务ID, 结果统计
    task_failed = pyqtSignal(str, str)       # 任务ID, 错误信息
    task_enabled = pyqtSignal(str, bool)     # 任务ID, 是否启用
    schedule_updated = pyqtSignal()         # 调度更新

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: Dict[str, ScheduledTask] = {}
        self.schedule_thread: Optional[threading.Thread] = None
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="IncrementalScheduler")

        # 定时器检查（每分钟检查一次）- 延迟初始化
        self.check_timer = None

        # 初始化调度器
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
            logger.info("增量更新调度器初始化完成")

        except Exception as e:
            logger.error(f"调度器初始化失败: {e}")

    def create_scheduled_task(self,
                             name: str,
                             symbols: List[str],
                             data_type: str = "K线数据",
                             frequency: str = "日线",
                             schedule_time: str = "09:30",
                             schedule_days: List[str] = ["monday", "tuesday", "wednesday", "thursday", "friday"],
                             schedule_type: ScheduleType = ScheduleType.WEEKLY,
                             incremental_days: int = 7,
                             gap_threshold: int = 30,
                             enabled: bool = True) -> str:
        """创建定时任务"""
        try:
            task_id = f"scheduled_task_{int(time.time())}"

            task = ScheduledTask(
                task_id=task_id,
                name=name,
                symbols=symbols,
                data_type=data_type,
                frequency=frequency,
                schedule_time=schedule_time,
                schedule_days=schedule_days,
                incremental_days=incremental_days,
                gap_threshold=gap_threshold,
                enabled=enabled
            )

            # 添加schedule_type属性
            task.schedule_type = schedule_type

            self.tasks[task_id] = task

            # 设置任务调度
            self._setup_task_schedule(task)

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
                task.last_run = datetime.now()
                task.next_run = self._calculate_next_run_time(task)

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
            from core.plugin_types import DataFrequency

            # 获取服务
            analyzer = get_incremental_data_analyzer()
            downloader = get_enhanced_duckdb_data_downloader()
            recorder = get_incremental_update_recorder()

            if not analyzer or not downloader or not recorder:
                raise Exception("无法获取必要的服务")

            # 频率映射
            freq_map = {
                "日线": DataFrequency.DAILY,
                "周线": DataFrequency.WEEKLY,
                "月线": DataFrequency.MONTHLY,
                "5分钟": DataFrequency.MINUTE_5,
                "15分钟": DataFrequency.MINUTE_15,
                "30分钟": DataFrequency.MINUTE_30,
                "60分钟": DataFrequency.HOUR_1
            }

            frequency = freq_map.get(task.frequency, DataFrequency.DAILY)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=task.incremental_days)

            # 分析增量需求
            download_plan = await analyzer.analyze_incremental_requirements(
                task.symbols,
                end_date,
                strategy='latest_only',
                skip_weekends=True,
                skip_holidays=True
            )

            # 创建更新记录
            record = recorder.create_update_record(
                task.task_id,
                task.name,
                download_plan.symbols_to_download,
                task.incremental_days
            )

            # 执行增量下载
            success_stats = await downloader.download_incremental_update_all_data(
                download_plan.symbols_to_download,
                end_date,
                task.incremental_days,
                skip_weekends=True,
                skip_holidays=True
            )

            # 更新记录状态
            recorder.update_record_status(
                record['id'],
                'completed',
                success_stats.get('success_count', 0),
                success_stats.get('failed_count', 0),
                success_stats.get('skipped_count', 0)
            )

            return success_stats

        except Exception as e:
            # 更新记录状态为失败
            if recorder and 'record' in locals():
                recorder.update_record_status(record['id'], 'failed', 0, len(task.symbols), 0)
            logger.error(f"增量更新执行失败: {e}")
            raise

    def _calculate_next_run_time(self, task: ScheduledTask) -> Optional[datetime]:
        """计算下次运行时间"""
        try:
            now = datetime.now()

            if task.schedule_type == ScheduleType.DAILY:
                next_run = now.replace(hour=9, minute=30, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run

            elif task.schedule_type == ScheduleType.WEEKLY:
                next_run = now.replace(hour=9, minute=30, second=0, microsecond=0)
                while next_run.weekday() not in [0, 1, 2, 3, 4]:  # 周一到周五
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

            for task_id, task in self.tasks.items():
                if task.enabled and task.next_run and now >= task.next_run:
                    logger.info(f"定时任务准备执行: {task.name}")
                    self._execute_scheduled_task(task_id)

        except Exception as e:
            logger.error(f"检查定时任务失败: {e}")

    def enable_task(self, task_id: str) -> bool:
        """启用任务"""
        try:
            if task_id in self.tasks:
                self.tasks[task_id].enabled = True
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
                'symbols_count': len(task.symbols),
                'data_type': task.data_type,
                'frequency': task.frequency,
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
                self.schedule_thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
                self.schedule_thread.start()
                logger.info("增量更新调度器已启动")
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")

    def stop_scheduler(self):
        """停止调度器"""
        try:
            if self.running:
                self.running = False
                logger.info("增量更新调度器已停止")
        except Exception as e:
            logger.error(f"停止调度器失败: {e}")

    def _run_scheduler_loop(self):
        """运行调度器循环"""
        while self.running:
            try:
                self._check_scheduled_tasks()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"调度器循环错误: {e}")
                time.sleep(60)


# 服务工厂函数
def get_incremental_update_scheduler() -> IncrementalUpdateScheduler:
    """获取增量更新调度器"""
    return IncrementalUpdateScheduler()