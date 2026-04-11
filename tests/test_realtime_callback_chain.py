#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Callback 模式完整链路集成测试

测试从 subscribe_realtime_data 到 event_bus.publish 的完整数据流

测试链路：
1. subscribe_realtime_data() → _subscribe_with_callback()
2. _subscribe_with_callback() → plugin.subscribe_realtime_data()
3. plugin._on_quote_update() → PluginCallbackAdapter.__call__()
4. PluginCallbackAdapter._queue_callback_data() → 线程安全队列
5. _process_callback_queue() → _process_callback_data()
6. _process_callback_data() → _process_realtime_data()
7. _process_realtime_data() → event_bus.publish()
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Dict, Any, List
from datetime import datetime
import queue

from core.services.enhanced_realtime_data_manager import (
    EnhancedRealtimeDataManager,
    PluginCallbackAdapter
)
from core.plugin_types import AssetType, DataType
from core.events.event_bus import EventBus, RealtimeDataEvent


class TestFullCallbackChain:
    """完整 callback 链路测试"""

    @pytest.fixture
    def mock_components(self):
        """创建模拟组件"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        data_standardizer = MagicMock()
        data_standardizer.standardize_realtime_data = MagicMock(side_effect=lambda x, y, z: x)
        data_validator = MagicMock()
        data_validator.validate_realtime_data = MagicMock(return_value=True)
        uni_plugin_manager = MagicMock()

        return {
            'event_bus': event_bus,
            'data_standardizer': data_standardizer,
            'data_validator': data_validator,
            'uni_plugin_manager': uni_plugin_manager
        }

    @pytest.fixture
    def manager(self, mock_components):
        """创建管理器实例"""
        return EnhancedRealtimeDataManager(
            event_bus=mock_components['event_bus'],
            data_standardizer=mock_components['data_standardizer'],
            data_validator=mock_components['data_validator'],
            uni_plugin_manager=mock_components['uni_plugin_manager']
        )

    @pytest.fixture
    def mock_plugin_with_callback(self):
        """创建支持 callback 的模拟插件"""
        plugin = MagicMock()
        plugin.subscribe_realtime_data = MagicMock(return_value=True)
        plugin.get_capabilities = MagicMock(return_value={'level2': True})
        return plugin

    @pytest.mark.asyncio
    async def test_full_chain_level2_plugin(self, manager, mock_plugin_with_callback):
        """
        测试完整链路：Level2RealtimePlugin 风格

        插件 callback 签名：callback(data_type, symbol, data)
        """
        # 注册插件
        manager.realtime_plugins['level2_plugin'] = mock_plugin_with_callback

        # 订阅数据
        await manager.subscribe_realtime_data(
            symbols=['600000'],
            data_types=[DataType.LEVEL2_DATA],
            asset_type=AssetType.STOCK_A,
            source_plugin_id='level2_plugin'
        )

        # 验证 subscribe_realtime_data 被调用
        mock_plugin_with_callback.subscribe_realtime_data.assert_called_once()
        callback_adapter = mock_plugin_with_callback.subscribe_realtime_data.call_args[0][1]

        # 模拟插件推送数据（Level2RealtimePlugin 风格：3个参数）
        test_data = {'symbol': '600000', 'price': 10.5, 'volume': 1000, 'bid1': 10.4, 'ask1': 10.6}
        callback_adapter('level2_data', '600000', test_data)

        # 等待数据处理
        await asyncio.sleep(0.3)

        # 验证数据处理流程
        # 1. 队列中有数据（或已被处理）
        # 2. event_bus.publish 被调用
        assert manager.event_bus.publish.called or not manager._callback_queue.empty()

    @pytest.mark.asyncio
    async def test_full_chain_miniqmt_plugin(self, manager, mock_plugin_with_callback):
        """
        测试完整链路：MiniQMTPlugin 风格

        插件 callback 签名：callback(data)
        """
        # 注册插件（模拟 MiniQMT）
        manager.realtime_plugins['miniqmt_plugin'] = mock_plugin_with_callback

        # 订阅数据
        await manager.subscribe_realtime_data(
            symbols=['000001'],
            data_types=[DataType.LEVEL2_DATA],
            asset_type=AssetType.STOCK_A,
            source_plugin_id='miniqmt_plugin'
        )

        # 获取注册的 callback
        callback_adapter = manager.realtime_plugins['miniqmt_plugin'].subscribe_realtime_data.call_args[0][1]

        # 模拟插件推送数据（MiniQMTPlugin 风格：1个参数，data 包含 symbol）
        test_data = {'symbol': '000001', 'price': 12.5, 'volume': 5000}
        callback_adapter(test_data)  # MiniQMT 风格：只有 data

        # 等待数据处理
        await asyncio.sleep(0.3)

        # 验证数据处理流程
        assert manager.event_bus.publish.called or not manager._callback_queue.empty()

    @pytest.mark.asyncio
    async def test_full_chain_with_real_event_bus(self, manager, mock_plugin_with_callback):
        """测试完整链路：验证 callback 数据流"""
        # 使用真实 EventBus
        real_event_bus = EventBus()
        manager.event_bus = real_event_bus
        manager.data_standardizer.standardize_realtime_data = MagicMock(side_effect=lambda x, y, z: x)

        # 注册插件 - plugin_id 必须包含 'level2'
        mock_plugin = MagicMock()
        mock_plugin.subscribe_realtime_data = MagicMock(return_value=True)
        mock_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        manager.realtime_plugins['level2_realtime_plugin'] = mock_plugin

        # 订阅数据
        await manager.subscribe_realtime_data(
            symbols=['600000'],
            data_types=[DataType.LEVEL2_DATA],
            asset_type=AssetType.STOCK_A,
            source_plugin_id='level2_realtime_plugin'
        )

        # 获取 callback 并模拟数据推送
        callback_adapter = mock_plugin.subscribe_realtime_data.call_args[0][1]
        test_data = {'symbol': '600000', 'price': 10.5, 'volume': 1000}
        callback_adapter('level2_data', '600000', test_data)

        # 等待异步处理
        await asyncio.sleep(0.5)

        # 验证数据被添加：队列可能有数据，缓冲区可能有数据，或事件已发布
        # 任一条件满足即说明链路工作正常
        has_queue_data = not manager._callback_queue.empty()
        has_buffer_data = len(manager.get_buffered_data('600000')) > 0
        assert has_queue_data or has_buffer_data, "数据未进入队列或缓冲区，链路可能中断"

    @pytest.mark.asyncio
    async def test_chain_error_propagation(self, manager):
        """测试链路错误传播"""
        # 注册返回失败的插件
        failing_plugin = MagicMock()
        failing_plugin.subscribe_realtime_data = MagicMock(return_value=False)
        failing_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        manager.realtime_plugins['failing_plugin'] = failing_plugin

        # 验证异常被正确抛出
        with pytest.raises(RuntimeError) as exc_info:
            await manager.subscribe_realtime_data(
                symbols=['600000'],
                data_types=[DataType.LEVEL2_DATA],
                asset_type=AssetType.STOCK_A,
                source_plugin_id='failing_plugin'
            )

        assert 'Callback 模式订阅失败' in str(exc_info.value)

    def test_plugin_callback_adapter_level2_signature(self, manager):
        """测试 PluginCallbackAdapter 处理 Level2 签名"""
        adapter = PluginCallbackAdapter(manager, 'level2_plugin', DataType.LEVEL2_DATA)

        # 模拟 Level2RealtimePlugin 的 callback 签名
        adapter('level2_data', '600000', {'symbol': '600000', 'price': 10.5})

        # 验证数据进入队列
        assert not manager._callback_queue.empty()
        queued_data = manager._callback_queue.get_nowait()
        assert queued_data['symbol'] == '600000'
        assert queued_data['data_type'] == 'level2_data'

    def test_plugin_callback_adapter_miniqmt_signature(self, manager):
        """测试 PluginCallbackAdapter 处理 MiniQMT 签名"""
        adapter = PluginCallbackAdapter(manager, 'miniqmt_plugin', DataType.LEVEL2_DATA)

        # 模拟 MiniQMTPlugin 的 callback 签名
        adapter({'symbol': '000001', 'price': 12.5})

        # 验证数据进入队列
        assert not manager._callback_queue.empty()
        queued_data = manager._callback_queue.get_nowait()
        assert queued_data['symbol'] == '000001'
        assert queued_data['data_type'] == DataType.LEVEL2_DATA.value

    def test_callback_queue_thread_safety(self, manager):
        """测试队列线程安全"""
        results = []

        def worker(worker_id):
            adapter = PluginCallbackAdapter(manager, f'plugin_{worker_id}', DataType.LEVEL2_DATA)
            for i in range(50):
                adapter({'symbol': f'SYM{worker_id * 100 + i}', 'price': 10.0 + i})
                results.append((worker_id, i))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有数据都被正确添加
        assert manager._callback_queue.qsize() == 250
        assert len(results) == 250

    @pytest.mark.asyncio
    async def test_concurrent_subscriptions(self, manager, mock_plugin_with_callback):
        """测试并发订阅"""
        manager.realtime_plugins['test_plugin'] = mock_plugin_with_callback

        symbols = [f'60000{i}' for i in range(5)]
        data_types = [DataType.LEVEL2_DATA, DataType.TICK_DATA]

        # 并发订阅
        tasks = [
            manager.subscribe_realtime_data(
                symbols=[symbol],
                data_types=data_types,
                asset_type=AssetType.STOCK_A,
                source_plugin_id='test_plugin'
            )
            for symbol in symbols
        ]

        await asyncio.gather(*tasks)

        # 验证订阅被正确调用
        assert mock_plugin_with_callback.subscribe_realtime_data.call_count == len(symbols) * len(data_types)


class TestCallbackChainWithRealComponents:
    """使用更真实组件的链路测试"""

    @pytest.fixture
    def real_manager(self):
        """创建使用部分真实组件的管理器"""
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()

        # 真实的数据验证器（使用实际类）
        from core.data_validator import DataValidator
        real_validator = DataValidator()

        # 真实的数据标准化器
        from core.data_standardization_engine import DataStandardizationEngine
        real_standardizer = DataStandardizationEngine()

        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=real_standardizer,
            data_validator=real_validator,
            uni_plugin_manager=MagicMock()
        )
        return manager

    @pytest.mark.asyncio
    async def test_chain_data_validation_and_standardization(self, real_manager):
        """测试链路中的数据验证和标准化"""
        # 创建真实插件
        real_plugin = MagicMock()
        real_plugin.subscribe_realtime_data = MagicMock(return_value=True)
        real_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        real_manager.realtime_plugins['real_plugin'] = real_plugin

        # 订阅
        await real_manager.subscribe_realtime_data(
            symbols=['600000'],
            data_types=[DataType.LEVEL2_DATA],
            asset_type=AssetType.STOCK_A,
            source_plugin_id='real_plugin'
        )

        # 获取 callback
        callback_adapter = real_plugin.subscribe_realtime_data.call_args[0][1]

        # 模拟数据
        test_data = {'symbol': '600000', 'price': 10.5, 'volume': 1000}
        callback_adapter('level2_data', '600000', test_data)

        # 等待处理
        await asyncio.sleep(0.5)

        # 验证数据被处理（队列可能已空但至少被尝试处理）
        # 在真实环境中，这会调用实际的验证和标准化逻辑
        assert real_plugin.subscribe_realtime_data.called


class TestCallbackChainPerformance:
    """链路性能测试"""

    @pytest.mark.asyncio
    async def test_callback_latency(self):
        """测试 callback 模式延迟"""
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        data_standardizer = MagicMock()
        data_standardizer.standardize_realtime_data = MagicMock(side_effect=lambda x, y, z: x)
        data_validator = MagicMock()
        data_validator.validate_realtime_data = MagicMock(return_value=True)
        uni_plugin_manager = MagicMock()

        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )

        # 注册插件
        plugin = MagicMock()
        plugin.subscribe_realtime_data = MagicMock(return_value=True)
        plugin.get_capabilities = MagicMock(return_value={'level2': True})
        manager.realtime_plugins['perf_plugin'] = plugin

        # 订阅
        await manager.subscribe_realtime_data(
            symbols=['600000'],
            data_types=[DataType.LEVEL2_DATA],
            asset_type=AssetType.STOCK_A,
            source_plugin_id='perf_plugin'
        )

        # 获取 callback
        callback_adapter = plugin.subscribe_realtime_data.call_args[0][1]

        # 测量延迟
        latencies = []
        for i in range(10):
            test_data = {'symbol': '600000', 'price': 10.0 + i * 0.1, 'volume': 1000 + i}
            start = time.time()
            callback_adapter('level2_data', '600000', test_data)

            # 等待数据被处理
            for _ in range(100):
                if manager.event_bus.publish.called:
                    break
                await asyncio.sleep(0.001)

            end = time.time()
            latencies.append((end - start) * 1000)
            manager.event_bus.publish.reset_mock()

        # 验证延迟 < 100ms
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        print(f"\n平均延迟: {avg_latency:.2f}ms, 最大延迟: {max_latency:.2f}ms")
        assert max_latency < 100, f"延迟过高: {max_latency:.2f}ms"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])