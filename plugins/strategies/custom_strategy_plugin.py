from loguru import logger
"""
自定义策略框架插件

提供策略开发基础框架，支持：
- Python策略开发
- 策略开发工具
- 策略模板
- 灵活的策略定制
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime
from dataclasses import dataclass
import inspect
import importlib.util
from pathlib import Path

# 项目内部导入
from core.strategy_extensions import (
    IStrategyPlugin, StrategyInfo, ParameterDef, Signal, TradeResult, Position,
    TradingPerformanceMetrics, StandardMarketData, StrategyContext,
    StrategyType, SignalType, TradeAction, TradeStatus, RiskLevel,
    AssetType, TimeFrame
)

logger = logger


class CustomStrategyBase:
    """自定义策略基类"""

    def __init__(self):
        self.name = "CustomStrategy"
        self.description = "自定义策略"
        self.parameters = {}
        self.positions = {}
        self.trades = []
        self.indicators = {}

    def initialize(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """初始化策略"""
        self.parameters = parameters
        return True

    def on_bar(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """K线更新事件"""
        return []

    def calculate_indicators(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """计算技术指标"""
        indicators = {}

        # 简单移动平均
        if 'sma_period' in self.parameters:
            period = self.parameters['sma_period']
            indicators['sma'] = df['close'].rolling(window=period).mean()

        # 指数移动平均
        if 'ema_period' in self.parameters:
            period = self.parameters['ema_period']
            indicators['ema'] = df['close'].ewm(span=period).mean()

        # RSI
        if 'rsi_period' in self.parameters:
            period = self.parameters['rsi_period']
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            indicators['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        if 'macd_fast' in self.parameters and 'macd_slow' in self.parameters:
            fast = self.parameters['macd_fast']
            slow = self.parameters['macd_slow']
            signal_period = self.parameters.get('macd_signal', 9)

            ema_fast = df['close'].ewm(span=fast).mean()
            ema_slow = df['close'].ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal_period).mean()

            indicators['macd'] = macd_line
            indicators['macd_signal'] = signal_line
            indicators['macd_histogram'] = macd_line - signal_line

        # 布林带
        if 'bollinger_period' in self.parameters:
            period = self.parameters['bollinger_period']
            std_dev = self.parameters.get('bollinger_std', 2.0)

            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()

            indicators['bollinger_upper'] = sma + (std * std_dev)
            indicators['bollinger_middle'] = sma
            indicators['bollinger_lower'] = sma - (std * std_dev)

        return indicators

    def generate_signal(self, symbol: str, signal_type: SignalType, price: float,
                        timestamp: datetime, reason: str = "", strength: float = 1.0) -> Signal:
        """生成交易信号"""
        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            timestamp=timestamp,
            price=price,
            reason=reason,
            metadata={'custom_strategy': True}
        )


class TrendFollowingTemplate(CustomStrategyBase):
    """趋势跟踪策略模板"""

    def __init__(self):
        super().__init__()
        self.name = "TrendFollowing"
        self.description = "基于移动平均线的趋势跟踪策略"

    def on_bar(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """K线更新事件"""
        df = market_data.to_dataframe()
        if len(df) < 20:  # 需要足够的数据
            return []

        # 计算指标
        indicators = self.calculate_indicators(df)

        signals = []
        current_price = df['close'].iloc[-1]
        current_time = df.index[-1]

        if 'sma' in indicators:
            sma = indicators['sma']

            # 价格突破均线买入
            if (df['close'].iloc[-1] > sma.iloc[-1] and
                    df['close'].iloc[-2] <= sma.iloc[-2]):

                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    timestamp=current_time,
                    reason="价格突破移动平均线"
                )
                signals.append(signal)

            # 价格跌破均线卖出
            elif (df['close'].iloc[-1] < sma.iloc[-1] and
                  df['close'].iloc[-2] >= sma.iloc[-2]):

                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    timestamp=current_time,
                    reason="价格跌破移动平均线"
                )
                signals.append(signal)

        return signals


class MeanReversionTemplate(CustomStrategyBase):
    """均值回归策略模板"""

    def __init__(self):
        super().__init__()
        self.name = "MeanReversion"
        self.description = "基于RSI的均值回归策略"

    def on_bar(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """K线更新事件"""
        df = market_data.to_dataframe()
        if len(df) < 20:
            return []

        # 计算指标
        indicators = self.calculate_indicators(df)

        signals = []
        current_price = df['close'].iloc[-1]
        current_time = df.index[-1]

        if 'rsi' in indicators:
            rsi = indicators['rsi']
            oversold = self.parameters.get('oversold_level', 30)
            overbought = self.parameters.get('overbought_level', 70)

            # RSI超卖买入
            if rsi.iloc[-1] < oversold:
                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    timestamp=current_time,
                    reason=f"RSI超卖 ({rsi.iloc[-1]:.2f})"
                )
                signals.append(signal)

            # RSI超买卖出
            elif rsi.iloc[-1] > overbought:
                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    timestamp=current_time,
                    reason=f"RSI超买 ({rsi.iloc[-1]:.2f})"
                )
                signals.append(signal)

        return signals


class MomentumTemplate(CustomStrategyBase):
    """动量策略模板"""

    def __init__(self):
        super().__init__()
        self.name = "Momentum"
        self.description = "基于MACD的动量策略"

    def on_bar(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """K线更新事件"""
        df = market_data.to_dataframe()
        if len(df) < 30:
            return []

        # 计算指标
        indicators = self.calculate_indicators(df)

        signals = []
        current_price = df['close'].iloc[-1]
        current_time = df.index[-1]

        if 'macd' in indicators and 'macd_signal' in indicators:
            macd = indicators['macd']
            signal_line = indicators['macd_signal']

            # MACD金叉买入
            if (macd.iloc[-1] > signal_line.iloc[-1] and
                    macd.iloc[-2] <= signal_line.iloc[-2]):

                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    timestamp=current_time,
                    reason="MACD金叉"
                )
                signals.append(signal)

            # MACD死叉卖出
            elif (macd.iloc[-1] < signal_line.iloc[-1] and
                  macd.iloc[-2] >= signal_line.iloc[-2]):

                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    timestamp=current_time,
                    reason="MACD死叉"
                )
                signals.append(signal)

        return signals


class BollingerBandsTemplate(CustomStrategyBase):
    """布林带策略模板"""

    def __init__(self):
        super().__init__()
        self.name = "BollingerBands"
        self.description = "基于布林带的突破策略"

    def on_bar(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """K线更新事件"""
        df = market_data.to_dataframe()
        if len(df) < 20:
            return []

        # 计算指标
        indicators = self.calculate_indicators(df)

        signals = []
        current_price = df['close'].iloc[-1]
        current_time = df.index[-1]

        if 'bollinger_upper' in indicators and 'bollinger_lower' in indicators:
            upper = indicators['bollinger_upper']
            lower = indicators['bollinger_lower']

            # 价格跌破下轨买入
            if (df['close'].iloc[-1] < lower.iloc[-1] and
                    df['close'].iloc[-2] >= lower.iloc[-2]):

                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    timestamp=current_time,
                    reason="价格跌破布林带下轨"
                )
                signals.append(signal)

            # 价格突破上轨卖出
            elif (df['close'].iloc[-1] > upper.iloc[-1] and
                  df['close'].iloc[-2] <= upper.iloc[-2]):

                signal = self.generate_signal(
                    symbol=market_data.symbol,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    timestamp=current_time,
                    reason="价格突破布林带上轨"
                )
                signals.append(signal)

        return signals


class CustomStrategyPlugin(IStrategyPlugin):
    """自定义策略框架插件"""

    def __init__(self):
        self.strategy_instance = None
        self.strategy_type = "TrendFollowing"
        self.current_positions = {}
        self.trade_history = []

        # 可用的策略模板
        self.strategy_templates = {
            'TrendFollowing': TrendFollowingTemplate,
            'MeanReversion': MeanReversionTemplate,
            'Momentum': MomentumTemplate,
            'BollingerBands': BollingerBandsTemplate,
        }

    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return {
            'name': 'Custom Strategy Plugin',
            'version': '1.0.0',
            'author': 'Custom Framework',
            'description': '自定义策略框架插件，提供灵活的Python策略开发环境',
            'supported_templates': list(self.strategy_templates.keys()),
            'supported_features': [
                'python_development', 'technical_indicators', 'strategy_templates',
                'flexible_customization', 'backtesting'
            ]
        }

    def get_strategy_info(self) -> StrategyInfo:
        """获取策略信息"""
        return StrategyInfo(
            name="custom_strategy",
            display_name="自定义策略",
            description="灵活的Python策略开发框架，支持多种策略模板和自定义开发",
            version="1.0.0",
            author="Custom Framework",
            strategy_type=StrategyType.CUSTOM,
            parameters=[
                ParameterDef("strategy_template", str, "TrendFollowing", "策略模板",
                             choices=list(self.strategy_templates.keys())),
                ParameterDef("sma_period", int, 20, "SMA周期", 5, 200),
                ParameterDef("ema_period", int, 12, "EMA周期", 5, 100),
                ParameterDef("rsi_period", int, 14, "RSI周期", 5, 50),
                ParameterDef("oversold_level", float, 30.0, "超卖水平", 10.0, 40.0),
                ParameterDef("overbought_level", float, 70.0, "超买水平", 60.0, 90.0),
                ParameterDef("macd_fast", int, 12, "MACD快线", 5, 30),
                ParameterDef("macd_slow", int, 26, "MACD慢线", 15, 50),
                ParameterDef("macd_signal", int, 9, "MACD信号线", 5, 20),
                ParameterDef("bollinger_period", int, 20, "布林带周期", 10, 50),
                ParameterDef("bollinger_std", float, 2.0, "布林带标准差", 1.0, 3.0),
                ParameterDef("position_size", int, 100, "仓位大小", 1, 10000),
            ],
            supported_assets=[AssetType.STOCK_A, AssetType.INDEX, AssetType.FUND, AssetType.CRYPTO],
            time_frames=[TimeFrame.MINUTE_1, TimeFrame.MINUTE_5, TimeFrame.MINUTE_15,
                         TimeFrame.MINUTE_30, TimeFrame.HOUR_1, TimeFrame.DAY_1],
            risk_level=RiskLevel.MEDIUM,
            tags=["custom", "python", "flexible", "templates"]
        )

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """初始化策略"""
        try:
            # 选择策略模板
            template_name = parameters.get('strategy_template', 'TrendFollowing')

            if template_name not in self.strategy_templates:
                logger.error(f"不支持的策略模板: {template_name}")
                return False

            # 创建策略实例
            strategy_class = self.strategy_templates[template_name]
            self.strategy_instance = strategy_class()

            # 初始化策略
            success = self.strategy_instance.initialize(context, parameters)

            if success:
                self.strategy_type = template_name
                logger.info(f"自定义策略初始化成功: {template_name}")

            return success

        except Exception as e:
            logger.error(f"自定义策略初始化失败: {e}")
            return False

    def generate_signals(self, market_data: Union[StandardMarketData, pd.DataFrame], context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        try:
            if not self.strategy_instance:
                return []

            # 处理不同类型的输入
            if isinstance(market_data, pd.DataFrame):
                # 如果输入是DataFrame，转换为StandardMarketData
                standard_market_data = StandardMarketData.from_dataframe(
                    market_data, 
                    symbol=context.symbol if hasattr(context, 'symbol') else "unknown"
                )
            else:
                standard_market_data = market_data

            # 调用策略实例的信号生成方法
            signals = self.strategy_instance.on_bar(standard_market_data, context)

            # 发布信号生成事件
            if signals:
                try:
                    from core.events import SignalGeneratedEvent, get_event_bus
                    event = SignalGeneratedEvent(
                        strategy_id=self.get_strategy_info().name,
                        strategy_name=self.get_strategy_info().display_name,
                        signals=[{
                            'signal_type': s.signal_type.value,
                            'symbol': s.symbol,
                            'strength': s.strength,
                            'timestamp': s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
                            'price': s.price,
                            'reason': s.reason
                        } for s in signals],
                        symbol=standard_market_data.symbol,
                        priority=1,
                        timestamp=datetime.now(),
                        source="custom_strategy",
                        data={'plugin_type': 'custom', 'template': self.strategy_type}
                    )
                    get_event_bus().publish(event)
                except Exception as event_error:
                    logger.warning(f"发布自定义策略信号事件失败: {event_error}")

            return signals

        except Exception as e:
            logger.error(f"自定义策略信号生成失败: {e}")
            return []

    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """执行交易"""
        try:
            # 生成交易ID
            trade_id = f"custom_{signal.symbol}_{int(signal.timestamp.timestamp())}"

            # 确定交易动作
            if signal.signal_type == SignalType.BUY:
                action = TradeAction.OPEN_LONG
            elif signal.signal_type == SignalType.SELL:
                action = TradeAction.CLOSE_LONG
            else:
                action = TradeAction.ADJUST

            # 计算交易数量
            position_size = 100  # 默认仓位
            if self.strategy_instance and hasattr(self.strategy_instance, 'parameters'):
                position_size = self.strategy_instance.parameters.get('position_size', 100)

            # 计算手续费
            commission = signal.price * position_size * context.commission_rate

            # 创建交易结果
            trade_result = TradeResult(
                trade_id=trade_id,
                symbol=signal.symbol,
                action=action,
                quantity=position_size,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=commission,
                status=TradeStatus.FILLED,
                metadata={'custom_strategy': True, 'template': self.strategy_type}
            )

            # 记录交易历史
            self.trade_history.append(trade_result)

            logger.info(f"自定义策略交易执行: {action.value} {signal.symbol} {position_size}@{signal.price}")
            return trade_result

        except Exception as e:
            logger.error(f"自定义策略交易执行失败: {e}")
            return TradeResult(
                trade_id=f"error_{int(signal.timestamp.timestamp())}",
                symbol=signal.symbol,
                action=TradeAction.OPEN_LONG,
                quantity=0,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=0,
                status=TradeStatus.ERROR,
                error_message=str(e)
            )

    def update_position(self, trade_result: TradeResult, context: StrategyContext) -> Position:
        """更新持仓"""
        symbol = trade_result.symbol

        # 获取当前持仓
        current_position = self.current_positions.get(symbol)

        if current_position is None:
            # 新建持仓
            if trade_result.action in [TradeAction.OPEN_LONG, TradeAction.OPEN_SHORT]:
                quantity = trade_result.quantity
                avg_price = trade_result.price
            else:
                quantity = 0
                avg_price = 0
        else:
            # 更新现有持仓
            if trade_result.action == TradeAction.OPEN_LONG:
                # 加仓
                total_cost = (current_position.quantity * current_position.avg_price +
                              trade_result.quantity * trade_result.price)
                quantity = current_position.quantity + trade_result.quantity
                avg_price = total_cost / quantity if quantity > 0 else 0
            elif trade_result.action == TradeAction.CLOSE_LONG:
                # 减仓
                quantity = max(0, current_position.quantity - trade_result.quantity)
                avg_price = current_position.avg_price
            else:
                quantity = current_position.quantity
                avg_price = current_position.avg_price

        # 计算市值和盈亏
        current_price = trade_result.price
        market_value = quantity * current_price
        unrealized_pnl = (current_price - avg_price) * quantity if quantity > 0 else 0

        # 创建新的持仓对象
        position = Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=0.0,
            timestamp=trade_result.timestamp,
            metadata={'custom_strategy': True, 'template': self.strategy_type}
        )

        # 更新持仓记录
        self.current_positions[symbol] = position

        return position

    def calculate_performance(self, context: StrategyContext) -> TradingPerformanceMetrics:
        """计算策略性能"""
        try:
            if not self.trade_history:
                return TradingPerformanceMetrics(
                    total_return=0.0, annual_return=0.0, sharpe_ratio=0.0,
                    max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                    total_trades=0, winning_trades=0, losing_trades=0,
                    avg_win=0.0, avg_loss=0.0,
                    start_date=context.start_date, end_date=context.end_date
                )

            # 计算基本统计
            total_trades = len(self.trade_history)

            # 计算盈亏（简化计算）
            profits = []
            for i in range(0, len(self.trade_history), 2):  # 假设买卖成对
                if i + 1 < len(self.trade_history):
                    buy_trade = self.trade_history[i]
                    sell_trade = self.trade_history[i + 1]
                    if (buy_trade.action == TradeAction.OPEN_LONG and
                            sell_trade.action == TradeAction.CLOSE_LONG):
                        profit = (sell_trade.price - buy_trade.price) * buy_trade.quantity
                        profits.append(profit)

            if not profits:
                profits = [0.0]

            winning_trades = len([p for p in profits if p > 0])
            losing_trades = len([p for p in profits if p < 0])

            total_profit = sum(profits)
            total_return = total_profit / context.initial_capital

            win_rate = winning_trades / len(profits) if profits else 0.0

            avg_win = np.mean([p for p in profits if p > 0]) if winning_trades > 0 else 0.0
            avg_loss = abs(np.mean([p for p in profits if p < 0])) if losing_trades > 0 else 0.0

            profit_factor = (avg_win * winning_trades) / (avg_loss * losing_trades) if avg_loss > 0 else 0.0

            return TradingPerformanceMetrics(
                total_return=total_return,
                annual_return=total_return,  # 简化计算
                sharpe_ratio=0.0,  # 需要更复杂的计算
                max_drawdown=0.0,  # 需要更复杂的计算
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                avg_win=avg_win,
                avg_loss=avg_loss,
                start_date=context.start_date,
                end_date=context.end_date,
                metadata={'custom_strategy': True, 'template': self.strategy_type}
            )

        except Exception as e:
            logger.error(f"自定义策略性能计算失败: {e}")
            return TradingPerformanceMetrics(
                total_return=0.0, annual_return=0.0, sharpe_ratio=0.0,
                max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, winning_trades=0, losing_trades=0,
                avg_win=0.0, avg_loss=0.0,
                start_date=context.start_date, end_date=context.end_date
            )

    def cleanup(self) -> None:
        """清理资源"""
        try:
            self.current_positions.clear()
            self.trade_history.clear()
            self.strategy_instance = None

            logger.info("自定义策略资源清理完成")

        except Exception as e:
            logger.error(f"自定义策略清理失败: {e}")

    def load_custom_strategy(self, strategy_file: str) -> bool:
        """加载自定义策略文件"""
        try:
            strategy_path = Path(strategy_file)
            if not strategy_path.exists():
                logger.error(f"策略文件不存在: {strategy_file}")
                return False

            # 动态加载策略模块
            spec = importlib.util.spec_from_file_location("custom_strategy", strategy_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找策略类
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, CustomStrategyBase) and
                        obj != CustomStrategyBase):

                    self.strategy_instance = obj()
                    logger.info(f"成功加载自定义策略: {name}")
                    return True

            logger.error("未找到有效的策略类")
            return False

        except Exception as e:
            logger.error(f"加载自定义策略失败: {e}")
            return False


# 导出的策略类
AVAILABLE_STRATEGIES = {
    'custom_trend_following': lambda: CustomStrategyPlugin(),
    'custom_mean_reversion': lambda: CustomStrategyPlugin(),
    'custom_momentum': lambda: CustomStrategyPlugin(),
    'custom_bollinger_bands': lambda: CustomStrategyPlugin(),
}


def get_available_strategies() -> Dict[str, callable]:
    """获取可用的自定义策略"""
    return AVAILABLE_STRATEGIES


def create_strategy(strategy_name: str) -> Optional[CustomStrategyPlugin]:
    """创建策略实例"""
    if strategy_name in AVAILABLE_STRATEGIES:
        return AVAILABLE_STRATEGIES[strategy_name]()
    return None
