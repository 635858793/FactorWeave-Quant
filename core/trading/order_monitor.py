"""
订单监控器

负责实时监控订单状态（事件驱动 + 轻量级定时检查）
"""

from loguru import logger
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from core.trading.order_models import Order, OrderStatus
from core.trading.order_repository import OrderRepository, get_order_repository
from core.containers import ServiceContainer
from core.events import EventBus


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class OrderAlert:
    """订单告警"""
    alert_id: str
    order_id: str
    alert_level: AlertLevel
    alert_type: str
    alert_message: str
    alert_time: datetime
    order_info: Dict[str, Any]
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'alert_id': self.alert_id,
            'order_id': self.order_id,
            'alert_level': self.alert_level.value,
            'alert_type': self.alert_type,
            'alert_message': self.alert_message,
            'alert_time': self.alert_time.isoformat(),
            'order_info': self.order_info,
            'details': self.details
        }


class OrderMonitor:
    """订单监控器（事件驱动 + 轻量级定时检查）"""

    # R237-P1 修复: 类级默认 _disposed (R235-D 标杆模式, 防御 __new__ 绕过 __init__ 的场景)
    _disposed = False

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        # R237-P1 修复: _disposed 标志 (R78 铁律 #6 幂等短路 + R233 §13.4 dispose 链)
        self._disposed = False
        self.service_container = service_container
        self.event_bus = event_bus

        self.repository: OrderRepository = None

        self._alerts: List[OrderAlert] = []
        self._monitoring_enabled = True

        # 优化：使用更长的检查间隔，因为主要依赖事件驱动
        self._check_interval = 300  # 检查间隔（秒）- 改为5分钟
        self._last_check_time = datetime.now()

        # 跟踪订单的创建时间，用于超时检查
        self._order_create_times: Dict[str, datetime] = {}

        self._config = self._load_config()

        self._initialize()

        logger.info("订单监控器初始化完成（事件驱动模式）")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        return {
            'monitoring_enabled': True,
            'check_interval': 300,  # 检查间隔（秒）- 改为5分钟
            'pending_timeout': 300,  # 待处理超时（秒）
            'submitted_timeout': 600,  # 已提交超时（秒）
            'partial_fill_timeout': 900,  # 部分成交超时（秒）
            'enable_alerts': True,
            'alert_threshold': {
                'pending_orders': 10,
                'rejected_orders': 5,
                'cancelled_orders': 10
            }
        }

    def _initialize(self):
        """初始化"""
        # R255-P2: 共用模块级单例, 保证 OrderCache 一致性
        self.repository = get_order_repository(self.service_container, self.event_bus)

        # 订阅事件（事件驱动：订单状态变化时立即响应）
        self.event_bus.subscribe('order_created', self._on_order_created)
        self.event_bus.subscribe('order_submitted', self._on_order_submitted)
        self.event_bus.subscribe('order_filled', self._on_order_filled)
        self.event_bus.subscribe('order_partially_filled', self._on_order_partially_filled)
        self.event_bus.subscribe('order_cancelled', self._on_order_cancelled)
        self.event_bus.subscribe('order_submitted_failed', self._on_order_submitted_failed)
        self.event_bus.subscribe('order_updated', self._on_order_updated)

        logger.info("订单监控器已订阅所有订单事件")

    def start_monitoring(self):
        """开始监控"""
        self._monitoring_enabled = True
        logger.info("订单监控已启动（事件驱动 + 轻量级定时检查）")

    def stop_monitoring(self):
        """停止监控"""
        self._monitoring_enabled = False
        try:
            self.event_bus.unsubscribe('order_created', self._on_order_created)
            self.event_bus.unsubscribe('order_submitted', self._on_order_submitted)
            self.event_bus.unsubscribe('order_filled', self._on_order_filled)
            self.event_bus.unsubscribe('order_partially_filled', self._on_order_partially_filled)
            self.event_bus.unsubscribe('order_cancelled', self._on_order_cancelled)
            self.event_bus.unsubscribe('order_submitted_failed', self._on_order_submitted_failed)
            self.event_bus.unsubscribe('order_updated', self._on_order_updated)
        except Exception as e:
            logger.error(f"取消订阅事件失败: {e}")
        logger.info("订单监控已停止")

    def dispose(self):
        """R237-P1 修复: dispose 链 (R78 铁律 #6 幂等短路 + R233 §13.4 业务核心)

        释放订单监控器资源:
        1. _disposed 标志幂等短路 (重复 dispose 不抛错)
        2. 停止监控 + 取消全部 7 个事件订阅 (R8 §8.1 铁律 #1)
        3. 清空业务数据 _alerts / _order_create_times (内存泄漏防御)
        4. 失败仅 warning 不抛 (R117-HVD-69 P1 模板)
        """
        if self._disposed:
            return
        try:
            self.stop_monitoring()
            self._alerts.clear()
            self._order_create_times.clear()
        except Exception as e:
            logger.warning(f"OrderMonitor.dispose 失败: {e}", exc_info=True)
        finally:
            self._disposed = True
        logger.info("订单监控器已释放")

    def check_orders(self) -> List[OrderAlert]:
        """
        检查订单（轻量级：只检查超时订单）

        优化说明：
        - 不再查询所有活跃订单
        - 只检查已跟踪的订单是否超时
        - 大幅减少数据库查询
        """
        if not self._monitoring_enabled:
            return []

        try:
            logger.debug("开始轻量级订单超时检查")

            alerts = []

            # 优化：只检查可能超时的订单
            now = datetime.now()
            orders_to_check = []

            # 检查待处理超时
            pending_timeout = self._config['pending_timeout']
            for order_id, create_time in self._order_create_times.items():
                elapsed = (now - create_time).total_seconds()
                if elapsed > pending_timeout:
                    orders_to_check.append(order_id)

            # 只查询可能超时的订单
            if orders_to_check:
                for order_id in orders_to_check:
                    order = self.repository.get_order(order_id)
                    if order and order.is_active:
                        timeout_alerts = self._check_order_timeout(order, now)
                        alerts.extend(timeout_alerts)

            # 清理已完成的订单
            self._cleanup_completed_orders()

            self._last_check_time = datetime.now()

            logger.debug(f"轻量级订单检查完成: 发现 {len(alerts)} 个告警")
            return alerts

        except Exception as e:
            logger.error(f"检查订单异常: {e}")
            return []

    def _check_order_timeout(self, order: Order, now: datetime) -> List[OrderAlert]:
        """检查单个订单是否超时"""
        alerts = []

        elapsed_time = (now - order.create_time).total_seconds()

        if order.order_status == OrderStatus.PENDING:
            timeout = self._config['pending_timeout']
            if elapsed_time > timeout:
                alert = OrderAlert(
                    alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    order_id=order.order_id,
                    alert_level=AlertLevel.WARNING,
                    alert_type="PENDING_TIMEOUT",
                    alert_message=f"订单 {order.order_id} 待处理超时 ({elapsed_time:.0f}s)",
                    alert_time=now,
                    order_info={
                        'order_id': order.order_id,
                        'stock_code': order.stock_code,
                        'order_type': order.order_type.value,
                        'order_quantity': order.order_quantity,
                        'elapsed_time': elapsed_time
                    },
                    details={'timeout': timeout}
                )
                alerts.append(alert)

        elif order.order_status == OrderStatus.SUBMITTED:
            timeout = self._config['submitted_timeout']
            if elapsed_time > timeout:
                alert = OrderAlert(
                    alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    order_id=order.order_id,
                    alert_level=AlertLevel.ERROR,
                    alert_type="SUBMITTED_TIMEOUT",
                    alert_message=f"订单 {order.order_id} 已提交超时 ({elapsed_time:.0f}s)",
                    alert_time=now,
                    order_info={
                        'order_id': order.order_id,
                        'stock_code': order.stock_code,
                        'order_type': order.order_type.value,
                        'order_quantity': order.order_quantity,
                        'elapsed_time': elapsed_time
                    },
                    details={'timeout': timeout}
                )
                alerts.append(alert)

        return alerts

    def _cleanup_completed_orders(self):
        """清理已完成的订单"""
        try:
            completed_statuses = [
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED
            ]

            for order_id in list(self._order_create_times.keys()):
                order = self.repository.get_order(order_id)
                if order and order.order_status in completed_statuses:
                    del self._order_create_times[order_id]

        except Exception as e:
            logger.error(f"清理已完成订单失败: {e}")

    def _check_timeout_orders(self, orders: List[Order]) -> List[OrderAlert]:
        """检查超时订单"""
        alerts = []
        now = datetime.now()

        for order in orders:
            elapsed_time = (now - order.create_time).total_seconds()

            if order.order_status == OrderStatus.PENDING:
                timeout = self._config['pending_timeout']
                if elapsed_time > timeout:
                    alert = OrderAlert(
                        alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        order_id=order.order_id,
                        alert_level=AlertLevel.WARNING,
                        alert_type="PENDING_TIMEOUT",
                        alert_message=f"订单 {order.order_id} 待处理超时 ({elapsed_time:.0f}s)",
                        alert_time=now,
                        order_info={
                            'order_id': order.order_id,
                            'stock_code': order.stock_code,
                            'order_type': order.order_type.value,
                            'order_quantity': order.order_quantity,
                            'elapsed_time': elapsed_time
                        },
                        details={'timeout': timeout}
                    )
                    alerts.append(alert)

            elif order.order_status == OrderStatus.SUBMITTED:
                timeout = self._config['submitted_timeout']
                if elapsed_time > timeout:
                    alert = OrderAlert(
                        alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        order_id=order.order_id,
                        alert_level=AlertLevel.ERROR,
                        alert_type="SUBMITTED_TIMEOUT",
                        alert_message=f"订单 {order.order_id} 已提交超时 ({elapsed_time:.0f}s)",
                        alert_time=now,
                        order_info={
                            'order_id': order.order_id,
                            'stock_code': order.stock_code,
                            'order_type': order.order_type.value,
                            'order_quantity': order.order_quantity,
                            'elapsed_time': elapsed_time
                        },
                        details={'timeout': timeout}
                    )
                    alerts.append(alert)

        return alerts

    def _check_abnormal_orders(self, orders: List[Order]) -> List[OrderAlert]:
        """检查异常订单"""
        alerts = []
        now = datetime.now()

        for order in orders:
            # 检查部分成交超时
            if order.order_status == OrderStatus.PARTIALLY_FILLED:
                elapsed_time = (now - order.update_time).total_seconds()
                timeout = self._config['partial_fill_timeout']

                if elapsed_time > timeout:
                    alert = OrderAlert(
                        alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        order_id=order.order_id,
                        alert_level=AlertLevel.WARNING,
                        alert_type="PARTIAL_FILL_TIMEOUT",
                        alert_message=f"订单 {order.order_id} 部分成交超时 ({elapsed_time:.0f}s)",
                        alert_time=now,
                        order_info={
                            'order_id': order.order_id,
                            'stock_code': order.stock_code,
                            'filled_quantity': order.filled_quantity,
                            'order_quantity': order.order_quantity,
                            'fill_ratio': order.fill_ratio,
                            'elapsed_time': elapsed_time
                        },
                        details={'timeout': timeout}
                    )
                    alerts.append(alert)

            # 检查价格异常
            if order.order_price < 0.01 or order.order_price > 1000000:
                alert = OrderAlert(
                    alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    order_id=order.order_id,
                    alert_level=AlertLevel.ERROR,
                    alert_type="ABNORMAL_PRICE",
                    alert_message=f"订单 {order.order_id} 价格异常: {order.order_price}",
                    alert_time=now,
                    order_info={
                        'order_id': order.order_id,
                        'stock_code': order.stock_code,
                        'order_price': order.order_price
                    }
                )
                alerts.append(alert)

        return alerts

    def _check_order_quantity(self) -> List[OrderAlert]:
        """检查订单数量"""
        alerts = []

        try:
            from core.trading.order_models import OrderQuery

            # 检查待处理订单数量
            pending_query = OrderQuery(order_status=OrderStatus.PENDING, limit=1000)
            pending_orders = self.repository.query_orders(pending_query)

            threshold = self._config['alert_threshold']['pending_orders']
            if len(pending_orders) > threshold:
                alert = OrderAlert(
                    alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    order_id="SYSTEM",
                    alert_level=AlertLevel.WARNING,
                    alert_type="TOO_MANY_PENDING_ORDERS",
                    alert_message=f"待处理订单数量过多: {len(pending_orders)}",
                    alert_time=datetime.now(),
                    order_info={'pending_orders_count': len(pending_orders)},
                    details={'threshold': threshold}
                )
                alerts.append(alert)

            # 检查被拒绝订单数量（最近1小时）
            one_hour_ago = datetime.now() - timedelta(hours=1)
            rejected_query = OrderQuery(order_status=OrderStatus.REJECTED, limit=1000)
            rejected_orders = self.repository.query_orders(rejected_query)
            recent_rejected = [o for o in rejected_orders if o.create_time >= one_hour_ago]

            threshold = self._config['alert_threshold']['rejected_orders']
            if len(recent_rejected) > threshold:
                alert = OrderAlert(
                    alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    order_id="SYSTEM",
                    alert_level=AlertLevel.ERROR,
                    alert_type="TOO_MANY_REJECTED_ORDERS",
                    alert_message=f"最近1小时被拒绝订单数量过多: {len(recent_rejected)}",
                    alert_time=datetime.now(),
                    order_info={'rejected_orders_count': len(recent_rejected)},
                    details={'threshold': threshold, 'time_range': '1 hour'}
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"检查订单数量异常: {e}")

        return alerts

    def _send_alert(self, alert: OrderAlert):
        """发送告警"""
        if not self._config['enable_alerts']:
            return

        try:
            # 发布告警事件
            self.event_bus.publish('order_alert', **alert.to_dict())

            # 根据告警级别记录日志
            if alert.alert_level == AlertLevel.INFO:
                logger.info(f"订单告警: {alert.alert_message}")
            elif alert.alert_level == AlertLevel.WARNING:
                logger.warning(f"订单告警: {alert.alert_message}")
            elif alert.alert_level == AlertLevel.ERROR:
                logger.error(f"订单告警: {alert.alert_message}")
            elif alert.alert_level == AlertLevel.CRITICAL:
                logger.critical(f"订单告警: {alert.alert_message}")

        except Exception as e:
            logger.error(f"发送告警异常: {e}")

    def get_alerts(self, limit: int = 100) -> List[OrderAlert]:
        """获取告警"""
        return self._alerts[-limit:]

    def get_alerts_by_order(self, order_id: str) -> List[OrderAlert]:
        """获取订单告警"""
        return [alert for alert in self._alerts if alert.order_id == order_id]

    def get_alerts_by_level(self, level: AlertLevel, limit: int = 100) -> List[OrderAlert]:
        """获取级别告警"""
        return [alert for alert in self._alerts if alert.alert_level == level][-limit:]

    def clear_old_alerts(self, days: int = 7):
        """清理旧告警"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            old_count = len(self._alerts)
            self._alerts = [alert for alert in self._alerts if alert.alert_time >= cutoff_time]
            new_count = len(self._alerts)

            logger.info(f"清理旧告警: 删除 {old_count - new_count} 条，保留 {new_count} 条")

        except Exception as e:
            logger.error(f"清理旧告警异常: {e}")

    def generate_monitoring_report(self) -> Dict[str, Any]:
        """生成监控报告"""
        try:
            from core.trading.order_models import OrderQuery

            now = datetime.now()
            one_hour_ago = now - timedelta(hours=1)
            one_day_ago = now - timedelta(days=1)

            # 统计活跃订单
            active_orders = self.repository.get_active_orders()

            # 统计最近1小时订单
            recent_query = OrderQuery(limit=1000)
            recent_orders = self.repository.query_orders(recent_query)
            recent_orders = [o for o in recent_orders if o.create_time >= one_hour_ago]

            # 统计最近1天订单
            daily_query = OrderQuery(limit=10000)
            daily_orders = self.repository.query_orders(daily_query)
            daily_orders = [o for o in daily_orders if o.create_time >= one_day_ago]

            # 统计告警
            recent_alerts = [alert for alert in self._alerts if alert.alert_time >= one_hour_ago]

            report = {
                'report_time': now.isoformat(),
                'active_orders': {
                    'total': len(active_orders),
                    'pending': len([o for o in active_orders if o.order_status == OrderStatus.PENDING]),
                    'submitted': len([o for o in active_orders if o.order_status == OrderStatus.SUBMITTED]),
                    'partially_filled': len([o for o in active_orders if o.order_status == OrderStatus.PARTIALLY_FILLED])
                },
                'recent_orders': {
                    'total': len(recent_orders),
                    'filled': len([o for o in recent_orders if o.order_status == OrderStatus.FILLED]),
                    'cancelled': len([o for o in recent_orders if o.order_status == OrderStatus.CANCELLED]),
                    'rejected': len([o for o in recent_orders if o.order_status == OrderStatus.REJECTED])
                },
                'daily_orders': {
                    'total': len(daily_orders),
                    'filled': len([o for o in daily_orders if o.order_status == OrderStatus.FILLED]),
                    'cancelled': len([o for o in daily_orders if o.order_status == OrderStatus.CANCELLED]),
                    'rejected': len([o for o in daily_orders if o.order_status == OrderStatus.REJECTED])
                },
                'alerts': {
                    'total': len(recent_alerts),
                    'info': len([a for a in recent_alerts if a.alert_level == AlertLevel.INFO]),
                    'warning': len([a for a in recent_alerts if a.alert_level == AlertLevel.WARNING]),
                    'error': len([a for a in recent_alerts if a.alert_level == AlertLevel.ERROR]),
                    'critical': len([a for a in recent_alerts if a.alert_level == AlertLevel.CRITICAL])
                },
                'monitoring_status': {
                    'enabled': self._monitoring_enabled,
                    'last_check_time': self._last_check_time.isoformat(),
                    'check_interval': self._config['check_interval']
                }
            }

            logger.info(f"生成监控报告: {report}")
            return report

        except Exception as e:
            logger.error(f"生成监控报告异常: {e}")
            return {}

    def update_config(self, config: Dict[str, Any]):
        """更新配置"""
        self._config.update(config)
        logger.info(f"订单监控器配置已更新: {config}")

    def _on_order_created(self, event):
        """订单创建事件处理（事件驱动：立即响应）"""
        order_id = event.order_id if hasattr(event, 'order_id') else event.data.get('order_id')
        logger.debug(f"监控器收到订单创建事件: {order_id}")

        # 优化：立即记录订单创建时间，用于后续超时检查
        self._order_create_times[order_id] = datetime.now()

    def _on_order_submitted(self, event):
        """订单提交事件处理（事件驱动：立即响应）"""
        order_id = event.order_id if hasattr(event, 'order_id') else event.data.get('order_id')
        logger.debug(f"监控器收到订单提交事件: {order_id}")

        # 优化：订单已提交，更新创建时间为提交时间
        if order_id in self._order_create_times:
            self._order_create_times[order_id] = datetime.now()

    def _on_order_updated(self, event):
        """订单更新事件处理（事件驱动：立即响应）"""
        order_id = event.order_id if hasattr(event, 'order_id') else event.data.get('order_id')
        logger.debug(f"监控器收到订单更新事件: {order_id}")

        # 优化：检查订单状态变化，立即检测异常
        try:
            order = self.repository.get_order(order_id)
            if order:
                # 检查价格异常
                if order.order_price < 0.01 or order.order_price > 1000000:
                    alert = OrderAlert(
                        alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        order_id=order_id,
                        alert_level=AlertLevel.ERROR,
                        alert_type="ABNORMAL_PRICE",
                        alert_message=f"订单 {order_id} 价格异常: {order.order_price}",
                        alert_time=datetime.now(),
                        order_info={
                            'order_id': order_id,
                            'stock_code': order.stock_code,
                            'order_price': order.order_price
                        }
                    )
                    self._alerts.append(alert)
                    self._send_alert(alert)

        except Exception as e:
            logger.error(f"处理订单更新事件失败: {e}")

    def _on_order_filled(self, event):
        """订单成交事件处理（事件驱动：立即响应）"""
        order_id = event.order_id if hasattr(event, 'order_id') else event.data.get('order_id')
        logger.debug(f"监控器收到订单成交事件: {order_id}")

        # 优化：订单已成交，从跟踪列表中移除
        if order_id in self._order_create_times:
            del self._order_create_times[order_id]

    def _on_order_partially_filled(self, event):
        """订单部分成交事件处理（事件驱动：立即响应）"""
        order_id = event.order_id if hasattr(event, 'order_id') else event.data.get('order_id')
        logger.debug(f"监控器收到订单部分成交事件: {order_id}")

        # 优化：订单部分成交，检查是否超时
        try:
            order = self.repository.get_order(order_id)
            if order:
                now = datetime.now()
                elapsed_time = (now - order.update_time).total_seconds()
                timeout = self._config['partial_fill_timeout']

                if elapsed_time > timeout:
                    alert = OrderAlert(
                        alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        order_id=order_id,
                        alert_level=AlertLevel.WARNING,
                        alert_type="PARTIAL_FILL_TIMEOUT",
                        alert_message=f"订单 {order_id} 部分成交超时 ({elapsed_time:.0f}s)",
                        alert_time=now,
                        order_info={
                            'order_id': order_id,
                            'stock_code': order.stock_code,
                            'filled_quantity': order.filled_quantity,
                            'order_quantity': order.order_quantity,
                            'fill_ratio': order.fill_ratio,
                            'elapsed_time': elapsed_time
                        },
                        details={'timeout': timeout}
                    )
                    self._alerts.append(alert)
                    self._send_alert(alert)

        except Exception as e:
            logger.error(f"处理订单部分成交事件失败: {e}")

    def _on_order_cancelled(self, event):
        """订单取消事件处理（事件驱动：立即响应）"""
        order_id = event.order_id if hasattr(event, 'order_id') else event.data.get('order_id')
        logger.debug(f"监控器收到订单取消事件: {order_id}")

        # 优化：订单已取消，从跟踪列表中移除
        if order_id in self._order_create_times:
            del self._order_create_times[order_id]

    def _on_order_submitted_failed(self, event):
        """订单提交失败事件处理（事件驱动：立即响应）"""
        order_id = event.order_id if hasattr(event, 'order_id') else event.data.get('order_id')
        error = event.error if hasattr(event, 'error') else event.data.get('error')

        logger.warning(f"监控器收到订单提交失败事件: {order_id} - {error}")

        # 优化：订单提交失败，从跟踪列表中移除
        if order_id in self._order_create_times:
            del self._order_create_times[order_id]

        # 创建告警
        alert = OrderAlert(
            alert_id=f"ALT{datetime.now().strftime('%Y%m%d%H%M%S')}",
            order_id=order_id,
            alert_level=AlertLevel.ERROR,
            alert_type="ORDER_SUBMIT_FAILED",
            alert_message=f"订单提交失败: {error}",
            alert_time=datetime.now(),
            order_info={'order_id': order_id, 'error': error}
        )

        self._alerts.append(alert)
        self._send_alert(alert)
