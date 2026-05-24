from typing import Optional, Dict, Any, List
import pandas as pd
from .base_service import BaseService, CacheableService, ConfigurableService
from loguru import logger


class IndexService(CacheableService, ConfigurableService):
    """
    指数服务
    
    负责指数数据的获取、缓存和管理，包括：
    - A股指数（上证指数、深证成指、创业板指、科创板指等）
    - 港股指数（恒生指数、恒生国企指数等）
    - 美股指数（道琼斯、纳斯达克、标普500等）
    - 指数行情数据
    - 指数成分股查询
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, cache_size: int = 100,
                 service_container=None, **kwargs):
        self.service_container = service_container
        
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'service_container'}
        CacheableService.__init__(self, cache_size=cache_size, namespace='index_service', **filtered_kwargs)
        ConfigurableService.__init__(self, config=config, **filtered_kwargs)
        
        self._unified_data_manager = None
        self._index_list = []
        self._no_data_cache = set()
        self._last_query_time = {}
        
    def _do_initialize(self) -> None:
        try:
            from .unified_data_manager import get_unified_data_manager
            self._unified_data_manager = get_unified_data_manager()
            if self._unified_data_manager:
                logger.info("IndexService 初始化成功，连接到 UnifiedDataManager")
            else:
                logger.warning("UnifiedDataManager 不可用，IndexService 将使用降级模式")
        except Exception as e:
            logger.warning(f"IndexService 初始化失败: {e}")
    
    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def get_index_list(self, market: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"index_list_{market}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            if self._unified_data_manager:
                df = self._unified_data_manager.get_asset_list(asset_type='index', market=market or 'all')
                if df is not None and not df.empty:
                    index_list = df.to_dict('records')
                    self.set_to_cache(cache_key, index_list)
                    self._index_list = index_list
                    return index_list
            
            return self._get_default_index_list(market)
        except Exception as e:
            logger.error(f"获取指数列表失败: {e}")
            return self._get_default_index_list(market)
    
    def _get_default_index_list(self, market: Optional[str] = None) -> List[Dict[str, Any]]:
        default_indices = [
            {'code': '000001', 'name': '上证指数', 'market': 'SH'},
            {'code': '399001', 'name': '深证成指', 'market': 'SZ'},
            {'code': '399006', 'name': '创业板指', 'market': 'SZ'},
            {'code': '000688', 'name': '科创板指', 'market': 'SH'},
            {'code': '399300', 'name': '沪深300', 'market': 'SZ'},
            {'code': '000016', 'name': '上证50', 'market': 'SH'},
            {'code': '000905', 'name': '中证500', 'market': 'SH'},
            {'code': '399101', 'name': '中小板指', 'market': 'SZ'},
            {'code': 'HSI', 'name': '恒生指数', 'market': 'HK'},
            {'code': 'HSCCI', 'name': '恒生国企指数', 'market': 'HK'},
            {'code': 'DJI', 'name': '道琼斯工业指数', 'market': 'US'},
            {'code': 'IXIC', 'name': '纳斯达克综合指数', 'market': 'US'},
            {'code': 'SPX', 'name': '标普500', 'market': 'US'},
        ]
        
        if market:
            return [idx for idx in default_indices if idx['market'].upper() == market.upper()]
        return default_indices
    
    def get_kline_data(self, index_code: str, period: str = 'D', 
                       count: int = 365) -> pd.DataFrame:
        self._ensure_initialized()
        
        cache_key = f"index_kline_{index_code}_{period}_{count}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        if index_code in self._no_data_cache:
            return pd.DataFrame()
        
        try:
            if self._unified_data_manager:
                df = self._unified_data_manager.get_kline_data(
                    stock_code=index_code,
                    period=period,
                    count=count,
                    asset_type='index'
                )
                if df is not None and not df.empty:
                    self.set_to_cache(cache_key, df)
                    return df
                else:
                    self._no_data_cache.add(index_code)
            
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取指数K线数据失败: {index_code}, {e}")
            return pd.DataFrame()
    
    def get_index_info(self, index_code: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"index_info_{index_code}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            index_list = self.get_index_list()
            for idx in index_list:
                if idx.get('code') == index_code or idx.get('symbol') == index_code:
                    self.set_to_cache(cache_key, idx)
                    return idx
            
            for idx in self._get_default_index_list(None):
                if idx.get('code') == index_code:
                    self.set_to_cache(cache_key, idx)
                    return idx
            
            return None
        except Exception as e:
            logger.error(f"获取指数信息失败: {index_code}, {e}")
            return None
    
    def search_indices(self, keyword: str) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        if not keyword:
            return []
        
        keyword = keyword.lower()
        index_list = self.get_index_list()
        
        results = [
            idx for idx in index_list
            if keyword in idx.get('name', '').lower() or keyword in idx.get('code', '').lower()
        ]
        
        if not results:
            default_list = self._get_default_index_list(None)
            results = [
                idx for idx in default_list
                if keyword in idx.get('name', '').lower() or keyword in idx.get('code', '').lower()
            ]
        
        return results
    
    def get_index_components(self, index_code: str) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"index_components_{index_code}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        component_map = {
            '000001': [
                {'code': '600519', 'name': '贵州茅台'},
                {'code': '601318', 'name': '中国平安'},
                {'code': '600036', 'name': '招商银行'},
            ],
            '399300': [
                {'code': '600519', 'name': '贵州茅台'},
                {'code': '000858', 'name': '五粮液'},
                {'code': '601318', 'name': '中国平安'},
            ],
            'HSI': [
                {'code': '00700', 'name': '腾讯控股'},
                {'code': '00939', 'name': '建设银行'},
                {'code': '01398', 'name': '工商银行'},
            ],
        }
        
        components = component_map.get(index_code, [])
        self.set_to_cache(cache_key, components)
        return components
    
    def get_realtime_quote(self, index_code: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        try:
            kline_df = self.get_kline_data(index_code, period='D', count=1)
            if kline_df is not None and not kline_df.empty:
                latest = kline_df.iloc[-1]
                return {
                    'code': index_code,
                    'name': self.get_index_info(index_code).get('name', index_code) if self.get_index_info(index_code) else index_code,
                    'close': latest.get('close', 0),
                    'open': latest.get('open', 0),
                    'high': latest.get('high', 0),
                    'low': latest.get('low', 0),
                    'volume': latest.get('volume', 0),
                    'amount': latest.get('amount', 0),
                    'pct_change': ((latest.get('close', 0) - latest.get('open', 0)) / latest.get('open', 1) * 100) if latest.get('open', 0) else 0,
                }
            return None
        except Exception as e:
            logger.error(f"获取指数实时行情失败: {index_code}, {e}")
            return None
    
    def clear_cache(self, index_code: Optional[str] = None):
        if index_code:
            self._no_data_cache.discard(index_code)
        else:
            self._no_data_cache.clear()
            self._index_list = []
        super().clear_cache()


_index_service_instance = None


def get_index_service() -> IndexService:
    global _index_service_instance
    if _index_service_instance is None:
        _index_service_instance = IndexService()
    return _index_service_instance


def reset_index_service():
    global _index_service_instance
    if _index_service_instance:
        _index_service_instance.clear_cache()
    _index_service_instance = None
