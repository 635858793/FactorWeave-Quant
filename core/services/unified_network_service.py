"""
网络服务模块
"""

from .network_service import NetworkService

def get_unified_network_service(service_container=None):
    """
    获取统一的网络服务
    
    Args:
        service_container: 服务容器，如果为None则使用全局容器
        
    Returns:
        NetworkService: 网络服务实例
    """
    from ..containers import get_service_container
    container = service_container or get_service_container()
    
    if container.is_registered(NetworkService):
        return container.resolve(NetworkService)
    else:
        return NetworkService(service_container=container)

__all__ = ['NetworkService', 'get_unified_network_service']