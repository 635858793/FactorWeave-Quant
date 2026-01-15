#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应连接池配置组件（支持多连接池）

允许用户配置每个连接池的自适应参数。
此组件将被集成到 ConnectionPoolManagerDialog 中。

作者: AI Assistant
日期: 2025-01-13
版本: 2.0（支持多连接池）
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QSpinBox, QDoubleSpinBox,
    QCheckBox, QPushButton, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt
from loguru import logger
from typing import Dict, Any


class AdaptivePoolConfigWidget(QWidget):
    """自适应连接池配置组件（支持多连接池）"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_pool_name = None

        self._init_ui()
        self._load_current_config()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 连接池选择器
        self._create_pool_selector(main_layout)

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

        main_layout.addStretch()

    def _create_pool_selector(self, parent_layout):
        """创建连接池选择器"""
        selector_group = QGroupBox("选择连接池")
        selector_layout = QFormLayout(selector_group)

        # 连接池下拉框
        self.pool_combo = QComboBox()
        self.pool_combo.addItems([
            "analytics_duckdb（分析数据库）",
            "strategy_sqlite（策略数据库）",
            "factorweave_system_sqlite（系统数据库）",
            "tradeaccount_sqlite（交易账户数据库）"
        ])
        self.pool_combo.currentTextChanged.connect(self._on_pool_changed)
        selector_layout.addRow("连接池:", self.pool_combo)

        # 连接池描述
        self.pool_description_label = QLabel()
        self.pool_description_label.setWordWrap(True)
        self.pool_description_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        selector_layout.addRow("", self.pool_description_label)

        parent_layout.addWidget(selector_group)

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
        self.save_button = QPushButton("✅ 保存并应用")
        self.save_button.setObjectName("save_button")
        self.save_button.clicked.connect(self._save_config)
        button_layout.addWidget(self.save_button)

        # 重置按钮
        self.reset_button = QPushButton("🔄 重置为默认")
        self.reset_button.setObjectName("reset_button")
        self.reset_button.clicked.connect(self._reset_config)
        button_layout.addWidget(self.reset_button)

        parent_layout.addLayout(button_layout)

    def _on_pool_changed(self, pool_name: str):
        """连接池选择改变"""
        # 解析连接池名称
        if "analytics_duckdb" in pool_name:
            self.current_pool_name = "analytics_duckdb"
            self.pool_description_label.setText(
                "<b>分析数据库（DuckDB）</b><br>"
                "高频并发访问，存储策略执行结果、技术指标、回测数据等。<br>"
                "<b>推荐启用自适应管理</b>，以应对负载变化。"
            )
        elif "strategy_sqlite" in pool_name:
            self.current_pool_name = "strategy_sqlite"
            self.pool_description_label.setText(
                "<b>策略数据库（SQLite）</b><br>"
                "中频访问，存储策略配置和策略数据。<br>"
                "<b>默认禁用自适应</b>，但可根据实际需求启用。"
            )
        elif "factorweave_system_sqlite" in pool_name:
            self.current_pool_name = "factorweave_system_sqlite"
            self.pool_description_label.setText(
                "<b>系统数据库（SQLite）</b><br>"
                "低频访问，存储用户偏好、用户反馈等配置数据。<br>"
                "<b>不建议启用自适应</b>，使用固定配置即可。"
            )
        elif "tradeaccount_sqlite" in pool_name:
            self.current_pool_name = "tradeaccount_sqlite"
            self.pool_description_label.setText(
                "<b>交易账户数据库（SQLite）</b><br>"
                "低频访问，存储交易账户信息。<br>"
                "<b>不建议启用自适应</b>，使用固定配置即可。"
            )

        # 加载该连接池的配置
        self._load_pool_config()

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

            # 加载当前选择的连接池配置
            if self.current_pool_name:
                config = config_manager.load_adaptive_pool_config(self.current_pool_name)

                # 应用到UI
                self.enabled_checkbox.setChecked(config.get('enabled', False))

                if config.get('enabled', False):
                    # 启用了自适应，显示自适应参数
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
                else:
                    # 禁用了自适应，显示固定配置
                    self.min_pool_spin.setValue(config.get('pool_size', 10))
                    self.max_pool_spin.setValue(config.get('max_pool_size', 30))
                    self.scale_up_threshold_spin.setValue(80)
                    self.scale_down_threshold_spin.setValue(30)
                    self.overflow_threshold_spin.setValue(50)
                    self.scale_up_factor_spin.setValue(1.5)
                    self.scale_down_factor_spin.setValue(0.8)
                    self.metrics_window_spin.setValue(60)
                    self.cooldown_spin.setValue(60)
                    self.collection_interval_spin.setValue(10)

            logger.info("已加载当前自适应配置")

        except Exception as e:
            logger.warning(f"加载自适应配置失败，使用默认值: {e}")

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
            config_manager.save_adaptive_pool_config(self.current_pool_name, config)

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
                from core.services.database_service import DatabaseService
                from core.containers import get_service_container

                container = get_service_container()
                db_service = container.resolve(DatabaseService)

                # 停止旧的管理器
                db_service.stop_adaptive_manager(self.current_pool_name)

                # 启用新的管理器
                if config['enabled']:
                    new_config = {
                        'enabled': True,
                        'min_pool_size': config['min_pool_size'],
                        'max_pool_size': config['max_pool_size'],
                        'scale_up_usage_threshold': config['scale_up_usage_threshold'],
                        'scale_down_usage_threshold': config['scale_down_usage_threshold'],
                        'scale_up_overflow_threshold': config['scale_up_overflow_threshold'],
                        'metrics_window_seconds': config['metrics_window_seconds'],
                        'cooldown_seconds': config['cooldown_seconds'],
                        'collection_interval': config['collection_interval'],
                        'scale_up_factor': config['scale_up_factor'],
                        'scale_down_factor': config['scale_down_factor']
                    }
                    db_service.create_adaptive_manager(self.current_pool_name, new_config)
                    QMessageBox.information(self, "成功", "自适应管理已重启，新配置已生效！")
                else:
                    QMessageBox.information(self, "成功", "配置已保存，自适应管理已禁用！")

        except Exception as e:
            logger.error(f"保存自适应配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败:\n{str(e)}")

    def _reset_config(self):
        """重置为默认配置"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要将当前连接池的配置重置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 重置为默认值
            self.enabled_checkbox.setChecked(True)

            # 根据连接池类型设置不同的默认值
            if self.current_pool_name == "analytics_duckdb":
                # 分析数据库：启用自适应，使用自适应默认值
                self.min_pool_spin.setValue(3)
                self.max_pool_spin.setValue(50)
                self.scale_up_threshold_spin.setValue(80)
                self.scale_down_threshold_spin.setValue(30)
                self.overflow_threshold_spin.setValue(50)
                self.scale_up_factor_spin.setValue(1.5)
                self.scale_down_factor_spin.setValue(0.8)
                self.metrics_window_spin.setValue(60)
                self.cooldown_spin.setValue(60)
                self.collection_interval_spin.setValue(10)
            else:
                # 其他数据库：禁用自适应，使用固定配置默认值
                self.enabled_checkbox.setChecked(False)
                self.min_pool_spin.setValue(10)
                self.max_pool_spin.setValue(30)
                self.scale_up_threshold_spin.setValue(80)
                self.scale_down_threshold_spin.setValue(30)
                self.overflow_threshold_spin.setValue(50)
                self.scale_up_factor_spin.setValue(1.5)
                self.scale_down_factor_spin.setValue(0.8)
                self.metrics_window_spin.setValue(60)
                self.cooldown_spin.setValue(60)
                self.collection_interval_spin.setValue(10)

            QMessageBox.information(self, "成功", "配置已重置为默认值！")

    def _load_pool_config(self):
        """加载连接池配置"""
        try:
            from core.containers import get_service_container
            from core.services.config_service import ConfigService
            from core.database.connection_pool_config import ConnectionPoolConfigManager

            container = get_service_container()
            config_service = container.resolve(ConfigService)
            config_manager = ConnectionPoolConfigManager(config_service)

            # 加载当前选择的连接池配置
            if self.current_pool_name:
                config = config_manager.load_adaptive_pool_config(self.current_pool_name)

                # 应用到UI
                self.enabled_checkbox.setChecked(config.get('enabled', False))

                if config.get('enabled', False):
                    # 启用了自适应，显示自适应参数
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
                else:
                    # 禁用了自适应，显示固定配置
                    self.min_pool_spin.setValue(config.get('pool_size', 10))
                    self.max_pool_spin.setValue(config.get('max_pool_size', 30))
                    self.scale_up_threshold_spin.setValue(80)
                    self.scale_down_threshold_spin.setValue(30)
                    self.overflow_threshold_spin.setValue(50)
                    self.scale_up_factor_spin.setValue(1.5)
                    self.scale_down_factor_spin.setValue(0.8)
                    self.metrics_window_spin.setValue(60)
                    self.cooldown_spin.setValue(60)
                    self.collection_interval_spin.setValue(10)

            logger.info("已加载当前自适应配置")

        except Exception as e:
            logger.warning(f"加载自适应配置失败，使用默认值: {e}")
