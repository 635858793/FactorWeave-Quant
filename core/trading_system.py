from loguru import logger
"""
交易系统核心模块 - 重构版本

使用插件架构，通过UnifiedDataManager和TradingService提供功能
不再直接调用hikyuu API，符合插件架构原则
"""
from typing import *
from datetime import datetime
import pandas as pd
import numpy as np
from dataclasses import asdict

# LogManager, LogLevel 已删除 - 使用纯Loguru架构
from .containers import ServiceContainer
from core.performance import measure_performance as monitor_performance

class TradingSystem:
    """
    交易系统类 - 重构版本

    通过服务容器获取所需服务，不直接调用hikyuu API
    所有数据访问通过UnifiedDataManager，符合插件架构原则
    """

    def __init__(self, service_container: ServiceContainer = None):
        """初始化交易系统"""
        self.service_container = service_container
        self.current_stock = None
        self.current_kdata = None
        self.current_signals = []
        self.current_positions = []

        # 服务依赖
        self._unified_data_manager = None
        self._trading_service = None
        self._unified_indicator_service = None

        # 初始化服务
        if self.service_container:
            self._initialize_services()

    def _initialize_services(self):
        """初始化服务依赖"""
        try:
            # 获取统一数据管理器
            from .services.unified_data_manager import UnifiedDataManager
            self._unified_data_manager = self.service_container.resolve(UnifiedDataManager)

            # 获取交易服务
            from .services.trading_service import TradingService
            self._trading_service = self.service_container.resolve(TradingService)

            # 获取指标服务
            from .services.unified_indicator_service import UnifiedIndicatorService
            self._unified_indicator_service = self.service_container.resolve(UnifiedIndicatorService)

            logger.info("交易系统服务依赖初始化完成")

        except Exception as e:
            logger.error(f"交易系统服务依赖初始化失败: {e}")

    def set_stock(self, stock_code: str):
        """设置当前股票

        Args:
            stock_code: 股票代码
        """
        try:
            self.current_stock = stock_code
            self.current_kdata = None
            self.current_signals = []
            self.current_positions = []

            logger.info(f"设置当前股票: {stock_code}")

        except Exception as e:
            logger.error(f"设置股票失败: {str(e)}")

    def load_kdata(self, start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   ktype: str = 'D'):
        """加载K线数据，使用插件架构"""
        try:
            if not self.current_stock:
                raise ValueError("未设置股票")

            if not self._unified_data_manager:
                raise ValueError("统一数据管理器不可用")

            # 使用统一数据管理器获取K线数据
            kdata = self._unified_data_manager.get_kdata(
                self.current_stock,
                start_date=start_date,
                end_date=end_date,
                period=ktype
            )

            if kdata is not None and not kdata.empty:
                self.current_kdata = kdata
                logger.info(f"加载K线数据成功: {self.current_stock}, 记录数: {len(kdata)}")
            else:
                logger.warning(f"K线数据为空: {self.current_stock}")
                self.current_kdata = pd.DataFrame()

        except Exception as e:
            logger.error(f"加载K线数据失败: {str(e)}")
            self.current_kdata = pd.DataFrame()

    def calculate_signals(self, strategy: str = 'MA策略') -> List[Dict[str, Any]]:
        """
        计算交易信号 - 使用插件架构
        """
        try:
            if self.current_kdata is None or self.current_kdata.empty:
                raise ValueError("未加载K线数据")

            # 使用策略服务计算信号
            if self._trading_service and hasattr(self._trading_service, 'calculate_signals'):
                signals = self._trading_service.calculate_signals(
                    stock_code=self.current_stock,
                    kdata=self.current_kdata,
                    strategy=strategy
                )
            else:
                # 降级到简单信号计算
                signals = self._calculate_simple_signals(strategy)

            self.current_signals = signals
            return signals

        except Exception as e:
            logger.error(f"计算交易信号失败: {str(e)}")
            return []

    def _calculate_simple_signals(self, strategy: str) -> List[Dict[str, Any]]:
        """简单信号计算（降级方案）"""
        try:
            if not self._unified_indicator_service:
                return []

            # 使用统一指标服务计算指标
            from .indicator_extensions import StandardKlineData

            standard_kdata = StandardKlineData.from_dataframe(self.current_kdata, self.current_stock)

            signals = []

            if strategy == 'MA策略':
                # 计算移动平均线
                ma5_result = self._unified_indicator_service.calculate_indicator(
                    "MA", standard_kdata, {"period": 5}
                )
                ma20_result = self._unified_indicator_service.calculate_indicator(
                    "MA", standard_kdata, {"period": 20}
                )

                if ma5_result and ma20_result and ma5_result.data and ma20_result.data:
                    ma5_values = ma5_result.data
                    ma20_values = ma20_result.data

                    ma5 = np.array(ma5_values, dtype=np.float64)
                    ma20 = np.array(ma20_values, dtype=np.float64)
                    n = min(len(ma5), len(ma20))

                    ma5_prev = np.roll(ma5, 1)
                    ma20_prev = np.roll(ma20, 1)

                    golden_cross = (ma5 > ma20) & (ma5_prev <= ma20_prev)
                    dead_cross = (ma5 < ma20) & (ma5_prev >= ma20_prev)

                    golden_cross[0] = False
                    dead_cross[0] = False

                    has_datetime_index = hasattr(self.current_kdata.index, '__getitem__')
                    close_col = self.current_kdata['close']

                    for i in np.where(golden_cross)[0]:
                        if i >= n:
                            continue
                        signals.append({
                            'datetime': self.current_kdata.index[i] if has_datetime_index else datetime.now(),
                            'signal': 'BUY',
                            'price': float(close_col.iloc[i]),
                            'reason': 'MA5上穿MA20'
                        })

                    for i in np.where(dead_cross)[0]:
                        if i >= n:
                            continue
                        signals.append({
                            'datetime': self.current_kdata.index[i] if has_datetime_index else datetime.now(),
                            'signal': 'SELL',
                            'price': float(close_col.iloc[i]),
                            'reason': 'MA5下穿MA20'
                        })

            return signals

        except Exception as e:
            logger.error(f"简单信号计算失败: {e}")
            return []

    @monitor_performance(name="run_backtest")
    def run_backtest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测 - 使用插件架构

        Args:
            params: 回测参数

        Returns:
            回测结果
        """
        try:
            if self.current_kdata is None or self.current_kdata.empty:
                raise ValueError("未加载K线数据")

            # 使用交易服务的回测功能
            if self._trading_service and hasattr(self._trading_service, 'run_backtest'):
                results = self._trading_service.run_backtest(params)
                if results:
                    return results

            # 降级到简单回测
            return self._run_simple_backtest(params)

        except Exception as e:
            logger.error(f"运行回测失败: {str(e)}")
            return {}

    def _run_simple_backtest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """简单回测实现（降级方案）"""
        try:
            # 计算信号
            strategy = params.get('strategy', 'MA策略')
            signals = self.calculate_signals(strategy)

            # 简化的回测逻辑
            initial_cash = params.get('initial_cash', 100000)
            commission_rate = params.get('commission_rate', 0.0003)

            cash = initial_cash
            position = 0
            trades = []

            for signal in signals:
                if signal['signal'] == 'BUY' and cash > 0:
                    # 买入
                    price = signal['price']
                    quantity = int(cash * 0.95 / price / 100) * 100  # 95%资金买入，整手
                    if quantity > 0:
                        cost = quantity * price * (1 + commission_rate)
                        if cost <= cash:
                            cash -= cost
                            position += quantity
                            trades.append({
                                'time': signal['datetime'],
                                'business': 'BUY',
                                'stock': self.current_stock,
                                'price': price,
                                'quantity': quantity,
                                'cost': cost,
                                'cash': cash
                            })

                elif signal['signal'] == 'SELL' and position > 0:
                    # 卖出
                    price = signal['price']
                    quantity = position
                    revenue = quantity * price * (1 - commission_rate)
                    cash += revenue
                    position = 0
                    trades.append({
                        'time': signal['datetime'],
                        'business': 'SELL',
                        'stock': self.current_stock,
                        'price': price,
                        'quantity': quantity,
                        'cost': revenue,
                        'cash': cash
                    })

            # 计算最终价值
            final_price = float(self.current_kdata.iloc[-1]['close']) if not self.current_kdata.empty else 0
            final_value = cash + position * final_price
            total_return = (final_value - initial_cash) / initial_cash

            return {
                'trades': trades,
                'positions': [{'stock': self.current_stock, 'quantity': position, 'cost': position * final_price}] if position > 0 else [],
                'performance': {
                    'total_return': total_return,
                    'annual_return': total_return,  # 简化
                    'max_drawdown': 0.0,  # 简化
                    'win_rate': 0.5,  # 简化
                    'profit_factor': 1.0 + total_return,
                    'sharpe_ratio': total_return  # 简化
                },
                'risk': {
                    'alpha': 0.0,
                    'beta': 1.0,
                    'information_ratio': 0.0,
                    'tracking_error': 0.0,
                    'var': 0.0
                }
            }

        except Exception as e:
            logger.error(f"简单回测失败: {e}")
            return {}

    def get_market_overview(self) -> Dict[str, Any]:
        """获取市场概览 - 使用插件架构

        Returns:
            市场概览数据
        """
        try:
            if not self._unified_data_manager:
                return {}

            # 获取指数数据
            index_data = {}
            try:
                # 获取主要指数
                for index_code in ['000001', '399001', '399006']:  # 上证指数、深证成指、创业板指
                    index_kdata = self._unified_data_manager.get_kdata(index_code, period='D', count=1)
                    if index_kdata is not None and not index_kdata.empty:
                        latest = index_kdata.iloc[-1]
                        index_data[index_code] = {
                            'close': float(latest['close']),
                            'change': float(latest['close'] - latest['open']),
                            'change_pct': float((latest['close'] - latest['open']) / latest['open'] * 100)
                        }
            except Exception as e:
                logger.warning(f"获取指数数据失败: {e}")

            # 获取市场统计
            market_stats = {}
            try:
                stock_list = self._unified_data_manager.get_stock_list()
                if stock_list is not None and not stock_list.empty:
                    market_stats = {
                        'total': len(stock_list),
                        'up_count': 0,  # 简化
                        'down_count': 0,  # 简化
                        'flat_count': 0  # 简化
                    }
            except Exception as e:
                logger.warning(f"获取市场统计失败: {e}")

            # 计算市场情绪
            sentiment = 0.5  # 默认中性
            if market_stats.get('total', 0) > 0:
                sentiment = market_stats.get('up_count', 0) / market_stats['total']

            return {
                'indices': index_data,
                'statistics': market_stats,
                'sentiment': sentiment
            }

        except Exception as e:
            logger.error(f"获取市场概览失败: {str(e)}")
            return {}

    def get_fund_flow(self) -> Dict[str, Any]:
        """获取资金流向 - 插件架构版本

        Returns:
            资金流向数据
        """
        try:
            # 简化实现，返回空数据
            # 实际实现需要接入资金流向数据源插件
            return {
                'north_flow': [],
                'industry_flow': [],
                'concept_flow': []
            }

        except Exception as e:
            logger.error(f"获取资金流向失败: {str(e)}")
            return {}

# 创建全局交易系统实例的工厂函数
def create_trading_system(service_container: ServiceContainer = None) -> TradingSystem:
    """创建交易系统实例"""
    return TradingSystem(service_container)

# 保持向后兼容性的全局实例
trading_system = None

def get_trading_system() -> Optional[TradingSystem]:
    """获取全局交易系统实例"""
    global trading_system
    return trading_system

def initialize_trading_system(service_container: ServiceContainer) -> TradingSystem:
    """初始化全局交易系统实例"""
    global trading_system
    if trading_system is None:
        trading_system = create_trading_system(service_container)
    return trading_system
