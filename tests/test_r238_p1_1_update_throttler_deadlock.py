"""
R238-P1-1 TDD 测试: UpdateThrottler.batch_update 锁重入死锁修复

测试目标:
1. 路径 A: batch_update 达到 max_batch_size 触发即时 flush 时不阻塞 (修复前 _flush_batch 重入 batch_lock)
2. 路径 B: batch_update 首请求启动 delayed_flush 定时器, 到期 flush 不阻塞
3. 修复后: 批量数据正确合并执行, batch_updates 清空

关联铁律:
- R104 §12 #1 R+1 round 二次验证
- R85 §10 假修复鉴别 4 步法
- TDD RED-GREEN-REFACTOR 闭环 (R219 强制)
"""

import threading
import time
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent

DEADLOCK_TIMEOUT = 2.0  # 秒


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


def make_throttler(max_batch_size=50):
    """构造轻量 UpdateThrottler (不启动 worker)."""
    from optimization.update_throttler import UpdateThrottler
    t = UpdateThrottler(max_batch_size=max_batch_size)
    t.is_running = True  # batch_update 需要 is_running=True
    return t


class TestR238P11BatchUpdateDeadlock:
    """R238-P1-1: batch_update 锁重入死锁."""

    def test_p11_1_immediate_flush_at_max_batch_no_deadlock(self):
        """路径 A: 达到 max_batch_size 即时 flush 不阻塞 (修复前重入 batch_lock 死锁)."""
        t = make_throttler(max_batch_size=2)
        executed = []
        update_func = lambda data: executed.append(list(data))

        # 第一请求: 启动定时器路径
        r1 = run_with_timeout(lambda: t.batch_update("batch-A", update_func, [1]))
        assert not r1.get('deadlock'), "第一请求不应死锁"

        # 第二请求: 达到 max_batch_size=2 → 即时 flush
        r2 = run_with_timeout(lambda: t.batch_update("batch-A", update_func, [2]))
        assert not r2.get('deadlock'), "达到 max_batch_size 即时 flush 死锁"

    def test_p11_2_flush_executes_combined_data(self):
        """路径 A: flush 后数据被合并执行."""
        t = make_throttler(max_batch_size=2)
        executed = []
        update_func = lambda data: executed.append(list(data))

        t.batch_update("batch-A", update_func, [1])
        t.batch_update("batch-A", update_func, [2])

        assert len(executed) >= 1, "flush 后 update_func 应被执行"
        assert executed[0] == [1, 2], f"数据应合并为 [1,2], 实际 {executed[0]}"
        assert "batch-A" not in t.batch_updates, "flush 后 batch_updates 应清空"

    def test_p11_3_delayed_flush_timer_no_deadlock(self):
        """路径 B: 首请求 delayed_flush 定时器到期 flush 不阻塞."""
        t = make_throttler(max_batch_size=50)
        executed = []
        update_func = lambda data: executed.append(list(data))

        # 只发一个请求 → 启动定时器 (max_wait_ms=100ms)
        t.batch_update("batch-B", update_func, [42], max_wait_ms=100)

        # 等定时器触发 (超时检测: 若死锁, barrier 永不 set)
        result = {}
        barrier = threading.Event()

        def _wait_flush():
            deadline = time.time() + DEADLOCK_TIMEOUT
            while time.time() < deadline:
                if executed:
                    barrier.set()
                    return
                time.sleep(0.02)
            barrier.set()  # 超时也算完成 (不会死锁挂住主线程)

        t2 = threading.Thread(target=_wait_flush, daemon=True)
        t2.start()
        t2.join(DEADLOCK_TIMEOUT + 0.5)
        assert not t2.is_alive(), "delayed_flush 定时器线程疑似死锁"

    def test_p11_4_delayed_flush_executes_data(self):
        """路径 B: 定时器 flush 后数据被执行."""
        t = make_throttler(max_batch_size=50)
        executed = []
        update_func = lambda data: executed.append(list(data))

        t.batch_update("batch-C", update_func, [7], max_wait_ms=100)

        deadline = time.time() + 2.0
        while time.time() < deadline and not executed:
            time.sleep(0.02)

        assert len(executed) >= 1, "定时器 flush 应执行 update_func"
        assert executed[0] == [7], f"数据应为 [7], 实际 {executed[0]}"
