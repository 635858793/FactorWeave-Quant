#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
复权价格动量策略插件

功能：
1. 基于复权价格计算动量
2. 生成买入卖出信号
3. 支持多种参数配置
4. 企业级插件架构
"""

from loguru import logger
import pandas as pd
import numpy as np
from typing import List,Tuple
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
    PerformanceMetrics,
    StandardMarketData,
    StrategyContext
)
from core.plugin_types import AssetType


class AdjMomentumPlugin(IStrategyPlugin):
    """复权价格动量策略插件"""
    
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
            "name": "adj_momentum",
            "display_name": "复权价格动量策略",
            "version": "1.0.0",
            "author": "FactorWeave-Quant Team",
            "description": "基于复权价格计算真实动量，选择动量最强的股票",
            "compatibility": "hikyuu-ui v2.0+"
        }
    
    def _create_strategy_info(self) -> StrategyInfo:
        """创建策略信息"""
        return StrategyInfo(
            name="adj_momentum",
            display_name="复权价格动量策略",
            description="基于复权价格计算真实动量，选择动量最强的股票",
            version="1.0.0",
            author="FactorWeave-Quant Team",
            strategy_type=StrategyType.MOMENTUM,
            parameters=[
                ParameterDef(
                    name="lookback_period",
                    type=int,
                    default_value=20,
                    description="动量计算周期",
                    min_value=1,
                    max_value=200,
                    required=True
                ),
                ParameterDef(
                    name="top_n",
                    type=int,
                    default_value=10,
                    description="选择前N只股票",
                    min_value=1,
                    max_value=100,
                    required=True
                ),
                ParameterDef(
                    name="signal_strength_threshold",
                    type=float,
                    default_value=0.01,
                    description="信号强度阈值",
                    min_value=0.0,
                    max_value=0.1,
                    required=False
                )
            ],
            supported_assets=[AssetType.STOCK_A],
            time_frames=[
                TimeFrame.DAY_1,
                TimeFrame.WEEK_1,
                TimeFrame.MONTH_1
            ],
            risk_level=RiskLevel.MEDIUM,
            tags=["momentum", "technical", "stock"],
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
            
            logger.info(f"复权价格动量策略初始化成功，参数: {self._parameters}")
            return True
        except Exception as e:
            logger.error(f"策略初始化失败: {e}")
            return False
    
    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        try:
            signals = []
            
            # 将市场数据转换为DataFrame
            df = market_data.to_dataframe()
            
            # 检查数据是否包含复权价格列，如果没有，使用close列作为替代
            price_column = 'adj_close'
            if price_column not in df.columns or df[price_column].isnull().all():
                logger.warning(f"数据缺少adj_close列，使用close列作为替代: {market_data.symbol}")
                price_column = 'close'
            
            # 获取参数
            lookback = self._parameters.get('lookback_period', 20)
            threshold = self._parameters.get('signal_strength_threshold', 0.01)
            
            # 计算动量
            df['momentum'] = df[price_column].pct_change(lookback)
            
            # 生成信号
            for i in range(len(df)):
                if i < lookback:  # 跳过初始数据
                    continue
                
                current_date = df.index[i]
                current_close = df.iloc[i]['close']
                momentum = df.iloc[i]['momentum']
                
                signal_type = SignalType.HOLD
                strength = 0.0
                reason = ""
                
                if momentum > threshold:
                    signal_type = SignalType.BUY
                    strength = min(momentum, 1.0)
                    reason = f"动量为正且超过阈值: {momentum:.4f}"
                elif momentum < -threshold:
                    signal_type = SignalType.SELL
                    strength = min(abs(momentum), 1.0)
                    reason = f"动量为负且超过阈值: {momentum:.4f}"
                
                if signal_type != SignalType.HOLD:
                    signal = Signal(
                        symbol=market_data.symbol,
                        signal_type=signal_type,
                        strength=strength,
                        timestamp=current_date,
                        price=current_close,
                        reason=reason,
                        metadata={
                            'momentum': momentum,
                            'lookback_period': lookback,
                            'price_column': price_column  # 添加使用的价格列信息
                        }
                    )
                    signals.append(signal)
            
            logger.info(f"生成了 {len(signals)} 个信号: {market_data.symbol}")
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
                    'signal_reason': signal.reason
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
    
    def calculate_performance(self, context: StrategyContext) -> PerformanceMetrics:
        """计算策略性能"""
        try:
            # 简化处理，实际应基于交易结果和持仓计算
            return PerformanceMetrics(
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
            if 'lookback_period' in parameters:
                value = parameters['lookback_period']
                if not isinstance(value, int) or value < 1 or value > 200:
                    return False, "lookback_period必须是1-200之间的整数"
            
            if 'top_n' in parameters:
                value = parameters['top_n']
                if not isinstance(value, int) or value < 1 or value > 100:
                    return False, "top_n必须是1-100之间的整数"
            
            return True, "参数验证通过"
        except Exception as e:
            return False, f"参数验证失败: {e}"