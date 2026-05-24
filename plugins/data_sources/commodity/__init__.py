"""
大宗商品数据源插件目录

包含大宗商品市场数据源插件
"""

from loguru import logger

COMMODITY_PLUGINS = []
_stub_names = ['mysteel_plugin']

for _name in _stub_names:
    try:
        __import__(f'plugins.data_sources.commodity.{_name}', fromlist=[_name])
        COMMODITY_PLUGINS.append(_name)
    except ImportError as e:
        logger.warning(f"商品插件 {_name} 导入失败（模块尚未实现）: {e}")

__all__ = COMMODITY_PLUGINS