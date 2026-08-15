"""
持仓风控执行器 (R269-D3 复活融入)

整合三个此前无活调用点的量化组件, 由订单执行器下单风控链路消费:
- AdaptiveStopLoss (core/stop_loss.py)          → 动态止损价 (ATR/均线/跟踪/波动率/固定 五路融合)
- AdaptiveTakeProfit (core/take_profit.py)      → 动态止盈价 (与止损镜像, 方向相反)
- EnhancedMoneyManager (core/money_manager.py)  → 基于账户资金与止损距离的动态下单量
- PositionManager (core/position_manager.py)    → 多空敞口计算 (calculate_exposure)

背景 (R269 深度调研, 全部含行号):
- 三个组件此前仅被死代码 TradeOrchestrator (core/risk_manager.py:506-723) 引用,
  TradeOrchestrator 依赖的 TradingInstruction 全仓库无定义 → 运行时必抛 NameError
  → 三个组件在生产链路从未生效 (100% 死代码)。
- 订单执行器止损检查依赖 stop_loss_levels (core/risk_control.py:13), 唯一写入点
  calculate_stop_loss (:135) 全库零调用 → 止损检查空转 (实盘止损恒不拦截)。
- 本模块作为新的活融入点: 提供动态止损/止盈/仓位建议/敞口, 供订单链路正确消费,
  并修复上述空转 (order_executor._fill_stop_loss_level 消费本模块动态止损价)。

设计: 无状态计算器 + 可选行情获取; 所有方法防御式降级 (行情数据不可用 → 固定比例),
保证任何异常都不阻断主交易链路 (风控降级放行原则, 与 R252-F1 一致)。
"""

import pandas as pd
from loguru import logger
from typing import Dict, List, Optional, Any


class PositionRiskMonitor:
    """持仓风控执行器 —— 动态止损/止盈/资金管理/敞口的统一出口"""

    _disposed = False

    def __init__(self, service_container=None,
                 stop_loss_params: Optional[Dict[str, Any]] = None,
                 take_profit_params: Optional[Dict[str, Any]] = None,
                 money_manager_params: Optional[Dict[str, Any]] = None):
        # R238-D-001 模式: _disposed 幂等标志 (R78 铁律 #6)
        self._disposed = False
        self._service_container = service_container
        self._params = {
            'stop_loss': stop_loss_params or {},
            'take_profit': take_profit_params or {},
            'money_manager': money_manager_params or {},
        }
        self._stop_loss = None
        self._take_profit = None
        self._money_manager = None
        self._position_manager = None

        self._init_components()
        logger.info("持仓风控执行器初始化完成 (动态止损/止盈/资金管理)")

    def _init_components(self):
        """懒初始化量化组件 (延迟 import 防循环依赖; 单个失败不影响整体)"""
        try:
            from core.stop_loss import AdaptiveStopLoss
            self._stop_loss = AdaptiveStopLoss(params=self._params['stop_loss'])
        except Exception as e:
            logger.warning(f"AdaptiveStopLoss 初始化失败(动态止损降级固定比例): {e}")

        try:
            from core.take_profit import AdaptiveTakeProfit
            self._take_profit = AdaptiveTakeProfit(params=self._params['take_profit'])
        except Exception as e:
            logger.warning(f"AdaptiveTakeProfit 初始化失败(动态止盈降级固定比例): {e}")

        try:
            from core.money_manager import EnhancedMoneyManager
            self._money_manager = EnhancedMoneyManager(params=self._params['money_manager'])
        except Exception as e:
            logger.warning(f"EnhancedMoneyManager 初始化失败(仓位建议不可用): {e}")

        try:
            from core.position_manager import PositionManager
            self._position_manager = PositionManager()
        except Exception as e:
            logger.warning(f"PositionManager 初始化失败(敞口计算不可用): {e}")

    # ---------------- 动态止损 ----------------

    def get_dynamic_stop_price(self, stock_code: str, current_price: float,
                               position: float = 0.0,
                               position_info: Optional[Dict[str, Any]] = None,
                               data: Optional[pd.DataFrame] = None) -> float:
        """计算动态止损价: 有 K 线时用 AdaptiveStopLoss 五路融合, 否则固定比例降级。

        Args:
            stock_code: 证券代码
            current_price: 当前价 (下单路径以订单申报价近似)
            position: 持仓方向 (正=多, 负=空)
            position_info: 持仓信息 (entry_price/highest_price/lowest_price 等)
            data: 可选 K 线 DataFrame; 不传则尝试自动获取

        Returns:
            float 止损价 (>0); 数据完全不可用/异常时返回 0 (调用方自行兜底)
        """
        if current_price <= 0:
            return 0.0
        pos_info = dict(position_info or {})
        if 'entry_price' not in pos_info:
            pos_info['entry_price'] = current_price

        if self._stop_loss is not None:
            kdata = data
            if kdata is None:
                kdata = self._get_kline_data(stock_code)
            if kdata is not None and not kdata.empty:
                try:
                    stop = self._stop_loss.calculate_stop_price(kdata, current_price, pos_info)
                    if stop and stop > 0:
                        return float(stop)
                except Exception as e:
                    logger.debug(f"自适应止损计算异常, 降级固定比例: {e}")

        # 降级: 固定比例 (min_stop_loss 默认 2%)
        ratio = self._stop_loss.get_param('min_stop_loss', 0.02) if self._stop_loss else 0.02
        return current_price * (1 - ratio) if position >= 0 else current_price * (1 + ratio)

    # ---------------- 动态止盈 ----------------

    def get_dynamic_take_profit(self, stock_code: str, current_price: float,
                                position: float = 0,
                                position_info: Optional[Dict[str, Any]] = None,
                                data: Optional[pd.DataFrame] = None) -> float:
        """计算动态止盈价: 有 K 线时用 AdaptiveTakeProfit, 否则固定比例降级。

        position: 持仓方向 (正=多头, 负=空头); 固定比例降级时多头 (1+ratio)、空头 (1-ratio)。
        """
        if current_price <= 0:
            return 0.0

        if self._take_profit is not None:
            kdata = data
            if kdata is None:
                kdata = self._get_kline_data(stock_code)
            if kdata is not None and not kdata.empty:
                try:
                    tp = self._take_profit.calculate_profit_price(kdata, current_price, position_info or {})
                    if tp and tp > 0:
                        return float(tp)
                except Exception as e:
                    logger.debug(f"自适应止盈计算异常, 降级固定比例: {e}")

        ratio = self._take_profit.get_param('min_take_profit', 0.02) if self._take_profit else 0.02
        return current_price * (1 + ratio) if position >= 0 else current_price * (1 - ratio)

    # ---------------- 资金管理 ----------------

    def calculate_position_size(self, current_price: float, stop_loss_price: float,
                                available_cash: float,
                                position_info: Optional[Dict[str, Any]] = None,
                                data: Optional[pd.DataFrame] = None) -> int:
        """基于每笔风险金额与止损距离计算建议下单量 (EnhancedMoneyManager)。"""
        if (self._money_manager is None or current_price <= 0
                or stop_loss_price <= 0 or available_cash <= 0):
            return 0
        try:
            return int(self._money_manager.calculate_position_size(
                data, current_price, stop_loss_price, available_cash,
                position_info or {}))
        except Exception as e:
            logger.warning(f"资金管理计算异常, 返回 0: {e}")
            return 0

    # ---------------- 多空敞口 ----------------

    def calculate_exposure(self, positions: List) -> Dict[str, float]:
        """计算多空敞口市值 (PositionManager.calculate_exposure)。"""
        if self._position_manager is None or not positions:
            return {'long': 0.0, 'short': 0.0, 'net': 0.0}
        try:
            result = self._position_manager.calculate_exposure(positions)
            return {
                'long': float(result.get('long', 0.0) or 0.0),
                'short': float(result.get('short', 0.0) or 0.0),
                'net': float(result.get('net', 0.0) or 0.0),
            }
        except Exception as e:
            logger.warning(f"敞口计算异常, 返回 0: {e}")
            return {'long': 0.0, 'short': 0.0, 'net': 0.0}

    # ---------------- 数据源 ----------------

    def _get_kline_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """尝试获取日 K 线 (UnifiedDataManager → StockService, 失败返回 None)。

        失败仅触发固定比例降级, 不抛异常 (风控降级放行原则)。
        """
        try:
            from core.services.unified_data_manager import get_unified_data_manager
            dm = get_unified_data_manager()
            if dm is not None:
                df = dm.get_kdata(stock_code, period='D', count=120)
                if df is not None and not df.empty:
                    return self._normalize_kdata(df)
        except Exception:
            pass

        try:
            from core.services.stock_service import StockService
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container is not None:
                stock_service = container.resolve(StockService)
                df = stock_service.get_kdata(stock_code, period='D', count=120)
                if df is not None and not df.empty:
                    return self._normalize_kdata(df)
        except Exception:
            pass

        return None

    @staticmethod
    def _normalize_kdata(df: pd.DataFrame) -> pd.DataFrame:
        """规范化 K 线列名 (open/high/low/close/volume 小写)。"""
        expected = {'open', 'high', 'low', 'close', 'volume'}
        cols = {str(c).lower() for c in df.columns}
        if expected.issubset(cols):
            return df.rename(columns={c: str(c).lower() for c in df.columns})
        return df

    # ---------------- 生命周期 (R238-D-001 幂等) ----------------

    def dispose(self):
        """释放资源 (幂等)。"""
        if self._disposed:
            return
        self._disposed = True
        self._stop_loss = None
        self._take_profit = None
        self._money_manager = None
        self._position_manager = None
        self._service_container = None
        logger.info("持仓风控执行器已释放")
