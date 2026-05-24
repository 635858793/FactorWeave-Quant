from loguru import logger
"""
系统优化器面板

提供系统优化器的面板组件，可以集成到主窗口中
"""

import asyncio
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QSpinBox, QPushButton, QProgressBar,
    QLabel, QTextEdit, QMessageBox, QSplitter, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont

from core.services.system_optimizer import (
    SystemOptimizerService,
    OptimizationLevel,
    OptimizationConfig,
    OptimizationResult
)

logger = logger

class SystemOptimizerPanel(QWidget):
    """系统维护工具面板"""

    # 信号
    optimization_started = pyqtSignal()
    optimization_completed = pyqtSignal(object)
    optimization_failed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.optimizer_service = None  # 延迟创建
        self.worker = None
        self.current_result = None

        # 设置面板属性
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)

        # 创建UI
        self._create_widgets()

        # 初始化服务
        self._init_service()

        # 连接信号
        self._connect_signals()

    def _create_widgets(self):
        """创建UI组件"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        title_label = QLabel("系统维护工具")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # 上半部分：控制面板
        control_widget = self._create_control_panel()
        splitter.addWidget(control_widget)

        # 下半部分：状态面板
        status_widget = self._create_status_panel()
        splitter.addWidget(status_widget)

        # 设置分割器比例
        splitter.setSizes([300, 200])

    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 维护级别选择
        level_group = QGroupBox("维护级别")
        level_layout = QFormLayout(level_group)

        self.level_combo = QComboBox()
        self.level_combo.addItems([
            "轻度维护",
            "中度维护",
            "深度维护",
            "自定义维护"
        ])
        self.level_combo.setCurrentIndex(1)  # 默认中度维护
        level_layout.addRow("级别:", self.level_combo)

        layout.addWidget(level_group)

        # 维护选项（仅在自定义模式下启用）
        options_group = QGroupBox("维护选项")
        options_layout = QFormLayout(options_group)

        self.clean_cache_cb = QCheckBox("清理缓存文件")
        self.clean_cache_cb.setChecked(True)
        self.clean_cache_cb.setEnabled(False)
        options_layout.addRow("", self.clean_cache_cb)

        self.clean_temp_cb = QCheckBox("清理临时文件")
        self.clean_temp_cb.setChecked(True)
        self.clean_temp_cb.setEnabled(False)
        options_layout.addRow("", self.clean_temp_cb)

        self.clean_logs_cb = QCheckBox("清理过期日志")
        self.clean_logs_cb.setChecked(True)
        self.clean_logs_cb.setEnabled(False)
        options_layout.addRow("", self.clean_logs_cb)

        self.optimize_memory_cb = QCheckBox("内存优化")
        self.optimize_memory_cb.setChecked(True)
        self.optimize_memory_cb.setEnabled(False)
        options_layout.addRow("", self.optimize_memory_cb)

        layout.addWidget(options_group)

        # 快捷操作按钮
        button_layout = QHBoxLayout()

        self.quick_clean_btn = QPushButton("快速清理")
        self.quick_clean_btn.setToolTip("快速清理缓存和临时文件")
        button_layout.addWidget(self.quick_clean_btn)

        self.analyze_btn = QPushButton("系统分析")
        self.analyze_btn.setToolTip("分析系统状态")
        button_layout.addWidget(self.analyze_btn)

        layout.addLayout(button_layout)

        # 主要操作按钮
        main_button_layout = QHBoxLayout()

        self.start_btn = QPushButton("开始维护")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        main_button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止维护")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        main_button_layout.addWidget(self.stop_btn)

        layout.addLayout(main_button_layout)

        return widget

    def _create_status_panel(self) -> QWidget:
        """创建状态面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 状态信息
        status_group = QGroupBox("维护状态")
        status_layout = QVBoxLayout(status_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("准备就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)

        # 统计信息
        stats_layout = QHBoxLayout()

        self.files_cleaned_label = QLabel("清理文件: 0")
        stats_layout.addWidget(self.files_cleaned_label)

        self.space_freed_label = QLabel("释放空间: 0 MB")
        stats_layout.addWidget(self.space_freed_label)

        self.time_elapsed_label = QLabel("耗时: 0s")
        stats_layout.addWidget(self.time_elapsed_label)

        status_layout.addLayout(stats_layout)

        layout.addWidget(status_group)

        # 日志输出
        log_group = QGroupBox("维护日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(120)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
            }
        """)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        return widget

    def _init_service(self):
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

            self._log_message("系统维护服务初始化成功")
        except Exception as e:
            self._log_message(f"初始化失败: {e}", "error")
            logger.error(f"系统维护服务初始化失败: {e}")

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
        self.start_btn.clicked.connect(self._start_optimization)
        self.stop_btn.clicked.connect(self._stop_optimization)
        self.quick_clean_btn.clicked.connect(self._quick_clean)
        self.analyze_btn.clicked.connect(self._analyze_system)

    def _on_level_changed(self, text: str):
        """维护级别改变"""
        is_custom = "自定义" in text

        # 根据级别启用/禁用选项
        self.clean_cache_cb.setEnabled(is_custom)
        self.clean_temp_cb.setEnabled(is_custom)
        self.clean_logs_cb.setEnabled(is_custom)
        self.optimize_memory_cb.setEnabled(is_custom)

    def _start_optimization(self):
        """开始维护"""
        if self.worker and self.worker.isRunning():
            return

        try:
            # 获取维护级别
            level_text = self.level_combo.currentText()
            if "轻度" in level_text:
                level = OptimizationLevel.LIGHT
            elif "中度" in level_text:
                level = OptimizationLevel.MEDIUM
            elif "深度" in level_text:
                level = OptimizationLevel.DEEP
            else:
                level = OptimizationLevel.CUSTOM

                # 设置自定义配置
                config = OptimizationConfig(
                    level=level,
                    clean_cache=self.clean_cache_cb.isChecked(),
                    clean_temp_files=self.clean_temp_cb.isChecked(),
                    clean_logs=self.clean_logs_cb.isChecked(),
                    optimize_memory=self.optimize_memory_cb.isChecked()
                )
                self.optimizer_service.update_optimization_config(config)

            # 创建工作线程
            from gui.dialogs.system_optimizer_dialog import OptimizationWorker
            self.worker = OptimizationWorker(self.optimizer_service, level)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.status_updated.connect(self._on_status_updated)
            self.worker.optimization_completed.connect(
                self._on_optimization_completed)
            self.worker.optimization_failed.connect(
                self._on_optimization_failed)

            # 更新UI状态
            self._update_ui_state(True)

            # 启动维护
            self.worker.start()
            self.optimization_started.emit()

        except Exception as e:
            self._log_message(f"启动维护失败: {e}", "error")
            logger.error(f"启动维护失败: {e}")

    def _stop_optimization(self):
        """停止维护"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        self._update_ui_state(False)
        self._log_message("维护已停止")

    def _quick_clean(self):
        """快速清理"""
        self.level_combo.setCurrentIndex(0)  # 轻度维护
        self._start_optimization()

    def _analyze_system(self):
        """分析系统"""
        self._log_message("正在分析系统状态...")

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
            message = f"""
系统分析完成：
- 总文件数: {analysis['total_files']}
- Python文件数: {analysis['python_files']}
- 大文件数: {len(analysis['large_files'])}
- 缓存文件数: {len(analysis['cache_files'])}
- 临时文件数: {len(analysis['temp_files'])}
"""
            self._log_message(message)

            # 获取维护建议
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
                self._log_message("维护建议:")
                for suggestion in suggestions[:3]:  # 只显示前3个建议
                    self._log_message(f"- {suggestion}")

        except Exception as e:
            self._log_message(f"系统分析失败: {e}", "error")
            logger.error(f"系统分析失败: {e}")

    def _on_progress_updated(self, message: str, progress: float):
        """更新进度"""
        self.progress_bar.setValue(int(progress * 100))
        self._log_message(f"进度 {progress:.1%}: {message}")

    def _on_status_updated(self, status: str):
        """更新状态"""
        self.status_label.setText(status)

    def _on_optimization_completed(self, result: OptimizationResult):
        """维护完成"""
        self.current_result = result
        self._update_ui_state(False)

        # 更新统计信息
        self.files_cleaned_label.setText(f"清理文件: {result.files_cleaned}")
        self.space_freed_label.setText(
            f"释放空间: {result.bytes_freed / 1024 / 1024:.2f} MB")
        self.time_elapsed_label.setText(
            f"耗时: {result.duration.total_seconds():.2f}s")

        # 显示完成消息
        self._log_message(f"维护完成！成功率: {result.success_rate:.2%}")

        # 发送信号
        self.optimization_completed.emit(result)

    def _on_optimization_failed(self, error: str):
        """维护失败"""
        self._update_ui_state(False)
        self._log_message(f"维护失败: {error}", "error")

        # 发送信号
        self.optimization_failed.emit(error)

    def _update_ui_state(self, is_optimizing: bool):
        """更新UI状态"""
        self.start_btn.setEnabled(not is_optimizing)
        self.stop_btn.setEnabled(is_optimizing)
        self.quick_clean_btn.setEnabled(not is_optimizing)
        self.analyze_btn.setEnabled(not is_optimizing)
        self.level_combo.setEnabled(not is_optimizing)

        if is_optimizing:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("维护中...")
        else:
            self.progress_bar.setVisible(False)
            self.status_label.setText("准备就绪")

    def _log_message(self, message: str, level: str = "info"):
        """记录日志消息"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        if level == "error":
            formatted_message = f"[{timestamp}]  {message}"
        elif level == "warning":
            formatted_message = f"[{timestamp}]  {message}"
        else:
            formatted_message = f"[{timestamp}] ℹ {message}"

        self.log_text.append(formatted_message)

        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)

    def get_optimization_result(self) -> Optional[OptimizationResult]:
        """获取维护结果"""
        return self.current_result

    def reset_panel(self):
        """重置面板状态"""
        self._update_ui_state(False)
        self.log_text.clear()
        self.files_cleaned_label.setText("清理文件: 0")
        self.space_freed_label.setText("释放空间: 0 MB")
        self.time_elapsed_label.setText("耗时: 0s")
        self.current_result = None

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.optimizer_service.dispose_async())
        except Exception as e:
            logger.error(f"清理维护服务失败: {e}")

        super().closeEvent(event)
        event.accept()
