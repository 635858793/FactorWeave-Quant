# -*- coding: utf-8 -*-
"""
XTP Pro交易接口测试

测试XTP Pro交易接口的功能完整性，包括：
1. 连接和登录
2. 下单和撤单
3. 查询订单、持仓、资金
4. 回调处理
5. 事件集成
"""

import pytest
import time
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from loguru import logger

from core.trading.interfaces.xtp_pro_trading_interface import XTPProTradingInterface
from core.trading.order_models import Order, OrderStatus, OrderType, OrderCategory
from core.trading.trading_types import ExecutionResult, ExecutionStatus
from core.events.event_bus import EventBus


class TestXTPProTradingInterface:
    """XTP Pro交易接口测试"""
    
    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        event_bus = EventBus()
        return event_bus
    
    @pytest.fixture
    def xtp_interface(self, event_bus):
        """创建XTP Pro交易接口"""
        interface = XTPProTradingInterface(
            account_id="test_account",
            password="test_password",
            client_id=1,
            trade_server="127.0.0.1:6001",
            quote_server="127.0.0.1:6002",
            event_bus=event_bus
        )
        return interface
    
    @pytest.fixture
    def sample_order(self):
        """创建示例订单"""
        from core.plugin_types import AssetType
        order = Order(
            order_id="TEST001",
            strategy_id="TEST_STRATEGY",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=1000,
            order_status=OrderStatus.PENDING,
            account_id="test_account",
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        return order
    
    def test_initialization(self, xtp_interface):
        """测试初始化"""
        assert xtp_interface.account_id == "test_account"
        assert xtp_interface.password == "test_password"
        assert xtp_interface.client_id == 1
        assert xtp_interface.trade_server == "127.0.0.1:6001"
        assert xtp_interface.quote_server == "127.0.0.1:6002"
        assert xtp_interface.event_bus is not None
        assert xtp_interface._connected is False
        assert xtp_interface._logged_in is False
        assert len(xtp_interface._orders) == 0
        assert len(xtp_interface._exchange_order_map) == 0
        logger.info("✓ 初始化测试通过")
    
    def test_connect_simulation_mode(self, xtp_interface):
        """测试连接（模拟模式）"""
        result = xtp_interface.connect()
        assert result is True
        assert xtp_interface._connected is True
        logger.info("✓ 连接测试（模拟模式）通过")
    
    def test_login_simulation_mode(self, xtp_interface):
        """测试登录（模拟模式）"""
        xtp_interface._connected = True
        result = xtp_interface.login()
        assert result is True
        assert xtp_interface._logged_in is True
        logger.info("✓ 登录测试（模拟模式）通过")
    
    def test_submit_order_simulation_mode(self, xtp_interface, sample_order):
        """测试提交订单（模拟模式）"""
        xtp_interface._logged_in = True
        xtp_interface._connected = True
        
        result = xtp_interface.submit_order(sample_order)
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.order_id == "TEST001"
        assert result.exchange_order_id is not None
        assert "XTPPRO" in result.exchange_order_id
        assert sample_order.order_id in xtp_interface._orders
        assert result.exchange_order_id in xtp_interface._exchange_order_map
        logger.info(f"✓ 提交订单测试（模拟模式）通过: {result.exchange_order_id}")
    
    def test_cancel_order_simulation_mode(self, xtp_interface, sample_order):
        """测试取消订单（模拟模式）"""
        xtp_interface._logged_in = True
        xtp_interface._connected = True
        
        # 先提交订单
        submit_result = xtp_interface.submit_order(sample_order)
        assert submit_result.status == ExecutionStatus.SUCCESS
        
        # 取消订单
        cancel_result = xtp_interface.cancel_order("TEST001")
        
        assert cancel_result.status == ExecutionStatus.SUCCESS
        assert cancel_result.message == "订单取消成功（模拟模式）"
        logger.info("✓ 取消订单测试（模拟模式）通过")
    
    def test_query_order_status(self, xtp_interface, sample_order):
        """测试查询订单状态"""
        xtp_interface._logged_in = True
        xtp_interface._connected = True
        
        # 先提交订单
        xtp_interface.submit_order(sample_order)
        
        # 查询订单状态
        result = xtp_interface.query_order_status("TEST001")
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.message == "订单状态查询成功"
        assert "order_status" in result.details
        assert "filled_quantity" in result.details
        assert "remaining_quantity" in result.details
        logger.info("✓ 查询订单状态测试通过")
    
    def test_query_fund_info_simulation_mode(self, xtp_interface):
        """测试查询资金信息（模拟模式）"""
        xtp_interface._logged_in = True
        
        fund_info = xtp_interface.query_fund_info("test_account")
        
        assert fund_info is not None
        assert fund_info.account_id == "test_account"
        assert fund_info.total_balance == 1000000.0
        assert fund_info.available_balance == 500000.0
        assert fund_info.market_value == 500000.0
        logger.info("✓ 查询资金信息测试（模拟模式）通过")
    
    def test_query_positions_simulation_mode(self, xtp_interface):
        """测试查询持仓信息（模拟模式）"""
        xtp_interface._logged_in = True
        
        positions = xtp_interface.query_positions("test_account")
        
        assert positions is not None
        assert len(positions) > 0
        assert positions[0].stock_code == "000001"
        assert positions[0].stock_name == "平安银行"
        assert positions[0].quantity == 1000
        logger.info("✓ 查询持仓信息测试（模拟模式）通过")
    
    def test_disconnect(self, xtp_interface):
        """测试断开连接"""
        xtp_interface._connected = True
        xtp_interface._logged_in = True
        
        xtp_interface.disconnect()
        
        assert xtp_interface._connected is False
        assert xtp_interface._logged_in is False
        logger.info("✓ 断开连接测试通过")
    
    def test_order_event_callback(self, xtp_interface, sample_order, event_bus):
        """测试订单状态回调"""
        xtp_interface._logged_in = True
        xtp_interface._connected = True
        
        # 提交订单
        xtp_interface.submit_order(sample_order)
        
        # 获取exchange_order_id
        exchange_order_id = list(xtp_interface._exchange_order_map.keys())[0]
        
        # 创建模拟的订单状态信息
        mock_order_info = Mock()
        mock_order_info.order_xtp_id = exchange_order_id
        mock_order_info.order_status = 52  # XTP_ORDER_STATUS_FILLED
        mock_order_info.filled_quantity = 1000
        mock_order_info.avg_price = 10.50
        
        # 订阅订单状态变更事件
        events_received = []
        def on_order_status_changed(event_obj):
            events_received.append({
                'order_id': event_obj.order_id,
                'old_status': event_obj.old_status,
                'new_status': event_obj.new_status,
                'exchange_order_id': event_obj.exchange_order_id,
                'filled_quantity': event_obj.filled_quantity,
                'remaining_quantity': event_obj.remaining_quantity
            })
        
        event_bus.subscribe('order_status_changed', on_order_status_changed)
        
        # 调用订单状态回调
        xtp_interface._on_order_event(mock_order_info)
        
        # 验证订单状态已更新
        assert sample_order.order_status == OrderStatus.FILLED
        assert sample_order.filled_quantity == 1000
        
        # 验证事件已发布
        assert len(events_received) == 1
        assert events_received[0]['order_id'] == "TEST001"
        assert events_received[0]['new_status'] == OrderStatus.FILLED.value
        assert events_received[0]['filled_quantity'] == 1000
        
        logger.info("✓ 订单状态回调测试通过")
    
    def test_trade_event_callback(self, xtp_interface, sample_order, event_bus):
        """测试成交回报回调"""
        xtp_interface._logged_in = True
        xtp_interface._connected = True
        
        # 提交订单
        xtp_interface.submit_order(sample_order)
        
        # 获取exchange_order_id
        exchange_order_id = list(xtp_interface._exchange_order_map.keys())[0]
        
        # 创建模拟的成交信息
        mock_trade_info = Mock()
        mock_trade_info.order_xtp_id = exchange_order_id
        mock_trade_info.price = 105000  # 10.50 * 10000
        mock_trade_info.quantity = 500
        
        # 订阅成交事件
        events_received = []
        def on_order_filled(event_obj):
            events_received.append({
                'order_id': event_obj.order_id,
                'exchange_order_id': event_obj.exchange_order_id,
                'trade_price': event_obj.trade_price,
                'trade_volume': event_obj.trade_volume,
                'trade_amount': event_obj.trade_amount,
                'filled_quantity': event_obj.filled_quantity,
                'remaining_quantity': event_obj.remaining_quantity,
                'avg_price': event_obj.avg_price,
                'order_status': event_obj.order_status
            })
        
        event_bus.subscribe('order_filled', on_order_filled)
        
        # 调用成交回报回调
        xtp_interface._on_trade_event(mock_trade_info)
        
        # 验证成交信息已更新
        assert sample_order.filled_quantity == 500
        assert sample_order.remaining_quantity == 500
        assert sample_order.filled_price == 10.50
        
        # 验证事件已发布
        assert len(events_received) == 1
        assert events_received[0]['order_id'] == "TEST001"
        assert events_received[0]['trade_price'] == 10.50
        assert events_received[0]['trade_volume'] == 500
        assert events_received[0]['filled_quantity'] == 500
        assert events_received[0]['avg_price'] == 10.50
        
        logger.info("✓ 成交回报回调测试通过")
    
    def test_error_event_callback(self, xtp_interface, event_bus):
        """测试错误回调"""
        # 创建模拟的错误信息
        mock_error_info = Mock()
        mock_error_info.error_id = 1
        mock_error_info.error_msg = "连接失败"
        
        # 订阅XTP错误事件
        events_received = []
        def on_xtp_error(event_obj):
            events_received.append({
                'error_id': event_obj.error_id,
                'error_msg': event_obj.error_msg,
                'account_id': event_obj.account_id,
                'timestamp': event_obj.timestamp
            })
        
        event_bus.subscribe('xtp_error', on_xtp_error)
        
        # 调用错误回调
        xtp_interface._on_error_event(mock_error_info)
        
        # 验证事件已发布（仅在EventBus可用时）
        if xtp_interface.event_bus:
            assert len(events_received) >= 1
            assert events_received[0]['error_id'] == 1
            assert events_received[0]['error_msg'] == "连接失败"
            assert events_received[0]['account_id'] == "test_account"
        else:
            # 如果EventBus不可用，事件不会被发布
            logger.info("EventBus不可用，跳过事件发布验证")
        
        logger.info("✓ 错误回调测试通过")
    
    def test_generate_exchange_order_id(self, xtp_interface, sample_order):
        """测试生成交易所订单ID"""
        exchange_order_id = xtp_interface._generate_exchange_order_id(sample_order)
        
        assert exchange_order_id is not None
        assert "XTPPRO" in exchange_order_id
        assert sample_order.order_id[-8:] in exchange_order_id
        
        logger.info(f"✓ 生成交易所订单ID测试通过: {exchange_order_id}")
    
    def test_get_market_type(self, xtp_interface):
        """测试获取市场类型"""
        # 测试上海市场
        sh_market = xtp_interface._get_market_type("600000")
        assert sh_market is not None
        
        # 测试深圳市场
        sz_market = xtp_interface._get_market_type("000001")
        assert sz_market is not None
        
        # 测试创业板
        cyb_market = xtp_interface._get_market_type("300001")
        assert cyb_market is not None
        
        logger.info("✓ 获取市场类型测试通过")
    
    def test_get_order_type(self, xtp_interface):
        """测试获取订单类型"""
        # 测试限价单
        limit_type = xtp_interface._get_order_type(OrderCategory.LIMIT)
        assert limit_type is not None
        
        # 测试市价单
        market_type = xtp_interface._get_order_type(OrderCategory.MARKET)
        assert market_type is not None
        
        logger.info("✓ 获取订单类型测试通过")
    
    def test_get_order_side(self, xtp_interface):
        """测试获取订单方向"""
        # 测试买入
        buy_side = xtp_interface._get_order_side(OrderType.BUY)
        assert buy_side is not None
        
        # 测试卖出
        sell_side = xtp_interface._get_order_side(OrderType.SELL)
        assert sell_side is not None
        
        logger.info("✓ 获取订单方向测试通过")


def run_tests():
    """运行所有测试"""
    logger.info("开始运行XTP Pro交易接口测试...")
    
    # 使用pytest运行测试
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))


if __name__ == "__main__":
    run_tests()
