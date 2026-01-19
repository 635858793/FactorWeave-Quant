#!/usr/bin/env python3
"""
统一性能协调器

整合UnifiedPerformanceMonitor和其他性能监控组件，建立统一的性能数据收集和分析接口
提供统一的性能监控协调服务，支持实时数据收集、分析和可视化
"""

import time
import threading
import asyncio
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from enum import Enum
from loguru import logger

# 导入性能监控组件
from .unified_monitor import (
    UnifiedPerformanceMonitor, PerformanceMetric, PerformanceCategory,
    MetricType, PerformanceStats, get_performance_monitor
)

# 导入UI性能组件
try:
    import sys
    import os
    # 添加项目根目录到路径
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from gui.widgets.performance.unified_performance_widget import ModernUnifiedPerformanceWidget
    from gui.widgets.performance.tabs.system_monitor_tab import ModernSystemMonitorTab
    from gui.widgets.performance.tabs.risk_control_center_tab import ModernRiskControlCenterTab
    # 注意：cache_optimization_tab、ai_prediction_tab、import_performance_tab 不存在
    # 使用 algorithm_optimization_tab 替代不存在的 enhanced_deep_analysis_tab
    from gui.widgets.performance.tabs.algorithm_optimization_tab import ModernAlgorithmOptimizationTab as ModernAIPredictionTab
    from gui.widgets.performance.tabs.trading_execution_monitor_tab import ModernTradingExecutionMonitorTab as ModernImportPerformanceTab
    UI_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"UI性能组件不可用: {e}")
    UI_COMPONENTS_AVAILABLE = False

# 导入风险监控
try:
    from ..core.risk_monitoring.enhanced_risk_monitor import get_enhanced_risk_monitor
    RISK_MONITORING_AVAILABLE = True
except ImportError:
    RISK_MONITORING_AVAILABLE = False

# 导入AI预测服务
try:
    from ..core.services.ai_prediction_service import AIPredictionService
    AI_PREDICTION_AVAILABLE = True
except ImportError:
    AI_PREDICTION_AVAILABLE = False

class CoordinatorStatus(Enum):
    """协调器状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class PerformanceAlert:
    """性能告警"""
    alert_id: str
    metric_name: str
    threshold: float
    current_value: float
    severity: str  # 'info', 'warning', 'error', 'critical'
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'metric_name': self.metric_name,
            'threshold': self.threshold,
            'current_value': self.current_value,
            'severity': self.severity,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged
        }

@dataclass
class CoordinatorConfig:
    """协调器配置"""
    monitor_interval: float = 1.0  # 监控间隔（秒）
    ui_update_interval: float = 2.0  # UI更新间隔（秒）
    alert_check_interval: float = 5.0  # 告警检查间隔（秒）
    max_history_size: int = 1000  # 最大历史记录数
    enable_auto_tuning: bool = True  # 启用自动调优
    enable_ui_updates: bool = True  # 启用UI更新
    enable_alerts: bool = True  # 启用告警
    enable_ai_prediction: bool = True  # 启用AI预测

    # 性能阈值配置
    cpu_warning_threshold: float = 80.0
    cpu_critical_threshold: float = 95.0
    memory_warning_threshold: float = 85.0
    memory_critical_threshold: float = 95.0
    disk_warning_threshold: float = 90.0
    disk_critical_threshold: float = 98.0

class ModernTabIntegrator:
    """Modern*Tab组件集成器"""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.tab_components = {}
        self.tab_data_cache = {}

    def register_tab_component(self, tab_name: str, tab_component: Any) -> bool:
        """注册标签页组件"""
        try:
            self.tab_components[tab_name] = tab_component

            # 为不同类型的标签页设置特定的数据更新逻辑
            if hasattr(tab_component, 'update_performance_data'):
                # 注册数据更新回调
                self.coordinator.register_ui_update_callback(
                    lambda data: self._update_tab_data(tab_name, data)
                )

            logger.info(f"标签页组件已注册: {tab_name}")
            return True
        except Exception as e:
            logger.error(f"注册标签页组件失败: {e}")
            return False

    def _update_tab_data(self, tab_name: str, performance_data: Dict[str, Any]):
        """更新标签页数据"""
        try:
            if tab_name not in self.tab_components:
                return

            tab_component = self.tab_components[tab_name]

            # 根据标签页类型准备特定数据
            if tab_name == "system_monitor":
                tab_data = self._prepare_system_monitor_data(performance_data)
            elif tab_name == "risk_control":
                tab_data = self._prepare_risk_control_data(performance_data)
            elif tab_name == "cache_optimization":
                tab_data = self._prepare_cache_optimization_data(performance_data)
            elif tab_name == "ai_prediction":
                tab_data = self._prepare_ai_prediction_data(performance_data)
            elif tab_name == "import_performance":
                tab_data = self._prepare_import_performance_data(performance_data)
            else:
                tab_data = performance_data

            # 缓存数据
            self.tab_data_cache[tab_name] = tab_data

            # 更新组件
            if hasattr(tab_component, 'update_performance_data'):
                tab_component.update_performance_data(tab_data)

        except Exception as e:
            logger.error(f"更新标签页数据失败 {tab_name}: {e}")

    def _prepare_system_monitor_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """准备系统监控标签页数据"""
        system_metrics = data.get('metrics', {}).get('system', [])

        # 提取系统关键指标
        system_data = {
            'cpu_usage': 0,
            'memory_usage': 0,
            'disk_usage': 0,
            'network_sent': 0,
            'network_recv': 0,
            'process_count': 0,
            'thread_count': 0
        }

        for metric in system_metrics:
            name = metric.get('name', '')
            value = metric.get('value', 0)

            if 'cpu_usage' in name:
                system_data['cpu_usage'] = value
            elif 'memory_usage' in name:
                system_data['memory_usage'] = value
            elif 'disk_usage' in name:
                system_data['disk_usage'] = value
            elif 'network_bytes_sent' in name:
                system_data['network_sent'] = value
            elif 'network_bytes_recv' in name:
                system_data['network_recv'] = value

        return {
            'system_metrics': system_data,
            'alerts': data.get('alerts', []),
            'timestamp': data.get('timestamp')
        }

    def _prepare_risk_control_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """准备风险控制标签页数据"""
        alerts = data.get('alerts', [])

        # 按严重程度分类告警
        risk_data = {
            'critical_alerts': [a for a in alerts if a.get('severity') == 'critical'],
            'warning_alerts': [a for a in alerts if a.get('severity') == 'warning'],
            'info_alerts': [a for a in alerts if a.get('severity') == 'info'],
            'total_alerts': len(alerts),
            'risk_level': 'low'
        }

        # 计算风险等级
        if len(risk_data['critical_alerts']) > 0:
            risk_data['risk_level'] = 'critical'
        elif len(risk_data['warning_alerts']) > 3:
            risk_data['risk_level'] = 'high'
        elif len(risk_data['warning_alerts']) > 0:
            risk_data['risk_level'] = 'medium'

        return risk_data

    def _prepare_cache_optimization_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """准备缓存优化标签页数据"""
        cache_metrics = data.get('metrics', {}).get('cache', [])

        cache_data = {
            'hit_rate': 0,
            'miss_rate': 0,
            'cache_size': 0,
            'evictions': 0,
            'performance_score': 0
        }

        for metric in cache_metrics:
            name = metric.get('name', '')
            value = metric.get('value', 0)

            if 'hit_rate' in name:
                cache_data['hit_rate'] = value
            elif 'miss_rate' in name:
                cache_data['miss_rate'] = value
            elif 'cache_size' in name:
                cache_data['cache_size'] = value
            elif 'evictions' in name:
                cache_data['evictions'] = value

        # 计算性能评分
        cache_data['performance_score'] = cache_data['hit_rate']

        return cache_data

    def _prepare_ai_prediction_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """准备AI预测标签页数据"""
        ai_metrics = data.get('metrics', {}).get('algorithm', [])

        ai_data = {
            'prediction_accuracy': 0,
            'model_performance': 0,
            'training_progress': 0,
            'predictions_made': 0,
            'model_status': 'idle'
        }

        for metric in ai_metrics:
            name = metric.get('name', '')
            value = metric.get('value', 0)

            if 'prediction_accuracy' in name:
                ai_data['prediction_accuracy'] = value
            elif 'model_performance' in name:
                ai_data['model_performance'] = value
            elif 'training_progress' in name:
                ai_data['training_progress'] = value
            elif 'predictions_made' in name:
                ai_data['predictions_made'] = value

        return ai_data

    def _prepare_import_performance_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """准备导入性能标签页数据"""
        import_metrics = data.get('metrics', {}).get('data_import', [])

        import_data = {
            'import_speed': 0,
            'records_processed': 0,
            'error_rate': 0,
            'queue_size': 0,
            'active_imports': 0
        }

        for metric in import_metrics:
            name = metric.get('name', '')
            value = metric.get('value', 0)

            if 'import_speed' in name:
                import_data['import_speed'] = value
            elif 'records_processed' in name:
                import_data['records_processed'] = value
            elif 'error_rate' in name:
                import_data['error_rate'] = value
            elif 'queue_size' in name:
                import_data['queue_size'] = value
            elif 'active_imports' in name:
                import_data['active_imports'] = value

        return import_data

    def get_tab_data(self, tab_name: str) -> Optional[Dict[str, Any]]:
        """获取标签页数据"""
        return self.tab_data_cache.get(tab_name)

    def get_all_tab_data(self) -> Dict[str, Dict[str, Any]]:
        """获取所有标签页数据"""
        return self.tab_data_cache.copy()

class UnifiedPerformanceCoordinator:
    """
    统一性能协调器

    功能特性：
    1. 整合所有性能监控组件
    2. 统一的性能数据收集和分析接口
    3. 实时性能指标收集和处理
    4. 性能告警和通知系统
    5. UI组件协调和数据同步
    6. 自动性能优化建议
    7. AI增强的性能预测
    8. 多维度性能分析
    9. Modern*Tab组件集成管理
    """

    def __init__(self, config: Optional[CoordinatorConfig] = None):
        """
        初始化统一性能协调器

        Args:
            config: 协调器配置
        """
        self.config = config or CoordinatorConfig()

        # 状态管理
        self.status = CoordinatorStatus.STOPPED
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()

        # 核心组件
        self.performance_monitor = get_performance_monitor()

        # UI组件管理
        self.ui_components: Dict[str, Any] = {}
        self.ui_update_callbacks: List[Callable] = []

        # Modern*Tab组件集成器
        self.tab_integrator = ModernTabIntegrator(self)

        # 数据管理
        self.metrics_buffer: deque = deque(maxlen=self.config.max_history_size)
        self.alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: List[PerformanceAlert] = []

        # 线程管理
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="PerfCoordinator")
        self.monitor_thread: Optional[threading.Thread] = None
        self.ui_update_thread: Optional[threading.Thread] = None
        self.alert_thread: Optional[threading.Thread] = None

        # 回调系统
        self.metric_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.alert_callbacks: List[Callable] = []

        # 统计信息
        self._stats = {
            'total_metrics_collected': 0,
            'total_alerts_generated': 0,
            'ui_updates_sent': 0,
            'coordinator_uptime': 0.0,
            'last_update_time': None
        }

        # 初始化可选组件
        self._init_optional_components()

        logger.info("统一性能协调器初始化完成")

    def _init_optional_components(self):
        """初始化可选组件"""
        # 初始化风险监控
        if RISK_MONITORING_AVAILABLE:
            try:
                self.risk_monitor = get_enhanced_risk_monitor()
                logger.info("风险监控组件已集成")
            except Exception as e:
                logger.warning(f"风险监控组件初始化失败: {e}")
                self.risk_monitor = None
        else:
            self.risk_monitor = None

        # 初始化AI预测服务
        if AI_PREDICTION_AVAILABLE:
            try:
                self.ai_predictor = AIPredictionService()
                logger.info("AI预测服务已集成")
            except Exception as e:
                logger.warning(f"AI预测服务初始化失败: {e}")
                self.ai_predictor = None
        else:
            self.ai_predictor = None

    def start(self) -> bool:
        """启动协调器"""
        with self._lock:
            if self.status != CoordinatorStatus.STOPPED:
                logger.warning(f"协调器已在运行，当前状态: {self.status.value}")
                return False

            try:
                self.status = CoordinatorStatus.STARTING
                self._shutdown_event.clear()

                # 启动性能监控器
                if not self.performance_monitor.is_running:
                    self.performance_monitor.start()

                # 启动监控线程
                self.monitor_thread = threading.Thread(
                    target=self._monitor_loop,
                    name="PerformanceCoordinator-Monitor",
                    daemon=True
                )
                self.monitor_thread.start()

                # 启动UI更新线程
                if self.config.enable_ui_updates and UI_COMPONENTS_AVAILABLE:
                    self.ui_update_thread = threading.Thread(
                        target=self._ui_update_loop,
                        name="PerformanceCoordinator-UI",
                        daemon=True
                    )
                    self.ui_update_thread.start()

                # 启动告警线程
                if self.config.enable_alerts:
                    self.alert_thread = threading.Thread(
                        target=self._alert_loop,
                        name="PerformanceCoordinator-Alert",
                        daemon=True
                    )
                    self.alert_thread.start()

                self.status = CoordinatorStatus.RUNNING
                self._stats['coordinator_uptime'] = time.time()

                logger.info("统一性能协调器已启动")
                return True

            except Exception as e:
                self.status = CoordinatorStatus.ERROR
                logger.error(f"启动协调器失败: {e}")
                return False

    def stop(self) -> bool:
        """停止协调器"""
        with self._lock:
            if self.status == CoordinatorStatus.STOPPED:
                return True

            try:
                self.status = CoordinatorStatus.STOPPING
                self._shutdown_event.set()

                # 等待线程结束
                threads = [self.monitor_thread, self.ui_update_thread, self.alert_thread]
                for thread in threads:
                    if thread and thread.is_alive():
                        thread.join(timeout=5)

                # 关闭线程池
                self.executor.shutdown(wait=True)

                self.status = CoordinatorStatus.STOPPED

                # 更新统计信息
                if self._stats['coordinator_uptime']:
                    self._stats['coordinator_uptime'] = time.time() - self._stats['coordinator_uptime']

                logger.info("统一性能协调器已停止")
                return True

            except Exception as e:
                logger.error(f"停止协调器失败: {e}")
                return False

    def _monitor_loop(self):
        """监控主循环"""
        logger.info("性能监控循环已启动")

        while not self._shutdown_event.is_set():
            try:
                start_time = time.time()

                # 收集性能指标
                self._collect_performance_metrics()

                # 处理指标数据
                self._process_metrics()

                # 更新统计信息
                self._stats['total_metrics_collected'] += 1
                self._stats['last_update_time'] = datetime.now()

                # 计算循环耗时并调整睡眠时间
                elapsed = time.time() - start_time
                sleep_time = max(0, self.config.monitor_interval - elapsed)

                if sleep_time > 0:
                    self._shutdown_event.wait(sleep_time)

            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                self._shutdown_event.wait(5)  # 出错后等待5秒

    def _collect_performance_metrics(self):
        """收集性能指标"""
        try:
            # 从性能监控器获取最新指标
            current_metrics = self.performance_monitor.get_current_metrics()

            # 添加到缓冲区
            for metric in current_metrics:
                self.metrics_buffer.append(metric)

                # 触发指标回调
                for callback in self.metric_callbacks.get(metric.name, []):
                    try:
                        callback(metric)
                    except Exception as e:
                        logger.error(f"指标回调执行失败: {e}")

            # 收集系统特定指标
            self._collect_system_metrics()

            # 收集AI预测指标
            if self.config.enable_ai_prediction and self.ai_predictor:
                self._collect_ai_metrics()

        except Exception as e:
            logger.error(f"收集性能指标失败: {e}")

    def _collect_system_metrics(self):
        """收集系统特定指标"""
        try:
            import psutil

            # CPU指标
            cpu_percent = psutil.cpu_percent(interval=None)
            self._add_metric("system_cpu_usage", cpu_percent, PerformanceCategory.SYSTEM)

            # 内存指标
            memory = psutil.virtual_memory()
            self._add_metric("system_memory_usage", memory.percent, PerformanceCategory.SYSTEM)
            self._add_metric("system_memory_available", memory.available / (1024**3), PerformanceCategory.SYSTEM)

            # 磁盘指标
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self._add_metric("system_disk_usage", disk_percent, PerformanceCategory.SYSTEM)

            # 网络指标
            net_io = psutil.net_io_counters()
            self._add_metric("system_network_bytes_sent", net_io.bytes_sent, PerformanceCategory.SYSTEM)
            self._add_metric("system_network_bytes_recv", net_io.bytes_recv, PerformanceCategory.SYSTEM)

        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")

    def _collect_ai_metrics(self):
        """收集AI预测指标"""
        try:
            if not self.ai_predictor:
                return

            # 获取AI预测统计
            ai_stats = self.ai_predictor.get_prediction_stats()

            for stat_name, stat_value in ai_stats.items():
                self._add_metric(f"ai_{stat_name}", stat_value, PerformanceCategory.ALGORITHM)

        except Exception as e:
            logger.error(f"收集AI指标失败: {e}")

    def _add_metric(self, name: str, value: float, category: PerformanceCategory,
                    metric_type: MetricType = MetricType.GAUGE, description: str = "",
                    tags: Optional[Dict[str, str]] = None):
        """添加指标到缓冲区"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            category=category,
            metric_type=metric_type,
            description=description,
            tags=tags or {}
        )

        self.metrics_buffer.append(metric)

    def _process_metrics(self):
        """处理指标数据"""
        try:
            # 更新性能监控器的统计信息
            for metric in list(self.metrics_buffer)[-100:]:  # 处理最近100个指标
                self.performance_monitor.record_metric(
                    metric.name, metric.value, metric.category, metric.metric_type
                )

        except Exception as e:
            logger.error(f"处理指标数据失败: {e}")

    def _ui_update_loop(self):
        """UI更新循环"""
        logger.info("UI更新循环已启动")

        while not self._shutdown_event.is_set():
            try:
                # 准备UI更新数据
                ui_data = self._prepare_ui_data()

                # 发送UI更新
                self._send_ui_updates(ui_data)

                # 更新统计信息
                self._stats['ui_updates_sent'] += 1

                # 等待下次更新
                self._shutdown_event.wait(self.config.ui_update_interval)

            except Exception as e:
                logger.error(f"UI更新循环错误: {e}")
                self._shutdown_event.wait(5)

    def _prepare_ui_data(self) -> Dict[str, Any]:
        """准备UI更新数据"""
        try:
            # 获取最近的指标
            recent_metrics = list(self.metrics_buffer)[-50:] if self.metrics_buffer else []

            # 按类别分组指标
            metrics_by_category = defaultdict(list)
            for metric in recent_metrics:
                metrics_by_category[metric.category.value].append(metric.to_dict())

            # 获取当前告警
            current_alerts = [alert.to_dict() for alert in self.alerts.values()]

            # 获取统计信息
            stats = self.get_statistics()

            return {
                'metrics': dict(metrics_by_category),
                'alerts': current_alerts,
                'statistics': stats,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"准备UI数据失败: {e}")
            return {}

    def _send_ui_updates(self, ui_data: Dict[str, Any]):
        """发送UI更新"""
        try:
            # 调用所有UI更新回调
            for callback in self.ui_update_callbacks:
                try:
                    callback(ui_data)
                except Exception as e:
                    logger.error(f"UI更新回调执行失败: {e}")

            # 更新已注册的UI组件
            for component_name, component in self.ui_components.items():
                try:
                    if hasattr(component, 'update_performance_data'):
                        component.update_performance_data(ui_data)
                except Exception as e:
                    logger.error(f"更新UI组件 {component_name} 失败: {e}")

        except Exception as e:
            logger.error(f"发送UI更新失败: {e}")

    def _alert_loop(self):
        """告警检查循环"""
        logger.info("告警检查循环已启动")

        while not self._shutdown_event.is_set():
            try:
                # 检查性能告警
                self._check_performance_alerts()

                # 清理过期告警
                self._cleanup_expired_alerts()

                # 等待下次检查
                self._shutdown_event.wait(self.config.alert_check_interval)

            except Exception as e:
                logger.error(f"告警检查循环错误: {e}")
                self._shutdown_event.wait(10)

    def _check_performance_alerts(self):
        """检查性能告警"""
        try:
            if not self.metrics_buffer:
                return

            # 获取最新指标
            latest_metrics = {}
            for metric in reversed(self.metrics_buffer):
                if metric.name not in latest_metrics:
                    latest_metrics[metric.name] = metric
                if len(latest_metrics) >= 20:  # 只检查最近的20个不同指标
                    break

            # 检查各种告警条件
            for metric in latest_metrics.values():
                self._check_metric_alerts(metric)

        except Exception as e:
            logger.error(f"检查性能告警失败: {e}")

    def _check_metric_alerts(self, metric: PerformanceMetric):
        """检查单个指标的告警"""
        try:
            alert_id = None
            severity = None
            threshold = None
            message = ""

            # CPU使用率告警
            if metric.name == "system_cpu_usage":
                if metric.value >= self.config.cpu_critical_threshold:
                    alert_id = f"cpu_critical_{int(time.time())}"
                    severity = "critical"
                    threshold = self.config.cpu_critical_threshold
                    message = f"CPU使用率过高: {metric.value:.1f}%"
                elif metric.value >= self.config.cpu_warning_threshold:
                    alert_id = f"cpu_warning_{int(time.time())}"
                    severity = "warning"
                    threshold = self.config.cpu_warning_threshold
                    message = f"CPU使用率较高: {metric.value:.1f}%"

            # 内存使用率告警
            elif metric.name == "system_memory_usage":
                if metric.value >= self.config.memory_critical_threshold:
                    alert_id = f"memory_critical_{int(time.time())}"
                    severity = "critical"
                    threshold = self.config.memory_critical_threshold
                    message = f"内存使用率过高: {metric.value:.1f}%"
                elif metric.value >= self.config.memory_warning_threshold:
                    alert_id = f"memory_warning_{int(time.time())}"
                    severity = "warning"
                    threshold = self.config.memory_warning_threshold
                    message = f"内存使用率较高: {metric.value:.1f}%"

            # 磁盘使用率告警
            elif metric.name == "system_disk_usage":
                if metric.value >= self.config.disk_critical_threshold:
                    alert_id = f"disk_critical_{int(time.time())}"
                    severity = "critical"
                    threshold = self.config.disk_critical_threshold
                    message = f"磁盘使用率过高: {metric.value:.1f}%"
                elif metric.value >= self.config.disk_warning_threshold:
                    alert_id = f"disk_warning_{int(time.time())}"
                    severity = "warning"
                    threshold = self.config.disk_warning_threshold
                    message = f"磁盘使用率较高: {metric.value:.1f}%"

            # 创建告警
            if alert_id and severity and threshold:
                alert = PerformanceAlert(
                    alert_id=alert_id,
                    metric_name=metric.name,
                    threshold=threshold,
                    current_value=metric.value,
                    severity=severity,
                    message=message
                )

                # 避免重复告警
                existing_alert_key = f"{metric.name}_{severity}"
                if existing_alert_key not in self.alerts:
                    self.alerts[existing_alert_key] = alert
                    self.alert_history.append(alert)

                    # 触发告警回调
                    for callback in self.alert_callbacks:
                        try:
                            callback(alert)
                        except Exception as e:
                            logger.error(f"告警回调执行失败: {e}")

                    # 更新统计信息
                    self._stats['total_alerts_generated'] += 1

                    logger.warning(f"性能告警: {message}")

        except Exception as e:
            logger.error(f"检查指标告警失败: {e}")

    def _cleanup_expired_alerts(self):
        """清理过期告警"""
        try:
            current_time = datetime.now()
            expired_keys = []

            for key, alert in self.alerts.items():
                # 告警超过1小时自动清理
                if (current_time - alert.timestamp).total_seconds() > 3600:
                    expired_keys.append(key)

            for key in expired_keys:
                del self.alerts[key]

            if expired_keys:
                logger.info(f"清理了 {len(expired_keys)} 个过期告警")

        except Exception as e:
            logger.error(f"清理过期告警失败: {e}")

    def register_ui_component(self, name: str, component: Any) -> bool:
        """注册UI组件"""
        try:
            self.ui_components[name] = component
            logger.info(f"UI组件已注册: {name}")
            return True
        except Exception as e:
            logger.error(f"注册UI组件失败: {e}")
            return False

    def register_modern_tab(self, tab_name: str, tab_component: Any) -> bool:
        """注册Modern*Tab组件"""
        try:
            # 同时注册到UI组件和Tab集成器
            success1 = self.register_ui_component(f"tab_{tab_name}", tab_component)
            success2 = self.tab_integrator.register_tab_component(tab_name, tab_component)

            if success1 and success2:
                logger.info(f"Modern*Tab组件已注册: {tab_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"注册Modern*Tab组件失败: {e}")
            return False

    def get_tab_data(self, tab_name: str) -> Optional[Dict[str, Any]]:
        """获取标签页数据"""
        return self.tab_integrator.get_tab_data(tab_name)

    def get_all_tab_data(self) -> Dict[str, Dict[str, Any]]:
        """获取所有标签页数据"""
        return self.tab_integrator.get_all_tab_data()

    def create_unified_performance_widget(self) -> Optional[Any]:
        """创建统一性能监控组件"""
        if not UI_COMPONENTS_AVAILABLE:
            logger.warning("UI组件不可用，无法创建统一性能监控组件")
            return None

        try:
            # 创建主要的性能监控组件
            widget = ModernUnifiedPerformanceWidget()

            # 注册组件
            self.register_ui_component("unified_performance_widget", widget)

            # 创建并注册各个标签页
            self._create_and_register_tabs(widget)

            logger.info("统一性能监控组件已创建")
            return widget

        except Exception as e:
            logger.error(f"创建统一性能监控组件失败: {e}")
            return None

    def _create_and_register_tabs(self, parent_widget: Any):
        """创建并注册所有标签页"""
        try:
            # 系统监控标签页
            system_tab = ModernSystemMonitorTab()
            self.register_modern_tab("system_monitor", system_tab)

            # 风险控制标签页
            risk_tab = ModernRiskControlCenterTab()
            self.register_modern_tab("risk_control", risk_tab)

            # AI预测标签页
            ai_tab = ModernAIPredictionTab()
            self.register_modern_tab("ai_prediction", ai_tab)

            # 导入性能标签页
            import_tab = ModernImportPerformanceTab()
            self.register_modern_tab("import_performance", import_tab)

            logger.info("所有Modern*Tab组件已创建并注册")

        except Exception as e:
            logger.error(f"创建标签页失败: {e}")

    def unregister_ui_component(self, name: str) -> bool:
        """注销UI组件"""
        try:
            if name in self.ui_components:
                del self.ui_components[name]
                logger.info(f"UI组件已注销: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"注销UI组件失败: {e}")
            return False

    def register_ui_update_callback(self, callback: Callable):
        """注册UI更新回调"""
        self.ui_update_callbacks.append(callback)

    def register_metric_callback(self, metric_name: str, callback: Callable):
        """注册指标回调"""
        self.metric_callbacks[metric_name].append(callback)

    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)

    def get_current_metrics(self) -> List[Dict[str, Any]]:
        """获取当前指标"""
        try:
            recent_metrics = list(self.metrics_buffer)[-50:] if self.metrics_buffer else []
            return [metric.to_dict() for metric in recent_metrics]
        except Exception as e:
            logger.error(f"获取当前指标失败: {e}")
            return []

    def get_metrics_by_category(self, category: PerformanceCategory) -> List[Dict[str, Any]]:
        """按类别获取指标"""
        try:
            category_metrics = [
                metric.to_dict() for metric in self.metrics_buffer
                if metric.category == category
            ]
            return category_metrics[-50:]  # 返回最近50个
        except Exception as e:
            logger.error(f"按类别获取指标失败: {e}")
            return []

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        return [alert.to_dict() for alert in self.alerts.values()]

    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取告警历史"""
        return [alert.to_dict() for alert in self.alert_history[-limit:]]

    def acknowledge_alert(self, alert_key: str) -> bool:
        """确认告警"""
        try:
            if alert_key in self.alerts:
                self.alerts[alert_key].acknowledged = True
                logger.info(f"告警已确认: {alert_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"确认告警失败: {e}")
            return False

    def clear_alert(self, alert_key: str) -> bool:
        """清除告警"""
        try:
            if alert_key in self.alerts:
                del self.alerts[alert_key]
                logger.info(f"告警已清除: {alert_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"清除告警失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()

        # 添加运行时统计
        if self.status == CoordinatorStatus.RUNNING and self._stats['coordinator_uptime']:
            stats['current_uptime'] = time.time() - self._stats['coordinator_uptime']

        # 添加组件状态
        stats['status'] = self.status.value
        stats['active_ui_components'] = len(self.ui_components)
        stats['active_alerts'] = len(self.alerts)
        stats['metrics_buffer_size'] = len(self.metrics_buffer)

        # 添加性能监控器统计
        try:
            monitor_stats = self.performance_monitor.get_stats()
            stats['monitor_statistics'] = monitor_stats
        except Exception as e:
            logger.error(f"获取监控器统计失败: {e}")
            stats['monitor_statistics'] = {}

        return stats

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        try:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'status': self.status.value,
                'metrics_collected': self._stats['total_metrics_collected'],
                'alerts_generated': self._stats['total_alerts_generated'],
                'active_alerts': len(self.alerts),
                'ui_components': len(self.ui_components)
            }

            # 添加最新的关键指标
            if self.metrics_buffer:
                latest_metrics = {}
                for metric in reversed(self.metrics_buffer):
                    if metric.name not in latest_metrics:
                        latest_metrics[metric.name] = metric.value
                    if len(latest_metrics) >= 10:
                        break

                summary['latest_metrics'] = latest_metrics

            return summary

        except Exception as e:
            logger.error(f"获取性能摘要失败: {e}")
            return {'error': str(e)}

    @contextmanager
    def measure_operation(self, operation_name: str, category: PerformanceCategory = PerformanceCategory.SYSTEM):
        """测量操作性能的上下文管理器"""
        start_time = time.time()
        try:
            yield
        finally:
            elapsed_time = time.time() - start_time
            self._add_metric(
                f"operation_{operation_name}_duration",
                elapsed_time * 1000,  # 转换为毫秒
                category,
                MetricType.HISTOGRAM,
                f"操作 {operation_name} 的执行时间"
            )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

# 全局单例实例
_coordinator_instance: Optional[UnifiedPerformanceCoordinator] = None
_coordinator_lock = threading.RLock()

def get_performance_coordinator() -> UnifiedPerformanceCoordinator:
    """获取全局性能协调器实例"""
    global _coordinator_instance

    with _coordinator_lock:
        if _coordinator_instance is None:
            _coordinator_instance = UnifiedPerformanceCoordinator()
            _coordinator_instance.start()

        return _coordinator_instance

def initialize_performance_coordinator(config: Optional[CoordinatorConfig] = None) -> UnifiedPerformanceCoordinator:
    """初始化全局性能协调器"""
    global _coordinator_instance

    with _coordinator_lock:
        if _coordinator_instance is not None:
            _coordinator_instance.stop()

        _coordinator_instance = UnifiedPerformanceCoordinator(config)
        _coordinator_instance.start()

    return _coordinator_instance
