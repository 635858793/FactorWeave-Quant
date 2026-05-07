#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能提醒UI组件
显示聚合交易信号和智能提醒
"""

from loguru import logger

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea, QPushButton, QProgressBar,
                             QGroupBox, QGridLayout, QTextEdit, QTabWidget,
                             QToolButton, QMenu, QAction, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QRect
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from .signal_aggregator import AggregatedAlert, TradingSignal, AlertLevel, SignalStrength


class AlertCard(QFrame):
    """单个警报卡片组件"""

    clicked = pyqtSignal(AggregatedAlert)
    dismissed = pyqtSignal(str)  # alert_id

    def __init__(self, alert: AggregatedAlert, parent=None):
        super().__init__(parent)
        self.alert = alert
        self.is_expanded = False
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setFrameStyle(QFrame.StyledPanel)
        self.setMaximumHeight(120)
        self.setCursor(Qt.PointingHandCursor)

        # 设置样式
        self.update_style()

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 头部布局
        header_layout = QHBoxLayout()

        # 警报图标和标题
        icon_label = QLabel(self._get_alert_icon())
        icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        icon_label.setMinimumSize(24, 24)
        icon_label.setMaximumSize(24, 24)
        icon_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel(self.alert.title)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)

        # 置信度显示
        confidence_label = QLabel(f"{self.alert.overall_confidence:.0%}")
        confidence_font = QFont()
        confidence_font.setPointSize(9)
        confidence_font.setBold(True)
        confidence_label.setFont(confidence_font)
        confidence_label.setStyleSheet(f"color: {self._get_confidence_color()};")

        # 时间标签
        time_label = QLabel(self._format_time())
        time_label.setStyleSheet("color: #7f8c8d; font-size: 8pt;")

        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        close_btn.setMinimumSize(20, 20)
        close_btn.setMaximumSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #95a5a6;
                font-weight: bold;
                font-size: 12pt;
            }
            QPushButton:hover {
                background: #ecf0f1;
                color: #e74c3c;
            }
        """)
        close_btn.clicked.connect(lambda: self.dismissed.emit(self.alert.alert_id))

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(confidence_label)
        header_layout.addWidget(time_label)
        header_layout.addWidget(close_btn)

        # 消息内容
        message_label = QLabel(self.alert.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #2c3e50; font-size: 9pt;")

        # 信号计数
        signal_count_label = QLabel(f"基于 {len(self.alert.signals)} 个信号")
        signal_count_label.setStyleSheet("color: #7f8c8d; font-size: 8pt; font-style: italic;")

        # 置信度进度条
        confidence_bar = QProgressBar()
        confidence_bar.setMaximum(100)
        confidence_bar.setValue(int(self.alert.overall_confidence * 100))
        confidence_bar.setMaximumHeight(4)
        confidence_bar.setTextVisible(False)
        confidence_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: #ecf0f1;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {self._get_confidence_color()};
                border-radius: 2px;
            }}
        """)

        layout.addLayout(header_layout)
        layout.addWidget(message_label)
        layout.addWidget(signal_count_label)
        layout.addWidget(confidence_bar)

        self.setLayout(layout)

    def _get_alert_icon(self) -> str:
        """获取警报图标"""
        icons = {
            AlertLevel.SUCCESS: "",
            AlertLevel.WARNING: "",
            AlertLevel.DANGER: "",
            AlertLevel.INFO: "ℹ"
        }
        return icons.get(self.alert.level, "ℹ")

    def _get_confidence_color(self) -> str:
        """获取置信度颜色"""
        if self.alert.overall_confidence >= 0.8:
            return "#27ae60"  # 绿色
        elif self.alert.overall_confidence >= 0.6:
            return "#f39c12"  # 橙色
        else:
            return "#e74c3c"  # 红色

    def _format_time(self) -> str:
        """格式化时间显示"""
        now = datetime.now()
        diff = now - self.alert.timestamp

        if diff.seconds < 60:
            return "刚刚"
        elif diff.seconds < 3600:
            return f"{diff.seconds // 60}分钟前"
        elif diff.days == 0:
            return f"{diff.seconds // 3600}小时前"
        else:
            return f"{diff.days}天前"

    def update_style(self):
        """更新样式"""
        colors = {
            AlertLevel.SUCCESS: "#d5f4e6",
            AlertLevel.WARNING: "#fff3cd",
            AlertLevel.DANGER: "#f8d7da",
            AlertLevel.INFO: "#d4edda"
        }

        border_colors = {
            AlertLevel.SUCCESS: "#27ae60",
            AlertLevel.WARNING: "#f39c12",
            AlertLevel.DANGER: "#e74c3c",
            AlertLevel.INFO: "#3498db"
        }

        bg_color = colors.get(self.alert.level, "#ecf0f1")
        border_color = border_colors.get(self.alert.level, "#bdc3c7")

        self.setStyleSheet(f"""
            AlertCard {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 8px;
                margin: 2px;
            }}
            AlertCard:hover {{
                border-color: {border_color};
                background-color: {bg_color};
            }}
        """)

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.alert)
        super().mousePressEvent(event)


class SignalDetailDialog(QWidget):
    """信号详情对话框"""

    def __init__(self, alert: AggregatedAlert, parent=None):
        super().__init__(parent)
        self.alert = alert
        self.setWindowTitle(f"信号详情 - {alert.title}")
        self.setFixedSize(600, 400)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题
        title_label = QLabel(self.alert.title)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)

        # 信息标签页
        tab_widget = QTabWidget()

        # 概览标签页
        overview_widget = self._create_overview_tab()
        tab_widget.addTab(overview_widget, "概览")

        # 信号详情标签页
        signals_widget = self._create_signals_tab()
        tab_widget.addTab(signals_widget, "信号详情")

        # 建议标签页
        recommendation_widget = self._create_recommendation_tab()
        tab_widget.addTab(recommendation_widget, "操作建议")

        layout.addWidget(title_label)
        layout.addWidget(tab_widget)

        self.setLayout(layout)

    def _create_overview_tab(self) -> QWidget:
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("警报级别:"), 0, 0)
        level_label = QLabel(self.alert.level.value.upper())
        level_label.setStyleSheet(f"font-weight: bold; color: {self._get_level_color()};")
        info_layout.addWidget(level_label, 0, 1)

        info_layout.addWidget(QLabel("置信度:"), 1, 0)
        confidence_label = QLabel(f"{self.alert.overall_confidence:.1%}")
        info_layout.addWidget(confidence_label, 1, 1)

        info_layout.addWidget(QLabel("信号数量:"), 2, 0)
        count_label = QLabel(str(len(self.alert.signals)))
        info_layout.addWidget(count_label, 2, 1)

        info_layout.addWidget(QLabel("生成时间:"), 3, 0)
        time_label = QLabel(self.alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        info_layout.addWidget(time_label, 3, 1)

        info_group.setLayout(info_layout)

        # 消息内容
        message_group = QGroupBox("详细信息")
        message_layout = QVBoxLayout()
        message_text = QTextEdit()
        message_text.setPlainText(self.alert.message)
        message_text.setMaximumHeight(100)
        message_text.setReadOnly(True)
        message_layout.addWidget(message_text)
        message_group.setLayout(message_layout)

        layout.addWidget(info_group)
        layout.addWidget(message_group)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_signals_tab(self) -> QWidget:
        """创建信号详情标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        for i, signal in enumerate(self.alert.signals):
            signal_group = QGroupBox(f"信号 {i+1}: {signal.message}")
            signal_layout = QGridLayout()

            signal_layout.addWidget(QLabel("类型:"), 0, 0)
            signal_layout.addWidget(QLabel(signal.signal_type.value), 0, 1)

            signal_layout.addWidget(QLabel("方向:"), 1, 0)
            direction_label = QLabel(signal.direction.upper())
            direction_color = "#FF0000" if signal.direction == "buy" else "#00FF00"
            direction_label.setStyleSheet(f"color: {direction_color}; font-weight: bold;")
            signal_layout.addWidget(direction_label, 1, 1)

            signal_layout.addWidget(QLabel("强度:"), 2, 0)
            strength_label = QLabel(f"{signal.strength.value}/5")
            signal_layout.addWidget(strength_label, 2, 1)

            signal_layout.addWidget(QLabel("置信度:"), 3, 0)
            signal_layout.addWidget(QLabel(f"{signal.confidence:.1%}"), 3, 1)

            signal_layout.addWidget(QLabel("时间:"), 4, 0)
            signal_layout.addWidget(QLabel(signal.timestamp.strftime("%H:%M:%S")), 4, 1)

            signal_group.setLayout(signal_layout)
            scroll_layout.addWidget(signal_group)

        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)
        widget.setLayout(layout)
        return widget

    def _create_recommendation_tab(self) -> QWidget:
        """创建操作建议标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 主要建议
        main_recommendation = QGroupBox("主要建议")
        main_layout = QVBoxLayout()

        recommendation_label = QLabel(self.alert.recommended_action)
        recommendation_label.setWordWrap(True)
        recommendation_font = QFont()
        recommendation_font.setPointSize(12)
        recommendation_font.setBold(True)
        recommendation_label.setFont(recommendation_font)
        recommendation_label.setStyleSheet("color: #2c3e50; padding: 10px;")

        main_layout.addWidget(recommendation_label)
        main_recommendation.setLayout(main_layout)

        # 风险提示
        risk_group = QGroupBox("风险提示")
        risk_layout = QVBoxLayout()

        risk_text = QTextEdit()
        risk_content = self._generate_risk_warning()
        risk_text.setPlainText(risk_content)
        risk_text.setMaximumHeight(150)
        risk_text.setReadOnly(True)

        risk_layout.addWidget(risk_text)
        risk_group.setLayout(risk_layout)

        layout.addWidget(main_recommendation)
        layout.addWidget(risk_group)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _get_level_color(self) -> str:
        """获取级别颜色"""
        colors = {
            AlertLevel.SUCCESS: "#27ae60",
            AlertLevel.WARNING: "#f39c12",
            AlertLevel.DANGER: "#e74c3c",
            AlertLevel.INFO: "#3498db"
        }
        return colors.get(self.alert.level, "#3498db")

    def _generate_risk_warning(self) -> str:
        """生成风险警告内容"""
        base_warning = "请注意：\n1. 所有交易信号仅供参考，不构成投资建议\n2. 市场存在风险，投资需谨慎\n3. 建议结合其他分析方法进行决策\n"

        if self.alert.overall_confidence < 0.6:
            base_warning += "4. 当前信号置信度较低，建议谨慎操作\n"

        if len(self.alert.signals) < 3:
            base_warning += "5. 信号数量较少，建议等待更多确认\n"

        return base_warning


class SmartAlertWidget(QWidget):
    """智能提醒主组件"""

    # 信号
    alert_clicked = pyqtSignal(AggregatedAlert)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.alerts: List[AggregatedAlert] = []
        self.max_alerts = 20  # 最多显示20个警报
        self.alert_channels_status = {
            'email': {'enabled': False, 'status': 'unknown', 'name': '邮件'},
            'sms': {'enabled': False, 'status': 'unknown', 'name': '短信'},
            'webhook': {'enabled': False, 'status': 'unknown', 'name': 'Webhook'},
            'dingtalk': {'enabled': False, 'status': 'unknown', 'name': '钉钉'}
        }
        self.init_ui()

        # 自动清理定时器
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_expired_alerts)
        self.cleanup_timer.start(60000)  # 每分钟检查一次

        # 外部告警渠道状态检查定时器
        self.channel_status_timer = QTimer()
        self.channel_status_timer.timeout.connect(self._check_channel_status)
        self.channel_status_timer.start(30000)  # 每30秒检查一次

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 标题栏
        header_layout = QHBoxLayout()

        title_label = QLabel("智能交易提醒")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")

        # 外部告警渠道状态按钮
        self.channel_status_btn = QToolButton()
        self.channel_status_btn.setText("🔔")
        self.channel_status_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.channel_status_btn.setMinimumSize(30, 30)
        self.channel_status_btn.setMaximumSize(30, 30)
        self.channel_status_btn.setToolTip("外部告警渠道状态")
        self.channel_status_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-size: 16px;
            }
            QToolButton:hover {
                background: #ecf0f1;
                border-radius: 15px;
            }
        """)
        self.channel_status_btn.clicked.connect(self._show_channel_status_menu)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.channel_status_btn)

        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setFixedSize(50, 25)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        clear_btn.clicked.connect(self.clear_all_alerts)

        header_layout.addWidget(clear_btn)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setSpacing(3)
        self.scroll_layout.addStretch()  # 添加弹性空间，让警报从顶部开始

        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(400)

        # 状态标签
        self.status_label = QLabel("等待交易信号...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #7f8c8d; font-style: italic; padding: 20px;")

        layout.addLayout(header_layout)
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.setMaximumWidth(350)

    def add_alert(self, alert: AggregatedAlert):
        """添加新警报"""
        # 检查是否已存在相同警报
        if any(a.alert_id == alert.alert_id for a in self.alerts):
            return

        self.alerts.insert(0, alert)  # 新警报插入到顶部

        # 限制警报数量
        if len(self.alerts) > self.max_alerts:
            removed_alert = self.alerts.pop()
            self._remove_alert_widget(removed_alert.alert_id)

        # 创建警报卡片
        alert_card = AlertCard(alert)
        alert_card.clicked.connect(self._show_alert_detail)
        alert_card.dismissed.connect(self._remove_alert)

        # 插入到布局顶部（弹性空间之前）
        self.scroll_layout.insertWidget(0, alert_card)

        # 更新状态
        self._update_status()

        # 滚动到顶部显示新警报
        self.scroll_area.verticalScrollBar().setValue(0)

    def _show_alert_detail(self, alert: AggregatedAlert):
        """显示警报详情"""
        self.alert_clicked.emit(alert)

        # 创建并显示详情对话框
        detail_dialog = SignalDetailDialog(alert, self)
        detail_dialog.show()

    def _remove_alert(self, alert_id: str):
        """移除指定警报"""
        self.alerts = [a for a in self.alerts if a.alert_id != alert_id]
        self._remove_alert_widget(alert_id)
        self._update_status()

    def _remove_alert_widget(self, alert_id: str):
        """移除警报Widget"""
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, AlertCard) and widget.alert.alert_id == alert_id:
                    widget.deleteLater()
                    break

    def clear_all_alerts(self):
        """清空所有警报"""
        self.alerts.clear()

        # 移除所有警报卡片
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), AlertCard):
                item.widget().deleteLater()

        self._update_status()

    def _cleanup_expired_alerts(self):
        """清理过期警报"""
        current_time = datetime.now()
        expired_alerts = []

        for alert in self.alerts:
            # 清理超过1小时的INFO级别警报
            if (alert.level == AlertLevel.INFO and
                    (current_time - alert.timestamp).seconds > 3600):
                expired_alerts.append(alert.alert_id)
            # 清理超过4小时的其他警报
            elif (current_time - alert.timestamp).seconds > 14400:
                expired_alerts.append(alert.alert_id)

        for alert_id in expired_alerts:
            self._remove_alert(alert_id)

    def _update_status(self):
        """更新状态显示"""
        if not self.alerts:
            self.status_label.setText("等待交易信号...")
            self.status_label.show()
        else:
            self.status_label.hide()

    def get_alert_summary(self) -> Dict[str, Any]:
        """获取警报摘要"""
        if not self.alerts:
            return {"total": 0}

        recent_alerts = [a for a in self.alerts if
                         (datetime.now() - a.timestamp).seconds < 3600]

        return {
            "total": len(self.alerts),
            "recent": len(recent_alerts),
            "by_level": {
                level.value: len([a for a in recent_alerts if a.level == level])
                for level in AlertLevel
            },
            "avg_confidence": sum(a.overall_confidence for a in recent_alerts) / len(recent_alerts) if recent_alerts else 0
        }

    def _show_channel_status_menu(self):
        """显示外部告警渠道状态菜单"""
        menu = QMenu(self)

        menu.setTitle("外部告警渠道状态")

        for channel_id, channel_info in self.alert_channels_status.items():
            action = QAction(menu)
            status_text = self._get_channel_status_text(channel_info['status'])
            action.setText(f"{channel_info['name']}: {status_text}")
            action.setEnabled(channel_info['enabled'])

            # 设置状态图标
            if channel_info['status'] == 'ok':
                action.setIcon(QIcon.fromTheme("dialog-ok"))
            elif channel_info['status'] == 'error':
                action.setIcon(QIcon.fromTheme("dialog-error"))
            elif channel_info['status'] == 'unknown':
                action.setIcon(QIcon.fromTheme("dialog-question"))

            menu.addAction(action)

        menu.addSeparator()

        config_action = QAction("配置告警渠道", menu)
        config_action.triggered.connect(self._open_channel_config)
        menu.addAction(config_action)

        self.channel_status_btn.setMenu(menu)
        menu.popup(self.channel_status_btn.mapToGlobal(
            self.channel_status_btn.rect().bottomLeft()
        ))

    def _get_channel_status_text(self, status: str) -> str:
        """获取渠道状态文本"""
        status_map = {
            'ok': '正常',
            'error': '异常',
            'unknown': '未知',
            'disabled': '未启用'
        }
        return status_map.get(status, '未知')

    def _check_channel_status(self):
        """检查外部告警渠道状态"""
        try:
            from core.services.external_alert_channels_service import get_alert_manager

            alert_manager = get_alert_manager()

            # 检查邮件渠道
            self.alert_channels_status['email']['enabled'] = alert_manager.is_channel_enabled('email')
            if self.alert_channels_status['email']['enabled']:
                self.alert_channels_status['email']['status'] = 'ok'
            else:
                self.alert_channels_status['email']['status'] = 'disabled'

            # 检查短信渠道
            self.alert_channels_status['sms']['enabled'] = alert_manager.is_channel_enabled('sms')
            if self.alert_channels_status['sms']['enabled']:
                self.alert_channels_status['sms']['status'] = 'ok'
            else:
                self.alert_channels_status['sms']['status'] = 'disabled'

            # 检查Webhook渠道
            self.alert_channels_status['webhook']['enabled'] = alert_manager.is_channel_enabled('webhook')
            if self.alert_channels_status['webhook']['enabled']:
                self.alert_channels_status['webhook']['status'] = 'ok'
            else:
                self.alert_channels_status['webhook']['status'] = 'disabled'

            # 检查钉钉渠道
            self.alert_channels_status['dingtalk']['enabled'] = alert_manager.is_channel_enabled('dingtalk')
            if self.alert_channels_status['dingtalk']['enabled']:
                self.alert_channels_status['dingtalk']['status'] = 'ok'
            else:
                self.alert_channels_status['dingtalk']['status'] = 'disabled'

        except Exception as e:
            logger.error(f"检查外部告警渠道状态失败: {e}")
            for channel_id in self.alert_channels_status:
                self.alert_channels_status[channel_id]['status'] = 'error'

    def _open_channel_config(self):
        """打开外部告警渠道配置对话框"""
        try:
            from gui.dialogs.external_alert_channel_config_dialog import ExternalAlertChannelManagerDialog

            dialog = ExternalAlertChannelManagerDialog(self)
            dialog.exec_()

            # 重新检查渠道状态
            self._check_channel_status()

        except Exception as e:
            logger.error(f"打开外部告警渠道配置对话框失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "错误",
                f"打开外部告警渠道配置对话框失败: {e}"
            )

    def update_channel_status(self, channel_id: str, status: str, enabled: bool):
        """
        更新外部告警渠道状态

        Args:
            channel_id: 渠道ID
            status: 状态 ('ok', 'error', 'unknown', 'disabled')
            enabled: 是否启用
        """
        if channel_id in self.alert_channels_status:
            self.alert_channels_status[channel_id]['status'] = status
            self.alert_channels_status[channel_id]['enabled'] = enabled

    def get_channel_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有外部告警渠道状态"""
        return self.alert_channels_status.copy()
