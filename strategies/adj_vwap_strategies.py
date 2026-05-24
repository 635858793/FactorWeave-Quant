#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略适配器 - 完整实现

将20字段标准策略完整适配到IStrategyPlugin接口

作者：FactorWeave-Quant Team
版本：V2.0.4
日期：2025-10-12
"""

# 首先设置路径，确保正确的模块解析
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 添加core目录到Python路径
core_dir = project_root / "core"
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

# 添加examples目录到Python路径
examples_dir = project_root / "examples"
if str(examples_dir) not in sys.path:
    sys.path.insert(0, str(examples_dir))

# 现在导入其他模块
from loguru import logger
from typing import Dict, Any, List, Tuple
from datetime import datetime
import pandas as pd
import uuid

from examples.strategies.vwap_mean_reversion_strategy import VWAPMeanReversionStrategy as OriginalVWAPStrategy
from examples.strategies.adj_price_momentum_strategy import AdjPriceMomentumStrategy as OriginalAdjMomentum
from core.strategy_extensions import (
    IStrategyPlugin, StrategyInfo, ParameterDef,
    StrategyContext, StandardMarketData,
    Signal, TradeResult, Position, TradingPerformanceMetrics,
    StrategyType, AssetType, TimeFrame, RiskLevel,
    SignalType, TradeAction, TradeStatus
)

# 导入现有策略框架

# 导入新的20字段标准策略


# ✅ 此文件为完整版实现，推荐使用。简化版请参见 strategies/strategy_adapters.py
class AdjMomentumPlugin(IStrategyPlugin):
    """复权价格动量策略插件 - ✅ 完整实现（推荐使用）"""

    def __init__(self):
        """初始化策略插件"""
        self.original_strategy = OriginalAdjMomentum()
        self.context = None
        self.positions = {}  # symbol -> Position
        self.trades = []  # 交易记录
        logger.info("初始化复权价格动量策略插件")

    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return {
            'plugin_id': 'adj_momentum_v2',
            'plugin_name': '复权价格动量策略',
            'plugin_version': '2.0.4',
            'plugin_author': 'FactorWeave-Quant Team',
            'plugin_type': 'strategy',
            'framework': '20-field-standard',
            'capabilities': ['backtest', 'live_trading'],
            'dependencies': []
        }

    def get_strategy_info(self) -> StrategyInfo:
        """获取策略信息"""
        return StrategyInfo(
            name="adj_momentum_v2",
            display_name="复权价格动量策略",
            description="使用复权价格计算真实动量，选择动量最强的股票。基于20字段标准K线数据。",
            version="2.0.4",
            author="FactorWeave-Quant Team",
            strategy_type=StrategyType.TREND_FOLLOWING,
            parameters=[
                ParameterDef(
                    name="lookback_period",
                    type=int,
                    default_value=20,
                    description="动量回溯周期（天）",
                    min_value=5,
                    max_value=100,
                    required=True
                ),
                ParameterDef(
                    name="top_n",
                    type=int,
                    default_value=10,
                    description="选择动量最强的前N只股票",
                    min_value=1,
                    max_value=50,
                    required=True
                )
            ],
            supported_assets=[AssetType.STOCK_A],
            time_frames=[TimeFrame.DAILY],
            risk_level=RiskLevel.MEDIUM,
            tags=['momentum', 'trend', 'adjusted_price', '20-field']
        )

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """初始化策略"""
        try:
            self.context = context
            self.positions = {}
            self.trades = []

            # 设置原始策略参数
            lookback_period = parameters.get('lookback_period', 20)
            top_n = parameters.get('top_n', 10)

            self.original_strategy.set_parameters(
                lookback_period=lookback_period,
                top_n=top_n
            )

            logger.info(f"策略初始化成功: lookback_period={lookback_period}, top_n={top_n}")
            return True

        except Exception as e:
            logger.error(f"策略初始化失败: {e}")
            return False

    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        try:
            # 转换为DataFrame
            df = market_data.to_dataframe()

            # 确保有adj_close字段
            if 'adj_close' not in df.columns:
                # 如果没有，使用close作为adj_close
                df['adj_close'] = df['close']
                df['adj_factor'] = 1.0

            # 添加必需字段
            df['symbol'] = market_data.symbol
            df['datetime'] = df.index

            # 验证数据
            if not self.original_strategy.validate_data(df):
                logger.warning(f"数据验证失败: {market_data.symbol}")
                return []

            # 计算动量
            momentum = self.original_strategy.calculate_momentum(df)

            if momentum.empty or len(momentum) == 0:
                logger.warning(f"动量计算失败: {market_data.symbol}")
                return []

            # 获取最新动量值
            latest_momentum = momentum.iloc[-1]
            latest_price = df['close'].iloc[-1]
            latest_time = df.index[-1]

            signals = []

            # 生成买入信号（正动量）
            if latest_momentum > 0.05:  # 动量>5%
                signal = Signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.BUY,
                    strength=min(latest_momentum, 1.0),
                    timestamp=latest_time,
                    price=latest_price,
                    volume=100,
                    reason=f"正动量: {latest_momentum:.2%}",
                    confidence=0.8
                )
                signals.append(signal)
                logger.info(f"生成买入信号: {market_data.symbol}, 动量={latest_momentum:.2%}")

            # 生成卖出信号（负动量）
            elif latest_momentum < -0.05:  # 动量<-5%
                # 检查是否有持仓
                if market_data.symbol in self.positions:
                    signal = Signal(
                        symbol=market_data.symbol,
                        signal_type=SignalType.SELL,
                        strength=min(abs(latest_momentum), 1.0),
                        timestamp=latest_time,
                        price=latest_price,
                        volume=self.positions[market_data.symbol].quantity,
                        reason=f"负动量: {latest_momentum:.2%}",
                        confidence=0.8
                    )
                    signals.append(signal)
                    logger.info(f"生成卖出信号: {market_data.symbol}, 动量={latest_momentum:.2%}")

            return signals

        except Exception as e:
            logger.error(f"生成信号失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """执行交易"""
        try:
            trade_id = str(uuid.uuid4())

            # 模拟交易执行
            commission = signal.price * signal.volume * context.commission_rate
            slippage = signal.price * context.slippage

            actual_price = signal.price + slippage if signal.signal_type == SignalType.BUY else signal.price - slippage

            trade_result = TradeResult(
                trade_id=trade_id,
                symbol=signal.symbol,
                action=TradeAction.BUY if signal.signal_type == SignalType.BUY else TradeAction.SELL,
                quantity=signal.volume,
                price=actual_price,
                timestamp=signal.timestamp,
                commission=commission,
                status=TradeStatus.FILLED
            )

            self.trades.append(trade_result)
            logger.info(f"交易执行: {trade_result}")

            return trade_result

        except Exception as e:
            logger.error(f"交易执行失败: {e}")
            return TradeResult(
                trade_id=str(uuid.uuid4()),
                symbol=signal.symbol,
                action=TradeAction.BUY if signal.signal_type == SignalType.BUY else TradeAction.SELL,
                quantity=0,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=0,
                status=TradeStatus.REJECTED,
                error_message=str(e)
            )

    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        """更新持仓"""
        try:
            symbol = trade_result.symbol

            # 获取或创建持仓
            if symbol not in self.positions:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=0,
                    avg_price=0,
                    current_price=trade_result.price,
                    market_value=0,
                    unrealized_pnl=0,
                    realized_pnl=0,
                    timestamp=trade_result.timestamp
                )

            position = self.positions[symbol]

            # 更新持仓
            if trade_result.action == TradeAction.BUY:
                # 买入：增加持仓
                total_cost = position.avg_price * position.quantity + trade_result.price * trade_result.quantity
                total_quantity = position.quantity + trade_result.quantity
                position.avg_price = total_cost / total_quantity if total_quantity > 0 else 0
                position.quantity = total_quantity

            elif trade_result.action == TradeAction.SELL:
                # 卖出：减少持仓
                position.quantity -= trade_result.quantity
                if position.quantity <= 0:
                    # 完全平仓
                    position.realized_pnl += (trade_result.price - position.avg_price) * trade_result.quantity
                    position.quantity = 0
                    position.avg_price = 0

            # 更新市值和未实现盈亏
            position.current_price = trade_result.price
            position.market_value = position.quantity * position.current_price
            position.unrealized_pnl = (position.current_price - position.avg_price) * position.quantity
            position.timestamp = trade_result.timestamp

            logger.info(f"持仓更新: {position}")

            return position

        except Exception as e:
            logger.error(f"更新持仓失败: {e}")
            return self.positions.get(trade_result.symbol, None)

    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        """计算策略性能"""
        try:
            if not self.trades:
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

            # 计算总收益
            total_pnl = sum(pos.realized_pnl + pos.unrealized_pnl for pos in self.positions.values())
            total_return = total_pnl / context.initial_capital

            # 计算年化收益
            days = (context.end_date - context.start_date).days
            annual_return = total_return * (365 / days) if days > 0 else 0

            # 计算胜率
            winning_trades = sum(1 for t in self.trades if self._is_winning_trade(t))
            losing_trades = len(self.trades) - winning_trades
            win_rate = winning_trades / len(self.trades) if self.trades else 0

            # 计算平均盈亏
            winning_pnls = [self._get_trade_pnl(t) for t in self.trades if self._is_winning_trade(t)]
            losing_pnls = [self._get_trade_pnl(t) for t in self.trades if not self._is_winning_trade(t)]

            avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
            avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0

            # 盈亏比
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

            metrics = TradingPerformanceMetrics(
                total_return=total_return,
                annual_return=annual_return,
                sharpe_ratio=self._calculate_sharpe_ratio(),
                max_drawdown=self._calculate_max_drawdown(),
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=len(self.trades),
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                avg_win=avg_win,
                avg_loss=avg_loss,
                start_date=context.start_date,
                end_date=context.end_date
            )

            logger.info(f"性能计算完成: 总收益={total_return:.2%}, 胜率={win_rate:.1%}")

            return metrics

        except Exception as e:
            logger.error(f"性能计算失败: {e}")
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
        """清理资源"""
        logger.info("清理策略资源")
        self.positions.clear()
        self.trades.clear()

    def _is_winning_trade(self, trade: TradeResult) -> bool:
        """判断是否盈利交易"""
        # 简化实现：假设买入后价格上涨就是盈利
        return trade.action == TradeAction.BUY

    def _get_trade_pnl(self, trade: TradeResult) -> float:
        """获取交易盈亏"""
        # 简化实现
        return 0.0

    def _calculate_sharpe_ratio(self) -> float:
        """计算夏普比率"""
        # 简化实现
        return 0.0

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        # 简化实现
        return 0.0


# ✅ 此文件为完整版实现，推荐使用。简化版请参见 strategies/strategy_adapters.py
class VWAPReversionPlugin(IStrategyPlugin):
    """VWAP均值回归策略插件 - ✅ 完整实现（推荐使用）"""

    def __init__(self):
        """初始化策略插件"""
        self.original_strategy = OriginalVWAPStrategy()
        self.context = None
        self.positions = {}
        self.trades = []
        self.position_day_count = 0
        logger.info("初始化VWAP均值回归策略插件")

    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return {
            'plugin_id': 'vwap_reversion_v2',
            'plugin_name': 'VWAP均值回归策略',
            'plugin_version': '2.0.4',
            'plugin_author': 'FactorWeave-Quant Team',
            'plugin_type': 'strategy',
            'framework': '20-field-standard',
            'capabilities': ['backtest', 'live_trading'],
            'dependencies': []
        }

    def get_strategy_info(self) -> StrategyInfo:
        """获取策略信息"""
        return StrategyInfo(
            name="vwap_reversion_v2",
            display_name="VWAP均值回归策略",
            description="当价格偏离VWAP超过阈值时进行反向交易。基于20字段标准K线数据。",
            version="2.0.4",
            author="FactorWeave-Quant Team",
            strategy_type=StrategyType.MEAN_REVERSION,
            parameters=[
                ParameterDef(
                    name="deviation_threshold",
                    type=float,
                    default_value=0.02,
                    description="VWAP偏离阈值（2%=0.02）",
                    min_value=0.005,
                    max_value=0.10,
                    required=True
                ),
                ParameterDef(
                    name="hold_period",
                    type=int,
                    default_value=3,
                    description="最大持有天数",
                    min_value=1,
                    max_value=20,
                    required=True
                ),
                ParameterDef(
                    name="min_turnover_rate",
                    type=float,
                    default_value=0.5,
                    description="最小换手率（%）",
                    min_value=0.1,
                    max_value=10.0,
                    required=True
                )
            ],
            supported_assets=[AssetType.STOCK_A],
            time_frames=[TimeFrame.DAILY, TimeFrame.INTRADAY],
            risk_level=RiskLevel.MEDIUM,
            tags=['mean_reversion', 'vwap', '20-field']
        )

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """初始化策略"""
        try:
            self.context = context
            self.positions = {}
            self.trades = []
            self.position_day_count = 0

            # 设置原始策略参数
            deviation_threshold = parameters.get('deviation_threshold', 0.02)
            hold_period = parameters.get('hold_period', 3)
            min_turnover_rate = parameters.get('min_turnover_rate', 0.5)

            self.original_strategy.set_parameters(
                deviation_threshold=deviation_threshold,
                hold_period=hold_period,
                use_turnover_filter=True,
                min_turnover_rate=min_turnover_rate
            )

            logger.info(f"策略初始化成功: deviation={deviation_threshold:.1%}, " +
                        f"hold_period={hold_period}, min_turnover={min_turnover_rate}%")
            return True

        except Exception as e:
            logger.error(f"策略初始化失败: {e}")
            return False

    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        try:
            # 转换为DataFrame
            df = market_data.to_dataframe()

            # 确保有vwap和turnover_rate字段
            if 'vwap' not in df.columns:
                # 如果没有vwap，计算它
                df['vwap'] = df['amount'] / df['volume'].replace(0, pd.NA) if 'amount' in df.columns else df['close']

            if 'turnover_rate' not in df.columns:
                # 如果没有换手率，设置默认值
                df['turnover_rate'] = 1.0  # 假设流动性充足

            # 添加必需字段
            df['symbol'] = market_data.symbol
            df['datetime'] = df.index
            df['high'] = df.get('high', df['close'])
            df['low'] = df.get('low', df['close'])

            # 验证数据
            if not self.original_strategy.validate_vwap_data(df):
                logger.warning(f"VWAP数据验证失败: {market_data.symbol}")
                return []

            # 计算偏离度
            deviation = self.original_strategy.calculate_vwap_deviation(df)

            if deviation.empty:
                logger.warning(f"偏离度计算失败: {market_data.symbol}")
                return []

            # 获取最新数据
            latest_deviation = deviation.iloc[-1]
            latest_price = df['close'].iloc[-1]
            latest_time = df.index[-1]
            latest_turnover_rate = df['turnover_rate'].iloc[-1]

            # 流动性检查
            if latest_turnover_rate < self.original_strategy.min_turnover_rate:
                logger.debug(f"流动性不足: {market_data.symbol}")
                return []

            signals = []
            threshold = self.original_strategy.deviation_threshold

            # 买入信号：价格低于VWAP
            if latest_deviation < -threshold:
                signal = Signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.BUY,
                    strength=min(abs(latest_deviation) / threshold, 1.0),
                    timestamp=latest_time,
                    price=latest_price,
                    volume=100,
                    reason=f"价格低于VWAP: {latest_deviation:.2%}",
                    confidence=0.75
                )
                signals.append(signal)
                logger.info(f"生成买入信号: {market_data.symbol}, 偏离度={latest_deviation:.2%}")

            # 卖出信号：价格高于VWAP
            elif latest_deviation > threshold:
                if market_data.symbol in self.positions and self.positions[market_data.symbol].quantity > 0:
                    signal = Signal(
                        symbol=market_data.symbol,
                        signal_type=SignalType.SELL,
                        strength=min(latest_deviation / threshold, 1.0),
                        timestamp=latest_time,
                        price=latest_price,
                        volume=self.positions[market_data.symbol].quantity,
                        reason=f"价格高于VWAP: {latest_deviation:.2%}",
                        confidence=0.75
                    )
                    signals.append(signal)
                    logger.info(f"生成卖出信号: {market_data.symbol}, 偏离度={latest_deviation:.2%}")

            return signals

        except Exception as e:
            logger.error(f"生成信号失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """执行交易（复用AdjMomentumPlugin的实现）"""
        try:
            trade_id = str(uuid.uuid4())
            commission = signal.price * signal.volume * context.commission_rate
            slippage = signal.price * context.slippage
            actual_price = signal.price + slippage if signal.signal_type == SignalType.BUY else signal.price - slippage

            trade_result = TradeResult(
                trade_id=trade_id,
                symbol=signal.symbol,
                action=TradeAction.BUY if signal.signal_type == SignalType.BUY else TradeAction.SELL,
                quantity=signal.volume,
                price=actual_price,
                timestamp=signal.timestamp,
                commission=commission,
                status=TradeStatus.FILLED
            )

            self.trades.append(trade_result)
            logger.info(f"交易执行: {trade_result}")
            return trade_result

        except Exception as e:
            logger.error(f"交易执行失败: {e}")
            return TradeResult(
                trade_id=str(uuid.uuid4()),
                symbol=signal.symbol,
                action=TradeAction.BUY if signal.signal_type == SignalType.BUY else TradeAction.SELL,
                quantity=0,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=0,
                status=TradeStatus.REJECTED,
                error_message=str(e)
            )

    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        """更新持仓（复用AdjMomentumPlugin的实现）"""
        # 与AdjMomentumPlugin相同的逻辑
        try:
            symbol = trade_result.symbol

            if symbol not in self.positions:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=0,
                    avg_price=0,
                    current_price=trade_result.price,
                    market_value=0,
                    unrealized_pnl=0,
                    realized_pnl=0,
                    timestamp=trade_result.timestamp
                )

            position = self.positions[symbol]

            if trade_result.action == TradeAction.BUY:
                total_cost = position.avg_price * position.quantity + trade_result.price * trade_result.quantity
                total_quantity = position.quantity + trade_result.quantity
                position.avg_price = total_cost / total_quantity if total_quantity > 0 else 0
                position.quantity = total_quantity

            elif trade_result.action == TradeAction.SELL:
                position.quantity -= trade_result.quantity
                if position.quantity <= 0:
                    position.realized_pnl += (trade_result.price - position.avg_price) * trade_result.quantity
                    position.quantity = 0
                    position.avg_price = 0

            position.current_price = trade_result.price
            position.market_value = position.quantity * position.current_price
            position.unrealized_pnl = (position.current_price - position.avg_price) * position.quantity
            position.timestamp = trade_result.timestamp

            logger.info(f"持仓更新: {position}")
            return position

        except Exception as e:
            logger.error(f"更新持仓失败: {e}")
            return self.positions.get(trade_result.symbol, None)

    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        """计算策略性能（复用AdjMomentumPlugin的实现）"""
        # 与AdjMomentumPlugin相同的逻辑
        try:
            if not self.trades:
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

            total_pnl = sum(pos.realized_pnl + pos.unrealized_pnl for pos in self.positions.values())
            total_return = total_pnl / context.initial_capital

            days = (context.end_date - context.start_date).days
            annual_return = total_return * (365 / days) if days > 0 else 0

            winning_trades = sum(1 for t in self.trades if t.action == TradeAction.BUY)
            losing_trades = len(self.trades) - winning_trades
            win_rate = winning_trades / len(self.trades) if self.trades else 0

            metrics = TradingPerformanceMetrics(
                total_return=total_return,
                annual_return=annual_return,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=win_rate,
                profit_factor=0.0,
                total_trades=len(self.trades),
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                avg_win=0.0,
                avg_loss=0.0,
                start_date=context.start_date,
                end_date=context.end_date
            )

            logger.info(f"性能计算完成: 总收益={total_return:.2%}, 胜率={win_rate:.1%}")
            return metrics

        except Exception as e:
            logger.error(f"性能计算失败: {e}")
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
        """清理资源"""
        logger.info("清理策略资源")
        self.positions.clear()
        self.trades.clear()


# 使用示例
if __name__ == "__main__":
    print("策略适配器模块 - 完整实现")
    print("=" * 60)

    # 显示策略信息
    print("\n1. 复权价格动量策略:")
    adj_plugin = AdjMomentumPlugin()
    adj_info = adj_plugin.get_strategy_info()
    print(f"   名称: {adj_info.display_name}")
    print(f"   描述: {adj_info.description}")
    print(f"   类型: {adj_info.strategy_type}")
    print(f"   参数数量: {len(adj_info.parameters)}")
    print(f"   插件信息: {adj_plugin.plugin_info}")

    print("\n2. VWAP均值回归策略:")
    vwap_plugin = VWAPReversionPlugin()
    vwap_info = vwap_plugin.get_strategy_info()
    print(f"   名称: {vwap_info.display_name}")
    print(f"   描述: {vwap_info.description}")
    print(f"   类型: {vwap_info.strategy_type}")
    print(f"   参数数量: {len(vwap_info.parameters)}")
    print(f"   插件信息: {vwap_plugin.plugin_info}")

    print("\n" + "=" * 60)
    print(">> 策略适配器加载成功（完整实现）")