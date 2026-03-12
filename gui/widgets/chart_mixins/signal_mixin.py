from loguru import logger

"""
信号处理Mixin - 处理交易信号的绘制、高亮和管理
"""

from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandas as pd

class SignalMixin:

    def _safe_remove_artist(self, artist):
        """安全删除matplotlib artist对象 - 改进版本"""
        if artist is None:
            return True

        try:
            # 获取artist的类型信息
            artist_type = str(type(artist))

            # 方法1: 优先使用标准remove方法（对大部分对象有效）
            if hasattr(artist, 'remove'):
                try:
                    artist.remove()
                    return True
                except Exception as e:
                    # 如果是ArtistList错误，不记录为错误，因为这是已知问题
                    if 'ArtistList' not in str(e):
                        logger.debug(f"标准remove方法失败: {e}")

            # 方法2: 对于PathCollection等集合类型，从axes中移除
            if hasattr(artist, 'axes') and artist.axes is not None:
                axes = artist.axes

                # 检查并从各种集合中移除
                collections_to_check = [
                    ('collections', axes.collections),
                    ('texts', axes.texts),
                    ('patches', axes.patches),
                    ('lines', axes.lines),
                    ('images', axes.images)
                ]

                for collection_name, collection in collections_to_check:
                    if hasattr(axes, collection_name) and artist in collection:
                        try:
                            collection.remove(artist)
                            return True
                        except Exception as e:
                            logger.debug(f"从{collection_name}中移除失败: {e}")
                            continue

            # 方法2.1: 额外检查 - 从 figure 级别 collections 中移除
            if hasattr(self, 'figure') and self.figure is not None:
                for ax in self.figure.axes:
                    for collection_list in [ax.collections, ax.texts, ax.patches, ax.lines]:
                        if artist in collection_list:
                            try:
                                collection_list.remove(artist)
                                return True
                            except Exception:
                                pass

            # 方法3: 如果以上都失败，至少隐藏对象
            if hasattr(artist, 'set_visible'):
                try:
                    artist.set_visible(False)
                    return True
                except Exception:
                    pass

            # 方法4: 对于一些特殊类型，尝试设置alpha为0
            if hasattr(artist, 'set_alpha'):
                try:
                    artist.set_alpha(0)
                    return True
                except Exception:
                    pass

            return False

        except Exception as e:
            # 只有在非预期错误时才记录警告
            if 'ArtistList' not in str(e):
                logger.debug(f"删除artist时出现问题: {e}")
            return False

    def plot_signals(self, signals, visible_range=None, signal_filter=None):
        """绘制信号，支持密度自适应、聚合展示、气泡提示"""
        try:
            if not hasattr(self, 'price_ax') or not self.price_ax:
                return

            # 清除旧信号
            for artist in getattr(self, '_signal_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception:
                    pass
            self._signal_artists = []

            if not signals:
                self.canvas.draw_idle()
                return

            # 获取当前可见区间
            if visible_range is None:
                visible_range = self.get_visible_range()

            # 筛选可见区间内的信号
            visible_signals = []
            if visible_range:
                start_idx, end_idx = visible_range
                for signal in signals:
                    sig_idx = signal.get('index', 0)
                    if start_idx <= sig_idx <= end_idx:
                        visible_signals.append(signal)
            else:
                visible_signals = signals

            # 信号密度自适应
            max_signals_per_screen = 20  # 每屏最多显示信号数
            if len(visible_signals) > max_signals_per_screen:
                # 选择重要信号
                visible_signals = self._select_important_signals(
                    visible_signals, max_signals_per_screen)

            # 绘制信号
            for signal in visible_signals:
                self._plot_single_signal(signal)

            # 启用气泡提示（如果有信号）
            if visible_signals:
                self._enable_signal_tooltips(visible_signals)

            # 更新画布
            self.canvas.draw_idle()

        except Exception as e:
            logger.error(f"绘制信号失败: {str(e)}")

    def draw_pattern_signals(self, all_indices: List[int], highlighted_index: int, pattern_name: str, analysis_type: str = ""):
        """在图表上绘制并高亮形态信号"""
        try:
            if not hasattr(self, 'price_ax') or not self.price_ax or self.current_kdata is None:
                logger.warning("无法绘制形态信号，因为图表或数据尚未准备好。")
                return

            # 根据算法类型选择不同的标记颜色
            if analysis_type == 'professional':
                color_scheme = {'normal': 'purple', 'highlighted': 'darkviolet', 'alpha': 0.8}
            elif analysis_type == 'one_click':
                color_scheme = {'normal': 'orange', 'highlighted': 'red', 'alpha': 0.7}
            else:
                color_scheme = {'normal': 'orange', 'highlighted': 'red', 'alpha': 0.7}

            logger.info(f"绘制形态信号: pattern={pattern_name}, type={analysis_type}, "
                        f"信号数量: {len(all_indices)}, color_scheme={color_scheme}")

            # 清除之前绘制的形态信号 - 使用安全的删除方法
            if hasattr(self, '_pattern_signal_artists'):
                for artist in self._pattern_signal_artists[:]:  # 创建副本以避免迭代时修改
                    self._safe_remove_artist(artist)
            self._pattern_signal_artists = []

            kdata = self.current_kdata

            # 去重索引，避免重复绘制
            unique_indices = list(set(all_indices))
            logger.debug(f"准备绘制 {len(unique_indices)} 个唯一的形态信号（原始数量: {len(all_indices)}）")
            
            # 绘制所有同类型的信号
            drawn_count = 0
            for index in unique_indices:
                if 0 <= index < len(kdata):
                    try:
                        # 获取价格，确保在可见范围内
                        price = float(kdata['high'].iloc[index]) * 1.02  # 在K线上方绘制标记
                        
                        # 验证价格是否有效
                        if pd.isna(price) or price <= 0:
                            logger.warning(f"索引 {index} 的价格无效: {price}")
                            continue

                        is_highlighted = (index == highlighted_index)

                        # 根据是否高亮选择不同的标记样式
                        marker = 'v' if not is_highlighted else '^'  # 高亮使用向上箭头
                        size = 150 if is_highlighted else 80
                        color = color_scheme['highlighted'] if is_highlighted else color_scheme['normal']
                        alpha = 1.0 if is_highlighted else color_scheme['alpha']
                        zorder = 10 if is_highlighted else 5

                        # 使用 scatter 绘制标记
                        scatter = self.price_ax.scatter(
                            index, price, 
                            s=size, 
                            c=color, 
                            marker=marker,
                            alpha=alpha, 
                            edgecolors='white', 
                            linewidth=1, 
                            zorder=zorder,
                            label=pattern_name if is_highlighted else None
                        )
                        self._pattern_signal_artists.append(scatter)
                        drawn_count += 1

                        # 如果是高亮信号，添加一个文本标签
                        if is_highlighted:
                            text = self.price_ax.text(
                                index, price, f'  {pattern_name}',
                                fontsize=9, 
                                color=color, 
                                va='bottom' if marker == '^' else 'top', 
                                ha='left',
                                fontweight='bold',
                                zorder=zorder + 1
                            )
                            self._pattern_signal_artists.append(text)
                    except Exception as e:
                        logger.warning(f"绘制索引 {index} 的信号失败: {e}")
                        continue

            # 确保坐标轴范围包含所有绘制的点
            if drawn_count > 0:
                try:
                    # 获取当前坐标轴范围
                    xlim = self.price_ax.get_xlim()
                    ylim = self.price_ax.get_ylim()
                    
                    # 计算需要包含的索引范围
                    if unique_indices:
                        min_idx = min(unique_indices)
                        max_idx = max(unique_indices)
                        
                        # 扩展X轴范围以包含所有信号
                        new_xlim = (
                            min(xlim[0], max(0, min_idx - 10)),
                            max(xlim[1], max_idx + 10)
                        )
                        
                        # 计算需要包含的价格范围
                        signal_prices = []
                        for idx in unique_indices:
                            if 0 <= idx < len(kdata):
                                try:
                                    p = float(kdata['high'].iloc[idx]) * 1.05  # 包含标签空间
                                    if not pd.isna(p) and p > 0:
                                        signal_prices.append(p)
                                except Exception:
                                    pass
                        
                        if signal_prices:
                            min_price = min(signal_prices)
                            max_price = max(signal_prices)
                            new_ylim = (
                                min(ylim[0], min_price * 0.95),
                                max(ylim[1], max_price * 1.05)
                            )
                            
                            # 更新坐标轴范围
                            self.price_ax.set_xlim(new_xlim)
                            self.price_ax.set_ylim(new_ylim)
                except Exception as e:
                    logger.warning(f"调整坐标轴范围失败: {e}")

            # 使用 draw_idle 进行延迟重绘，避免阻塞
            if hasattr(self, 'canvas') and self.canvas:
                try:
                    self.canvas.draw_idle()
                except Exception as e:
                    logger.warning(f"canvas.draw_idle() 失败: {e}")
            
            logger.info(f"成功绘制了 {drawn_count} 个 '{pattern_name}' 形态信号（去重后），并高亮显示了索引 {highlighted_index}。")

        except Exception as e:
            logger.error(f"绘制形态信号失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _select_important_signals(self, signals, max_count):
        """选择重要信号，根据置信度和类型优先级"""
        # 按置信度排序，选择top signals
        sorted_signals = sorted(signals, key=lambda s: s.get('confidence', 0),
                                reverse=True)
        return sorted_signals[:max_count]

    def _plot_single_signal(self, signal):
        """绘制单个信号标记"""
        try:
            idx = signal.get('index', 0)
            signal_type = signal.get('type', 'unknown')
            confidence = signal.get('confidence', 0)
            price = signal.get('price', 0)

            # 根据信号类型设置颜色和标记
            if signal_type == 'double_top':
                color = 'red'
                marker = 'v'
                label = 'DT'
            elif signal_type == 'double_bottom':
                color = 'green'
                marker = '^'
                label = 'DB'
            else:
                color = 'blue'
                marker = 'o'
                label = signal_type[:2].upper()

            # 信号标记
            scatter = self.price_ax.scatter(idx, price, c=color, marker=marker, s=80,
                                           alpha=0.8, edgecolors='white', linewidth=1)
            self._signal_artists.append(scatter)

            # 简洁文字标注（仅高置信度显示）
            if confidence > 0.7:
                text = self.price_ax.text(idx, price * 1.01, label,
                                         fontsize=8, ha='center', va='bottom',
                                         color=color, fontweight='bold',
                                         bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
                self._signal_artists.append(text)

        except Exception as e:
            logger.error(f"绘制单个信号失败: {str(e)}")

    def _enable_signal_tooltips(self, signals):
        """启用信号气泡提示 - 通过标志位与十字光标协调工作"""
        self._signal_tooltips_enabled = True

        # 存储信号数据供十字光标使用（避免重复tooltip）
        self._signal_tooltip_map = {}
        for signal in signals:
            idx = signal.get('index', 0)
            self._signal_tooltip_map[idx] = signal

    def _disable_signal_tooltips(self):
        """禁用信号气泡提示"""
        if hasattr(self, '_signal_tooltips_enabled'):
            self._signal_tooltips_enabled = False
            self._signal_tooltip_map = {}

            # 清除现有提示
            for artist in getattr(self, '_tooltip_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception:
                    pass
            self._tooltip_artists = []

    def get_signal_tooltip_at_index(self, idx: int) -> str:
        """获取指定索引处的信号提示信息，供十字光标调用

        Args:
            idx: K线数据索引

        Returns:
            格式化的信号提示字符串，如果无信号则返回空字符串
        """
        if not hasattr(self, '_signal_tooltip_map') or idx not in self._signal_tooltip_map:
            return ""

        try:
            signal = self._signal_tooltip_map[idx]
            signal_type = signal.get('type', 'unknown')
            confidence = signal.get('confidence', 0)
            price = signal.get('price', 0)

            signal_type_cn = {
                'double_top': '双顶',
                'double_bottom': '双底',
                'head_shoulders': '头肩顶',
                'inverse_head_shoulders': '头肩底',
                'triangle': '三角形',
                'wedge': '楔形',
                'flag': '旗形'
            }.get(signal_type, signal_type)

            return f"类型: {signal_type_cn}\n置信度: {confidence:.2%}\n价格: {price:.2f}"
        except Exception:
            return ""

    def highlight_signal(self, signal_index: int, signal_data: dict = None):
        """高亮显示特定信号"""
        try:
            # 清除之前的高亮
            for artist in getattr(self, '_highlight_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception:
                    pass
            self._highlight_artists = []

            if signal_data:
                # 高亮圆圈
                idx = signal_data.get('index', signal_index)
                price = signal_data.get('price', 0)

                highlight_circle = self.price_ax.scatter(idx, price, s=200,
                                                        facecolors='none',
                                                        edgecolors='yellow',
                                                        linewidths=3, alpha=0.8, zorder=100)
                self._highlight_artists.append(highlight_circle)

            self.canvas.draw_idle()

        except Exception as e:
            logger.error(f"高亮信号失败: {str(e)}")

    def clear_signal_highlight(self):
        """清除信号高亮"""
        try:
            # 移除高亮对象
            for artist in getattr(self, '_highlight_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception:
                    pass
            self._highlight_artists = []

            # 清除气泡提示
            for artist in getattr(self, '_tooltip_artists', []):
                try:
                    self._safe_remove_artist(artist)
                except Exception:
                    pass
            self._tooltip_artists = []

            self.canvas.draw_idle()

        except Exception as e:
            logger.error(f"清除信号高亮失败: {str(e)}")

    def plot_patterns(self, pattern_signals: list, highlight_index: int = None):
        """
        专业化形态信号显示：使用彩色箭头标记，默认隐藏浮窗，集成到十字光标显示
        Args:
            pattern_signals: List[dict]，每个dict至少包含 'index', 'pattern', 'signal', 'confidence' 等字段
        """
        if not hasattr(self, 'price_ax') or self.current_kdata is None or not pattern_signals:
            return

        ax = self.price_ax
        kdata = self.current_kdata
        x = np.arange(len(kdata))

        # 专业化颜色配置 - 参考同花顺、东方财富等软件
        signal_colors = {
            'buy': '#FF4444',      # 买入信号 - 红色箭头向上
            'sell': '#00AA00',     # 卖出信号 - 绿色箭头向下
            'neutral': '#FFB000'   # 中性信号 - 橙色圆点
        }

        # 置信度透明度映射
        def get_alpha(confidence):
            if confidence >= 0.8:
                return 1.0
            elif confidence >= 0.6:
                return 0.8
            else:
                return 0.6

        # 存储形态信息供十字光标使用
        self._pattern_info = {}

        # 统计有效和无效的形态信号
        valid_patterns = 0
        invalid_patterns = 0

        for pat in pattern_signals:
            try:
                idx = pat.get('index', 0)
                pattern_name = pat.get('pattern', 'unknown')
                signal = pat.get('signal', 'neutral')
                confidence = pat.get('confidence', 0.5)

                # 验证索引有效性
                if idx < 0 or idx >= len(kdata):
                    invalid_patterns += 1
                    continue

                valid_patterns += 1

                # 获取颜色和透明度
                color = signal_colors.get(signal, signal_colors['neutral'])
                alpha = get_alpha(confidence)

                # 绘制专业箭头标记
                if signal == 'buy':
                    # 买入信号：空心向上三角，位于K线下方
                    arrow_y = kdata.iloc[idx]['low'] - \
                        (kdata.iloc[idx]['high'] - kdata.iloc[idx]['low']) * 0.15
                    ax.scatter(idx, arrow_y, marker='^', s=80, facecolors='none',
                               edgecolors=color, linewidths=0.8, alpha=alpha, zorder=100)
                elif signal == 'sell':
                    # 卖出信号：空心向下三角，位于K线上方
                    arrow_y = kdata.iloc[idx]['high'] + \
                        (kdata.iloc[idx]['high'] - kdata.iloc[idx]['low']) * 0.15
                    ax.scatter(idx, arrow_y, marker='v', s=80, facecolors='none',
                               edgecolors=color, linewidths=0.8, alpha=alpha, zorder=100)
                else:
                    # 中性信号：空心圆点，位于收盘价位置
                    ax.scatter(idx, kdata.iloc[idx]['close'], marker='o', s=60, facecolors='none',
                               edgecolors=color, linewidths=0.8, alpha=alpha, zorder=100)

                # 存储形态信息供十字光标显示
                self._pattern_info[idx] = {
                    'pattern_name': pattern_name,
                    'signal': signal,
                    'confidence': confidence,
                    'signal_cn': {'buy': '买入', 'sell': '卖出', 'neutral': '中性'}.get(signal, signal),
                    'price': kdata.iloc[idx]['close'],
                    'datetime': kdata.index[idx].strftime('%Y-%m-%d') if hasattr(kdata.index[idx], 'strftime') else str(kdata.index[idx])
                }

            except Exception as e:
                invalid_patterns += 1
                logger.error(f"绘制形态信号出错 {idx}: {e}")

        # 记录绘制结果
        logger.info(
                f"形态信号绘制完成: 有效 {valid_patterns} 个, 无效 {invalid_patterns} 个")

        # 高亮特定形态（如果指定）
        if highlight_index is not None and highlight_index in self._pattern_info:
            self.highlight_signal(highlight_index, self._pattern_info[highlight_index])

        # 刷新图表
        if hasattr(self, 'canvas'):
            self.canvas.draw_idle()
