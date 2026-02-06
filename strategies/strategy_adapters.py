#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略适配器 - 将20字段标准策略适配到现有策略框架

功能：
1. 将简单策略接口适配到IStrategyPlugin接口
2. 使现有策略管理器可以使用新的20字段标准策略
3. 保持代码复用，避免重复开发

作者：FactorWeave-Quant Team
版本：V2.0.4
日期：2025-10-12
"""

from examples.strategies.vwap_mean_reversion_strategy import VWAPMeanReversionStrategy as OriginalVWAPStrategy
from examples.strategies.adj_price_momentum_strategy import AdjPriceMomentumStrategy as OriginalAdjMomentum
from core.strategy_extensions import (
    IStrategyPlugin, StrategyInfo, ParameterDef,
    StrategyContext, StandardMarketData, Signal, TradeResult,
    Position, TradingPerformanceMetrics,
    StrategyType, AssetType, TimeFrame, RiskLevel,
    SignalType, TradeAction, TradeStatus
)
from datetime import datetime
from typing import List, Dict, Any
import uuid
import sys
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入现有策略框架

# 导入新的20字段标准策略


class AdjMomentumPlugin(IStrategyPlugin):
    """
    复权价格动量策略插件（适配器）

    将简单的AdjPriceMomentumStrategy适配到IStrategyPlugin接口，
    使其可以被现有的策略管理系统使用。
    """

    def __init__(self):
        """初始化策略插件"""
        self.original_strategy = OriginalAdjMomentum()
        self.context = None
        logger.info("初始化复权价格动量策略插件")

    def get_strategy_info(self) -> StrategyInfo:
        """
        返回策略信息

        Returns:
            策略信息对象
        """
        return StrategyInfo(
            name="复权价格动量策略",
            display_name="复权价格动量策略",
            description="使用复权价格计算真实动量，选择动量最强的股票。基于20字段标准K线数据。",
            version="2.0.4",
            author="FactorWeave-Quant Team",
            strategy_type=StrategyType.TREND_FOLLOWING,
            supported_assets=[AssetType.STOCK_A],
            time_frames=[TimeFrame.DAY_1],
            parameters=[
                ParameterDef(
                    name="lookback_period",
                    type=int,
                    default_value=20,
                    description="计算动量的回溯天数（建议：10-60天）"
                ),
                ParameterDef(
                    name="top_n",
                    type=int,
                    default_value=10,
                    description="选择动量最强的前N只股票"
                )
            ]
        )

    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return {
            'name': 'AdjMomentumPlugin',
            'version': '2.0.4',
            'description': '复权价格动量策略插件',
            'author': 'FactorWeave-Quant Team'
        }

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """
        初始化策略

        Args:
            context: 策略上下文
            parameters: 策略参数
        """
        try:
            self.context = context
            self.parameters = parameters or {}

            # 设置原始策略的参数
            lookback_period = parameters.get('lookback_period', 20)
            top_n = parameters.get('top_n', 10)

            self.original_strategy.set_parameters(
                lookback_period=lookback_period,
                top_n=top_n
            )

            logger.info(f"策略初始化完成，参数: lookback_period={lookback_period}, top_n={top_n}")
            return True
        except Exception as e:
            logger.error(f"策略初始化失败: {e}")
            return False

    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """
        执行复权动量策略交易信号
        
        Args:
            signal: 交易信号
            context: 策略上下文
            
        Returns:
            交易结果
        """
        try:
            trade_id = str(uuid.uuid4())[:8]
            
            logger.info(f"复权动量执行交易信号: {trade_id} {signal.symbol} {signal.signal_type.value} "
                       f"{signal.volume}@{signal.price}")
            
            # 确定交易动作
            if signal.signal_type == SignalType.BUY:
                action = TradeAction.OPEN_LONG
            elif signal.signal_type == SignalType.SELL:
                action = TradeAction.CLOSE_LONG
            else:
                action = TradeAction.ADJUST
            
            return TradeResult(
                trade_id=trade_id,
                symbol=signal.symbol,
                action=action,
                quantity=signal.volume or 100,
                price=signal.price,
                timestamp=datetime.now(),
                commission=context.commission_rate * signal.price * (signal.volume or 100),
                status=TradeStatus.SUBMITTED,
                metadata={'strategy': 'AdjMomentum', 'reason': signal.reason}
            )
            
        except Exception as e:
            logger.error(f"复权动量交易执行失败: {e}")
            return TradeResult(
                trade_id=str(uuid.uuid4())[:8],
                symbol=signal.symbol,
                action=TradeAction.ADJUST,
                quantity=0,
                price=0.0,
                timestamp=datetime.now(),
                commission=0.0,
                status=TradeStatus.ERROR,
                error_message=str(e)
            )

    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """
        生成复权动量交易信号 - 符合IStrategyPlugin接口规范
        
        Args:
            market_data: 标准化市场数据
            context: 策略上下文
            
        Returns:
            交易信号列表
        """
        try:
            # 获取数据
            df = market_data.to_dataframe()
            if df.empty:
                return []

            # 模拟动量计算（假设数据中有必要字段）
            if len(df) < 20:  # 需要足够的历史数据
                return []

            # 获取回溯周期参数
            lookback_period = self.parameters.get('lookback_period', 20)
            
            # 计算动量（简化计算）
            if 'adj_close' in df.columns:
                price_series = df['adj_close']
            else:
                price_series = df['close']
            
            # 计算收益率作为动量指标
            momentum = (price_series.iloc[-1] / price_series.iloc[-lookback_period] - 1)
            
            signals = []
            latest_price = df.iloc[-1]['close']
            momentum_threshold = self.parameters.get('momentum_threshold', 0.02)
            
            # 正动量：买入信号
            if momentum > momentum_threshold:
                signal = Signal(
                    symbol=context.symbol,
                    signal_type=SignalType.BUY,
                    strength=min(0.9, max(0.1, momentum / 0.1)),
                    timestamp=datetime.now(),
                    price=latest_price,
                    volume=100,
                    reason=f"动量指标买入: {momentum:.2%}"
                )
                signals.append(signal)

            # 负动量：卖出信号
            elif momentum < -0.05:  # 动量下跌超过5%
                signal = Signal(
                    symbol=context.symbol,
                    signal_type=SignalType.SELL,
                    strength=min(0.9, max(0.1, abs(momentum) / 0.1)),
                    timestamp=datetime.now(),
                    price=latest_price,
                    volume=100,
                    reason=f"动量指标卖出: {momentum:.2%}"
                )
                signals.append(signal)

            return signals
            
        except Exception as e:
            logger.error(f"复权动量信号生成失败: {e}")
            return []

    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        """更新持仓信息"""
        try:
            # 这里应该实现实际的持仓计算逻辑
            # 现在返回模拟数据
            position = Position(
                symbol=trade_result.symbol,
                quantity=trade_result.quantity,
                avg_price=trade_result.price,
                current_price=trade_result.price,
                market_value=trade_result.price * trade_result.quantity,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                timestamp=datetime.now(),
                metadata={'strategy': 'AdjMomentum', 'trade_id': trade_result.trade_id}
            )
            return position
        except Exception as e:
            logger.error(f"持仓更新失败: {e}")
            # 返回空持仓
            return Position(
                symbol=trade_result.symbol,
                quantity=0.0,
                avg_price=0.0,
                current_price=0.0,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                timestamp=datetime.now()
            )

    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        """计算策略性能指标"""
        try:
            # 这里应该实现实际的性能计算逻辑
            # 现在返回模拟数据
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
                end_date=context.end_date,
                metadata={'strategy': 'AdjMomentum'}
            )
        except Exception as e:
            logger.error(f"性能计算失败: {e}")
            # 返回默认性能指标
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

    def on_trade(self, trade_result: TradeResult) -> None:
        """交易回调方法 - 测试兼容性"""
        try:
            logger.info(f"复权动量交易回调: {trade_result.trade_id} {trade_result.status}")
            # 在实际应用中，这里可以记录交易历史、更新持仓状态等
            pass
        except Exception as e:
            logger.error(f"复权动量交易回调失败: {e}")

    def on_order(self, order_result) -> None:
        """订单回调方法 - 测试兼容性"""
        try:
            logger.info(f"复权动量订单回调: {order_result}")
            # 在实际应用中，这里可以处理订单状态更新等
            pass
        except Exception as e:
            logger.error(f"复权动量订单回调失败: {e}")

    def cleanup(self) -> None:
        """清理复权动量策略资源"""
        logger.info("复权动量策略资源已清理")




class VWAPReversionPlugin(IStrategyPlugin):
    """
    VWAP均值回归策略插件（适配器）

    将简单的VWAPMeanReversionStrategy适配到IStrategyPlugin接口。
    """

    def __init__(self):
        """初始化策略插件"""
        self.original_strategy = OriginalVWAPStrategy()
        self.context = None
        self.position_day_count = 0  # 持仓天数计数
        logger.info("初始化VWAP均值回归策略插件")

    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return {
            'name': 'VWAPReversionPlugin',
            'version': '2.0.4',
            'description': 'VWAP均值回归策略插件',
            'author': 'FactorWeave-Quant Team'
        }

    def get_strategy_info(self) -> StrategyInfo:
        """
        返回策略信息

        Returns:
            策略信息对象
        """
        return StrategyInfo(
            name="VWAP均值回归策略",
            display_name="VWAP均值回归策略",
            description="当价格偏离VWAP超过阈值时进行反向交易，期待价格回归。基于20字段标准K线数据。",
            version="2.0.4",
            author="FactorWeave-Quant Team",
            strategy_type=StrategyType.MEAN_REVERSION,
            supported_assets=[AssetType.STOCK_A],
            time_frames=[TimeFrame.DAY_1, TimeFrame.HOUR_1],
            parameters=[
                ParameterDef(
                    name="deviation_threshold",
                    type=float,
                    default_value=0.02,
                    description="触发交易的VWAP偏离度（2%=0.02）"
                ),
                ParameterDef(
                    name="hold_period",
                    type=int,
                    default_value=3,
                    description="最大持有天数"
                ),
                ParameterDef(
                    name="min_turnover_rate",
                    type=float,
                    default_value=0.5,
                    description="流动性过滤阈值（%）"
                )
            ]
        )

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any] = None) -> bool:
        """
        初始化VWAP策略
        
        Args:
            context: 策略上下文
            parameters: 策略参数
            
        Returns:
            是否初始化成功
        """
        try:
            self.context = context
            self.parameters = parameters or {}

            # 设置原始策略的参数
            deviation_threshold = self.parameters.get('deviation_threshold', 0.02)
            hold_period = self.parameters.get('hold_period', 3)
            min_turnover_rate = self.parameters.get('min_turnover_rate', 0.5)

            # 模拟设置参数（原始策略可能没有此方法）
            # self.original_strategy.set_parameters(...)

            self.position_day_count = 0

            logger.info(f"VWAP策略初始化完成，参数: deviation={deviation_threshold:.1%}, " +
                       f"hold_period={hold_period}, min_turnover={min_turnover_rate}%")
            return True

        except Exception as e:
            logger.error(f"VWAP策略初始化失败: {e}")
            return False

    def initialize(self, context: StrategyContext) -> None:
        """
        兼容性初始化方法 - 将调用到initialize_strategy
        
        Args:
            context: 策略上下文
        """
        self.initialize_strategy(context)

    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        """更新持仓信息"""
        try:
            # 这里应该实现实际的持仓计算逻辑
            # 现在返回模拟数据
            position = Position(
                symbol=trade_result.symbol,
                quantity=trade_result.quantity,
                avg_price=trade_result.price,
                current_price=trade_result.price,
                market_value=trade_result.price * trade_result.quantity,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                timestamp=datetime.now(),
                metadata={'strategy': 'VWAPReversion', 'trade_id': trade_result.trade_id}
            )
            return position
        except Exception as e:
            logger.error(f"VWAP持仓更新失败: {e}")
            # 返回空持仓
            return Position(
                symbol=trade_result.symbol,
                quantity=0.0,
                avg_price=0.0,
                current_price=0.0,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                timestamp=datetime.now()
            )

    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        """计算策略性能指标"""
        try:
            # 这里应该实现实际的性能计算逻辑
            # 现在返回模拟数据
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
                end_date=context.end_date,
                metadata={'strategy': 'VWAPReversion'}
            )
        except Exception as e:
            logger.error(f"VWAP性能计算失败: {e}")
            # 返回默认性能指标
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

    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """
        执行VWAP策略交易信号
        
        Args:
            signal: 交易信号
            context: 策略上下文
            
        Returns:
            交易结果
        """
        try:
            trade_id = str(uuid.uuid4())[:8]
            
            logger.info(f"VWAP执行交易信号: {trade_id} {signal.symbol} {signal.signal_type.value} "
                       f"{signal.volume}@{signal.price}")
            
            # 确定交易动作
            if signal.signal_type == SignalType.BUY:
                action = TradeAction.OPEN_LONG
            elif signal.signal_type == SignalType.SELL:
                action = TradeAction.CLOSE_LONG
            else:
                action = TradeAction.ADJUST
            
            return TradeResult(
                trade_id=trade_id,
                symbol=signal.symbol,
                action=action,
                quantity=signal.volume or 100,
                price=signal.price,
                timestamp=datetime.now(),
                commission=context.commission_rate * signal.price * (signal.volume or 100),
                status=TradeStatus.SUBMITTED,
                metadata={'strategy': 'VWAPReversion', 'reason': signal.reason}
            )
            
        except Exception as e:
            logger.error(f"VWAP交易执行失败: {e}")
            return TradeResult(
                trade_id=str(uuid.uuid4())[:8],
                symbol=signal.symbol,
                action=TradeAction.ADJUST,
                quantity=0,
                price=0.0,
                timestamp=datetime.now(),
                commission=0.0,
                status=TradeStatus.ERROR,
                error_message=str(e)
            )

    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """
        生成VWAP交易信号 - 符合IStrategyPlugin接口规范
        
        Args:
            market_data: 标准化市场数据
            context: 策略上下文
            
        Returns:
            交易信号列表
        """
        try:
            # 获取数据
            df = market_data.to_dataframe()
            if df.empty:
                return []

            # 模拟VWAP计算（假设数据中有vwap字段）
            if 'vwap' not in df.columns:
                # 如果没有vwap列，用简化计算
                df['vwap'] = df['close'].rolling(window=20).mean()

            # 获取最新数据
            if len(df) < 2:
                return []

            latest_data = df.iloc[-1]
            latest_price = latest_data['close']
            latest_vwap = latest_data['vwap']
            
            # 计算偏离度
            if latest_vwap > 0:
                deviation = (latest_price - latest_vwap) / latest_vwap
            else:
                deviation = 0.0

            # 获取流动性数据（模拟）
            turnover_rate = latest_data.get('turnover_rate', 1.0)
            
            signals = []

            # 流动性检查
            if turnover_rate < 0.5:
                logger.debug(f"流动性不足: {turnover_rate:.2f}%")
                return signals

            # 开仓逻辑
            deviation_threshold = self.parameters.get('deviation_threshold', 0.02)
            hold_period = self.parameters.get('hold_period', 3)
            
            # 买入信号：价格低于VWAP
            if deviation < -deviation_threshold:
                signal = Signal(
                    symbol=context.symbol,
                    signal_type=SignalType.BUY,
                    strength=min(0.9, abs(deviation) / deviation_threshold),
                    timestamp=datetime.now(),
                    price=latest_price,
                    volume=100,
                    reason=f"VWAP偏离买入: {deviation:.2%}"
                )
                signals.append(signal)

            # 卖出信号：价格高于VWAP
            elif deviation > deviation_threshold:
                signal = Signal(
                    symbol=context.symbol,
                    signal_type=SignalType.SELL,
                    strength=min(0.9, deviation / deviation_threshold),
                    timestamp=datetime.now(),
                    price=latest_price,
                    volume=100,
                    reason=f"VWAP高估卖出: {deviation:.2%}"
                )
                signals.append(signal)

            # 平仓逻辑：回归VWAP附近或达到持有周期
            else:
                # 这里需要从上层获取持仓信息
                # 在实际应用中，持仓管理应该在更高层处理
                pass

            return signals

        except Exception as e:
            logger.error(f"VWAP信号生成失败: {e}")
            return []

    def on_trade(self, trade_result: TradeResult) -> None:
        """交易回调方法 - 测试兼容性"""
        try:
            logger.info(f"VWAP交易回调: {trade_result.trade_id} {trade_result.status}")
            # 在实际应用中，这里可以记录交易历史、更新持仓状态等
            pass
        except Exception as e:
            logger.error(f"VWAP交易回调失败: {e}")

    def on_order(self, order_result) -> None:
        """订单回调方法 - 测试兼容性"""
        try:
            logger.info(f"VWAP订单回调: {order_result}")
            # 在实际应用中，这里可以处理订单状态更新等
            pass
        except Exception as e:
            logger.error(f"VWAP订单回调失败: {e}")

    def cleanup(self) -> None:
        """清理VWAP策略资源"""
        self.position_day_count = 0
        logger.info("VWAP策略资源已清理")


# 策略注册工厂函数
def register_20field_strategies(strategy_service):
    """
    注册20字段标准策略到策略服务

    Args:
        strategy_service: 策略服务实例
    """
    try:
        # 注册复权动量策略
        strategy_service.register_strategy_plugin(
            'adj_momentum_v2',
            AdjMomentumPlugin
        )
        logger.info("✅ 已注册: 复权价格动量策略 (adj_momentum_v2)")

        # 注册VWAP均值回归策略
        strategy_service.register_strategy_plugin(
            'vwap_reversion_v2',
            VWAPReversionPlugin
        )
        logger.info("✅ 已注册: VWAP均值回归策略 (vwap_reversion_v2)")

        logger.success("✅ 20字段标准策略注册完成！")

    except Exception as e:
        logger.error(f"注册20字段策略失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


# 使用示例
if __name__ == "__main__":
    print("策略适配器模块")
    print("=" * 60)

    # 显示策略信息
    print("\n1. 复权价格动量策略:")
    adj_plugin = AdjMomentumPlugin()
    adj_info = adj_plugin.get_strategy_info()
    print(f"   名称: {adj_info.name}")
    print(f"   描述: {adj_info.description}")
    print(f"   类型: {adj_info.strategy_type}")
    print(f"   参数数量: {len(adj_info.parameters)}")

    print("\n2. VWAP均值回归策略:")
    vwap_plugin = VWAPReversionPlugin()
    vwap_info = vwap_plugin.get_strategy_info()
    print(f"   名称: {vwap_info.name}")
    print(f"   描述: {vwap_info.description}")
    print(f"   类型: {vwap_info.strategy_type}")
    print(f"   参数数量: {len(vwap_info.parameters)}")

    print("\n" + "=" * 60)
    print("✅ 策略适配器加载成功")
