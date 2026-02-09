"""
现代化指标卡片组件

参考TradingView设计的指标显示卡片
"""

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

# 延迟导入logger，避免在模块级别导入时触发性能监控
logger = None

def _get_logger():
    """延迟导入logger"""
    global logger
    if logger is None:
        from loguru import logger as _logger
        logger = _logger
    return logger

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            _get_logger().info("主题管理器模块导入成功")
        except Exception as e:
            _get_logger().warning(f"导入主题管理器失败: {e}")


class ModernMetricCard(QFrame):
    """现代化指标卡片 - 参考TradingView设计"""

    def __init__(self, title: str, value: str = "0", unit: str = "", color: str = "#3498db", trend: str = "neutral"):
        super().__init__()
        self.title = title
        self.value = value
        self.unit = unit
        self.color = color
        self.trend = trend
        self._last_trend = trend
        self.title_label = None
        self.trend_label = None
        self.unit_label = None
        
        # 延迟导入并初始化主题管理器
        _import_theme_manager()
        self.theme_manager = None
        if THEME_MANAGER_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
                self.theme_manager.theme_changed.connect(self.update_theme)
            except Exception as e:
                _get_logger().warning(f"获取ThemeManager失败: {e}")
        
        self.init_ui()
        self.update_theme()

    def init_ui(self):
        # 设置响应式大小和阴影效果 - 更紧凑的卡片
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumHeight(52)
        self.setMaximumHeight(52)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(4)

        # 标题区域
        title_layout = QHBoxLayout()

        self.title_label = QLabel(self.title)
        title_font = QFont("Segoe UI", 9, QFont.Weight.Medium)
        self.title_label.setFont(title_font)

        # 趋势指示器
        self.trend_label = QLabel()
        if self.trend == "up":
            self.trend_label.setText("▲")
        elif self.trend == "down":
            self.trend_label.setText("▼")
        else:
            self.trend_label.setText("●")

        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.trend_label)

        # 数值显示
        value_layout = QHBoxLayout()

        self.value_label = QLabel(self.value)
        value_font = QFont("Segoe UI", 13, QFont.Weight.Bold)
        self.value_label.setFont(value_font)

        self.unit_label = QLabel(self.unit)
        unit_font = QFont("Segoe UI", 8, QFont.Weight.Normal)
        self.unit_label.setFont(unit_font)

        value_layout.addWidget(self.value_label)
        value_layout.addWidget(self.unit_label)
        value_layout.addStretch()

        layout.addLayout(title_layout)
        layout.addLayout(value_layout)
        layout.addStretch()

    def update_theme(self):
        """更新主题样式"""
        try:
            if self.theme_manager:
                colors = self.theme_manager.get_theme_colors()
                is_dark = self.theme_manager.is_dark_theme()
                
                # 根据主题类型选择卡片背景色
                if is_dark:
                    # 深色主题：使用深蓝色渐变
                    card_bg_start = "#2c3e50"
                    card_bg_end = "#34495e"
                    card_border = "#404040"
                    text_color = "#ecf0f1"
                    title_color = "#bdc3c7"
                    unit_color = "#7f8c8d"
                else:
                    # 浅色主题：使用浅色渐变
                    card_bg_start = "#f7f9fa"
                    card_bg_end = "#ffffff"
                    card_border = "#e0e0e0"
                    text_color = "#222b45"
                    title_color = "#5c6b7f"
                    unit_color = "#8f9bb3"
                
                # 设置卡片样式 - 简化样式表，避免复杂渐变
                self.setStyleSheet(f"""
                    QFrame {{
                        background-color: {card_bg_start};
                        border: 1px solid {card_border};
                        border-radius: 8px;
                        margin: 3px;
                        padding: 0px;
                    }}
                    QLabel {{
                        background: transparent;
                        border: none;
                        color: {text_color};
                    }}
                """)
                
                # 更新标题颜色
                if self.title_label:
                    self.title_label.setStyleSheet(f"color: {title_color}; font-weight: 500;")
                
                # 更新数值颜色
                if self.value_label:
                    self.value_label.setStyleSheet(f"color: {self.color}; font-weight: bold;")
                
                # 更新单位颜色
                if self.unit_label:
                    self.unit_label.setStyleSheet(f"color: {unit_color}; margin-left: 4px;")
                
                # 更新趋势指示器颜色
                if self.trend_label:
                    if self.trend == "up":
                        self.trend_label.setStyleSheet("color: #27ae60; font-size: 10px;")
                    elif self.trend == "down":
                        self.trend_label.setStyleSheet("color: #e74c3c; font-size: 10px;")
                    else:
                        self.trend_label.setStyleSheet("color: #95a5a6; font-size: 8px;")
            else:
                # ThemeManager不可用，使用默认深色样式
                self.setStyleSheet(f"""
                    QFrame {{
                        background-color: #2c3e50;
                        border: 1px solid #404040;
                        border-radius: 8px;
                        margin: 3px;
                        padding: 0px;
                    }}
                    QLabel {{
                        background: transparent;
                        border: none;
                        color: #ecf0f1;
                    }}
                """)
                
                if self.title_label:
                    self.title_label.setStyleSheet("color: #bdc3c7; font-weight: 500;")
                if self.value_label:
                    self.value_label.setStyleSheet(f"color: {self.color}; font-weight: bold;")
                if self.unit_label:
                    self.unit_label.setStyleSheet("color: #7f8c8d; margin-left: 4px;")
                if self.trend_label:
                    if self.trend == "up":
                        self.trend_label.setStyleSheet("color: #27ae60; font-size: 10px;")
                    elif self.trend == "down":
                        self.trend_label.setStyleSheet("color: #e74c3c; font-size: 10px;")
                    else:
                        self.trend_label.setStyleSheet("color: #95a5a6; font-size: 8px;")
        except Exception as e:
            _get_logger().error(f"更新主题样式失败: {e}")
            # 发生错误时使用简单的备用样式
            try:
                self.setStyleSheet("""
                    QFrame {
                        background-color: #2c3e50;
                        border: 1px solid #404040;
                        border-radius: 8px;
                    }
                    QLabel {
                        background: transparent;
                        color: #ecf0f1;
                    }
                """)
            except Exception as e2:
                _get_logger().error(f"设置备用样式失败: {e2}")

    def update_value(self, value: str, trend: str = "neutral"):
        """更新数值和趋势"""
        self.value_label.setText(value)
        self.trend = trend
        
        # 更新趋势指示器文本
        if self.trend == "up":
            self.trend_label.setText("▲")
        elif self.trend == "down":
            self.trend_label.setText("▼")
        else:
            self.trend_label.setText("●")
        
        # 只在趋势真正改变时才更新样式，避免不必要的样式表设置
        if self.trend != self._last_trend:
            self._last_trend = self.trend
            if self.trend_label:
                if self.trend == "up":
                    self.trend_label.setStyleSheet("color: #27ae60; font-size: 10px;")
                elif self.trend == "down":
                    self.trend_label.setStyleSheet("color: #e74c3c; font-size: 10px;")
                else:
                    self.trend_label.setStyleSheet("color: #95a5a6; font-size: 8px;")

    def cleanup(self):
        """清理资源"""
        try:
            # 清理图形效果
            if self.graphicsEffect():
                self.setGraphicsEffect(None)
            
            # 清理布局
            if self.layout():
                while self.layout().count():
                    item = self.layout().takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                    elif item.layout():
                        while item.layout().count():
                            sub_item = item.layout().takeAt(0)
                            if sub_item.widget():
                                sub_item.widget().deleteLater()
            
            _get_logger().debug("ModernMetricCard cleanup completed")
            
        except Exception as e:
            _get_logger().error(f"清理资源失败: {e}")
