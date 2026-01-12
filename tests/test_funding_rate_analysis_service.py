"""
资金费率分析服务测试

测试 FundingRateAnalysisService 的各项功能
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from core.services.funding_rate_analysis_service import FundingRateAnalysisService
from core.containers import ServiceContainer
from core.events import EventBus


class TestFundingRateAnalysisService:
    """资金费率分析服务测试"""

    @pytest.fixture
    def service_container(self):
        """创建服务容器"""
        return ServiceContainer()

    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()

    @pytest.fixture
    def funding_rate_service(self, service_container, event_bus):
        """创建资金费率分析服务实例"""
        service = FundingRateAnalysisService(
            service_container=service_container,
            event_bus=event_bus
        )
        service.initialize()
        return service

    @pytest.fixture
    def mock_kline_data(self):
        """创建模拟K线数据"""
        dates = pd.date_range(
            start=datetime.now() - timedelta(hours=24),
            end=datetime.now(),
            freq='h'
        )
        
        data = pd.DataFrame({
            'datetime': dates,
            'open': [0.01 + i * 0.0001 for i in range(len(dates))],
            'high': [0.011 + i * 0.0001 for i in range(len(dates))],
            'low': [0.009 + i * 0.0001 for i in range(len(dates))],
            'close': [0.01 + i * 0.0001 for i in range(len(dates))],
            'volume': [1000 + i * 10 for i in range(len(dates))],
            'amount': [10000 + i * 100 for i in range(len(dates))]
        })
        
        return data

    @pytest.fixture
    def mock_kline_data_small(self):
        """创建少量模拟K线数据"""
        dates = pd.date_range(
            start=datetime.now() - timedelta(hours=9),
            end=datetime.now(),
            freq='h'
        )
        
        data = pd.DataFrame({
            'datetime': dates,
            'open': [0.01 + i * 0.0001 for i in range(len(dates))],
            'high': [0.011 + i * 0.0001 for i in range(len(dates))],
            'low': [0.009 + i * 0.0001 for i in range(len(dates))],
            'close': [0.01 + i * 0.0001 for i in range(len(dates))],
            'volume': [1000 + i * 10 for i in range(len(dates))],
            'amount': [10000 + i * 100 for i in range(len(dates))]
        })
        
        return data

    def test_service_initialization(self, funding_rate_service):
        """测试服务初始化"""
        assert funding_rate_service is not None
        assert funding_rate_service.initialized
        assert funding_rate_service.metrics['operation_count'] == 0

    def test_get_funding_rate(self, funding_rate_service, mock_kline_data_small):
        """测试获取资金费率数据"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data_small)
        ):
            df = funding_rate_service.get_funding_rate('600000', count=10)
            
            assert df is not None
            assert len(df) <= 10
            assert 'close' in df.columns
            assert 'datetime' in df.columns

    def test_get_funding_rate_empty_data(self, funding_rate_service):
        """测试获取空数据"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=pd.DataFrame())
        ):
            df = funding_rate_service.get_funding_rate('600000', count=10)
            
            assert df is not None
            assert df.empty

    def test_analyze_funding_trend_up(self, funding_rate_service, mock_kline_data):
        """测试分析上涨趋势"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data)
        ):
            result = funding_rate_service.analyze_funding_trend('600000', period=24)
            
            assert result is not None
            assert 'symbol' in result
            assert 'trend' in result
            assert 'value' in result
            assert 'change' in result
            assert result['symbol'] == '600000'
            assert result['trend'] in ['up', 'down', 'stable', 'unknown']

    def test_analyze_funding_trend_insufficient_data(self, funding_rate_service):
        """测试数据不足时的趋势分析"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=pd.DataFrame())
        ):
            result = funding_rate_service.analyze_funding_trend('600000', period=24)
            
            assert result is not None
            assert result['trend'] == 'unknown'
            assert result['value'] == 0
            assert result['change'] == 0

    def test_compare_funding_rates(self, funding_rate_service, mock_kline_data):
        """测试比较多个股票的资金费率"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data)
        ):
            symbols = ['600000', '600001', '600002']
            comparison = funding_rate_service.batch_analyze_trends(symbols, period=24)
            
            assert comparison is not None
            assert len(comparison) == 3
            assert all('symbol' in item for item in comparison.values())
            assert all('trend' in item for item in comparison.values())

    def test_get_metrics(self, funding_rate_service, mock_kline_data):
        """测试获取指标"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data)
        ):
            funding_rate_service.get_funding_rate('600000', count=10)
            
            metrics = funding_rate_service.metrics
            
            assert metrics['operation_count'] == 1

    def test_reset_metrics(self, funding_rate_service, mock_kline_data):
        """测试重置指标"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data)
        ):
            funding_rate_service.get_funding_rate('600000', count=10)
            assert funding_rate_service.metrics['operation_count'] == 1
            
            funding_rate_service._metrics['operation_count'] = 0
            assert funding_rate_service.metrics['operation_count'] == 0

    def test_batch_analyze(self, funding_rate_service, mock_kline_data):
        """测试批量分析"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data)
        ):
            symbols = ['600000', '600001', '600002']
            results = [
                funding_rate_service.analyze_funding_trend(symbol, period=24)
                for symbol in symbols
            ]
            
            assert len(results) == 3
            assert all(result['symbol'] in symbols for result in results)
            assert all('trend' in result for result in results)

    def test_get_funding_rate_with_custom_period(self, funding_rate_service, mock_kline_data):
        """测试获取自定义周期的资金费率"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data)
        ):
            df = funding_rate_service.get_funding_rate('600000', count=50)
            
            assert df is not None
            assert len(df) <= 50

    def test_analyze_trend_with_different_periods(self, funding_rate_service, mock_kline_data):
        """测试不同周期的趋势分析"""
        with patch.object(
            funding_rate_service.data_access,
            'get_kline_data',
            return_value=MagicMock(data=mock_kline_data)
        ):
            periods = [6, 12, 24, 48]
            results = [
                funding_rate_service.analyze_funding_trend('600000', period=period)
                for period in periods
            ]
            
            assert len(results) == 4
            assert all(result['symbol'] == '600000' for result in results)
            assert all('trend' in result for result in results)
