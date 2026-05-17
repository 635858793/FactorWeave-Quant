"""
异步工具函数

提供安全的异步执行工具，统一处理事件循环生命周期管理。
避免 asyncio.run() 在已有事件循环的上下文中引发 RuntimeError。
"""

import asyncio
from typing import Coroutine, Any, Optional
from loguru import logger


def run_async_safe(coro: Coroutine, timeout: Optional[float] = None) -> Any:
    """
    安全地运行异步协程，自动处理事件循环状态。

    优先级：
    1. 如果已有运行中的事件循环 → 使用 asyncio.create_task（不阻塞，返回 None）
    2. 如果存在事件循环但未运行 → 使用 loop.run_until_complete()
    3. 如果没有事件循环 → 使用 asyncio.run() 创建新的

    Args:
        coro: 要执行的协程
        timeout: 超时时间（秒），仅对 run_until_complete 和 asyncio.run 有效

    Returns:
        协程的返回值，如果使用 create_task 则返回 None
    """
    try:
        loop = asyncio.get_running_loop()
        logger.debug("检测到运行中的事件循环，使用 create_task 调度协程")
        asyncio.create_task(coro)
        return None
    except RuntimeError:
        pass

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")

        logger.debug("使用现有事件循环运行协程")
        if timeout is not None:
            return loop.run_until_complete(
                asyncio.wait_for(coro, timeout=timeout)
            )
        return loop.run_until_complete(coro)
    except RuntimeError:
        logger.debug("创建新事件循环运行协程")
        return asyncio.run(coro)


def run_async_blocking(coro: Coroutine, timeout: Optional[float] = None) -> Any:
    """
    阻塞方式运行异步协程，始终等待结果返回。

    与 run_async_safe 的区别：即使在运行中的事件循环中也会阻塞等待结果。
    使用 nest_asyncio 来支持嵌套事件循环。

    Args:
        coro: 要执行的协程
        timeout: 超时时间（秒）

    Returns:
        协程的返回值
    """
    try:
        loop = asyncio.get_running_loop()
        import nest_asyncio
        nest_asyncio.apply()
        logger.debug("检测到运行中的事件循环，使用 nest_asyncio 嵌套执行")
        task = loop.create_task(coro)
        if timeout is not None:
            return loop.run_until_complete(
                asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            )
        return loop.run_until_complete(asyncio.shield(task))
    except RuntimeError:
        return asyncio.run(coro)
