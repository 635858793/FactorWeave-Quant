#!/usr/bin/env python3
"""
交易模式管理模块

提供统一的交易模式枚举、上下文管理和模式感知能力
支持回测、模拟交易、实盘交易三种模式的无缝切换
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


class TradingMode(Enum):
    """交易模式枚举"""
    
    BACKTEST = "backtest"
    """回测模式：使用历史数据，完整计算，无性能压力"""
    
    PAPER = "paper"
    """模拟交易模式：使用实时数据，但不实际下单"""
    
    LIVE = "live"
    """实盘模式：使用实时数据，实际下单，性能敏感"""
    
    @property
    def is_backtest(self) -> bool:
        """是否为回测模式"""
        return self == TradingMode.BACKTEST
    
    @property
    def is_live(self) -> bool:
        """是否为实盘模式（包含模拟和实盘）"""
        return self in (TradingMode.PAPER, TradingMode.LIVE)
    
    @property
    def is_real_trading(self) -> bool:
        """是否为真实交易（仅实盘）"""
        return self == TradingMode.LIVE
    
    def get_description(self) -> str:
        """获取模式描述"""
        descriptions = {
            TradingMode.BACKTEST: "回测模式 - 使用历史数据，完整计算",
            TradingMode.PAPER: "模拟交易 - 实时数据，虚拟下单",
            TradingMode.LIVE: "实盘交易 - 实时数据，真实下单"
        }
        return descriptions.get(self, "未知模式")


@dataclass
class ModeContext:
    """
    交易模式上下文
    
    封装当前交易模式及其相关配置，提供模式感知能力
    """
    
    mode: TradingMode
    """当前交易模式"""
    
    config: Dict[str, Any] = field(default_factory=dict)
    """模式相关配置"""
    
    start_time: datetime = field(default_factory=datetime.now)
    """模式启动时间"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """元数据（用于扩展）"""
    
    @classmethod
    def create_backtest(cls, 
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       **kwargs) -> 'ModeContext':
        """
        创建回测模式上下文
        
        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
            **kwargs: 其他配置
            
        Returns:
            回测模式上下文
        """
        config = {
            'start_date': start_date,
            'end_date': end_date,
            'use_full_data': True,
            'enable_lookahead': False,
            'data_delay': 0,
        }
        config.update(kwargs)
        
        return cls(
            mode=TradingMode.BACKTEST,
            config=config,
            metadata={'type': 'backtest'}
        )
    
    @classmethod
    def create_paper(cls,
                    symbol: Optional[str] = None,
                    **kwargs) -> 'ModeContext':
        """
        创建模拟交易上下文
        
        Args:
            symbol: 交易标的
            **kwargs: 其他配置
            
        Returns:
            模拟交易上下文
        """
        config = {
            'symbol': symbol,
            'use_realtime_data': True,
            'enable_auto_trading': False,
            'risk_check_enabled': True,
            'commission_rate': 0.0003,
            'slippage': 0.0001,
            'stop_loss': 0.05,
            'take_profit': 0.12,
            'trailing_stop': 0.03,
            'position_ratio': 0.30,
            'single_stock_ratio': 0.15,
            'max_positions': 5,
            'lot_size': 100,
            '_strategy': 'MA5/MA20金叉死叉+止损止盈+仓位风控',
            '_source': 'Paper Trading验证: 胜率100% Sharpe=1.60 年化7.44%',
        }
        config.update(kwargs)
        
        return cls(
            mode=TradingMode.PAPER,
            config=config,
            metadata={'type': 'paper_trading'}
        )
    
    @classmethod
    def create_live(cls,
                   symbol: Optional[str] = None,
                   **kwargs) -> 'ModeContext':
        """
        创建实盘交易上下文
        
        Args:
            symbol: 交易标的
            **kwargs: 其他配置
            
        Returns:
            实盘交易上下文
        """
        config = {
            'symbol': symbol,
            'use_realtime_data': True,
            'enable_auto_trading': True,
            'risk_check_enabled': True,
            'performance_critical': True,
            'use_incremental': True,
            'commission_rate': 0.0003,
            'slippage': 0.0001,
            'stop_loss': 0.05,
            'take_profit': 0.12,
            'trailing_stop': 0.03,
            'position_ratio': 0.30,
            'single_stock_ratio': 0.15,
            'max_positions': 5,
            'lot_size': 100,
            '_source': '继承Paper Trading最优配置',
        }
        config.update(kwargs)
        
        return cls(
            mode=TradingMode.LIVE,
            config=config,
            metadata={'type': 'live_trading'}
        )
    
    def is_backtest(self) -> bool:
        """是否为回测模式"""
        return self.mode.is_backtest
    
    def is_live(self) -> bool:
        """是否为实盘模式（包含模拟和实盘）"""
        return self.mode.is_live
    
    def is_real_trading(self) -> bool:
        """是否为真实交易（仅实盘）"""
        return self.mode.is_real_trading
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """设置配置项"""
        self.config[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """设置元数据"""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'mode': self.mode.value,
            'config': self.config,
            'start_time': self.start_time.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModeContext':
        """从字典创建"""
        mode = TradingMode(data['mode'])
        context = cls(
            mode=mode,
            config=data.get('config', {}),
            metadata=data.get('metadata', {})
        )
        if 'start_time' in data:
            try:
                context.start_time = datetime.fromisoformat(data['start_time'])
            except Exception:
                pass
        return context


class ModeAwareMixin:
    """
    模式感知混入类
    
    为策略、引擎等组件提供模式感知能力
    """
    
    def __init__(self, *args, **kwargs):
        self._mode_context: Optional[ModeContext] = None
        super().__init__(*args, **kwargs)
    
    @property
    def mode_context(self) -> Optional[ModeContext]:
        """获取模式上下文"""
        return self._mode_context
    
    @mode_context.setter
    def mode_context(self, context: ModeContext) -> None:
        """设置模式上下文"""
        self._mode_context = context
        self._on_mode_changed(context)

    def set_mode_context(self, context: ModeContext) -> None:
        """设置模式上下文（方法形式，兼容旧接口）"""
        self.mode_context = context

    @property
    def trading_mode(self) -> Optional[TradingMode]:
        """获取当前交易模式"""
        return self._mode_context.mode if self._mode_context else None
    
    def is_backtest_mode(self) -> bool:
        """是否为回测模式"""
        return self._mode_context.is_backtest() if self._mode_context else False
    
    def is_live_mode(self) -> bool:
        """是否为实盘模式"""
        return self._mode_context.is_live() if self._mode_context else False
    
    def is_real_trading_mode(self) -> bool:
        """是否为真实交易模式"""
        return self._mode_context.is_real_trading() if self._mode_context else False
    
    def get_mode_config(self, key: str, default: Any = None) -> Any:
        """获取模式配置"""
        if self._mode_context:
            return self._mode_context.get_config(key, default)
        return default
    
    def _on_mode_changed(self, new_context: ModeContext) -> None:
        """
        模式切换回调
        
        子类可重写此方法以响应模式变化
        
        Args:
            new_context: 新的模式上下文
        """
        pass


def get_mode_description(mode: TradingMode) -> str:
    """
    获取模式描述
    
    Args:
        mode: 交易模式
        
    Returns:
        模式描述字符串
    """
    return mode.get_description()


def create_mode_context(mode_str: str, **kwargs) -> ModeContext:
    """
    根据字符串创建模式上下文
    
    Args:
        mode_str: 模式字符串 ('backtest', 'paper', 'live')
        **kwargs: 配置参数
        
    Returns:
        模式上下文
    """
    mode_map = {
        'backtest': ModeContext.create_backtest,
        'paper': ModeContext.create_paper,
        'live': ModeContext.create_live,
    }
    
    if mode_str not in mode_map:
        raise ValueError(f"未知的交易模式：{mode_str}，支持的：{list(mode_map.keys())}")
    
    return mode_map[mode_str](**kwargs)


# 导出常用符号
__all__ = [
    'TradingMode',
    'ModeContext',
    'ModeAwareMixin',
    'get_mode_description',
    'create_mode_context',
]
