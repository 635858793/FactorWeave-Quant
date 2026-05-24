"""
系统优化器对话框

提供系统优化器的图形界面，包括优化设置、进度监控、结果展示等功能。
"""

from loguru import logger
import asyncio
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QFormLayout, QComboBox, QSpinBox, QCheckBox,
    QListWidget, QPushButton, QTextEdit, QLabel, QDialogButtonBox,
    QMessageBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QSplitter, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap

from core.services.system_optimizer import (
    SystemOptimizerService,
    OptimizationLevel,
    OptimizationConfig,
    OptimizationResult
)
from .base_dialog import BaseDialog

logger = logger


class OptimizationWorker(QThread):
    """维护工作线程"""

    progress_updated = pyqtSignal(str, float)
    status_updated = pyqtSignal(str)
    optimization_completed = pyqtSignal(object)
    optimization_failed = pyqtSignal(str)

    def __init__(self, optimizer_service: SystemOptimizerService,
                 optimization_level: OptimizationLevel):
        super().__init__()
        self.optimizer_service = optimizer_service
        self.optimization_level = optimization_level
        self._is_running = False

    def run(self):
        """运行优化"""
        self._is_running = True
        try:
            # 设置回调函数
            self.optimizer_service.set_progress_callback(self._on_progress)
            self.optimizer_service.set_status_callback(self._on_status)

            # 运行异步优化
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.optimizer_service.run_full_optimization(
                    self.optimization_level)
            )

            if self._is_running:
                self.optimization_completed.emit(result)

        except Exception as e:
            if self._is_running:
                self.optimization_failed.emit(str(e))
        finally:
            self._is_running = False

    def _on_progress(self, message: str, progress: float):
        """进度回调"""
        if self._is_running:
            self.progress_updated.emit(message, progress)

    def _on_status(self, status: str):
        """状态回调"""
        if self._is_running:
            self.status_updated.emit(status)

    def stop(self):
        """停止优化"""
        self._is_running = False
        self.requestInterruption()
        self.quit()
        self.wait(5000)


class SystemOptimizerDialog(BaseDialog):
    """系统维护工具对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        self.optimizer_service = None  # 延迟创建
        self.worker = None
        self.current_result = None

        super().__init__(
            parent,
            title="系统维护工具",
            min_size=(900, 700),
            settings_key="SystemOptimizerDialog"
        )

        # 设置样式
        self._setup_styles()

        # 创建UI
        self._create_widgets()

        # 初始化优化器服务
        self._init_optimizer_service()

        # 连接信号
        self._connect_signals()

    def _setup_styles(self):
        """设置样式"""
        self.setStyleSheet("""
            QDialog {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                background-color: #f8f9fa;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                background-color: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
            QProgressBar {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 3px;
            }
        """)

    def _create_widgets(self):
        """创建UI组件"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 创建各个选项卡
        self._create_optimization_tab()
        self._create_analysis_tab()
        self._create_history_tab()
        self._create_settings_tab()

        # 创建按钮
        self._create_buttons(main_layout)

    def _create_optimization_tab(self):
        """创建优化选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 维护级别选择
        level_group = QGroupBox("维护级别")
        level_layout = QFormLayout(level_group)

        self.level_combo = QComboBox()
        self.level_combo.addItems([
            "轻度维护 (LIGHT)",
            "中度维护 (MEDIUM)",
            "深度维护 (DEEP)",
            "自定义维护 (CUSTOM)"
        ])
        self.level_combo.setCurrentIndex(1)  # 默认中度维护
        level_layout.addRow("维护级别:", self.level_combo)

        # 维护选项
        options_group = QGroupBox("维护选项")
        options_layout = QFormLayout(options_group)

        self.clean_cache_cb = QCheckBox("清理缓存文件")
        self.clean_cache_cb.setChecked(True)
        options_layout.addRow("", self.clean_cache_cb)

        self.clean_temp_cb = QCheckBox("清理临时文件")
        self.clean_temp_cb.setChecked(True)
        options_layout.addRow("", self.clean_temp_cb)

        self.clean_logs_cb = QCheckBox("清理过期日志")
        self.clean_logs_cb.setChecked(True)
        options_layout.addRow("", self.clean_logs_cb)

        self.optimize_imports_cb = QCheckBox("优化导入语句")
        self.optimize_imports_cb.setChecked(True)
        options_layout.addRow("", self.optimize_imports_cb)

        self.optimize_memory_cb = QCheckBox("内存优化")
        self.optimize_memory_cb.setChecked(True)
        options_layout.addRow("", self.optimize_memory_cb)

        self.backup_cb = QCheckBox("维护前备份")
        self.backup_cb.setChecked(True)
        options_layout.addRow("", self.backup_cb)

        # 高级设置
        advanced_group = QGroupBox("高级设置")
        advanced_layout = QFormLayout(advanced_group)

        self.log_retention_spin = QSpinBox()
        self.log_retention_spin.setRange(1, 365)
        self.log_retention_spin.setValue(30)
        self.log_retention_spin.setSuffix("天")
        advanced_layout.addRow("日志保留天数:", self.log_retention_spin)

        self.max_file_size_spin = QSpinBox()
        self.max_file_size_spin.setRange(1, 1000)
        self.max_file_size_spin.setValue(100)
        self.max_file_size_spin.setSuffix("MB")
        advanced_layout.addRow("大文件阈值:", self.max_file_size_spin)

        # 进度显示
        progress_group = QGroupBox("维护进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("准备就绪")
        progress_layout.addWidget(self.status_label)

        self.progress_text = QTextEdit()
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setReadOnly(True)
        progress_layout.addWidget(self.progress_text)

        # 添加到布局
        layout.addWidget(level_group)
        layout.addWidget(options_group)
        layout.addWidget(advanced_group)
        layout.addWidget(progress_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "维护设置")

    def _create_analysis_tab(self):
        """创建分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 分析结果显示
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        layout.addWidget(self.analysis_text)

        # 分析按钮
        analyze_btn = QPushButton("分析系统")
        analyze_btn.clicked.connect(self._analyze_system)
        layout.addWidget(analyze_btn)

        self.tab_widget.addTab(tab, "系统分析")

    def _create_history_tab(self):
        """创建历史选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "级别", "文件清理", "文件优化", "释放空间", "耗时"
        ])
        layout.addWidget(self.history_table)

        # 刷新按钮
        refresh_btn = QPushButton("刷新历史")
        refresh_btn.clicked.connect(self._refresh_history)
        layout.addWidget(refresh_btn)

        self.tab_widget.addTab(tab, "维护历史")

    def _create_settings_tab(self):
        """创建设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 排除模式设置
        exclude_group = QGroupBox("排除模式")
        exclude_layout = QVBoxLayout(exclude_group)

        self.exclude_text = QTextEdit()
        self.exclude_text.setPlainText("\n".join([
            "__pycache__",
            ".git",
            ".pytest_cache",
            "node_modules",
            ".vscode",
            ".idea",
            "*.pyc",
            "*.pyo",
            ".DS_Store"
        ]))
        exclude_layout.addWidget(self.exclude_text)

        layout.addWidget(exclude_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "高级设置")

    def _create_buttons(self, layout):
        """创建按钮"""
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("开始维护")
        self.start_btn.clicked.connect(self._start_optimization)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止维护")
        self.stop_btn.clicked.connect(self._stop_optimization)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _init_optimizer_service(self):
        """初始化维护服务"""
        try:
            # 创建服务实例
            self.optimizer_service = SystemOptimizerService()

            # 检查是否已有事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用线程池执行
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._init_service_in_thread)
                        future.result()
                else:
                    loop.run_until_complete(
                        self.optimizer_service.initialize_async())
            except RuntimeError:
                # 没有事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self.optimizer_service.initialize_async())

            logger.info("系统维护服务初始化成功")
        except Exception as e:
            logger.error(f"系统维护服务初始化失败: {e}")
            QMessageBox.critical(self, "错误", f"初始化失败: {e}")

    def _init_service_in_thread(self):
        """在新线程中初始化服务"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.optimizer_service.initialize_async())
        finally:
            loop.close()

    def _analyze_in_thread(self):
        """在新线程中分析系统"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.optimizer_service.analyze_system())
        finally:
            loop.close()

    def _get_suggestions_in_thread(self):
        """在新线程中获取建议"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.optimizer_service.get_optimization_suggestions())
        finally:
            loop.close()

    def _connect_signals(self):
        """连接信号"""
        self.level_combo.currentTextChanged.connect(self._on_level_changed)

    def _on_level_changed(self, text: str):
        """维护级别改变"""
        is_custom = "CUSTOM" in text

        # 根据级别启用/禁用选项
        self.clean_cache_cb.setEnabled(is_custom)
        self.clean_temp_cb.setEnabled(is_custom)
        self.clean_logs_cb.setEnabled(is_custom)
        self.optimize_imports_cb.setEnabled(is_custom)
        self.optimize_memory_cb.setEnabled(is_custom)

    def _start_optimization(self):
        """开始维护"""
        if self.worker and self.worker.isRunning():
            return

        try:
            # 获取维护级别
            level_text = self.level_combo.currentText()
            if "LIGHT" in level_text:
                level = OptimizationLevel.LIGHT
            elif "MEDIUM" in level_text:
                level = OptimizationLevel.MEDIUM
            elif "DEEP" in level_text:
                level = OptimizationLevel.DEEP
            else:
                level = OptimizationLevel.CUSTOM

                # 设置自定义配置
                config = OptimizationConfig(
                    level=level,
                    clean_cache=self.clean_cache_cb.isChecked(),
                    clean_temp_files=self.clean_temp_cb.isChecked(),
                    clean_logs=self.clean_logs_cb.isChecked(),
                    optimize_imports=self.optimize_imports_cb.isChecked(),
                    optimize_memory=self.optimize_memory_cb.isChecked(),
                    backup_before_optimize=self.backup_cb.isChecked(),
                    log_retention_days=self.log_retention_spin.value(),
                    max_file_size_mb=self.max_file_size_spin.value()
                )
                self.optimizer_service.update_optimization_config(config)

            # 创建工作线程
            self.worker = OptimizationWorker(self.optimizer_service, level)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.status_updated.connect(self._on_status_updated)
            self.worker.optimization_completed.connect(
                self._on_optimization_completed)
            self.worker.optimization_failed.connect(
                self._on_optimization_failed)

            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_text.clear()

            # 启动维护
            self.worker.start()

        except Exception as e:
            logger.error(f"启动维护失败: {e}")
            QMessageBox.critical(self, "错误", f"启动维护失败: {e}")

    def _stop_optimization(self):
        """停止维护"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        self._reset_ui_state()

    def _on_progress_updated(self, message: str, progress: float):
        """更新进度"""
        self.progress_bar.setValue(int(progress * 100))
        self.progress_text.append(f"{message}")

        # 自动滚动到底部
        cursor = self.progress_text.textCursor()
        cursor.movePosition(cursor.End)
        self.progress_text.setTextCursor(cursor)

    def _on_status_updated(self, status: str):
        """更新状态"""
        self.status_label.setText(status)

    def _on_optimization_completed(self, result: OptimizationResult):
        """维护完成"""
        self.current_result = result
        self._reset_ui_state()

        # 显示结果
        message = f"""
维护完成！

维护级别: {result.level.value}
耗时: {result.duration.total_seconds():.2f} 秒
清理文件: {result.files_cleaned} 个
优化文件: {result.files_optimized} 个
释放空间: {result.bytes_freed / 1024 / 1024:.2f} MB
成功率: {result.success_rate:.2%}
"""
        QMessageBox.information(self, "维护完成", message)

        # 刷新历史
        self._refresh_history()

    def _on_optimization_failed(self, error: str):
        """维护失败"""
        self._reset_ui_state()
        QMessageBox.critical(self, "维护失败", f"维护过程中发生错误: {error}")

    def _reset_ui_state(self):
        """重置UI状态"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("准备就绪")

    def _analyze_system(self):
        """分析系统"""
        self.analysis_text.clear()
        self.analysis_text.append("正在分析系统...")

        try:
            # 检查是否已有事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用线程池执行
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._analyze_in_thread)
                        analysis = future.result()
                else:
                    analysis = loop.run_until_complete(
                        self.optimizer_service.analyze_system())
            except RuntimeError:
                # 没有事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                analysis = loop.run_until_complete(
                    self.optimizer_service.analyze_system())

            # 显示分析结果
            text = f"""
系统分析报告
============

文件统计:
- 总文件数: {analysis['total_files']}
- Python文件数: {analysis['python_files']}
- 大文件数: {len(analysis['large_files'])}
- 空文件数: {len(analysis['empty_files'])}
- 缓存文件数: {len(analysis['cache_files'])}
- 临时文件数: {len(analysis['temp_files'])}

"""

            if analysis['performance_issues']:
                text += "性能问题:\n"
                for issue in analysis['performance_issues']:
                    text += f"- {issue['description']}\n"
                text += "\n"

            if analysis['security_issues']:
                text += "安全问题:\n"
                for issue in analysis['security_issues']:
                    text += f"- {issue['description']}\n"
                text += "\n"

            # 获取优化建议
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            self._get_suggestions_in_thread)
                        suggestions = future.result()
                else:
                    suggestions = loop.run_until_complete(
                        self.optimizer_service.get_optimization_suggestions()
                    )
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                suggestions = loop.run_until_complete(
                    self.optimizer_service.get_optimization_suggestions()
                )

            if suggestions:
                text += "优化建议:\n"
                for suggestion in suggestions:
                    text += f"- {suggestion}\n"

            self.analysis_text.setPlainText(text)

        except Exception as e:
            logger.error(f"系统分析失败: {e}")
            self.analysis_text.setPlainText(f"分析失败: {e}")

    def _refresh_history(self):
        """刷新历史记录"""
        try:
            history = self.optimizer_service.optimization_history

            self.history_table.setRowCount(len(history))

            for i, result in enumerate(history):
                self.history_table.setItem(i, 0, QTableWidgetItem(
                    result.start_time.strftime("%Y-%m-%d %H:%M")
                ))
                self.history_table.setItem(i, 1, QTableWidgetItem(
                    result.level.value
                ))
                self.history_table.setItem(i, 2, QTableWidgetItem(
                    str(result.files_cleaned)
                ))
                self.history_table.setItem(i, 3, QTableWidgetItem(
                    str(result.files_optimized)
                ))
                self.history_table.setItem(i, 4, QTableWidgetItem(
                    f"{result.bytes_freed / 1024 / 1024:.2f} MB"
                ))
                self.history_table.setItem(i, 5, QTableWidgetItem(
                    f"{result.duration.total_seconds():.2f}s"
                ))

            self.history_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"刷新历史失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认", "优化正在进行中，确定要关闭吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.worker.wait()
                super().closeEvent(event)
                event.accept()
            else:
                event.ignore()
        else:
            super().closeEvent(event)
            event.accept()

    def __del__(self):
        """析构函数"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.optimizer_service.dispose_async())
        except Exception as e:
            logger.error(f"清理优化器服务失败: {e}")


def show_system_optimizer_dialog(parent: Optional[QWidget] = None) -> None:
    """显示系统维护工具对话框"""
    dialog = SystemOptimizerDialog(parent)
    dialog.exec_()
