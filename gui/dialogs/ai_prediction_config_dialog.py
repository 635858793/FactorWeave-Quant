#!/usr/bin/env python3
"""
AI预测配置管理对话框

提供用户友好的界面来管理AI预测系统的各项配置参数
"""

import sys
import json
from loguru import logger
from datetime import datetime
from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QLineEdit, QTextEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QSplitter, QScrollArea, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon

logger = logger


class AIPredictionConfigDialog(BaseDialog):
    """AI预测配置对话框"""
    
    config_saved = pyqtSignal(object)  # 配置保存信号

    def __init__(self, parent=None, config: AIPredictionConfig = None):
        """
        初始化AI预测配置对话框
        
        Args:
            parent: 父窗口
            config: AI预测配置对象，如果为None则使用默认配置
        """
        super().__init__(
            parent,
            title="AI预测配置",
            min_size=(800, 700),
            size=(900, 800),
            settings_key="AIPredictionConfigDialog"
        )
        
        self.config = config or AIPredictionConfig()
        self.ai_service = AIPredictionService()
        self.selected_models = []
        
        self._setup_ui()
        self._load_config()
        self._connect_signals()

    def init_config_manager(self):
        """初始化配置管理器"""
        try:
            from db.models.ai_config_models import get_ai_config_manager
            self.config_manager = get_ai_config_manager()
        except Exception as e:
            logger.warning(f"配置管理器初始化失败，对话框将使用默认配置: {e}")
            self.config_manager = None

    def setup_ui(self):
        """设置用户界面"""
        try:
            self.setWindowTitle("AI预测系统配置管理")
            self.setMinimumSize(1050, 700)
            self.setModal(True)

            # 主布局
            main_layout = QVBoxLayout(self)

            # 标题
            title_label = QLabel("AI预测系统配置管理")
            title_label.setFixedHeight(30)
            title_font = QFont()
            title_font.setPointSize(16)
            title_font.setBold(True)
            title_label.setFont(title_font)
            title_label.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(title_label)

            # 分割器
            splitter = QSplitter(Qt.Horizontal)
            splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            main_layout.addWidget(splitter, 1)

            # 左侧：配置编辑区域
            config_widget = self.create_config_widget()
            splitter.addWidget(config_widget)

            # 右侧：历史和操作区域
            history_widget = self.create_history_widget()
            splitter.addWidget(history_widget)

            # 设置分割器比例
            splitter.setSizes([500, 550])

            # 底部按钮
            button_layout = self.create_button_layout()
            main_layout.addLayout(button_layout)

            # 状态标签
            self.status_label = QLabel("就绪")
            self.status_label.setFixedHeight(20)
            main_layout.addWidget(self.status_label)

        except Exception as e:
            logger.error(f"设置UI失败: {e}")
            raise

    def create_config_widget(self) -> QWidget:
        """创建配置编辑区域"""
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 配置标签页
        self.config_tabs = QTabWidget()
        self.config_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.config_tabs)

        # 模型配置标签页
        model_tab = self.create_model_config_tab()
        self.config_tabs.addTab(model_tab, "模型配置")

        # 验证配置标签页
        validation_tab = self.create_validation_config_tab()
        self.config_tabs.addTab(validation_tab, "验证配置")

        # 特征配置标签页
        feature_tab = self.create_feature_config_tab()
        self.config_tabs.addTab(feature_tab, "特征配置")

        # 缓存配置标签页
        cache_tab = self.create_cache_config_tab()
        self.config_tabs.addTab(cache_tab, "缓存配置")

        # 日志配置标签页
        logging_tab = self.create_logging_config_tab()
        self.config_tabs.addTab(logging_tab, "日志配置")

        return widget

    def create_model_config_tab(self) -> QWidget:
        """创建模型配置标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 基础模型配置
        basic_group = QGroupBox("基础配置")
        basic_layout = QFormLayout(basic_group)

        # 启用AI预测
        self.model_enabled = QCheckBox()
        basic_layout.addRow("启用AI预测:", self.model_enabled)

        # 模型类型
        self.model_type = QComboBox()
        # 使用汉语显示，但value仍为英文key
        model_items = [
            ("集成模型", "ensemble"),
            ("深度学习", "deep_learning"),
            ("统计模型", "statistical"),
            ("规则模型", "rule_based")
        ]
        for display_name, value in model_items:
            self.model_type.addItem(display_name, value)

        model_layout = QHBoxLayout()
        model_layout.addWidget(self.model_type)
        model_info_label = QLabel("(此设置会同步到预测界面)")
        model_info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        model_layout.addWidget(model_info_label)
        model_widget = QWidget()
        model_widget.setLayout(model_layout)
        basic_layout.addRow("模型类型:", model_widget)

        # 置信度阈值
        self.confidence_threshold = QDoubleSpinBox()
        self.confidence_threshold.setRange(0.0, 1.0)
        self.confidence_threshold.setSingleStep(0.1)
        self.confidence_threshold.setDecimals(2)
        basic_layout.addRow("置信度阈值:", self.confidence_threshold)

        # 预测周期
        self.prediction_horizon = QSpinBox()
        self.prediction_horizon.setRange(1, 30)
        horizon_layout = QHBoxLayout()
        horizon_layout.addWidget(self.prediction_horizon)
        info_label = QLabel("(此设置会同步到预测界面)")
        info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        horizon_layout.addWidget(info_label)
        horizon_widget = QWidget()
        horizon_widget.setLayout(horizon_layout)
        basic_layout.addRow("预测周期(天):", horizon_widget)

        # 特征窗口
        self.feature_window = QSpinBox()
        self.feature_window.setRange(5, 100)
        basic_layout.addRow("特征窗口:", self.feature_window)

        layout.addWidget(basic_group)

        # 高级配置
        advanced_group = QGroupBox("高级配置")
        advanced_layout = QFormLayout(advanced_group)

        # 缓存大小
        self.cache_size = QSpinBox()
        self.cache_size.setRange(100, 10000)
        advanced_layout.addRow("缓存大小:", self.cache_size)

        # 模型更新间隔
        self.model_update_interval = QSpinBox()
        self.model_update_interval.setRange(1, 168)
        self.model_update_interval.setSuffix("小时")
        advanced_layout.addRow("模型更新间隔:", self.model_update_interval)

        layout.addWidget(advanced_group)
        layout.addStretch()

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_validation_config_tab(self) -> QWidget:
        """创建验证配置标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 数据验证配置
        validation_group = QGroupBox("数据验证规则")
        validation_layout = QFormLayout(validation_group)

        # 最小数据点数
        self.min_data_points = QSpinBox()
        self.min_data_points.setRange(1, 1000)
        validation_layout.addRow("最小数据点数:", self.min_data_points)

        # 最大预测周期
        self.max_prediction_horizon = QSpinBox()
        self.max_prediction_horizon.setRange(1, 365)
        validation_layout.addRow("最大预测周期:", self.max_prediction_horizon)

        # 最大数据行数
        self.max_data_rows = QSpinBox()
        self.max_data_rows.setRange(1000, 100000)
        validation_layout.addRow("最大数据行数:", self.max_data_rows)

        # 必需列
        self.required_columns = QLineEdit()
        self.required_columns.setPlaceholderText("用逗号分隔，如: open,high,low,close")
        validation_layout.addRow("必需列:", self.required_columns)

        layout.addWidget(validation_group)
        layout.addStretch()

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_feature_config_tab(self) -> QWidget:
        """创建特征配置标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 特征工程配置
        feature_group = QGroupBox("特征工程设置")
        feature_layout = QFormLayout(feature_group)

        # 技术指标
        self.technical_indicators = QCheckBox()
        feature_layout.addRow("技术指标:", self.technical_indicators)

        # 形态特征
        self.pattern_features = QCheckBox()
        feature_layout.addRow("形态特征:", self.pattern_features)

        # 成交量特征
        self.volume_features = QCheckBox()
        feature_layout.addRow("成交量特征:", self.volume_features)

        # 价格特征
        self.price_features = QCheckBox()
        feature_layout.addRow("价格特征:", self.price_features)

        # 波动率特征
        self.volatility_features = QCheckBox()
        feature_layout.addRow("波动率特征:", self.volatility_features)

        layout.addWidget(feature_group)
        layout.addStretch()

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_cache_config_tab(self) -> QWidget:
        """创建缓存配置标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 缓存配置
        cache_group = QGroupBox("缓存设置")
        cache_layout = QFormLayout(cache_group)

        # 启用缓存
        self.enable_cache = QCheckBox()
        cache_layout.addRow("启用缓存:", self.enable_cache)

        # 缓存TTL
        self.cache_ttl = QSpinBox()
        self.cache_ttl.setRange(60, 3600)
        self.cache_ttl.setSuffix("秒")
        cache_layout.addRow("缓存有效期:", self.cache_ttl)

        # 最大缓存大小
        self.max_cache_size = QSpinBox()
        self.max_cache_size.setRange(100, 10000)
        cache_layout.addRow("最大缓存条目:", self.max_cache_size)

        layout.addWidget(cache_group)
        layout.addStretch()

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_logging_config_tab(self) -> QWidget:
        """创建日志配置标签页"""
        widget = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)

        # 日志配置
        logging_group = QGroupBox("日志设置")
        logging_layout = QFormLayout(logging_group)

        # 记录预测
        self.log_predictions = QCheckBox()
        logging_layout.addRow("记录预测结果:", self.log_predictions)

        # 日志级别
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        logging_layout.addRow("日志级别:", self.log_level)

        # 详细错误
        self.detailed_errors = QCheckBox()
        logging_layout.addRow("详细错误信息:", self.detailed_errors)

        layout.addWidget(logging_group)
        layout.addStretch()

        widget.setWidget(content)
        widget.setWidgetResizable(True)
        return widget

    def create_history_widget(self) -> QWidget:
        """创建历史记录区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 历史记录标题
        history_label = QLabel("配置变更历史")
        history_font = QFont()
        history_font.setBold(True)
        history_label.setFont(history_font)
        layout.addWidget(history_label)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["配置项", "修改者", "修改时间", "操作"])
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 历史记录表格列宽自适应
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.history_table, 1)

        # 刷新按钮
        refresh_btn = QPushButton("刷新历史")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.load_history)
        layout.addWidget(refresh_btn)

        return widget

    def create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()
        layout.setSpacing(10)

        # 应用按钮
        apply_btn = QPushButton("应用配置")
        apply_btn.clicked.connect(self.apply_config)
        layout.addWidget(apply_btn)

        # 重置按钮
        reset_btn = QPushButton("重置默认")
        reset_btn.clicked.connect(self.reset_to_defaults)
        layout.addWidget(reset_btn)

        # 导出按钮
        export_btn = QPushButton("导出配置")
        export_btn.clicked.connect(self.export_config)
        layout.addWidget(export_btn)

        # 导入按钮
        import_btn = QPushButton("导入配置")
        import_btn.clicked.connect(self.import_config)
        layout.addWidget(import_btn)

        layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return layout

    def load_current_configs(self):
        """加载当前配置"""
        try:
            if self.config_manager:
                self.current_configs = self.config_manager.get_all_configs()
            
            if not self.current_configs:
                logger.info("未找到配置，使用默认配置")
                self.current_configs = self._get_default_configs()
            
            self.populate_ui_from_configs()
            self.load_history()

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.current_configs = self._get_default_configs()
            self.populate_ui_from_configs()
            self.status_label.setText(f" 使用默认配置: {e}")

    def _get_default_configs(self) -> dict:
        """获取默认配置"""
        return {
            'model_config': {
                'enabled': True,
                'model_type': 'ensemble',
                'confidence_threshold': 0.7,
                'prediction_horizon': 5,
                'feature_window': 20,
                'cache_size': 1000,
                'model_update_interval': 24
            },
            'validation': {
                'min_data_points': 10,
                'max_prediction_horizon': 30,
                'max_data_rows': 10000,
                'required_columns': ['open', 'high', 'low', 'close']
            },
            'feature_config': {
                'technical_indicators': True,
                'pattern_features': True,
                'volume_features': True,
                'price_features': True,
                'volatility_features': True
            },
            'cache_config': {
                'enable_cache': True,
                'cache_ttl': 300,
                'max_cache_size': 1000
            },
            'logging': {
                'log_predictions': True,
                'log_level': 'INFO',
                'detailed_errors': True
            }
        }

    def populate_ui_from_configs(self):
        """从配置填充UI"""
        try:
            # 模型配置
            model_config = self.current_configs.get('model_config', {})
            self.model_enabled.setChecked(model_config.get('enabled', True))

            model_type = model_config.get('model_type', 'ensemble')
            index = self.model_type.findData(model_type)  # Use findData to match the value
            if index >= 0:
                self.model_type.setCurrentIndex(index)

            self.confidence_threshold.setValue(model_config.get('confidence_threshold', 0.7))
            self.prediction_horizon.setValue(model_config.get('prediction_horizon', 5))
            self.feature_window.setValue(model_config.get('feature_window', 20))
            self.cache_size.setValue(model_config.get('cache_size', 1000))
            self.model_update_interval.setValue(model_config.get('model_update_interval', 24))

            # 验证配置
            validation_config = self.current_configs.get('validation', {})
            self.min_data_points.setValue(validation_config.get('min_data_points', 10))
            self.max_prediction_horizon.setValue(validation_config.get('max_prediction_horizon', 30))
            self.max_data_rows.setValue(validation_config.get('max_data_rows', 10000))

            required_cols = validation_config.get('required_columns', ['open', 'high', 'low', 'close'])
            self.required_columns.setText(','.join(required_cols))

            # 特征配置
            feature_config = self.current_configs.get('feature_config', {})
            self.technical_indicators.setChecked(feature_config.get('technical_indicators', True))
            self.pattern_features.setChecked(feature_config.get('pattern_features', True))
            self.volume_features.setChecked(feature_config.get('volume_features', True))
            self.price_features.setChecked(feature_config.get('price_features', True))
            self.volatility_features.setChecked(feature_config.get('volatility_features', True))

            # 缓存配置
            cache_config = self.current_configs.get('cache_config', {})
            self.enable_cache.setChecked(cache_config.get('enable_cache', True))
            self.cache_ttl.setValue(cache_config.get('cache_ttl', 300))
            self.max_cache_size.setValue(cache_config.get('max_cache_size', 1000))

            # 日志配置
            logging_config = self.current_configs.get('logging', {})
            self.log_predictions.setChecked(logging_config.get('log_predictions', True))

            log_level = logging_config.get('log_level', 'INFO')
            index = self.log_level.findText(log_level)
            if index >= 0:
                self.log_level.setCurrentIndex(index)

            self.detailed_errors.setChecked(logging_config.get('detailed_errors', True))

            self.status_label.setText("配置已加载")

        except Exception as e:
            logger.error(f"填充UI失败: {e}")
            self.status_label.setText(f" 填充UI失败: {e}")

    def collect_configs_from_ui(self) -> Dict[str, Any]:
        """从UI收集配置"""
        configs = {}

        # 模型配置
        configs['model_config'] = {
            'enabled': self.model_enabled.isChecked(),
            'model_type': self.model_type.currentData(),  # Get the value from currentData
            'confidence_threshold': self.confidence_threshold.value(),
            'prediction_horizon': self.prediction_horizon.value(),
            'feature_window': self.feature_window.value(),
            'cache_size': self.cache_size.value(),
            'model_update_interval': self.model_update_interval.value()
        }

        # 验证配置
        required_cols = [col.strip() for col in self.required_columns.text().split(',') if col.strip()]
        configs['validation'] = {
            'min_data_points': self.min_data_points.value(),
            'max_prediction_horizon': self.max_prediction_horizon.value(),
            'max_data_rows': self.max_data_rows.value(),
            'required_columns': required_cols
        }

        # 特征配置
        configs['feature_config'] = {
            'technical_indicators': self.technical_indicators.isChecked(),
            'pattern_features': self.pattern_features.isChecked(),
            'volume_features': self.volume_features.isChecked(),
            'price_features': self.price_features.isChecked(),
            'volatility_features': self.volatility_features.isChecked()
        }

        # 缓存配置
        configs['cache_config'] = {
            'enable_cache': self.enable_cache.isChecked(),
            'cache_ttl': self.cache_ttl.value(),
            'max_cache_size': self.max_cache_size.value()
        }

        # 日志配置
        configs['logging'] = {
            'log_predictions': self.log_predictions.isChecked(),
            'log_level': self.log_level.currentText(),
            'detailed_errors': self.detailed_errors.isChecked()
        }

        return configs

    def apply_config(self):
        """应用配置"""
        if not self.config_manager:
            QMessageBox.warning(self, "错误", "配置管理器不可用")
            return

        try:
            configs = self.collect_configs_from_ui()

            # 保存每个配置段
            for key, value in configs.items():
                self.config_manager.update_config(key, value, "UI用户")
                self.config_changed.emit(key, value)

            self.status_label.setText("配置已保存并应用")
            self.load_history()  # 刷新历史记录

            QMessageBox.information(self, "成功", "配置已成功保存并应用！")

        except Exception as e:
            logger.error(f"应用配置失败: {e}")
            self.status_label.setText(f" 应用配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")

    def reset_to_defaults(self):
        """重置为默认配置"""
        if not self.config_manager:
            return

        reply = QMessageBox.question(
            self, "确认重置",
            "这将重置所有AI预测配置为默认值，当前配置将被备份。\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.config_manager.reset_to_defaults("UI重置")
                self.load_current_configs()
                self.status_label.setText("已重置为默认配置")
                QMessageBox.information(self, "成功", "配置已重置为默认值，原配置已备份！")

            except Exception as e:
                logger.error(f"重置配置失败: {e}")
                self.status_label.setText(f" 重置失败: {e}")
                QMessageBox.critical(self, "错误", f"重置配置失败: {e}")

    def export_config(self):
        """导出配置"""
        if not self.config_manager:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出AI预测配置",
            f"ai_config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json)"
        )

        if file_path:
            try:
                self.config_manager.export_config(file_path)
                self.status_label.setText(f" 配置已导出到: {file_path}")
                QMessageBox.information(self, "成功", f"配置已成功导出到:\n{file_path}")

            except Exception as e:
                logger.error(f"导出配置失败: {e}")
                self.status_label.setText(f" 导出失败: {e}")
                QMessageBox.critical(self, "错误", f"导出配置失败: {e}")

    def import_config(self):
        """导入配置"""
        if not self.config_manager:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入AI预测配置", "",
            "JSON文件 (*.json)"
        )

        if file_path:
            reply = QMessageBox.question(
                self, "确认导入",
                f"这将导入配置文件:\n{file_path}\n\n当前配置将被覆盖，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    self.config_manager.import_config(file_path, "UI导入")
                    self.load_current_configs()
                    self.status_label.setText(f" 配置已从 {file_path} 导入")
                    QMessageBox.information(self, "成功", "配置导入成功！")

                except Exception as e:
                    logger.error(f"导入配置失败: {e}")
                    self.status_label.setText(f" 导入失败: {e}")
                    QMessageBox.critical(self, "错误", f"导入配置失败: {e}")

    def load_history(self):
        """加载配置历史"""
        try:
            if not self.config_manager:
                self.history_table.setRowCount(1)
                self.history_table.setItem(0, 0, QTableWidgetItem("无配置管理器"))
                self.history_table.setItem(0, 1, QTableWidgetItem("-"))
                self.history_table.setItem(0, 2, QTableWidgetItem("-"))
                return

            history = self.config_manager.get_config_history(limit=20)

            if not history:
                self.history_table.setRowCount(1)
                self.history_table.setItem(0, 0, QTableWidgetItem("暂无历史记录"))
                self.history_table.setItem(0, 1, QTableWidgetItem("-"))
                self.history_table.setItem(0, 2, QTableWidgetItem("-"))
                return

            self.history_table.setRowCount(len(history))
            for row, (config_key, old_value, new_value, changed_by, changed_at) in enumerate(history):
                self.history_table.setItem(row, 0, QTableWidgetItem(config_key))
                self.history_table.setItem(row, 1, QTableWidgetItem(changed_by))

                # 格式化时间
                try:
                    dt = datetime.fromisoformat(changed_at)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    time_str = changed_at
                self.history_table.setItem(row, 2, QTableWidgetItem(time_str))

                # 查看详情按钮
                view_btn = QPushButton("查看")
                view_btn.clicked.connect(lambda checked, data=(old_value, new_value):
                                         self.show_change_details(data[0], data[1]))
                self.history_table.setCellWidget(row, 3, view_btn)

            # 调整列宽
            self.history_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"加载历史失败: {e}")
            self.status_label.setText(f" 加载历史失败: {e}")

    def show_change_details(self, old_value: str, new_value: str):
        """显示配置变更详情"""
        dialog = QDialog(self)
        dialog.setWindowTitle("配置变更详情")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)

        # 旧配置
        layout.addWidget(QLabel("变更前:"))
        old_text = QTextEdit()
        old_text.setReadOnly(True)
        try:
            if old_value:
                formatted_old = json.dumps(json.loads(old_value), indent=2, ensure_ascii=False)
                old_text.setPlainText(formatted_old)
            else:
                old_text.setPlainText("(无)")
        except Exception:
            old_text.setPlainText(old_value or "(无)")
        layout.addWidget(old_text)

        # 新配置
        layout.addWidget(QLabel("变更后:"))
        new_text = QTextEdit()
        new_text.setReadOnly(True)
        try:
            formatted_new = json.dumps(json.loads(new_value), indent=2, ensure_ascii=False)
            new_text.setPlainText(formatted_new)
        except Exception:
            new_text.setPlainText(new_value)
        layout.addWidget(new_text)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec_()

    def closeEvent(self, event):
        """关闭事件"""
        # 检查是否有未保存的更改
        try:
            current_ui_configs = self.collect_configs_from_ui()
            if current_ui_configs != self.current_configs:
                reply = QMessageBox.question(
                    self, "未保存的更改",
                    "您有未保存的配置更改，是否保存？",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                    QMessageBox.Save
                )

                if reply == QMessageBox.Save:
                    self.apply_config()
                elif reply == QMessageBox.Cancel:
                    event.ignore()
                    return
        except Exception:
            pass  # 忽略比较错误

        super().closeEvent(event)
        event.accept()
