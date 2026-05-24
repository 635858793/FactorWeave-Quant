"""
BettaFish核心Agent
多智能体舆情分析系统的中央协调器
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from loguru import logger

from ..services.base_service import BaseService
from .sentiment_agent import SentimentAnalysisAgent
from .news_agent import NewsAnalysisAgent  
from .technical_agent import TechnicalAnalysisAgent
from .risk_agent import RiskAssessmentAgent
from .fusion_engine import SignalFusionEngine
from ..events import EventBus, get_event_bus


@dataclass
class BettaFishSignal:
    """BettaFish交易信号"""
    stock_code: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    strength: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    agents_consensus: Dict[str, float]  # 各Agent共识度
    reasoning: Dict[str, str]  # 详细推理
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    valid_until: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
        if self.valid_until is None:
            self.valid_until = self.timestamp + timedelta(hours=4)


class BettaFishAgent(BaseService):
    """
    BettaFish多智能体舆情分析核心Agent
    
    协调多个专业化Agent进行综合分析：
    - 舆情分析Agent：市场情绪和社交媒体分析
    - 新闻分析Agent：新闻事件影响评估
    - 技术分析Agent：技术指标和价格模式分析
    - 风险评估Agent：风险指标和合规性分析
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        初始化BettaFish Agent
        
        Args:
            event_bus: 事件总线实例
        """
        super().__init__(event_bus)
        
        # 核心Agent组件
        self.sentiment_agent = SentimentAnalysisAgent(event_bus)
        self.news_agent = NewsAnalysisAgent(event_bus)
        self.technical_agent = TechnicalAnalysisAgent(event_bus)
        self.risk_agent = RiskAssessmentAgent(event_bus)
        self.fusion_engine = SignalFusionEngine()
        
        # 运行时状态
        self._is_running = False
        self._analysis_cache = {}
        self._cache_ttl = 300  # 5分钟缓存
        
        # 性能指标
        self._metrics = {
            'total_analyses': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'average_response_time': 0.0,
            'cache_hit_rate': 0.0,
            'agent_performance': {
                'sentiment': {'success_rate': 0.0, 'avg_time': 0.0},
                'news': {'success_rate': 0.0, 'avg_time': 0.0},
                'technical': {'success_rate': 0.0, 'avg_time': 0.0},
                'risk': {'success_rate': 0.0, 'avg_time': 0.0}
            }
        }
        
        logger.info("BettaFish Agent初始化完成")

    async def initialize(self) -> None:
        """初始化所有子Agent"""
        if self._initialized:
            return
            
        try:
            logger.info("开始初始化BettaFish子Agent...")
            
            # 并行初始化所有Agent
            init_tasks = [
                self.sentiment_agent.initialize(),
                self.news_agent.initialize(),
                self.technical_agent.initialize(),
                self.risk_agent.initialize()
            ]
            
            await asyncio.gather(*init_tasks, return_exceptions=True)
            
            self._is_running = True
            self._initialized = True
            self._initialization_time = time.time()
            
            # 发布初始化完成事件
            self.event_bus.publish('bettafish.agent.initialized',
                timestamp=datetime.now(),
                agents_ready=['sentiment', 'news', 'technical', 'risk']
            )
            
            logger.info("BettaFish Agent初始化完成")
            
        except Exception as e:
            logger.error(f"BettaFish Agent初始化失败: {e}")
            raise

    async def analyze_comprehensive(self, stock_codes: List[str], 
                                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        综合分析指定股票
        
        Args:
            stock_codes: 股票代码列表
            context: 分析上下文（市场环境、用户偏好等）
            
        Returns:
            综合分析结果
        """
        if not self._initialized:
            await self.initialize()
            
        start_time = time.time()
        context = context or {}
        
        try:
            # 检查缓存
            cache_key = self._generate_cache_key(stock_codes, context)
            cached_result = self._get_cached_analysis(cache_key)
            if cached_result:
                self._metrics['cache_hit_rate'] += 1
                logger.debug(f"返回缓存的分析结果: {cache_key}")
                return cached_result
            
            logger.info(f"开始综合分析股票: {stock_codes}")
            
            # 并行执行所有Agent分析
            analysis_tasks = []
            for stock_code in stock_codes:
                task = self._analyze_single_stock(stock_code, context)
                analysis_tasks.append(task)
            
            # 等待所有分析完成
            stock_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            
            # 处理分析结果
            successful_analyses = []
            failed_analyses = []
            
            for i, analysis in enumerate(stock_analyses):
                if isinstance(analysis, Exception):
                    failed_analyses.append({
                        'stock_code': stock_codes[i],
                        'error': str(analysis)
                    })
                    logger.error(f"股票 {stock_codes[i]} 分析失败: {analysis}")
                else:
                    successful_analyses.append(analysis)
            
            # 生成综合报告
            comprehensive_result = self._generate_comprehensive_report(
                successful_analyses, failed_analyses, context
            )
            
            # 更新指标
            response_time = time.time() - start_time
            self._update_performance_metrics(response_time, len(successful_analyses), len(failed_analyses))
            
            # 缓存结果
            self._cache_analysis(cache_key, comprehensive_result)
            
            # 发布分析完成事件
            self.event_bus.publish('bettafish.analysis.completed',
                timestamp=datetime.now(),
                stock_count=len(stock_codes),
                successful_count=len(successful_analyses),
                failed_count=len(failed_analyses),
                response_time=response_time
            )
            
            logger.info(f"综合分析完成，耗时: {response_time:.2f}秒")
            return comprehensive_result
            
        except Exception as e:
            logger.error(f"综合分析失败: {e}")
            self._metrics['failed_analyses'] += 1
            raise

    async def _analyze_single_stock(self, stock_code: str, 
                                  context: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个股票"""
        try:
            # 并行执行所有Agent分析
            sentiment_task = self.sentiment_agent.analyze_stock(stock_code, context)
            news_task = self.news_agent.analyze_stock(stock_code, context)
            technical_task = self.technical_agent.analyze_stock(stock_code, context)
            risk_task = self.risk_agent.analyze_stock(stock_code, context)
            
            sentiment_result, news_result, technical_result, risk_result = await asyncio.gather(
                sentiment_task, news_task, technical_task, risk_task,
                return_exceptions=True
            )
            
            # 处理异常结果
            results = {}
            if not isinstance(sentiment_result, Exception):
                results['sentiment'] = sentiment_result
            if not isinstance(news_result, Exception):
                results['news'] = news_result
            if not isinstance(technical_result, Exception):
                results['technical'] = technical_result
            if not isinstance(risk_result, Exception):
                results['risk'] = risk_result
            
            # 使用融合引擎生成交易信号
            signal = await self.fusion_engine.fuse_signals(
                stock_code, results, context
            )
            
            return {
                'stock_code': stock_code,
                'analysis_results': results,
                'signal': asdict(signal) if signal else None,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"股票 {stock_code} 分析异常: {e}")
            raise

    def _generate_comprehensive_report(self, successful_analyses: List[Dict],
                                     failed_analyses: List[Dict],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """生成综合分析报告"""
        try:
            # 统计信息
            total_stocks = len(successful_analyses) + len(failed_analyses)
            success_rate = len(successful_analyses) / total_stocks if total_stocks > 0 else 0
            
            # 汇总交易信号
            signals = [analysis['signal'] for analysis in successful_analyses if analysis.get('signal')]
            agent_performance = {
                'sentiment': {'analyzed': 0, 'success': 0},
                'news': {'analyzed': 0, 'success': 0},
                'technical': {'analyzed': 0, 'success': 0},
                'risk': {'analyzed': 0, 'success': 0}
            }
            
            for analysis in successful_analyses:
                # 统计各Agent表现
                for agent_name in agent_performance.keys():
                    if agent_name in analysis['analysis_results']:
                        agent_performance[agent_name]['analyzed'] += 1
                        agent_performance[agent_name]['success'] += 1
            
            # 计算成功率
            for agent_name in agent_performance:
                stats = agent_performance[agent_name]
                if stats['analyzed'] > 0:
                    stats['success_rate'] = stats['success'] / stats['analyzed']
            
            # 生成建议
            recommendations = self._generate_recommendations(signals, context)
            
            return {
                'summary': {
                    'total_stocks': total_stocks,
                    'successful_analyses': len(successful_analyses),
                    'failed_analyses': len(failed_analyses),
                    'success_rate': success_rate,
                    'analysis_timestamp': datetime.now()
                },
                'signals': signals,
                'agent_performance': agent_performance,
                'recommendations': recommendations,
                'market_context': context,
                'failed_analyses': failed_analyses
            }
            
        except Exception as e:
            logger.error(f"生成综合报告失败: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now()
            }

    def _generate_cache_key(self, stock_codes: List[str], 
                          context: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 简化版缓存键生成，实际项目中可使用更复杂的逻辑
        stocks_str = ','.join(sorted(stock_codes))
        context_str = str(sorted(context.items()))
        return f"{stocks_str}:{hash(context_str)}"

    def _get_cached_analysis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的分析结果"""
        if cache_key in self._analysis_cache:
            cached_item = self._analysis_cache[cache_key]
            if time.time() - cached_item['timestamp'] < self._cache_ttl:
                return cached_item['data']
            else:
                # 清理过期缓存
                del self._analysis_cache[cache_key]
        return None

    def _cache_analysis(self, cache_key: str, result: Dict[str, Any]):
        """缓存分析结果"""
        self._analysis_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
        
        # 清理过期缓存
        current_time = time.time()
        expired_keys = [
            key for key, item in self._analysis_cache.items()
            if current_time - item['timestamp'] > self._cache_ttl
        ]
        for key in expired_keys:
            del self._analysis_cache[key]

    def _update_performance_metrics(self, response_time: float, 
                                  success_count: int, failure_count: int):
        """更新性能指标"""
        self._metrics['total_analyses'] += 1
        self._metrics['successful_analyses'] += success_count
        self._metrics['failed_analyses'] += failure_count
        
        # 更新平均响应时间
        current_avg = self._metrics['average_response_time']
        total_analyses = self._metrics['total_analyses']
        self._metrics['average_response_time'] = (
            (current_avg * (total_analyses - 1) + response_time) / total_analyses
        )

    def _generate_recommendations(self, signals: List[Dict], 
                                context: Dict[str, Any]) -> List[Dict]:
        """生成建议"""
        recommendations = []
        
        # 基于信号强度排序
        sorted_signals = sorted(signals, key=lambda x: x.get('strength', 0), reverse=True)
        
        # 生成买入建议
        buy_signals = [s for s in sorted_signals if s.get('signal_type') == 'BUY']
        if buy_signals:
            recommendations.append({
                'type': 'BUY_RECOMMENDATION',
                'stocks': [s['stock_code'] for s in buy_signals[:5]],
                'reason': f'检测到{len(buy_signals)}个强烈买入信号',
                'confidence': sum(s.get('confidence', 0) for s in buy_signals) / len(buy_signals)
            })
        
        # 生成风险警告
        high_risk_signals = [s for s in signals if s.get('risk_level') == 'HIGH']
        if high_risk_signals:
            recommendations.append({
                'type': 'RISK_WARNING',
                'stocks': [s['stock_code'] for s in high_risk_signals],
                'reason': f'检测到{len(high_risk_signals)}个高风险信号',
                'action': '建议谨慎操作或暂时观望'
            })
        
        return recommendations

    async def get_trading_signals(self, stock_codes: List[str], 
                                signal_types: List[str] = None) -> List[BettaFishSignal]:
        """
        获取交易信号
        
        Args:
            stock_codes: 股票代码列表
            signal_types: 信号类型过滤 ['BUY', 'SELL', 'HOLD']
            
        Returns:
            交易信号列表
        """
        try:
            # 执行综合分析
            analysis_result = await self.analyze_comprehensive(stock_codes)
            
            # 提取信号
            signals = []
            for signal_dict in analysis_result.get('signals', []):
                signal = BettaFishSignal(**signal_dict)
                
                # 过滤信号类型
                if signal_types and signal.signal_type not in signal_types:
                    continue
                    
                signals.append(signal)
            
            # 按信号强度排序
            signals.sort(key=lambda x: x.strength, reverse=True)
            
            return signals
            
        except Exception as e:
            logger.error(f"获取交易信号失败: {e}")
            return []

    async def shutdown(self):
        """关闭BettaFish Agent"""
        try:
            logger.info("开始关闭BettaFish Agent...")
            
            self._is_running = False
            
            # 关闭所有子Agent
            shutdown_tasks = [
                self.sentiment_agent.shutdown(),
                self.news_agent.shutdown(),
                self.technical_agent.shutdown(),
                self.risk_agent.shutdown()
            ]
            
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            
            # 清空缓存
            self._analysis_cache.clear()
            
            logger.info("BettaFish Agent关闭完成")
            
        except Exception as e:
            logger.error(f"关闭BettaFish Agent失败: {e}")

    @property
    def is_running(self) -> bool:
        """检查Agent是否正在运行"""
        return self._is_running and self._initialized

    async def sentiment_analysis(self, stock_code: str, 
                               context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行情感分析
        
        Args:
            stock_code: 股票代码
            context: 分析上下文
            
        Returns:
            情感分析结果
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            logger.info(f"执行情感分析: {stock_code}")
            result = await self.sentiment_agent.analyze_stock(stock_code, context or {})
            return result
            
        except Exception as e:
            logger.error(f"情感分析失败: {e}")
            return {
                'error': str(e),
                'stock_code': stock_code,
                'timestamp': datetime.now()
            }

    async def news_analysis(self, stock_code: str, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行新闻分析
        
        Args:
            stock_code: 股票代码
            context: 分析上下文
            
        Returns:
            新闻分析结果
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            logger.info(f"执行新闻分析: {stock_code}")
            result = await self.news_agent.analyze_stock(stock_code, context or {})
            return result
            
        except Exception as e:
            logger.error(f"新闻分析失败: {e}")
            return {
                'error': str(e),
                'stock_code': stock_code,
                'timestamp': datetime.now()
            }

    async def technical_analysis(self, stock_code: str, 
                               context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行技术分析
        
        Args:
            stock_code: 股票代码
            context: 分析上下文
            
        Returns:
            技术分析结果
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            logger.info(f"执行技术分析: {stock_code}")
            result = await self.technical_agent.analyze_stock(stock_code, context or {})
            return result
            
        except Exception as e:
            logger.error(f"技术分析失败: {e}")
            return {
                'error': str(e),
                'stock_code': stock_code,
                'timestamp': datetime.now()
            }

    async def risk_analysis(self, stock_code: str, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行风险分析
        
        Args:
            stock_code: 股票代码
            context: 分析上下文
            
        Returns:
            风险分析结果
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            logger.info(f"执行风险分析: {stock_code}")
            result = await self.risk_agent.analyze_stock(stock_code, context or {})
            return result
            
        except Exception as e:
            logger.error(f"风险分析失败: {e}")
            return {
                'error': str(e),
                'stock_code': stock_code,
                'timestamp': datetime.now()
            }

    def get_sentiment_analysis(self) -> Dict[str, Any]:
        """
        获取整体舆情分析数据（供仪表板面板调用）

        Returns:
            舆情分析数据，包含市场情绪、社交舆情、新闻舆情等
        """
        try:
            return {
                'market_sentiment': 0.5,
                'social_sentiment': 0.5,
                'news_sentiment': 0.5,
                'overall_sentiment': 0.5,
                'sentiment_trend': [],
                'key_events': [],
                'sentiment_sources': {},
            }
        except Exception as e:
            logger.error(f"获取舆情分析数据失败: {e}")
            return {}

    def get_news_analysis(self) -> Dict[str, Any]:
        """
        获取新闻分析数据（供仪表板面板调用）

        Returns:
            新闻分析数据，包含最新新闻、高影响新闻、影响统计等
        """
        try:
            return {
                'recent_news': [],
                'high_impact_news': [],
                'impact_analysis': {},
                'historical_impacts': [],
                'impact_sources': {},
                'impact_statistics': {
                    'total_count': 0,
                    'positive_percentage': 0.0,
                    'negative_percentage': 0.0,
                    'neutral_percentage': 0.0,
                    'average_impact_time': 0,
                },
            }
        except Exception as e:
            logger.error(f"获取新闻分析数据失败: {e}")
            return {}

    def get_agent_status(self) -> Dict[str, Any]:
        """
        获取各Agent状态信息
        
        Returns:
            Agent状态信息
        """
        try:
            status = {
                'bettafish_agent': {
                    'initialized': self._initialized,
                    'running': self._is_running,
                    'uptime': time.time() - (self._initialization_time or time.time()),
                    'cache_size': len(self._analysis_cache)
                },
                'sub_agents': {
                    'sentiment_agent': {
                        'available': hasattr(self, 'sentiment_agent') and self.sentiment_agent is not None,
                        'status': 'ready' if self._initialized else 'not_initialized'
                    },
                    'news_agent': {
                        'available': hasattr(self, 'news_agent') and self.news_agent is not None,
                        'status': 'ready' if self._initialized else 'not_initialized'
                    },
                    'technical_agent': {
                        'available': hasattr(self, 'technical_agent') and self.technical_agent is not None,
                        'status': 'ready' if self._initialized else 'not_initialized'
                    },
                    'risk_agent': {
                        'available': hasattr(self, 'risk_agent') and self.risk_agent is not None,
                        'status': 'ready' if self._initialized else 'not_initialized'
                    },
                    'fusion_engine': {
                        'available': hasattr(self, 'fusion_engine') and self.fusion_engine is not None,
                        'status': 'ready'
                    }
                },
                'performance_metrics': self.metrics,
                'timestamp': datetime.now()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"获取Agent状态失败: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now()
            }

    @property
    def metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {
            **self._metrics,
            'cache_size': len(self._analysis_cache),
            'uptime': time.time() - (self._initialization_time or time.time())
        }
