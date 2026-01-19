#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连接池配置对话框

提供图形化界面配置连接池参数，支持：
1. 自动优化（推荐）
2. 手动配置（高级）
3. 热重载（立即生效）

作者: AI Assistant
日期: 2025-10-12
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QLabel, QSlider, QSpinBox, QDoubleSpinBox, QPushButton,
    QComboBox, QCheckBox, QMessageBox, QFormLayout
)
from PyQt5.QtCore import Qt
from loguru import logger


class ConnectionPoolConfigWidget(QWidget):
    """连接池配置组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = None
        self.db = None
        self._init_db()
        self.init_ui()
        self.load_config()

    def _init_db(self):
        """初始化数据库和配置管理器"""
        try:
            from core.database.factorweave_analytics_db import FactorWeaveAnalyticsDB
            self.db = FactorWeaveAnalyticsDB()
            self.config_manager = self.db.config_manager
            logger.info("连接池配置组件已初始化")
        except Exception as e:
            logger.error(f"初始化连接池配置组件失败: {e}")

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题
        title = QLabel("连接池性能配置")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 优化模式选择
        mode_group = QGroupBox("优化模式")
        mode_layout = QVBoxLayout()

        self.auto_mode_radio = QRadioButton("自动优化（推荐）")
        self.auto_mode_radio.setChecked(True)
        self.auto_mode_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.auto_mode_radio)

        self.manual_mode_radio = QRadioButton("手动配置（高级）")
        self.manual_mode_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.manual_mode_radio)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 自动优化设置
        self.auto_group = QGroupBox("自动优化设置")
        auto_layout = QFormLayout()

        self.workload_combo = QComboBox()
        self.workload_combo.addItems(["OLAP (分析型)", "OLTP (事务型)", "MIXED (混合型)"])
        auto_layout.addRow("工作负载类型:", self.workload_combo)

        # 显示当前自动配置
        self.auto_status_label = QLabel("正在检测系统资源...")
        self.auto_status_label.setStyleSheet("color: #666; font-size: 12px;")
        auto_layout.addRow("", self.auto_status_label)

        self.auto_group.setLayout(auto_layout)
        layout.addWidget(self.auto_group)

        # 手动配置设置
        self.manual_group = QGroupBox("手动配置")
        manual_layout = QFormLayout()

        # 连接池大小
        pool_layout = QHBoxLayout()
        self.pool_size_slider = QSlider(Qt.Horizontal)
        self.pool_size_slider.setRange(1, 50)
        self.pool_size_slider.setValue(15)
        self.pool_size_label = QLabel("15")
        self.pool_size_slider.valueChanged.connect(
            lambda v: self.pool_size_label.setText(str(v))
        )
        pool_layout.addWidget(self.pool_size_slider)
        pool_layout.addWidget(self.pool_size_label)
        manual_layout.addRow("连接池大小 (1-50):", pool_layout)

        # 最大溢出
        overflow_layout = QHBoxLayout()
        self.max_overflow_slider = QSlider(Qt.Horizontal)
        self.max_overflow_slider.setRange(0, 100)
        self.max_overflow_slider.setValue(20)
        self.max_overflow_label = QLabel("20")
        self.max_overflow_slider.valueChanged.connect(
            lambda v: self.max_overflow_label.setText(str(v))
        )
        overflow_layout.addWidget(self.max_overflow_slider)
        overflow_layout.addWidget(self.max_overflow_label)
        manual_layout.addRow("最大溢出 (0-100):", overflow_layout)

        # 超时时间
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 300.0)
        self.timeout_spin.setValue(30.0)
        self.timeout_spin.setSuffix(" 秒")
        manual_layout.addRow("获取连接超时:", self.timeout_spin)

        # 回收时间
        self.recycle_spin = QSpinBox()
        self.recycle_spin.setRange(60, 86400)
        self.recycle_spin.setValue(3600)
        self.recycle_spin.setSuffix(" 秒")
        manual_layout.addRow("连接回收时间:", self.recycle_spin)

        # 内存限制
        self.memory_spin = QDoubleSpinBox()
        self.memory_spin.setRange(0, 128)
        self.memory_spin.setValue(0)
        self.memory_spin.setSpecialValueText("自动")
        self.memory_spin.setSuffix(" GB")
        manual_layout.addRow("内存限制:", self.memory_spin)

        # 线程数
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 32)
        self.threads_spin.setValue(0)
        self.threads_spin.setSpecialValueText("自动")
        manual_layout.addRow("线程数:", self.threads_spin)

        self.manual_group.setLayout(manual_layout)
        self.manual_group.setEnabled(False)
        layout.addWidget(self.manual_group)

        # 当前状态显示
        status_group = QGroupBox("当前状态")
        status_layout = QFormLayout()

        self.current_pool_size_label = QLabel("5")
        status_layout.addRow("当前池大小:", self.current_pool_size_label)

        self.current_connections_label = QLabel("0/5")
        status_layout.addRow("活跃连接:", self.current_connections_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("立即应用（热重载）")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_config)
        button_layout.addWidget(self.apply_btn)

        self.reset_btn = QPushButton("重置默认")
        self.reset_btn.clicked.connect(self.reset_config)
        button_layout.addWidget(self.reset_btn)

        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self.refresh_status)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

        # 状态标签
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _on_mode_changed(self):
        """切换优化模式"""
        auto_mode = self.auto_mode_radio.isChecked()
        self.auto_group.setEnabled(auto_mode)
        self.manual_group.setEnabled(not auto_mode)

        if auto_mode:
            self._update_auto_status()

    def _update_auto_status(self):
        """更新自动优化状态"""
        try:
            import psutil
            memory_gb = psutil.virtual_memory().total / (1024**3)
            cpu_cores = psutil.cpu_count(logical=True)

            # 计算自动配置
            memory_limit = max(2.0, memory_gb * 0.7)
            threads = min(cpu_cores, 16)

            status_text = f"检测到: {memory_gb:.1f}GB内存, {cpu_cores}核CPU\n"
            status_text += f"自动配置: {memory_limit:.1f}GB内存, {threads}线程"
            self.auto_status_label.setText(status_text)
        except Exception as e:
            self.auto_status_label.setText(f"检测失败: {e}")

    def load_config(self):
        """加载当前配置"""
        if not self.config_manager:
            return

        try:
            # 加载连接池配置
            from core.database.connection_pool_config import ConnectionPoolConfig
            pool_config = self.config_manager.load_pool_config()

            self.pool_size_slider.setValue(pool_config.pool_size)
            self.max_overflow_slider.setValue(pool_config.max_overflow)
            self.timeout_spin.setValue(pool_config.timeout)
            self.recycle_spin.setValue(pool_config.pool_recycle)

            # 加载优化配置
            opt_config = self.config_manager.load_optimization_config()
            self.memory_spin.setValue(opt_config.memory_limit_gb or 0)
            self.threads_spin.setValue(opt_config.threads or 0)

            # 加载自动优化设置
            if self.config_manager.is_auto_optimization_enabled():
                self.auto_mode_radio.setChecked(True)
                workload = self.config_manager.get_workload_type()
                workload_map = {"olap": 0, "oltp": 1, "mixed": 2}
                self.workload_combo.setCurrentIndex(workload_map.get(workload, 0))
            else:
                self.manual_mode_radio.setChecked(True)

            self.refresh_status()
            self._update_auto_status()

        except Exception as e:
            logger.error(f"加载配置失败: {e}")

    def refresh_status(self):
        """刷新当前状态"""
        if not self.db:
            return

        try:
            status = self.db.get_pool_status()
            self.current_pool_size_label.setText(str(status.get('pool_size', 'N/A')))
            checked_out = status.get('checked_out', 0)
            pool_size = status.get('pool_size', 0)
            self.current_connections_label.setText(f"{checked_out}/{pool_size}")
        except Exception as e:
            logger.error(f"刷新状态失败: {e}")

    def apply_config(self):
        """应用配置（热重载）"""
        if not self.config_manager or not self.db:
            QMessageBox.warning(self, "错误", "配置管理器未初始化")
            return

        try:
            from core.database.connection_pool_config import (
                ConnectionPoolConfig,
                DuckDBOptimizationConfig
            )

            if self.auto_mode_radio.isChecked():
                # 自动优化模式
                workload_map = {0: "olap", 1: "oltp", 2: "mixed"}
                workload = workload_map[self.workload_combo.currentIndex()]

                self.config_manager.set_auto_optimization(True, workload)
                self.status_label.setText("正在应用自动优化...")

            else:
                # 手动配置模式
                pool_config = ConnectionPoolConfig(
                    pool_size=self.pool_size_slider.value(),
                    max_overflow=self.max_overflow_slider.value(),
                    timeout=self.timeout_spin.value(),
                    pool_recycle=self.recycle_spin.value()
                )

                # 验证配置
                valid, msg = pool_config.validate()
                if not valid:
                    QMessageBox.warning(self, "配置错误", msg)
                    return

                # 保存配置
                self.config_manager.save_pool_config(pool_config)
                self.config_manager.set_auto_optimization(False)

                # 保存优化配置
                opt_config = DuckDBOptimizationConfig(
                    memory_limit_gb=self.memory_spin.value() or None,
                    threads=self.threads_spin.value() or None
                )
                self.config_manager.save_optimization_config(opt_config)

                self.status_label.setText("正在热重载连接池...")

            # 热重载连接池
            if self.db.reload_pool():
                self.status_label.setText("成功! 配置已立即生效")
                self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                self.refresh_status()

                QMessageBox.information(
                    self,
                    "配置已应用",
                    "连接池配置已更新并立即生效！\n\n无需重启应用程序。"
                )
            else:
                self.status_label.setText("失败: 热重载失败")
                self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                QMessageBox.critical(self, "应用失败", "连接池热重载失败")

        except Exception as e:
            logger.error(f"应用配置失败: {e}")
            self.status_label.setText(f"错误: {str(e)}")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            QMessageBox.critical(self, "错误", f"应用配置失败:\n{str(e)}")

    def reset_config(self):
        """重置为默认配置"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置为默认配置吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                from core.database.connection_pool_config import ConnectionPoolConfig
                default_config = ConnectionPoolConfig()

                if self.config_manager:
                    self.config_manager.save_pool_config(default_config)
                    self.config_manager.set_auto_optimization(True, "olap")

                if self.db and self.db.reload_pool(default_config):
                    self.load_config()
                    self.status_label.setText("已重置为默认配置")
                    QMessageBox.information(self, "重置成功", "已重置为默认配置并立即生效")
            except Exception as e:
                logger.error(f"重置配置失败: {e}")
                QMessageBox.critical(self, "错误", f"重置失败:\n{str(e)}")
