import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

class RiskAlertSystem:
    def __init__(self):
        self.alert_history = []
        self.alert_levels = {
            'low': {'threshold': 0.3, 'action': 'monitor'},
            'medium': {'threshold': 0.5, 'action': 'reduce_position'},
            'high': {'threshold': 0.7, 'action': 'stop_trading'},
            'critical': {'threshold': 0.9, 'action': 'emergency_liquidation'}
        }
        self.risk_controls = {
            'monitor': self._monitor_risk,
            'reduce_position': self._reduce_position,
            'stop_trading': self._stop_trading,
            'emergency_liquidation': self._emergency_liquidation
        }

    def check_risk_alerts(self, risk_metrics: Dict) -> List[Dict]:
        """检查风险指标并生成预警"""
        alerts = []

        # 检查市场风险
        market_alerts = self._check_market_risk(
            risk_metrics.get('market_risk', {}))
        alerts.extend(market_alerts)

        # 检查行业风险
        sector_alerts = self._check_sector_risk(
            risk_metrics.get('sector_risk', {}))
        alerts.extend(sector_alerts)

        # 检查流动性风险
        liquidity_alerts = self._check_liquidity_risk(
            risk_metrics.get('liquidity_risk', {}))
        alerts.extend(liquidity_alerts)

        # 检查VaR和ES
        var_alerts = self._check_var_es(
            risk_metrics.get('var', 0), risk_metrics.get('es', 0))
        alerts.extend(var_alerts)

        # 检查相关性风险
        correlation_alerts = self._check_correlation_risk(
            risk_metrics.get('correlation_risk', {}))
        alerts.extend(correlation_alerts)

        # 检查尾部风险
        tail_alerts = self._check_tail_risk(risk_metrics.get('tail_risk', {}))
        alerts.extend(tail_alerts)

        # 执行风险控制措施
        self._execute_risk_controls(alerts)

        # 记录预警历史
        self._record_alerts(alerts)

        return alerts

    def _check_market_risk(self, market_risk: Dict) -> List[Dict]:
        """检查市场风险指标"""
        alerts = []

        # 检查Beta
        if market_risk.get('beta', 0) > 1.5:
            alerts.append({
                'type': 'market_risk',
                'metric': 'beta',
                'value': market_risk['beta'],
                'level': 'high',
                'message': '投资组合Beta值过高，市场风险较大'
            })

        # 检查夏普比率
        if market_risk.get('sharpe_ratio', 0) < 0.5:
            alerts.append({
                'type': 'market_risk',
                'metric': 'sharpe_ratio',
                'value': market_risk['sharpe_ratio'],
                'level': 'medium',
                'message': '夏普比率偏低，风险调整后收益不理想'
            })

        return alerts

    def _check_sector_risk(self, sector_risk: Dict) -> List[Dict]:
        """检查行业风险指标"""
        alerts = []

        # 检查行业集中度
        if sector_risk.get('herfindahl_index', 0) > 0.3:
            alerts.append({
                'type': 'sector_risk',
                'metric': 'herfindahl_index',
                'value': sector_risk['herfindahl_index'],
                'level': 'high',
                'message': '行业集中度过高，分散化不足'
            })

        # 检查单一行业暴露
        for sector, exposure in sector_risk.get('sector_exposure', {}).items():
            if exposure > 0.3:
                alerts.append({
                    'type': 'sector_risk',
                    'metric': 'sector_exposure',
                    'value': exposure,
                    'level': 'medium',
                    'message': f'{sector}行业暴露度过高'
                })

        return alerts

    def _check_liquidity_risk(self, liquidity_risk: Dict) -> List[Dict]:
        """检查流动性风险指标"""
        alerts = []

        # 检查成交量波动率
        if liquidity_risk.get('volume_volatility', 0) > 0.5:
            alerts.append({
                'type': 'liquidity_risk',
                'metric': 'volume_volatility',
                'value': liquidity_risk['volume_volatility'],
                'level': 'medium',
                'message': '成交量波动率过高，流动性风险增加'
            })

        # 检查买卖价差
        if liquidity_risk.get('avg_spread', 0) > 0.01:
            alerts.append({
                'type': 'liquidity_risk',
                'metric': 'avg_spread',
                'value': liquidity_risk['avg_spread'],
                'level': 'high',
                'message': '买卖价差过大，交易成本增加'
            })

        return alerts

    def _check_var_es(self, var: float, es: float) -> List[Dict]:
        """检查VaR和ES指标"""
        alerts = []

        # 检查VaR
        if var < -0.05:
            alerts.append({
                'type': 'var_es',
                'metric': 'var',
                'value': var,
                'level': 'high',
                'message': 'VaR值超过阈值，潜在损失风险较大'
            })

        # 检查ES
        if es < -0.07:
            alerts.append({
                'type': 'var_es',
                'metric': 'es',
                'value': es,
                'level': 'critical',
                'message': '预期损失超过阈值，极端风险较大'
            })

        return alerts

    def _check_correlation_risk(self, correlation_risk: Dict) -> List[Dict]:
        """检查相关性风险指标"""
        alerts = []

        # 检查平均相关性
        if correlation_risk.get('avg_correlation', 0) > 0.7:
            alerts.append({
                'type': 'correlation_risk',
                'metric': 'avg_correlation',
                'value': correlation_risk['avg_correlation'],
                'level': 'high',
                'message': '资产间相关性过高，分散化效果不佳'
            })

        return alerts

    def _check_tail_risk(self, tail_risk: Dict) -> List[Dict]:
        """检查尾部风险指标"""
        alerts = []

        # 检查峰度
        if tail_risk.get('kurtosis', 0) > 3:
            alerts.append({
                'type': 'tail_risk',
                'metric': 'kurtosis',
                'value': tail_risk['kurtosis'],
                'level': 'medium',
                'message': '收益分布峰度过高，尾部风险增加'
            })

        # 检查极端损失概率
        if tail_risk.get('extreme_loss_prob', 0) > 0.1:
            alerts.append({
                'type': 'tail_risk',
                'metric': 'extreme_loss_prob',
                'value': tail_risk['extreme_loss_prob'],
                'level': 'high',
                'message': '极端损失概率过高，需要加强风险控制'
            })

        return alerts

    def _execute_risk_controls(self, alerts: List[Dict]):
        """执行风险控制措施"""
        for alert in alerts:
            level = alert['level']
            action = self.alert_levels[level]['action']
            self.risk_controls[action](alert)

    def _monitor_risk(self, alert: Dict):
        logger.warning(f"风险监控: {alert['message']}")
        from core.events.event_bus import get_event_bus
        get_event_bus().publish('risk.monitor', alert=alert, timestamp=datetime.now())

    def _reduce_position(self, alert: Dict):
        logger.warning(f"触发减仓: {alert}")
        from core.events.event_bus import get_event_bus
        get_event_bus().publish('risk.reduce_position', alert=alert,
                                reduce_ratio=alert.get('reduce_ratio', 0.5),
                                timestamp=datetime.now())

    def _stop_trading(self, alert: Dict):
        logger.critical(f"触发停止交易: {alert}")
        from core.events.event_bus import get_event_bus
        get_event_bus().publish('risk.stop_trading', alert=alert,
                                duration_minutes=alert.get('duration', 30),
                                timestamp=datetime.now())

    def _emergency_liquidation(self, alert: Dict):
        logger.critical(f"触发紧急平仓: {alert}")
        from core.events.event_bus import get_event_bus
        get_event_bus().publish('risk.emergency_liquidation', alert=alert, timestamp=datetime.now())

    def _record_alerts(self, alerts: List[Dict]):
        """记录预警历史"""
        for alert in alerts:
            self.alert_history.append({
                'timestamp': datetime.now(),
                'alert': alert
            })

    def get_alert_history(self, start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None) -> List[Dict]:
        """获取预警历史记录"""
        if start_time and end_time:
            return [record for record in self.alert_history
                    if start_time <= record['timestamp'] <= end_time]
        return self.alert_history

    def analyze_alert_history(self) -> Dict:
        """分析预警历史"""
        if not self.alert_history:
            return {}

        # 统计各类型预警数量
        alert_counts = {}
        for record in self.alert_history:
            alert_type = record['alert']['type']
            alert_counts[alert_type] = alert_counts.get(alert_type, 0) + 1

        # 统计各等级预警数量
        level_counts = {}
        for record in self.alert_history:
            level = record['alert']['level']
            level_counts[level] = level_counts.get(level, 0) + 1

        return {
            'alert_counts': alert_counts,
            'level_counts': level_counts,
            'total_alerts': len(self.alert_history)
        }
