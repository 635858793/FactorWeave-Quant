#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R264: 指标列表动态化 + 空数据自动重拉测试（TDD）

覆盖：
1. get_talib_real_indicator_list 动态枚举（TA-Lib 支持哪些展示哪些）
2. 动态列表 ∩ TALIB_OUTPUT_MAP 全覆盖（列表中的每个指标计算端都能算）
3. 新增统计/量能指标全量计算验证（AD/TRANGE/LINEARREG*/STDDEV/TSF/VAR）
4. calculate_indicator 对未同步映射的 TA-Lib 函数动态单输出兜底
5. indicator_mixin._on_indicator_changed 空数据时自动重新拉取K线
"""

import sys
import os
import unittest
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.indicators.indicators_algorithm import get_talib_real_indicator_list
from core.unified_indicator_service import TALIB_OUTPUT_MAP


def _make_kdata(n=120) -> pd.DataFrame:
    """构造 120 根 OHLCV K线"""
    return pd.DataFrame({
        'datetime': pd.date_range('2026-01-01', periods=n, freq='D'),
        'open': np.linspace(10.0, 12.0, n),
        'high': np.linspace(10.5, 12.5, n),
        'low': np.linspace(9.5, 11.5, n),
        'close': np.linspace(10.0, 12.0, n),
        'volume': np.full(n, 10000.0),
        'amount': np.linspace(100000.0, 120000.0, n),
    })


def _make_svc():
    """构造轻量 UnifiedIndicatorService（__new__ 绕过 __init__，mock DB 依赖）
    mock get_indicator 返回 None → calculate_indicator 强制走 TA-Lib 直算兜底链路
    （本测试聚焦兜底计算正确性，DB 记录链路由既有 test_unified_indicator_service 覆盖）
    """
    from core.unified_indicator_service import UnifiedIndicatorService
    svc = UnifiedIndicatorService.__new__(UnifiedIndicatorService)
    svc._indicator_plugins = {}
    svc._cache_enabled = False
    svc._calculation_cache = {}
    svc._indicators_cache = {}
    svc.conn = None
    svc.get_indicator = MagicMock(return_value=None)
    svc.get_pattern = MagicMock(return_value=None)
    return svc


class TestDynamicIndicatorList(unittest.TestCase):
    """动态指标列表测试"""

    def test_list_is_dynamic_and_excludes_non_chart(self):
        names = get_talib_real_indicator_list()
        self.assertGreater(len(names), 46)  # 至少比原硬编码 46 个多
        self.assertLessEqual(len(names), 97)  # 非 CDL 全量为 97
        # 不含形态识别（CDL*）
        self.assertTrue(all(not n.startswith('CDL') for n in names))
        # 不含数学运算/变换/周期/价格变换/MAVP
        for excluded in ['ADD', 'LN', 'SQRT', 'HT_DCPERIOD', 'AVGPRICE', 'MAVP', 'BETA', 'CORREL']:
            self.assertNotIn(excluded, names, f"{excluded} 不应出现在图表指标列表")
        # 原有核心指标保留
        for core in ['MA', 'SMA', 'MACD', 'RSI', 'STOCH', 'BBANDS', 'MIDPRICE',
                     'SAR', 'TRIX', 'ATR', 'CCI', 'ADX', 'OBV']:
            self.assertIn(core, names, f"{core} 应保留在图表指标列表")
        # 新增统计/量能指标进入列表
        for added in ['LINEARREG', 'STDDEV', 'TSF', 'VAR', 'AD', 'TRANGE']:
            self.assertIn(added, names, f"{added} 应进入动态列表")

    def test_full_coverage_talib_output_map(self):
        """动态列表 ∩ TALIB_OUTPUT_MAP：列表中的每个指标计算端都有输出映射（能选能算）"""
        names = get_talib_real_indicator_list()
        missing = [n for n in names if n not in TALIB_OUTPUT_MAP]
        self.assertEqual(missing, [], f"以下指标在列表中但 TALIB_OUTPUT_MAP 缺失: {missing}")


class TestNewIndicatorCalculation(unittest.TestCase):
    """新增指标计算验证（R264 统计/量能/波动类）"""

    def test_stat_indicators_calculate(self):
        """统计类单输入指标可计算（线性回归/标准差/TSF/VAR）"""
        from core.indicators.indicators_algorithm import get_talib_real_indicator_list
        svc = _make_svc()
        df = _make_kdata()

        stat_indicators = [n for n in get_talib_real_indicator_list()
                           if n in ('LINEARREG', 'LINEARREG_ANGLE', 'LINEARREG_INTERCEPT',
                                    'LINEARREG_SLOPE', 'STDDEV', 'TSF', 'VAR')]
        for name in stat_indicators:
            result = svc.calculate_indicator(name, df.copy(), {'timeperiod': 14})
            self.assertIn(name, result.columns, f"{name} 计算结果应含 {name} 列")
            self.assertGreater(result[name].notna().sum(), 0, f"{name} 应有非空值")

    def test_ad_and_trange_calculate(self):
        """AD(high,low,close,volume) / TRANGE(high,low) 多输入指标可计算"""
        svc = _make_svc()
        df = _make_kdata()

        result = svc.calculate_indicator('AD', df.copy())
        self.assertIn('AD', result.columns)
        self.assertGreater(result['AD'].notna().sum(), 0)

        result2 = svc.calculate_indicator('TRANGE', df.copy())  # TRANGE 无参数
        self.assertIn('TRANGE', result2.columns)
        self.assertGreater(result2['TRANGE'].notna().sum(), 0)

    def test_all_dynamic_list_calculable(self):
        """动态列表全量可计算（能选能算）"""
        from core.indicators.indicators_algorithm import get_talib_real_indicator_list
        svc = _make_svc()
        df = _make_kdata()
        names = get_talib_real_indicator_list()
        failed = []
        for name in names:
            try:
                result = svc.calculate_indicator(name, df.copy())
                # 多输出指标（STOCH/MACD 等）输出列可能不完全一致，只要求调用不抛且返回含任一映射列
                mapped = TALIB_OUTPUT_MAP.get(name, [name])
                if not any(col in result.columns for col in mapped):
                    failed.append(f"{name}(缺输出列)")
            except Exception as e:
                failed.append(f"{name}(异常:{e})")
        self.assertEqual(failed, [], f"以下指标计算失败: {failed}")


class TestDynamicFallback(unittest.TestCase):
    """calculate_indicator 对未同步映射 TA-Lib 函数的动态单输出兜底"""

    def test_unmapped_function_dynamic_fallback(self):
        """不在 TALIB_OUTPUT_MAP 但 TA-Lib 存在的单输出函数可动态计算"""
        svc = _make_svc()
        df = _make_kdata()
        # 找 TA-Lib 存在但映射缺失的单输出函数（MAX 为 Math Operator，未在列表中）
        result = svc.calculate_indicator('MAX', df.copy(), {'timeperiod': 5})
        self.assertIn('MAX', result.columns, "未映射函数应动态兜底为单输出列")
        self.assertGreater(result['MAX'].notna().sum(), 0)


class TestAutoReloadOnEmptyKdata(unittest.TestCase):
    """current_kdata 为空时自动重新拉取K线"""

    def _make_widget(self):
        # gui/widgets 非包目录，通过文件路径加载 IndicatorMixin
        import importlib.util
        mixin_path = os.path.join(os.path.dirname(__file__), '..', 'gui', 'widgets',
                                  'chart_mixins', 'indicator_mixin.py')
        spec = importlib.util.spec_from_file_location('indicator_mixin_mod', mixin_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        IndicatorMixin = mod.IndicatorMixin
        widget = IndicatorMixin.__new__(IndicatorMixin)
        widget.active_indicators = []
        widget.current_kdata = None
        widget._current_stock_code = '300973'
        widget.load_data = MagicMock()
        widget.update_chart = MagicMock()
        return widget

    def test_reload_when_kdata_none(self):
        widget = self._make_widget()
        widget._on_indicator_changed(['MA'])
        widget.load_data.assert_called_once_with('300973', force_reload=True)

    def test_reload_when_kdata_empty_df(self):
        widget = self._make_widget()
        widget.current_kdata = pd.DataFrame()
        widget._on_indicator_changed(['MA'])
        widget.load_data.assert_called_once_with('300973', force_reload=True)

    def test_use_existing_kdata_when_present(self):
        widget = self._make_widget()
        widget.current_kdata = _make_kdata(30)
        widget._on_indicator_changed(['MA'])
        widget.load_data.assert_not_called()
        widget.update_chart.assert_called_once()
        self.assertTrue(widget.update_chart.call_args[0][0]['kdata'].equals(widget.current_kdata))

    def test_no_stock_code_no_reload(self):
        widget = self._make_widget()
        widget._current_stock_code = None
        widget.current_kdata = None
        widget._on_indicator_changed(['MA'])
        widget.load_data.assert_not_called()


if __name__ == '__main__':
    unittest.main()
