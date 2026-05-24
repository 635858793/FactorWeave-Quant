from loguru import logger
"""
专业风险指标计算模块
符合CFA/FRM等国际金融标准的风险管理算法实现

基于以下标准：
- CFA Institute Portfolio Management (2025 Curriculum)  
- GARP FRM Risk Management Handbook (2024)
- Basel III International Regulatory Framework
- Bloomberg/Reuters专业终端算法标准
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
from typing import Dict, List, Optional, Union, Tuple
import warnings


class ProfessionalRiskMetrics:
    """
    专业风险指标计算器

    实现符合CFA/FRM标准的风险管理算法，包括：
    - 多时间周期VaR计算
    - 增强型盈利因子
    - 精确的Sharpe比率计算
    - 专业回撤分析
    - 条件VaR和边际VaR
    """

    # 标准参数配置
    TRADING_DAYS_PER_YEAR = 252
    RISK_FREE_RATE_DEFAULT = 0.02  # 2%年化无风险利率

    # 标准置信度级别
    CONFIDENCE_LEVELS = {
        '90%': 0.90,
        '95%': 0.95,
        '99%': 0.99,
        '99.9%': 0.999
    }

    # 标准时间周期（交易日）
    TIME_HORIZONS = {
        '1d': 1,
        '1w': 5,
        '2w': 10,
        '1m': 22,
        '3m': 66,
        '6m': 126,
        '1y': 252
    }

    def __init__(self, risk_free_rate: float = RISK_FREE_RATE_DEFAULT):
        """
        初始化专业风险指标计算器

        Parameters:
        -----------
        risk_free_rate : float
            年化无风险利率，默认2%
        """
        self.risk_free_rate = risk_free_rate
        self.validation_enabled = True

    def calculate_var_comprehensive(self,
                                    returns: pd.Series,
                                    confidence_levels: List[float] = None,
                                    time_horizons: List[int] = None,
                                    method: str = 'parametric') -> Dict[str, Dict]:
        """
        计算符合CFA/FRM标准的综合VaR

        Parameters:
        -----------
        returns : pd.Series
            日收益率序列
        confidence_levels : List[float], optional
            置信度水平，默认[0.95, 0.99]
        time_horizons : List[int], optional  
            时间周期（交易日），默认[1, 10, 22, 252]
        method : str
            计算方法 ['parametric', 'historical', 'monte_carlo']

        Returns:
        --------
        Dict[str, Dict]
            多维度VaR结果

        理论依据:
        --------
        基于CFA Level II Risk Management标准：
        - 时间缩放公式：VaR(T) = VaR(1) × √T
        - 置信度：95%对应z=-1.645，99%对应z=-2.326
        - 相对VaR vs 绝对VaR的区别
        """
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]
        if time_horizons is None:
            time_horizons = [1, 10, 22, 252]

        # 输入验证
        self._validate_returns_input(returns)

        results = {}

        try:
            if method == 'parametric':
                results = self._calculate_parametric_var(returns, confidence_levels, time_horizons)
            elif method == 'historical':
                results = self._calculate_historical_var(returns, confidence_levels, time_horizons)
            elif method == 'monte_carlo':
                results = self._calculate_monte_carlo_var(returns, confidence_levels, time_horizons)
            else:
                raise ValueError(f"不支持的VaR计算方法: {method}")

            # 添加计算元数据
            results['metadata'] = {
                'method': method,
                'sample_size': len(returns),
                'calculation_date': pd.Timestamp.now(),
                'risk_free_rate': self.risk_free_rate,
                'standards_compliance': 'CFA/FRM'
            }

            logger.info(f"VaR计算完成: 方法={method}, 样本数={len(returns)}")

        except Exception as e:
            logger.error(f"VaR计算失败: {e}")
            results = self._get_fallback_var_results()

        return results

    def _calculate_parametric_var(self,
                                  returns: pd.Series,
                                  confidence_levels: List[float],
                                  time_horizons: List[int]) -> Dict[str, Dict]:
        """
        参数化VaR计算（假设正态分布）

        基于CFA标准的参数化方法
        """
        results = {}

        # 计算统计参数
        daily_mean = returns.mean()
        daily_vol = returns.std()

        for conf in confidence_levels:
            alpha = 1 - conf
            z_score = stats.norm.ppf(alpha)  # 标准正态分布分位数

            for horizon in time_horizons:
                # 标准时间缩放公式：VaR(T) = VaR(1) × √T
                horizon_vol = daily_vol * np.sqrt(horizon)
                horizon_mean = daily_mean * horizon

                # 相对VaR（相对于期望收益）
                var_relative = -(horizon_mean + z_score * horizon_vol)

                # 绝对VaR（相对于零收益）
                var_absolute = -z_score * horizon_vol

                # 组合键名
                key = f'VaR_{int(conf*100)}%_{horizon}d'

                results[key] = {
                    'relative_var': var_relative,
                    'absolute_var': var_absolute,
                    'confidence': conf,
                    'horizon_days': horizon,
                    'annualized_vol': daily_vol * np.sqrt(self.TRADING_DAYS_PER_YEAR),
                    'z_score': z_score,
                    'method': 'parametric'
                }

        return results

    def _calculate_historical_var(self,
                                  returns: pd.Series,
                                  confidence_levels: List[float],
                                  time_horizons: List[int]) -> Dict[str, Dict]:
        """
        历史模拟VaR计算

        基于FRM标准的历史模拟方法
        """
        results = {}

        for conf in confidence_levels:
            alpha = 1 - conf
            percentile = alpha * 100

            for horizon in time_horizons:
                if horizon == 1:
                    # 单日VaR直接使用历史分位数
                    var_value = np.percentile(returns, percentile)
                else:
                    # 多日VaR：模拟持有期收益
                    if len(returns) >= horizon:
                        # 滚动窗口计算持有期收益
                        rolling_returns = returns.rolling(window=horizon).sum()
                        rolling_returns = rolling_returns.dropna()

                        if len(rolling_returns) > 0:
                            var_value = np.percentile(rolling_returns, percentile)
                        else:
                            # 回退到时间缩放方法
                            var_value = np.percentile(returns, percentile) * np.sqrt(horizon)
                    else:
                        # 样本不足，使用时间缩放
                        var_value = np.percentile(returns, percentile) * np.sqrt(horizon)

                key = f'VaR_{int(conf*100)}%_{horizon}d'

                results[key] = {
                    'relative_var': abs(var_value),
                    'absolute_var': abs(var_value),
                    'confidence': conf,
                    'horizon_days': horizon,
                    'percentile_used': percentile,
                    'method': 'historical'
                }

        return results

    def _calculate_monte_carlo_var(self,
                                   returns: pd.Series,
                                   confidence_levels: List[float],
                                   time_horizons: List[int],
                                   num_simulations: int = 10000) -> Dict[str, Dict]:
        """
        蒙特卡洛VaR计算

        基于专业风险管理标准的MC模拟
        """
        results = {}

        # 过滤NaN并估计返回分布参数
        clean_returns = returns.dropna()
        if len(clean_returns) < 2:
            logger.warning("蒙特卡洛VaR: 清理后数据不足")
            return results

        daily_mean = clean_returns.mean()
        daily_vol = clean_returns.std()

        # 检验正态性假设
        _, p_value = stats.normaltest(clean_returns)
        distribution_type = 'normal' if p_value > 0.05 else 'empirical'

        for conf in confidence_levels:
            alpha = 1 - conf

            for horizon in time_horizons:
                # 蒙特卡洛模拟
                if distribution_type == 'normal':
                    # 使用正态分布模拟
                    simulated_returns = np.random.normal(
                        daily_mean * horizon,
                        daily_vol * np.sqrt(horizon),
                        num_simulations
                    )
                else:
                    # 使用经验分布重采样
                    clean_values = clean_returns.values
                    simulated_returns = np.random.choice(
                        clean_values,
                        size=(num_simulations, horizon),
                        replace=True
                    ).sum(axis=1)

                # 计算VaR
                var_value = np.percentile(simulated_returns, alpha * 100)

                key = f'VaR_{int(conf*100)}%_{horizon}d'

                results[key] = {
                    'relative_var': abs(var_value),
                    'absolute_var': abs(var_value),
                    'confidence': conf,
                    'horizon_days': horizon,
                    'num_simulations': num_simulations,
                    'distribution_type': distribution_type,
                    'normality_p_value': p_value,
                    'method': 'monte_carlo'
                }

        return results

    def calculate_enhanced_profit_factor(self,
                                         returns: pd.Series,
                                         method: str = 'geometric') -> Dict[str, float]:
        """
        计算增强版盈利因子

        Parameters:
        -----------
        returns : pd.Series
            交易收益率序列
        method : str
            计算方法 ['arithmetic', 'geometric', 'weighted', 'all']

        Returns:
        --------
        Dict[str, float]
            多种方法的盈利因子结果

        理论依据:
        --------
        基于量化交易专业标准：
        - 算术方法：传统的总盈利/总亏损
        - 几何方法：考虑复利效应的几何平均
        - 加权方法：按交易规模加权计算
        """
        # 输入验证
        self._validate_returns_input(returns)

        winning_trades = returns[returns > 0]
        losing_trades = returns[returns < 0]

        results = {}

        # 基础统计信息
        results['sample_size'] = len(returns)
        results['win_rate'] = len(winning_trades) / len(returns) if len(returns) > 0 else 0
        results['loss_rate'] = len(losing_trades) / len(returns) if len(returns) > 0 else 0
        results['avg_win'] = winning_trades.mean() if len(winning_trades) > 0 else 0
        results['avg_loss'] = losing_trades.mean() if len(losing_trades) > 0 else 0

        # 处理边界情况
        if len(losing_trades) == 0:
            results['profit_factor_arithmetic'] = float('inf')
            results['profit_factor_geometric'] = float('inf')
            results['profit_factor_weighted'] = float('inf')
            return results

        if len(winning_trades) == 0:
            results['profit_factor_arithmetic'] = 0.0
            results['profit_factor_geometric'] = 0.0
            results['profit_factor_weighted'] = 0.0
            return results

        try:
            # 1. 算术平均方法（传统方法）
            if method in ['arithmetic', 'all']:
                pf_arithmetic = winning_trades.sum() / abs(losing_trades.sum())
                results['profit_factor_arithmetic'] = pf_arithmetic

            # 2. 几何平均方法（考虑复利效应）
            if method in ['geometric', 'all']:
                # 计算几何平均收益
                geometric_wins = (1 + winning_trades).prod() ** (1/len(winning_trades)) - 1
                geometric_losses = abs((1 + losing_trades).prod() ** (1/len(losing_trades)) - 1)

                if geometric_losses > 0:
                    pf_geometric = geometric_wins / geometric_losses
                    results['profit_factor_geometric'] = pf_geometric
                else:
                    results['profit_factor_geometric'] = float('inf')

            # 3. 加权方法（按收益规模加权）
            if method in ['weighted', 'all']:
                # 使用收益率的绝对值作为权重
                win_weights = winning_trades.abs()
                loss_weights = losing_trades.abs()

                weighted_win_sum = (winning_trades * win_weights).sum()
                weighted_loss_sum = (losing_trades.abs() * loss_weights).sum()

                if weighted_loss_sum > 0:
                    pf_weighted = weighted_win_sum / weighted_loss_sum
                    results['profit_factor_weighted'] = pf_weighted
                else:
                    results['profit_factor_weighted'] = float('inf')

            # 如果只计算单一方法，返回主要结果
            if method != 'all':
                results['profit_factor'] = results.get(f'profit_factor_{method}', 0)

            # 质量指标
            results['confidence_score'] = self._calculate_pf_confidence(winning_trades, losing_trades)

            logger.info(f"盈利因子计算完成: 方法={method}, 样本数={len(returns)}")

        except Exception as e:
            logger.error(f"盈利因子计算失败: {e}")
            # 返回安全的默认值
            results.update({
                'profit_factor_arithmetic': 1.0,
                'profit_factor_geometric': 1.0,
                'profit_factor_weighted': 1.0,
                'confidence_score': 0.0
            })

        return results

    def calculate_sharpe_ratio_enhanced(self,
                                        returns: pd.Series,
                                        risk_free_rate: Optional[float] = None,
                                        frequency: int = None) -> Dict[str, float]:
        """
        计算符合CFA标准的增强Sharpe比率

        Parameters:
        -----------
        returns : pd.Series
            收益率序列
        risk_free_rate : float, optional
            无风险利率（年化），默认使用实例设置
        frequency : int, optional
            年化频率，默认252个交易日

        Returns:
        --------
        Dict[str, float]
            详细的Sharpe比率分析结果

        理论依据:
        --------
        基于CFA Institute标准：
        Sharpe Ratio = (E[R] - Rf) / σ(R)
        其中 E[R] 是期望收益，Rf 是无风险利率，σ(R) 是收益率标准差
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        if frequency is None:
            frequency = self.TRADING_DAYS_PER_YEAR

        # 输入验证
        self._validate_returns_input(returns)

        try:
            # 计算超额收益
            daily_rf_rate = risk_free_rate / frequency
            excess_returns = returns - daily_rf_rate

            # 年化指标
            annualized_return = returns.mean() * frequency
            annualized_excess_return = excess_returns.mean() * frequency
            annualized_volatility = returns.std() * np.sqrt(frequency)

            # Sharpe比率
            if annualized_volatility > 0:
                sharpe_ratio = annualized_excess_return / annualized_volatility
            else:
                sharpe_ratio = 0.0

            # 计算置信区间 (基于统计推断)
            n = len(returns)
            if n > 3:
                # Sharpe比率的标准误
                sharpe_se = np.sqrt((1 + 0.5 * sharpe_ratio**2) / n)
                # 95%置信区间
                confidence_95 = stats.norm.ppf(0.975) * sharpe_se
            else:
                confidence_95 = float('inf')

            results = {
                'sharpe_ratio': sharpe_ratio,
                'annualized_return': annualized_return,
                'annualized_excess_return': annualized_excess_return,
                'annualized_volatility': annualized_volatility,
                'risk_free_rate': risk_free_rate,
                'confidence_interval_95': confidence_95,
                'sample_size': n,
                'frequency': frequency
            }

            # 解释性等级
            if sharpe_ratio > 3.0:
                results['performance_rating'] = 'Exceptional'
            elif sharpe_ratio > 2.0:
                results['performance_rating'] = 'Very Good'
            elif sharpe_ratio > 1.0:
                results['performance_rating'] = 'Good'
            elif sharpe_ratio > 0.5:
                results['performance_rating'] = 'Acceptable'
            else:
                results['performance_rating'] = 'Poor'

            logger.info(f"Sharpe比率计算完成: {sharpe_ratio:.3f}")

        except Exception as e:
            logger.error(f"Sharpe比率计算失败: {e}")
            results = {
                'sharpe_ratio': 0.0,
                'annualized_return': 0.0,
                'annualized_excess_return': 0.0,
                'annualized_volatility': 0.0,
                'performance_rating': 'Unknown'
            }

        return results

    def calculate_maximum_drawdown_precise(self, returns: pd.Series) -> Dict[str, Union[float, pd.Timestamp, int]]:
        """
        精确计算最大回撤（符合CFA标准）

        Parameters:
        -----------
        returns : pd.Series
            收益率序列

        Returns:
        --------
        Dict[str, Union[float, pd.Timestamp, int]]
            详细的回撤分析结果

        理论依据:
        --------
        最大回撤 = max(|Peak - Trough| / Peak)
        其中Peak是历史最高点，Trough是该Peak之后的最低点
        """
        # 输入验证
        self._validate_returns_input(returns)

        try:
            # 计算累计净值曲线
            cumulative_returns = (1 + returns).cumprod()

            # 计算历史最高点（滚动最大值）
            rolling_max = cumulative_returns.expanding().max()

            # 计算回撤序列
            drawdowns = (cumulative_returns - rolling_max) / rolling_max

            # 最大回撤
            max_drawdown = drawdowns.min()
            max_dd_abs = abs(max_drawdown)

            # 回撤期间分析
            max_dd_idx = drawdowns.idxmin()
            peak_idx = rolling_max[:max_dd_idx].idxmax()

            # 寻找回复点
            recovery_idx = None
            if max_dd_idx in cumulative_returns.index:
                peak_value = cumulative_returns[peak_idx]
                post_trough = cumulative_returns[max_dd_idx:]
                recovery_mask = post_trough >= peak_value
                if recovery_mask.any():
                    recovery_idx = post_trough[recovery_mask].index[0]

            # 计算回撤期间长度
            if isinstance(returns.index, pd.DatetimeIndex):
                if recovery_idx is not None:
                    drawdown_duration = (recovery_idx - peak_idx).days
                    recovery_duration = (recovery_idx - max_dd_idx).days
                else:
                    drawdown_duration = (max_dd_idx - peak_idx).days
                    recovery_duration = None
            else:
                # 非日期索引，使用位置计算
                peak_pos = returns.index.get_loc(peak_idx)
                trough_pos = returns.index.get_loc(max_dd_idx)
                drawdown_duration = trough_pos - peak_pos

                if recovery_idx is not None:
                    recovery_pos = returns.index.get_loc(recovery_idx)
                    recovery_duration = recovery_pos - trough_pos
                else:
                    recovery_duration = None

            # 当前回撤
            current_drawdown = abs(drawdowns.iloc[-1])

            # 平均回撤
            negative_drawdowns = drawdowns[drawdowns < 0]
            avg_drawdown = abs(negative_drawdowns.mean()) if len(negative_drawdowns) > 0 else 0

            results = {
                'max_drawdown': max_dd_abs,
                'max_drawdown_pct': max_dd_abs * 100,
                'peak_date': peak_idx,
                'trough_date': max_dd_idx,
                'recovery_date': recovery_idx,
                'drawdown_duration_days': drawdown_duration,
                'recovery_duration_days': recovery_duration,
                'current_drawdown': current_drawdown,
                'current_drawdown_pct': current_drawdown * 100,
                'avg_drawdown': avg_drawdown,
                'avg_drawdown_pct': avg_drawdown * 100,
                'peak_to_trough_return': max_drawdown,
                'num_drawdown_periods': len(negative_drawdowns)
            }

            # 回撤严重程度评级
            if max_dd_abs > 0.5:
                results['severity_rating'] = 'Severe'
            elif max_dd_abs > 0.3:
                results['severity_rating'] = 'High'
            elif max_dd_abs > 0.15:
                results['severity_rating'] = 'Moderate'
            elif max_dd_abs > 0.05:
                results['severity_rating'] = 'Low'
            else:
                results['severity_rating'] = 'Minimal'

            logger.info(f"最大回撤计算完成: {max_dd_abs:.1%}")

        except Exception as e:
            logger.error(f"最大回撤计算失败: {e}")
            results = {
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'severity_rating': 'Unknown'
            }

        return results

    def calculate_conditional_var(self,
                                  returns: pd.Series,
                                  confidence: float = 0.95) -> Dict[str, float]:
        """
        计算条件VaR (CVaR / Expected Shortfall)

        Parameters:
        -----------
        returns : pd.Series
            收益率序列
        confidence : float
            置信度水平，默认95%

        Returns:
        --------
        Dict[str, float]
            CVaR计算结果

        理论依据:
        --------
        CVaR = E[R | R ≤ VaR]
        即超过VaR阈值的期望损失
        """
        # 输入验证
        self._validate_returns_input(returns)

        try:
            alpha = 1 - confidence

            # 计算VaR阈值
            var_threshold = np.percentile(returns, alpha * 100)

            # 计算条件VaR (期望短缺)
            tail_losses = returns[returns <= var_threshold]

            if len(tail_losses) > 0:
                cvar = tail_losses.mean()
                cvar_abs = abs(cvar)
            else:
                cvar = var_threshold
                cvar_abs = abs(var_threshold)

            results = {
                'conditional_var': cvar_abs,
                'conditional_var_pct': cvar_abs * 100,
                'var_threshold': abs(var_threshold),
                'tail_expectation': cvar,
                'tail_observations': len(tail_losses),
                'tail_percentage': len(tail_losses) / len(returns) * 100,
                'confidence': confidence
            }

            logger.info(f"CVaR计算完成: {cvar_abs:.1%} (置信度{confidence:.0%})")

        except Exception as e:
            logger.error(f"CVaR计算失败: {e}")
            results = {
                'conditional_var': 0.0,
                'conditional_var_pct': 0.0,
                'confidence': confidence
            }

        return results

    # 辅助方法
    def _validate_returns_input(self, returns: pd.Series) -> None:
        """验证收益率输入数据"""
        if returns.empty:
            raise ValueError("收益率序列不能为空")

        if returns.isna().sum() > len(returns) * 0.1:
            warnings.warn("数据缺失比例过高(>10%)")

        if abs(returns).max() > 1.0:
            warnings.warn("发现异常大的收益率值(>100%)")

        if len(returns) < 30:
            warnings.warn("样本数量较少(<30)，结果可能不够稳定")

    def _calculate_pf_confidence(self, winning_trades: pd.Series, losing_trades: pd.Series) -> float:
        """计算盈利因子的置信度分数"""
        total_trades = len(winning_trades) + len(losing_trades)

        if total_trades < 30:
            return 0.3  # 样本不足
        elif total_trades < 100:
            return 0.6  # 样本一般
        else:
            return 0.9  # 样本充足

    def _get_fallback_var_results(self) -> Dict[str, Dict]:
        """获取VaR计算失败时的回退结果"""
        return {
            'VaR_95%_1d': {
                'relative_var': 0.02,
                'absolute_var': 0.02,
                'confidence': 0.95,
                'horizon_days': 1,
                'method': 'fallback'
            },
            'metadata': {
                'method': 'fallback',
                'status': 'calculation_failed'
            }
        }

class FinancialMetricsValidator:
    """
    金融指标算法验证框架

    提供与CFA/FRM标准对比验证功能
    """

    def __init__(self):
        self.tolerance = 0.05  # 5%误差容忍度

    def validate_var_calculation(self, calculated_var: float, expected_range: Tuple[float, float]) -> bool:
        """验证VaR计算是否在合理范围内"""
        return expected_range[0] <= calculated_var <= expected_range[1]

    def validate_sharpe_ratio(self, sharpe_ratio: float, returns: pd.Series, risk_free_rate: float) -> Dict[str, bool]:
        """验证Sharpe比率计算的合理性"""
        # 重新计算验证
        excess_return = returns.mean() * 252 - risk_free_rate
        volatility = returns.std() * np.sqrt(252)
        expected_sharpe = excess_return / volatility if volatility > 0 else 0

        error = abs(sharpe_ratio - expected_sharpe) / max(abs(expected_sharpe), 0.001)

        return {
            'calculation_correct': error < self.tolerance,
            'value_reasonable': -5 <= sharpe_ratio <= 10,  # 合理范围
            'error_percentage': error
        }

    def benchmark_against_reference(self, metrics: Dict, reference_metrics: Dict) -> Dict[str, float]:
        """与参考基准（如QuantLib）对比"""
        comparisons = {}

        for key in metrics:
            if key in reference_metrics:
                calculated = metrics[key]
                reference = reference_metrics[key]

                if isinstance(calculated, (int, float)) and isinstance(reference, (int, float)):
                    if reference != 0:
                        error = abs(calculated - reference) / abs(reference)
                        comparisons[key] = error
                    else:
                        comparisons[key] = abs(calculated)

        return comparisons
