#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R257 TDD 回归测试: GUI 模式控件「完善实现」与真死代码治理 (修复代理2 + 用户反馈方向)

背景 (R257 交叉验证, 全部源码行号实证):
- 用户反馈「高价值的直接完善完整的实现所有需要的代码和功能链，不要轻易删除代码」:
  RealTimeChart (backtest_widget.py:125-283) 原 R256 时代的孤儿模式控件
  (mode_label/mode_selector 创建于 :141-145 但 init_ui 从未 addWidget) 经评估为
  高价值 → 完善实现: 控件可见 (init_ui :155-159 模式行) + 接入 TradingService
  (set_mode → _sync_order_executor_trading_mode → OrderExecutor 模式闸门) +
  实盘强确认 (_confirm_enter_live_mode 真实资金风险)。
- 真死代码仍删除: ProfessionalBacktestWidget on_mode_changed/current_mode
  (0 消费者); 「混合模式」选项 (TradingMode.HYBRID 不存在, trading_mode.py:15-24
  仅 BACKTEST/PAPER/LIVE); RealTimeChart.parent_widget (类内 0 读取)。
- 注释勘误 (R255 结论错误): trading_panel.py _on_trading_mode_changed docstring 与
  test_r256_live_mode_entry.py docstring —— enable_risk_control 字段全项目
  0 消费者; 真实闸门是 OrderExecutor._trading_mode, MODE_BLOCKED 是拦截而非关风控。

测试策略:
- 纯源码文本断言 (不 import GUI 模块, 避免 PyQt5 无头问题)
- 以类定义行号锚点提取类体, 断言功能链存在 (正向) 与真死代码消失 (反向)
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BACKTEST_WIDGET = os.path.join(ROOT, 'gui', 'widgets', 'backtest_widget.py')
TRADING_PANEL = os.path.join(ROOT, 'gui', 'widgets', 'trading_panel.py')
R256_TEST = os.path.join(ROOT, 'tests', 'test_r256_live_mode_entry.py')

# 顶层类定义正则 (\n + class, 不匹配缩进嵌套类)
_TOP_CLASS_RE = re.compile(r'\nclass [A-Za-z_]\w*')


def _read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _class_body(src, class_line):
    """提取 class_line 起始的类体文本 (到下一个顶层 class 或 EOF)"""
    start = src.index(class_line)
    m = _TOP_CLASS_RE.search(src, start + 1)
    if not m:
        return src[start:]
    return src[start:m.start()]


class TestRealTimeChartModeChainImplemented(unittest.TestCase):
    """RealTimeChart 模式控件已完善实现为完整功能链 (用户反馈: 高价值不删除)"""

    def setUp(self):
        self.src = _read(BACKTEST_WIDGET)
        self.rtc_body = _class_body(self.src, 'class RealTimeChart(QWidget):')

    def test_mode_controls_created_and_visible(self):
        """控件创建 (:141-142) + 模式行 addWidget (:155-159, 原孤儿控件现已可见)"""
        self.assertIn('self.mode_selector = QComboBox()', self.rtc_body)
        self.assertIn('self.mode_label = QLabel("交易模式:")', self.rtc_body)
        self.assertIn('mode_row.addWidget(self.mode_label)', self.rtc_body)
        self.assertIn('mode_row.addWidget(self.mode_selector)', self.rtc_body)
        self.assertIn('layout.addLayout(mode_row)', self.rtc_body)

    def test_service_container_injected(self):
        """构造参数注入 service_container (:131-133) 供图表区共享全局 TradingService"""
        self.assertIn('def __init__(self, parent=None, service_container=None):', self.rtc_body)
        self.assertIn('self.service_container = service_container', self.rtc_body)

    def test_function_chain_methods_exist(self):
        """功能链 5 方法存在: 服务解析 → 状态同步 → 切换(强确认) → 回退 (:214-283)"""
        self.assertIn('def _get_trading_service(self):', self.rtc_body)
        self.assertIn('def _sync_mode_from_service(self):', self.rtc_body)
        self.assertIn('def _on_trading_mode_changed(self, mode_text: str):', self.rtc_body)
        self.assertIn('def _confirm_enter_live_mode(self) -> bool:', self.rtc_body)
        self.assertIn('def _revert_mode_combo(self, target_text: str):', self.rtc_body)

    def test_mode_change_wired_to_service(self):
        """控件信号连接 + set_mode 联动 + 实盘强确认 (:145/:255-264)"""
        self.assertIn(
            "self.mode_selector.currentTextChanged.connect(self._on_trading_mode_changed)",
            self.rtc_body)
        self.assertIn('service.set_mode(TradingMode.LIVE)', self.rtc_body)
        self.assertIn('service.set_mode(TradingMode.PAPER)', self.rtc_body)
        self.assertIn('self._confirm_enter_live_mode()', self.rtc_body)

    def test_live_mode_confirmation_default_no(self):
        """实盘强确认默认 No + 真实资金风险文案 (:266-275)"""
        self.assertIn('"确认切换到实盘交易"', self.rtc_body)
        self.assertIn('QMessageBox.No', self.rtc_body)

    def test_old_dead_on_mode_changed_removed(self):
        """旧自写自读 on_mode_changed (0 消费者) 已删除, 由 _on_trading_mode_changed 取代"""
        self.assertNotIn('def on_mode_changed(self, mode_text: str):', self.rtc_body)

    def test_old_current_mode_removed(self):
        """自写自读 self.current_mode 字段已删除 (由服务端 get_mode 权威状态取代)"""
        self.assertNotIn('self.current_mode', self.rtc_body)

    def test_parent_widget_dead_field_removed(self):
        """RealTimeChart.parent_widget 死字段 (类内 0 读取) 已删除"""
        self.assertNotIn('self.parent_widget = None', self.rtc_body)

    def test_instantiation_injects_container(self):
        """ProfessionalBacktestWidget 实例化 RealTimeChart 时注入容器 (:2140-2142)"""
        self.assertIn(
            "service_container=getattr(self, 'service_container', None)",
            self.src)


class TestProfessionalBacktestWidgetDeadModeControlsRemoved(unittest.TestCase):
    """ProfessionalBacktestWidget current_mode / on_mode_changed 真死代码仍删除"""

    def setUp(self):
        self.src = _read(BACKTEST_WIDGET)
        self.pbw_body = _class_body(self.src, 'class ProfessionalBacktestWidget(QWidget):')

    def test_no_on_mode_changed_in_pbw(self):
        """类体不再定义 on_mode_changed (0 消费者, 无信号连接)"""
        self.assertNotIn('def on_mode_changed(self, mode_text: str):', self.pbw_body)

    def test_no_current_mode_assignment_in_pbw(self):
        """类体不再有 self.current_mode 赋值及任何 current_mode 引用"""
        self.assertNotIn('self.current_mode = TradingMode.BACKTEST', self.pbw_body)
        self.assertNotIn('self.current_mode', self.pbw_body)


class TestHybridModeOptionRemoved(unittest.TestCase):
    """「混合模式」死选项仍删除 (指向不存在的 TradingMode.HYBRID)"""

    def test_no_hybrid_mode_string(self):
        """backtest_widget.py 源码不再包含 '混合模式' / 'HYBRID'"""
        src = _read(BACKTEST_WIDGET)
        self.assertNotIn('混合模式', src)
        self.assertNotIn('HYBRID', src)


class TestCommentCorrections(unittest.TestCase):
    """R255 结论文档注释勘误 (BACKTEST 关风控 → MODE_BLOCKED 拦截闸门)"""

    def test_trading_panel_docstring_corrected(self):
        """trading_panel.py _on_trading_mode_changed docstring 含正确表述"""
        src = _read(TRADING_PANEL)
        region_start = src.index('def _on_trading_mode_changed(self, mode_text: str) -> None:')
        region = src[region_start:region_start + 3000]
        # 不再含「关风控」错误表述; 含正确表述: 拦截闸门 + enable_risk_control 无消费者
        self.assertNotIn('关风控', region)
        self.assertIn('拦截闸门', region)
        self.assertIn('enable_risk_control', region)

    def test_r256_test_docstring_corrected(self):
        """test_r256_live_mode_entry.py docstring 不再引用已删除死代码行号"""
        src = _read(R256_TEST)
        doc = src[:3000]
        self.assertNotIn('backtest_widget.py:1909-1923', doc)
        self.assertNotIn('仅记录 current_mode 不联动', doc)
        self.assertIn('enable_risk_control', doc)


class TestRegressionProtection(unittest.TestCase):
    """回归保护: 完善实现后关键活代码链不受影响"""

    def test_trading_mode_import_kept(self):
        """顶部 import 保留 TradingMode + ModeContext (:2, ModeContext.create_backtest 依赖)"""
        src = _read(BACKTEST_WIDGET)
        self.assertIn('from core.trading.trading_mode import TradingMode, ModeContext', src)

    def test_mode_context_create_backtest_kept(self):
        """ModeContext.create_backtest 调用链仍在"""
        src = _read(BACKTEST_WIDGET)
        self.assertIn('mode_context = ModeContext.create_backtest(', src)

    def test_trading_panel_mode_switch_logic_kept(self):
        """trading_panel.py 模式切换逻辑未动 (set_mode 联动保留, R256 修复不破坏)"""
        src = _read(TRADING_PANEL)
        self.assertIn('self.trading_service.set_mode(target_mode)', src)


if __name__ == '__main__':
    unittest.main()
