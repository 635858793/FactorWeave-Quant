import pytest
import tempfile
import shutil
import os
import json
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime
from typing import Dict, Any
import sqlite3

from core.trading.account_manager import AccountManager
from core.trading.account_models import Account, AccountStatus, InstitutionType, TradingInterfaceType


class TestAccountManager:
    """AccountManager 单元测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def temp_db(self, temp_dir):
        """临时数据库 fixture"""
        db_path = os.path.join(temp_dir, 'test_accounts.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                name TEXT,
                account_type TEXT,
                capital REAL,
                status TEXT,
                data TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        conn.commit()
        yield conn
        conn.close()

    @pytest.fixture
    def mock_service_container(self):
        """模拟服务容器"""
        container = MagicMock()
        return container

    @pytest.fixture
    def mock_event_bus(self):
        """模拟事件总线"""
        bus = MagicMock()
        return bus

    @pytest.fixture
    def mock_account_repository(self):
        """模拟账户仓储"""
        repo = MagicMock()
        repo.get_accounts.return_value = []
        return repo

    @pytest.fixture
    def sample_account(self):
        """示例账户对象"""
        account = MagicMock(spec=Account)
        account.account_id = 'test_001'
        account.account_name = '测试账户'
        account.account_type = 'simulated'
        account.status = AccountStatus.ACTIVE
        account.balance = 100000.0
        account.institution_name = '测试券商'
        account.trading_interface_type = TradingInterfaceType.MOCK
        return account

    def test_init_account_manager(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试 AccountManager 初始化"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            assert manager is not None
            assert manager._accounts == {}
            assert manager._positions == {}
            assert manager._fund_infos == {}

    def test_init_with_database(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试带数据库的初始化"""
        mock_account_repository.get_accounts.return_value = [sample_account]

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            assert manager is not None
            assert len(manager._accounts) == 1
            assert 'test_001' in manager._accounts

    def test_init_database_failure(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试数据库初始化失败"""
        mock_account_repository.get_accounts.side_effect = Exception("Database connection failed")

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            assert manager is not None
            assert manager._accounts == {}

    def test_create_account_success(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试成功创建账户"""
        mock_account_repository.save_account.return_value = True

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            result = manager.create_account(sample_account)

            assert result is True
            assert 'test_001' in manager._accounts
            mock_account_repository.save_account.assert_called_once()

    def test_create_account_already_exists(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试创建已存在的账户"""
        mock_account_repository.save_account.return_value = True

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager._accounts['test_001'] = sample_account
            result = manager.create_account(sample_account)

            assert result is False

    def test_create_account_database_error(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试数据库错误时创建账户"""
        mock_account_repository.save_account.return_value = False

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            result = manager.create_account(sample_account)
            assert result is False

    def test_get_all_accounts_empty(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试获取空账户列表"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            accounts = manager.get_all_accounts()
            assert accounts == []

    def test_get_all_accounts_with_data(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试获取账户列表（包含数据）"""
        mock_account_repository.get_accounts.return_value = [sample_account]

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            accounts = manager.get_all_accounts()
            assert len(accounts) == 1

    def test_get_account(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试根据ID获取账户"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager._accounts['test_001'] = sample_account
            account = manager.get_account('test_001')

            assert account is not None
            assert account.account_id == 'test_001'

    def test_get_account_not_found(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试获取不存在的账户"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            account = manager.get_account('nonexistent')
            assert account is None

    def test_update_account_success(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试成功更新账户"""
        mock_account_repository.save_account.return_value = True

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager._accounts['test_001'] = sample_account
            result = manager.update_account(sample_account)

            assert result is True
            mock_account_repository.save_account.assert_called_once()

    def test_update_account_not_found(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试更新不存在的账户"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            result = manager.update_account(sample_account)
            assert result is False

    def test_delete_account_success(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试成功删除账户"""
        mock_account_repository.delete_account.return_value = True

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager._accounts['test_001'] = sample_account
            result = manager.delete_account('test_001')

            assert result is True
            assert 'test_001' not in manager._accounts
            mock_account_repository.delete_account.assert_called_once()

    def test_delete_account_not_found(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试删除不存在的账户"""
        mock_account_repository.delete_account.return_value = False

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            result = manager.delete_account('nonexistent')
            assert result is False

    def test_delete_account_database_error(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试数据库错误时删除账户"""
        mock_account_repository.delete_account.side_effect = Exception("Database error")

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager._accounts['test_001'] = sample_account
            result = manager.delete_account('test_001')

            assert result is False
            assert 'test_001' in manager._accounts

    def test_refresh_accounts(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试刷新账户数据"""
        mock_account_repository.get_accounts.return_value = [sample_account]

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            result = manager.refresh_accounts()
            assert result is True
            mock_event_bus.publish.assert_called()

    def test_event_publishing_on_account_creation(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试账户创建时的事件发布"""
        mock_account_repository.save_account.return_value = True

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager.create_account(sample_account)

            mock_event_bus.publish.assert_called()
            calls = mock_event_bus.publish.call_args_list
            event_names = [call[0][0] for call in calls]
            assert 'account_created' in event_names

    def test_repository_property(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试仓库属性"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            assert manager.repository is not None

    def test_is_initialized_method(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试 is_initialized 方法"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            assert manager.is_initialized() is True

    def test_get_all_positions_empty(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试获取空持仓列表"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            positions = manager.get_all_positions()
            assert positions == []

    def test_get_account_positions(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试获取指定账户的持仓"""
        mock_position = MagicMock()
        mock_position.account_id = 'test_001'
        mock_position.position_id = 'pos_001'

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager._positions['pos_001'] = mock_position
            positions = manager.get_account_positions('test_001')

            assert len(positions) == 1
            assert positions[0].position_id == 'pos_001'

    def test_get_account_summary(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试获取账户汇总信息"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            manager._accounts['test_001'] = sample_account
            summary = manager.get_account_summary('test_001')

            assert summary is not None
            assert 'account' in summary
            assert 'positions' in summary
            assert summary['position_count'] == 0

    def test_get_account_summary_not_found(self, mock_service_container, mock_event_bus, mock_account_repository):
        """测试获取不存在的账户汇总"""
        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            summary = manager.get_account_summary('nonexistent')
            assert summary is None

    def test_sync_all_from_database(self, mock_service_container, mock_event_bus, sample_account, mock_account_repository):
        """测试全量数据同步"""
        mock_account_repository.get_accounts.return_value = [sample_account]
        mock_account_repository.get_positions.return_value = []
        mock_account_repository.get_all_fund_infos.return_value = []

        with patch('core.trading.account_manager.AccountRepository', return_value=mock_account_repository):
            manager = AccountManager(
                service_container=mock_service_container,
                event_bus=mock_event_bus
            )

            results = manager.sync_all_from_database()

            assert results['accounts'] == 1
            assert results['positions'] == 0
            assert results['fund_infos'] == 0
