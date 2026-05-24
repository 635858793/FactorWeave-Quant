from loguru import logger
"""
图表控件UI功能Mixin

该模块包含ChartWidget的UI相关功能，包括：
- UI初始化和布局管理
- 图表布局初始化
- 显示优化
- 无数据状态显示
"""

import traceback
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QVBoxLayout, QLabel
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class UIMixin:
    """UI功能Mixin

    包含ChartWidget的UI初始化、布局管理等功能
    """

    def init_ui(self):
        """初始化UI，移除十字光标按钮，默认开启十字光标。主图类型下拉框由主窗口统一管理，不在ChartWidget中定义。"""
        try:
            # 先设置主布局，确保self.layout()不为None
            if self.layout() is None:
                layout = QVBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                self.setLayout(layout)
            else:
                layout = self.layout()
            # 图表区
            self._init_figure_layout()
            # 移除底部指标栏（indicator_bar）相关代码
            # self.indicator_bar = None
            # layout.addWidget(self.indicator_bar)
            self._init_zoom_interaction()  # 新增：自定义缩放交互
            self._optimize_display()  # 保证初始化后也显示网格和刻度

        except Exception as e:
            logger.error(f"初始化UI失败: {str(e)}")

    def _init_figure_layout(self):
        """初始化图表布局"""
        try:
            self.figure = Figure(figsize=(15, 8), dpi=100,
                                 constrained_layout=False)
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.gs = self.figure.add_gridspec(3, 1, height_ratios=[3, 1, 1])
            self.price_ax = self.figure.add_subplot(self.gs[0])
            self.volume_ax = self.figure.add_subplot(
                self.gs[1], sharex=self.price_ax)
            self.indicator_ax = self.figure.add_subplot(
                self.gs[2], sharex=self.price_ax)
            # 只保留indicator_ax的X轴刻度和标签
            self.price_ax.set_xticklabels([])
            self.price_ax.tick_params(
                axis='x', which='both', bottom=False, top=False, labelbottom=False)
            self.volume_ax.set_xticklabels([])
            self.volume_ax.tick_params(
                axis='x', which='both', bottom=False, top=False, labelbottom=False)
            # indicator_ax保留X轴
            self.figure.subplots_adjust(
                left=0.05, right=0.98, top=0.98, bottom=0.06, hspace=0.03)
            # 修正：只有在self.layout()存在时才addWidget
            if self.layout() is not None:
                self.layout().addWidget(self.canvas)
            self._optimize_display()  # 保证布局初始化后也显示网格和刻度
        except Exception as e:
            logger.error(f"初始化图表布局失败: {str(e)}")

    def _optimize_display(self):
        """优化显示效果，所有坐标轴字体统一为8号，始终显示网格和XY轴刻度（任何操作都不隐藏）"""
        # 只优化indicator_ax的X轴刻度，其他子图不显示X轴
        for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
            ax.grid(True, linestyle='--', alpha=0.5)  # 始终显示网格
            ax.tick_params(axis='y', which='major',
                           labelsize=8, labelleft=True)  # Y轴刻度
            for label in (ax.get_yticklabels()):
                label.set_fontsize(8)
            ax.title.set_fontsize(8)
            ax.xaxis.label.set_fontsize(8)
            ax.yaxis.label.set_fontsize(8)
        # 只设置indicator_ax的X轴刻度样式
        self.indicator_ax.tick_params(
            axis='x', which='major', labelsize=7, labelbottom=True)
        for label in self.indicator_ax.get_xticklabels():
            label.set_fontsize(8)

    def show_no_data(self, message: str = "无数据"):
        """显示无数据状态

        Args:
            message: 显示的消息文本
        """
        try:
            # 清除现有图表
            if hasattr(self, 'figure'):
                self.figure.clear()

            # 重新创建子图布局
            self.price_ax = self.figure.add_subplot(311)
            self.volume_ax = self.figure.add_subplot(312)
            self.indicator_ax = self.figure.add_subplot(313)

            ax = self.price_ax
            ax.text(0.5, 0.5, message,
                    horizontalalignment='center',
                    verticalalignment='center',
                    transform=ax.transAxes,
                    fontsize=16,
                    color='gray')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            self.volume_ax.axis('off')
            self.indicator_ax.axis('off')

            # 更新画布
            if hasattr(self, 'canvas'):
                self.canvas.draw()

        except Exception as e:
            logger.error(f"显示无数据状态失败: {str(e)}")

    def show_message(self, message: str, color: str = 'gray', fontsize: int = 16):
        """显示消息状态

        Args:
            message: 显示的消息文本
            color: 文字颜色
            fontsize: 字体大小
        """
        try:
            # 清除现有图表
            if hasattr(self, 'figure'):
                self.figure.clear()

            # 重新创建子图布局
            self.price_ax = self.figure.add_subplot(311)
            self.volume_ax = self.figure.add_subplot(312)
            self.indicator_ax = self.figure.add_subplot(313)

            ax = self.price_ax
            ax.text(0.5, 0.5, message,
                    horizontalalignment='center',
                    verticalalignment='center',
                    transform=ax.transAxes,
                    fontsize=fontsize,
                    color=color)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            self.volume_ax.axis('off')
            self.indicator_ax.axis('off')

            # 更新画布
            if hasattr(self, 'canvas'):
                self.canvas.draw()

        except Exception as e:
            logger.error(f"显示消息状态失败: {str(e)}")

    def show_error(self, error_message: str):
        """显示错误消息

        Args:
            error_message: 错误消息文本
        """
        self.show_message(f"错误: {error_message}", color='red', fontsize=14)

    def show_loading(self, message: str = "正在加载..."):
        """显示加载消息

        Args:
            message: 加载消息文本
        """
        self.show_message(message, color='blue', fontsize=14)

    def resizeEvent(self, event):
        """窗口大小变化事件处理"""
        try:
            # 直接调用QWidget的resizeEvent，避免super()调用问题
            from PyQt5.QtWidgets import QWidget
            QWidget.resizeEvent(self, event)

            # 可以在这里添加窗口大小变化时的特殊处理
            if hasattr(self, 'canvas'):
                self.canvas.draw_idle()
        except Exception as e:
            logger.error(f"处理窗口大小变化失败: {str(e)}")

    def draw_overview(self, ax, kdata):
        """绘制概览图

        Args:
            ax: matplotlib轴对象
            kdata: K线数据
        """
        try:
            if kdata is None or kdata.empty:
                return

            # 绘制简化的价格线
            ax.plot(kdata.index, kdata['close'], linewidth=1, alpha=0.7)
            ax.set_title("概览", fontsize=8)
            ax.tick_params(labelsize=6)

        except Exception as e:
            logger.error(f"绘制概览图失败: {str(e)}")
