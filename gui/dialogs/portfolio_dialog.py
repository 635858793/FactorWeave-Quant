#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投资组合管理对话框

提供完整的投资组合管理功能，包括持仓管理、收益分析、风险评估等
"""

from loguru import logger
import sys
import os
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QDateEdit,
    QFrame, QSplitter, QScrollArea, QGroupBox,
    QProgressBar, QMessageBox, QHeaderView, QSpinBox,
    QDoubleSpinBox, QCheckBox, QWidget, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QDate, QTimer
from PyQt5.QtGui import QFont, QPixmap, QPalette

from gui.dialogs.base_dialog import BaseDialog


class PortfolioService:
    """投资组合服务（桩类，待后续实现）"""

    def __init__(self):
        pass


class PortfolioAnalyzer:
    """投资组合分析器（桩类，待后续实现）"""

    def __init__(self):
        pass


class PortfolioDialog(BaseDialog):
    """投资组合管理对话框"""
    
    portfolio_changed = pyqtSignal(str)
    stock_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        初始化投资组合管理对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(
            parent,
            title="投资组合管理",
            min_size=(1000, 700),
            size=(1100, 800),
            settings_key="PortfolioDialog"
        )
        
        self.logger = logger
        self.portfolio_service = PortfolioService()
        self.portfolio_analyzer = PortfolioAnalyzer()
        self.current_portfolio = None
        self.selected_holdings = []
        self.update_timer = QTimer()
        
        self.init_ui()
        self._connect_signals()
        self.load_portfolios()
        self._start_auto_refresh()

    def _connect_signals(self):
        """连接信号"""
        pass

    def _start_auto_refresh(self):
        """启动自动刷新"""
        pass

    def init_ui(self):
        """初始化用户界面"""
        try:
            # 主布局
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)

            # 创建工具栏
            self.create_toolbar()
            main_layout.addWidget(self.toolbar_frame)

            # 创建内容区域
            content_splitter = QSplitter(Qt.Horizontal)

            # 左侧组合列表
            self.create_portfolio_list()
            content_splitter.addWidget(self.portfolio_frame)

            # 右侧详情区域
            self.create_detail_area()
            content_splitter.addWidget(self.detail_widget)

            # 设置分割比例
            content_splitter.setSizes([300, 900])
            main_layout.addWidget(content_splitter)

            # 创建底部按钮
            self.create_buttons()
            main_layout.addWidget(self.button_frame)

        except Exception as e:
            self.logger.error(f"初始化UI失败: {e}")
            self.logger.error(traceback.format_exc())

    def create_toolbar(self):
        """创建工具栏"""
        try:
            self.toolbar_frame = QFrame()
            self.toolbar_frame.setFrameStyle(QFrame.StyledPanel)
            self.toolbar_frame.setMaximumHeight(50)

            layout = QHBoxLayout(self.toolbar_frame)
            layout.setContentsMargins(10, 5, 10, 5)

            # 新建组合按钮
            self.new_portfolio_btn = QPushButton("新建组合")
            self.new_portfolio_btn.clicked.connect(self.create_new_portfolio)
            layout.addWidget(self.new_portfolio_btn)

            # 导入组合按钮
            self.import_btn = QPushButton("导入组合")
            self.import_btn.clicked.connect(self.import_portfolio)
            layout.addWidget(self.import_btn)

            # 导出组合按钮
            self.export_btn = QPushButton("导出组合")
            self.export_btn.clicked.connect(self.export_portfolio)
            layout.addWidget(self.export_btn)

            layout.addStretch()

            # 刷新按钮
            self.refresh_btn = QPushButton("刷新")
            self.refresh_btn.clicked.connect(self.refresh_data)
            layout.addWidget(self.refresh_btn)

        except Exception as e:
            self.logger.error(f"创建工具栏失败: {e}")

    def create_portfolio_list(self):
        """创建组合列表"""
        try:
            self.portfolio_frame = QFrame()
            self.portfolio_frame.setFrameStyle(QFrame.StyledPanel)

            layout = QVBoxLayout(self.portfolio_frame)
            layout.setContentsMargins(5, 5, 5, 5)

            # 标题
            title_label = QLabel("投资组合")
            title_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #333;")
            layout.addWidget(title_label)

            # 组合列表
            self.portfolio_list = QTableWidget()
            self.portfolio_list.setColumnCount(3)
            self.portfolio_list.setHorizontalHeaderLabels(
                ['组合名称', '总市值', '收益率'])

            # 设置表格样式
            header = self.portfolio_list.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

            self.portfolio_list.setSelectionBehavior(QTableWidget.SelectRows)
            self.portfolio_list.itemSelectionChanged.connect(
                self.on_portfolio_selected)

            layout.addWidget(self.portfolio_list)

        except Exception as e:
            self.logger.error(f"创建组合列表失败: {e}")

    def create_detail_area(self):
        """创建详情区域"""
        try:
            self.detail_widget = QTabWidget()

            # 持仓明细标签页
            self.create_holdings_tab()
            self.detail_widget.addTab(self.holdings_tab, "持仓明细")

            # 收益分析标签页
            self.create_performance_tab()
            self.detail_widget.addTab(self.performance_tab, "收益分析")

            # 风险分析标签页
            self.create_risk_tab()
            self.detail_widget.addTab(self.risk_tab, "风险分析")

            # 交易记录标签页
            self.create_transactions_tab()
            self.detail_widget.addTab(self.transactions_tab, "交易记录")

        except Exception as e:
            self.logger.error(f"创建详情区域失败: {e}")

    def create_holdings_tab(self):
        """创建持仓明细标签页"""
        try:
            self.holdings_tab = QWidget()
            layout = QVBoxLayout(self.holdings_tab)

            # 操作按钮
            btn_layout = QHBoxLayout()

            self.add_holding_btn = QPushButton("添加持仓")
            self.add_holding_btn.clicked.connect(self.add_holding)
            btn_layout.addWidget(self.add_holding_btn)

            self.edit_holding_btn = QPushButton("编辑持仓")
            self.edit_holding_btn.clicked.connect(self.edit_holding)
            btn_layout.addWidget(self.edit_holding_btn)

            self.remove_holding_btn = QPushButton("删除持仓")
            self.remove_holding_btn.clicked.connect(self.remove_holding)
            btn_layout.addWidget(self.remove_holding_btn)

            btn_layout.addStretch()

            self.update_prices_btn = QPushButton("更新价格")
            self.update_prices_btn.clicked.connect(self.update_prices)
            btn_layout.addWidget(self.update_prices_btn)

            layout.addLayout(btn_layout)

            # 持仓表格
            self.holdings_table = QTableWidget()
            self.holdings_table.setColumnCount(10)
            self.holdings_table.setHorizontalHeaderLabels([
                '股票代码', '股票名称', '持仓数量', '成本价格', '当前价格',
                '市值', '成本', '盈亏', '盈亏率', '权重'
            ])

            # 设置表格样式
            header = self.holdings_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeToContents)

            self.holdings_table.setSelectionBehavior(QTableWidget.SelectRows)
            self.holdings_table.itemDoubleClicked.connect(
                self.on_holding_double_clicked)

            layout.addWidget(self.holdings_table)

            # 汇总信息
            summary_frame = QFrame()
            summary_frame.setFrameStyle(QFrame.StyledPanel)
            summary_frame.setMaximumHeight(80)

            summary_layout = QGridLayout(summary_frame)

            # 汇总标签
            self.total_value_label = QLabel("总市值: --")
            self.total_cost_label = QLabel("总成本: --")
            self.total_profit_label = QLabel("总盈亏: --")
            self.total_return_label = QLabel("总收益率: --")

            summary_layout.addWidget(self.total_value_label, 0, 0)
            summary_layout.addWidget(self.total_cost_label, 0, 1)
            summary_layout.addWidget(self.total_profit_label, 1, 0)
            summary_layout.addWidget(self.total_return_label, 1, 1)

            layout.addWidget(summary_frame)

        except Exception as e:
            self.logger.error(f"创建持仓明细标签页失败: {e}")

    def create_performance_tab(self):
        """创建收益分析标签页"""
        try:
            self.performance_tab = QWidget()
            layout = QVBoxLayout(self.performance_tab)

            # 性能指标
            metrics_group = QGroupBox("性能指标")
            metrics_layout = QGridLayout(metrics_group)

            self.performance_labels = {}
            metrics = [
                ('总收益率', 'total_return'),
                ('年化收益率', 'annual_return'),
                ('最大回撤', 'max_drawdown'),
                ('夏普比率', 'sharpe_ratio'),
                ('波动率', 'volatility'),
                ('胜率', 'win_rate')
            ]

            for i, (name, key) in enumerate(metrics):
                label = QLabel(f"{name}:")
                value_label = QLabel("--")
                value_label.setStyleSheet("font-weight: bold; color: #333;")

                metrics_layout.addWidget(label, i // 2, (i % 2) * 2)
                metrics_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)

                self.performance_labels[key] = value_label

            layout.addWidget(metrics_group)

            # 收益图表区域（占位）
            chart_group = QGroupBox("收益曲线")
            chart_layout = QVBoxLayout(chart_group)

            self.performance_chart_label = QLabel("收益曲线图表区域")
            self.performance_chart_label.setAlignment(Qt.AlignCenter)
            self.performance_chart_label.setStyleSheet(
                "border: 1px dashed #ccc; min-height: 300px;")
            chart_layout.addWidget(self.performance_chart_label)

            layout.addWidget(chart_group)

        except Exception as e:
            self.logger.error(f"创建收益分析标签页失败: {e}")

    def create_risk_tab(self):
        """创建风险分析标签页"""
        try:
            self.risk_tab = QWidget()
            layout = QVBoxLayout(self.risk_tab)

            # 风险指标
            risk_group = QGroupBox("风险指标")
            risk_layout = QGridLayout(risk_group)

            self.risk_labels = {}
            risk_metrics = [
                ('VaR(95%)', 'var_95'),
                ('CVaR(95%)', 'cvar_95'),
                ('Beta系数', 'beta'),
                ('相关系数', 'correlation'),
                ('跟踪误差', 'tracking_error'),
                ('信息比率', 'information_ratio')
            ]

            for i, (name, key) in enumerate(risk_metrics):
                label = QLabel(f"{name}:")
                value_label = QLabel("--")
                value_label.setStyleSheet("font-weight: bold; color: #333;")

                risk_layout.addWidget(label, i // 2, (i % 2) * 2)
                risk_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)

                self.risk_labels[key] = value_label

            layout.addWidget(risk_group)

            # 行业分布
            sector_group = QGroupBox("行业分布")
            sector_layout = QVBoxLayout(sector_group)

            self.sector_table = QTableWidget()
            self.sector_table.setColumnCount(3)
            self.sector_table.setHorizontalHeaderLabels(['行业', '权重', '收益贡献'])

            header = self.sector_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            sector_layout.addWidget(self.sector_table)
            layout.addWidget(sector_group)

        except Exception as e:
            self.logger.error(f"创建风险分析标签页失败: {e}")

    def create_transactions_tab(self):
        """创建交易记录标签页"""
        try:
            self.transactions_tab = QWidget()
            layout = QVBoxLayout(self.transactions_tab)

            # 操作按钮
            btn_layout = QHBoxLayout()

            self.add_transaction_btn = QPushButton("添加交易")
            self.add_transaction_btn.clicked.connect(self.add_transaction)
            btn_layout.addWidget(self.add_transaction_btn)

            self.edit_transaction_btn = QPushButton("编辑交易")
            self.edit_transaction_btn.clicked.connect(self.edit_transaction)
            btn_layout.addWidget(self.edit_transaction_btn)

            self.remove_transaction_btn = QPushButton("删除交易")
            self.remove_transaction_btn.clicked.connect(
                self.remove_transaction)
            btn_layout.addWidget(self.remove_transaction_btn)

            btn_layout.addStretch()

            layout.addLayout(btn_layout)

            # 交易记录表格
            self.transactions_table = QTableWidget()
            self.transactions_table.setColumnCount(8)
            self.transactions_table.setHorizontalHeaderLabels([
                '日期', '股票代码', '股票名称', '交易类型', '数量', '价格', '金额', '备注'
            ])

            # 设置表格样式
            header = self.transactions_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeToContents)

            self.transactions_table.setSelectionBehavior(
                QTableWidget.SelectRows)

            layout.addWidget(self.transactions_table)

        except Exception as e:
            self.logger.error(f"创建交易记录标签页失败: {e}")

    def create_buttons(self):
        """创建底部按钮"""
        try:
            self.button_frame = QFrame()
            layout = QHBoxLayout(self.button_frame)
            layout.setContentsMargins(10, 5, 10, 5)

            # 保存按钮
            self.save_btn = QPushButton("保存")
            self.save_btn.clicked.connect(self.save_portfolio)
            layout.addWidget(self.save_btn)

            layout.addStretch()

            # 关闭按钮
            self.close_btn = QPushButton("关闭")
            self.close_btn.clicked.connect(self.close)
            layout.addWidget(self.close_btn)

        except Exception as e:
            self.logger.error(f"创建底部按钮失败: {e}")

    def load_portfolios(self):
        """加载投资组合列表"""
        try:
            # 模拟加载组合数据
            self.portfolios = {
                "默认组合": {
                    "name": "默认组合",
                    "total_value": 100000,
                    "total_return": 0.15,
                    "holdings": [
                        {
                            "code": "000001",
                            "name": "平安银行",
                            "quantity": 1000,
                            "cost_price": 10.0,
                            "current_price": 11.5
                        }
                    ]
                }
            }

            self.update_portfolio_list()

        except Exception as e:
            self.logger.error(f"加载投资组合失败: {e}")

    def update_portfolio_list(self):
        """更新组合列表显示"""
        try:
            self.portfolio_list.setRowCount(len(self.portfolios))

            for i, (name, portfolio) in enumerate(self.portfolios.items()):
                self.portfolio_list.setItem(i, 0, QTableWidgetItem(name))
                self.portfolio_list.setItem(i, 1, QTableWidgetItem(
                    f"{portfolio.get('total_value', 0):,.2f}"))

                total_return = portfolio.get('total_return', 0)
                return_text = f"{total_return * 100:.2f}%"
                return_item = QTableWidgetItem(return_text)

                # 设置颜色
                if total_return > 0:
                    return_item.setBackground(Qt.red)
                elif total_return < 0:
                    return_item.setBackground(Qt.green)

                self.portfolio_list.setItem(i, 2, return_item)

        except Exception as e:
            self.logger.error(f"更新组合列表失败: {e}")

    def on_portfolio_selected(self):
        """组合选择事件"""
        try:
            current_row = self.portfolio_list.currentRow()
            if current_row >= 0:
                portfolio_name = self.portfolio_list.item(
                    current_row, 0).text()
                self.current_portfolio = self.portfolios.get(portfolio_name)

                if self.current_portfolio:
                    self.update_holdings_display()
                    self.update_performance_display()
                    self.update_risk_display()
                    self.update_transactions_display()

        except Exception as e:
            self.logger.error(f"处理组合选择失败: {e}")

    def update_holdings_display(self):
        """更新持仓显示"""
        try:
            if not self.current_portfolio:
                return

            holdings = self.current_portfolio.get('holdings', [])
            self.holdings_table.setRowCount(len(holdings))

            total_value = 0
            total_cost = 0

            for i, holding in enumerate(holdings):
                code = holding.get('code', '')
                name = holding.get('name', '')
                quantity = holding.get('quantity', 0)
                cost_price = holding.get('cost_price', 0)
                current_price = holding.get('current_price', 0)

                market_value = quantity * current_price
                cost_value = quantity * cost_price
                profit = market_value - cost_value
                profit_rate = (profit / cost_value *
                               100) if cost_value > 0 else 0

                total_value += market_value
                total_cost += cost_value

                self.holdings_table.setItem(i, 0, QTableWidgetItem(code))
                self.holdings_table.setItem(i, 1, QTableWidgetItem(name))
                self.holdings_table.setItem(
                    i, 2, QTableWidgetItem(str(quantity)))
                self.holdings_table.setItem(
                    i, 3, QTableWidgetItem(f"{cost_price:.2f}"))
                self.holdings_table.setItem(
                    i, 4, QTableWidgetItem(f"{current_price:.2f}"))
                self.holdings_table.setItem(
                    i, 5, QTableWidgetItem(f"{market_value:.2f}"))
                self.holdings_table.setItem(
                    i, 6, QTableWidgetItem(f"{cost_value:.2f}"))
                self.holdings_table.setItem(
                    i, 7, QTableWidgetItem(f"{profit:.2f}"))
                self.holdings_table.setItem(
                    i, 8, QTableWidgetItem(f"{profit_rate:.2f}%"))

                weight = (market_value / total_value *
                          100) if total_value > 0 else 0
                self.holdings_table.setItem(
                    i, 9, QTableWidgetItem(f"{weight:.2f}%"))

            # 更新汇总信息
            total_profit = total_value - total_cost
            total_return = (total_profit / total_cost *
                            100) if total_cost > 0 else 0

            self.total_value_label.setText(f"总市值: {total_value:,.2f}")
            self.total_cost_label.setText(f"总成本: {total_cost:,.2f}")
            self.total_profit_label.setText(f"总盈亏: {total_profit:,.2f}")
            self.total_return_label.setText(f"总收益率: {total_return:.2f}%")

        except Exception as e:
            self.logger.error(f"更新持仓显示失败: {e}")

    def update_performance_display(self):
        """更新收益分析显示"""
        try:
            if not self.current_portfolio:
                return

            # 模拟性能数据
            performance_data = {
                'total_return': 15.25,
                'annual_return': 12.80,
                'max_drawdown': -8.50,
                'sharpe_ratio': 1.35,
                'volatility': 18.60,
                'win_rate': 65.20
            }

            for key, value in performance_data.items():
                if key in self.performance_labels:
                    if key in ['total_return', 'annual_return', 'max_drawdown', 'volatility', 'win_rate']:
                        self.performance_labels[key].setText(f"{value:.2f}%")
                    else:
                        self.performance_labels[key].setText(f"{value:.2f}")

        except Exception as e:
            self.logger.error(f"更新收益分析显示失败: {e}")

    def update_risk_display(self):
        """更新风险分析显示"""
        try:
            if not self.current_portfolio:
                return

            # 模拟风险数据
            risk_data = {
                'var_95': -5.20,
                'cvar_95': -7.80,
                'beta': 1.15,
                'correlation': 0.85,
                'tracking_error': 3.20,
                'information_ratio': 0.45
            }

            for key, value in risk_data.items():
                if key in self.risk_labels:
                    if key in ['var_95', 'cvar_95', 'tracking_error']:
                        self.risk_labels[key].setText(f"{value:.2f}%")
                    else:
                        self.risk_labels[key].setText(f"{value:.2f}")

            # 更新行业分布
            sector_data = [
                ("银行", "25.0%", "3.2%"),
                ("科技", "30.0%", "4.8%"),
                ("消费", "20.0%", "2.1%"),
                ("医药", "15.0%", "1.8%"),
                ("其他", "10.0%", "0.8%")
            ]

            self.sector_table.setRowCount(len(sector_data))
            for i, (sector, weight, contribution) in enumerate(sector_data):
                self.sector_table.setItem(i, 0, QTableWidgetItem(sector))
                self.sector_table.setItem(i, 1, QTableWidgetItem(weight))
                self.sector_table.setItem(i, 2, QTableWidgetItem(contribution))

        except Exception as e:
            self.logger.error(f"更新风险分析显示失败: {e}")

    def update_transactions_display(self):
        """更新交易记录显示"""
        try:
            if not self.current_portfolio:
                return

            # 模拟交易记录
            transactions = [
                ("2023-01-15", "000001", "平安银行", "买入",
                 "1000", "10.00", "10000.00", "建仓"),
                ("2023-03-20", "000002", "万科A", "买入",
                 "500", "20.00", "10000.00", ""),
                ("2023-06-10", "000001", "平安银行", "卖出",
                 "200", "11.50", "2300.00", "减仓")
            ]

            self.transactions_table.setRowCount(len(transactions))
            for i, transaction in enumerate(transactions):
                for j, value in enumerate(transaction):
                    self.transactions_table.setItem(
                        i, j, QTableWidgetItem(str(value)))

        except Exception as e:
            self.logger.error(f"更新交易记录显示失败: {e}")

    def create_new_portfolio(self):
        """创建新组合"""
        try:
            name, ok = QInputDialog.getText(self, "新建组合", "请输入组合名称:")
            if ok and name:
                if name not in self.portfolios:
                    self.portfolios[name] = {
                        "name": name,
                        "total_value": 0,
                        "total_return": 0,
                        "holdings": []
                    }
                    self.update_portfolio_list()
                    self.logger.info(f"创建新组合: {name}")
                else:
                    QMessageBox.warning(self, "警告", "组合名称已存在！")

        except Exception as e:
            self.logger.error(f"创建新组合失败: {e}")

    def add_holding(self):
        """添加持仓"""
        try:
            if not self.current_portfolio:
                QMessageBox.warning(self, "警告", "请先选择一个组合！")
                return

            # 这里应该打开添加持仓对话框
            QMessageBox.information(self, "提示", "添加持仓功能待实现")

        except Exception as e:
            self.logger.error(f"添加持仓失败: {e}")

    def edit_holding(self):
        """编辑持仓"""
        try:
            current_row = self.holdings_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(self, "警告", "请先选择一个持仓！")
                return

            QMessageBox.information(self, "提示", "编辑持仓功能待实现")

        except Exception as e:
            self.logger.error(f"编辑持仓失败: {e}")

    def remove_holding(self):
        """删除持仓"""
        try:
            current_row = self.holdings_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(self, "警告", "请先选择一个持仓！")
                return

            reply = QMessageBox.question(self, "确认", "确定要删除选中的持仓吗？")
            if reply == QMessageBox.Yes:
                # 删除持仓逻辑
                QMessageBox.information(self, "提示", "删除持仓功能待实现")

        except Exception as e:
            self.logger.error(f"删除持仓失败: {e}")

    def add_transaction(self):
        """添加交易记录"""
        try:
            if not self.current_portfolio:
                QMessageBox.warning(self, "警告", "请先选择一个组合！")
                return

            QMessageBox.information(self, "提示", "添加交易功能待实现")

        except Exception as e:
            self.logger.error(f"添加交易失败: {e}")

    def edit_transaction(self):
        """编辑交易记录"""
        try:
            current_row = self.transactions_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(self, "警告", "请先选择一个交易记录！")
                return

            QMessageBox.information(self, "提示", "编辑交易功能待实现")

        except Exception as e:
            self.logger.error(f"编辑交易失败: {e}")

    def remove_transaction(self):
        """删除交易记录"""
        try:
            current_row = self.transactions_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(self, "警告", "请先选择一个交易记录！")
                return

            reply = QMessageBox.question(self, "确认", "确定要删除选中的交易记录吗？")
            if reply == QMessageBox.Yes:
                QMessageBox.information(self, "提示", "删除交易功能待实现")

        except Exception as e:
            self.logger.error(f"删除交易失败: {e}")

    def update_prices(self):
        """更新价格"""
        try:
            QMessageBox.information(self, "提示", "更新价格功能待实现")

        except Exception as e:
            self.logger.error(f"更新价格失败: {e}")

    def import_portfolio(self):
        """导入组合"""
        try:
            QMessageBox.information(self, "提示", "导入组合功能待实现")

        except Exception as e:
            self.logger.error(f"导入组合失败: {e}")

    def export_portfolio(self):
        """导出组合"""
        try:
            QMessageBox.information(self, "提示", "导出组合功能待实现")

        except Exception as e:
            self.logger.error(f"导出组合失败: {e}")

    def refresh_data(self):
        """刷新数据"""
        try:
            self.load_portfolios()
            if self.current_portfolio:
                self.update_holdings_display()
                self.update_performance_display()
                self.update_risk_display()
                self.update_transactions_display()

        except Exception as e:
            self.logger.error(f"刷新数据失败: {e}")

    def save_portfolio(self):
        """保存组合"""
        try:
            QMessageBox.information(self, "提示", "组合已保存")

        except Exception as e:
            self.logger.error(f"保存组合失败: {e}")

    def on_holding_double_clicked(self, item):
        """持仓双击事件"""
        try:
            row = item.row()
            code_item = self.holdings_table.item(row, 0)
            if code_item:
                stock_code = code_item.text()
                self.stock_selected.emit(stock_code)

        except Exception as e:
            self.logger.error(f"处理持仓双击失败: {e}")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 测试对话框
    dialog = PortfolioDialog()
    dialog.show()

    sys.exit(app.exec_())
