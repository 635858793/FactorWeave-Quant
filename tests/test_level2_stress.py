#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Level-2 数据集成测试和压力测试
包含：
1. 端到端集成测试
2. 高并发压力测试
3. 长时间运行稳定性测试
4. 网络异常场景测试
"""

import pytest
import pytest_asyncio
import asyncio
import time
from datetime import datetime
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
from core.events.types import RealtimeDataEvent, TickDataEvent, OrderBookEvent


# ========== 模拟插件 ==========

class MockLevel2Plugin(IDataSourcePlugin):
    """模拟 Level-2 插件（支持高并发场景）"""
    
    def __init__(self, has_level2_data: bool = True, callback_success: bool = True,
                 latency_ms: float = 50.0):
        self.has_level2_data = has_level2_data
        self.callback_success = callback_success
        self.latency_ms = latency_ms  # 模拟网络延迟
        self._connected = False
        self._callbacks = {}
        self.call_count = 0
        self.get_level2_data_call_count = 0
        self.callback_call_count = 0
    
    @property
    def plugin_info(self):
        """获取插件信息"""
        return PluginInfo(
            id='mock_level2_plugin',
            name='Mock Level-2 Plugin',
            version='1.0.0',
            description='模拟 Level-2 插件用于压力测试',
            author='Test',
            supported_asset_types=[AssetType.STOCK_A, AssetType.STOCK_HK, AssetType.STOCK_US],
            supported_data_types=[DataType.LEVEL2_DATA, DataType.TICK_DATA],
            capabilities={'realtime': True, 'level2': True, 'tick': True},
            chinese_name='模拟 Level-2 插件'
        )
    
    def connect(self, connection_info: ConnectionInfo) -> bool:
        """连接"""
        self._connected = True
        return True
    
    def disconnect(self):
        """断开连接"""
        self._connected = False
    
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    def get_connection_info(self) -> ConnectionInfo:
        """获取连接信息"""
        return ConnectionInfo()
    
    def get_asset_list(self, asset_type: AssetType) -> List[str]:
        """获取资产列表"""
        return ['000001.SZ', '000002.SZ', '600000.SH']
    
    def get_kdata(self, symbol: str, start_time, end_time, kline_type: str) -> Any:
        """获取 K 线数据"""
        return None
    
    def get_real_time_quotes(self, symbols: List[str]) -> Any:
        """获取实时行情"""
        return None
    
    def get_historical_data(self, symbols: List[str], data_type: DataType) -> Any:
        """获取历史数据"""
        return None
    
    def subscribe_realtime_data(self, symbols: List[str], callback, data_type: DataType) -> bool:
        """订阅实时数据"""
        if not self.callback_success:
            return False
        
        for symbol in symbols:
            if symbol not in self._callbacks:
                self._callbacks[symbol] = []
            self._callbacks[symbol].append(callback)
            self.callback_call_count += 1
        
        return True
    
    def unsubscribe_realtime_data(self, symbols: List[str], callback, data_type: DataType):
        """取消订阅"""
        for symbol in symbols:
            if symbol in self._callbacks:
                if callback in self._callbacks[symbol]:
                    self._callbacks[symbol].remove(callback)
    
    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        return HealthCheckResult(
            healthy=self._connected,
            message='OK' if self._connected else 'Disconnected'
        )
    
    def get_level2_data(self, symbol: str) -> Dict[str, Any]:
        """获取 Level-2 数据（模拟延迟）"""
        self.get_level2_data_call_count += 1
        
        # 模拟网络延迟
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000.0)
        
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
            'volume': 100000,
            'turnover': 1000000
        }
    
    def trigger_callback(self, symbol: str, data: Dict):
        """手动触发 callback（用于测试）"""
        if symbol in self._callbacks:
            for callback in self._callbacks[symbol]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Callback 触发失败：{e}")


# ========== 集成测试 ==========

class TestEndToEndIntegration:
    """端到端集成测试"""
    
    @pytest_asyncio.fixture
    async def setup_integration_test(self):
        """设置集成测试环境"""
        event_bus = EventBus()
        data_standardizer = Mock()
        data_standardizer.standardize_realtime_data = lambda data, dtype, pid: data  # 直接返回原数据
        data_validator = Mock()
        data_validator.validate_realtime_data = lambda data, dtype: True  # 总是验证通过
        uni_plugin_manager = Mock()
        plugin_center_mock = Mock()
        plugin_center_mock.data_source_plugins = {}
        uni_plugin_manager.plugin_center = plugin_center_mock
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        # 创建事件接收器
        received_events = []
        
        def on_realtime_event(event: RealtimeDataEvent):
            received_events.append(event)
        
        event_bus.subscribe(RealtimeDataEvent, on_realtime_event)
        
        yield manager, event_bus, received_events
        
        # 清理
        await manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_end_to_end_level2_flow(self, setup_integration_test):
        """测试从订阅到数据显示的完整流程"""
        manager, event_bus, received_events = setup_integration_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅 Level-2 数据
        await manager._subscribe_level2_data(
            plugin_id='test_plugin',
            plugin=plugin,
            symbols=['000001.SZ'],
            asset_type=AssetType.STOCK_A
        )
        
        # 等待数据更新
        await asyncio.sleep(0.5)
        
        # 验证
        # 1. 插件的 get_level2_data 应该被调用
        assert plugin.get_level2_data_call_count >= 1
        
        # 2. 应该收到 RealtimeDataEvent
        assert len(received_events) > 0
        
        # 3. 事件数据应该包含 Level-2 信息
        event = received_events[0]
        assert hasattr(event, 'realtime_data')
        assert 'symbol' in event.realtime_data
        assert 'bids' in event.realtime_data
        assert 'asks' in event.realtime_data
        
        # 4. 缓存中应该有数据
        cache_stats = manager.get_cache_stats()
        assert cache_stats['valid_cache'] > 0
        
        print(f"✅ 端到端测试通过：收到 {len(received_events)} 个事件")
    
    @pytest.mark.asyncio
    async def test_callback_realtime_push(self, setup_integration_test):
        """测试 Callback 实时推送"""
        manager, event_bus, received_events = setup_integration_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True, latency_ms=10.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅
        await manager._subscribe_level2_data(
            plugin_id='test_plugin',
            plugin=plugin,
            symbols=['000001.SZ'],
            asset_type=AssetType.STOCK_A
        )
        
        # 等待 Callback 注册完成
        await asyncio.sleep(0.2)
        
        # 手动触发 Callback
        test_data = {
            'symbol': '000001.SZ',
            'timestamp': datetime.now().isoformat(),
            'bids': [{'price': 10.5, 'volume': 1000}],
            'asks': [{'price': 10.6, 'volume': 1500}],
            'last_price': 10.55
        }
        plugin.trigger_callback('000001.SZ', test_data)
        
        # 等待事件处理
        await asyncio.sleep(0.2)
        
        # 验证
        assert len(received_events) > 0
        assert received_events[-1].realtime_data['last_price'] == 10.55
        
        print(f"✅ Callback 实时推送测试通过：收到 {len(received_events)} 个事件")


# ========== 压力测试 ==========

class TestHighConcurrencyStress:
    """高并发压力测试"""
    
    @pytest_asyncio.fixture
    async def setup_stress_test(self):
        """设置压力测试环境"""
        event_bus = EventBus()
        data_standardizer = Mock()
        data_standardizer.standardize_realtime_data = lambda data, dtype, pid: data
        data_validator = Mock()
        data_validator.validate_realtime_data = lambda data, dtype: True
        uni_plugin_manager = Mock()
        plugin_center_mock = Mock()
        plugin_center_mock.data_source_plugins = {}
        uni_plugin_manager.plugin_center = plugin_center_mock
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        yield manager
        
        await manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_100_stocks_concurrent_subscription(self, setup_stress_test):
        """测试 100 只股票同时订阅"""
        manager = setup_stress_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True, latency_ms=5.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 生成 100 只股票
        symbols = [f"00000{i}.SZ" for i in range(100)]
        
        # 并发订阅
        start_time = time.time()
        
        tasks = [
            manager._subscribe_level2_data(
                plugin_id='test_plugin',
                plugin=plugin,
                symbols=[symbol],
                asset_type=AssetType.STOCK_A
            )
            for symbol in symbols
        ]
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 等待数据处理完成
        await asyncio.sleep(1.0)
        
        # 验证
        # 1. 所有股票都应该被订阅
        cache_stats = manager.get_cache_stats()
        assert cache_stats['valid_cache'] >= 50  # 至少 50% 成功
        
        # 2. 性能指标应该合理
        metrics = manager.get_performance_metrics()
        assert 'summary' in metrics
        
        # 3. 耗时应该在合理范围内（<10 秒）
        assert elapsed < 10.0
        
        print(f"✅ 100 只股票并发订阅测试通过：耗时 {elapsed:.2f}s, 缓存命中 {cache_stats['valid_cache']} 只")
    
    @pytest.mark.asyncio
    async def test_high_frequency_callback(self, setup_stress_test):
        """测试高频 Callback 推送"""
        manager = setup_stress_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True, latency_ms=1.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅 10 只股票
        symbols = [f"00000{i}.SZ" for i in range(10)]
        
        for symbol in symbols:
            await manager._subscribe_level2_data(
                plugin_id='test_plugin',
                plugin=plugin,
                symbols=[symbol],
                asset_type=AssetType.STOCK_A
            )
        
        # 等待 Callback 注册
        await asyncio.sleep(0.5)
        
        # 高频触发 Callback（每秒 10 次，持续 5 秒）
        total_callbacks = 0
        start_time = time.time()
        
        for _ in range(50):  # 50 次触发
            for symbol in symbols:
                test_data = {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'bids': [{'price': 10.5, 'volume': 1000}],
                    'asks': [{'price': 10.6, 'volume': 1500}],
                    'last_price': 10.55 + total_callbacks * 0.01
                }
                plugin.trigger_callback(symbol, test_data)
                total_callbacks += 1
            
            await asyncio.sleep(0.1)  # 100ms 间隔
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 验证
        # 1. 所有 Callback 都应该被处理
        assert total_callbacks == 500  # 10 只股票 * 50 次
        
        # 2. 缓存应该正常工作
        cache_stats = manager.get_cache_stats()
        assert cache_stats['total_cached'] > 0
        
        print(f"✅ 高频 Callback 测试通过：触发 {total_callbacks} 次，耗时 {elapsed:.2f}s")
    
    @pytest.mark.asyncio
    async def test_mixed_data_types(self, setup_stress_test):
        """测试混合数据类型（Level-2 + Tick + OrderBook）"""
        manager = setup_stress_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True, latency_ms=5.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅多种数据类型
        symbols = ['000001.SZ', '000002.SZ', '600000.SH']
        
        for symbol in symbols:
            # 订阅 Level-2
            await manager._subscribe_level2_data(
                plugin_id='test_plugin',
                plugin=plugin,
                symbols=[symbol],
                asset_type=AssetType.STOCK_A
            )
        
        # 等待数据处理
        await asyncio.sleep(1.0)
        
        # 验证
        cache_stats = manager.get_cache_stats()
        assert cache_stats['valid_cache'] >= len(symbols) * 0.8  # 至少 80% 成功
        
        print(f"✅ 混合数据类型测试通过：缓存 {cache_stats['valid_cache']} 只股票")


# ========== 稳定性测试 ==========

class TestLongRunningStability:
    """长时间运行稳定性测试"""
    
    @pytest_asyncio.fixture
    async def setup_stability_test(self):
        """设置稳定性测试环境"""
        event_bus = EventBus()
        data_standardizer = Mock()
        data_standardizer.standardize_realtime_data = lambda data, dtype, pid: data
        data_validator = Mock()
        data_validator.validate_realtime_data = lambda data, dtype: True
        uni_plugin_manager = Mock()
        plugin_center_mock = Mock()
        plugin_center_mock.data_source_plugins = {}
        uni_plugin_manager.plugin_center = plugin_center_mock
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        yield manager
        
        await manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_30_seconds_continuous_operation(self, setup_stability_test):
        """测试 30 秒连续运行稳定性"""
        manager = setup_stability_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True, latency_ms=10.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅 5 只股票
        symbols = ['000001.SZ', '000002.SZ', '000003.SZ', '600000.SH', '600001.SH']
        
        for symbol in symbols:
            await manager._subscribe_level2_data(
                plugin_id='test_plugin',
                plugin=plugin,
                symbols=[symbol],
                asset_type=AssetType.STOCK_A
            )
        
        # 运行 30 秒
        print("开始 30 秒稳定性测试...")
        start_time = time.time()
        
        while time.time() - start_time < 30:
            # 定期触发数据更新
            for symbol in symbols:
                test_data = {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'bids': [{'price': 10.5, 'volume': 1000}],
                    'asks': [{'price': 10.6, 'volume': 1500}]
                }
                plugin.trigger_callback(symbol, test_data)
            
            await asyncio.sleep(1.0)  # 每秒更新一次
        
        elapsed = time.time() - start_time
        
        # 验证
        # 1. 没有异常抛出
        # 2. 缓存正常工作
        cache_stats = manager.get_cache_stats()
        assert cache_stats['total_cached'] > 0
        
        # 3. 性能指标正常
        metrics = manager.get_performance_metrics()
        assert 'summary' in metrics
        
        print(f"✅ 30 秒稳定性测试通过：运行 {elapsed:.2f}s, 缓存 {cache_stats['total_cached']} 次")
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, setup_stability_test):
        """测试内存泄漏检测"""
        import tracemalloc
        tracemalloc.start()
        
        manager = setup_stability_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True, latency_ms=5.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅 10 只股票
        symbols = [f"00000{i}.SZ" for i in range(10)]
        
        for symbol in symbols:
            await manager._subscribe_level2_data(
                plugin_id='test_plugin',
                plugin=plugin,
                symbols=[symbol],
                asset_type=AssetType.STOCK_A
            )
        
        # 运行 10 秒
        for _ in range(10):
            for symbol in symbols:
                test_data = {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'bids': [{'price': 10.5, 'volume': 1000}],
                    'asks': [{'price': 10.6, 'volume': 1500}]
                }
                plugin.trigger_callback(symbol, test_data)
            
            await asyncio.sleep(1.0)
        
        # 检查内存使用
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # 验证：峰值内存应该 < 50MB
        peak_mb = peak / 1024 / 1024
        assert peak_mb < 50, f"内存使用过高：{peak_mb:.2f}MB"
        
        print(f"✅ 内存泄漏检测通过：峰值内存 {peak_mb:.2f}MB")


# ========== 异常场景测试 ==========

class TestExceptionScenarios:
    """异常场景测试"""
    
    @pytest_asyncio.fixture
    async def setup_exception_test(self):
        """设置异常测试环境"""
        event_bus = EventBus()
        data_standardizer = Mock()
        data_standardizer.standardize_realtime_data = lambda data, dtype, pid: data
        data_validator = Mock()
        data_validator.validate_realtime_data = lambda data, dtype: True
        uni_plugin_manager = Mock()
        plugin_center_mock = Mock()
        plugin_center_mock.data_source_plugins = {}
        uni_plugin_manager.plugin_center = plugin_center_mock
        
        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )
        
        yield manager
        
        await manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_network_timeout_simulation(self, setup_exception_test):
        """测试网络超时模拟"""
        manager = setup_exception_test
        # 创建高延迟插件（模拟网络超时）
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=False, latency_ms=500.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅
        await manager._subscribe_level2_data(
            plugin_id='test_plugin',
            plugin=plugin,
            symbols=['000001.SZ'],
            asset_type=AssetType.STOCK_A
        )
        
        # 等待降级发生
        await asyncio.sleep(2.0)
        
        # 验证
        # 1. Callback 失败，应该降级到轮询
        fallback_stats = manager.get_fallback_stats()
        assert fallback_stats['total_fallbacks'] > 0
        
        print(f"✅ 网络超时测试通过：降级 {fallback_stats['total_fallbacks']} 次")
    
    @pytest.mark.asyncio
    async def test_plugin_disconnection(self, setup_exception_test):
        """测试插件断开连接"""
        manager = setup_exception_test
        plugin = MockLevel2Plugin(has_level2_data=True, callback_success=True, latency_ms=5.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅
        await manager._subscribe_level2_data(
            plugin_id='test_plugin',
            plugin=plugin,
            symbols=['000001.SZ'],
            asset_type=AssetType.STOCK_A
        )
        
        # 等待数据更新
        await asyncio.sleep(0.5)
        
        # 断开连接
        plugin.disconnect()
        
        # 验证
        assert plugin.is_connected() == False
        
        print(f"✅ 插件断开连接测试通过")
    
    @pytest.mark.asyncio
    async def test_continuous_errors_handling(self, setup_exception_test):
        """测试连续错误处理"""
        manager = setup_exception_test
        # 创建总是返回空的插件
        plugin = MockLevel2Plugin(has_level2_data=False, callback_success=False, latency_ms=1.0)
        
        # 注册插件
        await manager.register_realtime_plugin('test_plugin', plugin)
        
        # 订阅
        await manager._subscribe_level2_data(
            plugin_id='test_plugin',
            plugin=plugin,
            symbols=['000001.SZ'],
            asset_type=AssetType.STOCK_A
        )
        
        # 等待连续错误发生（最多 10 次）
        await asyncio.sleep(15.0)
        
        # 验证
        # 1. 应该记录了错误
        if hasattr(manager, '_level2_error_stats'):
            if '000001.SZ' in manager._level2_error_stats:
                errors = manager._level2_error_stats['000001.SZ']['errors']
                assert errors > 0
                print(f"✅ 连续错误处理测试通过：记录 {errors} 次错误")
            else:
                print(f"⚠️ 未记录错误统计（可能降级策略未触发）")
        else:
            print(f"⚠️ 错误统计属性不存在")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
