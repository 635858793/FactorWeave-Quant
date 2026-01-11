"""
指标组合管理对话框

提供用户界面来管理指标组合，包括加载、删除、导入导出等功能。
"""

from loguru import logger
import sys
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QGroupBox, QMessageBox, QDialogButtonBox,
    QSplitter, QWidget, QComboBox, QCheckBox, QFileDialog,
    QProgressBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QApplication, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

from core.indicator_combination_manager import get_combination_manager, IndicatorCombination

logger = logger.bind(module=__name__)

class CombinationLoadThread(QThread):
    """异步加载指标组合线程"""

    combinations_loaded = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, search_query: str = "", tags: List[str] = None):
        super().__init__()
        self.search_query = search_query
        self.tags = tags or []

    def run(self):
        """运行加载任务"""
        try:
            manager = get_combination_manager()

            if self.search_query or self.tags:
                combinations = manager.search_combinations(
                    self.search_query, self.tags)
            else:
                combinations = manager.get_all_combinations()

            self.combinations_loaded.emit(combinations)

        except Exception as e:
            self.error_occurred.emit(str(e))

class IndicatorCombinationDialog(QDialog):
    """指标组合管理对话框"""

    combination_selected = pyqtSignal(str, list)  # 组合名称, 指标列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = get_combination_manager()
        self.current_combinations = {}
        self.selected_combination = None
        self.load_thread = None
        self._init_ui()
        self._load_combinations()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("指标组合管理")
        self.setModal(True)
        self.resize(900, 650)

        # 主布局
        main_layout = QVBoxLayout()

        # 标题
        title_label = QLabel("指标组合管理")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)

        # 搜索区域
        search_layout = self._create_search_area()
        main_layout.addLayout(search_layout)

        # 主要内容区域
        content_splitter = QSplitter(Qt.Horizontal)

        # 左侧：组合列表
        left_panel = self._create_left_panel()
        content_splitter.addWidget(left_panel)

        # 右侧：组合详情
        right_panel = self._create_right_panel()
        content_splitter.addWidget(right_panel)

        # 设置分割器比例
        content_splitter.setSizes([300, 600])
        main_layout.addWidget(content_splitter)

        # 按钮区域
        button_layout = self._create_button_area()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # 绑定事件
        self._bind_events()

    def _create_search_area(self) -> QHBoxLayout:
        """创建搜索区域"""
        layout = QHBoxLayout()

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索组合名称、描述或指标...")
        layout.addWidget(QLabel("搜索:"))
        layout.addWidget(self.search_input)

        # 搜索按钮
        self.search_button = QPushButton("搜索")
        layout.addWidget(self.search_button)

        # 清除按钮
        self.clear_button = QPushButton("清除")
        layout.addWidget(self.clear_button)

        # 刷新按钮
        self.refresh_button = QPushButton("刷新")
        layout.addWidget(self.refresh_button)

        return layout

    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout()

        # 组合列表
        list_group = QGroupBox("指标组合列表")
        list_layout = QVBoxLayout()

        self.combination_list = QListWidget()
        self.combination_list.setSelectionMode(
            QAbstractItemView.SingleSelection)
        list_layout.addWidget(self.combination_list)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QVBoxLayout()

        self.stats_label = QLabel("正在加载...")
        stats_layout.addWidget(self.stats_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        panel.setLayout(layout)
        return panel

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout()

        # 组合详情
        details_group = QGroupBox("组合详情")
        details_layout = QVBoxLayout()

        # 基本信息
        info_layout = QGridLayout()

        self.name_label = QLabel("名称:")
        self.name_value = QLabel("-")
        info_layout.addWidget(self.name_label, 0, 0)
        info_layout.addWidget(self.name_value, 0, 1)

        self.created_label = QLabel("创建时间:")
        self.created_value = QLabel("-")
        info_layout.addWidget(self.created_label, 1, 0)
        info_layout.addWidget(self.created_value, 1, 1)

        self.updated_label = QLabel("更新时间:")
        self.updated_value = QLabel("-")
        info_layout.addWidget(self.updated_label, 2, 0)
        info_layout.addWidget(self.updated_value, 2, 1)

        details_layout.addLayout(info_layout)

        # 描述
        self.description_label = QLabel("描述:")
        self.description_text = QTextEdit()
        self.description_text.setMaximumHeight(80)
        self.description_text.setReadOnly(True)
        details_layout.addWidget(self.description_label)
        details_layout.addWidget(self.description_text)

        # 标签
        self.tags_label = QLabel("标签:")
        self.tags_value = QLabel("-")
        details_layout.addWidget(self.tags_label)
        details_layout.addWidget(self.tags_value)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # 指标列表
        indicators_group = QGroupBox("包含的指标")
        indicators_layout = QVBoxLayout()

        self.indicators_table = QTableWidget()
        self.indicators_table.setColumnCount(3)
        self.indicators_table.setHorizontalHeaderLabels(["指标名称", "类型", "参数"])

        # 设置表格属性
        header = self.indicators_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        self.indicators_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.indicators_table.setAlternatingRowColors(True)

        indicators_layout.addWidget(self.indicators_table)
        indicators_group.setLayout(indicators_layout)
        layout.addWidget(indicators_group)

        panel.setLayout(layout)
        return panel

    def _create_button_area(self) -> QHBoxLayout:
        """创建按钮区域"""
        layout = QHBoxLayout()

        # 管理按钮
        self.load_button = QPushButton("加载组合")
        self.load_button.setEnabled(False)
        layout.addWidget(self.load_button)

        self.delete_button = QPushButton("删除组合")
        self.delete_button.setEnabled(False)
        layout.addWidget(self.delete_button)

        layout.addStretch()

        # 导入导出按钮
        self.import_button = QPushButton("导入组合")
        layout.addWidget(self.import_button)

        self.export_button = QPushButton("导出组合")
        layout.addWidget(self.export_button)

        layout.addStretch()

        # 对话框按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        return layout

    def _bind_events(self):
        """绑定事件"""
        # 搜索相关
        self.search_button.clicked.connect(self._on_search)
        self.clear_button.clicked.connect(self._on_clear_search)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.search_input.returnPressed.connect(self._on_search)

        # 列表选择
        self.combination_list.itemSelectionChanged.connect(
            self._on_selection_changed)

        # 管理按钮
        self.load_button.clicked.connect(self._on_load_combination)
        self.delete_button.clicked.connect(self._on_delete_combination)

        # 导入导出
        self.import_button.clicked.connect(self._on_import_combinations)
        self.export_button.clicked.connect(self._on_export_combinations)

    def _load_combinations(self, search_query: str = ""):
        """加载指标组合"""
        try:
            # 如果有正在运行的线程，先停止
            if self.load_thread and self.load_thread.isRunning():
                self.load_thread.terminate()
                self.load_thread.wait()

            # 创建新的加载线程
            self.load_thread = CombinationLoadThread(search_query)
            self.load_thread.combinations_loaded.connect(
                self._on_combinations_loaded)
            self.load_thread.error_occurred.connect(self._on_load_error)
            self.load_thread.start()

            # 显示加载状态
            self.combination_list.clear()
            self.combination_list.addItem("正在加载...")

        except Exception as e:
            logger.error(f"Failed to load combinations: {e}")
            QMessageBox.critical(self, "错误", f"加载组合失败:\n{str(e)}")

    def _on_combinations_loaded(self, combinations: Dict[str, IndicatorCombination]):
        """处理组合加载完成"""
        try:
            self.current_combinations = combinations
            self._update_combination_list()
            self._update_stats()

        except Exception as e:
            logger.error(f"Failed to process loaded combinations: {e}")

    def _on_load_error(self, error: str):
        """处理加载错误"""
        logger.error(f"Load error: {error}")
        QMessageBox.critical(self, "错误", f"加载组合失败:\n{error}")
        self.combination_list.clear()

    def _update_combination_list(self):
        """更新组合列表"""
        self.combination_list.clear()

        if not self.current_combinations:
            self.combination_list.addItem("没有找到组合")
            return

        for name, combination in self.current_combinations.items():
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, combination)
            self.combination_list.addItem(item)

    def _update_stats(self):
        """更新统计信息"""
        try:
            stats = self.manager.get_combination_stats()

            stats_text = f"""
总组合数: {stats['total_combinations']}
总指标数: {stats['total_indicators']}
常用指标: {', '.join(list(stats['most_used_indicators'].keys())[:3])}
标签数: {len(stats['tags'])}
            """.strip()

            self.stats_label.setText(stats_text)

        except Exception as e:
            logger.error(f"Failed to update stats: {e}")
            self.stats_label.setText("统计信息获取失败")

    def _on_selection_changed(self):
        """处理选择变化"""
        try:
            selected_items = self.combination_list.selectedItems()

            if not selected_items:
                self._clear_details()
                self.load_button.setEnabled(False)
                self.delete_button.setEnabled(False)
                return

            item = selected_items[0]
            combination = item.data(Qt.UserRole)

            if combination:
                self.selected_combination = combination
                self._update_details(combination)
                self.load_button.setEnabled(True)
                self.delete_button.setEnabled(True)
            else:
                self._clear_details()
                self.load_button.setEnabled(False)
                self.delete_button.setEnabled(False)

        except Exception as e:
            logger.error(f"Failed to handle selection change: {e}")

    def _update_details(self, combination: IndicatorCombination):
        """更新详情显示"""
        try:
            # 基本信息
            self.name_value.setText(combination.name)
            self.created_value.setText(combination.created_at[:19])  # 去掉毫秒
            self.updated_value.setText(combination.updated_at[:19])

            # 描述
            self.description_text.setPlainText(combination.description)

            # 标签
            if combination.tags:
                self.tags_value.setText(", ".join(combination.tags))
            else:
                self.tags_value.setText("无")

            # 指标列表
            self.indicators_table.setRowCount(len(combination.indicators))

            for row, indicator in enumerate(combination.indicators):
                # 指标名称
                name_item = QTableWidgetItem(indicator.get('name', ''))
                self.indicators_table.setItem(row, 0, name_item)

                # 指标类型
                type_item = QTableWidgetItem(indicator.get('type', ''))
                self.indicators_table.setItem(row, 1, type_item)

                # 参数
                params = indicator.get('params', {})
                params_text = ", ".join(
                    [f"{k}={v}" for k, v in params.items()])
                params_item = QTableWidgetItem(params_text)
                self.indicators_table.setItem(row, 2, params_item)

        except Exception as e:
            logger.error(f"Failed to update details: {e}")

    def _clear_details(self):
        """清除详情显示"""
        self.name_value.setText("-")
        self.created_value.setText("-")
        self.updated_value.setText("-")
        self.description_text.clear()
        self.tags_value.setText("-")
        self.indicators_table.setRowCount(0)

    def _on_search(self):
        """处理搜索"""
        search_query = self.search_input.text().strip()
        self._load_combinations(search_query)

    def _on_clear_search(self):
        """清除搜索"""
        self.search_input.clear()
        self._load_combinations()

    def _on_refresh(self):
        """刷新列表"""
        search_query = self.search_input.text().strip()
        self._load_combinations(search_query)

    def _on_load_combination(self):
        """加载选中的组合"""
        if not self.selected_combination:
            return

        try:
            # 发送组合选择信号
            self.combination_selected.emit(
                self.selected_combination.name,
                self.selected_combination.indicators
            )

            QMessageBox.information(
                self,
                "成功",
                f"组合 '{self.selected_combination.name}' 已加载"
            )

        except Exception as e:
            logger.error(f"Failed to load combination: {e}")
            QMessageBox.critical(self, "错误", f"加载组合失败:\n{str(e)}")

    def _on_delete_combination(self):
        """删除选中的组合"""
        if not self.selected_combination:
            return

        try:
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除组合 '{self.selected_combination.name}' 吗？\n此操作无法撤销。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                success = self.manager.delete_combination(
                    self.selected_combination.name)

                if success:
                    QMessageBox.information(self, "成功", "组合删除成功")
                    self._on_refresh()  # 刷新列表
                else:
                    QMessageBox.critical(self, "错误", "删除组合失败")

        except Exception as e:
            logger.error(f"Failed to delete combination: {e}")
            QMessageBox.critical(self, "错误", f"删除组合失败:\n{str(e)}")

    def _on_import_combinations(self):
        """导入组合"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "导入指标组合",
                "",
                "JSON文件 (*.json);;所有文件 (*)"
            )

            if file_path:
                reply = QMessageBox.question(
                    self,
                    "导入确认",
                    "是否覆盖同名的现有组合？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                overwrite = reply == QMessageBox.Yes
                success = self.manager.import_combinations(
                    file_path, overwrite)

                if success:
                    QMessageBox.information(self, "成功", "组合导入成功")
                    self._on_refresh()
                else:
                    QMessageBox.critical(self, "错误", "导入组合失败")

        except Exception as e:
            logger.error(f"Failed to import combinations: {e}")
            QMessageBox.critical(self, "错误", f"导入组合失败:\n{str(e)}")

    def _on_export_combinations(self):
        """导出组合"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出指标组合",
                "indicator_combinations.json",
                "JSON文件 (*.json);;所有文件 (*)"
            )

            if file_path:
                success = self.manager.export_combinations(file_path)

                if success:
                    QMessageBox.information(
                        self, "成功", f"组合已导出到:\n{file_path}")
                else:
                    QMessageBox.critical(self, "错误", "导出组合失败")

        except Exception as e:
            logger.error(f"Failed to export combinations: {e}")
            QMessageBox.critical(self, "错误", f"导出组合失败:\n{str(e)}")

    def _accept(self):
        """确认并关闭对话框"""
        if self.selected_combination:
            self.combination_selected.emit(
                self.selected_combination.name,
                self.selected_combination.indicators
            )

        self.accept()

    def closeEvent(self, event):
        """关闭事件"""
        # 停止加载线程
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.terminate()
            self.load_thread.wait()

        event.accept()

def main():
    """测试函数"""
    app = QApplication(sys.argv)

    dialog = IndicatorCombinationDialog()

    def on_combination_selected(name, indicators):
        print(f"选择了组合: {name}")
        print(f"包含指标: {[ind['name'] for ind in indicators]}")

    dialog.combination_selected.connect(on_combination_selected)
    dialog.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
