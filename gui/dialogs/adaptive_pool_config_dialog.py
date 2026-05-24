#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应连接池配置对话框

允许用户配置自适应连接池的各项参数。

作者: AI Assistant
日期: 2025-10-13
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QSpinBox, QDoubleSpinBox,
    QCheckBox, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from loguru import logger
from typing import Dict, Any

from .base_dialog import BaseDialog


class AdaptivePoolConfigDialog(BaseDialog):
    """自适应连接池配置对话框"""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="自适应连接池配置",
            min_size=(500, 600),
            settings_key="AdaptivePoolConfigDialog"
        )

        self._init_ui()
        self._load_current_config()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 启用/禁用
        self.enabled_checkbox = QCheckBox("启用自适应连接池管理")
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.stateChanged.connect(self._toggle_controls)
        main_layout.addWidget(self.enabled_checkbox)

        # 边界配置
        self._create_boundary_group(main_layout)

        # 触发阈值
        self._create_threshold_group(main_layout)

        # 调整策略
        self._create_strategy_group(main_layout)

        # 时间窗口
        self._create_timing_group(main_layout)

        # 按钮
        self._create_buttons(main_layout)

    def _create_boundary_group(self, parent_layout):
        """创建边界配置组"""
        group = QGroupBox("连接池边界")
        layout = QFormLayout(group)

        # 最小值
        self.min_pool_spin = QSpinBox()
        self.min_pool_spin.setRange(1, 20)
        self.min_pool_spin.setValue(3)
        self.min_pool_spin.setToolTip("连接池最小大小，不会低于此值")
        layout.addRow("最小值 (min_pool_size):", self.min_pool_spin)

        # 最大值
        self.max_pool_spin = QSpinBox()
        self.max_pool_spin.setRange(10, 100)
        self.max_pool_spin.setValue(50)
        self.max_pool_spin.setToolTip("连接池最大大小，不会超过此值")
        layout.addRow("最大值 (max_pool_size):", self.max_pool_spin)

        parent_layout.addWidget(group)

    def _create_threshold_group(self, parent_layout):
        """创建触发阈值组"""
        group = QGroupBox("触发阈值")
        layout = QFormLayout(group)

        # 扩容阈值
        self.scale_up_threshold_spin = QDoubleSpinBox()
        self.scale_up_threshold_spin.setRange(0.5, 1.0)
        self.scale_up_threshold_spin.setSingleStep(0.05)
        self.scale_up_threshold_spin.setValue(0.8)
        self.scale_up_threshold_spin.setSuffix("%")
        self.scale_up_threshold_spin.setDecimals(2)
        self.scale_up_threshold_spin.setToolTip("使用率超过此值时触发扩容")
        layout.addRow("扩容触发 (usage):", self.scale_up_threshold_spin)

        # 缩容阈值
        self.scale_down_threshold_spin = QDoubleSpinBox()
        self.scale_down_threshold_spin.setRange(0.1, 0.5)
        self.scale_down_threshold_spin.setSingleStep(0.05)
        self.scale_down_threshold_spin.setValue(0.3)
        self.scale_down_threshold_spin.setSuffix("%")
        self.scale_down_threshold_spin.setDecimals(2)
        self.scale_down_threshold_spin.setToolTip("使用率低于此值时触发缩容")
        layout.addRow("缩容触发 (usage):", self.scale_down_threshold_spin)

        # 溢出阈值
        self.overflow_threshold_spin = QDoubleSpinBox()
        self.overflow_threshold_spin.setRange(0.3, 1.0)
        self.overflow_threshold_spin.setSingleStep(0.1)
        self.overflow_threshold_spin.setValue(0.5)
        self.overflow_threshold_spin.setSuffix("%")
        self.overflow_threshold_spin.setDecimals(2)
        self.overflow_threshold_spin.setToolTip("溢出连接超过pool_size的此比例时触发扩容")
        layout.addRow("溢出触发:", self.overflow_threshold_spin)

        parent_layout.addWidget(group)

    def _create_strategy_group(self, parent_layout):
        """创建调整策略组"""
        group = QGroupBox("调整策略")
        layout = QFormLayout(group)

        # 扩容因子
        self.scale_up_factor_spin = QDoubleSpinBox()
        self.scale_up_factor_spin.setRange(1.2, 3.0)
        self.scale_up_factor_spin.setSingleStep(0.1)
        self.scale_up_factor_spin.setValue(1.5)
        self.scale_up_factor_spin.setDecimals(1)
        self.scale_up_factor_spin.setToolTip("扩容时的倍数 (new_size = old_size × factor)")
        layout.addRow("扩容因子:", self.scale_up_factor_spin)

        # 缩容因子
        self.scale_down_factor_spin = QDoubleSpinBox()
        self.scale_down_factor_spin.setRange(0.5, 0.9)
        self.scale_down_factor_spin.setSingleStep(0.1)
        self.scale_down_factor_spin.setValue(0.8)
        self.scale_down_factor_spin.setDecimals(1)
        self.scale_down_factor_spin.setToolTip("缩容时的比例 (new_size = old_size × factor)")
        layout.addRow("缩容因子:", self.scale_down_factor_spin)

        parent_layout.addWidget(group)

    def _create_timing_group(self, parent_layout):
        """创建时间窗口组"""
        group = QGroupBox("时间窗口")
        layout = QFormLayout(group)

        # 指标窗口
        self.metrics_window_spin = QSpinBox()
        self.metrics_window_spin.setRange(30, 300)
        self.metrics_window_spin.setSingleStep(10)
        self.metrics_window_spin.setValue(60)
        self.metrics_window_spin.setSuffix(" 秒")
        self.metrics_window_spin.setToolTip("决策时查看最近N秒的指标")
        layout.addRow("指标窗口:", self.metrics_window_spin)

        # 冷却期
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(10, 300)
        self.cooldown_spin.setSingleStep(10)
        self.cooldown_spin.setValue(60)
        self.cooldown_spin.setSuffix(" 秒")
        self.cooldown_spin.setToolTip("调整后N秒内不再调整，防止频繁变动")
        layout.addRow("冷却期:", self.cooldown_spin)

        # 采集间隔
        self.collection_interval_spin = QSpinBox()
        self.collection_interval_spin.setRange(2, 60)
        self.collection_interval_spin.setSingleStep(1)
        self.collection_interval_spin.setValue(10)
        self.collection_interval_spin.setSuffix(" 秒")
        self.collection_interval_spin.setToolTip("每N秒采集一次指标")
        layout.addRow("采集间隔:", self.collection_interval_spin)

        parent_layout.addWidget(group)

    def _create_buttons(self, parent_layout):
        """创建按钮"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # 保存按钮
        self.save_button = QPushButton("保存并应用")
        self.save_button.setObjectName("save_button")
        self.save_button.clicked.connect(self._save_config)
        button_layout.addWidget(self.save_button)

        # 取消按钮
        self.cancel_button = QPushButton("❌ 取消")
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        parent_layout.addLayout(button_layout)

    def _toggle_controls(self, state):
        """切换控件启用状态"""
        enabled = (state == Qt.Checked)

        self.min_pool_spin.setEnabled(enabled)
        self.max_pool_spin.setEnabled(enabled)
        self.scale_up_threshold_spin.setEnabled(enabled)
        self.scale_down_threshold_spin.setEnabled(enabled)
        self.overflow_threshold_spin.setEnabled(enabled)
        self.scale_up_factor_spin.setEnabled(enabled)
        self.scale_down_factor_spin.setEnabled(enabled)
        self.metrics_window_spin.setEnabled(enabled)
        self.cooldown_spin.setEnabled(enabled)
        self.collection_interval_spin.setEnabled(enabled)

    def _load_current_config(self):
        """加载当前配置"""
        try:
            from core.containers import get_service_container
            from core.services.config_service import ConfigService
            from core.database.connection_pool_config import ConnectionPoolConfigManager

            container = get_service_container()
            config_service = container.resolve(ConfigService)
            config_manager = ConnectionPoolConfigManager(config_service)

            config = config_manager.load_adaptive_config()

            # 应用到UI
            self.enabled_checkbox.setChecked(config.get('enabled', True))
            self.min_pool_spin.setValue(config.get('min_pool_size', 3))
            self.max_pool_spin.setValue(config.get('max_pool_size', 50))
            self.scale_up_threshold_spin.setValue(config.get('scale_up_usage_threshold', 0.8) * 100)
            self.scale_down_threshold_spin.setValue(config.get('scale_down_usage_threshold', 0.3) * 100)
            self.overflow_threshold_spin.setValue(config.get('scale_up_overflow_threshold', 0.5) * 100)
            self.scale_up_factor_spin.setValue(config.get('scale_up_factor', 1.5))
            self.scale_down_factor_spin.setValue(config.get('scale_down_factor', 0.8))
            self.metrics_window_spin.setValue(config.get('metrics_window_seconds', 60))
            self.cooldown_spin.setValue(config.get('cooldown_seconds', 60))
            self.collection_interval_spin.setValue(config.get('collection_interval', 10))

            logger.info("已加载当前配置")

        except Exception as e:
            logger.warning(f"加载配置失败，使用默认值: {e}")

    def _save_config(self):
        """保存配置"""
        try:
            # 验证配置
            if self.min_pool_spin.value() >= self.max_pool_spin.value():
                QMessageBox.warning(self, "配置错误", "最小值必须小于最大值！")
                return

            if self.scale_down_threshold_spin.value() >= self.scale_up_threshold_spin.value():
                QMessageBox.warning(self, "配置错误", "缩容阈值必须小于扩容阈值！")
                return

            # 构建配置字典
            config = {
                'enabled': self.enabled_checkbox.isChecked(),
                'min_pool_size': self.min_pool_spin.value(),
                'max_pool_size': self.max_pool_spin.value(),
                'scale_up_usage_threshold': self.scale_up_threshold_spin.value() / 100,
                'scale_down_usage_threshold': self.scale_down_threshold_spin.value() / 100,
                'scale_up_overflow_threshold': self.overflow_threshold_spin.value() / 100,
                'metrics_window_seconds': self.metrics_window_spin.value(),
                'cooldown_seconds': self.cooldown_spin.value(),
                'collection_interval': self.collection_interval_spin.value(),
                'scale_up_factor': self.scale_up_factor_spin.value(),
                'scale_down_factor': self.scale_down_factor_spin.value()
            }

            # 保存到ConfigService
            from core.containers import get_service_container
            from core.services.config_service import ConfigService
            from core.database.connection_pool_config import ConnectionPoolConfigManager

            container = get_service_container()
            config_service = container.resolve(ConfigService)
            config_manager = ConnectionPoolConfigManager(config_service)

            config_manager.save_adaptive_config(config)

            # 提示重启
            reply = QMessageBox.question(
                self,
                "配置已保存",
                "配置已保存！\n\n是否立即重启自适应管理以应用新配置？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                # 重启自适应管理
                from core.adaptive_pool_initializer import stop_adaptive_pool, initialize_adaptive_pool
                stop_adaptive_pool()
                initialize_adaptive_pool()
                QMessageBox.information(self, "成功", "自适应管理已重启，新配置已生效！")

            self.accept()

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")
