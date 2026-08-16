#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R295 T3 测试：分钟线数据体系图表消费链路

覆盖：
- B1 ChartCanvas.update_chart chart_type 透传（修复覆盖缺陷）：
    ChartCanvas 从未赋值 _current_chart_type（全文件该属性仅存在于 MiddlePanel），
    update_chart 重建 chart_data 时恒取 'K线图'，覆盖上层传入的分时图 chart_type
    （R294 分时渲染分支永远走不到）。修复后透传 stock_data['chart_type']，
    并维护 self._current_chart_type 供分时轮询复用。
- B2 分时图 QTimer 实时刷新（MiddlePanel）：
    - _convert_intraday_to_kline：分时数据（index=DatetimeIndex, [price,vol,amount]）
      → 类1min K线（open=high=low=close=price, volume=vol），零渲染层改动
    - _refresh_intraday_realtime：优先实时分时接口；空/异常静默跳过（保持上次渲染）；
      接口未就绪时节流回退 _load_chart_data（1min K线聚合路径）；防抖（加载中不覆盖）
    - _sync_intraday_timer：分时图启动 / 其他停止 / 旧实例无 timer 兼容
背景：R293-G4 方案 B（分时图实时刷新）——T3 图表消费链路改造。
运行: E:\\anaconda3\\envs\\hikyuu\\python.exe -m pytest tests/test_r295_intraday_chart.py -q --no-header
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

# conftest.py 在模块层 mock 了 'gui.widgets'/'core.ui'/'core.ui.panels'（无 __path__），
# pytest 下直接导入真实子模块会报 "is not a package"。临时移除 mock、注册真实包路径，
# 用 importlib 按文件加载 middle_panel；完成后恢复以保护其他测试（参照 test_r293）。
_saved_gui_widgets = sys.modules.pop('gui.widgets', None)
_saved_core_ui = sys.modules.pop('core.ui', None)
_saved_core_ui_panels = sys.modules.pop('core.ui.panels', None)
_saved_base_panel = sys.modules.pop('core.ui.panels.base_panel', None)
_saved_core_services = sys.modules.pop('core.services', None)


def _load_module_from_file(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---- 包路径注册（真实子模块导入所需）----
_gui_pkg = types.ModuleType('gui.widgets')
_gui_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'gui', 'widgets')]
sys.modules['gui.widgets'] = _gui_pkg

_core_ui_pkg = types.ModuleType('core.ui')
_core_ui_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'core', 'ui')]
sys.modules['core.ui'] = _core_ui_pkg

_core_ui_panels_pkg = types.ModuleType('core.ui.panels')
_core_ui_panels_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'core', 'ui', 'panels')]
sys.modules['core.ui.panels'] = _core_ui_panels_pkg

_core_services_pkg = types.ModuleType('core.services')
_core_services_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'core', 'services')]
sys.modules['core.services'] = _core_services_pkg

# base_panel 必须真实加载：MiddlePanel 继承 BasePanel。若 BasePanel 是 MagicMock
# 实例（非类），class MiddlePanel(BasePanel) 定义时抛 issubclass() arg 1 must be a class
_load_module_from_file(
    'core.ui.panels.base_panel',
    os.path.join(PROJECT_ROOT, 'core', 'ui', 'panels', 'base_panel.py'))

# core.events 必须真实加载：middle_panel 用 @pyqtSlot(UIDataReadyEvent) 装饰，
# pyqtSlot 要求参数为真实类型（MagicMock 报 "bytes or ASCII string expected"）。
import core.events  # noqa: E402

# 真实加载 unified_data_manager（_refresh_intraday_realtime 运行时导入 +
# patch get_unified_data_manager；该模块模块级导入均有 try/except 防御）
_load_module_from_file(
    'core.services.unified_data_manager',
    os.path.join(PROJECT_ROOT, 'core', 'services', 'unified_data_manager.py'))

# middle_panel 其余模块级依赖：不在 sys.modules 则注册 MagicMock，避免无头环境
# 真实加载重型依赖链（参照 test_r293 TestChartTypePeriodLinkage.setup_class）。
# 注意: core.performance 不 mock —— 它是真实包，middle_panel 导入成功走真实
# measure_performance 装饰器（wrapper 执行原函数并返回结果，测试可正常调用）。
_saved_middle_deps = {}
for _dep in ['core.services.unified_chart_service',
             'core.indicators',
             'core.indicators.indicators_algorithm',
             'optimization',
             'optimization.progressive_loading_manager',
             'optimization.update_throttler']:
    _saved_middle_deps[_dep] = sys.modules.get(_dep)
    _m = MagicMock()
    _m.__name__ = _dep
    _m.__file__ = f'<mock:{_dep}>'
    sys.modules[_dep] = _m

# middle_panel 依赖链会导入 gui.widgets.chart_widget（取类符号）与 chart_mixins 包
sys.modules['gui.widgets.chart_widget'] = MagicMock()
_chart_mixins_pkg = MagicMock()
_chart_mixins_pkg.__name__ = 'gui.widgets.chart_mixins'
_chart_mixins_pkg.__file__ = '<mock:gui.widgets.chart_mixins>'
sys.modules['gui.widgets.chart_mixins'] = _chart_mixins_pkg

_middle_panel = _load_module_from_file(
    'core.ui.panels.middle_panel',
    os.path.join(PROJECT_ROOT, 'core', 'ui', 'panels', 'middle_panel.py'))


# ==================== 公共数据构造 ====================

def _make_intraday_frame(n=4, price=10.0, vol=1000):
    """R295 契约：index=DatetimeIndex，列 [price, vol, amount]（amount=price*vol）"""
    idx = pd.to_datetime([
        '2026-08-15 09:31:00', '2026-08-15 09:32:00',
        '2026-08-15 09:33:00', '2026-08-15 09:34:00'])[:n]
    prices = [price + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        'price': prices,
        'vol': [vol] * n,
        'amount': [p * vol for p in prices],
    }, index=idx)


def _make_kline():
    """类1min K线 DataFrame（含 datetime 列）"""
    return pd.DataFrame({
        'datetime': pd.to_datetime(['2026-08-15 09:30:00', '2026-08-15 09:31:00']),
        'open': [10.0, 10.1], 'high': [10.2, 10.3],
        'low': [9.8, 9.9], 'close': [10.1, 10.2],
        'volume': [100, 200],
    })


# ==================== B1: ChartCanvas chart_type 透传 ====================

@pytest.mark.unit
class TestChartCanvasChartTypePassthrough:
    """B1: ChartCanvas.update_chart 透传 chart_type（覆盖缺陷修复）"""

    def _make_canvas(self):
        c = _middle_panel.ChartCanvas.__new__(_middle_panel.ChartCanvas)
        c.chart_widget = MagicMock()
        c.progressive_loader = None
        c.update_throttler = None
        c.performance_monitor = None
        return c

    def test_intraday_type_passed_through(self):
        """update_chart({'chart_type': '分时图'}) → chart_widget 收到 '分时图'（不再被覆盖为 'K线图'）"""
        c = self._make_canvas()
        c.update_chart({'kline_data': _make_kline(),
                        'stock_code': '600519',
                        'stock_name': '贵州茅台',
                        'chart_type': '分时图'})
        assert c.chart_widget.update_chart.called
        chart_data = c.chart_widget.update_chart.call_args[0][0]
        assert chart_data['chart_type'] == '分时图'

    def test_us_line_type_passed_through(self):
        """'美国线' 同样透传（不局限分时图）"""
        c = self._make_canvas()
        c.update_chart({'kline_data': _make_kline(), 'stock_code': '600519',
                        'chart_type': '美国线'})
        chart_data = c.chart_widget.update_chart.call_args[0][0]
        assert chart_data['chart_type'] == '美国线'

    def test_default_kline_when_missing(self):
        """缺省 chart_type → 'K线图'（回归）"""
        c = self._make_canvas()
        c.update_chart({'kline_data': _make_kline(), 'stock_code': '600519'})
        chart_data = c.chart_widget.update_chart.call_args[0][0]
        assert chart_data['chart_type'] == 'K线图'

    def test_current_chart_type_maintained(self):
        """update_chart 维护 self._current_chart_type 供分时轮询复用"""
        c = self._make_canvas()
        c.update_chart({'kline_data': _make_kline(), 'stock_code': '600519',
                        'chart_type': '分时图'})
        assert c._current_chart_type == '分时图'


# ==================== B2: 分时数据 → 类1min K线 ====================

@pytest.mark.unit
class TestConvertIntradayToKline:
    """B2: _convert_intraday_to_kline 格式转换（零渲染层改动复用分时渲染分支）"""

    def _call(self, df):
        return _middle_panel.MiddlePanel._convert_intraday_to_kline(df)

    def test_index_datetime_contract(self):
        """契约（index=DatetimeIndex, [price,vol,amount]）：
        open==high==low==close==price、volume==vol、datetime 正确"""
        df = _make_intraday_frame()
        out = self._call(df)
        assert out is not None
        assert list(out.columns) == ['datetime', 'open', 'high', 'low', 'close', 'volume']
        np.testing.assert_allclose(out['open'].to_numpy(), df['price'].to_numpy(), rtol=1e-12)
        np.testing.assert_allclose(out['high'].to_numpy(), df['price'].to_numpy(), rtol=1e-12)
        np.testing.assert_allclose(out['low'].to_numpy(), df['price'].to_numpy(), rtol=1e-12)
        np.testing.assert_allclose(out['close'].to_numpy(), df['price'].to_numpy(), rtol=1e-12)
        np.testing.assert_allclose(out['volume'].to_numpy(), df['vol'].to_numpy(), rtol=1e-12)
        assert list(pd.to_datetime(out['datetime'])) == list(df.index)

    def test_datetime_column_variant(self):
        """兼容含 datetime 列的变体（reset_index 场景）"""
        df = _make_intraday_frame().reset_index(names='datetime')
        out = self._call(df)
        assert out is not None
        assert len(out) == len(df)
        assert list(pd.to_datetime(out['datetime'])) == list(pd.to_datetime(df['datetime']))

    def test_volume_column_alias(self):
        """vol 缺失时回退 volume 列别名"""
        df = _make_intraday_frame().rename(columns={'vol': 'volume'})
        out = self._call(df)
        assert out is not None
        np.testing.assert_allclose(out['volume'].to_numpy(), df['volume'].to_numpy(), rtol=1e-12)

    def test_empty_returns_none(self):
        """空 DataFrame / None → None"""
        assert self._call(pd.DataFrame()) is None
        assert self._call(None) is None

    def test_no_datetime_returns_none(self):
        """无 datetime 列且 index 非 datetime → None（无法定位时刻）"""
        df = pd.DataFrame({'price': [1.0, 2.0], 'vol': [100, 200]})
        assert self._call(df) is None

    # ---- R295-VWAP V-02: 昨收精确化 (attrs → prev_close 列) ----

    def test_prev_close_passthrough_from_attrs(self):
        """attrs['prev_close']=9.18 → 输出含 prev_close 列且每行同值 (V-02 昨收精确化)"""
        df = _make_intraday_frame()
        df.attrs['prev_close'] = 9.18
        out = self._call(df)
        assert out is not None
        assert 'prev_close' in out.columns
        assert list(out['prev_close']) == [9.18] * len(out)

    def test_no_prev_close_attr_no_column(self):
        """无 attrs prev_close → 输出不含 prev_close 列（渲染侧回退原逻辑, 回归）"""
        out = self._call(_make_intraday_frame())
        assert out is not None
        assert 'prev_close' not in out.columns
        assert list(out.columns) == ['datetime', 'open', 'high', 'low', 'close', 'volume']


# ==================== B2: 分时实时轮询 ====================

@pytest.mark.unit
class TestIntradayRealtimeRefresh:
    """B2: _refresh_intraday_realtime 轮询动作（mock 数据获取/定时器）"""

    def _make_panel(self, chart_type='分时图'):
        p = _middle_panel.MiddlePanel.__new__(_middle_panel.MiddlePanel)
        p._current_chart_type = chart_type
        p._current_stock_code = '600519'
        p._current_stock_name = '贵州茅台'
        p._last_intraday_fallback_ts = 0.0
        p.chart_canvas = MagicMock()
        p.chart_canvas.is_loading = False
        p._load_chart_data = MagicMock()
        p._intraday_timer = MagicMock()
        return p

    def test_skips_when_not_intraday_chart(self):
        """非分时图 → 不刷新"""
        p = self._make_panel(chart_type='K线图')
        p._refresh_intraday_realtime()
        p.chart_canvas.update_chart.assert_not_called()

    def test_skips_when_no_stock(self):
        """无股票代码 → 不刷新"""
        p = self._make_panel()
        p._current_stock_code = ''
        p._refresh_intraday_realtime()
        p.chart_canvas.update_chart.assert_not_called()

    def test_skips_when_loading(self):
        """防抖：数据加载中（chart_canvas.is_loading）→ 轮询不覆盖新数据"""
        p = self._make_panel()
        p.chart_canvas.is_loading = True
        p._refresh_intraday_realtime()
        p.chart_canvas.update_chart.assert_not_called()

    def test_refresh_with_realtime_data(self):
        """实时分时接口返回数据 → update_chart 收到 chart_type='分时图' + 类K线数据"""
        p = self._make_panel()
        dm = MagicMock()
        dm.get_intraday_data.return_value = _make_intraday_frame()
        with patch('core.services.unified_data_manager.get_unified_data_manager', return_value=dm):
            p._refresh_intraday_realtime()
        p.chart_canvas.update_chart.assert_called_once()
        chart_data = p.chart_canvas.update_chart.call_args[0][0]
        assert chart_data['chart_type'] == '分时图'
        assert chart_data['period'] == '分时'
        assert chart_data['stock_code'] == '600519'
        assert chart_data['title'] == '贵州茅台'
        kdf = chart_data['kline_data']
        assert list(kdf.columns) == ['datetime', 'open', 'high', 'low', 'close', 'volume']
        assert kdf['close'].iloc[-1] == 10.3  # 4 根 price=10.0..10.3
        assert kdf['volume'].iloc[0] == 1000

    def test_empty_data_keeps_last_render(self):
        """接口返回空 → 保持上次渲染（update_chart 不被调用）"""
        p = self._make_panel()
        dm = MagicMock()
        dm.get_intraday_data.return_value = pd.DataFrame()
        with patch('core.services.unified_data_manager.get_unified_data_manager', return_value=dm):
            p._refresh_intraday_realtime()
        p.chart_canvas.update_chart.assert_not_called()

    def test_api_exception_silently_skipped(self):
        """接口抛异常 → 静默跳过（不刷新、不抛错冒泡）"""
        p = self._make_panel()
        dm = MagicMock()
        dm.get_intraday_data.side_effect = RuntimeError('network down')
        with patch('core.services.unified_data_manager.get_unified_data_manager', return_value=dm):
            p._refresh_intraday_realtime()  # 不抛
        p.chart_canvas.update_chart.assert_not_called()

    def test_api_missing_falls_back_to_load(self):
        """实时接口未就绪（无 get_intraday_data 属性）→ 回退 _load_chart_data（1min 聚合）"""
        p = self._make_panel()

        class _StubDM:
            pass

        with patch('core.services.unified_data_manager.get_unified_data_manager',
                   return_value=_StubDM()):
            p._refresh_intraday_realtime()
        p._load_chart_data.assert_called_once()
        p.chart_canvas.update_chart.assert_not_called()

    def test_fallback_throttled(self):
        """回退节流：30s 内再次轮询不重复触发 _load_chart_data"""
        p = self._make_panel()
        p._last_intraday_fallback_ts = 9999999999.0  # 模拟刚回退过

        class _StubDM:
            pass

        with patch('core.services.unified_data_manager.get_unified_data_manager',
                   return_value=_StubDM()):
            p._refresh_intraday_realtime()
        p._load_chart_data.assert_not_called()


# ==================== B2: 定时器启停 ====================

@pytest.mark.unit
class TestSyncIntradayTimer:
    """B2: _sync_intraday_timer 定时器启停"""

    def _make_panel(self, chart_type='K线图', timer=None):
        p = _middle_panel.MiddlePanel.__new__(_middle_panel.MiddlePanel)
        p._current_chart_type = chart_type
        p._intraday_timer = timer if timer is not None else MagicMock()
        return p

    def test_start_when_intraday(self):
        """分时图 → timer.start()"""
        timer = MagicMock()
        timer.isActive.return_value = False
        p = self._make_panel(chart_type='分时图', timer=timer)
        p._sync_intraday_timer()
        timer.start.assert_called_once()

    def test_no_restart_when_already_active(self):
        """分时图且定时器已激活 → 不重复 start"""
        timer = MagicMock()
        timer.isActive.return_value = True
        p = self._make_panel(chart_type='分时图', timer=timer)
        p._sync_intraday_timer()
        timer.start.assert_not_called()

    def test_stop_when_not_intraday(self):
        """切到其他图表类型 → timer.stop()"""
        timer = MagicMock()
        p = self._make_panel(chart_type='K线图', timer=timer)
        p._sync_intraday_timer()
        timer.stop.assert_called_once()


@pytest.mark.unit
class TestOnChartTypeChangedTimer:
    """B2 集成：_on_chart_type_changed 联动定时器（切分时启动 / 切其他停止）"""

    def _make_panel(self):
        p = _middle_panel.MiddlePanel.__new__(_middle_panel.MiddlePanel)
        p._current_chart_type = 'K线图'
        p._current_period = '日线'
        p._load_chart_data = MagicMock()
        combo = MagicMock()
        combo.findText.return_value = 0
        p.get_widget = MagicMock(return_value=combo)
        timer = MagicMock()
        timer.isActive.return_value = False
        p._intraday_timer = timer
        return p, timer

    def test_switch_to_intraday_starts_timer(self):
        """切'分时图' → timer.start() + 周期联动 '分时' + 重新加载"""
        p, timer = self._make_panel()
        p._on_chart_type_changed('分时图')
        timer.start.assert_called_once()
        assert p._current_period == '分时'
        p._load_chart_data.assert_called_once()

    def test_switch_away_stops_timer(self):
        """切回'K线图' → timer.stop()（轮询不再运行）"""
        p, timer = self._make_panel()
        p._on_chart_type_changed('K线图')
        timer.stop.assert_called_once()
        assert p._current_chart_type == 'K线图'


# 恢复 conftest 的 mock，避免影响其他测试
for _sub in ['gui.widgets.chart_widget', 'gui.widgets.chart_mixins',
             'core.services.unified_data_manager',
             'core.services.unified_chart_service']:
    if _sub in sys.modules:
        del sys.modules[_sub]

if _saved_middle_deps:
    for _dep, _old in _saved_middle_deps.items():
        if _old is None:
            sys.modules.pop(_dep, None)
        else:
            sys.modules[_dep] = _old
    _saved_middle_deps = {}

if _saved_gui_widgets is not None:
    sys.modules['gui.widgets'] = _saved_gui_widgets
if _saved_core_ui is not None:
    sys.modules['core.ui'] = _saved_core_ui
if _saved_core_ui_panels is not None:
    sys.modules['core.ui.panels'] = _saved_core_ui_panels
if _saved_base_panel is not None:
    sys.modules['core.ui.panels.base_panel'] = _saved_base_panel
if _saved_core_services is not None:
    sys.modules['core.services'] = _saved_core_services
else:
    sys.modules.pop('core.services', None)
