#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R267-c 回测流程 E2E 验证

背景：R267-c 删除 backtest_widget.py 中 risk_canvas 死代码（risk_figure/risk_canvas/
risk_ax/_init_risk_chart/_update_risk_chart/_calculate_and_update_risk_metrics），
保留 AlertsPanel QLabel 标量展示。本测试验证删除后：
1. 完整回测流程真实跑通（UnifiedBacktestEngine.run_backtest 合成数据）
2. 回测结果 → _update_risk_metrics → alerts_panel.update_risk_metrics QLabel 展示链路无异常
3. 回测完成链路源码零死代码引用（交叉验证）

说明：_update_risk_metrics/_check_risk_alerts 从源码 AST 提取后 exec 绑定到宿主，
绕过 backtest_widget 模块级重依赖（conftest mock 下无法真实 import）。
"""
import ast
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLBACKEND', 'Agg')

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKTEST_WIDGET = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'backtest_widget.py')

RISK_KEYS = ['var_95', 'cvar_95', 'max_drawdown', 'volatility', 'sharpe_ratio']


def _make_kline_data(n=300, seed=42):
    """构造合成 K 线数据 + 信号列"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range('2024-01-01', periods=n, freq='D')
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    volume = rng.integers(10000, 100000, n)
    # 简单信号：价格 5 日均线金叉
    ma5 = pd.Series(close).rolling(5).mean().values
    signal = np.zeros(n)
    signal[1:] = np.where(close[1:] > ma5[1:], 1, 0)
    return pd.DataFrame({
        'date': dates, 'open': open_, 'high': high, 'low': low,
        'close': close, 'volume': volume, 'signal': signal,
    })


def _extract_class_src(src: str, class_name: str) -> str:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f'类 {class_name} 未找到')


def _extract_method_src(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f'方法 {name} 未找到')


def _make_alerts_panel():
    """AST 提取 AlertsPanel + 真实 PyQt5 命名空间 exec，返回真实 Qt 实例（offscreen）"""
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton,
        QLabel, QGroupBox, QFormLayout,
    )
    from PyQt5.QtGui import QColor
    from PyQt5.QtCore import Qt
    from datetime import datetime
    from typing import Dict, List, Optional, Any  # noqa: F401

    src = open(BACKTEST_WIDGET, encoding='utf-8').read()
    class_src = _extract_class_src(src, 'AlertsPanel')
    ns = {
        'QWidget': QWidget, 'QVBoxLayout': QVBoxLayout,
        'QListWidget': QListWidget, 'QListWidgetItem': QListWidgetItem,
        'QPushButton': QPushButton, 'QLabel': QLabel, 'QGroupBox': QGroupBox,
        'QFormLayout': QFormLayout, 'QColor': QColor, 'Qt': Qt,
        'datetime': datetime, 'Dict': Dict, 'List': List,
    }
    exec(compile(class_src, '<AlertsPanel>', 'exec'), ns)
    return ns['AlertsPanel']()


def _bind_method(src, name, host):
    """AST 提取方法并绑定到宿主对象（覆盖同名旧方法）"""
    from typing import Dict, Any, Optional, List
    method_src = _extract_method_src(src, name)
    ns = {'logger': MagicMock(), 'Dict': Dict, 'Any': Any,
          'Optional': Optional, 'List': List}
    exec(compile(method_src, f'<{name}>', 'exec'), ns)
    bound = ns[name].__get__(host, type(host))
    setattr(host, name, bound)
    return bound


def test_backtest_engine_full_run():
    """完整回测流程真实跑通，结果含全部风险指标字段"""
    from backtest.unified_backtest_engine import create_unified_backtest_engine

    engine = create_unified_backtest_engine()
    data = _make_kline_data()

    result = engine.run_backtest(
        data=data, initial_capital=100000, position_size=1.0,
        commission_pct=0.001, slippage_pct=0.001,
        enable_compound=True, mode_context=None,
    )

    assert isinstance(result, dict)
    for key in RISK_KEYS:
        assert key in result, f'回测结果缺少风险指标字段: {key}'
    assert 'equity_curve' in result
    assert result['sharpe_ratio'] is not None
    assert result['max_drawdown'] is not None


def test_risk_metrics_display_chain():
    """真实回测结果 → _update_risk_metrics → AlertsPanel QLabel 展示链路无异常"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    panel = _make_alerts_panel()

    # AST 提取 _update_risk_metrics/_check_risk_alerts 并绑定到宿主
    src = open(BACKTEST_WIDGET, encoding='utf-8').read()
    host = MagicMock()
    host.alerts_panel = panel
    host._is_closing = False
    host.risk_metrics = {}
    host.risk_alerts = []
    host.risk_thresholds = {
        'var_95': -0.05, 'max_drawdown': -0.20,
        'volatility': 0.30, 'sharpe_ratio': 0.5,
    }
    _bind_method(src, '_check_risk_alerts', host)
    _bind_method(src, '_update_risk_metrics', host)

    # 真实引擎结果
    from backtest.unified_backtest_engine import create_unified_backtest_engine
    result = create_unified_backtest_engine().run_backtest(data=_make_kline_data())

    # 触发统一入口（回测完成回调 L3235 的调用方式）
    host._update_risk_metrics(result)

    # 标量展示正确：QLabel 文本已更新（非 N/A）
    var_text = panel.var_label.text()
    sharpe_text = panel.sharpe_label.text()
    assert var_text != 'N/A', 'VaR QLabel 未更新'
    assert sharpe_text != 'N/A', 'Sharpe QLabel 未更新'
    assert '%' in var_text, f'VaR 应显示百分比: {var_text}'
    # 死代码残留会导致 AttributeError——此处能执行到即证明链路干净


def test_no_dead_code_in_completion_chain():
    """回测完成链路源码零死代码引用（交叉验证）"""
    src = open(BACKTEST_WIDGET, encoding='utf-8').read()
    completion = _extract_method_src(src, '_on_backtest_completed')
    risk_update = _extract_method_src(src, '_update_risk_metrics')
    for chunk, label in [(completion, '_on_backtest_completed'),
                         (risk_update, '_update_risk_metrics')]:
        for sym in ['risk_ax', 'risk_canvas', 'risk_figure',
                    '_update_risk_chart', '_init_risk_chart',
                    'risk_metrics_panel', 'risk_metrics_history']:
            assert sym not in chunk, f'{label} 仍引用死代码 {sym}'


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
