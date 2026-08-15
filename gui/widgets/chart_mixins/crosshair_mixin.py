from loguru import logger
"""
图表控件十字光标功能Mixin

该模块包含ChartWidget的十字光标相关功能，包括：
- 十字光标启用/禁用
- 光标信息显示
- 光标线条更新
- 轴标签更新
- 光标元素清理
"""

import time
from typing import Tuple, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

from optimization.update_throttler import get_update_throttler
# R292 涨跌停精确判定（按板块计算涨/跌停价，与 K 线渲染各路径一致）
from core.rendering.limit_price import is_limit_up_down, extract_symbol

class CrosshairMixin:
    """十字光标功能Mixin

    包含ChartWidget的十字光标显示、信息提示、线条更新等功能
    """

    def __init__(self):
        """初始化十字光标相关变量"""
        super().__init__()
        # 十字光标相关变量
        # 改为字典管理，键为 'price_v', 'volume_v', 'indicator_v', 'price_h'
        self._crosshair_lines = {}  # 明确初始化为空字典
        self._crosshair_text = None
        self._crosshair_xtext = None
        self._crosshair_ytext = None
        self._last_crosshair_update_time = 0
        self._crosshair_event_id = None  # 存储事件连接ID，避免重复绑定
        self._crosshair_initialized = False  # 跟踪十字光标是否已初始化
        self._blit_background = None  # R265: 十字光标blit局部重绘背景缓存（None=需重建）
        # R266: blit性能采样（每60次移动打一次均值日志，验证R265局部重绘加速效果）
        self._blit_perf_count = 0
        self._blit_perf_total = 0.0
        self._blit_perf_max = 0.0

        # 获取节流器实例
        self.throttler = get_update_throttler()

    def enable_crosshair(self, force_rebind=False):
        """启用十字光标功能"""
        try:
            # 性能优化：检查是否已经启用，避免重复调用
            if not force_rebind and hasattr(self, '_crosshair_initialized') and self._crosshair_initialized:
                if hasattr(self, 'crosshair_enabled') and self.crosshair_enabled:
                    logger.debug("十字光标已启用，跳过重复初始化")
                    return
            
            logger.info("启用十字光标功能...")

            if not hasattr(self, 'crosshair_enabled') or not self.crosshair_enabled:
                logger.info("十字光标功能未启用，跳过。")
                return

            # 确保_crosshair_lines和_crosshair_event_id属性存在
            if not hasattr(self, '_crosshair_lines'):
                self._crosshair_lines = {}
                logger.info("初始化_crosshair_lines属性")

            if not hasattr(self, '_crosshair_event_id'):
                self._crosshair_event_id = None
                logger.info("初始化_crosshair_event_id属性")

            # 清除现有的十字光标元素
            self._clear_crosshair_elements()

            # 创建统一的鼠标移动处理器（避免重复绑定）
            if self._crosshair_event_id is None or force_rebind:
                self._create_unified_crosshair_handler()

            # 标记十字光标已初始化
            self._crosshair_initialized = True

            # 限制X轴范围
            self._limit_xlim()

        except Exception as e:
            logger.error(f"启用十字光标失败: {str(e)}")

    def reset_crosshair(self):
        """
        重置十字光标状态 - 在图表数据更新后调用
        确保十字光标在图表更新后仍然正常工作
        
        性能优化：避免不必要的重置，只在真正需要时重置
        """
        try:
            # 性能优化：如果十字光标未启用，直接返回
            if not hasattr(self, 'crosshair_enabled') or not self.crosshair_enabled:
                logger.debug("十字光标未启用，跳过重置")
                return
            
            # 性能优化：如果已经初始化且状态正常，可能不需要完全重置
            # 只清除元素，不重新绑定事件（减少事件连接开销）
            if hasattr(self, '_crosshair_initialized') and self._crosshair_initialized:
                logger.debug("十字光标已初始化，只清除元素")
                self._clear_crosshair_elements()
                # 不重置_crosshair_initialized，避免重新绑定事件
                return
            
            logger.info("重置十字光标状态...")

            # 确保_crosshair_lines是字典类型
            if not isinstance(self._crosshair_lines, dict):
                self._crosshair_lines = {}
                logger.warning("_crosshair_lines不是字典类型，已重置为空字典")

            # 清除现有的十字光标元素
            self._clear_crosshair_elements()

            # 重置初始化状态
            self._crosshair_initialized = False

            # 重新启用十字光标（只在真正需要时）
            if hasattr(self, 'crosshair_enabled') and self.crosshair_enabled:
                self.enable_crosshair(force_rebind=True)
                logger.info("十字光标已重置并启用")
        except Exception as e:
            logger.error(f"重置十字光标失败: {e}")

    def _limit_xlim(self):
        """限制X轴范围，防止越界"""
        try:
            if self.current_kdata is not None and len(self.current_kdata) > 0:
                max_x = len(self.current_kdata) - 1
                for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                    if ax is not None:
                        current_xlim = ax.get_xlim()
                        new_xlim = (max(0, current_xlim[0]), min(
                            max_x, current_xlim[1]))
                        ax.set_xlim(new_xlim)
        except Exception as e:
            logger.error(f"限制X轴范围失败: {str(e)}")

    def _create_crosshair_info_text(self, row, idx: int, kdata) -> Tuple[str, str]:
        """创建十字光标信息文本 - 集成信号提示"""
        try:
            # 获取日期字符串
            date_str = self._safe_format_date(row, idx, kdata)

            # 计算涨跌幅
            is_limit_up = False
            is_limit_down = False
            if idx > 0:
                prev_close = kdata.iloc[idx-1]['close']
                change = row['close'] - prev_close
                change_pct = (change / prev_close) * 100
                # R292：涨停/跌停判定与K线渲染一致——按板块精确涨/跌停价
                # （core/rendering/limit_price.py，替代固定 4.8% 阈值，
                # 消除主板 5~9.9% 大阳线误判）
                is_limit_up, is_limit_down = is_limit_up_down(
                    prev_close, row['close'], row['high'], row['low'],
                    extract_symbol(kdata))
                if is_limit_up:
                    change_symbol = "+"
                    change_str = f"↑+{change:.3f} (+{change_pct:.2f}%) 涨停"
                elif is_limit_down:
                    change_symbol = "-"
                    change_str = f"↓{change:.3f} ({change_pct:.2f}%) 跌停"
                elif change > 0:
                    change_symbol = "+"
                    change_str = f"↑+{change:.3f} (+{change_pct:.2f}%)"
                elif change < 0:
                    change_symbol = "-"
                    change_str = f"↓{change:.3f} ({change_pct:.2f}%)"
                else:
                    change_symbol = ""
                    change_str = "0.000 (0.00%)"
            else:
                change_symbol = ""
                change_str = "0.000 (0.00%)"

            # 构建基础信息文本
            info = (
                f"日期: {date_str}\n"
                f"开盘: {row['open']:.3f}  收盘: {row['close']:.3f}\n"
                f"最高: {row['high']:.3f}  最低: {row['low']:.3f}\n"
                f"涨跌: {change_str}\n"
                f"成家量: {row['volume']:.0f}"
            )

            # 检查是否有信号提示信息需要添加
            signal_info = ""
            if hasattr(self, 'get_signal_tooltip_at_index'):
                signal_info = self.get_signal_tooltip_at_index(idx)
                if signal_info:
                    info += f"\n\n--- 交易信号 ---\n{signal_info}"

            # 检查是否有形态识别信息需要添加
            pattern_info = ""
            if hasattr(self, '_pattern_info') and idx in self._pattern_info:
                pattern_data = self._pattern_info[idx]
                pattern_info = f"\n\n--- 形态识别 ---\n"
                pattern_info += f"形态: {pattern_data.get('pattern_name', 'Unknown')}\n"
                pattern_info += f"信号: {pattern_data.get('signal', 'neutral')}\n"
                pattern_info += f"置信度: {pattern_data.get('confidence', 0):.3f}"
                info += pattern_info

            # 获取文本颜色（R292：涨停橙/跌停紫与K线渲染一致）
            text_color = self._get_change_color(change_symbol, is_limit_up, is_limit_down)

            return info, text_color

        except Exception as e:
            logger.error(f"创建十字光标信息失败: {str(e)}")
            return "信息加载失败", self._get_default_text_color()

    def _get_change_color(self, change_symbol: str, is_limit_up: bool = False, is_limit_down: bool = False) -> str:
        """根据涨跌符号获取颜色（中国市场：涨=红、跌=绿、涨停=橙、跌停=紫，与K线渲染严格一致）

        R265 修复：原实现键名语义颠倒（下跌取 up_color / 上涨取 down_color）且使用
        主题中不存在的 up_color/down_color 键，仅靠"颠倒逻辑+颠倒默认值"负负得正。
        现改为与 rendering_mixin._get_chart_style 相同的 k_up/k_down 键。
        R292 扩展：涨停/跌停单独取色 k_limit_up（橙）/k_limit_down（紫），
        is_limit_up/is_limit_down 带默认值以兼容单参调用。
        """
        try:
            colors = self.theme_manager.get_theme_colors()
            if is_limit_up:
                return colors.get('k_limit_up', '#FF9800')
            elif is_limit_down:
                return colors.get('k_limit_down', '#AB47BC')
            elif change_symbol == "+":
                return colors.get('k_up', '#e74c3c')
            elif change_symbol == "-":
                return colors.get('k_down', '#27ae60')
            else:
                return colors.get('chart_text', '#222b45')
        except Exception:
            # 默认颜色
            if is_limit_up:
                return '#FF9800'
            elif is_limit_down:
                return '#AB47BC'
            elif change_symbol == "+":
                return '#e74c3c'
            elif change_symbol == "-":
                return '#27ae60'
            else:
                return '#222b45'

    def _get_default_text_color(self) -> str:
        """获取默认文本颜色"""
        try:
            colors = self.theme_manager.get_theme_colors()
            return colors.get('chart_text', '#ffffff')
        except Exception:
            return '#ffffff'

    def _get_primary_color(self) -> str:
        """获取主题色"""
        try:
            colors = self.theme_manager.get_theme_colors()
            return colors.get('primary', '#1976d2')
        except Exception:
            return '#1976d2'

    def _update_crosshair_lines(self, x_val: float, y_val: float, primary_color: str):
        """更新十字光标线条 - 修复多条线问题"""
        try:
            # 检查图表是否已更新但十字光标未重新初始化
            if not self._crosshair_initialized:
                logger.info("检测到十字光标未初始化，正在重新初始化...")
                self.enable_crosshair(force_rebind=True)

            # 确保_crosshair_lines是字典类型
            if not isinstance(self._crosshair_lines, dict):
                logger.warning(f"_crosshair_lines类型错误: {type(self._crosshair_lines)}，重置为空字典")
                self._crosshair_lines = {}

            # 定义需要的线条及其对应的子图（R283: 移除 indicator_ax2 垂直线）
            line_configs = [
                ('price_v', self.price_ax, 'vertical'),
                ('volume_v', self.volume_ax, 'vertical'),
                ('indicator_v', self.indicator_ax, 'vertical'),
                ('price_h', self.price_ax, 'horizontal')
            ]

            for line_key, ax, line_type in line_configs:
                if ax is None:
                    continue

                # 如果线条不存在，创建新的
                if line_key not in self._crosshair_lines:
                    if line_type == 'vertical':
                        line = ax.axvline(x_val, color=primary_color, lw=1.2,
                                          ls='--', alpha=0.55, visible=True, zorder=100)
                    else:  # horizontal
                        line = ax.axhline(y_val, color=primary_color, lw=1.2,
                                          ls='--', alpha=0.55, visible=True, zorder=100)
                    self._crosshair_lines[line_key] = line
                else:
                    # 更新现有线条
                    line = self._crosshair_lines[line_key]
                    if line_type == 'vertical':
                        line.set_xdata([x_val, x_val])
                    else:  # horizontal - 只在主图显示横线
                        if line_key == 'price_h':
                            line.set_ydata([y_val, y_val])
                    line.set_color(primary_color)
                    line.set_visible(True)

        except Exception as e:
            logger.error(f"更新十字光标线条失败: {str(e)}")

    def _update_crosshair_text(self, event, x_val: float, y_val: float, info: str, text_color: str):
        """更新十字光标信息文本 - 修复悬浮框位置问题，让其跟随鼠标"""
        try:
            # 确保_crosshair_text属性存在
            if not hasattr(self, '_crosshair_text'):
                self._crosshair_text = None
                logger.info("初始化_crosshair_text属性")

            # 计算悬浮框位置 - 跟随鼠标但避免超出边界
            ax = self.price_ax
            if ax is None:
                return

            # 获取坐标轴范围
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()

            # 计算相对位置（0-1范围）
            x_rel = (x_val - xlim[0]) / (xlim[1] - xlim[0])
            y_rel = (y_val - ylim[0]) / (ylim[1] - ylim[0])

            # 动态调整悬浮框位置，避免超出边界
            if x_rel > 0.7:  # 鼠标在右侧，悬浮框显示在左侧
                text_x = x_rel - 0.05
                ha = 'right'
            else:  # 鼠标在左侧，悬浮框显示在右侧
                text_x = x_rel + 0.05
                ha = 'left'

            if y_rel > 0.7:  # 鼠标在上方，悬浮框显示在下方
                text_y = y_rel - 0.05
                va = 'top'
            else:  # 鼠标在下方，悬浮框显示在上方
                text_y = y_rel + 0.05
                va = 'bottom'

            # 确保位置在有效范围内
            text_x = max(0.02, min(0.98, text_x))
            text_y = max(0.02, min(0.98, text_y))

            if self._crosshair_text is None:
                # 创建信息文本框
                self._crosshair_text = ax.text(
                    text_x, text_y, info,
                    transform=ax.transAxes,
                    va=va, ha=ha,
                    fontsize=8.5,
                    color=text_color,  # #585d58
                    bbox=dict(facecolor='#fff', alpha=0.5, edgecolor='#1976d2',
                              boxstyle='round,pad=0.5', linewidth=0.8),
                    zorder=200
                )
            else:
                # 更新现有文本
                self._crosshair_text.set_position((text_x, text_y))
                self._crosshair_text.set_text(info)
                self._crosshair_text.set_color(text_color)
                self._crosshair_text.set_ha(ha)
                self._crosshair_text.set_va(va)
                self._crosshair_text.set_visible(True)

        except Exception as e:
            logger.error(f"更新十字光标文本失败: {str(e)}")

    def _update_crosshair_axis_labels(self, row, idx: int, kdata, x_val: float, y_val: float, primary_color: str):
        """更新十字光标轴标签"""
        try:
            # 确保_crosshair_xtext和_crosshair_ytext属性存在
            if not hasattr(self, '_crosshair_xtext'):
                self._crosshair_xtext = None
                logger.info("初始化_crosshair_xtext属性")

            if not hasattr(self, '_crosshair_ytext'):
                self._crosshair_ytext = None
                logger.info("初始化_crosshair_ytext属性")

            # X轴标签（日期）——画在最底部子图（indicator_ax，指标窗）（R283: 3轴布局）
            date_str = self._safe_format_date(row, idx, kdata)
            x_ax = self.indicator_ax
            if x_ax is not None:
                if self._crosshair_xtext is None:
                    self._crosshair_xtext = x_ax.text(
                        x_val, +1, date_str,
                        transform=x_ax.get_xaxis_transform(),
                        ha='center', va='top',
                        fontsize=8,
                        color=primary_color,
                        bbox=dict(facecolor='#fff', alpha=0.8,
                                  edgecolor=primary_color, boxstyle='round,pad=0.2'),
                        zorder=200
                    )
                else:
                    self._crosshair_xtext.set_position((x_val, +1))
                    self._crosshair_xtext.set_text(date_str)
                    self._crosshair_xtext.set_color(primary_color)
                    self._crosshair_xtext.set_visible(True)

            # Y轴标签（价格）
            if self.price_ax is not None:
                price_str = f"{y_val:.3f}"
                if self._crosshair_ytext is None:
                    self._crosshair_ytext = self.price_ax.text(
                        +0.03, y_val, price_str,
                        transform=self.price_ax.get_yaxis_transform(),
                        ha='right', va='center',
                        fontsize=8,
                        color=primary_color,
                        bbox=dict(facecolor='#fff', alpha=0.8,
                                  edgecolor=primary_color, boxstyle='round,pad=0.2'),
                        zorder=200
                    )
                else:
                    self._crosshair_ytext.set_position((+0.03, y_val))
                    self._crosshair_ytext.set_text(price_str)
                    self._crosshair_ytext.set_color(primary_color)
                    self._crosshair_ytext.set_visible(True)

        except Exception as e:
            logger.error(f"更新十字光标轴标签失败: {str(e)}")

    def _hide_crosshair_elements(self):
        """隐藏十字光标元素"""
        try:
            # 确保所有属性存在
            if not hasattr(self, '_crosshair_lines'):
                self._crosshair_lines = {}

            if not hasattr(self, '_crosshair_text'):
                self._crosshair_text = None

            if not hasattr(self, '_crosshair_xtext'):
                self._crosshair_xtext = None

            if not hasattr(self, '_crosshair_ytext'):
                self._crosshair_ytext = None

            # 确保_crosshair_lines是字典类型
            if not isinstance(self._crosshair_lines, dict):
                logger.warning(f"_crosshair_lines类型错误: {type(self._crosshair_lines)}，重置为空字典")
                self._crosshair_lines = {}
                return

            # 隐藏线条
            for line in self._crosshair_lines.values():
                if line is not None:
                    line.set_visible(False)

            # 隐藏文本
            if self._crosshair_text:
                self._crosshair_text.set_visible(False)
            if self._crosshair_xtext:
                self._crosshair_xtext.set_visible(False)
            if self._crosshair_ytext:
                self._crosshair_ytext.set_visible(False)

        except Exception as e:
            logger.error(f"隐藏十字光标元素失败: {str(e)}")

    def _clear_crosshair_elements(self):
        """清除十字光标元素"""
        try:
            # 确保_crosshair_lines属性存在
            if not hasattr(self, '_crosshair_lines'):
                self._crosshair_lines = {}
                logger.info("初始化_crosshair_lines属性")
                return

            # 确保_crosshair_lines是字典类型
            if not isinstance(self._crosshair_lines, dict):
                logger.warning(f"_crosshair_lines类型错误: {type(self._crosshair_lines)}，重置为空字典")
                self._crosshair_lines = {}
                return

            # 清除线条
            for line in self._crosshair_lines.values():
                if line is not None:
                    try:
                        line.remove()
                    except Exception as e:
                        logger.debug(f"crosshair_mixin: {e}")
            self._crosshair_lines.clear()

            # 清除文本
            for attr in ['_crosshair_text', '_crosshair_xtext', '_crosshair_ytext']:
                if hasattr(self, attr) and getattr(self, attr) is not None:
                    try:
                        getattr(self, attr).remove()
                    except Exception as e:
                        logger.debug(f"crosshair_mixin: {e}")
                    setattr(self, attr, None)

        except Exception as e:
            logger.error(f"清除十字光标元素失败: {str(e)}")
        finally:
            # R265: 十字元素移除后，blit背景失效需重建
            self._invalidate_crosshair_background()

    def _invalidate_crosshair_background(self):
        """使十字光标blit背景失效（任何全量重绘后必须调用，否则恢复错位背景）"""
        self._blit_background = None

    def _blit_crosshair(self) -> bool:
        """十字光标局部重绘（blit）：仅重绘十字光标相关artist，避免每帧全画布draw_idle

        R265 性能修复：原实现每次鼠标移动都 canvas.draw_idle() 全画布重绘，
        重绘成本 ∝ 画布artist数量（K线+指标线+MACD柱状图），指标越多越卡。
        blit 方案：先缓存一次干净背景，之后 restore_region + draw_artist 只重绘
        十字线条/文本，性能提升一个数量级。失败时自动回退 draw_idle。

        R266 性能日志：blit 路径逐帧采样（每60次打均值/最大耗时日志）；
        背景重建（全画布 draw+copy）与回退 draw_idle 打单次耗时，用于对比验证加速效果。
        """
        _t_start = time.perf_counter()
        try:
            if self.canvas is None or self.figure is None:
                return False
            if self._blit_background is None:
                # 建立干净背景：隐藏十字元素 → draw → copy（背景不含十字线）
                self._hide_crosshair_elements()
                self.canvas.draw()
                self._blit_background = self.canvas.copy_from_bbox(self.figure.bbox)
                _bg_ms = (time.perf_counter() - _t_start) * 1000
                logger.info(
                    f"[PERF][Crosshair] blit背景重建(全画布draw+copy): {_bg_ms:.2f}ms "
                    f"— 仅首次/全量重绘后发生，对比每帧blit局部重绘通常<1ms")
            self.canvas.restore_region(self._blit_background)
            for line in self._crosshair_lines.values():
                if line is not None and line.get_visible() and line.axes is not None:
                    line.axes.draw_artist(line)
            for artist in [self._crosshair_text, self._crosshair_xtext, self._crosshair_ytext]:
                if artist is not None and artist.get_visible() and artist.axes is not None:
                    artist.axes.draw_artist(artist)
            self.canvas.blit(self.figure.bbox)
            self._accumulate_blit_perf(time.perf_counter() - _t_start)
            return True
        except Exception as e:
            logger.debug(f"十字光标blit重绘失败，回退draw_idle: {e}")
            self._blit_background = None
            _t_fb = time.perf_counter()
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            _fb_ms = (time.perf_counter() - _t_fb) * 1000
            logger.warning(
                f"[PERF][Crosshair] blit失败回退全画布draw_idle: {_fb_ms:.2f}ms")
            return False

    def _accumulate_blit_perf(self, elapsed: float):
        """累计blit耗时采样，每60次移动输出一次均值/最大值日志（避免每帧刷屏干扰性能）"""
        self._blit_perf_count = getattr(self, '_blit_perf_count', 0) + 1
        self._blit_perf_total = getattr(self, '_blit_perf_total', 0.0) + elapsed
        self._blit_perf_max = max(getattr(self, '_blit_perf_max', 0.0), elapsed)
        if self._blit_perf_count >= 60:
            avg_ms = (self._blit_perf_total / self._blit_perf_count) * 1000
            max_ms = self._blit_perf_max * 1000
            logger.info(
                f"[PERF][Crosshair] blit局部重绘: 最近60次移动 "
                f"avg={avg_ms:.3f}ms max={max_ms:.3f}ms "
                f"(全画布draw_idle通常数十~数百ms，指标/K线越多差异越大，验证R265加速生效)")
            self._blit_perf_count = 0
            self._blit_perf_total = 0.0
            self._blit_perf_max = 0.0

    def _create_unified_crosshair_handler(self):
        """创建统一的十字光标处理器 - 避免重复绑定"""
        try:
            # 确保canvas属性存在
            if not hasattr(self, 'canvas') or self.canvas is None:
                logger.warning("canvas属性不存在或为None，无法创建十字光标处理器")
                return

            def do_update(event_data):
                """实际执行更新的函数"""
                event = event_data['event']

                # 获取主题色
                primary_color = self._get_primary_color()

                # 检查事件有效性
                if (not event.inaxes or
                    event.inaxes not in [self.price_ax, self.volume_ax, self.indicator_ax,
                                         getattr(self, 'indicator_ax2', None)] or
                    self.current_kdata is None or
                    len(self.current_kdata) == 0 or
                        event.xdata is None):
                    self._hide_crosshair_elements()
                    # R265: blit局部重绘（背景已缓存时无需全画布draw）
                    if self._blit_background is None:
                        self.canvas.draw_idle()
                    else:
                        self._blit_crosshair()
                    return

                # 获取数据
                kdata = self.current_kdata
                idx = int(max(0, min(len(kdata)-1, round(event.xdata))))
                row = kdata.iloc[idx]
                x_val = idx
                y_val = row['close']

                # 更新十字光标线条
                self._update_crosshair_lines(x_val, y_val, primary_color)

                # 创建信息文本
                info, text_color = self._create_crosshair_info_text(row, idx, kdata)

                # 更新信息文本
                self._update_crosshair_text(event, x_val, y_val, info, text_color)

                # 更新轴标签
                self._update_crosshair_axis_labels(row, idx, kdata, x_val, y_val, primary_color)

                # R265 性能：使用blit局部重绘，避免每帧全画布draw_idle
                if not self._blit_crosshair():
                    self.canvas.draw_idle()

            def on_mouse_move(event):
                # 性能优化P3：延迟初始化十字光标到用户首次交互时
                if hasattr(self, '_crosshair_needs_init') and self._crosshair_needs_init:
                    if not hasattr(self, '_crosshair_initialized') or not self._crosshair_initialized:
                        logger.debug("用户首次交互，初始化十字光标")
                        self.enable_crosshair(force_rebind=False)
                    self._crosshair_needs_init = False
                
                # 性能优化：基于帧率的节流机制，限制最高更新频率约60fps
                current_time = time.time()
                if current_time - self._last_crosshair_update_time < 0.016:
                    return
                self._last_crosshair_update_time = current_time
                
                # [最终诊断] 添加日志，检查事件是否被接收
                logger.debug(f"Crosshair event: x={event.x}, y={event.y}, inaxes={event.inaxes}")

                # 绕过有问题的节流阀，直接调用更新函数
                do_update({'event': event})

            # 断开之前的连接（如果存在）
            if hasattr(self, '_crosshair_event_id') and self._crosshair_event_id is not None:
                try:
                    self.canvas.mpl_disconnect(self._crosshair_event_id)
                except Exception as e:
                    logger.warning(f"断开十字光标事件连接失败: {e}")

            # 绑定新的事件处理器
            self._crosshair_event_id = self.canvas.mpl_connect(
                'motion_notify_event', on_mouse_move)

        except Exception as e:
            logger.error(f"创建十字光标处理器失败: {str(e)}")

    def disable_crosshair(self):
        """禁用十字光标功能"""
        try:
            # 清除所有十字光标元素
            if hasattr(self, '_clear_crosshair_elements'):
                self._clear_crosshair_elements()
            else:
                logger.warning("_clear_crosshair_elements方法不存在，无法清除十字光标元素")

            # 断开事件连接
            if hasattr(self, '_crosshair_event_id') and self._crosshair_event_id is not None:
                if hasattr(self, 'canvas') and self.canvas is not None:
                    try:
                        self.canvas.mpl_disconnect(self._crosshair_event_id)
                    except Exception as e:
                        logger.warning(f"断开十字光标事件连接失败: {e}")
                self._crosshair_event_id = None

            # 刷新画布
            if hasattr(self, 'canvas') and self.canvas is not None:
                self.canvas.draw_idle()

        except Exception as e:
            logger.error(f"禁用十字光标失败: {str(e)}")
