#!/usr/bin/env python3
"""
性能数据更新管理器
采用事件驱动架构，统一管理性能数据的更新和分发，替代原有的定时器轮询机制，降低资源消耗
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from collections import defaultdict, deque
from loguru import logger

from PyQt5.QtCore import QObject, pyqtSignal

from .performance_events import (
    PerformanceEventType,
    SystemMetricsUpdatedEvent,
    StrategyPerformanceUpdatedEvent,
    AlgorithmMetricsUpdatedEvent,
    RiskMetricsUpdatedEvent,
    TradeMetricsUpdatedEvent,
    HealthCheckCompletedEvent,
    DataQualityUpdatedEvent,
    ResourceUsageUpdatedEvent,
    DataRefreshRequestedEvent,
    DataRefreshCompletedEvent,
    PerformanceAlertEvent
)
from .timer_manager import get_timer_manager, TimerPriority
from .thread_pool_manager import get_thread_pool_manager, TaskPriority


class UpdateStrategy(Enum):
    """更新策略"""
    EVENT_DRIVEN = auto()  # 事件驱动（推荐）
    TIMER_BASED = auto()   # 基于定时器（兼容）

@dataclass
class DataUpdateConfig:
    """数据更新配置"""
    tab_name: str
    update_interval: float  # 更新间隔（秒）
    update_strategy: UpdateStrategy = UpdateStrategy.EVENT_DRIVEN
    enabled: bool = True
    last_update_time: float = 0.0
    update_count: int = 0
    total_update_time: float = 0.0

class PerformanceDataUpdateManager(QObject):
    """
    性能数据更新管理器
    功能：
    1. 采用事件驱动架构，统一管理数据更新
    2. 支持多种更新策略
    3. 支持数据过滤和采样
    4. 提供更新统计信息
    """

    # 信号
    data_updated = pyqtSignal(str, str, object)  # 数据更新信号 (tab_name, data_type, data)
    update_error = pyqtSignal(str, str, str)  # 更新错误信号 (tab_name, data_type, error)
    update_completed = pyqtSignal(str, float)  # 更新完成信号 (tab_name, update_time)

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化数据更新管理器"""
        if self._initialized:
            return

        super().__init__()

        self._initialized = True
        self._configs: Dict[str, DataUpdateConfig] = {}
        self._data_collectors: Dict[str, Callable] = {}
        self._event_bus = None
        self._timer_manager = get_timer_manager()
        self._thread_pool_manager = get_thread_pool_manager()

        # 数据缓存
        self._data_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # 事件订阅
        self._subscribed_events: Set[str] = set()

        # 统计信息
        self._stats = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'total_update_time': 0.0,
            'avg_update_time': 0.0,
            'events_published': 0,
            'events_handled': 0
        }

        logger.info("性能数据更新管理器已初始化")

    def set_event_bus(self, event_bus):
        """设置事件总线"""
        self._event_bus = event_bus

    def register_tab(self,
                      tab_name: str,
                      data_collector: Callable,
                      update_interval: float = 5.0,
                      update_strategy: UpdateStrategy = UpdateStrategy.EVENT_DRIVEN,
                      enabled: bool = True) -> bool:
        """
        注册标签页
        Args:
            tab_name: 标签页名称
            data_collector: 数据收集函数
            update_interval: 更新间隔（秒）
            update_strategy: 更新策略
            enabled: 是否启用

        Returns:
            是否注册成功
        """
        try:
            if tab_name in self._configs:
                logger.warning(f"标签页已注册: {tab_name}")
                return False

            config = DataUpdateConfig(
                tab_name=tab_name,
                update_interval=update_interval,
                update_strategy=update_strategy,
                enabled=enabled
            )

            self._configs[tab_name] = config
            self._data_collectors[tab_name] = data_collector

            # 如果使用定时器策略，注册定时器
            if update_strategy == UpdateStrategy.TIMER_BASED:
                self._timer_manager.register_timer(
                    name=f"{tab_name}_update_timer",
                    interval=update_interval,
                    callback=lambda: self._collect_data(tab_name),
                    priority=TimerPriority.NORMAL,
                    enabled=enabled
                )

            logger.info(f"标签页已注册: {tab_name}, 更新策略: {update_strategy.name}, 更新间隔: {update_interval}s")
            return True

        except Exception as e:
            logger.error(f"注册标签页失败: {tab_name}, 错误: {e}")
            return False

    def unregister_tab(self, tab_name: str) -> bool:
        """
        注销标签页
        Args:
            tab_name: 标签页名称
        Returns:
            是否注销成功
        """
        try:
            if tab_name not in self._configs:
                logger.warning(f"标签页不存在: {tab_name}")
                return False

            config = self._configs[tab_name]

            # 如果使用定时器策略，注销定时器
            if config.update_strategy == UpdateStrategy.TIMER_BASED:
                self._timer_manager.unregister_timer(f"{tab_name}_update_timer")

            del self._configs[tab_name]
            del self._data_collectors[tab_name]

            # 清除缓存
            if tab_name in self._data_cache:
                del self._data_cache[tab_name]

            logger.info(f"标签页已注销: {tab_name}")
            return True

        except Exception as e:
            logger.error(f"注销标签页失败: {tab_name}, 错误: {e}")
            return False

    def enable_tab(self, tab_name: str) -> bool:
        """
        启用标签页
        Args:
            tab_name: 标签页名称
        Returns:
            是否启用成功
        """
        try:
            if tab_name not in self._configs:
                logger.warning(f"标签页不存在: {tab_name}")
                return False

            config = self._configs[tab_name]
            config.enabled = True

            # 如果使用定时器策略，恢复定时器
            if config.update_strategy == UpdateStrategy.TIMER_BASED:
                self._timer_manager.resume_timer(f"{tab_name}_update_timer")

            logger.info(f"标签页已启用: {tab_name}")
            return True

        except Exception as e:
            logger.error(f"启用标签页失败: {tab_name}, 错误: {e}")
            return False

    def disable_tab(self, tab_name: str) -> bool:
        """
        禁用标签页
        Args:
            tab_name: 标签页名称
        Returns:
            是否禁用成功
        """
        try:
            if tab_name not in self._configs:
                logger.warning(f"标签页不存在: {tab_name}")
                return False

            config = self._configs[tab_name]
            config.enabled = False

            # 如果使用定时器策略，暂停定时器
            if config.update_strategy == UpdateStrategy.TIMER_BASED:
                self._timer_manager.pause_timer(f"{tab_name}_update_timer")

            logger.info(f"标签页已禁用: {tab_name}")
            return True

        except Exception as e:
            logger.error(f"禁用标签页失败: {tab_name}, 错误: {e}")
            return False

    def request_data_refresh(self, tab_name: str, refresh_type: str = 'full') -> bool:
        """
        请求数据刷新

        Args:
            tab_name: 标签页名称
            refresh_type: 刷新类型 ('full', 'incremental')

        Returns:
            是否请求成功
        """
        try:
            if tab_name not in self._configs:
                logger.warning(f"标签页不存在: {tab_name}")
                return False

            # 发布数据刷新请求事件
            if self._event_bus:
                event = DataRefreshRequestedEvent(
                    tab_name=tab_name,
                    refresh_type=refresh_type
                )
                self._event_bus.publish(event)
                self._stats['events_published'] += 1

            # 异步收集数据
            self._thread_pool_manager.submit_task(
                func=self._collect_data,
                args=(tab_name,),
                priority=TaskPriority.HIGH
            )

            logger.info(f"数据刷新已请求: {tab_name}, 类型: {refresh_type}")
            return True

        except Exception as e:
            logger.error(f"请求数据刷新失败: {tab_name}, 错误: {e}")
            return False

    def _collect_data(self, tab_name: str) -> Optional[Dict[str, Any]]:
        """
        收集数据

        Args:
            tab_name: 标签页名称

        Returns:
            收集的数据
        """
        try:
            if tab_name not in self._configs:
                logger.warning(f"标签页不存在: {tab_name}")
                return None

            config = self._configs[tab_name]

            if not config.enabled:
                logger.debug(f"标签页已禁用，跳过数据收集: {tab_name}")
                return None

            # 检查更新间隔
            current_time = time.time()
            if current_time - config.last_update_time < config.update_interval:
                logger.debug(f"更新间隔未到，跳过数据收集: {tab_name}")
                return None

            start_time = time.time()

            # 调用数据收集函数
            data = self._data_collectors[tab_name]()

            # 更新配置
            config.last_update_time = current_time
            config.update_count += 1
            update_time = time.time() - start_time
            config.total_update_time += update_time

            # 更新统计信息
            self._stats['total_updates'] += 1
            self._stats['successful_updates'] += 1
            self._stats['total_update_time'] += update_time
            self._stats['avg_update_time'] = self._stats['total_update_time'] / self._stats['total_updates']

            # 缓存数据
            self._data_cache[tab_name] = data

            # 发送信号
            self.data_updated.emit(tab_name, 'data', data)
            self.update_completed.emit(tab_name, update_time)

            # 发布数据刷新完成事件
            if self._event_bus:
                event = DataRefreshCompletedEvent(
                    tab_name=tab_name,
                    refresh_type='full',
                    success=True,
                    refresh_time=update_time
                )
                self._event_bus.publish(event)
                self._stats['events_published'] += 1

            logger.debug(f"数据已收集: {tab_name}, 耗时: {update_time:.3f}s")
            return data

        except Exception as e:
            logger.error(f"收集数据失败: {tab_name}, 错误: {e}")

            # 更新统计信息
            self._stats['total_updates'] += 1
            self._stats['failed_updates'] += 1

            # 发送错误信号
            self.update_error.emit(tab_name, 'data', str(e))

            # 发布数据刷新完成事件（失败）
            if self._event_bus:
                event = DataRefreshCompletedEvent(
                    tab_name=tab_name,
                    refresh_type='full',
                    success=False,
                    error_message=str(e)
                )
                self._event_bus.publish(event)
                self._stats['events_published'] += 1

            return None

    def get_cached_data(self, tab_name: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存数据

        Args:
            tab_name: 标签页名称

        Returns:
            缓存的数据
        """
        if tab_name not in self._data_cache:
            return None

        return self._data_cache[tab_name]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            'registered_tabs': len(self._configs),
            'enabled_tabs': len([c for c in self._configs.values() if c.enabled]),
            'disabled_tabs': len([c for c in self._configs.values() if not c.enabled]),
            'tabs': {
                name: {
                    'update_interval': config.update_interval,
                    'update_strategy': config.update_strategy.name,
                    'enabled': config.enabled,
                    'update_count': config.update_count,
                    'total_update_time': config.total_update_time,
                    'avg_update_time': config.total_update_time / config.update_count if config.update_count > 0 else 0.0
                }
                for name, config in self._configs.items()
            }
        }

    def get_tab_info(self, tab_name: str) -> Optional[Dict[str, Any]]:
        """获取标签页信息"""
        if tab_name not in self._configs:
            return None

        config = self._configs[tab_name]
        return {
            'tab_name': config.tab_name,
            'update_interval': config.update_interval,
            'update_strategy': config.update_strategy.name,
            'enabled': config.enabled,
            'last_update_time': config.last_update_time,
            'update_count': config.update_count,
            'total_update_time': config.total_update_time,
            'avg_update_time': config.total_update_time / config.update_count if config.update_count > 0 else 0.0
        }


# 全局实例
_data_update_manager_instance: Optional[PerformanceDataUpdateManager] = None
_data_update_manager_lock = threading.Lock()


def get_data_update_manager() -> PerformanceDataUpdateManager:
    """获取数据更新管理器实例"""
    global _data_update_manager_instance

    if _data_update_manager_instance is None:
        with _data_update_manager_lock:
            if _data_update_manager_instance is None:
                _data_update_manager_instance = PerformanceDataUpdateManager()

    return _data_update_manager_instance

def initialize_data_update_manager(event_bus=None) -> PerformanceDataUpdateManager:
    """初始化数据更新管理器"""
    manager = get_data_update_manager()
    manager.set_event_bus(event_bus)
    return manager
