"""
增强的交易信号系统 - 无 hikyuu 依赖

完全基于 pandas 和 TA-Lib 实现，支持多因子、机器学习、信号权重、
技术/基本面/量价等多维度因子的综合信号系统。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from .base import BaseSignal, Signal
from core.services.enhanced_indicator_service import EnhancedIndicatorService
from loguru import logger


@dataclass
class SignalStrength:
    """信号强度组件"""
    trend: float = 0.0
    momentum: float = 0.0
    volume: float = 0.0
    volatility: float = 0.0
    ml: float = 0.0
    total: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            'trend': self.trend,
            'momentum': self.momentum,
            'volume': self.volume,
            'volatility': self.volatility,
            'ml': self.ml,
            'total': self.total
        }


class EnhancedSignal(BaseSignal):
    """
    增强的交易信号系统 - 无 hikyuu 依赖
    
    支持多因子、机器学习、信号权重、技术/基本面/量价等多维度因子。
    完全基于 pandas 和 TA-Lib 实现，替代原有的 hikyuu SignalBase 继承。
    """

    def __init__(self, name: str = "EnhancedSignal", params: Optional[Dict[str, Any]] = None):
        super().__init__(name)
        
        # 默认参数
        default_params = {
            "n_fast": 12,              # 快速均线周期
            "n_slow": 26,              # 慢速均线周期
            "n_signal": 9,             # 信号线周期
            "rsi_window": 14,          # RSI计算窗口
            "rsi_buy_threshold": 30,   # RSI买入阈值
            "rsi_sell_threshold": 70,  # RSI卖出阈值
            "volume_ma": 20,           # 成交量均线周期
            "trend_strength": 0.02,    # 趋势强度阈值
            "signal_confirm_window": 3,  # 信号确认窗口
            "min_signal_strength": 2,   # 最小信号强度要求
            "kdj_n": 9,                # KDJ周期
            "boll_n": 20,              # 布林带周期
            "boll_width": 2,           # 布林带宽度
            "atr_period": 14,          # ATR周期
            "atr_multiplier": 2,       # ATR倍数
            "cci_period": 20,          # CCI周期
            "cci_threshold": 100,      # CCI阈值
            "obv_ma": 20,              # OBV均线周期
            "dmi_period": 14,          # DMI周期
            "dmi_threshold": 25,       # DMI阈值
            "volume_ratio": 1.5,       # 成交量比率阈值
            "volatility_threshold": 1.5,  # 波动率阈值
            "enable_ml": False,        # 是否启用机器学习
            "ml_model_path": None,     # 机器学习模型路径
            "ml_features": [],         # 机器学习特征列表
            "ml_threshold": 0.6,       # 机器学习信号阈值
            "signal_weights": {        # 信号权重
                "trend": 0.3,
                "momentum": 0.2,
                "volume": 0.15,
                "volatility": 0.15,
                "ml": 0.2
            }
        }
        
        # 更新参数
        if params is not None and isinstance(params, dict):
            default_params.update(params)
        
        for key, value in default_params.items():
            self.set_param(key, value)
        
        # 增强信号特有属性
        self.signal_history: List[Tuple[datetime, int]] = []  # 历史信号
        self.last_signal = 0      # 上一个信号
        self.market_regime = "neutral"  # 市场状态
        self.volatility = 0.0     # 市场波动率
        self._prev_macd_state = None  # MACD先前交叉状态: True=金叉, False=死叉, None=初始
        self._prev_ma_state = None    # MA先前交叉状态: True=金叉, False=死叉, None=初始
        self.ml_model = None
        try:
            from core.containers import get_service_container
            container = get_service_container()
            self._enhanced_indicator_service = container.resolve(EnhancedIndicatorService)
        except Exception:
            self._enhanced_indicator_service = EnhancedIndicatorService()
        
        # 加载机器学习模型
        if self.get_param("enable_ml") and self.get_param("ml_model_path"):
            self._load_ml_model()

    def _load_ml_model(self):
        """加载机器学习模型"""
        try:
            import joblib
            model_path = self.get_param("ml_model_path")
            if model_path:
                self.ml_model = joblib.load(model_path)
                logger.info(f"成功加载机器学习模型: {model_path}")
        except Exception as e:
            logger.warning(f"加载机器学习模型失败: {str(e)}")
            self.ml_model = None

    def _calculate_ml_signal(self, data: pd.DataFrame) -> float:
        """计算机器学习信号"""
        if not self.ml_model or not self.get_param("enable_ml"):
            return 0.0
        
        try:
            features = self._prepare_ml_features(data)
            if features is None or len(features) == 0:
                return 0.0
            
            # 获取最后一个时间点的预测
            latest_features = features[-1:] if len(features) > 1 else features
            prediction = self.ml_model.predict_proba(latest_features)[:, 1]
            
            return prediction[-1] if prediction[-1] > self.get_param("ml_threshold") else 0.0
            
        except Exception as e:
            logger.warning(f"机器学习信号计算错误: {str(e)}")
            return 0.0

    def _prepare_ml_features(self, data: pd.DataFrame) -> Optional[np.ndarray]:
        """准备机器学习特征"""
        try:
            features = []
            ml_features = self.get_param("ml_features", [])
            
            if not ml_features:
                # 默认特征
                ml_features = ["close", "volume", "rsi"]
            
            for feature_name in ml_features:
                if feature_name == "close":
                    features.append(data['close'].values)
                elif feature_name == "volume" and 'volume' in data.columns:
                    features.append(data['volume'].values)
                elif feature_name == "rsi":
                    rsi = self._enhanced_indicator_service.calculate_indicator(
                        'RSI', data, {'period': self.get_param("rsi_window")}
                    )
                    if rsi is not None and not rsi.empty:
                        features.append(rsi.values)
                # 可扩展更多特征
            
            if not features:
                return None
                
            # 确保所有特征长度一致
            min_length = min(len(f) for f in features)
            features = [f[:min_length] for f in features]
            
            return np.column_stack(features)
            
        except Exception as e:
            logger.warning(f"准备机器学习特征失败: {str(e)}")
            return None

    def clone(self) -> 'EnhancedSignal':
        """克隆增强信号实例"""
        cloned = EnhancedSignal(name=self.name)
        cloned._params = self._params.copy()
        cloned._cache = self._cache.copy()
        cloned.signal_history = self.signal_history.copy()
        cloned.last_signal = self.last_signal
        cloned.market_regime = self.market_regime
        cloned.volatility = self.volatility
        cloned._prev_macd_state = self._prev_macd_state
        cloned._prev_ma_state = self._prev_ma_state
        cloned.ml_model = self.ml_model
        return cloned

    def _calculate(self, data: pd.DataFrame, record) -> float:
        """基于pandas数据的计算逻辑"""
        try:
            if data.empty:
                return 0.0
                
            # 计算技术指标
            indicators = self._calculate_indicators(data)
            
            # 基础信号计算
            base_signal = self._calculate_base_signals(data, indicators)
            
            # 机器学习信号
            ml_signal = self._calculate_ml_signal(data)
            
            # 综合信号
            signal_strength = self._calculate_final_signal(base_signal, ml_signal)
            
            # 更新市场状态
            self.market_regime = self._detect_market_regime(data, indicators)
            self.volatility = self._calculate_volatility_pandas(data)
            
            # 更新历史记录和最后信号
            if hasattr(data.index, 'tolist') and len(data) > 0:
                timestamp = data.index[-1]
            else:
                timestamp = datetime.now()
                
            if signal_strength >= self.get_param("min_signal_strength", 2):
                if self.last_signal <= 0:
                    if hasattr(record, 'add_buy_signal'):
                        record.add_buy_signal(timestamp)
                    self.last_signal = 1
                    self.signal_history.append((timestamp, 1))
            elif signal_strength <= -self.get_param("min_signal_strength", 2):
                if self.last_signal >= 0:
                    if hasattr(record, 'add_sell_signal'):
                        record.add_sell_signal(timestamp)
                    self.last_signal = -1
                    self.signal_history.append((timestamp, -1))
                    
            # 保持历史记录长度
            if len(self.signal_history) > self.get_param("signal_confirm_window", 3):
                self.signal_history.pop(0)
                
            return signal_strength
            
        except Exception as e:
            logger.warning(f"EnhancedSignal计算错误: {str(e)}")
            return 0.0
            
    def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, float]:
        """计算技术指标"""
        indicators = {}
        
        try:
            # 移动平均线
            n_fast = self.get_param("n_fast", 12)
            n_slow = self.get_param("n_slow", 26)
            
            ma_fast = data['close'].rolling(window=n_fast).mean()
            ma_slow = data['close'].rolling(window=n_slow).mean()
            
            indicators['ma_fast'] = ma_fast.iloc[-1] if not pd.isna(ma_fast.iloc[-1]) else 0.0
            indicators['ma_slow'] = ma_slow.iloc[-1] if not pd.isna(ma_slow.iloc[-1]) else 0.0
            
            # MACD
            ema_fast = data['close'].ewm(span=n_fast).mean()
            ema_slow = data['close'].ewm(span=n_slow).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=self.get_param("n_signal", 9)).mean()
            
            indicators['macd'] = macd_line.iloc[-1] if not pd.isna(macd_line.iloc[-1]) else 0.0
            indicators['macd_signal'] = signal_line.iloc[-1] if not pd.isna(signal_line.iloc[-1]) else 0.0
            
            # RSI
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            indicators['rsi'] = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
            
            # 成交量均线
            if 'volume' in data.columns:
                volume_ma = data['volume'].rolling(window=self.get_param("volume_ma", 20)).mean()
                indicators['volume_ma'] = volume_ma.iloc[-1] if not pd.isna(volume_ma.iloc[-1]) else 0.0
            
            return indicators
            
        except Exception as e:
            logger.warning(f"计算技术指标错误: {str(e)}")
            return {}
    
    def _calculate_base_signals(self, data: pd.DataFrame, indicators: Dict[str, float]) -> float:
        """计算基础信号"""
        signal = 0.0
        
        try:
            # 趋势信号 - 仅金叉/死叉时刻触发
            curr_ma_state = indicators.get('ma_fast', 0) > indicators.get('ma_slow', 0)
            if self._prev_ma_state is not None:
                if curr_ma_state and not self._prev_ma_state:
                    signal += 0.3
                elif not curr_ma_state and self._prev_ma_state:
                    signal -= 0.3
            self._prev_ma_state = curr_ma_state
                
            # MACD信号 - 仅金叉/死叉时刻触发
            curr_macd_state = indicators.get('macd', 0) > indicators.get('macd_signal', 0)
            if self._prev_macd_state is not None:
                if curr_macd_state and not self._prev_macd_state:
                    signal += 0.3
                elif not curr_macd_state and self._prev_macd_state:
                    signal -= 0.3
            self._prev_macd_state = curr_macd_state
                
            # RSI信号
            rsi = indicators.get('rsi', 50)
            if rsi < self.get_param("rsi_buy_threshold", 30):
                signal += 0.2
            elif rsi > self.get_param("rsi_sell_threshold", 70):
                signal -= 0.2
                
            return signal
            
        except Exception as e:
            logger.warning(f"计算基础信号错误: {str(e)}")
            return 0.0

    def _calculate_base_signals_batch(self, data: pd.DataFrame) -> np.ndarray:
        """批量计算所有bar的基础信号（numpy向量化实现，替代逐bar状态跟踪）

        使用np.roll检测MA金叉/死叉和MACD金叉/死叉，
        与RSI信号综合后返回每个bar的信号强度数组。

        Args:
            data: 完整的K线DataFrame

        Returns:
            信号强度数组，正值为买入偏多，负值为卖出偏多
        """
        try:
            n = len(data)
            signals = np.zeros(n, dtype=np.float64)

            n_fast = self.get_param("n_fast", 12)
            n_slow = self.get_param("n_slow", 26)
            n_signal = self.get_param("n_signal", 9)

            close = data['close'].values

            # MA趋势信号 - 批量金叉/死叉检测
            ma_fast = pd.Series(close).rolling(window=n_fast).mean().values
            ma_slow = pd.Series(close).rolling(window=n_slow).mean().values

            ma_bull = ma_fast > ma_slow
            prev_ma_bull = np.roll(ma_bull, 1)
            prev_ma_bull[0] = ma_bull[0]

            ma_golden = ma_bull & (~prev_ma_bull)
            ma_death = (~ma_bull) & prev_ma_bull

            signals[ma_golden] += 0.3
            signals[ma_death] -= 0.3

            # MACD信号 - 批量金叉/死叉检测
            ema_fast = pd.Series(close).ewm(span=n_fast).mean().values
            ema_slow = pd.Series(close).ewm(span=n_slow).mean().values
            macd_line = ema_fast - ema_slow
            signal_line = pd.Series(macd_line).ewm(span=n_signal).mean().values

            macd_bull = macd_line > signal_line
            prev_macd_bull = np.roll(macd_bull, 1)
            prev_macd_bull[0] = macd_bull[0]

            macd_golden = macd_bull & (~prev_macd_bull)
            macd_death = (~macd_bull) & prev_macd_bull

            signals[macd_golden] += 0.3
            signals[macd_death] -= 0.3

            # RSI信号
            delta = np.diff(close, prepend=close[0])
            gain = np.maximum(delta, 0)
            loss = np.abs(np.minimum(delta, 0))
            rsi_window = self.get_param("rsi_window", 14)

            avg_gain = pd.Series(gain).rolling(window=rsi_window).mean().values
            avg_loss = pd.Series(loss).rolling(window=rsi_window).mean().values
            rs = np.divide(avg_gain, avg_loss, out=np.ones_like(avg_gain), where=avg_loss != 0)
            rsi = 100.0 - (100.0 / (1.0 + rs))

            rsi_buy_threshold = self.get_param("rsi_buy_threshold", 30)
            rsi_sell_threshold = self.get_param("rsi_sell_threshold", 70)

            signals[rsi < rsi_buy_threshold] += 0.2
            signals[rsi > rsi_sell_threshold] -= 0.2

            return signals

        except Exception as e:
            logger.warning(f"批量基础信号计算错误: {str(e)}")
            return np.zeros(len(data), dtype=np.float64)
    
    def _calculate_final_signal(self, base_signal: float, ml_signal: float) -> float:
        """计算最终信号"""
        weights = self.get_param("signal_weights", {
            "trend": 0.3, "momentum": 0.2, "volume": 0.15, "volatility": 0.15, "ml": 0.2
        })
        
        # 综合信号计算
        final_signal = base_signal * (1 - weights.get('ml', 0.2)) + ml_signal * weights.get('ml', 0.2)
        
        # 根据市场状态调整
        if self.market_regime == "bullish":
            final_signal *= 1.2
        elif self.market_regime == "bearish":
            final_signal *= 0.8
            
        return final_signal
        
    def _calculate_volatility_pandas(self, data: pd.DataFrame) -> float:
        """计算市场波动率"""
        try:
            returns = data['close'].pct_change().dropna()
            if len(returns) >= self.get_param("atr_period", 14):
                volatility = returns.rolling(window=self.get_param("atr_period", 14)).std().iloc[-1]
                return volatility if not pd.isna(volatility) else 0.0
            return 0.0
        except Exception as e:
            logger.warning(f"波动率计算错误: {str(e)}")
            return 0.0

    def _detect_market_regime(self, data: pd.DataFrame, indicators: Dict[str, float]) -> str:
        """检测市场状态"""
        try:
            trend_strength = self.get_param("trend_strength", 0.02)
            current_price = data['close'].iloc[-1]
            ma_slow_value = indicators.get('ma_slow', 0)
            
            if ma_slow_value != 0:
                relative_strength = (current_price - ma_slow_value) / ma_slow_value
                if relative_strength > trend_strength:
                    return "bullish"
                elif relative_strength < -trend_strength:
                    return "bearish"
            return "neutral"
        except Exception as e:
            logger.warning(f"市场状态检测错误: {str(e)}")
            return "neutral"

    def _calculate_volatility(self, data: pd.DataFrame, atr_values: Optional[np.ndarray] = None) -> float:
        """计算市场波动率"""
        try:
            if atr_values is not None and len(atr_values) > 0:
                current_atr = atr_values[-1]
                current_price = data['close'].iloc[-1]
                if current_price != 0:
                    return current_atr / current_price
            
            # 使用pandas直接计算波动率
            returns = data['close'].pct_change().dropna()
            if len(returns) >= 14:
                volatility = returns.rolling(window=14).std().iloc[-1]
                return volatility if not pd.isna(volatility) else 0.01
            return 0.01
        except Exception as e:
            logger.warning(f"波动率计算错误: {str(e)}")
            return 0.01

    def calculate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """主计算接口"""
        try:
            if data.empty:
                return {"signal": 0.0, "info": {"error": "Empty data"}}

            signal_value = self._calculate(data)

            signal_info = self.get_signal_info()
            signal_info.update({
                "current_signal": signal_value,
                "timestamp": data.index[-1] if hasattr(data.index, 'tolist') else datetime.now(),
                "data_points": len(data)
            })

            return {
                "signal": signal_value,
                "info": signal_info
            }

        except Exception as e:
            logger.warning(f"EnhancedSignal计算信号错误: {str(e)}")
            return {"signal": 0.0, "info": {"error": str(e)}}

    def calculate_signals_batch(self, data: pd.DataFrame) -> np.ndarray:
        """批量计算所有bar的交易信号（numpy向量化，单次遍历）

        一次性对完整历史数据计算所有bar的MA/MACD/RSI信号，
        使用np.roll向量化检测交叉点，避免逐bar状态跟踪的开销。
        适用于回测场景或需要完整信号序列的场景。

        Args:
            data: 完整的K线DataFrame

        Returns:
            信号强度数组 (n,) float64，正=买入偏多，负=卖出偏多
        """
        try:
            if data.empty:
                return np.array([], dtype=np.float64)

            base_signals = self._calculate_base_signals_batch(data)

            ml_signals = np.zeros(len(data), dtype=np.float64)
            if self.get_param("enable_ml") and self.ml_model:
                ml_signal_value = self._calculate_ml_signal(data)
                ml_signals[-1] = ml_signal_value

            weights = self.get_param("signal_weights", {
                "trend": 0.3, "momentum": 0.2, "volume": 0.15, "volatility": 0.15, "ml": 0.2
            })
            ml_weight = weights.get('ml', 0.2)
            final_signals = base_signals * (1 - ml_weight) + ml_signals * ml_weight

            return final_signals

        except Exception as e:
            logger.warning(f"批量信号计算错误: {str(e)}")
            return np.zeros(len(data), dtype=np.float64)

    def update_params(self, **params):
        """更新参数"""
        for key, value in params.items():
            self._params[key] = value
            
        # 重新加载模型如果需要
        if "ml_model_path" in params or "enable_ml" in params:
            self._load_ml_model()
            
        logger.info(f"EnhancedSignal参数已更新: {list(params.keys())}")
