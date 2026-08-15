from loguru import logger
#!/usr/bin/env python3
"""
数据导入任务执行引擎

负责执行数据导入任务，提供进度监控、状态更新和错误处理
"""

import asyncio
import threading
import time
import hashlib
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from .models import WriteTask, TaskExecutionStatus, TaskExecutionResult
from .database_writer import DatabaseWriterThread
from .import_config_manager import ImportConfigManager, ImportTaskConfig, ImportProgress, ImportStatus
from .intelligent_config_manager import (
    IntelligentConfigManager,
    ConfigOptimizationLevel,
    ConfigRecommendationType
)
from core.database.table_manager import TableType
from ..services.unified_data_manager import UnifiedDataManager, get_unified_data_manager
from ..real_data_provider import RealDataProvider
from ..services.ai_prediction_service import AIPredictionService, PredictionType
from ..services.deep_analysis_service import DeepAnalysisService, PerformanceMetric, AnomalyInfo
from ..performance.factorweave_performance_integration import FactorWeavePerformanceIntegrator
from ..performance.unified_monitor import get_performance_monitor
from ..services.enhanced_performance_bridge import EnhancedPerformanceBridge, get_enhanced_performance_bridge
from ..risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor, get_enhanced_risk_monitor
from ..services.distributed_service import DistributedService, NodeDiscovery, NodeInfo
from ..plugin_types import DataType
from optimization.auto_tuner import AlgorithmAutoTuner, TuningTask, OptimizationConfig
from optimization.algorithm_optimizer import PerformanceEvaluator
from ..services.enhanced_data_manager import DataQualityMonitor
from ..data.enhanced_models import DataQualityMetrics, DataQuality
from ..data_validator import ValidationLevel, ValidationResult
from ..events import EventBus, get_event_bus, EventPriority
from ..async_management.enhanced_async_manager import TaskPriority, ResourceRequirement
from ..performance.cache_manager import MultiLevelCacheManager, CacheLevel


class DataImportExecutionEngine(QObject):
    """
    数据导入任务执行引擎

    功能：
    1. 执行数据导入任务
    2. 监控任务进度
    3. 提供状态更新
    4. 错误处理和重试
    5. 任务调度和管理
    """

    # Qt信号
    task_started = pyqtSignal(str)  # 任务开始
    task_progress = pyqtSignal(str, float, str)  # 任务进度 (task_id, progress, message)
    task_completed = pyqtSignal(str, object)  # 任务完成 (task_id, result)
    task_failed = pyqtSignal(str, str)  # 任务失败 (task_id, error_message)
    task_cancelled = pyqtSignal(str)  # 修复：添加任务取消信号 (task_id)

    def __init__(self, config_manager: ImportConfigManager = None,
                 data_manager: UnifiedDataManager = None,
                 max_workers: int = 4,
                 enable_ai_optimization: bool = True,
                 enable_intelligent_config: bool = True,
                 enable_enhanced_performance_bridge: bool = True,
                 enable_enhanced_risk_monitoring: bool = True):
        super().__init__()

        # 配置管理器 - 支持智能配置
        if enable_intelligent_config:
            self.config_manager = config_manager or None
            self.enable_intelligent_config = True
        else:
            self.config_manager = config_manager or ImportConfigManager()
            self.enable_intelligent_config = False

        # 数据管理器 - 延迟初始化以避免阻塞
        self.data_manager = data_manager
        self._data_manager_initialized = data_manager is not None

        # 真实数据提供器 - 延迟初始化以避免阻塞
        self.real_data_provider = None
        self._real_data_provider_initialized = False

        # AI预测服务 - 延迟初始化以避免阻塞
        self.enable_ai_optimization = enable_ai_optimization
        self.ai_prediction_service = None
        self._ai_service_initialized = False
        # 优化：不在构造函数中初始化AI服务，改为懒加载
        # if enable_ai_optimization:
        #     self._init_ai_service()

        # 深度分析服务 - 延迟初始化以避免阻塞
        self.deep_analysis_service = None
        self._deep_analysis_initialized = False
        self.performance_integrator = None
        self._performance_integrator_initialized = False

        # 增强版性能数据桥接系统 - 延迟初始化
        self.enable_enhanced_performance_bridge = enable_enhanced_performance_bridge
        self.enhanced_performance_bridge = None
        self._enhanced_performance_bridge_initialized = False
        # 优化：不在构造函数中初始化，改为懒加载
        # if enable_enhanced_performance_bridge:
        #     self._init_enhanced_performance_bridge()

        # 增强版风险监控系统 - 延迟初始化
        self.enable_enhanced_risk_monitoring = enable_enhanced_risk_monitoring
        self.enhanced_risk_monitor = None
        self._enhanced_risk_monitor_initialized = False
        # 优化：不在构造函数中初始化，改为懒加载
        # if enable_enhanced_risk_monitoring:
        #     self._init_enhanced_risk_monitor()

        # 多级缓存系统 - 延迟初始化
        self.cache_manager = None
        self._cache_manager_initialized = False

        # 分布式服务系统 - 延迟初始化
        self.distributed_service = None
        self._distributed_service_initialized = False
        self.node_discovery = None
        self._node_discovery_initialized = False

        # 监控配置
        self.enable_performance_monitoring = True
        self.enable_anomaly_detection = True
        self.enable_intelligent_caching = True
        self.enable_distributed_execution = True
        self.enable_auto_tuning = True
        self.enable_data_quality_monitoring = True
        self.enable_enhanced_event_processing = True
        self.enable_enhanced_async_management = True

        # 线程池（需要在其他组件之前初始化）
        self.executor = ThreadPoolExecutor(max_workers=max_workers,
                                           thread_name_prefix="ImportEngine")

        # 自动调优系统 - 延迟初始化
        self.auto_tuner = None
        self._auto_tuner_initialized = False

        # 数据质量监控系统 - 延迟初始化
        self.data_quality_monitor = None
        self._data_quality_monitor_initialized = False

        # 数据库写入线程（单线程模式，解决DuckDB并发写入死锁）
        self.db_writer_thread = DatabaseWriterThread()
        self.db_writer_thread.start()
        logger.info("DatabaseWriterThread 已启动")

        # 基本面数据下载线程池（异步同步下载基本面数据）
        self.fundamental_executor = ThreadPoolExecutor(
            max_workers=10,
            thread_name_prefix="FundamentalDownloader"
        )
        logger.info("基本面数据下载线程池已初始化")

        # 优化2&3：质量评分缓存（数据源+日期→评分）
        self._quality_score_cache = {}  # key: f"{data_source}_{date}", value: score
        self._quality_cache_ttl = 3600  # 缓存1小时

        # 事件总线 - 延迟初始化
        self.event_bus = None
        self._event_bus_initialized = False

        # 增强异步管理器 - 延迟初始化
        self.enhanced_async_manager = None
        self._enhanced_async_manager_initialized = False

        # 任务管理
        self._running_tasks: Dict[str, Future] = {}
        self._task_results: Dict[str, TaskExecutionResult] = {}
        self._task_lock = threading.RLock()
        
        # 懒加载线程锁（确保线程安全的延迟初始化）
        self._lazy_init_lock = threading.RLock()

        # AI优化统计
        self._ai_optimization_stats = {
            'predictions_made': 0,
            'execution_time_saved': 0.0,
            'accuracy_improved': 0.0,
            'errors_prevented': 0
        }

        # 进度监控定时器
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_progress)
        self.progress_timer.start(1000)  # 每秒更新一次进度

        logger.info(f"数据导入执行引擎初始化完成 (AI优化: {'启用' if enable_ai_optimization else '禁用'}, 懒加载模式)")

    def _ensure_ai_service(self):
        """确保AI服务已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._ai_service_initialized and self.enable_ai_optimization:
                self._init_ai_service()

    def _ensure_deep_analysis_service(self):
        with self._lazy_init_lock:
            if not self._deep_analysis_initialized:
                try:
                    from core.containers import get_service_container
                    self.deep_analysis_service = get_service_container().resolve(DeepAnalysisService)
                    self._deep_analysis_initialized = True
                    logger.info("深度分析服务初始化成功(容器解析)")
                except Exception:
                    try:
                        self.deep_analysis_service = DeepAnalysisService()
                        self._deep_analysis_initialized = True
                        logger.info("深度分析服务初始化成功(后备)")
                    except Exception as e:
                        logger.warning(f"深度分析服务初始化失败: {e}")

    def _ensure_performance_integrator(self):
        """确保性能集成器已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._performance_integrator_initialized:
                try:
                    self.performance_integrator = FactorWeavePerformanceIntegrator()
                    self._performance_integrator_initialized = True
                    logger.info("性能集成器初始化成功")
                except Exception as e:
                    logger.warning(f"性能集成器初始化失败: {e}")

    def _ensure_enhanced_performance_bridge(self):
        """确保增强性能桥接已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._enhanced_performance_bridge_initialized and self.enable_enhanced_performance_bridge:
                self._init_enhanced_performance_bridge()

    def _ensure_enhanced_risk_monitor(self):
        """确保增强风险监控已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._enhanced_risk_monitor_initialized and self.enable_enhanced_risk_monitoring:
                self._init_enhanced_risk_monitor()

    def _ensure_cache_manager(self):
        """确保缓存管理器已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._cache_manager_initialized:
                self.cache_manager = self._init_cache_manager()

    def _ensure_distributed_service(self):
        """确保分布式服务已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._distributed_service_initialized:
                self.distributed_service = self._init_distributed_service()
                self._distributed_service_initialized = True

    def _ensure_node_discovery(self):
        """确保节点发现已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._node_discovery_initialized:
                self.node_discovery = self._init_node_discovery()
                self._node_discovery_initialized = True

    def _ensure_auto_tuner(self):
        """确保自动调优器已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._auto_tuner_initialized:
                self.auto_tuner = self._init_auto_tuner()
                self._auto_tuner_initialized = True

    def _ensure_data_quality_monitor(self):
        """确保数据质量监控已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._data_quality_monitor_initialized:
                self.data_quality_monitor = self._init_data_quality_monitor()
                self._data_quality_monitor_initialized = True

    def _ensure_event_bus(self):
        """确保事件总线已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._event_bus_initialized:
                self.event_bus = self._init_event_bus()
                self._event_bus_initialized = True

    def _ensure_enhanced_async_manager(self):
        """确保增强异步管理器已初始化（懒加载，线程安全）"""
        with self._lazy_init_lock:
            if not self._enhanced_async_manager_initialized:
                self.enhanced_async_manager = self._init_enhanced_async_manager()
                self._enhanced_async_manager_initialized = True

    def _init_ai_service(self):
        """初始化AI预测服务"""
        try:
            from core.containers import get_service_container
            container = get_service_container()
            self.ai_prediction_service = container.resolve(AIPredictionService)
            self._ai_service_initialized = True
            logger.info("AI预测服务初始化成功")
        except Exception as e:
            logger.warning(f"AI预测服务初始化失败: {e}")
            self.enable_ai_optimization = False
            self._ai_service_initialized = False

    def _predict_execution_time(self, task_config: ImportTaskConfig) -> Optional[float]:
        """使用AI预测任务执行时间"""
        if not self.enable_ai_optimization:
            return None
        
        # 确保AI服务已初始化
        self._ensure_ai_service()
        if not self._ai_service_initialized:
            return None

        try:
            # 构建预测输入数据
            prediction_data = {
                'symbols_count': len(task_config.symbols),
                'data_source': task_config.data_source,
                'frequency': task_config.frequency.value,
                'mode': task_config.mode.value,
                'batch_size': task_config.batch_size,
                'max_workers': task_config.max_workers
            }

            # 调用AI预测服务
            if self.ai_prediction_service:
                prediction_result = self.ai_prediction_service.predict(
                    PredictionType.EXECUTION_TIME,
                    prediction_data
                )

            if prediction_result and prediction_result.get('success'):
                predicted_time = prediction_result.get('predicted_time', 0)
                self._ai_optimization_stats['predictions_made'] += 1
                logger.info(f"AI预测任务执行时间: {predicted_time:.2f}秒")
                return predicted_time

        except Exception as e:
            logger.warning(f"AI执行时间预测失败: {e}")

        return None

    def _optimize_task_parameters(self, task_config: ImportTaskConfig) -> ImportTaskConfig:
        """使用AI优化任务参数"""
        if not self.enable_ai_optimization:
            return task_config
        
        # 确保AI服务已初始化
        self._ensure_ai_service()
        if not self._ai_service_initialized:
            return task_config

        try:
            # 获取历史执行数据用于优化
            historical_data = self._get_historical_execution_data(task_config)

            if historical_data and self.ai_prediction_service:
                # 使用AI预测最优参数
                optimization_result = self.ai_prediction_service.predict(
                    PredictionType.PARAMETER_OPTIMIZATION,
                    {
                        'current_config': task_config.to_dict(),
                        'historical_data': historical_data
                    }
                )

                if optimization_result and optimization_result.get('success'):
                    optimized_params = optimization_result.get('optimized_parameters', {})

                    # 应用优化建议
                    if 'batch_size' in optimized_params:
                        task_config.batch_size = optimized_params['batch_size']
                    if 'max_workers' in optimized_params:
                        task_config.max_workers = optimized_params['max_workers']

                    logger.info(f"AI优化任务参数: batch_size={task_config.batch_size}, max_workers={task_config.max_workers}")

        except Exception as e:
            logger.warning(f"AI参数优化失败: {e}")

        return task_config

    def _get_historical_execution_data(self, task_config: ImportTaskConfig) -> List[Dict]:
        """获取历史执行数据"""
        try:
            # 从配置管理器获取历史数据
            history = self.config_manager.get_history(limit=50)

            # 过滤相似任务的历史数据
            similar_tasks = []
            for record in history:
                if (record.get('data_source') == task_config.data_source and
                        record.get('frequency') == task_config.frequency.value):
                    similar_tasks.append(record)

            return similar_tasks

        except Exception as e:
            logger.warning(f"获取历史执行数据失败: {e}")
            return []

    def get_ai_optimization_stats(self) -> Dict[str, Any]:
        """获取AI优化统计信息"""
        return self._ai_optimization_stats.copy()

    def _init_cache_manager(self) -> Optional[MultiLevelCacheManager]:
        """初始化多级缓存管理器"""
        try:
            # MultiLevelCacheManager实际只支持简单的内存缓存
            # 参数：max_size (缓存条目数), ttl (生存时间秒数)
            cache_manager = MultiLevelCacheManager(
                max_size=1000,
                ttl=3600  # 60分钟 = 3600秒
            )

            logger.info("多级缓存管理器初始化成功")
            return cache_manager

        except Exception as e:
            logger.error(f"缓存管理器初始化失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None

    def _cache_task_data(self, task_id: str, data_type: str, data: Any) -> bool:
        """缓存任务数据"""
        if not self.enable_intelligent_caching:
            return False

        try:
            cache_key = f"task_{task_id}_{data_type}"

            # 确保缓存管理器已初始化
            self._ensure_cache_manager()
            
            # 使用多级缓存存储
            if self.cache_manager:
                success = self.cache_manager.set(cache_key, data)
                if success:
                    logger.debug(f"数据已缓存: {cache_key}")
                    return True

        except Exception as e:
            logger.warning(f"缓存数据失败: {e}")

        return False

    def _get_cached_task_data(self, task_id: str, data_type: str) -> Optional[Any]:
        """获取缓存的任务数据"""
        if not self.enable_intelligent_caching:
            return None

        try:
            cache_key = f"task_{task_id}_{data_type}"

            # 确保缓存管理器已初始化
            self._ensure_cache_manager()
            
            # 优先从多级缓存获取
            if self.cache_manager:
                data = self.cache_manager.get(cache_key)
                if data is not None:
                    logger.debug(f"从多级缓存命中: {cache_key}")
                    return data

        except Exception as e:
            logger.warning(f"获取缓存数据失败: {e}")

        return None

    def _cache_configuration_data(self, config: ImportTaskConfig) -> bool:
        """缓存配置数据"""
        if not self.enable_intelligent_caching:
            return False

        try:
            # 生成配置缓存键
            config_hash = hashlib.md5(
                f"{config.data_source}_{config.asset_type}_{config.frequency.value}".encode()
            ).hexdigest()[:8]

            cache_key = f"config_{config_hash}"

            # 缓存配置相关的优化数据
            cache_data = {
                'optimal_batch_size': config.batch_size,
                'optimal_workers': config.max_workers,
                'data_source': config.data_source,
                'frequency': config.frequency.value,
                'cached_at': datetime.now().isoformat()
            }

            # 确保缓存管理器已初始化
            self._ensure_cache_manager()
            
            if self.cache_manager:
                return self.cache_manager.set(cache_key, cache_data)

        except Exception as e:
            logger.warning(f"缓存配置数据失败: {e}")

        return False

    def _get_cached_configuration(self, config: ImportTaskConfig) -> Optional[Dict[str, Any]]:
        """获取缓存的配置数据"""
        if not self.enable_intelligent_caching:
            return None

        try:
            config_hash = hashlib.md5(
                f"{config.data_source}_{config.asset_type}_{config.frequency.value}".encode()
            ).hexdigest()[:8]

            cache_key = f"config_{config_hash}"

            # 确保缓存管理器已初始化
            self._ensure_cache_manager()
            
            if self.cache_manager:
                return self.cache_manager.get(cache_key)

        except Exception as e:
            logger.warning(f"获取缓存配置失败: {e}")

        return None

    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = {
            'intelligent_caching_enabled': self.enable_intelligent_caching,
            'cache_manager_available': self.cache_manager is not None
        }

        try:
            if self.cache_manager:
                # 获取多级缓存统计
                cache_stats = self.cache_manager.get_statistics()
                stats['multi_level_cache'] = cache_stats

        except Exception as e:
            logger.warning(f"获取缓存统计失败: {e}")
            stats['error'] = str(e)

        return stats

    def submit_distributed_import_task(self,
                                       task_config: 'ImportTaskConfig',
                                       priority: str = "normal") -> Optional[str]:
        """提交分布式导入任务"""
        try:
            # 确保分布式服务已初始化
            self._ensure_distributed_service()
            
            if not self.distributed_service:
                logger.warning("分布式服务未初始化，无法提交分布式任务")
                return None

            # 检查是否为增强版分布式服务
            if hasattr(self.distributed_service, 'submit_enhanced_task'):
                from ..async_management.enhanced_async_manager import TaskPriority

                # 转换优先级
                priority_map = {
                    "critical": TaskPriority.CRITICAL,
                    "high": TaskPriority.HIGH,
                    "normal": TaskPriority.NORMAL,
                    "low": TaskPriority.LOW,
                    "background": TaskPriority.BACKGROUND
                }

                task_priority = priority_map.get(priority, TaskPriority.NORMAL)

                # 估算资源需求
                cpu_requirement = min(4.0, task_config.max_workers)
                memory_requirement = max(512, task_config.batch_size * 2)  # MB

                # 提交增强版任务
                task_id = self.distributed_service.submit_enhanced_task(
                    task_type="data_import",
                    task_data={
                        "config": task_config.to_dict(),
                        "symbols": task_config.symbols,
                        "data_source": task_config.data_source
                    },
                    priority=task_priority,
                    cpu_requirement=cpu_requirement,
                    memory_requirement=memory_requirement,
                    timeout=3600,  # 1小时超时
                    affinity_rules={
                        "data_source": task_config.data_source
                    }
                )

                logger.info(f"提交增强版分布式导入任务: {task_id}")
                return task_id
            else:
                # 使用原始分布式服务
                task_id = self.distributed_service.submit_analysis_task(
                    stock_code=",".join(task_config.symbols[:5]),  # 限制长度
                    analysis_type="import"
                )

                logger.info(f"提交原始分布式导入任务: {task_id}")
                return task_id

        except Exception as e:
            logger.error(f"提交分布式导入任务失败: {e}")
            return None

    def get_distributed_service_status(self) -> Dict[str, Any]:
        """获取分布式服务状态"""
        try:
            # 确保分布式服务已初始化
            self._ensure_distributed_service()
            
            if not self.distributed_service:
                return {"error": "分布式服务未初始化"}

            # 检查是否为增强版分布式服务
            if hasattr(self.distributed_service, 'get_service_status'):
                return self.distributed_service.get_service_status()
            else:
                # 原始分布式服务的基本状态
                return {
                    "service_running": self.distributed_service.running,
                    "service_type": "original"
                }

        except Exception as e:
            logger.error(f"获取分布式服务状态失败: {e}")
            return {"error": str(e)}

    def _init_distributed_service(self) -> Optional[DistributedService]:
        """初始化分布式服务"""
        try:
            # 使用ServiceContainer中的DistributedService
            from ..containers import get_service_container

            container = get_service_container()

            if container.is_registered(DistributedService):
                distributed_service = container.resolve(DistributedService)
                logger.info("使用ServiceContainer中的DistributedService")
                return distributed_service

            # Fallback：创建新实例
            logger.info("ServiceContainer中无DistributedService，创建新实例")
            distributed_service = DistributedService()
            distributed_service.start_service()

            logger.info("分布式服务初始化成功")
            return distributed_service

        except ImportError:
            # 回退到原始分布式服务
            logger.warning("增强版分布式服务不可用，使用原始版本")
            try:
                distributed_service = DistributedService(discovery_port=8888)
                distributed_service.start_service()
                logger.info("原始分布式服务初始化成功")
                return distributed_service
            except Exception as e:
                logger.error(f"原始分布式服务初始化失败: {e}")
                return None
        except Exception as e:
            logger.error(f"增强版分布式服务初始化失败: {e}")
            return None

    def _init_node_discovery(self) -> Optional[NodeDiscovery]:
        """初始化节点发现服务"""
        try:
            node_discovery = NodeDiscovery(discovery_port=8888)

            # 添加节点发现回调
            node_discovery.add_discovery_callback(self._on_node_discovered)

            # 启动节点发现
            node_discovery.start_discovery()

            logger.info("节点发现服务初始化成功")
            return node_discovery

        except Exception as e:
            logger.error(f"节点发现服务初始化失败: {e}")
            return None

    def _on_node_discovered(self, node_info: NodeInfo):
        """节点发现回调"""
        try:
            logger.info(f"发现新节点: {node_info.node_id} ({node_info.address}:{node_info.port})")

            # 检查节点是否支持数据导入服务
            if 'import_execution' in node_info.services:
                logger.info(f"节点 {node_info.node_id} 支持分布式数据导入")

                # 可以在这里添加负载均衡逻辑
                self._register_distributed_node(node_info)

        except Exception as e:
            logger.error(f"处理节点发现失败: {e}")

    def _register_distributed_node(self, node_info: NodeInfo):
        """注册分布式节点"""
        try:
            if not hasattr(self, '_distributed_nodes'):
                self._distributed_nodes = {}

            self._distributed_nodes[node_info.node_id] = {
                'node_info': node_info,
                'last_seen': datetime.now(),
                'task_count': 0,
                'available': True
            }

            logger.info(f"已注册分布式节点: {node_info.node_id}")

        except Exception as e:
            logger.error(f"注册分布式节点失败: {e}")

    def _can_distribute_task(self, task_config: ImportTaskConfig) -> bool:
        """检查任务是否可以分布式执行"""
        if not self.enable_distributed_execution:
            return False

        try:
            # 确保分布式服务已初始化
            self._ensure_distributed_service()
            
            # 使用真实的DistributedService检查节点
            if not self.distributed_service:
                logger.debug("分布式服务未初始化")
                return False

            # 获取可用节点列表
            nodes_status = self.distributed_service.get_all_nodes_status()

            if not nodes_status:
                logger.debug("无可用分布式节点")
                return False

            available_nodes = [
                node for node in nodes_status
                if node.get('status') in ['active', 'idle'] and node.get('current_tasks', 0) < 3
            ]

            # 只有当任务足够大且有可用节点时才分布式执行
            symbol_count = len(task_config.symbols)
            can_distribute = symbol_count >= 100 and len(available_nodes) > 0

            if can_distribute:
                logger.info(f"任务可分布式执行: {symbol_count}个股票，{len(available_nodes)}个可用节点")

            return can_distribute

        except Exception as e:
            logger.error(f"检查分布式执行条件失败: {e}")
            return False

    def _distribute_task(self, task_config: ImportTaskConfig) -> bool:
        """分布式执行任务"""
        if not self._can_distribute_task(task_config):
            return False

        try:
            # 确保分布式服务已初始化
            self._ensure_distributed_service()
            
            # 使用真实的DistributedService提交任务
            logger.info(f"开始分布式执行任务: {task_config.task_id}")

            # 构造导入配置
            import_config = {
                "symbols": task_config.symbols,
                "data_source": task_config.data_source,
                "start_date": task_config.start_date,
                "end_date": task_config.end_date,
                "frequency": task_config.frequency,
                "asset_type": task_config.asset_type.value if hasattr(task_config.asset_type, 'value') else str(task_config.asset_type),
                "batch_size": task_config.batch_size,
                "parallel_workers": task_config.max_workers
            }

            # 提交数据导入任务到分布式服务
            task_id = self.distributed_service.submit_data_import_task(import_config)

            if task_id:
                logger.info(f"成功提交分布式任务: {task_id}")

                # 记录任务ID用于后续跟踪
                if not hasattr(self, '_distributed_task_ids'):
                    self._distributed_task_ids = {}
                self._distributed_task_ids[task_config.task_id] = task_id

                return True
            else:
                logger.warning("分布式任务提交失败，无任务ID返回")
                return False

        except Exception as e:
            logger.error(f"分布式执行任务失败: {e}")
            return False

    def _select_best_node(self) -> Optional[Dict[str, Any]]:
        """选择最佳分布式节点"""
        try:
            if not hasattr(self, '_distributed_nodes'):
                return None

            available_nodes = [
                node for node in self._distributed_nodes.values()
                if node['available'] and node['task_count'] < 3
            ]

            if not available_nodes:
                return None

            # 选择任务数最少的节点
            best_node = min(available_nodes, key=lambda x: x['task_count'])
            return best_node

        except Exception as e:
            logger.error(f"选择最佳节点失败: {e}")
            return None

    def _split_task(self, task_config: ImportTaskConfig) -> List[ImportTaskConfig]:
        """分割任务为子任务"""
        try:
            subtasks = []
            symbols = task_config.symbols
            chunk_size = max(50, len(symbols) // 4)  # 每个子任务至少50个股票

            for i in range(0, len(symbols), chunk_size):
                chunk_symbols = symbols[i:i + chunk_size]

                # 创建子任务配置
                subtask_config = ImportTaskConfig(
                    task_id=f"{task_config.task_id}_subtask_{i//chunk_size}",
                    name=f"{task_config.name}_子任务_{i//chunk_size}",
                    symbols=chunk_symbols,
                    data_source=task_config.data_source,
                    asset_type=task_config.asset_type,
                    frequency=task_config.frequency,
                    mode=task_config.mode,
                    batch_size=task_config.batch_size,
                    max_workers=min(task_config.max_workers, 2)  # 子任务使用较少线程
                )

                subtasks.append(subtask_config)

            logger.info(f"任务已分割为 {len(subtasks)} 个子任务")
            return subtasks

        except Exception as e:
            logger.error(f"分割任务失败: {e}")
            return []

    def _send_subtask_to_node(self, subtask: ImportTaskConfig, node: Dict[str, Any]) -> bool:
        try:
            node_info = node['node_info']
            logger.warning(f"分布式任务分发引擎不可用，子任务 {subtask.task_id} 无法发送到节点 {node_info.node_id}。请配置分布式服务。")
            return False

        except Exception as e:
            logger.error(f"发送子任务到节点失败: {e}")
            return False

    def get_distributed_status(self) -> Dict[str, Any]:
        """获取分布式服务状态"""
        status = {
            'distributed_execution_enabled': self.enable_distributed_execution,
            'distributed_service_available': self.distributed_service is not None,
            'node_discovery_available': self.node_discovery is not None,
            'discovered_nodes': 0,
            'available_nodes': 0,
            'service_type': 'unknown'
        }

        try:
            # 获取增强版分布式服务状态
            enhanced_status = self.get_distributed_service_status()
            if 'error' not in enhanced_status:
                status.update(enhanced_status)
                status['service_type'] = 'enhanced' if 'load_balancing_strategy' in enhanced_status else 'original'
            if hasattr(self, '_distributed_nodes'):
                status['discovered_nodes'] = len(self._distributed_nodes)
                status['available_nodes'] = len([
                    node for node in self._distributed_nodes.values()
                    if node['available']
                ])

                status['nodes_detail'] = [
                    {
                        'node_id': node_id,
                        'address': node['node_info'].address,
                        'port': node['node_info'].port,
                        'task_count': node['task_count'],
                        'available': node['available'],
                        'last_seen': node['last_seen'].isoformat()
                    }
                    for node_id, node in self._distributed_nodes.items()
                ]

        except Exception as e:
            logger.error(f"获取分布式状态失败: {e}")
            status['error'] = str(e)

        return status

    def _register_import_event_handlers(self, event_bus: EventBus):
        """注册数据导入相关的事件处理器"""
        try:
            event_bus.subscribe("import_task_started", self._handle_import_task_started_event)
            event_bus.subscribe("import_task_progress", self._handle_import_task_progress_event)
            event_bus.subscribe("import_task_completed", self._handle_import_task_completed_event)
            event_bus.subscribe("import_task_failed", self._handle_import_task_failed_event)

            logger.info("数据导入事件处理器注册完成")

        except Exception as e:
            logger.error(f"注册事件处理器失败: {e}")

    def _handle_import_task_started_event(self, event):
        """处理导入任务开始事件"""
        try:
            task_id = getattr(event, 'task_id', None) or (event.data.get('task_id') if hasattr(event, 'data') else None)
            task_name = getattr(event, 'task_name', 'Unknown') or (event.data.get('task_name') if hasattr(event, 'data') else 'Unknown')

            logger.info(f"事件处理 - 导入任务开始: {task_name} ({task_id})")

            self.task_started.emit(task_id, task_name)

        except Exception as e:
            logger.error(f"处理导入任务开始事件失败: {e}")

    def _handle_import_task_progress_event(self, event):
        """处理导入任务进度事件"""
        try:
            task_id = getattr(event, 'task_id', None) or (event.data.get('task_id') if hasattr(event, 'data') else None)
            progress = getattr(event, 'progress', 0) or (event.data.get('progress') if hasattr(event, 'data') else 0)
            status = getattr(event, 'status', 'unknown') or (event.data.get('status') if hasattr(event, 'data') else 'unknown')

            self.progress_updated.emit(task_id, progress, status)

        except Exception as e:
            logger.error(f"处理导入任务进度事件失败: {e}")

    def _handle_import_task_completed_event(self, event):
        """处理导入任务完成事件"""
        try:
            task_id = getattr(event, 'task_id', None) or (event.data.get('task_id') if hasattr(event, 'data') else None)
            task_name = getattr(event, 'task_name', 'Unknown') or (event.data.get('task_name') if hasattr(event, 'data') else 'Unknown')
            execution_time = getattr(event, 'execution_time', 0) or (event.data.get('execution_time') if hasattr(event, 'data') else 0)
            result = getattr(event, 'result', None) or (event.data.get('result') if hasattr(event, 'data') else None)

            logger.info(f"事件处理 - 导入任务完成: {task_name} ({execution_time:.2f}s)")

            self.task_completed.emit(task_id, result)

        except Exception as e:
            logger.error(f"处理导入任务完成事件失败: {e}")

    def _handle_import_task_failed_event(self, event):
        """处理导入任务失败事件"""
        try:
            task_id = getattr(event, 'task_id', None) or (event.data.get('task_id') if hasattr(event, 'data') else None)
            task_name = getattr(event, 'task_name', 'Unknown') or (event.data.get('task_name') if hasattr(event, 'data') else 'Unknown')
            error = getattr(event, 'error', 'Unknown error') or (event.data.get('error') if hasattr(event, 'data') else 'Unknown error')

            logger.error(f"事件处理 - 导入任务失败: {task_name} - {error}")

            self.task_failed.emit(task_id, error)

        except Exception as e:
            logger.error(f"处理导入任务失败事件失败: {e}")

    def submit_enhanced_async_task(self,
                                   func: Callable,
                                   *args,
                                   task_name: str = None,
                                   priority: TaskPriority = TaskPriority.NORMAL,
                                   timeout: float = None,
                                   resource_requirements: ResourceRequirement = None,
                                   **kwargs) -> Optional[str]:
        """提交增强版异步任务"""
        # 确保增强异步管理器已初始化
        self._ensure_enhanced_async_manager()
        
        if not self.enable_enhanced_async_management or not self.enhanced_async_manager:
            logger.warning("增强版异步管理器未启用或未初始化")
            return None

        try:
            task_id = self.enhanced_async_manager.submit_task(
                func=func,
                *args,
                name=task_name or getattr(func, '__name__', 'unnamed_task'),
                priority=priority,
                timeout=timeout,
                resource_requirements=resource_requirements or ResourceRequirement(),
                **kwargs
            )

            return task_id

        except Exception as e:
            logger.error(f"提交增强版异步任务失败: {e}")
            return None

    def publish_import_event(self,
                             event_name: str,
                             event_data: Dict[str, Any],
                             priority: EventPriority = EventPriority.NORMAL,
                             correlation_id: str = None):
        """发布导入相关事件"""
        # 确保事件总线已初始化
        self._ensure_event_bus()
        
        if not self.enable_enhanced_event_processing or not self.event_bus:
            return

        try:
            self.event_bus.publish(
                event_name,
                **event_data,
                priority=priority
            )
        except Exception as e:
            logger.error(f"发布导入事件失败: {e}")

    def get_enhanced_processing_stats(self) -> Dict[str, Any]:
        """获取增强版处理统计信息"""
        stats = {}

        # 确保事件总线已初始化
        self._ensure_event_bus()
        if self.event_bus:
            stats['event_bus'] = self.event_bus.get_stats()

        # 确保增强异步管理器已初始化
        self._ensure_enhanced_async_manager()
        if self.enhanced_async_manager:
            stats['async_manager'] = self.enhanced_async_manager.get_stats()

        return stats

    def get_database_writer_stats(self) -> Dict[str, Any]:
        """
        获取数据库写入线程统计信息

        Returns:
            统计字典，包含：
            - queue_size: 队列当前大小
            - queue_peak: 队列峰值大小
            - total_writes: 总写入任务次数
            - failed_writes: 失败写入任务次数
            - total_records: 成功落库记录总数
            - failed_records: 落库失败记录总数
            - merge_buffer_size: 合并缓冲区大小
            - is_stopped: 是否已停止
        """
        if hasattr(self, 'db_writer_thread'):
            return self.db_writer_thread.get_stats()
        else:
            return {
                'queue_size': 0,
                'queue_peak': 0,
                'total_writes': 0,
                'failed_writes': 0,
                'total_records': 0,
                'failed_records': 0,
                'merge_buffer_size': 0,
                'is_stopped': True
            }

    def get_tongdaxin_ip_stats(self) -> Dict[str, Any]:
        """
        获取通达信IP使用统计信息（用于监控）

        Returns:
            IP统计信息字典，包含：
            - total_connections: 总连接数
            - active_servers: 活跃服务器数
            - healthy_ips: 健康IP数
            - limited_ips: 限流IP数
            - failed_ips: 故障IP数
            - ip_stats: IP详细统计列表
        """
        try:
            # 从UnifiedDataManager获取通达信插件
            from core.services.unified_data_manager import get_unified_data_manager
            unified_manager = get_unified_data_manager()

            if not unified_manager:
                logger.debug("IP监控: UnifiedDataManager不可用")
                return {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': 'UnifiedDataManager不可用'
                }

            # 获取插件中心 - 通过_uni_plugin_manager访问
            # UnifiedDataManager没有直接的plugin_center属性，需要通过_uni_plugin_manager访问
            uni_plugin_manager = getattr(unified_manager, '_uni_plugin_manager', None)
            if not uni_plugin_manager:
                # 尝试通过get_uni_plugin_manager()方法获取
                if hasattr(unified_manager, 'get_uni_plugin_manager'):
                    uni_plugin_manager = unified_manager.get_uni_plugin_manager()

            if not uni_plugin_manager:
                logger.debug("IP监控: UniPluginDataManager不可用")
                return {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': 'UniPluginDataManager不可用'
                }

            # 从UniPluginDataManager获取plugin_center
            plugin_center = getattr(uni_plugin_manager, 'plugin_center', None)
            if not plugin_center:
                logger.debug("IP监控: 插件中心不可用")
                return {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': '插件中心不可用'
                }

            # 查找通达信插件
            tongdaxin_plugin_id = 'data_sources.stock.tongdaxin_plugin'
            plugin = plugin_center.get_plugin(tongdaxin_plugin_id)

            if not plugin:
                logger.debug(f"IP监控: 通达信插件未找到 (ID: {tongdaxin_plugin_id})")
                return {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': f'通达信插件未找到 (ID: {tongdaxin_plugin_id})'
                }

            # 获取连接池信息
            connection_pool = getattr(plugin, 'connection_pool', None)
            use_connection_pool = getattr(plugin, 'use_connection_pool', False)
            server_list = getattr(plugin, 'server_list', None)
            plugin_state = getattr(plugin, 'plugin_state', None)

            # 修复：如果连接池未初始化，尝试触发异步连接（如果插件状态允许）
            if use_connection_pool and not connection_pool:
                # 检查插件状态
                from plugins.plugin_interface import PluginLifecycle
                if plugin_state == PluginLifecycle.INITIALIZED:
                    # 插件已初始化但未连接，尝试触发异步连接
                    logger.debug("IP监控: 连接池未初始化，尝试触发异步连接...")
                    try:
                        if hasattr(plugin, 'connect_async'):
                            connection_future = plugin.connect_async()
                            if connection_future:
                                logger.debug("IP监控: 已触发异步连接，连接池将在后台初始化")
                                return {
                                    'total_connections': 0,
                                    'active_servers': 0,
                                    'healthy_ips': 0,
                                    'limited_ips': 0,
                                    'failed_ips': 0,
                                    'ip_stats': [],
                                    'error_message': '连接池正在初始化中，请稍候...'
                                }
                    except Exception as e:
                        logger.debug(f"IP监控: 触发异步连接失败: {e}")

                # 如果正在连接中，显示连接中状态
                if plugin_state == PluginLifecycle.CONNECTING:
                    logger.debug("IP监控: 连接池正在初始化中...")
                    return {
                        'total_connections': 0,
                        'active_servers': 0,
                        'healthy_ips': 0,
                        'limited_ips': 0,
                        'failed_ips': 0,
                        'ip_stats': [],
                        'error_message': '连接池正在初始化中，请稍候...'
                    }

                # 其他情况，显示未初始化提示
                logger.debug("IP监控: 连接池模式已启用但连接池未初始化")
                return {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': '连接池未初始化（请先连接数据源以初始化连接池）'
                }

            if not connection_pool:
                logger.debug(f"IP监控: 连接池不可用 (use_connection_pool={use_connection_pool}, has_server_list={bool(server_list)})")
                return {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': f'连接池不可用 (use_connection_pool={use_connection_pool}, 连接池未初始化或初始化失败)'
                }

            # 获取连接池信息
            pool_info = connection_pool.get_connection_pool_info()

            if not pool_info:
                logger.debug("IP监控: 连接池信息为空")
                return {
                    'total_connections': 0,
                    'active_servers': 0,
                    'healthy_ips': 0,
                    'limited_ips': 0,
                    'failed_ips': 0,
                    'ip_stats': [],
                    'error_message': '连接池信息为空'
                }

            # 转换IP统计为列表格式
            ip_stats_dict = pool_info.get('ip_stats', {})
            ip_stats_list = []

            if isinstance(ip_stats_dict, dict):
                for server_key, stats in ip_stats_dict.items():
                    if not isinstance(stats, dict):
                        logger.debug(f"IP监控: 跳过无效的stats数据 (server_key={server_key}, type={type(stats)})")
                        continue

                    # 修复：确保所有字段都有有效值，避免显示空白
                    ip = stats.get('ip', '')
                    port = stats.get('port', '')
                    use_count = stats.get('use_count', 0) or 0
                    success_count = stats.get('success_count', 0) or 0
                    failure_count = stats.get('failure_count', 0) or 0
                    avg_response_time = stats.get('avg_response_time', 0.0) or 0.0
                    status = stats.get('status', 'healthy') or 'healthy'
                    success_rate = stats.get('success_rate', 0.0) or 0.0

                    # 修复：如果IP或端口为空，尝试从server_key解析
                    if not ip or not port:
                        try:
                            if ':' in server_key:
                                parsed_ip, parsed_port = server_key.split(':', 1)
                                ip = ip or parsed_ip.strip()
                                port = port or parsed_port.strip()
                        except Exception as e:
                            logger.debug(f"IP监控: 从server_key解析IP/端口失败: {server_key}, {e}")

                    # 修复：如果数据仍然不完整，记录警告并跳过
                    if not ip:
                        logger.debug(f"IP监控: IP地址为空，跳过此条记录 (server_key={server_key})")
                        continue

                    ip_stats_list.append({
                        'ip': ip,
                        'port': port,
                        'use_count': use_count,
                        'success_count': success_count,
                        'failure_count': failure_count,
                        'avg_response_time': avg_response_time,
                        'status': status,
                        'success_rate': success_rate,
                        'last_used': stats.get('last_used')
                    })

            result = {
                'total_connections': pool_info.get('total_connections', 0),
                'active_servers': pool_info.get('active_servers', 0),
                'healthy_ips': pool_info.get('healthy_ips', 0),
                'limited_ips': pool_info.get('limited_ips', 0),
                'failed_ips': pool_info.get('failed_ips', 0),
                'ip_stats': ip_stats_list
            }

            logger.debug(f"IP监控: 获取到 {len(ip_stats_list)} 个IP统计，健康IP: {result['healthy_ips']}, 总连接: {result['total_connections']}")
            return result

        except Exception as e:
            logger.error(f"获取通达信IP统计信息失败: {e}")
            return {
                'total_connections': 0,
                'active_servers': 0,
                'healthy_ips': 0,
                'limited_ips': 0,
                'failed_ips': 0,
                'ip_stats': []
            }

    def _init_auto_tuner(self) -> Optional[AlgorithmAutoTuner]:
        """初始化自动调优器"""
        try:
            # 确保PerformanceEvaluator可用
            try:
                from optimization.algorithm_optimizer import PerformanceEvaluator
                evaluator = PerformanceEvaluator(debug_mode=False)
                logger.debug("PerformanceEvaluator初始化成功")
            except Exception as eval_error:
                logger.warning(f"PerformanceEvaluator初始化失败: {eval_error}")
                # 继续初始化AutoTuner，它可能有内置的评估器

            # 配置自动调优器
            max_workers = min(4, self.executor._max_workers)  # 使用较少的工作线程
            auto_tuner = AlgorithmAutoTuner(max_workers=max_workers, debug_mode=False)

            logger.info("自动调优器初始化成功")
            return auto_tuner

        except Exception as e:
            logger.error(f"自动调优器初始化失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None

    def _auto_tune_task_parameters(self, task_config: ImportTaskConfig) -> ImportTaskConfig:
        """使用AutoTuner自动调优任务参数"""
        if not self.enable_auto_tuning or not self.auto_tuner:
            return task_config

        try:
            logger.info("开始AutoTuner自动调优...")

            # 创建调优配置
            tuning_config = OptimizationConfig(
                target_metric='execution_time',
                method='bayesian',  # 参数名是'method'不是'optimization_method'
                max_iterations=10
                # OptimizationConfig不支持early_stopping参数
            )

            # 创建调优任务
            tuning_task = TuningTask(
                pattern_name=f"import_task_{task_config.data_source}",
                priority=1,
                config=tuning_config
            )

            # 定义参数空间
            parameter_space = {
                'batch_size': {
                    'type': 'integer',
                    'min': 500,
                    'max': 5000,
                    'current': task_config.batch_size
                },
                'max_workers': {
                    'type': 'integer',
                    'min': 2,
                    'max': min(8, self.executor._max_workers),
                    'current': task_config.max_workers
                }
            }

            # 执行自动调优
            tuning_result = self._execute_auto_tuning(tuning_task, parameter_space, task_config)

            if tuning_result and tuning_result.get('success'):
                optimized_params = tuning_result.get('optimized_parameters', {})

                # 应用优化参数
                if 'batch_size' in optimized_params:
                    task_config.batch_size = optimized_params['batch_size']
                if 'max_workers' in optimized_params:
                    task_config.max_workers = optimized_params['max_workers']

                logger.info(f" AutoTuner优化完成: batch_size={task_config.batch_size}, max_workers={task_config.max_workers}")
                logger.info(f" 预期性能提升: {tuning_result.get('improvement_percentage', 0):.1f}%")
            else:
                logger.warning("AutoTuner调优未找到更优参数，保持原配置")

        except Exception as e:
            logger.error(f"AutoTuner调优失败: {e}")

        return task_config

    def _execute_auto_tuning(self, tuning_task: TuningTask, parameter_space: Dict[str, Any],
                             base_config: ImportTaskConfig) -> Optional[Dict[str, Any]]:
        """执行自动调优"""
        try:
            # 定义目标函数
            def objective_function(params: Dict[str, Any]) -> float:
                """调优目标函数：最小化执行时间"""
                try:
                    # 创建测试配置
                    test_config = ImportTaskConfig(
                        task_id=f"tuning_test_{int(time.time())}",
                        name="调优测试任务",
                        symbols=base_config.symbols[:min(10, len(base_config.symbols))],  # 使用少量股票测试
                        data_source=base_config.data_source,
                        asset_type=base_config.asset_type,
                        data_type=base_config.data_type,  # 添加必需的data_type参数
                        frequency=base_config.frequency,
                        mode=base_config.mode,
                        batch_size=params.get('batch_size', base_config.batch_size),
                        max_workers=params.get('max_workers', base_config.max_workers)
                    )

                    # 模拟执行并测量性能
                    start_time = time.time()

                    # 这里应该执行实际的数据导入测试
                    # 为了演示，我们使用简化的性能估算
                    estimated_time = self._estimate_execution_time(test_config)

                    execution_time = time.time() - start_time + estimated_time

                    logger.debug(f"调优测试 - batch_size: {params['batch_size']}, "
                                 f"max_workers: {params['max_workers']}, "
                                 f"执行时间: {execution_time:.2f}秒")

                    return execution_time

                except Exception as e:
                    logger.error(f"调优目标函数执行失败: {e}")
                    return float('inf')

            # 使用AutoTuner执行优化
            best_params = None
            best_score = float('inf')

            # 网格搜索优化（简化版）
            batch_sizes = [500, 1000, 2000, 3000, 5000]
            worker_counts = [2, 3, 4, 6, 8]

            for batch_size in batch_sizes:
                if batch_size < parameter_space['batch_size']['min'] or batch_size > parameter_space['batch_size']['max']:
                    continue

                for workers in worker_counts:
                    if workers < parameter_space['max_workers']['min'] or workers > parameter_space['max_workers']['max']:
                        continue

                    params = {'batch_size': batch_size, 'max_workers': workers}
                    score = objective_function(params)

                    if score < best_score:
                        best_score = score
                        best_params = params

            if best_params:
                # 计算改进百分比
                current_params = {
                    'batch_size': parameter_space['batch_size']['current'],
                    'max_workers': parameter_space['max_workers']['current']
                }
                current_score = objective_function(current_params)

                improvement = max(0, (current_score - best_score) / current_score * 100)

                return {
                    'success': True,
                    'optimized_parameters': best_params,
                    'improvement_percentage': improvement,
                    'best_score': best_score,
                    'current_score': current_score
                }
            else:
                return {'success': False, 'reason': '未找到更优参数'}

        except Exception as e:
            logger.error(f"执行自动调优失败: {e}")
            return None

    def _estimate_execution_time(self, config: ImportTaskConfig) -> float:
        """估算执行时间（用于调优）"""
        try:
            # 基于配置参数的简单时间估算模型
            symbol_count = len(config.symbols)
            batch_size = config.batch_size
            max_workers = config.max_workers

            # 基础时间（秒）
            base_time = symbol_count * 0.1  # 每个股票0.1秒基础时间

            # 批次大小影响
            batch_factor = 1.0 + (1000 - batch_size) / 1000 * 0.3  # 批次越小，开销越大

            # 并发影响
            worker_factor = 1.0 / min(max_workers, symbol_count)  # 工作线程数影响

            estimated_time = base_time * batch_factor * worker_factor

            return max(0.1, estimated_time)  # 最小0.1秒

        except Exception as e:
            logger.error(f"估算执行时间失败: {e}")
            return 1.0  # 默认1秒

    def get_auto_tuning_status(self) -> Dict[str, Any]:
        """获取自动调优状态"""
        status = {
            'auto_tuning_enabled': self.enable_auto_tuning,
            'auto_tuner_available': self.auto_tuner is not None
        }

        try:
            # 确保自动调优器已初始化
            self._ensure_auto_tuner()
            
            if self.auto_tuner:
                # 获取调优器状态
                tuner_status = self.auto_tuner.get_status()
                status.update({
                    'active_tasks': tuner_status.get('active_tasks', 0),
                    'completed_tasks': tuner_status.get('completed_tasks', 0),
                    'failed_tasks': tuner_status.get('failed_tasks', 0),
                    'total_improvement': tuner_status.get('total_improvement', 0)
                })

        except Exception as e:
            logger.error(f"获取自动调优状态失败: {e}")
            status['error'] = str(e)

        return status

    def _init_data_quality_monitor(self) -> Optional[DataQualityMonitor]:
        """初始化数据质量监控器"""
        try:
            data_quality_monitor = DataQualityMonitor()
            logger.info("数据质量监控器初始化成功")
            return data_quality_monitor

        except Exception as e:
            logger.error(f"数据质量监控器初始化失败: {e}")
            return None

    def _validate_imported_data(self, task_id: str, data: pd.DataFrame,
                                data_source: str, data_type: str = 'kdata', strict_validation: bool = False) -> ValidationResult:
        """验证导入的数据质量
        
        Args:
            task_id: 任务ID
            data: 数据DataFrame
            data_source: 数据源
            data_type: 数据类型
            strict_validation: 是否启用严格验证模式（用于回测和实盘）
        """
        logger.info(f"[数据质量验证] 开始验证 - 任务: {task_id}, 数据源: {data_source}, 类型: {data_type}, 记录数: {len(data) if not data.empty else 0}, 严格模式: {strict_validation}")

        if not self.enable_data_quality_monitoring or not self.data_quality_monitor:
            logger.debug(f"[数据质量验证] 质量监控未启用，跳过验证")
            return ValidationResult(
                is_valid=True,
                quality_score=0.8,
                quality_level=DataQuality.GOOD,
                errors=[],
                warnings=[],
                suggestions=[],
                metrics={},
                validation_time=datetime.now()
            )

        try:
            logger.info(f" 开始数据质量验证: {task_id}")

            # 关键修复：确保datetime是列而不是索引
            # 解决"'datetime' is both an index level and a column label"错误
            if data.index.name == 'datetime' or isinstance(data.index, pd.DatetimeIndex):
                logger.debug("[数据质量验证] 检测到datetime被设置为索引，将其转换回列")
                data = data.reset_index(drop=False)
                if 'index' in data.columns:
                    data = data.drop('index', axis=1)
                if data.index.name is not None:
                    data = data.reset_index(drop=True)

            # 确保datetime列存在且是datetime类型
            if 'datetime' not in data.columns:
                logger.warning("[数据质量验证] 数据中没有datetime列，尝试从其他字段恢复")
                if 'date' in data.columns:
                    data['datetime'] = pd.to_datetime(data['date'])
                else:
                    logger.error("[数据质量验证] 无法找到datetime或date列")
                    return ValidationResult(
                        is_valid=False,
                        quality_score=0.0,
                        quality_level=DataQuality.POOR,
                        errors=["缺少datetime字段"],
                        warnings=[],
                        suggestions=["检查数据源是否提供了时间字段"],
                        metrics={},
                        validation_time=datetime.now()
                    )
            else:
                data['datetime'] = pd.to_datetime(data['datetime'])

            # 智能识别数据用途（一次性调用，避免重复计算）
            # 这个值将被用于质量评分计算和后续的记录质量指标
            data_usage = self._infer_data_usage(data, task_id)

            # 优化2&3：检查缓存（相同数据源+日期）
            cache_key = f"{data_source}_{datetime.now().date().isoformat()}"

            if cache_key in self._quality_score_cache:
                cached_data = self._quality_score_cache[cache_key]
                # 检查缓存是否过期
                if (datetime.now() - cached_data['timestamp']).seconds < self._quality_cache_ttl:
                    quality_score = cached_data['score']
                    logger.info(f"[质量评分缓存] 使用缓存评分: {quality_score:.3f} (数据源: {data_source})")
                    # 即使使用缓存，也要检查是否需要增量更新
                    if 'symbol' in data.columns:
                        new_symbols = set(data['symbol'].unique())
                        cached_symbols = cached_data.get('symbols', set())
                        if new_symbols - cached_symbols:  # 有新symbol
                            logger.info(f"[增量评分] 发现新symbol: {len(new_symbols - cached_symbols)}个，重新计算")
                            # 使用已识别的data_usage（避免重复调用）
                            quality_score = self.data_quality_monitor.calculate_quality_score(
                                data, data_type, data_usage=data_usage, data_source=data_source
                            )
                            # 更新缓存
                            self._quality_score_cache[cache_key] = {
                                'score': quality_score,
                                'timestamp': datetime.now(),
                                'symbols': new_symbols
                            }
                else:
                    # 缓存过期，重新计算
                    quality_score = self.data_quality_monitor.calculate_quality_score(
                        data, data_type, data_usage=data_usage, data_source=data_source
                    )
                    logger.info(f"[质量评分计算] 缓存过期，重新计算: {quality_score:.3f}")
                    self._quality_score_cache[cache_key] = {
                        'score': quality_score,
                        'timestamp': datetime.now(),
                        'symbols': set(data['symbol'].unique()) if 'symbol' in data.columns else set()
                    }
            else:
                # 无缓存，首次计算
                quality_score = self.data_quality_monitor.calculate_quality_score(
                    data, data_type, data_usage=data_usage, data_source=data_source
                )
                logger.info(f"[质量评分计算] 首次计算: {quality_score:.3f}")
                self._quality_score_cache[cache_key] = {
                    'score': quality_score,
                    'timestamp': datetime.now(),
                    'symbols': set(data['symbol'].unique()) if 'symbol' in data.columns else set()
                }

            # 记录质量指标（写入SQLite）- 支持智能权重
            table_name = f"{data_source}_{data_type}"
            logger.debug(f"[数据质量验证] 记录质量指标到SQLite - 插件: {data_source}, 表: {table_name}, 用途: {data_usage}")
            self.data_quality_monitor.record_quality_metrics(
                plugin_name=data_source,
                table_name=table_name,
                data=data,
                data_type=data_type,
                data_usage=data_usage,  # 🆕 传递用途参数
                data_source=data_source  # 🆕 传递数据源参数
            )

            # 关键：将质量评分写入DuckDB的data_quality_monitor表
            #    这样unified_best_quality_kline视图才能使用实际评分
            try:
                from ..asset_database_manager import get_asset_separated_database_manager
                from ..plugin_types import AssetType

                # 优化1：批量写入质量评分（提升性能）
                if 'symbol' in data.columns:
                    asset_manager = get_asset_separated_database_manager()
                    symbols = data['symbol'].unique()
                    
                    # 获取frequency（从数据中推断或使用默认值）
                    frequency = data.get('frequency', pd.Series(['1d'] * len(data))).iloc[0] if 'frequency' in data.columns else '1d'
                    logger.info(f"[质量评分写入] 开始批量写入质量评分到DuckDB - 总symbol数: {len(symbols)}, frequency: {frequency}")

                    # 按资产类型分组批量写入
                    from collections import defaultdict
                    quality_records_by_asset = defaultdict(list)

                    # 优化：使用向量化计算替代逐个循环（性能提升50-70%）
                    logger.debug(f"[质量评分写入] 使用向量化计算质量指标...")
                    
                    # 按symbol分组，向量化计算
                    grouped = data.groupby('symbol')
                    
                    # 向量化计算缺失值和完整性评分
                    missing_counts = data.isnull().groupby(data['symbol']).sum().sum(axis=1)
                    total_cells = grouped.size()
                    completeness_scores = 1.0 - (missing_counts / total_cells)
                    
                    # 批量生成记录
                    for symbol in symbols:
                        try:
                            # 确定资产类型
                            asset_type = AssetType.STOCK_A if str(symbol).endswith(('.SZ', '.SH')) else AssetType.STOCK_A

                            symbol_data = data[data['symbol'] == symbol]
                            monitor_id = f"{symbol}_{data_source}_{date.today().isoformat()}_{frequency}"
                            missing_count = int(missing_counts[symbol])
                            total_cells_symbol = int(total_cells[symbol])
                            completeness_score = float(completeness_scores[symbol])

                            quality_records_by_asset[asset_type].append([
                                monitor_id,
                                symbol,
                                data_source,
                                date.today(),
                                frequency,
                                quality_score,
                                0,  # anomaly_count
                                missing_count,
                                completeness_score,
                                f"Records: {len(symbol_data)}, Quality: {quality_score:.3f}"
                            ])
                        except Exception as e:
                            logger.warning(f"[质量评分准备] 准备{symbol}质量记录失败: {e}")

                    # 批量写入（按资产类型）
                    total_written = 0
                    for asset_type, records in quality_records_by_asset.items():
                        try:
                            with asset_manager.get_connection(asset_type) as conn:
                                # 使用executemany批量插入
                                conn.executemany("""
                                    INSERT OR REPLACE INTO data_quality_monitor 
                                    (monitor_id, symbol, data_source, check_date, frequency, quality_score, 
                                     anomaly_count, missing_count, completeness_score, details)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, records)
                                # R287 P0-2：同步维护 monitor_latest 物化表（每 symbol+data_source+
                                # frequency 仅保留最近一次评估，替代视图内全表 GROUP BY 子查询）
                                try:
                                    conn.execute("""
                                        CREATE TABLE IF NOT EXISTS monitor_latest (
                                            symbol VARCHAR NOT NULL,
                                            data_source VARCHAR NOT NULL,
                                            frequency VARCHAR NOT NULL DEFAULT '1d',
                                            check_date DATE NOT NULL,
                                            quality_score DECIMAL(5,2),
                                            anomaly_count INTEGER DEFAULT 0,
                                            missing_count INTEGER DEFAULT 0,
                                            completeness_score DECIMAL(5,2),
                                            details TEXT,
                                            PRIMARY KEY (symbol, data_source, frequency)
                                        )
                                    """)
                                    # records 元素顺序：monitor_id, symbol, data_source, check_date,
                                    # frequency, quality_score, anomaly_count, missing_count,
                                    # completeness_score, details
                                    conn.executemany("""
                                        INSERT OR REPLACE INTO monitor_latest
                                        (symbol, data_source, frequency, check_date, quality_score,
                                         anomaly_count, missing_count, completeness_score, details)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, [[r[1], r[2], r[4], r[3], r[5], r[6], r[7], r[8], r[9]] for r in records])
                                except Exception as ml_error:
                                    logger.warning(f"[质量评分写入] 同步维护monitor_latest失败: {ml_error}")
                                total_written += len(records)
                                logger.debug(f"[质量评分写入] 批量写入{asset_type.value}: {len(records)}条记录")
                        except Exception as e:
                            logger.warning(f"[质量评分写入] 批量写入{asset_type.value}失败: {e}")

                    logger.info(f"[质量评分写入] 批量写入完成 - 成功: {total_written}/{len(symbols)}条")
            except Exception as e:
                logger.warning(f"[质量评分写入] 写入质量评分到DuckDB失败: {e}")
                logger.debug(f"[质量评分写入] 异常堆栈: ", exc_info=True)

            # 创建详细的验证结果
            validation_result = self._create_detailed_validation_result(
                data, quality_score, data_source, data_type, strict_validation
            )

            # 记录质量评估结果
            quality_level = validation_result.quality_level
            logger.info(f" 数据质量评估完成: {quality_level.value}, 评分: {quality_score:.3f}")

            # 根据严格模式调整质量阈值
            if strict_validation:
                if quality_score < 0.85:
                    logger.warning(f" 严格模式：数据质量不达标 (评分: {quality_score:.3f} < 0.85)，建议检查数据源")
            else:
                if quality_score < 0.7:
                    logger.warning(f" 数据质量较差 (评分: {quality_score:.3f})，建议检查数据源")

            return validation_result

        except Exception as e:
            logger.error(f"数据质量验证失败: {e}")
            error_msg = f"验证过程出错: {str(e)}"
            logger.error(f"[数据质量验证] 异常详情: {error_msg}")
            return ValidationResult(
                is_valid=False,
                quality_score=0.0,
                quality_level=DataQuality.POOR,
                errors=[error_msg],
                warnings=[],
                suggestions=["检查数据源连接", "验证数据格式"],
                metrics={},
                validation_time=datetime.now()
            )

    def _infer_data_usage(self, data: pd.DataFrame, task_id: str = None) -> str:
        """
        智能识别数据用途

        识别逻辑：
        1. 检查任务ID中的关键词（优先级最高）
        2. 检查数据新鲜度（datetime列）
        3. 检查数据量和时间跨度

        Returns:
            'historical', 'realtime', 'backtest', 'live_trading', 'general'
        """
        try:
            logger.info(f"[数据用途推断] 开始识别 - 任务ID: {task_id}, 数据量: {len(data)}")

            # 方法1: 检查任务ID中的关键词（优先级最高）
            if task_id:
                task_id_lower = task_id.lower()
                if 'backtest' in task_id_lower or '回测' in task_id:
                    logger.info(f"[数据用途推断] 方法1-任务ID关键词识别 → backtest (关键词: {task_id})")
                    return 'backtest'
                elif 'realtime' in task_id_lower or '实时' in task_id:
                    logger.info(f"[数据用途推断] 方法1-任务ID关键词识别 → realtime (关键词: {task_id})")
                    return 'realtime'
                elif 'live' in task_id_lower or 'trading' in task_id_lower or '交易' in task_id:
                    logger.info(f"[数据用途推断] 方法1-任务ID关键词识别 → live_trading (关键词: {task_id})")
                    return 'live_trading'
                elif 'historical' in task_id_lower or '历史' in task_id:
                    logger.info(f"[数据用途推断] 方法1-任务ID关键词识别 → historical (关键词: {task_id})")
                    return 'historical'
                else:
                    logger.debug(f"[数据用途推断] 方法1-任务ID未匹配关键词，继续检查数据特征")
            else:
                logger.debug(f"[数据用途推断] 方法1-任务ID为空，跳过关键词检查")

            # 方法2: 检查数据新鲜度（及时性）
            if 'datetime' in data.columns and not data.empty:
                try:
                    datetime_series = pd.to_datetime(data['datetime'])
                    latest_time = datetime_series.max()
                    earliest_time = datetime_series.min()
                    current_time = pd.Timestamp.now()
                    delay_minutes = (current_time - latest_time).total_seconds() / 60
                    time_span_days = (latest_time - earliest_time).days

                    logger.debug(f"[数据用途推断] 方法2-时间分析 → 最新时间: {latest_time}, "
                                 f"延迟: {delay_minutes:.1f}分钟, 时间跨度: {time_span_days}天")

                    # 5分钟内的数据 → 实盘交易用途
                    if delay_minutes <= 5:
                        logger.info(f"[数据用途推断] 方法2-数据新鲜度识别 → live_trading "
                                    f"(延迟: {delay_minutes:.1f}分钟 ≤ 5分钟)")
                        return 'live_trading'
                    # 1小时内的数据 → 实时行情用途
                    elif delay_minutes <= 60:
                        logger.info(f"[数据用途推断] 方法2-数据新鲜度识别 → realtime "
                                    f"(延迟: {delay_minutes:.1f}分钟 ≤ 60分钟)")
                        return 'realtime'
                    # 1天以上的数据 → 历史数据或回测用途
                    elif delay_minutes > 1440:  # 1天
                        # 进一步判断是否用于回测（时间跨度超过3个月）
                        if time_span_days > 90:  # 超过3个月数据，可能用于回测
                            logger.info(f"[数据用途推断] 方法2-数据新鲜度识别 → backtest "
                                        f"(延迟: {delay_minutes/1440:.1f}天, 时间跨度: {time_span_days}天 > 90天)")
                            return 'backtest'
                        else:
                            logger.info(f"[数据用途推断] 方法2-数据新鲜度识别 → historical "
                                        f"(延迟: {delay_minutes/1440:.1f}天, 时间跨度: {time_span_days}天 ≤ 90天)")
                            return 'historical'
                    else:
                        logger.debug(f"[数据用途推断] 方法2-时间特征未明确匹配，继续检查数据量")

                except Exception as e:
                    logger.warning(f"[数据用途推断] 方法2-时间检查失败: {e}，继续使用方法3")
            else:
                logger.debug(f"[数据用途推断] 方法2-数据中无datetime列或数据为空，跳过时间分析")

            # 方法3: 检查数据量和时间跨度
            data_count = len(data)
            if data_count > 500:  # 大量历史数据
                logger.info(f"[数据用途推断] 方法3-数据量识别 → backtest (数据量: {data_count} > 500)")
                return 'backtest'
            elif data_count < 50:  # 少量数据
                logger.info(f"[数据用途推断] 方法3-数据量识别 → realtime (数据量: {data_count} < 50)")
                return 'realtime'

            # 默认：通用场景
            logger.info(f"[数据用途推断] 默认场景 → general (数据量: {data_count}, 无明确特征)")
            return 'general'

        except Exception as e:
            logger.error(f"[数据用途推断] ❌ 推断失败: {e}，使用默认值 general", exc_info=True)
            return 'general'

    def _create_detailed_validation_result(self, data: pd.DataFrame, quality_score: float,
                                           data_source: str, data_type: str, strict_validation: bool = False) -> ValidationResult:
        """创建详细的验证结果
        
        Args:
            data: 数据DataFrame
            quality_score: 质量评分
            data_source: 数据源
            data_type: 数据类型
            strict_validation: 是否启用严格验证模式
        """
        try:
            issues = []

            # 检查数据完整性
            if data.empty:
                issues.append("数据为空")
                logger.warning(f"[数据验证] 数据为空，数据源: {data_source}, 类型: {data_type}")
                return ValidationResult(
                    is_valid=False,
                    quality_score=0.0,
                    quality_level=DataQuality.POOR,
                    errors=issues,
                    warnings=[],
                    suggestions=["检查数据源是否正常", "验证查询条件"],
                    metrics={"total_records": 0},
                    validation_time=datetime.now()
                )

            # 检查空值
            null_percentage = data.isnull().sum().sum() / data.size
            if null_percentage > 0.1:
                issues.append(f"空值比例过高: {null_percentage:.1%}")

            # 检查重复数据
            duplicate_percentage = data.duplicated().sum() / len(data)
            if duplicate_percentage > 0.05:
                issues.append(f"重复数据比例过高: {duplicate_percentage:.1%}")

            # 检查数据范围（针对K线数据）
            if data_type == 'kdata':
                numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                available_columns = [col for col in numeric_columns if col in data.columns]

                for col in available_columns:
                    if col in ['open', 'high', 'low', 'close']:
                        # 价格数据应该大于0
                        if (data[col] <= 0).any():
                            issues.append(f"{col}列存在非正数价格")
                    elif col == 'volume':
                        # 成交量应该大于等于0
                        if (data[col] < 0).any():
                            issues.append(f"{col}列存在负数成交量")

                # 检查价格逻辑关系
                if all(col in data.columns for col in ['high', 'low', 'open', 'close']):
                    # 最高价应该 >= 最低价
                    if (data['high'] < data['low']).any():
                        issues.append("存在最高价小于最低价的异常数据")

                    # 开盘价和收盘价应该在最高价和最低价之间
                    if ((data['open'] > data['high']) | (data['open'] < data['low'])).any():
                        issues.append("存在开盘价超出最高最低价范围的异常数据")

                    if ((data['close'] > data['high']) | (data['close'] < data['low'])).any():
                        issues.append("存在收盘价超出最高最低价范围的异常数据")

            # 确定质量等级（根据严格模式调整阈值）
            if strict_validation:
                # 严格模式：更高的质量阈值
                if quality_score >= 0.98:
                    quality_level = DataQuality.EXCELLENT
                elif quality_score >= 0.90:
                    quality_level = DataQuality.GOOD
                elif quality_score >= 0.85:
                    quality_level = DataQuality.FAIR
                else:
                    quality_level = DataQuality.POOR
                
                # 严格模式下，质量评分必须 >= 0.85 且没有问题
                is_valid = quality_score >= 0.85 and len(issues) == 0
            else:
                # 普通模式：标准质量阈值
                if quality_score >= 0.95:
                    quality_level = DataQuality.EXCELLENT
                elif quality_score >= 0.85:
                    quality_level = DataQuality.GOOD
                elif quality_score >= 0.70:
                    quality_level = DataQuality.FAIR
                else:
                    quality_level = DataQuality.POOR
                
                # 普通模式下，质量评分必须 >= 0.70 且没有问题
                is_valid = quality_score >= 0.70 and len(issues) == 0

            # 生成建议
            suggestions = []
            if quality_score < 0.7:
                suggestions.append("数据质量较低，建议检查数据源")
            if null_percentage > 0.1:
                suggestions.append("空值比例较高，建议数据清洗")
            if duplicate_percentage > 0.05:
                suggestions.append("存在较多重复数据，建议去重")

            # 记录验证详情
            logger.info(f"[数据验证] 数据源: {data_source}, 类型: {data_type}, 质量评分: {quality_score:.3f}, "
                        f"质量等级: {quality_level.value}, 记录数: {len(data)}, "
                        f"空值率: {null_percentage:.2%}, 重复率: {duplicate_percentage:.2%}")

            return ValidationResult(
                is_valid=is_valid,
                quality_score=quality_score,
                quality_level=quality_level,
                errors=issues,
                warnings=[f"空值比例: {null_percentage:.1%}", f"重复数据比例: {duplicate_percentage:.1%}"] if (null_percentage > 0 or duplicate_percentage > 0) else [],
                suggestions=suggestions,
                metrics={
                    "total_records": len(data),
                    "null_records": int(data.isnull().sum().sum()),
                    "duplicate_records": int(data.duplicated().sum()),
                    "completeness_score": 1.0 - null_percentage,
                    "accuracy_score": quality_score,
                    "data_source": data_source,
                    "data_type": data_type
                },
                validation_time=datetime.now()
            )

        except Exception as e:
            error_msg = f"验证结果创建失败: {str(e)}"
            logger.error(f"[数据验证] {error_msg}, 数据源: {data_source}, 类型: {data_type}")
            return ValidationResult(
                is_valid=False,
                quality_score=0.0,
                quality_level=DataQuality.POOR,
                errors=[error_msg],
                warnings=[],
                suggestions=["检查数据格式", "验证数据完整性"],
                metrics={},
                validation_time=datetime.now()
            )

    def _handle_quality_issues(self, validation_result: ValidationResult, task_id: str):
        """处理数据质量问题"""
        if not validation_result.is_valid or validation_result.quality_level == DataQuality.POOR:
            logger.warning(f"[质量问题处理] 任务 {task_id} 数据质量问题:")
            for error in validation_result.errors:
                logger.warning(f"  - 错误: {error}")
            for warning in validation_result.warnings:
                logger.warning(f"  - 警告: {warning}")

            # 可以在这里添加自动修复逻辑
            metrics = validation_result.metrics
            if metrics.get('duplicate_records', 0) > 0:
                logger.info(f"  建议: 清理 {metrics['duplicate_records']} 条重复数据")

            if metrics.get('null_records', 0) > 0:
                logger.info(f"  建议: 处理 {metrics['null_records']} 个空值")

            # 输出建议
            for suggestion in validation_result.suggestions:
                logger.info(f"  建议: {suggestion}")

    def get_data_quality_statistics(self) -> Dict[str, Any]:
        """获取数据质量统计信息"""
        stats = {
            'data_quality_monitoring_enabled': self.enable_data_quality_monitoring,
            'data_quality_monitor_available': self.data_quality_monitor is not None
        }

        try:
            if self.data_quality_monitor:
                # 这里可以添加从数据库获取历史质量统计的逻辑
                stats.update({
                    'monitoring_active': True,
                    'quality_checks_performed': 0,  # 可以从数据库统计
                    'average_quality_score': 0.0,   # 可以从数据库计算
                    'last_check_time': datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"获取数据质量统计失败: {e}")
            stats['error'] = str(e)

        return stats

    def _start_performance_monitoring(self, task_id: str):
        """启动任务性能监控"""
        if not self.enable_performance_monitoring:
            return

        try:
            # 确保深度分析服务已初始化
            self._ensure_deep_analysis_service()
            # 确保性能集成器已初始化
            self._ensure_performance_integrator()
            
            # 记录任务开始时的系统状态
            if self.deep_analysis_service:
                self.deep_analysis_service.record_metric(
                    f"task_start_{task_id}",
                    time.time(),
                    "import_task"
                )

            # 启动性能集成器监控
            if self.performance_integrator:
                self.performance_integrator.start_monitoring()

            logger.info(f"任务 {task_id} 性能监控已启动")

        except Exception as e:
            logger.warning(f"启动性能监控失败: {e}")

    def _stop_performance_monitoring(self, task_id: str, execution_time: float):
        """停止任务性能监控"""
        if not self.enable_performance_monitoring:
            return

        try:
            # 确保深度分析服务已初始化
            self._ensure_deep_analysis_service()
            
            # 记录任务执行时间
            if self.deep_analysis_service:
                self.deep_analysis_service.record_operation_timing(
                    f"import_task_{task_id}",
                    execution_time
                )

                # 记录任务完成时的系统状态
                self.deep_analysis_service.record_metric(
                    f"task_end_{task_id}",
                    time.time(),
                    "import_task"
                )

                # 分析性能瓶颈
                bottlenecks = self.deep_analysis_service.analyze_bottlenecks()
                if bottlenecks:
                    logger.info(f"任务 {task_id} 性能瓶颈分析: {len(bottlenecks)} 个瓶颈点")
                    for bottleneck in bottlenecks[:3]:  # 显示前3个瓶颈
                        logger.info(f"  - {bottleneck.component}: {bottleneck.avg_duration:.2f}ms ({bottleneck.severity})")

            logger.info(f"任务 {task_id} 性能监控已停止")

        except Exception as e:
            logger.warning(f"停止性能监控失败: {e}")

    def _detect_anomalies(self, task_id: str) -> List[AnomalyInfo]:
        """检测任务执行异常"""
        if not self.enable_anomaly_detection:
            return []

        try:
            # 确保深度分析服务已初始化
            self._ensure_deep_analysis_service()
            
            if self.deep_analysis_service:
                anomalies = self.deep_analysis_service.detect_anomalies()

                if anomalies:
                    logger.warning(f"任务 {task_id} 检测到 {len(anomalies)} 个异常:")
                    for anomaly in anomalies:
                        logger.warning(f"  - {anomaly.metric_name}: {anomaly.description} (严重程度: {anomaly.severity})")

                return anomalies
            
            return []

        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return []

    def _monitor_task_progress(self, task_id: str, progress: float, message: str):
        """监控任务进度并检测异常"""
        try:
            # 记录进度指标
            if self.enable_performance_monitoring:
                # 确保深度分析服务已初始化
                self._ensure_deep_analysis_service()
                
                if self.deep_analysis_service:
                    self.deep_analysis_service.record_metric(
                        f"task_progress_{task_id}",
                        progress,
                        "import_progress"
                    )

            # 检测进度异常
            if self.enable_anomaly_detection:
                # 如果进度长时间没有变化，可能存在问题
                current_time = time.time()
                if hasattr(self, '_last_progress_time'):
                    time_diff = current_time - self._last_progress_time
                    if time_diff > 300 and progress == getattr(self, '_last_progress', 0):  # 5分钟没有进度变化
                        logger.warning(f"任务 {task_id} 可能存在进度停滞问题")

                self._last_progress_time = current_time
                self._last_progress = progress

            # 发送进度信号
            self.task_progress.emit(task_id, progress, message)

        except Exception as e:
            logger.error(f"监控任务进度失败: {e}")

    def get_performance_report(self, task_id: str = None) -> Dict[str, Any]:
        """获取性能报告"""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'monitoring_enabled': self.enable_performance_monitoring,
                'anomaly_detection_enabled': self.enable_anomaly_detection
            }

            if self.enable_performance_monitoring:
                # 确保深度分析服务已初始化
                self._ensure_deep_analysis_service()
                
                if self.deep_analysis_service:
                    # 获取性能统计
                    bottlenecks = self.deep_analysis_service.analyze_bottlenecks()
                    report['bottlenecks'] = [
                        {
                            'component': b.component,
                            'avg_duration': b.avg_duration,
                            'call_count': b.call_count,
                            'severity': b.severity
                        } for b in bottlenecks[:5]
                    ]

                    # 获取系统指标
                    system_metrics = self.deep_analysis_service.get_system_metrics()
                    report['system_metrics'] = system_metrics

            if self.enable_anomaly_detection:
                # 确保深度分析服务已初始化
                self._ensure_deep_analysis_service()
                
                if self.deep_analysis_service:
                    # 获取异常信息
                    anomalies = self.deep_analysis_service.detect_anomalies()
                    report['anomalies'] = [
                        {
                            'metric_name': a.metric_name,
                            'value': a.value,
                            'threshold': a.threshold,
                            'severity': a.severity,
                            'description': a.description,
                            'timestamp': a.timestamp.isoformat()
                        } for a in anomalies
                    ]

            return report

        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
            return {'error': str(e)}

    def _ensure_data_manager(self):
        """确保数据管理器已初始化"""
        if not self._data_manager_initialized:
            try:
                logger.info("延迟初始化数据管理器...")
                self.data_manager = get_unified_data_manager()
                self._data_manager_initialized = True
                logger.info("数据管理器延迟初始化完成")
            except Exception as e:
                logger.error(f" 数据管理器初始化失败: {e}")
                # 创建一个最小的数据管理器替代
                self.data_manager = None
                self._data_manager_initialized = False

    def _ensure_real_data_provider(self):
        """确保真实数据提供器已初始化"""
        if not self._real_data_provider_initialized:
            try:
                logger.info("延迟初始化真实数据提供器...")
                self.real_data_provider = RealDataProvider()
                self._real_data_provider_initialized = True
                logger.info("真实数据提供器延迟初始化完成")
            except Exception as e:
                logger.error(f" 真实数据提供器初始化失败: {e}")
                # 创建一个最小的替代
                self.real_data_provider = None
                self._real_data_provider_initialized = False

    def _ensure_asset_database_manager(self):
        """确保资产数据库管理器已初始化"""
        if not hasattr(self, 'asset_manager') or self.asset_manager is None:
            try:
                logger.info("初始化资产数据库管理器...")
                from ..asset_database_manager import AssetSeparatedDatabaseManager
                self.asset_manager = AssetSeparatedDatabaseManager()
                logger.info("资产数据库管理器初始化完成")
            except Exception as e:
                logger.error(f"资产数据库管理器初始化失败: {e}")
                self.asset_manager = None

    def _get_data_source_plugin(self, plugin_id: str):
        """获取指定的数据源插件实例"""
        try:
            # 从插件管理器获取插件实例
            from utils.singleton_helper import get_plugin_manager
            plugin_manager = get_plugin_manager()

            if plugin_manager:
                # 获取数据源插件
                plugin_instance = plugin_manager.get_data_source_plugin(plugin_id)
                if plugin_instance:
                    logger.info(f"获取数据源插件成功: {plugin_id}")
                    return plugin_instance
                else:
                    logger.warning(f"未找到数据源插件: {plugin_id}")

            # 如果插件管理器不可用，尝试直接导入
            if plugin_id.startswith('examples.'):
                module_name = plugin_id.replace('examples.', 'plugins.examples.')
                try:
                    import importlib
                    module = importlib.import_module(module_name)

                    # 查找插件类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (hasattr(attr, '__bases__') and
                                any('IDataSourcePlugin' in str(base) for base in attr.__bases__)):
                            plugin_instance = attr()
                            logger.info(f"直接导入数据源插件成功: {plugin_id}")
                            return plugin_instance

                except ImportError as e:
                    logger.error(f"直接导入数据源插件失败 {plugin_id}: {e}")

            return None

        except Exception as e:
            logger.error(f"获取数据源插件失败 {plugin_id}: {e}")
            return None

    def start_task(self, task_id: str) -> bool:
        """
        启动任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功启动
        """
        try:
            logger.info(f" 开始启动任务: {task_id}")

            # 获取任务配置
            task_config = self.config_manager.get_import_task(task_id)
            if not task_config:
                logger.error(f" 任务配置不存在: {task_id}")
                return False

            logger.info(f" 找到任务配置: {task_config.name}, 股票数量: {len(task_config.symbols)}")

            # 智能配置优化（最高优先级）
            if self.enable_intelligent_config:
                logger.info("开始智能配置优化...")
                intelligent_config = self._apply_intelligent_optimization(task_config, ConfigOptimizationLevel.BALANCED)
                if intelligent_config:
                    task_config = intelligent_config
                    logger.info(f" 智能配置优化完成: batch_size={task_config.batch_size}, max_workers={task_config.max_workers}")

            # 检查缓存的配置优化
            cached_config = self._get_cached_configuration(task_config)
            if cached_config and self.enable_intelligent_caching:
                logger.info("使用缓存的配置优化")
                task_config.batch_size = cached_config.get('optimal_batch_size', task_config.batch_size)
                task_config.max_workers = cached_config.get('optimal_workers', task_config.max_workers)

            # AutoTuner自动调优
            if self.enable_auto_tuning:
                task_config = self._auto_tune_task_parameters(task_config)

            # AI优化任务参数
            if self.enable_ai_optimization:
                logger.info("开始AI优化任务参数...")
                task_config = self._optimize_task_parameters(task_config)

                # 缓存优化后的配置
                self._cache_configuration_data(task_config)

                # AI预测执行时间
                predicted_time = self._predict_execution_time(task_config)
                if predicted_time:
                    logger.info(f" AI预测执行时间: {predicted_time:.2f}秒")

            # 检查是否可以分布式执行
            if self.enable_distributed_execution and self._can_distribute_task(task_config):
                logger.info("任务符合分布式执行条件，尝试分布式执行...")
                if self._distribute_task(task_config):
                    logger.info(f"任务 {task_id} 已分布式执行")
                    return True
                else:
                    logger.info("分布式执行失败，回退到本地执行")

            # 检查任务是否已在运行
            with self._task_lock:
                if task_id in self._running_tasks:
                    logger.warning(f"任务已在运行: {task_id}")
                    return False

            # 任务启动前预检：确保通达信连接池已填充可用IP
            try:
                from core.services.unified_data_manager import get_unified_data_manager
                unified_manager = get_unified_data_manager()
                plugin_center = getattr(unified_manager, 'plugin_center', None)
                if plugin_center:
                    tdx_plugin = plugin_center.get_plugin('data_sources.stock.tongdaxin_plugin')
                    if tdx_plugin and getattr(tdx_plugin, 'use_connection_pool', False):
                        pool = getattr(tdx_plugin, 'connection_pool', None)
                        needs_prewarm = True
                        if pool:
                            try:
                                info = pool.get_connection_pool_info()
                                needs_prewarm = int(info.get('total_connections', 0)) == 0
                            except Exception:
                                needs_prewarm = True
                        if needs_prewarm:
                            logger.info("预检：通达信连接池为空，开始服务器发现与健康检测以填充连接池...")
                            ok = False
                            if hasattr(tdx_plugin, 'ensure_pool_populated'):
                                ok = bool(tdx_plugin.ensure_pool_populated())
                            if ok:
                                logger.info("预检：通达信连接池已准备就绪")
                            else:
                                logger.warning("预检：通达信连接池未能就绪，将回退到单连接模式继续任务")
            except Exception as precheck_err:
                logger.warning(f"预检：通达信连接池准备失败（忽略继续）：{precheck_err}")

            # 创建任务执行结果
            result = TaskExecutionResult(
                task_id=task_id,
                status=TaskExecutionStatus.PENDING,
                start_time=datetime.now()
            )

            with self._task_lock:
                self._task_results[task_id] = result

            # 提交任务到线程池
            future = self.executor.submit(self._execute_task, task_config, result)

            with self._task_lock:
                self._running_tasks[task_id] = future

            # 启动增强版性能监控
            if self.enable_enhanced_performance_bridge:
                self.start_enhanced_performance_monitoring()
                logger.info("增强版性能监控已启动")

            # 启动增强版风险监控
            if self.enable_enhanced_risk_monitoring:
                self.start_enhanced_risk_monitoring()
                logger.info("增强版风险监控已启动")

            # 启动性能监控
            self._start_performance_monitoring(task_id)

            # 发送任务开始信号
            self.task_started.emit(task_id)

            logger.info(f"任务启动成功: {task_id}")
            return True

        except Exception as e:
            logger.error(f"启动任务失败 {task_id}: {e}")
            self.task_failed.emit(task_id, str(e))
            return False

    def stop_task(self, task_id: str) -> bool:
        """
        停止任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功停止
        """
        try:
            with self._task_lock:
                if task_id not in self._running_tasks:
                    logger.warning(f"任务未在运行: {task_id}")
                    # 修复：即使任务不在运行中，也检查任务状态，可能任务已完成或已取消
                    if task_id in self._task_results:
                        result = self._task_results[task_id]
                        if result.status == TaskExecutionStatus.CANCELLED:
                            logger.info(f"任务已处于取消状态: {task_id}")
                            return True
                        elif result.status == TaskExecutionStatus.COMPLETED:
                            logger.info(f"任务已完成: {task_id}")
                            return True
                    return False

                # 修复：先更新任务状态为CANCELLED，让执行中的任务能够检查并退出
                if task_id in self._task_results:
                    self._task_results[task_id].status = TaskExecutionStatus.CANCELLED
                    logger.info(f"任务状态已标记为取消: {task_id}")

                # 尝试取消Future（如果任务还未开始执行，cancel()会返回True）
                future = self._running_tasks[task_id]
                cancelled = future.cancel()

                if cancelled:
                    # Future成功取消（任务还未开始执行）
                    logger.info(f"任务Future已取消（任务未开始执行）: {task_id}")
                else:
                    # Future无法取消（任务已开始执行），但我们已经设置了状态为CANCELLED
                    # 执行中的任务会检查result.status并退出
                    logger.info(f"任务已开始执行，无法取消Future，但已设置取消状态: {task_id}")
                    logger.info(f"执行中的任务将在下次检查时检测到取消状态并退出")

                # 更新任务结果
                if task_id in self._task_results:
                    self._task_results[task_id].end_time = datetime.now()
                    if self._task_results[task_id].start_time:
                        self._task_results[task_id].execution_time = (
                            self._task_results[task_id].end_time - self._task_results[task_id].start_time
                        ).total_seconds()

                # 移除运行中的任务（无论cancel()是否成功）
                del self._running_tasks[task_id]

                # 停止增强版性能监控
                if self.enable_enhanced_performance_bridge:
                    self.stop_enhanced_performance_monitoring()
                    logger.info("增强版性能监控已停止")

                # 停止增强版风险监控
                if self.enable_enhanced_risk_monitoring:
                    self.stop_enhanced_risk_monitoring()
                    logger.info("增强版风险监控已停止")

                # 修复：发送任务取消信号
                self.task_cancelled.emit(task_id)

                logger.info(f"任务停止成功: {task_id}")
                return True

        except Exception as e:
            logger.error(f"停止任务失败 {task_id}: {e}", exc_info=True)
            return False

    def get_task_status(self, task_id: str) -> Optional[TaskExecutionResult]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            TaskExecutionResult: 任务执行结果
        """
        with self._task_lock:
            return self._task_results.get(task_id)

    def get_running_tasks(self) -> List[str]:
        """获取正在运行的任务列表"""
        with self._task_lock:
            return list(self._running_tasks.keys())

    def stop_all_tasks(self) -> bool:
        """
        停止所有正在运行的任务

        Returns:
            bool: 是否成功停止所有任务
        """
        try:
            with self._task_lock:
                running_task_ids = list(self._running_tasks.keys())

                if not running_task_ids:
                    logger.info("没有正在运行的任务需要停止")
                    return True

                logger.info(f"停止 {len(running_task_ids)} 个正在运行的任务")

                success_count = 0
                for task_id in running_task_ids:
                    if self.stop_task(task_id):
                        success_count += 1

                logger.info(f"成功停止 {success_count}/{len(running_task_ids)} 个任务")
                return success_count == len(running_task_ids)

        except Exception as e:
            logger.error(f"停止所有任务失败: {e}")
            return False

    def _ensure_db_writer_thread(self):
        """确保数据库写入线程存活（R292 修复：防止连续任务写线程死亡导致数据丢失）

        DatabaseWriterThread 在每次任务结束的 finally 中被 stop（保证 merge buffer
        完全刷新），同一引擎连续执行第二个任务时写线程已死，put_write_task 入队无人
        消费 → 数据静默丢失。任务执行前调用本方法：线程非存活则重建新实例并 start
        （threading.Thread 不可复用，只能重建）。
        """
        if not hasattr(self, 'db_writer_thread') or not self.db_writer_thread.is_alive():
            logger.warning("检测到 DatabaseWriterThread 已停止，重建写入线程（防止数据静默丢失）")
            self.db_writer_thread = DatabaseWriterThread()
            self.db_writer_thread.start()
            logger.info("DatabaseWriterThread 已重新启动")

    def _execute_task(self, task_config: ImportTaskConfig, result: TaskExecutionResult):
        """
        执行任务的核心逻辑

        Args:
            task_config: 任务配置
            result: 任务执行结果
        """
        try:
            # R292 修复：DatabaseWriterThread 在每次任务结束的 finally 中被 stop
            # （保证 merge buffer 完全刷新、防止数据丢失），但同一引擎连续执行第二个
            # 任务时写线程已死 → _save_kdata_to_database 的 put_write_task 入队无人
            # 消费 → 数据静默丢失。任务执行前检测线程存活，非存活则重建新实例
            # （threading.Thread 不可复用，只能重建后重新 start）。
            self._ensure_db_writer_thread()

            logger.info(f" 开始执行任务: {task_config.task_id}")
            logger.info(f" 任务名称: {task_config.name}")
            
            # 记录任务描述
            if task_config.description:
                logger.info(f" 任务描述: {task_config.description}")
            
            # 记录数据用途
            logger.info(f" 数据用途: {task_config.data_usage}")
            
            # 根据数据用途调整监控策略
            if task_config.data_usage == "backtest":
                # 回测用途：启用更严格的数据质量监控
                if hasattr(self, 'enable_data_quality_monitoring'):
                    self.enable_data_quality_monitoring = True
                    logger.info(" 回测用途：启用严格数据质量监控")
            elif task_config.data_usage == "realtime":
                # 实时用途：启用性能监控
                if hasattr(self, 'enable_performance_monitoring'):
                    self.enable_performance_monitoring = True
                    logger.info(" 实时用途：启用性能监控")
            elif task_config.data_usage == "live_trading":
                # 实盘用途：启用所有监控
                if hasattr(self, 'enable_data_quality_monitoring'):
                    self.enable_data_quality_monitoring = True
                if hasattr(self, 'enable_performance_monitoring'):
                    self.enable_performance_monitoring = True
                logger.info(" 实盘用途：启用所有监控")
            
            logger.info(f" 任务详情: 数据类型={getattr(task_config, 'data_type', 'K线数据')}, 股票数量={len(task_config.symbols)}")

            # 修复：检查是否有已保存的进度并恢复
            saved_progress = self.config_manager.get_progress(task_config.task_id)
            if saved_progress and saved_progress.status == ImportStatus.RUNNING:
                logger.info(f"📋 [进度恢复] 发现已保存的进度: task_id={task_config.task_id}")
                logger.info(f"   已处理记录: {saved_progress.imported_records}/{saved_progress.total_records}")

                # 恢复已处理的记录数
                result.processed_records = saved_progress.imported_records
                result.failed_records = saved_progress.error_count
                result.total_records = saved_progress.total_records or len(task_config.symbols)

                # 修复：使用processed_symbols_list过滤已处理的股票
                if hasattr(saved_progress, 'processed_symbols_list') and saved_progress.processed_symbols_list:
                    processed_symbols = set(saved_progress.processed_symbols_list)
                    original_symbols = task_config.symbols.copy()
                    remaining_symbols = [s for s in original_symbols if s not in processed_symbols]

                    if remaining_symbols:
                        logger.info(f"📋 [进度恢复] 已处理{len(processed_symbols)}个股票，剩余{len(remaining_symbols)}个股票继续处理")
                        task_config.symbols = remaining_symbols
                        # 更新total_records为原始总数（不改变总数，只改变待处理列表）
                        result.total_records = saved_progress.total_records or len(original_symbols)
                        # 恢复已处理股票列表到result中
                        result.processed_symbols_list = saved_progress.processed_symbols_list.copy()
                    else:
                        logger.info(f"📋 [进度恢复] 所有股票已处理完成，任务标记为完成")
                        result.status = TaskExecutionStatus.COMPLETED
                        result.success = True
                        result.end_time = datetime.now()
                        # 更新进度为完成状态
                        progress = ImportProgress(
                            task_id=task_config.task_id,
                            status=ImportStatus.COMPLETED,
                            total_symbols=saved_progress.total_symbols,
                            processed_symbols=saved_progress.processed_symbols,
                            total_records=result.total_records,
                            imported_records=result.processed_records,
                            error_count=result.failed_records,
                            start_time=saved_progress.start_time if hasattr(saved_progress, 'start_time') and saved_progress.start_time else datetime.now().isoformat(),
                            end_time=result.end_time.isoformat(),
                            error_message=None,
                            processed_symbols_list=saved_progress.processed_symbols_list
                        )
                        self.config_manager.update_progress(progress)
                        self.task_completed.emit(task_config.task_id, result)
                        return
                else:
                    # 如果没有processed_symbols_list，尝试基于processed_symbols数量跳过
                    if saved_progress.processed_symbols > 0:
                        logger.warning(f"📋 [进度恢复] 缺少processed_symbols_list，基于processed_symbols数量跳过前{saved_progress.processed_symbols}个股票")
                        if saved_progress.processed_symbols < len(task_config.symbols):
                            task_config.symbols = task_config.symbols[saved_progress.processed_symbols:]
                            logger.info(f"📋 [进度恢复] 跳过前{saved_progress.processed_symbols}个股票，剩余{len(task_config.symbols)}个股票继续处理")
                        else:
                            logger.info(f"📋 [进度恢复] 所有股票已处理完成")
                            result.status = TaskExecutionStatus.COMPLETED
                            result.success = True
                            result.end_time = datetime.now()
                            progress = ImportProgress(
                                task_id=task_config.task_id,
                                status=ImportStatus.COMPLETED,
                                total_symbols=saved_progress.total_symbols,
                                processed_symbols=saved_progress.processed_symbols,
                                total_records=result.total_records,
                                imported_records=result.processed_records,
                                error_count=result.failed_records,
                                start_time=saved_progress.start_time if hasattr(saved_progress, 'start_time') and saved_progress.start_time else datetime.now().isoformat(),
                                end_time=result.end_time.isoformat(),
                                error_message=None,
                                processed_symbols_list=[]
                            )
                            self.config_manager.update_progress(progress)
                            self.task_completed.emit(task_config.task_id, result)
                            return

                logger.info(f"[进度恢复] 任务将从第{result.processed_records + 1}条记录继续执行")

            # 修复：在执行前检查任务是否已取消
            if result.status == TaskExecutionStatus.CANCELLED:
                logger.info(f"⚠️ [任务已取消] {task_config.task_id} 在执行前已取消，跳过执行")
                result.end_time = datetime.now()
                if result.start_time:
                    result.execution_time = (result.end_time - result.start_time).total_seconds()
                self.task_cancelled.emit(task_config.task_id)
                return

            # 更新任务状态
            result.status = TaskExecutionStatus.RUNNING

            # 如果total_records未设置，使用symbols数量
            if result.total_records == 0:
                result.total_records = len(task_config.symbols)

            # 根据任务类型执行不同的导入逻辑
            # 根据任务类型执行不同的导入逻辑
            data_type_str = getattr(task_config, 'data_type', 'K 线数据').strip()
            
            # 使用 plugin_center 的映射机制（复用现有架构）
            data_type = data_type_str  # 默认使用原始字符串
            try:
                # 通过 data_manager 访问 plugin_center（已验证的访问路径）
                uni_plugin_manager = getattr(self.data_manager, '_uni_plugin_manager', None)
                if uni_plugin_manager:
                    plugin_center = getattr(uni_plugin_manager, 'plugin_center', None)
                    if plugin_center and hasattr(plugin_center, '_map_string_to_data_type'):
                        data_type_enum = plugin_center._map_string_to_data_type(data_type_str)
                        if data_type_enum:
                            # 将枚举转换为中文显示名用于后续比较
                            display_mapping = {
                                # 主要数据类型
                                DataType.HISTORICAL_KLINE: 'K 线数据',
                                DataType.REAL_TIME_QUOTE: '实时行情',
                                DataType.FUNDAMENTAL: '基本面数据',
                                DataType.ASSET_LIST: '资产列表',
                                DataType.SECTOR_FUND_FLOW: '板块资金流',
                                
                                # 其他数据类型（使用英文 value 作为显示名）
                                DataType.MARKET_DEPTH: '盘口深度',
                                DataType.TRADE_TICK: '逐笔成交',
                                DataType.TICK_DATA: 'Tick 数据',
                                DataType.ORDER_BOOK: '委托账本',
                                DataType.LEVEL2_DATA: 'Level2 数据',
                                DataType.NEWS: '新闻数据',
                                DataType.ANNOUNCEMENT: '公告数据',
                                DataType.FUND_FLOW: '资金流数据',
                                DataType.INDIVIDUAL_FUND_FLOW: '个股资金流',
                                DataType.MAIN_FUND_FLOW: '主力资金流',
                                DataType.SECTOR_DATA: '板块数据',
                                DataType.TECHNICAL_INDICATORS: '技术指标',
                                DataType.INTRADAY_DATA: '分时数据',
                                DataType.STOCK_BASIC_INFO: '股票基本信息',
                            }
                            data_type = display_mapping.get(data_type_enum, data_type_str)
                            logger.debug(f"数据类型映射：{data_type_str} → {data_type_enum.value} → {data_type}")
            except Exception as e:
                logger.debug(f"数据类型映射失败，使用原始值：{e}")
                data_type = data_type_str
            

            if data_type == "K线数据":
                logger.info("开始导入K线数据")
                self._import_kline_data(task_config, result)
            elif data_type == "实时行情":
                logger.info("开始导入实时行情")
                self._import_realtime_data(task_config, result)
            elif data_type == "基本面数据":
                logger.info("开始导入基本面数据")
                self._import_fundamental_data(task_config, result)
            else:
                logger.warning(f" 不支持的数据类型，默认使用K线数据: {data_type}")
                self._import_kline_data(task_config, result)

            # 修复：检查任务是否在完成前被取消
            if result.status == TaskExecutionStatus.CANCELLED:
                logger.info(f"⚠️ [任务已取消] {task_config.task_id} 在执行过程中被取消")
                result.end_time = datetime.now()
                if result.start_time:
                    result.execution_time = (result.end_time - result.start_time).total_seconds()
                # 不发送task_completed信号，因为任务是被取消的
                return

            # 任务完成
            result.status = TaskExecutionStatus.COMPLETED
            result.success = True
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()

            # 记录智能配置性能反馈
            if self.enable_intelligent_config:
                self.record_task_performance_feedback(task_config.task_id, result)

            # 记录增强性能数据
            if self.enable_enhanced_performance_bridge and result.success:
                execution_time = (result.end_time - result.start_time).total_seconds()
                self.record_custom_performance_metric(
                    f"task_execution_time_{task_config.task_id}",
                    execution_time,
                    "task_performance"
                )
                self.record_custom_performance_metric(
                    f"task_success_rate_{task_config.task_id}",
                    1.0,
                    "task_quality"
                )

            # 更新配置管理器中的进度
            # 修复：获取已处理股票列表（如果result中有）
            processed_symbols_list = getattr(result, 'processed_symbols_list', [])
            if not processed_symbols_list and hasattr(result, 'processed_records') and result.processed_records > 0:
                # 如果没有processed_symbols_list，尝试从task_config中获取所有股票（因为都处理完了）
                processed_symbols_list = task_config.symbols.copy() if hasattr(task_config, 'symbols') else []

            progress = ImportProgress(
                task_id=task_config.task_id,
                status=ImportStatus.COMPLETED,
                total_symbols=len(task_config.symbols) if hasattr(task_config, 'symbols') else 0,
                processed_symbols=result.processed_records + result.failed_records,
                total_records=result.total_records,
                imported_records=result.processed_records,
                error_count=result.failed_records,
                start_time=result.start_time.isoformat() if result.start_time else datetime.now().isoformat(),
                end_time=result.end_time.isoformat() if result.end_time else datetime.now().isoformat(),
                error_message=result.error_message,
                processed_symbols_list=processed_symbols_list  # 保存已处理股票列表
            )
            self.config_manager.update_progress(progress)

            # 停止性能监控并检测异常
            execution_time = (result.end_time - result.start_time).total_seconds()
            self._stop_performance_monitoring(task_config.task_id, execution_time)

            # 检测执行异常
            anomalies = self._detect_anomalies(task_config.task_id)
            if anomalies:
                logger.warning(f"任务 {task_config.task_id} 检测到 {len(anomalies)} 个异常")

            # 发送完成信号
            self.task_completed.emit(task_config.task_id, result)

            logger.info(f"任务执行完成: {task_config.task_id}")

        except Exception as e:
            logger.error(f"任务执行失败 {task_config.task_id}: {e}")

            # 更新任务状态
            result.status = TaskExecutionStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()

            # 停止性能监控
            if result.start_time and result.end_time:
                execution_time = (result.end_time - result.start_time).total_seconds()
                self._stop_performance_monitoring(task_config.task_id, execution_time)

            # 发送失败信号
            self.task_failed.emit(task_config.task_id, str(e))

        finally:
            if hasattr(self, 'db_writer_thread'):
                # 强制停止DatabaseWriterThread，确保merge buffer完全刷新
                # 修复：必须在finally块中明确停止写入线程，防止数据丢失
                try:
                    self.db_writer_thread.stop(wait=True, timeout=30.0)
                    stats = self.db_writer_thread.get_stats()
                    logger.info(f"DatabaseWriterThread统计: {stats}")
                except Exception as e:
                    logger.error(f"停止DatabaseWriterThread失败: {e}")

            with self._task_lock:
                if task_config.task_id in self._running_tasks:
                    del self._running_tasks[task_config.task_id]

    def _save_kdata_to_database(self, symbol: str, kdata: 'pd.DataFrame', task_config: ImportTaskConfig):
        """保存K线数据到数据库（支持实时/批量模式）"""
        try:
            # 优化：复用AssetSeparatedDatabaseManager实例，避免重复创建
            from ..asset_database_manager import AssetSeparatedDatabaseManager
            from ..plugin_types import AssetType, DataType

            # 复用实例（如果已存在）
            if not hasattr(self, '_metadata_asset_manager'):
                self._metadata_asset_manager = AssetSeparatedDatabaseManager()
            asset_manager = self._metadata_asset_manager

            # 修复：先添加symbol字段，再标准化
            if 'symbol' not in kdata.columns:
                kdata['symbol'] = symbol
                logger.debug(f"添加symbol字段: {symbol}")

            # 标准化数据字段，确保与表结构匹配
            # 修复：传递data_source参数，确保保存到数据库的数据包含正确的数据源标识
            # R292 修复：frequency 从任务配置推导（DataFrequency.value → DuckDB 格式）。
            # 此前 _standardize_kline_data_fields 内部硬编码 '1d'，导致分钟任务的数据
            # 落库为 frequency='1d'，污染日线视图（展示"数据多但日期集中"）。
            from core.plugin_types import Period as _PeriodCls
            try:
                _task_frequency = _PeriodCls.to_duckdb_frequency(str(task_config.frequency.value))
            except Exception:
                # R292 修复：兜底不再固定 '1d'（避免分钟任务异常时静默标为日线污染日线视图），
                # 从任务配置原始值回退（to_duckdb_frequency 内部已对未知值归一为 '1d'）。
                _task_frequency = str(getattr(task_config.frequency, 'value', '1d'))
            kdata = self._standardize_kline_data_fields(
                kdata, data_source=task_config.data_source, frequency=_task_frequency)

            # 使用任务配置中的资产类型，不再进行推断
            asset_type = task_config.asset_type

            # 改进：统一资产类型转换逻辑，支持三种格式
            if isinstance(asset_type, str):
                from core.ui_asset_type_utils import UIAssetTypeUtils
                try:
                    # 1. 尝试直接作为枚举值字符串转换（如"stock_a"）
                    asset_type = AssetType(asset_type)
                    logger.debug(f"资产类型从枚举值字符串转换: {asset_type.value}")
                except ValueError:
                    # 2. 尝试从中文显示名称转换（如"A股"）
                    asset_type = UIAssetTypeUtils.REVERSE_MAPPING.get(asset_type)
                    if asset_type is None:
                        # 3. 使用默认值
                        logger.warning(f"无法解析资产类型: {task_config.asset_type}，使用默认值 STOCK_A")
                        asset_type = AssetType.STOCK_A
                    else:
                        logger.debug(f"资产类型从中文名称转换: {task_config.asset_type} -> {asset_type.value}")

            # 优化：保存资产元数据改为异步（避免阻塞主流程）
            # 元数据保存移到后台线程，不阻塞K线数据入队
            self._save_asset_metadata_async(symbol, asset_type, task_config, kdata)

            # 新方案：统一使用写入队列（DatabaseWriterThread）
            # 生成buffer_key
            buffer_key = f"{asset_type.value}_{task_config.task_id}"

            # 创建写入任务
            write_task = WriteTask(
                buffer_key=buffer_key,
                data=kdata.copy(),  # 复制数据避免后续修改影响
                asset_type=asset_type,
                data_type=DataType.HISTORICAL_KLINE
            )

            # 优化：放入队列（记录队列状态，便于性能分析）
            queue_size_before = self.db_writer_thread.write_queue.qsize()
            queue_start_time = time.time()

            success = self.db_writer_thread.put_write_task(write_task, timeout=10.0)

            queue_put_duration = time.time() - queue_start_time
            queue_size_after = self.db_writer_thread.write_queue.qsize()
            mode = "队列写入"

            if success:
                # 优化：记录详细的队列操作信息
                if queue_put_duration > 0.1:  # 如果入队耗时超过0.1秒，记录警告
                    logger.warning(f"⚠️  [队列积压] {symbol} | 入队耗时:{queue_put_duration:.2f}秒 | 队列大小:{queue_size_before}→{queue_size_after} | 可能队列积压严重")
                logger.debug(f"K线数据保存成功({mode}模式): {symbol}, {len(kdata)}条记录 | 队列:{queue_size_before}→{queue_size_after}")
            else:
                logger.error(f"K线数据保存失败({mode}模式): {symbol}")

        except Exception as e:
            logger.error(f"保存K线数据到数据库失败: {symbol}, {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

    def _save_asset_metadata(self, symbol: str, asset_type, task_config: ImportTaskConfig, kdata: 'pd.DataFrame' = None):
        """
        保存资产元数据到数据库

        Args:
            symbol: 股票代码
            asset_type: 资产类型
            task_config: 任务配置
            kdata: K线数据DataFrame（用于提取股票名称等信息）
        """
        try:
            from ..asset_database_manager import AssetSeparatedDatabaseManager
            from ..plugin_types import AssetType

            # 优化：复用AssetSeparatedDatabaseManager实例
            if not hasattr(self, '_metadata_asset_manager'):
                self._metadata_asset_manager = AssetSeparatedDatabaseManager()
            asset_manager = self._metadata_asset_manager

            # 从K线数据中提取元数据信息
            stock_name = symbol  # 默认使用symbol
            stock_market = self._infer_market_from_symbol(symbol)
            stock_exchange = self._infer_exchange_from_market(stock_market)

            # 初始化可选字段
            sector = None
            industry = None
            industry_code = None
            listing_date = None
            total_shares = None
            circulating_shares = None

            if kdata is not None and not kdata.empty:
                # 获取第一行数据（元数据信息通常在每行都相同）
                first_row = kdata.iloc[0]

                # 提取股票名称
                if 'name' in kdata.columns:
                    name_value = first_row.get('name')
                    if name_value and str(name_value).strip() and str(name_value) != 'None':
                        stock_name = str(name_value).strip()
                        logger.debug(f"从K线数据获取股票名称: {symbol} -> {stock_name}")

                # 优化：如果K线数据中没有name，先检查数据库中是否已有元数据，再尝试从外部API获取
                if stock_name == symbol:
                    logger.debug(f"K线数据中未包含股票名称，尝试获取: {symbol}")

                    # 修复：先检查数据库中是否已有元数据（避免重复API调用）
                    try:
                        from ..asset_database_manager import AssetSeparatedDatabaseManager
                        asset_manager = AssetSeparatedDatabaseManager.get_instance()
                        existing_metadata = asset_manager.get_asset_metadata(symbol, asset_type)
                        if existing_metadata and existing_metadata.get('name'):
                            stock_name = existing_metadata['name']
                            logger.debug(f"从数据库获取股票名称: {symbol} -> {stock_name}")
                            # 同时获取行业板块信息
                            if existing_metadata.get('industry'):
                                industry = existing_metadata['industry']
                            if existing_metadata.get('sector'):
                                sector = existing_metadata['sector']
                            if existing_metadata.get('listing_date'):
                                listing_date = self._normalize_date_format(existing_metadata['listing_date'])
                    except Exception as e:
                        logger.debug(f"从数据库获取元数据失败 {symbol}: {e}")

                    # 修复：如果数据库中也没有，才尝试从外部API获取（添加超时，避免长时间阻塞）
                    if stock_name == symbol:
                        logger.debug(f"数据库中也没有股票名称，尝试从元数据增强器获取: {symbol}")
                        try:
                            from ..utils.stock_metadata_enhancer import get_metadata_enhancer
                            enhancer = get_metadata_enhancer()
                            # 优化：添加超时机制，避免外部API调用阻塞太久
                            import threading

                            enhanced_data = None
                            api_error = None

                            def fetch_metadata():
                                nonlocal enhanced_data, api_error
                                try:
                                    # 优化：批量获取元数据（虽然只有一个symbol，但利用缓存机制）
                                    enhanced_data = enhancer.enhance_stock_metadata_batch([symbol], source='akshare')
                                except Exception as e:
                                    api_error = e

                            # 在单独线程中执行，带超时
                            fetch_thread = threading.Thread(target=fetch_metadata, daemon=True)
                            fetch_thread.start()
                            fetch_thread.join(timeout=5.0)  # 优化：增加超时时间到5秒，避免频繁超时

                            if fetch_thread.is_alive():
                                # 优化：超时时不记录警告，只记录debug日志（因为可能是网络问题，不影响主流程）
                                logger.debug(f"从外部API获取元数据超时: {symbol}，跳过（不影响主流程）")
                            elif enhanced_data and symbol in enhanced_data:
                                metadata = enhanced_data[symbol]
                                if 'name' in metadata and metadata['name']:
                                    stock_name = metadata['name']
                                    logger.info(f"从外部API获取股票名称: {symbol} -> {stock_name}")
                                # 同时获取行业板块信息
                                if 'industry' in metadata and metadata['industry']:
                                    industry = metadata['industry']
                                    logger.debug(f"从外部API获取行业: {symbol} -> {industry}")
                                if 'sector' in metadata and metadata['sector']:
                                    sector = metadata['sector']
                                    logger.debug(f"从外部API获取板块: {symbol} -> {sector}")
                                if 'listing_date' in metadata and metadata['listing_date']:
                                    # 根本修复：统一转换日期格式（支持INTEGER和字符串）
                                    raw_date = metadata['listing_date']
                                    listing_date = self._normalize_date_format(raw_date)
                                    if listing_date:
                                        logger.debug(f"从外部API获取上市日期: {symbol} -> {listing_date} (原值:{raw_date})")
                                    else:
                                        logger.warning(f"上市日期格式无效: {symbol}, 原值={raw_date}")
                            elif api_error:
                                logger.debug(f"从外部API获取元数据失败 {symbol}: {api_error}（不影响主流程）")
                        except Exception as e:
                            logger.debug(f"从外部API获取元数据失败 {symbol}: {e}（不影响主流程）")

                # 提取市场信息
                if 'market' in kdata.columns:
                    market_value = first_row.get('market')
                    if market_value and str(market_value).strip():
                        stock_market = str(market_value).strip().lower()
                        stock_exchange = self._infer_exchange_from_market(stock_market)

                # 提取行业板块信息（支持多种字段名称变体）
                # 板块字段变体：sector, sector_name, plate, plate_name, 板块, 所属板块
                sector_fields = ['sector', 'sector_name', 'sectorname', 'plate', 'plate_name', '板块', '所属板块']
                for field in sector_fields:
                    if field in kdata.columns:
                        sector_value = first_row.get(field)
                        if sector_value and str(sector_value).strip() and str(sector_value).strip() not in ['', 'None', 'nan', '未知']:
                            sector = str(sector_value).strip()
                            logger.debug(f"从K线数据获取板块: {symbol} -> {sector} (字段:{field})")
                            break

                # 行业字段变体：industry, industry_name, industryname, 行业, 所属行业
                industry_fields = ['industry', 'industry_name', 'industryname', '行业', '所属行业']
                for field in industry_fields:
                    if field in kdata.columns:
                        industry_value = first_row.get(field)
                        if industry_value and str(industry_value).strip() and str(industry_value).strip() not in ['', 'None', 'nan', '未知']:
                            industry = str(industry_value).strip()
                            logger.debug(f"从K线数据获取行业: {symbol} -> {industry} (字段:{field})")
                            break

                # 行业代码字段变体：industry_code, industrycode, industry_id, 行业代码
                industry_code_fields = ['industry_code', 'industrycode', 'industry_id', '行业代码']
                for field in industry_code_fields:
                    if field in kdata.columns:
                        code_value = first_row.get(field)
                        if code_value and str(code_value).strip() and str(code_value).strip() not in ['', 'None', 'nan']:
                            industry_code = str(code_value).strip()
                            logger.debug(f"从K线数据获取行业代码: {symbol} -> {industry_code} (字段:{field})")
                            break

                # 提取上市日期（如果K线数据中有）
                for date_col in ['listing_date', 'list_date', 'ipo_date']:
                    if date_col in kdata.columns:
                        date_value = first_row.get(date_col)
                        if date_value:
                            # 使用统一的日期格式转换方法
                            normalized_date = self._normalize_date_format(date_value)
                            if normalized_date:
                                listing_date = normalized_date
                                logger.debug(f"从K线数据获取上市日期: {symbol} -> {listing_date} (原值:{date_value})")
                                break

                # 提取股本信息（如果K线数据中有）
                if 'total_shares' in kdata.columns:
                    shares_value = first_row.get('total_shares')
                    if shares_value and shares_value > 0:
                        total_shares = int(shares_value)
                        logger.debug(f"从K线数据获取总股本: {symbol} -> {total_shares}")

                if 'circulating_shares' in kdata.columns:
                    circ_value = first_row.get('circulating_shares')
                    if circ_value and circ_value > 0:
                        circulating_shares = int(circ_value)
                        logger.debug(f"从K线数据获取流通股本: {symbol} -> {circulating_shares}")

            # 根据资产类型推断货币
            currency = self._infer_currency_from_asset_type(asset_type, stock_market)

            # 构建元数据字典（仅包含非None的字段，避免覆盖已有数据）
            metadata = {
                'symbol': symbol,
                'name': stock_name,
                'market': stock_market,
                'exchange': stock_exchange,
                'asset_type': asset_type.value,
                'listing_status': 'active',
                'currency': currency,
                'base_currency': currency,
                'quote_currency': currency,
                'primary_data_source': task_config.data_source if hasattr(task_config, 'data_source') else 'unknown',
                'data_sources': [task_config.data_source] if hasattr(task_config, 'data_source') else [],
            }

            # 只添加从K线数据中提取到的字段
            if sector:
                metadata['sector'] = sector
            if industry:
                metadata['industry'] = industry
            if industry_code:
                metadata['industry_code'] = industry_code
            if listing_date:
                metadata['listing_date'] = listing_date
            if total_shares:
                metadata['total_shares'] = total_shares
            if circulating_shares:
                metadata['circulating_shares'] = circulating_shares

            logger.debug(f"资产元数据准备完成: {symbol} | 名称:{stock_name} | 行业:{industry} | 板块:{sector} | 上市日期:{listing_date}")

            # 保存元数据
            success = asset_manager.upsert_asset_metadata(symbol, asset_type, metadata)
            if success:
                logger.debug(f"保存资产元数据成功: {symbol} ({stock_name})")
            else:
                logger.warning(f"保存资产元数据失败: {symbol}")

        except Exception as e:
            logger.warning(f"保存资产元数据异常: {symbol}, {e}")

    def _save_asset_metadata_async(self, symbol: str, asset_type, task_config: ImportTaskConfig, kdata: 'pd.DataFrame' = None):
        """
        异步保存资产元数据（避免阻塞主流程）

        将元数据保存操作移到后台线程执行，不阻塞K线数据入队
        """
        try:
            # 优化：使用线程池异步执行元数据保存，避免阻塞
            def save_metadata_task():
                try:
                    self._save_asset_metadata(symbol, asset_type, task_config, kdata)
                except Exception as e:
                    logger.debug(f"异步保存资产元数据失败: {symbol}, {e}")

            # 提交到线程池执行（如果线程池可用）
            if hasattr(self, 'executor') and self.executor:
                self.executor.submit(save_metadata_task)
            else:
                # 如果没有线程池，使用新线程执行
                import threading
                thread = threading.Thread(target=save_metadata_task, daemon=True, name=f"MetadataSaver-{symbol}")
                thread.start()
        except Exception as e:
            logger.debug(f"启动异步元数据保存失败: {symbol}, {e}")

    def _normalize_date_format(self, date_value) -> str:
        """
        统一日期格式转换（根本修复：支持多种格式）

        Args:
            date_value: 日期值，可能是INTEGER (19990727), 字符串 ('1999-07-27', '19990727'), 或datetime对象

        Returns:
            str: YYYY-MM-DD格式的日期字符串，失败返回None
        """
        if date_value is None:
            return None

        try:
            import pandas as pd

            # 如果是整数（YYYYMMDD格式）
            if isinstance(date_value, (int, float)):
                date_str = str(int(date_value))
                if len(date_str) == 8:  # YYYYMMDD
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    return f"{year}-{month}-{day}"
                else:
                    logger.warning(f"日期整数格式不正确: {date_value}")
                    return None

            # 如果是字符串
            elif isinstance(date_value, str):
                date_str = date_value.strip()
                # 如果已经是YYYY-MM-DD格式
                if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
                    return date_str
                # 如果是YYYYMMDD格式字符串
                elif len(date_str) == 8 and date_str.isdigit():
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    return f"{year}-{month}-{day}"
                # 尝试用pandas解析
                else:
                    parsed_date = pd.to_datetime(date_str)
                    return parsed_date.strftime('%Y-%m-%d')

            # 如果是日期对象
            elif isinstance(date_value, date):
                return date_value.strftime('%Y-%m-%d')

            # 如果是datetime对象
            elif isinstance(date_value, (datetime, pd.Timestamp)):
                return pd.to_datetime(date_value).strftime('%Y-%m-%d')

            else:
                logger.warning(f"不支持的日期类型: {type(date_value)}, 值={date_value}")
                return None

        except Exception as e:
            logger.error(f"日期格式转换失败: {date_value}, 错误={e}")
            return None

    def _infer_market_from_symbol(self, symbol: str) -> str:
        """从股票代码推断市场"""
        symbol_clean = symbol.split('.')[0] if '.' in symbol else symbol

        if symbol_clean.startswith('6'):
            return 'sh'  # 上海
        elif symbol_clean.startswith(('0', '3')):
            return 'sz'  # 深圳
        elif symbol_clean.startswith(('4', '8', '9')):
            return 'bj'  # 北京（43xxxx-89xxxx, 92xxxx-92xxxx）
        else:
            return 'unknown'

    def _infer_exchange_from_market(self, market: str) -> str:
        """从市场代码推断交易所名称"""
        exchange_map = {
            'sh': 'SSE',      # 上海证券交易所 (Shanghai Stock Exchange)
            'sz': 'SZSE',     # 深圳证券交易所 (Shenzhen Stock Exchange)
            'bj': 'BSE',      # 北京证券交易所 (Beijing Stock Exchange)
            'hk': 'HKEX',     # 香港交易所 (Hong Kong Exchange)
            'us': 'NASDAQ',   # 纳斯达克（默认，也可能是NYSE）
        }
        return exchange_map.get(market.lower(), market.upper())

    def _infer_currency_from_asset_type(self, asset_type, market: str) -> str:
        """从资产类型和市场推断货币"""
        from ..plugin_types import AssetType

        # 根据资产类型推断
        if asset_type == AssetType.STOCK_A:
            return 'CNY'  # 人民币
        elif asset_type == AssetType.STOCK_HK:
            return 'HKD'  # 港币
        elif asset_type == AssetType.STOCK_US:
            return 'USD'  # 美元
        elif asset_type == AssetType.CRYPTO:
            return 'USDT'  # 加密货币通常用USDT计价
        elif asset_type == AssetType.FUTURES:
            # 期货根据市场判断
            if market in ['sh', 'sz', 'bj']:
                return 'CNY'
            elif market == 'hk':
                return 'HKD'
            else:
                return 'USD'
        else:
            # 默认根据市场判断
            market_currency_map = {
                'sh': 'CNY', 'sz': 'CNY', 'bj': 'CNY',
                'hk': 'HKD',
                'us': 'USD',
            }
            return market_currency_map.get(market.lower(), 'CNY')

    def _write_data_immediately(self, kdata: 'pd.DataFrame', asset_type, data_type) -> bool:
        """立即写入数据到数据库"""
        try:
            from ..asset_database_manager import AssetSeparatedDatabaseManager
            asset_manager = AssetSeparatedDatabaseManager()

            success = asset_manager.store_standardized_data(
                data=kdata,
                asset_type=asset_type,
                data_type=data_type
            )
            return success
        except Exception as e:
            logger.error(f"立即写入数据失败: {e}")
            return False

    def _standardize_kline_data_fields(self, df, data_source: str = None, frequency: str = '1d') -> 'pd.DataFrame':
        """标准化K线数据字段，确保与表结构匹配

        Args:
            df: 输入K线数据
            data_source: 数据源标识
            frequency: 落库频率（DuckDB 格式 1d/1w/1M/1min/...），
                       R292 修复：必须由调用方从任务配置推导后传入，
                       避免分钟数据被默认值 '1d' 误标为日线（污染日线视图）。
        """
        import pandas as pd  # 在函数开头导入，避免后续引用错误

        try:
            if df.empty:
                return df

            # 步骤1: 如果datetime是index，将其重置为列
            if isinstance(df.index, pd.DatetimeIndex):
                logger.debug("检测到DatetimeIndex，转换为datetime列")
                # 修复：检查datetime列是否已存在，避免重复插入
                if 'datetime' not in df.columns:
                    df = df.reset_index()
                    # 如果reset后的列名为'index'或'date'，重命名为datetime
                    if 'index' in df.columns and 'datetime' not in df.columns:
                        df = df.rename(columns={'index': 'datetime'})
                        logger.debug("已将'index'列重命名为'datetime'")
                    elif 'date' in df.columns and 'datetime' not in df.columns:
                        df = df.rename(columns={'date': 'datetime'})
                        logger.debug("已将'date'列重命名为'datetime'")
                else:
                    # datetime列已存在，只需重置索引为默认数字索引
                    df = df.reset_index(drop=True)
                    logger.debug("datetime列已存在，重置为默认索引")

            # 步骤2: 如果有'date'列但没有'datetime'列，重命名
            if 'date' in df.columns and 'datetime' not in df.columns:
                df = df.rename(columns={'date': 'datetime'})
                logger.debug("已将'date'列重命名为'datetime'")

            # 处理字段名称映射（code -> symbol）
            if 'code' in df.columns:
                if 'symbol' not in df.columns:
                    # 如果没有symbol列，将code重命名为symbol
                    df = df.rename(columns={'code': 'symbol'})
                    logger.debug("已将'code'列重命名为'symbol'")
                else:
                    # 如果已有symbol列，删除code列避免冲突
                    df = df.drop('code', axis=1)
                    logger.debug("已删除'code'列(已存在'symbol'列)")

            # 基础字段映射和默认值
            # 标准量化表字段（20字段 - 方案B）+ 行业分类字段（仅用于元数据提取）
            # 包括基础OHLCV、复权数据、扩展交易数据、元数据、行业分类
            field_defaults = {
                # 基础OHLCV字段（8个）
                'symbol': '',
                'datetime': None,
                'open': 0.0,
                'high': 0.0,
                'low': 0.0,
                'close': 0.0,
                'volume': 0,
                'amount': 0.0,
                'turnover': 0.0,

                # 复权数据（2个）- 量化回测必需
                'adj_close': None,      # 复权收盘价
                'adj_factor': 1.0,      # 复权因子（默认1.0=不复权）
                'adj_type': 'none',    # 复权类型 (qfq/hfq/none)
                'adj_source': 'unknown', # 复权数据来源 (plugin/calculated)

                # 扩展交易数据（2个）
                'turnover_rate': None,  # 换手率（行业标准）
                'vwap': None,           # 成交量加权均价（机构常用）

                # 元数据（6个）
                'name': None,
                'market': None,
                'frequency': frequency,  # R292 修复：频率字段由任务配置推导（不再恒为'1d'）
                'period': None,
                'data_source': data_source if data_source else 'unknown',  # 修复：使用传入的data_source参数，而不是硬编码'unknown'
                'created_at': None,
                'updated_at': None,

                # 行业分类字段（3个）- 仅用于传递给_save_asset_metadata，不存入K线表
                'sector': None,         # 板块
                'industry': None,       # 行业
                'industry_code': None,  # 行业代码

                # 涨跌数据
                'change': None,
                'change_pct': None,
            }

            # 添加缺失的必需字段
            for field, default_value in field_defaults.items():
                if field not in df.columns:
                    df[field] = default_value

            # 修复：单独处理data_source字段，确保使用正确的数据源标识
            # 如果传入了data_source参数（来自任务配置），始终使用它（这是最权威的数据源标识）
            if data_source:
                df['data_source'] = data_source
                logger.debug(f"设置data_source字段: {data_source} (来自任务配置)")
            elif 'data_source' not in df.columns:
                # 如果没有传入data_source参数且字段不存在，使用默认值'unknown'
                df['data_source'] = 'unknown'
                logger.warning(f"⚠️ data_source字段不存在且未传入参数，使用默认值'unknown'")

            # 🔧 修复：规范化frequency字段值（关键修复点！）
            if 'frequency' in df.columns:
                # 频率值规范化映射（统一为标准格式）
                frequency_normalization_map = {
                    # 日线
                    'D': '1d', 'd': '1d', 'day': '1d', 'daily': '1d', 'Day': '1d', 'Daily': '1d',
                    '1D': '1d', '1d': '1d',
                    # 周线
                    'W': '1w', 'w': '1w', 'week': '1w', 'weekly': '1w', 'Week': '1w', 'Weekly': '1w',
                    '1W': '1w', '1w': '1w',
                    # 月线
                    'M': '1M', 'm': '1M', 'month': '1M', 'monthly': '1M', 'Month': '1M', 'Monthly': '1M',
                    '1M': '1M',
                    # 分钟线
                    '1': '1min', '1min': '1min', '5': '5min', '5min': '5min',
                    '15': '15min', '15min': '15min', '30': '30min', '30min': '30min',
                    '60': '60min', '60min': '60min', '1H': '60min', '1h': '60min',
                }

                # 应用规范化映射
                def normalize_frequency(freq_value):
                    """规范化频率值"""
                    if pd.isna(freq_value) or freq_value is None or freq_value == '':
                        return '1d'  # 默认值

                    freq_str = str(freq_value).strip()
                    normalized = frequency_normalization_map.get(freq_str)
                    if normalized:
                        if normalized != freq_str:
                            logger.debug(f"🔧 频率规范化: '{freq_str}' -> '{normalized}'")
                        return normalized
                    else:
                        logger.warning(f"⚠️  未知的频率值: '{freq_str}'，使用默认值 '1d'")
                        return '1d'

                # 向量化处理频率列
                original_frequencies = df['frequency'].copy()
                df['frequency'] = df['frequency'].apply(normalize_frequency)

                # 统计频率变化
                changed_mask = original_frequencies != df['frequency']
                if changed_mask.any():
                    change_count = changed_mask.sum()
                    logger.info(f"[频率规范化统计] 共{change_count}条记录的频率被规范化")
                    logger.debug(f"   原始频率分布: {original_frequencies.value_counts().to_dict()}")
                    logger.debug(f"   规范化后频率分布: {df['frequency'].value_counts().to_dict()}")

            # 确保数据类型正确
            numeric_fields = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for field in numeric_fields:
                if field in df.columns:
                    df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)

            # 确保datetime字段格式正确且不为空
            if 'datetime' in df.columns:
                # R292 修复：数值型 datetime（如 20240814）直接 pd.to_datetime 会按纳秒
                # 解释为 1970 假象，先转字符串按 YYYYMMDD 解析（与
                # unified_data_manager._standardize_kdata_format 一致）。
                if pd.api.types.is_numeric_dtype(df['datetime']):
                    df['datetime'] = pd.to_datetime(df['datetime'].astype(str), errors='coerce')
                else:
                    df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
                # 删除datetime为空的行（数据库NOT NULL约束）
                null_datetime_count = df['datetime'].isna().sum()
                if null_datetime_count > 0:
                    logger.warning(f"发现 {null_datetime_count} 条datetime为空的记录，将被过滤")
                    df = df[df['datetime'].notna()]
            else:
                # 如果没有datetime列，尝试使用其他时间列
                time_columns = [col for col in df.columns if 'time' in col.lower() or 'date' in col.lower()]
                if time_columns:
                    logger.warning(f"未找到datetime列，尝试使用 {time_columns[0]}")
                    df['datetime'] = pd.to_datetime(df[time_columns[0]], errors='coerce')
                    df = df[df['datetime'].notna()]
                else:
                    # 最后尝试：检查是否有DatetimeIndex但还没被重置
                    if isinstance(df.index, pd.DatetimeIndex):
                        logger.warning("发现DatetimeIndex但未被重置为datetime列，正在修复")
                        df = df.reset_index()
                        if 'index' in df.columns:
                            df = df.rename(columns={'index': 'datetime'})
                    else:
                        logger.error(f"未找到时间相关列，无法标准化数据。可用列: {df.columns.tolist()}")
                        return pd.DataFrame()

            # 确保symbol字段不为空
            if 'symbol' in df.columns:
                df['symbol'] = df['symbol'].fillna('').astype(str)

            # 删除code列（如果存在），避免与symbol混淆
            if 'code' in df.columns:
                logger.debug("删除code列（已有symbol列）")
                df = df.drop(columns=['code'])

            # 设置默认时间戳
            if 'created_at' in df.columns and df['created_at'].isna().all():
                df['created_at'] = pd.Timestamp.now()

            # 智能计算复权价格（如果数据源没有提供）
            if 'adj_close' in df.columns:
                # 如果adj_close为空但有adj_factor，则计算
                mask = df['adj_close'].isna() & df['adj_factor'].notna()
                if mask.any():
                    df.loc[mask, 'adj_close'] = df.loc[mask, 'close'] * df.loc[mask, 'adj_factor']

                # 如果adj_close和adj_factor都为空，设置adj_close=close（不复权）
                mask = df['adj_close'].isna()
                if mask.any():
                    df.loc[mask, 'adj_close'] = df.loc[mask, 'close']

            # 智能计算VWAP（如果数据源没有提供）
            if 'vwap' in df.columns and df['vwap'].isna().all():
                # vwap = amount / volume
                df['vwap'] = df['amount'] / df['volume'].replace(0, pd.NA)

            # 最终检查：确保datetime字段存在且有效
            if 'datetime' not in df.columns:
                logger.error(f"标准化完成但缺少datetime字段！可用列: {df.columns.tolist()}")
                return pd.DataFrame()  # 返回空DataFrame，避免插入失败

            if df['datetime'].isna().all():
                logger.error(f"标准化完成但datetime字段全为空！")
                return pd.DataFrame()

            logger.info(f"数据字段标准化完成，字段数: {len(df.columns)}, 记录数: {len(df)}")
            logger.debug(f"📋 标准化后的列: {df.columns.tolist()}")
            logger.debug(f"频率分布: {df['frequency'].value_counts().to_dict() if 'frequency' in df.columns else '无频率列'}")
            return df

        except Exception as e:
            logger.error(f"标准化K线数据字段失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return df

    def _enrich_kline_data_with_metadata(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """
        补全K线数据的元数据字段（name, market）

        策略：
        1. 尝试从资产列表获取name和market
        2. 如果失败，从symbol推断market
        3. name无法推断则保持为空

        Args:
            df: K线数据DataFrame

        Returns:
            补全后的DataFrame
        """
        import pandas as pd

        try:
            if df.empty or 'symbol' not in df.columns:
                logger.warning("数据为空或缺少symbol字段，跳过元数据补全")
                return df

            logger.info(f"开始补全K线数据元数据: {len(df)} 条记录")

            # 策略1: 尝试从资产列表获取name和market
            try:
                from ..services.unified_data_manager import get_unified_data_manager
                unified_manager = get_unified_data_manager()

                if unified_manager:
                    # 获取资产列表
                    asset_list_df = unified_manager.get_asset_list()

                    if not asset_list_df.empty:
                        # 准备映射字典
                        symbol_to_info = {}
                        if 'symbol' in asset_list_df.columns:
                            sym_col = 'symbol'
                        elif 'code' in asset_list_df.columns:
                            sym_col = 'code'
                        else:
                            sym_col = asset_list_df.columns[0]
                        for row in asset_list_df.itertuples(index=False):
                            key = getattr(row, sym_col, '')
                            name_val = str(getattr(row, 'name', '')) if pd.notna(getattr(row, 'name', None)) else ''
                            market_val = str(getattr(row, 'market', '')) if pd.notna(getattr(row, 'market', None)) else ''
                            if key:
                                symbol_to_info[key] = {'name': name_val, 'market': market_val}

                        # 补全name字段
                        if 'name' in df.columns:
                            missing_name = df['name'].isna() | (df['name'] == '')
                            if missing_name.any():
                                lookup = df.loc[missing_name, 'symbol'].map(
                                    lambda s: symbol_to_info.get(s, {}).get('name', None)
                                )
                                df.loc[missing_name, 'name'] = lookup
                            enriched_count = df['name'].notna().sum()
                            logger.info(f"从资产列表补全了 {enriched_count} 条记录的name字段")

                        # 补全market字段
                        if 'market' in df.columns:
                            missing_market = df['market'].isna() | (df['market'] == '')
                            if missing_market.any():
                                lookup = df.loc[missing_market, 'symbol'].map(
                                    lambda s: symbol_to_info.get(s, {}).get('market', None)
                                )
                                df.loc[missing_market, 'market'] = lookup
                            enriched_count = df['market'].notna().sum()
                            logger.info(f"从资产列表补全了 {enriched_count} 条记录的market字段")
                    else:
                        logger.debug("资产列表为空，将使用symbol推断market")
                else:
                    logger.debug("UnifiedDataManager不可用，将使用symbol推断market")

            except Exception as e:
                logger.debug(f"从资产列表补全元数据失败（非关键错误）: {e}")

            # 策略2: 从symbol推断market（作为后备或补充）
            if 'market' in df.columns:
                # 向量化: 基于symbol的前缀/后缀批量推断market
                symbols = df['symbol'].astype(str)
                result_market = pd.Series('unknown', index=df.index)

                # 保留已有有效market
                if 'market' in df.columns:
                    existing_valid = df['market'].notna() & (df['market'] != '') & (df['market'] != 'unknown')
                    result_market[existing_valid] = df.loc[existing_valid, 'market']

                # 后缀推断
                unknown_mask = result_market == 'unknown'
                result_market[unknown_mask & symbols.str.endswith('.SH')] = 'SH'
                unknown_mask = result_market == 'unknown'
                result_market[unknown_mask & symbols.str.endswith('.SZ')] = 'SZ'
                unknown_mask = result_market == 'unknown'
                result_market[unknown_mask & symbols.str.endswith('.BJ')] = 'BSE'

                # 前缀推断
                unknown_mask = result_market == 'unknown'
                if unknown_mask.any():
                    codes = symbols[unknown_mask].str.split('.').str[0]
                    first_char = codes.str[0]
                    result_market[unknown_mask & (first_char == '6')] = 'SH'
                    result_market[unknown_mask & first_char.isin(['0', '3'])] = 'SZ'
                    result_market[unknown_mask & first_char.isin(['4', '8', '9'])] = 'BSE'

                df['market'] = result_market
                inferred_count = (df['market'] != 'unknown').sum()
                logger.info(f"从symbol推断了 {inferred_count} 条记录的market字段")

            # 策略3: 统计补全结果
            stats = {
                'total_records': len(df),
                'name_filled': df['name'].notna().sum() if 'name' in df.columns else 0,
                'market_filled': df['market'].notna().sum() if 'market' in df.columns else 0,
            }

            logger.info(f"元数据补全完成: "
                        f"总记录={stats['total_records']}, "
                        f"name填充率={stats['name_filled']/stats['total_records']*100:.1f}%, "
                        f"market填充率={stats['market_filled']/stats['total_records']*100:.1f}%")

            return df

        except Exception as e:
            logger.error(f"补全K线数据元数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return df

    def _import_realtime_data(self, task_config: ImportTaskConfig, result: TaskExecutionResult):
        """导入实时行情数据"""
        try:
            symbols = task_config.symbols
            result.total_records = len(symbols)

            for i, symbol in enumerate(symbols):
                if result.status == TaskExecutionStatus.CANCELLED:
                    break

                try:
                    # 获取实时行情数据
                    quote_data = self.real_data_provider.get_real_quote(symbol)

                    if quote_data:
                        logger.info(f"成功获取 {symbol} 的实时行情数据")
                        result.processed_records += 1
                    else:
                        logger.warning(f"未获取到 {symbol} 的实时行情数据")
                        result.failed_records += 1

                except Exception as e:
                    logger.error(f"导入 {symbol} 实时行情失败: {e}")
                    result.failed_records += 1

                time.sleep(0.05)  # 实时数据处理更快

        except Exception as e:
            raise Exception(f"实时行情导入失败: {e}")

    def _import_single_symbol_kline(self, symbol: str, index: int, total: int, task_config: ImportTaskConfig) -> dict:
        """
        导入单个股票的K线数据（用于并行处理）

        Returns:
            dict: {'symbol': str, 'success': bool, 'record_count': int, 'error': str}
        """
        import time
        import threading

        task_start_time = time.time()
        thread_id = threading.current_thread().name

        try:
            # 修复：在执行前检查任务是否已取消
            if hasattr(self, '_task_results') and task_config.task_id in self._task_results:
                task_result = self._task_results[task_config.task_id]
                if task_result.status == TaskExecutionStatus.CANCELLED:
                    logger.info(f"⚠️ [任务已取消] {symbol} 跳过执行")
                    return {'symbol': symbol, 'success': False, 'record_count': 0, 'error': '任务已取消'}

            logger.info(f"🔵 [开始] {symbol} ({index+1}/{total}) | 线程:{thread_id}")
            
            # 记录任务描述和数据用途
            if task_config.description:
                logger.debug(f"📝 [任务描述] {task_config.description}")
            logger.debug(f"[数据用途] {task_config.data_usage}")
            
            # 根据数据用途调整数据验证策略
            strict_validation = False
            if task_config.data_usage == "backtest":
                strict_validation = True
                logger.debug(f"[验证策略] 回测用途：启用严格验证")
            elif task_config.data_usage == "live_trading":
                strict_validation = True
                logger.debug(f"[验证策略] 实盘用途：启用严格验证")

            # 1. 从真实数据提供者获取K线数据（关键监控点1：网络请求）
            # 支持多种复权类型自动获取
            network_start = time.time()
            logger.debug(f"⏱️  [网络请求开始] {symbol} | 线程:{thread_id}")

            logger.debug(f"📝 [调用参数] code={symbol}, freq={task_config.frequency.value if hasattr(task_config.frequency, 'value') else task_config.frequency}, "
                         f"asset_type={task_config.asset_type}, data_source={task_config.data_source}")

            adjustment_types = self._get_plugin_adjustment_types(task_config.data_source)
            logger.info(f"[复权类型] {symbol} 支持的复权类型: {adjustment_types}")

            all_record_count = 0
            
            # 优化策略：只下载不复权数据，其他复权类型本地计算
            # 1. 首先下载不复权数据（网络请求）
            kdata = self.real_data_provider.get_real_kdata(
                code=symbol,
                freq=task_config.frequency.value if hasattr(task_config.frequency, 'value') else str(task_config.frequency),
                start_date=task_config.start_date,
                end_date=task_config.end_date,
                data_source=task_config.data_source,
                asset_type=task_config.asset_type,
                adjustment='none'
            )

            if kdata is None or kdata.empty:
                logger.warning(f"[不复权数据为空] {symbol}，无法获取基础数据")
                return {'symbol': symbol, 'success': False, 'record_count': 0, 'error': '无法获取不复权数据'}

            if 'adj_type' not in kdata.columns:
                kdata['adj_type'] = 'none'
            if 'adj_source' not in kdata.columns:
                kdata['adj_source'] = 'plugin'
            if 'adj_close' not in kdata.columns:
                kdata['adj_close'] = kdata['close']
                kdata['adj_factor'] = 1.0

            logger.info(f"[不复权数据获取成功] {symbol} | 条数:{len(kdata)}")

            # 保存不复权数据
            db_start = time.time()
            self._save_kdata_to_database(symbol, kdata, task_config)
            db_elapsed = time.time() - db_start
            logger.debug(f"[不复权数据入队完成] {symbol}, 入队耗时:{db_elapsed:.2f}秒")
            all_record_count += len(kdata)

            # 2. 本地计算前复权和后复权（如果有需要）
            for adj_type in ['qfq', 'hfq']:
                if adj_type not in adjustment_types:
                    logger.debug(f"[复权计算] {symbol} 跳过 {adj_type}（插件不支持）")
                    continue

                logger.debug(f"[复权计算] {symbol} 正在计算 {adj_type}")

                # 复制不复权数据作为基础
                adj_kdata = kdata.copy()

                # 计算复权价格
                calculated_kdata = self._calculate_adjustment_local_fast(symbol, adj_kdata, adj_type)

                if calculated_kdata is None or calculated_kdata.empty:
                    logger.warning(f"[复权计算失败] {symbol} 复权类型={adj_type}")
                    continue

                if 'adj_type' not in calculated_kdata.columns:
                    calculated_kdata['adj_type'] = adj_type
                if 'adj_source' not in calculated_kdata.columns:
                    calculated_kdata['adj_source'] = 'calculated'

                logger.info(f"[复权计算成功] {symbol} 复权类型={adj_type} | 条数:{len(calculated_kdata)}")

                # 保存复权数据
                db_start = time.time()
                self._save_kdata_to_database(symbol, calculated_kdata, task_config)
                db_elapsed = time.time() - db_start
                logger.debug(f"[复权数据入队完成] {symbol} 复权类型={adj_type}, 入队耗时:{db_elapsed:.2f}秒")
                all_record_count += len(calculated_kdata)

            network_elapsed = time.time() - network_start
            logger.info(f"⏱️  [网络请求完成] {symbol} | 耗时:{network_elapsed:.2f}秒 | 线程:{thread_id}")

            if all_record_count == 0:
                logger.warning(f"❌ [数据为空] {symbol} | 所有复权类型均无法获取数据")
                return {'symbol': symbol, 'success': False, 'record_count': 0, 'error': '所有复权类型均无法获取数据'}

            # 2. 数据质量验证
            if self.enable_data_quality_monitoring or strict_validation:
                validation_start = time.time()
                validation_result = self._validate_imported_data(
                    task_id=task_config.task_id,
                    data=kdata,
                    data_source=task_config.data_source,
                    data_type='kdata',
                    strict_validation=strict_validation  # 根据数据用途调整验证严格度
                )
                validation_elapsed = time.time() - validation_start
                logger.debug(f"⏱️  [质量验证] {symbol} | 评分:{validation_result.quality_score:.3f} | 严格度:{strict_validation} | 耗时:{validation_elapsed:.2f}秒")

            # 3. 保存K线数据到数据库（关键监控点2：数据库写入）
            db_start = time.time()
            logger.debug(f"⏱️  [数据库写入开始] {symbol} | 线程:{thread_id}")

            # 🔧 修复：添加asset_type调试日志
            logger.debug(f"📝 [资产类型] 原始值={task_config.asset_type}, 类型={type(task_config.asset_type)}")

            # 修复：记录队列状态，便于分析性能问题
            queue_size_before = self.db_writer_thread.write_queue.qsize() if hasattr(self, 'db_writer_thread') else 0

            self._save_kdata_to_database(symbol, kdata, task_config)

            # 修复：只计算放入队列的时间，不包含等待队列消费的时间
            # 真正的数据库写入是异步的，在DatabaseWriterThread中完成
            db_elapsed = time.time() - db_start
            queue_size_after = self.db_writer_thread.write_queue.qsize() if hasattr(self, 'db_writer_thread') else 0

            logger.info(f"⏱️  [数据入队完成] {symbol} | 入队耗时:{db_elapsed:.2f}秒 | 队列大小:{queue_size_before}→{queue_size_after} | 线程:{thread_id}")

            # 异步触发基本面数据下载（在 K 线数据成功获取后）
            # 🔧 修复：只在用户启用基本面数据下载时才触发
            if task_config.enable_fundamental_download:
                logger.debug(f"[基本面] {symbol} | 用户启用基本面数据下载，开始异步下载...")
                self._async_download_fundamental_data(symbol, task_config)
            else:
                logger.debug(f"[基本面] {symbol} | 用户未启用基本面数据下载，跳过")

            total_elapsed = time.time() - task_start_time
            logger.info(f"🟢 [完成] {symbol} | 总耗时:{total_elapsed:.2f}秒 | 总记录:{all_record_count} | 线程:{thread_id}")

            return {'symbol': symbol, 'success': True, 'record_count': all_record_count, 'error': None}

        except Exception as e:
            error_msg = str(e)
            total_elapsed = time.time() - task_start_time
            logger.error(f"🔴 [失败] {symbol} | 总耗时:{total_elapsed:.2f}秒 | 错误:{error_msg} | 线程:{thread_id}")
            logger.error(f"📋 [调试信息] 任务配置: task_id={task_config.task_id}, asset_type={task_config.asset_type}, data_source={task_config.data_source}")
            import traceback
            logger.error(traceback.format_exc())
            return {'symbol': symbol, 'success': False, 'record_count': 0, 'error': error_msg}

    def _get_plugin_adjustment_types(self, data_source: str = None) -> List[str]:
        """获取插件支持的复权类型"""
        try:
            if not self._real_data_provider_initialized:
                self._ensure_real_data_provider()

            if self.real_data_provider and hasattr(self.real_data_provider, '_get_plugin_adjustment_types'):
                return self.real_data_provider._get_plugin_adjustment_types(data_source)

            return ['none']
        except Exception as e:
            logger.debug(f"获取插件复权类型失败: {e}")
            return ['none']

    def _calculate_adjustment_local(self, symbol: str, task_config: ImportTaskConfig, adj_type: str) -> 'pd.DataFrame':
        """本地计算复权数据"""
        try:
            if adj_type == 'none':
                return pd.DataFrame()

            from core.utils.adjustment_calculator import get_adjustment_calculator
            calculator = get_adjustment_calculator()

            base_kdata = self.real_data_provider.get_real_kdata(
                code=symbol,
                freq=task_config.frequency.value if hasattr(task_config.frequency, 'value') else str(task_config.frequency),
                start_date=task_config.start_date,
                end_date=task_config.end_date,
                data_source=task_config.data_source,
                asset_type=task_config.asset_type,
                adjustment='none'
            )

            if base_kdata is None or base_kdata.empty:
                return pd.DataFrame()

            adjusted_kdata = calculator.calculate_adjustment(base_kdata, symbol, adj_type)

            logger.info(f"[本地复权计算] {symbol} 复权类型={adj_type}, 原始数据={len(base_kdata)}条")
            return adjusted_kdata

        except Exception as e:
            logger.error(f"[本地复权计算失败] {symbol} 复权类型={adj_type}: {e}")
            return pd.DataFrame()

    def _calculate_adjustment_local_fast(self, symbol: str, base_kdata: 'pd.DataFrame', adj_type: str) -> 'pd.DataFrame':
        """快速本地计算复权数据（基于已有不复权数据）"""
        try:
            if adj_type == 'none':
                return base_kdata

            if base_kdata is None or base_kdata.empty:
                return pd.DataFrame()

            from core.utils.adjustment_calculator import get_adjustment_calculator
            calculator = get_adjustment_calculator()

            adjusted_kdata = calculator.calculate_adjustment(base_kdata, symbol, adj_type)

            logger.info(f"[本地快速复权计算] {symbol} 复权类型={adj_type}, 原始数据={len(base_kdata)}条")
            return adjusted_kdata

        except Exception as e:
            logger.error(f"[本地快速复权计算失败] {symbol} 复权类型={adj_type}: {e}")
            return pd.DataFrame()

    def _import_kline_data(self, task_config: ImportTaskConfig, result: TaskExecutionResult):
        """导入K线数据（支持并行处理）"""
        try:
            # 确保真实数据提供器已初始化
            if not self._real_data_provider_initialized:
                self._ensure_real_data_provider()

            if self.real_data_provider is None:
                raise Exception("真实数据提供器初始化失败，无法导入K线数据")

            symbols = task_config.symbols
            # 修复：如果total_records已设置（从进度恢复），不要覆盖
            if result.total_records == 0:
                result.total_records = len(symbols)

            # 修复：初始化已处理股票列表（用于进度恢复）
            processed_symbols_set = set()
            if hasattr(result, 'processed_symbols_list') and result.processed_symbols_list:
                processed_symbols_set = set(result.processed_symbols_list)
                logger.debug(f"📋 [进度恢复] 从result恢复已处理股票列表: {len(processed_symbols_set)}个股票")

            # 使用max_workers进行并行处理
            max_workers = min(task_config.max_workers, len(symbols)) if hasattr(task_config, 'max_workers') else 1

            if max_workers > 1:
                logger.info(f"[并行模式] 开始导入: {len(symbols)}个股票，max_workers={max_workers}")
                logger.info(f"[任务队列] 已提交{len(symbols)}个任务到线程池，等待执行...")

                from concurrent.futures import ThreadPoolExecutor, as_completed
                import threading
                import time

                # 创建线程锁用于更新result（线程安全）
                result_lock = threading.Lock()
                batch_start_time = time.time()

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有任务
                    future_to_symbol = {
                        executor.submit(self._import_single_symbol_kline, symbol, i, len(symbols), task_config): symbol
                        for i, symbol in enumerate(symbols)
                    }

                    logger.info(f"[线程池状态] 已提交所有任务，开始执行...")

                    # 收集结果
                    completed_count = 0
                    for future in as_completed(future_to_symbol):
                        completed_count += 1

                        # 检查取消状态
                        if result.status == TaskExecutionStatus.CANCELLED:
                            logger.info("⚠️ [任务取消] 停止导入")
                            executor.shutdown(wait=False)
                            break

                        try:
                            import_result = future.result(timeout=300)  # 5分钟超时

                            symbol = import_result['symbol']
                            with result_lock:
                                if import_result['success']:
                                    result.processed_records += 1
                                    processed_symbols_set.add(symbol)  # 记录已处理的股票
                                else:
                                    result.failed_records += 1
                                    # 失败也记录，避免重复尝试（可根据需要调整）
                                    processed_symbols_set.add(symbol)

                            # 修复：实时更新进度（包含已处理股票列表）
                            progress = ImportProgress(
                                task_id=task_config.task_id,
                                status=ImportStatus.RUNNING,
                                total_symbols=len(symbols),
                                processed_symbols=result.processed_records + result.failed_records,
                                total_records=result.total_records,
                                imported_records=result.processed_records,
                                error_count=result.failed_records,
                                start_time=result.start_time.isoformat() if result.start_time else datetime.now().isoformat(),
                                end_time=None,
                                error_message=None,
                                processed_symbols_list=list(processed_symbols_set)  # 保存已处理股票列表
                            )
                            self.config_manager.update_progress(progress)

                            # 更新进度
                            progress_ratio = (result.processed_records + result.failed_records) / result.total_records
                            elapsed = time.time() - batch_start_time
                            avg_time = elapsed / completed_count if completed_count > 0 else 0
                            eta = avg_time * (len(symbols) - completed_count) if completed_count > 0 else 0

                            logger.info(f"[进度] {completed_count}/{len(symbols)} | 成功:{result.processed_records} 失败:{result.failed_records} | 平均耗时:{avg_time:.2f}s | 预计剩余:{eta:.1f}s")

                            # 修复：在进度消息中包含错误信息（如果失败），以便UI可以提取并记录到错误表
                            if import_result['success']:
                                progress_message = f"导入股票数据: {symbol} ({result.processed_records + result.failed_records}/{result.total_records})"
                            else:
                                error_info = import_result.get('error', '未知错误')
                                progress_message = f"导入股票数据: {symbol} ({result.processed_records + result.failed_records}/{result.total_records}) | {symbol}失败: {error_info}"

                            self.task_progress.emit(
                                task_config.task_id,
                                progress_ratio,
                                progress_message
                            )

                        except TimeoutError:
                            symbol = future_to_symbol[future]
                            logger.error(f"⏰ [超时] {symbol} 执行超过300秒，future.result()超时")
                            with result_lock:
                                result.failed_records += 1
                                processed_symbols_set.add(symbol)  # 超时也记录
                        except Exception as e:
                            symbol = future_to_symbol[future]
                            logger.error(f"🔴 [异常] {symbol} 处理结果失败: {e}")
                            with result_lock:
                                result.failed_records += 1
                                processed_symbols_set.add(symbol)  # 异常也记录

                total_elapsed = time.time() - batch_start_time
                logger.info(f"[并行完成] 总耗时:{total_elapsed:.2f}秒 | 成功:{result.processed_records} 失败:{result.failed_records}")

                # 修复：将已处理股票列表设置到result中
                result.processed_symbols_list = list(processed_symbols_set)
            else:
                logger.info(f"开始串行导入K线数据: {len(symbols)}个股票")

                for i, symbol in enumerate(symbols):
                    if result.status == TaskExecutionStatus.CANCELLED:
                        logger.info("任务被取消，停止导入")
                        break

                    import_result = self._import_single_symbol_kline(symbol, i, len(symbols), task_config)

                    if import_result['success']:
                        result.processed_records += 1
                        processed_symbols_set.add(symbol)  # 记录已处理的股票
                    else:
                        result.failed_records += 1
                        processed_symbols_set.add(symbol)  # 失败也记录

                    # 修复：实时更新进度（包含已处理股票列表）
                    progress = ImportProgress(
                        task_id=task_config.task_id,
                        status=ImportStatus.RUNNING,
                        total_symbols=len(symbols),
                        processed_symbols=result.processed_records + result.failed_records,
                        total_records=result.total_records,
                        imported_records=result.processed_records,
                        error_count=result.failed_records,
                        start_time=result.start_time.isoformat() if result.start_time else datetime.now().isoformat(),
                        end_time=None,
                        error_message=None,
                        processed_symbols_list=list(processed_symbols_set)  # 保存已处理股票列表
                    )
                    self.config_manager.update_progress(progress)

                    # 修复：在进度消息中包含错误信息（如果失败），以便UI可以提取并记录到错误表
                    if import_result['success']:
                        progress_message = f"导入股票数据: {symbol} ({i+1}/{len(symbols)})"
                    else:
                        error_info = import_result.get('error', '未知错误')
                        progress_message = f"导入股票数据: {symbol} ({i+1}/{len(symbols)}) | {symbol}失败: {error_info}"

                    # 更新进度
                    progress_ratio = (i + 1) / len(symbols)
                    self.task_progress.emit(
                        task_config.task_id,
                        progress_ratio,
                        progress_message
                    )

                # 修复：将已处理股票列表设置到result中
                result.processed_symbols_list = list(processed_symbols_set)

                # 控制请求频率
                time.sleep(0.1)

            logger.info(f"K线数据导入完成: 成功 {result.processed_records}/{result.total_records}, 失败 {result.failed_records}")

        except Exception as e:
            logger.error(f"K线数据导入失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise Exception(f"K线数据导入失败: {e}")

    def _import_fundamental_data(self, task_config: ImportTaskConfig, result: TaskExecutionResult):
        """导入基本面数据"""
        try:
            symbols = task_config.symbols
            result.total_records = len(symbols)

            for i, symbol in enumerate(symbols):
                if result.status == TaskExecutionStatus.CANCELLED:
                    break

                try:
                    # 获取基本面数据（使用 data_manager 统一接口）
                    fundamental_data = self.data_manager.get_fundamental_data(
                        symbol,
                        asset_type=task_config.asset_type,
                        data_source=task_config.data_source
                    )

                    if fundamental_data:
                        # 将基本面数据转换为DataFrame并保存
                        if isinstance(fundamental_data, (dict, list)):
                            import pandas as pd
                            if isinstance(fundamental_data, dict):
                                fund_df = pd.DataFrame([fundamental_data])
                            else:
                                fund_df = pd.DataFrame(fundamental_data)
                            self._save_fundamental_data_to_database(symbol, fund_df, "基本面数据", task_config.asset_type)
                        logger.info(f"成功导入并保存 {symbol} 的基本面数据")
                        result.processed_records += 1
                    else:
                        logger.warning(f"未获取到 {symbol} 的基本面数据")
                        result.failed_records += 1

                except Exception as e:
                    logger.error(f"导入 {symbol} 基本面数据失败: {e}")
                    result.failed_records += 1

                time.sleep(0.2)  # 基本面数据处理较慢

        except Exception as e:
            raise Exception(f"基本面数据导入失败: {e}")

    def _update_progress(self):
        """更新任务进度"""
        with self._task_lock:
            for task_id, result in self._task_results.items():
                if result.status == TaskExecutionStatus.RUNNING:
                    progress = result.progress_percentage
                    message = f"已处理 {result.processed_records}/{result.total_records} 条记录"

                    # 使用监控功能发送进度信号
                    self._monitor_task_progress(task_id, progress, message)

    # ==================== 基本面数据异步下载功能 ====================

    def _async_download_fundamental_data(self, symbol: str, task_config: ImportTaskConfig):
        """异步下载基本面数据（在K线数据成功获取后触发）

        Args:
            symbol: 股票代码
            task_config: 任务配置（包含数据源和资产类型信息）
        """
        try:
            self.fundamental_executor.submit(
                self._download_and_save_fundamental_data,
                symbol,
                task_config
            )
        except Exception as e:
            logger.warning(f"⚠️  [基本面] {symbol} | 异步下载任务提交失败: {e}")

    def _download_and_save_fundamental_data(self, symbol: str, task_config: ImportTaskConfig):
        """下载并保存基本面数据（在独立线程中执行）

        Args:
            symbol: 股票代码
            task_config: 任务配置
        """
        self._ensure_data_manager()

        if self.data_manager is None:
            logger.warning(f"⚠️  [基本面] {symbol} | 数据管理器未初始化，尝试降级获取...")
            fundamental_data = self._get_fundamental_data_fallback(symbol, task_config)
            if fundamental_data:
                self._save_fundamental_data_to_database(symbol, fundamental_data, task_config)
            return

        try:
            logger.debug(f"[基本面] {symbol} | 开始下载基本面数据...")

            fundamental_data = self.data_manager.get_fundamental_data(
                symbol,
                asset_type=task_config.asset_type,
                data_source=task_config.data_source
            )

            if fundamental_data and len(fundamental_data) > 0:
                import pandas as pd
                fund_df = pd.DataFrame([fundamental_data])

                self._save_fundamental_data_to_database(
                    symbol,
                    fund_df,
                    task_config
                )

                logger.info(f"[基本面] {symbol} | 数据已保存到数据库")
            else:
                logger.debug(f"⚠️  [基本面] {symbol} | 未获取到基本面数据，尝试降级获取...")
                fundamental_data = self._get_fundamental_data_fallback(symbol, task_config)
                if fundamental_data is not None:
                    self._save_fundamental_data_to_database(symbol, fundamental_data, task_config)

        except Exception as e:
            logger.error(f"❌ [基本面] {symbol} | 下载失败: {e}，尝试降级获取...")
            import traceback
            logger.debug(traceback.format_exc())
            try:
                fundamental_data = self._get_fundamental_data_fallback(symbol, task_config)
                if fundamental_data is not None:
                    self._save_fundamental_data_to_database(symbol, fundamental_data, task_config)
            except Exception as fallback_error:
                logger.error(f"❌ [基本面] {symbol} | 降级获取也失败: {fallback_error}")

    def _save_fundamental_data_to_database(self, symbol: str, fund_df: 'pd.DataFrame', task_config: ImportTaskConfig):
        """保存基本面数据到数据库（使用写入队列）

        Args:
            symbol: 股票代码
            fund_df: 基本面数据DataFrame
            task_config: 任务配置
        """
        try:
            from ..plugin_types import DataType

            # 标准化数据字段
            fund_df = self._standardize_fundamental_data_fields(fund_df, symbol, data_source=task_config.data_source)

            # asset_type 可能是字符串或枚举类型，需要处理
            asset_type_str = task_config.asset_type.value if hasattr(task_config.asset_type, 'value') else str(task_config.asset_type)
            buffer_key = f"{asset_type_str}_{task_config.task_id}_fundamental"

            write_task = WriteTask(
                buffer_key=buffer_key,
                data=fund_df.copy(),
                asset_type=task_config.asset_type,
                data_type=DataType.FUNDAMENTAL
            )

            success = self.db_writer_thread.put_write_task(write_task, timeout=10.0)

            if success:
                logger.debug(f"💾 [基本面] {symbol} | 数据已入队保存")
            else:
                logger.error(f"❌ [基本面] {symbol} | 数据入队失败")

        except Exception as e:
            logger.error(f"❌ [基本面] {symbol} | 保存到数据库失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _get_fundamental_data_fallback(self, symbol: str, task_config: ImportTaskConfig):
        """降级获取基本面数据 - 尝试其他数据源插件

        Args:
            symbol: 股票代码
            task_config: 任务配置

        Returns:
            DataFrame or None: 基本面数据DataFrame
        """
        import pandas as pd

        fallback_plugins = [
            'eastmoney_stock_data_source',
            'akshare_stock_data_source',
            'tushare_stock_data_source',
            'tongdaxin_stock_plugin'
        ]

        for plugin_id in fallback_plugins:
            try:
                logger.info(f"[基本面降级] {symbol} | 尝试数据源: {plugin_id}")
                plugin = self._get_data_source_plugin(plugin_id)

                if plugin is None:
                    continue

                if hasattr(plugin, 'get_fundamental_data'):
                    data = plugin.get_fundamental_data(symbol)
                    if data and isinstance(data, dict) and len(data) > 0:
                        fund_df = pd.DataFrame([data])
                        logger.info(f"[基本面降级] {symbol} | 从 {plugin_id} 获取成功")
                        return fund_df
                    else:
                        logger.debug(f"[基本面降级] {symbol} | {plugin_id} 返回空数据")

            except Exception as e:
                logger.debug(f"[基本面降级] {symbol} | {plugin_id} 获取失败: {e}")
                continue

        logger.warning(f"[基本面降级] {symbol} | 所有降级数据源均失败")
        return None

    def _normalize_date_format(self, date_value) -> Optional[str]:
        """标准化日期格式为 YYYY-MM-DD

        Args:
            date_value: 日期值，可能是字符串、datetime或其他格式

        Returns:
            标准化后的日期字符串 (YYYY-MM-DD) 或 None
        """
        if date_value is None or (isinstance(date_value, str) and date_value.strip() == ''):
            return None

        # 如果已经是 datetime 对象
        if isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%d')

        # 如果是 pandas Timestamp
        try:
            import pandas as pd
            if isinstance(date_value, pd.Timestamp):
                return date_value.strftime('%Y-%m-%d')
        except ImportError:
            pass

        # 字符串格式转换
        date_str = str(date_value).strip()

        # YYYYMMDD -> YYYY-MM-DD
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # YYYY-MM-DD (已经是正确格式)
        if len(date_str) == 10 and '-' in date_str:
            return date_str

        # YYYY/MM/DD -> YYYY-MM-DD
        if len(date_str) == 10 and '/' in date_str:
            return date_str.replace('/', '-')

        # 尝试解析其他格式
        try:
            from datetime import datetime as dt
            parsed = dt.strptime(date_str, '%Y-%m-%d')
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            pass

        try:
            from datetime import datetime as dt
            parsed = dt.strptime(date_str, '%Y/%m/%d')
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            pass

        logger.warning(f"无法解析日期格式: {date_value}")
        return None

    def _standardize_fundamental_data_fields(self, fund_df: 'pd.DataFrame', symbol: str, data_source: str) -> 'pd.DataFrame':
        """标准化基本面数据字段，确保与数据库表结构匹配

        Args:
            fund_df: 原始基本面数据DataFrame
            symbol: 股票代码（用于填充缺失的symbol字段）
            data_source: 数据源名称

        Returns:
            标准化后的DataFrame
        """
        try:
            import pandas as pd

            # 确保symbol字段存在，如果不存在则添加
            if 'symbol' not in fund_df.columns:
                logger.warning("基本面数据缺少symbol字段，自动填充")
                fund_df['symbol'] = symbol

            # 字段映射（将插件返回的字段名映射到数据库表结构）
            # 数据库表结构（来自AssetSeparatedDatabaseManager）：
            # symbol, name, market, industry, sector, list_date,
            # total_shares, float_shares, market_cap, status, currency, is_st,
            # updated_time, created_at
            field_mapping = {
                'total_shares': 'total_shares',
                'circulating_shares': 'float_shares',
                'total_market_cap': 'market_cap',
                'industry': 'industry',
                'list_date': 'list_date'
            }

            # 重命名字段
            fund_df = fund_df.rename(columns=field_mapping)

            # 标准化 list_date 字段格式 (YYYYMMDD -> YYYY-MM-DD)
            if 'list_date' in fund_df.columns:
                fund_df['list_date'] = fund_df['list_date'].apply(self._normalize_date_format)

            # 添加created_at字段
            fund_df['created_at'] = datetime.now()

            # 添加updated_time字段（注意：数据库使用的是updated_time，不是updated_at）
            fund_df['updated_time'] = datetime.now()

            # 确保必需字段存在（如果不存在则设置为NULL）
            required_fields = [
                'symbol', 'name', 'market', 'industry', 'sector',
                'list_date', 'total_shares', 'float_shares', 'market_cap',
                'status', 'currency', 'is_st',
                'created_at', 'updated_time'
            ]

            for field in required_fields:
                if field not in fund_df.columns:
                    fund_df[field] = None

            logger.debug(f"基本面数据字段标准化完成: {fund_df.columns.tolist()}")
            return fund_df

        except Exception as e:
            logger.error(f"基本面数据字段标准化失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return fund_df

    # ==================== 智能配置管理功能 ====================

    def _apply_intelligent_optimization(self, config: ImportTaskConfig,
                                        optimization_level: ConfigOptimizationLevel = ConfigOptimizationLevel.BALANCED) -> Optional[ImportTaskConfig]:
        """应用智能配置优化"""
        if not self.enable_intelligent_config or not isinstance(self.config_manager, IntelligentConfigManager):
            return None

        try:
            logger.info(f"开始智能配置优化: {config.task_id}")

            # 使用智能配置管理器生成优化配置
            optimized_config = self.config_manager.generate_intelligent_config(
                config,
                optimization_level
            )

            logger.info(f"智能配置优化完成: {config.task_id}")
            return optimized_config

        except Exception as e:
            logger.error(f"智能配置优化失败: {e}")
            return None

    def generate_config_recommendations(self, task_id: str,
                                        recommendation_type: ConfigRecommendationType = ConfigRecommendationType.BALANCED) -> List[Dict[str, Any]]:
        """生成配置推荐"""
        if not self.enable_intelligent_config or not isinstance(self.config_manager, IntelligentConfigManager):
            return []

        try:
            recommendations = self.config_manager.generate_config_recommendations(
                task_id, recommendation_type
            )

            # 转换为字典格式便于UI显示
            return [
                {
                    'recommendation_id': rec.recommendation_id,
                    'recommendation_type': rec.recommendation_type.value,
                    'recommended_changes': rec.recommended_changes,
                    'expected_improvement': rec.expected_improvement,
                    'confidence_score': rec.confidence_score,
                    'reasoning': rec.reasoning,
                    'created_at': rec.created_at
                }
                for rec in recommendations
            ]

        except Exception as e:
            logger.error(f"生成配置推荐失败: {e}")
            return []

    def detect_and_resolve_config_conflicts(self, auto_resolve: bool = True) -> Dict[str, Any]:
        """检测并解决配置冲突"""
        if not self.enable_intelligent_config or not isinstance(self.config_manager, IntelligentConfigManager):
            return {'conflicts_detected': 0, 'conflicts_resolved': 0, 'message': '智能配置未启用'}

        try:
            # 检测配置冲突
            conflicts = self.config_manager.detect_config_conflicts()

            result = {
                'conflicts_detected': len(conflicts),
                'conflicts_resolved': 0,
                'conflicts': []
            }

            # 转换冲突信息为字典格式
            for conflict in conflicts:
                conflict_info = {
                    'conflict_id': conflict.conflict_id,
                    'config_ids': conflict.config_ids,
                    'conflict_type': conflict.conflict_type,
                    'description': conflict.description,
                    'severity': conflict.severity,
                    'auto_resolvable': conflict.auto_resolvable,
                    'suggested_resolution': conflict.suggested_resolution
                }
                result['conflicts'].append(conflict_info)

            # 自动解决冲突
            if auto_resolve and conflicts:
                resolution_results = self.config_manager.auto_resolve_conflicts(conflicts)
                result['conflicts_resolved'] = resolution_results['resolved']
                result['resolution_details'] = resolution_results['details']

            logger.info(f"配置冲突检测完成: 发现{len(conflicts)}个冲突")
            return result

        except Exception as e:
            logger.error(f"配置冲突检测失败: {e}")
            return {'error': str(e), 'conflicts_detected': 0, 'conflicts_resolved': 0}

    def record_task_performance_feedback(self, task_id: str, execution_result: TaskExecutionResult):
        """记录任务性能反馈用于智能学习"""
        if not self.enable_intelligent_config or not isinstance(self.config_manager, IntelligentConfigManager):
            return

        try:
            # 获取任务配置
            config = self.config_manager.get_import_task(task_id)
            if not config:
                return

            # 计算性能指标
            execution_time = execution_result.duration or 0
            success_rate = 1.0 if execution_result.success else 0.0
            error_rate = 1.0 - success_rate
            throughput = (execution_result.processed_records / execution_time) if execution_time > 0 else 0

            # 记录性能反馈
            self.config_manager.record_performance_feedback(
                config, execution_time, success_rate, error_rate, throughput
            )

            logger.info(f"记录任务性能反馈: {task_id}")

        except Exception as e:
            logger.error(f"记录性能反馈失败: {e}")

    def get_intelligent_config_statistics(self) -> Dict[str, Any]:
        """获取智能配置统计信息"""
        if not self.enable_intelligent_config or not isinstance(self.config_manager, IntelligentConfigManager):
            return {
                'intelligent_config_enabled': False,
                'message': '智能配置未启用'
            }

        try:
            stats = self.config_manager.get_intelligent_statistics()
            stats['intelligent_config_enabled'] = True
            return stats

        except Exception as e:
            logger.error(f"获取智能配置统计失败: {e}")
            return {
                'intelligent_config_enabled': True,
                'error': str(e),
                'message': '获取智能配置统计失败'
            }

    # ==================== 增强版性能桥接系统功能 ====================

    def _init_enhanced_performance_bridge(self):
        """初始化增强版性能数据桥接系统"""
        try:
            self.enhanced_performance_bridge = get_enhanced_performance_bridge()
            logger.info("增强版性能数据桥接系统初始化完成")
        except Exception as e:
            logger.error(f"初始化增强版性能桥接系统失败: {e}")
            self.enhanced_performance_bridge = None

    def _init_enhanced_risk_monitor(self):
        """初始化增强版风险监控系统"""
        try:
            self.enhanced_risk_monitor = get_enhanced_risk_monitor()
            logger.info("增强版风险监控系统初始化完成")
        except Exception as e:
            logger.error(f"初始化增强版风险监控系统失败: {e}")
            self.enhanced_risk_monitor = None

    def _init_event_bus(self) -> Optional[EventBus]:
        """初始化事件总线"""
        try:
            event_bus = get_event_bus()

            self._register_import_event_handlers(event_bus)

            logger.info("事件总线初始化完成")
            return event_bus
        except Exception as e:
            logger.error(f"事件总线初始化失败: {e}")
            return None

    def _init_enhanced_async_manager(self):
        """初始化增强版异步任务管理器"""
        try:
            from ..async_management.enhanced_async_manager import get_enhanced_async_manager
            enhanced_async_manager = get_enhanced_async_manager()

            enhanced_async_manager.max_workers = self.executor._max_workers

            logger.info("增强版异步任务管理器初始化完成")
            return enhanced_async_manager
        except Exception as e:
            logger.error(f"增强版异步任务管理器初始化失败: {e}")
            return None

    def start_enhanced_performance_monitoring(self):
        """启动增强版性能监控"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return False

        try:
            self.enhanced_performance_bridge.start_enhanced_monitoring()
            logger.info("增强版性能监控已启动")
            return True
        except Exception as e:
            logger.error(f"启动增强版性能监控失败: {e}")
            return False

    def stop_enhanced_performance_monitoring(self):
        """停止增强版性能监控"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return False

        try:
            self.enhanced_performance_bridge.stop_enhanced_monitoring()
            logger.info("增强版性能监控已停止")
            return True
        except Exception as e:
            logger.error(f"停止增强版性能监控失败: {e}")
            return False

    def get_enhanced_performance_summary(self) -> Dict[str, Any]:
        """获取增强版性能摘要"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return {
                'enhanced_performance_bridge_enabled': False,
                'message': '增强版性能桥接系统未启用'
            }

        try:
            summary = self.enhanced_performance_bridge.get_performance_summary()
            summary['enhanced_performance_bridge_enabled'] = True
            return summary
        except Exception as e:
            logger.error(f"获取增强版性能摘要失败: {e}")
            return {
                'enhanced_performance_bridge_enabled': True,
                'error': str(e),
                'message': '获取增强版性能摘要失败'
            }

    def get_performance_anomalies(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取性能异常"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return []

        try:
            return self.enhanced_performance_bridge.get_recent_anomalies(hours)
        except Exception as e:
            logger.error(f"获取性能异常失败: {e}")
            return []

    def get_performance_trends(self) -> Dict[str, Dict[str, Any]]:
        """获取性能趋势"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return {}

        try:
            return self.enhanced_performance_bridge.get_performance_trends()
        except Exception as e:
            logger.error(f"获取性能趋势失败: {e}")
            return {}

    def get_performance_optimization_suggestions(self, priority_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取性能优化建议"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return []

        try:
            return self.enhanced_performance_bridge.get_optimization_suggestions(priority_filter)
        except Exception as e:
            logger.error(f"获取性能优化建议失败: {e}")
            return []

    def get_metric_performance_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """获取指标性能历史"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return []

        try:
            return self.enhanced_performance_bridge.get_metric_history(metric_name, hours)
        except Exception as e:
            logger.error(f"获取指标性能历史失败: {e}")
            return []

    def resolve_performance_anomaly(self, anomaly_id: str) -> bool:
        """解决性能异常"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return False

        try:
            return self.enhanced_performance_bridge.resolve_anomaly(anomaly_id)
        except Exception as e:
            logger.error(f"解决性能异常失败: {e}")
            return False

    def apply_performance_optimization(self, suggestion_id: str) -> bool:
        """应用性能优化建议"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return False

        try:
            return self.enhanced_performance_bridge.apply_optimization_suggestion(suggestion_id)
        except Exception as e:
            logger.error(f"应用性能优化建议失败: {e}")
            return False

    def record_custom_performance_metric(self, metric_name: str, value: float, category: str = "custom"):
        """记录自定义性能指标"""
        if not self.enable_enhanced_performance_bridge or not self.enhanced_performance_bridge:
            return

        try:
            # 确保深度分析服务已初始化
            self._ensure_deep_analysis_service()
            
            # 通过深度分析服务记录指标，增强桥接系统会自动收集
            if self.deep_analysis_service:
                self.deep_analysis_service.record_metric(metric_name, value, category)
                logger.debug(f"记录自定义性能指标: {metric_name} = {value}")
        except Exception as e:
            logger.error(f"记录自定义性能指标失败: {e}")

    def get_comprehensive_performance_report(self) -> Dict[str, Any]:
        """获取综合性能报告"""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'engine_status': {
                    'ai_optimization_enabled': self.enable_ai_optimization,
                    'intelligent_config_enabled': self.enable_intelligent_config,
                    'enhanced_performance_bridge_enabled': self.enable_enhanced_performance_bridge,
                    'enhanced_risk_monitoring_enabled': self.enable_enhanced_risk_monitoring,
                    'performance_monitoring_enabled': self.enable_performance_monitoring,
                    'anomaly_detection_enabled': self.enable_anomaly_detection,
                    'intelligent_caching_enabled': self.enable_intelligent_caching,
                    'distributed_execution_enabled': self.enable_distributed_execution,
                    'auto_tuning_enabled': self.enable_auto_tuning,
                    'data_quality_monitoring_enabled': self.enable_data_quality_monitoring
                }
            }

            # 添加各个系统的统计信息
            if self.enable_ai_optimization:
                report['ai_optimization_stats'] = self.get_ai_optimization_stats()

            if self.enable_performance_monitoring:
                report['performance_report'] = self.get_performance_report()

            if self.enable_intelligent_caching:
                report['cache_statistics'] = self.get_cache_statistics()

            if self.enable_distributed_execution:
                report['distributed_status'] = self.get_distributed_status()

            if self.enable_auto_tuning:
                report['auto_tuning_status'] = self.get_auto_tuning_status()

            if self.enable_data_quality_monitoring:
                report['data_quality_statistics'] = self.get_data_quality_statistics()

            if self.enable_intelligent_config:
                report['intelligent_config_statistics'] = self.get_intelligent_config_statistics()

            if self.enable_enhanced_performance_bridge:
                report['enhanced_performance_summary'] = self.get_enhanced_performance_summary()
                report['performance_anomalies'] = self.get_performance_anomalies(1)  # 最近1小时
                report['performance_trends'] = self.get_performance_trends()
                report['optimization_suggestions'] = self.get_performance_optimization_suggestions('high')  # 高优先级建议

            if self.enable_enhanced_risk_monitoring:
                report['risk_status'] = self.get_current_risk_status()
                report['risk_alerts'] = self.get_risk_alerts(1, False)  # 最近1小时未解决的预警
                report['risk_scenarios'] = self.get_risk_scenarios(3)  # 前3个风险情景
                report['risk_dashboard'] = self.get_risk_dashboard_data()

            return report

        except Exception as e:
            logger.error(f"获取综合性能报告失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}

    # ==================== 增强版风险监控系统功能 ====================

    def start_enhanced_risk_monitoring(self):
        """启动增强版风险监控"""
        if not self.enable_enhanced_risk_monitoring or not self.enhanced_risk_monitor:
            return False

        try:
            self.enhanced_risk_monitor.start_monitoring()
            logger.info("增强版风险监控已启动")
            return True
        except Exception as e:
            logger.error(f"启动增强版风险监控失败: {e}")
            return False

    def stop_enhanced_risk_monitoring(self):
        """停止增强版风险监控"""
        if not self.enable_enhanced_risk_monitoring or not self.enhanced_risk_monitor:
            return False

        try:
            self.enhanced_risk_monitor.stop_monitoring()
            logger.info("增强版风险监控已停止")
            return True
        except Exception as e:
            logger.error(f"停止增强版风险监控失败: {e}")
            return False

    def get_current_risk_status(self) -> Dict[str, Any]:
        """获取当前风险状态"""
        if not self.enable_enhanced_risk_monitoring or not self.enhanced_risk_monitor:
            return {
                'enhanced_risk_monitoring_enabled': False,
                'message': '增强版风险监控系统未启用'
            }

        try:
            status = self.enhanced_risk_monitor.get_current_risk_status()
            status['enhanced_risk_monitoring_enabled'] = True
            return status
        except Exception as e:
            logger.error(f"获取风险状态失败: {e}")
            return {
                'enhanced_risk_monitoring_enabled': True,
                'error': str(e),
                'message': '获取风险状态失败'
            }

    def get_risk_alerts(self, hours: int = 24, resolved: bool = False) -> List[Dict[str, Any]]:
        """获取风险预警"""
        if not self.enable_enhanced_risk_monitoring or not self.enhanced_risk_monitor:
            return []

        try:
            return self.enhanced_risk_monitor.get_risk_alerts(hours, resolved)
        except Exception as e:
            logger.error(f"获取风险预警失败: {e}")
            return []

    def resolve_risk_alert(self, alert_id: str, resolution_action: str = "") -> bool:
        """解决风险预警"""
        if not self.enable_enhanced_risk_monitoring or not self.enhanced_risk_monitor:
            return False

        try:
            return self.enhanced_risk_monitor.resolve_alert(alert_id, resolution_action)
        except Exception as e:
            logger.error(f"解决风险预警失败: {e}")
            return False

    def get_risk_scenarios(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取风险情景"""
        if not self.enable_enhanced_risk_monitoring or not self.enhanced_risk_monitor:
            return []

        try:
            return self.enhanced_risk_monitor.get_risk_scenarios(limit)
        except Exception as e:
            logger.error(f"获取风险情景失败: {e}")
            return []

    def get_risk_dashboard_data(self) -> Dict[str, Any]:
        """获取风险仪表板数据"""
        try:
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'risk_monitoring_enabled': self.enable_enhanced_risk_monitoring
            }

            if self.enable_enhanced_risk_monitoring and self.enhanced_risk_monitor:
                # 当前风险状态
                dashboard_data['current_status'] = self.get_current_risk_status()

                # 最近预警
                dashboard_data['recent_alerts'] = self.get_risk_alerts(24, False)

                # 风险情景
                dashboard_data['risk_scenarios'] = self.get_risk_scenarios(5)

                # 风险趋势（最近7天）
                dashboard_data['risk_trends'] = self._get_risk_trends(7)

                # 风险分布
                dashboard_data['risk_distribution'] = self._get_risk_distribution()

            return dashboard_data

        except Exception as e:
            logger.error(f"获取风险仪表板数据失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}

    def _get_risk_trends(self, days: int) -> Dict[str, List[Dict[str, Any]]]:
        """获取风险趋势数据"""
        try:
            if not self.enhanced_risk_monitor:
                return {}

            logger.warning("风险趋势数据不可用，返回空数据。请配置风险数据源以获取真实数据。")
            trends = {
                'market_risk': [],
                'liquidity_risk': [],
                'concentration_risk': []
            }

            return trends

        except Exception as e:
            logger.error(f"获取风险趋势失败: {e}")
            return {}

    def _get_risk_distribution(self) -> Dict[str, int]:
        """获取风险分布"""
        try:
            if not self.enhanced_risk_monitor:
                return {}

            # 获取当前风险状态中的分布信息
            status = self.get_current_risk_status()
            return status.get('risk_distribution', {})

        except Exception as e:
            logger.error(f"获取风险分布失败: {e}")
            return {}

    def cleanup(self):
        """清理资源"""
        try:
            # 取消事件总线订阅
            try:
                if hasattr(self, 'event_bus') and self.event_bus:
                    self.event_bus.unsubscribe("import_task_started", self._handle_import_task_started_event)
                    self.event_bus.unsubscribe("import_task_progress", self._handle_import_task_progress_event)
                    self.event_bus.unsubscribe("import_task_completed", self._handle_import_task_completed_event)
                    self.event_bus.unsubscribe("import_task_failed", self._handle_import_task_failed_event)
            except Exception as e:
                logger.error(f"取消事件订阅失败: {e}")

            # 停止进度定时器
            if self.progress_timer.isActive():
                self.progress_timer.stop()

            # 取消所有运行中的任务
            with self._task_lock:
                for task_id in list(self._running_tasks.keys()):
                    self.stop_task(task_id)

            # 停止数据库写入线程（等待队列清空）
            if hasattr(self, 'db_writer_thread'):
                logger.info("停止DatabaseWriterThread...")
                self.db_writer_thread.stop(wait=True, timeout=30.0)
                stats = self.db_writer_thread.get_stats()
                logger.info(f"DatabaseWriterThread统计: {stats}")

            # 关闭线程池
            self.executor.shutdown(wait=True)

            # 关闭基本面数据下载线程池
            if hasattr(self, 'fundamental_executor'):
                logger.info("停止基本面数据下载线程池...")
                self.fundamental_executor.shutdown(wait=True, timeout=10.0)
                logger.info("基本面数据下载线程池已停止")

            logger.info("数据导入执行引擎清理完成")

        except Exception as e:
            logger.error(f"清理执行引擎失败: {e}")


def main():
    """测试函数"""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 创建执行引擎
    engine = DataImportExecutionEngine()

    # 测试任务配置
    from .import_config_manager import ImportTaskConfig, ImportMode, DataFrequency

    task_config = ImportTaskConfig(
        task_id="test_task_001",
        name="测试K线数据导入",
        data_source="FactorWeave-Quant",
        asset_type="股票",
        data_type="K线数据",
        symbols=["000001", "000002"],
        frequency=DataFrequency.DAILY,
        mode=ImportMode.MANUAL
    )

    # 添加任务配置
    engine.config_manager.add_import_task(task_config)

    # 启动任务
    success = engine.start_task("test_task_001")
    logger.info(f"任务启动: {'成功' if success else '失败'}")

    # 运行应用
    try:
        app.exec_()
    finally:
        engine.cleanup()


if __name__ == "__main__":
    main()
