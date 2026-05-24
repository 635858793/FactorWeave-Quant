"""
统一设计系统
建立统一的UI设计规范和组件标准，定义颜色、字体、间距等设计元素
"""

from loguru import logger
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from PyQt5.QtGui import QColor, QFont, QPalette, QPixmap, QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
import json
import os

class ColorScheme(Enum):
    """颜色方案枚举"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"
    HIGH_CONTRAST = "high_contrast"

class ComponentSize(Enum):
    """组件尺寸枚举"""
    EXTRA_SMALL = "xs"
    SMALL = "sm"
    MEDIUM = "md"
    LARGE = "lg"
    EXTRA_LARGE = "xl"

class IconSize(Enum):
    """图标尺寸枚举"""
    TINY = 12
    SMALL = 16
    MEDIUM = 24
    LARGE = 32
    EXTRA_LARGE = 48

@dataclass
class ColorPalette:
    """颜色调色板数据类"""
    # 主色调
    primary_50: str = "#E3F2FD"
    primary_100: str = "#BBDEFB"
    primary_200: str = "#90CAF9"
    primary_300: str = "#64B5F6"
    primary_400: str = "#42A5F5"
    primary_500: str = "#2196F3"  # 主色
    primary_600: str = "#1E88E5"
    primary_700: str = "#1976D2"
    primary_800: str = "#1565C0"
    primary_900: str = "#0D47A1"
    
    # 辅助色调
    secondary_50: str = "#FFF3E0"
    secondary_100: str = "#FFE0B2"
    secondary_200: str = "#FFCC80"
    secondary_300: str = "#FFB74D"
    secondary_400: str = "#FFA726"
    secondary_500: str = "#FF9800"  # 辅助色
    secondary_600: str = "#FB8C00"
    secondary_700: str = "#F57C00"
    secondary_800: str = "#EF6C00"
    secondary_900: str = "#E65100"
    
    # 状态色调
    success_50: str = "#E8F5E8"
    success_500: str = "#4CAF50"
    success_700: str = "#388E3C"
    
    warning_50: str = "#FFF8E1"
    warning_500: str = "#FFC107"
    warning_700: str = "#F57C00"
    
    error_50: str = "#FFEBEE"
    error_500: str = "#F44336"
    error_700: str = "#D32F2F"
    
    info_50: str = "#E1F5FE"
    info_500: str = "#03A9F4"
    info_700: str = "#0288D1"
    
    # 中性色调
    grey_50: str = "#FAFAFA"
    grey_100: str = "#F5F5F5"
    grey_200: str = "#EEEEEE"
    grey_300: str = "#E0E0E0"
    grey_400: str = "#BDBDBD"
    grey_500: str = "#9E9E9E"
    grey_600: str = "#757575"
    grey_700: str = "#616161"
    grey_800: str = "#424242"
    grey_900: str = "#212121"
    
    # 背景色
    background_default: str = "#FFFFFF"
    background_paper: str = "#FFFFFF"
    background_level1: str = "#F5F5F5"
    background_level2: str = "#EEEEEE"
    
    # 文本色
    text_primary: str = "#212121"
    text_secondary: str = "#757575"
    text_disabled: str = "#BDBDBD"
    text_hint: str = "#9E9E9E"
    
    # 边框色
    border_light: str = "#E0E0E0"
    border_medium: str = "#BDBDBD"
    border_dark: str = "#757575"
    
    # 阴影色
    shadow_light: str = "rgba(0, 0, 0, 0.12)"
    shadow_medium: str = "rgba(0, 0, 0, 0.16)"
    shadow_dark: str = "rgba(0, 0, 0, 0.24)"

@dataclass
class DarkColorPalette(ColorPalette):
    """深色主题调色板"""
    # 重写深色主题的颜色
    background_default: str = "#121212"
    background_paper: str = "#1E1E1E"
    background_level1: str = "#2C2C2C"
    background_level2: str = "#383838"
    
    text_primary: str = "#FFFFFF"
    text_secondary: str = "#B0B0B0"
    text_disabled: str = "#6C6C6C"
    text_hint: str = "#8C8C8C"
    
    border_light: str = "#383838"
    border_medium: str = "#4C4C4C"
    border_dark: str = "#6C6C6C"

@dataclass
class Typography:
    """字体排版数据类"""
    # 字体族
    font_family_primary: str = "Microsoft YaHei UI"
    font_family_secondary: str = "Arial, sans-serif"
    font_family_monospace: str = "Consolas, Monaco, monospace"
    
    # 字体大小（像素）
    font_size_xs: int = 10
    font_size_sm: int = 12
    font_size_md: int = 14
    font_size_lg: int = 16
    font_size_xl: int = 18
    font_size_xxl: int = 20
    font_size_xxxl: int = 24
    
    # 行高
    line_height_tight: float = 1.2
    line_height_normal: float = 1.4
    line_height_relaxed: float = 1.6
    
    # 字重
    font_weight_light: int = 300
    font_weight_normal: int = 400
    font_weight_medium: int = 500
    font_weight_semibold: int = 600
    font_weight_bold: int = 700
    
    # 标题样式
    h1_size: int = 32
    h1_weight: int = 700
    h1_line_height: float = 1.2
    
    h2_size: int = 28
    h2_weight: int = 600
    h2_line_height: float = 1.3
    
    h3_size: int = 24
    h3_weight: int = 600
    h3_line_height: float = 1.3
    
    h4_size: int = 20
    h4_weight: int = 500
    h4_line_height: float = 1.4
    
    h5_size: int = 18
    h5_weight: int = 500
    h5_line_height: float = 1.4
    
    h6_size: int = 16
    h6_weight: int = 500
    h6_line_height: float = 1.4
    
    # 正文样式
    body1_size: int = 16
    body1_weight: int = 400
    body1_line_height: float = 1.5
    
    body2_size: int = 14
    body2_weight: int = 400
    body2_line_height: float = 1.4
    
    # 说明文字样式
    caption_size: int = 12
    caption_weight: int = 400
    caption_line_height: float = 1.3
    
    # 按钮文字样式
    button_size: int = 14
    button_weight: int = 500
    button_line_height: float = 1.4

@dataclass
class Spacing:
    """间距系统数据类"""
    # 基础间距单位（像素）
    unit: int = 4
    
    # 间距级别
    xs: int = 4    # 1 * unit
    sm: int = 8    # 2 * unit
    md: int = 16   # 4 * unit
    lg: int = 24   # 6 * unit
    xl: int = 32   # 8 * unit
    xxl: int = 48  # 12 * unit
    xxxl: int = 64 # 16 * unit
    
    # 组件内边距
    padding_xs: int = 4
    padding_sm: int = 8
    padding_md: int = 12
    padding_lg: int = 16
    padding_xl: int = 20
    
    # 组件外边距
    margin_xs: int = 4
    margin_sm: int = 8
    margin_md: int = 16
    margin_lg: int = 24
    margin_xl: int = 32

@dataclass
class BorderRadius:
    """圆角系统数据类"""
    none: int = 0
    xs: int = 2
    sm: int = 4
    md: int = 6
    lg: int = 8
    xl: int = 12
    xxl: int = 16
    full: str = "50%"

@dataclass
class Shadows:
    """阴影系统数据类"""
    none: str = "none"
    xs: str = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
    sm: str = "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)"
    md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
    lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)"
    xl: str = "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)"
    xxl: str = "0 25px 50px -12px rgba(0, 0, 0, 0.25)"
    inner: str = "inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)"

@dataclass
class ComponentStyles:
    """组件样式数据类"""
    # 按钮样式
    button_height_sm: int = 28
    button_height_md: int = 36
    button_height_lg: int = 44
    button_padding_x: int = 16
    button_border_radius: int = 6
    
    # 输入框样式
    input_height_sm: int = 32
    input_height_md: int = 40
    input_height_lg: int = 48
    input_padding_x: int = 12
    input_border_width: int = 1
    input_border_radius: int = 4
    
    # 卡片样式
    card_padding: int = 16
    card_border_radius: int = 8
    card_border_width: int = 1
    
    # 表格样式
    table_row_height: int = 48
    table_header_height: int = 56
    table_cell_padding_x: int = 16
    table_cell_padding_y: int = 12
    
    # 标签页样式
    tab_height: int = 48
    tab_padding_x: int = 16
    tab_border_radius: int = 4
    
    # 对话框样式
    dialog_border_radius: int = 8
    dialog_padding: int = 24
    dialog_max_width: int = 600
    
    # 工具提示样式
    tooltip_padding_x: int = 8
    tooltip_padding_y: int = 4
    tooltip_border_radius: int = 4
    tooltip_max_width: int = 300

class DesignTokens:
    """设计令牌管理器"""
    
    def __init__(self, color_scheme: ColorScheme = ColorScheme.LIGHT):
        self.color_scheme = color_scheme
        self.colors = self._get_color_palette()
        self.typography = Typography()
        self.spacing = Spacing()
        self.border_radius = BorderRadius()
        self.shadows = Shadows()
        self.components = ComponentStyles()
        
        # 组件尺寸映射
        self.size_mappings = {
            ComponentSize.EXTRA_SMALL: {
                'height': 24,
                'padding': self.spacing.xs,
                'font_size': self.typography.font_size_xs
            },
            ComponentSize.SMALL: {
                'height': 32,
                'padding': self.spacing.sm,
                'font_size': self.typography.font_size_sm
            },
            ComponentSize.MEDIUM: {
                'height': 40,
                'padding': self.spacing.md,
                'font_size': self.typography.font_size_md
            },
            ComponentSize.LARGE: {
                'height': 48,
                'padding': self.spacing.lg,
                'font_size': self.typography.font_size_lg
            },
            ComponentSize.EXTRA_LARGE: {
                'height': 56,
                'padding': self.spacing.xl,
                'font_size': self.typography.font_size_xl
            }
        }
    
    def _get_color_palette(self) -> ColorPalette:
        """获取颜色调色板"""
        if self.color_scheme == ColorScheme.DARK:
            return DarkColorPalette()
        else:
            return ColorPalette()
    
    def set_color_scheme(self, scheme: ColorScheme):
        """设置颜色方案"""
        self.color_scheme = scheme
        self.colors = self._get_color_palette()
    
    def get_component_size_config(self, size: ComponentSize) -> Dict[str, Any]:
        """获取组件尺寸配置"""
        return self.size_mappings.get(size, self.size_mappings[ComponentSize.MEDIUM])
    
    def get_semantic_color(self, semantic_type: str, variant: str = "500") -> str:
        """获取语义化颜色"""
        color_map = {
            'primary': getattr(self.colors, f'primary_{variant}', self.colors.primary_500),
            'secondary': getattr(self.colors, f'secondary_{variant}', self.colors.secondary_500),
            'success': getattr(self.colors, f'success_{variant}', self.colors.success_500),
            'warning': getattr(self.colors, f'warning_{variant}', self.colors.warning_500),
            'error': getattr(self.colors, f'error_{variant}', self.colors.error_500),
            'info': getattr(self.colors, f'info_{variant}', self.colors.info_500),
        }
        return color_map.get(semantic_type, self.colors.primary_500)
    
    def get_text_color(self, level: str = "primary") -> str:
        """获取文本颜色"""
        text_colors = {
            'primary': self.colors.text_primary,
            'secondary': self.colors.text_secondary,
            'disabled': self.colors.text_disabled,
            'hint': self.colors.text_hint
        }
        return text_colors.get(level, self.colors.text_primary)
    
    def get_background_color(self, level: str = "default") -> str:
        """获取背景颜色"""
        bg_colors = {
            'default': self.colors.background_default,
            'paper': self.colors.background_paper,
            'level1': self.colors.background_level1,
            'level2': self.colors.background_level2
        }
        return bg_colors.get(level, self.colors.background_default)
    
    def get_border_color(self, level: str = "light") -> str:
        """获取边框颜色"""
        border_colors = {
            'light': self.colors.border_light,
            'medium': self.colors.border_medium,
            'dark': self.colors.border_dark
        }
        return border_colors.get(level, self.colors.border_light)

class StyleSheetGenerator:
    """样式表生成器"""
    
    def __init__(self, design_tokens: DesignTokens):
        self.tokens = design_tokens
    
    def generate_button_style(self, variant: str = "primary", size: ComponentSize = ComponentSize.MEDIUM) -> str:
        """生成按钮样式"""
        size_config = self.tokens.get_component_size_config(size)
        
        if variant == "primary":
            bg_color = self.tokens.get_semantic_color('primary')
            text_color = "#FFFFFF"
            hover_color = self.tokens.get_semantic_color('primary', '600')
        elif variant == "secondary":
            bg_color = self.tokens.get_semantic_color('secondary')
            text_color = "#FFFFFF"
            hover_color = self.tokens.get_semantic_color('secondary', '600')
        elif variant == "outline":
            bg_color = "transparent"
            text_color = self.tokens.get_semantic_color('primary')
            hover_color = self.tokens.get_semantic_color('primary', '50')
        else:  # text variant
            bg_color = "transparent"
            text_color = self.tokens.get_semantic_color('primary')
            hover_color = self.tokens.get_semantic_color('primary', '50')
        
        return f"""
        QPushButton {{
            background-color: {bg_color};
            color: {text_color};
            border: {'1px solid ' + self.tokens.get_semantic_color('primary') if variant == 'outline' else 'none'};
            border-radius: {self.tokens.border_radius.md}px;
            padding: {self.tokens.spacing.sm}px {size_config['padding']}px;
            font-family: {self.tokens.typography.font_family_primary};
            font-size: {size_config['font_size']}px;
            font-weight: {self.tokens.typography.font_weight_medium};
            min-height: {size_config['height']}px;
        }}
        
        QPushButton:hover {{
            background-color: {hover_color};
        }}
        
        QPushButton:pressed {{
            background-color: {self.tokens.get_semantic_color('primary', '700') if variant == 'primary' else hover_color};
        }}
        
        QPushButton:disabled {{
            background-color: {self.tokens.colors.grey_300};
            color: {self.tokens.get_text_color('disabled')};
            border-color: {self.tokens.colors.grey_300};
        }}
        """
    
    def generate_input_style(self, size: ComponentSize = ComponentSize.MEDIUM) -> str:
        """生成输入框样式"""
        size_config = self.tokens.get_component_size_config(size)
        
        return f"""
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {self.tokens.get_background_color('paper')};
            color: {self.tokens.get_text_color('primary')};
            border: 1px solid {self.tokens.get_border_color('light')};
            border-radius: {self.tokens.border_radius.sm}px;
            padding: {self.tokens.spacing.sm}px {self.tokens.spacing.md}px;
            font-family: {self.tokens.typography.font_family_primary};
            font-size: {size_config['font_size']}px;
            min-height: {size_config['height']}px;
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {self.tokens.get_semantic_color('primary')};
            outline: none;
        }}
        
        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
            background-color: {self.tokens.colors.grey_100};
            color: {self.tokens.get_text_color('disabled')};
            border-color: {self.tokens.get_border_color('light')};
        }}
        """
    
    def generate_card_style(self) -> str:
        """生成卡片样式"""
        return f"""
        .card {{
            background-color: {self.tokens.get_background_color('paper')};
            border: 1px solid {self.tokens.get_border_color('light')};
            border-radius: {self.tokens.border_radius.lg}px;
            padding: {self.tokens.components.card_padding}px;
            box-shadow: {self.tokens.shadows.sm};
        }}
        """
    
    def generate_table_style(self) -> str:
        """生成表格样式"""
        return f"""
        QTableWidget {{
            background-color: {self.tokens.get_background_color('paper')};
            alternate-background-color: {self.tokens.get_background_color('level1')};
            gridline-color: {self.tokens.get_border_color('light')};
            border: 1px solid {self.tokens.get_border_color('light')};
            border-radius: {self.tokens.border_radius.md}px;
            font-family: {self.tokens.typography.font_family_primary};
            font-size: {self.tokens.typography.font_size_md}px;
        }}
        
        QTableWidget::item {{
            padding: {self.tokens.components.table_cell_padding_y}px {self.tokens.components.table_cell_padding_x}px;
            border: none;
        }}
        
        QTableWidget::item:selected {{
            background-color: {self.tokens.get_semantic_color('primary', '100')};
            color: {self.tokens.get_semantic_color('primary', '800')};
        }}
        
        QHeaderView::section {{
            background-color: {self.tokens.get_background_color('level1')};
            color: {self.tokens.get_text_color('primary')};
            padding: {self.tokens.components.table_cell_padding_y}px {self.tokens.components.table_cell_padding_x}px;
            border: none;
            border-bottom: 2px solid {self.tokens.get_border_color('medium')};
            font-weight: {self.tokens.typography.font_weight_semibold};
        }}
        """
    
    def generate_tab_style(self) -> str:
        """生成标签页样式"""
        return f"""
        QTabWidget::pane {{
            border: 1px solid {self.tokens.get_border_color('light')};
            border-radius: {self.tokens.border_radius.md}px;
            background-color: {self.tokens.get_background_color('paper')};
            padding: {self.tokens.spacing.md}px;
        }}
        
        QTabBar::tab {{
            background-color: {self.tokens.get_background_color('level1')};
            color: {self.tokens.get_text_color('secondary')};
            border: 1px solid {self.tokens.get_border_color('light')};
            border-bottom: none;
            border-radius: {self.tokens.border_radius.sm}px {self.tokens.border_radius.sm}px 0 0;
            padding: {self.tokens.spacing.sm}px {self.tokens.spacing.lg}px;
            margin-right: 2px;
            font-family: {self.tokens.typography.font_family_primary};
            font-size: {self.tokens.typography.font_size_md}px;
            font-weight: {self.tokens.typography.font_weight_medium};
            min-height: {self.tokens.components.tab_height - 16}px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {self.tokens.get_background_color('paper')};
            color: {self.tokens.get_text_color('primary')};
            border-bottom: 2px solid {self.tokens.get_semantic_color('primary')};
        }}
        
        QTabBar::tab:hover {{
            background-color: {self.tokens.get_semantic_color('primary', '50')};
            color: {self.tokens.get_semantic_color('primary')};
        }}
        """
    
    def generate_complete_stylesheet(self) -> str:
        """生成完整样式表"""
        return f"""
        /* 全局样式 */
        * {{
            font-family: {self.tokens.typography.font_family_primary};
        }}
        
        QWidget {{
            background-color: {self.tokens.get_background_color('default')};
            color: {self.tokens.get_text_color('primary')};
            font-size: {self.tokens.typography.font_size_md}px;
        }}
        
        /* 按钮样式 */
        {self.generate_button_style('primary')}
        
        /* 输入框样式 */
        {self.generate_input_style()}
        
        /* 表格样式 */
        {self.generate_table_style()}
        
        /* 标签页样式 */
        {self.generate_tab_style()}
        
        /* 进度条样式 */
        QProgressBar {{
            background-color: {self.tokens.get_background_color('level1')};
            border: 1px solid {self.tokens.get_border_color('light')};
            border-radius: {self.tokens.border_radius.sm}px;
            text-align: center;
            font-size: {self.tokens.typography.font_size_sm}px;
            font-weight: {self.tokens.typography.font_weight_medium};
        }}
        
        QProgressBar::chunk {{
            background-color: {self.tokens.get_semantic_color('primary')};
            border-radius: {self.tokens.border_radius.sm}px;
        }}
        
        /* 分组框样式 */
        QGroupBox {{
            font-weight: {self.tokens.typography.font_weight_semibold};
            border: 1px solid {self.tokens.get_border_color('medium')};
            border-radius: {self.tokens.border_radius.md}px;
            margin-top: {self.tokens.spacing.md}px;
            padding-top: {self.tokens.spacing.md}px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {self.tokens.spacing.lg}px;
            padding: 0 {self.tokens.spacing.sm}px;
            color: {self.tokens.get_text_color('primary')};
        }}
        
        /* 滚动条样式 */
        QScrollBar:vertical {{
            background-color: {self.tokens.get_background_color('level1')};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {self.tokens.get_border_color('medium')};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {self.tokens.get_border_color('dark')};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        
        /* 工具提示样式 */
        QToolTip {{
            background-color: {self.tokens.colors.grey_800};
            color: white;
            border: none;
            border-radius: {self.tokens.border_radius.sm}px;
            padding: {self.tokens.spacing.xs}px {self.tokens.spacing.sm}px;
            font-size: {self.tokens.typography.font_size_sm}px;
        }}
        
        /* 菜单样式 */
        QMenu {{
            background-color: {self.tokens.get_background_color('paper')};
            border: 1px solid {self.tokens.get_border_color('light')};
            border-radius: {self.tokens.border_radius.md}px;
            padding: {self.tokens.spacing.xs}px;
        }}
        
        QMenu::item {{
            padding: {self.tokens.spacing.sm}px {self.tokens.spacing.md}px;
            border-radius: {self.tokens.border_radius.sm}px;
        }}
        
        QMenu::item:selected {{
            background-color: {self.tokens.get_semantic_color('primary', '100')};
            color: {self.tokens.get_semantic_color('primary')};
        }}
        
        /* 状态栏样式 */
        QStatusBar {{
            background-color: {self.tokens.get_background_color('level1')};
            border-top: 1px solid {self.tokens.get_border_color('light')};
            padding: {self.tokens.spacing.xs}px {self.tokens.spacing.md}px;
        }}
        """

class UnifiedDesignSystem:
    """统一设计系统主类"""
    
    def __init__(self, color_scheme: ColorScheme = ColorScheme.LIGHT):
        self.design_tokens = DesignTokens(color_scheme)
        self.stylesheet_generator = StyleSheetGenerator(self.design_tokens)
        self.current_stylesheet = ""
        self._generate_stylesheet()
        
        logger.info(f"统一设计系统已初始化，颜色方案: {color_scheme.value}")
    
    def _generate_stylesheet(self):
        """生成样式表"""
        self.current_stylesheet = self.stylesheet_generator.generate_complete_stylesheet()
    
    def set_color_scheme(self, scheme: ColorScheme):
        """设置颜色方案"""
        self.design_tokens.set_color_scheme(scheme)
        self._generate_stylesheet()
        logger.info(f"颜色方案已更新: {scheme.value}")
    
    def get_stylesheet(self) -> str:
        """获取完整样式表"""
        return self.current_stylesheet
    
    def get_component_stylesheet(self, component_type: str, **kwargs) -> str:
        """获取特定组件样式表"""
        if component_type == "button":
            variant = kwargs.get('variant', 'primary')
            size = kwargs.get('size', ComponentSize.MEDIUM)
            return self.stylesheet_generator.generate_button_style(variant, size)
        elif component_type == "input":
            size = kwargs.get('size', ComponentSize.MEDIUM)
            return self.stylesheet_generator.generate_input_style(size)
        elif component_type == "table":
            return self.stylesheet_generator.generate_table_style()
        elif component_type == "tab":
            return self.stylesheet_generator.generate_tab_style()
        elif component_type == "card":
            return self.stylesheet_generator.generate_card_style()
        else:
            logger.warning(f"未知组件类型: {component_type}")
            return ""
    
    def apply_to_application(self, app: QApplication):
        """应用样式到整个应用程序"""
        try:
            app.setStyleSheet(self.current_stylesheet)
            logger.info("设计系统样式已应用到应用程序")
        except Exception as e:
            logger.error(f"应用样式失败: {e}")
    
    def get_design_tokens(self) -> DesignTokens:
        """获取设计令牌"""
        return self.design_tokens
    
    def export_tokens(self, file_path: str):
        """导出设计令牌到JSON文件"""
        try:
            tokens_dict = {
                'colors': self.design_tokens.colors.__dict__,
                'typography': self.design_tokens.typography.__dict__,
                'spacing': self.design_tokens.spacing.__dict__,
                'border_radius': self.design_tokens.border_radius.__dict__,
                'shadows': self.design_tokens.shadows.__dict__,
                'components': self.design_tokens.components.__dict__,
                'color_scheme': self.design_tokens.color_scheme.value
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(tokens_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"设计令牌已导出到: {file_path}")
            
        except Exception as e:
            logger.error(f"导出设计令牌失败: {e}")
    
    def import_tokens(self, file_path: str):
        """从JSON文件导入设计令牌"""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"设计令牌文件不存在: {file_path}")
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                tokens_dict = json.load(f)
            
            # 更新设计令牌
            if 'colors' in tokens_dict:
                for key, value in tokens_dict['colors'].items():
                    if hasattr(self.design_tokens.colors, key):
                        setattr(self.design_tokens.colors, key, value)
            
            if 'typography' in tokens_dict:
                for key, value in tokens_dict['typography'].items():
                    if hasattr(self.design_tokens.typography, key):
                        setattr(self.design_tokens.typography, key, value)
            
            # 重新生成样式表
            self._generate_stylesheet()
            
            logger.info(f"设计令牌已从文件导入: {file_path}")
            
        except Exception as e:
            logger.error(f"导入设计令牌失败: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取设计系统状态"""
        return {
            'color_scheme': self.design_tokens.color_scheme.value,
            'stylesheet_length': len(self.current_stylesheet),
            'available_components': ['button', 'input', 'table', 'tab', 'card'],
            'available_sizes': [size.value for size in ComponentSize],
            'available_color_schemes': [scheme.value for scheme in ColorScheme],
            'timestamp': logger.info.__name__  # 简化实现
        }

# 全局实例
unified_design_system = UnifiedDesignSystem()

def get_unified_design_system() -> UnifiedDesignSystem:
    """获取统一设计系统实例"""
    return unified_design_system

def apply_design_system(app: QApplication, color_scheme: ColorScheme = ColorScheme.LIGHT):
    """应用设计系统到应用程序"""
    design_system = get_unified_design_system()
    design_system.set_color_scheme(color_scheme)
    design_system.apply_to_application(app)
