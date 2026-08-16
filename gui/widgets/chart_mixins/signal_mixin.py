from loguru import logger

"""
信号处理Mixin - 处理交易信号的绘制、高亮和管理
"""

from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandas as pd

try:
    from PyQt5.QtCore import QMutexLocker
    QMUTEX_AVAILABLE = True
except ImportError:
    QMUTEX_AVAILABLE = False

try:
    from utils.theme import ThemeManager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False


def is_dark_theme(theme_manager) -> bool:
    """检测是否为暗色主题"""
    if theme_manager is None:
        return True
    try:
        if hasattr(theme_manager, 'is_dark_theme'):
            return theme_manager.is_dark_theme()
        if hasattr(theme_manager, 'current_theme') and hasattr(theme_manager.current_theme, 'is_dark'):
            return theme_manager.current_theme.is_dark()
        if hasattr(theme_manager, 'theme_type'):
            return theme_manager.theme_type.lower() == 'dark'
    except Exception as e:
        logger.debug(f"signal_mixin: {e}")
    return True


class PatternStyleManager:
    """形态渲染样式管理器 - 提供统一的形态渲染样式配置（支持主题适配）"""
    
    # 暗色主题样式
    DARK_STYLES = {
        'head_shoulders': {
            'region_color': (0.0, 1.0, 0.0, 0.15),
            'line_color': '#00FF00',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 100,
            'marker_color': '#00FF00',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#00FF00',
            'border_width': 1.0,
        },
        'head_shoulders_inverse': {
            'region_color': (1.0, 0.0, 0.0, 0.12),
            'line_color': '#FF0000',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 100,
            'marker_color': '#FF0000',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#FF0000',
            'border_width': 1.0,
        },
        'double_top': {
            'region_color': (0.0, 1.0, 0.0, 0.12),
            'line_color': '#00FF00',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': 'D',
            'marker_size': 80,
            'marker_color': '#00FF00',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#00FF00',
            'border_width': 1.0,
        },
        'double_bottom': {
            'region_color': (1.0, 0.0, 0.0, 0.12),
            'line_color': '#FF0000',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': 'D',
            'marker_size': 80,
            'marker_color': '#FF0000',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#FF0000',
            'border_width': 1.0,
        },
        'triangle': {
            'region_color': (0.3, 0.5, 1.0, 0.12),
            'line_color': '#5588FF',
            'line_style': ':',
            'line_width': 1.2,
            'marker': '^',
            'marker_size': 80,
            'marker_color': '#5588FF',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#5588FF',
            'border_width': 1.0,
        },
        'wedge': {
            'region_color': (0.8, 0.5, 0.2, 0.12),
            'line_color': '#CC8800',
            'line_style': '-.',
            'line_width': 1.2,
            'marker': '^',
            'marker_size': 80,
            'marker_color': '#CC8800',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#CC8800',
            'border_width': 1.0,
        },
        'channel': {
            'region_color': (0.5, 0.5, 0.5, 0.1),
            'line_color': '#888888',
            'line_style': '-',
            'line_width': 1.0,
            'marker': 'o',
            'marker_size': 60,
            'marker_color': '#888888',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.0,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#888888',
            'border_width': 1.0,
        },
        'flag': {
            'region_color': (0.2, 0.6, 0.8, 0.12),
            'line_color': '#00CED1',
            'line_style': '-',
            'line_width': 1.5,
            'marker': 's',
            'marker_size': 70,
            'marker_color': '#00CED1',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#00CED1',
            'border_width': 1.0,
        },
        'rectangle': {
            'region_color': (0.6, 0.4, 0.2, 0.12),
            'line_color': '#CD853F',
            'line_style': '-',
            'line_width': 1.5,
            'marker': 's',
            'marker_size': 80,
            'marker_color': '#CD853F',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#CD853F',
            'border_width': 1.0,
        },
        'symmetrical_triangle': {
            'region_color': (0.5, 0.3, 0.7, 0.12),
            'line_color': '#9370DB',
            'line_style': ':',
            'line_width': 1.5,
            'marker': 'D',
            'marker_size': 80,
            'marker_color': '#9370DB',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#9370DB',
            'border_width': 1.0,
        },
        'ascending_triangle': {
            'region_color': (0.3, 0.7, 0.4, 0.12),
            'line_color': '#32CD32',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': '^',
            'marker_size': 80,
            'marker_color': '#32CD32',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#32CD32',
            'border_width': 1.0,
        },
        'descending_triangle': {
            'region_color': (0.8, 0.3, 0.3, 0.12),
            'line_color': '#DC143C',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': 'v',
            'marker_size': 80,
            'marker_color': '#DC143C',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#DC143C',
            'border_width': 1.0,
        },
        'cup_and_handle': {
            'region_color': (0.9, 0.6, 0.1, 0.12),
            'line_color': '#FFB347',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 90,
            'marker_color': '#FFB347',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#FFB347',
            'border_width': 1.0,
        },
        'rounding_bottom': {
            'region_color': (0.4, 0.6, 0.8, 0.12),
            'line_color': '#6495ED',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 90,
            'marker_color': '#6495ED',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#6495ED',
            'border_width': 1.0,
        },
        'professional': {
            'region_color': (0.6, 0.3, 0.8, 0.12),
            'line_color': '#9944FF',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 100,
            'marker_color': '#9944FF',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#9944FF',
            'border_width': 1.0,
        },
        'one_click': {
            'region_color': (1.0, 0.65, 0.0, 0.12),
            'line_color': '#FFA500',
            'line_style': '-',
            'line_width': 1.2,
            'marker': 'v',
            'marker_size': 80,
            'marker_color': '#FFA500',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#FFA500',
            'border_width': 1.0,
        },
        'default': {
            'region_color': (1.0, 0.65, 0.0, 0.12),
            'line_color': '#FFA500',
            'line_style': '-',
            'line_width': 1.0,
            'marker': 'v',
            'marker_size': 80,
            'marker_color': '#FFA500',
            'marker_edge_color': '#FFFFFF',
            'marker_edge_width': 1.0,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#FFA500',
            'border_width': 1.0,
        }
    }
    
    # 亮色主题样式
    LIGHT_STYLES = {
        'head_shoulders': {
            'region_color': (0.0, 1.0, 0.0, 0.15),
            'line_color': '#00FF00',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 100,
            'marker_color': '#00FF00',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#00FF00',
            'border_width': 1.0,
        },
        'head_shoulders_inverse': {
            'region_color': (1.0, 0.0, 0.0, 0.12),
            'line_color': '#FF0000',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 100,
            'marker_color': '#FF0000',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#FF0000',
            'border_width': 1.0,
        },
        'double_top': {
            'region_color': (0.0, 1.0, 0.0, 0.12),
            'line_color': '#00FF00',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': 'D',
            'marker_size': 80,
            'marker_color': '#00FF00',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#00FF00',
            'border_width': 1.0,
        },
        'double_bottom': {
            'region_color': (1.0, 0.0, 0.0, 0.12),
            'line_color': '#FF0000',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': 'D',
            'marker_size': 80,
            'marker_color': '#FF0000',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#FF0000',
            'border_width': 1.0,
        },
        'triangle': {
            'region_color': (0.2, 0.4, 0.9, 0.12),
            'line_color': '#2255DD',
            'line_style': ':',
            'line_width': 1.2,
            'marker': '^',
            'marker_size': 80,
            'marker_color': '#2255DD',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#2255DD',
            'border_width': 1.0,
        },
        'wedge': {
            'region_color': (0.7, 0.4, 0.1, 0.12),
            'line_color': '#996600',
            'line_style': '-.',
            'line_width': 1.2,
            'marker': '^',
            'marker_size': 80,
            'marker_color': '#996600',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#996600',
            'border_width': 1.0,
        },
        'channel': {
            'region_color': (0.4, 0.4, 0.4, 0.1),
            'line_color': '#666666',
            'line_style': '-',
            'line_width': 1.0,
            'marker': 'o',
            'marker_size': 60,
            'marker_color': '#666666',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.0,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#666666',
            'border_width': 1.0,
        },
        'flag': {
            'region_color': (0.1, 0.5, 0.7, 0.12),
            'line_color': '#008B8B',
            'line_style': '-',
            'line_width': 1.5,
            'marker': 's',
            'marker_size': 70,
            'marker_color': '#008B8B',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#008B8B',
            'border_width': 1.0,
        },
        'rectangle': {
            'region_color': (0.5, 0.3, 0.1, 0.12),
            'line_color': '#A0522D',
            'line_style': '-',
            'line_width': 1.5,
            'marker': 's',
            'marker_size': 80,
            'marker_color': '#A0522D',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#A0522D',
            'border_width': 1.0,
        },
        'symmetrical_triangle': {
            'region_color': (0.4, 0.2, 0.6, 0.12),
            'line_color': '#8A2BE2',
            'line_style': ':',
            'line_width': 1.5,
            'marker': 'D',
            'marker_size': 80,
            'marker_color': '#8A2BE2',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#8A2BE2',
            'border_width': 1.0,
        },
        'ascending_triangle': {
            'region_color': (0.2, 0.6, 0.3, 0.12),
            'line_color': '#228B22',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': '^',
            'marker_size': 80,
            'marker_color': '#228B22',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#228B22',
            'border_width': 1.0,
        },
        'descending_triangle': {
            'region_color': (0.7, 0.2, 0.2, 0.12),
            'line_color': '#B22222',
            'line_style': '-.',
            'line_width': 1.5,
            'marker': 'v',
            'marker_size': 80,
            'marker_color': '#B22222',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#B22222',
            'border_width': 1.0,
        },
        'cup_and_handle': {
            'region_color': (0.8, 0.5, 0.0, 0.12),
            'line_color': '#DAA520',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 90,
            'marker_color': '#DAA520',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#DAA520',
            'border_width': 1.0,
        },
        'rounding_bottom': {
            'region_color': (0.3, 0.5, 0.7, 0.12),
            'line_color': '#4169E1',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 90,
            'marker_color': '#4169E1',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#4169E1',
            'border_width': 1.0,
        },
        'professional': {
            'region_color': (0.5, 0.2, 0.7, 0.12),
            'line_color': '#7722CC',
            'line_style': '--',
            'line_width': 1.5,
            'marker': 'o',
            'marker_size': 100,
            'marker_color': '#7722CC',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#7722CC',
            'border_width': 1.0,
        },
        'one_click': {
            'region_color': (0.9, 0.5, 0.0, 0.12),
            'line_color': '#DD8800',
            'line_style': '-',
            'line_width': 1.2,
            'marker': 'v',
            'marker_size': 80,
            'marker_color': '#DD8800',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#DD8800',
            'border_width': 1.0,
        },
        'default': {
            'region_color': (0.9, 0.5, 0.0, 0.12),
            'line_color': '#DD8800',
            'line_style': '-',
            'line_width': 1.0,
            'marker': 'v',
            'marker_size': 80,
            'marker_color': '#DD8800',
            'marker_edge_color': '#333333',
            'marker_edge_width': 1.0,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': '#DD8800',
            'border_width': 1.0,
        }
    }
    
    @classmethod
    def get_style(cls, pattern_type: str = 'default', is_dark: bool = True) -> dict:
        """获取形态样式配置（支持主题适配）
        
        Args:
            pattern_type: 形态类型
            is_dark: 是否为暗色主题
            
        Returns:
            样式配置字典
        """
        styles = cls.DARK_STYLES if is_dark else cls.LIGHT_STYLES
        return styles.get(pattern_type, styles['default'])
    
    @classmethod
    def get_style_by_analysis_type(cls, analysis_type: str, is_dark: bool = True) -> dict:
        """根据分析类型获取样式（支持主题适配）"""
        styles = cls.DARK_STYLES if is_dark else cls.LIGHT_STYLES
        
        if analysis_type == 'professional':
            return styles.get('professional', styles['default'])
        elif analysis_type == 'one_click':
            return styles.get('one_click', styles['default'])
        return styles['default']
    
    @classmethod
    def detect_pattern_type(cls, pattern_name: str) -> str:
        """根据形态名称自动检测类型"""
        name_lower = pattern_name.lower() if pattern_name else ''
        
        if 'head' in name_lower or 'shoulder' in name_lower or '头肩' in pattern_name:
            if 'inv' in name_lower or '底' in pattern_name:
                return 'head_shoulders_inverse'
            return 'head_shoulders'
        elif 'double_top' in name_lower or '双顶' in pattern_name or 'M顶' in pattern_name:
            return 'double_top'
        elif 'double_bottom' in name_lower or '双底' in pattern_name or 'W底' in pattern_name:
            return 'double_bottom'
        elif 'triangle' in name_lower or '三角' in pattern_name:
            if '对称' in name_lower or 'symmetric' in name_lower:
                return 'symmetrical_triangle'
            elif '上升' in name_lower or 'ascend' in name_lower:
                return 'ascending_triangle'
            elif '下降' in name_lower or 'descend' in name_lower:
                return 'descending_triangle'
            return 'triangle'
        elif 'wedge' in name_lower or '楔形' in pattern_name:
            return 'wedge'
        elif 'channel' in name_lower or '通道' in pattern_name:
            return 'channel'
        elif 'flag' in name_lower or '旗' in pattern_name:
            return 'flag'
        elif 'rectangle' in name_lower or '矩形' in pattern_name or '箱体' in pattern_name:
            return 'rectangle'
        elif 'cup' in name_lower or 'handle' in name_lower or '杯柄' in pattern_name:
            return 'cup_and_handle'
        elif 'rounding' in name_lower or '圆' in name_lower:
            return 'rounding_bottom'
        
        return 'default'
    
    @classmethod
    def _normalize_category(cls, category: str) -> str:
        """标准化形态类别名称
        
        采用精确匹配优先策略，避免短别名误匹配。
        """
        if not category:
            return 'unknown'
        
        cat_lower = category.lower()
        
        exact_reversal = {'reversal', '反转形态', 'candlestick'}
        exact_continuation = {'continuation', '持续形态'}
        exact_trend = {'trend', '趋势形态'}
        exact_complex = {'complex', '复杂形态'}
        exact_volume = {'volume', '价量形态'}
        exact_gap = {'gap', '缺口形态'}
        
        if cat_lower in exact_reversal:
            return 'reversal'
        if cat_lower in exact_continuation:
            return 'continuation'
        if cat_lower in exact_trend:
            return 'trend'
        if cat_lower in exact_complex:
            return 'complex'
        if cat_lower in exact_volume:
            return 'volume'
        if cat_lower in exact_gap:
            return 'gap'
        
        reversal_substrings = ['反转', 'revers', '顶部', '底部', 'k线']
        continuation_substrings = ['持续', 'continu', '盘整']
        trend_substrings = ['趋势']
        complex_substrings = ['复杂']
        volume_substrings = ['价量', '量能']
        gap_substrings = ['缺口', '跳空']
        
        for alias in reversal_substrings:
            if alias in cat_lower:
                return 'reversal'
        for alias in continuation_substrings:
            if alias in cat_lower:
                return 'continuation'
        for alias in trend_substrings:
            if alias in cat_lower:
                return 'trend'
        for alias in complex_substrings:
            if alias in cat_lower:
                return 'complex'
        for alias in volume_substrings:
            if alias in cat_lower:
                return 'volume'
        for alias in gap_substrings:
            if alias in cat_lower:
                return 'gap'
        
        return 'unknown'
    
    @classmethod
    def _normalize_signal(cls, signal) -> str:
        """标准化信号类型
        
        采用精确匹配优先策略，避免子串误匹配。
        例如 'close_long' 不应被 'long' 误判为 buy。
        """
        if not signal:
            return 'neutral'
        
        if hasattr(signal, 'value'):
            signal = signal.value
        
        sig_lower = str(signal).lower()
        
        exact_buy = {'buy', 'strong_buy', 'close_short'}
        exact_sell = {'sell', 'strong_sell', 'close_long'}
        
        if sig_lower in exact_buy:
            return 'buy'
        if sig_lower in exact_sell:
            return 'sell'
        
        buy_substrings = ['看涨', '买入', 'bullish', '多', '上涨']
        sell_substrings = ['看跌', '卖出', 'bearish', '空', '下跌']
        
        for alias in buy_substrings:
            if alias in sig_lower:
                return 'buy'
        for alias in sell_substrings:
            if alias in sig_lower:
                return 'sell'
        
        return 'neutral'
    
    # 动态样式模板 - 按形态类别和信号类型生成样式
    # 类别: reversal(反转), continuation(持续), trend(趋势), complex(复杂), volume(价量), gap(缺口), unknown(未知)
    # 信号: buy(看涨)→^, sell(看跌)→v, neutral(中性)→o
    CATEGORY_STYLES = {
        'reversal': {
            'buy': {'marker': '^', 'line_style': '--'},
            'sell': {'marker': 'v', 'line_style': '--'},
            'neutral': {'marker': 'o', 'line_style': '--'},
        },
        'continuation': {
            'buy': {'marker': '^', 'line_style': '-.'},
            'sell': {'marker': 'v', 'line_style': '-.'},
            'neutral': {'marker': 'o', 'line_style': '-.'},
        },
        'trend': {
            'buy': {'marker': '^', 'line_style': '-'},
            'sell': {'marker': 'v', 'line_style': '-'},
            'neutral': {'marker': 'o', 'line_style': '-'},
        },
        'complex': {
            'buy': {'marker': '^', 'line_style': ':'},
            'sell': {'marker': 'v', 'line_style': ':'},
            'neutral': {'marker': 'o', 'line_style': ':'},
        },
        'volume': {
            'buy': {'marker': '^', 'line_style': '--'},
            'sell': {'marker': 'v', 'line_style': '--'},
            'neutral': {'marker': 'o', 'line_style': '--'},
        },
        'gap': {
            'buy': {'marker': '^', 'line_style': '-.'},
            'sell': {'marker': 'v', 'line_style': '-.'},
            'neutral': {'marker': 'o', 'line_style': '-.'},
        },
        'unknown': {
            'buy': {'marker': '^', 'line_style': '-'},
            'sell': {'marker': 'v', 'line_style': '-'},
            'neutral': {'marker': 'o', 'line_style': '-'},
        },
    }
    
    # 颜色方案 - 按类别+信号+主题
    COLOR_SCHEMES = {
        ('reversal', 'buy'): {
            'dark': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)},
            'light': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)}
        },
        ('reversal', 'sell'): {
            'dark': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)},
            'light': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)}
        },
        ('continuation', 'buy'): {
            'dark': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)},
            'light': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)}
        },
        ('continuation', 'sell'): {
            'dark': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)},
            'light': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)}
        },
        ('trend', 'buy'): {
            'dark': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)},
            'light': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)}
        },
        ('trend', 'sell'): {
            'dark': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)},
            'light': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)}
        },
        ('trend', 'neutral'): {
            'dark': {'primary': '#888888', 'light': '#666666', 'region': (0.5, 0.5, 0.5, 0.1)},
            'light': {'primary': '#666666', 'light': '#808080', 'region': (0.4, 0.4, 0.4, 0.1)}
        },
        ('complex', 'neutral'): {
            'dark': {'primary': '#AA44FF', 'light': '#7722CC', 'region': (0.6, 0.2, 0.8, 0.12)},
            'light': {'primary': '#8B008B', 'light': '#9932CC', 'region': (0.5, 0.0, 0.5, 0.12)}
        },
        ('volume', 'buy'): {
            'dark': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)},
            'light': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)}
        },
        ('volume', 'sell'): {
            'dark': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)},
            'light': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)}
        },
        ('gap', 'buy'): {
            'dark': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)},
            'light': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)}
        },
        ('gap', 'sell'): {
            'dark': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)},
            'light': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)}
        },
        ('unknown', 'buy'): {
            'dark': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)},
            'light': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)}
        },
        ('unknown', 'sell'): {
            'dark': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)},
            'light': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)}
        },
        ('unknown', 'neutral'): {
            'dark': {'primary': '#FFA500', 'light': '#DD8800', 'region': (1.0, 0.65, 0.0, 0.12)},
            'light': {'primary': '#FF8C00', 'light': '#FFA500', 'region': (1.0, 0.5, 0.0, 0.12)}
        },
        ('reversal', 'neutral'): {
            'dark': {'primary': '#888888', 'light': '#666666', 'region': (0.5, 0.5, 0.5, 0.1)},
            'light': {'primary': '#666666', 'light': '#808080', 'region': (0.4, 0.4, 0.4, 0.1)}
        },
        ('continuation', 'neutral'): {
            'dark': {'primary': '#888888', 'light': '#666666', 'region': (0.5, 0.5, 0.5, 0.1)},
            'light': {'primary': '#666666', 'light': '#808080', 'region': (0.4, 0.4, 0.4, 0.1)}
        },
        ('complex', 'buy'): {
            'dark': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)},
            'light': {'primary': '#FF0000', 'light': '#FF0000', 'region': (1.0, 0.0, 0.0, 0.12)}
        },
        ('complex', 'sell'): {
            'dark': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)},
            'light': {'primary': '#00FF00', 'light': '#00FF00', 'region': (0.0, 1.0, 0.0, 0.12)}
        },
        ('volume', 'neutral'): {
            'dark': {'primary': '#888888', 'light': '#666666', 'region': (0.5, 0.5, 0.5, 0.1)},
            'light': {'primary': '#666666', 'light': '#808080', 'region': (0.4, 0.4, 0.4, 0.1)}
        },
        ('gap', 'neutral'): {
            'dark': {'primary': '#888888', 'light': '#666666', 'region': (0.5, 0.5, 0.5, 0.1)},
            'light': {'primary': '#666666', 'light': '#808080', 'region': (0.4, 0.4, 0.4, 0.1)}
        }
    }
    
    @classmethod
    def get_style_dynamic(cls, pattern_info: dict, is_dark: bool = True) -> dict:
        """动态生成样式 - 基于形态类别和信号类型
        
        Args:
            pattern_info: 形态信息字典，包含:
                - pattern_category: 形态类别 (reversal/continuation/trend/complex/volume/gap/unknown)
                - signal_type: 信号类型 (buy/sell/neutral)
                - pattern_type: 具体形态类型 (可选，用于精确匹配)
            is_dark: 是否为暗色主题
            
        Returns:
            完整的样式配置字典
        """
        category = pattern_info.get('pattern_category', 'unknown')
        signal = pattern_info.get('signal_type', 'neutral')
        
        if category is None:
            category = 'unknown'
        if signal is None:
            signal = 'neutral'
        
        category = cls._normalize_category(category)
        signal = cls._normalize_signal(signal)
        
        theme_key = 'dark' if is_dark else 'light'
        
        color_key = (category, signal)
        color_scheme = cls.COLOR_SCHEMES.get(color_key, cls.COLOR_SCHEMES.get(('unknown', 'neutral')))
        colors = color_scheme.get(theme_key, color_scheme['dark'])
        
        category_templates = cls.CATEGORY_STYLES.get(category, cls.CATEGORY_STYLES['unknown'])
        template = category_templates.get(signal, category_templates['neutral'])
        
        edge_color = '#FFFFFF' if is_dark else '#333333'
        
        style = {
            'region_color': colors['region'],
            'line_color': colors['primary'],
            'line_style': template.get('line_style', '-'),
            'line_width': 1.5,
            'marker': template.get('marker', 'o'),
            'marker_size': 80,
            'marker_color': colors['primary'],
            'marker_edge_color': edge_color,
            'marker_edge_width': 1.5,
            'glow_effect': False,
            'gradient_fill': False,
            'border_color': colors['primary'],
            'border_width': 1.0,
            'category': category,
            'signal': signal,
        }
        
        return style
    
    @classmethod
    def get_style_from_result(cls, pattern_result: dict, is_dark: bool = True) -> dict:
        """从PatternResult对象获取样式（支持动态和静态两种方式）
        
        Args:
            pattern_result: 形态识别结果字典，包含:
                - pattern_category: 形态类别
                - signal_type: 信号类型
                - pattern_name: 形态名称
                - pattern_type: 形态类型标识
            is_dark: 是否为暗色主题
            
        Returns:
            样式配置字典
        """
        if pattern_result.get('pattern_category') or pattern_result.get('signal_type'):
            return cls.get_style_dynamic(pattern_result, is_dark)
        
        pattern_type = pattern_result.get('pattern_type')
        if pattern_type:
            return cls.get_style(pattern_type, is_dark)
        
        pattern_name = pattern_result.get('pattern_name', '')
        detected_type = cls.detect_pattern_type(pattern_name)
        return cls.get_style(detected_type, is_dark)


class SignalMixin:

    def _safe_remove_artist(self, artist):
        """安全删除matplotlib artist对象 - 改进版本"""
        if artist is None:
            return True

        try:
            # 获取artist的类型信息
            artist_type = str(type(artist))

            # 方法1: 优先使用标准remove方法（对大部分对象有效）
            if hasattr(artist, 'remove'):
                try:
                    artist.remove()
                    return True
                except Exception as e:
                    # 如果是ArtistList错误，不记录为错误，因为这是已知问题
                    if 'ArtistList' not in str(e):
                        logger.debug(f"标准remove方法失败: {e}")

            # 方法2: 对于PathCollection等集合类型，从axes中移除
            if hasattr(artist, 'axes') and artist.axes is not None:
                axes = artist.axes

                # 检查并从各种集合中移除
                collections_to_check = [
                    ('collections', axes.collections),
                    ('texts', axes.texts),
                    ('patches', axes.patches),
                    ('lines', axes.lines),
                    ('images', axes.images)
                ]

                for collection_name, collection in collections_to_check:
                    if hasattr(axes, collection_name) and artist in collection:
                        try:
                            collection.remove(artist)
                            return True
                        except Exception as e:
                            logger.debug(f"从{collection_name}中移除失败: {e}")
                            continue

            # 方法2.1: 额外检查 - 从 figure 级别 collections 中移除
            if hasattr(self, 'figure') and self.figure is not None:
                for ax in self.figure.axes:
                    for collection_list in [ax.collections, ax.texts, ax.patches, ax.lines]:
                        if artist in collection_list:
                            try:
                                collection_list.remove(artist)
                                return True
                            except Exception as e:
                                logger.debug(f"signal_mixin: {e}")

            # 方法3: 如果以上都失败，至少隐藏对象
            if hasattr(artist, 'set_visible'):
                try:
                    artist.set_visible(False)
                    return True
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")

            # 方法4: 对于一些特殊类型，尝试设置alpha为0
            if hasattr(artist, 'set_alpha'):
                try:
                    artist.set_alpha(0)
                    return True
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")          

            return False

        except Exception as e:
            # 只有在非预期错误时才记录警告
            if 'ArtistList' not in str(e):
                logger.debug(f"删除artist时出现问题: {e}")
            return False

    def plot_signals(self, signals, visible_range=None, signal_filter=None):
        """绘制信号，支持密度自适应、聚合展示、气泡提示"""
        try:
            if not hasattr(self, 'price_ax') or not self.price_ax:
                return

            # 清除旧信号
            for artist in getattr(self, '_signal_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")
            self._signal_artists = []

            if not signals:
                self.canvas.draw_idle()
                # HV6：清空旧信号后背景快照已过时
                if hasattr(self, '_invalidate_crosshair_background'):
                    self._invalidate_crosshair_background()
                return

            # 获取当前可见区间
            if visible_range is None:
                visible_range = self.get_visible_range()

            # 筛选可见区间内的信号
            visible_signals = []
            if visible_range:
                start_idx, end_idx = visible_range
                for signal in signals:
                    sig_idx = signal.get('index', 0)
                    if start_idx <= sig_idx <= end_idx:
                        visible_signals.append(signal)
            else:
                visible_signals = signals

            # 信号密度自适应
            max_signals_per_screen = 20  # 每屏最多显示信号数
            if len(visible_signals) > max_signals_per_screen:
                # 选择重要信号
                visible_signals = self._select_important_signals(
                    visible_signals, max_signals_per_screen)

            # 绘制信号
            for signal in visible_signals:
                self._plot_single_signal(signal)

            # 启用气泡提示（如果有信号）
            if visible_signals:
                self._enable_signal_tooltips(visible_signals)

            # 更新画布
            self.canvas.draw_idle()
            # HV6：新信号绘制后背景快照过时（否则鼠标移动 restore 擦除信号标记）
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()

        except Exception as e:
            logger.error(f"绘制信号失败: {str(e)}")

    def draw_pattern_signals(self, all_indices: List[int], highlighted_index: int, pattern_name: str, analysis_type: str = "", pattern_data: dict = None):
        """在图表上绘制并高亮形态信号 - 线程安全增强版本
        
        参数:
            all_indices: 所有信号索引列表
            highlighted_index: 高亮信号索引
            pattern_name: 形态名称
            analysis_type: 分析类型 (professional/one_click)
            pattern_data: 形态详细数据，用于渲染区域背景和关键点连线
                - start_idx: 形态起始索引
                - end_idx: 形态结束索引
                - key_points: 关键点列表 [(idx, price), ...]
                - pattern_type: 形态类型 (head_shoulders/double_top/triangle等)
        """
        # 线程安全保护：尝试获取渲染锁
        if QMUTEX_AVAILABLE and hasattr(self, '_render_lock'):
            with QMutexLocker(self._render_lock):
                # R279：保存最后绘制的形态参数，供 update_chart 清场后恢复
                self._last_pattern_display = {
                    'all_indices': all_indices,
                    'highlighted_index': highlighted_index,
                    'pattern_name': pattern_name,
                    'analysis_type': analysis_type,
                    'pattern_data': pattern_data,
                }
                self._draw_pattern_signals_impl(
                    all_indices, highlighted_index, pattern_name, 
                    analysis_type, pattern_data
                )
        else:
            # R279：保存最后绘制的形态参数，供 update_chart 清场后恢复
            self._last_pattern_display = {
                'all_indices': all_indices,
                'highlighted_index': highlighted_index,
                'pattern_name': pattern_name,
                'analysis_type': analysis_type,
                'pattern_data': pattern_data,
            }
            self._draw_pattern_signals_impl(
                all_indices, highlighted_index, pattern_name,
                analysis_type, pattern_data
            )
    
    def _draw_pattern_signals_impl(self, all_indices: List[int], highlighted_index: int, 
                                   pattern_name: str, analysis_type: str, pattern_data: dict):
        """实际绘制实现 - 私有方法"""
        try:
            if not hasattr(self, 'price_ax') or not self.price_ax or self.current_kdata is None:
                logger.warning("无法绘制形态信号，因为图表或数据尚未准备好。")
                return

            # 数据一致性保护：复制数据避免引用
            kdata = self.current_kdata.copy()
            
            # 获取主题信息
            is_dark = True
            if hasattr(self, 'theme_manager') and self.theme_manager is not None:
                is_dark = is_dark_theme(self.theme_manager)
            
            # 获取样式配置
            pattern_type = None
            
            pattern_info = {}
            if pattern_data:
                pattern_info = {
                    'pattern_category': pattern_data.get('pattern_category'),
                    'signal_type': pattern_data.get('signal_type'),
                    'pattern_type': pattern_data.get('pattern_type'),
                    'pattern_name': pattern_name,
                }
            
            if pattern_data and 'pattern_type' in pattern_data:
                pattern_type = pattern_data['pattern_type']
            else:
                pattern_type = PatternStyleManager.detect_pattern_type(pattern_name)
                pattern_info['pattern_type'] = pattern_type
            
            if pattern_info.get('pattern_category') or pattern_info.get('signal_type'):
                logger.info(f"使用动态样式: category={pattern_info.get('pattern_category')}, signal={pattern_info.get('signal_type')}")
                style = PatternStyleManager.get_style_dynamic(pattern_info, is_dark)
            elif pattern_data and (pattern_data.get('pattern_category') or pattern_data.get('signal_type')):
                logger.info(f"从pattern_data使用动态样式: category={pattern_data.get('pattern_category')}, signal={pattern_data.get('signal_type')}")
                style = PatternStyleManager.get_style_dynamic(pattern_data, is_dark)
            elif analysis_type:
                style = PatternStyleManager.get_style_by_analysis_type(analysis_type, is_dark)
            else:
                style = PatternStyleManager.get_style(pattern_type, is_dark)
            
            logger.info(f"绘制形态信号: pattern={pattern_name}, type={pattern_type}, "
                        f"analysis={analysis_type}, 信号数量: {len(all_indices)}, style={pattern_type}")

            # 清除之前绘制的形态信号
            self._clear_pattern_artists()
            
            # 确保列表已初始化
            if not hasattr(self, '_pattern_signal_artists'):
                self._pattern_signal_artists = []

            # 绘制形态区域背景（新增功能）
            region_artist = self._render_pattern_region(pattern_data, kdata, style)
            if region_artist:
                if isinstance(region_artist, list):
                    self._pattern_signal_artists.extend(region_artist)
                else:
                    self._pattern_signal_artists.append(region_artist)

            # 绘制形态关键点连线（新增功能）
            line_artist = self._render_pattern_lines(pattern_data, kdata, style)
            if line_artist:
                if isinstance(line_artist, tuple):
                    self._pattern_signal_artists.extend(line_artist)
                elif isinstance(line_artist, list):
                    self._pattern_signal_artists.extend(line_artist)
                else:
                    self._pattern_signal_artists.append(line_artist)

            # 去重索引，避免重复绘制
            unique_indices = list(set(all_indices))
            logger.debug(f"准备绘制 {len(unique_indices)} 个唯一的形态信号（原始数量: {len(all_indices)}）")
            
            # 绘制所有信号标记点
            drawn_count = 0
            for index in unique_indices:
                if 0 <= index < len(kdata):
                    try:
                        price = float(kdata['high'].iloc[index]) * 1.02
                        
                        if pd.isna(price) or price <= 0:
                            logger.warning(f"索引 {index} 的价格无效: {price}")
                            continue

                        is_highlighted = (index == highlighted_index)
                        
                        # 使用样式配置
                        marker = style.get('marker', 'o')
                        # 高亮时放大，但保持使用样式中定义的标记
                        size = style.get('marker_size', 80) * 1.5 if is_highlighted else style.get('marker_size', 80)
                        color = style.get('marker_color', '#FFA500')
                        # 高亮时保持原色，只增加不透明度
                        alpha = 1.0 if is_highlighted else 0.75
                        zorder = 10 if is_highlighted else 5
                        edge_color = style.get('marker_edge_color', 'white')

                        scatter = self.price_ax.scatter(
                            index, price, 
                            s=size, 
                            c=color, 
                            marker=marker,
                            alpha=alpha, 
                            edgecolors=edge_color, 
                            linewidth=style.get('marker_edge_width', 1.5), 
                            zorder=zorder,
                            label=pattern_name if is_highlighted else None
                        )
                        self._pattern_signal_artists.append(scatter)
                        drawn_count += 1

                        # 高亮信号添加标签
                        if is_highlighted:
                            text = self.price_ax.text(
                                index, price, f'  {pattern_name}',
                                fontsize=9, 
                                color=color, 
                                va='bottom',
                                ha='left',
                                fontweight='bold',
                                bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.9, edgecolor=color),
                                zorder=zorder + 1
                            )
                            self._pattern_signal_artists.append(text)
                    except Exception as e:
                        logger.warning(f"绘制索引 {index} 的信号失败: {e}")
                        continue

            # 调整坐标轴范围
            if drawn_count > 0:
                self._adjust_axis_limits(unique_indices, kdata)

            # 统一绘制，避免过度渲染
            if hasattr(self, 'canvas') and self.canvas:
                try:
                    self.canvas.draw_idle()
                    # R279 修复：形态绘制后失效十字光标 blit 背景。
                    # 否则 blit 背景快照停留在"无形态"旧画面，鼠标移入中间面板时
                    # _blit_crosshair 的 restore_region 会把画布覆盖回旧快照，
                    # 形态标记被物理擦除（用户报告的"鼠标移入即消失"根因）。
                    if hasattr(self, '_invalidate_crosshair_background'):
                        self._invalidate_crosshair_background()
                except Exception as e:
                    logger.warning(f"canvas.draw_idle() 失败: {e}")
            
            logger.info(f"成功绘制了 {drawn_count} 个 '{pattern_name}' 形态信号（去重后），并高亮显示了索引 {highlighted_index}。")

        except Exception as e:
            logger.error(f"绘制形态信号失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _render_pattern_region(self, pattern_data: dict, kdata, style: dict):
        """渲染形态区域背景"""
        if not pattern_data:
            return None
        
        try:
            start_idx = pattern_data.get('start_idx')
            end_idx = pattern_data.get('end_idx')
            
            if start_idx is None or end_idx is None:
                return None
            
            start_idx = max(0, int(start_idx) - 1)
            end_idx = min(len(kdata) - 1, int(end_idx) + 1)
            
            if start_idx >= end_idx:
                return None
            
            artists = []
            
            region = self.price_ax.axvspan(
                start_idx, end_idx,
                color=style.get('region_color', (1.0, 0.65, 0.0, 0.12)),
                zorder=1,
                alpha=0.15
            )
            artists.append(region)
            
            # 移除渐变填充以提高性能
            # if style.get('gradient_fill', False):
            #     for i in range(1, 6):
            #         alpha = 0.02 * i
            #         gradient_region = self.price_ax.axvspan(
            #             start_idx, end_idx,
            #             color=style.get('region_color', (1.0, 0.65, 0.0, 0.12)),
            #             zorder=1,
            #             alpha=alpha
            #         )
            #         artists.append(gradient_region)
            
            if style.get('border_color') and style.get('border_width', 0) > 0:
                border_left = self.price_ax.axvline(
                    x=start_idx,
                    color=style.get('border_color'),
                    linewidth=style.get('border_width', 1.0),
                    linestyle='--',
                    alpha=0.7,
                    zorder=2
                )
                border_right = self.price_ax.axvline(
                    x=end_idx,
                    color=style.get('border_color'),
                    linewidth=style.get('border_width', 1.0),
                    linestyle='--',
                    alpha=0.7,
                    zorder=2
                )
                artists.extend([border_left, border_right])
            
            return artists if len(artists) > 1 else artists[0] if artists else None
            
        except Exception as e:
            logger.debug(f"渲染形态区域背景失败: {e}")
            return None
    
    def _render_pattern_lines(self, pattern_data: dict, kdata, style: dict):
        """渲染形态关键点连线"""
        if not pattern_data:
            return None
        
        try:
            key_points = pattern_data.get('key_points', [])
            
            if not key_points or len(key_points) < 2:
                return None
            
            # 确保所有点都在有效范围内
            valid_points = []
            for idx, price in key_points:
                if 0 <= idx < len(kdata):
                    try:
                        if price is None:
                            price = float(kdata['high'].iloc[idx])
                        valid_points.append((idx, price))
                    except Exception:
                        continue
            
            if len(valid_points) < 2:
                return None
            
            x_coords = [p[0] for p in valid_points]
            y_coords = [p[1] for p in valid_points]
            
            line, = self.price_ax.plot(
                x_coords, y_coords,
                color=style.get('line_color', '#FFA500'),
                linestyle=style.get('line_style', '-'),
                linewidth=style.get('line_width', 1.5),
                marker=style.get('marker', 'o'),
                markersize=8,
                markerfacecolor=style.get('marker_color', '#FFA500'),
                markeredgecolor=style.get('marker_edge_color', 'white'),
                markeredgewidth=style.get('marker_edge_width', 1.5),
                zorder=3,
                alpha=0.85
            )
            
            if style.get('glow_effect', False):
                glow_line, = self.price_ax.plot(
                    x_coords, y_coords,
                    color=style.get('marker_color', '#FFA500'),
                    linestyle=style.get('line_style', '-'),
                    linewidth=style.get('line_width', 1.5) + 3,
                    marker=style.get('marker', 'o'),
                    markersize=12,
                    markerfacecolor='none',
                    markeredgecolor=style.get('marker_color', '#FFA500'),
                    markeredgewidth=0.5,
                    zorder=2,
                    alpha=0.3
                )
                return line, glow_line
            
            return line
            
        except Exception as e:
            logger.debug(f"渲染形态关键点连线失败: {e}")
            return None
    
    def _clear_pattern_artists(self):
        """清除之前的形态渲染对象"""
        if not hasattr(self, '_pattern_signal_artists'):
            self._pattern_signal_artists = []
            return
        
        if self._pattern_signal_artists:
            for artist in self._pattern_signal_artists[:]:
                try:
                    self._safe_remove_artist(artist)
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")
        self._pattern_signal_artists = []
    
    def _adjust_axis_limits(self, unique_indices: list, kdata):
        """调整坐标轴范围以包含所有信号"""
        try:
            xlim = self.price_ax.get_xlim()
            ylim = self.price_ax.get_ylim()
            
            if unique_indices:
                min_idx = min(unique_indices)
                max_idx = max(unique_indices)
                
                new_xlim = (
                    min(xlim[0], max(0, min_idx - 10)),
                    max(xlim[1], max_idx + 10)
                )
                
                signal_prices = []
                for idx in unique_indices:
                    if 0 <= idx < len(kdata):
                        try:
                            p = float(kdata['high'].iloc[idx]) * 1.08
                            if not pd.isna(p) and p > 0:
                                signal_prices.append(p)
                        except Exception as e:
                            logger.debug(f"signal_mixin: {e}")
                
                if signal_prices:
                    min_price = min(signal_prices)
                    max_price = max(signal_prices)
                    new_ylim = (
                        min(ylim[0], min_price * 0.95),
                        max(ylim[1], max_price * 1.08)
                    )
                    
                    self.price_ax.set_xlim(new_xlim)
                    self.price_ax.set_ylim(new_ylim)
        except Exception as e:
            logger.debug(f"调整坐标轴范围失败: {e}")

    def _select_important_signals(self, signals, max_count):
        """选择重要信号，根据置信度和类型优先级"""
        # 按置信度排序，选择top signals
        sorted_signals = sorted(signals, key=lambda s: s.get('confidence', 0),
                                reverse=True)
        return sorted_signals[:max_count]

    def _plot_single_signal(self, signal):
        """绘制单个信号标记"""
        try:
            idx = signal.get('index', 0)
            signal_type = signal.get('type', 'unknown')
            confidence = signal.get('confidence', 0)
            price = signal.get('price', 0)

            # 根据信号类型设置颜色和标记（中国股市习惯：买入=红色，卖出=绿色）
            if signal_type == 'double_top':
                color = 'green'
                marker = 'v'
                label = 'DT'
            elif signal_type == 'double_bottom':
                color = 'red'
                marker = '^'
                label = 'DB'
            else:
                color = 'blue'
                marker = 'o'
                label = signal_type[:2].upper()

            # 信号标记
            scatter = self.price_ax.scatter(idx, price, c=color, marker=marker, s=80,
                                           alpha=0.8, edgecolors='white', linewidth=1)
            self._signal_artists.append(scatter)

            # 简洁文字标注（仅高置信度显示）
            if confidence > 0.7:
                text = self.price_ax.text(idx, price * 1.01, label,
                                         fontsize=8, ha='center', va='bottom',
                                         color=color, fontweight='bold',
                                         bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
                self._signal_artists.append(text)

        except Exception as e:
            logger.error(f"绘制单个信号失败: {str(e)}")

    def _enable_signal_tooltips(self, signals):
        """启用信号气泡提示 - 通过标志位与十字光标协调工作"""
        self._signal_tooltips_enabled = True

        # 存储信号数据供十字光标使用（避免重复tooltip）
        self._signal_tooltip_map = {}
        for signal in signals:
            idx = signal.get('index', 0)
            self._signal_tooltip_map[idx] = signal

    def _disable_signal_tooltips(self):
        """禁用信号气泡提示"""
        if hasattr(self, '_signal_tooltips_enabled'):
            self._signal_tooltips_enabled = False
            self._signal_tooltip_map = {}

            # 清除现有提示
            for artist in getattr(self, '_tooltip_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")
            self._tooltip_artists = []

    def get_signal_tooltip_at_index(self, idx: int) -> str:
        """获取指定索引处的信号提示信息，供十字光标调用

        Args:
            idx: K线数据索引

        Returns:
            格式化的信号提示字符串，如果无信号则返回空字符串
        """
        if not hasattr(self, '_signal_tooltip_map') or idx not in self._signal_tooltip_map:
            return ""

        try:
            signal = self._signal_tooltip_map[idx]
            signal_type = signal.get('type', 'unknown')
            confidence = signal.get('confidence', 0)
            price = signal.get('price', 0)

            signal_type_cn = {
                'double_top': '双顶',
                'double_bottom': '双底',
                'head_shoulders': '头肩顶',
                'inverse_head_shoulders': '头肩底',
                'triangle': '三角形',
                'wedge': '楔形',
                'flag': '旗形'
            }.get(signal_type, signal_type)

            return f"类型: {signal_type_cn}\n置信度: {confidence:.2%}\n价格: {price:.2f}"
        except Exception:
            return ""

    def highlight_signal(self, signal_index: int, signal_data: dict = None):
        """高亮显示特定信号"""
        try:
            # 清除之前的高亮
            for artist in getattr(self, '_highlight_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")
            self._highlight_artists = []

            if signal_data:
                # 高亮圆圈
                idx = signal_data.get('index', signal_index)
                price = signal_data.get('price', 0)

                highlight_circle = self.price_ax.scatter(idx, price, s=200,
                                                        facecolors='none',
                                                        edgecolors='yellow',
                                                        linewidths=3, alpha=0.8, zorder=100)
                self._highlight_artists.append(highlight_circle)

            self.canvas.draw_idle()
            # HV6：高亮后背景快照过时（否则鼠标移动 restore 擦除高亮圆圈）
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()

        except Exception as e:
            logger.error(f"高亮信号失败: {str(e)}")

    def clear_signal_highlight(self):
        """清除信号高亮"""
        try:
            # 移除高亮对象
            for artist in getattr(self, '_highlight_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")
            self._highlight_artists = []

            # 清除气泡提示
            for artist in getattr(self, '_tooltip_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception as e:
                    logger.debug(f"signal_mixin: {e}")
            self._tooltip_artists = []

            self.canvas.draw_idle()
            # HV6：清除高亮后背景快照过时
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()

        except Exception as e:
            logger.error(f"清除信号高亮失败: {str(e)}")

    def plot_patterns(self, pattern_signals: list, highlight_index: int = None):
        """
        专业化形态信号显示：使用彩色箭头标记，默认隐藏浮窗，集成到十字光标显示
        Args:
            pattern_signals: List[dict]，每个dict至少包含 'index', 'pattern', 'signal', 'confidence' 等字段
        """
        if not hasattr(self, 'price_ax') or self.current_kdata is None or not pattern_signals:
            return

        ax = self.price_ax
        kdata = self.current_kdata
        x = np.arange(len(kdata))

        # 专业化颜色配置 - 参考同花顺、东方财富等软件（中国股市习惯：买入=亮红色，卖出=亮绿色）
        signal_colors = {
            'buy': '#FF0000',      # 买入信号 - 亮红色箭头向上
            'sell': '#00FF00',     # 卖出信号 - 亮绿色箭头向下
            'neutral': '#FFB000'   # 中性信号 - 橙色圆点
        }

        # 置信度透明度映射
        def get_alpha(confidence):
            if confidence >= 0.8:
                return 1.0
            elif confidence >= 0.6:
                return 0.8
            else:
                return 0.6

        # 存储形态信息供十字光标使用
        self._pattern_info = {}

        # 统计有效和无效的形态信号
        valid_patterns = 0
        invalid_patterns = 0

        for pat in pattern_signals:
            try:
                idx = pat.get('index', 0)
                pattern_name = pat.get('pattern', 'unknown')
                signal = pat.get('signal', 'neutral')
                confidence = pat.get('confidence', 0.5)

                # 验证索引有效性
                if idx < 0 or idx >= len(kdata):
                    invalid_patterns += 1
                    continue

                valid_patterns += 1

                # 获取颜色和透明度
                color = signal_colors.get(signal, signal_colors['neutral'])
                alpha = get_alpha(confidence)

                # 绘制专业箭头标记
                if signal == 'buy':
                    # 买入信号：空心向上三角，位于K线下方
                    arrow_y = kdata.iloc[idx]['low'] - \
                        (kdata.iloc[idx]['high'] - kdata.iloc[idx]['low']) * 0.15
                    ax.scatter(idx, arrow_y, marker='^', s=80, facecolors='none',
                               edgecolors=color, linewidths=0.8, alpha=alpha, zorder=100)
                elif signal == 'sell':
                    # 卖出信号：空心向下三角，位于K线上方
                    arrow_y = kdata.iloc[idx]['high'] + \
                        (kdata.iloc[idx]['high'] - kdata.iloc[idx]['low']) * 0.15
                    ax.scatter(idx, arrow_y, marker='v', s=80, facecolors='none',
                               edgecolors=color, linewidths=0.8, alpha=alpha, zorder=100)
                else:
                    # 中性信号：空心圆点，位于收盘价位置
                    ax.scatter(idx, kdata.iloc[idx]['close'], marker='o', s=60, facecolors='none',
                               edgecolors=color, linewidths=0.8, alpha=alpha, zorder=100)

                # 存储形态信息供十字光标显示
                self._pattern_info[idx] = {
                    'pattern_name': pattern_name,
                    'signal': signal,
                    'confidence': confidence,
                    'signal_cn': {'buy': '买入', 'sell': '卖出', 'neutral': '中性'}.get(signal, signal),
                    'price': kdata.iloc[idx]['close'],
                    'datetime': kdata.index[idx].strftime('%Y-%m-%d') if hasattr(kdata.index[idx], 'strftime') else str(kdata.index[idx])
                }

            except Exception as e:
                invalid_patterns += 1
                logger.error(f"绘制形态信号出错 {idx}: {e}")

        # 记录绘制结果
        logger.info(
                f"形态信号绘制完成: 有效 {valid_patterns} 个, 无效 {invalid_patterns} 个")

        # 高亮特定形态（如果指定）
        if highlight_index is not None and highlight_index in self._pattern_info:
            self.highlight_signal(highlight_index, self._pattern_info[highlight_index])

        # 刷新图表
        if hasattr(self, 'canvas'):
            self.canvas.draw_idle()
            # HV6：形态绘制后背景快照过时
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()
