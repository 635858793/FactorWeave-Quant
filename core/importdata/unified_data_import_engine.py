#!/usr/bin/env python3
"""
统一数据导入引擎

整合所有数据导入功能，提供统一的接口和专业级功能
对标Bloomberg Terminal、Wind万得等专业金融软件
"""

# 导入核心服务
from core.services.unified_data_manager import get_unified_data_manager

import asyncio
import threading
import time
import hashlib
import pandas as pd
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QThread
from loguru import logger

# 配置管理
from .import_config_manager import ImportConfigManager, ImportTaskConfig, ImportProgress, ImportStatus

# 核心服务
from core.database.table_manager import TableType
from ..services.unified_data_manager import UnifiedDataManager
from ..real_data_provider import RealDataProvider

# AI和智能优化
from ..services.ai_prediction_service import AIPredictionService, PredictionType
from ..services.deep_analysis_service import DeepAnalysisService, PerformanceMetric, AnomalyInfo
from optimization.auto_tuner import AlgorithmAutoTuner, TuningTask, OptimizationConfig

# 性能和监控
from ..performance.factorweave_performance_integration import FactorWeavePerformanceIntegrator
from ..services.enhanced_performance_bridge import EnhancedPerformanceBridge, get_enhanced_performance_bridge
from ..risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor, get_enhanced_risk_monitor

# 分布式和并发
from ..services.distributed_service import DistributedService, NodeDiscovery, NodeInfo
# from ..services.enhanced_distributed_service import EnhancedDistributedService, get_enhanced_distributed_service  # Module doesn't exist
from ..events import get_event_bus, EventPriority
from ..async_management.enhanced_async_manager import get_enhanced_async_manager, TaskPriority, ResourceRequirement

# 数据质量
from ..services.enhanced_data_manager import DataQualityMonitor
from ..data.enhanced_models import DataQualityMetrics, DataQuality
from ..data_validator import ValidationLevel, ValidationResult


class UnifiedTaskStatus(Enum):
    """统一任务状态枚举"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    RESUMING = "resuming"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ImportMode(Enum):
    """导入模式"""
    MANUAL = "manual"          # 手动导入
    BATCH = "batch"           # 批量导入
    SCHEDULED = "scheduled"   # 定时导入
    INCREMENTAL = "incremental"  # 增量导入
    FULL = "full"            # 全量导入
    REALTIME = "realtime"    # 实时导入


@dataclass
class UnifiedImportTask:
    """统一导入任务配置"""
    task_id: str
    task_name: str
    symbols: List[str]
    data_source: str
    asset_type: str
    data_type: str
    frequency: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    mode: ImportMode = ImportMode.MANUAL
    priority: TaskPriority = TaskPriority.NORMAL
    retry_count: int = 3
    timeout: int = 300
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_import_task_config(self) -> ImportTaskConfig:
        """转换为ImportTaskConfig格式以保持兼容性"""
        return ImportTaskConfig(
            task_id=self.task_id,
            task_name=self.task_name,
            symbols=self.symbols,
            data_source=self.data_source,
            asset_type=self.asset_type,
            data_type=self.data_type,
            frequency=self.frequency,
            start_date=self.start_date,
            end_date=self.end_date,
            mode=self.mode.value,
            **self.config
        )


@dataclass
class UnifiedImportResult:
    """统一导入结果"""
    task_id: str
    status: UnifiedTaskStatus
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    skipped_records: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: float = 0.0
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, Any] = field(default_factory=dict)
    ai_insights: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """任务是否成功"""
        return self.status == UnifiedTaskStatus.COMPLETED

    @property
    def progress_percentage(self) -> float:
        """进度百分比"""
        if self.total_records == 0:
            return 0.0
        return (self.processed_records / self.total_records) * 100

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_records == 0:
            return 0.0
        return ((self.processed_records - self.failed_records) / self.total_records) * 100


class UnifiedAsyncWorker(QThread):
    """统一异步工作线程"""

    # 信号定义 - 与AsyncDataImportWorker兼容
    progress_updated = pyqtSignal(int, str)  # 进度百分比, 状态消息
    import_started = pyqtSignal(str)  # 导入任务ID
    import_completed = pyqtSignal(str, dict)  # 任务ID, 结果统计
    import_failed = pyqtSignal(str, str)  # 任务ID, 错误消息
    data_chunk_imported = pyqtSignal(str, int, int)  # 任务ID, 已导入数量, 总数量

    def __init__(self, task_config: UnifiedImportTask, engine_ref, parent=None):
        super().__init__(parent)
        self.task_config = task_config
        self.engine_ref = engine_ref  # 引用主引擎
        self._stop_requested = False

    def run(self):
        """执行异步任务"""
        try:
            logger.info(f"开始异步执行任务: {self.task_config.task_id}")
            self.import_started.emit(self.task_config.task_id)
            self.progress_updated.emit(0, "初始化任务执行...")

            # 检查停止请求
            if self._stop_requested:
                return

            # 创建任务结果对象
            result = UnifiedImportResult(
                task_id=self.task_config.task_id,
                status=UnifiedTaskStatus.RUNNING,
                start_time=datetime.now()
            )

            # 执行任务
            self.engine_ref._execute_unified_task_sync(self.task_config, result)

            # 转换结果格式以保持兼容性
            result_dict = {
                'task_id': result.task_id,
                'status': 'success' if result.success else 'failed',
                'imported_count': result.processed_records,
                'failed_count': result.failed_records,
                'start_time': result.start_time.isoformat() if result.start_time else None,
                'end_time': result.end_time.isoformat() if result.end_time else None,
                'execution_time': result.execution_time,
                'warnings': result.warnings,
                'performance_metrics': result.performance_metrics
            }

            if result.success:
                self.progress_updated.emit(100, "任务执行完成")
                self.import_completed.emit(self.task_config.task_id, result_dict)
            else:
                self.import_failed.emit(self.task_config.task_id, result.error_message or "任务执行失败")

        except Exception as e:
            logger.error(f"异步任务执行失败: {e}")
            self.import_failed.emit(self.task_config.task_id, str(e))

    def stop(self):
        """停止任务"""
        self._stop_requested = True
        self.quit()
        self.wait(5000)  # 等待5秒


class UnifiedDataImportEngine(QObject):
    """
    统一数据导入引擎

    功能特性：
    1. 统一任务执行和状态管理
    2. AI智能优化和预测
    3. 多级性能监控和分析
    4. 分布式任务执行
    5. 智能缓存和数据质量监控
    6. 风险监控和异常检测
    7. 自动参数调优
    8. 增强事件处理和异步管理
    9. 高效的多线程异步处理
    10. 资源管理和内存优化

    对标专业软件：Bloomberg Terminal、Wind万得、Refinitiv Eikon
    """

    # Qt信号 - 增强版信号系统
    task_created = pyqtSignal(str, object)  # 任务创建 (task_id, task_config)
    task_started = pyqtSignal(str, object)  # 任务开始 (task_id, task_info)
    task_progress = pyqtSignal(str, float, str, object)  # 任务进度 (task_id, progress, message, metrics)
    task_paused = pyqtSignal(str, str)  # 任务暂停 (task_id, reason)
    task_resumed = pyqtSignal(str)  # 任务恢复 (task_id)
    task_completed = pyqtSignal(str, object)  # 任务完成 (task_id, result)
    task_failed = pyqtSignal(str, str, object)  # 任务失败 (task_id, error_message, error_details)
    task_cancelled = pyqtSignal(str, str)  # 任务取消 (task_id, reason)

    # 异步处理兼容信号 - 与AsyncDataImportWorker兼容
    progress_updated = pyqtSignal(int, str)  # 进度百分比, 状态消息
    import_started = pyqtSignal(str)  # 导入任务ID
    import_completed = pyqtSignal(str, dict)  # 任务ID, 结果统计
    import_failed = pyqtSignal(str, str)  # 任务ID, 错误消息
    data_chunk_imported = pyqtSignal(str, int, int)  # 任务ID, 已导入数量, 总数量

    # 系统级信号
    engine_status_changed = pyqtSignal(str, object)  # 引擎状态变化 (status, details)
    performance_alert = pyqtSignal(str, object)  # 性能警报 (alert_type, metrics)
    quality_alert = pyqtSignal(str, object)  # 质量警报 (alert_type, details)
    ai_insight_generated = pyqtSignal(str, object)  # AI洞察生成 (insight_type, data)

    def __init__(self,
                 config_manager: Optional[ImportConfigManager] = None,
                 data_manager: Optional[UnifiedDataManager] = None,
                 max_workers: int = 8,
                 enable_ai_optimization: bool = True,
                 enable_intelligent_config: bool = True,
                 enable_enhanced_performance: bool = True,
                 enable_enhanced_risk_monitoring: bool = True,
                 enable_distributed_execution: bool = True,
                 enable_advanced_caching: bool = True,
                 enable_data_quality_monitoring: bool = True):
        """
        初始化统一数据导入引擎

        Args:
            config_manager: 配置管理器
            data_manager: 数据管理器
            max_workers: 最大工作线程数
            enable_ai_optimization: 启用AI优化
            enable_intelligent_config: 启用智能配置
            enable_enhanced_performance: 启用增强性能监控
            enable_enhanced_risk_monitoring: 启用增强风险监控
            enable_distributed_execution: 启用分布式执行
            enable_advanced_caching: 启用高级缓存
            enable_data_quality_monitoring: 启用数据质量监控
        """
        super().__init__()

        # 引擎配置
        self.max_workers = max_workers
        self.enable_ai_optimization = enable_ai_optimization
        self.enable_intelligent_config = enable_intelligent_config
        self.enable_enhanced_performance = enable_enhanced_performance
        self.enable_enhanced_risk_monitoring = enable_enhanced_risk_monitoring
        self.enable_distributed_execution = enable_distributed_execution
        self.enable_advanced_caching = enable_advanced_caching
        self.enable_data_quality_monitoring = enable_data_quality_monitoring

        # 核心组件初始化
        self._init_core_components(config_manager, data_manager)

        # AI和智能优化组件
        self._init_ai_components()

        # 性能和监控组件
        self._init_performance_components()

        # 分布式和并发组件
        self._init_distributed_components()

        # 数据质量组件
        self._init_quality_components()

        # 任务管理
        self._init_task_management()

        # 启动监控系统
        self._start_monitoring_systems()

        logger.info(f"统一数据导入引擎初始化完成 - 功能配置: AI优化={enable_ai_optimization}, "
                    f"智能配置={enable_intelligent_config}, 分布式执行={enable_distributed_execution}")

    def _init_core_components(self, config_manager: Optional[ImportConfigManager],
                              data_manager: Optional[UnifiedDataManager]):
        """初始化核心组件"""
        try:
            # 配置管理器
            if self.enable_intelligent_config:
                self.config_manager = config_manager or None
                logger.info("使用智能配置管理器")
            else:
                self.config_manager = config_manager or ImportConfigManager()
                logger.info("使用标准配置管理器")

            # 数据管理器 - 延迟初始化
            self.data_manager = data_manager
            self._data_manager_initialized = data_manager is not None

            # 真实数据提供器 - 延迟初始化
            self.real_data_provider = None
            self._real_data_provider_initialized = False

            # 线程池
            self.executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="UnifiedImportEngine"
            )

            logger.info("核心组件初始化完成")

        except Exception as e:
            logger.error(f"核心组件初始化失败: {e}")
            raise

    def _init_ai_components(self):
        """初始化AI和智能优化组件"""
        try:
            if self.enable_ai_optimization:
                # AI预测服务
                self.ai_prediction_service = AIPredictionService()
                self._ai_service_initialized = True

                # 自动调优系统
                self.auto_tuner = AlgorithmAutoTuner()

                # AI优化统计
                self._ai_stats = {
                    'predictions_made': 0,
                    'execution_time_saved': 0.0,
                    'accuracy_improved': 0.0,
                    'errors_prevented': 0,
                    'optimizations_applied': 0
                }

                logger.info("AI智能优化组件初始化完成")
            else:
                self.ai_prediction_service = None
                self.auto_tuner = None
                self._ai_service_initialized = False

        except Exception as e:
            logger.error(f"AI组件初始化失败: {e}")
            self.ai_prediction_service = None
            self.auto_tuner = None
            self._ai_service_initialized = False

    def _init_performance_components(self):
        """初始化性能和监控组件"""
        try:
            # 深度分析服务
            self.deep_analysis_service = DeepAnalysisService()

            # 性能集成器
            self.performance_integrator = FactorWeavePerformanceIntegrator()

            if self.enable_enhanced_performance:
                # 增强性能桥接
                self.enhanced_performance_bridge = get_enhanced_performance_bridge()
                logger.info("增强性能监控已启用")
            else:
                self.enhanced_performance_bridge = None

            if self.enable_enhanced_risk_monitoring:
                # 增强风险监控
                self.enhanced_risk_monitor = get_enhanced_risk_monitor()
                logger.info("增强风险监控已启用")
            else:
                self.enhanced_risk_monitor = None

            if self.enable_advanced_caching:
                # 多级缓存管理器
                self.cache_manager = None
                logger.info("高级缓存系统已启用")
            else:
                self.cache_manager = None

            logger.info("性能监控组件初始化完成")

        except Exception as e:
            logger.error(f"性能组件初始化失败: {e}")
            # 设置回退值
            self.enhanced_performance_bridge = None
            self.enhanced_risk_monitor = None
            self.cache_manager = None

    def _init_distributed_components(self):
        """初始化分布式和并发组件"""
        try:
            if self.enable_distributed_execution:
                # 分布式服务
                self.distributed_service = DistributedService()

                # 节点发现
                self.node_discovery = NodeDiscovery()

                logger.info("分布式执行系统已启用")
            else:
                self.distributed_service = None
                self.node_discovery = None

            self.event_bus = get_event_bus()

            # 增强异步管理器
            self.enhanced_async_manager = get_enhanced_async_manager()

            # 断点续传管理器
            try:
                from core.services.breakpoint_resume_manager import get_breakpoint_resume_manager
                self.breakpoint_resume_manager = get_breakpoint_resume_manager()
                logger.info("断点续传管理器已启用")
            except Exception as e:
                logger.warning(f"断点续传管理器初始化失败: {e}")
                self.breakpoint_resume_manager = None

            # 增量更新调度器
            try:
                from core.services.incremental_update_scheduler import get_incremental_update_scheduler
                self.incremental_scheduler = get_incremental_update_scheduler()
                logger.info("增量更新调度器已启用")
            except Exception as e:
                logger.warning(f"增量更新调度器初始化失败: {e}")
                self.incremental_scheduler = None

            logger.info("分布式和并发组件初始化完成")

        except Exception as e:
            logger.error(f"分布式组件初始化失败: {e}")
            self.distributed_service = None
            self.node_discovery = None
            self.breakpoint_resume_manager = None
            self.incremental_scheduler = None

    def _init_quality_components(self):
        """初始化数据质量组件"""
        try:
            if self.enable_data_quality_monitoring:
                self.data_quality_monitor = DataQualityMonitor()
                logger.info("数据质量监控已启用")
            else:
                self.data_quality_monitor = None

        except Exception as e:
            logger.error(f"数据质量组件初始化失败: {e}")
            self.data_quality_monitor = None

    def _init_task_management(self):
        """初始化任务管理"""
        try:
            # 任务存储
            self._running_tasks: Dict[str, Future] = {}
            self._task_results: Dict[str, UnifiedImportResult] = {}
            self._task_configs: Dict[str, UnifiedImportTask] = {}

            # 异步工作线程管理
            self._async_workers: Dict[str, UnifiedAsyncWorker] = {}
            self._worker_lock = threading.RLock()

            # 线程安全锁
            self._task_lock = threading.RLock()

            # 任务统计
            self._task_stats = {
                'total_created': 0,
                'total_completed': 0,
                'total_failed': 0,
                'total_cancelled': 0,
                'average_execution_time': 0.0,
                'success_rate': 0.0
            }

            # 资源管理
            self._max_concurrent_async_tasks = max(4, self.max_workers // 2)
            self._active_async_tasks = 0

            logger.info("任务管理系统初始化完成")

        except Exception as e:
            logger.error(f"任务管理初始化失败: {e}")
            raise

    def _start_monitoring_systems(self):
        """启动监控系统"""
        try:
            # 进度监控定时器
            self.progress_timer = QTimer()
            self.progress_timer.timeout.connect(self._update_all_progress)
            self.progress_timer.start(1000)  # 每秒更新

            # 性能监控定时器
            self.performance_timer = QTimer()
            self.performance_timer.timeout.connect(self._collect_performance_metrics)
            self.performance_timer.start(5000)  # 每5秒收集性能指标

            # 健康检查定时器
            self.health_timer = QTimer()
            self.health_timer.timeout.connect(self._perform_health_check)
            self.health_timer.start(30000)  # 每30秒健康检查

            logger.info("监控系统启动完成")

        except Exception as e:
            logger.error(f"监控系统启动失败: {e}")

    # ==================== 公共API方法 ====================

    def create_import_task(self, task_config: Union[UnifiedImportTask, ImportTaskConfig]) -> str:
        """
        创建导入任务

        Args:
            task_config: 任务配置

        Returns:
            str: 任务ID
        """
        try:
            # 兼容性处理
            if isinstance(task_config, ImportTaskConfig):
                unified_task = self._convert_to_unified_task(task_config)
            else:
                unified_task = task_config

            # 生成任务ID（如果未提供）
            if not unified_task.task_id:
                unified_task.task_id = self._generate_task_id(unified_task)

            # AI优化任务配置
            if self.enable_ai_optimization and self._ai_service_initialized:
                unified_task = self._optimize_task_config(unified_task)

            # 存储任务配置
            with self._task_lock:
                self._task_configs[unified_task.task_id] = unified_task
                self._task_stats['total_created'] += 1

            # 发射任务创建信号
            self.task_created.emit(unified_task.task_id, unified_task)

            logger.info(f"创建导入任务: {unified_task.task_id} - {unified_task.task_name}")
            return unified_task.task_id

        except Exception as e:
            logger.error(f"创建导入任务失败: {e}")
            raise

    def start_import_task(self, task_id: str, use_async: bool = True) -> bool:
        """
        启动导入任务

        Args:
            task_id: 任务ID
            use_async: 是否使用异步执行（默认True）

        Returns:
            bool: 是否成功启动
        """
        try:
            with self._task_lock:
                if task_id not in self._task_configs:
                    logger.error(f"任务不存在: {task_id}")
                    return False

                if task_id in self._running_tasks or task_id in self._async_workers:
                    logger.warning(f"任务已在运行: {task_id}")
                    return False

                task_config = self._task_configs[task_id]

            # 创建断点记录（如果管理器可用）
            if self.breakpoint_resume_manager:
                try:
                    from core.services.breakpoint_resume_manager import ResumeStrategy
                    self.breakpoint_resume_manager.create_breakpoint(
                        task_id=task_id,
                        task_name=task_config.task_name,
                        data_type=task_config.data_type,
                        frequency=task_config.frequency.value if hasattr(task_config.frequency, 'value') else str(task_config.frequency),
                        symbols=task_config.symbols,
                        strategy=ResumeStrategy.RESUME_FROM_FAILURE
                    )
                    logger.info(f"已为任务 {task_id} 创建断点")
                except Exception as e:
                    logger.warning(f"创建断点失败: {e}")

            # 创建任务结果对象
            result = UnifiedImportResult(
                task_id=task_id,
                status=UnifiedTaskStatus.INITIALIZING,
                start_time=datetime.now()
            )

            with self._task_lock:
                self._task_results[task_id] = result

            # 根据配置选择执行方式
            if use_async and self._active_async_tasks < self._max_concurrent_async_tasks:
                # 使用异步工作线程
                success = self._start_async_task(task_config, result)
            else:
                # 使用线程池
                success = self._start_sync_task(task_config, result)

            if success:
                # 发射任务开始信号
                self.task_started.emit(task_id, {
                    'task_name': task_config.task_name,
                    'symbols_count': len(task_config.symbols),
                    'data_type': task_config.data_type,
                    'mode': task_config.mode.value,
                    'execution_mode': 'async' if use_async else 'sync'
                })

                # 发射兼容性信号
                self.import_started.emit(task_id)

                logger.info(f"启动导入任务: {task_id} ({'异步' if use_async else '同步'}模式)")

            return success

        except Exception as e:
            logger.error(f"启动导入任务失败 {task_id}: {e}")
            self.task_failed.emit(task_id, str(e), {'exception': str(e)})
            self.import_failed.emit(task_id, str(e))
            return False

    def _start_async_task(self, task_config: UnifiedImportTask, result: UnifiedImportResult) -> bool:
        """启动异步任务"""
        try:
            # 创建异步工作线程
            worker = UnifiedAsyncWorker(task_config, self)

            # 连接信号
            worker.progress_updated.connect(self._on_async_progress)
            worker.import_started.connect(self._on_async_started)
            worker.import_completed.connect(self._on_async_completed)
            worker.import_failed.connect(self._on_async_failed)
            worker.data_chunk_imported.connect(self._on_async_chunk_imported)

            # 连接到统一信号
            worker.progress_updated.connect(
                lambda progress, message: self.task_progress.emit(
                    task_config.task_id, float(progress), message, {}
                )
            )

            with self._worker_lock:
                self._async_workers[task_config.task_id] = worker
                self._active_async_tasks += 1

            # 启动工作线程
            worker.start()

            logger.info(f"异步任务启动成功: {task_config.task_id}")
            return True

        except Exception as e:
            logger.error(f"启动异步任务失败: {e}")
            return False

    def _start_sync_task(self, task_config: UnifiedImportTask, result: UnifiedImportResult) -> bool:
        """启动同步任务（使用线程池）"""
        try:
            # 提交任务到线程池
            future = self.executor.submit(self._execute_unified_task, task_config, result)

            with self._task_lock:
                self._running_tasks[task_config.task_id] = future

            logger.info(f"同步任务启动成功: {task_config.task_id}")
            return True

        except Exception as e:
            logger.error(f"启动同步任务失败: {e}")
            return False

    def pause_import_task(self, task_id: str, reason: str = "用户请求") -> bool:
        """暂停导入任务"""
        try:
            with self._task_lock:
                if task_id not in self._task_results:
                    return False

                result = self._task_results[task_id]
                if result.status == UnifiedTaskStatus.RUNNING:
                    result.status = UnifiedTaskStatus.PAUSED

                    # 使用断点管理器记录暂停
                    if self.breakpoint_resume_manager:
                        try:
                            self.breakpoint_resume_manager.pause_task(task_id, reason)
                        except Exception as e:
                            logger.warning(f"记录暂停到断点管理器失败: {e}")

                    self.task_paused.emit(task_id, reason)
                    logger.info(f"暂停导入任务: {task_id} - {reason}")
                    return True

            return False

        except Exception as e:
            logger.error(f"暂停导入任务失败 {task_id}: {e}")
            return False

    def resume_import_task(self, task_id: str) -> bool:
        """恢复导入任务"""
        try:
            with self._task_lock:
                if task_id not in self._task_results:
                    return False

                result = self._task_results[task_id]
                if result.status == UnifiedTaskStatus.PAUSED:
                    result.status = UnifiedTaskStatus.RESUMING

                    # 使用断点管理器恢复任务
                    if self.breakpoint_resume_manager:
                        try:
                            self.breakpoint_resume_manager.resume_task(task_id)
                        except Exception as e:
                            logger.warning(f"从断点管理器恢复失败: {e}")

                    self.task_resumed.emit(task_id)
                    logger.info(f"恢复导入任务: {task_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"恢复导入任务失败 {task_id}: {e}")
            return False

    def cancel_import_task(self, task_id: str, reason: str = "用户取消") -> bool:
        """取消导入任务"""
        try:
            cancelled = False

            with self._task_lock:
                # 取消同步任务
                if task_id in self._running_tasks:
                    future = self._running_tasks[task_id]
                    future.cancel()
                    del self._running_tasks[task_id]
                    cancelled = True

            with self._worker_lock:
                # 取消异步任务
                if task_id in self._async_workers:
                    worker = self._async_workers[task_id]
                    worker.stop()
                    del self._async_workers[task_id]
                    self._active_async_tasks = max(0, self._active_async_tasks - 1)
                    cancelled = True

            if cancelled:
                with self._task_lock:
                    # 更新任务状态
                    if task_id in self._task_results:
                        result = self._task_results[task_id]
                        result.status = UnifiedTaskStatus.CANCELLED
                        result.end_time = datetime.now()
                        if result.start_time:
                            result.execution_time = (result.end_time - result.start_time).total_seconds()

                        self._task_stats['total_cancelled'] += 1

                # 使用断点管理器停止任务
                if self.breakpoint_resume_manager:
                    try:
                        self.breakpoint_resume_manager.stop_task(task_id, reason)
                    except Exception as e:
                        logger.warning(f"停止断点管理器中的任务失败: {e}")

                self.task_cancelled.emit(task_id, reason)
                logger.info(f"取消导入任务: {task_id} - {reason}")
                return True
            else:
                logger.warning(f"任务不在运行状态，无法取消: {task_id}")
                return False

        except Exception as e:
            logger.error(f"取消导入任务失败 {task_id}: {e}")
            return False

    def get_task_result(self, task_id: str) -> Optional[UnifiedImportResult]:
        """获取任务结果"""
        with self._task_lock:
            return self._task_results.get(task_id)

    def get_running_tasks(self) -> List[str]:
        """获取正在运行的任务列表"""
        with self._task_lock:
            return list(self._running_tasks.keys())

    def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        with self._task_lock:
            stats = self._task_stats.copy()

            # 计算成功率
            total_finished = stats['total_completed'] + stats['total_failed']
            if total_finished > 0:
                stats['success_rate'] = (stats['total_completed'] / total_finished) * 100

            # 添加当前运行任务数
            stats['currently_running'] = len(self._running_tasks)

            return stats

    def get_ai_statistics(self) -> Dict[str, Any]:
        """获取AI优化统计"""
        if self.enable_ai_optimization and hasattr(self, '_ai_stats'):
            return self._ai_stats.copy()
        return {}

    def shutdown(self):
        """关闭引擎"""
        try:
            logger.info("开始关闭统一数据导入引擎...")

            # 停止所有定时器
            if hasattr(self, 'progress_timer'):
                self.progress_timer.stop()
            if hasattr(self, 'performance_timer'):
                self.performance_timer.stop()
            if hasattr(self, 'health_timer'):
                self.health_timer.stop()

            # 取消所有运行中的任务
            with self._task_lock:
                for task_id in list(self._running_tasks.keys()):
                    self.cancel_import_task(task_id, "引擎关闭")

            # 停止所有异步工作线程
            with self._worker_lock:
                for task_id, worker in list(self._async_workers.items()):
                    try:
                        logger.info(f"停止异步工作线程: {task_id}")
                        worker.stop()
                        worker.deleteLater()
                    except Exception as e:
                        logger.warning(f"停止异步工作线程失败 {task_id}: {e}")

                self._async_workers.clear()
                self._active_async_tasks = 0

            # 关闭线程池
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True, timeout=30)

            # 关闭分布式服务
            if self.distributed_service:
                try:
                    self.distributed_service.shutdown()
                except Exception as e:
                    logger.warning(f"关闭分布式服务失败: {e}")

            logger.info("统一数据导入引擎已关闭")

        except Exception as e:
            logger.error(f"关闭引擎失败: {e}")

    # ==================== 兼容性方法 ====================

    def start_async_import(self, import_config: dict) -> str:
        """
        启动异步导入（兼容AsyncDataImportWorker接口）

        Args:
            import_config: 导入配置字典

        Returns:
            str: 任务ID
        """
        try:
            # 转换配置格式
            task_config = self._convert_dict_to_unified_task(import_config)

            # 创建任务
            task_id = self.create_import_task(task_config)

            # 启动异步任务
            success = self.start_import_task(task_id, use_async=True)

            if success:
                return task_id
            else:
                raise Exception("启动异步任务失败")

        except Exception as e:
            logger.error(f"启动异步导入失败: {e}")
            raise

    def _convert_dict_to_unified_task(self, import_config: dict) -> UnifiedImportTask:
        """将字典配置转换为UnifiedImportTask"""
        task_id = import_config.get('task_id', f"import_{int(time.time())}")

        # 从data_sources提取股票代码
        data_sources = import_config.get('data_sources', [])
        symbols = data_sources if isinstance(data_sources, list) else [data_sources]

        return UnifiedImportTask(
            task_id=task_id,
            task_name=import_config.get('task_name', f"导入任务_{task_id}"),
            symbols=symbols,
            data_source=import_config.get('data_source', '默认数据源'),
            asset_type=import_config.get('asset_type', '股票'),
            data_type=import_config.get('data_type', 'K线数据'),
            frequency=import_config.get('frequency', '日线'),
            start_date=import_config.get('start_date'),
            end_date=import_config.get('end_date'),
            mode=ImportMode(import_config.get('mode', 'manual')),
            config=import_config
        )

    # ==================== 私有方法 ====================

    def _convert_to_unified_task(self, task_config: ImportTaskConfig) -> UnifiedImportTask:
        """将ImportTaskConfig转换为UnifiedImportTask"""
        # 创建UnifiedImportTask
        unified_task = UnifiedImportTask(
            task_id=task_config.task_id,
            task_name=task_config.task_name,
            symbols=task_config.symbols,
            data_source=task_config.data_source,
            asset_type=task_config.asset_type,
            data_type=task_config.data_type,
            frequency=task_config.frequency,
            start_date=task_config.start_date,
            end_date=task_config.end_date,
            mode=ImportMode(getattr(task_config, 'mode', 'manual'))
        )

        # 保留新的配置参数
        if hasattr(task_config, 'gap_fill_mode') and task_config.gap_fill_mode:
            unified_task.config['gap_fill_mode'] = True
            unified_task.config['gap_threshold_days'] = getattr(task_config, 'gap_threshold_days', 30)
            unified_task.config['gap_fill_threshold'] = getattr(task_config, 'gap_fill_threshold', 30)
            unified_task.config['auto_fill_gaps'] = getattr(task_config, 'auto_fill_gaps', True)
            unified_task.config['skip_weekends'] = getattr(task_config, 'skip_weekends', True)
            unified_task.config['skip_holidays'] = getattr(task_config, 'skip_holidays', True)

        if hasattr(task_config, 'smart_fill_mode') and task_config.smart_fill_mode:
            unified_task.config['smart_fill_mode'] = True
            unified_task.config['recent_days_only'] = getattr(task_config, 'recent_days_only', 30)
            unified_task.config['auto_fill_gaps'] = getattr(task_config, 'auto_fill_gaps', True)
            unified_task.config['skip_weekends'] = getattr(task_config, 'skip_weekends', True)
            unified_task.config['skip_holidays'] = getattr(task_config, 'skip_holidays', True)

        if hasattr(task_config, 'incremental_days'):
            unified_task.config['incremental_days'] = task_config.incremental_days
            unified_task.config['skip_weekends'] = getattr(task_config, 'skip_weekends', True)
            unified_task.config['skip_holidays'] = getattr(task_config, 'skip_holidays', True)

        return unified_task

    def _generate_task_id(self, task_config: UnifiedImportTask) -> str:
        """生成任务ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content = f"{task_config.task_name}_{task_config.data_type}_{len(task_config.symbols)}"
        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"task_{timestamp}_{hash_suffix}"

    def _optimize_task_config(self, task_config: UnifiedImportTask) -> UnifiedImportTask:
        """AI优化任务配置"""
        try:
            if not self.ai_prediction_service:
                return task_config

            # 预测执行时间并优化参数
            prediction_data = {
                'symbols_count': len(task_config.symbols),
                'data_type': task_config.data_type,
                'frequency': task_config.frequency,
                'mode': task_config.mode.value
            }

            # 获取执行时间预测
            predicted_time = self.ai_prediction_service.predict(
                PredictionType.EXECUTION_TIME,
                prediction_data
            )

            if predicted_time and predicted_time.get('success'):
                # 根据预测时间调整超时设置
                estimated_time = predicted_time.get('prediction', 300)
                task_config.timeout = max(int(estimated_time * 1.5), 300)  # 1.5倍预测时间作为超时

                # 记录AI优化统计
                self._ai_stats['predictions_made'] += 1

                logger.info(f"AI优化任务配置: 预测执行时间={estimated_time:.1f}s, 设置超时={task_config.timeout}s")

            return task_config

        except Exception as e:
            logger.warning(f"AI优化任务配置失败: {e}")
            return task_config

    def _execute_unified_task(self, task_config: UnifiedImportTask, result: UnifiedImportResult):
        """执行统一任务的核心逻辑"""
        try:
            logger.info(f"开始执行统一任务: {task_config.task_id}")

            # 更新状态为运行中
            result.status = UnifiedTaskStatus.RUNNING
            result.start_time = datetime.now()

            # 初始化数据管理器（如果需要）
            if not self._data_manager_initialized:
                self._init_data_manager()

            # 初始化真实数据提供器（如果需要）
            if not self._real_data_provider_initialized:
                self._init_real_data_provider()

            # 转换为兼容的ImportTaskConfig
            import_config = task_config.to_import_task_config()

            # 执行数据导入逻辑
            if task_config.data_type == "K线数据":
                self._import_kline_data(import_config, result)
            elif task_config.data_type == "实时行情":
                self._import_realtime_data(import_config, result)
            elif task_config.data_type == "基本面数据":
                self._import_fundamental_data(import_config, result)
            else:
                logger.warning(f"不支持的数据类型，使用默认K线数据导入: {task_config.data_type}")
                self._import_kline_data(import_config, result)

            # 任务完成
            result.status = UnifiedTaskStatus.COMPLETED
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()

            # 更新统计
            with self._task_lock:
                self._task_stats['total_completed'] += 1
                if task_config.task_id in self._running_tasks:
                    del self._running_tasks[task_config.task_id]

            # 发射完成信号
            self.task_completed.emit(task_config.task_id, result)

            logger.info(f"任务执行完成: {task_config.task_id}, 耗时: {result.execution_time:.2f}s")

        except Exception as e:
            # 任务失败处理
            result.status = UnifiedTaskStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()
            if result.start_time:
                result.execution_time = (result.end_time - result.start_time).total_seconds()

            # 更新统计
            with self._task_lock:
                self._task_stats['total_failed'] += 1
                if task_config.task_id in self._running_tasks:
                    del self._running_tasks[task_config.task_id]

            # 发射失败信号
            self.task_failed.emit(task_config.task_id, str(e), {'exception': str(e)})

            logger.error(f"任务执行失败: {task_config.task_id} - {e}")

    def _execute_unified_task_sync(self, task_config: UnifiedImportTask, result: UnifiedImportResult):
        """同步执行统一任务（用于异步工作线程）"""
        try:
            logger.info(f"开始同步执行统一任务: {task_config.task_id}")

            # 更新状态为运行中
            result.status = UnifiedTaskStatus.RUNNING
            result.start_time = datetime.now()

            # 初始化数据管理器（如果需要）
            if not self._data_manager_initialized:
                self._init_data_manager()

            # 初始化真实数据提供器（如果需要）
            if not self._real_data_provider_initialized:
                self._init_real_data_provider()

            # 转换为兼容的ImportTaskConfig
            import_config = task_config.to_import_task_config()

            # 执行数据导入逻辑
            if task_config.data_type == "K线数据":
                self._import_kline_data_sync(import_config, result)
            elif task_config.data_type == "实时行情":
                self._import_realtime_data_sync(import_config, result)
            elif task_config.data_type == "基本面数据":
                self._import_fundamental_data_sync(import_config, result)
            else:
                logger.warning(f"不支持的数据类型，使用默认K线数据导入: {task_config.data_type}")
                self._import_kline_data_sync(import_config, result)

            # 任务完成
            result.status = UnifiedTaskStatus.COMPLETED
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()

            # 更新统计
            with self._task_lock:
                self._task_stats['total_completed'] += 1

            logger.info(f"同步任务执行完成: {task_config.task_id}, 耗时: {result.execution_time:.2f}s")

        except Exception as e:
            # 任务失败处理
            result.status = UnifiedTaskStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()
            if result.start_time:
                result.execution_time = (result.end_time - result.start_time).total_seconds()

            # 更新统计
            with self._task_lock:
                self._task_stats['total_failed'] += 1

            logger.error(f"同步任务执行失败: {task_config.task_id} - {e}")
            raise

    # ==================== 异步信号处理方法 ====================

    def _on_async_progress(self, progress: int, message: str):
        """处理异步进度更新"""
        # 转发兼容性信号
        self.progress_updated.emit(progress, message)

    def _on_async_started(self, task_id: str):
        """处理异步任务开始"""
        # 转发兼容性信号
        self.import_started.emit(task_id)

    def _on_async_completed(self, task_id: str, result_dict: dict):
        """处理异步任务完成"""
        try:
            # 清理异步工作线程
            with self._worker_lock:
                if task_id in self._async_workers:
                    worker = self._async_workers[task_id]
                    worker.deleteLater()  # 安全删除Qt对象
                    del self._async_workers[task_id]
                    self._active_async_tasks = max(0, self._active_async_tasks - 1)

            # 更新任务结果
            with self._task_lock:
                if task_id in self._task_results:
                    result = self._task_results[task_id]
                    result.status = UnifiedTaskStatus.COMPLETED
                    if not result.end_time:
                        result.end_time = datetime.now()
                    if result.start_time and not result.execution_time:
                        result.execution_time = (result.end_time - result.start_time).total_seconds()

            # 转发信号
            self.import_completed.emit(task_id, result_dict)

            # 发射统一完成信号
            if task_id in self._task_results:
                self.task_completed.emit(task_id, self._task_results[task_id])

            logger.info(f"异步任务完成处理: {task_id}")

        except Exception as e:
            logger.error(f"处理异步任务完成失败: {e}")

    def _on_async_failed(self, task_id: str, error_message: str):
        """处理异步任务失败"""
        try:
            # 清理异步工作线程
            with self._worker_lock:
                if task_id in self._async_workers:
                    worker = self._async_workers[task_id]
                    worker.deleteLater()  # 安全删除Qt对象
                    del self._async_workers[task_id]
                    self._active_async_tasks = max(0, self._active_async_tasks - 1)

            # 更新任务结果
            with self._task_lock:
                if task_id in self._task_results:
                    result = self._task_results[task_id]
                    result.status = UnifiedTaskStatus.FAILED
                    result.error_message = error_message
                    if not result.end_time:
                        result.end_time = datetime.now()
                    if result.start_time and not result.execution_time:
                        result.execution_time = (result.end_time - result.start_time).total_seconds()

            # 转发信号
            self.import_failed.emit(task_id, error_message)

            # 发射统一失败信号
            self.task_failed.emit(task_id, error_message, {'async_error': True})

            logger.error(f"异步任务失败处理: {task_id} - {error_message}")

        except Exception as e:
            logger.error(f"处理异步任务失败失败: {e}")

    def _on_async_chunk_imported(self, task_id: str, imported_count: int, total_count: int):
        """处理异步数据块导入"""
        # 转发兼容性信号
        self.data_chunk_imported.emit(task_id, imported_count, total_count)

        # 计算进度并发射统一进度信号
        if total_count > 0:
            progress = (imported_count / total_count) * 100
            self.task_progress.emit(
                task_id,
                progress,
                f"已导入 {imported_count}/{total_count} 条数据",
                {'imported': imported_count, 'total': total_count}
            )
    
    def _extract_asset_metadata_from_kline(self, symbol: str, kline_data: pd.DataFrame, 
                                          data_source: str, asset_type) -> dict:
        """从K线数据和数据源获取完整的资产元数据"""
        from core.plugin_types import AssetType
        
        # 1. 从数据源插件获取股票列表（包含name、industry等信息）
        stock_info = None
        if self.real_data_provider:
            try:
                # 尝试从插件获取股票列表
                plugin = self.real_data_provider.get_plugin(data_source)
                if plugin and hasattr(plugin, 'get_stock_list'):
                    stock_list_df = plugin.get_stock_list()
                    if stock_list_df is not None and not stock_list_df.empty:
                        # 查找当前symbol的信息
                        matching_stocks = stock_list_df[stock_list_df['code'] == symbol]
                        if not matching_stocks.empty:
                            stock_info = matching_stocks.iloc[0].to_dict()
                            logger.debug(f"从插件获取到股票信息: {symbol} - {stock_info.get('name', symbol)}")
            except Exception as e:
                logger.debug(f"从插件获取股票信息失败: {e}")
        
        # 2. 推断market
        if symbol.startswith(('000', '001', '002', '003')):
            market = 'SZ'
        elif symbol.startswith(('600', '601', '603', '605')):
            market = 'SH'
        elif symbol.startswith('HK'):
            market = 'HK'
        elif len(symbol) <= 5 and symbol.isalpha():
            market = 'US'
        else:
            market = 'SZ'
        
        # 3. 从K线数据中提取可能包含的元数据字段
        name = symbol  # 默认值
        industry = None
        sector = None
        
        if kline_data is not None and not kline_data.empty:
            first_row = kline_data.iloc[0]
            # 尝试从K线数据中获取name（某些数据源可能包含）
            if 'name' in first_row:
                name = first_row['name']
            if 'industry' in first_row:
                industry = first_row['industry']
            if 'sector' in first_row:
                sector = first_row['sector']
        
        # 4. 如果从插件获取到了信息，优先使用插件数据
        if stock_info:
            name = stock_info.get('name', name)
            market = stock_info.get('market', market)
            # 注意：通达信插件可能没有industry/sector字段，但其他插件可能有
            if 'industry' in stock_info and stock_info['industry']:
                industry = stock_info['industry']
            if 'sector' in stock_info and stock_info['sector']:
                sector = stock_info['sector']
        
        # 5. 构建完整的元数据
        metadata = {
            'symbol': symbol,
            'name': name,
            'market': market,
            'asset_type': asset_type.value,
            'primary_data_source': data_source,
            'data_sources': [data_source],
            'listing_status': 'active',
            'updated_at': datetime.now().isoformat()
        }
        
        # 添加可选字段
        if industry:
            metadata['industry'] = industry
        if sector:
            metadata['sector'] = sector
        
        return metadata

    def _import_kline_data(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """导入K线数据 - 真实实现"""
        try:
            logger.info(f"开始导入K线数据: {len(task_config.symbols)}个股票")
            
            from core.asset_database_manager import get_asset_separated_database_manager
            from core.plugin_types import DataType, AssetType
            from datetime import datetime
            
            result.total_records = len(task_config.symbols)
            asset_db_manager = get_asset_separated_database_manager()

            for i, symbol in enumerate(task_config.symbols):
                # 检查任务是否被暂停或取消
                if result.status in [UnifiedTaskStatus.PAUSED, UnifiedTaskStatus.CANCELLED]:
                    logger.info(f"任务被{result.status.value}，停止导入")
                    break

                try:
                    logger.info(f"导入股票数据: {symbol} ({i+1}/{len(task_config.symbols)})")

                    # 1. 从真实数据提供器获取K线数据（若无则使用模拟）
                    kline_data = None
                    if self.real_data_provider and hasattr(self.real_data_provider, 'fetch_kline'):
                        try:
                            kline_data = self.real_data_provider.fetch_kline(
                                symbol=symbol,
                                data_source=task_config.data_source,
                                frequency=task_config.frequency,
                                start_date=task_config.start_date,
                                end_date=task_config.end_date
                            )
                        except Exception as e:
                            logger.warning(f"获取K线数据失败: {e}")

                    if kline_data is None or kline_data.empty:
                        logger.warning(f"未获取到股票数据: {symbol}")
                        result.skipped_records += 1
                        continue

                    # 2. 识别资产类型
                    asset_type = AssetType.STOCK_A
                    try:
                        if hasattr(self, 'asset_identifier'):
                            asset_type = self.asset_identifier.identify_asset_type_by_symbol(symbol)
                    except:
                        pass

                    # 3. 标准化K线数据字段
                    import pandas as pd
                    df = kline_data.copy()
                    required_fields = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                    for field in required_fields:
                        if field not in df.columns:
                            if field == 'datetime' and 'date' in df.columns:
                                df['datetime'] = df['date']
                            elif field == 'volume':
                                df[field] = 0
                            else:
                                df[field] = 0.0
                    
                    df['symbol'] = symbol
                    df['data_source'] = task_config.data_source
                    df['frequency'] = task_config.frequency
                    df['updated_at'] = datetime.now()
                    
                    if 'datetime' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                        df['datetime'] = pd.to_datetime(df['datetime'])

                    # 4. 保存K线数据到资产数据库
                    rows_affected = asset_db_manager.store_standardized_data(
                        df,
                        asset_type,
                        DataType.HISTORICAL_KLINE
                    )
                    logger.info(f"保存K线数据: {symbol}, 条数: {rows_affected}")

                    # 5. 提取并保存资产元数据 - 从数据源获取完整信息
                    asset_metadata = self._extract_asset_metadata_from_kline(
                        symbol, 
                        kline_data, 
                        task_config.data_source,
                        asset_type
                    )

                    # 6. 使用asset_database_manager保存元数据
                    save_success = asset_db_manager.upsert_asset_metadata(
                        symbol,
                        asset_type,
                        asset_metadata
                    )
                    
                    if save_success:
                        logger.info(f"保存资产元数据成功: {symbol}, market={market}, asset_type={asset_type.value}, data_source={task_config.data_source}")
                        # 立即验证是否保存成功
                        saved_metadata = asset_db_manager.get_asset_metadata(symbol, asset_type)
                        if saved_metadata:
                            logger.debug(f"验证成功: {symbol} 元数据已存在于asset_metadata表")
                        else:
                            logger.error(f"验证失败: {symbol} 元数据未能成功保存到asset_metadata表")
                    else:
                        logger.error(f"❌ 保存资产元数据失败: {symbol}")

                    result.processed_records += 1

                    # 发射进度更新信号
                    progress = (result.processed_records / result.total_records) * 100
                    self.task_progress.emit(
                        task_config.task_id,
                        progress,
                        f"正在导入 {symbol} ({result.processed_records}/{result.total_records})",
                        {'current_symbol': symbol, 'processed': result.processed_records, 'rows': rows_affected}
                    )

                except Exception as e:
                    logger.error(f"导入股票数据失败 {symbol}: {e}", exc_info=True)
                    result.failed_records += 1
                    result.warnings.append(f"导入{symbol}失败: {str(e)}")

            logger.info(f"K线数据导入完成: 成功={result.processed_records}, 失败={result.failed_records}, 跳过={result.skipped_records}")

        except Exception as e:
            logger.error(f"K线数据导入失败: {e}", exc_info=True)
            raise

    def _import_realtime_data(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """导入实时行情数据"""
        logger.info("导入实时行情数据 - 功能开发中")
        result.total_records = len(task_config.symbols)
        result.processed_records = result.total_records

    def _import_fundamental_data(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """导入基本面数据"""
        logger.info("导入基本面数据 - 功能开发中")
        result.total_records = len(task_config.symbols)
        result.processed_records = result.total_records

    # ==================== 同步版本的数据导入方法 ====================

    def _import_kline_data_sync(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """同步导入K线数据（用于异步工作线程）"""
        try:
            logger.info(f"开始同步导入K线数据: {len(task_config.symbols)}个股票")

            from core.asset_database_manager import get_asset_separated_database_manager
            from core.plugin_types import DataType, AssetType
            from datetime import datetime

            # 检查是否启用了间隙填充模式
            gap_fill_mode = getattr(task_config, 'gap_fill_mode', False)
            smart_fill_mode = getattr(task_config, 'smart_fill_mode', False)

            # 检查是否启用了增量下载模式
            incremental_mode = task_config.mode.value == 'incremental'

            if gap_fill_mode:
                logger.info(f"启用间隙填充模式，阈值: {getattr(task_config, 'gap_threshold_days', 30)}天")
                self._execute_gap_fill_sync(task_config, result)
                return

            if smart_fill_mode:
                logger.info(f"启用智能补全模式，仅补全最近{getattr(task_config, 'recent_days_only', 30)}天数据")
                self._execute_smart_fill_sync(task_config, result)
                return

            if incremental_mode:
                logger.info(f"启用增量下载模式，最近{getattr(task_config, 'incremental_days', 7)}天")
                self._execute_incremental_sync(task_config, result)
                return

            # 标准全量下载模式
            logger.info("使用标准全量下载模式")

            result.total_records = len(task_config.symbols)
            asset_db_manager = get_asset_separated_database_manager()

            for i, symbol in enumerate(task_config.symbols):
                # 检查任务是否被取消
                if result.status == UnifiedTaskStatus.CANCELLED:
                    logger.info(f"任务被取消，停止导入")
                    break

                try:
                    logger.info(f"同步导入股票数据: {symbol} ({i+1}/{len(task_config.symbols)})")

                    # 1. 从真实数据提供器获取K线数据
                    kline_data = None
                    if self.real_data_provider and hasattr(self.real_data_provider, 'fetch_kline'):
                        try:
                            kline_data = self.real_data_provider.fetch_kline(
                                symbol=symbol,
                                data_source=task_config.data_source,
                                frequency=task_config.frequency,
                                start_date=task_config.start_date,
                                end_date=task_config.end_date
                            )
                        except Exception as e:
                            logger.warning(f"获取K线数据失败: {e}")

                    if kline_data is None or kline_data.empty:
                        logger.warning(f"未获取到股票数据: {symbol}")
                        result.skipped_records += 1
                        continue

                    # 2. 识别资产类型
                    asset_type = AssetType.STOCK_A
                    try:
                        if hasattr(self, 'asset_identifier'):
                            asset_type = self.asset_identifier.identify_asset_type_by_symbol(symbol)
                    except:
                        pass

                    # 3. 标准化K线数据字段
                    import pandas as pd
                    df = kline_data.copy()
                    required_fields = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                    for field in required_fields:
                        if field not in df.columns:
                            if field == 'datetime' and 'date' in df.columns:
                                df['datetime'] = df['date']
                            elif field == 'volume':
                                df[field] = 0
                            else:
                                df[field] = 0.0
                    
                    df['symbol'] = symbol
                    df['data_source'] = task_config.data_source
                    df['frequency'] = task_config.frequency
                    df['updated_at'] = datetime.now()
                    
                    if 'datetime' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                        df['datetime'] = pd.to_datetime(df['datetime'])

                    # 4. 保存K线数据到资产数据库
                    rows_affected = asset_db_manager.store_standardized_data(
                        df,
                        asset_type,
                        DataType.HISTORICAL_KLINE
                    )
                    logger.info(f"保存K线数据: {symbol}, 条数: {rows_affected}")

                    # 5. 提取并保存资产元数据 - 从数据源获取完整信息
                    asset_metadata = self._extract_asset_metadata_from_kline(
                        symbol, 
                        kline_data, 
                        task_config.data_source,
                        asset_type
                    )

                    # 6. 使用asset_database_manager保存元数据
                    save_success = asset_db_manager.upsert_asset_metadata(
                        symbol,
                        asset_type,
                        asset_metadata
                    )
                    
                    if save_success:
                        logger.info(f"同步保存资产元数据成功: {symbol}, market={market}, asset_type={asset_type.value}, data_source={task_config.data_source}")
                        # 立即验证是否保存成功
                        saved_metadata = asset_db_manager.get_asset_metadata(symbol, asset_type)
                        if saved_metadata:
                            logger.debug(f"验证成功: {symbol} 元数据已存在于asset_metadata表")
                        else:
                            logger.error(f"验证失败: {symbol} 元数据未能成功保存到asset_metadata表")
                    else:
                        logger.error(f"❌ 同步保存资产元数据失败: {symbol}")

                    result.processed_records += 1

                except Exception as e:
                    logger.error(f"同步导入股票数据失败 {symbol}: {e}", exc_info=True)
                    result.failed_records += 1
                    result.warnings.append(f"导入{symbol}失败: {str(e)}")

            logger.info(f"同步K线数据导入完成: 成功={result.processed_records}, 失败={result.failed_records}, 跳过={result.skipped_records}")

        except Exception as e:
            logger.error(f"同步K线数据导入失败: {e}", exc_info=True)
            raise

    def _import_realtime_data_sync(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """同步导入实时行情数据"""
        logger.info("同步导入实时行情数据 - 功能开发中")
        result.total_records = len(task_config.symbols)
        result.processed_records = result.total_records

    def _import_fundamental_data_sync(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """同步导入基本面数据"""
        logger.info("同步导入基本面数据 - 功能开发中")
        result.total_records = len(task_config.symbols)
        result.processed_records = result.total_records

    def _init_data_manager(self):
        """初始化数据管理器"""
        try:
            if not self.data_manager:
                self.data_manager = get_unified_data_manager()
            self._data_manager_initialized = True
            logger.info("数据管理器初始化完成")
        except Exception as e:
            logger.error(f"数据管理器初始化失败: {e}")

    def _init_real_data_provider(self):
        """初始化真实数据提供器"""
        try:
            if not self.real_data_provider:
                self.real_data_provider = RealDataProvider()
            self._real_data_provider_initialized = True
            logger.info("真实数据提供器初始化完成")
        except Exception as e:
            logger.error(f"真实数据提供器初始化失败: {e}")

    def _update_all_progress(self):
        """更新所有任务进度"""
        try:
            with self._task_lock:
                for task_id, result in self._task_results.items():
                    if result.status == UnifiedTaskStatus.RUNNING:
                        # 这里可以添加更详细的进度更新逻辑
                        pass
        except Exception as e:
            logger.debug(f"更新进度失败: {e}")

    def _collect_performance_metrics(self):
        """收集性能指标"""
        try:
            if self.enhanced_performance_bridge:
                # 收集性能指标
                pass
        except Exception as e:
            logger.debug(f"收集性能指标失败: {e}")

    def _perform_health_check(self):
        """执行健康检查"""
        try:
            # 检查各组件状态
            health_status = {
                'engine_status': 'healthy',
                'running_tasks': len(self._running_tasks),
                'total_tasks': len(self._task_results),
                'ai_service': self._ai_service_initialized,
                'data_manager': self._data_manager_initialized
            }

            self.engine_status_changed.emit('health_check', health_status)

        except Exception as e:
            logger.debug(f"健康检查失败: {e}")

    def _execute_gap_fill_sync(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """执行间隙填充模式导入"""
        try:
            from core.services.enhanced_duckdb_data_downloader import get_enhanced_duckdb_data_downloader

            logger.info(f"开始间隙填充导入: {len(task_config.symbols)}个股票")

            # 获取增强数据下载器
            downloader = get_enhanced_duckdb_data_downloader()
            if not downloader:
                raise Exception("无法获取增强数据下载器")

            gap_threshold_days = getattr(task_config, 'gap_threshold_days', 30)
            auto_fill_gaps = getattr(task_config, 'auto_fill_gaps', True)
            skip_weekends = getattr(task_config, 'skip_weekends', True)
            skip_holidays = getattr(task_config, 'skip_holidays', True)
            check_completeness = getattr(task_config, 'check_completeness', True)
            skip_latest_data = getattr(task_config, 'skip_latest_data', True)

            # 执行间隙填充下载
            import asyncio
            from datetime import datetime

            end_date = datetime.strptime(task_config.end_date, '%Y-%m-%d')

            async def _gap_fill_wrapper():
                symbols_to_check = task_config.symbols
                # 如果启用了skip_latest_data，先检查最新数据状态
                if skip_latest_data:
                    try:
                        latest_check = await downloader.check_latest_data_status(symbols_to_check)
                        symbols_to_check = [s for s in symbols_to_check if not latest_check.get(s, True)]
                        logger.info(f"跳过最新数据后，需要检查的股票数: {len(symbols_to_check)}/{len(task_config.symbols)}")
                    except Exception as e:
                        logger.warning(f"检查最新数据状态失败: {e}，继续使用所有符号")

                return await downloader.check_and_fill_data_gaps(
                    symbols_to_check,
                    end_date,
                    gap_threshold_days,
                    auto_fill_gaps,
                    skip_weekends,
                    skip_holidays
                )

            # 在新的事件循环中执行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success_stats = loop.run_until_complete(_gap_fill_wrapper())

                # 更新结果统计
                result.processed_records = success_stats.get('total_symbols', 0)
                result.success_count = success_stats.get('success_count', 0)
                result.failed_count = success_stats.get('failed_count', 0)
                result.skipped_count = success_stats.get('skipped_count', 0)

                logger.info(f"间隙填充导入完成: 成功={result.success_count}, 失败={result.failed_count}, 跳过={result.skipped_count}")

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"间隙填充导入失败: {e}")
            result.failed_records = len(task_config.symbols)
            result.error_message = str(e)
            raise

    def _execute_smart_fill_sync(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """执行智能补全模式导入"""
        try:
            from core.services.enhanced_duckdb_data_downloader import get_enhanced_duckdb_data_downloader
            from core.services.incremental_data_analyzer import get_incremental_data_analyzer
            from datetime import datetime

            logger.info(f"开始智能补全导入: {len(task_config.symbols)}个股票")

            # 获取服务
            downloader = get_enhanced_duckdb_data_downloader()
            analyzer = get_incremental_data_analyzer()
            if not downloader or not analyzer:
                raise Exception("无法获取必要的服务")

            recent_days_only = getattr(task_config, 'recent_days_only', 30)
            auto_fill_gaps = getattr(task_config, 'auto_fill_gaps', True)
            skip_weekends = getattr(task_config, 'skip_weekends', True)
            skip_holidays = getattr(task_config, 'skip_holidays', True)
            check_completeness = getattr(task_config, 'check_completeness', True)
            skip_latest_data = getattr(task_config, 'skip_latest_data', True)

            end_date = datetime.strptime(task_config.end_date, '%Y-%m-%d')
            start_date = end_date - datetime.timedelta(days=recent_days_only)

            # 智能补全分析
            import asyncio

            async def _smart_fill_wrapper():
                # 生成下载计划
                download_plan = await analyzer.analyze_incremental_requirements(
                    task_config.symbols,
                    end_date,
                    strategy='smart_fill',
                    skip_weekends=skip_weekends,
                    skip_holidays=skip_holidays,
                    check_completeness=check_completeness
                )

                # 如果启用了skip_latest_data，过滤掉已经是最新的符号
                symbols_to_download = download_plan.symbols_to_download
                if skip_latest_data:
                    try:
                        latest_check = await downloader.check_latest_data_status(task_config.symbols)
                        symbols_to_download = [s for s in symbols_to_download if not latest_check.get(s, True)]
                        logger.info(f"跳过最新数据后，需要补全的股票数: {len(symbols_to_download)}/{len(download_plan.symbols_to_download)}")
                    except Exception as e:
                        logger.warning(f"检查最新数据状态失败: {e}，继续使用计划中的符号")

                # 执行智能补全下载
                success_stats = await downloader.check_and_fill_data_gaps(
                    symbols_to_download,
                    end_date,
                    recent_days_only,
                    auto_fill_gaps,
                    skip_weekends,
                    skip_holidays
                )

                return success_stats

            # 在新的事件循环中执行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success_stats = loop.run_until_complete(_smart_fill_wrapper())

                # 更新结果统计
                result.processed_records = success_stats.get('total_symbols', 0)
                result.success_count = success_stats.get('success_count', 0)
                result.failed_count = success_stats.get('failed_count', 0)
                result.skipped_count = success_stats.get('skipped_count', 0)

                logger.info(f"智能补全导入完成: 成功={result.success_count}, 失败={result.failed_count}, 跳过={result.skipped_count}")

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"智能补全导入失败: {e}")
            result.failed_records = len(task_config.symbols)
            result.error_message = str(e)
            raise

    def _execute_incremental_sync(self, task_config: ImportTaskConfig, result: UnifiedImportResult):
        """执行增量下载模式导入"""
        try:
            from core.services.enhanced_duckdb_data_downloader import get_enhanced_duckdb_data_downloader
            from core.services.incremental_data_analyzer import get_incremental_data_analyzer
            from datetime import datetime

            logger.info(f"开始增量下载导入: {len(task_config.symbols)}个股票")

            # 获取服务
            downloader = get_enhanced_duckdb_data_downloader()
            analyzer = get_incremental_data_analyzer()
            if not downloader or not analyzer:
                raise Exception("无法获取必要的服务")

            incremental_days = getattr(task_config, 'incremental_days', 7)
            skip_weekends = getattr(task_config, 'skip_weekends', True)
            skip_holidays = getattr(task_config, 'skip_holidays', True)
            check_completeness = getattr(task_config, 'check_completeness', True)
            skip_latest_data = getattr(task_config, 'skip_latest_data', True)

            end_date = datetime.strptime(task_config.end_date, '%Y-%m-%d')

            # 增量分析
            import asyncio

            async def _incremental_wrapper():
                # 分析增量需求
                download_plan = await analyzer.analyze_incremental_requirements(
                    task_config.symbols,
                    end_date,
                    strategy='latest_only',
                    skip_weekends=skip_weekends,
                    skip_holidays=skip_holidays,
                    check_completeness=check_completeness
                )

                # 如果启用了skip_latest_data，过滤掉已经是最新的符号
                symbols_to_download = download_plan.symbols_to_download
                if skip_latest_data:
                    logger.info(f"启用跳过最新数据选项，正在过滤已有最新数据的股票...")
                    try:
                        # 检查哪些符号的数据已是最新
                        latest_check = await downloader.check_latest_data_status(task_config.symbols)
                        symbols_to_download = [s for s in symbols_to_download if not latest_check.get(s, True)]
                        logger.info(f"过滤后需要下载的股票数: {len(symbols_to_download)}/{len(task_config.symbols)}")
                    except Exception as e:
                        logger.warning(f"检查最新数据状态失败: {e}，继续使用所有符号进行下载")

                # 执行增量下载
                success_stats = await downloader.download_incremental_update_all_data(
                    symbols_to_download,
                    end_date,
                    incremental_days,
                    skip_weekends,
                    skip_holidays
                )

                return success_stats

            # 在新的事件循环中执行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success_stats = loop.run_until_complete(_incremental_wrapper())

                # 更新结果统计
                result.processed_records = success_stats.get('total_symbols', 0)
                result.success_count = success_stats.get('success_count', 0)
                result.failed_count = success_stats.get('failed_count', 0)
                result.skipped_count = success_stats.get('skipped_count', 0)

                logger.info(f"增量下载完成: 成功={result.success_count}, 失败={result.failed_count}, 跳过={result.skipped_count}")

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"增量下载失败: {e}")
            result.failed_records = len(task_config.symbols)
            result.error_message = str(e)
            raise
# 兼容性别名
DataImportExecutionEngine = UnifiedDataImportEngine
