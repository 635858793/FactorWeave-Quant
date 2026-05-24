#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据管理对话框

【已废弃 - DEPRECATED】

此文件已被新的统一数据管理对话框替代：
- 新文件：data_management_dialog_unified.py
- 新类：UnifiedDataManagementDialog

本文件保留仅用于向后兼容性，将在未来版本中删除。
建议迁移到新的统一数据管理对话框。

原有功能：
- 数据源管理
- 下载任务管理
- 数据质量监控
- 智能数据缺失处理

作者: FactorWeave-Quant团队
版本: 1.0 (已废弃)
废弃日期: 2026-05-13
"""

import warnings
warnings.warn(
    "DataManagementDialog is deprecated and will be removed in a future version. "
    "Use UnifiedDataManagementDialog from data_management_dialog_unified.py instead.",
    DeprecationWarning,
    stacklevel=2
)

import sys
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
    QTableWidget, QTableWidgetItem, QTextEdit, QProgressBar,
    QGroupBox, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QApplication, QHeaderView, QComboBox, QLineEdit,
    QDateEdit, QSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QMessageBox, QMenu, QToolBar, QAction, QStatusBar,
    QDialogButtonBox, QFormLayout
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDate, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

# 导入自定义组件
try:
    from gui.widgets.data_management_widget import (
        DataManagementWidget, DataSourceManagementWidget,
        DownloadTaskWidget, DataQualityMonitorWidget
    )
    from gui.widgets.smart_data_missing_widget import (
        SmartDataMissingPrompt, SmartDataMissingIntegration
    )
    WIDGETS_AVAILABLE = True
except ImportError as e:
    print(f"导入UI组件失败: {e}")
    WIDGETS_AVAILABLE = False

# 导入核心组件
try:
    from core.plugin_types import AssetType, DataType, PluginType
    from core.asset_type_identifier import get_asset_type_identifier
    from core.data_router import get_data_router
    from core.ui_integration.data_missing_manager import get_data_missing_manager
    from core.ui_integration.smart_data_integration import get_smart_data_integration
    from loguru import logger
    CORE_AVAILABLE = True
except ImportError as e:
    logger = None
    print(f"导入核心组件失败: {e}")
    CORE_AVAILABLE = False

from .base_dialog import BaseDialog

logger = logger.bind(module=__name__) if logger else None

class DataManagementDialog(BaseDialog):
    """数据管理对话框"""

    # 信号定义
    data_downloaded = pyqtSignal(str, str)  # 数据下载完成 (symbol, source)
    source_configured = pyqtSignal(str, dict)  # 数据源配置更新

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="FactorWeave-Quant 数据管理中心",
            size=(1200, 800),
            settings_key="DataManagementDialog",
            modal=False
        )
        self.data_management_widget = None
        self.smart_integration = None
        self.setup_ui()
        self.setup_connections()
        self.init_components()

    def setup_ui(self):
        """设置UI"""

        # 设置窗口图标
        self.setWindowIcon(self.style().standardIcon(self.style().SP_ComputerIcon))

        layout = QVBoxLayout(self)

        # 主要内容区域
        if WIDGETS_AVAILABLE:
            self.data_management_widget = DataManagementWidget()
            layout.addWidget(self.data_management_widget)
        else:
            # 如果组件不可用，显示占位符
            placeholder_label = QLabel("数据管理组件加载失败")
            placeholder_label.setAlignment(Qt.AlignCenter)
            placeholder_label.setStyleSheet("color: red; font-size: 16px;")
            layout.addWidget(placeholder_label)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 智能检查按钮
        self.smart_check_btn = QPushButton("智能数据检查")
        self.smart_check_btn.setIcon(self.style().standardIcon(self.style().SP_DialogApplyButton))
        self.smart_check_btn.clicked.connect(self.run_smart_data_check)
        button_layout.addWidget(self.smart_check_btn)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setIcon(self.style().standardIcon(self.style().SP_BrowserReload))
        self.refresh_btn.clicked.connect(self.refresh_data)
        button_layout.addWidget(self.refresh_btn)

        button_layout.addStretch()

        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.setIcon(self.style().standardIcon(self.style().SP_DialogCloseButton))
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # 状态栏
        self.status_label = QLabel("数据管理系统就绪")
        self.status_label.setStyleSheet("QLabel { padding: 5px; border-top: 1px solid #ccc; }")
        layout.addWidget(self.status_label)

    def setup_connections(self):
        """设置信号连接"""
        if self.data_management_widget:
            # 连接数据管理组件的信号
            if hasattr(self.data_management_widget, 'source_widget'):
                self.data_management_widget.source_widget.source_configured.connect(
                    self.on_source_configured
                )

            if hasattr(self.data_management_widget, 'task_widget'):
                self.data_management_widget.task_widget.task_started.connect(
                    self.on_task_started
                )

    def init_components(self):
        """初始化组件"""
        if not CORE_AVAILABLE:
            return

        try:
            # 初始化智能数据集成
            if WIDGETS_AVAILABLE:
                self.smart_integration = SmartDataMissingIntegration()

        except Exception as e:
            if logger:
                logger.error(f"初始化组件失败: {e}")

    def run_smart_data_check(self):
        """运行智能数据检查"""
        self.status_label.setText("正在进行智能数据检查...")

        # 模拟检查过程
        QTimer.singleShot(1000, self.complete_smart_check)

    def complete_smart_check(self):
        """完成智能检查"""
        # 模拟检查结果
        missing_data = [
            {"symbol": "000001", "reason": "历史数据不完整"},
            {"symbol": "600000", "reason": "实时数据源连接失败"},
            {"symbol": "BTC-USDT", "reason": "加密货币数据未配置"}
        ]

        if missing_data:
            # 显示检查结果
            result_msg = "发现以下数据问题：\n\n"
            for item in missing_data:
                result_msg += f"• {item['symbol']}: {item['reason']}\n"
            result_msg += "\n是否要自动修复这些问题？"

            reply = QMessageBox.question(
                self, "智能数据检查结果", result_msg,
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.auto_fix_data_issues(missing_data)
            else:
                self.status_label.setText("智能检查完成，发现数据问题但未修复")
        else:
            QMessageBox.information(self, "检查完成", "所有数据状态正常！")
            self.status_label.setText("智能检查完成，数据状态正常")

    def auto_fix_data_issues(self, issues: List[Dict[str, str]]):
        """自动修复数据问题"""
        self.status_label.setText("正在自动修复数据问题...")

        # 模拟修复过程
        for i, issue in enumerate(issues):
            # 触发智能数据缺失提示
            if self.smart_integration:
                self.smart_integration.trigger_missing_data_prompt(
                    issue['symbol'],
                    reason=issue['reason']
                )

        self.status_label.setText(f"已处理 {len(issues)} 个数据问题")

    def refresh_data(self):
        """刷新数据"""
        self.status_label.setText("正在刷新数据...")

        # 刷新数据管理组件
        if self.data_management_widget:
            if hasattr(self.data_management_widget, 'source_widget'):
                self.data_management_widget.source_widget.refresh_sources()

        QTimer.singleShot(500, lambda: self.status_label.setText("数据刷新完成"))

    def on_source_configured(self, source_name: str, config: Dict[str, Any]):
        """数据源配置事件"""
        self.status_label.setText(f"数据源 {source_name} 配置已更新")
        self.source_configured.emit(source_name, config)

        if logger:
            logger.info(f"数据源配置更新: {source_name} -> {config}")

    def on_task_started(self, task_name: str):
        """任务开始事件"""
        self.status_label.setText(f"下载任务已开始: {task_name}")

    def show_data_missing_prompt(self, symbol: str, asset_type: AssetType = None,
                                 data_type: DataType = None, reason: str = None):
        """显示数据缺失提示"""
        if self.smart_integration:
            self.smart_integration.trigger_missing_data_prompt(
                symbol, asset_type, data_type, reason
            )
        else:
            # 备用简单提示
            msg = f"检测到股票 {symbol} 的数据缺失"
            if reason:
                msg += f"\n原因: {reason}"
            msg += "\n\n请在数据管理界面中手动下载数据。"

            QMessageBox.information(self, "数据缺失提醒", msg)

    def check_and_prompt_missing_data(self, symbol: str) -> bool:
        """检查并提示缺失数据"""
        if not self.smart_integration:
            return True  # 假设数据可用

        # 检查数据可用性
        is_available = self.smart_integration.check_data_availability(symbol)

        if not is_available:
            # 显示缺失数据提示
            self.show_data_missing_prompt(symbol, reason="数据未下载")
            return False

        return True

    def get_available_data_sources(self, asset_type: AssetType = None) -> List[str]:
        """获取可用数据源列表"""
        # 默认数据源列表
        default_sources = ['tongdaxin', 'eastmoney', 'sina', 'tencent']

        if asset_type == AssetType.CRYPTO:
            default_sources.extend(['binance'])
        elif asset_type == AssetType.STOCK_US:
            default_sources.extend(['yahoo'])

        return default_sources

    def create_download_task(self, symbol: str, source: str, config: Dict[str, Any]):
        """创建下载任务"""
        if self.data_management_widget and hasattr(self.data_management_widget, 'task_widget'):
            # 构造任务配置
            task_config = {
                'name': f"下载_{symbol}_{datetime.now().strftime('%H%M%S')}",
                'source': source,
                'asset_type': 'stock_a',  # 默认
                'data_type': 'historical_kline',  # 默认
                'symbols': [symbol],
                'start_date': config.get('start_date', datetime.now() - timedelta(days=30)),
                'end_date': config.get('end_date', datetime.now()),
                'status': 'pending',
                'progress': 0,
                'created_at': datetime.now()
            }

            # 添加任务
            self.data_management_widget.task_widget.add_task(task_config)

            # 切换到任务管理选项卡
            self.data_management_widget.tab_widget.setCurrentIndex(1)

            self.status_label.setText(f"已创建下载任务: {symbol}")

    def closeEvent(self, event):
        """关闭事件"""
        # 保存窗口状态等清理工作
        if logger:
            logger.info("数据管理对话框关闭")
        super().closeEvent(event)
        event.accept()

class QuickDataCheckDialog(QDialog):
    """快速数据检查对话框"""

    def __init__(self, symbols: List[str], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.symbols = symbols
        self.setup_ui()
        self.start_check()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("快速数据检查")
        self.setModal(True)
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        # 说明
        info_label = QLabel(f"正在检查 {len(self.symbols)} 只股票的数据完整性...")
        layout.addWidget(info_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.symbols))
        layout.addWidget(self.progress_bar)

        # 结果列表
        self.result_list = QListWidget()
        layout.addWidget(self.result_list)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def start_check(self):
        """开始检查"""
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_next_symbol)
        self.current_index = 0
        self.check_timer.start(100)  # 每100ms检查一个

    def check_next_symbol(self):
        """检查下一个股票"""
        if self.current_index >= len(self.symbols):
            self.check_timer.stop()
            self.check_completed()
            return

        symbol = self.symbols[self.current_index]

        # 模拟检查
        import random
        status = random.choice(["正常", "缺失", "部分缺失"])

        # 添加结果
        item_text = f"{symbol}: {status}"
        item = QListWidgetItem(item_text)

        if status == "正常":
            item.setBackground(QColor(144, 238, 144))  # 浅绿色
        elif status == "缺失":
            item.setBackground(QColor(255, 182, 193))  # 浅红色
        else:
            item.setBackground(QColor(255, 255, 0))  # 黄色

        self.result_list.addItem(item)

        # 更新进度
        self.current_index += 1
        self.progress_bar.setValue(self.current_index)

    def check_completed(self):
        """检查完成"""
        QMessageBox.information(self, "检查完成", "数据完整性检查已完成！")

    def closeEvent(self, event):
        if hasattr(self, 'check_timer') and self.check_timer.isActive():
            self.check_timer.stop()
        super().closeEvent(event)

def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 创建对话框
    dialog = DataManagementDialog()
    dialog.show()

    # 测试快速检查
    def test_quick_check():
        quick_dialog = QuickDataCheckDialog(["000001", "000002", "600000", "600036"])
        quick_dialog.exec_()

    # 添加测试按钮
    test_btn = QPushButton("测试快速检查")
    test_btn.clicked.connect(test_quick_check)
    dialog.layout().insertWidget(1, test_btn)

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
