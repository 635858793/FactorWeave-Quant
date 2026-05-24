"""
债券数据源插件目录

包含债券市场数据源插件
"""

from loguru import logger

BOND_PLUGINS = []
_stub_names = ['bond_universal_plugin']

for _name in _stub_names:
    try:
        __import__(f'plugins.data_sources.bond.{_name}', fromlist=[_name])
        BOND_PLUGINS.append(_name)
    except ImportError as e:
        logger.warning(f"债券插件 {_name} 导入失败（模块尚未实现）: {e}")

__all__ = BOND_PLUGINS