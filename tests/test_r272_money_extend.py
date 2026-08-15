# -*- coding: utf-8 -*-
"""R272 正式回归测试: 资金管理消费延伸 (卖出/平仓量建议 + 持仓敞口预警阈值)

背景 (R272, 全部含源码行号):
- R271 完成买入区"建议数量"按钮 (trading_panel.py suggest_quantity_btn →
  _on_suggest_quantity_clicked, 调用 PositionRiskMonitor.calculate_position_size
  止损价 current_price*0.98 固定 2% 降级) + 多空敞口标签 (exposure_label →
  _compute_exposure_display 调用 monitor.calculate_exposure)。
- R272 将其延伸至卖出侧 + 加敞口预警:
  A. 卖出区新增"建议平仓"按钮 suggest_sell_quantity_btn →
     _on_suggest_sell_quantity_clicked: 持仓超风控目标 → 建议减仓量写入
     sell_quantity_spin; 未超 → 全部平仓; monitor 不可用 → 降级全平。
  B. 敞口预警: 净敞口绝对值 / 总资产 > _EXPOSURE_WARN_RATIO (0.3) →
     exposure_label 红色高亮 + tooltip; 否则恢复默认样式, 文本格式保持 R271。

运行: conda activate hikyuu; python -m pytest tests/test_r272_money_extend.py -q
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLBACKEND', 'Agg')

_PANEL = PROJECT_ROOT / 'gui' / 'widgets' / 'trading_panel.py'


def _unmock_gui_widgets():
    """清除 tests/conftest.py:51 gui.widgets 顶层包 MagicMock (mock 无 __path__ 阻断真实子模块导入)"""
    for _m in list(sys.modules):
        if _m == 'gui.widgets' or _m.startswith('gui.widgets.'):
            del sys.modules[_m]


def _make_inst(stock_code='000001', price=10.0, quantity=1000, available_cash=10000.0):
    """构造 TradingPanel 实例 (__new__ 绕过 __init__), 提供卖出建议所需最小属性集"""
    from gui.widgets.trading_panel import TradingPanel
    inst = TradingPanel.__new__(TradingPanel)
    inst._current_stock_code = stock_code
    inst._get_current_price = MagicMock(return_value=price)
    inst.price_spin = MagicMock()
    inst.price_spin.value.return_value = 0.0
    inst._portfolio = SimpleNamespace(available_cash=available_cash)
    inst.sell_quantity_spin = MagicMock()
    inst.trading_service = SimpleNamespace(
        get_position=MagicMock(return_value=SimpleNamespace(quantity=quantity)))
    return inst


# ==================== A. 卖出/平仓量建议按钮 ====================

class TestSuggestSellQuantityBtn:
    def test_btn_wired_and_handler_present(self):
        """卖出区存在"建议平仓"按钮且 clicked 连接 handler (trading_panel.py:308-312)"""
        src = _PANEL.read_text(encoding='utf-8')
        assert 'self.suggest_sell_quantity_btn = QPushButton("建议平仓")' in src
        assert 'clicked.connect(self._on_suggest_sell_quantity_clicked)' in src
        # 运行时 wiring: handler 真实存在且可调用
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        assert callable(TradingPanel._on_suggest_sell_quantity_clicked)

    def test_no_stock_code_warns_no_spin_write(self):
        """未选择股票: 仅警告, 不写 sell_quantity_spin (trading_panel.py:808-810)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._current_stock_code = None
        inst.sell_quantity_spin = MagicMock()
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_sell_quantity_clicked()
        inst.sell_quantity_spin.setValue.assert_not_called()
        assert mb.warning.called

    def test_no_position_warns_no_spin_write(self):
        """无持仓 (get_position 返回 None): 仅警告"当前无持仓", 不写 spin (trading_panel.py:820-823)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = _make_inst()
        inst.trading_service.get_position.return_value = None
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_sell_quantity_clicked()
        inst.sell_quantity_spin.setValue.assert_not_called()
        assert mb.warning.called
        assert mb.warning.call_args[0][2] == '当前无持仓'

    def test_position_zero_warns_no_spin_write(self):
        """持仓数量 <= 0: 视为无持仓, 仅警告 (trading_panel.py:821)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = _make_inst(quantity=0)
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_sell_quantity_clicked()
        inst.sell_quantity_spin.setValue.assert_not_called()
        assert mb.warning.called

    def test_over_risk_target_reduce_written(self):
        """持仓超风控目标: 减仓量 (quantity - target) 写入 sell_quantity_spin (trading_panel.py:846-852)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = _make_inst(price=10.0, quantity=1000, available_cash=10000.0)
        monitor = MagicMock()
        monitor.calculate_position_size.return_value = 400  # 风控目标持仓量
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_sell_quantity_clicked()
        inst.sell_quantity_spin.setValue.assert_called_once_with(600)
        # 与买入侧对称参数
        call_kwargs = monitor.calculate_position_size.call_args[1]
        assert call_kwargs['current_price'] == 10.0
        assert call_kwargs['stop_loss_price'] == pytest.approx(9.8)
        assert call_kwargs['available_cash'] == 10000.0
        assert mb.information.called
        assert '建议减仓 600 股' in mb.information.call_args[0][2]

    def test_under_risk_target_full_close_written(self):
        """持仓未超风控目标: 全部平仓量写入 sell_quantity_spin (trading_panel.py:853-857)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = _make_inst(price=10.0, quantity=200, available_cash=10000.0)
        monitor = MagicMock()
        monitor.calculate_position_size.return_value = 500  # 风控目标持仓量
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_sell_quantity_clicked()
        inst.sell_quantity_spin.setValue.assert_called_once_with(200)
        assert mb.information.called
        assert '可全部平仓' in mb.information.call_args[0][2]

    def test_monitor_unavailable_fallback_full_close(self):
        """PositionRiskMonitor 不可用: 降级直接建议全部平仓 (trading_panel.py:825-832)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = _make_inst(price=10.0, quantity=1000, available_cash=10000.0)
        inst._resolve_position_risk_monitor = MagicMock(return_value=None)
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_sell_quantity_clicked()
        inst.sell_quantity_spin.setValue.assert_called_once_with(1000)
        assert mb.information.called
        assert '全部平仓' in mb.information.call_args[0][2]


# ==================== B. 持仓敞口预警阈值 ====================

def _make_portfolio_display_inst(net_exposure, total_assets=20000.0):
    """构造 _update_portfolio_display 所需最小属性集 (全部 label MagicMock)"""
    _unmock_gui_widgets()
    from gui.widgets.trading_panel import TradingPanel
    inst = TradingPanel.__new__(TradingPanel)
    inst._service_container = None  # __new__ 实例无该属性, 访问缺失属性会触发 PyQt init 错误
    inst._portfolio = SimpleNamespace(
        available_cash=10000.0,
        total_assets=total_assets,
        market_value=10000.0,
        total_profit_loss=1000.0,
        total_profit_loss_pct=5.0,
        positions={'000001': SimpleNamespace(quantity=100, current_price=10.0)})
    for name in ['available_cash_label', 'total_assets_label', 'exposure_label',
                 'total_assets_overview_label', 'available_cash_overview_label',
                 'market_value_label', 'total_profit_loss_label', 'profit_loss_pct_label']:
        setattr(inst, name, MagicMock())
    monitor = MagicMock()
    monitor.calculate_exposure.return_value = {
        'long': net_exposure, 'short': 0.0, 'net': net_exposure}
    inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
    return inst


class TestExposureWarning:
    def test_module_warn_ratio_constant(self):
        """模块级常量 _EXPOSURE_WARN_RATIO = 0.3 (trading_panel.py:37-38)"""
        src = _PANEL.read_text(encoding='utf-8')
        assert '_EXPOSURE_WARN_RATIO = 0.3' in src

    def test_over_threshold_sets_red_style(self):
        """净敞口/总资产超阈值 (10000/20000=0.5>0.3): exposure_label 红色样式 + tooltip (trading_panel.py:1330-1335)"""
        inst = _make_portfolio_display_inst(net_exposure=10000.0)
        inst._update_portfolio_display()
        inst.exposure_label.setStyleSheet.assert_called_once()
        style = inst.exposure_label.setStyleSheet.call_args[0][0]
        assert '#e74c3c' in style
        assert 'font-weight: bold' in style
        inst.exposure_label.setToolTip.assert_called_once()
        assert '净敞口' in inst.exposure_label.setToolTip.call_args[0][0]

    def test_under_threshold_default_style(self):
        """净敞口/总资产未超阈值 (1000/20000=0.05<0.3): 恢复默认样式 (空样式 + 空 tooltip) (trading_panel.py:1336-1338)"""
        inst = _make_portfolio_display_inst(net_exposure=1000.0)
        inst._update_portfolio_display()
        inst.exposure_label.setStyleSheet.assert_called_once_with('')
        inst.exposure_label.setToolTip.assert_called_once_with('')

    def test_exposure_text_format_preserved(self):
        """敞口标签文本格式保持 R271 格式 (多/空/净 ¥ 千分位) (trading_panel.py:784-791)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._service_container = None
        inst._portfolio = SimpleNamespace(positions={
            '000001': SimpleNamespace(quantity=100, current_price=10.0)})
        monitor = MagicMock()
        monitor.calculate_exposure.return_value = {'long': 10000.0, 'short': 0.0, 'net': 10000.0}
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        text = inst._compute_exposure_display()
        assert text == '多: ¥10,000 / 空: ¥0 / 净: ¥10,000'
        assert '多:' in text and '空:' in text and '净:' in text
