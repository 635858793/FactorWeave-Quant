#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预测准确性跟踪对话框

提供预测结果的记录和准确性跟踪功能，包括：
- 查看预测记录
- 准确性统计
- 准确性趋势图表
- 模型性能对比
"""

from loguru import logger
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLabel, QLineEdit, QComboBox, QDateEdit, QGroupBox,
    QFormLayout, QMessageBox, QSplitter, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QDate
from PyQt5.QtGui import QFont, QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from .base_dialog import BaseDialog


class PredictionAccuracyDialog(BaseDialog):
    """预测准确性跟踪对话框"""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="预测准确性跟踪",
            min_size=(1200, 800),
            settings_key="PredictionAccuracyDialog",
            modal=False
        )
        self.logger = logger.bind(module=__name__)
        
        # 服务引用
        self.tracking_service = None
        self.training_service = None
        self.service_container = None
        
        # 初始化服务
        self.init_services()
        
        # 数据
        self.records = []
        self.statistics = []
        self.trend_data = []
        
        # 定时器用于刷新数据
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(5000)  # 每5秒刷新一次
        
        # 初始化UI
        self.setup_ui()
        
        # 加载数据
        self._update_model_version_combo()
        self.load_statistics()

    def init_services(self):
        """初始化服务"""
        try:
            from core.containers import get_service_container
            from core.services.prediction_tracking_service import PredictionTrackingService
            from core.services.model_training_service import ModelTrainingService
            
            self.service_container = get_service_container()
            self.tracking_service = self.service_container.resolve(PredictionTrackingService)
            self.training_service = self.service_container.resolve(ModelTrainingService)
            
            if not self.tracking_service:
                raise ValueError("无法获取预测跟踪服务")
                
            self.logger.info("预测跟踪服务初始化成功")
        except Exception as e:
            self.logger.error(f"初始化预测跟踪服务失败: {e}")
            QMessageBox.critical(self, "错误", f"无法初始化预测跟踪服务: {e}")

    def setup_ui(self):
        """设置用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("预测准确性跟踪系统")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 标签页
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # 准确性统计标签页
        self.statistics_tab = self.create_statistics_tab()
        self.tabs.addTab(self.statistics_tab, "准确性统计")

        # 准确性趋势标签页
        self.trend_tab = self.create_trend_tab()
        self.tabs.addTab(self.trend_tab, "准确性趋势")

        # 预测记录标签页
        self.records_tab = self.create_records_tab()
        self.tabs.addTab(self.records_tab, "预测记录")

        # 底部按钮
        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_all)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

    def create_statistics_tab(self) -> QWidget:
        """创建准确性统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 筛选工具栏
        filter_toolbar = QHBoxLayout()
        filter_toolbar.addWidget(QLabel("模型版本:"))
        self.model_version_combo = QComboBox()
        self.model_version_combo.setEditable(True)
        self.model_version_combo.currentIndexChanged.connect(self.load_statistics)
        self.model_version_combo.editTextChanged.connect(self.load_statistics)
        filter_toolbar.addWidget(self.model_version_combo)
        
        filter_toolbar.addWidget(QLabel("预测类型:"))
        self.prediction_type_combo = QComboBox()
        self.prediction_type_combo.addItems(["", "pattern", "trend", "price", "sentiment"])
        self.prediction_type_combo.currentTextChanged.connect(self.load_statistics)
        filter_toolbar.addWidget(self.prediction_type_combo)
        
        filter_toolbar.addStretch()
        layout.addLayout(filter_toolbar)

        # 统计表格
        self.statistics_table = QTableWidget()
        self.statistics_table.setColumnCount(6)
        self.statistics_table.setHorizontalHeaderLabels([
            "模型版本", "预测类型", "时间周期", "总预测数", "正确预测数", "准确率"
        ])
        self.statistics_table.horizontalHeader().setStretchLastSection(True)
        self.statistics_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.statistics_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.statistics_table)

        return widget

    def create_trend_tab(self) -> QWidget:
        """创建准确性趋势标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 筛选工具栏
        filter_toolbar = QHBoxLayout()
        filter_toolbar.addWidget(QLabel("模型版本:"))
        self.trend_model_combo = QComboBox()
        self.trend_model_combo.setEditable(True)
        filter_toolbar.addWidget(self.trend_model_combo)
        
        filter_toolbar.addWidget(QLabel("预测类型:"))
        self.trend_type_combo = QComboBox()
        self.trend_type_combo.addItems(["pattern", "trend", "price", "sentiment"])
        filter_toolbar.addWidget(self.trend_type_combo)
        
        filter_toolbar.addWidget(QLabel("天数:"))
        self.days_spin = QComboBox()
        self.days_spin.addItems(["7", "14", "30", "60", "90"])
        self.days_spin.setCurrentText("30")
        filter_toolbar.addWidget(self.days_spin)
        
        update_btn = QPushButton("更新图表")
        update_btn.clicked.connect(self.update_trend_chart)
        filter_toolbar.addWidget(update_btn)
        filter_toolbar.addStretch()
        layout.addLayout(filter_toolbar)

        # 趋势图表
        self.trend_figure = Figure(figsize=(10, 6))
        self.trend_canvas = FigureCanvas(self.trend_figure)
        layout.addWidget(self.trend_canvas)

        return widget

    def create_records_tab(self) -> QWidget:
        """创建预测记录标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 筛选工具栏
        filter_toolbar = QHBoxLayout()
        filter_toolbar.addWidget(QLabel("模型版本:"))
        self.record_model_combo = QComboBox()
        self.record_model_combo.setEditable(True)
        self.record_model_combo.currentIndexChanged.connect(self.load_records)
        self.record_model_combo.editTextChanged.connect(self.load_records)
        filter_toolbar.addWidget(self.record_model_combo)
        
        filter_toolbar.addWidget(QLabel("预测类型:"))
        self.record_type_combo = QComboBox()
        self.record_type_combo.addItems(["", "pattern", "trend", "price", "sentiment"])
        self.record_type_combo.currentTextChanged.connect(self.load_records)
        filter_toolbar.addWidget(self.record_type_combo)
        
        filter_toolbar.addStretch()
        layout.addLayout(filter_toolbar)

        # 记录表格
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(6)
        self.records_table.setHorizontalHeaderLabels([
            "记录ID", "模型版本", "预测类型", "预测时间", "置信度", "准确性"
        ])
        self.records_table.horizontalHeader().setStretchLastSection(True)
        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.records_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.records_table.doubleClicked.connect(self.view_record_details)
        layout.addWidget(self.records_table)

        return widget

    def load_statistics(self):
        """加载准确性统计"""
        try:
            if not self.tracking_service:
                return

            model_version_id = self._get_selected_version_id(self.model_version_combo)
            prediction_type = self.prediction_type_combo.currentText() or None

            self.statistics = self.tracking_service.get_accuracy_statistics(
                model_version_id=model_version_id,
                prediction_type=prediction_type
            )

            self.statistics_table.setRowCount(len(self.statistics))

            for row, stat in enumerate(self.statistics):
                # 模型版本
                version_id = stat.get('model_version_id', '')
                # 尝试获取版本号
                if self.training_service:
                    version = self.training_service.get_model_version(version_id)
                    version_display = version.get('version_number', version_id) if version else version_id
                else:
                    version_display = version_id
                self.statistics_table.setItem(row, 0, QTableWidgetItem(version_display))
                # 预测类型
                self.statistics_table.setItem(row, 1, QTableWidgetItem(stat.get('prediction_type', '')))
                # 时间周期
                self.statistics_table.setItem(row, 2, QTableWidgetItem(stat.get('time_period', '')))
                # 总预测数
                self.statistics_table.setItem(row, 3, QTableWidgetItem(str(stat.get('total_predictions', 0))))
                # 正确预测数
                self.statistics_table.setItem(row, 4, QTableWidgetItem(str(stat.get('correct_predictions', 0))))
                # 准确率
                accuracy = stat.get('accuracy_rate', 0.0)
                accuracy_item = QTableWidgetItem(f"{accuracy:.2%}")
                if accuracy >= 0.8:
                    accuracy_item.setForeground(QColor(0, 128, 0))
                elif accuracy >= 0.6:
                    accuracy_item.setForeground(QColor(255, 165, 0))
                else:
                    accuracy_item.setForeground(QColor(255, 0, 0))
                self.statistics_table.setItem(row, 5, accuracy_item)

            self.statistics_table.resizeColumnsToContents()

            # 更新模型版本下拉框
            self._update_model_version_combo()

        except Exception as e:
            self.logger.error(f"加载准确性统计失败: {e}")

    def load_records(self):
        """加载预测记录"""
        try:
            if not self.tracking_service:
                return

            model_version_id = self._get_selected_version_id(self.record_model_combo)
            prediction_type = self.record_type_combo.currentText() or None

            self.records = self.tracking_service.get_prediction_records(
                model_version_id=model_version_id,
                prediction_type=prediction_type,
                limit=100
            )

            self.records_table.setRowCount(len(self.records))

            for row, record in enumerate(self.records):
                # 记录ID
                record_id = record.get('record_id', '')
                self.records_table.setItem(row, 0, QTableWidgetItem(record_id[:8] + '...' if len(record_id) > 8 else record_id))
                # 模型版本
                version_id = record.get('model_version_id', '')
                if self.training_service:
                    version = self.training_service.get_model_version(version_id)
                    version_display = version.get('version_number', version_id) if version else version_id
                else:
                    version_display = version_id
                self.records_table.setItem(row, 1, QTableWidgetItem(version_display))
                # 预测类型
                self.records_table.setItem(row, 2, QTableWidgetItem(record.get('prediction_type', '')))
                # 预测时间
                prediction_time = record.get('prediction_time', '')
                if prediction_time:
                    try:
                        dt = datetime.fromisoformat(prediction_time.replace('Z', '+00:00'))
                        prediction_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                self.records_table.setItem(row, 3, QTableWidgetItem(prediction_time))
                # 置信度
                confidence = record.get('confidence', 0.0)
                confidence_item = QTableWidgetItem(f"{confidence:.2%}")
                self.records_table.setItem(row, 4, confidence_item)
                # 准确性
                accuracy = record.get('accuracy')
                if accuracy is not None:
                    accuracy_item = QTableWidgetItem(f"{accuracy:.2%}")
                    if accuracy >= 0.8:
                        accuracy_item.setForeground(QColor(0, 128, 0))
                    elif accuracy >= 0.6:
                        accuracy_item.setForeground(QColor(255, 165, 0))
                    else:
                        accuracy_item.setForeground(QColor(255, 0, 0))
                else:
                    accuracy_item = QTableWidgetItem("未计算")
                self.records_table.setItem(row, 5, accuracy_item)

            self.records_table.resizeColumnsToContents()

            # 更新模型版本下拉框
            self._update_model_version_combo()

        except Exception as e:
            self.logger.error(f"加载预测记录失败: {e}")

    def update_trend_chart(self):
        """更新趋势图表"""
        try:
            if not self.tracking_service:
                return

            model_version_id = self._get_selected_version_id(self.trend_model_combo)
            prediction_type = self.trend_type_combo.currentText()
            days = int(self.days_spin.currentText())

            if not model_version_id:
                QMessageBox.warning(self, "警告", "请选择模型版本")
                return

            trend_data = self.tracking_service.get_accuracy_trend(
                model_version_id=model_version_id,
                prediction_type=prediction_type,
                days=days
            )

            if not trend_data:
                QMessageBox.information(self, "提示", "没有可用的趋势数据")
                return

            # 绘制图表
            self.trend_figure.clear()
            ax = self.trend_figure.add_subplot(111)

            dates = [datetime.fromisoformat(d['date'].replace('Z', '+00:00')) for d in trend_data]
            accuracies = [d['accuracy_rate'] for d in trend_data]
            total_predictions = [d['total_predictions'] for d in trend_data]

            # 绘制准确率曲线
            ax.plot(dates, accuracies, 'b-o', label='准确率', linewidth=2, markersize=6)
            ax.set_xlabel('日期', fontsize=10)
            ax.set_ylabel('准确率', fontsize=10)
            ax.set_title(f'{prediction_type} 预测准确性趋势 ({days}天)', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best')
            ax.set_ylim([0, 1])

            # 格式化x轴日期
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
            self.trend_figure.autofmt_xdate()

            # 添加预测数量信息
            ax2 = ax.twinx()
            ax2.bar(dates, total_predictions, alpha=0.3, color='green', label='预测数量')
            ax2.set_ylabel('预测数量', fontsize=10)
            ax2.legend(loc='upper right')

            self.trend_canvas.draw()

        except Exception as e:
            self.logger.error(f"更新趋势图表失败: {e}")
            QMessageBox.critical(self, "错误", f"更新趋势图表失败: {e}")

    def view_record_details(self):
        """查看记录详情"""
        current_row = self.records_table.currentRow()
        if current_row < 0:
            return

        record = self.records[current_row]
        import json
        record_info = json.dumps(record, indent=2, ensure_ascii=False)

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("预测记录详情")
        msg_box.setText("预测记录详情")
        msg_box.setDetailedText(record_info)
        msg_box.exec_()

    def _get_selected_version_id(self, combo: QComboBox) -> Optional[str]:
        """统一获取下拉框中选择的版本ID"""
        if combo is None:
            return None
        data = combo.currentData()
        if data:
            return data
        text = combo.currentText().strip()
        return text or None

    def _update_model_version_combo(self):
        """更新模型版本下拉框"""
        try:
            if not self.training_service:
                return

            versions = self.training_service.get_all_versions()
            version_ids = {v.get('version_id') for v in versions if v.get('version_id')}

            # 从统计中收集版本ID
            for stat in self.statistics:
                version_ids.add(stat.get('model_version_id'))

            # 从记录中收集版本ID
            for record in self.records:
                version_ids.add(record.get('model_version_id'))

            # 更新下拉框
            for combo in [self.model_version_combo, self.trend_model_combo, self.record_model_combo]:
                if combo is None:
                    continue
                current_data = combo.currentData()
                current_text = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("", None)
                for version_id in sorted(filter(None, version_ids)):
                    version = next((v for v in versions if v.get('version_id') == version_id), None)
                    if not version:
                        version = self.training_service.get_model_version(version_id)
                    display_text = version.get('version_number', version_id) if version else version_id
                    combo.addItem(f"{display_text} ({version_id[:8]})", version_id)

                # 恢复之前的选择
                if current_data:
                    idx = combo.findData(current_data)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    else:
                        combo.setCurrentIndex(0)
                elif current_text:
                    idx = combo.findText(current_text)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    else:
                        combo.setCurrentIndex(0)
                else:
                    combo.setCurrentIndex(0)
                combo.blockSignals(False)

        except Exception as e:
            self.logger.error(f"更新模型版本下拉框失败: {e}")

    def refresh_data(self):
        """刷新数据"""
        current_index = self.tabs.currentIndex()
        if current_index == 0:  # 准确性统计标签页
            self.load_statistics()
        elif current_index == 2:  # 预测记录标签页
            self.load_records()

    def refresh_all(self):
        """刷新所有数据"""
        self.load_statistics()
        self.load_records()
        if self.tabs.currentIndex() == 1:  # 准确性趋势标签页
            self.update_trend_chart()

    def closeEvent(self, event):
        """关闭事件"""
        self.refresh_timer.stop()
        super().closeEvent(event)

