"""
期货数据源插件目录

包含所有期货交易相关的数据源插件
"""

from loguru import logger

FUTURES_PLUGINS = []

for _name in ['ctp_plugin', 'wenhua_plugin', 'futures_universal_plugin']:
    try:
        __import__(f'plugins.data_sources.futures.{_name}', fromlist=[_name])
        FUTURES_PLUGINS.append(_name)
    except ImportError as e:
        logger.warning(f"期货插件 {_name} 导入失败（模块尚未实现）: {e}")

__all__ = FUTURES_PLUGINS