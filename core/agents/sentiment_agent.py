"""
舆情分析Agent
负责市场情绪分析和社交媒体舆情监控
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

import numpy as np
from loguru import logger

from ..services.base_service import BaseService
from ..events import EventBus, get_event_bus


@dataclass
class SentimentData:
    """舆情数据"""
    stock_code: str
    sentiment_score: float  # -1.0到1.0
    sentiment_type: str  # 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
    confidence: float  # 0.0到1.0
    source_count: int  # 数据源数量
    data_sources: List[str]  # 数据源列表
    keywords: List[str]  # 关键词
    trending_score: float  # 热度分数
    timestamp: datetime


class SentimentAnalysisAgent(BaseService):
    """
    舆情分析Agent

    当前版本使用K线价格代理(price_proxy)作为舆情数据源。
    各_fetch_*方法均基于真实K线数据计算动量、成交量、波动率、均线排列等指标来模拟舆情情绪。
    如需启用真实舆情数据源（新闻API、社交媒体等），请调用 enable_real_sources()。
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__(event_bus)
        
        self.has_real_data = False
        
        self._use_real_sources = False
        
        self._data_provider = None
        
        self.data_sources = [
            "news_api",
            "social_media",
            "financial_forums",
            "analyst_reports"
        ]
        
        self.sentiment_keywords = {
            'positive': ['利好', '上涨', '突破', '买入', '推荐', '乐观', '前景'],
            'negative': ['利空', '下跌', '破位', '卖出', '警告', '悲观', '风险'],
            'neutral': ['持平', '震荡', '观望', '等待', '中性']
        }
        
        self._metrics = {
            'analyses_count': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'average_response_time': 0.0,
            'data_sources_status': {source: 'active' for source in self.data_sources}
        }

    def enable_real_sources(self):
        """
        启用真实舆情数据源（框架预留接口）
        
        当前版本未实现真实数据源连接，调用此方法后仅更改为标记状态。
        待后续版本集成新闻API、社交媒体API等真实数据源后生效。
        """
        self._use_real_sources = True
        logger.info("舆情Agent: 已标记启用真实数据源（框架预留）")

    def disable_real_sources(self):
        """
        禁用真实舆情数据源，回退到K线价格代理模式
        """
        self._use_real_sources = False
        logger.info("舆情Agent: 已回退到价格代理模式")

    async def initialize(self) -> None:
        """初始化舆情分析Agent"""
        if self._initialized:
            return
            
        try:
            logger.info("初始化舆情分析Agent...")
            
            # 初始化数据源连接
            await self._initialize_data_sources()
            
            # 启动舆情监控任务
            asyncio.create_task(self._monitor_sentiment_trends())
            
            self._initialized = True
            logger.info("舆情分析Agent初始化完成")
            
        except Exception as e:
            logger.error(f"舆情分析Agent初始化失败: {e}")
            raise

    async def _initialize_data_sources(self):
        """初始化数据源连接"""
        for source in self.data_sources:
            try:
                logger.debug(f"连接数据源: {source}")
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"数据源 {source} 连接失败: {e}")
                self._metrics['data_sources_status'][source] = 'error'

    def _get_data_provider(self):
        if self._data_provider is None:
            from core.real_data_provider import get_real_data_provider
            self._data_provider = get_real_data_provider()
        return self._data_provider

    def _compute_ema(self, data: np.ndarray, period: int) -> float:
        if len(data) < 2:
            return float(data[-1])
        alpha = 2.0 / (period + 1.0)
        ema = float(data[0])
        for i in range(1, len(data)):
            ema = alpha * float(data[i]) + (1.0 - alpha) * ema
        return ema

    def _compute_macd(self, close: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = len(close)
        alpha12 = 2.0 / 13.0
        alpha26 = 2.0 / 27.0
        alpha9 = 2.0 / 10.0
        
        ema12 = np.zeros(n)
        ema26 = np.zeros(n)
        ema12[0] = float(close[0])
        ema26[0] = float(close[0])
        
        for i in range(1, n):
            ema12[i] = alpha12 * float(close[i]) + (1.0 - alpha12) * ema12[i - 1]
            ema26[i] = alpha26 * float(close[i]) + (1.0 - alpha26) * ema26[i - 1]
        
        macd_line = ema12 - ema26
        
        signal = np.zeros(n)
        signal[0] = macd_line[0]
        for i in range(1, n):
            signal[i] = alpha9 * macd_line[i] + (1.0 - alpha9) * signal[i - 1]
        
        histogram = macd_line - signal
        
        return macd_line, signal, histogram

    async def analyze_stock(self, stock_code: str, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        分析指定股票的舆情
        
        Args:
            stock_code: 股票代码
            context: 分析上下文
            
        Returns:
            舆情分析结果
        """
        start_time = time.time()
        context = context or {}
        context.setdefault('stock_code', stock_code)
        
        try:
            logger.debug(f"开始舆情分析: {stock_code}")
            
            # 收集舆情数据
            sentiment_data = await self._collect_sentiment_data(stock_code, context)
            
            # 分析舆情趋势
            trend_analysis = await self._analyze_sentiment_trend(sentiment_data, context)
            
            # 生成舆情评分
            sentiment_score = self._calculate_sentiment_score(sentiment_data, trend_analysis)
            
            # 确定舆情类型
            sentiment_type = self._classify_sentiment_type(sentiment_score)
            
            # 计算置信度
            confidence = self._calculate_confidence(sentiment_data, trend_analysis)
            
            # 分析结果
            analysis_result = {
                'stock_code': stock_code,
                'sentiment_score': sentiment_score,
                'sentiment_type': sentiment_type,
                'confidence': confidence,
                'data_sources': sentiment_data.get('sources', []),
                'keyword_analysis': sentiment_data.get('keywords', []),
                'trend_analysis': trend_analysis,
                'trending_score': sentiment_data.get('trending_score', 0.0),
                'recommendation': self._generate_sentiment_recommendation(sentiment_score, confidence),
                'risk_factors': self._identify_risk_factors(sentiment_data),
                'data_quality': 'price_proxy',
                'timestamp': datetime.now()
            }
            
            # 更新指标
            response_time = time.time() - start_time
            self._update_metrics(response_time, True)
            
            # 发布分析完成事件
            self.event_bus.publish('bettafish.sentiment.analysis.completed',
                stock_code=stock_code,
                sentiment_score=sentiment_score,
                confidence=confidence,
                response_time=response_time
            )
            
            logger.debug(f"舆情分析完成: {stock_code}, 得分: {sentiment_score:.2f}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"舆情分析失败: {stock_code}, 错误: {e}")
            self._update_metrics(0, False)
            raise

    async def _collect_sentiment_data(self, stock_code: str, 
                                    context: Dict[str, Any]) -> Dict[str, Any]:
        """收集舆情数据"""
        sentiment_data = {
            'stock_code': stock_code,
            'raw_data': {},
            'sources': [],
            'keywords': [],
            'trending_score': 0.0,
            'volume': 0
        }
        
        news_data = await self._fetch_news_sentiment(stock_code)
        sentiment_data['raw_data']['news'] = news_data
        sentiment_data['sources'].append('news_api')
        
        social_data = await self._fetch_social_sentiment(stock_code)
        sentiment_data['raw_data']['social'] = social_data
        sentiment_data['sources'].append('social_media')
        
        forum_data = await self._fetch_forum_sentiment(stock_code)
        sentiment_data['raw_data']['forum'] = forum_data
        sentiment_data['sources'].append('financial_forums')
        
        analyst_data = await self._fetch_analyst_sentiment(stock_code)
        sentiment_data['raw_data']['analyst'] = analyst_data
        sentiment_data['sources'].append('analyst_reports')
        
        return sentiment_data

    async def _fetch_news_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取新闻舆情数据 (价格动量代理)"""
        try:
            provider = self._get_data_provider()
            df = provider.get_real_kdata(stock_code, freq='D', count=30)
            
            if df.empty or len(df) < 5:
                logger.warning(f"新闻情绪代理: {stock_code} 无法获取足够K线数据")
                return {'articles_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0}
            
            close = df['close'].values.astype(np.float64)
            n = len(close)
            
            pct_5d = float((close[-1] - close[-5]) / close[-5]) if n >= 5 else 0.0
            
            recent_delta = np.diff(close[-min(15, n):])
            gain = float(np.sum(recent_delta[recent_delta > 0]))
            loss = float(-np.sum(recent_delta[recent_delta < 0]))
            rs = gain / loss if loss > 1e-10 else 100.0
            rsi = 100.0 - (100.0 / (1.0 + rs))
            rsi_signal = (rsi - 50.0) / 50.0
            
            ema12 = self._compute_ema(close[-min(26, n):], 12)
            ema26 = self._compute_ema(close[-min(26, n):], 26)
            macd_raw = ema12 - ema26
            
            trend_score = float(np.tanh(pct_5d * 10.0 + rsi_signal * 2.0 + macd_raw * 5.0))
            
            if trend_score > 0.15:
                pos = 0.45 + trend_score * 0.25
                neg = 0.20 - trend_score * 0.12
                neu = 1.0 - pos - neg
            elif trend_score < -0.15:
                neg = 0.45 - trend_score * 0.25
                pos = 0.20 + trend_score * 0.12
                neu = 1.0 - pos - neg
            else:
                pos, neg = 0.30, 0.28
                neu = 0.42
            
            pos = float(np.clip(pos, 0.05, 0.75))
            neg = float(np.clip(neg, 0.05, 0.75))
            neu = float(np.clip(neu, 0.05, 0.75))
            total = pos + neg + neu
            pos, neg, neu = pos / total, neg / total, neu / total
            
            trending = float(np.clip(abs(pct_5d * 5.0) + abs(trend_score), 0.05, 0.95))
            
            keywords = ['动量']
            if trend_score > 0.3:
                keywords = ['上涨动量', '价格强势', '突破']
            elif trend_score < -0.3:
                keywords = ['下跌动量', '价格弱势', '破位']
            
            return {
                'articles_count': len(df),
                'sentiment_distribution': {'positive': pos, 'negative': neg, 'neutral': neu},
                'keywords': keywords,
                'trending_score': trending,
                'data_source': 'price_proxy'
            }
        except Exception as e:
            logger.warning(f"新闻情绪代理获取失败 {stock_code}: {e}")
            return {'articles_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0, 'data_source': 'price_proxy'}

    async def _fetch_social_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取社交媒体舆情数据 (成交量情绪代理)"""
        try:
            provider = self._get_data_provider()
            df = provider.get_real_kdata(stock_code, freq='D', count=30)
            
            if df.empty or len(df) < 5:
                logger.warning(f"社交媒体情绪代理: {stock_code} 无法获取足够K线数据")
                return {'posts_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0}
            
            close = df['close'].values.astype(np.float64)
            volume = df['volume'].values.astype(np.float64)
            n = len(close)
            
            price_chg = np.diff(close[-min(10, n):])
            vol_chg = np.diff(volume[-min(10, n):])
            
            if len(price_chg) > 2:
                corr_matrix = np.corrcoef(price_chg, vol_chg)
                vol_price_corr = float(corr_matrix[0, 1]) if not np.isnan(corr_matrix[0, 1]) else 0.0
            else:
                vol_price_corr = 0.0
            
            avg_vol_ratio = float(volume[-min(5, n):].mean() / volume[-min(20, n):].mean()) if n >= 20 else 1.0
            
            recent_pct = float((close[-1] - close[-min(5, n)]) / close[-min(5, n)])
            
            score = float(np.tanh(recent_pct * 8.0 + vol_price_corr * 2.0))
            
            if avg_vol_ratio > 1.3:
                if recent_pct > 0:
                    pos, neg, neu = 0.55, 0.15, 0.30
                else:
                    pos, neg, neu = 0.15, 0.55, 0.30
            elif score > 0.1:
                pos, neg, neu = 0.45, 0.20, 0.35
            elif score < -0.1:
                pos, neg, neu = 0.20, 0.45, 0.35
            else:
                pos, neg, neu = 0.30, 0.30, 0.40
            
            pos = float(np.clip(pos, 0.05, 0.75))
            neg = float(np.clip(neg, 0.05, 0.75))
            neu = float(np.clip(neu, 0.05, 0.75))
            total = pos + neg + neu
            pos, neg, neu = pos / total, neg / total, neu / total
            
            trending = float(np.clip(abs(vol_price_corr) * avg_vol_ratio * 0.5, 0.05, 0.9))
            
            keywords = ['量价']
            if vol_price_corr > 0.5:
                keywords = ['放量', '量价齐升' if recent_pct > 0 else '放量下跌', '关注']
            elif vol_price_corr < -0.3:
                keywords = ['缩量', '背离']
            
            return {
                'posts_count': int(np.clip(volume[-min(5, n):].mean() / 1000.0, 1, 500)),
                'sentiment_distribution': {'positive': pos, 'negative': neg, 'neutral': neu},
                'keywords': keywords,
                'trending_score': trending,
                'data_source': 'price_proxy'
            }
        except Exception as e:
            logger.warning(f"社交媒体情绪代理获取失败 {stock_code}: {e}")
            return {'posts_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0, 'data_source': 'price_proxy'}

    async def _fetch_forum_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取财经论坛舆情数据 (波动率情绪代理)"""
        try:
            provider = self._get_data_provider()
            df = provider.get_real_kdata(stock_code, freq='D', count=30)
            
            if df.empty or len(df) < 5:
                logger.warning(f"论坛情绪代理: {stock_code} 无法获取足够K线数据")
                return {'threads_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0}
            
            close = df['close'].values.astype(np.float64)
            high = df['high'].values.astype(np.float64)
            low = df['low'].values.astype(np.float64)
            n = len(close)
            
            daily_range = (high - low) / close
            atr = float(daily_range[-min(14, n):].mean())
            
            returns = np.diff(close) / close[:-1]
            volatility = float(returns[-min(20, len(returns)):].std() * np.sqrt(252))
            
            trend_10d = float((close[-1] - close[-min(10, n)]) / close[-min(10, n)])
            
            vol_ratio = volatility / 0.3
            
            if vol_ratio > 1.5:
                pos, neg, neu = 0.20, 0.25, 0.55
            elif vol_ratio > 0.8:
                if trend_10d > 0.02:
                    pos, neg, neu = 0.40, 0.20, 0.40
                elif trend_10d < -0.02:
                    pos, neg, neu = 0.20, 0.40, 0.40
                else:
                    pos, neg, neu = 0.28, 0.28, 0.44
            else:
                if trend_10d > 0.02:
                    pos, neg, neu = 0.50, 0.15, 0.35
                elif trend_10d < -0.02:
                    pos, neg, neu = 0.15, 0.50, 0.35
                else:
                    pos, neg, neu = 0.30, 0.30, 0.40
            
            pos = float(np.clip(pos, 0.05, 0.75))
            neg = float(np.clip(neg, 0.05, 0.75))
            neu = float(np.clip(neu, 0.05, 0.75))
            total = pos + neg + neu
            pos, neg, neu = pos / total, neg / total, neu / total
            
            trending = float(np.clip(volatility * 2.0, 0.05, 0.8))
            
            keywords = ['波动']
            if volatility > 0.4:
                keywords = ['高波动', '分歧', '观望']
            elif trend_10d > 0.03:
                keywords = ['趋势向上', '共识']
            elif trend_10d < -0.03:
                keywords = ['趋势向下', '共识']
            
            return {
                'threads_count': max(1, n // 2),
                'sentiment_distribution': {'positive': pos, 'negative': neg, 'neutral': neu},
                'keywords': keywords,
                'trending_score': trending,
                'data_source': 'price_proxy'
            }
        except Exception as e:
            logger.warning(f"论坛情绪代理获取失败 {stock_code}: {e}")
            return {'threads_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0, 'data_source': 'price_proxy'}

    async def _fetch_analyst_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取分析师报告舆情数据 (均线排列情绪代理)"""
        try:
            provider = self._get_data_provider()
            df = provider.get_real_kdata(stock_code, freq='D', count=120)
            
            if df.empty or len(df) < 60:
                logger.warning(f"分析师情绪代理: {stock_code} 无法获取足够K线数据，尝试较少数据")
                df = provider.get_real_kdata(stock_code, freq='D', count=30)
                if df.empty or len(df) < 20:
                    return {'reports_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0}
            
            close = df['close'].values.astype(np.float64)
            n = len(close)
            
            ma5 = float(close[-min(5, n):].mean())
            ma20 = float(close[-min(20, n):].mean())
            ma60 = float(close[-min(60, n):].mean()) if n >= 60 else float(close.mean())
            
            if ma5 > ma20 > ma60:
                pos, neg, neu = 0.55, 0.15, 0.30
                alignment = 'bullish'
                report_count = 5
            elif ma5 < ma20 < ma60:
                pos, neg, neu = 0.15, 0.55, 0.30
                alignment = 'bearish'
                report_count = 5
            elif abs(ma5 - ma20) / ma20 < 0.02:
                pos, neg, neu = 0.30, 0.30, 0.40
                alignment = 'sideways'
                report_count = 2
            else:
                ma5_20_diff = (ma5 - ma20) / ma20
                if ma5_20_diff > 0:
                    pos, neg, neu = 0.40, 0.25, 0.35
                else:
                    pos, neg, neu = 0.25, 0.40, 0.35
                alignment = 'mixed'
                report_count = 3
            
            pos = float(np.clip(pos, 0.05, 0.75))
            neg = float(np.clip(neg, 0.05, 0.75))
            neu = float(np.clip(neu, 0.05, 0.75))
            total = pos + neg + neu
            pos, neg, neu = pos / total, neg / total, neu / total
            
            trending = float(np.clip(abs(ma5 - ma60) / ma60 * 5.0, 0.1, 0.95))
            
            keywords = ['均线']
            if alignment == 'bullish':
                keywords = ['多头排列', '趋势向上', '看多']
            elif alignment == 'bearish':
                keywords = ['空头排列', '趋势向下', '看空']
            
            return {
                'reports_count': report_count,
                'sentiment_distribution': {'positive': pos, 'negative': neg, 'neutral': neu},
                'keywords': keywords,
                'trending_score': trending,
                'data_source': 'price_proxy'
            }
        except Exception as e:
            logger.warning(f"分析师情绪代理获取失败 {stock_code}: {e}")
            return {'reports_count': 0, 'sentiment_distribution': {'positive': 0.0, 'negative': 0.0, 'neutral': 0.0}, 'keywords': [], 'trending_score': 0.0, 'data_source': 'price_proxy'}

    async def _analyze_sentiment_trend(self, sentiment_data: Dict[str, Any],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """分析舆情趋势 (基于MACD柱状图变化方向)"""
        try:
            stock_code = sentiment_data.get('stock_code', context.get('stock_code', ''))
            if not stock_code:
                logger.warning("舆情趋势分析: 未提供股票代码")
                return {'direction': 'stable', 'momentum': 0.0, 'volatility': 0.2, 'peak_activity': datetime.now(), 'trend_strength': 0.0}
            
            provider = self._get_data_provider()
            df = provider.get_real_kdata(stock_code, freq='D', count=60)
            
            if df.empty or len(df) < 26:
                logger.warning(f"舆情趋势分析: {stock_code} 无法获取足够K线数据")
                return {'direction': 'stable', 'momentum': 0.0, 'volatility': 0.2, 'peak_activity': datetime.now(), 'trend_strength': 0.0}
            
            close = df['close'].values.astype(np.float64)
            
            macd_line, signal, histogram = self._compute_macd(close)
            
            recent_hist = histogram[-min(10, len(histogram)):]
            if len(recent_hist) >= 2:
                x = np.arange(len(recent_hist), dtype=np.float64)
                slope = float(np.polyfit(x, recent_hist, 1)[0])
            else:
                slope = 0.0
            
            if slope > 0.001:
                direction = 'improving'
                momentum = float(np.clip(slope * 500.0, 0.1, 1.0))
            elif slope < -0.001:
                direction = 'declining'
                momentum = float(np.clip(slope * 500.0, -1.0, -0.1))
            else:
                direction = 'stable'
                momentum = 0.0
            
            returns = np.diff(close[-20:]) / close[-21:-1]
            hist_volatility = float(np.std(returns) * 100)
            volatility = float(np.clip(hist_volatility / 5.0, 0.05, 0.8))
            
            trend_strength = float(np.clip(abs(momentum), 0.0, 1.0))
            
            return {
                'direction': direction,
                'momentum': momentum,
                'volatility': volatility,
                'peak_activity': datetime.now(),
                'trend_strength': trend_strength
            }
        except Exception as e:
            logger.warning(f"舆情趋势分析失败: {e}")
            return {'direction': 'stable', 'momentum': 0.0, 'volatility': 0.2, 'peak_activity': datetime.now(), 'trend_strength': 0.0}

    def _calculate_sentiment_score(self, sentiment_data: Dict[str, Any],
                                 trend_analysis: Dict[str, Any]) -> float:
        """计算舆情评分"""
        # 加权计算综合舆情得分
        weights = {
            'news': 0.3,
            'social': 0.25,
            'forum': 0.2,
            'analyst': 0.25
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for source, source_data in sentiment_data.get('raw_data', {}).items():
            if source in weights and 'sentiment_distribution' in source_data:
                dist = source_data['sentiment_distribution']
                # 计算该数据源的舆情得分
                source_score = (
                    dist['positive'] * 1.0 +
                    dist['neutral'] * 0.0 +
                    dist['negative'] * -1.0
                )
                
                total_score += source_score * weights[source]
                total_weight += weights[source]
        
        if total_weight > 0:
            base_score = total_score / total_weight
        else:
            base_score = 0.0
        
        # 考虑趋势影响
        trend_factor = trend_analysis.get('trend_strength', 0.5)
        trend_direction = trend_analysis.get('momentum', 0.0)
        
        # 最终得分 = 基础得分 + 趋势影响
        final_score = base_score + (trend_direction * trend_factor * 0.3)
        
        # 限制在-1到1范围内
        return max(-1.0, min(1.0, final_score))

    def _classify_sentiment_type(self, sentiment_score: float) -> str:
        """分类舆情类型"""
        if sentiment_score > 0.3:
            return 'POSITIVE'
        elif sentiment_score < -0.3:
            return 'NEGATIVE'
        else:
            return 'NEUTRAL'

    def _calculate_confidence(self, sentiment_data: Dict[str, Any],
                            trend_analysis: Dict[str, Any]) -> float:
        """计算置信度"""
        # 基于数据源数量和一致性计算置信度
        sources_count = len(sentiment_data.get('sources', []))
        max_sources = len(self.data_sources)
        
        source_confidence = min(1.0, sources_count / max_sources)
        
        # 考虑数据一致性
        raw_data = sentiment_data.get('raw_data', {})
        consistency_score = self._calculate_data_consistency(raw_data)
        
        # 考虑趋势强度
        trend_strength = trend_analysis.get('trend_strength', 0.5)
        
        # 综合置信度
        confidence = (source_confidence * 0.4 + 
                     consistency_score * 0.4 + 
                     trend_strength * 0.2)
        
        return min(1.0, max(0.0, confidence))

    def _calculate_data_consistency(self, raw_data: Dict[str, Any]) -> float:
        """计算数据一致性"""
        if len(raw_data) < 2:
            return 0.5
        
        # 简化的数据一致性计算
        scores = [
            source_data['sentiment_distribution']['positive'] - source_data['sentiment_distribution']['negative']
            for source_data in raw_data.values()
            if 'sentiment_distribution' in source_data
        ]
        
        if len(scores) < 2:
            return 0.5
        
        # 计算得分方差（方差越小，一致性越高）
        try:
            variance = float(np.var(scores, ddof=1)) if len(scores) >= 2 else 0.0
            consistency = max(0.0, 1.0 - variance)
        except Exception:
            consistency = 0.5
        
        return consistency

    def _generate_sentiment_recommendation(self, sentiment_score: float, 
                                         confidence: float) -> Dict[str, Any]:
        """生成舆情建议"""
        if sentiment_score > 0.5 and confidence > 0.7:
            return {
                'action': 'POSITIVE',
                'description': '舆情积极，建议关注',
                'strength': 'STRONG'
            }
        elif sentiment_score > 0.2 and confidence > 0.5:
            return {
                'action': 'SLIGHTLY_POSITIVE',
                'description': '舆情偏积极，可谨慎关注',
                'strength': 'MODERATE'
            }
        elif sentiment_score < -0.5 and confidence > 0.7:
            return {
                'action': 'NEGATIVE',
                'description': '舆情消极，建议谨慎',
                'strength': 'STRONG'
            }
        elif sentiment_score < -0.2 and confidence > 0.5:
            return {
                'action': 'SLIGHTLY_NEGATIVE',
                'description': '舆情偏消极，观望为宜',
                'strength': 'MODERATE'
            }
        else:
            return {
                'action': 'NEUTRAL',
                'description': '舆情中性，继续观察',
                'strength': 'WEAK'
            }

    def _identify_risk_factors(self, sentiment_data: Dict[str, Any]) -> List[str]:
        """识别风险因素"""
        risk_factors = []
        
        # 检查数据源状态
        for source, status in self._metrics['data_sources_status'].items():
            if status == 'error':
                risk_factors.append(f'数据源{source}连接异常')
        
        # 检查数据量
        total_volume = 0
        for source_data in sentiment_data.get('raw_data', {}).values():
            if 'posts_count' in source_data:
                total_volume += source_data['posts_count']
            elif 'articles_count' in source_data:
                total_volume += source_data['articles_count']
        
        if total_volume < 10:
            risk_factors.append('舆情数据量较少，分析可靠性较低')
        
        # 检查趋势波动性
        if len(sentiment_data.get('sources', [])) < 2:
            risk_factors.append('数据源不足，可能存在偏差')
        
        return risk_factors

    async def _monitor_sentiment_trends(self):
        """监控舆情趋势（后台任务）"""
        while self._is_running:
            try:
                await asyncio.sleep(300)
                
                provider = self._get_data_provider()
                if provider is not None:
                    try:
                        test_df = provider.get_real_kdata('000001', freq='D', count=1)
                        if test_df.empty:
                            logger.warning("舆情趋势监控: 数据提供器返回空数据，可能存在连接问题")
                        else:
                            logger.debug("舆情趋势监控: 数据提供器连接正常")
                    except Exception as probe_error:
                        logger.warning(f"舆情趋势监控: 数据提供器探测失败: {probe_error}")
                
            except Exception as e:
                logger.error(f"舆情趋势监控异常: {e}")
                await asyncio.sleep(60)

    def _update_metrics(self, response_time: float, success: bool):
        """更新性能指标"""
        self._metrics['analyses_count'] += 1
        
        if success:
            self._metrics['successful_analyses'] += 1
        else:
            self._metrics['failed_analyses'] += 1
        
        # 更新平均响应时间
        current_avg = self._metrics['average_response_time']
        total_count = self._metrics['analyses_count']
        self._metrics['average_response_time'] = (
            (current_avg * (total_count - 1) + response_time) / total_count
        )

    async def shutdown(self):
        """关闭舆情分析Agent"""
        try:
            self._is_running = False
            logger.info("舆情分析Agent已关闭")
        except Exception as e:
            logger.error(f"关闭舆情分析Agent失败: {e}")

    @property
    def metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self._metrics.copy()
