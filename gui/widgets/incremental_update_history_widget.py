#!/usr/bin/env python3
"""
增量更新历史UI组件

提供增量更新历史记录查看和管理功能
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QLabel, QComboBox,
                             QSpinBox, QDateEdit, QDateTimeEdit, QLineEdit,
                             QMessageBox, QToolBar, QHeaderView, QMenu,
                             QAction, QStyledItemDelegate, QStyle,
                             QCheckBox, QGroupBox, QSplitter, QTextEdit,
                             QTabWidget, QProgressBar, QDialog, QDialogButtonBox)
from PyQt5.QtCore import Qt, QTimer, QDateTime, pyqtSignal, QDate
from PyQt5.QtGui import QIcon, QFont, QColor
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger

try:
    CORE_AVAILABLE = True
    from core.services.incremental_update_recorder import get_incremental_update_recorder, UpdateRecord, UpdateTask
    from core.services.breakpoint_resume_manager import get_breakpoint_resume_manager, BreakpointState
    from core.plugin_types import AssetType, DataType
except ImportError as e:
    logger.warning(f"无法导入核心组件: {e}")
    CORE_AVAILABLE = False


class UpdateHistoryWidget(QWidget):
    """增量更新历史管理组件"""

    # 信号定义
    record_selected = pyqtSignal(dict)              # 记录被选中
    record_deleted = pyqtSignal(str)                # 记录被删除
    task_status_changed = pyqtSignal(str, str)      # 任务状态变更
    export_requested = pyqtSignal(str, str)        # 导出请求

    def __init__(self, parent=None):
        super().__init__(parent)
        self.records: List[Dict[str, Any]] = []
        self.filtered_records: List[Dict[str, Any]] = []
        self.selected_record_id: Optional[str] = None
        self.setup_ui()
        self.setup_connections()
        self.load_records()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 工具栏
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # 过滤器区域
        filter_group = self.create_filter_group()
        layout.addWidget(filter_group)

        # 主要内容区域
        splitter = QSplitter(Qt.Horizontal)

        # 记录列表
        self.table = self.create_record_table()
        splitter.addWidget(self.table)

        # 详细信息面板
        detail_widget = self.create_detail_panel()
        splitter.addWidget(detail_widget)

        splitter.setStretchFactor(0, 60)  # 记录列表占60%
        splitter.setStretchFactor(1, 40)  # 详细信息占40%

        layout.addWidget(splitter)

        # 统计信息
        self.stats_label = QLabel()
        layout.addWidget(self.stats_label)

        self.setLayout(layout)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()

        # 刷新按钮
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_records)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # 导出按钮
        export_action = QAction("导出", self)
        export_action.triggered.connect(self.export_records)
        toolbar.addAction(export_action)

        # 清除过期记录
        clear_action = QAction("清除过期记录", self)
        clear_action.triggered.connect(self.clear_expired_records)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()

        # 自动刷新
        self.auto_refresh_cb = QCheckBox("自动刷新")
        self.auto_refresh_cb.setChecked(True)
        toolbar.addWidget(self.auto_refresh_cb)

        # 自动刷新间隔
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(1, 60)
        self.refresh_interval.setValue(5)
        self.refresh_interval.setSuffix(" 秒")
        self.refresh_interval.setEnabled(True)
        toolbar.addWidget(QLabel("刷新间隔:"))
        toolbar.addWidget(self.refresh_interval)

        return toolbar

    def create_filter_group(self):
        """创建过滤器组"""
        group = QGroupBox("过滤条件")
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 任务名称
        layout.addWidget(QLabel("任务名称:"))
        self.task_name_filter = QLineEdit()
        self.task_name_filter.setPlaceholderText("输入任务名称过滤...")
        self.task_name_filter.textChanged.connect(self.apply_filters)
        layout.addWidget(self.task_name_filter)

        # 状态
        layout.addWidget(QLabel("状态:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部", "待开始", "进行中", "已完成", "失败", "已停止"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        layout.addWidget(self.status_filter)

        # 时间范围
        layout.addWidget(QLabel("开始时间:"))
        self.start_date_filter = QDateEdit()
        self.start_date_filter.setCalendarPopup(True)
        self.start_date_filter.setDate(QDate.currentDate().addDays(-30))
        self.start_date_filter.setDateTime(QDateTime.currentDateTime().addDays(-30))
        self.start_date_filter.dateTimeChanged.connect(self.apply_filters)
        layout.addWidget(self.start_date_filter)

        layout.addWidget(QLabel("结束时间:"))
        self.end_date_filter = QDateEdit()
        self.end_date_filter.setCalendarPopup(True)
        self.end_date_filter.setDateTime(QDateTime.currentDateTime())
        self.end_date_filter.dateTimeChanged.connect(self.apply_filters)
        layout.addWidget(self.end_date_filter)

        layout.addStretch()

        # 统计信息
        self.filter_stats = QLabel("共 0 条记录")
        layout.addWidget(self.filter_stats)

        group.setLayout(layout)
        return group

    def create_record_table(self):
        """创建记录表格"""
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "任务ID", "任务名称", "股票代码", "数据类型", "开始时间", "结束时间",
            "状态", "进度", "操作"
        ])

        # 设置列宽
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # 任务ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)     # 任务名称
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # 股票代码
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # 数据类型
        header.setSectionResizeMode(4, QHeaderView.Interactive)  # 开始时间
        header.setSectionResizeMode(5, QHeaderView.Interactive)  # 结束时间
        header.setSectionResizeMode(6, QHeaderView.Interactive)  # 状态
        header.setSectionResizeMode(7, QHeaderView.Interactive)  # 进度
        header.setSectionResizeMode(8, QHeaderView.Interactive)  # 操作

        # 设置选择模式
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        # 启用排序
        table.setSortingEnabled(True)

        return table

    def create_detail_panel(self):
        """创建详细信息面板"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 选项卡
        tab_widget = QTabWidget()

        # 基本信息选项卡
        basic_tab = self.create_basic_info_tab()
        tab_widget.addTab(basic_tab, "基本信息")

        # 统计信息选项卡
        stats_tab = self.create_statistics_tab()
        tab_widget.addTab(stats_tab, "统计信息")

        # 日志选项卡
        log_tab = self.create_log_tab()
        tab_widget.addTab(log_tab, "执行日志")

        layout.addWidget(tab_widget)
        widget.setLayout(layout)
        return widget

    def create_basic_info_tab(self):
        """创建基本信息选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 基本信息
        self.basic_info = QTextEdit()
        self.basic_info.setReadOnly(True)
        self.basic_info.setFont(QFont("Consolas", 10))
        layout.addWidget(self.basic_info)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.resume_btn = QPushButton("继续执行")
        self.resume_btn.clicked.connect(self.resume_selected_task)
        button_layout.addWidget(self.resume_btn)

        self.pause_btn = QPushButton("暂停任务")
        self.pause_btn.clicked.connect(self.pause_selected_task)
        button_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("停止任务")
        self.stop_btn.clicked.connect(self.stop_selected_task)
        button_layout.addWidget(self.stop_btn)

        self.delete_btn = QPushButton("删除记录")
        self.delete_btn.clicked.connect(self.delete_selected_record)
        button_layout.addWidget(self.delete_btn)

        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def create_statistics_tab(self):
        """创建统计信息选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 统计表格
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(4)
        self.stats_table.setHorizontalHeaderLabels([
            "指标", "数量", "百分比", "详情"
        ])

        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        layout.addWidget(self.stats_table)

        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        widget.setLayout(layout)
        return widget

    def create_log_tab(self):
        """创建日志选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)

        # 日志级别过滤
        log_filter_layout = QHBoxLayout()
        log_filter_layout.addWidget(QLabel("日志级别:"))

        self.debug_cb = QCheckBox("DEBUG")
        self.debug_cb.setChecked(True)
        log_filter_layout.addWidget(self.debug_cb)

        self.info_cb = QCheckBox("INFO")
        self.info_cb.setChecked(True)
        log_filter_layout.addWidget(self.info_cb)

        self.error_cb = QCheckBox("ERROR")
        self.error_cb.setChecked(True)
        log_filter_layout.addWidget(self.error_cb)

        log_filter_layout.addStretch()
        layout.addLayout(log_filter_layout)

        widget.setLayout(layout)
        return widget

    def setup_connections(self):
        """设置信号连接"""
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.auto_refresh_cb.toggled.connect(self.toggle_auto_refresh)

        # 设置自动刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_records)
        self.refresh_timer.start(5000)  # 5秒自动刷新

    def load_records(self):
        """加载记录"""
        if not CORE_AVAILABLE:
            return

        try:
            recorder = get_incremental_update_recorder()
            self.records = recorder.get_all_update_history()
            self.apply_filters()

        except Exception as e:
            logger.error(f"加载更新记录失败: {e}")
            QMessageBox.critical(self, "错误", f"加载更新记录失败: {e}")

    def apply_filters(self):
        """应用过滤器"""
        try:
            task_name = self.task_name_filter.text().lower()
            status = self.status_filter.currentText()
            start_date = self.start_date_filter.dateTime().toPyDateTime()
            end_date = self.end_date_filter.dateTime().toPyDateTime()

            self.filtered_records = []

            for record in self.records:
                # 任务名称过滤
                if task_name and task_name not in record['task_name'].lower():
                    continue

                # 状态过滤
                if status != "全部" and record['status'] != status:
                    continue

                # 时间过滤
                record_start = datetime.fromisoformat(record['start_time'])
                if record_start < start_date or record_start > end_date:
                    continue

                self.filtered_records.append(record)

        except Exception as e:
            logger.error(f"应用过滤器失败: {e}")
            self.filtered_records = self.records

        self.update_table()

    def update_table(self):
        """更新表格显示"""
        self.table.setRowCount(0)

        for i, record in enumerate(self.filtered_records):
            self.table.insertRow(i)

            # 任务ID
            task_id_item = QTableWidgetItem(record['task_id'][:12] + "..." if len(record['task_id']) > 12 else record['task_id'])
            task_id_item.setData(Qt.UserRole, record['task_id'])
            self.table.setItem(i, 0, task_id_item)

            # 任务名称
            self.table.setItem(i, 1, QTableWidgetItem(record['task_name']))

            # 股票代码
            symbols = ", ".join(record['symbols'][:5])
            if len(record['symbols']) > 5:
                symbols += f" (+{len(record['symbols']) - 5})"
            self.table.setItem(i, 2, QTableWidgetItem(symbols))

            # 数据类型
            self.table.setItem(i, 3, QTableWidgetItem(record['data_type']))

            # 开始时间
            start_time = datetime.fromisoformat(record['start_time'])
            self.table.setItem(i, 4, QTableWidgetItem(start_time.strftime("%Y-%m-%d %H:%M")))

            # 结束时间
            end_time = datetime.fromisoformat(record['end_time']) if record['end_time'] else None
            end_time_str = end_time.strftime("%Y-%m-%d %H:%M") if end_time else "进行中"
            self.table.setItem(i, 5, QTableWidgetItem(end_time_str))

            # 状态
            status_item = QTableWidgetItem(self.format_status(record['status']))
            status_item.setData(Qt.UserRole, record['status'])
            status_item.setBackground(self.get_status_color(record['status']))
            self.table.setItem(i, 6, status_item)

            # 进度
            progress = record.get('progress', 0)
            progress_item = QTableWidgetItem(f"{progress:.1f}%")
            self.table.setItem(i, 7, progress_item)

            # 操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)

            # 查看详情按钮
            detail_btn = QPushButton("详情")
            detail_btn.clicked.connect(lambda checked, r=record: self.show_record_details(r))
            action_layout.addWidget(detail_btn)

            action_widget.setLayout(action_layout)
            self.table.setCellWidget(i, 8, action_widget)

        # 更新统计信息
        self.update_statistics()

    def format_status(self, status: str) -> str:
        """格式化状态显示"""
        status_map = {
            'pending': '待开始',
            'running': '进行中',
            'completed': '已完成',
            'failed': '失败',
            'stopped': '已停止'
        }
        return status_map.get(status, status)

    def get_status_color(self, status: str) -> QColor:
        """获取状态颜色"""
        color_map = {
            'pending': QColor(100, 100, 100),      # 灰色
            'running': QColor(0, 150, 255),        # 蓝色
            'completed': QColor(0, 200, 0),        # 绿色
            'failed': QColor(255, 0, 0),            # 红色
            'stopped': QColor(255, 165, 0)         # 橙色
        }
        return color_map.get(status, QColor(0, 0, 0))

    def update_statistics(self):
        """更新统计信息"""
        total_count = len(self.filtered_records)
        status_count = {}

        for record in self.filtered_records:
            status = record['status']
            status_count[status] = status_count.get(status, 0) + 1

        stats_text = f"共 {total_count} 条记录 | "
        stats_text += " | ".join([f"{self.format_status(s)}: {count}" for s, count in status_count.items()])
        self.filter_stats.setText(stats_text)

        # 更新表格统计数据
        self.stats_table.setRowCount(len(status_count))
        for i, (status, count) in enumerate(status_count.items()):
            self.stats_table.setItem(i, 0, QTableWidgetItem(self.format_status(status)))
            self.stats_table.setItem(i, 1, QTableWidgetItem(str(count)))
            self.stats_table.setItem(i, 2, QTableWidgetItem(f"{count/total_count*100:.1f}%"))
            self.stats_table.setItem(i, 3, QTableWidgetItem(f"查看{status}记录"))

    def on_selection_changed(self):
        """选择变化处理"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        task_id = self.table.item(row, 0).data(Qt.UserRole)

        # 查找对应的记录
        for record in self.filtered_records:
            if record['task_id'] == task_id:
                self.selected_record_id = task_id
                self.record_selected.emit(record)
                self.update_detail_panel(record)
                break

    def update_detail_panel(self, record: Dict[str, Any]):
        """更新详细信息面板"""
        # 更新基本信息
        info_text = f"任务ID: {record['task_id']}\n"
        info_text += f"任务名称: {record['task_name']}\n"
        info_text += f"数据类型: {record['data_type']}\n"
        info_text += f"频率: {record.get('frequency', '日线')}\n"
        info_text += f"股票数量: {len(record['symbols'])}\n"
        info_text += f"状态: {self.format_status(record['status'])}\n"
        info_text += f"进度: {record.get('progress', 0):.1f}%\n"
        info_text += f"开始时间: {datetime.fromisoformat(record['start_time']).strftime('%Y-%m-%d %H:%M:%S')}\n"
        info_text += f"结束时间: {datetime.fromisoformat(record['end_time']).strftime('%Y-%m-%d %H:%M:%S') if record['end_time'] else '进行中'}\n"
        info_text += f"执行时长: {record.get('execution_time', 0):.2f}秒\n"
        info_text += f"成功数量: {record['success_count']}\n"
        info_text += f"失败数量: {record['failed_count']}\n"
        info_text += f"跳过数量: {record['skipped_count']}\n"

        self.basic_info.setText(info_text)

        # 更新进度条
        self.progress_bar.setValue(int(record.get('progress', 0)))

        # 更新日志
        self.update_log_panel(record)

    def update_log_panel(self, record: Dict[str, Any]):
        """更新日志面板"""
        self.log_text.clear()

        # 模拟日志输出（实际应该从数据库获取）
        logs = [
            f"[INFO] 任务开始执行: {record['task_name']}",
            f"[INFO] 开始下载 {len(record['symbols'])} 个股票的数据",
            f"[INFO] 数据类型: {record['data_type']}",
            f"[INFO] 预计执行时间: {record.get('estimated_time', 0)} 秒",
        ]

        # 添加成功和失败信息
        for i in range(record['success_count']):
            logs.append(f"[INFO] 成功下载股票: {record['symbols'][i] if i < len(record['symbols']) else f'Stock_{i}'}")

        for i in range(record['failed_count']):
            success_count = record['success_count']
            symbol_idx = success_count + i
            symbol = record['symbols'][symbol_idx] if symbol_idx < len(record['symbols']) else f'Stock_{symbol_idx}'
            logs.append(f"[ERROR] 下载失败: {symbol}")

        # 添加进度信息
        logs.append(f"[INFO] 任务完成，成功率: {record['success_count']/len(record['symbols'])*100:.1f}%")

        for log in logs:
            self.log_text.append(log)

    def refresh_records(self):
        """刷新记录"""
        if not CORE_AVAILABLE:
            return

        try:
            recorder = get_incremental_update_recorder()
            self.records = recorder.get_all_update_history()
            self.apply_filters()

        except Exception as e:
            logger.error(f"刷新记录失败: {e}")

    def export_records(self):
        """导出记录"""
        if not self.filtered_records:
            QMessageBox.warning(self, "警告", "没有可导出的记录")
            return

        # 简单的CSV导出
        try:
            import csv
            from PyQt5.QtWidgets import QFileDialog

            filename, _ = QFileDialog.getSaveFileName(
                self, "导出记录", f"update_history_{datetime.now().strftime('%Y%m%d')}.csv",
                "CSV文件 (*.csv)"
            )

            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['task_id', 'task_name', 'symbols', 'data_type', 'status',
                                'progress', 'start_time', 'end_time', 'execution_time',
                                'success_count', 'failed_count', 'skipped_count']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for record in self.filtered_records:
                        export_record = {
                            'task_id': record['task_id'],
                            'task_name': record['task_name'],
                            'symbols': ', '.join(record['symbols']),
                            'data_type': record['data_type'],
                            'status': record['status'],
                            'progress': record.get('progress', 0),
                            'start_time': record['start_time'],
                            'end_time': record['end_time'],
                            'execution_time': record.get('execution_time', 0),
                            'success_count': record['success_count'],
                            'failed_count': record['failed_count'],
                            'skipped_count': record['skipped_count']
                        }
                        writer.writerow(export_record)

                QMessageBox.information(self, "成功", "记录导出成功")

        except Exception as e:
            logger.error(f"导出记录失败: {e}")
            QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def clear_expired_records(self):
        """清除过期记录"""
        reply = QMessageBox.question(
            self, "确认",
            "确定要清除30天前的记录吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if CORE_AVAILABLE:
                    recorder = get_incremental_update_recorder()
                    cutoff_date = datetime.now() - timedelta(days=30)
                    recorder.cleanup_old_records(cutoff_date)

                self.refresh_records()
                QMessageBox.information(self, "成功", "过期记录已清除")

            except Exception as e:
                logger.error(f"清除过期记录失败: {e}")
                QMessageBox.critical(self, "错误", f"清除失败: {e}")

    def show_record_details(self, record: Dict[str, Any]):
        """显示记录详情"""
        dialog = QDialog(self)
        dialog.setWindowTitle("任务详情")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout()

        # 显示详细信息的只读文本框
        detail_text = QTextEdit()
        detail_text.setReadOnly(True)

        details = f"""
任务ID: {record['task_id']}
任务名称: {record['task_name']}
数据类型: {record['data_type']}
频率: {record.get('frequency', '日线')}
状态: {self.format_status(record['status'])}
进度: {record.get('progress', 0):.1f}%

股票列表:
{chr(10).join(record['symbols'])}

执行统计:
- 总股票数: {len(record['symbols'])}
- 成功数量: {record['success_count']}
- 失败数量: {record['failed_count']}
- 跳过数量: {record['skipped_count']}
- 成功率: {record['success_count']/len(record['symbols'])*100:.1f}%

时间信息:
- 开始时间: {datetime.fromisoformat(record['start_time']).strftime('%Y-%m-%d %H:%M:%S')}
- 结束时间: {datetime.fromisoformat(record['end_time']).strftime('%Y-%m-%d %H:%M:%S') if record['end_time'] else '进行中'}
- 执行时长: {record.get('execution_time', 0):.2f}秒
        """

        detail_text.setText(details)
        layout.addWidget(detail_text)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.setLayout(layout)
        dialog.exec_()

    def resume_selected_task(self):
        """恢复选中的任务"""
        if not self.selected_record_id:
            QMessageBox.warning(self, "警告", "请先选择要恢复的任务")
            return

        try:
            if CORE_AVAILABLE:
                from core.services.breakpoint_resume_manager import get_breakpoint_resume_manager
                manager = get_breakpoint_resume_manager()
                success = manager.resume_task(self.selected_record_id)

                if success:
                    QMessageBox.information(self, "成功", "任务已恢复执行")
                    self.refresh_records()
                else:
                    QMessageBox.warning(self, "警告", "任务恢复失败")

        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            QMessageBox.critical(self, "错误", f"恢复失败: {e}")

    def pause_selected_task(self):
        """暂停选中的任务"""
        if not self.selected_record_id:
            QMessageBox.warning(self, "警告", "请先选择要暂停的任务")
            return

        try:
            if CORE_AVAILABLE:
                from core.services.breakpoint_resume_manager import get_breakpoint_resume_manager
                manager = get_breakpoint_resume_manager()
                success = manager.pause_task(self.selected_record_id)

                if success:
                    QMessageBox.information(self, "成功", "任务已暂停")
                    self.refresh_records()
                else:
                    QMessageBox.warning(self, "警告", "任务暂停失败")

        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            QMessageBox.critical(self, "错误", f"暂停失败: {e}")

    def stop_selected_task(self):
        """停止选中的任务"""
        if not self.selected_record_id:
            QMessageBox.warning(self, "警告", "请先选择要停止的任务")
            return

        reply = QMessageBox.question(
            self, "确认",
            "确定要停止此任务吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if CORE_AVAILABLE:
                    from core.services.breakpoint_resume_manager import get_breakpoint_resume_manager
                    manager = get_breakpoint_resume_manager()
                    success = manager.stop_task(self.selected_record_id)

                    if success:
                        QMessageBox.information(self, "成功", "任务已停止")
                        self.refresh_records()
                    else:
                        QMessageBox.warning(self, "警告", "任务停止失败")

            except Exception as e:
                logger.error(f"停止任务失败: {e}")
                QMessageBox.critical(self, "错误", f"停止失败: {e}")

    def delete_selected_record(self):
        """删除选中的记录"""
        if not self.selected_record_id:
            QMessageBox.warning(self, "警告", "请先选择要删除的记录")
            return

        reply = QMessageBox.question(
            self, "确认",
            "确定要删除此记录吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if CORE_AVAILABLE:
                    recorder = get_incremental_update_recorder()
                    success = recorder.delete_update_record(self.selected_record_id)

                    if success:
                        QMessageBox.information(self, "成功", "记录已删除")
                        self.record_deleted.emit(self.selected_record_id)
                        self.refresh_records()
                    else:
                        QMessageBox.warning(self, "警告", "删除记录失败")

            except Exception as e:
                logger.error(f"删除记录失败: {e}")
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def toggle_auto_refresh(self, enabled: bool):
        """切换自动刷新"""
        if enabled:
            self.refresh_timer.start(self.refresh_interval.value() * 1000)
        else:
            self.refresh_timer.stop()

    def on_cell_double_clicked(self, row: int, column: int):
        """双击单元格处理"""
        if column == 0:  # 任务ID列
            task_id = self.table.item(row, 0).data(Qt.UserRole)
            for record in self.filtered_records:
                if record['task_id'] == task_id:
                    self.show_record_details(record)
                    break