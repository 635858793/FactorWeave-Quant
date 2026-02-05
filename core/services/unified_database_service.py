"""
数据库服务模块
"""

from .database_service import DatabaseService

def get_unified_database_service(service_container=None):
    """
    获取统一的数据库服务
    
    Args:
        service_container: 服务容器，如果为None则使用全局容器
        
    Returns:
        DatabaseService: 数据库服务实例
    """
    from ..containers import get_service_container
    container = service_container or get_service_container()
    
    if container.is_registered(DatabaseService):
        return container.resolve(DatabaseService)
    else:
        return DatabaseService(service_container=container)

__all__ = ['DatabaseService', 'get_unified_database_service']