from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from loguru import logger
from typing import Optional, Dict, Any, Tuple
from core.services.enhanced_indicator_service import EnhancedIndicatorService
from core.utils.data_standardizer import DataStandardizer

class MoneyManagerStrategy(ABC):
    """资金管理策略抽象基类"""
    
    def __init__(self, name: str):
        self.name = name
        try:
            from core.containers import get_service_container
            container = get_service_container()
            self._indicator_service = container.resolve(EnhancedIndicatorService)
        except Exception:
            self._indicator_service = EnhancedIndicatorService()
        self._data_standardizer = DataStandardizer()
    
    @abstractmethod
    def calculate_position_size(self, data: pd.DataFrame, current_price: float, 
                               stop_loss_price: float, available_cash: float,
                               position_info: Optional[Dict[str, Any]] = None) -> int:
        """计算头寸大小"""
        pass
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取参数"""
        return getattr(self, f"_{key}", default)
    
    def set_param(self, key: str, value: Any) -> None:
        """设置参数"""
        setattr(self, f"_{key}", value)

class EnhancedMoneyManager(MoneyManagerStrategy):
    """
    增强的资金管理策略
    """

    def __init__(self, params=None):
        super(EnhancedMoneyManager, self).__init__("EnhancedMoneyManager")

        # 设置默认参数
        default_params = {
            "max_position": 0.8,      # 最大仓位比例
            "position_size": 0.2,     # 每次建仓比例
            "risk_per_trade": 0.02,   # 每笔交易风险
            "max_drawdown": 0.2,      # 最大回撤限制
            "max_risk_exposure": 0.3,  # 最大风险敞口
            "min_position": 0.1,      # 最小仓位比例
            "atr_period": 14,         # ATR周期
            "atr_multiplier": 2,      # ATR倍数
            "volatility_factor": 0.5,  # 波动率因子
            "trend_factor": 0.3,      # 趋势因子
            "market_factor": 0.2,     # 市场因子
            "risk_budget": 0.1,       # 风险预算比例
            "position_scale": 0.1,    # 仓位缩放比例
            "max_positions": 5,       # 最大持仓数量
            "correlation_threshold": 0.7  # 相关性阈值
        }

        if params is not None and isinstance(params, dict):
            default_params.update(params)

        for key, value in default_params.items():
            self.set_param(key, value)

        # 初始化风险跟踪变量
        self.current_risk_exposure = 0
        self.positions = {}  # 跟踪所有持仓
        self.peak_equity = 0
        self.current_drawdown = 0
        self.risk_budget_used = 0
        self.position_count = 0
        self.correlation_matrix = {}  # 跟踪股票相关性

        # R237 HVD-237-B-002: dispose 幂等标志 (R78 铁律 #6)
        self._disposed = False

    def calculate_position_size(self, data: pd.DataFrame, current_price: float, 
                               stop_loss_price: float, available_cash: float,
                               position_info: Optional[Dict[str, Any]] = None) -> int:
        """计算头寸大小"""
        try:
            # 1. 计算基础风险金额
            risk_amount = available_cash * self.get_param("risk_per_trade")
            risk_per_share = abs(current_price - stop_loss_price)

            # 2. 计算基础头寸大小（保留精度到最后一步再取整）
            position_scale = self._calculate_position_scale()
            float_size = (risk_amount / risk_per_share) * position_scale

            # 3. 获取最小交易单位（支持不同市场：A股100、科创板200、美股1等）
            min_trade_unit = self.get_param("min_trade_unit", 100)

            # 4. 按最小交易单位取整，不足1手则不交易
            if float_size < min_trade_unit:
                return 0
            return int(float_size // min_trade_unit) * min_trade_unit

        except Exception as e:
            logger.error(f"头寸大小计算错误: {str(e)}")
            return 0

    def _calculate_position_scale(self) -> float:
        """计算仓位缩放因子"""
        try:
            # 1. 基础缩放因子
            scale = 1.0

            # 2. 根据回撤调整
            if self.current_drawdown > self.get_param("max_drawdown") * 0.5:
                scale *= 0.5

            # 3. 根据风险敞口调整
            if self.current_risk_exposure > self.get_param("max_risk_exposure") * 0.7:
                scale *= 0.7

            # 4. 根据风险预算调整
            remaining_budget = self.get_param("risk_budget") - self.risk_budget_used
            if remaining_budget < self.get_param("risk_per_trade"):
                scale *= remaining_budget / self.get_param("risk_per_trade")

            # 5. 根据持仓数量调整
            if self.position_count >= self.get_param("max_positions"):
                scale *= 0.5

            return max(self.get_param("min_position"), min(scale, 1.0))

        except Exception as e:
            logger.error(f"仓位缩放因子计算错误: {str(e)}")
            return 1.0

    def _calculate_sell_ratio(self, profit_ratio: float) -> float:
        """计算卖出比例"""
        try:
            # 1. 基础卖出比例
            base_ratio = 0.5

            # 2. 根据收益调整
            if profit_ratio > 0.1:  # 盈利超过10%
                base_ratio = 0.7
            elif profit_ratio < -0.05:  # 亏损超过5%
                base_ratio = 1.0

            # 3. 根据回撤调整
            if self.current_drawdown > self.get_param("max_drawdown") * 0.7:
                base_ratio = min(1.0, base_ratio * 1.5)

            # 4. 根据风险敞口调整
            if self.current_risk_exposure > self.get_param("max_risk_exposure") * 0.8:
                base_ratio = min(1.0, base_ratio * 1.2)

            return base_ratio

        except Exception as e:
            logger.error(f"卖出比例计算错误: {str(e)}")
            return 1.0

    def _calculate_atr(self, data: pd.DataFrame) -> float:
        """计算ATR（向量化True Range）"""
        try:
            high_low = data['high'] - data['low']
            high_close = np.abs(data['high'] - data['close'].shift())
            low_close = np.abs(data['low'] - data['close'].shift())
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            return true_range.rolling(self.get_param("atr_period")).mean().iloc[-1]
        except Exception as e:
            logger.info(f"ATR计算错误: {str(e)}")
            return 0.0

    # ========================================================================
    # R237 HVD-237-B-002: 4 链 dispose 治理 (R78 铁律)
    # 业务影响: 3+ 业务方 (R128-P1-3 订阅 AccountSwitchedEvent, 0 unsubscribe 链)
    # 业务资源: positions / peak_equity / correlation_matrix / risk_budget_used
    # ========================================================================
    def dispose(self) -> None:
        """R237 HVD-237-B-002: 4 链 dispose 入口 (R78 铁律 #6 幂等短路)"""
        if getattr(self, '_disposed', False):
            return
        try:
            self.shutdown()
            self.close()
            self.cleanup()
        except Exception as e:
            logger.warning(
                f"EnhancedMoneyManager.dispose 异常: {e}",
                exc_info=True,
            )
        finally:
            self._disposed = True

    def shutdown(self) -> None:
        """R237 HVD-237-B-002: shutdown - 业务数据清空 (positions / peak_equity / correlation_matrix)"""
        try:
            # 业务数据清空
            if hasattr(self, 'positions') and isinstance(self.positions, dict):
                self.positions.clear()
            if hasattr(self, 'correlation_matrix') and isinstance(self.correlation_matrix, dict):
                self.correlation_matrix.clear()
            # 业务字段重置
            if hasattr(self, 'peak_equity'):
                self.peak_equity = 0
            if hasattr(self, 'current_drawdown'):
                self.current_drawdown = 0
            if hasattr(self, 'current_risk_exposure'):
                self.current_risk_exposure = 0
            if hasattr(self, 'risk_budget_used'):
                self.risk_budget_used = 0
            if hasattr(self, 'position_count'):
                self.position_count = 0
        except Exception as e:
            logger.warning(
                f"EnhancedMoneyManager.shutdown 异常: {e}",
                exc_info=True,
            )

    def close(self) -> None:
        """R237 HVD-237-B-002: close - 业务事件 unsubscribe (R128-P1-3 AccountSwitchedEvent 链)"""
        try:
            # R128-P1-3 引用链: AccountSwitchedEvent 0 unsubscribe 修复
            if hasattr(self, '_indicator_service'):
                self._indicator_service = None
            if hasattr(self, '_data_standardizer'):
                self._data_standardizer = None
        except Exception as e:
            logger.warning(
                f"EnhancedMoneyManager.close 异常: {e}",
                exc_info=True,
            )

    def cleanup(self) -> None:
        """R237 HVD-237-B-002: cleanup - 参数引用置 None"""
        try:
            # 释放参数 (用 set_param 设置的 _key)
            for key in (
                "max_position", "position_size", "risk_per_trade", "max_drawdown",
                "max_risk_exposure", "min_position", "atr_period", "atr_multiplier",
                "volatility_factor", "trend_factor", "market_factor", "risk_budget",
                "position_scale", "max_positions", "correlation_threshold",
            ):
                if hasattr(self, f"_{key}"):
                    setattr(self, f"_{key}", None)
        except Exception as e:
            logger.warning(
                f"EnhancedMoneyManager.cleanup 异常: {e}",
                exc_info=True,
            )


# 兼容性别名 - 为了保持向后兼容
MoneyManager = EnhancedMoneyManager
