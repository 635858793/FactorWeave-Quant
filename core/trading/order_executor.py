"""
订单执行器

负责订单执行与接口对接
"""

from loguru import logger
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from core.trading.order_models import Order, OrderFill, OrderType, OrderStatus, OrderCategory
from core.trading.order_repository import OrderRepository
from core.containers import ServiceContainer
from core.events import EventBus
from core.plugin_types import AssetType
from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface
from core.trading.interfaces.xtp_trading_interface import XTPTradingInterface
from core.trading.interfaces.xtp_pro_trading_interface import XTPProTradingInterface
from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface
from core.trading.account_models import TradingInterfaceType, Account
from typing import Optional


class MockTradingInterface(TradingInterface):
    """模拟交易接口"""

    def __init__(self):
        self._orders: Dict[str, Order] = {}
        self._order_counter = 0

    def submit_order(self, order: Order) -> ExecutionResult:
        """提交订单（模拟）"""
        try:
            self._order_counter += 1
            exchange_order_id = f"EXC{self._order_counter:08d}"

            self._orders[order.order_id] = order

            logger.info(f"模拟提交订单: {order.order_id} -> {exchange_order_id}")

            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.SUCCESS,
                message="订单提交成功",
                exchange_order_id=exchange_order_id
            )

        except Exception as e:
            logger.error(f"模拟提交订单失败: {e}")
            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.FAILED,
                message=f"订单提交失败: {str(e)}",
                error_code="SUBMIT_FAILED"
            )

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


class OrderExecutor:
    """订单执行器"""

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        self.service_container = service_container
        self.event_bus = event_bus

        self.repository: OrderRepository = None
        self.trading_interface: TradingInterface = None
        
        self._trading_interfaces: Dict[AssetType, TradingInterface] = {}
        self._account_interface_cache: Dict[str, TradingInterface] = {}

        self._initialize()

        logger.info("订单执行器初始化完成")

    def _initialize(self):
        """初始化"""
        self.repository = OrderRepository(self.service_container, self.event_bus)

        # 注册不同资产类型的交易接口
        self._register_trading_interfaces()

        # 默认使用模拟交易接口
        self.trading_interface = MockTradingInterface()

    def _register_trading_interfaces(self):
        """注册不同资产类型的交易接口"""
        # 注册股票交易接口（XTP Pro）
        self._trading_interfaces[AssetType.STOCK_A] = XTPProTradingInterface()
        self._trading_interfaces[AssetType.STOCK_B] = XTPProTradingInterface()
        self._trading_interfaces[AssetType.STOCK_H] = XTPProTradingInterface()
        self._trading_interfaces[AssetType.STOCK_US] = XTPProTradingInterface()
        self._trading_interfaces[AssetType.STOCK_HK] = XTPProTradingInterface()
        
        # 注册期货交易接口（CTP）
        self._trading_interfaces[AssetType.FUTURES] = CTPTradingInterface()
        
        # 注册期权交易接口（CTP）
        self._trading_interfaces[AssetType.OPTION] = CTPTradingInterface()
        
        # 注册加密货币交易接口
        self._trading_interfaces[AssetType.CRYPTO] = MockTradingInterface()
        
        # 注册外汇交易接口
        self._trading_interfaces[AssetType.FOREX] = MockTradingInterface()
        
        # 注册债券交易接口
        self._trading_interfaces[AssetType.BOND] = MockTradingInterface()
        
        # 注册商品交易接口
        self._trading_interfaces[AssetType.COMMODITY] = MockTradingInterface()
        
        # 注册指数交易接口
        self._trading_interfaces[AssetType.INDEX] = MockTradingInterface()
        
        # 注册基金交易接口
        self._trading_interfaces[AssetType.FUND] = MockTradingInterface()
        
        # 注册权证交易接口
        self._trading_interfaces[AssetType.WARRANT] = MockTradingInterface()
        
        logger.info("交易接口注册完成")

        # 初始化所有交易接口
        self._initialize_trading_interfaces()

    def _initialize_trading_interfaces(self):
        """初始化所有交易接口"""
        # 先从账户管理器获取账户信息
        self._load_account_info_to_interfaces()
        
        # 然后初始化所有交易接口
        for asset_type, interface in self._trading_interfaces.items():
            try:
                if interface.connect():
                    logger.info(f"{asset_type.value} 交易接口连接成功")
                    if interface.login():
                        logger.info(f"{asset_type.value} 交易接口登录成功")
                    else:
                        logger.warning(f"{asset_type.value} 交易接口登录失败")
                else:
                    logger.warning(f"{asset_type.value} 交易接口连接失败")
            except Exception as e:
                logger.error(f"{asset_type.value} 交易接口初始化失败: {e}")

    def _load_account_info_to_interfaces(self):
        """从账户管理器加载账户信息到交易接口"""
        try:
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

    def _get_trading_interface(self, asset_type: AssetType) -> TradingInterface:
        """根据资产类型获取对应的交易接口"""
        trading_interface = self._trading_interfaces.get(asset_type)
        if not trading_interface:
            logger.warning(f"未找到资产类型 {asset_type.value} 的交易接口，使用默认接口")
            return self.trading_interface
        return trading_interface

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

            # 优先级1：订单级别
            if order.account_id and order.account_id != "default":
                account = account_manager.get_account(order.account_id)
                if account:
                    logger.info(f"使用订单指定的账号: {account.account_id}")
                    return account
                else:
                    logger.warning(f"订单指定的账号不存在: {order.account_id}")

            # 优先级2：策略级别
            if order.strategy_id and order.strategy_id != "default":
                strategy = strategy_manager.get_strategy(order.strategy_id)
                if strategy and hasattr(strategy, 'default_account_id') and strategy.default_account_id:
                    account = account_manager.get_account(strategy.default_account_id)
                    if account:
                        logger.info(f"使用策略的默认账号: {account.account_id}")
                        return account
                    else:
                        logger.warning(f"策略的默认账号不存在: {strategy.default_account_id}")

            # 优先级3：系统级别
            accounts = account_manager.get_all_accounts()
            if accounts:
                # 返回第一个账号作为系统默认账号
                account = accounts[0]
                logger.info(f"使用系统默认账号: {account.account_id}")
                return account

            logger.warning("无法解析订单使用的账号")
            return None

        except Exception as e:
            logger.error(f"解析订单账号失败: {e}")
            return None

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
            trading_interface_type = account.trading_interface_type

            if trading_interface_type == TradingInterfaceType.MOCK:
                interface = MockTradingInterface()

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

            else:
                logger.warning(f"未知的交易接口类型: {trading_interface_type.value}，使用模拟接口")
                interface = MockTradingInterface()

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

            # 3. 根据账号获取对应的交易接口
            trading_interface = self._get_trading_interface_for_account(account)
            if not trading_interface:
                logger.error(f"无法获取账号 {account.account_id} 的交易接口")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"无法获取账号 {account.account_id} 的交易接口",
                    error_code="INTERFACE_NOT_FOUND"
                )

            # 4. 提交到交易接口
            result = trading_interface.submit_order(order)

            # 5. 处理执行结果
            if result.status == ExecutionStatus.SUCCESS:
                order.execute_time = datetime.now()
                order.update_time = datetime.now()
                order.metadata['exchange_order_id'] = result.exchange_order_id
                order.metadata['account_id'] = account.account_id

                self.repository.update_order(order)

                logger.info(f"订单提交成功: {order.order_id} ({order.asset_type.value}) -> {result.exchange_order_id}, 账号: {account.account_id}")

                self.event_bus.publish('order_submitted_success',
                    order_id=order.order_id,
                    exchange_order_id=result.exchange_order_id,
                    asset_type=order.asset_type.value,
                    account_id=account.account_id
                )

                return result
            else:
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
                trading_interface = self._get_trading_interface(asset_type)

                for order in asset_orders:
                    try:
                        # 提交到交易接口
                        result = trading_interface.submit_order(order)

                        # 处理执行结果
                        if result.status == ExecutionStatus.SUCCESS:
                            order.execute_time = datetime.now()
                            order.update_time = datetime.now()
                            order.metadata['exchange_order_id'] = result.exchange_order_id

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

            # 1. 获取订单
            order = self.repository.get_order(order_id)
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

            # 3. 根据资产类型获取对应的交易接口
            trading_interface = self._get_trading_interface(order.asset_type)

            # 4. 提交取消请求
            result = trading_interface.cancel_order(order_id)

            # 5. 处理取消结果
            if result.status == ExecutionStatus.SUCCESS:
                order.order_status = OrderStatus.CANCELLED
                order.update_time = datetime.now()

                self.repository.update_order(order)

                logger.info(f"订单取消成功: {order_id} ({order.asset_type.value})")

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

            # 4. 保存成交记录
            fill = OrderFill(
                fill_id=self.repository.generate_fill_id(),
                order_id=order_id,
                stock_code=order.stock_code,
                fill_price=fill_price,
                fill_quantity=fill_quantity,
                fill_time=datetime.now(),
                commission=fill_price * fill_quantity * 0.0003  # 假设手续费率为0.03%
            )

            self.repository.save_order_fill(fill, order.asset_type)

            logger.info(f"订单成交处理完成: {order_id} ({order.asset_type.value}) - 已成交: {order.filled_quantity}/{order.order_quantity}")

            # 5. 发布事件
            if order.order_status == OrderStatus.FILLED:
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

    def set_trading_interface(self, trading_interface: TradingInterface):
        """设置交易接口"""
        self.trading_interface = trading_interface
        logger.info("交易接口已更新")
