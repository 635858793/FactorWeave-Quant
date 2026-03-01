#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTP行情接口实现 - 基于ctpbee

CTP（综合交易平台）行情接口，支持期货和期权行情订阅
使用ctpbee框架实现真正的CTP通信
"""

from typing import Dict, Optional, List, Set, Callable, Any
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass, field
from loguru import logger
import threading
import time

from core.trading.interfaces.ctp_config import CTPConfig, get_ctp_config

try:
    from ctpbee import CtpBee, CtpbeeApi
    from ctpbee.constant import TickData, ContractData, BarData
    CTP_AVAILABLE = True
except ImportError:
    CTP_AVAILABLE = False
    logger.warning("ctpbee未安装，请安装: pip install ctpbee")

try:
    from core.events import EventBus, EVENT_BUS_AVAILABLE
except ImportError:
    EVENT_BUS_AVAILABLE = False
    logger.warning("EventBus不可用，将使用基本模式")


@dataclass
class CTPMarketData:
    """CTP行情数据"""
    symbol: str
    exchange: str
    last_price: float
    pre_close: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    turnover: float
    bid_price1: float
    bid_volume1: int
    ask_price1: float
    ask_volume1: int
    update_time: str
    update_millisec: int
    trading_day: str
    action_day: str = ""
    datetime: datetime = None


class MarketDataApi(CtpbeeApi if CTP_AVAILABLE else object):
    """行情数据API处理器 - 继承CtpbeeApi"""

    def __init__(self, name: str, parent: 'CTPMarketInterface' = None):
        if CTP_AVAILABLE:
            super().__init__(name)
        self.parent = parent
        self._contracts: Dict[str, ContractData] = {}

    def on_init(self, init: bool) -> None:
        """初始化完成回调"""
        logger.info(f"CTP行情API初始化完成: {init}")
        if self.parent:
            self.parent._on_api_init(init)

    def on_tick(self, tick: TickData) -> None:
        """行情数据回调"""
        try:
            if self.parent:
                self.parent._on_tick_data(tick)
        except Exception as e:
            logger.error(f"处理行情数据失败: {e}")

    def on_contract(self, contract: ContractData) -> None:
        """合约信息回调"""
        try:
            self._contracts[contract.local_symbol] = contract
            if self.parent:
                self.parent._on_contract_data(contract)
        except Exception as e:
            logger.error(f"处理合约信息失败: {e}")

    def on_realtime(self) -> None:
        """实时回调"""
        pass

    def get_contract(self, local_symbol: str) -> Optional[ContractData]:
        """获取合约信息"""
        return self._contracts.get(local_symbol)


class CTPMarketInterface:
    """CTP行情接口 - 基于ctpbee实现"""

    def __init__(self, config: CTPConfig = None, event_bus: EventBus = None):
        """
        初始化CTP行情接口

        Args:
            config: CTP配置对象，如果为None则使用默认配置
            event_bus: 事件总线，用于发布行情事件
        """
        self.config = config if config else get_ctp_config()
        self.event_bus = event_bus

        self._connected = False
        self._logged_in = False
        self._market_data: Dict[str, CTPMarketData] = {}
        self._subscriptions: Set[str] = set()
        self._data_lock = threading.RLock()
        self._contracts: Dict[str, ContractData] = {}

        self._app: Optional[CtpBee] = None
        self._api: Optional[MarketDataApi] = None
        self._init_complete = False

        logger.info(f"初始化CTP行情接口: {self.config.broker_id}/{self.config.investor_id} (模拟环境: {self.config.use_simulation})")

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
        连接CTP行情服务器

        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info("正在连接CTP行情服务器...")

            if not CTP_AVAILABLE:
                logger.error("ctpbee未安装，无法连接CTP行情服务器，请安装: pip install ctpbee")
                return False

            if not self._validate_config():
                logger.error("CTP配置参数不完整")
                return False

            if not self.config.quote_front:
                logger.error("CTP行情前置地址未配置")
                return False

            self._create_app()

            logger.info(f"连接CTP行情前置: {self.config.quote_front}")
            return True

        except Exception as e:
            logger.error(f"连接CTP行情服务器失败: {e}")
            self._connected = False
            return False

    def login(self) -> bool:
        """
        登录CTP行情账户

        Returns:
            bool: 登录是否成功
        """
        try:
            logger.info("正在登录CTP行情账户...")

            if not self._app:
                logger.error("CTP应用未创建，请先调用connect()")
                return False

            if not CTP_AVAILABLE:
                logger.error("ctpbee未安装，无法登录CTP行情账户")
                return False

            self._start_app()

            self._connected = True
            self._logged_in = True
            logger.info("CTP行情账户登录成功")
            return True

        except Exception as e:
            logger.error(f"登录CTP行情账户失败: {e}")
            self._logged_in = False
            return False

    def disconnect(self):
        """断开CTP行情连接"""
        try:
            logger.info("正在断开CTP行情连接...")

            if self._app:
                try:
                    self._app.stop()
                except Exception as e:
                    logger.warning(f"停止CTP应用失败: {e}")

            self._logged_in = False
            self._connected = False
            self._subscriptions.clear()
            self._app = None
            self._api = None

            logger.info("CTP行情连接已断开")

        except Exception as e:
            logger.error(f"断开CTP行情连接失败: {e}")

    def subscribe_quote(self, symbols: List[str]) -> bool:
        """
        订阅行情

        Args:
            symbols: 合约代码列表（格式：rb2506.SHFE）

        Returns:
            bool: 订阅是否成功
        """
        try:
            logger.info(f"订阅CTP行情: {symbols}")

            if not self._logged_in:
                logger.error("未登录CTP行情账户")
                return False

            if not self._api:
                logger.error("CTP API未初始化")
                return False

            if not CTP_AVAILABLE:
                logger.warning("ctpbee未安装，无法订阅真实行情")
                return False

            with self._data_lock:
                for symbol in symbols:
                    self._subscriptions.add(symbol)
                    try:
                        self._api.action.subscribe(symbol)
                        logger.debug(f"订阅合约成功: {symbol}")
                    except Exception as e:
                        logger.warning(f"订阅合约失败: {symbol}, {e}")

            logger.info(f"CTP行情订阅成功: {len(symbols)} 个合约")
            return True

        except Exception as e:
            logger.error(f"订阅CTP行情失败: {e}")
            return False

    def unsubscribe_quote(self, symbols: List[str]) -> bool:
        """
        取消订阅行情

        Args:
            symbols: 合约代码列表

        Returns:
            bool: 取消订阅是否成功
        """
        try:
            logger.info(f"取消订阅CTP行情: {symbols}")

            with self._data_lock:
                for symbol in symbols:
                    self._subscriptions.discard(symbol)

            logger.info(f"CTP行情取消订阅成功: {len(symbols)} 个合约")
            return True

        except Exception as e:
            logger.error(f"取消订阅CTP行情失败: {e}")
            return False

    def get_quote(self, symbol: str) -> Optional[CTPMarketData]:
        """
        获取行情数据

        Args:
            symbol: 合约代码

        Returns:
            CTPMarketData: 行情数据，如果不存在则返回 None
        """
        try:
            with self._data_lock:
                return self._market_data.get(symbol)

        except Exception as e:
            logger.error(f"获取CTP行情数据失败: {e}")
            return None

    def get_all_quotes(self) -> Dict[str, CTPMarketData]:
        """
        获取所有行情数据

        Returns:
            Dict[str, CTPMarketData]: 行情数据字典
        """
        try:
            with self._data_lock:
                return self._market_data.copy()

        except Exception as e:
            logger.error(f"获取所有CTP行情数据失败: {e}")
            return {}

    def get_contract(self, symbol: str) -> Optional[Any]:
        """获取合约信息"""
        return self._contracts.get(symbol)

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

    def _create_app(self):
        """创建CtpBee应用"""
        if not CTP_AVAILABLE:
            return

        app_name = f"market_{self.config.investor_id}_{int(time.time())}"
        self._app = CtpBee(app_name, __name__)

        config = {
            "CONNECT_INFO": {
                "userid": self.config.investor_id,
                "password": self.config.password,
                "brokerid": self.config.broker_id,
                "md_address": self.config.quote_front,
                "td_address": self.config.trade_front or "",
                "appid": self.config.app_id or "market_app",
                "auth_code": self.config.auth_code or "",
                "product_info": self.config.product_info or ""
            },
            "INTERFACE": "ctp",
            "TD_FUNC": False,
            "MD_FUNC": True
        }

        self._app.config.from_mapping(config)

        self._api = MarketDataApi("market_api", self)
        self._app.add_extension(self._api)

        logger.info(f"CTP应用创建成功: {app_name}")

    def _start_app(self):
        """启动CTP应用"""
        if self._app:
            self._app.start()
            time.sleep(1)

    def _on_api_init(self, init: bool):
        """API初始化回调"""
        self._init_complete = init
        if init:
            logger.info("CTP行情API初始化完成")
            self._on_connected()
        else:
            logger.warning("CTP行情API初始化失败")

    def _on_tick_data(self, tick: TickData):
        """处理行情数据"""
        try:
            ctp_data = CTPMarketData(
                symbol=tick.local_symbol,
                exchange=tick.exchange.value if hasattr(tick.exchange, 'value') else str(tick.exchange),
                last_price=tick.last_price,
                pre_close=tick.pre_close,
                open_price=tick.open_price,
                high_price=tick.high_price,
                low_price=tick.low_price,
                volume=tick.volume,
                turnover=tick.turnover,
                bid_price1=tick.bid_price_1,
                bid_volume1=tick.bid_volume_1,
                ask_price1=tick.ask_price_1,
                ask_volume1=tick.ask_volume_1,
                update_time=str(tick.datetime.time()) if tick.datetime else "",
                update_millisec=0,
                trading_day=tick.trading_day or "",
                datetime=tick.datetime
            )

            with self._data_lock:
                self._market_data[tick.local_symbol] = ctp_data

            logger.debug(f"CTP行情更新: {tick.local_symbol} 价格={tick.last_price:.2f}")

            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'market.quote_updated',
                        symbol=tick.local_symbol,
                        price=tick.last_price,
                        volume=tick.volume,
                        timestamp=datetime.now()
                    )
                except Exception as e:
                    logger.error(f"发布行情更新事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP行情数据失败: {e}")

    def _on_contract_data(self, contract: ContractData):
        """处理合约信息"""
        try:
            self._contracts[contract.local_symbol] = contract
            logger.debug(f"收到合约信息: {contract.local_symbol}")

            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'market.contract_received',
                        symbol=contract.local_symbol,
                        exchange=contract.exchange.value if hasattr(contract.exchange, 'value') else str(contract.exchange),
                        size=contract.size
                    )
                except Exception as e:
                    logger.error(f"发布合约信息事件失败: {e}")

        except Exception as e:
            logger.error(f"处理合约信息失败: {e}")

    def _on_connected(self):
        """连接成功回调"""
        try:
            logger.info("CTP行情服务器连接成功回调")

            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'market.connected',
                        interface_type='CTP',
                        server=self.config.quote_front
                    )
                except Exception as e:
                    logger.error(f"发布连接成功事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP连接成功回调失败: {e}")

    def _on_disconnected(self):
        """连接断开回调"""
        try:
            logger.warning("CTP行情服务器连接断开回调")

            self._connected = False
            self._logged_in = False

            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'market.disconnected',
                        interface_type='CTP'
                    )
                except Exception as e:
                    logger.error(f"发布连接断开事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP连接断开回调失败: {e}")
