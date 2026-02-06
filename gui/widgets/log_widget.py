from loguru import logger
"""
日志控件模块

提供日志显示和管理功能
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
import json
import pandas as pd
import matplotlib.pyplot as plt
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败: {e}")

class DragHandle(QWidget):
    """顶部可拖动分隔条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self.setCursor(Qt.SizeVerCursor)
        self._dragging = False
        self._drag_start_pos = None
        self._orig_height = None
        self.setStyleSheet(
            "background: #e0e0e0; border-top: 1px solid #bdbdbd; border-bottom: 1px solid #bdbdbd;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPos()
            self._orig_height = self.parentWidget().height() if self.parentWidget() else None
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_start_pos and self._orig_height is not None:
            dy = event.globalY() - self._drag_start_pos.y()
            new_height = max(60, self._orig_height - dy)
            if self.parentWidget():
                self.parentWidget().setFixedHeight(new_height)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._drag_start_pos = None
        self._orig_height = None
        event.accept()

class LogWidget(QWidget):
    """日志控件类"""

    # 定义信号，确保日志更新在主线程进行
    _log_received = pyqtSignal(str, str)  # level, message

    def __init__(self, parent=None):
        """初始化日志控件

        Args:
            # log_manager: 已迁移到Loguru日志系统
            parent: 父窗口
        """
        try:
            # 避免self作为parent导致布局错乱，parent只允许为None或QWidget实例且不能为self
            if parent is not None and (parent is self or not isinstance(parent, QWidget)):
                parent = None
            super().__init__(parent)
            self.log_text = None  # 确保属性总是存在

            # 使用传入的日志管理器或创建新的
            # 纯Loguru架构，移除log_manager依赖

            self.pause_scroll = False  # 显式初始化
            self.user_paused = False  # 新增：区分用户主动暂停
            self.popup_dialog = None   # 持有弹窗引用
            self._all_logs = []        # 存储所有日志 (message, level, timestamp)
            self._structured_fields = set()  # 1. 在LogWidget.__init__中初始化结构化字段缓存

            # 初始化UI
            self.init_ui()

            # 连接信号
            self._log_received.connect(self._update_log_text)
            self.connect_signals()

            # 延迟导入并设置样式
            _import_theme_manager()
            self.theme_manager = None
            if THEME_MANAGER_AVAILABLE:
                try:
                    self.theme_manager = get_theme_manager()
                except Exception as e:
                    logger.warning(f"获取ThemeManager失败: {e}")

            logger.info("日志控件初始化完成")

        except Exception as e:
            error_msg = f"初始化失败: {str(e)}"
            self.log_text = None
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def init_ui(self):
        """初始化UI，动态生成结构化字段筛选器和时间区间筛选"""
        try:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.setAlignment(Qt.AlignTop)
            self.drag_handle = DragHandle(self)
            layout.addWidget(self.drag_handle)
            toolbar_layout = QHBoxLayout()
            toolbar_layout.setContentsMargins(-2, -2, -2, -2)
            toolbar_layout.setSpacing(0)
            toolbar_layout.setAlignment(Qt.AlignTop)
            # 日志级别过滤器
            level_label = QLabel("日志级别:")
            level_label.setFixedWidth(60)
            self.level_combo = QComboBox()
            self.level_combo.addItems(["全部", "信息", "警告", "错误", "调试"])
            self.level_combo.setFixedWidth(80)
            toolbar_layout.addWidget(level_label)
            toolbar_layout.addWidget(self.level_combo)
            # event筛选器
            self.event_combo = QComboBox()
            self.event_combo.setFixedWidth(120)
            self.event_combo.addItem("全部事件")
            toolbar_layout.addWidget(self.event_combo)
            # module筛选器
            self.module_combo = QComboBox()
            self.module_combo.setFixedWidth(120)
            self.module_combo.addItem("全部模块")
            toolbar_layout.addWidget(self.module_combo)
            # 时间区间筛选
            self.time_start = QDateTimeEdit()
            self.time_start.setDateTime(QDateTime.currentDateTime())
            self.time_start.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            self.time_start.setCalendarPopup(True)
            self.time_end = QDateTimeEdit()
            self.time_end.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            self.time_end.setDateTime(QDateTime.currentDateTime().addDays(1))
            self.time_end.setCalendarPopup(True)
            toolbar_layout.addWidget(QLabel("起止时间:"))
            toolbar_layout.addWidget(self.time_start)
            toolbar_layout.addWidget(QLabel("-"))
            toolbar_layout.addWidget(self.time_end)
            # 搜索框
            self.search_box = QLineEdit()
            self.search_box.setPlaceholderText("搜索日志...")
            self.search_box.setFixedWidth(180)
            toolbar_layout.addWidget(self.search_box)
            toolbar_layout.addStretch(0)
            self.scroll_status_label = QLabel("自动滚动中")
            self.scroll_status_label.setFixedWidth(60)
            toolbar_layout.addWidget(self.scroll_status_label)
            self.maximize_btn = QPushButton("最大化")
            # self.maximize_btn.setFixedWidth(70)
            self.maximize_btn.clicked.connect(self.toggle_maximize)
            toolbar_layout.addWidget(self.maximize_btn)
            self.popup_btn = QPushButton("弹窗")
            # self.popup_btn.setFixedWidth(70)
            self.popup_btn.clicked.connect(self.show_popup)
            toolbar_layout.addWidget(self.popup_btn)
            self.pause_btn = QPushButton("暂停滚动")
            # self.pause_btn.setFixedWidth(80)
            self.pause_btn.clicked.connect(self.toggle_scroll)
            toolbar_layout.addWidget(self.pause_btn)
            self.clear_button = QPushButton("清除")
            # self.clear_button.setFixedWidth(60)
            toolbar_layout.addWidget(self.clear_button)
            self.export_button = QPushButton("导出日志")
            # self.export_button.setFixedWidth(60)
            self.export_button.clicked.connect(self.export_logs)
            toolbar_layout.addWidget(self.export_button)
            self.visual_button = QPushButton("日志可视化")
            # self.visual_button.setFixedWidth(60)
            self.visual_button.clicked.connect(self.show_log_stats)
            toolbar_layout.addWidget(self.visual_button)
            layout.addLayout(toolbar_layout)
            if self.log_text is None:
                self.log_text = QTextEdit()
            self.log_text.setReadOnly(True)
            self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
            self.log_text.setContextMenuPolicy(Qt.CustomContextMenu)
            self.log_text.customContextMenuRequested.connect(
                self.show_log_context_menu)
            self.log_text.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.log_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.log_text.setStyleSheet(
                "margin-top: 0px; margin-bottom: 0px; font-size: 12px; line-height: 1.4; padding: 5px 16px; font-family: 'Consolas', 'Microsoft YaHei', monospace;")
            layout.addWidget(self.log_text, 1)
            self.log_text.verticalScrollBar().valueChanged.connect(
                self._on_scrollbar_value_changed)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.update()
            self.adjustSize()
            logger.info("日志控件UI初始化完成")
        except Exception as e:
            error_msg = f"初始化UI失败,加载默认日志控件: {str(e)}"
            if self.log_text is None:
                self.log_text = QTextEdit()
                self.log_text.setReadOnly(True)
                self.log_text.setSizePolicy(
                    QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.log_text.setHorizontalScrollBarPolicy(
                    Qt.ScrollBarAlwaysOff)
                self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                self.layout().addWidget(self.log_text, 1)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.apply_style()
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)
            self.setVisible(True)
            self.update()
            self.adjustSize()

    def connect_signals(self):
        """连接控件信号（不再连接log_manager信号，信号连接只在主窗口进行）"""
        try:
            if getattr(self, '_signals_connected', False):
                return
            self._signals_connected = True
            # 只连接控件信号，不连接log_manager信号
            self.level_combo.currentTextChanged.connect(self.filter_logs)
            self.search_box.textChanged.connect(self.search_logs)
            self.clear_button.clicked.connect(self.clear_logs)
            self.export_button.clicked.connect(self.export_logs)
            self.visual_button.clicked.connect(self.show_log_stats)
            logger.info("信号连接完成")
        except Exception as e:
            error_msg = f"连接信号失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def apply_style(self):
        pass  # 移除自定义样式，统一由主题管理器apply_theme

    def add_log(self, message: str, level: str = "INFO"):
        """
        线程安全的日志添加方法。
        发射信号，由主线程的槽函数来更新UI。
        """
        self._log_received.emit(level, message)

    @pyqtSlot(str, str)
    def _update_log_text(self, level: str, message: str):
        """在主线程更新日志文本"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 存储原始日志
            log_entry = {
                'timestamp': timestamp,
                'level': level,
                'message': message
            }
            self._all_logs.append(log_entry)

            # 根据当前过滤器判断是否显示
            if not self._should_display(log_entry):
                return

            color = self._get_level_color(level)
            formatted_message = f'<span style="color: {color};"><b>[{level}]</b> {timestamp}: {message}</span>'

            if self.log_text:
                self.log_text.append(formatted_message)
        except Exception as e:
            # 记录到原始日志系统，避免无限循环
            logger.info(f"Error in _update_log_text: {e}")

    def _get_level_color(self, level: str) -> str:
        """根据日志级别获取颜色"""
        if level == "ERROR":
            return "red"
        elif level == "WARNING":
            return "orange"
        elif level == "DEBUG":
            return "purple"
        else:
            return "black"  # 默认颜色

    def _should_display(self, log_entry: dict) -> bool:
        """根据当前过滤器判断日志是否应该显示"""
        # 级别过滤
        current_level_filter = self.level_combo.currentText()
        log_level = log_entry['level']
        level_map = {"全部": 5, "调试": 4, "信息": 3, "警告": 2, "错误": 1}

        log_level_value = level_map.get(log_level.upper(), 3)
        filter_level_value = level_map.get(current_level_filter, 5)

        if log_level_value > filter_level_value:
            return False

        # 文本过滤
        search_text = self.search_box.text().lower()
        if search_text and search_text not in log_entry['message'].lower():
            return False

        return True

    def flash_error(self):
        """错误闪烁提示"""
        try:
            orig_style = self.log_text.styleSheet() if self.log_text else ""
            self.log_text.setStyleSheet(
                orig_style + "background-color: #ffebee;")
            QTimer.singleShot(
                500, lambda: self.log_text.setStyleSheet(orig_style))
        except Exception as e:
            logger.error(f"闪烁错误提示失败: {str(e)}")

    def filter_logs(self, level: str):
        """根据级别过滤日志

        Args:
            level: 日志级别
        """
        self.refresh_display()

    def search_logs(self, text: str):
        """搜索日志

        Args:
            text: 搜索文本
        """
        self.refresh_display()

    def clear_logs(self):
        """清除日志"""
        try:
            self._all_logs.clear()
            if self.log_text is not None:
                self.log_text.clear()
            self.log_cleared.emit()
            logger.info("日志已清除")
            # 清除后强制刷新UI
            self.setVisible(True)
            self.apply_style()
            self.update()
            self.adjustSize()
        except Exception as e:
            error_msg = f"清除日志失败: {str(e)}"
            if self.log_text is None:
                self.log_text = QTextEdit()
                self.log_text.setReadOnly(True)
                self.log_text.setSizePolicy(
                    QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.log_text.setHorizontalScrollBarPolicy(
                    Qt.ScrollBarAlwaysOff)
                self.log_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                self.layout().addWidget(self.log_text, 1)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.apply_style()
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)
            self.setVisible(True)
            self.update()
            self.adjustSize()

    def export_logs(self, fmt="csv"):
        """导出日志到文件"""
        try:
            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出日志",
                "",
                "CSV Files (*.csv);;JSON Files (*.json)"
            )

            if file_path:
                # 保存日志
                logs = [l for l in self._all_logs if isinstance(l[0], dict)]
                if not logs:
                    return
                df = pd.DataFrame(
                    [dict(**d[0], level=d[1], timestamp=d[2]) for d in logs])
                if fmt == "csv":
                    df.to_csv(file_path, index=False)
                else:
                    df.to_json(file_path, orient="records", force_ascii=False)

                logger.info(f"日志已导出到: {file_path}")

        except Exception as e:
            error_msg = f"导出日志失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def show_log_context_menu(self, pos):
        """日志内容右键菜单：复制、全选、清空、导出"""
        menu = QMenu(self)
        copy_action = menu.addAction("复制")
        select_all_action = menu.addAction("全选")
        clear_action = menu.addAction("清空")
        export_action = menu.addAction("导出")
        action = menu.exec_(self.log_text.mapToGlobal(pos))
        if action == copy_action:
            self.log_text.copy()
        elif action == select_all_action:
            self.log_text.selectAll()
        elif action == clear_action:
            self.clear_logs()
        elif action == export_action:
            self.export_logs()

    def toggle_maximize(self):
        """最大化/全屏/还原日志区"""
        window = self.window()
        if hasattr(self, '_is_maximized') and self._is_maximized:
            # 还原
            if hasattr(self, '_old_geometry'):
                self.setGeometry(self._old_geometry)
            if hasattr(window, 'showNormal'):
                window.showNormal()
            self._is_maximized = False
            self.maximize_btn.setText("最大化")
        else:
            # 全屏
            self._old_geometry = self.geometry()
            if hasattr(window, 'showFullScreen'):
                window.showFullScreen()
            self._is_maximized = True
            self.maximize_btn.setText("还原")

    def show_popup(self):
        """显示日志弹窗"""
        try:
            # 如果已有弹窗，则激活它
            if hasattr(self, 'popup_dialog') and self.popup_dialog:
                self.popup_dialog.activateWindow()
                self.popup_dialog.raise_()
                return

            # 创建弹窗
            self.popup_dialog = QDialog(self.window())
            self.popup_dialog.setWindowTitle("日志详情")
            self.popup_dialog.setMinimumSize(800, 600)
            self.popup_dialog.setWindowFlags(
                Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint
            )
            self.popup_dialog.setWindowModality(Qt.NonModal)
            self.popup_dialog.setAttribute(Qt.WA_DeleteOnClose)

            # 创建主布局
            layout = QVBoxLayout(self.popup_dialog)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(5)

            # 顶部工具栏
            toolbar_layout = QHBoxLayout()
            toolbar_layout.setSpacing(16)
            toolbar_layout.setContentsMargins(0, 0, 0, 0)

            # 日志级别过滤
            level_label = QLabel("日志级别:")
            level_label.setFixedWidth(60)
            level_label.setFixedHeight(45)
            level_label.setAlignment(Qt.AlignCenter)
            level_label.setStyleSheet("color: #1376d2;")
            level_combo = QComboBox()
            toolbar_layout.addWidget(level_label)
            level_combo.addItems(["全部", "信息", "警告", "错误", "调试"])
            level_combo.setCurrentText(self.level_combo.currentText())
            level_combo.setFixedWidth(100)
            toolbar_layout.addWidget(level_combo)

            # 搜索框
            search_box = QLineEdit()
            search_box.setPlaceholderText("搜索日志...")
            search_box.setText(self.search_box.text())
            search_box.setFixedWidth(200)
            toolbar_layout.addWidget(search_box)

            # 添加弹性空间
            toolbar_layout.addStretch()

            # 清除按钮
            clear_btn = QPushButton("清除")
            clear_btn.setFixedWidth(80)
            toolbar_layout.addWidget(clear_btn)

            # 导出按钮
            export_btn = QPushButton("导出")
            export_btn.setFixedWidth(80)
            toolbar_layout.addWidget(export_btn)

            layout.addLayout(toolbar_layout)

            # 日志内容区
            log_text = QTextEdit()
            log_text.setReadOnly(True)
            log_text.setLineWrapMode(QTextEdit.WidgetWidth)
            log_text.setAlignment(Qt.AlignLeft)
            log_text.setStyleSheet("""
                QTextEdit {
                    font-family: 'Consolas', 'Microsoft YaHei', monospace;
                    font-size: 13px;
                    background: #f8fafc;
                    color: #23293a;
        
                    border-radius: 4px;
                    padding: 8px;
                    margin: 0;
                }
                QScrollBar:vertical {
                    background: #f0f0f0;
                    width: 12px;
                    margin: 0;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background: #bdbdbd;
                    min-height: 30px;
                    border-radius: 6px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                }
                QScrollBar:horizontal {
                    background: #f0f0f0;
                    height: 12px;
                    margin: 0;
                    border-radius: 6px;
                }
                QScrollBar::handle:horizontal {
                    background: #bdbdbd;
                    min-width: 30px;
                    border-radius: 6px;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0;
                }
            """)
            log_text.setSizePolicy(QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
            layout.addWidget(log_text, 1)

            # 保存对话框组件的引用，供refresh_popup方法使用
            self._popup_log_text = log_text
            self._popup_level_combo = level_combo
            self._popup_search_box = search_box

            # 日志内容渲染逻辑 - 定义为实例方法
            self.get_filtered_logs_html = lambda: self._get_popup_filtered_logs_html(level_combo, search_box)

            # 初始刷新
            self.refresh_popup()

            # 工具栏交互同步
            def on_level_changed(text):
                self.refresh_popup()

            def on_search_changed(text):
                self.refresh_popup()

            level_combo.currentTextChanged.connect(on_level_changed)
            search_box.textChanged.connect(on_search_changed)
            clear_btn.clicked.connect(self.clear_logs)

            def do_export():
                file_path, _ = QFileDialog.getSaveFileName(
                    self.popup_dialog, "导出日志", "", "Text Files (*.txt);;Log Files (*.log)")
                if file_path:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(log_text.toPlainText())

            export_btn.clicked.connect(do_export)

            # 右键菜单
            def show_context_menu(pos):
                menu = QMenu(self.popup_dialog)
                copy_action = menu.addAction("复制")
                select_all_action = menu.addAction("全选")
                clear_action = menu.addAction("清空")
                export_action = menu.addAction("导出")
                action = menu.exec_(log_text.mapToGlobal(pos))
                if action == copy_action:
                    log_text.copy()
                elif action == select_all_action:
                    log_text.selectAll()
                elif action == clear_action:
                    log_text.clear()
                elif action == export_action:
                    do_export()

            log_text.customContextMenuRequested.connect(show_context_menu)

            def on_close():
                self.popup_dialog = None
                self._popup_log_text = None
                self._popup_level_combo = None
                self._popup_search_box = None

            self.popup_dialog.finished.connect(on_close)

            # 显示弹窗并设置位置
            self.popup_dialog.show()
            self.center_dialog(self.popup_dialog, self.window(), offset_y=50)
            self.popup_dialog.raise_()
            self.popup_dialog.activateWindow()

        except Exception as e:
            error_msg = f"显示日志弹窗失败: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.error_occurred.emit(error_msg)

    def center_dialog(self, dialog, parent=None, offset_y=50):
        """将弹窗居中到父窗口或屏幕，并尽量靠近上部

        Args:
            dialog: 要居中的对话框
            parent: 父窗口，如果为None则使用屏幕
            offset_y: 距离顶部的偏移量
        """
        try:
            if parent and parent.isVisible():
                # 相对于父窗口居中
                parent_geom = parent.geometry()
                dialog_geom = dialog.frameGeometry()
                x = parent_geom.center().x() - dialog_geom.width() // 2
                y = parent_geom.top() + offset_y

                # 确保弹窗不会超出父窗口边界
                x = max(parent_geom.left(), min(
                    x, parent_geom.right() - dialog_geom.width()))
                y = max(parent_geom.top(), min(
                    y, parent_geom.bottom() - dialog_geom.height()))
            else:
                # 相对于屏幕居中
                screen = dialog.screen() or dialog.parentWidget().screen()
                if screen:
                    screen_geom = screen.geometry()
                    dialog_geom = dialog.frameGeometry()
                    x = screen_geom.center().x() - dialog_geom.width() // 2
                    y = screen_geom.top() + offset_y

                    # 确保弹窗不会超出屏幕边界
                    x = max(screen_geom.left(), min(
                        x, screen_geom.right() - dialog_geom.width()))
                    y = max(screen_geom.top(), min(
                        y, screen_geom.bottom() - dialog_geom.height()))

            dialog.move(x, y)
        except Exception as e:
            logger.error(f"设置弹窗位置失败: {str(e)}")
            logger.error(traceback.format_exc())

    def toggle_scroll(self):
        """暂停/恢复自动滚动"""
        self.user_paused = not self.user_paused
        self.pause_scroll = self.user_paused
        if self.pause_scroll:
            self.pause_btn.setText("恢复滚动")
        else:
            self.pause_btn.setText("暂停滚动")
            # 恢复自动滚动时立即刷新并滚动到底部
            self.refresh_display(scroll_to_end=True)

    def _on_scrollbar_value_changed(self, value):
        """监听滚动条变化，自动切换自动滚动状态（仅在未手动暂停时生效）"""
        try:
            if self.user_paused:
                return  # 用户主动暂停时，自动检测不生效
            scrollbar = self.log_text.verticalScrollBar()
            if value == scrollbar.maximum():
                if self.pause_scroll:
                    self.pause_scroll = False
                    self.pause_btn.setText("暂停滚动")
            else:
                if not self.pause_scroll:
                    self.pause_scroll = True
                    self.pause_btn.setText("恢复滚动")
        except Exception as e:
            logger.error(f"滚动条监听失败: {str(e)}")

    def restore_scroll_position(self, scroll_to_end: bool = False):
        """刷新后还原滚动条位置或自动滚动到底部，供所有日志区/弹窗复用 - 线程安全版本"""
        scrollbar = self.log_text.verticalScrollBar()
        if scroll_to_end:
            # 使用单次计时器在主线程中设置滚动条位置
            QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))
        elif self.pause_scroll:
            # 恢复原有滚动条相对位置（防止跳到顶部）
            def restore():
                new_max = scrollbar.maximum()
                new_value = int(self._last_scroll_ratio * new_max)
                scrollbar.setValue(new_value)
            QTimer.singleShot(0, restore)

    def refresh_display(self, scroll_to_end: bool = False):
        """根据所有筛选条件刷新日志显示"""
        level_text = self.level_combo.currentText()
        event_text = self.event_combo.currentText()
        module_text = self.module_combo.currentText()
        search_text = self.search_box.text().strip().lower()
        start_dt = self.time_start.dateTime().toPyDateTime()
        end_dt = self.time_end.dateTime().toPyDateTime()
        html_logs = []
        for msg, lvl, ts in self._all_logs:
            # 结构化日志
            if isinstance(msg, dict):
                if level_text != "全部":
                    if level_text == "信息" and lvl.upper() != "INFO":
                        continue
                    if level_text == "警告" and lvl.upper() != "WARNING":
                        continue
                    if level_text == "错误" and lvl.upper() != "ERROR":
                        continue
                    if level_text == "调试" and lvl.upper() != "DEBUG":
                        continue
                if event_text != "全部事件" and msg.get("event", "") != event_text:
                    continue
                if module_text != "全部模块" and msg.get("module", "") != module_text:
                    continue
                log_time = pd.to_datetime(ts)
                if log_time < start_dt or log_time > end_dt:
                    continue
                if search_text and search_text not in json.dumps(msg, ensure_ascii=False).lower():
                    continue
                color = {
                    "ERROR": "#FF0000",
                    "WARNING": "#FFA500",
                    "INFO": "#000000",
                    "DEBUG": "#808080"
                }.get(lvl.upper(), "#000000")
                html_logs.append(
                    f'<div style="text-align:left;color:{color};word-break:break-all;white-space:pre-wrap;width:100%;">[{ts}] [{lvl}] {json.dumps(msg, ensure_ascii=False)}</div>')
            else:
                # 未结构化日志
                if level_text != "全部":
                    if level_text == "信息" and lvl.upper() != "INFO":
                        continue
                    if level_text == "警告" and lvl.upper() != "WARNING":
                        continue
                    if level_text == "错误" and lvl.upper() != "ERROR":
                        continue
                    if level_text == "调试" and lvl.upper() != "DEBUG":
                        continue
                log_time = pd.to_datetime(ts)
                if log_time < start_dt or log_time > end_dt:
                    continue
                if search_text and search_text not in str(msg).lower():
                    continue
                color = {
                    "ERROR": "#FF0000",
                    "WARNING": "#FFA500",
                    "INFO": "#000000",
                    "DEBUG": "#808080"
                }.get(lvl.upper(), "#000000")
                html_logs.append(
                    f'<div style="text-align:left;color:{color};word-break:break-all;white-space:pre-wrap;width:100%;">[{ts}] [{lvl}] {msg}</div>')
        if not html_logs:
            html_logs = [
                '<div style="color:#888;text-align:center;margin-top:40px;">暂无日志内容</div>']
        scrollbar = self.log_text.verticalScrollBar()
        old_value = scrollbar.value()
        old_max = scrollbar.maximum()
        self._last_scroll_ratio = old_value / old_max if old_max > 0 else 1.0
        if self.log_text is not None:
            self.log_text.setHtml("".join(html_logs))
            if scroll_to_end or not self.pause_scroll:
                QTimer.singleShot(
                    0, lambda: self.log_text.moveCursor(QTextCursor.End))

    def refresh(self) -> None:
        """
        刷新日志控件内容，异常只记录日志不抛出。
        """
        try:
            self.refresh_display(scroll_to_end=True)
        except Exception as e:
            logger.error(f"刷新日志控件失败: {str(e)}")

    def update(self) -> None:
        """
        只做Qt刷新，不再递归调用refresh。
        """
        QWidget.update(self)

    def reload(self) -> None:
        """
        兼容旧接口，重定向到refresh。
        """
        self.refresh()

    def show_log_stats(self):
        """嵌入式日志统计图，支持交互"""
        logs = [l for l in self._all_logs if isinstance(l[0], dict)]
        if not logs:
            return
        df = pd.DataFrame(
            [dict(**d[0], level=d[1], timestamp=d[2]) for d in logs])
        dialog = QDialog(self)
        dialog.setWindowTitle("日志统计可视化")
        layout = QVBoxLayout(dialog)
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        fig = Figure(figsize=(8, 6))
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)
        ax1 = fig.add_subplot(221)
        ax2 = fig.add_subplot(222)
        ax3 = fig.add_subplot(212)
        # 事件分布
        if "event" in df:
            df["event"].value_counts().plot(kind="bar", ax=ax1, title="事件分布")
        # 级别分布
        if "level" in df:
            df["level"].value_counts().plot(
                kind="pie", ax=ax2, autopct="%1.1f%%", title="日志级别分布")
        # 时间趋势
        if "timestamp" in df:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp").resample(
                "min").size().plot(ax=ax3, title="日志时间趋势")
        fig.tight_layout()
        # 支持导出图片
        btn_export = QPushButton("导出统计图")

        def do_export():
            file_path, _ = QFileDialog.getSaveFileName(
                dialog, "导出统计图", "", "PNG Files (*.png)")
            if file_path:
                fig.savefig(file_path)
        btn_export.clicked.connect(do_export)
        layout.addWidget(btn_export)
        dialog.setLayout(layout)
        dialog.resize(900, 700)
        dialog.exec_()

def _get_popup_filtered_logs_html(self, level_combo, search_box):
    """获取弹窗中经过筛选的日志HTML内容"""
    # 获取筛选条件
    level_text = level_combo.currentText()
    search_text = search_box.text().strip().lower()

    # 筛选日志
    filtered_logs = []
    for msg, lvl, ts in self._all_logs:
        # 按级别筛选
        if level_text != "全部":
            if level_text == "信息" and lvl.upper() != "INFO":
                continue
            if level_text == "警告" and lvl.upper() != "WARNING":
                continue
            if level_text == "错误" and lvl.upper() != "ERROR":
                continue
            if level_text == "调试" and lvl.upper() != "DEBUG":
                continue

        # 按关键词搜索
        if search_text and search_text not in str(msg).lower():
            continue

        # 格式化日志
        color = self._get_level_color(lvl)
        if isinstance(msg, dict):
            formatted_msg = json.dumps(msg, ensure_ascii=False)
        else:
            formatted_msg = str(msg)

        html_log = f'<div style="color:{color};">[{ts}] [{lvl}] {formatted_msg}</div>'
        filtered_logs.append(html_log)

    # 返回HTML
    if not filtered_logs:
        return '<div style="color:#888;text-align:center;margin-top:40px;">暂无符合条件的日志</div>'
    return "".join(filtered_logs)

def refresh_popup(self):
    """刷新弹窗内容 - 线程安全版本"""
    if not hasattr(self, 'popup_dialog') or not self.popup_dialog or not hasattr(self, '_popup_log_text') or not self._popup_log_text:
        return

    # 获取HTML内容
    html_content = self.get_filtered_logs_html()

    # 使用信号/槽机制确保在主线程中更新UI
    QMetaObject.invokeMethod(
        self._popup_log_text,
        "setHtml",
        Qt.QueuedConnection,
        Q_ARG(str, html_content)
    )

    # 使用单次计时器在主线程中移动光标
    QTimer.singleShot(0, lambda: self._move_cursor_to_end(self._popup_log_text))

def _move_cursor_to_end(self, text_edit):
    """在主线程中安全地将光标移动到文本末尾"""
    if text_edit:
        cursor = text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        text_edit.setTextCursor(cursor)
