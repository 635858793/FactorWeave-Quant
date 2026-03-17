"""
策略开发工作流组件 - 重构版
集成系统主题管理，提供现代化的工作流体验
"""
import os
from typing import Dict, List, Optional, Any
from enum import Enum
from loguru import logger

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QGroupBox, QFormLayout, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QProgressBar, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QFrame,
    QScrollArea, QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QLinearGradient

try:
    from utils.theme import get_theme_manager, Theme
    from gui.styles.unified_design_system import DesignTokens, ColorScheme, StyleSheetGenerator
    THEME_AVAILABLE = True
except ImportError as e:
    logger.warning(f"主题模块导入失败: {e}")
    THEME_AVAILABLE = False


class WorkflowStage(Enum):
    """工作流阶段"""
    DESIGN = "设计"
    CODING = "编码"
    DEBUGGING = "调试"
    BACKTEST = "回测"
    OPTIMIZATION = "优化"
    DEPLOYMENT = "部署"


class WorkflowStep:
    """工作流步骤"""
    
    def __init__(self, stage: WorkflowStage, name: str, description: str, is_completed: bool = False):
        self.stage = stage
        self.name = name
        self.description = description
        self.is_completed = is_completed
        self.data = {}


class StageIndicator(QWidget):
    """阶段指示器组件"""

    stage_clicked = pyqtSignal(int)

    def __init__(self, stages: List[str], parent=None, theme_manager=None):
        super().__init__(parent)
        self.stages = stages
        self.theme_manager = theme_manager
        self.current_stage = 0
        self.completed_stages = set()
        self.setMinimumHeight(60)
        self._apply_theme()

    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            self._active_color = colors.get('highlight', '#1976d2')
            self._completed_color = colors.get('success', '#4CAF50')
            self._pending_color = colors.get('border', '#3c3c3c')
            self._text_color = colors.get('text', '#d4d4d4')
            self._bg_color = colors.get('sidebar_bg', '#2d2d2d')
        else:
            self._active_color = '#1976d2'
            self._completed_color = '#4CAF50'
            self._pending_color = '#3c3c3c'
            self._text_color = '#d4d4d4'
            self._bg_color = '#2d2d2d'

    def set_current_stage(self, index: int):
        self.current_stage = index
        self.update()

    def set_completed(self, index: int, completed: bool = True):
        if completed:
            self.completed_stages.add(index)
        else:
            self.completed_stages.discard(index)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        stage_count = len(self.stages)
        
        if stage_count == 0:
            return

        step_width = width // stage_count
        circle_radius = 12
        y_center = height // 2

        for i, stage in enumerate(self.stages):
            x_center = step_width * i + step_width // 2

            if i < self.current_stage or i in self.completed_stages:
                color = QColor(self._completed_color)
            elif i == self.current_stage:
                color = QColor(self._active_color)
            else:
                color = QColor(self._pending_color)

            if i < stage_count - 1:
                line_start = x_center + circle_radius + 5
                line_end = x_center + step_width - circle_radius - 5
                
                if i < self.current_stage or i in self.completed_stages:
                    line_color = QColor(self._completed_color)
                else:
                    line_color = QColor(self._pending_color)
                
                painter.setPen(QPen(line_color, 2))
                painter.drawLine(line_start, y_center, line_end, y_center)

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(120), 2))
            painter.drawEllipse(x_center - circle_radius, y_center - circle_radius, 
                              circle_radius * 2, circle_radius * 2)

            painter.setPen(QColor(self._text_color))
            font = painter.font()
            if i == self.current_stage:
                font.setBold(True)
                font.setPointSize(10)
            else:
                font.setBold(False)
                font.setPointSize(9)
            painter.setFont(font)
            
            text_rect = painter.fontMetrics().boundingRect(stage)
            text_x = x_center - text_rect.width() // 2
            text_y = y_center + circle_radius + 15
            painter.drawText(text_x, text_y, stage)

    def mousePressEvent(self, event):
        stage_count = len(self.stages)
        if stage_count == 0:
            return
            
        step_width = self.width() // stage_count
        clicked_stage = event.x() // step_width
        
        if 0 <= clicked_stage < stage_count:
            self.stage_clicked.emit(clicked_stage)

    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._apply_theme()
        self.update()


class ModernStageCard(QFrame):
    """现代化阶段卡片"""

    clicked = pyqtSignal()

    def __init__(self, title: str, description: str, index: int, parent=None, theme_manager=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.index = index
        self.theme_manager = theme_manager
        self.is_active = False
        self.is_completed = False
        self._setup_ui()
        # self._apply_theme()

    def _setup_ui(self):
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(80)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self.index_label = QLabel(str(self.index + 1))
        self.index_label.setFixedSize(36, 36)
        self.index_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.index_label)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)

        self.title_label = QLabel(self.title)
        self.title_label.setObjectName("card_title")
        content_layout.addWidget(self.title_label)

        self.desc_label = QLabel(self.description)
        self.desc_label.setObjectName("card_desc")
        self.desc_label.setWordWrap(True)
        content_layout.addWidget(self.desc_label)

        layout.addLayout(content_layout)
        layout.addStretch()

        self.status_icon = QLabel()
        self.status_icon.setFixedSize(24, 24)
        layout.addWidget(self.status_icon)

    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('main_content_bg', '#ffffff')
            border_color = colors.get('border', '#e0e0e0')
            text_color = colors.get('text', '#222b45')
            highlight_color = colors.get('highlight', '#1976d2')
            success_color = colors.get('success', '#4CAF50')
            secondary_text = colors.get('chart_text', '#6272a4')
        else:
            bg_color = '#ffffff'
            border_color = '#e0e0e0'
            text_color = '#222b45'
            highlight_color = '#1976d2'
            success_color = '#4CAF50'
            secondary_text = '#6272a4'

        active_bg = highlight_color
        completed_bg = success_color

        if self.is_active:
            card_bg = highlight_color + '15'
            card_border = highlight_color
            index_bg = highlight_color
            index_text = '#ffffff'
        elif self.is_completed:
            card_bg = success_color + '10'
            card_border = success_color
            index_bg = success_color
            index_text = '#ffffff'
        else:
            card_bg = bg_color
            card_border = border_color
            index_bg = border_color
            index_text = text_color

        self.setStyleSheet(f"""
            ModernStageCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
            ModernStageCard:hover {{
                border-color: {highlight_color};
            }}
            QLabel#card_title {{
                color: {text_color};
                font-size: 14px;
                font-weight: bold;
            }}
            QLabel#card_desc {{
                color: {secondary_text};
                font-size: 11px;
            }}
        """)

        # self.index_label.setStyleSheet(f"""
        #     QLabel {{
        #         background-color: {index_bg};
        #         color: {index_text};
        #         border-radius: 18px;
        #         font-weight: bold;
        #         font-size: 14px;
        #     }}
        # """)

        if self.is_completed:
            self.status_icon.setText('✓')
            self.status_icon.setStyleSheet(f"color: {success_color}; font-size: 16px; font-weight: bold;")
        elif self.is_active:
            self.status_icon.setText('▶')
            self.status_icon.setStyleSheet(f"color: {highlight_color}; font-size: 14px;")
        else:
            self.status_icon.setText('')

    def set_active(self, active: bool):
        self.is_active = active
        self._apply_theme()

    def set_completed(self, completed: bool):
        self.is_completed = completed
        self._apply_theme()

    def update_theme(self, theme_manager):
        self.theme_manager = theme_manager
        self._apply_theme()

    def mousePressEvent(self, event):
        self.clicked.emit()


class StrategyDevelopmentWorkflow(QWidget):
    """策略开发工作流 - 重构版"""
    
    workflow_completed = pyqtSignal(dict)
    stage_changed = pyqtSignal(str)
    
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.current_stage = WorkflowStage.DESIGN
        self.steps: Dict[WorkflowStage, List[WorkflowStep]] = {
            WorkflowStage.DESIGN: [
                WorkflowStep(WorkflowStage.DESIGN, "策略思路", "描述策略的基本思路和逻辑"),
                WorkflowStep(WorkflowStage.DESIGN, "参数设计", "定义策略需要的参数"),
                WorkflowStep(WorkflowStage.DESIGN, "指标选择", "选择策略使用的技术指标"),
            ],
            WorkflowStage.CODING: [
                WorkflowStep(WorkflowStage.CODING, "编写代码", "使用代码编辑器编写策略代码"),
                WorkflowStep(WorkflowStage.CODING, "语法检查", "检查代码语法错误"),
                WorkflowStep(WorkflowStage.CODING, "代码格式化", "格式化代码风格"),
            ],
            WorkflowStage.DEBUGGING: [
                WorkflowStep(WorkflowStage.DEBUGGING, "设置断点", "在关键位置设置断点"),
                WorkflowStep(WorkflowStage.DEBUGGING, "单步调试", "逐行执行代码"),
                WorkflowStep(WorkflowStage.DEBUGGING, "变量检查", "检查变量值是否正确"),
            ],
            WorkflowStage.BACKTEST: [
                WorkflowStep(WorkflowStage.BACKTEST, "选择数据", "选择回测数据范围"),
                WorkflowStep(WorkflowStage.BACKTEST, "执行回测", "运行回测引擎"),
                WorkflowStep(WorkflowStage.BACKTEST, "结果分析", "分析回测结果"),
            ],
            WorkflowStage.OPTIMIZATION: [
                WorkflowStep(WorkflowStage.OPTIMIZATION, "参数优化", "优化策略参数"),
                WorkflowStep(WorkflowStage.OPTIMIZATION, "结果对比", "对比不同参数的结果"),
                WorkflowStep(WorkflowStage.OPTIMIZATION, "最优选择", "选择最优参数组合"),
            ],
            WorkflowStage.DEPLOYMENT: [
                WorkflowStep(WorkflowStage.DEPLOYMENT, "策略保存", "保存策略到策略库"),
                WorkflowStep(WorkflowStage.DEPLOYMENT, "策略注册", "注册策略到系统"),
                WorkflowStep(WorkflowStage.DEPLOYMENT, "策略发布", "发布策略供使用"),
            ],
        }
        self.workflow_data = {}
        self._init_theme_manager()
        self.init_ui()
        self._connect_theme_signal()
    
    def _init_theme_manager(self):
        if self.theme_manager is None and THEME_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
            except Exception as e:
                logger.warning(f"获取主题管理器失败: {e}")

    def _connect_theme_signal(self):
        if self.theme_manager:
            try:
                self.theme_manager.theme_changed.connect(self._on_theme_changed)
            except:
                pass

    def _on_theme_changed(self, theme):
        self._apply_theme()
        if hasattr(self, 'stage_indicator'):
            self.stage_indicator.update_theme(self.theme_manager)
        if hasattr(self, 'stage_cards'):
            for card in self.stage_cards:
                card.update_theme(self.theme_manager)
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = self._create_header()
        layout.addWidget(header)

        stage_indicator = self._create_stage_indicator()
        layout.addWidget(stage_indicator)

        main_content = self._create_main_content()
        layout.addWidget(main_content, 1)

        footer = self._create_footer()
        layout.addWidget(footer)

        # self._apply_theme()
        self._update_navigation()
        self._update_button_states()

    def _create_header(self) -> QWidget:
        """创建头部"""
        widget = QWidget()
        widget.setObjectName("workflow_header")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 12, 20, 12)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        title = QLabel("策略开发工作流")
        title.setObjectName("header_title")
        title_layout.addWidget(title)

        self.stage_label = QLabel(f"当前阶段: {self.current_stage.value}")
        self.stage_label.setObjectName("header_subtitle")
        title_layout.addWidget(self.stage_label)

        layout.addLayout(title_layout)
        layout.addStretch()

        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(4)

        progress_title = QLabel("整体进度")
        progress_title.setObjectName("progress_title")
        progress_title.setAlignment(Qt.AlignRight)
        progress_layout.addWidget(progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)

        layout.addLayout(progress_layout)

        return widget

    def _create_stage_indicator(self) -> QWidget:
        """创建阶段指示器"""
        widget = QWidget()
        widget.setObjectName("stage_indicator_container")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 10, 20, 10)

        stages = [stage.value for stage in WorkflowStage]
        self.stage_indicator = StageIndicator(stages, theme_manager=self.theme_manager)
        self.stage_indicator.stage_clicked.connect(self._on_stage_indicator_clicked)
        layout.addWidget(self.stage_indicator)

        return widget

    def _create_main_content(self) -> QWidget:
        """创建主内容区域"""
        widget = QWidget()
        widget.setObjectName("main_content")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_panel = self._create_navigation_panel()
        layout.addWidget(nav_panel)

        content_stack = self._create_content_stack()
        layout.addWidget(content_stack, 1)

        return widget

    def _create_navigation_panel(self) -> QWidget:
        """创建导航面板"""
        widget = QWidget()
        widget.setObjectName("nav_panel")
        widget.setFixedWidth(280)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        nav_title = QLabel("开发阶段")
        nav_title.setObjectName("nav_title")
        layout.addWidget(nav_title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setObjectName("nav_scroll")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        self.stage_cards = []
        for i, stage in enumerate(WorkflowStage):
            card = ModernStageCard(
                stage.value,
                self._get_stage_description(stage),
                i,
                theme_manager=self.theme_manager
            )
            card.clicked.connect(lambda idx=i: self._on_stage_card_clicked(idx))
            self.stage_cards.append(card)
            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        return widget

    def _get_stage_description(self, stage: WorkflowStage) -> str:
        descriptions = {
            WorkflowStage.DESIGN: "设计策略思路和参数",
            WorkflowStage.CODING: "编写策略代码",
            WorkflowStage.DEBUGGING: "调试策略逻辑",
            WorkflowStage.BACKTEST: "执行历史回测",
            WorkflowStage.OPTIMIZATION: "优化策略参数",
            WorkflowStage.DEPLOYMENT: "部署和发布策略",
        }
        return descriptions.get(stage, "")

    def _create_content_stack(self) -> QWidget:
        """创建内容栈"""
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("content_stack")

        self.design_widget = self._create_design_widget()
        self.content_stack.addWidget(self.design_widget)

        self.coding_widget = self._create_coding_widget()
        self.content_stack.addWidget(self.coding_widget)

        self.debugging_widget = self._create_debugging_widget()
        self.content_stack.addWidget(self.debugging_widget)

        self.backtest_widget = self._create_backtest_widget()
        self.content_stack.addWidget(self.backtest_widget)

        self.optimization_widget = self._create_optimization_widget()
        self.content_stack.addWidget(self.optimization_widget)

        self.deployment_widget = self._create_deployment_widget()
        self.content_stack.addWidget(self.deployment_widget)

        return self.content_stack

    def _create_design_widget(self) -> QWidget:
        """创建设计阶段组件"""
        widget = QWidget()
        widget.setObjectName("design_widget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("策略设计")
        header.setObjectName("section_header")
        layout.addWidget(header)

        form_container = QWidget()
        form_container.setObjectName("form_container")
        form_layout = QFormLayout(form_container)
        form_layout.setSpacing(16)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.strategy_name_edit = QLineEdit()
        self.strategy_name_edit.setPlaceholderText("输入策略名称")
        self.strategy_name_edit.setObjectName("form_input")
        form_layout.addRow("策略名称:", self.strategy_name_edit)

        self.strategy_desc_edit = QTextEdit()
        self.strategy_desc_edit.setPlaceholderText("描述策略的基本思路和逻辑")
        self.strategy_desc_edit.setMaximumHeight(120)
        self.strategy_desc_edit.setObjectName("form_textarea")
        form_layout.addRow("策略描述:", self.strategy_desc_edit)

        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems(["MA", "EMA", "RSI", "MACD", "BOLL", "KDJ", "自定义"])
        self.indicator_combo.setObjectName("form_combo")
        form_layout.addRow("主要指标:", self.indicator_combo)

        layout.addWidget(form_container)
        layout.addStretch()

        return widget

    def _create_coding_widget(self) -> QWidget:
        """创建编码阶段组件"""
        widget = QWidget()
        widget.setObjectName("coding_widget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("策略编码")
        header.setObjectName("section_header")
        layout.addWidget(header)

        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setObjectName("code_preview")
        layout.addWidget(self.code_preview)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        open_editor_btn = QPushButton("打开代码编辑器")
        open_editor_btn.setObjectName("primary_button")
        open_editor_btn.clicked.connect(self._open_code_editor)
        btn_layout.addWidget(open_editor_btn)

        check_syntax_btn = QPushButton("检查语法")
        check_syntax_btn.setObjectName("secondary_button")
        check_syntax_btn.clicked.connect(self._check_syntax)
        btn_layout.addWidget(check_syntax_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_debugging_widget(self) -> QWidget:
        """创建调试阶段组件"""
        widget = QWidget()
        widget.setObjectName("debugging_widget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("策略调试")
        header.setObjectName("section_header")
        layout.addWidget(header)

        self.debug_output = QTextEdit()
        self.debug_output.setReadOnly(True)
        self.debug_output.setObjectName("debug_output")
        layout.addWidget(self.debug_output)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        open_debugger_btn = QPushButton("打开调试器")
        open_debugger_btn.setObjectName("primary_button")
        open_debugger_btn.clicked.connect(self._open_debugger)
        btn_layout.addWidget(open_debugger_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_backtest_widget(self) -> QWidget:
        """创建回测阶段组件"""
        widget = QWidget()
        widget.setObjectName("backtest_widget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("策略回测")
        header.setObjectName("section_header")
        layout.addWidget(header)

        self.backtest_output = QTextEdit()
        self.backtest_output.setReadOnly(True)
        self.backtest_output.setObjectName("backtest_output")
        layout.addWidget(self.backtest_output)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        open_backtest_btn = QPushButton("打开回测系统")
        open_backtest_btn.setObjectName("primary_button")
        open_backtest_btn.clicked.connect(self._open_backtest)
        btn_layout.addWidget(open_backtest_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_optimization_widget(self) -> QWidget:
        """创建优化阶段组件"""
        widget = QWidget()
        widget.setObjectName("optimization_widget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("参数优化")
        header.setObjectName("section_header")
        layout.addWidget(header)

        self.optimization_output = QTextEdit()
        self.optimization_output.setReadOnly(True)
        self.optimization_output.setObjectName("optimization_output")
        layout.addWidget(self.optimization_output)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        open_optimization_btn = QPushButton("打开参数优化")
        open_optimization_btn.setObjectName("primary_button")
        open_optimization_btn.clicked.connect(self._open_optimization)
        btn_layout.addWidget(open_optimization_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_deployment_widget(self) -> QWidget:
        """创建部署阶段组件"""
        widget = QWidget()
        widget.setObjectName("deployment_widget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("策略部署")
        header.setObjectName("section_header")
        layout.addWidget(header)

        form_container = QWidget()
        form_container.setObjectName("form_container")
        form_layout = QFormLayout(form_container)
        form_layout.setSpacing(16)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        path_layout = QHBoxLayout()
        self.save_path_edit = QLineEdit()
        self.save_path_edit.setPlaceholderText("选择保存路径")
        self.save_path_edit.setObjectName("form_input")
        path_layout.addWidget(self.save_path_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("secondary_button")
        browse_btn.clicked.connect(self._browse_save_path)
        path_layout.addWidget(browse_btn)
        form_layout.addRow("保存路径:", path_layout)

        self.register_check = QCheckBox("注册到策略库")
        self.register_check.setChecked(True)
        self.register_check.setObjectName("form_checkbox")
        form_layout.addRow("", self.register_check)

        self.publish_check = QCheckBox("发布策略")
        self.publish_check.setChecked(False)
        self.publish_check.setObjectName("form_checkbox")
        form_layout.addRow("", self.publish_check)

        layout.addWidget(form_container)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        save_btn = QPushButton("保存策略")
        save_btn.setObjectName("primary_button")
        save_btn.clicked.connect(self._save_strategy)
        btn_layout.addWidget(save_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

        return widget

    def _create_footer(self) -> QWidget:
        """创建底部"""
        widget = QWidget()
        widget.setObjectName("workflow_footer")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)

        self.prev_btn = QPushButton("← 上一步")
        self.prev_btn.setObjectName("secondary_button")
        self.prev_btn.clicked.connect(self._prev_stage)
        layout.addWidget(self.prev_btn)

        layout.addStretch()

        self.next_btn = QPushButton("下一步 →")
        self.next_btn.setObjectName("primary_button")
        self.next_btn.clicked.connect(self._next_stage)
        layout.addWidget(self.next_btn)

        self.finish_btn = QPushButton("完成 ✓")
        self.finish_btn.setObjectName("success_button")
        self.finish_btn.clicked.connect(self._finish_workflow)
        self.finish_btn.setVisible(False)
        layout.addWidget(self.finish_btn)

        return widget

    def _apply_theme(self):
        if self.theme_manager:
            colors = self.theme_manager.get_theme_colors()
            bg_color = colors.get('background', '#f7f9fa')
            text_color = colors.get('text', '#222b45')
            border_color = colors.get('border', '#e0e0e0')
            highlight_color = colors.get('highlight', '#1976d2')
            success_color = colors.get('success', '#4CAF50')
            secondary_text = colors.get('chart_text', '#6272a4')
            sidebar_bg = colors.get('sidebar_bg', '#f3f6fa')
            card_bg = colors.get('main_content_bg', '#ffffff')
            input_bg = colors.get('chart_background', '#ffffff')
            
            self.setStyleSheet(f"""
                QWidget#workflow_header {{
                    background-color: {sidebar_bg};
                    border-bottom: 1px solid {border_color};
                }}
                QLabel#header_title {{
                    color: {highlight_color};
                    font-size: 18px;
                    font-weight: bold;
                }}
                QLabel#header_subtitle {{
                    color: {secondary_text};
                    font-size: 12px;
                }}
                QLabel#progress_title {{
                    color: {secondary_text};
                    font-size: 11px;
                }}
                QProgressBar {{
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    text-align: center;
                    background-color: {input_bg};
                    color: {text_color};
                    min-height: 8px;
                }}
                QProgressBar::chunk {{
                    background-color: {highlight_color};
                    border-radius: 3px;
                }}
                QWidget#stage_indicator_container {{
                    background-color: {card_bg};
                    border-bottom: 1px solid {border_color};
                }}
                QWidget#nav_panel {{
                    background-color: {sidebar_bg};
                    border-right: 1px solid {border_color};
                }}
                QLabel#nav_title {{
                    color: {text_color};
                    font-size: 14px;
                    font-weight: bold;
                }}
                QScrollArea#nav_scroll {{
                    border: none;
                    background-color: transparent;
                }}
                QLabel#section_header {{
                    color: {highlight_color};
                    font-size: 16px;
                    font-weight: bold;
                }}
                QWidget#form_container {{
                    background-color: {card_bg};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    padding: 16px;
                }}
                QLineEdit#form_input, QTextEdit#form_textarea, QComboBox#form_combo {{
                    background-color: {input_bg};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 8px;
                    min-height: 20px;
                }}
                QLineEdit#form_input:focus, QTextEdit#form_textarea:focus {{
                    border-color: {highlight_color};
                }}
                QPushButton#primary_button {{
                    background-color: {highlight_color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                }}
                QPushButton#primary_button:hover {{
                    background-color: {highlight_color}dd;
                }}
                QPushButton#secondary_button {{
                    background-color: transparent;
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    padding: 10px 20px;
                }}
                QPushButton#secondary_button:hover {{
                    background-color: {sidebar_bg};
                    border-color: {highlight_color};
                }}
                QPushButton#success_button {{
                    background-color: {success_color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                }}
                QPushButton#success_button:hover {{
                    background-color: {success_color}dd;
                }}
                QTextEdit#code_preview, QTextEdit#debug_output, 
                QTextEdit#backtest_output, QTextEdit#optimization_output {{
                    background-color: {input_bg};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    font-family: Consolas;
                    font-size: 11px;
                    padding: 8px;
                }}
                QWidget#workflow_footer {{
                    background-color: {sidebar_bg};
                    border-top: 1px solid {border_color};
                }}
                QCheckBox#form_checkbox {{
                    color: {text_color};
                    spacing: 8px;
                }}
                QCheckBox#form_checkbox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 1px solid {border_color};
                    border-radius: 3px;
                }}
                QCheckBox#form_checkbox::indicator:checked {{
                    background-color: {highlight_color};
                    border-color: {highlight_color};
                }}
            """)
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: #f7f9fa;
                    color: #222b45;
                }
            """)

    def _on_stage_indicator_clicked(self, index: int):
        stages = list(WorkflowStage)
        if 0 <= index < len(stages):
            self._set_stage(stages[index])

    def _on_stage_card_clicked(self, index: int):
        stages = list(WorkflowStage)
        if 0 <= index < len(stages):
            self._set_stage(stages[index])

    def _on_stage_changed(self, row: int):
        stages = list(WorkflowStage)
        if 0 <= row < len(stages):
            self._set_stage(stages[row])

    def _set_stage(self, stage: WorkflowStage):
        self.current_stage = stage
        self.stage_label.setText(f"当前阶段: {stage.value}")
        self.stage_changed.emit(stage.value)

        stage_index = list(WorkflowStage).index(stage)
        self.content_stack.setCurrentIndex(stage_index)
        self.stage_indicator.set_current_stage(stage_index)

        for i, card in enumerate(self.stage_cards):
            card.set_active(i == stage_index)

        self._update_button_states()
        self._update_progress()

    def _on_step_clicked(self, item: QListWidgetItem):
        step = item.data(Qt.UserRole)
        if step:
            logger.info(f"步骤点击: {step.name}")

    def _update_navigation(self):
        stage_index = list(WorkflowStage).index(self.current_stage)
        for i, card in enumerate(self.stage_cards):
            card.set_active(i == stage_index)
            card.set_completed(i < stage_index)
        self.stage_indicator.set_current_stage(stage_index)

    def _update_button_states(self):
        stages = list(WorkflowStage)
        current_index = stages.index(self.current_stage)
        
        self.prev_btn.setEnabled(current_index > 0)
        
        if current_index == len(stages) - 1:
            self.next_btn.setVisible(False)
            self.finish_btn.setVisible(True)
        else:
            self.next_btn.setVisible(True)
            self.finish_btn.setVisible(False)

    def _update_progress(self):
        stages = list(WorkflowStage)
        current_index = stages.index(self.current_stage)
        progress = int((current_index + 1) / len(stages) * 100)
        self.progress_bar.setValue(progress)

    def _prev_stage(self):
        stages = list(WorkflowStage)
        current_index = stages.index(self.current_stage)
        if current_index > 0:
            self._set_stage(stages[current_index - 1])

    def _next_stage(self):
        stages = list(WorkflowStage)
        current_index = stages.index(self.current_stage)
        if current_index < len(stages) - 1:
            self.stage_cards[current_index].set_completed(True)
            self.stage_indicator.set_completed(current_index, True)
            self._set_stage(stages[current_index + 1])

    def _finish_workflow(self):
        self.workflow_data = {
            'name': self.strategy_name_edit.text(),
            'description': self.strategy_desc_edit.toPlainText(),
            'indicator': self.indicator_combo.currentText(),
            'code': self.code_preview.toPlainText(),
        }
        self.workflow_completed.emit(self.workflow_data)
        QMessageBox.information(self, "完成", "策略开发工作流已完成！")

    def _open_code_editor(self):
        try:
            from gui.widgets.strategy_code_editor import StrategyCodeEditor
            from PyQt5.QtWidgets import QDialog
            
            dialog = QDialog(self)
            dialog.setWindowTitle("策略代码编辑器")
            dialog.resize(1200, 800)
            
            layout = QVBoxLayout(dialog)
            editor = StrategyCodeEditor(theme_manager=self.theme_manager)
            layout.addWidget(editor)
            
            dialog.exec_()
            
            self.code_preview.setPlainText(editor.code_editor.toPlainText())
            
        except Exception as e:
            logger.error(f"打开代码编辑器失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开代码编辑器: {e}")

    def _check_syntax(self):
        code = self.code_preview.toPlainText()
        try:
            compile(code, '<string>', 'exec')
            QMessageBox.information(self, "语法检查", "语法检查通过！")
        except SyntaxError as e:
            QMessageBox.warning(self, "语法错误", f"语法错误: {e}")

    def _open_debugger(self):
        try:
            from gui.widgets.strategy_debugger import StrategyDebugger
            from PyQt5.QtWidgets import QDialog
            
            dialog = QDialog(self)
            dialog.setWindowTitle("策略调试器")
            dialog.resize(1200, 800)
            
            layout = QVBoxLayout(dialog)
            debugger = StrategyDebugger()
            debugger.load_code(self.code_preview.toPlainText())
            layout.addWidget(debugger)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"打开调试器失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开调试器: {e}")

    def _open_backtest(self):
        try:
            from gui.widgets.backtest_widget import ProfessionalBacktestWidget
            from PyQt5.QtWidgets import QDialog
            
            dialog = QDialog(self)
            dialog.setWindowTitle("专业回测系统")
            dialog.resize(1400, 900)
            
            layout = QVBoxLayout(dialog)
            backtest = ProfessionalBacktestWidget()
            layout.addWidget(backtest)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"打开回测系统失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开回测系统: {e}")

    def _open_optimization(self):
        try:
            from gui.dialogs.enhanced_strategy_manager_dialog import EnhancedStrategyManagerDialog
            
            dialog = EnhancedStrategyManagerDialog(self)
            dialog._switch_view('optimization')
            dialog.show()
            
        except Exception as e:
            logger.error(f"打开参数优化失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开参数优化: {e}")

    def _browse_save_path(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存策略", "", "Python 文件 (*.py)"
        )
        if file_path:
            self.save_path_edit.setText(file_path)

    def _save_strategy(self):
        try:
            save_path = self.save_path_edit.text()
            if not save_path:
                QMessageBox.warning(self, "警告", "请选择保存路径")
                return
            
            code = self.code_preview.toPlainText()
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            if self.register_check.isChecked():
                try:
                    from core.strategy.strategy_registry import StrategyRegistry
                    from core.containers import get_service_container
                    
                    container = get_service_container()
                    registry = container.resolve(StrategyRegistry)
                    
                    strategy_name = self.strategy_name_edit.text()
                    if strategy_name:
                        logger.info(f"策略已注册: {strategy_name}")
                
                except Exception as e:
                    logger.warning(f"注册策略失败: {e}")
            
            QMessageBox.information(self, "成功", f"策略已保存到: {save_path}")
            
            self.workflow_data = {
                'name': self.strategy_name_edit.text(),
                'description': self.strategy_desc_edit.toPlainText(),
                'indicator': self.indicator_combo.currentText(),
                'code': code,
                'save_path': save_path,
                'registered': self.register_check.isChecked(),
                'published': self.publish_check.isChecked()
            }
            
            self.workflow_completed.emit(self.workflow_data)
            
        except Exception as e:
            logger.error(f"保存策略失败: {e}")
            QMessageBox.critical(self, "错误", f"保存策略失败: {e}")
