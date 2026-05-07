"""
依赖注入容器模块

提供依赖注入和服务管理的核心组件。
"""

from .service_container import ServiceContainer, get_service_container, set_service_container
from .service_registry import ServiceRegistry, ServiceInfo, ServiceScope

_enhanced_service_container = None
_unified_service_container = None

def _get_enhanced_service_container():
    """延迟导入EnhancedServiceContainer，避免循环导入"""
    global _enhanced_service_container
    if _enhanced_service_container is None:
        from .enhanced_service_container import EnhancedServiceContainer
        _enhanced_service_container = EnhancedServiceContainer
    return _enhanced_service_container

def _get_unified_service_container():
    """延迟导入UnifiedServiceContainer，避免循环导入"""
    global _unified_service_container
    if _unified_service_container is None:
        from .unified_service_container import UnifiedServiceContainer
        _unified_service_container = UnifiedServiceContainer
    return _unified_service_container

class EnhancedServiceContainer:
    """EnhancedServiceContainer延迟代理"""
    def __new__(cls, *args, **kwargs):
        return _get_enhanced_service_container()(*args, **kwargs)

class UnifiedServiceContainer:
    """UnifiedServiceContainer延迟代理"""
    def __new__(cls, *args, **kwargs):
        return _get_unified_service_container()(*args, **kwargs)

def get_unified_container():
    from .unified_service_container import get_unified_container as _get_unified
    return _get_unified()

def reset_unified_container():
    from .unified_service_container import reset_unified_container as _reset_unified
    _reset_unified()

__all__ = [
    'ServiceContainer',
    'get_service_container',
    'set_service_container',
    'ServiceRegistry',
    'ServiceInfo',
    'ServiceScope',
    'EnhancedServiceContainer',
    'UnifiedServiceContainer',
    'get_unified_container',
    'reset_unified_container',
]
