"""
风险管理模块
"""
import numpy as np
import pandas as pd
from loguru import logger
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from core.config import ConfigManager, config_manager

class RiskManager:
    """风险管理类

    设计债务（TECH_DEBT-001）：持仓三分问题
    本模块通过 self.current_positions: dict 维护了独立的持仓数据结构，
    与 core/position_manager.py 和 core/trading_engine.py 中的持仓数据无同步机制。
    三个模块各自独立维护持仓，可能导致数据不一致。
    建议通过事件总线（EventBus）同步：当任一处持仓变更时，发布
    'position_updated' 事件，由其他两模块订阅并更新。
    """

    def __init__(self):
        """初始化风险管理器"""
        # 纯Loguru架构，移除log_manager依赖
        self.initialized = False

        # 风险控制参数
        self.max_position_size = 0.3  # 最大持仓比例
        self.max_single_position = 0.1  # 单个股票最大持仓比例
        self.stop_loss = 0.05  # 止损比例
        self.max_drawdown = 0.2  # 最大回撤限制

        # 当前状态
        self.current_positions = {}  # 当前持仓
        self.current_equity = 0  # 当前权益
        self.peak_equity = 0  # 最高权益

        # 监控桥接
        self._monitor = None

    def initialize(self) -> bool:
        """初始化风险管理器"""
        try:
            # 加载风险控制参数
            self._load_risk_params()

            self.initialized = True
            logger.info("风险管理器初始化成功")
            return True

        except Exception as e:
            logger.info(f"风险管理器初始化失败: {str(e)}")
            return False

    def _load_risk_params(self):
        """加载风险控制参数"""
        try:
            risk_config = config_manager.get('risk', {})

            self.max_position_size = risk_config.get(
                'max_position_size',
                self.max_position_size
            )
            self.max_single_position = risk_config.get(
                'max_single_position',
                self.max_single_position
            )
            self.stop_loss = risk_config.get(
                'stop_loss',
                self.stop_loss
            )
            self.max_drawdown = risk_config.get(
                'max_drawdown',
                self.max_drawdown
            )

            logger.info(
                f"风险控制参数加载成功: "
                f"最大持仓比例={self.max_position_size}, "
                f"单股最大持仓={self.max_single_position}, "
                f"止损比例={self.stop_loss}, "
                f"最大回撤={self.max_drawdown}"
            )

        except Exception as e:
            logger.error(f"加载风险控制参数失败: {str(e)}")
            logger.warning("使用默认风险控制参数")

    def check_trade(self, signal: float, price: float, current_equity: float) -> bool:
        """回测引擎集成的交易风险检查（简化接口）

        Args:
            signal: 交易信号值 (1=买入, -1=卖出, 0=持仓)
            price: 当前价格
            current_equity: 当前权益

        Returns:
            bool: 是否通过风险检查
        """
        try:
            if signal == 0:
                return True

            if not self.initialized:
                self.initialized = True

            self.current_equity = current_equity

            signal_type = 'buy' if signal > 0 else 'sell'
            signal_dict = {
                'type': signal_type,
                'stock_code': 'backtest',
                'amount': current_equity * self.max_single_position,
                'price': price
            }

            if not self._check_position_limit(signal_dict):
                return False

            if not self._check_stop_loss(signal_dict):
                return False

            if not self._check_drawdown():
                return False

            return True

        except Exception as e:
            logger.error(f"回测交易风险检查失败: {str(e)}")
            return False

    def _check_position_limit(self, signal: Dict) -> bool:
        """检查持仓限制"""
        try:
            if signal['type'] == 'buy':
                if self.current_equity <= 0:
                    logger.warning("当前权益为零或负数，跳过持仓限制检查")
                    return False

                # 计算当前总持仓市值
                total_position_value = sum(
                    pos.get('amount', 0) if isinstance(pos, dict) else pos
                    for pos in self.current_positions.values()
                )
                total_position_ratio = total_position_value / self.current_equity

                # 检查是否超过最大持仓比例
                if total_position_ratio >= self.max_position_size:
                    logger.warning("超过最大持仓比例限制")
                    return False

                # 计算目标股票持仓比例
                stock_code = signal['stock_code']
                current_pos = self.current_positions.get(stock_code, 0)
                current_amount = current_pos.get('amount', 0) if isinstance(current_pos, dict) else current_pos
                new_position = current_amount + signal['amount']
                position_ratio = new_position / self.current_equity

                # 检查是否超过单个股票最大持仓比例
                if position_ratio > self.max_single_position:
                    logger.warning("超过单个股票最大持仓比例限制")
                    return False

            return True

        except Exception as e:
            logger.error(f"检查持仓限制失败: {str(e)}")
            return False

    def _check_stop_loss(self, signal: Dict) -> bool:
        """检查止损"""
        try:
            if signal['type'] == 'buy':
                return True

            stock_code = signal['stock_code']
            if stock_code not in self.current_positions:
                return True

            # 获取持仓中的均价（兼容字典和数值两种格式）
            pos_data = self.current_positions[stock_code]
            if isinstance(pos_data, dict):
                avg_cost = pos_data.get('avg_cost', 0)
            else:
                avg_cost = float(pos_data) if pos_data else 0

            if avg_cost <= 0:
                return True

            # 计算浮动盈亏比例
            current_price = signal['price']
            profit_ratio = (current_price - avg_cost) / avg_cost

            if signal['type'] == 'short':
                if profit_ratio >= self.stop_loss:
                    logger.warning(f"触发做空止损: {stock_code}, 亏损: {profit_ratio:.2%}")
                    return False
                return True

            if profit_ratio <= -self.stop_loss:
                logger.warning(f"触发止损: {stock_code}, 亏损: {profit_ratio:.2%}")
                return False

            return True

        except Exception as e:
            logger.error(f"检查止损失败: {str(e)}")
            return False

    def _check_drawdown(self) -> bool:
        """检查回撤"""
        try:
            if self.current_equity > self.peak_equity:
                self.peak_equity = self.current_equity

            if self.peak_equity > 0:
                drawdown = (self.peak_equity -
                            self.current_equity) / self.peak_equity

                # 检查是否超过最大回撤限制
                if drawdown >= self.max_drawdown:
                    logger.warning("超过最大回撤限制")
                    return False

            return True

        except Exception as e:
            logger.error(f"检查回撤失败: {str(e)}")
            return False

    def dispose(self) -> None:
        """释放资源 (HVD-241-P0-C-3, R78 4 链标准)

        Why: 纯内存状态类, 双宿主 (backtest 引擎 unified_backtest_engine.py:248 +
             backtest_widget.py:1877) 均无清理调用 → 一致性/防御性治理
             (R241-C 子智能体 100% 确认, 非泄漏源)
        Fix: _disposed 幂等短路 + 清空 current_positions + initialized 置 False
             + 解除 _monitor 引用; 失败仅 warning 不抛 (R8 铁律 #7)
        TDD: tests/test_r241_p0c_dispose_chains_tools_cache.py T05/T06
        """
        if getattr(self, '_disposed', False):
            return
        try:
            self.current_positions = {}
            self.initialized = False
            self._monitor = None
            self._disposed = True
            logger.info("RiskManager disposed")
        except Exception as e:
            logger.warning(f"RiskManager dispose 失败: {e}")
            self._disposed = True


class TradeOrchestrator:
    """
    [R269-D3 REMOVED] 死代码删除 (2026-08-09)

    本类为半成品死代码, 判定依据 (深度调研 + 源码行号交叉验证):
    - 全仓库零调用点: grep `TradeOrchestrator` 仅命中本文件自身定义与日志字符串。
    - 依赖的 `TradingInstruction` 类型全仓库无定义 (无 import/class/dataclass),
      即使被调用, orchestrate 构造 TradingInstruction 时必抛 NameError → 必返回 None。
    - 其价值已由 R269-D3 复活的三组件完整承接: AdaptiveStopLoss (core/stop_loss.py)、
      AdaptiveTakeProfit (core/take_profit.py)、EnhancedMoneyManager (core/money_manager.py)
      现由活服务 PositionRiskMonitor (core/trading/position_risk_monitor.py) 集成,
      并已注册容器 (service_bootstrap) + 接入订单风控链路 (order_executor._fill_stop_loss_level)。
    """
