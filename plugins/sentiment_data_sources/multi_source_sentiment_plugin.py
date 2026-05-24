from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源情绪数据插件
支持多种免费/低成本API：
1. Financial Modeling Prep (FMP) - 免费额度
2. Exorde API - 1000免费credits
3. AI Market Mood - 免费使用
4. Alpha Vantage - 新闻情绪
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from core.plugin_types import PluginType, PluginCategory
from plugins.sentiment_data_sources.base_sentiment_plugin import BaseSentimentPlugin
from plugins.sentiment_data_source_interface import SentimentData, SentimentResponse

# ⚠️ 模拟数据模式 - 此插件已禁用，所有数据源需对接真实API后方可启用
class MultiSourceSentimentPlugin(BaseSentimentPlugin):
    """多源情绪数据插件"""

    has_real_data = False

    def __init__(self):
        super().__init__()
        self._simulated = True
        # API配置
        self.api_keys = {
            'fmp': '',  # Financial Modeling Prep
            'exorde': '',  # Exorde API
            'alpha_vantage': '',  # Alpha Vantage
        }
        self.api_configs = {
            'fmp': {
                'base_url': 'https://financialmodelingprep.com/api',
                'free_limit': 250,  # 每日免费请求数
                'endpoints': {
                    'social_sentiment': '/v4/historical/social-sentiment',
                    'news_sentiment': '/v4/stock-news-sentiments-rss-feed',
                    'trending': '/v4/social-sentiments/trending'
                }
            },
            'exorde': {
                'base_url': 'https://api.exorde.io',
                'free_credits': 1000,
                'endpoints': {
                    'sentiment': '/sentiment',
                    'emotions': '/emotions',
                    'volume': '/volume'
                }
            }
        }

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": "多源情绪数据插件",
            "version": "1.0.0",
            "author": "FactorWeave-Quant  Team",
            "email": "support@factorweave.com",
            "website": "https://github.com/factorweave/FactorWeave-Quant ",
            "license": "MIT",
            "description": "集成多种免费情绪分析API：FMP、Exorde、AI Market Mood等，提供全面的市场情绪数据",
            "plugin_type": PluginType.DATA_SOURCE,
            "category": PluginCategory.CORE,
            "dependencies": ["requests>=2.25.0", "pandas>=1.3.0", "numpy>=1.20.0"],
            "min_framework_version": "1.0.0",
            "max_framework_version": "2.0.0",
            "documentation_url": "https://site.financialmodelingprep.com/developer/docs",
            "tags": ["sentiment", "emotion", "multi-source", "fmp", "exorde", "free"]
        }

    def _fetch_raw_sentiment_data(self, **kwargs) -> SentimentResponse:
        """获取原始情绪数据"""
        try:
            logger.warning("多源情绪插件：所有数据源未配置真实API，无法获取市场数据")
            # 此插件使用模拟数据，已被禁用
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message="多源情绪插件已禁用，请使用专门的数据源插件（如FMP、VIX等）",
                data_quality="unavailable",
                update_time=datetime.now()
            )
        except Exception as e:
            self._safe_log("error", f"多源情绪数据获取失败: {e}")
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message=f"数据获取异常: {str(e)}",
                data_quality="error",
                update_time=datetime.now()
            )

    def _fetch_fmp_sentiment(self) -> List[SentimentData]:
        logger.warning("FMP情绪API: 当前无真实API配置，无法获取FMP社交情绪数据")
        return []

    def _fetch_exorde_sentiment(self) -> List[SentimentData]:
        logger.warning("Exorde情绪API: 当前无真实API配置，无法获取Exorde情绪数据")
        return []

    def _fetch_news_sentiment(self) -> List[SentimentData]:
        logger.warning("新闻情绪API: 当前无真实API配置，无法获取新闻情绪数据")
        return []

    def _fetch_vix_simulation(self) -> Optional[SentimentData]:
        logger.warning("VIX指数: 当前无真实API配置，无法获取VIX恐慌指数数据")
        return None

    def _fetch_crypto_sentiment(self) -> Optional[SentimentData]:
        logger.warning("加密市场情绪: 当前无真实API配置，无法获取Crypto Fear&Greed数据")
        return None

    def _calculate_composite_score(self, sentiment_data: List[SentimentData]) -> float:
        """计算多源综合情绪指数"""
        if not sentiment_data:
            return 50.0

        total_weighted_score = 0.0
        total_weight = 0.0

        # 多源权重设定
        source_weights = {
            "FMP-社交": 0.25,
            "Exorde-27情绪": 0.20,
            "新闻-财经新闻": 0.15,
            "新闻-分析师报告": 0.15,
            "新闻-公司公告": 0.10,
            "VIX-模拟": 0.20,  # VIX需要反向处理
            "Crypto-Fear&Greed": 0.10
        }

        for data in sentiment_data:
            # 从source中提取权重key
            weight_key = next((key for key in source_weights.keys()
                               if key in data.source), "default")
            weight = source_weights.get(weight_key, 0.05)

            confidence = data.confidence if data.confidence else 0.5
            adjusted_weight = weight * confidence

            # VIX反向处理
            if "VIX" in data.source:
                # VIX越低，情绪越乐观
                if data.value <= 15:
                    sentiment_score = 80
                elif data.value <= 25:
                    sentiment_score = 60
                elif data.value <= 35:
                    sentiment_score = 40
                else:
                    sentiment_score = 20
            else:
                sentiment_score = data.value

            total_weighted_score += sentiment_score * adjusted_weight
            total_weight += adjusted_weight

        if total_weight > 0:
            composite_score = total_weighted_score / total_weight
        else:
            composite_score = 50.0

        return max(0.0, min(100.0, round(composite_score, 2)))

    def get_api_usage_info(self) -> Dict[str, Any]:
        """获取API使用情况信息"""
        return {
            "apis_available": [
                {
                    "name": "Financial Modeling Prep",
                    "free_tier": "250 requests/day",
                    "features": ["社交情绪", "新闻情绪", "趋势分析"],
                    "cost": "免费使用"
                },
                {
                    "name": "Exorde API",
                    "free_tier": "1000 credits",
                    "features": ["27种情绪分析", "社交监听", "趋势检测"],
                    "cost": "$20/月起"
                },
                {
                    "name": "AI Market Mood",
                    "free_tier": "基础使用免费",
                    "features": ["新闻聚合", "情绪分析", "市场预测"],
                    "cost": "免费 + 付费升级"
                }
            ],
            "recommendation": "建议组合使用多个免费额度，获得更全面的情绪数据"
        }

    def get_available_indicators(self) -> List[str]:
        """获取可用的情绪指标列表"""
        return [
            "FMP社交情绪",
            "市场情绪光谱",
            "财经新闻情绪",
            "分析师报告情绪",
            "公司公告情绪",
            "市场恐慌指数",
            "加密市场情绪"
        ]

# 插件工厂函数
def create_multi_source_sentiment_plugin() -> MultiSourceSentimentPlugin:
    """创建多源情绪数据插件实例"""
    return MultiSourceSentimentPlugin()

if __name__ == "__main__":
    # 测试插件
    plugin = create_multi_source_sentiment_plugin()

    # 初始化
    plugin.initialize(None)

    # 获取数据
    response = plugin._fetch_raw_sentiment_data()

    logger.info(f"成功: {response.success}")
    logger.info(f"数据项: {len(response.data)}")
    logger.info(f"综合指数: {response.composite_score}")

    if response.data:
        for item in response.data:
            logger.info(f"- {item.indicator_name}: {item.value} ({item.status})")

    # API使用信息
    usage_info = plugin.get_api_usage_info()
    logger.info(f"\nAPI信息: {json.dumps(usage_info, indent=2, ensure_ascii=False)}")
