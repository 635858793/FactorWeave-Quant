#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一缓存集成验证测试

验证所有服务是否正确集成统一缓存服务。
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestUnifiedCacheIntegration:
    """统一缓存集成测试"""

    def test_cache_service_namespace_support(self):
        """测试 CacheService 命名空间支持"""
        from core.services.cache_service import CacheService
        
        cache = CacheService()
        cache._do_initialize()
        
        cache.set("key1", "value1", namespace="ns1")
        cache.set("key1", "value2", namespace="ns2")
        
        assert cache.get("key1", namespace="ns1") == "value1"
        assert cache.get("key1", namespace="ns2") == "value2"
        assert cache.get("key1") is None

    def test_cacheable_service_unified_cache(self):
        """测试 CacheableService 使用统一缓存"""
        from core.services.base_service import CacheableService
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        cache_service = CacheService()
        cache_service._do_initialize()
        
        if not container.is_registered(CacheService):
            container.register(CacheService, lambda: cache_service)
        
        class TestService(CacheableService):
            def __init__(self):
                super().__init__(namespace='test_service')
        
        service = TestService()
        
        service.put_to_cache("test_key", "test_value")
        assert service.get_from_cache("test_key") == "test_value"
        
        assert service._unified_cache is not None
        assert service._namespace == 'test_service'

    def test_data_service_cache_integration(self):
        """测试 DataService 缓存集成"""
        from core.services.data_service import DataService
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        cache_service = CacheService()
        cache_service._do_initialize()
        
        if not container.is_registered(CacheService):
            container.register(CacheService, lambda: cache_service)
        
        with patch.object(DataService, '_do_initialize'):
            service = DataService()
        
        assert hasattr(service, '_unified_cache')
        assert hasattr(service, '_cache_namespace')
        assert service._cache_namespace == 'data_service'

    def test_analysis_service_cache_integration(self):
        """测试 AnalysisService 缓存集成"""
        from core.services.analysis_service import AnalysisService
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        cache_service = CacheService()
        cache_service._do_initialize()
        
        if not container.is_registered(CacheService):
            container.register(CacheService, lambda: cache_service)
        
        with patch.object(AnalysisService, '_do_initialize'):
            service = AnalysisService()
        
        assert hasattr(service, '_unified_cache')
        assert hasattr(service, '_cache_namespace')
        assert service._cache_namespace == 'analysis_service'
        
        assert hasattr(service, '_get_from_cache')
        assert hasattr(service, '_put_to_cache')

    def test_network_service_cache_integration(self):
        """测试 NetworkService 缓存集成"""
        from core.services.network_service import NetworkService
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        cache_service = CacheService()
        cache_service._do_initialize()
        
        if not container.is_registered(CacheService):
            container.register(CacheService, lambda: cache_service)
        
        with patch.object(NetworkService, '_do_initialize'):
            service = NetworkService()
        
        assert hasattr(service, '_unified_cache')
        assert hasattr(service, '_cache_namespace')
        assert service._cache_namespace == 'network_service'

    def test_sector_fund_flow_service_cache_integration(self):
        """测试 SectorFundFlowService 缓存集成"""
        from core.services.sector_fund_flow_service import SectorFundFlowService
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        cache_service = CacheService()
        cache_service._do_initialize()
        
        if not container.is_registered(CacheService):
            container.register(CacheService, lambda: cache_service)
        
        service = SectorFundFlowService()
        
        assert hasattr(service, '_unified_cache')
        assert hasattr(service, '_cache_namespace')
        assert service._cache_namespace == 'sector_fund_flow'

    def test_cache_namespace_isolation(self):
        """测试缓存命名空间隔离"""
        from core.services.cache_service import CacheService
        
        cache = CacheService()
        cache._do_initialize()
        
        cache.set("shared_key", "data_value", namespace="data_service")
        cache.set("shared_key", "network_value", namespace="network_service")
        cache.set("shared_key", "analysis_value", namespace="analysis_service")
        
        assert cache.get("shared_key", namespace="data_service") == "data_value"
        assert cache.get("shared_key", namespace="network_service") == "network_value"
        assert cache.get("shared_key", namespace="analysis_service") == "analysis_value"

    def test_cache_ttl_support(self):
        """测试缓存 TTL 支持"""
        from core.services.cache_service import CacheService
        
        cache = CacheService()
        cache._do_initialize()
        
        cache.set("ttl_key", "ttl_value", ttl=timedelta(seconds=1))
        
        assert cache.get("ttl_key") == "ttl_value"
        
        import time
        time.sleep(1.5)
        
        assert cache.get("ttl_key") is None

    def test_cache_statistics(self):
        """测试缓存统计"""
        from core.services.cache_service import CacheService
        
        cache = CacheService()
        cache._do_initialize()
        
        cache.set("stat_key1", "value1", namespace="test")
        cache.set("stat_key2", "value2", namespace="test")
        
        cache.get("stat_key1", namespace="test")
        cache.get("stat_key2", namespace="test")
        cache.get("stat_key3", namespace="test")
        
        stats = cache.get_stats()
        
        assert stats is not None
        assert isinstance(stats, dict)


class TestCacheFallback:
    """缓存回退测试"""

    def test_cacheable_service_fallback(self):
        """测试 CacheableService 回退到独立缓存"""
        from core.services.base_service import CacheableService
        
        class TestFallbackService(CacheableService):
            def __init__(self):
                super().__init__(namespace='fallback_test')
        
        service = TestFallbackService()
        
        service.put_to_cache("fallback_key", "fallback_value")
        assert service.get_from_cache("fallback_key") == "fallback_value"

    def test_data_service_fallback(self):
        """测试 DataService 强制使用统一缓存"""
        from core.services.data_service import DataService
        from core.services.cache_service import CacheService
        from core.containers import get_service_container
        
        container = get_service_container()
        original_registered = container.is_registered(CacheService) if container else False
        
        if original_registered:
            cache_service = CacheService()
            cache_service._do_initialize()
            container.register(CacheService, lambda: cache_service)
        
        with patch.object(DataService, '_do_initialize'):
            with patch('core.services.data_service.get_service_container') as mock_container:
                mock_container_instance = Mock()
                mock_container_instance.is_registered.return_value = False
                mock_container.return_value = mock_container_instance
                
                with pytest.raises(RuntimeError) as exc_info:
                    service = DataService()
                
                assert "统一缓存服务未注册" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
