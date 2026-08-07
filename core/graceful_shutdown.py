"""
优雅关闭管理器
确保程序退出时所有资源被正确释放，防止数据库文件损坏
"""
import atexit
import os
import signal
import sys
import threading
from loguru import logger
from typing import Callable, List


class GracefulShutdownManager:
    """
    优雅关闭管理器

    功能：
    1. 捕获系统信号（SIGTERM, SIGINT, SIGBREAK）
    2. 按注册顺序执行清理处理器
    3. 防止重复执行清理
    4. 记录详细的关闭日志
    """

    def __init__(self):
        self._cleanup_handlers: List[tuple[str, Callable]] = []
        self._is_shutting_down = False
        self._shutdown_signaled = False
        self._shutdown_lock = threading.Lock()
        self._register_signal_handlers()
        logger.info("优雅关闭管理器已初始化")

    def register_cleanup_handler(self, handler: Callable, name: str = None):
        """
        注册清理处理器

        Args:
            handler: 清理函数
            name: 处理器名称（用于日志）
        """
        if name is None:
            name = getattr(handler, '__name__', str(handler))

        self._cleanup_handlers.append((name, handler))
        logger.debug(f"注册清理处理器: {name}")

    def register_event_bus_cleanup(self):
        """注册 EventBus.dispose 兜底清理 (HVD-239-P1-005, 2026-08-02)

        Why: EventBus.dispose() (event_bus.py:670-689) 生产代码 0 调用方
             (Grep 实测仅 tests + tools/_r198_a_smoke.py:31) → 信号退出路径
             事件总线持 handler 引用/线程永不释放
        Fix: 注册兜底 handler, 在清理链末尾 (LIFO 最先注册最后执行) 释放
        TDD: tests/test_r239_p0_dispose_chains.py
        """
        def _dispose_event_bus():
            try:
                from core.events import get_event_bus
                bus = get_event_bus()
                if bus is not None:
                    bus.dispose()
            except Exception as e:
                logger.warning(f"EventBus dispose 兜底失败: {e}")

        self.register_cleanup_handler(_dispose_event_bus, name="event_bus_dispose_fallback")

    def _register_signal_handlers(self):
        """注册系统信号处理器"""
        def signal_handler(signum, frame):
            try:
                signal_name = signal.Signals(signum).name
            except Exception:
                signal_name = str(signum)

            try:
                logger.warning(f"🛑 收到退出信号: {signal_name}")
            except Exception:
                pass

            self._shutdown_signaled = True
            self._perform_shutdown()
            sys.exit(0)

        # 注册信号
        try:
            signal.signal(signal.SIGTERM, signal_handler)  # kill命令
            logger.debug("已注册SIGTERM信号处理器")
        except Exception:
            logger.warning("无法注册SIGTERM信号处理器")

        try:
            signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
            logger.debug("已注册SIGINT信号处理器")
        except Exception:
            logger.warning("无法注册SIGINT信号处理器")

        # Windows特有信号
        if sys.platform == "win32":
            try:
                signal.signal(signal.SIGBREAK, signal_handler)  # Ctrl+Break
                logger.debug("已注册SIGBREAK信号处理器（Windows）")
            except Exception:
                logger.warning("无法注册SIGBREAK信号处理器")

        # 注册atexit（程序正常退出时）
        atexit.register(self._atexit_shutdown)
        logger.debug("已注册atexit处理器")

    def _perform_shutdown(self):
        """执行关闭流程"""
        with self._shutdown_lock:
            if self._is_shutting_down:
                return

            self._is_shutting_down = True

        logger.info("=" * 70)
        logger.info("开始优雅关闭流程")
        logger.info("=" * 70)

        total_handlers = len(self._cleanup_handlers)
        success_count = 0
        failed_count = 0

        # 按注册的逆序执行清理（后进先出）
        for i, (name, handler) in enumerate(reversed(self._cleanup_handlers), 1):
            try:
                logger.info(f"[{i}/{total_handlers}] 执行清理: {name}")
                handler()
                logger.info(f"    {name} 清理完成")
                success_count += 1
            except Exception as e:
                logger.error(f"    ❌ {name} 清理失败: {e}")
                failed_count += 1
                # 继续执行其他清理，不中断

        logger.info("=" * 70)
        logger.info(f"优雅关闭完成: 成功 {success_count}/{total_handlers}, 失败 {failed_count}")
        logger.info("=" * 70)

    def _atexit_shutdown(self):
        """atexit 回调：仅在非信号触发的正常退出时执行关闭"""
        if self._shutdown_signaled:
            return
        try:
            self._perform_shutdown()
        except Exception:
            pass

    def shutdown_now(self):
        """立即执行关闭流程（手动调用）"""
        logger.warning("手动触发优雅关闭")
        self._perform_shutdown()


# 全局单例
_shutdown_manager_instance = None
_shutdown_manager_lock = threading.Lock()


def get_shutdown_manager() -> GracefulShutdownManager:
    """获取全局优雅关闭管理器单例"""
    global _shutdown_manager_instance

    if _shutdown_manager_instance is None:
        with _shutdown_manager_lock:
            if _shutdown_manager_instance is None:
                _shutdown_manager_instance = GracefulShutdownManager()

    return _shutdown_manager_instance


# 便捷访问
shutdown_manager = get_shutdown_manager()


__all__ = ['GracefulShutdownManager', 'get_shutdown_manager', 'shutdown_manager']
