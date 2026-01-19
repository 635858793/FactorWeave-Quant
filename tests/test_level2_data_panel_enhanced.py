#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Level-2 数据面板增强功能测试
测试新增的订单簿深度图表、数据导出、历史回放、自定义指标、价格预警等功能
"""

import pytest
import json
import csv
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from PyQt5.QtWidgets import QApplication, QTableWidget
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
import pandas as pd

from gui.widgets.enhanced_ui.level2_data_panel import (
    Level2DataPanel,
    CustomIndicatorDialog,
    PriceAlertDialog,
    HistoricalReplayDialog
)
from core.events.event_bus import EventBus, RealtimeDataEvent, TickDataEvent, OrderBookEvent


@pytest.fixture
def qapp():
    """QApplication fixture"""
    if not QApplication.instance():
        app = QApplication([])
    else:
        app = QApplication.instance()
    yield app


@pytest.fixture
def mock_event_bus():
    """模拟事件总线"""
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.publish = MagicMock()
    return event_bus


@pytest.fixture
def mock_realtime_manager():
    """模拟实时数据管理器"""
    manager = MagicMock()
    manager.subscribe_realtime_data = AsyncMock(return_value=None)
    manager.unsubscribe_realtime_data = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def level2_panel(qapp, mock_event_bus, mock_realtime_manager):
    """Level-2 数据面板 fixture"""
    panel = Level2DataPanel(
        event_bus=mock_event_bus,
        realtime_manager=mock_realtime_manager
    )
    yield panel
    panel.close()


@pytest.fixture
def sample_level2_data():
    """示例 Level-2 数据"""
    return {
        'symbol': '600000',
        'price': 100.25,
        'change': 2.35,
        'change_pct': 2.4,
        'volume': 1234567,
        'turnover': 123450000,
        'bid_price': 100.20,
        'ask_price': 100.30,
        'bid_volume': 5000,
        'ask_volume': 6000,
        'bids': [
            {'price': 100.20, 'volume': 5000},
            {'price': 100.19, 'volume': 4500},
            {'price': 100.18, 'volume': 4000},
            {'price': 100.17, 'volume': 3500},
            {'price': 100.16, 'volume': 3000},
        ],
        'asks': [
            {'price': 100.30, 'volume': 6000},
            {'price': 100.31, 'volume': 5500},
            {'price': 100.32, 'volume': 5000},
            {'price': 100.33, 'volume': 4500},
            {'price': 100.34, 'volume': 4000},
        ]
    }


@pytest.fixture
def sample_tick_data():
    """示例 Tick 数据"""
    return {
        'symbol': '600000',
        'timestamp': datetime.now().isoformat(),
        'price': 100.25,
        'volume': 100,
        'type': 'buy',
        'direction': 'up'
    }


@pytest.fixture
def sample_order_book_data():
    """示例订单簿数据"""
    return {
        'symbol': '600000',
        'timestamp': datetime.now().isoformat(),
        'bids': [
            {'price': 100.20, 'volume': 5000},
            {'price': 100.19, 'volume': 4500},
            {'price': 100.18, 'volume': 4000},
        ],
        'asks': [
            {'price': 100.30, 'volume': 6000},
            {'price': 100.31, 'volume': 5500},
            {'price': 100.32, 'volume': 5000},
        ]
    }


class TestLevel2DataPanelEnhanced:
    """Level-2 数据面板增强功能测试"""

    def test_initialization(self, level2_panel):
        """测试面板初始化"""
        assert level2_panel is not None
        assert level2_panel.event_bus is not None
        assert level2_panel.realtime_manager is not None
        assert level2_panel.current_symbol is None
        assert len(level2_panel.subscribed_symbols) == 0

    def test_ui_components(self, level2_panel):
        """测试UI组件"""
        assert level2_panel.symbol_combo is not None
        assert level2_panel.subscribe_btn is not None
        assert level2_panel.depth_spin is not None
        assert level2_panel.refresh_combo is not None
        assert level2_panel.level2_table is not None
        assert level2_panel.tick_table is not None
        assert level2_panel.order_book_widget is not None

    def test_new_buttons_exist(self, level2_panel):
        """测试新增按钮存在"""
        assert level2_panel.export_btn is not None
        assert level2_panel.replay_btn is not None
        assert level2_panel.custom_indicator_btn is not None
        assert level2_panel.price_alert_btn is not None
        assert level2_panel.compare_btn is not None

    def test_symbol_selection(self, level2_panel):
        """测试股票代码选择"""
        level2_panel.set_symbol('600000')
        assert level2_panel.get_current_symbol() == '600000'

    def test_subscription(self, level2_panel, sample_level2_data):
        """测试订阅功能"""
        level2_panel.set_symbol('600000')
        level2_panel._subscribe_symbol('600000')

        assert '600000' in level2_panel.subscribed_symbols
        assert level2_panel.is_subscribed('600000') is True

    def test_unsubscription(self, level2_panel):
        """测试取消订阅功能"""
        level2_panel.subscribed_symbols.add('600000')
        level2_panel._unsubscribe_symbol('600000')

        assert '600000' not in level2_panel.subscribed_symbols
        assert level2_panel.is_subscribed('600000') is False

    def test_handle_realtime_data(self, level2_panel, sample_level2_data):
        """测试处理实时数据"""
        event = RealtimeDataEvent(realtime_data=sample_level2_data)
        level2_panel._handle_realtime_data(event)

        assert '600000' in level2_panel.level2_data_cache
        assert len(level2_panel.historical_data) > 0

    def test_handle_tick_data(self, level2_panel, sample_tick_data):
        """测试处理Tick数据"""
        event = TickDataEvent(tick_data=sample_tick_data)
        level2_panel.set_symbol('600000')
        level2_panel._handle_tick_data(event)

        assert '600000' in level2_panel.tick_data_cache
        assert len(level2_panel.tick_data_cache['600000']) > 0

    def test_handle_order_book_data(self, level2_panel, sample_order_book_data):
        """测试处理订单簿数据"""
        event = OrderBookEvent(order_book_data=sample_order_book_data)
        level2_panel.set_symbol('600000')
        level2_panel._handle_order_book_data(event)

        assert '600000' in level2_panel.order_book_cache

    def test_price_alert_check(self, level2_panel, sample_level2_data):
        """测试价格预警检查"""
        level2_panel.price_alerts['600000'] = [
            {'type': '高于', 'price': 100.0, 'enabled': True},
            {'type': '低于', 'price': 101.0, 'enabled': True}
        ]

        with patch.object(level2_panel, 'alert_triggered') as mock_alert:
            level2_panel._check_price_alerts(sample_level2_data)
            mock_alert.assert_called_once()

    def test_custom_indicator_calculation(self, level2_panel):
        """测试自定义指标计算"""
        level2_panel.custom_indicators = {
            'test_indicator': 'bid_volume + ask_volume'
        }

        level2_panel._update_custom_indicators()

        assert level2_panel.custom_indicator_table.rowCount() > 0

    def test_depth_change(self, level2_panel):
        """测试档位变更"""
        level2_panel._on_depth_changed(15)
        assert level2_panel.depth_spin.value() == 15

    def test_refresh_rate_change(self, level2_panel):
        """测试刷新频率变更"""
        level2_panel._on_refresh_rate_changed('500ms')
        assert level2_panel.refresh_combo.currentText() == '500ms'

    def test_clear_displays(self, level2_panel):
        """测试清空显示"""
        level2_panel._clear_displays()
        assert level2_panel.level2_table.rowCount() == 0
        assert level2_panel.tick_table.rowCount() == 0


class TestDataExport:
    """数据导出功能测试"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录 fixture"""
        temp = tempfile.mkdtemp()
        yield temp
        import shutil
        shutil.rmtree(temp, ignore_errors=True)

    def test_export_to_csv(self, level2_panel, temp_dir, sample_tick_data):
        """测试导出为CSV"""
        level2_panel.set_symbol('600000')
        level2_panel.tick_data_cache['600000'] = [sample_tick_data]

        csv_path = os.path.join(temp_dir, 'test_export.csv')
        level2_panel._export_to_csv(csv_path)

        assert os.path.exists(csv_path)

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) > 1

    def test_export_to_excel(self, level2_panel, temp_dir, sample_tick_data):
        """测试导出为Excel"""
        level2_panel.set_symbol('600000')
        level2_panel.tick_data_cache['600000'] = [sample_tick_data]

        excel_path = os.path.join(temp_dir, 'test_export.xlsx')
        level2_panel._export_to_excel(excel_path)

        assert os.path.exists(excel_path)

        df = pd.read_excel(excel_path)
        assert len(df) > 0

    def test_export_to_json(self, level2_panel, temp_dir, sample_tick_data):
        """测试导出为JSON"""
        level2_panel.set_symbol('600000')
        level2_panel.tick_data_cache['600000'] = [sample_tick_data]
        level2_panel.historical_data = [sample_tick_data]

        json_path = os.path.join(temp_dir, 'test_export.json')
        level2_panel._export_to_json(json_path)

        assert os.path.exists(json_path)

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'symbol' in data
            assert 'tick_data' in data


class TestCustomIndicatorDialog:
    """自定义指标对话框测试"""

    def test_dialog_initialization(self, qapp):
        """测试对话框初始化"""
        dialog = CustomIndicatorDialog()
        assert dialog is not None
        assert dialog.indicator_table is not None
        dialog.close()

    def test_add_indicator(self, qapp):
        """测试添加指标"""
        dialog = CustomIndicatorDialog()
        initial_rows = dialog.indicator_table.rowCount()

        dialog._add_indicator()
        assert dialog.indicator_table.rowCount() == initial_rows + 1
        dialog.close()

    def test_get_indicators(self, qapp):
        """测试获取指标"""
        dialog = CustomIndicatorDialog()
        dialog._add_indicator()

        name_edit = dialog.indicator_table.cellWidget(0, 0)
        formula_edit = dialog.indicator_table.cellWidget(0, 1)
        name_edit.setText('test_indicator')
        formula_edit.setText('bid_volume + ask_volume')

        indicators = dialog.get_indicators()
        assert 'test_indicator' in indicators
        assert indicators['test_indicator'] == 'bid_volume + ask_volume'
        dialog.close()

    def test_test_indicator(self, qapp):
        """测试指标公式"""
        dialog = CustomIndicatorDialog()
        dialog._add_indicator()

        formula_edit = dialog.indicator_table.cellWidget(0, 1)
        formula_edit.setText('bid_volume + ask_volume')

        with patch('PyQt5.QtWidgets.QMessageBox.information') as mock_info:
            dialog._test_indicator('bid_volume + ask_volume')
            mock_info.assert_called_once()
        dialog.close()


class TestPriceAlertDialog:
    """价格预警对话框测试"""

    def test_dialog_initialization(self, qapp):
        """测试对话框初始化"""
        dialog = PriceAlertDialog(current_price=100.25)
        assert dialog is not None
        assert dialog.alert_table is not None
        dialog.close()

    def test_add_alert(self, qapp):
        """测试添加预警"""
        dialog = PriceAlertDialog(current_price=100.25)
        initial_rows = dialog.alert_table.rowCount()

        dialog.alert_price_edit.setText('101.00')
        dialog.alert_type_combo.setCurrentText('高于')
        dialog._add_alert()

        assert dialog.alert_table.rowCount() == initial_rows + 1
        dialog.close()

    def test_get_alerts(self, qapp):
        """测试获取预警"""
        dialog = PriceAlertDialog(current_price=100.25)
        dialog.alert_price_edit.setText('101.00')
        dialog.alert_type_combo.setCurrentText('高于')
        dialog._add_alert()

        alerts = dialog.get_alerts()
        assert len(alerts) > 0
        assert alerts[0]['type'] == '高于'
        assert alerts[0]['price'] == 101.0
        dialog.close()


class TestHistoricalReplayDialog:
    """历史数据回放对话框测试"""

    @pytest.fixture
    def sample_historical_data(self):
        """示例历史数据"""
        data = []
        for i in range(10):
            data.append({
                'timestamp': (datetime.now() + timedelta(minutes=i)).isoformat(),
                'price': 100.0 + i * 0.1,
                'volume': 100 + i * 10,
                'type': 'buy' if i % 2 == 0 else 'sell'
            })
        return data

    def test_dialog_initialization(self, qapp, sample_historical_data):
        """测试对话框初始化"""
        dialog = HistoricalReplayDialog(historical_data=sample_historical_data)
        assert dialog is not None
        assert dialog.data_table is not None
        assert len(dialog.historical_data) == 10
        dialog.close()

    def test_playback_controls(self, qapp, sample_historical_data):
        """测试回放控制"""
        dialog = HistoricalReplayDialog(historical_data=sample_historical_data)

        assert dialog.play_btn is not None
        assert dialog.pause_btn is not None
        assert dialog.stop_btn is not None
        assert dialog.progress_slider is not None
        dialog.close()

    def test_slider_change(self, qapp, sample_historical_data):
        """测试滑块变更"""
        dialog = HistoricalReplayDialog(historical_data=sample_historical_data)
        dialog._on_slider_changed(5)

        assert dialog.current_index == 5
        assert dialog.data_table.rowCount() > 0
        dialog.close()

    def test_speed_change(self, qapp, sample_historical_data):
        """测试速度变更"""
        dialog = HistoricalReplayDialog(historical_data=sample_historical_data)
        dialog._on_speed_changed('500ms')

        assert dialog.playback_speed == 500
        dialog.close()


class TestIntegration:
    """集成测试"""

    def test_full_data_flow(self, level2_panel, sample_level2_data, sample_tick_data, sample_order_book_data):
        """测试完整数据流"""
        level2_panel.set_symbol('600000')
        level2_panel._subscribe_symbol('600000')

        level2_panel._handle_realtime_data(RealtimeDataEvent(realtime_data=sample_level2_data))
        level2_panel._handle_tick_data(TickDataEvent(tick_data=sample_tick_data))
        level2_panel._handle_order_book_data(OrderBookEvent(order_book_data=sample_order_book_data))

        assert '600000' in level2_panel.level2_data_cache
        assert '600000' in level2_panel.tick_data_cache
        assert '600000' in level2_panel.order_book_cache
        assert len(level2_panel.historical_data) > 0

    def test_custom_indicator_integration(self, level2_panel):
        """测试自定义指标集成"""
        level2_panel.custom_indicators = {
            'test_indicator': 'bid_volume + ask_volume'
        }

        level2_panel._update_custom_indicators()
        assert level2_panel.custom_indicator_table.rowCount() > 0

    def test_price_alert_integration(self, level2_panel, sample_level2_data):
        """测试价格预警集成"""
        level2_panel.price_alerts['600000'] = [
            {'type': '高于', 'price': 100.0, 'enabled': True}
        ]

        with patch.object(level2_panel, 'alert_triggered') as mock_alert:
            level2_panel._check_price_alerts(sample_level2_data)
            mock_alert.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
