"""
自定义数据源插件目录

包含用户自定义数据源插件
"""

from loguru import logger

CUSTOM_PLUGINS = []

for _name in ['custom_data_plugin']:
    try:
        __import__(f'plugins.data_sources.custom.{_name}', fromlist=[_name])
        CUSTOM_PLUGINS.append(_name)
    except ImportError as e:
        logger.warning(f"自定义插件 {_name} 导入失败（模块尚未实现）: {e}")

__all__ = CUSTOM_PLUGINS