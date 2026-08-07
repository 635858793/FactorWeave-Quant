#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTP交易接口实现 - 基于ctpbee

CTP（综合交易平台）是中国期货市场的主要交易接口，支持期货和期权交易。
使用ctpbee框架实现真正的CTP通信
"""

from typing import Dict, Optional, List, Any
from datetime import datetime
from loguru import logger
import threading
import time

from core.trading.order_models import Order, OrderStatus
from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface
from core.trading.interfaces.ctp_config import CTPConfig, get_ctp_config

try:
    from ctpbee import CtpBee, CtpbeeApi
    from ctpbee.constant import TickData, ContractData, TradeData, OrderData, Direction, Offset
    CTP_AVAILABLE = True
except ImportError:
    CTP_AVAILABLE = False
    logger.warning("ctpbee未安装，请安装: pip install ctpbee")

try:
    from core.events import EventBus, EVENT_BUS_AVAILABLE
except ImportError:
    EVENT_BUS_AVAILABLE = False
    logger.warning("EventBus不可用，将使用基本模式")


class TradingApi(CtpbeeApi if CTP_AVAILABLE else object):
    """交易API处理器 - 继承CtpbeeApi"""

    def __init__(self, name: str, parent: 'CTPTradingInterface' = None):
        if CTP_AVAILABLE:
            super().__init__(name)
        self.parent = parent
        self._contracts: Dict[str, ContractData] = {}

    def on_init(self, init: bool) -> None:
        """初始化完成回调"""
        logger.info(f"CTP交易API初始化完成: {init}")
        if self.parent:
            self.parent._on_api_init(init)

    def on_tick(self, tick: TickData) -> None:
        """行情数据回调"""
        if self.parent:
            self.parent._on_tick_data(tick)

    def on_contract(self, contract: ContractData) -> None:
        """合约信息回调"""
        self._contracts[contract.local_symbol] = contract
        if self.parent:
            self.parent._on_contract_data(contract)

    def on_order(self, order: OrderData) -> None:
        """订单状态回调"""
        if self.parent:
            self.parent._on_order_data(order)

    def on_trade(self, trade: TradeData) -> None:
        """成交回报回调"""
        if self.parent:
            self.parent._on_trade_data(trade)

    def on_realtime(self) -> None:
        """实时回调"""
        pass

    def get_contract(self, local_symbol: str) -> Optional[ContractData]:
        """获取合约信息"""
        return self._contracts.get(local_symbol)


class CTPTradingInterface(TradingInterface):
    """CTP交易接口 - 基于ctpbee实现"""

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
        self._order_lock = threading.RLock()

        self._app: Optional[CtpBee] = None
        self._api: Optional[TradingApi] = None
        self._init_complete = False
        self._contracts: Dict[str, ContractData] = {}

        logger.info(f"初始化CTP交易接口: {self.config.broker_id}/{self.config.investor_id} (模拟环境: {self.config.use_simulation})")

    @property
    def broker_id(self) -> str:
        """期货公司代码"""
        return self.config.broker_id

    @broker_id.setter
    def broker_id(self, value: str):
        """设置期货公司代码"""
        self.config.broker_id = value

    @property
    def investor_id(self) -> str:
        """投资者代码"""
        return self.config.investor_id

    @investor_id.setter
    def investor_id(self, value: str):
        """设置投资者代码"""
        self.config.investor_id = value

    @property
    def password(self) -> str:
        """密码"""
        return self.config.password

    @password.setter
    def password(self, value: str):
        """设置密码"""
        self.config.password = value

    @property
    def trade_front(self) -> str:
        """交易前置地址"""
        return self.config.trade_front

    @trade_front.setter
    def trade_front(self, value: str):
        """设置交易前置地址"""
        self.config.trade_front = value

    @property
    def quote_front(self) -> str:
        """行情前置地址"""
        return self.config.quote_front

    @quote_front.setter
    def quote_front(self, value: str):
        """设置行情前置地址"""
        self.config.quote_front = value

    @property
    def app_id(self) -> str:
        """应用ID"""
        return self.config.app_id

    @app_id.setter
    def app_id(self, value: str):
        """设置应用ID"""
        self.config.app_id = value

    @property
    def auth_code(self) -> str:
        """认证码"""
        return self.config.auth_code

    @auth_code.setter
    def auth_code(self, value: str):
        """设置认证码"""
        self.config.auth_code = value

    @property
    def product_info(self) -> str:
        """产品信息"""
        return self.config.product_info

    @product_info.setter
    def product_info(self, value: str):
        """设置产品信息"""
        self.config.product_info = value

    def connect(self) -> bool:
        """
        连接CTP服务器

        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info("正在连接CTP服务器...")

            if not CTP_AVAILABLE:
                logger.error("ctpbee未安装，无法连接CTP服务器，请安装: pip install ctpbee")
                return False

            if not self._validate_config():
                logger.error("CTP配置参数不完整")
                return False

            if not self.config.trade_front:
                logger.error("CTP交易前置地址未配置")
                return False

            self._create_app()

            logger.info(f"连接CTP交易前置: {self.config.trade_front}")
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

            if not self._app:
                logger.error("CTP应用未创建，请先调用connect()")
                return False

            if not CTP_AVAILABLE:
                logger.error("ctpbee未安装，无法登录CTP账户")
                return False

            self._start_app()

            self._connected = True
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

            if self._app:
                try:
                    self._app.stop()
                except Exception as e:
                    logger.warning(f"停止CTP应用失败: {e}")

            self._authenticated = False
            self._logged_in = False
            self._connected = False
            self._app = None
            self._api = None

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

            if not self._api:
                logger.error("CTP API未初始化")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="CTP API未初始化",
                    error_code="API_NOT_INITIALIZED"
                )

            if not self._validate_contract_code(order.stock_code):
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.REJECTED,
                    message=f"无效的合约代码: {order.stock_code}",
                    error_code="INVALID_CONTRACT"
                )

            direction, offset = self._parse_order_direction(order.order_direction)

            # R257-P0: 捕获 CTP 侧订单号 (ctpbee action 返回值), 供回报回调反查本地订单
            # 注意: 返回值可能是字符串/对象/None (ctpbee 版本差异), 用 try/except 保守处理,
            # 拿不到字符串订单号时仅记 debug 日志, 不阻断主流程
            ctpbee_order_id = None
            try:
                if direction == Direction.LONG:
                    if offset == Offset.OPEN:
                        ctpbee_order_id = self._api.action.buy_open(order.price, order.order_quantity, order.stock_code)
                    else:
                        ctpbee_order_id = self._api.action.buy_close(order.price, order.order_quantity, order.stock_code)
                else:
                    if offset == Offset.OPEN:
                        ctpbee_order_id = self._api.action.sell_open(order.price, order.order_quantity, order.stock_code)
                    else:
                        ctpbee_order_id = self._api.action.sell_close(order.price, order.order_quantity, order.stock_code)

                with self._order_lock:
                    self._orders[order.order_id] = order
                    if ctpbee_order_id and isinstance(ctpbee_order_id, str):
                        self._exchange_order_map[ctpbee_order_id] = order.order_id
                    else:
                        logger.debug(f"CTP下单未返回字符串订单号({ctpbee_order_id!r}), 跳过交易所映射: {order.order_id}")

                logger.info(f"CTP订单提交成功: {order.order_id}")

                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.SUCCESS,
                    message="订单提交成功",
                    exchange_order_id=ctpbee_order_id if isinstance(ctpbee_order_id, str) else None
                )

            except Exception as e:
                logger.error(f"CTP报单失败: {e}")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"CTP报单失败: {str(e)}",
                    error_code="CTP_ORDER_FAILED"
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

            if not self._api:
                logger.error("CTP API未初始化")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="CTP API未初始化",
                    error_code="API_NOT_INITIALIZED"
                )

            with self._order_lock:
                if order_id in self._orders:
                    order = self._orders[order_id]
                    try:
                        # R257-P1: 撤单必须传 CTP 侧订单号 (本地 UUID 与 CTP 订单号不相交)
                        # _exchange_order_map 语义为 exchange_id -> local_id, 此处按 local_id 反查;
                        # get(order_id) 兜底兼容直接命中场景
                        ctpbee_id = order_id
                        for _ex_id, _local_id in self._exchange_order_map.items():
                            if _local_id == order_id:
                                ctpbee_id = _ex_id
                                break
                        ctpbee_id = self._exchange_order_map.get(order_id, ctpbee_id)
                        self._api.action.cancel_order(order.stock_code, ctpbee_id)
                        logger.info(f"CTP订单取消成功: {order_id} -> {ctpbee_id}")
                        return ExecutionResult(
                            order_id=order_id,
                            status=ExecutionStatus.SUCCESS,
                            message="订单取消成功"
                        )
                    except Exception as e:
                        logger.error(f"CTP撤单失败: {e}")
                        return ExecutionResult(
                            order_id=order_id,
                            status=ExecutionStatus.FAILED,
                            message=f"CTP撤单失败: {str(e)}",
                            error_code="CTP_CANCEL_FAILED"
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

            with self._order_lock:
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

    def query_fund_info(self, account_id: str):
        """
        查询账户资金信息（基类接口适配）

        Args:
            account_id: 账户ID

        Returns:
            FundInfo 或 Dict: 资金信息
        """
        try:
            from core.trading.account_models import FundInfo
            account_data = self.get_account()
            if not account_data:
                return None
            return FundInfo(
                account_id=account_id,
                total_assets=account_data.get('balance', 0),
                available_cash=account_data.get('available', 0),
                market_value=0.0,
                frozen_cash=account_data.get('frozen_cash', 0),
                total_profit_loss=0.0,
                today_profit_loss=0.0,
                update_time=datetime.now()
            )
        except Exception as e:
            logger.error(f"查询CTP账户资金信息失败: {e}")
            return None

    def query_positions(self, account_id: str):
        """
        查询账户持仓信息（基类接口适配）

        Args:
            account_id: 账户ID

        Returns:
            List[Position]: 持仓列表
        """
        try:
            from core.trading.account_models import Position, PositionSide
            raw_positions = self.get_position()
            positions = []
            for symbol, pos_data in raw_positions.items():
                long_qty = pos_data.get('long_pos', 0)
                short_qty = pos_data.get('short_pos', 0)
                if long_qty > 0:
                    positions.append(Position(
                        position_id=f"{account_id}_{symbol}_L",
                        account_id=account_id,
                        stock_code=symbol,
                        stock_name=symbol,
                        position_side=PositionSide.LONG,
                        quantity=long_qty,
                        available_quantity=long_qty - pos_data.get('long_frozen', 0),
                        cost_price=0.0,
                        current_price=0.0,
                        market_value=0.0,
                        profit_loss=0.0,
                        profit_loss_ratio=0.0,
                        update_time=datetime.now()
                    ))
                if short_qty > 0:
                    positions.append(Position(
                        position_id=f"{account_id}_{symbol}_S",
                        account_id=account_id,
                        stock_code=symbol,
                        stock_name=symbol,
                        position_side=PositionSide.SHORT,
                        quantity=short_qty,
                        available_quantity=short_qty - pos_data.get('short_frozen', 0),
                        cost_price=0.0,
                        current_price=0.0,
                        market_value=0.0,
                        profit_loss=0.0,
                        profit_loss_ratio=0.0,
                        update_time=datetime.now()
                    ))
            return positions
        except Exception as e:
            logger.error(f"查询CTP账户持仓信息失败: {e}")
            return []

    def get_position(self, symbol: str = None) -> Dict[str, Any]:
        """
        获取持仓信息（原始CTP格式）

        Args:
            symbol: 合约代码，如果为None则返回所有持仓

        Returns:
            Dict: 持仓信息
        """
        try:
            if not self._api or not self._logged_in:
                return {}

            positions = {}
            if hasattr(self._api, 'center'):
                pos_manager = self._api.center
                if symbol:
                    pos = pos_manager.get_position(symbol)
                    if pos:
                        positions[symbol] = {
                            'long_pos': pos.long_pos,
                            'short_pos': pos.short_pos,
                            'long_frozen': pos.long_frozen,
                            'short_frozen': pos.short_frozen,
                        }
                else:
                    for local_symbol, pos in pos_manager.positions.items():
                        positions[local_symbol] = {
                            'long_pos': pos.long_pos,
                            'short_pos': pos.short_pos,
                            'long_frozen': pos.long_frozen,
                            'short_frozen': pos.short_frozen,
                        }

            return positions

        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return {}

    def get_account(self) -> Dict[str, Any]:
        """
        获取账户资金信息（原始CTP格式）

        Returns:
            Dict: 账户资金信息
        """
        try:
            if not self._api or not self._logged_in:
                return {}

            account = {}
            if hasattr(self._api, 'center') and hasattr(self._api.center, 'account'):
                acc = self._api.center.account
                account = {
                    'balance': acc.balance if hasattr(acc, 'balance') else 0,
                    'available': acc.available if hasattr(acc, 'available') else 0,
                    'margin': acc.margin if hasattr(acc, 'margin') else 0,
                    'frozen_margin': acc.frozen_margin if hasattr(acc, 'frozen_margin') else 0,
                    'frozen_cash': acc.frozen_cash if hasattr(acc, 'frozen_cash') else 0,
                }

            return account

        except Exception as e:
            logger.error(f"获取账户资金信息失败: {e}")
            return {}

    def _validate_config(self) -> bool:
        """验证配置参数"""
        if not self.config.broker_id:
            logger.error("broker_id未配置")
            return False
        if not self.config.investor_id:
            logger.error("investor_id未配置")
            return False
        if not self.config.password:
            logger.error("password未配置")
            return False
        return True

    def _validate_contract_code(self, contract_code: str) -> bool:
        """验证期货/期权合约代码"""
        if not contract_code:
            return False
        if len(contract_code) < 6:
            return False
        return True

    def _parse_order_direction(self, direction: str) -> tuple:
        """解析订单方向"""
        if not CTP_AVAILABLE:
            return (None, None)

        direction_upper = direction.upper() if isinstance(direction, str) else str(direction)

        if direction_upper in ['BUY', 'BUY_OPEN', 'B']:
            return (Direction.LONG, Offset.OPEN)
        elif direction_upper in ['SELL', 'SELL_OPEN', 'S']:
            return (Direction.SHORT, Offset.OPEN)
        elif direction_upper in ['BUY_CLOSE', 'BC']:
            return (Direction.LONG, Offset.CLOSE)
        elif direction_upper in ['SELL_CLOSE', 'SC']:
            return (Direction.SHORT, Offset.CLOSE)
        else:
            return (Direction.LONG, Offset.OPEN)

    def _create_app(self):
        """创建CtpBee应用"""
        if not CTP_AVAILABLE:
            return

        app_name = f"trading_{self.config.investor_id}_{int(time.time())}"
        self._app = CtpBee(app_name, __name__)

        config = {
            "CONNECT_INFO": {
                "userid": self.config.investor_id,
                "password": self.config.password,
                "brokerid": self.config.broker_id,
                "md_address": self.config.quote_front or "",
                "td_address": self.config.trade_front,
                "appid": self.config.app_id or "trading_app",
                "auth_code": self.config.auth_code or "",
                "product_info": self.config.product_info or ""
            },
            "INTERFACE": "ctp",
            "TD_FUNC": True,
            "MD_FUNC": True
        }

        self._app.config.from_mapping(config)

        self._api = TradingApi("trading_api", self)
        self._app.add_extension(self._api)

        logger.info(f"CTP交易应用创建成功: {app_name}")

    def _start_app(self):
        """启动CTP应用"""
        if self._app:
            self._app.start()
            time.sleep(1)

    def _on_api_init(self, init: bool):
        """API初始化回调"""
        self._init_complete = init
        if init:
            logger.info("CTP交易API初始化完成")
        else:
            logger.warning("CTP交易API初始化失败")

    def _on_tick_data(self, tick: TickData):
        """处理行情数据"""
        pass

    def _on_contract_data(self, contract: ContractData):
        """处理合约信息"""
        self._contracts[contract.local_symbol] = contract
        logger.debug(f"收到合约信息: {contract.local_symbol}")

    def _on_order_data(self, order: OrderData):
        """处理订单状态"""
        try:
            logger.debug(f"CTP订单状态回调: {order.order_id}, status={order.status}")

            # R257-P0: 回报回调的 order_id 是 CTP 侧订单号, 与本地 UUID 不相交,
            # 必须经 _exchange_order_map 反查本地订单; `or ctpbee_id` 兜底兼容直接命中场景
            ctpbee_id = order.order_id
            local_id = self._exchange_order_map.get(ctpbee_id) or ctpbee_id

            with self._order_lock:
                if local_id not in self._orders:
                    logger.warning(f"CTP回报未匹配到本地订单: {ctpbee_id}")
                    return

                local_order = self._orders[local_id]

                status_map = {
                    'SUBMITTING': OrderStatus.PENDING,
                    'SUBMITTED': OrderStatus.SUBMITTED,
                    'PARTTRADED': OrderStatus.PARTIALLY_FILLED,
                    'ALLTRADED': OrderStatus.FILLED,
                    'CANCELLED': OrderStatus.CANCELLED,
                    'NOTTRADED': OrderStatus.PENDING,
                    'REJECTED': OrderStatus.REJECTED,
                }

                # R257-P0: 默认值 OrderStatus.UNKNOWN 不存在于枚举, 改用 FAILED
                new_status = status_map.get(order.status, OrderStatus.FAILED)
                old_status = local_order.order_status

                if old_status != new_status:
                    local_order.order_status = new_status
                    logger.info(f"订单状态更新: {local_id} {old_status.value} -> {new_status.value}")

                    if self.event_bus and EVENT_BUS_AVAILABLE:
                        try:
                            # R257-P1: ctpbee 字段名兼容 (traded_volume 可能不存在, 回退 traded)
                            traded_volume = getattr(order, 'traded_volume', getattr(order, 'traded', 0))
                            volume = getattr(order, 'volume', 0)
                            self.event_bus.publish(
                                'order_status_changed',
                                order_id=local_id,
                                old_status=old_status.value,
                                new_status=new_status.value,
                                filled_quantity=traded_volume,
                                remaining_quantity=volume - traded_volume
                            )
                        except Exception as e:
                            logger.error(f"发布订单状态变更事件失败: {e}")

                # R257-P2: 终态清理, 防止 _orders/_exchange_order_map 内存累积
                if new_status in (OrderStatus.FILLED, OrderStatus.CANCELLED,
                                  OrderStatus.REJECTED, OrderStatus.EXPIRED):
                    self._exchange_order_map.pop(ctpbee_id, None)
                    self._orders.pop(local_id, None)

        except Exception as e:
            logger.error(f"处理CTP订单状态回调失败: {e}")

    def _on_trade_data(self, trade: TradeData):
        """处理成交回报"""
        try:
            logger.debug(f"CTP成交回报回调: {trade.order_id}, price={trade.price}, volume={trade.volume}")

            # R257-P0: 同 _on_order_data, 经 _exchange_order_map 反查本地订单
            ctpbee_id = trade.order_id
            local_id = self._exchange_order_map.get(ctpbee_id) or ctpbee_id

            with self._order_lock:
                if local_id not in self._orders:
                    logger.warning(f"CTP成交回报未匹配到本地订单: {ctpbee_id}")
                    return

                order = self._orders[local_id]

                order.filled_quantity += trade.volume
                if order.filled_quantity > 0:
                    total_amount = order.filled_price * (order.filled_quantity - trade.volume) + trade.price * trade.volume
                    order.filled_price = total_amount / order.filled_quantity

                if order.filled_quantity >= order.order_quantity:
                    order.order_status = OrderStatus.FILLED
                    logger.info(f"订单完全成交: {local_id}")

                logger.info(f"成交回报: {local_id} 价格={trade.price:.2f} 数量={trade.volume}")

                if self.event_bus and EVENT_BUS_AVAILABLE:
                    try:
                        self.event_bus.publish(
                            'order_filled',
                            order_id=local_id,
                            trade_price=trade.price,
                            trade_volume=trade.volume,
                            filled_quantity=order.filled_quantity,
                            avg_price=order.filled_price
                        )
                    except Exception as e:
                        logger.error(f"发布成交事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP成交回报回调失败: {e}")
