#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R293 修复：enhanced_data_import_widget 向 download_incremental_data 传递非法 kwargs（TDD）

运行时 TypeError：gui/widgets/enhanced_data_import_widget.py 两处调用
`download_incremental_data(..., skip_weekends=True, skip_holidays=True)`，
但 EnhancedDuckDBDataDownloader.download_incremental_data 签名中不存在这两个参数
（跳过逻辑由服务端 config['skip_weekends']/config['skip_holidays'] 默认 True 驱动）。

修复：删除 UI 两处调用中的 skip_weekends/skip_holidays 参数行，行为不变。
"""
import os
import sys
import inspect
import asyncio
from datetime import datetime
import pytest
from unittest.mock import MagicMock, AsyncMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader
from core.services.incremental_data_analyzer import DownloadStrategy

WIDGET_PATH = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'enhanced_data_import_widget.py')


# =========================================================================
# 测试 1 + 3：download_incremental_data 签名契约（服务端）
# =========================================================================
class TestDownloadSignatureContract:
    """签名契约：不包含 skip_weekends/skip_holidays，合法参数集可绑定"""

    def test_signature_has_no_skip_kwargs(self):
        """锁定契约：签名不含 skip_weekends/skip_holidays（跳过逻辑由 config 驱动）"""
        sig = inspect.signature(EnhancedDuckDBDataDownloader.download_incremental_data)
        assert 'skip_weekends' not in sig.parameters, "签名不应包含 skip_weekends"
        assert 'skip_holidays' not in sig.parameters, "签名不应包含 skip_holidays"

    def test_valid_kwargs_bindable(self):
        """兼容性：现有合法参数集可绑定，不抛 TypeError"""
        sig = inspect.signature(EnhancedDuckDBDataDownloader.download_incremental_data)
        sig.bind(
            object(),  # self 占位（未绑定方法签名含 self）
            symbols=['000001'],
            end_date=datetime(2026, 8, 15),
            strategy=DownloadStrategy.GAP_FILL,
        )

    def test_call_with_valid_kwargs_no_typeerror(self):
        """兼容性：以现有合法参数集调用 download_incremental_data 不抛 TypeError

        参考 tests/test_r254_data_storage.py TestDegradedDownload：三组件置 None
        触发降级朴素增量路径，验证完整调用链路合法。
        """
        dl = object.__new__(EnhancedDuckDBDataDownloader)
        dl.incremental_analyzer = None
        dl.completeness_checker = None
        dl.update_recorder = None
        dl.download_historical_kline_data = AsyncMock(
            return_value={'000001': __import__('pandas').DataFrame()})
        dl.download_fundamental_data = AsyncMock(return_value={})

        result = asyncio.run(
            dl.download_incremental_data(
                symbols=['000001'],
                end_date=datetime(2026, 8, 15),
                strategy=DownloadStrategy.GAP_FILL,
            )
        )
        assert result is not None
        assert result['task_id'] is None


# =========================================================================
# 测试 2：UI 调用点净化断言（widget 源码）
# =========================================================================
class TestWidgetCallSiteClean:
    """widget 源码中两处调用段不得再携带 skip_* 非法 kwargs"""

    def test_widget_source_has_no_skip_kwargs(self):
        """整个 widget 文件中 'skip_weekends' / 'skip_holidays' 出现次数必须为 0"""
        with open(WIDGET_PATH, encoding='utf-8') as f:
            src = f.read()
        assert src.count('skip_weekends') == 0, "widget 源码仍含 skip_weekends 非法参数"
        assert src.count('skip_holidays') == 0, "widget 源码仍含 skip_holidays 非法参数"
