"""
指标市场对话框
用于在线指标市场浏览、安装、上传和评价
"""

from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QTabWidget,
                             QTableWidget, QTableWidgetItem, QPushButton,
                             QLabel, QLineEdit, QTextEdit, QGroupBox,
                             QFormLayout, QSpinBox, QCheckBox, QComboBox,
                             QProgressBar, QMessageBox, QHeaderView,
                             QSplitter, QFrame, QListWidget, QListWidgetItem,
                             QScrollArea, QWidget, QGridLayout,
                             QSlider, QFileDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QPixmap, QIcon, QPainter, QColor
import json
import os
import time

from .base_dialog import BaseDialog


class StarRatingWidget(QWidget):
    """自定义星级评分组件"""

    def __init__(self, rating=0, max_rating=5, editable=False, parent=None):
        super().__init__(parent)
        self.rating = rating
        self.max_rating = max_rating
        self.editable = editable
        self.setFixedHeight(20)

    def paintEvent(self, event):
        painter = QPainter(self)

        star_width = 16
        star_spacing = 2

        for i in range(self.max_rating):
            x = i * (star_width + star_spacing)

            if i < int(self.rating):
                # 填充星星
                painter.setPen(QColor("#ffa500"))
                painter.drawText(x, 15, "")
            else:
                # 空星星
                painter.setPen(QColor("#ddd"))
                painter.drawText(x, 15, "")

    def mousePressEvent(self, event):
        if self.editable:
            star_width = 16
            star_spacing = 2
            x = event.x()
            rating = min(self.max_rating, max(
                1, int(x / (star_width + star_spacing)) + 1))
            self.rating = rating
            self.update()


class IndicatorCard(QFrame):
    """指标卡片组件"""

    install_clicked = pyqtSignal(dict)
    details_clicked = pyqtSignal(dict)

    def __init__(self, indicator_data, parent=None):
        super().__init__(parent)
        self.indicator_data = indicator_data
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
                margin: 5px;
            }
            QFrame:hover {
                border-color: #007acc;
                background-color: #f8f9fa;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 指标名称
        name_label = QLabel(self.indicator_data.get('name', '未知指标'))
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)

        # 指标描述
        desc_label = QLabel(self.indicator_data.get('description', '无描述'))
        desc_label.setWordWrap(True)
        desc_label.setMaximumHeight(40)
        layout.addWidget(desc_label)

        # 指标信息
        info_layout = QHBoxLayout()

        # 作者
        author_label = QLabel(f"作者: {self.indicator_data.get('author', '未知')}")
        author_label.setStyleSheet("color: #666;")
        info_layout.addWidget(author_label)

        # 版本
        version_label = QLabel(f"v{self.indicator_data.get('version', '1.0')}")
        version_label.setStyleSheet("color: #666;")
        info_layout.addWidget(version_label)

        info_layout.addStretch()

        # 评分（模拟星级评分）
        rating = self.indicator_data.get('rating', 0)
        rating_widget = StarRatingWidget(rating)
        info_layout.addWidget(rating_widget)

        layout.addLayout(info_layout)

        # 统计信息
        stats_layout = QHBoxLayout()

        downloads = self.indicator_data.get('downloads', 0)
        downloads_label = QLabel(f"下载: {downloads}")
        downloads_label.setStyleSheet("color: #666; font-size: 10px;")
        stats_layout.addWidget(downloads_label)

        likes = self.indicator_data.get('likes', 0)
        likes_label = QLabel(f"点赞: {likes}")
        likes_label.setStyleSheet("color: #666; font-size: 10px;")
        stats_layout.addWidget(likes_label)

        stats_layout.addStretch()

        # 价格
        price = self.indicator_data.get('price', 0)
        if price > 0:
            price_label = QLabel(f"¥{price}")
            price_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        else:
            price_label = QLabel("免费")
            price_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        stats_layout.addWidget(price_label)

        layout.addLayout(stats_layout)

        # 按钮
        button_layout = QHBoxLayout()

        details_btn = QPushButton("详情")
        details_btn.clicked.connect(
            lambda: self.details_clicked.emit(self.indicator_data))
        button_layout.addWidget(details_btn)

        install_btn = QPushButton("安装")
        install_btn.clicked.connect(
            lambda: self.install_clicked.emit(self.indicator_data))
        install_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        button_layout.addWidget(install_btn)

        layout.addLayout(button_layout)


class IndicatorMarketDialog(BaseDialog):
    """指标市场对话框"""

    indicator_installed = pyqtSignal(dict)
    indicator_uploaded = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="指标市场",
            min_size=(1200, 800),
            size=(1200, 800),
            settings_key="IndicatorMarketDialog"
        )

        self.indicators = []
        self.categories = ["全部", "趋势指标", "震荡指标", "成交量指标", "动量指标", "自定义指标"]
        self.current_category = "全部"

        self.setup_ui()
        self.load_sample_data()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("指标市场")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 创建选项卡
        tab_widget = QTabWidget()

        # 浏览市场选项卡
        browse_tab = self.create_browse_tab()
        tab_widget.addTab(browse_tab, "浏览市场")

        # 我的指标选项卡
        my_indicators_tab = self.create_my_indicators_tab()
        tab_widget.addTab(my_indicators_tab, "我的指标")

        # 上传指标选项卡
        upload_tab = self.create_upload_tab()
        tab_widget.addTab(upload_tab, "上传指标")

        # 管理面板选项卡
        manage_tab = self.create_manage_tab()
        tab_widget.addTab(manage_tab, "管理面板")

        layout.addWidget(tab_widget)

        # 按钮
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("刷新市场")
        refresh_btn.clicked.connect(self.refresh_market)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)

        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def create_browse_tab(self):
        """创建浏览市场选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 搜索和筛选
        filter_layout = QHBoxLayout()

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索指标...")
        self.search_edit.textChanged.connect(self.filter_indicators)
        filter_layout.addWidget(QLabel("搜索:"))
        filter_layout.addWidget(self.search_edit)

        # 分类筛选
        self.category_combo = QComboBox()
        self.category_combo.addItems(self.categories)
        self.category_combo.currentTextChanged.connect(
            self.on_category_changed)
        filter_layout.addWidget(QLabel("分类:"))
        filter_layout.addWidget(self.category_combo)

        # 排序
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["最新", "最热", "评分最高", "下载最多"])
        self.sort_combo.currentTextChanged.connect(self.sort_indicators)
        filter_layout.addWidget(QLabel("排序:"))
        filter_layout.addWidget(self.sort_combo)

        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # 指标展示区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.indicators_widget = QWidget()
        self.indicators_layout = QGridLayout(self.indicators_widget)
        self.indicators_layout.setAlignment(Qt.AlignTop)

        scroll_area.setWidget(self.indicators_widget)
        layout.addWidget(scroll_area)

        return widget

    def create_my_indicators_tab(self):
        """创建我的指标选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 已安装指标
        installed_group = QGroupBox("已安装指标")
        installed_layout = QVBoxLayout(installed_group)

        self.installed_table = QTableWidget()
        self.installed_table.setColumnCount(6)
        self.installed_table.setHorizontalHeaderLabels([
            "指标名称", "版本", "作者", "安装日期", "状态", "操作"
        ])
        self.installed_table.horizontalHeader().setStretchLastSection(True)
        installed_layout.addWidget(self.installed_table)

        layout.addWidget(installed_group)

        # 收藏指标
        favorites_group = QGroupBox("收藏指标")
        favorites_layout = QVBoxLayout(favorites_group)

        self.favorites_table = QTableWidget()
        self.favorites_table.setColumnCount(5)
        self.favorites_table.setHorizontalHeaderLabels([
            "指标名称", "作者", "评分", "收藏日期", "操作"
        ])
        self.favorites_table.horizontalHeader().setStretchLastSection(True)
        favorites_layout.addWidget(self.favorites_table)

        layout.addWidget(favorites_group)

        return widget

    def create_upload_tab(self):
        """创建上传指标选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 指标信息
        info_group = QGroupBox("指标信息")
        info_layout = QFormLayout(info_group)

        self.upload_name_edit = QLineEdit()
        info_layout.addRow("指标名称:", self.upload_name_edit)

        self.upload_description_edit = QTextEdit()
        self.upload_description_edit.setMaximumHeight(80)
        info_layout.addRow("指标描述:", self.upload_description_edit)

        self.upload_category_combo = QComboBox()
        self.upload_category_combo.addItems(self.categories[1:])  # 排除"全部"
        info_layout.addRow("指标分类:", self.upload_category_combo)

        self.upload_version_edit = QLineEdit()
        self.upload_version_edit.setText("1.0.0")
        info_layout.addRow("版本号:", self.upload_version_edit)

        self.upload_tags_edit = QLineEdit()
        self.upload_tags_edit.setPlaceholderText("用逗号分隔多个标签")
        info_layout.addRow("标签:", self.upload_tags_edit)

        layout.addWidget(info_group)

        # 文件上传
        file_group = QGroupBox("文件上传")
        file_layout = QVBoxLayout(file_group)

        # 指标文件
        indicator_file_layout = QHBoxLayout()
        self.indicator_file_edit = QLineEdit()
        self.indicator_file_edit.setReadOnly(True)
        indicator_file_btn = QPushButton("选择文件")
        indicator_file_btn.clicked.connect(self.select_indicator_file)

        indicator_file_layout.addWidget(QLabel("指标文件:"))
        indicator_file_layout.addWidget(self.indicator_file_edit)
        indicator_file_layout.addWidget(indicator_file_btn)
        file_layout.addLayout(indicator_file_layout)

        # 文档文件
        doc_file_layout = QHBoxLayout()
        self.doc_file_edit = QLineEdit()
        self.doc_file_edit.setReadOnly(True)
        doc_file_btn = QPushButton("选择文件")
        doc_file_btn.clicked.connect(self.select_doc_file)

        doc_file_layout.addWidget(QLabel("文档文件:"))
        doc_file_layout.addWidget(self.doc_file_edit)
        doc_file_layout.addWidget(doc_file_btn)
        file_layout.addLayout(doc_file_layout)

        layout.addWidget(file_group)

        # 发布设置
        publish_group = QGroupBox("发布设置")
        publish_layout = QFormLayout(publish_group)

        self.price_spin = QSpinBox()
        self.price_spin.setRange(0, 9999)
        self.price_spin.setSuffix("元")
        publish_layout.addRow("价格:", self.price_spin)

        self.license_combo = QComboBox()
        self.license_combo.addItems(
            ["MIT", "GPL v3", "Apache 2.0", "BSD", "商业许可"])
        publish_layout.addRow("许可证:", self.license_combo)

        self.public_check = QCheckBox("公开发布")
        self.public_check.setChecked(True)
        publish_layout.addRow(self.public_check)

        layout.addWidget(publish_group)

        # 上传按钮
        upload_btn = QPushButton("上传指标")
        upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        upload_btn.clicked.connect(self.upload_indicator)
        layout.addWidget(upload_btn)

        return widget

    def create_manage_tab(self):
        """创建管理面板选项卡"""
        widget = QFrame()
        layout = QVBoxLayout(widget)

        # 我的发布
        published_group = QGroupBox("我的发布")
        published_layout = QVBoxLayout(published_group)

        self.published_table = QTableWidget()
        self.published_table.setColumnCount(7)
        self.published_table.setHorizontalHeaderLabels([
            "指标名称", "版本", "下载量", "评分", "收入", "状态", "操作"
        ])
        self.published_table.horizontalHeader().setStretchLastSection(True)
        published_layout.addWidget(self.published_table)

        layout.addWidget(published_group)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QFormLayout(stats_group)

        self.total_downloads_label = QLabel("0")
        self.total_income_label = QLabel("¥0")
        self.avg_rating_label = QLabel("0.0")
        self.total_indicators_label = QLabel("0")

        stats_layout.addRow("总下载量:", self.total_downloads_label)
        stats_layout.addRow("总收入:", self.total_income_label)
        stats_layout.addRow("平均评分:", self.avg_rating_label)
        stats_layout.addRow("发布指标数:", self.total_indicators_label)

        layout.addWidget(stats_group)

        return widget

    def load_sample_data(self):
        """加载示例数据"""
        self.indicators = [
            {
                'id': 1,
                'name': 'SuperTrend增强版',
                'description': '基于ATR的趋势跟踪指标，加入了动态参数调整功能',
                'author': '量化大师',
                'version': '2.1.0',
                'category': '趋势指标',
                'rating': 4.8,
                'downloads': 1250,
                'likes': 89,
                'price': 0,
                'tags': ['趋势', 'ATR', '动态'],
                'created_date': '2024-01-15'
            },
            {
                'id': 2,
                'name': 'AI智能RSI',
                'description': '使用机器学习优化的RSI指标，提供更准确的超买超卖信号',
                'author': 'AI交易员',
                'version': '1.5.2',
                'category': '震荡指标',
                'rating': 4.6,
                'downloads': 890,
                'likes': 67,
                'price': 99,
                'tags': ['AI', 'RSI', '机器学习'],
                'created_date': '2024-02-01'
            },
            {
                'id': 3,
                'name': '成交量能量指标',
                'description': '综合价格和成交量的能量分析指标，识别主力资金流向',
                'author': '主力猎手',
                'version': '3.0.1',
                'category': '成交量指标',
                'rating': 4.9,
                'downloads': 2100,
                'likes': 156,
                'price': 199,
                'tags': ['成交量', '资金流', '主力'],
                'created_date': '2024-01-20'
            },
            {
                'id': 4,
                'name': '多周期MACD',
                'description': '同时显示多个周期的MACD指标，提供全面的趋势分析',
                'author': '周期分析师',
                'version': '1.8.0',
                'category': '动量指标',
                'rating': 4.4,
                'downloads': 750,
                'likes': 45,
                'price': 0,
                'tags': ['MACD', '多周期', '趋势'],
                'created_date': '2024-02-10'
            },
            {
                'id': 5,
                'name': '自适应布林带',
                'description': '根据市场波动性自动调整参数的布林带指标',
                'author': '波动专家',
                'version': '2.3.1',
                'category': '趋势指标',
                'rating': 4.7,
                'downloads': 1580,
                'likes': 92,
                'price': 149,
                'tags': ['布林带', '自适应', '波动性'],
                'created_date': '2024-01-25'
            }
        ]

        self.display_indicators()

    def display_indicators(self):
        """显示指标卡片"""
        # 清空现有卡片
        for i in reversed(range(self.indicators_layout.count())):
            child = self.indicators_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        # 筛选指标
        filtered_indicators = self.get_filtered_indicators()

        # 创建指标卡片
        columns = 3
        for i, indicator in enumerate(filtered_indicators):
            row = i // columns
            col = i % columns

            card = IndicatorCard(indicator)
            card.install_clicked.connect(self.install_indicator)
            card.details_clicked.connect(self.show_indicator_details)

            self.indicators_layout.addWidget(card, row, col)

    def get_filtered_indicators(self):
        """获取筛选后的指标"""
        filtered = self.indicators

        # 按分类筛选
        if self.current_category != "全部":
            filtered = [ind for ind in filtered if ind['category']
                        == self.current_category]

        # 按搜索关键词筛选
        search_text = self.search_edit.text().lower()
        if search_text:
            filtered = [ind for ind in filtered
                        if search_text in ind['name'].lower()
                        or search_text in ind['description'].lower()
                        or search_text in ind['author'].lower()]

        return filtered

    def on_category_changed(self, category):
        """分类改变事件"""
        self.current_category = category
        self.display_indicators()

    def filter_indicators(self):
        """筛选指标"""
        self.display_indicators()

    def sort_indicators(self, sort_type):
        """排序指标"""
        if sort_type == "最新":
            self.indicators.sort(key=lambda x: x['created_date'], reverse=True)
        elif sort_type == "最热":
            self.indicators.sort(key=lambda x: x['likes'], reverse=True)
        elif sort_type == "评分最高":
            self.indicators.sort(key=lambda x: x['rating'], reverse=True)
        elif sort_type == "下载最多":
            self.indicators.sort(key=lambda x: x['downloads'], reverse=True)

        self.display_indicators()

    def install_indicator(self, indicator_data):
        """安装指标"""
        try:
            indicator_name = indicator_data['name']

            # 确认安装
            reply = QMessageBox.question(
                self, "确认安装",
                f"确定要安装指标 '{indicator_name}' 吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 模拟安装过程
                progress = QProgressBar()
                progress.setRange(0, 100)

                # 这里应该实现真实的安装逻辑
                for i in range(101):
                    progress.setValue(i)
                    time.sleep(0.01)

                QMessageBox.information(
                    self, "安装成功", f"指标 '{indicator_name}' 安装成功！")
                self.indicator_installed.emit(indicator_data)

        except Exception as e:
            QMessageBox.critical(self, "安装失败", f"安装指标失败: {str(e)}")

    def show_indicator_details(self, indicator_data):
        """显示指标详情"""
        details_dialog = QDialog(self)
        details_dialog.setWindowTitle(f"指标详情 - {indicator_data['name']}")
        details_dialog.setModal(True)
        details_dialog.resize(600, 500)

        layout = QVBoxLayout(details_dialog)

        # 基本信息
        info_text = f"""
        <h2>{indicator_data['name']}</h2>
        <p><b>作者:</b> {indicator_data['author']}</p>
        <p><b>版本:</b> {indicator_data['version']}</p>
        <p><b>分类:</b> {indicator_data['category']}</p>
        <p><b>评分:</b> {'' * int(indicator_data['rating'])} ({indicator_data['rating']})</p>
        <p><b>下载量:</b> {indicator_data['downloads']}</p>
        <p><b>价格:</b> {'免费' if indicator_data['price'] == 0 else f'¥{indicator_data["price"]}'}</p>
        <p><b>标签:</b> {', '.join(indicator_data.get('tags', []))}</p>
        
        <h3>描述</h3>
        <p>{indicator_data['description']}</p>
        """

        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 按钮
        button_layout = QHBoxLayout()
        install_btn = QPushButton("安装")
        favorite_btn = QPushButton("收藏")
        close_btn = QPushButton("关闭")

        install_btn.clicked.connect(
            lambda: self.install_indicator(indicator_data))
        close_btn.clicked.connect(details_dialog.accept)

        button_layout.addWidget(install_btn)
        button_layout.addWidget(favorite_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        details_dialog.exec_()

    def select_indicator_file(self):
        """选择指标文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择指标文件", "", "Python文件 (*.py);;所有文件 (*)"
        )
        if file_path:
            self.indicator_file_edit.setText(file_path)

    def select_doc_file(self):
        """选择文档文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文档文件", "", "文档文件 (*.md *.txt *.pdf);;所有文件 (*)"
        )
        if file_path:
            self.doc_file_edit.setText(file_path)

    def upload_indicator(self):
        """上传指标"""
        try:
            name = self.upload_name_edit.text().strip()
            description = self.upload_description_edit.toPlainText().strip()
            indicator_file = self.indicator_file_edit.text().strip()

            if not name or not description or not indicator_file:
                QMessageBox.warning(self, "警告", "请填写完整的指标信息并选择指标文件")
                return

            # 模拟上传过程
            progress_dialog = QProgressBar()
            progress_dialog.setRange(0, 100)

            for i in range(101):
                progress_dialog.setValue(i)
                time.sleep(0.02)

            QMessageBox.information(self, "上传成功", f"指标 '{name}' 上传成功！")

            # 清空表单
            self.upload_name_edit.clear()
            self.upload_description_edit.clear()
            self.indicator_file_edit.clear()
            self.doc_file_edit.clear()

            self.indicator_uploaded.emit({
                'name': name,
                'description': description,
                'category': self.upload_category_combo.currentText(),
                'version': self.upload_version_edit.text(),
                'price': self.price_spin.value()
            })

        except Exception as e:
            QMessageBox.critical(self, "上传失败", f"上传指标失败: {str(e)}")

    def refresh_market(self):
        """刷新市场"""
        # 模拟刷新过程
        self.load_sample_data()
        QMessageBox.information(self, "刷新完成", "市场数据已刷新")
