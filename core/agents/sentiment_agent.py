"""
舆情分析Agent
负责市场情绪分析和社交媒体舆情监控
"""

import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
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
    """舆情分析Agent"""

    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__(event_bus)
        
        # 模拟数据源配置
        self.data_sources = [
            "news_api",
            "social_media",
            "financial_forums",
            "analyst_reports"
        ]
        
        # 舆情关键词库
        self.sentiment_keywords = {
            'positive': ['利好', '上涨', '突破', '买入', '推荐', '乐观', '前景'],
            'negative': ['利空', '下跌', '破位', '卖出', '警告', '悲观', '风险'],
            'neutral': ['持平', '震荡', '观望', '等待', '中性']
        }
        
        # 性能指标
        self._metrics = {
            'analyses_count': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'average_response_time': 0.0,
            'data_sources_status': {source: 'active' for source in self.data_sources}
        }

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
        # 模拟初始化各个数据源
        for source in self.data_sources:
            try:
                # 实际项目中这里会连接真实的数据源API
                logger.debug(f"连接数据源: {source}")
                await asyncio.sleep(0.1)  # 模拟连接时间
            except Exception as e:
                logger.error(f"数据源 {source} 连接失败: {e}")
                self._metrics['data_sources_status'][source] = 'error'

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
        # 模拟从多个数据源收集舆情数据
        sentiment_data = {
            'raw_data': {},
            'sources': [],
            'keywords': [],
            'trending_score': 0.0,
            'volume': 0  # 讨论量
        }
        
        # 模拟从新闻API收集数据
        news_data = await self._fetch_news_sentiment(stock_code)
        sentiment_data['raw_data']['news'] = news_data
        sentiment_data['sources'].append('news_api')
        
        # 模拟从社交媒体收集数据
        social_data = await self._fetch_social_sentiment(stock_code)
        sentiment_data['raw_data']['social'] = social_data
        sentiment_data['sources'].append('social_media')
        
        # 模拟从财经论坛收集数据
        forum_data = await self._fetch_forum_sentiment(stock_code)
        sentiment_data['raw_data']['forum'] = forum_data
        sentiment_data['sources'].append('financial_forums')
        
        # 模拟从分析师报告收集数据
        analyst_data = await self._fetch_analyst_sentiment(stock_code)
        sentiment_data['raw_data']['analyst'] = analyst_data
        sentiment_data['sources'].append('analyst_reports')
        
        return sentiment_data

    async def _fetch_news_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取新闻舆情数据"""
        # 模拟API调用延迟
        await asyncio.sleep(0.1)
        
        # 模拟新闻数据
        import random
        return {
            'articles_count': random.randint(5, 50),
            'sentiment_distribution': {
                'positive': random.uniform(0.2, 0.6),
                'negative': random.uniform(0.1, 0.4),
                'neutral': random.uniform(0.1, 0.3)
            },
            'keywords': random.sample(['业绩', '增长', '投资', '合作', '创新'], 3),
            'trending_score': random.uniform(0.1, 0.9)
        }

    async def _fetch_social_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取社交媒体舆情数据"""
        await asyncio.sleep(0.1)
        
        import random
        return {
            'posts_count': random.randint(10, 200),
            'sentiment_distribution': {
                'positive': random.uniform(0.3, 0.7),
                'negative': random.uniform(0.1, 0.3),
                'neutral': random.uniform(0.1, 0.4)
            },
            'keywords': random.sample(['热门', '关注', '讨论', '看法', '建议'], 3),
            'trending_score': random.uniform(0.2, 0.8)
        }

    async def _fetch_forum_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取财经论坛舆情数据"""
        await asyncio.sleep(0.1)
        
        import random
        return {
            'threads_count': random.randint(3, 30),
            'sentiment_distribution': {
                'positive': random.uniform(0.2, 0.5),
                'negative': random.uniform(0.2, 0.4),
                'neutral': random.uniform(0.2, 0.4)
            },
            'keywords': random.sample(['分析', '观点', '预测', '评价', '讨论'], 3),
            'trending_score': random.uniform(0.1, 0.6)
        }

    async def _fetch_analyst_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取分析师报告舆情数据"""
        await asyncio.sleep(0.1)
        
        import random
        return {
            'reports_count': random.randint(1, 10),
            'sentiment_distribution': {
                'positive': random.uniform(0.3, 0.6),
                'negative': random.uniform(0.1, 0.3),
                'neutral': random.uniform(0.2, 0.4)
            },
            'keywords': random.sample(['评级', '目标价', '评级', '前景', '建议'], 3),
            'trending_score': random.uniform(0.3, 0.9)
        }

    async def _analyze_sentiment_trend(self, sentiment_data: Dict[str, Any],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """分析舆情趋势"""
        # 模拟趋势分析
        import random
        
        trend_analysis = {
            'direction': random.choice(['improving', 'declining', 'stable']),
            'momentum': random.uniform(-1.0, 1.0),  # -1到1，负数表示下降趋势
            'volatility': random.uniform(0.1, 0.8),  # 舆情波动性
            'peak_activity': datetime.now() - timedelta(minutes=random.randint(5, 60)),
            'trend_strength': random.uniform(0.0, 1.0)
        }
        
        return trend_analysis

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
        scores = []
        for source_data in raw_data.values():
            if 'sentiment_distribution' in source_data:
                dist = source_data['sentiment_distribution']
                score = dist['positive'] - dist['negative']
                scores.append(score)
        
        if len(scores) < 2:
            return 0.5
        
        # 计算得分方差（方差越小，一致性越高）
        import statistics
        try:
            variance = statistics.variance(scores)
            consistency = max(0.0, 1.0 - variance)
        except:
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
                # 模拟舆情趋势监控
                await asyncio.sleep(300)  # 5分钟检查一次
                
                # 这里可以实现实时舆情趋势监控
                # 例如：检测异常舆情波动、热点事件等
                
            except Exception as e:
                logger.error(f"舆情趋势监控异常: {e}")
                await asyncio.sleep(60)  # 异常时等待1分钟再继续

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
