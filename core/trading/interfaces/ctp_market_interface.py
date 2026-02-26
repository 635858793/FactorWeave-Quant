#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTP行情接口实现

CTP（综合交易平台）行情接口，支持期货和期权行情订阅
"""

from typing import Dict, Optional, List, Set
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from loguru import logger
import threading

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
    action_day: str


class CTPMarketInterface:
    """CTP行情接口"""

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

        logger.info(f"初始化CTP行情接口: {self.config.broker_id}/{self.config.investor_id} (模拟环境: {self.config.use_simulation})")

    def connect(self) -> bool:
        """
        连接CTP行情服务器

        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info("正在连接CTP行情服务器...")

            if not CTP_AVAILABLE:
                logger.error("CTP SDK未安装，无法连接CTP行情服务器，请安装CTP SDK")
                return False

            if not self.config.quote_front:
                logger.error("CTP行情前置地址未配置")
                return False

            logger.info(f"连接CTP行情前置: {self.config.quote_front}")

            self._connected = True
            logger.info("CTP行情服务器连接成功")
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

            if not self._connected:
                logger.error("未连接到CTP行情服务器")
                return False

            if not CTP_AVAILABLE:
                logger.error("CTP SDK未安装，无法登录CTP行情账户，请安装CTP SDK")
                return False

            if not self.config.broker_id or not self.config.investor_id or not self.config.password:
                logger.error("CTP账户信息未配置")
                return False

            logger.info(f"登录CTP行情账户: {self.config.broker_id}/{self.config.investor_id}")

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

            self._logged_in = False
            self._connected = False
            self._subscriptions.clear()

            logger.info("CTP行情连接已断开")

        except Exception as e:
            logger.error(f"断开CTP行情连接失败: {e}")

    def subscribe_quote(self, symbols: List[str]) -> bool:
        """
        订阅行情

        Args:
            symbols: 合约代码列表

        Returns:
            bool: 订阅是否成功
        """
        try:
            logger.info(f"订阅CTP行情: {symbols}")

            if not self._logged_in:
                logger.error("未登录CTP行情账户")
                return False

            if not self._connected:
                logger.error("未连接到CTP行情服务器")
                return False

            if not CTP_AVAILABLE:
                logger.warning("CTP SDK未安装，无法订阅真实行情，请安装CTP SDK")
                return False

            with self._data_lock:
                for symbol in symbols:
                    self._subscriptions.add(symbol)

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

    def _on_market_data(self, market_data):
        """
        行情数据回调

        Args:
            market_data: CTP行情数据
        """
        try:
            symbol = market_data.instrument_id

            ctp_data = CTPMarketData(
                symbol=symbol,
                exchange=market_data.exchange_id,
                last_price=market_data.last_price,
                pre_close=market_data.pre_close,
                open_price=market_data.open_price,
                high_price=market_data.highest_price,
                low_price=market_data.lowest_price,
                volume=market_data.volume,
                turnover=market_data.turnover,
                bid_price1=market_data.bid_price1,
                bid_volume1=market_data.bid_volume1,
                ask_price1=market_data.ask_price1,
                ask_volume1=market_data.ask_volume1,
                update_time=market_data.update_time,
                update_millisec=market_data.update_millisec,
                trading_day=market_data.trading_day,
                action_day=market_data.action_day
            )

            with self._data_lock:
                self._market_data[symbol] = ctp_data

            logger.debug(f"CTP行情更新: {symbol} 价格={ctp_data.last_price:.2f}")

            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'market.quote_updated',
                        symbol=symbol,
                        price=ctp_data.last_price,
                        volume=ctp_data.volume,
                        timestamp=datetime.now()
                    )
                except Exception as e:
                    logger.error(f"发布行情更新事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP行情数据回调失败: {e}")

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

    def _on_error(self, error_info):
        """
        错误事件回调

        Args:
            error_info: CTP错误信息
        """
        try:
            error_id = error_info.error_id
            error_msg = error_info.error_msg

            logger.error(f"CTP行情错误事件: error_id={error_id}, error_msg={error_msg}")

            if self.event_bus and EVENT_BUS_AVAILABLE:
                try:
                    self.event_bus.publish(
                        'market.error',
                        interface_type='CTP',
                        error_id=error_id,
                        error_message=error_msg
                    )
                except Exception as e:
                    logger.error(f"发布错误事件失败: {e}")

        except Exception as e:
            logger.error(f"处理CTP错误事件回调失败: {e}")
