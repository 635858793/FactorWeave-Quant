"""
CacheService扩展功能单元测试

测试命名空间、分组管理和优先级控制功能
"""

import pytest
import time
from datetime import timedelta
from core.services.cache_service import CacheService, CacheLevel


class TestCacheServiceNamespace:
    """命名空间功能测试"""

    def test_create_namespace(self, cache_service):
        """测试创建命名空间"""
        result = cache_service.create_namespace(
            name="test_namespace",
            max_size=1000,
            priority=8,
            description="测试命名空间"
        )
        assert result is True

        namespaces = cache_service.list_namespaces()
        assert "test_namespace" in namespaces

    def test_create_duplicate_namespace(self, cache_service):
        """测试创建重复命名空间"""
        cache_service.create_namespace("duplicate_test")
        result = cache_service.create_namespace("duplicate_test")
        assert result is False

    def test_delete_namespace(self, cache_service):
        """测试删除命名空间"""
        cache_service.create_namespace("to_delete")
        cache_service.set("key1", "value1", namespace="to_delete")

        result = cache_service.delete_namespace("to_delete")
        assert result is True

        namespaces = cache_service.list_namespaces()
        assert "to_delete" not in namespaces

    def test_delete_default_namespace_fails(self, cache_service):
        """测试不能删除默认命名空间"""
        result = cache_service.delete_namespace("default")
        assert result is False

    def test_namespace_isolation(self, cache_service):
        """测试命名空间隔离"""
        cache_service.create_namespace("ns1")
        cache_service.create_namespace("ns2")

        cache_service.set("same_key", "value_ns1", namespace="ns1")
        cache_service.set("same_key", "value_ns2", namespace="ns2")

        value1 = cache_service.get("same_key", namespace="ns1")
        value2 = cache_service.get("same_key", namespace="ns2")

        assert value1 == "value_ns1"
        assert value2 == "value_ns2"

    def test_get_namespace_stats(self, cache_service):
        """测试获取命名空间统计"""
        cache_service.create_namespace("stats_test", max_size=500, priority=7)
        cache_service.set("key1", "value1", namespace="stats_test")
        cache_service.set("key2", "value2", namespace="stats_test")

        stats = cache_service.get_namespace_stats("stats_test")

        assert stats["name"] == "stats_test"
        assert stats["key_count"] == 2
        assert stats["priority"] == 7
        assert stats["max_size"] == 500

    def test_clear_namespace(self, cache_service):
        """测试清空命名空间"""
        cache_service.create_namespace("clear_test")
        cache_service.set("key1", "value1", namespace="clear_test")
        cache_service.set("key2", "value2", namespace="clear_test")

        cleared = cache_service.clear_namespace("clear_test")
        assert cleared == 2

        stats = cache_service.get_namespace_stats("clear_test")
        assert stats["key_count"] == 0


class TestCacheServiceGroup:
    """分组管理功能测试"""

    def test_set_with_group(self, cache_service):
        """测试设置带分组的缓存"""
        cache_service.create_namespace("group_test")
        cache_service.set("key1", "value1", namespace="group_test", group="group_a")
        cache_service.set("key2", "value2", namespace="group_test", group="group_a")
        cache_service.set("key3", "value3", namespace="group_test", group="group_b")

        stats = cache_service.get_namespace_stats("group_test")
        assert stats["group_count"] == 2
        assert stats["groups"]["group_a"] == 2
        assert stats["groups"]["group_b"] == 1

    def test_get_by_group(self, cache_service):
        """测试获取分组数据"""
        cache_service.create_namespace("get_group_test")
        cache_service.set("k1", "v1", namespace="get_group_test", group="g1")
        cache_service.set("k2", "v2", namespace="get_group_test", group="g1")
        cache_service.set("k3", "v3", namespace="get_group_test", group="g2")

        group_data = cache_service.get_by_group("get_group_test", "g1")

        assert len(group_data) == 2
        assert group_data["k1"] == "v1"
        assert group_data["k2"] == "v2"
        assert "k3" not in group_data

    def test_clear_group(self, cache_service):
        """测试清空分组"""
        cache_service.create_namespace("clear_group_test")
        cache_service.set("k1", "v1", namespace="clear_group_test", group="g1")
        cache_service.set("k2", "v2", namespace="clear_group_test", group="g1")
        cache_service.set("k3", "v3", namespace="clear_group_test", group="g2")

        cleared = cache_service.clear_group("clear_group_test", "g1")
        assert cleared == 2

        group_data = cache_service.get_by_group("clear_group_test", "g1")
        assert len(group_data) == 0

        group_data2 = cache_service.get_by_group("clear_group_test", "g2")
        assert len(group_data2) == 1


class TestCacheServicePriority:
    """优先级控制功能测试"""

    def test_set_with_priority(self, cache_service):
        """测试设置带优先级的缓存"""
        cache_service.set("low_key", "low_value", priority=1)
        cache_service.set("high_key", "high_value", priority=10)
        cache_service.set("mid_key", "mid_value", priority=5)

        stats = cache_service.get_unified_stats()
        priority_dist = stats.get("priority_distribution", {})

        assert 1 in priority_dist
        assert 10 in priority_dist
        assert 5 in priority_dist

    def test_priority_bounds(self, cache_service):
        """测试优先级边界"""
        cache_service.set("below_min", "value", priority=-5)
        cache_service.set("above_max", "value", priority=15)

        stats = cache_service.get_unified_stats()
        priority_dist = stats.get("priority_distribution", {})

        assert 0 in priority_dist
        assert 10 in priority_dist

    def test_evict_by_priority(self, cache_service):
        """测试按优先级驱逐"""
        cache_service.set("p1_key", "v1", priority=1)
        cache_service.set("p2_key", "v2", priority=2)
        cache_service.set("p3_key", "v3", priority=3)
        cache_service.set("p8_key", "v8", priority=8)
        cache_service.set("p9_key", "v9", priority=9)

        evicted = cache_service.evict_by_priority(min_priority=1, max_priority=3)
        assert evicted == 3

        assert cache_service.get("p1_key") is None
        assert cache_service.get("p2_key") is None
        assert cache_service.get("p3_key") is None
        assert cache_service.get("p8_key") == "v8"
        assert cache_service.get("p9_key") == "v9"


class TestCacheServiceUnifiedStats:
    """统一统计功能测试"""

    def test_unified_stats(self, cache_service):
        """测试统一统计"""
        cache_service.create_namespace("stats_ns1", priority=8)
        cache_service.create_namespace("stats_ns2", priority=3)

        cache_service.set("k1", "v1", namespace="stats_ns1", group="g1", priority=7)
        cache_service.set("k2", "v2", namespace="stats_ns2", group="g2", priority=4)

        stats = cache_service.get_unified_stats()

        assert "namespaces" in stats
        assert "namespace_count" in stats
        assert "priority_distribution" in stats
        assert stats["namespace_count"] >= 2


class TestCacheServiceBackwardCompatibility:
    """向后兼容性测试"""

    def test_default_namespace_usage(self, cache_service):
        """测试默认命名空间使用"""
        cache_service.set("default_key", "default_value")
        value = cache_service.get("default_key")

        assert value == "default_value"

    def test_original_api_compatibility(self, cache_service):
        """测试原始API兼容性"""
        cache_service.set("test_key", "test_value", ttl=timedelta(seconds=60))
        value = cache_service.get("test_key")

        assert value == "test_value"

        result = cache_service.delete("test_key")
        assert result is True

        value_after_delete = cache_service.get("test_key")
        assert value_after_delete is None


@pytest.fixture
def cache_service():
    """创建CacheService实例"""
    service = CacheService()
    service.initialize()
    yield service
    service.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
