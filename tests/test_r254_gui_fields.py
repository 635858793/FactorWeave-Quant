#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R254 回归测试: GUI域 P2/P3 修复 (板块资金流字段映射 + 热点估算标注 + 热点结果落库)

覆盖:
- T1: sector_flow_tab_pro._process_new_sector_flow_data 字段映射兼容双插件
      (change_pct/change_percent 双形态 + super_large_net_inflow 等净流入口径)
      + flow_strength 基于 main_net_inflow 绝对值
- T2: _update_monitor_table 读取键与产出 dict 键对齐 (mock 断言 6 列全部填充)
- T3: _analyze_capital_flow_from_rankings 产出含 '数据来源': '估算'
- T4: 热点结果落库 (mock asset_db_manager 断言 store_standardized_data
      被调用且 DataFrame 列为英文列)

依赖隔离与 test_r252_batch_hotspot.py / test_r253_hotspot_cleanup.py 一致:
- 移除 conftest 预注册的 gui 系列 mock
- sys.modules 注入 mock 依赖后 importlib 加载 sector_flow_tab_pro / hotspot_tab
- 文件末尾恢复被 mock 的条目, 避免污染其他测试文件
"""
import os
import sys
import types
import unittest

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

from unittest.mock import MagicMock  # noqa: E402
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
# 依赖隔离: 轻量 analysis_tabs 包 + mock 重依赖
# ---------------------------------------------------------------------------
import gui.widgets  # noqa: E402  (其 __init__.py 仅注释, 安全)

_analysis_tabs_mod = types.ModuleType('gui.widgets.analysis_tabs')
_analysis_tabs_mod.__path__ = [
    os.path.join(os.path.dirname(gui.widgets.__file__), 'analysis_tabs')]
sys.modules['gui.widgets.analysis_tabs'] = _analysis_tabs_mod

for _dep in ('utils.config_manager', 'utils.trace_context', 'core.performance',
             'utils.manager_factory'):
    _make_mock_module(_dep)

# base_tab 真实加载 (依赖已被 mock), 供 sector_flow_tab_pro / hotspot_tab 使用
base_tab = _load_module_from_file(
    'gui.widgets.analysis_tabs.base_tab',
    'gui/widgets/analysis_tabs/base_tab.py')

sector_flow_tab_pro = _load_module_from_file(
    'gui.widgets.analysis_tabs.sector_flow_tab_pro',
    'gui/widgets/analysis_tabs/sector_flow_tab_pro.py')

from gui.widgets.analysis_tabs.hotspot_tab import HotspotAnalysisTab  # noqa: E402

SectorFlowTabPro = sector_flow_tab_pro.SectorFlowTabPro

# R253 交叉审查: 模块级注入后必须恢复, 否则污染后续收集的测试文件
for _dep in ('utils.config_manager', 'utils.trace_context', 'core.performance',
             'utils.manager_factory'):
    sys.modules.pop(_dep, None)


class TestSectorFlowFieldMapping(unittest.TestCase):
    """T1: _process_new_sector_flow_data 字段映射兼容双插件"""

    @staticmethod
    def _make_akshare_df():
        """akshare 插件列形态 (change_percent + super_large_net_inflow + timestamp)"""
        return pd.DataFrame([{
            'sector_code': 'AK_001',
            'sector_name': '银行',
            'change_percent': 2.5,
            'main_net_inflow': 60000000,
            'super_large_net_inflow': 30000000,
            'large_net_inflow': 20000000,
            'medium_net_inflow': 8000000,
            'small_net_inflow': 2000000,
            'timestamp': '2026-08-06 10:00:00',
        }])

    @staticmethod
    def _make_eastmoney_df():
        """eastmoney 插件列形态 (change_pct + super_large_net_inflow, 无 timestamp)"""
        return pd.DataFrame([{
            'sector_code': 'BK0475',
            'sector_name': '半导体',
            'change_pct': -1.2,
            'main_net_inflow': -8000000,
            'super_large_net_inflow': -5000000,
            'large_net_inflow': -2000000,
            'medium_net_inflow': -600000,
            'small_net_inflow': -400000,
        }])

    def test_akshare_mapping_and_flow_strength(self):
        """akshare 列形态: 净流入口径字段映射 + flow_strength 基于主力净流入绝对值"""
        tab = MagicMock()
        result = SectorFlowTabPro._process_new_sector_flow_data(
            tab, self._make_akshare_df())
        self.assertEqual(len(result), 1)
        d = result[0]
        # 插件实际输出 super_large_net_inflow → super_large_inflow
        self.assertEqual(d['super_large_inflow'], 30000000)
        self.assertEqual(d['large_inflow'], 20000000)
        self.assertEqual(d['medium_inflow'], 8000000)
        self.assertEqual(d['small_inflow'], 2000000)
        # change_percent 形态
        self.assertEqual(d['avg_change_percent'], 2.5)
        # timestamp → trade_date
        self.assertEqual(d['trade_date'], '2026-08-06 10:00:00')
        # outflow 系列恒 0 (数据源无流入/流出拆分)
        self.assertEqual(d['super_large_outflow'], 0)
        self.assertEqual(d['large_outflow'], 0)
        self.assertEqual(d['medium_outflow'], 0)
        self.assertEqual(d['small_outflow'], 0)
        # ranking/stock_count/turnover_rate 无来源置 0
        self.assertEqual(d['ranking'], 0)
        self.assertEqual(d['stock_count'], 0)
        self.assertEqual(d['turnover_rate'], 0)
        # flow_strength: |6000万| >= 5000万 → 80
        self.assertEqual(d['flow_strength'], 80)
        # flow_status 基于 main_net_inflow
        self.assertEqual(d['flow_status'], '强力流入')

    def test_eastmoney_mapping_change_pct(self):
        """eastmoney 列形态: change_pct 形态 + 无 timestamp 兜底为空"""
        tab = MagicMock()
        result = SectorFlowTabPro._process_new_sector_flow_data(
            tab, self._make_eastmoney_df())
        self.assertEqual(len(result), 1)
        d = result[0]
        # change_pct 形态
        self.assertEqual(d['avg_change_percent'], -1.2)
        self.assertEqual(d['super_large_inflow'], -5000000)
        self.assertEqual(d['main_net_inflow'], -8000000)
        # 无 timestamp 列 → 空字符串
        self.assertEqual(d['trade_date'], '')
        # flow_strength: |800万| >= 100万 → 40
        self.assertEqual(d['flow_strength'], 40)
        # flow_status 基于 main_net_inflow: -800万 < -1万 → 强力流出
        self.assertEqual(d['flow_status'], '强力流出')

    def test_change_pct_priority_over_change_percent(self):
        """双形态同时存在时 change_pct 优先; 零净流入 → flow_strength 0"""
        df = pd.DataFrame([{
            'sector_code': 'BK0001',
            'sector_name': '测试',
            'change_pct': 1.5,
            'change_percent': 9.9,
            'main_net_inflow': 0,
            'super_large_net_inflow': 0,
            'large_net_inflow': 0,
            'medium_net_inflow': 0,
            'small_net_inflow': 0,
        }])
        tab = MagicMock()
        result = SectorFlowTabPro._process_new_sector_flow_data(tab, df)
        self.assertEqual(result[0]['avg_change_percent'], 1.5)
        self.assertEqual(result[0]['flow_strength'], 0)
        self.assertEqual(result[0]['flow_status'], '基本平衡')


class TestUpdateMonitorTableKeys(unittest.TestCase):
    """T2: _update_monitor_table 读取键与 _process_new_sector_flow_data 产出键对齐"""

    @staticmethod
    def _produced_row():
        """_process_new_sector_flow_data 实际产出的 dict 结构"""
        return {
            'sector_id': 'AK_001',
            'sector_name': '银行',
            'main_net_inflow': 60000000,
            'super_large_inflow': 30000000,
            'super_large_outflow': 0,
            'large_inflow': 20000000,
            'large_outflow': 0,
            'medium_inflow': 8000000,
            'medium_outflow': 0,
            'small_inflow': 2000000,
            'small_outflow': 0,
            'stock_count': 0,
            'avg_change_percent': 2.5,
            'turnover_rate': 0,
            'ranking': 0,
            'trade_date': '2026-08-06 10:00:00',
            'update_time': '2026-08-06 10:00:00',
            'flow_strength': 80,
            'flow_status': '强力流入',
        }

    def test_monitor_table_consumes_produced_keys(self):
        """产出 dict 的键必须被 _update_monitor_table 消费, 6 列全部非空"""
        tab = MagicMock()
        table = MagicMock()
        tab.monitor_table = table
        SectorFlowTabPro._update_monitor_table(
            tab, [self._produced_row()])

        table.setRowCount.assert_called_once_with(1)
        self.assertEqual(table.setItem.call_count, 6)  # 6 列全部填充
        by_col = {}
        for call in table.setItem.call_args_list:
            by_col[call.args[1]] = call.args[2].text()
        # 列头: 时间/板块/事件/金额(万)/影响/状态
        self.assertEqual(by_col[0], '2026-08-06 10:00:00')  # 时间 ← trade_date
        self.assertEqual(by_col[1], '银行')                  # 板块 ← sector_name
        self.assertEqual(by_col[2], 'AK_001')                # 事件 ← sector_id
        self.assertEqual(by_col[3], '6000')                  # 金额(万) ← main_net_inflow/10000
        self.assertEqual(by_col[4], '80')                    # 影响 ← flow_strength
        self.assertEqual(by_col[5], '强力流入')              # 状态 ← flow_status

    def test_monitor_table_defaults_for_missing_keys(self):
        """缺失键时使用默认值, 不抛异常"""
        tab = MagicMock()
        table = MagicMock()
        tab.monitor_table = table
        SectorFlowTabPro._update_monitor_table(tab, [{}])
        table.setRowCount.assert_called_once_with(1)
        self.assertEqual(table.setItem.call_count, 6)


class TestCapitalFlowEstimateMarking(unittest.TestCase):
    """T3: _analyze_capital_flow_from_rankings 产出含 '数据来源': '估算'"""

    def test_estimate_flow_contains_source_mark(self):
        """估算资金流条目必须显式标注 '数据来源': '估算' (反假数据原则)"""
        tab = MagicMock()
        tab.sector_rankings = [
            {'板块名称': '银行', '涨跌幅': '+3.25%'},
            {'板块名称': '半导体', '涨跌幅': '-2.10%'},
        ]
        tab.capital_flow = []
        HotspotAnalysisTab._analyze_capital_flow_from_rankings(tab)
        self.assertEqual(len(tab.capital_flow), 2)
        for entry in tab.capital_flow:
            self.assertEqual(entry.get('数据来源'), '估算')

    def test_estimate_flow_empty_rankings(self):
        """无排行数据时估算结果为空, 不抛异常"""
        tab = MagicMock()
        tab.sector_rankings = []
        tab.capital_flow = []
        HotspotAnalysisTab._analyze_capital_flow_from_rankings(tab)
        self.assertEqual(tab.capital_flow, [])


class TestHotspotPersistence(unittest.TestCase):
    """T4: 热点结果落库 (mock asset_db_manager)"""

    def setUp(self):
        # 用 mock 模块替换 core.asset_database_manager, 断言落库调用
        self._asset_db_mod = _make_mock_module('core.asset_database_manager')
        self._asset_db_manager = MagicMock()
        self._asset_db_mod.get_asset_separated_database_manager = MagicMock(
            return_value=self._asset_db_manager)
        self.addCleanup(lambda: sys.modules.pop('core.asset_database_manager', None))

    @staticmethod
    def _build_tab():
        # 绑定真实 staticmethod 底层函数 (MagicMock 实例会拦截类属性查找,
        # 导致 self._build_hotspot_persist_frame(...) 返回 MagicMock 而非 DataFrame)
        tab = MagicMock()
        tab._build_hotspot_persist_frame = \
            HotspotAnalysisTab._build_hotspot_persist_frame
        tab.sector_rankings = [
            {'板块名称': '银行', '板块代码': 'BK0475', '热度指数': '45.6',
             '涨跌幅': '+3.25%', '成交量比': '1.50%', '领涨股': '招商银行',
             '上涨家数': '30', '热点等级': '超级热点'},
        ]
        tab.theme_opportunities = [
            {'主题名称': '国产芯片', '热度评分': '52', '相关股票数': '62',
             '平均涨幅': '+5.20%', '资金关注度': '高', '投资机会': '强烈推荐'},
        ]
        return tab

    @staticmethod
    def _build_empty_tab():
        tab = MagicMock()
        tab._build_hotspot_persist_frame = \
            HotspotAnalysisTab._build_hotspot_persist_frame
        tab.sector_rankings = []
        tab.theme_opportunities = []
        return tab

    def test_persist_sector_and_concept_with_english_columns(self):
        """板块→SECTOR_DATA / 概念→CONCEPT_DATA, DataFrame 列为英文列"""
        tab = self._build_tab()
        HotspotAnalysisTab._persist_hotspot_results(tab)

        self._asset_db_mod.get_asset_separated_database_manager.assert_called_once()
        self.assertEqual(
            self._asset_db_manager.store_standardized_data.call_count, 2)

        # 第一次调用: 板块 → SECTOR_DATA (英文列, 热度指数转 float)
        first_call = self._asset_db_manager.store_standardized_data.call_args_list[0]
        sector_df = first_call.args[0]
        self.assertIsInstance(sector_df, pd.DataFrame)
        self.assertEqual(
            set(sector_df.columns),
            {'sector_name', 'sector_code', 'heat_score', 'change_pct', 'turnover_rate'})
        self.assertEqual(float(sector_df.iloc[0]['heat_score']), 45.6)
        self.assertEqual(float(sector_df.iloc[0]['change_pct']), 3.25)
        self.assertEqual(first_call.args[1].value, 'sector')        # AssetType.SECTOR
        self.assertEqual(first_call.args[2].value, 'sector_data')   # DataType.SECTOR_DATA

        # 第二次调用: 概念 → CONCEPT_DATA (英文列)
        second_call = self._asset_db_manager.store_standardized_data.call_args_list[1]
        theme_df = second_call.args[0]
        self.assertEqual(
            set(theme_df.columns),
            {'concept_name', 'heat_score', 'change_pct', 'stock_count'})
        self.assertEqual(float(theme_df.iloc[0]['heat_score']), 52.0)
        self.assertEqual(second_call.args[2].value, 'concept_data')  # DataType.CONCEPT_DATA

    def test_persist_skips_empty_results(self):
        """结果为空时不下发 store_standardized_data (不抛异常)"""
        tab = self._build_empty_tab()
        HotspotAnalysisTab._persist_hotspot_results(tab)
        self._asset_db_manager.store_standardized_data.assert_not_called()

    def test_persist_failure_does_not_raise(self):
        """落库异常仅告警不抛异常 (不阻断 UI)"""
        self._asset_db_manager.store_standardized_data.side_effect = \
            RuntimeError('db down')
        tab = self._build_tab()
        try:
            HotspotAnalysisTab._persist_hotspot_results(tab)
        except RuntimeError:
            self.fail('落库失败不应向上抛异常')

    def test_analyze_hotspot_calls_persist_before_emit(self):
        """analyze_hotspot 必须在 emit 前调用 _persist_hotspot_results (源码级断言)"""
        import inspect
        source = inspect.getsource(HotspotAnalysisTab.analyze_hotspot)
        self.assertIn('_persist_hotspot_results()', source)
        emit_pos = source.index('hotspot_analysis_completed.emit')
        persist_pos = source.index('_persist_hotspot_results()')
        self.assertLess(persist_pos, emit_pos)


if __name__ == '__main__':
    unittest.main()
