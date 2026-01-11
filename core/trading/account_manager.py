#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户管理器

管理账户、持仓、资金等信息
"""

from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

from core.trading.account_models import (
    Account, Position, FundInfo, AccountQuery, PositionQuery,
    AccountStatus, PositionSide, InstitutionType, TradingInterfaceType
)
from core.trading.account_repository import AccountRepository
from core.containers import ServiceContainer
from core.events import EventBus


class AccountManager:
    """账户管理器"""

    def __init__(self, service_container: ServiceContainer, event_bus: EventBus):
        """
        初始化账户管理器

        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        self.service_container = service_container
        self.event_bus = event_bus
        
        self.repository = AccountRepository(service_container, event_bus)

        self._accounts: Dict[str, Account] = {}
        self._positions: Dict[str, Position] = {}
        self._fund_infos: Dict[str, FundInfo] = {}

        self._load_accounts_from_database()

        logger.info("账户管理器初始化完成")

    def _load_accounts_from_database(self):
        """
        从数据库加载账户数据
        """
        try:
            accounts = self.repository.get_accounts()
            for account in accounts:
                self._accounts[account.account_id] = account
            logger.info(f"从数据库加载了 {len(accounts)} 个账户")
        except Exception as e:
            logger.error(f"从数据库加载账户失败: {e}")

    def create_account(self, account: Account) -> bool:
        """
        创建账户

        Args:
            account: 账户对象

        Returns:
            bool: 是否创建成功
        """
        try:
            if account.account_id in self._accounts:
                logger.warning(f"账户已存在: {account.account_id}")
                return False

            # 验证账户信息
            if not account.institution_name:
                logger.warning(f"账户缺少机构名称: {account.account_id}")
            
            if not account.trading_interface_type:
                logger.warning(f"账户未指定交易接口类型，将使用默认值: {account.account_id}")
                account.trading_interface_type = TradingInterfaceType.MOCK

            self._accounts[account.account_id] = account
            
            if self.repository.save_account(account):
                logger.info(f"账户创建成功: {account.account_id}, 机构: {account.institution_name}, 交易接口: {account.trading_interface_type.value}")

                self.event_bus.publish('account_created', account_id=account.account_id, account_name=account.account_name, institution_name=account.institution_name, trading_interface_type=account.trading_interface_type.value)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"创建账户失败: {e}")
            return False

    def update_account(self, account: Account) -> bool:
        """
        更新账户信息

        Args:
            account: 账户对象

        Returns:
            bool: 是否更新成功
        """
        try:
            if account.account_id not in self._accounts:
                logger.warning(f"账户不存在: {account.account_id}")
                return False

            self._accounts[account.account_id] = account
            
            if self.repository.save_account(account):
                logger.debug(f"账户信息更新成功: {account.account_id}")

                self.event_bus.publish('account_updated', account_id=account.account_id, account_name=account.account_name)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"更新账户信息失败: {e}")
            return False

    def get_account(self, account_id: str) -> Optional[Account]:
        """
        获取账户信息

        Args:
            account_id: 账户ID

        Returns:
            Account: 账户对象，不存在返回None
        """
        return self._accounts.get(account_id)

    def query_accounts(self, query: AccountQuery) -> List[Account]:
        """
        查询账户列表

        Args:
            query: 查询条件

        Returns:
            List[Account]: 账户列表
        """
        try:
            accounts = list(self._accounts.values())

            if query.account_id:
                accounts = [a for a in accounts if a.account_id == query.account_id]

            if query.user_id:
                accounts = [a for a in accounts if a.user_id == query.user_id]

            if query.account_type:
                accounts = [a for a in accounts if a.account_type == query.account_type]

            if query.status:
                accounts = [a for a in accounts if a.status == query.status]

            if query.sort_by == "create_time":
                accounts.sort(key=lambda x: x.create_time, reverse=(query.sort_order == "desc"))
            elif query.sort_by == "update_time":
                accounts.sort(key=lambda x: x.update_time, reverse=(query.sort_order == "desc"))
            elif query.sort_by == "balance":
                accounts.sort(key=lambda x: x.balance, reverse=(query.sort_order == "desc"))

            if query.limit:
                accounts = accounts[query.offset:query.offset + query.limit]

            return accounts

        except Exception as e:
            logger.error(f"查询账户列表失败: {e}")
            return []

    def delete_account(self, account_id: str) -> bool:
        """
        删除账户

        Args:
            account_id: 账户ID

        Returns:
            bool: 是否删除成功
        """
        try:
            if account_id not in self._accounts:
                logger.warning(f"账户不存在: {account_id}")
                return False

            del self._accounts[account_id]
            
            if self.repository.delete_account(account_id):
                logger.info(f"账户删除成功: {account_id}")

                self.event_bus.publish('account_deleted', account_id=account_id)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"删除账户失败: {e}")
            return False

    def create_position(self, position: Position) -> bool:
        """
        创建持仓

        Args:
            position: 持仓对象

        Returns:
            bool: 是否创建成功
        """
        try:
            if position.position_id in self._positions:
                logger.warning(f"持仓已存在: {position.position_id}")
                return False

            self._positions[position.position_id] = position
            
            if self.repository.save_position(position):
                logger.info(f"持仓创建成功: {position.position_id}")

                self.event_bus.publish('position_created', position_id=position.position_id, account_id=position.account_id, stock_code=position.stock_code)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"创建持仓失败: {e}")
            return False

    def update_position(self, position: Position) -> bool:
        """
        更新持仓信息

        Args:
            position: 持仓对象

        Returns:
            bool: 是否更新成功
        """
        try:
            if position.position_id not in self._positions:
                logger.warning(f"持仓不存在: {position.position_id}")
                return False

            self._positions[position.position_id] = position
            
            if self.repository.save_position(position):
                logger.debug(f"持仓信息更新成功: {position.position_id}")

                self.event_bus.publish('position_updated', position_id=position.position_id, account_id=position.account_id, stock_code=position.stock_code)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"更新持仓信息失败: {e}")
            return False

    def get_position(self, position_id: str) -> Optional[Position]:
        """
        获取持仓信息

        Args:
            position_id: 持仓ID

        Returns:
            Position: 持仓对象，不存在返回None
        """
        return self._positions.get(position_id)

    def query_positions(self, query: PositionQuery) -> List[Position]:
        """
        查询持仓列表

        Args:
            query: 查询条件

        Returns:
            List[Position]: 持仓列表
        """
        try:
            positions = list(self._positions.values())

            if query.account_id:
                positions = [p for p in positions if p.account_id == query.account_id]

            if query.asset_type:
                positions = [p for p in positions if p.asset_type == query.asset_type]

            if query.stock_code:
                positions = [p for p in positions if p.stock_code == query.stock_code]

            if query.side:
                positions = [p for p in positions if p.side == query.side]

            if query.sort_by == "open_time":
                positions.sort(key=lambda x: x.open_time, reverse=(query.sort_order == "desc"))
            elif query.sort_by == "update_time":
                positions.sort(key=lambda x: x.update_time, reverse=(query.sort_order == "desc"))
            elif query.sort_by == "market_value":
                positions.sort(key=lambda x: x.market_value, reverse=(query.sort_order == "desc"))

            if query.limit:
                positions = positions[query.offset:query.offset + query.limit]

            return positions

        except Exception as e:
            logger.error(f"查询持仓列表失败: {e}")
            return []

    def delete_position(self, position_id: str) -> bool:
        """
        删除持仓

        Args:
            position_id: 持仓ID

        Returns:
            bool: 是否删除成功
        """
        try:
            if position_id not in self._positions:
                logger.warning(f"持仓不存在: {position_id}")
                return False

            del self._positions[position_id]
            
            if self.repository.delete_position(position_id):
                logger.info(f"持仓删除成功: {position_id}")

                self.event_bus.publish('position_deleted', position_id=position_id)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"删除持仓失败: {e}")
            return False

    def update_fund_info(self, fund_info: FundInfo) -> bool:
        """
        更新资金信息

        Args:
            fund_info: 资金信息对象

        Returns:
            bool: 是否更新成功
        """
        try:
            self._fund_infos[fund_info.account_id] = fund_info
            
            if self.repository.save_fund_info(fund_info):
                logger.debug(f"资金信息更新成功: {fund_info.account_id}")

                self.event_bus.publish('fund_updated', account_id=fund_info.account_id, total_assets=fund_info.total_assets)

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"更新资金信息失败: {e}")
            return False

    def get_fund_info(self, account_id: str) -> Optional[FundInfo]:
        """
        获取资金信息

        Args:
            account_id: 账户ID

        Returns:
            FundInfo: 资金信息对象，不存在返回None
        """
        return self._fund_infos.get(account_id)

    def get_all_accounts(self) -> List[Account]:
        """
        获取所有账户

        Returns:
            List[Account]: 账户列表
        """
        return list(self._accounts.values())

    def get_all_positions(self) -> List[Position]:
        """
        获取所有持仓

        Returns:
            List[Position]: 持仓列表
        """
        return list(self._positions.values())

    def get_account_positions(self, account_id: str) -> List[Position]:
        """
        获取指定账户的所有持仓

        Args:
            account_id: 账户ID

        Returns:
            List[Position]: 持仓列表
        """
        return [p for p in self._positions.values() if p.account_id == account_id]

    def get_account_summary(self, account_id: str) -> Optional[Dict]:
        """
        获取账户汇总信息

        Args:
            account_id: 账户ID

        Returns:
            Dict: 账户汇总信息
        """
        try:
            account = self.get_account(account_id)
            if not account:
                return None

            positions = self.get_account_positions(account_id)
            fund_info = self.get_fund_info(account_id)

            summary = {
                'account': account.to_dict(),
                'positions': [p.to_dict() for p in positions],
                'fund_info': fund_info.to_dict() if fund_info else None,
                'position_count': len(positions),
                'total_market_value': sum(p.market_value for p in positions),
                'total_profit_loss': sum(p.profit_loss for p in positions)
            }

            return summary

        except Exception as e:
            logger.error(f"获取账户汇总信息失败: {e}")
            return None

    def start_account_monitoring(self, account_id: str, interval_seconds: int = 60):
        """
        启动账户状态监控

        Args:
            account_id: 账户ID
            interval_seconds: 监控间隔（秒）
        """
        try:
            logger.info(f"启动账户监控: {account_id}, 间隔: {interval_seconds}秒")

            from PyQt5.QtCore import QTimer

            if not hasattr(self, '_monitor_timers'):
                self._monitor_timers = {}

            if account_id in self._monitor_timers:
                logger.warning(f"账户监控已存在: {account_id}")
                return

            timer = QTimer()
            timer.timeout.connect(lambda: self._monitor_account_status(account_id))
            timer.start(interval_seconds * 1000)

            self._monitor_timers[account_id] = timer
            logger.info(f"账户监控已启动: {account_id}")

        except Exception as e:
            logger.error(f"启动账户监控失败: {e}")

    def stop_account_monitoring(self, account_id: str):
        """
        停止账户状态监控

        Args:
            account_id: 账户ID
        """
        try:
            if hasattr(self, '_monitor_timers') and account_id in self._monitor_timers:
                timer = self._monitor_timers[account_id]
                timer.stop()
                del self._monitor_timers[account_id]
                logger.info(f"账户监控已停止: {account_id}")

        except Exception as e:
            logger.error(f"停止账户监控失败: {e}")

    def _monitor_account_status(self, account_id: str):
        """
        监控账户状态

        Args:
            account_id: 账户ID
        """
        try:
            account = self.get_account(account_id)
            if not account:
                logger.warning(f"账户不存在: {account_id}")
                return

            old_status = account.status

            self.sync_account_fund(account_id)
            self.sync_account_positions(account_id)

            account = self.get_account(account_id)
            new_status = account.status

            if old_status != new_status:
                logger.info(f"账户状态变化: {account_id} {old_status} -> {new_status}")
                self.event_bus.publish('account_status_changed', account_id=account_id, old_status=old_status.value if old_status else None, new_status=new_status.value if new_status else None)

        except Exception as e:
            logger.error(f"监控账户状态失败: {e}")

    def sync_account_fund(self, account_id: str) -> bool:
        """
        同步账户资金信息

        Args:
            account_id: 账户ID

        Returns:
            bool: 是否同步成功
        """
        try:
            logger.debug(f"同步账户资金: {account_id}")

            account = self.get_account(account_id)
            if not account:
                logger.warning(f"账户不存在: {account_id}")
                return False

            # 根据账户类型获取对应的交易接口
            trading_interface = self._get_trading_interface_for_account(account)
            if not trading_interface:
                logger.warning(f"无法获取交易接口: {account_id}")
                return False

            fund_info = trading_interface.query_fund_info(account_id)
            if fund_info:
                self.update_fund_info(fund_info)
                logger.debug(f"账户资金同步成功: {account_id}")
                return True
            else:
                logger.warning(f"获取账户资金失败: {account_id}")
                return False

        except Exception as e:
            logger.error(f"同步账户资金失败: {e}")
            return False

    def sync_account_positions(self, account_id: str) -> bool:
        """
        同步账户持仓信息

        Args:
            account_id: 账户ID

        Returns:
            bool: 是否同步成功
        """
        try:
            logger.debug(f"同步账户持仓: {account_id}")

            account = self.get_account(account_id)
            if not account:
                logger.warning(f"账户不存在: {account_id}")
                return False

            if not account.trading_interface:
                logger.warning(f"账户未配置交易接口: {account_id}")
                return False

            trading_interface = self.service_container.resolve(account.trading_interface)
            if not trading_interface:
                logger.warning(f"交易接口未注册: {account.trading_interface}")
                return False

            if not trading_interface._logged_in:
                logger.warning(f"交易接口未登录: {account.trading_interface}")
                return False

            positions = trading_interface.query_positions(account_id)
            if positions:
                for position in positions:
                    existing_position = self.get_position(position.position_id)
                    if existing_position:
                        self.update_position(position)
                    else:
                        self.create_position(position)

                logger.debug(f"账户持仓同步成功: {account_id}, 数量: {len(positions)}")
                return True
            else:
                logger.warning(f"获取账户持仓失败: {account_id}")
                return False

        except Exception as e:
            logger.error(f"同步账户持仓失败: {e}")
            return False

    def _get_trading_interface_for_account(self, account):
        """
        根据账户获取对应的交易接口

        Args:
            account: 账户对象

        Returns:
            TradingInterface: 交易接口实例
        """
        from core.trading.order_executor import OrderExecutor
        
        # 获取OrderExecutor
        order_executor = self.service_container.resolve(OrderExecutor)
        
        # 根据账户类型获取资产类型
        if account.account_type == "股票账户":
            from core.plugin_types import AssetType
            asset_type = AssetType.STOCK_A
        elif account.account_type in ["期货账户", "期权账户"]:
            from core.plugin_types import AssetType
            asset_type = AssetType.FUTURES
        else:
            from core.plugin_types import AssetType
            asset_type = AssetType.CRYPTO
        
        # 从OrderExecutor获取对应的交易接口
        trading_interface = order_executor._trading_interfaces.get(asset_type)
        if trading_interface:
            # 根据交易接口类型初始化账户信息
            if account.trading_interface_type == TradingInterfaceType.XTP_PRO:
                from core.trading.interfaces.xtp_pro_trading_interface import XTPProTradingInterface
                if isinstance(trading_interface, XTPProTradingInterface):
                    trading_interface.account_id = account.xtp_account_id
                    trading_interface.password = account.xtp_password
                    trading_interface.server_address = account.xtp_server_address
                    trading_interface.trade_server = account.xtp_server_address
                    trading_interface.quote_server = account.xtp_server_address
                    logger.info(f"使用账户信息初始化XTP Pro接口: {account.account_id}")
            elif account.trading_interface_type == TradingInterfaceType.CTP:
                from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface
                if isinstance(trading_interface, CTPTradingInterface):
                    trading_interface.broker_id = account.ctp_broker_id
                    trading_interface.investor_id = account.ctp_investor_id
                    trading_interface.password = account.ctp_password
                    trading_interface.trade_front = account.ctp_trade_front
                    trading_interface.quote_front = account.ctp_quote_front
                    logger.info(f"使用账户信息初始化CTP接口: {account.account_id}")
        
        return trading_interface


