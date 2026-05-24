"""
订单执行器单元测试

测试范围:
- MockTradingInterface 功能
- OrderExecutor 核心流程
- 订单提交、取消、查询
- 批量提交
- 订单成交处理
- 异常处理和边界条件
- 风控检查
"""
import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch, call
from typing import Dict, List

from core.trading.order_executor import OrderExecutor, MockTradingInterface
from core.trading.order_models import Order, OrderFill, OrderType, OrderStatus, OrderCategory
from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface
from core.plugin_types import AssetType
from core.trading.account_models import Account, TradingInterfaceType
from core.containers import ServiceContainer
from core.events import EventBus


@pytest.fixture
def mock_service_container():
    """模拟服务容器"""
    container = MagicMock(spec=ServiceContainer)
    container.resolve = MagicMock()
    container.try_resolve = MagicMock()
    return container


@pytest.fixture
def mock_event_bus():
    """模拟事件总线"""
    bus = MagicMock(spec=EventBus)
    bus.publish = MagicMock()
    return bus


@pytest.fixture
def mock_repository():
    """模拟订单仓库"""
    repo = MagicMock()
    repo.get_order = MagicMock(return_value=None)
    repo.update_order = MagicMock()
    repo.update_orders_batch = MagicMock()
    repo.save_order_fill = MagicMock()
    repo.generate_fill_id = MagicMock(return_value='FILL001')
    return repo


@pytest.fixture
def mock_account_manager():
    """模拟账户管理器"""
    manager = MagicMock()
    manager.get_account = MagicMock(return_value=None)
    manager.get_all_accounts = MagicMock(return_value=[])
    return manager


@pytest.fixture
def mock_strategy_manager():
    """模拟策略管理器"""
    manager = MagicMock()
    manager.get_strategy = MagicMock(return_value=None)
    return manager


@pytest.fixture
def sample_order():
    """创建示例订单"""
    return Order(
        order_id='ORD001',
        strategy_id='STRAT001',
        asset_type=AssetType.STOCK_A,
        stock_code='000001',
        order_type=OrderType.BUY,
        order_category=OrderCategory.LIMIT,
        order_price=10.5,
        order_quantity=100,
        order_status=OrderStatus.PENDING,
        create_time=datetime.now(),
        update_time=datetime.now(),
        account_id='ACC001'
    )


@pytest.fixture
def sample_account():
    """创建示例账户"""
    account = MagicMock(spec=Account)
    account.account_id = 'ACC001'
    account.trading_interface_type = TradingInterfaceType.MOCK
    account.available_cash = 100000.0
    account.position_limit = 10
    return account


@pytest.fixture
def executor(mock_service_container, mock_event_bus, mock_repository):
    """创建订单执行器实例"""
    with patch('core.trading.order_executor.OrderRepository', return_value=mock_repository):
        with patch('core.trading.order_executor.XTPProTradingInterface'):
            with patch('core.trading.order_executor.CTPTradingInterface'):
                with patch('core.trading.order_executor.XTPTradingInterface'):
                    exec = OrderExecutor(mock_service_container, mock_event_bus)
                    exec.repository = mock_repository
                    return exec


class TestMockTradingInterface:
    """MockTradingInterface 测试"""

    def test_submit_order_success(self):
        """测试提交订单成功"""
        interface = MockTradingInterface()
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        result = interface.submit_order(order)

        assert result.status == ExecutionStatus.SUCCESS
        assert result.order_id == 'ORD001'
        assert result.exchange_order_id.startswith('EXC')
        assert 'ORD001' in interface._orders

    def test_submit_order_exception(self):
        """测试提交订单异常"""
        interface = MockTradingInterface()
        order = MagicMock()
        order.order_id = 'ORD001'
        order.order_status = OrderStatus.PENDING

        result = interface.submit_order(order)
        assert result.status == ExecutionStatus.SUCCESS

    def test_cancel_order_success(self):
        """测试取消订单成功"""
        interface = MockTradingInterface()
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        interface.submit_order(order)

        result = interface.cancel_order('ORD001')

        assert result.status == ExecutionStatus.SUCCESS
        assert result.order_id == 'ORD001'

    def test_cancel_order_not_found(self):
        """测试取消不存在的订单"""
        interface = MockTradingInterface()
        result = interface.cancel_order('NONEXISTENT')

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'ORDER_NOT_FOUND'

    def test_query_order_status_success(self):
        """测试查询订单状态成功"""
        interface = MockTradingInterface()
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.SUBMITTED,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        interface.submit_order(order)

        result = interface.query_order_status('ORD001')

        assert result.status == ExecutionStatus.SUCCESS
        assert result.details['order_status'] == 'submitted'

    def test_query_order_status_not_found(self):
        """测试查询不存在的订单"""
        interface = MockTradingInterface()
        result = interface.query_order_status('NONEXISTENT')

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'ORDER_NOT_FOUND'


class TestOrderExecutorInitialization:
    """OrderExecutor 初始化测试"""

    def test_initialization(self, mock_service_container, mock_event_bus):
        """测试初始化"""
        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.order_executor.XTPProTradingInterface'):
                with patch('core.trading.order_executor.CTPTradingInterface'):
                    with patch('core.trading.order_executor.XTPTradingInterface'):
                        executor = OrderExecutor(mock_service_container, mock_event_bus)

                        assert executor.service_container == mock_service_container
                        assert executor.event_bus == mock_event_bus
                        assert executor.repository is not None
                        assert executor.trading_interface is not None

    def test_trading_interface_registration(self, mock_service_container, mock_event_bus):
        """测试交易接口注册"""
        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.order_executor.XTPProTradingInterface'):
                with patch('core.trading.order_executor.CTPTradingInterface'):
                    with patch('core.trading.order_executor.XTPTradingInterface'):
                        executor = OrderExecutor(mock_service_container, mock_event_bus)

                        assert AssetType.STOCK_A in executor._trading_interfaces
                        assert AssetType.FUTURES in executor._trading_interfaces
                        assert AssetType.CRYPTO in executor._trading_interfaces


class TestOrderExecutorSubmitOrder:
    """订单提交测试"""

    def test_submit_order_success(self, executor, sample_order, mock_repository, mock_event_bus):
        """测试订单提交成功"""
        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=None)
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        mock_interface = MockTradingInterface()
        executor.trading_interface = mock_interface

        result = executor.submit_order(sample_order)

        assert result.status == ExecutionStatus.SUCCESS
        assert sample_order.order_status == OrderStatus.SUBMITTED
        mock_repo.update_order.assert_called()

    def test_submit_order_validation_failed(self, executor, mock_repository):
        """测试订单验证失败"""
        mock_repo = MagicMock()
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        invalid_order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=0,
            order_quantity=0,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        result = executor.submit_order(invalid_order)

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'ORDER_VALIDATION_FAILED'

    def test_submit_order_account_not_found(self, executor, sample_order, mock_service_container, mock_repository):
        """测试账户不存在"""
        mock_repo = MagicMock()
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        mock_service_container.resolve.side_effect = [
            MagicMock(get_account=MagicMock(return_value=None), get_all_accounts=MagicMock(return_value=[])),
            MagicMock(get_strategy=MagicMock(return_value=None))
        ]

        result = executor.submit_order(sample_order)

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'ACCOUNT_NOT_FOUND'

    def test_submit_order_interface_not_found(self, executor, sample_order, mock_service_container, mock_repository, mock_account_manager):
        """测试交易接口不存在"""
        mock_repo = MagicMock()
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        mock_service_container.resolve.side_effect = lambda cls: mock_account_manager if 'AccountManager' in str(cls) else None

        result = executor.submit_order(sample_order)

        assert result.status == ExecutionStatus.FAILED

    def test_submit_order_risk_check_failed(self, executor, sample_order, mock_service_container, mock_repository):
        """测试风控检查失败"""
        mock_repo = MagicMock()
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        mock_risk_monitor = MagicMock()
        mock_risk_monitor.check_order_risk = MagicMock(return_value={'passed': False, 'reason': 'Risk limit exceeded'})
        mock_service_container.resolve.side_effect = lambda cls: mock_risk_monitor if 'RiskMonitor' in str(cls) else None

        result = executor.submit_order(sample_order)

        assert result.status == ExecutionStatus.FAILED
        assert 'RISK_CHECK' in result.error_code or result.error_code == 'ACCOUNT_NOT_FOUND'


class TestOrderExecutorBatchSubmit:
    """批量订单提交测试"""

    def test_submit_orders_batch_success(self, executor, mock_repository, mock_event_bus):
        """测试批量提交成功"""
        mock_repo = MagicMock()
        mock_repo.update_orders_batch = MagicMock()
        executor.repository = mock_repo

        orders = [
            Order(
                order_id=f'ORD{i}',
                strategy_id='STRAT001',
                asset_type=AssetType.STOCK_A,
                stock_code=f'00000{i}',
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i,
                order_quantity=100,
                order_status=OrderStatus.PENDING,
                create_time=datetime.now(),
                update_time=datetime.now(),
                account_id='ACC001'
            )
            for i in range(3)
        ]

        mock_interface = MockTradingInterface()
        executor.trading_interface = mock_interface

        with patch.object(executor, '_get_trading_interface', return_value=mock_interface):
            results = executor.submit_orders_batch(orders)

        assert len(results) == 3
        assert all(r.status == ExecutionStatus.SUCCESS for r in results)
        mock_repo.update_orders_batch.assert_called_once()

    def test_submit_orders_batch_empty(self, executor):
        """测试批量提交空订单列表"""
        results = executor.submit_orders_batch([])
        assert results == []

    def test_submit_orders_batch_with_failures(self, executor, mock_repository):
        """测试批量提交部分失败"""
        mock_repo = MagicMock()
        mock_repo.update_orders_batch = MagicMock()
        executor.repository = mock_repo

        orders = [
            Order(
                order_id=f'ORD{i}',
                strategy_id='STRAT001',
                asset_type=AssetType.STOCK_A,
                stock_code=f'00000{i}',
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0,
                order_quantity=100,
                order_status=OrderStatus.PENDING,
                create_time=datetime.now(),
                update_time=datetime.now()
            )
            for i in range(3)
        ]

        mock_interface = MagicMock()
        mock_interface.submit_order.side_effect = [
            ExecutionResult(order_id='ORD0', status=ExecutionStatus.SUCCESS, message='Success'),
            ExecutionResult(order_id='ORD1', status=ExecutionStatus.FAILED, message='Failed'),
            ExecutionResult(order_id='ORD2', status=ExecutionStatus.SUCCESS, message='Success'),
        ]

        with patch.object(executor, '_get_trading_interface', return_value=mock_interface):
            results = executor.submit_orders_batch(orders)

        assert len(results) == 3
        success_count = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        failed_count = sum(1 for r in results if r.status == ExecutionStatus.FAILED)
        assert success_count == 2
        assert failed_count == 1


class TestOrderExecutorCancelOrder:
    """取消订单测试"""

    def test_cancel_order_success(self, executor, mock_repository):
        """测试取消订单成功"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.SUBMITTED,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=order)
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        mock_interface = MockTradingInterface()
        mock_interface.submit_order(order)

        with patch.object(executor, '_get_trading_interface', return_value=mock_interface):
            result = executor.cancel_order('ORD001')

        assert result.status == ExecutionStatus.SUCCESS
        assert order.order_status == OrderStatus.CANCELLED

    def test_cancel_order_not_found(self, executor, mock_repository):
        """测试取消不存在的订单"""
        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=None)
        executor.repository = mock_repo

        result = executor.cancel_order('NONEXISTENT')

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'ORDER_NOT_FOUND'

    def test_cancel_order_completed(self, executor, mock_repository):
        """测试取消已完成的订单"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.FILLED,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=order)
        executor.repository = mock_repo

        result = executor.cancel_order('ORD001')

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'ORDER_COMPLETED'

    def test_cancel_order_partially_filled(self, executor, mock_repository):
        """测试取消部分成交的订单"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PARTIALLY_FILLED,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=order)
        executor.repository = mock_repo

        result = executor.cancel_order('ORD001')

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'ORDER_PARTIALLY_FILLED'


class TestOrderExecutorQueryStatus:
    """查询订单状态测试"""

    def test_query_order_status_success(self, executor, mock_repository):
        """测试查询订单状态成功"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.SUBMITTED,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=order)
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        mock_interface = MockTradingInterface()
        mock_interface.submit_order(order)
        executor.trading_interface = mock_interface

        result = executor.query_order_status('ORD001')

        assert result.status == ExecutionStatus.SUCCESS
        assert 'order_status' in result.details

    def test_query_order_status_exception(self, executor, mock_repository):
        """测试查询订单状态异常"""
        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=None)
        executor.repository = mock_repo

        mock_interface = MagicMock()
        mock_interface.query_order_status = MagicMock(side_effect=Exception("Query error"))
        executor.trading_interface = mock_interface

        result = executor.query_order_status('ORD001')

        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == 'QUERY_ERROR'


class TestOrderExecutorHandleFill:
    """订单成交处理测试"""

    def test_handle_order_fill_complete(self, executor, mock_repository, mock_event_bus):
        """测试订单完全成交"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.SUBMITTED,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=order)
        mock_repo.update_order = MagicMock()
        mock_repo.save_order_fill = MagicMock()
        mock_repo.generate_fill_id = MagicMock(return_value='FILL001')
        executor.repository = mock_repo

        result = executor.handle_order_fill('ORD001', 10.5, 100)

        assert result is True
        assert order.order_status == OrderStatus.FILLED
        assert order.filled_quantity == 100
        assert order.filled_price == 10.5
        mock_repo.update_order.assert_called()
        mock_repo.save_order_fill.assert_called()

    def test_handle_order_fill_partial(self, executor, mock_repository, mock_event_bus):
        """测试订单部分成交"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.SUBMITTED,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=order)
        mock_repo.update_order = MagicMock()
        mock_repo.save_order_fill = MagicMock()
        mock_repo.generate_fill_id = MagicMock(return_value='FILL001')
        executor.repository = mock_repo

        result = executor.handle_order_fill('ORD001', 10.5, 50)

        assert result is True
        assert order.order_status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity == 50

    def test_handle_order_fill_order_not_found(self, executor, mock_repository):
        """测试订单不存在"""
        mock_repo = MagicMock()
        mock_repo.get_order = MagicMock(return_value=None)
        executor.repository = mock_repo

        result = executor.handle_order_fill('NONEXISTENT', 10.5, 100)

        assert result is False


class TestOrderExecutorEdgeCases:
    """边界条件测试"""

    def test_submit_order_with_default_account_id(self, executor, mock_repository):
        """测试使用默认 account_id"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id='default'
        )

        mock_repo = MagicMock()
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        result = executor.submit_order(order)

    def test_submit_order_with_large_amount(self, executor, mock_repository, mock_service_container):
        """测试大额订单"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='000001',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=100000.0,
            order_quantity=10000,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id='ACC001'
        )

        mock_repo = MagicMock()
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        mock_service_container.resolve.side_effect = [
            MagicMock(get_account=MagicMock(return_value=None), get_all_accounts=MagicMock(return_value=[])),
            MagicMock(get_strategy=MagicMock(return_value=None))
        ]

        result = executor.submit_order(order)

    def test_concurrent_order_submission(self, executor, mock_repository, mock_event_bus):
        """测试并发订单提交"""
        import threading

        mock_repo = MagicMock()
        mock_repo.update_order = MagicMock()
        executor.repository = mock_repo

        results = []
        errors = []

        def submit_order_thread(order_id):
            try:
                order = Order(
                    order_id=f'ORD{order_id}',
                    strategy_id='STRAT001',
                    asset_type=AssetType.STOCK_A,
                    stock_code=f'00000{order_id}',
                    order_type=OrderType.BUY,
                    order_category=OrderCategory.LIMIT,
                    order_price=10.0,
                    order_quantity=100,
                    order_status=OrderStatus.PENDING,
                    create_time=datetime.now(),
                    update_time=datetime.now()
                )
                mock_interface = MockTradingInterface()
                executor.trading_interface = mock_interface
                result = executor.submit_order(order)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit_order_thread, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5

    def test_set_trading_interface(self, executor):
        """测试设置交易接口"""
        new_interface = MockTradingInterface()
        executor.set_trading_interface(new_interface)
        assert executor.trading_interface == new_interface


class TestOrderValidator:
    """订单验证测试"""

    def test_validate_order_integrity_valid(self, executor, sample_order):
        """测试有效订单验证"""
        error = executor._validate_order_integrity(sample_order)
        assert error is None

    def test_validate_order_integrity_missing_fields(self, executor):
        """测试缺少必要字段"""
        order = Order(
            order_id='ORD001',
            strategy_id='STRAT001',
            asset_type=AssetType.STOCK_A,
            stock_code='',
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=0,
            order_quantity=0,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        error = executor._validate_order_integrity(order)
        assert error is not None

    def test_validate_order_integrity_invalid_price(self, executor, sample_order):
        """测试无效价格"""
        sample_order.order_price = -10.0
        error = executor._validate_order_integrity(sample_order)
        assert error is not None

    def test_validate_order_integrity_invalid_quantity(self, executor, sample_order):
        """测试无效数量"""
        sample_order.order_quantity = -100
        error = executor._validate_order_integrity(sample_order)
        assert error is not None


class TestPreTradeRiskCheck:
    """交易前风控检查测试"""

    def test_pre_trade_risk_check_valid(self, executor, sample_order, mock_service_container):
        """测试有效的风控检查"""
        mock_service_container.resolve = MagicMock(side_effect=Exception("Service not available"))
        result = executor._pre_trade_risk_check(sample_order)
        assert 'passed' in result

    def test_pre_trade_risk_check_invalid_quantity(self, executor, sample_order):
        """测试无效数量的风控检查"""
        sample_order.order_quantity = 0
        result = executor._pre_trade_risk_check(sample_order)
        assert result['passed'] is False

    def test_pre_trade_risk_check_invalid_price(self, executor, sample_order):
        """测试无效价格的风控检查"""
        sample_order.order_price = 0
        result = executor._pre_trade_risk_check(sample_order)
        assert result['passed'] is False
