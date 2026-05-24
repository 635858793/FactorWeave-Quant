"""
区间统计对话框

提供详细的区间统计功能，包含30多个统计指标。
"""

from loguru import logger
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QTabWidget, QWidget,
    QHeaderView, QFrame, QGridLayout, QTextEdit, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from .base_dialog import BaseDialog

# Matplotlib 延迟导入标志
MATPLOTLIB_AVAILABLE = False

logger = logger

class IntervalStatDialog(BaseDialog):
    """区间统计对话框"""

    def __init__(self, kdata: pd.DataFrame, stat_data: Dict[str, Any], parent=None):
        """
        初始化区间统计对话框

        Args:
            kdata: K线数据
            stat_data: 统计数据
            parent: 父窗口
        """
        super().__init__(
            parent,
            title="区间统计分析",
            min_size=(800, 600),
            size=(1000, 700),
            settings_key="IntervalStatDialog"
        )
        self.kdata = kdata
        self.stat_data = stat_data

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(5)

        # 标题
        # title_label = QLabel("区间统计分析报告")
        # title_label.setAlignment(Qt.AlignCenter)
        # title_label.setStyleSheet("""
        #     QLabel {
        #         font-size: 15px;
        #         font-weight: bold;
        #         color: #2c3e50;
        #         padding: 10px;
        #         background-color: #ecf0f1;
        #         border-radius: 5px;
        #     }
        # """)
        # layout.addWidget(title_label)

        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # 基础统计标签页
        basic_tab = self._create_basic_stats_tab()
        tab_widget.addTab(basic_tab, "基础统计")

        # 高级统计标签页
        advanced_tab = self._create_advanced_stats_tab()
        tab_widget.addTab(advanced_tab, "高级统计")

        # 图表分析标签页
        if MATPLOTLIB_AVAILABLE:
            chart_tab = self._create_chart_tab()
            tab_widget.addTab(chart_tab, "图表分析")

        # 按钮栏
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        export_btn = QPushButton("导出报告")
        export_btn.clicked.connect(self._export_report)
        button_layout.addWidget(export_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_basic_stats_tab(self) -> QWidget:
        """创建基础统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 创建统计表格
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["指标", "数值"])

        # 设置表格样式
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 10px;
                font-weight: bold;
            }
        """)

        # 基础统计指标
        basic_stats = [
            ("开盘价", self.stat_data.get('开盘价', 0)),
            ("收盘价", self.stat_data.get('收盘价', 0)),
            ("最高价", self.stat_data.get('最高价', 0)),
            ("最低价", self.stat_data.get('最低价', 0)),
            ("均价", self.stat_data.get('均价', 0)),
            ("涨跌幅(%)", self.stat_data.get('涨跌幅(%)', 0)),
            ("最大回撤(%)", self.stat_data.get('最大回撤(%)', 0)),
            ("振幅均值(%)", self.stat_data.get('振幅均值(%)', 0)),
            ("振幅最大(%)", self.stat_data.get('振幅最大(%)', 0)),
            ("区间波动率(年化%)", self.stat_data.get('区间波动率(年化%)', 0)),
        ]

        table.setRowCount(len(basic_stats))
        for i, (name, value) in enumerate(basic_stats):
            table.setItem(i, 0, QTableWidgetItem(name))

            # 格式化数值
            if isinstance(value, (int, float)):
                if abs(value) >= 1:
                    formatted_value = f"{value:.2f}"
                else:
                    formatted_value = f"{value:.4f}"
            else:
                formatted_value = str(value)

            item = QTableWidgetItem(formatted_value)

            # 根据数值设置颜色
            if "涨跌幅" in name and isinstance(value, (int, float)):
                if value > 0:
                    item.setForeground(QColor("#e74c3c"))  # 红色
                elif value < 0:
                    item.setForeground(QColor("#27ae60"))  # 绿色

            table.setItem(i, 1, item)

        # 调整列宽
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        layout.addWidget(table)
        return widget

    def _create_advanced_stats_tab(self) -> QWidget:
        """创建高级统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧：交易统计
        trade_frame = QFrame()
        trade_frame.setFrameStyle(QFrame.StyledPanel)
        trade_layout = QVBoxLayout(trade_frame)

        trade_title = QLabel("交易统计")
        trade_title.setAlignment(Qt.AlignCenter)
        trade_title.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 5px;")
        trade_layout.addWidget(trade_title)

        trade_table = QTableWidget()
        trade_table.setColumnCount(2)
        trade_table.setHorizontalHeaderLabels(["指标", "数值"])

        trade_stats = [
            ("阳线天数", self.stat_data.get('阳线天数', 0)),
            ("阴线天数", self.stat_data.get('阴线天数', 0)),
            ("阳线比例(%)", self.stat_data.get('阳线比例(%)', 0)),
            ("阴线比例(%)", self.stat_data.get('阴线比例(%)', 0)),
            ("最大连续阳线", self.stat_data.get('最大连续阳线', 0)),
            ("最大连续阴线", self.stat_data.get('最大连续阴线', 0)),
            ("开盘上涨次数", self.stat_data.get('开盘上涨次数', 0)),
            ("开盘下跌次数", self.stat_data.get('开盘下跌次数', 0)),
        ]

        trade_table.setRowCount(len(trade_stats))
        for i, (name, value) in enumerate(trade_stats):
            trade_table.setItem(i, 0, QTableWidgetItem(name))
            trade_table.setItem(i, 1, QTableWidgetItem(str(value)))

        trade_table.setAlternatingRowColors(True)
        header = trade_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        trade_layout.addWidget(trade_table)
        splitter.addWidget(trade_frame)

        # 右侧：成交量统计
        volume_frame = QFrame()
        volume_frame.setFrameStyle(QFrame.StyledPanel)
        volume_layout = QVBoxLayout(volume_frame)

        volume_title = QLabel("成交量统计")
        volume_title.setAlignment(Qt.AlignCenter)
        volume_title.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 5px;")
        volume_layout.addWidget(volume_title)

        volume_table = QTableWidget()
        volume_table.setColumnCount(2)
        volume_table.setHorizontalHeaderLabels(["指标", "数值"])

        volume_stats = [
            ("成交量均值", self.stat_data.get('成交量均值', 0)),
            ("成交量总和", self.stat_data.get('成交量总和', 0)),
            ("最大成交量", self.stat_data.get('最大成交量', 0)),
            ("最小成交量", self.stat_data.get('最小成交量', 0)),
            ("最大单日涨幅(%)", self.stat_data.get('最大单日涨幅(%)', 0)),
            ("最大单日跌幅(%)", self.stat_data.get('最大单日跌幅(%)', 0)),
            ("最大单日振幅(%)", self.stat_data.get('最大单日振幅(%)', 0)),
            ("最大跳空缺口", self.stat_data.get('最大跳空缺口', 0)),
        ]

        volume_table.setRowCount(len(volume_stats))
        for i, (name, value) in enumerate(volume_stats):
            volume_table.setItem(i, 0, QTableWidgetItem(name))

            # 格式化大数值
            if isinstance(value, (int, float)):
                if value >= 10000:
                    formatted_value = f"{value:,.0f}"
                else:
                    formatted_value = f"{value:.2f}"
            else:
                formatted_value = str(value)

            volume_table.setItem(i, 1, QTableWidgetItem(formatted_value))

        volume_table.setAlternatingRowColors(True)
        header = volume_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        volume_layout.addWidget(volume_table)
        splitter.addWidget(volume_frame)

        return widget

    def _create_chart_tab(self) -> QWidget:
        """创建图表分析标签页"""
        # 延迟导入 matplotlib，避免在没有 QApplication 时崩溃
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            import matplotlib.pyplot as plt
            MATPLOTLIB_AVAILABLE = True
        except ImportError:
            MATPLOTLIB_AVAILABLE = False
            FigureCanvas = None
            Figure = None

        if not MATPLOTLIB_AVAILABLE:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            label = QLabel("图表功能需要安装matplotlib\npip install matplotlib")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            return widget

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 创建matplotlib图形
        fig = Figure(figsize=(12, 8), dpi=100)
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)

        # 创建子图
        ax1 = fig.add_subplot(2, 2, 1)
        ax2 = fig.add_subplot(2, 2, 2)
        ax3 = fig.add_subplot(2, 2, 3)
        ax4 = fig.add_subplot(2, 2, 4)

        try:
            # 绘制价格走势图
            dates = pd.to_datetime(self.kdata.index)
            closes = self.kdata['close'].values

            ax1.plot(dates, closes, linewidth=2, color='#3498db')
            ax1.set_title('价格走势', fontsize=12, fontweight='bold')
            ax1.set_ylabel('价格')
            ax1.grid(True, alpha=0.3)

            # 绘制成交量柱状图
            volumes = self.kdata['volume'].values
            colors = ['red' if self.kdata['close'].iloc[i] >= self.kdata['open'].iloc[i]
                      else 'green' for i in range(len(self.kdata))]

            ax2.bar(dates, volumes, color=colors, alpha=0.7)
            ax2.set_title('成交量分布', fontsize=12, fontweight='bold')
            ax2.set_ylabel('成交量')
            ax2.grid(True, alpha=0.3)

            # 绘制收益率分布直方图
            returns = self.kdata['close'].pct_change().dropna()
            ax3.hist(returns, bins=30, alpha=0.7,
                     color='#9b59b6', edgecolor='black')
            ax3.set_title('收益率分布', fontsize=12, fontweight='bold')
            ax3.set_xlabel('收益率')
            ax3.set_ylabel('频次')
            ax3.grid(True, alpha=0.3)

            # 绘制振幅分布
            amplitude = (
                (self.kdata['high'] - self.kdata['low']) / self.kdata['close'] * 100)
            ax4.hist(amplitude, bins=20, alpha=0.7,
                     color='#e67e22', edgecolor='black')
            ax4.set_title('振幅分布', fontsize=12, fontweight='bold')
            ax4.set_xlabel('振幅(%)')
            ax4.set_ylabel('频次')
            ax4.grid(True, alpha=0.3)

            # 调整布局
            fig.tight_layout()
            canvas.draw()

        except Exception as e:
            logger.error(f"Failed to create charts: {e}")

        return widget

    def _export_report(self):
        """导出报告"""
        try:
            from PyQt5.QtWidgets import QFileDialog, QMessageBox

            filename, _ = QFileDialog.getSaveFileName(
                self,
                "导出统计报告",
                f"区间统计报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt);;所有文件 (*)"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("区间统计分析报告\n")
                    f.write("=" * 50 + "\n\n")

                    f.write("基础统计:\n")
                    f.write("-" * 20 + "\n")
                    for key, value in self.stat_data.items():
                        f.write(f"{key}: {value}\n")

                    f.write(
                        f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

                QMessageBox.information(self, "导出成功", f"报告已导出到: {filename}")

        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "导出失败", f"导出失败: {str(e)}")
