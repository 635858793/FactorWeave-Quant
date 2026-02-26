"""
统一缓存服务提供者

提供全局缓存服务实例，支持各模块通过适配器访问统一缓存。
"""

from typing import Optional, Dict, Any
from threading import Lock
from loguru import logger

from core.services.cache_service import CacheService
from core.adapters.legacy_cache_adapter import (
    SmartDataCacheAdapter,
    StrategyCacheAdapter,
    AsyncIOManagerAdapter,
    create_smart_cache_adapter,
    create_strategy_cache_adapter,
    create_async_io_adapter
)


class UnifiedCacheProvider:
    """
    统一缓存服务提供者
    
    单例模式，提供全局缓存服务实例和适配器工厂。
    """
    
    _instance: Optional['UnifiedCacheProvider'] = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._cache_service: Optional[CacheService] = None
        self._adapters: Dict[str, Any] = {}
        self._initialized = True
        
        logger.info("UnifiedCacheProvider initialized")
    
    def initialize(self, cache_service: CacheService = None) -> None:
        """
        初始化缓存服务
        
        Args:
            cache_service: 缓存服务实例（可选，如果不提供则从服务容器获取）
        """
        if cache_service:
            self._cache_service = cache_service
        else:
            try:
                from core.containers import get_service_container
                service_container = get_service_container()
                self._cache_service = service_container.resolve(CacheService)
            except Exception as e:
                logger.warning(f"无法从服务容器获取CacheService: {e}")
                self._cache_service = CacheService()
                self._cache_service.initialize()
        
        logger.info("UnifiedCacheProvider initialized with CacheService")
    
    def get_cache_service(self) -> CacheService:
        """获取缓存服务实例"""
        if self._cache_service is None:
            self.initialize()
        return self._cache_service
    
    def get_smart_cache_adapter(self, namespace: str = "backtest",
                                 **kwargs) -> SmartDataCacheAdapter:
        """
        获取SmartDataCache适配器
        
        Args:
            namespace: 命名空间
            **kwargs: 额外参数
            
        Returns:
            SmartDataCacheAdapter实例
        """
        cache_key = f"smart_cache:{namespace}"
        
        if cache_key not in self._adapters:
            self._adapters[cache_key] = create_smart_cache_adapter(
                self.get_cache_service(),
                namespace,
                **kwargs
            )
        
        return self._adapters[cache_key]
    
    def get_strategy_cache_adapter(self, namespace: str = "strategy",
                                    **kwargs) -> StrategyCacheAdapter:
        """
        获取StrategyCache适配器
        
        Args:
            namespace: 命名空间
            **kwargs: 额外参数
            
        Returns:
            StrategyCacheAdapter实例
        """
        cache_key = f"strategy_cache:{namespace}"
        
        if cache_key not in self._adapters:
            self._adapters[cache_key] = create_strategy_cache_adapter(
                self.get_cache_service(),
                namespace,
                **kwargs
            )
        
        return self._adapters[cache_key]
    
    def get_async_io_adapter(self, namespace: str = "async_io",
                              **kwargs) -> AsyncIOManagerAdapter:
        """
        获取AsyncIOManager适配器
        
        Args:
            namespace: 命名空间
            **kwargs: 额外参数
            
        Returns:
            AsyncIOManagerAdapter实例
        """
        cache_key = f"async_io:{namespace}"
        
        if cache_key not in self._adapters:
            self._adapters[cache_key] = create_async_io_adapter(
                self.get_cache_service(),
                namespace,
                **kwargs
            )
        
        return self._adapters[cache_key]
    
    def get_unified_stats(self) -> Dict[str, Any]:
        """获取统一缓存统计信息"""
        return self.get_cache_service().get_unified_stats()
    
    def clear_all_namespaces(self) -> None:
        """清空所有命名空间"""
        cache_service = self.get_cache_service()
        for namespace in cache_service.list_namespaces():
            cache_service.clear_namespace(namespace)
        
        logger.info("All namespaces cleared")


# 全局单例
_unified_cache_provider: Optional[UnifiedCacheProvider] = None
_provider_lock = Lock()


def get_unified_cache_provider() -> UnifiedCacheProvider:
    """获取全局缓存服务提供者实例"""
    global _unified_cache_provider
    
    if _unified_cache_provider is None:
        with _provider_lock:
            if _unified_cache_provider is None:
                _unified_cache_provider = UnifiedCacheProvider()
    
    return _unified_cache_provider


def get_smart_cache() -> SmartDataCacheAdapter:
    """获取SmartDataCache适配器（便捷函数）"""
    return get_unified_cache_provider().get_smart_cache_adapter()


def get_strategy_cache() -> StrategyCacheAdapter:
    """获取StrategyCache适配器（便捷函数）"""
    return get_unified_cache_provider().get_strategy_cache_adapter()


def get_async_io_cache() -> AsyncIOManagerAdapter:
    """获取AsyncIOManager适配器（便捷函数）"""
    return get_unified_cache_provider().get_async_io_adapter()
