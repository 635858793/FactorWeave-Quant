#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R282 专项测试：指标判组统一 + 参数兜底 + 中文名 + 参数/归属持久化 + 去重指纹

覆盖：
- BUILTIN_INDICATORS 单源判组（left_panel/middle_panel 口径一致，CCI/OBV 归 talib 组）
- get_indicator_params_config 兜底配置（KAMA/MAMA/TEMA 等 DB 未种子指标参数非空）
- get_talib_chinese_name 中文名补齐
- middle_panel 全量指标列表 = 内置 + TA-Lib + DB 去重
- middle_panel 对话框改参回存与重选持久化（_indicator_user_params / _indicator_region_map）
- IndicatorChangedEvent dedup_fingerprint（改参事件不被 0.5s 去重窗口误吞）
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# conftest.py 将 gui.widgets / core.ui.panels 等注入 MagicMock（R256+ 规避 Qt 硬崩溃）。
# 本测试需真实导入 middle_panel，故 pop 后重建（参照 test_r270 模式）。
_CONFTEST_MOCKS = [
    'gui.widgets',
    'core.ui',
    'core.ui.panels',
    'core.ui.panels.middle_panel',
    'core.ui.panels.base_panel',
]
for _mod in _CONFTEST_MOCKS:
    sys.modules.pop(_mod, None)

from core.indicators.indicators_algorithm import BUILTIN_INDICATORS, get_talib_real_indicator_list
from core.indicator_adapter import get_indicator_params_config, get_talib_chinese_name
from core.events.types import IndicatorChangedEvent


def _load_middle_panel_module():
    import importlib
    return importlib.import_module('core.ui.panels.middle_panel')


# ==================== 1. 判组单源 ====================

def test_builtin_indicators_single_source():
    """判组唯一常量：5 项内置，CCI/OBV 不属内置（走 talib 组直算）"""
    assert BUILTIN_INDICATORS == frozenset({'MA', 'MACD', 'RSI', 'BOLL', 'KDJ'})
    assert 'CCI' not in BUILTIN_INDICATORS
    assert 'OBV' not in BUILTIN_INDICATORS


def test_middle_panel_builtin_consistency():
    """middle_panel 类常量与判组唯一常量一致（消除 7 项硬编码）"""
    mod = _load_middle_panel_module()
    assert mod.MiddlePanel._BUILTIN_INDICATORS == set(BUILTIN_INDICATORS)
    assert mod.MiddlePanel._BUILTIN_LIST == sorted(BUILTIN_INDICATORS)
    assert 'CCI' not in mod.MiddlePanel._BUILTIN_LIST
    assert 'OBV' not in mod.MiddlePanel._BUILTIN_LIST


# ==================== 2. 参数兜底配置 ====================

@pytest.mark.parametrize("name", [
    'KAMA', 'MAMA', 'TEMA', 'MACDEXT', 'STOCHF', 'STOCHRSI',
    'ULTOSC', 'SAR', 'STDDEV', 'VAR', 'NATR', 'AROONOSC',
])
def test_fallback_param_config_non_empty(name):
    """DB 未种子指标（走 _FALLBACK_INDICATOR_CONFIGS 兜底）参数配置非空"""
    cfg = get_indicator_params_config(name)
    assert cfg is not None, f'{name} 无兜底配置'
    assert cfg.get('params'), f'{name} 参数为空'


def test_fallback_kama_defaults():
    """KAMA 兜底参数符合 TA-Lib 契约（timeperiod/fastlimit/slowlimit）"""
    cfg = get_indicator_params_config('KAMA')
    params = cfg['params']
    assert 'timeperiod' in params and params['timeperiod']['default'] == 10
    assert 'fastlimit' in params and params['fastlimit']['default'] == 0.666
    assert 'slowlimit' in params and params['slowlimit']['default'] == 0.0645


# ==================== 3. 中文名补齐 ====================

@pytest.mark.parametrize("en,cn", [
    ('KAMA', '考夫曼'), ('MAMA', 'MESA'), ('TEMA', '三重'),
    ('TRIMA', '三角'), ('ADXR', '平均方向'), ('TRIX', '三重指数'),
])
def test_chinese_name_mapping(en, cn):
    assert cn in get_talib_chinese_name(en), f'{en} 中文名缺失'


def test_chinese_name_not_empty_for_all_talib():
    """TA-Lib 全量列表中文名覆盖（TRANGE 为内部范围函数，豁免）"""
    exempt = {'TRANGE'}
    empty = [n for n in get_talib_real_indicator_list() if n not in exempt
             and (not get_talib_chinese_name(n) or get_talib_chinese_name(n) == n)]
    assert not empty, f"无中文名指标: {empty}"


# ==================== 4. 全量指标列表（内置 + TA-Lib + DB 去重） ====================

def test_all_indicator_names_talib_plus_db(monkeypatch):
    """_get_all_indicator_names 合并内置+TA-Lib+DB 全量去重（DB 自定义指标可见）"""
    mod = _load_middle_panel_module()
    # 避免真实 DB IO：mock DB 返回
    monkeypatch.setattr(
        'core.indicator_adapter.get_all_indicators_metadata',
        lambda: [{'name': 'MYCUSTOM'}, {'name': 'KAMA'}]  # KAMA 与 TA-Lib 重名验证去重
    )
    obj = SimpleNamespace(_BUILTIN_LIST=mod.MiddlePanel._BUILTIN_LIST)
    names = mod.MiddlePanel._get_all_indicator_names(obj)
    assert len(set(names)) == len(names), "列表存在重复"
    assert 'MYCUSTOM' in names, "DB 自定义指标未出现"
    assert 'KAMA' in names and 'MAMA' in names and 'TEMA' in names
    # 内置 5 项 + TA-Lib(59) + DB 新增，去重后应 ≥ 60
    assert len(names) >= 60, f"全量指标列表过短: {len(names)}"


# ==================== 5. 参数/归属持久化 ====================

def _make_panel(monkeypatch):
    mod = _load_middle_panel_module()
    chart_widget = MagicMock()
    canvas = SimpleNamespace(chart_widget=chart_widget)
    panel = SimpleNamespace(
        _BUILTIN_INDICATORS=mod.MiddlePanel._BUILTIN_INDICATORS,
        _TALIB_DEFAULT_PARAMS=mod.MiddlePanel._TALIB_DEFAULT_PARAMS,
        _indicator_region_map={'KAMA': 'indicator1'},
        _indicator_user_params={},
    )
    panel.get_widget = lambda k: {'chart_canvas': canvas}.get(k)
    return mod, panel, chart_widget


def test_user_params_persisted_on_accept(monkeypatch):
    """对话框改参事件 → 回存 _indicator_user_params；重选（无参事件）→ 复用历史参数"""
    mod, panel, chart_widget = _make_panel(monkeypatch)
    event = IndicatorChangedEvent(
        selected_indicators=['KAMA'],
        indicator_params={'KAMA': {'timeperiod': 21}},
    )
    mod.MiddlePanel.on_indicator_changed(panel, event)
    assert panel._indicator_user_params['KAMA'] == {'timeperiod': 21}

    # left_panel 重选（事件不带 params）→ 复用历史参数 + 保留 region
    event2 = IndicatorChangedEvent(selected_indicators=['KAMA'])
    mod.MiddlePanel.on_indicator_changed(panel, event2)
    ind_list = chart_widget.on_indicator_selected.call_args.args[0]
    kama = next(i for i in ind_list if i['name'] == 'KAMA')
    assert kama['params'].get('timeperiod') == 21, "历史参数未复用"
    assert kama['region'] == 'indicator1', "区域归属未保留"


def test_region_map_cleared_on_none(monkeypatch):
    """区域下拉框选"无" → 移除该区域历史归属（R283: 单指标区）"""
    mod = _load_middle_panel_module()
    chart_widget = MagicMock()
    canvas = SimpleNamespace(chart_widget=chart_widget)
    combos = {
        'indicator1_combo': SimpleNamespace(currentText=lambda: '无'),
    }
    panel = SimpleNamespace(
        _BUILTIN_INDICATORS=mod.MiddlePanel._BUILTIN_INDICATORS,
        _TALIB_DEFAULT_PARAMS=mod.MiddlePanel._TALIB_DEFAULT_PARAMS,
        _indicator_region_map={'RSI': 'indicator1'},
        _indicator_user_params={},
    )
    panel.get_widget = lambda k: {'chart_canvas': canvas}.get(k, combos.get(k))
    mod.MiddlePanel._on_region_indicator_changed(panel, '无')
    assert panel._indicator_region_map == {}, "indicator1 清空后归属应全部移除"


# ==================== 6. 去重指纹 ====================

def test_dedup_fingerprint():
    """改参事件指纹不同（不被 0.5s 去重窗口误吞）；同参事件指纹一致"""
    e1 = IndicatorChangedEvent(selected_indicators=['KAMA'],
                               indicator_params={'KAMA': {'timeperiod': 21}})
    e2 = IndicatorChangedEvent(selected_indicators=['KAMA'],
                               indicator_params={'KAMA': {'timeperiod': 10}})
    e3 = IndicatorChangedEvent(selected_indicators=['KAMA'],
                               indicator_params={'KAMA': {'timeperiod': 21}})
    assert e1.dedup_fingerprint != e2.dedup_fingerprint
    assert e1.dedup_fingerprint == e3.dedup_fingerprint
