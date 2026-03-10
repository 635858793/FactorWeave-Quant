"""
Incremental Update Recorder Module

This module provides functionality to track and record incremental update
history, including update ranges, results, and metadata.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

from ..database.duckdb_manager import DuckDBConnectionManager
from ..events.event_bus import EventBus
from ..events.types import UpdateHistoryEvent

logger = logging.getLogger(__name__)


class UpdateStatus(Enum):
    """Update status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class UpdateType(Enum):
    """Update type enumeration"""
    INCREMENTAL = "incremental"
    FULL = "full"
    GAP_FILL = "gap_fill"
    SCHEDULED = "scheduled"


@dataclass
class UpdateTask:
    """Update task information"""
    task_id: str
    task_name: str
    update_type: UpdateType
    symbols: List[str]
    date_range: Tuple[datetime, datetime]
    strategy: str
    status: UpdateStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    total_symbols: int = 0
    completed_symbols: int = 0
    success_symbols: int = 0
    failed_symbols: int = 0
    skipped_symbols: int = 0
    estimated_records: int = 0
    actual_records: int = 0
    error_messages: Dict[str, str] = None

    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = {}


@dataclass
class UpdateRecord:
    """Update record for database storage"""
    id: int
    task_id: str
    task_name: str
    update_type: str
    symbols: str  # JSON string
    date_range: str  # JSON string
    result: str  # JSON string
    new_records_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    error_messages: str  # JSON string
    execution_time: float
    created_at: datetime
    updated_at: datetime


@dataclass
class UpdateHistoryItem:
    """Update history item for display"""
    id: int
    task_name: str
    update_type: str
    symbols_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    new_records_count: int
    execution_time: float
    created_at: datetime
    status: str


class IncrementalUpdateRecorder:
    """Service to track and record incremental update history"""

    def __init__(self, db_manager: DuckDBConnectionManager, event_bus: EventBus, db_path: str = None):
        self.db_manager = db_manager
        self.event_bus = event_bus
        self._active_tasks = {}
        self._task_counter = 0
        # Use provided db_path or default to system database
        self.db_path = db_path or "data/factorweave_system.sqlite"

        # Initialize database tables
        self._initialize_tables()

    def _initialize_tables(self):
        """Initialize database tables for update tracking"""
        # Create update history table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS incremental_update_history (
            id INTEGER PRIMARY KEY,
            task_id TEXT NOT NULL,
            task_name TEXT NOT NULL,
            update_type TEXT NOT NULL,
            symbols TEXT NOT NULL,
            date_range TEXT NOT NULL,
            result TEXT NOT NULL,
            new_records_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            error_messages TEXT DEFAULT '{}',
            execution_time REAL DEFAULT 0.0,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """

        with self.db_manager.get_connection(self.db_path) as conn:
            conn.execute(create_table_query)

        # Create active tasks table
        create_active_tasks_query = """
        CREATE TABLE IF NOT EXISTS incremental_update_tasks (
            id INTEGER PRIMARY KEY,
            task_id TEXT UNIQUE NOT NULL,
            task_name TEXT NOT NULL,
            update_type TEXT NOT NULL,
            symbols TEXT NOT NULL,
            date_range TEXT NOT NULL,
            strategy TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            progress REAL DEFAULT 0.0,
            total_symbols INTEGER DEFAULT 0,
            completed_symbols INTEGER DEFAULT 0,
            success_symbols INTEGER DEFAULT 0,
            failed_symbols INTEGER DEFAULT 0,
            skipped_symbols INTEGER DEFAULT 0,
            estimated_records INTEGER DEFAULT 0,
            actual_records INTEGER DEFAULT 0,
            error_messages TEXT DEFAULT '{}'
        )
        """

        with self.db_manager.get_connection(self.db_path) as conn:
            conn.execute(create_active_tasks_query)

        # Create indexes for performance
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_update_history_task_id ON incremental_update_history(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_update_history_created_at ON incremental_update_history(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_active_tasks_task_id ON incremental_update_tasks(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_active_tasks_status ON incremental_update_tasks(status)"
        ]

        with self.db_manager.get_connection(self.db_path) as conn:
            for query in index_queries:
                conn.execute(query)

    def create_update_task(
        self,
        task_name: str,
        symbols: List[str],
        date_range: Tuple[datetime, datetime],
        update_type: UpdateType,
        strategy: str
    ) -> str:
        """
        Create a new update task

        Args:
            task_name: Name of the task
            symbols: List of symbols to update
            date_range: Tuple of (start_date, end_date)
            update_type: Type of update
            strategy: Update strategy

        Returns:
            Task ID for the created task
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._task_counter}"
        self._task_counter += 1

        task = UpdateTask(
            task_id=task_id,
            task_name=task_name,
            update_type=update_type,
            symbols=symbols,
            date_range=date_range,
            strategy=strategy,
            status=UpdateStatus.PENDING,
            created_at=datetime.now()
        )

        self._active_tasks[task_id] = task

        # Save to database
        self._save_active_task(task)

        # Publish event
        self.event_bus.publish(UpdateHistoryEvent(
            task_id=task_id,
            task_name=task_name,
            update_type=update_type.value,
            action="created",
            symbols_count=len(symbols),
            date_range=date_range
        ))

        logger.info(f"Created update task: {task_id} - {task_name}")
        return task_id

    def start_task(self, task_id: str) -> bool:
        """
        Start an update task

        Args:
            task_id: Task ID to start

        Returns:
            True if task was started successfully
        """
        if task_id not in self._active_tasks:
            logger.error(f"Task not found: {task_id}")
            return False

        task = self._active_tasks[task_id]
        task.status = UpdateStatus.RUNNING
        task.started_at = datetime.now()

        self._save_active_task(task)

        # Publish event
        self.event_bus.publish(UpdateHistoryEvent(
            task_id=task_id,
            task_name=task.task_name,
            update_type=task.update_type.value,
            action="started",
            progress=task.progress
        ))

        logger.info(f"Started task: {task_id}")
        return True

    def update_task_progress(
        self,
        task_id: str,
        completed_symbols: int,
        success_symbols: int,
        failed_symbols: int,
        skipped_symbols: int,
        actual_records: int,
        progress: float,
        error_messages: Dict[str, str] = None
    ) -> bool:
        """
        Update task progress

        Args:
            task_id: Task ID
            completed_symbols: Number of completed symbols
            success_symbols: Number of successful symbols
            failed_symbols: Number of failed symbols
            skipped_symbols: Number of skipped symbols
            actual_records: Number of actual records downloaded
            progress: Progress percentage (0-100)
            error_messages: Dictionary of error messages per symbol

        Returns:
            True if progress was updated successfully
        """
        if task_id not in self._active_tasks:
            logger.error(f"Task not found: {task_id}")
            return False

        task = self._active_tasks[task_id]
        task.completed_symbols = completed_symbols
        task.success_symbols = success_symbols
        task.failed_symbols = failed_symbols
        task.skipped_symbols = skipped_symbols
        task.actual_records = actual_records
        task.progress = progress

        if error_messages:
            task.error_messages.update(error_messages)

        self._save_active_task(task)

        # Publish event
        self.event_bus.publish(UpdateHistoryEvent(
            task_id=task_id,
            task_name=task.task_name,
            update_type=task.update_type.value,
            action="progress",
            progress=progress,
            success_count=success_symbols,
            failed_count=failed_symbols,
            skipped_count=skipped_symbols,
            actual_records=actual_records
        ))

        logger.info(f"Updated progress for task {task_id}: {progress:.1f}%")
        return True

    def complete_task(self, task_id: str, new_records_count: int, execution_time: float) -> bool:
        """
        Complete an update task

        Args:
            task_id: Task ID
            new_records_count: Number of new records downloaded
            execution_time: Execution time in seconds

        Returns:
            True if task was completed successfully
        """
        if task_id not in self._active_tasks:
            logger.error(f"Task not found: {task_id}")
            return False

        task = self._active_tasks[task_id]
        task.status = UpdateStatus.COMPLETED
        task.completed_at = datetime.now()
        task.new_records_count = new_records_count
        task.actual_records = new_records_count
        task.progress = 100.0

        # Move from active tasks to history
        self._save_to_history(task, execution_time)
        del self._active_tasks[task_id]

        # Publish event
        self.event_bus.publish(UpdateHistoryEvent(
            task_id=task_id,
            task_name=task.task_name,
            update_type=task.update_type.value,
            action="completed",
            progress=100.0,
            success_count=task.success_symbols,
            failed_count=task.failed_symbols,
            skipped_count=task.skipped_symbols,
            new_records_count=new_records_count,
            execution_time=execution_time
        ))

        logger.info(f"Completed task: {task_id} with {new_records_count} new records in {execution_time:.2f}s")
        return True

    def fail_task(self, task_id: str, error_message: str) -> bool:
        """
        Mark a task as failed

        Args:
            task_id: Task ID
            error_message: Error message

        Returns:
            True if task was marked as failed successfully
        """
        if task_id not in self._active_tasks:
            logger.error(f"Task not found: {task_id}")
            return False

        task = self._active_tasks[task_id]
        task.status = UpdateStatus.FAILED
        task.completed_at = datetime.now()
        task.progress = 100.0
        task.error_messages["general"] = error_message

        # Move from active tasks to history
        execution_time = (task.completed_at - task.created_at).total_seconds() if task.completed_at else 0
        self._save_to_history(task, execution_time)
        del self._active_tasks[task_id]

        # Publish event
        self.event_bus.publish(UpdateHistoryEvent(
            task_id=task_id,
            task_name=task.task_name,
            update_type=task.update_type.value,
            action="failed",
            progress=100.0,
            error_message=error_message
        ))

        logger.error(f"Failed task: {task_id} - {error_message}")
        return True

    def pause_task(self, task_id: str) -> bool:
        """
        Pause an update task

        Args:
            task_id: Task ID

        Returns:
            True if task was paused successfully
        """
        if task_id not in self._active_tasks:
            logger.error(f"Task not found: {task_id}")
            return False

        task = self._active_tasks[task_id]
        task.status = UpdateStatus.PAUSED

        self._save_active_task(task)

        # Publish event
        self.event_bus.publish(UpdateHistoryEvent(
            task_id=task_id,
            task_name=task.task_name,
            update_type=task.update_type.value,
            action="paused",
            progress=task.progress
        ))

        logger.info(f"Paused task: {task_id}")
        return True

    def get_task_status(self, task_id: str) -> Optional[UpdateTask]:
        """
        Get the status of a task

        Args:
            task_id: Task ID

        Returns:
            UpdateTask object or None if not found
        """
        return self._active_tasks.get(task_id)

    def get_all_active_tasks(self) -> List[UpdateTask]:
        """
        Get all active tasks

        Returns:
            List of active UpdateTask objects
        """
        return list(self._active_tasks.values())

    def get_task_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        update_type: Optional[str] = None,
        limit: int = 100
    ) -> List[UpdateHistoryItem]:
        """
        Get task history with optional filters

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            update_type: Filter by update type
            limit: Maximum number of records to return

        Returns:
            List of UpdateHistoryItem objects
        """
        query = """
        SELECT * FROM incremental_update_history
        WHERE 1=1
        """

        params = []

        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)

        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)

        if update_type:
            query += " AND update_type = ?"
            params.append(update_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.db_manager.get_connection(self.db_path) as conn:
            results = conn.execute(query, tuple(params)).fetchall()

        history_items = []
        for row in results:
            history_item = UpdateHistoryItem(
                id=row[0],
                task_name=row[2],
                update_type=row[3],
                symbols_count=len(eval(row[4])),
                success_count=row[7],
                failed_count=row[8],
                skipped_count=row[9],
                new_records_count=row[6],
                execution_time=row[11],
                created_at=datetime.fromisoformat(row[12]),
                status="completed"
            )
            history_items.append(history_item)

        return history_items

    def get_all_update_history(self, limit: int = 500) -> List[UpdateHistoryItem]:
        """
        Get all update history records

        Args:
            limit: Maximum number of records to return (default: 500)

        Returns:
            List of UpdateHistoryItem objects containing all update history
        """
        return self.get_task_history(limit=limit)

    def get_task_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get task statistics for the last N days

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with statistics
        """
        start_date = datetime.now() - timedelta(days=days)
        query = """
        SELECT
            update_type,
            COUNT(*) as task_count,
            SUM(success_count) as success_count,
            SUM(failed_count) as failed_count,
            SUM(skipped_count) as skipped_count,
            SUM(new_records_count) as total_records,
            AVG(execution_time) as avg_execution_time
        FROM incremental_update_history
        WHERE created_at >= ?
        GROUP BY update_type
        """

        with self.db_manager.get_connection(self.db_path) as conn:
            results = conn.execute(query, (start_date,)).fetchall()

        stats = {
            'period_days': days,
            'total_tasks': 0,
            'total_success': 0,
            'total_failed': 0,
            'total_skipped': 0,
            'total_records': 0,
            'avg_execution_time': 0.0,
            'by_type': {}
        }

        for row in results:
            type_stats = {
                'task_count': row[1],
                'success_count': row[2],
                'failed_count': row[3],
                'skipped_count': row[4],
                'total_records': row[5],
                'avg_execution_time': row[6]
            }

            stats['by_type'][row[0]] = type_stats
            stats['total_tasks'] += row[1]
            stats['total_success'] += row[2]
            stats['total_failed'] += row[3]
            stats['total_skipped'] += row[4]
            stats['total_records'] += row[5]
            stats['avg_execution_time'] = row[6]

        return stats

    def get_active_task_by_status(self, status: UpdateStatus) -> List[UpdateTask]:
        """
        Get active tasks by status

        Args:
            status: Status to filter by

        Returns:
            List of UpdateTask objects
        """
        return [task for task in self._active_tasks.values() if task.status == status]

    def clean_old_tasks(self, days: int = 30) -> int:
        """
        Clean old completed tasks from active tasks table

        Args:
            days: Number of days to keep tasks in active table

        Returns:
            Number of tasks cleaned
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        query = """
        DELETE FROM incremental_update_tasks
        WHERE status = 'completed' AND completed_at < ?
        """

        with self.db_manager.get_connection(self.db_path) as conn:
            conn.execute(query, (cutoff_date,))
            # Note: DuckDB doesn't have rowcount attribute like SQLite,
            # we'll just log that cleanup was attempted
            conn.commit()

        logger.info(f"Cleaned old completed tasks older than {cutoff_date}")
        return 0  # Return 0 since we can't easily get affected row count

    def _save_active_task(self, task: UpdateTask):
        """Save task to active tasks table"""
        query = """
        INSERT OR REPLACE INTO incremental_update_tasks (
            task_id, task_name, update_type, symbols, date_range, strategy,
            status, created_at, started_at, completed_at, progress,
            total_symbols, completed_symbols, success_symbols, failed_symbols,
            skipped_symbols, estimated_records, actual_records, error_messages
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        symbols_json = str(task.symbols)
        date_range_json = str(task.date_range)
        error_messages_json = str(task.error_messages)

        with self.db_manager.get_connection(self.db_path) as conn:
            conn.execute(query, (
                task.task_id, task.task_name, task.update_type.value, symbols_json,
                date_range_json, task.strategy, task.status.value,
                task.created_at, task.started_at, task.completed_at,
                task.progress, task.total_symbols, task.completed_symbols,
                task.success_symbols, task.failed_symbols, task.skipped_symbols,
                task.estimated_records, task.actual_records, error_messages_json
            ))

    def _save_to_history(self, task: UpdateTask, execution_time: float):
        """Save task to history table"""
        query = """
        INSERT INTO incremental_update_history (
            task_id, task_name, update_type, symbols, date_range, result,
            new_records_count, success_count, failed_count, skipped_count,
            error_messages, execution_time, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        symbols_json = str(task.symbols)
        date_range_json = str(task.date_range)
        result_json = str({
            'completed_symbols': task.completed_symbols,
            'actual_records': task.actual_records
        })
        error_messages_json = str(task.error_messages)

        with self.db_manager.get_connection(self.db_path) as conn:
            conn.execute(query, (
                task.task_id, task.task_name, task.update_type.value, symbols_json,
                date_range_json, result_json, task.new_records_count,
                task.success_symbols, task.failed_symbols, task.skipped_symbols,
                error_messages_json, execution_time, task.created_at, datetime.now()
            ))


_recorder_instance: Optional[IncrementalUpdateRecorder] = None


def get_incremental_update_recorder() -> IncrementalUpdateRecorder:
    """
    Get the singleton instance of IncrementalUpdateRecorder.
    
    This function provides backward compatibility for code that uses
    the factory pattern. New code should use dependency injection.
    
    Returns:
        IncrementalUpdateRecorder: The singleton recorder instance
    """
    global _recorder_instance
    
    if _recorder_instance is None:
        from ..database.duckdb_manager import get_connection_manager
        from ..events.event_bus import get_event_bus
        
        db_manager = get_connection_manager()
        event_bus = get_event_bus()
        _recorder_instance = IncrementalUpdateRecorder(db_manager, event_bus)
    
    return _recorder_instance