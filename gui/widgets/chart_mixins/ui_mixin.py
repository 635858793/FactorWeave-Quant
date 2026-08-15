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
from PyQt5.QtCore import QTimer, Qt
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
            self._create_region_indicator_menu_btn()  # R283: 第二指标区"指标▼"菜单按钮

        except Exception as e:
            logger.error(f"初始化UI失败: {str(e)}")

    # ---- R283: 指标区指标列表展开（左上角"指标 ▼"按钮，显示当前指标名）----
    # 目标：省出左侧面板的指标窗口做其他功能。按钮作为 overlay 子控件叠加在
    # matplotlib canvas 上（不进入布局，避免破坏 GridSpec 3 轴布局），点击弹出
    # QMenu 指标列表，选择后经 region_indicator_selected 信号交给 middle_panel
    # 更新 indicator1_combo，复用既有"下拉框 → on_indicator_selected"渲染链路。
    def _create_region_indicator_menu_btn(self):
        """创建指标区"指标 ▼"按钮（overlay 子控件，不进入布局）

        R283+: 固定高度 12px（约为原高度一半），定位由 _sync_region_indicator_btn_pos
        负责（中间面板/图表左下角），点击弹出可多选的指标列表菜单。
        """
        try:
            from PyQt5.QtWidgets import QToolButton
            btn = QToolButton(self)
            btn.setText("指标 ▼")
            btn.setToolTip("展开指标列表（可多选）")
            btn.setAutoRaise(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(12)  # R283+: 高度减半（原约 20px+，现 12px）
            # R283+ 修复：绿色高亮便于识别；clicked 信号携带 checked(bool) 参数，
            # 直接连接会把 False 当作 pos 传入 exec_ 抛异常（菜单从未弹出的根因），
            # 必须用 lambda 丢弃该参数。
            btn.setStyleSheet(
                "QToolButton { background: #27ae60; color: white; border: 1px solid #1e8449;"
                " border-radius: 2px; padding: 0px 4px; font-size: 8px; font-weight: bold; }"
                "QToolButton:hover { background: #2ecc71; }")
            btn.clicked.connect(
                lambda checked=False: self._show_region_indicator_menu())
            btn.hide()
            self._region_indicator_menu_btn = btn
        except Exception as e:
            logger.error(f"创建指标菜单按钮失败: {e}")
            self._region_indicator_menu_btn = None

    def set_region_indicator_names(self, names: list):
        """middle_panel 注入可用指标名称列表（含'无'），供菜单展开使用"""
        self._region_indicator_names = list(names or [])

    def _load_region_indicator_names(self) -> list:
        """获取指标菜单名称列表（含'无'）

        R283+: 优先使用 middle_panel 注入列表；注入缺失/为空时兜底从
        BUILTIN_INDICATORS + get_talib_real_indicator_list 拉取——与左侧
        技术面板技术列表同源（left_panel._init_indicators 同一数据源），
        保证"指标 ▼"菜单在无注入场景下仍有完整技术指标列表。
        """
        names = list(getattr(self, '_region_indicator_names', []) or [])
        if not names or names == ['无']:
            try:
                from core.indicators.indicators_algorithm import (
                    get_talib_real_indicator_list, BUILTIN_INDICATORS)
                seen = set()
                merged = []
                for n in list(BUILTIN_INDICATORS) + list(get_talib_real_indicator_list()):
                    if n and n not in seen:
                        seen.add(n)
                        merged.append(n)
                names = ['无'] + merged
            except Exception as e:
                logger.warning(f"兜底拉取指标列表失败: {e}")
                names = ['无']
        return names

    def _sync_region_indicator_btn_pos(self):
        """将"指标 ▼"按钮定位到中间面板（图表 canvas）左下角，
        并同步按钮文字为当前指标1区指标名（多选逗号分隔）"""
        btn = getattr(self, '_region_indicator_menu_btn', None)
        if btn is None:
            return
        try:
            if not hasattr(self, 'canvas'):
                return
            # R283: 按钮文字显示当前指标名（从 active_indicators 收集 indicator1 区）
            names = [ind.get('name') for ind in getattr(self, 'active_indicators', []) or []
                     if ind.get('name') and ind.get('region', 'indicator1') == 'indicator1']
            label = '指标 ▼' + (('  ' + ', '.join(names)) if names else '')
            btn.setText(label)
            # R283+: 左下角——canvas 底部左边缘内侧（原为 indicator_ax 左上角）
            canvas_origin = self.canvas.mapTo(self, self.canvas.pos())
            btn.move(int(canvas_origin.x() + 4),
                     int(canvas_origin.y() + self.canvas.height() - btn.height() - 4))
            btn.show()
            btn.raise_()
        except Exception as e:
            logger.debug(f"同步指标菜单按钮位置失败: {e}")

    def _show_region_indicator_menu(self, pos=None):
        """弹出指标列表菜单（R283+: 6 列网格多选）

        菜单内嵌 QTableWidget（6 列，与左侧技术面板 indicator_list 网格布局一致），
        每格为可勾选指标（初始勾选当前指标1区已选指标）；菜单关闭（点击
        "确定"或菜单外）即提交勾选集合：
        - 勾选集合为空 → 清空指标区
        - 勾选 ≥1 项 → 批量渲染所选指标

        Args:
            pos: 可选，菜单弹出的全局坐标（右键场景传鼠标位置）；缺省时用按钮左下角
        """
        try:
            from PyQt5.QtCore import Qt
            from PyQt5.QtWidgets import (
                QMenu, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                QTableWidgetItem, QPushButton, QAbstractItemView,
                QWidgetAction)
            btn = getattr(self, '_region_indicator_menu_btn', None)
            names = self._load_region_indicator_names()
            current = set(ind.get('name') for ind in getattr(self, 'active_indicators', []) or []
                          if ind.get('name') and ind.get('region', 'indicator1') == 'indicator1')

            menu = QMenu(self)
            menu.setTitle("指标列表（可多选）")

            cols = 6  # R283+: 单列 → 6 列网格展示
            items = [n for n in names if n != '无']  # "无"=全不选，以空勾选表达
            rows = (len(items) + cols - 1) // cols

            table = QTableWidget(rows, cols)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setVisible(False)
            table.setShowGrid(True)
            table.setSelectionMode(QAbstractItemView.NoSelection)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.verticalHeader().setDefaultSectionSize(22)
            table.setFixedWidth(cols * 64 + 22)  # 列宽 64 + 滚动条/边框余量
            # 最多展示 8 行（超出滚动），防止菜单过高
            table.setFixedHeight(min(rows, 8) * 22 + 4)

            for i, name in enumerate(items):
                row, col = divmod(i, cols)
                item = QTableWidgetItem(name)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if name in current else Qt.Unchecked)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, col, item)

            # 表格 + 确定按钮包进 QWidgetAction（QMenu 内嵌控件）
            widget = QWidget()
            lay = QVBoxLayout(widget)
            lay.setContentsMargins(6, 6, 6, 6)
            lay.setSpacing(4)
            lay.addWidget(table)
            bottom = QHBoxLayout()
            bottom.addStretch(1)
            ok_btn = QPushButton("确定")
            ok_btn.setFixedWidth(56)
            bottom.addWidget(ok_btn)
            lay.addLayout(bottom)

            action = QWidgetAction(menu)
            action.setDefaultWidget(widget)
            menu.addAction(action)

            # 菜单关闭（hide）时收集勾选——此刻 table 仍存活（menu 未析构）
            selected: list = []

            def _collect_on_hide():
                for i, name in enumerate(items):
                    row, col = divmod(i, cols)
                    it = table.item(row, col)
                    if it is not None and it.checkState() == Qt.Checked:
                        selected.append(name)

            menu.aboutToHide.connect(_collect_on_hide)
            ok_btn.clicked.connect(menu.close)

            if pos is not None:
                menu.exec_(pos)
            elif btn is not None:
                menu.exec_(btn.mapToGlobal(btn.rect().bottomLeft()))
            else:
                menu.exec_()

            self._on_region_indicator_picked(selected)
        except Exception as e:
            logger.error(f"展开指标菜单失败: {e}")

    def _on_region_indicator_picked(self, names):
        """用户从菜单多选指标 → 通知 middle_panel（R283+: 携带名称列表）"""
        if isinstance(names, str):
            names = [names]
        if hasattr(self, 'region_indicator_selected'):
            self.region_indicator_selected.emit('indicator1', list(names))

    def _init_figure_layout(self):
        """初始化图表布局（R283: 移除 indicator_ax2 第二指标窗，收敛为 K线/交易量/指标 3 轴）"""
        try:
            self.figure = Figure(figsize=(15, 8), dpi=100,
                                 constrained_layout=False)
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.gs = self.figure.add_gridspec(3, 1, height_ratios=[4, 1, 1])
            self.price_ax = self.figure.add_subplot(self.gs[0])
            self.volume_ax = self.figure.add_subplot(
                self.gs[1], sharex=self.price_ax)
            self.indicator_ax = self.figure.add_subplot(
                self.gs[2], sharex=self.price_ax)
            # 只保留最后一个指标区(indicator_ax)的X轴刻度和标签
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
        # 所有子图显示网格/Y轴刻度（R283: 收敛为 3 轴）
        for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
            if ax is None:
                continue
            ax.grid(True, linestyle='--', alpha=0.5)  # 始终显示网格
            ax.tick_params(axis='y', which='major',
                           labelsize=8, labelleft=True)  # Y轴刻度
            for label in (ax.get_yticklabels()):
                label.set_fontsize(8)
            ax.title.set_fontsize(8)
            ax.xaxis.label.set_fontsize(8)
            ax.yaxis.label.set_fontsize(8)
        # 指标窗显示X轴日期刻度（4轴改3轴后 X轴显示权从 indicator_ax2 移交 indicator_ax）
        if getattr(self, 'indicator_ax', None):
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

            # 重新创建子图布局（R283: 收敛为 3 轴）
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

            # 重新创建子图布局（R283: 收敛为 3 轴）
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
            # R283: 窗口尺寸变化后重定位"指标▼"按钮
            if hasattr(self, '_sync_region_indicator_btn_pos'):
                self._sync_region_indicator_btn_pos()
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
