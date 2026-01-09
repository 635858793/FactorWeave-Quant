"""
订单验证器

负责订单有效性验证
"""

from loguru import logger
from datetime import datetime, time
from typing import Dict, Any, Optional
from dataclasses import dataclass

from core.trading.order_models import Order, OrderRequest, OrderType, OrderCategory
from core.containers import ServiceContainer
from core.events import EventBus
from core.plugin_types import AssetType


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    message: str = ""
    error_code: Optional[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class OrderValidator:
    """订单验证器"""

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        self.service_container = service_container
        self.event_bus = event_bus

        self._config = self._load_config()
        logger.info("订单验证器初始化完成")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        return {
            'min_order_quantity': 100,
            'max_order_quantity': 1000000,
            'min_order_price': 0.01,
            'max_order_price': 1000000.0,
            'trading_hours': {
                'start': time(9, 30),
                'end': time(15, 0)
            },
            'max_position_ratio': 0.3,
            'max_daily_loss_ratio': 0.05,
            'max_order_value_ratio': 0.1
        }

    def validate_order_request(self, request: OrderRequest) -> ValidationResult:
        """验证订单请求"""
        try:
            # 1. 基础参数验证
            result = self._validate_basic_params(request)
            if not result.passed:
                return result

            # 2. 交易时间验证（可选，可配置）
            if self._config.get('validate_trading_time', False):
                result = self._validate_trading_time()
                if not result.passed:
                    return result

            # 3. 订单价值限制验证（可选，可配置）
            if self._config.get('validate_order_value', False):
                result = self._validate_order_value_limit(request)
                if not result.passed:
                    return result

            logger.info(f"订单请求验证通过: {request.stock_code} {request.order_type.value}")
            return ValidationResult(passed=True)

        except Exception as e:
            logger.error(f"订单请求验证失败: {e}")
            return ValidationResult(
                passed=False,
                message=f"验证过程发生错误: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def validate_order(self, order: Order) -> ValidationResult:
        """验证订单"""
        try:
            # 1. 基础参数验证
            result = self._validate_order_basic_params(order)
            if not result.passed:
                return result

            # 2. 订单状态验证
            result = self._validate_order_status(order)
            if not result.passed:
                return result

            # 3. 根据资产类型进行特定验证
            if order.asset_type == AssetType.FUTURES:
                result = self._validate_futures_order(order)
            elif order.asset_type == AssetType.OPTION:
                result = self._validate_option_order(order)
            elif order.asset_type in [AssetType.STOCK_A, AssetType.STOCK_B, AssetType.STOCK_H, 
                                    AssetType.STOCK_US, AssetType.STOCK_HK]:
                result = self._validate_stock_order(order)
            else:
                # 其他资产类型暂时通过基础验证
                logger.debug(f"资产类型 {order.asset_type.value} 暂时只进行基础验证")
                result = ValidationResult(passed=True)

            if not result.passed:
                return result

            logger.info(f"订单验证通过: {order.order_id} ({order.asset_type.value})")
            return ValidationResult(passed=True)

        except Exception as e:
            logger.error(f"订单验证失败: {e}")
            return ValidationResult(
                passed=False,
                message=f"验证过程发生错误: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def _validate_basic_params(self, request: OrderRequest) -> ValidationResult:
        """验证基础参数"""
        # 验证订单数量
        if request.order_quantity < self._config['min_order_quantity']:
            return ValidationResult(
                passed=False,
                message=f"订单数量 {request.order_quantity} 小于最小值 {self._config['min_order_quantity']}",
                error_code="INVALID_QUANTITY",
                details={'min_quantity': self._config['min_order_quantity']}
            )

        if request.order_quantity > self._config['max_order_quantity']:
            return ValidationResult(
                passed=False,
                message=f"订单数量 {request.order_quantity} 超过最大值 {self._config['max_order_quantity']}",
                error_code="INVALID_QUANTITY",
                details={'max_quantity': self._config['max_order_quantity']}
            )

        # 验证订单价格
        if request.order_price < self._config['min_order_price']:
            return ValidationResult(
                passed=False,
                message=f"订单价格 {request.order_price} 小于最小值 {self._config['min_order_price']}",
                error_code="INVALID_PRICE",
                details={'min_price': self._config['min_order_price']}
            )

        if request.order_price > self._config['max_order_price']:
            return ValidationResult(
                passed=False,
                message=f"订单价格 {request.order_price} 超过最大值 {self._config['max_order_price']}",
                error_code="INVALID_PRICE",
                details={'max_price': self._config['max_order_price']}
            )

        # 验证止损价格
        if request.order_category in [OrderCategory.STOP, OrderCategory.STOP_LIMIT]:
            if request.stop_price is None:
                return ValidationResult(
                    passed=False,
                    message="止损订单必须指定止损价格",
                    error_code="MISSING_STOP_PRICE"
                )

            if request.stop_price <= 0:
                return ValidationResult(
                    passed=False,
                    message=f"止损价格 {request.stop_price} 必须大于0",
                    error_code="INVALID_STOP_PRICE"
                )

        return ValidationResult(passed=True)

    def _validate_order_basic_params(self, order: Order) -> ValidationResult:
        """验证订单基础参数"""
        # 验证订单数量
        if order.order_quantity <= 0:
            return ValidationResult(
                passed=False,
                message=f"订单数量必须大于0",
                error_code="INVALID_QUANTITY"
            )

        # 验证订单价格
        if order.order_price <= 0:
            return ValidationResult(
                passed=False,
                message=f"订单价格必须大于0",
                error_code="INVALID_PRICE"
            )

        # 验证已成交数量
        if order.filled_quantity < 0:
            return ValidationResult(
                passed=False,
                message=f"已成交数量不能为负数",
                error_code="INVALID_FILLED_QUANTITY"
            )

        if order.filled_quantity > order.order_quantity:
            return ValidationResult(
                passed=False,
                message=f"已成交数量 {order.filled_quantity} 超过订单数量 {order.order_quantity}",
                error_code="INVALID_FILLED_QUANTITY"
            )

        return ValidationResult(passed=True)

    def _validate_trading_time(self) -> ValidationResult:
        """验证交易时间"""
        now = datetime.now().time()
        start_time = self._config['trading_hours']['start']
        end_time = self._config['trading_hours']['end']

        if not (start_time <= now <= end_time):
            return ValidationResult(
                passed=False,
                message=f"当前时间 {now} 不在交易时间内 ({start_time} - {end_time})",
                error_code="INVALID_TRADING_TIME",
                details={'trading_hours': f"{start_time} - {end_time}"}
            )

        return ValidationResult(passed=True)

    def _validate_order_value_limit(self, request: OrderRequest) -> ValidationResult:
        """验证订单价值限制"""
        # TODO: 等待账户管理系统实现后，添加资金和持仓验证
        # 目前暂时通过，避免阻塞
        logger.debug("订单价值限制验证暂时跳过（等待账户管理系统实现）")
        return ValidationResult(passed=True)

    def _validate_order_status(self, order: Order) -> ValidationResult:
        """验证订单状态"""
        # 验证已完成订单不能修改
        if order.is_completed:
            return ValidationResult(
                passed=False,
                message=f"订单 {order.order_id} 已完成，不能修改",
                error_code="ORDER_COMPLETED"
            )

        return ValidationResult(passed=True)

    def update_config(self, config: Dict[str, Any]):
        """更新配置"""
        self._config.update(config)
        logger.info(f"订单验证器配置已更新: {config}")

    def _validate_futures_order(self, order: Order) -> ValidationResult:
        """验证期货订单"""
        try:
            # 验证保证金比例
            if order.margin_ratio < 0 or order.margin_ratio > 1:
                return ValidationResult(
                    passed=False,
                    message=f"保证金比例 {order.margin_ratio} 必须在0到1之间",
                    error_code="INVALID_MARGIN_RATIO",
                    details={'margin_ratio': order.margin_ratio}
                )

            # 验证合约乘数
            if order.contract_multiplier <= 0:
                return ValidationResult(
                    passed=False,
                    message=f"合约乘数 {order.contract_multiplier} 必须大于0",
                    error_code="INVALID_CONTRACT_MULTIPLIER",
                    details={'contract_multiplier': order.contract_multiplier}
                )

            logger.debug(f"期货订单验证通过: {order.order_id}")
            return ValidationResult(passed=True)

        except Exception as e:
            logger.error(f"期货订单验证失败: {e}")
            return ValidationResult(
                passed=False,
                message=f"期货订单验证失败: {str(e)}",
                error_code="FUTURES_VALIDATION_ERROR"
            )

    def _validate_option_order(self, order: Order) -> ValidationResult:
        """验证期权订单"""
        try:
            # 验证行权价
            if not order.strike_price or order.strike_price <= 0:
                return ValidationResult(
                    passed=False,
                    message=f"期权必须有行权价，当前行权价: {order.strike_price}",
                    error_code="MISSING_STRIKE_PRICE",
                    details={'strike_price': order.strike_price}
                )

            # 验证到期日
            if not order.expiry_date:
                return ValidationResult(
                    passed=False,
                    message="期权必须有到期日",
                    error_code="MISSING_EXPIRY_DATE"
                )

            # 验证到期日是否在未来
            if order.expiry_date <= datetime.now():
                return ValidationResult(
                    passed=False,
                    message=f"期权到期日 {order.expiry_date} 必须在未来",
                    error_code="INVALID_EXPIRY_DATE",
                    details={'expiry_date': order.expiry_date}
                )

            # 验证期权类型
            if order.option_type not in ["CALL", "PUT"]:
                return ValidationResult(
                    passed=False,
                    message=f"期权类型必须是CALL或PUT，当前类型: {order.option_type}",
                    error_code="INVALID_OPTION_TYPE",
                    details={'option_type': order.option_type}
                )

            logger.debug(f"期权订单验证通过: {order.order_id}")
            return ValidationResult(passed=True)

        except Exception as e:
            logger.error(f"期权订单验证失败: {e}")
            return ValidationResult(
                passed=False,
                message=f"期权订单验证失败: {str(e)}",
                error_code="OPTION_VALIDATION_ERROR"
            )

    def _validate_stock_order(self, order: Order) -> ValidationResult:
        """验证股票订单"""
        try:
            # 股票订单的额外验证
            # 验证订单数量是否为100的整数倍（A股最小交易单位）
            if order.asset_type == AssetType.STOCK_A and order.order_quantity % 100 != 0:
                return ValidationResult(
                    passed=False,
                    message=f"A股订单数量 {order.order_quantity} 必须是100的整数倍",
                    error_code="INVALID_QUANTITY",
                    details={'order_quantity': order.order_quantity}
                )

            logger.debug(f"股票订单验证通过: {order.order_id}")
            return ValidationResult(passed=True)

        except Exception as e:
            logger.error(f"股票订单验证失败: {e}")
            return ValidationResult(
                passed=False,
                message=f"股票订单验证失败: {str(e)}",
                error_code="STOCK_VALIDATION_ERROR"
            )
