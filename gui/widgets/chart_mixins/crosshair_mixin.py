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
            if idx > 0:
                prev_close = kdata.iloc[idx-1]['close']
                change = row['close'] - prev_close
                change_pct = (change / prev_close) * 100
                if change > 0:
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

            # 获取文本颜色
            text_color = self._get_change_color(change_symbol)

            return info, text_color

        except Exception as e:
            logger.error(f"创建十字光标信息失败: {str(e)}")
            return "信息加载失败", self._get_default_text_color()

    def _get_change_color(self, change_symbol: str) -> str:
        """根据涨跌符号获取颜色"""
        try:
            colors = self.theme_manager.get_theme_colors()
            if change_symbol == "-":
                return colors.get('up_color', '#00ff00')
            elif change_symbol == "+":
                return colors.get('down_color', '#ff0000')
            else:
                return colors.get('chart_text', '#ffffff')
        except Exception:
            # 默认颜色
            if change_symbol == "-":
                return '#00ff00'
            elif change_symbol == "+":
                return '#ff0000'
            else:
                return '#ffffff'

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

            # 定义需要的线条及其对应的子图
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

            # X轴标签（日期）
            date_str = self._safe_format_date(row, idx, kdata)
            if self.indicator_ax is not None:
                if self._crosshair_xtext is None:
                    self._crosshair_xtext = self.indicator_ax.text(
                        x_val, +1, date_str,
                        transform=self.indicator_ax.get_xaxis_transform(),
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
                    except Exception:
                        pass
            self._crosshair_lines.clear()

            # 清除文本
            for attr in ['_crosshair_text', '_crosshair_xtext', '_crosshair_ytext']:
                if hasattr(self, attr) and getattr(self, attr) is not None:
                    try:
                        getattr(self, attr).remove()
                    except Exception:
                        pass
                    setattr(self, attr, None)

        except Exception as e:
            logger.error(f"清除十字光标元素失败: {str(e)}")

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
                    event.inaxes not in [self.price_ax, self.volume_ax, self.indicator_ax] or
                    self.current_kdata is None or
                    len(self.current_kdata) == 0 or
                        event.xdata is None):
                    self._hide_crosshair_elements()
                    self.canvas.draw_idle()
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

                # 刷新画布
                self.canvas.draw_idle()

            def on_mouse_move(event):
                # 性能优化P3：延迟初始化十字光标到用户首次交互时
                if hasattr(self, '_crosshair_needs_init') and self._crosshair_needs_init:
                    if not hasattr(self, '_crosshair_initialized') or not self._crosshair_initialized:
                        logger.debug("用户首次交互，初始化十字光标")
                        self.enable_crosshair(force_rebind=False)
                    self._crosshair_needs_init = False
                
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
