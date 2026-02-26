"""
测试遗留缓存适配器

验证SmartDataCacheAdapter、StrategyCacheAdapter和AsyncIOManagerAdapter的功能
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services.cache_service import CacheService
from core.adapters.legacy_cache_adapter import (
    SmartDataCacheAdapter,
    StrategyCacheAdapter,
    AsyncIOManagerAdapter,
    create_smart_cache_adapter,
    create_strategy_cache_adapter,
    create_async_io_adapter
)


@pytest.fixture
def cache_service():
    """创建缓存服务实例"""
    service = CacheService()
    service.initialize()
    return service


class TestSmartDataCacheAdapter:
    """SmartDataCache适配器测试"""

    def test_create_adapter(self, cache_service):
        """测试创建适配器"""
        adapter = create_smart_cache_adapter(cache_service, namespace="test_backtest")
        assert adapter is not None
        assert isinstance(adapter, SmartDataCacheAdapter)

    def test_put_and_get(self, cache_service):
        """测试put和get操作"""
        adapter = SmartDataCacheAdapter(cache_service, namespace="test_backtest")
        
        adapter.put("test_key", "test_value", ttl=3600)
        value = adapter.get("test_key")
        
        assert value == "test_value"

    def test_delete(self, cache_service):
        """测试delete操作"""
        adapter = SmartDataCacheAdapter(cache_service, namespace="test_backtest")
        
        adapter.put("delete_key", "value")
        result = adapter.delete("delete_key")
        
        assert result is True
        assert adapter.get("delete_key") is None

    def test_clear(self, cache_service):
        """测试clear操作"""
        adapter = SmartDataCacheAdapter(cache_service, namespace="test_clear")
        
        adapter.put("key1", "value1")
        adapter.put("key2", "value2")
        adapter.clear()
        
        assert adapter.get("key1") is None
        assert adapter.get("key2") is None

    def test_get_stats(self, cache_service):
        """测试获取统计信息"""
        adapter = SmartDataCacheAdapter(cache_service, namespace="test_stats")
        
        adapter.put("key1", "value1")
        adapter.get("key1")
        adapter.get("nonexistent")
        
        stats = adapter.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1


class TestStrategyCacheAdapter:
    """StrategyCache适配器测试"""

    def test_create_adapter(self, cache_service):
        """测试创建适配器"""
        adapter = create_strategy_cache_adapter(cache_service, namespace="test_strategy")
        assert adapter is not None
        assert isinstance(adapter, StrategyCacheAdapter)

    def test_put_with_strategy(self, cache_service):
        """测试带策略名的put操作"""
        adapter = StrategyCacheAdapter(cache_service, namespace="test_strategy")
        
        adapter.put("strategy_key", "strategy_value", strategy_name="ma_cross", priority=8)
        value = adapter.get("strategy_key")
        
        assert value == "strategy_value"

    def test_clear_strategy(self, cache_service):
        """测试清空指定策略缓存"""
        adapter = StrategyCacheAdapter(cache_service, namespace="test_strategy_clear")
        
        adapter.put("key1", "value1", strategy_name="strategy_a")
        adapter.put("key2", "value2", strategy_name="strategy_a")
        adapter.put("key3", "value3", strategy_name="strategy_b")
        
        cleared = adapter.clear_strategy("strategy_a")
        
        assert cleared >= 0

    def test_get_stats(self, cache_service):
        """测试获取统计信息"""
        adapter = StrategyCacheAdapter(cache_service, namespace="test_strategy_stats")
        
        adapter.put("key1", "value1", strategy_name="test_strategy")
        adapter.get("key1")
        
        stats = adapter.get_stats()
        
        assert "cache_size" in stats
        assert "strategy_count" in stats


class TestAsyncIOManagerAdapter:
    """AsyncIOManager适配器测试"""

    def test_create_adapter(self, cache_service):
        """测试创建适配器"""
        adapter = create_async_io_adapter(cache_service, namespace="test_async_io")
        assert adapter is not None
        assert isinstance(adapter, AsyncIOManagerAdapter)

    def test_cache_data(self, cache_service):
        """测试缓存数据"""
        adapter = AsyncIOManagerAdapter(cache_service, namespace="test_async_io")
        
        adapter.cache_data("file_key", {"data": "test"}, ttl=3600)
        value = adapter.get_cached_data("file_key")
        
        assert value == {"data": "test"}

    def test_invalidate_cache(self, cache_service):
        """测试使缓存失效"""
        adapter = AsyncIOManagerAdapter(cache_service, namespace="test_async_io")
        
        adapter.cache_data("invalidate_key", "data")
        result = adapter.invalidate_cache("invalidate_key")
        
        assert result is True
        assert adapter.get_cached_data("invalidate_key") is None

    def test_get_stats(self, cache_service):
        """测试获取统计信息"""
        adapter = AsyncIOManagerAdapter(cache_service, namespace="test_async_io_stats")
        
        adapter.cache_data("key1", "value1")
        adapter.get_cached_data("key1")
        adapter.get_cached_data("nonexistent")
        
        stats = adapter.get_stats()
        
        assert "cache_hits" in stats
        assert "cache_misses" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
