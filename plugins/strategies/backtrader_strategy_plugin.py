from loguru import logger
"""
Backtrader策略插件

集成Backtrader框架，提供：
- Backtrader策略开发框架
- 回测引擎
- 数据源适配
- 指标计算
- 订单管理
- 性能分析
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass

# Backtrader相关导入
try:
    import backtrader as bt
    import backtrader.feeds as btfeeds
    import backtrader.indicators as btind
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False
    logger.warning("Backtrader未安装或无法导入，Backtrader策略插件将无法使用")

# 项目内部导入
from core.strategy_extensions import (
    IStrategyPlugin, StrategyInfo, ParameterDef, Signal, TradeResult, Position,
    PerformanceMetrics, StandardMarketData, StrategyContext,
    StrategyType, SignalType, TradeAction, TradeStatus, RiskLevel,
    AssetType, TimeFrame
)

logger = logger

if BACKTRADER_AVAILABLE:
    class BacktraderDataFeed(btfeeds.PandasData):
        """Backtrader数据源适配器"""

        params = (
            ('datetime', None),
            ('open', 'open'),
            ('high', 'high'),
            ('low', 'low'),
            ('close', 'close'),
            ('volume', 'volume'),
            ('openinterest', None),
        )
else:
    # 如果Backtrader不可用，创建占位符类
    class BacktraderDataFeed:
        """Backtrader数据源适配器占位符"""
        pass

if BACKTRADER_AVAILABLE:
    class BaseBacktraderStrategy(bt.Strategy):
        """基础Backtrader策略类"""

        params = (
            ('period', 20),
            ('position_size', 100),
        )
else:
    # 如果Backtrader不可用，创建占位符类
    class BaseBacktraderStrategy:
        """基础Backtrader策略类占位符"""
        pass

    def __init__(self):
        self.signals = []
        self.trades = []

    def log(self, txt, dt=None):
        """日志记录"""
        dt = dt or self.datas[0].datetime.date(0)
        logger.debug(f'{dt.isoformat()}: {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

    def notify_trade(self, trade):
        """交易状态通知"""
        if not trade.isclosed:
            return

        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')

        # 记录交易
        trade_info = {
            'entry_date': trade.dtopen,
            'exit_date': trade.dtclose,
            'entry_price': trade.price,
            'exit_price': trade.price,
            'size': trade.size,
            'pnl': trade.pnl,
            'pnlcomm': trade.pnlcomm
        }
        self.trades.append(trade_info)


class SMAStrategy(BaseBacktraderStrategy):
    """SMA交叉策略"""

    params = (
        ('short_period', 5),
        ('long_period', 20),
    )

    def __init__(self):
        super().__init__()
        self.sma_short = btind.SimpleMovingAverage(self.datas[0], period=self.params.short_period)
        self.sma_long = btind.SimpleMovingAverage(self.datas[0], period=self.params.long_period)
        self.crossover = btind.CrossOver(self.sma_short, self.sma_long)

    def next(self):
        if not self.position:
            if self.crossover > 0:  # 金叉
                self.buy(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'BUY',
                    'price': self.datas[0].close[0]
                })
        else:
            if self.crossover < 0:  # 死叉
                self.sell(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'SELL',
                    'price': self.datas[0].close[0]
                })


class MACDStrategy(BaseBacktraderStrategy):
    """MACD策略"""

    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
    )

    def __init__(self):
        super().__init__()
        self.macd = btind.MACD(self.datas[0],
                               period_me1=self.params.fast_period,
                               period_me2=self.params.slow_period,
                               period_signal=self.params.signal_period)

    def next(self):
        if not self.position:
            if self.macd.macd[0] > self.macd.signal[0] and self.macd.macd[-1] <= self.macd.signal[-1]:
                self.buy(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'BUY',
                    'price': self.datas[0].close[0]
                })
        else:
            if self.macd.macd[0] < self.macd.signal[0] and self.macd.macd[-1] >= self.macd.signal[-1]:
                self.sell(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'SELL',
                    'price': self.datas[0].close[0]
                })


class RSIStrategy(BaseBacktraderStrategy):
    """RSI策略"""

    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
    )

    def __init__(self):
        super().__init__()
        self.rsi = btind.RelativeStrengthIndex(self.datas[0], period=self.params.rsi_period)

    def next(self):
        if not self.position:
            if self.rsi[0] < self.params.oversold:
                self.buy(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'BUY',
                    'price': self.datas[0].close[0]
                })
        else:
            if self.rsi[0] > self.params.overbought:
                self.sell(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'SELL',
                    'price': self.datas[0].close[0]
                })


class BollingerBandsStrategy(BaseBacktraderStrategy):
    """布林带策略"""

    params = (
        ('period', 20),
        ('devfactor', 2.0),
    )

    def __init__(self):
        super().__init__()
        self.boll = btind.BollingerBands(self.datas[0],
                                         period=self.params.period,
                                         devfactor=self.params.devfactor)

    def next(self):
        if not self.position:
            if self.datas[0].close[0] < self.boll.lines.bot[0]:  # 价格跌破下轨
                self.buy(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'BUY',
                    'price': self.datas[0].close[0]
                })
        else:
            if self.datas[0].close[0] > self.boll.lines.top[0]:  # 价格突破上轨
                self.sell(size=self.params.position_size)
                self.signals.append({
                    'date': self.datas[0].datetime.date(0),
                    'type': 'SELL',
                    'price': self.datas[0].close[0]
                })


class BacktraderStrategyPlugin(IStrategyPlugin):
    """Backtrader策略插件"""

    def __init__(self):
        self.cerebro = None
        self.strategy_class = None
        self.strategy_params = {}
        self.results = None
        self.current_positions = {}
        self.trade_history = []

    @property
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件基本信息"""
        return {
            'name': 'Backtrader Strategy Plugin',
            'version': '1.0.0',
            'author': 'Backtrader Community',
            'description': 'Backtrader框架策略插件，提供专业的量化交易回测功能',
            'backtrader_available': BACKTRADER_AVAILABLE,
            'supported_strategies': ['SMA', 'MACD', 'RSI', 'BollingerBands'],
            'supported_features': [
                'backtesting', 'indicators', 'order_management',
                'performance_analysis', 'data_feeds'
            ]
        }

    def get_strategy_info(self) -> StrategyInfo:
        """获取策略信息"""
        return StrategyInfo(
            name="backtrader_strategy",
            display_name="Backtrader策略",
            description="基于Backtrader框架的量化交易策略，支持多种技术指标和回测功能",
            version="1.0.0",
            author="Backtrader Community",
            strategy_type=StrategyType.QUANTITATIVE,
            parameters=[
                ParameterDef("strategy_type", str, "SMA", "策略类型",
                             choices=["SMA", "MACD", "RSI", "BollingerBands"]),
                ParameterDef("short_period", int, 5, "短周期", 1, 50),
                ParameterDef("long_period", int, 20, "长周期", 10, 200),
                ParameterDef("rsi_period", int, 14, "RSI周期", 5, 50),
                ParameterDef("oversold", float, 30.0, "超卖水平", 10.0, 40.0),
                ParameterDef("overbought", float, 70.0, "超买水平", 60.0, 90.0),
                ParameterDef("position_size", int, 100, "仓位大小", 1, 10000),
                ParameterDef("initial_cash", float, 100000.0, "初始资金", 10000.0, 1000000.0),
            ],
            supported_assets=[AssetType.STOCK_A, AssetType.INDEX, AssetType.FUND],
            time_frames=[TimeFrame.DAY_1, TimeFrame.WEEK_1, TimeFrame.MONTH_1],
            risk_level=RiskLevel.MEDIUM,
            tags=["backtrader", "quantitative", "technical_analysis", "backtesting"]
        )

    def initialize_strategy(self, context: StrategyContext, parameters: Dict[str, Any]) -> bool:
        """初始化策略"""
        try:
            if not BACKTRADER_AVAILABLE:
                logger.error("Backtrader未安装，无法初始化策略")
                return False

            # 创建Cerebro引擎
            self.cerebro = bt.Cerebro()

            # 设置初始资金
            initial_cash = parameters.get('initial_cash', context.initial_capital)
            self.cerebro.broker.setcash(initial_cash)

            # 设置手续费
            self.cerebro.broker.setcommission(commission=context.commission_rate)

            # 选择策略类型
            strategy_type = parameters.get('strategy_type', 'SMA')

            if strategy_type == 'SMA':
                self.strategy_class = SMAStrategy
                self.strategy_params = {
                    'short_period': parameters.get('short_period', 5),
                    'long_period': parameters.get('long_period', 20),
                    'position_size': parameters.get('position_size', 100)
                }
            elif strategy_type == 'MACD':
                self.strategy_class = MACDStrategy
                self.strategy_params = {
                    'fast_period': parameters.get('short_period', 12),
                    'slow_period': parameters.get('long_period', 26),
                    'signal_period': 9,
                    'position_size': parameters.get('position_size', 100)
                }
            elif strategy_type == 'RSI':
                self.strategy_class = RSIStrategy
                self.strategy_params = {
                    'rsi_period': parameters.get('rsi_period', 14),
                    'oversold': parameters.get('oversold', 30.0),
                    'overbought': parameters.get('overbought', 70.0),
                    'position_size': parameters.get('position_size', 100)
                }
            elif strategy_type == 'BollingerBands':
                self.strategy_class = BollingerBandsStrategy
                self.strategy_params = {
                    'period': parameters.get('long_period', 20),
                    'devfactor': 2.0,
                    'position_size': parameters.get('position_size', 100)
                }
            else:
                logger.error(f"不支持的策略类型: {strategy_type}")
                return False

            # 添加策略到Cerebro
            self.cerebro.addstrategy(self.strategy_class, **self.strategy_params)

            # 添加分析器
            self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
            self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
            self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

            logger.info(f"Backtrader策略初始化成功: {strategy_type}")
            return True

        except Exception as e:
            logger.error(f"Backtrader策略初始化失败: {e}")
            return False

    def generate_signals(self, market_data: StandardMarketData, context: StrategyContext) -> List[Signal]:
        """生成交易信号"""
        try:
            if not BACKTRADER_AVAILABLE or not self.cerebro:
                return []

            # 转换数据格式
            df = market_data.to_dataframe()

            # 创建数据源
            data_feed = BacktraderDataFeed(dataname=df)
            self.cerebro.adddata(data_feed)

            # 运行回测
            self.results = self.cerebro.run()

            # 提取信号
            signals = []
            if self.results and len(self.results) > 0:
                strategy_result = self.results[0]

                # 从策略中获取信号
                for signal_info in strategy_result.signals:
                    signal_type = SignalType.BUY if signal_info['type'] == 'BUY' else SignalType.SELL

                    signal = Signal(
                        symbol=market_data.symbol,
                        signal_type=signal_type,
                        strength=1.0,
                        timestamp=datetime.combine(signal_info['date'], datetime.min.time()),
                        price=signal_info['price'],
                        reason=f"Backtrader {signal_info['type']} 信号",
                        metadata={'backtrader_strategy': True}
                    )
                    signals.append(signal)

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
                        symbol=market_data.symbol,
                        priority=1,
                        timestamp=datetime.now(),
                        source="backtrader_strategy",
                        data={'plugin_type': 'backtrader'}
                    )
                    get_event_bus().publish(event)
                except Exception as event_error:
                    logger.warning(f"发布Backtrader信号事件失败: {event_error}")

            return signals

        except Exception as e:
            logger.error(f"Backtrader信号生成失败: {e}")
            return []

    def execute_trade(self, signal: Signal, context: StrategyContext) -> TradeResult:
        """执行交易"""
        try:
            # 生成交易ID
            trade_id = f"backtrader_{signal.symbol}_{int(signal.timestamp.timestamp())}"

            # 确定交易动作
            if signal.signal_type == SignalType.BUY:
                action = TradeAction.OPEN_LONG
            elif signal.signal_type == SignalType.SELL:
                action = TradeAction.CLOSE_LONG
            else:
                action = TradeAction.ADJUST

            # 计算交易数量
            quantity = self.strategy_params.get('position_size', 100)

            # 计算手续费
            commission = signal.price * quantity * context.commission_rate

            # 创建交易结果
            trade_result = TradeResult(
                trade_id=trade_id,
                symbol=signal.symbol,
                action=action,
                quantity=quantity,
                price=signal.price,
                timestamp=signal.timestamp,
                commission=commission,
                status=TradeStatus.FILLED,
                metadata={'backtrader_strategy': True}
            )

            # 记录交易历史
            self.trade_history.append(trade_result)

            logger.info(f"Backtrader交易执行: {action.value} {signal.symbol} {quantity}@{signal.price}")
            return trade_result

        except Exception as e:
            logger.error(f"Backtrader交易执行失败: {e}")
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
            metadata={'backtrader_strategy': True}
        )

        # 更新持仓记录
        self.current_positions[symbol] = position

        return position

    def calculate_performance(self, context: StrategyContext) -> PerformanceMetrics:
        """计算策略性能"""
        try:
            if not self.results or len(self.results) == 0:
                return PerformanceMetrics(
                    total_return=0.0, annual_return=0.0, sharpe_ratio=0.0,
                    max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                    total_trades=0, winning_trades=0, losing_trades=0,
                    avg_win=0.0, avg_loss=0.0,
                    start_date=context.start_date, end_date=context.end_date
                )

            strategy_result = self.results[0]

            # 获取分析结果
            sharpe_ratio = 0.0
            max_drawdown = 0.0
            total_return = 0.0

            if hasattr(strategy_result.analyzers, 'sharpe'):
                sharpe_analysis = strategy_result.analyzers.sharpe.get_analysis()
                sharpe_ratio = sharpe_analysis.get('sharperatio', 0.0) or 0.0

            if hasattr(strategy_result.analyzers, 'drawdown'):
                drawdown_analysis = strategy_result.analyzers.drawdown.get_analysis()
                max_drawdown = drawdown_analysis.get('max', {}).get('drawdown', 0.0) or 0.0
                max_drawdown = abs(max_drawdown) / 100.0  # 转换为小数

            if hasattr(strategy_result.analyzers, 'returns'):
                returns_analysis = strategy_result.analyzers.returns.get_analysis()
                total_return = returns_analysis.get('rtot', 0.0) or 0.0

            # 交易分析
            total_trades = 0
            winning_trades = 0
            losing_trades = 0
            win_rate = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = 0.0

            if hasattr(strategy_result.analyzers, 'trades'):
                trades_analysis = strategy_result.analyzers.trades.get_analysis()
                total_trades = trades_analysis.get('total', {}).get('total', 0) or 0
                winning_trades = trades_analysis.get('won', {}).get('total', 0) or 0
                losing_trades = trades_analysis.get('lost', {}).get('total', 0) or 0

                if total_trades > 0:
                    win_rate = winning_trades / total_trades

                avg_win = trades_analysis.get('won', {}).get('pnl', {}).get('average', 0.0) or 0.0
                avg_loss = abs(trades_analysis.get('lost', {}).get('pnl', {}).get('average', 0.0) or 0.0)

                if avg_loss > 0:
                    profit_factor = (avg_win * winning_trades) / (avg_loss * losing_trades)

            return PerformanceMetrics(
                total_return=total_return,
                annual_return=total_return,  # 简化计算
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                avg_win=avg_win,
                avg_loss=avg_loss,
                start_date=context.start_date,
                end_date=context.end_date,
                metadata={'backtrader_strategy': True}
            )

        except Exception as e:
            logger.error(f"Backtrader性能计算失败: {e}")
            return PerformanceMetrics(
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
            self.strategy_params.clear()
            self.cerebro = None
            self.results = None

            logger.info("Backtrader策略资源清理完成")

        except Exception as e:
            logger.error(f"Backtrader策略清理失败: {e}")


# 导出的策略类
AVAILABLE_STRATEGIES = {
    'backtrader_sma': lambda: BacktraderStrategyPlugin(),
    'backtrader_macd': lambda: BacktraderStrategyPlugin(),
    'backtrader_rsi': lambda: BacktraderStrategyPlugin(),
    'backtrader_bollinger': lambda: BacktraderStrategyPlugin(),
}


def get_available_strategies() -> Dict[str, callable]:
    """获取可用的Backtrader策略"""
    if not BACKTRADER_AVAILABLE:
        return {}
    return AVAILABLE_STRATEGIES


def create_strategy(strategy_name: str) -> Optional[BacktraderStrategyPlugin]:
    """创建策略实例"""
    if strategy_name in AVAILABLE_STRATEGIES and BACKTRADER_AVAILABLE:
        return AVAILABLE_STRATEGIES[strategy_name]()
    return None
