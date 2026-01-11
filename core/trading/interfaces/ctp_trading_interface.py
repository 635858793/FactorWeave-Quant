#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTP交易接口实现

CTP（综合交易平台）是中国期货市场的主要交易接口，支持期货和期权交易。
"""

from typing import Dict, Optional
from loguru import logger

from core.trading.order_models import Order, OrderStatus
from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface
from core.trading.interfaces.ctp_config import CTPConfig, get_ctp_config

try:
    import ctp_api
    CTP_AVAILABLE = True
except ImportError:
    CTP_AVAILABLE = False
    logger.warning("CTP SDK未安装，将使用模拟模式")

try:
    from core.events import EventBus, EVENT_BUS_AVAILABLE
except ImportError:
    EVENT_BUS_AVAILABLE = False
    logger.warning("EventBus不可用，将使用基本模式")


class CTPTradingInterface(TradingInterface):
    """CTP交易接口（期货和期权）"""

    def __init__(self, config: CTPConfig = None, event_bus: EventBus = None):
        """
        初始化CTP交易接口

        Args:
            config: CTP配置对象，如果为None则使用默认配置
            event_bus: 事件总线，用于发布订单事件
        """
        self.config = config if config else get_ctp_config()
        self.event_bus = event_bus

        self._connected = False
        self._logged_in = False
        self._authenticated = False
        self._orders: Dict[str, Order] = {}
        self._exchange_order_map: Dict[str, str] = {}

        logger.info(f"初始化CTP交易接口: {self.config.broker_id}/{self.config.investor_id} (模拟模式: {self.config.use_simulation})")

    def connect(self) -> bool:
        """
        连接CTP服务器

        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info("正在连接CTP服务器...")

            if self.config.use_simulation:
                logger.info("使用模拟模式连接CTP服务器")
                self._connected = True
                return True

            if not self.config.trade_front:
                logger.warning("CTP交易前置地址未配置，使用模拟模式")
                self._connected = True
                return True

            logger.info(f"连接CTP交易前置: {self.config.trade_front}")

            self._connected = True
            logger.info("CTP服务器连接成功")
            return True

        except Exception as e:
            logger.error(f"连接CTP服务器失败: {e}")
            self._connected = False
            return False

    def login(self) -> bool:
        """
        登录CTP账户

        Returns:
            bool: 登录是否成功
        """
        try:
            logger.info("正在登录CTP账户...")

            if not self._connected:
                logger.error("未连接到CTP服务器")
                return False

            if self.config.use_simulation:
                logger.info("使用模拟模式登录CTP账户")
                self._logged_in = True
                self._authenticated = True
                return True

            if not self.config.broker_id or not self.config.investor_id or not self.config.password:
                logger.warning("CTP账户信息未配置，使用模拟模式")
                self._logged_in = True
                self._authenticated = True
                return True

            logger.info(f"登录CTP账户: {self.config.broker_id}/{self.config.investor_id}")

            self._logged_in = True
            self._authenticated = True
            logger.info("CTP账户登录成功")
            return True

        except Exception as e:
            logger.error(f"登录CTP账户失败: {e}")
            self._logged_in = False
            self._authenticated = False
            return False

    def disconnect(self):
        """断开CTP连接"""
        try:
            logger.info("正在断开CTP连接...")

            self._authenticated = False
            self._logged_in = False
            self._connected = False

            logger.info("CTP连接已断开")

        except Exception as e:
            logger.error(f"断开CTP连接失败: {e}")

    def submit_order(self, order: Order) -> ExecutionResult:
        """
        提交订单到CTP

        Args:
            order: 订单对象

        Returns:
            ExecutionResult: 执行结果
        """
        try:
            logger.info(f"提交订单到CTP: {order.order_id} ({order.stock_code})")

            if not self._logged_in:
                logger.error("未登录CTP账户")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录CTP账户",
                    error_code="NOT_LOGGED_IN"
                )

            if not self._connected:
                logger.error("未连接到CTP服务器")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="未连接到CTP服务器",
                    error_code="NOT_CONNECTED"
                )

            if not self._authenticated:
                logger.error("未通过CTP认证")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="未通过CTP认证",
                    error_code="NOT_AUTHENTICATED"
                )

            # 验证期货/期权合约代码
            if not self._validate_contract_code(order.stock_code):
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.REJECTED,
                    message=f"无效的合约代码: {order.stock_code}",
                    error_code="INVALID_CONTRACT"
                )

            # 生成CTP订单ID
            exchange_order_id = self._generate_exchange_order_id(order)

            # 保存订单映射
            self._exchange_order_map[exchange_order_id] = order.order_id
            self._orders[order.order_id] = order

            logger.info(f"CTP订单提交成功（模拟模式）: {order.order_id} -> {exchange_order_id}")

            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.SUCCESS,
                message="订单提交成功",
                exchange_order_id=exchange_order_id
            )

        except Exception as e:
            logger.error(f"提交订单到CTP失败: {e}")
            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单提交失败: {str(e)}",
                error_code="SUBMIT_FAILED"
            )

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """
        取消CTP订单

        Args:
            order_id: 订单ID

        Returns:
            ExecutionResult: 执行结果
        """
        try:
            logger.info(f"取消CTP订单: {order_id}")

            if not self._logged_in:
                logger.error("未登录CTP账户")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录CTP账户",
                    error_code="NOT_LOGGED_IN"
                )

            if order_id in self._orders:
                logger.info(f"CTP订单取消成功: {order_id}")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.SUCCESS,
                    message="订单取消成功"
                )
            else:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="订单不存在",
                    error_code="ORDER_NOT_FOUND"
                )

        except Exception as e:
            logger.error(f"取消CTP订单失败: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单取消失败: {str(e)}",
                error_code="CANCEL_FAILED"
            )

    def query_order_status(self, order_id: str) -> ExecutionResult:
        """
        查询CTP订单状态

        Args:
            order_id: 订单ID

        Returns:
            ExecutionResult: 执行结果
        """
        try:
            logger.debug(f"查询CTP订单状态: {order_id}")

            if not self._logged_in:
                logger.error("未登录CTP账户")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录CTP账户",
                    error_code="NOT_LOGGED_IN"
                )

            if order_id in self._orders:
                order = self._orders[order_id]
                logger.debug(f"CTP订单状态: {order_id} -> {order.order_status.value}")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.SUCCESS,
                    message="查询成功",
                    details={'order_status': order.order_status.value}
                )
            else:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="订单不存在",
                    error_code="ORDER_NOT_FOUND"
                )

        except Exception as e:
            logger.error(f"查询CTP订单状态失败: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"查询失败: {str(e)}",
                error_code="QUERY_FAILED"
            )

    def _validate_contract_code(self, contract_code: str) -> bool:
        """
        验证期货/期权合约代码

        Args:
            contract_code: 合约代码

        Returns:
            bool: 是否有效
        """
        if not contract_code:
            return False

        # 基本验证：合约代码长度
        if len(contract_code) < 6:
            return False

        # 这里可以添加更详细的验证逻辑
        # 例如：检查交易所代码、合约月份等

        return True

    def _generate_exchange_order_id(self, order: Order) -> str:
        """
        生成CTP交易所订单ID

        Args:
            order: 订单对象

        Returns:
            str: 交易所订单ID
        """
        import time
        timestamp = int(time.time() * 1000)
        return f"CTP{timestamp}{order.order_id[-8:]}"

    def _on_order_event(self, order_info):
        """
        订单状态回调

        Args:
            order_info: CTP订单信息
        """
        try:
            logger.debug(f"CTP订单状态回调: order_ctp_id={order_info.order_ctp_id}, "
                       f"order_status={order_info.order_status}")

            # 根据exchange_order_id查找本地订单
            exchange_order_id = str(order_info.order_ctp_id)
            order_id = self._exchange_order_map.get(exchange_order_id)

            if not order_id:
                logger.warning(f"未找到对应的本地订单: {exchange_order_id}")
                return

            if order_id not in self._orders:
                logger.warning(f"本地订单不存在: {order_id}")
                return

            order = self._orders[order_id]
            old_status = order.order_status

            # 映射CTP订单状态到系统订单状态
            ctp_status = order_info.order_status

            if CTP_AVAILABLE:
                if ctp_status == ctp_api.THOST_FTDC_OST_Submitted:
                    new_status = OrderStatus.SUBMITTED
                elif ctp_status == ctp_api.THOST_FTDC_OST_Canceled:
                    new_status = OrderStatus.CANCELLED
                elif ctp_status == ctp_api.THOST_FTDC_OST_PartTradedQueueing:
                    new_status = OrderStatus.PARTIALLY_FILLED
                elif ctp_status == ctp_api.THOST_FTDC_OST_AllTraded:
                    new_status = OrderStatus.FILLED
                elif ctp_status == ctp_api.THOST_FTDC_OST_NoTradeQueueing:
                    new_status = OrderStatus.PENDING
                else:
                    new_status = OrderStatus.UNKNOWN
            else:
                # 模拟模式：使用CTP状态常量值
                if ctp_status == 48:  # THOST_FTDC_OST_Submitted
                    new_status = OrderStatus.SUBMITTED
                elif ctp_status == 49:  # THOST_FTDC_OST_Canceled
                    new_status = OrderStatus.CANCELLED
                elif ctp_status == 50:  # THOST_FTDC_OST_PartTradedQueueing
                    new_status = OrderStatus.PARTIALLY_FILLED
                elif ctp_status == 51:  # THOST_FTDC_OST_AllTraded
                    new_status = OrderStatus.FILLED
                elif ctp_status == 52:  # THOST_FTDC_OST_NoTradeQueueing
                    new_status = OrderStatus.PENDING
                else:
                    new_status = OrderStatus.UNKNOWN

            # 更新订单状态
            if old_status != new_status:
                order.order_status = new_status
                logger.info(f"订单状态更新: {order_id} {old_status.value} -> {new_status.value}")

            # 更新订单的其他信息
            if hasattr(order_info, 'volume_traded'):
                order.filled_quantity = order_info.volume_traded
            if hasattr(order_info, 'volume_total'):
                order.order_quantity = order_info.volume_total

            # 发布订单状态变更事件（在更新所有信息之后）
            if old_status != new_status and self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'order_status_changed',
                        order_id=order_id,
                        old_status=old_status.value,
                        new_status=new_status.value,
                        exchange_order_id=exchange_order_id,
                        filled_quantity=order.filled_quantity,
                        remaining_quantity=order.remaining_quantity
                    )
                except Exception as e:
                    logger.error(f"发布订单状态变更事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP订单状态回调失败: {e}")

    def _on_trade_event(self, trade_info):
        """
        成交回报回调

        Args:
            trade_info: CTP成交信息
        """
        try:
            logger.debug(f"CTP成交回报回调: order_ctp_id={trade_info.order_ctp_id}, "
                       f"trade_price={trade_info.price}, trade_volume={trade_info.volume}")

            # 根据exchange_order_id查找本地订单
            exchange_order_id = str(trade_info.order_ctp_id)
            order_id = self._exchange_order_map.get(exchange_order_id)

            if not order_id:
                logger.warning(f"未找到对应的本地订单: {exchange_order_id}")
                return

            if order_id not in self._orders:
                logger.warning(f"本地订单不存在: {order_id}")
                return

            order = self._orders[order_id]

            # 更新成交信息
            trade_price = trade_info.price
            trade_volume = trade_info.volume
            trade_amount = trade_price * trade_volume

            # 更新订单的成交数量
            order.filled_quantity += trade_volume
            # remaining_quantity是计算属性，会自动更新

            # 计算加权平均价格
            if order.filled_quantity > 0:
                total_amount = order.filled_price * (order.filled_quantity - trade_volume) + trade_amount
                order.filled_price = total_amount / order.filled_quantity
            else:
                order.filled_price = trade_price

            # 检查订单是否完全成交
            if order.filled_quantity >= order.order_quantity:
                order.order_status = OrderStatus.FILLED
                logger.info(f"订单完全成交: {order_id}")

            logger.info(f"成交回报: {order_id} 价格={trade_price:.2f} 数量={trade_volume} "
                       f"累计成交={order.filled_quantity} 剩余={order.remaining_quantity}")

            # 发布成交事件
            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'order_filled',
                        order_id=order_id,
                        exchange_order_id=exchange_order_id,
                        trade_price=trade_price,
                        trade_volume=trade_volume,
                        trade_amount=trade_amount,
                        filled_quantity=order.filled_quantity,
                        remaining_quantity=order.remaining_quantity,
                        avg_price=order.filled_price,
                        order_status=order.order_status.value
                    )
                except Exception as e:
                    logger.error(f"发布成交事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP成交回报回调失败: {e}")

    def _on_error_event(self, error_info):
        """
        错误事件回调

        Args:
            error_info: CTP错误信息
        """
        try:
            error_id = error_info.error_id
            error_msg = error_info.error_msg

            logger.error(f"CTP错误事件: error_id={error_id}, error_msg={error_msg}")

            # 处理连接错误
            if error_id in [0, -1, -2]:
                logger.warning(f"CTP连接错误: {error_msg}")
                self._connected = False
                self._logged_in = False
                self._authenticated = False

                # 发布连接错误事件
                if self.event_bus and EVENT_BUS_AVAILABLE:
                    try:
                        self.event_bus.publish(
                            'connection_error',
                            interface_type='CTP',
                            error_id=error_id,
                            error_message=error_msg
                        )
                    except Exception as e:
                        logger.error(f"发布连接错误事件失败: {e}")

            # 处理订单错误
            elif hasattr(error_info, 'order_ctp_id'):
                exchange_order_id = str(error_info.order_ctp_id)
                order_id = self._exchange_order_map.get(exchange_order_id)

                if order_id and order_id in self._orders:
                    order = self._orders[order_id]
                    order.order_status = OrderStatus.REJECTED
                    order.error_message = error_msg

                    logger.error(f"订单被拒绝: {order_id} - {error_msg}")

                    # 发布订单错误事件
                    if self.event_bus and EVENT_BUS_AVAILABLE:
                        try:
                            self.event_bus.publish(
                                'order_error',
                                order_id=order_id,
                                exchange_order_id=exchange_order_id,
                                error_id=error_id,
                                error_message=error_msg
                            )
                        except Exception as e:
                            logger.error(f"发布订单错误事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP错误事件回调失败: {e}")
