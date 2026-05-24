"""
Core Package

This package contains core functionality for the trading system.
"""

# 导入纯Loguru日志系统 - 简化版本，避免循环导入
from loguru import logger
from .loguru_config import initialize_loguru

# 向后兼容导入（纯Loguru架构）
from .base_logger import BaseLogManager, LogLevel

__all__ = [
    'initialize_loguru',
    'BaseLogManager',
    'LogLevel',
]
