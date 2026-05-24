"""
情绪数据源插件包
提供多种情绪分析数据源的统一接口

⚠️ 模拟数据警告：以下3个插件为模拟数据插件，生产环境不可用（需对接真实数据源）：
  - NewsSentimentPlugin (news_sentiment_plugin.py) - 新闻情绪分析
  - CryptoSentimentPlugin (crypto_sentiment_plugin.py) - 加密货币情绪分析
  - MultiSourceSentimentPlugin (multi_source_sentiment_plugin.py) - 多源情绪数据
  这些插件已标记 self._simulated = True，需对接真实数据源后方可启用。

  可用的真实数据源插件：
  - FMPSentimentPlugin - Financial Modeling Prep API (需要 API Key)
  - ExordeSentimentPlugin - Exorde 27种情绪分析 API (免费/付费)
  - VIXSentimentPlugin - Yahoo Finance / AlphaVantage 恐慌指数 (免费)
"""

from plugins.sentiment_data_sources.base_sentiment_plugin import BaseSentimentPlugin
from plugins.sentiment_data_sources.config_base import ConfigurablePlugin, PluginConfigField

# 导入新的独立插件
from plugins.sentiment_data_sources.fmp_sentiment_plugin import FMPSentimentPlugin
from plugins.sentiment_data_sources.exorde_sentiment_plugin import ExordeSentimentPlugin
from plugins.sentiment_data_sources.news_sentiment_plugin import NewsSentimentPlugin
from plugins.sentiment_data_sources.vix_sentiment_plugin import VIXSentimentPlugin
from plugins.sentiment_data_sources.crypto_sentiment_plugin import CryptoSentimentPlugin

# 保留多源插件作为备用
from plugins.sentiment_data_sources.multi_source_sentiment_plugin import MultiSourceSentimentPlugin

# 可选导入AkShare插件（如果依赖不可用则跳过）
try:
    from plugins.sentiment_data_sources.akshare_sentiment_plugin import AkShareSentimentPlugin
    AKSHARE_AVAILABLE = True
except ImportError:
    AkShareSentimentPlugin = None
    AKSHARE_AVAILABLE = False

# 可用的情绪数据源插件
__all__ = [
    'BaseSentimentPlugin',
    'ConfigurablePlugin',
    'PluginConfigField',
    'FMPSentimentPlugin',
    'ExordeSentimentPlugin',
    'NewsSentimentPlugin',
    'VIXSentimentPlugin',
    'CryptoSentimentPlugin',
    'MultiSourceSentimentPlugin'
]

if AKSHARE_AVAILABLE:
    __all__.append('AkShareSentimentPlugin')

# 插件注册表 - 现在以独立插件为主
AVAILABLE_PLUGINS = {
    'fmp_sentiment': FMPSentimentPlugin,
    'exorde_sentiment': ExordeSentimentPlugin,
    'news_sentiment': NewsSentimentPlugin,
    'vix_sentiment': VIXSentimentPlugin,
    'crypto_sentiment': CryptoSentimentPlugin,
    'multi_source': MultiSourceSentimentPlugin,  # 保留作为备用
}

if AKSHARE_AVAILABLE:
    AVAILABLE_PLUGINS['akshare'] = AkShareSentimentPlugin

# 获取默认插件

def get_default_plugin():
    """获取默认的情绪数据源插件"""
    # 现在优先使用FMP插件，然后是其他独立插件
    try:
        return FMPSentimentPlugin()
    except Exception:
        try:
            return MultiSourceSentimentPlugin()
        except Exception:
            if AKSHARE_AVAILABLE:
                return AkShareSentimentPlugin()
            else:
                raise RuntimeError("没有可用的情绪数据源插件")

def get_plugin_by_name(name: str):
    """根据名称获取插件"""
    if name in AVAILABLE_PLUGINS:
        return AVAILABLE_PLUGINS[name]()
    else:
        available_names = list(AVAILABLE_PLUGINS.keys())
        raise ValueError(f"未找到名为 {name} 的插件。可用插件: {available_names}")

def list_available_plugins():
    """列出所有可用的插件"""
    return list(AVAILABLE_PLUGINS.keys())

def check_plugin_availability():
    """检查插件可用性"""
    return {
        'fmp_sentiment': True,
        'exorde_sentiment': True,
        'news_sentiment': True,
        'vix_sentiment': True,
        'crypto_sentiment': True,
        'multi_source': True,
        'akshare': AKSHARE_AVAILABLE,
        'total_available': len(AVAILABLE_PLUGINS)
    }
