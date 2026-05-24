"""
数据导出对话框

【已废弃 - DEPRECATED】

此文件已被新的统一数据管理对话框替代：
- 新文件：data_management_dialog_unified.py
- 新类：UnifiedDataManagementDialog

本文件保留仅用于向后兼容性，将在未来版本中删除。
建议迁移到新的统一数据管理对话框。

原有功能：
- 提供完整的数据导出功能
- 支持单股票和批量导出

作者: FactorWeave-Quant团队
版本: 1.0 (已废弃)
废弃日期: 2026-05-13
"""

import warnings
warnings.warn(
    "DataExportDialog is deprecated and will be removed in a future version. "
    "Use UnifiedDataManagementDialog from data_management_dialog_unified.py instead.",
    DeprecationWarning,
    stacklevel=2
)

from loguru import logger
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QGridLayout, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter,
    QProgressBar, QMessageBox, QFileDialog, QDateEdit,
    QTextEdit, QTabWidget, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QDate
from PyQt5.QtGui import QFont

from .base_dialog import BaseDialog
from core.real_data_provider import get_real_data_provider

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
        try:
            stock_code = self.export_params.get('stock_code', '')
            stock_name = self.export_params.get('stock_name', '')
            file_path = self.export_params.get('file_path', '')
            start_date = self.export_params.get('start_date')
            end_date = self.export_params.get('end_date')

            import pandas as pd

            self.export_progress.emit(10)

            try:
                provider = get_real_data_provider()
                start_str = start_date.strftime('%Y-%m-%d') if start_date else None
                end_str = end_date.strftime('%Y-%m-%d') if end_date else None

                kdata = provider.get_real_kdata(
                    code=stock_code,
                    freq='D',
                    start_date=start_str,
                    end_date=end_str
                )
            except Exception as e:
                logger.warning(f"RealDataProvider获取数据失败: {e}")
                kdata = pd.DataFrame()

            if kdata.empty:
                self.export_error.emit(f"股票 {stock_code} 暂无数据可导出，请确认数据源是否可用")
                return

            self.export_progress.emit(30)

            col_map = {
                'open': '开盘价', 'high': '最高价', 'low': '最低价',
                'close': '收盘价', 'volume': '成交量'
            }
            export_cols = []
            for src, dst in col_map.items():
                if src in kdata.columns:
                    kdata = kdata.rename(columns={src: dst})
                    export_cols.append(dst)

            if isinstance(kdata.index, pd.DatetimeIndex):
                kdata['日期'] = kdata.index.strftime('%Y-%m-%d')
            elif 'datetime' in kdata.columns:
                kdata['日期'] = pd.to_datetime(kdata['datetime']).dt.strftime('%Y-%m-%d')
            elif 'date' in kdata.columns:
                kdata['日期'] = pd.to_datetime(kdata['date']).dt.strftime('%Y-%m-%d')
            export_cols.insert(0, '日期')

            if '成交额' not in kdata.columns and '收盘价' in kdata.columns and '成交量' in kdata.columns:
                kdata['成交额'] = round(kdata['收盘价'] * kdata['成交量'], 2)
                export_cols.append('成交额')

            df = kdata[export_cols].copy()
            df = df.reset_index(drop=True)

            self.export_progress.emit(70)

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                info_df = pd.DataFrame([
                    ['股票代码', stock_code],
                    ['股票名称', stock_name],
                    ['数据起始日期', df['日期'].iloc[0] if not df.empty else ''],
                    ['数据结束日期', df['日期'].iloc[-1] if not df.empty else ''],
                    ['数据条数', len(df)],
                    ['导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                    ['数据来源', '真实市场数据']
                ], columns=['项目', '值'])
                info_df.to_excel(writer, sheet_name='基本信息', index=False)

                df.to_excel(writer, sheet_name='K线数据', index=False)

                if '最高价' in df.columns and '最低价' in df.columns and '收盘价' in df.columns and '成交量' in df.columns:
                    stats_data = [
                        ['最高价', df['最高价'].max()],
                        ['最低价', df['最低价'].min()],
                        ['平均收盘价', round(df['收盘价'].mean(), 2)],
                        ['总成交量', int(df['成交量'].sum())],
                    ]
                    if '成交额' in df.columns:
                        stats_data.append(['总成交额', round(df['成交额'].sum(), 2)])
                    if '开盘价' in df.columns:
                        valid_mask = df['开盘价'] > 0
                        if valid_mask.any():
                            daily_return = ((df.loc[valid_mask, '收盘价'] / df.loc[valid_mask, '开盘价'] - 1) * 100)
                            stats_data.append(['最大单日涨幅', round(daily_return.max(), 2)])
                            stats_data.append(['最大单日跌幅', round(daily_return.min(), 2)])
                    stats_df = pd.DataFrame(stats_data, columns=['统计项', '数值'])
                    stats_df.to_excel(writer, sheet_name='统计信息', index=False)

            self.export_progress.emit(100)
            self.export_completed.emit(file_path)

        except Exception as e:
            logger.error(f"Single stock export failed: {e}")
            self.export_error.emit(f"单股票导出失败: {str(e)}")

    def _export_batch_stocks(self):
        try:
            stocks = self.export_params.get('stocks', [])
            file_path = self.export_params.get('file_path', '')

            import pandas as pd

            try:
                provider = get_real_data_provider()
            except Exception as e:
                logger.warning(f"RealDataProvider初始化失败: {e}")
                self.export_error.emit("数据提供器不可用，无法导出数据")
                return

            all_data = []
            total = len(stocks)

            for i, stock in enumerate(stocks):
                code = stock.get('code', '')
                name = stock.get('name', '')
                market = stock.get('market', '')

                try:
                    kdata = provider.get_real_kdata(code=code, freq='D', count=1)
                except Exception:
                    kdata = pd.DataFrame()

                if kdata.empty:
                    current_price = None
                    volume_info = '无数据'
                else:
                    last_row = kdata.iloc[-1]
                    current_price = round(float(last_row.get('close', 0)), 2) if 'close' in last_row.index else None
                    vol = int(last_row.get('volume', 0)) if 'volume' in last_row.index else 0
                    volume_info = f"{vol / 10000:.0f}万手" if vol > 0 else '-'

                stock_data = {
                    '股票代码': code,
                    '股票名称': name,
                    '市场': market,
                    '行业': stock.get('industry', '-'),
                    '当前价格': current_price if current_price else '-',
                    '成交量': volume_info,
                    '数据状态': '有数据' if current_price else '无数据'
                }
                all_data.append(stock_data)

                progress = int((i + 1) / total * 90)
                self.export_progress.emit(progress)

            if not all_data:
                self.export_error.emit("所有股票均无数据可导出")
                return

            df = pd.DataFrame(all_data)
            df.to_excel(file_path, sheet_name='股票列表', index=False)

            self.export_progress.emit(100)
            self.export_completed.emit(file_path)

        except Exception as e:
            logger.error(f"Batch export failed: {e}")
            self.export_error.emit(f"批量导出失败: {str(e)}")

class DataExportDialog(BaseDialog):
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
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.stocks = stocks or []
        self.export_worker = None

        # 确定导出模式
        self.export_mode = 'single' if stock_code else 'batch'
        title_text = "单股票数据导出" if self.export_mode == 'single' else "批量数据导出"

        super().__init__(
            parent,
            title=title_text,
            min_size=(600, 500),
            size=(700, 600),
            settings_key="DataExportDialog"
        )

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

            super().closeEvent(event)
            event.accept()
        except Exception as e:
            logger.error(f"Failed to close dialog: {e}")
            super().closeEvent(event)
            event.accept()
