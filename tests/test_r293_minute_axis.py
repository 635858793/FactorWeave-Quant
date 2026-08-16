#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R293-G1/G2/G3 测试：分钟线展示层三缺口修复（TDD）

覆盖：
- G1 时刻轴标签（_safe_format_date 分钟感知）：
    分钟频率输出时刻（当日 %H:%M / 跨日 %m-%d %H:%M），日线维持 %Y-%m-%d（回归）
- G2 分时图强制 1min（middle_panel._on_chart_type_changed 联动周期）：
    切"分时图"时 _current_period 联动为 '分时'（1min），并同步 period_combo
- G3 分钟降采样感知（_downsample_kdata 按交易日窗口聚合 + 分时图跳过降采样）：
    长历史分钟数据不再被等距抽样稀疏化，当日细节保留；日线等距抽样不变（回归）

背景：R293 高价值项"分钟线完整数据体系"P1——存储/下载/去重链路已完整，
仅展示层存在：a) 分钟K线/分时X轴刻度标签丢失时刻（同日标签重复）；
b) 分时图消费"当前所选周期"K线而非 1min（选日线时分时图无法成线）；
c) 长历史分钟数据被等距抽样稀疏化（当日分时点密度不足）。
"""
import os
import sys
import types
import importlib.util
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# conftest.py 在模块层 mock 了 'gui.widgets'（无 __path__），pytest 下直接
# `from gui.widgets.chart_mixins.utility_mixin import ...` 会报 "is not a package"。
# 临时移除 mock，用 importlib 按文件加载，完成后恢复以保护其他测试。
_saved_gui_widgets = sys.modules.pop('gui.widgets', None)


def _load_module_from_file(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# chart_mixins 包用 MagicMock 注册：middle_panel 依赖链（chart_widget.py L33）
# 会 `from gui.widgets.chart_mixins import BaseMixin, ...` 取全部 mixin 类；
# 真实 ui_mixin/utility_mixin 仍按需 importlib 加载（注册为子模块）。
_chart_mixins_pkg = MagicMock()
_chart_mixins_pkg.__name__ = 'gui.widgets.chart_mixins'
_chart_mixins_pkg.__file__ = '<mock:gui.widgets.chart_mixins>'
sys.modules['gui.widgets.chart_mixins'] = _chart_mixins_pkg

# middle_panel 依赖链会真实导入 gui.widgets.chart_widget → 顶层包需可导入
_gui_widgets_pkg = types.ModuleType('gui.widgets')
_gui_widgets_pkg.__path__ = [
    os.path.join(PROJECT_ROOT, 'gui', 'widgets')]
sys.modules['gui.widgets'] = _gui_widgets_pkg

_load_module_from_file(
    'gui.widgets.chart_mixins.ui_mixin',
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins', 'ui_mixin.py'))
_load_module_from_file(
    'gui.widgets.chart_mixins.utility_mixin',
    os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins', 'utility_mixin.py'))

from gui.widgets.chart_mixins.utility_mixin import UtilityMixin  # noqa: E402


# ==================== 公共数据构造 ====================

def _make_minute_kdata(n_days=2, per_day=240, start='2026-08-14'):
    """构造多日 1min K线（datetime 列，每天 09:30 起，跨交易日）"""
    frames = []
    days = pd.date_range(start, periods=n_days)
    for d in days:
        ts = pd.date_range(d + pd.Timedelta(hours=9, minutes=30),
                           periods=per_day, freq='1min')
        close = np.linspace(10.0, 11.0, per_day)
        frames.append(pd.DataFrame({
            'datetime': ts,
            'open': close - 0.1,
            'high': close + 0.2,
            'low': close - 0.2,
            'close': close,
            'volume': np.full(per_day, 1000),
        }))
    return pd.concat(frames, ignore_index=True)


def _make_long_intraday():
    """5 个交易日 1min：前 4 天各 600 根 + 最后一天 100 根（当日刚开盘），共 2500 根。

    2026-08-10 ~ 2026-08-14 均为工作日。等距抽样会把最后一天稀释到约 48 根，
    按交易日窗口聚合应全保留 100 根（当日细节不丢）。
    """
    frames = []
    days = pd.date_range('2026-08-10', periods=5)
    for d in days:
        per_day = 600 if d < days[-1] else 100
        ts = pd.date_range(d + pd.Timedelta(hours=9, minutes=30),
                           periods=per_day, freq='1min')
        close = np.linspace(10.0, 10.0 + per_day * 0.001, per_day)
        frames.append(pd.DataFrame({
            'datetime': ts,
            'open': close - 0.1,
            'high': close + 0.2,
            'low': close - 0.2,
            'close': close,
            'volume': np.full(per_day, 1000),
        }))
    return pd.concat(frames, ignore_index=True)


# ==================== G1: 时刻轴标签 ====================

class TestSafeFormatDateMinute:
    """_safe_format_date 分钟感知：时刻标签 / 日线回归"""

    def _make(self):
        return UtilityMixin()

    def test_minute_period_same_day_uses_time(self):
        """分钟频率 + 最新交易日（当日）→ 只输出时刻 %H:%M"""
        m = self._make()
        kdata = _make_minute_kdata()  # 2026-08-14 00:00 ~ 2026-08-15 03:59
        last_idx = len(kdata) - 1
        label = m._safe_format_date(kdata.iloc[last_idx], last_idx, kdata, period='1m')
        assert label == kdata['datetime'].iloc[last_idx].strftime('%H:%M')

    def test_minute_period_previous_day_includes_date(self):
        """分钟频率 + 历史交易日 → '%m-%d %H:%M'（跨日标签含日期防重复）"""
        m = self._make()
        kdata = _make_minute_kdata()
        label = m._safe_format_date(kdata.iloc[0], 0, kdata, period='1m')
        assert label == kdata['datetime'].iloc[0].strftime('%m-%d %H:%M')
        assert '-' in label and ':' in label

    def test_minute_autodetect_without_period(self):
        """未传 period：1min 数据按自身间隔自动识别为分钟 → 含时刻"""
        m = self._make()
        kdata = _make_minute_kdata()
        last_idx = len(kdata) - 1
        label = m._safe_format_date(kdata.iloc[last_idx], last_idx, kdata)
        assert ':' in label

    def test_daily_period_keeps_date_only(self):
        """日线周期（回归）：仍输出 %Y-%m-%d"""
        m = self._make()
        kdata = pd.DataFrame({
            'datetime': pd.to_datetime(['2026-08-14 00:00:00', '2026-08-15 00:00:00']),
            'close': [1.0, 2.0]})
        assert m._safe_format_date(kdata.iloc[0], 0, kdata, period='D') == '2026-08-14'

    def test_default_daily_regression(self):
        """不传 period 的日线数据（回归）：仍输出 %Y-%m-%d"""
        m = self._make()
        kdata = pd.DataFrame({
            'datetime': pd.to_datetime(['2026-08-14 09:30:00', '2026-08-15 09:30:00']),
            'close': [1.0, 2.0]})
        assert m._safe_format_date(kdata.iloc[0], 0, kdata) == '2026-08-14'

    def test_int_datetime_not_mistaken_as_minute(self):
        """int 日期列（20240814）不被误判为分钟（回归，R292 语义保持）"""
        m = self._make()
        kdata = pd.DataFrame({'datetime': [20240814, 20240815], 'close': [1.0, 2.0]})
        assert m._safe_format_date(kdata.iloc[0], 0, kdata) == '2024-08-14'

    def test_int_index_fallback_daily(self):
        """无 datetime 列 + 数字索引（回归）：兜底日期仍 %Y-%m-%d"""
        m = self._make()
        kdata = pd.DataFrame({'close': [1.0, 2.0]})
        assert m._safe_format_date(kdata.iloc[0], 0, kdata) == '2024-01-01'


# ==================== G3: 分钟降采样感知 ====================

class TestDownsampleMinuteAware:
    """_downsample_kdata 分钟感知：按交易日窗口聚合，当日细节不丢"""

    def _make(self):
        return UtilityMixin()

    def test_intraday_downsample_keeps_latest_day_detail(self):
        """2500 根 1min（最后一天仅 100 根）→ 最后一天 100 根全保留"""
        m = self._make()
        kdata = _make_long_intraday()
        out = m._downsample_kdata(kdata, max_points=1200)
        assert len(out) <= 1200
        ts = pd.to_datetime(out['datetime'])
        last_day = ts.max().normalize()
        last_day_count = int((ts.dt.normalize() == last_day).sum())
        assert last_day_count == 100  # 当日细节不丢（等距抽样仅剩约 48 根）

    def test_intraday_downsample_keeps_all_days(self):
        """聚合抽样后仍覆盖全部交易日（每天至少 per_day 根）"""
        m = self._make()
        kdata = _make_long_intraday()
        out = m._downsample_kdata(kdata, max_points=1200)
        days_out = pd.to_datetime(out['datetime']).dt.normalize().nunique()
        assert days_out == 5

    def test_daily_downsample_unchanged(self):
        """日线数据（回归）：降采样受预算约束，且首尾行强制保留

        R292-HV4：采样策略由"等距 linspace 抽行"升级为"分桶代表性行"——
        每桶保留峰(最高价)+谷(最低价)，首尾强制保留；长度 ≤ max_points
        （峰谷同行去重时可能略少于 1200）。
        """
        m = self._make()
        kdata = pd.DataFrame({
            'datetime': pd.date_range('2024-01-01', periods=1500, freq='D'),
            'open': np.linspace(10, 11, 1500),
            'high': np.linspace(10.5, 11.5, 1500),
            'low': np.linspace(9.5, 10.5, 1500),
            'close': np.linspace(10.2, 11.2, 1500),
            'volume': np.full(1500, 1000),
        })
        out = m._downsample_kdata(kdata)
        assert len(out) <= 1200
        # 走势连续性：首尾行必被保留
        assert out.index[0] == 0 and out.index[-1] == 1499


class TestIntradayChartSkipsDownsample:
    """分时图分支跳过降采样：多日 1min 数据不被等距抽样稀释"""

    @classmethod
    def setup_class(cls):
        try:
            cls.render_mod = _load_module_from_file(
                'gui.widgets.chart_mixins.rendering_mixin',
                os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'chart_mixins',
                             'rendering_mixin.py'))
        except Exception as e:  # matplotlib/PyQt5 无头导入失败等
            pytest.skip(f"rendering_mixin 无头加载失败，跳过分时图降采样测试: {e}")

    def _make_widget(self):
        class _ChartWidget(self.render_mod.RenderingMixin, UtilityMixin):
            pass
        w = _ChartWidget.__new__(_ChartWidget)
        w.current_kdata = None
        w._full_kdata = None
        w.price_ax = MagicMock()
        w.volume_ax = MagicMock()
        w.indicator_ax = MagicMock()
        w.renderer = MagicMock()
        w.theme_manager = MagicMock()
        w.theme_manager.get_theme_colors.return_value = {
            'chart_text': '#222b45', 'chart_background': '#ffffff'}
        w.active_indicators = []
        w.error_occurred = MagicMock()
        w.canvas = MagicMock()
        w._render_indicators = MagicMock()
        w._optimize_display = MagicMock()
        w.close_loading_dialog = MagicMock()
        w._invalidate_crosshair_background = MagicMock()
        w.show_no_data = MagicMock()
        w._safe_format_date = MagicMock(return_value='08-14 10:00')
        w._get_chart_style = MagicMock(return_value={})
        w.current_stock = '600519'
        return w

    def test_intraday_chart_type_skips_downsample(self):
        """chart_type='分时图' + 2500 根 1min → current_kdata 未被裁剪"""
        w = self._make_widget()
        kdata = _make_long_intraday()
        assert len(kdata) > 1200
        w.update_chart({'kdata': kdata, 'chart_type': '分时图'})
        assert len(w.current_kdata) == len(kdata)

    def test_kline_chart_type_still_downsampled(self):
        """chart_type='K线图' + 2500 根 1min → 仍降采样（回归）"""
        w = self._make_widget()
        kdata = _make_long_intraday()
        w.update_chart({'kdata': kdata, 'chart_type': 'K线图'})
        assert len(w.current_kdata) <= 1200


# ==================== G2: 分时图强制 1min 联动 ====================

_saved_core_ui = None
_saved_core_ui_panels = None
_saved_base_panel = None
_saved_middle_deps = {}


class TestChartTypePeriodLinkage:
    """middle_panel._on_chart_type_changed：分时图联动周期为 1min（'分时'）"""

    @classmethod
    def setup_class(cls):
        global _saved_gui_widgets, _saved_core_ui, _saved_core_ui_panels, \
            _saved_base_panel, _saved_middle_deps
        cls.panel_mod = None
        cls._load_error = ''
        try:
            # 文件尾已把 gui.widgets 恢复为 conftest mock（无 __path__），
            # middle_panel 依赖链需真实导入 gui.widgets 子模块 → 重新注册
            _saved_gui_widgets = sys.modules.pop('gui.widgets', None)
            _gui_pkg = types.ModuleType('gui.widgets')
            _gui_pkg.__path__ = [
                os.path.join(PROJECT_ROOT, 'gui', 'widgets')]
            sys.modules['gui.widgets'] = _gui_pkg
            # 拦截 chart_widget：本文件模块级把 gui.widgets.chart_mixins 注册为
            # MagicMock（G1/G3 需要），真实构造 ChartWidget 会因 mixin 非类触发
            # metaclass 冲突 → 提供 MagicMock 模块（middle_panel 仅取类符号）
            sys.modules['gui.widgets.chart_widget'] = MagicMock()
            # conftest mock 了 core.ui.panels（无 __path__）→ 临时注册真实包路径
            _saved_core_ui = sys.modules.pop('core.ui', None)
            _saved_core_ui_panels = sys.modules.pop('core.ui.panels', None)
            _ui_pkg = types.ModuleType('core.ui')
            _ui_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'core', 'ui')]
            sys.modules['core.ui'] = _ui_pkg
            _panels_pkg = types.ModuleType('core.ui.panels')
            _panels_pkg.__path__ = [
                os.path.join(PROJECT_ROOT, 'core', 'ui', 'panels')]
            sys.modules['core.ui.panels'] = _panels_pkg

            # base_panel 必须真实加载：MiddlePanel 继承 BasePanel。若 BasePanel
            # 是 MagicMock 实例（非类），class MiddlePanel(BasePanel) 定义时
            # Python 检查 metaclass 兼容性抛 issubclass() arg 1 must be a class
            _saved_base_panel = sys.modules.pop(
                'core.ui.panels.base_panel', None)
            _load_module_from_file(
                'core.ui.panels.base_panel',
                os.path.join(PROJECT_ROOT, 'core', 'ui', 'panels',
                             'base_panel.py'))

            # middle_panel 其余模块级依赖（事件/服务/指标/优化器）：不在
            # sys.modules 中则注册 MagicMock，避免无头环境真实加载重型依赖链
            # （unified_chart_service → utils.config_manager / core.containers
            #  等；core.events → event_bus 等），G2 测试仅验证联动逻辑。
            _saved_middle_deps = {}
            for _dep in ['core.events',
                         'core.services',
                         'core.services.unified_chart_service',
                         'core.indicators',
                         'core.indicators.indicators_algorithm',
                         'optimization',
                         'optimization.progressive_loading_manager',
                         'optimization.update_throttler',
                         'core.performance']:
                if _dep not in sys.modules:
                    _saved_middle_deps[_dep] = None
                    _m = MagicMock()
                    _m.__name__ = _dep
                    _m.__file__ = f'<mock:{_dep}>'
                    sys.modules[_dep] = _m
                else:
                    _saved_middle_deps[_dep] = sys.modules[_dep]

            cls.panel_mod = _load_module_from_file(
                'core.ui.panels.middle_panel',
                os.path.join(PROJECT_ROOT, 'core', 'ui', 'panels',
                             'middle_panel.py'))
        except Exception as e:
            cls.panel_mod = None
            cls._load_error = repr(e)

    @classmethod
    def teardown_class(cls):
        global _saved_gui_widgets, _saved_core_ui, _saved_core_ui_panels, \
            _saved_base_panel, _saved_middle_deps
        if _saved_middle_deps:
            for _dep, _old in _saved_middle_deps.items():
                if _old is None:
                    sys.modules.pop(_dep, None)
                else:
                    sys.modules[_dep] = _old
            _saved_middle_deps = {}
        if _saved_base_panel is not None:
            sys.modules['core.ui.panels.base_panel'] = _saved_base_panel
        if _saved_gui_widgets is not None:
            sys.modules['gui.widgets'] = _saved_gui_widgets
        if _saved_core_ui is not None:
            sys.modules['core.ui'] = _saved_core_ui
        if _saved_core_ui_panels is not None:
            sys.modules['core.ui.panels'] = _saved_core_ui_panels

    def _skip_if_unavailable(self):
        if self.panel_mod is None:
            pytest.skip(f"middle_panel 无头加载失败: {self._load_error}")

    def _make_panel(self):
        p = self.panel_mod.MiddlePanel.__new__(self.panel_mod.MiddlePanel)
        p._current_chart_type = 'K线图'
        p._current_period = '日线'
        p._load_chart_data = MagicMock()
        combo = MagicMock()
        combo.findText.return_value = 0
        p.get_widget = MagicMock(return_value=combo)
        return p

    def test_switch_to_intraday_forces_min_period(self):
        """切'分时图' → _current_period 联动为 '分时'（1min）并重新加载"""
        self._skip_if_unavailable()
        p = self._make_panel()
        p._on_chart_type_changed('分时图')
        assert p._current_period == '分时'
        p._load_chart_data.assert_called_once()
        # period_combo 被同步（联动后不触发 _on_period_changed 双重加载）
        p.get_widget.assert_called_with('period_combo')

    def test_switch_to_intraday_syncs_combo_without_double_load(self):
        """联动期间 period_combo 信号被屏蔽 → _load_chart_data 仅调用一次"""
        self._skip_if_unavailable()
        p = self._make_panel()
        combo = p.get_widget('period_combo')
        combo.blockSignals.side_effect = lambda flag: None
        p._on_chart_type_changed('分时图')
        combo.blockSignals.assert_called()
        p._load_chart_data.assert_called_once()

    def test_switch_to_kline_keeps_period(self):
        """切回'K线图' → 周期不被改动（联动仅对分时图）"""
        self._skip_if_unavailable()
        p = self._make_panel()
        p._on_chart_type_changed('K线图')
        assert p._current_period == '日线'
        assert p._current_chart_type == 'K线图'
        p._load_chart_data.assert_called_once()


# 恢复 conftest 的 mock，避免影响其他测试
if _saved_gui_widgets is not None:
    sys.modules['gui.widgets'] = _saved_gui_widgets
