import sys
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
from .containers import ServiceContainer
from loguru import logger
from .services.backtest_result_manager import BacktestResultManager, BacktestResult
import time

# 修复PyQt5导入
try:
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:
    # 兼容处理，避免在非GUI环境下导入失败
    class QObject:
        pass
    
    def pyqtSignal(*args, **kwargs):
        return lambda x: x

# 重构后的交易控制器 - 使用服务架构

class TradingController(QObject):
    """
    交易控制器 - 重构版本

    使用ServiceContainer获取TradingService，符合插件架构原则
    """
    signal_updated = pyqtSignal(dict)
    log_updated = pyqtSignal(str)
    position_updated = pyqtSignal(dict)
    risk_updated = pyqtSignal(dict)
    market_updated = pyqtSignal(dict)
    backtest_updated = pyqtSignal(dict)

    def __init__(self, service_container: ServiceContainer):
        super().__init__()
        self.service_container = service_container
        # 纯Loguru架构，移除log_manager依赖

        # 获取交易服务
        self._trading_service = None
        self._trading_engine = None
        self._unified_data_manager = None
        self._backtest_result_manager = None

        self.current_strategy = None
        self.order_queue = []

        # 初始化服务
        self._initialize_services()
        
        # 获取 BacktestResultManager 单例
        self._backtest_result_manager = self._get_backtest_result_manager()

    def _initialize_services(self):
        """初始化服务依赖"""
        try:
            # 获取交易服务
            from .services.trading_service import TradingService
            self._trading_service = self.service_container.resolve(TradingService)

            # 获取交易引擎
            from .trading_engine import TradingEngine
            self._trading_engine = self.service_container.resolve(TradingEngine)

            # 获取统一数据管理器
            from .services.unified_data_manager import UnifiedDataManager
            self._unified_data_manager = self.service_container.resolve(UnifiedDataManager)

            logger.info("交易控制器服务依赖初始化完成")

        except Exception as e:
            logger.error(f"交易控制器服务依赖初始化失败: {e}")

    def _get_backtest_result_manager(self):
        """从服务容器获取 BacktestResultManager 单例"""
        try:
            from core.services.backtest_result_manager import BacktestResultManager
            return self.service_container.resolve(BacktestResultManager)
        except Exception as e:
            logger.warning(f"无法从服务容器获取BacktestResultManager，回退到直接创建: {e}")
            return BacktestResultManager()

    def initialize(self):
        """Initialize the trading controller"""
        try:
            logger.info("Initializing trading controller...")

            if self._trading_service:
                # 初始化交易服务
                if hasattr(self._trading_service, 'initialize'):
                    self._trading_service.initialize()

            self.log_updated.emit("交易控制器初始化完成")

        except Exception as e:
            logger.error(f"Failed to initialize trading controller: {str(e)}")
            self.log_updated.emit(f"交易控制器初始化失败: {str(e)}")
            raise

    def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up trading controller...")

            if self._trading_service and hasattr(self._trading_service, 'cleanup'):
                self._trading_service.cleanup()

            if self._trading_engine and hasattr(self._trading_engine, 'cleanup'):
                self._trading_engine.cleanup()

            self.log_updated.emit("交易控制器清理完成")

        except Exception as e:
            logger.error(f"Failed to cleanup trading controller: {str(e)}")

    def handle_signal(self, signal):
        """处理交易信号"""
        try:
            # 添加风险控制检查
            if self.check_risk(signal):
                self.order_queue.append(signal)
                self.execute_orders()

        except Exception as e:
            self.log_updated.emit(f"处理交易信号失败: {str(e)}")

    def check_risk(self, signal) -> bool:
        """风险控制检查"""
        try:
            if not self._trading_service:
                self.log_updated.emit("风险检查失败: 交易服务不可用")
                return False

            # 获取当前风险状态
            portfolio = self._trading_service.get_portfolio()
            if portfolio:
                # 计算仓位比例
                total_assets = portfolio.total_assets
                market_value = portfolio.market_value

                if total_assets > 0:
                    exposure = market_value / total_assets
                    if exposure > 0.8:
                        self.log_updated.emit("风险警告: 仓位超过80%")
                        self.risk_updated.emit({
                            'type': 'high_exposure',
                            'exposure': exposure,
                            'message': '仓位超过80%'
                        })
                        return False

            return True

        except Exception as e:
            self.log_updated.emit(f"风险检查失败: {str(e)}")
            return False

    def execute_orders(self):
        """执行订单"""
        while self.order_queue:
            order = self.order_queue.pop(0)
            try:
                if not self._trading_service:
                    self.log_updated.emit("执行订单失败: 交易服务不可用")
                    continue

                # 使用交易服务执行订单
                if hasattr(self._trading_service, 'execute_signal'):
                    result = self._trading_service.execute_signal(order)
                    if result:
                        self.signal_updated.emit({'type': 'order', 'data': result})
                        self.log_updated.emit(f"订单执行成功: {order}")
                    else:
                        self.log_updated.emit(f"订单执行失败: {order}")
                else:
                    self.log_updated.emit("交易服务不支持信号执行")

            except Exception as e:
                self.log_updated.emit(f"订单执行失败: {str(e)}")

    def handle_log(self, message):
        """处理日志消息"""
        # 转发日志消息
        self.log_updated.emit(message)

    def run_backtest(self, params):
        """运行回测（重构版）"""
        try:
            # 添加参数验证
            if not validate_backtest_params(params):
                raise ValueError("无效的回测参数")

            if not self._trading_service:
                raise ValueError("交易服务不可用")

            # 使用交易服务的回测功能
            if hasattr(self._trading_service, 'run_backtest'):
                results = self._trading_service.run_backtest(params)
            else:
                # 降级到统一数据管理器
                if not self._unified_data_manager:
                    raise ValueError("数据管理器不可用")

                # 获取K线数据
                stock_code = params['stock']
                start_date = params.get('start_date')
                end_date = params.get('end_date')

                kdata = self._unified_data_manager.get_kdata(
                    stock_code,
                    start_date=start_date,
                    end_date=end_date
                )

                if kdata is None or (hasattr(kdata, 'empty') and kdata.empty):
                    raise ValueError("无法获取K线数据")

                # 简化的回测结果
                results = {
                    'trades': [],
                    'positions': [],
                    'performance': {
                        'total_return': 0.0,
                        'annual_return': 0.0,
                        'max_drawdown': 0.0,
                        'win_rate': 0.0,
                        'profit_factor': 1.0,
                        'sharpe_ratio': 0.0
                    },
                    'risk': {
                        'alpha': 0.0,
                        'beta': 1.0,
                        'information_ratio': 0.0,
                        'tracking_error': 0.0,
                        'var': 0.0
                    }
                }

            # 检查结果是否为None
            if results is None:
                self.log_updated.emit("回测没有产生有效结果")
                return None

            # 添加风险指标计算
            try:
                if 'risk_metrics' not in results:
                    results['risk_metrics'] = self.calculate_risk_metrics(results)
            except Exception as e:
                self.log_updated.emit(f"计算风险指标失败: {str(e)}")
                results['risk_metrics'] = {}

            # 将回测结果添加到回测结果管理器
            if results and isinstance(results, dict):
                # 构建回测结果对象
                stock_code = params.get('stock', '')
                stock_name = params.get('stock_name', '')
                strategy_name = params.get('strategy_name', '未知策略')
                
                backtest_result = BacktestResult(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    strategy_name=strategy_name,
                    backtest_time=time.time(),
                    backtest_results=results,
                    trades=results.get('trades', []),
                    duration=results.get('duration', 0),
                    is_professional=True
                )
                
                # 添加到回测结果管理器
                self._backtest_result_manager.add_result(backtest_result)

            # 发送信号更新UI
            self.backtest_updated.emit(results)
            self.signal_updated.emit({'type': 'backtest_complete', 'data': results})

            return results

        except Exception as e:
            error_msg = f"回测失败: {str(e)}"
            self.log_updated.emit(error_msg)
            return None

    def calculate_risk_metrics(self, results):
        """计算风险指标"""
        try:
            if not results or 'performance' not in results:
                return {
                    'max_drawdown': 0,
                    'sharpe_ratio': 0,
                    'var_95': 0
                }

            performance = results.get('performance', {})

            return {
                'max_drawdown': performance.get('max_drawdown', 0),
                'sharpe_ratio': performance.get('sharpe_ratio', 0),
                'var_95': performance.get('var', 0)
            }

        except Exception as e:
            self.log_updated.emit(f"计算风险指标失败: {str(e)}")
            return {
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'var_95': 0
            }

    def get_current_positions(self):
        """获取当前持仓"""
        try:
            if self._trading_service and hasattr(self._trading_service, 'get_portfolio'):
                portfolio = self._trading_service.get_portfolio()
                return portfolio.positions if portfolio else []
            elif self._trading_engine and hasattr(self._trading_engine, 'get_all_positions'):
                return self._trading_engine.get_all_positions()
            else:
                return []

        except Exception as e:
            self.log_updated.emit(f"获取持仓失败: {str(e)}")
            return []

    def get_trading_statistics(self):
        """获取交易统计"""
        try:
            if self._trading_service and hasattr(self._trading_service, 'get_portfolio'):
                portfolio = self._trading_service.get_portfolio()
                if portfolio:
                    return {
                        'total_assets': portfolio.total_assets,
                        'available_cash': portfolio.available_cash,
                        'market_value': portfolio.market_value,
                        'total_profit_loss': portfolio.total_profit_loss,
                        'total_profit_loss_pct': portfolio.total_profit_loss_pct,
                        'trade_count': len(portfolio.trade_history)
                    }
            return {}

        except Exception as e:
            self.log_updated.emit(f"获取交易统计失败: {str(e)}")
            return {}

def validate_backtest_params(params):
    """验证回测参数"""
    required_fields = ['stock']

    # 检查必填字段
    for field in required_fields:
        if field not in params:
            return False

    # 验证股票代码
    if not params['stock'] or not isinstance(params['stock'], str):
        return False

    return True
