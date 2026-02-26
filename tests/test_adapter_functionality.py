"""
简单的功能测试 - 验证适配器功能
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services.cache_service import CacheService
from core.adapters.legacy_cache_adapter import (
    SmartDataCacheAdapter,
    StrategyCacheAdapter,
    AsyncIOManagerAdapter
)


@pytest.fixture
def cache_service():
    """创建缓存服务实例"""
    service = CacheService()
    service.initialize()
    return service


class TestAdapterBasicOperations:
    """适配器基本操作测试"""

    def test_smart_cache_adapter_basic(self, cache_service):
        """测试SmartDataCache适配器基本操作"""
        adapter = SmartDataCacheAdapter(cache_service, namespace="test_basic")
        
        adapter.put("test_key", "test_value", ttl=3600)
        value = adapter.get("test_key")
        assert value == "test_value"
        
        adapter.delete("test_key")
        assert adapter.get("test_key") is None

    def test_strategy_cache_adapter_basic(self, cache_service):
        """测试StrategyCache适配器基本操作"""
        adapter = StrategyCacheAdapter(cache_service, namespace="test_strategy_basic")
        
        adapter.put("strategy_key", "strategy_value", strategy_name="test_strategy")
        value = adapter.get("strategy_key")
        assert value == "strategy_value"

    def test_async_io_adapter_basic(self, cache_service):
        """测试AsyncIOManager适配器基本操作"""
        adapter = AsyncIOManagerAdapter(cache_service, namespace="test_async_basic")
        
        adapter.cache_data("file_key", {"data": "test"}, ttl=3600)
        value = adapter.get_cached_data("file_key")
        assert value == {"data": "test"}

    def test_namespace_isolation(self, cache_service):
        """测试命名空间隔离"""
        adapter1 = SmartDataCacheAdapter(cache_service, namespace="ns1")
        adapter2 = SmartDataCacheAdapter(cache_service, namespace="ns2")
        
        adapter1.put("same_key", "value_ns1")
        adapter2.put("same_key", "value_ns2")
        
        assert adapter1.get("same_key") == "value_ns1"
        assert adapter2.get("same_key") == "value_ns2"

    def test_stats_collection(self, cache_service):
        """测试统计信息收集"""
        adapter = SmartDataCacheAdapter(cache_service, namespace="test_stats_collection")
        
        adapter.put("key1", "value1")
        adapter.get("key1")
        adapter.get("nonexistent")
        
        stats = adapter.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
