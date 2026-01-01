from loguru import logger
"""
事件处理器模块

提供事件处理器的基类和实现，支持同步和异步事件处理。
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union
from .events import BaseEvent


class EventHandler(ABC):
    """
    事件处理器基类

    所有事件处理器都应该继承此类并实现handle方法。
    """

    def __init__(self, name: str = ""):
        """
        初始化事件处理器

        Args:
            name: 处理器名称
        """
        self.name = name or self.__class__.__name__
        self.enabled = True
        self.priority = 0  # 数值越大优先级越高

    @abstractmethod
    def handle(self, event: BaseEvent) -> Any:
        """
        处理事件

        Args:
            event: 要处理的事件

        Returns:
            处理结果
        """
        pass

    def can_handle(self, event: BaseEvent) -> bool:
        """
        检查是否可以处理指定事件

        Args:
            event: 要检查的事件

        Returns:
            是否可以处理
        """
        return self.enabled

    def __str__(self) -> str:
        return f"{self.name}(enabled={self.enabled}, priority={self.priority})"

class AsyncEventHandler(EventHandler):
    """
    异步事件处理器基类

    用于处理需要异步执行的事件。
    """

    @abstractmethod
    async def handle_async(self, event: BaseEvent) -> Any:
        """
        异步处理事件

        Args:
            event: 要处理的事件

        Returns:
            处理结果
        """
        pass

    def handle(self, event: BaseEvent) -> Any:
        """
        同步接口，内部调用异步处理

        Args:
            event: 要处理的事件

        Returns:
            处理结果
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在事件循环中，创建任务
                return asyncio.create_task(self.handle_async(event))
            else:
                # 如果没有事件循环，运行新的循环
                return loop.run_until_complete(self.handle_async(event))
        except RuntimeError:
            # 如果没有事件循环，创建新的
            return asyncio.run(self.handle_async(event))

class FunctionEventHandler(EventHandler):
    """
    函数事件处理器

    将普通函数包装成事件处理器。
    """

    def __init__(self, func: Callable[[BaseEvent], Any], name: str = ""):
        """
        初始化函数事件处理器

        Args:
            func: 处理函数
            name: 处理器名称
        """
        super().__init__(name or func.__name__)
        self.func = func

    def handle(self, event: BaseEvent) -> Any:
        """
        处理事件

        Args:
            event: 要处理的事件

        Returns:
            处理结果
        """
        try:
            return self.func(event)
        except Exception as e:
            logger.error(
                f"Event handler {self.name} failed to handle event {event.event_id}: {e}")
            raise

class ConditionalEventHandler(EventHandler):
    """
    条件事件处理器

    只有满足特定条件才会处理事件。
    """

    def __init__(self,
                 handler: EventHandler,
                 condition: Callable[[BaseEvent], bool],
                 name: str = ""):
        """
        初始化条件事件处理器

        Args:
            handler: 实际的事件处理器
            condition: 条件检查函数
            name: 处理器名称
        """
        super().__init__(name or f"Conditional({handler.name})")
        self.handler = handler
        self.condition = condition

    def handle(self, event: BaseEvent) -> Any:
        """
        处理事件

        Args:
            event: 要处理的事件

        Returns:
            处理结果
        """
        if self.condition(event):
            return self.handler.handle(event)
        return None

    def can_handle(self, event: BaseEvent) -> bool:
        """
        检查是否可以处理指定事件

        Args:
            event: 要检查的事件

        Returns:
            是否可以处理
        """
        return self.enabled and self.condition(event) and self.handler.can_handle(event)

class CompositeEventHandler(EventHandler):
    """
    复合事件处理器

    可以包含多个子处理器，按顺序执行。
    """

    def __init__(self, handlers: List[EventHandler], name: str = ""):
        """
        初始化复合事件处理器

        Args:
            handlers: 子处理器列表
            name: 处理器名称
        """
        super().__init__(name or "CompositeHandler")
        self.handlers = sorted(
            handlers, key=lambda h: h.priority, reverse=True)

    def handle(self, event: BaseEvent) -> List[Any]:
        """
        处理事件

        Args:
            event: 要处理的事件

        Returns:
            所有处理器的处理结果列表
        """
        results = []
        for handler in self.handlers:
            if handler.can_handle(event):
                try:
                    result = handler.handle(event)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Handler {handler.name} failed: {e}")
                    results.append(None)
        return results

    def add_handler(self, handler: EventHandler):
        """
        添加子处理器

        Args:
            handler: 要添加的处理器
        """
        self.handlers.append(handler)
        self.handlers.sort(key=lambda h: h.priority, reverse=True)

    def remove_handler(self, handler: EventHandler):
        """
        移除子处理器

        Args:
            handler: 要移除的处理器
        """
        if handler in self.handlers:
            self.handlers.remove(handler)
