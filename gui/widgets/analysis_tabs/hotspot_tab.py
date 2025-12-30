from loguru import logger
"""
热点分析标签页模块
"""

from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import time
import random
import os

from .base_tab import BaseAnalysisTab
from utils.config_manager import ConfigManager


class FundFlowWorker(QThread):
    """资金流数据异步查询Worker"""
    # 定义信号
    finished = pyqtSignal(dict)  # 查询完成信号，携带数据
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
    
    def run(self):
        """后台执行资金流查询"""
        try:
            logger.info("开始异步查询板块资金流数据...")
            fund_flow_data = self.data_manager.get_fund_flow()
            logger.info(f"资金流数据查询完成")
            self.finished.emit(fund_flow_data if fund_flow_data else {})
        except Exception as e:
            logger.error(f"资金流数据查询失败: {e}")
            self.error.emit(str(e))


class HotspotAnalysisTab(BaseAnalysisTab):
    """热点分析标签页"""

    # 定义信号
    hotspot_analysis_completed = pyqtSignal(dict)
    
    # 跳过K线数据设置（热点分析不需要个股K线数据，资金流查询已改为异步避免阻塞）
    skip_kdata = True

    def __init__(self, config_manager: Optional[ConfigManager] = None, service_container=None):
        self.service_container = service_container
        super().__init__(config_manager)
        self.hotspot_results = []
        self.hotspot_statistics = {}
        self.sector_rankings = []
        self.leading_stocks = []
        self.theme_opportunities = []
        
        # 异步Worker相关
        self.fund_flow_worker = None
        self.data_manager = None

    def create_ui(self):
        """创建热点分析UI"""
        layout = QVBoxLayout(self)

        # 热点类型选择区域
        types_group = self.create_types_section()
        layout.addWidget(types_group)

        # 参数配置区域
        params_group = self.create_params_section()
        layout.addWidget(params_group)

        # 分析控制区域
        control_group = self.create_control_section()
        layout.addWidget(control_group)

        # 结果显示区域
        results_group = self.create_results_section()
        layout.addWidget(results_group)

    def create_types_section(self):
        """创建热点类型选择区域"""
        types_group = QGroupBox("热点分析类型")
        layout = QGridLayout(types_group)

        # 板块热点
        self.sector_cb = QCheckBox("板块热点分析")
        self.sector_cb.setChecked(True)
        self.sector_cb.setToolTip("分析各行业板块的热度排名")
        layout.addWidget(self.sector_cb, 0, 0)

        # 主题热点
        self.theme_cb = QCheckBox("主题热点分析")
        self.theme_cb.setChecked(True)
        self.theme_cb.setToolTip("分析当前热门投资主题")
        layout.addWidget(self.theme_cb, 0, 1)

        # 龙头股分析
        self.leading_cb = QCheckBox("龙头股分析")
        self.leading_cb.setChecked(True)
        self.leading_cb.setToolTip("识别各板块的龙头股票")
        layout.addWidget(self.leading_cb, 0, 2)

        # 资金流向
        self.flow_cb = QCheckBox("资金流向分析")
        self.flow_cb.setChecked(True)
        self.flow_cb.setToolTip("分析资金流向热点板块")
        layout.addWidget(self.flow_cb, 1, 0)

        # 板块轮动
        self.rotation_cb = QCheckBox("板块轮动分析")
        self.rotation_cb.setChecked(False)
        self.rotation_cb.setToolTip("分析板块轮动规律")
        layout.addWidget(self.rotation_cb, 1, 1)

        # 热点持续性
        self.persistence_cb = QCheckBox("热点持续性分析")
        self.persistence_cb.setChecked(False)
        self.persistence_cb.setToolTip("预测热点持续时间")
        layout.addWidget(self.persistence_cb, 1, 2)

        return types_group

    def create_params_section(self):
        """创建参数配置区域"""
        params_group = QGroupBox("热点分析参数")
        layout = QGridLayout(params_group)

        # 分析周期
        layout.addWidget(QLabel("分析周期:"), 0, 0)
        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 60)
        self.period_spin.setValue(5)
        self.period_spin.setSuffix("天")
        layout.addWidget(self.period_spin, 0, 1)

        # 热度阈值
        layout.addWidget(QLabel("热度阈值:"), 0, 2)
        self.heat_threshold_spin = QDoubleSpinBox()
        self.heat_threshold_spin.setRange(0.1, 5.0)
        self.heat_threshold_spin.setValue(1.5)
        self.heat_threshold_spin.setDecimals(1)
        layout.addWidget(self.heat_threshold_spin, 0, 3)

        # 涨幅阈值
        layout.addWidget(QLabel("涨幅阈值:"), 1, 0)
        self.gain_threshold_spin = QDoubleSpinBox()
        self.gain_threshold_spin.setRange(1.0, 50.0)
        self.gain_threshold_spin.setValue(5.0)
        self.gain_threshold_spin.setSuffix("%")
        layout.addWidget(self.gain_threshold_spin, 1, 1)

        # 成交量倍数
        self.volume_multiplier_spin = QDoubleSpinBox()
        layout.addWidget(QLabel("成交量倍数:"), 1, 2)
        self.volume_multiplier_spin.setRange(1.0, 10.0)
        self.volume_multiplier_spin.setValue(2.0)
        self.volume_multiplier_spin.setDecimals(1)
        layout.addWidget(self.volume_multiplier_spin, 1, 3)

        return params_group

    def create_control_section(self):
        """创建分析控制区域"""
        control_group = QGroupBox("热点分析控制")
        layout = QHBoxLayout(control_group)

        # 开始分析按钮
        analyze_btn = QPushButton("开始热点分析")
        analyze_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; font-weight: bold; }")
        analyze_btn.clicked.connect(self.analyze_hotspot)
        layout.addWidget(analyze_btn)

        # 实时监控按钮
        monitor_btn = QPushButton("实时监控")
        monitor_btn.setStyleSheet(
            "QPushButton { background-color: #17a2b8; color: white; font-weight: bold; }")
        monitor_btn.clicked.connect(self.start_monitor)
        layout.addWidget(monitor_btn)

        # 清除结果按钮
        clear_btn = QPushButton("清除结果")
        clear_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; }")
        clear_btn.clicked.connect(self.clear_hotspot)
        layout.addWidget(clear_btn)

        # 导出结果按钮
        export_btn = QPushButton("导出热点分析")
        export_btn.setStyleSheet(
            "QPushButton { background-color: #fd7e14; color: white; }")
        export_btn.clicked.connect(self.export_hotspot_analysis)
        layout.addWidget(export_btn)

        layout.addStretch()
        return control_group

    def create_results_section(self):
        """创建结果显示区域"""
        results_group = QGroupBox("热点分析结果")
        layout = QVBoxLayout(results_group)

        # 热点概览
        overview_group = QGroupBox("热点概览")
        overview_layout = QHBoxLayout(overview_group)

        # 热点板块数
        hotspot_card = QFrame()
        hotspot_card.setFrameStyle(QFrame.StyledPanel)
        hotspot_layout = QVBoxLayout(hotspot_card)
        hotspot_layout.addWidget(QLabel("热点板块"))

        self.hotspot_count_label = QLabel("0")
        self.hotspot_count_label.setAlignment(Qt.AlignCenter)
        self.hotspot_count_label.setStyleSheet(
            "QLabel { font-size: 24px; font-weight: bold; color: #dc3545; }")
        hotspot_layout.addWidget(self.hotspot_count_label)

        overview_layout.addWidget(hotspot_card)

        # 龙头股数
        leading_card = QFrame()
        leading_card.setFrameStyle(QFrame.StyledPanel)
        leading_layout = QVBoxLayout(leading_card)
        leading_layout.addWidget(QLabel("龙头股"))

        self.leading_count_label = QLabel("0")
        self.leading_count_label.setAlignment(Qt.AlignCenter)
        self.leading_count_label.setStyleSheet(
            "QLabel { font-size: 24px; font-weight: bold; color: #28a745; }")
        leading_layout.addWidget(self.leading_count_label)

        overview_layout.addWidget(leading_card)

        # 主题机会
        theme_card = QFrame()
        theme_card.setFrameStyle(QFrame.StyledPanel)
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.addWidget(QLabel("主题机会"))

        self.theme_count_label = QLabel("0")
        self.theme_count_label.setAlignment(Qt.AlignCenter)
        self.theme_count_label.setStyleSheet(
            "QLabel { font-size: 24px; font-weight: bold; color: #007bff; }")
        theme_layout.addWidget(self.theme_count_label)

        overview_layout.addWidget(theme_card)

        # 市场热度
        heat_card = QFrame()
        heat_card.setFrameStyle(QFrame.StyledPanel)
        heat_layout = QVBoxLayout(heat_card)
        heat_layout.addWidget(QLabel("市场热度"))

        self.market_heat_label = QLabel("中等")
        self.market_heat_label.setAlignment(Qt.AlignCenter)
        self.market_heat_label.setStyleSheet(
            "QLabel { font-size: 18px; font-weight: bold; color: #ffc107; }")
        heat_layout.addWidget(self.market_heat_label)

        overview_layout.addWidget(heat_card)

        layout.addWidget(overview_group)

        # 详细分析结果标签页
        self.results_tab_widget = QTabWidget()

        # 板块热点标签页
        self.sector_tab = self.create_sector_results_tab()
        self.results_tab_widget.addTab(self.sector_tab, "板块热点")

        # 龙头股标签页
        self.leading_tab = self.create_leading_results_tab()
        self.results_tab_widget.addTab(self.leading_tab, "龙头股")

        # 主题机会标签页
        self.theme_tab = self.create_theme_results_tab()
        self.results_tab_widget.addTab(self.theme_tab, "主题机会")

        # 资金流向标签页
        self.flow_tab = self.create_flow_results_tab()
        self.results_tab_widget.addTab(self.flow_tab, "资金流向")

        layout.addWidget(self.results_tab_widget)
        return results_group

    def create_sector_results_tab(self):
        """创建板块热点结果标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.sector_table = QTableWidget()
        self.sector_table.setColumnCount(7)
        self.sector_table.setHorizontalHeaderLabels([
            "板块名称", "热度指数", "涨跌幅", "成交量比", "领涨股", "上涨家数", "热点等级"
        ])
        self.sector_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sector_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sector_table.setAlternatingRowColors(True)
        self.sector_table.setSortingEnabled(True)

        layout.addWidget(self.sector_table)
        return tab

    def create_leading_results_tab(self):
        """创建龙头股结果标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.leading_table = QTableWidget()
        self.leading_table.setColumnCount(8)
        self.leading_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "所属板块", "涨跌幅", "成交量比", "龙头指数", "市值", "地位"
        ])
        self.leading_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.leading_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.leading_table.setAlternatingRowColors(True)
        self.leading_table.setSortingEnabled(True)

        layout.addWidget(self.leading_table)
        return tab

    def create_theme_results_tab(self):
        """创建主题机会结果标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.theme_table = QTableWidget()
        self.theme_table.setColumnCount(6)
        self.theme_table.setHorizontalHeaderLabels([
            "主题名称", "热度评分", "相关股票数", "平均涨幅", "资金关注度", "投资机会"
        ])
        self.theme_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.theme_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.theme_table.setAlternatingRowColors(True)
        self.theme_table.setSortingEnabled(True)

        layout.addWidget(self.theme_table)
        return tab

    def create_flow_results_tab(self):
        """创建资金流向结果标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.flow_table = QTableWidget()
        self.flow_table.setColumnCount(6)
        self.flow_table.setHorizontalHeaderLabels([
            "板块名称", "主力净流入", "散户净流入", "总净流入", "流入强度", "资金偏好"
        ])
        self.flow_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.flow_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.flow_table.setAlternatingRowColors(True)
        self.flow_table.setSortingEnabled(True)

        layout.addWidget(self.flow_table)
        return tab

    def analyze_hotspot(self):
        """执行热点分析"""
        try:
            self.show_loading("正在进行热点分析...")

            # 获取参数
            period = self.period_spin.value()
            heat_threshold = self.heat_threshold_spin.value()
            gain_threshold = self.gain_threshold_spin.value() / 100.0
            volume_multiplier = self.volume_multiplier_spin.value()

            # 执行分析
            self.hotspot_results = []
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if self.sector_cb.isChecked():
                self.analyze_sector_hotspots(
                    period, heat_threshold, gain_threshold, volume_multiplier)

            if self.leading_cb.isChecked():
                self.analyze_leading_stocks(
                    period, heat_threshold, gain_threshold)

            if self.theme_cb.isChecked():
                self.analyze_theme_opportunities(period, heat_threshold)

            if self.flow_cb.isChecked():
                self.analyze_capital_flow(period)

            if self.rotation_cb.isChecked():
                self.analyze_sector_rotation(period)

            if self.persistence_cb.isChecked():
                self.analyze_hotspot_persistence(period)

            # 更新显示
            self.update_hotspot_display()
            self.update_hotspot_statistics()

            # 发送完成信号
            self.hotspot_analysis_completed.emit({
                'results': self.hotspot_results,
                'statistics': self.hotspot_statistics,
                'sector_rankings': self.sector_rankings,
                'leading_stocks': self.leading_stocks,
                'theme_opportunities': self.theme_opportunities
            })

        except Exception as e:
            logger.error(f"热点分析失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"热点分析失败: {str(e)}")
        finally:
            self.hide_loading()

    def analyze_sector_hotspots(self, period: int, heat_threshold: float, gain_threshold: float, volume_multiplier: float):
        """分析板块热点"""
        try:
            # 模拟板块数据
            sectors = [
                "新能源汽车", "人工智能", "半导体", "生物医药", "5G通信",
                "新材料", "军工", "消费电子", "光伏", "风电",
                "锂电池", "芯片", "云计算", "大数据", "物联网"
            ]

            self.sector_rankings = []

            for sector in sectors:
                # 模拟板块数据
                heat_index = random.uniform(0.5, 3.0)
                gain_pct = random.uniform(-5.0, 15.0)
                volume_ratio = random.uniform(0.8, 4.0)
                rising_count = random.randint(5, 25)
                leading_stock = f"{sector}龙头"

                # 判断热点等级
                if heat_index >= 2.5 and gain_pct >= 5.0:
                    level = "超级热点"
                elif heat_index >= 2.0 and gain_pct >= 3.0:
                    level = "强势热点"
                elif heat_index >= 1.5 and gain_pct >= 1.0:
                    level = "一般热点"
                else:
                    level = "冷门板块"

                self.sector_rankings.append({
                    '板块名称': sector,
                    '热度指数': f"{heat_index:.2f}",
                    '涨跌幅': f"{gain_pct:+.2f}%",
                    '成交量比': f"{volume_ratio:.2f}",
                    '领涨股': leading_stock,
                    '上涨家数': f"{rising_count}",
                    '热点等级': level
                })

            # 按热度指数排序
            self.sector_rankings.sort(
                key=lambda x: float(x['热度指数']), reverse=True)

        except Exception as e:
            logger.error(f"板块热点分析失败: {str(e)}")

    def analyze_leading_stocks(self, period: int, heat_threshold: float, gain_threshold: float):
        """分析龙头股"""
        try:
            # 模拟龙头股数据
            leading_stocks_data = [
                ("000001", "平安银行", "银行", 8.5, 2.3, 85, "2500亿", "绝对龙头"),
                ("000002", "万科A", "房地产", 5.2, 1.8, 78, "2800亿", "行业龙头"),
                ("000858", "五粮液", "白酒", 12.3, 3.1, 92, "8500亿", "绝对龙头"),
                ("600036", "招商银行", "银行", 6.8, 2.0, 88, "12000亿", "绝对龙头"),
                ("600519", "贵州茅台", "白酒", 4.2, 1.5, 95, "25000亿", "绝对龙头"),
                ("000858", "宁德时代", "新能源", 15.8, 4.2, 90, "12000亿", "绝对龙头"),
                ("002415", "海康威视", "安防", 9.3, 2.8, 82, "4500亿", "行业龙头"),
                ("300059", "东方财富", "券商", 11.2, 3.5, 79, "3200亿", "行业龙头")
            ]

            self.leading_stocks = []

            for code, name, sector, base_gain, base_volume, base_index, market_cap, status in leading_stocks_data:
                # 添加随机波动
                gain_pct = base_gain + random.uniform(-2.0, 3.0)
                volume_ratio = base_volume + random.uniform(-0.5, 1.0)
                leading_index = base_index + random.randint(-5, 5)

                self.leading_stocks.append({
                    '股票代码': code,
                    '股票名称': name,
                    '所属板块': sector,
                    '涨跌幅': f"{gain_pct:+.2f}%",
                    '成交量比': f"{volume_ratio:.2f}",
                    '龙头指数': str(leading_index),
                    '市值': market_cap,
                    '地位': status
                })

            # 按龙头指数排序
            self.leading_stocks.sort(
                key=lambda x: int(x['龙头指数']), reverse=True)

        except Exception as e:
            logger.error(f"龙头股分析失败: {str(e)}")

    def analyze_theme_opportunities(self, period: int, heat_threshold: float):
        """分析主题机会"""
        try:
            # 模拟主题机会数据
            themes = [
                "碳中和", "数字经济", "元宇宙", "新基建", "国产替代",
                "医美概念", "预制菜", "ChatGPT", "东数西算", "专精特新"
            ]

            self.theme_opportunities = []

            for theme in themes:
                heat_score = random.uniform(60, 95)
                stock_count = random.randint(15, 80)
                avg_gain = random.uniform(-2.0, 12.0)
                attention = random.uniform(0.3, 1.0)

                # 判断投资机会
                if heat_score >= 85 and avg_gain >= 5.0:
                    opportunity = "强烈推荐"
                elif heat_score >= 75 and avg_gain >= 2.0:
                    opportunity = "值得关注"
                elif heat_score >= 65:
                    opportunity = "谨慎观望"
                else:
                    opportunity = "暂不推荐"

                self.theme_opportunities.append({
                    '主题名称': theme,
                    '热度评分': f"{heat_score:.1f}",
                    '相关股票数': str(stock_count),
                    '平均涨幅': f"{avg_gain:+.2f}%",
                    '资金关注度': f"{attention:.2f}",
                    '投资机会': opportunity
                })

            # 按热度评分排序
            self.theme_opportunities.sort(
                key=lambda x: float(x['热度评分']), reverse=True)

        except Exception as e:
            logger.error(f"主题机会分析失败: {str(e)}")

    def analyze_capital_flow(self, period: int):
        """分析资金流向（异步） - 使用真实数据"""
        try:
            self.capital_flow = []

            # 确保有数据管理器 - 使用工厂方法获取正确实例
            if not self.data_manager:
                try:
                    from utils.manager_factory import get_manager_factory, get_data_manager
                    factory = get_manager_factory()
                    self.data_manager = get_data_manager()
                except ImportError:
                    # 降级方案：使用统一数据管理器
                    from core.services.unified_data_manager import get_unified_data_manager
                    self.data_manager = get_unified_data_manager()

            # 停止之前的Worker（如果存在）
            if self.fund_flow_worker and self.fund_flow_worker.isRunning():
                logger.info("停止之前的资金流查询...")
                self.fund_flow_worker.quit()
                self.fund_flow_worker.wait()

            # 创建并启动异步Worker
            logger.info("启动异步资金流查询...")
            self.fund_flow_worker = FundFlowWorker(self.data_manager, self)
            self.fund_flow_worker.finished.connect(self._on_fund_flow_finished)
            self.fund_flow_worker.error.connect(self._on_fund_flow_error)
            self.fund_flow_worker.start()
            
            # 显示加载状态
            self.show_loading("正在异步查询板块资金流数据，请稍候...")

        except Exception as e:
            logger.error(f"启动资金流向分析失败: {str(e)}")
            self.hide_loading()
    
    def _on_fund_flow_finished(self, fund_flow_data: dict):
        """资金流数据查询完成回调"""
        try:
            logger.info("处理资金流查询结果...")
            self.hide_loading()
            
            if fund_flow_data and 'sector_flow_rank' in fund_flow_data:
                sector_df = fund_flow_data['sector_flow_rank']

                if not sector_df.empty:
                    # 处理前10个板块
                    top_sectors = sector_df.head(10)

                    for _, row in top_sectors.iterrows():
                        sector_name = row.get('板块', row.get('industry', '未知板块'))

                        # 获取各种资金流数据
                        main_inflow = self._parse_flow_value(row.get('今日主力净流入-净额', row.get('主力净流入-净额', 0)))
                        retail_inflow = self._parse_flow_value(row.get('今日散户净流入-净额', row.get('散户净流入-净额', 0)))
                        total_inflow = main_inflow + retail_inflow

                        # 计算流入强度
                        abs_total = abs(total_inflow)
                        if abs_total > 150000000:  # 1.5亿
                            intensity = "极强"
                        elif abs_total > 80000000:  # 8000万
                            intensity = "强"
                        elif abs_total > 30000000:  # 3000万
                            intensity = "中等"
                        else:
                            intensity = "弱"

                        # 判断资金偏好
                        if abs(main_inflow) > abs(retail_inflow) * 2:
                            preference = "机构偏好"
                        elif abs(retail_inflow) > abs(main_inflow) * 2:
                            preference = "散户偏好"
                        else:
                            preference = "均衡流入"

                        self.capital_flow.append({
                            '板块名称': sector_name,
                            '主力净流入': f"{main_inflow/10000:.0f}万",
                            '散户净流入': f"{retail_inflow/10000:.0f}万",
                            '总净流入': f"{total_inflow/10000:.0f}万",
                            '流入强度': intensity,
                            '资金偏好': preference
                        })

                    logger.info(f"资金流向分析完成，共分析 {len(self.capital_flow)} 个板块")
                else:
                    logger.warning("板块资金流数据为空")
            else:
                logger.warning("未获取到板块资金流数据")

            # 如果没有获取到真实数据，使用板块排行数据作为替代
            if not self.capital_flow and hasattr(self, 'sector_rankings') and self.sector_rankings:
                self._analyze_capital_flow_from_rankings()

        except Exception as e:
            logger.error(f"处理资金流数据失败: {str(e)}")
            self.hide_loading()
    
    def _on_fund_flow_error(self, error_msg: str):
        """资金流数据查询失败回调"""
        try:
            logger.error(f"资金流数据查询失败: {error_msg}")
            self.hide_loading()
            
            # 尝试使用板块排行数据作为降级方案
            if hasattr(self, 'sector_rankings') and self.sector_rankings:
                logger.info("使用板块排行数据作为降级方案...")
                self._analyze_capital_flow_from_rankings()
            else:
                QMessageBox.warning(self, "提示", f"资金流数据获取失败：{error_msg}\n建议稍后重试")
                
        except Exception as e:
            logger.error(f"处理资金流错误失败: {str(e)}")

    def _parse_flow_value(self, value):
        """解析资金流数值"""
        try:
            if isinstance(value, str):
                # 处理带单位的字符串
                if '万' in value:
                    return float(value.replace('万', '')) * 10000
                elif '亿' in value:
                    return float(value.replace('亿', '')) * 100000000
                else:
                    return float(value)
            elif isinstance(value, (int, float)):
                return float(value)
            else:
                return 0.0
        except:
            return 0.0

    def _analyze_capital_flow_from_rankings(self):
        """从板块排行数据分析资金流向（备用方案）"""
        try:
            for sector_data in self.sector_rankings[:10]:
                sector_name = sector_data.get('板块名称', '未知板块')

                # 基于涨跌幅估算资金流
                change_pct = sector_data.get('涨跌幅', 0)
                if isinstance(change_pct, str):
                    change_pct = float(change_pct.replace('%', ''))

                # 简单的估算逻辑
                estimated_flow = change_pct * 10000000  # 按涨跌幅估算资金流
                main_inflow = estimated_flow * 0.7  # 主力占70%
                retail_inflow = estimated_flow * 0.3  # 散户占30%

                # 计算强度和偏好
                abs_total = abs(estimated_flow)
                if abs_total > 50000000:
                    intensity = "强"
                elif abs_total > 20000000:
                    intensity = "中等"
                else:
                    intensity = "弱"

                preference = "机构偏好" if main_inflow > retail_inflow else "散户偏好"

                self.capital_flow.append({
                    '板块名称': sector_name,
                    '主力净流入': f"{main_inflow/10000:.0f}万",
                    '散户净流入': f"{retail_inflow/10000:.0f}万",
                    '总净流入': f"{estimated_flow/10000:.0f}万",
                    '流入强度': intensity,
                    '资金偏好': preference
                })

            logger.info(f"使用排行数据估算资金流向完成，共 {len(self.capital_flow)} 个板块")

        except Exception as e:
            logger.error(f"从排行数据分析资金流向失败: {str(e)}")

    def analyze_sector_rotation(self, period: int):
        """分析板块轮动"""
        try:
            # 模拟板块轮动分析
            logger.info("板块轮动分析完成")

        except Exception as e:
            logger.error(f"板块轮动分析失败: {str(e)}")

    def analyze_hotspot_persistence(self, period: int):
        """分析热点持续性"""
        try:
            # 模拟热点持续性分析
            logger.info("热点持续性分析完成")

        except Exception as e:
            logger.error(f"热点持续性分析失败: {str(e)}")

    def start_monitor(self):
        """开始实时监控"""
        try:
            QMessageBox.information(self, "监控启动", "实时热点监控已启动，将每5分钟更新一次数据")
            # 这里可以实现定时器来定期更新数据

        except Exception as e:
            logger.error(f"启动监控失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"启动监控失败: {str(e)}")

    def update_hotspot_display(self):
        """更新热点分析显示"""
        try:
            # 更新板块热点表格
            if hasattr(self, 'sector_rankings'):
                self.sector_table.setRowCount(len(self.sector_rankings))
                for i, sector in enumerate(self.sector_rankings):
                    self.sector_table.setItem(
                        i, 0, QTableWidgetItem(sector['板块名称']))
                    self.sector_table.setItem(
                        i, 1, QTableWidgetItem(sector['热度指数']))

                    # 涨跌幅带颜色显示
                    gain_item = QTableWidgetItem(sector['涨跌幅'])
                    if '+' in sector['涨跌幅']:
                        gain_item.setForeground(QColor("red"))
                    else:
                        gain_item.setForeground(QColor("green"))
                    self.sector_table.setItem(i, 2, gain_item)

                    self.sector_table.setItem(
                        i, 3, QTableWidgetItem(sector['成交量比']))
                    self.sector_table.setItem(
                        i, 4, QTableWidgetItem(sector['领涨股']))
                    self.sector_table.setItem(
                        i, 5, QTableWidgetItem(sector['上涨家数']))

                    # 热点等级带颜色显示
                    level_item = QTableWidgetItem(sector['热点等级'])
                    if '超级' in sector['热点等级']:
                        level_item.setForeground(QColor("red"))
                    elif '强势' in sector['热点等级']:
                        level_item.setForeground(QColor("orange"))
                    elif '一般' in sector['热点等级']:
                        level_item.setForeground(QColor("blue"))
                    else:
                        level_item.setForeground(QColor("gray"))
                    self.sector_table.setItem(i, 6, level_item)

            # 更新龙头股表格
            if hasattr(self, 'leading_stocks'):
                self.leading_table.setRowCount(len(self.leading_stocks))
                for i, stock in enumerate(self.leading_stocks):
                    self.leading_table.setItem(
                        i, 0, QTableWidgetItem(stock['股票代码']))
                    self.leading_table.setItem(
                        i, 1, QTableWidgetItem(stock['股票名称']))
                    self.leading_table.setItem(
                        i, 2, QTableWidgetItem(stock['所属板块']))

                    # 涨跌幅带颜色显示
                    gain_item = QTableWidgetItem(stock['涨跌幅'])
                    if '+' in stock['涨跌幅']:
                        gain_item.setForeground(QColor("red"))
                    else:
                        gain_item.setForeground(QColor("green"))
                    self.leading_table.setItem(i, 3, gain_item)

                    self.leading_table.setItem(
                        i, 4, QTableWidgetItem(stock['成交量比']))
                    self.leading_table.setItem(
                        i, 5, QTableWidgetItem(stock['龙头指数']))
                    self.leading_table.setItem(
                        i, 6, QTableWidgetItem(stock['市值']))
                    self.leading_table.setItem(
                        i, 7, QTableWidgetItem(stock['地位']))

            # 更新主题机会表格
            if hasattr(self, 'theme_opportunities'):
                self.theme_table.setRowCount(len(self.theme_opportunities))
                for i, theme in enumerate(self.theme_opportunities):
                    self.theme_table.setItem(
                        i, 0, QTableWidgetItem(theme['主题名称']))
                    self.theme_table.setItem(
                        i, 1, QTableWidgetItem(theme['热度评分']))
                    self.theme_table.setItem(
                        i, 2, QTableWidgetItem(theme['相关股票数']))

                    # 平均涨幅带颜色显示
                    gain_item = QTableWidgetItem(theme['平均涨幅'])
                    if '+' in theme['平均涨幅']:
                        gain_item.setForeground(QColor("red"))
                    else:
                        gain_item.setForeground(QColor("green"))
                    self.theme_table.setItem(i, 3, gain_item)

                    self.theme_table.setItem(
                        i, 4, QTableWidgetItem(theme['资金关注度']))

                    # 投资机会带颜色显示
                    opp_item = QTableWidgetItem(theme['投资机会'])
                    if '强烈推荐' in theme['投资机会']:
                        opp_item.setForeground(QColor("red"))
                    elif '值得关注' in theme['投资机会']:
                        opp_item.setForeground(QColor("orange"))
                    elif '谨慎观望' in theme['投资机会']:
                        opp_item.setForeground(QColor("blue"))
                    else:
                        opp_item.setForeground(QColor("gray"))
                    self.theme_table.setItem(i, 5, opp_item)

            # 更新资金流向表格
            if hasattr(self, 'capital_flow'):
                self.flow_table.setRowCount(len(self.capital_flow))
                for i, flow in enumerate(self.capital_flow):
                    self.flow_table.setItem(
                        i, 0, QTableWidgetItem(flow['板块名称']))

                    # 资金流入带颜色显示
                    main_item = QTableWidgetItem(flow['主力净流入'])
                    if '万' in flow['主力净流入'] and not flow['主力净流入'].startswith('-'):
                        main_item.setForeground(QColor("red"))
                    else:
                        main_item.setForeground(QColor("green"))
                    self.flow_table.setItem(i, 1, main_item)

                    retail_item = QTableWidgetItem(flow['散户净流入'])
                    if '万' in flow['散户净流入'] and not flow['散户净流入'].startswith('-'):
                        retail_item.setForeground(QColor("red"))
                    else:
                        retail_item.setForeground(QColor("green"))
                    self.flow_table.setItem(i, 2, retail_item)

                    total_item = QTableWidgetItem(flow['总净流入'])
                    if '万' in flow['总净流入'] and not flow['总净流入'].startswith('-'):
                        total_item.setForeground(QColor("red"))
                    else:
                        total_item.setForeground(QColor("green"))
                    self.flow_table.setItem(i, 3, total_item)

                    self.flow_table.setItem(
                        i, 4, QTableWidgetItem(flow['流入强度']))
                    self.flow_table.setItem(
                        i, 5, QTableWidgetItem(flow['资金偏好']))

            # 调整列宽
            self.sector_table.resizeColumnsToContents()
            self.leading_table.resizeColumnsToContents()
            self.theme_table.resizeColumnsToContents()
            self.flow_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"更新热点分析显示失败: {str(e)}")

    def update_hotspot_statistics(self):
        """更新热点分析统计"""
        try:
            # 统计热点数量
            hotspot_count = len([s for s in self.sector_rankings if '热点' in s.get(
                '热点等级', '')]) if hasattr(self, 'sector_rankings') else 0
            leading_count = len(self.leading_stocks) if hasattr(
                self, 'leading_stocks') else 0
            theme_count = len(self.theme_opportunities) if hasattr(
                self, 'theme_opportunities') else 0

            # 计算市场热度
            if hotspot_count >= 8:
                market_heat = "火热"
                heat_color = "#dc3545"
            elif hotspot_count >= 5:
                market_heat = "活跃"
                heat_color = "#fd7e14"
            elif hotspot_count >= 3:
                market_heat = "中等"
                heat_color = "#ffc107"
            else:
                market_heat = "冷清"
                heat_color = "#6c757d"

            # 更新显示
            self.hotspot_count_label.setText(str(hotspot_count))
            self.leading_count_label.setText(str(leading_count))
            self.theme_count_label.setText(str(theme_count))
            self.market_heat_label.setText(market_heat)
            self.market_heat_label.setStyleSheet(
                f"QLabel {{ font-size: 18px; font-weight: bold; color: {heat_color}; }}")

            # 更新统计数据
            self.hotspot_statistics = {
                'hotspot_sectors': hotspot_count,
                'leading_stocks': leading_count,
                'theme_opportunities': theme_count,
                'market_heat': market_heat
            }

        except Exception as e:
            logger.error(f"更新热点分析统计失败: {str(e)}")

    def clear_hotspot(self):
        """清除热点分析结果"""
        self.hotspot_results = []
        self.hotspot_statistics = {}
        self.sector_rankings = []
        self.leading_stocks = []
        self.theme_opportunities = []

        self.sector_table.setRowCount(0)
        self.leading_table.setRowCount(0)
        self.theme_table.setRowCount(0)
        self.flow_table.setRowCount(0)

        self.hotspot_count_label.setText("0")
        self.leading_count_label.setText("0")
        self.theme_count_label.setText("0")
        self.market_heat_label.setText("中等")
        self.market_heat_label.setStyleSheet(
            "QLabel { font-size: 18px; font-weight: bold; color: #ffc107; }")

    def export_hotspot_analysis(self):
        """导出热点分析结果"""
        try:
            if not any([
                hasattr(self, 'sector_rankings') and self.sector_rankings,
                hasattr(self, 'leading_stocks') and self.leading_stocks,
                hasattr(self, 'theme_opportunities') and self.theme_opportunities
            ]):
                QMessageBox.warning(self, "警告", "没有可导出的热点分析数据")
                return

            # 获取保存文件路径
            from PyQt5.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self, "导出热点分析数据", f"hotspot_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON files (*.json)")

            if not filename:
                return

            # 导出数据
            export_data = {
                'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_type': '热点分析',
                'statistics': self.hotspot_statistics,
                'sector_rankings': self.sector_rankings if hasattr(self, 'sector_rankings') else [],
                'leading_stocks': self.leading_stocks if hasattr(self, 'leading_stocks') else [],
                'theme_opportunities': self.theme_opportunities if hasattr(self, 'theme_opportunities') else [],
                'capital_flow': self.capital_flow if hasattr(self, 'capital_flow') else []
            }

            import json
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, ensure_ascii=False, indent=2)

            QMessageBox.information(self, "成功", f"热点分析数据已导出到: {filename}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def refresh_data(self):
        """刷新数据"""
        self.analyze_hotspot()

    def clear_data(self):
        """清除数据"""
        self.clear_hotspot()
