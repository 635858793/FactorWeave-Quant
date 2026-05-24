#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
启动向导对话框
为新用户提供系统功能介绍和快速入门指导
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QTextEdit, QCheckBox, QScrollArea,
    QFrame, QGridLayout, QGroupBox, QProgressBar, QListWidget,
    QListWidgetItem, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QIcon
from loguru import logger
from pathlib import Path

from .base_dialog import BaseDialog

logger = logger


class StartupGuidesDialog(BaseDialog):
    """启动向导对话框"""

    # 信号
    guide_completed = pyqtSignal(str)  # 向导完成信号

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="FactorWeave-Quant 启动向导",
            size=(800, 600),
            settings_key="StartupGuidesDialog"
        )

        # 初始化UI
        self._init_ui()
        self._load_content()

    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)

        # 标题区域
        self._create_header(layout)

        # 主要内容区域
        self._create_main_content(layout)

        # 底部按钮区域
        self._create_footer(layout)

    def _create_header(self, parent_layout):
        """创建标题区域"""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4a90e2, stop:1 #357abd);
                border-radius: 8px;
                margin: 5px;
            }
        """)
        header_frame.setFixedHeight(80)

        header_layout = QHBoxLayout(header_frame)

        # 标题文本
        title_label = QLabel("欢迎使用 FactorWeave-Quant 2.0")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white; margin: 10px;")

        subtitle_label = QLabel("专业的量化交易分析平台")
        subtitle_label.setStyleSheet("color: #e8f4fd; margin-left: 10px; font-size: 12px;")

        title_container = QVBoxLayout()
        title_container.addWidget(title_label)
        title_container.addWidget(subtitle_label)

        header_layout.addLayout(title_container)
        header_layout.addStretch()

        parent_layout.addWidget(header_frame)

    def _create_main_content(self, parent_layout):
        """创建主要内容区域"""
        # 创建标签页
        self.tab_widget = QTabWidget()

        # 欢迎页
        self._create_welcome_tab()

        # 功能介绍页
        self._create_features_tab()

        # 快速开始页
        self._create_quickstart_tab()

        # 设置页
        self._create_settings_tab()

        parent_layout.addWidget(self.tab_widget)

    def _create_welcome_tab(self):
        """创建欢迎页"""
        welcome_widget = QWidget()
        layout = QVBoxLayout(welcome_widget)

        # 欢迎文本
        welcome_text = QTextEdit()
        welcome_text.setReadOnly(True)
        welcome_text.setHtml("""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; padding: 20px;">
            <h2 style="color: #2c3e50;"> 欢迎使用 FactorWeave-Quant</h2>
            
            <p><strong>FactorWeave-Quant</strong> 是一个专业的量化交易分析平台，为您提供：</p>
            
            <ul>
                <li> <strong>实时数据分析</strong> - 支持多种数据源的实时股票、期货、数字货币数据</li>
                <li> <strong>技术指标计算</strong> - 内置100+种技术指标，支持自定义指标开发</li>
                <li> <strong>策略回测</strong> - 强大的回测引擎，支持多种策略类型</li>
                <li> <strong>插件生态</strong> - 丰富的插件市场，支持功能扩展</li>
                <li> <strong>AI辅助分析</strong> - 集成机器学习模型，提供智能分析建议</li>
                <li> <strong>情绪分析</strong> - 多源情绪数据分析，把握市场情绪脉搏</li>
            </ul>
            
            <h3 style="color: #34495e;"> 开始您的量化之旅</h3>
            <p>请按照向导的步骤，我们将帮助您快速上手这个强大的平台。</p>
            
            <div style="background: #ecf0f1; padding: 15px; border-radius: 5px; margin-top: 20px;">
                <p><strong> 提示：</strong> 如果您是第一次使用，建议完整浏览所有向导页面。</p>
            </div>
        </div>
        """)

        layout.addWidget(welcome_text)

        self.tab_widget.addTab(welcome_widget, "欢迎")

    def _create_features_tab(self):
        """创建功能介绍页"""
        features_widget = QWidget()
        layout = QVBoxLayout(features_widget)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 功能分组
        self._add_feature_group(scroll_layout, "数据分析", [
            ("实时行情", "获取实时股票、期货、数字货币行情数据"),
            ("历史数据", "访问丰富的历史数据，支持多种时间周期"),
            ("数据质量", "内置数据质量检查和清洗功能"),
            ("多源整合", "支持多个数据源的整合和对比")
        ])

        self._add_feature_group(scroll_layout, "技术分析", [
            ("技术指标", "100+种内置技术指标，支持自定义开发"),
            ("图表分析", "专业的K线图表，支持多种图表类型"),
            ("形态识别", "自动识别经典技术形态"),
            ("趋势分析", "智能趋势识别和预测")
        ])

        self._add_feature_group(scroll_layout, "策略系统", [
            ("策略开发", "可视化策略开发环境"),
            ("回测引擎", "高性能的策略回测系统"),
            ("风险管理", "完善的风险控制机制"),
            ("实盘交易", "支持多种券商接口的实盘交易")
        ])

        self._add_feature_group(scroll_layout, "AI功能", [
            ("情绪分析", "多源市场情绪数据分析"),
            ("智能预测", "基于机器学习的价格预测"),
            ("模式识别", "AI驱动的市场模式识别"),
            ("智能建议", "个性化的交易建议系统")
        ])

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        self.tab_widget.addTab(features_widget, "功能")

    def _add_feature_group(self, layout, title, features):
        """添加功能分组"""
        group_box = QGroupBox(title)
        group_layout = QVBoxLayout(group_box)

        for name, description in features:
            feature_frame = QFrame()
            feature_layout = QHBoxLayout(feature_frame)

            name_label = QLabel(f" {name}")
            name_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
            name_label.setFixedWidth(100)

            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #7f8c8d;")
            desc_label.setWordWrap(True)

            feature_layout.addWidget(name_label)
            feature_layout.addWidget(desc_label)
            feature_layout.addStretch()

            group_layout.addWidget(feature_frame)

        layout.addWidget(group_box)

    def _create_quickstart_tab(self):
        """创建快速开始页"""
        quickstart_widget = QWidget()
        layout = QVBoxLayout(quickstart_widget)

        # 快速开始步骤
        steps_text = QTextEdit()
        steps_text.setReadOnly(True)
        steps_text.setHtml("""
        <div style="font-family: Arial, sans-serif; line-height: 1.8; padding: 20px;">
            <h2 style="color: #2c3e50;"> 快速开始指南</h2>
            
            <h3 style="color: #34495e;">第一步：数据源配置</h3>
            <ol>
                <li>点击菜单栏 "工具" → "插件管理"</li>
                <li>在插件管理器中启用所需的数据源插件</li>
                <li>配置数据源的API密钥（如需要）</li>
            </ol>
            
            <h3 style="color: #34495e;">第二步：查看股票数据</h3>
            <ol>
                <li>在左侧面板的股票列表中选择一只股票</li>
                <li>中间面板将显示该股票的K线图</li>
                <li>右侧面板显示技术指标和分析结果</li>
            </ol>
            
            <h3 style="color: #34495e;">第三步：技术分析</h3>
            <ol>
                <li>在右侧面板选择技术指标</li>
                <li>调整指标参数以适应您的分析需求</li>
                <li>观察指标信号和图表形态</li>
            </ol>
            
            <h3 style="color: #34495e;">第四步：策略开发</h3>
            <ol>
                <li>点击菜单栏 "策略" → "策略管理器"</li>
                <li>创建新策略或导入现有策略</li>
                <li>运行回测验证策略效果</li>
            </ol>
            
            <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin-top: 20px;">
                <h4 style="color: #27ae60; margin-top: 0;"> 新手建议</h4>
                <ul>
                    <li>先从简单的技术指标开始学习</li>
                    <li>充分利用回测功能验证策略</li>
                    <li>关注风险管理，设置合理的止损</li>
                    <li>多关注市场情绪和基本面分析</li>
                </ul>
            </div>
        </div>
        """)

        layout.addWidget(steps_text)

        self.tab_widget.addTab(quickstart_widget, "快速开始")

    def _create_settings_tab(self):
        """创建设置页"""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)

        # 设置选项
        settings_group = QGroupBox("启动设置")
        settings_layout = QVBoxLayout(settings_group)

        # 启动时显示向导
        self.show_on_startup_cb = QCheckBox("启动时显示此向导")
        self.show_on_startup_cb.setChecked(True)
        settings_layout.addWidget(self.show_on_startup_cb)

        # 自动检查更新
        self.auto_update_cb = QCheckBox("自动检查软件更新")
        self.auto_update_cb.setChecked(True)
        settings_layout.addWidget(self.auto_update_cb)

        # 启用数据缓存
        self.enable_cache_cb = QCheckBox("启用数据缓存（提高性能）")
        self.enable_cache_cb.setChecked(True)
        settings_layout.addWidget(self.enable_cache_cb)

        # 启用情绪分析
        self.enable_sentiment_cb = QCheckBox("启用情绪分析功能")
        self.enable_sentiment_cb.setChecked(True)
        settings_layout.addWidget(self.enable_sentiment_cb)

        layout.addWidget(settings_group)

        # 资源链接
        resources_group = QGroupBox("学习资源")
        resources_layout = QVBoxLayout(resources_group)

        resources_text = QTextEdit()
        resources_text.setReadOnly(True)
        resources_text.setMaximumHeight(200)
        resources_text.setHtml("""
        <div style="font-family: Arial, sans-serif; padding: 10px;">
            <p><strong> 学习资源：</strong></p>
            <ul>
                <li><a href="#">用户手册</a> - 详细的功能说明</li>
                <li><a href="#">视频教程</a> - 入门和进阶教程</li>
                <li><a href="#">API文档</a> - 开发者文档</li>
                <li><a href="#">社区论坛</a> - 用户交流和支持</li>
            </ul>
            
            <p><strong>🆘 获取帮助：</strong></p>
            <ul>
                <li>菜单栏 "帮助" → "用户手册"</li>
                <li>菜单栏 "帮助" → "快捷键"</li>
                <li>遇到问题可通过 "帮助" → "反馈问题" 联系我们</li>
            </ul>
        </div>
        """)

        resources_layout.addWidget(resources_text)
        layout.addWidget(resources_group)

        layout.addStretch()

        self.tab_widget.addTab(settings_widget, "设置")

    def _create_footer(self, parent_layout):
        """创建底部按钮区域"""
        footer_layout = QHBoxLayout()

        # 进度指示器
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(4)  # 4个标签页
        self.progress_bar.setValue(1)
        self.progress_bar.setFixedHeight(8)
        footer_layout.addWidget(self.progress_bar)

        footer_layout.addStretch()

        # 按钮
        self.prev_btn = QPushButton("上一步")
        self.prev_btn.clicked.connect(self._prev_tab)
        self.prev_btn.setEnabled(False)

        self.next_btn = QPushButton("下一步")
        self.next_btn.clicked.connect(self._next_tab)

        self.finish_btn = QPushButton("完成")
        self.finish_btn.clicked.connect(self._finish_guide)
        self.finish_btn.setVisible(False)

        self.skip_btn = QPushButton("跳过")
        self.skip_btn.clicked.connect(self.reject)

        footer_layout.addWidget(self.prev_btn)
        footer_layout.addWidget(self.next_btn)
        footer_layout.addWidget(self.finish_btn)
        footer_layout.addWidget(self.skip_btn)

        parent_layout.addLayout(footer_layout)

        # 连接标签页变化信号
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _load_content(self):
        """加载内容"""
        # 这里可以加载动态内容，如最新的功能介绍等
        pass

    def _prev_tab(self):
        """上一个标签页"""
        current = self.tab_widget.currentIndex()
        if current > 0:
            self.tab_widget.setCurrentIndex(current - 1)

    def _next_tab(self):
        """下一个标签页"""
        current = self.tab_widget.currentIndex()
        if current < self.tab_widget.count() - 1:
            self.tab_widget.setCurrentIndex(current + 1)

    def _on_tab_changed(self, index):
        """标签页变化处理"""
        # 更新进度条
        self.progress_bar.setValue(index + 1)

        # 更新按钮状态
        self.prev_btn.setEnabled(index > 0)

        is_last_tab = (index == self.tab_widget.count() - 1)
        self.next_btn.setVisible(not is_last_tab)
        self.finish_btn.setVisible(is_last_tab)

    def _finish_guide(self):
        """完成向导"""
        # 保存设置
        self._save_settings()

        # 发射完成信号
        self.guide_completed.emit("startup_guide")

        # 关闭对话框
        self.accept()

    def _save_settings(self):
        """保存设置"""
        try:
            # 这里可以保存用户的设置选择
            # 例如保存到配置文件或数据库
            logger.info("启动向导设置已保存")
        except Exception as e:
            logger.error(f"保存启动向导设置失败: {e}")

    def closeEvent(self, event):
        """关闭事件处理"""
        # 可以在这里添加关闭确认逻辑
        super().closeEvent(event)
        event.accept()
