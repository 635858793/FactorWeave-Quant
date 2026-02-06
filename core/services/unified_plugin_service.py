"""
插件服务模块
"""

from .plugin_service import PluginService

def get_unified_plugin_service(service_container=None):
    """
    获取统一的插件服务
    
    Args:
        service_container: 服务容器，如果为None则使用全局容器
        
    Returns:
        PluginService: 插件服务实例
    """
    from ..containers import get_service_container
    container = service_container or get_service_container()
    
    if container.is_registered(PluginService):
        return container.resolve(PluginService)
    else:
        return PluginService(service_container=container)

__all__ = ['PluginService', 'get_unified_plugin_service']