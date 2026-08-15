from loguru import logger
"""
增强的单股分析器 - 专业级单股分析功能
对标专业量化软件的单股分析标准
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import warnings
from dataclasses import dataclass
from enum import Enum
from scipy import stats
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False

# 导入自定义模块
from core.data_validator import ProfessionalDataValidator, ValidationLevel
from core.performance_optimizer import ProfessionalPerformanceOptimizer
from analysis.pattern_recognition import EnhancedPatternRecognizer
from analysis.technical_analysis import TechnicalAnalyzer
from core.indicator_service import calculate_indicator, get_indicator_metadata, get_all_indicators_metadata

class AnalysisDepth(Enum):
    """分析深度级别"""
    BASIC = "basic"              # 基础分析
    STANDARD = "standard"        # 标准分析
    COMPREHENSIVE = "comprehensive"  # 全面分析
    PROFESSIONAL = "professional"   # 专业级分析

class RiskLevel(Enum):
    """风险等级"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class InvestmentHorizon(Enum):
    """投资时间范围"""
    SHORT_TERM = "short_term"    # 短期 (1-30天)
    MEDIUM_TERM = "medium_term"  # 中期 (1-6个月)
    LONG_TERM = "long_term"      # 长期 (6个月以上)

@dataclass
class StockAnalysisResult:
    """股票分析结果"""
    stock_code: str
    stock_name: str
    analysis_date: datetime
    analysis_depth: AnalysisDepth

    # 基础信息
    current_price: float
    price_change: float
    price_change_percent: float
    volume: int
    market_cap: float

    # 技术分析
    technical_score: float
    technical_signals: List[Dict[str, Any]]
    support_levels: List[float]
    resistance_levels: List[float]
    trend_direction: str
    trend_strength: float

    # 形态识别
    patterns: List[Dict[str, Any]]
    pattern_score: float

    # 基本面分析
    fundamental_score: float
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    roe: Optional[float]
    debt_ratio: Optional[float]

    # 风险评估
    risk_level: RiskLevel
    volatility: float
    beta: Optional[float]
    max_drawdown: float
    var_95: float  # 95%置信度的VaR

    # 投资建议
    recommendation: str  # BUY, SELL, HOLD
    confidence: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    investment_horizon: InvestmentHorizon

    # 综合评分
    overall_score: float
    quality_rating: str

    # 详细分析
    detailed_analysis: Dict[str, Any]
    warnings: List[str]
    suggestions: List[str]

class ProfessionalStockAnalyzer:
    """专业级股票分析器"""

    def __init__(self, analysis_depth: AnalysisDepth = AnalysisDepth.PROFESSIONAL):
        """
        初始化分析器

        Args:
            analysis_depth: 分析深度级别
        """
        self.analysis_depth = analysis_depth
        self.logger = logger

        # 初始化组件
        self.data_validator = ProfessionalDataValidator(
            ValidationLevel.PROFESSIONAL)
        self.pattern_recognizer = EnhancedPatternRecognizer(debug_mode=False)
        self.technical_analyzer = TechnicalAnalyzer()
        self.performance_optimizer = ProfessionalPerformanceOptimizer()  # 实例化性能优化器

        # 分析配置
        self.config = {
            'min_data_points': 60,  # 最少数据点数
            'volatility_window': 20,  # 波动率计算窗口
            'trend_window': 50,  # 趋势计算窗口
            'support_resistance_window': 100,  # 支撑阻力计算窗口
        }

    def analyze_stock(self, kdata: pd.DataFrame, stock_code: str,
                      stock_name: str = None, market_data: Dict = None) -> StockAnalysisResult:
        """
        全面分析股票

        Args:
            kdata: K线数据
            stock_code: 股票代码
            stock_name: 股票名称
            market_data: 市场数据（可选）

        Returns:
            StockAnalysisResult: 分析结果
        """
        self.performance_optimizer.start_monitoring()  # 开始监控
        try:
            # 1. 数据验证
            validation_result = self.data_validator.validate_kdata(
                kdata, stock_code)
            if not validation_result.is_valid:
                raise ValueError(f"数据验证失败: {validation_result.errors}")

            # 2. 数据预处理
            processed_data = self._preprocess_data(kdata)

            # 3. 基础信息提取
            basic_info = self._extract_basic_info(
                processed_data, stock_code, stock_name)

            # 4. 技术分析
            technical_analysis = self._perform_technical_analysis(
                processed_data)

            # 5. 形态识别
            pattern_analysis = self._perform_pattern_analysis(
                processed_data)

            # 6. 基本面分析（如果有数据）
            fundamental_analysis = self._perform_fundamental_analysis(
                processed_data, stock_code, market_data
            )

            # 7. 风险评估
            risk_assessment = self._assess_risk(
                processed_data, market_data)

            # 8. 投资建议生成
            investment_recommendation = self._generate_investment_recommendation(
                technical_analysis, pattern_analysis, fundamental_analysis, risk_assessment
            )

            # 9. 综合评分
            overall_evaluation = self._calculate_overall_score(
                technical_analysis, pattern_analysis, fundamental_analysis, risk_assessment
            )

            # 10. 构建分析结果
            result = StockAnalysisResult(
                stock_code=stock_code,
                stock_name=stock_name or stock_code,
                analysis_date=datetime.now(),
                analysis_depth=self.analysis_depth,

                # 基础信息
                current_price=basic_info['current_price'],
                price_change=basic_info['price_change'],
                price_change_percent=basic_info['price_change_percent'],
                volume=basic_info['volume'],
                market_cap=basic_info.get('market_cap', 0),

                # 技术分析
                technical_score=technical_analysis['score'],
                technical_signals=technical_analysis['signals'],
                support_levels=technical_analysis['support_levels'],
                resistance_levels=technical_analysis['resistance_levels'],
                trend_direction=technical_analysis['trend_direction'],
                trend_strength=technical_analysis['trend_strength'],

                # 形态识别
                patterns=pattern_analysis['patterns'],
                pattern_score=pattern_analysis['score'],

                # 基本面分析
                fundamental_score=fundamental_analysis['score'],
                pe_ratio=fundamental_analysis.get('pe_ratio'),
                pb_ratio=fundamental_analysis.get('pb_ratio'),
                roe=fundamental_analysis.get('roe'),
                debt_ratio=fundamental_analysis.get('debt_ratio'),

                # 风险评估
                risk_level=risk_assessment['risk_level'],
                volatility=risk_assessment['volatility'],
                beta=risk_assessment.get('beta'),
                max_drawdown=risk_assessment['max_drawdown'],
                var_95=risk_assessment['var_95'],

                # 投资建议
                recommendation=investment_recommendation['action'],
                confidence=investment_recommendation['confidence'],
                target_price=investment_recommendation.get('target_price'),
                stop_loss=investment_recommendation.get('stop_loss'),
                investment_horizon=investment_recommendation['horizon'],

                # 综合评分
                overall_score=overall_evaluation['score'],
                quality_rating=overall_evaluation['rating'],

                # 详细分析
                detailed_analysis={
                    'technical': technical_analysis,
                    'pattern': pattern_analysis,
                    'fundamental': fundamental_analysis,
                    'risk': risk_assessment,
                    'validation': validation_result.statistics
                },
                warnings=validation_result.warnings + self._generate_analysis_warnings(
                    technical_analysis, pattern_analysis, risk_assessment
                ),
                suggestions=validation_result.suggestions +
                investment_recommendation.get('suggestions', [])
            )

            return result

        except Exception as e:
            self.logger.error(f"股票分析失败 {stock_code}: {e}")
            raise
        finally:
            metrics = self.performance_optimizer.stop_monitoring()  # 结束监控
            self.logger.info(
                f"股票分析_{stock_code} 执行完成 - 耗时: {metrics.execution_time:.3f}s, "
                f"内存: {metrics.memory_usage:.1f}%, CPU: {metrics.cpu_usage:.1f}%"
            )

    def _preprocess_data(self, kdata: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        try:
            # 复制数据避免修改原始数据
            data = kdata.copy()

            # 确保数据按日期排序
            if 'datetime' in data.columns:
                data = data.sort_values('datetime')
            elif data.index.name == 'datetime':
                data = data.sort_index()

            # 计算基础技术指标（原代码 calculate_indicator(data, 'all') 参数颠倒且 'all' 不是合法指标名，必崩）
            data = calculate_indicator('MA', data, timeperiod=20)

            # 计算收益率
            data['returns'] = data['close'].pct_change()
            data['log_returns'] = np.log(
                data['close'] / data['close'].shift(1))

            # 计算累计收益
            data['cumulative_returns'] = (1 + data['returns']).cumprod()

            # 移除NaN值
            data = data.dropna()

            return data

        except Exception as e:
            self.logger.error(f"数据预处理失败: {e}")
            raise

    def _extract_basic_info(self, data: pd.DataFrame, stock_code: str,
                            stock_name: str = None) -> Dict[str, Any]:
        """提取基础信息"""
        try:
            current_price = data['close'].iloc[-1]
            previous_price = data['close'].iloc[-2] if len(
                data) > 1 else current_price

            return {
                'current_price': current_price,
                'price_change': current_price - previous_price,
                'price_change_percent': (current_price / previous_price - 1) * 100 if previous_price != 0 else 0,
                'volume': int(data['volume'].iloc[-1]),
                'high_52w': data['high'].rolling(252).max().iloc[-1],
                'low_52w': data['low'].rolling(252).min().iloc[-1],
                'avg_volume_20d': data['volume'].rolling(20).mean().iloc[-1],
                'market_cap': None  # 需要外部数据源
            }

        except Exception as e:
            self.logger.error(f"提取基础信息失败: {e}")
            return {}

    def _perform_technical_analysis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """执行技术分析"""
        try:
            # 完全依赖TechnicalAnalyzer进行分析
            analysis = self.technical_analyzer.analyze(data)

            # 技术指标信号
            indicator_signals = self._analyze_technical_indicators(data)
            analysis['signals'] = indicator_signals

            # 计算技术分析综合得分
            analysis['score'] = self._calculate_technical_score(analysis)

            return analysis

        except Exception as e:
            self.logger.error(f"技术分析失败: {e}")
            return {'score': 0.0, 'signals': [], 'support_levels': [],
                    'resistance_levels': [], 'trend_direction': 'NEUTRAL', 'trend_strength': 0.0}

    def _analyze_technical_indicators(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """分析技术指标信号"""
        signals = []

        try:
            # RSI信号
            if 'rsi' in data.columns:
                rsi_current = data['rsi'].iloc[-1]
                if rsi_current > 70:
                    signals.append({
                        'indicator': 'RSI',
                        'signal': 'SELL',
                        'strength': min((rsi_current - 70) / 30, 1.0),
                        'description': f'RSI超买 ({rsi_current:.1f})'
                    })
                elif rsi_current < 30:
                    signals.append({
                        'indicator': 'RSI',
                        'signal': 'BUY',
                        'strength': min((30 - rsi_current) / 30, 1.0),
                        'description': f'RSI超卖 ({rsi_current:.1f})'
                    })

            # MACD信号
            if all(col in data.columns for col in ['macd', 'signal']):
                macd_current = data['macd'].iloc[-1]
                signal_current = data['signal'].iloc[-1]
                macd_prev = data['macd'].iloc[-2]
                signal_prev = data['signal'].iloc[-2]

                # 金叉死叉
                if macd_prev <= signal_prev and macd_current > signal_current:
                    signals.append({
                        'indicator': 'MACD',
                        'signal': 'BUY',
                        'strength': 0.7,
                        'description': 'MACD金叉'
                    })
                elif macd_prev >= signal_prev and macd_current < signal_current:
                    signals.append({
                        'indicator': 'MACD',
                        'signal': 'SELL',
                        'strength': 0.7,
                        'description': 'MACD死叉'
                    })

            # 布林带信号
            if all(col in data.columns for col in ['bb_upper', 'bb_lower', 'bb_middle']):
                current_price = data['close'].iloc[-1]
                bb_upper = data['bb_upper'].iloc[-1]
                bb_lower = data['bb_lower'].iloc[-1]
                bb_middle = data['bb_middle'].iloc[-1]

                if current_price > bb_upper:
                    signals.append({
                        'indicator': 'BOLLINGER',
                        'signal': 'SELL',
                        'strength': 0.6,
                        'description': '价格突破布林带上轨'
                    })
                elif current_price < bb_lower:
                    signals.append({
                        'indicator': 'BOLLINGER',
                        'signal': 'BUY',
                        'strength': 0.6,
                        'description': '价格跌破布林带下轨'
                    })

            return signals

        except Exception as e:
            self.logger.error(f"技术指标分析失败: {e}")
            return []

    def _perform_pattern_analysis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """执行形态分析"""
        try:
            # 使用形态识别器
            patterns = self.pattern_recognizer.identify_patterns(data)

            # 计算形态得分
            pattern_score = 0.0
            if patterns:
                # 基于形态的信号强度和置信度计算得分
                total_confidence = sum(p.get('confidence', 0)
                                       for p in patterns)
                pattern_score = min(total_confidence / len(patterns), 1.0)

            return {
                'patterns': patterns,
                'score': pattern_score,
                'pattern_count': len(patterns)
            }

        except Exception as e:
            self.logger.error(f"形态分析失败: {e}")
            return {'patterns': [], 'score': 0.0, 'pattern_count': 0}

    def _perform_fundamental_analysis(self, data: pd.DataFrame, stock_code: str,
                                      market_data: Dict = None) -> Dict[str, Any]:
        """执行基本面分析"""
        try:
            # 基础框架，实际需要外部数据源
            fundamental_data = {
                'score': 0.5,  # 默认中性得分
                'pe_ratio': None,
                'pb_ratio': None,
                'roe': None,
                'debt_ratio': None,
                'revenue_growth': None,
                'profit_growth': None,
                'analysis': '基本面数据需要外部数据源'
            }

            # 如果有市场数据，进行分析
            if market_data:
                # 这里可以添加具体的基本面分析逻辑
                pass

            return fundamental_data

        except Exception as e:
            self.logger.error(f"基本面分析失败: {e}")
            return {'score': 0.5}

    def _assess_risk(self, data: pd.DataFrame, market_data: Dict = None) -> Dict[str, Any]:
        """风险评估"""
        try:
            # 计算波动率
            returns = data['returns'].dropna()
            volatility = returns.std() * np.sqrt(252)  # 年化波动率

            # 计算最大回撤
            cumulative_returns = data['cumulative_returns']
            rolling_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - rolling_max) / rolling_max
            max_drawdown = drawdown.min()

            # 计算VaR (95%置信度) - 修复：VaR应该为正值表示损失
            var_95 = abs(np.percentile(returns, 5))

            # 风险等级评估
            if volatility < 0.15:
                risk_level = RiskLevel.LOW
            elif volatility < 0.25:
                risk_level = RiskLevel.MEDIUM
            elif volatility < 0.35:
                risk_level = RiskLevel.HIGH
            else:
                risk_level = RiskLevel.VERY_HIGH

            # Beta计算（需要市场数据）
            beta = None
            if market_data and 'market_returns' in market_data:
                market_returns = market_data['market_returns']
                if len(market_returns) == len(returns):
                    covariance = np.cov(returns, market_returns)[0][1]
                    market_variance = np.var(market_returns)
                    beta = covariance / market_variance if market_variance != 0 else None

            return {
                'risk_level': risk_level,
                'volatility': volatility,
                'max_drawdown': max_drawdown,
                'var_95': var_95,
                'beta': beta,
                'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0
            }

        except Exception as e:
            self.logger.error(f"风险评估失败: {e}")
            return {
                'risk_level': RiskLevel.MEDIUM,
                'volatility': 0.0,
                'max_drawdown': 0.0,
                'var_95': 0.0,
                'beta': None
            }

    def _generate_investment_recommendation(self, technical: Dict, pattern: Dict,
                                            fundamental: Dict, risk: Dict) -> Dict[str, Any]:
        """生成投资建议"""
        try:
            # 综合各项分析得出建议
            technical_score = technical.get('score', 0.5)
            pattern_score = pattern.get('score', 0.5)
            fundamental_score = fundamental.get('score', 0.5)

            # 加权综合得分
            weights = {'technical': 0.4, 'pattern': 0.3, 'fundamental': 0.3}
            composite_score = (
                technical_score * weights['technical'] +
                pattern_score * weights['pattern'] +
                fundamental_score * weights['fundamental']
            )

            # 风险调整
            risk_level = risk.get('risk_level', RiskLevel.MEDIUM)
            if risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                composite_score *= 0.8  # 高风险降低推荐强度

            # 生成建议
            if composite_score > 0.7:
                action = 'BUY'
                confidence = min(composite_score, 0.95)
                horizon = InvestmentHorizon.MEDIUM_TERM
            elif composite_score < 0.3:
                action = 'SELL'
                confidence = min(1 - composite_score, 0.95)
                horizon = InvestmentHorizon.SHORT_TERM
            else:
                action = 'HOLD'
                confidence = 0.5
                horizon = InvestmentHorizon.LONG_TERM

            return {
                'action': action,
                'confidence': confidence,
                'horizon': horizon,
                'composite_score': composite_score,
                'target_price': None,  # 需要更复杂的计算
                'stop_loss': None,     # 需要更复杂的计算
                'suggestions': self._generate_investment_suggestions(technical, pattern, risk)
            }

        except Exception as e:
            self.logger.error(f"投资建议生成失败: {e}")
            return {
                'action': 'HOLD',
                'confidence': 0.5,
                'horizon': InvestmentHorizon.MEDIUM_TERM,
                'suggestions': []
            }

    def _calculate_technical_score(self, analysis: Dict) -> float:
        """计算技术分析得分"""
        try:
            score = 0.5  # 基础得分

            # 趋势得分
            trend_strength = analysis.get('trend_strength', 0)
            score += trend_strength * 0.3

            # 信号得分
            signals = analysis.get('signals', [])
            if signals:
                buy_signals = [s for s in signals if s['signal'] == 'BUY']
                sell_signals = [s for s in signals if s['signal'] == 'SELL']

                buy_strength = sum(s['strength'] for s in buy_signals)
                sell_strength = sum(s['strength'] for s in sell_signals)

                signal_score = (buy_strength - sell_strength) / \
                    max(len(signals), 1)
                score += signal_score * 0.2

            return max(0.0, min(1.0, score))

        except Exception as e:
            self.logger.error(f"技术分析得分计算失败: {e}")
            return 0.5

    def _calculate_overall_score(self, technical: Dict, pattern: Dict,
                                 fundamental: Dict, risk: Dict) -> Dict[str, Any]:
        """计算综合评分"""
        try:
            # 各项得分
            technical_score = technical.get('score', 0.5)
            pattern_score = pattern.get('score', 0.5)
            fundamental_score = fundamental.get('score', 0.5)

            # 加权平均
            overall_score = (
                technical_score * 0.35 +
                pattern_score * 0.25 +
                fundamental_score * 0.4
            )

            # 质量评级
            if overall_score >= 0.8:
                rating = 'EXCELLENT'
            elif overall_score >= 0.6:
                rating = 'GOOD'
            elif overall_score >= 0.4:
                rating = 'FAIR'
            else:
                rating = 'POOR'

            return {
                'score': overall_score,
                'rating': rating,
                'components': {
                    'technical': technical_score,
                    'pattern': pattern_score,
                    'fundamental': fundamental_score
                }
            }

        except Exception as e:
            self.logger.error(f"综合评分计算失败: {e}")
            return {'score': 0.5, 'rating': 'FAIR'}

    def _generate_analysis_warnings(self, technical: Dict, pattern: Dict,
                                    risk: Dict) -> List[str]:
        """生成分析警告"""
        warnings = []

        try:
            # 风险警告
            risk_level = risk.get('risk_level', RiskLevel.MEDIUM)
            if risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                warnings.append(
                    f"高风险警告：该股票波动率较高 ({risk.get('volatility', 0):.2%})")

            # 技术指标警告
            signals = technical.get('signals', [])
            sell_signals = [s for s in signals if s['signal'] == 'SELL']
            if len(sell_signals) >= 2:
                warnings.append("多个技术指标发出卖出信号")

            # 形态警告
            patterns = pattern.get('patterns', [])
            bearish_patterns = [
                p for p in patterns if p.get('signal_type') == 'SELL']
            if bearish_patterns:
                warnings.append("识别到看跌形态")

        except Exception as e:
            self.logger.error(f"警告生成失败: {e}")

        return warnings

    def _generate_investment_suggestions(self, technical: Dict, pattern: Dict,
                                         risk: Dict) -> List[str]:
        """生成投资建议"""
        suggestions = []

        try:
            # 基于风险的建议
            risk_level = risk.get('risk_level', RiskLevel.MEDIUM)
            if risk_level == RiskLevel.HIGH:
                suggestions.append("建议设置较紧的止损位")
                suggestions.append("考虑分批建仓以降低风险")

            # 基于技术分析的建议
            trend_direction = technical.get('trend_direction', 'NEUTRAL')
            if 'UPTREND' in trend_direction:
                suggestions.append("趋势向上，可考虑逢低买入")
            elif 'DOWNTREND' in trend_direction:
                suggestions.append("趋势向下，建议谨慎操作")

            # 基于形态的建议
            patterns = pattern.get('patterns', [])
            if patterns:
                recent_pattern = patterns[-1]  # 最近的形态
                if recent_pattern.get('signal_type') == 'BUY':
                    suggestions.append(
                        f"识别到看涨形态：{recent_pattern.get('pattern_type', '')}")
                elif recent_pattern.get('signal_type') == 'SELL':
                    suggestions.append(
                        f"识别到看跌形态：{recent_pattern.get('pattern_type', '')}")

        except Exception as e:
            self.logger.error(f"投资建议生成失败: {e}")

        return suggestions

# 便捷函数

def analyze_single_stock(kdata: pd.DataFrame, stock_code: str,
                         stock_name: str = None,
                         analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD) -> StockAnalysisResult:
    """
    分析单只股票

    Args:
        kdata: K线数据
        stock_code: 股票代码
        stock_name: 股票名称
        analysis_depth: 分析深度

    Returns:
        StockAnalysisResult: 分析结果
    """
    analyzer = ProfessionalStockAnalyzer(analysis_depth)
    return analyzer.analyze_stock(kdata, stock_code, stock_name)

def batch_analyze_stocks(stock_data_dict: Dict[str, pd.DataFrame],
                         analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD) -> Dict[str, StockAnalysisResult]:
    """
    批量分析股票

    Args:
        stock_data_dict: {股票代码: K线数据} 字典
        analysis_depth: 分析深度

    Returns:
        Dict: {股票代码: 分析结果} 字典
    """
    analyzer = ProfessionalStockAnalyzer(analysis_depth)
    results = {}

    for stock_code, kdata in stock_data_dict.items():
        try:
            result = analyzer.analyze_stock(kdata, stock_code)
            results[stock_code] = result
        except Exception as e:
            logger.error(f"分析股票 {stock_code} 失败: {e}")

    return results
