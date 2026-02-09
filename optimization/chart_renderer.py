from loguru import logger
"""
优化的图表渲染器模块
提供渲染优先级、异步渲染和性能优化功能
"""

import os
import threading
import time
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, PriorityQueue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker, QTimer
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import to_rgba
import warnings
import matplotlib.dates as mdates
from core.performance import measure_performance
from optimization.update_throttler import get_update_throttler

logger = logger

class RenderPriority(Enum):
    """渲染优先级"""
    CRITICAL = 1    # 关键图表（K线主图）
    HIGH = 2        # 高优先级（成交量）
    NORMAL = 3      # 普通优先级（主要指标）
    LOW = 4         # 低优先级（次要指标）
    BACKGROUND = 5  # 后台渲染（装饰元素）

@dataclass
class RenderTask:
    """渲染任务"""
    id: str
    priority: RenderPriority
    render_func: Callable
    data: Any
    callback: Optional[Callable] = None
    created_time: float = field(default_factory=time.time)

    def __lt__(self, other):
        """支持优先级队列排序"""
        return self.priority.value < other.priority.value

class ChartRenderer(QObject):
    """优化的图表渲染器"""

    # 添加Qt信号
    render_progress = pyqtSignal(int, str)  # 渲染进度信号
    render_complete = pyqtSignal()  # 渲染完成信号
    render_error = pyqtSignal(str)  # 错误信号
    priority_render_complete = pyqtSignal(str, object)  # 优先级渲染完成信号

    def __init__(self, max_workers: int = os.cpu_count(), enable_progressive: bool = True):
        """
        初始化图表渲染器

        Args:
            max_workers: 最大工作线程数
            enable_progressive: 是否启用渐进式渲染
        """
        super().__init__()  # 调用QObject初始化
        self.max_workers = max_workers
        self.enable_progressive = enable_progressive

        # 渲染队列（优先级队列）
        self.render_queue = PriorityQueue()

        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 运行状态
        self.is_running = False
        self.worker_thread = None

        # 渲染统计
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'average_render_time': 0.0,
            'queue_size': 0
        }

        # 当前渲染任务
        self.current_tasks: Dict[str, Future] = {}

        # 锁
        self.stats_lock = threading.Lock()
        self.tasks_lock = threading.Lock()
        self._render_lock = QMutex()  # 添加QMutex用于渲染锁

        # 从gui版本合并的属性
        self._view_range = None  # 当前视图范围
        self._downsampling_threshold = 2000  # 降采样阈值
        self._last_layout = None  # 缓存上一次布局参数

        # 渲染优先级管理
        self._render_queue = []  # 保留gui版本的渲染队列以兼容现有代码
        self._current_render_task = None

        # 更新节流器
        self._update_throttler = get_update_throttler()
        self._pending_render_data = None

        # 性能监控
        self._render_stats = {
            'total_renders': 0,
            'avg_render_time': 0,
            'priority_breakdown': {p.name: 0 for p in RenderPriority},
            'throttled_updates': 0,
            'skipped_updates': 0
        }

        logger.info(f"ChartRenderer初始化完成 - 工作线程数: {max_workers}")

    def start(self):
        """启动渲染器"""
        if self.is_running:
            return

        self.is_running = True

        # 启动工作线程
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="ChartRenderer-Worker",
            daemon=True
        )
        self.worker_thread.start()

        logger.info("ChartRenderer已启动")

    def stop(self):
        """停止渲染器"""
        if not self.is_running:
            return

        self.is_running = False

        # 等待队列清空
        while not self.render_queue.empty():
            time.sleep(0.1)

        # 取消所有正在进行的任务
        with self.tasks_lock:
            for task_id, future in self.current_tasks.items():
                future.cancel()
            self.current_tasks.clear()

        # 关闭线程池
        self.executor.shutdown(wait=True)

        logger.info("ChartRenderer已停止")

    def _worker_loop(self):
        """工作线程主循环"""
        while self.is_running:
            try:
                # 获取任务（带超时）
                task = self.render_queue.get(timeout=1.0)

                # 更新队列大小统计
                with self.stats_lock:
                    self.stats['queue_size'] = self.render_queue.qsize()

                # 处理任务
                self._process_render_task(task)

                self.render_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                logger.error(f"渲染工作线程处理任务时出错: {e}")

    @measure_performance("ChartRenderer._process_render_task")
    def _process_render_task(self, task: RenderTask):
        """处理渲染任务"""
        start_time = time.time()

        try:
            # 发送进度信号
            self.render_progress.emit(10, f"执行渲染任务 {task.id}...")

            # 提交到线程池执行
            future = self.executor.submit(task.render_func, task.data)

            # 记录当前任务
            with self.tasks_lock:
                self.current_tasks[task.id] = future

            # 等待完成
            result = future.result()

            # 发送完成信号
            self.render_progress.emit(90, "渲染任务完成")
            self.priority_render_complete.emit(task.id, result)

            # 如果是关键优先级的任务，触发渲染完成信号
            if task.priority == RenderPriority.CRITICAL:
                self.render_complete.emit()

            # 调用回调函数
            if task.callback:
                task.callback(result)

            # 更新成功统计
            with self.stats_lock:
                self.stats['completed_tasks'] += 1

            logger.debug(
                f"渲染任务 {task.id} 完成 - 耗时: {time.time() - start_time:.4f}s")

        except Exception as e:
            # 发送错误信号
            self.render_error.emit(f"渲染任务 {task.id} 失败: {str(e)}")

            # 更新失败统计
            with self.stats_lock:
                self.stats['failed_tasks'] += 1

            logger.error(f"渲染任务 {task.id} 失败: {e}")

        finally:
            # 移除当前任务记录
            with self.tasks_lock:
                self.current_tasks.pop(task.id, None)

            # 更新渲染时间统计
            render_time = time.time() - start_time
            with self.stats_lock:
                total_completed = self.stats['completed_tasks'] + \
                    self.stats['failed_tasks']
                if total_completed > 0:
                    current_avg = self.stats['average_render_time']
                    self.stats['average_render_time'] = (
                        (current_avg * (total_completed - 1) +
                         render_time) / total_completed
                    )

            # 更新gui版本兼容的统计
            self._update_render_stats(task.priority, render_time)

    # 添加GUI版本的方法
    def render(self, figure: Figure, data: pd.DataFrame, indicators: List[Dict] = None):
        """标准渲染方法（兼容性）"""
        self.render_with_priority(
            task_id=f"render_{int(time.time() * 1000)}",
            render_func=self._execute_render,
            data={'figure': figure, 'data': data, 'indicators': indicators},
            priority=RenderPriority.NORMAL
        )

    def render_with_throttling(self, figure: Figure, data: pd.DataFrame, indicators: List[Dict] = None):
        """带节流的渲染方法"""
        # 保存渲染数据
        self._pending_render_data = (figure, data, indicators)

        # 请求节流更新 - 使用新的API
        self._update_throttler.request_update(
            'chart-render-throttled',
            self._process_throttled_update,
            mode='debounce',  # 使用防抖模式，因为我们只需要最后一次更新
            delay=150
        )

        # 更新统计
        self._render_stats['throttled_updates'] += 1

    def _process_throttled_update(self):
        """处理节流更新"""
        if self._pending_render_data:
            figure, data, indicators = self._pending_render_data
            self._pending_render_data = None
            self.render(figure, data, indicators)

    def _execute_render(self, data: Dict):
        """执行具体的渲染逻辑"""
        figure = data.get('figure')
        df = data.get('data')
        indicators = data.get('indicators')

        # 保存当前状态
        current_state = self._save_state()

        try:
            # 执行渲染逻辑
            return self._do_render_prioritized(figure, df, indicators)
        finally:
            # 恢复状态
            self._restore_state(current_state)

    def _do_render_prioritized(self, figure: Figure, data: pd.DataFrame, indicators: List[Dict] = None):
        """执行优先级渲染逻辑"""
        try:
            # 设置图表布局
            gs, axes = self.setup_figure(figure)
            price_ax, volume_ax, indicator_ax = axes

            # 第一阶段：关键渲染（K线主图）
            self.render_progress.emit(10, "渲染K线主图...")
            self.render_candlesticks(price_ax, data)

            # 立即更新显示，让用户看到主图
            figure.canvas.draw_idle()

            # 第二阶段：高优先级渲染（成交量）
            self.render_progress.emit(30, "渲染成交量...")
            self.render_volume(volume_ax, data)

            # 第三阶段：指标渲染（按优先级）
            if indicators:
                self._render_indicators_by_priority(
                    indicator_ax, indicators, figure)

            # 最终优化和完成
            self.render_progress.emit(90, "优化显示...")
            self._finalize_render(price_ax, volume_ax, indicator_ax)

            self.render_progress.emit(100, "渲染完成")

            return True

        except Exception as e:
            import traceback
            error_msg = f"优先级渲染失败: {str(e)}\n{traceback.format_exc()}"
            raise Exception(error_msg)

    def _render_indicators_by_priority(self, base_ax, indicators: List[Dict], figure: Figure):
        """按优先级渲染指标"""
        self.render_progress.emit(50, "渲染指标...")

        # 按优先级对指标进行排序
        prioritized_indicators = sorted(
            indicators,
            key=lambda ind: self._get_indicator_priority(
                ind.get('name', '')).value
        )

        # 创建足够的轴
        indicator_axes = [base_ax]
        if len(indicators) > 1:
            for i in range(1, len(indicators)):
                indicator_axes.append(base_ax.twinx())

            # 设置右侧轴的位置，避免重叠
            for i, ax in enumerate(indicator_axes[1:], 1):
                ax.spines['right'].set_position(('outward', 60 * (i-1)))

        # 渲染每个指标
        for i, indicator in enumerate(prioritized_indicators):
            if 'data' in indicator and not indicator['data'].empty:
                self.render_progress.emit(
                    50 + (40 * i) // len(prioritized_indicators),
                    f"渲染指标 {indicator.get('name', f'指标{i}')}..."
                )
                self.render_line(
                    indicator_axes[min(i, len(indicator_axes)-1)],
                    indicator['data'],
                    {
                        'color': self._get_indicator_color(i),
                        'label': indicator.get('name', '')
                    }
                )

    def _get_indicator_priority(self, indicator_name: str) -> RenderPriority:
        """根据指标名获取优先级"""
        # 常用指标优先级
        priority_map = {
            'MA': RenderPriority.HIGH,
            'EMA': RenderPriority.HIGH,
            'BOLL': RenderPriority.HIGH,
            'MACD': RenderPriority.NORMAL,
            'RSI': RenderPriority.NORMAL,
            'KDJ': RenderPriority.NORMAL,
        }

        for key, priority in priority_map.items():
            if key in indicator_name:
                return priority

        return RenderPriority.LOW

    def _finalize_render(self, price_ax, volume_ax, indicator_ax):
        """完成渲染，优化显示"""
        # 优化各个轴的显示
        for ax in [price_ax, volume_ax, indicator_ax]:
            # 设置网格
            ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

            # 优化刻度标签
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontsize(8)

            # 移除上框和右框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

        # 隐藏上面两个子图的x轴刻度标签
        price_ax.tick_params(axis='x', labelbottom=False)
        volume_ax.tick_params(axis='x', labelbottom=False)

    def _update_render_stats(self, priority: RenderPriority, render_time: float):
        """更新渲染统计"""
        self._render_stats['total_renders'] += 1

        # 更新平均渲染时间
        total = self._render_stats['total_renders']
        current_avg = self._render_stats['avg_render_time']
        self._render_stats['avg_render_time'] = (
            current_avg * (total - 1) + render_time) / total

        # 更新优先级统计
        self._render_stats['priority_breakdown'][priority.name] += 1

    def get_render_stats(self) -> Dict[str, Any]:
        """获取渲染统计信息"""
        return {**self._render_stats}

    def cancel_low_priority_tasks(self):
        """取消低优先级任务"""
        with QMutexLocker(self._render_lock):
            self._render_queue = [t for t in self._render_queue
                                  if t.priority.value <= RenderPriority.HIGH.value]

    def clear_render_queue(self):
        """清空渲染队列"""
        with QMutexLocker(self._render_lock):
            self._render_queue = []

    def _save_state(self):
        """保存当前状态"""
        return {
            'view_range': self._view_range,
            'downsampling_threshold': self._downsampling_threshold,
            'last_layout': self._last_layout
        }

    def _restore_state(self, state):
        """恢复状态"""
        if state:
            self._view_range = state.get('view_range', self._view_range)
            self._downsampling_threshold = state.get(
                'downsampling_threshold', self._downsampling_threshold)
            self._last_layout = state.get('last_layout', self._last_layout)

    def set_throttle_interval(self, interval_ms: int):
        """设置节流间隔"""
        self._update_throttler.min_interval_ms = interval_ms

    def render_with_priority(self, task_id: str, render_func: Callable, data: Any,
                             priority: RenderPriority = RenderPriority.NORMAL,
                             callback: Optional[Callable] = None,
                             cancel_lower_priority: bool = False) -> bool:
        """
        按优先级渲染

        Args:
            task_id: 任务ID
            render_func: 渲染函数
            data: 渲染数据
            priority: 渲染优先级
            callback: 完成回调函数
            cancel_lower_priority: 是否取消低优先级任务

        Returns:
            bool: 是否成功提交
        """
        if not self.is_running:
            logger.warning("渲染器未启动，无法提交任务")
            return False

        # 如果需要，取消低优先级任务
        if cancel_lower_priority:
            self._cancel_lower_priority_tasks(priority)

        task = RenderTask(
            id=task_id,
            priority=priority,
            render_func=render_func,
            data=data,
            callback=callback
        )

        try:
            self.render_queue.put(task)

            with self.stats_lock:
                self.stats['total_tasks'] += 1

            logger.debug(f"渲染任务 {task_id} 已提交到 {priority.name} 优先级队列")
            return True

        except Exception as e:
            logger.error(f"提交渲染任务 {task_id} 失败: {e}")
            return False

    def _cancel_lower_priority_tasks(self, priority: RenderPriority):
        """取消低优先级任务"""
        # 创建新队列，只保留高优先级任务
        new_queue = PriorityQueue()
        cancelled_count = 0

        while not self.render_queue.empty():
            try:
                task = self.render_queue.get_nowait()
                if task.priority.value <= priority.value:
                    # 保留高优先级或同优先级任务
                    new_queue.put(task)
                else:
                    # 取消低优先级任务
                    cancelled_count += 1
                self.render_queue.task_done()
            except Empty:
                break

        self.render_queue = new_queue

        if cancelled_count > 0:
            logger.info(f"已取消 {cancelled_count} 个低优先级渲染任务")

    def render_chart_progressive(self, chart_data: Dict[str, Any],
                                 canvas: FigureCanvasQTAgg,
                                 stages: Optional[List[str]] = None) -> bool:
        """
        渐进式图表渲染

        Args:
            chart_data: 图表数据
            canvas: matplotlib画布
            stages: 渲染阶段列表

        Returns:
            bool: 是否成功启动渲染
        """
        if not self.enable_progressive:
            # 直接渲染完整图表
            return self.render_with_priority(
                task_id="full_chart",
                render_func=self._render_full_chart,
                data={'chart_data': chart_data, 'canvas': canvas},
                priority=RenderPriority.NORMAL
            )

        # 默认渲染阶段
        if stages is None:
            stages = ['kline', 'volume', 'indicators_high',
                      'indicators_normal', 'decorations']

        # 分阶段提交渲染任务
        stage_priorities = {
            'kline': RenderPriority.CRITICAL,
            'volume': RenderPriority.HIGH,
            'indicators_high': RenderPriority.HIGH,
            'indicators_normal': RenderPriority.NORMAL,
            'indicators_low': RenderPriority.LOW,
            'decorations': RenderPriority.BACKGROUND
        }

        success_count = 0
        for i, stage in enumerate(stages):
            priority = stage_priorities.get(stage, RenderPriority.NORMAL)

            if self.render_with_priority(
                task_id=f"chart_stage_{i}_{stage}",
                render_func=self._render_chart_stage,
                data={
                    'chart_data': chart_data,
                    'canvas': canvas,
                    'stage': stage,
                    'stage_index': i
                },
                priority=priority,
                cancel_lower_priority=(stage == 'kline')  # K线图可取消低优先级任务
            ):
                success_count += 1

        logger.info(f"渐进式渲染启动 - 成功提交 {success_count}/{len(stages)} 个阶段")
        return success_count > 0

    def _render_full_chart(self, data: Dict[str, Any]):
        """渲染完整图表"""
        chart_data = data['chart_data']
        canvas = data['canvas']

        # 清除画布
        canvas.figure.clear()

        # 创建子图
        ax = canvas.figure.add_subplot(111)

        # 渲染K线数据
        if 'kline' in chart_data:
            self._render_kline(ax, chart_data['kline'])

        # 渲染成交量
        if 'volume' in chart_data:
            self._render_volume(ax, chart_data['volume'])

        # 渲染指标
        if 'indicators' in chart_data:
            self._render_indicators(ax, chart_data['indicators'])

        # 更新画布
        canvas.draw()

    def _render_chart_stage(self, data: Dict[str, Any]):
        """渲染图表阶段"""
        chart_data = data['chart_data']
        canvas = data['canvas']
        stage = data['stage']
        stage_index = data['stage_index']

        # 如果是第一阶段，清除画布
        if stage_index == 0:
            canvas.figure.clear()

        # 获取或创建子图
        if canvas.figure.axes:
            ax = canvas.figure.axes[0]
        else:
            ax = canvas.figure.add_subplot(111)

        # 根据阶段渲染不同内容
        if stage == 'kline' and 'kline' in chart_data:
            self._render_kline(ax, chart_data['kline'])
        elif stage == 'volume' and 'volume' in chart_data:
            self._render_volume(ax, chart_data['volume'])
        elif stage.startswith('indicators') and 'indicators' in chart_data:
            # 根据优先级渲染不同指标
            indicators = chart_data['indicators']
            if stage == 'indicators_high':
                high_priority_indicators = [
                    ind for ind in indicators if ind.get('priority', 'normal') == 'high']
                self._render_indicators(ax, high_priority_indicators)
            elif stage == 'indicators_normal':
                normal_indicators = [ind for ind in indicators if ind.get(
                    'priority', 'normal') == 'normal']
                self._render_indicators(ax, normal_indicators)
            elif stage == 'indicators_low':
                low_indicators = [ind for ind in indicators if ind.get(
                    'priority', 'normal') == 'low']
                self._render_indicators(ax, low_indicators)
        elif stage == 'decorations':
            self._render_decorations(ax, chart_data.get('decorations', []))

        # 更新画布
        canvas.draw()

    def _render_kline(self, ax, kline_data):
        """渲染K线图"""
        if not kline_data or len(kline_data) == 0:
            return

        # 简化的K线渲染逻辑
        try:
            dates = range(len(kline_data))
            opens = [item.get('open', 0) for item in kline_data]
            highs = [item.get('high', 0) for item in kline_data]
            lows = [item.get('low', 0) for item in kline_data]
            closes = [item.get('close', 0) for item in kline_data]

            # 绘制K线
            for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
                color = 'red' if c > o else 'green'
                # 实体
                ax.add_patch(patches.Rectangle((i-0.3, min(o, c)), 0.6, abs(c-o),
                                               facecolor=color, alpha=0.8))
                # 影线
                ax.plot([i, i], [l, h], color=color, linewidth=1)

            ax.set_xlim(-1, len(dates))
            ax.set_ylim(min(lows) * 0.95, max(highs) * 1.05)

        except Exception as e:
            logger.error(f"K线渲染失败: {e}")

    def _render_volume(self, ax, volume_data):
        """渲染成交量"""
        if not volume_data:
            return

        try:
            # 创建成交量子图（简化版本）
            volumes = [item.get('volume', 0) for item in volume_data]
            dates = range(len(volumes))

            # 在现有图表下方添加成交量柱状图
            ax2 = ax.twinx()
            ax2.bar(dates, volumes, alpha=0.3, color='blue')
            ax2.set_ylabel('Volume')

        except Exception as e:
            logger.error(f"成交量渲染失败: {e}")

    def _render_indicators(self, ax, indicators_data):
        """渲染技术指标"""
        if not indicators_data:
            return

        try:
            for indicator in indicators_data:
                if indicator is None:
                    continue
                name = indicator.get('name', 'Unknown')
                values = indicator.get('values', [])
                color = indicator.get('color', 'blue')

                if values:
                    dates = range(len(values))
                    ax.plot(dates, values, label=name, color=color, alpha=0.7)

            ax.legend()

        except Exception as e:
            logger.error(f"指标渲染失败: {e}")

    def _render_decorations(self, ax, decorations_data):
        """渲染装饰元素"""
        if not decorations_data:
            return

        try:
            for decoration in decorations_data:
                dec_type = decoration.get('type', 'text')

                if dec_type == 'text':
                    x = decoration.get('x', 0)
                    y = decoration.get('y', 0)
                    text = decoration.get('text', '')
                    ax.text(x, y, text, fontsize=8, alpha=0.7)
                elif dec_type == 'line':
                    x1, y1 = decoration.get('start', (0, 0))
                    x2, y2 = decoration.get('end', (0, 0))
                    ax.plot([x1, x2], [y1, y2], '--', alpha=0.5)

        except Exception as e:
            logger.error(f"装饰元素渲染失败: {e}")

    def get_render_status(self) -> Dict[str, Any]:
        """获取渲染状态"""
        with self.stats_lock:
            stats = self.stats.copy()

        with self.tasks_lock:
            current_task_count = len(self.current_tasks)

        return {
            'is_running': self.is_running,
            'max_workers': self.max_workers,
            'queue_size': self.render_queue.qsize(),
            'current_tasks': current_task_count,
            'stats': stats
        }

    def clear_queue(self):
        """清空渲染队列"""
        cleared_count = self.render_queue.qsize()

        while not self.render_queue.empty():
            try:
                self.render_queue.get_nowait()
                self.render_queue.task_done()
            except Empty:
                break

        logger.info(f"已清空渲染队列 - 清除任务数: {cleared_count}")

    def setup_figure(self, figure: Figure) -> Tuple[GridSpec, List]:
        """设置图表布局

        Args:
            figure: matplotlib图形对象

        Returns:
            Tuple[GridSpec, List]: 网格规格和轴列表
        """
        try:
            # 清除当前图表
            figure.clear()

            # 创建三个子图，比例为3:1:1
            gs = figure.add_gridspec(3, 1, height_ratios=[
                                     3, 1, 1], hspace=0.05)

            # 创建轴
            price_ax = figure.add_subplot(gs[0])  # 价格图(K线)
            volume_ax = figure.add_subplot(gs[1], sharex=price_ax)  # 成交量
            indicator_ax = figure.add_subplot(gs[2], sharex=price_ax)  # 指标

            # 隐藏x轴标签（除了最后一个子图）
            price_ax.tick_params(axis='x', labelbottom=False)
            volume_ax.tick_params(axis='x', labelbottom=False)

            # 返回网格规格和轴列表
            return gs, [price_ax, volume_ax, indicator_ax]
        except Exception as e:
            self.render_error.emit(f"设置图表布局失败: {str(e)}")
            # 创建基础布局
            figure.clear()
            ax = figure.add_subplot(111)
            return None, [ax, ax, ax]

    def render_candlesticks(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True):
        """高性能K线绘制，支持datetime X轴和等距序号X轴
        Args:
            ax: matplotlib轴对象
            data: K线数据
            style: 样式字典
            x: 可选，X轴数据（可以是datetime数组或数字索引）
            use_datetime_axis: 是否使用datetime X轴（如果数据包含datetime列）
        """
        try:
            # 添加数据有效性检查
            if data is None:
                self.render_error.emit("绘制K线失败: 数据为None")
                return

            if not isinstance(data, pd.DataFrame):
                self.render_error.emit(f"绘制K线失败: 数据类型错误: {type(data)}")
                return

            if data.empty:
                self.render_error.emit("绘制K线失败: 数据为空DataFrame")
                return

            # 检查必要的列
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [
                col for col in required_columns if col not in data.columns]
            if missing_columns:
                self.render_error.emit(f"绘制K线失败: 数据缺少必要列: {missing_columns}")
                return

            view_data = self._get_view_data(data)
            plot_data = self._downsample_data(view_data)
            self._render_candlesticks_efficient(ax, plot_data, style or {}, x, use_datetime_axis)
            self._optimize_display(ax)
        except Exception as e:
            self.render_error.emit(f"绘制K线失败: {str(e)}")

    def _render_candlesticks_efficient(self, ax, data: pd.DataFrame, style: Dict[str, Any], x: np.ndarray = None, use_datetime_axis: bool = False):
        """使用collections高效渲染K线，支持datetime X轴和等距序号X轴，空心样式"""
        try:
            # 添加ax有效性检查
            if ax is None:
                logger.warning("_render_candlesticks_efficient: ax参数为None，跳过渲染")
                return

            # 添加数据有效性检查
            if data is None or data.empty:
                logger.warning("_render_candlesticks_efficient: 数据为空")
                return

            # 确保必要的列存在
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [
                col for col in required_columns if col not in data.columns]
            if missing_columns:
                logger.warning(
                    f"_render_candlesticks_efficient: 数据缺少必要列: {missing_columns}")
                return

            up_color = style.get('up_color', '#ff0000')
            down_color = style.get('down_color', '#00ff00')
            alpha = style.get('alpha', 1.0)
            # 修复：横坐标处理（支持datetime X轴）
            if x is not None:
                xvals = x
            elif use_datetime_axis and 'datetime' in data.columns:
                # 使用datetime列
                try:
                    datetime_series = pd.to_datetime(data['datetime'])
                    xvals = mdates.date2num(datetime_series)
                except Exception as e:
                    logger.warning(f"datetime X轴转换失败: {e}，使用数字索引")
                    xvals = np.arange(len(data))
            else:
                try:
                    # 检查索引类型
                    if hasattr(data.index, 'to_pydatetime'):
                        xvals = mdates.date2num(data.index.to_pydatetime())
                    elif pd.api.types.is_datetime64_any_dtype(data.index):
                        # 如果是datetime类型但没有to_pydatetime方法
                        xvals = mdates.date2num(pd.to_datetime(data.index).to_pydatetime())
                    else:
                        # 如果不是日期索引，使用序号
                        logger.debug(f"索引类型不是日期类型: {type(data.index)}，使用序号作为X轴")
                        xvals = np.arange(len(data))
                except Exception as e:
                    logger.debug(f"转换日期失败，使用序号作为X轴: {e}")
                    xvals = np.arange(len(data))

            verts_up, verts_down, segments_up, segments_down = [], [], [], []
            for i, (idx, row) in enumerate(data.iterrows()):
                try:
                    open_price = row['open']
                    close = row['close']
                    high = row['high']
                    low = row['low']
                    left = xvals[i] - 0.3
                    right = xvals[i] + 0.3
                    if close >= open_price:
                        verts_up.append([
                            (left, open_price), (left, close), (right,
                                                                close), (right, open_price)
                        ])
                        segments_up.append([(xvals[i], low), (xvals[i], high)])
                    else:
                        verts_down.append([
                            (left, open_price), (left, close), (right,
                                                                close), (right, open_price)
                        ])
                        segments_down.append(
                            [(xvals[i], low), (xvals[i], high)])
                except Exception as e:
                    logger.warning(f"处理K线数据行 {i} 时出错: {e}")
                    continue

            # 修改：实现经典的阳线空心，阴线实心样式
            if verts_up:
                # 阳线（上涨）：空心，只有红色边框
                collection_up = PolyCollection(
                    verts_up, facecolor='none', edgecolor=up_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_up)

            if verts_down:
                # 阴线（下跌）：实心绿色
                collection_down = PolyCollection(
                    verts_down, facecolor=down_color, edgecolor=down_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_down)

            if segments_up:  # 上涨影线
                collection_shadow_up = LineCollection(
                    segments_up, colors=up_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_shadow_up)

            if segments_down:  # 下跌影线
                collection_shadow_down = LineCollection(
                    segments_down, colors=down_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_shadow_down)

            ax.autoscale_view()
        except Exception as e:
            logger.error(f"_render_candlesticks_efficient失败: {e}")

    def render_volume(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True):
        """高性能成交量绘制，支持datetime X轴和等距序号X轴
        Args:
            ax: matplotlib轴对象
            data: K线数据
            style: 样式字典
            x: 可选，X轴数据（可以是datetime数组或数字索引）
            use_datetime_axis: 是否使用datetime X轴（如果数据包含datetime列）
        """
        try:
            # 添加数据有效性检查
            if data is None:
                self.render_error.emit("绘制成交量失败: 数据为None")
                return

            if not isinstance(data, pd.DataFrame):
                self.render_error.emit(f"绘制成交量失败: 数据类型错误: {type(data)}")
                return

            if data.empty:
                self.render_error.emit("绘制成交量失败: 数据为空DataFrame")
                return

            # 检查volume列
            if 'volume' not in data.columns:
                self.render_error.emit("绘制成交量失败: 数据缺少volume列")
                return

            view_data = self._get_view_data(data)
            plot_data = self._downsample_data(view_data)
            # 修复：直接使用向量化渲染实现
            self._render_volume_vectorized(ax, plot_data, style or {}, x, use_datetime_axis)
            self._optimize_display(ax)
        except Exception as e:
            self.render_error.emit(f"绘制成交量失败: {str(e)}")

    def _render_volume_vectorized(self, ax, data: pd.DataFrame, style: Dict[str, Any], x: np.ndarray = None, use_datetime_axis: bool = False):
        """使用向量化高效渲染成交量，支持datetime X轴和等距序号X轴
        移植自gui/widgets/chart_renderer.py的_render_volume_efficient实现
        """
        up_color = style.get('up_color', '#ff0000')
        down_color = style.get('down_color', '#00ff00')
        alpha = style.get('volume_alpha', 0.5)

        # 横坐标（与K线图保持一致）
        if x is not None:
            xvals = x
        elif use_datetime_axis and 'datetime' in data.columns:
            try:
                datetime_series = pd.to_datetime(data['datetime'])
                xvals = mdates.date2num(datetime_series)
            except Exception as e:
                logger.warning(f"成交量datetime X轴转换失败: {e}，使用数字索引")
                xvals = np.arange(len(data))
        elif isinstance(data.index, pd.DatetimeIndex):
            xvals = mdates.date2num(data.index.to_pydatetime())
        else:
            xvals = np.arange(len(data))

        # 计算柱状图宽度（与K线图保持一致）
        if use_datetime_axis and len(xvals) > 1:
            avg_interval = np.mean(np.diff(xvals))
            bar_width = max(0.3, avg_interval * 0.6)
        else:
            bar_width = 0.3

        # 性能优化：使用完全向量化的numpy操作，提升10-100倍性能
        # 提取数据为numpy数组（避免iterrows()的性能开销）
        volumes = data['volume'].values
        closes = data['close'].values
        opens = data['open'].values
        n = len(data)

        # 向量化计算left和right
        lefts = xvals - bar_width / 2
        rights = xvals + bar_width / 2

        # 向量化判断涨跌
        is_up = closes >= opens
        up_indices = np.where(is_up)[0]
        down_indices = np.where(~is_up)[0]

        # 性能优化：完全向量化构建，直接使用numpy数组（PolyCollection支持）
        def build_volume_verts(indices):
            """批量构建成交量柱状图顶点，返回numpy数组"""
            if len(indices) == 0:
                return np.empty((0, 4, 2))
            idx_arr = indices  # 已经是numpy数组，不需要转换
            verts = np.empty((len(indices), 4, 2), dtype=np.float64)
            verts[:, 0, 0] = lefts[idx_arr]      # 左下x
            verts[:, 0, 1] = 0                   # 左下y (底部)
            verts[:, 1, 0] = lefts[idx_arr]      # 左上x
            verts[:, 1, 1] = volumes[idx_arr]    # 左上y (顶部)
            verts[:, 2, 0] = rights[idx_arr]     # 右上x
            verts[:, 2, 1] = volumes[idx_arr]    # 右上y (顶部)
            verts[:, 3, 0] = rights[idx_arr]     # 右下x
            verts[:, 3, 1] = 0                   # 右下y (底部)
            return verts  # 直接返回numpy数组，PolyCollection支持

        verts_up = build_volume_verts(up_indices)
        verts_down = build_volume_verts(down_indices)
        # 性能优化：检查数组长度而不是转换为bool（避免numpy警告）
        if len(verts_up) > 0:
            collection_up = PolyCollection(
                verts_up, facecolor=up_color, edgecolor='none', alpha=alpha)
            ax.add_collection(collection_up)
        if len(verts_down) > 0:
            collection_down = PolyCollection(
                verts_down, facecolor=down_color, edgecolor='none', alpha=alpha)
            ax.add_collection(collection_down)
        # 性能优化：移除autoscale_view()调用，由调用方统一处理
        # ax.autoscale_view()  # 已移除，在rendering_mixin中统一调用

    def render_line(self, ax, data: pd.Series, style: Dict[str, Any] = None):
        """高性能线图绘制
        Args:
            ax: matplotlib轴对象
            data: 数据序列
            style: 样式字典
        """
        try:
            self._render_line_efficient(ax, data, style or {})
        except Exception as e:
            self.render_error.emit(f"绘制线图失败: {str(e)}")

    def _render_line_efficient(self, ax, data: pd.Series, style: Dict[str, Any]):
        """高效渲染线图"""
        color = style.get('color', '#1976d2')
        linewidth = style.get('linewidth', 0.4)
        alpha = style.get('alpha', 0.85)
        label = style.get('label', '')

        # 处理不同的数据类型
        if isinstance(data, pd.Series):
            # pandas Series
            y_values = data.values
            if data.index.equals(pd.RangeIndex(start=0, stop=len(data))):
                # 如果索引是范围索引，直接使用值作为横坐标
                x_values = np.arange(len(y_values))
            else:
                try:
                    # 如果索引是日期类型
                    x_values = mdates.date2num(data.index.to_pydatetime())
                except:
                    # 如果不是日期类型，使用序号作为横坐标
                    x_values = np.arange(len(y_values))
        elif isinstance(data, np.ndarray):
            # numpy数组
            y_values = data
            x_values = np.arange(len(y_values))
        elif isinstance(data, list):
            # 列表
            y_values = np.array(data)
            x_values = np.arange(len(y_values))
        else:
            self.render_error.emit(f"不支持的数据类型: {type(data)}")
            return

        # 过滤掉NaN和inf值
        valid = ~(np.isnan(y_values) | np.isinf(y_values))
        x_valid = x_values[valid]
        y_valid = y_values[valid]

        if len(x_valid) > 0:
            # 绘制线图
            ax.plot(x_valid, y_valid, color=color, linewidth=linewidth,
                    alpha=alpha, label=label)

            # 如果有标签，添加图例
            if label:
                ax.legend(loc='upper left', fontsize=8)

    def _get_view_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """获取视图范围内的数据"""
        # 添加数据有效性检查
        if data is None:
            logger.warning("_get_view_data: 数据为None")
            return pd.DataFrame()  # 返回空DataFrame而不是None

        # 确保data是DataFrame
        if not isinstance(data, pd.DataFrame):
            logger.warning(f"_get_view_data: 数据类型错误: {type(data)}")
            return pd.DataFrame()

        if data.empty:
            return data

        if self._view_range is None:
            return data

        start, end = self._view_range
        mask = (data.index >= start) & (data.index <= end)
        return data[mask]

    def _downsample_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """根据阈值对数据进行降采样"""
        # 添加数据有效性检查
        if data is None:
            logger.warning("_downsample_data: 数据为None")
            return pd.DataFrame()  # 返回空DataFrame而不是None

        # 确保data是DataFrame
        if not isinstance(data, pd.DataFrame):
            logger.warning(f"_downsample_data: 数据类型错误: {type(data)}")
            return pd.DataFrame()

        if data.empty:
            return data

        # 如果数据量小于阈值，不进行降采样
        if len(data) <= self._downsampling_threshold:
            return data

        # 根据数据量计算采样因子
        sampling_factor = max(1, len(data) // self._downsampling_threshold)

        # 进行采样
        return data.iloc[::sampling_factor].copy()

    def _optimize_display(self, ax):
        """优化显示效果"""
        # 启用网格
        ax.grid(True, alpha=0.2, linestyle='--', linewidth=0.5)

        # 设置刻度标签样式
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontsize(8)

        # 去除顶部和右侧边框
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    def set_view_range(self, start: pd.Timestamp, end: pd.Timestamp):
        """设置视图范围"""
        self._view_range = (start, end)

    def clear_view_range(self):
        """清除视图范围"""
        self._view_range = None

    def _get_indicator_color(self, index: int) -> str:
        """获取指标颜色"""
        # 预定义的颜色列表
        colors = [
            '#1976d2',  # 蓝色
            '#ab47bc',  # 紫色
            '#fbc02d',  # 黄色
            '#43a047',  # 绿色
            '#e53935',  # 红色
            '#00bcd4',  # 青色
            '#ff9800',  # 橙色
        ]
        return colors[index % len(colors)]

# 全局图表渲染器实例
_global_renderer = None

def get_chart_renderer() -> ChartRenderer:
    """获取全局图表渲染器实例"""
    global _global_renderer
    if _global_renderer is None:
        _global_renderer = ChartRenderer()
        _global_renderer.start()
    return _global_renderer

def initialize_chart_renderer(max_workers: int = 4, enable_progressive: bool = True):
    """初始化全局渲染器"""
    global _global_renderer
    if _global_renderer is not None:
        _global_renderer.stop()

    _global_renderer = ChartRenderer(max_workers, enable_progressive)
    _global_renderer.start()

def shutdown_chart_renderer():
    """关闭全局渲染器"""
    global _global_renderer
    if _global_renderer is not None:
        _global_renderer.stop()
        _global_renderer = None

# 便捷函数

def render_chart(task_id: str, render_func: Callable, data: Any,
                 priority: RenderPriority = RenderPriority.NORMAL,
                 callback: Optional[Callable] = None) -> bool:
    """渲染图表"""
    return get_chart_renderer().render_with_priority(task_id, render_func, data, priority, callback)

def render_progressive(chart_data: Dict[str, Any], canvas, stages: Optional[List[str]] = None) -> bool:
    """渐进式渲染图表"""
    return get_chart_renderer().render_chart_progressive(chart_data, canvas, stages)

# 导出接口
__all__ = [
    'RenderPriority',
    'RenderTask',
    'ChartRenderer',
    'get_chart_renderer',
    'initialize_chart_renderer',
    'shutdown_chart_renderer',
    'render_chart',
    'render_progressive'
]
