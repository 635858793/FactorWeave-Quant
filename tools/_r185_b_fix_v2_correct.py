"""
R185-B HVD-182-3 第二轮修复 v2 (精确匹配)
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_event_dispatcher_async_failure():
    path = PROJECT_ROOT / "core/events/event_dispatcher.py"
    src = path.read_text(encoding="utf-8")

    # 改写 _submit_to_executor 整个方法, _safe_dispatch 改为闭包直接记 events_failed
    old_block = '''        # R83-B P0-9 内存泄漏防御: add_done_callback 清理 future
        def _on_done(fut: Future) -> None:
            with lock:
                futures_set.discard(fut)
            try:
                if fut.exception() is not None:
                    with lock:
                        stats["events_failed"] += 1
                    # R51 §7.1 #5 + R174: 异步路径失败仅 warning, 不影响主流程
                    logger.warning(
                        f"[R185-B HVD-182-3 async] executor handler 异常: "
                        f"event={event!r} err={fut.exception()}"
                    , exc_info=True,)
                else:
                    with lock:
                        stats["events_dispatched"] += 1
            except Exception as cb_exc:
                logger.warning(
                    f"[R185-B HVD-182-3] _on_done callback 自身异常: {cb_exc}"
                , exc_info=True,)

        # 锁内只做 future 集合 add (短锁, 微秒级)
        future = executor.submit(self._safe_dispatch, event, kwargs)
        with lock:
            futures_set.add(future)
            stats["events_published"] += 1
        future.add_done_callback(_on_done)
        return future

    def _safe_dispatch(
        self,
        event: Union[BaseEvent, str],
        kwargs: Dict[str, Any],
    ) -> None:
        """
        实际 EventBus.publish 包装 (R75-DEV-4 fire-and-forget)

        Why: 异步路径, 失败仅 warning 不抛 (R8 #7 不影响主流程 + R51 软解析降级)
        """
        try:
            # 兼容 EventBus.publish 签名: publish(event, **kwargs)
            self._bus.publish(event, **kwargs)
        except Exception as e:
            # R51 §7.1 #5: 异步路径失败仅 warning, 业务方不感知 (主流程不阻塞)
            # R185-B 修复 (2026-07-25): kwargs 用 str() 包装, 避免 loguru.format KeyError.
            logger.warning(
                "[R185-B HVD-182-3 async] 异步分发失败 (非致命): "
                "event={event!r} kwargs={kwargs_str} err={err_str}",
                event=event,
                kwargs_str=str(kwargs),
                err_str=str(e),
                exc_info=True,
            )'''

    new_block = '''        # R185-B 修复 (2026-07-25): _safe_dispatch 改为闭包直接捕获 lock/stats,
        # 异常时立即 events_failed += 1 (与 _on_done 解耦, 避免依赖 fut.exception() 判定).
        # test_async_failure_only_warning 验证 (patch bus.publish 抛 RuntimeError, events_failed>=1).
        def _safe_dispatch() -> None:
            """实际 EventBus.publish 包装 (R75-DEV-4 fire-and-forget, 闭包形式)
            异常时直接增加 events_failed, _on_done 只需处理 success 路径.
            """
            try:
                # 兼容 EventBus.publish 签名: publish(event, **kwargs)
                self._bus.publish(event, **kwargs)
            except Exception as e:
                # 立即记录 failed (闭包捕获 lock/stats, 不依赖 _on_done)
                with lock:
                    stats["events_failed"] += 1
                # R51 §7.1 #5: 异步路径失败仅 warning, 业务方不感知 (主流程不阻塞)
                # R185-B 修复: kwargs 用 str() 包装, 避免 loguru.format KeyError.
                logger.warning(
                    "[R185-B HVD-182-3 async] 异步分发失败 (非致命): "
                    "event={event!r} kwargs={kwargs_str} err={err_str}",
                    event=event,
                    kwargs_str=str(kwargs),
                    err_str=str(e),
                    exc_info=True,
                )

        # R83-B P0-9 内存泄漏防御: add_done_callback 清理 future
        def _on_done(fut: Future) -> None:
            with lock:
                futures_set.discard(fut)
            try:
                if fut.exception() is None:
                    # dispatch 成功: 增加 events_dispatched
                    # 失败已被 _safe_dispatch 闭包内直接记录, 这里不重复
                    with lock:
                        stats["events_dispatched"] += 1
            except Exception as cb_exc:
                logger.warning(
                    f"[R185-B HVD-182-3] _on_done callback 自身异常: {cb_exc}"
                , exc_info=True,)

        # 锁内只做 future 集合 add (短锁, 微秒级)
        future = executor.submit(_safe_dispatch)
        with lock:
            futures_set.add(future)
            stats["events_published"] += 1
        future.add_done_callback(_on_done)
        return future'''

    if old_block not in src:
        print(f"FAIL: 找不到 _submit_to_executor + _safe_dispatch 原文 in {path}")
        return False
    src = src.replace(old_block, new_block)
    print(f"OK: 修复 2 - {path} _submit_to_executor 改为 _safe_dispatch 闭包 + _on_done 简化 (合并替换)")

    path.write_text(src, encoding="utf-8")
    return True


if __name__ == "__main__":
    ok2 = fix_event_dispatcher_async_failure()
    if ok2:
        print("\nv2 修复完成, 请重新跑 pytest 验证")
        sys.exit(0)
    else:
        print("\nv2 修复失败")
        sys.exit(1)
