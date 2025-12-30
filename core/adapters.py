#!/usr/bin/env python3
"""
系统适配器模块

提供系统组件的统一访问接口，简化模块间的依赖关系
"""

from loguru import logger
from typing import Dict, Any, Optional
import json
import os


def get_config() -> Dict[str, Any]:
    """
    获取系统配置

    Returns:
        系统配置字典
    """
    try:
        # 默认配置
        default_config = {
            'real_data': {
                'cache_ttl': 300,  # 5分钟缓存
                'max_retries': 3,
                'timeout': 30
            },
            'database': {
                'path': 'data/factorweave_system.sqlite',
                'connection_pool_size': 50
            },
            'import': {
                'batch_size': 100,
                'max_workers': 10
            }
        }

        # 尝试从配置文件加载
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'system_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                default_config.update(file_config)
                logger.info(f"已加载配置文件: {config_path}")
        else:
            logger.info("使用默认配置")

        return default_config

    except Exception as e:
        logger.warning(f"获取配置失败，使用默认配置: {e}")
        return {
            'real_data': {'cache_ttl': 300},
            'database': {'path': 'data/factorweave_system.sqlite'},
            'import': {'batch_size': 100}
        }

def get_data_validator():
    """
    获取数据验证器

    Returns:
        数据验证器实例
    """
    try:
        from core.data_validator import ProfessionalDataValidator
        return ProfessionalDataValidator()
    except ImportError as e:
        logger.warning(f"专业数据验证器不可用，使用默认验证器: {e}")
        return DefaultDataValidator()
    except Exception as e:
        logger.warning(f"数据验证器初始化失败，使用默认验证器: {e}")
        return DefaultDataValidator()

class DefaultDataValidator:
    """默认数据验证器"""

    def validate_data(self, data, data_type: str = None) -> bool:
        """验证数据"""
        if data is None:
            return False

        # 简单验证：非空检查
        if hasattr(data, '__len__'):
            return len(data) > 0

        return True

    def validate_stock_code(self, code: str) -> bool:
        """验证股票代码"""
        if not code or not isinstance(code, str):
            return False

        # 简单验证：6位数字
        return len(code) == 6 and code.isdigit()

def get_performance_monitor():
    """
    获取性能监控器

    Returns:
        性能监控器实例
    """
    try:
        from core.performance import get_performance_monitor as _get_performance_monitor
        return _get_performance_monitor()
    except ImportError as e:
        logger.warning(f"无法导入性能监控器: {e}")
        return None
    except Exception as e:
        logger.error(f"获取性能监控器失败: {e}")
        return None
