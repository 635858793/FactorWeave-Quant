#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R256 TDD 回归测试: 实盘 LIVE 入口 (断点A, P0)

覆盖 (R256 主智能体交叉验证 + R257 死代码清理勘误, 全部源码行号实证):
- 断点A 实证链:
  * 闸门: order_executor.py:340 默认 _trading_mode='paper'; :1013 真实 CTP/XTP 接口
    在非 live 模式一律 MODE_BLOCKED (真实资金安全拦截闸门, 拦截报单)。
  * 勘误 (R257): 真实闸门是 OrderExecutor._trading_mode, MODE_BLOCKED 是拦截
    而非关闭风险控制; trading_service._trading_config["enable_risk_control"]
    字段全项目 0 消费者, 并非风控闸门。
  * 放行链已存在: trading_service.set_mode (:325) → _sync_order_executor_trading_mode
    (:357-374) → OrderExecutor.set_trading_mode('live') (:1522)。
  * 断链 (R257 已清理): backtest_widget.py 死代码模式控件/on_mode_changed 已删除;
    trading_panel.py 此前无任何交易模式控件。
- 修复: TradingPanel 提供 模拟交易/实盘交易 切换 (R256-P0):
  * 切实盘: _confirm_enter_live_mode 强确认 (QMessageBox 真实资金风险) → 确认后
    trading_service.set_mode(TradingMode.LIVE); 取消回退选择器。
  * 切模拟: 直接 trading_service.set_mode(TradingMode.PAPER), 无需确认。
  * 交易服务缺失 / set_mode 抛异常 → 不崩溃, 选择器回退模拟。

测试策略 (同 R255):
- 弹出 conftest 冲突 mock 条目, 用 importlib 从文件加载被测试模块
- order_repository / account_repository 以 mock 模块隔离重型 DB 依赖
- TradingPanel 构造: offscreen QApplication + MagicMock 容器/表格 (patch UI 初始化)
- 值语义断言 (跨批次 sys.modules 分裂防御, R254 教训): 枚举按 .value 比较
- 本文件末尾恢复被 mock 污染的 sys.modules 条目
"""
import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R251/R252/R253/R254/R255)
# ---------------------------------------------------------------------------
_CONFTEST_MOCKS = [
    'gui', 'gui.dialogs', 'gui.dialogs.strategy_manager_dialog',
    'gui.widgets', 'gui.widgets.backtest_widget', 'gui.widgets.trading_panel',
    'gui.widgets.enhanced_ui', 'gui.widgets.enhanced_ui.order_book_widget',
    'gui.widgets.enhanced_ui.level2_data_panel', 'gui.widgets.performance',
    'gui.widgets.performance.tabs', 'gui.utils', 'gui.utils.responsive_helper',
    'core.ui', 'core.ui.panels', 'core.ui.panels.base_panel',
    'core.ui.panels.left_panel', 'core.ui.panels.middle_panel',
    'core.ui.panels.right_panel', 'core.ui.panels.bottom_panel',
    'core.ui.widgets', 'core.coordinators.main_window_coordinator',
]
for _mod in _CONFTEST_MOCKS:
    sys.modules.pop(_mod, None)

# trading_panel 模块级导入依赖的 DB 重型模块以 mock 隔离
for _mod in ('core.trading.order_repository', 'core.trading.account_repository'):
    sys.modules.pop(_mod, None)
from unittest.mock import MagicMock, patch  # noqa: E402

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
# mock 重型依赖后, 真实加载被测试模块 (加载顺序同 R255)
# ---------------------------------------------------------------------------
_make_mock_module('core.trading.order_repository')
_make_mock_module('core.trading.account_repository')

# trading_service: TradingPanel 模块级导入 (:32) 依赖, 且 set_mode 联动测试需要
_ts_module = _load_module_from_file(
    'core.services.trading_service', 'core/services/trading_service.py')
TradingService = _ts_module.TradingService
TradingMode = _ts_module.TradingMode

import gui.widgets  # noqa: E402
_tp_module = _load_module_from_file(
    'gui.widgets.trading_panel', 'gui/widgets/trading_panel.py')
TradingPanel = _tp_module.TradingPanel

from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

_APP = None


def _get_app():
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


# ===========================================================================
# 断点A: TradingPanel 交易模式切换 → TradingService.set_mode 联动
# ===========================================================================
_MISSING = object()  # 哨兵: 区分 默认(MagicMock) 与 显式 None(缺失场景)


class TestTradingPanelModeSwitch(unittest.TestCase):
    """GUI 实盘入口: 模拟/实盘切换联动 TradingService.set_mode (断点A 修复)"""

    def _make_panel(self, trading_service=_MISSING):
        """真实 TradingPanel 实例 (patch UI 初始化, 同 R255), 模式选择器用 MagicMock"""
        _get_app()
        with patch.object(TradingPanel, '_init_ui'), \
             patch.object(TradingPanel, '_connect_signals'), \
             patch.object(TradingPanel, '_subscribe_events'):
            if trading_service is _MISSING:
                panel = TradingPanel(
                    trading_service=MagicMock(),
                    event_bus=MagicMock(),
                    service_container=MagicMock(),
                )
            else:
                # 显式 None: 模拟交易服务缺失场景 (防三元表达式兜底成 MagicMock)
                panel = TradingPanel(
                    trading_service=trading_service,
                    event_bus=MagicMock(),
                    service_container=MagicMock(),
                )
        combo = MagicMock()
        combo.findText.return_value = 0
        panel.trading_mode_combo = combo
        return panel

    def test_live_mode_confirm_calls_set_mode_live(self):
        """确认切入实盘 → trading_service.set_mode(LIVE) 被调用 (闸门放行前提)"""
        panel = self._make_panel()
        panel._confirm_enter_live_mode = lambda: True

        TradingPanel._on_trading_mode_changed(panel, '实盘交易')

        panel.trading_service.set_mode.assert_called_once()
        mode_arg = panel.trading_service.set_mode.call_args[0][0]
        # 值语义断言 (跨批次防御): TradingMode.LIVE.value == 'live'
        self.assertEqual(mode_arg.value, 'live')
        self.assertFalse(panel.trading_mode_combo.blockSignals.called)

    def test_live_mode_cancel_reverts_combo_and_no_set_mode(self):
        """取消切入实盘 → set_mode 不被调用, 选择器回退 (blockSignals 防再触发)"""
        panel = self._make_panel()
        panel._confirm_enter_live_mode = lambda: False

        TradingPanel._on_trading_mode_changed(panel, '实盘交易')

        panel.trading_service.set_mode.assert_not_called()
        # 回退: findText 查找模拟交易索引 + blockSignals 包裹 setCurrentIndex
        panel.trading_mode_combo.findText.assert_called_once_with('模拟交易')
        panel.trading_mode_combo.blockSignals.assert_called()
        panel.trading_mode_combo.setCurrentIndex.assert_called_once()

    def test_paper_mode_switches_without_confirm(self):
        """切回模拟 → 直接 set_mode(PAPER), 不触发实盘确认"""
        panel = self._make_panel()
        panel._confirm_enter_live_mode = lambda: (_ for _ in ()).throw(
            AssertionError('模拟模式不应触发实盘确认'))

        TradingPanel._on_trading_mode_changed(panel, '模拟交易')

        panel.trading_service.set_mode.assert_called_once()
        mode_arg = panel.trading_service.set_mode.call_args[0][0]
        self.assertEqual(mode_arg.value, 'paper')

    def test_trading_service_missing_no_crash_reverts(self):
        """交易服务缺失 → 不崩溃, 选择器回退"""
        panel = self._make_panel(trading_service=None)
        panel._confirm_enter_live_mode = lambda: True

        TradingPanel._on_trading_mode_changed(panel, '实盘交易')

        panel.trading_mode_combo.findText.assert_called_once_with('模拟交易')
        panel.trading_mode_combo.setCurrentIndex.assert_called_once()

    def test_set_mode_raises_no_crash_reverts(self):
        """set_mode 抛异常 → 不崩溃, 选择器回退"""
        panel = self._make_panel()
        panel.trading_service.set_mode.side_effect = RuntimeError('boom')
        panel._confirm_enter_live_mode = lambda: True

        TradingPanel._on_trading_mode_changed(panel, '实盘交易')

        panel.trading_mode_combo.findText.assert_called_once_with('模拟交易')
        panel.trading_mode_combo.setCurrentIndex.assert_called_once()


class TestConfirmEnterLiveMode(unittest.TestCase):
    """实盘强确认对话框: Yes/No 分支"""

    def test_confirm_yes(self):
        """QMessageBox.warning 返回 Yes → 确认"""
        _get_app()
        panel = TradingPanel.__new__(TradingPanel)
        with patch.object(QMessageBox, 'warning', return_value=QMessageBox.Yes):
            self.assertTrue(TradingPanel._confirm_enter_live_mode(panel))

    def test_confirm_no(self):
        """QMessageBox.warning 返回 No (默认按钮) → 拒绝"""
        _get_app()
        panel = TradingPanel.__new__(TradingPanel)
        with patch.object(QMessageBox, 'warning', return_value=QMessageBox.No):
            self.assertFalse(TradingPanel._confirm_enter_live_mode(panel))


# ---------------------------------------------------------------------------
# 恢复被 mock 污染的 sys.modules 条目 (同 R255 教训: 消费者副本一并弹出)
# ---------------------------------------------------------------------------
for _mod_name in ('core.trading.order_repository',
                  'core.trading.account_repository',
                  'core.services.trading_service',
                  'gui.widgets.trading_panel'):
    sys.modules.pop(_mod_name, None)


if __name__ == '__main__':
    unittest.main()
