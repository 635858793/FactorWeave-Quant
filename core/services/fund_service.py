from typing import Optional, Dict, Any, List
import pandas as pd
from .base_service import BaseService, CacheableService, ConfigurableService
from loguru import logger


class FundService(CacheableService, ConfigurableService):
    """
    基金服务
    
    负责基金数据的获取、缓存和管理，包括：
    - 公募基金（股票型、债券型、混合型、货币型等）
    - 私募基金
    - 基金行情数据
    - 基金基本信息查询
    - 基金持仓查询
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, cache_size: int = 100,
                 service_container=None, **kwargs):
        self.service_container = service_container
        
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'service_container'}
        CacheableService.__init__(self, cache_size=cache_size, namespace='fund_service', **filtered_kwargs)
        ConfigurableService.__init__(self, config=config, **filtered_kwargs)
        
        self._unified_data_manager = None
        self._fund_list = []
        self._no_data_cache = set()
        self._last_query_time = {}
        
    def _do_initialize(self) -> None:
        try:
            from .unified_data_manager import get_unified_data_manager
            self._unified_data_manager = get_unified_data_manager()
            if self._unified_data_manager:
                logger.info("FundService 初始化成功，连接到 UnifiedDataManager")
            else:
                logger.warning("UnifiedDataManager 不可用，FundService 将使用降级模式")
        except Exception as e:
            logger.warning(f"FundService 初始化失败: {e}")
    
    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def get_fund_list(self, fund_type: Optional[str] = None, 
                     market: str = 'all') -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"fund_list_{fund_type}_{market}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            if self._unified_data_manager:
                df = self._unified_data_manager.get_asset_list(asset_type='fund', market=market)
                if df is not None and not df.empty:
                    fund_list = df.to_dict('records')
                    if fund_type:
                        fund_list = [f for f in fund_list if f.get('type') == fund_type]
                    self.set_to_cache(cache_key, fund_list)
                    self._fund_list = fund_list
                    logger.info(f"真实数据路径: 获取基金列表成功, 共 {len(fund_list)} 条")
                    return fund_list
            
            logger.warning("降级路径: 无法获取真实基金列表")
            return self._get_default_fund_list(fund_type)
        except Exception as e:
            logger.error(f"获取基金列表失败: {e}")
            return self._get_default_fund_list(fund_type)
    
    def _get_default_fund_list(self, fund_type: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.warning("降级路径: 返回空基金列表，真实数据源不可用")
        return []
    
    def get_kline_data(self, fund_code: str, period: str = 'D', 
                       count: int = 365) -> pd.DataFrame:
        self._ensure_initialized()
        
        cache_key = f"fund_kline_{fund_code}_{period}_{count}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        if fund_code in self._no_data_cache:
            return pd.DataFrame()
        
        try:
            if self._unified_data_manager:
                df = self._unified_data_manager.get_kline_data(
                    stock_code=fund_code,
                    period=period,
                    count=count,
                    asset_type='fund'
                )
                if df is not None and not df.empty:
                    self.set_to_cache(cache_key, df)
                    logger.info(f"真实数据路径: 获取基金 {fund_code} K线数据成功, {len(df)} 条")
                    return df
                else:
                    self._no_data_cache.add(fund_code)
            
            logger.warning(f"降级路径: 基金 {fund_code} 无真实K线数据")
            return self._generate_mock_kline_data(fund_code, period, count)
        except Exception as e:
            logger.error(f"获取基金K线数据失败: {fund_code}, {e}")
            return self._generate_mock_kline_data(fund_code, period, count)
    
    def _generate_mock_kline_data(self, fund_code: str, period: str, count: int) -> pd.DataFrame:
        logger.warning(f"降级路径: 基金 {fund_code} 无真实K线数据，返回空DataFrame")
        return pd.DataFrame()
    
    def get_fund_info(self, fund_code: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"fund_info_{fund_code}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            fund_list = self.get_fund_list()
            for fund in fund_list:
                if fund.get('code') == fund_code:
                    self.set_to_cache(cache_key, fund)
                    return fund
            
            for fund in self._get_default_fund_list(None):
                if fund.get('code') == fund_code:
                    self.set_to_cache(cache_key, fund)
                    return fund
            
            return None
        except Exception as e:
            logger.error(f"获取基金信息失败: {fund_code}, {e}")
            return None
    
    def search_funds(self, keyword: str) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        if not keyword:
            return []
        
        keyword = keyword.lower()
        fund_list = self.get_fund_list()
        
        results = [
            fund for fund in fund_list
            if keyword in fund.get('name', '').lower() or keyword in fund.get('code', '').lower()
        ]
        
        return results
    
    def get_fund_nav_history(self, fund_code: str, 
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> pd.DataFrame:
        self._ensure_initialized()
        
        cache_key = f"fund_nav_{fund_code}_{start_date}_{end_date}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            df = self.get_kline_data(fund_code, period='D', count=365)
            
            if start_date and not df.empty:
                df = df[df['date'] >= start_date]
            if end_date and not df.empty:
                df = df[df['date'] <= end_date]
            
            if not df.empty:
                self.set_to_cache(cache_key, df)
            return df
        except Exception as e:
            logger.error(f"获取基金净值历史失败: {fund_code}, {e}")
            return pd.DataFrame()
    
    def get_fund_holdings(self, fund_code: str, 
                         date: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        
        cache_key = f"fund_holdings_{fund_code}_{date}"
        cached_result = self.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            if self._unified_data_manager:
                holdings = self._unified_data_manager.get_fund_holdings(fund_code, date) if hasattr(self._unified_data_manager, 'get_fund_holdings') else None
                if holdings:
                    self.set_to_cache(cache_key, holdings)
                    logger.info(f"真实数据路径: 获取基金 {fund_code} 持仓数据成功")
                    return holdings
            
            logger.warning(f"降级路径: 基金 {fund_code} 无真实持仓数据")
            return []
        except Exception as e:
            logger.warning(f"降级路径: 获取基金 {fund_code} 持仓数据失败: {e}")
            return []
    
    def calculate_fund_return(self, fund_code: str, 
                             days: int = 30) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        try:
            df = self.get_kline_data(fund_code, period='D', count=days + 1)
            if df is None or df.empty or len(df) < 2:
                return None
            
            latest = df.iloc[-1]
            oldest = df.iloc[0]
            
            start_price = oldest.get('close', 0)
            end_price = latest.get('close', 0)
            
            if start_price == 0:
                return None
            
            total_return = (end_price - start_price) / start_price * 100
            daily_return = total_return / days
            
            return {
                'fund_code': fund_code,
                'fund_name': self.get_fund_info(fund_code).get('name', fund_code) if self.get_fund_info(fund_code) else fund_code,
                'start_date': oldest.get('date'),
                'end_date': latest.get('date'),
                'start_price': start_price,
                'end_price': end_price,
                'total_return': round(total_return, 2),
                'daily_return': round(daily_return, 4),
                'days': days,
            }
        except Exception as e:
            logger.error(f"计算基金收益失败: {fund_code}, {e}")
            return None
    
    def get_realtime_quote(self, fund_code: str) -> Optional[Dict[str, Any]]:
        self._ensure_initialized()
        
        try:
            kline_df = self.get_kline_data(fund_code, period='D', count=1)
            if kline_df is not None and not kline_df.empty:
                latest = kline_df.iloc[-1]
                return {
                    'code': fund_code,
                    'name': self.get_fund_info(fund_code).get('name', fund_code) if self.get_fund_info(fund_code) else fund_code,
                    'net_value': latest.get('close', 0),
                    'acc_value': latest.get('close', 0) * 1.5,
                    'pct_change': ((latest.get('close', 0) - latest.get('open', 0)) / latest.get('open', 1) * 100) if latest.get('open', 0) else 0,
                }
            return None
        except Exception as e:
            logger.error(f"获取基金实时行情失败: {fund_code}, {e}")
            return None
    
    def clear_cache(self, fund_code: Optional[str] = None):
        if fund_code:
            self._no_data_cache.discard(fund_code)
        else:
            self._no_data_cache.clear()
            self._fund_list = []
        super().clear_cache()


_fund_service_instance = None


def get_fund_service() -> FundService:
    global _fund_service_instance
    if _fund_service_instance is None:
        _fund_service_instance = FundService()
    return _fund_service_instance


def reset_fund_service():
    global _fund_service_instance
    if _fund_service_instance:
        _fund_service_instance.clear_cache()
    _fund_service_instance = None
