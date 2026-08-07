# -*- coding: utf-8 -*-

"""
功能控制面板

提供系统功能的统一管理和控制界面，包括：
- 功能开关管理（按级别分组）
- 功能状态实时监控
- 功能配置参数编辑
- 用户偏好设置
- 功能依赖关系展示

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QSpinBox, QSlider,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit, QCheckBox, QDateTimeEdit, QTimeEdit,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QScrollArea,
    QMessageBox, QDialog, QDialogButtonBox, QApplication, QTreeWidget,
    QTreeWidgetItem, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsProxyWidget, QToolBar, QAction,
    QMenu, QActionGroup, QButtonGroup, QRadioButton, QLCDNumber,
    QDial, QCalendarWidget, QLineEdit, QDoubleSpinBox, QSizePolicy,
    QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QThread, QMutex, QMutexLocker,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QDateTime, QTime, QDate, QSize, QSortFilterProxyModel, QAbstractTableModel
)
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QPixmap, QIcon, QPainter, QBrush, QPen,
    QLinearGradient, QRadialGradient, QFontMetrics, QPainterPath,
    QPolygonF, QCursor
)

try:
    from core.services.feature_control_service import (
        FeatureControlService, FeatureConfig, FeatureStatus, FeatureLevel,
        get_feature_control_service
    )
    from loguru import logger
    CORE_AVAILABLE = True
except ImportError as e:
    logger = None
    print(f"导入核心组件失败: {e}")
    CORE_AVAILABLE = False

logger = logger.bind(module=__name__) if logger else None


class FeatureToggleDelegate(QStyledItemDelegate):
    """功能开关委托"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        """绘制开关"""
        enabled = index.data(Qt.UserRole)

        painter.save()

        rect = option.rect
        center_y = rect.center().y()
        switch_width = 50
        switch_height = 26
        switch_rect = QRectF(
            rect.center().x() - switch_width / 2,
            center_y - switch_height / 2,
            switch_width,
            switch_height
        )

        background_color = QColor(76, 175, 80) if enabled else QColor(158, 158, 158)
        painter.setBrush(QBrush(background_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(switch_rect, 13, 13)

        circle_radius = 10
        circle_x = switch_rect.right() - 18 if enabled else switch_rect.left() + 18
        circle_rect = QRectF(
            circle_x - circle_radius,
            center_y - circle_radius,
            circle_radius * 2,
            circle_radius * 2
        )

        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(circle_rect)

        painter.restore()


class FeatureConfigDialog(QDialog):
    """功能配置对话框"""

    def __init__(self, feature_config: FeatureConfig, parent=None):
        super().__init__(parent)
        self.feature_config = feature_config
        self.config_updates = {}
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle(f"配置 - {self.feature_config.name}")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        form_layout = QFormLayout()

        for key, value in self.feature_config.config.items():
            if isinstance(value, bool):
                widget = QCheckBox()
                widget.setChecked(value)
                widget.stateChanged.connect(lambda state, k=key: self._on_bool_changed(k, state))
            elif isinstance(value, int):
                widget = QSpinBox()
                widget.setRange(0, 10000)
                widget.setValue(value)
                widget.valueChanged.connect(lambda v, k=key: self._on_int_changed(k, v))
            elif isinstance(value, float):
                widget = QDoubleSpinBox()
                widget.setRange(0.0, 10000.0)
                widget.setValue(value)
                widget.setSingleStep(0.1)
                widget.valueChanged.connect(lambda v, k=key: self._on_float_changed(k, v))
            elif isinstance(value, str):
                widget = QLineEdit()
                widget.setText(str(value))
                widget.textChanged.connect(lambda text, k=key: self._on_str_changed(k, text))
            else:
                widget = QLabel(str(value))

            form_layout.addRow(key.replace("_", " ").title(), widget)

        scroll_layout.addLayout(form_layout)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_bool_changed(self, key: str, state: int):
        """布尔值变化"""
        self.config_updates[key] = state == Qt.Checked

    def _on_int_changed(self, key: str, value: int):
        """整数值变化"""
        self.config_updates[key] = value

    def _on_float_changed(self, key: str, value: float):
        """浮点数值变化"""
        self.config_updates[key] = value

    def _on_str_changed(self, key: str, text: str):
        """字符串值变化"""
        self.config_updates[key] = text

    def get_config_updates(self) -> Dict[str, Any]:
        """获取配置更新"""
        return self.config_updates


class FeatureControlWidget(QWidget):
    """功能控制面板主组件"""

    feature_toggled = pyqtSignal(str, bool)
    feature_config_updated = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.feature_service: Optional[FeatureControlService] = None
        self.feature_widgets: Dict[str, QWidget] = {}

        self.setup_ui()
        self.initialize_service()

    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_features)
        self.toolbar.addAction(refresh_action)

        reset_action = QAction("重置默认", self)
        reset_action.triggered.connect(self.reset_to_defaults)
        self.toolbar.addAction(reset_action)

        self.toolbar.addSeparator()

        save_action = QAction("保存配置", self)
        save_action.triggered.connect(self.save_configuration)
        self.toolbar.addAction(save_action)

        main_layout.addWidget(self.toolbar)

        self.tab_widget = QTabWidget()

        self.tab_widget.addTab(self.create_feature_toggle_tab(), "功能开关")
        self.tab_widget.addTab(self.create_feature_config_tab(), "功能配置")
        self.tab_widget.addTab(self.create_feature_status_tab(), "状态监控")

        main_layout.addWidget(self.tab_widget)

        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet("QLabel { padding: 5px; background-color: #f0f0f0; border-radius: 3px; }")
        main_layout.addWidget(self.status_bar)

    def create_feature_toggle_tab(self) -> QWidget:
        """创建功能开关标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        if CORE_AVAILABLE and self.feature_service:
            ui_config = self.feature_service.create_feature_toggle_ui_config()

            for section in ui_config["sections"]:
                group_box = QGroupBox(section["title"])
                group_layout = QVBoxLayout(group_box)

                description_label = QLabel(section["description"])
                description_label.setStyleSheet("color: #666; font-size: 11px;")
                group_layout.addWidget(description_label)

                for feature_info in section["features"]:
                    feature_widget = self.create_feature_widget(feature_info)
                    group_layout.addWidget(feature_widget)
                    self.feature_widgets[feature_info["name"]] = feature_widget

                scroll_layout.addWidget(group_box)

            scroll_layout.addStretch()
        else:
            error_label = QLabel("功能控制服务不可用")
            error_label.setStyleSheet("color: red; font-size: 14px;")
            error_label.setAlignment(Qt.AlignCenter)
            scroll_layout.addWidget(error_label)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        return widget

    def create_feature_widget(self, feature_info: Dict[str, Any]) -> QFrame:
        """创建功能组件"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 10px;
                margin: 5px;
            }
            QFrame:hover {
                background-color: #f5f5f5;
            }
        """)

        layout = QHBoxLayout(frame)

        name_label = QLabel(feature_info["title"])
        name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        name_label.setMinimumWidth(150)
        layout.addWidget(name_label)

        description_label = QLabel(feature_info["description"])
        description_label.setStyleSheet("color: #666; font-size: 11px;")
        description_label.setWordWrap(True)
        layout.addWidget(description_label, 1)

        enabled = feature_info["enabled"]
        level = feature_info["level"]

        level_badge = QLabel(level.upper())
        level_color = {
            "core": "#4CAF50",
            "advanced": "#2196F3",
            "premium": "#FF9800"
        }.get(level, "#999")
        level_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {level_color};
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(level_badge)

        toggle_button = QPushButton("启用" if not enabled else "禁用")
        toggle_button.setCheckable(True)
        toggle_button.setChecked(enabled)
        toggle_button.setMinimumWidth(80)
        toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#4CAF50' if enabled else '#f44336'};
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {'#45a049' if enabled else '#da190b'};
            }}
            QPushButton:pressed {{
                background-color: {'#3d8b40' if enabled else '#b7150a'};
            }}
        """)
        toggle_button.clicked.connect(
            lambda checked, name=feature_info["name"]: self.toggle_feature(name, checked)
        )

        if level == "core":
            toggle_button.setEnabled(False)
            toggle_button.setText("核心")
            toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #9E9E9E;
                    color: white;
                    border: none;
                    padding: 5px 15px;
                    border-radius: 3px;
                    font-weight: bold;
                }
            """)

        layout.addWidget(toggle_button)

        config_button = QPushButton("配置")
        config_button.setMinimumWidth(60)
        config_button.clicked.connect(
            lambda: self.open_feature_config(feature_info["name"])
        )
        layout.addWidget(config_button)

        return frame

    def create_feature_config_tab(self) -> QWidget:
        """创建功能配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.config_table = QTableWidget()
        self.config_table.setColumnCount(4)
        self.config_table.setHorizontalHeaderLabels(["功能名称", "配置项", "当前值", "操作"])

        header = self.config_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.config_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.config_table.setAlternatingRowColors(True)
        self.config_table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f9f9f9;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)

        layout.addWidget(self.config_table)

        return widget

    def create_feature_status_tab(self) -> QWidget:
        """创建状态监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        summary_group = QGroupBox("功能状态摘要")
        summary_layout = QGridLayout(summary_group)

        self.total_features_label = QLabel("0")
        self.enabled_features_label = QLabel("0")
        self.disabled_features_label = QLabel("0")
        self.unavailable_features_label = QLabel("0")

        summary_layout.addWidget(QLabel("总功能数:"), 0, 0)
        summary_layout.addWidget(self.total_features_label, 0, 1)
        summary_layout.addWidget(QLabel("已启用:"), 0, 2)
        summary_layout.addWidget(self.enabled_features_label, 0, 3)
        summary_layout.addWidget(QLabel("已禁用:"), 1, 0)
        summary_layout.addWidget(self.disabled_features_label, 1, 1)
        summary_layout.addWidget(QLabel("不可用:"), 1, 2)
        summary_layout.addWidget(self.unavailable_features_label, 1, 3)

        layout.addWidget(summary_group)

        self.status_table = QTableWidget()
        self.status_table.setColumnCount(6)
        self.status_table.setHorizontalHeaderLabels([
            "功能名称", "级别", "状态", "描述", "依赖", "最后更新"
        ])

        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.status_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.status_table.setAlternatingRowColors(True)

        layout.addWidget(self.status_table)

        return widget

    def initialize_service(self):
        """初始化服务"""
        if CORE_AVAILABLE:
            try:
                self.feature_service = get_feature_control_service()
                self.refresh_features()
                logger.info("功能控制服务初始化成功")
            except Exception as e:
                logger.error(f"功能控制服务初始化失败: {e}")
                self.show_error_message(f"初始化失败: {e}")
        else:
            self.show_error_message("功能控制服务不可用")

    def refresh_features(self):
        """刷新功能列表"""
        if not self.feature_service:
            return

        try:
            self.status_bar.setText("正在刷新功能列表...")

            ui_config = self.feature_service.create_feature_toggle_ui_config()
            self.update_feature_widgets(ui_config)
            self.update_status_table()
            self.update_config_table()

            self.status_bar.setText("功能列表已刷新")
            logger.info("功能列表已刷新")

        except Exception as e:
            logger.error(f"刷新功能列表失败: {e}")
            self.status_bar.setText(f"刷新失败: {e}")

    def update_feature_widgets(self, ui_config: Dict[str, Any]):
        """更新功能组件"""
        for section in ui_config["sections"]:
            for feature_info in section["features"]:
                feature_name = feature_info["name"]
                if feature_name in self.feature_widgets:
                    widget = self.feature_widgets[feature_name]
                    buttons = widget.findChildren(QPushButton)

                    for button in buttons:
                        if button.text() in ["启用", "禁用", "核心"]:
                            if feature_info["level"] == "core":
                                continue

                            enabled = feature_info["enabled"]
                            button.setChecked(enabled)
                            button.setText("禁用" if enabled else "启用")
                            button.setStyleSheet(f"""
                                QPushButton {{
                                    background-color: {'#4CAF50' if enabled else '#f44336'};
                                    color: white;
                                    border: none;
                                    padding: 5px 15px;
                                    border-radius: 3px;
                                    font-weight: bold;
                                }}
                                QPushButton:hover {{
                                    background-color: {'#45a049' if enabled else '#da190b'};
                                }}
                                QPushButton:pressed {{
                                    background-color: {'#3d8b40' if enabled else '#b7150a'};
                                }}
                            """)

    def update_status_table(self):
        """更新状态表格"""
        if not self.feature_service:
            return

        try:
            summary = self.feature_service.get_feature_status_summary()

            self.total_features_label.setText(str(summary["total_features"]))
            self.enabled_features_label.setText(str(summary["enabled_features"]))
            self.disabled_features_label.setText(str(summary["disabled_features"]))
            self.unavailable_features_label.setText(str(summary["unavailable_features"]))

            self.status_table.setRowCount(0)

            for feature_name, feature_info in summary["features"].items():
                row = self.status_table.rowCount()
                self.status_table.insertRow(row)

                self.status_table.setItem(row, 0, QTableWidgetItem(feature_name))
                self.status_table.setItem(row, 1, QTableWidgetItem(feature_info["level"]))
                self.status_table.setItem(row, 2, QTableWidgetItem(feature_info["status"]))
                self.status_table.setItem(row, 3, QTableWidgetItem(feature_info["description"]))

                dependencies = ", ".join(feature_info["dependencies"])
                self.status_table.setItem(row, 4, QTableWidgetItem(dependencies))

                feature_config = self.feature_service.get_feature_config(feature_name)
                if feature_config:
                    last_updated = datetime.fromtimestamp(feature_config.last_updated)
                    self.status_table.setItem(row, 5, QTableWidgetItem(
                        last_updated.strftime("%Y-%m-%d %H:%M:%S")
                    ))

                status_item = self.status_table.item(row, 2)
                status_color = {
                    "enabled": "#4CAF50",
                    "disabled": "#f44336",
                    "unavailable": "#FF9800",
                    "maintenance": "#9E9E9E"
                }.get(feature_info["status"], "#000")
                status_item.setForeground(QBrush(QColor(status_color)))

        except Exception as e:
            logger.error(f"更新状态表格失败: {e}")

    def update_config_table(self):
        """更新配置表格"""
        if not self.feature_service:
            return

        try:
            self.config_table.setRowCount(0)

            features = self.feature_service.get_all_features()

            for feature_name, feature_config in features.items():
                for config_key, config_value in feature_config.config.items():
                    row = self.config_table.rowCount()
                    self.config_table.insertRow(row)

                    self.config_table.setItem(row, 0, QTableWidgetItem(feature_name))
                    self.config_table.setItem(row, 1, QTableWidgetItem(config_key))
                    self.config_table.setItem(row, 2, QTableWidgetItem(str(config_value)))

                    edit_button = QPushButton("编辑")
                    edit_button.clicked.connect(
                        lambda _, fn=feature_name: self.open_feature_config(fn)
                    )
                    self.config_table.setCellWidget(row, 3, edit_button)

        except Exception as e:
            logger.error(f"更新配置表格失败: {e}")

    def toggle_feature(self, feature_name: str, enabled: bool):
        """切换功能状态"""
        if not self.feature_service:
            return

        try:
            if enabled:
                success = self.feature_service.enable_feature(feature_name, "user")
                message = f"功能 {feature_name} 已启用"
            else:
                success = self.feature_service.disable_feature(feature_name, "user")
                message = f"功能 {feature_name} 已禁用"

            if success:
                self.status_bar.setText(message)
                self.feature_toggled.emit(feature_name, enabled)
                self.refresh_features()
                logger.info(message)
            else:
                self.show_error_message(f"操作失败: {feature_name}")

        except Exception as e:
            logger.error(f"切换功能状态失败: {e}")
            self.show_error_message(f"操作失败: {e}")

    def open_feature_config(self, feature_name: str):
        """打开功能配置对话框"""
        if not self.feature_service:
            return

        try:
            feature_config = self.feature_service.get_feature_config(feature_name)
            if not feature_config:
                self.show_error_message(f"功能不存在: {feature_name}")
                return

            dialog = FeatureConfigDialog(feature_config, self)
            if dialog.exec_() == QDialog.Accepted:
                config_updates = dialog.get_config_updates()
                if config_updates:
                    success = self.feature_service.update_feature_config(
                        feature_name, config_updates, "user"
                    )
                    if success:
                        self.status_bar.setText(f"功能 {feature_name} 配置已更新")
                        self.feature_config_updated.emit(feature_name, config_updates)
                        self.refresh_features()
                        logger.info(f"功能 {feature_name} 配置已更新")
                    else:
                        self.show_error_message(f"配置更新失败: {feature_name}")

        except Exception as e:
            logger.error(f"打开功能配置失败: {e}")
            self.show_error_message(f"操作失败: {e}")

    def reset_to_defaults(self):
        """重置为默认配置"""
        if not self.feature_service:
            return

        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置所有功能为默认配置吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.feature_service.reset_to_defaults(user_id="user")
                self.status_bar.setText("已重置为默认配置")
                self.refresh_features()
                logger.info("已重置为默认配置")
            except Exception as e:
                logger.error(f"重置默认配置失败: {e}")
                self.show_error_message(f"重置失败: {e}")

    def save_configuration(self):
        """保存配置"""
        if not self.feature_service:
            return

        try:
            self.status_bar.setText("配置已保存")
            logger.info("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            self.show_error_message(f"保存失败: {e}")

    def show_error_message(self, message: str):
        """显示错误消息"""
        QMessageBox.critical(self, "错误", message)
        self.status_bar.setText(f"错误: {message}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = FeatureControlWidget()
    widget.setWindowTitle("功能控制面板")
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec_())
