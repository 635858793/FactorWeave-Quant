"""
BettaFish技术分析Agent
专门处理股票技术指标和图表分析
"""

import asyncio
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from scipy.signal import argrelextrema

from core.services.base_service import BaseService
from core.indicator_service import calculate_indicator

class TechnicalSignal(Enum):
    """技术信号"""
    STRONG_BUY = "strong_buy"      # 强烈买入
    BUY = "buy"                    # 买入
    HOLD = "hold"                  # 持有
    SELL = "sell"                  # 卖出
    STRONG_SELL = "strong_sell"    # 强烈卖出

class TrendDirection(Enum):
    """趋势方向"""
    STRONG_UPTREND = "strong_uptrend"  # 强势上升
    UPTREND = "uptrend"                # 上升
    SIDEWAYS = "sideways"              # 横盘
    DOWNTREND = "downtrend"            # 下降
    STRONG_DOWNTREND = "strong_downtrend"  # 强势下降

@dataclass
class TechnicalIndicator:
    """技术指标"""
    name: str
    value: float
    signal: TechnicalSignal
    confidence: float
    description: str

@dataclass
class ChartPattern:
    """图表形态"""
    pattern_type: str
    pattern_name: str
    signal: TechnicalSignal
    confidence: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None

@dataclass
class TechnicalAnalysisResult:
    """技术分析结果"""
    stock_code: str
    analysis_time: datetime
    current_price: float
    trend_direction: TrendDirection
    overall_signal: TechnicalSignal
    indicators: List[TechnicalIndicator]
    patterns: List[ChartPattern]
    support_resistance_levels: Dict[str, float]
    volume_analysis: Dict[str, Any]
    recommendations: List[str]
    confidence: float

class TechnicalAnalysisAgent(BaseService):
    """技术分析Agent"""
    
    def __init__(self, event_bus: Optional[Any] = None):
        super().__init__(event_bus)
        
        # 分析配置
        self.config = {
            "ma_periods": [5, 10, 20, 60],
            "rsi_period": 14,
            "macd_params": {"fast": 12, "slow": 26, "signal": 9},
            "bollinger_period": 20,
            "volume_ma_period": 20,
            "min_data_points": 100
        }
        
        # 缓存
        self._technical_cache = {}
        self._cache_ttl = 900  # 15分钟

        # 数据状态
        self.has_real_data = False
        
        # 性能统计
        self._stats = {
            "total_analyses": 0,
            "cache_hits": 0,
            "avg_processing_time": 0.0,
            "indicators_calculated": 0
        }

    async def analyze_stock(self, stock_code: str, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析指定股票的技术指标"""
        start_time = time.time()
        context = context or {}
        
        try:
            logger.debug(f"开始技术分析: {stock_code}")
            
            # 检查缓存
            cache_key = f"technical_analysis_{stock_code}_{int(time.time() // self._cache_ttl)}"
            if cache_key in self._technical_cache:
                self._stats["cache_hits"] += 1
                logger.debug(f"技术分析缓存命中: {stock_code}")
                return self._technical_cache[cache_key]
            
            # 获取价格数据
            price_data = await self._get_price_data(stock_code, context)
            
            if price_data is None or len(price_data) < self.config["min_data_points"]:
                logger.warning(f"{stock_code}价格数据不足，无法进行技术分析")
                return {
                    "status": "insufficient_data",
                    "message": "价格数据不足，无法进行技术分析",
                    "stock_code": stock_code
                }
            
            # 计算技术指标
            indicators = await self._calculate_indicators(price_data)
            
            # 识别图表形态
            patterns = await self._identify_patterns(price_data)
            
            # 分析趋势
            trend_analysis = await self._analyze_trend(price_data, indicators)
            
            # 分析支撑阻力位
            support_resistance = await self._find_support_resistance(price_data)
            
            # 成交量分析
            volume_analysis = await self._analyze_volume(price_data)
            
            # 生成综合建议
            recommendations = self._generate_recommendations(indicators, patterns, trend_analysis)
            
            # 构建分析结果
            analysis_result = TechnicalAnalysisResult(
                stock_code=stock_code,
                analysis_time=datetime.now(),
                current_price=price_data['close'].iloc[-1],
                trend_direction=trend_analysis["direction"],
                overall_signal=trend_analysis["signal"],
                indicators=indicators,
                patterns=patterns,
                support_resistance_levels=support_resistance,
                volume_analysis=volume_analysis,
                recommendations=recommendations,
                confidence=min(0.9, self._calculate_confidence(indicators, patterns))
            )
            
            # 缓存结果
            self._technical_cache[cache_key] = {
                "status": "success",
                "analysis_result": analysis_result,
                "raw_data_summary": {
                    "data_points": len(price_data),
                    "date_range": {
                        "start": price_data.index[0].strftime("%Y-%m-%d"),
                        "end": price_data.index[-1].strftime("%Y-%m-%d")
                    }
                }
            }
            
            self._stats["total_analyses"] += 1
            self._stats["indicators_calculated"] += len(indicators)
            
            processing_time = time.time() - start_time
            self._update_processing_stats(processing_time)
            
            logger.info(f"技术分析完成: {stock_code}, 耗时: {processing_time:.2f}s")
            
            return self._technical_cache[cache_key]
            
        except Exception as e:
            logger.error(f"技术分析失败: {stock_code}, 错误: {str(e)}")
            return {
                "status": "error",
                "message": f"技术分析失败: {str(e)}",
                "stock_code": stock_code
            }

    async def _get_price_data(self, stock_code: str, 
                            context: Dict[str, Any] = None) -> Optional[pd.DataFrame]:
        """获取价格数据 - 仅从真实数据源获取"""
        try:
            df = await self._fetch_real_price_data(stock_code)
            if df is not None and not df.empty and len(df) >= self.config["min_data_points"]:
                self.has_real_data = True
                logger.info(f"成功从真实数据源获取{stock_code}价格数据: {len(df)}条")
                return df
            self.has_real_data = False
            logger.warning(f"真实数据源无{stock_code}数据或数据不足(需要>={self.config['min_data_points']}条)，跳过技术分析")
            return None
        except Exception as e:
            self.has_real_data = False
            logger.warning(f"获取价格数据失败({stock_code}): {str(e)}")
            return None

    async def _fetch_real_price_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """从真实数据源获取K线价格数据"""
        df = None
        try:
            from core.services.unified_data_manager import get_unified_data_manager
            data_manager = get_unified_data_manager()
            if data_manager:
                df = data_manager.get_kdata(stock_code, period='D', count=self.config["min_data_points"] + 50)
                if df is not None and not df.empty:
                    expected_cols = {'open', 'high', 'low', 'close', 'volume'}
                    if expected_cols.issubset(set(col.lower() for col in df.columns)):
                        rename_map = {col: col.lower() for col in df.columns}
                        df = df.rename(columns=rename_map)
                    return df
        except ImportError:
            logger.debug("UnifiedDataManager 不可用，尝试 StockService")
        except Exception as e:
            logger.debug(f"UnifiedDataManager 获取数据失败: {e}")

        try:
            from core.services.stock_service import StockService
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container:
                stock_service = container.resolve(StockService)
            else:
                stock_service = None
            if stock_service and hasattr(stock_service, 'get_kdata'):
                df = stock_service.get_kdata(stock_code, period='D', count=self.config["min_data_points"] + 50)
                if df is not None and not df.empty:
                    expected_cols = {'open', 'high', 'low', 'close', 'volume'}
                    if expected_cols.issubset(set(col.lower() for col in df.columns)):
                        rename_map = {col: col.lower() for col in df.columns}
                        df = df.rename(columns=rename_map)
                    return df
        except ImportError:
            logger.debug("StockService 不可用")
        except Exception as e:
            logger.debug(f"StockService 获取数据失败: {e}")

        return df

    async def _calculate_indicators(self, price_data: pd.DataFrame) -> List[TechnicalIndicator]:
        """计算技术指标"""
        indicators = []
        
        try:
            close = price_data['close']
            high = price_data['high']
            low = price_data['low']
            volume = price_data['volume']
            
            # 移动平均线
            ma_indicators = self._calculate_moving_averages(close)
            indicators.extend(ma_indicators)
            
            # RSI
            rsi_indicator = self._calculate_rsi(close)
            if rsi_indicator:
                indicators.append(rsi_indicator)
            
            # MACD
            macd_indicator = self._calculate_macd(close)
            if macd_indicator:
                indicators.append(macd_indicator)
            
            # 布林带
            bollinger_indicators = self._calculate_bollinger_bands(close)
            indicators.extend(bollinger_indicators)
            
            # KDJ
            kdj_indicators = self._calculate_kdj(high, low, close)
            indicators.extend(kdj_indicators)
            
            # 成交量指标
            volume_indicators = self._calculate_volume_indicators(volume)
            indicators.extend(volume_indicators)
            
            logger.debug(f"计算了{len(indicators)}个技术指标")
            return indicators
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {str(e)}")
            return []

    def _calculate_moving_averages(self, close: pd.Series) -> List[TechnicalIndicator]:
        """计算移动平均线 - 使用统一指标服务"""
        indicators = []
        
        for period in self.config["ma_periods"]:
            try:
                price_data = pd.DataFrame({'close': close})
                result = calculate_indicator('MA', price_data, timeperiod=period)
                
                if isinstance(result, pd.DataFrame) and 'MA' in result.columns:
                    current_ma = result['MA'].iloc[-1]
                elif isinstance(result, pd.Series):
                    current_ma = result.iloc[-1]
                else:
                    ma = close.rolling(window=period).mean()
                    current_ma = ma.iloc[-1]
            except Exception as e:
                logger.warning(f"统一服务计算MA{period}失败，使用本地计算: {e}")
                ma = close.rolling(window=period).mean()
                current_ma = ma.iloc[-1]
            
            if pd.isna(current_ma):
                continue
            
            current_price = close.iloc[-1]
            
            if current_price > current_ma * 1.02:
                signal = TechnicalSignal.BUY
                confidence = 0.7
            elif current_price > current_ma:
                signal = TechnicalSignal.HOLD
                confidence = 0.6
            elif current_price < current_ma * 0.98:
                signal = TechnicalSignal.SELL
                confidence = 0.7
            else:
                signal = TechnicalSignal.HOLD
                confidence = 0.5
            
            indicator = TechnicalIndicator(
                name=f"MA{period}",
                value=current_ma,
                signal=signal,
                confidence=confidence,
                description=f"{period}日移动平均线，当前价格{'高于' if current_price > current_ma else '低于'}均线"
            )
            indicators.append(indicator)
        
        return indicators

    def _calculate_rsi(self, close: pd.Series) -> Optional[TechnicalIndicator]:
        """计算RSI - 使用统一指标服务"""
        try:
            period = self.config["rsi_period"]
            
            try:
                price_data = pd.DataFrame({'close': close})
                result = calculate_indicator('RSI', price_data, timeperiod=period)
                
                if isinstance(result, pd.DataFrame) and 'RSI' in result.columns:
                    current_rsi = result['RSI'].iloc[-1]
                elif isinstance(result, pd.Series):
                    current_rsi = result.iloc[-1]
                else:
                    delta = close.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    current_rsi = rsi.iloc[-1]
            except Exception as e:
                logger.warning(f"统一服务计算RSI失败，使用本地计算: {e}")
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]
            
            if pd.isna(current_rsi):
                return None
            
            if current_rsi > 70:
                signal = TechnicalSignal.SELL
                confidence = 0.8
                description = "RSI超买，可能回调"
            elif current_rsi < 30:
                signal = TechnicalSignal.BUY
                confidence = 0.8
                description = "RSI超卖，可能反弹"
            elif current_rsi > 50:
                signal = TechnicalSignal.HOLD
                confidence = 0.6
                description = "RSI偏强，趋势向好"
            else:
                signal = TechnicalSignal.HOLD
                confidence = 0.6
                description = "RSI偏弱，趋势偏弱"
            
            return TechnicalIndicator(
                name="RSI",
                value=current_rsi,
                signal=signal,
                confidence=confidence,
                description=description
            )
            
        except Exception as e:
            logger.error(f"计算RSI失败: {str(e)}")
            return None

    def _calculate_macd(self, close: pd.Series) -> Optional[TechnicalIndicator]:
        """计算MACD - 使用统一指标服务"""
        try:
            fast = self.config["macd_params"]["fast"]
            slow = self.config["macd_params"]["slow"]
            signal_period = self.config["macd_params"]["signal"]
            
            try:
                price_data = pd.DataFrame({'close': close})
                result = calculate_indicator('MACD', price_data, 
                                           fastperiod=fast, 
                                           slowperiod=slow, 
                                           signalperiod=signal_period)
                
                if isinstance(result, pd.DataFrame):
                    if 'MACD' in result.columns:
                        macd_line = result['MACD']
                        current_macd = macd_line.iloc[-1]
                    else:
                        current_macd = None
                    
                    if 'MACDSignal' in result.columns:
                        signal_line = result['MACDSignal']
                        current_signal = signal_line.iloc[-1]
                    else:
                        current_signal = None
                    
                    if 'MACDHist' in result.columns:
                        histogram = result['MACDHist']
                        current_histogram = histogram.iloc[-1]
                    else:
                        current_histogram = None
                    
                    if current_macd is None or current_signal is None or current_histogram is None:
                        raise ValueError("MACD计算结果不完整")
                else:
                    raise ValueError("MACD计算结果格式不正确")
            except Exception as e:
                logger.warning(f"统一服务计算MACD失败，使用本地计算: {e}")
                ema_fast = close.ewm(span=fast).mean()
                ema_slow = close.ewm(span=slow).mean()
                macd_line = ema_fast - ema_slow
                signal_line = macd_line.ewm(span=signal_period).mean()
                histogram = macd_line - signal_line
                
                current_macd = macd_line.iloc[-1]
                current_signal = signal_line.iloc[-1]
                current_histogram = histogram.iloc[-1]
            
            if pd.isna(current_histogram):
                return None
            
            if current_macd > current_signal and current_histogram > 0:
                signal = TechnicalSignal.BUY
                confidence = 0.7
                description = "MACD金叉，买入信号"
            elif current_macd < current_signal and current_histogram < 0:
                signal = TechnicalSignal.SELL
                confidence = 0.7
                description = "MACD死叉，卖出信号"
            else:
                signal = TechnicalSignal.HOLD
                confidence = 0.5
                description = "MACD信号不明确"
            
            return TechnicalIndicator(
                name="MACD",
                value=current_histogram,
                signal=signal,
                confidence=confidence,
                description=description
            )
            
        except Exception as e:
            logger.error(f"计算MACD失败: {str(e)}")
            return None

    def _calculate_bollinger_bands(self, close: pd.Series) -> List[TechnicalIndicator]:
        """计算布林带 - 使用统一指标服务"""
        indicators = []
        
        try:
            period = self.config["bollinger_period"]
            
            try:
                price_data = pd.DataFrame({'close': close})
                result = calculate_indicator('BBANDS', price_data, 
                                           timeperiod=period,
                                           nbdevup=2,
                                           nbdevdn=2)
                
                if isinstance(result, pd.DataFrame):
                    if 'BBUpper' in result.columns:
                        current_upper = result['BBUpper'].iloc[-1]
                    else:
                        current_upper = None
                    
                    if 'BBMiddle' in result.columns:
                        current_middle = result['BBMiddle'].iloc[-1]
                    else:
                        current_middle = None
                    
                    if 'BBLower' in result.columns:
                        current_lower = result['BBLower'].iloc[-1]
                    else:
                        current_lower = None
                    
                    if current_upper is None or current_middle is None or current_lower is None:
                        raise ValueError("布林带计算结果不完整")
                else:
                    raise ValueError("布林带计算结果格式不正确")
            except Exception as e:
                logger.warning(f"统一服务计算布林带失败，使用本地计算: {e}")
                std_dev = close.rolling(window=period).std()
                middle_band = close.rolling(window=period).mean()
                upper_band = middle_band + (std_dev * 2)
                lower_band = middle_band - (std_dev * 2)
                
                current_upper = upper_band.iloc[-1]
                current_lower = lower_band.iloc[-1]
                current_middle = middle_band.iloc[-1]
            
            current_price = close.iloc[-1]
            
            if pd.isna(current_upper) or pd.isna(current_lower):
                return []
            
            if current_price > current_upper:
                signal = TechnicalSignal.BUY
                confidence = 0.7
                description = "价格突破布林带上轨，可能继续上涨"
            elif current_price < current_lower:
                signal = TechnicalSignal.BUY
                confidence = 0.7
                description = "价格触及布林带下轨，可能获得支撑"
            else:
                signal = TechnicalSignal.HOLD
                confidence = 0.5
                description = "价格在布林带区间内震荡"
            
            upper_indicator = TechnicalIndicator(
                name="BB_Upper",
                value=current_upper,
                signal=signal,
                confidence=confidence,
                description=f"布林带上轨: {description}"
            )
            indicators.append(upper_indicator)
            
            lower_indicator = TechnicalIndicator(
                name="BB_Lower",
                value=current_lower,
                signal=signal,
                confidence=confidence,
                description=f"布林带下轨: {description}"
            )
            indicators.append(lower_indicator)
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算布林带失败: {str(e)}")
            return []

    def _calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series) -> List[TechnicalIndicator]:
        """计算KDJ"""
        indicators = []
        
        try:
            period = 9
            k_period = 3
            d_period = 3
            
            # 计算RSV
            lowest_low = low.rolling(window=period).min()
            highest_high = high.rolling(window=period).max()
            rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
            
            # 计算K值
            k = rsv.ewm(alpha=1/k_period).mean()
            
            # 计算D值
            d = k.ewm(alpha=1/d_period).mean()
            
            # 计算J值
            j = 3 * k - 2 * d
            
            current_k = k.iloc[-1]
            current_d = d.iloc[-1]
            current_j = j.iloc[-1]
            
            # 判断信号
            if current_k < 20 and current_d < 20:
                signal = TechnicalSignal.BUY
                confidence = 0.8
                description = "KDJ超卖区域，可能反弹"
            elif current_k > 80 and current_d > 80:
                signal = TechnicalSignal.SELL
                confidence = 0.8
                description = "KDJ超买区域，可能回调"
            elif current_k > current_d:
                signal = TechnicalSignal.HOLD
                confidence = 0.6
                description = "K线在D线上方，偏强"
            else:
                signal = TechnicalSignal.HOLD
                confidence = 0.6
                description = "K线在D线下方，偏弱"
            
            # K指标
            k_indicator = TechnicalIndicator(
                name="K",
                value=current_k,
                signal=signal,
                confidence=confidence,
                description=f"K值({current_k:.2f}): {description}"
            )
            indicators.append(k_indicator)
            
            # D指标
            d_indicator = TechnicalIndicator(
                name="D",
                value=current_d,
                signal=signal,
                confidence=confidence,
                description=f"D值({current_d:.2f}): {description}"
            )
            indicators.append(d_indicator)
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算KDJ失败: {str(e)}")
            return []

    def _calculate_volume_indicators(self, volume: pd.Series) -> List[TechnicalIndicator]:
        """计算成交量指标"""
        indicators = []
        
        try:
            # 成交量移动平均
            volume_ma = volume.rolling(window=self.config["volume_ma_period"]).mean()
            current_volume = volume.iloc[-1]
            avg_volume = volume_ma.iloc[-1]
            
            # 成交量比率
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio > 1.5:
                signal = TechnicalSignal.BUY
                confidence = 0.7
                description = f"成交量放大至平均的{volume_ratio:.2f}倍"
            elif volume_ratio < 0.5:
                signal = TechnicalSignal.SELL
                confidence = 0.6
                description = f"成交量萎缩至平均的{volume_ratio:.2f}倍"
            else:
                signal = TechnicalSignal.HOLD
                confidence = 0.5
                description = f"成交量正常，为平均的{volume_ratio:.2f}倍"
            
            indicator = TechnicalIndicator(
                name="Volume",
                value=volume_ratio,
                signal=signal,
                confidence=confidence,
                description=description
            )
            indicators.append(indicator)
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算成交量指标失败: {str(e)}")
            return []

    async def _identify_patterns(self, price_data: pd.DataFrame) -> List[ChartPattern]:
        """识别图表形态"""
        patterns = []
        
        try:
            # 简单形态识别
            close = price_data['close']
            
            # 双重底/顶识别
            double_pattern = self._identify_double_pattern(close)
            if double_pattern:
                patterns.append(double_pattern)
            
            # 三角形整理识别
            triangle_pattern = self._identify_triangle_pattern(price_data)
            if triangle_pattern:
                patterns.append(triangle_pattern)
            
            logger.debug(f"识别出{len(patterns)}个图表形态")
            return patterns
            
        except Exception as e:
            logger.error(f"识别图表形态失败: {str(e)}")
            return []

    def _identify_double_pattern(self, close: pd.Series) -> Optional[ChartPattern]:
        """识别双重底/顶"""
        try:
            # 简化的双重底识别
            recent_data = close.tail(20)
            close_array = recent_data.values

            peak_indices = argrelextrema(close_array, np.greater_equal, order=1)[0]
            trough_indices = argrelextrema(close_array, np.less_equal, order=1)[0]
            peaks = [(int(idx), close_array[idx]) for idx in peak_indices]
            troughs = [(int(idx), close_array[idx]) for idx in trough_indices]
            
            # 双重底
            if len(troughs) >= 2:
                trough1_pos, trough1_price = troughs[-2]
                trough2_pos, trough2_price = troughs[-1]
                
                if abs(trough1_price - trough2_price) / trough1_price < 0.03:  # 3%内
                    return ChartPattern(
                        pattern_type="double_bottom",
                        pattern_name="双重底",
                        signal=TechnicalSignal.BUY,
                        confidence=0.7,
                        target_price=trough1_price * 1.1,
                        stop_loss=min(trough1_price, trough2_price) * 0.95
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"识别双重形态失败: {str(e)}")
            return None

    def _identify_triangle_pattern(self, price_data: pd.DataFrame) -> Optional[ChartPattern]:
        """识别三角形整理"""
        try:
            close = price_data['close'].tail(30)
            high = price_data['high'].tail(30)
            low = price_data['low'].tail(30)
            
            # 简化的三角形识别逻辑
            # 检查趋势线收敛
            high_slope = (high.iloc[-1] - high.iloc[0]) / len(high)
            low_slope = (low.iloc[-1] - low.iloc[0]) / len(low)
            
            if abs(high_slope) < 0.01 and abs(low_slope) < 0.01:  # 趋势线相对平缓
                return ChartPattern(
                    pattern_type="triangle",
                    pattern_name="三角形整理",
                    signal=TechnicalSignal.HOLD,
                    confidence=0.6
                )
            
            return None
            
        except Exception as e:
            logger.error(f"识别三角形形态失败: {str(e)}")
            return None

    async def _analyze_trend(self, price_data: pd.DataFrame, 
                           indicators: List[TechnicalIndicator]) -> Dict[str, Any]:
        """分析趋势"""
        try:
            close = price_data['close']
            current_price = close.iloc[-1]
            
            # 计算移动平均线趋势
            ma_20 = close.rolling(window=20).mean().iloc[-1]
            ma_60 = close.rolling(window=60).mean().iloc[-1]
            
            # 基础趋势判断
            if current_price > ma_20 > ma_60:
                if current_price > ma_20 * 1.02:
                    direction = TrendDirection.STRONG_UPTREND
                    signal = TechnicalSignal.STRONG_BUY
                else:
                    direction = TrendDirection.UPTREND
                    signal = TechnicalSignal.BUY
            elif current_price < ma_20 < ma_60:
                if current_price < ma_20 * 0.98:
                    direction = TrendDirection.STRONG_DOWNTREND
                    signal = TechnicalSignal.STRONG_SELL
                else:
                    direction = TrendDirection.DOWNTREND
                    signal = TechnicalSignal.SELL
            else:
                direction = TrendDirection.SIDEWAYS
                signal = TechnicalSignal.HOLD
            
            # 结合其他指标调整信号
            buy_signals = sum(1 for ind in indicators if ind.signal in [TechnicalSignal.BUY, TechnicalSignal.STRONG_BUY])
            sell_signals = sum(1 for ind in indicators if ind.signal in [TechnicalSignal.SELL, TechnicalSignal.STRONG_SELL])
            
            if buy_signals > sell_signals + 2:
                if signal == TechnicalSignal.HOLD:
                    signal = TechnicalSignal.BUY
            elif sell_signals > buy_signals + 2:
                if signal == TechnicalSignal.HOLD:
                    signal = TechnicalSignal.SELL
            
            return {
                "direction": direction,
                "signal": signal,
                "strength": abs(buy_signals - sell_signals) / max(1, len(indicators))
            }
            
        except Exception as e:
            logger.error(f"分析趋势失败: {str(e)}")
            return {
                "direction": TrendDirection.SIDEWAYS,
                "signal": TechnicalSignal.HOLD,
                "strength": 0.0
            }

    async def _find_support_resistance(self, price_data: pd.DataFrame) -> Dict[str, float]:
        """寻找支撑阻力位"""
        try:
            close = price_data['close']
            high = price_data['high']
            low = price_data['low']
            
            current_price = close.iloc[-1]
            
            # 寻找近期高点和低点
            recent_highs = high.tail(50)
            recent_lows = low.tail(50)

            # 阻力位：局部最大值 (order=5)
            resistance_indices = argrelextrema(recent_highs.values, np.greater, order=5)[0]
            resistance_levels = recent_highs.values[resistance_indices].tolist()

            # 支撑位：局部最小值 (order=5)
            support_indices = argrelextrema(recent_lows.values, np.less, order=5)[0]
            support_levels = recent_lows.values[support_indices].tolist()
            
            # 选择最重要的支撑阻力位
            key_resistance = min([r for r in resistance_levels if r > current_price], 
                               default=current_price * 1.1)
            key_support = max([s for s in support_levels if s < current_price], 
                            default=current_price * 0.9)
            
            return {
                "key_resistance": key_resistance,
                "key_support": key_support,
                "resistance_levels": sorted(resistance_levels, reverse=True)[:3],
                "support_levels": sorted(support_levels)[:3]
            }
            
        except Exception as e:
            logger.error(f"寻找支撑阻力位失败: {str(e)}")
            return {
                "key_resistance": current_price * 1.1,
                "key_support": current_price * 0.9,
                "resistance_levels": [],
                "support_levels": []
            }

    async def _analyze_volume(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """分析成交量"""
        try:
            volume = price_data['volume']
            close = price_data['close']
            
            # 成交量趋势
            volume_ma = volume.rolling(window=20).mean()
            current_volume = volume.iloc[-1]
            avg_volume = volume_ma.iloc[-1]
            
            # 量价关系
            price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]
            volume_change = (current_volume - volume.iloc[-2]) / volume.iloc[-2]
            
            # 量价配合分析
            if price_change > 0 and volume_change > 0:
                volume_price_relation = "量价齐升"
            elif price_change < 0 and volume_change < 0:
                volume_price_relation = "量价齐跌"
            elif price_change > 0 and volume_change < 0:
                volume_price_relation = "价升量缩"
            elif price_change < 0 and volume_change > 0:
                volume_price_relation = "价跌量增"
            else:
                volume_price_relation = "量价背离"
            
            return {
                "current_volume": current_volume,
                "avg_volume": avg_volume,
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 1,
                "volume_trend": "增加" if current_volume > avg_volume else "减少",
                "volume_price_relation": volume_price_relation,
                "volume_intensity": "高" if current_volume > avg_volume * 1.5 else "正常"
            }
            
        except Exception as e:
            logger.error(f"分析成交量失败: {str(e)}")
            return {}

    def _generate_recommendations(self, indicators: List[TechnicalIndicator], 
                                patterns: List[ChartPattern],
                                trend_analysis: Dict[str, Any]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        try:
            # 基于总体信号的建议
            overall_signal = trend_analysis["signal"]
            trend_direction = trend_analysis["direction"]
            
            if overall_signal in [TechnicalSignal.STRONG_BUY, TechnicalSignal.BUY]:
                recommendations.append("技术面偏多，可考虑买入或加仓")
                recommendations.append("注意设置止损，控制风险")
            elif overall_signal in [TechnicalSignal.STRONG_SELL, TechnicalSignal.SELL]:
                recommendations.append("技术面偏空，建议减仓或观望")
                recommendations.append("关注支撑位，避免盲目抄底")
            else:
                recommendations.append("技术面信号不明确，建议等待更明确信号")
                recommendations.append("可考虑做T或波段操作")
            
            # 基于图表形态的建议
            for pattern in patterns:
                if pattern.signal == TechnicalSignal.BUY:
                    recommendations.append(f"检测到{pattern.pattern_name}形态，谨慎乐观")
                    if pattern.target_price:
                        recommendations.append(f"目标价位：{pattern.target_price:.2f}")
                    if pattern.stop_loss:
                        recommendations.append(f"止损位：{pattern.stop_loss:.2f}")
                elif pattern.signal == TechnicalSignal.SELL:
                    recommendations.append(f"检测到{pattern.pattern_name}形态，注意风险")
            
            # 基于关键指标的建议
            rsi_indicators = [ind for ind in indicators if ind.name == "RSI"]
            if rsi_indicators:
                rsi = rsi_indicators[0]
                if rsi.value > 70:
                    recommendations.append("RSI超买，短期可能回调")
                elif rsi.value < 30:
                    recommendations.append("RSI超卖，短期可能反弹")
            
            # 基于趋势的建议
            if trend_direction == TrendDirection.STRONG_UPTREND:
                recommendations.append("上升趋势明确，可顺势操作")
            elif trend_direction == TrendDirection.STRONG_DOWNTREND:
                recommendations.append("下降趋势明确，宜减仓观望")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成建议失败: {str(e)}")
            return ["技术分析建议生成失败，请谨慎操作"]

    def _calculate_confidence(self, indicators: List[TechnicalIndicator], 
                            patterns: List[ChartPattern]) -> float:
        """计算置信度"""
        try:
            if not indicators:
                return 0.5
            
            # 基于指标置信度
            indicator_confidence = np.mean([ind.confidence for ind in indicators])
            
            # 基于形态置信度
            pattern_confidence = sum(pattern.confidence for pattern in patterns) / max(1, len(patterns))
            
            # 综合置信度
            overall_confidence = indicator_confidence * 0.7 + pattern_confidence * 0.3
            
            return min(0.9, overall_confidence)
            
        except Exception as e:
            logger.error(f"计算置信度失败: {str(e)}")
            return 0.5

    def _update_processing_stats(self, processing_time: float):
        """更新处理统计"""
        current_avg = self._stats["avg_processing_time"]
        total_analyses = self._stats["total_analyses"]
        
        # 移动平均
        self._stats["avg_processing_time"] = (current_avg * (total_analyses - 1) + processing_time) / total_analyses

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "total_analyses": self._stats["total_analyses"],
            "cache_hits": self._stats["cache_hits"],
            "cache_hit_rate": self._stats["cache_hits"] / max(1, self._stats["total_analyses"]),
            "avg_processing_time": self._stats["avg_processing_time"],
            "indicators_calculated": self._stats["indicators_calculated"],
            "cache_size": len(self._technical_cache)
        }

    async def cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self._technical_cache.items()
            if isinstance(value, dict) and "analysis_time" in value
            and isinstance(value["analysis_time"], datetime)
            and (current_time - value["analysis_time"].timestamp()) > self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._technical_cache[key]
        
        logger.debug(f"清理了{len(expired_keys)}个过期缓存项")
