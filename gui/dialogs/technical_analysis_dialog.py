"""
技术分析对话框 - 简化版本

提供技术指标计算、图表显示、分析报告等功能。
"""

from loguru import logger
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit, QComboBox,
    QGroupBox, QFormLayout, QPushButton, QTextEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QSplitter, QListWidget, QListWidgetItem,
    QHeaderView, QMessageBox, QProgressDialog, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from core.indicator_service import calculate_indicator

from .base_dialog import BaseDialog

logger = logger

class TechnicalAnalysisDialog(BaseDialog):
    """技术分析对话框"""

    # 信号
    analysis_completed = pyqtSignal(dict)
    indicator_calculated = pyqtSignal(str, dict)

    def __init__(self, parent=None, stock_code=None, stock_name=None, analysis_service=None):
        """
        初始化技术分析对话框

        Args:
            parent: 父窗口
            stock_code: 股票代码
            stock_name: 股票名称
            analysis_service: 分析服务
        """
        self.stock_code = stock_code
        self.stock_name = stock_name or stock_code or ''
        self.analysis_service = analysis_service
        self.current_data = None
        self.indicators_data = {}
        
        display_name = f"{self.stock_name} ({self.stock_code})" if self.stock_name and self.stock_code else (self.stock_code or '未选择股票')
        
        super().__init__(
            parent,
            title=f"技术分析 - {display_name}",
            size=(1000, 700),
            settings_key="TechnicalAnalysisDialog"
        )
        
        self._setup_ui()
        self._load_stock_data()

    def _setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 指标计算选项卡
        self._create_indicators_tab()

        # 分析报告选项卡
        self._create_analysis_tab()

        # 按钮区域
        button_layout = QHBoxLayout()

        calculate_button = QPushButton("重新计算")
        calculate_button.clicked.connect(self._calculate_indicators)

        export_button = QPushButton("导出分析")
        export_button.clicked.connect(self._export_analysis)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)

        button_layout.addWidget(calculate_button)
        button_layout.addWidget(export_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _create_indicators_tab(self) -> None:
        """创建技术指标选项卡"""
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # 左侧参数设置
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 参数设置
        params_group = QGroupBox("参数设置")
        params_layout = QFormLayout(params_group)

        self.ma_period_spin = QSpinBox()
        self.ma_period_spin.setRange(1, 250)
        self.ma_period_spin.setValue(20)
        params_layout.addRow("MA周期:", self.ma_period_spin)

        self.rsi_period_spin = QSpinBox()
        self.rsi_period_spin.setRange(1, 100)
        self.rsi_period_spin.setValue(14)
        params_layout.addRow("RSI周期:", self.rsi_period_spin)

        left_layout.addWidget(params_group)
        left_layout.addStretch()

        layout.addWidget(left_widget, 1)

        # 右侧结果显示
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 指标结果表格
        self.indicators_table = QTableWidget()
        self.indicators_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.indicators_table)

        layout.addWidget(right_widget, 2)

        self.tab_widget.addTab(tab, "技术指标")

    def _create_analysis_tab(self) -> None:
        """创建分析报告选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 分析报告
        self.analysis_report = QTextEdit()
        self.analysis_report.setReadOnly(True)
        self.analysis_report.setFont(QFont("Consolas", 10))
        layout.addWidget(self.analysis_report)

        self.tab_widget.addTab(tab, "分析报告")

    def _load_stock_data(self) -> None:
        """加载股票数据"""
        try:
            if not self.stock_code:
                return

            # 生成示例数据（实际应从数据服务获取）
            self.current_data = self._generate_sample_data()
            self._calculate_indicators()

        except Exception as e:
            logger.error(f"加载股票数据失败: {e}")

    def _generate_sample_data(self) -> pd.DataFrame:
        """生成示例数据"""
        logger.warning("技术分析示例数据不可用，返回空DataFrame。请配置数据源以获取真实数据。")
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    def _calculate_indicators(self) -> None:
        """计算技术指标 - 使用统一指标服务"""
        try:
            if self.current_data is None or self.current_data.empty:
                QMessageBox.warning(self, "警告", "没有数据可供计算")
                return

            self.indicators_data = {}

            kline_data = self.current_data.copy()
            if 'date' in kline_data.columns:
                kline_data = kline_data.set_index('date')

            ma_period = self.ma_period_spin.value()
            try:
                ma_result = calculate_indicator('MA', kline_data, timeperiod=ma_period)
                if isinstance(ma_result, pd.DataFrame) and 'MA' in ma_result.columns:
                    self.indicators_data['MA'] = ma_result['MA']
                elif isinstance(ma_result, pd.Series):
                    self.indicators_data['MA'] = ma_result
                else:
                    self.indicators_data['MA'] = kline_data['close'].rolling(window=ma_period).mean()
            except Exception as e:
                logger.warning(f"统一服务计算MA失败，使用本地计算: {e}")
                self.indicators_data['MA'] = kline_data['close'].rolling(window=ma_period).mean()

            rsi_period = self.rsi_period_spin.value()
            try:
                rsi_result = calculate_indicator('RSI', kline_data, timeperiod=rsi_period)
                if isinstance(rsi_result, pd.DataFrame) and 'RSI' in rsi_result.columns:
                    self.indicators_data['RSI'] = rsi_result['RSI']
                elif isinstance(rsi_result, pd.Series):
                    self.indicators_data['RSI'] = rsi_result
                else:
                    self.indicators_data['RSI'] = self._calculate_rsi(kline_data['close'], rsi_period)
            except Exception as e:
                logger.warning(f"统一服务计算RSI失败，使用本地计算: {e}")
                self.indicators_data['RSI'] = self._calculate_rsi(kline_data['close'], rsi_period)

            self._display_indicators()

            self._generate_analysis_report()

            logger.info("技术指标计算完成")

        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            QMessageBox.critical(self, "错误", f"计算技术指标失败: {e}")

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _display_indicators(self) -> None:
        """显示技术指标结果"""
        try:
            if not self.indicators_data:
                return

            # 准备表格数据
            dates = self.current_data['date'].dt.strftime('%Y-%m-%d').tolist()

            # 设置表格
            columns = ['日期', '收盘价'] + list(self.indicators_data.keys())
            self.indicators_table.setColumnCount(len(columns))
            self.indicators_table.setHorizontalHeaderLabels(columns)
            self.indicators_table.setRowCount(len(dates))

            # 填充数据
            for row in range(len(dates)):
                self.indicators_table.setItem(
                    row, 0, QTableWidgetItem(dates[row]))
                self.indicators_table.setItem(row, 1, QTableWidgetItem(
                    f"{self.current_data.iloc[row]['close']:.2f}"))

                for col, (indicator, values) in enumerate(self.indicators_data.items(), start=2):
                    if row < len(values) and not pd.isna(values.iloc[row]):
                        self.indicators_table.setItem(
                            row, col, QTableWidgetItem(f"{values.iloc[row]:.2f}"))
                    else:
                        self.indicators_table.setItem(
                            row, col, QTableWidgetItem("--"))

            # 调整列宽
            self.indicators_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"显示技术指标失败: {e}")

    def _generate_analysis_report(self) -> None:
        """生成分析报告"""
        try:
            if not self.indicators_data or self.current_data is None:
                return

            # 获取最新数据
            latest_data = self.current_data.iloc[-1]
            latest_price = latest_data['close']

            report = f"""
技术分析报告
股票代码: {self.stock_code}
分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
最新价格: {latest_price:.2f}

=== 趋势分析 ===
"""

            # MA分析
            if 'MA' in self.indicators_data:
                ma_value = self.indicators_data['MA'].iloc[-1]
                if not pd.isna(ma_value):
                    trend = "上升" if latest_price > ma_value else "下降"
                    report += f"移动平均线({self.ma_period_spin.value()}日): {ma_value:.2f}\n"
                    report += f"价格相对MA: {trend}趋势\n"

            # RSI分析
            if 'RSI' in self.indicators_data:
                rsi_value = self.indicators_data['RSI'].iloc[-1]
                if not pd.isna(rsi_value):
                    if rsi_value > 70:
                        rsi_status = "超买"
                    elif rsi_value < 30:
                        rsi_status = "超卖"
                    else:
                        rsi_status = "正常"
                    report += f"RSI指标: {rsi_value:.2f} ({rsi_status})\n"

            report += "\n=== 综合评价 ===\n"
            report += "基于当前技术指标分析，建议投资者关注以下要点：\n"
            report += "1. 结合多个指标进行综合判断\n"
            report += "2. 注意风险控制，设置止损点\n"
            report += "3. 关注成交量变化确认信号\n"
            report += "4. 本分析仅供参考，不构成投资建议\n"

            self.analysis_report.setPlainText(report)

        except Exception as e:
            logger.error(f"生成分析报告失败: {e}")

    def _export_analysis(self) -> None:
        """导出分析结果"""
        try:
            from PyQt5.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出分析结果",
                f"{self.stock_code}_技术分析.txt",
                "文本文件 (*.txt);;所有文件 (*)"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.analysis_report.toPlainText())

                QMessageBox.information(self, "成功", f"分析结果已导出到: {file_path}")

        except Exception as e:
            logger.error(f"导出分析结果失败: {e}")
            QMessageBox.critical(self, "错误", f"导出分析结果失败: {e}")
