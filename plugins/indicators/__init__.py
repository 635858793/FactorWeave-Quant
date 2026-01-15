"""
指标插件模块

提供多种指标计算后端支持：
- FactorWeave-Quant指标插件：基于FactorWeave-Quant框架的高性能指标计算
- TA-Lib指标插件：基于TA-Lib库的经典技术指标
- 自定义指标插件：支持用户自定义指标开发

所有插件都实现统一的IIndicatorPlugin接口，确保兼容性和可扩展性。
"""

# 已移除 hikyuu 指标插件导入
# 已移除 pandas_ta 指标插件导入（插件未实现，已废弃）

try:
    from .talib_indicators_plugin import TALibIndicatorsPlugin
except ImportError:
    TALibIndicatorsPlugin = None

try:
    from .custom_indicators_plugin import CustomIndicatorsPlugin
except ImportError:
    CustomIndicatorsPlugin = None

__all__ = [
    'TALibIndicatorsPlugin',
    'CustomIndicatorsPlugin'
]
