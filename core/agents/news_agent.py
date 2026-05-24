"""
BettaFish新闻分析Agent
专门处理股票相关的新闻信息分析
"""

import asyncio
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from core.services.base_service import BaseService

class NewsType(Enum):
    """新闻类型"""
    COMPANY_NEWS = "company_news"        # 公司新闻
    INDUSTRY_NEWS = "industry_news"      # 行业新闻
    MARKET_NEWS = "market_news"          # 市场新闻
    REGULATORY_NEWS = "regulatory_news"  # 监管新闻
    FINANCIAL_NEWS = "financial_news"    # 财务新闻

class NewsImpact(Enum):
    """新闻影响级别"""
    VERY_POSITIVE = "very_positive"      # 非常积极
    POSITIVE = "positive"                # 积极
    NEUTRAL = "neutral"                  # 中性
    NEGATIVE = "negative"                # 消极
    VERY_NEGATIVE = "very_negative"      # 非常消极

@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    content: str
    source: str
    publish_time: datetime
    news_type: NewsType
    impact_level: NewsImpact
    confidence: float
    url: Optional[str] = None
    keywords: List[str] = None
    source_type: str = 'price_proxy'

@dataclass
class NewsAnalysisResult:
    """新闻分析结果"""
    stock_code: str
    analysis_time: datetime
    news_count: int
    sentiment_score: float  # -1 to 1
    impact_analysis: Dict[str, float]
    key_themes: List[str]
    recommendations: List[str]
    confidence: float

class NewsAnalysisAgent(BaseService):
    """
    新闻分析Agent

    当前版本使用实时行情价格代理(price_proxy)作为新闻数据源。
    _collect_news_data基于真实行情快照生成市场动态类NewsItem，NewsItem.source_type标记为'price_proxy'。
    如需启用真实新闻数据源（新闻API抓取等），请调用 enable_real_sources()。
    """
    
    def __init__(self, event_bus: Optional[Any] = None):
        super().__init__(event_bus)
        
        # 新闻数据源配置
        self.news_sources = [
            "sina_finance",
            "east_money", 
            "hexun_finance",
            "10jqka",
            "xueqiu"
        ]

        self._use_real_sources = False
        
        # 分析配置
        self.config = {
            "max_news_per_query": 50,
            "analysis_window_hours": 24,
            "min_confidence_threshold": 0.6,
            "sentiment_weights": {
                "title": 0.3,
                "content": 0.7
            }
        }
        
        # 缓存
        self._news_cache = {}
        self._cache_ttl = 1800  # 30分钟
        
        # 性能统计
        self._stats = {
            "total_analyses": 0,
            "cache_hits": 0,
            "avg_processing_time": 0.0
        }

    def enable_real_sources(self):
        """
        启用真实新闻数据源（框架预留接口）
        
        当前版本未实现真实新闻API连接，调用此方法后仅更改为标记状态。
        待后续版本集成新闻抓取API后生效。
        """
        self._use_real_sources = True
        logger.info("新闻Agent: 已标记启用真实数据源（框架预留）")

    def disable_real_sources(self):
        """
        禁用真实新闻数据源，回退到行情价格代理模式
        """
        self._use_real_sources = False
        logger.info("新闻Agent: 已回退到价格代理模式")

    async def analyze_stock(self, stock_code: str, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析指定股票的新闻"""
        start_time = time.time()
        context = context or {}
        
        try:
            logger.debug(f"开始新闻分析: {stock_code}")
            
            # 检查缓存
            cache_key = f"news_analysis_{stock_code}_{int(time.time() // self._cache_ttl)}"
            if cache_key in self._news_cache:
                self._stats["cache_hits"] += 1
                logger.debug(f"新闻分析缓存命中: {stock_code}")
                return self._news_cache[cache_key]
            
            # 收集新闻数据
            news_items = await self._collect_news_data(stock_code, context)
            has_real_data = len(news_items) > 0
            
            if not news_items:
                logger.warning(f"未找到{stock_code}相关新闻")
                return {
                    "status": "no_news",
                    "message": "未找到相关新闻数据",
                    "stock_code": stock_code,
                    "has_real_data": False
                }
            
            # 分析新闻内容
            analysis_result = await self._analyze_news_content(news_items, stock_code)
            analysis_result["has_real_data"] = has_real_data
            
            # 缓存结果
            self._news_cache[cache_key] = analysis_result
            self._stats["total_analyses"] += 1
            
            processing_time = time.time() - start_time
            self._update_processing_stats(processing_time)
            
            logger.info(f"新闻分析完成: {stock_code}, 耗时: {processing_time:.2f}s")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"新闻分析失败: {stock_code}, 错误: {str(e)}")
            return {
                "status": "error",
                "message": f"新闻分析失败: {str(e)}",
                "stock_code": stock_code,
                "has_real_data": False
            }

    async def _collect_news_data(self, stock_code: str,
                               context: Dict[str, Any] = None) -> List[NewsItem]:
        try:
            from core.real_data_provider import get_real_data_provider

            provider = get_real_data_provider()
            quote = provider.get_real_quote(stock_code)

            if not quote:
                logger.warning(f"无法获取{stock_code}真实行情数据，新闻列表为空")
                return []

            price = quote.get('price', 0)
            change_pct = quote.get('change_pct', 0)
            name = quote.get('name', stock_code)
            volume = quote.get('volume', 0)

            news_items = []

            if change_pct is not None and price > 0:
                pct_str = f"{change_pct:+.2f}%"
                if change_pct > 0:
                    direction = "上涨"
                    impact = NewsImpact.POSITIVE
                elif change_pct < 0:
                    direction = "下跌"
                    impact = NewsImpact.NEGATIVE
                else:
                    direction = "持平"
                    impact = NewsImpact.NEUTRAL

                news_items.append(NewsItem(
                    title=f"{name}({stock_code})今日{direction}{abs(change_pct):.2f}%",
                    content=f"{name}({stock_code})当前价格{price:.2f}元，今日{direction}{abs(change_pct):.2f}%，成交量{volume}",
                    source="实时行情",
                    publish_time=datetime.now(),
                    news_type=NewsType.MARKET_NEWS,
                    impact_level=impact,
                    confidence=0.9,
                    keywords=["行情", "涨跌", stock_code],
                    source_type='price_proxy'
                ))

            logger.debug(f"基于真实行情生成{len(news_items)}条市场动态")
            return news_items

        except ImportError as e:
            logger.warning(f"RealDataProvider不可用: {e}")
            return []
        except Exception as e:
            logger.error(f"收集新闻数据失败: {str(e)}")
            return []

    async def _analyze_news_content(self, news_items: List[NewsItem], 
                                  stock_code: str) -> Dict[str, Any]:
        """分析新闻内容"""
        try:
            # 计算整体情绪得分
            sentiment_scores = []
            impact_weights = []
            
            for news in news_items:
                # 根据新闻类型和影响级别计算得分
                base_score = self._calculate_sentiment_score(news)
                time_weight = self._calculate_time_weight(news.publish_time)
                confidence_weight = news.confidence
                
                final_score = base_score * time_weight * confidence_weight
                sentiment_scores.append(final_score)
                impact_weights.append(confidence_weight)
            
            # 加权平均计算总体情绪
            if sentiment_scores:
                total_weight = sum(impact_weights)
                overall_sentiment = sum(s * w for s, w in zip(sentiment_scores, impact_weights)) / total_weight
            else:
                overall_sentiment = 0.0
            
            # 分析关键主题
            key_themes = self._extract_key_themes(news_items)
            
            # 生成建议
            recommendations = self._generate_recommendations(overall_sentiment, news_items)
            
            # 构建分析结果
            analysis_result = NewsAnalysisResult(
                stock_code=stock_code,
                analysis_time=datetime.now(),
                news_count=len(news_items),
                sentiment_score=overall_sentiment,
                impact_analysis=self._analyze_impact_distribution(news_items),
                key_themes=key_themes,
                recommendations=recommendations,
                confidence=min(0.9, sum(n.confidence for n in news_items) / len(news_items))
            )
            
            return {
                "status": "success",
                "analysis_result": analysis_result,
                "raw_news": [
                    {
                        "title": news.title,
                        "source": news.source,
                        "publish_time": news.publish_time.isoformat(),
                        "news_type": news.news_type.value,
                        "impact_level": news.impact_level.value,
                        "confidence": news.confidence,
                        "keywords": news.keywords
                    }
                    for news in news_items
                ]
            }
            
        except Exception as e:
            logger.error(f"分析新闻内容失败: {str(e)}")
            raise

    def _calculate_sentiment_score(self, news: NewsItem) -> float:
        """计算新闻情绪得分"""
        # 基于影响级别的基础得分
        impact_scores = {
            NewsImpact.VERY_POSITIVE: 0.8,
            NewsImpact.POSITIVE: 0.4,
            NewsImpact.NEUTRAL: 0.0,
            NewsImpact.NEGATIVE: -0.4,
            NewsImpact.VERY_NEGATIVE: -0.8
        }
        
        return impact_scores.get(news.impact_level, 0.0)

    def _calculate_time_weight(self, publish_time: datetime) -> float:
        """计算时间权重"""
        now = datetime.now()
        hours_ago = (now - publish_time).total_seconds() / 3600
        
        # 时间衰减函数
        if hours_ago <= 1:
            return 1.0
        elif hours_ago <= 6:
            return 0.9
        elif hours_ago <= 24:
            return 0.7
        else:
            return 0.5

    def _extract_key_themes(self, news_items: List[NewsItem]) -> List[str]:
        """提取关键主题"""
        theme_counter = {}
        
        for news in news_items:
            if news.keywords:
                for keyword in news.keywords:
                    theme_counter[keyword] = theme_counter.get(keyword, 0) + 1
        
        # 按频次排序，返回前5个主题
        sorted_themes = sorted(theme_counter.items(), key=lambda x: x[1], reverse=True)
        return [theme for theme, count in sorted_themes[:5]]

    def _generate_recommendations(self, sentiment_score: float, 
                                news_items: List[NewsItem]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if sentiment_score > 0.5:
            recommendations.append("新闻情绪偏向积极，可关注后续发展")
            recommendations.append("结合基本面分析考虑是否加仓")
        elif sentiment_score < -0.5:
            recommendations.append("新闻情绪偏向消极，建议谨慎操作")
            recommendations.append("关注风险控制，避免过度暴露")
        else:
            recommendations.append("新闻情绪相对中性，保持观望态度")
        
        # 基于新闻类型给出具体建议
        recent_financial_news = any(n.news_type == NewsType.FINANCIAL_NEWS 
                                  for n in news_items)
        if recent_financial_news:
            recommendations.append("关注即将发布的财务报告和业绩预期")
        
        recent_regulatory_news = any(n.news_type == NewsType.REGULATORY_NEWS 
                                   for n in news_items)
        if recent_regulatory_news:
            recommendations.append("密切关注监管政策变化对业务的影响")
        
        return recommendations

    def _analyze_impact_distribution(self, news_items: List[NewsItem]) -> Dict[str, float]:
        """分析影响分布"""
        impact_distribution = {
            "positive_ratio": 0.0,
            "negative_ratio": 0.0,
            "neutral_ratio": 0.0,
            "high_impact_ratio": 0.0
        }
        
        if not news_items:
            return impact_distribution
        
        positive_count = sum(1 for n in news_items 
                           if n.impact_level in [NewsImpact.POSITIVE, NewsImpact.VERY_POSITIVE])
        negative_count = sum(1 for n in news_items 
                           if n.impact_level in [NewsImpact.NEGATIVE, NewsImpact.VERY_NEGATIVE])
        high_impact_count = sum(1 for n in news_items if n.confidence > 0.8)
        
        total_count = len(news_items)
        
        impact_distribution["positive_ratio"] = positive_count / total_count
        impact_distribution["negative_ratio"] = negative_count / total_count
        impact_distribution["neutral_ratio"] = (total_count - positive_count - negative_count) / total_count
        impact_distribution["high_impact_ratio"] = high_impact_count / total_count
        
        return impact_distribution

    def _update_processing_stats(self, processing_time: float):
        """更新处理统计"""
        current_avg = self._stats["avg_processing_time"]
        total_analyses = self._stats["total_analyses"]
        
        # 移动平均
        self._stats["avg_processing_time"] = (current_avg * (total_analyses - 1) + processing_time) / total_analyses

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "total_analyses": self._stats["total_analyses"],
            "cache_hits": self._stats["cache_hits"],
            "cache_hit_rate": self._stats["cache_hits"] / max(1, self._stats["total_analyses"]),
            "avg_processing_time": self._stats["avg_processing_time"],
            "cache_size": len(self._news_cache)
        }

    async def cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self._news_cache.items()
            if isinstance(value, dict) and "analysis_time" in value
            and isinstance(value["analysis_time"], datetime)
            and (current_time - value["analysis_time"].timestamp()) > self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._news_cache[key]
        
        logger.debug(f"清理了{len(expired_keys)}个过期缓存项")