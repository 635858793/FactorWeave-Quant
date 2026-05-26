import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger

class RiskControlStrategy:
    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}
        self.risk_budget = {}  # 风险预算分配
        self.position_limits = {}  # 持仓限制
        self.hedge_positions = {}  # 对冲头寸
        self.stop_loss_levels = {}  # 止损水平
        self.risk_metrics_history = []  # 风险指标历史

    def allocate_risk_budget(self, portfolio: Dict[str, float],
                             risk_metrics: Dict) -> Dict[str, float]:
        """动态分配风险预算"""
        try:
            # 获取当前风险指标
            market_risk = risk_metrics.get('market_risk', {})
            sector_risk = risk_metrics.get('sector_risk', {})
            liquidity_risk = risk_metrics.get('liquidity_risk', {})

            # 计算各资产的风险贡献
            risk_contributions = {}
            for asset, weight in portfolio.items():
                # 计算市场风险贡献
                beta = market_risk.get('beta', 1.0)
                market_contribution = weight * beta

                # 计算行业风险贡献
                stock_sector_map = sector_risk.get('stock_sector_map', {})
                sector_name = stock_sector_map.get(asset, 'Unknown')
                sector_exposure_val = sector_risk.get('sector_exposure', {}).get(sector_name, 0)
                sector_contribution = weight * sector_exposure_val

                # 计算流动性风险贡献
                liquidity = liquidity_risk.get(
                    'liquidity_ratio', {}).get(asset, 1.0)
                liquidity_contribution = weight * (1 / liquidity)

                # 综合风险贡献
                total_contribution = (
                    market_contribution * 0.4 +  # 市场风险权重
                    sector_contribution * 0.3 +  # 行业风险权重
                    liquidity_contribution * 0.3  # 流动性风险权重
                )

                risk_contributions[asset] = total_contribution

            # 归一化风险预算
            total_contribution = sum(risk_contributions.values())
            if total_contribution > 0:
                risk_budget = {
                    asset: contribution / total_contribution
                    for asset, contribution in risk_contributions.items()
                }
            else:
                risk_budget = {asset: 1.0/len(portfolio)
                               for asset in portfolio}

            self.risk_budget = risk_budget
            return risk_budget

        except Exception as e:
            logger.error(f"分配风险预算时出错: {str(e)}")
            return {}

    def calculate_position_limits(self, risk_metrics: Dict) -> Dict[str, float]:
        """计算持仓限制"""
        try:
            # 获取风险指标
            var = risk_metrics.get('var', 0)
            es = risk_metrics.get('es', 0)
            correlation_risk = risk_metrics.get('correlation_risk', {})

            # 计算基础持仓限制
            base_limit = 1.0 - abs(var)  # 基于VaR的持仓限制

            # 根据ES调整
            if es < -0.05:
                base_limit *= 0.8  # 降低20%持仓

            # 根据相关性风险调整
            avg_correlation = correlation_risk.get('avg_correlation', 0)
            if avg_correlation > 0.7:
                base_limit *= 0.9  # 降低10%持仓

            # 设置各资产持仓限制
            position_limits = {}
            for asset in self.risk_budget:
                # 考虑风险预算分配
                asset_limit = base_limit * self.risk_budget[asset]

                # 考虑流动性风险
                liquidity = risk_metrics.get('liquidity_risk', {}).get(
                    'liquidity_ratio', {}).get(asset, 1.0)
                asset_limit *= min(1.0, liquidity)

                position_limits[asset] = asset_limit

            self.position_limits = position_limits
            return position_limits

        except Exception as e:
            logger.error(f"计算持仓限制时出错: {str(e)}")
            return {}

    def calculate_stop_loss(self, asset: str, price: float,
                            position: float, risk_metrics: Dict) -> float:
        """计算动态止损水平"""
        try:
            market_risk = risk_metrics.get('market_risk', {})
            volatility = market_risk.get('volatility', 0.2)
            beta = market_risk.get('beta', 1.0)

            if position > 0:
                base_stop = max(price * (1 - volatility * beta), price * 0.80)
            elif position < 0:
                base_stop = min(price * (1 + volatility * beta), price * 1.20)
            else:
                base_stop = price

            position_ratio = abs(position) / self.position_limits.get(asset, 1.0)
            if position_ratio > 0.8:
                base_stop *= 0.95

            market_regime = self._detect_market_regime(risk_metrics)
            if market_regime == 'bear':
                base_stop *= 0.95
            elif market_regime == 'bull':
                base_stop *= 1.05

            self.stop_loss_levels[asset] = base_stop

            return base_stop

        except Exception as e:
            logger.error(f"计算止损水平时出错: {str(e)}")
            return price * 0.9  # 默认10%止损

    def check_stop_loss_trigger(self, asset: str, position: float,
                                 entry_price: float, current_price: float,
                                 current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        检查是否触发止损（供回测与实盘共同使用）

        Args:
            asset: 资产标识
            position: 当前持仓（正=多头，负=空头）
            entry_price: 入场价格
            current_price: 当前价格
            current_time: 当前时间（可选）

        Returns:
            Tuple[bool, str]: (是否触发止损, 触发原因)
        """
        try:
            if position == 0 or entry_price <= 0 or current_price <= 0:
                return False, ""

            stop_price = self.stop_loss_levels.get(asset)
            if stop_price is None or stop_price <= 0:
                return False, ""

            if position > 0:
                if current_price <= stop_price:
                    loss_pct = (current_price - entry_price) / entry_price
                    return True, f"多头止损触发: 当前价{current_price:.4f} <= 止损价{stop_price:.4f} ({loss_pct:.2%})"
            elif position < 0:
                if current_price >= stop_price:
                    loss_pct = (entry_price - current_price) / entry_price
                    return True, f"空头止损触发: 当前价{current_price:.4f} >= 止损价{stop_price:.4f} ({loss_pct:.2%})"

            return False, ""

        except Exception as e:
            logger.error(f"检查止损触发时出错: {str(e)}")
            return False, f"止损检查异常: {str(e)}"

    def setup_hedge(self, asset: str, position: float,
                    risk_metrics: Dict) -> Optional[Tuple[str, float]]:
        """设置对冲头寸"""
        try:
            # 检查是否需要对冲
            if not self._need_hedge(asset, position, risk_metrics):
                return None

            # 选择对冲工具
            hedge_asset = self._select_hedge_asset(asset, risk_metrics)
            if not hedge_asset:
                return None

            # 计算对冲比例
            hedge_ratio = self._calculate_hedge_ratio(
                asset, hedge_asset, risk_metrics)

            # 计算对冲头寸
            hedge_position = -position * hedge_ratio

            # 记录对冲头寸
            self.hedge_positions[asset] = (hedge_asset, hedge_position)

            return (hedge_asset, hedge_position)

        except Exception as e:
            logger.error(f"设置对冲头寸时出错: {str(e)}")
            return None

    def _detect_market_regime(self, risk_metrics: Dict) -> str:
        """检测市场状态"""
        try:
            market_risk = risk_metrics.get('market_risk', {})
            beta = market_risk.get('beta', 1.0)
            volatility = market_risk.get('volatility', 0.2)

            if beta > 1.2 and volatility > 0.25:
                return 'bear'
            elif beta < 0.8 and volatility < 0.15:
                return 'bull'
            else:
                return 'neutral'

        except Exception as e:
            logger.error(f"检测市场状态时出错: {str(e)}")
            return 'neutral'

    def _need_hedge(self, asset: str, position: float,
                    risk_metrics: Dict) -> bool:
        """判断是否需要对冲"""
        try:
            # 检查持仓规模
            if position < self.position_limits.get(asset, 1.0) * 0.5:
                return False

            # 检查风险指标
            var = risk_metrics.get('var', 0)
            if var > -0.03:  # VaR风险较小
                return False

            # 检查市场状态
            market_regime = self._detect_market_regime(risk_metrics)
            if market_regime == 'bull':
                return False

            return True

        except Exception as e:
            logger.error(f"判断是否需要对冲时出错: {str(e)}")
            return False

    def _select_hedge_asset(self, asset: str, risk_metrics: Dict) -> Optional[str]:
        """选择对冲工具"""
        try:
            # 获取相关性矩阵
            correlation_matrix = risk_metrics.get('correlation_risk', {}).get(
                'correlation_matrix', pd.DataFrame())

            if asset not in correlation_matrix.index:
                return None

            # 寻找负相关性最高的资产
            correlations = correlation_matrix[asset]
            hedge_asset = correlations[correlations < -0.7].index[0] if len(
                correlations[correlations < -0.7]) > 0 else None

            return hedge_asset

        except Exception as e:
            logger.error(f"选择对冲工具时出错: {str(e)}")
            return None

    def _calculate_hedge_ratio(self, asset: str, hedge_asset: str,
                               risk_metrics: Dict) -> float:
        """计算对冲比例"""
        try:
            # 获取相关性
            correlation_matrix = risk_metrics.get('correlation_risk', {}).get(
                'correlation_matrix', pd.DataFrame())
            correlation = correlation_matrix.loc[asset, hedge_asset]

            # 获取波动率
            market_risk = risk_metrics.get('market_risk', {})
            asset_vol = market_risk.get('volatility', {}).get(asset, 0.2)
            hedge_vol = market_risk.get('volatility', {}).get(hedge_asset, 0.2)

            # 计算最优对冲比例
            hedge_ratio = (correlation * asset_vol) / hedge_vol

            return min(abs(hedge_ratio), 1.0)  # 限制最大对冲比例为1

        except Exception as e:
            logger.error(f"计算对冲比例时出错: {str(e)}")
            return 0.5  # 默认50%对冲

    def update_risk_metrics_history(self, risk_metrics: Dict):
        """更新风险指标历史"""
        try:
            self.risk_metrics_history.append({
                'timestamp': datetime.now(),
                'metrics': risk_metrics
            })

            # 保留最近100条记录
            if len(self.risk_metrics_history) > 100:
                self.risk_metrics_history.pop(0)

        except Exception as e:
            logger.error(f"更新风险指标历史时出错: {str(e)}")

    def get_risk_metrics_history(self, start_time: Optional[datetime] = None,
                                 end_time: Optional[datetime] = None) -> List[Dict]:
        """获取风险指标历史"""
        try:
            if start_time and end_time:
                return [record for record in self.risk_metrics_history
                        if start_time <= record['timestamp'] <= end_time]
            return self.risk_metrics_history

        except Exception as e:
            logger.error(f"获取风险指标历史时出错: {str(e)}")
            return []

class RiskMonitor:
    """风险监控和预警系统"""

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}
        self.alert_levels = {
            'low': 0.3,    # 低风险阈值
            'medium': 0.5,  # 中风险阈值
            'high': 0.7,   # 高风险阈值
            'critical': 0.9  # 严重风险阈值
        }
        self.alert_history = []  # 预警历史记录
        self.risk_snapshots = []  # 风险快照历史

    def monitor_risk(self, portfolio: Dict[str, float],
                     risk_metrics: Dict) -> List[Dict]:
        """实时监控风险并生成预警"""
        try:
            alerts = []

            # 1. 监控市场风险
            market_alerts = self._monitor_market_risk(risk_metrics)
            alerts.extend(market_alerts)

            # 2. 监控行业风险
            sector_alerts = self._monitor_sector_risk(risk_metrics)
            alerts.extend(sector_alerts)

            # 3. 监控流动性风险
            liquidity_alerts = self._monitor_liquidity_risk(risk_metrics)
            alerts.extend(liquidity_alerts)

            # 4. 监控组合风险
            portfolio_alerts = self._monitor_portfolio_risk(
                portfolio, risk_metrics)
            alerts.extend(portfolio_alerts)

            # 5. 监控止损风险
            stop_loss_alerts = self._monitor_stop_loss(risk_metrics)
            alerts.extend(stop_loss_alerts)

            # 6. 监控对冲风险
            hedge_alerts = self._monitor_hedge_risk(risk_metrics)
            alerts.extend(hedge_alerts)

            # 记录预警
            if alerts:
                self._record_alerts(alerts)

            # 保存风险快照
            self._save_risk_snapshot(portfolio, risk_metrics, alerts)

            return alerts

        except Exception as e:
            logger.error(f"风险监控时出错: {str(e)}")
            return []

    def _monitor_market_risk(self, risk_metrics: Dict) -> List[Dict]:
        """监控市场风险"""
        alerts = []
        market_risk = risk_metrics.get('market_risk', {})

        # 检查波动率
        volatility = market_risk.get('volatility', 0)
        if volatility > self.alert_levels['high']:
            alerts.append({
                'type': 'market_risk',
                'level': 'high',
                'metric': 'volatility',
                'value': volatility,
                'message': f'市场波动率过高: {volatility:.2%}'
            })

        # 检查Beta
        beta = market_risk.get('beta', 1.0)
        if abs(beta - 1.0) > 0.5:
            alerts.append({
                'type': 'market_risk',
                'level': 'medium',
                'metric': 'beta',
                'value': beta,
                'message': f'Beta偏离过大: {beta:.3f}'
            })

        return alerts

    def _monitor_sector_risk(self, risk_metrics: Dict) -> List[Dict]:
        """监控行业风险"""
        alerts = []
        sector_risk = risk_metrics.get('sector_risk', {})

        # 检查行业集中度
        sector_exposure = sector_risk.get('sector_exposure', {})
        for sector, exposure in sector_exposure.items():
            if exposure > self.alert_levels['medium']:
                alerts.append({
                    'type': 'sector_risk',
                    'level': 'medium',
                    'metric': 'sector_exposure',
                    'value': exposure,
                    'message': f'行业集中度过高: {sector} {exposure:.2%}'
                })

        return alerts

    def _monitor_liquidity_risk(self, risk_metrics: Dict) -> List[Dict]:
        """监控流动性风险"""
        alerts = []
        liquidity_risk = risk_metrics.get('liquidity_risk', {})

        # 检查流动性比率
        liquidity_ratio = liquidity_risk.get('liquidity_ratio', {})
        for asset, ratio in liquidity_ratio.items():
            if ratio < 0.1:  # 流动性过低
                alerts.append({
                    'type': 'liquidity_risk',
                    'level': 'high',
                    'metric': 'liquidity_ratio',
                    'value': ratio,
                    'message': f'流动性风险: {asset} 流动性比率 {ratio:.2%}'
                })

        return alerts

    def _monitor_portfolio_risk(self, portfolio: Dict[str, float],
                                risk_metrics: Dict) -> List[Dict]:
        """监控组合风险"""
        alerts = []

        # 检查VaR
        var = risk_metrics.get('var', 0)
        if var < -0.05:  # VaR超过5%
            alerts.append({
                'type': 'portfolio_risk',
                'level': 'high',
                'metric': 'var',
                'value': var,
                'message': f'组合VaR风险过高: {var:.2%}'
            })

        # 检查ES
        es = risk_metrics.get('es', 0)
        if es < -0.07:  # ES超过7%
            alerts.append({
                'type': 'portfolio_risk',
                'level': 'critical',
                'metric': 'es',
                'value': es,
                'message': f'组合ES风险过高: {es:.2%}'
            })

        return alerts

    def _monitor_stop_loss(self, risk_metrics: Dict) -> List[Dict]:
        """监控止损风险"""
        alerts = []
        stop_loss_levels = risk_metrics.get('stop_loss_levels', {})

        for asset, stop_price in stop_loss_levels.items():
            current_price = risk_metrics.get(
                'current_prices', {}).get(asset, 0)
            if current_price > 0:
                distance = (current_price - stop_price) / current_price
                if distance < 0.02:  # 接近止损线
                    alerts.append({
                        'type': 'stop_loss_risk',
                        'level': 'high',
                        'metric': 'stop_loss_distance',
                        'value': distance,
                        'message': f'接近止损线: {asset} 距离 {distance:.2%}'
                    })

        return alerts

    def _monitor_hedge_risk(self, risk_metrics: Dict) -> List[Dict]:
        """监控对冲风险"""
        alerts = []
        hedge_positions = risk_metrics.get('hedge_positions', {})

        for asset, (hedge_asset, ratio) in hedge_positions.items():
            # 检查对冲比例
            if abs(ratio) > 1.0:
                alerts.append({
                    'type': 'hedge_risk',
                    'level': 'medium',
                    'metric': 'hedge_ratio',
                    'value': ratio,
                    'message': f'对冲比例异常: {asset} 对冲 {hedge_asset} 比例 {ratio:.3f}'
                })

        return alerts

    def _record_alerts(self, alerts: List[Dict]):
        """记录预警信息"""
        timestamp = datetime.now()
        for alert in alerts:
            alert['timestamp'] = timestamp
            self.alert_history.append(alert)

        # 保留最近1000条预警记录
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

    def _save_risk_snapshot(self, portfolio: Dict[str, float],
                            risk_metrics: Dict, alerts: List[Dict]):
        """保存风险快照"""
        snapshot = {
            'timestamp': datetime.now(),
            'portfolio': portfolio,
            'risk_metrics': risk_metrics,
            'alerts': alerts
        }
        self.risk_snapshots.append(snapshot)

        # 保留最近100个快照
        if len(self.risk_snapshots) > 100:
            self.risk_snapshots.pop(0)

    def get_alert_history(self, start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None) -> List[Dict]:
        """获取预警历史"""
        if start_time and end_time:
            return [alert for alert in self.alert_history
                    if start_time <= alert['timestamp'] <= end_time]
        return self.alert_history

    def get_risk_snapshots(self, start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> List[Dict]:
        """获取风险快照历史"""
        if start_time and end_time:
            return [snapshot for snapshot in self.risk_snapshots
                    if start_time <= snapshot['timestamp'] <= end_time]
        return self.risk_snapshots

    def get_risk_metrics(self) -> dict:
        """获取当前风险指标，桥接professional_risk_metrics的计算结果"""
        try:
            from core.performance.professional_risk_metrics import calculate_risk_metrics
            if hasattr(self, '_position_records') and self._position_records:
                returns = pd.Series([p.get('daily_return', 0) for p in self._position_records])
                return calculate_risk_metrics(returns=returns) if len(returns) > 0 else self._default_metrics()
        except ImportError:
            pass
        return self._default_metrics()

    def _default_metrics(self) -> dict:
        return {
            'volatility': 0.0, 'beta': 0.0, 'var_95': 0.0, 'var_99': 0.0,
            'cvar_95': 0.0, 'max_drawdown': 0.0, 'herfindahl_index': 0.0,
            'sector_concentration': 0.0, 'sharpe_ratio': 0.0, 'sortino_ratio': 0.0
        }

class RiskReportGenerator:
    """风险报告生成器"""

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}

    def generate_report(self, portfolio: Dict[str, float],
                        risk_metrics: Dict,
                        risk_monitor: RiskMonitor,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None) -> Dict:
        """生成风险分析报告"""
        try:
            report = {
                'summary': self._generate_summary(portfolio, risk_metrics),
                'market_risk': self._analyze_market_risk(risk_metrics),
                'sector_risk': self._analyze_sector_risk(risk_metrics),
                'liquidity_risk': self._analyze_liquidity_risk(risk_metrics),
                'portfolio_risk': self._analyze_portfolio_risk(portfolio, risk_metrics),
                'stop_loss_analysis': self._analyze_stop_loss(risk_metrics),
                'hedge_analysis': self._analyze_hedge(risk_metrics),
                'alert_analysis': self._analyze_alerts(risk_monitor, start_time, end_time),
                'recommendations': self._generate_recommendations(portfolio, risk_metrics)
            }

            return report

        except Exception as e:
            logger.error(f"生成风险报告时出错: {str(e)}")
            return {}

    def _generate_summary(self, portfolio: Dict[str, float],
                          risk_metrics: Dict) -> Dict:
        """生成风险摘要"""
        summary = {
            'total_risk_score': self._calculate_total_risk_score(risk_metrics),
            'key_risk_indicators': self._get_key_risk_indicators(risk_metrics),
            'portfolio_concentration': self._calculate_portfolio_concentration(portfolio),
            'risk_trend': self._analyze_risk_trend(risk_metrics)
        }
        return summary

    def _analyze_market_risk(self, risk_metrics: Dict) -> Dict:
        """分析市场风险"""
        market_risk = risk_metrics.get('market_risk', {})
        analysis = {
            'volatility_analysis': {
                'current': market_risk.get('volatility', 0),
                'historical_avg': market_risk.get('historical_volatility', 0),
                'trend': self._analyze_metric_trend('volatility', market_risk)
            },
            'beta_analysis': {
                'current': market_risk.get('beta', 1.0),
                'historical_avg': market_risk.get('historical_beta', 1.0),
                'trend': self._analyze_metric_trend('beta', market_risk)
            },
            'correlation_analysis': self._analyze_market_correlations(risk_metrics)
        }
        return analysis

    def _analyze_sector_risk(self, risk_metrics: Dict) -> Dict:
        """分析行业风险"""
        sector_risk = risk_metrics.get('sector_risk', {})
        analysis = {
            'sector_exposure': sector_risk.get('sector_exposure', {}),
            'sector_concentration': self._calculate_sector_concentration(sector_risk),
            'sector_correlation': self._analyze_sector_correlations(sector_risk)
        }
        return analysis

    def _analyze_liquidity_risk(self, risk_metrics: Dict) -> Dict:
        """分析流动性风险"""
        liquidity_risk = risk_metrics.get('liquidity_risk', {})
        analysis = {
            'liquidity_ratios': liquidity_risk.get('liquidity_ratio', {}),
            'volume_analysis': self._analyze_volume_metrics(liquidity_risk),
            'bid_ask_spread': self._analyze_bid_ask_spread(liquidity_risk)
        }
        return analysis

    def _analyze_portfolio_risk(self, portfolio: Dict[str, float],
                                risk_metrics: Dict) -> Dict:
        """分析组合风险"""
        analysis = {
            'var_analysis': {
                'current': risk_metrics.get('var', 0),
                'historical': risk_metrics.get('historical_var', []),
                'confidence_level': risk_metrics.get('var_confidence', 0.95)
            },
            'es_analysis': {
                'current': risk_metrics.get('es', 0),
                'historical': risk_metrics.get('historical_es', []),
                'confidence_level': risk_metrics.get('es_confidence', 0.95)
            },
            'drawdown_analysis': self._analyze_drawdown(risk_metrics),
            'correlation_matrix': self._analyze_portfolio_correlations(portfolio, risk_metrics)
        }
        return analysis

    def _analyze_stop_loss(self, risk_metrics: Dict) -> Dict:
        """分析止损情况"""
        stop_loss_levels = risk_metrics.get('stop_loss_levels', {})
        analysis = {
            'current_stop_losses': stop_loss_levels,
            'stop_loss_effectiveness': self._analyze_stop_loss_effectiveness(risk_metrics),
            'stop_loss_adjustments': self._analyze_stop_loss_adjustments(risk_metrics)
        }
        return analysis

    def _analyze_hedge(self, risk_metrics: Dict) -> Dict:
        """分析对冲情况"""
        hedge_positions = risk_metrics.get('hedge_positions', {})
        analysis = {
            'current_hedges': hedge_positions,
            'hedge_effectiveness': self._analyze_hedge_effectiveness(risk_metrics),
            'hedge_costs': self._analyze_hedge_costs(risk_metrics)
        }
        return analysis

    def _analyze_alerts(self, risk_monitor: RiskMonitor,
                        start_time: Optional[datetime],
                        end_time: Optional[datetime]) -> Dict:
        """分析预警情况"""
        alerts = risk_monitor.get_alert_history(start_time, end_time)
        analysis = {
            'alert_summary': self._summarize_alerts(alerts),
            'alert_trends': self._analyze_alert_trends(alerts),
            'alert_categories': self._categorize_alerts(alerts)
        }
        return analysis

    def _generate_recommendations(self, portfolio: Dict[str, float],
                                  risk_metrics: Dict) -> List[Dict]:
        """生成风险控制建议"""
        recommendations = []

        # 1. 基于市场风险的建议
        market_recommendations = self._generate_market_recommendations(
            risk_metrics)
        recommendations.extend(market_recommendations)

        # 2. 基于行业风险的建议
        sector_recommendations = self._generate_sector_recommendations(
            risk_metrics)
        recommendations.extend(sector_recommendations)

        # 3. 基于流动性风险的建议
        liquidity_recommendations = self._generate_liquidity_recommendations(
            risk_metrics)
        recommendations.extend(liquidity_recommendations)

        # 4. 基于组合风险的建议
        portfolio_recommendations = self._generate_portfolio_recommendations(
            portfolio, risk_metrics)
        recommendations.extend(portfolio_recommendations)

        return recommendations

    def _calculate_total_risk_score(self, risk_metrics: Dict) -> float:
        """计算总体风险分数"""
        try:
            # 获取各项风险指标
            market_risk = risk_metrics.get('market_risk', {})
            sector_risk = risk_metrics.get('sector_risk', {})
            liquidity_risk = risk_metrics.get('liquidity_risk', {})
            portfolio_risk = risk_metrics.get('portfolio_risk', {})

            # 计算加权风险分数
            weights = {
                'market': 0.3,
                'sector': 0.2,
                'liquidity': 0.2,
                'portfolio': 0.3
            }

            score = (
                weights['market'] * market_risk.get('risk_score', 0) +
                weights['sector'] * sector_risk.get('risk_score', 0) +
                weights['liquidity'] * liquidity_risk.get('risk_score', 0) +
                weights['portfolio'] * portfolio_risk.get('risk_score', 0)
            )

            return min(max(score, 0), 1)  # 归一化到[0,1]区间

        except Exception as e:
            logger.error(f"计算总体风险分数时出错: {str(e)}")
            return 0.5

    def _get_key_risk_indicators(self, risk_metrics: Dict) -> List[Dict]:
        """获取关键风险指标"""
        indicators = []

        # 市场风险指标
        market_risk = risk_metrics.get('market_risk', {})
        indicators.append({
            'name': '市场波动率',
            'value': market_risk.get('volatility', 0),
            'trend': self._analyze_metric_trend('volatility', market_risk)
        })

        # 组合风险指标
        indicators.append({
            'name': 'VaR',
            'value': risk_metrics.get('var', 0),
            'trend': self._analyze_metric_trend('var', risk_metrics)
        })

        # 流动性风险指标
        liquidity_risk = risk_metrics.get('liquidity_risk', {})
        indicators.append({
            'name': '平均流动性比率',
            'value': np.mean(list(liquidity_risk.get('liquidity_ratio', {}).values())),
            'trend': self._analyze_metric_trend('liquidity_ratio', liquidity_risk)
        })

        return indicators

    def _calculate_portfolio_concentration(self, portfolio: Dict[str, float]) -> float:
        """计算组合集中度"""
        try:
            weights = np.array(list(portfolio.values()))
            hhi = np.sum(weights ** 2)  # Herfindahl-Hirschman Index
            return hhi
        except Exception as e:
            logger.error(f"计算组合集中度时出错: {str(e)}")
            return 0

    def _analyze_risk_trend(self, risk_metrics: Dict) -> str:
        """分析风险趋势"""
        try:
            # 获取历史风险指标
            historical_metrics = risk_metrics.get('historical_metrics', [])
            if len(historical_metrics) < 2:
                return "stable"

            # 计算最近的风险变化
            recent_change = historical_metrics[-1] - historical_metrics[-2]

            if recent_change > 0.1:
                return "increasing"
            elif recent_change < -0.1:
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"分析风险趋势时出错: {str(e)}")
            return "unknown"

    def _analyze_metric_trend(self, metric_name: str, metrics: Dict) -> str:
        """分析指标趋势"""
        try:
            historical_values = metrics.get(f'historical_{metric_name}', [])
            if len(historical_values) < 2:
                return "stable"

            recent_change = historical_values[-1] - historical_values[-2]

            if recent_change > 0:
                return "increasing"
            elif recent_change < 0:
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"分析指标趋势时出错: {str(e)}")
            return "unknown"

    def _summarize_alerts(self, alerts: List[Dict]) -> Dict:
        """汇总预警信息"""
        summary = {
            'total_alerts': len(alerts),
            'alert_by_level': {},
            'alert_by_type': {}
        }

        # 按级别统计
        for alert in alerts:
            level = alert.get('level', 'unknown')
            summary['alert_by_level'][level] = summary['alert_by_level'].get(
                level, 0) + 1

            # 按类型统计
            alert_type = alert.get('type', 'unknown')
            summary['alert_by_type'][alert_type] = summary['alert_by_type'].get(
                alert_type, 0) + 1

        return summary

    def _analyze_alert_trends(self, alerts: List[Dict]) -> Dict:
        """分析预警趋势"""
        trends = {
            'alert_frequency': self._calculate_alert_frequency(alerts),
            'alert_severity': self._calculate_alert_severity(alerts),
            'alert_patterns': self._identify_alert_patterns(alerts)
        }
        return trends

    def _categorize_alerts(self, alerts: List[Dict]) -> Dict:
        """分类预警信息"""
        categories = {
            'market_risk': [],
            'sector_risk': [],
            'liquidity_risk': [],
            'portfolio_risk': [],
            'stop_loss_risk': [],
            'hedge_risk': []
        }

        for alert in alerts:
            alert_type = alert.get('type', 'unknown')
            if alert_type in categories:
                categories[alert_type].append(alert)

        return categories
