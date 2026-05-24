"""
宏观经济数据源插件包

提供各种宏观经济数据源的插件实现，包括：
- FRED (Federal Reserve Economic Data)
- 央行数据
- 统计局数据
- 国际组织数据

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

from loguru import logger

FREDPlugin = None
PBOCPlugin = None
NBSPlugin = None

try:
    from .fred_plugin import FREDPlugin
except ImportError as e:
    logger.warning(f"FREDPlugin 导入失败（模块尚未实现）: {e}")

try:
    from .pboc_plugin import PBOCPlugin
except ImportError as e:
    logger.warning(f"PBOCPlugin 导入失败（模块尚未实现）: {e}")

try:
    from .nbs_plugin import NBSPlugin
except ImportError as e:
    logger.warning(f"NBSPlugin 导入失败（模块尚未实现）: {e}")

__all__ = [
    'FREDPlugin',
    'PBOCPlugin',
    'NBSPlugin'
]
