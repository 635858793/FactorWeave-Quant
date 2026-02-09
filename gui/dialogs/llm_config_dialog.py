"""
LLM配置对话框

提供统一的LLM配置界面，支持多个大模型提供商
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QFormLayout, QComboBox, QLineEdit,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox,
    QCheckBox, QTextEdit, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from loguru import logger
from typing import Optional, Dict, Any

try:
    from core.services.llm_config_service import (
        LLMConfigService, LLMProvider, LLMConfig, LLMProviderInfo
    )
except ImportError:
    logger.warning("LLM配置服务导入失败")
    LLMConfigService = None
    LLMProvider = None
    LLMConfig = None
    LLMProviderInfo = None


class LLMConfigDialog(QDialog):
    """LLM配置对话框"""

    config_updated = pyqtSignal()

    def __init__(self, parent=None, llm_config_service=None):
        """
        初始化LLM配置对话框

        Args:
            parent: 父窗口
            llm_config_service: LLM配置服务
        """
        super().__init__(parent)
        self.llm_config_service = llm_config_service
        self.current_provider = None
        self.current_config = None

        self.setWindowTitle("LLM配置")
        self.setMinimumSize(900, 700)
        self.setModal(True)

        self.setup_ui()
        self.load_current_config()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("大语言模型配置")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 创建选项卡
        tab_widget = QTabWidget()

        # 配置选项卡
        config_tab = self.create_config_tab()
        tab_widget.addTab(config_tab, "配置")

        # 提供商信息选项卡
        info_tab = self.create_provider_info_tab()
        tab_widget.addTab(info_tab, "提供商信息")

        # 测试连接选项卡
        test_tab = self.create_test_tab()
        tab_widget.addTab(test_tab, "测试连接")

        layout.addWidget(tab_widget)

        # 按钮
        button_layout = QHBoxLayout()

        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self.test_connection)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)

        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self.apply_config)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)

        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.apply_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def create_config_tab(self):
        """创建配置选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 提供商选择
        provider_group = QGroupBox("提供商选择")
        provider_layout = QFormLayout(provider_group)

        self.provider_combo = QComboBox()
        if LLMConfigService:
            providers = self.llm_config_service.get_all_providers()
            for provider_info in providers:
                self.provider_combo.addItem(
                    f"{provider_info.name} - {provider_info.description}",
                    provider_info.provider
                )
        provider_layout.addRow("选择提供商:", self.provider_combo)
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)

        # 当前提供商显示
        self.current_provider_label = QLabel("未选择提供商")
        provider_layout.addRow("当前提供商:", self.current_provider_label)

        layout.addWidget(provider_group)

        # API配置
        api_group = QGroupBox("API配置")
        api_layout = QFormLayout(api_group)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("输入API密钥")
        api_layout.addRow("API密钥*:", self.api_key_edit)

        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        self.api_secret_edit.setPlaceholderText("输入API密钥（如果需要）")
        api_layout.addRow("API密钥:", self.api_secret_edit)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("输入自定义API地址（可选）")
        api_layout.addRow("API地址:", self.base_url_edit)

        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("输入代理地址（可选，如：http://127.0.0.1:7890）")
        api_layout.addRow("代理:", self.proxy_edit)

        layout.addWidget(api_group)

        # 模型配置
        model_group = QGroupBox("模型配置")
        model_layout = QFormLayout(model_group)

        self.model_combo = QComboBox()
        model_layout.addRow("模型:", self.model_combo)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        model_layout.addRow("温度:", self.temperature_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 32000)
        self.max_tokens_spin.setValue(2000)
        model_layout.addRow("最大Token数:", self.max_tokens_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        model_layout.addRow("超时时间:", self.timeout_spin)

        layout.addWidget(model_group)

        # 高级配置
        advanced_group = QGroupBox("高级配置")
        advanced_layout = QFormLayout(advanced_group)

        self.enabled_check = QCheckBox("启用此提供商")
        self.enabled_check.setChecked(True)
        advanced_layout.addRow("", self.enabled_check)

        self.extra_params_edit = QTextEdit()
        self.extra_params_edit.setPlaceholderText('{"key": "value"}')
        self.extra_params_edit.setMaximumHeight(100)
        advanced_layout.addRow("额外参数 (JSON):", self.extra_params_edit)

        layout.addWidget(advanced_group)

        return widget

    def create_provider_info_tab(self):
        """创建提供商信息选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 提供商列表
        self.provider_table = QTableWidget()
        self.provider_table.setColumnCount(5)
        self.provider_table.setHorizontalHeaderLabels([
            "提供商", "描述", "默认模型", "文档", "定价"
        ])
        self.provider_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.provider_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.provider_table.setSelectionMode(QTableWidget.SingleSelection)

        if LLMConfigService:
            providers = self.llm_config_service.get_all_providers()
            self.provider_table.setRowCount(len(providers))

            for row, provider_info in enumerate(providers):
                self.provider_table.setItem(row, 0, QTableWidgetItem(provider_info.name))
                self.provider_table.setItem(row, 1, QTableWidgetItem(provider_info.description))
                self.provider_table.setItem(row, 2, QTableWidgetItem(provider_info.default_model))
                self.provider_table.setItem(row, 3, QTableWidgetItem("查看" if provider_info.documentation_url else ""))
                self.provider_table.setItem(row, 4, QTableWidgetItem("查看" if provider_info.pricing_url else ""))

        self.provider_table.itemDoubleClicked.connect(self.on_provider_info_clicked)

        layout.addWidget(self.provider_table)

        return widget

    def create_test_tab(self):
        """创建测试连接选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 测试配置
        test_group = QGroupBox("连接测试")
        test_layout = QFormLayout(test_group)

        self.test_provider_combo = QComboBox()
        test_layout.addRow("选择提供商:", self.test_provider_combo)

        self.test_model_label = QLabel("未选择模型")
        test_layout.addRow("模型:", self.test_model_label)

        self.test_result_edit = QTextEdit()
        self.test_result_edit.setReadOnly(True)
        self.test_result_edit.setMaximumHeight(200)
        test_layout.addRow("测试结果:", self.test_result_edit)

        layout.addWidget(test_group)

        # 快速测试按钮
        quick_test_layout = QHBoxLayout()

        test_all_btn = QPushButton("测试所有已配置的提供商")
        test_all_btn.clicked.connect(self.test_all_providers)
        quick_test_layout.addWidget(test_all_btn)

        clear_results_btn = QPushButton("清除结果")
        clear_results_btn.clicked.connect(self.clear_test_results)
        quick_test_layout.addWidget(clear_results_btn)

        layout.addLayout(quick_test_layout)

        return widget

    def load_current_config(self):
        """加载当前配置"""
        if not self.llm_config_service:
            return

        # 加载当前提供商
        current_provider = self.llm_config_service.get_current_provider()
        if current_provider:
            self.provider_combo.setCurrentIndex(
                self.provider_combo.findData(current_provider)
            )
            self.on_provider_changed(self.provider_combo.currentIndex())

            # 加载配置
            config = self.llm_config_service.get_config(current_provider)
            if config:
                self.current_config = config
                self.api_key_edit.setText(config.api_key)
                self.api_secret_edit.setText(config.api_secret or "")
                self.base_url_edit.setText(config.base_url or "")
                self.proxy_edit.setText(config.proxy or "")
                self.temperature_spin.setValue(config.temperature)
                self.max_tokens_spin.setValue(config.max_tokens)
                self.timeout_spin.setValue(config.timeout)
                self.enabled_check.setChecked(config.enabled)

                # 加载额外参数
                if config.extra_params:
                    import json
                    self.extra_params_edit.setText(
                        json.dumps(config.extra_params, indent=2, ensure_ascii=False)
                    )

    def on_provider_changed(self, index):
        """提供商改变时更新UI"""
        if not LLMConfigService:
            return

        provider = self.provider_combo.itemData(index)
        if not provider:
            return

        self.current_provider = provider

        # 更新提供商信息
        provider_info = self.llm_config_service.get_provider_info(provider)
        if provider_info:
            self.current_provider_label.setText(provider_info.name)

            # 更新模型列表
            self.model_combo.clear()
            self.model_combo.addItems(provider_info.models)

            # 设置默认模型
            if provider_info.default_model:
                self.model_combo.setCurrentText(provider_info.default_model)

            # 更新API地址
            if provider_info.base_url:
                self.base_url_edit.setText(provider_info.base_url)

            # 更新API密钥提示
            if provider_info.requires_api_secret:
                self.api_secret_edit.setEnabled(True)
                self.api_secret_edit.setPlaceholderText("此提供商需要API密钥")
            else:
                self.api_secret_edit.setEnabled(False)
                self.api_secret_edit.clear()

    def save_config(self):
        """保存配置"""
        if not self.llm_config_service or not self.current_provider:
            QMessageBox.warning(self, "警告", "请先选择提供商")
            return

        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "警告", "API密钥不能为空")
            return

        try:
            config = LLMConfig(
                provider=self.current_provider,
                api_key=api_key,
                api_secret=self.api_secret_edit.text().strip() or None,
                base_url=self.base_url_edit.text().strip() or None,
                model=self.model_combo.currentText(),
                temperature=self.temperature_spin.value(),
                max_tokens=self.max_tokens_spin.value(),
                timeout=self.timeout_spin.value(),
                enabled=self.enabled_check.isChecked(),
                proxy=self.proxy_edit.text().strip() or None
            )

            # 解析额外参数
            extra_params_text = self.extra_params_edit.toPlainText().strip()
            if extra_params_text:
                import json
                config.extra_params = json.loads(extra_params_text)

            # 保存配置
            self.llm_config_service.set_config(config)

            # 设置为当前提供商
            self.llm_config_service.set_current_provider(self.current_provider)

            QMessageBox.information(self, "成功", "LLM配置保存成功")
            self.config_updated.emit()

        except Exception as e:
            logger.error(f"保存LLM配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def apply_config(self):
        """应用配置"""
        self.save_config()

    def test_connection(self):
        """测试连接"""
        if not self.llm_config_service or not self.current_provider:
            QMessageBox.warning(self, "警告", "请先选择提供商")
            return

        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "警告", "API密钥不能为空")
            return

        try:
            # 创建临时配置进行测试
            config = LLMConfig(
                provider=self.current_provider,
                api_key=api_key,
                api_secret=self.api_secret_edit.text().strip() or None,
                base_url=self.base_url_edit.text().strip() or None,
                model=self.model_combo.currentText(),
                temperature=self.temperature_spin.value(),
                max_tokens=self.max_tokens_spin.value(),
                timeout=self.timeout_spin.value(),
                enabled=self.enabled_check.isChecked(),
                proxy=self.proxy_edit.text().strip() or None
            )

            # 临时保存配置
            self.llm_config_service.set_config(config)

            # 测试连接
            result = self.llm_config_service.test_connection(self.current_provider)

            # 显示结果
            self.test_result_edit.clear()
            if result.get('success'):
                self.test_result_edit.appendPlainText(f"连接成功\n")
                self.test_result_edit.appendPlainText(f"模型: {result.get('model', 'N/A')}\n")
                self.test_result_edit.appendPlainText(f"响应: {result.get('response', 'N/A')[:100]}...")
                QMessageBox.information(self, "成功", "连接测试成功")
            else:
                self.test_result_edit.appendPlainText(f"❌ 连接失败\n")
                self.test_result_edit.appendPlainText(f"错误: {result.get('error', '未知错误')}\n")
                QMessageBox.warning(self, "失败", f"连接测试失败: {result.get('error', '未知错误')}")

        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            QMessageBox.critical(self, "错误", f"测试连接失败: {str(e)}")

    def test_all_providers(self):
        """测试所有已配置的提供商"""
        if not self.llm_config_service:
            return

        providers = self.llm_config_service.get_available_providers()
        if not providers:
            QMessageBox.information(self, "提示", "没有已配置的提供商")
            return

        self.test_result_edit.clear()
        self.test_result_edit.appendPlainText("开始测试所有已配置的提供商...\n\n")

        success_count = 0
        for provider in providers:
            result = self.llm_config_service.test_connection(provider)
            if result.get('success'):
                self.test_result_edit.appendPlainText(f"{provider.value}: 成功\n")
                success_count += 1
            else:
                self.test_result_edit.appendPlainText(f"❌ {provider.value}: 失败 - {result.get('error', '未知错误')}\n")

        self.test_result_edit.appendPlainText(f"\n测试完成: {success_count}/{len(providers)} 成功")

    def clear_test_results(self):
        """清除测试结果"""
        self.test_result_edit.clear()

    def on_provider_info_clicked(self, item):
        """提供商信息被点击"""
        row = item.row()
        if not LLMConfigService:
            return

        providers = self.llm_config_service.get_all_providers()
        if row < len(providers):
            provider_info = providers[row]

            if item.column() == 3 and provider_info.documentation_url:
                import webbrowser
                webbrowser.open(provider_info.documentation_url)
            elif item.column() == 4 and provider_info.pricing_url:
                import webbrowser
                webbrowser.open(provider_info.pricing_url)
