from loguru import logger
"""
图表渲染功能Mixin - 处理K线渲染、指标渲染、样式配置等功能
"""
import time
import numpy as np
import pandas as pd
import re
from typing import Dict, Any, Tuple, Optional, List
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 替换旧的指标系统导入
from core.indicator_adapter import get_indicator_english_name
from utils.theme import parse_color_for_matplotlib
# R292 涨跌停精确判定（按板块计算涨/跌停价，替代固定 4.8% 阈值）
from core.rendering.limit_price import classify_limit_up_down, extract_symbol


class IndicatorPerformanceOptimizer:
    """指标性能优化器 - 缓存和批量计算"""
    
    def __init__(self):
        self._precomputed_indicators = {}
        self._style_cache = {}
        self._cache_version = 0
        self._talib_module = None
        self._pattern_cache = {}
    
    def clear_cache(self):
        """清除所有缓存"""
        self._precomputed_indicators.clear()
        self._style_cache.clear()
        self._cache_version += 1
        self._pattern_cache.clear()
    
    def get_precomputed_indicators(self, kdata_hash, required_indicators):
        """获取预计算的指标"""
        cache_key = f"{kdata_hash}_{hash(str(required_indicators))}"
        return self._precomputed_indicators.get(cache_key, {})
    
    def cache_indicators(self, kdata_hash, required_indicators, results):
        """缓存指标计算结果"""
        cache_key = f"{kdata_hash}_{hash(str(required_indicators))}"
        self._precomputed_indicators[cache_key] = results
    
    def get_cached_style(self, name, index, theme_version):
        """获取缓存的样式"""
        cache_key = f"{name}_{index}_{theme_version}"
        return self._style_cache.get(cache_key)
    
    def cache_style(self, name, index, theme_version, style):
        """缓存样式"""
        cache_key = f"{name}_{index}_{theme_version}"
        self._style_cache[cache_key] = style
    
    @property
    def talib(self):
        """惰性加载talib模块"""
        if self._talib_module is None:
            try:
                import talib
                self._talib_module = talib
            except ImportError:
                self._talib_module = False
        return self._talib_module
    
    def get_cached_pattern(self, pattern_name):
        """获取缓存的正则表达式"""
        if pattern_name not in self._pattern_cache:
            if pattern_name == 'ma':
                self._pattern_cache[pattern_name] = re.compile(r'^MA(\d+)?$')
            elif pattern_name == 'builtin':
                self._pattern_cache[pattern_name] = {'MA', 'MACD', 'RSI', 'BOLL'}
        return self._pattern_cache[pattern_name]


class RenderingMixin:
    """图表渲染功能Mixin"""
    
    def __init__(self):
        """初始化渲染混入类"""
        super().__init__()
        # 初始化性能优化器
        self._performance_optimizer = IndicatorPerformanceOptimizer()
        # 预编译的正则表达式
        # 内置指标集合（用于快速匹配）
        self._builtin_indicators = {'MA', 'MACD', 'RSI', 'BOLL'}

    def _get_theme_colors(self):
        """获取主题颜色，自动处理rgba格式"""
        colors = self.theme_manager.get_theme_colors() if hasattr(self, 'theme_manager') else {}
        # 处理 rgba 颜色转换为 matplotlib 兼容格式
        for key in ['chart_background', 'chart_grid', 'chart_text', 'chart_positive', 'chart_negative']:
            if key in colors:
                colors[key] = parse_color_for_matplotlib(colors[key])
        return colors

    
    
    
    
    
    
    def update_chart(self, data: dict = None):
        """唯一K线渲染实现，X轴为等距序号，彻底消除节假日断层。"""
        try:
            if not data:
                return
            start_time = time.time()
            # 🔴 性能优化P1.4：降低日志级别，避免list()调用和DataFrame.head()打印
            logger.debug(f"RenderingMixin.update_chart接收到数据类型: {type(data)}")

            # 处理不同的数据字段格式，兼容kdata和kline_data
            kdata = None
            if 'kdata' in data:
                kdata = data['kdata']
                logger.debug(f"从'kdata'键获取数据，类型: {type(kdata)}")
            elif 'kline_data' in data:
                kdata = data['kline_data']
                logger.debug(f"从'kline_data'键获取数据，类型: {type(kdata)}")
            else:
                # 没有找到有效的K线数据
                logger.error("未找到有效的K线数据键")
                self.show_no_data("无K线数据")
                return

            # 处理嵌套的数据结构
            if isinstance(kdata, dict) and 'kline_data' in kdata:
                # 这是一个嵌套的数据结构，真正的K线数据在kline_data键中
                logger.debug(f"检测到嵌套的数据结构，从kline_data键中提取真正的K线数据")
                nested_kdata = kdata.get('kline_data')
                logger.debug(f"嵌套的K线数据类型: {type(nested_kdata)}")
                kdata = nested_kdata

            # 处理kdata是字典的情况
            if isinstance(kdata, dict):
                # 如果kdata是字典，尝试从中提取DataFrame
                logger.info(f"kdata是字典")

                if 'data' in kdata:
                    # 如果字典中有data键，使用它
                    df_data = kdata.get('data')
                    logger.debug(f"从字典的'data'键获取数据，类型: {type(df_data)}")

                    if isinstance(df_data, pd.DataFrame):
                        kdata = df_data
                        logger.debug(f"成功从字典的'data'键获取DataFrame，形状: {kdata.shape}")
                    elif isinstance(df_data, list) and df_data:
                        kdata = pd.DataFrame(df_data)
                        logger.debug(f"将列表转换为DataFrame，形状: {kdata.shape}")
                    else:
                        logger.error(f"字典中的'data'键内容无效: {type(df_data)}")
                        self.show_no_data(f"K线数据格式错误: {type(df_data)}")
                        return
                else:
                    # 尝试将整个字典转换为DataFrame
                    try:
                        kdata = pd.DataFrame([kdata])
                        logger.debug(f"将整个字典转换为DataFrame，形状: {kdata.shape}")
                    except Exception as e:
                        logger.error(f"无法将字典转换为DataFrame: {e}")
                        self.show_no_data("K线数据格式错误")
                        return

            # 记录处理后的kdata信息
            logger.debug(f"处理后的kdata类型: {type(kdata)}")
            if hasattr(kdata, 'shape'):
                logger.debug(f"处理后的kdata形状: {kdata.shape}")

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线类型转化完成，耗时: {render_time:.2f}ms")

            start_time = time.time()
            # 检查kdata是否包含必要的列
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if isinstance(kdata, pd.DataFrame):
                missing_columns = [col for col in required_columns if col not in kdata.columns]
                if missing_columns:
                    logger.error(f"K线数据缺少必要列: {missing_columns}")
                    self.show_no_data(f"K线数据缺少必要列: {', '.join(missing_columns)}")
                    return

            # R267: 降采样前保存完整原始数据，防止 current_kdata 被降采样结果覆盖导致数据永久丢失
            # （数据>1200条时，指标切换若基于已降采样的 current_kdata 重渲染，原始数据无法恢复）
            self._full_kdata = kdata

            # R292-HV 修正：涨跌停四色判定必须在降采样前用全量数据执行。
            # 降采样后相邻 K 线并非真实相邻交易日，"昨收"错位 → 涨停/跌停价计算错误
            # → 四色漏判。方案：全量计算 limit 掩码 → 附加为 limit_up/limit_down 布尔列
            # → 随降采样 iloc 切片保留 → 渲染路径优先读取该列（列缺失时回退内部重判，
            # 兼容直接传数据、未带 limit 列的调用方）。
            if isinstance(kdata, pd.DataFrame) and not kdata.empty:
                try:
                    if ('limit_up' not in kdata.columns
                            or 'limit_down' not in kdata.columns):
                        lu, ld = classify_limit_up_down(
                            kdata['close'].to_numpy(dtype=float),
                            kdata['high'].to_numpy(dtype=float),
                            kdata['low'].to_numpy(dtype=float),
                            extract_symbol(kdata))
                        kdata['limit_up'] = lu
                        kdata['limit_down'] = ld
                except Exception as e:
                    logger.debug(f"涨跌停掩码计算失败，回退渲染层重判: {e}")

            kdata = self._downsample_kdata(kdata)
            # R290 防御：dropna 仅对 K 线必要列过滤，避免 adj_type/adj_source 等
            # 辅助列为 NaN 时 how='any' 把全部行删除导致图表空白。
            kdata = kdata.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
            kdata = kdata.loc[~kdata.index.duplicated(keep='first')]

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线数据校验，耗时: {render_time:.2f}ms")

            start_time = time.time()
            self.current_kdata = kdata

            # 记录清理后的kdata信息
            logger.debug(f"清理后的kdata形状: {kdata.shape}")

            if not kdata.empty:
                self._ymin = float(kdata['low'].min())
                self._ymax = float(kdata['high'].max())
                logger.debug(f"Y轴范围: {self._ymin} - {self._ymax}")
            else:
                self._ymin = 0
                self._ymax = 1
                logger.warning("kdata为空，设置默认Y轴范围")

            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if ax is None:
                    continue
                for artist in ax.lines + ax.collections + ax.texts:
                    artist.remove()

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线price_ax，耗时: {render_time:.2f}ms")

            start_time = time.time()

            style = self._get_chart_style()
            x = np.arange(len(kdata))  # 用等距序号做X轴

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"K线style设置，耗时: {render_time:.2f}ms")

            start_time = time.time()

            # R277 修复：图表类型（K线图/分时图/美国线/收盘价）真实生效。
            # 原实现无条件渲染K线图（render_candlesticks），chart_type 在链路中被丢弃。
            chart_type = data.get('chart_type') or getattr(self, 'chart_type', None) or 'K线图'
            logger.info(f"渲染图表类型: {chart_type}, 数据条数: {len(kdata)}")

            # 记录渲染参数
            logger.debug(f"准备调用渲染器，x轴长度: {len(x)}")

            # 性能优化：延迟绘制 - 先完成所有渲染，最后统一绘制
            # 调用渲染器
            if chart_type == '美国线':
                try:
                    self._render_ohlc_bars(self.price_ax, kdata, style, x)
                    logger.debug("美国线渲染成功")
                except Exception as e:
                    logger.error(f"美国线渲染失败: {e}", exc_info=True)
                try:
                    self.renderer.render_volume(self.volume_ax, kdata, style, x=x)
                    logger.debug("成交量渲染成功")
                except Exception as e:
                    logger.error(f"成交量渲染失败: {e}", exc_info=True)
            elif chart_type == '收盘价':
                try:
                    self.renderer.render_line(self.price_ax, kdata['close'], style, x=x)
                    logger.debug("收盘价线渲染成功")
                except Exception as e:
                    logger.error(f"收盘价线渲染失败: {e}", exc_info=True)
            elif chart_type == '分时图':
                # 分时图：收盘价折线 + 成交量（简化实现，数据为所选周期K线）
                # R279 说明：当前"分时图"渲染的是所选周期（默认1分钟）的历史K线折线，
                # 并非实时行情推送。明确标注数据性质，避免用户误认为实时分时。
                try:
                    self.renderer.render_line(self.price_ax, kdata['close'], style, x=x)
                    logger.debug("分时图渲染成功")
                except Exception as e:
                    logger.error(f"分时图渲染失败: {e}", exc_info=True)
                try:
                    self.renderer.render_volume(self.volume_ax, kdata, style, x=x)
                    logger.debug("成交量渲染成功")
                except Exception as e:
                    logger.error(f"成交量渲染失败: {e}", exc_info=True)
                try:
                    self.price_ax.text(
                        0.99, 0.99, '历史K线 · 非实时行情',
                        transform=self.price_ax.transAxes, ha='right', va='top',
                        fontsize=9, color='#888888', alpha=0.85, zorder=200)
                except Exception as e:
                    logger.debug(f"分时图数据来源标注失败: {e}")
            else:  # K线图（默认）
                try:
                    self.renderer.render_candlesticks(self.price_ax, kdata, style, x=x)
                    logger.debug("K线渲染成功")
                except Exception as e:
                    logger.error(f"K线渲染失败: {e}", exc_info=True)
                    raise
                try:
                    self.renderer.render_volume(self.volume_ax, kdata, style, x=x)
                    logger.debug("成交量渲染成功")
                except Exception as e:
                    logger.error(f"成交量渲染失败: {e}", exc_info=True)
            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"图表类型[{chart_type}]渲染，耗时: {render_time:.2f}ms")

            start_time = time.time()

            # 性能优化P2.1：合并autoscale_view()调用 - 在所有渲染完成后统一调用
            # 统一设置所有轴（价格、成交量、指标）的自动缩放范围
            try:
                self.price_ax.autoscale_view()
                self.volume_ax.autoscale_view()
                if hasattr(self, 'indicator_ax') and self.indicator_ax:
                    self.indicator_ax.autoscale_view()
                logger.debug("统一调用autoscale_view()完成（3轴合并）")
            except Exception as e:
                logger.warning(f"autoscale_view()调用失败: {e}")

            # indicators_data（分析链预计算结果）不在此渲染：真实渲染由
            # _render_indicators 按 active_indicators 实时重算完成。R290 已清理
            # _render_indicator_data 死代码（其仅处理大写 MA/MACD 键，与实际生产
            # 数据的小写 ma5/rsi/macd/boll 格式不匹配，0 渲染输出）。
            indicators_data = data.get('indicators_data', {})
            if indicators_data:
                logger.debug(f"检测到indicators_data，指标数量: {len(indicators_data)}，由_render_indicators按active_indicators渲染")

            start_time = time.time()
            # 🔧 修复：只在active_indicators为None时使用默认指标，保护用户的选择
            if self.active_indicators is None:  # 仅当完全未设置时才使用默认
                # 调用_get_active_indicators获取默认指标
                if hasattr(self, '_get_active_indicators'):
                    self.active_indicators = self._get_active_indicators()
                    logger.info(f"active_indicators为None，使用默认指标: {len(self.active_indicators) if self.active_indicators else 0}个")
                else:
                    # 硬编码默认指标作为最后的fallback
                    self.active_indicators = [
                        {"name": "MA20", "params": {"period": 20}, "group": "builtin"},
                        {"name": "MA60", "params": {"period": 60}, "group": "builtin"}
                    ]
                    logger.info(f"active_indicators为None，使用硬编码默认指标: MA20, MA60")
            else:
                # 验证active_indicators是否为列表
                if not isinstance(self.active_indicators, list):
                    logger.warning(f"active_indicators格式错误，应为列表，实际为: {type(self.active_indicators)}")
                    # 重置为默认指标
                    self.active_indicators = [
                        {"name": "MA20", "params": {"period": 20}, "group": "builtin"},
                        {"name": "MA60", "params": {"period": 60}, "group": "builtin"}
                    ]
                    logger.info(f"active_indicators格式错误，已重置为默认指标: MA20, MA60")
                else:
                    # 记录active_indicators状态
                    indicator_names = []
                    for ind in self.active_indicators:
                        if ind is not None and isinstance(ind, dict):
                            indicator_names.append(ind.get('name', 'unknown'))
                        else:
                            indicator_names.append('invalid')
                    logger.info(f"active_indicators已被设置，保持现有值不变: {indicator_names}")

            # 记录active_indicators状态
            active_inds = getattr(self, 'active_indicators', None)
            # 如果active_indicators为None，使用空列表
            if active_inds is None:
                active_inds = []
            else:
                # 验证active_indicators中的每个指标
                validated_inds = []
                for i, ind in enumerate(active_inds):
                    if ind is not None and isinstance(ind, dict) and ind.get('name'):
                        validated_inds.append(ind)
                    else:
                        logger.warning(f"移除无效指标 #{i}: {ind}")
                active_inds = validated_inds
                self.active_indicators = active_inds  # 更新为验证后的列表
            
            logger.info(f"准备调用_render_indicators，active_indicators状态: {len(active_inds) if active_inds else 0}个指标")
            # if active_inds:
            #     logger.info(f"active_indicators内容: {[ind.get('name', 'unknown') for ind in active_inds]}")

            self._render_indicators(kdata, x=x)

            # --- 形态信号可视化（R279：update_chart 清场后恢复形态标识）---
            pattern_signals = data.get('pattern_signals', None)
            if not pattern_signals:
                # plot_patterns 路径：读取上次绘制的形态状态（周期切换/指标变更/缩放重绘后恢复）
                pattern_signals = getattr(self, '_current_pattern_signals', None)
            if pattern_signals:
                self.plot_patterns(pattern_signals)
            else:
                # 右侧形态tab路径（signal_mixin）：重绘右侧选中的形态信号
                last_display = getattr(self, '_last_pattern_display', None)
                if last_display:
                    try:
                        self.draw_pattern_signals(**last_display)
                    except Exception as e:
                        logger.debug(f"重绘右侧形态信号失败: {e}")
            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"_render_indicators，耗时: {render_time:.2f}ms")

            # 性能优化P1: 统一调用_optimize_display()设置所有轴的完整样式
            # 替代chart_renderer中的_optimize_display()调用，避免重复设置样式
            # _optimize_display()会设置所有轴（price_ax、volume_ax、indicator_ax）的样式
            self._optimize_display()

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"形态信号可视化，耗时: {render_time:.2f}ms")

            if not kdata.empty:
                for ax in [self.price_ax, self.volume_ax, self.indicator_ax,
                           getattr(self, 'indicator_ax2', None)]:
                    if ax is None:
                        continue
                    ax.set_xlim(0, len(kdata)-1)
                self.price_ax.set_ylim(self._ymin, self._ymax)
                # 设置X轴刻度和标签（间隔显示，防止过密）
                step = max(1, len(kdata)//8)
                xticks = np.arange(0, len(kdata), step)
                xticklabels = [self._safe_format_date(
                    kdata.iloc[i], i, kdata) for i in xticks]
                x_ax = self.indicator_ax
                x_ax.set_xticks(xticks)
                # 修复：确保tick数量和label数量一致
                if len(xticks) == len(xticklabels):
                    x_ax.set_xticklabels(
                        xticklabels, rotation=30, fontsize=8)
                else:
                    # 自动补齐或截断
                    min_len = min(len(xticks), len(xticklabels))
                    x_ax.set_xticks(xticks[:min_len])
                    x_ax.set_xticklabels(
                        xticklabels[:min_len], rotation=30, fontsize=8)
            self.close_loading_dialog()
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if ax is None:
                    continue
                ax.yaxis.set_tick_params(direction='in', pad=0)
                ax.yaxis.set_label_position('left')
                ax.tick_params(axis='y', direction='in', pad=0)

            # 性能优化：延迟十字光标初始化到渲染完成后
            # 不在渲染过程中初始化，避免影响渲染性能
            self.crosshair_enabled = True
            # self.enable_crosshair(force_rebind=True)  # 已移除，延迟到绘制完成后

            # 性能优化：延迟绘制 - 所有渲染和范围设置完成后，只调用一次draw_idle()
            # 这样可以避免K线、成交量、指标分别触发绘制，大幅提升性能
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.draw_idle()
                logger.debug("统一绘制完成（延迟绘制优化）")

            # R265: 全量重绘完成后，十字光标blit背景失效需重建（避免恢复错位画面）
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()

            # R283: 渲染完成后重定位第二指标区"指标▼"按钮（轴布局/尺寸可能已变化）
            if hasattr(self, '_sync_region_indicator_btn_pos'):
                try:
                    self._sync_region_indicator_btn_pos()
                except Exception:
                    pass

            # 性能优化P3：进一步延迟十字光标初始化到用户交互时
            # 不在渲染完成后立即初始化，而是在用户首次鼠标移动时再初始化
            # 这样可以避免在渲染过程中初始化十字光标，进一步提升渲染性能
            if hasattr(self, 'crosshair_enabled') and self.crosshair_enabled:
                # 标记需要初始化，但不立即执行
                self._crosshair_needs_init = True
                logger.debug("十字光标初始化已延迟到用户交互时")

                # 如果已经初始化，只需要清除旧元素（不重新绑定事件）
                if hasattr(self, '_crosshair_initialized') and self._crosshair_initialized:
                    try:
                        if hasattr(self, '_clear_crosshair_elements'):
                            self._clear_crosshair_elements()
                            logger.debug("十字光标元素已清除（已初始化，不重新绑定）")
                    except Exception as e:
                        logger.warning(f"清除十字光标元素失败: {e}")
            # 左上角显示股票名称和代码
            if hasattr(self, '_stock_info_text') and self._stock_info_text:
                try:
                    if self._stock_info_text in self.price_ax.texts:
                        self._stock_info_text.remove()
                except Exception as e:
                    if True:  # 使用Loguru日志
                        logger.warning(f"移除股票信息文本失败: {str(e)}")
                self._stock_info_text = None
            stock_name = data.get('title') or getattr(
                self, 'current_stock', '')
            stock_code = data.get('stock_code') or getattr(
                self, 'current_stock', '')
            if stock_name and stock_code and stock_code not in stock_name:
                info_str = f"{stock_name} ({stock_code})"
            elif stock_name:
                info_str = stock_name
            elif stock_code:
                info_str = stock_code
            else:
                info_str = ''
            colors = self.theme_manager.get_theme_colors()
            text_color = parse_color_for_matplotlib(colors.get('chart_text', '#222b45'))
            bg_color = parse_color_for_matplotlib(colors.get('chart_background', '#ffffff'))
            self._stock_info_text = self.price_ax.text(
                0.01, 0.99, info_str,  # y坐标0.98
                transform=self.price_ax.transAxes,
                va='top', ha='left',
                fontsize=8,
                color=text_color,
                bbox=dict(facecolor=bg_color, alpha=0.7,
                          edgecolor='none', boxstyle='round,pad=0.2'),
                zorder=200
            )
            # 性能优化P0: 移除draw_idle()调用，由最后统一绘制处理
            # 不再在这里触发绘制，避免在渲染过程中触发额外绘制
            # self.canvas.draw_idle()  # 已移除，在最后统一绘制
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if ax is None:
                    continue
                for label in (ax.get_xticklabels() + ax.get_yticklabels()):
                    label.set_fontsize(8)
                ax.title.set_fontsize(8)
                ax.xaxis.label.set_fontsize(8)
                ax.yaxis.label.set_fontsize(8)

            # # 右下角显示数据时间
            # if hasattr(self, '_data_time_text') and self._data_time_text:
            #     try:
            #         if self._data_time_text in self.price_ax.texts:
            #             self._data_time_text.remove()
            #     except Exception as e:
            #         if True:  # 使用Loguru日志
            #             logger.warning(f"移除数据时间文本失败: {str(e)}")
            #     self._data_time_text = None

            # # 获取数据时间
            # import datetime
            # now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # data_time_str = f"当前时间: {now}"

            # # 右下角显示数据时间
            # self._data_time_text = self.price_ax.text(
            #     0.99, 0.01, data_time_str,
            #     transform=self.price_ax.transAxes,
            #     va='bottom', ha='right',
            #     fontsize=8,
            #     color=text_color,
            #     bbox=dict(facecolor=bg_color, alpha=0.7,
            #               edgecolor='none', boxstyle='round,pad=0.2'),
            #     zorder=200
            # )

            self._optimize_display()
        except Exception as e:
            logger.error(f"更新图表失败: {str(e)}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            self.show_no_data("渲染失败")

    def clear_performance_cache(self):
        """清除性能优化缓存"""
        self._performance_optimizer.clear_cache()
        logger.info("性能优化缓存已清除")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            'precomputed_count': len(self._performance_optimizer._precomputed_indicators),
            'style_cache_count': len(self._performance_optimizer._style_cache),
            'cache_version': self._performance_optimizer._cache_version,
            'talib_available': self._performance_optimizer.talib is not None and self._performance_optimizer.talib is not False
        }

    def _get_chart_style(self) -> Dict[str, Any]:
        """获取图表样式，所有颜色从theme_manager.get_theme_colors获取"""
        try:
            colors = self.theme_manager.get_theme_colors()
            
            processed_colors = {}
            for key, value in colors.items():
                processed_colors[key] = parse_color_for_matplotlib(value)
            
            from utils.theme import get_alpha_value
            volume_alpha = get_alpha_value(colors, 'volume_alpha', 0.5)
            k_alpha = get_alpha_value(colors, 'alpha', 1.0)
                    
            return {
                'up_color': processed_colors.get('k_up', '#e74c3c'),
                'down_color': processed_colors.get('k_down', '#27ae60'),
                'limit_up_color': processed_colors.get('k_limit_up', '#FF9800'),
                'limit_down_color': processed_colors.get('k_limit_down', '#AB47BC'),
                'edge_color': processed_colors.get('k_edge', '#2c3140'),
                'volume_up_color': processed_colors.get('volume_up', '#e74c3c'),
                'volume_down_color': processed_colors.get('volume_down', '#27ae60'),
                'volume_alpha': volume_alpha,
                'alpha': k_alpha,
                'grid_color': processed_colors.get('chart_grid', '#e0e0e0'),
                'background_color': processed_colors.get('chart_background', '#ffffff'),
                'text_color': processed_colors.get('chart_text', '#222b45'),
                'axis_color': processed_colors.get('chart_grid', '#e0e0e0'),
                'label_color': processed_colors.get('chart_text', '#222b45'),
                'border_color': processed_colors.get('chart_grid', '#e0e0e0'),
            }
        except Exception as e:
            logger.error(f"获取图表样式失败: {str(e)}")
            return {}

    def _render_ohlc_bars(self, ax, data: pd.DataFrame, style: Dict[str, Any] = None,
                          x: np.ndarray = None) -> None:
        """R277: 美国线（OHLC Bar）渲染

        标准美国线画法：竖线连接最高/最低价，左侧横线为开盘价，右侧横线为收盘价，
        涨红跌绿（与K线图一致）。数据量已由 _downsample_kdata 控制（≤1200 条）。
        R292-HV 修正：与 K 线四色规则一致（涨红/跌绿/涨停橙/跌停紫）。美国线不使用
        阳线空心语义，直接按四色分组着色。'limit_up'/'limit_down' 列存在时优先读取
        （上游在降采样前按全量数据计算，保证昨收为真实前一交易日），缺失时回退内部
        按板块判定，兼容直接传数据的调用方。
        """
        try:
            up_color = (style or {}).get('up_color', '#e74c3c')
            down_color = (style or {}).get('down_color', '#27ae60')
            limit_up_color = (style or {}).get('limit_up_color', '#FF9800')
            limit_down_color = (style or {}).get('limit_down_color', '#AB47BC')
            if x is None:
                x = np.arange(len(data))
            x = np.asarray(x, dtype=float)

            open_p = data['open'].to_numpy(dtype=float)
            high_p = data['high'].to_numpy(dtype=float)
            low_p = data['low'].to_numpy(dtype=float)
            close_p = data['close'].to_numpy(dtype=float)
            # R292-HV：四色分类（列优先；无 limit 列时回退内部按板块判定）
            if 'limit_up' in data.columns and 'limit_down' in data.columns:
                is_limit_up = data['limit_up'].to_numpy(dtype=bool)
                is_limit_down = data['limit_down'].to_numpy(dtype=bool)
            else:
                is_limit_up, is_limit_down = classify_limit_up_down(
                    close_p, high_p, low_p, extract_symbol(data))
            colors = np.where(
                is_limit_up, limit_up_color,
                np.where(is_limit_down, limit_down_color,
                         np.where(close_p >= open_p, up_color, down_color)))

            bar_width = 0.4 if len(x) > 1 else 0.5
            for xi, o, h, l, c, col in zip(x, open_p, high_p, low_p, close_p, colors):
                ax.vlines(xi, l, h, colors=col, linewidth=1)
                ax.hlines(o, xi - bar_width, xi, colors=col, linewidth=1)
                ax.hlines(c, xi, xi + bar_width, colors=col, linewidth=1)
        except Exception as e:
            logger.error(f"美国线(OHLC)渲染失败: {e}", exc_info=True)

    def _get_indicator_style(self, name: str, index: int = 0) -> Dict[str, Any]:
        """获取指标样式，颜色从theme_manager.get_theme_colors获取"""
        colors = self.theme_manager.get_theme_colors()
        indicator_colors_raw = colors.get('indicator_colors', [
            '#fbc02d', '#ab47bc', '#1976d2', '#43a047', '#e53935', '#00bcd4', '#ff9800'])
        indicator_colors = [parse_color_for_matplotlib(c) for c in indicator_colors_raw]
        return {
            'color': indicator_colors[index % len(indicator_colors)],
            'linewidth': 0.7,
            'alpha': 0.85,
            'label': name
        }

    def _optimize_rendering(self):
        """优化渲染性能"""
        try:
            # 启用双缓冲
            self.setAttribute(Qt.WA_OpaquePaintEvent)
            self.setAttribute(Qt.WA_NoSystemBackground)
            self.setAutoFillBackground(True)

            # 优化matplotlib设置
            plt.style.use('fast')
            self.figure.set_dpi(100)

            # 禁用不必要的特性
            plt.rcParams['path.simplify'] = True
            plt.rcParams['path.simplify_threshold'] = 1.0
            plt.rcParams['agg.path.chunksize'] = 20000

            # 优化布局（只保留subplots_adjust，去除set_tight_layout和set_constrained_layout）
            # self.figure.set_tight_layout(False)
            # self.figure.set_constrained_layout(True)

            # 设置固定边距
            self.figure.subplots_adjust(
                left=0.02, right=0.98,
                top=0.98, bottom=0.02,
                hspace=0.1
            )

        except Exception as e:
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(f"优化渲染失败: {str(e)}")

    def _on_render_progress(self, progress: int, message: str):
        """处理渲染进度"""
        self.update_loading_progress(progress, message)

    def _on_render_complete(self):
        """处理渲染完成"""
        self.close_loading_dialog()

    def _on_render_error(self, error: str):
        """处理渲染错误"""
        if hasattr(self, 'error_occurred'):
            self.error_occurred.emit(error)
        self.close_loading_dialog()

    def clear_chart(self):
        """清空图表"""
        try:
            # 清空所有子图（R283: 补 indicator_ax2，此前遗漏导致切换指标后旧图残留）
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if ax is None:
                    continue
                ax.cla()

            # 重置数据
            self.current_kdata = None
            self._full_kdata = None  # R267: 完整数据源一并清空，防止残留脏数据
            self._ymin = 0
            self._ymax = 1

            # 清空十字光标
            if hasattr(self, '_crosshair_lines'):
                # 确保_crosshair_lines是字典类型
                if isinstance(self._crosshair_lines, dict):
                    for line in self._crosshair_lines.values():
                        try:
                            line.remove()
                        except Exception:
                            pass
                else:
                    # 兼容处理列表类型
                    for line in self._crosshair_lines:
                        try:
                            line.remove()
                        except Exception:
                            pass
                # 重置为空字典，与CrosshairMixin保持一致
                self._crosshair_lines = {}

            if hasattr(self, '_crosshair_text') and self._crosshair_text:
                try:
                    self._crosshair_text.remove()
                except Exception:
                    pass
                self._crosshair_text = None

            # 清空股票信息文本
            if hasattr(self, '_stock_info_text') and self._stock_info_text:
                try:
                    self._stock_info_text.remove()
                except Exception:
                    pass
                self._stock_info_text = None

            # 重新绘制
            self.canvas.draw()

        except Exception as e:
            logger.error(f"清空图表失败: {str(e)}")

    def apply_theme(self):
        """应用主题"""
        try:
            if not hasattr(self, 'theme_manager') or not self.theme_manager:
                return

            colors = self.theme_manager.get_theme_colors()
            
            processed_colors = {}
            for key, value in colors.items():
                processed_colors[key] = parse_color_for_matplotlib(value)
            
            bg_color = processed_colors.get('chart_background', '#ffffff')
            if isinstance(bg_color, tuple):
                bg_color = '#{:02x}{:02x}{:02x}'.format(
                    int(bg_color[0]), int(bg_color[1]), int(bg_color[2])
                ) if len(bg_color) >= 3 else '#ffffff'

            self.figure.patch.set_facecolor(bg_color)

            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if ax is None:
                    continue
                ax.set_facecolor(bg_color)

                grid_color = processed_colors.get('chart_grid', '#e0e0e0')
                if isinstance(grid_color, tuple):
                    grid_color = '#{:02x}{:02x}{:02x}'.format(
                        int(grid_color[0]), int(grid_color[1]), int(grid_color[2])
                    ) if len(grid_color) >= 3 else '#e0e0e0'
                ax.grid(True, color=grid_color, alpha=0.3, linewidth=0.5)

                text_color = processed_colors.get('chart_text', '#222b45')
                if isinstance(text_color, tuple):
                    text_color = '#{:02x}{:02x}{:02x}'.format(
                        int(text_color[0]), int(text_color[1]), int(text_color[2])
                    ) if len(text_color) >= 3 else '#222b45'
                ax.tick_params(colors=text_color)
                ax.xaxis.label.set_color(text_color)
                ax.yaxis.label.set_color(text_color)

            self.canvas.draw()

        except Exception as e:
            logger.error(f"应用主题失败: {str(e)}")
            logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")

    def _init_figure_layout(self):
        """初始化图表布局"""
        try:
            # 创建子图
            self.price_ax = self.figure.add_subplot(211)  # 价格图
            self.volume_ax = self.figure.add_subplot(212)  # 成交量图
            self.indicator_ax = self.volume_ax  # 指标图与成交量图共用

            # 设置子图间距
            self.figure.subplots_adjust(
                left=0.02, right=0.98,
                top=0.98, bottom=0.02,
                hspace=0.1
            )

            # 应用主题
            self.apply_theme()

        except Exception as e:
            logger.error(f"初始化图表布局失败: {str(e)}")

    def draw_overview(self, ax, kdata):
        """绘制概览图"""
        try:
            if kdata is None or kdata.empty:
                return

            # 简化的K线图
            x = np.arange(len(kdata))
            ax.plot(x, kdata['close'], color='blue', linewidth=1, alpha=0.7)

            # 设置样式
            ax.set_xlim(0, len(kdata)-1)
            ax.set_ylim(kdata['low'].min(), kdata['high'].max())
            ax.grid(True, alpha=0.3)

        except Exception as e:
            logger.error(f"绘制概览图失败: {str(e)}")

    def show_no_data(self, message: str = "无数据"):
        """无数据时清空图表并显示提示信息，所有字体统一为8号，健壮处理异常，始终显示网格和XY轴刻度"""
        try:
            if hasattr(self, 'figure'):
                self.figure.clear()
                # 重新创建子图，防止后续渲染异常
                self.price_ax = self.figure.add_subplot(211)
                self.volume_ax = self.figure.add_subplot(212)
                self.indicator_ax = self.volume_ax
                # 清空其他内容
                self.price_ax.cla()
                self.volume_ax.cla()
                # 在主图中央显示提示文本
                self.price_ax.text(0.5, 0.5, message,
                                   transform=self.price_ax.transAxes,
                                   fontsize=16, color='#888',
                                   ha='center', va='center', alpha=0.85)
                # 设置默认XY轴刻度和网格
                self.price_ax.set_xlim(0, 1)
                self.price_ax.set_ylim(0, 1)
                self.volume_ax.set_xlim(0, 1)
                self.volume_ax.set_ylim(0, 1)
                self._optimize_display()  # 保证无数据时也显示网格和刻度

                # 使用安全的布局调整方式
                from utils.matplotlib_utils import safe_figure_layout
                safe_figure_layout(self.figure)

                self.canvas.draw()

                # 统一字体大小（全部设为8号）
                for ax in [self.price_ax, self.volume_ax]:
                    for label in (ax.get_xticklabels() + ax.get_yticklabels()):
                        label.set_fontsize(8)
                    ax.title.set_fontsize(8)
                    ax.xaxis.label.set_fontsize(8)
                    ax.yaxis.label.set_fontsize(8)
        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f"显示无数据提示失败: {str(e)}")

    def _get_style(self) -> Dict[str, Any]:
        """获取样式配置"""
        return self._get_chart_style()

    def on_period_changed(self, period: str):
        """处理周期变更"""
        try:
            # 这里可以根据周期调整显示样式
            if hasattr(self, 'current_period'):
                self.current_period = period

            # 发射周期变更信号
            if hasattr(self, 'period_changed'):
                self.period_changed.emit(period)

            # 刷新图表（R267: 使用完整数据源，避免基于已降采样的current_kdata丢失原始数据）
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                self.update_chart({'kdata': self._get_render_kdata() if hasattr(self, '_get_render_kdata') else self.current_kdata})

        except Exception as e:
            logger.error(f"处理周期变更失败: {str(e)}")

    def on_indicator_changed(self, indicator: str):
        """处理指标变更"""
        try:
            # 发射指标变更信号
            if hasattr(self, 'indicator_changed'):
                self.indicator_changed.emit(indicator)

            # 刷新图表（R267: 使用完整数据源，避免基于已降采样的current_kdata丢失原始数据）
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                self.update_chart({'kdata': self._get_render_kdata() if hasattr(self, '_get_render_kdata') else self.current_kdata})

        except Exception as e:
            logger.error(f"处理指标变更失败: {str(e)}")

    def _optimize_display(self):
        """优化显示效果，所有坐标轴字体统一为8号，始终显示网格和XY轴刻度（任何操作都不隐藏）"""
        try:

            start_time = time.time()

            # 确保所有子图都有网格和刻度
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                if not ax:
                    continue

                # 获取主题颜色
                colors = self.theme_manager.get_theme_colors()
                grid_color = parse_color_for_matplotlib(colors.get('chart_grid', '#e0e0e0'))
                text_color = parse_color_for_matplotlib(colors.get('chart_text', '#222b45'))

                # 设置网格
                ax.grid(True, linestyle='--', alpha=0.3, color=grid_color)

                # 设置刻度样式
                ax.tick_params(axis='both', which='major',
                               labelsize=8, colors=text_color)
                ax.tick_params(axis='y', which='major', labelleft=True)

                # 设置所有文本字体大小
                for label in (ax.get_yticklabels()):
                    label.set_fontsize(8)
                    label.set_color(text_color)

                # 设置标题和标签字体
                if ax.get_title():
                    ax.title.set_fontsize(8)
                    ax.title.set_color(text_color)
                ax.xaxis.label.set_fontsize(8)
                ax.xaxis.label.set_color(text_color)
                ax.yaxis.label.set_fontsize(8)
                ax.yaxis.label.set_color(text_color)

            # 只设置indicator_ax的X轴刻度样式，其他子图隐藏X轴
            if self.price_ax:
                self.price_ax.set_xticklabels([])
                self.price_ax.tick_params(
                    axis='x', which='both', bottom=False, top=False, labelbottom=False)

            if self.volume_ax and self.volume_ax != self.indicator_ax:
                self.volume_ax.set_xticklabels([])
                self.volume_ax.tick_params(
                    axis='x', which='both', bottom=False, top=False, labelbottom=False)

            if self.indicator_ax:
                self.indicator_ax.tick_params(
                    axis='x', which='major', labelsize=8, labelbottom=True, colors=text_color)
                for label in self.indicator_ax.get_xticklabels():
                    label.set_fontsize(8)
                    label.set_color(text_color)
                    label.set_rotation(30)

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"_optimize_display，耗时: {render_time:.2f}ms")

        except Exception as e:
            logger.error(f"优化显示失败: {str(e)}")
