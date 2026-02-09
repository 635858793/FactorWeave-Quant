#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VWAP均值回归策略插件

功能：
1. 基于VWAP的价格偏离度计算
2. 价格偏离VWAP时进行反向交易
3. 支持多种参数配置
4. 企业级插件架构
"""

from loguru import logger
import pandas as pd
import numpy as np
from typing import List,Tuple, Union
from datetime import datetime
from typing import Dict, Any

from core.strategy_extensions import (
    IStrategyPlugin,
    StrategyInfo,
    StrategyType,
    RiskLevel,
    TimeFrame,
    ParameterDef,
    Signal,
    SignalType,
    TradeResult,
    TradeAction,
    TradeStatus,
    Position,
    TradingPerformanceMetrics,
    StandardMarketData,
    StrategyContext
)
from core.plugin_types import AssetType


class VWAPReversionPlugin(IStrategyPlugin):
    """VWAP均值回归策略插件"""
    
    def __init__(self):
        """初始化策略插件"""
        self._strategy_info = self._create_strategy_info()
        self._parameters = {}
        self._context = None
        self._positions = {}
        self._trade_results = []
    
    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return {
            "name": "vwap_reversion",
            "display_name": "VWAP均值回归策略",
            "version": "1.0.0",
            "author": "FactorWeave-Quant Team",
            "description": "价格偏离VWAP时进行反向交易",
            "compatibility": "hikyuu-ui v2.0+"
        }
    
    def _create_strategy_info(self) -> StrategyInfo:
        """创建策略信息"""
        return StrategyInfo(
            name="vwap_reversion",
            display_name="VWAP均值回归策略",
            description="价格偏离VWAP时进行反向交易",
            version="1.0.0",
            author="FactorWeave-Quant Team",
            strategy_type=StrategyType.MEAN_REVERSION,
            parameters=[
                ParameterDef(
                    name="deviation_threshold",
                    type=float,
                    default_value=0.02,
                    description="偏离阈值",
                    min_value=0.001,
                    max_value=0.1,
                    required=True
                ),
                ParameterDef(
                    name="hold_period",
                    type=int,
                    default_value=3,
                    description="持有周期",
                    min_value=1,
                    max_value=20,
                    required=True
                ),
                ParameterDef(
                    name="min_turnover_rate",
                    type=float,
                    default_value=0.5,
                    description="最小换手率",
                    min_value=0.1,
                    max_value=10.0,
                    required=False
                )
            ],
            supported_assets=[AssetType.STOCK_A, AssetType.STOCK_B, AssetType.STOCK_HK],
            time_frames=[
                TimeFrame.DAY_1,
                TimeFrame.WEEK_1
            ],
            risk_level=RiskLevel.MEDIUM,
            tags=["mean_reversion", "technical", "stock"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def get_strategy_info(self) -> StrategyInfo:
        """获取策略信息"""
        return self._strategy_info
    
    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """初始化策略"""
        try:
            # 验证参数
            is_valid, error_msg = self.validate_parameters(parameters)
            if not is_valid:
                logger.error(f"参数验证失败: {error_msg}")
                return False
            
            # 设置参数
            self._parameters = parameters
            self._context = context
            self._positions = {}
            self._trade_results = []
            
            logger.info(f"VWAP均值回归策略初始化成功，参数: {self._parameters}")
            return True
        except Exception as e:
            logger.error(f"策略初始化失败: {e}")
            return False
    
    def generate_signals(self, market_data: Union[StandardMarketData, pd.DataFrame], context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        try:
            signals = []
            
            # 处理不同类型的输入
            if isinstance(market_data, pd.DataFrame):
                df = market_data
                symbol = context.symbol if hasattr(context, 'symbol') else "unknown"
            else:
                df = market_data.to_dataframe()
                symbol = market_data.symbol
            
            # 检查数据是否包含必需的列
            required_cols = ['vwap', 'close', 'turnover_rate']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.error(f"数据缺少必需列: {missing_cols}, 股票: {symbol}")
                return signals
            
            # 获取参数
            threshold = self._parameters.get('deviation_threshold', 0.02)
            min_turnover = self._parameters.get('min_turnover_rate', 0.5)
            
            # 计算偏离度
            df['vwap_deviation'] = (df['close'] - df['vwap']) / df['vwap']
            
            # 流动性过滤
            df['is_liquid'] = df['turnover_rate'] > min_turnover
            
            # 生成信号
            for i in range(len(df)):
                current_date = df.index[i]
                current_close = df.iloc[i]['close']
                deviation = df.iloc[i]['vwap_deviation']
                is_liquid = df.iloc[i]['is_liquid']
                
                signal_type = SignalType.HOLD
                strength = 0.0
                reason = ""
                
                if is_liquid:
                    if deviation < -threshold:
                        signal_type = SignalType.BUY
                        strength = min(abs(deviation), 1.0)
                        reason = f"价格低于VWAP {abs(deviation):.4f}，且流动性充足"
                    elif deviation > threshold:
                        signal_type = SignalType.SELL
                        strength = min(deviation, 1.0)
                        reason = f"价格高于VWAP {deviation:.4f}，且流动性充足"
                
                if signal_type != SignalType.HOLD:
                    signal = Signal(
                        symbol=symbol,
                        signal_type=signal_type,
                        strength=strength,
                        timestamp=current_date,
                        price=current_close,
                        reason=reason,
                        metadata={
                            'vwap_deviation': deviation,
                            'is_liquid': is_liquid,
                            'deviation_threshold': threshold
                        }
                    )
                    signals.append(signal)
            
            logger.info(f"生成了 {len(signals)} 个信号: {symbol}")
            
            # 发布信号生成事件
            if signals:
                try:
                    from core.events import SignalGeneratedEvent, get_event_bus
                    event = SignalGeneratedEvent(
                        strategy_id=self._strategy_info.name,
                        strategy_name=self._strategy_info.display_name,
                        signals=[{
                            'signal_type': s.signal_type.value,
                            'symbol': s.symbol,
                            'strength': s.strength,
                            'timestamp': s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
                            'price': s.price,
                            'reason': s.reason
                        } for s in signals],
                        symbol=symbol,
                        priority=1,
                        timestamp=datetime.now(),
                        source="vwap_reversion_strategy",
                        data={'plugin_type': 'vwap_reversion'}
                    )
                    get_event_bus().publish(event)
                except Exception as event_error:
                    logger.warning(f"发布VWAP策略信号事件失败: {event_error}")
            
            return signals
        except Exception as e:
            logger.error(f"生成信号失败: {e}")
            return []
    
    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """执行交易"""
        try:
            # 创建交易结果
            trade_result = TradeResult(
                trade_id=f"trade_{datetime.now().timestamp()}_{signal.symbol}",
                symbol=signal.symbol,
                action=TradeAction.OPEN_LONG if signal.signal_type == SignalType.BUY else TradeAction.CLOSE_LONG,
                quantity=100,  # 简化处理，实际应根据资金和风险计算
                price=signal.price,
                timestamp=signal.timestamp,
                commission=signal.price * 100 * context.commission_rate,
                status=TradeStatus.FILLED,
                metadata={
                    'signal_strength': signal.strength,
                    'signal_reason': signal.reason,
                    'vwap_deviation': signal.metadata.get('vwap_deviation', 0.0)
                }
            )
            
            self._trade_results.append(trade_result)
            logger.info(f"执行交易成功: {trade_result.trade_id}")
            return trade_result
        except Exception as e:
            logger.error(f"执行交易失败: {e}")
            return TradeResult(
                trade_id=f"trade_{datetime.now().timestamp()}_{signal.symbol}",
                symbol=signal.symbol,
                action=TradeAction.OPEN_LONG if signal.signal_type == SignalType.BUY else TradeAction.CLOSE_LONG,
                quantity=0,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=0,
                status=TradeStatus.ERROR,
                error_message=str(e)
            )
    
    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        """更新持仓"""
        try:
            symbol = trade_result.symbol
            
            # 创建或更新持仓
            if symbol not in self._positions:
                self._positions[symbol] = {
                    'quantity': 0,
                    'avg_price': 0.0,
                    'current_price': trade_result.price
                }
            
            position_data = self._positions[symbol]
            
            if trade_result.action == TradeAction.OPEN_LONG:
                # 开仓
                total_cost = position_data['avg_price'] * position_data['quantity'] + trade_result.price * trade_result.quantity
                total_quantity = position_data['quantity'] + trade_result.quantity
                position_data['avg_price'] = total_cost / total_quantity if total_quantity > 0 else 0.0
                position_data['quantity'] = total_quantity
            elif trade_result.action == TradeAction.CLOSE_LONG:
                # 平仓
                position_data['quantity'] = max(0, position_data['quantity'] - trade_result.quantity)
                if position_data['quantity'] == 0:
                    position_data['avg_price'] = 0.0
            
            position_data['current_price'] = trade_result.price
            
            # 计算持仓信息
            market_value = position_data['quantity'] * position_data['current_price']
            unrealized_pnl = position_data['quantity'] * (position_data['current_price'] - position_data['avg_price'])
            
            # 创建持仓对象
            position = Position(
                symbol=symbol,
                quantity=position_data['quantity'],
                avg_price=position_data['avg_price'],
                current_price=position_data['current_price'],
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=0.0,  # 简化处理，实际应累加已平仓盈亏
                timestamp=trade_result.timestamp
            )
            
            logger.info(f"更新持仓成功: {symbol}, 持仓数量: {position.quantity}")
            return position
        except Exception as e:
            logger.error(f"更新持仓失败: {e}")
            raise
    
    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        """计算策略性能"""
        try:
            # 简化处理，实际应基于交易结果和持仓计算
            return TradingPerformanceMetrics(
                total_return=0.0,
                annual_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=len(self._trade_results),
                winning_trades=0,
                losing_trades=0,
                avg_win=0.0,
                avg_loss=0.0,
                start_date=context.start_date,
                end_date=context.end_date
            )
        except Exception as e:
            logger.error(f"计算性能指标失败: {e}")
            raise
    
    def cleanup(self) -> None:
        """清理资源"""
        self._parameters = {}
        self._context = None
        self._positions = {}
        self._trade_results = []
        logger.info("策略资源清理完成")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """验证策略参数"""
        try:
            # 调用父类的验证方法
            result = super().validate_parameters(parameters)
            if not result[0]:
                return result
            
            # 自定义验证逻辑
            if 'deviation_threshold' in parameters:
                value = parameters['deviation_threshold']
                if not isinstance(value, (int, float)) or value <= 0 or value > 0.1:
                    return False, "deviation_threshold必须是0-0.1之间的正数"
            
            if 'hold_period' in parameters:
                value = parameters['hold_period']
                if not isinstance(value, int) or value < 1 or value > 20:
                    return False, "hold_period必须是1-20之间的整数"
            
            if 'min_turnover_rate' in parameters:
                value = parameters['min_turnover_rate']
                if not isinstance(value, (int, float)) or value < 0.1 or value > 10.0:
                    return False, "min_turnover_rate必须是0.1-10.0之间的正数"
            
            return True, "参数验证通过"
        except Exception as e:
            return False, f"参数验证失败: {e}"