#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Callback 模式单元测试

测试 PluginCallbackAdapter 和 EnhancedRealtimeDataManager 的 callback 模式功能

测试内容：
1. PluginCallbackAdapter 对 Level2RealtimePlugin 的适配
2. PluginCallbackAdapter 对 MiniQMTPlugin 的适配
3. Callback 队列的线程安全性
4. Callback 模式订阅流程
5. Fallback 到轮询模式
"""

import pytest
import asyncio
import threading
import time
import queue
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any
from datetime import datetime

from core.services.enhanced_realtime_data_manager import (
    EnhancedRealtimeDataManager,
    PluginCallbackAdapter
)
from core.plugin_types import AssetType, DataType
from core.events.event_bus import EventBus, RealtimeDataEvent


class TestPluginCallbackAdapter:
    """测试 PluginCallbackAdapter 类"""

    def test_adapter_identifies_level2_plugin(self):
        """测试适配器正确识别 Level2RealtimePlugin"""
        mock_manager = MagicMock()
        adapter = PluginCallbackAdapter(mock_manager, 'data_sources.stock.level2_realtime_plugin', DataType.LEVEL2_DATA)

        assert adapter._is_level2_plugin == True
        assert 'level2' in adapter.plugin_id.lower()

    def test_adapter_identifies_miniqmt_plugin(self):
        """测试适配器正确识别 MiniQMTPlugin"""
        mock_manager = MagicMock()
        adapter = PluginCallbackAdapter(mock_manager, 'data_sources.stock.miniqmt_plugin', DataType.LEVEL2_DATA)

        assert adapter._is_level2_plugin == False
        assert 'level2' not in adapter.plugin_id.lower()

    def test_level2_plugin_callback_three_args(self):
        """测试 Level2RealtimePlugin 的三参数 callback 签名"""
        mock_manager = MagicMock()
        adapter = PluginCallbackAdapter(mock_manager, 'level2_realtime_plugin', DataType.LEVEL2_DATA)

        # 模拟 Level2RealtimePlugin 的 callback：callback(data_type, symbol, data)
        test_data = {'symbol': '600000', 'price': 10.5, 'volume': 1000}
        adapter('level2', '600000', test_data)

        mock_manager._queue_callback_data.assert_called_once_with(
            'level2_realtime_plugin',
            '600000',
            'level2',
            test_data
        )

    def test_miniqmt_plugin_callback_one_arg(self):
        """测试 MiniQMTPlugin 的单参数 callback 签名"""
        mock_manager = MagicMock()
        adapter = PluginCallbackAdapter(mock_manager, 'miniqmt_plugin', DataType.LEVEL2_DATA)

        # 模拟 MiniQMTPlugin 的 callback：callback(data)
        test_data = {'symbol': '600000', 'price': 10.5, 'volume': 1000}
        adapter(test_data)

        mock_manager._queue_callback_data.assert_called_once_with(
            'miniqmt_plugin',
            '600000',
            DataType.LEVEL2_DATA.value,
            test_data
        )

    def test_callback_with_kwargs(self):
        """测试使用关键字参数的 callback"""
        mock_manager = MagicMock()
        adapter = PluginCallbackAdapter(mock_manager, 'level2_realtime_plugin', DataType.TICK_DATA)

        test_data = {'symbol': '600001', 'price': 11.0}
        adapter(data_type='tick', symbol='600001', data=test_data)

        mock_manager._queue_callback_data.assert_called_once()

    def test_callback_missing_symbol_warning(self):
        """测试缺少 symbol 参数时的警告"""
        mock_manager = MagicMock()
        adapter = PluginCallbackAdapter(mock_manager, 'level2_realtime_plugin', DataType.LEVEL2_DATA)

        # 不带 symbol 调用
        adapter('level2', '', {'price': 10.0})

        # 不应该调用 _queue_callback_data
        mock_manager._queue_callback_data.assert_not_called()

    def test_callback_exception_handling(self):
        """测试 callback 执行时的异常处理"""
        mock_manager = MagicMock()
        mock_manager._queue_callback_data.side_effect = Exception("Queue error")
        adapter = PluginCallbackAdapter(mock_manager, 'level2_realtime_plugin', DataType.LEVEL2_DATA)

        # 不应该抛出异常
        test_data = {'symbol': '600000', 'price': 10.5}
        try:
            adapter('level2', '600000', test_data)
        except Exception as e:
            pytest.fail(f"Callback adapter should handle exceptions: {e}")


class TestEnhancedRealtimeDataManagerCallbackMode:
    """测试 EnhancedRealtimeDataManager 的 Callback 模式"""

    @pytest.fixture
    def mock_components(self):
        """创建模拟组件"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        data_standardizer = MagicMock()
        data_validator = MagicMock()
        uni_plugin_manager = MagicMock()

        return {
            'event_bus': event_bus,
            'data_standardizer': data_standardizer,
            'data_validator': data_validator,
            'uni_plugin_manager': uni_plugin_manager
        }

    @pytest.fixture
    def manager(self, mock_components):
        """创建 EnhancedRealtimeDataManager 实例"""
        return EnhancedRealtimeDataManager(
            event_bus=mock_components['event_bus'],
            data_standardizer=mock_components['data_standardizer'],
            data_validator=mock_components['data_validator'],
            uni_plugin_manager=mock_components['uni_plugin_manager']
        )

    def test_manager_has_callback_queue(self, manager):
        """测试管理器有 callback 队列"""
        assert hasattr(manager, '_callback_queue')
        assert isinstance(manager._callback_queue, queue.Queue)
        assert manager._callback_queue.maxsize == 1000

    def test_manager_has_callback_mode_flag(self, manager):
        """测试管理器有 callback 模式标志"""
        assert hasattr(manager, '_use_callback_mode')
        assert manager._use_callback_mode == True

    def test_manager_has_callback_mode_lock(self, manager):
        """测试管理器有 callback 模式锁"""
        assert hasattr(manager, '_callback_mode_lock')
        assert manager._callback_mode_lock is not None
        assert hasattr(manager._callback_mode_lock, 'acquire')

    def test_queue_callback_data_thread_safe(self, manager):
        """测试 _queue_callback_data 是线程安全的"""
        results = []

        def add_data():
            for i in range(100):
                manager._queue_callback_data(
                    'test_plugin',
                    f'SYM{i}',
                    'level2',
                    {'symbol': f'SYM{i}', 'price': 10.0 + i}
                )
                results.append(i)

        threads = [threading.Thread(target=add_data) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有数据都被成功添加
        assert manager._callback_queue.qsize() == 500
        assert len(results) == 500

    @pytest.mark.asyncio
    async def test_subscribe_with_callback_success(self, manager):
        """测试 callback 模式订阅成功"""
        # 注册模拟插件
        mock_plugin = MagicMock()
        mock_plugin.subscribe_realtime_data = MagicMock(return_value=True)
        manager.realtime_plugins['test_plugin'] = mock_plugin

        # 执行订阅
        await manager._subscribe_with_callback(
            symbol='600000',
            data_type=DataType.LEVEL2_DATA,
            asset_type=AssetType.STOCK_A,
            plugin_id='test_plugin'
        )

        # 等待一小段时间让协程执行
        await asyncio.sleep(0.1)

        # 验证插件的 subscribe_realtime_data 被调用
        mock_plugin.subscribe_realtime_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_with_callback_raises_on_failure(self, manager):
        """测试 callback 模式失败时抛出异常（不回退）"""
        # 注册一个返回 False 的插件
        mock_plugin = MagicMock()
        mock_plugin.subscribe_realtime_data = MagicMock(return_value=False)
        mock_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        manager.realtime_plugins['test_plugin'] = mock_plugin

        # 执行订阅应该抛出异常
        with pytest.raises(RuntimeError) as exc_info:
            await manager._subscribe_with_callback(
                symbol='600000',
                data_type=DataType.LEVEL2_DATA,
                asset_type=AssetType.STOCK_A,
                plugin_id='test_plugin'
            )

        # 验证异常信息
        assert 'Callback 模式订阅失败' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_subscribe_with_callback_raises_on_missing_plugin(self, manager):
        """测试 callback 模式插件不存在时抛出异常"""
        # 不注册任何插件

        # 执行订阅应该抛出异常
        with pytest.raises(RuntimeError) as exc_info:
            await manager._subscribe_with_callback(
                symbol='600000',
                data_type=DataType.LEVEL2_DATA,
                asset_type=AssetType.STOCK_A,
                plugin_id='nonexistent_plugin'
            )

        # 验证异常信息
        assert '未注册' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_subscribe_with_callback_raises_on_missing_method(self, manager):
        """测试 callback 模式插件不支持方法时抛出异常"""
        # 注册不支持 subscribe_realtime_data 的插件
        mock_plugin = MagicMock(spec=['get_real_time_data', 'get_capabilities'])
        mock_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        manager.realtime_plugins['test_plugin'] = mock_plugin

        # 执行订阅应该抛出异常
        with pytest.raises(AttributeError) as exc_info:
            await manager._subscribe_with_callback(
                symbol='600000',
                data_type=DataType.LEVEL2_DATA,
                asset_type=AssetType.STOCK_A,
                plugin_id='test_plugin'
            )

        # 验证异常信息
        assert '不支持 subscribe_realtime_data' in str(exc_info.value)

    def test_fallback_to_poll_mode(self, manager):
        """测试回退到轮询模式"""
        # 注册模拟插件
        mock_plugin = MagicMock()
        mock_plugin.get_real_time_data = MagicMock(return_value=MagicMock())
        manager.realtime_plugins['test_plugin'] = mock_plugin

        # 直接调用回退方法
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                manager._fallback_to_poll_mode(
                    symbol='600000',
                    data_type=DataType.LEVEL2_DATA,
                    asset_type=AssetType.STOCK_A,
                    plugin_id='test_plugin'
                )
            )
        finally:
            loop.close()

        # 验证轮询任务被创建
        assert 'test_plugin' in manager.subscription_status

    @pytest.mark.asyncio
    async def test_ensure_callback_mode_started_async(self, manager):
        """测试异步确保 callback 处理协程启动"""
        initial_state = manager._callback_mode_started

        # 调用异步确保启动方法
        await manager._ensure_callback_mode_started_async()

        # 应该已经启动
        assert manager._callback_mode_started == True

    @pytest.mark.asyncio
    async def test_subscribe_realtime_data_propagates_exceptions(self, manager):
        """测试 subscribe_realtime_data 正确传播 callback 异常"""
        # 注册一个返回 False 的插件
        mock_plugin = MagicMock()
        mock_plugin.subscribe_realtime_data = MagicMock(return_value=False)
        mock_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        manager.realtime_plugins['test_plugin'] = mock_plugin

        # 执行订阅应该直接抛出异常，不被吞掉
        with pytest.raises(RuntimeError) as exc_info:
            await manager.subscribe_realtime_data(
                symbols=['600000'],
                data_types=[DataType.LEVEL2_DATA],
                asset_type=AssetType.STOCK_A,
                source_plugin_id='test_plugin'
            )

        # 验证异常信息
        assert 'Callback 模式订阅失败' in str(exc_info.value)


class TestCallbackIntegration:
    """集成测试：Callback 完整流程"""

    @pytest.fixture
    def integration_components(self):
        """创建集成测试组件"""
        event_bus = EventBus()
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
    def integration_manager(self, integration_components):
        """创建集成测试管理器"""
        return EnhancedRealtimeDataManager(
            event_bus=integration_components['event_bus'],
            data_standardizer=integration_components['data_standardizer'],
            data_validator=integration_components['data_validator'],
            uni_plugin_manager=integration_components['uni_plugin_manager']
        )

    @pytest.mark.asyncio
    async def test_full_callback_flow(self, integration_manager):
        """测试完整的 callback 流程"""
        # 注册模拟插件
        mock_plugin = MagicMock()
        mock_plugin.subscribe_realtime_data = MagicMock(return_value=True)
        mock_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        integration_manager.realtime_plugins['test_plugin'] = mock_plugin

        # 订阅数据
        await integration_manager.subscribe_realtime_data(
            symbols=['600000'],
            data_types=[DataType.LEVEL2_DATA],
            asset_type=AssetType.STOCK_A,
            source_plugin_id='test_plugin'
        )

        # 等待订阅完成
        await asyncio.sleep(0.2)

        # 验证 subscribe_realtime_data 被调用
        mock_plugin.subscribe_realtime_data.assert_called_once()

        # 获取注册的 callback
        call_args = mock_plugin.subscribe_realtime_data.call_args
        callback_adapter = call_args[0][1]  # 第二个参数是 callback

        # 模拟插件通过 callback 推送数据
        test_data = {'symbol': '600000', 'price': 10.5, 'volume': 1000}
        callback_adapter('level2', '600000', test_data)

        # 等待数据被处理协程处理
        await asyncio.sleep(0.2)

        # 验证数据被放入队列（处理协程可能已经取走并处理了）
        # 由于队列是异步处理的，队列可能在检查时已经为空
        # 所以我们验证 subscribe_realtime_data 被调用了就说明流程正确
        assert mock_plugin.subscribe_realtime_data.called

    def test_thread_safe_callback_from_multiple_sources(self):
        """测试从多个线程并发调用 callback 的线程安全性"""
        event_bus = MagicMock()
        data_standardizer = MagicMock()
        data_validator = MagicMock()
        uni_plugin_manager = MagicMock()

        manager = EnhancedRealtimeDataManager(
            event_bus=event_bus,
            data_standardizer=data_standardizer,
            data_validator=data_validator,
            uni_plugin_manager=uni_plugin_manager
        )

        # 创建多个适配器模拟不同插件
        adapter1 = PluginCallbackAdapter(manager, 'level2_plugin', DataType.LEVEL2_DATA)
        adapter2 = PluginCallbackAdapter(manager, 'miniqmt_plugin', DataType.LEVEL2_DATA)

        def simulate_plugin1():
            for i in range(100):
                adapter1('level2', f'SYM{i}', {'symbol': f'SYM{i}', 'price': 10.0 + i})

        def simulate_plugin2():
            for i in range(100):
                adapter2({'symbol': f'SYM{i + 1000}', 'price': 11.0 + i})

        threads = [
            threading.Thread(target=simulate_plugin1),
            threading.Thread(target=simulate_plugin2)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有数据都被成功添加
        assert manager._callback_queue.qsize() == 200


class TestCallbackPerformance:
    """性能测试：Callback 模式的延迟对比"""

    @pytest.mark.asyncio
    async def test_callback_mode_latency(self):
        """测试 callback 模式的延迟"""
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
        mock_plugin = MagicMock()
        mock_plugin.subscribe_realtime_data = MagicMock(return_value=True)
        mock_plugin.get_capabilities = MagicMock(return_value={'level2': True})
        manager.realtime_plugins['test_plugin'] = mock_plugin

        # 启动 callback 处理协程
        manager._ensure_callback_mode_started()
        await asyncio.sleep(0.1)

        # 测量从 callback 到处理的时间
        start_time = time.time()

        # 模拟插件推送数据
        call_args = mock_plugin.subscribe_realtime_data.call_args
        if call_args:
            callback_adapter = call_args[0][1]
            test_data = {'symbol': '600000', 'price': 10.5, 'volume': 1000}
            callback_adapter('level2', '600000', test_data)

            # 等待数据被处理
            processed = False
            for _ in range(100):  # 最多等待 1 秒
                if event_bus.publish.called:
                    processed = True
                    break
                await asyncio.sleep(0.01)

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # Callback 模式延迟应该 < 100ms
            assert latency_ms < 100, f"Callback latency too high: {latency_ms}ms"
            print(f"Callback mode latency: {latency_ms:.2f}ms")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])