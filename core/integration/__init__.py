"""
系统集成模块

提供系统集成的工具和接口
"""

from .data_router import DataRouter
from .system_integration_manager import SystemIntegrationManager

__all__ = [
    'DataRouter',
    'SystemIntegrationManager'
]