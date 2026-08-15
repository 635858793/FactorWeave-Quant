#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R267-c 风险图表死代码清理测试（backtest_widget.py）

背景：risk_figure / risk_canvas / risk_ax 全文件无赋值创建，_init_risk_chart 无调用点，
仅回测完成时触发一次且因缺 canvas 从未真正执行。经三子代理交叉验证（业务意图还原
→ UI 结构 → 数据可得性 → 重复度），判定不值得完整实现（VaR/CVaR 是整段标量非时间
序列，标量已由 QLabel/QTableWidget 多处展示，主图已有回撤曲线），决策为删除死代码、
保留 QLabel 标量展示与 AlertsPanel 类本体。

覆盖：
- 源码零残留：risk_figure/risk_canvas/risk_ax/risk_metrics_history/_init_risk_chart/
  _update_risk_chart/risk_metrics_panel/_calculate_and_update_risk_metrics 均不在源码中
- 类本体保留：AlertsPanel 定义存在，update_risk_metrics 方法存在
- 动态行为：AST 提取 AlertsPanel 类 + stub Qt 命名空间 exec，实例化正常
- update_risk_metrics：QLabel 标量正确更新、QGroupBox 仅首帧创建、可重复调用
"""
import ast
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKTEST_WIDGET = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'backtest_widget.py')

# R267-c 删除的死代码标识符（全文件必须零残留）
DEAD_SYMBOLS = [
    'risk_figure',
    'risk_canvas',
    'risk_ax',
    'risk_metrics_history',
    '_init_risk_chart',
    '_update_risk_chart',
    'risk_metrics_panel',
    '_calculate_and_update_risk_metrics',
]


def _read_source() -> str:
    with open(BACKTEST_WIDGET, encoding='utf-8') as f:
        return f.read()


def _extract_class_source(src: str, class_name: str) -> str:
    """AST 提取指定类定义的源码文本"""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f'类 {class_name} 未在源码中找到')


def _make_qt_stub_ns():
    """构造 AlertsPanel 可 exec 的 Qt stub 命名空间（无需真实 PyQt5）"""
    class StubWidget:
        def __init__(self, *a, **kw):
            pass

        def layout(self):
            return MagicMock()

    ns = {
        'QWidget': StubWidget,
        'QVBoxLayout': lambda *a, **kw: MagicMock(),
        'QLabel': lambda *a, **kw: MagicMock(),
        'QListWidget': lambda *a, **kw: MagicMock(),
        'QListWidgetItem': lambda *a, **kw: MagicMock(),
        'QPushButton': lambda *a, **kw: MagicMock(),
        'QColor': lambda *a, **kw: MagicMock(),
        'QGroupBox': lambda *a, **kw: MagicMock(),
        'QFormLayout': lambda *a, **kw: MagicMock(),
        'datetime': __import__('datetime'),
        'Dict': dict,
    }
    return ns


def test_dead_symbols_fully_removed():
    """死代码标识符全文件零残留（含注释、字符串、代码三态）"""
    src = _read_source()
    for sym in DEAD_SYMBOLS:
        assert sym not in src, f'死代码标识符 {sym} 仍残留在 backtest_widget.py'


def test_alerts_panel_class_kept():
    """AlertsPanel 类本体保留（外部测试 test_backtest_ui_static.py:137 依赖）"""
    src = _read_source()
    assert 'class AlertsPanel(QWidget)' in src
    assert 'def update_risk_metrics' in src


def test_update_risk_metrics_no_chart_reference():
    """update_risk_metrics 不再引用已删除的 _update_risk_chart"""
    src = _read_source()
    alerts_src = _extract_class_source(src, 'AlertsPanel')
    assert '_update_risk_chart' not in alerts_src
    assert 'risk_ax' not in alerts_src


def test_alerts_panel_instantiates():
    """AST 提取 + stub Qt 命名空间 exec：AlertsPanel 可实例化、init_ui 正常"""
    src = _read_source()
    class_src = _extract_class_source(src, 'AlertsPanel')
    ns = _make_qt_stub_ns()
    exec(compile(class_src, '<AlertsPanel>', 'exec'), ns)
    cls = ns['AlertsPanel']
    panel = cls(parent=None)
    assert panel.alerts == []


def test_update_risk_metrics_sets_labels():
    """update_risk_metrics：QLabel 标量正确更新、QGroupBox 仅首帧创建、可重复调用"""
    src = _read_source()
    class_src = _extract_class_source(src, 'AlertsPanel')
    ns = _make_qt_stub_ns()
    exec(compile(class_src, '<AlertsPanel>', 'exec'), ns)
    cls = ns['AlertsPanel']
    panel = cls(parent=None)

    risk_metrics = {
        'var_95': -0.02,
        'cvar_95': -0.03,
        'max_drawdown': -0.15,
        'volatility': 0.2,
        'sharpe_ratio': 1.5,
    }
    panel.update_risk_metrics(risk_metrics)
    panel.update_risk_metrics(risk_metrics)

    assert panel.var_label.setText.called
    assert panel.sharpe_label.setText.called
    # QGroupBox 仅创建一次
    panel.var_label.setText.assert_called_with('-2.00%')
    # 再次调用不重建（同一 risk_group 对象）
    group_id = id(panel.risk_group)
    panel.update_risk_metrics(risk_metrics)
    assert id(panel.risk_group) == group_id


def test_no_risk_chart_call_in_metrics_pipeline():
    """回测结果→指标更新链不再有 risk_metrics_panel / risk_ax 分支"""
    src = _read_source()
    assert 'risk_metrics_panel' not in src
    assert 'risk_ax' not in src


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
