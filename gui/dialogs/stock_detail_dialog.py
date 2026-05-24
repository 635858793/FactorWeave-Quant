#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票详情对话框

显示股票的详细信息，包括基本信息、财务数据、技术指标等
"""

from loguru import logger
import sys
import os
import traceback
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QDateEdit,
    QFrame, QSplitter, QScrollArea, QGroupBox,
    QProgressBar, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QDate, QTimer
from PyQt5.QtGui import QFont, QPixmap, QPalette

from gui.dialogs.base_dialog import BaseDialog

class StockDataWorker(QThread):
    """股票数据获取工作线程"""

    data_loaded = pyqtSignal(dict)  # 数据加载完成
    error_occurred = pyqtSignal(str)  # 发生错误
    progress_updated = pyqtSignal(int)  # 进度更新

    def __init__(self, stock_code: str, data_manager=None):
        super().__init__()
        self.stock_code = stock_code
        self.data_manager = data_manager
        self.logger = logger.bind(module=__name__)

    def run(self):
        """运行数据获取任务"""
        try:
            if not self.data_manager:
                self.error_occurred.emit("数据管理器未设置")
                return

            result = {}
            total_steps = 6
            current_step = 0

            # 1. 基本信息
            self.progress_updated.emit(int(current_step * 100 / total_steps))
            basic_info = self.get_basic_info()
            result['basic_info'] = basic_info
            current_step += 1

            # 2. K线数据
            self.progress_updated.emit(int(current_step * 100 / total_steps))
            kdata = self.get_kdata()
            result['kdata'] = kdata
            current_step += 1

            # 3. 财务数据
            self.progress_updated.emit(int(current_step * 100 / total_steps))
            finance_data = self.get_finance_data()
            result['finance_data'] = finance_data
            current_step += 1

            # 4. 技术指标
            self.progress_updated.emit(int(current_step * 100 / total_steps))
            indicators = self.get_indicators()
            result['indicators'] = indicators
            current_step += 1

            # 5. 历史统计
            self.progress_updated.emit(int(current_step * 100 / total_steps))
            statistics = self.get_statistics()
            result['statistics'] = statistics
            current_step += 1

            # 6. 相关股票
            self.progress_updated.emit(int(current_step * 100 / total_steps))
            related_stocks = self.get_related_stocks()
            result['related_stocks'] = related_stocks
            current_step += 1

            self.progress_updated.emit(100)
            self.data_loaded.emit(result)

        except Exception as e:
            self.logger.error(f"获取股票数据失败: {e}")
            self.error_occurred.emit(str(e))

    def get_basic_info(self) -> Dict[str, Any]:
        try:
            info = {
                'code': self.stock_code,
                'market': '深圳' if self.stock_code.startswith('00') else '上海',
            }

            try:
                from core.real_data_provider import get_real_data_provider
                provider = get_real_data_provider()
                quote = provider.get_real_quote(self.stock_code)
                if quote:
                    info['name'] = quote.get('name', '')
                    info['price'] = quote.get('price', 0)
                    info['change_pct'] = quote.get('change_pct', 0)
                    info['change'] = quote.get('change', 0)
                    info['volume'] = quote.get('volume', 0)
                    info['amount'] = quote.get('amount', 0)
                    cap = quote.get('market_cap') or quote.get('total_market_cap', 0)
                    if cap:
                        info['market_cap'] = cap
            except Exception as e:
                self.logger.warning(f"获取实时行情失败: {e}")

            if self.data_manager and hasattr(self.data_manager, 'get_stock_info'):
                real_info = self.data_manager.get_stock_info(self.stock_code)
                if real_info:
                    for key, value in real_info.items():
                        if value is not None and value != '':
                            info[key] = value
            elif self.data_manager and hasattr(self.data_manager, 'get_stock_list'):
                stock_list = self.data_manager.get_stock_list()
                for stock in stock_list:
                    s_code = stock.get('code') if isinstance(stock, dict) else getattr(stock, 'code', None)
                    if s_code == self.stock_code:
                        if isinstance(stock, dict):
                            for key, value in stock.items():
                                if value is not None and value != '':
                                    info[key] = value
                        else:
                            for attr in ['name', 'industry', 'market', 'pe_ratio', 'pb_ratio']:
                                val = getattr(stock, attr, None)
                                if val is not None and val != '':
                                    info[attr] = val
                        break

            return info

        except Exception as e:
            self.logger.error(f"获取基本信息失败: {e}")
            return {}

    def get_kdata(self) -> Dict[str, Any]:
        """获取K线数据"""
        try:
            result = {}

            # 获取不同周期的K线数据
            periods = ['1min', '5min', '15min',
                       '30min', '60min', 'D', 'W', 'M']
            for period in periods:
                try:
                    if self.data_manager and hasattr(self.data_manager, 'get_kdata'):
                        kdata = self.data_manager.get_kdata(
                            self.stock_code, period)
                        if kdata is not None and not kdata.empty:
                            result[period] = {
                                'count': len(kdata),
                                'start_date': str(kdata.index[0]) if len(kdata) > 0 else '',
                                'end_date': str(kdata.index[-1]) if len(kdata) > 0 else '',
                                'latest_price': float(kdata['close'].iloc[-1]) if len(kdata) > 0 else 0,
                                'latest_volume': float(kdata['volume'].iloc[-1]) if len(kdata) > 0 else 0
                            }
                except Exception as e:
                    self.logger.warning(f"获取{period}周期数据失败: {e}")
                    continue

            return result

        except Exception as e:
            self.logger.error(f"获取K线数据失败: {e}")
            return {}

    def get_finance_data(self) -> Dict[str, Any]:
        try:
            if self.data_manager and hasattr(self.data_manager, 'get_finance_data'):
                real_data = self.data_manager.get_finance_data(self.stock_code)
                if real_data:
                    return real_data

            return {}

        except Exception as e:
            self.logger.error(f"获取财务数据失败: {e}")
            return {}

    def get_indicators(self) -> Dict[str, Any]:
        try:
            try:
                from core.real_data_provider import get_real_data_provider
                provider = get_real_data_provider()
                kdata = provider.get_real_kdata(code=self.stock_code, freq='D', count=250)
                if kdata is not None and not kdata.empty and 'close' in kdata.columns:
                    close = kdata['close'].astype(float)
                    high = kdata.get('high', close).astype(float)
                    low = kdata.get('low', close).astype(float)
                    volume = kdata.get('volume', pd.Series(0, index=close.index)).astype(float)

                    indicators = {}

                    for period in [5, 10, 20, 60]:
                        ma = close.rolling(window=min(period, len(close))).mean()
                        val = ma.iloc[-1]
                        indicators[f'ma{period}'] = float(val) if not pd.isna(val) else 0.0

                    delta = close.diff()
                    gain = delta.where(delta > 0, 0.0).rolling(window=14, min_periods=1).mean()
                    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14, min_periods=1).mean()
                    rs = gain / loss.replace(0, float('nan'))
                    rsi = 100.0 - (100.0 / (1.0 + rs))
                    indicators['rsi'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 0.0

                    ema12 = close.ewm(span=12, adjust=False).mean()
                    ema26 = close.ewm(span=26, adjust=False).mean()
                    macd_line = ema12 - ema26
                    signal_line = macd_line.ewm(span=9, adjust=False).mean()
                    macd_hist = macd_line - signal_line
                    indicators['macd'] = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else 0.0

                    low_min = low.rolling(window=9, min_periods=1).min()
                    high_max = high.rolling(window=9, min_periods=1).max()
                    h_l_diff = (high_max - low_min).replace(0, float('nan'))
                    rsv = (close - low_min) / h_l_diff * 100.0
                    k = rsv.ewm(com=2, adjust=False).mean()
                    d = k.ewm(com=2, adjust=False).mean()
                    indicators['kdj_k'] = float(k.iloc[-1]) if not pd.isna(k.iloc[-1]) else 0.0
                    indicators['kdj_d'] = float(d.iloc[-1]) if not pd.isna(d.iloc[-1]) else 0.0

                    ma20 = close.rolling(window=min(20, len(close))).mean()
                    std20 = close.rolling(window=min(20, len(close))).std()
                    indicators['boll_upper'] = float((ma20 + 2 * std20).iloc[-1]) if not pd.isna(ma20.iloc[-1]) else 0.0
                    indicators['boll_lower'] = float((ma20 - 2 * std20).iloc[-1]) if not pd.isna(ma20.iloc[-1]) else 0.0

                    vol_ma5 = volume.rolling(window=5, min_periods=1).mean()
                    if vol_ma5.iloc[-1] and vol_ma5.iloc[-1] > 0:
                        indicators['volume_ratio'] = float(volume.iloc[-1] / vol_ma5.iloc[-1])
                    else:
                        indicators['volume_ratio'] = 0.0

                    if 'turnover_rate' in kdata.columns:
                        val = kdata['turnover_rate'].iloc[-1]
                        indicators['turnover_rate'] = float(val) if not pd.isna(val) else 0.0
                    elif 'turn' in kdata.columns:
                        val = kdata['turn'].iloc[-1]
                        indicators['turnover_rate'] = float(val) if not pd.isna(val) else 0.0
                    else:
                        indicators['turnover_rate'] = 0.0

                    return indicators
            except Exception as e:
                self.logger.warning(f"使用RealDataProvider计算技术指标失败: {e}")

            return {}

        except Exception as e:
            self.logger.error(f"获取技术指标失败: {e}")
            return {}

    def get_statistics(self) -> Dict[str, Any]:
        """获取历史统计数据"""
        try:
            # 模拟统计数据
            statistics = {
                'max_price_52w': 12.5,
                'min_price_52w': 8.2,
                'avg_volume_20d': 50000000,
                'price_change_1d': 0.02,
                'price_change_5d': 0.05,
                'price_change_20d': 0.08,
                'price_change_60d': 0.12,
                'price_change_ytd': 0.15,
                'volatility_20d': 0.025,
                'beta': 1.2,
                'amplitude_20d': 0.08
            }

            return statistics

        except Exception as e:
            self.logger.error(f"获取统计数据失败: {e}")
            return {}

    def get_related_stocks(self) -> List[Dict[str, Any]]:
        try:
            related = []

            if self.data_manager:
                try:
                    if hasattr(self.data_manager, 'get_stock_info'):
                        stock_info = self.data_manager.get_stock_info(self.stock_code)
                        industry = None
                        if isinstance(stock_info, dict):
                            industry = stock_info.get('industry')
                        elif stock_info is not None:
                            industry = getattr(stock_info, 'industry', None)

                        if industry:
                            if hasattr(self.data_manager, 'get_industry_stocks'):
                                industry_stocks = self.data_manager.get_industry_stocks(industry)
                                if industry_stocks:
                                    for s in industry_stocks:
                                        code = s.get('code', '') if isinstance(s, dict) else getattr(s, 'code', '')
                                        name = s.get('name', '') if isinstance(s, dict) else getattr(s, 'name', '')
                                        if code and code != self.stock_code:
                                            related.append({
                                                'code': code,
                                                'name': name or code,
                                                'correlation': 0.0
                                            })
                                            if len(related) >= 5:
                                                break

                    if not related and hasattr(self.data_manager, 'get_stock_list'):
                        stock_list = self.data_manager.get_stock_list()
                        for stock in stock_list:
                            code = stock.get('code', '') if isinstance(stock, dict) else getattr(stock, 'code', '')
                            name = stock.get('name', '') if isinstance(stock, dict) else getattr(stock, 'name', '')
                            if code and code != self.stock_code:
                                related.append({
                                    'code': code,
                                    'name': name or code,
                                    'correlation': 0.0
                                })
                            if len(related) >= 5:
                                break
                except Exception as e:
                    self.logger.warning(f"通过数据管理器获取关联股票失败: {e}")

            if not related:
                try:
                    from core.real_data_provider import get_real_data_provider
                    provider = get_real_data_provider()
                    stocks = provider.get_default_test_stocks(10)
                    for code in stocks:
                        if code != self.stock_code:
                            try:
                                quote = provider.get_real_quote(code)
                                name = quote.get('name', code) if quote else code
                            except Exception:
                                name = code
                            related.append({
                                'code': code,
                                'name': name,
                                'correlation': 0.0
                            })
                        if len(related) >= 5:
                            break
                except Exception as e:
                    self.logger.warning(f"通过RealDataProvider获取关联股票失败: {e}")

            return related[:5]

        except Exception as e:
            self.logger.error(f"获取相关股票失败: {e}")
            return []

class StockDetailDialog(BaseDialog):
    """股票详情对话框"""

    # 信号定义
    stock_selected = pyqtSignal(str)  # 股票选择
    data_export_requested = pyqtSignal(str, dict)  # 数据导出请求

    def __init__(self, stock_code: str, data_manager=None, parent=None):
        """
        初始化股票详情对话框

        Args:
            stock_code: 股票代码
            data_manager: 数据管理器
            parent: 父窗口
        """
        super().__init__(
            parent,
            title="股票详情",
            min_size=(1000, 700),
            size=(1100, 800),
            settings_key="StockDetailDialog"
        )
        
        self.stock_code = stock_code
        self.data_manager = data_manager
        self.logger = logger.bind(module=__name__)
        self.stock_data = {}

        # 工作线程
        self.data_worker = None

        self.init_ui()
        self.load_data()

        self.logger.info(f"股票详情对话框初始化完成: {stock_code}")

    def init_ui(self):
        """初始化用户界面"""
        try:
            # 主布局
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)

            # 创建头部信息
            self.create_header()
            main_layout.addWidget(self.header_frame)

            # 创建进度条
            self.progress_bar = QProgressBar()
            self.progress_bar.setVisible(False)
            main_layout.addWidget(self.progress_bar)

            # 创建标签页
            self.create_tabs()
            main_layout.addWidget(self.tab_widget)

            # 创建底部按钮
            self.create_buttons()
            main_layout.addWidget(self.button_frame)

        except Exception as e:
            self.logger.error(f"初始化UI失败: {e}")
            self.logger.error(traceback.format_exc())

    def create_header(self):
        """创建头部信息"""
        try:
            self.header_frame = QFrame()
            self.header_frame.setFrameStyle(QFrame.StyledPanel)
            self.header_frame.setMaximumHeight(100)

            layout = QHBoxLayout(self.header_frame)
            layout.setContentsMargins(15, 10, 15, 10)

            # 左侧基本信息
            left_layout = QVBoxLayout()

            # 股票代码和名称
            title_layout = QHBoxLayout()
            self.code_label = QLabel(self.stock_code)
            self.code_label.setStyleSheet(
                "font-size: 18px; font-weight: bold; color: #2E86AB;")
            title_layout.addWidget(self.code_label)

            self.name_label = QLabel("加载中...")
            self.name_label.setStyleSheet("font-size: 16px; color: #333;")
            title_layout.addWidget(self.name_label)
            title_layout.addStretch()
            left_layout.addLayout(title_layout)

            # 基本信息
            info_layout = QHBoxLayout()
            self.market_label = QLabel("市场: --")
            self.industry_label = QLabel("行业: --")
            self.listing_label = QLabel("上市日期: --")

            for label in [self.market_label, self.industry_label, self.listing_label]:
                label.setStyleSheet("color: #666; margin-right: 20px;")
                info_layout.addWidget(label)

            info_layout.addStretch()
            left_layout.addLayout(info_layout)

            layout.addLayout(left_layout)

            # 右侧价格信息
            right_layout = QVBoxLayout()

            price_layout = QHBoxLayout()
            self.price_label = QLabel("--")
            self.price_label.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #E74C3C;")
            price_layout.addWidget(self.price_label)

            self.change_label = QLabel("--")
            self.change_label.setStyleSheet("font-size: 14px; color: #E74C3C;")
            price_layout.addWidget(self.change_label)
            price_layout.addStretch()
            right_layout.addLayout(price_layout)

            # 市值信息
            cap_layout = QHBoxLayout()
            self.market_cap_label = QLabel("市值: --")
            self.pe_label = QLabel("PE: --")
            self.pb_label = QLabel("PB: --")

            for label in [self.market_cap_label, self.pe_label, self.pb_label]:
                label.setStyleSheet("color: #666; margin-right: 15px;")
                cap_layout.addWidget(label)

            cap_layout.addStretch()
            right_layout.addLayout(cap_layout)

            layout.addLayout(right_layout)

        except Exception as e:
            self.logger.error(f"创建头部信息失败: {e}")

    def create_tabs(self):
        """创建标签页"""
        try:
            self.tab_widget = QTabWidget()

            # 基本信息标签页
            self.create_basic_tab()
            self.tab_widget.addTab(self.basic_tab, "基本信息")

            # 财务数据标签页
            self.create_finance_tab()
            self.tab_widget.addTab(self.finance_tab, "财务数据")

            # 技术指标标签页
            self.create_indicator_tab()
            self.tab_widget.addTab(self.indicator_tab, "技术指标")

            # 数据统计标签页
            self.create_statistics_tab()
            self.tab_widget.addTab(self.statistics_tab, "数据统计")

            # 相关股票标签页
            self.create_related_tab()
            self.tab_widget.addTab(self.related_tab, "相关股票")

        except Exception as e:
            self.logger.error(f"创建标签页失败: {e}")

    def create_basic_tab(self):
        """创建基本信息标签页"""
        try:
            self.basic_tab = QWidget()
            layout = QVBoxLayout(self.basic_tab)

            # 创建滚动区域
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)

            content_widget = QWidget()
            content_layout = QGridLayout(content_widget)

            # 基本信息组
            basic_group = QGroupBox("基本信息")
            basic_layout = QGridLayout(basic_group)

            self.basic_info_labels = {}
            basic_fields = [
                ('股票代码', 'code'), ('股票名称', 'name'), ('所属市场', 'market'),
                ('所属行业', 'industry'), ('概念板块', 'concept'), ('上市日期', 'listing_date')
            ]

            for i, (label_text, field) in enumerate(basic_fields):
                label = QLabel(f"{label_text}:")
                value_label = QLabel("--")
                value_label.setStyleSheet("color: #333; font-weight: bold;")

                basic_layout.addWidget(label, i // 2, (i % 2) * 2)
                basic_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)

                self.basic_info_labels[field] = value_label

            content_layout.addWidget(basic_group, 0, 0)

            # 股本信息组
            share_group = QGroupBox("股本信息")
            share_layout = QGridLayout(share_group)

            share_fields = [
                ('总股本', 'total_share'), ('流通股本',
                                         'float_share'), ('总市值', 'market_cap'),
                ('市盈率', 'pe_ratio'), ('市净率', 'pb_ratio'), ('股息率', 'dividend_yield')
            ]

            for i, (label_text, field) in enumerate(share_fields):
                label = QLabel(f"{label_text}:")
                value_label = QLabel("--")
                value_label.setStyleSheet("color: #333; font-weight: bold;")

                share_layout.addWidget(label, i // 2, (i % 2) * 2)
                share_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)

                self.basic_info_labels[field] = value_label

            content_layout.addWidget(share_group, 0, 1)

            # 财务指标组
            financial_group = QGroupBox("关键财务指标")
            financial_layout = QGridLayout(financial_group)

            financial_fields = [
                ('净资产收益率', 'roe'), ('资产负债率', 'debt_ratio')
            ]

            for i, (label_text, field) in enumerate(financial_fields):
                label = QLabel(f"{label_text}:")
                value_label = QLabel("--")
                value_label.setStyleSheet("color: #333; font-weight: bold;")

                financial_layout.addWidget(label, i, 0)
                financial_layout.addWidget(value_label, i, 1)

                self.basic_info_labels[field] = value_label

            content_layout.addWidget(financial_group, 1, 0, 1, 2)

            scroll.setWidget(content_widget)
            layout.addWidget(scroll)

        except Exception as e:
            self.logger.error(f"创建基本信息标签页失败: {e}")

    def create_finance_tab(self):
        """创建财务数据标签页"""
        try:
            self.finance_tab = QWidget()
            layout = QVBoxLayout(self.finance_tab)

            # 财务数据表格
            self.finance_table = QTableWidget()
            self.finance_table.setColumnCount(5)
            self.finance_table.setHorizontalHeaderLabels(
                ['指标', '2023年', '2022年', '2021年', '2020年'])

            # 设置表格样式
            header = self.finance_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            layout.addWidget(self.finance_table)

        except Exception as e:
            self.logger.error(f"创建财务数据标签页失败: {e}")

    def create_indicator_tab(self):
        """创建技术指标标签页"""
        try:
            self.indicator_tab = QWidget()
            layout = QVBoxLayout(self.indicator_tab)

            # 技术指标表格
            self.indicator_table = QTableWidget()
            self.indicator_table.setColumnCount(2)
            self.indicator_table.setHorizontalHeaderLabels(['指标名称', '当前值'])

            # 设置表格样式
            header = self.indicator_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            layout.addWidget(self.indicator_table)

        except Exception as e:
            self.logger.error(f"创建技术指标标签页失败: {e}")

    def create_statistics_tab(self):
        """创建数据统计标签页"""
        try:
            self.statistics_tab = QWidget()
            layout = QVBoxLayout(self.statistics_tab)

            # 统计数据表格
            self.statistics_table = QTableWidget()
            self.statistics_table.setColumnCount(2)
            self.statistics_table.setHorizontalHeaderLabels(['统计项目', '数值'])

            # 设置表格样式
            header = self.statistics_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            layout.addWidget(self.statistics_table)

        except Exception as e:
            self.logger.error(f"创建数据统计标签页失败: {e}")

    def create_related_tab(self):
        """创建相关股票标签页"""
        try:
            self.related_tab = QWidget()
            layout = QVBoxLayout(self.related_tab)

            # 相关股票表格
            self.related_table = QTableWidget()
            self.related_table.setColumnCount(3)
            self.related_table.setHorizontalHeaderLabels(
                ['股票代码', '股票名称', '相关度'])

            # 设置表格样式
            header = self.related_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            # 双击事件
            self.related_table.itemDoubleClicked.connect(
                self.on_related_stock_clicked)

            layout.addWidget(self.related_table)

        except Exception as e:
            self.logger.error(f"创建相关股票标签页失败: {e}")

    def create_buttons(self):
        """创建底部按钮"""
        try:
            self.button_frame = QFrame()
            layout = QHBoxLayout(self.button_frame)
            layout.setContentsMargins(10, 5, 10, 5)

            # 刷新按钮
            self.refresh_btn = QPushButton("刷新数据")
            self.refresh_btn.clicked.connect(self.load_data)
            layout.addWidget(self.refresh_btn)

            # 导出按钮
            self.export_btn = QPushButton("导出数据")
            self.export_btn.clicked.connect(self.export_data)
            layout.addWidget(self.export_btn)

            layout.addStretch()

            # 关闭按钮
            self.close_btn = QPushButton("关闭")
            self.close_btn.clicked.connect(self.close)
            layout.addWidget(self.close_btn)

        except Exception as e:
            self.logger.error(f"创建底部按钮失败: {e}")

    def load_data(self):
        """加载股票数据"""
        try:
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.refresh_btn.setEnabled(False)

            # 创建工作线程
            self.data_worker = StockDataWorker(
                self.stock_code, self.data_manager)
            self.data_worker.data_loaded.connect(self.on_data_loaded)
            self.data_worker.error_occurred.connect(self.on_error_occurred)
            self.data_worker.progress_updated.connect(
                self.progress_bar.setValue)
            self.data_worker.finished.connect(self.on_loading_finished)

            # 启动线程
            self.data_worker.start()

        except Exception as e:
            self.logger.error(f"加载数据失败: {e}")
            self.on_error_occurred(str(e))

    def on_data_loaded(self, data: Dict[str, Any]):
        """数据加载完成事件"""
        try:
            self.stock_data = data

            # 更新头部信息
            self.update_header(data.get('basic_info', {}))

            # 更新各个标签页
            self.update_basic_info(data.get('basic_info', {}))
            self.update_finance_data(data.get('finance_data', {}))
            self.update_indicators(data.get('indicators', {}))
            self.update_statistics(data.get('statistics', {}))
            self.update_related_stocks(data.get('related_stocks', []))

            self.logger.info("股票数据更新完成")

        except Exception as e:
            self.logger.error(f"处理数据失败: {e}")

    def on_error_occurred(self, error_msg: str):
        """错误发生事件"""
        QMessageBox.warning(self, "错误", f"加载数据失败: {error_msg}")
        self.logger.error(f"数据加载错误: {error_msg}")

    def on_loading_finished(self):
        """加载完成事件"""
        self.progress_bar.setVisible(False)
        self.refresh_btn.setEnabled(True)
        if self.data_worker:
            self.data_worker.deleteLater()
            self.data_worker = None

    def update_header(self, basic_info: Dict[str, Any]):
        """更新头部信息"""
        try:
            if basic_info:
                self.name_label.setText(basic_info.get('name', '--'))
                self.market_label.setText(
                    f"市场: {basic_info.get('market', '--')}")
                self.industry_label.setText(
                    f"行业: {basic_info.get('industry', '--')}")
                self.listing_label.setText(
                    f"上市日期: {basic_info.get('listing_date', '--')}")

                # 更新价格信息（从K线数据获取）
                kdata = self.stock_data.get('kdata', {})
                if 'D' in kdata:
                    daily_data = kdata['D']
                    price = daily_data.get('latest_price', 0)
                    if price > 0:
                        self.price_label.setText(f"{price:.2f}")

                # 更新市值信息
                market_cap = basic_info.get('market_cap', 0)
                if market_cap > 0:
                    cap_text = f"{market_cap / 100000000:.2f}亿" if market_cap > 100000000 else f"{market_cap / 10000:.2f}万"
                    self.market_cap_label.setText(f"市值: {cap_text}")

                pe_ratio = basic_info.get('pe_ratio', 0)
                if pe_ratio > 0:
                    self.pe_label.setText(f"PE: {pe_ratio:.2f}")

                pb_ratio = basic_info.get('pb_ratio', 0)
                if pb_ratio > 0:
                    self.pb_label.setText(f"PB: {pb_ratio:.2f}")

        except Exception as e:
            self.logger.error(f"更新头部信息失败: {e}")

    def update_basic_info(self, basic_info: Dict[str, Any]):
        """更新基本信息"""
        try:
            for field, label in self.basic_info_labels.items():
                value = basic_info.get(field, '--')

                # 格式化显示
                if field in ['total_share', 'float_share']:
                    if isinstance(value, (int, float)) and value > 0:
                        value = f"{value / 100000000:.2f}亿股"
                elif field in ['market_cap']:
                    if isinstance(value, (int, float)) and value > 0:
                        value = f"{value / 100000000:.2f}亿元"
                elif field in ['pe_ratio', 'pb_ratio', 'dividend_yield', 'roe', 'debt_ratio']:
                    if isinstance(value, (int, float)):
                        if field in ['dividend_yield', 'roe', 'debt_ratio']:
                            value = f"{value * 100:.2f}%"
                        else:
                            value = f"{value:.2f}"

                label.setText(str(value))

        except Exception as e:
            self.logger.error(f"更新基本信息失败: {e}")

    def update_finance_data(self, finance_data: Dict[str, Any]):
        """更新财务数据"""
        try:
            if not finance_data:
                return

            # 财务指标映射
            finance_items = [
                ('营业收入(万元)', 'revenue'),
                ('净利润(万元)', 'profit'),
                ('总资产(万元)', 'assets'),
                ('总负债(万元)', 'liability'),
                ('净资产(万元)', 'equity'),
                ('经营现金流(万元)', 'cash_flow')
            ]

            self.finance_table.setRowCount(len(finance_items))

            years = finance_data.get('years', ['2023', '2022', '2021', '2020'])

            for i, (name, key) in enumerate(finance_items):
                # 设置指标名称
                self.finance_table.setItem(i, 0, QTableWidgetItem(name))

                # 设置各年数据
                values = finance_data.get(key, [])
                for j, year in enumerate(years[:4]):  # 只显示4年
                    if j < len(values):
                        value = values[j]
                        if isinstance(value, (int, float)):
                            value_text = f"{value / 10000:.2f}" if value > 10000 else f"{value:.2f}"
                        else:
                            value_text = str(value)
                    else:
                        value_text = "--"

                    self.finance_table.setItem(
                        i, j + 1, QTableWidgetItem(value_text))

        except Exception as e:
            self.logger.error(f"更新财务数据失败: {e}")

    def update_indicators(self, indicators: Dict[str, Any]):
        """更新技术指标"""
        try:
            if not indicators:
                return

            # 技术指标映射
            indicator_items = [
                ('MA5', 'ma5'),
                ('MA10', 'ma10'),
                ('MA20', 'ma20'),
                ('MA60', 'ma60'),
                ('RSI', 'rsi'),
                ('MACD', 'macd'),
                ('KDJ-K', 'kdj_k'),
                ('KDJ-D', 'kdj_d'),
                ('布林上轨', 'boll_upper'),
                ('布林下轨', 'boll_lower'),
                ('量比', 'volume_ratio'),
                ('换手率(%)', 'turnover_rate')
            ]

            self.indicator_table.setRowCount(len(indicator_items))

            for i, (name, key) in enumerate(indicator_items):
                self.indicator_table.setItem(i, 0, QTableWidgetItem(name))

                value = indicators.get(key, '--')
                if isinstance(value, (int, float)):
                    if key == 'turnover_rate':
                        value_text = f"{value:.2f}%"
                    else:
                        value_text = f"{value:.2f}"
                else:
                    value_text = str(value)

                self.indicator_table.setItem(
                    i, 1, QTableWidgetItem(value_text))

        except Exception as e:
            self.logger.error(f"更新技术指标失败: {e}")

    def update_statistics(self, statistics: Dict[str, Any]):
        """更新统计数据"""
        try:
            if not statistics:
                return

            # 统计指标映射
            stat_items = [
                ('52周最高价', 'max_price_52w'),
                ('52周最低价', 'min_price_52w'),
                ('20日平均成交量', 'avg_volume_20d'),
                ('1日涨跌幅(%)', 'price_change_1d'),
                ('5日涨跌幅(%)', 'price_change_5d'),
                ('20日涨跌幅(%)', 'price_change_20d'),
                ('60日涨跌幅(%)', 'price_change_60d'),
                ('年初至今涨跌幅(%)', 'price_change_ytd'),
                ('20日波动率(%)', 'volatility_20d'),
                ('Beta系数', 'beta'),
                ('20日振幅(%)', 'amplitude_20d')
            ]

            self.statistics_table.setRowCount(len(stat_items))

            for i, (name, key) in enumerate(stat_items):
                self.statistics_table.setItem(i, 0, QTableWidgetItem(name))

                value = statistics.get(key, '--')
                if isinstance(value, (int, float)):
                    if key in ['price_change_1d', 'price_change_5d', 'price_change_20d',
                               'price_change_60d', 'price_change_ytd', 'volatility_20d', 'amplitude_20d']:
                        value_text = f"{value * 100:.2f}%"
                    elif key == 'avg_volume_20d':
                        value_text = f"{value / 10000:.2f}万"
                    else:
                        value_text = f"{value:.2f}"
                else:
                    value_text = str(value)

                self.statistics_table.setItem(
                    i, 1, QTableWidgetItem(value_text))

        except Exception as e:
            self.logger.error(f"更新统计数据失败: {e}")

    def update_related_stocks(self, related_stocks: List[Dict[str, Any]]):
        """更新相关股票"""
        try:
            if not related_stocks:
                return

            self.related_table.setRowCount(len(related_stocks))

            for i, stock in enumerate(related_stocks):
                self.related_table.setItem(
                    i, 0, QTableWidgetItem(stock.get('code', '')))
                self.related_table.setItem(
                    i, 1, QTableWidgetItem(stock.get('name', '')))

                correlation = stock.get('correlation', 0)
                correlation_text = f"{correlation:.2f}" if isinstance(
                    correlation, (int, float)) else str(correlation)
                self.related_table.setItem(
                    i, 2, QTableWidgetItem(correlation_text))

        except Exception as e:
            self.logger.error(f"更新相关股票失败: {e}")

    def on_related_stock_clicked(self, item):
        """相关股票点击事件"""
        try:
            row = item.row()
            code_item = self.related_table.item(row, 0)
            if code_item:
                stock_code = code_item.text()
                self.stock_selected.emit(stock_code)

        except Exception as e:
            self.logger.error(f"处理相关股票点击失败: {e}")

    def export_data(self):
        """导出数据"""
        try:
            self.data_export_requested.emit(self.stock_code, self.stock_data)

        except Exception as e:
            self.logger.error(f"导出数据失败: {e}")
            QMessageBox.warning(self, "错误", f"导出数据失败: {e}")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 测试对话框
    dialog = StockDetailDialog("000001")
    dialog.show()

    sys.exit(app.exec_())
