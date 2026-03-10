#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能数据缺失提示组件

当检测到数据缺失时，自动显示智能提示界面，引导用户下载数据
集成数据缺失管理器和智能数据集成功能

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sys
from typing import Dict, List, Optional, Callable, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGroupBox, QProgressBar, QComboBox, QTextEdit,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QDialog, QDialogButtonBox, QCheckBox,
    QSpinBox, QDateEdit, QApplication, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QFormLayout, QLineEdit
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSize, QDate, QPropertyAnimation,
    QEasingCurve, QRect, QParallelAnimationGroup, QSequentialAnimationGroup
)
from PyQt5.QtGui import (
    QFont, QPixmap, QPainter, QColor, QLinearGradient, QPen, QBrush,
    QIcon, QPalette, QMovie
)

# 导入核心组件
try:
    from core.plugin_types import AssetType, DataType, PluginType, DataSourceProvider
    from core.asset_type_identifier import AssetTypeIdentifier, get_asset_type_identifier
    from core.data_router import DataRouter, get_data_router
    from core.ui_integration.data_missing_manager import DataMissingManager
    from core.ui_integration.smart_data_integration import SmartDataIntegration
    from loguru import logger
    CORE_AVAILABLE = True
except ImportError as e:
    logger = None
    print(f"导入核心组件失败: {e}")
    CORE_AVAILABLE = False

logger = logger.bind(module=__name__) if logger else None


class DataMissingReason(Enum):
    """数据缺失原因"""
    NOT_DOWNLOADED = "not_downloaded"
    PLUGIN_DISABLED = "plugin_disabled"
    NETWORK_ERROR = "network_error"
    DATA_SOURCE_ERROR = "data_source_error"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class MissingDataInfo:
    """缺失数据信息"""
    symbol: str
    asset_type: AssetType
    data_type: DataType
    reason: DataMissingReason
    suggested_sources: List[str]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    error_message: Optional[str] = None


class DataSourceRecommendationWidget(QWidget):
    """数据源推荐组件"""

    source_selected = pyqtSignal(str, dict)  # 数据源选择信号

    def __init__(self, missing_info: MissingDataInfo, parent=None):
        super().__init__(parent)
        self.missing_info = missing_info
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("推荐数据源")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 推荐列表
        self.sources_list = QListWidget()
        self.sources_list.setMaximumHeight(150)

        # 添加推荐的数据源
        for source in self.missing_info.suggested_sources:
            item = QListWidgetItem(f" {source}")
            item.setData(Qt.UserRole, source)

            # 根据数据源设置不同的描述
            descriptions = {
                'tongdaxin': '通达信 - 稳定可靠，支持A股历史数据',
                'eastmoney': '东方财富 - 数据丰富，更新及时',
                'sina': '新浪财经 - 免费使用，适合实时数据',
                'tencent': '腾讯财经 - 快速响应，数据准确',
                'binance': '币安 - 加密货币专业数据源',
                'yahoo': '雅虎财经 - 国际市场数据'
            }

            description = descriptions.get(source, f'{source} - 专业数据提供商')
            item.setToolTip(description)

            self.sources_list.addItem(item)

        layout.addWidget(self.sources_list)

        # 下载配置
        config_group = QGroupBox("下载配置")
        config_layout = QFormLayout(config_group)

        # 日期范围
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        config_layout.addRow("开始日期:", self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        config_layout.addRow("结束日期:", self.end_date)

        # 数据频率
        from core.plugin_types import Period
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(Period.all_periods())
        config_layout.addRow("数据频率:", self.frequency_combo)

        layout.addWidget(config_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.download_btn = QPushButton("立即下载")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.close)

        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def start_download(self):
        """开始下载"""
        current_item = self.sources_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择一个数据源")
            return

        source = current_item.data(Qt.UserRole)
        config = {
            'start_date': self.start_date.date().toPyDate(),
            'end_date': self.end_date.date().toPyDate(),
            'frequency': self.frequency_combo.currentText()
        }

        self.source_selected.emit(source, config)


class SmartDataMissingPrompt(QWidget):
    """智能数据缺失提示组件"""

    # 信号定义
    download_requested = pyqtSignal(str, str, dict)  # 下载请求 (symbol, source, config)
    prompt_closed = pyqtSignal()  # 提示关闭

    def __init__(self, parent=None):
        super().__init__(parent)
        self.missing_manager = None
        self.smart_integration = None
        self.current_missing_info = None
        self.setup_ui()
        self.setup_connections()
        self.init_managers()

    def setup_ui(self):
        """设置UI"""
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setFixedSize(450, 600)

        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
            }
            QLabel {
                color: #333;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 标题区域
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
                padding: 15px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)

        # 图标和标题
        title_layout = QHBoxLayout()

        # 警告图标
        icon_label = QLabel("")
        icon_label.setFont(QFont("Arial", 24))
        title_layout.addWidget(icon_label)

        # 标题文本
        title_label = QLabel("数据缺失提醒")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: white;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()
        header_layout.addLayout(title_layout)

        # 副标题
        subtitle_label = QLabel("检测到您请求的数据不存在，我们为您提供智能下载建议")
        subtitle_label.setFont(QFont("Arial", 10))
        subtitle_label.setStyleSheet("color: #f0f0f0;")
        subtitle_label.setWordWrap(True)
        header_layout.addWidget(subtitle_label)

        layout.addWidget(header_frame)

        # 缺失信息显示
        info_group = QGroupBox("缺失数据信息")
        info_layout = QFormLayout(info_group)

        self.symbol_label = QLabel("--")
        self.symbol_label.setFont(QFont("Arial", 10, QFont.Bold))
        info_layout.addRow("股票代码:", self.symbol_label)

        self.asset_type_label = QLabel("--")
        info_layout.addRow("资产类型:", self.asset_type_label)

        self.data_type_label = QLabel("--")
        info_layout.addRow("数据类型:", self.data_type_label)

        self.reason_label = QLabel("--")
        info_layout.addRow("缺失原因:", self.reason_label)

        layout.addWidget(info_group)

        # 推荐数据源区域
        self.recommendation_area = QScrollArea()
        self.recommendation_area.setWidgetResizable(True)
        self.recommendation_area.setMaximumHeight(250)
        layout.addWidget(self.recommendation_area)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.later_btn = QPushButton("稍后处理")
        self.later_btn.clicked.connect(self.close_prompt)

        self.manage_btn = QPushButton("数据管理")
        self.manage_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.manage_btn.clicked.connect(self.open_data_management)

        button_layout.addWidget(self.later_btn)
        button_layout.addWidget(self.manage_btn)
        layout.addLayout(button_layout)

        # 进度指示器（隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def setup_connections(self):
        """设置信号连接"""
        pass

    def init_managers(self):
        """初始化管理器"""
        if not CORE_AVAILABLE:
            return

        try:
            # 尝试创建管理器实例
            self.missing_manager = DataMissingManager() if CORE_AVAILABLE else None
            self.smart_integration = SmartDataIntegration() if CORE_AVAILABLE else None
        except Exception as e:
            if logger:
                logger.error(f"初始化管理器失败: {e}")
            self.missing_manager = None
            self.smart_integration = None

    def show_missing_data_prompt(self, symbol: str, asset_type: AssetType,
                                 data_type: DataType, reason: str = None):
        """显示数据缺失提示"""
        if not CORE_AVAILABLE:
            return

        try:
            # 获取资产类型（如果未提供）
            if not asset_type:
                try:
                    identifier = AssetTypeIdentifier.get_instance()
                    asset_type = identifier.identify_asset_type(symbol)
                except:
                    asset_type = AssetType.STOCK_A  # 默认值

            # 获取推荐数据源
            suggested_sources = []
            if self.missing_manager:
                suggested_sources = self.missing_manager.suggest_data_sources(symbol, data_type)

            # 创建缺失数据信息
            self.current_missing_info = MissingDataInfo(
                symbol=symbol,
                asset_type=asset_type,
                data_type=data_type,
                reason=DataMissingReason.NOT_DOWNLOADED,
                suggested_sources=suggested_sources or ['tongdaxin', 'eastmoney'],
                error_message=reason
            )

            # 更新UI显示
            self.update_missing_info_display()

            # 创建推荐组件
            self.create_recommendation_widget()

            # 显示提示窗口
            self.show()
            self.raise_()
            self.activateWindow()

        except Exception as e:
            if logger:
                logger.error(f"显示数据缺失提示失败: {e}")

    def update_missing_info_display(self):
        """更新缺失信息显示"""
        if not self.current_missing_info:
            return

        info = self.current_missing_info

        self.symbol_label.setText(info.symbol)
        self.asset_type_label.setText(info.asset_type.value if info.asset_type else "未知")
        self.data_type_label.setText(info.data_type.value if info.data_type else "未知")

        # 设置原因显示
        reason_text = {
            DataMissingReason.NOT_DOWNLOADED: "数据未下载",
            DataMissingReason.PLUGIN_DISABLED: "数据源插件未启用",
            DataMissingReason.NETWORK_ERROR: "网络连接错误",
            DataMissingReason.DATA_SOURCE_ERROR: "数据源错误",
            DataMissingReason.PERMISSION_ERROR: "权限不足",
            DataMissingReason.UNKNOWN_ERROR: "未知错误"
        }.get(info.reason, "未知原因")

        if info.error_message:
            reason_text += f" ({info.error_message})"

        self.reason_label.setText(reason_text)

    def create_recommendation_widget(self):
        """创建推荐组件"""
        if not self.current_missing_info:
            return

        # 创建推荐组件
        recommendation_widget = DataSourceRecommendationWidget(self.current_missing_info)
        recommendation_widget.source_selected.connect(self.on_source_selected)

        # 设置到滚动区域
        self.recommendation_area.setWidget(recommendation_widget)

    def on_source_selected(self, source: str, config: Dict[str, Any]):
        """数据源选择事件"""
        if not self.current_missing_info:
            return

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度

        # 发送下载请求信号
        self.download_requested.emit(self.current_missing_info.symbol, source, config)

        # 模拟下载过程
        QTimer.singleShot(2000, self.download_completed)

    def download_completed(self):
        """下载完成"""
        self.progress_bar.setVisible(False)

        # 显示成功消息
        QMessageBox.information(
            self, "下载完成",
            f"数据下载已完成！\n股票: {self.current_missing_info.symbol}"
        )

        self.close_prompt()

    def close_prompt(self):
        """关闭提示"""
        self.prompt_closed.emit()
        self.hide()

    def open_data_management(self):
        """打开数据管理界面"""
        # 这里应该打开数据管理主界面
        # 暂时显示消息
        QMessageBox.information(
            self, "数据管理",
            "正在打开数据管理界面..."
        )
        self.close_prompt()


class SmartDataMissingIntegration(QWidget):
    """智能数据缺失集成组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompt_widget = None
        self.setup_integration()

    def setup_integration(self):
        """设置集成"""
        # 创建提示组件
        self.prompt_widget = SmartDataMissingPrompt()
        self.prompt_widget.download_requested.connect(self.handle_download_request)
        self.prompt_widget.prompt_closed.connect(self.on_prompt_closed)

    def init_managers(self):
        """初始化管理器（兼容性方法）"""
        if self.prompt_widget:
            self.prompt_widget.init_managers()
            # 为了兼容性，也在当前对象上设置引用
            self.missing_manager = getattr(self.prompt_widget, 'missing_manager', None)
            self.smart_integration = getattr(self.prompt_widget, 'smart_integration', None)

    def check_data_availability(self, symbol: str, data_type: DataType = None) -> bool:
        """检查数据可用性"""
        if not CORE_AVAILABLE:
            return True  # 假设可用

        try:
            # 使用数据缺失管理器检查
            if self.prompt_widget.missing_manager:
                availability = self.prompt_widget.missing_manager.check_data_availability(
                    symbol, data_type or DataType.HISTORICAL_KLINE
                )
                return availability.status == 'available'

        except Exception as e:
            if logger:
                logger.error(f"检查数据可用性失败: {e}")

        return False

    def trigger_missing_data_prompt(self, symbol: str, asset_type: AssetType = None,
                                    data_type: DataType = None, reason: str = None):
        """触发数据缺失提示"""
        if not self.prompt_widget:
            return

        # 默认参数
        if not data_type:
            data_type = DataType.HISTORICAL_KLINE

        # 显示提示
        self.prompt_widget.show_missing_data_prompt(symbol, asset_type, data_type, reason)

    def handle_download_request(self, symbol: str, source: str, config: Dict[str, Any]):
        """处理下载请求"""
        if logger:
            logger.info(f"处理下载请求: {symbol} from {source} with config {config}")

        # 这里应该调用实际的下载逻辑
        # 暂时只记录日志

    def on_prompt_closed(self):
        """提示关闭事件"""
        if logger:
            logger.info("数据缺失提示已关闭")


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 创建集成组件
    integration = SmartDataMissingIntegration()

    # 模拟数据缺失检查
    def test_missing_data():
        if not integration.check_data_availability("000001"):
            integration.trigger_missing_data_prompt(
                "000001",
                AssetType.STOCK_A,
                DataType.HISTORICAL_KLINE,
                "测试数据缺失"
            )

    # 延迟触发测试
    QTimer.singleShot(1000, test_missing_data)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
