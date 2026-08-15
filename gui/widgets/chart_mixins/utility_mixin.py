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

class UtilityMixin:
    """工具功能Mixin

    包含ChartWidget的各种工具方法和辅助功能
    """

    def _downsample_kdata(self, kdata, max_points=1200):
        """对K线数据做降采样，提升渲染性能

        Args:
            kdata: K线数据DataFrame
            max_points: 最大点数，默认1200

        Returns:
            pd.DataFrame: 降采样后的K线数据
        """
        if len(kdata) <= max_points:
            return kdata
        idx = np.linspace(0, len(kdata)-1, max_points).astype(int)
        return kdata.iloc[idx]

    def _safe_format_date(self, row, idx, kdata):
        """安全地格式化日期，处理数值索引和datetime索引的情况

        Args:
            row: K线数据行
            idx: K线索引
            kdata: K线数据DataFrame

        Returns:
            str: 格式化后的日期字符串
        """
        try:
            # 优先从kdata的实际索引获取datetime
            if hasattr(kdata.index[idx], 'strftime'):
                return kdata.index[idx].strftime('%Y-%m-%d')
            elif hasattr(row.name, 'strftime'):
                # 如果索引本身是datetime
                return row.name.strftime('%Y-%m-%d')
            else:
                # 如果都不是datetime，检查是否有datetime列
                if 'datetime' in kdata.columns:
                    try:
                        date_val = self._coerce_to_datetime(kdata.iloc[idx]['datetime'])
                        if date_val is not None:
                            return date_val.strftime('%Y-%m-%d')
                    except Exception:
                        pass

                # 尝试转换索引
                try:
                    date_val = self._coerce_to_datetime(kdata.index[idx])
                    if date_val is not None:
                        return date_val.strftime('%Y-%m-%d')
                except Exception:
                    pass
                # 最后的兜底方案：使用索引位置生成相对日期
                base_date = datetime(2024, 1, 1)
                actual_date = base_date + timedelta(days=idx)
                return actual_date.strftime('%Y-%m-%d')
        except Exception:
            return f"第{idx}根K线"

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
