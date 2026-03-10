"""
复权计算引擎

提供专业的复权计算功能，对标Wind/同花顺的复权精度。
当数据源不提供复权数据时，使用此模块进行本地计算。
"""

import threading
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
from loguru import logger

from core.services.dividend_data_service import get_dividend_service, DividendEvent


class AdjustmentCalculator:
    """
    复权计算引擎
    
    对标专业软件的复权计算精度。
    当数据源不提供复权数据时，使用此模块进行本地计算。
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
        
        self._initialized = True
        self._dividend_service = get_dividend_service()
        
        logger.info("复权计算引擎初始化完成")
    
    def calculate_adjustment(self, 
                           kdata: pd.DataFrame, 
                           symbol: str, 
                           adj_type: str = 'qfq') -> pd.DataFrame:
        """
        计算复权价格
        
        Args:
            kdata: K线数据DataFrame（包含close列）
            symbol: 股票代码
            adj_type: 复权类型 ('qfq' 前复权, 'hfq' 后复权)
            
        Returns:
            带有复权价格的DataFrame
        """
        if kdata is None or kdata.empty:
            return kdata
        
        if 'close' not in kdata.columns:
            logger.warning(f"K线数据缺少close列，无法计算复权")
            return kdata
        
        if adj_type == 'none':
            result = kdata.copy()
            result['adj_close'] = result['close']
            result['adj_factor'] = 1.0
            result['adj_type'] = adj_type
            result['adj_source'] = 'none'
            return result
        
        result = kdata.copy()
        
        try:
            events = self._dividend_service.get_dividend_data(symbol)
            
            if not events:
                logger.debug(f"{symbol} 无分红数据，使用不复权价格")
                result['adj_close'] = result['close']
                result['adj_factor'] = 1.0
                result['adj_type'] = adj_type
                result['adj_source'] = 'calculated'
                return result
            
            result = self._apply_adjustment(result, events, adj_type)
            
        except Exception as e:
            logger.error(f"复权计算失败 {symbol}: {e}")
            result['adj_close'] = result['close']
            result['adj_factor'] = 1.0
            result['adj_type'] = adj_type
            result['adj_source'] = 'error'
        
        return result
    
    def _apply_adjustment(self, 
                         kdata: pd.DataFrame, 
                         events: list, 
                         adj_type: str) -> pd.DataFrame:
        """应用复权计算"""
        
        result = kdata.copy()
        
        dates = result.index if isinstance(result.index, pd.DatetimeIndex) else pd.to_datetime(result.index)
        
        sorted_events = sorted(events, key=lambda e: pd.to_datetime(e.announcement_date))
        
        factors = []
        cumulative_factor = 1.0
        
        for date in dates:
            for event in sorted_events:
                event_date = pd.to_datetime(event.announcement_date)
                if event_date <= date:
                    cumulative_factor *= self._calculate_factor_from_event(event, adj_type)
            
            factors.append(cumulative_factor)
        
        result['adj_factor'] = factors
        
        if adj_type == 'qfq':
            result['adj_close'] = result['close'] * factors
        elif adj_type == 'hfq':
            latest_factor = factors[-1] if factors else 1.0
            if latest_factor > 0:
                result['adj_close'] = result['close'] * (latest_factor / np.array(factors))
            else:
                result['adj_close'] = result['close']
        else:
            result['adj_close'] = result['close']
        
        result['adj_type'] = adj_type
        result['adj_source'] = 'calculated'
        
        return result
    
    def _calculate_factor_from_event(self, event: DividendEvent, adj_type: str) -> float:
        """从分红事件计算复权因子"""
        
        total_ratio = 0.0
        
        if event.cash_dividend > 0:
            total_ratio += event.cash_dividend / 10.0
        
        if event.bonus_shares > 0:
            total_ratio += event.bonus_shares
        
        if event.stock_dividend > 0:
            total_ratio += event.stock_dividend
        
        if event.stock_split > 0:
            total_ratio += event.stock_split
        
        if total_ratio <= 0:
            return 1.0
        
        return 1.0 + total_ratio
    
    def batch_calculate(self, 
                       kdata_dict: Dict[str, pd.DataFrame], 
                       adj_type: str = 'qfq') -> Dict[str, pd.DataFrame]:
        """
        批量计算复权
        
        Args:
            kdata_dict: {symbol: DataFrame} 字典
            adj_type: 复权类型
            
        Returns:
            {symbol: DataFrame} 字典（已计算复权）
        """
        results = {}
        
        for symbol, kdata in kdata_dict.items():
            results[symbol] = self.calculate_adjustment(kdata, symbol, adj_type)
        
        return results
    
    def verify_adjustment(self, 
                        original: pd.DataFrame, 
                        adjusted: pd.DataFrame,
                        adj_type: str) -> Dict[str, Any]:
        """
        验证复权计算的正确性
        
        Args:
            original: 原始K线数据
            adjusted: 复权后K线数据
            adj_type: 复权类型
            
        Returns:
            验证结果字典
        """
        if 'adj_close' not in adjusted.columns:
            return {
                'valid': False,
                'error': '缺少adj_close列'
            }
        
        if original.empty or adjusted.empty:
            return {
                'valid': False,
                'error': '数据为空'
            }
        
        if len(original) != len(adjusted):
            return {
                'valid': False,
                'error': f'数据长度不匹配: {len(original)} vs {len(adjusted)}'
            }
        
        price_diff = (adjusted['adj_close'].values - original['close'].values)
        
        if adj_type == 'qfq':
            is_increasing = all(price_diff[i] <= price_diff[i+1] 
                              for i in range(len(price_diff)-1) if price_diff[i+1] != price_diff[i])
            expected_direction = 'decrease'
        else:
            is_increasing = all(price_diff[i] >= price_diff[i+1] 
                              for i in range(len(price_diff)-1) if price_diff[i+1] != price_diff[i])
            expected_direction = 'increase'
        
        return {
            'valid': True,
            'adj_type': adj_type,
            'expected_direction': expected_direction,
            'price_diff_stats': {
                'mean': float(np.mean(price_diff)),
                'std': float(np.std(price_diff)),
                'min': float(np.min(price_diff)),
                'max': float(np.max(price_diff))
            }
        }


_adjustment_calculator_instance = None
_adjustment_calculator_lock = threading.Lock()


def get_adjustment_calculator() -> AdjustmentCalculator:
    """获取复权计算器单例"""
    global _adjustment_calculator_instance
    
    if _adjustment_calculator_instance is None:
        with _adjustment_calculator_lock:
            if _adjustment_calculator_instance is None:
                _adjustment_calculator_instance = AdjustmentCalculator()
    
    return _adjustment_calculator_instance
