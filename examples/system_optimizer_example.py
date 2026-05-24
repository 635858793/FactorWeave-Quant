#!/usr/bin/env python3
"""
系统优化器使用示例

展示如何在FactorWeave-Quant 中使用系统优化器的各种功能
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from gui.panels.system_optimizer_panel import SystemOptimizerPanel
from gui.dialogs import show_system_optimizer_dialog
from core.services.system_optimizer import SystemOptimizerService, OptimizationLevel


class SystemOptimizerExample(QMainWindow):
    """系统优化器示例主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FactorWeave-Quant  系统优化器示例")
        self.setGeometry(100, 100, 1000, 700)

        # 创建中央窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建布局
        layout = QVBoxLayout(central_widget)

        # 创建按钮组
        button_layout = QHBoxLayout()

        # 对话框按钮
        dialog_btn = QPushButton("打开系统优化器对话框")
        dialog_btn.clicked.connect(self.show_optimizer_dialog)
        button_layout.addWidget(dialog_btn)

        # 面板按钮
        panel_btn = QPushButton("显示/隐藏优化器面板")
        panel_btn.clicked.connect(self.toggle_optimizer_panel)
        button_layout.addWidget(panel_btn)

        # 快速优化按钮
        quick_btn = QPushButton("快速优化")
        quick_btn.clicked.connect(self.quick_optimize)
        button_layout.addWidget(quick_btn)

        # 系统分析按钮
        analyze_btn = QPushButton("系统分析")
        analyze_btn.clicked.connect(self.analyze_system)
        button_layout.addWidget(analyze_btn)

        layout.addLayout(button_layout)

        # 创建优化器面板
        self.optimizer_panel = SystemOptimizerPanel()
        self.optimizer_panel.setVisible(False)
        layout.addWidget(self.optimizer_panel)

        # 连接面板信号
        self.optimizer_panel.optimization_completed.connect(
            self.on_optimization_completed)
        self.optimizer_panel.optimization_failed.connect(
            self.on_optimization_failed)

        # 创建优化器服务
        self.optimizer_service = SystemOptimizerService()

        # 初始化服务
        self.init_optimizer_service()

    def init_optimizer_service(self):
        """初始化优化器服务"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.optimizer_service.initialize_async())
            logger.info("系统优化器服务初始化成功")
        except Exception as e:
            logger.info(f" 系统优化器服务初始化失败: {e}")

    def show_optimizer_dialog(self):
        """显示系统优化器对话框"""
        try:
            show_system_optimizer_dialog(self)
        except Exception as e:
            logger.info(f"打开系统优化器对话框失败: {e}")

    def toggle_optimizer_panel(self):
        """切换优化器面板显示状态"""
        self.optimizer_panel.setVisible(not self.optimizer_panel.isVisible())

    def quick_optimize(self):
        """快速优化"""
        try:
            # 设置轻度优化
            self.optimizer_panel.level_combo.setCurrentIndex(0)
            self.optimizer_panel._start_optimization()
        except Exception as e:
            logger.info(f"快速优化失败: {e}")

    def analyze_system(self):
        """分析系统"""
        try:
            self.optimizer_panel._analyze_system()
        except Exception as e:
            logger.info(f"系统分析失败: {e}")

    def on_optimization_completed(self, result):
        """优化完成回调"""
        logger.info(f" 优化完成！")
        logger.info(f"  - 清理文件: {result.files_cleaned}")
        logger.info(f"  - 释放空间: {result.bytes_freed / 1024 / 1024:.2f} MB")
        logger.info(f"  - 耗时: {result.duration.total_seconds():.2f} 秒")
        logger.info(f"  - 成功率: {result.success_rate:.2%}")

    def on_optimization_failed(self, error):
        """优化失败回调"""
        logger.info(f" 优化失败: {error}")

    def closeEvent(self, event):
        """关闭事件"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.optimizer_service.dispose_async())
        except Exception as e:
            logger.info(f"清理优化器服务失败: {e}")

        event.accept()


def main():
    """主函数"""
    logger.info("FactorWeave-Quant  系统优化器示例")
    logger.info("=" * 40)

    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setApplicationName("FactorWeave-Quant  System Optimizer Example")
    app.setApplicationVersion("1.0")

    # 创建主窗口
    window = SystemOptimizerExample()
    window.show()

    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
