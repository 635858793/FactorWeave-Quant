#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R252 回归测试: 分析tab域修复 G1-G6 (代理B)

覆盖问题:
- G1: pattern_tab_pro 一键分析/自动扫描结果被 _filter_patterns 丢弃
      (success_rate 缺失时被 continue 掉); _detect_patterns 未显式兜底 success_rate
- G2: wave_tab_pro 无模块级 logger -> 现场重算异常路径 :797/:806 NameError
- G3: base_tab.run_analysis_async 调用不存在的 run_button_analysis_async -> AttributeError
- G4: 形态统计面板数据结构失配 (avg_confidence/pattern_types/high_confidence_count)
      + PatternAnalysisTabPro._calculate_statistics 下标访问 KeyError
- G5: wave_tab_pro 综合分析结果不回流实例属性 -> 波浪预测/导出空数据
- G6: wave_tab 未连接 error_occurred -> 分析异常静默

测试策略 (参考 tests/test_r251_right_panel_architecture.py):
- 保留真实 PyQt5 (无头 offscreen), 仅 mock 重/崩溃依赖链
  (analysis.pattern_recognition / pattern_manager / db / core.events /
   core.services.backtest_result_manager / chart_mixins.signal_mixin /
   utils.config_manager / utils.trace_context / core.performance)
- 预注册轻量 analysis_tabs 包, importlib 从文件加载真实模块
- 全部以"未绑定方法 + 假 self"方式调用被测方法, 不做真实 QWidget 实例化
- 文件末尾恢复被 mock 的 sys.modules 条目, 避免污染其他测试文件
"""
import os
import sys
import types
import inspect
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
# mock 掉重/崩溃依赖链 (真实 PyQt5 / numpy / pandas / scipy / loguru 保留)
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


def _load_module(module_name, rel_path):
    """从文件加载真实模块 (绕过 sys.modules 中已注册的 mock)"""
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 依次加载: base_tab -> pattern_tab_pro / wave_tab_pro -> wave_tab
base_tab = _load_module('gui.widgets.analysis_tabs.base_tab',
                        'gui/widgets/analysis_tabs/base_tab.py')
pattern_tab_pro = _load_module('gui.widgets.analysis_tabs.pattern_tab_pro',
                               'gui/widgets/analysis_tabs/pattern_tab_pro.py')
wave_tab_pro = _load_module('gui.widgets.analysis_tabs.wave_tab_pro',
                            'gui/widgets/analysis_tabs/wave_tab_pro.py')
wave_tab = _load_module('gui.widgets.analysis_tabs.wave_tab',
                        'gui/widgets/analysis_tabs/wave_tab.py')

BaseAnalysisTab = base_tab.BaseAnalysisTab
AnalysisThread = pattern_tab_pro.AnalysisThread
PatternAnalysisTabPro = pattern_tab_pro.PatternAnalysisTabPro
WaveAnalysisTabPro = wave_tab_pro.WaveAnalysisTabPro
WaveAnalysisTab = wave_tab.WaveAnalysisTab

# 恢复被 mock 的 sys.modules 条目 (保留已加载的真实模块对象)
_restore_sys_modules()


# ---------------------------------------------------------------------------
# G1: 形态一键分析/自动扫描 success_rate 字段
# ---------------------------------------------------------------------------
def test_g1_filter_patterns_keeps_pattern_without_success_rate():
    """无 success_rate 字段的形态不应被 _filter_patterns 丢弃 (仅按置信度过滤)"""
    fake_self = MagicMock()
    fake_self.filters = {
        'min_confidence': 0.0, 'max_confidence': 1.0,
        'min_success_rate': 0.0, 'max_success_rate': 1.0,
        'risk_level': '全部',
    }
    patterns = [{'pattern_name': '锤子线', 'confidence': 0.8}]
    result = AnalysisThread._filter_patterns(fake_self, patterns)
    assert len(result) == 1
    assert result[0]['pattern_name'] == '锤子线'


def test_g1_filter_patterns_keeps_pattern_with_none_success_rate():
    """success_rate 显式为 None 的形态同样不应被丢弃"""
    fake_self = MagicMock()
    fake_self.filters = {
        'min_confidence': 0.0, 'max_confidence': 1.0,
        'min_success_rate': 0.0, 'max_success_rate': 1.0,
        'risk_level': '全部',
    }
    patterns = [{'pattern_name': '三白兵', 'confidence': 0.75,
                 'success_rate': None}]
    result = AnalysisThread._filter_patterns(fake_self, patterns)
    assert len(result) == 1


def test_g1_filter_patterns_still_filters_bad_success_rate():
    """成功率超出范围时仍应被过滤 (回归: 宽容处理不改变既有过滤语义)"""
    fake_self = MagicMock()
    fake_self.filters = {
        'min_confidence': 0.0, 'max_confidence': 1.0,
        'min_success_rate': 0.8, 'max_success_rate': 1.0,
        'risk_level': '全部',
    }
    patterns = [{'pattern_name': 'X', 'confidence': 0.9, 'success_rate': 0.5}]
    result = AnalysisThread._filter_patterns(fake_self, patterns)
    assert result == []


def test_g1_detect_patterns_adds_success_rate_default():
    """_detect_patterns 输出必须包含 success_rate/risk_level 兜底字段,
    且保留识别器显式给出的 success_rate"""
    rec = MagicMock()
    rec.identify_patterns.return_value = [
        {'pattern_name': '锤子线', 'signal': 'buy', 'confidence': 0.85,
         'price': 10.0},
        {'pattern_name': '三白兵', 'signal': 'buy', 'confidence': 0.9,
         'price': 11.0, 'success_rate': 0.92},
    ]
    pat_mod = _make_mock_module(
        'analysis.pattern_recognition',
        EnhancedPatternRecognizer=MagicMock(return_value=rec))
    saved = sys.modules.get('analysis.pattern_recognition')
    sys.modules['analysis.pattern_recognition'] = pat_mod
    try:
        fake_self = MagicMock()
        fake_self.kdata = pd.DataFrame({'close': list(range(120))})
        fake_self.selected_patterns = []
        fake_self.sensitivity = 0.7
        fake_self._validate_and_clean_pattern = (
            lambda p: AnalysisThread._validate_and_clean_pattern(fake_self, p))
        result = AnalysisThread._detect_patterns(fake_self)
    finally:
        if saved is not None:
            sys.modules['analysis.pattern_recognition'] = saved
        else:
            sys.modules.pop('analysis.pattern_recognition', None)

    assert result, "应检测到形态"
    by_name = {p['pattern_name']: p for p in result}
    assert by_name['锤子线']['success_rate'] == 0.7    # 缺失时兜底 0.7
    assert by_name['锤子线']['risk_level'] == 'medium'  # 缺失时兜底 medium
    assert by_name['三白兵']['success_rate'] == 0.92   # 保留显式值


# ---------------------------------------------------------------------------
# G2: wave_tab_pro 模块级 logger
# ---------------------------------------------------------------------------
def test_g2_wave_tab_pro_has_module_logger():
    """wave_tab_pro 模块应具有可用的模块级 logger"""
    assert hasattr(wave_tab_pro, 'logger')
    wave_tab_pro.logger.debug("R252-G2 logger 可用")


def test_g2_wave_tab_pro_logger_no_nameerror_on_recalc_failure():
    """现场计算斐波那契/江恩水平失败时不得抛 NameError (logger 缺失)"""
    dates = pd.date_range('2026-01-01', periods=30)
    kdata = pd.DataFrame({'close': [10.0 + i * 0.1 for i in range(30)]},
                         index=dates)
    fake_self = MagicMock()
    fake_self.current_kdata = kdata
    fake_self.fibonacci_levels = []
    fake_self.gann_levels = []
    fake_self.elliott_waves = []
    fake_self._calculate_fibonacci_levels.side_effect = Exception('重算失败')
    fake_self._calculate_gann_levels.side_effect = Exception('重算失败')

    try:
        pred = WaveAnalysisTabPro._generate_wave_prediction(fake_self)
    except NameError as e:
        pytest.fail(f"现场重算异常路径抛出 NameError: {e}")

    assert isinstance(pred, str)
    assert '波浪预测报告' in pred


# ---------------------------------------------------------------------------
# G3: base_tab.run_analysis_async 防御性调用
# ---------------------------------------------------------------------------
class _NoAsyncParent:
    """无 run_button_analysis_async 方法的父组件 (复现 AttributeError)"""
    pass


def test_g3_run_analysis_async_no_attrerror_without_parent_async():
    """parent_widget 无 run_button_analysis_async 时不得抛 AttributeError,
    应回退到同步执行"""
    fake_self = MagicMock()
    fake_self.is_initialized = True
    fake_self.error_occurred = MagicMock()
    fake_self.analysis_completed = MagicMock()
    fake_self.parent_widget = _NoAsyncParent()

    calls = []

    def analysis_func(*args, **kwargs):
        calls.append(1)
        return {'ok': True}

    result = BaseAnalysisTab.run_analysis_async(fake_self, analysis_func)
    assert result == {'ok': True}
    assert calls == [1]
    fake_self.analysis_completed.emit.assert_called_once_with({'ok': True})


def test_g3_run_analysis_async_delegates_when_parent_has_method():
    """parent_widget 提供 run_button_analysis_async 时仍应委托 (回归)"""
    fake_self = MagicMock()
    fake_self.is_initialized = True
    fake_self.error_occurred = MagicMock()
    fake_self.analysis_completed = MagicMock()
    parent = MagicMock()
    parent.run_button_analysis_async.return_value = 'delegated'
    fake_self.parent_widget = parent

    result = BaseAnalysisTab.run_analysis_async(
        fake_self, lambda: {'x': 1})
    assert result == 'delegated'
    parent.run_button_analysis_async.assert_called_once()


# ---------------------------------------------------------------------------
# G4: 形态统计面板数据结构失配
# ---------------------------------------------------------------------------
def test_g4_analysis_thread_statistics_unified_keys():
    """AnalysisThread._calculate_statistics 应输出
    avg_confidence/pattern_types/high_confidence_count 顶层键"""
    patterns = [
        {'pattern_name': '锤子线', 'confidence': 0.9, 'signal': 'buy'},
        {'pattern_name': '三白兵', 'confidence': 0.6, 'signal': 'sell'},
        {'pattern_name': '锤子线', 'confidence': 0.3, 'signal': 'neutral'},
    ]
    stats = AnalysisThread._calculate_statistics(None, patterns)
    assert 'avg_confidence' in stats
    assert 'pattern_types' in stats
    assert 'high_confidence_count' in stats
    assert stats['avg_confidence'] == pytest.approx((0.9 + 0.6 + 0.3) / 3)
    assert stats['high_confidence_count'] == 1
    assert stats['pattern_types'] == {'锤子线': 2, '三白兵': 1}
    # 兼容旧键
    assert stats['confidence_stats']['average'] == stats['avg_confidence']
    assert stats['pattern_distribution'] == stats['pattern_types']


def test_g4_tab_statistics_defensive_get_and_unified_keys():
    """PatternAnalysisTabPro._calculate_statistics 对缺失
    success_rate/risk_level/category 应防御式访问并输出统一键"""
    patterns = [
        {'pattern_name': 'X', 'confidence': 0.85, 'signal': 'buy'},
        {'pattern_name': 'Y', 'confidence': 0.4, 'signal': 'neutral'},
    ]  # 故意缺失 success_rate / risk_level / category
    stats = PatternAnalysisTabPro._calculate_statistics(None, patterns)
    assert 'avg_confidence' in stats
    assert 'pattern_types' in stats
    assert 'high_confidence_count' in stats
    assert stats['avg_confidence'] == pytest.approx(0.625)
    assert stats['high_confidence_count'] == 1
    assert stats['pattern_types'] == {'X': 1, 'Y': 1}
    assert 'risk_distribution' in stats
    assert 'category_distribution' in stats


def test_g4_statistics_display_consumes_unified_keys():
    """_update_statistics_display 应能消费统一键名的统计 dict (回归)"""
    fake_self = MagicMock()
    stats_label = MagicMock()
    fake_self.stats_label = stats_label
    stats = {
        'total_patterns': 3,
        'avg_confidence': 0.7,
        'high_confidence_count': 1,
        'pattern_types': {'锤子线': 2, '三白兵': 1},
    }
    PatternAnalysisTabPro._update_statistics_display(fake_self, stats)
    text = stats_label.setText.call_args[0][0]
    assert '平均置信度: 70.00%' in text
    assert '高置信度: 1' in text
    assert '锤子线' in text


# ---------------------------------------------------------------------------
# G5: wave_tab_pro 综合分析结果回流实例属性
# ---------------------------------------------------------------------------
def test_g5_comprehensive_analysis_writes_back_instance_attrs():
    """_comprehensive_analysis_async 计算结果应写回
    self.elliott_waves/self.gann_levels/self.fibonacci_levels"""
    fake_self = MagicMock()
    fake_self.elliott_cb.isChecked.return_value = True
    fake_self.gann_cb.isChecked.return_value = True
    fake_self.fibonacci_cb.isChecked.return_value = False
    fake_self._detect_elliott_waves.return_value = [
        {'wave': 1, 'type': '推动浪'}]
    fake_self._calculate_gann_levels.return_value = [{'price': 10.5}]
    fake_self._calculate_fibonacci_levels.return_value = [{'price': 9.0}]
    fake_self._generate_comprehensive_report = MagicMock(
        return_value='综合报告')

    results = WaveAnalysisTabPro._comprehensive_analysis_async(fake_self)

    assert results.get('elliott_waves') == [{'wave': 1, 'type': '推动浪'}]
    assert fake_self.elliott_waves == [{'wave': 1, 'type': '推动浪'}]
    assert fake_self.gann_levels == [{'price': 10.5}]
    assert fake_self.fibonacci_levels == []  # 未勾选 → 空列表


def test_g5_wave_prediction_uses_instance_attrs():
    """_generate_wave_prediction 应使用已回流的实例属性 (回归)"""
    dates = pd.date_range('2026-01-01', periods=30)
    kdata = pd.DataFrame({'close': [10.0 + i * 0.1 for i in range(30)]},
                         index=dates)
    fake_self = MagicMock()
    fake_self.current_kdata = kdata
    fake_self.fibonacci_levels = [{'ratio': 0.618, 'price': 12.0,
                                   'type': '阻力'}]
    fake_self.gann_levels = [{'price': 8.0, 'type': '支撑'}]
    fake_self.elliott_waves = [{'wave': 1, 'type': '推动浪',
                                'confidence': 0.8, 'status': '确认'}]

    pred = WaveAnalysisTabPro._generate_wave_prediction(fake_self)
    assert '未检测到波浪结构' not in pred
    assert '12.00' in pred  # 斐波那契阻力位来自实例属性
    assert '8.00' in pred   # 江恩支撑位


# ---------------------------------------------------------------------------
# G6: wave_tab 连接 error_occurred
# ---------------------------------------------------------------------------
def test_g6_wave_tab_connects_error_occurred():
    """WaveAnalysisTab.__init__ 应连接 error_occurred, 避免分析异常静默
    (信号连接位于重型 QWidget 初始化中, 采用源码级断言, 确定性验证)"""
    src = inspect.getsource(WaveAnalysisTab.__init__)
    assert 'error_occurred.connect' in src
