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
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal, QDateTime
from loguru import logger
from typing import Optional, List, Dict, Any
from datetime import datetime


class ScheduledTaskDialog(QDialog):
    """定时任务配置对话框"""

    task_scheduled = pyqtSignal(str, str)  # task_id, schedule_cron

    def __init__(self, config_manager, import_engine=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.import_engine = import_engine
        self.selected_task_id = None
        self.schedule_cron = None

        self.setWindowTitle("⏰ 定时任务配置")
        self.setModal(True)
        self.resize(700, 550)

        self._setup_ui()
        self._load_tasks()
        self._load_scheduled_tasks()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("定时任务配置")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title_label)

        # 主要配置区域
        config_group = QGroupBox("定时配置")
        config_layout = QFormLayout(config_group)

        # 任务选择
        self.task_combo = QComboBox()
        self.task_combo.setMinimumWidth(300)
        self.task_combo.currentIndexChanged.connect(self._on_task_selected)
        config_layout.addRow("选择任务:", self.task_combo)

        # 定时类型
        type_layout = QHBoxLayout()
        self.daily_radio = QRadioButton("每日")
        self.weekly_radio = QRadioButton("每周")
        self.monthly_radio = QRadioButton("每月")
        self.custom_radio = QRadioButton("自定义")

        self.daily_radio.setChecked(True)
        self.daily_radio.toggled.connect(self._on_type_changed)
        self.weekly_radio.toggled.connect(self._on_type_changed)
        self.monthly_radio.toggled.connect(self._on_type_changed)
        self.custom_radio.toggled.connect(self._on_type_changed)

        type_layout.addWidget(self.daily_radio)
        type_layout.addWidget(self.weekly_radio)
        type_layout.addWidget(self.monthly_radio)
        type_layout.addWidget(self.custom_radio)
        type_layout.addStretch()

        type_group = QGroupBox("定时类型")
        type_group_layout = QVBoxLayout(type_group)
        type_group_layout.addLayout(type_layout)
        layout.addWidget(type_group)

        # 执行时间
        time_layout = QHBoxLayout()

        time_layout.addWidget(QLabel("执行时间:"))
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setValue(9)
        self.hour_spin.valueChanged.connect(self._on_type_changed)
        time_layout.addWidget(self.hour_spin)

        time_layout.addWidget(QLabel(":"))

        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setValue(30)
        self.minute_spin.valueChanged.connect(self._on_type_changed)
        time_layout.addWidget(self.minute_spin)

        time_layout.addStretch()

        layout.addLayout(time_layout)

        # 星期选择（每周）
        self.weekdays_group = QGroupBox("执行日期（每周）")
        weekdays_layout = QHBoxLayout(self.weekdays_group)

        self.weekday_checks = {}
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i, name in enumerate(weekday_names):
            checkbox = QCheckBox(name)
            checkbox.setChecked(i < 5)  # 默认工作日
            checkbox.toggled.connect(self._on_type_changed)
            self.weekday_checks[i] = checkbox
            weekdays_layout.addWidget(checkbox)

        weekdays_layout.addStretch()
        layout.addWidget(self.weekdays_group)

        # 日期选择（每月）
        self.day_group = QGroupBox("执行日期（每月）")
        day_layout = QHBoxLayout(self.day_group)

        day_layout.addWidget(QLabel("每月"))
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 28)
        self.day_spin.setValue(1)
        self.day_spin.valueChanged.connect(self._on_type_changed)
        day_layout.addWidget(self.day_spin)
        day_layout.addWidget(QLabel("日"))

        day_layout.addStretch()
        layout.addWidget(self.day_group)

        # 自定义Cron表达式
        cron_group = QGroupBox("自定义Cron表达式")
        cron_layout = QVBoxLayout(cron_group)

        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("分 时 日 月 周 (例如: 0 9 * * 1-5)")
        self.cron_edit.textChanged.connect(self._on_custom_cron_changed)
        cron_layout.addWidget(self.cron_edit)

        cron_help = QLabel("格式: 分 时 日 月 周 (0-59 0-23 1-31 1-12 0-6)")
        cron_help.setStyleSheet("color: #666; font-size: 11px;")
        cron_layout.addWidget(cron_help)

        layout.addWidget(cron_group)

        # Cron预览
        preview_group = QGroupBox("定时预览")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("每天 09:30 执行")
        self.preview_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #28a745;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 4px;
        """)
        preview_layout.addWidget(self.preview_label)

        self.cron_preview = QLabel("")
        self.cron_preview.setStyleSheet("color: #666; font-size: 12px;")
        preview_layout.addWidget(self.cron_preview)

        layout.addWidget(preview_group)

        # 启用开关
        enable_layout = QHBoxLayout()
        self.enable_checkbox = QCheckBox("启用此定时任务")
        self.enable_checkbox.setChecked(True)
        enable_layout.addWidget(self.enable_checkbox)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)

        # 按钮区域
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # 定时任务列表Tab
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
        self.scheduled_table.setMinimumHeight(150)
        list_layout.addWidget(self.scheduled_table)

        list_btn_layout = QHBoxLayout()
        self.refresh_list_btn = QPushButton("刷新")
        self.refresh_list_btn.clicked.connect(self._load_scheduled_tasks)
        list_btn_layout.addWidget(self.refresh_list_btn)

        self.delete_schedule_btn = QPushButton("删除定时")
        self.delete_schedule_btn.clicked.connect(self._delete_selected_schedule)
        list_btn_layout.addWidget(self.delete_schedule_btn)

        self.trigger_now_btn = QPushButton("立即执行")
        self.trigger_now_btn.clicked.connect(self._trigger_selected_now)
        list_btn_layout.addWidget(self.trigger_now_btn)

        list_btn_layout.addStretch()
        list_layout.addLayout(list_btn_layout)

        layout.addWidget(list_group)

        # 初始化UI状态
        self._update_ui_visibility()
        self._update_preview()

    def _load_tasks(self):
        """加载任务列表"""
        try:
            if not self.config_manager:
                return

            tasks = self.config_manager.get_import_tasks()

            self.task_combo.clear()
            self.task_combo.addItem("-- 选择任务 --", None)

            for task in tasks:
                display_text = f"{task.name} ({task.data_source})"
                self.task_combo.addItem(display_text, task.task_id)

        except Exception as e:
            logger.error(f"加载任务列表失败: {e}")

    def _on_task_selected(self, index):
        """任务选择改变"""
        self.selected_task_id = self.task_combo.currentData()

        if self.selected_task_id:
            task = self.config_manager.get_import_task(self.selected_task_id)
            if task and task.schedule_cron:
                self._parse_cron_and_update_ui(task.schedule_cron)

    def _parse_cron_and_update_ui(self, cron: str):
        """解析Cron表达式并更新UI"""
        try:
            parts = cron.strip().split()
            if len(parts) < 5:
                return

            minute, hour, day, month, weekday = parts[0], parts[1], parts[2], parts[3], parts[4]

            self.hour_spin.setValue(int(hour))
            self.minute_spin.setValue(int(minute))

            if day == "*" and month == "*" and weekday == "*":
                self.daily_radio.setChecked(True)
            elif weekday != "*" and day == "*":
                self.weekly_radio.setChecked(True)
                self._parse_weekdays(weekday)
            elif day != "*" and weekday == "*":
                self.monthly_radio.setChecked(True)
                self.day_spin.setValue(int(day))
            else:
                self.custom_radio.setChecked(True)
                self.cron_edit.setText(cron)

        except Exception as e:
            logger.warning(f"解析Cron表达式失败: {e}")

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
                days = map(int, weekday_str.split(","))
                for d in days:
                    if d in self.weekday_checks:
                        self.weekday_checks[d].setChecked(True)
            elif weekday_str.isdigit():
                d = int(weekday_str)
                if d in self.weekday_checks:
                    self.weekday_checks[d].setChecked(True)

        except Exception as e:
            logger.warning(f"解析星期失败: {e}")

    def _on_type_changed(self):
        """定时类型改变"""
        self._update_ui_visibility()
        self._update_preview()

    def _on_custom_cron_changed(self):
        """自定义Cron改变"""
        if self.custom_radio.isChecked():
            self._update_preview()

    def _update_ui_visibility(self):
        """更新UI可见性"""
        is_weekly = self.weekly_radio.isChecked()
        is_monthly = self.monthly_radio.isChecked()
        is_custom = self.custom_radio.isChecked()

        self.weekdays_group.setVisible(is_weekly)
        self.day_group.setVisible(is_monthly)

    def _generate_cron(self) -> str:
        """生成Cron表达式"""
        hour = self.hour_spin.value()
        minute = self.minute_spin.value()

        if self.daily_radio.isChecked():
            return f"{minute} {hour} * * *"
        elif self.weekly_radio.isChecked():
            weekdays = []
            for i, checkbox in self.weekday_checks.items():
                if checkbox.isChecked():
                    weekdays.append(str(i))
            weekday_str = ",".join(weekdays) if weekdays else "1-5"
            return f"{minute} {hour} * * {weekday_str}"
        elif self.monthly_radio.isChecked():
            day = self.day_spin.value()
            return f"{minute} {hour} {day} * *"
        elif self.custom_radio.isChecked():
            return self.cron_edit.text().strip()
        else:
            return f"{minute} {hour} * * *"

    def _update_preview(self):
        """更新预览"""
        self.schedule_cron = self._generate_cron()

        hour = self.hour_spin.value()
        minute = self.minute_spin.value()
        time_str = f"{hour:02d}:{minute:02d}"

        if self.daily_radio.isChecked():
            preview = f"每天 {time_str} 执行"
        elif self.weekly_radio.isChecked():
            weekdays = []
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            for i, checkbox in self.weekday_checks.items():
                if checkbox.isChecked():
                    weekdays.append(weekday_names[i])
            if weekdays:
                preview = f"每周{'/'.join(weekdays)} {time_str} 执行"
            else:
                preview = f"每天 {time_str} 执行（默认工作日）"
        elif self.monthly_radio.isChecked():
            day = self.day_spin.value()
            preview = f"每月{day}日 {time_str} 执行"
        elif self.custom_radio.isChecked():
            preview = f"自定义: {self.schedule_cron}"
        else:
            preview = f"每天 {time_str} 执行"

        self.preview_label.setText(preview)
        self.cron_preview.setText(f"Cron: {self.schedule_cron}")

    def _on_accept(self):
        """确认保存"""
        if not self.selected_task_id:
            QMessageBox.warning(self, "警告", "请选择要配置的任务")
            return

        if not self.schedule_cron:
            QMessageBox.warning(self, "警告", "请配置定时规则")
            return

        try:
            self.config_manager.update_import_task(
                self.selected_task_id,
                schedule_cron=self.schedule_cron,
                enabled=self.enable_checkbox.isChecked()
            )

            logger.info(f"保存定时任务配置: {self.selected_task_id}, cron: {self.schedule_cron}")
            self.accept()

        except Exception as e:
            logger.error(f"保存定时任务配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def get_schedule_cron(self) -> Optional[str]:
        """获取Cron表达式"""
        return self.schedule_cron

    def get_enabled(self) -> bool:
        """获取启用状态"""
        return self.enable_checkbox.isChecked()

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

                task_id = task.task_id

            logger.info(f"加载了 {len(scheduled_tasks)} 个定时任务")

        except Exception as e:
            logger.error(f"加载定时任务列表失败: {e}")

    def _delete_selected_schedule(self):
        """删除选中的定时任务配置"""
        current_row = self.scheduled_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要删除的定时任务")
            return

        task_name = self.scheduled_table.item(current_row, 0).text()
        cron = self.scheduled_table.item(current_row, 1).text()

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
