"""
数据导出对话框

提供完整的数据导出功能，支持单股票和批量导出。
"""

from loguru import logger
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QGridLayout, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter,
    QProgressBar, QMessageBox, QFileDialog, QDateEdit,
    QTextEdit, QTabWidget, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QDate
from PyQt5.QtGui import QFont

class ExportWorker(QThread):
    """导出工作线程"""

    export_completed = pyqtSignal(str)  # 导出完成，返回文件路径
    export_error = pyqtSignal(str)
    export_progress = pyqtSignal(int)

    def __init__(self, export_params: Dict[str, Any]):
        super().__init__()
        self.export_params = export_params

    def run(self):
        """执行导出"""
        try:
            export_type = self.export_params.get('type', 'single')

            if export_type == 'single':
                self._export_single_stock()
            elif export_type == 'batch':
                self._export_batch_stocks()
            else:
                self.export_error.emit("未知的导出类型")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.export_error.emit(str(e))

    def _export_single_stock(self):
        """导出单只股票数据"""
        try:
            stock_code = self.export_params.get('stock_code', '')
            stock_name = self.export_params.get('stock_name', '')
            file_path = self.export_params.get('file_path', '')
            start_date = self.export_params.get('start_date')
            end_date = self.export_params.get('end_date')

            # 模拟数据生成过程
            import pandas as pd
            import numpy as np

            # 生成模拟K线数据
            date_range = pd.date_range(
                start=start_date, end=end_date, freq='D')
            dates = [d for d in date_range if d.weekday() < 5]  # 只包含工作日

            self.export_progress.emit(20)

            # 生成模拟OHLCV数据
            base_price = 10.0
            data = []

            for i, date in enumerate(dates):
                # 模拟价格波动
                change = np.random.normal(0, 0.02)
                open_price = base_price * (1 + change)
                high_price = open_price * (1 + abs(np.random.normal(0, 0.01)))
                low_price = open_price * (1 - abs(np.random.normal(0, 0.01)))
                close_price = open_price * (1 + np.random.normal(0, 0.01))
                volume = np.random.randint(100000, 1000000)

                data.append({
                    '日期': date.strftime('%Y-%m-%d'),
                    '开盘价': round(open_price, 2),
                    '最高价': round(high_price, 2),
                    '最低价': round(low_price, 2),
                    '收盘价': round(close_price, 2),
                    '成交量': volume,
                    '成交额': round(volume * close_price, 2)
                })

                base_price = close_price

                # 更新进度
                progress = 20 + int((i + 1) / len(dates) * 60)
                self.export_progress.emit(progress)

            # 创建DataFrame
            df = pd.DataFrame(data)

            self.export_progress.emit(85)

            # 导出到Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 基本信息sheet
                info_df = pd.DataFrame([
                    ['股票代码', stock_code],
                    ['股票名称', stock_name],
                    ['数据起始日期', start_date.strftime('%Y-%m-%d')],
                    ['数据结束日期', end_date.strftime('%Y-%m-%d')],
                    ['数据条数', len(df)],
                    ['导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                ], columns=['项目', '值'])
                info_df.to_excel(writer, sheet_name='基本信息', index=False)

                # K线数据sheet
                df.to_excel(writer, sheet_name='K线数据', index=False)

                # 统计信息sheet
                stats_df = pd.DataFrame([
                    ['最高价', df['最高价'].max()],
                    ['最低价', df['最低价'].min()],
                    ['平均价', df['收盘价'].mean()],
                    ['总成交量', df['成交量'].sum()],
                    ['总成交额', df['成交额'].sum()],
                    ['价格标准差', df['收盘价'].std()],
                    ['最大单日涨幅', ((df['收盘价'] / df['开盘价'] - 1) * 100).max()],
                    ['最大单日跌幅', ((df['收盘价'] / df['开盘价'] - 1) * 100).min()]
                ], columns=['统计项', '数值'])
                stats_df.to_excel(writer, sheet_name='统计信息', index=False)

            self.export_progress.emit(100)
            self.export_completed.emit(file_path)

        except Exception as e:
            logger.error(f"Single stock export failed: {e}")
            self.export_error.emit(f"单股票导出失败: {str(e)}")

    def _export_batch_stocks(self):
        """批量导出股票数据"""
        try:
            stocks = self.export_params.get('stocks', [])
            file_path = self.export_params.get('file_path', '')

            # 模拟批量导出

            all_data = []
            for i, stock in enumerate(stocks):
                # 模拟每只股票的基本数据
                stock_data = {
                    '股票代码': stock.get('code', ''),
                    '股票名称': stock.get('name', ''),
                    '市场': stock.get('market', ''),
                    '行业': stock.get('industry', '未知'),
                    '当前价格': round(10.0 + i * 0.5, 2),
                    '市值': f"{100 + i * 10}亿",
                    '成交量': f"{1000 + i * 100}万手"
                }
                all_data.append(stock_data)

                # 更新进度
                progress = int((i + 1) / len(stocks) * 90)
                self.export_progress.emit(progress)

            # 导出到Excel
            df = pd.DataFrame(all_data)
            df.to_excel(file_path, sheet_name='股票列表', index=False)

            self.export_progress.emit(100)
            self.export_completed.emit(file_path)

        except Exception as e:
            logger.error(f"Batch export failed: {e}")
            self.export_error.emit(f"批量导出失败: {str(e)}")

class DataExportDialog(QDialog):
    """数据导出对话框"""

    def __init__(self, parent=None, stock_code=None, stock_name=None, stocks=None):
        """
        初始化数据导出对话框

        Args:
            parent: 父窗口
            stock_code: 单股票代码（单股票导出模式）
            stock_name: 单股票名称（单股票导出模式）
            stocks: 股票列表（批量导出模式）
        """
        super().__init__(parent)
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.stocks = stocks or []
        self.export_worker = None

        # 确定导出模式
        self.export_mode = 'single' if stock_code else 'batch'

        self.setWindowTitle("数据导出")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        title_text = "单股票数据导出" if self.export_mode == 'single' else "批量数据导出"
        title_label = QLabel(title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 5px;
            }
        """)
        layout.addWidget(title_label)

        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        if self.export_mode == 'single':
            # 单股票导出标签页
            single_tab = self._create_single_export_tab()
            tab_widget.addTab(single_tab, "单股票导出")
        else:
            # 批量导出标签页
            batch_tab = self._create_batch_export_tab()
            tab_widget.addTab(batch_tab, "批量导出")

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(
            "color: #6c757d; font-size: 12px; padding: 5px;")
        layout.addWidget(self.status_label)

        # 按钮栏
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        # 开始导出按钮
        export_btn = QPushButton("开始导出")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        export_btn.clicked.connect(self._start_export)
        button_layout.addWidget(export_btn)

        button_layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

    def _create_single_export_tab(self) -> QWidget:
        """创建单股票导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 股票信息组
        info_group = QGroupBox("股票信息")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("股票代码:"), 0, 0)
        self.code_label = QLabel(self.stock_code or "未选择")
        self.code_label.setStyleSheet("font-weight: bold; color: #007bff;")
        info_layout.addWidget(self.code_label, 0, 1)

        info_layout.addWidget(QLabel("股票名称:"), 1, 0)
        self.name_label = QLabel(self.stock_name or "未选择")
        self.name_label.setStyleSheet("font-weight: bold; color: #007bff;")
        info_layout.addWidget(self.name_label, 1, 1)

        layout.addWidget(info_group)

        # 导出设置组
        settings_group = QGroupBox("导出设置")
        settings_layout = QGridLayout(settings_group)

        # 日期范围
        settings_layout.addWidget(QLabel("开始日期:"), 0, 0)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addYears(-1))
        settings_layout.addWidget(self.start_date_edit, 0, 1)

        settings_layout.addWidget(QLabel("结束日期:"), 0, 2)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        settings_layout.addWidget(self.end_date_edit, 0, 3)

        # 导出格式
        settings_layout.addWidget(QLabel("导出格式:"), 1, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Excel (.xlsx)", "CSV (.csv)"])
        settings_layout.addWidget(self.format_combo, 1, 1)

        # 包含的数据
        settings_layout.addWidget(QLabel("包含数据:"), 2, 0)

        data_layout = QHBoxLayout()
        self.include_kline = QCheckBox("K线数据")
        self.include_kline.setChecked(True)
        data_layout.addWidget(self.include_kline)

        self.include_volume = QCheckBox("成交量")
        self.include_volume.setChecked(True)
        data_layout.addWidget(self.include_volume)

        self.include_indicators = QCheckBox("技术指标")
        self.include_indicators.setChecked(False)
        data_layout.addWidget(self.include_indicators)

        settings_layout.addLayout(data_layout, 2, 1, 1, 3)

        layout.addWidget(settings_group)

        # 文件保存组
        file_group = QGroupBox("保存位置")
        file_layout = QHBoxLayout(file_group)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择保存位置...")
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_save_path)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        layout.addStretch()
        return widget

    def _create_batch_export_tab(self) -> QWidget:
        """创建批量导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 股票列表组
        list_group = QGroupBox(f"股票列表 (共 {len(self.stocks)} 只)")
        list_layout = QVBoxLayout(list_group)

        # 股票列表表格
        self.stocks_table = QTableWidget()
        self.stocks_table.setColumnCount(4)
        self.stocks_table.setHorizontalHeaderLabels(
            ["股票代码", "股票名称", "市场", "状态"])

        # 填充股票数据
        self.stocks_table.setRowCount(len(self.stocks))
        for i, stock in enumerate(self.stocks):
            self.stocks_table.setItem(
                i, 0, QTableWidgetItem(stock.get('code', '')))
            self.stocks_table.setItem(
                i, 1, QTableWidgetItem(stock.get('name', '')))
            self.stocks_table.setItem(
                i, 2, QTableWidgetItem(stock.get('market', '')))
            self.stocks_table.setItem(i, 3, QTableWidgetItem("待导出"))

        # 调整列宽
        header = self.stocks_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        list_layout.addWidget(self.stocks_table)
        layout.addWidget(list_group)

        # 导出设置组
        settings_group = QGroupBox("导出设置")
        settings_layout = QGridLayout(settings_group)

        # 导出格式
        settings_layout.addWidget(QLabel("导出格式:"), 0, 0)
        self.batch_format_combo = QComboBox()
        self.batch_format_combo.addItems(["Excel (.xlsx)", "CSV (.csv)"])
        settings_layout.addWidget(self.batch_format_combo, 0, 1)

        layout.addWidget(settings_group)

        # 文件保存组
        file_group = QGroupBox("保存位置")
        file_layout = QHBoxLayout(file_group)

        self.batch_file_path_edit = QLineEdit()
        self.batch_file_path_edit.setPlaceholderText("选择保存位置...")
        file_layout.addWidget(self.batch_file_path_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_batch_save_path)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        return widget

    def _browse_save_path(self):
        """浏览保存路径（单股票）"""
        try:
            default_filename = f"{self.stock_code}_{self.stock_name}_数据.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存股票数据",
                default_filename,
                "Excel文件 (*.xlsx);;CSV文件 (*.csv);;所有文件 (*)"
            )

            if file_path:
                self.file_path_edit.setText(file_path)

        except Exception as e:
            logger.error(f"Failed to browse save path: {e}")

    def _browse_batch_save_path(self):
        """浏览保存路径（批量）"""
        try:
            default_filename = f"股票列表_{datetime.now().strftime('%Y%m%d')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存股票列表",
                default_filename,
                "Excel文件 (*.xlsx);;CSV文件 (*.csv);;所有文件 (*)"
            )

            if file_path:
                self.batch_file_path_edit.setText(file_path)

        except Exception as e:
            logger.error(f"Failed to browse batch save path: {e}")

    def _start_export(self):
        """开始导出"""
        try:
            if self.export_mode == 'single':
                self._start_single_export()
            else:
                self._start_batch_export()

        except Exception as e:
            logger.error(f"Failed to start export: {e}")
            QMessageBox.critical(self, "导出错误", f"启动导出失败: {str(e)}")

    def _start_single_export(self):
        """开始单股票导出"""
        try:
            # 验证输入
            if not self.stock_code:
                QMessageBox.warning(self, "提示", "请先选择股票")
                return

            file_path = self.file_path_edit.text().strip()
            if not file_path:
                QMessageBox.warning(self, "提示", "请选择保存位置")
                return

            # 收集导出参数
            export_params = {
                'type': 'single',
                'stock_code': self.stock_code,
                'stock_name': self.stock_name,
                'file_path': file_path,
                'start_date': self.start_date_edit.date().toPyDate(),
                'end_date': self.end_date_edit.date().toPyDate(),
                'format': self.format_combo.currentText(),
                'include_kline': self.include_kline.isChecked(),
                'include_volume': self.include_volume.isChecked(),
                'include_indicators': self.include_indicators.isChecked(),
            }

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("正在导出...")

            # 启动导出线程
            self.export_worker = ExportWorker(export_params)
            self.export_worker.export_completed.connect(
                self._on_export_completed)
            self.export_worker.export_error.connect(self._on_export_error)
            self.export_worker.export_progress.connect(
                self._on_export_progress)
            self.export_worker.start()

        except Exception as e:
            logger.error(f"Failed to start single export: {e}")
            QMessageBox.critical(self, "导出错误", f"启动单股票导出失败: {str(e)}")

    def _start_batch_export(self):
        """开始批量导出"""
        try:
            # 验证输入
            if not self.stocks:
                QMessageBox.warning(self, "提示", "没有可导出的股票")
                return

            file_path = self.batch_file_path_edit.text().strip()
            if not file_path:
                QMessageBox.warning(self, "提示", "请选择保存位置")
                return

            # 收集导出参数
            export_params = {
                'type': 'batch',
                'stocks': self.stocks,
                'file_path': file_path,
                'format': self.batch_format_combo.currentText(),
            }

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("正在批量导出...")

            # 启动导出线程
            self.export_worker = ExportWorker(export_params)
            self.export_worker.export_completed.connect(
                self._on_export_completed)
            self.export_worker.export_error.connect(self._on_export_error)
            self.export_worker.export_progress.connect(
                self._on_export_progress)
            self.export_worker.start()

        except Exception as e:
            logger.error(f"Failed to start batch export: {e}")
            QMessageBox.critical(self, "导出错误", f"启动批量导出失败: {str(e)}")

    def _on_export_progress(self, progress: int):
        """更新导出进度"""
        self.progress_bar.setValue(progress)

    def _on_export_completed(self, file_path: str):
        """导出完成处理"""
        try:
            # 隐藏进度条
            self.progress_bar.setVisible(False)
            self.status_label.setText("导出完成")

            # 显示成功消息
            reply = QMessageBox.question(
                self,
                "导出完成",
                f"数据已成功导出到:\n{file_path}\n\n是否打开文件所在位置？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 打开文件所在目录
                import subprocess
                import platform

                folder_path = os.path.dirname(file_path)
                if platform.system() == "Windows":
                    subprocess.run(['explorer', folder_path])
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(['open', folder_path])
                else:  # Linux
                    subprocess.run(['xdg-open', folder_path])

        except Exception as e:
            logger.error(f"Failed to handle export completion: {e}")

    def _on_export_error(self, error_msg: str):
        """导出错误处理"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        self.status_label.setText("导出失败")

        # 显示错误信息
        QMessageBox.critical(self, "导出错误", f"导出失败: {error_msg}")
        logger.error(f"Export error: {error_msg}")

    def closeEvent(self, event):
        """关闭事件处理"""
        try:
            # 停止导出线程
            if self.export_worker and self.export_worker.isRunning():
                self.export_worker.quit()
                self.export_worker.wait()

            event.accept()
        except Exception as e:
            logger.error(f"Failed to close dialog: {e}")
            event.accept()
