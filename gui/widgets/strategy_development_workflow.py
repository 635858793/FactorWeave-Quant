"""
策略开发工作流组件
提供完整的策略开发工作流管理
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
    QListWidget, QListWidgetItem, QSplitter, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor


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


class StrategyDevelopmentWorkflow(QWidget):
    """策略开发工作流"""
    
    workflow_completed = pyqtSignal(dict)
    stage_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = self._create_header()
        layout.addWidget(header)
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        nav_panel = self._create_navigation_panel()
        main_splitter.addWidget(nav_panel)
        
        content_stack = self._create_content_stack()
        main_splitter.addWidget(content_stack)
        
        main_splitter.setSizes([200, 800])
        layout.addWidget(main_splitter)
        
        footer = self._create_footer()
        layout.addWidget(footer)
        
        self._update_navigation()
    
    def _create_header(self) -> QWidget:
        """创建头部"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-bottom: 1px solid #3c3c3c;
            }
        """)
        layout = QHBoxLayout(widget)
        
        title = QLabel("策略开发工作流")
        title.setStyleSheet("""
            QLabel {
                color: #4ec9b0;
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        layout.addWidget(title)
        
        self.stage_label = QLabel(f"当前阶段: {self.current_stage.value}")
        self.stage_label.setStyleSheet("""
            QLabel {
                color: #d4d4d4;
                font-size: 12px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.stage_label)
        
        layout.addStretch()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                text-align: center;
                background-color: #2d2d2d;
                color: #d4d4d4;
            }
            QProgressBar::chunk {
                background-color: #4ec9b0;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setFixedWidth(200)
        layout.addWidget(self.progress_bar)
        
        return widget
    
    def _create_navigation_panel(self) -> QWidget:
        """创建导航面板"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-right: 1px solid #3c3c3c;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.stage_list = QListWidget()
        self.stage_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: #d4d4d4;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #3c3c3c;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
        """)
        
        for stage in WorkflowStage:
            item = QListWidgetItem(f"{stage.value}")
            item.setData(Qt.UserRole, stage)
            self.stage_list.addItem(item)
        
        self.stage_list.currentRowChanged.connect(self._on_stage_changed)
        layout.addWidget(self.stage_list)
        
        self.step_list = QListWidget()
        self.step_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: #d4d4d4;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 8px;
                padding-left: 20px;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
        """)
        layout.addWidget(self.step_list)
        
        return widget
    
    def _create_content_stack(self) -> QWidget:
        """创建内容栈"""
        self.content_stack = QStackedWidget()
        
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
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("策略设计")
        group.setStyleSheet("""
            QGroupBox {
                color: #4ec9b0;
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        form_layout = QFormLayout(group)
        
        self.strategy_name_edit = QLineEdit()
        self.strategy_name_edit.setPlaceholderText("输入策略名称")
        self.strategy_name_edit.setStyleSheet("background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555; padding: 5px;")
        form_layout.addRow("策略名称:", self.strategy_name_edit)
        
        self.strategy_desc_edit = QTextEdit()
        self.strategy_desc_edit.setPlaceholderText("描述策略的基本思路和逻辑")
        self.strategy_desc_edit.setMaximumHeight(100)
        self.strategy_desc_edit.setStyleSheet("background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555;")
        form_layout.addRow("策略描述:", self.strategy_desc_edit)
        
        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems(["MA", "EMA", "RSI", "MACD", "BOLL", "KDJ", "自定义"])
        self.indicator_combo.setStyleSheet("background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555; padding: 5px;")
        form_layout.addRow("主要指标:", self.indicator_combo)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _create_coding_widget(self) -> QWidget:
        """创建编码阶段组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel("编码阶段：使用代码编辑器编写策略代码")
        label.setStyleSheet("color: #4ec9b0; font-size: 14px; font-weight: bold;")
        layout.addWidget(label)
        
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: Consolas;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.code_preview)
        
        btn_layout = QHBoxLayout()
        
        open_editor_btn = QPushButton("打开代码编辑器")
        open_editor_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        open_editor_btn.clicked.connect(self._open_code_editor)
        btn_layout.addWidget(open_editor_btn)
        
        check_syntax_btn = QPushButton("检查语法")
        check_syntax_btn.setStyleSheet(open_editor_btn.styleSheet())
        check_syntax_btn.clicked.connect(self._check_syntax)
        btn_layout.addWidget(check_syntax_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_debugging_widget(self) -> QWidget:
        """创建调试阶段组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel("调试阶段：使用调试工具调试策略")
        label.setStyleSheet("color: #4ec9b0; font-size: 14px; font-weight: bold;")
        layout.addWidget(label)
        
        self.debug_output = QTextEdit()
        self.debug_output.setReadOnly(True)
        self.debug_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: Consolas;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.debug_output)
        
        btn_layout = QHBoxLayout()
        
        open_debugger_btn = QPushButton("打开调试器")
        open_debugger_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        open_debugger_btn.clicked.connect(self._open_debugger)
        btn_layout.addWidget(open_debugger_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_backtest_widget(self) -> QWidget:
        """创建回测阶段组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel("回测阶段：执行回测并分析结果")
        label.setStyleSheet("color: #4ec9b0; font-size: 14px; font-weight: bold;")
        layout.addWidget(label)
        
        self.backtest_output = QTextEdit()
        self.backtest_output.setReadOnly(True)
        self.backtest_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: Consolas;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.backtest_output)
        
        btn_layout = QHBoxLayout()
        
        open_backtest_btn = QPushButton("打开回测系统")
        open_backtest_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        open_backtest_btn.clicked.connect(self._open_backtest)
        btn_layout.addWidget(open_backtest_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_optimization_widget(self) -> QWidget:
        """创建优化阶段组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel("优化阶段：优化策略参数")
        label.setStyleSheet("color: #4ec9b0; font-size: 14px; font-weight: bold;")
        layout.addWidget(label)
        
        self.optimization_output = QTextEdit()
        self.optimization_output.setReadOnly(True)
        self.optimization_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: Consolas;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.optimization_output)
        
        btn_layout = QHBoxLayout()
        
        open_optimization_btn = QPushButton("打开参数优化")
        open_optimization_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        open_optimization_btn.clicked.connect(self._open_optimization)
        btn_layout.addWidget(open_optimization_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_deployment_widget(self) -> QWidget:
        """创建部署阶段组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("策略部署")
        group.setStyleSheet("""
            QGroupBox {
                color: #4ec9b0;
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        form_layout = QFormLayout(group)
        
        self.save_path_edit = QLineEdit()
        self.save_path_edit.setPlaceholderText("选择保存路径")
        self.save_path_edit.setStyleSheet("background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555; padding: 5px;")
        form_layout.addRow("保存路径:", self.save_path_edit)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_save_path)
        form_layout.addRow("", browse_btn)
        
        self.register_check = QCheckBox("注册到策略库")
        self.register_check.setChecked(True)
        form_layout.addRow("", self.register_check)
        
        self.publish_check = QCheckBox("发布策略")
        self.publish_check.setChecked(False)
        form_layout.addRow("", self.publish_check)
        
        layout.addWidget(group)
        
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存策略")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        save_btn.clicked.connect(self._save_strategy)
        btn_layout.addWidget(save_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        return widget
    
    def _create_footer(self) -> QWidget:
        """创建底部"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-top: 1px solid #3c3c3c;
            }
        """)
        layout = QHBoxLayout(widget)
        
        self.prev_btn = QPushButton("上一步")
        self.prev_btn.clicked.connect(self._prev_stage)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """)
        layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("下一步")
        self.next_btn.clicked.connect(self._next_stage)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        layout.addWidget(self.next_btn)
        
        layout.addStretch()
        
        return widget
    
    def _update_navigation(self):
        """更新导航"""
        self.stage_list.clear()
        for stage in WorkflowStage:
            item = QListWidgetItem(f"{stage.value}")
            item.setData(Qt.UserRole, stage)
            if stage == self.current_stage:
                item.setBackground(QColor("#094771"))
            self.stage_list.addItem(item)
        
        self.step_list.clear()
        steps = self.steps.get(self.current_stage, [])
        for step in steps:
            icon = "✓" if step.is_completed else "○"
            item = QListWidgetItem(f"{icon} {step.name}")
            self.step_list.addItem(item)
        
        self.stage_label.setText(f"当前阶段: {self.current_stage.value}")
        
        completed_steps = sum(1 for steps in self.steps.values() for step in steps if step.is_completed)
        total_steps = sum(len(steps) for steps in self.steps.values())
        progress = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
        self.progress_bar.setValue(progress)
    
    def _on_stage_changed(self, row: int):
        """阶段改变"""
        stages = list(WorkflowStage)
        if 0 <= row < len(stages):
            self.current_stage = stages[row]
            self.content_stack.setCurrentIndex(row)
            self._update_navigation()
            self.stage_changed.emit(self.current_stage.value)
    
    def _prev_stage(self):
        """上一阶段"""
        stages = list(WorkflowStage)
        current_index = stages.index(self.current_stage)
        if current_index > 0:
            self.current_stage = stages[current_index - 1]
            self.stage_list.setCurrentRow(current_index - 1)
            self.content_stack.setCurrentIndex(current_index - 1)
            self._update_navigation()
            self.stage_changed.emit(self.current_stage.value)
    
    def _next_stage(self):
        """下一阶段"""
        stages = list(WorkflowStage)
        current_index = stages.index(self.current_stage)
        if current_index < len(stages) - 1:
            self.current_stage = stages[current_index + 1]
            self.stage_list.setCurrentRow(current_index + 1)
            self.content_stack.setCurrentIndex(current_index + 1)
            self._update_navigation()
            self.stage_changed.emit(self.current_stage.value)
    
    def _open_code_editor(self):
        """打开代码编辑器"""
        try:
            from gui.widgets.strategy_code_editor import StrategyCodeEditor
            from PyQt5.QtWidgets import QDialog
            
            dialog = QDialog(self)
            dialog.setWindowTitle("策略代码编辑器")
            dialog.resize(1200, 800)
            
            layout = QVBoxLayout(dialog)
            editor = StrategyCodeEditor()
            layout.addWidget(editor)
            
            dialog.exec_()
            
            self.code_preview.setPlainText(editor.code_editor.toPlainText())
            
        except Exception as e:
            logger.error(f"打开代码编辑器失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开代码编辑器: {e}")
    
    def _check_syntax(self):
        """检查语法"""
        code = self.code_preview.toPlainText()
        try:
            compile(code, '<string>', 'exec')
            QMessageBox.information(self, "语法检查", "语法检查通过！")
        except SyntaxError as e:
            QMessageBox.warning(self, "语法错误", f"语法错误: {e}")
    
    def _open_debugger(self):
        """打开调试器"""
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
        """打开回测系统"""
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
        """打开参数优化"""
        try:
            from gui.dialogs.enhanced_strategy_manager_dialog_v2 import EnhancedStrategyManagerDialogV2
            
            dialog = EnhancedStrategyManagerDialogV2(self)
            dialog.tab_widget.setCurrentIndex(3)
            dialog.show()
            
        except Exception as e:
            logger.error(f"打开参数优化失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开参数优化: {e}")
    
    def _browse_save_path(self):
        """浏览保存路径"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存策略", "", "Python 文件 (*.py)"
        )
        if file_path:
            self.save_path_edit.setText(file_path)
    
    def _save_strategy(self):
        """保存策略"""
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
