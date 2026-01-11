#!/usr/bin/env python3
"""
断点续传管理器

提供任务断点续传功能，支持任务暂停、恢复和状态管理
"""

import asyncio
import threading
import json
import pickle
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from loguru import logger

# 配置管理
from core.importdata.import_config_manager import ImportTaskConfig
from core.database.table_manager import TableType

# 核心服务
from core.services.enhanced_duckdb_data_downloader import get_enhanced_duckdb_downloader
from core.services.incremental_data_analyzer import IncrementalDataAnalyzer
from core.services.incremental_update_recorder import IncrementalUpdateRecorder

# 数据库
from core.database.duckdb_manager import DuckDBConnectionManager


@dataclass
class BreakpointState:
    """断点状态"""
    task_id: str
    task_name: str
    data_type: str
    frequency: str
    symbols: List[str]
    completed_symbols: List[str] = field(default_factory=list)
    failed_symbols: List[str] = field(default_factory=list)
    skipped_symbols: List[str] = field(default_factory=list)
    progress: float = 0.0
    current_symbol: Optional[str] = None
    start_time: Optional[datetime] = None
    pause_time: Optional[datetime] = None
    resume_time: Optional[datetime] = None
    status: str = "ready"  # ready, running, paused, completed, failed, stopped
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


class ResumeStrategy(Enum):
    """续传策略"""
    RESUME_FROM_FAILURE = "resume_from_failure"  # 从失败的位置续传
    RESUME_FROM_NEXT = "resume_from_next"       # 从下一个续传
    FULL_RESTART = "full_restart"               # 完全重启
    MERGE_EXISTING = "merge_existing"            # 合并已有数据


class BreakpointResumeManager(QObject):
    """断点续传管理器"""

    # 信号定义
    breakpoint_created = pyqtSignal(str, str)     # 任务ID, 任务名称
    task_paused = pyqtSignal(str, str)           # 任务ID, 暂停原因
    task_resumed = pyqtSignal(str)               # 任务ID
    task_completed = pyqtSignal(str, dict)       # 任务ID, 完成统计
    task_failed = pyqtSignal(str, str)           # 任务ID, 错误信息
    progress_updated = pyqtSignal(str, float, str)  # 任务ID, 进度, 状态信息

    def __init__(self, storage_path: str = "data/breakpoints", parent=None):
        super().__init__(parent)
        self.storage_path = storage_path
        self.breakpoints: Dict[str, BreakpointState] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.save_timer = None
        self._ensure_storage_directory()

    def _ensure_save_timer(self):
        """确保保存定时器已初始化"""
        if self.save_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建保存定时器")
                return
            self.save_timer = QTimer()
            self.save_timer.timeout.connect(self._auto_save_breakpoints)
            self.save_timer.start(30000)  # 每30秒自动保存一次

    def _ensure_storage_directory(self):
        """确保存储目录存在"""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            logger.info(f"断点续传存储目录已准备: {self.storage_path}")
        except Exception as e:
            logger.error(f"创建存储目录失败: {e}")

    def create_breakpoint(self,
                          task_id: str,
                          task_name: str,
                          data_type: str,
                          frequency: str,
                          symbols: List[str],
                          strategy: ResumeStrategy = ResumeStrategy.RESUME_FROM_FAILURE) -> str:
        """创建断点"""
        try:
            breakpoint_state = BreakpointState(
                task_id=task_id,
                task_name=task_name,
                data_type=data_type,
                frequency=frequency,
                symbols=symbols,
                strategy=strategy.value
            )

            self.breakpoints[task_id] = breakpoint_state
            self._save_breakpoint(task_id)
            self.breakpoint_created.emit(task_id, task_name)
            logger.info(f"创建断点成功: {task_name} ({task_id})")

            return task_id

        except Exception as e:
            logger.error(f"创建断点失败: {e}")
            raise

    def start_task(self, task_id: str, resume_if_paused: bool = True) -> bool:
        """启动任务"""
        try:
            if task_id not in self.breakpoints:
                logger.error(f"断点不存在: {task_id}")
                return False

            breakpoint_state = self.breakpoints[task_id]

            if breakpoint_state.status == "completed":
                logger.info(f"任务已完成，无需启动: {task_id}")
                return True

            if breakpoint_state.status == "paused" and resume_if_paused:
                self._resume_task(task_id)
            else:
                self._start_task(task_id)

            return True

        except Exception as e:
            logger.error(f"启动任务失败: {e}")
            return False

    def _start_task(self, task_id: str):
        """启动新任务"""
        try:
            breakpoint_state = self.breakpoints[task_id]

            # 更新任务状态
            breakpoint_state.status = "running"
            breakpoint_state.start_time = datetime.now()
            breakpoint_state.last_updated = datetime.now()

            # 获取需要下载的股票列表（排除已完成的）
            symbols_to_download = [
                symbol for symbol in breakpoint_state.symbols
                if symbol not in breakpoint_state.completed_symbols
                and symbol not in breakpoint_state.failed_symbols
            ]

            if not symbols_to_download:
                logger.info("所有股票已完成，无需下载")
                breakpoint_state.status = "completed"
                breakpoint_state.progress = 100.0
                self.task_completed.emit(task_id, {
                    'completed': len(breakpoint_state.completed_symbols),
                    'failed': len(breakpoint_state.failed_symbols),
                    'skipped': len(breakpoint_state.skipped_symbols)
                })
                return

            # 创建异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            task = loop.create_task(self._execute_download_with_breakpoint(task_id, symbols_to_download))

            # 保存任务引用
            self.running_tasks[task_id] = task

            # 在新线程中运行事件循环
            thread = threading.Thread(target=self._run_async_task, args=(loop, task), daemon=True)
            thread.start()

            logger.info(f"任务启动成功: {task_id}")

        except Exception as e:
            logger.error(f"启动任务失败: {e}")
            breakpoint_state.status = "failed"
            self.task_failed.emit(task_id, str(e))

    def _run_async_task(self, loop: asyncio.AbstractEventLoop, task: asyncio.Task):
        """运行异步任务"""
        try:
            loop.run_until_complete(task)
        except Exception as e:
            logger.error(f"异步任务执行失败: {e}")
        finally:
            loop.close()

    async def _execute_download_with_breakpoint(self, task_id: str, symbols: List[str]):
        """执行带断点的下载"""
        try:
            breakpoint_state = self.breakpoints[task_id]

            # 获取服务
            downloader = get_enhanced_duckdb_data_downloader()
            if not downloader:
                raise Exception("无法获取数据下载器")

            total_symbols = len(symbols)
            for i, symbol in enumerate(symbols):
                # 检查任务是否被停止
                if breakpoint_state.status == "stopped":
                    logger.info(f"任务已停止: {task_id}")
                    break

                # 更新当前符号和进度
                breakpoint_state.current_symbol = symbol
                progress = (i / total_symbols) * 100
                breakpoint_state.progress = progress
                breakpoint_state.last_updated = datetime.now()

                # 发送进度信号
                self.progress_updated.emit(task_id, progress, f"正在下载: {symbol}")

                try:
                    # 执行下载
                    success = await downloader.download_single_symbol_with_breakpoint(
                        symbol,
                        data_type=breakpoint_state.data_type,
                        frequency=breakpoint_state.frequency,
                        resume_state=breakpoint_state
                    )

                    if success:
                        breakpoint_state.completed_symbols.append(symbol)
                        logger.info(f"下载成功: {symbol}")
                    else:
                        breakpoint_state.failed_symbols.append(symbol)
                        logger.warning(f"下载失败: {symbol}")

                except Exception as e:
                    breakpoint_state.failed_symbols.append(symbol)
                    logger.error(f"下载异常: {symbol}, {e}")

            # 检查任务是否完成
            if len(breakpoint_state.completed_symbols) == total_symbols:
                breakpoint_state.status = "completed"
                breakpoint_state.progress = 100.0
                self.task_completed.emit(task_id, {
                    'completed': len(breakpoint_state.completed_symbols),
                    'failed': len(breakpoint_state.failed_symbols),
                    'skipped': len(breakpoint_state.skipped_symbols)
                })
                logger.info(f"任务完成: {task_id}")

        except Exception as e:
            breakpoint_state.status = "failed"
            self.task_failed.emit(task_id, str(e))
            logger.error(f"任务执行失败: {task_id}, {e}")

    def pause_task(self, task_id: str, reason: str = "用户手动暂停") -> bool:
        """暂停任务"""
        try:
            if task_id not in self.breakpoints:
                logger.error(f"断点不存在: {task_id}")
                return False

            breakpoint_state = self.breakpoints[task_id]

            if breakpoint_state.status == "running":
                breakpoint_state.status = "paused"
                breakpoint_state.pause_time = datetime.now()
                breakpoint_state.last_updated = datetime.now()

                # 取消异步任务
                if task_id in self.running_tasks:
                    self.running_tasks[task_id].cancel()
                    del self.running_tasks[task_id]

                self._save_breakpoint(task_id)
                self.task_paused.emit(task_id, reason)
                logger.info(f"任务已暂停: {task_id}")

                return True
            else:
                logger.warning(f"任务状态不支持暂停: {breakpoint_state.status}")
                return False

        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False

    def resume_task(self, task_id: str, strategy: Optional[ResumeStrategy] = None) -> bool:
        """恢复任务"""
        try:
            if task_id not in self.breakpoints:
                logger.error(f"断点不存在: {task_id}")
                return False

            breakpoint_state = self.breakpoints[task_id]

            if breakpoint_state.status == "paused":
                # 更新策略
                if strategy:
                    breakpoint_state.strategy = strategy.value

                # 更新恢复时间
                breakpoint_state.resume_time = datetime.now()
                breakpoint_state.last_updated = datetime.now()

                # 保存状态
                self._save_breakpoint(task_id)

                # 重新启动任务
                self._start_task(task_id)
                self.task_resumed.emit(task_id)
                logger.info(f"任务已恢复: {task_id}")

                return True
            else:
                logger.warning(f"任务状态不支持恢复: {breakpoint_state.status}")
                return False

        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            return False

    def stop_task(self, task_id: str, reason: str = "用户手动停止") -> bool:
        """停止任务"""
        try:
            if task_id not in self.breakpoints:
                logger.error(f"断点不存在: {task_id}")
                return False

            breakpoint_state = self.breakpoints[task_id]

            if breakpoint_state.status in ["running", "paused"]:
                breakpoint_state.status = "stopped"
                breakpoint_state.last_updated = datetime.now()

                # 取消异步任务
                if task_id in self.running_tasks:
                    self.running_tasks[task_id].cancel()
                    del self.running_tasks[task_id]

                self._save_breakpoint(task_id)
                logger.info(f"任务已停止: {task_id}")

                return True
            else:
                logger.warning(f"任务状态不支持停止: {breakpoint_state.status}")
                return False

        except Exception as e:
            logger.error(f"停止任务失败: {e}")
            return False

    def delete_breakpoint(self, task_id: str) -> bool:
        """删除断点"""
        try:
            if task_id in self.breakpoints:
                del self.breakpoints[task_id]
                self._delete_breakpoint_file(task_id)
                logger.info(f"断点已删除: {task_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"删除断点失败: {e}")
            return False

    def get_breakpoint_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取断点状态"""
        try:
            if task_id not in self.breakpoints:
                return None

            breakpoint_state = self.breakpoints[task_id]
            return {
                'task_id': breakpoint_state.task_id,
                'task_name': breakpoint_state.task_name,
                'data_type': breakpoint_state.data_type,
                'frequency': breakpoint_state.frequency,
                'total_symbols': len(breakpoint_state.symbols),
                'completed_symbols': len(breakpoint_state.completed_symbols),
                'failed_symbols': len(breakpoint_state.failed_symbols),
                'skipped_symbols': len(breakpoint_state.skipped_symbols),
                'progress': breakpoint_state.progress,
                'current_symbol': breakpoint_state.current_symbol,
                'status': breakpoint_state.status,
                'strategy': breakpoint_state.strategy,
                'start_time': breakpoint_state.start_time.isoformat() if breakpoint_state.start_time else None,
                'pause_time': breakpoint_state.pause_time.isoformat() if breakpoint_state.pause_time else None,
                'resume_time': breakpoint_state.resume_time.isoformat() if breakpoint_state.resume_time else None,
                'created_at': breakpoint_state.created_at.isoformat(),
                'last_updated': breakpoint_state.last_updated.isoformat()
            }
        except Exception as e:
            logger.error(f"获取断点状态失败: {e}")
            return None

    def get_all_breakpoints(self) -> List[Dict[str, Any]]:
        """获取所有断点"""
        try:
            return [self.get_breakpoint_status(task_id) for task_id in self.breakpoints.keys()]
        except Exception as e:
            logger.error(f"获取所有断点失败: {e}")
            return []

    def _save_breakpoint(self, task_id: str):
        """保存断点"""
        try:
            # 确保定时器已初始化
            self._ensure_save_timer()

            if task_id not in self.breakpoints:
                return

            breakpoint_state = self.breakpoints[task_id]
            file_path = os.path.join(self.storage_path, f"{task_id}.json")

            # 序列化状态
            state_dict = {
                'task_id': breakpoint_state.task_id,
                'task_name': breakpoint_state.task_name,
                'data_type': breakpoint_state.data_type,
                'frequency': breakpoint_state.frequency,
                'symbols': breakpoint_state.symbols,
                'completed_symbols': breakpoint_state.completed_symbols,
                'failed_symbols': breakpoint_state.failed_symbols,
                'skipped_symbols': breakpoint_state.skipped_symbols,
                'progress': breakpoint_state.progress,
                'current_symbol': breakpoint_state.current_symbol,
                'status': breakpoint_state.status,
                'strategy': breakpoint_state.strategy,
                'metadata': breakpoint_state.metadata,
                'created_at': breakpoint_state.created_at.isoformat(),
                'last_updated': breakpoint_state.last_updated.isoformat(),
                'start_time': breakpoint_state.start_time.isoformat() if breakpoint_state.start_time else None,
                'pause_time': breakpoint_state.pause_time.isoformat() if breakpoint_state.pause_time else None,
                'resume_time': breakpoint_state.resume_time.isoformat() if breakpoint_state.resume_time else None
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state_dict, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存断点失败: {e}")

    def _load_breakpoint(self, task_id: str) -> Optional[BreakpointState]:
        """加载断点"""
        try:
            file_path = os.path.join(self.storage_path, f"{task_id}.json")

            if not os.path.exists(file_path):
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                state_dict = json.load(f)

            breakpoint_state = BreakpointState(
                task_id=state_dict['task_id'],
                task_name=state_dict['task_name'],
                data_type=state_dict['data_type'],
                frequency=state_dict['frequency'],
                symbols=state_dict['symbols'],
                completed_symbols=state_dict.get('completed_symbols', []),
                failed_symbols=state_dict.get('failed_symbols', []),
                skipped_symbols=state_dict.get('skipped_symbols', []),
                progress=state_dict.get('progress', 0.0),
                current_symbol=state_dict.get('current_symbol'),
                start_time=datetime.fromisoformat(state_dict['start_time']) if state_dict.get('start_time') else None,
                pause_time=datetime.fromisoformat(state_dict['pause_time']) if state_dict.get('pause_time') else None,
                resume_time=datetime.fromisoformat(state_dict['resume_time']) if state_dict.get('resume_time') else None,
                status=state_dict['status'],
                metadata=state_dict.get('metadata', {}),
                created_at=datetime.fromisoformat(state_dict['created_at']),
                last_updated=datetime.fromisoformat(state_dict['last_updated'])
            )

            return breakpoint_state

        except Exception as e:
            logger.error(f"加载断点失败: {e}")
            return None

    def _delete_breakpoint_file(self, task_id: str):
        """删除断点文件"""
        try:
            file_path = os.path.join(self.storage_path, f"{task_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"删除断点文件失败: {e}")

    def _auto_save_breakpoints(self):
        """自动保存断点"""
        try:
            for task_id in self.breakpoints.keys():
                self._save_breakpoint(task_id)
        except Exception as e:
            logger.error(f"自动保存断点失败: {e}")

    def load_all_breakpoints(self):
        """加载所有断点"""
        try:
            if not os.path.exists(self.storage_path):
                return

            for filename in os.listdir(self.storage_path):
                if filename.endswith('.json'):
                    task_id = filename[:-5]  # 移除 .json 后缀
                    if self._load_breakpoint(task_id):
                        self.breakpoints[task_id] = self._load_breakpoint(task_id)
                        logger.info(f"加载断点成功: {task_id}")

        except Exception as e:
            logger.error(f"加载所有断点失败: {e}")

    def validate_breakpoint(self, task_id: str) -> bool:
        """验证断点有效性"""
        try:
            if task_id not in self.breakpoints:
                return False

            breakpoint_state = self.breakpoints[task_id]

            # 检查必要字段
            required_fields = ['task_id', 'task_name', 'data_type', 'frequency', 'symbols', 'status']
            for field in required_fields:
                if not getattr(breakpoint_state, field, None):
                    return False

            return True

        except Exception as e:
            logger.error(f"验证断点失败: {e}")
            return False


# 服务工厂函数
def get_breakpoint_resume_manager() -> BreakpointResumeManager:
    """获取断点续传管理器"""
    return BreakpointResumeManager()