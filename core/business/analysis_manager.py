from loguru import logger

"""
分析管理业务逻辑

负责技术分析和基本面分析相关的业务逻辑处理，包括：
- 技术指标计算
- 趋势分析
- 信号生成
- 分析报告
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np

from ..data.models import StockInfo, KlineData, QueryParams
from ..data.data_access import DataAccess
from core.indicator_service import calculate_indicator


@dataclass
class TechnicalSignal:

    signal_type: str  # 信号类型：'buy', 'sell', 'hold'
    strength: float  # 信号强度 0-1
    indicator: str  # 指标名称
    description: str  # 信号描述
    timestamp: datetime  # 信号时间
    price: Optional[float] = None  # 信号价格


@dataclass
class AnalysisResult:
    """分析结果"""
    stock_code: str
    stock_name: str
    analysis_type: str  # 分析类型：'technical', 'fundamental'
    signals: List[TechnicalSignal]
    summary: str  # 分析摘要
    recommendation: str  # 推荐操作：'strong_buy', 'buy', 'hold', 'sell', 'strong_sell'
    confidence: float  # 置信度 0-1
    target_price: Optional[float] = None  # 目标价格
    stop_loss: Optional[float] = None  # 止损价格
    analysis_time: datetime = None


class AnalysisManager:
    """分析管理器"""

    def __init__(self, data_access: DataAccess):
        self.data_access = data_access
        self._analysis_cache = {}  # 分析结果缓存
        self.logger = logger.bind(module=self.__class__.__name__)

    def _technical_analysis(self, stock_code: str, stock_info: StockInfo) -> Optional[AnalysisResult]:
        """技术分析"""
        try:
            # 获取K线数据
            params = QueryParams(
                stock_code=stock_code,
                period='day',
                start_date=datetime.now() - timedelta(days=250),  # 获取250天数据
                end_date=datetime.now()
            )

            kline_data = self.data_access.get_kline_data(params)
            if not kline_data or not kline_data.data:
                return None

            # 转换为DataFrame进行分析
            df = pd.DataFrame(kline_data.data)
            if df.empty:
                return None

            signals = []

            # 计算技术指标
            signals.extend(self._calculate_ma_signals(df, stock_code))
            signals.extend(self._calculate_rsi_signals(df, stock_code))
            signals.extend(self._calculate_macd_signals(df, stock_code))
            signals.extend(self._calculate_bollinger_signals(df, stock_code))

            # 生成综合推荐
            recommendation, confidence = self._generate_recommendation(signals)

            # 计算目标价和止损价
            current_price = df['close'].iloc[-1] if not df.empty else None
            target_price, stop_loss = self._calculate_price_targets(
                df, recommendation)

            # 生成分析摘要
            summary = self._generate_technical_summary(
                signals, recommendation, confidence)

            return AnalysisResult(
                stock_code=stock_code,
                stock_name=stock_info.name,
                analysis_type='technical',
                signals=signals,
                summary=summary,
                recommendation=recommendation,
                confidence=confidence,
                target_price=target_price,
                stop_loss=stop_loss
            )

        except Exception as e:
            self.logger.error(
                f"Technical analysis failed for {stock_code}: {e}")
            return None

    def _fundamental_analysis(self, stock_code: str, stock_info: StockInfo) -> Optional[AnalysisResult]:
        """基本面分析"""
        try:
            signals = []

            # PE估值分析
            if stock_info.pe_ratio:
                if stock_info.pe_ratio < 15:
                    signals.append(TechnicalSignal(
                        signal_type='buy',
                        strength=0.7,
                        indicator='PE_Ratio',
                        description=f'PE比率 {stock_info.pe_ratio:.2f} 相对较低，估值合理',
                        timestamp=datetime.now()
                    ))
                elif stock_info.pe_ratio > 30:
                    signals.append(TechnicalSignal(
                        signal_type='sell',
                        strength=0.6,
                        indicator='PE_Ratio',
                        description=f'PE比率 {stock_info.pe_ratio:.2f} 相对较高，估值偏贵',
                        timestamp=datetime.now()
                    ))

            # PB估值分析
            if stock_info.pb_ratio:
                if stock_info.pb_ratio < 1.5:
                    signals.append(TechnicalSignal(
                        signal_type='buy',
                        strength=0.6,
                        indicator='PB_Ratio',
                        description=f'PB比率 {stock_info.pb_ratio:.2f} 较低，账面价值支撑强',
                        timestamp=datetime.now()
                    ))
                elif stock_info.pb_ratio > 3:
                    signals.append(TechnicalSignal(
                        signal_type='sell',
                        strength=0.5,
                        indicator='PB_Ratio',
                        description=f'PB比率 {stock_info.pb_ratio:.2f} 较高，溢价明显',
                        timestamp=datetime.now()
                    ))

            # 行业分析
            if stock_info.industry:
                # 这里可以加入行业轮动分析
                signals.append(TechnicalSignal(
                    signal_type='hold',
                    strength=0.5,
                    indicator='Industry',
                    description=f'所属行业：{stock_info.industry}',
                    timestamp=datetime.now()
                ))

            # 生成推荐
            recommendation, confidence = self._generate_recommendation(signals)
            summary = self._generate_fundamental_summary(
                signals, stock_info, recommendation)

            return AnalysisResult(
                stock_code=stock_code,
                stock_name=stock_info.name,
                analysis_type='fundamental',
                signals=signals,
                summary=summary,
                recommendation=recommendation,
                confidence=confidence
            )

        except Exception as e:
            self.logger.error(
                f"Fundamental analysis failed for {stock_code}: {e}")
            return None

    def _calculate_ma_signals(self, df: pd.DataFrame, stock_code: str) -> List[TechnicalSignal]:
        """计算移动平均线信号 - 使用统一指标服务"""
        signals = []
        try:
            try:
                ma5_result = calculate_indicator('MA', df, timeperiod=5)
                ma20_result = calculate_indicator('MA', df, timeperiod=20)
                ma60_result = calculate_indicator('MA', df, timeperiod=60)
                
                if isinstance(ma5_result, pd.DataFrame) and 'MA' in ma5_result.columns:
                    df['ma5'] = ma5_result['MA']
                else:
                    df['ma5'] = df['close'].rolling(window=5).mean()
                
                if isinstance(ma20_result, pd.DataFrame) and 'MA' in ma20_result.columns:
                    df['ma20'] = ma20_result['MA']
                else:
                    df['ma20'] = df['close'].rolling(window=20).mean()
                
                if isinstance(ma60_result, pd.DataFrame) and 'MA' in ma60_result.columns:
                    df['ma60'] = ma60_result['MA']
                else:
                    df['ma60'] = df['close'].rolling(window=60).mean()
            except Exception as e:
                self.logger.warning(f"统一服务计算MA失败，使用本地计算: {e}")
                df['ma5'] = df['close'].rolling(window=5).mean()
                df['ma20'] = df['close'].rolling(window=20).mean()
                df['ma60'] = df['close'].rolling(window=60).mean()

            current_price = df['close'].iloc[-1]
            ma5 = df['ma5'].iloc[-1]
            ma20 = df['ma20'].iloc[-1]
            ma60 = df['ma60'].iloc[-1]

            if pd.isna(ma5) or pd.isna(ma20) or pd.isna(ma60):
                return signals

            if ma5 > ma20 > ma60:
                signals.append(TechnicalSignal(
                    signal_type='buy',
                    strength=0.8,
                    indicator='MA_Golden_Cross',
                    description='均线多头排列，趋势向上',
                    timestamp=datetime.now(),
                    price=current_price
                ))
            elif ma5 < ma20 < ma60:
                signals.append(TechnicalSignal(
                    signal_type='sell',
                    strength=0.7,
                    indicator='MA_Death_Cross',
                    description='均线空头排列，趋势向下',
                    timestamp=datetime.now(),
                    price=current_price
                ))

            if current_price > ma20:
                signals.append(TechnicalSignal(
                    signal_type='buy',
                    strength=0.6,
                    indicator='Price_Above_MA20',
                    description='价格站上20日均线，短期趋势积极',
                    timestamp=datetime.now(),
                    price=current_price
                ))

        except Exception as e:
            self.logger.error(f"MA signal calculation failed: {e}")

        return signals

    def _calculate_rsi_signals(self, df: pd.DataFrame, stock_code: str) -> List[TechnicalSignal]:
        """计算RSI信号 - 使用统一指标服务"""
        signals = []
        try:
            try:
                result = calculate_indicator('RSI', df, timeperiod=14)
                if isinstance(result, pd.DataFrame) and 'RSI' in result.columns:
                    df['rsi'] = result['RSI']
                else:
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                    rs = gain / loss
                    df['rsi'] = 100 - (100 / (1 + rs))
            except Exception as e:
                self.logger.warning(f"统一服务计算RSI失败，使用本地计算: {e}")
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))

            current_rsi = df['rsi'].iloc[-1]
            current_price = df['close'].iloc[-1]

            if pd.isna(current_rsi):
                return signals

            if current_rsi < 30:
                signals.append(TechnicalSignal(
                    signal_type='buy',
                    strength=0.7,
                    indicator='RSI_Oversold',
                    description=f'RSI {current_rsi:.1f} 超卖，可能反弹',
                    timestamp=datetime.now(),
                    price=current_price
                ))
            elif current_rsi > 70:
                signals.append(TechnicalSignal(
                    signal_type='sell',
                    strength=0.7,
                    indicator='RSI_Overbought',
                    description=f'RSI {current_rsi:.1f} 超买，可能回调',
                    timestamp=datetime.now(),
                    price=current_price
                ))

        except Exception as e:
            self.logger.error(f"RSI signal calculation failed: {e}")

        return signals

    def _calculate_macd_signals(self, df: pd.DataFrame, stock_code: str) -> List[TechnicalSignal]:
        """计算MACD信号 - 使用统一指标服务"""
        signals = []
        try:
            try:
                result = calculate_indicator('MACD', df, fastperiod=12, slowperiod=26, signalperiod=9)
                if isinstance(result, pd.DataFrame):
                    if 'MACD' in result.columns:
                        df['macd'] = result['MACD']
                    if 'MACDSignal' in result.columns:
                        df['macd_signal'] = result['MACDSignal']
                    if 'MACDHist' in result.columns:
                        df['macd_histogram'] = result['MACDHist']
                
                if 'macd' not in df.columns or 'macd_signal' not in df.columns:
                    raise ValueError("MACD计算结果不完整")
            except Exception as e:
                self.logger.warning(f"统一服务计算MACD失败，使用本地计算: {e}")
                exp1 = df['close'].ewm(span=12).mean()
                exp2 = df['close'].ewm(span=26).mean()
                df['macd'] = exp1 - exp2
                df['macd_signal'] = df['macd'].ewm(span=9).mean()
                df['macd_histogram'] = df['macd'] - df['macd_signal']

            current_macd = df['macd'].iloc[-1]
            current_signal = df['macd_signal'].iloc[-1]
            prev_macd = df['macd'].iloc[-2]
            prev_signal = df['macd_signal'].iloc[-2]
            current_price = df['close'].iloc[-1]

            if pd.isna(current_macd) or pd.isna(current_signal):
                return signals

            if current_macd > current_signal and prev_macd <= prev_signal:
                signals.append(TechnicalSignal(
                    signal_type='buy',
                    strength=0.8,
                    indicator='MACD_Golden_Cross',
                    description='MACD金叉，买入信号',
                    timestamp=datetime.now(),
                    price=current_price
                ))
            elif current_macd < current_signal and prev_macd >= prev_signal:
                signals.append(TechnicalSignal(
                    signal_type='sell',
                    strength=0.8,
                    indicator='MACD_Death_Cross',
                    description='MACD死叉，卖出信号',
                    timestamp=datetime.now(),
                    price=current_price
                ))

        except Exception as e:
            self.logger.error(f"MACD signal calculation failed: {e}")

        return signals

    def _calculate_bollinger_signals(self, df: pd.DataFrame, stock_code: str) -> List[TechnicalSignal]:
        """计算布林带信号 - 使用统一指标服务"""
        signals = []
        try:
            try:
                result = calculate_indicator('BBANDS', df, timeperiod=20, nbdevup=2, nbdevdn=2)
                if isinstance(result, pd.DataFrame):
                    if 'BBMiddle' in result.columns:
                        df['bb_middle'] = result['BBMiddle']
                    if 'BBUpper' in result.columns:
                        df['bb_upper'] = result['BBUpper']
                    if 'BBLower' in result.columns:
                        df['bb_lower'] = result['BBLower']
                
                if 'bb_upper' not in df.columns or 'bb_lower' not in df.columns:
                    raise ValueError("布林带计算结果不完整")
            except Exception as e:
                self.logger.warning(f"统一服务计算布林带失败，使用本地计算: {e}")
                df['bb_middle'] = df['close'].rolling(window=20).mean()
                bb_std = df['close'].rolling(window=20).std(ddof=0)
                df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
                df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

            current_price = df['close'].iloc[-1]
            bb_upper = df['bb_upper'].iloc[-1]
            bb_lower = df['bb_lower'].iloc[-1]

            if pd.isna(bb_upper) or pd.isna(bb_lower):
                return signals

            if current_price <= bb_lower:
                signals.append(TechnicalSignal(
                    signal_type='buy',
                    strength=0.6,
                    indicator='Bollinger_Lower',
                    description='价格触及布林带下轨，可能反弹',
                    timestamp=datetime.now(),
                    price=current_price
                ))
            elif current_price >= bb_upper:
                signals.append(TechnicalSignal(
                    signal_type='sell',
                    strength=0.6,
                    indicator='Bollinger_Upper',
                    description='价格触及布林带上轨，可能回调',
                    timestamp=datetime.now(),
                    price=current_price
                ))

        except Exception as e:
            self.logger.error(f"Bollinger signal calculation failed: {e}")

        return signals

    def _generate_recommendation(self, signals: List[TechnicalSignal]) -> Tuple[str, float]:
        """生成综合推荐"""
        if not signals:
            return 'hold', 0.5

        # 计算买入和卖出信号的权重
        buy_weight = sum(s.strength for s in signals if s.signal_type == 'buy')
        sell_weight = sum(
            s.strength for s in signals if s.signal_type == 'sell')

        total_signals = len(
            [s for s in signals if s.signal_type in ['buy', 'sell']])
        if total_signals == 0:
            return 'hold', 0.5

        # 计算净权重
        net_weight = buy_weight - sell_weight
        max_weight = max(buy_weight, sell_weight)

        if net_weight > 1.5:
            return 'strong_buy', min(0.9, max_weight / total_signals)
        elif net_weight > 0.5:
            return 'buy', min(0.8, max_weight / total_signals)
        elif net_weight < -1.5:
            return 'strong_sell', min(0.9, max_weight / total_signals)
        elif net_weight < -0.5:
            return 'sell', min(0.8, max_weight / total_signals)
        else:
            return 'hold', 0.5

    def _calculate_price_targets(self, df: pd.DataFrame, recommendation: str) -> Tuple[Optional[float], Optional[float]]:
        """计算目标价和止损价"""
        if df.empty:
            return None, None

        current_price = df['close'].iloc[-1]

        # 计算近期波动率
        returns = df['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)  # 年化波动率

        if recommendation in ['strong_buy', 'buy']:
            # 目标价：当前价格 + 1.5倍波动率
            target_price = current_price * (1 + volatility * 1.5)
            # 止损价：当前价格 - 0.5倍波动率
            stop_loss = current_price * (1 - volatility * 0.5)
        elif recommendation in ['strong_sell', 'sell']:
            # 目标价：当前价格 - 1.5倍波动率
            target_price = current_price * (1 - volatility * 1.5)
            # 止损价：当前价格 + 0.5倍波动率
            stop_loss = current_price * (1 + volatility * 0.5)
        else:
            return None, None

        return float(target_price), float(stop_loss)

    def _generate_technical_summary(self, signals: List[TechnicalSignal],
                                    recommendation: str, confidence: float) -> str:
        """生成技术分析摘要"""
        signal_count = len(signals)
        buy_signals = len([s for s in signals if s.signal_type == 'buy'])
        sell_signals = len([s for s in signals if s.signal_type == 'sell'])

        summary = f"技术分析共产生{signal_count}个信号，其中买入信号{buy_signals}个，卖出信号{sell_signals}个。"
        summary += f"综合推荐：{recommendation}，置信度：{confidence:.1%}。"

        # 添加主要信号描述
        strong_signals = [s for s in signals if s.strength > 0.7]
        if strong_signals:
            summary += "主要信号：" + \
                "；".join([s.description for s in strong_signals[:3]])

        return summary

    def _generate_fundamental_summary(self, signals: List[TechnicalSignal],
                                      stock_info: StockInfo, recommendation: str) -> str:
        """生成基本面分析摘要"""
        summary = f"基本面分析：{stock_info.name}（{stock_info.code}）"

        if stock_info.pe_ratio:
            summary += f"，PE比率{stock_info.pe_ratio:.2f}"
        if stock_info.pb_ratio:
            summary += f"，PB比率{stock_info.pb_ratio:.2f}"
        if stock_info.industry:
            summary += f"，所属{stock_info.industry}行业"

        summary += f"。综合推荐：{recommendation}。"

        return summary

    def _combine_analysis(self, tech_result: AnalysisResult,
                          fund_result: AnalysisResult) -> AnalysisResult:
        """合并技术分析和基本面分析"""
        if not tech_result or not fund_result:
            return tech_result or fund_result

        # 合并信号
        combined_signals = tech_result.signals + fund_result.signals

        # 重新生成推荐
        recommendation, confidence = self._generate_recommendation(
            combined_signals)

        # 合并摘要
        summary = f"综合分析：{tech_result.summary} {fund_result.summary}"

        return AnalysisResult(
            stock_code=tech_result.stock_code,
            stock_name=tech_result.stock_name,
            analysis_type='combined',
            signals=combined_signals,
            summary=summary,
            recommendation=recommendation,
            confidence=confidence,
            target_price=tech_result.target_price,
            stop_loss=tech_result.stop_loss
        )

    def get_market_overview(self) -> Dict[str, Any]:
        """获取市场概览"""
        try:
            # 这里可以分析主要指数和市场情绪
            return {
                'market_trend': 'neutral',
                'volatility': 'medium',
                'sentiment': 'cautious',
                'recommendation': '保持谨慎，关注个股机会',
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to get market overview: {e}")
            return {}

    def clear_cache(self) -> None:
        """清除分析缓存"""
        self._analysis_cache.clear()
        self.logger.info("Analysis cache cleared")
