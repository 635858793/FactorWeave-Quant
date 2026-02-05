"""
双均线策略插件

基于 IStrategyPlugin (core.strategy_extensions) 实现的经典双均线交叉策略。
与系统的主要策略框架对齐，支持完整的策略生命周期管理。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime

from PyQt5.QtWidgets import QWidget, QFormLayout, QSpinBox, QComboBox

from core.strategy_extensions import (
    IStrategyPlugin, Signal, TradeResult, Position, TradingPerformanceMetrics,
    StandardMarketData, StrategyContext, SignalType, TradeAction, TradeStatus,
    ParameterDef, StrategyType, RiskLevel
)
from core.plugin_types import PluginType


@dataclass
class MAStrategyConfig:
    """双均线策略配置"""
    fast_period: int = 5
    slow_period: int = 20
    ma_type: str = 'SMA'
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10


class MovingAverageStrategyPlugin(IStrategyPlugin):
    """双均线策略插件"""
    
    def __init__(self):
        self._config = MAStrategyConfig()
        self._initialized = False
        self._plugin_info = {
            "name": "moving_average",
            "version": "3.0.0",
            "display_name": "双均线策略",
            "description": "经典双均线交叉策略，基于快慢均线生成交易信号",
            "author": "FactorWeave 团队",
            "strategy_type": StrategyType.TREND_FOLLOWING,
            "risk_level": RiskLevel.MEDIUM
        }

    @property
    def plugin_info(self) -> Dict[str, Any]:
        return {
            "name": self._plugin_info["name"],
            "version": self._plugin_info["version"],
            "display_name": self._plugin_info["display_name"],
            "description": self._plugin_info["description"],
            "author": self._plugin_info["author"],
            "strategy_type": self._plugin_info["strategy_type"].value,
            "risk_level": self._plugin_info["risk_level"].value,
            "tags": ["技术指标", "趋势跟踪", "均线交叉"]
        }

    def get_strategy_info(self) -> 'StrategyInfo':
        from core.strategy_extensions import StrategyInfo
        return StrategyInfo(
            name=self._plugin_info["name"],
            display_name=self._plugin_info["display_name"],
            description=self._plugin_info["description"],
            version=self._plugin_info["version"],
            author=self._plugin_info["author"],
            strategy_type=self._plugin_info["strategy_type"],
            risk_level=self._plugin_info["risk_level"],
            parameters=self.get_parameters(),
            tags=["技术指标", "趋势跟踪", "均线交叉"]
        )

    def get_parameters(self) -> List[ParameterDef]:
        return [
            ParameterDef(
                name="fast_period",
                type=int,
                default_value=5,
                description="快速均线周期",
                min_value=1,
                max_value=50,
                required=True
            ),
            ParameterDef(
                name="slow_period",
                type=int,
                default_value=20,
                description="慢速均线周期",
                min_value=2,
                max_value=200,
                required=True
            ),
            ParameterDef(
                name="ma_type",
                type=str,
                default_value="SMA",
                description="均线类型",
                choices=["SMA", "EMA"],
                required=True
            ),
            ParameterDef(
                name="stop_loss_pct",
                type=float,
                default_value=0.05,
                description="止损百分比",
                min_value=0.0,
                max_value=0.5,
                required=False
            ),
            ParameterDef(
                name="take_profit_pct",
                type=float,
                default_value=0.10,
                description="止盈百分比",
                min_value=0.0,
                max_value=1.0,
                required=False
            )
        ]

    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            fast_period = int(parameters.get('fast_period', 5))
            slow_period = int(parameters.get('slow_period', 20))
            ma_type = str(parameters.get('ma_type', 'SMA'))
            
            if not (1 <= fast_period <= 50):
                return False, f"快速周期必须在1-50之间，当前值: {fast_period}"
            if not (2 <= slow_period <= 200):
                return False, f"慢速周期必须在2-200之间，当前值: {slow_period}"
            if fast_period >= slow_period:
                return False, f"快速周期必须小于慢速周期，当前: {fast_period} >= {slow_period}"
            if ma_type not in ['SMA', 'EMA']:
                return False, f"均线类型必须是SMA或EMA，当前值: {ma_type}"
            
            return True, ""
        except Exception as e:
            return False, f"参数验证异常: {str(e)}"

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        valid, error_msg = self.validate_parameters(parameters)
        if not valid:
            return False
        
        try:
            self._config = MAStrategyConfig(
                fast_period=int(parameters.get('fast_period', 5)),
                slow_period=int(parameters.get('slow_period', 20)),
                ma_type=str(parameters.get('ma_type', 'SMA')),
                stop_loss_pct=float(parameters.get('stop_loss_pct', 0.05)),
                take_profit_pct=float(parameters.get('take_profit_pct', 0.10))
            )
            self._initialized = True
            return True
        except Exception:
            return False

    def generate_signals(self, market_data: Union[StandardMarketData, pd.DataFrame], 
                        context: StrategyContext) -> List[Signal]:
        if not self._initialized:
            raise RuntimeError("双均线策略未初始化")
        
        # 处理不同类型的输入
        if isinstance(market_data, pd.DataFrame):
            data = market_data
            symbol = context.symbol if hasattr(context, 'symbol') else "unknown"
        else:
            data = market_data.to_dataframe()
            symbol = market_data.symbol
        
        if len(data) < self._config.slow_period:
            raise ValueError(f"数据长度不足，需要至少{self._config.slow_period}个数据点")

        close_prices = data['close']
        if self._config.ma_type == 'EMA':
            fast_ma = self._calculate_ema(close_prices, self._config.fast_period)
            slow_ma = self._calculate_ema(close_prices, self._config.slow_period)
        else:
            fast_ma = self._calculate_sma(close_prices, self._config.fast_period)
            slow_ma = self._calculate_sma(close_prices, self._config.slow_period)

        signals = []
        current_position = 0
        
        for i in range(1, len(data)):
            timestamp = data.index[i]
            current_price = close_prices.iloc[i]
            
            fast_ma_val = fast_ma.iloc[i]
            slow_ma_val = slow_ma.iloc[i]
            fast_ma_prev = fast_ma.iloc[i-1]
            slow_ma_prev = slow_ma.iloc[i-1]
            
            signal_type = SignalType.HOLD
            reason = ""
            
            if fast_ma_prev <= slow_ma_prev and fast_ma_val > slow_ma_val:
                if current_position <= 0:
                    signal_type = SignalType.BUY
                    current_position = 1
                    reason = f"金叉: 快速均线({fast_ma_val:.2f})上穿慢速均线({slow_ma_val:.2f})"
            elif fast_ma_prev >= slow_ma_prev and fast_ma_val < slow_ma_val:
                if current_position >= 0:
                    signal_type = SignalType.SELL
                    current_position = -1
                    reason = f"死叉: 快速均线({fast_ma_val:.2f})下穿慢速均线({slow_ma_val:.2f})"
            
            if signal_type != SignalType.HOLD:
                stop_loss = current_price * (1 - self._config.stop_loss_pct) if self._config.stop_loss_pct > 0 else None
                take_profit = current_price * (1 + self._config.take_profit_pct) if self._config.take_profit_pct > 0 else None
                
                confidence = min(abs(fast_ma_val - slow_ma_val) / slow_ma_val * 10 + 0.5, 1.0)
                
                signal = Signal(
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=1.0,
                    timestamp=timestamp,
                    price=current_price,
                    reason=reason,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=confidence
                )
                signals.append(signal)
        
        # 发布信号生成事件
        if signals:
            try:
                from core.events import SignalGeneratedEvent, get_event_bus
                event = SignalGeneratedEvent(
                    strategy_id=self._plugin_info["name"],
                    strategy_name=self._plugin_info["display_name"],
                    signals=[{
                        'signal_type': s.signal_type.value,
                        'symbol': s.symbol,
                        'strength': getattr(s, 'confidence', s.strength),
                        'timestamp': s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
                        'price': s.price,
                        'reason': s.reason
                    } for s in signals],
                    symbol=symbol,
                    priority=1,
                    timestamp=datetime.now(),
                    source="moving_average_strategy",
                    data={'plugin_type': 'moving_average'}
                )
                get_event_bus().publish(event)
            except Exception as event_error:
                logger.warning(f"发布均线策略信号事件失败: {event_error}")
        
        return signals

    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        trade_action = TradeAction.OPEN_LONG if signal.signal_type == SignalType.BUY else TradeAction.CLOSE_LONG
        
        quantity = int(context.initial_capital * 0.1 / signal.price)
        if quantity <= 0:
            quantity = 100
        
        commission = signal.price * quantity * context.commission_rate
        
        return TradeResult(
            trade_id=f"ma_{signal.symbol}_{int(signal.timestamp.timestamp())}",
            symbol=signal.symbol,
            action=trade_action,
            quantity=quantity,
            price=signal.price,
            timestamp=signal.timestamp,
            commission=commission,
            status=TradeStatus.FILLED,
            metadata={
                "strategy": "moving_average",
                "confidence": signal.confidence,
                "reason": signal.reason
            }
        )

    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        return Position(
            symbol=trade_result.symbol,
            quantity=trade_result.quantity,
            avg_price=trade_result.price,
            current_price=trade_result.price,
            market_value=trade_result.quantity * trade_result.price,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            timestamp=trade_result.timestamp
        )

    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        return TradingPerformanceMetrics(
            total_return=0.0,
            annual_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_win=0.0,
            avg_loss=0.0,
            start_date=context.start_date,
            end_date=context.end_date
        )

    def cleanup(self) -> None:
        self._initialized = False

    def _calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        return data.rolling(window=period, min_periods=1).mean()

    def _calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        return data.ewm(span=period, adjust=False).mean()

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'fast_period': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 5, 'title': '快速均线周期'},
                'slow_period': {'type': 'integer', 'minimum': 2, 'maximum': 200, 'default': 20, 'title': '慢速均线周期'},
                'ma_type': {'type': 'string', 'enum': ['SMA', 'EMA'], 'default': 'SMA', 'title': '均线类型'},
                'stop_loss_pct': {'type': 'number', 'minimum': 0.0, 'maximum': 0.5, 'default': 0.05, 'title': '止损百分比'},
                'take_profit_pct': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0, 'default': 0.10, 'title': '止盈百分比'}
            },
            'required': ['fast_period', 'slow_period', 'ma_type'],
            'additionalProperties': False
        }

    def create_config_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        
        fast_box = QSpinBox()
        fast_box.setRange(1, 50)
        fast_box.setValue(self._config.fast_period)
        
        slow_box = QSpinBox()
        slow_box.setRange(2, 200)
        slow_box.setValue(self._config.slow_period)
        
        ma_type_combo = QComboBox()
        ma_type_combo.addItems(['SMA', 'EMA'])
        ma_type_combo.setCurrentText(self._config.ma_type)
        
        layout.addRow("快速均线周期:", fast_box)
        layout.addRow("慢速均线周期:", slow_box)
        layout.addRow("均线类型:", ma_type_combo)

        def on_change():
            new_cfg = {
                'fast_period': fast_box.value(),
                'slow_period': slow_box.value(),
                'ma_type': ma_type_combo.currentText()
            }
            valid, _ = self.validate_parameters(new_cfg)
            if valid:
                self._config.fast_period = fast_box.value()
                self._config.slow_period = slow_box.value()
                self._config.ma_type = ma_type_combo.currentText()
        
        fast_box.valueChanged.connect(on_change)
        slow_box.valueChanged.connect(on_change)
        ma_type_combo.currentTextChanged.connect(on_change)
        
        return widget
