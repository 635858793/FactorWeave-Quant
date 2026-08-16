"""
图表渲染功能Mixin - 处理K线渲染、指标渲染、样式配置等功能

## HV6.2 末根 overlay 惰性拆分策略（R292-HV6.2）

bar 内 tick 增量渲染采用"末根 overlay 独立集合"：主体集合（前 n-1 根）与末根
分离，tick 期间主体集合**永不动**，只重建 + draw 末根 1 根（光栅化 ∝ 顶点数，
单根 <1ms，消除 HV6.1 全视图 8 集合 draw_artist 15ms 的 blit 瓶颈）。

惰性拆分时序约束（关键）：
1. `_ensure_tick_overlay()` 在 `_update_last_bar_with_tick` **数据更新之前**调用——
   主体集合仍是更新前 verts，末根类别须按更新前数据判定拆分，否则类别错位
   导致主体残留末根；
2. `_setup_tick_overlay()` 从主体 `get_paths()` 恢复顶点（PolyCollection 无
   get_verts()），matplotlib 闭合 Path 首点重复（4 顶点 → 5 顶点 Path）须去重
   `verts[:, :-1, :]`；
3. 全部 8 K线 + 4 成交量 key 都建 overlay 集合（含空集合），类别迁移时可
   set_verts 到任意类别；类别只含末根 1 根时主体必须 set_verts 空数组清空，
   否则迁移后主体不在 blit 范围 → 旧末根残影不可清除；
4. update_chart 全量重绘后（ax.clear 移除旧集合）惰性重建。

退化回退机制：
- overlay 不可用（单根数据 / 集合缺失 / ax 缺失 / 拆分异常）→ `_ensure_tick_overlay`
  返回 False → tick 路径回退 HV6.1 全视图向量化重建（`_rebuild_kline_verts`/
  `_rebuild_volume_verts`，~6ms）+ blit 主体集合（~15ms），仍远快于生产全量；
- `_rebuild_kline_overlay`/`_rebuild_volume_overlay` 失败 → 返回 False → 外层退化
  全量 update_chart（rendering_mixin.py L763-766）。三重回退保证 tick 路径永不断裂。
"""
import time
import numpy as np
import pandas as pd
import re
from loguru import logger
from typing import Dict, Any, Tuple, Optional, List
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 替换旧的指标系统导入
from core.indicator_adapter import get_indicator_english_name
from utils.theme import parse_color_for_matplotlib
# R292 涨跌停精确判定（按板块计算涨/跌停价，替代固定 4.8% 阈值）
from core.rendering.limit_price import classify_limit_up_down, extract_symbol, is_limit_up_down


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

    
    
    
    
    
    
    @staticmethod
    def _compute_intraday_series(kdata: pd.DataFrame):
        """R294: 计算当日分时图序列（纯逻辑，可无 GUI 测试）

        从 1min 周期 K 线中过滤最新交易日数据，计算昨收与成交量加权均价(VWAP)。

        Returns:
            (当日数据 DataFrame, 昨收 float|None, 均价线 Series)
        """
        intra = kdata
        prev_close = None
        # V-03 契约: 数据链路将昨收写入 prev_close 列（类1min K线，每行同值）。
        # 优先读取该列（精确昨收，避免历史 close 错位 / 退化 open[0] 近似）；
        # 列缺失或全空时保留原回退链路（历史 close → open[0]），行为不变。
        if 'prev_close' in kdata.columns:
            pc = pd.to_numeric(kdata['prev_close'], errors='coerce').dropna()
            if len(pc):
                prev_close = float(pc.iloc[0])
        if 'datetime' in kdata.columns:
            ts = pd.to_datetime(kdata['datetime'])
            last_day = ts.max().normalize()
            day_mask = ts.dt.normalize() == last_day
            intra = kdata.loc[day_mask]
            if prev_close is None and len(kdata) > len(intra):
                # 昨收 = 最新交易日之前最后一根的收盘价
                prev_close = float(kdata.loc[~day_mask, 'close'].iloc[-1])
        if len(intra) == 0:
            intra = kdata
        if prev_close is None and len(intra):
            prev_close = float(intra['open'].iloc[0])

        # 均价线: 成交量加权 VWAP（volume 为 0 时退化为 close 均价）
        vol = pd.to_numeric(intra['volume'], errors='coerce').fillna(0).to_numpy()
        cl = intra['close'].to_numpy(dtype=float)
        cum_vol = vol.cumsum()
        with np.errstate(divide='ignore', invalid='ignore'):
            avg = np.where(cum_vol > 0, (cl * vol).cumsum() / cum_vol, cl)
        return intra, prev_close, pd.Series(avg, index=intra.index)

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

            # R277 修复：图表类型（K线图/分时图/美国线/收盘价）真实生效。
            # 提前读取（R293-G3: 分时图数据为当日 1min，跳过降采样避免当日
            # 分时点密度被等距抽样稀释；日线/分钟K线仍走 _downsample_kdata）。
            chart_type = data.get('chart_type') or getattr(self, 'chart_type', None) or 'K线图'
            if chart_type != '分时图':
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

            # 图表类型已在降采样前读取（R293-G3），此处仅记录渲染参数
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
                # R294 增强: 从"历史K线折线"升级为"当日分时图"——过滤最新交易日的
                # 1min 数据，绘制分时线(close) + 均价线(成交量加权 VWAP) + 昨收参考线。
                # 数据源为 1min 周期 K 线(Period.MIN1 → '1min')，行情快照默认当日。
                # 已知局限: _downsample_kdata(utility_mixin.py L26-39)等距抽样会把
                # 长历史分钟数据稀疏化，当日分时点密度取决于实际拉取到的分钟量。
                try:
                    intra, prev_close, avg = self._compute_intraday_series(kdata)
                    x_intra = np.arange(len(intra))
                    # 分时线（收盘价折线）
                    self.renderer.render_line(self.price_ax, intra['close'], style, x=x_intra)
                    # 均价线（V-04: 颜色取主题 avg_line，缺省黄色，区别于分时线）
                    avg_style = dict(style)
                    avg_style['color'] = style.get('avg_color', '#ffd700')
                    self.renderer.render_line(self.price_ax, avg, avg_style, x=x_intra)
                    # 昨收参考线（虚线）
                    if prev_close is not None:
                        self.price_ax.axhline(prev_close, color='#888888',
                                              linestyle='--', linewidth=0.8, alpha=0.7)
                    # 成交量
                    self.renderer.render_volume(self.volume_ax, intra, style, x=x_intra)
                except Exception as e:
                    logger.error(f"分时图渲染失败: {e}", exc_info=True)
                try:
                    self.price_ax.text(
                        0.99, 0.99, '当日分时(1分钟)',
                        transform=self.price_ax.transAxes, ha='right', va='top',
                        fontsize=9, color='#888888', alpha=0.85, zorder=200)
                    # V-05: 右上角第二行追加最新 VWAP 均价角标
                    # （均价线计算失败时 avg 未定义 → locals().get 静默跳过）
                    avg_latest = locals().get('avg')
                    if avg_latest is not None and len(avg_latest):
                        self.price_ax.text(
                            0.99, 0.94, f'均价 {avg_latest.iloc[-1]:.2f}',
                            transform=self.price_ax.transAxes, ha='right', va='top',
                            fontsize=9, color='#888888', alpha=0.85, zorder=200)
                except Exception as e:
                    logger.debug(f"分时图数据来源标注失败: {e}")
            else:  # K线图（默认）
                try:
                    kc = self.renderer.render_candlesticks(self.price_ax, kdata, style, x=x)
                    self._save_kline_collections(kc)
                    logger.debug("K线渲染成功")
                except Exception as e:
                    logger.error(f"K线渲染失败: {e}", exc_info=True)
                    raise
                try:
                    vc = self.renderer.render_volume(self.volume_ax, kdata, style, x=x)
                    self._save_volume_collections(vc)
                    logger.debug("成交量渲染成功")
                except Exception as e:
                    logger.error(f"成交量渲染失败: {e}", exc_info=True)
                # HV6.2：末根 overlay 初始化（主体前 n-1 根 + 末根独立集合）。
                # 必须在 autoscale_view 之前执行——overlay 含末根 high/low，
                # 拆分后主体集合少了末根，ylim 由 overlay 补齐
                try:
                    self._setup_tick_overlay()
                except Exception:
                    pass
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
                    kdata.iloc[i], i, kdata,
                    getattr(self, 'current_period', None)) for i in xticks]
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

    # ============================================================
    # HV6 tick 增量渲染（R292-HV6）
    # 统一 blit 方案（HV5）就绪后，K 线主图订阅 TickDataEvent：
    # - bar 内 tick：只更新末根 bar 的 OHLCV + set_verts 重建对应集合 + BlitEngine blit
    #   （基准：1200 根 9.2ms/增量 vs 41.7ms/全量，4.6x，不触发全画布 draw_idle）
    # - 新 bar（跨周期）：x 轴右移 → 走 update_chart 全量（一次性背景重建，之后分钟级 tick 免费）
    # - 指标联动：bar 内不更新指标（避免全量重算抵消收益），新 bar 收盘全量刷新
    # ============================================================
    KLINE_KEYS = ('up', 'down', 'limit_up', 'limit_down',
                  'shadow_up', 'shadow_down', 'shadow_limit_up', 'shadow_limit_down')
    VOLUME_KEYS = ('up', 'down', 'limit_up', 'limit_down')
    # R292-HV6 性能日志：慢 tick 阈值（单次 > 33ms 告警）与聚合采样间隔（类属性，测试可覆盖）
    SLOW_TICK_MS = 33.0
    PERF_SAMPLE_EVERY = 60

    def _get_tick_perf_stats(self):
        """惰性初始化实例级 tick 增量渲染性能统计（仅首次访问创建，避免侵入 __init__）"""
        stats = getattr(self, '_tick_perf_stats', None)
        if stats is None:
            stats = {
                # bar 内 tick（_update_last_bar_with_tick 成功路径）
                'bar_count': 0, 'bar_total_ms': 0.0, 'bar_max_ms': 0.0,
                # 子阶段累计耗时（ms）：数据更新 / K 线 verts 重建 / 成交量 verts 重建 / blit
                'stage_data_ms': 0.0, 'stage_kline_ms': 0.0,
                'stage_volume_ms': 0.0, 'stage_blit_ms': 0.0,
                # 聚合日志节流窗口（每 PERF_SAMPLE_EVERY 次输出并重置）
                'agg_count': 0, 'agg_total_ms': 0.0, 'agg_max_ms': 0.0,
                # 新 bar（跨周期，_append_new_bar 路径）
                'newbar_count': 0, 'newbar_total_ms': 0.0, 'newbar_max_ms': 0.0,
                # 退化全量（增量失败 → update_chart 全量重绘）
                'fallback_count': 0,
            }
            self._tick_perf_stats = stats
        return stats

    def _log_tick_perf_agg(self, stats):
        """每 PERF_SAMPLE_EVERY 次 bar 内 tick 打一条聚合日志（节流，避免高频刷屏）"""
        n = stats['agg_count']
        bar_cnt = stats['bar_count']
        new_cnt = stats['newbar_count']
        avg = stats['agg_total_ms'] / n if n else 0.0
        new_avg = stats['newbar_total_ms'] / new_cnt if new_cnt else 0.0

        def _stage_avg(key):
            return stats[key] / bar_cnt if bar_cnt else 0.0

        logger.info(
            f"[PERF][TickIncremental] bar内tick {n}次 avg={avg:.1f}ms "
            f"max={stats['agg_max_ms']:.1f}ms | 阶段avg: "
            f"数据={_stage_avg('stage_data_ms'):.1f} 重建K={_stage_avg('stage_kline_ms'):.1f} "
            f"重建V={_stage_avg('stage_volume_ms'):.1f} blit={_stage_avg('stage_blit_ms'):.1f} "
            f"| 新bar {new_cnt}次 avg={new_avg:.1f}ms max={stats['newbar_max_ms']:.1f}ms "
            f"| 退化全量 {stats['fallback_count']}次")

    def _save_kline_collections(self, colls):
        """保存 K 线 8-collection 引用（tuple → dict，tick 增量更新按 key 操作）"""
        if not isinstance(colls, (tuple, list)) or len(colls) != len(self.KLINE_KEYS):
            self._kline_collections = None
            return
        self._kline_collections = dict(zip(self.KLINE_KEYS, colls))

    def _save_volume_collections(self, colls):
        """保存成交量 4-collection 引用"""
        if not isinstance(colls, (tuple, list)) or len(colls) != len(self.VOLUME_KEYS):
            self._volume_collections = None
            return
        self._volume_collections = dict(zip(self.VOLUME_KEYS, colls))

    def _on_tick_event(self, event):
        """TickDataEvent 桥接：事件对象 → tick dict（ChartWidget._bind_events 订阅）"""
        try:
            self._handle_realtime_tick(getattr(event, 'tick_data', None))
        except Exception as e:
            logger.debug(f"处理 TickDataEvent 失败: {e}")

    def _bar_key_of(self, dt):
        """tick/bar 归属周期桶（新 bar 判定：tick 时间戳跨桶 → 追加新 bar）"""
        period = str(getattr(self, 'current_period', None) or 'D')
        freq = {'1min': '1min', '5min': '5min', '15min': '15min',
                '30min': '30min', '60min': '1h', 'D': 'D',
                'W': 'W'}.get(period, 'D')
        try:
            return pd.Timestamp(dt).floor(freq)
        except Exception:
            return pd.Timestamp(dt).floor('D')

    def _handle_realtime_tick(self, tick):
        """tick 增量渲染入口：symbol 过滤 + 图表类型守卫 + bar 归属判断"""
        try:
            if not tick or not isinstance(tick, dict):
                return
            symbol = tick.get('symbol')
            current = (getattr(self, 'current_stock', None)
                       or getattr(self, '_current_stock_code', None) or '')
            if symbol and current and str(symbol).strip() != str(current).strip():
                return  # symbol 不匹配：不更新
            chart_type = getattr(self, 'chart_type', None) or 'K线图'
            if chart_type != 'K线图':
                return  # 仅 K线图走增量（分时图/美国线/收盘价回退现有全量路径）
            kdata = getattr(self, 'current_kdata', None)
            if kdata is None or kdata.empty:
                return
            # 新 bar（跨周期）判定
            ts = tick.get('timestamp')
            if ts is not None and 'datetime' in kdata.columns:
                try:
                    tick_bucket = self._bar_key_of(ts)
                    last_bucket = self._bar_key_of(kdata['datetime'].iloc[-1])
                    if tick_bucket > last_bucket:
                        # 新 bar（跨周期）：计时 → 追加 + 全量重绘
                        _t = time.perf_counter()
                        self._append_new_bar(tick)
                        elapsed_ms = (time.perf_counter() - _t) * 1000
                        stats = self._get_tick_perf_stats()
                        stats['newbar_count'] += 1
                        stats['newbar_total_ms'] += elapsed_ms
                        stats['newbar_max_ms'] = max(stats['newbar_max_ms'], elapsed_ms)
                        return
                except Exception:
                    pass
            ok = self._update_last_bar_with_tick(tick)
            if not ok:
                # 无法增量（如末根新类别所属集合渲染时为空）→ 退化全量，保证正确
                stats = self._get_tick_perf_stats()
                stats['fallback_count'] += 1
                # HV6 修复：DataFrame 的 or 短路会触发 __bool__ 抛 ValueError
                # （ambiguous truth value）被外层 try 吞掉，导致退化全量永不生效
                full = getattr(self, '_full_kdata', None)
                if full is None:
                    full = kdata
                self.update_chart({'kdata': full})
        except Exception as e:
            logger.debug(f"tick 增量更新失败: {e}")

    def _update_last_bar_with_tick(self, tick):
        """bar 内 tick：更新末根 OHLCV → set_verts 重建对应集合 → blit 快路径。

        Returns:
            True=增量成功；False=无法增量（调用方退化全量重绘）。
        """
        kdata = getattr(self, 'current_kdata', None)
        colls = getattr(self, '_kline_collections', None)
        vol_colls = getattr(self, '_volume_collections', None)
        if kdata is None or kdata.empty or not colls or not vol_colls:
            return False
        # 性能统计起点（仅成功路径累计，失败/退化不计入 bar 内 tick）
        _t0 = time.perf_counter()
        stats = self._get_tick_perf_stats()
        try:
            price = float(tick.get('price'))
        except (TypeError, ValueError):
            return False
        i = len(kdata) - 1
        # HV6.2：先确保末根 overlay——必须在数据更新前拆分：主体集合仍是
        # 更新前 verts，末根类别须按更新前数据判定，overlay 拆分才与集合
        # 内容一致（更新后类别迁移由 _rebuild_kline_overlay 重建 overlay 完成）
        overlay_ready = self._ensure_tick_overlay()
        full = getattr(self, '_full_kdata', None)
        # 降采样视图末行 == 全量末行（分桶采样 _bucket_key_indices 强制保留首尾行）；
        # 昨收取全量倒数第二根（视图经降采样后相邻 bar 并非真实相邻交易日，用视图
        # 昨收会导致 limit 判定基准漂移）
        if full is not None and not full.empty and len(full) > 1:
            prev_close = float(full['close'].iloc[-2])
        elif i > 0:
            prev_close = float(kdata['close'].iloc[i - 1])
        else:
            prev_close = float(kdata['close'].iloc[i])
        open_ = float(kdata['open'].iloc[i])
        old_high = float(kdata['high'].iloc[i])
        old_low = float(kdata['low'].iloc[i])
        old_vol = float(kdata['volume'].iloc[i])
        new_high = max(old_high, price)
        new_low = min(old_low, price)
        new_vol = old_vol + max(0.0, float(tick.get('volume') or 0))
        # 记录旧类别（更新前末根）：blit 只重画末根相关集合，类别迁移时旧+新集合都要画
        old_close = float(kdata['close'].iloc[i])
        old_open = float(kdata['open'].iloc[i])
        old_lu = bool(kdata['limit_up'].iloc[i]) if 'limit_up' in kdata.columns else False
        old_ld = bool(kdata['limit_down'].iloc[i]) if 'limit_down' in kdata.columns else False

        # 1) 更新数据框（当前降采样视图 + 全量数据保持一致）
        # HV6 修复：视图(≤1200根)与全量(5万根)不等长——分桶采样视图末根=全量末根，
        # 但视图内位置 i ≠ 全量位置，须按各自末行位置 j=len(frame)-1 更新（原 i 会
        # 错位更新全量第 i 行，导致全量末行永不刷新、下次全量刷新数据回退）
        _t = time.perf_counter()
        for frame in (kdata, full):
            if frame is None or frame.empty:
                continue
            j = len(frame) - 1  # 各自末行位置（视图末行=全量末行）
            for col, val in (('close', price), ('high', new_high),
                             ('low', new_low), ('volume', new_vol)):
                if col in frame.columns:
                    frame.iat[j, frame.columns.get_loc(col)] = val
            # limit 末行单根重判（昨收=前一根 close，is_limit_up_down 单点判定）
            symbol = extract_symbol(frame) or getattr(self, 'current_stock', '') or ''
            is_lu, is_ld = is_limit_up_down(prev_close, price, new_high, new_low, symbol)
            if 'limit_up' in frame.columns:
                frame.iat[j, frame.columns.get_loc('limit_up')] = is_lu
            if 'limit_down' in frame.columns:
                frame.iat[j, frame.columns.get_loc('limit_down')] = is_ld
        stats['stage_data_ms'] += (time.perf_counter() - _t) * 1000

        # 2) 重建 verts：HV6.2 优先"末根 overlay"（仅 1 根 bar）——主体集合
        # （前 n-1 根）tick 期间永不动。draw_artist 光栅化 ∝ 顶点数，全视图
        # 重建 + draw 是 5 万行视图下 blit 15ms 的瓶颈；overlay 不可用
        # （单根数据/集合缺失）时回退全视图重建（向量化后 ~6ms，仍远快于全量）
        xvals = np.arange(len(kdata))
        _t = time.perf_counter()
        if overlay_ready:
            ok_kline = self._rebuild_kline_overlay(kdata)
        else:
            ok_kline = self._rebuild_kline_verts(kdata, xvals)
        stats['stage_kline_ms'] += (time.perf_counter() - _t) * 1000
        _t = time.perf_counter()
        if overlay_ready:
            ok_volume = self._rebuild_volume_overlay(kdata)
        else:
            ok_volume = self._rebuild_volume_verts(kdata, xvals)
        stats['stage_volume_ms'] += (time.perf_counter() - _t) * 1000
        if not ok_kline or not ok_volume:
            return False

        # 3) ylim 突破 → invalidate（背景重建），否则 blit 快路径
        _t = time.perf_counter()
        invalidated = False
        if new_high > self._ymax or new_low < self._ymin:
            self._ymax = max(self._ymax, new_high)
            self._ymin = min(self._ymin, new_low)
            try:
                self.price_ax.set_ylim(self._ymin, self._ymax)
                if hasattr(self, '_invalidate_crosshair_background'):
                    self._invalidate_crosshair_background()
            except Exception:
                pass
            invalidated = True

        # 4) 统一 BlitEngine 局部重绘（复用 crosshair 引擎，铁律㊲：单 canvas 单背景管理）
        engine = None
        if hasattr(self, '_ensure_blit_engine'):
            try:
                engine = self._ensure_blit_engine()
            except Exception:
                engine = None
        if engine is None:
            engine = getattr(self, '_blit_engine', None)
        # HV6.1 blit 范围缩小：只重画"末根相关集合"（新类别 + 迁移旧类别）——
        # 其他集合 verts 未变（背景快照像素仍正确），全量 draw_artist 8 集合是
        # 5 万行视图下 blit 20ms 的瓶颈，缩小后仅 2~4 集合（Agg 光栅化 ∝ 顶点数）
        def _cat_keys(lu_f, ld_f, close_v, open_v):
            if lu_f:
                return ('limit_up', 'shadow_limit_up')
            if ld_f:
                return ('limit_down', 'shadow_limit_down')
            return ('up', 'shadow_up') if close_v >= open_v else ('down', 'shadow_down')

        new_lu = bool(kdata['limit_up'].iloc[i]) if 'limit_up' in kdata.columns else False
        new_ld = bool(kdata['limit_down'].iloc[i]) if 'limit_down' in kdata.columns else False
        k_keys = set(_cat_keys(new_lu, new_ld, price, open_)) | \
                 set(_cat_keys(old_lu, old_ld, old_close, old_open))
        # HV6.2：draw 对象取末根 overlay（每集合仅 1 根 bar → 光栅化 <1ms）；
        # overlay 不可用时回退主体集合（前 n-1 根 + 末根，数百根，光栅化 ~15ms）
        if overlay_ready:
            artists = ([self._kline_overlay[k] for k in k_keys
                        if self._kline_overlay.get(k) is not None]
                       + [self._volume_overlay[k] for k in k_keys
                          if self._volume_overlay.get(k) is not None])
        else:
            artists = ([colls[k] for k in k_keys if colls.get(k) is not None]
                       + [vol_colls[k] for k in k_keys if vol_colls.get(k) is not None])
        if engine is not None:
            try:
                # 背景将重建（首次/失效后）时先隐藏十字线，保证快照不含十字线残影
                # （与 crosshair_mixin._blit_crosshair 预处理一致，铁律㊲ 单背景管理）
                if not engine.background_cached and hasattr(self, '_hide_crosshair_elements'):
                    self._hide_crosshair_elements()
                ok = engine.render(artists)
                if ok:
                    # 同步背景快照为最新 K 线像素：否则鼠标移动（十字光标 blit）
                    # 会 restore 回 tick 前的旧快照，bar 内 tick 更新像素级回退
                    if hasattr(engine, 'refresh_background'):
                        engine.refresh_background()
                elif hasattr(self, 'canvas'):
                    self.canvas.draw_idle()
            except Exception:
                if hasattr(self, 'canvas'):
                    self.canvas.draw_idle()
        elif hasattr(self, 'canvas') and self.canvas:
            self.canvas.draw_idle()
        stats['stage_blit_ms'] += (time.perf_counter() - _t) * 1000

        # 5) 性能统计累计：bar 内 tick 计数/耗时 + 慢 tick 告警 + 聚合日志节流
        elapsed_ms = (time.perf_counter() - _t0) * 1000
        stats['bar_count'] += 1
        stats['bar_total_ms'] += elapsed_ms
        stats['bar_max_ms'] = max(stats['bar_max_ms'], elapsed_ms)
        stats['agg_count'] += 1
        stats['agg_total_ms'] += elapsed_ms
        stats['agg_max_ms'] = max(stats['agg_max_ms'], elapsed_ms)
        if elapsed_ms > self.SLOW_TICK_MS:
            logger.warning(
                f"[PERF][TickIncremental] 慢tick: bar内tick单次耗时 {elapsed_ms:.1f}ms "
                f"超阈值 {self.SLOW_TICK_MS:.1f}ms (累计{stats['bar_count']}次)")
        if stats['agg_count'] >= self.PERF_SAMPLE_EVERY:
            self._log_tick_perf_agg(stats)
            stats['agg_count'] = 0
            stats['agg_total_ms'] = 0.0
            stats['agg_max_ms'] = 0.0
        return True

    # ============================================================
    # HV6.2 末根 overlay：主体集合（前 n-1 根）与末根分离，tick 只重建+draw
    # overlay（1 根 bar）——draw_artist 光栅化 ∝ 顶点数，全视图重建 + draw
    # 是 5 万行视图下 blit 15ms 的瓶颈，overlay 方案降至 <1ms 级。
    # ============================================================
    def _ensure_tick_overlay(self) -> bool:
        """确保末根 overlay 集合可用：已存在直接返回 True，否则惰性初始化。

        Returns:
            True=overlay 可用；False=初始化失败（非 K线图/集合缺失/数据过短），
            调用方（tick 路径）回退全视图重建 _rebuild_kline_verts。
        """
        if getattr(self, '_kline_overlay', None) and getattr(self, '_volume_overlay', None):
            return True
        return self._setup_tick_overlay()

    def _setup_tick_overlay(self) -> bool:
        """末根 overlay 初始化：从主体集合拆出末根 verts/segments。

        - 主体集合（8 K线 + 4 成交量）set_verts 前 n-1 根（tick 期间永不动）；
        - 末根归入新建 overlay 集合（仅 1 根 bar，复制主体样式，后 add 覆盖绘制）；
        - update_chart 全量重绘后必须重新调用（ax.clear 已移除旧集合）。

        Returns:
            True=拆分成功；False=条件不满足（单根数据/集合缺失/ax 缺失）。
        """
        colls = getattr(self, '_kline_collections', None)
        vol_colls = getattr(self, '_volume_collections', None)
        kdata = getattr(self, 'current_kdata', None)
        if kdata is None or kdata.empty or not colls or not vol_colls:
            return False
        if len(kdata) < 2:
            # 单根数据：主体为空，overlay 无意义，tick 走全视图重建（成本可忽略）
            return False
        price_ax = getattr(self, 'price_ax', None)
        volume_ax = getattr(self, 'volume_ax', None)
        if price_ax is None or volume_ax is None:
            return False
        try:
            # 末根类别判定（列优先，与渲染链同规则）
            i = len(kdata) - 1
            lu = bool(kdata['limit_up'].iloc[i]) if 'limit_up' in kdata.columns else False
            ld = bool(kdata['limit_down'].iloc[i]) if 'limit_down' in kdata.columns else False
            up = (not lu and not ld
                  and kdata['close'].iloc[i] >= kdata['open'].iloc[i])
            down = not lu and not ld and not up

            kline_overlay = {}
            for key, is_last in (('up', up), ('down', down),
                                 ('limit_up', lu), ('limit_down', ld)):
                src = colls.get(key)
                src_shadow = colls.get('shadow_' + key)
                # 柱：主体去掉末根（verts[:-1]），末根归 overlay（verts[-1:]）。
                # PolyCollection 无 get_verts()，从 get_paths() 的 Path.vertices 恢复；
                # matplotlib 闭合 Path 首点重复（4 顶点 → Path 5 顶点），恢复时去重。
                # 注意：body 为 (0,4,2) 空数组（类别只含末根 1 根，如连续下跌后拉红）
                # 也必须 set_verts 清空主体——否则主体残留末根，tick 迁移类别时主体
                # 不在 blit 范围，旧末根成为不可清除的残影（HV6.2 边界修复）。
                body_verts = None
                last_verts = None
                if src is not None:
                    paths = src.get_paths()
                    if len(paths) > 0:
                        verts = np.array([p.vertices for p in paths])
                        if verts.ndim == 3 and verts.shape[1] == 5:
                            verts = verts[:, :-1, :]
                        if is_last:
                            body_verts = verts[:-1]
                            last_verts = verts[-1:]
                        else:
                            body_verts = verts
                if body_verts is not None:
                    src.set_verts(body_verts)
                # 影线：segments 同理
                body_segs = None
                last_segs = None
                if src_shadow is not None:
                    segs = src_shadow.get_segments()
                    if len(segs) > 0:
                        if is_last:
                            body_segs = segs[:-1]
                            last_segs = segs[-1:]
                        else:
                            body_segs = segs
                if body_segs is not None:
                    src_shadow.set_segments(body_segs)
                # overlay 集合（仅末根）：复制主体样式，add 到 ax（后 add 覆盖绘制）
                ov = self._new_overlay_collection(src, last_verts, shadow=False)
                ov_shadow = self._new_overlay_collection(src_shadow, last_segs, shadow=True)
                if ov is not None:
                    price_ax.add_collection(ov)
                if ov_shadow is not None:
                    price_ax.add_collection(ov_shadow)
                kline_overlay[key] = ov
                kline_overlay['shadow_' + key] = ov_shadow

            volume_overlay = {}
            for key, is_last in (('up', up), ('down', down),
                                 ('limit_up', lu), ('limit_down', ld)):
                src = vol_colls.get(key)
                body_verts = None
                last_verts = None
                if src is not None:
                    paths = src.get_paths()
                    if len(paths) > 0:
                        verts = np.array([p.vertices for p in paths])
                        if verts.ndim == 3 and verts.shape[1] == 5:
                            verts = verts[:, :-1, :]
                        if is_last:
                            body_verts = verts[:-1]
                            last_verts = verts[-1:]
                        else:
                            body_verts = verts
                if body_verts is not None:
                    src.set_verts(body_verts)
                ov = self._new_overlay_collection(src, last_verts, shadow=False)
                if ov is not None:
                    volume_ax.add_collection(ov)
                volume_overlay[key] = ov

            self._kline_overlay = kline_overlay
            self._volume_overlay = volume_overlay
            return True
        except Exception as e:
            logger.debug(f"末根 overlay 初始化失败，回退全视图重建: {e}")
            self._kline_overlay = None
            self._volume_overlay = None
            return False

    @staticmethod
    def _new_overlay_collection(src, verts, shadow=False):
        """从主体集合复制样式创建 overlay 集合。

        verts 为 None（末根不属于该类别）时创建空集合 ((0,4,2)/(0,2,2))——
        必须为全部类别都建集合，tick 类别迁移时可 set_verts 到任意类别；
        src 为 None（视图无该类别柱，末根必然也不属于它）时用中性默认样式，
        该集合永不可见，样式无关紧要。
        """
        from matplotlib.collections import PolyCollection, LineCollection
        if verts is None:
            verts = np.empty((0, 4, 2) if not shadow else (0, 2, 2))
        try:
            if shadow:
                colors = src.get_color() if src is not None else '#888888'
                lw = src.get_linewidth() if src is not None else 1.0
                alpha = src.get_alpha() if src is not None else 1.0
                zorder = src.get_zorder() if src is not None else 1
                return LineCollection(
                    verts, colors=colors, linewidth=lw, alpha=alpha, zorder=zorder)
            face = src.get_facecolor() if src is not None else 'none'
            edge = src.get_edgecolor() if src is not None else '#888888'
            lw = src.get_linewidth() if src is not None else 1.0
            alpha = src.get_alpha() if src is not None else 1.0
            zorder = src.get_zorder() if src is not None else 1
            return PolyCollection(
                verts, facecolor=face, edgecolor=edge,
                linewidth=lw, alpha=alpha, zorder=zorder)
        except Exception:
            return None

    def _rebuild_kline_overlay(self, kdata) -> bool:
        """只重建末根 K 线 overlay 集合 verts（1 根 bar，替代全视图重建）。

        Returns:
            True=成功；False=overlay 缺失/重建失败（调用方已回退或退化全量）。
        """
        overlay = getattr(self, '_kline_overlay', None)
        renderer = getattr(self, 'renderer', None)
        if not overlay or renderer is None or not hasattr(renderer, 'build_candle_groups'):
            return False
        i = len(kdata) - 1
        lu = (np.array([bool(kdata['limit_up'].iloc[i])])
              if 'limit_up' in kdata.columns else np.array([False]))
        ld = (np.array([bool(kdata['limit_down'].iloc[i])])
              if 'limit_down' in kdata.columns else np.array([False]))
        try:
            (vu, vd, vlu, vld, su, sd, slu, sld) = renderer.build_candle_groups(
                kdata.iloc[[i]], np.array([float(i)]), lu, ld)
        except Exception:
            return False
        for key, verts in (('up', vu), ('down', vd),
                           ('limit_up', vlu), ('limit_down', vld)):
            coll = overlay.get(key)
            if coll is not None:
                coll.set_verts(verts)
        for key, segs in (('shadow_up', su), ('shadow_down', sd),
                          ('shadow_limit_up', slu), ('shadow_limit_down', sld)):
            coll = overlay.get(key)
            if coll is not None:
                coll.set_segments(segs)
        return True

    def _rebuild_volume_overlay(self, kdata) -> bool:
        """只重建末根成交量 overlay 集合 verts（1 根 bar）"""
        overlay = getattr(self, '_volume_overlay', None)
        renderer = getattr(self, 'renderer', None)
        if not overlay or renderer is None or not hasattr(renderer, 'build_volume_groups'):
            return False
        i = len(kdata) - 1
        try:
            (vu, vd, vlu, vld) = renderer.build_volume_groups(
                kdata.iloc[[i]], np.array([float(i)]))
        except Exception:
            return False
        for key, verts in (('up', vu), ('down', vd),
                           ('limit_up', vlu), ('limit_down', vld)):
            coll = overlay.get(key)
            if coll is not None:
                coll.set_verts(verts)
        return True

    def _rebuild_kline_verts(self, kdata, xvals) -> bool:
        """按当前 kdata 重建 K 线 8 集合 verts/segments（set_verts/set_segments）"""
        colls = getattr(self, '_kline_collections', None)
        renderer = getattr(self, 'renderer', None)
        if not colls or renderer is None or not hasattr(renderer, 'build_candle_groups'):
            return False
        lu = (kdata['limit_up'].to_numpy(dtype=bool)
              if 'limit_up' in kdata.columns else np.zeros(len(kdata), dtype=bool))
        ld = (kdata['limit_down'].to_numpy(dtype=bool)
              if 'limit_down' in kdata.columns else np.zeros(len(kdata), dtype=bool))
        try:
            (vu, vd, vlu, vld, su, sd, slu, sld) = renderer.build_candle_groups(kdata, xvals, lu, ld)
        except Exception:
            return False
        for key, verts in (('up', vu), ('down', vd),
                           ('limit_up', vlu), ('limit_down', vld)):
            coll = colls.get(key)
            if coll is not None:
                coll.set_verts(verts)
        for key, segs in (('shadow_up', su), ('shadow_down', sd),
                          ('shadow_limit_up', slu), ('shadow_limit_down', sld)):
            coll = colls.get(key)
            if coll is not None:
                coll.set_segments(segs)
        return True

    def _rebuild_volume_verts(self, kdata, xvals) -> bool:
        """按当前 kdata 重建成交量 4 集合 verts"""
        colls = getattr(self, '_volume_collections', None)
        renderer = getattr(self, 'renderer', None)
        if not colls or renderer is None or not hasattr(renderer, 'build_volume_groups'):
            return False
        try:
            (vu, vd, vlu, vld) = renderer.build_volume_groups(kdata, xvals)
        except Exception:
            return False
        for key, verts in (('up', vu), ('down', vd),
                           ('limit_up', vlu), ('limit_down', vld)):
            coll = colls.get(key)
            if coll is not None:
                coll.set_verts(verts)
        return True

    def _append_new_bar(self, tick):
        """新 bar（跨周期）：追加到全量数据 → update_chart 全量重绘。
        x 轴右移/指标/xticks 需整体刷新，一次性背景重建后分钟级 tick 免费。"""
        try:
            full = getattr(self, '_full_kdata', None)
            if full is None:
                return
            price = float(tick.get('price'))
            ts = tick.get('timestamp')
            vol = float(tick.get('volume') or 0)
            new_row = {'open': price, 'high': price, 'low': price,
                       'close': price, 'volume': vol}
            if ts is not None:
                new_row['datetime'] = pd.to_datetime(ts)
            if 'limit_up' in full.columns:
                new_row['limit_up'] = False
                new_row['limit_down'] = False
            self._full_kdata = pd.concat(
                [full, pd.DataFrame([new_row])], ignore_index=True)
            self.update_chart({'kdata': self._full_kdata})
        except Exception as e:
            logger.debug(f"追加新 bar 失败: {e}")

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
                # V-04: 分时均价线颜色（主题键 avg_line，缺省黄色，向后兼容）
                'avg_color': processed_colors.get('avg_line', '#ffd700'),
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
            # HV6：全量重绘后失效 blit 背景（否则十字光标 restore 复活已清空内容）
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()

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
            # HV6：主题改色后背景快照过期（否则鼠标移动 restore 回旧主题色）
            if hasattr(self, '_invalidate_crosshair_background'):
                self._invalidate_crosshair_background()

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
                # HV6：figure.clear() 重建子图，背景必须失效
                if hasattr(self, '_invalidate_crosshair_background'):
                    self._invalidate_crosshair_background()

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
