"""
风险事件订阅管理器

集中管理所有风险相关EventBus订阅，包括：
- 风险监控事件（来自RiskAlertSystem）
- 订单执行事件（来自OrderExecutor）
- 交易熔断事件

由ServiceContainer在应用启动时初始化，提供统一的订阅生命周期管理。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2025-05-24
"""

from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

from core.events.event_bus import EventBus
from core.risk.compliance_audit_logger import ComplianceAuditLogger, get_audit_logger, EventType


class RiskEventSubscriber:
    """
    风险事件订阅管理器

    职责：
    1. 集中管理所有风险相关EventBus订阅
    2. 将风险事件路由到ComplianceAuditLogger进行合规审计
    3. 提供统一的订阅生命周期管理（订阅/取消/状态查询）
    """

    def __init__(self, audit_logger: Optional[ComplianceAuditLogger] = None):
        self._event_bus = EventBus()
        self._audit_logger = audit_logger or get_audit_logger()
        self._subscriptions: List[Tuple[str, Any]] = []
        self._initialized = False

        logger.info("RiskEventSubscriber初始化完成")

    def initialize(self):
        """初始化所有风险事件订阅"""
        if self._initialized:
            logger.warning("RiskEventSubscriber已经初始化，跳过重复初始化")
            return

        self._subscribe_risk_alert_events()
        self._subscribe_order_execution_events()
        self._subscribe_trading_events()

        self._initialized = True
        logger.info(f"RiskEventSubscriber初始化完成，共 {len(self._subscriptions)} 个EventBus订阅")

    def _subscribe_risk_alert_events(self):
        risk_events = [
            ('risk.monitor', self._handle_risk_monitor),
            ('risk.reduce_position', self._handle_risk_reduce_position),
            ('risk.stop_trading', self._handle_risk_stop_trading),
            ('risk.emergency_liquidation', self._handle_risk_emergency_liquidation),
        ]

        for event_name, handler in risk_events:
            self._event_bus.subscribe(event_name, handler)
            self._subscriptions.append((event_name, handler))
            logger.debug(f"RiskEventSubscriber订阅风险事件: {event_name}")

    def _subscribe_order_execution_events(self):
        order_events = [
            ('order.executed', self._handle_order_executed),
            ('order_submitted_success', self._handle_order_submitted_success),
            ('order_submitted_failed', self._handle_order_submitted_failed),
            ('order_filled', self._handle_order_filled),
            ('order_partially_filled', self._handle_order_partially_filled),
            ('order_cancelled', self._handle_order_cancelled),
            ('order_cancel_failed', self._handle_order_cancel_failed),
            ('order_terminal_state', self._handle_order_terminal_state),
            ('batch_orders_submitted_success', self._handle_batch_orders_success),
            ('batch_orders_submitted_failed', self._handle_batch_orders_failed),
        ]

        for event_name, handler in order_events:
            self._event_bus.subscribe(event_name, handler)
            self._subscriptions.append((event_name, handler))
            logger.debug(f"RiskEventSubscriber订阅订单事件: {event_name}")

    def _subscribe_trading_events(self):
        trading_events = [
            ('trading_interface_circuit_breaker', self._handle_trading_circuit_breaker),
        ]

        for event_name, handler in trading_events:
            self._event_bus.subscribe(event_name, handler)
            self._subscriptions.append((event_name, handler))
            logger.debug(f"RiskEventSubscriber订阅交易事件: {event_name}")

    def _handle_risk_monitor(self, event):
        logger.info(f"[RiskEventSubscriber] 收到风险监控事件: {getattr(event, 'alert', {})}")
        self._audit_logger._on_risk_monitor(event)

    def _handle_risk_reduce_position(self, event):
        logger.warning(f"[RiskEventSubscriber] 收到减仓事件: reduce_ratio={getattr(event, 'reduce_ratio', 0)}")
        self._audit_logger._on_risk_reduce_position(event)

    def _handle_risk_stop_trading(self, event):
        logger.warning(f"[RiskEventSubscriber] 收到停止交易事件: duration={getattr(event, 'duration_minutes', 30)}min")
        self._audit_logger._on_risk_stop_trading(event)

    def _handle_risk_emergency_liquidation(self, event):
        logger.critical(f"[RiskEventSubscriber] 收到紧急平仓事件: {getattr(event, 'alert', {})}")
        self._audit_logger._on_risk_emergency_liquidation(event)

    def _handle_order_executed(self, event):
        logger.info(f"[RiskEventSubscriber] 订单执行: order_id={getattr(event, 'order_id', '')}")
        self._audit_logger._on_order_executed(event)

    def _handle_order_submitted_success(self, event):
        logger.info(f"[RiskEventSubscriber] 订单提交成功: order_id={getattr(event, 'order_id', '')}")
        self._audit_logger._on_order_submitted_success(event)

    def _handle_order_submitted_failed(self, event):
        logger.error(f"[RiskEventSubscriber] 订单提交失败: order_id={getattr(event, 'order_id', '')}, error={getattr(event, 'error', '')}")
        self._audit_logger._on_order_submitted_failed(event)

    def _handle_order_filled(self, event):
        logger.info(f"[RiskEventSubscriber] 订单成交: order_id={getattr(event, 'order_id', '')}, price={getattr(event, 'fill_price', 0)}")
        self._audit_logger._on_order_filled(event)

    def _handle_order_partially_filled(self, event):
        logger.info(f"[RiskEventSubscriber] 订单部分成交: order_id={getattr(event, 'order_id', '')}, qty={getattr(event, 'fill_quantity', 0)}")
        self._audit_logger._on_order_partially_filled(event)

    def _handle_order_cancelled(self, event):
        logger.info(f"[RiskEventSubscriber] 订单取消: order_id={getattr(event, 'order_id', '')}")
        self._audit_logger._on_order_cancelled(event)

    def _handle_order_cancel_failed(self, event):
        logger.error(f"[RiskEventSubscriber] 订单取消失败: order_id={getattr(event, 'order_id', '')}, error={getattr(event, 'error', '')}")
        self._audit_logger._on_order_cancel_failed(event)

    def _handle_order_terminal_state(self, event):
        logger.info(f"[RiskEventSubscriber] 订单终态: order_id={getattr(event, 'order_id', '')}, status={getattr(event, 'status', '')}")
        self._audit_logger._on_order_terminal_state(event)

    def _handle_batch_orders_success(self, event):
        logger.info(f"[RiskEventSubscriber] 批量订单成功: count={getattr(event, 'count', 0)}")
        self._audit_logger._on_batch_orders_success(event)

    def _handle_batch_orders_failed(self, event):
        logger.error(f"[RiskEventSubscriber] 批量订单失败: count={getattr(event, 'count', 0)}")
        self._audit_logger._on_batch_orders_failed(event)

    def _handle_trading_circuit_breaker(self, event):
        logger.critical(f"[RiskEventSubscriber] 交易接口熔断: asset_type={getattr(event, 'asset_type', '')}, consecutive_failures={getattr(event, 'consecutive_failures', 0)}")
        self._audit_logger._on_trading_circuit_breaker(event)

    def unsubscribe_all(self):
        """取消所有EventBus订阅"""
        for event_name, handler in self._subscriptions:
            try:
                self._event_bus.unsubscribe(event_name, handler)
                logger.debug(f"RiskEventSubscriber取消订阅: {event_name}")
            except Exception as e:
                logger.warning(f"RiskEventSubscriber取消订阅失败 {event_name}: {e}")

        self._subscriptions.clear()
        self._initialized = False
        logger.info("RiskEventSubscriber已取消所有EventBus订阅")

    def get_subscription_count(self) -> int:
        """获取当前订阅数量"""
        return len(self._subscriptions)

    def get_subscription_list(self) -> List[str]:
        """获取当前订阅的事件名称列表"""
        return [event_name for event_name, _ in self._subscriptions]

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def dispose(self):
        """释放资源（兼容ServiceContainer的dispose模式）"""
        self.unsubscribe_all()
        if self._audit_logger:
            try:
                self._audit_logger.close()
            except Exception as e:
                logger.warning(f"关闭审计日志记录器失败: {e}")
        logger.info("RiskEventSubscriber已释放所有资源")


_global_risk_subscriber: Optional[RiskEventSubscriber] = None


def get_risk_event_subscriber(audit_logger: Optional[ComplianceAuditLogger] = None) -> RiskEventSubscriber:
    """获取全局风险事件订阅管理器"""
    global _global_risk_subscriber
    if _global_risk_subscriber is None:
        _global_risk_subscriber = RiskEventSubscriber(audit_logger=audit_logger)
        _global_risk_subscriber.initialize()
    return _global_risk_subscriber


def reset_risk_event_subscriber():
    """重置全局风险事件订阅管理器"""
    global _global_risk_subscriber
    if _global_risk_subscriber is not None:
        _global_risk_subscriber.unsubscribe_all()
        _global_risk_subscriber = None