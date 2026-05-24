#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增量更新调度器配置组件

提供增量更新定时任务的配置和管理界面，包括：
- 调度器状态控制
- 定时任务配置
- 任务列表管理
- 执行历史查看

作者: FactorWeave-Quant团队
版本: 1.0
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import asdict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QSpinBox, 
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit, QCheckBox, QDateTimeEdit, QTimeEdit,
    QListWidget, QListWidgetItem, QSplitter, QFrame, 
    QMessageBox, QDialog, QDialogButtonBox, QLineEdit,
    QScrollArea, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QDateTime, QTime, QDate
)
from PyQt5.QtGui import QFont, QColor, QIcon

from loguru import logger

try:
    from core.services.incremental_update_scheduler import (
        IncrementalUpdateScheduler, ScheduledTask, ScheduleType
    )
    from core.containers import get_service_container
    SCHEDULER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"增量更新调度器导入失败: {e}")
    SCHEDULER_AVAILABLE = False
    IncrementalUpdateScheduler = None
    ScheduledTask = None
    ScheduleType = None


class IncrementalSchedulerConfigWidget(QWidget):
    """增量更新调度器配置组件"""
    
    task_created = pyqtSignal(str)
    task_updated = pyqtSignal(str)
    task_deleted = pyqtSignal(str)
    scheduler_status_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scheduler: Optional[IncrementalUpdateScheduler] = None
        self.tasks: Dict[str, Dict[str, Any]] = {}
        
        self._init_scheduler()
        self._create_ui()
        self._connect_signals()
        self._refresh_task_list()
        
        self._start_status_timer()
    
    def _init_scheduler(self):
        """初始化调度器服务"""
        if not SCHEDULER_AVAILABLE:
            logger.warning("增量更新调度器服务不可用")
            return
        
        try:
            container = get_service_container()
            if container and container.is_registered(IncrementalUpdateScheduler):
                self.scheduler = container.resolve(IncrementalUpdateScheduler)
                self._connect_scheduler_signals()
                logger.info("增量更新调度器服务初始化成功")
            else:
                logger.warning("IncrementalUpdateScheduler 未注册到服务容器")
        except Exception as e:
            logger.error(f"初始化增量更新调度器失败: {e}")
    
    def _connect_scheduler_signals(self):
        """连接调度器信号"""
        if not self.scheduler:
            return
        
        try:
            self.scheduler.task_started.connect(self._on_task_started)
            self.scheduler.task_completed.connect(self._on_task_completed)
            self.scheduler.task_failed.connect(self._on_task_failed)
            self.scheduler.task_enabled.connect(self._on_task_enabled_changed)
            logger.info("调度器信号连接成功")
        except Exception as e:
            logger.error(f"连接调度器信号失败: {e}")
    
    def _on_task_started(self, task_id: str):
        """任务开始执行"""
        logger.info(f"任务开始执行: {task_id}")
        self._refresh_task_list()
    
    def _on_task_completed(self, task_id: str, stats: dict):
        """任务执行完成"""
        logger.info(f"任务执行完成: {task_id}, 统计: {stats}")
        self._refresh_task_list()
    
    def _on_task_failed(self, task_id: str, error: str):
        """任务执行失败"""
        logger.error(f"任务执行失败: {task_id}, 错误: {error}")
        self._refresh_task_list()
    
    def _on_task_enabled_changed(self, task_id: str, enabled: bool):
        """任务启用状态改变"""
        logger.info(f"任务 {task_id} {'启用' if enabled else '禁用'}")
        self._refresh_task_list()
    
    def _create_ui(self):
        """创建UI界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        layout.addWidget(self._create_status_panel())
        
        layout.addWidget(self._create_task_list_panel())
        
        layout.addWidget(self._create_action_panel())
    
    def _create_status_panel(self) -> QGroupBox:
        """创建状态面板"""
        group = QGroupBox("调度器状态")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QHBoxLayout(group)
        
        self.status_label = QLabel("状态: 未启动")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.start_btn = QPushButton("▶ 启动")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        return group
    
    def _create_task_list_panel(self) -> QGroupBox:
        """创建任务列表面板"""
        group = QGroupBox("定时任务列表")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(7)
        self.task_table.setHorizontalHeaderLabels([
            "任务名称", "调度类型", "执行时间", "股票数量", 
            "状态", "上次执行", "下次执行"
        ])
        
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addWidget(self.task_table)
        
        return group
    
    def _create_action_panel(self) -> QGroupBox:
        """创建操作面板"""
        group = QGroupBox("任务操作")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QHBoxLayout(group)
        
        self.add_task_btn = QPushButton("➕ 新建任务")
        self.add_task_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(self.add_task_btn)
        
        self.edit_task_btn = QPushButton("✏ 编辑任务")
        self.edit_task_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        self.edit_task_btn.setEnabled(False)
        layout.addWidget(self.edit_task_btn)
        
        self.delete_task_btn = QPushButton("🗑 删除任务")
        self.delete_task_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.delete_task_btn.setEnabled(False)
        layout.addWidget(self.delete_task_btn)
        
        self.toggle_task_btn = QPushButton("⚡ 启用/禁用")
        self.toggle_task_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.toggle_task_btn.setEnabled(False)
        layout.addWidget(self.toggle_task_btn)
        
        layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        layout.addWidget(self.refresh_btn)
        
        return group
    
    def _connect_signals(self):
        """连接信号"""
        self.start_btn.clicked.connect(self._on_start_scheduler)
        self.stop_btn.clicked.connect(self._on_stop_scheduler)
        self.add_task_btn.clicked.connect(self._on_add_task)
        self.edit_task_btn.clicked.connect(self._on_edit_task)
        self.delete_task_btn.clicked.connect(self._on_delete_task)
        self.toggle_task_btn.clicked.connect(self._on_toggle_task)
        self.refresh_btn.clicked.connect(self._refresh_task_list)
        
        self.task_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.task_table.doubleClicked.connect(self._on_edit_task)
    
    def _start_status_timer(self):
        """启动状态更新定时器"""
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(5000)
    
    def _update_status(self):
        """更新状态显示"""
        if self.scheduler:
            if self.scheduler.running:
                self.status_label.setText("状态: 运行中 ✅")
                self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #27ae60;")
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
            else:
                self.status_label.setText("状态: 已停止 ⏹")
                self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
        else:
            self.status_label.setText("状态: 服务不可用 ❌")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
    
    def _refresh_task_list(self):
        """刷新任务列表"""
        self.task_table.setRowCount(0)
        
        if not self.scheduler:
            return
        
        try:
            tasks = self.scheduler.get_all_tasks()
            self.tasks = {task['task_id']: task for task in tasks}
            
            for task in tasks:
                row = self.task_table.rowCount()
                self.task_table.insertRow(row)
                
                self.task_table.setItem(row, 0, QTableWidgetItem(task.get('name', '')))
                
                schedule_type = task.get('schedule_type')
                schedule_type_text = self._get_schedule_type_text(schedule_type)
                self.task_table.setItem(row, 1, QTableWidgetItem(schedule_type_text))
                
                time_text = task.get('schedule_time', '-')
                self.task_table.setItem(row, 2, QTableWidgetItem(time_text))
                
                symbols_count = task.get('symbols_count', 0)
                self.task_table.setItem(row, 3, QTableWidgetItem(str(symbols_count)))
                
                status_text = "启用" if task.get('enabled', False) else "禁用"
                status_item = QTableWidgetItem(status_text)
                if task.get('enabled', False):
                    status_item.setForeground(QColor("#27ae60"))
                else:
                    status_item.setForeground(QColor("#e74c3c"))
                self.task_table.setItem(row, 4, status_item)
                
                last_run_str = task.get('last_run')
                if last_run_str:
                    try:
                        last_run = datetime.fromisoformat(last_run_str)
                        last_run_text = last_run.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        last_run_text = last_run_str
                else:
                    last_run_text = "-"
                self.task_table.setItem(row, 5, QTableWidgetItem(last_run_text))
                
                next_run_str = task.get('next_run')
                if next_run_str:
                    try:
                        next_run = datetime.fromisoformat(next_run_str)
                        next_run_text = next_run.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        next_run_text = next_run_str
                else:
                    next_run_text = "-"
                self.task_table.setItem(row, 6, QTableWidgetItem(next_run_text))
                
        except Exception as e:
            logger.error(f"刷新任务列表失败: {e}")
    
    def _get_schedule_type_text(self, schedule_type) -> str:
        """获取调度类型文本"""
        if schedule_type is None:
            return "-"
        
        if ScheduleType is None:
            return str(schedule_type)
        
        if isinstance(schedule_type, str):
            type_map_str = {
                "daily": "每日",
                "weekly": "每周",
                "monthly": "每月",
                "market_open": "开盘时",
                "market_close": "收盘时",
                "custom": "自定义"
            }
            return type_map_str.get(schedule_type, schedule_type)
        
        type_map = {
            ScheduleType.DAILY: "每日",
            ScheduleType.WEEKLY: "每周",
            ScheduleType.MONTHLY: "每月",
            ScheduleType.MARKET_OPEN: "开盘时",
            ScheduleType.MARKET_CLOSE: "收盘时"
        }
        return type_map.get(schedule_type, str(schedule_type))
    
    def _on_start_scheduler(self):
        """启动调度器"""
        if self.scheduler:
            try:
                self.scheduler.start_scheduler()
                self._update_status()
                QMessageBox.information(self, "成功", "增量更新调度器已启动")
            except Exception as e:
                logger.error(f"启动调度器失败: {e}")
                QMessageBox.critical(self, "错误", f"启动调度器失败: {e}")
    
    def _on_stop_scheduler(self):
        """停止调度器"""
        if self.scheduler:
            try:
                self.scheduler.stop_scheduler()
                self._update_status()
                QMessageBox.information(self, "成功", "增量更新调度器已停止")
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")
                QMessageBox.critical(self, "错误", f"停止调度器失败: {e}")
    
    def _on_add_task(self):
        """添加新任务"""
        dialog = IncrementalTaskDialog(self.scheduler, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self._refresh_task_list()
            self.task_created.emit(dialog.task_id)
    
    def _on_edit_task(self):
        """编辑任务"""
        selected_rows = self.task_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        name_item = self.task_table.item(row, 0)
        if not name_item:
            return
        
        task_name = name_item.text()
        task_id = None
        for tid, task in self.tasks.items():
            if task.get('name') == task_name:
                task_id = tid
                break
        
        if task_id:
            dialog = IncrementalTaskDialog(self.scheduler, task_id, parent=self)
            if dialog.exec_() == QDialog.Accepted:
                self._refresh_task_list()
                self.task_updated.emit(task_id)
    
    def _on_delete_task(self):
        """删除任务"""
        selected_rows = self.task_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        name_item = self.task_table.item(row, 0)
        if not name_item:
            return
        
        task_name = name_item.text()
        task_id = None
        for tid, task in self.tasks.items():
            if task.get('name') == task_name:
                task_id = tid
                break
        
        if task_id:
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除任务 '{task_name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if self.scheduler:
                    try:
                        self.scheduler.remove_task(task_id)
                        self._refresh_task_list()
                        self.task_deleted.emit(task_id)
                        QMessageBox.information(self, "成功", "任务已删除")
                    except Exception as e:
                        logger.error(f"删除任务失败: {e}")
                        QMessageBox.critical(self, "错误", f"删除任务失败: {e}")
    
    def _on_selection_changed(self):
        """选择变化时更新按钮状态"""
        has_selection = len(self.task_table.selectedItems()) > 0
        self.edit_task_btn.setEnabled(has_selection)
        self.delete_task_btn.setEnabled(has_selection)
        self.toggle_task_btn.setEnabled(has_selection)
    
    def _on_toggle_task(self):
        """切换任务启用/禁用状态"""
        selected_rows = self.task_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        name_item = self.task_table.item(row, 0)
        if not name_item:
            return
        
        task_name = name_item.text()
        task_id = None
        for tid, task in self.tasks.items():
            if task.get('name') == task_name:
                task_id = tid
                break
        
        if task_id and self.scheduler:
            try:
                task = self.tasks.get(task_id, {})
                current_enabled = task.get('enabled', False)
                
                if current_enabled:
                    self.scheduler.disable_task(task_id)
                    QMessageBox.information(self, "成功", f"任务 '{task_name}' 已禁用")
                else:
                    self.scheduler.enable_task(task_id)
                    QMessageBox.information(self, "成功", f"任务 '{task_name}' 已启用")
                
                self._refresh_task_list()
                
            except Exception as e:
                logger.error(f"切换任务状态失败: {e}")
                QMessageBox.critical(self, "错误", f"切换任务状态失败: {e}")


class IncrementalTaskDialog(QDialog):
    """增量更新任务配置对话框"""
    
    def __init__(self, scheduler: Optional[IncrementalUpdateScheduler], 
                 task_id: str = None, parent=None):
        super().__init__(parent)
        
        self.scheduler = scheduler
        self.task_id = task_id
        self.existing_task: Optional[Dict[str, Any]] = None
        
        if task_id and scheduler:
            tasks = scheduler.get_all_tasks()
            for task in tasks:
                if task.get('task_id') == task_id:
                    self.existing_task = task
                    break
        
        self.setWindowTitle("编辑任务" if self.existing_task else "新建增量更新任务")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self._create_ui()
        self._load_existing_data()
    
    def _create_ui(self):
        """创建UI"""
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("请输入任务名称")
        form_layout.addRow("任务名称:", self.name_edit)
        
        self.schedule_type_combo = QComboBox()
        if ScheduleType:
            self.schedule_type_combo.addItem("每日", ScheduleType.DAILY)
            self.schedule_type_combo.addItem("每周", ScheduleType.WEEKLY)
            self.schedule_type_combo.addItem("每月", ScheduleType.MONTHLY)
            self.schedule_type_combo.addItem("开盘时", ScheduleType.MARKET_OPEN)
            self.schedule_type_combo.addItem("收盘时", ScheduleType.MARKET_CLOSE)
        form_layout.addRow("调度类型:", self.schedule_type_combo)
        
        self.schedule_time_edit = QTimeEdit()
        self.schedule_time_edit.setTime(QTime.currentTime())
        self.schedule_time_edit.setDisplayFormat("HH:mm")
        form_layout.addRow("执行时间:", self.schedule_time_edit)
        
        self.schedule_days_list = QListWidget()
        self.schedule_days_list.setMaximumHeight(100)
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for day in days:
            item = QListWidgetItem(day)
            item.setCheckState(Qt.Unchecked)
            self.schedule_days_list.addItem(item)
        form_layout.addRow("执行日期:", self.schedule_days_list)
        
        self.symbols_edit = QTextEdit()
        self.symbols_edit.setPlaceholderText("每行一个股票代码，例如:\n000001\n000002\n600000")
        self.symbols_edit.setMaximumHeight(100)
        form_layout.addRow("股票代码:", self.symbols_edit)
        
        self.incremental_days_spin = QSpinBox()
        self.incremental_days_spin.setRange(1, 365)
        self.incremental_days_spin.setValue(7)
        form_layout.addRow("回溯天数:", self.incremental_days_spin)
        
        self.gap_threshold_spin = QSpinBox()
        self.gap_threshold_spin.setRange(1, 365)
        self.gap_threshold_spin.setValue(30)
        form_layout.addRow("间隙阈值(天):", self.gap_threshold_spin)
        
        self.enabled_cb = QCheckBox("启用任务")
        self.enabled_cb.setChecked(True)
        form_layout.addRow("", self.enabled_cb)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_existing_data(self):
        """加载现有任务数据"""
        if self.existing_task:
            self.name_edit.setText(self.existing_task.get('name', ''))
            
            if ScheduleType:
                schedule_type = self.existing_task.get('schedule_type')
                index = self.schedule_type_combo.findData(schedule_type)
                if index >= 0:
                    self.schedule_type_combo.setCurrentIndex(index)
            
            schedule_time = self.existing_task.get('schedule_time')
            if schedule_time:
                time_parts = schedule_time.split(":")
                if len(time_parts) >= 2:
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    self.schedule_time_edit.setTime(QTime(hour, minute))
            
            day_map_reverse = {
                "monday": "周一", "tuesday": "周二", "wednesday": "周三",
                "thursday": "周四", "friday": "周五", "saturday": "周六", "sunday": "周日"
            }
            schedule_days = self.existing_task.get('schedule_days', [])
            for i in range(self.schedule_days_list.count()):
                item = self.schedule_days_list.item(i)
                day_name = item.text()
                english_day = day_map_reverse.get(day_name.lower(), day_name.lower())
                if english_day in schedule_days or day_name in schedule_days:
                    item.setCheckState(Qt.Checked)
            
            symbols = self.existing_task.get('symbols', [])
            if symbols:
                self.symbols_edit.setPlainText("\n".join(symbols))
            
            self.incremental_days_spin.setValue(self.existing_task.get('incremental_days', 7))
            self.gap_threshold_spin.setValue(self.existing_task.get('gap_threshold', 30))
            self.enabled_cb.setChecked(self.existing_task.get('enabled', True))
    
    def _on_accept(self):
        """确认保存"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "请输入任务名称")
            return
        
        symbols_text = self.symbols_edit.toPlainText().strip()
        symbols = [s.strip() for s in symbols_text.split("\n") if s.strip()]
        if not symbols:
            QMessageBox.warning(self, "警告", "请输入至少一个股票代码")
            return
        
        schedule_type = self.schedule_type_combo.currentData()
        schedule_time = self.schedule_time_edit.time().toString("HH:mm")
        
        day_map = {
            "周一": "monday", "周二": "tuesday", "周三": "wednesday",
            "周四": "thursday", "周五": "friday", "周六": "saturday", "周日": "sunday"
        }
        schedule_days = []
        for i in range(self.schedule_days_list.count()):
            item = self.schedule_days_list.item(i)
            if item.checkState() == Qt.Checked:
                day_name = item.text()
                schedule_days.append(day_map.get(day_name, day_name.lower()))
        
        if not self.scheduler:
            QMessageBox.warning(self, "警告", "调度器服务不可用")
            return
        
        try:
            existing_task_id = self.existing_task.get('task_id') if self.existing_task else None
            if existing_task_id:
                self.scheduler.remove_task(existing_task_id)
            
            task_id = self.scheduler.create_scheduled_task(
                name=name,
                symbols=symbols,
                schedule_type=schedule_type,
                schedule_time=schedule_time,
                schedule_days=schedule_days,
                incremental_days=self.incremental_days_spin.value(),
                gap_threshold=self.gap_threshold_spin.value(),
                enabled=self.enabled_cb.isChecked()
            )
            
            self.task_id = task_id
            self.accept()
            
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
            QMessageBox.critical(self, "错误", f"保存任务失败: {e}")
