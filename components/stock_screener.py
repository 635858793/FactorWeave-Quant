from loguru import logger
"""
选股策略组件

提供多种选股策略，包括技术指标筛选、基本面筛选、资金流向筛选等
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Union
from core.services.unified_data_manager import UnifiedDataManager
from core.stock_screener import StockScreener
from loguru import logger
import traceback
import time
import json
import os

from datetime import datetime
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.figure import Figure
import json
import traceback
from core.indicator_adapter import calc_ma, calc_macd, calc_rsi, calc_kdj, calc_boll, calc_atr, calc_obv, calc_cci, calc_wr, calc_talib_indicator, get_talib_indicator_list
from core.indicator_service import get_indicator_categories, get_all_indicators_metadata, get_indicator_metadata
from gui.ui_components import BaseAnalysisPanel, AnalysisToolsPanel
from concurrent.futures import ThreadPoolExecutor
import os


class PagedTableWidget(QWidget):
    def __init__(self, columns, page_size=100, parent=None):
        super().__init__(parent)
        self.page_size = page_size
        self.current_page = 1
        self.data = []
        self.columns = columns
        self.layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.layout.addWidget(self.table)
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("上一页")
        self.next_btn = QPushButton("下一页")
        self.page_label = QLabel()
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.next_btn)
        self.layout.addLayout(nav_layout)
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)

    def set_data(self, data):
        self.data = data
        self.current_page = 1
        self.update_page()

    def update_page(self):
        start = (self.current_page - 1) * self.page_size
        end = start + self.page_size
        page_data = self.data[start:end]
        self.table.setRowCount(len(page_data))
        for i, row in enumerate(page_data):
            for j, value in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        total_pages = max(
            1, (len(self.data) + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"第 {self.current_page} / {total_pages} 页")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)

    def next_page(self):
        total_pages = max(
            1, (len(self.data) + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.update_page()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.update_page()


class ScreeningWorker(QThread):
    """选股工作线程（多线程筛选支持）"""
    finished = pyqtSignal(pd.DataFrame)
    error = pyqtSignal(str)

    def __init__(self, screener, params):
        super().__init__()
        self.screener = screener
        self.params = params

    def run(self):
        try:
            results = self.screener.screen_stocks(
                strategy_type=self.params['strategy_type'],
                template=self.params['template'],
                technical_params=self.params['technical'],
                fundamental_params=self.params['fundamental'],
                capital_params=self.params['capital']
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class StockScreenerWidget(BaseAnalysisPanel):
    """选股策略组件，继承统一分析面板基类"""

    def __init__(self, parent=None, data_manager=None):
        """初始化选股策略组件

        Args:
            parent: 父窗口
            data_manager: 数据管理器实例
            # log_manager: 已迁移到Loguru日志系统
        """
        super().__init__(parent)
        self.data_manager = data_manager
        # log_manager已迁移到Loguru
        # 先初始化所有依赖属性
        self.template_manager = TemplateManager(
            template_dir="templates/stock_screener")
        self.conditions = []
        self.templates = {}
        # 再初始化UI和加载模板
        self.init_ui()
        self.load_templates()
        # 主动拉取一次股票列表并刷新结果表，确保初始有数据展示
        try:
            from core.utils.data_standardizer import DataStandardizer
            data_standardizer = DataStandardizer()
            stock_list = data_standardizer.get_stock_list()
            if not stock_list.empty:
                # 只显示前100条
                data = stock_list.head(100).values.tolist()
                self.paged_table.set_data(data)
        except Exception as e:
            logger.warning(f"初始化拉取股票列表失败: {str(e)}")

    def init_ui(self):
        """Initialize UI components"""
        try:
            # Create main layout
            self.main_layout = QVBoxLayout()
            if self.layout() is None:
                self.setLayout(self.main_layout)
            # Create strategy selection group
            strategy_group = QGroupBox("选股策略")
            strategy_layout = QVBoxLayout(strategy_group)

            # Add strategy type selector
            self.strategy_type = QComboBox()
            self.strategy_type.addItems([
                "技术指标选股",
                "基本面选股",
                "资金面选股",
                "综合选股"
            ])
            self.strategy_type.currentTextChanged.connect(
                self.on_strategy_changed)
            strategy_layout.addWidget(self.strategy_type)

            # Add template management
            template_layout = QHBoxLayout()

            # Add template selector
            self.template_combo = QComboBox()
            self.template_combo.currentTextChanged.connect(
                self.on_template_changed)
            template_layout.addWidget(self.template_combo)

            # Add template buttons
            load_button = QPushButton("加载模板")
            load_button.clicked.connect(self.load_template)
            template_layout.addWidget(load_button)

            save_button = QPushButton("保存模板")
            save_button.clicked.connect(self.save_template)
            template_layout.addWidget(save_button)

            delete_button = QPushButton("删除模板")
            delete_button.clicked.connect(self.delete_template)
            template_layout.addWidget(delete_button)

            strategy_layout.addLayout(template_layout)

            # Add to main layout
            self.main_layout.addWidget(strategy_group)

            # Create condition settings group
            self.condition_group = QGroupBox("选股条件")
            self.condition_layout = QVBoxLayout(self.condition_group)
            self.main_layout.addWidget(self.condition_group)

            # Create result display group
            self.result_group = QGroupBox("选股结果")
            result_layout = QVBoxLayout(self.result_group)

            # Add result table first
            self.paged_table = PagedTableWidget(
                columns=["股票代码", "股票名称", "最新价", "涨跌幅", "筛选得分"], page_size=100)
            self.paged_table.table.setToolTip("分页显示大数据量选股结果，支持排序和筛选")
            result_layout.addWidget(self.paged_table)

            # Add sorting functions after result table is created
            self.add_sorting_functions()

            # Add filter functions
            self.add_filter_functions()

            # Add action buttons
            buttons_layout = QHBoxLayout()

            screen_button = QPushButton("开始选股")
            screen_button.clicked.connect(self.start_screening)
            screen_button.setToolTip("点击开始选股")
            buttons_layout.addWidget(screen_button)
            self.run_button = screen_button  # 记录引用，便于多线程控制

            export_button = QPushButton("导出结果")
            export_button.clicked.connect(self.export_results)
            export_button.setToolTip("导出当前筛选结果到Excel或CSV文件")
            buttons_layout.addWidget(export_button)

            save_button = QPushButton("保存策略")
            save_button.clicked.connect(self.save_strategy)
            buttons_layout.addWidget(save_button)

            # 增加模板管理按钮
            manage_button = QPushButton("模板管理")
            manage_button.clicked.connect(self.show_template_manager_dialog)
            buttons_layout.addWidget(manage_button)

            batch_export_button = QPushButton("批量导出分析结果")
            batch_export_button.clicked.connect(self.export_batch_results)
            buttons_layout.addWidget(batch_export_button)

            result_layout.addLayout(buttons_layout)
            self.main_layout.addWidget(self.result_group)

            # Initialize condition settings
            self.on_strategy_changed(self.strategy_type.currentText())

            # Load templates
            self.load_templates()

            # Add chart functions
            self.add_chart_functions()

            # 新增：连接条件控件信号
            self._connect_condition_signals()

            # 批量股票代码输入区
            self.batch_input = QLineEdit()
            self.batch_input.setPlaceholderText("输入多个股票代码，用逗号分隔，或点击导入文件")
            self.main_layout.addWidget(self.batch_input)
            import_button = QPushButton("导入股票代码文件")
            import_button.clicked.connect(self.import_stock_codes)
            self.main_layout.addWidget(import_button)
            # 多策略对比入口
            self.strategy_checkboxes = []
            for strategy in ["双均线", "MACD", "KDJ", "RSI", "BOLL"]:
                cb = QCheckBox(strategy)
                self.main_layout.addWidget(cb)
                self.strategy_checkboxes.append(cb)
            compare_button = QPushButton("多策略对比分析")
            compare_button.clicked.connect(self.compare_strategies)
            self.main_layout.addWidget(compare_button)
            # 结果展示表格
            self.compare_table = QTableWidget()
            self.compare_table.setColumnCount(3)
            self.compare_table.setHorizontalHeaderLabels(
                ["股票代码", "策略", "分析结果"])
            self.compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.main_layout.addWidget(self.compare_table)

            # 新增多因子选股Tab
            self.tab_widget = QTabWidget()
            self.tab_widget.addTab(QWidget(), "常规选股")
            self.multi_factor_tab = QWidget()
            mf_layout = QVBoxLayout(self.multi_factor_tab)
            # 特征选择方式
            self.feature_method_combo = QComboBox()
            self.feature_method_combo.addItems(["PCA降维", "增强型特征选择", "自定义特征"])
            mf_layout.addWidget(QLabel("特征选择方法："))
            mf_layout.addWidget(self.feature_method_combo)
            # 因子权重设置（简化为表格）
            self.factor_table = QTableWidget(0, 2)
            self.factor_table.setHorizontalHeaderLabels(["特征/因子", "权重"])
            mf_layout.addWidget(QLabel("因子权重设置："))
            mf_layout.addWidget(self.factor_table)
            # 一键多因子选股按钮
            self.run_multi_factor_btn = QPushButton("一键多因子选股")
            mf_layout.addWidget(self.run_multi_factor_btn)
            # 结果表格
            self.multi_factor_result = QTableWidget()
            self.multi_factor_result.setColumnCount(8)
            self.multi_factor_result.setHorizontalHeaderLabels(
                ["股票代码", "名称", "行业", "最新价", "涨跌幅", "PE", "PB", "综合得分"])
            mf_layout.addWidget(self.multi_factor_result)
            # 导出按钮
            self.export_multi_factor_btn = QPushButton("导出选股结果")
            mf_layout.addWidget(self.export_multi_factor_btn)
            self.tab_widget.addTab(self.multi_factor_tab, "多因子选股")
            self.main_layout.addWidget(self.tab_widget)
            # 信号绑定
            self.run_multi_factor_btn.clicked.connect(
                self.run_multi_factor_selection)
            self.export_multi_factor_btn.clicked.connect(
                self.export_multi_factor_results)

        except Exception as e:
            logger.error(f"初始化UI失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def on_strategy_changed(self, strategy_type: str):
        """Handle strategy type change

        Args:
            strategy_type: Selected strategy type
        """
        try:
            # Clear condition layout
            while self.condition_layout.count():
                item = self.condition_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Add condition settings based on strategy type
            if strategy_type == "技术指标选股":
                self.add_technical_conditions()
            elif strategy_type == "基本面选股":
                self.add_fundamental_conditions()
            elif strategy_type == "资金面选股":
                self.add_capital_conditions()
            else:
                self.add_comprehensive_conditions()

        except Exception as e:
            logger.error(f"更新策略设置失败: {str(e)}")

    def add_technical_conditions(self):
        """Add technical indicator conditions"""
        try:
            # Add MA condition
            ma_layout = QHBoxLayout()
            ma_layout.addWidget(QLabel("均线条件:"))

            self.ma_type = QComboBox()
            self.ma_type.addItems(["MA5", "MA10", "MA20", "MA60"])
            ma_layout.addWidget(self.ma_type)

            self.ma_condition = QComboBox()
            self.ma_condition.addItems(["上穿", "下穿", "金叉", "死叉"])
            ma_layout.addWidget(self.ma_condition)

            self.condition_layout.addLayout(ma_layout)

            # Add MACD condition
            macd_layout = QHBoxLayout()
            macd_layout.addWidget(QLabel("MACD条件:"))

            self.macd_condition = QComboBox()
            self.macd_condition.addItems(["金叉", "死叉", "红柱", "绿柱"])
            macd_layout.addWidget(self.macd_condition)

            self.condition_layout.addLayout(macd_layout)

            # Add RSI condition
            rsi_layout = QHBoxLayout()
            rsi_layout.addWidget(QLabel("RSI条件:"))

            self.rsi_period = QSpinBox()
            self.rsi_period.setRange(5, 30)
            self.rsi_period.setValue(14)
            rsi_layout.addWidget(self.rsi_period)

            self.rsi_condition = QComboBox()
            self.rsi_condition.addItems(["超买", "超卖", "背离"])
            rsi_layout.addWidget(self.rsi_condition)

            self.condition_layout.addLayout(rsi_layout)

        except Exception as e:
            logger.error(f"添加技术指标条件失败: {str(e)}")

    def add_fundamental_conditions(self):
        """Add fundamental conditions"""
        try:
            # Add PE condition
            pe_layout = QHBoxLayout()
            pe_layout.addWidget(QLabel("市盈率:"))

            self.pe_min = QDoubleSpinBox()
            self.pe_min.setDecimals(2)
            self.pe_min.setRange(0.0, 100.0)
            self.pe_min.setValue(0.0)
            pe_layout.addWidget(self.pe_min)

            pe_layout.addWidget(QLabel("至"))

            self.pe_max = QDoubleSpinBox()
            self.pe_max.setDecimals(2)
            self.pe_max.setRange(0.0, 100.0)
            self.pe_max.setValue(100.0)
            pe_layout.addWidget(self.pe_max)

            self.condition_layout.addLayout(pe_layout)

            # Add PB condition
            pb_layout = QHBoxLayout()
            pb_layout.addWidget(QLabel("市净率:"))

            self.pb_min = QDoubleSpinBox()
            self.pb_min.setDecimals(2)
            self.pb_min.setRange(0.0, 10.0)
            self.pb_min.setValue(0.0)
            pb_layout.addWidget(self.pb_min)

            pb_layout.addWidget(QLabel("至"))

            self.pb_max = QDoubleSpinBox()
            self.pb_max.setDecimals(2)
            self.pb_max.setRange(0.0, 10.0)
            self.pb_max.setValue(10.0)
            pb_layout.addWidget(self.pb_max)

            self.condition_layout.addLayout(pb_layout)

            # Add ROE condition
            roe_layout = QHBoxLayout()
            roe_layout.addWidget(QLabel("净资产收益率:"))

            self.roe_min = QDoubleSpinBox()
            self.roe_min.setDecimals(2)
            self.roe_min.setRange(0.0, 100.0)
            self.roe_min.setValue(10.0)
            self.roe_min.setSuffix("%")
            roe_layout.addWidget(self.roe_min)

            self.condition_layout.addLayout(roe_layout)

        except Exception as e:
            logger.error(f"添加基本面条件失败: {str(e)}")

    def add_capital_conditions(self):
        """Add capital flow conditions"""
        try:
            # Add main net inflow condition
            inflow_layout = QHBoxLayout()
            inflow_layout.addWidget(QLabel("主力净流入:"))

            self.inflow_min = QDoubleSpinBox()
            self.inflow_min.setDecimals(2)
            self.inflow_min.setRange(0.0, 1000000.0)
            self.inflow_min.setValue(100000.0)
            self.inflow_min.setSuffix("万元")
            inflow_layout.addWidget(self.inflow_min)

            self.condition_layout.addLayout(inflow_layout)

            # Add volume condition
            volume_layout = QHBoxLayout()
            volume_layout.addWidget(QLabel("成交量:"))

            self.volume_min = QDoubleSpinBox()
            self.volume_min.setDecimals(2)
            self.volume_min.setRange(0.0, 1000000.0)
            self.volume_min.setValue(100000.0)
            self.volume_min.setSuffix("手")
            volume_layout.addWidget(self.volume_min)

            self.condition_layout.addLayout(volume_layout)

        except Exception as e:
            logger.error(f"添加资金面条件失败: {str(e)}")

    def add_comprehensive_conditions(self):
        """Add comprehensive conditions"""
        try:
            # Add technical weight
            tech_layout = QHBoxLayout()
            tech_layout.addWidget(QLabel("技术指标权重:"))

            self.tech_weight = QDoubleSpinBox()
            self.tech_weight.setDecimals(2)
            self.tech_weight.setRange(0.0, 1.0)
            self.tech_weight.setValue(0.4)
            self.tech_weight.setSingleStep(0.1)
            tech_layout.addWidget(self.tech_weight)

            self.condition_layout.addLayout(tech_layout)

            # Add fundamental weight
            fund_layout = QHBoxLayout()
            fund_layout.addWidget(QLabel("基本面权重:"))

            self.fund_weight = QDoubleSpinBox()
            self.fund_weight.setDecimals(2)
            self.fund_weight.setRange(0.0, 1.0)
            self.fund_weight.setValue(0.3)
            self.fund_weight.setSingleStep(0.1)
            fund_layout.addWidget(self.fund_weight)

            self.condition_layout.addLayout(fund_layout)

            # Add capital weight
            cap_layout = QHBoxLayout()
            cap_layout.addWidget(QLabel("资金面权重:"))

            self.cap_weight = QDoubleSpinBox()
            self.cap_weight.setDecimals(2)
            self.cap_weight.setRange(0.0, 1.0)
            self.cap_weight.setValue(0.3)
            self.cap_weight.setSingleStep(0.1)
            cap_layout.addWidget(self.cap_weight)

            self.condition_layout.addLayout(cap_layout)

        except Exception as e:
            logger.error(f"添加综合条件失败: {str(e)}")

    def start_screening(self):
        """多线程启动筛选"""
        try:
            valid, msg = self.validate_params()
            if not valid:
                QMessageBox.warning(self, "参数错误", f"请修正以下参数后再筛选：\n{msg}")
                return
            params = {
                'strategy_type': self.strategy_type.currentText(),
                'template': self.template_combo.currentText(),
                'technical': self.get_technical_params(),
                'fundamental': self.get_fundamental_params(),
                'capital': self.get_capital_params()
            }
            self.screening_worker = ScreeningWorker(self.screener, params)
            self.screening_worker.finished.connect(self.on_screening_finished)
            self.screening_worker.error.connect(self.on_screening_error)
            self.screening_worker.start()
            # 禁用按钮防止重复点击
            self.run_button.setEnabled(False)
        except Exception as e:
            logger.error(f"启动筛选失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"启动筛选失败: {str(e)}")

    def on_screening_finished(self, results):
        """筛选完成回调"""
        self.update_result_table(results)
        self.run_button.setEnabled(True)
        QMessageBox.information(self, "完成", f"筛选完成，共{len(results)}条记录")

    def on_screening_error(self, error):
        """筛选错误回调"""
        self.run_button.setEnabled(True)
        logger.error(f"筛选失败: {error}")
        QMessageBox.critical(self, "错误", f"筛选失败: {error}")

    def get_technical_params(self):
        # TODO: 从UI获取技术指标参数
        return {}

    def get_fundamental_params(self):
        # TODO: 从UI获取基本面参数
        return {}

    def get_capital_params(self):
        # TODO: 从UI获取资金流向参数
        return {}

    def on_stock_selected(self):
        """Handle stock selection in result table"""
        try:
            # Get selected row
            selected_items = self.paged_table.table.selectedIndexes()
            if not selected_items:
                return

            # Get stock code
            stock_code = selected_items[0].data()

            # Emit signal to parent
            if hasattr(self.parent(), 'on_stock_selected'):
                self.parent().on_stock_selected(stock_code)

        except Exception as e:
            logger.error(f"处理股票选择失败: {str(e)}")

    def export_results(self):
        """导出选股结果"""
        try:
            # 获取当前数据
            data = []
            for row in range(self.paged_table.table.rowCount()):
                data.append({
                    'code': self.paged_table.table.item(row, 0).text(),
                    'name': self.paged_table.table.item(row, 1).text(),
                    'close': float(self.paged_table.table.item(row, 2).text()),
                    'change_percent': float(self.paged_table.table.item(row, 3).text().rstrip('%')),
                    'score': float(self.paged_table.table.item(row, 4).text())
                })

            if not data:
                QMessageBox.warning(self, "警告", "没有可导出的数据")
                return

            # 转换为DataFrame
            df = pd.DataFrame(data)

            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出选股结果",
                f"选股结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "Excel Files (*.xlsx);;CSV Files (*.csv)"
            )

            if file_path:
                # 根据文件类型保存
                if file_path.endswith('.xlsx'):
                    df.to_excel(file_path, index=False)
                else:
                    df.to_csv(file_path, index=False)

                logger.info(f"选股结果已导出到: {file_path}")
                QMessageBox.information(self, "成功", "选股结果导出成功")

        except Exception as e:
            logger.error(f"导出选股结果失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"导出选股结果失败: {str(e)}")

    def save_strategy(self):
        """保存当前选股策略"""
        try:
            strategy_type = self.strategy_type.currentText()
            conditions = self.get_current_conditions()
            name, ok = QInputDialog.getText(
                self, "保存模板", "模板名称:", text=f"{strategy_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            if ok and name:
                self.template_manager.save_template(name, conditions)
                QMessageBox.information(self, "成功", "模板保存成功")
        except Exception as e:
            logger.error(f"保存模板失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存模板失败: {str(e)}")

    def load_strategy(self):
        """加载选股策略"""
        try:
            # 获取文件路径
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "加载选股策略",
                "",
                "JSON Files (*.json)"
            )

            if file_path:
                # 读取策略数据
                with open(file_path, 'r', encoding='utf-8') as f:
                    strategy_data = json.load(f)

                # 更新策略类型
                index = self.strategy_type.findText(
                    strategy_data['strategy_type'])
                if index >= 0:
                    self.strategy_type.setCurrentIndex(index)

                # 更新条件设置
                self.update_conditions(strategy_data['conditions'])

                logger.info(f"已加载选股策略: {file_path}")

                # 显示成功对话框
                dialog = QMessageBox(self)
                dialog.setWindowTitle("成功")
                dialog.setIcon(QMessageBox.Information)
                dialog.setText("选股策略加载成功")
                dialog.setStandardButtons(QMessageBox.Ok)

                # 显示对话框并居中
                dialog.show()
                self.center_dialog(dialog, self)
                dialog.exec_()

        except Exception as e:
            logger.error(f"加载选股策略失败: {str(e)}")

            # 显示错误对话框
            dialog = QMessageBox(self)
            dialog.setWindowTitle("错误")
            dialog.setIcon(QMessageBox.Critical)
            dialog.setText(f"加载选股策略失败: {str(e)}")
            dialog.setStandardButtons(QMessageBox.Ok)

            # 显示对话框并居中
            dialog.show()
            self.center_dialog(dialog, self)
            dialog.exec_()

    def get_current_conditions(self) -> dict:
        """获取当前UI中设置的选股条件

        Returns:
            dict: 选股条件字典
        """
        try:
            strategy_type = self.strategy_type.currentText()
            conditions = {}

            if strategy_type == "技术指标选股":
                conditions = {
                    "ma_type": self.ma_type.currentText(),
                    "ma_condition": self.ma_condition.currentText(),
                    "macd_condition": self.macd_condition.currentText(),
                    "rsi_period": self.rsi_period.value(),
                    "rsi_condition": self.rsi_condition.currentText()
                }
            elif strategy_type == "基本面选股":
                conditions = {
                    "pe_min": self.pe_min.value(),
                    "pe_max": self.pe_max.value(),
                    "pb_min": self.pb_min.value(),
                    "pb_max": self.pb_max.value(),
                    "roe_min": self.roe_min.value()
                }
            elif strategy_type == "资金面选股":
                conditions = {
                    "inflow_min": self.inflow_min.value(),
                    "volume_min": self.volume_min.value()
                }
            else:  # 综合选股
                conditions = {
                    "tech_weight": self.tech_weight.value(),
                    "fund_weight": self.fund_weight.value(),
                    "cap_weight": self.cap_weight.value()
                }

            return conditions

        except Exception as e:
            logger.error(f"获取选股条件失败: {str(e)}")
            return {}

    def load_templates(self):
        """加载策略模板列表"""
        try:
            self.template_combo.clear()
            for name in self.template_manager.list_templates():
                self.template_combo.addItem(name)
        except Exception as e:
            logger.error(f"加载模板列表失败: {str(e)}")

    def on_template_changed(self, template_name: str):
        """处理模板选择变更

        Args:
            template_name: 选中的模板名称
        """
        try:
            if not template_name:
                return
            params = self.template_manager.load_template(template_name)
            self.update_conditions(params)
        except Exception as e:
            logger.error(f"加载模板失败: {str(e)}")

    def update_conditions(self, conditions: dict):
        """更新选股条件设置

        Args:
            conditions: 选股条件字典
        """
        try:
            strategy_type = self.strategy_type.currentText()

            if strategy_type == "技术指标选股":
                # 更新技术指标条件
                if 'ma_type' in conditions:
                    index = self.ma_type.findText(conditions['ma_type'])
                    if index >= 0:
                        self.ma_type.setCurrentIndex(index)

                if 'ma_condition' in conditions:
                    index = self.ma_condition.findText(
                        conditions['ma_condition'])
                    if index >= 0:
                        self.ma_condition.setCurrentIndex(index)

                if 'macd_condition' in conditions:
                    index = self.macd_condition.findText(
                        conditions['macd_condition'])
                    if index >= 0:
                        self.macd_condition.setCurrentIndex(index)

                if 'rsi_period' in conditions:
                    self.rsi_period.setValue(conditions['rsi_period'])

                if 'rsi_condition' in conditions:
                    index = self.rsi_condition.findText(
                        conditions['rsi_condition'])
                    if index >= 0:
                        self.rsi_condition.setCurrentIndex(index)

            elif strategy_type == "基本面选股":
                # 更新基本面条件
                if 'pe_min' in conditions:
                    self.pe_min.setValue(conditions['pe_min'])

                if 'pe_max' in conditions:
                    self.pe_max.setValue(conditions['pe_max'])

                if 'pb_min' in conditions:
                    self.pb_min.setValue(conditions['pb_min'])

                if 'pb_max' in conditions:
                    self.pb_max.setValue(conditions['pb_max'])

                if 'roe_min' in conditions:
                    self.roe_min.setValue(conditions['roe_min'])

            elif strategy_type == "资金面选股":
                # 更新资金面条件
                if 'inflow_min' in conditions:
                    self.inflow_min.setValue(conditions['inflow_min'])

                if 'volume_min' in conditions:
                    self.volume_min.setValue(conditions['volume_min'])

            else:  # 综合选股
                # 更新综合条件
                if 'tech_weight' in conditions:
                    self.tech_weight.setValue(conditions['tech_weight'])

                if 'fund_weight' in conditions:
                    self.fund_weight.setValue(conditions['fund_weight'])

                if 'cap_weight' in conditions:
                    self.cap_weight.setValue(conditions['cap_weight'])

        except Exception as e:
            logger.error(f"更新选股条件失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"更新选股条件失败: {str(e)}")

    def save_template(self):
        """保存当前策略为模板"""
        try:
            # 获取模板名称
            template_name, ok = QInputDialog.getText(
                self,
                "保存模板",
                "请输入模板名称:",
                text=f"{self.strategy_type.currentText()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            if ok and template_name:
                # 获取当前策略设置
                strategy_type = self.strategy_type.currentText()
                conditions = self.get_current_conditions()

                # 保存模板
                self.template_manager.save_template(template_name, conditions)

                # 重新加载模板列表
                self.load_templates()

        except Exception as e:
            logger.error(f"保存模板失败: {str(e)}")

    def delete_template(self):
        """删除选中的模板"""
        try:
            template_name = self.template_combo.currentText()
            if not template_name:
                return

            # 确认删除
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除模板 '{template_name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 删除模板
                self.template_manager.delete_templates([template_name])

                # 重新加载模板列表
                self.load_templates()

        except Exception as e:
            logger.error(f"删除模板失败: {str(e)}")

    def add_sorting_functions(self):
        """添加排序功能"""
        try:
            # 设置表格可排序
            self.paged_table.table.setSortingEnabled(True)

            # 添加排序按钮
            sort_layout = QHBoxLayout()

            # 添加排序方式选择
            self.sort_combo = QComboBox()
            self.sort_combo.addItems([
                "按得分排序",
                "按涨跌幅排序",
                "按最新价排序"
            ])
            self.sort_combo.currentTextChanged.connect(self.on_sort_changed)
            sort_layout.addWidget(self.sort_combo)

            # 添加排序方向选择
            self.sort_direction = QComboBox()
            self.sort_direction.addItems([
                "降序",
                "升序"
            ])
            self.sort_direction.currentTextChanged.connect(
                self.on_sort_changed)
            sort_layout.addWidget(self.sort_direction)

            # 添加到结果组
            self.result_group.layout().insertLayout(0, sort_layout)

        except Exception as e:
            logger.error(f"添加排序功能失败: {str(e)}")

    def on_sort_changed(self):
        """处理排序变更"""
        try:
            # 获取排序方式和方向
            sort_by = self.sort_combo.currentText()
            ascending = self.sort_direction.currentText() == "升序"

            # 获取当前数据
            data = []
            for row in range(self.paged_table.table.rowCount()):
                data.append({
                    'code': self.paged_table.table.item(row, 0).text(),
                    'name': self.paged_table.table.item(row, 1).text(),
                    'close': float(self.paged_table.table.item(row, 2).text()),
                    'change_percent': float(self.paged_table.table.item(row, 3).text().rstrip('%')),
                    'score': float(self.paged_table.table.item(row, 4).text())
                })

            # 转换为DataFrame并排序
            df = pd.DataFrame(data)
            if sort_by == "按得分排序":
                df = df.sort_values('score', ascending=ascending)
            elif sort_by == "按涨跌幅排序":
                df = df.sort_values('change_percent', ascending=ascending)
            else:  # 按最新价排序
                df = df.sort_values('close', ascending=ascending)

            # 更新表格
            self.update_result_table(df)

        except Exception as e:
            logger.error(f"处理排序变更失败: {str(e)}")

    def add_filter_functions(self):
        """添加筛选功能"""
        try:
            # 添加筛选布局
            filter_layout = QHBoxLayout()

            # 添加筛选条件选择
            self.filter_combo = QComboBox()
            self.filter_combo.addItems([
                "全部",
                "得分>0.8",
                "涨跌幅>5%",
                "最新价<20"
            ])
            self.filter_combo.currentTextChanged.connect(
                self.on_filter_changed)
            filter_layout.addWidget(self.filter_combo)

            # 添加到结果组
            self.result_group.layout().insertLayout(1, filter_layout)

        except Exception as e:
            logger.error(f"添加筛选功能失败: {str(e)}")

    def on_filter_changed(self):
        """处理筛选变更"""
        try:
            # 获取筛选条件
            filter_condition = self.filter_combo.currentText()

            # 获取当前数据
            data = []
            for row in range(self.paged_table.table.rowCount()):
                data.append({
                    'code': self.paged_table.table.item(row, 0).text(),
                    'name': self.paged_table.table.item(row, 1).text(),
                    'close': float(self.paged_table.table.item(row, 2).text()),
                    'change_percent': float(self.paged_table.table.item(row, 3).text().rstrip('%')),
                    'score': float(self.paged_table.table.item(row, 4).text())
                })

            # 转换为DataFrame并筛选
            df = pd.DataFrame(data)
            if filter_condition == "得分>0.8":
                df = df[df['score'] > 0.8]
            elif filter_condition == "涨跌幅>5%":
                df = df[df['change_percent'] > 5]
            elif filter_condition == "最新价<20":
                df = df[df['close'] < 20]

            # 更新表格
            self.update_result_table(df)

        except Exception as e:
            logger.error(f"处理筛选变更失败: {str(e)}")

    def add_chart_functions(self):
        """添加图表显示功能"""
        try:
            # 创建图表组
            chart_group = QGroupBox("选股结果图表")
            chart_layout = QVBoxLayout(chart_group)

            # 创建图表类型选择
            chart_type_layout = QHBoxLayout()
            chart_type_layout.addWidget(QLabel("图表类型:"))

            self.chart_type = QComboBox()
            self.chart_type.addItems([
                "得分分布图",
                "涨跌幅分布图",
                "价格分布图"
            ])
            self.chart_type.currentTextChanged.connect(
                self.update_distribution_chart)
            chart_type_layout.addWidget(self.chart_type)

            chart_layout.addLayout(chart_type_layout)

            # 创建图表画布
            self.figure = Figure(figsize=(8, 4))
            self.canvas = FigureCanvas(self.figure)
            chart_layout.addWidget(self.canvas)

            # 添加到结果组
            self.result_group.layout().addWidget(chart_group)

            # 初始化图表
            self.update_distribution_chart()

        except Exception as e:
            logger.error(f"添加图表功能失败: {str(e)}")

    def update_distribution_chart(self):
        """更新分布图/直方图，仅用于选股器等非K线业务"""
        try:
            # 清空图表
            self.figure.clear()
            # 获取当前数据
            data = []
            for row in range(self.paged_table.table.rowCount()):
                data.append({
                    'code': self.paged_table.table.item(row, 0).text(),
                    'name': self.paged_table.table.item(row, 1).text(),
                    'close': float(self.paged_table.table.item(row, 2).text()),
                    'change_percent': float(self.paged_table.table.item(row, 3).text().rstrip('%')),
                    'score': float(self.paged_table.table.item(row, 4).text())
                })
            if not data:
                return
            # 转换为DataFrame
            df = pd.DataFrame(data)
            # 创建子图
            ax = self.figure.add_subplot(111)
            # 根据图表类型绘制
            chart_type = self.chart_type.currentText()
            if chart_type == "得分分布图":
                ax.hist(df['score'], bins=20, alpha=0.7)
                ax.set_xlabel('筛选得分')
                ax.set_ylabel('股票数量')
                ax.set_title('筛选得分分布')
                # 顶部显示最大、最小、均值、标准差
                score_max = df['score'].max()
                score_min = df['score'].min()
                score_mean = df['score'].mean()
                score_std = df['score'].std()
                ax.text(0.5, 0.95, f"最大: {score_max:.3f}  最小: {score_min:.3f}  均值: {score_mean:.3f}  标准差: {score_std:.3f}",
                        transform=ax.transAxes, ha='center', va='bottom', fontsize=11, color='#1976d2')
            elif chart_type == "涨跌幅分布图":
                ax.hist(df['change_percent'], bins=20, alpha=0.7)
                ax.set_xlabel('涨跌幅(%)')
                ax.set_ylabel('股票数量')
                ax.set_title('涨跌幅分布')
                # 顶部显示最大、最小、均值、标准差
                chg_max = df['change_percent'].max()
                chg_min = df['change_percent'].min()
                chg_mean = df['change_percent'].mean()
                chg_std = df['change_percent'].std()
                ax.text(0.5, 0.95, f"最大: {chg_max:.3f}%  最小: {chg_min:.3f}%  均值: {chg_mean:.3f}%  标准差: {chg_std:.3f}%",
                        transform=ax.transAxes, ha='center', va='bottom', fontsize=11, color='#e53935')
            else:  # 价格分布图
                ax.hist(df['close'], bins=20, alpha=0.7)
                ax.set_xlabel('最新价')
                ax.set_ylabel('股票数量')
                ax.set_title('价格分布')
                # 顶部显示最大、最小、均值、标准差
                close_max = df['close'].max()
                close_min = df['close'].min()
                close_mean = df['close'].mean()
                close_std = df['close'].std()
                ax.text(0.5, 0.95, f"最大: {close_max:.3f}  最小: {close_min:.3f}  均值: {close_mean:.3f}  标准差: {close_std:.3f}",
                        transform=ax.transAxes, ha='center', va='bottom', fontsize=11, color='#43a047')
            # 调整布局
            self.figure.tight_layout()
            # 更新画布
            self.canvas.draw()
        except Exception as e:
            logger.error(f"更新分布图失败: {str(e)}")

    def screen_stocks(self):
        start_time = time.time()
        logger.info("[StockScreenerWidget.screen_stocks] 开始")
        try:
            if not self.conditions:
                QMessageBox.warning(self, "警告", "请添加筛选条件")
                return

            # 创建进度对话框
            progress = QProgressDialog("正在筛选股票...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("股票筛选")
            progress.setAutoClose(True)
            progress.setAutoReset(True)

            # 获取所有股票列表
            from core.utils.data_standardizer import DataStandardizer
            data_standardizer = DataStandardizer()
            stock_list = data_standardizer.get_stock_list()
            total_stocks = len(stock_list)
            progress.setMaximum(total_stocks)

            # 初始化结果列表
            results = []

            # 遍历股票进行筛选
            for i, stock in enumerate(stock_list):
                if progress.wasCanceled():
                    break
                # 更新进度，保证范围安全
                progress.setValue(max(0, min(i, total_stocks)))
                progress.setLabelText(
                    f"正在筛选股票: {stock['code']} - {stock['name']}")
                # 获取股票数据
                stock_data = data_standardizer.get_stock_data(stock['code'])
                if stock_data.empty:
                    continue
                # 检查是否满足所有条件
                match_score = 0
                total_conditions = len(self.conditions)
                for condition in self.conditions:
                    condition_type = condition['type']
                    condition_params = condition['params']
                    if condition_type == "技术指标":
                        if self.check_technical_condition(stock_data, condition_params):
                            match_score += 1
                    elif condition_type == "基本面":
                        if self.check_fundamental_condition(stock, condition_params):
                            match_score += 1
                    elif condition_type == "资金流向":
                        if self.check_capital_condition(stock_data, condition_params):
                            match_score += 1
                    elif condition_type == "消息面":
                        if self.check_news_condition(stock['code'], condition_params):
                            match_score += 1
                match_ratio = match_score / total_conditions
                if match_ratio > 0:
                    results.append({
                        'code': stock['code'],
                        'name': stock['name'],
                        'match_ratio': match_ratio
                    })
            # 更新结果表格
            self.update_result_table(results)
        except Exception as e:
            progress.setStyleSheet(
                "QProgressBar::chunk {background-color: #FF0000;}")
            progress.setLabelText(f"筛选失败: {str(e)}")
        finally:
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(
                f"[StockScreenerWidget.screen_stocks] 结束，耗时: {elapsed} ms")
            progress.setValue(total_stocks)
            QTimer.singleShot(500, progress.close)

    def check_technical_condition(self, stock_data, condition_params):
        """检查技术指标条件，支持多种指标"""
        try:
            # 支持表达式如：MA5>MA10, MACD>0, RSI<70, BOLL>close, OBV>10000
            import re
            # 解析条件，支持 > < =
            match = re.match(
                r"([A-Z]+\d*)([><=])([A-Z]+\d*|\d+\.?\d*)", condition_params.replace(' ', ''))
            if not match:
                return False
            ind1, op, ind2 = match.groups()
            # 计算第一个指标

            def get_value(ind):
                # 优先支持ta-lib指标
                talib_list = get_talib_indicator_list()
                if ind in talib_list:
                    try:
                        # 已替换为新的导入
                        df = stock_data.copy()
                        res = calc_talib_indicator(ind, df)
                        if isinstance(res, pd.DataFrame):
                            return res.iloc[-1, 0]
                        else:
                            return res.iloc[-1]
                    except Exception:
                        return None
                # 内置指标全部用ta-lib封装（已移除hikyuu依赖）
                if ind.startswith('MA'):
                    period = int(ind[2:]) if len(
                        ind) > 2 and ind[2:].isdigit() else 5
                    close_data = stock_data['close']
                    # 统一使用新的指标系统（FactorWeave-Quant）
                    close_series = pd.Series(close_data) if not isinstance(close_data, pd.Series) else close_data
                    return calc_ma(close_series, period).iloc[-1]
                if ind == 'MACD':
                    close_data = stock_data['close']
                    # 使用新的指标系统（FactorWeave-Quant）
                    close_series = pd.Series(close_data) if not isinstance(close_data, pd.Series) else close_data
                    macd, _, _ = calc_macd(close_series, fast=12, slow=26, signal=9)
                    return macd.iloc[-1]
                if ind == 'RSI':
                    return calc_rsi(stock_data['close'], n=6).iloc[-1]
                if ind == 'KDJ':
                    k, d, j = calc_kdj(stock_data, n=9, m1=3, m2=3)
                    return j.iloc[-1]
                if ind == 'BOLL':
                    close_data = stock_data['close']
                    if isinstance(close_data, pd.Series):
                        _, upper, lower = calc_boll(close_data, n=20, p=2)
                        return upper.iloc[-1]
                    else:
                        # 对于非Series数据，也转换为Series处理
                        close_series = pd.Series(close_data)
                        _, upper, lower = calc_boll(close_series, n=20, p=2)
                        return upper.iloc[-1]
                if ind == 'ATR':
                    if isinstance(stock_data['close'], pd.Series):
                        return calc_atr(stock_data, n=14).iloc[-1]
                    else:
                        # 对于非Series数据，也转换为DataFrame处理
                        stock_df = pd.DataFrame(stock_data)
                        return calc_atr(stock_df, n=14).iloc[-1]
                if ind == 'OBV':
                    if isinstance(stock_data['close'], pd.Series):
                        return calc_obv(stock_data).iloc[-1]
                    else:
                        # 对于非Series数据，也转换为DataFrame处理
                        stock_df = pd.DataFrame(stock_data)
                        return calc_obv(stock_df).iloc[-1]
                if ind == 'CCI':
                    if isinstance(stock_data['close'], pd.Series):
                        return calc_cci(stock_data, n=14).iloc[-1]
                    else:
                        # 对于非Series数据，也转换为DataFrame处理
                        stock_df = pd.DataFrame(stock_data)
                        return calc_cci(stock_df, n=14).iloc[-1]
                return None
            v1 = get_value(ind1)
            v2 = get_value(ind2)
            if v1 is None or v2 is None:
                return False
            if op == '>':
                return v1 > v2
            elif op == '<':
                return v1 < v2
            elif op == '=':
                return v1 == v2
            return False
        except Exception:
            return False

    def check_fundamental_condition(self, stock, condition_params):
        """检查基本面条件"""
        try:
            # 解析条件参数
            # 示例：PE<20
            parts = condition_params.split('<')
            if len(parts) != 2:
                return False

            indicator = parts[0].strip()
            value = float(parts[1].strip())

            # 获取基本面数据
            if indicator == 'PE':
                return stock['pe'] < value
            elif indicator == 'PB':
                return stock['pb'] < value
            elif indicator == 'ROE':
                return stock['roe'] > value
            else:
                return False

        except Exception:
            return False

    def check_capital_condition(self, stock_data, condition_params):
        """检查资金流向条件"""
        try:
            # 解析条件参数
            # 示例：主力净流入>1000万
            parts = condition_params.split('>')
            if len(parts) != 2:
                return False

            indicator = parts[0].strip()
            value = float(parts[1].strip()) * 10000  # 转换为元

            # 获取资金流向数据
            if indicator == '主力净流入':
                return stock_data['main_net_inflow'].iloc[-1] > value
            elif indicator == '北向资金':
                return stock_data['north_money'].iloc[-1] > value
            else:
                return False

        except Exception:
            return False

    def check_news_condition(self, stock_code, condition_params):
        """检查消息面条件"""
        try:
            # 获取股票新闻数据
            from core.utils.data_standardizer import DataStandardizer
            data_standardizer = DataStandardizer()
            news_data = data_standardizer.get_stock_news(stock_code)

            # 检查是否包含关键词
            keywords = condition_params.split(',')
            for news in news_data:
                for keyword in keywords:
                    if keyword.strip() in news['title'] or keyword.strip() in news['content']:
                        return True

            return False

        except Exception:
            return False

    def update_result_table(self, results):
        """更新结果表格

        Args:
            results: DataFrame or list of dict containing stock screening results
        """
        try:
            # 清空表格
            self.paged_table.table.setRowCount(0)

            if isinstance(results, pd.DataFrame):
                # 如果输入是DataFrame
                self.paged_table.table.setRowCount(len(results))
                for i, (_, row) in enumerate(results.iterrows()):
                    # 设置股票代码
                    code_item = QTableWidgetItem(str(row['code']))
                    self.paged_table.table.setItem(i, 0, code_item)

                    # 设置股票名称
                    name_item = QTableWidgetItem(str(row['name']))
                    self.paged_table.table.setItem(i, 1, name_item)

                    # 设置最新价
                    close_item = QTableWidgetItem(f"{row['close']:.3f}")
                    close_item.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter)
                    self.paged_table.table.setItem(i, 2, close_item)

                    # 设置涨跌幅
                    change_item = QTableWidgetItem(
                        f"{row['change_percent']:.3f}%")
                    change_item.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter)
                    if row['change_percent'] > 0:
                        change_item.setForeground(QColor("#FF4D4D"))
                    elif row['change_percent'] < 0:
                        change_item.setForeground(QColor("#4DB870"))
                    self.paged_table.table.setItem(i, 3, change_item)

                    # 设置筛选得分
                    score_item = QTableWidgetItem(f"{row['score']:.3f}")
                    score_item.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter)
                    self.paged_table.table.setItem(i, 4, score_item)

                # 统计分析
                if not results.empty:
                    change_arr = results['change_percent'].values
                    score_arr = results['score'].values
                    row_count = len(results)
                    table = self.paged_table.table
                    # 添加统计行
                    table.setRowCount(row_count + 3)
                    # 均值行
                    mean_items = [QTableWidgetItem("均值"), QTableWidgetItem(""),
                                  QTableWidgetItem(""),
                                  QTableWidgetItem(
                                      f"{change_arr.mean():.3f}%"),
                                  QTableWidgetItem(f"{score_arr.mean():.3f}")]
                    for j, item in enumerate(mean_items):
                        item.setBackground(QColor("#fffde7"))
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        table.setItem(row_count, j, item)
                    # 最大行
                    max_idx = np.argmax(score_arr)
                    max_items = [QTableWidgetItem("最大"), QTableWidgetItem(""),
                                 QTableWidgetItem(""),
                                 QTableWidgetItem(
                                     f"{change_arr[max_idx]:.3f}%"),
                                 QTableWidgetItem(f"{score_arr[max_idx]:.3f}")]
                    for j, item in enumerate(max_items):
                        item.setBackground(QColor("#ffe082"))
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        table.setItem(row_count + 1, j, item)
                    # 最小行
                    min_idx = np.argmin(score_arr)
                    min_items = [QTableWidgetItem("最小"), QTableWidgetItem(""),
                                 QTableWidgetItem(""),
                                 QTableWidgetItem(
                                     f"{change_arr[min_idx]:.3f}%"),
                                 QTableWidgetItem(f"{score_arr[min_idx]:.3f}")]
                    for j, item in enumerate(min_items):
                        item.setBackground(QColor("#ffccbc"))
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        table.setItem(row_count + 2, j, item)
                    # 极值高亮
                    table.item(max_idx, 4).setBackground(QColor("#b2ff59"))
                    table.item(min_idx, 4).setBackground(QColor("#ffcdd2"))
                    table.item(np.argmax(change_arr), 3).setBackground(
                        QColor("#b2ff59"))
                    table.item(np.argmin(change_arr), 3).setBackground(
                        QColor("#ffcdd2"))
            else:
                # 如果输入是字典列表
                self.paged_table.table.setRowCount(len(results))
                for i, result in enumerate(results):
                    # 设置股票代码
                    code_item = QTableWidgetItem(str(result['code']))
                    self.paged_table.table.setItem(i, 0, code_item)

                    # 设置股票名称
                    name_item = QTableWidgetItem(str(result['name']))
                    self.paged_table.table.setItem(i, 1, name_item)

                    # 设置最新价
                    close_item = QTableWidgetItem(f"{result['close']:.3f}")
                    close_item.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter)
                    self.paged_table.table.setItem(i, 2, close_item)

                    # 设置涨跌幅
                    change_item = QTableWidgetItem(
                        f"{result['change_percent']:.3f}%")
                    change_item.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter)
                    if result['change_percent'] > 0:
                        change_item.setForeground(QColor("#FF4D4D"))
                    elif result['change_percent'] < 0:
                        change_item.setForeground(QColor("#4DB870"))
                    self.paged_table.table.setItem(i, 3, change_item)

                    # 设置筛选得分
                    score_item = QTableWidgetItem(f"{result['score']:.3f}")
                    score_item.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter)
                    self.paged_table.table.setItem(i, 4, score_item)

            # 调整列宽
            self.paged_table.table.resizeColumnsToContents()

            # 更新状态
            logger.info(f"更新选股结果表格完成，共{len(results)}条记录")

        except Exception as e:
            error_msg = f"更新结果表格失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "错误", error_msg)

    def load_template(self):
        """加载选中的模板"""
        try:
            # 获取选中的模板名称
            template_name = self.template_combo.currentText()
            if not template_name:
                QMessageBox.warning(self, "警告", "请先选择一个模板")
                return

            # 加载模板
            strategy_type, conditions = self.screener.load_strategy(
                template_name)
            if strategy_type and conditions:
                # 更新策略类型
                index = self.strategy_type.findText(strategy_type)
                if index >= 0:
                    self.strategy_type.setCurrentIndex(index)

                # 更新条件设置
                self.update_conditions(conditions)

                logger.info(f"已加载模板: {template_name}")
                QMessageBox.information(self, "成功", "模板加载成功")

        except Exception as e:
            logger.error(f"加载模板失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载模板失败: {str(e)}")

    def center_dialog(self, dialog, parent=None, offset_y=50):
        """将弹窗居中到父窗口或屏幕，并尽量靠近上部

        Args:
            dialog: 要居中的对话框
            parent: 父窗口，如果为None则使用屏幕
            offset_y: 距离顶部的偏移量
        """
        try:
            if parent and parent.isVisible():
                # 相对于父窗口居中
                parent_geom = parent.geometry()
                dialog_geom = dialog.frameGeometry()
                x = parent_geom.center().x() - dialog_geom.width() // 2
                y = parent_geom.top() + offset_y

                # 确保弹窗不会超出父窗口边界
                x = max(parent_geom.left(), min(
                    x, parent_geom.right() - dialog_geom.width()))
                y = max(parent_geom.top(), min(
                    y, parent_geom.bottom() - dialog_geom.height()))
            else:
                # 相对于屏幕居中
                screen = dialog.screen() or dialog.parentWidget().screen()
                if screen:
                    screen_geom = screen.geometry()
                    dialog_geom = dialog.frameGeometry()
                    x = screen_geom.center().x() - dialog_geom.width() // 2
                    y = screen_geom.top() + offset_y

                    # 确保弹窗不会超出屏幕边界
                    x = max(screen_geom.left(), min(
                        x, screen_geom.right() - dialog_geom.width()))
                    y = max(screen_geom.top(), min(
                        y, screen_geom.bottom() - dialog_geom.height()))

            dialog.move(x, y)
        except Exception as e:
            logger.error(f"设置弹窗位置失败: {str(e)}")

    def get_available_indicators(self):
        """获取可用的技术指标列表"""
        try:
            # 使用新的指标系统获取指标列表
            indicators = get_all_indicators_metadata()
            # 将指标按分类组织
            categories = {}
            for indicator in indicators:
                category = indicator.get('category', '其他')
                if category not in categories:
                    categories[category] = []
                categories[category].append(indicator['name'])
            return categories
        except Exception as e:
            logger.error(f"获取指标列表失败: {str(e)}")
            # 返回默认分类
            return {
                "趋势指标": ["MA", "EMA", "MACD"],
                "震荡指标": ["RSI", "KDJ", "CCI"],
                "成交量指标": ["OBV", "VOLUME"],
                "波动率指标": ["ATR", "BOLL"]
            }

    def screen_by_technical(self, stock_list: List[str], params: Dict[str, Any]) -> pd.DataFrame:
        """技术指标筛选，全部用ta-lib封装，分类、筛选用统一接口"""
        results = []
        categories = self.get_available_indicators()
        # 示例：遍历所有分类和指标，实际可按params指定分类/指标筛选
        for stock in stock_list:
            try:
                from core.utils.data_standardizer import DataStandardizer
                data_standardizer = DataStandardizer()
                kdata = data_standardizer.get_kdata(stock)
                if kdata.empty:
                    continue
                for cat, inds in categories.items():
                    for ind in inds:
                        try:
                            res = calc_talib_indicator(ind, kdata)
                        except Exception:
                            continue
                # ...原有条件判断和结果收集逻辑...
                ma_short = calc_ma(kdata['close'], params.get('ma_short', 5))
                ma_long = calc_ma(kdata['close'], params.get('ma_long', 20))
                macd, _, _ = calc_macd(
                    kdata['close'], fast=12, slow=26, signal=9)
                rsi = calc_rsi(kdata['close'], n=6)
                if ma_short.iloc[-1] > ma_long.iloc[-1] and macd.iloc[-1] > 0 and rsi.iloc[-1] > params.get('rsi_value', 50):
                    info = data_standardizer.get_stock_info(stock)
                    results.append({
                        'code': stock,
                        'name': info['name'],
                        'industry': info['industry'],
                        'price': kdata['close'].iloc[-1],
                        'change': (kdata['close'].iloc[-1] / kdata['close'].iloc[-2] - 1) * 100,
                        'pe': info['pe'],
                        'pb': info['pb'],
                        'roe': info['roe'],
                        'main_force': self.get_main_force(stock),
                        'north_money': self.get_north_money(stock)
                    })
            except Exception as e:
                logger.info(
                    f"处理股票 {stock} 失败: {str(e)}")
                continue
        return pd.DataFrame(results)

    def show_screener_guide(self):
        """显示选股器操作引导"""
        QMessageBox.information(
            self,
            "选股操作引导",
            "【选股操作步骤】\n"
            "1. 选择策略类型和条件，支持技术、基本面、资金面等多维度筛选。\n"
            "2. 点击\"开始选股\"按钮，系统将自动筛选并分页展示结果。\n"
            "3. 可导出结果、保存/加载策略模板。\n"
            "4. 鼠标悬停在各控件上可查看详细说明。"
        )

    def validate_params(self) -> (bool, str):
        """
        校验所有选股条件控件的输入，支持QSpinBox、QDoubleSpinBox、QLineEdit等。
        校验失败时高亮控件并返回错误信息。
        Returns:
            (bool, str): 是否通过校验，错误信息
        """
        valid = True
        error_msgs = []
        # 技术指标条件
        if hasattr(self, 'rsi_period'):
            w = self.rsi_period
            w.setStyleSheet("")
            v = w.value()
            if v < w.minimum() or v > w.maximum():
                valid = False
                error_msgs.append(f"RSI周期超出范围 [{w.minimum()}, {w.maximum()}]")
                w.setStyleSheet("border: 2px solid red;")
        # 基本面条件
        for attr in ['pe_min', 'pe_max', 'pb_min', 'pb_max', 'roe_min']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                w.setStyleSheet("")
                v = w.value()
                if v < w.minimum() or v > w.maximum():
                    valid = False
                    error_msgs.append(
                        f"{attr.upper()} 超出范围 [{w.minimum()}, {w.maximum()}]")
                    w.setStyleSheet("border: 2px solid red;")
        # 资金面条件
        for attr in ['inflow_min', 'volume_min']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                w.setStyleSheet("")
                v = w.value()
                if v < w.minimum() or v > w.maximum():
                    valid = False
                    error_msgs.append(
                        f"{attr.upper()} 超出范围 [{w.minimum()}, {w.maximum()}]")
                    w.setStyleSheet("border: 2px solid red;")
        # 综合权重
        for attr in ['tech_weight', 'fund_weight', 'cap_weight']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                w.setStyleSheet("")
                v = w.value()
                if v < w.minimum() or v > w.maximum():
                    valid = False
                    error_msgs.append(
                        f"{attr.upper()} 超出范围 [{w.minimum()}, {w.maximum()}]")
                    w.setStyleSheet("border: 2px solid red;")
        return valid, "\n".join(error_msgs)

    def _connect_condition_signals(self):
        """为所有条件控件增加实时校验信号"""
        for attr in ['rsi_period', 'pe_min', 'pe_max', 'pb_min', 'pb_max', 'roe_min',
                     'inflow_min', 'volume_min', 'tech_weight', 'fund_weight', 'cap_weight']:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if hasattr(w, 'valueChanged'):
                    w.valueChanged.connect(self._on_condition_changed)
                elif hasattr(w, 'editingFinished'):
                    w.editingFinished.connect(self._on_condition_changed)

    def _on_condition_changed(self):
        valid, msg = self.validate_params()
        # 实时高亮错误，无需弹窗
        # 可扩展为状态栏提示

    def show_template_manager_dialog(self):
        """弹出批量模板管理对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("批量模板管理")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.MultiSelection)
        # 加载模板列表
        for name in self.template_manager.list_templates():
            list_widget.addItem(name)
        layout.addWidget(list_widget)
        # 按钮区
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("导入")
        export_btn = QPushButton("导出")
        delete_btn = QPushButton("删除")
        rename_btn = QPushButton("重命名")
        apply_btn = QPushButton("应用")
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(rename_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)
        # 事件绑定
        import_btn.clicked.connect(lambda: self._import_templates(list_widget))
        export_btn.clicked.connect(lambda: self._export_templates(list_widget))
        delete_btn.clicked.connect(lambda: self._delete_templates(list_widget))
        rename_btn.clicked.connect(lambda: self._rename_template(list_widget))
        apply_btn.clicked.connect(
            lambda: self._apply_template(list_widget, dialog))
        dialog.exec_()

    def _import_templates(self, list_widget):
        files, _ = QFileDialog.getOpenFileNames(
            self, "导入模板", "", "JSON Files (*.json)")
        if files:
            self.template_manager.import_templates(files)
            list_widget.clear()
            for name in self.template_manager.list_templates():
                list_widget.addItem(name)

    def _export_templates(self, list_widget):
        selected = [item.text() for item in list_widget.selectedItems()]
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要导出的模板")
            return
        dir_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if dir_path:
            self.template_manager.export_templates(selected, dir_path)
            QMessageBox.information(self, "成功", "模板导出成功")

    def _delete_templates(self, list_widget):
        selected = [item.text() for item in list_widget.selectedItems()]
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return
        self.template_manager.delete_templates(selected)
        for item in list_widget.selectedItems():
            list_widget.takeItem(list_widget.row(item))
        QMessageBox.information(self, "成功", "模板删除成功")

    def _rename_template(self, list_widget):
        selected = list_widget.selectedItems()
        if len(selected) != 1:
            QMessageBox.warning(self, "提示", "请只选择一个模板进行重命名")
            return
        old_name = selected[0].text()
        new_name, ok = QInputDialog.getText(
            self, "重命名模板", "新模板名:", text=old_name)
        if ok and new_name and new_name != old_name:
            params = self.template_manager.load_template(old_name)
            self.template_manager.save_template(new_name, params)
            self.template_manager.delete_templates([old_name])
            selected[0].setText(new_name)
            QMessageBox.information(self, "成功", "模板重命名成功")

    def _apply_template(self, list_widget, dialog):
        selected = list_widget.selectedItems()
        if len(selected) != 1:
            QMessageBox.warning(self, "提示", "请只选择一个模板进行应用")
            return
        name = selected[0].text()
        params = self.template_manager.load_template(name)
        # 这里假设params结构与get_current_conditions一致
        self.update_conditions(params)
        QMessageBox.information(self, "成功", f"模板 {name} 已应用")
        dialog.accept()

    def import_stock_codes(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入股票代码", "", "Text Files (*.txt)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                codes = f.read().replace('\n', ',')
                self.batch_input.setText(codes)

    def compare_strategies(self):
        codes = [c.strip()
                 for c in self.batch_input.text().split(',') if c.strip()]
        strategies = [cb.text()
                      for cb in self.strategy_checkboxes if cb.isChecked()]
        if not codes or not strategies:
            QMessageBox.warning(self, "参数错误", "请至少输入一个股票代码并选择一个策略")
            return
        # 清空表格
        self.compare_table.setRowCount(0)
        # 动态设置表头，展示常用对比指标
        headers = ["股票代码", "策略", "信号", "得分", "涨跌幅",
                   "PE", "PB", "ROE", "主力净流入", "北向资金"]
        self.compare_table.setColumnCount(len(headers))
        self.compare_table.setHorizontalHeaderLabels(headers)
        screener = StockScreener(self.data_manager)
        row = 0
        for code in codes:
            for strategy in strategies:
                try:
                    # 根据策略类型调用不同分析方法
                    if strategy in ["双均线", "MACD", "KDJ", "RSI", "BOLL"]:
                        # 技术指标策略
                        params = {"ma_short": 5, "ma_long": 20,
                                  "rsi_value": 50}  # 可扩展为UI参数
                        df = screener.screen_by_technical([code], params)
                    else:
                        # 其他策略可扩展
                        df = None
                    if df is not None and not df.empty:
                        info = df.iloc[0]
                        items = [
                            str(info.get("code", code)),
                            strategy,
                            "买入" if info.get(
                                "change", 0) > 0 else "观望",  # 示例信号
                            f"{info.get('score', 0):.3f}" if 'score' in info else "-",
                            f"{info.get('change', 0):.3f}%" if 'change' in info else "-",
                            f"{info.get('pe', 0):.3f}" if 'pe' in info else "-",
                            f"{info.get('pb', 0):.3f}" if 'pb' in info else "-",
                            f"{info.get('roe', 0):.3f}" if 'roe' in info else "-",
                            f"{info.get('main_force', 0):.3f}" if 'main_force' in info else "-",
                            f"{info.get('north_money', 0):.3f}" if 'north_money' in info else "-",
                        ]
                    else:
                        items = [code, strategy, "无信号", "-",
                                 "-", "-", "-", "-", "-", "-"]
                    self.compare_table.insertRow(row)
                    for col, val in enumerate(items):
                        self.compare_table.setItem(
                            row, col, QTableWidgetItem(val))
                    row += 1
                except Exception as e:
                    logger.error(
                        f"策略对比分析失败: {code}-{strategy}: {str(e)}")
                    self.compare_table.insertRow(row)
                    for col, val in enumerate([code, strategy, "异常", "-", "-", "-", "-", "-", "-", "-"]):
                        self.compare_table.setItem(
                            row, col, QTableWidgetItem(val))
                    row += 1
        self.compare_table.resizeColumnsToContents()
        QMessageBox.information(self, "对比完成", "多策略对比分析已完成，结果已展示。")

    def export_batch_results(self):
        """
        批量导出分析结果，支持多选导出和批量导出所有策略/股票结果
        """
        try:
            # 导出compare_table中的所有结果
            row_count = self.compare_table.rowCount()
            if row_count == 0:
                QMessageBox.warning(self, "警告", "没有可导出的对比分析结果")
                return
            data = []
            for row in range(row_count):
                code = self.compare_table.item(row, 0).text()
                strategy = self.compare_table.item(row, 1).text()
                result = self.compare_table.item(row, 2).text()
                data.append({
                    'code': code,
                    'strategy': strategy,
                    'result': result
                })
            df = pd.DataFrame(data)
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "批量导出分析结果",
                f"批量分析结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "Excel Files (*.xlsx);;CSV Files (*.csv)"
            )
            if file_path:
                if file_path.endswith('.xlsx'):
                    df.to_excel(file_path, index=False)
                else:
                    df.to_csv(file_path, index=False)
                QMessageBox.information(self, "成功", "批量分析结果导出成功")
        except Exception as e:
            logger.error(f"批量导出失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"批量导出失败: {str(e)}")

    # 多面板联动和自定义指标预留接口

    def link_with_other_panels(self, panel_refs: dict):
        """
        多面板联动接口，panel_refs为其他面板实例的引用字典
        """
        self._linked_panels = panel_refs
        # 示例：可通过self._linked_panels['fund_flow']等访问其他面板

    def add_custom_indicator(self, name: str, func):
        """
        注册自定义指标，func为计算函数，name为指标名
        """
        if not hasattr(self, '_custom_indicators'):
            self._custom_indicators = {}
        self._custom_indicators[name] = func
        # 可在筛选/对比分析时调用自定义指标

    def run_multi_factor_selection(self):
        """一键多因子选股，自动特征工程+因子加权+批量选股"""
        try:
            from features.feature_selection import integrate_enhanced_features, enhanced_feature_selection, select_features_pca
            # 获取股票数据
            from core.utils.data_standardizer import DataStandardizer
            data_standardizer = DataStandardizer()
            stock_list = data_standardizer.get_stock_list()
            dfs = []
            for code in stock_list['code']:
                df = data_standardizer.get_kdata(code)
                if not df.empty:
                    df = integrate_enhanced_features(df)
                    df['code'] = code
                    dfs.append(df)
            if not dfs:
                QMessageBox.warning(self, "无数据", "未获取到有效股票数据")
                return
            all_df = pd.concat(dfs, ignore_index=True)
            # 特征选择
            method = self.feature_method_combo.currentText()
            if method == "PCA降维":
                selected = select_features_pca(
                    all_df.drop(['code'], axis=1), n_components=8)
            elif method == "增强型特征选择":
                y = (all_df['close'].pct_change().shift(-1)
                     > 0).astype(int)  # 以次日涨跌为目标
                selected, _ = enhanced_feature_selection(
                    all_df.drop(['code'], axis=1), y)
                selected = [all_df.columns[i]
                            for i in selected if all_df.columns[i] != 'code']
            else:
                selected = [self.factor_table.item(i, 0).text(
                ) for i in range(self.factor_table.rowCount())]
            # 权重
            weights = {}
            for i, feat in enumerate(selected):
                item = self.factor_table.item(i, 1)
                try:
                    weights[feat] = float(item.text()) if item else 1.0
                except Exception:
                    weights[feat] = 1.0
            # 计算综合得分
            all_df['score'] = 0
            for feat in selected:
                if feat in all_df.columns:
                    all_df['score'] += all_df[feat].rank(
                        pct=True) * weights.get(feat, 1.0)
            # 结果排序
            result = all_df.groupby('code').agg({
                'score': 'mean', 'close': 'last', 'industry': 'last', 'name': 'last', 'pe': 'last', 'pb': 'last', 'change': 'last'
            }).reset_index()
            result = result.sort_values('score', ascending=False).head(100)
            self.multi_factor_result.setRowCount(len(result))
            for i, row in result.iterrows():
                self.multi_factor_result.setItem(
                    i, 0, QTableWidgetItem(str(row['code'])))
                self.multi_factor_result.setItem(
                    i, 1, QTableWidgetItem(str(row['name'])))
                self.multi_factor_result.setItem(
                    i, 2, QTableWidgetItem(str(row['industry'])))
                self.multi_factor_result.setItem(
                    i, 3, QTableWidgetItem(f"{row['close']:.3f}"))
                self.multi_factor_result.setItem(i, 4, QTableWidgetItem(
                    f"{row['change']:.3f}%" if 'change' in row else '-'))
                self.multi_factor_result.setItem(i, 5, QTableWidgetItem(
                    f"{row['pe']:.3f}" if 'pe' in row else '-'))
                self.multi_factor_result.setItem(i, 6, QTableWidgetItem(
                    f"{row['pb']:.3f}" if 'pb' in row else '-'))
                self.multi_factor_result.setItem(
                    i, 7, QTableWidgetItem(f"{row['score']:.4f}"))
            self.multi_factor_result.resizeColumnsToContents()
            QMessageBox.information(self, "多因子选股完成", "多因子选股已完成，结果已展示。")
        except Exception as e:
            logger.error(f"多因子选股异常: {str(e)}")
            QMessageBox.critical(self, "多因子选股异常", str(e))

    def export_multi_factor_results(self):
        try:
            row_count = self.multi_factor_result.rowCount()
            if row_count == 0:
                QMessageBox.warning(self, "无数据", "没有可导出的多因子选股结果")
                return
            data = []
            for row in range(row_count):
                data.append([
                    self.multi_factor_result.item(row, col).text(
                    ) if self.multi_factor_result.item(row, col) else ''
                    for col in range(self.multi_factor_result.columnCount())
                ])
            df = pd.DataFrame(
                data, columns=["股票代码", "名称", "行业", "最新价", "涨跌幅", "PE", "PB", "综合得分"])
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出多因子选股结果", "多因子选股结果", "Excel Files (*.xlsx);;CSV Files (*.csv)")
            if file_path:
                if file_path.endswith('.xlsx'):
                    df.to_excel(file_path, index=False)
                else:
                    df.to_csv(file_path, index=False)
                QMessageBox.information(self, "导出成功", "多因子选股结果已导出")
        except Exception as e:
            logger.error(f"导出多因子选股结果失败: {str(e)}")
            QMessageBox.critical(self, "导出失败", f"导出多因子选股结果失败: {str(e)}")

    def _run_analysis_async(self, button, analysis_func, *args, **kwargs):
        original_text = button.text()
        button.setText("取消")
        button._interrupted = False

        def on_cancel():
            button._interrupted = True
            button.setText(original_text)
            button.setEnabled(True)
            # 重新绑定分析逻辑
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda: self._run_analysis_async(
                button, analysis_func, *args, **kwargs))

        try:
            button.clicked.disconnect()
        except Exception:
            pass
        button.clicked.connect(on_cancel)

        def task():
            try:
                if not getattr(button, '_interrupted', False):
                    result = analysis_func(*args, **kwargs)
                    return result
            except Exception as e:
                if True:  # 使用Loguru日志
                    logger.error(f"分析异常: {str(e)}")
                return None
            finally:
                QTimer.singleShot(0, lambda: on_done(None))

        def on_done(future):
            button.setText(original_text)
            button.setEnabled(True)
            # 重新绑定分析逻辑
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda: self._run_analysis_async(
                button, analysis_func, *args, **kwargs))
        if not hasattr(self, '_thread_pool'):
            self._thread_pool = ThreadPoolExecutor(os.cpu_count() * 2)
        future = self._thread_pool.submit(task)
        # 只需在finally中恢复，无需重复回调

    def on_screener_analyze(self):
        """选股分析入口，参数校验、日志、调用主分析逻辑，自动适配所有策略和UI刷新。"""
        valid, msg = self.validate_params()
        if not valid:
            self.set_status_message(msg, error=True)
            return
        self.set_status_message("参数校验通过，正在分析...", error=False)
        try:
            logger.info("on_screener_analyze 开始分析 - 选股")
            from core.utils.data_standardizer import DataStandardizer
            data_standardizer = DataStandardizer()
            if hasattr(data_standardizer, 'get_screener_results'):
                data = data_standardizer.get_screener_results()
                if data:
                    self.update_screener_results(data)
                    self.set_status_message("分析完成", error=False)
                else:
                    self.set_status_message("未获取到选股结果", error=True)
                    logger.warning("分析未获取到数据")
            else:
                self.set_status_message(
                    "数据管理器未实现get_screener_results", error=True)
        except Exception as e:
            self.set_status_message(f"分析失败: {str(e)}", error=True)
            logger.error(f"分析失败: {str(e)}")
