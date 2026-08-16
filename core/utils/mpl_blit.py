# -*- coding: utf-8 -*-
"""
matplotlib blit 局部重绘引擎（R267 blit 推广基础设施）

背景：R265 十字光标接入 blit 局部重绘（copy_from_bbox → restore_region →
draw_artist → blit）后，高频交互场景性能提升一个数量级（基准约 350 倍）。

本引擎将 R265/R266 验证过的约定提炼为可复用组件，供订单簿深度图、监控图表等
高频 matplotlib UI 接入，避免各组件重复实现：
1. 背景缓存 + 失效：canvas.draw() 后 copy_from_bbox 缓存干净背景；任何全量重绘
   （ax.clear / tight_layout / resize / 数据清空 / 坐标轴范围变化）后必须调用 invalidate()
2. 失败回退：blit 异常时置空背景并回退 canvas.draw_idle()，绝不抛错影响业务
3. 性能采样：每 N 次成功 blit 打一次均值日志（[PERF] 前缀），量化加速效果
4. 无头兼容：canvas 缺失或异常环境自动回退 draw_idle（测试/后台场景安全）
"""
import time

from loguru import logger


class BlitEngine:
    """matplotlib 局部重绘引擎

    Args:
        canvas: matplotlib canvas（FigureCanvas 或 mock）
        bbox_getter: 返回需要 blit 的 bbox 的可调用对象（默认 canvas.figure.bbox）
        log_tag: 日志前缀标签（如 '[DepthChart]'）
        sample_every: 性能采样间隔（次），0 表示禁用采样日志
    """

    def __init__(self, canvas, bbox_getter=None, log_tag='', sample_every=60):
        self.canvas = canvas
        self._bbox_getter = bbox_getter or (lambda: canvas.figure.bbox)
        self._log_tag = log_tag
        self._sample_every = sample_every
        self._background = None
        self._count = 0
        self._total = 0.0
        self._max = 0.0
        self._bg_rebuild_count = 0

    def invalidate(self):
        """使 blit 背景失效。

        任何全量重绘后必须调用：ax.clear()、tight_layout()、坐标轴范围变化、
        resize、数据清空、系列数变化等。下次 render() 会自动重建背景。
        """
        self._background = None

    @property
    def background_cached(self) -> bool:
        """背景快照是否已缓存。

        R292-HV5 统一 blit：调用方（如十字光标）需要在 render 前判断"本次是否将
        重建背景"——重建前可执行专属预处理（如隐藏临时元素以保证背景干净），
        且"背景已缓存"时可直接走 blit 快路径而不触发全画布 draw。
        """
        return self._background is not None

    def refresh_background(self):
        """同步背景快照为当前画布像素（render 成功后调用）。

        HV6 tick 增量渲染：集合 verts 更新后 render 只重绘了本次 artists，
        背景快照仍停留在旧像素；若不同步，下一次十字光标 blit 会
        restore_region 回旧快照，导致 bar 内 tick 更新像素级回退。
        """
        try:
            if self.canvas is None or self._background is None:
                return
            self._background = self.canvas.copy_from_bbox(self._bbox_getter())
        except Exception:
            pass

    def render(self, artists):
        """执行 blit 局部重绘：restore_region + draw_artist + blit。

        背景未缓存（首次或 invalidate 后）时先全量 draw + copy_from_bbox 重建。
        异常时置空背景并回退 draw_idle，返回 False；成功返回 True。
        """
        _t = time.perf_counter()
        try:
            if self.canvas is None:
                return False
            if self._background is None:
                self.canvas.draw()
                self._background = self.canvas.copy_from_bbox(self._bbox_getter())
                self._bg_rebuild_count += 1
                # 背景重建耗时日志节流：每 5 次重建打一条（高频组件避免刷屏）
                if self._bg_rebuild_count % 5 == 1:
                    bg_ms = (time.perf_counter() - _t) * 1000
                    logger.info(
                        f"[PERF]{self._log_tag} blit背景重建(全画布draw+copy): "
                        f"{bg_ms:.2f}ms 第{self._bg_rebuild_count}次 "
                        f"— 仅首次/全量重绘后发生，对比每帧blit通常<1ms")
            self.canvas.restore_region(self._background)
            for artist in artists:
                if artist is None:
                    continue
                get_visible = getattr(artist, 'get_visible', None)
                axes = getattr(artist, 'axes', None)
                if get_visible is None or axes is None:
                    continue
                if get_visible():
                    axes.draw_artist(artist)
            self.canvas.blit(self._bbox_getter())
            self._accumulate(time.perf_counter() - _t)
            return True
        except Exception as e:
            logger.debug(f"{self._log_tag} blit重绘失败，回退draw_idle: {e}")
            self._background = None
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            return False

    def _accumulate(self, elapsed):
        """累计 blit 耗时，每 sample_every 次输出一次均值/最大值日志"""
        if self._sample_every <= 0:
            return
        self._count += 1
        self._total += elapsed
        self._max = max(self._max, elapsed)
        if self._count >= self._sample_every:
            avg_ms = (self._total / self._count) * 1000
            max_ms = self._max * 1000
            logger.info(
                f"[PERF]{self._log_tag} blit局部重绘: 最近{self._count}次 "
                f"avg={avg_ms:.3f}ms max={max_ms:.3f}ms "
                f"(全画布draw_idle通常数十~数百ms，验证blit加速生效)")
            self._count = 0
            self._total = 0.0
            self._max = 0.0
