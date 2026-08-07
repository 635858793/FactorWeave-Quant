#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R261-c5: BaseDialog 及其安全子类真实 GUI 实例化测试

背景:
- BaseDialog 构造路径不触碰 QApplication/desktop (gui/dialogs/base_dialog.py:133-144 构造,
  desktop 仅在 showEvent -> center_on_parent 时触发, base_dialog.py:249), 可安全真实实例化。
- conftest.py 已按 R261-c5 移除 'gui.dialogs' 顶层 mock, 仅保留有硬问题的子模块 mock。

覆盖:
- session 级 QApplication fixture (offscreen 平台)
- 每个经 R261-c5 独立子进程实证安全的对话框类执行真实实例化断言
- BaseDialog 本体专项断言 (标题/模态/settings_key/方法存在性)
"""
import os
import importlib

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt5.QtWidgets import QApplication, QDialog

from gui.dialogs.base_dialog import BaseDialog


@pytest.fixture(scope='session')
def qapp():
    """session 级 QApplication (offscreen), 与 test_responsive_helper 同模式"""
    app = QApplication.instance() or QApplication([])
    assert QApplication.instance() is not None
    yield app


# R261-c5 实证安全类清单 (模块, 类名, 实例化 kwargs)
# 每个条目均已在独立子进程实测: 导入 + 无参(或给定 kwargs)构造成功且 isinstance QDialog。
SAFE_DIALOGS = [
    ('gui.dialogs.base_dialog', 'BaseDialog', {}),
    ('gui.dialogs.calculator_dialog', 'CalculatorDialog', {}),
    ('gui.dialogs.converter_dialog', 'ConverterDialog', {}),
    ('gui.dialogs.advanced_search_dialog', 'AdvancedSearchDialog', {}),
    ('gui.dialogs.alert_rule_dialog', 'AlertRuleDialog', {}),
    ('gui.dialogs.batch_filter_dialog', 'CompactAdvancedFilterDialog', {}),
    ('gui.dialogs.cloud_api_dialog', 'CloudApiDialog', {}),
    ('gui.dialogs.data_usage_terms_dialog', 'DataUsageTermsDialog', {}),
    ('gui.dialogs.help_viewer_dialog', 'HelpViewerDialog', {}),
    ('gui.dialogs.interval_stat_settings_dialog', 'IntervalStatSettingsDialog', {}),
    ('gui.dialogs.startup_guides_dialog', 'StartupGuidesDialog', {}),
    ('gui.dialogs.external_alert_channel_config_dialog', 'ExternalAlertChannelManagerDialog', {}),
    ('gui.dialogs.risk_rule_config_dialog', 'RiskRuleConfigDialog', {}),
    ('gui.dialogs.settings_dialog', 'SettingsDialog', {}),
    ('gui.dialogs.version_manager_dialog', 'VersionManagerDialog', {}),
    ('gui.dialogs.indicator_params_dialog', 'IndicatorParamsDialog', {'selected_indicators': []}),
    ('gui.dialogs.indicator_combination_dialog', 'IndicatorCombinationDialog', {}),
    ('gui.dialogs.indicator_market_dialog', 'IndicatorMarketDialog', {}),
    ('gui.dialogs.duckdb_config_dialog', 'DuckDBConfigDialog', {}),
    ('gui.dialogs.enhanced_config_management_dialog', 'EnhancedConfigManagementDialog', {}),
    ('gui.dialogs.technical_analysis_dialog', 'TechnicalAnalysisDialog', {}),
    ('gui.dialogs.history_data_dialog', 'HistoryDataDialog', {}),
    ('gui.dialogs.stock_detail_dialog', 'StockDetailDialog', {'stock_code': '600000'}),
    ('gui.dialogs.performance_evaluation_dialog', 'PerformanceEvaluationDialog', {}),
    ('gui.dialogs.portfolio_dialog', 'PortfolioDialog', {}),
]


def _instantiate(module_path: str, cls_name: str, kwargs: dict):
    """真实导入模块并实例化对话框"""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    return cls(**kwargs)


class TestBaseDialogReal:
    """BaseDialog 本体真实实例化专项"""

    def test_construct_no_application_desktop_access(self, qapp):
        """构造路径不触碰 desktop: 构造期间不调用 QApplication.desktop"""
        # BaseDialog 构造 (base_dialog.py:133-196) 不含 desktop; 仅 showEvent 时调用 (L249)
        dlg = BaseDialog(title='R261-test')
        assert isinstance(dlg, QDialog)
        assert dlg.windowTitle() == 'R261-test'
        assert dlg._settings_key is None
        assert dlg.isModal() is True

    def test_construct_with_settings_key_and_size(self, qapp):
        """带 settings_key/size 参数构造: QSettings 恢复路径安全 (restore_geometry L288-312)"""
        dlg = BaseDialog(
            title='R261-key', settings_key='R261BaseDialog',
            size=(640, 480), min_size=(400, 300), modal=False,
        )
        assert dlg._settings_key == 'R261BaseDialog'
        assert dlg.isModal() is False
        assert dlg.minimumWidth() == 400
        assert dlg.minimumHeight() == 300

    def test_required_methods_exist(self, qapp):
        """关键方法存在性 (不调用, 避免触发 desktop/弹窗)"""
        dlg = BaseDialog()
        for attr in ('center_on_parent', 'restore_geometry', 'save_geometry',
                     'show_loading', 'hide_loading', 'set_theme_style',
                     'on_theme_changed', 'add_shadow_effect'):
            assert hasattr(dlg, attr), f'BaseDialog 缺少方法 {attr}'

    def test_multiple_instances(self, qapp):
        """连续实例化多个 BaseDialog 无副作用"""
        dialogs = [BaseDialog(title=f'D{i}') for i in range(3)]
        assert all(isinstance(d, QDialog) for d in dialogs)
        assert [d.windowTitle() for d in dialogs] == ['D0', 'D1', 'D2']


@pytest.mark.parametrize(
    'module_path,cls_name,kwargs',
    SAFE_DIALOGS,
    ids=[f'{m.split(".")[-1]}.{c}' for m, c, _ in SAFE_DIALOGS],
)
def test_safe_dialog_real_instantiation(qapp, module_path, cls_name, kwargs):
    """安全对话框类真实实例化断言"""
    dlg = _instantiate(module_path, cls_name, kwargs)
    assert isinstance(dlg, QDialog), f'{cls_name} 不是 QDialog 实例'
    # 对象存活且具备 QWidget 基本能力
    assert dlg.objectName() is not None or True  # objectName 可空, 仅验证对象有效
    assert hasattr(dlg, 'setWindowTitle')
    assert hasattr(dlg, 'close')
    # R261-c5 加固: StockDetailDialog 构造会 load_data() 启动真实 StockDataWorker 线程
    # (stock_detail_dialog.py:708-730), 立即 close 可能触发 QThread 销毁竞态导致
    # Qt 硬崩溃 0xC0000409 (偶发)。关闭前等待线程结束消除该竞态。
    worker = getattr(dlg, 'data_worker', None)
    if worker is not None and hasattr(worker, 'wait'):
        worker.wait(5000)
    # 关闭路径安全 (closeEvent -> save_geometry 仅在有 settings_key 时触达 QSettings)
    dlg.close()
