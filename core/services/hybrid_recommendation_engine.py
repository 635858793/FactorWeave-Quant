"""
混合推荐引擎

基于事件驱动的混合推荐引擎，结合传统推荐引擎和BettaFish智能体，
提供个性化的股票推荐服务。

作者: 量化策略团队
版本: 1.0
日期: 2025-12-13
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

# 核心组件导入
from .base_service import BaseService
from ..events import EventBus, BaseEvent, get_event_bus
from ..containers import get_service_container
from .smart_recommendation_engine import (
    SmartRecommendationEngine, 
    Recommendation, 
    RecommendationType, 
    UserProfile
)
from ..agents.bettafish_agent import BettaFishAgent, BettaFishSignal
from ..monitoring.performance_monitor import PerformanceMonitor
from ..gui.rendering.data_adapter import DataAdapter, DataValidationLevel
from .cache_service import CacheService, CacheConfig, CacheStrategy, CacheLevel, CacheMetrics

# 缓存配置
@dataclass
class RecommendationCacheConfig:
    """推荐引擎缓存配置"""
    # 主推荐结果缓存
    main_cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    main_cache_size: int = 1000
    
    # 传统推荐缓存
    traditional_cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=10))
    traditional_cache_size: int = 500
    
    # BettaFish信号缓存
    bettafish_cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=3))
    bettafish_cache_size: int = 300
    
    # 融合结果缓存
    fusion_cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=2))
    fusion_cache_size: int = 800
    
    # 缓存策略
    strategy: CacheStrategy = CacheStrategy.LRU
    enable_multi_level: bool = True
    enable_metrics: bool = True


# 事件定义
class HybridRecommendationEvent(BaseEvent):
    """混合推荐事件基类"""
    def __init__(self, user_id: str, context: Dict, request_id: str):
        super().__init__()
        self.user_id = user_id
        self.context = context
        self.request_id = request_id
        self.timestamp = datetime.now()


class HybridRecommendationRequestedEvent(HybridRecommendationEvent):
    """混合推荐请求事件"""
    def __init__(self, user_id: str, context: Dict, request_id: str, 
                 stock_codes: List[str] = None):
        super().__init__(user_id, context, request_id)
        self.stock_codes = stock_codes or []
        self.event_type = "HybridRecommendationRequested"


class TraditionalRecommendationCompletedEvent(BaseEvent):
    """传统推荐完成事件"""
    def __init__(self, user_id: str, recommendations: List[Dict], 
                 confidence: float, request_id: str):
        super().__init__()
        self.user_id = user_id
        self.recommendations = recommendations
        self.confidence = confidence
        self.request_id = request_id
        self.timestamp = datetime.now()
        self.event_type = "TraditionalRecommendationCompleted"


class BettaFishRecommendationCompletedEvent(BaseEvent):
    """BettaFish推荐完成事件"""
    def __init__(self, user_id: str, signals: List[Dict], 
                 request_id: str):
        super().__init__()
        self.user_id = user_id
        self.signals = signals
        self.request_id = request_id
        self.timestamp = datetime.now()
        self.event_type = "BettaFishRecommendationCompleted"


class HybridRecommendationCompletedEvent(BaseEvent):
    """混合推荐完成事件"""
    def __init__(self, user_id: str, hybrid_recommendations: List[Dict], 
                 request_id: str, processing_time: float):
        super().__init__()
        self.user_id = user_id
        self.hybrid_recommendations = hybrid_recommendations
        self.request_id = request_id
        self.processing_time = processing_time
        self.timestamp = datetime.now()
        self.event_type = "HybridRecommendationCompleted"


class HybridRecommendationErrorEvent(BaseEvent):
    """混合推荐错误事件"""
    def __init__(self, request_id: str, error: Exception, context: Dict):
        super().__init__()
        self.request_id = request_id
        self.error = error
        self.context = context
        self.timestamp = datetime.now()
        self.event_type = "HybridRecommendationError"


class RecommendationFusionEngine:
    """推荐融合引擎，负责将传统推荐和BettaFish推荐进行融合"""
    
    def __init__(self):
        """初始化推荐融合引擎"""
        self.weights = {
            'traditional': 0.4,  # 传统推荐权重
            'bettafish': 0.6     # BettaFish推荐权重
        }
        
    def fuse_recommendations(self, 
                           traditional_recs: List[Dict], 
                           bettafish_signals: List[Dict]) -> List[Dict]:
        """
        融合传统推荐和BettaFish信号
        
        Args:
            traditional_recs: 传统推荐列表
            bettafish_signals: BettaFish信号列表
            
        Returns:
            融合后的推荐列表
        """
        try:
            # 将BettaFish信号转换为推荐格式
            bettafish_recs = self._convert_bettafish_signals_to_recommendations(bettafish_signals)
            
            # 创建股票到推荐的映射
            stock_to_traditional = {rec['stock_code']: rec for rec in traditional_recs}
            stock_to_bettafish = {rec['stock_code']: rec for rec in bettafish_recs}
            
            # 获取所有股票代码
            all_stocks = set(stock_to_traditional.keys()) | set(stock_to_bettafish.keys())
            
            # 融合推荐
            fused_recommendations = []
            for stock_code in all_stocks:
                traditional_rec = stock_to_traditional.get(stock_code)
                bettafish_rec = stock_to_bettafish.get(stock_code)
                
                if traditional_rec and bettafish_rec:
                    # 如果两者都有，则融合
                    fused_rec = self._fuse_single_recommendation(traditional_rec, bettafish_rec)
                    fused_recommendations.append(fused_rec)
                elif traditional_rec:
                    # 只有传统推荐
                    fused_recommendations.append(traditional_rec)
                elif bettafish_rec:
                    # 只有BettaFish推荐
                    fused_recommendations.append(bettafish_rec)
            
            # 按分数排序
            fused_recommendations.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            return fused_recommendations
            
        except Exception as e:
            logger.error(f"推荐融合失败: {e}")
            return traditional_recs or bettafish_signals  # 返回任一可用的推荐
            
    def _convert_bettafish_signals_to_recommendations(self, signals: List[Dict]) -> List[Dict]:
        """将BettaFish信号转换为推荐格式"""
        recommendations = []
        
        for signal in signals:
            stock_code = signal.get('stock_code')
            if not stock_code:
                continue
                
            # 计算推荐分数
            score = self._calculate_score_from_signal(signal)
            
            recommendation = {
                'stock_code': stock_code,
                'score': score,
                'reason': f"BettaFish推荐: {signal.get('reasoning', '基于智能体分析')}",
                'confidence': signal.get('confidence', 0.5),
                'recommendation_type': signal.get('signal_type', 'HOLD'),
                'metadata': {
                    'source': 'bettafish',
                    'signal_strength': signal.get('strength', 0.5),
                    'risk_level': signal.get('risk_level', 'MEDIUM'),
                    'agents_consensus': signal.get('agents_consensus', {})
                }
            }
            
            recommendations.append(recommendation)
            
        return recommendations
        
    def _calculate_score_from_signal(self, signal: Dict) -> float:
        """根据BettaFish信号计算推荐分数"""
        try:
            # 基础分数
            base_score = signal.get('strength', 0.5)
            
            # 置信度调整
            confidence = signal.get('confidence', 0.5)
            
            # 风险级别调整
            risk_level = signal.get('risk_level', 'MEDIUM')
            risk_factor = {
                'LOW': 1.2,      # 低风险增加分数
                'MEDIUM': 1.0,   # 中风险保持不变
                'HIGH': 0.7      # 高风险降低分数
            }.get(risk_level, 1.0)
            
            # 共识度调整
            agents_consensus = signal.get('agents_consensus', {})
            if agents_consensus:
                consensus_score = sum(agents_consensus.values()) / len(agents_consensus)
            else:
                consensus_score = 0.5
                
            # 综合分数计算
            final_score = base_score * confidence * risk_factor * (0.5 + 0.5 * consensus_score)
            
            # 确保分数在0-1范围内
            return max(0.0, min(1.0, final_score))
            
        except Exception as e:
            logger.error(f"计算BettaFish信号分数失败: {e}")
            return 0.5
            
    def _fuse_single_recommendation(self, traditional_rec: Dict, bettafish_rec: Dict) -> Dict:
        """融合单个推荐"""
        try:
            # 计算加权分数
            traditional_score = traditional_rec.get('score', 0.5)
            bettafish_score = bettafish_rec.get('score', 0.5)
            
            # 融合分数
            fused_score = (
                traditional_score * self.weights['traditional'] +
                bettafish_score * self.weights['bettafish']
            )
            
            # 选择置信度较高的原因
            reason = bettafish_rec.get('reason', traditional_rec.get('reason', ''))
            
            # 选择置信度较高的置信度
            confidence = max(
                traditional_rec.get('confidence', 0.5),
                bettafish_rec.get('confidence', 0.5)
            )
            
            # 融合元数据
            metadata = {
                'source': 'hybrid',
                'traditional_score': traditional_score,
                'bettafish_score': bettafish_score,
                'traditional_metadata': traditional_rec.get('metadata', {}),
                'bettafish_metadata': bettafish_rec.get('metadata', {})
            }
            
            # 融合推荐类型
            recommendation_type = self._resolve_recommendation_type(
                traditional_rec.get('recommendation_type', 'HOLD'),
                bettafish_rec.get('recommendation_type', 'HOLD')
            )
            
            return {
                'stock_code': traditional_rec.get('stock_code', bettafish_rec.get('stock_code')),
                'score': fused_score,
                'reason': reason,
                'confidence': confidence,
                'recommendation_type': recommendation_type,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"融合单个推荐失败: {e}")
            # 失败时返回传统推荐
            return traditional_rec
            
    def _resolve_recommendation_type(self, traditional_type: str, bettafish_type: str) -> str:
        """解决推荐类型冲突"""
        # 定义优先级
        priority = {'SELL': 2, 'BUY': 1, 'HOLD': 0}
        
        # 选择优先级较高的类型
        if priority.get(traditional_type, 0) > priority.get(bettafish_type, 0):
            return traditional_type
        elif priority.get(bettafish_type, 0) > priority.get(traditional_type, 0):
            return bettafish_type
        else:
            # 优先级相同时，选择BettaFish的类型
            return bettafish_type


class ResultComparisonAnalyzer:
    """结果比较分析器，用于分析两种推荐结果的一致性和差异"""
    
    def __init__(self):
        """初始化结果比较分析器"""
        self.analysis_cache = {}
        
    def analyze(self, traditional_recs: List[Dict], 
               bettafish_signals: List[Dict]) -> Dict[str, Any]:
        """
        分析传统推荐和BettaFish推荐的一致性
        
        Args:
            traditional_recs: 传统推荐列表
            bettafish_signals: BettaFish信号列表
            
        Returns:
            分析结果
        """
        try:
            # 转换BettaFish信号为推荐格式
            bettafish_recs = self._convert_bettafish_signals_to_recommendations(bettafish_signals)
            
            # 计算一致性和差异
            consistency_score = self._calculate_consistency_score(traditional_recs, bettafish_recs)
            
            # 分析推荐的股票列表差异
            stock_diff = self._analyze_stock_differences(traditional_recs, bettafish_recs)
            
            # 分析分数分布差异
            score_distribution = self._analyze_score_distribution(traditional_recs, bettafish_recs)
            
            # 生成分析报告
            analysis_report = {
                'consistency_score': consistency_score,
                'stock_differences': stock_diff,
                'score_distribution': score_diff,
                'analysis_timestamp': datetime.now(),
                'recommendation_count': {
                    'traditional': len(traditional_recs),
                    'bettafish': len(bettafish_recs)
                }
            }
            
            return analysis_report
            
        except Exception as e:
            logger.error(f"结果比较分析失败: {e}")
            return {
                'error': str(e),
                'analysis_timestamp': datetime.now()
            }
            
    def _convert_bettafish_signals_to_recommendations(self, signals: List[Dict]) -> List[Dict]:
        """将BettaFish信号转换为推荐格式"""
        recommendations = []
        
        for signal in signals:
            stock_code = signal.get('stock_code')
            if not stock_code:
                continue
                
            recommendation = {
                'stock_code': stock_code,
                'score': signal.get('strength', 0.5),
                'recommendation_type': signal.get('signal_type', 'HOLD')
            }
            
            recommendations.append(recommendation)
            
        return recommendations
        
    def _calculate_consistency_score(self, traditional_recs: List[Dict], 
                                    bettafish_recs: List[Dict]) -> float:
        """计算一致性分数"""
        try:
            if not traditional_recs or not bettafish_recs:
                return 0.5  # 缺乏数据时返回中性分数
                
            # 获取排序后的股票列表
            traditional_stocks = [rec['stock_code'] for rec in sorted(traditional_recs, key=lambda x: x.get('score', 0), reverse=True)]
            bettafish_stocks = [rec['stock_code'] for rec in sorted(bettafish_recs, key=lambda x: x.get('score', 0), reverse=True)]
            
            # 计算前10个股票的交集比例
            top_n = min(10, len(traditional_stocks), len(bettafish_stocks))
            if top_n == 0:
                return 0.5
                
            intersection = set(traditional_stocks[:top_n]) & set(bettafish_stocks[:top_n])
            consistency = len(intersection) / top_n
            
            return consistency
            
        except Exception as e:
            logger.error(f"计算一致性分数失败: {e}")
            return 0.5
            
    def _analyze_stock_differences(self, traditional_recs: List[Dict], 
                                 bettafish_recs: List[Dict]) -> Dict[str, List[str]]:
        """分析股票推荐差异"""
        try:
            traditional_stocks = {rec['stock_code'] for rec in traditional_recs}
            bettafish_stocks = {rec['stock_code'] for rec in bettafish_recs}
            
            only_traditional = list(traditional_stocks - bettafish_stocks)
            only_bettafish = list(bettafish_stocks - traditional_stocks)
            common_stocks = list(traditional_stocks & bettafish_stocks)
            
            return {
                'only_traditional': only_traditional,
                'only_bettafish': only_bettafish,
                'common_stocks': common_stocks,
                'total_unique_stocks': len(traditional_stocks | bettafish_stocks)
            }
            
        except Exception as e:
            logger.error(f"分析股票差异失败: {e}")
            return {
                'only_traditional': [],
                'only_bettafish': [],
                'common_stocks': [],
                'total_unique_stocks': 0
            }
            
    def _analyze_score_distribution(self, traditional_recs: List[Dict], 
                                  bettafish_recs: List[Dict]) -> Dict[str, Any]:
        """分析分数分布差异"""
        try:
            # 提取分数
            traditional_scores = [rec.get('score', 0) for rec in traditional_recs]
            bettafish_scores = [rec.get('score', 0) for rec in bettafish_recs]
            
            if not traditional_scores or not bettafish_scores:
                return {
                    'traditional': {'mean': 0, 'std': 0, 'min': 0, 'max': 0},
                    'bettafish': {'mean': 0, 'std': 0, 'min': 0, 'max': 0}
                }
                
            # 计算统计量
            import numpy as np
            
            return {
                'traditional': {
                    'mean': float(np.mean(traditional_scores)),
                    'std': float(np.std(traditional_scores)),
                    'min': float(np.min(traditional_scores)),
                    'max': float(np.max(traditional_scores))
                },
                'bettafish': {
                    'mean': float(np.mean(bettafish_scores)),
                    'std': float(np.std(bettafish_scores)),
                    'min': float(np.min(bettafish_scores)),
                    'max': float(np.max(bettafish_scores))
                }
            }
            
        except Exception as e:
            logger.error(f"分析分数分布失败: {e}")
            return {
                'traditional': {'mean': 0, 'std': 0, 'min': 0, 'max': 0},
                'bettafish': {'mean': 0, 'std': 0, 'min': 0, 'max': 0}
            }


class HybridRecommendationEngine(BaseService):
    """混合推荐引擎"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__(event_bus)
        
        # 核心组件 - 通过ServiceContainer注入
        self.traditional_engine = None  # 将在initialize中通过容器解析
        self.bettafish_agent = None     # 将在initialize中通过容器解析
        self._database_service = None   # 将在initialize中通过容器解析
        
        # 融合和分析组件
        self.fusion_algorithm = RecommendationFusionEngine()
        self.comparison_analyzer = ResultComparisonAnalyzer()
        
        # 状态跟踪
        self.pending_requests: Dict[str, Dict] = {}
        self.request_lock = asyncio.Lock()
        
        # 缓存配置
        self.cache_config = RecommendationCacheConfig()
        self.cache_service = None  # 将在initialize中初始化
        
        # 多层缓存实例
        self.main_cache = None        # 主推荐结果缓存
        self.traditional_cache = None # 传统推荐缓存
        self.bettafish_cache = None   # BettaFish信号缓存
        self.fusion_cache = None      # 融合结果缓存
        
        # 缓存指标
        self.cache_metrics: Dict[str, CacheMetrics] = {}
        
        # 数据适配器 - 用于验证推荐数据
        self.data_adapter = DataAdapter(event_bus)
        self.data_adapter.validation_level = DataValidationLevel.MODERATE
        
        # 性能监控
        self.performance_monitor = PerformanceMonitor()
        
        # 热门数据缓存
        self._popular_users_cache = None
        self._popular_users_cache_time = 0
        self._popular_stocks_cache = None
        self._popular_stocks_cache_time = 0
        self._cache_ttl = 3600  # 缓存有效期1小时
        
        logger.info("混合推荐引擎已初始化")
        
    async def initialize(self) -> None:
        """初始化引擎并注册事件监听器"""
        if self._initialized:
            return
            
        try:
            logger.info("开始初始化混合推荐引擎...")
            
            # 获取服务容器中的组件
            container = get_service_container()
            
            # 解析传统推荐引擎
            self.traditional_engine = container.resolve(SmartRecommendationEngine)
            
            # 解析BettaFish智能体
            self.bettafish_agent = container.resolve(BettaFishAgent)
            
            # 解析数据库服务
            try:
                self._database_service = container.get_service('DatabaseService')
                logger.info("数据库服务初始化成功")
            except Exception as e:
                logger.warning(f"数据库服务初始化失败: {e}")
            
            # 初始化缓存服务
            if self.cache_config.enable_multi_level:
                self.cache_service = container.resolve(CacheService)
                await self._initialize_caches()
            
            # 注册事件监听器
            # R242-B-001 修复 (2026-08-04): 发布端 publish 类实例 (事件名=类名 '...Event'),
            # 订阅端字符串 'HybridRecommendationRequested' 永不匹配 → 混合推荐链路 100% 失效
            # (API /api/hybrid/recommendation 恒 504)。改为订阅类, 与 publish 键精确对齐
            self.event_bus.subscribe(
                HybridRecommendationRequestedEvent,
                self._handle_recommendation_request
            )
            
            # 启动性能监控 (HVD-240-P0-003: start_monitoring 是同步方法 performance_monitor.py:233, await 会 TypeError)
            self.performance_monitor.start_monitoring()
            
            self._initialized = True
            
            logger.info("混合推荐引擎初始化完成")
            
        except Exception as e:
            logger.error(f"混合推荐引擎初始化失败: {e}")
            raise
            
    async def _initialize_caches(self) -> None:
        """初始化多层缓存"""
        try:
            if not self.cache_service:
                logger.warning("缓存服务未初始化")
                return

            # HVD-240-P1-001: CacheService 无 create_cache API (cache_service.py:1324 仅 create_namespace),
            # 缓存对象 API (get/set/get_keys) 与 CacheService 不匹配 → 优雅降级为无缓存模式
            # 下游消费点 (L1192/1232/1269/1300/1495/1678) 均有 `if not self.xxx_cache` 空值保护
            if not hasattr(self.cache_service, 'create_cache'):
                logger.warning(
                    "CacheService 无 create_cache API (仅 create_namespace), "
                    "混合推荐引擎降级为无缓存模式 (HVD-240-P1-001)")
                return

            # 创建主推荐结果缓存
            main_config = CacheConfig(
                max_size=self.cache_config.main_cache_size,
                default_ttl=self.cache_config.main_cache_ttl,
                strategy=self.cache_config.strategy
            )
            self.main_cache = await self.cache_service.create_cache("hybrid_recommendations", main_config)
            
            # 创建传统推荐缓存
            traditional_config = CacheConfig(
                max_size=self.cache_config.traditional_cache_size,
                default_ttl=self.cache_config.traditional_cache_ttl,
                strategy=self.cache_config.strategy
            )
            self.traditional_cache = await self.cache_service.create_cache("traditional_recommendations", traditional_config)
            
            # 创建BettaFish信号缓存
            bettafish_config = CacheConfig(
                max_size=self.cache_config.bettafish_cache_size,
                default_ttl=self.cache_config.bettafish_cache_ttl,
                strategy=self.cache_config.strategy
            )
            self.bettafish_cache = await self.cache_service.create_cache("bettafish_signals", bettafish_config)
            
            # 创建融合结果缓存
            fusion_config = CacheConfig(
                max_size=self.cache_config.fusion_cache_size,
                default_ttl=self.cache_config.fusion_cache_ttl,
                strategy=self.cache_config.strategy
            )
            self.fusion_cache = await self.cache_service.create_cache("fusion_results", fusion_config)
            
            # 初始化缓存指标
            if self.cache_config.enable_metrics:
                await self._initialize_cache_metrics()
            
            logger.info("多层缓存初始化完成")
            
        except Exception as e:
            logger.error(f"初始化缓存失败: {e}")
            
    async def _initialize_cache_metrics(self) -> None:
        """初始化缓存指标"""
        try:
            if not self.cache_service:
                return
                
            # 为主缓存创建指标
            self.cache_metrics["main"] = CacheMetrics(
                level=CacheLevel.L1_MEMORY,
                operation_count=0,
                error_count=0
            )
            
            # 为传统推荐缓存创建指标
            self.cache_metrics["traditional"] = CacheMetrics(
                level=CacheLevel.L1_MEMORY,
                operation_count=0,
                error_count=0
            )
            
            # 为BettaFish缓存创建指标
            self.cache_metrics["bettafish"] = CacheMetrics(
                level=CacheLevel.L1_MEMORY,
                operation_count=0,
                error_count=0
            )
            
            # 为融合缓存创建指标
            self.cache_metrics["fusion"] = CacheMetrics(
                level=CacheLevel.L1_MEMORY,
                operation_count=0,
                error_count=0
            )
            
        except Exception as e:
            logger.error(f"初始化缓存指标失败: {e}")
            
    async def _handle_recommendation_request(self, event: HybridRecommendationRequestedEvent) -> None:
        """处理混合推荐请求事件"""
        try:
            request_id = event.request_id
            
            # 获取请求信息
            user_id = event.user_id
            context = event.context
            stock_codes = event.stock_codes
            
            logger.info(f"处理混合推荐请求: {request_id}")
            
            # 启动性能监控
            start_time = time.time()
            
            # 并行执行传统推荐和BettaFish分析
            traditional_task = self._get_traditional_recommendations(user_id, context, stock_codes)
            bettafish_task = self._get_bettafish_recommendations(user_id, stock_codes, context)
            
            # 等待所有任务完成
            traditional_result, bettafish_result = await asyncio.gather(
                traditional_task, bettafish_task
            )
            
            # 融合推荐结果
            hybrid_recommendations = self.fusion_algorithm.fuse_recommendations(
                traditional_result, bettafish_result
            )
            
            # 执行结果比较分析
            analysis_result = self.comparison_analyzer.analyze(
                traditional_result, bettafish_result
            )
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 验证混合推荐数据质量
            validation_result = self._validate_recommendation_data(hybrid_recommendations)
            if not validation_result.is_valid:
                logger.warning(f"混合推荐数据验证失败: {validation_result.errors}")
                # 可以选择修复数据或记录警告
                if validation_result.score < 0.5:
                    logger.error(f"数据质量分数过低 ({validation_result.score:.2%})，建议检查数据源")
            
            # 发布推荐完成事件
            completion_event = HybridRecommendationCompletedEvent(
                user_id, hybrid_recommendations, request_id, processing_time
            )
            self.event_bus.publish(completion_event)
            
            # 更新性能监控 (HVD-240-P0-005: record_metric 是同步方法 performance_monitor.py:283, await 会 TypeError)
            self.performance_monitor.record_metric(
                'hybrid_recommendation_processing_time', 
                processing_time
            )
            
            # 记录分析结果
            logger.info(f"混合推荐分析完成: {request_id}, 处理时间: {processing_time:.2f}秒")
            logger.debug(f"分析结果: {json.dumps(analysis_result, default=str, indent=2)}")
            
        except Exception as e:
            logger.error(f"处理混合推荐请求失败: {e}")
            
            # 更新错误指标
            await self._update_cache_metrics("main", "get", False, error=str(e))
            
            # 发布错误事件
            error_event = HybridRecommendationErrorEvent(
                event.request_id, e, {'user_id': event.user_id}
            )
            self.event_bus.publish(error_event)
            
    async def _get_traditional_recommendations(self, user_id: str, 
                                             context: Dict, 
                                             stock_codes: List[str] = None) -> List[Dict]:
        """获取传统推荐"""
        try:
            # 尝试从缓存获取
            cached_result = await self._get_cached_traditional_recommendations(user_id, context, stock_codes or [])
            if cached_result:
                return cached_result
                
            if not self.traditional_engine:
                logger.warning("传统推荐引擎未初始化")
                return []
                
            # 获取推荐
            recommendations = await self.traditional_engine.get_recommendations(
                user_id, 
                RecommendationType.STOCK, 
                10  # 获取前10个推荐
            )
            
            # 转换为字典格式
            result = [self._convert_recommendation_to_dict(rec) for rec in recommendations]
            
            # 缓存结果
            await self._cache_traditional_recommendations(user_id, context, stock_codes or [], result)
            
            return result
            
        except Exception as e:
            logger.error(f"获取传统推荐失败: {e}")
            return []
            
    async def _get_bettafish_recommendations(self, user_id: str, 
                                           stock_codes: List[str], 
                                           context: Dict) -> List[Dict]:
        """获取BettaFish推荐"""
        try:
            # 尝试从缓存获取
            cached_result = await self._get_cached_bettafish_signals(user_id, stock_codes or [], context)
            if cached_result:
                return cached_result
                
            if not self.bettafish_agent:
                logger.warning("BettaFish智能体未初始化")
                return []
                
            # 获取交易信号
            signals = await self.bettafish_agent.get_trading_signals(
                stock_codes or [], 
                ['BUY', 'SELL', 'HOLD']
            )
            
            # 转换为字典格式
            result = [self._convert_signal_to_dict(signal) for signal in signals]
            
            # 缓存结果
            await self._cache_bettafish_signals(user_id, stock_codes or [], result)
            
            return result
            
        except Exception as e:
            logger.error(f"获取BettaFish推荐失败: {e}")
            return []
            
    def _convert_recommendation_to_dict(self, recommendation: Recommendation) -> Dict:
        """将推荐对象转换为字典"""
        return {
            'stock_code': recommendation.item_id,  # 假设item_id是股票代码
            'score': recommendation.score,
            'reason': recommendation.explanation,
            'confidence': recommendation.confidence,
            'recommendation_type': recommendation.reason.value,  # 使用推荐原因作为类型
            'metadata': recommendation.metadata
        }
        
    def _convert_signal_to_dict(self, signal: BettaFishSignal) -> Dict:
        """将信号对象转换为字典"""
        return {
            'stock_code': signal.stock_code,
            'score': signal.strength,
            'reason': signal.reasoning.get('summary', ''),
            'confidence': signal.confidence,
            'recommendation_type': signal.signal_type,
            'metadata': {
                'risk_level': signal.risk_level,
                'target_price': signal.target_price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit
            }
        }
        
    async def request_hybrid_recommendation(self, user_id: str, 
                                         context: Dict, 
                                         stock_codes: List[str] = None) -> str:
        """
        请求混合推荐
        
        Args:
            user_id: 用户ID
            context: 推荐上下文
            stock_codes: 股票代码列表（可选）
            
        Returns:
            请求ID
        """
        # 生成请求ID
        request_id = f"{user_id}_{int(time.time())}"
        
        # 创建推荐请求事件
        request_event = HybridRecommendationRequestedEvent(
            user_id, context, request_id, stock_codes
        )
        
        # 发布事件
        self.event_bus.publish(request_event)
        
        logger.info(f"混合推荐请求已发布: {request_id}")
        
        return request_id
        
    async def get_recommendation_by_request_id(self, request_id: str, timeout: int = 30) -> Optional[Dict]:
        """
        根据请求ID获取推荐结果
        
        Args:
            request_id: 请求ID
            timeout: 超时时间（秒）
            
        Returns:
            推荐结果字典，如果超时则返回None
        """
        # 等待推荐完成事件
        result_event = await self._wait_for_recommendation_completion(request_id, timeout)
        
        if result_event:
            return {
                'user_id': result_event.user_id,
                'recommendations': result_event.hybrid_recommendations,
                'processing_time': result_event.processing_time,
                'timestamp': result_event.timestamp
            }
        else:
            logger.warning(f"获取推荐结果超时: {request_id}")
            return None
            
    async def _wait_for_recommendation_completion(self, request_id: str, timeout: int) -> Optional[HybridRecommendationCompletedEvent]:
        """
        等待推荐完成事件
        
        Args:
            request_id: 请求ID
            timeout: 超时时间（秒）
            
        Returns:
            推荐完成事件，如果超时则返回None
        """
        # 创建一个事件用于同步
        event = asyncio.Event()
        result = None
        
        # 事件监听器
        async def on_completion(completion_event: HybridRecommendationCompletedEvent):
            nonlocal result
            
            if completion_event.request_id == request_id:
                result = completion_event
                event.set()
                
        # 订阅完成事件 (R242-B-001: 改订阅类, 匹配发布端类名)
        self.event_bus.subscribe(HybridRecommendationCompletedEvent, on_completion)
        
        try:
            # 等待事件触发或超时
            await asyncio.wait_for(event.wait(), timeout=timeout)
            
        except asyncio.TimeoutError:
            logger.warning(f"等待推荐完成超时: {request_id}")
            
        finally:
            # 取消订阅 (R242-B-001: 与订阅端类名一致)
            self.event_bus.unsubscribe(HybridRecommendationCompletedEvent, on_completion)
            
        return result
        
    async def shutdown(self):
        """关闭混合推荐引擎"""
        try:
            logger.info("开始关闭混合推荐引擎...")

            try:
                self.event_bus.unsubscribe(
                    HybridRecommendationRequestedEvent,
                    self._handle_recommendation_request
                )
            except Exception as e:
                logger.error(f"取消事件订阅失败: {e}")

            # 关闭性能监控 (HVD-240-P0-004: stop_monitoring 是同步方法 performance_monitor.py:238, await 会 TypeError)
            if self.performance_monitor:
                self.performance_monitor.stop_monitoring()
                
            # 清空多层缓存
            if self.main_cache:
                await self.main_cache.clear()
            if self.traditional_cache:
                await self.traditional_cache.clear()
            if self.bettafish_cache:
                await self.bettafish_cache.clear()
            if self.fusion_cache:
                await self.fusion_cache.clear()
            
            # 清空缓存指标
            self.cache_metrics.clear()
            
            # 清空待处理请求
            self.pending_requests.clear()
            
            logger.info("混合推荐引擎已关闭")
            
        except Exception as e:
            logger.error(f"关闭混合推荐引擎失败: {e}")
            
    @property
    def is_initialized(self) -> bool:
        """检查引擎是否已初始化"""
        return self._initialized
        
    @property
    def performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        base_metrics = self.performance_monitor.get_metrics()
        
        # 添加缓存指标
        if self.cache_config.enable_metrics:
            cache_metrics = self.get_cache_performance_metrics()
            base_metrics.update(cache_metrics)
            
        return base_metrics
        
    def get_cache_performance_metrics(self) -> Dict[str, Any]:
        """
        获取缓存性能指标
        
        Returns:
            缓存性能指标字典
        """
        try:
            metrics = {}
            
            for cache_name, cache_metrics in self.cache_metrics.items():
                metrics[f"cache_{cache_name}"] = {
                    'level': cache_metrics.level.value,
                    'operation_count': cache_metrics.operation_count,
                    'error_count': cache_metrics.error_count,
                    'error_rate': cache_metrics.error_count / cache_metrics.operation_count if cache_metrics.operation_count > 0 else 0,
                    'last_error': cache_metrics.last_error,
                    'last_update': cache_metrics.last_update.isoformat() if cache_metrics.last_update else None
                }
                
            # 添加缓存配置信息
            metrics["cache_config"] = {
                'strategy': self.cache_config.strategy.value,
                'enable_multi_level': self.cache_config.enable_multi_level,
                'enable_metrics': self.cache_config.enable_metrics,
                'main_cache_ttl_minutes': self.cache_config.main_cache_ttl.total_seconds() / 60,
                'traditional_cache_ttl_minutes': self.cache_config.traditional_cache_ttl.total_seconds() / 60,
                'bettafish_cache_ttl_minutes': self.cache_config.bettafish_cache_ttl.total_seconds() / 60,
                'fusion_cache_ttl_minutes': self.cache_config.fusion_cache_ttl.total_seconds() / 60
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"获取缓存性能指标失败: {e}")
            return {"cache_error": str(e)}
        
    def _validate_recommendation_data(self, recommendations: List[Dict]) -> Any:
        """
        验证推荐数据质量
        
        Args:
            recommendations: 推荐数据列表
            
        Returns:
            数据质量报告
        """
        try:
            if not recommendations:
                from ..gui.rendering.data_adapter import DataQualityReport
                return DataQualityReport(
                    is_valid=False,
                    score=0.0,
                    errors=["推荐数据为空"]
                )
                
            # 将推荐数据转换为DataFrame进行验证
            import pandas as pd
            df = pd.DataFrame(recommendations)
            
            # 使用混合推荐数据模式进行验证
            schema_name = "hybrid_recommendation"
            if schema_name not in self.data_adapter.schemas:
                logger.error(f"未找到数据模式: {schema_name}")
                from ..gui.rendering.data_adapter import DataQualityReport
                return DataQualityReport(
                    is_valid=False,
                    score=0.0,
                    errors=[f"数据模式 {schema_name} 不存在"]
                )
                
            schema = self.data_adapter.schemas[schema_name]
            quality_report = self.data_adapter.validate_data(df, schema)
            
            # 记录验证结果
            logger.debug(f"推荐数据验证结果: 分数={quality_report.score:.2%}, "
                        f"有效={quality_report.is_valid}, "
                        f"错误数={len(quality_report.errors)}")
            
            return quality_report
            
        except Exception as e:
            logger.error(f"验证推荐数据失败: {e}")
            from ..gui.rendering.data_adapter import DataQualityReport
            return DataQualityReport(
                is_valid=False,
                score=0.0,
                errors=[f"验证过程异常: {str(e)}"]
            )
            
    def get_data_quality_report(self, request_id: str) -> Optional[Any]:
        """
        获取指定请求的数据质量报告
        
        Args:
            request_id: 请求ID
            
        Returns:
            数据质量报告，如果未找到则返回None
        """
        try:
            # 这里可以从缓存或数据库中获取历史验证结果
            # 目前先返回None，实际实现时可以存储验证结果
            logger.debug(f"获取数据质量报告: {request_id}")
            return None
            
        except Exception as e:
            logger.error(f"获取数据质量报告失败: {e}")
            return None
            
    def _generate_cache_key(self, user_id: str, context: Dict, stock_codes: List[str]) -> str:
        """
        生成缓存键
        
        Args:
            user_id: 用户ID
            context: 推荐上下文
            stock_codes: 股票代码列表
            
        Returns:
            缓存键
        """
        try:
            # 创建用于生成键的内容
            key_content = {
                'user_id': user_id,
                'context': json.dumps(context, sort_keys=True, default=str),
                'stock_codes': sorted(stock_codes) if stock_codes else []
            }
            
            # 生成MD5哈希作为键
            key_string = json.dumps(key_content, sort_keys=True)
            cache_key = hashlib.md5(key_string.encode()).hexdigest()
            
            return f"hybrid_rec_{cache_key}"
            
        except Exception as e:
            logger.error(f"生成缓存键失败: {e}")
            return f"hybrid_rec_fallback_{user_id}_{int(time.time())}"
            
    def _generate_fusion_cache_key(self, traditional_result: List[Dict], bettafish_result: List[Dict]) -> str:
        """
        生成融合结果缓存键
        
        Args:
            traditional_result: 传统推荐结果
            bettafish_result: BettaFish信号结果
            
        Returns:
            融合缓存键
        """
        try:
            # 创建用于生成键的内容
            key_content = {
                'traditional': sorted([rec.get('stock_code', '') for rec in traditional_result]),
                'bettafish': sorted([rec.get('stock_code', '') for rec in bettafish_result])
            }
            
            # 生成MD5哈希作为键
            key_string = json.dumps(key_content, sort_keys=True)
            cache_key = hashlib.md5(key_string.encode()).hexdigest()
            
            return f"fusion_{cache_key}"
            
        except Exception as e:
            logger.error(f"生成融合缓存键失败: {e}")
            return f"fusion_fallback_{int(time.time())}"
            
    async def _update_cache_metrics(self, cache_name: str, operation: str, success: bool, error: str = None) -> None:
        """
        更新缓存指标
        
        Args:
            cache_name: 缓存名称
            operation: 操作类型
            success: 是否成功
            error: 错误信息
        """
        try:
            if not self.cache_config.enable_metrics:
                return
                
            if cache_name not in self.cache_metrics:
                return
                
            metrics = self.cache_metrics[cache_name]
            
            # 更新操作计数
            metrics.operation_count += 1
            
            # 更新错误计数
            if not success:
                metrics.error_count += 1
                metrics.last_error = error
                
            # 更新时间戳
            metrics.last_update = datetime.now()
            
        except Exception as e:
            logger.error(f"更新缓存指标失败: {e}")
            
    async def _get_cached_traditional_recommendations(self, user_id: str, context: Dict, stock_codes: List[str]) -> Optional[List[Dict]]:
        """
        获取缓存的传统推荐
        
        Args:
            user_id: 用户ID
            context: 推荐上下文
            stock_codes: 股票代码列表
            
        Returns:
            缓存的推荐结果，如果没有则返回None
        """
        try:
            if not self.traditional_cache:
                return None
                
            # 生成传统推荐缓存键
            key_content = {
                'user_id': user_id,
                'context': json.dumps(context, sort_keys=True, default=str),
                'stock_codes': sorted(stock_codes) if stock_codes else []
            }
            cache_key = hashlib.md5(json.dumps(key_content, sort_keys=True).encode()).hexdigest()
            
            # 尝试从缓存获取
            cached_result = await self.traditional_cache.get(cache_key)
            
            if cached_result:
                await self._update_cache_metrics("traditional", "get", True)
                logger.debug(f"缓存命中传统推荐: {cache_key}")
                return cached_result
            else:
                await self._update_cache_metrics("traditional", "get", False)
                return None
                
        except Exception as e:
            logger.error(f"获取缓存传统推荐失败: {e}")
            await self._update_cache_metrics("traditional", "get", False, error=str(e))
            return None
            
    async def _get_cached_bettafish_signals(self, user_id: str, stock_codes: List[str], context: Dict) -> Optional[List[Dict]]:
        """
        获取缓存的BettaFish信号
        
        Args:
            user_id: 用户ID
            stock_codes: 股票代码列表
            context: 推荐上下文
            
        Returns:
            缓存的信号结果，如果没有则返回None
        """
        try:
            if not self.bettafish_cache:
                return None
                
            # 生成BettaFish缓存键
            key_content = {
                'user_id': user_id,
                'stock_codes': sorted(stock_codes) if stock_codes else []
            }
            cache_key = hashlib.md5(json.dumps(key_content, sort_keys=True).encode()).hexdigest()
            
            # 尝试从缓存获取
            cached_result = await self.bettafish_cache.get(cache_key)
            
            if cached_result:
                await self._update_cache_metrics("bettafish", "get", True)
                logger.debug(f"缓存命中BettaFish信号: {cache_key}")
                return cached_result
            else:
                await self._update_cache_metrics("bettafish", "get", False)
                return None
                
        except Exception as e:
            logger.error(f"获取缓存BettaFish信号失败: {e}")
            await self._update_cache_metrics("bettafish", "get", False, error=str(e))
            return None
            
    async def _cache_traditional_recommendations(self, user_id: str, context: Dict, stock_codes: List[str], recommendations: List[Dict]) -> None:
        """
        缓存传统推荐结果
        
        Args:
            user_id: 用户ID
            context: 推荐上下文
            stock_codes: 股票代码列表
            recommendations: 推荐结果
        """
        try:
            if not self.traditional_cache or not recommendations:
                return
                
            # 生成缓存键
            key_content = {
                'user_id': user_id,
                'context': json.dumps(context, sort_keys=True, default=str),
                'stock_codes': sorted(stock_codes) if stock_codes else []
            }
            cache_key = hashlib.md5(json.dumps(key_content, sort_keys=True).encode()).hexdigest()
            
            # 缓存结果
            await self.traditional_cache.set(cache_key, recommendations)
            await self._update_cache_metrics("traditional", "set", True)
            
            logger.debug(f"缓存传统推荐结果: {cache_key}")
            
        except Exception as e:
            logger.error(f"缓存传统推荐失败: {e}")
            await self._update_cache_metrics("traditional", "set", False, error=str(e))
            
    async def _cache_bettafish_signals(self, user_id: str, stock_codes: List[str], signals: List[Dict]) -> None:
        """
        缓存BettaFish信号结果
        
        Args:
            user_id: 用户ID
            stock_codes: 股票代码列表
            signals: 信号结果
        """
        try:
            if not self.bettafish_cache or not signals:
                return
                
            # 生成缓存键
            key_content = {
                'user_id': user_id,
                'stock_codes': sorted(stock_codes) if stock_codes else []
            }
            cache_key = hashlib.md5(json.dumps(key_content, sort_keys=True).encode()).hexdigest()
            
            # 缓存结果
            await self.bettafish_cache.set(cache_key, signals)
            await self._update_cache_metrics("bettafish", "set", True)
            
            logger.debug(f"缓存BettaFish信号结果: {cache_key}")
            
        except Exception as e:
            logger.error(f"缓存BettaFish信号失败: {e}")
            await self._update_cache_metrics("bettafish", "set", False, error=str(e))
            
    async def warm_cache(self, user_ids: List[str] = None, stock_codes: List[str] = None) -> None:
        """
        缓存预热策略
        
        Args:
            user_ids: 预热用户ID列表，如果为None则使用热门用户
            stock_codes: 预热股票代码列表，如果为None则使用热门股票
        """
        try:
            logger.info("开始缓存预热...")
            
            # 如果没有指定用户，使用热门用户ID
            if not user_ids:
                user_ids = await self._get_popular_users()
                
            # 如果没有指定股票，使用热门股票
            if not stock_codes:
                stock_codes = await self._get_popular_stocks()
                
            # 创建预热任务
            warmup_tasks = []
            
            # 为每个用户预热推荐
            for user_id in user_ids[:10]:  # 限制预热数量
                context = {'warmup': True, 'source': 'cache_warmup'}
                warmup_tasks.append(self._preload_user_recommendations(user_id, context, stock_codes[:20]))
                
            # 并发执行预热任务
            if warmup_tasks:
                await asyncio.gather(*warmup_tasks, return_exceptions=True)
                
            logger.info(f"缓存预热完成，预热了 {len(user_ids[:10])} 个用户")
            
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
            
    async def _get_popular_users(self) -> List[str]:
        """
        获取热门用户ID列表
        
        Returns:
            热门用户ID列表
        """
        import time
        
        current_time = time.time()
        
        if self._popular_users_cache and (current_time - self._popular_users_cache_time) < self._cache_ttl:
            logger.debug(f"使用缓存的热门用户数据")
            return self._popular_users_cache
        
        try:
            if self._database_service is None:
                logger.warning("数据库服务不可用，无法获取热门用户")
                return []
            
            try:
                user_activity_sql = """
                    SELECT 
                        strategy_id as user_id,
                        COUNT(*) as order_count,
                        MAX(create_time) as last_activity
                    FROM orders
                    WHERE create_time >= datetime('now', '-30 days')
                    GROUP BY strategy_id
                    ORDER BY order_count DESC, last_activity DESC
                    LIMIT 20
                """
                
                user_activity_result = self._database_service.fetch_all(user_activity_sql)
                
                if user_activity_result and len(user_activity_result) > 0:
                    popular_users = [row['user_id'] for row in user_activity_result]
                    self._popular_users_cache = popular_users
                    self._popular_users_cache_time = current_time
                    logger.info(f"从数据库查询到 {len(popular_users)} 个热门用户")
                    return popular_users
                else:
                    logger.info("数据库中暂无用户活动数据")
                    return []
                    
            except Exception as e:
                logger.error(f"查询热门用户失败: {e}")
                return []
                
        except Exception as e:
            logger.error(f"获取热门用户失败: {e}")
            return []
        
    async def _get_popular_stocks(self) -> List[str]:
        """
        获取热门股票代码列表
        
        Returns:
            热门股票代码列表
        """
        import time
        
        current_time = time.time()
        
        if self._popular_stocks_cache and (current_time - self._popular_stocks_cache_time) < self._cache_ttl:
            logger.debug(f"使用缓存的热门股票数据")
            return self._popular_stocks_cache
        
        try:
            if self._database_service is None:
                logger.warning("数据库服务不可用，无法获取热门股票")
                return []
            
            try:
                stock_activity_sql = """
                    SELECT 
                        stock_code,
                        SUM(fill_quantity) as total_volume,
                        COUNT(*) as trade_count
                    FROM order_fills
                    WHERE fill_time >= datetime('now', '-30 days')
                    GROUP BY stock_code
                    ORDER BY (total_volume * 0.6 + trade_count * 0.4) DESC
                    LIMIT 20
                """
                
                stock_activity_result = self._database_service.fetch_all(stock_activity_sql)
                
                if stock_activity_result and len(stock_activity_result) > 0:
                    popular_stocks = [row['stock_code'] for row in stock_activity_result]
                    self._popular_stocks_cache = popular_stocks
                    self._popular_stocks_cache_time = current_time
                    logger.info(f"从数据库查询到 {len(popular_stocks)} 个热门股票")
                    return popular_stocks
                else:
                    logger.info("数据库中暂无股票交易数据")
                    return []
                    
            except Exception as e:
                logger.error(f"查询热门股票失败: {e}")
                return []
                
        except Exception as e:
            logger.error(f"获取热门股票失败: {e}")
            return []
        
    async def _preload_user_recommendations(self, user_id: str, context: Dict, stock_codes: List[str]) -> None:
        """
        为用户预加载推荐结果
        
        Args:
            user_id: 用户ID
            context: 推荐上下文
            stock_codes: 股票代码列表
        """
        try:
            # 生成预热的混合推荐
            await self.request_hybrid_recommendation(user_id, context, stock_codes)
            
            # 等待预热完成
            await asyncio.sleep(0.1)  # 短暂延迟避免过载
            
        except Exception as e:
            logger.debug(f"预热用户 {user_id} 推荐失败: {e}")
            
    async def _invalidate_cache_by_pattern(self, pattern: str) -> int:
        """
        根据模式失效缓存
        
        Args:
            pattern: 缓存键匹配模式
            
        Returns:
            被失效的缓存项数量
        """
        try:
            invalidated_count = 0
            
            # 失效主缓存
            if self.main_cache:
                main_keys = await self.main_cache.get_keys()
                for key in main_keys:
                    if pattern in key:
                        await self.main_cache.delete(key)
                        invalidated_count += 1
                        
            # 失效传统推荐缓存
            if self.traditional_cache:
                traditional_keys = await self.traditional_cache.get_keys()
                for key in traditional_keys:
                    if pattern in key:
                        await self.traditional_cache.delete(key)
                        invalidated_count += 1
                        
            # 失效BettaFish缓存
            if self.bettafish_cache:
                bettafish_keys = await self.bettafish_cache.get_keys()
                for key in bettafish_keys:
                    if pattern in key:
                        await self.bettafish_cache.delete(key)
                        invalidated_count += 1
                        
            # 失效融合缓存
            if self.fusion_cache:
                fusion_keys = await self.fusion_cache.get_keys()
                for key in fusion_keys:
                    if pattern in key:
                        await self.fusion_cache.delete(key)
                        invalidated_count += 1
                        
            logger.info(f"根据模式 '{pattern}' 失效了 {invalidated_count} 个缓存项")
            
            return invalidated_count
            
        except Exception as e:
            logger.error(f"缓存失效失败: {e}")
            return 0
            
    async def _optimize_cache_performance(self) -> Dict[str, Any]:
        """
        优化缓存性能
        
        Returns:
            优化建议
        """
        try:
            optimization_report = {
                'recommendations': [],
                'current_metrics': {},
                'optimization_applied': []
            }
            
            # 分析当前缓存指标
            for cache_name, metrics in self.cache_metrics.items():
                if metrics.operation_count > 0:
                    hit_rate = (metrics.operation_count - metrics.error_count) / metrics.operation_count
                    
                    optimization_report['current_metrics'][cache_name] = {
                        'hit_rate': hit_rate,
                        'error_rate': metrics.error_count / metrics.operation_count,
                        'operation_count': metrics.operation_count
                    }
                    
                    # 根据命中率给出优化建议
                    if hit_rate < 0.3:
                        optimization_report['recommendations'].append({
                            'cache': cache_name,
                            'issue': '低命中率',
                            'suggestion': '考虑增加缓存大小或延长TTL时间',
                            'priority': 'high'
                        })
                    elif hit_rate < 0.6:
                        optimization_report['recommendations'].append({
                            'cache': cache_name,
                            'issue': '中等命中率',
                            'suggestion': '考虑调整缓存策略或预热机制',
                            'priority': 'medium'
                        })
                        
            # 如果启用了多级缓存，建议优化策略
            if self.cache_config.enable_multi_level:
                optimization_report['recommendations'].append({
                    'cache': 'all',
                    'issue': '多级缓存优化',
                    'suggestion': '考虑实现L1/L2/L3多层缓存策略以提高性能',
                    'priority': 'medium'
                })
                
            # 如果错误率过高，建议检查缓存实现
            for cache_name, metrics in optimization_report['current_metrics'].items():
                if metrics['error_rate'] > 0.05:  # 错误率超过5%
                    optimization_report['recommendations'].append({
                        'cache': cache_name,
                        'issue': '高错误率',
                        'suggestion': '检查缓存实现是否存在并发问题或内存泄漏',
                        'priority': 'high'
                    })
                    
            return optimization_report
            
        except Exception as e:
            logger.error(f"缓存性能优化分析失败: {e}")
            return {'error': str(e)}
            
    async def get_detailed_cache_statistics(self) -> Dict[str, Any]:
        """
        获取详细的缓存统计信息
        
        Returns:
            详细缓存统计信息
        """
        try:
            stats = {
                'summary': {
                    'total_operations': 0,
                    'total_errors': 0,
                    'overall_hit_rate': 0.0
                },
                'cache_details': {},
                'performance_recommendations': []
            }
            
            total_ops = 0
            total_errors = 0
            
            # 收集每个缓存的详细统计
            for cache_name, metrics in self.cache_metrics.items():
                cache_detail = {
                    'level': metrics.level.value,
                    'operations': metrics.operation_count,
                    'errors': metrics.error_count,
                    'error_rate': metrics.error_count / metrics.operation_count if metrics.operation_count > 0 else 0,
                    'hit_rate': 1 - (metrics.error_count / metrics.operation_count if metrics.operation_count > 0 else 1),
                    'last_update': metrics.last_update.isoformat() if metrics.last_update else None
                }
                
                # 如果有具体的缓存实例，获取更多统计信息
                cache_instance = getattr(self, f"{cache_name}_cache", None)
                if cache_instance:
                    try:
                        # 尝试获取缓存大小和使用情况
                        cache_detail['cache_size'] = getattr(cache_instance, '_cache', {}).__len__() if hasattr(cache_instance, '_cache') else 0
                        cache_detail['memory_usage'] = f"{cache_detail['cache_size']} items"
                    except Exception:
                        pass
                        
                stats['cache_details'][cache_name] = cache_detail
                
                total_ops += metrics.operation_count
                total_errors += metrics.error_count
                
            # 计算总体统计
            stats['summary']['total_operations'] = total_ops
            stats['summary']['total_errors'] = total_errors
            stats['summary']['overall_hit_rate'] = (total_ops - total_errors) / total_ops if total_ops > 0 else 0.0
            
            # 添加配置信息
            stats['cache_config'] = {
                'strategy': self.cache_config.strategy.value,
                'enable_multi_level': self.cache_config.enable_multi_level,
                'enable_metrics': self.cache_config.enable_metrics,
                'main_cache_size': self.cache_config.main_cache_size,
                'traditional_cache_size': self.cache_config.traditional_cache_size,
                'bettafish_cache_size': self.cache_config.bettafish_cache_size,
                'fusion_cache_size': self.cache_config.fusion_cache_size
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取详细缓存统计失败: {e}")
            return {'error': str(e)}
            
    async def clear_cache(self) -> None:
        """
        清空所有缓存
        
        Returns:
            None
        """
        try:
            # 清空多层缓存
            if self.main_cache:
                await self.main_cache.clear()
                
            if self.traditional_cache:
                await self.traditional_cache.clear()
                
            if self.bettafish_cache:
                await self.bettafish_cache.clear()
                
            if self.fusion_cache:
                await self.fusion_cache.clear()
            
            # 重置缓存指标
            self.cache_metrics.clear()
            if self.cache_config.enable_metrics:
                await self._initialize_cache_metrics()
                
            logger.info("已清空所有缓存")
            
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            raise
            
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息字典
        """
        try:
            # 获取缓存性能指标
            cache_metrics = self.get_cache_performance_metrics()
            
            # 补充缓存基本信息
            result = {
                "cache_status": "enabled" if self.cache_config.enable_multi_level else "disabled",
                "cache_config": {
                    "strategy": self.cache_config.strategy.value,
                    "enable_multi_level": self.cache_config.enable_multi_level,
                    "enable_metrics": self.cache_config.enable_metrics
                },
                "cache_performance": cache_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"获取缓存统计信息失败: {e}")
            return {"error": str(e)}
            
    async def optimize_cache_settings(self) -> Dict[str, Any]:
        """
        根据使用模式优化缓存设置
        
        Returns:
            优化建议和实际应用的更改
        """
        try:
            optimization_result = {
                'suggestions': [],
                'applied_changes': [],
                'performance_impact': {}
            }
            
            # 分析缓存使用模式
            stats = await self.get_detailed_cache_statistics()
            
            if 'error' in stats:
                return optimization_result
                
            # 根据统计信息给出优化建议
            for cache_name, cache_stats in stats['cache_details'].items():
                hit_rate = cache_stats['hit_rate']
                error_rate = cache_stats['error_rate']
                
                if hit_rate < 0.4:
                    # 低命中率，建议增加缓存大小
                    current_size = getattr(self.cache_config, f"{cache_name}_cache_size")
                    suggested_size = int(current_size * 1.5)  # 增加50%
                    
                    optimization_result['suggestions'].append({
                        'cache': cache_name,
                        'current_size': current_size,
                        'suggested_size': suggested_size,
                        'reason': f'命中率较低 ({hit_rate:.2%})，建议增加缓存大小'
                    })
                    
                if error_rate > 0.03:
                    # 高错误率，建议检查实现
                    optimization_result['suggestions'].append({
                        'cache': cache_name,
                        'issue': 'error_rate_high',
                        'reason': f'错误率过高 ({error_rate:.2%})，建议检查缓存实现'
                    })
                    
            # 根据推荐应用优化（可选）
            # 这里可以根据实际情况决定是否自动应用优化
            # 暂时只返回建议，不自动应用
            for suggestion in optimization_result['suggestions']:
                if 'suggested_size' in suggestion:
                    # 模拟应用更改
                    optimization_result['applied_changes'].append({
                        'type': 'cache_size_increase',
                        'cache': suggestion['cache'],
                        'old_value': suggestion['current_size'],
                        'new_value': suggestion['suggested_size']
                    })
                    
            return optimization_result
            
        except Exception as e:
            logger.error(f"缓存设置优化失败: {e}")
            return {'error': str(e)}