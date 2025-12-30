from pathlib import Path
from loguru import logger
"""
Theme Management Module

This module provides a unified theme management solution with support for
multiple themes, dynamic theme switching, and theme customization.
"""

from enum import Enum
import json
import os
import re
import glob
from typing import Dict, Any, Optional, Union
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from .config_manager import ConfigManager
from .theme_types import Theme
from .config_types import ThemeConfig
from core.base_logger import BaseLogManager
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from utils.theme_utils import load_theme_json_with_comments
import sqlite3
from datetime import datetime
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from core.events.event_bus import get_event_bus
from core.events.events import ThemeChangedEvent

# Global theme manager instance
_theme_manager_instance: Optional['ThemeManager'] = None


def parse_color(color_str: str) -> Union[str, tuple]:
    """解析颜色字符串，支持rgba()格式
    
    Args:
        color_str: 颜色字符串，支持 #hex, rgb(), rgba()
        
    Returns:
        Union[str, tuple]: 如果是rgba格式返回(r,g,b,a)元组，否则返回原字符串
    """
    if not color_str or not isinstance(color_str, str):
        return color_str
        
    # 处理rgba()格式
    if color_str.startswith('rgba(') and color_str.endswith(')'):
        try:
            # 提取rgba参数
            rgba_content = color_str[5:-1]  # 去掉 "rgba(" 和 ")"
            parts = [part.strip() for part in rgba_content.split(',')]
            
            if len(parts) >= 4:
                r = int(parts[0].strip())
                g = int(parts[1].strip()) 
                b = int(parts[2].strip())
                a = float(parts[3].strip())
                
                # 返回Qt可识别的格式
                return (r, g, b, a)
        except (ValueError, IndexError) as e:
            logger.warning(f"解析rgba颜色失败: {color_str}, 错误: {e}")
            
    return color_str

DB_PATH = os.path.join(os.path.dirname(
    os.path.dirname(__file__)), 'data', 'factorweave_system.sqlite')


def safe_read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='gbk') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin1') as f:
                return f.read()


def load_theme_json_with_comments(path: str) -> dict:
    """读取带注释的JSON文件，自动去除注释"""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 去除 // 注释
    content = re.sub(r'//.*', '', content)
    # 去除 /* ... */ 注释（如有）
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # 去除多余空行
    content = '\n'.join(
        [line for line in content.splitlines() if line.strip()])
    return json.loads(content)


class ThemeType(Enum):
    JSON = 'json'
    QSS = 'qss'


class ThemeManager(QObject):
    """主题管理器类，统一从config/theme.json读取所有配色"""

    # 主题变更信号
    theme_changed = pyqtSignal(Theme)

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """初始化主题管理器

        Args:
            config_manager: 配置管理器实例
        """
        super().__init__()

        # 初始化配置管理器
        self.config_manager = config_manager or ConfigManager()

        # 初始化主题缓存
        self._theme_cache = {}

        # 加载主题配置
        self._theme_json_path = os.path.join(os.path.dirname(
            os.path.dirname(__file__)), 'config', 'theme.json')
        self._theme_data = {}
        self._current_theme = Theme.LIGHT  # 默认主题
        self._init_db()
        self._load_theme_json()
        self.qss_theme_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'QSSTheme')
        self._import_themes_to_db()
        self._current_theme_type = ThemeType.JSON
        self._current_qss_file = None

        # 从配置中恢复上次保存的主题
        self._restore_last_theme()
        
        # 初始化EventBus（支持容器+Event模式）
        self._event_bus = get_event_bus()
        
        # 初始化组件跟踪列表（用于QSS主题的样式表清理）
        self._tracked_widgets = set()

    def _init_db(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute('''CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            type TEXT,
            content TEXT,
            base_type TEXT DEFAULT 'light',
            origin TEXT,
            created_at TEXT,
            updated_at TEXT
        )''')
        self.conn.commit()

    def _restore_last_theme(self):
        """从配置服务恢复上次保存的主题

        从 config 表的 theme 键读取 theme_name 字段
        """
        try:
            # 从 config_manager 获取 theme 配置
            theme_config = self.config_manager.get('theme', {})
            saved_theme_name = theme_config.get('theme_name')

            if saved_theme_name and saved_theme_name != 'default':
                logger.info(f"从配置恢复主题: {saved_theme_name}")

                # 检查主题是否存在
                row = self._get_theme_content(saved_theme_name)
                if row:
                    type_, content, base_type = row

                    # 根据数据库中的 base_type 设置主题枚举
                    if base_type == 'dark':
                        self._current_theme = Theme.DARK
                    elif base_type == 'gradient':
                        self._current_theme = Theme.GRADIENT
                    else:  # 默认 'light'
                        self._current_theme = Theme.LIGHT

                    # 设置主题状态（不触发完整刷新，避免初始化时的问题）
                    if type_ == 'qss':
                        self._current_theme_type = ThemeType.QSS
                        # 只有在QApplication可用时才应用QSS
                        app = QApplication.instance()
                        if app:
                            self.apply_qss_theme_content(content)
                    else:  # JSON主题
                        self._current_theme_type = ThemeType.JSON
                        theme_dict = json.loads(content)
                        self._theme_cache[saved_theme_name.lower()] = theme_dict

                    logger.info(f"✅ 成功恢复主题: {saved_theme_name} ({type_}, base_type={base_type})")
                else:
                    logger.warning(f"保存的主题 '{saved_theme_name}' 不存在，使用默认主题")
            else:
                logger.debug("未找到保存的主题配置或使用默认主题")

        except Exception as e:
            logger.warning(f"恢复主题失败: {e}，使用默认主题")
            # 失败时使用默认主题，不抛出异常

    def _import_themes_to_db(self):
        # 导入QSS主题
        for qss_file in glob.glob(os.path.join(self.qss_theme_dir, '*.qss')):
            name = os.path.splitext(os.path.basename(qss_file))[0]
            content = safe_read_file(qss_file)
            # 跳过已存在的主题
            cur = self.conn.cursor()
            cur.execute('SELECT id FROM themes WHERE name=?', (name,))
            if cur.fetchone():
                continue
            self._upsert_theme(name, 'qss', content, 'file')
        # 导入JSON主题
        for t in self._theme_data.keys():
            name = t.capitalize()
            content = json.dumps(self._theme_data[t], ensure_ascii=False)
            cur = self.conn.cursor()
            cur.execute('SELECT id FROM themes WHERE name=?', (name,))
            if cur.fetchone():
                continue
            self._upsert_theme(name, 'json', content, 'file')

    def _detect_base_type(self, theme_name: str, theme_type: str, content: str) -> str:
        """智能检测主题的基础类型

        Args:
            theme_name: 主题名称
            theme_type: 主题类型 (qss/json)
            content: 主题内容

        Returns:
            'dark', 'light', 或 'gradient'
        """
        # 优先级1: 通过名称关键词判断
        theme_name_lower = theme_name.lower()

        if '深' in theme_name or '黑' in theme_name or 'dark' in theme_name_lower or 'amoled' in theme_name_lower:
            return 'dark'
        elif '浅' in theme_name or '白' in theme_name or 'light' in theme_name_lower:
            return 'light'
        elif '渐变' in theme_name or 'gradient' in theme_name_lower or '炫彩' in theme_name:
            return 'gradient'

        # 优先级2: 对于JSON主题，检查数据内容
        if theme_type == 'json':
            try:
                theme_dict = json.loads(content)
                if isinstance(theme_dict, dict):
                    theme_base = theme_dict.get('theme', 'light')
                    if theme_base == 'dark':
                        return 'dark'
                    elif theme_base == 'gradient':
                        return 'gradient'
                    else:
                        return 'light'
            except:
                pass

        # 默认: light
        return 'light'

    def _upsert_theme(self, name, type_, content, origin, base_type='light'):
        """插入或更新主题

        Args:
            name: 主题名称
            type_: 主题类型 (qss/json)
            content: 主题内容
            origin: 来源 (built-in/user/imported)
            base_type: 基础类型 (dark/light/gradient)，默认light
        """
        now = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute('SELECT id FROM themes WHERE name=?', (name,))
        if cur.fetchone():
            cur.execute('UPDATE themes SET type=?, content=?, base_type=?, origin=?, updated_at=? WHERE name=?',
                        (type_, content, base_type, origin, now, name))
        else:
            cur.execute('INSERT INTO themes (name, type, content, base_type, origin, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (name, type_, content, base_type, origin, now, now))
        self.conn.commit()

    def _get_all_themes_from_db(self):
        cur = self.conn.cursor()
        cur.execute('SELECT name, type, content, origin, created_at, updated_at FROM themes ORDER BY id')
        return cur.fetchall()

    def _get_theme_content(self, name):
        """获取主题内容

        Returns:
            tuple: (type, content, base_type) 或 None
        """
        cur = self.conn.cursor()
        cur.execute('SELECT type, content, base_type FROM themes WHERE name=?', (name,))
        return cur.fetchone()

    def get_theme_config(self, theme_name: str) -> Optional[dict]:
        """获取主题配置（兼容性方法）

        Args:
            theme_name: 主题名称

        Returns:
            主题配置字典，如果主题不存在则返回None
        """
        try:
            row = self._get_theme_content(theme_name)
            if not row:
                # 检查是否是内置主题
                if theme_name in self._theme_data:
                    return self._theme_data[theme_name]
                return None

            theme_type, content, base_type = row

            # 如果是JSON类型，解析内容
            if theme_type == 'json':
                if isinstance(content, str):
                    return json.loads(content)
                return content
            # 如果是QSS类型，返回基本信息
            elif theme_type == 'qss':
                return {
                    'type': 'qss',
                    'content': content,
                    'base_type': base_type,
                    'description': f'QSS主题: {theme_name}'
                }
            else:
                return {
                    'type': theme_type,
                    'content': content,
                    'base_type': base_type
                }
        except Exception as e:
            logger.error(f"获取主题配置失败: {e}")
            return None

    def _load_theme_json(self):
        """加载主题配置文件"""
        try:
            self._theme_data = load_theme_json_with_comments(
                self._theme_json_path)
        except Exception as e:
            logger.info(f"加载theme.json失败: {str(e)}")
            self._theme_data = {}

    @property
    def current_theme(self) -> Theme:
        """获取当前主题"""
        return self._current_theme

    def set_theme(self, theme_name: str):
        row = self._get_theme_content(theme_name)
        if not row:
            return
        type_, content, base_type = row

        # 根据数据库中的 base_type 设置主题枚举
        if base_type == 'dark':
            self._current_theme = Theme.DARK
        elif base_type == 'gradient':
            self._current_theme = Theme.GRADIENT
        else:  # 默认 'light'
            self._current_theme = Theme.LIGHT

        # 保存主题名称到 config 表的 theme.theme_name 配置
        try:
            theme_config = self.config_manager.get('theme', {})
            theme_config['theme_name'] = theme_name
            self.config_manager.set('theme', theme_config)
            logger.debug(f"已保存主题配置: theme.theme_name = {theme_name}")
        except Exception as e:
            logger.warning(f"保存主题配置失败: {e}")

        # 清除所有旧样式（样式优先级：QSS主题 > JSON主题 > 全局样式）
        self.clear_qss_theme()
        self._clear_widget_stylesheets()

        if type_ == 'qss':
            self._current_theme_type = ThemeType.QSS
            # 清除主题缓存（QSS主题不需要缓存）
            self._theme_cache.clear()
            
            # 立即发送主题变化信号，让监听的组件快速响应
            self.theme_changed.emit(self._current_theme)
            
            # 发布主题变化事件（EventBus模式）
            event = ThemeChangedEvent(
                theme_name=theme_name,
                theme_config=self.get_theme_colors()
            )
            self._event_bus.publish(event)
            
            # 使用异步方式应用QSS主题，避免阻塞UI
            QTimer.singleShot(0, lambda: self._apply_qss_theme_async(theme_name, content, base_type))
            
            logger.info(f"QSS主题切换: {theme_name} (base_type={base_type}, 异步应用...)")
        else:
            self._current_theme_type = ThemeType.JSON
            theme_dict = json.loads(content)
            
            # 更新主题缓存（在发送信号之前）
            self._theme_cache[theme_name.lower()] = theme_dict
            
            # 清除QSS样式
            self.clear_qss_theme()

            # 立即发送主题变化信号，让监听的组件快速响应
            self.theme_changed.emit(self._current_theme)
            
            # 发布主题变化事件（EventBus模式）
            event = ThemeChangedEvent(
                theme_name=theme_name,
                theme_config=self.get_theme_colors()
            )
            self._event_bus.publish(event)

            # 异步刷新所有窗口组件（避免阻塞UI）
            # 使用QTimer.singleShot确保在事件循环中执行
            QTimer.singleShot(50, self._refresh_all_widgets)

            logger.info(f"JSON主题切换: {theme_name} (base_type={base_type}, 异步刷新...)")

    def get_theme_colors(self, theme: Optional[Theme] = None) -> Dict[str, Any]:
        """获取主题颜色

        Args:
            theme: 可选的主题，默认使用当前主题

        Returns:
            主题颜色字典
        """
        theme = theme or self._current_theme
        theme_key = theme.name.lower() if hasattr(
            theme, 'name') else str(theme).lower()
        if theme_key in self._theme_cache:
            return self._theme_cache[theme_key].copy()
        colors = self._theme_data.get(theme_key, {})
        self._theme_cache[theme_key] = colors.copy()
        return colors

    def get_color(self, name: str, theme: Optional[Theme] = None, default: str = None) -> Any:
        """Get color by name

        Args:
            name: Color name
            theme: Theme to get color from, defaults to current theme
            default: Default color if not found

        Returns:
            Color value
        """
        colors = self.get_theme_colors(theme)
        return colors.get(name, default)

    def apply_chart_theme(self, figure, theme: Optional[Theme] = None) -> None:
        """Apply theme to matplotlib figure

        Args:
            figure: Matplotlib figure to apply theme to
            theme: Theme to apply, defaults to current theme
        """
        if theme is None:
            theme = self.current_theme

        try:
            colors = self.get_theme_colors(theme)
            
            # 处理颜色格式，确保rgba格式被正确解析
            processed_colors = {}
            for key, value in colors.items():
                if isinstance(value, str) and value.startswith('rgba('):
                    processed_colors[key] = parse_color(value)
                else:
                    processed_colors[key] = value

            # Set figure facecolor (处理rgba格式)
            chart_bg = processed_colors.get('chart_background', '#ffffff')
            if isinstance(chart_bg, tuple) and len(chart_bg) >= 4:
                figure.set_facecolor(chart_bg[:3])  # 使用RGB部分，忽略alpha
            else:
                figure.set_facecolor(chart_bg)

            # Set axes colors
            for ax in figure.get_axes():
                # 设置背景色
                chart_bg = processed_colors.get('chart_background', '#ffffff')
                if isinstance(chart_bg, tuple) and len(chart_bg) >= 4:
                    ax.set_facecolor(chart_bg[:3])
                else:
                    ax.set_facecolor(chart_bg)
                    
                # 设置文字颜色
                text_color = processed_colors.get('chart_text', '#222b45')
                ax.tick_params(colors=text_color)
                ax.title.set_color(text_color)
                ax.xaxis.label.set_color(text_color)
                ax.yaxis.label.set_color(text_color)
                
                # 设置边框颜色
                grid_color = processed_colors.get('chart_grid', '#e0e0e0')
                ax.spines['bottom'].set_color(grid_color)
                ax.spines['top'].set_color(grid_color)
                ax.spines['right'].set_color(grid_color)
                ax.spines['left'].set_color(grid_color)

                # Set grid color
                ax.grid(True, color=grid_color, alpha=0.3)

                # Set tick colors
                for tick in ax.get_xticklabels():
                    tick.set_color(text_color)
                for tick in ax.get_yticklabels():
                    tick.set_color(text_color)

            # Draw figure
            figure.canvas.draw()

        except Exception as e:
            logger.error(f"应用图表主题失败: {str(e)}")
            logger.error(f"错误类型: {type(e).__name__}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")

    def is_dark_theme(self) -> bool:
        """Check if current theme is dark

        Returns:
            True if current theme is dark
        """
        return self.current_theme.is_dark

    def apply_theme(self, widget):
        """应用主题到指定控件

        Args:
            widget: 要应用主题的控件
        """
        # 检查当前主题类型，如果是QSS主题则跳过，因为QSS主题已经全局应用
        if self.is_qss_theme():
            logger.debug(f"当前为QSS主题，跳过apply_theme调用")
            return
        
        colors = self.get_theme_colors()
        # 处理颜色格式，确保rgba格式被正确解析
        processed_colors = {}
        for key, value in colors.items():
            if isinstance(value, str) and value.startswith('rgba('):
                processed_colors[key] = parse_color(value)
            else:
                processed_colors[key] = value
        
        stylesheet = self._build_stylesheet(processed_colors)
        
        # 修复CSS属性中可能存在的't'前缀问题，比如'tmin-height'应该改为'min-height'
        # 这是一个防御性修复，防止生成错误的CSS属性
        stylesheet = re.sub(r'\bt(min-height|min-width|max-height|max-width|padding|margin|border-radius|border-width|border-style|border-color|font-size|font-family|font-weight|font-style|text-align|text-color|background-color|color|width|height|left|top|right|bottom|opacity|z-index)\b', r'\1', stylesheet)
        
        # 添加主题应用状态跟踪，避免重复应用
        if not hasattr(self, '_applied_widgets'):
            self._applied_widgets = set()
        
        widget_id = id(widget)
        if widget_id not in self._applied_widgets:
            # 应用样式表到目标控件
            widget.setStyleSheet(stylesheet)
            
            # 优化：只应用到直接子控件，利用Qt的样式表继承机制
            # 避免过度递归和性能问题
            for child in widget.children():
                if isinstance(child, QWidget) and child != widget:
                    child.setStyleSheet(stylesheet)
            self._applied_widgets.add(widget_id)

    def _build_stylesheet(self, colors: Dict[str, Any]) -> str:
        """构建样式表

        Args:
            colors: 主题颜色字典

        Returns:
            QSS样式表字符串
        """
        return f"""
        QWidget {{
            background-color: {colors.get('background', '#FFFFFF')};
            color: {colors.get('text', '#222b45')};
            font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
            font-size: 9pt;
        }}

        QPushButton {{
            background-color: {colors.get('button_bg', '#e3f2fd')};
            color: {colors.get('button_text', '#1565c0')};
            border: 1px solid {colors.get('button_border', '#90caf9')};
            border-radius: 4px;
            padding: 6px 12px;
            min-height: 20px;
        }}

        QPushButton:hover {{
            background-color: {colors.get('button_hover', '#90caf9')};
        }}

        QPushButton:pressed {{
            background-color: {colors.get('button_pressed', '#64b5f6')};
        }}

        QGroupBox {{
            border: 2px solid {colors.get('border', '#e0e0e0')};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 12px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {colors.get('highlight', '#1976d2')};
        }}

        QTableWidget {{
            background-color: {colors.get('card', '#FFFFFF')};
            border: 1px solid {colors.get('border', '#e0e0e0')};
            gridline-color: {colors.get('chart_grid', '#e0e0e0')};
        }}

        QTableWidget::item {{
            padding: 4px;
        }}

        QTableWidget::item[data-status="running"] {{
            background-color: {colors.get('success', '#4CAF50')};
            color: #FFFFFF;
        }}

        QTableWidget::item[data-status="error"] {{
            background-color: {colors.get('error', '#FF5252')};
            color: #FFFFFF;
        }}

        QTableWidget::item[data-status="configured"] {{
            background-color: {colors.get('info', '#2196F3')};
            color: #FFFFFF;
        }}

        QTableWidget::item[data-status="stopped"] {{
            background-color: {colors.get('background', '#FFFFFF')};
            color: {colors.get('text', '#222b45')};
        }}

        QLineEdit, QTextEdit, QComboBox {{
            background-color: {colors.get('card', '#FFFFFF')};
            border: 1px solid {colors.get('border', '#e0e0e0')};
            border-radius: 4px;
            padding: 6px;
            min-height: 28px;
        }}

        QTabWidget::pane {{
            border: 1px solid {colors.get('border', '#e0e0e0')};
            background-color: {colors.get('card', '#FFFFFF')};
        }}

        QTabBar::tab {{
            background-color: {colors.get('sidebar_bg', '#f3f6fa')};
            color: {colors.get('text', '#222b45')};
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}

        QTabBar::tab:selected {{
            background-color: {colors.get('highlight', '#1976d2')};
            color: #FFFFFF;
        }}

        QProgressBar {{
            background-color: {colors.get('hover', '#F5F5F5')};
            border: none;
            border-radius: 4px;
            text-align: center;
        }}

        QProgressBar::chunk {{
            background-color: {colors.get('progress_chunk', '#4CAF50')};
            border-radius: 4px;
        }}

        QScrollBar:vertical {{
            background-color: {colors.get('hover', '#F5F5F5')};
            width: 10px;
            border-radius: 5px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {colors.get('secondary', '#6B7280')};
            border-radius: 5px;
            min-height: 20px;
        }}

        QMenu {{
            background-color: {colors.get('card', '#FFFFFF')};
            border: 1px solid {colors.get('border', '#e0e0e0')};
            border-radius: 4px;
        }}

        QMenu::item:selected {{
            background-color: {colors.get('highlight', '#1976d2')};
            color: #FFFFFF;
        }}

        QDialog {{
            background-color: {colors.get('dialog_bg', '#FFFFFF')};
        }}
        """

    def _scan_qss_themes(self):
        themes = {}
        for qss_file in glob.glob(os.path.join(self.qss_theme_dir, '*.qss')):
            name = os.path.splitext(os.path.basename(qss_file))[0]
            themes[name] = qss_file
        return themes

    def get_all_themes(self):
        # 返回所有主题名称（数据库）
        return [row[0] for row in self._get_all_themes_from_db()]

    def get_available_themes(self):
        """获取可用主题列表（兼容性方法）

        Returns:
            dict: 主题名称到主题信息的映射
        """
        try:
            themes = {}
            # 获取数据库中的主题
            db_themes = self._get_all_themes_from_db()
            for name, type_, content, origin, created_at, updated_at in db_themes:
                themes[name] = {
                    'name': name,
                    'type': type_,
                    'origin': origin,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'description': f'{type_.upper()}主题' if type_ else '未知类型主题'
                }

            return themes

        except Exception as e:
            logger.error(f"获取主题列表失败: {e}")
            return {}  # 返回空字典，UI会显示"暂无主题"

    def _apply_qss_theme_async(self, theme_name, qss_content, base_type):
        """异步应用QSS主题内容
        
        Args:
            theme_name: 主题名称
            qss_content: QSS主题内容
            base_type: 基础主题类型
        """
        try:
            logger.debug(f"开始异步应用QSS主题: {theme_name}")
            
            # 应用QSS主题内容
            self.apply_qss_theme_content(qss_content)
            
            logger.info(f"✅ QSS主题异步应用完成: {theme_name} (base_type={base_type})")
        except Exception as e:
            logger.error(f"❌ 异步应用QSS主题失败: {e}")
    
    def apply_qss_theme_content(self, qss):
        # 全局滚动条样式
        scrollbar_qss = '''
            QScrollBar:vertical {
                width: 5px;
                background: #f0f0f0;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar:horizontal {
                height: 5px;
                background: #f0f0f0;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #b0b0b0;
                min-height: 20px;
                min-width: 20px;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                height: 0px;
                width: 0px;
                background: none;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        '''
        app = QApplication.instance()
        if not app:
            logger.warning("QApplication not available, cannot apply QSS theme")
            return
        app.setStyleSheet(qss + '\n' + scrollbar_qss)

    def clear_qss_theme(self):
        """清除QSS主题样式表"""
        app = QApplication.instance()
        if app:
            # 直接清除全局样式表，这是一个轻量级操作，不需要异步
            app.setStyleSheet('')
            logger.debug("已清除全局QSS样式表")

    def _clear_widget_stylesheets(self):
        """清除所有已跟踪组件的样式表"""
        try:
            # 优化：如果没有跟踪的组件，直接返回
            if not hasattr(self, '_tracked_widgets') or not self._tracked_widgets:
                logger.debug("没有需要清除的跟踪组件，跳过样式表清除")
                return
            
            # 异步批量清除组件样式表，避免阻塞UI
            QTimer.singleShot(0, self._clear_widget_stylesheets_async)
        except Exception as e:
            logger.warning(f"清除组件样式表失败: {e}")
    
    def _clear_widget_stylesheets_async(self):
        """异步批量清除组件样式表"""
        try:
            # 批量处理组件样式表清除
            batch_size = 50  # 每批处理50个组件
            widgets = list(self._tracked_widgets.copy())  # 转换为列表以便批量处理
            
            # 分批清除组件样式表
            for i in range(0, len(widgets), batch_size):
                batch = widgets[i:i + batch_size]
                # 使用定时器延迟处理每批，避免阻塞UI
                QTimer.singleShot(i // batch_size * 5, lambda b=batch: self._clear_batch_stylesheets(b))
                
            logger.debug(f"异步清除样式表：共 {len(widgets)} 个组件，分为 {len(widgets) // batch_size + 1} 批处理")
        except Exception as e:
            logger.warning(f"异步清除组件样式表失败: {e}")
    
    def _clear_batch_stylesheets(self, widgets):
        """清除一批组件的样式表"""
        for widget in widgets:
            try:
                if widget and not widget.isVisible():
                    widget.setStyleSheet('')
            except Exception as e:
                logger.warning(f"清除组件 {widget.__class__.__name__ if widget else 'Unknown'} 样式表失败: {e}")

    def is_qss_theme(self):
        return self._current_theme_type == ThemeType.QSS

    def _refresh_all_widgets(self):
        """强制刷新所有窗口组件以应用JSON主题（异步优化版）

        JSON主题不像QSS可以通过setStyleSheet全局应用，
        需要遍历所有窗口和组件，触发重绘。
        使用异步批量刷新避免UI卡顿。
        """
        try:
            app = QApplication.instance()
            if not app:
                return

            # 收集所有需要刷新的顶层窗口
            # 过滤已销毁窗口（检查widget是否有效）
            top_widgets = []
            for w in app.topLevelWidgets():
                try:
                    # 检查窗口是否有效（未被销毁）
                    if w and not w.isHidden():
                        # 尝试访问窗口属性，如果窗口已销毁会抛出异常
                        _ = w.windowTitle()
                        top_widgets.append(w)
                except (RuntimeError, AttributeError):
                    # 窗口已销毁，跳过
                    continue

            if not top_widgets:
                return

            logger.info(f"JSON主题：开始异步刷新 {len(top_widgets)} 个顶层窗口")

            # 使用定时器分批刷新，避免阻塞UI（增加延迟到100ms）
            self._refresh_widgets_batch(top_widgets, 0, delay=100)

        except Exception as e:
            logger.error(f"刷新窗口组件失败: {e}")

    def _refresh_widgets_batch(self, widgets, index, delay=10):
        """分批刷新组件（避免UI卡顿）

        Args:
            widgets: 要刷新的组件列表
            index: 当前索引
            delay: 延迟时间（毫秒）
        """
        try:
            if index >= len(widgets):
                logger.info("JSON主题：所有窗口组件刷新完成")
                return

            widget = widgets[index]

            # 刷新当前widget
            try:
                # 轻量级刷新：只更新样式，不强制重绘
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()

                # 异步刷新子组件树
                QTimer.singleShot(0, lambda: self._refresh_widget_tree_async(widget))

            except Exception as e:
                logger.debug(f"刷新widget失败: {e}")

            # 继续下一个widget（使用定时器避免阻塞）
            QTimer.singleShot(delay, lambda: self._refresh_widgets_batch(widgets, index + 1, delay))

        except Exception as e:
            logger.error(f"批量刷新失败: {e}")

    def _refresh_widget_tree_async(self, widget):
        """异步递归刷新组件树（优化版）"""
        try:
            # 使用findChildren一次性获取所有子组件（比递归快）
            children = widget.findChildren(QWidget)

            # 分批处理子组件
            batch_size = 50  # 每批处理50个组件
            for i in range(0, len(children), batch_size):
                batch = children[i:i + batch_size]
                # 使用定时器延迟处理每批
                QTimer.singleShot(i // batch_size * 5, lambda b=batch: self._refresh_batch(b))

        except Exception as e:
            logger.debug(f"异步刷新组件树失败: {e}")

    def _refresh_batch(self, widgets):
        """刷新一批组件"""
        for widget in widgets:
            try:
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            except:
                pass  # 忽略单个组件错误

    def _refresh_widget_tree(self, widget):
        """递归刷新组件树"""
        try:
            # 更新当前组件
            widget.update()

            # 递归更新所有子组件
            for child in widget.findChildren(QWidget):
                try:
                    # 重新应用样式
                    child.style().unpolish(child)
                    child.style().polish(child)
                    child.update()
                except:
                    pass  # 某些组件可能不支持，跳过

        except Exception as e:
            # 忽略单个组件的错误，继续处理其他组件
            pass

    # 主题增删改查接口（预留）
    def add_theme(self, name, type_, content, origin='user'):
        self._upsert_theme(name, type_, content, origin)

    def delete_theme(self, name):
        self.conn.execute('DELETE FROM themes WHERE name=?', (name,))
        self.conn.commit()

    def rename_theme(self, old_name: str, new_name: str) -> bool:
        """重命名主题

        Args:
            old_name: 原主题名称
            new_name: 新主题名称

        Returns:
            True: 重命名成功
            False: 重命名失败
        """
        try:
            # 检查旧主题是否存在
            row = self._get_theme_content(old_name)
            if not row:
                logger.error(f"主题不存在: {old_name}")
                return False

            # 检查新名称是否已被使用
            existing = self._get_theme_content(new_name)
            if existing:
                logger.error(f"主题名称已存在: {new_name}")
                return False

            # 更新数据库
            self.conn.execute(
                'UPDATE themes SET name=?, updated_at=? WHERE name=?',
                (new_name, datetime.now().isoformat(), old_name)
            )
            self.conn.commit()

            logger.info(f"主题已重命名: {old_name} -> {new_name}")
            return True

        except Exception as e:
            logger.error(f"重命名主题失败: {e}")
            return False

    def update_theme(self, name, content):
        now = datetime.now().isoformat()
        self.conn.execute(
            'UPDATE themes SET content=?, updated_at=? WHERE name=?', (content, now, name))
        self.conn.commit()

    def edit_theme(self, name: str, new_content: str) -> bool:
        """
        编辑QSS主题内容并保存到数据库，仅支持QSS类型主题。
        Args:
            name: 主题名称
            new_content: 新的QSS内容
        Returns:
            True: 编辑成功
            False: 编辑失败（主题不存在或不是QSS类型）
        """
        row = self._get_theme_content(name)
        if not row:
            return False
        type_, _ = row
        if type_ != 'qss':
            return False
        self.update_theme(name, new_content)
        # 编辑后自动应用新主题
        self.set_theme(name)
        # 不再重复emit，set_theme已emit
        return True

    def _validate_theme_config(self, theme_name: str, theme_data: dict) -> bool:
        """
        验证主题配置

        Args:
            theme_name: 主题名称
            theme_data: 主题数据字典

        Returns:
            True: 验证通过
            False: 验证失败
        """
        try:
            # 基础字段验证
            if not isinstance(theme_data, dict):
                logger.error(f"主题 {theme_name} 配置无效：不是字典类型")
                return False

            # 对于JSON主题，验证必需字段
            if 'colors' in theme_data:
                colors = theme_data.get('colors', {})
                required_colors = ['primary', 'background', 'text_primary']

                missing_colors = [c for c in required_colors if c not in colors]
                if missing_colors:
                    logger.warning(f"主题 {theme_name} 缺少推荐颜色: {missing_colors}")
                    # 警告但不阻止，因为这些可能有默认值

            logger.debug(f"主题 {theme_name} 验证通过")
            return True

        except Exception as e:
            logger.error(f"验证主题 {theme_name} 时出错: {e}")
            return False

    def export_theme(self, theme_name: str, export_path: str) -> bool:
        """
        导出主题到文件

        Args:
            theme_name: 要导出的主题名称
            export_path: 导出文件路径

        Returns:
            True: 导出成功
            False: 导出失败
        """
        try:
            # 首先尝试从数据库获取
            row = self._get_theme_content(theme_name)

            if row:
                theme_type, content = row
            else:
                # 如果数据库中没有，检查是否是内置主题
                available_themes = self.get_available_themes()
                if theme_name not in available_themes:
                    logger.error(f"主题不存在: {theme_name}")
                    return False

                theme_info = available_themes[theme_name]
                theme_type = theme_info.get('type', 'builtin')

                # 对于内置主题，导出其配置信息
                if theme_type == 'builtin':
                    # 从theme.json获取配置
                    if theme_name in self._theme_data:
                        content = json.dumps(self._theme_data[theme_name], ensure_ascii=False)
                    else:
                        # 如果没有详细配置，导出基本信息
                        content = json.dumps({
                            'type': 'builtin',
                            'description': theme_info.get('description', ''),
                            'note': 'This is a built-in theme. Content may not be fully customizable.'
                        }, ensure_ascii=False)
                else:
                    logger.error(f"主题 {theme_name} 在数据库中不存在且不是有效的内置主题")
                    return False

            # 构建导出数据
            theme_data = {
                'name': theme_name,
                'type': theme_type,
                'content': content,
                'export_version': '1.0',
                'export_date': datetime.now().isoformat(),
                'exporter': 'FactorWeave-Quant ThemeManager'
            }

            # 写入文件
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(theme_data, f, indent=2, ensure_ascii=False)

            logger.info(f"主题已导出: {theme_name} -> {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出主题失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def import_theme(self, import_path: str, overwrite: bool = False, theme_name: str = None) -> bool:
        """
        从文件导入主题

        支持两种格式：
        1. JSON导出文件（包含元数据）
        2. 纯QSS文件（直接导入）

        Args:
            import_path: 导入文件路径
            overwrite: 是否覆盖同名主题
            theme_name: 主题名称（仅用于QSS文件，JSON文件会忽略此参数）

        Returns:
            True: 导入成功
            False: 导入失败
        """
        try:
            file_ext = os.path.splitext(import_path)[1].lower()

            # 方式1：纯QSS文件
            if file_ext == '.qss':
                logger.info(f"检测到QSS文件: {import_path}")

                # 读取QSS内容
                with open(import_path, 'r', encoding='utf-8') as f:
                    qss_content = f.read()

                # 确定主题名称
                if not theme_name:
                    # 从文件名推导主题名
                    theme_name = Path(import_path).stem

                # 检查是否已存在
                existing = self._get_theme_content(theme_name)
                if existing and not overwrite:
                    logger.error(f"主题已存在: {theme_name}，使用overwrite=True以覆盖")
                    return False

                # 智能检测 base_type
                base_type = self._detect_base_type(theme_name, 'qss', qss_content)

                # 保存到数据库
                self._upsert_theme(theme_name, 'qss', qss_content, 'imported', base_type)

                logger.info(f"QSS主题已导入: {theme_name} (base_type={base_type})")
                return True

            # 方式2：JSON导出文件
            else:
                # 读取主题文件
                with open(import_path, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)

                # 验证必需字段
                required_fields = ['name', 'type', 'content']
                for field in required_fields:
                    if field not in theme_data:
                        logger.error(f"主题文件缺少必需字段: {field}")
                        return False

                name = theme_data['name']
                theme_type = theme_data['type']
                content = theme_data['content']

            # 检查是否已存在
            existing = self._get_theme_content(name)
            if existing and not overwrite:
                logger.error(f"主题已存在: {name}，使用overwrite=True以覆盖")
                return False

            # 对于JSON类型主题，验证内容
            if theme_type == 'json':
                try:
                    content_dict = json.loads(content) if isinstance(content, str) else content
                    if not self._validate_theme_config(name, content_dict):
                        logger.warning(f"主题 {name} 验证未完全通过，但仍将导入")
                except json.JSONDecodeError:
                    logger.error(f"JSON主题内容无效: {name}")
                    return False

            # 智能检测 base_type
            base_type = self._detect_base_type(name, theme_type, content if isinstance(content, str) else json.dumps(content))

            # 保存到数据库
            self._upsert_theme(name, theme_type, content, 'imported', base_type)

            logger.info(f"主题已导入: {name} ({theme_type}, base_type={base_type})")
            return True

        except FileNotFoundError:
            logger.error(f"主题文件不存在: {import_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"主题文件格式错误: {e}")
            return False
        except Exception as e:
            logger.error(f"导入主题失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def get_theme_manager(config_manager: Optional[ConfigManager] = None) -> ThemeManager:
    """获取主题管理器实例

    Args:
        config_manager: 可选的配置管理器实例

    Returns:
        主题管理器实例
    """
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager(config_manager)
    return _theme_manager_instance
