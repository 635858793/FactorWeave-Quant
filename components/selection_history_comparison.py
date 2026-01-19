"""
选股历史对比对话框

提供多个选股结果的对比功能
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from loguru import logger
from typing import Dict, Any, Optional, List
import json

# 数据库服务
try:
    from core.services.database_service import DatabaseService
except ImportError:
    DatabaseService = None


class SelectionComparisonDialog(QDialog):
    """选股历史对比对话框"""
    
    def __init__(self, result_ids: List[str], parent=None):
        super().__init__(parent)
        self.result_ids = result_ids
        self.db_service = None
        self.comparison_data = None
        
        # 初始化服务
        self._init_services()
        
        # 创建UI
        self._create_ui()
        
        # 加载对比数据
        self._load_comparison_data()
    
    def _init_services(self):
        """初始化数据库服务"""
        try:
            from core.containers import get_service_container
            container = get_service_container()
            if container and DatabaseService:
                self.db_service = container.resolve(DatabaseService)
                logger.info("数据库服务加载成功")
            else:
                logger.warning("数据库服务不可用")
        except Exception as e:
            logger.error(f"数据库服务初始化失败: {e}")
    
    def _create_ui(self):
        """创建UI界面"""
        self.setWindowTitle("选股结果对比")
        self.setMinimumSize(1000, 700)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 添加各个选项卡
        self._create_overview_tab()
        self._create_parameters_tab()
        self._create_results_tab()
        self._create_overlap_tab()
        self._create_metrics_tab()
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def _create_overview_tab(self):
        """创建概览选项卡"""
        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)
        
        # 标题
        title_label = QLabel("对比概览")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        overview_layout.addWidget(title_label)
        
        # 概览表格
        self.overview_table = QTableWidget()
        overview_layout.addWidget(self.overview_table)
        
        self.tab_widget.addTab(overview_widget, "概览")
    
    def _create_parameters_tab(self):
        """创建参数对比选项卡"""
        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        
        # 标题
        title_label = QLabel("策略参数对比")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        params_layout.addWidget(title_label)
        
        # 参数对比表格
        self.params_table = QTableWidget()
        params_layout.addWidget(self.params_table)
        
        self.tab_widget.addTab(params_widget, "策略参数")
    
    def _create_results_tab(self):
        """创建结果对比选项卡"""
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        
        # 标题
        title_label = QLabel("选股结果对比")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        results_layout.addWidget(title_label)
        
        # 结果对比表格
        self.results_table = QTableWidget()
        results_layout.addWidget(self.results_table)
        
        self.tab_widget.addTab(results_widget, "选股结果")
    
    def _create_overlap_tab(self):
        """创建重叠度分析选项卡"""
        overlap_widget = QWidget()
        overlap_layout = QVBoxLayout(overlap_widget)
        
        # 标题
        title_label = QLabel("股票重叠度分析")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        overlap_layout.addWidget(title_label)
        
        # 重叠度表格
        self.overlap_table = QTableWidget()
        overlap_layout.addWidget(self.overlap_table)
        
        # 详细信息
        self.overlap_detail_label = QLabel("")
        self.overlap_detail_label.setWordWrap(True)
        self.overlap_detail_label.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
        overlap_layout.addWidget(self.overlap_detail_label)
        
        self.tab_widget.addTab(overlap_widget, "重叠度分析")
    
    def _create_metrics_tab(self):
        """创建性能指标对比选项卡"""
        metrics_widget = QWidget()
        metrics_layout = QVBoxLayout(metrics_widget)
        
        # 标题
        title_label = QLabel("性能指标对比")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        metrics_layout.addWidget(title_label)
        
        # 性能指标表格
        self.metrics_table = QTableWidget()
        metrics_layout.addWidget(self.metrics_table)
        
        self.tab_widget.addTab(metrics_widget, "性能指标")
    
    def _load_comparison_data(self):
        """加载对比数据"""
        if not self.db_service:
            QMessageBox.warning(self, "错误", "数据库服务不可用")
            return
        
        try:
            # 获取对比数据
            self.comparison_data = self.db_service.compare_selection_results(self.result_ids)
            
            # 更新各个选项卡
            self._update_overview_tab()
            self._update_parameters_tab()
            self._update_results_tab()
            self._update_overlap_tab()
            self._update_metrics_tab()
            
        except Exception as e:
            logger.error(f"加载对比数据失败: {e}")
            QMessageBox.critical(self, "错误", f"加载对比数据失败: {e}")
    
    def _update_overview_tab(self):
        """更新概览选项卡"""
        if not self.comparison_data:
            return
        
        comparison = self.comparison_data.get('comparison', {})
        
        # 设置表格
        self.overview_table.setColumnCount(len(self.result_ids) + 1)
        self.overview_table.setHorizontalHeaderLabels(['指标'] + [f"结果 {i+1}" for i in range(len(self.result_ids))])
        
        # 数据行
        data = [
            ('股票数量', 'stock_counts'),
            ('平均评分', 'avg_scores'),
            ('最低评分', 'score_ranges_min'),
            ('最高评分', 'score_ranges_max'),
            ('选股日期', 'date_ranges')
        ]
        
        self.overview_table.setRowCount(len(data))
        
        for row, (label, key) in enumerate(data):
            # 指标列
            self.overview_table.setItem(row, 0, QTableWidgetItem(label))
            
            # 各结果数据列
            for col, result_id in enumerate(self.result_ids):
                if key == 'score_ranges_min':
                    value = comparison.get('score_ranges', {}).get(result_id, {}).get('min', 0)
                    self.overview_table.setItem(row, col + 1, QTableWidgetItem(f"{value:.2f}"))
                elif key == 'score_ranges_max':
                    value = comparison.get('score_ranges', {}).get(result_id, {}).get('max', 0)
                    self.overview_table.setItem(row, col + 1, QTableWidgetItem(f"{value:.2f}"))
                elif key == 'avg_scores':
                    value = comparison.get('avg_scores', {}).get(result_id, 0)
                    self.overview_table.setItem(row, col + 1, QTableWidgetItem(f"{value:.2f}"))
                else:
                    value = comparison.get(key, {}).get(result_id, '')
                    self.overview_table.setItem(row, col + 1, QTableWidgetItem(str(value)))
        
        self.overview_table.horizontalHeader().setStretchLastSection(True)
    
    def _update_parameters_tab(self):
        """更新参数对比选项卡"""
        if not self.comparison_data:
            return
        
        metrics = self.comparison_data.get('metrics', {})
        
        # 设置表格
        self.params_table.setColumnCount(len(self.result_ids) + 1)
        self.params_table.setHorizontalHeaderLabels(['参数'] + [f"结果 {i+1}" for i in range(len(self.result_ids))])
        
        # 参数行
        data = [
            ('策略类型', 'strategy_type'),
            ('风险等级', 'risk_level'),
            ('最大股票数', 'max_stocks'),
            ('市值下限', 'market_cap_min'),
            ('市值上限', 'market_cap_max')
        ]
        
        self.params_table.setRowCount(len(data))
        
        for row, (label, key) in enumerate(data):
            # 参数列
            self.params_table.setItem(row, 0, QTableWidgetItem(label))
            
            # 各结果数据列
            for col, result_id in enumerate(self.result_ids):
                result_metrics = metrics.get(result_id, {})
                
                if key == 'market_cap_min':
                    value = result_metrics.get('market_cap_range', {}).get('min', '')
                    self.params_table.setItem(row, col + 1, QTableWidgetItem(str(value)))
                elif key == 'market_cap_max':
                    value = result_metrics.get('market_cap_range', {}).get('max', '')
                    self.params_table.setItem(row, col + 1, QTableWidgetItem(str(value)))
                else:
                    value = result_metrics.get(key, '')
                    self.params_table.setItem(row, col + 1, QTableWidgetItem(str(value)))
        
        self.params_table.horizontalHeader().setStretchLastSection(True)
    
    def _update_results_tab(self):
        """更新结果对比选项卡"""
        if not self.comparison_data:
            return
        
        results = self.comparison_data.get('results', {})
        
        # 收集所有股票
        all_stocks = set()
        for result_id, result_list in results.items():
            for result in result_list:
                all_stocks.add(result['stock_code'])
        
        # 设置表格
        self.results_table.setColumnCount(len(self.result_ids) + 1)
        self.results_table.setHorizontalHeaderLabels(['股票代码'] + [f"结果 {i+1}" for i in range(len(self.result_ids))])
        
        self.results_table.setRowCount(len(all_stocks))
        
        # 按股票代码排序
        sorted_stocks = sorted(list(all_stocks))
        
        for row, stock_code in enumerate(sorted_stocks):
            # 股票代码列
            self.results_table.setItem(row, 0, QTableWidgetItem(stock_code))
            
            # 各结果数据列
            for col, result_id in enumerate(self.result_ids):
                result_list = results.get(result_id, [])
                found = False
                
                for result in result_list:
                    if result['stock_code'] == stock_code:
                        # 显示评分和排名
                        score = result.get('score', 0)
                        rank = result_list.index(result) + 1
                        self.results_table.setItem(
                            row, 
                            col + 1, 
                            QTableWidgetItem(f"评分: {score:.2f}\n排名: {rank}")
                        )
                        found = True
                        break
                
                if not found:
                    self.results_table.setItem(row, col + 1, QTableWidgetItem("-"))
        
        self.results_table.horizontalHeader().setStretchLastSection(True)
    
    def _update_overlap_tab(self):
        """更新重叠度分析选项卡"""
        if not self.comparison_data:
            return
        
        overlap = self.comparison_data.get('overlap', {})
        
        # 设置表格
        self.overlap_table.setColumnCount(4)
        self.overlap_table.setHorizontalHeaderLabels(['对比', '交集数量', '并集数量', '重叠度'])
        
        self.overlap_table.setRowCount(len(overlap))
        
        for row, (key, data) in enumerate(overlap.items()):
            # 对比列
            self.overlap_table.setItem(row, 0, QTableWidgetItem(key.replace('_', ' vs ')))
            
            # 交集数量
            self.overlap_table.setItem(row, 1, QTableWidgetItem(str(data['intersection_count'])))
            
            # 并集数量
            self.overlap_table.setItem(row, 2, QTableWidgetItem(str(data['union_count'])))
            
            # 重叠度
            overlap_ratio = data['overlap_ratio'] * 100
            overlap_item = QTableWidgetItem(f"{overlap_ratio:.2f}%")
            
            # 根据重叠度设置颜色
            if overlap_ratio >= 70:
                overlap_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif overlap_ratio >= 40:
                overlap_item.setBackground(QColor(255, 255, 144))  # 浅黄色
            else:
                overlap_item.setBackground(QColor(255, 182, 193))  # 浅红色
            
            self.overlap_table.setItem(row, 3, overlap_item)
        
        self.overlap_table.horizontalHeader().setStretchLastSection(True)
        
        # 更新详细信息
        detail_text = "重叠度说明:\n"
        detail_text += "- 绿色: 重叠度 >= 70% (高度相似)\n"
        detail_text += "- 黄色: 重叠度 >= 40% (中度相似)\n"
        detail_text += "- 红色: 重叠度 < 40% (低度相似)\n\n"
        
        if overlap:
            first_key = list(overlap.keys())[0]
            first_data = overlap[first_key]
            detail_text += f"示例 ({first_key}):\n"
            detail_text += f"- 交集股票: {', '.join(first_data['intersection'][:10])}"
            if len(first_data['intersection']) > 10:
                detail_text += f" 等 {len(first_data['intersection'])} 只"
            detail_text += "\n"
        
        self.overlap_detail_label.setText(detail_text)
    
    def _update_metrics_tab(self):
        """更新性能指标对比选项卡"""
        if not self.comparison_data:
            return
        
        comparison = self.comparison_data.get('comparison', {})
        
        # 设置表格
        self.metrics_table.setColumnCount(len(self.result_ids) + 1)
        self.metrics_table.setHorizontalHeaderLabels(['指标'] + [f"结果 {i+1}" for i in range(len(self.result_ids))])
        
        # 性能指标行
        data = [
            ('股票数量', 'stock_counts'),
            ('平均评分', 'avg_scores'),
            ('评分范围', 'score_range'),
            ('选股日期', 'date_ranges')
        ]
        
        self.metrics_table.setRowCount(len(data))
        
        for row, (label, key) in enumerate(data):
            # 指标列
            self.metrics_table.setItem(row, 0, QTableWidgetItem(label))
            
            # 各结果数据列
            for col, result_id in enumerate(self.result_ids):
                if key == 'score_range':
                    score_range = comparison.get('score_ranges', {}).get(result_id, {})
                    min_score = score_range.get('min', 0)
                    max_score = score_range.get('max', 0)
                    self.metrics_table.setItem(row, col + 1, QTableWidgetItem(f"{min_score:.2f} - {max_score:.2f}"))
                elif key == 'avg_scores':
                    value = comparison.get('avg_scores', {}).get(result_id, 0)
                    self.metrics_table.setItem(row, col + 1, QTableWidgetItem(f"{value:.2f}"))
                else:
                    value = comparison.get(key, {}).get(result_id, '')
                    self.metrics_table.setItem(row, col + 1, QTableWidgetItem(str(value)))
        
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
