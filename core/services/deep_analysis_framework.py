"""
深度分析框架 - 统一入口

提供统一的深度分析服务入口，整合以下功能：
- UnifiedPerformanceCoordinator: 统一性能协调器
- AdvancedPerformanceAnalytics: 高级性能分析引擎
- DeepAnalysisService: 基础深度分析服务

使用方式:
    from core.services.deep_analysis_framework import (
        get_deep_analysis_framework,
        get_performance_coordinator,
        get_advanced_analytics
    )
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# 全局单例实例
_deep_analysis_framework_instance: Optional['DeepAnalysisFramework'] = None
_performance_coordinator_instance: Optional[Any] = None
_advanced_analytics_instance: Optional[Any] = None


class DeepAnalysisFramework:
    """
    深度分析框架 - 统一入口类
    
    整合以下核心组件:
    - 性能监控
    - 瓶颈分析
    - 趋势预测
    - 异常检测
    - 优化建议
    """
    
    def __init__(self):
        self._coordinator = None
        self._analytics = None
        self._initialized = False
        logger.info("DeepAnalysisFramework 实例已创建")
    
    def initialize(self) -> bool:
        """初始化深度分析框架"""
        if self._initialized:
            logger.warning("DeepAnalysisFramework 已经初始化")
            return True
        
        try:
            # 初始化性能协调器
            self._coordinator = get_performance_coordinator()
            logger.info("性能协调器初始化完成")
            
            # 初始化高级分析引擎
            self._analytics = get_advanced_analytics()
            logger.info("高级分析引擎初始化完成")
            
            self._initialized = True
            logger.info("DeepAnalysisFramework 初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"DeepAnalysisFramework 初始化失败: {e}")
            return False
    
    @property
    def coordinator(self):
        """获取性能协调器"""
        if self._coordinator is None:
            self._coordinator = get_performance_coordinator()
        return self._coordinator
    
    @property
    def analytics(self):
        """获取高级分析引擎"""
        if self._analytics is None:
            self._analytics = get_advanced_analytics()
        return self._analytics
    
    def get_status(self) -> Dict[str, Any]:
        """获取框架状态"""
        return {
            'initialized': self._initialized,
            'coordinator_available': self._coordinator is not None,
            'analytics_available': self._analytics is not None,
            'coordinator_status': getattr(self._coordinator, 'status', None) if self._coordinator else None
        }
    
    def get_capabilities(self) -> Dict[str, List[str]]:
        """获取框架能力"""
        capabilities = {
            'performance_monitoring': [
                'system_metrics',
                'cpu_tracking',
                'memory_tracking',
                'thread_monitoring',
                'ui_performance'
            ],
            'analytics': [],
            'alerts': [
                'performance_alerts',
                'threshold_alerts',
                'anomaly_alerts'
            ]
        }
        
        # 添加高级分析能力
        if self._analytics and hasattr(self._analytics, 'get_analysis_status'):
            try:
                status = self._analytics.get_analysis_status()
                capabilities['analytics'] = status.get('supported_analyses', [])
            except Exception as e:
                logger.warning(f"获取分析能力失败: {e}")
        
        return capabilities


def get_deep_analysis_framework() -> DeepAnalysisFramework:
    """
    获取深度分析框架单例
    
    Returns:
        DeepAnalysisFramework: 深度分析框架实例
    """
    global _deep_analysis_framework_instance
    
    if _deep_analysis_framework_instance is None:
        _deep_analysis_framework_instance = DeepAnalysisFramework()
        logger.info("创建 DeepAnalysisFramework 全局单例")
    
    return _deep_analysis_framework_instance


def get_performance_coordinator():
    """
    获取统一性能协调器
    
    优先使用完整版 (core/performance/unified_performance_coordinator.py)
    
    Returns:
        UnifiedPerformanceCoordinator: 性能协调器实例
    """
    global _performance_coordinator_instance
    
    if _performance_coordinator_instance is None:
        try:
            # 优先使用完整版
            from core.performance.unified_performance_coordinator import get_performance_coordinator as _get_coord
            _performance_coordinator_instance = _get_coord()
            logger.info("加载完整版 UnifiedPerformanceCoordinator")
        except ImportError as e:
            logger.warning(f"完整版不可用，尝试简化版: {e}")
            try:
                # 降级到简化版
                from core.advanced_optimization.performance.unified_performance_coordinator import get_unified_performance_coordinator as _get_coord
                _performance_coordinator_instance = _get_coord()
                logger.info("加载简化版 UnifiedPerformanceCoordinator")
            except ImportError as e2:
                logger.error(f"无法加载 UnifiedPerformanceCoordinator: {e2}")
                raise
    
    return _performance_coordinator_instance


def get_advanced_analytics():
    """
    获取高级性能分析引擎
    
    使用 AdvancedPerformanceAnalytics (core/advanced_optimization/performance/advanced_performance_analytics.py)
    
    Returns:
        AdvancedPerformanceAnalytics: 高级分析引擎实例
    """
    global _advanced_analytics_instance
    
    if _advanced_analytics_instance is None:
        try:
            from core.advanced_optimization.performance.advanced_performance_analytics import get_advanced_performance_analytics as _get_analytics
            _advanced_analytics_instance = _get_analytics()
            logger.info("加载 AdvancedPerformanceAnalytics 成功")
        except ImportError as e:
            logger.error(f"无法加载 AdvancedPerformanceAnalytics: {e}")
            raise
    
    return _advanced_analytics_instance


def get_deep_analysis_service():
    """
    获取基础深度分析服务（兼容旧接口）
    
    此函数保留用于向后兼容。
    新代码应使用 get_deep_analysis_framework() 或 get_advanced_analytics()
    
    Returns:
        DeepAnalysisService: 基础分析服务实例
    """
    try:
        from core.services.deep_analysis_service import get_deep_analysis_service as _get_service
        return _get_service()
    except ImportError as e:
        logger.warning(f"DeepAnalysisService 不可用: {e}")
        return None


def initialize_deep_analysis_framework(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    初始化深度分析框架
    
    Args:
        config: 配置参数（可选）
        
    Returns:
        bool: 初始化是否成功
    """
    framework = get_deep_analysis_framework()
    return framework.initialize()


def get_framework_status() -> Dict[str, Any]:
    """
    获取深度分析框架状态
    
    Returns:
        Dict: 框架状态信息
    """
    framework = get_deep_analysis_framework()
    return framework.get_status()


# 导出列表
__all__ = [
    'DeepAnalysisFramework',
    'get_deep_analysis_framework',
    'get_performance_coordinator',
    'get_advanced_analytics',
    'get_deep_analysis_service',
    'initialize_deep_analysis_framework',
    'get_framework_status',
]
