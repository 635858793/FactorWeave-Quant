"""
交易确认与风控服务测试

测试 TradingConfirmationService 的各项功能
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from core.services.trading_confirmation_service import TradingConfirmationService
from core.services.trading_service import TradingOrder, OrderSide, OrderType, OrderStatus
from core.containers import ServiceContainer
from core.events import EventBus


class TestTradingConfirmationService:
    """交易确认与风控服务测试"""

    @pytest.fixture
    def service_container(self):
        """创建服务容器"""
        return ServiceContainer()

    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()

    @pytest.fixture
    def mock_account_manager(self):
        """创建模拟账户管理器"""
        manager = Mock()
        manager.get_account = Mock(return_value=None)
        manager.get_position = Mock(return_value=None)
        return manager

    @pytest.fixture
    def trading_confirmation_service(self, service_container, event_bus, mock_account_manager):
        """创建交易确认与风控服务实例"""
        with patch.object(
            service_container,
            'resolve',
            return_value=mock_account_manager
        ):
            service = TradingConfirmationService(
                service_container=service_container,
                event_bus=event_bus
            )
            service.initialize()
            return service

    @pytest.fixture
    def sample_buy_order(self):
        """创建买入订单"""
        return TradingOrder(
            order_id="order_001",
            symbol="600000",
            symbol_name="浦发银行",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal('10.00'),
            status=OrderStatus.PENDING
        )

    @pytest.fixture
    def sample_sell_order(self):
        """创建卖出订单"""
        return TradingOrder(
            order_id="order_002",
            symbol="600000",
            symbol_name="浦发银行",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal('10.00'),
            status=OrderStatus.PENDING
        )

    def test_service_initialization(self, trading_confirmation_service):
        """测试服务初始化"""
        assert trading_confirmation_service is not None
        assert trading_confirmation_service.initialized
        assert trading_confirmation_service.metrics['operation_count'] == 0

    def test_validate_order_success(self, trading_confirmation_service, sample_buy_order):
        """测试订单验证成功"""
        is_valid, message = trading_confirmation_service.validate_order(sample_buy_order)
        
        assert is_valid is True
        assert message == "订单验证通过"

    def test_validate_order_missing_order_id(self, trading_confirmation_service):
        """测试订单ID为空"""
        order = TradingOrder(
            order_id="",
            symbol="600000",
            symbol_name="浦发银行",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal('10.00'),
            status=OrderStatus.PENDING
        )
        
        is_valid, message = trading_confirmation_service.validate_order(order)
        
        assert is_valid is False
        assert "订单ID不能为空" in message

    def test_validate_order_missing_symbol(self, trading_confirmation_service):
        """测试股票代码为空"""
        order = TradingOrder(
            order_id="order_001",
            symbol="",
            symbol_name="浦发银行",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal('10.00'),
            status=OrderStatus.PENDING
        )
        
        is_valid, message = trading_confirmation_service.validate_order(order)
        
        assert is_valid is False
        assert "股票代码不能为空" in message

    def test_validate_order_invalid_quantity(self, trading_confirmation_service):
        """测试数量无效"""
        order = TradingOrder(
            order_id="order_001",
            symbol="600000",
            symbol_name="浦发银行",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0,
            price=Decimal('10.00'),
            status=OrderStatus.PENDING
        )
        
        is_valid, message = trading_confirmation_service.validate_order(order)
        
        assert is_valid is False
        assert "数量必须大于0" in message

    def test_validate_order_limit_order_without_price(self, trading_confirmation_service):
        """测试限价单没有价格"""
        order = TradingOrder(
            order_id="order_001",
            symbol="600000",
            symbol_name="浦发银行",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=None,
            status=OrderStatus.PENDING
        )
        
        is_valid, message = trading_confirmation_service.validate_order(order)
        
        assert is_valid is False
        assert "限价单必须指定价格" in message

    def test_validate_order_invalid_price(self, trading_confirmation_service):
        """测试价格无效"""
        order = TradingOrder(
            order_id="order_001",
            symbol="600000",
            symbol_name="浦发银行",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal('0'),
            status=OrderStatus.PENDING
        )
        
        is_valid, message = trading_confirmation_service.validate_order(order)
        
        assert is_valid is False
        assert "价格必须大于0" in message

    def test_validate_order_invalid_side(self, trading_confirmation_service):
        """测试订单方向无效"""
        order = TradingOrder(
            order_id="order_001",
            symbol="600000",
            symbol_name="浦发银行",
            side="INVALID",
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal('10.00'),
            status=OrderStatus.PENDING
        )
        
        is_valid, message = trading_confirmation_service.validate_order(order)
        
        assert is_valid is False
        assert "无效的订单方向" in message

    def test_check_risk_insufficient_funds(self, trading_confirmation_service, sample_buy_order, mock_account_manager):
        """测试资金不足风险检查"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('500.00'),
            available_balance=Decimal('500.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('500.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        risk_check = trading_confirmation_service.check_risk(sample_buy_order)
        
        assert risk_check['passed'] is False
        assert "资金不足" in risk_check['reason']

    def test_check_risk_insufficient_position(self, trading_confirmation_service, sample_sell_order, mock_account_manager):
        """测试持仓不足风险检查"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_002",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        mock_account_manager.get_position.return_value = None
        
        risk_check = trading_confirmation_service.check_risk(sample_sell_order)
        
        assert risk_check['passed'] is False
        assert "持仓不足" in risk_check['reason']

    def test_check_risk_passed(self, trading_confirmation_service, sample_buy_order, mock_account_manager):
        """测试风险检查通过"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        risk_check = trading_confirmation_service.check_risk(sample_buy_order)
        
        assert risk_check['passed'] is True
        assert risk_check['reason'] == ''

    def test_check_position_limit_exceeded(self, trading_confirmation_service, sample_buy_order, mock_account_manager):
        """测试持仓限制检查"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        trading_confirmation_service.update_config({
            'max_order_amount': Decimal('500.00')
        })
        
        position_check = trading_confirmation_service.check_position_limit(sample_buy_order)
        
        assert position_check['passed'] is False
        assert "单笔订单金额超过限制" in position_check['reason']

    def test_check_position_limit_passed(self, trading_confirmation_service, sample_buy_order, mock_account_manager):
        """测试持仓限制检查通过"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        position_check = trading_confirmation_service.check_position_limit(sample_buy_order)
        
        assert position_check['passed'] is True
        assert position_check['reason'] == ''

    def test_confirm_order_success(self, trading_confirmation_service, sample_buy_order, mock_account_manager):
        """测试订单确认成功"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        is_confirmed, message = trading_confirmation_service.confirm_order(sample_buy_order)
        
        assert is_confirmed is True
        assert "订单确认成功" in message

    def test_confirm_order_validation_failed(self, trading_confirmation_service):
        """测试订单验证失败"""
        order = TradingOrder(
            order_id="",
            symbol="600000",
            symbol_name="浦发银行",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal('10.00'),
            status=OrderStatus.PENDING
        )
        
        is_confirmed, message = trading_confirmation_service.confirm_order(order)
        
        assert is_confirmed is False
        assert "订单验证失败" in message

    def test_batch_confirm_orders(self, trading_confirmation_service, mock_account_manager):
        """测试批量确认订单"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        orders = [
            TradingOrder(
                order_id=f"order_{i:03d}",
                symbol="600000",
                symbol_name="浦发银行",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=Decimal('10.00'),
                status=OrderStatus.PENDING
            )
            for i in range(1, 6)
        ]
        
        results = trading_confirmation_service.batch_confirm_orders(orders)
        
        assert len(results) == 5
        assert all(order_id in results for order_id in [f"order_{i:03d}" for i in range(1, 6)])

    def test_update_config(self, trading_confirmation_service):
        """测试更新配置"""
        new_config = {
            'max_order_amount': Decimal('5000000'),
            'max_single_position_ratio': Decimal('0.5'),
            'min_cash_ratio': Decimal('0.15'),
            'enable_risk_check': False,
            'enable_position_limit': False,
        }
        
        trading_confirmation_service.update_config(new_config)
        
        assert trading_confirmation_service._config['max_order_amount'] == Decimal('5000000')
        assert trading_confirmation_service._config['max_single_position_ratio'] == Decimal('0.5')
        assert trading_confirmation_service._config['min_cash_ratio'] == Decimal('0.15')
        assert trading_confirmation_service._config['enable_risk_check'] is False
        assert trading_confirmation_service._config['enable_position_limit'] is False

    def test_get_metrics(self, trading_confirmation_service, sample_buy_order, mock_account_manager):
        """测试获取指标"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        trading_confirmation_service.confirm_order(sample_buy_order)
        
        metrics = trading_confirmation_service.metrics
        
        assert metrics['operation_count'] == 1

    def test_reset_metrics(self, trading_confirmation_service, sample_buy_order, mock_account_manager):
        """测试重置指标"""
        from core.trading.account_models import Account, AccountStatus, InstitutionType
        
        mock_account = Account(
            account_id="order_001",
            account_name="测试账户",
            account_type="securities",
            status=AccountStatus.ACTIVE,
            balance=Decimal('10000.00'),
            available_balance=Decimal('10000.00'),
            frozen_balance=Decimal('0'),
            market_value=Decimal('0'),
            total_assets=Decimal('10000.00'),
            profit_loss=Decimal('0'),
            profit_loss_ratio=Decimal('0'),
            create_time=datetime.now(),
            update_time=datetime.now(),
            institution_type=InstitutionType.BROKER,
            institution_name="测试证券公司"
        )
        
        mock_account_manager.get_account.return_value = mock_account
        
        trading_confirmation_service.confirm_order(sample_buy_order)
        assert trading_confirmation_service.metrics['operation_count'] == 1
        
        trading_confirmation_service._metrics['operation_count'] = 0
        assert trading_confirmation_service.metrics['operation_count'] == 0

    def test_health_check(self, trading_confirmation_service):
        """测试健康检查"""
        health = trading_confirmation_service.perform_health_check()
        
        assert health is not None
        assert 'service_name' in health
        assert 'status' in health
