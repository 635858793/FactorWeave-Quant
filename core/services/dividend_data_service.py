"""
分红送配数据服务

提供股票分红、送股、配股等信息的获取和缓存。
对标Wind/同花顺的专业级数据获取能力。
"""

import threading
import time  # HVD-241-P3-A: L110/122 使用 time.time() (R241 修复缺 import → 必现 NameError)
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import pandas as pd
from loguru import logger

from .base_service import BaseService


@dataclass
class DividendEvent:
    """分红事件"""
    symbol: str
    announcement_date: str
    dividend_date: Optional[str]
    cash_dividend: float  # 每股现金分红（元）
    stock_dividend: float  # 每股送股比例
    stock_split: float  # 每股配股比例
    split_ratio: float  # 拆股比例
    bonus_shares: float  # 送转股比例
    rights_issue_price: Optional[float]  # 配股价
    
    @property
    def total_dividend_ratio(self) -> float:
        """总分红比例（现金+送转）"""
        return self.cash_dividend + self.bonus_shares * 10


class DividendDataService(BaseService):
    """
    分红送配数据服务
    
    提供股票历史分红送配数据的获取和缓存。
    支持多种数据源：AKShare、Tushare等。
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        super().__init__()
        self._initialized = True
        self._akshare = None
        self._init_data_sources()
        
        self._memory_cache: Dict[str, List[DividendEvent]] = {}
        self._memory_cache_time: Dict[str, float] = {}
        self._cache_ttl = 7 * 24 * 3600
        
        self._hot_stocks = ['000001', '600000', '600519', '000002', '601318', '601941']
        self._preload_hot_stocks()
        
        logger.info("分红数据服务初始化完成")
    
    def _init_data_sources(self):
        """初始化数据源"""
        try:
            import akshare as ak
            self._akshare = ak
            logger.debug("AKShare数据源已加载")
        except ImportError:
            logger.warning("AKShare未安装，部分分红数据可能无法获取")
    
    def _preload_hot_stocks(self):
        """预加载热门股票分红数据"""
        def _preload():
            for symbol in self._hot_stocks:
                try:
                    self.get_dividend_data(symbol)
                except Exception as e:
                    logger.debug(f"预加载分红数据失败 {symbol}: {e}")
        
        threading.Thread(target=_preload, daemon=True).start()
    
    def get_dividend_data(self, symbol: str) -> List[DividendEvent]:
        """
        获取股票分红数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            分红事件列表
        """
        if not symbol:
            return []
        
        symbol = symbol.strip()
        
        if symbol in self._memory_cache:
            cache_time = self._memory_cache_time.get(symbol, 0)
            if time.time() - cache_time < self._cache_ttl:
                return self._memory_cache[symbol]

        events = self._fetch_dividend_data(symbol)

        max_cache = getattr(self, '_max_cache_size', 2000)
        if len(self._memory_cache) >= max_cache:
            oldest = min(self._memory_cache_time, key=self._memory_cache_time.get)
            del self._memory_cache[oldest]
            del self._memory_cache_time[oldest]

        self._memory_cache[symbol] = events
        self._memory_cache_time[symbol] = time.time()
        
        return events
    
    def _fetch_dividend_data(self, symbol: str) -> List[DividendEvent]:
        """从数据源获取分红数据"""
        events = []
        
        if self._akshare:
            try:
                events = self._fetch_from_akshare(symbol)
            except Exception as e:
                logger.error(f"从AKShare获取分红数据失败 {symbol}: {e}")
        
        return events
    
    def _fetch_from_akshare(self, symbol: str) -> List[DividendEvent]:
        """从AKShare获取分红数据"""
        events = []
        
        try:
            symbol_clean = symbol.split('.')[0] if '.' in symbol else symbol
            
            df = self._akshare.stock_dividend_cnftp(symbol=symbol_clean)
            
            if df is None or df.empty:
                return events
            
            for row_dict in df.to_dict('records'):
                try:
                    event = DividendEvent(
                        symbol=symbol,
                        announcement_date=str(row_dict.get('公告日期', '')),
                        dividend_date=str(row_dict.get('分红送转日期', '')),
                        cash_dividend=float(row_dict.get('每股现金分红', 0) or 0),
                        stock_dividend=float(row_dict.get('每股送股比例', 0) or 0),
                        stock_split=float(row_dict.get('每股转增比例', 0) or 0),
                        split_ratio=float(row_dict.get('拆股比例', 0) or 0),
                        bonus_shares=float(row_dict.get('送转股比例', 0) or 0),
                        rights_issue_price=None
                    )
                    events.append(event)
                except Exception as e:
                    logger.debug(f"解析分红记录失败: {e}")
                    continue
            
            logger.debug(f"从AKShare获取 {symbol} 分红数据成功: {len(events)} 条")
            
        except Exception as e:
            logger.debug(f"AKShare分红接口调用失败: {e}")
        
        return events
    
    def get_adjustment_factor(self, symbol: str, 
                             start_date: str, 
                             end_date: str) -> pd.Series:
        """
        获取指定日期范围内的复权因子序列
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            复权因子序列（与日期对应）
        """
        events = self.get_dividend_data(symbol)
        
        if not events:
            return pd.Series([1.0])
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        factors = []
        cumulative_factor = 1.0
        
        current_date = start_dt
        while current_date <= end_dt:
            for event in events:
                event_date = pd.to_datetime(event.announcement_date)
                if event_date <= current_date:
                    factor = self._calculate_factor_from_event(event)
                    cumulative_factor *= factor
            
            factors.append(cumulative_factor)
            current_date += pd.Timedelta(days=1)
        
        return pd.Series(factors)
    
    def _calculate_factor_from_event(self, event: DividendEvent) -> float:
        """从分红事件计算复权因子"""
        if event.cash_dividend > 0:
            return 1.0
        
        total_ratio = event.bonus_shares
        if total_ratio > 0:
            return 1.0 + total_ratio
        
        return 1.0
    
    def calculate_forward_adjustment(self, prices: pd.Series, 
                                    symbol: str) -> pd.Series:
        """
        计算前复权价格
        
        Args:
            prices: 原始价格序列
            symbol: 股票代码
            
        Returns:
            前复权价格序列
        """
        events = self.get_dividend_data(symbol)
        
        if not events:
            return prices
        
        dates = prices.index if hasattr(prices, 'index') else range(len(prices))
        
        adjusted = []
        cumulative_factor = 1.0
        
        for i, date in enumerate(dates):
            current_date = pd.to_datetime(date) if isinstance(date, str) else date
            
            for event in events:
                event_date = pd.to_datetime(event.announcement_date)
                if event_date <= current_date:
                    factor = self._calculate_factor_from_event(event)
                    cumulative_factor *= factor
            
            adjusted.append(prices.iloc[i] * cumulative_factor)
        
        return pd.Series(adjusted, index=dates)
    
    def calculate_backward_adjustment(self, prices: pd.Series,
                                     symbol: str) -> pd.Series:
        """
        计算后复权价格
        
        Args:
            prices: 原始价格序列
            symbol: 股票代码
            
        Returns:
            后复权价格序列
        """
        events = self.get_dividend_data(symbol)
        
        if not events:
            return prices
        
        dates = prices.index if hasattr(prices, 'index') else range(len(prices))
        
        adjusted = []
        cumulative_factor = 1.0
        
        for i, date in enumerate(dates):
            current_date = pd.to_datetime(date) if isinstance(date, str) else date
            
            for event in events:
                event_date = pd.to_datetime(event.announcement_date)
                if event_date <= current_date:
                    factor = self._calculate_factor_from_event(event)
                    cumulative_factor /= factor
            
            adjusted.append(prices.iloc[i] * cumulative_factor)
        
        return pd.Series(adjusted, index=dates)
    
    def clear_cache(self, symbol: Optional[str] = None):
        """
        清除缓存
        
        Args:
            symbol: 股票代码，如果为None则清除所有缓存
        """
        if symbol:
            self._memory_cache.pop(symbol, None)
            self._memory_cache_time.pop(symbol, None)
        else:
            self._memory_cache.clear()
            self._memory_cache_time.clear()
        
        logger.info(f"分红数据缓存已清除: {symbol or '全部'}")


_dividend_service_instance = None
_dividend_service_lock = threading.Lock()


def get_dividend_service() -> DividendDataService:
    """获取分红数据服务单例"""
    global _dividend_service_instance
    
    if _dividend_service_instance is None:
        with _dividend_service_lock:
            if _dividend_service_instance is None:
                _dividend_service_instance = DividendDataService()
    
    return _dividend_service_instance
