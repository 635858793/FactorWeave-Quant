"""
风险管理模块
"""
from loguru import logger
from typing import Dict, Optional, Any
from core.performance import measure_performance as monitor_performance
from core.config import ConfigManager, config_manager

class RiskManager:
    """风险管理类"""

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

    def initialize(self) -> bool:
        """初始化风险管理器"""
        try:
            # 加载风险控制参数
            self._load_risk_params()

            self.initialized = True
            logger.error("风险管理器初始化成功")
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
        try:
            if not self.initialized:
                raise RuntimeError("风险管理器未初始化")

            # 检查持仓限制
            if not self._check_position_limit(signal):
                return False

            # 检查止损
            if not self._check_stop_loss(signal):
                return False

            # 检查回撤
            if not self._check_drawdown():
                return False

            return True

        except Exception as e:
            logger.error(f"风险检查失败: {str(e)}")
            return False

    def _check_position_limit(self, signal: Dict) -> bool:
        """检查持仓限制"""
        try:
            if signal['type'] == 'buy':
                # 计算当前总持仓比例
                total_position = sum(
                    self.current_positions.values()) / self.current_equity

                # 检查是否超过最大持仓比例
                if total_position >= self.max_position_size:
                    logger.warning("超过最大持仓比例限制")
                    return False

                # 计算目标股票持仓比例
                stock_code = signal['stock_code']
                current_position = self.current_positions.get(stock_code, 0)
                new_position = current_position + signal['amount']
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

            # 计算浮动盈亏比例
            current_price = signal['price']
            avg_cost = self.current_positions[stock_code]['avg_cost']
            profit_ratio = (current_price - avg_cost) / avg_cost

            # 检查是否触发止损
            if profit_ratio <= -self.stop_loss:
                logger.warning(f"触发止损: {stock_code}")
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
            stock_service = StockService()

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
