from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from loguru import logger
from typing import Optional, Dict, Any
from core.services.enhanced_indicator_service import EnhancedIndicatorService
from core.utils.data_standardizer import DataStandardizer

class TakeProfitStrategy(ABC):
    """止盈策略抽象基类"""
    
    def __init__(self, name: str):
        self.name = name
        try:
            from core.containers import get_service_container
            container = get_service_container()
            self._indicator_service = container.resolve(EnhancedIndicatorService)
        except Exception:
            self._indicator_service = EnhancedIndicatorService()
        self._data_standardizer = DataStandardizer()
    
    @abstractmethod
    def calculate_profit_price(self, data: pd.DataFrame, current_price: float, 
                             position_info: Optional[Dict[str, Any]] = None) -> float:
        """计算止盈价格"""
        pass
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取参数"""
        return getattr(self, f"_{key}", default)
    
    def set_param(self, key: str, value: Any) -> None:
        """设置参数"""
        setattr(self, f"_{key}", value)

class AdaptiveTakeProfit(TakeProfitStrategy):
    """
    自适应止盈策略
    基于pandas DataFrame的自定义止盈策略
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super(AdaptiveTakeProfit, self).__init__("AdaptiveTakeProfit")

        # 设置默认参数
        self.set_param("atr_period", 14)         # ATR周期
        self.set_param("atr_multiplier", 2)      # ATR倍数
        self.set_param("atr_method", "sma")      # ATR计算方法: 'sma'/'wilder'/'ema'
        self.set_param("ma_period", 20)          # 均线周期
        self.set_param("volatility_period", 20)  # 波动率计算周期
        self.set_param("min_take_profit", 0.02)  # 最小止盈比例
        self.set_param("max_take_profit", 0.2)   # 最大止盈比例
        self.set_param("trailing_profit", 0.03)  # 跟踪止盈比例
        self.set_param("profit_lock", 0.05)      # 盈利锁定比例
        self.set_param("volatility_factor", 0.5)  # 波动率因子
        self.set_param("trend_factor", 0.3)      # 趋势因子
        self.set_param("market_factor", 0.2)     # 市场因子

        # R269-D3: 支持参数覆盖 (与 AdaptiveStopLoss/EnhancedMoneyManager 构造对齐)
        if params is not None and isinstance(params, dict):
            for key, value in params.items():
                self.set_param(key, value)

    def calculate_profit_price(self, data: pd.DataFrame, current_price: float, 
                             position_info: Optional[Dict[str, Any]] = None) -> float:
        """计算止盈价格"""
        try:
            if position_info is None:
                position_info = {}

            # 1. 计算技术指标
            atr = self._calculate_atr(data)
            ma = self._calculate_ma(data)
            volatility = self._calculate_volatility(data)
            trend = self._calculate_trend(data)

            # 2. 计算不同类型的止盈价格
            profits = {
                'atr': self._calculate_atr_profit(current_price, atr, trend),
                'ma': self._calculate_ma_profit(current_price, ma, trend),
                'trailing': self._calculate_trailing_profit(current_price, position_info, trend),
                'volatility': self._calculate_volatility_profit(current_price, volatility, trend),
                'fixed': self._calculate_fixed_profit(current_price, trend)
            }

            # 3. 选择最终的止盈价格
            profit_price = self._select_profit_price(
                current_price, profits, position_info, trend)

            return profit_price

        except Exception as e:
            logger.error(f"止盈价格计算错误: {str(e)}")
            return 0.0

    def _calculate_atr(self, data: pd.DataFrame, method: str = None) -> float:
        """
        ATR计算，支持三种平滑方式：
          - 'sma':   简单移动平均SMA（当前默认，与旧版兼容）
          - 'wilder': Wilder平滑（标准ATR，与indicator库JIT版一致）
          - 'ema':    指数移动平均EMA（与indicator库ewm版一致）
        """
        try:
            if method is None:
                method = self.get_param("atr_method", "sma")

            high = data['high'].values
            low = data['low'].values
            close = data['close'].values

            tr = np.maximum(
                high[1:] - low[1:],
                np.maximum(
                    np.abs(high[1:] - close[:-1]),
                    np.abs(low[1:] - close[:-1])
                )
            )

            period = self.get_param("atr_period")
            if len(tr) < period:
                return 0.0

            if method == 'wilder':
                return self._wilder_atr(tr, period)
            elif method == 'ema':
                return self._ema_atr(tr, period)
            else:
                return np.mean(tr[-period:])

        except Exception as e:
            logger.error(f"ATR计算错误: {str(e)}")
            return 0.0

    def _wilder_atr(self, tr: np.ndarray, period: int) -> float:
        tr_series = pd.Series(tr)
        atr = tr_series.iloc[:period].mean()
        for i in range(period, len(tr_series)):
            atr = (atr * (period - 1) + tr_series.iloc[i]) / period
        return atr

    def _ema_atr(self, tr: np.ndarray, period: int) -> float:
        tr_series = pd.Series(tr)
        return tr_series.ewm(span=period, adjust=False).mean().iloc[-1]

    def _calculate_ma(self, data: pd.DataFrame) -> float:
        """计算移动平均"""
        try:
            return data['close'].rolling(window=self.get_param("ma_period")).mean().iloc[-1]
        except Exception as e:
            logger.error(f"MA计算错误: {str(e)}")
            return 0.0

    def _calculate_volatility(self, data: pd.DataFrame) -> float:
        """计算波动率"""
        try:
            returns = data['close'].pct_change()
            return returns.rolling(window=self.get_param("volatility_period")).std().iloc[-1]
        except Exception as e:
            logger.error(f"波动率计算错误: {str(e)}")
            return 0.0

    def _calculate_trend(self, data: pd.DataFrame) -> int:
        """计算趋势"""
        try:
            ma = data['close'].rolling(window=self.get_param("ma_period")).mean()
            return 1 if data['close'].iloc[-1] > ma.iloc[-1] else -1
        except Exception as e:
            logger.error(f"趋势计算错误: {str(e)}")
            return 0

    def _calculate_atr_profit(self, price: float, atr: float, trend: int) -> float:
        """计算ATR止盈价格"""
        try:
            profit_distance = atr * self.get_param("atr_multiplier")
            if trend > 0:
                return price + profit_distance
            else:
                return price - profit_distance
        except Exception as e:
            logger.error(f"ATR止盈计算错误: {str(e)}")
            return 0.0

    def _calculate_ma_profit(self, price: float, ma: float, trend: int) -> float:
        """计算均线止盈价格"""
        try:
            profit_distance = self.get_param("min_take_profit")
            if trend > 0:
                return ma * (1 + profit_distance)
            else:
                return ma * (1 - profit_distance)
        except Exception as e:
            logger.error(f"均线止盈计算错误: {str(e)}")
            return 0.0

    def _calculate_trailing_profit(self, price: float, position_info: Dict[str, Any], trend: int) -> float:
        """计算跟踪止盈价格"""
        try:
            trailing_pct = self.get_param("trailing_profit")
            if trend > 0:
                highest_price = position_info.get('highest_price', price)
                if price > highest_price:
                    highest_price = price
                    position_info['highest_price'] = highest_price
                return highest_price * (1 - trailing_pct)
            else:
                lowest_price = position_info.get('lowest_price', price)
                if price < lowest_price:
                    lowest_price = price
                    position_info['lowest_price'] = lowest_price
                return lowest_price * (1 + trailing_pct)
        except Exception as e:
            logger.error(f"跟踪止盈计算错误: {str(e)}")
            return 0.0

    def _calculate_volatility_profit(self, price: float, volatility: float, trend: int = 1) -> float:
        """计算波动率止盈价格"""
        try:
            profit_distance = price * volatility * self.get_param("volatility_factor")
            if trend < 0:
                return price - profit_distance
            return price + profit_distance
        except Exception as e:
            logger.error(f"波动率止盈计算错误: {str(e)}")
            return 0.0

    def _calculate_fixed_profit(self, price: float, trend: int = 1) -> float:
        """计算固定止盈价格"""
        try:
            if trend < 0:
                return price * (1 - self.get_param("min_take_profit"))
            return price * (1 + self.get_param("min_take_profit"))
        except Exception as e:
            logger.error(f"固定止盈计算错误: {str(e)}")
            return 0.0

    def _select_profit_price(self, price: float, profits: Dict[str, float], 
                           position_info: Dict[str, Any], trend: int) -> float:
        """选择最终的止盈价格"""
        try:
            entry_price = position_info.get('entry_price', price)
            
            if trend > 0:
                profit_price = max(
                    profits['atr'],
                    profits['ma'],
                    profits['trailing'],
                    profits['volatility']
                )
            else:
                profit_price = min(
                    profits['atr'],
                    profits['ma'],
                    profits['trailing'],
                    profits['volatility']
                )

            if trend < 0:
                min_profit = price * (1 - self.get_param("max_take_profit"))
                max_profit = price * (1 - self.get_param("min_take_profit"))
            else:
                min_profit = price * (1 + self.get_param("min_take_profit"))
                max_profit = price * (1 + self.get_param("max_take_profit"))
            profit_price = min(max_profit, max(profit_price, min_profit))

            if trend < 0:
                if price < entry_price:
                    profit_ratio = (entry_price - price) / entry_price
                    if profit_ratio > self.get_param("profit_lock"):
                        lock_price = entry_price * (1 - self.get_param("profit_lock"))
                        profit_price = max(profit_price, lock_price)
            else:
                if price > entry_price:
                    profit_ratio = (price - entry_price) / entry_price
                    if profit_ratio > self.get_param("profit_lock"):
                        lock_price = entry_price * (1 + self.get_param("profit_lock"))
                        profit_price = max(profit_price, lock_price)

            return profit_price

        except Exception as e:
            logger.error(f"选择止盈价格错误: {str(e)}")
            return 0.0
