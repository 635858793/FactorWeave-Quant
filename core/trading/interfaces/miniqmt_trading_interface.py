"""
miniQMT交易接口

提供miniQMT交易执行功能，支持A股、港股、美股等市场。
基于FactorWeave-Quant交易接口标准实现，集成xttrader接口。

功能特性：
- 股票下单
- 订单撤单
- 订单查询
- 资金查询
- 持仓查询
- 多账户支持

作者: FactorWeave-Quant团队
版本: 1.0.0
日期: 2025-01-16
"""

import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from loguru import logger

from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface
from core.trading.order_models import Order, OrderType, OrderCategory

try:
    import xtquant.xttrader as xttrader
    XTTRADER_AVAILABLE = True
except ImportError:
    XTTRADER_AVAILABLE = False
    logger.warning("xttrader (miniQMT) 未安装，miniQMT交易功能不可用")


@dataclass
class MiniQMTConfig:
    """miniQMT交易配置"""
    session_id: int = 0
    ip: str = "127.0.0.1"
    port: int = 58610
    account_type: str = "STOCK"  # STOCK, FUTURE, CREDIT
    account_id: str = ""
    password: str = ""


class MiniQMTTradingInterface(TradingInterface):
    """miniQMT交易接口"""

    def __init__(self, config: MiniQMTConfig = None):
        """
        初始化miniQMT交易接口

        Args:
            config: miniQMT配置
        """
        if not XTTRADER_AVAILABLE:
            raise ImportError("xttrader (miniQMT) 未安装，请先安装: pip install xtquant")

        self.config = config or MiniQMTConfig()

        # xttrader连接
        self._trader = None
        self._connected = False
        self._logged_in = False

        # 订单缓存
        self._orders: Dict[str, Dict] = {}

        # 性能统计
        self._stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'total_cancels': 0,
            'successful_cancels': 0
        }

        self.logger = logger.bind(interface="miniqmt_trading")
        self.logger.info("miniQMT交易接口初始化完成")

    def connect(self) -> bool:
        """连接miniQMT交易服务器"""
        try:
            self.logger.info(f"正在连接miniQMT交易服务器: {self.config.ip}:{self.config.port}")

            # 创建交易连接
            self._trader = xttrader.XtTrader(
                session_id=self.config.session_id
            )

            # 连接服务器
            connect_result = self._trader.connect(
                path=self.config.ip,
                port=self.config.port
            )

            if connect_result != 0:
                self.logger.error(f"miniQMT连接失败，错误代码: {connect_result}")
                return False

            self._connected = True
            self.logger.info("miniQMT交易服务器连接成功")
            return True

        except Exception as e:
            self.logger.error(f"连接miniQMT交易服务器失败: {e}")
            return False

    def login(self) -> bool:
        """登录交易账户"""
        try:
            if not self._connected:
                self.logger.error("未连接到交易服务器")
                return False

            self.logger.info(f"正在登录账户: {self.config.account_id}")

            # 登录
            login_result = self._trader.login(
                account_type=self.config.account_type,
                account_id=self.config.account_id,
                password=self.config.password
            )

            if login_result != 0:
                self.logger.error(f"登录失败，错误代码: {login_result}")
                return False

            self._logged_in = True
            self.logger.info("账户登录成功")
            return True

        except Exception as e:
            self.logger.error(f"登录账户失败: {e}")
            return False

    def disconnect(self):
        """断开交易连接"""
        try:
            if self._trader and self._logged_in:
                self._trader.logout()
                self._logged_in = False

            if self._trader and self._connected:
                self._trader.disconnect()
                self._connected = False

            self.logger.info("miniQMT交易连接已断开")

        except Exception as e:
            self.logger.error(f"断开连接失败: {e}")

    def submit_order(self, order: Order) -> ExecutionResult:
        """提交订单"""
        try:
            if not self._logged_in:
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录交易账户",
                    error_code="NOT_LOGGED_IN"
                )

            self.logger.info(f"提交订单: {order.order_id}, {order.stock_code}, {order.order_type.value}, {order.order_category.value}, {order.order_quantity}")

            # 转换订单类型
            xt_order_type = self._convert_order_type(order.order_category)

            # 转换订单方向
            xt_order_side = self._convert_order_side(order.order_type)

            # 提交订单
            order_result = self._trader.order_stock(
                account=self.config.account_id,
                stock_code=order.stock_code,
                order_type=xt_order_type,
                order_volume=order.order_quantity,
                price_type=xt_order_side,
                price=order.order_price if order.order_price else 0
            )

            # 检查结果
            if order_result != 0:
                self._stats['failed_orders'] += 1
                error_msg = self._get_error_message(order_result)
                self.logger.error(f"订单提交失败: {error_msg}")
                return ExecutionResult(
                    order_id=order.order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"订单提交失败: {error_msg}",
                    error_code=str(order_result)
                )

            # 缓存订单
            self._orders[order.order_id] = {
                'stock_code': order.stock_code,
                'order_type': order.order_type.value,
                'order_category': order.order_category.value,
                'order_quantity': order.order_quantity,
                'order_price': order.order_price,
                'submit_time': datetime.now()
            }

            self._stats['total_orders'] += 1
            self._stats['successful_orders'] += 1

            self.logger.info(f"订单提交成功: {order.order_id}")
            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.SUCCESS,
                message="订单提交成功",
                exchange_order_id=str(order_result)
            )

        except Exception as e:
            self._stats['failed_orders'] += 1
            self.logger.error(f"提交订单异常: {e}")
            return ExecutionResult(
                order_id=order.order_id,
                status=ExecutionStatus.FAILED,
                message=f"提交订单异常: {str(e)}",
                error_code="EXCEPTION"
            )

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """取消订单"""
        try:
            if not self._logged_in:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录交易账户",
                    error_code="NOT_LOGGED_IN"
                )

            self.logger.info(f"取消订单: {order_id}")

            # 从缓存获取订单信息
            if order_id not in self._orders:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="订单不存在",
                    error_code="ORDER_NOT_FOUND"
                )

            order_info = self._orders[order_id]

            # 取消订单
            cancel_result = self._trader.cancel_order_stock(
                account=self.config.account_id,
                order_id=int(order_id)
            )

            # 检查结果
            if cancel_result != 0:
                self._stats['failed_cancels'] += 1
                error_msg = self._get_error_message(cancel_result)
                self.logger.error(f"订单取消失败: {error_msg}")
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message=f"订单取消失败: {error_msg}",
                    error_code=str(cancel_result)
                )

            # 从缓存移除
            del self._orders[order_id]

            self._stats['total_cancels'] += 1
            self._stats['successful_cancels'] += 1

            self.logger.info(f"订单取消成功: {order_id}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.SUCCESS,
                message="订单取消成功"
            )

        except Exception as e:
            self.logger.error(f"取消订单异常: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"取消订单异常: {str(e)}",
                error_code="EXCEPTION"
            )

    def query_order_status(self, order_id: str) -> ExecutionResult:
        """查询订单状态"""
        try:
            if not self._logged_in:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="未登录交易账户",
                    error_code="NOT_LOGGED_IN"
                )

            # 查询订单
            order_query = self._trader.query_stock_order(
                account=self.config.account_id,
                order_id=int(order_id)
            )

            if order_query:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.SUCCESS,
                    message="查询成功",
                    details={
                        'order_status': order_query.get('order_status'),
                        'filled_quantity': order_query.get('filled_qty', 0),
                        'remaining_quantity': order_query.get('remain_qty', 0),
                        'avg_price': order_query.get('avg_price', 0)
                    }
                )
            else:
                return ExecutionResult(
                    order_id=order_id,
                    status=ExecutionStatus.FAILED,
                    message="订单不存在或查询失败",
                    error_code="QUERY_FAILED"
                )

        except Exception as e:
            self.logger.error(f"查询订单状态异常: {e}")
            return ExecutionResult(
                order_id=order_id,
                status=ExecutionStatus.FAILED,
                message=f"查询异常: {str(e)}",
                error_code="EXCEPTION"
            )

    def query_fund_info(self, account_id: str) -> Dict[str, Any]:
        """查询账户资金信息"""
        try:
            if not self._logged_in:
                return {
                    'error': '未登录交易账户'
                }

            # 查询资金
            fund_info = self._trader.query_stock_asset(
                account=account_id
            )

            if fund_info:
                return {
                    'account_id': account_id,
                    'total_asset': fund_info.get('total_asset', 0),
                    'cash': fund_info.get('cash', 0),
                    'market_value': fund_info.get('market_value', 0),
                    'available_cash': fund_info.get('available_cash', 0),
                    'frozen_cash': fund_info.get('frozen_cash', 0),
                    'profit_loss': fund_info.get('profit_loss', 0)
                }
            else:
                return {
                    'error': '查询资金信息失败'
                }

        except Exception as e:
            self.logger.error(f"查询资金信息异常: {e}")
            return {
                'error': f'查询异常: {str(e)}'
            }

    def query_positions(self, account_id: str) -> List[Dict[str, Any]]:
        """查询账户持仓信息"""
        try:
            if not self._logged_in:
                return []

            # 查询持仓
            positions = self._trader.query_stock_positions(
                account=account_id
            )

            if positions:
                return [
                    {
                        'symbol': pos.get('stock_code'),
                        'quantity': pos.get('volume', 0),
                        'available_quantity': pos.get('can_use_volume', 0),
                        'avg_price': pos.get('open_price', 0),
                        'current_price': pos.get('last_price', 0),
                        'market_value': pos.get('market_value', 0),
                        'profit_loss': pos.get('profit_loss', 0),
                        'profit_loss_ratio': pos.get('profit_loss_ratio', 0)
                    }
                    for pos in positions
                ]
            else:
                return []

        except Exception as e:
            self.logger.error(f"查询持仓信息异常: {e}")
            return []

    def _convert_order_type(self, order_type: OrderType) -> int:
        """转换订单类型"""
        type_mapping = {
            OrderType.MARKET: 23,      # 市价单
            OrderType.LIMIT: 24,       # 限价单
            OrderType.STOP: 25,        # 止损单
            OrderType.STOP_LIMIT: 26    # 止损限价单
        }
        return type_mapping.get(order_type, 24)  # 默认限价单

    def _convert_order_side(self, order_side: OrderType) -> int:
        """转换订单方向"""
        side_mapping = {
            OrderType.BUY: 11,          # 买入
            OrderType.SELL: 12         # 卖出
        }
        return side_mapping.get(order_side, 11)  # 默认买入

    def _get_error_message(self, error_code: int) -> str:
        """获取错误消息"""
        error_messages = {
            -1: "未知错误",
            -2: "网络连接失败",
            -3: "未登录",
            -4: "账户不存在",
            -5: "密码错误",
            -6: "权限不足",
            -7: "资金不足",
            -8: "持仓不足",
            -9: "订单不存在",
            -10: "订单已成交",
            -11: "订单已撤销",
            -12: "订单状态错误",
            -13: "股票代码错误",
            -14: "价格错误",
            -15: "数量错误",
            -16: "交易时间错误",
            -17: "交易规则限制",
            -18: "系统繁忙"
        }
        return error_messages.get(error_code, f"未知错误代码: {error_code}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'connected': self._connected,
            'logged_in': self._logged_in,
            'stats': self._stats.copy(),
            'cached_orders': len(self._orders)
        }

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    def is_logged_in(self) -> bool:
        """检查登录状态"""
        return self._logged_in
