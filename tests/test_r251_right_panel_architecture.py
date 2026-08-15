#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R251 回归测试: 右侧面板 (RightPanel) 架构修复 R4-R9

覆盖问题:
- R4: 双 UIDataReadyEvent 竞态 (无 ui_data 的旧路径不再抛 AttributeError)
- R5: _professional_tabs 索引 vs QTabWidget 索引错位 (indexOf 映射)
- R6: 买卖信号读取键不存在 (technical_analysis['signals'] 映射)
- R7: 面板无退订 (_do_dispose 取消 EventBus 订阅)
- R8: 导出报告占位空壳 (真实 Markdown 导出)
- R9: 波浪预测硬编码 (基于真实 K 线数据生成)
"""
import os
import sys
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# conftest.py 会把 gui / gui.widgets / core.ui.panels.* 等模块预注册为 MagicMock,
# 导致真实导入失败 ("'gui.widgets' is not a package")。
# 同时, 真实导入 core.ui.panels.base_panel 会因 PyQt5 sip wrappertype 与 ABC
# 组合元类 (QObjectMeta) 在无头环境 0xC0000005 崩溃 (这正是 conftest 将其 mock
# 的原因), 且 right_panel 的依赖链 (analysis.pattern_recognition / ta-lib) 也会崩溃。
# 因此本测试采用:
#   1) 移除 conftest 冲突 mock 条目;
#   2) 预注册轻量 analysis_tabs 包 (跳过其 __init__.py 重型链);
#   3) mock 掉 right_panel / base_tab 的所有外部服务依赖;
#   4) right_panel 用 importlib 从文件加载 + 极简假 BasePanel;
#   5) wave_tab_pro 走标准导入 (base_tab 链已隔离为安全).
# ---------------------------------------------------------------------------
_CONFTEST_MOCKS = [
    'gui', 'gui.dialogs', 'gui.dialogs.strategy_manager_dialog',
    'gui.widgets', 'gui.widgets.backtest_widget', 'gui.widgets.trading_panel',
    'gui.widgets.enhanced_ui', 'gui.widgets.enhanced_ui.order_book_widget',
    'gui.widgets.enhanced_ui.level2_data_panel', 'gui.widgets.performance',
    'gui.widgets.performance.tabs', 'gui.utils', 'gui.utils.responsive_helper',
    'core.ui', 'core.ui.panels', 'core.ui.panels.base_panel',
    'core.ui.panels.left_panel', 'core.ui.panels.middle_panel',
    'core.ui.panels.right_panel', 'core.ui.panels.bottom_panel',
    'core.ui.widgets', 'core.coordinators.main_window_coordinator',
]
for _mod in _CONFTEST_MOCKS:
    sys.modules.pop(_mod, None)

from unittest.mock import MagicMock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_mock_module(name: str) -> MagicMock:
    _m = MagicMock()
    _m.__name__ = name
    _m.__file__ = f'<mock:{name}>'
    sys.modules[name] = _m
    return _m


# gui.widgets 真实导入 (其 __init__.py 仅注释, 安全)
import gui.widgets  # noqa: E402

# 预注册轻量 analysis_tabs 包 (跳过 __init__.py 的重型导入链:
# __init__ 会触发 pattern_tab→pattern_tab_pro→analysis.pattern_recognition, 无头环境崩溃)
_analysis_tabs_mod = types.ModuleType('gui.widgets.analysis_tabs')
_analysis_tabs_mod.__path__ = [
    os.path.join(os.path.dirname(gui.widgets.__file__), 'analysis_tabs')]
sys.modules['gui.widgets.analysis_tabs'] = _analysis_tabs_mod

# mock 掉 analysis_tabs 中 right_panel 需要但导入链崩溃/过重的兄弟模块
for _sub in ('pattern_tab', 'pattern_tab_pro', 'technical_tab', 'trend_tab',
             'wave_tab', 'sector_flow_tab', 'sector_flow_tab_pro', 'hotspot_tab'):
    _make_mock_module(f'gui.widgets.analysis_tabs.{_sub}')

# gui.ui_components 未被 conftest mock, right_panel 导入它可能触发重型依赖 → mock 掉
if 'gui.ui_components' not in sys.modules:
    _make_mock_module('gui.ui_components')

# right_panel / base_tab 的外部服务依赖 → mock 掉 (避免 analysis.pattern_base / ta-lib /
# unified_sqlite_access 等重型导入链)
for _dep in ('core.performance', 'core.services.analysis_service',
             'core.services.backtest_result_manager',
             'utils.config_manager', 'utils.trace_context'):
    _make_mock_module(_dep)


def _load_module_from_file(module_name: str, rel_path: str):
    """从文件加载模块 (绕过 sys.modules 中已注册的 mock)"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 假 BasePanel: 避免 PyQt5 sip wrappertype+ABC 组合元类在无头环境崩溃
class _FakeBasePanel:
    """极简 BasePanel 替身, 仅提供 RightPanel 生命周期所需空实现"""

    def _do_dispose(self) -> None:
        pass

    def dispose(self) -> None:
        if not getattr(self, '_disposed', False):
            self._do_dispose()
            self._disposed = True


_panels_pkg = types.ModuleType('core.ui.panels')
_panels_pkg.__path__ = [os.path.join(ROOT, 'core', 'ui', 'panels')]
sys.modules['core.ui.panels'] = _panels_pkg

_base_panel_mod = types.ModuleType('core.ui.panels.base_panel')
_base_panel_mod.BasePanel = _FakeBasePanel
sys.modules['core.ui.panels.base_panel'] = _base_panel_mod

# 从文件加载 right_panel 模块 (模块内 from .base_panel import BasePanel → 假基类)
_rp_module = _load_module_from_file(
    'core.ui.panels.right_panel', 'core/ui/panels/right_panel.py')
RightPanel = _rp_module.RightPanel

# wave_tab_pro: 标准导入 (analysis_tabs 轻量包已注册; base_tab 链已隔离为安全)
from gui.widgets.analysis_tabs.wave_tab_pro import WaveAnalysisTabPro  # noqa: E402

import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pandas as pd  # noqa: E402

from core.events import AnalysisCompleteEvent, UIDataReadyEvent  # noqa: E402


def _make_kdata_df(n: int = 60) -> pd.DataFrame:
    """构造K线DataFrame (含 date/open/high/low/close/volume 列, DatetimeIndex)"""
    dates = pd.date_range('2024-01-01', periods=n, freq='D')
    df = pd.DataFrame({
        'date': dates,
        'open': [10.0 + i * 0.01 for i in range(n)],
        'high': [10.5 + i * 0.01 for i in range(n)],
        'low': [9.5 + i * 0.01 for i in range(n)],
        'close': [10.0 + i * 0.01 for i in range(n)],
        'volume': [1000000 + i * 1000 for i in range(n)],
        'amount': [10000000 + i * 10000 for i in range(n)],
    })
    df.index = dates
    return df


def _build_right_panel(**kwargs) -> RightPanel:
    """构造轻量 RightPanel 实例 (跳过 __init__ 避免重型 UI 依赖)"""
    panel = object.__new__(RightPanel)
    panel._current_stock_code = ''
    panel._current_stock_name = ''
    panel._performance_manager = None
    panel._has_basic_tabs = False
    panel._pending_tab_updates = {}
    panel._tab_stock_code = {}
    panel._backtest_result_manager = None
    panel._update_status = MagicMock()
    panel._clear_backtest_results = MagicMock()
    panel._update_analysis_display = MagicMock()
    panel._async_update_professional_tabs = MagicMock()
    panel._update_professional_tabs_with_performance_manager = MagicMock()
    for key, value in kwargs.items():
        setattr(panel, key, value)
    return panel


class TestR4UiDataReadyEventRace(unittest.TestCase):
    """R4: 双 UIDataReadyEvent 竞态 - 事件契约不一致"""

    def test_no_ui_data_event_does_not_raise_attribute_error(self):
        """旧路径 (AssetSelectedEvent 派生的 UIDataReadyEvent, 仅 kline_data 无 ui_data)
        调用 _on_ui_data_ready 不得抛 AttributeError, 且面板正常更新"""
        kline_df = _make_kdata_df()
        event = UIDataReadyEvent(
            stock_code='000001',
            stock_name='平安银行',
            kline_data=kline_df,
            market='SZ'
        )
        # ui_data 默认 {} → 模拟旧路径事件
        self.assertEqual(event.ui_data, {})

        stock_label = MagicMock()
        panel = _build_right_panel(
            _performance_manager=MagicMock(),
            get_widget=lambda name: stock_label if name == 'stock_label' else None,
        )

        # 不应抛出 AttributeError (修复前: event.ui_data.get 抛错被吞, 面板不更新)
        panel._on_ui_data_ready(event)

        stock_label.setText.assert_called_once()
        # kline_data 通过 getattr(event, 'kline_data') 兜底读到, 走性能管理器分支
        panel._update_professional_tabs_with_performance_manager.assert_called_once_with(kline_df)
        panel._update_status.assert_called_once()
        self.assertEqual(panel._current_stock_code, '000001')

    def test_full_ui_data_event_still_works(self):
        """新路径 (_on_stock_selected 派生的 UIDataReadyEvent, 带完整 ui_data) 行为不变"""
        kline_df = _make_kdata_df()
        event = UIDataReadyEvent(
            stock_code='000001',
            stock_name='平安银行',
            ui_data={
                'kline_data': kline_df,
                'analysis': {'technical_analysis': {'trend': 'up'}},
                'kdata': kline_df,
            }
        )

        stock_label = MagicMock()
        panel = _build_right_panel(
            _performance_manager=MagicMock(),
            _has_basic_tabs=True,
            get_widget=lambda name: stock_label if name == 'stock_label' else None,
        )

        panel._on_ui_data_ready(event)

        panel._update_professional_tabs_with_performance_manager.assert_called_once_with(kline_df)
        # analysis 从 ui_data 读出并传递给基础标签页
        panel._update_analysis_display.assert_called_once_with(
            {'technical_analysis': {'trend': 'up'}})


class TestR5TabIndexMapping(unittest.TestCase):
    """R5: _professional_tabs 列表索引 vs QTabWidget 索引错位"""

    def _make_tab_widget(self, current_index: int, index_of_map: dict):
        tab_widget = MagicMock()
        tab_widget.currentIndex.return_value = current_index
        tab_widget.indexOf.side_effect = lambda tab: index_of_map[tab]
        tab_widget.widget.side_effect = lambda idx: {v: k for k, v in index_of_map.items()}.get(idx)
        return tab_widget

    def test_batch_analysis_active_no_professional_tab_updated(self):
        """currentIndex=6 (批量分析): 无专业 tab 被误判为激活, 全部进待更新队列,
        key 使用 QTabWidget 索引 (0-5)"""
        tabs = [MagicMock() for _ in range(6)]
        for t in tabs:
            t.skip_kdata = False
        index_of_map = {t: i for i, t in enumerate(tabs)}
        tab_widget = self._make_tab_widget(current_index=6, index_of_map=index_of_map)

        panel = _build_right_panel(
            _performance_manager=MagicMock(),
            _current_stock_code='000001',
            _professional_tabs=tabs,
            get_widget=lambda name: tab_widget if name == 'tab_widget' else None,
        )
        # 绑定真实方法 (默认被 _build_right_panel 预设为 MagicMock)
        panel._update_professional_tabs_with_performance_manager = (
            RightPanel._update_professional_tabs_with_performance_manager.__get__(panel, RightPanel))

        panel._update_professional_tabs_with_performance_manager(_make_kdata_df())

        # 没有 tab 被立即更新 (update_tab_data 从未被调用)
        panel._performance_manager.update_tab_data.assert_not_called()
        # 全部 6 个专业 tab 进待更新队列, key 为 QTabWidget 索引 0-5
        self.assertEqual(set(panel._pending_tab_updates.keys()), {0, 1, 2, 3, 4, 5})
        # 没有误写 6 (批量分析索引) 到已更新表
        self.assertNotIn(6, panel._tab_stock_code)

    def test_off_by_one_index_mapping_uses_indexof(self):
        """错位场景: 某专业 tab 的真实索引 ≠ enumerate 位置时, 用 indexOf 决定更新/待更新"""
        t1, t2, t3 = MagicMock(), MagicMock(), MagicMock()
        for t in (t1, t2, t3):
            t.skip_kdata = False
        # 模拟真实索引与 _professional_tabs 位置错位: t1 在 QTabWidget 索引 2
        index_of_map = {t1: 2, t2: 0, t3: 1}
        tab_widget = self._make_tab_widget(current_index=2, index_of_map=index_of_map)

        panel = _build_right_panel(
            _performance_manager=MagicMock(),
            _current_stock_code='000001',
            _professional_tabs=[t1, t2, t3],
            get_widget=lambda name: tab_widget if name == 'tab_widget' else None,
        )
        # 绑定真实方法 (默认被 _build_right_panel 预设为 MagicMock)
        panel._update_professional_tabs_with_performance_manager = (
            RightPanel._update_professional_tabs_with_performance_manager.__get__(panel, RightPanel))

        panel._update_professional_tabs_with_performance_manager(_make_kdata_df())

        # 只有真实索引==current_index(2) 的 t1 被立即更新
        panel._performance_manager.update_tab_data.assert_called_once()
        call_kwargs = panel._performance_manager.update_tab_data.call_args[1]
        self.assertIs(call_kwargs['tab_widget'], t1)
        # 已更新记录 key 为真实索引 2
        self.assertEqual(panel._tab_stock_code, {2: '000001'})
        # 其余 tab 进待更新, key 为真实索引 0/1 (而非 enumerate 位置 1/2)
        self.assertEqual(set(panel._pending_tab_updates.keys()), {0, 1})

    def test_on_tab_changed_uses_qtabwidget_index(self):
        """_on_tab_changed(index) 按 QTabWidget 索引从待更新队列取数据, 用 widget(index) 取 tab"""
        t1, t2 = MagicMock(), MagicMock()
        for t in (t1, t2):
            t.skip_kdata = False
        index_of_map = {t1: 0, t2: 1}
        tab_widget = self._make_tab_widget(current_index=0, index_of_map=index_of_map)

        panel = _build_right_panel(
            _performance_manager=MagicMock(),
            _current_stock_code='000001',
            _professional_tabs=[t1, t2],
            get_widget=lambda name: tab_widget if name == 'tab_widget' else None,
        )
        kline_df = _make_kdata_df()
        panel._pending_tab_updates = {0: kline_df}

        # 切换到索引 6 (批量分析) 不应崩溃也不应误消费 pending
        panel._on_tab_changed(6)
        self.assertEqual(panel._pending_tab_updates, {0: kline_df})

        # 切换到索引 0 (技术分析) → 从 pending 弹出并更新
        panel._on_tab_changed(0)
        self.assertNotIn(0, panel._pending_tab_updates)
        tab_widget.widget.assert_called_with(0)
        panel._performance_manager.update_tab_data.assert_called_once()
        self.assertEqual(panel._tab_stock_code.get(0), '000001')


class TestR6SignalKeyMapping(unittest.TestCase):
    """R6: 买卖信号读取的键不存在 (analysis_service 真实结构无顶层 'signals')"""

    def test_convert_technical_signals(self):
        """technical_analysis['signals'] → _update_signal_analysis_safe 期望的展示结构"""
        panel = _build_right_panel()
        tech_signals = [
            {'name': 'MA20', 'signal': 'bullish', 'desc': '收盘价高于 MA20(10.00)'},
            {'name': 'RSI', 'signal': 'oversold', 'desc': 'RSI(14)=28.0 超卖'},
            {'name': 'MACD', 'signal': 'bearish', 'desc': 'MACD柱=-0.0012'},
        ]
        converted = panel._convert_technical_signals(tech_signals)

        self.assertEqual(converted['current']['type'], 'buy')
        self.assertEqual(converted['current']['strength'], 2)  # bullish + oversold(超卖→买入)
        self.assertEqual(len(converted['history']), 3)
        self.assertEqual(converted['statistics']['total_signals'], 3)
        self.assertEqual(converted['statistics']['buy_signals'], 2)
        self.assertEqual(converted['statistics']['sell_signals'], 1)
        # history 元素包含 _update_signal_analysis_safe 所需键
        for item in converted['history']:
            for key in ('time', 'type', 'price', 'strength', 'return'):
                self.assertIn(key, item)

    def test_update_analysis_display_with_real_structure(self):
        """analyze_stock 真实返回结构 (无顶层 signals) 也能更新信号显示"""
        panel = _build_right_panel()
        # 绑定真实方法, 但 mock 掉展示入口与回测管理器, 验证信号映射逻辑
        panel._update_analysis_display = RightPanel._update_analysis_display.__get__(panel, RightPanel)
        panel._update_signal_analysis_safe = MagicMock()
        panel._backtest_result_manager = MagicMock()
        panel._backtest_result_manager.get_latest_result.return_value = None

        analysis_data = {
            'indicators': {'ma5': [], 'rsi': []},
            'technical_analysis': {
                'trend': 'up',
                'signals': [{'name': 'MA20', 'signal': 'bullish', 'desc': '收盘价高于 MA20'}],
            },
            'data_available': True,
        }
        panel._update_analysis_display(analysis_data)

        # 信号被提取并转换后传给展示方法
        panel._update_signal_analysis_safe.assert_called_once()
        converted = panel._update_signal_analysis_safe.call_args[0][0]
        self.assertEqual(converted['current']['type'], 'buy')
        self.assertEqual(len(converted['history']), 1)
        self.assertEqual(converted['history'][0]['name'], 'MA20')

    def test_update_analysis_display_top_level_signals_priority(self):
        """顶层 'signals' 键存在时优先使用 (兼容历史聚合格式)"""
        panel = _build_right_panel()
        panel._update_analysis_display = RightPanel._update_analysis_display.__get__(panel, RightPanel)
        panel._update_signal_analysis_safe = MagicMock()
        panel._backtest_result_manager = MagicMock()
        panel._backtest_result_manager.get_latest_result.return_value = None

        analysis_data = {
            'signals': {'current': {'type': 'sell', 'strength': 2}, 'history': []},
            'technical_analysis': {
                'signals': [{'name': 'MA20', 'signal': 'bullish', 'desc': 'x'}],
            },
        }
        panel._update_analysis_display(analysis_data)

        panel._update_signal_analysis_safe.assert_called_once()
        passed = panel._update_signal_analysis_safe.call_args[0][0]
        self.assertEqual(passed['current']['type'], 'sell')  # 未被 technical_analysis 覆盖


class TestR7DisposeUnsubscribe(unittest.TestCase):
    """R7: 面板无退订 - _do_dispose 取消 EventBus 订阅"""

    def test_do_dispose_unsubscribes_events(self):
        """调用 _do_dispose 后, event_bus.unsubscribe 对两个事件都被调用"""
        event_bus = MagicMock()
        panel = _build_right_panel(event_bus=event_bus)
        panel._on_ui_data_ready = MagicMock()
        panel._on_analysis_complete = MagicMock()

        panel._do_dispose()

        self.assertEqual(event_bus.unsubscribe.call_count, 2)
        unsubscribe_args = [call.args[0] for call in event_bus.unsubscribe.call_args_list]
        self.assertIn(UIDataReadyEvent, unsubscribe_args)
        self.assertIn(AnalysisCompleteEvent, unsubscribe_args)
        # 退订的 handler 与订阅时一致
        for call in event_bus.unsubscribe.call_args_list:
            self.assertIn(call.args[1], (panel._on_ui_data_ready, panel._on_analysis_complete))


class TestR8ExportReport(unittest.TestCase):
    """R8: 导出报告占位空壳 - 真实 Markdown 导出"""

    @patch('PyQt5.QtWidgets.QFileDialog.getSaveFileName')
    def test_export_report_writes_file(self, mock_get_save):
        tmp_dir = tempfile.mkdtemp(prefix='r251_report_')
        target = os.path.join(tmp_dir, 'report.md')
        mock_get_save.return_value = (target, 'Markdown 文件 (*.md)')

        status_label = MagicMock()
        status_label.text.return_value = 'BUY\n强度: 1'
        signal_table = MagicMock()
        signal_table.rowCount.return_value = 1
        signal_table.columnCount.return_value = 5
        cell_item = MagicMock()
        cell_item.text.return_value = '2024-01-01'
        signal_table.item.return_value = cell_item

        latest_result = MagicMock()
        latest_result.backtest_results = {'总收益率': 0.12, '年化收益率': 0.35}
        latest_result.trades = [
            {'date': '2024-01-01', 'action': '买入', 'price': 10.0,
             'quantity': 100, 'profit': 50.0}
        ]
        backtest_mgr = MagicMock()
        backtest_mgr.get_latest_result.return_value = latest_result

        panel = _build_right_panel(
            _current_stock_code='000001',
            _current_stock_name='平安银行',
            _backtest_result_manager=backtest_mgr,
            get_widget=lambda name: {
                'signal_status_label': status_label,
                'signal_table': signal_table,
            }.get(name),
        )

        panel._export_report()

        self.assertTrue(os.path.exists(target))
        content = open(target, encoding='utf-8').read()
        self.assertIn('000001', content)
        self.assertIn('平安银行', content)
        self.assertIn('BUY', content)
        self.assertIn('2024-01-01', content)
        self.assertIn('总收益率', content)
        # 状态提示成功
        panel._update_status.assert_called()
        self.assertIn('已导出', panel._update_status.call_args[0][0])

    def test_export_report_without_stock(self):
        """未选择股票时提示, 不弹对话框"""
        panel = _build_right_panel(_current_stock_code='')
        with patch('PyQt5.QtWidgets.QFileDialog.getSaveFileName') as mock_get_save:
            panel._export_report()
            mock_get_save.assert_not_called()
        panel._update_status.assert_called_once_with('请先选择股票再导出报告')

    def test_export_report_cancel(self):
        """用户取消保存对话框时不写文件"""
        status_label = MagicMock()
        status_label.text.return_value = '暂无信号'
        signal_table = MagicMock()
        signal_table.rowCount.return_value = 0
        panel = _build_right_panel(
            _current_stock_code='000001',
            _current_stock_name='平安银行',
            get_widget=lambda name: {
                'signal_status_label': status_label,
                'signal_table': signal_table,
            }.get(name),
        )
        with patch('PyQt5.QtWidgets.QFileDialog.getSaveFileName', return_value=('', '')):
            panel._export_report()
        panel._update_status.assert_called_once_with('已取消导出')


class TestR9WavePredictionRealData(unittest.TestCase):
    """R9: 波浪预测硬编码 - 基于真实 K 线数据"""

    def _build_tab(self, df=None, fib=None, gann=None, elliott=None):
        """构造轻量波浪分析 Tab 替身

        PyQt5 sip 类型不能用 object.__new__ (TypeError: not safe),
        且真实实例化 QWidget 在无头环境风险高。
        改用普通对象 + 绑定 WaveAnalysisTabPro 真实方法, 零 UI 实例化。
        """
        tab = types.SimpleNamespace()
        tab.current_kdata = df
        tab.fibonacci_levels = fib if fib is not None else []
        tab.gann_levels = gann if gann is not None else []
        tab.elliott_waves = elliott if elliott is not None else []
        tab.elliott_config = {
            'fibonacci_ratios': [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.618],
        }
        tab.gann_config = {'angles': {}, 'time_cycles': [], 'price_squares': []}
        # 绑定真实实现方法 (self 为假对象, 仅需其属性)
        tab._calculate_fibonacci_levels = WaveAnalysisTabPro._calculate_fibonacci_levels.__get__(tab, object)
        tab._calculate_gann_levels = WaveAnalysisTabPro._calculate_gann_levels.__get__(tab, object)
        tab._generate_wave_prediction = WaveAnalysisTabPro._generate_wave_prediction.__get__(tab, object)
        return tab

    def test_prediction_contains_real_close_price(self):
        """输出包含真实最新收盘价数值而非纯模板"""
        df = _make_kdata_df(60)
        last_close = float(df['close'].iloc[-1])  # 10.59
        tab = self._build_tab(
            df=df,
            fib=[
                {'ratio': '0.382', 'price': 9.8, 'type': '回调位', 'strength': '强', 'validity': '有效'},
                {'ratio': '1.618', 'price': 11.2, 'type': '扩展位', 'strength': '强', 'validity': '有效'},
            ],
            gann=[
                {'type': '江恩1x1', 'angle': 45, 'price': 9.5, 'time': '2024-01-01',
                 'strength': 'very_strong', 'status': '有效'},
            ],
            elliott=[
                {'wave': '第3浪', 'type': '推动浪', 'start': {}, 'end': {}, 'amplitude': 0.1,
                 'time': 5, 'confidence': 0.8, 'status': '确认'},
            ],
        )

        pred = tab._generate_wave_prediction()

        # 含真实收盘价数值
        self.assertIn(f'{last_close:.2f}', pred)
        self.assertIn('最新收盘价', pred)
        # 含真实斐波那契/江恩价位
        self.assertIn('9.80', pred)
        self.assertIn('11.20', pred)
        self.assertIn('9.50', pred)
        # 含波浪结构
        self.assertIn('第3浪', pred)
        # 不再包含原模板占位文案
        self.assertNotIn('预计价格将在关键斐波那契位附近震荡', pred)

    def test_prediction_computes_levels_when_empty(self):
        """无预置分析结果时, 基于 K 线现场计算斐波那契/江恩水平"""
        df = _make_kdata_df(60)
        last_close = float(df['close'].iloc[-1])
        tab = self._build_tab(df=df)
        tab.elliott_config = {
            'fibonacci_ratios': [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.618],
        }
        tab.gann_config = {'angles': {}, 'time_cycles': [], 'price_squares': []}

        pred = tab._generate_wave_prediction()

        self.assertIn(f'{last_close:.2f}', pred)
        # 现场计算至少产出关键价位行
        self.assertIn('斐波那契支撑位', pred)

    def test_prediction_no_data_returns_explanation(self):
        """K 线数据缺失时返回带说明的文本"""
        tab = self._build_tab(df=None)
        pred = tab._generate_wave_prediction()
        self.assertIn('数据不足', pred)
        self.assertIn('波浪预测', pred)


# ---------------------------------------------------------------------------
# R251 交叉审查回归修复: 恢复被本文件 mock 污染的 sys.modules 条目
# pytest 收集阶段会 import 全部测试文件; 若不恢复, 其他测试文件运行时
# 重新 import 这些模块会拿到 MagicMock (如 analysis_service → "a coroutine was
# expected" 假性失败), 造成假性回归。恢复方式: 删除注入条目, 触发真实模块
# 重新加载。注: core.ui.panels 包 / right_panel / wave_tab_pro 已真实加载成功,
# 保留在 sys.modules 中(删除会导致其他文件重新真实导入而崩溃)。
# ---------------------------------------------------------------------------
_POLLUTED_MODULES = [
    'gui.widgets.analysis_tabs',  # 顶层轻量假包 (R251 收集期注入, 遗留致 analysis_widget 真实导入失败)
    'gui.widgets.analysis_tabs.pattern_tab',
    'gui.widgets.analysis_tabs.pattern_tab_pro',
    'gui.widgets.analysis_tabs.technical_tab',
    'gui.widgets.analysis_tabs.trend_tab',
    'gui.widgets.analysis_tabs.wave_tab',
    'gui.widgets.analysis_tabs.sector_flow_tab',
    'gui.widgets.analysis_tabs.sector_flow_tab_pro',
    'gui.widgets.analysis_tabs.hotspot_tab',
    'gui.ui_components',
    'core.performance',
    'core.services.analysis_service',
    'core.services.backtest_result_manager',
    'utils.config_manager',
    'utils.trace_context',
]
for _mod_name in _POLLUTED_MODULES:
    sys.modules.pop(_mod_name, None)


if __name__ == '__main__':
    unittest.main()
