#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析标签页模块
"""

from .base_tab import BaseAnalysisTab
# professional_sentiment_tab已删除（性能优化）
# 修复：enhanced_kline_technical_tab 模块未实现，暂时注释掉
# from .enhanced_kline_technical_tab import EnhancedKLineTechnicalTab
from .technical_tab import TechnicalAnalysisTab
from .trend_tab import TrendAnalysisTab
from .wave_tab import WaveAnalysisTab
from .wave_tab_pro import WaveAnalysisTabPro
from .sector_flow_tab import SectorFlowTab
from .sector_flow_tab_pro import SectorFlowTabPro
from .pattern_tab import PatternAnalysisTab
from .pattern_tab_pro import PatternAnalysisTabPro
from .hotspot_tab import HotspotAnalysisTab

__all__ = [
    'BaseAnalysisTab',
    # 'EnhancedKLineTechnicalTab',  # 修复：模块未实现，暂时移除
    'TechnicalAnalysisTab',
    'TrendAnalysisTab',
    'WaveAnalysisTab',
    'WaveAnalysisTabPro',
    'SectorFlowTab',
    'SectorFlowTabPro',
    'PatternAnalysisTab',
    'PatternAnalysisTabPro',
    'HotspotAnalysisTab',
]
