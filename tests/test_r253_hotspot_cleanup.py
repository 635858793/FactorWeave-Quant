#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R253 回归测试: 热点分析三大空方法接入真实数据源 + right_panel AI 选股死代码清理

覆盖:
- H1: analyze_sector_hotspots 接入 AkShare 真实数据源 (mock), 填充非空 sector_rankings
      (键对齐 update_hotspot_display :681-710, 热度降序)
- H2: analyze_leading_stocks / analyze_theme_opportunities 同样填充真实数据 (mock)
- H3: akshare import 失败 (ImportError) 时三方法返回空列表且不抛异常
- H4: right_panel.py 不再包含 AI 选股死代码方法定义 (源码级断言)

依赖隔离与 test_r252_batch_hotspot.py 一致:
- 移除 conftest 预注册的 gui 系列 mock
- sys.modules 注入 mock 依赖后 import hotspot_tab
- 每个测试 setUp 注入/清理 'akshare', 防止跨文件污染
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


# ---------------------------------------------------------------------------
# hotspot_tab 依赖隔离 (与 test_r252 一致)
# ---------------------------------------------------------------------------
import gui.widgets  # noqa: E402  (其 __init__.py 仅注释, 安全)

_analysis_tabs_mod = types.ModuleType('gui.widgets.analysis_tabs')
_analysis_tabs_mod.__path__ = [
    os.path.join(os.path.dirname(gui.widgets.__file__), 'analysis_tabs')]
sys.modules['gui.widgets.analysis_tabs'] = _analysis_tabs_mod

for _dep in ('utils.config_manager', 'utils.trace_context', 'core.performance'):
    _make_mock_module(_dep)

from gui.widgets.analysis_tabs.hotspot_tab import HotspotAnalysisTab  # noqa: E402

# R253 交叉审查: 模块级注入后必须恢复, 否则污染后续收集的测试文件
# (core.performance 被替换为非包 MagicMock, 导致 core.performance.cache_manager 无法导入)
for _dep in ('utils.config_manager', 'utils.trace_context', 'core.performance'):
    sys.modules.pop(_dep, None)

_RIGHT_PANEL_SRC = os.path.join(ROOT, 'core/ui/panels/right_panel.py')

# ---------------------------------------------------------------------------
# 假 akshare 模块: 行业板块行情 / 板块成分股 / 概念板块行情
# ---------------------------------------------------------------------------


def _make_fake_ak():
    """构造假 akshare 模块 (sys.modules 注入用)"""
    ak = MagicMock()
    ak.__name__ = 'akshare'

    ak.stock_board_industry_name_em.return_value = pd.DataFrame({
        '板块名称': ['银行', '半导体', '白酒', '医药'],
        '板块代码': ['BK0475', 'BK1036', 'BK0896', 'BK0727'],
        '涨跌幅': [3.25, 2.10, 1.80, -0.50],
        '换手率': [1.50, 4.20, 0.80, 1.10],
        '成交额': [2.5e11, 8.0e10, 3.0e10, 1.2e10],
        '领涨股票': ['招商银行', '中芯国际', '贵州茅台', '恒瑞医药'],
        '上涨家数': [30, 45, 18, 12],
        '下跌家数': [5, 3, 12, 28],
    })

    ak.stock_board_industry_cons_em.return_value = pd.DataFrame({
        '代码': ['600036', '601398', '000001'],
        '名称': ['招商银行', '工商银行', '平安银行'],
        '涨跌幅': [4.10, 3.20, 2.80],
        '成交额': [5.0e9, 4.0e9, 3.0e9],
        '量比': [2.5, 1.8, 1.5],
        '总市值': [9.5e11, 1.8e12, 2.0e11],
    })

    ak.stock_board_concept_name_em.return_value = pd.DataFrame({
        '概念名称': ['国产芯片', '人工智能', '新能源车'],
        '概念代码': ['BK1036', 'BK0800', 'BK1034'],
        '涨跌幅': [5.20, 4.10, 3.30],
        '换手率': [6.0, 5.0, 4.0],
        '上涨家数': [60, 40, 35],
        '下跌家数': [2, 5, 8],
        '领涨股票': ['中芯国际', '科大讯飞', '宁德时代'],
    })
    return ak


def _build_tab():
    """构造轻量 HotspotAnalysisTab 替身 (仅需三个结果属性)"""
    return types.SimpleNamespace(
        sector_rankings=None, leading_stocks=None, theme_opportunities=None)


class TestHotspotRealDataSource(unittest.TestCase):
    """H1/H2: 三方法接入 AkShare 真实数据源 (mock 注入)"""

    def setUp(self):
        self._fake_ak = _make_fake_ak()
        sys.modules['akshare'] = self._fake_ak
        self.addCleanup(lambda: sys.modules.pop('akshare', None))

    def test_analyze_sector_hotspots_fills_rankings(self):
        """板块热点: 填充非空 sector_rankings, 键对齐渲染, 热度降序"""
        tab = _build_tab()
        HotspotAnalysisTab.analyze_sector_hotspots(tab, 5, 1.5, 0.05, 2.0)

        self.assertTrue(tab.sector_rankings, 'sector_rankings 不应为空')
        required = {'板块名称', '热度指数', '涨跌幅', '成交量比',
                    '领涨股', '上涨家数', '热点等级'}
        self.assertTrue(
            required.issubset(set(tab.sector_rankings[0])),
            f'缺少渲染键: {required - set(tab.sector_rankings[0])}')
        heats = [float(r['热度指数']) for r in tab.sector_rankings]
        self.assertEqual(heats, sorted(heats, reverse=True), '应按热度降序')

    def test_analyze_leading_stocks_fills_stocks(self):
        """龙头股: 基于板块热点前3板块成分股, 填充非空 leading_stocks"""
        tab = _build_tab()
        HotspotAnalysisTab.analyze_sector_hotspots(tab, 5, 1.5, 0.05, 2.0)
        HotspotAnalysisTab.analyze_leading_stocks(tab, 5, 1.5, 0.05)

        self.assertTrue(tab.leading_stocks, 'leading_stocks 不应为空')
        required = {'股票代码', '股票名称', '所属板块', '涨跌幅',
                    '成交量比', '龙头指数', '市值', '地位'}
        self.assertTrue(
            required.issubset(set(tab.leading_stocks[0])),
            f'缺少渲染键: {required - set(tab.leading_stocks[0])}')

    def test_analyze_theme_opportunities_fills_themes(self):
        """主题机会: 填充非空 theme_opportunities, 按涨跌幅降序"""
        tab = _build_tab()
        HotspotAnalysisTab.analyze_theme_opportunities(tab, 5, 1.5)

        self.assertTrue(tab.theme_opportunities, 'theme_opportunities 不应为空')
        required = {'主题名称', '热度评分', '相关股票数',
                    '平均涨幅', '资金关注度', '投资机会'}
        self.assertTrue(
            required.issubset(set(tab.theme_opportunities[0])),
            f'缺少渲染键: {required - set(tab.theme_opportunities[0])}')
        gains = [float(t['平均涨幅'].replace('%', '').replace('+', ''))
                 for t in tab.theme_opportunities]
        self.assertEqual(gains, sorted(gains, reverse=True), '应按涨跌幅降序')


class TestAkshareImportFailure(unittest.TestCase):
    """H3: akshare import 失败 (sys.modules['akshare'] = None → ImportError) 时降级"""

    def setUp(self):
        # None in sys.modules 会使 'import akshare' 抛 ImportError
        sys.modules['akshare'] = None
        self.addCleanup(lambda: sys.modules.pop('akshare', None))

    def test_sector_hotspots_import_failure_returns_empty(self):
        tab = _build_tab()
        HotspotAnalysisTab.analyze_sector_hotspots(tab, 5, 1.5, 0.05, 2.0)
        self.assertEqual(tab.sector_rankings, [])

    def test_leading_stocks_import_failure_returns_empty(self):
        tab = _build_tab()
        HotspotAnalysisTab.analyze_leading_stocks(tab, 5, 1.5, 0.05)
        self.assertEqual(tab.leading_stocks, [])

    def test_theme_opportunities_import_failure_returns_empty(self):
        tab = _build_tab()
        HotspotAnalysisTab.analyze_theme_opportunities(tab, 5, 1.5)
        self.assertEqual(tab.theme_opportunities, [])


class TestRightPanelDeadCodeRemoved(unittest.TestCase):
    """H4: right_panel.py 不再包含 AI 选股死代码方法定义 (源码级断言)"""

    def test_no_ai_dead_code_definitions(self):
        with open(_RIGHT_PANEL_SRC, encoding='utf-8') as f:
            src = f.read()
        dead_methods = (
            '_create_ai_stock_tab', '_on_ai_select_stocks', '_should_use_nlp',
            '_convert_ui_to_criteria', '_display_ai_selection_results',
            '_on_export_ai_results')
        for name in dead_methods:
            self.assertNotIn(
                f'def {name}(', src, f'{name} 死代码未清理')

    def test_no_ai_old_button_connections(self):
        """旧按钮信号连接 (ai_run_btn / export_ai_btn) 应已移除"""
        with open(_RIGHT_PANEL_SRC, encoding='utf-8') as f:
            src = f.read()
        self.assertNotIn('_on_ai_select_stocks', src)
        self.assertNotIn('_on_export_ai_results', src)
        # 基础功能 tab 创建链仍保留
        self.assertIn('self._create_industry_tab(tab_widget)', src)


if __name__ == '__main__':
    unittest.main()
