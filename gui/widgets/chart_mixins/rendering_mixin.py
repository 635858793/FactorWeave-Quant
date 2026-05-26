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

            kdata = self._downsample_kdata(kdata)
            kdata = kdata.dropna(how='any')
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

            # 记录渲染参数
            logger.debug(f"准备调用renderer.render_candlesticks，x轴长度: {len(x)}")

            # 性能优化：延迟绘制 - 先完成所有渲染，最后统一绘制
            # 调用渲染器
            try:
                self.renderer.render_candlesticks(self.price_ax, kdata, style, x=x)
                logger.debug("K线渲染成功")
            except Exception as e:
                logger.error(f"K线渲染失败: {e}", exc_info=True)
                raise
            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"render_candlesticks，耗时: {render_time:.2f}ms")

            start_time = time.time()
            try:
                self.renderer.render_volume(self.volume_ax, kdata, style, x=x)
                logger.debug("成交量渲染成功")
            except Exception as e:
                logger.error(f"成交量渲染失败: {e}", exc_info=True)

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"render_volume，耗时: {render_time:.2f}ms")

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

            # 处理indicators_data（如果存在）
            indicators_data = data.get('indicators_data', {})
            if indicators_data:
                # 将indicators_data传递给渲染函数
                logger.info(f"检测到indicators_data，指标数量: {len(indicators_data)}, 指标名称: {list(indicators_data.keys())}")
                self._render_indicator_data(indicators_data, kdata, x)
                logger.info(f"_render_indicator_data调用完成")
            else:
                logger.debug(f"💡 indicators_data为空，builtin指标将在_render_indicators中计算")

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

            # --- 新增：形态信号可视化 ---
            pattern_signals = data.get('pattern_signals', None)
            if pattern_signals:
                self.plot_patterns(pattern_signals)
            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"_render_indicators，耗时: {render_time:.2f}ms")

            # 性能优化P1: 统一调用_optimize_display()设置所有轴的完整样式
            # 替代chart_renderer中的_optimize_display()调用，避免重复设置样式
            # _optimize_display()会设置所有轴（price_ax、volume_ax、indicator_ax）的样式
            self._optimize_display()

            render_time = (time.time() - start_time) * 1000  # 转换为毫秒
            logger.info(f"形态信号可视化，耗时: {render_time:.2f}ms")

            if not kdata.empty:
                for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                    ax.set_xlim(0, len(kdata)-1)
                self.price_ax.set_ylim(self._ymin, self._ymax)
                # 设置X轴刻度和标签（间隔显示，防止过密）
                step = max(1, len(kdata)//8)
                xticks = np.arange(0, len(kdata), step)
                xticklabels = [self._safe_format_date(
                    kdata.iloc[i], i, kdata) for i in xticks]
                self.indicator_ax.set_xticks(xticks)
                # 修复：确保tick数量和label数量一致
                if len(xticks) == len(xticklabels):
                    self.indicator_ax.set_xticklabels(
                        xticklabels, rotation=30, fontsize=8)
                else:
                    # 自动补齐或截断
                    min_len = min(len(xticks), len(xticklabels))
                    self.indicator_ax.set_xticks(xticks[:min_len])
                    self.indicator_ax.set_xticklabels(
                        xticklabels[:min_len], rotation=30, fontsize=8)
            self.close_loading_dialog()
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
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

    def _render_indicator_data(self, indicators_data, kdata, x=None):
        """渲染从indicators_data传递的指标数据"""
        try:
            logger.info(f"_render_indicator_data开始执行")
            if not indicators_data:
                logger.warning(f"❌ indicators_data为空，直接返回")
                return

            if x is None:
                x = np.arange(len(kdata))

            logger.info(f"准备遍历indicators_data，指标数量: {len(indicators_data)}")
            # 遍历所有指标
            for i, (indicator_name, indicator_data) in enumerate(indicators_data.items()):
                logger.info(f"处理指标 {i+1}/{len(indicators_data)}: {indicator_name}, 数据类型: {type(indicator_data)}")
                # 处理MA指标
                if indicator_name == 'MA':
                    for j, (period, values) in enumerate(indicator_data.items()):
                        # 确保values是列表
                        values_list = values
                        if hasattr(values, 'tolist'):
                            values_list = values.tolist()

                        # 处理值为None的情况
                        valid_values = []
                        valid_x = []
                        for idx, val in enumerate(values_list):
                            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                                valid_values.append(val)
                                valid_x.append(x[idx] if idx < len(x) else idx)

                        if valid_values:
                            style = self._get_indicator_style(f'MA{period}', j)
                            self.price_ax.plot(
                                valid_x,
                                valid_values,
                                color=style['color'],
                                linewidth=style['linewidth'],
                                alpha=style['alpha'],
                                label=f'MA{period}'
                            )

                # 处理MACD指标
                elif indicator_name == 'MACD':
                    # MACD通常有DIF、DEA和MACD三个数据序列
                    dif_values = indicator_data.get('DIF', [])
                    dea_values = indicator_data.get('DEA', [])
                    hist_values = indicator_data.get('MACD', [])

                    # 确保是列表
                    if hasattr(dif_values, 'tolist'):
                        dif_values = dif_values.tolist()
                    if hasattr(dea_values, 'tolist'):
                        dea_values = dea_values.tolist()
                    if hasattr(hist_values, 'tolist'):
                        hist_values = hist_values.tolist()

                    # 绘制DIF和DEA线
                    valid_dif = [(idx, val) for idx, val in enumerate(dif_values)
                                 if val is not None and not (isinstance(val, float) and np.isnan(val))]
                    valid_dea = [(idx, val) for idx, val in enumerate(dea_values)
                                 if val is not None and not (isinstance(val, float) and np.isnan(val))]

                    if valid_dif:
                        valid_x_dif, valid_y_dif = zip(*valid_dif)
                        self.indicator_ax.plot(
                            [x[i] for i in valid_x_dif if i < len(x)],
                            valid_y_dif,
                            color='#1976d2',  # 蓝色
                            linewidth=0.7,
                            alpha=0.85,
                            label='DIF'
                        )

                    if valid_dea:
                        valid_x_dea, valid_y_dea = zip(*valid_dea)
                        self.indicator_ax.plot(
                            [x[i] for i in valid_x_dea if i < len(x)],
                            valid_y_dea,
                            color='#ff9800',  # 橙色
                            linewidth=0.7,
                            alpha=0.85,
                            label='DEA'
                        )

                    # 绘制MACD柱状图
                    valid_hist = [(idx, val) for idx, val in enumerate(hist_values)
                                  if val is not None and not (isinstance(val, float) and np.isnan(val))]

                    if valid_hist:
                        valid_x_hist, valid_y_hist = zip(*valid_hist)
                        valid_x_hist = [x[i]
                                        for i in valid_x_hist if i < len(x)]
                        colors = ['#e53935' if h >=
                                  0 else '#43a047' for h in valid_y_hist]  # 红色和绿色
                        self.indicator_ax.bar(
                            valid_x_hist,
                            valid_y_hist,
                            color=colors,
                            alpha=0.5,
                            width=0.6
                        )

                # 其他指标类型...可以根据需要添加更多指标的处理逻辑

        except Exception as e:
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(f"渲染指标数据失败: {str(e)}")
            logger.error(f"渲染指标数据失败: {str(e)}")

    
    
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
            # 清空所有子图
            for ax in [self.price_ax, self.volume_ax, self.indicator_ax]:
                ax.cla()

            # 重置数据
            self.current_kdata = None
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

            # 刷新图表
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                self.update_chart({'kdata': self.current_kdata})

        except Exception as e:
            logger.error(f"处理周期变更失败: {str(e)}")

    def on_indicator_changed(self, indicator: str):
        """处理指标变更"""
        try:
            # 发射指标变更信号
            if hasattr(self, 'indicator_changed'):
                self.indicator_changed.emit(indicator)

            # 刷新图表
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                self.update_chart({'kdata': self.current_kdata})

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
