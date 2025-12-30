"""
高级搜索对话框

提供完整的多维度股票筛选功能，完全按照原版main_legacy.py实现。
"""

from loguru import logger
from typing import Dict, Any, List, Optional
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QGridLayout, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter,
    QProgressBar, QMessageBox, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont

logger = logger


class SearchWorker(QThread):
    """搜索工作线程"""

    search_completed = pyqtSignal(list)
    search_error = pyqtSignal(str)
    search_progress = pyqtSignal(int)

    def __init__(self, search_params: Dict[str, Any]):
        super().__init__()
        self.search_params = search_params

    def run(self):
        """执行搜索"""
        try:
            # 这里模拟搜索过程
            # 实际项目中需要连接到数据源进行搜索
            import time

            results = []
            total_stocks = 100  # 假设有100只股票

            for i in range(total_stocks):
                # 模拟搜索进度
                time.sleep(0.01)
                progress = int((i + 1) / total_stocks * 100)
                self.search_progress.emit(progress)

                # 模拟符合条件的股票
                if i % 3 == 0:  # 每3只股票中有1只符合条件
                    stock = {
                        'code': f'00000{i:02d}',
                        'name': f'测试股票{i}',
                        'market': '沪市主板' if i % 2 == 0 else '深市主板',
                        'industry': '电子信息' if i % 4 == 0 else '制造业',
                        'price': 10.0 + i * 0.1,
                        'market_cap': 100000000 + i * 1000000,
                        'volume': 1000000 + i * 10000,
                        'turnover_rate': 1.0 + i * 0.01
                    }

                    # 应用筛选条件
                    if self._matches_criteria(stock):
                        results.append(stock)

            self.search_completed.emit(results)

        except Exception as e:
            logger.error(f"Search failed: {e}")
            self.search_error.emit(str(e))

    def _matches_criteria(self, stock: Dict[str, Any]) -> bool:
        """检查股票是否符合搜索条件"""
        try:
            params = self.search_params

            # 股票代码筛选
            if params.get('code') and params['code'] not in stock['code']:
                return False

            # 股票名称筛选
            if params.get('name') and params['name'] not in stock['name']:
                return False

            # 市场分类筛选
            if params.get('market') and params['market'] != '全部' and params['market'] != stock['market']:
                return False

            # 行业分类筛选
            if params.get('industry') and params['industry'] != '全部' and params['industry'] != stock['industry']:
                return False

            # 价格范围筛选
            if params.get('price_min') and stock['price'] < params['price_min']:
                return False
            if params.get('price_max') and stock['price'] > params['price_max']:
                return False

            # 市值范围筛选
            if params.get('market_cap_min') and stock['market_cap'] < params['market_cap_min']:
                return False
            if params.get('market_cap_max') and stock['market_cap'] > params['market_cap_max']:
                return False

            # 成交量范围筛选
            if params.get('volume_min') and stock['volume'] < params['volume_min']:
                return False
            if params.get('volume_max') and stock['volume'] > params['volume_max']:
                return False

            # 换手率范围筛选
            if params.get('turnover_min') and stock['turnover_rate'] < params['turnover_min']:
                return False
            if params.get('turnover_max') and stock['turnover_rate'] > params['turnover_max']:
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to match criteria: {e}")
            return False


class AdvancedSearchDialog(QDialog):
    """高级搜索对话框"""

    # 定义信号
    search_completed = pyqtSignal(list)  # 搜索完成信号

    def __init__(self, parent=None):
        """
        初始化高级搜索对话框

        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.search_worker = None

        self.setWindowTitle("高级搜索")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self._init_ui()
        self._init_data()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧：搜索条件面板
        search_panel = self._create_search_panel()
        splitter.addWidget(search_panel)

        # 右侧：搜索结果面板
        result_panel = self._create_result_panel()
        splitter.addWidget(result_panel)

        # 设置分割器比例
        splitter.setSizes([400, 500])

        # 按钮栏
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        # 搜索按钮
        search_btn = QPushButton("开始搜索")
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        search_btn.clicked.connect(self._start_search)
        button_layout.addWidget(search_btn)

        # 重置按钮
        reset_btn = QPushButton("重置条件")
        reset_btn.clicked.connect(self._reset_conditions)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _create_search_panel(self) -> QWidget:
        """创建搜索条件面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)

        # 基础条件组
        basic_group = QGroupBox("基础条件")
        basic_layout = QGridLayout(basic_group)

        # 股票代码
        basic_layout.addWidget(QLabel("股票代码:"), 0, 0)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("如: 000001")
        basic_layout.addWidget(self.code_edit, 0, 1)

        # 股票名称
        basic_layout.addWidget(QLabel("股票名称:"), 1, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如: 平安银行")
        basic_layout.addWidget(self.name_edit, 1, 1)

        # 市场分类
        basic_layout.addWidget(QLabel("市场分类:"), 2, 0)
        self.market_combo = QComboBox()
        self.market_combo.addItems([
            "全部", "沪市主板", "深市主板", "创业板", "科创板", "北交所"
        ])
        basic_layout.addWidget(self.market_combo, 2, 1)

        # 行业分类
        basic_layout.addWidget(QLabel("行业分类:"), 3, 0)
        self.industry_combo = QComboBox()
        self.industry_combo.addItems([
            "全部", "电子信息", "制造业", "金融业", "房地产", "医药生物",
            "化工", "机械设备", "电力设备", "食品饮料", "交通运输"
        ])
        basic_layout.addWidget(self.industry_combo, 3, 1)

        layout.addWidget(basic_group)

        # 价格范围组
        price_group = QGroupBox("价格范围")
        price_layout = QGridLayout(price_group)

        price_layout.addWidget(QLabel("最低价格:"), 0, 0)
        self.price_min_spin = QDoubleSpinBox()
        self.price_min_spin.setRange(0, 999999)
        self.price_min_spin.setDecimals(2)
        self.price_min_spin.setSuffix("元")
        price_layout.addWidget(self.price_min_spin, 0, 1)

        price_layout.addWidget(QLabel("最高价格:"), 0, 2)
        self.price_max_spin = QDoubleSpinBox()
        self.price_max_spin.setRange(0, 999999)
        self.price_max_spin.setDecimals(2)
        self.price_max_spin.setSuffix("元")
        self.price_max_spin.setValue(999999)
        price_layout.addWidget(self.price_max_spin, 0, 3)

        layout.addWidget(price_group)

        # 市值范围组
        market_cap_group = QGroupBox("市值范围")
        market_cap_layout = QGridLayout(market_cap_group)

        market_cap_layout.addWidget(QLabel("最小市值:"), 0, 0)
        self.market_cap_min_spin = QSpinBox()
        self.market_cap_min_spin.setRange(0, 999999)
        self.market_cap_min_spin.setSuffix("亿元")
        market_cap_layout.addWidget(self.market_cap_min_spin, 0, 1)

        market_cap_layout.addWidget(QLabel("最大市值:"), 0, 2)
        self.market_cap_max_spin = QSpinBox()
        self.market_cap_max_spin.setRange(0, 999999)
        self.market_cap_max_spin.setSuffix("亿元")
        self.market_cap_max_spin.setValue(999999)
        market_cap_layout.addWidget(self.market_cap_max_spin, 0, 3)

        layout.addWidget(market_cap_group)

        # 成交量范围组
        volume_group = QGroupBox("成交量范围")
        volume_layout = QGridLayout(volume_group)

        volume_layout.addWidget(QLabel("最小成交量:"), 0, 0)
        self.volume_min_spin = QSpinBox()
        self.volume_min_spin.setRange(0, 999999999)
        self.volume_min_spin.setSuffix("手")
        volume_layout.addWidget(self.volume_min_spin, 0, 1)

        volume_layout.addWidget(QLabel("最大成交量:"), 0, 2)
        self.volume_max_spin = QSpinBox()
        self.volume_max_spin.setRange(0, 999999999)
        self.volume_max_spin.setSuffix("手")
        self.volume_max_spin.setValue(999999999)
        volume_layout.addWidget(self.volume_max_spin, 0, 3)

        layout.addWidget(volume_group)

        # 换手率范围组
        turnover_group = QGroupBox("换手率范围")
        turnover_layout = QGridLayout(turnover_group)

        turnover_layout.addWidget(QLabel("最小换手率:"), 0, 0)
        self.turnover_min_spin = QDoubleSpinBox()
        self.turnover_min_spin.setRange(0, 100)
        self.turnover_min_spin.setDecimals(2)
        self.turnover_min_spin.setSuffix("%")
        turnover_layout.addWidget(self.turnover_min_spin, 0, 1)

        turnover_layout.addWidget(QLabel("最大换手率:"), 0, 2)
        self.turnover_max_spin = QDoubleSpinBox()
        self.turnover_max_spin.setRange(0, 100)
        self.turnover_max_spin.setDecimals(2)
        self.turnover_max_spin.setSuffix("%")
        self.turnover_max_spin.setValue(100)
        turnover_layout.addWidget(self.turnover_max_spin, 0, 3)

        layout.addWidget(turnover_group)

        layout.addStretch()
        return panel

    def _create_result_panel(self) -> QWidget:
        """创建搜索结果面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)

        # 结果标题
        result_title = QLabel("搜索结果")
        result_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(result_title)

        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "市场", "行业", "价格", "市值(亿)", "成交量(手)", "换手率(%)"
        ])

        # 设置表格样式
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setStyleSheet("""
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

        # 调整列宽
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 股票名称列自适应

        layout.addWidget(self.result_table)

        # 结果统计
        self.result_label = QLabel("共找到 0 只股票")
        self.result_label.setStyleSheet(
            "color: #6c757d; font-size: 12px; padding: 5px;")
        layout.addWidget(self.result_label)

        return panel

    def _init_data(self):
        """初始化数据"""
        # 这里可以加载初始数据，如行业分类等
        pass

    def _start_search(self):
        """开始搜索"""
        try:
            # 收集搜索参数
            search_params = {
                'code': self.code_edit.text().strip(),
                'name': self.name_edit.text().strip(),
                'market': self.market_combo.currentText(),
                'industry': self.industry_combo.currentText(),
                'price_min': self.price_min_spin.value() if self.price_min_spin.value() > 0 else None,
                'price_max': self.price_max_spin.value() if self.price_max_spin.value() < 999999 else None,
                'market_cap_min': self.market_cap_min_spin.value() * 100000000 if self.market_cap_min_spin.value() > 0 else None,
                'market_cap_max': self.market_cap_max_spin.value() * 100000000 if self.market_cap_max_spin.value() < 999999 else None,
                'volume_min': self.volume_min_spin.value() if self.volume_min_spin.value() > 0 else None,
                'volume_max': self.volume_max_spin.value() if self.volume_max_spin.value() < 999999999 else None,
                'turnover_min': self.turnover_min_spin.value() if self.turnover_min_spin.value() > 0 else None,
                'turnover_max': self.turnover_max_spin.value() if self.turnover_max_spin.value() < 100 else None,
            }

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            # 清空结果表格
            self.result_table.setRowCount(0)
            self.result_label.setText("正在搜索...")

            # 启动搜索线程
            self.search_worker = SearchWorker(search_params)
            self.search_worker.search_completed.connect(
                self._on_search_completed)
            self.search_worker.search_error.connect(self._on_search_error)
            self.search_worker.search_progress.connect(
                self._on_search_progress)
            self.search_worker.start()

        except Exception as e:
            logger.error(f"Failed to start search: {e}")
            QMessageBox.critical(self, "搜索错误", f"启动搜索失败: {str(e)}")

    def _on_search_progress(self, progress: int):
        """更新搜索进度"""
        self.progress_bar.setValue(progress)

    def _on_search_completed(self, results: List[Dict[str, Any]]):
        """搜索完成处理"""
        try:
            # 隐藏进度条
            self.progress_bar.setVisible(False)

            # 更新结果表格
            self.result_table.setRowCount(len(results))
            for i, stock in enumerate(results):
                self.result_table.setItem(
                    i, 0, QTableWidgetItem(stock['code']))
                self.result_table.setItem(
                    i, 1, QTableWidgetItem(stock['name']))
                self.result_table.setItem(
                    i, 2, QTableWidgetItem(stock['market']))
                self.result_table.setItem(
                    i, 3, QTableWidgetItem(stock['industry']))
                self.result_table.setItem(
                    i, 4, QTableWidgetItem(f"{stock['price']:.2f}"))
                self.result_table.setItem(i, 5, QTableWidgetItem(
                    f"{stock['market_cap']/100000000:.2f}"))
                self.result_table.setItem(
                    i, 6, QTableWidgetItem(f"{stock['volume']:,}"))
                self.result_table.setItem(i, 7, QTableWidgetItem(
                    f"{stock['turnover_rate']:.2f}"))

            # 更新统计信息
            self.result_label.setText(f"共找到 {len(results)} 只股票")

            # 发出搜索完成信号
            self.search_completed.emit(results)

        except Exception as e:
            logger.error(f"Failed to process search results: {e}")
            QMessageBox.critical(self, "结果处理错误", f"处理搜索结果失败: {str(e)}")

    def _on_search_error(self, error_msg: str):
        """搜索错误处理"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 显示错误信息
        self.result_label.setText("搜索失败")
        QMessageBox.critical(self, "搜索错误", f"搜索失败: {error_msg}")

    def _reset_conditions(self):
        """重置搜索条件"""
        try:
            self.code_edit.clear()
            self.name_edit.clear()
            self.market_combo.setCurrentIndex(0)
            self.industry_combo.setCurrentIndex(0)
            self.price_min_spin.setValue(0)
            self.price_max_spin.setValue(999999)
            self.market_cap_min_spin.setValue(0)
            self.market_cap_max_spin.setValue(999999)
            self.volume_min_spin.setValue(0)
            self.volume_max_spin.setValue(999999999)
            self.turnover_min_spin.setValue(0)
            self.turnover_max_spin.setValue(100)

            # 清空结果
            self.result_table.setRowCount(0)
            self.result_label.setText("共找到 0 只股票")

        except Exception as e:
            logger.error(f"Failed to reset conditions: {e}")

    def closeEvent(self, event):
        """关闭事件处理"""
        try:
            # 停止搜索线程
            if self.search_worker and self.search_worker.isRunning():
                self.search_worker.quit()
                self.search_worker.wait()

            event.accept()
        except Exception as e:
            logger.error(f"Failed to close dialog: {e}")
            event.accept()
