import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from core.services.enhanced_indicator_service import EnhancedIndicatorService
from core.utils.data_standardizer import DataStandardizer
from loguru import logger

class SystemCondition(ABC):
    """
    系统条件基类 - 完全脱离hikyuu依赖
    
    替代原有的hikyuu ConditionBase，提供基于pandas的系统条件判断功能。
    """

    def __init__(self, name: str = "SystemCondition"):
        self.name = name
        self._params = {}
        try:
            from core.containers import get_service_container
            container = get_service_container()
            self._indicator_service = container.resolve(EnhancedIndicatorService)
        except Exception:
            self._indicator_service = EnhancedIndicatorService()
        self._data_standardizer = DataStandardizer()
        
        # 状态属性
        self.market_regime = "neutral"  # 市场状态
        self.volatility = 0.0          # 市场波动率
        self.trend_strength = 0.0      # 趋势强度
        self.volume_ratio = 0.0        # 成交量比率
        
        # 设置默认参数
        self._set_default_params()

    def _set_default_params(self):
        """设置默认参数"""
        self._params.update({
            "ma_period": 20,           # 均线周期
            "volume_ma_period": 20,    # 成交量均线周期
            "volatility_period": 20,   # 波动率计算周期
            "trend_period": 50,        # 趋势判断周期
            "volume_ratio": 1.5,       # 成交量比率阈值
            "trend_threshold": 0.02,   # 趋势强度阈值
            "volatility_threshold": 0.02,  # 波动率阈值
            "min_price": 5.0,          # 最小价格限制
            "max_price": 500.0,        # 最大价格限制
            "min_volume": 1000000,     # 最小成交量限制
            "enable_ml": False,        # 是否启用机器学习
            "ml_model_path": None      # 机器学习模型路径
        })

    @abstractmethod
    def evaluate(self, data: pd.DataFrame, symbol: str = "") -> bool:
        """
        评估系统条件是否满足
        
        Args:
            data: 标准OHLCV数据
            symbol: 交易标的代码
            
        Returns:
            bool: 条件是否满足
        """
        pass

    def reset(self):
        """重置状态"""
        self.market_regime = "neutral"
        self.volatility = 0.0
        self.trend_strength = 0.0
        self.volume_ratio = 0.0

    def clone(self) -> 'SystemCondition':
        """克隆实例"""
        cloned = self.__class__(name=self.name)
        cloned._params = self._params.copy()
        return cloned

    def set_param(self, name: str, value: Any):
        """设置参数"""
        self._params[name] = value

    def get_param(self, name: str, default: Any = None) -> Any:
        """获取参数"""
        return self._params.get(name, default)


class EnhancedSystemCondition(SystemCondition):
    """
    增强的系统有效条件判断
    
    提供完整的市场状态评估和条件判断功能。
    """

    def __init__(self, params=None):
        super().__init__("EnhancedSystemCondition")
        
        if params:
            self._params.update(params)

    def evaluate(self, data: pd.DataFrame, symbol: str = "") -> bool:
        """
        评估系统条件是否满足
        """
        try:
            # 数据验证
            if data is None or len(data) == 0:
                logger.warning(f"系统条件评估收到空数据 - {symbol}")
                return False
            
            # 重置状态
            self.reset()
            
            # 1. 基础数据检查
            if not self._check_basic_conditions(data):
                return False

            # 2. 计算技术指标
            indicators = self._calculate_indicators(data)

            # 3. 判断市场状态
            self.market_regime = self._detect_market_regime(data, indicators)

            # 4. 计算波动率
            self.volatility = self._calculate_volatility(data)

            # 5. 计算趋势强度
            self.trend_strength = self._calculate_trend_strength(data)

            # 6. 计算成交量比率
            self.volume_ratio = self._calculate_volume_ratio(data)

            # 7. 综合判断
            return self._make_decision(data, indicators)

        except Exception as e:
            logger.error(f"系统条件评估错误: {str(e)}")
            return False

    def _check_basic_conditions(self, data: pd.DataFrame) -> bool:
        """检查基础条件"""
        try:
            # 检查数据长度
            if len(data) < self.get_param("ma_period"):
                return False

            # 检查价格范围
            current_price = data['close'].iloc[-1]
            if current_price < self.get_param("min_price") or current_price > self.get_param("max_price"):
                return False

            # 检查成交量
            current_volume = data['volume'].iloc[-1]
            if current_volume < self.get_param("min_volume"):
                return False

            return True

        except Exception as e:
            logger.error(f"基础条件检查错误: {str(e)}")
            return False

    def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """计算技术指标"""
        try:
            indicators = {}
            
            # 计算主要技术指标
            indicators['ma'] = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("ma_period")}
            )
            
            indicators['macd'] = self._indicator_service.calculate_indicator(
                'MACD', data, {
                    'fastperiod': 12,
                    'slowperiod': 26,
                    'signalperiod': 9
                }
            )
            
            indicators['rsi'] = self._indicator_service.calculate_indicator(
                'RSI', data, {'period': 14}
            )
            
            return indicators
            
        except Exception as e:
            logger.error(f"指标计算错误: {str(e)}")
            return {}

    def _detect_market_regime(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame]) -> str:
        """检测市场状态"""
        try:
            # 获取价格和均线
            close = data['close']
            ma = indicators.get('ma')
            
            if ma is None or len(ma) == 0:
                return "neutral"

            # 计算趋势
            trend = (close.iloc[-1] - ma.iloc[-1]) / ma.iloc[-1]

            # 判断市场状态
            if trend > self.get_param("trend_threshold"):
                return "bullish"
            elif trend < -self.get_param("trend_threshold"):
                return "bearish"
            else:
                return "neutral"

        except Exception as e:
            logger.error(f"市场状态检测错误: {str(e)}")
            return "neutral"

    def _calculate_volatility(self, data: pd.DataFrame) -> float:
        """计算波动率"""
        try:
            returns = data['close'].pct_change()
            volatility = returns.rolling(
                window=self.get_param("volatility_period")).std()
            return volatility.iloc[-1] if not volatility.empty else 0.0
        except Exception as e:
            logger.error(f"波动率计算错误: {str(e)}")
            return 0.0

    def _calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """计算趋势强度"""
        try:
            ma_short = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("ma_period")}
            )
            ma_long = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("trend_period")}
            )

            if ma_short.empty or ma_long.empty:
                return 0.0
                
            trend = (ma_short.iloc[-1] - ma_long.iloc[-1]) / ma_long.iloc[-1]
            return trend

        except Exception as e:
            logger.error(f"趋势强度计算错误: {str(e)}")
            return 0.0

    def _calculate_volume_ratio(self, data: pd.DataFrame) -> float:
        """计算成交量比率"""
        try:
            volume = data['volume']
            volume_ma = self._indicator_service.calculate_indicator(
                'MA', data, {'period': self.get_param("volume_ma_period")}
            )
            
            if volume_ma.empty or volume_ma.iloc[-1] == 0:
                return 0.0
                
            return volume.iloc[-1] / volume_ma.iloc[-1]
        except Exception as e:
            logger.error(f"成交量比率计算错误: {str(e)}")
            return 0.0

    def _make_decision(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame]) -> bool:
        """综合判断系统是否有效"""
        try:
            # 1. 检查市场状态
            if self.market_regime == "bearish" and self.trend_strength < -self.get_param("trend_threshold"):
                return False

            # 2. 检查波动率
            if self.volatility > self.get_param("volatility_threshold"):
                return False

            # 3. 检查成交量
            if self.volume_ratio < self.get_param("volume_ratio"):
                return False

            # 4. 检查技术指标
            macd = indicators.get('macd')
            rsi = indicators.get('rsi')

            if macd is not None and not macd.empty:
                # MACD在零轴下方
                if len(macd) >= 2:
                    diff_col = macd.columns[1] if len(macd.columns) > 1 else macd.columns[0]
                    dea_col = macd.columns[2] if len(macd.columns) > 2 else macd.columns[0]
                    
                    if macd.iloc[-1][diff_col] < 0 and macd.iloc[-1][dea_col] < 0:
                        return False

            if rsi is not None and not rsi.empty:
                # RSI超买
                if rsi.iloc[-1, 0] > 70:
                    return False

            # 5. 如果启用机器学习，使用模型预测
            if self.get_param("enable_ml") and self.get_param("ml_model_path"):
                if not self._ml_predict(data, indicators):
                    return False

            return True

        except Exception as e:
            logger.error(f"综合判断错误: {str(e)}")
            return False

    def _ml_predict(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame]) -> bool:
        """使用机器学习模型预测"""
        try:
            # 准备特征数据
            features = self._prepare_ml_features(data, indicators)

            if features is None:
                return False

            # 加载模型并预测
            import joblib
            model = joblib.load(self.get_param("ml_model_path"))
            prediction = model.predict(features)

            return prediction[0] > 0.5

        except Exception as e:
            logger.error(f"机器学习预测错误: {str(e)}")
            return False

    def _prepare_ml_features(self, data: pd.DataFrame, indicators: Dict[str, pd.DataFrame]) -> Optional[np.ndarray]:
        """准备机器学习特征"""
        try:
            features = []

            # 添加价格特征
            features.append(data['close'].iloc[-1])
            features.append(data['close'].iloc[-1] / data['close'].iloc[-2] - 1)  # 收益率

            # 添加技术指标特征
            ma = indicators.get('ma')
            if ma is not None and not ma.empty:
                features.append(ma.iloc[-1, 0])
                features.append(data['close'].iloc[-1] / ma.iloc[-1, 0] - 1)  # 价格偏离度
            else:
                features.append(0.0)
                features.append(0.0)

            macd = indicators.get('macd')
            if macd is not None and not macd.empty:
                if len(macd.columns) > 1:
                    features.append(macd.iloc[-1, 1])  # diff
                    features.append(macd.iloc[-1, 2])  # dea
                else:
                    features.extend([0.0, 0.0])
            else:
                features.extend([0.0, 0.0])

            rsi = indicators.get('rsi')
            if rsi is not None and not rsi.empty:
                features.append(rsi.iloc[-1, 0])
            else:
                features.append(0.0)

            # 添加成交量特征
            features.append(data['volume'].iloc[-1])
            features.append(self.volume_ratio)

            # 添加波动率特征
            features.append(self.volatility)

            # 添加趋势特征
            features.append(self.trend_strength)

            return np.array(features).reshape(1, -1)

        except Exception as e:
            logger.error(f"特征准备错误: {str(e)}")
            return None

def get_indicator_categories():
    """获取所有指标分类及其指标列表，确保与ta-lib分类一致"""
    # 已替换为新的导入
    return get_all_indicators_by_category()
