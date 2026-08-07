#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R253 回归测试: 板块资金流流向预测域 (P1-1 / P1-4)

覆盖问题 (R253 交叉验证实证):
- P1-1: sector_flow_tab_pro.py 中 flow_prediction/_flow_prediction_async/
        _generate_flow_prediction 各定义两次, Python 类体后定义覆盖先定义,
        生效版本 (:1617-1654) 返回纯硬编码文本, 无任何实时数据参与
- P1-4: :777 处以两参调用 get_unified_data_manager(service_container, event_bus),
        但定义 def get_unified_data_manager() 无参 -> TypeError 被 try/except
        吞掉 -> TET 兜底方案2永远走不到

测试策略 (参考 tests/test_r252_analysis_tabs.py):
- 保留真实 PyQt5 (无头 offscreen), 仅 mock 重/崩溃依赖链
- 预注册轻量 analysis_tabs 包, importlib 从文件加载真实模块
- 全部以"未绑定方法 + 假 self"方式调用被测方法
- 文件末尾恢复被 mock 的 sys.modules 条目, 避免污染其他测试文件
"""
import os
import sys
import types
import importlib.util

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest  # noqa: E402
import pandas as pd  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS_TABS_DIR = os.path.join(ROOT, 'gui', 'widgets', 'analysis_tabs')

# ---------------------------------------------------------------------------
# sys.modules 保存/恢复工具
# ---------------------------------------------------------------------------
_SAVED_MODULES = {}
_ADDED_MODULES = []


def _make_mock_module(name, **attrs):
    m = MagicMock()
    m.__name__ = name
    m.__file__ = f'<mock:{name}>'
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _install(name, mod):
    if name in sys.modules:
        _SAVED_MODULES[name] = sys.modules[name]
    else:
        _ADDED_MODULES.append(name)
    sys.modules[name] = mod


def _restore_sys_modules():
    for name, mod in _SAVED_MODULES.items():
        sys.modules[name] = mod
    for name in _ADDED_MODULES:
        sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# 轻量 analysis_tabs 包 (跳过 __init__.py 的重型导入链)
# ---------------------------------------------------------------------------
_pkg = types.ModuleType('gui.widgets.analysis_tabs')
_pkg.__path__ = [ANALYSIS_TABS_DIR]
_pkg.__package__ = 'gui.widgets.analysis_tabs'
_install('gui.widgets.analysis_tabs', _pkg)

# ---------------------------------------------------------------------------
# mock 重/崩溃依赖链 (base_tab + utils.manager_factory 模块级导入所需)
# ---------------------------------------------------------------------------
_install('analysis.pattern_recognition',
         _make_mock_module('analysis.pattern_recognition',
                           EnhancedPatternRecognizer=MagicMock()))
_install('analysis.pattern_manager',
         _make_mock_module('analysis.pattern_manager',
                           PatternManager=MagicMock()))
_install('db.models.ai_config_models',
         _make_mock_module('db.models.ai_config_models',
                           get_ai_config_manager=MagicMock()))
_install('core.events.types',
         _make_mock_module('core.events.types',
                           PatternSignalsDisplayEvent=MagicMock()))
_install('core.services.backtest_result_manager',
         _make_mock_module('core.services.backtest_result_manager',
                           BacktestResultManager=MagicMock(),
                           BacktestResult=MagicMock()))
_install('gui.widgets.chart_mixins.signal_mixin',
         _make_mock_module('gui.widgets.chart_mixins.signal_mixin',
                           PatternStyleManager=MagicMock()))
_install('utils.config_manager',
         _make_mock_module('utils.config_manager',
                           ConfigManager=MagicMock()))
_install('utils.trace_context',
         _make_mock_module('utils.trace_context',
                           get_trace_id=MagicMock(return_value='test'),
                           set_trace_id=MagicMock()))
_install('core.performance',
         _make_mock_module('core.performance',
                           measure_performance=lambda *a, **k: (lambda f: f)))
_install('core.performance.unified_monitor',
         _make_mock_module('core.performance.unified_monitor',
                           UnifiedPerformanceMonitor=MagicMock()))
_install('core.industry_manager',
         _make_mock_module('core.industry_manager',
                           IndustryManager=MagicMock()))
_install('utils.theme',
         _make_mock_module('utils.theme',
                           ThemeManager=MagicMock()))
_install('core.services.unified_data_manager',
         _make_mock_module('core.services.unified_data_manager',
                           UnifiedDataManager=MagicMock(),
                           get_unified_data_manager=MagicMock(return_value=None)))


def _load_module(module_name, rel_path):
    """从文件加载真实模块 (绕过 sys.modules 中已注册的 mock)"""
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 依次加载: base_tab -> sector_flow_tab_pro
base_tab = _load_module('gui.widgets.analysis_tabs.base_tab',
                        'gui/widgets/analysis_tabs/base_tab.py')
sector_tab_pro = _load_module('gui.widgets.analysis_tabs.sector_flow_tab_pro',
                              'gui/widgets/analysis_tabs/sector_flow_tab_pro.py')

BaseAnalysisTab = base_tab.BaseAnalysisTab
SectorFlowTabPro = sector_tab_pro.SectorFlowTabPro

# 恢复被 mock 的 sys.modules 条目 (保留已加载的真实模块对象)
_restore_sys_modules()

SRC_FILE = os.path.join(ANALYSIS_TABS_DIR, 'sector_flow_tab_pro.py')
with open(SRC_FILE, encoding='utf-8') as _f:
    _SRC = _f.read()


# ---------------------------------------------------------------------------
# P1-1: 合并双定义为单一数据驱动实现 (源码级断言)
# ---------------------------------------------------------------------------
def test_p11_no_hardcoded_prediction_text():
    """源码中不得再包含硬编码预测字面量 '预计科技板块将继续' (P1-1)"""
    assert '预计科技板块将继续' not in _SRC


def test_p11_prediction_methods_defined_once():
    """flow_prediction/_flow_prediction_async 各只定义一次,
    _generate_flow_prediction 硬编码生成器必须已删除 (P1-1)"""
    assert _SRC.count('def flow_prediction(') == 1
    assert _SRC.count('def _flow_prediction_async(') == 1
    assert _SRC.count('def _generate_flow_prediction(') == 0


# ---------------------------------------------------------------------------
# P1-1: _predict_fund_flow 数据驱动行为 (运行时, 未绑定方法 + 假 self)
# ---------------------------------------------------------------------------
def test_p11_predict_fund_flow_up_trend_3_days():
    """合成 20 天递增 main_net_inflow -> 输出 3 日预测且 direction='up'"""
    fake_self = MagicMock()
    fake_self.ranking_data = [
        {'net_inflow': float(i) * 10000.0} for i in range(1, 21)
    ]  # 20 个递增净流入点 (>=10)
    fake_self.get_sector_historical_trend = MagicMock(
        return_value=pd.DataFrame())  # 历史趋势不可用 -> 回退排行快照
    # MagicMock 会拦截 self.xxx 方法调用, 需显式绑定到类方法
    fake_self._collect_flow_inflow_series = (
        lambda: SectorFlowTabPro._collect_flow_inflow_series(fake_self))
    fake_self._predict_flow_trend = (
        lambda values, horizon=3: SectorFlowTabPro._predict_flow_trend(
            fake_self, values, horizon))

    result = SectorFlowTabPro._predict_fund_flow(fake_self)

    assert isinstance(result, dict), f"应返回结构化预测 dict, 实际: {result!r}"
    assert len(result['values']) == 3
    assert len(result['dates']) == 3
    assert result['direction'] == 'up'
    assert 0.0 < result['confidence'] <= 1.0


def test_p11_predict_fund_flow_insufficient_data():
    """输入不足 (<10 点) 时返回 '数据不足，无法预测' 且不崩溃"""
    fake_self = MagicMock()
    fake_self.ranking_data = [
        {'net_inflow': float(i) * 10000.0} for i in range(1, 6)
    ]  # 仅 5 个点 (<10)
    fake_self.get_sector_historical_trend = MagicMock(
        return_value=pd.DataFrame())
    fake_self._collect_flow_inflow_series = (
        lambda: SectorFlowTabPro._collect_flow_inflow_series(fake_self))
    fake_self._predict_flow_trend = (
        lambda values, horizon=3: SectorFlowTabPro._predict_flow_trend(
            fake_self, values, horizon))

    result = SectorFlowTabPro._predict_fund_flow(fake_self)

    assert result == '数据不足，无法预测'


# ---------------------------------------------------------------------------
# P1-4: get_unified_data_manager 调用处签名正确 (运行时 mock 断言)
# ---------------------------------------------------------------------------
def test_p14_get_unified_data_manager_call_site_no_typeerror():
    """修复后 :777 调用点必须以无参方式调用 get_unified_data_manager (P1-4):
    以严格无参签名的桩替换后, 调用过程不得抛 TypeError, 且所有调用均为无参"""
    calls = []
    udm = MagicMock()
    udm.get_sector_fund_flow_service.return_value = None  # 方案1 走空 -> 进入方案2

    def strict_get_unified_data_manager(*args, **kwargs):
        """模拟真实 def get_unified_data_manager() 无参签名"""
        calls.append((args, kwargs))
        if args or kwargs:
            raise TypeError("get_unified_data_manager() takes no arguments")
        return udm

    saved = {}
    tmp_mods = {
        'core.services.unified_data_manager': _make_mock_module(
            'core.services.unified_data_manager',
            UnifiedDataManager=MagicMock(),
            get_unified_data_manager=strict_get_unified_data_manager),
        'core.plugin_types': _make_mock_module(
            'core.plugin_types',
            AssetType=MagicMock(),
            DataType=MagicMock()),
        'core.containers.service_container': _make_mock_module(
            'core.containers.service_container',
            get_service_container=lambda: MagicMock()),
        'core.events.event_bus': _make_mock_module(
            'core.events.event_bus',
            EventBus=MagicMock()),
    }
    for name, mod in tmp_mods.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod
    try:
        fake_self = MagicMock()
        fake_self.service_container = MagicMock()
        fake_self._process_new_sector_flow_data = MagicMock(return_value=[])
        fake_self._process_realtime_fund_flow_data = MagicMock(return_value=[])
        fake_self._implement_fund_flow_analysis = MagicMock(return_value=[])

        SectorFlowTabPro._get_realtime_fund_flow_data(fake_self)
    finally:
        for name, mod in saved.items():
            if mod is not None:
                sys.modules[name] = mod
            else:
                sys.modules.pop(name, None)

    assert calls, "应至少调用一次 get_unified_data_manager"
    for args, kwargs in calls:
        assert args == () and kwargs == {}, \
            f"get_unified_data_manager 必须以无参方式调用, 实际: {args} {kwargs}"
