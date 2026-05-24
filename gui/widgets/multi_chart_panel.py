#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多屏幕图表面板

固定为多屏模式，提供多股票同时分析功能
"""

import sys
import traceback
from typing import List, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox,
    QFrame, QScrollArea
)
from PyQt5.QtCore import pyqtSignal
from loguru import logger

from gui.widgets.chart_widget import ChartWidget as ChartCanvas

class MultiChartPanel(QWidget):
    """
    多屏幕图表面板
    
    固定为多屏模式，提供多股票同时分析功能。
    支持网格布局（2x2, 2x3, 3x2, 3x3等），可同时显示多只股票的K线图。
    """

    # 信号定义
    chart_updated = pyqtSignal(str, dict)  # 股票代码, 图表数据
    mode_changed = pyqtSignal(bool)  # 模式变更信号（固定为多屏模式，始终为True）
    stock_selected = pyqtSignal(str)  # 选中的股票代码

    def __init__(self, parent=None):
        """
        初始化多屏幕图表面板

        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.logger = logger.bind(module=__name__)

        # 状态变量
        self.stock_list = []  # 股票列表
        self.data_manager = None  # 数据管理器
        self.current_indicators = []  # 当前指标

        # 图表组件
        self.chart_widgets = []  # 多屏图表网格 [[chart, chart], [chart, chart]]
        self.grid_size = (2, 2)  # 默认2x2网格

        # UI组件
        self.main_layout = None
        self.control_panel = None
        self.chart_container = None
        self.multi_container = None

        self.init_ui()
        self.setup_multi_mode()
        
        # 发出模式变更信号（固定为多屏模式）
        self.mode_changed.emit(True)

        self.logger.info("多屏幕图表面板初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        try:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(5, 5, 5, 5)
            self.main_layout.setSpacing(5)

            # 创建控制面板
            self.create_control_panel()

            # 创建图表容器
            self.create_chart_containers()

        except Exception as e:
            self.logger.error(f"初始化UI失败: {e}")
            self.logger.error(traceback.format_exc())

    def create_control_panel(self):
        """创建控制面板"""
        try:
            self.control_panel = QFrame()
            self.control_panel.setFrameStyle(QFrame.StyledPanel)

            layout = QHBoxLayout(self.control_panel)
            layout.setContentsMargins(10, 5, 10, 5)

            # 模式切换按钮已移除（仅支持多屏模式，无需切换）

            # 网格大小选择
            layout.addWidget(QLabel("网格大小:"))
            self.grid_combo = QComboBox()
            self.grid_combo.addItems(
                ["2x2", "2x3", "3x2", "3x3", "4x2", "2x4"])
            self.grid_combo.currentTextChanged.connect(
                self.on_grid_size_changed)
            layout.addWidget(self.grid_combo)

            # 自动填充按钮
            self.auto_fill_btn = QPushButton("自动填充")
            self.auto_fill_btn.clicked.connect(self.auto_fill_multi_charts)
            self.auto_fill_btn.setEnabled(True)  # 默认启用
            layout.addWidget(self.auto_fill_btn)

            # 清空按钮
            self.clear_btn = QPushButton("清空图表")
            self.clear_btn.clicked.connect(self.clear_all_charts)
            self.clear_btn.setEnabled(True)  # 默认启用
            layout.addWidget(self.clear_btn)

            layout.addStretch()

            # 状态标签（固定显示多屏模式）
            self.status_label = QLabel("多屏模式")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            layout.addWidget(self.status_label)

            self.main_layout.addWidget(self.control_panel)

        except Exception as e:
            self.logger.error(f"创建控制面板失败: {e}")

    def create_chart_containers(self):
        """创建图表容器"""
        try:
            # 创建主容器
            self.chart_container = QWidget()
            container_layout = QVBoxLayout(self.chart_container)
            container_layout.setContentsMargins(0, 0, 0, 0)

            # 多屏容器
            self.multi_container = QScrollArea()
            self.multi_container.setWidgetResizable(True)
            container_layout.addWidget(self.multi_container)

            self.main_layout.addWidget(self.chart_container)

        except Exception as e:
            self.logger.error(f"创建图表容器失败: {e}")

    def setup_multi_mode(self):
        """设置多屏模式"""
        try:
            # 解析网格大小
            rows, cols = self.parse_grid_size(self.grid_combo.currentText())
            self.grid_size = (rows, cols)

            # 创建多屏网格容器
            multi_widget = QWidget()
            grid_layout = QGridLayout(multi_widget)
            grid_layout.setSpacing(5)

            # 清空现有图表
            self.chart_widgets = []

            # 创建图表网格
            for row in range(rows):
                chart_row = []
                for col in range(cols):
                    chart = ChartCanvas(self)
                    chart.setMinimumSize(300, 200)
                    # 添加点击事件处理
                    chart.figure.canvas.mpl_connect('button_press_event',
                                                    lambda event, r=row, c=col: self._on_multi_chart_clicked(event, r, c))

                    # 添加图表标题
                    chart_frame = QFrame()
                    chart_frame.setFrameStyle(QFrame.StyledPanel)
                    frame_layout = QVBoxLayout(chart_frame)
                    frame_layout.setContentsMargins(2, 2, 2, 2)

                    # 标题栏
                    title_bar = QWidget()
                    title_layout = QHBoxLayout(title_bar)
                    title_layout.setContentsMargins(5, 2, 5, 2)

                    # 股票标题标签 - 现在只使用这个标签，不再使用下拉框
                    title_label = QLabel(f"图表 {row+1}-{col+1}")
                    title_label.setStyleSheet(
                        "font-weight: bold; color: #333;")
                    title_layout.addWidget(title_label)

                    # 添加拖拽提示
                    drag_hint = QLabel("← 拖拽股票到此处")
                    drag_hint.setStyleSheet("color: #999; font-style: italic;")
                    title_layout.addWidget(drag_hint)

                    title_layout.addStretch()

                    frame_layout.addWidget(title_bar)
                    frame_layout.addWidget(chart)

                    grid_layout.addWidget(chart_frame, row, col)

                    # 启用接收拖拽
                    chart.setAcceptDrops(True)
                    # 保存原始的拖拽事件处理方法
                    chart._original_dragEnterEvent = chart.dragEnterEvent
                    chart._original_dropEvent = chart.dropEvent
                    # 重写拖拽事件处理方法
                    chart.dragEnterEvent = lambda event, r=row, c=col: self._on_chart_drag_enter(event, r, c, chart)
                    chart.dropEvent = lambda event, r=row, c=col: self._on_chart_drop(event, r, c, chart)

                    chart_row.append({
                        'chart': chart,
                        'frame': chart_frame,
                        'title': title_label,
                        'drag_hint': drag_hint,
                        'stock_code': None
                    })

                self.chart_widgets.append(chart_row)

            # 设置到滚动区域
            self.multi_container.setWidget(multi_widget)

            self.logger.debug(f"多屏模式设置完成，网格大小: {rows}x{cols}")

        except Exception as e:
            self.logger.error(f"设置多屏模式失败: {e}")

    def _on_chart_drag_enter(self, event, row, col, chart):
        """处理图表拖拽进入事件"""
        try:
            # 检查是否包含股票代码
            if event.mimeData().hasText() or event.mimeData().hasFormat("application/x-stock-code"):
                event.acceptProposedAction()
            else:
                # 调用原始方法处理其他类型的拖拽
                if hasattr(chart, '_original_dragEnterEvent'):
                    chart._original_dragEnterEvent(event)
        except Exception as e:
            self.logger.error(f"处理图表拖拽进入事件失败: {e}")

    def _on_multi_chart_clicked(self, event, row, col):
        """处理多屏模式下的图表点击事件"""
        try:
            if row < len(self.chart_widgets) and col < len(self.chart_widgets[row]):
                chart_info = self.chart_widgets[row][col]
                if chart_info['stock_code']:
                    self.stock_selected.emit(chart_info['stock_code'])
        except Exception as e:
            self.logger.error(f"处理多屏图表点击事件失败: {e}")

    def _on_chart_drop(self, event, row, col, chart):
        """处理图表拖拽释放事件"""
        try:
            # 解析拖拽数据
            stock_code = None
            stock_name = ""

            # 尝试从自定义MIME类型获取
            if event.mimeData().hasFormat("application/x-stock-code"):
                stock_code = bytes(event.mimeData().data("application/x-stock-code")).decode("utf-8")
                if event.mimeData().hasFormat("application/x-stock-name"):
                    stock_name = bytes(event.mimeData().data("application/x-stock-name")).decode("utf-8")

            # 如果自定义MIME类型获取失败，尝试从文本获取
            if not stock_code and event.mimeData().hasText():
                text = event.mimeData().text().strip()
                parts = text.split()
                if parts:
                    stock_code = parts[0]
                    if len(parts) > 1:
                        stock_name = " ".join(parts[1:])

            if stock_code:
                chart_info = self.chart_widgets[row][col]

                # 更新图表标题，显示股票代码和名称
                if stock_name:
                    chart_info['title'].setText(f"{stock_code} {stock_name}")
                else:
                    chart_info['title'].setText(f"{stock_code}")

                # 隐藏拖拽提示
                if 'drag_hint' in chart_info:
                    chart_info['drag_hint'].setVisible(False)

                # 更新图表数据
                self.update_chart_data(row, col, stock_code)

                event.acceptProposedAction()
            else:
                # 调用原始方法处理其他类型的拖拽
                if hasattr(chart, '_original_dropEvent'):
                    chart._original_dropEvent(event)

        except Exception as e:
            self.logger.error(f"处理图表拖拽释放事件失败: {e}")
            if hasattr(chart, '_original_dropEvent'):
                chart._original_dropEvent(event)

    def on_grid_size_changed(self, grid_text: str):
        """网格大小改变事件"""
        try:
            self.setup_multi_mode()
            self.logger.debug(f"网格大小已更改为: {grid_text}")
        except Exception as e:
            self.logger.error(f"更改网格大小失败: {e}")

    def auto_fill_multi_charts(self):
        """自动填充多屏图表"""
        try:
            if not self.stock_list:
                return

            stock_index = 0
            for row in range(len(self.chart_widgets)):
                for col in range(len(self.chart_widgets[row])):
                    if stock_index < len(self.stock_list):
                        stock = self.stock_list[stock_index]
                        stock_code = stock.get('code', '')
                        stock_name = stock.get('name', '')

                        if stock_code:
                            chart_info = self.chart_widgets[row][col]

                            # 更新标题显示股票代码和名称
                            if stock_name:
                                chart_info['title'].setText(f"{stock_code} {stock_name}")
                            else:
                                chart_info['title'].setText(f"{stock_code}")

                            # 隐藏拖拽提示
                            if 'drag_hint' in chart_info:
                                chart_info['drag_hint'].setVisible(False)

                            # 更新图表数据
                            self.update_chart_data(row, col, stock_code)

                        stock_index += 1
                    else:
                        break

                if stock_index >= len(self.stock_list):
                    break

            self.logger.info("多屏图表自动填充完成")

        except Exception as e:
            self.logger.error(f"自动填充多屏图表失败: {e}")

    def clear_all_charts(self):
        """清空所有图表"""
        try:
            for row in range(len(self.chart_widgets)):
                for col in range(len(self.chart_widgets[row])):
                    chart_info = self.chart_widgets[row][col]
                    chart_info['chart'].clear()
                    chart_info['title'].setText(f"图表 {row+1}-{col+1}")
                    chart_info['stock_code'] = None

                    # 显示拖拽提示
                    if 'drag_hint' in chart_info:
                        chart_info['drag_hint'].setVisible(True)

            self.logger.info("所有图表已清空")

        except Exception as e:
            self.logger.error(f"清空图表失败: {e}")

    def set_stock_list(self, stock_list: List[Dict[str, Any]]):
        """设置股票列表"""
        try:
            self.stock_list = stock_list or []
            self.logger.debug(f"股票列表已更新，共 {len(self.stock_list)} 只股票")
        except Exception as e:
            self.logger.error(f"设置股票列表失败: {e}")

    def set_data_manager(self, data_manager):
        """设置数据管理器"""
        try:
            self.data_manager = data_manager
            self.logger.debug("数据管理器已设置")
        except Exception as e:
            self.logger.error(f"设置数据管理器失败: {e}")

    def set_indicators(self, indicators: List[Dict[str, Any]]):
        """设置技术指标"""
        try:
            self.current_indicators = indicators or []

            # 更新所有图表的指标
            for row in range(len(self.chart_widgets)):
                for col in range(len(self.chart_widgets[row])):
                    chart_info = self.chart_widgets[row][col]
                    if chart_info['stock_code']:
                        self.update_chart_data(
                            row, col, chart_info['stock_code'])

            self.logger.debug(f"技术指标已更新，共 {len(indicators)} 个指标")

        except Exception as e:
            self.logger.error(f"设置技术指标失败: {e}")

    def update_chart_data(self, row: int, col: int, stock_code: str):
        """更新指定图表的数据"""
        try:
            if not self.data_manager:
                self.logger.error("数据管理器未初始化，无法更新图表")
                return

            chart_info = self.chart_widgets[row][col]
            chart = chart_info['chart']

            # 获取K线数据
            kdata = self._get_kdata_from_manager(stock_code)
            if kdata is not None and not kdata.empty:
                # 保存股票代码到chart_info
                chart_info['stock_code'] = stock_code

                # 构建正确的数据格式传递给update_chart
                chart_data = {
                    'kdata': kdata,
                    'stock_code': stock_code
                }

                # 添加指标数据（如果有）
                if self.current_indicators:
                    chart_data['indicators'] = self.current_indicators

                # 更新图表
                self.logger.info(f"更新图表 [{row}][{col}] 股票代码: {stock_code}, 数据行数: {len(kdata)}")
                chart.update_chart(chart_data)
                self.chart_updated.emit(stock_code, {'kdata': kdata})
            else:
                self.logger.warning(f"获取股票 {stock_code} 的K线数据失败或数据为空")
                chart_info['title'].setText(f"{stock_code} (无数据)")

        except Exception as e:
            self.logger.error(f"更新图表数据失败: {e}", exc_info=True)

    def _get_kdata_from_manager(self, stock_code: str):
        """从数据管理器获取K线数据，适配不同类型的数据管理器"""
        try:
            # 检查数据管理器类型
            manager_type = self.data_manager.__class__.__name__
            self.logger.info(f"数据管理器类型: {manager_type}")

            # 如果是UnifiedDataManager
            if manager_type == 'UnifiedDataManager':
                # 尝试从服务容器中获取StockService
                from core.containers import get_service_container
                from core.services.stock_service import StockService

                container = get_service_container()
                if container:
                    stock_service = container.resolve(StockService)
                    if stock_service:
                        return stock_service.get_stock_data(stock_code, 'D', 365)

                self.logger.warning("无法从UnifiedDataManager获取数据，尝试其他方法")
                return None

            # 如果数据管理器有get_kdata方法
            elif hasattr(self.data_manager, 'get_kdata'):
                return self.data_manager.get_kdata(stock_code)

            # 如果数据管理器有get_stock_data方法
            elif hasattr(self.data_manager, 'get_stock_data'):
                # 注意：这个方法可能是异步的，这里简单处理
                import asyncio
                try:
                    # 尝试使用同步方式调用异步方法
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(self.data_manager.get_stock_data(stock_code, 'D'))
                except Exception:
                    # 如果失败，尝试直接调用（可能不是异步方法）
                    return self.data_manager.get_stock_data(stock_code, 'D')

            self.logger.error(f"数据管理器 {manager_type} 没有可用的获取K线数据的方法")
            return None

        except Exception as e:
            self.logger.error(f"从数据管理器获取K线数据失败: {e}", exc_info=True)
            return None

    def parse_grid_size(self, grid_text: str) -> tuple:
        """解析网格大小文本"""
        try:
            parts = grid_text.split('x')
            if len(parts) == 2:
                rows = int(parts[0])
                cols = int(parts[1])
                return (rows, cols)
            else:
                return (2, 2)  # 默认值
        except Exception:
            return (2, 2)

    def get_current_chart(self):
        """获取当前活动的图表"""
        for row in range(len(self.chart_widgets)):
            for col in range(len(self.chart_widgets[row])):
                chart_info = self.chart_widgets[row][col]
                if chart_info['stock_code']:
                    return chart_info['chart']
        return None

    def broadcast_data(self, data: Dict[str, Any]):
        """广播数据到所有图表"""
        try:
            for row in range(len(self.chart_widgets)):
                for col in range(len(self.chart_widgets[row])):
                    chart = self.chart_widgets[row][col]['chart']
                    if hasattr(chart, 'update_data'):
                        chart.update_data(data)

        except Exception as e:
            self.logger.error(f"广播数据失败: {e}")

    def load_stock_data(self, stock_code: str, stock_name: str = '', chart_data: Dict[str, Any] = None):
        """
        加载股票数据到图表

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            chart_data: 图表数据
        """
        try:
            if not chart_data:
                self.logger.warning(f"没有提供图表数据: {stock_code}")
                return

            # 加载到第一个图表
            if self.chart_widgets and len(self.chart_widgets) > 0 and len(self.chart_widgets[0]) > 0:
                chart = self.chart_widgets[0][0]['chart']
                if chart and hasattr(chart, 'update_chart'):
                    chart.update_chart(chart_data)
                elif chart and hasattr(chart, 'update_chart_data'):
                    chart.update_chart_data(chart_data)

            self.logger.info(f"成功加载股票数据: {stock_code} - {stock_name}")

        except Exception as e:
            self.logger.error(f"加载股票数据失败: {e}")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    # 测试窗口
    window = QMainWindow()
    window.setWindowTitle("多屏幕图表面板测试")
    window.setGeometry(100, 100, 1200, 800)

    # 创建面板
    panel = MultiChartPanel()
    window.setCentralWidget(panel)

    # 设置测试数据
    test_stocks = [
        {"code": "000001", "name": "平安银行"},
        {"code": "000002", "name": "万科A"},
        {"code": "600000", "name": "浦发银行"},
        {"code": "600036", "name": "招商银行"},
    ]
    panel.set_stock_list(test_stocks)

    window.show()
    sys.exit(app.exec_())
