#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能配置推荐界面

提供配置推荐的展示和应用功能，包括：
- 配置推荐获取和展示
- 推荐配置的预览和比较
- 配置变更影响分析
- 推荐应用和回滚功能
- 用户反馈收集

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sys
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

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
    QDial, QCalendarWidget, QLineEdit, QDoubleSpinBox, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QThread, QMutex, QMutexLocker,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QDateTime, QTime, QDate, QSize, QPropertyAnimation, QRect
)
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QPixmap, QIcon, QPainter, QBrush, QPen,
    QLinearGradient, QRadialGradient, QFontMetrics
)

# 导入核心AI服务
from core.ai.config_recommendation_engine import ConfigRecommendationEngine
from core.ai.config_impact_analyzer import ConfigImpactAnalyzer
from core.ui_integration.ui_business_logic_adapter import get_ui_adapter
from loguru import logger


class RecommendationType(Enum):
    """推荐类型"""
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    RESOURCE_EFFICIENCY = "resource_efficiency"
    RELIABILITY_IMPROVEMENT = "reliability_improvement"
    COST_REDUCTION = "cost_reduction"
    SECURITY_ENHANCEMENT = "security_enhancement"


class RecommendationPriority(Enum):
    """推荐优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConfigRecommendation:
    """配置推荐"""
    id: str
    title: str
    description: str
    recommendation_type: RecommendationType
    priority: RecommendationPriority
    confidence: float
    estimated_impact: Dict[str, float]  # {"performance": 0.15, "cost": -0.05}
    current_config: Dict[str, Any]
    recommended_config: Dict[str, Any]
    rationale: str
    prerequisites: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    applied: bool = False
    user_feedback: Optional[str] = None


class RecommendationCard(QWidget):
    """推荐卡片组件"""

    apply_clicked = pyqtSignal(str)  # recommendation_id
    preview_clicked = pyqtSignal(str)  # recommendation_id
    feedback_submitted = pyqtSignal(str, str)  # recommendation_id, feedback

    def __init__(self, recommendation: ConfigRecommendation, parent=None):
        super().__init__(parent)
        self.recommendation = recommendation
        self.setup_ui()
        self.setup_animations()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 主卡片容器
        self.card_frame = QFrame()
        self.card_frame.setFrameStyle(QFrame.Box)
        self.card_frame.setStyleSheet(self.get_card_style())

        card_layout = QVBoxLayout(self.card_frame)

        # 标题和优先级行
        header_layout = QHBoxLayout()

        # 标题
        title_label = QLabel(self.recommendation.title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 优先级标签
        priority_label = QLabel(self.get_priority_text())
        priority_label.setStyleSheet(self.get_priority_style())
        header_layout.addWidget(priority_label)

        card_layout.addLayout(header_layout)

        # 描述
        desc_label = QLabel(self.recommendation.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            QLabel {
                color: #5a6c7d;
                font-size: 13px;
                padding: 5px 0;
            }
        """)
        card_layout.addWidget(desc_label)

        # 置信度和影响指标
        metrics_layout = QGridLayout()

        # 置信度
        metrics_layout.addWidget(QLabel("置信度:"), 0, 0)
        confidence_bar = QProgressBar()
        confidence_bar.setRange(0, 100)
        confidence_bar.setValue(int(self.recommendation.confidence * 100))
        confidence_bar.setStyleSheet(self.get_confidence_style())
        metrics_layout.addWidget(confidence_bar, 0, 1)

        # 预期影响
        row = 1
        for metric, impact in self.recommendation.estimated_impact.items():
            metrics_layout.addWidget(QLabel(f"{metric}影响:"), row, 0)

            impact_label = QLabel(f"{impact:+.1%}")
            if impact > 0:
                impact_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            elif impact < 0:
                impact_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            else:
                impact_label.setStyleSheet("color: #95a5a6;")

            metrics_layout.addWidget(impact_label, row, 1)
            row += 1

        card_layout.addLayout(metrics_layout)

        # 配置变更预览
        config_group = QGroupBox("配置变更预览")
        config_layout = QVBoxLayout(config_group)

        # 创建配置比较表格
        config_comparison = self.create_config_comparison()
        config_layout.addWidget(config_comparison)

        card_layout.addWidget(config_group)

        # 风险和前提条件
        if self.recommendation.risks or self.recommendation.prerequisites:
            warnings_layout = QVBoxLayout()

            if self.recommendation.prerequisites:
                prereq_label = QLabel("前提条件: " + "; ".join(self.recommendation.prerequisites))
                prereq_label.setStyleSheet("""
                    QLabel {
                        color: #f39c12;
                        font-size: 12px;
                        background-color: #fef9e7;
                        padding: 5px;
                        border-radius: 3px;
                    }
                """)
                prereq_label.setWordWrap(True)
                warnings_layout.addWidget(prereq_label)

            if self.recommendation.risks:
                risk_label = QLabel("潜在风险: " + "; ".join(self.recommendation.risks))
                risk_label.setStyleSheet("""
                    QLabel {
                        color: #e74c3c;
                        font-size: 12px;
                        background-color: #fdedec;
                        padding: 5px;
                        border-radius: 3px;
                    }
                """)
                risk_label.setWordWrap(True)
                warnings_layout.addWidget(risk_label)

            card_layout.addLayout(warnings_layout)

        # 操作按钮
        buttons_layout = QHBoxLayout()

        # 预览按钮
        preview_btn = QPushButton("👀 预览配置")
        preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.recommendation.id))
        preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        buttons_layout.addWidget(preview_btn)

        # 应用按钮
        apply_btn = QPushButton("应用推荐")
        if self.recommendation.applied:
            apply_btn.setText("✓ 已应用")
            apply_btn.setEnabled(False)
        else:
            apply_btn.clicked.connect(lambda: self.apply_clicked.emit(self.recommendation.id))

        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        buttons_layout.addWidget(apply_btn)

        # 反馈按钮
        feedback_btn = QPushButton("💬 反馈")
        feedback_btn.clicked.connect(self.show_feedback_dialog)
        feedback_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        buttons_layout.addWidget(feedback_btn)

        buttons_layout.addStretch()

        card_layout.addLayout(buttons_layout)

        layout.addWidget(self.card_frame)

    def create_config_comparison(self) -> QWidget:
        """创建配置比较组件"""
        comparison_widget = QWidget()
        layout = QVBoxLayout(comparison_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # 简化的配置对比显示
        changes_count = 0
        for key in self.recommendation.recommended_config:
            if key in self.recommendation.current_config:
                current_val = self.recommendation.current_config[key]
                recommended_val = self.recommendation.recommended_config[key]

                if current_val != recommended_val:
                    changes_count += 1

                    change_layout = QHBoxLayout()

                    # 参数名
                    param_label = QLabel(f"{key}:")
                    param_label.setFixedWidth(120)
                    param_label.setStyleSheet("font-weight: bold;")
                    change_layout.addWidget(param_label)

                    # 当前值
                    current_label = QLabel(str(current_val))
                    current_label.setStyleSheet("color: #e74c3c; background-color: #fdedec; padding: 2px; border-radius: 2px;")
                    change_layout.addWidget(current_label)

                    # 箭头
                    arrow_label = QLabel("→")
                    arrow_label.setStyleSheet("font-weight: bold; color: #3498db;")
                    change_layout.addWidget(arrow_label)

                    # 推荐值
                    recommended_label = QLabel(str(recommended_val))
                    recommended_label.setStyleSheet("color: #27ae60; background-color: #eafaf1; padding: 2px; border-radius: 2px;")
                    change_layout.addWidget(recommended_label)

                    change_layout.addStretch()
                    layout.addLayout(change_layout)

        if changes_count == 0:
            no_changes_label = QLabel("无配置变更")
            no_changes_label.setStyleSheet("color: #95a5a6; font-style: italic;")
            layout.addWidget(no_changes_label)

        return comparison_widget

    def get_card_style(self) -> str:
        """获取卡片样式"""
        priority_colors = {
            RecommendationPriority.LOW: "#ecf0f1",
            RecommendationPriority.MEDIUM: "#fef9e7",
            RecommendationPriority.HIGH: "#fdecea",
            RecommendationPriority.CRITICAL: "#fadbd8"
        }

        bg_color = priority_colors.get(self.recommendation.priority, "#ecf0f1")

        return f"""
            QFrame {{
                background-color: {bg_color};
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin: 5px;
            }}
            QFrame:hover {{
                border-color: #3498db;
                box-shadow: 0 2px 10px rgba(52, 152, 219, 0.3);
            }}
        """

    def get_priority_text(self) -> str:
        """获取优先级文本"""
        priority_texts = {
            RecommendationPriority.LOW: "🟢 低优先级",
            RecommendationPriority.MEDIUM: "🟡 中优先级",
            RecommendationPriority.HIGH: "🟠 高优先级",
            RecommendationPriority.CRITICAL: "🔴 紧急"
        }
        return priority_texts.get(self.recommendation.priority, "未知")

    def get_priority_style(self) -> str:
        """获取优先级样式"""
        priority_styles = {
            RecommendationPriority.LOW: """
                QLabel {
                    background-color: #d5f4e6;
                    color: #27ae60;
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """,
            RecommendationPriority.MEDIUM: """
                QLabel {
                    background-color: #fcf3cf;
                    color: #f39c12;
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """,
            RecommendationPriority.HIGH: """
                QLabel {
                    background-color: #fdecea;
                    color: #e67e22;
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """,
            RecommendationPriority.CRITICAL: """
                QLabel {
                    background-color: #fadbd8;
                    color: #e74c3c;
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """
        }
        return priority_styles.get(self.recommendation.priority, "")

    def get_confidence_style(self) -> str:
        """获取置信度样式"""
        if self.recommendation.confidence >= 0.8:
            color = "#27ae60"
        elif self.recommendation.confidence >= 0.6:
            color = "#f39c12"
        else:
            color = "#e74c3c"

        return f"""
            QProgressBar {{
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                color: white;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """

    def setup_animations(self):
        """设置动画效果"""
        self.hover_animation = QPropertyAnimation(self.card_frame, b"geometry")
        self.hover_animation.setDuration(200)
        self.hover_animation.setEasingCurve(QEasingCurve.OutCubic)

    def show_feedback_dialog(self):
        """显示反馈对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("提供反馈")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)

        # 反馈说明
        info_label = QLabel(f"对推荐 '{self.recommendation.title}' 提供反馈:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # 反馈文本框
        feedback_text = QTextEdit()
        feedback_text.setPlaceholderText("请输入您对此推荐的反馈意见...")
        if self.recommendation.user_feedback:
            feedback_text.setPlainText(self.recommendation.user_feedback)
        layout.addWidget(feedback_text)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            feedback = feedback_text.toPlainText().strip()
            if feedback:
                self.feedback_submitted.emit(self.recommendation.id, feedback)

    def mark_as_applied(self):
        """标记为已应用"""
        self.recommendation.applied = True
        # 更新按钮状态
        # 这里需要重新设置UI，为简化起见暂时省略


class ConfigPreviewDialog(QDialog):
    """配置预览对话框"""

    def __init__(self, recommendation: ConfigRecommendation, parent=None):
        super().__init__(parent)
        self.recommendation = recommendation
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle(f"配置预览 - {self.recommendation.title}")
        self.setModal(True)
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # 推荐信息
        info_group = QGroupBox("推荐信息")
        info_layout = QFormLayout(info_group)

        info_layout.addRow("标题:", QLabel(self.recommendation.title))
        info_layout.addRow("描述:", QLabel(self.recommendation.description))
        info_layout.addRow("置信度:", QLabel(f"{self.recommendation.confidence:.1%}"))

        # 预期影响
        impact_text = "; ".join([f"{k}: {v:+.1%}" for k, v in self.recommendation.estimated_impact.items()])
        info_layout.addRow("预期影响:", QLabel(impact_text))

        layout.addWidget(info_group)

        # 配置对比
        comparison_group = QGroupBox("配置对比")
        comparison_layout = QVBoxLayout(comparison_group)

        # 创建选项卡
        tab_widget = QTabWidget()

        # 当前配置选项卡
        current_tab = QTextEdit()
        current_tab.setReadOnly(True)
        current_tab.setPlainText(json.dumps(self.recommendation.current_config, indent=2, ensure_ascii=False))
        tab_widget.addTab(current_tab, "当前配置")

        # 推荐配置选项卡
        recommended_tab = QTextEdit()
        recommended_tab.setReadOnly(True)
        recommended_tab.setPlainText(json.dumps(self.recommendation.recommended_config, indent=2, ensure_ascii=False))
        tab_widget.addTab(recommended_tab, "推荐配置")

        # 差异对比选项卡
        diff_tab = self.create_diff_view()
        tab_widget.addTab(diff_tab, "差异对比")

        comparison_layout.addWidget(tab_widget)
        layout.addWidget(comparison_group)

        # 影响分析
        if hasattr(self, 'impact_analyzer'):
            impact_group = QGroupBox("影响分析")
            impact_layout = QVBoxLayout(impact_group)

            impact_text = QTextEdit()
            impact_text.setReadOnly(True)
            impact_text.setMaximumHeight(100)
            impact_text.setPlainText(f"理由: {self.recommendation.rationale}")
            impact_layout.addWidget(impact_text)

            layout.addWidget(impact_group)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def create_diff_view(self) -> QWidget:
        """创建差异视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        diff_table = QTableWidget()
        diff_table.setColumnCount(3)
        diff_table.setHorizontalHeaderLabels(["参数", "当前值", "推荐值"])

        # 收集所有参数
        all_keys = set(self.recommendation.current_config.keys()) | set(self.recommendation.recommended_config.keys())
        changed_keys = []

        for key in all_keys:
            current_val = self.recommendation.current_config.get(key, "未设置")
            recommended_val = self.recommendation.recommended_config.get(key, "未设置")

            if current_val != recommended_val:
                changed_keys.append((key, current_val, recommended_val))

        diff_table.setRowCount(len(changed_keys))

        for row, (key, current_val, recommended_val) in enumerate(changed_keys):
            # 参数名
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            diff_table.setItem(row, 0, key_item)

            # 当前值
            current_item = QTableWidgetItem(str(current_val))
            current_item.setFlags(current_item.flags() & ~Qt.ItemIsEditable)
            current_item.setBackground(QColor(248, 215, 218))  # 红色背景
            diff_table.setItem(row, 1, current_item)

            # 推荐值
            recommended_item = QTableWidgetItem(str(recommended_val))
            recommended_item.setFlags(recommended_item.flags() & ~Qt.ItemIsEditable)
            recommended_item.setBackground(QColor(212, 237, 218))  # 绿色背景
            diff_table.setItem(row, 2, recommended_item)

        # 自动调整列宽
        diff_table.resizeColumnsToContents()
        header = diff_table.horizontalHeader()
        header.setStretchLastSection(True)

        layout.addWidget(diff_table)

        return widget


class ConfigRecommendationPanel(QWidget):
    """智能配置推荐面板主组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui_adapter = None
        self.recommendations: List[ConfigRecommendation] = []

        # 初始化核心服务
        if CORE_AVAILABLE:
            try:
                self.ui_adapter = get_ui_adapter()
                self.config_manager = None
                self.recommendation_engine = ConfigRecommendationEngine(self.config_manager)
                self.impact_analyzer = ConfigImpactAnalyzer()
            except Exception as e:
                logger.warning(f"核心服务初始化失败: {e}")
                self.config_manager = None
                self.recommendation_engine = None
                self.impact_analyzer = None
        else:
            self.config_manager = None
            self.recommendation_engine = None
            self.impact_analyzer = None

        self.setup_ui()
        self.setup_connections()
        self.load_sample_recommendations()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题和控制区域
        header_layout = QHBoxLayout()

        title_label = QLabel("[INFO] 智能配置推荐")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
            }
        """)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 获取推荐按钮
        get_recommendations_btn = QPushButton("获取新推荐")
        get_recommendations_btn.clicked.connect(self.get_recommendations)
        get_recommendations_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        header_layout.addWidget(get_recommendations_btn)

        layout.addLayout(header_layout)

        # 过滤和排序控制
        filter_layout = QHBoxLayout()

        # 类型过滤
        filter_layout.addWidget(QLabel("类型:"))
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItems([
            "全部", "性能优化", "资源效率", "可靠性改进", "成本节约", "安全增强"
        ])
        self.type_filter_combo.currentTextChanged.connect(self.filter_recommendations)
        filter_layout.addWidget(self.type_filter_combo)

        # 优先级过滤
        filter_layout.addWidget(QLabel("优先级:"))
        self.priority_filter_combo = QComboBox()
        self.priority_filter_combo.addItems(["全部", "紧急", "高", "中", "低"])
        self.priority_filter_combo.currentTextChanged.connect(self.filter_recommendations)
        filter_layout.addWidget(self.priority_filter_combo)

        # 状态过滤
        filter_layout.addWidget(QLabel("状态:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["全部", "未应用", "已应用"])
        self.status_filter_combo.currentTextChanged.connect(self.filter_recommendations)
        filter_layout.addWidget(self.status_filter_combo)

        filter_layout.addStretch()

        # 批量操作
        batch_apply_btn = QPushButton("批量应用")
        batch_apply_btn.clicked.connect(self.batch_apply)
        batch_apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        filter_layout.addWidget(batch_apply_btn)

        layout.addLayout(filter_layout)

        # 推荐列表区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarNever)

        # 推荐容器
        self.recommendations_container = QWidget()
        self.recommendations_layout = QVBoxLayout(self.recommendations_container)
        self.recommendations_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.recommendations_container)
        layout.addWidget(self.scroll_area)

        # 统计信息
        stats_group = QGroupBox("推荐统计")
        stats_layout = QGridLayout(stats_group)

        # 总推荐数
        stats_layout.addWidget(QLabel("总推荐数:"), 0, 0)
        self.total_recommendations_label = QLabel("0")
        stats_layout.addWidget(self.total_recommendations_label, 0, 1)

        # 已应用数
        stats_layout.addWidget(QLabel("已应用:"), 0, 2)
        self.applied_recommendations_label = QLabel("0")
        stats_layout.addWidget(self.applied_recommendations_label, 0, 3)

        # 平均置信度
        stats_layout.addWidget(QLabel("平均置信度:"), 1, 0)
        self.avg_confidence_label = QLabel("0%")
        stats_layout.addWidget(self.avg_confidence_label, 1, 1)

        # 预期总影响
        stats_layout.addWidget(QLabel("预期性能提升:"), 1, 2)
        self.expected_impact_label = QLabel("0%")
        stats_layout.addWidget(self.expected_impact_label, 1, 3)

        layout.addWidget(stats_group)

    def setup_connections(self):
        """设置连接"""
        pass

    def load_sample_recommendations(self):
        """加载推荐（使用真实推荐引擎）"""
        try:
            if self.recommendation_engine is not None:
                logger.info("使用真实推荐引擎生成配置推荐")
                self._load_real_recommendations()
            else:
                logger.warning("推荐引擎不可用，显示无数据状态")
                self._show_no_data_state()
        except Exception as e:
            logger.error(f"加载推荐失败: {e}")
            self._show_no_data_state()
    
    def _show_no_data_state(self):
        """显示无数据状态"""
        logger.info("显示无数据状态")
        self.recommendations = []
        self.update_recommendations_display()
        self.update_statistics()
        
        # 显示提示信息
        QMessageBox.information(
            self, 
            "推荐引擎不可用",
            "配置推荐引擎当前不可用，无法生成配置优化建议。\n\n"
            "请检查系统配置或联系管理员。"
        )
    
    def _load_real_recommendations(self):
        """使用真实推荐引擎加载推荐"""
        try:
            from core.ai.config_recommendation_engine import ImportTaskConfig, RecommendationStrategy, OptimizationObjective
            
            base_config = ImportTaskConfig(
                max_workers=4,
                batch_size=100,
                chunk_size=1000,
                use_multiprocessing=True,
                validate_data=True,
                skip_duplicates=True,
                enable_caching=True
            )
            
            recommendations = []
            
            strategies = [
                RecommendationStrategy.AGGRESSIVE,
                RecommendationStrategy.CONSERVATIVE,
                RecommendationStrategy.BALANCED
            ]
            
            objectives = [
                OptimizationObjective.MAXIMIZE_SUCCESS_RATE,
                OptimizationObjective.MINIMIZE_EXECUTION_TIME,
                OptimizationObjective.MAXIMIZE_THROUGHPUT
            ]
            
            for strategy in strategies:
                for objective in objectives:
                    try:
                        recommendation = self.recommendation_engine.recommend_config(
                            base_config=base_config,
                            strategy=strategy,
                            objective=objective
                        )
                        
                        if recommendation:
                            formatted_rec = self._format_recommendation(recommendation, strategy, objective)
                            recommendations.append(formatted_rec)
                    except Exception as e:
                        logger.warning(f"生成推荐失败 (策略: {strategy}, 目标: {objective}): {e}")
                        continue
            
            if recommendations:
                self.recommendations = recommendations[:10]
                logger.info(f"成功生成 {len(self.recommendations)} 个真实推荐")
            else:
                logger.warning("未生成任何推荐，使用演示数据")
                self._load_demo_recommendations()
                
            self.update_recommendations_display()
            self.update_statistics()
            
        except Exception as e:
            logger.error(f"加载真实推荐失败: {e}")
            self._load_demo_recommendations()
    
    def _format_recommendation(self, recommendation, strategy, objective):
        """格式化推荐为 ConfigRecommendation 对象"""
        from core.ai.config_recommendation_engine import RecommendationType, RecommendationPriority
        
        strategy_names = {
            RecommendationStrategy.AGGRESSIVE: "激进策略",
            RecommendationStrategy.CONSERVATIVE: "保守策略",
            RecommendationStrategy.BALANCED: "平衡策略"
        }
        
        objective_names = {
            OptimizationObjective.MAXIMIZE_SUCCESS_RATE: "最大化成功率",
            OptimizationObjective.MINIMIZE_EXECUTION_TIME: "最小化执行时间",
            OptimizationObjective.MAXIMIZE_THROUGHPUT: "最大化吞吐量"
        }
        
        title = f"{strategy_names.get(strategy, '优化')} - {objective_names.get(objective, '优化')}"
        
        confidence = recommendation.confidence_score
        
        if confidence >= 0.8:
            priority = RecommendationPriority.HIGH
        elif confidence >= 0.6:
            priority = RecommendationPriority.MEDIUM
        else:
            priority = RecommendationPriority.LOW
        
        return ConfigRecommendation(
            id=f"real_rec_{strategy.value}_{objective.value}",
            title=title,
            description=recommendation.optimization_rationale,
            recommendation_type=RecommendationType.PERFORMANCE_OPTIMIZATION,
            priority=priority,
            confidence=confidence,
            estimated_impact=recommendation.expected_performance,
            current_config={"max_workers": 4, "batch_size": 100},
            recommended_config=recommendation.recommended_config,
            rationale=recommendation.optimization_rationale,
            prerequisites=recommendation.risk_assessment.get("prerequisites", []),
            risks=recommendation.risk_assessment.get("risks", [])
        )
    
    def get_recommendations(self):
        """获取新推荐"""
        try:
            if self.recommendation_engine:
                # 调用真实的推荐引擎
                context = {
                    "current_time": datetime.now(),
                    "system_load": "medium",
                    "user_preferences": {}
                }

                new_recommendations = self.recommendation_engine.generate_recommendations(context)
                if new_recommendations:
                    self.recommendations.extend(new_recommendations)
                    self.update_recommendations_display()
                    self.update_statistics()

                    QMessageBox.information(
                        self, "获取成功",
                        f"成功获取 {len(new_recommendations)} 个新推荐"
                    )
                else:
                    QMessageBox.information(self, "无新推荐", "当前没有新的配置推荐")
            else:
                # 模拟获取推荐
                QMessageBox.information(self, "模拟模式", "当前为演示模式，已加载示例推荐")

        except Exception as e:
            logger.error(f"获取推荐失败: {e}")
            QMessageBox.warning(self, "获取失败", f"获取推荐时出错: {e}")

    def filter_recommendations(self):
        """过滤推荐"""
        self.update_recommendations_display()

    def update_recommendations_display(self):
        """更新推荐显示"""
        # 清除现有推荐卡片
        for i in reversed(range(self.recommendations_layout.count())):
            child = self.recommendations_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        # 应用过滤器
        filtered_recommendations = self.apply_filters()

        if not filtered_recommendations:
            # 显示无推荐消息
            no_rec_label = QLabel("📭 暂无符合条件的推荐")
            no_rec_label.setAlignment(Qt.AlignCenter)
            no_rec_label.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    color: #95a5a6;
                    padding: 50px;
                }
            """)
            self.recommendations_layout.addWidget(no_rec_label)
        else:
            # 添加推荐卡片
            for recommendation in filtered_recommendations:
                card = RecommendationCard(recommendation)
                card.apply_clicked.connect(self.apply_recommendation)
                card.preview_clicked.connect(self.preview_recommendation)
                card.feedback_submitted.connect(self.submit_feedback)

                self.recommendations_layout.addWidget(card)

    def apply_filters(self) -> List[ConfigRecommendation]:
        """应用过滤器"""
        filtered = self.recommendations.copy()

        # 类型过滤
        type_filter = self.type_filter_combo.currentText()
        if type_filter != "全部":
            type_mapping = {
                "性能优化": RecommendationType.PERFORMANCE_OPTIMIZATION,
                "资源效率": RecommendationType.RESOURCE_EFFICIENCY,
                "可靠性改进": RecommendationType.RELIABILITY_IMPROVEMENT,
                "成本节约": RecommendationType.COST_REDUCTION,
                "安全增强": RecommendationType.SECURITY_ENHANCEMENT
            }
            target_type = type_mapping.get(type_filter)
            if target_type:
                filtered = [r for r in filtered if r.recommendation_type == target_type]

        # 优先级过滤
        priority_filter = self.priority_filter_combo.currentText()
        if priority_filter != "全部":
            priority_mapping = {
                "紧急": RecommendationPriority.CRITICAL,
                "高": RecommendationPriority.HIGH,
                "中": RecommendationPriority.MEDIUM,
                "低": RecommendationPriority.LOW
            }
            target_priority = priority_mapping.get(priority_filter)
            if target_priority:
                filtered = [r for r in filtered if r.priority == target_priority]

        # 状态过滤
        status_filter = self.status_filter_combo.currentText()
        if status_filter == "未应用":
            filtered = [r for r in filtered if not r.applied]
        elif status_filter == "已应用":
            filtered = [r for r in filtered if r.applied]

        # 按优先级和置信度排序
        priority_order = {
            RecommendationPriority.CRITICAL: 4,
            RecommendationPriority.HIGH: 3,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 1
        }

        filtered.sort(key=lambda r: (priority_order.get(r.priority, 0), r.confidence), reverse=True)

        return filtered

    def apply_recommendation(self, recommendation_id: str):
        """应用推荐"""
        recommendation = next((r for r in self.recommendations if r.id == recommendation_id), None)
        if not recommendation:
            return

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认应用",
            f"确定要应用推荐 '{recommendation.title}' 吗？\n\n"
            f"这将修改当前系统配置。建议先进行预览和影响分析。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 这里应该调用实际的配置应用逻辑
                if self.config_manager:
                    # 实际应用配置
                    success = self.apply_config_changes(recommendation)
                    if success:
                        recommendation.applied = True
                        self.update_recommendations_display()
                        self.update_statistics()

                        QMessageBox.information(
                            self, "应用成功",
                            f"推荐 '{recommendation.title}' 已成功应用！"
                        )
                    else:
                        QMessageBox.warning(
                            self, "应用失败",
                            "配置应用失败，请检查系统状态。"
                        )
                else:
                    # 模拟应用
                    recommendation.applied = True
                    self.update_recommendations_display()
                    self.update_statistics()

                    QMessageBox.information(
                        self, "模拟应用",
                        f"推荐 '{recommendation.title}' 已模拟应用！"
                    )

            except Exception as e:
                logger.error(f"应用推荐失败: {e}")
                QMessageBox.critical(self, "应用错误", f"应用推荐时发生错误: {e}")

    def apply_config_changes(self, recommendation: ConfigRecommendation) -> bool:
        """应用配置变更"""
        try:
            # 这里应该实现实际的配置应用逻辑
            # 例如更新配置文件、重启服务等

            if self.impact_analyzer:
                # 记录配置变更
                self.impact_analyzer.record_config_change(
                    recommendation.current_config,
                    recommendation.recommended_config,
                    recommendation.rationale
                )

            return True

        except Exception as e:
            logger.error(f"配置应用失败: {e}")
            return False

    def preview_recommendation(self, recommendation_id: str):
        """预览推荐"""
        recommendation = next((r for r in self.recommendations if r.id == recommendation_id), None)
        if recommendation:
            dialog = ConfigPreviewDialog(recommendation, self)
            dialog.exec_()

    def submit_feedback(self, recommendation_id: str, feedback: str):
        """提交反馈"""
        recommendation = next((r for r in self.recommendations if r.id == recommendation_id), None)
        if recommendation:
            recommendation.user_feedback = feedback
            logger.info(f"用户对推荐 '{recommendation.title}' 提供反馈: {feedback}")

            QMessageBox.information(self, "反馈提交", "感谢您的反馈！这将帮助我们改进推荐算法。")

    def batch_apply(self):
        """批量应用推荐"""
        # 获取未应用的高置信度推荐
        unapplied_high_confidence = [
            r for r in self.recommendations
            if not r.applied and r.confidence >= 0.8 and r.priority != RecommendationPriority.LOW
        ]

        if not unapplied_high_confidence:
            QMessageBox.information(self, "无可批量应用项", "暂无适合批量应用的推荐项。")
            return

        # 显示批量应用对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("批量应用推荐")
        dialog.setModal(True)
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        info_label = QLabel(f"发现 {len(unapplied_high_confidence)} 个高置信度推荐可以批量应用:")
        layout.addWidget(info_label)

        # 推荐列表
        list_widget = QListWidget()
        for rec in unapplied_high_confidence:
            item_text = f"✓ {rec.title} (置信度: {rec.confidence:.1%})"
            list_widget.addItem(item_text)
        layout.addWidget(list_widget)

        # 警告
        warning_label = QLabel("批量应用将同时修改多个系统配置，请确保您了解所有变更的影响。")
        warning_label.setStyleSheet("color: #e67e22; font-weight: bold;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            # 执行批量应用
            success_count = 0
            for rec in unapplied_high_confidence:
                try:
                    if self.apply_config_changes(rec):
                        rec.applied = True
                        success_count += 1
                except Exception as e:
                    logger.error(f"批量应用推荐 {rec.id} 失败: {e}")

            self.update_recommendations_display()
            self.update_statistics()

            QMessageBox.information(
                self, "批量应用完成",
                f"成功应用 {success_count}/{len(unapplied_high_confidence)} 个推荐"
            )

    def update_statistics(self):
        """更新统计信息"""
        if not self.recommendations:
            return

        # 总推荐数
        total_count = len(self.recommendations)
        self.total_recommendations_label.setText(str(total_count))

        # 已应用数
        applied_count = sum(1 for r in self.recommendations if r.applied)
        self.applied_recommendations_label.setText(str(applied_count))

        # 平均置信度
        avg_confidence = sum(r.confidence for r in self.recommendations) / total_count
        self.avg_confidence_label.setText(f"{avg_confidence:.1%}")

        # 预期总影响（性能提升）
        total_performance_impact = sum(
            r.estimated_impact.get("performance", 0)
            for r in self.recommendations if not r.applied
        )
        self.expected_impact_label.setText(f"{total_performance_impact:+.1%}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 2px solid #bdc3c7;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 12px;
            background-color: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 8px 0 8px;
            color: #2c3e50;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 100px;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #21618c;
        }
        QScrollArea {
            border: 1px solid #bdc3c7;
            border-radius: 6px;
            background-color: #ffffff;
        }
        QComboBox {
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: white;
        }
        QComboBox:hover {
            border-color: #3498db;
        }
    """)

    # 创建主窗口
    widget = ConfigRecommendationPanel()
    widget.setWindowTitle("智能配置推荐面板")
    widget.resize(1000, 800)
    widget.show()

    sys.exit(app.exec_())
