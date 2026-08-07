#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R204-P0-3: UnifiedDataManager 递归防重入保护测试

背景: 2026-08-01 日志出现 "maximum recursion depth exceeded"，
根因: UDM.get_stock_list → get_asset_list → _legacy_get_asset_list → _get_stock_asset_list
      → StockService.get_stock_list → StockManager → DataAccess → StockRepository
      → data_manager.get_stock_list (data_manager=UDM) → 回到 UDM.get_stock_list 无限循环

修复: 模块级 _recursion_guard = threading.local()
      1. _legacy_get_asset_list 统一入口防重入 (覆盖 stock/index/fund/bond 全部资产类型)
      2. _get_stock_asset_list 深度防御防重入
"""

import threading

import pytest
import pandas as pd

from core.containers import get_service_container
from core.services.unified_data_manager import (
    UnifiedDataManager, _recursion_guard
)
from core.plugin_types import AssetType

EMPTY_COLS = ['code', 'name', 'market', 'industry', 'sector', 'list_date', 'status', 'asset_type']


@pytest.fixture(scope='module')
def udm():
    """构造轻量 UDM 实例 (部分初始化失败不影响)"""
    return UnifiedDataManager(get_service_container())


def test_legacy_guard_returns_empty_on_reentry(udm):
    """设置 in_legacy_get_asset_list 标志后，重入调用应直接返回空 DataFrame"""
    _recursion_guard.in_legacy_get_asset_list = True
    try:
        result = udm._legacy_get_asset_list(AssetType.STOCK_A, 'all')
        assert isinstance(result, pd.DataFrame)
        assert result.empty, "递归重入时应返回空 DataFrame 而非继续递归"
    finally:
        _recursion_guard.in_legacy_get_asset_list = False


def test_stock_guard_returns_empty_on_reentry(udm):
    """设置 in_get_stock_asset_list 标志后，重入调用 _get_stock_asset_list 应返回空 DataFrame"""
    _recursion_guard.in_get_stock_asset_list = True
    try:
        result = udm._get_stock_asset_list(AssetType.STOCK_A, 'all')
        assert isinstance(result, pd.DataFrame)
        assert result.empty, "递归重入时应返回空 DataFrame 而非继续递归"
    finally:
        _recursion_guard.in_get_stock_asset_list = False


def test_guard_flags_are_reset_after_normal_call(udm):
    """正常调用结束后标志必须被 finally 重置 (防止污染后续调用)"""
    # 强制走 legacy 路径, 不命中重入
    original_duckdb = udm.duckdb_available
    udm.duckdb_available = False
    try:
        result = udm._legacy_get_asset_list(AssetType.STOCK_A, 'all')
        assert isinstance(result, pd.DataFrame)
    finally:
        udm.duckdb_available = original_duckdb
    assert not getattr(_recursion_guard, 'in_legacy_get_asset_list', False), \
        "in_legacy_get_asset_list 标志应在 finally 中重置"
    assert not getattr(_recursion_guard, 'in_get_stock_asset_list', False), \
        "in_get_stock_asset_list 标志应在 finally 中重置"


def test_recursion_chain_no_crash(udm):
    """
    模拟完整递归环: FakeStockService.get_stock_list 回调 UDM.get_asset_list
    断言: 不抛 RecursionError, 返回空 DataFrame
    """
    class FakeStockService:
        """模拟 StockRepository.data_manager.get_stock_list 回调 UDM"""

        def __init__(self, inner_udm):
            self.inner_udm = inner_udm

        def get_stock_list(self):
            # 对应 core/data/repository.py:142 getattr(self.data_manager, 'get_stock_list')
            return self.inner_udm.get_asset_list(asset_type='stock_a')

    original_duckdb = udm.duckdb_available
    original_stock_service = getattr(udm, '_stock_service', None)
    udm.duckdb_available = False
    udm._stock_service = FakeStockService(udm)
    try:
        result = udm.get_asset_list(asset_type='stock_a')
        assert isinstance(result, pd.DataFrame), \
            "递归环应被守卫阻断并返回 DataFrame, 而非抛 RecursionError"
    finally:
        udm.duckdb_available = original_duckdb
        udm._stock_service = original_stock_service


def test_index_recursion_chain_no_crash(udm):
    """R+1 round 补强: index 资产类型的同类递归环也应被统一守卫阻断"""
    class FakeIndexService:
        """模拟 index_service 回调 UDM"""

        def __init__(self, inner_udm):
            self.inner_udm = inner_udm

        def get_index_list(self):
            return self.inner_udm.get_asset_list(asset_type='index')

    # 构造一个可解析的 fallback_loader, 使 _get_index_asset_list 走 fake 服务
    original_duckdb = udm.duckdb_available
    original_fallback = getattr(udm, 'fallback_loader', None)
    udm.duckdb_available = False

    class FakeFallbackLoader:
        def __init__(self, inner_udm):
            self.inner_udm = inner_udm

        def get_asset_list(self, asset_type, market=None):
            return FakeIndexService(self.inner_udm).get_index_list()

    udm.fallback_loader = FakeFallbackLoader(udm)
    try:
        result = udm.get_asset_list(asset_type='index')
        assert isinstance(result, pd.DataFrame), \
            "index 递归环应被统一守卫阻断并返回 DataFrame"
    finally:
        udm.duckdb_available = original_duckdb
        udm.fallback_loader = original_fallback


def test_thread_local_isolation():
    """threading.local 守卫应线程隔离: 子线程设置标志不影响主线程"""
    assert isinstance(_recursion_guard, threading.local)
    set_flag = threading.Event()
    release = threading.Event()

    def worker():
        _recursion_guard.in_legacy_get_asset_list = True
        set_flag.set()
        release.wait(5)

    t = threading.Thread(target=worker)
    t.start()
    try:
        assert set_flag.wait(5), "子线程应完成标志设置"
        # 主线程不应看到子线程的标志
        assert not getattr(_recursion_guard, 'in_legacy_get_asset_list', False), \
            "threading.local 应隔离线程间标志"
    finally:
        release.set()
        t.join(5)
