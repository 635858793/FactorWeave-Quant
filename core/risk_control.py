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
        self.take_profit_levels = {}  # 止盈水平 (R270: 对称于止损)
        self.risk_metrics_history = []  # 风险指标历史

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

    def calculate_take_profit(self, asset: str, price: float,
                              position: float, risk_metrics: Dict) -> float:
        """计算动态止盈水平 (R270: 对称于 calculate_stop_loss)"""
        try:
            market_risk = risk_metrics.get('market_risk', {})
            volatility = market_risk.get('volatility', 0.2)
            beta = market_risk.get('beta', 1.0)

            if position > 0:
                base_tp = min(price * (1 + volatility * beta), price * 1.20)
            elif position < 0:
                base_tp = max(price * (1 - volatility * beta), price * 0.80)
            else:
                base_tp = price

            position_ratio = abs(position) / self.position_limits.get(asset, 1.0)
            if position_ratio > 0.8:
                base_tp *= 1.05

            market_regime = self._detect_market_regime(risk_metrics)
            if market_regime == 'bear':
                base_tp *= 0.95
            elif market_regime == 'bull':
                base_tp *= 1.05

            self.take_profit_levels[asset] = base_tp

            return base_tp

        except Exception as e:
            logger.error(f"计算止盈水平时出错: {str(e)}")
            return price * 1.1  # 默认10%止盈

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
                # R269-D3: 防御兜底 —— 无填充止损水平时按固定比例降级
                # (多头 -5% / 空头 +5%), 消除"空 level 恒放行"空转 (原 :163-165 直接放行)。
                # 注: 动态止损价由 order_executor._fill_stop_loss_level 正常路径填充。
                stop_price = entry_price * (1 - 0.05) if position > 0 else entry_price * (1 + 0.05)

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

    def check_take_profit_trigger(self, asset: str, position: float,
                                  entry_price: float, current_price: float,
                                  current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        检查是否触发止盈 (R270: 对称于 check_stop_loss_trigger)

        语义: 已有持仓时, 现价已达止盈目标价 → 应止盈出场而非继续追价开仓,
        触发则拒绝该订单。无填充止盈水平时按固定比例兜底 (+5%/-5%)。

        Returns:
            Tuple[bool, str]: (是否触发止盈, 触发原因)
        """
        try:
            if position == 0 or entry_price <= 0 or current_price <= 0:
                return False, ""

            tp_price = self.take_profit_levels.get(asset)
            if tp_price is None or tp_price <= 0:
                # 无填充止盈水平时固定比例兜底 (多头 +5% / 空头 -5%)
                tp_price = entry_price * (1 + 0.05) if position > 0 else entry_price * (1 - 0.05)

            if position > 0:
                if current_price >= tp_price:
                    gain_pct = (current_price - entry_price) / entry_price
                    return True, f"多头止盈触发: 当前价{current_price:.4f} >= 止盈价{tp_price:.4f} ({gain_pct:.2%})"
            elif position < 0:
                if current_price <= tp_price:
                    gain_pct = (entry_price - current_price) / entry_price
                    return True, f"空头止盈触发: 当前价{current_price:.4f} <= 止盈价{tp_price:.4f} ({gain_pct:.2%})"

            return False, ""

        except Exception as e:
            logger.error(f"检查止盈触发时出错: {str(e)}")
            return False, f"止盈检查异常: {str(e)}"

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
