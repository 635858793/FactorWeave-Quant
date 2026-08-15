"""
订单执行器

负责订单执行与接口对接
"""

import os
from loguru import logger
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from core.trading.order_models import Order, OrderFill, OrderType, OrderStatus, OrderCategory
from core.trading.order_repository import OrderRepository, get_order_repository
from core.containers import ServiceContainer
from core.events import get_event_bus
from core.events.event_bus import EventBus
from core.plugin_types import AssetType
from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface
# 注意：真实交易接口（XTP/CTP/miniQMT）不在模块级导入，改为延迟到实际使用/连接时加载，
# 避免模块导入链加载 C 扩展 (.pyd) 触发原生崩溃 (0xC0000005)。

from core.trading.account_models import TradingInterfaceType, Account
from typing import Optional


class MockTradingInterface(TradingInterface):
    """模拟交易接口 - 整合真实计算链路（AccountManager + TradingEngine）"""

    # R255-P0: Mock 接口标记 (模式闸门放行依据: _is_mock_interface=True → 不拦截)
    _is_mock_interface = True

    def __init__(self, service_container=None, event_bus=None):
        self._orders: Dict[str, Order] = {}
        self._order_counter = 0
        self._connected = True
        self._logged_in = True

        self._service_container = service_container
        # HVD-241-P1-B: event_bus or → is not None (EventBus __len__ falsy 陷阱, R240-P0-007)
        self._event_bus = event_bus if event_bus is not None else get_event_bus()
        self._trading_engine = None
        self._account_manager = None
        self._fill_records: List[Dict[str, Any]] = []

        self._init_real_components()

    def _init_real_components(self):
        if self._service_container:
            try:
                from core.trading.account_manager import AccountManager
                self._account_manager = self._service_container.resolve(AccountManager)
                logger.info("MockTradingInterface: 使用真实AccountManager")
            except Exception as e:
                self._account_manager = None
                logger.warning(f"MockTradingInterface: AccountManager不可用，使用默认值: {e}")

            try:
                from core.trading_engine import TradingEngine
                self._trading_engine = TradingEngine(self._service_container, self._event_bus)
                logger.info("MockTradingInterface: 使用真实TradingEngine计算链路")
            except Exception as e:
                self._trading_engine = None
                logger.warning(f"MockTradingInterface: TradingEngine初始化失败，使用默认计算: {e}")

    def connect(self) -> bool:
        self._connected = True
        return True

    def login(self) -> bool:
        self._logged_in = True
        return True

    def disconnect(self):
        self._logged_in = False
        self._connected = False

    def submit_order(self, order: Order) -> ExecutionResult:
        """提交订单（整合真实计算：滑点 + 手续费 + TradingEngine同步）"""
        try:
            self._order_counter += 1
            exchange_order_id = f"EXC{self._order_counter:08d}"

            commission_pct, slippage_pct = self._get_trading_config(order)
            asset_type = getattr(order, 'asset_type', None)
            is_sell = order.order_type.value in ('sell', 'short')
            is_buy = not is_sell

            order_category = getattr(order, 'order_category', None)
            order_category_value = getattr(order_category, 'value', '') if order_category else ''
            is_market_order = (order_category_value.upper() == 'MARKET')

            if is_market_order:
                spread_pct = 0.001
                if is_buy:
                    filled_price = order.order_price * (1.0 + spread_pct + slippage_pct)
                else:
                    filled_price = order.order_price * (1.0 - spread_pct - slippage_pct)
            else:
                if is_sell:
                    filled_price = order.order_price * (1.0 - slippage_pct)
                else:
                    filled_price = order.order_price * (1.0 + slippage_pct)

            # 计算手续费
            if self._trading_engine and asset_type:
                commission = self._trading_engine._calculate_cost(
                    filled_price, order.order_quantity, is_buy=is_buy, asset_type=asset_type
                )
            else:
                commission = filled_price * order.order_quantity * commission_pct

            # 记录成交信息到 TradingEngine 内置交易日志
            fill_record = {
                'fill_id': f"FILL_{exchange_order_id}",
                'order_id': order.order_id,
                'stock_code': order.stock_code,
                'fill_price': round(filled_price, 4),
                'fill_quantity': order.order_quantity,
                'commission': round(commission, 4),
                'fill_time': datetime.now(),
                'slippage_pct': slippage_pct,
                'commission_pct': commission_pct,
            }
            self._fill_records.append(fill_record)
            order.filled_price = filled_price
            order.commission = commission

            if self._trading_engine:
                try:
                    from core.trading_engine import TradingSignal, SignalType
                    signal = TradingSignal(
                        symbol=order.stock_code,
                        signal_type=SignalType.BUY if is_buy else SignalType.SELL,
                        timestamp=datetime.now(),
                        price=filled_price,
                        volume=order.order_quantity,
                        asset_type=asset_type,
                    )
                    self._trading_engine.signals.append(signal)
                    logger.info(f"MockTradingInterface: 已同步订单到TradingEngine: {order.order_id}")
                except Exception as e:
                    logger.warning(f"MockTradingInterface: TradingEngine同步失败: {e}")

            self._orders[order.order_id] = order

            logger.info(
                f"MockTradingInterface: 订单提交 | {order.order_id} -> {exchange_order_id} | "
                f"请求价={order.order_price:.4f} 成交价={filled_price:.4f} "
                f"滑点={slippage_pct:.4%} 佣金={commission:.4f}"
            )

            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.SUCCESS,
                message=f"订单提交成功（滑点调整: {filled_price:.4f}）",
                exchange_order_id=exchange_order_id,
                details={
                    'filled_price': filled_price,
                    'commission': commission,
                    'slippage_pct': slippage_pct,
                    'commission_pct': commission_pct,
                }
            )

        except Exception as e:
            logger.error(f"模拟提交订单失败: {e}")
            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单提交失败: {str(e)}",
                error_code="SUBMIT_FAILED"
            )

    def _get_trading_config(self, order=None):
        commission_pct = 0.0003
        slippage_pct = 0.0001

        try:
            if self._trading_engine and order and hasattr(order, 'asset_type') and order.asset_type:
                commission_pct = self._trading_engine.commission_rates.get(
                    order.asset_type, self._trading_engine.commission_rate
                )
        except Exception as e:
            logger.debug(f"获取资产类型佣金费率失败: {e}")

        try:
            from core.trading.trading_mode import ModeContext
            paper_ctx = ModeContext.create_paper()
            slippage_pct = paper_ctx.config.get('slippage', 0.0001)
            commission_pct = paper_ctx.config.get('commission_rate', commission_pct)
        except Exception as e:
            logger.debug(f"获取模拟交易滑点配置失败: {e}")

        return commission_pct, slippage_pct

    def get_fill_records(self) -> List[Dict[str, Any]]:
        """获取Mock交易成交记录（模拟TradingEngine日志）"""
        return self._fill_records.copy()

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """取消订单（模拟）"""
        try:
            if order_id in self._orders:
                logger.info(f"模拟取消订单: {order_id}")
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
            logger.error(f"模拟取消订单失败: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单取消失败: {str(e)}",
                error_code="CANCEL_FAILED"
            )

    def query_order_status(self, order_id: str) -> ExecutionResult:
        """查询订单状态（模拟）"""
        try:
            if order_id in self._orders:
                order = self._orders[order_id]
                logger.debug(f"模拟查询订单状态: {order_id} -> {order.order_status.value}")
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
            logger.error(f"模拟查询订单状态失败: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"查询失败: {str(e)}",
                error_code="QUERY_FAILED"
            )

    def query_fund_info(self, account_id: str):
        """查询账户资金信息（整合真实AccountManager）"""
        try:
            from core.trading.account_models import FundInfo

            if self._account_manager:
                account = self._account_manager.get_account(account_id or 'default')
                if account:
                    fund_info = self._account_manager.get_fund_info(account_id or 'default')
                    if fund_info:
                        logger.info(f"MockTradingInterface: 使用真实AccountManager查询资金: {account_id}")
                        return fund_info
                    logger.info(f"MockTradingInterface: 使用真实AccountManager查询资金（从Account构建）: {account_id}")
                    return FundInfo(
                        account_id=account_id or 'default',
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

            logger.warning("MockTradingInterface: AccountManager不可用，使用默认资金值")
            return FundInfo(
                account_id=account_id,
                total_balance=1000000.0,
                available_balance=500000.0,
                frozen_balance=0.0,
                market_value=500000.0,
                total_assets=1000000.0,
                profit_loss=0.0,
                profit_loss_ratio=0.0,
                margin_used=0.0,
                margin_available=500000.0,
                maintenance_margin=0.0,
                update_time=datetime.now()
            )
        except Exception as e:
            logger.error(f"模拟查询资金信息失败: {e}")
            return None

    def query_positions(self, account_id: str):
        """查询账户持仓信息（整合真实AccountManager）"""
        try:
            if self._account_manager:
                positions = self._account_manager.get_account_positions(account_id or 'default')
                if positions:
                    logger.info(f"MockTradingInterface: 使用真实AccountManager查询持仓: {account_id}, 持仓数={len(positions)}")
                    return positions

            logger.warning("MockTradingInterface: AccountManager不可用或无持仓，返回空持仓列表（不再构造模拟持仓）")
            return []
        except Exception as e:
            logger.error(f"模拟查询持仓信息失败: {e}")
            return []


class OrderExecutor:
    """订单执行器"""

    # R238-D-001 修复: 类级默认 _disposed (R235-D 标杆模式, 防御 __new__ 绕过 __init__)
    _disposed = False

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        # R238-D-001 修复: _disposed 标志 (R78 铁律 #6 幂等短路)
        self._disposed = False
        self.service_container = service_container
        self.event_bus = event_bus

        self.repository: OrderRepository = None
        self.trading_interface: TradingInterface = None
        
        self._trading_interfaces: Dict[AssetType, TradingInterface] = {}
        self._account_interface_cache: Dict[str, TradingInterface] = {}

        # R255-P0 模式闸门: 默认 paper, 绝不默认 live (真实资金安全铁律)
        self._trading_mode = 'paper'

        # R258-P0: 风控开关 (默认开, 资金安全铁律)。
        # enable_risk_control 由 trading_service.set_mode 经 _sync_order_executor_trading_mode
        # (trading_service.py:357-374) 联动下发; 关闭时 _pre_trade_risk_check 快速放行。
        self._risk_control_enabled = True

        # R269-D2: 风控熔断暂停标志 (由 RiskEventSubscriber 在 stop_trading/紧急平仓
        # 事件时置位, 之后 _pre_trade_risk_check 拦截所有新订单)
        self._halted = False

        self._initialize()

        logger.info("订单执行器初始化完成")

    def _initialize(self):
        """初始化"""
        # R272-FIX: 改用模块级懒单例 (get_order_repository), 消除与
        # order_service/monitor/analyzer 的独立 OrderCache 割裂。
        # 此前直接 OrderRepository(...) 构造 → 独立缓存实例, executor 写穿
        # 自己的缓存, order_service 等走单例缓存读, 存在 300s TTL 陈旧读
        # (test_order_management_integration.test_06 实证: DB 已 CANCELLED,
        # 缓存滞留 SUBMITTED)。同 R255-P2 治理模式。
        self.repository = get_order_repository(self.service_container, self.event_bus)

        # 注册不同资产类型的交易接口
        self._register_trading_interfaces()

        # 默认交易接口：优先使用已注册的真实交易接口（XTP/CTP），不再默认实例化模拟接口
        if self._trading_interfaces:
            first_asset_type = next(iter(self._trading_interfaces))
            self.trading_interface = self._trading_interfaces[first_asset_type]
            logger.info(f"默认交易接口: {first_asset_type.value}（真实交易接口）")
        else:
            self.trading_interface = None
            logger.warning("未配置真实交易接口，下单功能不可用")

    def _register_trading_interfaces(self):
        """注册不同资产类型的交易接口"""
        # R255-P0 Mock 保护层: HIKYUU_TRADING_MOCK=1/true (测试/沙箱环境) 时
        # 追加注册 MockTradingInterface, 供测试与仿真走模拟成交, 不触真实接口
        self._mock_enabled = os.environ.get('HIKYUU_TRADING_MOCK', '').lower() in ('1', 'true')
        # 延迟导入真实交易接口（避免模块导入链加载 C 扩展 SDK；导入失败仅跳过对应接口）
        try:
            from core.trading.interfaces.xtp_pro_trading_interface import XTPProTradingInterface
        except ImportError:
            XTPProTradingInterface = None
            logger.warning("XTP Pro 交易接口不可用，跳过注册")
        try:
            from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface
        except ImportError:
            CTPTradingInterface = None
            logger.warning("CTP 交易接口不可用，跳过注册")

        # 注册股票交易接口（XTP Pro）
        if XTPProTradingInterface is not None:
            self._trading_interfaces[AssetType.STOCK_A] = XTPProTradingInterface()
            self._trading_interfaces[AssetType.STOCK_B] = XTPProTradingInterface()
            self._trading_interfaces[AssetType.STOCK_H] = XTPProTradingInterface()
            self._trading_interfaces[AssetType.STOCK_US] = XTPProTradingInterface()
            self._trading_interfaces[AssetType.STOCK_HK] = XTPProTradingInterface()

        # 注册期货交易接口（CTP）
        if CTPTradingInterface is not None:
            self._trading_interfaces[AssetType.FUTURES] = CTPTradingInterface()

        # 注册期权交易接口（CTP）
        if CTPTradingInterface is not None:
            self._trading_interfaces[AssetType.OPTION] = CTPTradingInterface()
        
        # 加密货币/外汇/债券/商品/指数/基金/权证等资产类型暂无可用的真实交易接口，
        # 不再无条件注册模拟接口（模拟接口会干扰真实场景），待接入真实接口后按需注册。
        # 已移除: CRYPTO/FOREX/BOND/COMMODITY/INDEX/FUND/WARRANT → MockTradingInterface()

        # R255-P0: Mock 保护层 (仅 HIKYUU_TRADING_MOCK=1/true 时追加注册, 不替换真实接口)
        if self._mock_enabled:
            try:
                self._trading_interfaces[AssetType.FUND] = MockTradingInterface(
                    self.service_container, self.event_bus)
                self._trading_interfaces[AssetType.CRYPTO] = MockTradingInterface(
                    self.service_container, self.event_bus)
                logger.info("Mock 保护层: 已注册 MockTradingInterface (HIKYUU_TRADING_MOCK)")
            except Exception as e:
                logger.warning(f"Mock 保护层注册失败: {e}")

        logger.info("交易接口注册完成")

        # 交易接口健康状态跟踪
        self._interface_health: Dict[AssetType, Dict[str, Any]] = {}
        self._interface_failover_map: Dict[AssetType, List[AssetType]] = {}  # 故障转移映射
        self._max_retry_count = 3  # 最大重试次数
        self._retry_delay_ms = 500  # 重试延迟（毫秒）

        # 初始化所有交易接口
        self._initialize_trading_interfaces()

    def _initialize_trading_interfaces(self):
        """初始化所有交易接口，记录健康状态"""
        # 先从账户管理器获取账户信息
        self._load_account_info_to_interfaces()
        
        # 然后初始化所有交易接口
        for asset_type, interface in self._trading_interfaces.items():
            health_info = {
                "connected": False, 
                "logged_in": False, 
                "last_error": None, 
                "retry_count": 0,
                "last_health_check": None,
                "consecutive_failures": 0,  # 连续失败次数
                "circuit_breaker": False,  # 熔断状态
                "total_requests": 0,
                "failed_requests": 0
            }
            try:
                if interface.connect():
                    logger.info(f"{asset_type.value} 交易接口连接成功")
                    health_info["connected"] = True
                    if interface.login():
                        logger.info(f"{asset_type.value} 交易接口登录成功")
                        health_info["logged_in"] = True
                    else:
                        logger.warning(f"{asset_type.value} 交易接口登录失败")
                        health_info["last_error"] = "登录失败"
                else:
                    logger.warning(f"{asset_type.value} 交易接口连接失败")
                    health_info["last_error"] = "连接失败"
            except Exception as e:
                logger.error(f"{asset_type.value} 交易接口初始化失败: {e}")
                health_info["last_error"] = str(e)
            
            self._interface_health[asset_type] = health_info
        
        # 设置故障转移映射（当主接口失败时，切换到备用接口）
        self._setup_failover_mapping()

    def _load_account_info_to_interfaces(self):
        """从账户管理器加载账户信息到交易接口"""
        try:
            # 延迟导入交易接口类（用于 isinstance 判断，避免模块导入链加载 C 扩展 SDK）
            from core.trading.interfaces.xtp_trading_interface import XTPTradingInterface
            from core.trading.interfaces.xtp_pro_trading_interface import XTPProTradingInterface
            from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface
            from core.trading.account_manager import AccountManager
            
            account_manager = self.service_container.resolve(AccountManager)
            accounts = account_manager.get_all_accounts()
            
            for account in accounts:
                # 获取账户对应的资产类型
                asset_type = self._get_asset_type_for_account(account)
                
                if asset_type and asset_type in self._trading_interfaces:
                    trading_interface = self._trading_interfaces[asset_type]
                    
                    # 根据交易接口类型初始化账户信息
                    if account.trading_interface_type == TradingInterfaceType.XTP_PRO:
                        if isinstance(trading_interface, XTPProTradingInterface):
                            trading_interface.account_id = account.xtp_account_id
                            trading_interface.password = account.xtp_password
                            trading_interface.server_address = account.xtp_server_address
                            trading_interface.trade_server = account.xtp_server_address
                            trading_interface.quote_server = account.xtp_server_address
                            logger.info(f"使用账户信息初始化XTP Pro接口: {account.account_id}, 机构: {account.institution_name}")
                    elif account.trading_interface_type == TradingInterfaceType.CTP:
                        if isinstance(trading_interface, CTPTradingInterface):
                            trading_interface.broker_id = account.ctp_broker_id
                            trading_interface.investor_id = account.ctp_investor_id
                            trading_interface.password = account.ctp_password
                            trading_interface.trade_front = account.ctp_trade_front
                            trading_interface.quote_front = account.ctp_quote_front
                            trading_interface.app_id = account.ctp_app_id
                            trading_interface.auth_code = account.ctp_auth_code
                            trading_interface.product_info = account.ctp_product_info
                            logger.info(f"使用账户信息初始化CTP接口: {account.account_id}, 机构: {account.institution_name}")
                    elif account.trading_interface_type == TradingInterfaceType.XTP:
                        if isinstance(trading_interface, XTPTradingInterface):
                            trading_interface.account_id = account.xtp_account_id
                            trading_interface.password = account.xtp_password
                            trading_interface.server_address = account.xtp_server_address
                            logger.info(f"使用账户信息初始化XTP接口: {account.account_id}, 机构: {account.institution_name}")
                    else:
                        logger.debug(f"账户 {account.account_id} 使用模拟交易接口或自定义接口")
            
        except Exception as e:
            logger.error(f"加载账户信息到交易接口失败: {e}")
    def _get_asset_type_for_account(self, account):
        """根据账户获取对应的资产类型"""
        # 这里可以根据账户的股票代码前缀或其他信息判断资产类型
        # 暂时默认返回STOCK_A
        from core.plugin_types import AssetType
        return AssetType.STOCK_A
    
    def _setup_failover_mapping(self):
        """设置故障转移映射"""
        # 股票接口失败时，尝试使用模拟接口
        self._interface_failover_map[AssetType.STOCK_A] = [AssetType.FUND]  # 备用接口
        self._interface_failover_map[AssetType.STOCK_HK] = [AssetType.STOCK_A]  # 港股失败尝试A股接口
        self._interface_failover_map[AssetType.STOCK_US] = [AssetType.STOCK_A]  # 美股失败尝试A股接口
    
    def check_interface_health(self, asset_type: AssetType) -> Dict[str, Any]:
        """
        检查交易接口健康状态
        
        Args:
            asset_type: 资产类型
            
        Returns:
            健康状态信息
        """
        if asset_type not in self._interface_health:
            return {"connected": False, "error": "接口未初始化"}
        
        health = self._interface_health[asset_type]
        interface = self._trading_interfaces.get(asset_type)
        
        if not interface:
            health["connected"] = False
            health["last_error"] = "接口对象不存在"
            return health
        
        # 如果处于熔断状态，尝试恢复
        if health.get("circuit_breaker") and health.get("consecutive_failures", 0) >= self._max_retry_count:
            logger.warning(f"{asset_type.value} 接口处于熔断状态，尝试恢复连接")
            self._try_reconnect_interface(asset_type)
        
        from datetime import datetime
        health["last_health_check"] = datetime.now().isoformat()
        return health
    
    def _try_reconnect_interface(self, asset_type: AssetType):
        """
        尝试重新连接交易接口
        
        Args:
            asset_type: 资产类型
        """
        health = self._interface_health[asset_type]
        interface = self._trading_interfaces.get(asset_type)
        
        if not interface:
            logger.error(f"无法重新连接：{asset_type.value} 接口对象不存在")
            return
        
        try:
            logger.info(f"尝试重新连接 {asset_type.value} 交易接口...")
            health["retry_count"] += 1
            
            # 尝试重新连接和登录
            if interface.connect():
                health["connected"] = True
                if interface.login():
                    health["logged_in"] = True
                    health["consecutive_failures"] = 0
                    health["circuit_breaker"] = False
                    logger.info(f"{asset_type.value} 接口重新连接成功")
                else:
                    logger.warning(f"{asset_type.value} 接口重新登录失败")
            else:
                logger.error(f"{asset_type.value} 接口重新连接失败")
                health["consecutive_failures"] += 1
                
                # 如果连续失败次数过多，触发熔断
                if health["consecutive_failures"] >= self._max_retry_count:
                    health["circuit_breaker"] = True
                    logger.error(f"{asset_type.value} 接口连续失败 {self._max_retry_count} 次，触发熔断")
                    self.event_bus.publish('trading_interface_circuit_breaker',
                        asset_type=asset_type.value,
                        consecutive_failures=health["consecutive_failures"]
                    )
                    
        except Exception as e:
            logger.error(f"重新连接 {asset_type.value} 接口异常: {e}")
            health["last_error"] = str(e)
            health["consecutive_failures"] += 1
    def _get_trading_interface(self, asset_type: AssetType) -> TradingInterface:
        """根据资产类型获取对应的交易接口（带健康检查和故障转移）"""
        # 先检查健康状态
        health = self.check_interface_health(asset_type)
        
        # 如果主接口不可用，尝试故障转移
        if not health.get("connected") or not health.get("logged_in"):
            if health.get("circuit_breaker"):
                logger.warning(f"{asset_type.value} 接口处于熔断状态，尝试故障转移")
            
            # 尝试使用备用接口
            failover_list = self._interface_failover_map.get(asset_type, [])
            for backup_asset_type in failover_list:
                backup_health = self.check_interface_health(backup_asset_type)
                if backup_health.get("connected") and backup_health.get("logged_in"):
                    logger.info(f"使用备用接口: {backup_asset_type.value} 替代 {asset_type.value}")
                    return self._trading_interfaces.get(backup_asset_type)
            
            logger.error(f"所有接口都不可用: {asset_type.value}")
            return None
        
        return self._trading_interfaces.get(asset_type)

    def get_trading_interface(self, asset_type: AssetType) -> Optional[TradingInterface]:
        """公开: 根据资产类型获取交易接口 (薄封装, 消除跨类私有属性访问)

        R254-P1: account_manager 等外部组件经 OrderService 委托本方法获取接口,
        不再直接访问 _trading_interfaces 私有属性; 接口字段初始化已由
        _load_account_info_to_interfaces (order_executor.py:440-489) 内部负责,
        调用方无需再改写接口字段。健康检查仅记录状态 (容错, 不阻断返回)。

        Args:
            asset_type: 资产类型

        Returns:
            TradingInterface: 交易接口实例, 未注册该资产类型时返回 None
        """
        try:
            self.check_interface_health(asset_type)
        except Exception as e:
            logger.debug(f"交易接口健康检查异常(不影响获取): {asset_type}, 错误: {e}")
        return self._trading_interfaces.get(asset_type)

    def _validate_order_integrity(self, order: Order) -> Optional[str]:
        """
        验证订单对象的完整性
        Args:
            order: 订单对象
        Returns:
            Optional[str]: 如果验证失败返回错误信息，否则返回 None
        """
        try:
            # 验证必要字段
            required_fields = {
                'order_id': order.order_id,
                'strategy_id': order.strategy_id,
                'asset_type': order.asset_type,
                'stock_code': order.stock_code,
                'order_type': order.order_type,
                'order_category': order.order_category,
                'order_price': order.order_price,
                'order_quantity': order.order_quantity,
                'order_status': order.order_status,
                'create_time': order.create_time,
                'update_time': order.update_time,
                'account_id': order.account_id
            }
            for field_name, field_value in required_fields.items():
                if field_value is None:
                    return f"必要字段 {field_name} 为 None"
            # 验证数据类型和值
            if not isinstance(order.order_price, (int, float)) or order.order_price <= 0:
                return f"订单价格无效: {order.order_price}"
            if not isinstance(order.order_quantity, int) or order.order_quantity <= 0:
                return f"订单数量无效: {order.order_quantity}"
            if not isinstance(order.stock_code, str) or len(order.stock_code) == 0:
                return f"股票代码无效: {order.stock_code}"
            # 验证账号ID
            if order.account_id == "default":
                logger.warning(f"订单 {order.order_id} 的 account_id 为 'default'，可能导致账号解析失败")
            # 验证策略ID
            if order.strategy_id == "default":
                logger.warning(f"订单 {order.order_id} 的 strategy_id 为 'default'，可能导致账号解析失败")
            logger.debug(f"订单完整性验证通过: {order.order_id}")
            return None
        except Exception as e:
            logger.error(f"验证订单完整性时发生异常: {e}")
            import traceback
            logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return f"验证异常: {str(e)}"
    def _resolve_account_for_order(self, order: Order) -> Optional[Account]:
        """
        解析订单使用的账号（三级优先级）
        Args:
            order: 订单对象
        Returns:
            Account: 账号对象，如果无法解析则返回 None
        """
        try:
            from core.trading.account_manager import AccountManager
            from core.trading.strategy_manager import StrategyManager
            account_manager = self.service_container.resolve(AccountManager)
            strategy_manager = self.service_container.resolve(StrategyManager)
            logger.debug(f"开始解析订单账号: order_id={order.order_id}, account_id={order.account_id}, strategy_id={order.strategy_id}")
            # 优先级1：订单级别
            if order.account_id and order.account_id != "default":
                account = account_manager.get_account(order.account_id)
                if account:
                    logger.info(f"使用订单指定的账号: {account.account_id}")
                    return account
                else:
                    logger.warning(f"订单指定的账号不存在: {order.account_id}")
                    logger.warning(f"订单详细信息: order_id={order.order_id}, stock_code={order.stock_code}")
            # 优先级2：策略级别
            if order.strategy_id and order.strategy_id != "default":
                strategy = strategy_manager.get_strategy(order.strategy_id)
                if strategy and strategy.default_account_id:
                    account = account_manager.get_account(strategy.default_account_id)
                    if account:
                        logger.info(f"使用策略的默认账号: {account.account_id} (策略: {strategy.strategy_id})")
                        return account
                    else:
                        logger.warning(f"策略的默认账号不存在: {strategy.default_account_id} (策略: {strategy.strategy_id})")
                else:
                    logger.warning(f"策略不存在或没有默认账号: {order.strategy_id}")
            # 优先级3：系统级别
            accounts = account_manager.get_all_accounts()
            if accounts:
                # 返回第一个账号作为系统默认账号
                account = accounts[0]
                logger.info(f"使用系统默认账号: {account.account_id} (共 {len(accounts)} 个账号)")
                return account
            logger.error("无法解析订单使用的账号")
            logger.error(f"订单详细信息:")
            logger.error(f"  order_id: {order.order_id}")
            logger.error(f"  stock_code: {order.stock_code}")
            logger.error(f"  order_type: {order.order_type.value}")
            logger.error(f"  order_quantity: {order.order_quantity}")
            logger.error(f"  order_price: {order.order_price}")
            logger.error(f"  account_id: {order.account_id}")
            logger.error(f"  strategy_id: {order.strategy_id}")
            logger.error(f"  asset_type: {order.asset_type.value}")
            logger.error(f"系统状态:")
            logger.error(f"  可用账号数: {len(accounts) if accounts else 0}")
            logger.error(f"  可能原因:")
            logger.error(f"    1. 系统中没有配置任何账号")
            logger.error(f"    2. 订单的 account_id 和 strategy_id 都是 'default'")
            logger.error(f"    3. 订单指定的账号不存在")
            logger.error(f"    4. 策略指定的默认账号不存在")
            return None
        except Exception as e:
            logger.error(f"解析订单账号失败: {e}")
            logger.error(f"订单ID: {order.order_id}")
            import traceback
            logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return None

    def halt_trading(self, reason: str = "") -> None:
        """R269-D2: 风控熔断 —— 暂停所有新订单受理。

        由 RiskEventSubscriber 在 stop_trading / 紧急平仓事件时调用;
        置位后 _pre_trade_risk_check 以 RISK_HALTED 拒绝一切新订单。
        """
        self._halted = True
        logger.critical(f"风控熔断已触发, 暂停所有新订单: {reason}")

    def resume_trading(self) -> None:
        """R269-D2: 解除风控熔断, 恢复新订单受理。"""
        if self._halted:
            self._halted = False
            logger.info("风控熔断已解除, 恢复订单受理")

    def is_halted(self) -> bool:
        """R269-D2: 查询是否处于风控熔断状态。"""
        return getattr(self, '_halted', False)

    def _pre_trade_risk_check(self, order: Order) -> Dict[str, Any]:
        """
        交易前风控预检查（P0-2修复）
        
        在订单提交前进行风控检查，确保符合风控规则
        
        Args:
            order: 订单对象
            
        Returns:
            Dict[str, Any]: 包含 'passed' 和 'reason' 的检查结果
        """
        try:
            # R269-D2: 风控熔断拦截 —— 熔断为资金安全最高优先级, 即使风控开关被
            # 关闭也不放行 (RiskEventSubscriber 在 stop_trading/紧急平仓事件时置位)
            if getattr(self, '_halted', False):
                return {'passed': False, 'reason': '风控熔断中, 已暂停新订单受理', 'warnings': [], 'error_code': 'RISK_HALTED'}

            # R258-P0: 风控开关 (trading_service.set_mode 经 set_trading_mode 联动下发)。
            # 关闭时快速放行, 不执行任何风控检查 (backtest 显式关闭用, 默认开启)
            if not getattr(self, '_risk_control_enabled', True):
                return {'passed': True, 'reason': '风控已禁用 (enable_risk_control=False)', 'warnings': []}

            result = {'passed': True, 'reason': '', 'warnings': []}
            
            try:
                from core.risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor
                # R252-F1: 使用 try_resolve 而非 resolve —— EnhancedRiskMonitor 未注册时
                # resolve 会抛 ValueError 导致所有订单被风控误拒, try_resolve 失败返回 None 跳过增强风控
                risk_monitor = self.service_container.try_resolve(EnhancedRiskMonitor)
                
                if risk_monitor and hasattr(risk_monitor, 'check_order_risk'):
                    # R268-F1: 同步账户实时持仓 → 集中度检查数据源。
                    # 不打通则 _current_positions 恒空 → 集中度限制永不执行。
                    self._sync_positions_to_risk_monitor(risk_monitor, order.account_id)
                    risk_result = risk_monitor.check_order_risk(order)
                    if not risk_result.get('passed', True):
                        result['passed'] = False
                        result['reason'] = risk_result.get('reason', '风控检查未通过')
                        logger.warning(f"风控检查拒绝订单: {order.order_id}, 原因: {result['reason']}")
                        return result
                        
            except ImportError:
                logger.debug("EnhancedRiskMonitor不可用，跳过高级风控检查")
            except Exception as e:
                # R252-F1: 风控服务异常不应阻断交易主链路, 降级为 warning 后继续基础检查
                logger.warning(f"高级风控检查异常，降级跳过（不阻断交易）: {order.order_id}, 错误: {e}")
            
            try:
                from core.trading.account_manager import AccountManager
                account_manager = self.service_container.resolve(AccountManager)
                
                if order.account_id and order.account_id != "default":
                    account = account_manager.get_account(order.account_id)
                    if account:
                        order_value = order.order_price * order.order_quantity
                        
                        # R268-F4: 修复资金检查 fail-open —— 原 `and account.available_cash` 使
                        # 可用资金为 0/None 时跳过校验 (0 资金也可下单)。0 → 拒绝, None → 告警。
                        # R273-F1: 原 hasattr(account, 'available_cash') 恒 False (真实 Account
                        # dataclass 仅有 available_balance, account_models.py:72) → 校验整体跳过。
                        # 现双字段兼容: 属性存在 → 直接用 (None = 资金未知 → 告警);
                        # 属性不存在 → 回退 available_balance (真实 Account 路径)。
                        if hasattr(account, 'available_cash'):
                            available_funds = account.available_cash
                        else:
                            available_funds = getattr(account, 'available_balance', None)
                        if available_funds is None:
                            result['warnings'].append("账户可用资金未知，无法校验资金充足性")
                        elif order_value > available_funds:
                            result['passed'] = False
                            result['reason'] = f"资金不足: 需要{order_value:.2f}, 可用{available_funds:.2f}"
                            return result
                        
                        if hasattr(account, 'position_limit') and account.position_limit:
                            # R268-F4: get_positions_by_account 在 AccountManager 中不存在
                            # (account_manager.py:604 实际方法为 get_account_positions) →
                            # AttributeError 被下方 :821 捕获 → 误拒所有设置了 position_limit 的账户。
                            positions = account_manager.get_account_positions(account.account_id)
                            if len(positions) >= account.position_limit:
                                result['warnings'].append(f"持仓数量接近限制: {len(positions)}/{account.position_limit}")
                                
            except Exception as e:
                logger.critical(f"账户风控检查异常，订单被拒绝: {order.order_id}, 错误: {e}")
                return {'passed': False, 'reason': f'账户风控检查异常，订单被拒绝: {str(e)}', 'warnings': [], 'error_code': 'RISK_CHECK_FAILED'}
            
            if order.order_quantity <= 0:
                result['passed'] = False
                result['reason'] = f"订单数量无效: {order.order_quantity}"
                return result
            
            if order.order_price <= 0:
                result['passed'] = False
                result['reason'] = f"订单价格无效: {order.order_price}"
                return result
            # 集成核心风控模块 - 止损/止盈检查 (P0-4修复 + R269-D3 止损空转 + R270 止盈融入)
            try:
                from core.risk_control import RiskControlStrategy
                risk_ctrl = RiskControlStrategy()
                entry_price = self._get_avg_entry_price(order.account_id, order.stock_code)
                if entry_price is not None and entry_price > 0:
                    position = self._get_position(order.account_id, order.stock_code)
                    # R269-D3: 修复止损检查空转 —— 原 stop_loss_levels 唯一填充点
                    # calculate_stop_loss (risk_control.py:135) 全库零调用 → 恒空 →
                    # check_stop_loss_trigger (risk_control.py:163-165) 恒放行。
                    # 此处先填充动态止损价 (PositionRiskMonitor 自适应优先, 降级保守值)。
                    if position != 0:
                        self._fill_stop_loss_level(risk_ctrl, order, entry_price, position)
                    triggered, reason = risk_ctrl.check_stop_loss_trigger(
                        asset=order.stock_code,
                        position=position,
                        entry_price=entry_price,
                        current_price=order.order_price,
                        current_time=order.create_time
                    )
                    if triggered:
                        result['passed'] = False
                        result['reason'] = f"风控止损触发: {reason}"
                        return result
                    # R270: 止盈检查 (对称于止损, 激活 AdaptiveTakeProfit 生产消费)
                    if position != 0:
                        self._fill_take_profit_level(risk_ctrl, order, entry_price, position)
                    tp_triggered, tp_reason = risk_ctrl.check_take_profit_trigger(
                        asset=order.stock_code,
                        position=position,
                        entry_price=entry_price,
                        current_price=order.order_price,
                        current_time=order.create_time
                    )
                    if tp_triggered:
                        result['passed'] = False
                        result['reason'] = f"风控止盈触发: {tp_reason}"
                        return result
            except ImportError:
                logger.debug("RiskControlStrategy不可用，跳过止损/止盈风控检查")
            except Exception as e:
                logger.warning(f"风控止损/止盈检查异常(不影响交易): {e}")
            max_order_value = 10000000
            order_value = order.order_price * order.order_quantity
            if order_value > max_order_value:
                result['warnings'].append(f"单笔订单金额较大: {order_value:.2f}")
            
            if result['warnings']:
                logger.info(f"订单风控检查通过但有警告: {order.order_id}, 警告: {result['warnings']}")
            else:
                logger.debug(f"订单风控检查通过: {order.order_id}")
            
            return result
            
        except Exception as e:
            logger.critical(f"交易前风控检查异常，订单被拒绝: {order.order_id}, 错误: {e}")
            return {'passed': False, 'reason': f'风控检查异常，订单被拒绝: {str(e)}', 'warnings': [], 'error_code': 'RISK_CHECK_FAILED'}
    def _fill_stop_loss_level(self, risk_ctrl, order, entry_price: float, position: float) -> None:
        """R269-D3: 为 check_stop_loss_trigger 填充动态止损价 (修复止损空转)。

        优先使用 PositionRiskMonitor (AdaptiveStopLoss 五路融合, 需 K 线行情,
        数据不可用时降级固定比例); 组件不可用时降级 RiskControlStrategy 保守计算。
        仅填充不阻断 —— 填充失败由 check_stop_loss_trigger 固定比例兜底。
        """
        try:
            stop_price = None
            try:
                from core.trading.position_risk_monitor import PositionRiskMonitor
                monitor = None
                try:
                    if self.service_container is not None:
                        monitor = self.service_container.try_resolve(PositionRiskMonitor)
                except Exception:
                    monitor = None
                if monitor is None:
                    monitor = PositionRiskMonitor(self.service_container)
                stop_price = monitor.get_dynamic_stop_price(
                    stock_code=order.stock_code,
                    current_price=entry_price,
                    position=position,
                )
            except Exception as e:
                logger.debug(f"自适应止损不可用, 降级 RiskControlStrategy: {e}")
            if stop_price is None or stop_price <= 0:
                # 降级: 保守默认波动率 (calculate_stop_loss risk_metrics 有缺省兜底)
                stop_price = risk_ctrl.calculate_stop_loss(
                    asset=order.stock_code,
                    price=entry_price,
                    position=position,
                    risk_metrics={'market_risk': {'volatility': 0.2, 'beta': 1.0}},
                )
            if stop_price and stop_price > 0:
                risk_ctrl.stop_loss_levels[order.stock_code] = float(stop_price)
        except Exception as e:
            logger.warning(f"填充止损水平失败(将由 check_stop_loss_trigger 兜底): {e}")

    def _fill_take_profit_level(self, risk_ctrl, order, entry_price: float, position: float) -> None:
        """R270: 为 check_take_profit_trigger 填充动态止盈价 (激活 AdaptiveTakeProfit 能力)。

        优先使用 PositionRiskMonitor.get_dynamic_take_profit (需 K 线行情,
        数据不可用时降级固定比例); 组件不可用时降级 RiskControlStrategy 保守计算。
        仅填充不阻断 —— 填充失败由 check_take_profit_trigger 固定比例兜底。
        """
        try:
            tp_price = None
            try:
                from core.trading.position_risk_monitor import PositionRiskMonitor
                monitor = None
                try:
                    if self.service_container is not None:
                        monitor = self.service_container.try_resolve(PositionRiskMonitor)
                except Exception:
                    monitor = None
                if monitor is None:
                    monitor = PositionRiskMonitor(self.service_container)
                tp_price = monitor.get_dynamic_take_profit(
                    stock_code=order.stock_code,
                    current_price=entry_price,
                    position=position,
                )
            except Exception as e:
                logger.debug(f"自适应止盈不可用, 降级 RiskControlStrategy: {e}")
            if tp_price is None or tp_price <= 0:
                # 降级: 保守默认波动率 (calculate_take_profit risk_metrics 有缺省兜底)
                tp_price = risk_ctrl.calculate_take_profit(
                    asset=order.stock_code,
                    price=entry_price,
                    position=position,
                    risk_metrics={'market_risk': {'volatility': 0.2, 'beta': 1.0}},
                )
            if tp_price and tp_price > 0:
                risk_ctrl.take_profit_levels[order.stock_code] = float(tp_price)
        except Exception as e:
            logger.warning(f"填充止盈水平失败(将由 check_take_profit_trigger 兜底): {e}")

    def _sync_positions_to_risk_monitor(self, risk_monitor, account_id: str) -> None:
        """R268-F1: 同步账户实时持仓到增强风控监控器 (集中度检查数据源).

        从 AccountManager 活数据流取持仓并转换为 check_order_risk 期望的 dict 结构。
        """
        try:
            if not account_id or not hasattr(risk_monitor, 'update_portfolio_positions'):
                return
            from core.trading.account_manager import AccountManager
            account_manager = self.service_container.try_resolve(AccountManager)
            if not account_manager:
                return
            positions = account_manager.get_account_positions(account_id) or []
            risk_monitor.update_portfolio_positions([
                {
                    'stock_code': p.stock_code,
                    'quantity': p.quantity,
                    'price': p.current_price or p.open_price,
                }
                for p in positions
            ])
        except Exception as e:
            logger.debug(f"同步持仓到风控监控器失败(降级跳过): {e}")

    def _get_trading_interface_for_account(self, account: Account) -> Optional[TradingInterface]:
        """
        根据账号获取交易接口（带缓存）
        Args:
            account: 账号对象
        Returns:
            TradingInterface: 交易接口，如果无法获取则返回 None
        """
        try:
            # 检查缓存
            if account.account_id in self._account_interface_cache:
                return self._account_interface_cache[account.account_id]
            # 创建交易接口
            trading_interface = self._create_trading_interface_for_account(account)
            if trading_interface:
                # 缓存交易接口
                self._account_interface_cache[account.account_id] = trading_interface
                logger.info(f"为账号 {account.account_id} 创建并缓存交易接口")
            return trading_interface
        except Exception as e:
            logger.error(f"获取账号 {account.account_id} 的交易接口失败: {e}")
            return None
    def _create_trading_interface_for_account(self, account: Account) -> Optional[TradingInterface]:
        """
        为账号创建交易接口
        Args:
            account: 账号对象
        Returns:
            TradingInterface: 交易接口，如果无法创建则返回 None
        """
        try:
            # 延迟导入交易接口类（避免模块导入链加载 C 扩展 SDK；导入失败由外层 except 兜底返回 None）
            from core.trading.interfaces.xtp_trading_interface import XTPTradingInterface
            from core.trading.interfaces.xtp_pro_trading_interface import XTPProTradingInterface
            from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface

            trading_interface_type = account.trading_interface_type

            if trading_interface_type == TradingInterfaceType.MOCK:
                logger.warning(f"账号 {account.account_id} 配置为模拟交易接口(MOCK)，已弃用模拟接口，下单功能不可用")
                return None

            elif trading_interface_type == TradingInterfaceType.XTP:
                interface = XTPTradingInterface()
                interface.account_id = account.xtp_account_id
                interface.password = account.xtp_password
                interface.server_address = account.xtp_server_address

            elif trading_interface_type == TradingInterfaceType.XTP_PRO:
                interface = XTPProTradingInterface()
                interface.account_id = account.xtp_account_id
                interface.password = account.xtp_password
                interface.server_address = account.xtp_server_address

            elif trading_interface_type == TradingInterfaceType.CTP:
                interface = CTPTradingInterface()
                interface.broker_id = account.ctp_broker_id
                interface.investor_id = account.ctp_investor_id
                interface.password = account.ctp_password
                interface.trade_front = account.ctp_trade_front
                interface.quote_front = account.ctp_quote_front
                interface.app_id = account.ctp_app_id
                interface.auth_code = account.ctp_auth_code
                interface.product_info = account.ctp_product_info

            elif trading_interface_type == TradingInterfaceType.MINIQMT:
                from core.trading.interfaces.miniqmt_trading_interface import MiniQMTConfig, MiniQMTTradingInterface
                config = MiniQMTConfig()
                config.account_id = account.miniqmt_account_id if hasattr(account, 'miniqmt_account_id') else account.account_id
                config.password = account.miniqmt_password if hasattr(account, 'miniqmt_password') else ""
                config.ip = account.miniqmt_ip if hasattr(account, 'miniqmt_ip') else "127.0.0.1"
                config.port = account.miniqmt_port if hasattr(account, 'miniqmt_port') else 58610
                interface = MiniQMTTradingInterface(config)

            else:
                logger.warning(f"未知的交易接口类型: {trading_interface_type.value}，无法创建交易接口")
                return None

            # 初始化交易接口
            try:
                if interface.connect():
                    logger.info(f"账号 {account.account_id} 的交易接口连接成功")
                    if interface.login():
                        logger.info(f"账号 {account.account_id} 的交易接口登录成功")
                    else:
                        logger.warning(f"账号 {account.account_id} 的交易接口登录失败")
                else:
                    logger.warning(f"账号 {account.account_id} 的交易接口连接失败")
            except Exception as e:
                logger.error(f"账号 {account.account_id} 的交易接口初始化失败: {e}")

            return interface

        except Exception as e:
            logger.error(f"为账号 {account.account_id} 创建交易接口失败: {e}")
            return None

    def submit_order(self, order: Order) -> ExecutionResult:
        """提交订单"""
        try:
            logger.info(f"开始提交订单: {order.order_id} ({order.asset_type.value})")

            # 0. 验证订单对象的完整性
            validation_error = self._validate_order_integrity(order)
            if validation_error:
                logger.error(f"订单完整性验证失败: {order.order_id} - {validation_error}")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"订单完整性验证失败: {validation_error}",
                    error_code="ORDER_VALIDATION_FAILED"
                )

            # 0.5 交易前风控预检查（P0-2修复）
            risk_check_result = self._pre_trade_risk_check(order)
            if not risk_check_result['passed']:
                logger.warning(f"交易前风控检查未通过: {order.order_id} - {risk_check_result['reason']}")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"风控检查未通过: {risk_check_result['reason']}",
                    # R270: 保留具体风控错误码 (RISK_HALTED/DAILY_LOSS_LIMIT_EXCEEDED 等),
                    # 原硬编码 RISK_CHECK_FAILED 会丢失熔断原因
                    error_code=risk_check_result.get('error_code', 'RISK_CHECK_FAILED')
                )

            # 1. 解析订单使用的账号
            account = self._resolve_account_for_order(order)
            if not account:
                logger.error(f"无法解析订单使用的账号: {order.order_id}")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="无法解析订单使用的账号",
                    error_code="ACCOUNT_NOT_FOUND"
                )

            # 2. 更新订单状态为已提交
            order.order_status = OrderStatus.SUBMITTED
            order.update_time = datetime.now()
            self.repository.update_order(order)

            # 3. 根据账号获取对应的交易接口（带健康检查和故障转移）
            trading_interface = self._get_trading_interface_for_account(account)
            if not trading_interface:
                logger.error(f"无法获取账号 {account.account_id} 的交易接口")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"无法获取账号 {account.account_id} 的交易接口",
                    error_code="INTERFACE_NOT_FOUND"
                )

            # 3.4 模式闸门 (R255-P0 真实资金安全): 真实 CTP/XTP 接口在非 live
            # 模式一律拦截 (MODE_BLOCKED), 绝不误触发真实报单; Mock 接口放行
            if self._trading_mode != 'live' and self._is_real_trading_interface(trading_interface):
                logger.error(
                    f"订单 {order.order_id} 被模式闸门拦截: 当前模式={self._trading_mode}, "
                    f"接口={type(trading_interface).__name__} (非实盘模式禁止真实接口下单)"
                )
                order.order_status = OrderStatus.REJECTED
                order.error_message = "非实盘模式禁止真实接口下单"
                order.update_time = datetime.now()
                self.repository.update_order(order)
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="非实盘模式禁止真实接口下单（需显式切换实盘模式）",
                    error_code="MODE_BLOCKED"
                )

            # 3.5 更新健康状态统计
            health = self._interface_health.get(order.asset_type)
            if health:
                health["total_requests"] = health.get("total_requests", 0) + 1

            # 4. 提交到交易接口
            result = trading_interface.submit_order(order)

            # 5. 处理执行结果并更新健康状态
            if result.status == ExecutionStatus.SUCCESS:
                order.execute_time = datetime.now()
                order.update_time = datetime.now()
                order.metadata['exchange_order_id'] = result.exchange_order_id
                order.metadata['account_id'] = account.account_id

                self.repository.update_order(order)
                
                # 成功时重置连续失败计数
                if health:
                    health["consecutive_failures"] = 0

                logger.info(f"订单提交成功: {order.order_id} ({order.asset_type.value}) -> {result.exchange_order_id}, 账号: {account.account_id}")

                self.event_bus.publish('order.executed',
                    order_id=order.order_id,
                    stock_code=order.stock_code,
                    order_price=order.order_price,
                    order_quantity=order.order_quantity,
                    filled_price=result.details.get('filled_price', order.order_price) if result.details else order.order_price,
                    asset_type=order.asset_type.value,
                    account_id=account.account_id,
                    exchange_order_id=result.exchange_order_id,
                    timestamp=datetime.now()
                )

                self.event_bus.publish('order_submitted_success',
                    order_id=order.order_id,
                    exchange_order_id=result.exchange_order_id,
                    asset_type=order.asset_type.value,
                    account_id=account.account_id
                )

                return result
            else:
                # 失败时更新健康状态
                if health:
                    health["failed_requests"] = health.get("failed_requests", 0) + 1
                    health["consecutive_failures"] = health.get("consecutive_failures", 0) + 1
                    health["last_error"] = result.message
                    
                    # 检查是否触发熔断
                    if health["consecutive_failures"] >= self._max_retry_count:
                        health["circuit_breaker"] = True
                        logger.error(f"{order.asset_type.value} 接口连续失败 {health['consecutive_failures']} 次，触发熔断")
                        self.event_bus.publish('trading_interface_circuit_breaker',
                            asset_type=order.asset_type.value,
                            consecutive_failures=health["consecutive_failures"]
                        )

                order.order_status = OrderStatus.REJECTED
                order.error_message = result.message
                order.update_time = datetime.now()

                self.repository.update_order(order)

                logger.error(f"订单提交失败: {order.order_id} ({order.asset_type.value}) - {result.message}, 账号: {account.account_id}")

                self.event_bus.publish('order_submitted_failed',
                    order_id=order.order_id,
                    error=result.message,
                    asset_type=order.asset_type.value,
                    account_id=account.account_id
                )

                return result

        except Exception as e:
            logger.error(f"提交订单异常: {e}")
            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.FAILED,
                message=f"提交订单异常: {str(e)}",
                error_code="EXECUTION_ERROR"
            )

    def submit_orders_batch(self, orders: List[Order]) -> List[ExecutionResult]:
        """
        批量提交订单

        Args:
            orders: 订单列表

        Returns:
            List[ExecutionResult]: 执行结果列表
        """
        try:
            logger.info(f"开始批量提交订单: {len(orders)} 个订单")

            if not orders:
                return []

            results = []
            success_count = 0
            failed_count = 0

            # 按资产类型分组
            orders_by_asset_type: Dict[AssetType, List[Order]] = {}
            for order in orders:
                if order.asset_type not in orders_by_asset_type:
                    orders_by_asset_type[order.asset_type] = []
                orders_by_asset_type[order.asset_type].append(order)

            # 批量更新订单状态为已提交
            for order in orders:
                order.order_status = OrderStatus.SUBMITTED
                order.update_time = datetime.now()

            # 按资产类型批量提交
            for asset_type, asset_orders in orders_by_asset_type.items():

                for order in asset_orders:
                    try:
                        validation_error = self._validate_order_integrity(order)
                        if validation_error:
                            order.order_status = OrderStatus.REJECTED
                            order.error_message = f"订单完整性验证失败: {validation_error}"
                            order.update_time = datetime.now()
                            results.append(ExecutionResult(
                                order_id=order.order_id,
                                status=ExecutionStatus.FAILED,
                                message=f"订单完整性验证失败: {validation_error}",
                                error_code="ORDER_VALIDATION_FAILED"
                            ))
                            failed_count += 1
                            continue

                        risk_check_result = self._pre_trade_risk_check(order)
                        if not risk_check_result['passed']:
                            logger.warning(f"批量订单风控检查未通过: {order.order_id} - {risk_check_result['reason']}")
                            order.order_status = OrderStatus.REJECTED
                            order.error_message = f"风控检查未通过: {risk_check_result['reason']}"
                            order.update_time = datetime.now()
                            results.append(ExecutionResult(
                                order_id=order.order_id,
                                status=ExecutionStatus.FAILED,
                                message=f"风控检查未通过: {risk_check_result['reason']}",
                                # R270: 保留具体风控错误码 (同 submit_order)
                                error_code=risk_check_result.get('error_code', 'RISK_CHECK_FAILED')
                            ))
                            failed_count += 1
                            continue

                        account = self._resolve_account_for_order(order)
                        if not account:
                            logger.error(f"批量订单无法解析账号: {order.order_id}")
                            order.order_status = OrderStatus.REJECTED
                            order.error_message = "无法解析订单使用的账号"
                            order.update_time = datetime.now()
                            results.append(ExecutionResult(
                                order_id=order.order_id,
                                status=ExecutionStatus.FAILED,
                                message="无法解析订单使用的账号",
                                error_code="ACCOUNT_NOT_FOUND"
                            ))
                            failed_count += 1
                            continue

                        trading_interface = self._get_trading_interface_for_account(account)

                        # R255-P0 模式闸门 (批量路径同单笔): 真实接口非 live 模式拦截
                        if self._trading_mode != 'live' and self._is_real_trading_interface(trading_interface):
                            order.order_status = OrderStatus.REJECTED
                            order.error_message = "非实盘模式禁止真实接口下单"
                            order.update_time = datetime.now()
                            results.append(ExecutionResult(
                                order_id=order.order_id,
                                status=ExecutionStatus.FAILED,
                                message="非实盘模式禁止真实接口下单（需显式切换实盘模式）",
                                error_code="MODE_BLOCKED"
                            ))
                            failed_count += 1
                            continue

                        result = trading_interface.submit_order(order)

                        # 处理执行结果
                        if result.status == ExecutionStatus.SUCCESS:
                            order.execute_time = datetime.now()
                            order.update_time = datetime.now()
                            order.metadata['exchange_order_id'] = result.exchange_order_id

                            self.event_bus.publish('order.executed',
                                order_id=order.order_id,
                                stock_code=order.stock_code,
                                order_price=order.order_price,
                                order_quantity=order.order_quantity,
                                filled_price=order.order_price,
                                asset_type=order.asset_type.value,
                                account_id=account.account_id,
                                exchange_order_id=result.exchange_order_id,
                                timestamp=order.execute_time.isoformat()
                            )
                            self.event_bus.publish('order_submitted_success',
                                order_id=order.order_id,
                                exchange_order_id=result.exchange_order_id,
                                asset_type=order.asset_type.value,
                                account_id=account.account_id
                            )

                            success_count += 1
                        else:
                            order.order_status = OrderStatus.REJECTED
                            order.error_message = result.message
                            order.update_time = datetime.now()

                            failed_count += 1

                        results.append(result)

                    except Exception as e:
                        logger.error(f"批量提交订单异常: {order.order_id} - {e}")
                        order.order_status = OrderStatus.REJECTED
                        order.error_message = str(e)
                        order.update_time = datetime.now()

                        results.append(ExecutionResult(
                            order_id=order.order_id,
                            status=ExecutionStatus.FAILED,
                            message=f"订单提交异常: {str(e)}",
                            error_code="EXECUTION_ERROR"
                        ))

                        failed_count += 1

            # 批量更新订单到数据库
            self.repository.update_orders_batch(orders)

            # 批量发布事件
            success_orders = [r for r in results if r.status == ExecutionStatus.SUCCESS]
            failed_orders = [r for r in results if r.status != ExecutionStatus.SUCCESS]

            if success_orders:
                self.event_bus.publish('batch_orders_submitted_success',
                    count=len(success_orders),
                    order_ids=[r.order_id for r in success_orders]
                )

            if failed_orders:
                self.event_bus.publish('batch_orders_submitted_failed',
                    count=len(failed_orders),
                    order_ids=[r.order_id for r in failed_orders]
                )

            logger.info(f"批量订单提交完成: 成功 {success_count}, 失败 {failed_count}")

            return results

        except Exception as e:
            logger.error(f"批量提交订单异常: {e}")
            return [ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.FAILED,
                message=f"批量提交异常: {str(e)}",
                error_code="BATCH_EXECUTION_ERROR"
            ) for order in orders]

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """取消订单"""
        try:
            logger.info(f"开始取消订单: {order_id}")

            # 1. 获取订单（遍历所有数据池）
            order = self.repository.get_order(order_id, asset_type=None, use_cache=False)
            if not order:
                logger.error(f"订单取消失败: {order_id} - 订单不存在，可能原因：")
                logger.error(f"  1. 订单创建时保存失败但ID已生成")
                logger.error(f"  2. 订单被保存到了错误的数据池")
                logger.error(f"  3. 订单已被删除")
                logger.error(f"  4. 数据库事务问题导致订单未持久化")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="订单不存在",
                    error_code="ORDER_NOT_FOUND"
                )

            # 2. 检查订单状态
            if order.is_completed:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"订单已完成，不能取消",
                    error_code="ORDER_COMPLETED"
                )

            # 3. 检查部分成交状态
            if order.order_status == OrderStatus.PARTIALLY_FILLED:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"订单部分成交，不能取消",
                    error_code="ORDER_PARTIALLY_FILLED"
                )

            # 4. 获取交易接口: 账户缓存优先 (R256-P0: 与 submit 路径对齐,
            #    connect_ctp_account 注入的已登录实例), 未命中回退注册接口
            account = self._resolve_account_for_order(order)
            trading_interface = self._get_trading_interface_for_account(account) if account else None
            if trading_interface is None:
                trading_interface = self._get_trading_interface(order.asset_type)

            # R252-F6: 无可用交易接口时显式返回, 避免 None.cancel_order 抛 AttributeError
            if trading_interface is None:
                logger.error(f"取消订单失败: {order_id} - 无可用交易接口")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="无可用交易接口，无法撤销订单",
                    error_code="NO_TRADING_INTERFACE"
                )

            # 5. 提交取消请求
            result = trading_interface.cancel_order(order_id)

            # 6. 处理取消结果
            if result.status == ExecutionStatus.SUCCESS:
                order.order_status = OrderStatus.CANCELLED
                order.update_time = datetime.now()

                self.repository.update_order(order)

                # 解冻被冻结的资金
                self._unfreeze_order_funds(order)

                logger.info(f"订单取消成功: {order_id} ({order.asset_type.value})")

                # 发布订单终态事件，通知清理资源
                self.event_bus.publish('order_terminal_state',
                    order_id=order_id,
                    status=OrderStatus.CANCELLED.value
                )

                self.event_bus.publish('order_cancelled',
                    order_id=order_id,
                    asset_type=order.asset_type.value
                )

                return result
            else:
                logger.error(f"订单取消失败: {order_id} ({order.asset_type.value}) - {result.message}")

                self.event_bus.publish('order_cancel_failed',
                    order_id=order_id,
                    error=result.message,
                    asset_type=order.asset_type.value
                )

                return result

        except Exception as e:
            logger.error(f"取消订单异常: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"取消订单异常: {str(e)}",
                error_code="EXECUTION_ERROR"
            )

    def query_order_status(self, order_id: str) -> ExecutionResult:
        """查询订单状态"""
        try:
            # R252-F6: 未配置真实交易接口时 (self.trading_interface=None) 显式返回,
            # 避免 None.query_order_status 抛 AttributeError 被误判为订单状态异常
            if self.trading_interface is None:
                logger.warning(f"无可用交易接口，无法查询订单状态: {order_id}")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="无可用交易接口，无法查询订单状态",
                    error_code="QUERY_ERROR"
                )

            result = self.trading_interface.query_order_status(order_id)

            if result.status == ExecutionStatus.SUCCESS:
                # 更新本地订单状态
                order = self.repository.get_order(order_id)
                if order and 'order_status' in result.details:
                    new_status = OrderStatus(result.details['order_status'])
                    if order.order_status != new_status:
                        order.order_status = new_status
                        order.update_time = datetime.now()
                        self.repository.update_order(order)

                        logger.info(f"订单状态更新: {order_id} -> {new_status.value}")

            return result

        except Exception as e:
            logger.error(f"查询订单状态异常: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"查询订单状态异常: {str(e)}",
                error_code="QUERY_ERROR"
            )

    def handle_order_fill(self, order_id: str, fill_price: float, fill_quantity: int) -> bool:
        """处理订单成交"""
        try:
            logger.info(f"处理订单成交: {order_id} - 价格: {fill_price}, 数量: {fill_quantity}")

            # 1. 获取订单
            order = self.repository.get_order(order_id)
            if not order:
                logger.error(f"订单不存在: {order_id}")
                return False

            # 2. 更新订单成交信息
            order.filled_quantity += fill_quantity
            order.filled_price = fill_price
            order.update_time = datetime.now()

            # 3. 更新订单状态
            if order.filled_quantity >= order.order_quantity:
                order.order_status = OrderStatus.FILLED
            else:
                order.order_status = OrderStatus.PARTIALLY_FILLED

            self.repository.update_order(order)

            commission_rate = self._get_commission_rate()

            # 4. 保存成交记录
            fill = OrderFill(
                fill_id=self.repository.generate_fill_id(),
                order_id=order_id,
                stock_code=order.stock_code,
                fill_price=fill_price,
                fill_quantity=fill_quantity,
                fill_time=datetime.now(),
                commission=fill_price * fill_quantity * commission_rate
            )

            self.repository.save_order_fill(fill, order.asset_type)

            logger.info(f"订单成交处理完成: {order_id} ({order.asset_type.value}) - 已成交: {order.filled_quantity}/{order.order_quantity}")

            # 5. 发布事件
            if order.order_status == OrderStatus.FILLED:
                # 订单达到终态（FILLED），发布终态事件通知清理锁
                self.event_bus.publish('order_terminal_state',
                    order_id=order_id,
                    status=OrderStatus.FILLED.value
                )
                self.event_bus.publish('order_filled',
                    order_id=order_id,
                    fill_price=fill_price,
                    fill_quantity=fill_quantity,
                    asset_type=order.asset_type.value
                )
            else:
                self.event_bus.publish('order_partially_filled',
                    order_id=order_id,
                    fill_price=fill_price,
                    fill_quantity=fill_quantity,
                    asset_type=order.asset_type.value
                )

            return True

        except Exception as e:
            logger.error(f"处理订单成交异常: {e}")
            return False

    def set_trading_interface(self, trading_interface: TradingInterface,
                              account_id: Optional[str] = None):
        """设置交易接口 (R255-P0: 支持按账户注入, 双实例打通)

        Args:
            trading_interface: 交易接口实例
            account_id: 可选账户ID, 提供时同时写入账户接口缓存,
                        下单路径 _get_trading_interface_for_account 优先复用
        """
        if trading_interface is None:
            return
        self.trading_interface = trading_interface
        if account_id:
            self._account_interface_cache[account_id] = trading_interface
            logger.info(f"交易接口已更新并注入账户缓存: {account_id}")
        else:
            logger.info("交易接口已更新")

    # R255-P0 模式闸门 (真实资金安全): 默认 paper, 仅显式 set_trading_mode('live') 放行
    def set_trading_mode(self, mode: str, enable_risk_control: Optional[bool] = None) -> None:
        """设置交易模式 ('live'/'paper'/'backtest'), 未知模式回退 paper (绝不默认 live)

        R258-P0: 联动风控开关 _risk_control_enabled —— live/paper 强制开启 (资金安全铁律),
        backtest 由调用方显式 enable_risk_control 决定 (缺省保持当前值, 默认 True)。
        """
        normalized = str(mode or '').strip().lower()
        if normalized in ('live', 'paper', 'backtest'):
            self._trading_mode = normalized
            # 风控开关联动: live/paper 强制 True (资金安全铁律); backtest 显式值优先
            if normalized in ('live', 'paper'):
                self._risk_control_enabled = True
            elif enable_risk_control is not None:
                self._risk_control_enabled = bool(enable_risk_control)
            logger.info(
                f"交易模式设置为: {normalized}, 风控={self._risk_control_enabled}")
        else:
            self._trading_mode = 'paper'
            self._risk_control_enabled = True
            logger.warning(f"未知交易模式 {mode!r}, 回退为 paper (禁止实盘)")

    def get_trading_mode(self) -> str:
        """获取当前交易模式 (默认 'paper')"""
        return getattr(self, '_trading_mode', 'paper')

    def _is_real_trading_interface(self, trading_interface) -> bool:
        """判断是否为真实交易接口 (CTP/XTP/MiniQMT), 供模式闸门拦截

        放行 (返回 False):
        - MockTradingInterface 实例或带 _is_mock_interface=True 标记的接口
        - 测试桩 (MagicMock 等 type 名不含 CTP/XTP/MiniQMT 的类型)

        拦截 (返回 True): 仅确认为真实 CTP/XTP/MiniQMT 类型的接口
        """
        if isinstance(trading_interface, MockTradingInterface):
            return False
        if getattr(trading_interface, '_is_mock_interface', False):
            return False
        type_name = type(trading_interface).__name__
        return any(key in type_name for key in ('CTP', 'XTP', 'MiniQMT'))

    def _get_position(self, account_id: str, stock_code: str) -> int:
        try:
            from core.trading.account_manager import AccountManager
            account_manager = self.service_container.resolve(AccountManager)
            positions = account_manager.get_account_positions(account_id)
            for pos in positions:
                if pos.stock_code == stock_code:
                    if pos.side.value == 'short':
                        return -pos.quantity
                    return pos.quantity
            return 0
        except Exception as e:
            logger.debug(f"获取持仓数量失败: {e}")
            return 0

    def _get_avg_entry_price(self, account_id: str, stock_code: str) -> Optional[float]:
        try:
            from core.trading.account_manager import AccountManager
            account_manager = self.service_container.resolve(AccountManager)
            positions = account_manager.get_account_positions(account_id)
            for pos in positions:
                if pos.stock_code == stock_code:
                    return pos.cost_price if pos.cost_price else pos.open_price
            return None
        except Exception as e:
            logger.debug(f"获取平均入场价失败: {e}")
            return None

    def _get_commission_rate(self) -> float:
        """获取手续费率（从配置读取，默认万三）"""
        try:
            from core.config import config_manager
            trading_cfg = config_manager.get('trading', {})
            return trading_cfg.get('commission_rate', 0.0003)
        except Exception:
            return 0.0003

    def _unfreeze_order_funds(self, order) -> None:
        """解冻订单对应的冻结资金"""
        try:
            if order.order_category and order.order_category.value == 'market':
                return

            account_id = getattr(order, 'account_id', None)
            if not account_id or account_id == 'default':
                return

            frozen_amount = order.order_price * order.order_quantity
            from core.trading.account_manager import AccountManager
            account_manager = self.service_container.resolve(AccountManager)
            account_manager.unfreeze_cash(account_id, frozen_amount)
            logger.info(f"订单取消，解冻资金: account={account_id}, amount={frozen_amount:.2f}")
        except Exception as e:
            logger.warning(f"解冻订单资金失败: {e}")

    # R238-D-001 修复: 4 链 dispose (R233 §13.4 业务核心 P0 必修 + R78 铁律 #6 幂等短路)
    def dispose(self) -> None:
        """释放订单执行器资源"""
        if self._disposed:
            return
        self._disposed = True

        try:
            # 1. 释放全部交易接口连接 (XTPProTradingInterface ×5 + CTP ×2 + Mock ×7)
            for asset_type, interface in list(self._trading_interfaces.items()):
                try:
                    if interface is not None and hasattr(interface, 'disconnect'):
                        interface.disconnect()
                except Exception as e:
                    logger.warning(f"{asset_type.value} 交易接口释放失败: {e}")

            # 2. 释放默认交易接口 (MockTradingInterface, 不在 _trading_interfaces 中)
            if self.trading_interface is not None and hasattr(self.trading_interface, 'disconnect'):
                try:
                    self.trading_interface.disconnect()
                except Exception as e:
                    logger.warning(f"默认交易接口释放失败: {e}")

            # 3. 清空接口缓存与健康跟踪
            self._trading_interfaces.clear()
            self._account_interface_cache.clear()
            self._interface_health.clear()
            self._interface_failover_map.clear()

            # 4. 清空子组件引用
            self.repository = None
            self.trading_interface = None

            logger.info("订单执行器资源已释放")
        except Exception as e:
            logger.warning(f"订单执行器释放失败: {e}")
