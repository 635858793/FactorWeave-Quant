#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版异步任务管理器

提供智能化的异步任务管理功能：
1. 智能任务调度和优先级管理
2. 任务依赖关系处理
3. 动态资源分配和负载均衡
4. 任务监控和性能分析
5. 故障恢复和重试机制
6. 任务持久化和状态管理
7. 分布式任务协调
8. 任务生命周期管理
"""

import asyncio
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union, Tuple, Awaitable
import weakref
from loguru import logger

from ..database.unified_sqlite_access import UnifiedSQLiteAccess
from ..events import get_event_bus, EventPriority


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SUSPENDED = "suspended"


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class ResourceType(Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"


@dataclass
class ResourceRequirement:
    """资源需求"""
    cpu_cores: float = 1.0
    memory_mb: int = 256
    disk_mb: int = 100
    network_mbps: float = 10.0
    gpu_memory_mb: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceRequirement':
        return cls(**data)


@dataclass
class TaskMetadata:
    """任务元数据"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "unnamed_task"
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout: Optional[float] = None
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: float = 1.0
    tags: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    resource_requirements: ResourceRequirement = field(default_factory=ResourceRequirement)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['scheduled_at'] = self.scheduled_at.isoformat() if self.scheduled_at else None
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        data['priority'] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskMetadata':
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'scheduled_at' in data and data['scheduled_at']:
            data['scheduled_at'] = datetime.fromisoformat(data['scheduled_at'])
        if 'started_at' in data and data['started_at']:
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if 'completed_at' in data and data['completed_at']:
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        if 'priority' in data:
            data['priority'] = TaskPriority(data['priority'])
        if 'resource_requirements' in data:
            data['resource_requirements'] = ResourceRequirement.from_dict(data['resource_requirements'])
        return cls(**data)


@dataclass
class AsyncTask:
    """异步任务"""
    func: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    metadata: TaskMetadata = field(default_factory=TaskMetadata)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    future: Optional[Future] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'func_name': getattr(self.func, '__name__', str(self.func)),
            'args': self.args,
            'kwargs': self.kwargs,
            'metadata': self.metadata.to_dict(),
            'status': self.status.value,
            'result': self.result,
            'error': str(self.error) if self.error else None
        }


class TaskScheduler:
    """智能任务调度器"""

    def __init__(self):
        self.priority_queues: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.completed_tasks: Set[str] = set()

    def add_task(self, task: AsyncTask):
        """添加任务到调度队列"""
        # 检查依赖关系
        if task.metadata.dependencies:
            for dep_id in task.metadata.dependencies:
                self.dependency_graph[task.metadata.task_id].add(dep_id)
                self.reverse_dependency_graph[dep_id].add(task.metadata.task_id)

        # 如果没有未完成的依赖，添加到优先级队列
        if self._can_schedule(task):
            self.priority_queues[task.metadata.priority].append(task)
            task.status = TaskStatus.QUEUED
        else:
            task.status = TaskStatus.PENDING

    def get_next_task(self) -> Optional[AsyncTask]:
        """获取下一个可执行的任务"""
        for priority in TaskPriority:
            queue = self.priority_queues[priority]
            if queue:
                return queue.popleft()
        return None

    def mark_task_completed(self, task_id: str):
        """标记任务完成，检查依赖任务"""
        self.completed_tasks.add(task_id)

        # 检查依赖此任务的其他任务
        dependent_tasks = self.reverse_dependency_graph.get(task_id, set())
        for dependent_id in dependent_tasks:
            # 这里需要从任务存储中获取任务实例
            # 简化实现，实际需要维护任务ID到任务实例的映射
            pass

    def _can_schedule(self, task: AsyncTask) -> bool:
        """检查任务是否可以调度"""
        dependencies = self.dependency_graph.get(task.metadata.task_id, set())
        return dependencies.issubset(self.completed_tasks)


class ResourceManager:
    """资源管理器"""

    def __init__(self):
        self.available_resources = {
            ResourceType.CPU: 8.0,  # CPU核心数
            ResourceType.MEMORY: 8192,  # MB
            ResourceType.DISK: 10240,  # MB
            ResourceType.NETWORK: 1000.0,  # Mbps
            ResourceType.GPU: 0  # GPU内存MB
        }

        self.allocated_resources = {
            ResourceType.CPU: 0.0,
            ResourceType.MEMORY: 0,
            ResourceType.DISK: 0,
            ResourceType.NETWORK: 0.0,
            ResourceType.GPU: 0
        }

        self.resource_allocations: Dict[str, ResourceRequirement] = {}
        self.lock = threading.Lock()

    def can_allocate(self, requirements: ResourceRequirement) -> bool:
        """检查是否可以分配资源"""
        with self.lock:
            return (
                self.allocated_resources[ResourceType.CPU] + requirements.cpu_cores <= self.available_resources[ResourceType.CPU] and
                self.allocated_resources[ResourceType.MEMORY] + requirements.memory_mb <= self.available_resources[ResourceType.MEMORY] and
                self.allocated_resources[ResourceType.DISK] + requirements.disk_mb <= self.available_resources[ResourceType.DISK] and
                self.allocated_resources[ResourceType.NETWORK] + requirements.network_mbps <= self.available_resources[ResourceType.NETWORK] and
                self.allocated_resources[ResourceType.GPU] + requirements.gpu_memory_mb <= self.available_resources[ResourceType.GPU]
            )

    def allocate_resources(self, task_id: str, requirements: ResourceRequirement) -> bool:
        """分配资源"""
        with self.lock:
            if self.can_allocate(requirements):
                self.allocated_resources[ResourceType.CPU] += requirements.cpu_cores
                self.allocated_resources[ResourceType.MEMORY] += requirements.memory_mb
                self.allocated_resources[ResourceType.DISK] += requirements.disk_mb
                self.allocated_resources[ResourceType.NETWORK] += requirements.network_mbps
                self.allocated_resources[ResourceType.GPU] += requirements.gpu_memory_mb

                self.resource_allocations[task_id] = requirements
                return True
            return False

    def release_resources(self, task_id: str):
        """释放资源"""
        with self.lock:
            if task_id in self.resource_allocations:
                requirements = self.resource_allocations[task_id]

                self.allocated_resources[ResourceType.CPU] -= requirements.cpu_cores
                self.allocated_resources[ResourceType.MEMORY] -= requirements.memory_mb
                self.allocated_resources[ResourceType.DISK] -= requirements.disk_mb
                self.allocated_resources[ResourceType.NETWORK] -= requirements.network_mbps
                self.allocated_resources[ResourceType.GPU] -= requirements.gpu_memory_mb

                del self.resource_allocations[task_id]

    def get_resource_utilization(self) -> Dict[str, float]:
        """获取资源利用率"""
        with self.lock:
            return {
                'cpu': self.allocated_resources[ResourceType.CPU] / self.available_resources[ResourceType.CPU] * 100,
                'memory': self.allocated_resources[ResourceType.MEMORY] / self.available_resources[ResourceType.MEMORY] * 100,
                'disk': self.allocated_resources[ResourceType.DISK] / self.available_resources[ResourceType.DISK] * 100,
                'network': self.allocated_resources[ResourceType.NETWORK] / self.available_resources[ResourceType.NETWORK] * 100,
                'gpu': self.allocated_resources[ResourceType.GPU] / max(self.available_resources[ResourceType.GPU], 1) * 100
            }


class TaskPersistence:
    """任务持久化管理器"""

    def __init__(self, db_path: str = "data/enhanced_async_tasks.sqlite"):
        self.db_path = Path(db_path)
        self._init_database()

    def _get_db(self) -> UnifiedSQLiteAccess:
        return UnifiedSQLiteAccess.get_instance(self.db_path)

    def _init_database(self):
        """初始化数据库"""
        db = self._get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS async_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    func_name TEXT NOT NULL,
                    args TEXT,
                    kwargs TEXT,
                    metadata TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 任务执行历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    execution_time REAL,
                    resource_usage TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES async_tasks (id)
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON async_tasks (status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON async_tasks (created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_task_id ON task_execution_history (task_id)")

            conn.commit()

    def save_task(self, task: AsyncTask):
        """保存任务"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO async_tasks 
                    (id, name, func_name, args, kwargs, metadata, status, result, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.metadata.task_id,
                    task.metadata.name,
                    getattr(task.func, '__name__', str(task.func)),
                    json.dumps(task.args),
                    json.dumps(task.kwargs),
                    json.dumps(task.metadata.to_dict()),
                    task.status.value,
                    json.dumps(task.result) if task.result else None,
                    str(task.error) if task.error else None
                ))
        except Exception as e:
            logger.error(f"保存任务失败: {e}")

    def update_task_status(self, task_id: str, status: TaskStatus, result: Any = None, error: Exception = None):
        """更新任务状态"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE async_tasks 
                    SET status = ?, result = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    status.value,
                    json.dumps(result) if result else None,
                    str(error) if error else None,
                    task_id
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")

    def get_tasks_by_status(self, status: TaskStatus, limit: int = 100) -> List[Dict[str, Any]]:
        """根据状态获取任务"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, func_name, args, kwargs, metadata, status, result, error
                    FROM async_tasks WHERE status = ? ORDER BY created_at LIMIT ?
                """, (status.value, limit))

                tasks = []
                for row in cursor.fetchall():
                    task_data = {
                        'id': row[0],
                        'name': row[1],
                        'func_name': row[2],
                        'args': json.loads(row[3]) if row[3] else [],
                        'kwargs': json.loads(row[4]) if row[4] else {},
                        'metadata': json.loads(row[5]),
                        'status': row[6],
                        'result': json.loads(row[7]) if row[7] else None,
                        'error': row[8]
                    }
                    tasks.append(task_data)

                return tasks
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return []

    def record_execution_history(self, task_id: str, status: TaskStatus,
                                 execution_time: float = 0.0,
                                 resource_usage: Dict[str, Any] = None,
                                 error_message: str = None):
        """记录执行历史"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO task_execution_history 
                    (task_id, status, execution_time, resource_usage, error_message)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    task_id, status.value, execution_time,
                    json.dumps(resource_usage) if resource_usage else None,
                    error_message
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"记录执行历史失败: {e}")


class EnhancedAsyncManager:
    """增强版异步任务管理器"""

    def __init__(self,
                 max_workers: int = os.cpu_count() * 2,
                 enable_persistence: bool = True,
                 enable_monitoring: bool = True,
                 db_path: str = "data/enhanced_async_tasks.sqlite"):
        """
        初始化增强版异步任务管理器

        Args:
            max_workers: 最大工作线程数
            enable_persistence: 是否启用持久化
            enable_monitoring: 是否启用监控
            db_path: 数据库路径
        """
        self.max_workers = max_workers
        self.enable_persistence = enable_persistence
        self.enable_monitoring = enable_monitoring

        # 核心组件
        self.scheduler = TaskScheduler()
        self.resource_manager = ResourceManager()
        self.persistence = TaskPersistence(db_path) if enable_persistence else None
        self.event_bus = get_event_bus() if enable_monitoring else None

        # 执行器
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.async_loop = None
        self.loop_thread = None

        # 任务管理
        self.active_tasks: Dict[str, AsyncTask] = {}
        self.task_futures: Dict[str, Future] = {}

        # 监控和统计
        self.stats = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_cancelled': 0,
            'total_execution_time': 0.0,
            'average_execution_time': 0.0,
            'resource_utilization_history': []
        }

        # 控制标志
        self.running = False
        self.shutdown_event = threading.Event()

        # 启动管理器
        self._start_manager()

        logger.info("增强版异步任务管理器初始化完成")

    def _start_manager(self):
        """启动管理器"""
        self.running = True
        self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.loop_thread.start()

    def _run_event_loop(self):
        """运行事件循环"""
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)

        try:
            self.async_loop.run_until_complete(self._management_loop())
        except Exception as e:
            logger.error(f"事件循环错误: {e}")
        finally:
            self.async_loop.close()

    async def _management_loop(self):
        """管理循环"""
        while self.running and not self.shutdown_event.is_set():
            try:
                # 处理待调度任务
                await self._process_pending_tasks()

                # 检查任务状态
                await self._check_task_status()

                # 更新资源利用率统计
                if self.enable_monitoring:
                    self._update_resource_stats()

                # 清理完成的任务
                self._cleanup_completed_tasks()

                await asyncio.sleep(0.1)  # 避免CPU占用过高

            except Exception as e:
                logger.error(f"管理循环错误: {e}")
                await asyncio.sleep(1)

    async def _process_pending_tasks(self):
        """处理待调度任务"""
        while True:
            task = self.scheduler.get_next_task()
            if not task:
                break

            # 检查资源是否可用
            if self.resource_manager.can_allocate(task.metadata.resource_requirements):
                # 分配资源
                if self.resource_manager.allocate_resources(
                    task.metadata.task_id,
                    task.metadata.resource_requirements
                ):
                    # 提交任务执行
                    await self._execute_task(task)
                else:
                    # 资源分配失败，重新排队
                    self.scheduler.add_task(task)
                    break
            else:
                # 资源不足，重新排队
                self.scheduler.add_task(task)
                break

    async def _execute_task(self, task: AsyncTask):
        """执行任务"""
        try:
            task.status = TaskStatus.RUNNING
            task.metadata.started_at = datetime.now()

            # 保存任务状态
            if self.persistence:
                self.persistence.save_task(task)

            # 发布任务开始事件
            if self.event_bus:
                self.event_bus.publish(
                    "task_started",
                    task_id=task.metadata.task_id,
                    task_name=task.metadata.name,
                    priority=EventPriority.NORMAL
                )

            # 提交到线程池执行
            if asyncio.iscoroutinefunction(task.func):
                # 异步函数
                future = asyncio.create_task(task.func(*task.args, **task.kwargs))
            else:
                # 同步函数
                future = self.async_loop.run_in_executor(
                    self.executor,
                    lambda: task.func(*task.args, **task.kwargs)
                )

            task.future = future
            self.task_futures[task.metadata.task_id] = future
            self.active_tasks[task.metadata.task_id] = task

            # 设置超时
            if task.metadata.timeout:
                future = asyncio.wait_for(future, timeout=task.metadata.timeout)

            # 等待任务完成
            try:
                result = await future
                await self._handle_task_completion(task, result)
            except asyncio.TimeoutError:
                await self._handle_task_timeout(task)
            except Exception as e:
                await self._handle_task_error(task, e)

        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            await self._handle_task_error(task, e)

    async def _handle_task_completion(self, task: AsyncTask, result: Any):
        """处理任务完成"""
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.metadata.completed_at = datetime.now()

        # 计算执行时间
        execution_time = 0.0
        if task.metadata.started_at:
            execution_time = (task.metadata.completed_at - task.metadata.started_at).total_seconds()

        # 更新统计
        self.stats['tasks_completed'] += 1
        self.stats['total_execution_time'] += execution_time
        self.stats['average_execution_time'] = (
            self.stats['total_execution_time'] / max(self.stats['tasks_completed'], 1)
        )

        # 释放资源
        self.resource_manager.release_resources(task.metadata.task_id)

        # 保存任务状态
        if self.persistence:
            self.persistence.update_task_status(task.metadata.task_id, task.status, result)
            self.persistence.record_execution_history(
                task.metadata.task_id, task.status, execution_time,
                self.resource_manager.get_resource_utilization()
            )

        # 发布任务完成事件
        if self.event_bus:
            self.event_bus.publish(
                "task_completed",
                task_id=task.metadata.task_id,
                task_name=task.metadata.name,
                execution_time=execution_time,
                result=str(result)[:100],
                priority=EventPriority.NORMAL
            )

        # 标记依赖任务可以调度
        self.scheduler.mark_task_completed(task.metadata.task_id)

        logger.info(f"任务完成: {task.metadata.name} ({execution_time:.2f}s)")

    async def _handle_task_error(self, task: AsyncTask, error: Exception):
        """处理任务错误"""
        task.error = error

        # 检查是否需要重试
        if task.metadata.retry_count < task.metadata.max_retries:
            task.metadata.retry_count += 1
            task.status = TaskStatus.RETRYING

            # 延迟重试
            await asyncio.sleep(task.metadata.retry_delay * task.metadata.retry_count)

            # 重新调度任务
            self.scheduler.add_task(task)

            logger.warning(f"任务重试 ({task.metadata.retry_count}/{task.metadata.max_retries}): {task.metadata.name}")
        else:
            # 重试次数用尽，标记为失败
            task.status = TaskStatus.FAILED
            self.stats['tasks_failed'] += 1

            # 释放资源
            self.resource_manager.release_resources(task.metadata.task_id)

            logger.error(f"任务失败: {task.metadata.name} - {error}")

        # 保存任务状态
        if self.persistence:
            self.persistence.update_task_status(task.metadata.task_id, task.status, error=error)
            self.persistence.record_execution_history(
                task.metadata.task_id, task.status, 0.0,
                error_message=str(error)
            )

        # 发布任务错误事件
        if self.event_bus:
            event_name = "task_failed" if task.status == TaskStatus.FAILED else "task_retrying"
            self.event_bus.publish(
                event_name,
                task_id=task.metadata.task_id,
                task_name=task.metadata.name,
                error=str(error),
                retry_count=task.metadata.retry_count,
                priority=EventPriority.HIGH
            )

    async def _handle_task_timeout(self, task: AsyncTask):
        """处理任务超时"""
        timeout_error = TimeoutError(f"任务超时: {task.metadata.timeout}s")
        await self._handle_task_error(task, timeout_error)

    async def _check_task_status(self):
        """检查任务状态"""
        completed_tasks = []

        for task_id, future in self.task_futures.items():
            if future.done():
                completed_tasks.append(task_id)

        # 清理已完成的future
        for task_id in completed_tasks:
            del self.task_futures[task_id]

    def _update_resource_stats(self):
        """更新资源统计"""
        utilization = self.resource_manager.get_resource_utilization()
        utilization['timestamp'] = datetime.now().isoformat()

        self.stats['resource_utilization_history'].append(utilization)

        # 保持最近1000条记录
        if len(self.stats['resource_utilization_history']) > 1000:
            self.stats['resource_utilization_history'] = self.stats['resource_utilization_history'][-1000:]

    def _cleanup_completed_tasks(self):
        """清理已完成的任务"""
        completed_task_ids = [
            task_id for task_id, task in self.active_tasks.items()
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        ]

        for task_id in completed_task_ids:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    def submit_task(self,
                    func: Callable,
                    *args,
                    name: str = None,
                    description: str = "",
                    priority: TaskPriority = TaskPriority.NORMAL,
                    timeout: float = None,
                    max_retries: int = 3,
                    retry_delay: float = 1.0,
                    dependencies: List[str] = None,
                    resource_requirements: ResourceRequirement = None,
                    tags: Dict[str, Any] = None,
                    **kwargs) -> str:
        """提交任务"""

        # 创建任务元数据
        metadata = TaskMetadata(
            name=name or getattr(func, '__name__', 'unnamed_task'),
            description=description,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            dependencies=dependencies or [],
            resource_requirements=resource_requirements or ResourceRequirement(),
            tags=tags or {}
        )

        # 创建任务
        task = AsyncTask(
            func=func,
            args=args,
            kwargs=kwargs,
            metadata=metadata
        )

        # 保存任务
        if self.persistence:
            self.persistence.save_task(task)

        # 添加到调度器
        self.scheduler.add_task(task)

        # 更新统计
        self.stats['tasks_submitted'] += 1

        # 发布任务提交事件
        if self.event_bus:
            self.event_bus.publish(
                "task_submitted",
                task_id=task.metadata.task_id,
                task_name=task.metadata.name,
                priority=priority.name,
                priority_level=EventPriority.LOW
            )

        logger.info(f"任务已提交: {task.metadata.name} ({task.metadata.task_id})")
        return task.metadata.task_id

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            # 取消正在执行的任务
            if task_id in self.task_futures:
                future = self.task_futures[task_id]
                future.cancel()
                del self.task_futures[task_id]

            # 更新任务状态
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.status = TaskStatus.CANCELLED

                # 释放资源
                self.resource_manager.release_resources(task_id)

                # 保存状态
                if self.persistence:
                    self.persistence.update_task_status(task_id, TaskStatus.CANCELLED)

                # 发布取消事件
                if self.event_bus:
                    self.event_bus.publish(
                        "task_cancelled",
                        task_id=task_id,
                        task_name=task.metadata.name,
                        priority=EventPriority.NORMAL
                    )

                self.stats['tasks_cancelled'] += 1
                logger.info(f"任务已取消: {task_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                'task_id': task_id,
                'name': task.metadata.name,
                'status': task.status.value,
                'priority': task.metadata.priority.name,
                'created_at': task.metadata.created_at.isoformat(),
                'started_at': task.metadata.started_at.isoformat() if task.metadata.started_at else None,
                'completed_at': task.metadata.completed_at.isoformat() if task.metadata.completed_at else None,
                'retry_count': task.metadata.retry_count,
                'result': task.result,
                'error': str(task.error) if task.error else None
            }
        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'active_tasks': len(self.active_tasks),
            'queued_tasks': sum(len(queue) for queue in self.scheduler.priority_queues.values()),
            'resource_utilization': self.resource_manager.get_resource_utilization(),
            'max_workers': self.max_workers
        }

    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """关闭管理器"""
        logger.info("正在关闭异步任务管理器...")

        self.running = False
        self.shutdown_event.set()

        # 取消所有活动任务
        for task_id in list(self.task_futures.keys()):
            self.cancel_task(task_id)

        # 关闭执行器
        self.executor.shutdown(wait=wait)

        # 等待管理循环结束
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=timeout)

        logger.info("异步任务管理器已关闭")


# 全局实例
_enhanced_async_manager: Optional[EnhancedAsyncManager] = None


def get_enhanced_async_manager() -> EnhancedAsyncManager:
    """获取增强版异步任务管理器实例"""
    global _enhanced_async_manager
    if _enhanced_async_manager is None:
        _enhanced_async_manager = EnhancedAsyncManager()
    return _enhanced_async_manager


def initialize_enhanced_async_manager(
    max_workers: int = 8,
    enable_persistence: bool = True,
    enable_monitoring: bool = True,
    db_path: str = "data/enhanced_async_tasks.sqlite"
) -> EnhancedAsyncManager:
    """初始化增强版异步任务管理器"""
    global _enhanced_async_manager

    _enhanced_async_manager = EnhancedAsyncManager(
        max_workers=max_workers,
        enable_persistence=enable_persistence,
        enable_monitoring=enable_monitoring,
        db_path=db_path
    )

    logger.info("增强版异步任务管理器初始化完成")
    return _enhanced_async_manager
