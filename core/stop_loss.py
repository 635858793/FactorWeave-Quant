from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from loguru import logger
from typing import Optional, Dict, Any, Tuple
from core.services.enhanced_indicator_service import EnhancedIndicatorService
from core.utils.data_standardizer import DataStandardizer

class StopLossStrategy(ABC):
    """止损策略抽象基类"""
    
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
    def calculate_stop_price(self, data: pd.DataFrame, current_price: float,
                           position_info: Optional[Dict[str, Any]] = None) -> float:
        """计算止损价格"""
        pass
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取参数"""
        return getattr(self, f"_{key}", default)
    
    def set_param(self, key: str, value: Any) -> None:
        """设置参数"""
        setattr(self, f"_{key}", value)

class AdaptiveStopLoss(StopLossStrategy):
    """
    自适应止损策略
    基于技术指标和风险控制的智能止损系统
    """

    def __init__(self, params=None):
        super(AdaptiveStopLoss, self).__init__("AdaptiveStopLoss")

        # 设置默认参数
        self._atr_period = 14         # ATR周期
        self._atr_multiplier = 2      # ATR倍数
        self._atr_method = 'sma'      # ATR计算方法: 'sma'/'wilder'/'ema'
        self._ma_period = 20          # 均线周期
        self._volatility_period = 20  # 波动率计算周期
        self._min_stop_loss = 0.02    # 最小止损比例
        self._max_stop_loss = 0.1     # 最大止损比例
        self._trailing_stop = 0.03    # 跟踪止损比例
        self._profit_lock = 0.05      # 盈利锁定比例
        self._volatility_factor = 0.5  # 波动率因子
        self._trend_factor = 0.3      # 趋势因子
        self._market_factor = 0.2     # 市场因子

        if params is not None and isinstance(params, dict):
            for key, value in params.items():
                self.set_param(key, value)

        # 初始化持仓信息
        self.positions = {}  # 记录每个持仓的止损信息

    def calculate_stop_price(self, data: pd.DataFrame, current_price: float,
                           position_info: Optional[Dict[str, Any]] = None) -> float:
        """计算止损价格"""
        try:
            # 1. 检查数据有效性
            if data.empty or current_price <= 0:
                return 0.0

            # 2. 获取或初始化持仓信息
            position = position_info or {}

            # 3. 计算技术指标
            atr = self._calculate_atr(data)
            ma = self._calculate_ma(data)
            volatility = self._calculate_volatility(data)
            trend = self._calculate_trend(data)

            # 4. 计算不同类型的止损价格
            stops = {
                'atr': self._calculate_atr_stop(current_price, atr, trend),
                'ma': self._calculate_ma_stop(current_price, ma),
                'trailing': self._calculate_trailing_stop(current_price, position, trend),
                'volatility': self._calculate_volatility_stop(current_price, volatility, trend),
                'fixed': self._calculate_fixed_stop(current_price, trend)
            }

            # 5. 选择最终的止损价格
            stop_price = self._select_stop_price(current_price, stops, position, trend)

            # 6. 更新持仓信息
            self._update_position_info(current_price, stop_price, position)

            return stop_price

        except Exception as e:
            logger.error(f"止损价格计算错误: {str(e)}")
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

    def _get_position_info(self, position_key: str) -> Dict[str, Any]:
        """获取持仓信息"""
        try:
            if position_key not in self.positions:
                self.positions[position_key] = {
                    'entry_price': 0.0,
                    'highest_price': 0.0,
                    'lowest_price': 0.0,
                    'last_stop_price': 0.0,
                    'last_update': None
                }

            return self.positions[position_key]

        except Exception as e:
            logger.error(f"获取持仓信息错误: {str(e)}")
            return {}

    def _calculate_atr_stop(self, price: float, atr: float, trend: int) -> float:
        """计算ATR止损价格"""
        try:
            stop_distance = atr * self.get_param("atr_multiplier")
            if trend > 0:
                return price - stop_distance
            else:
                return price + stop_distance
        except Exception as e:
            logger.error(f"ATR止损计算错误: {str(e)}")
            return 0.0

    def _calculate_ma_stop(self, price: float, ma: float) -> float:
        """计算均线止损价格"""
        try:
            return ma
        except Exception as e:
            logger.error(f"均线止损计算错误: {str(e)}")
            return 0.0

    def _calculate_trailing_stop(self, price: float, position: Dict[str, Any], trend: int = 1) -> float:
        """计算跟踪止损价格"""
        try:
            if trend < 0:
                if price < position.get('lowest_price', price):
                    position['lowest_price'] = price
                lowest_price = position.get('lowest_price', price)
                stop_distance = lowest_price * self.get_param("trailing_stop")
                return lowest_price + stop_distance
            if price > position.get('highest_price', price):
                position['highest_price'] = price
            highest_price = position.get('highest_price', price)
            stop_distance = highest_price * self.get_param("trailing_stop")
            return highest_price - stop_distance

        except Exception as e:
            logger.error(f"跟踪止损计算错误: {str(e)}")
            return 0.0

    def _calculate_volatility_stop(self, price: float, volatility: float, trend: int = 1) -> float:
        """计算波动率止损价格"""
        try:
            stop_distance = price * volatility * self.get_param("volatility_factor")
            if trend < 0:
                return price + stop_distance
            return price - stop_distance
        except Exception as e:
            logger.error(f"波动率止损计算错误: {str(e)}")
            return 0.0

    def _calculate_fixed_stop(self, price: float, trend: int = 1) -> float:
        """计算固定止损价格"""
        try:
            if trend < 0:
                return price * (1 + self.get_param("min_stop_loss"))
            return price * (1 - self.get_param("min_stop_loss"))
        except Exception as e:
            logger.error(f"固定止损计算错误: {str(e)}")
            return 0.0

    def _select_stop_price(self, price: float, stops: Dict[str, float], 
                          position: Dict[str, Any], trend: int) -> float:
        """选择最终的止损价格"""
        try:
            if trend > 0:
                stop_price = min(
                    stops['atr'],
                    stops['ma'],
                    stops['trailing'],
                    stops['volatility']
                )
            else:
                stop_price = max(
                    stops['atr'],
                    stops['ma'],
                    stops['trailing'],
                    stops['volatility']
                )

            if trend < 0:
                min_stop = price * (1 + self.get_param("min_stop_loss"))
                max_stop = price * (1 + self.get_param("max_stop_loss"))
            else:
                min_stop = price * (1 - self.get_param("max_stop_loss"))
                max_stop = price * (1 - self.get_param("min_stop_loss"))
            stop_price = max(min_stop, min(stop_price, max_stop))

            entry_price = position.get('entry_price', price)
            if trend < 0:
                if price < entry_price:
                    profit_ratio = (entry_price - price) / entry_price
                    if profit_ratio > self.get_param("profit_lock"):
                        lock_price = entry_price * (1 - self.get_param("profit_lock"))
                        stop_price = max(stop_price, lock_price)
            else:
                if price > entry_price:
                    profit_ratio = (price - entry_price) / entry_price
                    if profit_ratio > self.get_param("profit_lock"):
                        lock_price = entry_price * (1 + self.get_param("profit_lock"))
                        stop_price = max(stop_price, lock_price)

            return stop_price

        except Exception as e:
            logger.error(f"选择止损价格错误: {str(e)}")
            return 0.0

    def _update_position_info(self, current_price: float, stop_price: float, 
                            position: Dict[str, Any]) -> None:
        """更新持仓信息"""
        try:
            if not position.get('entry_price'):
                position['entry_price'] = current_price
                position['highest_price'] = current_price
                position['lowest_price'] = current_price

            position['last_stop_price'] = stop_price

            if current_price > position.get('highest_price', current_price):
                position['highest_price'] = current_price
            if current_price < position.get('lowest_price', current_price):
                position['lowest_price'] = current_price

        except Exception as e:
            logger.error(f"更新持仓信息错误: {str(e)}")
