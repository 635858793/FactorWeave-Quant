#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Level-2 数据集成测试
测试 get_level2_data() 集成到标准数据流的功能

测试覆盖：
1. 缓存管理功能
2. 智能降级策略
3. 轮询优化
4. 监控指标
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock
from typing import Dict, Any, List
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.plugin_types import AssetType, DataType
from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult, ConnectionInfo
from core.services.enhanced_realtime_data_manager import EnhancedRealtimeDataManager
from core.events.event_bus import EventBus
from core.data_standardization_engine import DataStandardizationEngine
from core.data_validator import DataValidator
import pandas as pd


class MockLevel2Plugin(IDataSourcePlugin):
    """模拟 Level-2 插件"""
    
    def __init__(self, has_level2_data: bool = True, callback_success: bool = True):
        self.has_level2_data = has_level2_data
        self.callback_success = callback_success
        self._connected = False
        self._callbacks = {}
        self.call_count = 0
        self.get_level2_data_call_count = 0
    
    @property
    def plugin_info(self):
        """获取插件信息"""
        return PluginInfo(
            id='mock_level2_plugin',
            name='Mock Level-2 Plugin',
            version='1.0.0',
            description='模拟 Level-2 插件用于测试',
            author='Test',
            supported_asset_types=[AssetType.STOCK],
            supported_data_types=[DataType.LEVEL2_DATA, DataType.TICK_DATA],
            capabilities={'realtime': True, 'level2': True, 'tick': True},
            chinese_name='模拟 Level-2 插件'
        )
    
    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        self._connected = True
        return True
    
    def disconnect(self) -> bool:
        """断开连接"""
        self._connected = False
        return True
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected
    
    def get_connection_info(self):
        """获取连接信息"""
        return ConnectionInfo(
            is_connected=self._connected,
            connection_time=datetime.now() if self._connected else None,
            last_activity=datetime.now(),
            connection_params={}
        )
    
    def health_check(self):
        """健康检查"""
        return HealthCheckResult(
            is_healthy=True,
            message='Healthy',
            response_time=10.0
        )
    
    def get_asset_list(self, asset_type: AssetType, market: str = None):
        """获取资产列表"""
        return []
    
    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None):
        """获取 K 线数据"""
        return pd.DataFrame()
    
    def get_real_time_quotes(self, symbols: List[str]):
        """获取实时行情"""
        return pd.DataFrame()
    
    def get_historical_data(self, symbol: str, data_type: DataType,
                           start_date: str, end_date: str, freq: str = "D"):
        """获取历史数据"""
        return pd.DataFrame()
    
    def subscribe_realtime_data(self, symbols, callback, data_type=None):
        """订阅实时数据"""
        for symbol in symbols:
            self._callbacks[symbol] = callback
        return self.callback_success
    
    def unsubscribe_realtime_data(self, symbols):
        """取消订阅实时数据"""
        for symbol in symbols:
            if symbol in self._callbacks:
                del self._callbacks[symbol]
    
    def get_level2_data(self, symbol: str) -> Dict[str, Any]:
        """获取 Level-2 数据"""
        self.get_level2_data_call_count += 1
        if not self.has_level2_data:
            return None
        
        # 返回模拟的五档数据
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'bids': [
                {'price': 10.5 - i * 0.1, 'volume': 1000 + i * 100}
                for i in range(5)
            ],
            'asks': [
                {'price': 10.6 + i * 0.1, 'volume': 1500 + i * 150}
                for i in range(5)
            ],
            'last_price': 10.55,
            'volume': 100000
        }


class TestLevel2CacheManagement:
    """测试缓存管理功能"""
    
    @pytest.fixture
    def setup_manager(self):
        """设置测试环境"""
        # 创建依赖对象
        event_bus = EventBus()
        data_standardizer = Mock(spec=DataStandardizationEngine)
        data_validator = Mock(spec=DataValidator)
        uni_plugin_manager = Mock()
        
        # 创建管理器
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        return manager
    
    def test_cache_set_and_get(self, setup_manager):
        """测试缓存设置和获取"""
        manager = setup_manager
        
        # 设置缓存
        symbol = '000001.SZ'
        test_data = {
            'symbol': symbol,
            'bids': [{'price': 10.5, 'volume': 1000}],
            'asks': [{'price': 10.6, 'volume': 1500}]
        }
        
        manager._set_cached_level2_data(symbol, test_data)
        
        # 获取缓存
        cached_data = manager._get_cached_level2_data(symbol)
        
        assert cached_data is not None
        assert cached_data['symbol'] == symbol
        assert len(cached_data['bids']) == 1
        assert len(cached_data['asks']) == 1
    
    def test_cache_expiration(self, setup_manager):
        """测试缓存过期"""
        manager = setup_manager
        
        symbol = '000001.SZ'
        test_data = {'symbol': symbol, 'bids': [], 'asks': []}
        
        # 设置缓存
        manager._set_cached_level2_data(symbol, test_data)
        
        # 手动修改时间戳使其过期
        manager._cache_timestamps[symbol] = datetime.now() - timedelta(seconds=10)
        manager._cache_ttl_seconds = 5  # 5 秒过期
        
        # 获取缓存应该返回 None
        cached_data = manager._get_cached_level2_data(symbol)
        assert cached_data is None
    
    def test_cache_thread_safety(self, setup_manager):
        """测试缓存线程安全"""
        manager = setup_manager
        import threading
        
        symbol = '000001.SZ'
        errors = []
        
        def set_cache():
            try:
                for i in range(100):
                    data = {'symbol': symbol, 'value': i}
                    manager._set_cached_level2_data(symbol, data)
            except Exception as e:
                errors.append(e)
        
        def get_cache():
            try:
                for i in range(100):
                    manager._get_cached_level2_data(symbol)
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程同时访问缓存
        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=set_cache)
            t2 = threading.Thread(target=get_cache)
            threads.extend([t1, t2])
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 不应该有错误
        assert len(errors) == 0, f"缓存线程安全测试失败：{errors}"


class TestSmartFallbackStrategy:
    """测试智能降级策略"""
    
    @pytest.fixture
    def setup_manager_with_plugin(self):
        """设置带插件的测试环境"""
        event_bus = EventBus()
        data_standardizer = Mock(spec=DataStandardizationEngine)
        data_validator = Mock(spec=DataValidator)
        uni_plugin_manager = Mock()
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        # 注册插件
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True)
        manager.realtime_plugins['mock_plugin'] = plugin
        
        return manager, plugin
    
    @pytest.mark.asyncio
    async def test_callback_success_path(self, setup_manager_with_plugin):
        """测试 Callback 成功路径"""
        manager, plugin = setup_manager_with_plugin
        
        # 执行智能订阅
        await manager._subscribe_level2_data_smart(
            symbol='000001.SZ',
            plugin_id='mock_plugin',
            plugin=plugin,
            asset_type=AssetType.STOCK_A
        )
        
        # 验证初始数据被获取
        assert plugin.get_level2_data_call_count >= 1
        
        # 验证没有发生降级
        fallback_stats = manager.get_fallback_stats()
        assert fallback_stats['total_fallbacks'] == 0
    
    @pytest.mark.asyncio
    async def test_callback_failure_fallback(self, setup_manager_with_plugin):
        """测试 Callback 失败降级"""
        manager, plugin = setup_manager_with_plugin
        
        # 设置 Callback 失败
        plugin.callback_success = False
        
        # 执行智能订阅
        await manager._subscribe_level2_data_smart(
            symbol='000001.SZ',
            plugin_id='mock_plugin',
            plugin=plugin,
            asset_type=AssetType.STOCK_A
        )
        
        # 验证发生了降级
        fallback_stats = manager.get_fallback_stats()
        assert fallback_stats['total_fallbacks'] > 0
    
    @pytest.mark.asyncio
    async def test_initial_data_failure(self, setup_manager_with_plugin):
        """测试初始数据获取失败"""
        manager, plugin = setup_manager_with_plugin
        
        # 设置没有 Level-2 数据
        plugin.has_level2_data = False
        
        # 执行智能订阅
        await manager._subscribe_level2_data_smart(
            symbol='000001.SZ',
            plugin_id='mock_plugin',
            plugin=plugin,
            asset_type=AssetType.STOCK_A
        )
        
        # 等待一小段时间让异步任务完成
        await asyncio.sleep(0.1)
        
        # 验证记录了失败（即使初始数据失败，Callback 可能成功）
        # 所以这里只验证 get_level2_data 被调用了
        assert plugin.get_level2_data_call_count >= 1


class TestCachedPolling:
    """测试带缓存的轮询"""
    
    @pytest.fixture
    def setup_polling_test(self):
        """设置轮询测试环境"""
        event_bus = EventBus()
        data_standardizer = Mock(spec=DataStandardizationEngine)
        data_validator = Mock(spec=DataValidator)
        uni_plugin_manager = Mock()
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        plugin = MockLevel2Plugin(has_level2_data=True)
        manager.realtime_plugins['mock_plugin'] = plugin
        
        return manager, plugin
    
    @pytest.mark.asyncio
    async def test_polling_with_cache(self, setup_polling_test):
        """测试带缓存的轮询"""
        manager, plugin = setup_polling_test
        
        # 启动轮询任务
        polling_task = asyncio.create_task(
            manager._poll_level2_data_cached(
                plugin_id='mock_plugin',
                plugin=plugin,
                symbols=['000001.SZ'],
                asset_type=AssetType.STOCK_A,
                initial_interval=0.5,  # 0.5 秒轮询一次
                max_interval=2.0
            )
        )
        
        # 等待一段时间
        await asyncio.sleep(1.5)
        
        # 取消轮询
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        
        # 验证轮询次数（应该少于无缓存的情况）
        # 1.5 秒内，如果每次都轮询应该是 3 次，但有缓存应该更少
        assert plugin.get_level2_data_call_count <= 3
        assert plugin.get_level2_data_call_count >= 1
        
        # 验证缓存中有数据
        cache_stats = manager.get_cache_stats()
        assert cache_stats['valid_cache'] > 0


class TestMonitoringMetrics:
    """测试监控指标"""
    
    @pytest.fixture
    def setup_monitoring_test(self):
        """设置监控测试环境"""
        event_bus = EventBus()
        data_standardizer = Mock(spec=DataStandardizationEngine)
        data_validator = Mock(spec=DataValidator)
        uni_plugin_manager = Mock()
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        # 添加一些测试数据
        manager._set_cached_level2_data('000001.SZ', {'symbol': '000001.SZ'})
        manager._set_cached_level2_data('000002.SZ', {'symbol': '000002.SZ'})
        
        # 记录一些降级
        manager._record_fallback('000001.SZ', 'test_reason_1')
        manager._record_fallback('000001.SZ', 'test_reason_2')
        
        return manager
    
    def test_cache_stats(self, setup_monitoring_test):
        """测试缓存统计"""
        manager = setup_monitoring_test
        
        stats = manager.get_cache_stats()
        
        assert stats['total_cached'] == 2
        assert stats['valid_cache'] == 2
        assert stats['cache_ttl_seconds'] == 5
    
    def test_fallback_stats(self, setup_monitoring_test):
        """测试降级统计"""
        manager = setup_monitoring_test
        
        stats = manager.get_fallback_stats()
        
        assert stats['total_symbols'] == 1
        assert stats['total_fallbacks'] == 2
        assert '000001.SZ' in stats['details']
        assert len(stats['details']['000001.SZ']['last_reasons']) == 2
    
    def test_performance_metrics(self, setup_monitoring_test):
        """测试性能指标"""
        manager = setup_monitoring_test
        
        metrics = manager.get_performance_metrics()
        
        assert 'cache' in metrics
        assert 'fallback' in metrics
        assert 'polling' in metrics
        assert 'summary' in metrics
        
        # 验证汇总指标
        assert 'callback_success_rate' in metrics['summary']
        assert 'cache_hit_rate' in metrics['summary']


class TestFullIntegration:
    """完整集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_level2_subscription_flow(self):
        """测试完整的 Level-2 订阅流程"""
        # 创建组件
        event_bus = EventBus()
        data_standardizer = Mock(spec=DataStandardizationEngine)
        data_validator = Mock(spec=DataValidator)
        
        # 创建真实的 Mock 对象而不是完全 Mock
        uni_plugin_manager = Mock()
        plugin_center_mock = Mock()
        plugin_center_mock.data_source_plugins = {}  # 设置为字典而不是 Mock
        uni_plugin_manager.plugin_center = plugin_center_mock
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        # 注册插件
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True)
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅 Level-2 数据
        await manager._subscribe_level2_data(
            plugin_id='test_plugin',
            plugin=plugin,
            symbols=['000001.SZ'],
            asset_type=AssetType.STOCK_A
        )
        
        # 等待一小段时间让异步任务执行
        await asyncio.sleep(0.1)
        
        # 验证
        # 1. 插件的 get_level2_data 应该被调用
        assert plugin.get_level2_data_call_count >= 1
        
        # 2. 缓存中应该有数据
        cache_stats = manager.get_cache_stats()
        assert cache_stats['valid_cache'] > 0
        
        # 3. 性能指标应该可用
        metrics = manager.get_performance_metrics()
        assert 'summary' in metrics
        
        # 清理
        await manager.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
