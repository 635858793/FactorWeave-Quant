from loguru import logger
#!/usr/bin/env python3
"""
进度持久化管理器

实现保存和恢复导入进度功能,包括:
- 任务进度保存
- 断点续传
- 进度状态管理
- 数据完整性检查
"""

import json
import sqlite3
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from ..database.unified_sqlite_access import UnifiedSQLiteAccess

class ProgressStatus(Enum):
    """进度状态"""
    PENDING = "pending"  # 待开始
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 已失败
    CANCELLED = "cancelled"  # 已取消

@dataclass
class ProgressCheckpoint:
    """进度检查点"""
    checkpoint_id: str
    task_id: str
    timestamp: str
    progress_percentage: float
    current_item: str
    processed_count: int
    total_count: int
    data_snapshot: dict
    status: ProgressStatus

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ProgressCheckpoint':
        """从字典创建"""
        status = ProgressStatus(data.pop('status'))
        return cls(status=status, **data)

@dataclass
class TaskProgress:
    """任务进度"""
    task_id: str
    task_name: str
    task_type: str
    created_at: str
    updated_at: str
    status: ProgressStatus

    # 进度信息
    total_items: int
    processed_items: int
    failed_items: int
    skipped_items: int
    progress_percentage: float

    # 当前状态
    current_phase: str
    current_item: str
    estimated_remaining_time: Optional[float] = None

    # 检查点列表
    checkpoints: List[ProgressCheckpoint] = None

    # 元数据
    metadata: dict = None

    def __post_init__(self):
        if self.checkpoints is None:
            self.checkpoints = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        data['checkpoints'] = [cp.to_dict() for cp in self.checkpoints]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'TaskProgress':
        """从字典创建"""
        checkpoints_data = data.pop('checkpoints', [])
        status = ProgressStatus(data.pop('status'))

        checkpoints = [ProgressCheckpoint.from_dict(cp_data) for cp_data in checkpoints_data]

        return cls(status=status, checkpoints=checkpoints, **data)

class ProgressDatabase:
    """进度数据库管理器"""

    def __init__(self, db_path: str = "data/factorweave_system.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS task_progress (
                        task_id TEXT PRIMARY KEY,
                        task_name TEXT NOT NULL,
                        task_type TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        total_items INTEGER DEFAULT 0,
                        processed_items INTEGER DEFAULT 0,
                        failed_items INTEGER DEFAULT 0,
                        skipped_items INTEGER DEFAULT 0,
                        progress_percentage REAL DEFAULT 0.0,
                        current_phase TEXT DEFAULT '',
                        current_item TEXT DEFAULT '',
                        estimated_remaining_time REAL,
                        metadata TEXT DEFAULT '{}'
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS progress_checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        progress_percentage REAL NOT NULL,
                        current_item TEXT NOT NULL,
                        processed_count INTEGER NOT NULL,
                        total_count INTEGER NOT NULL,
                        data_snapshot TEXT NOT NULL,
                        status TEXT NOT NULL,
                        FOREIGN KEY (task_id) REFERENCES task_progress (task_id)
                    )
                ''')

                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_task_progress_status 
                    ON task_progress (status)
                ''')

                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_task_id 
                    ON progress_checkpoints (task_id, timestamp)
                ''')

        except Exception as e:
            logger.error(f"初始化进度数据库失败: {e}")
            raise

    def save_progress(self, progress: TaskProgress) -> bool:
        """保存任务进度"""
        try:
            with self._lock:
                db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
                with db.get_connection() as conn:
                    # 保存任务进度
                    conn.execute('''
                        INSERT OR REPLACE INTO task_progress 
                        (task_id, task_name, task_type, created_at, updated_at, status,
                         total_items, processed_items, failed_items, skipped_items,
                         progress_percentage, current_phase, current_item, 
                         estimated_remaining_time, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        progress.task_id, progress.task_name, progress.task_type,
                        progress.created_at, progress.updated_at, progress.status.value,
                        progress.total_items, progress.processed_items,
                        progress.failed_items, progress.skipped_items,
                        progress.progress_percentage, progress.current_phase,
                        progress.current_item, progress.estimated_remaining_time,
                        json.dumps(progress.metadata)
                    ))

                    # 保存检查点
                    for checkpoint in progress.checkpoints:
                        conn.execute('''
                            INSERT OR REPLACE INTO progress_checkpoints
                            (checkpoint_id, task_id, timestamp, progress_percentage,
                             current_item, processed_count, total_count, 
                             data_snapshot, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            checkpoint.checkpoint_id, checkpoint.task_id,
                            checkpoint.timestamp, checkpoint.progress_percentage,
                            checkpoint.current_item, checkpoint.processed_count,
                            checkpoint.total_count, json.dumps(checkpoint.data_snapshot),
                            checkpoint.status.value
                        ))

                    return True

        except Exception as e:
            logger.error(f"保存任务进度失败: {e}")
            return False

    def load_progress(self, task_id: str) -> Optional[TaskProgress]:
        """加载任务进度"""
        try:
            with self._lock:
                db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
                with db.get_connection() as conn:
                    # 加载任务进度
                    cursor = conn.execute('''
                        SELECT * FROM task_progress WHERE task_id = ?
                    ''', (task_id,))

                    row = cursor.fetchone()
                    if not row:
                        return None

                    # 加载检查点
                    checkpoints_cursor = conn.execute('''
                        SELECT * FROM progress_checkpoints 
                        WHERE task_id = ? ORDER BY timestamp
                    ''', (task_id,))

                    checkpoints = []
                    for cp_row in checkpoints_cursor.fetchall():
                        checkpoint = ProgressCheckpoint(
                            checkpoint_id=cp_row['checkpoint_id'],
                            task_id=cp_row['task_id'],
                            timestamp=cp_row['timestamp'],
                            progress_percentage=cp_row['progress_percentage'],
                            current_item=cp_row['current_item'],
                            processed_count=cp_row['processed_count'],
                            total_count=cp_row['total_count'],
                            data_snapshot=json.loads(cp_row['data_snapshot']),
                            status=ProgressStatus(cp_row['status'])
                        )
                        checkpoints.append(checkpoint)

                    # 创建进度对象
                    progress = TaskProgress(
                        task_id=row['task_id'],
                        task_name=row['task_name'],
                        task_type=row['task_type'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        status=ProgressStatus(row['status']),
                        total_items=row['total_items'],
                        processed_items=row['processed_items'],
                        failed_items=row['failed_items'],
                        skipped_items=row['skipped_items'],
                        progress_percentage=row['progress_percentage'],
                        current_phase=row['current_phase'],
                        current_item=row['current_item'],
                        estimated_remaining_time=row['estimated_remaining_time'],
                        checkpoints=checkpoints,
                        metadata=json.loads(row['metadata'])
                    )

                    return progress

        except Exception as e:
            logger.error(f"加载任务进度失败: {e}")
            return None

    def delete_progress(self, task_id: str) -> bool:
        """删除任务进度"""
        try:
            with self._lock:
                db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
                with db.get_connection() as conn:
                    conn.execute('DELETE FROM progress_checkpoints WHERE task_id = ?', (task_id,))
                    conn.execute('DELETE FROM task_progress WHERE task_id = ?', (task_id,))
                    return True

        except Exception as e:
            logger.error(f"删除任务进度失败: {e}")
            return False

    def get_all_progress(self) -> List[TaskProgress]:
        """获取所有任务进度"""
        try:
            with self._lock:
                db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
                with db.get_connection() as conn:
                    cursor = conn.execute('SELECT task_id FROM task_progress')
                    task_ids = [row['task_id'] for row in cursor.fetchall()]

                    return [self.load_progress(task_id) for task_id in task_ids if self.load_progress(task_id)]

        except Exception as e:
            logger.error(f"获取所有任务进度失败: {e}")
            return []

    def cleanup_old_progress(self, days: int = 30) -> int:
        """清理旧的进度记录"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            with self._lock:
                db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
                with db.get_connection() as conn:
                    # 删除旧的已完成任务
                    cursor = conn.execute('''
                        DELETE FROM progress_checkpoints 
                        WHERE task_id IN (
                            SELECT task_id FROM task_progress 
                            WHERE status IN ('completed', 'failed', 'cancelled') 
                            AND updated_at < ?
                        )
                    ''', (cutoff_date,))

                    deleted_checkpoints = cursor.rowcount

                    cursor = conn.execute('''
                        DELETE FROM task_progress 
                        WHERE status IN ('completed', 'failed', 'cancelled') 
                        AND updated_at < ?
                    ''', (cutoff_date,))

                    deleted_tasks = cursor.rowcount

                    logger.info(f"清理了 {deleted_tasks} 个旧任务和 {deleted_checkpoints} 个检查点")
                    return deleted_tasks

        except Exception as e:
            logger.error(f"清理旧进度记录失败: {e}")
            return 0

class ProgressPersistenceManager(QObject):
    """进度持久化管理器"""

    # 信号定义
    progress_saved = pyqtSignal(str)  # 任务ID
    progress_loaded = pyqtSignal(str, dict)  # 任务ID, 进度数据
    checkpoint_created = pyqtSignal(str, str)  # 任务ID, 检查点ID

    def __init__(self, db_path: str = "data/factorweave_system.sqlite", parent=None):
        super().__init__(parent)
        self.db = ProgressDatabase(db_path)
        self.active_progress: Dict[str, TaskProgress] = {}

        # 自动保存定时器 - 延迟初始化
        self.auto_save_timer = None

        # 清理定时器 - 延迟初始化
        self.cleanup_timer = None

    def _ensure_timers(self):
        """确保定时器已初始化"""
        if self.auto_save_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建自动保存定时器")
                return
            self.auto_save_timer = QTimer()
            self.auto_save_timer.timeout.connect(self._auto_save_all)
            self.auto_save_timer.start(30000)  # 每30秒自动保存

        if self.cleanup_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建清理定时器")
                return
            self.cleanup_timer = QTimer()
            self.cleanup_timer.timeout.connect(self._cleanup_old_progress)
            self.cleanup_timer.start(24 * 60 * 60 * 1000)  # 每24小时清理一次

    def create_task_progress(self, task_id: str, task_name: str, task_type: str,
                             total_items: int = 0) -> TaskProgress:
        """创建任务进度"""
        try:
            now = datetime.now().isoformat()

            progress = TaskProgress(
                task_id=task_id,
                task_name=task_name,
                task_type=task_type,
                created_at=now,
                updated_at=now,
                status=ProgressStatus.PENDING,
                total_items=total_items,
                processed_items=0,
                failed_items=0,
                skipped_items=0,
                progress_percentage=0.0,
                current_phase="初始化",
                current_item=""
            )

            self.active_progress[task_id] = progress
            self.save_progress(task_id)

            logger.info(f"创建任务进度: {task_id}")
            return progress

        except Exception as e:
            logger.error(f"创建任务进度失败: {e}")
            raise

    def update_progress(self, task_id: str, processed_items: int = None,
                        failed_items: int = None, current_phase: str = None,
                        current_item: str = None, metadata: dict = None) -> bool:
        """更新任务进度"""
        try:
            if task_id not in self.active_progress:
                logger.warning(f"任务进度不存在: {task_id}")
                return False

            progress = self.active_progress[task_id]
            progress.updated_at = datetime.now().isoformat()

            if processed_items is not None:
                progress.processed_items = processed_items

            if failed_items is not None:
                progress.failed_items = failed_items

            if current_phase is not None:
                progress.current_phase = current_phase

            if current_item is not None:
                progress.current_item = current_item

            if metadata is not None:
                progress.metadata.update(metadata)

            # 计算进度百分比
            if progress.total_items > 0:
                progress.progress_percentage = (progress.processed_items / progress.total_items) * 100

            # 估算剩余时间
            self._estimate_remaining_time(progress)

            return True

        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
            return False

    def create_checkpoint(self, task_id: str, data_snapshot: dict = None) -> Optional[str]:
        """创建进度检查点"""
        try:
            if task_id not in self.active_progress:
                return None

            progress = self.active_progress[task_id]
            checkpoint_id = f"{task_id}_cp_{int(datetime.now().timestamp())}"

            checkpoint = ProgressCheckpoint(
                checkpoint_id=checkpoint_id,
                task_id=task_id,
                timestamp=datetime.now().isoformat(),
                progress_percentage=progress.progress_percentage,
                current_item=progress.current_item,
                processed_count=progress.processed_items,
                total_count=progress.total_items,
                data_snapshot=data_snapshot or {},
                status=progress.status
            )

            progress.checkpoints.append(checkpoint)

            # 限制检查点数量
            if len(progress.checkpoints) > 50:
                progress.checkpoints = progress.checkpoints[-50:]

            self.checkpoint_created.emit(task_id, checkpoint_id)
            logger.info(f"创建检查点: {checkpoint_id}")

            return checkpoint_id

        except Exception as e:
            logger.error(f"创建检查点失败: {e}")
            return None

    def restore_from_checkpoint(self, task_id: str, checkpoint_id: str = None) -> Optional[dict]:
        """从检查点恢复"""
        try:
            progress = self.load_progress(task_id)
            if not progress:
                return None

            if checkpoint_id:
                # 恢复到指定检查点
                checkpoint = None
                for cp in progress.checkpoints:
                    if cp.checkpoint_id == checkpoint_id:
                        checkpoint = cp
                        break

                if not checkpoint:
                    logger.warning(f"检查点不存在: {checkpoint_id}")
                    return None
            else:
                # 恢复到最新检查点
                if not progress.checkpoints:
                    logger.warning(f"没有可用的检查点: {task_id}")
                    return None

                checkpoint = progress.checkpoints[-1]

            # 恢复进度状态
            progress.processed_items = checkpoint.processed_count
            progress.current_item = checkpoint.current_item
            progress.progress_percentage = checkpoint.progress_percentage
            progress.status = ProgressStatus.PAUSED  # 恢复后设为暂停状态
            progress.updated_at = datetime.now().isoformat()

            self.active_progress[task_id] = progress

            logger.info(f"从检查点恢复任务: {task_id} -> {checkpoint.checkpoint_id}")

            return {
                'task_progress': progress.to_dict(),
                'checkpoint_data': checkpoint.data_snapshot
            }

        except Exception as e:
            logger.error(f"从检查点恢复失败: {e}")
            return None

    def save_progress(self, task_id: str) -> bool:
        """保存任务进度"""
        try:
            # 确保定时器已初始化
            self._ensure_timers()

            if task_id not in self.active_progress:
                return False

            progress = self.active_progress[task_id]
            success = self.db.save_progress(progress)

            if success:
                self.progress_saved.emit(task_id)

            return success

        except Exception as e:
            logger.error(f"保存任务进度失败: {e}")
            return False

    def load_progress(self, task_id: str) -> Optional[TaskProgress]:
        """加载任务进度"""
        try:
            progress = self.db.load_progress(task_id)

            if progress:
                self.active_progress[task_id] = progress
                self.progress_loaded.emit(task_id, progress.to_dict())

            return progress

        except Exception as e:
            logger.error(f"加载任务进度失败: {e}")
            return None

    def complete_task(self, task_id: str, success: bool = True) -> bool:
        """完成任务"""
        try:
            if task_id not in self.active_progress:
                return False

            progress = self.active_progress[task_id]
            progress.status = ProgressStatus.COMPLETED if success else ProgressStatus.FAILED
            progress.updated_at = datetime.now().isoformat()

            if success:
                progress.progress_percentage = 100.0
                progress.current_phase = "已完成"
            else:
                progress.current_phase = "执行失败"

            return self.save_progress(task_id)

        except Exception as e:
            logger.error(f"完成任务失败: {e}")
            return False

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            if task_id not in self.active_progress:
                return False

            progress = self.active_progress[task_id]
            progress.status = ProgressStatus.CANCELLED
            progress.updated_at = datetime.now().isoformat()
            progress.current_phase = "已取消"

            return self.save_progress(task_id)

        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return False

    def get_resumable_tasks(self) -> List[dict]:
        """获取可恢复的任务"""
        try:
            all_progress = self.db.get_all_progress()
            resumable = []

            for progress in all_progress:
                if progress.status in [ProgressStatus.PAUSED, ProgressStatus.RUNNING]:
                    if progress.checkpoints:  # 有检查点才能恢复
                        resumable.append(progress.to_dict())

            return resumable

        except Exception as e:
            logger.error(f"获取可恢复任务失败: {e}")
            return []

    def _estimate_remaining_time(self, progress: TaskProgress):
        """估算剩余时间"""
        try:
            if progress.processed_items <= 0 or progress.total_items <= 0:
                return

            # 计算处理速度（基于最近的检查点）
            if len(progress.checkpoints) >= 2:
                recent_checkpoints = progress.checkpoints[-2:]

                time1 = datetime.fromisoformat(recent_checkpoints[0].timestamp)
                time2 = datetime.fromisoformat(recent_checkpoints[1].timestamp)

                time_diff = (time2 - time1).total_seconds()
                items_diff = recent_checkpoints[1].processed_count - recent_checkpoints[0].processed_count

                if time_diff > 0 and items_diff > 0:
                    items_per_second = items_diff / time_diff
                    remaining_items = progress.total_items - progress.processed_items
                    progress.estimated_remaining_time = remaining_items / items_per_second

        except Exception as e:
            logger.error(f"估算剩余时间失败: {e}")

    def _auto_save_all(self):
        """自动保存所有活跃进度"""
        try:
            for task_id in list(self.active_progress.keys()):
                self.save_progress(task_id)
        except Exception as e:
            logger.error(f"自动保存失败: {e}")

    def _cleanup_old_progress(self):
        """清理旧的进度记录"""
        try:
            self.db.cleanup_old_progress()
        except Exception as e:
            logger.error(f"清理旧进度记录失败: {e}")

# 全局服务实例
_progress_persistence_manager = None

def get_progress_persistence_manager() -> ProgressPersistenceManager:
    """获取进度持久化管理器实例"""
    global _progress_persistence_manager
    if _progress_persistence_manager is None:
        _progress_persistence_manager = ProgressPersistenceManager()
    return _progress_persistence_manager
