from loguru import logger
"""
更新节流器模块
提供UI更新频率控制、防抖机制和批量更新功能
"""

import threading
import time
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from queue import Queue, Empty, PriorityQueue
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

logger = logger

@dataclass
class UpdateRequest:
    """更新请求"""
    id: str
    update_func: Callable
    data: Any
    priority: int = 1  # 优先级，数字越小优先级越高
    created_time: float = field(default_factory=time.time)

    def __lt__(self, other):
        """支持优先级排序"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_time < other.created_time

class UpdateThrottler:
    """更新节流器"""

    def __init__(self, min_interval_ms: int = 150, max_batch_size: int = 50):
        """
        初始化更新节流器

        Args:
            min_interval_ms: 最小更新间隔（毫秒）
            max_batch_size: 最大批量更新大小
        """
        self.min_interval_ms = min_interval_ms
        self.max_batch_size = max_batch_size

        # 更新队列 - 使用优先级队列
        self.update_queue = PriorityQueue()

        # 防抖定时器
        self.debounce_timers: Dict[str, threading.Timer] = {}

        # 最后更新时间
        self.last_update_times: Dict[str, float] = {}

        # 批量更新缓存
        self.batch_updates: Dict[str, List[UpdateRequest]] = defaultdict(list)

        # 运行状态
        self.is_running = False
        self.worker_thread = None

        # 优先级级别和对应的最小间隔（毫秒）
        self.priority_levels = {
            'critical': 0,    # 立即执行，不节流
            'high': 50,       # 50ms最小间隔
            'normal': 150,    # 默认150ms间隔
            'low': 300        # 300ms间隔
        }

        # 统计信息
        self.stats = {
            'total_requests': 0,
            'throttled_requests': 0,
            'batch_updates': 0,
            'debounced_requests': 0,
            'critical_updates': 0,
            'high_priority_updates': 0,
            'normal_priority_updates': 0,
            'low_priority_updates': 0
        }

        # 锁
        self.stats_lock = threading.Lock()
        self.timers_lock = threading.Lock()
        self.batch_lock = threading.Lock()

        logger.info(
            f"UpdateThrottler初始化完成 - 间隔: {min_interval_ms}ms, 批量大小: {max_batch_size}")

    def start(self):
        """启动节流器"""
        if self.is_running:
            return

        self.is_running = True

        # 启动工作线程
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="UpdateThrottler-Worker",
            daemon=True
        )
        self.worker_thread.start()

        logger.info("UpdateThrottler已启动")

    def stop(self):
        """停止节流器"""
        if not self.is_running:
            return

        self.is_running = False

        # 取消所有防抖定时器
        with self.timers_lock:
            for timer in self.debounce_timers.values():
                timer.cancel()
            self.debounce_timers.clear()

        # 等待队列清空
        while not self.update_queue.empty():
            time.sleep(0.1)

        logger.info("UpdateThrottler已停止")

    def _worker_loop(self):
        """工作线程主循环"""
        while self.is_running:
            try:
                # 获取更新请求（带超时）
                request = self.update_queue.get(timeout=1.0)

                # 处理更新请求
                self._process_update_request(request)

                self.update_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                logger.error(f"更新节流器工作线程处理请求时出错: {e}")

    def _process_update_request(self, request: UpdateRequest):
        """处理更新请求"""
        current_time = time.time()
        last_update = self.last_update_times.get(request.id, 0)
        time_since_last = (current_time - last_update) * 1000  # 转换为毫秒

        # 获取该优先级的最小间隔
        priority_name = self._get_priority_name(request.priority)
        interval = self.priority_levels.get(
            priority_name, self.min_interval_ms)

        # 关键更新总是立即执行
        if priority_name == 'critical':
            with self.stats_lock:
                self.stats['critical_updates'] += 1

            try:
                # 立即执行更新
                request.update_func(request.data)

                # 更新最后执行时间
                self.last_update_times[request.id] = time.time()

                return
            except Exception as e:
                logger.error(f"执行关键更新请求 {request.id} 失败: {e}")
                return

        # 更新优先级统计
        with self.stats_lock:
            if priority_name == 'high':
                self.stats['high_priority_updates'] += 1
            elif priority_name == 'normal':
                self.stats['normal_priority_updates'] += 1
            elif priority_name == 'low':
                self.stats['low_priority_updates'] += 1

        # 检查是否需要节流
        if time_since_last < interval:
            with self.stats_lock:
                self.stats['throttled_requests'] += 1

            # 延迟执行
            delay = (interval - time_since_last) / 1000.0
            time.sleep(delay)

        try:
            # 执行更新
            request.update_func(request.data)

            # 更新最后执行时间
            self.last_update_times[request.id] = time.time()

        except Exception as e:
            logger.error(f"执行更新请求 {request.id} 失败: {e}")

    def _get_priority_name(self, priority: int) -> str:
        """根据优先级数值获取优先级名称"""
        if priority == 0:
            return 'critical'
        elif priority == 1:
            return 'high'
        elif priority == 2:
            return 'normal'
        elif priority >= 3:
            return 'low'
        return 'normal'

    def request_update(self, update_id: str, update_func: Callable, data: Any,
                       priority: int = 1, force: bool = False) -> bool:
        """
        请求更新

        Args:
            update_id: 更新ID
            update_func: 更新函数
            data: 更新数据
            priority: 优先级
            force: 是否强制更新（忽略节流）

        Returns:
            bool: 是否成功提交
        """
        if not self.is_running:
            logger.warning("节流器未启动，无法提交更新请求")
            return False

        with self.stats_lock:
            self.stats['total_requests'] += 1

        # 强制更新或关键更新
        if force or priority == 0:
            try:
                update_func(data)
                self.last_update_times[update_id] = time.time()

                if priority == 0:
                    with self.stats_lock:
                        self.stats['critical_updates'] += 1

                return True
            except Exception as e:
                logger.error(f"强制更新 {update_id} 失败: {e}")
                return False

        # 创建更新请求
        request = UpdateRequest(
            id=update_id,
            update_func=update_func,
            data=data,
            priority=priority
        )

        try:
            self.update_queue.put(request)
            return True
        except Exception as e:
            logger.error(f"提交更新请求 {update_id} 失败: {e}")
            return False

    def debounce_update(self, update_id: str, update_func: Callable, data: Any,
                        delay_ms: int = 300) -> bool:
        """
        防抖更新

        在指定延迟时间内的重复调用会被忽略，只有最后一次调用会执行

        Args:
            update_id: 更新ID
            update_func: 更新函数
            data: 更新数据
            delay_ms: 延迟时间（毫秒）

        Returns:
            bool: 是否成功提交
        """
        if not self.is_running:
            logger.warning("节流器未启动，无法提交防抖更新请求")
            return False

        with self.stats_lock:
            self.stats['total_requests'] += 1
            self.stats['debounced_requests'] += 1

        # 取消现有定时器
        with self.timers_lock:
            if update_id in self.debounce_timers:
                self.debounce_timers[update_id].cancel()

            # 创建新定时器
            def delayed_update():
                try:
                    update_func(data)
                    self.last_update_times[update_id] = time.time()
                    with self.timers_lock:
                        if update_id in self.debounce_timers:
                            del self.debounce_timers[update_id]
                except Exception as e:
                    logger.error(f"执行防抖更新 {update_id} 失败: {e}")

            timer = threading.Timer(delay_ms / 1000.0, delayed_update)
            timer.daemon = True
            self.debounce_timers[update_id] = timer
            timer.start()

        return True

    def batch_update(self, batch_id: str, update_func: Callable, data: Any,
                     max_wait_ms: int = 100) -> bool:
        """
        批量更新

        收集一段时间内的更新请求，一次性执行

        Args:
            batch_id: 批量更新ID
            update_func: 更新函数
            data: 更新数据
            max_wait_ms: 最大等待时间（毫秒）

        Returns:
            bool: 是否成功提交
        """
        if not self.is_running:
            logger.warning("节流器未启动，无法提交批量更新请求")
            return False

        with self.stats_lock:
            self.stats['total_requests'] += 1
            self.stats['batch_updates'] += 1

        # 创建更新请求
        request = UpdateRequest(
            id=f"{batch_id}_{int(time.time() * 1000)}",
            update_func=update_func,
            data=data,
            priority=2  # 批量更新使用普通优先级
        )

        # 添加到批量更新缓存
        # R238-P1-1 防死锁: _flush_batch 内部会自行获取 batch_lock,
        # 若在此锁内调用将同线程重入普通 Lock → 死锁. 故锁内仅收集状态, flush 移到锁外.
        need_flush = False
        is_first = False
        with self.batch_lock:
            self.batch_updates[batch_id].append(request)

            # 检查是否需要刷新批量更新
            need_flush = self._should_flush_batch(batch_id, max_wait_ms)
            is_first = len(self.batch_updates[batch_id]) == 1

        if need_flush:
            self._flush_batch(batch_id)
        elif is_first:
            # 第一个请求，启动定时器
            def delayed_flush():
                self._flush_batch(batch_id)

            timer = threading.Timer(max_wait_ms / 1000.0, delayed_flush)
            timer.daemon = True
            timer.start()

        return True

    def _should_flush_batch(self, batch_id: str, max_wait_ms: int) -> bool:
        """检查是否应该刷新批量更新"""
        batch = self.batch_updates.get(batch_id, [])
        if not batch:
            return False

        # 达到最大批量大小
        if len(batch) >= self.max_batch_size:
            return True

        # 第一个请求已经等待足够长时间
        first_request = batch[0]
        elapsed_ms = (time.time() - first_request.created_time) * 1000
        return elapsed_ms >= max_wait_ms

    def _flush_batch(self, batch_id: str):
        """刷新批量更新"""
        with self.batch_lock:
            if batch_id not in self.batch_updates or not self.batch_updates[batch_id]:
                return

            batch = self.batch_updates[batch_id]

            # 合并所有数据
            combined_data = []
            for request in batch:
                if isinstance(request.data, list):
                    combined_data.extend(request.data)
                else:
                    combined_data.append(request.data)

            # 获取第一个请求的更新函数
            update_func = batch[0].update_func

            # 清空批量更新缓存
            del self.batch_updates[batch_id]

        try:
            # 执行批量更新
            update_func(combined_data)
            self.last_update_times[batch_id] = time.time()
        except Exception as e:
            logger.error(f"执行批量更新 {batch_id} 失败: {e}")

    def clear_pending_updates(self, update_id: str = None):
        """
        清除待处理的更新请求

        Args:
            update_id: 更新ID，如果为None则清除所有请求
        """
        # 清除防抖定时器
        with self.timers_lock:
            if update_id is not None:
                if update_id in self.debounce_timers:
                    self.debounce_timers[update_id].cancel()
                    del self.debounce_timers[update_id]
            else:
                for timer in self.debounce_timers.values():
                    timer.cancel()
                self.debounce_timers.clear()

        # 清除批量更新缓存
        with self.batch_lock:
            if update_id is not None:
                if update_id in self.batch_updates:
                    del self.batch_updates[update_id]
            else:
                self.batch_updates.clear()

        # 清除更新队列比较复杂，因为PriorityQueue不支持直接移除元素
        # 这里我们创建一个新队列，并将不需要清除的请求重新加入
        if update_id is not None:
            new_queue = PriorityQueue()
            while not self.update_queue.empty():
                try:
                    request = self.update_queue.get_nowait()
                    if request.id != update_id:
                        new_queue.put(request)
                except Empty:
                    break
            self.update_queue = new_queue
        else:
            # 清空整个队列
            while not self.update_queue.empty():
                try:
                    self.update_queue.get_nowait()
                except Empty:
                    break

    def get_throttler_status(self) -> Dict[str, Any]:
        """获取节流器状态"""
        with self.stats_lock:
            stats = self.stats.copy()

        status = {
            'stats': stats,
            'queue_size': self.update_queue.qsize(),
            'debounce_timers': len(self.debounce_timers),
            'batch_updates': {k: len(v) for k, v in self.batch_updates.items()},
            'is_running': self.is_running,
            'min_interval_ms': self.min_interval_ms,
            'max_batch_size': self.max_batch_size,
            'priority_levels': self.priority_levels.copy()
        }

        return status

    def set_throttle_interval(self, interval_ms: int):
        """设置最小更新间隔"""
        self.min_interval_ms = max(10, interval_ms)  # 确保至少10ms
        self.priority_levels['normal'] = self.min_interval_ms
        self.priority_levels['high'] = max(10, self.min_interval_ms // 3)
        self.priority_levels['low'] = self.min_interval_ms * 2

    def set_batch_size(self, batch_size: int):
        """设置最大批量更新大小"""
        self.max_batch_size = max(1, batch_size)

# 全局实例
_update_throttler = None

def get_update_throttler() -> UpdateThrottler:
    """获取全局更新节流器实例"""
    global _update_throttler
    if _update_throttler is None:
        _update_throttler = UpdateThrottler()
        _update_throttler.start()
    return _update_throttler

def initialize_throttler(min_interval_ms: int = 150, max_batch_size: int = 50):
    """初始化全局更新节流器"""
    global _update_throttler
    if _update_throttler is not None:
        _update_throttler.stop()
    _update_throttler = UpdateThrottler(min_interval_ms, max_batch_size)
    _update_throttler.start()
    return _update_throttler

def shutdown_throttler():
    """关闭全局更新节流器"""
    global _update_throttler
    if _update_throttler is not None:
        _update_throttler.stop()
        _update_throttler = None

# 便捷函数
def throttle_update(update_id: str, update_func: Callable, data: Any,
                    priority: int = 1, force: bool = False) -> bool:
    """节流更新便捷函数"""
    return get_update_throttler().request_update(update_id, update_func, data, priority, force)

def debounce_update(update_id: str, update_func: Callable, data: Any,
                    delay_ms: int = 300) -> bool:
    """防抖更新便捷函数"""
    return get_update_throttler().debounce_update(update_id, update_func, data, delay_ms)

def batch_update(batch_id: str, update_func: Callable, data: Any,
                 max_wait_ms: int = 100) -> bool:
    """批量更新便捷函数"""
    return get_update_throttler().batch_update(batch_id, update_func, data, max_wait_ms)
