#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R283 专项测试：健康检查反馈回路污染修复 + 空指标窗初始化同步 + 指标菜单桥接

覆盖：
A. 数据源熔断（真实导入 data_source_router）：
   - 健康检查成功不清零真实请求的连续失败计数（P0 根因：快速熔断计数被 30s
     健康检查永久清零 → 每次股票切换仍全量扫描不可用数据源）
   - 连续 3 次真实失败仍触发快速熔断（回归保护）
   - 熔断后 get_available_sources 的 can_execute 过滤剔除该源
   - 健康检查失败同样累积连续失败（探测失败 = 数据接口不可用）
B. middle_panel 菜单桥接：
   - _on_chart_region_indicator_selected 更新对应下拉框
   - 选择与当前相同指标时手动补触发渲染
C. UIMixin 指标菜单：
   - set_region_indicator_names 注入存储
   - _on_region_indicator_picked 发出 region_indicator_selected('indicator2', name)
"""
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# conftest.py 将 gui.widgets / core.ui.panels / matplotlib Qt backend 等注入 MagicMock。
# 本测试需真实导入相关模块，pop 后重建（参照 test_r270/test_r282 模式）。
_CONFTEST_MOCKS = [
    'gui.widgets',
    'core.ui',
    'core.ui.panels',
    'core.ui.panels.middle_panel',
    'core.ui.panels.base_panel',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_qt',
]
for _mod in _CONFTEST_MOCKS:
    sys.modules.pop(_mod, None)


# ==================== A. 数据源熔断（P0） ====================

def _make_router():
    """构造 DataSourceRouter 并手动注册 2 个数据源（不走 register_data_source，
    避免其自动启动 30s 健康检查线程污染测试环境）"""
    from core.data_source_router import DataSourceRouter

    router = DataSourceRouter(health_check_interval=3600)
    for sid in ('em', 'sina'):
        router.data_sources[sid] = SimpleNamespace()
        router.metrics[sid] = SimpleNamespace(
            weight=1.0, total_requests=0, successful_requests=0, failed_requests=0,
            last_request_time=None, avg_response_time_ms=0.0, health_score=1.0,
            success_rate=1.0,
        )
        # 手动创建熔断器（等同 register_data_source 的 circuit_breakers 分支）
        from core.data_source_router import CircuitBreaker
        if sid not in router.circuit_breakers:
            router.circuit_breakers[sid] = CircuitBreaker(
                sid, router.circuit_breaker_config)
    # 资产优先级 + 插件信息声明（供 _get_available_sources 过滤）
    from core.plugin_types import AssetType
    router.asset_priorities[AssetType.STOCK_A] = ['em', 'sina']
    for sid in ('em', 'sina'):
        router.data_sources[sid].get_plugin_info = lambda: SimpleNamespace(
            supported_asset_types=[AssetType.STOCK_A],
            supported_data_types=None,
        )
    return router


def test_health_check_success_does_not_clear_failures():
    """P0：健康检查成功（from_health_check=True）不清零真实请求的连续失败计数。

    修复前 record_request_result 成功分支无条件清零 _consecutive_failures，
    健康检查线程每 30s 一次"首页可达"成功探测将熔断计数永久清零，
    真实数据源故障后连续失败永远到不了阈值 3，每次股票切换全量扫描。
    """
    from core.data_source_router import CircuitBreakerState
    router = _make_router()

    # 2 次真实业务请求失败 → 连续失败计数 2
    router.record_request_result('em', False)
    router.record_request_result('em', False)
    assert router._consecutive_failures['em'] == 2

    # 健康检查成功（模拟 _health_check_worker 走 from_health_check=True）
    router.record_request_result('em', True, from_health_check=True)
    assert router._consecutive_failures['em'] == 2, \
        "健康检查成功不应清零真实请求的连续失败计数"

    # 第 3 次真实失败 → 仍触发快速熔断
    router.record_request_result('em', False)
    assert router.circuit_breakers['em'].state == CircuitBreakerState.OPEN, \
        "健康检查成功探测不应阻碍真实请求的快速熔断"


def test_health_check_failure_still_counts():
    """健康检查失败同样累积连续失败（探测失败 = 数据接口不可用，不区分来源）"""
    from core.data_source_router import CircuitBreakerState
    router = _make_router()

    for _ in range(3):
        router.record_request_result('em', False, from_health_check=True)
    assert router.circuit_breakers['em'].state == CircuitBreakerState.OPEN


def test_fast_fail_trips_after_three_failures():
    """回归保护：无健康检查干扰时连续 3 次失败触发快速熔断"""
    from core.data_source_router import CircuitBreakerState
    router = _make_router()

    for _ in range(3):
        router.record_request_result('em', False)
    assert router.circuit_breakers['em'].state == CircuitBreakerState.OPEN


def test_available_sources_filters_tripped_source():
    """熔断后 get_available_sources 的 can_execute 过滤剔除该源（不再全量扫描）"""
    from core.plugin_types import AssetType, DataType
    router = _make_router()

    for _ in range(3):
        router.record_request_result('em', False)
    assert router.circuit_breakers['em'].state.name == 'OPEN'

    req = SimpleNamespace(asset_type=AssetType.STOCK_A,
                          data_type=DataType.HISTORICAL_KLINE)
    avail = router.get_available_sources(req)
    assert 'em' not in avail, "已熔断数据源不应进入候选列表"
    assert 'sina' in avail, "健康数据源应保留"


def test_successful_request_clears_failures():
    """真实业务请求成功后清零连续失败计数（恢复语义不受影响）"""
    router = _make_router()
    router.record_request_result('em', False)
    router.record_request_result('em', False)
    assert router._consecutive_failures['em'] == 2
    router.record_request_result('em', True)  # 真实请求成功（非健康检查）
    assert router._consecutive_failures['em'] == 0


def test_health_check_success_does_not_close_half_open():
    """R283 盲区修复：健康检查成功不推进熔断状态机（HALF_OPEN 不恢复 CLOSED）

    修复前 record_request_result 成功分支无条件调 circuit_breaker.record_success()，
    HALF_OPEN 下 3 次成功将熔断器恢复 CLOSED（30s 探测周期 + 60s 恢复期 ≈ 90s 内
    "治愈"已熔断源）→ 健康检查反而导致不可用源被反复全量扫描。
    """
    from core.data_source_router import CircuitBreakerState
    router = _make_router()

    # 触发熔断（OPEN）
    for _ in range(3):
        router.record_request_result('em', False)
    breaker = router.circuit_breakers['em']
    assert breaker.state == CircuitBreakerState.OPEN

    # 模拟恢复期已过 → 下一次 can_execute 自动转 HALF_OPEN 放行
    breaker.last_failure_time = datetime.now() - timedelta(seconds=70)
    assert breaker.can_execute() is True
    assert breaker.state == CircuitBreakerState.HALF_OPEN

    # 健康检查成功 3 次（R283: 不应恢复 CLOSED）
    for _ in range(3):
        router.record_request_result('em', True, from_health_check=True)
    assert breaker.state == CircuitBreakerState.HALF_OPEN, \
        "健康检查成功不应将 HALF_OPEN 恢复为 CLOSED（否则熔断白做）"

    # 真实业务请求成功 → 恢复正常 CLOSED
    # 注：HALF_OPEN 下需累计 half_open_max_calls(3) 次真实成功才恢复 CLOSED
    # （健康检查成功不推进状态机，half_open_calls 仍为 0）
    for _ in range(3):
        router.record_request_result('em', True)
    assert breaker.state == CircuitBreakerState.CLOSED, \
        "真实业务请求成功累计达到 half_open_max_calls 才可恢复正常"


def test_timeout_marks_unavailable_and_cooldown_skips_connect():
    """P0: failover 超时即时熔断（不再等 3 次）+ 失败冷却（冷却期内不再真实 connect）"""
    import importlib
    import time
    from core.plugin_types import AssetType, DataType
    from core.data_source_router import CircuitBreakerState

    tet_mod = importlib.import_module('core.tet_data_pipeline')
    router = _make_router()

    # 注册 adapter：connect 阻塞 5s（> per_source_timeout 0.5s）→ 走 TimeoutError 分支
    adapter = MagicMock()
    adapter.plugin_id = 'em'
    adapter.is_connected.return_value = False

    def _slow_connect():
        time.sleep(5)
        return False

    adapter.connect.side_effect = _slow_connect
    adapter.get_plugin_info.return_value = SimpleNamespace(
        supported_asset_types=[AssetType.STOCK_A], supported_data_types=None)

    pipeline = tet_mod.TETDataPipeline(router)
    pipeline._per_source_timeout = 0.5  # 缩短单源超时加速测试
    pipeline._adapters['em'] = adapter

    req = SimpleNamespace(asset_type=AssetType.STOCK_A,
                          data_type=DataType.HISTORICAL_KLINE)
    # provider=None：tet_data_pipeline.extract_data_with_failover L555
    # 需访问 original_query.provider（未指定提供商时走 get_available_sources 全量路由）
    original_query = SimpleNamespace(provider=None)

    start = time.time()
    df, _, _ = pipeline.extract_data_with_failover(req, original_query)
    elapsed = time.time() - start
    assert df.empty
    assert router.circuit_breakers['em'].state == CircuitBreakerState.OPEN, \
        "超时=确定性故障应即时熔断（mark_unavailable），不再等 3 次连续失败"
    assert elapsed < 3.0, f"单源超时应被 per_source_timeout 截断，实际耗时 {elapsed:.1f}s"

    # 冷却期内再次 failover：已熔断源被 can_execute 过滤 + 冷却拦截，不再真实 connect
    pipeline.extract_data_with_failover(req, original_query)
    assert adapter.connect.call_count == 1, "冷却期内不应再次真实 connect（切换股票快速失败）"


# ==================== B. middle_panel 菜单桥接 ====================

def _load_middle_panel_module():
    import importlib
    return importlib.import_module('core.ui.panels.middle_panel')


def test_on_chart_region_indicator_selected_updates_combo():
    """菜单选指标（字符串兼容） → 更新 indicator1_combo 值（值变化时由 currentTextChanged 链路渲染）"""
    mod = _load_middle_panel_module()

    combo = SimpleNamespace()
    combo._text = 'MACD'
    combo.setCurrentText = lambda t: setattr(combo, '_text', t)
    combo.currentText = lambda: combo._text
    panel = SimpleNamespace(
        get_widget=lambda k: combo if k == 'indicator1_combo' else None,
        _on_region_indicator_changed=MagicMock(),
    )

    mod.MiddlePanel._on_chart_region_indicator_selected(panel, 'indicator1', 'KDJ')
    assert combo._text == 'KDJ', "indicator1_combo 应更新为 KDJ"
    # 值发生变化：真实 combo 的 currentTextChanged 会自动触发渲染（此处不手动补触发）
    panel._on_region_indicator_changed.assert_not_called()


def test_on_chart_region_indicator_selected_same_value_manual_trigger():
    """选择与当前相同的指标（或'无'）时 currentTextChanged 不触发 → 手动补触发渲染"""
    mod = _load_middle_panel_module()

    combo = SimpleNamespace()
    combo._text = 'MACD'
    combo.setCurrentText = lambda t: setattr(combo, '_text', t)
    combo.currentText = lambda: combo._text
    panel = SimpleNamespace(
        get_widget=lambda k: combo if k == 'indicator1_combo' else None,
        _on_region_indicator_changed=MagicMock(),
    )

    mod.MiddlePanel._on_chart_region_indicator_selected(panel, 'indicator1', 'MACD')
    panel._on_region_indicator_changed.assert_called_once_with('MACD')


def test_on_chart_region_indicator_selected_multi_select():
    """R283+: 菜单多选指标 → 直接重组多指标列表渲染（region 全部 indicator1）"""
    mod = _load_middle_panel_module()

    chart_widget = SimpleNamespace(on_indicator_selected=MagicMock())
    canvas = SimpleNamespace(chart_widget=chart_widget)
    panel = SimpleNamespace(
        _BUILTIN_INDICATORS=mod.MiddlePanel._BUILTIN_INDICATORS,
        _TALIB_DEFAULT_PARAMS=mod.MiddlePanel._TALIB_DEFAULT_PARAMS,
        _indicator_region_map={},
        _indicator_user_params={},
    )
    panel.get_widget = lambda k: {'chart_canvas': canvas}.get(k)

    mod.MiddlePanel._on_chart_region_indicator_selected(panel, 'indicator1', ['MACD', 'RSI'])

    indicator_list = chart_widget.on_indicator_selected.call_args.args[0]
    names = [(ind['name'], ind['region'], ind['group']) for ind in indicator_list]
    assert ('MACD', 'indicator1', 'builtin') in names, "MACD 应归属 indicator1 区"
    assert ('RSI', 'indicator1', 'builtin') in names, "RSI 应归属 indicator1 区"
    assert panel._indicator_region_map == {'MACD': 'indicator1', 'RSI': 'indicator1'}, \
        "多选指标应全部记录区域归属"


def test_on_chart_region_indicator_selected_empty_clears():
    """R283+: 菜单全部取消勾选（空列表） → 清空指标区与区域归属"""
    mod = _load_middle_panel_module()

    chart_widget = SimpleNamespace(on_indicator_selected=MagicMock())
    canvas = SimpleNamespace(chart_widget=chart_widget)
    panel = SimpleNamespace(
        _BUILTIN_INDICATORS=mod.MiddlePanel._BUILTIN_INDICATORS,
        _TALIB_DEFAULT_PARAMS=mod.MiddlePanel._TALIB_DEFAULT_PARAMS,
        _indicator_region_map={'MACD': 'indicator1'},
        _indicator_user_params={},
    )
    panel.get_widget = lambda k: {'chart_canvas': canvas}.get(k)

    mod.MiddlePanel._on_chart_region_indicator_selected(panel, 'indicator1', [])

    indicator_list = chart_widget.on_indicator_selected.call_args.args[0]
    assert indicator_list == [], "空选择应清空全部指标"
    assert panel._indicator_region_map == {}, "清空后应移除历史归属"


# ==================== C. UIMixin 指标菜单 ====================

def _load_ui_mixin():
    import importlib
    return importlib.import_module('gui.widgets.chart_mixins.ui_mixin')


def test_set_region_indicator_names_stores():
    """middle_panel 注入的指标名称列表被存储，供菜单展开使用"""
    ui = _load_ui_mixin()
    chart = SimpleNamespace()
    ui.UIMixin.set_region_indicator_names(chart, ['无', 'MACD', 'RSI'])
    assert chart._region_indicator_names == ['无', 'MACD', 'RSI']


def test_region_indicator_picked_emits_signal():
    """菜单单选（字符串兼容） → 发出 region_indicator_selected('indicator1', ['KDJ']) 桥接信号"""
    ui = _load_ui_mixin()
    signal = MagicMock()
    chart = SimpleNamespace(region_indicator_selected=signal)
    ui.UIMixin._on_region_indicator_picked(chart, 'KDJ')
    signal.emit.assert_called_once_with('indicator1', ['KDJ'])


def test_region_indicator_picked_emits_list():
    """R283+: 菜单多选（列表） → 发出 region_indicator_selected('indicator1', [names])"""
    ui = _load_ui_mixin()
    signal = MagicMock()
    chart = SimpleNamespace(region_indicator_selected=signal)
    ui.UIMixin._on_region_indicator_picked(chart, ['MACD', 'RSI'])
    signal.emit.assert_called_once_with('indicator1', ['MACD', 'RSI'])


def test_load_region_indicator_names_fallback():
    """R283+: 无 middle_panel 注入时兜底拉取——与左侧技术面板同源（BUILTIN + TA-Lib）"""
    ui = _load_ui_mixin()
    chart = SimpleNamespace()
    names = ui.UIMixin._load_region_indicator_names(chart)
    assert names[0] == '无', "列表应以'无'开头"
    assert 'MACD' in names and 'MA' in names, "内置指标应出现在兜底列表"
    assert len(names) >= 6, f"兜底列表过短: {len(names)}"


def test_load_region_indicator_names_uses_injected():
    """middle_panel 已注入时直接复用注入列表（不重复拉取）"""
    ui = _load_ui_mixin()
    chart = SimpleNamespace(_region_indicator_names=['无', 'KAMA'])
    names = ui.UIMixin._load_region_indicator_names(chart)
    assert names == ['无', 'KAMA'], "应复用注入列表"


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v', '--tb=short']))
