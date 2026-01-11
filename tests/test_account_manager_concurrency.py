"""
账户管理器并发测试

测试 AccountManager 在多线程环境下的并发安全性
"""

import pytest
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from core.trading.account_manager import AccountManager
from core.trading.account_models import Account, AccountStatus, InstitutionType, PositionSide
from core.containers import ServiceContainer
from core.events import EventBus


class TestAccountManagerConcurrency:
    """账户管理器并发测试"""

    @pytest.fixture
    def service_container(self):
        """创建服务容器"""
        return ServiceContainer()

    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()

    @pytest.fixture
    def sample_account(self):
        """创建测试账户"""
        return Account(
            account_id="test_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=100000.0,
            available_balance=100000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )

    def test_thread_lock_protection(self):
        """测试线程锁保护"""
        from core.trading.account_manager import AccountManager
        
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        with patch('core.trading.account_repository.AccountRepository._init_database_tables'):
            manager = AccountManager(service_container, event_bus)
            
            assert hasattr(manager, '_account_lock')
            assert hasattr(manager, '_position_lock')
            assert hasattr(manager, '_fund_info_lock')

    def test_concurrent_account_access(self, sample_account):
        """测试并发账户访问"""
        from core.trading.account_manager import AccountManager
        
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        with patch('core.trading.account_repository.AccountRepository._init_database_tables'):
            manager = AccountManager(service_container, event_bus)
            manager._accounts['test_001'] = sample_account
            
            num_threads = 10
            accesses_per_thread = 100
            results = []
            errors = []

            def access_account(thread_id):
                try:
                    for i in range(accesses_per_thread):
                        account = manager.get_account('test_001')
                        if account:
                            results.append((thread_id, i, account.account_id))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append((thread_id, str(e)))

            threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=access_account, args=(i,))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            assert len(errors) == 0, f"并发访问账户时发生错误: {errors}"
            assert len(results) == num_threads * accesses_per_thread

    def test_concurrent_account_modification(self, sample_account):
        """测试并发账户修改"""
        from core.trading.account_manager import AccountManager
        
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        with patch('core.trading.account_repository.AccountRepository._init_database_tables'):
            manager = AccountManager(service_container, event_bus)
            manager._accounts['test_001'] = sample_account
            
            num_threads = 10
            updates_per_thread = 10
            results = []
            errors = []

            def modify_account(thread_id):
                try:
                    for i in range(updates_per_thread):
                        account = manager.get_account('test_001')
                        if account:
                            account.available_balance += 100.0
                            account.total_assets += 100.0
                            results.append((thread_id, i, account.available_balance))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append((thread_id, str(e)))

            threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=modify_account, args=(i,))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            assert len(errors) == 0, f"并发修改账户时发生错误: {errors}"
            assert len(results) == num_threads * updates_per_thread

    def test_concurrent_query_accounts(self, sample_account):
        """测试并发查询账户"""
        from core.trading.account_manager import AccountManager
        from core.trading.account_models import AccountQuery
        
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        with patch('core.trading.account_repository.AccountRepository._init_database_tables'):
            manager = AccountManager(service_container, event_bus)
            
            for i in range(20):
                account = Account(
                    account_id=f"query_test_{i}",
                    account_name=f"查询测试_{i}",
                    account_type="securities",
                    status=AccountStatus.ACTIVE,
                    balance=100000.0,
                    available_balance=100000.0,
                    frozen_balance=0.0,
                    market_value=0.0,
                    total_assets=100000.0,
                    profit_loss=0.0,
                    profit_loss_ratio=0.0,
                    create_time=datetime.now(),
                    update_time=datetime.now(),
                    institution_type=InstitutionType.BROKER,
                    institution_name="测试证券公司"
                )
                manager._accounts[f"query_test_{i}"] = account

            num_threads = 10
            queries_per_thread = 10
            results = []
            errors = []

            def query_accounts(thread_id):
                try:
                    for i in range(queries_per_thread):
                        query = AccountQuery(
                            status=AccountStatus.ACTIVE,
                            limit=10,
                            offset=i % 10
                        )
                        accounts = manager.query_accounts(query)
                        results.append((thread_id, len(accounts)))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append((thread_id, str(e)))

            threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=query_accounts, args=(i,))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            assert len(errors) == 0, f"并发查询账户时发生错误: {errors}"
            assert len(results) == num_threads * queries_per_thread

    def test_concurrent_position_access(self):
        """测试并发持仓访问"""
        from core.trading.account_manager import AccountManager
        from core.trading.account_models import Position
        from core.plugin_types import AssetType
        
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        with patch('core.trading.account_repository.AccountRepository._init_database_tables'):
            manager = AccountManager(service_container, event_bus)
            
            position = Position(
                position_id="test_position_001",
                account_id="test_001",
                asset_type=AssetType.STOCK_A,
                stock_code="600000",
                stock_name="浦发银行",
                side=PositionSide.LONG,
                quantity=1000,
                available_quantity=1000,
                open_price=10.0,
                current_price=10.0,
                market_value=10000.0,
                cost_price=10.0,
                cost_value=10000.0,
                profit_loss=0.0,
                profit_loss_ratio=0.0,
                open_time=datetime.now(),
                update_time=datetime.now()
            )
            manager._positions['test_position_001'] = position
            
            num_threads = 10
            accesses_per_thread = 100
            results = []
            errors = []

            def access_position(thread_id):
                try:
                    for i in range(accesses_per_thread):
                        pos = manager.get_position('test_position_001')
                        if pos:
                            results.append((thread_id, i, pos.position_id))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append((thread_id, str(e)))

            threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=access_position, args=(i,))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            assert len(errors) == 0, f"并发访问持仓时发生错误: {errors}"
            assert len(results) == num_threads * accesses_per_thread

    def test_concurrent_fund_info_access(self):
        """测试并发资金信息访问"""
        from core.trading.account_manager import AccountManager
        from core.trading.account_models import FundInfo
        
        service_container = ServiceContainer()
        event_bus = EventBus()
        
        with patch('core.trading.account_repository.AccountRepository._init_database_tables'):
            manager = AccountManager(service_container, event_bus)
            
            fund_info = FundInfo(
                account_id="test_001",
                total_balance=100000.0,
                available_balance=100000.0,
                frozen_balance=0.0,
                market_value=0.0,
                total_assets=100000.0,
                profit_loss=0.0,
                profit_loss_ratio=0.0,
                margin_used=0.0,
                margin_available=100000.0,
                maintenance_margin=0.0,
                update_time=datetime.now()
            )
            manager._fund_infos['test_001'] = fund_info
            
            num_threads = 10
            accesses_per_thread = 100
            results = []
            errors = []

            def access_fund_info(thread_id):
                try:
                    for i in range(accesses_per_thread):
                        fund = manager.get_fund_info('test_001')
                        if fund:
                            results.append((thread_id, i, fund.account_id))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append((thread_id, str(e)))

            threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=access_fund_info, args=(i,))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            assert len(errors) == 0, f"并发访问资金信息时发生错误: {errors}"
            assert len(results) == num_threads * accesses_per_thread
