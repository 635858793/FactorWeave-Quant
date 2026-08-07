# -*- coding: utf-8 -*-
"""
XTP Pro交易接口实现

XTP Pro是中泰证券提供的专业交易接口，支持A股、港股、美股等市场。
基于官方Python SDK：https://github.com/ztsec/xtp_api_python
"""

from typing import Dict, Optional, List
from datetime import datetime
from loguru import logger

from core.trading.order_models import Order, OrderStatus
from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface

# XTP SDK (C 扩展) 延迟导入：
# import xtp_api 会加载原生 .pyd，可能触发 0xC0000005 (ACCESS_VIOLATION) 崩溃，
# 且原生崩溃无法被 try/except ImportError 捕获。因此延迟到首次 connect/login 时才导入，
# 避免在模块导入链（如 core.services）中加载 C 扩展导致进程崩溃。
xtp_api = None
XTP_AVAILABLE = False
_xtp_import_attempted = False


def _ensure_xtp_api_loaded():
    """延迟加载 XTP SDK（首次连接时调用），返回 XTP_AVAILABLE 是否可用"""
    global xtp_api, XTP_AVAILABLE, _xtp_import_attempted
    if _xtp_import_attempted:
        return XTP_AVAILABLE
    _xtp_import_attempted = True
    try:
        import xtp_api
        XTP_AVAILABLE = True
        logger.info("XTP SDK加载成功")
    except ImportError:
        xtp_api = None
        XTP_AVAILABLE = False
        logger.warning("XTP SDK未安装，使用模拟模式")
    return XTP_AVAILABLE

try:
    from core.events.event_bus import EventBus
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False
    logger.warning("EventBus未可用，XTP回调将不会发布事件")


class XTPProTradingInterface(TradingInterface):
    """XTP Pro交易接口"""

    def __init__(self, account_id: str = None, password: str = None, 
                 client_id: int = 1, server_address: str = None,
                 trade_server: str = None, quote_server: str = None,
                 event_bus: EventBus = None):
        """
        初始化XTP Pro交易接口

        Args:
            account_id: XTP账户ID
            password: XTP账户密码
            client_id: 客户端ID（默认1）
            server_address: 服务器地址
            trade_server: 交易服务器地址
            quote_server: 行情服务器地址
            event_bus: 事件总线
        """
        self.account_id = account_id
        self.password = password
        self.client_id = client_id
        self.server_address = server_address
        self.trade_server = trade_server
        self.quote_server = quote_server
        self.event_bus = event_bus

        self._connected = False
        self._logged_in = False
        self._orders: Dict[str, Order] = {}
        self._exchange_order_map: Dict[str, str] = {}  # exchange_order_id -> order_id
        self._xtp_api = None

        logger.info(f"初始化XTP Pro交易接口: {account_id}")

    def connect(self) -> bool:
        """
        连接XTP Pro服务器

        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info("正在连接XTP Pro服务器...")

            # 延迟加载 XTP SDK（首次连接时导入 C 扩展）
            _ensure_xtp_api_loaded()

            if not XTP_AVAILABLE:
                logger.warning("XTP SDK未安装，使用模拟模式")
                self._connected = True
                return True

            if not self.trade_server:
                logger.warning("XTP Pro交易服务器地址未配置，使用模拟模式")
                self._connected = True
                return True

            logger.info(f"连接XTP Pro交易服务器: {self.trade_server}")
            logger.info(f"连接XTP Pro行情服务器: {self.quote_server}")

            # 初始化XTP API
            self._xtp_api = xtp_api.XTPApi()
            
            # 设置回调
            self._setup_callbacks()

            # 连接交易服务器
            result = self._xtp_api.Connect(self.trade_server, self.client_id)
            if result != 0:
                logger.error(f"连接XTP Pro交易服务器失败: {result}")
                return False

            # 连接行情服务器
            if self.quote_server:
                result = self._xtp_api.ConnectQuote(self.quote_server, self.client_id)
                if result != 0:
                    logger.warning(f"连接XTP Pro行情服务器失败: {result}")

            self._connected = True
            logger.info("XTP Pro服务器连接成功")
            return True

        except Exception as e:
            logger.error(f"连接XTP Pro服务器失败: {e}")
            self._connected = False
            return False

    def login(self) -> bool:
        """
        登录XTP Pro账户

        Returns:
            bool: 登录是否成功
        """
        try:
            logger.info("正在登录XTP Pro账户...")
            # 延迟加载 XTP SDK（首次登录时导入 C 扩展）
            _ensure_xtp_api_loaded()
            if not self._connected:
                logger.error("未连接到XTP Pro服务器")
                return False

            if not XTP_AVAILABLE:
                logger.warning("XTP SDK未安装，使用模拟模式")
                self._logged_in = True
                return True

            if not self.account_id or not self.password:
                logger.warning("XTP Pro账户信息未配置，使用模拟模式")
                self._logged_in = True
                return True

            logger.info(f"登录XTP Pro账户: {self.account_id}")

            # 登录交易账户
            result = self._xtp_api.Login(
                self.account_id,
                self.password,
                self.client_id
            )
            
            if result != 0:
                logger.error(f"登录XTP Pro账户失败: {result}")
                return False

            self._logged_in = True
            logger.info("XTP Pro账户登录成功")
            return True

        except Exception as e:
            logger.error(f"登录XTP Pro账户失败: {e}")
            self._logged_in = False
            return False

    def disconnect(self):
        """断开XTP Pro连接"""
        try:
            logger.info("正在断开XTP Pro连接...")

            if self._xtp_api:
                if self._logged_in:
                    self._xtp_api.Logout()
                self._xtp_api.Disconnect()
                self._xtp_api.DisconnectQuote()

            self._logged_in = False
            self._connected = False

            logger.info("XTP Pro连接已断开")

        except Exception as e:
            logger.error(f"断开XTP Pro连接失败: {e}")

    def submit_order(self, order: Order) -> ExecutionResult:
        """
        提交订单到XTP Pro

        Args:
            order: 订单对象

        Returns:
            ExecutionResult: 执行结果
        """
        try:
            logger.info(f"提交订单到XTP Pro: {order.order_id}")

            if not self._logged_in:
                logger.error("未登录XTP Pro账户")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录XTP Pro账户",
                    error_code="NOT_LOGGED_IN"
                )

            if not self._connected:
                logger.error("未连接到XTP Pro服务器")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="未连接到XTP Pro服务器",
                    error_code="NOT_CONNECTED"
                )

            if not XTP_AVAILABLE:
                # 模拟模式
                exchange_order_id = self._generate_exchange_order_id(order)
                order.order_status = OrderStatus.SUBMITTED  # 更新订单状态
                self._orders[order.order_id] = order
                self._exchange_order_map[exchange_order_id] = order.order_id
                logger.info(f"XTP Pro订单提交成功（模拟模式）: {order.order_id} -> {exchange_order_id}")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.SUCCESS,
                    message="订单提交成功（模拟模式）",
                    exchange_order_id=exchange_order_id
                )

            # 真实模式：使用XTP API提交订单
            order_req = xtp_api.XTPOrderField()
            order_req.order_xtp_id = 0
            order_req.order_client_id = self.client_id
            order_req.ticker = order.stock_code
            order_req.market = self._get_market_type(order.stock_code)
            order_req.price = int(order.order_price * 10000)  # XTP价格单位
            order_req.quantity = order.order_quantity
            order_req.order_type = self._get_order_type(order.order_category)
            order_req.side = self._get_order_side(order.order_type)
            order_req.price_type = xtp_api.XTP_PRICE_TYPE_LIMIT
            
            result = self._xtp_api.InsertOrder(order_req)
            if result != 0:
                logger.error(f"提交订单到XTP Pro失败: {result}")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"订单提交失败: {result}",
                    error_code=str(result)
                )

            exchange_order_id = self._generate_exchange_order_id(order)
            self._orders[order.order_id] = order
            self._exchange_order_map[exchange_order_id] = order.order_id

            logger.info(f"XTP Pro订单提交成功: {order.order_id} -> {exchange_order_id}")

            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.SUCCESS,
                message="订单提交成功",
                exchange_order_id=exchange_order_id
            )

        except Exception as e:
            logger.error(f"提交订单到XTP Pro失败: {e}")
            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单提交失败: {str(e)}",
                error_code="SUBMIT_FAILED"
            )

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """
        取消XTP Pro订单

        Args:
            order_id: 订单ID

        Returns:
            ExecutionResult: 执行结果
        """
        try:
            logger.info(f"取消XTP Pro订单: {order_id}")

            if not self._logged_in:
                logger.error("未登录XTP Pro账户")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录XTP Pro账户",
                    error_code="NOT_LOGGED_IN"
                )

            if order_id in self._orders:
                order = self._orders[order_id]
                
                if not XTP_AVAILABLE:
                    # 模拟模式
                    logger.info(f"XTP Pro订单取消成功（模拟模式）: {order_id}")
                    return ExecutionResult(
                        order_id=order_id,
                        status=ExecutionStatus.SUCCESS,
                        message="订单取消成功（模拟模式）"
                    )

                # 真实模式：使用XTP API取消订单
                cancel_req = xtp_api.XTPOrderActionField()
                cancel_req.order_xtp_id = order.exchange_order_id
                cancel_req.order_client_id = self.client_id
                
                result = self._xtp_api.CancelOrder(cancel_req)
                if result != 0:
                    logger.error(f"取消XTP Pro订单失败: {result}")
                    return ExecutionResult(
                        order_id=order_id,
                        status=ExecutionStatus.FAILED,
                        message=f"订单取消失败: {result}",
                        error_code=str(result)
                    )

                logger.info(f"XTP Pro订单取消成功: {order_id}")
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
            logger.error(f"取消XTP Pro订单失败: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单取消失败: {str(e)}",
                error_code="CANCEL_FAILED"
            )

    def query_order_status(self, order_id: str) -> ExecutionResult:
        """
        查询订单状态

        Args:
            order_id: 订单ID

        Returns:
            ExecutionResult: 执行结果
        """
        try:
            logger.debug(f"查询XTP Pro订单状态: {order_id}")

            if not self._logged_in:
                logger.error("未登录XTP Pro账户")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录XTP Pro账户",
                    error_code="NOT_LOGGED_IN"
                )

            if order_id in self._orders:
                order = self._orders[order_id]
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.SUCCESS,
                    message="订单状态查询成功",
                    details={
                        "order_status": order.order_status.value,
                        "filled_quantity": order.filled_quantity,
                        "remaining_quantity": order.remaining_quantity
                    }
                )
            else:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="订单不存在",
                    error_code="ORDER_NOT_FOUND"
                )

        except Exception as e:
            logger.error(f"查询XTP Pro订单状态失败: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单状态查询失败: {str(e)}",
                error_code="QUERY_FAILED"
            )

    def query_fund_info(self, account_id: str):
        try:
            logger.debug(f"查询XTP Pro账户资金信息: {account_id}")

            if not self._logged_in:
                logger.warning("未登录XTP Pro账户")
                return None

            try:
                from core.trading.account_manager import AccountManager
                from core.services.service_container import ServiceContainer
                from core.events.event_bus import EventBus

                service_container = ServiceContainer()
                event_bus = service_container.resolve(EventBus)
                account_manager = AccountManager(service_container, event_bus)

                fund_info = account_manager.get_fund_info(account_id)
                if fund_info:
                    logger.debug(f"通过AccountManager获取资金信息成功: {account_id}")
                    return fund_info

                account = account_manager.get_account(account_id)
                if account:
                    from core.trading.account_models import FundInfo
                    fund_info = FundInfo(
                        account_id=account_id,
                        total_balance=account.balance + account.frozen_balance,
                        available_balance=account.available_balance,
                        frozen_balance=account.frozen_balance,
                        market_value=account.market_value,
                        total_assets=account.total_assets,
                        profit_loss=account.profit_loss,
                        profit_loss_ratio=account.profit_loss_ratio,
                        margin_used=0.0,
                        margin_available=account.available_balance,
                        maintenance_margin=account.maintenance_margin,
                        update_time=datetime.now()
                    )
                    logger.debug(f"从Account构建资金信息成功: {account_id}")
                    return fund_info

                logger.warning(f"AccountManager中未找到账户: {account_id}")

            except ImportError as e:
                logger.warning(f"AccountManager不可用: {e}")
            except Exception as e:
                logger.warning(f"通过AccountManager获取资金信息失败: {e}")

            if XTP_AVAILABLE:
                asset = self._xtp_api.QueryAsset()
                if asset:
                    from core.trading.account_models import FundInfo
                    fund_info = FundInfo(
                        account_id=account_id,
                        total_balance=asset.cash + asset.frozen_cash,
                        available_balance=asset.cash,
                        frozen_balance=asset.frozen_cash,
                        market_value=asset.total_asset - asset.cash,
                        total_assets=asset.total_asset,
                        profit_loss=asset.total_asset - asset.balance if hasattr(asset, 'balance') else 0.0,
                        profit_loss_ratio=0.0,
                        margin_used=0.0,
                        margin_available=asset.cash,
                        maintenance_margin=0.0,
                        update_time=datetime.now()
                    )
                    logger.debug(f"通过XTP API获取资金信息成功: {account_id}")
                    return fund_info

            logger.warning(f"无法获取XTP Pro账户资金信息: {account_id}")
            return None

        except Exception as e:
            logger.error(f"查询XTP Pro账户资金信息失败: {e}")
            return None

    def query_positions(self, account_id: str):
        try:
            logger.debug(f"查询XTP Pro账户持仓信息: {account_id}")

            if not self._logged_in:
                logger.warning("未登录XTP Pro账户")
                return []

            try:
                from core.trading.account_manager import AccountManager
                from core.services.service_container import ServiceContainer
                from core.events.event_bus import EventBus

                service_container = ServiceContainer()
                event_bus = service_container.resolve(EventBus)
                account_manager = AccountManager(service_container, event_bus)

                positions = account_manager.get_account_positions(account_id)
                if positions:
                    logger.debug(f"通过AccountManager获取持仓信息成功: {account_id}, 数量: {len(positions)}")
                    return positions

                logger.warning(f"AccountManager中未找到账户持仓: {account_id}")

            except ImportError as e:
                logger.warning(f"AccountManager不可用: {e}")
            except Exception as e:
                logger.warning(f"通过AccountManager获取持仓信息失败: {e}")

            if XTP_AVAILABLE:
                positions_data = self._xtp_api.QueryPosition()
                positions = []

                if positions_data:
                    from core.trading.account_models import Position
                    from core.trading.account_models import PositionSide
                    from core.plugin_types import AssetType

                    for pos in positions_data:
                        position = Position(
                            position_id=f"{account_id}_{pos.ticker}",
                            account_id=account_id,
                            asset_type=AssetType.STOCK_A,
                            stock_code=pos.ticker,
                            stock_name=pos.ticker,
                            side=PositionSide.LONG if pos.quantity > 0 else PositionSide.SHORT,
                            quantity=abs(pos.quantity),
                            available_quantity=abs(pos.can_use_quantity),
                            open_price=pos.open_price,
                            current_price=pos.last_price,
                            market_value=pos.market_value,
                            cost_price=pos.open_price,
                            cost_value=pos.open_price * abs(pos.quantity),
                            profit_loss=pos.unrealized_pnl,
                            profit_loss_ratio=pos.unrealized_pnl / pos.open_price if pos.open_price > 0 else 0,
                            open_time=datetime.now(),
                            update_time=datetime.now()
                        )
                        positions.append(position)

                    logger.debug(f"通过XTP API获取持仓信息成功: {account_id}, 数量: {len(positions)}")
                    return positions

            logger.warning(f"无法获取XTP Pro账户持仓信息: {account_id}")
            return []

        except Exception as e:
            logger.error(f"查询XTP Pro账户持仓信息失败: {e}")
            return []

    def _setup_callbacks(self):
        """设置XTP回调函数"""
        try:
            if not XTP_AVAILABLE:
                return

            # 订单状态回调
            self._xtp_api.SetOnOrderEvent(self._on_order_event)
            
            # 成交回报回调
            self._xtp_api.SetOnTradeEvent(self._on_trade_event)
            
            # 错误回调
            self._xtp_api.SetOnErrorEvent(self._on_error_event)
            
            logger.info("XTP Pro回调函数设置完成")

        except Exception as e:
            logger.error(f"设置XTP Pro回调函数失败: {e}")

    def _on_order_event(self, order_info):
        """
        订单状态回调
        
        Args:
            order_info: XTP订单信息
        """
        try:
            logger.debug(f"XTP Pro订单状态回调: order_xtp_id={order_info.order_xtp_id}, "
                        f"order_status={order_info.order_status}")
            
            # 根据exchange_order_id查找本地订单
            exchange_order_id = str(order_info.order_xtp_id)
            order_id = self._exchange_order_map.get(exchange_order_id)
            
            if not order_id:
                logger.warning(f"未找到对应的本地订单: {exchange_order_id}")
                return
            
            if order_id not in self._orders:
                logger.warning(f"本地订单不存在: {order_id}")
                return
            
            order = self._orders[order_id]
            old_status = order.order_status
            
            # 映射XTP订单状态到系统订单状态
            xtp_status = order_info.order_status
            
            if XTP_AVAILABLE:
                if xtp_status == xtp_api.XTP_ORDER_STATUS_SUBMITTED:
                    new_status = OrderStatus.SUBMITTED
                elif xtp_status == xtp_api.XTP_ORDER_STATUS_CANCELLED:
                    new_status = OrderStatus.CANCELLED
                elif xtp_status == xtp_api.XTP_ORDER_STATUS_PARTIALFILLED:
                    new_status = OrderStatus.PARTIALLY_FILLED
                elif xtp_status == xtp_api.XTP_ORDER_STATUS_FILLED:
                    new_status = OrderStatus.FILLED
                elif xtp_status == xtp_api.XTP_ORDER_STATUS_REJECTED:
                    new_status = OrderStatus.REJECTED
                elif xtp_status == xtp_api.XTP_ORDER_STATUS_UNKNOWN:
                    new_status = OrderStatus.UNKNOWN
                else:
                    new_status = OrderStatus.UNKNOWN
            else:
                # 模拟模式：使用XTP状态常量值
                if xtp_status == 49:  # XTP_ORDER_STATUS_SUBMITTED
                    new_status = OrderStatus.SUBMITTED
                elif xtp_status == 50:  # XTP_ORDER_STATUS_CANCELLED
                    new_status = OrderStatus.CANCELLED
                elif xtp_status == 51:  # XTP_ORDER_STATUS_PARTIALFILLED
                    new_status = OrderStatus.PARTIALLY_FILLED
                elif xtp_status == 52:  # XTP_ORDER_STATUS_FILLED
                    new_status = OrderStatus.FILLED
                elif xtp_status == 53:  # XTP_ORDER_STATUS_REJECTED
                    new_status = OrderStatus.REJECTED
                elif xtp_status == 54:  # XTP_ORDER_STATUS_UNKNOWN
                    new_status = OrderStatus.UNKNOWN
                else:
                    new_status = OrderStatus.UNKNOWN
            
            # 更新订单状态
            if old_status != new_status:
                order.order_status = new_status
                logger.info(f"订单状态更新: {order_id} {old_status.value} -> {new_status.value}")
            
            # 更新订单的其他信息
            if hasattr(order_info, 'filled_quantity'):
                order.filled_quantity = order_info.filled_quantity
            if hasattr(order_info, 'avg_price'):
                order.filled_price = order_info.avg_price
            # remaining_quantity是计算属性，不需要设置
            
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
            logger.error(f"处理XTP Pro订单状态回调失败: {e}")

    def _on_trade_event(self, trade_info):
        """
        成交回报回调
        
        Args:
            trade_info: XTP成交信息
        """
        try:
            logger.debug(f"XTP Pro成交回报: order_xtp_id={trade_info.order_xtp_id}, "
                        f"trade_price={trade_info.price}, trade_volume={trade_info.quantity}")
            
            # 根据exchange_order_id查找本地订单
            exchange_order_id = str(trade_info.order_xtp_id)
            order_id = self._exchange_order_map.get(exchange_order_id)
            
            if not order_id:
                logger.warning(f"未找到对应的本地订单: {exchange_order_id}")
                return
            
            if order_id not in self._orders:
                logger.warning(f"本地订单不存在: {order_id}")
                return
            
            order = self._orders[order_id]
            
            # 更新成交信息
            trade_price = trade_info.price / 10000.0  # XTP价格单位转换
            trade_volume = trade_info.quantity
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
            logger.error(f"处理XTP Pro成交回报回调失败: {e}")

    def _on_error_event(self, error_info):
        """
        错误回调
        
        Args:
            error_info: XTP错误信息
        """
        try:
            error_id = error_info.error_id
            error_msg = error_info.error_msg if hasattr(error_info, 'error_msg') else str(error_info)
            
            logger.error(f"XTP Pro错误回调: error_id={error_id}, error_msg={error_msg}")
            
            # 发布错误事件
            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'xtp_error',
                        error_id=error_id,
                        error_msg=error_msg,
                        account_id=self.account_id,
                        timestamp=datetime.now().isoformat()
                    )
                except Exception as e:
                    logger.error(f"发布XTP错误事件失败: {e}")
            
            # 根据错误类型进行特殊处理（仅在XTP可用时）
            if XTP_AVAILABLE:
                if error_id == xtp_api.XTP_ERROR_CONNECT_FAILED:
                    logger.error("XTP连接失败，尝试重新连接...")
                    self._handle_connection_error()
                elif error_id == xtp_api.XTP_ERROR_LOGIN_FAILED:
                    logger.error("XTP登录失败，请检查账户信息")
                elif error_id == xtp_api.XTP_ERROR_ORDER_FAILED:
                    logger.error("XTP订单提交失败")
            
        except Exception as e:
            logger.error(f"处理XTP Pro错误回调失败: {e}")
    
    def _handle_connection_error(self):
        """处理连接错误，尝试重新连接"""
        try:
            logger.info("尝试重新连接XTP服务器...")
            
            # 断开现有连接
            self.disconnect()
            
            # 等待一段时间后重新连接
            import time
            time.sleep(5)
            
            # 重新连接
            if self.connect():
                logger.info("XTP重新连接成功")
                if self.login():
                    logger.info("XTP重新登录成功")
            else:
                logger.error("XTP重新连接失败")
                
        except Exception as e:
            logger.error(f"处理XTP连接错误失败: {e}")

    def _get_market_type(self, stock_code: str) -> int:
        """获取市场类型"""
        if not XTP_AVAILABLE:
            # 模拟模式：根据股票代码判断市场
            if stock_code.startswith('6'):
                return 1  # 上海市场
            elif stock_code.startswith('0') or stock_code.startswith('3'):
                return 2  # 深圳市场
            else:
                return 1  # 默认上海市场
        
        if stock_code.startswith('6'):
            return xtp_api.XTP_MARKET_TYPE_SH  # 上海
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            return xtp_api.XTP_MARKET_TYPE_SZ  # 深圳
        else:
            return xtp_api.XTP_MARKET_TYPE_SH  # 默认上海

    def _get_order_type(self, order_category) -> int:
        """获取订单类型"""
        from core.trading.order_models import OrderCategory
        
        if not XTP_AVAILABLE:
            # 模拟模式：返回默认值
            return 1  # 限价单
        
        if order_category == OrderCategory.MARKET:
            return xtp_api.XTP_ORDER_TYPE_MARKET
        elif order_category == OrderCategory.STOP:
            return xtp_api.XTP_ORDER_TYPE_STOP
        elif order_category == OrderCategory.STOP_LIMIT:
            return xtp_api.XTP_ORDER_TYPE_STOP_LIMIT
        else:
            return xtp_api.XTP_ORDER_TYPE_LIMIT

    def _get_order_side(self, order_type) -> int:
        """获取订单方向"""
        from core.trading.order_models import OrderType
        
        if not XTP_AVAILABLE:
            # 模拟模式：根据订单类型判断方向
            if order_type == OrderType.BUY:
                return 1  # 买入
            else:
                return 2  # 卖出
        
        if order_type == OrderType.BUY:
            return xtp_api.XTP_SIDE_BUY
        else:
            return xtp_api.XTP_SIDE_SELL

    def _generate_exchange_order_id(self, order: Order) -> str:
        """
        生成XTP Pro交易所订单ID

        Args:
            order: 订单对象

        Returns:
            str: 交易所订单ID
        """
        import time
        timestamp = int(time.time() * 1000)
        return f"XTPPRO{timestamp}{order.order_id[-8:]}"