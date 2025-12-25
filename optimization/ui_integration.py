from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI集成组件
提供形态算法优化的图形界面集成功能
"""

from analysis.pattern_manager import PatternManager
from optimization.version_manager import VersionManager
from optimization.auto_tuner import AlgorithmAutoTuner, TuningTask, OptimizationConfig
import sys
import os
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import json
import threading
from dataclasses import dataclass

# GUI框架导入
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QProgressBar, QTextEdit, QTableWidget, QTableWidgetItem,
        QDialog, QDialogButtonBox, QGroupBox, QFormLayout,
        QMenu, QAction, QMessageBox, QTabWidget, QSplitter,
        QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox,
        QListWidget, QListWidgetItem, QInputDialog, QProgressDialog
    )
    from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
    from PyQt5.QtGui import QFont, QIcon, QPixmap, QTextCursor
    GUI_AVAILABLE = True
except ImportError:
    logger.info("PyQt5 未安装，UI功能将受限")
    GUI_AVAILABLE = False

# 导入优化系统组件
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@dataclass
class UIConfig:
    """UI配置"""
    theme: str = "light"
    font_size: int = 10
    auto_refresh: bool = True
    refresh_interval: int = 1000  # 毫秒
    show_debug_info: bool = False

class OptimizationWorker(QThread if GUI_AVAILABLE else QObject):
    """优化工作线程"""

    if GUI_AVAILABLE:
        progress_updated = pyqtSignal(str, float)  # pattern_name, progress
        task_completed = pyqtSignal(str, dict)     # pattern_name, result
        # pattern_name, error_message
        error_occurred = pyqtSignal(str, str)

    def __init__(self, auto_tuner: AlgorithmAutoTuner):
        super().__init__()
        self.auto_tuner = auto_tuner
        self.current_task = None
        self.is_running = False

    def run_optimization(self, pattern_name: str, config: OptimizationConfig):
        """运行单个优化任务"""
        self.current_task = pattern_name
        self.is_running = True

        if GUI_AVAILABLE:
            self.start()
        else:
            self.run()

    def run(self):
        """线程执行函数"""
        try:
            if not self.current_task:
                return

            # 设置进度回调
            def progress_callback(task: TuningTask):
                if GUI_AVAILABLE:
                    self.progress_updated.emit(
                        task.pattern_name, task.progress)

            def completion_callback(task: TuningTask):
                if GUI_AVAILABLE:
                    self.task_completed.emit(
                        task.pattern_name, task.result or {})

            self.auto_tuner.set_progress_callback(progress_callback)
            self.auto_tuner.set_completion_callback(completion_callback)

            # 执行优化
            result = self.auto_tuner.optimizer.optimize_algorithm(
                pattern_name=self.current_task,
                config=OptimizationConfig()
            )

            if GUI_AVAILABLE:
                self.task_completed.emit(self.current_task, result)

        except Exception as e:
            if GUI_AVAILABLE:
                self.error_occurred.emit(
                    self.current_task or "unknown", str(e))
        finally:
            self.is_running = False

class OptimizationDialog(QDialog if GUI_AVAILABLE else object):
    """优化配置对话框"""

    def __init__(self, pattern_name: str, parent=None):
        if not GUI_AVAILABLE:
            return

        super().__init__(parent)
        self.pattern_name = pattern_name
        self.config = OptimizationConfig()
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"优化配置 - {self.pattern_name}")
        self.setFixedSize(400, 500)

        layout = QVBoxLayout()

        # 基本配置组
        basic_group = QGroupBox("基本配置")
        basic_layout = QFormLayout()

        # 优化方法
        self.method_combo = QComboBox()
        self.method_combo.addItems(
            ["genetic", "bayesian", "random", "gradient"])
        self.method_combo.setCurrentText("genetic")
        basic_layout.addRow("优化方法:", self.method_combo)

        # 最大迭代次数
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(5, 200)
        self.iterations_spin.setValue(50)
        basic_layout.addRow("最大迭代次数:", self.iterations_spin)

        # 目标指标
        self.target_combo = QComboBox()
        self.target_combo.addItems([
            "overall_score", "signal_quality", "confidence_avg",
            "execution_time", "robustness_score"
        ])
        basic_layout.addRow("目标指标:", self.target_combo)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 高级配置组
        advanced_group = QGroupBox("高级配置")
        advanced_layout = QFormLayout()

        # 种群大小（遗传算法）
        self.population_spin = QSpinBox()
        self.population_spin.setRange(5, 100)
        self.population_spin.setValue(20)
        advanced_layout.addRow("种群大小:", self.population_spin)

        # 变异率
        self.mutation_spin = QDoubleSpinBox()
        self.mutation_spin.setRange(0.01, 0.5)
        self.mutation_spin.setSingleStep(0.01)
        self.mutation_spin.setValue(0.1)
        advanced_layout.addRow("变异率:", self.mutation_spin)

        # 交叉率
        self.crossover_spin = QDoubleSpinBox()
        self.crossover_spin.setRange(0.1, 1.0)
        self.crossover_spin.setSingleStep(0.1)
        self.crossover_spin.setValue(0.8)
        advanced_layout.addRow("交叉率:", self.crossover_spin)

        # 超时时间
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix("分钟")
        advanced_layout.addRow("超时时间:", self.timeout_spin)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_config(self) -> OptimizationConfig:
        """获取配置"""
        if not GUI_AVAILABLE:
            return OptimizationConfig()

        return OptimizationConfig(
            method=self.method_combo.currentText(),
            max_iterations=self.iterations_spin.value(),
            population_size=self.population_spin.value(),
            mutation_rate=self.mutation_spin.value(),
            crossover_rate=self.crossover_spin.value(),
            target_metric=self.target_combo.currentText(),
            timeout_minutes=self.timeout_spin.value()
        )

class VersionManagerDialog(QDialog if GUI_AVAILABLE else object):
    """版本管理对话框"""

    def __init__(self, pattern_name: str, version_manager: VersionManager, parent=None):
        if not GUI_AVAILABLE:
            return

        super().__init__(parent)
        self.pattern_name = pattern_name
        self.version_manager = version_manager
        self.init_ui()
        self.load_versions()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"版本管理 - {self.pattern_name}")
        self.setFixedSize(800, 600)

        layout = QVBoxLayout()

        # 版本列表
        self.version_table = QTableWidget()
        self.version_table.setColumnCount(7)
        self.version_table.setHorizontalHeaderLabels([
            "版本号", "创建时间", "优化方法", "描述", "激活状态", "性能评分", "操作"
        ])
        self.version_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.version_table)

        # 按钮栏
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_versions)
        button_layout.addWidget(self.refresh_btn)

        self.activate_btn = QPushButton("激活选中版本")
        self.activate_btn.clicked.connect(self.activate_selected_version)
        button_layout.addWidget(self.activate_btn)

        self.delete_btn = QPushButton("删除选中版本")
        self.delete_btn.clicked.connect(self.delete_selected_version)
        button_layout.addWidget(self.delete_btn)

        self.export_btn = QPushButton("导出版本")
        self.export_btn.clicked.connect(self.export_selected_version)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def load_versions(self):
        """加载版本列表"""
        versions = self.version_manager.get_versions(self.pattern_name)

        self.version_table.setRowCount(len(versions))

        for i, version in enumerate(versions):
            # 版本号
            self.version_table.setItem(
                i, 0, QTableWidgetItem(str(version.version_number)))

            # 创建时间
            self.version_table.setItem(
                i, 1, QTableWidgetItem(version.created_time))

            # 优化方法
            self.version_table.setItem(
                i, 2, QTableWidgetItem(version.optimization_method))

            # 描述
            self.version_table.setItem(
                i, 3, QTableWidgetItem(version.description))

            # 激活状态
            status = " 激活" if version.is_active else "未激活"
            self.version_table.setItem(i, 4, QTableWidgetItem(status))

            # 性能评分
            score = "N/A"
            if version.performance_metrics:
                score = f"{version.performance_metrics.overall_score:.3f}"
            self.version_table.setItem(i, 5, QTableWidgetItem(score))

            # 存储版本ID用于操作
            self.version_table.item(i, 0).setData(Qt.UserRole, version.id)

    def activate_selected_version(self):
        """激活选中的版本"""
        current_row = self.version_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要激活的版本")
            return

        version_id = self.version_table.item(current_row, 0).data(Qt.UserRole)

        if self.version_manager.activate_version(version_id):
            QMessageBox.information(self, "成功", "版本激活成功")
            self.load_versions()
        else:
            QMessageBox.critical(self, "错误", "版本激活失败")

    def delete_selected_version(self):
        """删除选中的版本"""
        current_row = self.version_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要删除的版本")
            return

        reply = QMessageBox.question(
            self, "确认删除", "确定要删除选中的版本吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            version_id = self.version_table.item(
                current_row, 0).data(Qt.UserRole)

            if self.version_manager.delete_version(version_id):
                QMessageBox.information(self, "成功", "版本删除成功")
                self.load_versions()
            else:
                QMessageBox.critical(self, "错误", "版本删除失败")

    def export_selected_version(self):
        """导出选中的版本"""
        current_row = self.version_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要导出的版本")
            return

        version_id = self.version_table.item(current_row, 0).data(Qt.UserRole)
        version_number = self.version_table.item(current_row, 0).text()

        export_path = f"exports/{self.pattern_name}_v{version_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # 确保导出目录存在
        os.makedirs("exports", exist_ok=True)

        if self.version_manager.export_version(version_id, export_path):
            QMessageBox.information(self, "成功", f"版本已导出到: {export_path}")
        else:
            QMessageBox.critical(self, "错误", "版本导出失败")

class UIIntegration:
    """UI集成主类"""

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.config = UIConfig()

        # 核心组件
        self.auto_tuner = AlgorithmAutoTuner(debug_mode=debug_mode)
        self.version_manager = VersionManager()
        self.evaluator = PerformanceEvaluator(debug_mode)
        self.pattern_manager = PatternManager()

        # UI组件
        self.optimization_worker = OptimizationWorker(self.auto_tuner)
        self.active_dialogs = {}

        # 状态
        self.current_optimizations = {}

    def create_pattern_context_menu(self, pattern_name: str) -> Optional[Any]:
        """创建形态右键菜单"""
        if not GUI_AVAILABLE:
            if self.debug_mode:
                logger.info(f"    GUI不可用，跳过菜单创建: {pattern_name}")
            return None

        try:
            # 检查是否已有QApplication实例
            app = QApplication.instance()
            if app is None:
                if self.debug_mode:
                    logger.info(f"    无QApplication实例，跳过菜单创建: {pattern_name}")
                return None

            menu = QMenu(f"优化 {pattern_name}")

            # 快速优化
            quick_action = QAction("快速优化", menu)
            quick_action.triggered.connect(
                lambda: self.quick_optimize(pattern_name))
            menu.addAction(quick_action)

            # 高级优化
            advanced_action = QAction("高级优化...", menu)
            advanced_action.triggered.connect(
                lambda: self.show_optimization_dialog(pattern_name))
            menu.addAction(advanced_action)

            menu.addSeparator()

            # 版本管理
            version_action = QAction("版本管理...", menu)
            version_action.triggered.connect(
                lambda: self.show_version_manager(pattern_name))
            menu.addAction(version_action)

            # 性能评估
            eval_action = QAction("性能评估", menu)
            eval_action.triggered.connect(
                lambda: self.evaluate_pattern(pattern_name))
            menu.addAction(eval_action)

            return menu

        except Exception as e:
            if self.debug_mode:
                logger.info(f"   创建菜单失败: {e}")
            return None

    def show_optimization_dialog(self, pattern_name: str):
        """显示优化配置对话框"""
        if not GUI_AVAILABLE:
            logger.info(f"GUI不可用，无法显示优化对话框: {pattern_name}")
            return

        dialog = OptimizationDialog(pattern_name)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_config()
            self.start_optimization(pattern_name, config)

    def quick_optimize(self, pattern_name: str):
        """快速优化（使用默认配置）"""
        config = OptimizationConfig(
            method="random",
            max_iterations=10,
            timeout_minutes=5
        )
        self.start_optimization(pattern_name, config)

    def start_optimization(self, pattern_name: str, config: OptimizationConfig):
        """开始优化"""
        if pattern_name in self.current_optimizations:
            if GUI_AVAILABLE:
                QMessageBox.warning(None, "警告", f"{pattern_name} 正在优化中，请等待完成")
            return

        logger.info(f" 开始优化: {pattern_name}")

        # 记录优化状态
        self.current_optimizations[pattern_name] = {
            "start_time": datetime.now(),
            "config": config,
            "progress": 0.0
        }

        # 启动优化工作线程
        self.optimization_worker.run_optimization(pattern_name, config)

        # 连接信号
        if GUI_AVAILABLE:
            self.optimization_worker.progress_updated.connect(
                self.on_progress_updated)
            self.optimization_worker.task_completed.connect(
                self.on_task_completed)
            self.optimization_worker.error_occurred.connect(
                self.on_error_occurred)

    def show_version_manager(self, pattern_name: str):
        """显示版本管理对话框"""
        if not GUI_AVAILABLE:
            logger.info(f"GUI不可用，无法显示版本管理: {pattern_name}")
            return

        if pattern_name in self.active_dialogs:
            self.active_dialogs[pattern_name].raise_()
            return

        dialog = VersionManagerDialog(pattern_name, self.version_manager)
        self.active_dialogs[pattern_name] = dialog

        # 对话框关闭时清理引用
        dialog.finished.connect(
            lambda: self.active_dialogs.pop(pattern_name, None))

        dialog.show()

    def evaluate_pattern(self, pattern_name: str):
        """评估形态性能"""
        try:
            logger.info(f"评估形态性能: {pattern_name}")

            # 创建测试数据集
            test_datasets = self.evaluator.create_test_datasets(
                pattern_name, count=3)

            # 评估性能
            metrics = self.evaluator.evaluate_algorithm(
                pattern_name, test_datasets)

            # 显示结果
            result_text = f"""
形态: {pattern_name}
综合评分: {metrics.overall_score:.3f}
信号质量: {metrics.signal_quality:.3f}
平均置信度: {metrics.confidence_avg:.3f}
执行时间: {metrics.execution_time:.3f}秒
识别形态数: {metrics.patterns_found}
鲁棒性: {metrics.robustness_score:.3f}
            """.strip()

            if GUI_AVAILABLE:
                QMessageBox.information(
                    None, f"性能评估 - {pattern_name}", result_text)
            else:
                logger.info(result_text)

        except Exception as e:
            error_msg = f"性能评估失败: {e}"
            if GUI_AVAILABLE:
                QMessageBox.critical(None, "错误", error_msg)
            else:
                logger.info(f" {error_msg}")

    def export_pattern_algorithm(self, pattern_name: str):
        """导出形态算法"""
        try:
            # 获取当前最佳版本
            best_version = self.version_manager.get_best_version(pattern_name)

            if not best_version:
                if GUI_AVAILABLE:
                    QMessageBox.warning(None, "警告", f"未找到 {pattern_name} 的版本")
                return

            # 导出路径
            export_path = f"exports/{pattern_name}_algorithm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.makedirs("exports", exist_ok=True)

            # 导出
            if self.version_manager.export_version(best_version.id, export_path):
                if GUI_AVAILABLE:
                    QMessageBox.information(
                        None, "成功", f"算法已导出到: {export_path}")
                else:
                    logger.info(f" 算法已导出到: {export_path}")
            else:
                raise Exception("导出失败")

        except Exception as e:
            error_msg = f"导出算法失败: {e}"
            if GUI_AVAILABLE:
                QMessageBox.critical(None, "错误", error_msg)
            else:
                logger.info(f" {error_msg}")

    def on_progress_updated(self, pattern_name: str, progress: float):
        """优化进度更新"""
        if pattern_name in self.current_optimizations:
            self.current_optimizations[pattern_name]["progress"] = progress

        if self.debug_mode:
            logger.info(f"↑ {pattern_name} 优化进度: {progress:.1%}")

    def on_task_completed(self, pattern_name: str, result: Dict[str, Any]):
        """优化任务完成"""
        if pattern_name in self.current_optimizations:
            del self.current_optimizations[pattern_name]

        improvement = result.get("improvement_percentage", 0)

        message = f"""
优化完成: {pattern_name}

性能提升: {improvement:.3f}%
最佳评分: {result.get('best_score', 0):.3f}
基准评分: {result.get('baseline_score', 0):.3f}
迭代次数: {result.get('iterations', 0)}
        """.strip()

        if GUI_AVAILABLE:
            QMessageBox.information(None, "优化完成", message)
        else:
            logger.info(f" {message}")

    def on_error_occurred(self, pattern_name: str, error_message: str):
        """优化错误处理"""
        if pattern_name in self.current_optimizations:
            del self.current_optimizations[pattern_name]

        error_msg = f"优化失败: {pattern_name}\n错误: {error_message}"

        if GUI_AVAILABLE:
            QMessageBox.critical(None, "优化失败", error_msg)
        else:
            logger.info(f" {error_msg}")

    def get_optimization_status(self) -> Dict[str, Any]:
        """获取当前优化状态"""
        return {
            "active_optimizations": len(self.current_optimizations),
            "optimizations": {
                name: {
                    "progress": info["progress"],
                    "duration": (datetime.now() - info["start_time"]).total_seconds(),
                    "method": info["config"].method
                }
                for name, info in self.current_optimizations.items()
            }
        }

    def batch_optimize_all(self):
        """批量优化所有形态"""
        if GUI_AVAILABLE:
            reply = QMessageBox.question(
                None, "确认批量优化",
                "确定要优化所有形态吗？这可能需要较长时间。",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

        logger.info("启动批量优化...")
        result = self.auto_tuner.one_click_optimize()

        summary = result.get("summary", {})
        message = f"""
批量优化完成！

总任务数: {summary.get('total_tasks', 0)}
成功任务数: {summary.get('successful_tasks', 0)}
成功率: {summary.get('success_rate', 0):.1f}%
平均改进: {summary.get('average_improvement', 0):.3f}%
最佳改进: {summary.get('best_improvement', 0):.3f}%
        """.strip()

        if GUI_AVAILABLE:
            QMessageBox.information(None, "批量优化完成", message)
        else:
            logger.info(f" {message}")

def create_ui_integration(debug_mode: bool = False) -> UIIntegration:
    """创建UI集成实例"""
    return UIIntegration(debug_mode=debug_mode)

# 便捷函数
def show_pattern_menu(pattern_name: str, parent_widget=None) -> Optional['QMenu']:
    """显示形态右键菜单的便捷函数"""
    ui_integration = create_ui_integration()
    return ui_integration.create_pattern_context_menu(pattern_name)

def quick_optimize_pattern(pattern_name: str):
    """快速优化形态的便捷函数"""
    ui_integration = create_ui_integration()
    ui_integration.quick_optimize(pattern_name)

if __name__ == "__main__":
    # 测试UI集成
    if GUI_AVAILABLE:
        app = QApplication(sys.argv)

        # 创建UI集成实例
        ui_integration = create_ui_integration(debug_mode=True)

        # 测试右键菜单
        menu = ui_integration.create_pattern_context_menu("hammer")
        if menu:
            menu.exec_()

        # 测试版本管理对话框
        ui_integration.show_version_manager("hammer")

        sys.exit(app.exec_())
    else:
        logger.info("测试UI集成（无GUI模式）")
        ui_integration = create_ui_integration(debug_mode=True)

        # 测试快速优化
        ui_integration.quick_optimize("hammer")

        # 测试性能评估
        ui_integration.evaluate_pattern("hammer")
