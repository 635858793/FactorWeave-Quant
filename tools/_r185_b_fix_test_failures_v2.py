"""
R185-B HVD-182-3 第二轮修复脚本 (2 项)

修复:
1. self_loop_detector.py: 触发后 cool-down 5s, 期间内相同 key 直接返回 True
   (R8 铁律 #6 + R83-B P0-6 防御性升级, 防止 self-loop 风暴)
2. event_dispatcher.py: _safe_dispatch 异常时直接记 events_failed (与 _on_done 解耦)
   _on_done 改为只处理 dispatch 成功路径
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")


def fix_self_loop_detector_cooldown():
    """修复 1: SelfLoopDetector 加 cool-down 机制 (触发后 5s 内后续都 break)"""
    path = PROJECT_ROOT / "core/events/self_loop_detector.py"
    src = path.read_text(encoding="utf-8")

    # 1) __init__ 加 _cool_down 字段
    old_init_stats = '''        self._window_seconds = window_seconds
        self._trigger_threshold = trigger_threshold
        self._window: Dict[str, list] = {}
        # R84 P0-6 模板: Lock → RLock 防御性升级
        self._window_lock = RLock()
        # 统计: 用于可观测性 (R100-F 经验)
        self._stats = {
            "total_checks": 0,
            "self_loops_detected": 0,
            "active_keys": 0,
        }'''

    new_init_stats = '''        self._window_seconds = window_seconds
        self._trigger_threshold = trigger_threshold
        self._window: Dict[str, list] = {}
        # R185-B 修复 (2026-07-25): cool-down 机制 (R8 铁律 #6 + R83-B P0-6 防御性升级)
        # Why: 原实现触发后清空 _window, 后续从 1 重新计数, 业务方在 5s 窗口内
        #      仍可绕过 self-loop 检测 → test_self_loop_blocks_subsequent_publish FAIL.
        # Fix: 触发后记录 _cool_down[event_key] = trigger_time, 5s 内任何相同 key
        #      直接返回 True (不计数, 不重新进入 _window), 5s 过后才重新进入 _window 计数.
        self._cool_down: Dict[str, float] = {}
        # R84 P0-6 模板: Lock → RLock 防御性升级
        self._window_lock = RLock()
        # 统计: 用于可观测性 (R100-F 经验)
        self._stats = {
            "total_checks": 0,
            "self_loops_detected": 0,
            "active_keys": 0,
            "cool_down_active": 0,
        }'''

    if old_init_stats not in src:
        print(f"FAIL: 找不到 __init__ _stats 字段 in {path}")
        return False
    src = src.replace(old_init_stats, new_init_stats)
    print(f"OK: 修复 1a - {path} __init__ 加 _cool_down 字段")

    # 2) is_self_loop 加 cool-down 检查
    old_is_self_loop = '''    def is_self_loop(self, event_key: str) -> bool:
        """
        检查 event_key 是否构成 self-loop (5s 窗口 + 3 次触发)

        Args:
            event_key: 事件 key (由 EventDispatcher._build_event_key 构造)

        Returns:
            bool: True=触发 self-loop (业务方应 break), False=正常

        副作用:
        - 每次调用都记录 hit_timestamp (即便未触发也记录, 用于后续检查)
        - 懒清理 5s 之前的 hit (避免内存泄漏)
        """
        with self._window_lock:
            self._stats["total_checks"] += 1
            now = time.time()

            # 懒清理: 移除 5s 之前的 hit
            cutoff = now - self._window_seconds
            if event_key in self._window:
                self._window[event_key] = [
                    t for t in self._window[event_key] if t > cutoff
                ]
                if not self._window[event_key]:
                    del self._window[event_key]

            # 记录本次 hit
            if event_key not in self._window:
                self._window[event_key] = []
            self._window[event_key].append(now)

            # 检查 5s 窗口内 hit 数
            hit_count = len(self._window[event_key])
            if hit_count >= self._trigger_threshold:
                self._stats["self_loops_detected"] += 1
                # 触发后清空, 给业务方恢复机会 (避免永久屏蔽)
                del self._window[event_key]
                return True

            # 更新 active_keys 统计 (锁内更新, 锁外读取)
            self._stats["active_keys"] = len(self._window)
            return False'''

    new_is_self_loop = '''    def is_self_loop(self, event_key: str) -> bool:
        """
        检查 event_key 是否构成 self-loop (5s 窗口 + 3 次触发 + cool-down)

        Args:
            event_key: 事件 key (由 EventDispatcher._build_event_key 构造)

        Returns:
            bool: True=触发 self-loop (业务方应 break), False=正常

        副作用:
        - 每次调用都记录 hit_timestamp (即便未触发也记录, 用于后续检查)
        - 懒清理 5s 之前的 hit (避免内存泄漏)
        - R185-B cool-down: 触发后 5s 内相同 key 直接返回 True, 不重新计数

        R8 铁律 #6: 防止链式 self-loop 风暴, 业务方在 cool-down 期内被自动 break.
        """
        with self._window_lock:
            self._stats["total_checks"] += 1
            now = time.time()
            cutoff = now - self._window_seconds

            # R185-B 修复 (2026-07-25) Step 1: cool-down 检查
            # 触发后 5s 内, 任何相同 key 直接返回 True (不计数, 不重新进入 _window)
            if event_key in self._cool_down:
                trigger_time = self._cool_down[event_key]
                if trigger_time > cutoff:
                    # cool-down 期内, 仍记为 detected (累计计数便于观察)
                    self._stats["self_loops_detected"] += 1
                    return True
                else:
                    # cool-down 过期, 清空
                    del self._cool_down[event_key]

            # 懒清理: 移除 5s 之前的 hit
            if event_key in self._window:
                self._window[event_key] = [
                    t for t in self._window[event_key] if t > cutoff
                ]
                if not self._window[event_key]:
                    del self._window[event_key]

            # 记录本次 hit
            if event_key not in self._window:
                self._window[event_key] = []
            self._window[event_key].append(now)

            # 检查 5s 窗口内 hit 数
            hit_count = len(self._window[event_key])
            if hit_count >= self._trigger_threshold:
                self._stats["self_loops_detected"] += 1
                # R185-B 修复: 触发后清空 _window + 记录 cool-down (5s 内相同 key 直接 break)
                del self._window[event_key]
                self._cool_down[event_key] = now
                # 更新 cool_down_active 统计
                self._stats["cool_down_active"] = len(self._cool_down)
                return True

            # 更新 active_keys 统计 (锁内更新, 锁外读取)
            self._stats["active_keys"] = len(self._window)
            self._stats["cool_down_active"] = len(self._cool_down)
            return False'''

    if old_is_self_loop not in src:
        print(f"FAIL: 找不到 is_self_loop 原文 in {path}")
        return False
    src = src.replace(old_is_self_loop, new_is_self_loop)
    print(f"OK: 修复 1b - {path} is_self_loop 加 cool-down 检查")
    path.write_text(src, encoding="utf-8")
    return True


def fix_event_dispatcher_async_failure():
    """修复 2: _safe_dispatch 异常时直接记 events_failed, _on_done 改为只处理 dispatch 成功"""
    path = PROJECT_ROOT / "core/events/event_dispatcher.py"
    src = path.read_text(encoding="utf-8")

    # 重写 _submit_to_executor 整个方法, 让 _safe_dispatch 内部直接记 events_failed
    old_submit = '''        # R83-B P0-9 内存泄漏防御: add_done_callback 清理 future
        def _on_done(fut: Future) -> None:
            with lock:
                futures_set.discard(fut)
            try:
                if fut.exception() is not None:
                    with lock:
                        stats["events_failed"] += 1
                    # R51 §7.1 #5 + R174: 异步路径失败仅 warning, 不影响主流程
                    # R185-B 修复 (2026-07-25): err 用 str() 包装, 避免 loguru.format KeyError.
                    logger.warning(
                        "[R185-B HVD-182-3 async] executor handler 异常: "
                        "event={event!r} err={err_str}",
                        event=event,
                        err_str=str(fut.exception()),
                        exc_info=True,
                    )
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

    new_submit = '''        # R185-B 修复 (2026-07-25): _safe_dispatch 改为闭包 (closure) 直接捕获 lock/stats,
        # 异常时立即 events_failed += 1 (与 _on_done 解耦, 避免依赖 fut.exception() 判定).
        # test_async_failure_only_warning 验证 (patch bus.publish 抛 RuntimeError, events_failed>=1).
        def _safe_dispatch() -> None:
            """实际 EventBus.publish 包装 (R75-DEV-4 fire-and-forget)
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

    if old_submit not in src:
        print(f"FAIL: 找不到 _submit_to_executor 原文 in {path}")
        return False
    src = src.replace(old_submit, new_submit)
    print(f"OK: 修复 2 - {path} _submit_to_executor 改为 _safe_dispatch 闭包 + _on_done 简化")

    # 删除原 _safe_dispatch 实例方法 (被闭包替代)
    old_safe_dispatch = '''    def _safe_dispatch(
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
            )

    @staticmethod
    def _build_event_key(event: Union[BaseEvent, str], **kwargs: Any) -> str:'''

    new_safe_dispatch = '''    @staticmethod
    def _build_event_key(event: Union[BaseEvent, str], **kwargs: Any) -> str:'''

    if old_safe_dispatch in src:
        src = src.replace(old_safe_dispatch, new_safe_dispatch)
        print(f"OK: 修复 2b - {path} 删除原 _safe_dispatch 实例方法 (被闭包替代)")
    else:
        print(f"WARN: 找不到 _safe_dispatch 原文, 可能已删除或格式略不同")

    path.write_text(src, encoding="utf-8")
    return True


if __name__ == "__main__":
    ok1 = fix_self_loop_detector_cooldown()
    ok2 = fix_event_dispatcher_async_failure()
    if ok1 and ok2:
        print("\n第二轮修复完成, 请重新跑 pytest 验证")
        sys.exit(0)
    else:
        print("\n第二轮修复失败, 请检查")
        sys.exit(1)
