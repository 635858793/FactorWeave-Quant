"""
R238-P0-2 TDD 测试: UnifiedDataManager 锁重入双路径死锁修复

测试目标:
1. 路径 A: cancel_request 持 request_tracker_lock 时调用 _cleanup_resources
   → _unregister_request 重入同锁 → 死锁 (修复前 unified_data_manager.py:3840-3853)
2. 路径 B: dispose 持 _request_lock 时调用 cancel_request
   → cancel_request 内 with self._request_lock 重入同锁 → 死锁 (修复前 :4158-4163)
3. 修复后: 两条路径均在有限时间内完成 (不阻塞), 请求正确取消

关联铁律:
- R104 §12 #1 R+1 round 二次验证
- R85 §10 假修复鉴别 4 步法
- TDD RED-GREEN-REFACTOR 闭环 (R219 强制)
"""

import os
import threading
import time
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

ROOT = Path(__file__).parent.parent

DEADLOCK_TIMEOUT = 2.0  # 秒 - 死锁检测超时


def run_with_timeout(fn, timeout=DEADLOCK_TIMEOUT):
    """在子线程中运行函数, 若超时未完成则判定死锁."""
    result = {}
    barrier = threading.Event()

    def _target():
        try:
            result['value'] = fn()
            result['ok'] = True
        except Exception as e:
            result['error'] = e
        finally:
            barrier.set()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    done = barrier.wait(timeout=timeout)
    if not done:
        return {'deadlock': True, 'thread': t}
    if 'error' in result:
        raise result['error']
    return {'deadlock': False, 'value': result.get('value')}


@pytest.fixture
def manager():
    """轻量构造 UnifiedDataManager (绕过沉重 __init__, 只设锁与相关属性).

    仅聚焦锁重入逻辑, 不触发数据库/插件/DuckDB 等初始化.
    """
    import threading as _threading

    from core.services.unified_data_manager import UnifiedDataManager, DataRequestStatus

    m = UnifiedDataManager.__new__(UnifiedDataManager)
    # 锁
    m.request_tracker_lock = _threading.Lock()
    m._request_lock = _threading.Lock()
    m._dedup_lock = _threading.Lock()
    # 请求容器
    m.request_tracker = {}
    m._pending_requests = {}
    m._active_requests = {}
    m._completed_requests = {}
    m._request_dedup = {}
    # 统计
    m._stats = {
        'requests_total': 0,
        'requests_completed': 0,
        'requests_failed': 0,
        'requests_cancelled': 0,
        'cache_hits': 0,
        'cache_misses': 0
    }
    # dispose 所需
    m._executor = MagicMock()
    m._cache_lock = _threading.Lock()
    m._data_cache = {}
    m._cache_timestamps = {}
    m.multi_cache = MagicMock()
    m.cache_manager = MagicMock()
    m.cache_enabled = True
    m._cache_ttl = 300
    m.db_access = None
    return m


class TestR238P02CancelRequestDeadlock:
    """R238-P0-2-A: cancel_request 锁重入死锁 (路径 A)."""

    def test_p02a_1_cancel_request_with_tracked_request_no_deadlock(self, manager):
        """路径 A: request_tracker 有请求时 cancel_request 不阻塞 (修复前死锁)."""
        from core.services.unified_data_manager import DataRequest

        req_id = "req-A-1"
        manager.request_tracker[req_id] = {'timestamp': time.time(), 'task': None}

        r = run_with_timeout(lambda: manager.cancel_request(req_id))
        assert not r.get('deadlock'), "cancel_request 死锁: 持 request_tracker_lock 重入同锁"

    def test_p02a_2_tracker_cleaned_after_cancel(self, manager):
        """路径 A: cancel_request 后 request_tracker 中请求被移除."""
        from core.services.unified_data_manager import DataRequest

        req_id = "req-A-2"
        manager.request_tracker[req_id] = {'timestamp': time.time(), 'task': None}

        manager.cancel_request(req_id)
        assert req_id not in manager.request_tracker, "request_tracker 未清理"

    def test_p02a_3_cancel_returns_true(self, manager):
        """路径 A: 命中 tracker 时 cancel_request 返回 True."""
        from core.services.unified_data_manager import DataRequest

        req_id = "req-A-3"
        manager.request_tracker[req_id] = {'timestamp': time.time(), 'task': None}

        assert manager.cancel_request(req_id) is True, "cancel_request 应返回 True"


class TestR238P02DisposeDeadlock:
    """R238-P0-2-B: dispose 锁重入死锁 (路径 B)."""

    def test_p02b_1_dispose_with_pending_request_no_deadlock(self, manager):
        """路径 B: 有 pending 请求时 dispose 不阻塞 (修复前持 _request_lock 重入死锁)."""
        from core.services.unified_data_manager import DataRequest, DataRequestStatus

        req = DataRequest(request_id="req-B-1", symbol="600000", status=DataRequestStatus.PENDING)
        manager._pending_requests[req.request_id] = req

        r = run_with_timeout(manager.dispose)
        assert not r.get('deadlock'), "dispose 死锁: 持 _request_lock 重入 cancel_request"

    def test_p02b_2_dispose_with_active_request_no_deadlock(self, manager):
        """路径 B: 有 active 请求时 dispose 不阻塞."""
        from core.services.unified_data_manager import DataRequest, DataRequestStatus

        req = DataRequest(request_id="req-B-2", symbol="600000", status=DataRequestStatus.LOADING)
        manager._active_requests[req.request_id] = req

        r = run_with_timeout(manager.dispose)
        assert not r.get('deadlock'), "dispose 死锁: 持 _request_lock 重入 cancel_request"

    def test_p02b_3_pending_cleared_after_dispose(self, manager):
        """路径 B: dispose 后 pending 请求被取消移除."""
        from core.services.unified_data_manager import DataRequest, DataRequestStatus

        req = DataRequest(request_id="req-B-3", symbol="600000", status=DataRequestStatus.PENDING)
        manager._pending_requests[req.request_id] = req

        manager.dispose()
        assert req.request_id not in manager._pending_requests, "pending 请求未在 dispose 后清理"
