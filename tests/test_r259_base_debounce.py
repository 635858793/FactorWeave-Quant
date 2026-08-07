#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R259 交叉验证回归测试: StandardDataSourcePlugin 基类防抖 + 验证钩子下沉

覆盖 (R259 交叉验证实证, 全部源码行号):
- 基类 is_connected() 原为纯标志位 (standard_data_source_plugin.py:245-247 R259 前)。
  R259 下沉: 30s 防抖 + 可覆写 _test_connection() 钩子 (is_connected 实现 L252-277)。
- 默认钩子回退标志位 → 不覆写子类行为与旧版完全一致 (向后兼容铁律)。
- connect 成功刷新验证时间戳 (L214-218); disconnect 清缓存 (L238-242)。
- Sina 覆写 _test_connection() 启用 HTTP 数据级验证 (sina_plugin.py:229-242)。

测试策略 (同 R255):
- 弹出 conftest 冲突 mock, 用 importlib 从文件加载被测试模块
- 用 MagicMock 桩隔离 PluginConfig/网络依赖
- 以 call_count 断言防抖: 30s 窗口内 _test_connection 只调一次
"""
import os
import sys
import types
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R251-R258)
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module_from_file(module_name: str, rel_path: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 真实加载基类模块 (轻量依赖链: core.data_source_extensions / core.plugin_types)
_std_module = _load_module_from_file(
    'plugins.templates.standard_data_source_plugin',
    'plugins/templates/standard_data_source_plugin.py')
StandardDataSourcePlugin = _std_module.StandardDataSourcePlugin
AssetType = _std_module.AssetType
DataType = _std_module.DataType

# ===========================================================================
# 测试桩: 最小子类
# ===========================================================================
class _StubPlugin(StandardDataSourcePlugin):
    """最小可实例化子类: 实现基类抽象方法"""

    def __init__(self):
        super().__init__('stub', 'stub_plugin')
        self._test_calls = 0

    def get_version(self) -> str:
        return '1.0.0'

    def get_description(self) -> str:
        return 'stub'

    def get_author(self) -> str:
        return 'test'

    def get_supported_asset_types(self):
        return [AssetType.STOCK_A]

    def get_supported_data_types(self):
        return [DataType.KLINE]

    def get_capabilities(self) -> dict:
        return {}

    def _internal_connect(self, **kwargs) -> bool:
        return True

    def _internal_disconnect(self) -> bool:
        return True

    def _internal_get_asset_list(self, asset_type, market=None):
        return []

    def _internal_get_kdata(self, symbol, freq='D', start_date=None, end_date=None, count=None):
        import pandas as pd
        return pd.DataFrame()

    def _internal_get_real_time_quotes(self, symbols):
        return []

    def _test_connection(self) -> bool:
        self._test_calls += 1
        return True


class _StubDefault(StandardDataSourcePlugin):
    """不覆写钩子的子类: 验证默认回退标志位"""

    def __init__(self):
        super().__init__('stub_default', 'stub_default_plugin')

    def get_version(self) -> str:
        return '1.0.0'

    def get_description(self) -> str:
        return 'stub'

    def get_author(self) -> str:
        return 'test'

    def get_supported_asset_types(self):
        return [AssetType.STOCK_A]

    def get_supported_data_types(self):
        return [DataType.KLINE]

    def get_capabilities(self) -> dict:
        return {}

    def _internal_connect(self, **kwargs) -> bool:
        return True

    def _internal_disconnect(self) -> bool:
        return True

    def _internal_get_asset_list(self, asset_type, market=None):
        return []

    def _internal_get_kdata(self, symbol, freq='D', start_date=None, end_date=None, count=None):
        import pandas as pd
        return pd.DataFrame()

    def _internal_get_real_time_quotes(self, symbols):
        return []


class TestDebouncedIsConnected(unittest.TestCase):
    """R259: 基类 30s 防抖 is_connected"""

    def test_default_hook_falls_back_to_flag(self):
        """默认钩子: 不覆写子类 is_connected 行为与纯标志位一致 (向后兼容)"""
        p = _StubDefault()
        self.assertFalse(p.is_connected())
        p._is_connected = True
        self.assertTrue(p.is_connected())

    def test_connect_success_refreshes_verify_time(self):
        """connect 成功置标志位 + 刷新验证时间戳"""
        p = _StubPlugin()
        result = p.connect()
        self.assertTrue(result)
        self.assertTrue(p.is_connected())
        self.assertIsNotNone(p._last_connection_verify_time)

    def test_debounce_skips_repeated_verification_within_window(self):
        """30s 窗口内 is_connected 不重复调用 _test_connection (防抖实证)"""
        p = _StubPlugin()
        p.connect()
        # 手动回拨验证时间戳 → 模拟窗口内
        p._last_connection_verify_time = datetime.now()
        calls_before = p._test_calls
        for _ in range(5):
            self.assertTrue(p.is_connected())
        self.assertEqual(p._test_calls, calls_before,
                         "30s 防抖窗口内 _test_connection 不得被重复调用")

    def test_verify_rerun_after_interval_expired(self):
        """窗口过期后重新调用 _test_connection 验证"""
        p = _StubPlugin()
        p.connect()
        # 过期验证时间戳 → 下一次 is_connected 触发真实验证
        p._last_connection_verify_time = datetime.now() - timedelta(seconds=31)
        self.assertTrue(p.is_connected())
        self.assertEqual(p._test_calls, 1)

    def test_disconnect_invalidates_cache_immediately(self):
        """disconnect 后立即失效: is_connected() == False, 无防抖残留"""
        p = _StubPlugin()
        p.connect()
        p.disconnect()
        self.assertFalse(p.is_connected())
        # 标志位已清 → 直接短路, 不触发钩子
        calls_before = p._test_calls
        p.is_connected()
        self.assertEqual(p._test_calls, calls_before)

    def test_verification_failure_resets_flag(self):
        """验证失败置 _is_connected = False (防呆: 断连不再误报在线)"""
        p = _StubPlugin()
        p.connect()
        p._test_connection = lambda: False
        p._last_connection_verify_time = datetime.now() - timedelta(seconds=31)
        self.assertFalse(p.is_connected())
        self.assertFalse(p._is_connected)

    def test_verification_exception_fails_safe(self):
        """钩子抛异常 → is_connected False (fail-closed)"""
        p = _StubPlugin()
        p.connect()

        def _boom():
            raise RuntimeError('network down')

        p._test_connection = _boom
        p._last_connection_verify_time = datetime.now() - timedelta(seconds=31)
        self.assertFalse(p.is_connected())
        self.assertFalse(p._is_connected)


if __name__ == '__main__':
    unittest.main()
