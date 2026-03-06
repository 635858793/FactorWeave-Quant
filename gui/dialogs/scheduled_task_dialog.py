#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
定时任务配置对话框

简化版定时任务配置：
- 选择已有的导入任务
- 配置定时类型（每日/每周/每月/自定义）
- 生成Cron表达式
- 保存定时配置
- 显示已配置的定时任务列表
- 支持删除和立即执行
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QCheckBox,
    QGroupBox, QRadioButton, QDialogButtonBox, QMessageBox,
    QDateTimeEdit, QTabWidget, QWidget, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QListWidget, QListWidgetItem,
    QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QDateTime
from PyQt5.QtGui import QColor
from loguru import logger
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from croniter import croniter
    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False
    logger.warning("croniter 未安装，Cron表达式验证功能受限")


class ScheduledTaskDialog(QDialog):
    """定时任务配置对话框"""

    task_scheduled = pyqtSignal(str, str)  # task_id, schedule_cron

    def __init__(self, config_manager, import_engine=None, parent=None, preselected_task_ids=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.import_engine = import_engine
        self.preselected_task_ids = preselected_task_ids or []
        self.selected_task_ids = []
        self.schedule_cron = None

        self.setWindowTitle("⏰ 定时任务配置")
        self.setModal(True)
        self.resize(700, 650)

        self._create_ui()

    def _create_ui(self):
        """创建UI - 所有组件在一个方法中创建，避免生命周期问题"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("定时任务配置")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title_label)

        # 主要配置区域
        config_group = QGroupBox("定时配置")
        config_layout = QVBoxLayout(config_group)

        # 任务选择标签
        task_label = QLabel("选择任务（可多选）:")
        config_layout.addWidget(task_label)
        
        # 任务列表 - 关键：创建后立即使用
        self.task_list = QListWidget()
        self.task_list.setMinimumWidth(300)
        self.task_list.setMinimumHeight(80)
        self.task_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        config_layout.addWidget(self.task_list)
        
        layout.addWidget(config_group)
        
        # 立即加载任务数据
        self._load_tasks_data()
        
        # 连接信号
        self.task_list.itemSelectionChanged.connect(self._on_tasks_selected)
        
        # 如果有预选任务，自动选中
        if self.preselected_task_ids:
            self._preselect_tasks_data()

        # ==================== 定时类型选择 ====================
        type_group = QGroupBox("定时类型")
        type_layout = QHBoxLayout(type_group)
        
        self.daily_radio = QRadioButton("每日")
        self.weekly_radio = QRadioButton("每周")
        self.monthly_radio = QRadioButton("每月")
        self.custom_radio = QRadioButton("自定义Cron")
        
        self.daily_radio.setChecked(True)
        
        # 使用按钮组确保互斥
        self.daily_radio.toggled.connect(self._on_type_changed)
        self.weekly_radio.toggled.connect(self._on_type_changed)
        self.monthly_radio.toggled.connect(self._on_type_changed)
        self.custom_radio.toggled.connect(self._on_type_changed)
        
        type_layout.addWidget(self.daily_radio)
        type_layout.addWidget(self.weekly_radio)
        type_layout.addWidget(self.monthly_radio)
        type_layout.addWidget(self.custom_radio)
        type_layout.addStretch()
        
        layout.addWidget(type_group)

        # ==================== 使用 QStackedWidget 实现互斥配置 ====================
        self.config_stack = QStackedWidget()
        
        # --- 每日配置面板 ---
        daily_widget = QWidget()
        daily_layout = QVBoxLayout(daily_widget)
        daily_layout.setContentsMargins(0, 0, 0, 0)
        
        daily_time_layout = QHBoxLayout()
        daily_time_layout.addWidget(QLabel("执行时间:"))
        self.daily_hour_spin = QSpinBox()
        self.daily_hour_spin.setRange(0, 23)
        self.daily_hour_spin.setValue(9)
        self.daily_hour_spin.valueChanged.connect(self._on_config_changed)
        daily_time_layout.addWidget(self.daily_hour_spin)
        daily_time_layout.addWidget(QLabel(":"))
        self.daily_minute_spin = QSpinBox()
        self.daily_minute_spin.setRange(0, 59)
        self.daily_minute_spin.setValue(30)
        self.daily_minute_spin.valueChanged.connect(self._on_config_changed)
        daily_time_layout.addWidget(self.daily_minute_spin)
        daily_time_layout.addStretch()
        daily_layout.addLayout(daily_time_layout)
        daily_layout.addWidget(QLabel("示例: 每天 09:30 执行"))
        
        self.config_stack.addWidget(daily_widget)
        
        # --- 每周配置面板 ---
        weekly_widget = QWidget()
        weekly_layout = QVBoxLayout(weekly_widget)
        weekly_layout.setContentsMargins(0, 0, 0, 0)
        
        weekly_time_layout = QHBoxLayout()
        weekly_time_layout.addWidget(QLabel("执行时间:"))
        self.weekly_hour_spin = QSpinBox()
        self.weekly_hour_spin.setRange(0, 23)
        self.weekly_hour_spin.setValue(9)
        self.weekly_hour_spin.valueChanged.connect(self._on_config_changed)
        weekly_time_layout.addWidget(self.weekly_hour_spin)
        weekly_time_layout.addWidget(QLabel(":"))
        self.weekly_minute_spin = QSpinBox()
        self.weekly_minute_spin.setRange(0, 59)
        self.weekly_minute_spin.setValue(30)
        self.weekly_minute_spin.valueChanged.connect(self._on_config_changed)
        weekly_time_layout.addWidget(self.weekly_minute_spin)
        weekly_time_layout.addStretch()
        weekly_layout.addLayout(weekly_time_layout)
        
        weekly_layout.addWidget(QLabel("选择星期:"))
        weekday_layout = QHBoxLayout()
        self.weekday_checks = {}
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i, name in enumerate(weekday_names):
            checkbox = QCheckBox(name)
            checkbox.setChecked(i < 5)  # 默认工作日
            checkbox.toggled.connect(self._on_config_changed)
            self.weekday_checks[i] = checkbox
            weekday_layout.addWidget(checkbox)
        weekday_layout.addStretch()
        weekly_layout.addLayout(weekday_layout)
        
        self.config_stack.addWidget(weekly_widget)
        
        # --- 每月配置面板 ---
        monthly_widget = QWidget()
        monthly_layout = QVBoxLayout(monthly_widget)
        monthly_layout.setContentsMargins(0, 0, 0, 0)
        
        monthly_time_layout = QHBoxLayout()
        monthly_time_layout.addWidget(QLabel("执行时间:"))
        self.monthly_hour_spin = QSpinBox()
        self.monthly_hour_spin.setRange(0, 23)
        self.monthly_hour_spin.setValue(9)
        self.monthly_hour_spin.valueChanged.connect(self._on_config_changed)
        monthly_time_layout.addWidget(self.monthly_hour_spin)
        monthly_time_layout.addWidget(QLabel(":"))
        self.monthly_minute_spin = QSpinBox()
        self.monthly_minute_spin.setRange(0, 59)
        self.monthly_minute_spin.setValue(30)
        self.monthly_minute_spin.valueChanged.connect(self._on_config_changed)
        monthly_time_layout.addWidget(self.monthly_minute_spin)
        monthly_time_layout.addStretch()
        monthly_layout.addLayout(monthly_time_layout)
        
        monthly_day_layout = QHBoxLayout()
        monthly_day_layout.addWidget(QLabel("每月第"))
        self.monthly_day_spin = QSpinBox()
        self.monthly_day_spin.setRange(1, 28)
        self.monthly_day_spin.setValue(1)
        self.monthly_day_spin.valueChanged.connect(self._on_config_changed)
        monthly_day_layout.addWidget(self.monthly_day_spin)
        monthly_day_layout.addWidget(QLabel("日执行"))
        monthly_day_layout.addStretch()
        monthly_layout.addLayout(monthly_day_layout)
        
        self.config_stack.addWidget(monthly_widget)
        
        # --- 自定义Cron配置面板 ---
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        
        cron_input_layout = QHBoxLayout()
        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("分 时 日 月 周 (例如: 0 9 * * 1-5)")
        self.cron_edit.textChanged.connect(self._on_custom_cron_changed)
        cron_input_layout.addWidget(self.cron_edit)
        
        self.cron_status_label = QLabel("")
        self.cron_status_label.setFixedWidth(80)
        cron_input_layout.addWidget(self.cron_status_label)
        
        custom_layout.addLayout(cron_input_layout)
        
        cron_help = QLabel("格式: 分 时 日 月 周 (0-59 0-23 1-31 1-12 0-6，0和7都表示周日)")
        cron_help.setStyleSheet("color: #666; font-size: 11px;")
        custom_layout.addWidget(cron_help)
        
        example_layout = QHBoxLayout()
        example_label = QLabel("常用示例:")
        example_label.setStyleSheet("color: #666; font-size: 11px;")
        example_layout.addWidget(example_label)
        
        examples = [
            ("每天9点", "0 9 * * *"),
            ("工作日9点", "0 9 * * 1-5"),
            ("每小时", "0 * * * *"),
            ("每5分钟", "*/5 * * * *"),
        ]
        
        for name, cron_expr in examples:
            btn = QPushButton(name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e9ecef;
                    border: 1px solid #ced4da;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #dee2e6;
                }
            """)
            btn.clicked.connect(lambda checked, expr=cron_expr: self._set_cron_example(expr))
            example_layout.addWidget(btn)
        
        example_layout.addStretch()
        custom_layout.addLayout(example_layout)
        
        self.config_stack.addWidget(custom_widget)
        
        layout.addWidget(self.config_stack)

        # ==================== Cron预览 ====================
        preview_group = QGroupBox("定时预览")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("每天 09:30 执行")
        self.preview_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #28a745;
            padding: 10px;
            background-color: #d4edda;
            border-radius: 4px;
        """)
        preview_layout.addWidget(self.preview_label)
        
        self.cron_preview = QLabel("Cron表达式: 30 9 * * *")
        self.cron_preview.setStyleSheet("color: #666; font-size: 12px;")
        preview_layout.addWidget(self.cron_preview)
        
        self.next_run_label = QLabel("")
        self.next_run_label.setStyleSheet("color: #007bff; font-size: 12px;")
        preview_layout.addWidget(self.next_run_label)
        
        layout.addWidget(preview_group)

        # 启用开关
        enable_layout = QHBoxLayout()
        self.enable_checkbox = QCheckBox("启用此定时任务")
        self.enable_checkbox.setChecked(True)
        enable_layout.addWidget(self.enable_checkbox)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)

        # 按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # 定时任务列表
        list_group = QGroupBox("已配置的定时任务")
        list_layout = QVBoxLayout(list_group)

        self.scheduled_table = QTableWidget()
        self.scheduled_table.setColumnCount(5)
        self.scheduled_table.setHorizontalHeaderLabels([
            "任务名称", "定时规则", "状态", "数据源", "操作"
        ])
        self.scheduled_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scheduled_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.scheduled_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.scheduled_table.setMinimumHeight(100)
        list_layout.addWidget(self.scheduled_table)

        list_btn_layout = QHBoxLayout()
        self.refresh_list_btn = QPushButton("刷新")
        self.refresh_list_btn.clicked.connect(self._load_scheduled_tasks)
        list_btn_layout.addWidget(self.refresh_list_btn)

        self.edit_schedule_btn = QPushButton("编辑定时")
        self.edit_schedule_btn.clicked.connect(self._edit_selected_schedule)
        list_btn_layout.addWidget(self.edit_schedule_btn)

        self.delete_schedule_btn = QPushButton("删除定时")
        self.delete_schedule_btn.clicked.connect(self._delete_selected_schedule)
        list_btn_layout.addWidget(self.delete_schedule_btn)

        self.trigger_now_btn = QPushButton("立即执行")
        self.trigger_now_btn.clicked.connect(self._trigger_selected_now)
        list_btn_layout.addWidget(self.trigger_now_btn)

        list_btn_layout.addStretch()
        list_layout.addLayout(list_btn_layout)
        layout.addWidget(list_group)

        # 初始化
        self._on_type_changed()
        self._load_scheduled_tasks()

    def _load_tasks_data(self):
        """加载任务数据"""
        try:
            if not self.config_manager:
                return

            tasks = self.config_manager.get_import_tasks()
            self.task_list.clear()

            for task in tasks:
                display_text = f"{task.name} ({task.data_source})"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, task.task_id)
                self.task_list.addItem(item)
            
            logger.info(f"已加载 {len(tasks)} 个任务到列表")

        except Exception as e:
            logger.error(f"加载任务列表失败: {e}")

    def _preselect_tasks_data(self):
        """预选任务"""
        try:
            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                if item and item.data(Qt.UserRole) in self.preselected_task_ids:
                    item.setSelected(True)
            self._on_tasks_selected()
        except Exception as e:
            logger.error(f"预选任务失败: {e}")

    def _on_tasks_selected(self):
        """任务多选改变"""
        self.selected_task_ids = []
        for item in self.task_list.selectedItems():
            task_id = item.data(Qt.UserRole)
            if task_id:
                self.selected_task_ids.append(task_id)

    def _on_type_changed(self):
        """定时类型改变 - 切换配置面板"""
        if self.daily_radio.isChecked():
            self.config_stack.setCurrentIndex(0)
        elif self.weekly_radio.isChecked():
            self.config_stack.setCurrentIndex(1)
        elif self.monthly_radio.isChecked():
            self.config_stack.setCurrentIndex(2)
        elif self.custom_radio.isChecked():
            self.config_stack.setCurrentIndex(3)
        
        self._on_config_changed()

    def _on_config_changed(self):
        """配置改变 - 更新Cron表达式和预览"""
        self._update_cron()
        self._update_preview()

    def _set_cron_example(self, cron_expr: str):
        """设置Cron示例"""
        self.cron_edit.setText(cron_expr)

    def _validate_cron(self, cron_expr: str) -> tuple:
        """验证Cron表达式"""
        if not cron_expr or not cron_expr.strip():
            return False, "表达式为空"
        
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return False, f"需要5个字段，当前有{len(parts)}个"
        
        if CRONITER_AVAILABLE:
            try:
                croniter(cron_expr)
                return True, ""
            except ValueError as e:
                return False, str(e)
        else:
            field_ranges = [
                (0, 59, "分钟"),
                (0, 23, "小时"),
                (1, 31, "日"),
                (1, 12, "月"),
                (0, 6, "周"),
            ]
            
            for i, (min_val, max_val, name) in enumerate(field_ranges):
                part = parts[i]
                if part == "*":
                    continue
                try:
                    if "/" in part:
                        base, step = part.split("/")
                        if base != "*" and (int(base) < min_val or int(base) > max_val):
                            return False, f"{name}字段范围应为{min_val}-{max_val}"
                        if int(step) < 1:
                            return False, f"{name}字段步长应大于0"
                    elif "-" in part:
                        start, end = part.split("-")
                        if int(start) < min_val or int(end) > max_val or int(start) > int(end):
                            return False, f"{name}字段范围应为{min_val}-{max_val}"
                    elif "," in part:
                        for val in part.split(","):
                            if int(val) < min_val or int(val) > max_val:
                                return False, f"{name}字段范围应为{min_val}-{max_val}"
                    else:
                        val = int(part)
                        if val < min_val or val > max_val:
                            return False, f"{name}字段范围应为{min_val}-{max_val}"
                except ValueError:
                    return False, f"{name}字段格式错误"
            
            return True, ""

    def _cron_to_human_readable(self, cron_expr: str) -> str:
        """将Cron表达式转换为人类可读的描述"""
        if not cron_expr:
            return "未设置"
        
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return f"自定义: {cron_expr}"
        
        minute, hour, day, month, weekday = parts
        
        time_desc = ""
        if minute == "*" and hour == "*":
            time_desc = "每分钟"
        elif minute != "*" and hour != "*":
            try:
                h, m = int(hour), int(minute)
                time_desc = f"{h:02d}:{m:02d}"
            except:
                time_desc = f"{hour}:{minute}"
        else:
            time_desc = f"{hour}:{minute}"
        
        if day == "*" and month == "*" and weekday == "*":
            if time_desc == "每分钟":
                return "每分钟执行一次"
            return f"每天 {time_desc} 执行"
        
        if weekday != "*" and day == "*" and month == "*":
            weekday_names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
            if "-" in weekday:
                try:
                    start, end = map(int, weekday.split("-"))
                    days = [weekday_names[i] for i in range(start, end + 1)]
                    return f"每 {', '.join(days)} {time_desc} 执行"
                except:
                    pass
            elif "," in weekday:
                try:
                    days = [weekday_names[int(d)] for d in weekday.split(",")]
                    return f"每 {', '.join(days)} {time_desc} 执行"
                except:
                    pass
            else:
                try:
                    w = int(weekday)
                    if 0 <= w <= 6:
                        return f"每{weekday_names[w]} {time_desc} 执行"
                except:
                    pass
            return f"每周 {time_desc} 执行"
        
        if day != "*" and weekday == "*" and month == "*":
            try:
                d = int(day)
                return f"每月 {d} 日 {time_desc} 执行"
            except:
                pass
            return f"每月 {time_desc} 执行"
        
        return f"自定义: {cron_expr}"

    def _get_next_run_times(self, cron_expr: str, count: int = 3) -> list:
        """获取接下来几次执行时间"""
        if not CRONITER_AVAILABLE or not cron_expr:
            return []
        
        try:
            cron = croniter(cron_expr, datetime.now())
            return [cron.get_next(datetime) for _ in range(count)]
        except:
            return []

    def _on_custom_cron_changed(self):
        """自定义Cron表达式改变"""
        cron_expr = self.cron_edit.text().strip()
        
        if not cron_expr:
            self.cron_status_label.setText("")
            self.cron_status_label.setStyleSheet("color: #666;")
            self.schedule_cron = None
            self._update_preview()
            return
        
        is_valid, error_msg = self._validate_cron(cron_expr)
        
        if is_valid:
            self.cron_status_label.setText("✓ 有效")
            self.cron_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.schedule_cron = cron_expr
        else:
            self.cron_status_label.setText("✗ 无效")
            self.cron_status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.schedule_cron = None
        
        self._update_preview()

    def _update_cron(self):
        """根据当前类型更新Cron表达式"""
        if self.daily_radio.isChecked():
            hour = self.daily_hour_spin.value()
            minute = self.daily_minute_spin.value()
            self.schedule_cron = f"{minute} {hour} * * *"
            
        elif self.weekly_radio.isChecked():
            hour = self.weekly_hour_spin.value()
            minute = self.weekly_minute_spin.value()
            weekdays = []
            for i, checkbox in self.weekday_checks.items():
                if checkbox.isChecked():
                    weekdays.append(str(i + 1))
            weekday_str = ",".join(weekdays) if weekdays else "*"
            self.schedule_cron = f"{minute} {hour} * * {weekday_str}"
            
        elif self.monthly_radio.isChecked():
            hour = self.monthly_hour_spin.value()
            minute = self.monthly_minute_spin.value()
            day = self.monthly_day_spin.value()
            self.schedule_cron = f"{minute} {hour} {day} * *"
            
        elif self.custom_radio.isChecked():
            self.schedule_cron = self.cron_edit.text().strip() or None

    def _update_preview(self):
        """更新预览"""
        if not self.schedule_cron:
            self.preview_label.setText("请配置定时规则")
            self.preview_label.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: #6c757d;
                padding: 10px;
                background-color: #f0f0f0;
                border-radius: 4px;
            """)
            self.cron_preview.setText("")
            self.next_run_label.setText("")
            return

        is_valid, error_msg = self._validate_cron(self.schedule_cron)
        
        if not is_valid:
            self.preview_label.setText(f"⚠ 表达式无效: {error_msg}")
            self.preview_label.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                color: #dc3545;
                padding: 10px;
                background-color: #f8d7da;
                border-radius: 4px;
            """)
            self.cron_preview.setText(f"Cron: {self.schedule_cron}")
            self.next_run_label.setText("")
            return

        human_desc = self._cron_to_human_readable(self.schedule_cron)
        self.preview_label.setText(human_desc)
        self.preview_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #28a745;
            padding: 10px;
            background-color: #d4edda;
            border-radius: 4px;
        """)
        
        self.cron_preview.setText(f"Cron表达式: {self.schedule_cron}")
        
        next_runs = self._get_next_run_times(self.schedule_cron, 3)
        if next_runs:
            next_str = "下次执行: " + next_runs[0].strftime("%Y-%m-%d %H:%M")
            if len(next_runs) > 1:
                next_str += f" (之后: {next_runs[1].strftime('%H:%M')}, {next_runs[2].strftime('%H:%M')})"
            self.next_run_label.setText(next_str)
        else:
            self.next_run_label.setText("")

    def _on_accept(self):
        """确认保存"""
        if not self.selected_task_ids:
            QMessageBox.warning(self, "警告", "请选择要配置的任务")
            return

        if not self.schedule_cron:
            QMessageBox.warning(self, "警告", "请配置定时规则")
            return
        
        is_valid, error_msg = self._validate_cron(self.schedule_cron)
        if not is_valid:
            QMessageBox.warning(self, "警告", f"Cron表达式无效: {error_msg}")
            return

        try:
            for task_id in self.selected_task_ids:
                self.config_manager.update_import_task(
                    task_id,
                    schedule_cron=self.schedule_cron,
                    enabled=self.enable_checkbox.isChecked()
                )
                logger.info(f"保存定时任务配置: {task_id}, cron: {self.schedule_cron}")
            
            QMessageBox.information(self, "成功", f"已为 {len(self.selected_task_ids)} 个任务设置定时任务")
            self.accept()

        except Exception as e:
            logger.error(f"保存定时任务配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _load_scheduled_tasks(self):
        """加载已配置的定时任务"""
        try:
            self.scheduled_table.setRowCount(0)

            if not self.config_manager:
                return

            tasks = self.config_manager.get_import_tasks()
            scheduled_tasks = [
                task for task in tasks
                if hasattr(task, 'schedule_cron') and task.schedule_cron
            ]

            for task in scheduled_tasks:
                row = self.scheduled_table.rowCount()
                self.scheduled_table.insertRow(row)

                self.scheduled_table.setItem(row, 0, QTableWidgetItem(task.name))
                self.scheduled_table.setItem(row, 1, QTableWidgetItem(task.schedule_cron))
                self.scheduled_table.setItem(row, 2, QTableWidgetItem("启用" if task.enabled else "禁用"))
                self.scheduled_table.setItem(row, 3, QTableWidgetItem(task.data_source))

            logger.info(f"加载了 {len(scheduled_tasks)} 个定时任务")

        except Exception as e:
            logger.error(f"加载定时任务列表失败: {e}")

    def _edit_selected_schedule(self):
        """编辑选中的定时任务配置"""
        current_row = self.scheduled_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要编辑的定时任务")
            return

        task_name = self.scheduled_table.item(current_row, 0).text()
        cron = self.scheduled_table.item(current_row, 1).text()

        try:
            target_task = None
            for task in self.config_manager.get_import_tasks():
                if task.name == task_name:
                    target_task = task
                    break

            if not target_task:
                QMessageBox.warning(self, "错误", "找不到任务")
                return

            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                if item and item.data(Qt.UserRole) == target_task.task_id:
                    item.setSelected(True)
                    break

            if cron:
                self._parse_cron_and_update_ui(cron)

            self.task_list.setFocus()
            logger.info(f"正在编辑定时任务: {task_name}")

        except Exception as e:
            logger.error(f"编辑定时任务失败: {e}")
            QMessageBox.critical(self, "错误", f"编辑失败: {e}")

    def _parse_cron_and_update_ui(self, cron: str):
        """解析Cron表达式并更新UI"""
        try:
            parts = cron.strip().split()
            if len(parts) < 5:
                self.custom_radio.setChecked(True)
                self.cron_edit.setText(cron)
                return

            minute, hour, day, month, weekday = parts[0], parts[1], parts[2], parts[3], parts[4]

            if day == "*" and month == "*" and weekday == "*":
                # 每日: * * * * *
                self.daily_radio.setChecked(True)
                self.daily_hour_spin.setValue(int(hour))
                self.daily_minute_spin.setValue(int(minute))
            elif weekday != "*" and day == "*" and month == "*":
                # 每周: * * * * 1-5
                self.weekly_radio.setChecked(True)
                self.weekly_hour_spin.setValue(int(hour))
                self.weekly_minute_spin.setValue(int(minute))
                self._parse_weekdays(weekday)
            elif day != "*" and weekday == "*" and month == "*":
                # 每月: * * 1 * *
                self.monthly_radio.setChecked(True)
                self.monthly_hour_spin.setValue(int(hour))
                self.monthly_minute_spin.setValue(int(minute))
                self.monthly_day_spin.setValue(int(day))
            else:
                # 其他复杂表达式归为自定义
                self.custom_radio.setChecked(True)
                self.cron_edit.setText(cron)

        except Exception as e:
            logger.warning(f"解析Cron表达式失败: {e}")
            self.custom_radio.setChecked(True)
            self.cron_edit.setText(cron)

    def _parse_weekdays(self, weekday_str: str):
        """解析星期表达式"""
        try:
            for i in range(7):
                self.weekday_checks[i].setChecked(False)

            if "-" in weekday_str:
                start, end = map(int, weekday_str.split("-"))
                for i in range(start, end + 1):
                    if i in self.weekday_checks:
                        self.weekday_checks[i].setChecked(True)
            elif "," in weekday_str:
                for d in weekday_str.split(","):
                    d = int(d)
                    if d in self.weekday_checks:
                        self.weekday_checks[d].setChecked(True)
            else:
                try:
                    d = int(weekday_str)
                    if d in self.weekday_checks:
                        self.weekday_checks[d].setChecked(True)
                except ValueError:
                    pass

        except Exception as e:
            logger.warning(f"解析星期表达式失败: {e}")

    def _delete_selected_schedule(self):
        """删除选中的定时任务配置"""
        current_row = self.scheduled_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要删除的定时任务")
            return

        task_name = self.scheduled_table.item(current_row, 0).text()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除任务 \"{task_name}\" 的定时配置吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                for task in self.config_manager.get_import_tasks():
                    if task.name == task_name:
                        self.config_manager.update_import_task(
                            task.task_id,
                            schedule_cron=None,
                            enabled=True
                        )
                        logger.info(f"已删除定时配置: {task_name}")
                        break

                self._load_scheduled_tasks()
                QMessageBox.information(self, "成功", "定时配置已删除")

            except Exception as e:
                logger.error(f"删除定时配置失败: {e}")
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def _trigger_selected_now(self):
        """立即执行选中的任务"""
        current_row = self.scheduled_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要执行的任务")
            return

        task_name = self.scheduled_table.item(current_row, 0).text()

        try:
            target_task = None
            for task in self.config_manager.get_import_tasks():
                if task.name == task_name:
                    target_task = task
                    break

            if not target_task:
                QMessageBox.warning(self, "错误", "找不到任务")
                return

            if self.import_engine:
                success = self.import_engine.start_import_task(target_task.task_id)
                if success:
                    logger.info(f"立即执行任务: {task_name}")
                    QMessageBox.information(self, "成功", f"任务 \"{task_name}\" 已启动")
                else:
                    QMessageBox.warning(self, "失败", "任务启动失败")
            else:
                QMessageBox.warning(self, "错误", "导入引擎不可用")

        except Exception as e:
            logger.error(f"立即执行任务失败: {e}")
            QMessageBox.critical(self, "错误", f"执行失败: {e}")
