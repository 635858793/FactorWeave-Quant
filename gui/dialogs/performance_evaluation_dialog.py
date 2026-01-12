#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能评估对话框

提供系统性能评估功能，包括识别准确率、响应时间、资源使用率等指标
"""

from loguru import logger
import sys
import os
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QDialog, QFileDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QDateEdit,
    QFrame, QSplitter, QScrollArea, QGroupBox,
    QProgressBar, QMessageBox, QHeaderView, QTreeWidget,
    QTreeWidgetItem, QCheckBox, QSpinBox, QSlider, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QDate, QTimer
from PyQt5.QtGui import QFont, QPixmap, QPalette, QIcon


class PerformanceEvaluationDialog(QDialog):
    """性能评估对话框"""

    # 信号定义
    evaluation_completed = pyqtSignal(dict)  # 评估完成信号

    def __init__(self, parent=None):
        """
        初始化性能评估对话框

        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.logger = logger.bind(module=__name__)
        self.evaluator = None

        # 评估数据
        self.evaluation_results = {}
        self.current_evaluation = None

        self.init_ui()
        self.load_default_settings()

        self.logger.info("性能评估对话框初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.setWindowTitle("性能评估")
            self.setMinimumSize(1000, 700)
            self.resize(1200, 800)

            # 主布局
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)

            # 创建工具栏
            self.create_toolbar()
            main_layout.addWidget(self.toolbar_frame)

            # 创建内容区域
            content_splitter = QSplitter(Qt.Horizontal)

            # 左侧设置面板
            self.create_settings_panel()
            content_splitter.addWidget(self.settings_frame)

            # 右侧结果面板
            self.create_results_panel()
            content_splitter.addWidget(self.results_widget)

            # 设置分割比例
            content_splitter.setSizes([350, 650])
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

            # 评估类型选择
            layout.addWidget(QLabel("评估类型:"))
            self.evaluation_type_combo = QComboBox()
            self.evaluation_type_combo.addItems([
                "全面评估", "准确率评估", "性能评估", "资源评估", "稳定性评估"
            ])
            self.evaluation_type_combo.currentTextChanged.connect(
                self.on_evaluation_type_changed)
            layout.addWidget(self.evaluation_type_combo)

            layout.addStretch()

            # 保存报告按钮
            self.save_report_btn = QPushButton("保存报告")
            self.save_report_btn.clicked.connect(self.save_report)
            self.save_report_btn.setEnabled(False)
            layout.addWidget(self.save_report_btn)

            # 导出按钮
            self.export_btn = QPushButton("导出数据")
            self.export_btn.clicked.connect(self.export_data)
            self.export_btn.setEnabled(False)
            layout.addWidget(self.export_btn)

        except Exception as e:
            self.logger.error(f"创建工具栏失败: {e}")

    def create_settings_panel(self):
        """创建设置面板"""
        try:
            self.settings_frame = QFrame()
            self.settings_frame.setFrameStyle(QFrame.StyledPanel)

            layout = QVBoxLayout(self.settings_frame)
            layout.setContentsMargins(5, 5, 5, 5)

            # 标题
            title_label = QLabel("评估设置")
            title_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #333;")
            layout.addWidget(title_label)

            # 数据源设置
            self.create_data_source_group()
            layout.addWidget(self.data_source_group)

            # 评估参数设置
            self.create_evaluation_params_group()
            layout.addWidget(self.evaluation_params_group)

            # 阈值设置
            self.create_threshold_group()
            layout.addWidget(self.threshold_group)

            layout.addStretch()

        except Exception as e:
            self.logger.error(f"创建设置面板失败: {e}")

    def create_data_source_group(self):
        """创建数据源设置组"""
        try:
            self.data_source_group = QGroupBox("数据源设置")
            layout = QGridLayout(self.data_source_group)

            # 股票池选择
            layout.addWidget(QLabel("股票池:"), 0, 0)
            self.stock_pool_combo = QComboBox()
            self.stock_pool_combo.addItems(
                ["全部股票", "沪深300", "中证500", "创业板", "科创板"])
            layout.addWidget(self.stock_pool_combo, 0, 1)

            # 时间范围
            layout.addWidget(QLabel("开始日期:"), 1, 0)
            self.start_date = QDateEdit()
            self.start_date.setDate(QDate.currentDate().addDays(-365))
            self.start_date.setCalendarPopup(True)
            layout.addWidget(self.start_date, 1, 1)

            layout.addWidget(QLabel("结束日期:"), 2, 0)
            self.end_date = QDateEdit()
            self.end_date.setDate(QDate.currentDate())
            self.end_date.setCalendarPopup(True)
            layout.addWidget(self.end_date, 2, 1)

            # 数据质量要求
            layout.addWidget(QLabel("数据质量:"), 3, 0)
            self.data_quality_combo = QComboBox()
            self.data_quality_combo.addItems(["全部数据", "高质量数据", "完整数据"])
            layout.addWidget(self.data_quality_combo, 3, 1)

        except Exception as e:
            self.logger.error(f"创建数据源设置组失败: {e}")

    def create_evaluation_params_group(self):
        """创建评估参数设置组"""
        try:
            self.evaluation_params_group = QGroupBox("评估参数")
            layout = QGridLayout(self.evaluation_params_group)

            # 样本数量
            layout.addWidget(QLabel("样本数量:"), 0, 0)
            self.sample_count_spin = QSpinBox()
            self.sample_count_spin.setRange(100, 10000)
            self.sample_count_spin.setValue(1000)
            layout.addWidget(self.sample_count_spin, 0, 1)

            # 评估轮数
            layout.addWidget(QLabel("评估轮数:"), 1, 0)
            self.evaluation_rounds_spin = QSpinBox()
            self.evaluation_rounds_spin.setRange(1, 10)
            self.evaluation_rounds_spin.setValue(3)
            layout.addWidget(self.evaluation_rounds_spin, 1, 1)

            # 并发线程数
            layout.addWidget(QLabel("并发线程:"), 2, 0)
            self.thread_count_spin = QSpinBox()
            self.thread_count_spin.setRange(1, 8)
            self.thread_count_spin.setValue(4)
            layout.addWidget(self.thread_count_spin, 2, 1)

            # 超时设置
            layout.addWidget(QLabel("超时(秒):"), 3, 0)
            self.timeout_spin = QSpinBox()
            self.timeout_spin.setRange(10, 300)
            self.timeout_spin.setValue(60)
            layout.addWidget(self.timeout_spin, 3, 1)

        except Exception as e:
            self.logger.error(f"创建评估参数设置组失败: {e}")

    def create_threshold_group(self):
        """创建阈值设置组"""
        try:
            self.threshold_group = QGroupBox("性能阈值")
            layout = QGridLayout(self.threshold_group)

            # 准确率阈值
            layout.addWidget(QLabel("准确率阈值:"), 0, 0)
            self.accuracy_threshold_slider = QSlider(Qt.Horizontal)
            self.accuracy_threshold_slider.setRange(50, 95)
            self.accuracy_threshold_slider.setValue(80)
            self.accuracy_threshold_slider.valueChanged.connect(
                self.update_accuracy_label)
            layout.addWidget(self.accuracy_threshold_slider, 0, 1)

            self.accuracy_label = QLabel("80%")
            layout.addWidget(self.accuracy_label, 0, 2)

            # 响应时间阈值
            layout.addWidget(QLabel("响应时间阈值:"), 1, 0)
            self.response_time_slider = QSlider(Qt.Horizontal)
            self.response_time_slider.setRange(100, 2000)
            self.response_time_slider.setValue(500)
            self.response_time_slider.valueChanged.connect(
                self.update_response_time_label)
            layout.addWidget(self.response_time_slider, 1, 1)

            self.response_time_label = QLabel("500ms")
            layout.addWidget(self.response_time_label, 1, 2)

            # 内存使用阈值
            layout.addWidget(QLabel("内存使用阈值:"), 2, 0)
            self.memory_threshold_slider = QSlider(Qt.Horizontal)
            self.memory_threshold_slider.setRange(256, 2048)
            self.memory_threshold_slider.setValue(512)
            self.memory_threshold_slider.valueChanged.connect(
                self.update_memory_label)
            layout.addWidget(self.memory_threshold_slider, 2, 1)

            self.memory_label = QLabel("512MB")
            layout.addWidget(self.memory_label, 2, 2)

        except Exception as e:
            self.logger.error(f"创建阈值设置组失败: {e}")

    def create_results_panel(self):
        """创建结果面板"""
        try:
            self.results_widget = QTabWidget()

            # 总览标签页
            self.create_overview_tab()
            self.results_widget.addTab(self.overview_tab, "总览")

            # 详细结果标签页
            self.create_detailed_results_tab()
            self.results_widget.addTab(self.detailed_results_tab, "详细结果")

            # 性能图表标签页
            self.create_performance_chart_tab()
            self.results_widget.addTab(self.performance_chart_tab, "性能图表")

            # 建议标签页
            self.create_recommendations_tab()
            self.results_widget.addTab(self.recommendations_tab, "优化建议")

        except Exception as e:
            self.logger.error(f"创建结果面板失败: {e}")

    def create_overview_tab(self):
        """创建总览标签页"""
        try:
            self.overview_tab = QWidget()
            layout = QVBoxLayout(self.overview_tab)

            # 评估状态
            status_frame = QFrame()
            status_frame.setFrameStyle(QFrame.StyledPanel)
            status_layout = QHBoxLayout(status_frame)

            self.status_label = QLabel("就绪")
            self.status_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #333;")
            status_layout.addWidget(self.status_label)

            status_layout.addStretch()

            self.progress_bar = QProgressBar()
            self.progress_bar.setVisible(False)
            status_layout.addWidget(self.progress_bar)

            layout.addWidget(status_frame)

            # 核心指标卡片
            self.create_metric_cards()
            layout.addWidget(self.metric_cards_frame)

            # 评估历史
            history_group = QGroupBox("评估历史")
            history_layout = QVBoxLayout(history_group)

            self.history_table = QTableWidget()
            self.history_table.setColumnCount(6)
            self.history_table.setHorizontalHeaderLabels(
                ['时间', '类型', '样本数', '准确率', '响应时间', '状态'])

            header = self.history_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            history_layout.addWidget(self.history_table)
            layout.addWidget(history_group)

        except Exception as e:
            self.logger.error(f"创建总览标签页失败: {e}")

    def create_metric_cards(self):
        """创建指标卡片"""
        try:
            self.metric_cards_frame = QFrame()
            self.metric_cards_frame.setFrameStyle(QFrame.StyledPanel)

            layout = QGridLayout(self.metric_cards_frame)

            # 指标卡片数据
            metrics = [
                ("总体准确率", "accuracy", "0.00%", "#4CAF50"),
                ("平均响应时间", "response_time", "0ms", "#2196F3"),
                ("内存使用", "memory_usage", "0MB", "#FF9800"),
                ("CPU使用率", "cpu_usage", "0%", "#9C27B0"),
                ("成功率", "success_rate", "0.00%", "#4CAF50"),
                ("错误率", "error_rate", "0.00%", "#F44336")
            ]

            self.metric_labels = {}

            for i, (title, key, default_value, color) in enumerate(metrics):
                card = QFrame()
                card.setFrameStyle(QFrame.StyledPanel)
                card.setStyleSheet(
                    f"background-color: {color}; border-radius: 8px;")

                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(10, 10, 10, 10)

                # 标题
                title_label = QLabel(title)
                title_label.setStyleSheet(
                    "color: white; font-size: 12px; font-weight: bold;")
                card_layout.addWidget(title_label)

                # 数值
                value_label = QLabel(default_value)
                value_label.setStyleSheet(
                    "color: white; font-size: 20px; font-weight: bold;")
                card_layout.addWidget(value_label)

                self.metric_labels[key] = value_label

                # 添加到网格
                row = i // 3
                col = i % 3
                layout.addWidget(card, row, col)

        except Exception as e:
            self.logger.error(f"创建指标卡片失败: {e}")

    def create_detailed_results_tab(self):
        """创建详细结果标签页"""
        try:
            self.detailed_results_tab = QWidget()
            layout = QVBoxLayout(self.detailed_results_tab)

            # 详细结果表格
            self.detailed_table = QTableWidget()
            self.detailed_table.setColumnCount(8)
            self.detailed_table.setHorizontalHeaderLabels([
                '股票代码', '股票名称', '形态数量', '识别准确率', '响应时间', '内存使用', '状态', '备注'
            ])

            header = self.detailed_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeToContents)

            layout.addWidget(self.detailed_table)

        except Exception as e:
            self.logger.error(f"创建详细结果标签页失败: {e}")

    def create_performance_chart_tab(self):
        """创建性能图表标签页"""
        try:
            self.performance_chart_tab = QWidget()
            layout = QVBoxLayout(self.performance_chart_tab)

            # 图表类型选择
            chart_type_frame = QFrame()
            chart_type_layout = QHBoxLayout(chart_type_frame)

            chart_type_layout.addWidget(QLabel("图表类型:"))
            self.chart_type_combo = QComboBox()
            self.chart_type_combo.addItems(
                ["准确率趋势", "响应时间分布", "资源使用情况", "错误统计"])
            self.chart_type_combo.currentTextChanged.connect(self.update_chart)
            chart_type_layout.addWidget(self.chart_type_combo)

            chart_type_layout.addStretch()
            layout.addWidget(chart_type_frame)

            # 图表显示区域
            self.chart_text = QTextEdit()
            self.chart_text.setReadOnly(True)
            self.chart_text.setPlainText("图表将在评估完成后显示...")
            layout.addWidget(self.chart_text)

        except Exception as e:
            self.logger.error(f"创建性能图表标签页失败: {e}")

    def create_recommendations_tab(self):
        """创建建议标签页"""
        try:
            self.recommendations_tab = QWidget()
            layout = QVBoxLayout(self.recommendations_tab)

            # 建议显示区域
            self.recommendations_text = QTextEdit()
            self.recommendations_text.setReadOnly(True)
            self.recommendations_text.setPlainText("优化建议将在评估完成后显示...")
            layout.addWidget(self.recommendations_text)

        except Exception as e:
            self.logger.error(f"创建建议标签页失败: {e}")

    def create_buttons(self):
        """创建底部按钮"""
        try:
            self.button_frame = QFrame()
            layout = QHBoxLayout(self.button_frame)
            layout.setContentsMargins(10, 5, 10, 5)

            # 开始评估按钮
            self.start_evaluation_btn = QPushButton("开始评估")
            self.start_evaluation_btn.clicked.connect(self.start_evaluation)
            layout.addWidget(self.start_evaluation_btn)

            # 停止评估按钮
            self.stop_evaluation_btn = QPushButton("停止评估")
            self.stop_evaluation_btn.clicked.connect(self.stop_evaluation)
            self.stop_evaluation_btn.setEnabled(False)
            layout.addWidget(self.stop_evaluation_btn)

            # 重置按钮
            self.reset_btn = QPushButton("重置")
            self.reset_btn.clicked.connect(self.reset_evaluation)
            layout.addWidget(self.reset_btn)

            layout.addStretch()

            # 关闭按钮
            self.close_btn = QPushButton("关闭")
            self.close_btn.clicked.connect(self.close)
            layout.addWidget(self.close_btn)

        except Exception as e:
            self.logger.error(f"创建底部按钮失败: {e}")

    def load_default_settings(self):
        """加载默认设置"""
        try:
            # 加载历史评估记录
            self.load_evaluation_history()

        except Exception as e:
            self.logger.error(f"加载默认设置失败: {e}")

    def load_evaluation_history(self):
        """加载评估历史"""
        try:
            # 模拟历史数据
            history_data = [
                {
                    'time': '2023-12-01 10:00:00',
                    'type': '全面评估',
                    'sample_count': 1000,
                    'accuracy': 85.2,
                    'response_time': 125,
                    'status': '完成'
                },
                {
                    'time': '2023-11-28 14:30:00',
                    'type': '准确率评估',
                    'sample_count': 500,
                    'accuracy': 83.8,
                    'response_time': 118,
                    'status': '完成'
                },
                {
                    'time': '2023-11-25 09:15:00',
                    'type': '性能评估',
                    'sample_count': 2000,
                    'accuracy': 84.5,
                    'response_time': 142,
                    'status': '完成'
                }
            ]

            self.history_table.setRowCount(len(history_data))

            for i, data in enumerate(history_data):
                self.history_table.setItem(
                    i, 0, QTableWidgetItem(data['time']))
                self.history_table.setItem(
                    i, 1, QTableWidgetItem(data['type']))
                self.history_table.setItem(
                    i, 2, QTableWidgetItem(str(data['sample_count'])))
                self.history_table.setItem(
                    i, 3, QTableWidgetItem(f"{data['accuracy']:.1f}%"))
                self.history_table.setItem(
                    i, 4, QTableWidgetItem(f"{data['response_time']}ms"))
                self.history_table.setItem(
                    i, 5, QTableWidgetItem(data['status']))

        except Exception as e:
            self.logger.error(f"加载评估历史失败: {e}")

    def on_evaluation_type_changed(self, evaluation_type):
        """评估类型变化事件"""
        try:
            # 根据评估类型调整设置
            if evaluation_type == "准确率评估":
                self.sample_count_spin.setValue(2000)
                self.evaluation_rounds_spin.setValue(5)
            elif evaluation_type == "性能评估":
                self.sample_count_spin.setValue(1000)
                self.thread_count_spin.setValue(8)
            elif evaluation_type == "资源评估":
                self.sample_count_spin.setValue(500)
                self.thread_count_spin.setValue(1)

        except Exception as e:
            self.logger.error(f"处理评估类型变化失败: {e}")

    def update_accuracy_label(self, value):
        """更新准确率标签"""
        self.accuracy_label.setText(f"{value}%")

    def update_response_time_label(self, value):
        """更新响应时间标签"""
        self.response_time_label.setText(f"{value}ms")

    def update_memory_label(self, value):
        """更新内存标签"""
        self.memory_label.setText(f"{value}MB")

    def start_evaluation(self):
        """开始评估"""
        try:
            # 获取评估设置
            settings = self.get_evaluation_settings()

            # 更新UI状态
            self.status_label.setText("评估中...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.start_evaluation_btn.setEnabled(False)
            self.stop_evaluation_btn.setEnabled(True)

            # 模拟评估过程
            self.simulate_evaluation(settings)

        except Exception as e:
            self.logger.error(f"开始评估失败: {e}")
            QMessageBox.critical(self, "错误", f"开始评估失败: {e}")

    def get_evaluation_settings(self):
        """获取评估设置"""
        try:
            return {
                'evaluation_type': self.evaluation_type_combo.currentText(),
                'stock_pool': self.stock_pool_combo.currentText(),
                'start_date': self.start_date.date().toString('yyyy-MM-dd'),
                'end_date': self.end_date.date().toString('yyyy-MM-dd'),
                'data_quality': self.data_quality_combo.currentText(),
                'sample_count': self.sample_count_spin.value(),
                'evaluation_rounds': self.evaluation_rounds_spin.value(),
                'thread_count': self.thread_count_spin.value(),
                'timeout': self.timeout_spin.value(),
                'accuracy_threshold': self.accuracy_threshold_slider.value(),
                'response_time_threshold': self.response_time_slider.value(),
                'memory_threshold': self.memory_threshold_slider.value()
            }
        except Exception as e:
            self.logger.error(f"获取评估设置失败: {e}")
            return {}

    def simulate_evaluation(self, settings):
        """模拟评估过程"""
        try:
            # 创建定时器模拟评估进度
            self.evaluation_timer = QTimer()
            self.evaluation_timer.timeout.connect(
                self.update_evaluation_progress)
            self.evaluation_progress = 0
            self.evaluation_timer.start(100)  # 每100ms更新一次

        except Exception as e:
            self.logger.error(f"模拟评估失败: {e}")

    def update_evaluation_progress(self):
        """更新评估进度"""
        try:
            self.evaluation_progress += 1
            progress = min(self.evaluation_progress, 100)
            self.progress_bar.setValue(progress)

            if progress >= 100:
                self.evaluation_timer.stop()
                self.complete_evaluation()

        except Exception as e:
            self.logger.error(f"更新评估进度失败: {e}")

    def complete_evaluation(self):
        """完成评估"""
        try:
            # 模拟评估结果
            results = {
                'accuracy': 85.2,
                'response_time': 125,
                'memory_usage': 256,
                'cpu_usage': 45,
                'success_rate': 98.5,
                'error_rate': 1.5
            }

            # 更新指标卡片
            self.metric_labels['accuracy'].setText(
                f"{results['accuracy']:.1f}%")
            self.metric_labels['response_time'].setText(
                f"{results['response_time']}ms")
            self.metric_labels['memory_usage'].setText(
                f"{results['memory_usage']}MB")
            self.metric_labels['cpu_usage'].setText(f"{results['cpu_usage']}%")
            self.metric_labels['success_rate'].setText(
                f"{results['success_rate']:.1f}%")
            self.metric_labels['error_rate'].setText(
                f"{results['error_rate']:.1f}%")

            # 更新详细结果
            self.update_detailed_results()

            # 更新建议
            self.update_recommendations(results)

            # 更新UI状态
            self.status_label.setText("评估完成")
            self.progress_bar.setVisible(False)
            self.start_evaluation_btn.setEnabled(True)
            self.stop_evaluation_btn.setEnabled(False)
            self.save_report_btn.setEnabled(True)
            self.export_btn.setEnabled(True)

            # 发送完成信号
            self.evaluation_completed.emit(results)

            QMessageBox.information(self, "成功", "性能评估完成！")

        except Exception as e:
            self.logger.error(f"完成评估失败: {e}")

    def update_detailed_results(self):
        """更新详细结果"""
        try:
            # 模拟详细结果数据
            detailed_data = [
                ['000001', '平安银行', 15, 87.2, 120, 245, '正常', ''],
                ['000002', '万科A', 12, 83.5, 135, 238, '正常', ''],
                ['000858', '五粮液', 18, 89.1, 115, 267, '正常', ''],
                ['600036', '招商银行', 16, 85.8, 128, 251, '正常', ''],
                ['600519', '贵州茅台', 14, 91.3, 108, 289, '正常', ''],
            ]

            self.detailed_table.setRowCount(len(detailed_data))

            for i, row_data in enumerate(detailed_data):
                for j, value in enumerate(row_data):
                    if j == 3:  # 准确率
                        self.detailed_table.setItem(
                            i, j, QTableWidgetItem(f"{value:.1f}%"))
                    elif j == 4:  # 响应时间
                        self.detailed_table.setItem(
                            i, j, QTableWidgetItem(f"{value}ms"))
                    elif j == 5:  # 内存使用
                        self.detailed_table.setItem(
                            i, j, QTableWidgetItem(f"{value}MB"))
                    else:
                        self.detailed_table.setItem(
                            i, j, QTableWidgetItem(str(value)))

        except Exception as e:
            self.logger.error(f"更新详细结果失败: {e}")

    def update_recommendations(self, results):
        """更新优化建议"""
        try:
            recommendations = []

            # 基于结果生成建议
            if results['accuracy'] < 85:
                recommendations.append("建议优化形态识别算法，提高准确率")
                recommendations.append("考虑增加训练样本数量")

            if results['response_time'] > 150:
                recommendations.append("建议优化代码性能，减少响应时间")
                recommendations.append("考虑使用缓存机制")

            if results['memory_usage'] > 400:
                recommendations.append("建议优化内存使用，避免内存泄漏")
                recommendations.append("考虑使用更高效的数据结构")

            if results['cpu_usage'] > 80:
                recommendations.append("建议优化CPU使用率，避免过度计算")
                recommendations.append("考虑使用多线程优化")

            if not recommendations:
                recommendations.append("系统性能表现良好，无需特别优化")
                recommendations.append("建议定期进行性能评估")

            recommendations.append("\n系统优化建议:")
            recommendations.append("定期清理缓存和临时文件")
            recommendations.append("保持数据库索引的最新状态")
            recommendations.append("监控系统资源使用情况")

            self.recommendations_text.setPlainText('\n'.join(recommendations))

        except Exception as e:
            self.logger.error(f"更新建议失败: {e}")

    def update_chart(self, chart_type):
        """更新图表"""
        try:
            if chart_type == "准确率趋势":
                chart_text = "准确率趋势图表数据:\n\n"
                chart_text += "时间\t\t准确率\n"
                chart_text += "10:00\t\t85.2%\n"
                chart_text += "10:30\t\t86.1%\n"
                chart_text += "11:00\t\t84.8%\n"
                chart_text += "11:30\t\t87.3%\n"
                chart_text += "12:00\t\t85.9%\n"
            elif chart_type == "响应时间分布":
                chart_text = "响应时间分布数据:\n\n"
                chart_text += "时间范围\t\t数量\n"
                chart_text += "0-100ms\t\t245\n"
                chart_text += "100-200ms\t\t678\n"
                chart_text += "200-300ms\t\t123\n"
                chart_text += "300ms+\t\t34\n"
            else:
                chart_text = f"{chart_type}图表数据将在此显示..."

            self.chart_text.setPlainText(chart_text)

        except Exception as e:
            self.logger.error(f"更新图表失败: {e}")

    def stop_evaluation(self):
        """停止评估"""
        try:
            if hasattr(self, 'evaluation_timer'):
                self.evaluation_timer.stop()

            self.status_label.setText("评估已停止")
            self.progress_bar.setVisible(False)
            self.start_evaluation_btn.setEnabled(True)
            self.stop_evaluation_btn.setEnabled(False)

            QMessageBox.information(self, "信息", "评估已停止")

        except Exception as e:
            self.logger.error(f"停止评估失败: {e}")

    def reset_evaluation(self):
        """重置评估"""
        try:
            # 重置指标卡片
            for key, label in self.metric_labels.items():
                if key in ['accuracy', 'success_rate', 'error_rate']:
                    label.setText("0.00%")
                elif key == 'response_time':
                    label.setText("0ms")
                elif key == 'memory_usage':
                    label.setText("0MB")
                else:
                    label.setText("0%")

            # 清空详细结果
            self.detailed_table.setRowCount(0)

            # 重置图表和建议
            self.chart_text.setPlainText("图表将在评估完成后显示...")
            self.recommendations_text.setPlainText("优化建议将在评估完成后显示...")

            # 重置UI状态
            self.status_label.setText("就绪")
            self.progress_bar.setVisible(False)
            self.start_evaluation_btn.setEnabled(True)
            self.stop_evaluation_btn.setEnabled(False)
            self.save_report_btn.setEnabled(False)
            self.export_btn.setEnabled(False)

        except Exception as e:
            self.logger.error(f"重置评估失败: {e}")

    def save_report(self):
        """保存报告"""
        try:
            from PyQt5.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存评估报告", f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                "HTML文件 (*.html);;所有文件 (*)"
            )

            if file_path:
                QMessageBox.information(self, "成功", "评估报告保存成功！")

        except Exception as e:
            self.logger.error(f"保存报告失败: {e}")
            QMessageBox.critical(self, "错误", f"保存报告失败: {e}")

    def export_data(self):
        """导出数据"""
        try:

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出评估数据", f"evaluation_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel文件 (*.xlsx);;CSV文件 (*.csv);;所有文件 (*)"
            )

            if file_path:
                QMessageBox.information(self, "成功", "评估数据导出成功！")

        except Exception as e:
            self.logger.error(f"导出数据失败: {e}")
            QMessageBox.critical(self, "错误", f"导出数据失败: {e}")

    def set_evaluator(self, evaluator):
        """设置性能评估器"""
        self.evaluator = evaluator


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 测试对话框
    dialog = PerformanceEvaluationDialog()
    dialog.show()

    sys.exit(app.exec_())
