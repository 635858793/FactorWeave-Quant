#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版数据导入系统启动器

集成了所有智能化功能的数据导入UI启动器
"""

from loguru import logger
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMenuBar, QAction
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 预先导入QAbstractItemView以防止运行时错误
try:
    from PyQt5.QtWidgets import QAbstractItemView
    logger.info("QAbstractItemView预导入成功")
except ImportError as e:
    logger.warning(f"QAbstractItemView预导入失败: {e}")

try:
    from gui.widgets.enhanced_data_import_widget import EnhancedDataImportWidget
    UI_AVAILABLE = True
except ImportError as e:
    logger.error(f"导入UI组件失败: {e}")
    UI_AVAILABLE = False


class EnhancedDataImportMainWindow(QMainWindow):
    """增强版数据导入主窗口"""

    def __init__(self, plugin_manager=None):
        super().__init__()
        self.plugin_manager = plugin_manager  # 保存plugin_manager
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("K线专业数据导入系统")
        self.setGeometry(100, 100, 1400, 900)

        # 设置窗口图标
        self.setWindowIcon(self.style().standardIcon(self.style().SP_ComputerIcon))

        # 创建中央部件
        if UI_AVAILABLE:
            # 传入plugin_manager
            central_widget = EnhancedDataImportWidget(plugin_manager=self.plugin_manager)
            self.setCentralWidget(central_widget)
        else:
            # 如果UI不可用，显示错误信息
            from PyQt5.QtWidgets import QLabel
            error_label = QLabel("K线数据导入UI组件加载失败\n请检查依赖项是否正确安装")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red; font-size: 16px;")
            self.setCentralWidget(error_label)


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用程序信息
    app.setApplicationName("数据导入系统")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("FactorWeave-Quant")

    # 设置全局样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QMenuBar {
            background-color: #2c3e50;
            color: white;
            border: none;
            padding: 4px;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 8px 12px;
            border-radius: 4px;
        }
        QMenuBar::item:selected {
            background-color: #34495e;
        }
        QMenu {
            background-color: white;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
        }
        QMenu::item {
            padding: 8px 20px;
        }
        QMenu::item:selected {
            background-color: #3498db;
            color: white;
        }
        QStatusBar {
            background-color: #ecf0f1;
            border-top: 1px solid #bdc3c7;
        }
    """)

    # 创建主窗口
    window = EnhancedDataImportMainWindow()
    window.show()

    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
