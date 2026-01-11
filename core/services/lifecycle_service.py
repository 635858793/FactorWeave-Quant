"""
统一生命周期服务
架构精简重构 - 整合所有生命周期和任务调度Manager为单一Service

整合的Manager类：
- ServiceBootstrap (core/services/service_bootstrap.py)
- TaskScheduler (core/services/task_scheduler.py)
- StrategyLifecycleManager (core/strategy/lifecycle_manager.py)
- TaskStatusManager (core/importdata/task_status_manager.py)
- AsyncTaskManager (core/async_management/enhanced_async_manager.py)

提供完整的服务生命周期管理、任务调度和执行监控功能，无任何简化或Mock。
"""

import threading
import time
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Set, Type, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from loguru import logger

from .base_service import BaseService
from ..containers.service_container import ServiceContainer
from ..containers.service_registry import ServiceScope
from ..services.task_scheduler import TaskScheduler, ScheduledTask, TaskType, TaskStatus, TaskExecution
from ..strategy.lifecycle_manager import StrategyLifecycleManager, LifecycleStage, StrategyInstance


class ServiceLifecycleState(Enum):
    """服务生命周期状态"""
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DISPOSED = "disposed"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ServiceLifecycleEvent:
    """服务生命周期事件"""
    timestamp: datetime
    service_name: str
    previous_state: ServiceLifecycleState
    new_state: ServiceLifecycleState
    event_type: str
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class ManagedService:
    """托管服务信息"""
    service_type: Type
    service_name: str
    instance: Optional[Any] = None
    state: ServiceLifecycleState = ServiceLifecycleState.UNREGISTERED
    dependencies: List[str] = field(default_factory=list)
    startup_priority: int = 0
    auto_restart: bool = True
    max_restart_attempts: int = 3
    restart_attempts: int = 0
    last_restart: Optional[datetime] = None
    lifecycle_events: List[ServiceLifecycleEvent] = field(default_factory=list)
    health_check_interval: int = 30  # 秒
    last_health_check: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTask:
    """执行任务"""
    task_id: str
    name: str
    priority: TaskPriority
    task_function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


class LifecycleService(BaseService):
    """
    统一生命周期服务

    整合所有生命周期和任务管理Manager的功能：
    1. 服务生命周期管理（注册、初始化、启动、停止、重启）
    2. 任务调度和执行（定时任务、一次性任务、重复任务）
    3. 依赖关系管理（服务依赖、任务依赖）
    4. 健康检查和自动恢复
    5. 策略生命周期管理
    6. 异步任务管理
    7. 执行监控和日志记录
    """

    def __init__(self, event_bus=None):
        """初始化生命周期服务"""
        super().__init__(event_bus)

        # 核心组件
        self._task_scheduler: Optional[TaskScheduler] = None
        self._strategy_lifecycle_manager: Optional[StrategyLifecycleManager] = None

        # 服务管理
        self._managed_services: Dict[str, ManagedService] = {}
        self._service_container: Optional[ServiceContainer] = None
        self._startup_order: List[str] = []

        # 任务管理
        self._execution_tasks: Dict[str, ExecutionTask] = {}
        self._task_queue: List[str] = []  # 任务ID队列
        self._running_tasks: Dict[str, Future] = {}

        # 线程池和执行器
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers: int = 10

        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._health_check_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        # 状态管理
        self._lifecycle_active = False
        self._task_execution_active = False

        # 锁
        self._services_lock = threading.RLock()
        self._tasks_lock = threading.RLock()
        self._execution_lock = threading.RLock()

        # 配置
        self._config = {
            "service_health_check_interval": 30,  # 秒
            "task_monitor_interval": 5,  # 秒
            "auto_restart_services": True,
            "max_concurrent_tasks": 50,
            "task_timeout_default": 300  # 秒
        }

        logger.info("LifecycleService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """初始化生命周期服务"""
        try:
            # 从服务容器获取任务调度器
            from ..containers.service_container import get_service_container
            self._task_scheduler = get_service_container().resolve(TaskScheduler)
            logger.info("TaskScheduler resolved from service container")

            # 初始化策略生命周期管理器
            self._strategy_lifecycle_manager = StrategyLifecycleManager()
            logger.info("StrategyLifecycleManager initialized")

            # 初始化线程池
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="LifecycleService"
            )
            logger.info(f"ThreadPoolExecutor initialized with {self._max_workers} workers")

            # 启动监控线程
            self._start_monitoring()

            logger.info("LifecycleService initialized successfully with full functionality")

        except Exception as e:
            logger.error(f"Failed to initialize LifecycleService: {e}")
            raise

    def _do_dispose(self) -> None:
        """清理生命周期服务资源"""
        try:
            # 停止所有监控
            self._shutdown_event.set()

            # 停止所有托管服务
            self._stop_all_services()

            # 等待监控线程结束
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
                logger.info("Monitor thread stopped")

            if self._health_check_thread and self._health_check_thread.is_alive():
                self._health_check_thread.join(timeout=5)
                logger.info("Health check thread stopped")

            # 停止任务执行线程
            if hasattr(self, '_task_execution_thread') and self._task_execution_thread and self._task_execution_thread.is_alive():
                self._task_execution_active = False
                self._task_execution_thread.join(timeout=5)
                logger.info("Task execution thread stopped")

            # 关闭线程池
            if self._executor:
                self._executor.shutdown(wait=True)
                logger.info("ThreadPoolExecutor shutdown")

            # 清理任务调度器
            if self._task_scheduler:
                self._task_scheduler = None

            # 清理策略生命周期管理器
            if self._strategy_lifecycle_manager:
                self._strategy_lifecycle_manager = None

            logger.info("LifecycleService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing LifecycleService: {e}")

    def _start_monitoring(self) -> None:
        """启动监控线程"""
        if not self._lifecycle_active:
            self._lifecycle_active = True

            # 启动服务监控线程
            self._monitor_thread = threading.Thread(
                target=self._service_monitor_loop,
                name="ServiceMonitor",
                daemon=True
            )
            self._monitor_thread.start()

            # 启动健康检查线程
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop,
                name="HealthChecker",
                daemon=True
            )
            self._health_check_thread.start()

            # 启动任务执行监控
            self._task_execution_active = True

            # 启动任务执行线程
            self._task_execution_thread = threading.Thread(
                target=self._task_execution_loop,
                name="TaskExecutor",
                daemon=True
            )
            self._task_execution_thread.start()

            logger.info("Lifecycle monitoring started")

    def _service_monitor_loop(self) -> None:
        """服务监控主循环"""
        while not self._shutdown_event.is_set():
            try:
                # 检查任务队列
                self._process_task_queue()

                # 检查运行中的任务
                self._check_running_tasks()

                # 检查服务状态
                self._check_service_states()

            except Exception as e:
                logger.error(f"Error in service monitor loop: {e}")

            self._shutdown_event.wait(self._config["task_monitor_interval"])

    def _health_check_loop(self) -> None:
        """健康检查主循环"""
        while not self._shutdown_event.is_set():
            try:
                self._perform_health_checks()
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

            self._shutdown_event.wait(self._config["service_health_check_interval"])

    def _task_execution_loop(self) -> None:
        """任务执行主循环"""
        while not self._shutdown_event.is_set() and self._task_execution_active:
            try:
                self._process_pending_tasks()
            except Exception as e:
                logger.error(f"Error in task execution loop: {e}")

            # 短暂等待避免过度占用CPU
            self._shutdown_event.wait(0.1)

    def _process_pending_tasks(self) -> None:
        """处理待执行的任务"""
        with self._tasks_lock:
            # 获取可执行的任务
            executable_tasks = []
            for task_id in list(self._task_queue):
                task = self._execution_tasks.get(task_id)
                if task and task.status == TaskStatus.PENDING:
                    # 检查依赖是否满足
                    if self._are_dependencies_satisfied(task):
                        executable_tasks.append(task_id)
                        self._task_queue.remove(task_id)
                        break  # 一次只执行一个任务

        # 异步执行任务
        for task_id in executable_tasks:
            self._execute_task_async(task_id)

    def _are_dependencies_satisfied(self, task: ExecutionTask) -> bool:
        """检查任务依赖是否满足"""
        for dep_id in task.dependencies:
            dep_task = self._execution_tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True

    def _execute_task_async(self, task_id: str) -> None:
        """异步执行任务"""
        task = self._execution_tasks.get(task_id)
        if not task:
            return

        # 更新任务状态
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        # 提交到线程池执行
        future = self._executor.submit(self._execute_task_by_id, task_id)

        # 添加完成回调
        def task_completed(fut):
            # 重新获取任务对象以避免闭包问题
            current_task = self._execution_tasks.get(task_id)
            if not current_task:
                return

            try:
                result = fut.result()
                current_task.result = result
                current_task.status = TaskStatus.COMPLETED
                current_task.completed_at = datetime.now()
                logger.info(f"Task {current_task.name} ({task_id}) completed successfully")
            except Exception as e:
                current_task.error = str(e)
                current_task.status = TaskStatus.FAILED
                current_task.completed_at = datetime.now()
                logger.error(f"Task {current_task.name} ({task_id}) failed: {e}")

                # 如果还有重试次数，重新排队
                if current_task.retry_count < current_task.max_retries:
                    current_task.retry_count += 1
                    current_task.status = TaskStatus.PENDING
                    current_task.started_at = None
                    current_task.completed_at = None
                    current_task.error = None
                    with self._tasks_lock:
                        self._task_queue.append(task_id)
                    logger.info(f"Task {current_task.name} ({task_id}) queued for retry ({current_task.retry_count}/{current_task.max_retries})")

        future.add_done_callback(task_completed)

    def _execute_task_by_id(self, task_id: str) -> Any:
        """执行单个任务 (通过ID)"""
        task = self._execution_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        try:
            logger.debug(f"Executing task {task.name} with function {task.task_function} and args {task.args}")
            # 执行任务函数
            result = task.task_function(*task.args, **task.kwargs)
            logger.debug(f"Task {task.name} completed with result: {result}")
            return result
        except Exception as e:
            logger.error(f"Task execution failed for {task.name}: {e}")
            logger.exception(f"Full traceback for task {task.name}:")
            raise

    def _process_task_queue(self) -> None:
        """处理任务队列"""
        with self._tasks_lock:
            while self._task_queue and len(self._running_tasks) < self._config["max_concurrent_tasks"]:
                task_id = self._task_queue.pop(0)
                task = self._execution_tasks.get(task_id)

                if task and task.status == TaskStatus.PENDING:
                    self._execute_task(task)

    def _execute_task(self, task: ExecutionTask) -> None:
        """执行任务"""
        try:
            # 检查依赖
            if not self._check_task_dependencies(task):
                logger.debug(f"Task {task.task_id} dependencies not ready, rescheduling")
                with self._tasks_lock:
                    self._task_queue.append(task.task_id)
                return

            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            # 提交到线程池执行
            future = self._executor.submit(self._run_task, task)

            with self._execution_lock:
                self._running_tasks[task.task_id] = future

            logger.info(f"Task {task.name} ({task.task_id}) started execution")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Failed to execute task {task.task_id}: {e}")

    def _run_task(self, task: ExecutionTask) -> Any:
        """运行任务的实际执行逻辑"""
        try:
            # 执行任务函数
            if task.timeout:
                # 带超时的执行
                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Task {task.task_id} timed out after {task.timeout} seconds")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(task.timeout))

                try:
                    result = task.task_function(*task.args, **task.kwargs)
                finally:
                    signal.alarm(0)
            else:
                result = task.task_function(*task.args, **task.kwargs)

            # 更新任务状态
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()

            logger.info(f"Task {task.name} ({task.task_id}) completed successfully")
            return result

        except Exception as e:
            # 处理失败
            task.retry_count += 1

            if task.retry_count <= task.max_retries:
                task.status = TaskStatus.PENDING
                task.error = f"Retry {task.retry_count}/{task.max_retries}: {str(e)}"

                # 重新加入队列
                with self._tasks_lock:
                    self._task_queue.append(task.task_id)

                logger.warning(f"Task {task.task_id} failed, retry {task.retry_count}/{task.max_retries}: {e}")
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()

                logger.error(f"Task {task.task_id} failed after {task.max_retries} retries: {e}")

            return None
        finally:
            # 清理运行中的任务记录
            with self._execution_lock:
                self._running_tasks.pop(task.task_id, None)

    def _check_task_dependencies(self, task: ExecutionTask) -> bool:
        """检查任务依赖是否满足"""
        for dep_task_id in task.dependencies:
            dep_task = self._execution_tasks.get(dep_task_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True

    def _check_running_tasks(self) -> None:
        """检查运行中的任务状态"""
        with self._execution_lock:
            completed_tasks = []

            for task_id, future in self._running_tasks.items():
                if future.done():
                    completed_tasks.append(task_id)

                    task = self._execution_tasks.get(task_id)
                    if task:
                        if future.exception():
                            task.status = TaskStatus.FAILED
                            task.error = str(future.exception())
                        else:
                            if task.status != TaskStatus.COMPLETED:  # 可能已在_run_task中设置
                                task.status = TaskStatus.COMPLETED
                                task.result = future.result()

                        if not task.completed_at:
                            task.completed_at = datetime.now()

            # 清理已完成的任务
            for task_id in completed_tasks:
                self._running_tasks.pop(task_id, None)

    def _check_service_states(self) -> None:
        """检查服务状态"""
        with self._services_lock:
            for service_name, managed_service in self._managed_services.items():
                try:
                    if managed_service.state == ServiceLifecycleState.RUNNING:
                        # 检查服务是否仍然健康
                        if managed_service.instance and hasattr(managed_service.instance, 'initialized'):
                            if not managed_service.instance.initialized:
                                self._handle_service_failure(service_name, "Service lost initialization state")

                except Exception as e:
                    logger.error(f"Error checking service {service_name}: {e}")

    def _perform_health_checks(self) -> None:
        """执行健康检查"""
        with self._services_lock:
            for service_name, managed_service in self._managed_services.items():
                try:
                    if managed_service.state == ServiceLifecycleState.RUNNING:
                        if managed_service.instance and hasattr(managed_service.instance, 'perform_health_check'):
                            health_result = managed_service.instance.perform_health_check()
                            managed_service.last_health_check = datetime.now()

                            if health_result.get('status') != 'healthy':
                                self._handle_service_failure(service_name, f"Health check failed: {health_result}")

                except Exception as e:
                    logger.error(f"Health check failed for service {service_name}: {e}")
                    self._handle_service_failure(service_name, f"Health check exception: {e}")

    def _handle_service_failure(self, service_name: str, reason: str) -> None:
        """处理服务失败"""
        managed_service = self._managed_services.get(service_name)
        if not managed_service:
            return

        logger.warning(f"Service {service_name} failure detected: {reason}")

        # 记录失败事件
        event = ServiceLifecycleEvent(
            timestamp=datetime.now(),
            service_name=service_name,
            previous_state=managed_service.state,
            new_state=ServiceLifecycleState.ERROR,
            event_type="failure_detected",
            details={"reason": reason},
            success=False,
            error_message=reason
        )
        managed_service.lifecycle_events.append(event)
        managed_service.state = ServiceLifecycleState.ERROR

        # 自动重启（如果启用）
        if (managed_service.auto_restart and
                managed_service.restart_attempts < managed_service.max_restart_attempts):

            self._restart_service(service_name)

    def _restart_service(self, service_name: str) -> bool:
        """重启服务"""
        managed_service = self._managed_services.get(service_name)
        if not managed_service:
            return False

        try:
            managed_service.restart_attempts += 1
            managed_service.last_restart = datetime.now()

            logger.info(f"Attempting to restart service {service_name} (attempt {managed_service.restart_attempts})")

            # 停止服务
            self._stop_service(service_name)

            # 等待一段时间
            time.sleep(2)

            # 重新启动
            success = self._start_service(service_name)

            if success:
                managed_service.restart_attempts = 0  # 重置重试计数
                logger.info(f"Service {service_name} restarted successfully")

            return success

        except Exception as e:
            logger.error(f"Failed to restart service {service_name}: {e}")
            return False

    # 公共接口方法

    def register_service(self,
                         service_type: Type,
                         dependencies: List[str] = None,
                         startup_priority: int = 0,
                         auto_restart: bool = True,
                         max_restart_attempts: int = 3,
                         health_check_interval: int = 30,
                         **metadata) -> bool:
        """
        注册托管服务

        Args:
            service_type: 服务类型
            dependencies: 依赖的服务名称列表
            startup_priority: 启动优先级（数字越小越早启动）
            auto_restart: 是否自动重启
            max_restart_attempts: 最大重启尝试次数
            health_check_interval: 健康检查间隔（秒）
            **metadata: 额外的元数据
        """
        service_name = service_type.__name__

        with self._services_lock:
            if service_name in self._managed_services:
                logger.warning(f"Service {service_name} already registered")
                return False

            managed_service = ManagedService(
                service_type=service_type,
                service_name=service_name,
                dependencies=dependencies or [],
                startup_priority=startup_priority,
                auto_restart=auto_restart,
                max_restart_attempts=max_restart_attempts,
                health_check_interval=health_check_interval,
                metadata=metadata
            )

            self._managed_services[service_name] = managed_service

            # 记录注册事件
            event = ServiceLifecycleEvent(
                timestamp=datetime.now(),
                service_name=service_name,
                previous_state=ServiceLifecycleState.UNREGISTERED,
                new_state=ServiceLifecycleState.REGISTERED,
                event_type="service_registered",
                details={"dependencies": dependencies, "priority": startup_priority}
            )
            managed_service.lifecycle_events.append(event)
            managed_service.state = ServiceLifecycleState.REGISTERED

            logger.info(f"Service {service_name} registered with priority {startup_priority}")
            return True

    def start_service(self, service_name: str) -> bool:
        """启动指定服务"""
        return self._start_service(service_name)

    def _start_service(self, service_name: str) -> bool:
        """内部启动服务方法"""
        managed_service = self._managed_services.get(service_name)
        if not managed_service:
            logger.error(f"Service {service_name} not registered")
            return False

        if managed_service.state == ServiceLifecycleState.RUNNING:
            logger.info(f"Service {service_name} already running")
            return True

        try:
            # 检查依赖
            for dep_name in managed_service.dependencies:
                dep_service = self._managed_services.get(dep_name)
                if not dep_service or dep_service.state != ServiceLifecycleState.RUNNING:
                    logger.error(f"Dependency {dep_name} not running for service {service_name}")
                    return False

            # 更新状态
            managed_service.state = ServiceLifecycleState.STARTING

            # 创建服务实例（如果需要）
            if not managed_service.instance:
                managed_service.instance = managed_service.service_type()

            # 初始化服务
            if hasattr(managed_service.instance, 'initialize'):
                managed_service.instance.initialize()

            # 更新状态
            managed_service.state = ServiceLifecycleState.RUNNING

            # 记录启动事件
            event = ServiceLifecycleEvent(
                timestamp=datetime.now(),
                service_name=service_name,
                previous_state=ServiceLifecycleState.STARTING,
                new_state=ServiceLifecycleState.RUNNING,
                event_type="service_started"
            )
            managed_service.lifecycle_events.append(event)

            logger.info(f"Service {service_name} started successfully")
            return True

        except Exception as e:
            managed_service.state = ServiceLifecycleState.ERROR

            # 记录错误事件
            event = ServiceLifecycleEvent(
                timestamp=datetime.now(),
                service_name=service_name,
                previous_state=ServiceLifecycleState.STARTING,
                new_state=ServiceLifecycleState.ERROR,
                event_type="service_start_failed",
                success=False,
                error_message=str(e)
            )
            managed_service.lifecycle_events.append(event)

            logger.error(f"Failed to start service {service_name}: {e}")
            return False

    def stop_service(self, service_name: str) -> bool:
        """停止指定服务"""
        return self._stop_service(service_name)

    def _stop_service(self, service_name: str) -> bool:
        """内部停止服务方法"""
        managed_service = self._managed_services.get(service_name)
        if not managed_service:
            logger.error(f"Service {service_name} not registered")
            return False

        if managed_service.state == ServiceLifecycleState.STOPPED:
            logger.info(f"Service {service_name} already stopped")
            return True

        try:
            managed_service.state = ServiceLifecycleState.STOPPING

            # 停止服务
            if managed_service.instance and hasattr(managed_service.instance, 'dispose'):
                managed_service.instance.dispose()

            managed_service.state = ServiceLifecycleState.STOPPED

            # 记录停止事件
            event = ServiceLifecycleEvent(
                timestamp=datetime.now(),
                service_name=service_name,
                previous_state=ServiceLifecycleState.STOPPING,
                new_state=ServiceLifecycleState.STOPPED,
                event_type="service_stopped"
            )
            managed_service.lifecycle_events.append(event)

            logger.info(f"Service {service_name} stopped successfully")
            return True

        except Exception as e:
            managed_service.state = ServiceLifecycleState.ERROR

            # 记录错误事件
            event = ServiceLifecycleEvent(
                timestamp=datetime.now(),
                service_name=service_name,
                previous_state=ServiceLifecycleState.STOPPING,
                new_state=ServiceLifecycleState.ERROR,
                event_type="service_stop_failed",
                success=False,
                error_message=str(e)
            )
            managed_service.lifecycle_events.append(event)

            logger.error(f"Failed to stop service {service_name}: {e}")
            return False

    def start_all_services(self) -> Dict[str, bool]:
        """按优先级启动所有注册的服务"""
        results = {}

        # 按优先级排序
        sorted_services = sorted(
            self._managed_services.items(),
            key=lambda x: x[1].startup_priority
        )

        for service_name, _ in sorted_services:
            results[service_name] = self.start_service(service_name)

        return results

    def _stop_all_services(self) -> None:
        """停止所有服务"""
        # 按优先级反序停止
        sorted_services = sorted(
            self._managed_services.items(),
            key=lambda x: x[1].startup_priority,
            reverse=True
        )

        for service_name, _ in sorted_services:
            self.stop_service(service_name)

    def submit_task(self,
                    name: str,
                    task_function: Callable,
                    args: tuple = (),
                    kwargs: Dict[str, Any] = None,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    max_retries: int = 3,
                    timeout: Optional[float] = None,
                    dependencies: List[str] = None) -> str:
        """
        提交执行任务

        Args:
            name: 任务名称
            task_function: 任务函数
            args: 位置参数
            kwargs: 关键字参数
            priority: 任务优先级
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            dependencies: 依赖的任务ID列表

        Returns:
            任务ID
        """
        task_id = f"task_{int(datetime.now().timestamp() * 1000000)}"

        task = ExecutionTask(
            task_id=task_id,
            name=name,
            priority=priority,
            task_function=task_function,
            args=args,
            kwargs=kwargs or {},
            max_retries=max_retries,
            timeout=timeout,
            dependencies=dependencies or []
        )

        with self._tasks_lock:
            self._execution_tasks[task_id] = task
            self._task_queue.append(task_id)

            # 按优先级排序队列
            self._task_queue.sort(key=lambda tid: self._execution_tasks[tid].priority.value, reverse=True)

        logger.info(f"Task {name} ({task_id}) submitted with priority {priority.name}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        task = self._execution_tasks.get(task_id)
        return task.status if task else None

    def get_task_result(self, task_id: str) -> Any:
        """获取任务结果"""
        task = self._execution_tasks.get(task_id)
        return task.result if task else None

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._tasks_lock:
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)
                task = self._execution_tasks.get(task_id)
                if task:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.now()
                return True

        with self._execution_lock:
            if task_id in self._running_tasks:
                future = self._running_tasks[task_id]
                if future.cancel():
                    task = self._execution_tasks.get(task_id)
                    if task:
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = datetime.now()
                    return True

        return False

    def get_service_status(self, service_name: str) -> Optional[ServiceLifecycleState]:
        """获取服务状态"""
        managed_service = self._managed_services.get(service_name)
        return managed_service.state if managed_service else None

    def get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """获取服务信息"""
        managed_service = self._managed_services.get(service_name)
        if not managed_service:
            return None

        return {
            "service_name": managed_service.service_name,
            "service_type": managed_service.service_type.__name__,
            "state": managed_service.state.value,
            "dependencies": managed_service.dependencies,
            "startup_priority": managed_service.startup_priority,
            "auto_restart": managed_service.auto_restart,
            "restart_attempts": managed_service.restart_attempts,
            "last_restart": managed_service.last_restart.isoformat() if managed_service.last_restart else None,
            "last_health_check": managed_service.last_health_check.isoformat() if managed_service.last_health_check else None,
            "event_count": len(managed_service.lifecycle_events),
            "metadata": managed_service.metadata
        }

    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务状态"""
        return {
            service_name: self.get_service_info(service_name)
            for service_name in self._managed_services.keys()
        }

    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """获取运行中的任务"""
        running_tasks = []

        with self._execution_lock:
            for task_id in self._running_tasks.keys():
                task = self._execution_tasks.get(task_id)
                if task:
                    running_tasks.append({
                        "task_id": task.task_id,
                        "name": task.name,
                        "priority": task.priority.name,
                        "status": task.status.value,
                        "started_at": task.started_at.isoformat() if task.started_at else None,
                        "retry_count": task.retry_count,
                        "dependencies": task.dependencies
                    })

        return running_tasks

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取待执行的任务"""
        pending_tasks = []

        with self._tasks_lock:
            for task_id in self._task_queue:
                task = self._execution_tasks.get(task_id)
                if task:
                    pending_tasks.append({
                        "task_id": task.task_id,
                        "name": task.name,
                        "priority": task.priority.name,
                        "created_at": task.created_at.isoformat(),
                        "dependencies": task.dependencies
                    })

        return pending_tasks

    def generate_lifecycle_report(self) -> Dict[str, Any]:
        """生成生命周期报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "services": {
                "total": len(self._managed_services),
                "running": len([s for s in self._managed_services.values() if s.state == ServiceLifecycleState.RUNNING]),
                "stopped": len([s for s in self._managed_services.values() if s.state == ServiceLifecycleState.STOPPED]),
                "error": len([s for s in self._managed_services.values() if s.state == ServiceLifecycleState.ERROR])
            },
            "tasks": {
                "total": len(self._execution_tasks),
                "running": len(self._running_tasks),
                "pending": len(self._task_queue),
                "completed": len([t for t in self._execution_tasks.values() if t.status == TaskStatus.COMPLETED]),
                "failed": len([t for t in self._execution_tasks.values() if t.status == TaskStatus.FAILED])
            },
            "system": {
                "lifecycle_active": self._lifecycle_active,
                "task_execution_active": self._task_execution_active,
                "thread_pool_workers": self._max_workers
            }
        }

        return report

    def _do_health_check(self) -> Optional[Dict[str, Any]]:
        """自定义健康检查"""
        try:
            health_data = {
                "lifecycle_active": self._lifecycle_active,
                "task_execution_active": self._task_execution_active,
                "managed_services_count": len(self._managed_services),
                "running_services": len([s for s in self._managed_services.values() if s.state == ServiceLifecycleState.RUNNING]),
                "running_tasks": len(self._running_tasks),
                "pending_tasks": len(self._task_queue),
                "thread_pool_active": self._executor is not None and not self._executor._shutdown
            }

            return health_data

        except Exception as e:
            return {"health_check_error": str(e)}


# 便捷函数
def get_lifecycle_service() -> Optional[LifecycleService]:
    """获取生命周期服务实例"""
    try:
        from ..containers.unified_service_container import get_unified_container
        container = get_unified_container()
        return container.resolve(LifecycleService)
    except Exception:
        return None
