"""
现代化性能图表组件

参考专业交易软件设计的图表组件
"""

from collections import defaultdict
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

# 延迟导入logger，避免在模块级别导入时触发性能监控
logger = None

def _get_logger():
    """延迟导入logger"""
    global logger
    if logger is None:
        from loguru import logger as _logger
        logger = _logger
    return logger

# 延迟导入matplotlib，避免在模块级别导入时崩溃
MATPLOTLIB_AVAILABLE = False
matplotlib = None
plt = None
FigureCanvas = None
Figure = None
np = None

def _import_matplotlib():
    """延迟导入matplotlib"""
    global MATPLOTLIB_AVAILABLE, matplotlib, plt, FigureCanvas, Figure, np
    
    if not MATPLOTLIB_AVAILABLE:
        try:
            import matplotlib
            # 检查是否已有 QApplication 实例
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is None:
                # 如果没有 QApplication，使用 Agg 后端
                matplotlib.use('Agg')
                from matplotlib.backends.backend_agg import FigureCanvasAgg as _FigureCanvas
            else:
                # 如果已有 QApplication，使用 Qt5Agg 后端
                matplotlib.use('Qt5Agg')
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as _FigureCanvas
            
            import matplotlib.pyplot as plt
            from matplotlib.figure import Figure
            import numpy as np
            
            FigureCanvas = _FigureCanvas
            MATPLOTLIB_AVAILABLE = True
            _get_logger().info("matplotlib导入成功")
        except Exception as e:
            _get_logger().error(f"matplotlib导入失败: {e}")
            MATPLOTLIB_AVAILABLE = False

class ModernPerformanceChart(QWidget):
    """现代化性能图表组件 - 参考专业交易软件"""

    def __init__(self, title: str = "性能图表", chart_type: str = "line"):
        super().__init__()
        self.title = title
        self.chart_type = chart_type
        self.data_history = defaultdict(list)
        self.max_points = 100
        self._update_pending = False  # 防止频繁更新
        self._last_update_time = 0
        self.init_ui()

    def init_ui(self):
        # 延迟导入matplotlib
        _import_matplotlib()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 标题栏
        header = QHBoxLayout()

        title_label = QLabel(self.title)
        title_label.setMaximumHeight(25)
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #11f0f1; font-weight: bold; margin-bottom: 8px;")

        header.addWidget(title_label)
        header.addStretch()

        layout.addLayout(header)

        if MATPLOTLIB_AVAILABLE:
            # 专业图表样式
            self.figure = Figure(figsize=(8, 4), facecolor='#1e1e1e')
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111, facecolor='#1e1e1e')

            # 设置专业样式
            self.ax.spines['top'].set_visible(False)
            self.ax.spines['right'].set_visible(False)
            self.ax.spines['bottom'].set_color('#404040')
            self.ax.spines['left'].set_color('#404040')
            self.ax.grid(True, alpha=0.2, color='#404040', linewidth=0.5)

            layout.addWidget(self.canvas)
        else:
            placeholder = QLabel("图表需要matplotlib支持")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #7f8c8d; font-style: italic;")
            layout.addWidget(placeholder)

    def add_data_point(self, series_name: str, value: float):
        """添加数据点"""
        if not MATPLOTLIB_AVAILABLE:
            return

        self.data_history[series_name].append(value)
        if len(self.data_history[series_name]) > self.max_points:
            self.data_history[series_name].pop(0)

    def update_chart(self):
        """更新图表 - 专业交易软件风格（R267 blit：line 分支局部重绘，bar 分支保留全量）"""
        # 确保matplotlib和numpy已导入
        _import_matplotlib()
        
        if not MATPLOTLIB_AVAILABLE or not self.data_history:
            return

        # 限制更新频率，避免频繁重绘
        import time
        current_time = time.time()
        if current_time - self._last_update_time < 1.0:  # 1秒内只更新一次
            if not self._update_pending:
                self._update_pending = True
                QTimer.singleShot(1000, self._delayed_update)
            return

        self._last_update_time = current_time
        self._update_pending = False

        # R267 blit：惰性初始化局部重绘引擎（避免顶部硬依赖 matplotlib）
        if not hasattr(self, '_blit'):
            from core.utils.mpl_blit import BlitEngine
            self._blit = BlitEngine(self.canvas, bbox_getter=lambda: self.ax.bbox,
                                    log_tag='[PerfChart]')
            self._line_artists = None  # None=需全量重建
            self._line_sig = None      # (系列数) 结构签名

        # 专业色彩方案
        colors = ['#3498db', '#e74c3c', '#f39c12', '#27ae60', '#9b59b6', '#1abc9c']

        if self.chart_type == "line":
            self._update_chart_line_blit(colors)
        else:
            self._update_chart_bar_full(colors)

    def _update_chart_line_blit(self, colors):
        """line 分支：blit 增量更新（结构不变仅 set_data，结构变化重建背景）"""
        series_snapshot = [(name, data) for name, data in self.data_history.items() if data]
        if not series_snapshot:
            self._line_artists = None
            self._line_sig = None
            self._blit.invalidate()
            return

        # R267-c A1-fix：签名仅含系列数（不含数据长度）。
        # 数据长度增长（累积期 len<max_points）由 set_data 增量处理，
        # 若把长度纳入签名，累积期每帧签名变化 → 每帧 _rebuild_line_artists
        # 全量重建（plot+annotate+scatter+legend+tight_layout+invalidate），
        # 使 A1 的 xlim 固定与增量路径在累积期完全失效。
        # 仅系列增减（annotate/scatter 数量变化）才需全量重建。
        new_sig = (len(series_snapshot),)
        needs_rebuild = (self._line_artists is None or self._line_sig != new_sig)

        if needs_rebuild:
            self._rebuild_line_artists(series_snapshot, colors, new_sig)
        else:
            self._update_line_artists(series_snapshot, colors)

    def _rebuild_line_artists(self, series_snapshot, colors, new_sig):
        """全量重建 line 动态层（系列增减/长度变化时触发）"""
        if self._line_artists:
            for artist in self._line_artists:
                try:
                    artist.remove()
                except Exception as e:
                    _get_logger().debug(f"performance_chart: {e}")

        artists = []
        for i, (series_name, data) in enumerate(series_snapshot):
            color = colors[i % len(colors)]
            artists.append(self.ax.plot(data, label=series_name, color=color,
                                        linewidth=0.5, alpha=0.8)[0])
            latest_value = data[-1]
            unit = self._get_value_unit(series_name, latest_value)
            artists.append(self.ax.annotate(
                f"{latest_value:.1f}{unit}",
                xy=(len(data) - 1, latest_value),
                xytext=(8, 8), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.7),
                color='white', fontsize=8, fontweight='bold',
                ha='left', va='bottom'))
            artists.append(self.ax.scatter([len(data) - 1], [latest_value],
                                           color=color, s=40, zorder=5, alpha=0.9))

        # 图例（文本颜色与线条颜色一致）
        if len(series_snapshot) > 1:
            legend = self.ax.legend(frameon=False, loc='upper left',
                                    fontsize=8, fancybox=False, shadow=False)
            for i, (series_name, _) in enumerate(series_snapshot):
                color = colors[i % len(colors)]
                legend.get_texts()[i].set_color(color)
            artists.append(legend)

        self.ax.set_facecolor('#1e1e1e')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color('#404040')
        self.ax.spines['left'].set_color('#404040')
        self.ax.grid(True, alpha=0.2, color='#404040', linewidth=0.5)
        self.ax.tick_params(colors='#cccccc', labelsize=8)
        self.ax.margins(x=0.02, y=0.1)
        # R267-c A1：固定 xlim 为滑动窗口 (0, max_points)。
        # 消除数据累积期（len<max_points）xlim 每帧右移导致的 blit 背景失效
        # （原 autoscale 下每帧 invalidate → 全画布重建，blit 形同虚设）。
        # 满窗后 add_data_point 裁剪至 max_points，窗口恒为最新 max_points 个点。
        self.ax.set_xlim(0, self.max_points)
        self.figure.tight_layout()

        self._line_artists = artists
        self._line_sig = new_sig
        # 重建后强制重算背景（背景包含新 artist 与刻度）
        self._blit.invalidate()
        self._blit.render(artists)

    def _update_line_artists(self, series_snapshot, colors):
        """增量更新 line 动态层（仅 set_data/set_text/set_offsets，blit 局部重绘）"""
        idx = 0
        artists = self._line_artists
        for i, (series_name, data) in enumerate(series_snapshot):
            color = colors[i % len(colors)]
            line = artists[idx]
            line.set_data(np.arange(len(data)), data)
            idx += 1
            annotate = artists[idx]
            idx += 1
            latest_value = data[-1]
            unit = self._get_value_unit(series_name, latest_value)
            annotate.set_text(f"{latest_value:.1f}{unit}")
            annotate.xy = (len(data) - 1, latest_value)
            scatter = artists[idx]
            idx += 1
            scatter.set_offsets([[len(data) - 1, latest_value]])

        # R267-c A1：xlim 固定滑动窗口 (0, max_points)，仅 ylim 变化才重建背景。
        # 数据累积期 xlim 不再右移 → 不再每帧 invalidate 全画布重建，blit 全程生效。
        old_ylim = self.ax.get_ylim()
        self.ax.relim()
        self.ax.autoscale_view()
        self.ax.set_xlim(0, self.max_points)
        if old_ylim != self.ax.get_ylim():
            self._blit.invalidate()
        self._blit.render(artists)

    def _update_chart_bar_full(self, colors):
        """bar 分支：保留原全量重建逻辑（低频，blit 收益小不强行接入）"""
        self.ax.clear()

        for i, (series_name, data) in enumerate(self.data_history.items()):
            if not data:
                continue

            color = colors[i % len(colors)]
            x_pos = np.arange(len(data))
            self.ax.bar(x_pos, data, label=series_name, color=color, alpha=0.7)

            if data:
                latest_value = data[-1]
                unit = self._get_value_unit(series_name, latest_value)
                value_text = f"{latest_value:.1f}{unit}"
                last_x = len(data) - 1
                self.ax.text(last_x, latest_value + max(data) * 0.02, value_text,
                             ha='center', va='bottom', color=color,
                             fontsize=8, fontweight='bold',
                             bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

        self.ax.set_facecolor('#1e1e1e')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color('#404040')
        self.ax.spines['left'].set_color('#404040')
        self.ax.grid(True, alpha=0.2, color='#404040', linewidth=0.5)

        if len(self.data_history) > 1:
            legend = self.ax.legend(frameon=False, loc='upper left',
                                    fontsize=8, fancybox=False, shadow=False)
            for i, (series_name, _) in enumerate(self.data_history.items()):
                color = colors[i % len(colors)]
                legend.get_texts()[i].set_color(color)

        self.ax.tick_params(colors='#cccccc', labelsize=8)
        self.ax.margins(x=0.02, y=0.1)

        self.figure.tight_layout()
        self.canvas.draw()

    def _get_value_unit(self, series_name: str, value: float) -> str:
        """根据序列名称和数值确定单位"""
        # 百分比指标
        if any(keyword in series_name for keyword in ['率', '收益', '回撤', '波动', '误差']):
            return '%'

        # 时间指标
        elif any(keyword in series_name for keyword in ['时间', '延迟']):
            if value < 1000:
                return 'ms'
            else:
                return 's'

        # 频率指标
        elif any(keyword in series_name for keyword in ['帧率', '频率']):
            return 'fps' if '帧率' in series_name else 'Hz'

        # 次数指标
        elif any(keyword in series_name for keyword in ['次数', '连续', '获利']):
            return '次'

        # 吞吐量指标
        elif '吞吐量' in series_name:
            return 'ops/s'

        # 默认无单位（比率类指标）
        else:
            return ''

    def _delayed_update(self):
        """延迟更新图表"""
        if self._update_pending:
            self._update_pending = False
            self.update_chart()

    def clear_data(self):
        """清空图表数据"""
        self.data_history.clear()
        if MATPLOTLIB_AVAILABLE:
            self.ax.clear()
            # R267 blit：清空后背景失效、动态 artist 引用作废，下次 update_chart 自动重建
            if hasattr(self, '_blit'):
                self._blit.invalidate()
                self._line_artists = None
                self._line_sig = None
            self.canvas.draw()

    def cleanup(self):
        """清理资源"""
        try:
            # 清空数据
            self.data_history.clear()
            
            # 清理matplotlib资源
            if MATPLOTLIB_AVAILABLE:
                if hasattr(self, 'ax'):
                    self.ax.clear()
                if hasattr(self, 'figure'):
                    import matplotlib.pyplot as plt
                    plt.close(self.figure)
                if hasattr(self, 'canvas'):
                    self.canvas.close()
            
            # 清理布局
            if self.layout():
                while self.layout().count():
                    item = self.layout().takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                    elif item.layout():
                        while item.layout().count():
                            sub_item = item.layout().takeAt(0)
                            if sub_item.widget():
                                sub_item.widget().deleteLater()
            
            _get_logger().debug("ModernPerformanceChart cleanup completed")
            
        except Exception as e:
            _get_logger().error(f"清理资源失败: {e}")
