"""
国际股票数据源插件目录

包含国际股票市场的数据源插件（非A股）
"""

from loguru import logger

INTERNATIONAL_STOCK_PLUGINS = []

for _name in ['wind_plugin', 'yahoo_finance_plugin']:
    try:
        __import__(f'plugins.data_sources.stock_international.{_name}', fromlist=[_name])
        INTERNATIONAL_STOCK_PLUGINS.append(_name)
    except ImportError as e:
        logger.warning(f"国际股票插件 {_name} 导入失败（模块尚未实现）: {e}")

__all__ = INTERNATIONAL_STOCK_PLUGINS