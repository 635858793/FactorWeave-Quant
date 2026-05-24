"""
外汇数据源插件目录

包含外汇市场数据源插件
"""

from loguru import logger

FOREX_PLUGINS = []
_stub_names = ['forex_universal_plugin']

for _name in _stub_names:
    try:
        __import__(f'plugins.data_sources.forex.{_name}', fromlist=[_name])
        FOREX_PLUGINS.append(_name)
    except ImportError as e:
        logger.warning(f"外汇插件 {_name} 导入失败（模块尚未实现）: {e}")

__all__ = FOREX_PLUGINS