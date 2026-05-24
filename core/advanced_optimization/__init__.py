#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
深度优化系统统一入口

集成5个核心优化模块：
1. 图表渲染性能深度优化
2. 实时数据流处理优化  
3. 智能缓存策略升级
4. 响应式图表界面适配
5. AI驱动的智能图表推荐

作者: FactorWeave-Quant团队
版本: 1.0
"""

# 核心模块导入
from .performance.virtualization import (
    VirtualScrollRenderer,
    DataAggregator,
    ViewportTracker,
    ChunkRenderer
)

from .timing.websocket_client import (
    RealTimeDataProcessor,
    MessageQueue,
    DataCompressor
)

from .cache.intelligent_cache import (
    IntelligentCache,
    L1MemoryCache,
    L2DiskCache,
    MLPredictor
)

from .ui.responsive_adapter import (
    ResponsiveOptimizer,
    ResponsiveChartWidget,
    LayoutMode,
    InteractionMode,
    ScreenType
)

from .ai.smart_chart_recommender import (
    SmartChartRecommender,
    UserBehaviorAnalyzer,
    ContentBasedRecommender,
    RecommendationResult
)

# 统一优化服务
from .unified_optimization_service import (
    UnifiedOptimizationService,
    OptimizationConfig,
    OptimizationMetrics,
    OptimizationMode
)

__all__ = [
    # 性能优化模块
    'VirtualScrollRenderer',
    'DataAggregator', 
    'ViewportTracker',
    'ChunkRenderer',
    
    # 实时数据流处理模块
    'RealTimeDataProcessor',
    'MessageQueue',
    'DataCompressor',
    
    # 智能缓存模块
    'IntelligentCache',
    'L1MemoryCache',
    'L2DiskCache', 
    'MLPredictor',
    
    # 响应式界面模块
    'ResponsiveOptimizer',
    'ResponsiveChartWidget',
    'LayoutMode',
    'InteractionMode',
    'ScreenType',
    
    # AI推荐模块
    'SmartChartRecommender',
    'UserBehaviorAnalyzer',
    'ContentBasedRecommender',
    'RecommendationResult',
    
    # 统一优化服务
    'UnifiedOptimizationService',
    'OptimizationConfig',
    'OptimizationMetrics',
    'OptimizationMode'
]