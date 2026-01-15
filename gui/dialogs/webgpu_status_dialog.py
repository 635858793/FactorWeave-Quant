from loguru import logger
"""
WebGPU状态对话框

显示WebGPU硬件加速渲染的状态信息，包括：
- WebGPU初始化状态
- GPU硬件信息
- 渲染性能指标
- 兼容性报告
"""

from typing import Dict, Any, Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QPushButton, QProgressBar, QLabel,
    QTextEdit, QMessageBox, QSplitter, QFrame, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider,
    QSpinBox, QDoubleSpinBox, QLineEdit, QScrollArea, QWidget,
    QGridLayout, QTextBrowser
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor


class WebGPUStatusDialog(QDialog):
    """WebGPU状态对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WebGPU状态")
        self.setMinimumSize(900, 700)
        self.setModal(True)

        self._create_widgets()
        self._load_status()

    def _create_widgets(self):
        """创建界面组件"""
        layout = QVBoxLayout(self)

        # 状态概览
        overview_group = QGroupBox("状态概览")
        overview_layout = QFormLayout(overview_group)

        self.webgpu_enabled_label = QLabel()
        self.backend_label = QLabel()
        self.renderer_label = QLabel()

        overview_layout.addRow("WebGPU状态:", self.webgpu_enabled_label)
        overview_layout.addRow("当前后端:", self.backend_label)
        overview_layout.addRow("渲染器:", self.renderer_label)

        layout.addWidget(overview_group)

        # GPU信息
        gpu_group = QGroupBox("GPU信息")
        gpu_layout = QFormLayout(gpu_group)

        self.gpu_name_label = QLabel()
        self.gpu_memory_label = QLabel()
        self.gpu_features_label = QLabel()

        gpu_layout.addRow("GPU型号:", self.gpu_name_label)
        gpu_layout.addRow("显存大小:", self.gpu_memory_label)
        gpu_layout.addRow("支持特性:", self.gpu_features_label)

        layout.addWidget(gpu_group)

        # 性能指标
        performance_group = QGroupBox("性能指标")
        performance_layout = QFormLayout(performance_group)

        self.render_time_label = QLabel()
        self.fps_label = QLabel()
        self.fallback_count_label = QLabel()

        performance_layout.addRow("平均渲染时间:", self.render_time_label)
        performance_layout.addRow("帧率:", self.fps_label)
        performance_layout.addRow("降级次数:", self.fallback_count_label)

        layout.addWidget(performance_group)

        # 兼容性报告
        compatibility_group = QGroupBox("兼容性报告")
        compatibility_layout = QVBoxLayout(compatibility_group)

        self.compatibility_text = QTextEdit()
        self.compatibility_text.setReadOnly(True)
        self.compatibility_text.setMaximumHeight(200)
        compatibility_layout.addWidget(self.compatibility_text)

        layout.addWidget(compatibility_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self._load_status)

        self.test_btn = QPushButton("测试渲染")
        self.test_btn.clicked.connect(self._test_rendering)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)

        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _load_status(self):
        """加载WebGPU状态"""
        try:
            from core.webgpu import get_webgpu_manager

            webgpu_manager = get_webgpu_manager()

            if webgpu_manager and webgpu_manager._initialized:
                self.webgpu_enabled_label.setText("✅ 已启用")
                self.webgpu_enabled_label.setStyleSheet("color: #28a745; font-weight: bold;")
                self.backend_label.setText(webgpu_manager.current_backend)
                self.renderer_label.setText("WebGPU渲染器")

                # 获取GPU信息
                gpu_info = webgpu_manager._webgpu_renderer.get_gpu_info()
                self.gpu_name_label.setText(gpu_info.get('name', '未知'))
                self.gpu_memory_label.setText(f"{gpu_info.get('memory_mb', 0)} MB")
                self.gpu_features_label.setText(", ".join(gpu_info.get('features', [])))

                # 获取性能指标
                stats = webgpu_manager._performance_stats
                avg_time = stats.get('average_render_time', 0.0)
                self.render_time_label.setText(f"{avg_time:.3f}s")
                self.fps_label.setText(f"{1.0/avg_time:.1f}" if avg_time > 0 else "N/A")
                self.fallback_count_label.setText(str(stats.get('fallback_triggered', 0)))

                # 获取兼容性报告
                report = webgpu_manager._compatibility_report
                self.compatibility_text.setText(self._format_compatibility_report(report))
            else:
                self.webgpu_enabled_label.setText("❌ 未启用")
                self.webgpu_enabled_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                self.backend_label.setText("matplotlib")
                self.renderer_label.setText("传统渲染器")
                self.gpu_name_label.setText("未知")
                self.gpu_memory_label.setText("0 MB")
                self.gpu_features_label.setText("无")
                self.render_time_label.setText("N/A")
                self.fps_label.setText("N/A")
                self.fallback_count_label.setText("0")
                self.compatibility_text.setText("WebGPU未初始化")

        except Exception as e:
            logger.error(f"加载WebGPU状态失败: {e}")
            QMessageBox.critical(self, "错误", f"加载WebGPU状态失败: {e}")

    def _test_rendering(self):
        """测试WebGPU渲染"""
        try:
            from core.webgpu import get_webgpu_manager

            webgpu_manager = get_webgpu_manager()

            if webgpu_manager and webgpu_manager._initialized:
                # 执行渲染测试
                success = self._test_webgpu_render()
                if success:
                    QMessageBox.information(self, "测试结果", "✅ WebGPU渲染测试成功！")
                else:
                    QMessageBox.warning(self, "测试结果", "⚠️ WebGPU渲染测试失败，已降级到matplotlib")
            else:
                QMessageBox.warning(self, "测试结果", "⚠️ WebGPU未初始化，无法测试")

        except Exception as e:
            logger.error(f"测试渲染失败: {e}")
            QMessageBox.critical(self, "错误", f"测试渲染失败: {e}")

    def _test_webgpu_render(self) -> bool:
        """执行WebGPU渲染测试"""
        try:
            import numpy as np
            import matplotlib.pyplot as plt

            # 创建测试数据
            x = np.linspace(0, 10, 100)
            y = np.sin(x)

            # 尝试使用WebGPU渲染
            from core.webgpu import render_chart_webgpu

            fig, ax = plt.subplots()
            success = render_chart_webgpu('line', ax, {'x': x, 'y': y}, {})

            plt.close(fig)

            return success

        except Exception as e:
            logger.error(f"WebGPU渲染测试失败: {e}")
            return False

    def _format_compatibility_report(self, report) -> str:
        """格式化兼容性报告"""
        if not report:
            return "无兼容性报告"

        issues_text = "\n".join(f"  - {issue}" for issue in report.issues)
        recommendations_text = "\n".join(f"  - {rec}" for rec in report.recommendations)

        return f"""兼容性级别: {report.level.value}
推荐后端: {report.recommended_backend.value}
性能评分: {report.performance_score:.1f}

问题:
{issues_text if issues_text else "  无"}

建议:
{recommendations_text if recommendations_text else "  无"}
"""