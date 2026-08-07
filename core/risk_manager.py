"""
风险管理模块
"""
import numpy as np
import pandas as pd
from loguru import logger
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from core.performance import measure_performance as monitor_performance
from core.config import ConfigManager, config_manager

class RiskManager:
    """风险管理类

    设计债务（TECH_DEBT-001）：持仓三分问题
    本模块通过 self.current_positions: dict 维护了独立的持仓数据结构，
    与 core/position_manager.py 和 core/trading_engine.py 中的持仓数据无同步机制。
    三个模块各自独立维护持仓，可能导致数据不一致。
    建议通过事件总线（EventBus）同步：当任一处持仓变更时，发布
    'position_updated' 事件，由其他两模块订阅并更新。
    """

    def __init__(self):
        """初始化风险管理器"""
        # 纯Loguru架构，移除log_manager依赖
        self.initialized = False

        # 风险控制参数
        self.max_position_size = 0.3  # 最大持仓比例
        self.max_single_position = 0.1  # 单个股票最大持仓比例
        self.stop_loss = 0.05  # 止损比例
        self.max_drawdown = 0.2  # 最大回撤限制

        # 当前状态
        self.current_positions = {}  # 当前持仓
        self.current_equity = 0  # 当前权益
        self.peak_equity = 0  # 最高权益

        # 监控桥接
        self._monitor = None

    def initialize(self) -> bool:
        """初始化风险管理器"""
        try:
            # 加载风险控制参数
            self._load_risk_params()

            self.initialized = True
            logger.info("风险管理器初始化成功")
            return True

        except Exception as e:
            logger.info(f"风险管理器初始化失败: {str(e)}")
            return False

    def _load_risk_params(self):
        """加载风险控制参数"""
        try:
            risk_config = config_manager.get('risk', {})

            self.max_position_size = risk_config.get(
                'max_position_size',
                self.max_position_size
            )
            self.max_single_position = risk_config.get(
                'max_single_position',
                self.max_single_position
            )
            self.stop_loss = risk_config.get(
                'stop_loss',
                self.stop_loss
            )
            self.max_drawdown = risk_config.get(
                'max_drawdown',
                self.max_drawdown
            )

            logger.info(
                f"风险控制参数加载成功: "
                f"最大持仓比例={self.max_position_size}, "
                f"单股最大持仓={self.max_single_position}, "
                f"止损比例={self.stop_loss}, "
                f"最大回撤={self.max_drawdown}"
            )

        except Exception as e:
            logger.error(f"加载风险控制参数失败: {str(e)}")
            logger.warning("使用默认风险控制参数")

    def get_risk_params(self) -> Dict[str, Any]:
        """获取当前风险控制参数"""
        return {
            'max_position_size': self.max_position_size,
            'max_single_position': self.max_single_position,
            'stop_loss': self.stop_loss,
            'max_drawdown': self.max_drawdown
        }

    def update_risk_params(self, **kwargs) -> bool:
        """更新风险控制参数"""
        try:
            valid_params = {
                'max_position_size': float,
                'max_single_position': float,
                'stop_loss': float,
                'max_drawdown': float
            }

            for param, expected_type in valid_params.items():
                if param in kwargs:
                    value = kwargs[param]
                    if not isinstance(value, (int, float)):
                        raise TypeError(f"{param} 必须是数字类型")
                    if param in ['max_position_size', 'max_single_position', 'max_drawdown']:
                        if not 0 < value <= 1:
                            raise ValueError(f"{param} 必须在 (0, 1] 范围内")
                    if param == 'stop_loss':
                        if not 0 < value <= 1:
                            raise ValueError(f"{param} 必须在 (0, 1] 范围内")

                    setattr(self, param, float(value))

            logger.info(f"风险控制参数已更新: {kwargs}")
            return True

        except Exception as e:
            logger.error(f"更新风险控制参数失败: {str(e)}")
            return False

    @monitor_performance("check_risk")
    def check_risk(self, signal: Dict) -> bool:
        """
        检查交易信号的风险

        Args:
            signal: 交易信号

        Returns:
            bool: 是否通过风险检查
        """
        allowed, reason = self.check_order(signal)
        if not allowed:
            logger.warning(f"风险检查未通过: {reason}")
        return allowed

    def check_order(self, signal: Dict) -> tuple:
        """
        检查交易信号的风险（带原因返回）

        Args:
            signal: 交易信号

        Returns:
            tuple: (allowed: bool, reason: str)
        """
        try:
            if not self.initialized:
                return False, "风险管理器未初始化"

            if self.current_equity <= 0:
                return False, "当前权益为零或负数"

            if not self._check_position_limit(signal):
                return False, "超过持仓限制"

            if not self._check_stop_loss(signal):
                return False, "触发止损条件"

            if not self._check_drawdown():
                return False, "超过最大回撤限制"

            return True, "风险检查通过"

        except Exception as e:
            logger.error(f"风险检查失败: {str(e)}")
            return False, str(e)

    def check_trade(self, signal: float, price: float, current_equity: float) -> bool:
        """回测引擎集成的交易风险检查（简化接口）

        Args:
            signal: 交易信号值 (1=买入, -1=卖出, 0=持仓)
            price: 当前价格
            current_equity: 当前权益

        Returns:
            bool: 是否通过风险检查
        """
        try:
            if signal == 0:
                return True

            if not self.initialized:
                self.initialized = True

            self.current_equity = current_equity

            signal_type = 'buy' if signal > 0 else 'sell'
            signal_dict = {
                'type': signal_type,
                'stock_code': 'backtest',
                'amount': current_equity * self.max_single_position,
                'price': price
            }

            if not self._check_position_limit(signal_dict):
                return False

            if not self._check_stop_loss(signal_dict):
                return False

            if not self._check_drawdown():
                return False

            return True

        except Exception as e:
            logger.error(f"回测交易风险检查失败: {str(e)}")
            return False

    def _check_position_limit(self, signal: Dict) -> bool:
        """检查持仓限制"""
        try:
            if signal['type'] == 'buy':
                if self.current_equity <= 0:
                    logger.warning("当前权益为零或负数，跳过持仓限制检查")
                    return False

                # 计算当前总持仓市值
                total_position_value = sum(
                    pos.get('amount', 0) if isinstance(pos, dict) else pos
                    for pos in self.current_positions.values()
                )
                total_position_ratio = total_position_value / self.current_equity

                # 检查是否超过最大持仓比例
                if total_position_ratio >= self.max_position_size:
                    logger.warning("超过最大持仓比例限制")
                    return False

                # 计算目标股票持仓比例
                stock_code = signal['stock_code']
                current_pos = self.current_positions.get(stock_code, 0)
                current_amount = current_pos.get('amount', 0) if isinstance(current_pos, dict) else current_pos
                new_position = current_amount + signal['amount']
                position_ratio = new_position / self.current_equity

                # 检查是否超过单个股票最大持仓比例
                if position_ratio > self.max_single_position:
                    logger.warning("超过单个股票最大持仓比例限制")
                    return False

            return True

        except Exception as e:
            logger.error(f"检查持仓限制失败: {str(e)}")
            return False

    def _check_stop_loss(self, signal: Dict) -> bool:
        """检查止损"""
        try:
            if signal['type'] == 'buy':
                return True

            stock_code = signal['stock_code']
            if stock_code not in self.current_positions:
                return True

            # 获取持仓中的均价（兼容字典和数值两种格式）
            pos_data = self.current_positions[stock_code]
            if isinstance(pos_data, dict):
                avg_cost = pos_data.get('avg_cost', 0)
            else:
                avg_cost = float(pos_data) if pos_data else 0

            if avg_cost <= 0:
                return True

            # 计算浮动盈亏比例
            current_price = signal['price']
            profit_ratio = (current_price - avg_cost) / avg_cost

            if signal['type'] == 'short':
                if profit_ratio >= self.stop_loss:
                    logger.warning(f"触发做空止损: {stock_code}, 亏损: {profit_ratio:.2%}")
                    return False
                return True

            if profit_ratio <= -self.stop_loss:
                logger.warning(f"触发止损: {stock_code}, 亏损: {profit_ratio:.2%}")
                return False

            return True

        except Exception as e:
            logger.error(f"检查止损失败: {str(e)}")
            return False

    def _check_drawdown(self) -> bool:
        """检查回撤"""
        try:
            if self.current_equity > self.peak_equity:
                self.peak_equity = self.current_equity

            if self.peak_equity > 0:
                drawdown = (self.peak_equity -
                            self.current_equity) / self.peak_equity

                # 检查是否超过最大回撤限制
                if drawdown >= self.max_drawdown:
                    logger.warning("超过最大回撤限制")
                    return False

            return True

        except Exception as e:
            logger.error(f"检查回撤失败: {str(e)}")
            return False

    def update_position(self, stock_code: str, amount: float, price: float):
        """
        更新持仓信息

        Args:
            stock_code: 股票代码
            amount: 持仓数量变化（正数为买入，负数为卖出）
            price: 成交价格
        """
        try:
            if not self.initialized:
                raise RuntimeError("风险管理器未初始化")

            if stock_code not in self.current_positions:
                if amount > 0:
                    self.current_positions[stock_code] = {
                        'amount': amount,
                        'avg_cost': price
                    }
            else:
                current = self.current_positions[stock_code]
                new_amount = current['amount'] + amount

                if new_amount <= 0:
                    del self.current_positions[stock_code]
                else:
                    # 更新持仓均价
                    if amount > 0:
                        total_cost = current['amount'] * \
                            current['avg_cost'] + amount * price
                        current['avg_cost'] = total_cost / new_amount
                    current['amount'] = new_amount

        except Exception as e:
            logger.error(f"更新持仓信息失败: {str(e)}")
            logger.debug("跳过异常时的持仓推送以避免损坏数据")

    def update_equity(self, equity: float):
        """
        更新当前权益

        Args:
            equity: 当前权益
        """
        try:
            if not self.initialized:
                raise RuntimeError("风险管理器未初始化")

            self.current_equity = equity
            if equity > self.peak_equity:
                self.peak_equity = equity

        except Exception as e:
            logger.error(f"更新权益信息失败: {str(e)}")

    def get_risk_metrics(self) -> Dict:
        """
        获取风险指标

        Returns:
            Dict: 风险指标
        """
        try:
            if not self.initialized:
                raise RuntimeError("风险管理器未初始化")

            # 计算当前持仓比例
            total_position = sum(
                pos['amount'] * self.get_current_price(code)
                for code, pos in self.current_positions.items()
            )
            position_ratio = total_position / \
                self.current_equity if self.current_equity > 0 else 0

            # 计算当前回撤
            drawdown = ((self.peak_equity - self.current_equity) / self.peak_equity
                        if self.peak_equity > 0 else 0)

            return {
                'position_ratio': position_ratio,
                'drawdown': drawdown,
                'peak_equity': self.peak_equity,
                'current_equity': self.current_equity
            }

        except Exception as e:
            logger.error(f"获取风险指标失败: {str(e)}")
            return {}

    def get_current_price(self, stock_code: str) -> float:
        """获取当前价格"""
        try:
            price = self._fetch_price_from_service(stock_code)
            if price is not None and price > 0:
                return price

            last_price = self._get_last_transaction_price(stock_code)
            if last_price > 0:
                return last_price

            logger.warning(f"无法获取 {stock_code} 的当前价格，使用默认价格 0.0")
            return 0.0

        except Exception as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return 0.0

    def _fetch_price_from_service(self, stock_code: str) -> Optional[float]:
        """从服务获取实时价格"""
        try:
            from core.services.stock_service import StockService
            from core.containers import get_service_container
            container = get_service_container()
            stock_service = container.resolve(StockService)

            if not stock_service._initialized:
                stock_service._do_initialize()

            kdata = stock_service.get_kdata(stock_code, period='D', count=1)
            if kdata is not None and not kdata.empty:
                if 'close' in kdata.columns:
                    return float(kdata['close'].iloc[-1])
                elif '收盘' in kdata.columns:
                    return float(kdata['收盘'].iloc[-1])

            return None

        except Exception as e:
            logger.debug(f"从服务获取价格失败: {str(e)}")
            return None

    def _get_last_transaction_price(self, stock_code: str) -> float:
        """获取最后交易价格（基于本地持仓数据估算）"""
        try:
            if stock_code in self.current_positions:
                return float(self.current_positions[stock_code].get('avg_cost', 0))
            return 0.0

        except Exception as e:
            logger.debug(f"获取最后交易价格失败: {str(e)}")
            return 0.0

    def refresh_all_positions_price(self) -> Dict[str, float]:
        """刷新所有持仓的当前价格"""
        try:
            refreshed_prices = {}
            for stock_code in list(self.current_positions.keys()):
                price = self.get_current_price(stock_code)
                if price > 0:
                    refreshed_prices[stock_code] = price

            logger.info(f"成功刷新 {len(refreshed_prices)} 个持仓的当前价格")
            return refreshed_prices

        except Exception as e:
            logger.error(f"刷新持仓价格失败: {str(e)}")
            return {}



    def sync_to_monitor(self, monitor: 'EnhancedRiskMonitor') -> None:
        self._monitor = monitor

    def dispose(self) -> None:
        """释放资源 (HVD-241-P0-C-3, R78 4 链标准)

        Why: 纯内存状态类, 双宿主 (backtest 引擎 unified_backtest_engine.py:248 +
             backtest_widget.py:1877) 均无清理调用 → 一致性/防御性治理
             (R241-C 子智能体 100% 确认, 非泄漏源)
        Fix: _disposed 幂等短路 + 清空 current_positions + initialized 置 False
             + 解除 _monitor 引用; 失败仅 warning 不抛 (R8 铁律 #7)
        TDD: tests/test_r241_p0c_dispose_chains_tools_cache.py T05/T06
        """
        if getattr(self, '_disposed', False):
            return
        try:
            self.current_positions = {}
            self.initialized = False
            self._monitor = None
            self._disposed = True
            logger.info("RiskManager disposed")
        except Exception as e:
            logger.warning(f"RiskManager dispose 失败: {e}")
            self._disposed = True

    def _push_position_update(self, position_data: dict) -> None:
        if hasattr(self, '_monitor') and self._monitor:
            try:
                self._monitor.update_portfolio_positions([position_data])
            except Exception as e:
                logger.warning(f"推送持仓更新失败: {e}")


@dataclass
class TradingInstruction:
    stock_code: str = ""
    action: str = "hold"
    price: float = 0.0
    stop_loss_price: float = 0.0
    available_cash: float = 0.0
    position_shares: int = 0
    risk_amount: float = 0.0
    risk_level: str = "unknown"
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class TradeOrchestrator:
    """
    止损→资金→仓位编排器

    职责：
    1. 接收交易信号
    2. 调用 stop_loss 计算止损价
    3. 调用 money_manager 计算可用资金
    4. 调用 position_manager 计算仓位
    5. 返回综合交易指令
    """

    def __init__(self, stop_loss_params=None, money_manager_params=None):
        self._stop_loss_params = stop_loss_params or {}
        self._money_manager_params = money_manager_params or {}
        self._stop_loss: Optional[Any] = None
        self._money_manager: Optional[Any] = None
        self._position_manager: Optional[Any] = None
        self._initialized = False

    def initialize(self) -> bool:
        try:
            from core.stop_loss import AdaptiveStopLoss
            from core.money_manager import EnhancedMoneyManager
            from core.position_manager import PositionManager

            self._stop_loss = AdaptiveStopLoss(params=self._stop_loss_params)
            self._money_manager = EnhancedMoneyManager(params=self._money_manager_params)
            self._position_manager = PositionManager()

            self._initialized = True
            logger.info("TradeOrchestrator 初始化完成: 止损→资金→仓位编排链路已就绪")
            return True
        except Exception as e:
            logger.error(f"TradeOrchestrator 初始化失败: {e}")
            return False

    def _ensure_initialized(self):
        if not self._initialized:
            raise RuntimeError("TradeOrchestrator 未初始化，请先调用 initialize()")

    @monitor_performance("orchestrate_trade")
    def orchestrate(self, signal: Dict[str, Any]) -> Optional[TradingInstruction]:
        """
        编排止损→资金→仓位计算流程

        Args:
            signal: 交易信号字典，需包含:
                - stock_code: 股票代码
                - action: buy/sell/hold
                - price: 当前价格
                - data: 行情DataFrame (可选)
                - available_cash: 可用资金 (可选)

        Returns:
            TradingInstruction 或 None
        """
        self._ensure_initialized()

        try:
            stock_code = signal.get("stock_code", "")
            action = signal.get("action", "hold")
            price = signal.get("price", 0.0)
            data = signal.get("data")
            available_cash = signal.get("available_cash", 0.0)

            if not stock_code or price <= 0:
                logger.warning(f"无效信号: stock_code={stock_code}, price={price}")
                return None

            if action not in ("buy", "sell", "hold"):
                logger.warning(f"未知操作: {action}")
                return None

            data = self._ensure_dataframe(data)

            stop_loss_price = self._orchestrate_stop_loss(data, price)
            position_shares, risk_amount = self._orchestrate_money_manager(
                data, price, stop_loss_price, available_cash
            )

            risk_level = self._classify_risk_level(price, stop_loss_price, risk_amount, available_cash)

            instruction = TradingInstruction(
                stock_code=stock_code,
                action=action,
                price=price,
                stop_loss_price=stop_loss_price,
                available_cash=available_cash,
                position_shares=position_shares,
                risk_amount=risk_amount,
                risk_level=risk_level,
                reason=self._build_reason(action, stop_loss_price, position_shares, risk_level),
                metadata={
                    "stop_loss_params": self._stop_loss.get_param("atr_multiplier") if self._stop_loss else None,
                    "risk_per_trade": self._money_manager.get_param("risk_per_trade") if self._money_manager else None,
                }
            )

            logger.info(
                f"编排完成: {stock_code} {action} @ {price:.2f}, "
                f"止损={stop_loss_price:.2f}, 仓位={position_shares}, "
                f"风险={risk_level}"
            )
            return instruction

        except Exception as e:
            logger.error(f"TradeOrchestrator 编排失败: {e}")
            return None

    @monitor_performance("orchestrate_batch")
    def orchestrate_batch(self, signals: list) -> list:
        """批量编排多个交易信号"""
        self._ensure_initialized()
        results = []
        for signal in signals:
            instruction = self.orchestrate(signal)
            if instruction:
                results.append(instruction)
        return results

    def _orchestrate_stop_loss(self, data: Optional["pd.DataFrame"], price: float) -> float:
        """调用止损模块计算止损价"""
        if self._stop_loss is None:
            return price * 0.95

        try:
            if data is not None and not data.empty:
                return self._stop_loss.calculate_stop_price(data, price)
            return price * (1 - self._stop_loss.get_param("min_stop_loss", 0.05))
        except Exception as e:
            logger.warning(f"止损计算异常，使用默认止损: {e}")
            return price * 0.95

    def _orchestrate_money_manager(
        self, data: Optional["pd.DataFrame"], price: float,
        stop_loss_price: float, available_cash: float
    ) -> tuple:
        """调用资金管理模块计算仓位"""
        if self._money_manager is None:
            return 0, 0.0

        try:
            if data is not None and not data.empty:
                shares = self._money_manager.calculate_position_size(
                    data, price, stop_loss_price, available_cash
                )
            else:
                risk_amount = available_cash * self._money_manager.get_param("risk_per_trade", 0.02)
                risk_per_share = max(price - stop_loss_price, 0.01)
                shares = int((risk_amount / risk_per_share) // 100) * 100

            risk_amount = shares * (price - stop_loss_price)
            return shares, risk_amount
        except Exception as e:
            logger.warning(f"资金管理计算异常: {e}")
            return 0, 0.0

    @staticmethod
    def _classify_risk_level(price: float, stop_loss_price: float,
                             risk_amount: float, available_cash: float) -> str:
        """根据止损距离和风险敞口分类风险等级"""
        if price <= 0 or stop_loss_price <= 0:
            return "unknown"

        stop_distance_pct = (price - stop_loss_price) / price

        risk_exposure = risk_amount / available_cash if available_cash > 0 else 0

        if stop_distance_pct < 0.01:
            return "critical"
        elif stop_distance_pct < 0.03 or risk_exposure > 0.05:
            return "high"
        elif stop_distance_pct < 0.05 or risk_exposure > 0.02:
            return "medium"
        else:
            return "low"

    @staticmethod
    def _build_reason(action: str, stop_loss_price: float,
                      position_shares: int, risk_level: str) -> str:
        if action == "buy":
            return (
                f"买入信号: 止损价={stop_loss_price:.2f}, "
                f"建议仓位={position_shares}股, 风险等级={risk_level}"
            )
        elif action == "sell":
            return f"卖出信号: 风险等级={risk_level}"
        return f"持仓不变: 风险等级={risk_level}"

    @staticmethod
    def _ensure_dataframe(data):
        if isinstance(data, pd.DataFrame):
            return data
        if isinstance(data, dict):
            try:
                return pd.DataFrame(data)
            except Exception:
                return None
        if isinstance(data, (list, tuple)):
            try:
                return pd.DataFrame(data)
            except Exception:
                return None
        return None

    def update_account(self, account) -> None:
        if self._position_manager and account:
            self._position_manager.account = account

    def get_stop_loss_strategy(self):
        return self._stop_loss

    def get_money_manager(self):
        return self._money_manager

    def get_position_manager(self):
        return self._position_manager
