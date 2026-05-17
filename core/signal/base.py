"""
核心信号系统基类 - 完全脱离 hikyuu 依赖

该模块提供了基于 pandas 和 TA-Lib 的信号计算系统，完全替代 hikyuu 信号基类。
支持标准 OHLCV 数据格式，兼容多种数据源。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from core.services.enhanced_indicator_service import EnhancedIndicatorService
from core.utils.data_standardizer import DataStandardizer
from core.indicator_adapter import calc_ma, calc_macd, calc_rsi
from loguru import logger


@dataclass
class Signal:
    """标准信号数据结构"""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'hold'
    price: float
    strength: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class BaseSignal:
    """
    信号系统基类 - 无 hikyuu 依赖
    
    替代原有的 hikyuu SignalBase，提供纯 pandas + TA-Lib 的信号计算能力。
    支持标准 OHLCV 数据格式的信号生成和评估。
    """

    def __init__(self, name: str = "BaseSignal"):
        self.name = name
        self._params = {}
        self._cache = {}
        try:
            from core.containers import get_service_container
            container = get_service_container()
            self._indicator_service = container.resolve(EnhancedIndicatorService)
        except Exception:
            self._indicator_service = EnhancedIndicatorService()
        self._data_standardizer = DataStandardizer()
        
        # 信号存储
        self._buy_signals: List[Signal] = []
        self._sell_signals: List[Signal] = []
        
        # 默认参数
        self._set_default_params()

    def _set_default_params(self):
        """设置默认参数"""
        default_params = {
            "n_fast": 12,
            "n_slow": 26,
            "n_signal": 9,
            "rsi_window": 14,
            "kdj_n": 9,
            "boll_n": 20,
            "atr_n": 14,
            "volume_threshold": 1.5
        }
        self._params.update(default_params)

    def clone(self) -> 'BaseSignal':
        """克隆信号实例"""
        cloned = self.__class__(name=self.name)
        cloned._params = self._params.copy()
        cloned._cache = self._cache.copy()
        return cloned

    def calculate(self, data: pd.DataFrame, symbol: str = "") -> List[Signal]:
        """
        计算交易信号 - 主要接口
        
        Args:
            data: 标准 OHLCV 数据
            symbol: 交易标的代码
            
        Returns:
            List[Signal]: 计算得到的交易信号列表
        """
        try:
            # 数据验证和标准化
            if data is None or len(data) == 0:
                logger.warning(f"信号计算收到空数据，直接返回 - {symbol}")
                return []
            
            # 标准化数据格式
            standardized_data = self._data_standardizer.standardize_kline_data(
                data, symbol, "D"
            )
            
            if standardized_data is None or len(standardized_data) == 0:
                logger.warning(f"数据标准化失败 - {symbol}")
                return []
                
            # 清空之前的信号
            self._buy_signals.clear()
            self._sell_signals.clear()
            
            # 计算技术指标
            indicators = self._calculate_indicators(standardized_data)
            
            # 生成交易信号
            signals = self._generate_signals(standardized_data, indicators, symbol)
            
            # 记录信号
            self._record_signals(signals)
            
            return signals
            
        except Exception as e:
            logger.error(f"信号计算失败 {symbol}: {str(e)}")
            return []

    def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """计算技术指标"""
        try:
            # 使用增强指标服务计算指标
            indicators = {}
            
            # MA 指标
            indicators['ma_fast'] = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("n_fast", 12)}
            )
            indicators['ma_slow'] = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("n_slow", 26)}
            )
            
            # MACD 指标
            indicators['macd'] = self._indicator_service.calculate_indicator(
                'MACD', data, {
                    'fastperiod': self.get_param("n_fast", 12),
                    'slowperiod': self.get_param("n_slow", 26),
                    'signalperiod': self.get_param("n_signal", 9)
                }
            )
            
            # RSI 指标
            indicators['rsi'] = self._indicator_service.calculate_indicator(
                'RSI', data, {'period': self.get_param("rsi_window", 14)}
            )
            
            # KDJ 指标
            indicators['kdj'] = self._indicator_service.calculate_indicator(
                'KDJ', data, {'n': self.get_param("kdj_n", 9)}
            )
            
            # 布林带指标
            indicators['boll'] = self._indicator_service.calculate_indicator(
                'BOLL', data, {'timeperiod': self.get_param("boll_n", 20)}
            )
            
            # ATR 指标
            indicators['atr'] = self._indicator_service.calculate_indicator(
                'ATR', data, {'timeperiod': self.get_param("atr_n", 14)}
            )
            
            return indicators
            
        except Exception as e:
            logger.error(f"技术指标计算失败: {str(e)}")
            return {}

    def _generate_signals(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame], symbol: str) -> List[Signal]:
        """生成交易信号"""
        signals = []
        
        try:
            n = len(data)
            if n < max(self.get_param("n_slow", 26), self.get_param("rsi_window", 14)):
                logger.warning(f"数据长度不足，无法生成信号: {n}")
                return signals
            
            for i in range(1, n):
                timestamp = data.index[i]
                current_price = data['close'].iloc[i]
                
                # 评估买入信号
                buy_signal = self._check_buy_signal(data, indicators, i)
                if buy_signal:
                    signals.append(Signal(
                        symbol=symbol,
                        timestamp=timestamp,
                        signal_type='buy',
                        price=current_price,
                        strength=buy_signal.get('strength', 0.5),
                        confidence=buy_signal.get('confidence', 0.5),
                        metadata=buy_signal.get('metadata', {}),
                        reason=buy_signal.get('reason', '')
                    ))
                
                # 评估卖出信号
                sell_signal = self._check_sell_signal(data, indicators, i)
                if sell_signal:
                    signals.append(Signal(
                        symbol=symbol,
                        timestamp=timestamp,
                        signal_type='sell',
                        price=current_price,
                        strength=sell_signal.get('strength', 0.5),
                        confidence=sell_signal.get('confidence', 0.5),
                        metadata=sell_signal.get('metadata', {}),
                        reason=sell_signal.get('reason', '')
                    ))
                    
        except Exception as e:
            logger.error(f"信号生成失败: {str(e)}")
            
        return signals

    def _check_buy_signal(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame], i: int) -> Optional[Dict[str, Any]]:
        """检查买入信号条件 - 默认返回空，子类可重写"""
        return None

    def _check_sell_signal(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame], i: int) -> Optional[Dict[str, Any]]:
        """检查卖出信号条件 - 默认返回空，子类可重写"""
        return None

    def _record_signals(self, signals: List[Signal]):
        """记录信号到内部存储"""
        for signal in signals:
            if signal.signal_type == 'buy':
                self._buy_signals.append(signal)
            elif signal.signal_type == 'sell':
                self._sell_signals.append(signal)

    # 参数管理方法
    def set_param(self, name: str, value: Any):
        """设置参数"""
        self._params[name] = value

    def get_param(self, name: str, default: Any = None) -> Any:
        """获取参数"""
        return self._params.get(name, default)

    def get_params(self) -> Dict[str, Any]:
        """获取所有参数"""
        return self._params.copy()

    # 信号访问方法
    def get_buy_signals(self) -> List[Signal]:
        """获取所有买入信号"""
        return self._buy_signals.copy()

    def get_sell_signals(self) -> List[Signal]:
        """获取所有卖出信号"""
        return self._sell_signals.copy()

    def get_all_signals(self) -> List[Signal]:
        """获取所有信号"""
        return self._buy_signals + self._sell_signals

    # 兼容性方法 - 为了向下兼容
    def add_buy_signal(self, datetime):
        """添加买入信号 - 兼容性方法"""
        logger.warning("add_buy_signal方法已废弃，请使用新的信号系统")

    def add_sell_signal(self, datetime):
        """添加卖出信号 - 兼容性方法"""
        logger.warning("add_sell_signal方法已废弃，请使用新的信号系统")

    def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """计算技术指标 - 完全脱离hikyuu依赖"""
        try:
            # 使用增强指标服务计算指标
            indicators = {}
            
            # MA 指标
            indicators['ma_fast'] = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("n_fast", 12)}
            )
            indicators['ma_slow'] = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("n_slow", 26)}
            )
            
            # MACD 指标
            indicators['macd'] = self._indicator_service.calculate_indicator(
                'MACD', data, {
                    'fastperiod': self.get_param("n_fast", 12),
                    'slowperiod': self.get_param("n_slow", 26),
                    'signalperiod': self.get_param("n_signal", 9)
                }
            )
            
            # RSI 指标
            indicators['rsi'] = self._indicator_service.calculate_indicator(
                'RSI', data, {'period': self.get_param("rsi_window", 14)}
            )
            
            # KDJ 指标
            indicators['kdj'] = self._indicator_service.calculate_indicator(
                'KDJ', data, {'n': self.get_param("kdj_n", 9)}
            )
            
            return indicators
            
        except Exception as e:
            logger.error(f"技术指标计算失败: {str(e)}")
            return {}

    def _check_buy_signal(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame], i: int) -> Optional[Dict[str, Any]]:
        """检查买入信号条件 - 默认返回空，子类可重写"""
        return None

    def _check_sell_signal(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame], i: int) -> Optional[Dict[str, Any]]:
        """检查卖出信号条件 - 默认返回空，子类可重写"""
        return None
