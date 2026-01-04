"""
策略插件目录

包含各种交易策略的实现，作为插件形式提供给系统使用。
"""

from .trend_following import *
from .adaptive_strategy import *
from .moving_average_strategy import *
from .mean_reversion_strategy import *

__all__ = [
    # 趋势跟踪策略
    'TrendFollowingStrategy',

    # 自适应策略
    'AdaptiveStrategy',
    
    # 双均线策略
    'MovingAverageStrategyPlugin',
    
    # 均值回归策略
    'MeanReversionStrategyPlugin',
]
