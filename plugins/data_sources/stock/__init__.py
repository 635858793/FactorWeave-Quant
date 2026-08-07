"""
A股数据源插件目录

包含所有针对中国A股市场的数据源插件
"""

from pathlib import Path

# 插件列表
STOCK_PLUGINS = [
    'tongdaxin_plugin',      # 通达信（高性能K线）
    'eastmoney_plugin',      # 东方财富（综合数据）
    'akshare_plugin',        # AkShare（开源）
    'sina_plugin',           # 新浪（快速行情）
    'level2_realtime_plugin',  # Level-2（高频数据）
    'baostock_plugin'        # Baostock（免费历史K线，含复权）
]

__all__ = STOCK_PLUGINS
