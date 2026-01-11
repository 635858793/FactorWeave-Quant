"""
交易确认与风控服务

验证交易订单，检查交易风险，确认交易执行。
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from decimal import Decimal
from loguru import logger
import threading

from .base_service import BaseService
from ..events import EventBus
from ..containers import ServiceContainer
from ..trading.account_manager import AccountManager
from ..trading.account_models import Account, Position
from .trading_service import TradingOrder, OrderSide, OrderType, OrderStatus


class TradingConfirmationService(BaseService):
    """交易确认与风控服务"""

    def __init__(self, service_container: ServiceContainer, event_bus: Optional[EventBus] = None):
        """
        初始化交易确认与风控服务

        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        super().__init__(event_bus)
        self.service_container = service_container
        
        self._lock = threading.RLock()
        
        self._account_manager: Optional[AccountManager] = None
        
        self._config = {
            'max_order_amount': Decimal('1000000'),
            'max_single_position_ratio': Decimal('0.3'),
            'min_cash_ratio': Decimal('0.1'),
            'enable_risk_check': True,
            'enable_position_limit': True,
        }
        
        self.add_dependency('AccountManager')
        self.add_dependency('TradingService')

    def _do_initialize(self) -> None:
        """初始化服务"""
        try:
            self._account_manager = self.service_container.resolve(AccountManager)
            logger.info("交易确认与风控服务初始化完成")
        except Exception as e:
            logger.error(f"交易确认与风控服务初始化失败: {e}")
            raise

    def confirm_order(self, order: TradingOrder) -> Tuple[bool, str]:
        """
        确认订单

        Args:
            order: 交易订单

        Returns:
            (是否成功, 消息)
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            with self._lock:
                is_valid, message = self.validate_order(order)
                if not is_valid:
                    logger.warning(f"订单验证失败: {order.order_id}, 原因: {message}")
                    self._event_bus.publish('order.validation_failed', order_id=order.order_id, reason=message)
                    return False, f"订单验证失败: {message}"

                if self._config['enable_risk_check']:
                    risk_check = self.check_risk(order)
                    if not risk_check['passed']:
                        logger.warning(f"风险检查未通过: {order.order_id}, 原因: {risk_check['reason']}")
                        self._event_bus.publish('order.risk_check_failed', order_id=order.order_id, reason=risk_check['reason'])
                        return False, f"风险检查未通过: {risk_check['reason']}"

                if self._config['enable_position_limit']:
                    position_check = self.check_position_limit(order)
                    if not position_check['passed']:
                        logger.warning(f"持仓限制检查未通过: {order.order_id}, 原因: {position_check['reason']}")
                        self._event_bus.publish('order.position_limit_failed', order_id=order.order_id, reason=position_check['reason'])
                        return False, f"持仓限制检查未通过: {position_check['reason']}"

                logger.info(f"订单确认成功: {order.order_id}")
                self._event_bus.publish('order.confirmed', order_id=order.order_id)
                return True, "订单确认成功"

        except Exception as e:
            logger.error(f"确认订单失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return False, f"确认订单失败: {e}"

    def validate_order(self, order: TradingOrder) -> Tuple[bool, str]:
        """
        验证订单

        Args:
            order: 交易订单

        Returns:
            (是否有效, 消息)
        """
        try:
            if not order.order_id:
                return False, "订单ID不能为空"

            if not order.symbol:
                return False, "股票代码不能为空"

            if order.quantity <= 0:
                return False, "数量必须大于0"

            if order.order_type == OrderType.LIMIT and order.price is None:
                return False, "限价单必须指定价格"

            if order.price is not None and order.price <= 0:
                return False, "价格必须大于0"

            if order.side not in [OrderSide.BUY, OrderSide.SELL]:
                return False, "无效的订单方向"

            return True, "订单验证通过"

        except Exception as e:
            logger.error(f"验证订单失败: {e}")
            return False, f"验证订单失败: {e}"

    def check_risk(self, order: TradingOrder) -> Dict:
        """
        检查风险

        Args:
            order: 交易订单

        Returns:
            风险检查结果
        """
        try:
            if not self._account_manager:
                return {'passed': False, 'reason': '账户管理器未初始化'}

            account = self._account_manager.get_account(order.order_id)
            if not account:
                return {'passed': False, 'reason': '账户不存在'}

            if order.side == OrderSide.BUY:
                required_amount = Decimal(str(order.quantity)) * (order.price or Decimal('0'))
                if required_amount > account.available_balance:
                    return {
                        'passed': False,
                        'reason': f'资金不足: 需要 {required_amount}, 可用 {account.available_balance}'
                    }

            if order.side == OrderSide.SELL:
                position = self._account_manager.get_position(order.order_id, order.symbol)
                if not position or position.quantity < order.quantity:
                    return {
                        'passed': False,
                        'reason': f'持仓不足: 需要 {order.quantity}, 可用 {position.quantity if position else 0}'
                    }

            return {'passed': True, 'reason': ''}

        except Exception as e:
            logger.error(f"检查风险失败: {e}")
            return {'passed': False, 'reason': f'检查风险失败: {e}'}

    def check_position_limit(self, order: TradingOrder) -> Dict:
        """
        检查持仓限制

        Args:
            order: 交易订单

        Returns:
            持仓限制检查结果
        """
        try:
            if not self._account_manager:
                return {'passed': False, 'reason': '账户管理器未初始化'}

            account = self._account_manager.get_account(order.order_id)
            if not account:
                return {'passed': False, 'reason': '账户不存在'}

            order_amount = Decimal(str(order.quantity)) * (order.price or Decimal('0'))

            if order_amount > self._config['max_order_amount']:
                return {
                    'passed': False,
                    'reason': f'单笔订单金额超过限制: {order_amount} > {self._config["max_order_amount"]}'
                }

            if order.side == OrderSide.BUY:
                current_position = self._account_manager.get_position(order.order_id, order.symbol)
                current_value = current_position.market_value if current_position else Decimal('0')
                new_value = current_value + order_amount
                total_value = account.total_assets
                
                if total_value > 0:
                    position_ratio = new_value / total_value
                    if position_ratio > self._config['max_single_position_ratio']:
                        return {
                            'passed': False,
                            'reason': f'单只股票持仓比例超过限制: {position_ratio:.2%} > {self._config["max_single_position_ratio"]:.2%}'
                        }

            if order.side == OrderSide.BUY:
                new_cash = account.available_balance - order_amount
                if total_value > 0:
                    cash_ratio = new_cash / total_value
                    if cash_ratio < self._config['min_cash_ratio']:
                        return {
                            'passed': False,
                            'reason': f'现金比例低于最小限制: {cash_ratio:.2%} < {self._config["min_cash_ratio"]:.2%}'
                        }

            return {'passed': True, 'reason': ''}

        except Exception as e:
            logger.error(f"检查持仓限制失败: {e}")
            return {'passed': False, 'reason': f'检查持仓限制失败: {e}'}

    def batch_confirm_orders(self, orders: List[TradingOrder]) -> Dict[str, Tuple[bool, str]]:
        """
        批量确认订单

        Args:
            orders: 交易订单列表

        Returns:
            订单ID到确认结果的映射
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            results = {}
            for order in orders:
                results[order.order_id] = self.confirm_order(order)

            self._event_bus.publish(
                'orders.batch_confirmed',
                total=len(orders),
                success=sum(1 for result in results.values() if result[0]),
                failed=sum(1 for result in results.values() if not result[0]),
                timestamp=datetime.now().isoformat()
            )

            return results

        except Exception as e:
            logger.error(f"批量确认订单失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return {}

    def update_config(self, config: Dict) -> None:
        """
        更新配置

        Args:
            config: 新的配置
        """
        self._config.update(config)
        logger.info(f"交易确认与风控服务配置已更新: {config}")

    def _do_health_check(self) -> Optional[Dict[str, Any]]:
        """自定义健康检查"""
        return {
            'account_manager_initialized': self._account_manager is not None,
            'config': self._config
        }
