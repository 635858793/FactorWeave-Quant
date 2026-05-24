"""
增强插件市场对话框

提供插件浏览、搜索、下载、安装、管理等完整功能。
"""

import os
from typing import List, Optional, Dict, Any
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QTextEdit, QProgressBar, QListWidget, QListWidgetItem,
    QSplitter, QGroupBox, QFormLayout, QSpinBox, QCheckBox,
    QMessageBox, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor

from .base_dialog import BaseDialog

from plugins.plugin_market import PluginMarket, PluginInfo as MarketPluginInfo
from core.plugin_types import PluginType, PluginCategory
from plugins.development.plugin_sdk import PluginSDK
from core.plugin_manager import PluginManager, PluginInfo

class PluginSearchThread(QThread):
    """插件搜索线程"""

    search_completed = pyqtSignal(list, int)  # 搜索完成
    search_failed = pyqtSignal(str)  # 搜索失败

    def __init__(self, plugin_market: PluginMarket, search_params: Dict[str, Any]):
        """
        初始化搜索线程

        Args:
            plugin_market: 插件市场
            search_params: 搜索参数
        """
        super().__init__()
        self.plugin_market = plugin_market
        self.search_params = search_params

    def run(self):
        """执行搜索"""
        try:
            plugins, total = self.plugin_market.search_plugins(
                **self.search_params)
            self.search_completed.emit(plugins, total)
        except Exception as e:
            self.search_failed.emit(str(e))

class PluginCard(QFrame):
    """插件卡片组件"""

    install_requested = pyqtSignal(str)  # 安装请求
    details_requested = pyqtSignal(str)  # 详情请求

    def __init__(self, plugin_info: MarketPluginInfo, is_installed: bool = False):
        """
        初始化插件卡片

        Args:
            plugin_info: 插件信息
            is_installed: 是否已安装
        """
        super().__init__()
        self.plugin_info = plugin_info
        self.is_installed = is_installed

        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
                margin: 4px;
            }
            QFrame:hover {
                border-color: #0078d4;
                background-color: #f8f9fa;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 标题行
        title_layout = QHBoxLayout()

        # 插件名称
        name_label = QLabel(self.plugin_info.metadata.name)
        name_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_layout.addWidget(name_label)

        title_layout.addStretch()

        # 版本标签
        version_label = QLabel(f"v{self.plugin_info.metadata.version}")
        version_label.setStyleSheet("color: #666; font-size: 10px;")
        title_layout.addWidget(version_label)

        layout.addLayout(title_layout)

        # 描述
        desc_label = QLabel(self.plugin_info.metadata.description)
        desc_label.setWordWrap(True)
        desc_label.setMaximumHeight(40)
        desc_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(desc_label)

        # 信息行
        info_layout = QHBoxLayout()

        # 作者
        author_label = QLabel(f"作者: {self.plugin_info.metadata.author}")
        author_label.setStyleSheet("color: #666; font-size: 10px;")
        info_layout.addWidget(author_label)

        info_layout.addStretch()

        # 评分
        rating_label = QLabel(
            f" {self.plugin_info.rating:.1f} ({self.plugin_info.rating_count})")
        rating_label.setStyleSheet("color: #ff9500; font-size: 10px;")
        info_layout.addWidget(rating_label)

        layout.addLayout(info_layout)

        # 按钮行
        button_layout = QHBoxLayout()

        # 详情按钮
        details_btn = QPushButton("详情")
        details_btn.setMaximumWidth(60)
        details_btn.clicked.connect(
            lambda: self.details_requested.emit(self.plugin_info.metadata.name))
        button_layout.addWidget(details_btn)

        button_layout.addStretch()

        # 安装/已安装按钮
        if self.is_installed:
            install_btn = QPushButton("已安装")
            install_btn.setEnabled(False)
            install_btn.setStyleSheet(
                "background-color: #28a745; color: white;")
        else:
            install_btn = QPushButton("安装")
            install_btn.clicked.connect(
                lambda: self.install_requested.emit(self.plugin_info.metadata.name))
            install_btn.setStyleSheet(
                "background-color: #0078d4; color: white;")

        install_btn.setMaximumWidth(80)
        button_layout.addWidget(install_btn)

        layout.addLayout(button_layout)

class EnhancedPluginMarketDialog(BaseDialog):
    """增强插件市场对话框"""

    def __init__(self, plugin_manager: PluginManager, parent=None):
        """
        初始化对话框

        Args:
            plugin_manager: 插件管理器
            parent: 父窗口
        """
        self.plugin_manager = plugin_manager

        # 初始化插件市场和SDK
        plugins_dir = "plugins"
        cache_dir = os.path.join(plugins_dir, ".cache")
        self.plugin_market = PluginMarket(plugins_dir, cache_dir)

        sdk_workspace = os.path.join(plugins_dir, ".sdk")
        self.plugin_sdk = PluginSDK(sdk_workspace)

        self.search_thread = None
        self.current_plugins = []

        super().__init__(
            parent,
            title="FactorWeave-Quant  插件市场",
            min_size=(1000, 700),
            settings_key="EnhancedPluginMarketDialog"
        )

        self.setup_ui()
        self.load_initial_data()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 创建标签页
        self.tab_widget = QTabWidget()

        # 市场标签页
        self.market_tab = self.create_market_tab()
        self.tab_widget.addTab(self.market_tab, "插件市场")

        # 已安装标签页
        self.installed_tab = self.create_installed_tab()
        self.tab_widget.addTab(self.installed_tab, "已安装")

        # 开发工具标签页
        self.development_tab = self.create_development_tab()
        self.tab_widget.addTab(self.development_tab, "开发工具")

        layout.addWidget(self.tab_widget)

        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

    def create_market_tab(self) -> QWidget:
        """创建市场标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索区域
        search_group = QGroupBox("搜索插件")
        search_layout = QFormLayout(search_group)

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入插件名称或关键词...")
        self.search_edit.returnPressed.connect(self.search_plugins)
        search_layout.addRow("关键词:", self.search_edit)

        # 筛选条件
        filter_layout = QHBoxLayout()

        # 插件类型
        self.type_combo = QComboBox()
        self.type_combo.addItem("所有类型", None)
        for plugin_type in PluginType:
            self.type_combo.addItem(plugin_type.value.title(), plugin_type)
        filter_layout.addWidget(QLabel("类型:"))
        filter_layout.addWidget(self.type_combo)

        # 插件分类
        self.category_combo = QComboBox()
        self.category_combo.addItem("所有分类", None)
        for category in PluginCategory:
            self.category_combo.addItem(category.value.title(), category)
        filter_layout.addWidget(QLabel("分类:"))
        filter_layout.addWidget(self.category_combo)

        # 排序方式
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["热门程度", "评分", "更新时间", "名称"])
        filter_layout.addWidget(QLabel("排序:"))
        filter_layout.addWidget(self.sort_combo)

        # 搜索按钮
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self.search_plugins)
        filter_layout.addWidget(search_btn)

        filter_layout.addStretch()
        search_layout.addRow(filter_layout)

        layout.addWidget(search_group)

        # 插件列表区域
        self.plugin_scroll = QScrollArea()
        self.plugin_scroll.setWidgetResizable(True)
        self.plugin_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.plugin_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 插件容器
        self.plugin_container = QWidget()
        self.plugin_layout = QVBoxLayout(self.plugin_container)
        self.plugin_layout.setAlignment(Qt.AlignTop)

        self.plugin_scroll.setWidget(self.plugin_container)
        layout.addWidget(self.plugin_scroll)

        # 加载更多按钮
        self.load_more_btn = QPushButton("加载更多")
        self.load_more_btn.clicked.connect(self.load_more_plugins)
        self.load_more_btn.setVisible(False)
        layout.addWidget(self.load_more_btn)

        return widget

    def create_installed_tab(self) -> QWidget:
        """创建已安装标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_installed_plugins)
        toolbar_layout.addWidget(refresh_btn)

        toolbar_layout.addStretch()

        # 安装本地插件按钮
        install_local_btn = QPushButton("安装本地插件")
        install_local_btn.clicked.connect(self.install_local_plugin)
        toolbar_layout.addWidget(install_local_btn)

        layout.addLayout(toolbar_layout)

        # 已安装插件表格
        self.installed_table = QTableWidget()
        self.installed_table.setColumnCount(6)
        self.installed_table.setHorizontalHeaderLabels([
            "名称", "版本", "类型", "状态", "作者", "操作"
        ])

        header = self.installed_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        self.installed_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.installed_table.setAlternatingRowColors(True)

        layout.addWidget(self.installed_table)

        return widget

    def create_development_tab(self) -> QWidget:
        """创建开发工具标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 项目创建区域
        create_group = QGroupBox("创建新插件项目")
        create_layout = QFormLayout(create_group)

        # 项目信息
        self.project_name_edit = QLineEdit()
        create_layout.addRow("项目名称:", self.project_name_edit)

        self.project_type_combo = QComboBox()
        for plugin_type in PluginType:
            self.project_type_combo.addItem(
                plugin_type.value.title(), plugin_type)
        create_layout.addRow("插件类型:", self.project_type_combo)

        self.project_author_edit = QLineEdit()
        create_layout.addRow("作者:", self.project_author_edit)

        self.project_desc_edit = QLineEdit()
        create_layout.addRow("描述:", self.project_desc_edit)

        # 创建按钮
        create_btn = QPushButton("创建项目")
        create_btn.clicked.connect(self.create_plugin_project)
        create_layout.addRow(create_btn)

        layout.addWidget(create_group)

        # 项目管理区域
        manage_group = QGroupBox("管理项目")
        manage_layout = QVBoxLayout(manage_group)

        # 项目列表
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["项目名称", "版本", "类型", "最后修改"])
        self.project_tree.setAlternatingRowColors(True)
        manage_layout.addWidget(self.project_tree)

        # 项目操作按钮
        project_btn_layout = QHBoxLayout()

        refresh_projects_btn = QPushButton("刷新")
        refresh_projects_btn.clicked.connect(self.refresh_projects)
        project_btn_layout.addWidget(refresh_projects_btn)

        build_btn = QPushButton("构建")
        build_btn.clicked.connect(self.build_project)
        project_btn_layout.addWidget(build_btn)

        test_btn = QPushButton("测试")
        test_btn.clicked.connect(self.test_project)
        project_btn_layout.addWidget(test_btn)

        project_btn_layout.addStretch()

        manage_layout.addLayout(project_btn_layout)

        layout.addWidget(manage_group)

        return widget

    def load_initial_data(self):
        """加载初始数据"""
        # 加载精选插件
        self.status_label.setText("加载精选插件...")
        QTimer.singleShot(100, self.load_featured_plugins)

        # 刷新已安装插件
        self.refresh_installed_plugins()

        # 刷新开发项目
        self.refresh_projects()

    def load_featured_plugins(self):
        """加载精选插件"""
        try:
            featured_plugins = self.plugin_market.get_featured_plugins()
            self.display_plugins(featured_plugins)
            self.status_label.setText(f"已加载 {len(featured_plugins)} 个精选插件")
        except Exception as e:
            self.status_label.setText(f"加载精选插件失败: {e}")

    def search_plugins(self):
        """搜索插件"""
        if self.search_thread and self.search_thread.isRunning():
            return

        # 获取搜索参数
        search_params = {
            'query': self.search_edit.text(),
            'plugin_type': self.type_combo.currentData(),
            'category': self.category_combo.currentData(),
            'sort_by': ['popularity', 'rating', 'updated', 'name'][self.sort_combo.currentIndex()],
            'page': 1,
            'per_page': 20
        }

        # 启动搜索线程
        self.search_thread = PluginSearchThread(
            self.plugin_market, search_params)
        self.search_thread.search_completed.connect(self.on_search_completed)
        self.search_thread.search_failed.connect(self.on_search_failed)
        self.search_thread.start()

        self.status_label.setText("搜索中...")

    def on_search_completed(self, plugins: List[MarketPluginInfo], total: int):
        """搜索完成处理"""
        self.current_plugins = plugins
        self.display_plugins(plugins)

        # 显示加载更多按钮
        if len(plugins) < total:
            self.load_more_btn.setVisible(True)
        else:
            self.load_more_btn.setVisible(False)

        self.status_label.setText(f"找到 {total} 个插件，显示 {len(plugins)} 个")

    def on_search_failed(self, error: str):
        """搜索失败处理"""
        QMessageBox.warning(self, "搜索失败", f"搜索插件时发生错误:\n{error}")
        self.status_label.setText("搜索失败")

    def display_plugins(self, plugins: List[MarketPluginInfo]):
        """显示插件列表"""
        # 清空现有插件卡片
        for i in reversed(range(self.plugin_layout.count())):
            child = self.plugin_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        # 获取已安装插件列表
        installed_plugins = set(self.plugin_manager.get_all_plugins().keys())

        # 创建插件卡片
        for plugin in plugins:
            is_installed = plugin.metadata.name in installed_plugins
            card = PluginCard(plugin, is_installed)
            card.install_requested.connect(self.install_plugin)
            card.details_requested.connect(self.show_plugin_details)
            self.plugin_layout.addWidget(card)

    def load_more_plugins(self):
        """加载更多插件"""
        # 这里应该实现分页加载
        self.load_more_btn.setVisible(False)
        self.status_label.setText("暂不支持加载更多")

    def install_plugin(self, plugin_name: str):
        """安装插件"""
        try:
            # 这里应该实现实际的插件安装逻辑
            QMessageBox.information(
                self, "安装插件", f"插件 {plugin_name} 安装功能正在开发中")
            self.status_label.setText(f"插件 {plugin_name} 安装中...")
        except Exception as e:
            QMessageBox.warning(self, "安装失败", f"安装插件时发生错误:\n{e}")

    def show_plugin_details(self, plugin_name: str):
        """显示插件详情"""
        try:
            # 这里应该实现插件详情对话框
            QMessageBox.information(
                self, "插件详情", f"插件 {plugin_name} 的详情功能正在开发中")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"显示插件详情时发生错误:\n{e}")

    def refresh_installed_plugins(self):
        """刷新已安装插件"""
        try:
            # 导入插件显示工具
            from utils.plugin_utils import PluginDisplayUtils

            # 获取已安装插件
            plugins = self.plugin_manager.get_all_plugins()

            self.installed_table.setRowCount(len(plugins))

            for row, (name, instance) in enumerate(plugins.items()):
                # 获取插件元数据
                metadata = self.plugin_manager.get_plugin_metadata(name) or {}

                # 使用显示工具格式化插件信息
                formatted_info = PluginDisplayUtils.format_plugin_info(metadata)

                # 填充表格
                self.installed_table.setItem(row, 0, QTableWidgetItem(name))
                self.installed_table.setItem(
                    row, 1, QTableWidgetItem(formatted_info.get('version', '1.0.0')))

                # 使用中文显示的插件类型
                type_display = formatted_info.get('type_display', '未知类型')
                type_icon = formatted_info.get('type_icon', '')
                self.installed_table.setItem(
                    row, 2, QTableWidgetItem(f"{type_icon} {type_display}"))

                # 状态
                status = "已启用" if instance else "已禁用"
                status_item = QTableWidgetItem(status)
                if instance:
                    status_item.setForeground(QColor("#28a745"))  # 绿色
                else:
                    status_item.setForeground(QColor("#dc3545"))  # 红色
                self.installed_table.setItem(row, 3, status_item)

                self.installed_table.setItem(
                    row, 4, QTableWidgetItem(formatted_info.get('author', '未知')))

                # 操作按钮
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(4, 4, 4, 4)

                enable_btn = QPushButton("启用" if not instance else "禁用")
                enable_btn.setMaximumWidth(60)
                if instance:
                    enable_btn.setStyleSheet("background-color: #ffc107; color: #000;")
                else:
                    enable_btn.setStyleSheet("background-color: #28a745; color: #fff;")
                btn_layout.addWidget(enable_btn)

                remove_btn = QPushButton("卸载")
                remove_btn.setMaximumWidth(60)
                remove_btn.setStyleSheet("background-color: #dc3545; color: #fff;")
                btn_layout.addWidget(remove_btn)

                self.installed_table.setCellWidget(row, 5, btn_widget)

            self.status_label.setText(f"已安装 {len(plugins)} 个插件")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"刷新已安装插件时发生错误:\n{e}")
            import traceback
            print(f"刷新插件错误详情: {traceback.format_exc()}")

    def install_local_plugin(self):
        """安装本地插件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择插件文件", "", "插件文件 (*.zip);;所有文件 (*)"
        )

        if file_path:
            try:
                # 这里应该实现本地插件安装逻辑
                QMessageBox.information(self, "安装插件", "本地插件安装功能正在开发中")
            except Exception as e:
                QMessageBox.warning(self, "安装失败", f"安装本地插件时发生错误:\n{e}")

    def create_plugin_project(self):
        """创建插件项目"""
        try:
            name = self.project_name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "错误", "请输入项目名称")
                return

            plugin_type = self.project_type_combo.currentData()
            author = self.project_author_edit.text().strip() or "Unknown"
            description = self.project_desc_edit.text().strip() or f"{name}插件"

            # 创建项目
            project_path = self.plugin_sdk.create_plugin_project(
                name=name,
                plugin_type=plugin_type,
                author=author,
                description=description
            )

            QMessageBox.information(self, "创建成功", f"插件项目已创建:\n{project_path}")

            # 清空表单
            self.project_name_edit.clear()
            self.project_author_edit.clear()
            self.project_desc_edit.clear()

            # 刷新项目列表
            self.refresh_projects()

        except Exception as e:
            QMessageBox.warning(self, "创建失败", f"创建插件项目时发生错误:\n{e}")

    def refresh_projects(self):
        """刷新项目列表"""
        try:
            self.project_tree.clear()

            projects = self.plugin_sdk.list_projects()

            for project in projects:
                item = QTreeWidgetItem([
                    project['name'],
                    project['version'],
                    project['plugin_type'],
                    project['last_modified'][:19]  # 只显示日期时间部分
                ])
                item.setData(0, Qt.UserRole, project['path'])
                self.project_tree.addTopLevelItem(item)

            self.status_label.setText(f"找到 {len(projects)} 个开发项目")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"刷新项目列表时发生错误:\n{e}")

    def build_project(self):
        """构建项目"""
        current_item = self.project_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "错误", "请选择一个项目")
            return

        project_path = current_item.data(0, Qt.UserRole)

        try:
            # 构建项目
            output_file = self.plugin_sdk.build_plugin(project_path)
            QMessageBox.information(self, "构建成功", f"插件已构建:\n{output_file}")

        except Exception as e:
            QMessageBox.warning(self, "构建失败", f"构建项目时发生错误:\n{e}")

    def test_project(self):
        """测试项目"""
        current_item = self.project_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "错误", "请选择一个项目")
            return

        project_path = current_item.data(0, Qt.UserRole)

        try:
            # 测试项目
            result = self.plugin_sdk.test_plugin(project_path)

            if result['passed']:
                QMessageBox.information(self, "测试通过", "所有测试都通过了!")
            else:
                error_msg = "\n".join(result['errors'])
                QMessageBox.warning(self, "测试失败", f"测试失败:\n{error_msg}")

        except Exception as e:
            QMessageBox.warning(self, "测试失败", f"测试项目时发生错误:\n{e}")

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 创建模拟的插件管理器
    class MockPluginManager:
        def get_all_plugins(self):
            return {"示例插件": None}

        def get_plugin_metadata(self, name):
            return {
                'version': '1.0.0',
                'plugin_type': 'indicator',
                'author': '测试作者'
            }

    dialog = EnhancedPluginMarketDialog(MockPluginManager())
    dialog.show()

    sys.exit(app.exec_())
