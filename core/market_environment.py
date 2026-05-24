import numpy as np
import pandas as pd

from core.indicator_service import calculate_indicator, get_indicator_metadata, get_all_indicators_metadata
from loguru import logger

class MarketEnvironment:
    """
    市场环境判断模块
    完全脱离 hikyuu 依赖，实现市场环境分析
    """

    def __init__(self, params=None):
        # 设置默认参数
        self.params = {
            "ma_short": 5,           # 短期均线周期
            "ma_mid": 20,            # 中期均线周期
            "ma_long": 60,           # 长期均线周期
            "volatility_window": 20,  # 波动率计算窗口
            "trend_window": 50,      # 趋势计算窗口
            "volume_ma": 20,         # 成交量均线周期
            "rsi_period": 14,        # RSI周期
            "macd_fast": 12,         # MACD快线周期
            "macd_slow": 26,         # MACD慢线周期
            "macd_signal": 9,        # MACD信号线周期
            "boll_period": 20,       # 布林带周期
            "boll_width": 2,         # 布林带宽度
            "atr_period": 14,        # ATR周期
            "cci_period": 14,        # CCI周期
            "volatility_threshold": 0.02,  # 波动率阈值
            "trend_threshold": 0.02,       # 趋势强度阈值
            "volume_threshold": 1.5        # 成交量阈值
        }
        
        # 更新用户提供的参数
        if params:
            self.params.update(params)

        # 初始化市场状态
        self.market_state = {
            'trend': 'neutral',      # 趋势状态：up/down/neutral
            'volatility': 'normal',  # 波动率状态：high/normal/low
            'volume': 'normal',      # 成交量状态：high/normal/low
            'strength': 0.0,         # 趋势强度
            'regime': 'normal'       # 市场状态：bull/bear/neutral
        }
        
    def set_param(self, name, value):
        """设置参数"""
        self.params[name] = value
        
    def get_param(self, name, default=None):
        """获取参数"""
        return self.params.get(name, default)

    def analyze(self, data):
        """分析市场环境
        
        Args:
            data: pandas DataFrame 包含 OHLCV 数据
            
        Returns:
            bool: 是否适合交易
        """
        try:
            # 1. 计算技术指标
            indicators = self._calculate_indicators(data)

            if not indicators:
                logger.warning("指标计算失败，返回默认状态")
                return True

            # 2. 分析市场状态
            self._analyze_trend(indicators)
            self._analyze_volatility(indicators)
            self._analyze_volume(indicators)
            self._analyze_market_regime(indicators)

            # 3. 综合判断市场环境
            return self._judge_market_environment()

        except Exception as e:
            logger.error(f"市场环境分析错误: {str(e)}")
            return True

    def _calculate_indicators(self, data):
        """计算技术指标
        
        Args:
            data: pandas DataFrame 包含 OHLCV 数据
        """
        try:
            if not isinstance(data, pd.DataFrame) or 'close' not in data.columns:
                logger.error("数据格式不正确，需要包含 OHLCV 字段的 DataFrame")
                return {}
                
            # 计算移动平均线
            ma_short = calculate_indicator('MA', data, {'timeperiod': self.get_param("ma_short")})
            ma_mid = calculate_indicator('MA', data, {'timeperiod': self.get_param("ma_mid")})
            ma_long = calculate_indicator('MA', data, {'timeperiod': self.get_param("ma_long")})
            
            # 计算 MACD
            macd = calculate_indicator('MACD', data, {
                'fast': self.get_param("macd_fast"),
                'slow': self.get_param("macd_slow"), 
                'signal': self.get_param("macd_signal")
            })
            
            # 计算 RSI
            rsi = calculate_indicator('RSI', data, {'timeperiod': self.get_param("rsi_period")})
            
            # 计算布林带
            boll = calculate_indicator('BOLL', data, {
                'timeperiod': self.get_param("boll_period"), 
                'width': self.get_param("boll_width")
            })
            
            # 计算 ATR
            atr = calculate_indicator('ATR', data, {'timeperiod': self.get_param("atr_period", 14)})
            
            # 计算 OBV
            obv = calculate_indicator('OBV', data, {})
            
            # 计算 CCI
            cci = calculate_indicator('CCI', data, {'timeperiod': self.get_param("cci_period", 14)})
            
            # 计算成交量移动平均线
            volume_ma = calculate_indicator('MA', data[['volume']], {'timeperiod': self.get_param("volume_ma")})
            
            # 计算波动率 (基于收盘价变化率)
            returns = data['close'].pct_change().rolling(window=self.get_param("volatility_window", 20)).std()
            volatility = returns * np.sqrt(252)  # 年化波动率
            
            return {
                'ma_short': ma_short,
                'ma_mid': ma_mid,
                'ma_long': ma_long,
                'macd': macd,
                'rsi': rsi,
                'boll': boll,
                'atr': atr,
                'volatility': volatility,
                'volume_ma': volume_ma,
                'close': data['close'],
                'volume': data['volume'],
                'obv': obv,
                'cci': cci
            }
        except Exception as e:
            logger.error(f"技术指标计算错误: {str(e)}")
            return {}

    def _analyze_trend(self, indicators):
        """分析趋势"""
        try:
            # 1. 计算趋势强度
            ma_short = indicators['ma_short']
            ma_mid = indicators['ma_mid']
            ma_long = indicators['ma_long']

            # 确保数据有效性
            if len(ma_short) < 5 or len(ma_mid) < 5 or len(ma_long) < 5:
                logger.warning("数据长度不足，使用默认趋势")
                self.market_state['trend'] = 'neutral'
                self.market_state['strength'] = 0.0
                return

            # 短期趋势 (使用最后几个有效数据点)
            recent_short = ma_short.dropna().tail(5)
            recent_mid = ma_mid.dropna().tail(5)
            recent_long = ma_long.dropna().tail(5)
            
            if len(recent_short) >= 2 and len(recent_mid) >= 2 and len(recent_long) >= 2:
                # 短期趋势
                short_trend = (recent_short.iloc[-1] - recent_short.iloc[0]) / recent_short.iloc[0]
                # 中期趋势
                mid_trend = (recent_mid.iloc[-1] - recent_mid.iloc[0]) / recent_mid.iloc[0]
                # 长期趋势
                long_trend = (recent_long.iloc[-1] - recent_long.iloc[0]) / recent_long.iloc[0]

                # 综合趋势强度
                trend_strength = (short_trend + mid_trend + long_trend) / 3

                # 判断趋势方向
                threshold = self.get_param("trend_threshold")
                if trend_strength > threshold:
                    self.market_state['trend'] = 'up'
                elif trend_strength < -threshold:
                    self.market_state['trend'] = 'down'
                else:
                    self.market_state['trend'] = 'neutral'

                self.market_state['strength'] = abs(trend_strength)
            else:
                logger.warning("有效数据不足，设置默认趋势")
                self.market_state['trend'] = 'neutral'
                self.market_state['strength'] = 0.0

        except Exception as e:
            logger.error(f"趋势分析错误: {str(e)}")
            self.market_state['trend'] = 'neutral'
            self.market_state['strength'] = 0.0

    def _analyze_volatility(self, indicators):
        """分析波动率"""
        try:
            volatility = indicators['volatility']
            
            # 获取最新的有效波动率值
            volatility_clean = volatility.dropna()
            if len(volatility_clean) == 0:
                logger.warning("波动率数据为空，使用默认值")
                self.market_state['volatility'] = 'normal'
                return
                
            current_volatility = volatility_clean.iloc[-1]

            threshold = self.get_param("volatility_threshold")
            if current_volatility > threshold * 1.5:
                self.market_state['volatility'] = 'high'
            elif current_volatility < threshold * 0.5:
                self.market_state['volatility'] = 'low'
            else:
                self.market_state['volatility'] = 'normal'

        except Exception as e:
            logger.error(f"波动率分析错误: {str(e)}")
            self.market_state['volatility'] = 'normal'

    def _analyze_volume(self, indicators):
        """分析成交量"""
        try:
            volume = indicators['volume']
            volume_ma = indicators['volume_ma']
            
            # 获取最新的有效数据
            volume_clean = volume.dropna()
            volume_ma_clean = volume_ma.dropna()
            
            if len(volume_clean) == 0 or len(volume_ma_clean) == 0:
                logger.warning("成交量数据为空，使用默认值")
                self.market_state['volume'] = 'normal'
                return
                
            current_volume = volume_clean.iloc[-1]
            current_volume_ma = volume_ma_clean.iloc[-1]
            
            if current_volume_ma == 0:
                logger.warning("成交量均值为零，使用默认值")
                self.market_state['volume'] = 'normal'
                return
                
            volume_ratio = current_volume / current_volume_ma

            threshold = self.get_param("volume_threshold")
            if volume_ratio > threshold:
                self.market_state['volume'] = 'high'
            elif volume_ratio < 1/threshold:
                self.market_state['volume'] = 'low'
            else:
                self.market_state['volume'] = 'normal'

        except Exception as e:
            logger.error(f"成交量分析错误: {str(e)}")
            self.market_state['volume'] = 'normal'

    def _analyze_market_regime(self, indicators):
        """分析市场状态"""
        try:
            # 1. 获取各项指标
            rsi_series = indicators['rsi']
            macd_series = indicators['macd']
            boll_series = indicators['boll']
            close_series = indicators['close']

            # 获取最新的有效数据
            rsi_clean = rsi_series.dropna()
            macd_clean = macd_series.dropna() if hasattr(macd_series, 'dropna') else macd_series
            boll_clean = boll_series.dropna() if hasattr(boll_series, 'dropna') else boll_series
            close_clean = close_series.dropna()

            if (len(rsi_clean) == 0 or len(macd_clean) == 0 or 
                len(boll_clean) == 0 or len(close_clean) == 0):
                logger.warning("市场状态指标数据不足，使用默认值")
                self.market_state['regime'] = 'neutral'
                return

            current_rsi = rsi_clean.iloc[-1]
            current_close = close_clean.iloc[-1]

            # 2. 计算市场状态得分 (Z-Score标准化加权评分)
            score = 0.0

            # RSI得分: Z-Score标准化 (历史均值~50, 标准差~15)
            # 正值=看涨倾向, 负值=看跌倾向
            rsi_mean = rsi_clean.mean() if len(rsi_clean) > 0 else 50.0
            rsi_std = rsi_clean.std() if len(rsi_clean) > 0 else 15.0
            if rsi_std > 0:
                rsi_z = (current_rsi - rsi_mean) / rsi_std
            else:
                rsi_z = 0.0
            score += rsi_z * 1.0

            # MACD得分: diff值相较于历史波动标准化
            if hasattr(macd_clean, 'diff'):
                macd_diff = macd_clean['diff'].iloc[-1]
                macd_hist_std = macd_clean['diff'].std() if len(macd_clean) > 0 else 0.01
                if macd_hist_std > 0:
                    macd_z = macd_diff / macd_hist_std
                else:
                    macd_z = 0.0
                score += macd_z * 1.2
            elif isinstance(macd_clean, pd.Series):
                macd_val = macd_clean.iloc[-1]
                macd_hist_std = macd_clean.std() if len(macd_clean) > 0 else 0.01
                if macd_hist_std > 0:
                    macd_z = macd_val / macd_hist_std
                else:
                    macd_z = 0.0
                score += macd_z * 1.2

            # 布林带得分: 价格在带宽中的位置
            if hasattr(boll_clean, 'upper') and hasattr(boll_clean, 'lower'):
                upper = boll_clean['upper'].iloc[-1]
                lower = boll_clean['lower'].iloc[-1]
                mid = (upper + lower) / 2
                if upper != lower:
                    bb_position = (current_close - mid) / (upper - lower) * 2
                    score += -bb_position * 0.8
            elif isinstance(boll_clean, pd.Series):
                bb_std = boll_clean.std()
                if bb_std > 0:
                    bb_z = (current_close - boll_clean.mean()) / bb_std
                    score += -bb_z * 0.8

            # 3. 判断市场状态
            if score >= 1.5:
                self.market_state['regime'] = 'bull'
            elif score <= -1.5:
                self.market_state['regime'] = 'bear'
            else:
                self.market_state['regime'] = 'neutral'

        except Exception as e:
            logger.error(f"市场状态分析错误: {str(e)}")
            self.market_state['regime'] = 'neutral'

    def _judge_market_environment(self):
        """综合判断市场环境"""
        try:
            # 1. 获取市场状态
            trend = self.market_state['trend']
            volatility = self.market_state['volatility']
            volume = self.market_state['volume']
            regime = self.market_state['regime']

            # 2. 判断是否适合交易
            if regime == 'bull' and trend == 'up' and volatility == 'normal' and volume == 'normal':
                return True  # 适合做多
            elif regime == 'bear' and trend == 'down' and volatility == 'normal' and volume == 'normal':
                return True  # 适合做空
            elif regime == 'neutral' and volatility == 'low' and volume == 'normal':
                return True  # 适合震荡交易
            else:
                return False  # 不适合交易

        except Exception as e:
            logger.info(f"市场环境判断错误: {str(e)}")
            return True

    def get_market_state(self):
        """获取当前市场状态"""
        return self.market_state

    def is_bull_market(self):
        """判断是否为牛市"""
        return self.market_state['regime'] == 'bull'

    def is_bear_market(self):
        """判断是否为熊市"""
        return self.market_state['regime'] == 'bear'

    def is_high_volatility(self):
        """判断是否为高波动率"""
        return self.market_state['volatility'] == 'high'

    def is_high_volume(self):
        """判断是否为高成交量"""
        return self.market_state['volume'] == 'high'

    def get_trend_strength(self):
        """获取趋势强度"""
        return self.market_state['strength']
