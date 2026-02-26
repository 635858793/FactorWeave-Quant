"""
服务健康监控模块

提供实时服务健康状态监控、报警和可视化仪表板。
"""

import json
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import socket
import traceback
from pathlib import Path

from loguru import logger
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
from PyQt5.QtGui import QFont, QColor

from ..events import EventBus, get_event_bus
from ..containers import get_service_container
from ..containers.enhanced_service_container import EnhancedServiceContainer, ServiceStatus, ServiceHealth


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthAlert:
    """健康告警"""
    id: str
    service_name: str
    level: AlertLevel
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class ServiceMetrics:
    """服务指标"""
    service_name: str
    response_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    request_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class ServiceHealthMonitor(QObject):
    """
    服务健康监控器

    提供服务健康状态监控、指标收集、告警管理和可视化仪表板。
    """

    # Qt信号
    health_status_changed = pyqtSignal(str, str)  # service_name, status
    alert_triggered = pyqtSignal(str, str, str)   # service_name, level, message
    metrics_updated = pyqtSignal(str, dict)       # service_name, metrics

    def __init__(self, event_bus: Optional[EventBus] = None, check_interval: int = 30):
        """
        初始化服务健康监控器

        Args:
            event_bus: 事件总线
            check_interval: 健康检查间隔（秒）
        """
        super().__init__()

        self._event_bus = event_bus or get_event_bus()
        self._check_interval = check_interval
        self._container = get_service_container()

        # 健康状态跟踪
        self._service_health: Dict[str, ServiceHealth] = {}
        self._service_metrics: Dict[str, ServiceMetrics] = {}
        self._health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # 告警管理
        self._alerts: Dict[str, HealthAlert] = {}
        self._alert_rules: Dict[str, List[Callable]] = defaultdict(list)
        self._alert_callbacks: List[Callable] = []

        # 监控控制
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_lock = threading.RLock()

        # Qt定时器用于UI更新 - 延迟初始化
        self._ui_timer = None

        # Web仪表板
        self._dashboard_port = 8889
        self._dashboard_thread: Optional[threading.Thread] = None

        # 初始化默认告警规则
        self._setup_default_alert_rules()

        logger.info(f"Service health monitor initialized with {check_interval}s check interval")

    def _ensure_ui_timer(self):
        """确保UI定时器已初始化"""
        if self._ui_timer is None:
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                logger.warning("QApplication未初始化，无法创建UI定时器")
                return
            self._ui_timer = QTimer()
            self._ui_timer.timeout.connect(self._update_ui)

    def start_monitoring(self) -> None:
        """开始健康监控"""
        with self._monitor_lock:
            if self._monitoring_active:
                logger.warning("Health monitoring is already active")
                return

            self._monitoring_active = True

            # 启动监控线程
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="ServiceHealthMonitor",
                daemon=True
            )
            self._monitor_thread.start()

            # 启动UI更新定时器
            self._ensure_ui_timer()
            if self._ui_timer is not None:
                self._ui_timer.start(5000)  # 每5秒更新一次UI

            # 启动Web仪表板
            self._start_web_dashboard()

            logger.info("Service health monitoring started")

    def stop_monitoring(self) -> None:
        """停止健康监控"""
        with self._monitor_lock:
            if not self._monitoring_active:
                return

            self._monitoring_active = False

            # 停止UI定时器
            self._ui_timer.stop()

            # 等待监控线程结束
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)

            logger.info("Service health monitoring stopped")

    def register_service(self, service_name: str, health_check_func: Optional[Callable] = None) -> None:
        """
        注册服务进行监控

        Args:
            service_name: 服务名称
            health_check_func: 自定义健康检查函数
        """
        if service_name not in self._service_metrics:
            self._service_metrics[service_name] = ServiceMetrics(service_name=service_name)
            logger.info(f"Service {service_name} registered for health monitoring")

    def update_service_metrics(self, service_name: str, metrics: Dict[str, Any]) -> None:
        """
        更新服务指标

        Args:
            service_name: 服务名称
            metrics: 指标数据
        """
        if service_name not in self._service_metrics:
            self.register_service(service_name)

        service_metrics = self._service_metrics[service_name]

        # 更新指标
        if 'response_time_ms' in metrics:
            service_metrics.response_time_ms = metrics['response_time_ms']
        if 'memory_usage_mb' in metrics:
            service_metrics.memory_usage_mb = metrics['memory_usage_mb']
        if 'cpu_usage_percent' in metrics:
            service_metrics.cpu_usage_percent = metrics['cpu_usage_percent']
        if 'request_count' in metrics:
            service_metrics.request_count = metrics['request_count']
        if 'error_count' in metrics:
            service_metrics.error_count = metrics['error_count']
        if 'last_error' in metrics:
            service_metrics.last_error = metrics['last_error']
        if 'uptime_seconds' in metrics:
            service_metrics.uptime_seconds = metrics['uptime_seconds']

        service_metrics.timestamp = datetime.now()

        # 发出更新信号
        self.metrics_updated.emit(service_name, asdict(service_metrics))

        # 检查告警规则
        self._check_alert_rules(service_name, service_metrics)

    def _monitoring_loop(self) -> None:
        """监控主循环"""
        logger.info("Health monitoring loop started")

        while self._monitoring_active:
            try:
                # 执行健康检查
                self._perform_health_checks()

                # 等待下一次检查
                time.sleep(self._check_interval)

            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                logger.error(traceback.format_exc())
                time.sleep(5)  # 出错时短暂等待

        logger.info("Health monitoring loop stopped")

    def _perform_health_checks(self) -> None:
        """执行健康检查"""
        try:
            # 检查增强服务容器的健康状态
            if isinstance(self._container, EnhancedServiceContainer):
                health_report = self._container.perform_health_check()
                self._process_container_health_report(health_report)

            # 检查注册服务的自定义健康状态
            for service_name, metrics in self._service_metrics.items():
                self._check_service_health(service_name, metrics)

        except Exception as e:
            logger.error(f"Error performing health checks: {e}")

    def _process_container_health_report(self, health_report: Dict[str, Any]) -> None:
        """处理容器健康报告"""
        overall_status = health_report.get('overall_status', 'unknown')
        services = health_report.get('services', {})

        for service_name, service_data in services.items():
            status = service_data.get('status', 'unknown')
            error_message = service_data.get('error_message')

            # 更新健康状态
            self._update_service_health_status(service_name, status, error_message)

            # 更新指标
            if service_name in self._service_metrics:
                metrics = self._service_metrics[service_name]
                if 'initialization_time_ms' in service_data:
                    metrics.response_time_ms = service_data['initialization_time_ms']
                metrics.timestamp = datetime.now()

    def _check_service_health(self, service_name: str, metrics: ServiceMetrics) -> None:
        """检查单个服务健康状态"""
        try:
            # 检查服务是否在容器中注册
            if hasattr(self._container, 'is_registered'):
                # 尝试通过服务名获取服务类型
                registered = False
                try:
                    # 这里需要更复杂的逻辑来映射服务名到类型
                    # 暂时使用简单的检查
                    registered = True  # 假设已注册
                except:
                    registered = False

                if not registered:
                    self._update_service_health_status(
                        service_name,
                        ServiceStatus.FAILED.value,
                        "Service not registered in container"
                    )
                    return

            # 检查响应时间
            if metrics.response_time_ms > 5000:  # 5秒超时
                self._trigger_alert(
                    service_name,
                    AlertLevel.WARNING,
                    f"High response time: {metrics.response_time_ms:.2f}ms"
                )

            # 检查错误率
            if metrics.error_count > 0:
                self._trigger_alert(
                    service_name,
                    AlertLevel.ERROR,
                    f"Service has {metrics.error_count} errors. Last error: {metrics.last_error}"
                )

            # 检查内存使用
            if metrics.memory_usage_mb > 1000:  # 1GB内存警告
                self._trigger_alert(
                    service_name,
                    AlertLevel.WARNING,
                    f"High memory usage: {metrics.memory_usage_mb:.2f}MB"
                )

            # 如果没有问题，标记为健康
            if (metrics.response_time_ms < 5000 and
                metrics.error_count == 0 and
                    metrics.memory_usage_mb < 1000):
                self._update_service_health_status(service_name, ServiceStatus.HEALTHY.value)

        except Exception as e:
            logger.error(f"Error checking health for service {service_name}: {e}")
            self._update_service_health_status(
                service_name,
                ServiceStatus.FAILED.value,
                f"Health check failed: {str(e)}"
            )

    def _update_service_health_status(self, service_name: str, status: str, error_message: Optional[str] = None) -> None:
        """更新服务健康状态"""
        # 记录历史
        status_entry = {
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'error_message': error_message
        }
        self._health_history[service_name].append(status_entry)

        # 发出状态变化信号
        self.health_status_changed.emit(service_name, status)

        logger.debug(f"Service {service_name} health status updated to {status}")

    def _setup_default_alert_rules(self) -> None:
        """设置默认告警规则"""
        # 响应时间告警
        def response_time_rule(service_name: str, metrics: ServiceMetrics) -> Optional[HealthAlert]:
            if metrics.response_time_ms > 10000:  # 10秒
                return HealthAlert(
                    id=f"{service_name}_response_time_{int(time.time())}",
                    service_name=service_name,
                    level=AlertLevel.CRITICAL,
                    message=f"Critical response time: {metrics.response_time_ms:.2f}ms",
                    timestamp=datetime.now()
                )
            return None

        # 错误率告警
        def error_rate_rule(service_name: str, metrics: ServiceMetrics) -> Optional[HealthAlert]:
            if metrics.error_count > 10:
                return HealthAlert(
                    id=f"{service_name}_error_rate_{int(time.time())}",
                    service_name=service_name,
                    level=AlertLevel.ERROR,
                    message=f"High error count: {metrics.error_count}",
                    timestamp=datetime.now()
                )
            return None

        # 注册默认规则
        for service_name in ['*']:  # '*' 表示所有服务
            self._alert_rules[service_name].extend([
                response_time_rule,
                error_rate_rule
            ])

    def _check_alert_rules(self, service_name: str, metrics: ServiceMetrics) -> None:
        """检查告警规则"""
        # 检查通用规则
        for rule in self._alert_rules.get('*', []):
            alert = rule(service_name, metrics)
            if alert:
                self._trigger_alert_object(alert)

        # 检查特定服务规则
        for rule in self._alert_rules.get(service_name, []):
            alert = rule(service_name, metrics)
            if alert:
                self._trigger_alert_object(alert)

    def _trigger_alert(self, service_name: str, level: AlertLevel, message: str) -> None:
        """触发告警"""
        alert = HealthAlert(
            id=f"{service_name}_{level.value}_{int(time.time())}",
            service_name=service_name,
            level=level,
            message=message,
            timestamp=datetime.now()
        )
        self._trigger_alert_object(alert)

    def _trigger_alert_object(self, alert: HealthAlert) -> None:
        """触发告警对象"""
        self._alerts[alert.id] = alert

        # 发出告警信号
        self.alert_triggered.emit(alert.service_name, alert.level.value, alert.message)

        # 记录日志
        log_func = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.ERROR: logger.error,
            AlertLevel.CRITICAL: logger.critical
        }.get(alert.level, logger.info)

        log_func(f"🚨 ALERT [{alert.level.value.upper()}] {alert.service_name}: {alert.message}")

        # 调用告警回调
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def _update_ui(self) -> None:
        """更新UI显示"""
        # 这个方法会被Qt定时器调用，用于更新UI组件
        pass

    def _start_web_dashboard(self) -> None:
        """启动Web仪表板"""
        try:
            self._dashboard_thread = threading.Thread(
                target=self._run_web_dashboard,
                name="HealthDashboard",
                daemon=True
            )
            self._dashboard_thread.start()
            logger.info(f"Health monitoring dashboard started at http://localhost:{self._dashboard_port}")
        except Exception as e:
            logger.error(f"Failed to start web dashboard: {e}")

    def _run_web_dashboard(self) -> None:
        """运行Web仪表板服务器"""
        try:
            import http.server
            import socketserver
            from urllib.parse import urlparse, parse_qs

            class HealthDashboardHandler(http.server.BaseHTTPRequestHandler):
                def __init__(self, *args, monitor=None, **kwargs):
                    self.monitor = monitor
                    super().__init__(*args, **kwargs)

                def do_GET(self):
                    if self.path == '/' or self.path == '/health':
                        self._serve_health_dashboard()
                    elif self.path == '/api/health':
                        self._serve_health_api()
                    elif self.path == '/api/metrics':
                        self._serve_metrics_api()
                    else:
                        self.send_error(404)

                def _serve_health_dashboard(self):
                    html = self._generate_dashboard_html()
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html.encode('utf-8'))

                def _serve_health_api(self):
                    data = {
                        'timestamp': datetime.now().isoformat(),
                        'services': {
                            name: asdict(metrics)
                            for name, metrics in self.monitor._service_metrics.items()
                        },
                        'alerts': {
                            alert_id: asdict(alert)
                            for alert_id, alert in self.monitor._alerts.items()
                            if not alert.resolved
                        }
                    }

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(data, default=str).encode('utf-8'))

                def _serve_metrics_api(self):
                    metrics = {
                        name: asdict(metrics)
                        for name, metrics in self.monitor._service_metrics.items()
                    }

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(metrics, default=str).encode('utf-8'))

                def _generate_dashboard_html(self):
                    return f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Service Health Dashboard</title>
                        <meta charset="utf-8">
                        <meta http-equiv="refresh" content="30">
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 20px; }}
                            .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
                            .service {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                            .healthy {{ background-color: #d4edda; border-color: #c3e6cb; }}
                            .warning {{ background-color: #fff3cd; border-color: #ffeaa7; }}
                            .error {{ background-color: #f8d7da; border-color: #f5c6cb; }}
                            .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
                            .metric {{ background: #f8f9fa; padding: 10px; border-radius: 3px; }}
                            .alerts {{ background: #fff3cd; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                        </style>
                    </head>
                    <body>
                        <div class="header">
                            <h1>🏥 Service Health Dashboard</h1>
                            <p>Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        </div>
                        
                        <h2>Service Status</h2>
                        {self._generate_services_html()}
                        
                        <h2>🚨 Active Alerts</h2>
                        {self._generate_alerts_html()}
                        
                        <script>
                            // Auto-refresh every 30 seconds
                            setTimeout(function(){{ window.location.reload(); }}, 30000);
                        </script>
                    </body>
                    </html>
                    """

                def _generate_services_html(self):
                    if not self.monitor._service_metrics:
                        return "<p>No services registered for monitoring.</p>"

                    html = ""
                    for name, metrics in self.monitor._service_metrics.items():
                        status_class = "healthy"
                        if metrics.error_count > 0:
                            status_class = "error"
                        elif metrics.response_time_ms > 1000:
                            status_class = "warning"

                        html += f"""
                        <div class="service {status_class}">
                            <h3>{name}</h3>
                            <div class="metrics">
                                <div class="metric">
                                    <strong>Response Time:</strong> {metrics.response_time_ms:.2f}ms
                                </div>
                                <div class="metric">
                                    <strong>Memory Usage:</strong> {metrics.memory_usage_mb:.2f}MB
                                </div>
                                <div class="metric">
                                    <strong>Error Count:</strong> {metrics.error_count}
                                </div>
                                <div class="metric">
                                    <strong>Uptime:</strong> {metrics.uptime_seconds:.0f}s
                                </div>
                                <div class="metric">
                                    <strong>Last Updated:</strong> {metrics.timestamp.strftime('%H:%M:%S')}
                                </div>
                            </div>
                        </div>
                        """
                    return html

                def _generate_alerts_html(self):
                    active_alerts = [
                        alert for alert in self.monitor._alerts.values()
                        if not alert.resolved
                    ]

                    if not active_alerts:
                        return "<p>No active alerts.</p>"

                    html = '<div class="alerts">'
                    for alert in sorted(active_alerts, key=lambda a: a.timestamp, reverse=True):
                        html += f"""
                        <div>
                            <strong>[{alert.level.value.upper()}]</strong> 
                            {alert.service_name}: {alert.message}
                            <br><small>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</small>
                        </div>
                        <hr>
                        """
                    html += '</div>'
                    return html

                def log_message(self, format, *args):
                    # 静默HTTP服务器日志
                    pass

            # 创建服务器
            handler = lambda *args, **kwargs: HealthDashboardHandler(*args, monitor=self, **kwargs)

            with socketserver.TCPServer(("", self._dashboard_port), handler) as httpd:
                httpd.serve_forever()

        except Exception as e:
            logger.error(f"Web dashboard server error: {e}")

    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康状态摘要"""
        total_services = len(self._service_metrics)
        healthy_services = 0
        unhealthy_services = 0

        for metrics in self._service_metrics.values():
            if metrics.error_count == 0 and metrics.response_time_ms < 5000:
                healthy_services += 1
            else:
                unhealthy_services += 1

        active_alerts = len([a for a in self._alerts.values() if not a.resolved])

        return {
            'timestamp': datetime.now().isoformat(),
            'total_services': total_services,
            'healthy_services': healthy_services,
            'unhealthy_services': unhealthy_services,
            'active_alerts': active_alerts,
            'monitoring_active': self._monitoring_active
        }

    def create_dashboard_widget(self) -> QWidget:
        """创建仪表板UI组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 标题
        title_label = QLabel("🏥 Service Health Monitor")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 状态显示
        self._status_label = QLabel("Loading...")
        layout.addWidget(self._status_label)

        # 服务列表
        self._services_text = QTextEdit()
        self._services_text.setMaximumHeight(200)
        layout.addWidget(self._services_text)

        # 控制按钮
        button_layout = QHBoxLayout()

        self._start_btn = QPushButton("Start Monitoring")
        self._start_btn.clicked.connect(self.start_monitoring)
        button_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop Monitoring")
        self._stop_btn.clicked.connect(self.stop_monitoring)
        button_layout.addWidget(self._stop_btn)

        layout.addLayout(button_layout)

        # 连接信号
        self.health_status_changed.connect(self._update_dashboard_widget)

        return widget

    def _update_dashboard_widget(self) -> None:
        """更新仪表板UI组件"""
        if hasattr(self, '_status_label'):
            summary = self.get_health_summary()
            status_text = (
                f"Services: {summary['healthy_services']}/{summary['total_services']} healthy | "
                f"Alerts: {summary['active_alerts']} | "
                f"Status: {'🟢 Active' if summary['monitoring_active'] else '🔴 Inactive'}"
            )
            self._status_label.setText(status_text)

        if hasattr(self, '_services_text'):
            services_info = []
            for name, metrics in self._service_metrics.items():
                status = "🟢" if metrics.error_count == 0 else "🔴"
                services_info.append(
                    f"{status} {name}: {metrics.response_time_ms:.1f}ms, "
                    f"{metrics.memory_usage_mb:.1f}MB, {metrics.error_count} errors"
                )

            self._services_text.setPlainText("\n".join(services_info))

    def dispose(self) -> None:
        """释放监控器资源"""
        self.stop_monitoring()
        logger.info("Service health monitor disposed")


# 全局实例
_health_monitor: Optional[ServiceHealthMonitor] = None
_monitor_lock = threading.Lock()


def get_health_monitor() -> ServiceHealthMonitor:
    """获取全局健康监控器实例"""
    global _health_monitor
    if _health_monitor is None:
        with _monitor_lock:
            if _health_monitor is None:
                # 检查QApplication是否存在
                from PyQt5.QtWidgets import QApplication
                if QApplication.instance() is None:
                    logger.warning("QApplication未初始化，无法创建ServiceHealthMonitor")
                    return None
                _health_monitor = ServiceHealthMonitor()
    return _health_monitor


def start_health_monitoring() -> ServiceHealthMonitor:
    """启动健康监控"""
    monitor = get_health_monitor()
    monitor.start_monitoring()
    return monitor
