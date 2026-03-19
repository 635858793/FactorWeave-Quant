from loguru import logger
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd
import numpy as np

from core.strategy_extensions import (
    IStrategyPlugin, StrategyInfo, StrategyContext, Signal, SignalType,
    TradeResult, TradeAction, Position, TradingPerformanceMetrics, StrategyType,
    ParameterDef, RiskLevel, TimeFrame
)
from core.trading.trading_mode import ModeAwareMixin
from core.events import SignalGeneratedEvent, get_event_bus


class MeanReversionConfig:
    """均值回归策略配置"""
    
    def __init__(
        self,
        lookback_period: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.10,
        position_size_pct: float = 0.1,
        min_periods: int = 30
    ):
        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.position_size_pct = position_size_pct
        self.min_periods = min_periods


class MeanReversionStrategyPlugin(IStrategyPlugin):
    """
    均值回归策略插件
    
    策略逻辑:
    - 当价格偏离均值超过 entry_threshold 个标准差时产生信号
    - 价格回归均值时平仓
    
    特点:
    - 适合震荡市场
    - 有明确的止损止盈
    - 参数可配置
    """
    
    def __init__(self):
        # 初始化模式感知混入类
        ModeAwareMixin.__init__(self)
        
        self._initialized = False
        self._config: Optional[MeanReversionConfig] = None
        self._plugin_info = {
            "name": "mean_reversion",
            "version": "1.0.0",
            "author": "System",
            "description": "均值回归策略 - 基于价格偏离均值的交易策略",
            "strategy_type": "mean_reversion"
        }
        self._trade_history: List[TradeResult] = []
        self.logger = logger.bind(module=self.__class__.__name__)
    
    @property
    def plugin_info(self) -> Dict[str, Any]:
        return self._plugin_info
    
    def get_strategy_info(self) -> StrategyInfo:
        return StrategyInfo(
            name="mean_reversion",
            display_name="均值回归策略",
            description="基于价格偏离均值的均值回归交易策略，适合震荡市场",
            version="1.0.0",
            author="System",
            strategy_type=StrategyType.MEAN_REVERSION,
            parameters=[
                ParameterDef(
                    name="lookback_period",
                    type=int,
                    default_value=20,
                    description="均值计算回看期",
                    min_value=5,
                    max_value=200
                ),
                ParameterDef(
                    name="entry_threshold",
                    type=float,
                    default_value=2.0,
                    description="入场阈值（标准差倍数）",
                    min_value=0.5,
                    max_value=5.0
                ),
                ParameterDef(
                    name="exit_threshold",
                    type=float,
                    default_value=0.5,
                    description="出场阈值（标准差倍数）",
                    min_value=0.0,
                    max_value=2.0
                ),
                ParameterDef(
                    name="stop_loss_pct",
                    type=float,
                    default_value=0.05,
                    description="止损比例",
                    min_value=0.01,
                    max_value=0.2
                ),
                ParameterDef(
                    name="take_profit_pct",
                    type=float,
                    default_value=0.10,
                    description="止盈比例",
                    min_value=0.02,
                    max_value=0.3
                ),
                ParameterDef(
                    name="position_size_pct",
                    type=float,
                    default_value=0.1,
                    description="仓位比例",
                    min_value=0.05,
                    max_value=0.5
                )
            ],
            supported_assets=[],
            time_frames=[TimeFrame.DAY_1, TimeFrame.HOUR_4, TimeFrame.HOUR_1],
            risk_level=RiskLevel.MEDIUM,
            tags=["均值回归", "震荡市场", "技术分析"]
        )
    
    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        try:
            self._config = MeanReversionConfig(
                lookback_period=parameters.get('lookback_period', 20),
                entry_threshold=parameters.get('entry_threshold', 2.0),
                exit_threshold=parameters.get('exit_threshold', 0.5),
                stop_loss_pct=parameters.get('stop_loss_pct', 0.05),
                take_profit_pct=parameters.get('take_profit_pct', 0.10),
                position_size_pct=parameters.get('position_size_pct', 0.1)
            )
            self._initialized = True
            self.logger.info(f"均值回归策略初始化成功: lookback={self._config.lookback_period}, "
                           f"entry={self._config.entry_threshold}σ")
            return True
        except Exception as e:
            self.logger.error(f"均值回归策略初始化失败: {e}")
            return False
    
    def generate_signals(self, market_data, context: StrategyContext) -> List[Signal]:
        if not self._initialized or self._config is None:
            return []
        
        try:
            # 处理不同类型的输入
            if isinstance(market_data, pd.DataFrame):
                df = market_data
            else:
                df = market_data.to_dataframe()
            
            if len(df) < self._config.min_periods:
                self.logger.warning(f"数据不足，需要至少 {self._config.min_periods} 个周期")
                return []
            
            close = df['close']
            
            # 计算均值和标准差
            mean = close.rolling(window=self._config.lookback_period).mean()
            std = close.rolling(window=self._config.lookback_period).std()
            
            # 计算偏离度（Z-score）
            z_score = (close - mean) / std
            
            signals = []
            current_position = 0
            
            for i in range(1, len(df)):
                if i < self._config.lookback_period:
                    continue
                
                timestamp = df.index[i]
                current_price = close.iloc[i]
                z = z_score.iloc[i]
                
                signal_type = SignalType.HOLD
                reason = ""
                
                # 入场信号：价格偏离均值超过阈值
                if z > self._config.entry_threshold and current_position <= 0:
                    signal_type = SignalType.SELL
                    current_position = -1
                    reason = f"价格高估: Z-score={z:.2f}"
                elif z < -self._config.entry_threshold and current_position >= 0:
                    signal_type = SignalType.BUY
                    current_position = 1
                    reason = f"价格低估: Z-score={z:.2f}"
                # 出场信号：价格回归均值
                elif abs(z) < self._config.exit_threshold and current_position != 0:
                    signal_type = SignalType.HOLD
                    if current_position > 0:
                        signal_type = SignalType.SELL
                        reason = f"价格回归: Z-score={z:.2f}"
                    else:
                        signal_type = SignalType.BUY
                        reason = f"价格回归: Z-score={z:.2f}"
                    current_position = 0
                
                if signal_type != SignalType.HOLD:
                    stop_loss = None
                    take_profit = None
                    
                    if signal_type == SignalType.BUY:
                        stop_loss = current_price * (1 - self._config.stop_loss_pct)
                        take_profit = current_price * (1 + self._config.take_profit_pct)
                    else:
                        stop_loss = current_price * (1 + self._config.stop_loss_pct)
                        take_profit = current_price * (1 - self._config.take_profit_pct)
                    
                    confidence = min(abs(z) / self._config.entry_threshold, 1.0)
                    
                    signal = Signal(
                        symbol=market_data.symbol,
                        signal_type=signal_type,
                        strength=confidence,
                        timestamp=timestamp,
                        price=current_price,
                        reason=reason,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        metadata={
                            'z_score': z,
                            'mean': mean.iloc[i] if not pd.isna(mean.iloc[i]) else 0,
                            'std': std.iloc[i] if not pd.isna(std.iloc[i]) else 0
                        }
                    )
                    signals.append(signal)
            
            # 发布信号生成事件
            if signals:
                try:
                    event = SignalGeneratedEvent(
                        strategy_id=self._plugin_info["name"],
                        strategy_name=self._plugin_info["display_name"],
                        signals=[{
                            'signal_type': s.signal_type.value,
                            'symbol': s.symbol,
                            'strength': s.strength,
                            'timestamp': s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
                            'price': s.price,
                            'reason': s.reason
                        } for s in signals],
                        symbol=market_data.symbol,
                        priority=1,
                        timestamp=datetime.now(),
                        source="mean_reversion_strategy",
                        data={
                            'plugin_type': 'mean_reversion',
                            'z_score_range': f"{z_score.min():.2f} ~ {z_score.max():.2f}" if hasattr(z_score, 'min') else "N/A"
                        }
                    )
                    get_event_bus().publish(event)
                except Exception as event_error:
                    self.logger.warning(f"发布信号事件失败: {event_error}")
            
            return signals
            
        except Exception as e:
            self.logger.error(f"均值回归策略信号生成失败: {e}")
            return []
    
    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        try:
            quantity = int(context.initial_capital * self._config.position_size_pct / signal.price) if self._config else 100
            if quantity <= 0:
                quantity = 100
            
            trade_id = f"mean_reversion_{signal.symbol}_{int(signal.timestamp.timestamp())}"
            
            if signal.signal_type == SignalType.BUY:
                action = TradeAction.OPEN_LONG
            elif signal.signal_type == SignalType.SELL:
                action = TradeAction.CLOSE_LONG
            else:
                action = TradeAction.ADJUST
            
            commission = signal.price * quantity * context.commission_rate
            
            trade_result = TradeResult(
                trade_id=trade_id,
                symbol=signal.symbol,
                action=action,
                quantity=quantity,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=commission,
                status=None,
                metadata={
                    'signal_reason': signal.reason,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit
                }
            )
            
            self._trade_history.append(trade_result)
            self.logger.info(f"均值回归交易执行: {action.value} {signal.symbol} {quantity}@{signal.price}")
            return trade_result
            
        except Exception as e:
            self.logger.error(f"均值回归策略交易执行失败: {e}")
            return TradeResult(
                trade_id=f"error_{int(datetime.now().timestamp())}",
                symbol=signal.symbol,
                action=TradeAction.ADJUST,
                quantity=0,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=0,
                status=None,
                error_message=str(e)
            )
    
    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        symbol = trade_result.symbol
        current_price = trade_result.price
        
        existing = next((p for p in [] if p.symbol == symbol), None)
        quantity = trade_result.quantity if trade_result.action in [TradeAction.OPEN_LONG, TradeAction.OPEN_SHORT] else -trade_result.quantity
        
        return Position(
            symbol=symbol,
            quantity=abs(quantity),
            avg_price=trade_result.price,
            current_price=current_price,
            market_value=current_price * abs(quantity),
            unrealized_pnl=0,
            realized_pnl=0,
            timestamp=trade_result.timestamp,
            metadata={}
        )
    
    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        if not self._trade_history:
            return TradingPerformanceMetrics(
                total_return=0,
                annual_return=0,
                sharpe_ratio=0,
                max_drawdown=0,
                win_rate=0,
                profit_factor=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0,
                avg_loss=0,
                start_date=datetime.now(),
                end_date=datetime.now()
            )
        
        returns = []
        win_count = 0
        total_trades = len(self._trade_history)
        wins = []
        losses = []
        
        for i in range(1, len(self._trade_history)):
            curr = self._trade_history[i]
            prev = self._trade_history[i - 1]
            
            if prev.action in [TradeAction.OPEN_LONG, TradeAction.OPEN_SHORT]:
                pnl = (curr.price - prev.price) / prev.price
                returns.append(pnl)
                if pnl > 0:
                    win_count += 1
                    wins.append(pnl)
                else:
                    losses.append(pnl)
        
        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = np.std(returns) if len(returns) > 1 else 0.01
            sharpe = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
            max_dd = min(returns) if returns else 0
            annual_return = avg_return * 252
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0
        else:
            avg_return = 0
            sharpe = 0
            max_dd = 0
            annual_return = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        start_date = self._trade_history[0].timestamp if self._trade_history else datetime.now()
        end_date = self._trade_history[-1].timestamp if self._trade_history else datetime.now()
        
        return TradingPerformanceMetrics(
            total_return=sum(returns) if returns else 0,
            annual_return=annual_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=total_trades - win_count,
            avg_win=avg_win,
            avg_loss=avg_loss,
            start_date=start_date,
            end_date=end_date
        )
    
    def cleanup(self) -> None:
        self._initialized = False
        self._config = None
        self._trade_history.clear()
        self.logger.info("均值回归策略已清理")
