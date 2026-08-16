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
# R292 涨跌停精确判定（按板块计算涨/跌停价，替代固定 4.8% 阈值）
from core.rendering.limit_price import classify_limit_up_down, extract_symbol

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

    def cancel_low_priority_tasks(self):
        """取消低优先级任务"""
        with QMutexLocker(self._render_lock):
            self._render_queue = [t for t in self._render_queue
                                  if t.priority.value <= RenderPriority.HIGH.value]

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
            colls = self._render_candlesticks_efficient(ax, plot_data, style or {}, x, use_datetime_axis)
            self._optimize_display(ax)
            return colls
        except Exception as e:
            self.render_error.emit(f"绘制K线失败: {str(e)}")
            return None

    @staticmethod
    def build_candle_groups(data: pd.DataFrame, xvals: np.ndarray,
                            is_limit_up: np.ndarray, is_limit_down: np.ndarray):
        """构建 K 线四色分组顶点/线段（HV6 提取，全量渲染与 tick 增量更新共用）。

        HV6.1 向量化：对齐 build_volume_groups 返回 numpy 数组（空类别形状
        (0,4,2)/(0,2,2)），消除逐行 Python 循环——5 万行视图（≤1200 根）下
        每次 tick 的 verts 重建从 ~21ms 降至 ~2ms，tick 增量流畅性的关键。

        Args:
            data: K 线 DataFrame（含 open/high/low/close）
            xvals: 等距序号 X 轴（与渲染链一致，禁止 date2num）
            is_limit_up / is_limit_down: 涨跌停掩码（列优先或内部判定结果）

        Returns:
            (verts_up, verts_down, verts_limit_up, verts_limit_down,
             segments_up, segments_down, segments_limit_up, segments_limit_down)
            柱 (N,4,2) / 影线 (N,2,2) numpy 数组（空类别为 (0,4,2)/(0,2,2)）。
        """
        opens_arr = data['open'].values.astype(float)
        closes_arr = data['close'].values.astype(float)
        highs_arr = data['high'].values.astype(float)
        lows_arr = data['low'].values.astype(float)
        x = np.asarray(xvals, dtype=float)
        left = x - 0.3
        right = x + 0.3
        lu = np.asarray(is_limit_up, dtype=bool)
        ld = np.asarray(is_limit_down, dtype=bool)
        non_limit = ~lu & ~ld
        up_mask = non_limit & (closes_arr >= opens_arr)
        down_mask = non_limit & (closes_arr < opens_arr)

        def _verts(mask):
            idx = np.nonzero(mask)[0]
            if len(idx) == 0:
                return np.empty((0, 4, 2))
            o = opens_arr[idx]
            c = closes_arr[idx]
            l = left[idx]
            r = right[idx]
            verts = np.empty((len(idx), 4, 2), dtype=np.float64)
            verts[:, 0, 0] = l
            verts[:, 0, 1] = o
            verts[:, 1, 0] = l
            verts[:, 1, 1] = c
            verts[:, 2, 0] = r
            verts[:, 2, 1] = c
            verts[:, 3, 0] = r
            verts[:, 3, 1] = o
            return verts

        def _segments(mask):
            idx = np.nonzero(mask)[0]
            if len(idx) == 0:
                return np.empty((0, 2, 2))
            xc = x[idx]
            segs = np.empty((len(idx), 2, 2), dtype=np.float64)
            segs[:, 0, 0] = xc
            segs[:, 0, 1] = lows_arr[idx]
            segs[:, 1, 0] = xc
            segs[:, 1, 1] = highs_arr[idx]
            return segs

        return (_verts(up_mask), _verts(down_mask), _verts(lu), _verts(ld),
                _segments(up_mask), _segments(down_mask),
                _segments(lu), _segments(ld))

    def _render_candlesticks_efficient(self, ax, data: pd.DataFrame, style: Dict[str, Any], x: np.ndarray = None, use_datetime_axis: bool = False):
        """使用collections高效渲染K线，支持datetime X轴和等距序号X轴，空心样式

        Returns:
            HV6 tick 增量渲染：返回 8 元组 collections 引用
            (up, down, limit_up, limit_down, shadow_up, shadow_down,
             shadow_limit_up, shadow_limit_down)，元素为 None 表示该类别为空。
            调用方（rendering_mixin.update_chart）保存引用，bar 内 tick 通过
            set_verts/set_segments 局部重建 + BlitEngine blit，避免全量重绘。
        """
        collection_up = collection_down = None
        collection_limit_up = collection_limit_down = None
        collection_shadow_up = collection_shadow_down = None
        collection_shadow_limit_up = collection_shadow_limit_down = None
        try:
            # 添加ax有效性检查
            if ax is None:
                logger.warning("_render_candlesticks_efficient: ax参数为None，跳过渲染")
                return None

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
            limit_up_color = style.get('limit_up_color', '#FF9800')    # 涨停橙色
            limit_down_color = style.get('limit_down_color', '#AB47BC')  # 跌停紫色
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
                # R292 修复：xvals 必须与调用方 use_datetime_axis 严格一致。
                # 原实现 use_datetime_axis=False（数字轴，UI set_xlim(0, len-1)）时，
                # 若索引恰为 DatetimeIndex 仍会走 date2num(索引)（约 73 万级数值）
                # → 蜡烛全部出视野，表现为偶发数据范围/展示错乱。
                if use_datetime_axis:
                    # datetime轴但无datetime列：尝试从datetime索引取
                    try:
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
                else:
                    # 数字索引X轴：一律使用序号，禁止 date2num(索引)
                    xvals = np.arange(len(data))

            # R292 修复：A股四色分类（涨红/跌绿/涨停橙/跌停紫）。
            # 涨停/跌停按板块精确判定：昨收 × (1 ± 幅度) 四舍五入到分 = 涨/跌停价，
            # 收盘价等于涨/跌停价且封板才判定（core/rendering/limit_price.py）——
            # 消除固定 4.8% 阈值对主板 5~9.9% 大阳线等的误判。
            closes_arr = data['close'].values.astype(float)
            opens_arr = data['open'].values.astype(float)
            highs_arr = data['high'].values.astype(float)
            lows_arr = data['low'].values.astype(float)
            # R292-HV：列优先读取 limit 掩码。'limit_up'/'limit_down' 列由上游
            # （rendering_mixin.update_chart）在降采样前按全量数据计算——降采样后
            # 相邻 K 线并非真实相邻交易日，内部重判的"昨收"会错位导致四色漏判；
            # 列缺失时回退内部按板块判定，兼容直接传数据的调用方。
            if 'limit_up' in data.columns and 'limit_down' in data.columns:
                is_limit_up = data['limit_up'].to_numpy(dtype=bool)
                is_limit_down = data['limit_down'].to_numpy(dtype=bool)
            else:
                is_limit_up, is_limit_down = classify_limit_up_down(
                    closes_arr, highs_arr, lows_arr, extract_symbol(data))

            # HV6 提取：K 线四色分组构建逻辑由 build_candle_groups 承担，
            # 全量渲染与 tick 增量更新（set_verts 重建）共用，杜绝逻辑漂移。
            (verts_up, verts_down, verts_limit_up, verts_limit_down,
             segments_up, segments_down, segments_limit_up, segments_limit_down) = \
                self.build_candle_groups(data, xvals, is_limit_up, is_limit_down)

            # 修改：实现经典的阳线空心，阴线实心样式
            if len(verts_up) > 0:
                # 阳线（上涨）：空心，只有红色边框
                collection_up = PolyCollection(
                    verts_up, facecolor='none', edgecolor=up_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_up)

            if len(verts_down) > 0:
                # 阴线（下跌）：实心绿色
                collection_down = PolyCollection(
                    verts_down, facecolor=down_color, edgecolor=down_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_down)

            if len(verts_limit_up) > 0:
                # 涨停（橙色）：空心 + 加粗边框突出
                collection_limit_up = PolyCollection(
                    verts_limit_up, facecolor='none', edgecolor=limit_up_color,
                    linewidth=1.4, alpha=alpha)
                ax.add_collection(collection_limit_up)

            if len(verts_limit_down) > 0:
                # 跌停（紫色）：空心 + 加粗边框突出
                collection_limit_down = PolyCollection(
                    verts_limit_down, facecolor='none', edgecolor=limit_down_color,
                    linewidth=1.4, alpha=alpha)
                ax.add_collection(collection_limit_down)

            if len(segments_up) > 0:  # 上涨影线
                collection_shadow_up = LineCollection(
                    segments_up, colors=up_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_shadow_up)

            if len(segments_down) > 0:  # 下跌影线
                collection_shadow_down = LineCollection(
                    segments_down, colors=down_color, linewidth=1, alpha=alpha)
                ax.add_collection(collection_shadow_down)

            if len(segments_limit_up) > 0:  # 涨停影线（加粗）
                collection_shadow_limit_up = LineCollection(
                    segments_limit_up, colors=limit_up_color, linewidth=1.4, alpha=alpha)
                ax.add_collection(collection_shadow_limit_up)

            if len(segments_limit_down) > 0:  # 跌停影线（加粗）
                collection_shadow_limit_down = LineCollection(
                    segments_limit_down, colors=limit_down_color, linewidth=1.4, alpha=alpha)
                ax.add_collection(collection_shadow_limit_down)

            ax.autoscale_view()
            return (collection_up, collection_down, collection_limit_up,
                    collection_limit_down, collection_shadow_up,
                    collection_shadow_down, collection_shadow_limit_up,
                    collection_shadow_limit_down)
        except Exception as e:
            logger.error(f"_render_candlesticks_efficient失败: {e}")
            return None

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
            colls = self._render_volume_vectorized(ax, plot_data, style or {}, x, use_datetime_axis)
            self._optimize_display(ax)
            return colls
        except Exception as e:
            self.render_error.emit(f"绘制成交量失败: {str(e)}")
            return None

    @staticmethod
    def build_volume_groups(data: pd.DataFrame, xvals: np.ndarray,
                            bar_width: float = 0.3, is_limit_up=None, is_limit_down=None):
        """构建成交量四色柱顶点（HV6 提取，全量渲染与 tick 增量更新共用）。

        向量化构建，返回 4 个 (N,4,2) numpy 数组：up/down/limit_up/limit_down。
        is_limit_up/is_limit_down 为 None 时按列优先/内部判定（与渲染链同规则）。
        """
        volumes = data['volume'].values
        closes = data['close'].values
        opens = data['open'].values
        highs = data['high'].values
        lows = data['low'].values
        lefts = xvals - bar_width / 2
        rights = xvals + bar_width / 2
        if is_limit_up is None or is_limit_down is None:
            if 'limit_up' in data.columns and 'limit_down' in data.columns:
                is_limit_up = data['limit_up'].to_numpy(dtype=bool)
                is_limit_down = data['limit_down'].to_numpy(dtype=bool)
            else:
                is_limit_up, is_limit_down = classify_limit_up_down(
                    closes, highs, lows, extract_symbol(data))
        is_up = closes >= opens
        up_indices = np.where(is_up & ~is_limit_up & ~is_limit_down)[0]
        down_indices = np.where((~is_up) & ~is_limit_up & ~is_limit_down)[0]
        limit_up_indices = np.where(is_limit_up)[0]
        limit_down_indices = np.where(is_limit_down)[0]

        def build(indices):
            if len(indices) == 0:
                return np.empty((0, 4, 2))
            verts = np.empty((len(indices), 4, 2), dtype=np.float64)
            verts[:, 0, 0] = lefts[indices]
            verts[:, 0, 1] = 0
            verts[:, 1, 0] = lefts[indices]
            verts[:, 1, 1] = volumes[indices]
            verts[:, 2, 0] = rights[indices]
            verts[:, 2, 1] = volumes[indices]
            verts[:, 3, 0] = rights[indices]
            verts[:, 3, 1] = 0
            return verts

        return (build(up_indices), build(down_indices),
                build(limit_up_indices), build(limit_down_indices))

    def _render_volume_vectorized(self, ax, data: pd.DataFrame, style: Dict[str, Any], x: np.ndarray = None, use_datetime_axis: bool = False):
        """使用向量化高效渲染成交量，支持datetime X轴和等距序号X轴
        移植自gui/widgets/chart_renderer.py的_render_volume_efficient实现

        Returns:
            HV6 tick 增量渲染：返回 4 元组 collections 引用
            (up, down, limit_up, limit_down)，元素为 None 表示该类别为空。
        """
        collection_up = collection_down = None
        collection_limit_up = collection_limit_down = None
        # R292-HV4：与 fallback 链键语义统一——volume_* 专属键优先，回退 K 线
        # 同款 up/down（默认值与 K 线一致，用户可单独定制成交量涨跌色）。
        up_color = style.get('volume_up_color') or style.get('up_color', '#ff0000')
        down_color = style.get('volume_down_color') or style.get('down_color', '#00ff00')
        limit_up_color = style.get('limit_up_color', '#FF9800')    # 涨停橙色
        limit_down_color = style.get('limit_down_color', '#AB47BC')  # 跌停紫色
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
        elif use_datetime_axis and isinstance(data.index, pd.DatetimeIndex):
            # R292 修复：仅 datetime 轴才允许 date2num(索引)；数字轴一律序号，
            # 否则与K线轴（序号）不一致且 date2num 数值出视野
            xvals = mdates.date2num(data.index.to_pydatetime())
        else:
            xvals = np.arange(len(data))

        # 计算柱状图宽度（与K线图保持一致）
        if use_datetime_axis and len(xvals) > 1:
            avg_interval = np.mean(np.diff(xvals))
            bar_width = max(0.3, avg_interval * 0.6)
        else:
            bar_width = 0.3

        # HV6 提取：向量化构建（含列优先 limit 掩码）由 build_volume_groups 承担，
        # 全量渲染与 tick 增量更新（set_verts 重建）共用，杜绝逻辑漂移。
        (verts_up, verts_down, verts_limit_up, verts_limit_down) = \
            self.build_volume_groups(data, xvals, bar_width)
        # 性能优化：检查数组长度而不是转换为bool（避免numpy警告）
        if len(verts_up) > 0:
            collection_up = PolyCollection(
                verts_up, facecolor=up_color, edgecolor='none', alpha=alpha)
            ax.add_collection(collection_up)
        if len(verts_down) > 0:
            collection_down = PolyCollection(
                verts_down, facecolor=down_color, edgecolor='none', alpha=alpha)
            ax.add_collection(collection_down)
        if len(verts_limit_up) > 0:
            # 涨停柱（橙色）
            collection_limit_up = PolyCollection(
                verts_limit_up, facecolor=limit_up_color, edgecolor='none', alpha=alpha)
            ax.add_collection(collection_limit_up)
        if len(verts_limit_down) > 0:
            # 跌停柱（紫色）
            collection_limit_down = PolyCollection(
                verts_limit_down, facecolor=limit_down_color, edgecolor='none', alpha=alpha)
            ax.add_collection(collection_limit_down)
        return (collection_up, collection_down,
                collection_limit_up, collection_limit_down)
        # 性能优化：移除autoscale_view()调用，由调用方统一处理
        # ax.autoscale_view()  # 已移除，在rendering_mixin中统一调用

    def render_line(self, ax, data: pd.Series, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True):
        """高性能线图绘制
        Args:
            ax: matplotlib轴对象
            data: 数据序列
            style: 样式字典
            x: 可选，X轴数据（与其他渲染器接口对齐；为None时按索引/日期自动推导）
            use_datetime_axis: 是否使用datetime X轴（预留，与其他渲染器对齐）
        """
        try:
            self._render_line_efficient(ax, data, style or {}, x)
        except Exception as e:
            self.render_error.emit(f"绘制线图失败: {str(e)}")

    def _render_line_efficient(self, ax, data: pd.Series, style: Dict[str, Any], x: np.ndarray = None):
        """高效渲染线图"""
        color = style.get('color', '#1976d2')
        linewidth = style.get('linewidth', 0.4)
        alpha = style.get('alpha', 0.85)
        label = style.get('label', '')

        # 处理不同的数据类型
        if x is not None:
            # 调用方显式传入X轴数据（等距序号），直接对齐使用
            y_values = data.values if hasattr(data, 'values') else np.asarray(data)
            x_values = x
        elif isinstance(data, pd.Series):
            # pandas Series
            y_values = data.values
            if data.index.equals(pd.RangeIndex(start=0, stop=len(data))):
                # 如果索引是范围索引，直接使用值作为横坐标
                x_values = np.arange(len(y_values))
            else:
                try:
                    # 如果索引是日期类型
                    x_values = mdates.date2num(data.index.to_pydatetime())
                except Exception:
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

# 导出接口
__all__ = [
    'RenderPriority',
    'RenderTask',
    'ChartRenderer',
    'get_chart_renderer',
    'initialize_chart_renderer',
    'shutdown_chart_renderer',
]
