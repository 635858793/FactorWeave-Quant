"""
现代化UI组件库 - 专业交易软件风格
提供：
1. 可折叠侧边栏导航
2. 增强统计卡片（带阴影、迷你图、趋势指示器）
3. 可折叠面板
4. 快捷操作面板
5. 实时数据指示器
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsDropShadowEffect, QPropertyAnimation, QEasingCurve,
    QScrollArea, QFrame, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient, QFont, QIcon
from loguru import logger
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NavItem:
    name: str
    label: str
    icon: str
    shortcut: str


FINANCIAL_COLORS = {
    'primary': '#2962FF',
    'profit': '#10B981',
    'loss': '#EF4444',
    'warning': '#F59E0B',
    'auxiliary_1': '#8B5CF6',
    'auxiliary_2': '#EC4899',
    'auxiliary_3': '#06B6D4',
}

STATUS_COLORS = {
    'running': '#10B981',
    'configured': '#3B82F6',
    'error': '#EF4444',
    'stopped': '#6B7280'
}


class ModernSidebarNavigation(QWidget):
    """
    现代化侧边栏导航组件
    - 可折叠（200px ↔ 60px）
    - 带图标和文字
    - 支持快捷键
    - 悬停动画效果
    """
    
    nav_changed = pyqtSignal(str)
    
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.expanded_width = 200
        self.collapsed_width = 60
        self.is_expanded = True
        self.nav_items: List[NavItem] = []
        self.nav_buttons: List[QPushButton] = []
        self.current_nav = None
        
        # 连接主题变化信号
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self._setup_ui()
        self._apply_style()
        
    def _setup_ui(self):
        self.setFixedWidth(self.expanded_width)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.nav_container = QWidget()
        self.nav_layout = QVBoxLayout(self.nav_container)
        self.nav_layout.setContentsMargins(8, 8, 8, 8)
        self.nav_layout.setSpacing(4)
        
        self.main_layout.addWidget(self.nav_container)
        
        self.main_layout.addStretch()
        
        self.quick_action_container = QWidget()
        self.quick_action_layout = QVBoxLayout(self.quick_action_container)
        self.quick_action_layout.setContentsMargins(8, 8, 8, 8)
        self.quick_action_layout.setSpacing(4)
        
        self.main_layout.addWidget(self.quick_action_container)
        
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.clicked.connect(self.toggle)
        self.quick_action_layout.addWidget(self.toggle_btn, alignment=Qt.AlignCenter)
        
    def add_nav_item(self, name: str, label: str, icon: str = "", shortcut: str = ""):
        item = NavItem(name=name, label=label, icon=icon, shortcut=shortcut)
        self.nav_items.append(item)
        
        btn = QPushButton()
        btn.setObjectName("navButton")
        btn.setProperty("nav_name", name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        
        self._update_button_text(btn, item)
        btn.clicked.connect(lambda checked, n=name: self._on_nav_clicked(n))
        
        self.nav_layout.addWidget(btn)
        self.nav_buttons.append(btn)
        
    def _update_button_text(self, btn: QPushButton, item: NavItem):
        if self.is_expanded:
            text = f"{item.icon} {item.label}" if item.icon else item.label
            if item.shortcut:
                text += f" ({item.shortcut})"
            btn.setText(text)
            btn.setToolTip("")
        else:
            btn.setText(item.icon if item.icon else item.label[0])
            btn.setToolTip(f"{item.label} ({item.shortcut})" if item.shortcut else item.label)
            
    def add_quick_action(self, label: str, icon: str, callback: Callable):
        btn = QPushButton(f"{icon} {label}" if self.is_expanded else icon)
        btn.setObjectName("quickActionButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        self.quick_action_layout.addWidget(btn)
        
    def toggle(self):
        self.is_expanded = not self.is_expanded
        target_width = self.expanded_width if self.is_expanded else self.collapsed_width
        
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        
        current_geometry = self.geometry()
        target_geometry = QRect(
            current_geometry.x(),
            current_geometry.y(),
            target_width,
            current_geometry.height()
        )
        
        self.animation.setStartValue(current_geometry)
        self.animation.setEndValue(target_geometry)
        self.animation.start()
        
        for btn, item in zip(self.nav_buttons, self.nav_items):
            self._update_button_text(btn, item)
            
    def _on_nav_clicked(self, name: str):
        self.current_nav = name
        self.nav_changed.emit(name)
        
    def set_current_nav(self, name: str):
        for btn in self.nav_buttons:
            if btn.property("nav_name") == name:
                btn.setChecked(True)
                self.current_nav = name
                break
                
    def _apply_style(self):
        colors = self._get_theme_colors()
        
        self.setStyleSheet(f"""
            ModernSidebarNavigation {{
                background-color: {colors.get('background', '#FFFFFF')};
                border-right: 1px solid {colors.get('border', '#E0E0E0')};
            }}
            
            QPushButton#navButton {{
                background-color: transparent;
                color: {colors.get('text', '#222B45')};
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                text-align: left;
                font-size: 13px;
                font-weight: 500;
            }}
            
            QPushButton#navButton:hover {{
                background-color: {colors.get('hover', '#F0F4F8')};
            }}
            
            QPushButton#navButton:checked {{
                background-color: {colors.get('highlight', '#2962FF')};
                color: white;
            }}
            
            QPushButton#quickActionButton {{
                background-color: {colors.get('surface', '#F8F9FA')};
                color: {colors.get('text', '#222B45')};
                border: 1px solid {colors.get('border', '#E0E0E0')};
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }}
            
            QPushButton#quickActionButton:hover {{
                background-color: {colors.get('hover', '#E3F2FD')};
                border-color: {colors.get('highlight', '#2962FF')};
            }}
            
            QPushButton {{
                background-color: {colors.get('surface', '#F8F9FA')};
                border: none;
                border-radius: 8px;
                font-size: 18px;
            }}
            
            QPushButton:hover {{
                background-color: {colors.get('hover', '#E3F2FD')};
            }}
        """)
        
    def _get_theme_colors(self) -> Dict[str, str]:
        if self.theme_manager:
            try:
                return self.theme_manager.get_theme_colors()
            except Exception as e:
                logger.warning(f"获取主题颜色失败: {e}")
        
        return {
            'background': '#FFFFFF',
            'surface': '#F8F9FA',
            'text': '#222B45',
            'highlight': '#2962FF',
            'hover': '#E3F2FD',
            'border': '#E0E0E0',
        }
    
    def _on_theme_changed(self, theme):
        """主题变化时重新应用样式"""
        logger.debug(f"ModernSidebarNavigation收到主题变化: {theme}")
        self._apply_style()


class SparklineWidget(QWidget):
    """
    迷你趋势图组件
    - 显示最近7天的数据趋势
    - 支持自定义颜色
    - 自动缩放
    """
    
    def __init__(self, data: List[float] = None, color: str = "#2962FF", parent=None):
        super().__init__(parent)
        self.data = data or []
        self.color = color
        self.setFixedSize(80, 30)
        
    def set_data(self, data: List[float]):
        self.data = data
        self.update()
        
    def paintEvent(self, event):
        if not self.data or len(self.data) < 2:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor(self.color))
        pen.setWidth(2)
        painter.setPen(pen)
        
        min_val = min(self.data)
        max_val = max(self.data)
        range_val = max_val - min_val if max_val != min_val else 1
        
        width = self.width() - 4
        height = self.height() - 4
        
        points = []
        for i, value in enumerate(self.data):
            x = 2 + (i / (len(self.data) - 1)) * width
            y = height - 2 - ((value - min_val) / range_val) * height
            points.append((x, y))
            
        for i in range(len(points) - 1):
            painter.drawLine(int(points[i][0]), int(points[i][1]),
                           int(points[i+1][0]), int(points[i+1][1]))


class EnhancedStatCard(QWidget):
    """
    增强统计卡片
    - 阴影效果（QGraphicsDropShadowEffect）
    - 迷你趋势图（Sparkline）
    - 趋势指示器（↑↓箭头）
    - 悬停动画
    """
    
    clicked = pyqtSignal()
    
    def __init__(self, title: str, value: str = "0", color: str = "#2962FF",
                 parent=None, theme_manager=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.color = color
        self.theme_manager = theme_manager
        self.trend_data: List[float] = []
        self.trend_percent = 0.0
        
        # 连接主题变化信号
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self._setup_ui()
        self._apply_shadow()
        self._apply_style()
        
    def _setup_ui(self):
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        header_layout = QHBoxLayout()
        
        self.icon_label = QLabel("📊")
        self.icon_label.setStyleSheet(f"font-size: 24px;")
        header_layout.addWidget(self.icon_label)
        
        self.title_label = QLabel(self.title)
        self.title_label.setObjectName("cardTitle")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        value_layout = QHBoxLayout()
        
        self.value_label = QLabel(self.value)
        self.value_label.setObjectName("cardValue")
        value_layout.addWidget(self.value_label)
        value_layout.addStretch()
        
        self.sparkline = SparklineWidget(color=self.color)
        value_layout.addWidget(self.sparkline)
        
        layout.addLayout(value_layout)
        
        trend_layout = QHBoxLayout()
        
        self.trend_label = QLabel("--")
        self.trend_label.setObjectName("cardTrend")
        trend_layout.addWidget(self.trend_label)
        trend_layout.addStretch()
        
        self.compare_label = QLabel("较昨日 --")
        self.compare_label.setObjectName("cardCompare")
        trend_layout.addWidget(self.compare_label)
        
        layout.addLayout(trend_layout)
        
    def _apply_shadow(self):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
    def set_value(self, value: str, trend_percent: float = 0.0, trend_data: List[float] = None):
        self.value = value
        self.trend_percent = trend_percent
        self.trend_data = trend_data or []
        
        self.value_label.setText(value)
        
        if trend_percent > 0:
            self.trend_label.setText(f"↑ {abs(trend_percent):.1f}%")
            self.trend_label.setStyleSheet(f"color: {FINANCIAL_COLORS['profit']}; font-weight: bold;")
        elif trend_percent < 0:
            self.trend_label.setText(f"↓ {abs(trend_percent):.1f}%")
            self.trend_label.setStyleSheet(f"color: {FINANCIAL_COLORS['loss']}; font-weight: bold;")
        else:
            self.trend_label.setText("--")
            self.trend_label.setStyleSheet("color: #6B7280;")
            
        if self.trend_data:
            self.sparkline.set_data(self.trend_data)
            
    def _apply_style(self):
        colors = self._get_theme_colors()
        
        self.setStyleSheet(f"""
            EnhancedStatCard {{
                background-color: {colors.get('surface', '#FFFFFF')};
                border: 1px solid {colors.get('border', '#E0E0E0')};
                border-radius: 12px;
            }}
            
            EnhancedStatCard:hover {{
                border: 2px solid {self.color};
            }}
            
            QLabel#cardTitle {{
                color: {colors.get('text_secondary', '#6B7280')};
                font-size: 13px;
                font-weight: 500;
            }}
            
            QLabel#cardValue {{
                color: {self.color};
                font-size: 28px;
                font-weight: bold;
            }}
            
            QLabel#cardCompare {{
                color: {colors.get('text_secondary', '#6B7280')};
                font-size: 11px;
            }}
        """)
        
    def _get_theme_colors(self) -> Dict[str, str]:
        if self.theme_manager:
            try:
                return self.theme_manager.get_theme_colors()
            except Exception as e:
                logger.warning(f"获取主题颜色失败: {e}")
        
        return {
            'surface': '#FFFFFF',
            'text': '#222B45',
            'text_secondary': '#6B7280',
            'border': '#E0E0E0',
        }
    
    def _on_theme_changed(self, theme):
        """主题变化时重新应用样式"""
        logger.debug(f"EnhancedStatCard收到主题变化: {theme}")
        self._apply_style()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CollapsiblePanel(QWidget):
    """
    可折叠面板
    - 点击标题栏折叠/展开
    - 动画效果
    - 记住折叠状态
    """
    
    def __init__(self, title: str, parent=None, theme_manager=None):
        super().__init__(parent)
        self.title = title
        self.theme_manager = theme_manager
        self.is_expanded = True
        self.content_widget: Optional[QWidget] = None
        
        # 连接主题变化信号
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self._setup_ui()
        self._apply_style()
        
    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.header = QPushButton(f"▼ {self.title}")
        self.header.setObjectName("panelHeader")
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(self.toggle)
        self.main_layout.addWidget(self.header)
        
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        
        self.main_layout.addWidget(self.content_container)
        
    def set_content(self, widget: QWidget):
        if self.content_widget:
            self.content_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()
            
        self.content_widget = widget
        self.content_layout.addWidget(widget)
        
    def toggle(self):
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            self.header.setText(f"▼ {self.title}")
            self.content_container.show()
        else:
            self.header.setText(f"▶ {self.title}")
            self.content_container.hide()
            
    def _apply_style(self):
        colors = self._get_theme_colors()
        
        self.setStyleSheet(f"""
            QPushButton#panelHeader {{
                background-color: {colors.get('surface', '#F8F9FA')};
                color: {colors.get('text', '#222B45')};
                border: 1px solid {colors.get('border', '#E0E0E0')};
                border-radius: 8px;
                padding: 12px;
                text-align: left;
                font-size: 13px;
                font-weight: 600;
            }}
            
            QPushButton#panelHeader:hover {{
                background-color: {colors.get('hover', '#E3F2FD')};
            }}
        """)
        
    def _get_theme_colors(self) -> Dict[str, str]:
        if self.theme_manager:
            try:
                return self.theme_manager.get_theme_colors()
            except Exception as e:
                logger.warning(f"获取主题颜色失败: {e}")
        
        return {
            'surface': '#F8F9FA',
            'text': '#222B45',
            'hover': '#E3F2FD',
            'border': '#E0E0E0',
        }
    
    def _on_theme_changed(self, theme):
        """主题变化时重新应用样式"""
        logger.debug(f"CollapsiblePanel收到主题变化: {theme}")
        self._apply_style()


class QuickActionPanel(QWidget):
    """
    快捷操作面板
    - 常用操作快捷按钮
    - 最近使用的策略
    - 收藏的策略
    """
    
    action_triggered = pyqtSignal(str)
    
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        
        # 连接主题变化信号
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self._setup_ui()
        self._apply_style()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        title = QLabel("快捷操作")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        actions = [
            ("新建策略", "➕", "create"),
            ("快速回测", "🚀", "backtest"),
            ("参数优化", "⚙️", "optimize"),
            ("导入策略", "📥", "import"),
        ]
        
        for label, icon, action_id in actions:
            btn = QPushButton(f"{icon}\n{label}")
            btn.setObjectName("actionButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, a=action_id: self.action_triggered.emit(a))
            btn_layout.addWidget(btn)
            
        layout.addLayout(btn_layout)
        
        recent_label = QLabel("最近使用")
        recent_label.setObjectName("sectionTitle")
        layout.addWidget(recent_label)
        
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recentList")
        self.recent_list.setMaximumHeight(150)
        layout.addWidget(self.recent_list)
        
        layout.addStretch()
        
    def add_recent_strategy(self, name: str, status: str):
        item = QListWidgetItem(f"• {name} ({status})")
        self.recent_list.insertItem(0, item)
        
        if self.recent_list.count() > 5:
            self.recent_list.takeItem(self.recent_list.count() - 1)
            
    def _apply_style(self):
        colors = self._get_theme_colors()
        
        self.setStyleSheet(f"""
            QLabel#panelTitle {{
                color: {colors.get('text', '#222B45')};
                font-size: 14px;
                font-weight: bold;
            }}
            
            QLabel#sectionTitle {{
                color: {colors.get('text_secondary', '#6B7280')};
                font-size: 12px;
                font-weight: 600;
            }}
            
            QPushButton#actionButton {{
                background-color: {colors.get('surface', '#FFFFFF')};
                color: {colors.get('text', '#222B45')};
                border: 1px solid {colors.get('border', '#E0E0E0')};
                border-radius: 8px;
                padding: 12px;
                font-size: 11px;
            }}
            
            QPushButton#actionButton:hover {{
                background-color: {colors.get('hover', '#E3F2FD')};
                border-color: {colors.get('highlight', '#2962FF')};
            }}
            
            QListWidget#recentList {{
                background-color: {colors.get('surface', '#FFFFFF')};
                border: 1px solid {colors.get('border', '#E0E0E0')};
                border-radius: 8px;
                padding: 8px;
            }}
            
            QListWidget#recentList::item {{
                color: {colors.get('text', '#222B45')};
                padding: 4px;
            }}
            
            QListWidget#recentList::item:hover {{
                background-color: {colors.get('hover', '#E3F2FD')};
            }}
        """)
        
    def _get_theme_colors(self) -> Dict[str, str]:
        if self.theme_manager:
            try:
                return self.theme_manager.get_theme_colors()
            except Exception as e:
                logger.warning(f"获取主题颜色失败: {e}")
        
        return {
            'surface': '#FFFFFF',
            'text': '#222B45',
            'text_secondary': '#6B7280',
            'highlight': '#2962FF',
            'hover': '#E3F2FD',
            'border': '#E0E0E0',
        }
    
    def _on_theme_changed(self, theme):
        """主题变化时重新应用样式"""
        logger.debug(f"QuickActionPanel收到主题变化: {theme}")
        self._apply_style()


class RealtimeIndicator(QWidget):
    """
    实时数据指示器
    - 绿色闪烁点（数据更新时）
    - 最后更新时间
    - 连接状态
    """
    
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.is_connected = True
        self.last_update_time = datetime.now()
        
        # 连接主题变化信号
        if self.theme_manager:
            self.theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self._setup_ui()
        self._apply_style()
        
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._blink)
        self.blink_visible = True
        
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        layout.addWidget(self.status_dot)
        
        self.status_label = QLabel("实时")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.time_label = QLabel(f"最后更新: {self.last_update_time.strftime('%H:%M:%S')}")
        self.time_label.setObjectName("timeLabel")
        layout.addWidget(self.time_label)
        
    def set_connected(self, connected: bool):
        self.is_connected = connected
        if connected:
            self.status_label.setText("实时")
            self.status_dot.setStyleSheet("color: #10B981;")
            self.blink_timer.start(1000)
        else:
            self.status_label.setText("离线")
            self.status_dot.setStyleSheet("color: #EF4444;")
            self.blink_timer.stop()
            
    def update_time(self):
        self.last_update_time = datetime.now()
        self.time_label.setText(f"最后更新: {self.last_update_time.strftime('%H:%M:%S')}")
        
    def _blink(self):
        if self.is_connected:
            self.blink_visible = not self.blink_visible
            color = "#10B981" if self.blink_visible else "#6EE7B7"
            self.status_dot.setStyleSheet(f"color: {color};")
            
    def _apply_style(self):
        colors = self._get_theme_colors()
        
        self.setStyleSheet(f"""
            RealtimeIndicator {{
                background-color: {colors.get('surface', '#F8F9FA')};
                border: 1px solid {colors.get('border', '#E0E0E0')};
                border-radius: 8px;
            }}
            
            QLabel#statusDot {{
                font-size: 12px;
                color: #10B981;
            }}
            
            QLabel#statusLabel {{
                color: {colors.get('text', '#222B45')};
                font-size: 12px;
                font-weight: 600;
            }}
            
            QLabel#timeLabel {{
                color: {colors.get('text_secondary', '#6B7280')};
                font-size: 11px;
            }}
        """)
        
    def _get_theme_colors(self) -> Dict[str, str]:
        if self.theme_manager:
            try:
                return self.theme_manager.get_theme_colors()
            except Exception as e:
                logger.warning(f"获取主题颜色失败: {e}")
        
        return {
            'surface': '#F8F9FA',
            'text': '#222B45',
            'text_secondary': '#6B7280',
            'border': '#E0E0E0',
        }
    
    def _on_theme_changed(self, theme):
        """主题变化时重新应用样式"""
        logger.debug(f"RealtimeIndicator收到主题变化: {theme}")
        self._apply_style()


class WorkspaceManager:
    """
    工作区管理器
    - 保存/恢复布局状态
    - 多工作区切换
    - 导入/导出配置
    """
    
    WORKSPACE_KEY = "strategy_manager/workspace"
    
    def __init__(self, settings: QSettings = None):
        self.settings = settings or QSettings()
        self.current_workspace = "default"
        
    def save_workspace(self, name: str, state: Dict):
        key = f"{self.WORKSPACE_KEY}/{name}"
        self.settings.setValue(key, state)
        
    def load_workspace(self, name: str) -> Optional[Dict]:
        key = f"{self.WORKSPACE_KEY}/{name}"
        return self.settings.value(key)
        
    def get_workspaces(self) -> List[str]:
        self.settings.beginGroup(self.WORKSPACE_KEY)
        workspaces = self.settings.childGroups()
        self.settings.endGroup()
        return list(workspaces)
        
    def delete_workspace(self, name: str):
        key = f"{self.WORKSPACE_KEY}/{name}"
        self.settings.remove(key)
        
    def export_workspace(self, name: str, file_path: str):
        state = self.load_workspace(name)
        if state:
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                
    def import_workspace(self, name: str, file_path: str):
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        self.save_workspace(name, state)
