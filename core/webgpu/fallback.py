from loguru import logger
"""
多层降级渲染器模块

提供完整的渲染后备方案：
WebGPU → OpenGL → Canvas 2D → matplotlib

确保在任何环境下都能正常工作
"""

import time
from typing import Dict, Any, Optional, Protocol, List
from abc import ABC, abstractmethod
from enum import Enum
import numpy as np
import pandas as pd

# R292 涨跌停精确判定（按板块计算涨/跌停价，替代固定 4.8% 阈值）
from core.rendering.limit_price import classify_limit_up_down, extract_symbol

# 导入虚拟滚动渲染器和数据采样优化器
try:
    from core.optimization.volume_virtual_renderer import VolumeVirtualRenderer
    from core.advanced_optimization.performance.virtualization import VirtualRenderStyle
    VIRTUAL_SCROLL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"虚拟滚动渲染器不可用: {e}")
    VIRTUAL_SCROLL_AVAILABLE = False
    VolumeVirtualRenderer = None
    VirtualRenderStyle = None

try:
    from core.optimization.data_sampling_optimizer import AdaptiveDataOptimizer, SamplingConfig, SamplingStrategy
    DATA_SAMPLING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"数据采样优化器不可用: {e}")
    DATA_SAMPLING_AVAILABLE = False
    AdaptiveDataOptimizer = None
    SamplingConfig = None
    SamplingStrategy = None

try:
    from core.monitoring.performance_monitor import get_performance_monitor, init_performance_monitor
    PERFORMANCE_MONITOR_AVAILABLE = True
    # 初始化全局性能监控
    _performance_monitor = init_performance_monitor({'auto_report': False})
except ImportError as e:
    logger.warning(f"性能监控系统不可用: {e}")
    PERFORMANCE_MONITOR_AVAILABLE = False
    get_performance_monitor = None
    init_performance_monitor = None
    _performance_monitor = None

from .compatibility import CompatibilityReport
from .environment import GPUSupportLevel


class RenderBackend(Enum):
    """渲染后端类型"""
    OPENGL = "opengl"
    WEBGL = "webgl"
    WEBGPU = "webgpu"
    CANVAS2D = "canvas2d"
    MATPLOTLIB = "matplotlib"

class ChartRenderer(Protocol):
    """图表渲染器协议"""

    def render_candlesticks(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染K线图"""
        ...

    def render_volume(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染成交量"""
        ...

    def render_line(self, ax, data: pd.Series, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染线图"""
        ...

    def clear(self) -> None:
        """清空渲染内容"""
        ...

    def get_performance_info(self) -> Dict[str, Any]:
        """获取性能信息"""
        ...

class BaseRenderer(ABC):
    """渲染器基类"""

    def __init__(self, backend: RenderBackend):
        self.backend = backend
        self._initialized = False
        self._performance_stats = {
            'render_count': 0,
            'total_render_time': 0.0,
            'average_render_time': 0.0,
            'last_render_time': 0.0,
            'memory_usage_mb': 0.0
        }

    @abstractmethod
    def initialize(self, context: Optional[Any] = None) -> bool:
        """初始化渲染器"""
        pass

    @abstractmethod
    def render_candlesticks(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染K线图"""
        pass

    @abstractmethod
    def render_volume(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染成交量"""
        pass

    @abstractmethod
    def render_line(self, ax, data: pd.Series, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染线图"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空渲染内容"""
        pass

    def get_performance_info(self) -> Dict[str, Any]:
        """获取性能信息"""
        return {
            'backend': self.backend.value,
            'initialized': self._initialized,
            **self._performance_stats
        }

    def _update_performance_stats(self, render_time: float):
        """更新性能统计"""
        self._performance_stats['render_count'] += 1
        self._performance_stats['total_render_time'] += render_time
        self._performance_stats['last_render_time'] = render_time
        self._performance_stats['average_render_time'] = (
            self._performance_stats['total_render_time'] /
            self._performance_stats['render_count']
        )



class MatplotlibRenderer(BaseRenderer):
    """Matplotlib渲染器 - 集成虚拟滚动优化"""

    def __init__(self):
        super().__init__(RenderBackend.MATPLOTLIB)
        self._figure = None
        self._axes = None
        
        # R292-HV2：不再启用成交量虚拟滚动（_volume_virtual_renderer 保持 None）。
        # 性能决策（用户实测：接口修正启用后系统严重卡顿）：
        #   ① VirtualScrollRenderer.__init__ 无条件启动 60fps QTimer（virtualization.py
        #      L627-629）→ 每图表实例每 16ms 执行 _render_loop（request_chunk 聚合 +
        #      data_rendered 信号）→ 多图表叠加持续占用主线程；
        #   ② fallback.render_volume 每次渲染前无条件 set_volume_data →
        #      VirtualScrollRenderer.set_data_source（virtualization.py L660-661）每次
        #      chunks.clear() + _clear_cache() → chunk 缓存永远 miss，每次全量重建；
        #   ③ _render_chunk（volume_virtual_renderer.py L361-377）逐柱 Python 循环
        #      （chunk_size 默认 2000 → 每 chunk 2000 次 append）→ 大行情每次刷新极慢。
        # 常规渲染路径（下方 render_volume）为 numpy 向量化 PolyCollection，且四色
        # 列优先（limit_up/limit_down 列）已修，性能与颜色均满足需求。
        self._volume_virtual_renderer = None
        
        # 数据采样优化器
        self._data_optimizer = None
        if DATA_SAMPLING_AVAILABLE:
            self._data_optimizer = AdaptiveDataOptimizer()
            logger.info("Matplotlib渲染器已启用数据采样优化")

    def initialize(self, context: Optional[Any] = None) -> bool:
        """初始化Matplotlib渲染器"""
        try:
            logger.info("初始化Matplotlib渲染器...")

            # 使用现有的图表组件
            if context and hasattr(context, 'figure'):
                self._figure = context.figure
                if hasattr(context, 'price_ax'):
                    self._axes = {
                        'price': context.price_ax,
                        'volume': getattr(context, 'volume_ax', None),
                        'indicator': getattr(context, 'indicator_ax', None)
                    }

            # 初始化虚拟滚动渲染器
            if self._volume_virtual_renderer and self._axes and self._axes['volume']:
                # 设置成交量轴数据
                volume_data = pd.DataFrame({'volume': [0]})  # 初始化空数据
                self._volume_virtual_renderer.set_volume_data(volume_data, self._axes['volume'])
                logger.info("成交量虚拟滚动渲染器已配置")

            self._initialized = True
            logger.info("Matplotlib渲染器初始化成功")
            return True

        except Exception as e:
            logger.error(f"Matplotlib渲染器初始化失败: {e}")
            return False

    def render_candlesticks(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染K线图 - 使用高效matplotlib实现"""
        if not self._initialized:
            return False

        # 导入必要的模块
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.collections import LineCollection, PolyCollection
        from matplotlib.colors import to_rgba
        
        try:
            start_time = time.time()
            
            # 默认样式
            if style is None:
                style = {}
                
            up_color = style.get('up_color', '#ff0000')
            down_color = style.get('down_color', '#00ff00')
            # R292 修复：fallback 链 MatplotlibRenderer 补四色（涨红/跌绿/涨停橙/跌停紫），
            # 与 optimization/chart_renderer.py 判定一致（按板块精确涨/跌停价）。
            limit_up_color = style.get('limit_up_color', '#FF9800')
            limit_down_color = style.get('limit_down_color', '#AB47BC')
            alpha = style.get('alpha', 1.0)
            
            # 使用给定的x参数或根据datetime轴标志选择适当的x轴
            if x is not None:
                xvals = x
            elif use_datetime_axis:
                # 处理datetime轴
                try:
                    if 'datetime' in data.columns:
                        datetime_series = pd.to_datetime(data['datetime'])
                        xvals = mdates.date2num(datetime_series)
                    else:
                        # 检查索引类型
                        if hasattr(data.index, 'to_pydatetime'):
                            xvals = mdates.date2num(data.index.to_pydatetime())
                        elif pd.api.types.is_datetime64_any_dtype(data.index):
                            xvals = mdates.date2num(pd.to_datetime(data.index).to_pydatetime())
                        else:
                            # 如果不是日期索引，使用序号
                            logger.debug(f"索引类型不是日期类型: {type(data.index)}，使用序号作为X轴")
                            xvals = np.arange(len(data))
                except Exception as e:
                    logger.debug(f"转换日期失败，使用序号作为X轴: {e}")
                    xvals = np.arange(len(data))
            else:
                xvals = np.arange(len(data))

            # 确保必要的列存在
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [
                col for col in required_columns if col not in data.columns]
            if missing_columns:
                logger.warning(
                    f"MatplotlibRenderer: 数据缺少必要列: {missing_columns}")
                return False

            opens = data['open'].values
            closes = data['close'].values
            highs = data['high'].values
            lows = data['low'].values

            candle_width = 0.6
            lefts = xvals - candle_width / 2
            rights = xvals + candle_width / 2

            is_up = closes >= opens
            # R292-HV4：列优先读取 limit 掩码（与同链 render_volume L491-499、
            # optimization 链 K线/成交量一致）——'limit_up'/'limit_down' 列由上游
            # （rendering_mixin.update_chart）在降采样前按全量数据计算并随切片保留；
            # 降采样后相邻K线并非真实相邻交易日，内部重判的"昨收"会错位导致
            # 涨停橙/跌停紫与成交量不一致（铁律㉑：所有渲染路径共享列优先分类列）。
            if 'limit_up' in data.columns and 'limit_down' in data.columns:
                is_limit_up = data['limit_up'].to_numpy(dtype=bool)
                is_limit_down = data['limit_down'].to_numpy(dtype=bool)
            else:
                is_limit_up, is_limit_down = classify_limit_up_down(
                    closes, highs, lows, extract_symbol(data))
            up_indices = np.where(is_up & ~is_limit_up & ~is_limit_down)[0]
            down_indices = np.where((~is_up) & ~is_limit_up & ~is_limit_down)[0]
            limit_up_indices = np.where(is_limit_up)[0]
            limit_down_indices = np.where(is_limit_down)[0]

            def _build_candle_verts(indices_arr):
                if len(indices_arr) == 0:
                    return np.empty((0, 4, 2))
                n = len(indices_arr)
                verts = np.empty((n, 4, 2), dtype=np.float64)
                verts[:, 0, 0] = lefts[indices_arr]
                verts[:, 0, 1] = opens[indices_arr]
                verts[:, 1, 0] = lefts[indices_arr]
                verts[:, 1, 1] = closes[indices_arr]
                verts[:, 2, 0] = rights[indices_arr]
                verts[:, 2, 1] = closes[indices_arr]
                verts[:, 3, 0] = rights[indices_arr]
                verts[:, 3, 1] = opens[indices_arr]
                return verts

            def _build_shadow_segments(indices_arr):
                if len(indices_arr) == 0:
                    return np.empty((0, 2, 2))
                n = len(indices_arr)
                segments = np.empty((n, 2, 2), dtype=np.float64)
                segments[:, 0, 0] = xvals[indices_arr]
                segments[:, 0, 1] = lows[indices_arr]
                segments[:, 1, 0] = xvals[indices_arr]
                segments[:, 1, 1] = highs[indices_arr]
                return segments

            verts_up = _build_candle_verts(up_indices)
            verts_down = _build_candle_verts(down_indices)
            verts_limit_up = _build_candle_verts(limit_up_indices)
            verts_limit_down = _build_candle_verts(limit_down_indices)
            segments_up = _build_shadow_segments(up_indices)
            segments_down = _build_shadow_segments(down_indices)
            segments_limit_up = _build_shadow_segments(limit_up_indices)
            segments_limit_down = _build_shadow_segments(limit_down_indices)

            if ax:
                if len(verts_up) > 0:
                    collection_up = PolyCollection(
                        verts_up, facecolor='none', edgecolor=up_color, linewidth=1, alpha=alpha)
                    ax.add_collection(collection_up)

                if len(verts_down) > 0:
                    collection_down = PolyCollection(
                        verts_down, facecolor=down_color, edgecolor=down_color, linewidth=1, alpha=alpha)
                    ax.add_collection(collection_down)

                if len(verts_limit_up) > 0:
                    collection_limit_up = PolyCollection(
                        verts_limit_up, facecolor='none', edgecolor=limit_up_color, linewidth=1.4, alpha=alpha)
                    ax.add_collection(collection_limit_up)

                if len(verts_limit_down) > 0:
                    collection_limit_down = PolyCollection(
                        verts_limit_down, facecolor='none', edgecolor=limit_down_color, linewidth=1.4, alpha=alpha)
                    ax.add_collection(collection_limit_down)

                if len(segments_up) > 0:
                    collection_shadow_up = LineCollection(
                        segments_up, colors=up_color, linewidth=1, alpha=alpha)
                    ax.add_collection(collection_shadow_up)

                if len(segments_down) > 0:
                    collection_shadow_down = LineCollection(
                        segments_down, colors=down_color, linewidth=1, alpha=alpha)
                    ax.add_collection(collection_shadow_down)

                if len(segments_limit_up) > 0:
                    collection_shadow_limit_up = LineCollection(
                        segments_limit_up, colors=limit_up_color, linewidth=1.2, alpha=alpha)
                    ax.add_collection(collection_shadow_limit_up)

                if len(segments_limit_down) > 0:
                    collection_shadow_limit_down = LineCollection(
                        segments_limit_down, colors=limit_down_color, linewidth=1.2, alpha=alpha)
                    ax.add_collection(collection_shadow_limit_down)

                if len(data) > 0:
                    ax.autoscale_view()

            render_time = time.time() - start_time
            self._update_performance_stats(render_time)

            logger.debug(f"Matplotlib渲染K线图: {len(data)}个数据点，耗时 {render_time*1000:.2f}ms")
            return True

        except Exception as e:
            logger.error(f"Matplotlib K线渲染失败: {e}")
            return False

    def render_volume(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染成交量 - 优先使用数据采样优化和虚拟滚动"""
        if not self._initialized:
            return False

        try:
            start_time = time.time()

            # 获取性能监控器
            perf_monitor = get_performance_monitor() if PERFORMANCE_MONITOR_AVAILABLE else None

            # 首先进行数据采样优化
            original_data_size = len(data)
            optimized_data = data
            
            if self._data_optimizer and original_data_size > 2000:
                # 对大数据进行采样优化
                try:
                    optimized_data = self._data_optimizer.optimize_for_performance(
                        data, render_time_target=100.0  # 目标100ms内完成
                    )
                    optimization_time = time.time() - start_time
                    
                    compression_ratio = len(optimized_data) / original_data_size
                    logger.info(f"数据采样优化: {original_data_size} -> {len(optimized_data)} "
                               f"(压缩比: {compression_ratio:.2%}, 优化耗时: {optimization_time*1000:.2f}ms)")
                    
                except Exception as opt_error:
                    logger.warning(f"数据采样优化失败: {opt_error}，使用原始数据")
                    optimized_data = data

            logger.debug(f"Matplotlib渲染成交量: {len(optimized_data)}个数据点 (原始: {original_data_size})")

            if ax and len(optimized_data) > 0:
                # 首先尝试使用虚拟滚动渲染器
                if self._volume_virtual_renderer and self._volume_virtual_renderer.is_enabled:
                    try:
                        # R292 bug 修复：每次渲染前无条件刷新数据源（原逻辑仅首次设置，
                        # 切周期/刷行情后 volume_data 停留在旧数据，成交量显示过期值）
                        self._volume_virtual_renderer.set_volume_data(optimized_data, ax)
                        
                        # 使用虚拟滚动渲染（使用优化后的数据）。
                        # R292-HV：方法名修正——VolumeVirtualRenderer 真实接口为
                        # render_with_virtual_scroll（volume_virtual_renderer.py L128-133，
                        # 内部 _render_regular/_render_virtual 分派）。原
                        # render_volume_with_virtual_scroll 不存在 → 运行时每次必抛
                        # AttributeError 被 except 吞掉静默降级常规渲染，虚拟滚动
                        # 成交量优化从未真正生效（本轮修复后首次走虚拟滚动路径）。
                        success = self._volume_virtual_renderer.render_with_virtual_scroll(
                            ax, optimized_data, style, x, use_datetime_axis)
                        
                        if success:
                            render_time = time.time() - start_time
                            self._update_performance_stats(render_time)
                            logger.debug(f"虚拟滚动成交量渲染完成: {len(optimized_data)}个数据点，耗时 {render_time*1000:.2f}ms")
                            return True
                        else:
                            logger.debug("虚拟滚动渲染失败，降级到常规渲染")
                            
                    except Exception as virtual_error:
                        logger.warning(f"虚拟滚动成交量渲染失败: {virtual_error}，降级到常规渲染")
                        # 继续使用常规渲染
                
                # 降级到常规渲染（优化版本）
                from matplotlib.collections import PolyCollection
                
                # 获取数据（使用优化后的数据）
                x_values = x if x is not None else np.arange(len(optimized_data))
                volumes = optimized_data['volume'].values

                if style is None:
                    style = {}

                # R292 四色：涨红/跌绿/涨停橙/跌停紫，判定与 K 线一致
                # （volume_* 专属键优先，回退到 K 线同款 up/down 键；color 旧键仍兼容）
                up_color = style.get('volume_up_color') or style.get('up_color', '#ff0000')
                down_color = style.get('volume_down_color') or style.get('down_color', '#00ff00')
                limit_up_color = style.get('limit_up_color', '#FF9800')
                limit_down_color = style.get('limit_down_color', '#AB47BC')
                color = style.get('color', up_color)
                alpha = style.get('alpha', 0.7)
                edge_color = style.get('edge_color', '#000000')
                edge_width = style.get('edge_width', 0.5)
                bar_width = style.get('width', 0.8)

                nonzero_mask = volumes > 0
                if not np.any(nonzero_mask):
                    logger.debug("没有有效的成交量数据需要渲染")
                else:
                    nonzero_indices = np.where(nonzero_mask)[0]
                    n_bars = len(nonzero_indices)
                    verts = np.empty((n_bars, 4, 2), dtype=np.float64)
                    x_vals_nz = x_values[nonzero_indices]
                    vol_nz = volumes[nonzero_indices]

                    half_w = bar_width / 2
                    verts[:, 0, 0] = x_vals_nz - half_w
                    verts[:, 0, 1] = 0
                    verts[:, 1, 0] = x_vals_nz - half_w
                    verts[:, 1, 1] = vol_nz
                    verts[:, 2, 0] = x_vals_nz + half_w
                    verts[:, 2, 1] = vol_nz
                    verts[:, 3, 0] = x_vals_nz + half_w
                    verts[:, 3, 1] = 0

                    # 四色分类（数据含 open/close 列时生效，判定与 K 线一致）
                    categories = None
                    if 'open' in optimized_data.columns and 'close' in optimized_data.columns:
                        closes = optimized_data['close'].values.astype(np.float64)
                        opens = optimized_data['open'].values.astype(np.float64)
                        is_up = closes >= opens
                        categories = np.where(is_up[nonzero_indices], 1, 0).astype(np.int8)
                        if 'high' in optimized_data.columns and 'low' in optimized_data.columns:
                            # R292-HV：列优先读取 limit 掩码（与 optimization/chart_renderer.py
                            # K线/成交量一致）。'limit_up'/'limit_down' 列由上游
                            # （rendering_mixin.update_chart）在降采样前按全量数据计算，
                            # 降采样后相邻K线并非真实相邻交易日，内部重判的"昨收"会错位
                            # 导致涨停橙/跌停紫与K线不一致；列缺失时回退内部判定。
                            if ('limit_up' in optimized_data.columns
                                    and 'limit_down' in optimized_data.columns):
                                is_limit_up = optimized_data['limit_up'].to_numpy(dtype=bool)
                                is_limit_down = optimized_data['limit_down'].to_numpy(dtype=bool)
                            else:
                                is_limit_up, is_limit_down = classify_limit_up_down(
                                    closes, optimized_data['high'].values.astype(np.float64),
                                    optimized_data['low'].values.astype(np.float64),
                                    extract_symbol(optimized_data))
                            # 优先级：涨停 → limit_up_color、跌停 → limit_down_color，与 K 线一致
                            categories = np.where(
                                is_limit_down[nonzero_indices], 3,
                                np.where(is_limit_up[nonzero_indices], 2, categories))

                    if callable(color):
                        max_vol = vol_nz.max() if len(vol_nz) > 0 else 1
                        if max_vol == 0:
                            max_vol = 1
                        normalized = vol_nz / max_vol
                        colors_arr = [color(v) for v in normalized]
                        collection = PolyCollection(
                            verts, facecolors=colors_arr, edgecolors=edge_color,
                            linewidths=edge_width, alpha=alpha)
                    elif categories is not None:
                        # 四色：0=跌绿 1=涨红 2=涨停橙 3=跌停紫
                        color_map = np.array([down_color, up_color, limit_up_color, limit_down_color])
                        collection = PolyCollection(
                            verts, facecolors=color_map[categories].tolist(), edgecolors=edge_color,
                            linewidths=edge_width, alpha=alpha)
                    else:
                        collection = PolyCollection(
                            verts, facecolors=color, edgecolors=edge_color,
                            linewidths=edge_width, alpha=alpha)

                    ax.add_collection(collection)
                    ax.autoscale_view()
                    logger.debug(f"PolyCollection成交量渲染完成: {n_bars}个柱子")

            render_time = time.time() - start_time
            self._update_performance_stats(render_time)

            return True

        except Exception as e:
            logger.error(f"Matplotlib成交量渲染失败: {e}")
            return False

    def render_line(self, ax, data: pd.Series, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染线图"""
        if not self._initialized:
            return False

        try:
            start_time = time.time()

            logger.debug(f"Matplotlib渲染线图: {len(data)}个数据点")

            if ax:
                x = np.arange(len(data))
                color = style.get('color', 'blue') if style else 'blue'
                ax.plot(x, data, color=color, linewidth=1.0)

            render_time = time.time() - start_time
            self._update_performance_stats(render_time)

            return True

        except Exception as e:
            logger.error(f"Matplotlib线图渲染失败: {e}")
            return False

    def clear(self) -> None:
        """清空渲染内容"""
        if self._initialized and self._axes:
            for ax in self._axes.values():
                if ax:
                    ax.clear()
            logger.debug("Matplotlib清空渲染内容")

class FallbackRenderer:
    """多层降级渲染器"""

    def __init__(self):
        self._renderers = {}
        self._current_renderer = None
        self._fallback_chain = []
        self._failure_count = {}
        self._compatibility_report = None  # 保存兼容性报告

        # 创建所有渲染器实例
        self._create_renderers()

    def _create_renderers(self):
        """创建所有渲染器实例（WebGPU渲染器由WebGPUManager单独管理，避免重复创建）
        已清理 OpenGL/Canvas2D stub 假成功渲染器，仅保留真实 Matplotlib 兜底"""
        self._renderers = {
            RenderBackend.MATPLOTLIB: MatplotlibRenderer()
        }

        # 初始化失败计数（只针对实际创建的渲染器）
        for backend in self._renderers.keys():
            self._failure_count[backend] = 0

    def initialize(self, compatibility_report: CompatibilityReport, context: Optional[Any] = None) -> bool:
        """
        根据兼容性报告初始化渲染器

        Args:
            compatibility_report: 兼容性报告
            context: 渲染上下文
            
        Returns:
            是否初始化成功
        """
        logger.info("初始化多层降级渲染器...")

        # 保存兼容性报告以供后续使用
        self._compatibility_report = compatibility_report

        # 确定降级链
        self._fallback_chain = self._determine_fallback_chain(compatibility_report)

        # 尝试按照降级链初始化渲染器
        for backend in self._fallback_chain:
            # 跳过WebGPU后端，因为它由WebGPUManager单独管理
            if backend == RenderBackend.WEBGPU:
                continue
                
            # 检查渲染器是否存在
            if backend not in self._renderers:
                logger.warning(f"渲染器 {backend.value} 不存在，跳过初始化")
                continue
                
            renderer = self._renderers[backend]

            logger.info(f"尝试初始化 {backend.value} 渲染器...")

            if hasattr(renderer, 'initialize'):
                if renderer.initialize(context):
                    self._current_renderer = renderer
                    logger.info(f"使用 {backend.value} 渲染器")
                    return True
                else:
                    logger.warning(f"{backend.value} 渲染器初始化失败")
                    self._failure_count[backend] += 1

        logger.error("所有渲染器初始化失败")
        return False

    def _determine_fallback_chain(self, compatibility_report: CompatibilityReport) -> List[RenderBackend]:
        """确定降级链"""

        # 如果兼容性报告为None或无效，创建默认推荐后端
        if compatibility_report is None:
            recommended = GPUSupportLevel.WEBGPU
        else:
            recommended = compatibility_report.recommended_backend

        if recommended == GPUSupportLevel.WEBGPU:
            return [RenderBackend.WEBGPU, RenderBackend.MATPLOTLIB]
        else:  # WEBGL / NATIVE / BASIC 均走 Matplotlib 兜底
            return [RenderBackend.MATPLOTLIB]

    def render_candlesticks(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染K线图"""
        return self._render_with_fallback('render_candlesticks', ax, data, style, x, use_datetime_axis)

    def render_volume(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染成交量"""
        return self._render_with_fallback('render_volume', ax, data, style, x, use_datetime_axis)

    def render_line(self, ax, data: pd.Series, style: Dict[str, Any] = None, x: np.ndarray = None, use_datetime_axis: bool = True) -> bool:
        """渲染线图"""
        return self._render_with_fallback('render_line', ax, data, style, x, use_datetime_axis)

    def _render_with_fallback(self, method_name: str, *args, **kwargs) -> bool:
        """带降级的渲染"""
        if not self._current_renderer:
            logger.error("没有可用的渲染器")
            return False

        try:
            # 尝试使用当前渲染器
            method = getattr(self._current_renderer, method_name)
            if method(*args, **kwargs):
                return True
            else:
                logger.warning(f"当前渲染器 {self._current_renderer.backend.value} 渲染失败")
                return self._try_fallback(method_name, *args, **kwargs)

        except Exception as e:
            logger.error(f"渲染器 {self._current_renderer.backend.value} 渲染异常: {e}")
            self._failure_count[self._current_renderer.backend] += 1
            return self._try_fallback(method_name, *args, **kwargs)

    def _try_fallback(self, method_name: str, *args, **kwargs) -> bool:
        """尝试降级渲染"""
        current_backend = self._current_renderer.backend

        # 在降级链中找到当前渲染器的位置
        try:
            current_index = self._fallback_chain.index(current_backend)
        except ValueError:
            current_index = -1

        # 尝试后续的渲染器
        for i in range(current_index + 1, len(self._fallback_chain)):
            backend = self._fallback_chain[i]
            
            # 跳过WebGPU后端，因为它由WebGPUManager单独管理
            if backend == RenderBackend.WEBGPU:
                continue
                
            # 检查渲染器是否存在
            if backend not in self._renderers:
                logger.warning(f"渲染器 {backend.value} 不存在，跳过降级")
                continue
                
            renderer = self._renderers[backend]

            logger.info(f"降级到 {backend.value} 渲染器")

            # 如果渲染器未初始化，尝试初始化
            if not renderer._initialized:
                if not renderer.initialize():
                    continue

            try:
                method = getattr(renderer, method_name)
                if method(*args, **kwargs):
                    self._current_renderer = renderer
                    logger.info(f"降级到 {backend.value} 渲染器成功")
                    return True
            except Exception as e:
                logger.warning(f"降级渲染器 {backend.value} 也失败: {e}")
                self._failure_count[backend] += 1
                continue

        logger.error("所有降级渲染器都失败")
        return False

    def clear(self) -> None:
        """清空渲染内容"""
        if self._current_renderer:
            self._current_renderer.clear()

    def get_current_backend(self) -> Optional[RenderBackend]:
        """获取当前使用的渲染后端"""
        return self._current_renderer.backend if self._current_renderer else None

    def get_performance_info(self) -> Dict[str, Any]:
        """获取性能信息"""
        info = {
            'current_backend': self.get_current_backend().value if self.get_current_backend() else None,
            'fallback_chain': [backend.value for backend in self._fallback_chain],
            'failure_counts': {backend.value: count for backend, count in self._failure_count.items()},
            'renderers': {}
        }

        # 收集各个渲染器的性能信息
        for backend, renderer in self._renderers.items():
            info['renderers'][backend.value] = renderer.get_performance_info()

        return info

    def force_fallback(self, target_backend: RenderBackend = None) -> bool:
        """强制降级到指定后端"""
        if target_backend is None:
            # 降级到下一个后端
            current_backend = self._current_renderer.backend
            try:
                current_index = self._fallback_chain.index(current_backend)
                if current_index + 1 < len(self._fallback_chain):
                    target_backend = self._fallback_chain[current_index + 1]
                else:
                    logger.warning("已经是最后一个后端，无法继续降级")
                    return False
            except ValueError:
                logger.error("当前后端不在降级链中")
                return False

        # 切换到目标后端
        if target_backend in self._renderers:
            target_renderer = self._renderers[target_backend]
            if target_renderer._initialized or target_renderer.initialize():
                self._current_renderer = target_renderer
                logger.info(f"强制切换到 {target_backend.value} 渲染器")
                return True

        logger.error(f"无法切换到 {target_backend.value} 渲染器")
        return False
