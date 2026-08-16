from loguru import logger

from gui.widgets.chart_mixins.ui_mixin import UIMixin
"""
图表控件工具方法Mixin

该模块包含ChartWidget的工具方法，包括：
- 数据处理和格式化
- 周期变更处理
- 可见范围获取
- 基础的图表操作方法
"""

import numpy as np
import pandas as pd
import traceback
from datetime import datetime, timedelta
from typing import Tuple, Optional


def _bucket_key_indices(kdata, max_points):
    """分桶选择代表性行索引：每桶保留 峰(最高价)+谷(最低价) 两行，桶内含
    涨跌停时追加涨跌停行；首尾行强制保留（走势连续性）

    R292-HV4：替代等距 linspace 抽行——等距抽行会丢失桶内最高/最低、涨跌停、
    巨量 bar（关键价格形态失真）。迭代修正（T3 实测暴露）：原"巨量>最高>最低"
    单行优先级中 volume 列必然存在导致巨量分支独占、峰谷兜底成死代码；改为
    每桶 峰+谷 双行（信息量翻倍），涨跌停 P0 四色追加，首尾强制保留。选"整行"
    保持"每根蜡烛=真实交易日 bar"语义（指标/十字光标不受影响）；
    limit_up/limit_down 列随行保留（铁律⑲/㉑：limit 掩码由上游降采样前全量
    计算，此处仅做行选择不重判）。

    ponytail: 涨跌停桶最多 3 行/桶，极端数据下总行数可能轻微超出 max_points
    （渲染上限仍在 ~1800 根内）；如需硬性预算可改为"涨跌停替换谷"。

    Args:
        kdata: K线数据DataFrame
        max_points: 目标最大行数

    Returns:
        np.ndarray: 选中的行索引（升序，正常情况长度 ≤ max_points）
    """
    n = len(kdata)
    if n <= max_points:
        return np.arange(n)
    # 每桶 2 行（峰+谷）满配：num_buckets=(max_points-2)//2 预留首尾 2 行；
    # 涨跌停桶追加行使总行数在极端数据下轻微超出 max_points（渲染上限仍在
    # ~1800 根内，性能不受影响）——ponytail: 如需硬性预算可改"涨跌停替换谷"
    num_buckets = max(1, (max_points - 2) // 2)
    edges = np.linspace(0, n, num_buckets + 1).astype(int)
    has_limit = 'limit_up' in kdata.columns and 'limit_down' in kdata.columns
    hi = kdata['high'].to_numpy(dtype=float)
    lo = kdata['low'].to_numpy(dtype=float)
    lu = kdata['limit_up'].to_numpy(dtype=bool) if has_limit else None
    ld = kdata['limit_down'].to_numpy(dtype=bool) if has_limit else None
    chosen = []
    for s, e in zip(edges[:-1], edges[1:]):
        if s >= e:
            continue
        picks = {s + int(np.argmax(hi[s:e]))}  # 峰：桶内最高价
        if has_limit:
            hit_u = np.nonzero(lu[s:e])[0]
            hit_d = np.nonzero(ld[s:e])[0]
            if len(hit_u):
                picks.add(s + int(hit_u[0]))  # 涨停（P0 四色）
            if len(hit_d):
                picks.add(s + int(hit_d[0]))  # 跌停（P0 四色）
        if len(picks) < 2:
            picks.add(s + int(np.argmin(lo[s:e])))  # 谷：桶内最低价
        chosen.extend(picks)
    return np.array(sorted(set(chosen) | {0, n - 1}))


class UtilityMixin:
    """工具功能Mixin

    包含ChartWidget的各种工具方法和辅助功能
    """

    def _downsample_kdata(self, kdata, max_points=1200):
        """对K线数据做降采样，提升渲染性能

        R293-G3: 分钟/日内频率数据改为按交易日时间窗口聚合抽样——每个交易日
        至少保留 max_points//交易日数 根（下限2），长历史分钟数据不再被等距
        抽样稀疏化到"当日仅剩数根"（当日走势细节不丢）。日线等低频维持等距抽样。

        R292-HV4: 日线兜底抽样由"等距 linspace 抽行"升级为"分桶代表性行"——
        等距抽行会丢失桶内最高价/最低价、涨跌停、巨量 bar（关键价格形态失真）；
        桶内按优先级 涨跌停→巨量→最高价→最低价 选代表性整行，limit 列随行保留
        （铁律⑲/㉑：limit 掩码由上游降采样前全量计算，此处仅做行选择不重判）。

        Args:
            kdata: K线数据DataFrame
            max_points: 最大点数，默认1200

        Returns:
            pd.DataFrame: 降采样后的K线数据
        """
        if len(kdata) <= max_points:
            return kdata
        if self._is_minute_frequency(kdata):
            # 分钟数据：按交易日聚合抽样，保证每个交易日保留足够的走势细节
            try:
                ts = pd.to_datetime(kdata['datetime'])
                days = ts.dt.normalize()
                n_days = int(days.nunique())
                per_day = max(2, max_points // n_days)
                groups = []
                for _, grp in kdata.groupby(days, sort=False):
                    if len(grp) <= per_day:
                        groups.append(grp)
                    else:
                        idx = _bucket_key_indices(grp, per_day)
                        groups.append(grp.iloc[idx])
                return pd.concat(groups)
            except Exception:
                pass  # 聚合失败回退等距抽样
        idx = _bucket_key_indices(kdata, max_points)
        return kdata.iloc[idx]

    @staticmethod
    def _is_minute_frequency(kdata) -> bool:
        """判断K线数据是否为分钟/日内频率（相邻时刻间隔 < 1 天）

        R293: 分钟降采样感知与时刻标签共用。datetime 列优先，缺失时检查
        DatetimeIndex。数值型整数日期按 _coerce_to_datetime 语义解析，
        避免 pd.to_datetime(int) 按纳秒解释产生 1ns 假间隔误判为分钟。
        """
        try:
            if kdata is None or len(kdata) < 2:
                return False
            if 'datetime' in kdata.columns:
                col = kdata['datetime']
                ts = pd.to_datetime(
                    col.map(UtilityMixin._coerce_to_datetime), errors='coerce')
                ts = ts.dropna()
                if len(ts) >= 2:
                    diffs = ts.diff().dropna()
                    if len(diffs) and diffs.median() < pd.Timedelta(days=1):
                        return True
            # datetime 列缺失或无法解析 → 检查 DatetimeIndex
            if pd.api.types.is_datetime64_any_dtype(kdata.index):
                ts = pd.to_datetime(kdata.index)
                diffs = ts.diff().dropna()
                if len(diffs) and diffs.median() < pd.Timedelta(days=1):
                    return True
        except Exception:
            pass
        return False

    def _safe_format_date(self, row, idx, kdata, period=None):
        """安全地格式化日期，处理数值索引和datetime索引的情况

        R293-G1: 增加分钟/分时感知——分钟频率数据 X 轴刻度标签输出时刻
        （当日 '%H:%M'，历史交易日 '%m-%d %H:%M' 防止同日标签重复），
        日线维持 '%Y-%m-%d'。频率判断优先使用调用方传入的 period
        （Period.is_intraday），未传入时回退按数据自身间隔检测
        （_is_minute_frequency）。

        Args:
            row: K线数据行
            idx: K线索引
            kdata: K线数据DataFrame
            period: 可选周期字符串（如 '1m'/'D'/'分时'），用于分钟感知

        Returns:
            str: 格式化后的日期字符串
        """
        is_minute = False
        if period is not None:
            from core.plugin_types import Period
            is_minute = Period.is_intraday(period)
        if not is_minute:
            is_minute = self._is_minute_frequency(kdata)

        fmt = '%m-%d %H:%M' if is_minute else '%Y-%m-%d'
        try:
            if is_minute and 'datetime' in kdata.columns:
                # 分钟数据：按 datetime 列解析，当日只显示时刻，历史日含日期
                try:
                    ts = pd.to_datetime(
                        kdata['datetime'].map(self._coerce_to_datetime),
                        errors='coerce')
                    ts_val = ts.iloc[idx]
                    if pd.notna(ts_val):
                        last_day = ts.max().normalize()
                        if ts_val.normalize() == last_day:
                            return ts_val.strftime('%H:%M')
                        return ts_val.strftime('%m-%d %H:%M')
                except Exception:
                    pass
            # 优先从kdata的实际索引获取datetime
            if hasattr(kdata.index[idx], 'strftime'):
                return kdata.index[idx].strftime(fmt)
            elif hasattr(row.name, 'strftime'):
                # 如果索引本身是datetime
                return row.name.strftime(fmt)
            else:
                # 如果都不是datetime，检查是否有datetime列
                if 'datetime' in kdata.columns:
                    try:
                        date_val = self._coerce_to_datetime(kdata.iloc[idx]['datetime'])
                        if date_val is not None:
                            return date_val.strftime(fmt)
                    except Exception:
                        pass

                # 尝试转换索引
                try:
                    date_val = self._coerce_to_datetime(kdata.index[idx])
                    if date_val is not None:
                        return date_val.strftime(fmt)
                except Exception:
                    pass
                # 最后的兜底方案：使用索引位置生成相对日期
                base_date = datetime(2024, 1, 1)
                actual_date = base_date + timedelta(days=idx)
                return actual_date.strftime(fmt)
        except Exception:
            return f"第{idx}根K线"

    def _refresh_x_date_ticks(self):
        """R294: 按当前可见 X 轴范围重新生成日期刻度标签（缩放/平移后联动）。

        渲染路径一次性写入全量等距固定 xticks（rendering_mixin L470-486 /
        chart_widget L739-752 等），缩放/平移后 xlim 变化但刻度不跟随 → 缩放后
        日期标签缺失/错位。本方法按 price_ax 当前可见区间重算 ticks/labels，
        注册为 price_ax 的 'xlim_changed' 回调（zoom_mixin._init_zoom_interaction），
        一处注册覆盖框选缩放/右拖平移/滚轮缩放/双击还原全部路径；set_xticks
        不改变 xlim，无递归触发风险（_limit_xlim 二次 set_xlim 触发亦幂等）。
        """
        ax = getattr(self, 'indicator_ax', None)
        kdata = getattr(self, 'current_kdata', None)
        if ax is None or kdata is None or len(kdata) == 0:
            return
        left, right = self.price_ax.get_xlim()
        start = max(0, int(left))
        end = min(len(kdata), int(right) + 1)
        if end <= start:
            return
        n_vis = end - start
        step = max(1, n_vis // 8)
        xticks = np.arange(start, end, step)
        xticklabels = [self._safe_format_date(
            kdata.iloc[i], i, kdata,
            getattr(self, 'current_period', None)) for i in xticks]
        ax.set_xticks(xticks)
        ax.set_xticklabels(xticklabels, rotation=30, fontsize=8)

    @staticmethod
    def _coerce_to_datetime(val) -> Optional[pd.Timestamp]:
        """将日期值安全转换为 Timestamp；无法解析返回 None。

        R292 修复：pd.to_datetime(int) 会把整数按纳秒时间戳解释
        （如 20240814 → 1970-01-01 00:00:00.020240814），产生"所有日期
        基本都一样"的 1970 假象。数值型日期按常见格式解析：
        - 6 位 YYYYMM / 8 位 YYYYMMDD → 字符串解析
        - 9~11 位 → Unix 秒时间戳
        - 其余数字（如普通 RangeIndex 0,1,2…）→ None（走调用方兜底）
        """
        if val is None:
            return None
        if isinstance(val, bool):
            return None
        try:
            if isinstance(val, (int, np.integer, float, np.floating)):
                if pd.isna(val):
                    return None
                s = str(int(val))
                if len(s) == 6:
                    return pd.to_datetime(s, format='%Y%m')
                if len(s) == 8:
                    return pd.to_datetime(s, format='%Y%m%d')
                if 9 <= len(s) <= 11:
                    return pd.to_datetime(int(s), unit='s', errors='coerce')
                return None
            return pd.to_datetime(val)
        except Exception:
            return None

    def on_period_changed(self, period: str):
        """处理周期变更事件

        Args:
            period: 周期名称
        """
        try:
            from core.plugin_types import Period

            # 使用统一的 Period 枚举类转换周期
            self.current_period = Period.normalize(period)

            # 发出周期变更信号
            self.period_changed.emit(self.current_period)

            # 如果设置了调试日志
            logger.info(f"周期已变更为: {period} -> {self.current_period}")

        except Exception as e:
            error_msg = f"处理周期变更失败: {str(e)}"
            logger.error(error_msg)
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(error_msg)

    def on_chart_type_changed(self, chart_type: str):
        """处理图表类型变更事件

        Args:
            chart_type: 图表类型名称
        """
        try:
            # 保存当前图表类型
            self.current_chart_type = chart_type

            # 如果设置了调试日志
            logger.info(f"图表类型已变更为: {chart_type}")

            # 发出图表类型变更信号
            if hasattr(self, 'chart_type_changed'):
                self.chart_type_changed.emit(chart_type)

        except Exception as e:
            error_msg = f"处理图表类型变更失败: {str(e)}"
            logger.error(error_msg)
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(error_msg)

    def on_time_range_changed(self, time_range: str):
        """处理时间范围变更事件

        Args:
            time_range: 时间范围名称
        """
        try:
            # 保存当前时间范围
            self.current_time_range = time_range

            # 如果设置了调试日志
            logger.info(f"时间范围已变更为: {time_range}")

            # 发出时间范围变更信号
            if hasattr(self, 'time_range_changed'):
                self.time_range_changed.emit(time_range)

        except Exception as e:
            error_msg = f"处理时间范围变更失败: {str(e)}"
            logger.error(error_msg)
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(error_msg)

    def refresh(self) -> None:
        """
        刷新当前图表内容，异常只记录日志不抛出。
        若有数据则重绘K线图，否则显示"无数据"提示。
        """
        try:
            # 调用ChartWidget的refresh方法，它会正确调用update_chart
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                # 使用ChartWidget的refresh方法
                if hasattr(self.__class__, 'refresh') and self.__class__.refresh != UIMixin.refresh:
                    # 调用ChartWidget的refresh方法
                    super(UIMixin, self).refresh()
                else:
                    # 直接调用update_chart（R267: 使用完整数据源）
                    self.update_chart({'kdata': self._get_render_kdata()})
            else:
                self.show_no_data("无数据")
        except Exception as e:
            error_msg = f"刷新图表失败: {str(e)}"
            logger.error(error_msg)
            # 发射异常信号，主窗口可捕获弹窗
            if hasattr(self, 'error_occurred'):
                self.error_occurred.emit(error_msg)
            # 确保错误情况下也显示错误提示
            self.show_no_data(f"刷新失败: {str(e)}")

    def update(self) -> None:
        """
        兼容旧接口，重定向到refresh。
        """
        self.refresh()

    def reload(self) -> None:
        """
        兼容旧接口，重定向到refresh。
        """
        self.refresh()

    def get_visible_range(self) -> Optional[Tuple[int, int]]:
        """获取当前主图可见区间的K线索引范围

        Returns:
            Optional[Tuple[int, int]]: (开始索引, 结束索引) 或 None
        """
        try:
            xlim = self.indicator_ax.get_xlim()
            return int(xlim[0]), int(xlim[1])
        except Exception:
            return None

    def _get_render_kdata(self):
        """获取用于重新渲染的K线数据源

        R267: 优先返回完整原始数据（_full_kdata），保证任何交互（指标切换/周期变更/刷新等）
        触发的重渲染都基于完整数据重新降采样，避免 current_kdata 被降采样结果覆盖后数据永久丢失。
        无完整数据时回退到 current_kdata（兼容旧路径）。
        """
        full_kdata = getattr(self, '_full_kdata', None)
        if full_kdata is not None and not full_kdata.empty:
            return full_kdata
        return getattr(self, 'current_kdata', None)

    def on_indicator_selected(self, indicators: list):
        """指标选择事件处理

        Args:
            indicators: 选中的指标列表
        """
        self.active_indicators = indicators
        # 修复：传入当前K线数据，否则update_chart会因data=None直接返回
        kdata = self._get_render_kdata()
        if kdata is not None and not kdata.empty:
            self.update_chart({'kdata': kdata})
        else:
            logger.warning("on_indicator_selected: 没有可用的K线数据，无法更新图表")

    def _on_indicator_changed(self, indicators):
        """指标变更处理（内部方法）

        Args:
            indicators: 变更的指标列表
        """
        self.active_indicators = indicators
        # 修复：传入当前K线数据，否则update_chart会因data=None直接返回
        kdata = self._get_render_kdata()
        if kdata is not None and not kdata.empty:
            self.update_chart({'kdata': kdata})
        else:
            logger.warning("_on_indicator_changed: 没有可用的K线数据，无法更新图表")
