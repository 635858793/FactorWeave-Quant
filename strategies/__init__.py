"""
策略模块 - 版本说明
=============================================================
| 文件                         | 版本     | 说明                        |
|------------------------------|----------|-----------------------------|
| adj_vwap_strategies.py       | ✅ 完整版 | 推荐使用，含完整交易逻辑     |
| strategy_adapters.py         | ⚠️ 简化版 | 适配器/模拟数据，用于兼容    |
=============================================================

AdjMomentumPlugin、VWAPReversionPlugin 在两个文件中均有定义：
  - adj_vwap_strategies.py  → 完整版（✅ 推荐）
  - strategy_adapters.py    → 简化版（⚠️ 含模拟数据）

默认导出完整版（adj_vwap_strategies.py），如需简化版请直接导入 strategy_adapters。
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导出策略类供外部使用（默认使用完整版）
try:
    from .adj_vwap_strategies import AdjMomentumPlugin, VWAPReversionPlugin
    from core.trading.strategy_manager import StrategyManager, get_strategy_manager
    __all__ = ['AdjMomentumPlugin', 'VWAPReversionPlugin', 'StrategyManager', 'get_strategy_manager']
except ImportError as e:
    from loguru import logger
    logger.error(f"导入策略模块失败: {e}")
    logger.error(f"当前sys.path: {sys.path}")
    __all__ = []

# 版本信息
__version__ = '1.0.0'