import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime
from loguru import logger

class RiskMetricsCalculator:
    def __init__(self):
        self.cache = {}  # 用于缓存计算结果
        self.alert_history = []  # 存储预警历史记录

    def calculate_market_risk_metrics(self, returns: pd.Series, market_returns: pd.Series) -> Dict:
        """计算市场风险指标"""
        try:
            # 计算Beta
            covariance = np.cov(returns, market_returns)[0, 1]
            market_variance = np.var(market_returns)
            beta = covariance / market_variance if market_variance != 0 else 0

            # 计算Alpha（日化无风险利率）
            trading_days = 252
            risk_free_rate_annual = 0.02
            risk_free_rate = risk_free_rate_annual / trading_days
            alpha = np.mean(returns) - (risk_free_rate + beta *
                                        (np.mean(market_returns) - risk_free_rate))

            # 计算年化夏普比率
            excess_returns = returns - risk_free_rate
            daily_sharpe = np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) != 0 else 0
            sharpe_ratio = daily_sharpe * np.sqrt(trading_days)

            # 计算年化索提诺比率（基于超额收益的下行偏差）
            downside_excess = excess_returns[excess_returns < 0]
            if len(downside_excess) > 0:
                downside_deviation = np.sqrt(np.mean(downside_excess ** 2))
                sortino_ratio = np.mean(excess_returns) / downside_deviation * np.sqrt(trading_days)
            else:
                sortino_ratio = 0.0

            return {
                'beta': beta,
                'alpha': alpha,
                'sharpe_ratio': sharpe_ratio,
                'sortino_ratio': sortino_ratio
            }
        except Exception as e:
            logger.info(f"计算市场风险指标时出错: {str(e)}")
            return {}

    def calculate_sector_exposure(self, portfolio: Dict[str, float], sector_data: Dict[str, str]) -> Dict:
        """计算行业和板块风险暴露度"""
        try:
            sector_exposure = {}
            for stock, weight in portfolio.items():
                sector = sector_data.get(stock, 'Unknown')
                sector_exposure[sector] = sector_exposure.get(
                    sector, 0) + weight

            # 计算集中度
            herfindahl_index = sum(w**2 for w in sector_exposure.values())

            return {
                'sector_exposure': sector_exposure,
                'herfindahl_index': herfindahl_index,
                'stock_sector_map': sector_data
            }
        except Exception as e:
            logger.info(f"计算行业暴露度时出错: {str(e)}")
            return {}

    def calculate_liquidity_risk(self, volume_data: pd.Series, price_data: pd.Series) -> Dict:
        """计算流动性风险指标"""
        try:
            # 计算平均成交量
            avg_volume = volume_data.mean()

            # 计算成交量波动率
            volume_volatility = volume_data.std() / avg_volume if avg_volume != 0 else 0

            # 计算买卖价差
            bid_ask_spread = (
                price_data['high'] - price_data['low']) / price_data['close']
            avg_spread = bid_ask_spread.mean()

            # 计算流动性比率
            liquidity_ratio = volume_data * \
                price_data['close'] / price_data['close'].sum()

            return {
                'avg_volume': avg_volume,
                'volume_volatility': volume_volatility,
                'avg_spread': avg_spread,
                'liquidity_ratio': liquidity_ratio
            }
        except Exception as e:
            logger.info(f"计算流动性风险指标时出错: {str(e)}")
            return {}

    def calculate_value_at_risk(self, returns: pd.Series, confidence_level: float = 0.95) -> float:
        """计算VaR"""
        try:
            return np.percentile(returns, (1 - confidence_level) * 100)
        except Exception as e:
            logger.info(f"计算VaR时出错: {str(e)}")
            return 0

    def calculate_expected_shortfall(self, returns: pd.Series, confidence_level: float = 0.95) -> float:
        """计算预期损失(ES)"""
        try:
            var = self.calculate_value_at_risk(returns, confidence_level)
            return returns[returns <= var].mean()
        except Exception as e:
            logger.info(f"计算ES时出错: {str(e)}")
            return 0

    def calculate_conditional_var(self, returns: pd.Series, confidence_level: float = 0.95) -> float:
        """计算条件在险价值(CVaR) - calculate_expected_shortfall的别名"""
        return self.calculate_expected_shortfall(returns, confidence_level)

    def calculate_correlation_risk(self, returns_matrix: pd.DataFrame) -> Dict:
        """计算相关性风险"""
        try:
            correlation_matrix = returns_matrix.corr()
            avg_correlation = correlation_matrix.values[np.triu_indices_from(
                correlation_matrix.values, k=1)].mean()

            return {
                'correlation_matrix': correlation_matrix,
                'avg_correlation': avg_correlation
            }
        except Exception as e:
            logger.info(f"计算相关性风险时出错: {str(e)}")
            return {}

    def calculate_tail_risk(self, returns: pd.Series) -> Dict:
        """计算尾部风险"""
        try:
            # 计算偏度
            skewness = returns.skew()

            # 计算峰度
            kurtosis = returns.kurtosis()

            # 计算极端损失概率
            extreme_loss_prob = len(
                returns[returns < returns.quantile(0.05)]) / len(returns)

            return {
                'skewness': skewness,
                'kurtosis': kurtosis,
                'extreme_loss_prob': extreme_loss_prob
            }
        except Exception as e:
            logger.info(f"计算尾部风险时出错: {str(e)}")
            return {}

    def calculate_risk_metrics(self, data: Dict) -> Dict:
        """计算所有风险指标"""
        try:
            # 检查缓存
            cache_key = str(data)
            if cache_key in self.cache:
                return self.cache[cache_key]

            # 计算各项风险指标
            market_risk = self.calculate_market_risk_metrics(
                data['returns'], data['market_returns'])
            sector_risk = self.calculate_sector_exposure(
                data['portfolio'], data['sector_data'])
            liquidity_risk = self.calculate_liquidity_risk(
                data['volume'], data['price'])
            var = self.calculate_value_at_risk(data['returns'])
            es = self.calculate_expected_shortfall(data['returns'])
            correlation_risk = self.calculate_correlation_risk(
                data['returns_matrix'])
            tail_risk = self.calculate_tail_risk(data['returns'])

            # 合并所有风险指标
            risk_metrics = {
                'market_risk': market_risk,
                'sector_risk': sector_risk,
                'liquidity_risk': liquidity_risk,
                'var': var,
                'es': es,
                'correlation_risk': correlation_risk,
                'tail_risk': tail_risk
            }

            # 更新缓存
            self.cache[cache_key] = risk_metrics

            return risk_metrics
        except Exception as e:
            logger.info(f"计算风险指标时出错: {str(e)}")
            return {}
