"""
缓存服务模块
"""

from .cache_service import CacheService

def get_unified_cache_service(service_container=None):
    """
    获取统一的缓存服务
    
    Args:
        service_container: 服务容器，如果为None则使用全局容器
        
    Returns:
        CacheService: 缓存服务实例
    """
    from ..containers import get_service_container
    container = service_container or get_service_container()
    
    if container.is_registered(CacheService):
        return container.resolve(CacheService)
    else:
        return CacheService(service_container=container)

__all__ = ['CacheService', 'get_unified_cache_service']