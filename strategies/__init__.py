"""
策略模块
包含各种交易策略实现
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导出策略类供外部使用
try:
    from .adj_vwap_strategies import AdjMomentumPlugin, VWAPReversionPlugin
    from .strategy_manager import StrategyManager, get_strategy_manager
    __all__ = ['AdjMomentumPlugin', 'VWAPReversionPlugin', 'StrategyManager', 'get_strategy_manager']
except ImportError as e:
    import logging
    logging.error(f"导入策略模块失败: {e}")
    logging.error(f"当前sys.path: {sys.path}")
    __all__ = []

# 版本信息
__version__ = '1.0.0'
