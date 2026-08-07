#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R252 回归测试: 批量分析 (EnhancedBatchAnalysisMixin) + 热点分析 (HotspotAnalysisTab)

覆盖 H1-H6:
- H1: 批量分析空结果 (None 指标) 消费层防御
      (_add_batch_result_to_table / _update_batch_results_statistics /
       _filter_profitable_batch_results / _sort_batch_results)
- H2: 批量回测日期范围配置生效 (mode_context 使用真实 start_date/end_date)
- H3: 股票全选/全不选遍历所有列 (10 列网格)
- H4: 热点资金流向表格数据填充后刷新 UI (_on_fund_flow_finished 末尾刷新)
- H5: 批量分析线程清理 getattr 兼容 (threading.Thread 无 quit/wait)
- H6: 移除热点假数据语义 (start_monitor 文案 / 三大空方法日志)

说明:
- conftest.py 会把 gui / gui.widgets 等预注册为 MagicMock, 且真实导入
  gui.enhanced_batch_analysis_methods / hotspot_tab 会触发重型依赖链,
  因此本测试采用与 test_r251_right_panel_architecture.py 一致的 mock 手法:
  sys.modules 注入 mock 依赖 + importlib 加载, 文件末尾恢复被 mock 的条目。
"""
import os
import sys
import types
import threading

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# conftest.py 会把 gui / gui.widgets 等预注册为 MagicMock; 先移除冲突条目
# ---------------------------------------------------------------------------
_CONFTEST_MOCKS = [
    'gui', 'gui.dialogs', 'gui.dialogs.strategy_manager_dialog',
    'gui.widgets', 'gui.widgets.backtest_widget', 'gui.widgets.trading_panel',
    'gui.widgets.enhanced_ui', 'gui.widgets.enhanced_ui.order_book_widget',
    'gui.widgets.enhanced_ui.level2_data_panel', 'gui.widgets.performance',
    'gui.widgets.performance.tabs', 'gui.utils', 'gui.utils.responsive_helper',
]
for _mod in _CONFTEST_MOCKS:
    sys.modules.pop(_mod, None)

from unittest.mock import MagicMock, patch  # noqa: E402
from PyQt5.QtCore import Qt  # noqa: E402

import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_mock_module(name: str) -> MagicMock:
    _m = MagicMock()
    _m.__name__ = name
    _m.__file__ = f'<mock:{name}>'
    sys.modules[name] = _m
    return _m


def _load_module_from_file(module_name: str, rel_path: str):
    """从文件加载模块 (绕过 sys.modules 中已注册的 mock)"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Part A: enhanced_batch_analysis_methods 依赖隔离
# ---------------------------------------------------------------------------
# backtest.unified_backtest_engine: 重型链 (numba/scipy/matplotlib/risk_manager), mock
_fake_backtest_mod = types.ModuleType('backtest.unified_backtest_engine')


class _FakeUnifiedBacktestEngine:
    """假回测引擎: 仅验证 mode_context 传参与 run_backtest 调用"""

    def __init__(self):
        self.mode_context = None

    def run_backtest(self, **kwargs):
        return {'metrics': {
            'total_return': 0.1234, 'sharpe_ratio': 1.5,
            'max_drawdown': -0.05, 'win_rate': 0.6, 'total_trades': 12,
        }}


_fake_backtest_mod.UnifiedBacktestEngine = _FakeUnifiedBacktestEngine
sys.modules['backtest.unified_backtest_engine'] = _fake_backtest_mod

# core.services.stock_service / strategy_service: mock (容器 resolve 用)
_svc_mod = types.ModuleType('core.services.stock_service')


class _StockService:
    pass


_svc_mod.StockService = _StockService
sys.modules['core.services.stock_service'] = _svc_mod

_stg_mod = types.ModuleType('core.services.strategy_service')


class _StrategyService:
    pass


_stg_mod.StrategyService = _StrategyService
sys.modules['core.services.strategy_service'] = _stg_mod

# core.containers: mock (get_service_container)
_containers_mod = types.ModuleType('core.containers')
sys.modules['core.containers'] = _containers_mod
print('[DEBUG-A] containers mocked:', sys.modules['core.containers'] is _containers_mod)

# core.trading.trading_mode: 真实导入安全 (纯 enum/dataclass)
from core.trading.trading_mode import ModeContext  # noqa: E402
print('[DEBUG-B] after trading_mode import:', sys.modules['core.containers'] is _containers_mod)

# 从文件加载 enhanced_batch_analysis_methods (模块内无相对导入)
_ebam = _load_module_from_file(
    'gui.enhanced_batch_analysis_methods',
    'gui/enhanced_batch_analysis_methods.py')
EnhancedBatchAnalysisMixin = _ebam.EnhancedBatchAnalysisMixin

# ---------------------------------------------------------------------------
# Part B: hotspot_tab 依赖隔离 (标准导入)
# ---------------------------------------------------------------------------
import gui.widgets  # noqa: E402  (其 __init__.py 仅注释, 安全)

_analysis_tabs_mod = types.ModuleType('gui.widgets.analysis_tabs')
_analysis_tabs_mod.__path__ = [
    os.path.join(os.path.dirname(gui.widgets.__file__), 'analysis_tabs')]
sys.modules['gui.widgets.analysis_tabs'] = _analysis_tabs_mod

# base_tab / hotspot_tab 的重依赖 → mock (与 test_r251 一致)
for _dep in ('utils.config_manager', 'utils.trace_context', 'core.performance'):
    _make_mock_module(_dep)

from gui.widgets.analysis_tabs.hotspot_tab import HotspotAnalysisTab  # noqa: E402

# ---------------------------------------------------------------------------
# Part C: ui_components.cleanup_enhanced_batch_analysis (H5 用)
# 注: 整个 ui_components.py 无法 importlib 加载 —— AnalysisToolsPanel 多继承
# (BaseAnalysisPanel(QWidget) + Mixin) 触发 sip wrappertype 元类合并,
# 无头环境 0xC0000005 崩溃 (与 conftest mock 'gui' 的原因一致)。
# 因此用 AST 从源文件提取该方法体并 exec, 保证测试与源文件同步。
# ---------------------------------------------------------------------------
import ast  # noqa: E402
import textwrap  # noqa: E402


def _extract_method_source(rel_path: str, class_name: str, method_name: str) -> str:
    """从源文件提取类方法的源码文本 (AST 定位)"""
    src_path = os.path.join(ROOT, rel_path)
    with open(src_path, encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    lines = src.splitlines()
                    return textwrap.dedent(
                        '\n'.join(lines[item.lineno - 1:item.end_lineno]))
    raise AssertionError(f'{class_name}.{method_name} not found in {rel_path}')


_CLEANUP_NS = {'logger': __import__('loguru').logger}
exec(_extract_method_source(
    'gui/ui_components.py', 'AnalysisToolsPanel', 'cleanup_enhanced_batch_analysis'),
    _CLEANUP_NS)
_cleanup_enhanced_batch_analysis = _CLEANUP_NS['cleanup_enhanced_batch_analysis']

# ---------------------------------------------------------------------------
# 公共构造
# ---------------------------------------------------------------------------
_UNAVAILABLE_RESULT = {
    'stock_code': '000001', 'stock_name': '平安银行', 'strategy': 'MA策略',
    'return_rate': None, 'sharpe_ratio': None, 'max_drawdown': None,
    'win_rate': None, 'total_trades': 0,
    'analysis_time': '2024-01-01 10:00:00', 'data_unavailable': True,
}

_VALID_RESULT = {
    'stock_code': '000002', 'stock_name': '浦发银行', 'strategy': 'MA策略',
    'return_rate': 0.05, 'sharpe_ratio': 1.2, 'max_drawdown': 0.02,
    'win_rate': 0.6, 'total_trades': 3,
    'analysis_time': '2024-01-01 10:00:00',
}


def _build_batch_obj(**kwargs):
    """构造轻量 EnhancedBatchAnalysisMixin 替身 (mixin 无 Qt 基类, 可 object.__new__)"""
    obj = object.__new__(EnhancedBatchAnalysisMixin)
    obj.enhanced_batch_analysis_config = {
        'stocks': [{'code': '000001', 'name': '平安银行'}],
        'strategies': ['MA策略'],
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'initial_capital': 100000,
        'commission': 0.003,
        'slippage': 0.001,
    }
    obj.trading_widget = True
    obj._backtest_engine = _FakeUnifiedBacktestEngine()
    obj._publish_batch_analysis_event = MagicMock()
    obj._add_batch_log = MagicMock()
    for key, value in kwargs.items():
        setattr(obj, key, value)
    return obj


def _build_stats_obj(results):
    """构造带统计 label 的 mixin 替身"""
    obj = _build_batch_obj()
    obj.enhanced_batch_results = results
    obj.batch_results_table = MagicMock()
    obj.batch_tasks_table = MagicMock()
    obj.batch_total_combinations_label = MagicMock()
    obj.batch_profitable_combinations_label = MagicMock()
    obj.batch_best_return_label = MagicMock()
    obj.batch_worst_return_label = MagicMock()
    obj.batch_avg_return_label = MagicMock()
    obj.batch_best_sharpe_label = MagicMock()
    return obj


import unittest  # noqa: E402


class TestH1NoneResultDefense(unittest.TestCase):
    """H1: 批量分析空结果 (None 指标) 消费层不再崩溃"""

    def test_add_result_to_table_with_none_metrics(self):
        """None 指标结果写入结果表: 不抛异常, 百分比列显示 N/A"""
        obj = _build_stats_obj([])
        obj._add_batch_result_to_table(_UNAVAILABLE_RESULT)

        by_col = {}
        for call in obj.batch_results_table.setItem.call_args_list:
            by_col[call.args[1]] = call.args[2].text()

        self.assertEqual(by_col[3], 'N/A')  # 收益率
        self.assertEqual(by_col[4], 'N/A')  # 夏普比率
        self.assertEqual(by_col[5], 'N/A')  # 最大回撤
        self.assertEqual(by_col[6], 'N/A')  # 胜率
        self.assertEqual(by_col[7], '0')    # 交易次数

    def test_add_result_to_table_with_valid_metrics_unchanged(self):
        """正常结果格式化不变"""
        obj = _build_stats_obj([])
        obj._add_batch_result_to_table(_VALID_RESULT)

        by_col = {}
        for call in obj.batch_results_table.setItem.call_args_list:
            by_col[call.args[1]] = call.args[2].text()

        self.assertEqual(by_col[3], '5.00%')
        self.assertEqual(by_col[4], '1.2')
        self.assertEqual(by_col[5], '2.00%')
        self.assertEqual(by_col[6], '60.0%')
        self.assertEqual(by_col[7], '3')

    def test_statistics_all_unavailable_shows_no_data(self):
        """全部结果 data_unavailable: 不抛异常, 显示暂无数据"""
        obj = _build_stats_obj([_UNAVAILABLE_RESULT])
        obj._update_batch_results_statistics()

        obj.batch_total_combinations_label.setText.assert_called_with('1')
        obj.batch_profitable_combinations_label.setText.assert_called_with('0')
        obj.batch_best_return_label.setText.assert_called_with('暂无数据')
        obj.batch_worst_return_label.setText.assert_called_with('暂无数据')
        obj.batch_avg_return_label.setText.assert_called_with('暂无数据')
        obj.batch_best_sharpe_label.setText.assert_called_with('N/A')

    def test_statistics_mixed_skips_unavailable(self):
        """混合结果: 统计仅基于可用数据, 组合总数含全部"""
        obj = _build_stats_obj([_UNAVAILABLE_RESULT, _VALID_RESULT])
        obj._update_batch_results_statistics()

        obj.batch_total_combinations_label.setText.assert_called_with('2')
        obj.batch_profitable_combinations_label.setText.assert_called_with('1')
        obj.batch_best_return_label.setText.assert_called_with('5.00%')
        obj.batch_worst_return_label.setText.assert_called_with('5.00%')
        obj.batch_avg_return_label.setText.assert_called_with('5.00%')
        obj.batch_best_sharpe_label.setText.assert_called_with('1.20')

    def test_filter_profitable_skips_unavailable(self):
        """仅显示盈利: 跳过 data_unavailable 结果, 不抛异常"""
        obj = _build_stats_obj([_UNAVAILABLE_RESULT, _VALID_RESULT])
        obj._filter_profitable_batch_results()

        # 只有 valid 一行被重填 (8 列)
        self.assertEqual(len(obj.batch_results_table.setItem.call_args_list), 8)

    def test_sort_with_none_metrics_no_crash(self):
        """排序含 None 指标的结果: 不抛异常, 全部行重填"""
        obj = _build_stats_obj([_UNAVAILABLE_RESULT, _VALID_RESULT])
        obj._sort_batch_results('return_rate')

        self.assertEqual(len(obj.batch_results_table.setItem.call_args_list), 16)


class TestH2DateRangeConfig(unittest.TestCase):
    """H2: 批量回测日期范围配置生效"""

    def setUp(self):
        # pytest 运行期 (收集→运行之间) 会触发真实导入覆盖 sys.modules 假模块,
        # 这里在每次测试前重新注入, 保证依赖隔离 (与 test_r251 的 mock 手法一致)
        sys.modules['core.containers'] = _containers_mod
        sys.modules['core.services.stock_service'] = _svc_mod
        sys.modules['core.services.strategy_service'] = _stg_mod
        sys.modules['backtest.unified_backtest_engine'] = _fake_backtest_mod
        # R252 交叉审查: 执行期注入必须在测试后立即恢复, 否则跨文件污染
        # (r250 测试 import analysis_service → from core.containers import
        #  ServiceContainer 会拿到无该属性的 mock → ImportError)
        for _name in ('core.containers', 'core.services.stock_service',
                      'core.services.strategy_service',
                      'backtest.unified_backtest_engine'):
            self.addCleanup(lambda n=_name: sys.modules.pop(n, None))

    def test_mode_context_uses_real_start_end_dates(self):
        """mode_context 创建时必须使用配置的真实起止日期"""
        kline_df = pd.DataFrame({
            'close': [10.0 + i * 0.1 for i in range(50)],
            'open': [10.0 + i * 0.1 for i in range(50)],
            'high': [10.5 + i * 0.1 for i in range(50)],
            'low': [9.5 + i * 0.1 for i in range(50)],
            'volume': [1000000] * 50,
        })
        stock_service = MagicMock()
        stock_service.get_kline_data.return_value = kline_df
        container = MagicMock()
        container.resolve.return_value = stock_service
        _containers_mod.get_service_container = MagicMock(return_value=container)

        obj = _build_batch_obj()
        with patch.object(EnhancedBatchAnalysisMixin, '_get_cached_kline_data',
                          return_value=kline_df):
            result = obj._run_real_backtest_analysis(
                {'code': '000001', 'name': '平安银行'}, 'MA策略')

        self.assertIsNotNone(result)
        self.assertEqual(
            obj._backtest_engine.mode_context.config['start_date'], '2024-01-01')
        self.assertEqual(
            obj._backtest_engine.mode_context.config['end_date'], '2024-12-31')
        self.assertEqual(result['return_rate'], 0.1234)

    def test_unavailable_data_log_uses_empty_result_wording(self):
        """数据不可用日志不再宣称'使用模拟数据'"""
        obj = _build_batch_obj()
        stock_service = MagicMock()
        stock_service.get_kline_data.return_value = None
        container = MagicMock()
        container.resolve.return_value = stock_service
        _containers_mod.get_service_container = MagicMock(return_value=container)

        with patch.object(EnhancedBatchAnalysisMixin, '_get_cached_kline_data',
                          return_value=None):
            result = obj._run_real_backtest_analysis(
                {'code': '000001', 'name': '平安银行'}, 'MA策略')

        self.assertIsNotNone(result)
        self.assertTrue(result.get('data_unavailable'))
        # 日志文案不包含 "使用模拟数据"
        for call in obj._add_batch_log.call_args_list:
            self.assertNotIn('使用模拟数据', call.args[0])


class TestH3SelectAllColumns(unittest.TestCase):
    """H3: 股票全选/全不选作用于所有列 (10 列网格)"""

    def _build(self):
        obj = _build_batch_obj()
        table = MagicMock()
        table.rowCount.return_value = 2
        table.columnCount.return_value = 10
        obj._items = [[MagicMock() for _ in range(10)] for _ in range(2)]
        table.item.side_effect = lambda r, c: obj._items[r][c]
        obj.batch_stock_list = table
        return obj

    def test_select_all_touches_all_columns(self):
        obj = self._build()
        obj._batch_select_all_stocks()
        for r in range(2):
            for c in range(10):
                obj._items[r][c].setCheckState.assert_called_with(Qt.Checked)

    def test_select_none_touches_all_columns(self):
        obj = self._build()
        obj._batch_select_no_stocks()
        for r in range(2):
            for c in range(10):
                obj._items[r][c].setCheckState.assert_called_with(Qt.Unchecked)


class TestH4FundFlowRefresh(unittest.TestCase):
    """H4: 热点资金流向数据填充后刷新 UI"""

    def _build_tab(self):
        obj = types.SimpleNamespace()
        obj.capital_flow = []
        obj.sector_rankings = []
        obj.hide_loading = MagicMock()
        obj.update_hotspot_display = MagicMock()
        obj._analyze_capital_flow_from_rankings = MagicMock()
        obj._parse_flow_value = HotspotAnalysisTab._parse_flow_value.__get__(
            obj, HotspotAnalysisTab)
        obj._on_fund_flow_finished = HotspotAnalysisTab._on_fund_flow_finished.__get__(
            obj, HotspotAnalysisTab)
        return obj

    def test_fund_flow_finished_refreshes_display(self):
        """资金流数据填充后必须调用 update_hotspot_display 刷新表格"""
        tab = self._build_tab()
        df = pd.DataFrame({
            '板块': ['银行', '科技'],
            '今日主力净流入-净额': ['10000万', '20000万'],
            '今日散户净流入-净额': ['3000万', '4000万'],
        })
        tab._on_fund_flow_finished({'sector_flow_rank': df})

        self.assertEqual(len(tab.capital_flow), 2)
        tab.update_hotspot_display.assert_called_once()

    def test_fund_flow_finished_empty_data_still_refreshes(self):
        """无资金流数据时同样刷新 (不崩溃)"""
        tab = self._build_tab()
        tab._on_fund_flow_finished({})
        tab.update_hotspot_display.assert_called_once()


class TestH5CleanupThreadCompat(unittest.TestCase):
    """H5: 批量分析线程清理兼容 threading.Thread (无 quit/wait)"""

    def _build_panel(self):
        return types.SimpleNamespace(
            enhanced_batch_worker=None,
            enhanced_batch_results=[],
            enhanced_batch_analysis_config={},
        )

    def test_cleanup_with_threading_thread_no_crash(self):
        """worker 为 threading.Thread 时 cleanup 不抛 AttributeError"""
        obj = self._build_panel()
        obj.enhanced_batch_worker = threading.Thread(target=lambda: None)
        _cleanup_enhanced_batch_analysis(obj)
        self.assertIsNone(obj.enhanced_batch_worker)

    def test_cleanup_with_qthread_worker_still_works(self):
        """worker 支持 quit/wait 时仍正常调用"""
        obj = self._build_panel()
        worker = MagicMock()
        obj.enhanced_batch_worker = worker
        _cleanup_enhanced_batch_analysis(obj)
        worker.quit.assert_called_once()
        worker.wait.assert_called_once()
        self.assertIsNone(obj.enhanced_batch_worker)

    def test_cleanup_without_worker(self):
        """无 worker 时 cleanup 幂等"""
        obj = self._build_panel()
        _cleanup_enhanced_batch_analysis(obj)
        self.assertIsNone(obj.enhanced_batch_worker)


class TestH6HotspotNoFakeData(unittest.TestCase):
    """H6: 移除热点假数据语义 (最小修复)"""

    def setUp(self):
        # R253: 三大空方法已接入 AkShare 真实数据源。为保持 H6 断言离线确定
        # (调用不产生假数据 → 返回空列表), 注入 akshare import 失败 (ImportError),
        # 使方法走降级路径, 不依赖真实网络。
        sys.modules['akshare'] = None
        self.addCleanup(lambda: sys.modules.pop('akshare', None))

    def _build_tab(self):
        return types.SimpleNamespace(
            sector_rankings=None, leading_stocks=None, theme_opportunities=None)

    def test_start_monitor_no_fake_5min_promise(self):
        """实时监控弹窗文案不再宣称'每5分钟更新'(源码级断言, 注释说明不计入)"""
        import inspect
        source = inspect.getsource(HotspotAnalysisTab.start_monitor)
        code_part = source.split('#', 1)[0]  # 去掉注释, 只查用户可见弹窗文案
        self.assertNotIn('每5分钟', code_part)

    def test_sector_hotspots_no_fake_data(self):
        """板块热点: 可调用且不产生假数据"""
        tab = self._build_tab()
        HotspotAnalysisTab.analyze_sector_hotspots(tab, 5, 1.5, 0.05, 2.0)
        self.assertEqual(tab.sector_rankings, [])

    def test_leading_stocks_no_fake_data(self):
        """龙头股: 可调用且不产生假数据"""
        tab = self._build_tab()
        HotspotAnalysisTab.analyze_leading_stocks(tab, 5, 1.5, 0.05)
        self.assertEqual(tab.leading_stocks, [])

    def test_theme_opportunities_no_fake_data(self):
        """主题机会: 可调用且不产生假数据"""
        tab = self._build_tab()
        HotspotAnalysisTab.analyze_theme_opportunities(tab, 5, 1.5)
        self.assertEqual(tab.theme_opportunities, [])


# ---------------------------------------------------------------------------
# 恢复被本文件 mock 污染的 sys.modules 条目, 避免影响其他测试文件
# ---------------------------------------------------------------------------
_POLLUTED_MODULES = [
    'backtest.unified_backtest_engine',
    'core.services.stock_service',
    'core.services.strategy_service',
    'core.containers',
    'utils.config_manager',
    'utils.trace_context',
    'core.performance',
]
for _mod_name in _POLLUTED_MODULES:
    sys.modules.pop(_mod_name, None)


if __name__ == '__main__':
    unittest.main()
