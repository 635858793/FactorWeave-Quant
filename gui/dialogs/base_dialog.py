"""
对话框基类模块

提供统一的对话框基类，包含通用的功能：
- 居中显示
- 主题切换支持
- 窗口尺寸记忆和恢复
- 统一的关闭按钮处理
- 加载/完成状态指示器
- 错误提示对话框
- 确认对话框
- 统一的日志记录

作者: Hikyuu-UI Team
版本: 1.0
"""

import os
from typing import Optional, Tuple, Any
from pathlib import Path

from loguru import logger

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QProgressBar, QFrame, QGraphicsDropShadowEffect,
    QApplication
)
from PyQt5.QtCore import Qt, QRect, QSettings, QTimer, QSize, QPoint
from PyQt5.QtGui import QColor, QFont

try:
    from core.events.event_bus import get_event_bus
    from core.events.types import ThemeChangedEvent
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False
    get_event_bus = None
    ThemeChangedEvent = None


class LoadingIndicator(QFrame):
    """加载状态指示器组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loading_indicator")
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFixedHeight(60)
        self.setStyleSheet("""
            #loading_indicator {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 无限循环模式
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(200)
        layout.addWidget(self.progress_bar, 0, Qt.AlignCenter)

        self.message_label = QLabel("加载中...")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("font-size: 14px; color: #495057;")
        layout.addWidget(self.message_label, 0, Qt.AlignCenter)

    def show_message(self, message: str):
        """显示加载消息"""
        self.message_label.setText(message)
        self.show()

    def hide_indicator(self):
        """隐藏指示器"""
        self.hide()


class BaseDialog(QDialog):
    """
    对话框基类

    提供通用的对话框功能，所有自定义对话框都应继承此类。

    功能特性:
        - 自动居中显示在父窗口或屏幕中央
        - 主题切换支持（通过事件总线或主题管理器）
        - 窗口尺寸记忆和恢复（使用 QSettings）
        - 统一的关闭按钮处理
        - 加载/完成状态指示器
        - 错误提示对话框
        - 确认对话框
        - 统一的日志记录

    使用示例:
        ```python
        class MyCustomDialog(BaseDialog):
            def __init__(self, parent=None):
                super().__init__(
                    parent,
                    title="我的对话框",
                    min_size=(600, 400),
                    settings_key="MyCustomDialog"
                )
                self.setup_custom_ui()

            def setup_custom_ui(self):
                # 自定义UI设置
                layout = QVBoxLayout(self)
                label = QLabel("Hello World")
                layout.addWidget(label)
                layout.addStretch()
        ```

    主题切换支持:
        BaseDialog 支持两种主题切换机制：
        1. 事件总线方式：通过订阅 ThemeChangedEvent 事件
        2. 主题管理器方式：通过连接 theme_manager.theme_changed 信号

        子类应重写 on_theme_changed() 方法来处理主题切换逻辑。
    """

    # 类级别的 QSettings 组织信息
    SETTINGS_ORG = "HikyuuUI"
    SETTINGS_APP = "Dialogs"

    def __init__(
        self,
        parent: Optional[Any] = None,
        title: str = "",
        min_size: Optional[Tuple[int, int]] = None,
        max_size: Optional[Tuple[int, int]] = None,
        size: Optional[Tuple[int, int]] = None,
        settings_key: Optional[str] = None,
        modal: bool = True,
        theme_manager: Optional[Any] = None,
        enable_theme_events: bool = True,
    ):
        """
        初始化对话框基类

        Args:
            parent: 父窗口组件
            title: 对话框标题
            min_size: 最小尺寸 (width, height)
            max_size: 最大尺寸 (width, height)
            size: 初始尺寸 (width, height)
            settings_key: QSettings 使用的键名，用于记忆窗口尺寸
            modal: 是否为模态对话框
            theme_manager: 主题管理器实例
            enable_theme_events: 是否启用主题事件订阅
        """
        super().__init__(parent)

        self.setAttribute(Qt.WA_DeleteOnClose)

        # 基本设置
        self._settings_key = settings_key
        self._theme_manager = theme_manager
        self._theme_event_connected = False
        self._loading_indicator = None

        # 设置窗口标题
        if title:
            self.setWindowTitle(title)

        # 设置模态
        self.setModal(modal)

        # 设置窗口标志
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint
        )

        # 设置尺寸
        if min_size:
            self.setMinimumSize(*min_size)
        if max_size:
            self.setMaximumSize(*max_size)
        if size:
            self.resize(*size)

        # 恢复窗口几何信息
        self.restore_geometry()

        # 连接主题切换
        self._connect_theme_support(enable_theme_events)

        # 记录日志
        logger.debug(f"BaseDialog 初始化: {self.windowTitle()}")

    def _connect_theme_support(self, enable_events: bool):
        """连接主题切换支持"""
        # 方式1: 通过主题管理器信号
        if self._theme_manager and hasattr(self._theme_manager, 'theme_changed'):
            try:
                self._theme_manager.theme_changed.connect(self._on_theme_changed_wrapper)
                logger.debug("主题管理器信号已连接")
            except Exception as e:
                logger.warning(f"连接主题管理器信号失败: {e}")

        # 方式2: 通过事件总线
        if enable_events and EVENT_BUS_AVAILABLE:
            try:
                event_bus = get_event_bus()
                if event_bus and ThemeChangedEvent:
                    event_bus.subscribe(ThemeChangedEvent, self._on_theme_changed_wrapper)
                    self._theme_event_connected = True
                    logger.debug("主题事件已订阅")
            except Exception as e:
                logger.warning(f"订阅主题事件失败: {e}")

    def _on_theme_changed_wrapper(self, *args, **kwargs):
        """主题变化包装器，兼容不同的调用方式"""
        try:
            self.on_theme_changed(*args, **kwargs)
        except Exception as e:
            logger.error(f"处理主题变化失败: {e}")

    def on_theme_changed(self, *args, **kwargs):
        """
        主题变化回调方法

        子类应重写此方法来处理主题切换逻辑。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数
        """
        logger.debug(f"主题变化通知: {self.windowTitle()}")

    def center_on_parent(self):
        """
        将对话框居中显示在父窗口或屏幕中央
        """
        frame_geometry = self.frameGeometry()

        if self.parent():
            # 获取父窗口的几何中心
            parent_center = self.parent().frameGeometry().center()
        else:
            # 获取屏幕中心
            screen_center = QApplication.desktop().availableGeometry().center()
            parent_center = screen_center

        # 移动对话框到中心位置
        frame_geometry.moveCenter(parent_center)
        self.move(frame_geometry.topLeft())

        logger.debug(f"对话框已居中: {self.windowTitle()}")

    def showEvent(self, event):
        """对话框显示事件"""
        super().showEvent(event)
        self.center_on_parent()

    def save_geometry(self):
        """
        保存窗口几何信息到 QSettings

        在对话框关闭时自动调用，下次打开时恢复。
        """
        if not self._settings_key:
            return

        try:
            settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
            settings.beginGroup(self._settings_key)

            settings.setValue("geometry", self.saveGeometry())
            # R247 修复: saveState 仅 QMainWindow 存在, QDialog 无此方法,
            # 直接调用会抛 AttributeError (被 except 吞掉仅产生 warning 噪音)。
            if hasattr(self, 'saveState'):
                settings.setValue("windowState", self.saveState())

            settings.endGroup()

            logger.debug(f"窗口几何信息已保存: {self._settings_key}")
        except Exception as e:
            logger.warning(f"保存窗口几何信息失败: {e}")

    def restore_geometry(self):
        """
        从 QSettings 恢复窗口几何信息

        在对话框初始化时调用。
        """
        if not self._settings_key:
            return

        try:
            settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
            settings.beginGroup(self._settings_key)

            geometry = settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
                logger.debug(f"窗口几何信息已恢复: {self._settings_key}")

            state = settings.value("windowState")
            if state:
                self.restoreState(state)

            settings.endGroup()
        except Exception as e:
            logger.warning(f"恢复窗口几何信息失败: {e}")

    def closeEvent(self, event):
        """对话框关闭事件"""
        # 保存窗口几何信息
        self.save_geometry()

        # 取消订阅主题事件
        if self._theme_event_connected and EVENT_BUS_AVAILABLE:
            try:
                event_bus = get_event_bus()
                if event_bus and ThemeChangedEvent:
                    event_bus.unsubscribe(ThemeChangedEvent, self._on_theme_changed_wrapper)
                    self._theme_event_connected = False
            except Exception as e:
                logger.warning(f"取消订阅主题事件失败: {e}")

        logger.debug(f"对话框已关闭: {self.windowTitle()}")
        super().closeEvent(event)
        event.accept()

    def reject(self):
        """重写 reject 方法，确保保存几何信息"""
        self.save_geometry()
        super().reject()

    def accept(self):
        """重写 accept 方法，确保保存几何信息"""
        self.save_geometry()
        super().accept()

    def add_shadow_effect(self, blur_radius: int = 32, x_offset: int = 0, y_offset: int = 12, alpha: int = 80):
        """
        添加阴影效果

        Args:
            blur_radius: 模糊半径
            x_offset: X轴偏移
            y_offset: Y轴偏移
            alpha: 透明度
        """
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(blur_radius)
            shadow.setXOffset(x_offset)
            shadow.setYOffset(y_offset)
            shadow.setColor(QColor(0, 0, 0, alpha))
            self.setGraphicsEffect(shadow)
        except Exception as e:
            logger.warning(f"添加阴影效果失败: {e}")

    def setup_loading_indicator(self, parent_layout: Optional[QVBoxLayout] = None):
        """
        设置加载状态指示器

        Args:
            parent_layout: 父布局，如果不提供则添加到主布局底部
        """
        self._loading_indicator = LoadingIndicator(self)
        self._loading_indicator.hide()

        if parent_layout:
            parent_layout.addWidget(self._loading_indicator)
        else:
            layout = self.layout()
            if layout and isinstance(layout, QVBoxLayout):
                layout.addWidget(self._loading_indicator)

    def show_loading(self, message: str = "加载中..."):
        """
        显示加载状态

        Args:
            message: 加载提示信息
        """
        if not self._loading_indicator:
            self.setup_loading_indicator()

        self._loading_indicator.show_message(message)
        QApplication.processEvents()
        logger.debug(f"显示加载状态: {message}")

    def hide_loading(self):
        """隐藏加载状态"""
        if self._loading_indicator:
            self._loading_indicator.hide_indicator()
            QApplication.processEvents()
            logger.debug("隐藏加载状态")

    def show_error(self, title: str, message: str):
        """
        显示错误提示对话框

        Args:
            title: 错误标题
            message: 错误信息
        """
        QMessageBox.critical(self, title, message)
        logger.error(f"错误对话框 [{title}]: {message}")

    def show_warning(self, title: str, message: str):
        """
        显示警告提示对话框

        Args:
            title: 警告标题
            message: 警告信息
        """
        QMessageBox.warning(self, title, message)
        logger.warning(f"警告对话框 [{title}]: {message}")

    def show_success(self, title: str, message: str):
        """
        显示成功提示对话框

        Args:
            title: 成功标题
            message: 成功信息
        """
        QMessageBox.information(self, title, message)
        logger.info(f"成功对话框 [{title}]: {message}")

    def show_info(self, title: str, message: str):
        """
        显示信息提示对话框

        Args:
            title: 信息标题
            message: 信息内容
        """
        QMessageBox.information(self, title, message)
        logger.info(f"信息对话框 [{title}]: {message}")

    def confirm(
        self,
        title: str,
        message: str,
        default_button: QMessageBox.StandardButton = QMessageBox.Yes
    ) -> bool:
        """
        显示确认对话框

        Args:
            title: 确认标题
            message: 确认信息
            default_button: 默认按钮

        Returns:
            bool: 用户是否确认
        """
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            default_button
        )
        result = reply == QMessageBox.Yes
        logger.debug(f"确认对话框 [{title}]: {'确认' if result else '取消'}")
        return result

    def set_theme_style(self, is_dark: bool):
        """
        根据主题设置应用样式

        子类可以重写此方法来应用自定义的样式。

        Args:
            is_dark: 是否为深色主题
        """
        pass

    def get_theme_colors(self) -> dict:
        """
        获取当前主题的颜色配置

        Returns:
            dict: 颜色配置字典
        """
        if self._theme_manager:
            try:
                current_theme = self._theme_manager.get_current_theme()
                if current_theme:
                    return current_theme.colors
            except Exception as e:
                logger.warning(f"获取主题颜色失败: {e}")
        return {}
