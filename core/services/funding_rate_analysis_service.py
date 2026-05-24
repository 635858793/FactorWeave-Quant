"""
资金费率分析服务

获取资金费率数据，分析资金费率趋势，提供资金费率预警。
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger

from .base_service import BaseService
from ..events import EventBus
from ..containers import ServiceContainer
from ..data.data_access import DataAccess
from ..data.repository import QueryParams


class FundingRateAnalysisService(BaseService):
    """资金费率分析服务"""

    def __init__(self, service_container: ServiceContainer, event_bus: Optional[EventBus] = None):
        """
        初始化资金费率分析服务

        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        super().__init__(event_bus)
        self.service_container = service_container
        self.data_access = DataAccess(service_container)
        
        self._cache_ttl = 300
        self._unified_cache = None
        self._cache_namespace = 'funding_rate'
        self._init_unified_cache()
        
        self.add_dependency('DataAccess')
        self.add_dependency('KlineRepository')

    def _init_unified_cache(self) -> None:
        """初始化统一缓存服务（强制）"""
        from core.services.cache_service import CacheService
        
        if self.service_container and self.service_container.is_registered(CacheService):
            self._unified_cache = self.service_container.resolve(CacheService)
            logger.debug(f"FundingRateAnalysisService 已连接到统一缓存服务，命名空间: {self._cache_namespace}")
        else:
            self._unified_cache = None
            logger.debug(f"{self.__class__.__name__} 统一缓存服务未注册，缓存功能降级为空操作")

    def _do_initialize(self) -> None:
        """初始化服务"""
        logger.info("资金费率分析服务初始化完成")

    def get_funding_rate(self, symbol: str, interval: str = '1h', count: int = 100) -> pd.DataFrame:
        """
        获取资金费率数据

        Args:
            symbol: 股票代码
            interval: 时间间隔
            count: 数据条数

        Returns:
            资金费率数据
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            cache_key = f"{symbol}_{interval}_{count}"
            cached_data = self._unified_cache.get(cache_key, namespace=self._cache_namespace)
            if cached_data is not None:
                logger.debug(f"从缓存获取资金费率数据: {cache_key}")
                return cached_data

            params = QueryParams(
                stock_code=symbol,
                period=interval,
                count=count
            )
            
            kline_data = self.data_access.get_kline_data(params)
            
            if kline_data and kline_data.data is not None:
                df = kline_data.data
                if self._unified_cache is not None:
                    self._unified_cache.set(cache_key, df, ttl=timedelta(seconds=self._cache_ttl), namespace=self._cache_namespace)
                logger.info(f"获取资金费率数据成功: {symbol}, {len(df)} 条")
                return df
            
            logger.warning(f"未获取到资金费率数据: {symbol}")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取资金费率数据失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return pd.DataFrame()

    def analyze_funding_trend(self, symbol: str, period: int = 24) -> Dict:
        """
        分析资金费率趋势

        Args:
            symbol: 股票代码
            period: 分析周期（小时）

        Returns:
            趋势分析结果
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            df = self.get_funding_rate(symbol, count=period)
            
            if df.empty:
                return {
                    'symbol': symbol,
                    'trend': 'unknown',
                    'value': 0,
                    'change': 0,
                    'timestamp': datetime.now().isoformat()
                }

            recent_values = df.tail(period)
            if len(recent_values) < 2:
                return {
                    'symbol': symbol,
                    'trend': 'insufficient_data',
                    'value': recent_values.iloc[-1]['close'] if not recent_values.empty else 0,
                    'change': 0,
                    'timestamp': datetime.now().isoformat()
                }

            first_value = recent_values.iloc[0]['close']
            last_value = recent_values.iloc[-1]['close']
            change = last_value - first_value
            
            if change > 0.01:
                trend = 'up'
            elif change < -0.01:
                trend = 'down'
            else:
                trend = 'stable'

            result = {
                'symbol': symbol,
                'trend': trend,
                'value': float(last_value),
                'change': float(change),
                'change_percent': float(change / first_value * 100) if first_value != 0 else 0,
                'period': period,
                'timestamp': datetime.now().isoformat()
            }

            self._event_bus.publish(
                'funding_rate.analyzed',
                **result
            )

            return result

        except Exception as e:
            logger.error(f"分析资金费率趋势失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return {
                'symbol': symbol,
                'trend': 'error',
                'value': 0,
                'change': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def check_funding_alert(self, symbol: str, threshold: float = 0.05) -> Dict:
        """
        检查资金费率预警

        Args:
            symbol: 股票代码
            threshold: 预警阈值

        Returns:
            预警结果
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            df = self.get_funding_rate(symbol, count=1)
            
            if df.empty:
                return {
                    'symbol': symbol,
                    'alert': False,
                    'reason': 'no_data',
                    'timestamp': datetime.now().isoformat()
                }

            current_value = df.iloc[-1]['close']
            alert = abs(current_value) > threshold

            result = {
                'symbol': symbol,
                'alert': alert,
                'value': float(current_value),
                'threshold': threshold,
                'timestamp': datetime.now().isoformat()
            }

            if alert:
                result['reason'] = 'threshold_exceeded'
                self._event_bus.publish(
                    'funding_rate.alert',
                    **result
                )
                logger.warning(f"资金费率预警: {symbol}, 值: {current_value}, 阈值: {threshold}")
            else:
                result['reason'] = 'normal'

            return result

        except Exception as e:
            logger.error(f"检查资金费率预警失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return {
                'symbol': symbol,
                'alert': False,
                'reason': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def batch_analyze_trends(self, symbols: List[str], period: int = 24) -> Dict[str, Dict]:
        """
        批量分析资金费率趋势

        Args:
            symbols: 股票代码列表
            period: 分析周期（小时）

        Returns:
            股票代码到趋势分析结果的映射
        """
        try:
            self._ensure_initialized()
            self.increment_operation_count()

            results = {}
            for symbol in symbols:
                results[symbol] = self.analyze_funding_trend(symbol, period)

            success_count = sum(1 for result in results.values() if result.get('trend') not in ['unknown', 'error'])
            logger.info(f"批量分析资金费率趋势完成: {success_count}/{len(symbols)} 成功")

            self._event_bus.publish(
                'funding_rates.batch_analyzed',
                total=len(symbols),
                success=success_count,
                timestamp=datetime.now().isoformat()
            )

            return results

        except Exception as e:
            logger.error(f"批量分析资金费率趋势失败: {e}")
            self._metrics['error_count'] += 1
            self._metrics['last_error'] = str(e)
            return {}

    def clear_cache(self) -> None:
        """清空缓存"""
        if self._unified_cache:
            self._unified_cache.clear_namespace(self._cache_namespace)
        logger.debug("资金费率数据缓存已清空")

    def _do_health_check(self) -> Optional[Dict[str, Any]]:
        """自定义健康检查"""
        cache_stats = {}
        if self._unified_cache:
            cache_stats = self._unified_cache.get_namespace_stats(self._cache_namespace) or {}
        return {
            'cache_stats': cache_stats,
            'cache_ttl': self._cache_ttl
        }
