"""
R185-B HVD-182-3 测试失败修复脚本 (3 项)

修复:
1. self_loop_detector.py: reset() 同步重置 _stats["active_keys"]
2. event_dispatcher.py: _publish_critical logger f-string 内嵌 {} 触发 format KeyError
3. event_dispatcher.py: _safe_dispatch logger f-string 内嵌 {} 触发 format KeyError

策略: f-string 中 dict 渲染成 "{key: value}" 含花括号, loguru 内部 message.format(*args, **kwargs)
      会把它当 format 占位符. 修复: 用 str(kwargs) 替代 {kwargs}, 或用 logger.opt(exception=True).
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_self_loop_detector_reset():
    """修复 1: SelfLoopDetector.reset() 同步重置 _stats["active_keys"]"""
    path = PROJECT_ROOT / "core/events/self_loop_detector.py"
    src = path.read_text(encoding="utf-8")

    # 找到 reset 方法 (L125-136)
    # 把清空 _window 的逻辑补上 _stats["active_keys"] = 0
    old_reset = '''    def reset(self, event_key: Optional[str] = None) -> None:
        """
        重置状态 (测试用 / 业务方手动重置)

        Args:
            event_key: 若指定, 仅重置该 key; 若 None, 清空全部
        """
        with self._window_lock:
            if event_key is None:
                self._window.clear()
            elif event_key in self._window:
                del self._window[event_key]'''

    new_reset = '''    def reset(self, event_key: Optional[str] = None) -> None:
        """
        重置状态 (测试用 / 业务方手动重置)

        Args:
            event_key: 若指定, 仅重置该 key; 若 None, 清空全部

        R185-B 修复 (2026-07-25): 清空后同步重置 _stats["active_keys"],
        避免 get_stats() 返回陈旧值. test_reset_all 验证 active_keys==0.
        """
        with self._window_lock:
            if event_key is None:
                self._window.clear()
                # 同步重置 active_keys 统计, 与 _window 状态一致
                self._stats["active_keys"] = 0
            elif event_key in self._window:
                del self._window[event_key]
                self._stats["active_keys"] = len(self._window)'''

    if old_reset not in src:
        print(f"FAIL: 找不到 reset() 原文 in {path}")
        return False
    src = src.replace(old_reset, new_reset)
    path.write_text(src, encoding="utf-8")
    print(f"OK: 修复 1 - {path} reset() 同步重置 _stats[active_keys]")
    return True


def fix_event_dispatcher_loggers():
    """修复 2/3: event_dispatcher.py logger 避免 f-string 内嵌 {}"""
    path = PROJECT_ROOT / "core/events/event_dispatcher.py"
    src = path.read_text(encoding="utf-8")

    # 修复 _publish_critical logger (L229-232)
    old_critical_log = '''            logger.error(
                f"[R185-B HVD-182-3 CRITICAL FAIL] 同步直发失败: event={event!r} "
                f"kwargs={kwargs} err={e}"
            , exc_info=True,)'''

    new_critical_log = '''            # R185-B 修复 (2026-07-25): kwargs 改用 str() 包装, 避免 f-string
            # 渲染后 "kwargs={}" 内嵌花括号触发 loguru.message.format KeyError.
            # test_critical_failure_raises 验证 (patch bus.publish 抛 RuntimeError).
            logger.error(
                "[R185-B HVD-182-3 CRITICAL FAIL] 同步直发失败: event={event!r} "
                "kwargs={kwargs_str} err={err_str}",
                event=event,
                kwargs_str=str(kwargs),
                err_str=str(e),
                exc_info=True,
            )'''

    if old_critical_log not in src:
        print(f"FAIL: 找不到 _publish_critical logger 原文 in {path}")
        return False
    src = src.replace(old_critical_log, new_critical_log)
    print(f"OK: 修复 2 - {path} _publish_critical logger 改用 str() 包装")

    # 修复 _safe_dispatch logger (L338-341)
    old_async_log = '''            # R51 §7.1 #5: 异步路径失败仅 warning, 业务方不感知 (主流程不阻塞)
            logger.warning(
                f"[R185-B HVD-182-3 async] 异步分发失败 (非致命): "
                f"event={event!r} kwargs={kwargs} err={e}"
            , exc_info=True,)'''

    new_async_log = '''            # R51 §7.1 #5: 异步路径失败仅 warning, 业务方不感知 (主流程不阻塞)
            # R185-B 修复 (2026-07-25): kwargs 用 str() 包装, 避免 loguru.format KeyError.
            logger.warning(
                "[R185-B HVD-182-3 async] 异步分发失败 (非致命): "
                "event={event!r} kwargs={kwargs_str} err={err_str}",
                event=event,
                kwargs_str=str(kwargs),
                err_str=str(e),
                exc_info=True,
            )'''

    if old_async_log not in src:
        print(f"FAIL: 找不到 _safe_dispatch logger 原文 in {path}")
        return False
    src = src.replace(old_async_log, new_async_log)
    print(f"OK: 修复 3 - {path} _safe_dispatch logger 改用 str() 包装")

    # 修复 _on_done callback logger (L302-306) - 类似问题
    old_on_done_log = '''                # R51 §7.1 #5 + R174: 异步路径失败仅 warning, 不影响主流程
                logger.warning(
                    f"[R185-B HVD-182-3 async] executor handler 异常: "
                    f"event={event!r} err={fut.exception()}"
                , exc_info=True,)'''

    new_on_done_log = '''                # R51 §7.1 #5 + R174: 异步路径失败仅 warning, 不影响主流程
                # R185-B 修复 (2026-07-25): err 用 str() 包装, 避免 loguru.format KeyError.
                logger.warning(
                    "[R185-B HVD-182-3 async] executor handler 异常: "
                    "event={event!r} err={err_str}",
                    event=event,
                    err_str=str(fut.exception()),
                    exc_info=True,
                )'''

    if old_on_done_log in src:
        src = src.replace(old_on_done_log, new_on_done_log)
        print(f"OK: 修复 4 - {path} _on_done callback logger 改用 str() 包装 (防御性)")
    else:
        print(f"WARN: 找不到 _on_done logger 原文, 跳过 (可能已修复)")

    # 修复 SelfLoop warning logger (L185-188) - event_key 不含 {}, 但 format 参数检查
    # 实际 event_key = "OrderFilledEvent:order_id=O_LOOP" 不含花括号, 安全.
    # 但为防御性也修复, 把 exc_info=True 后的, 改 logger.opt(exception=True)
    old_selfloop_log = '''        if self._self_loop_detector.is_self_loop(event_key):
            logger.warning(
                f"[R185-B HVD-182-3 SelfLoopDetector] 事件 {event_key} 5s 窗口内触发 3 次, "
                f"自动 break 防止 self-loop 风暴 (R8 铁律 #6 + R83-B P0-6 防御)"
            , exc_info=True,)'''

    new_selfloop_log = '''        if self._self_loop_detector.is_self_loop(event_key):
            # R185-B 修复 (2026-07-25): event_key 不含花括号安全, 但统一改用
            # logger.opt(exception=True).warning 形式, 避免内嵌 {} 触发 format KeyError.
            logger.opt(exception=True).warning(
                f"[R185-B HVD-182-3 SelfLoopDetector] 事件 {event_key} 5s 窗口内触发 3 次, "
                f"自动 break 防止 self-loop 风暴 (R8 铁律 #6 + R83-B P0-6 防御)"
            )'''

    if old_selfloop_log in src:
        src = src.replace(old_selfloop_log, new_selfloop_log)
        print(f"OK: 修复 5 - {path} SelfLoop warning 改用 logger.opt(exception=True)")

    path.write_text(src, encoding="utf-8")
    return True


if __name__ == "__main__":
    ok1 = fix_self_loop_detector_reset()
    ok2 = fix_event_dispatcher_loggers()
    if ok1 and ok2:
        print("\n所有修复完成, 请重新跑 pytest 验证")
        sys.exit(0)
    else:
        print("\n修复失败, 请检查")
        sys.exit(1)
