"""
缩放功能Mixin - 处理图表缩放、拖拽、平移等交互功能
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
from PyQt5.QtCore import QTimer

class ZoomMixin:
    """缩放功能Mixin"""

    def _init_zoom_interaction(self):
        """自定义鼠标缩放交互，支持多级缩放、右键还原、滚轮缩放，优化流畅性"""
        self._zoom_press_x = None
        self._zoom_rect = None
        self._zoom_history = []  # 多级缩放历史
        self._last_motion_time = 0
        self._motion_interval_ms = 100  # 约60fps
        self.canvas.mpl_connect('button_press_event', self._on_zoom_press)
        self.canvas.mpl_connect('motion_notify_event', self._on_zoom_motion)
        self.canvas.mpl_connect('button_release_event', self._on_zoom_release)
        self.canvas.mpl_connect('button_press_event',
                                self._on_zoom_right_click)
        self.canvas.mpl_connect('scroll_event', self._on_zoom_scroll)
        # R294: X 轴可见范围变化联动日期刻度标签（缩放/平移后 ticks 随可见
        # 范围刷新，覆盖框选缩放/右拖平移/滚轮缩放/双击还原全部 set_xlim 路径）。
        # weak=False 防止 bound method 回调被 GC 回收。
        self.price_ax.callbacks.connect(
            'xlim_changed', self._refresh_x_date_ticks, weak=False)

    def _on_zoom_press(self, event):
        """处理缩放按下事件"""
        if event.inaxes != self.price_ax or event.button != 1:
            return
        self._zoom_press_x = event.xdata
        # 删除旧的rect，重新创建新的
        if self._zoom_rect is not None:
            self._zoom_rect.remove()
            self._zoom_rect = None
        self._zoom_rect = self.price_ax.axvspan(
            event.xdata, event.xdata, color='blue', alpha=0.18)
        self.canvas.draw_idle()
        # R265: 全量重绘后十字光标blit背景失效
        if hasattr(self, '_invalidate_crosshair_background'):
            self._invalidate_crosshair_background()

    def _on_zoom_motion(self, event):
        """处理缩放拖动事件 - 只在拖拽状态下处理，避免与十字光标冲突"""
        # 只有在按下鼠标左键并且开始拖拽时才处理
        if (self._zoom_press_x is None or
            event.inaxes != self.price_ax or
            event.button != 1 or
            not hasattr(event, 'button') or
                event.button is None):
            return

        now = int(time.time() * 1000)
        if now - self._last_motion_time < self._motion_interval_ms:
            return
        self._last_motion_time = now

        x0, x1 = self._zoom_press_x, event.xdata
        # 删除旧的rect，重新创建新的
        if self._zoom_rect is not None:
            self._zoom_rect.remove()
            self._zoom_rect = None
        self._zoom_rect = self.price_ax.axvspan(
            x0, x1, color='blue', alpha=0.18)
        self.canvas.draw_idle()
        # R265: 全量重绘后十字光标blit背景失效
        if hasattr(self, '_invalidate_crosshair_background'):
            self._invalidate_crosshair_background()

    def _on_zoom_release(self, event):
        """处理缩放释放事件"""
        if self._zoom_press_x is None or event.inaxes != self.price_ax or event.button != 1:
            return
        x0, x1 = self._zoom_press_x, event.xdata
        if self._zoom_rect:
            self._zoom_rect.remove()
            self._zoom_rect = None
        if abs(x1 - x0) < 1:  # 拖动太短不缩放
            self._zoom_press_x = None
            self.canvas.draw_idle()
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()
            return
        if x1 > x0:
            # 左→右：放大
            self._zoom_history.append(self.price_ax.get_xlim())
            self.price_ax.set_xlim(x0, x1)
            # 新增：缩放后纵向自适应（不超出边界，自动居中）
            ymin = getattr(self, '_ymin', None)
            ymax = getattr(self, '_ymax', None)
            if ymin is not None and ymax is not None:
                kdata = self.current_kdata
                left_idx = int(max(0, round(x0)))
                right_idx = int(min(len(kdata)-1, round(x1)))
                if right_idx > left_idx:
                    sub = kdata.iloc[left_idx:right_idx+1]
                    y1 = float(sub['low'].min())
                    y2 = float(sub['high'].max())
                    pad = (y2 - y1) * 0.08
                    self.price_ax.set_ylim(y1 - pad, y2 + pad)
                else:
                    self.price_ax.set_ylim(ymin, ymax)
        else:
            # 右→左：还原到上一级
            if self._zoom_history:
                prev_xlim = self._zoom_history.pop()
                self.price_ax.set_xlim(prev_xlim)
            else:
                self.price_ax.set_xlim(auto=True)
            # 新增：还原后纵向自适应
            ymin = getattr(self, '_ymin', None)
            ymax = getattr(self, '_ymax', None)
            if ymin is not None and ymax is not None:
                self.price_ax.set_ylim(ymin, ymax)
        self._limit_xlim()
        self._zoom_press_x = None
        self.canvas.draw_idle()
        # R265 性能：移除防御性_optimize_display调用 + 标记blit背景失效
        if hasattr(self, '_invalidate_crosshair_background'):
            self._invalidate_crosshair_background()

    def _on_zoom_right_click(self, event):
        """处理右键点击事件 - 支持拖拽和双击还原"""
        # 右键单击支持K线拖拽和平移，右键双击还原初始状态
        if event.inaxes == self.price_ax and event.button == 3:
            if not hasattr(self, '_last_right_click_time'):
                self._last_right_click_time = 0
            now = time.time()
            # 双击判定（0.35秒内两次）
            if hasattr(self, '_last_right_click_pos') and abs(event.x - self._last_right_click_pos) < 5 and (now - self._last_right_click_time) < 0.35:
                # 右键双击：还原初始状态
                self.price_ax.set_xlim(0, len(self.current_kdata)-1)
                ymin = getattr(self, '_ymin', None)
                ymax = getattr(self, '_ymax', None)
                if ymin is not None and ymax is not None:
                    self.price_ax.set_ylim(ymin, ymax)
                self._zoom_history.clear()
                self.canvas.draw_idle()
                # R265 性能：移除防御性_optimize_display调用 + 标记blit背景失效
                if hasattr(self, '_invalidate_crosshair_background'):
                    self._invalidate_crosshair_background()
                self._last_right_click_time = 0
                return
            # 记录本次点击
            self._last_right_click_time = now
            self._last_right_click_pos = event.x
            # 右键单击：拖拽平移
            if not hasattr(self, '_drag_start_x') or self._drag_start_x is None:
                self._drag_start_x = event.xdata
                self._drag_start_xlim = self.price_ax.get_xlim()
                self.canvas.mpl_connect(
                    'motion_notify_event', self._on_drag_move)
            else:
                self._drag_start_x = None
                self._drag_start_xlim = None

    def _on_drag_move(self, event):
        """处理拖拽移动事件"""
        if event.inaxes != self.price_ax or event.button != 3:
            return
        if not hasattr(self, '_drag_start_x') or self._drag_start_x is None:
            return
        dx = event.xdata - self._drag_start_x
        left, right = self._drag_start_xlim
        self.price_ax.set_xlim(left - dx, right - dx)
        self._limit_xlim()
        self.canvas.draw_idle()
        # R265: 全量重绘后十字光标blit背景失效
        if hasattr(self, '_invalidate_crosshair_background'):
            self._invalidate_crosshair_background()

    def _on_zoom_scroll(self, event):
        """处理滚轮缩放事件"""
        # 滚轮缩放，鼠标为中心放大/缩小
        if event.inaxes != self.price_ax:
            return
        cur_xlim = self.price_ax.get_xlim()
        xdata = event.xdata
        scale_factor = 0.8 if event.button == 'up' else 1.25
        left = xdata - (xdata - cur_xlim[0]) * scale_factor
        right = xdata + (cur_xlim[1] - xdata) * scale_factor
        self._zoom_history.append(cur_xlim)
        self.price_ax.set_xlim(left, right)
        self._limit_xlim()
        self.canvas.draw_idle()
        # R265 性能：set_xlim不影响网格/刻度，移除_optimize_display高频调用
        # （该防御代码每滚一格执行一次，纯浪费）；并标记十字光标blit背景失效
        if hasattr(self, '_invalidate_crosshair_background'):
            self._invalidate_crosshair_background()

    def async_update_chart(self, data: dict, n_segments: int = 20):
        """异步更新图表 - 多线程分段预处理实现"""
        if not data or 'kdata' not in data:
            return
        kdata = data['kdata']
        if len(kdata) <= 100 or n_segments <= 1:
            QTimer.singleShot(0, lambda: self.update_chart({'kdata': kdata}))
            return

        # 分段
        segments = np.array_split(kdata, n_segments)
        results = [None] * n_segments
        progress_step = int(100 / n_segments) if n_segments > 0 else 100

        def process_segment(segment, idx):
            # 这里可以做降采样、指标等预处理
            res = self._downsample_kdata(segment, max_points=1200)
            # 实时更新进度
            QTimer.singleShot(0, lambda: self.update_loading_progress(
                min((idx+1)*progress_step, 100), f"正在处理第{idx+1}/{n_segments}段..."))
            return res

        with ThreadPoolExecutor(max_workers=n_segments) as executor:
            futures = {executor.submit(
                process_segment, seg, i): i for i, seg in enumerate(segments)}
            for f in as_completed(futures):
                idx = futures[f]
                results[idx] = f.result()
        merged = np.concatenate(results)
        merged_df = kdata.iloc[merged] if isinstance(
            merged[0], (int, np.integer)) else pd.concat(results)
        # 渲染后关闭进度对话框由update_chart内部完成
        # 新增：补充 title 和 stock_code 字段，优先从 data 拷贝
        title = data.get('title', '')
        stock_code = data.get('stock_code', '')
        QTimer.singleShot(0, lambda: self.update_chart(
            {'kdata': merged_df, 'title': title, 'stock_code': stock_code}))

    def _limit_xlim(self):
        """限制X轴范围"""
        if not hasattr(self, 'current_kdata') or self.current_kdata is None:
            return

        xlim = self.price_ax.get_xlim()
        max_x = len(self.current_kdata) - 1
        min_x = 0

        # 确保不超出数据范围
        left = max(min_x, xlim[0])
        right = min(max_x, xlim[1])

        if left != xlim[0] or right != xlim[1]:
            self.price_ax.set_xlim(left, right)

    def get_visible_range(self):
        """获取当前主图可见区间的K线索引范围"""
        if not hasattr(self, 'price_ax') or not hasattr(self, 'current_kdata'):
            return None, None

        xlim = self.price_ax.get_xlim()
        start_idx = max(0, int(xlim[0]))
        end_idx = min(len(self.current_kdata) - 1, int(xlim[1]))

        return start_idx, end_idx
