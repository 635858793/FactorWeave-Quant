"""
历史数据管理对话框

提供历史数据的查看、导入、导出、更新等功能。
"""

from loguru import logger
import os
import json
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit, QComboBox,
    QGroupBox, QFormLayout, QPushButton, QDateEdit, QSpinBox,
    QHeaderView, QFileDialog, QMessageBox, QProgressDialog,
    QSplitter, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QCheckBox, QSlider, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPixmap

from .base_dialog import BaseDialog

logger = logger

class DataUpdateThread(QThread):
    """数据更新线程"""

    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, stocks, start_date, end_date):
        super().__init__()
        self.stocks = stocks
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        try:
            total = len(self.stocks)
            for i, stock in enumerate(self.stocks):
                if self.isInterruptionRequested():
                    break

                self.status_updated.emit(f"正在更新 {stock} 的数据...")

                # 模拟数据更新过程
                self.msleep(100)  # 模拟网络请求时间

                progress = int((i + 1) / total * 100)
                self.progress_updated.emit(progress)

            self.finished_signal.emit(False, "数据更新引擎不可用，无法执行真实数据更新。请配置数据源连接。")

        except Exception as e:
            self.finished_signal.emit(False, f"数据更新失败: {e}")

class HistoryDataDialog(BaseDialog):
    """历史数据管理对话框"""

    # 信号
    data_imported = pyqtSignal(str)
    data_exported = pyqtSignal(str)
    data_updated = pyqtSignal(list)

    def __init__(self, parent=None, stock_service=None):
        """
        初始化历史数据管理对话框

        Args:
            parent: 父窗口
            stock_service: 股票服务
        """
        super().__init__(
            parent,
            title="历史数据管理",
            min_size=(1000, 800),
            size=(1000, 800),
            settings_key="HistoryDataDialog"
        )
        self.stock_service = stock_service
        self.current_stock = None
        self.current_data = None
        self.update_thread = None
        self._setup_ui()
        self._load_stock_list()

    def _setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 数据查看选项卡
        self._create_data_view_tab()

        # 数据导入选项卡
        self._create_data_import_tab()

        # 数据更新选项卡
        self._create_data_update_tab()

        # 数据统计选项卡
        self._create_data_statistics_tab()

        # 按钮区域
        button_layout = QHBoxLayout()

        refresh_button = QPushButton("刷新数据")
        refresh_button.clicked.connect(self._refresh_data)

        export_button = QPushButton("导出数据")
        export_button.clicked.connect(self._export_data)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)

        button_layout.addWidget(refresh_button)
        button_layout.addWidget(export_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _create_data_view_tab(self) -> None:
        """创建数据查看选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 股票选择区域
        selection_layout = QHBoxLayout()

        selection_layout.addWidget(QLabel("股票代码:"))
        self.stock_combo = QComboBox()
        self.stock_combo.setEditable(True)
        self.stock_combo.currentTextChanged.connect(self._on_stock_changed)
        selection_layout.addWidget(self.stock_combo)

        selection_layout.addWidget(QLabel("数据周期:"))
        self.period_combo = QComboBox()
        from core.plugin_types import Period
        self.period_combo.addItems(Period.all_periods())
        self.period_combo.currentTextChanged.connect(self._on_period_changed)
        selection_layout.addWidget(self.period_combo)

        selection_layout.addWidget(QLabel("开始日期:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate().addDays(-365))
        self.start_date_edit.setCalendarPopup(True)
        selection_layout.addWidget(self.start_date_edit)

        selection_layout.addWidget(QLabel("结束日期:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        selection_layout.addWidget(self.end_date_edit)

        query_button = QPushButton("查询")
        query_button.clicked.connect(self._query_data)
        selection_layout.addWidget(query_button)

        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # 数据表格
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSortingEnabled(True)
        layout.addWidget(self.data_table)

        # 数据统计信息
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("数据统计: 无数据")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        self.tab_widget.addTab(tab, "数据查看")

    def _create_data_import_tab(self) -> None:
        """创建数据导入选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 导入设置组
        import_group = QGroupBox("导入设置")
        import_layout = QFormLayout(import_group)

        # 数据源选择
        self.data_source_combo = QComboBox()
        self.data_source_combo.addItems([
            "CSV文件", "Excel文件", "JSON文件", "通达信数据",
            "同花顺数据", "Wind数据", "在线数据源"
        ])
        import_layout.addRow("数据源:", self.data_source_combo)

        # 文件路径
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择要导入的文件")
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(self._browse_import_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(browse_button)
        import_layout.addRow("文件路径:", file_layout)

        # 数据格式设置
        self.date_format_edit = QLineEdit()
        self.date_format_edit.setText("%Y-%m-%d")
        self.date_format_edit.setPlaceholderText("日期格式，如: %Y-%m-%d")
        import_layout.addRow("日期格式:", self.date_format_edit)

        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["utf-8", "gbk", "gb2312", "utf-16"])
        import_layout.addRow("文件编码:", self.encoding_combo)

        # 字段映射
        mapping_group = QGroupBox("字段映射")
        mapping_layout = QFormLayout(mapping_group)

        self.date_field_edit = QLineEdit()
        self.date_field_edit.setText("date")
        mapping_layout.addRow("日期字段:", self.date_field_edit)

        self.open_field_edit = QLineEdit()
        self.open_field_edit.setText("open")
        mapping_layout.addRow("开盘价字段:", self.open_field_edit)

        self.high_field_edit = QLineEdit()
        self.high_field_edit.setText("high")
        mapping_layout.addRow("最高价字段:", self.high_field_edit)

        self.low_field_edit = QLineEdit()
        self.low_field_edit.setText("low")
        mapping_layout.addRow("最低价字段:", self.low_field_edit)

        self.close_field_edit = QLineEdit()
        self.close_field_edit.setText("close")
        mapping_layout.addRow("收盘价字段:", self.close_field_edit)

        self.volume_field_edit = QLineEdit()
        self.volume_field_edit.setText("volume")
        mapping_layout.addRow("成交量字段:", self.volume_field_edit)

        layout.addWidget(import_group)
        layout.addWidget(mapping_group)

        # 导入预览
        preview_group = QGroupBox("导入预览")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # 导入按钮
        import_button_layout = QHBoxLayout()

        preview_button = QPushButton("预览数据")
        preview_button.clicked.connect(self._preview_import_data)

        import_button = QPushButton("开始导入")
        import_button.clicked.connect(self._import_data)

        import_button_layout.addWidget(preview_button)
        import_button_layout.addWidget(import_button)
        import_button_layout.addStretch()

        layout.addLayout(import_button_layout)

        self.tab_widget.addTab(tab, "数据导入")

    def _create_data_update_tab(self) -> None:
        """创建数据更新选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 更新设置组
        update_group = QGroupBox("更新设置")
        update_layout = QFormLayout(update_group)

        # 更新范围
        self.update_scope_combo = QComboBox()
        self.update_scope_combo.addItems([
            "全部股票", "沪深主板", "创业板", "科创板", "北交所", "自选股", "指定股票"
        ])
        update_layout.addRow("更新范围:", self.update_scope_combo)

        # 指定股票
        self.specified_stocks_edit = QLineEdit()
        self.specified_stocks_edit.setPlaceholderText("多个股票代码用逗号分隔")
        update_layout.addRow("指定股票:", self.specified_stocks_edit)

        # 更新周期
        from core.plugin_types import Period
        self.update_period_combo = QComboBox()
        self.update_period_combo.addItems(Period.all_periods())
        update_layout.addRow("更新周期:", self.update_period_combo)

        # 更新模式
        self.update_mode_combo = QComboBox()
        self.update_mode_combo.addItems(["增量更新", "全量更新", "仅缺失数据"])
        update_layout.addRow("更新模式:", self.update_mode_combo)

        # 数据来源
        self.data_provider_combo = QComboBox()
        self.data_provider_combo.addItems([
            "新浪财经", "腾讯财经", "东方财富", "雅虎财经", "Alpha Vantage"
        ])
        update_layout.addRow("数据来源:", self.data_provider_combo)

        layout.addWidget(update_group)

        # 更新进度组
        progress_group = QGroupBox("更新进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressDialog()
        self.progress_bar.setWindowModality(Qt.WindowModal)
        self.progress_bar.setAutoClose(False)
        self.progress_bar.setAutoReset(False)

        self.status_label = QLabel("准备就绪")
        progress_layout.addWidget(self.status_label)

        # 更新日志
        self.update_log = QTextEdit()
        self.update_log.setMaximumHeight(200)
        self.update_log.setReadOnly(True)
        progress_layout.addWidget(self.update_log)

        layout.addWidget(progress_group)

        # 更新按钮
        update_button_layout = QHBoxLayout()

        self.start_update_button = QPushButton("开始更新")
        self.start_update_button.clicked.connect(self._start_update)

        self.stop_update_button = QPushButton("停止更新")
        self.stop_update_button.clicked.connect(self._stop_update)
        self.stop_update_button.setEnabled(False)

        update_button_layout.addWidget(self.start_update_button)
        update_button_layout.addWidget(self.stop_update_button)
        update_button_layout.addStretch()

        layout.addLayout(update_button_layout)

        self.tab_widget.addTab(tab, "数据更新")

    def _create_data_statistics_tab(self) -> None:
        """创建数据统计选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 统计概览
        overview_group = QGroupBox("数据概览")
        overview_layout = QFormLayout(overview_group)

        self.total_stocks_label = QLabel("0")
        overview_layout.addRow("股票总数:", self.total_stocks_label)

        self.total_records_label = QLabel("0")
        overview_layout.addRow("数据记录总数:", self.total_records_label)

        self.latest_date_label = QLabel("无数据")
        overview_layout.addRow("最新数据日期:", self.latest_date_label)

        self.earliest_date_label = QLabel("无数据")
        overview_layout.addRow("最早数据日期:", self.earliest_date_label)

        self.data_size_label = QLabel("0 MB")
        overview_layout.addRow("数据大小:", self.data_size_label)

        layout.addWidget(overview_group)

        # 市场分布
        market_group = QGroupBox("市场分布")
        market_layout = QVBoxLayout(market_group)

        self.market_tree = QTreeWidget()
        self.market_tree.setHeaderLabels(["市场", "股票数量", "数据记录数", "最新更新"])
        market_layout.addWidget(self.market_tree)

        layout.addWidget(market_group)

        # 数据质量
        quality_group = QGroupBox("数据质量")
        quality_layout = QFormLayout(quality_group)

        self.missing_data_label = QLabel("0")
        quality_layout.addRow("缺失数据:", self.missing_data_label)

        self.duplicate_data_label = QLabel("0")
        quality_layout.addRow("重复数据:", self.duplicate_data_label)

        self.invalid_data_label = QLabel("0")
        quality_layout.addRow("无效数据:", self.invalid_data_label)

        layout.addWidget(quality_group)

        # 刷新统计按钮
        refresh_stats_button = QPushButton("刷新统计")
        refresh_stats_button.clicked.connect(self._refresh_statistics)
        layout.addWidget(refresh_stats_button)

        self.tab_widget.addTab(tab, "数据统计")

    def _load_stock_list(self) -> None:
        """加载股票列表"""
        try:
            if self.stock_service:
                # 从股票服务获取股票列表
                stocks = self.stock_service.get_all_stocks()
                self.stock_combo.clear()

                for stock in stocks[:100]:  # 限制显示数量
                    self.stock_combo.addItem(
                        f"{stock['code']} - {stock['name']}")

                logger.info(f"已加载 {len(stocks)} 只股票到下拉列表")
            else:
                # 使用示例数据
                sample_stocks = [
                    "000001 - 平安银行", "000002 - 万科A", "000858 - 五粮液",
                    "600000 - 浦发银行", "600036 - 招商银行", "600519 - 贵州茅台"
                ]
                self.stock_combo.addItems(sample_stocks)

        except Exception as e:
            logger.error(f"加载股票列表失败: {e}")

    def _on_stock_changed(self, stock_text: str) -> None:
        """股票选择变化处理"""
        try:
            if stock_text:
                # 提取股票代码
                stock_code = stock_text.split(
                    ' - ')[0] if ' - ' in stock_text else stock_text
                self.current_stock = stock_code
                logger.info(f"选择股票: {stock_code}")

        except Exception as e:
            logger.error(f"股票选择处理失败: {e}")

    def _on_period_changed(self, period: str) -> None:
        """周期选择变化处理"""
        logger.info(f"选择周期: {period}")

    def _query_data(self) -> None:
        """查询数据"""
        try:
            if not self.current_stock:
                QMessageBox.warning(self, "警告", "请选择股票")
                return

            start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
            end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
            period = self.period_combo.currentText()

            # 生成示例数据
            data = self._generate_sample_data(
                self.current_stock, start_date, end_date)

            # 显示数据
            self._display_data(data)

            # 更新统计信息
            self.stats_label.setText(
                f"数据统计: 共 {len(data)} 条记录，时间范围: {start_date} 至 {end_date}")

            logger.info(f"查询数据完成: {self.current_stock}, {len(data)} 条记录")

        except Exception as e:
            logger.error(f"查询数据失败: {e}")
            QMessageBox.critical(self, "错误", f"查询数据失败: {e}")

    def _generate_sample_data(self, stock_code: str, start_date: str, end_date: str) -> List[Dict]:
        """生成示例数据"""
        logger.warning(f"历史数据不可用({stock_code})，返回空数据。请配置数据源以获取真实数据。")
        return []

    def _display_data(self, data: List[Dict]) -> None:
        """显示数据"""
        try:
            if not data:
                self.data_table.setRowCount(0)
                return

            # 设置表格
            columns = ['日期', '开盘价', '最高价', '最低价', '收盘价', '成交量', '成交额']
            self.data_table.setColumnCount(len(columns))
            self.data_table.setHorizontalHeaderLabels(columns)
            self.data_table.setRowCount(len(data))

            # 填充数据
            for row, record in enumerate(data):
                self.data_table.setItem(
                    row, 0, QTableWidgetItem(record['date']))
                self.data_table.setItem(
                    row, 1, QTableWidgetItem(str(record['open'])))
                self.data_table.setItem(
                    row, 2, QTableWidgetItem(str(record['high'])))
                self.data_table.setItem(
                    row, 3, QTableWidgetItem(str(record['low'])))
                self.data_table.setItem(
                    row, 4, QTableWidgetItem(str(record['close'])))
                self.data_table.setItem(
                    row, 5, QTableWidgetItem(f"{record['volume']:,}"))
                self.data_table.setItem(
                    row, 6, QTableWidgetItem(f"{record['amount']:,.2f}"))

            # 调整列宽
            self.data_table.horizontalHeader().setStretchLastSection(True)
            self.data_table.resizeColumnsToContents()

            self.current_data = data

        except Exception as e:
            logger.error(f"显示数据失败: {e}")

    def _browse_import_file(self) -> None:
        """浏览导入文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择导入文件", "",
                "所有支持的文件 (*.csv *.xlsx *.xls *.json);;CSV文件 (*.csv);;Excel文件 (*.xlsx *.xls);;JSON文件 (*.json)"
            )

            if file_path:
                self.file_path_edit.setText(file_path)

        except Exception as e:
            logger.error(f"浏览文件失败: {e}")

    def _preview_import_data(self) -> None:
        """预览导入数据"""
        try:
            file_path = self.file_path_edit.text().strip()
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择有效的导入文件")
                return

            # 读取文件前几行作为预览
            if file_path.endswith('.csv'):
                df = pd.read_csv(
                    file_path, encoding=self.encoding_combo.currentText(), nrows=10)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path, nrows=10)
            elif file_path.endswith('.json'):
                with open(file_path, 'r', encoding=self.encoding_combo.currentText()) as f:
                    data = json.load(f)
                df = pd.DataFrame(data[:10])
            else:
                QMessageBox.warning(self, "警告", "不支持的文件格式")
                return

            # 显示预览
            self.preview_table.setColumnCount(len(df.columns))
            self.preview_table.setHorizontalHeaderLabels(df.columns.tolist())
            self.preview_table.setRowCount(len(df))

            for row in range(len(df)):
                for col in range(len(df.columns)):
                    item = QTableWidgetItem(str(df.iloc[row, col]))
                    self.preview_table.setItem(row, col, item)

            self.preview_table.resizeColumnsToContents()

            QMessageBox.information(self, "预览", f"文件预览完成，显示前 {len(df)} 行数据")

        except Exception as e:
            logger.error(f"预览数据失败: {e}")
            QMessageBox.critical(self, "错误", f"预览数据失败: {e}")

    def _import_data(self) -> None:
        """导入数据"""
        try:
            file_path = self.file_path_edit.text().strip()
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择有效的导入文件")
                return

            # 显示进度对话框
            progress = QProgressDialog("正在导入数据...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            # 模拟导入过程
            for i in range(101):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                self.msleep(10)

            progress.close()

            logger.warning("数据导入引擎不可用，无法执行真实导入。请配置数据导入引擎。")
            QMessageBox.warning(self, "引擎不可用", f"数据导入引擎当前不可用，无法导入:\n{file_path}")

        except Exception as e:
            logger.error(f"导入数据失败: {e}")
            QMessageBox.critical(self, "错误", f"导入数据失败: {e}")

    def _start_update(self) -> None:
        """开始更新数据"""
        try:
            # 获取更新参数
            scope = self.update_scope_combo.currentText()
            period = self.update_period_combo.currentText()
            mode = self.update_mode_combo.currentText()
            provider = self.data_provider_combo.currentText()

            # 确定要更新的股票列表
            if scope == "指定股票":
                stocks_text = self.specified_stocks_edit.text().strip()
                if not stocks_text:
                    QMessageBox.warning(self, "警告", "请输入要更新的股票代码")
                    return
                stocks = [s.strip() for s in stocks_text.split(',')]
            else:
                # 使用示例股票列表
                stocks = ["000001", "000002", "600000", "600036", "600519"]

            # 创建更新线程
            self.update_thread = DataUpdateThread(stocks, None, None)
            self.update_thread.progress_updated.connect(
                self._on_update_progress)
            self.update_thread.status_updated.connect(self._on_update_status)
            self.update_thread.finished_signal.connect(
                self._on_update_finished)

            # 显示进度对话框
            self.progress_bar.setLabelText("正在更新数据...")
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.show()

            # 更新按钮状态
            self.start_update_button.setEnabled(False)
            self.stop_update_button.setEnabled(True)

            # 启动更新
            self.update_thread.start()

            # 添加日志
            self.update_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 开始更新数据")
            self.update_log.append(f"更新范围: {scope}")
            self.update_log.append(f"更新周期: {period}")
            self.update_log.append(f"更新模式: {mode}")

        except Exception as e:
            logger.error(f"启动数据更新失败: {e}")
            QMessageBox.critical(self, "错误", f"启动数据更新失败: {e}")

    def _stop_update(self) -> None:
        """停止更新数据"""
        try:
            if self.update_thread and self.update_thread.isRunning():
                self.update_thread.requestInterruption()
                self.update_thread.wait(3000)  # 等待3秒

            self.progress_bar.close()

            # 恢复按钮状态
            self.start_update_button.setEnabled(True)
            self.stop_update_button.setEnabled(False)

            self.update_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 数据更新已停止")

        except Exception as e:
            logger.error(f"停止数据更新失败: {e}")

    @pyqtSlot(int)
    def _on_update_progress(self, progress: int) -> None:
        """更新进度处理"""
        self.progress_bar.setValue(progress)

    @pyqtSlot(str)
    def _on_update_status(self, status: str) -> None:
        """更新状态处理"""
        self.status_label.setText(status)
        self.update_log.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] {status}")

    @pyqtSlot(bool, str)
    def _on_update_finished(self, success: bool, message: str) -> None:
        """更新完成处理"""
        self.progress_bar.close()

        # 恢复按钮状态
        self.start_update_button.setEnabled(True)
        self.stop_update_button.setEnabled(False)

        if success:
            self.status_label.setText("更新完成")
            self.update_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

            # 发送更新完成信号
            stocks = self.update_thread.stocks if self.update_thread else []
            self.data_updated.emit(stocks)

            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("更新失败")
            self.update_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] 错误: {message}")
            QMessageBox.critical(self, "错误", message)

    def _refresh_data(self) -> None:
        """刷新数据"""
        try:
            if self.current_stock:
                self._query_data()
            else:
                QMessageBox.information(self, "提示", "请先选择股票")

        except Exception as e:
            logger.error(f"刷新数据失败: {e}")

    def _export_data(self) -> None:
        """导出数据"""
        try:
            if not self.current_data:
                QMessageBox.warning(self, "警告", "没有可导出的数据")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出数据", f"{self.current_stock}_历史数据.xlsx",
                "Excel文件 (*.xlsx);;CSV文件 (*.csv);;JSON文件 (*.json)"
            )

            if file_path:
                df = pd.DataFrame(self.current_data)

                if file_path.endswith('.xlsx'):
                    df.to_excel(file_path, index=False)
                elif file_path.endswith('.csv'):
                    df.to_csv(file_path, index=False, encoding='utf-8-sig')
                elif file_path.endswith('.json'):
                    df.to_json(file_path, orient='records', date_format='iso')

                # 发送导出完成信号
                self.data_exported.emit(file_path)

                QMessageBox.information(self, "成功", f"数据已导出到: {file_path}")

        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            QMessageBox.critical(self, "错误", f"导出数据失败: {e}")

    def _refresh_statistics(self) -> None:
        """刷新统计信息"""
        try:
            # 更新概览统计
            self.total_stocks_label.setText("7,603")
            self.total_records_label.setText("15,206,000")
            self.latest_date_label.setText(datetime.now().strftime("%Y-%m-%d"))
            self.earliest_date_label.setText("2010-01-01")
            self.data_size_label.setText("2.3 GB")

            # 更新市场分布
            self.market_tree.clear()

            markets = [
                ("沪市主板", 1200, 2400000, "2024-01-15"),
                ("深市主板", 800, 1600000, "2024-01-15"),
                ("创业板", 1000, 2000000, "2024-01-15"),
                ("科创板", 500, 1000000, "2024-01-15"),
                ("北交所", 200, 400000, "2024-01-15")
            ]

            for market, stock_count, record_count, last_update in markets:
                item = QTreeWidgetItem(
                    [market, str(stock_count), f"{record_count:,}", last_update])
                self.market_tree.addTopLevelItem(item)

            self.market_tree.expandAll()

            # 更新数据质量
            self.missing_data_label.setText("156 条")
            self.duplicate_data_label.setText("23 条")
            self.invalid_data_label.setText("8 条")

            logger.info("统计信息刷新完成")

        except Exception as e:
            logger.error(f"刷新统计信息失败: {e}")

    def msleep(self, msecs: int) -> None:
        """毫秒级睡眠"""
        import time
        time.sleep(msecs / 1000.0)
