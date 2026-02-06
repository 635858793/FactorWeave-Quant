from loguru import logger
#!/usr/bin/env python3
"""
UI优化模块

提供更好的UI刷新机制，替换QApplication.processEvents()的使用
使用信号/槽机制和异步处理来避免UI阻塞
"""

from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication
from typing import Callable, Any, Optional
import threading
import time

# 使用系统统一组件
from core.system_adapters import get_config

class UIOptimizer(QObject):
    """UI优化器 - 提供更好的UI刷新机制"""

    # 定义信号
    ui_update_requested = pyqtSignal()
    delayed_action_requested = pyqtSignal(object, int)  # 回调函数, 延迟时间

    def __init__(self):
        """初始化UI优化器"""
        super().__init__()
        self.logger = logger.bind(module=__name__)
        self.config = get_config()

        # 配置参数
        self.default_delay = self.config.get(
            'ui_optimizer', {}).get('default_delay', 0)
        self.max_update_frequency = self.config.get(
            'ui_optimizer', {}).get('max_update_frequency', 60)  # Hz

        # 更新频率控制
        self._last_update_time = 0
        self._min_update_interval = 1.0 / self.max_update_frequency

        # 连接信号
        self.delayed_action_requested.connect(self._handle_delayed_action)

        self.logger.info("UI优化器初始化完成")

    def schedule_ui_update(self, callback: Callable = None, delay: int = None) -> None:
        """调度UI更新，替换QApplication.processEvents()

        Args:
            callback: 可选的回调函数
            delay: 延迟时间（毫秒），默认为0
        """
        try:
            if delay is None:
                delay = self.default_delay

            # 频率控制
            current_time = time.time()
            if current_time - self._last_update_time < self._min_update_interval:
                # 如果更新太频繁，延迟到下一个允许的时间点
                remaining_time = self._min_update_interval - \
                    (current_time - self._last_update_time)
                delay = max(delay, int(remaining_time * 1000))

            if callback:
                # 使用QTimer调度回调
                QTimer.singleShot(delay, callback)
                self.logger.debug(f"调度UI回调，延迟: {delay}ms")
            else:
                # 调度基本UI更新
                QTimer.singleShot(delay, self._perform_safe_ui_update)
                self.logger.debug(f"调度UI更新，延迟: {delay}ms")

            self._last_update_time = current_time

        except Exception as e:
            self.logger.error(f"调度UI更新失败: {e}")

    def _perform_safe_ui_update(self):
        """执行安全的UI更新"""
        try:
            # 只在必要时处理事件
            QApplication.processEvents()
            self.logger.debug("执行安全UI更新")
        except Exception as e:
            self.logger.error(f"执行UI更新失败: {e}")

    def _handle_delayed_action(self, callback: Callable, delay: int):
        """处理延迟动作"""
        try:
            QTimer.singleShot(delay, callback)
            self.logger.debug(f"处理延迟动作，延迟: {delay}ms")
        except Exception as e:
            self.logger.error(f"处理延迟动作失败: {e}")

    def create_async_worker(self, work_func: Callable,
                            success_callback: Callable = None,
                            error_callback: Callable = None) -> 'AsyncWorker':
        """创建异步工作线程

        Args:
            work_func: 工作函数
            success_callback: 成功回调
            error_callback: 错误回调

        Returns:
            异步工作线程实例
        """
        try:
            worker = AsyncWorker(work_func, success_callback, error_callback)
            self.logger.debug("创建异步工作线程")
            return worker
        except Exception as e:
            self.logger.error(f"创建异步工作线程失败: {e}")
            return None

    def throttle_function(self, func: Callable, delay: int = 100) -> Callable:
        """函数节流装饰器

        Args:
            func: 要节流的函数
            delay: 节流延迟（毫秒）

        Returns:
            节流后的函数
        """
        last_call_time = [0]  # 使用列表来存储可变值

        def throttled_func(*args, **kwargs):
            current_time = time.time() * 1000  # 转换为毫秒
            if current_time - last_call_time[0] >= delay:
                last_call_time[0] = current_time
                return func(*args, **kwargs)
            else:
                # 如果调用太频繁，使用QTimer延迟执行
                remaining_delay = delay - (current_time - last_call_time[0])
                QTimer.singleShot(int(remaining_delay),
                                  lambda: func(*args, **kwargs))

        return throttled_func

    def debounce_function(self, func: Callable, delay: int = 300) -> Callable:
        """函数防抖装饰器

        Args:
            func: 要防抖的函数
            delay: 防抖延迟（毫秒）

        Returns:
            防抖后的函数
        """
        timer = [None]  # 使用列表来存储可变值

        def debounced_func(*args, **kwargs):
            if timer[0] is not None:
                timer[0].stop()

            timer[0] = QTimer()
            timer[0].setSingleShot(True)
            timer[0].timeout.connect(lambda: func(*args, **kwargs))
            timer[0].start(delay)

        return debounced_func

class AsyncWorker(QThread):
    """异步工作线程"""

    # 定义信号
    work_finished = pyqtSignal(object)  # 工作完成信号
    work_error = pyqtSignal(str)  # 工作错误信号
    progress_updated = pyqtSignal(int)  # 进度更新信号

    def __init__(self, work_func: Callable,
                 success_callback: Callable = None,
                 error_callback: Callable = None):
        """初始化异步工作线程

        Args:
            work_func: 工作函数
            success_callback: 成功回调
            error_callback: 错误回调
        """
        super().__init__()
        self.work_func = work_func
        self.logger = logger.bind(module=__name__)

        # 连接信号
        if success_callback:
            self.work_finished.connect(success_callback)
        if error_callback:
            self.work_error.connect(error_callback)

    def run(self):
        """执行工作函数"""
        try:
            self.logger.debug("异步工作线程开始执行")
            result = self.work_func()
            self.work_finished.emit(result)
            self.logger.debug("异步工作线程执行完成")
        except Exception as e:
            error_msg = f"异步工作执行失败: {str(e)}"
            self.logger.error(error_msg)
            self.work_error.emit(error_msg)

    def update_progress(self, progress: int):
        """更新进度

        Args:
            progress: 进度百分比 (0-100)
        """
        self.progress_updated.emit(progress)

class UIUpdateManager:
    """UI更新管理器 - 全局单例"""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = logger.bind(module=__name__)
        self.optimizer = UIOptimizer()
        self._initialized = True

        self.logger.info("UI更新管理器初始化完成")

    def schedule_update(self, callback: Callable = None, delay: int = None):
        """调度UI更新"""
        return self.optimizer.schedule_ui_update(callback, delay)

    def create_worker(self, work_func: Callable,
                      success_callback: Callable = None,
                      error_callback: Callable = None) -> AsyncWorker:
        """创建异步工作线程"""
        return self.optimizer.create_async_worker(work_func, success_callback, error_callback)

    def throttle(self, func: Callable, delay: int = 100) -> Callable:
        """函数节流"""
        return self.optimizer.throttle_function(func, delay)

    def debounce(self, func: Callable, delay: int = 300) -> Callable:
        """函数防抖"""
        return self.optimizer.debounce_function(func, delay)

# 全局UI更新管理器实例
_ui_manager = None
_manager_lock = threading.RLock()

def get_ui_manager() -> UIUpdateManager:
    """获取全局UI更新管理器实例

    Returns:
        UI更新管理器实例
    """
    global _ui_manager

    with _manager_lock:
        if _ui_manager is None:
            _ui_manager = UIUpdateManager()

        return _ui_manager

# 便捷函数

def schedule_ui_update(callback: Callable = None, delay: int = None):
    """调度UI更新的便捷函数

    Args:
        callback: 可选的回调函数
        delay: 延迟时间（毫秒）
    """
    manager = get_ui_manager()
    return manager.schedule_update(callback, delay)

def create_async_worker(work_func: Callable,
                        success_callback: Callable = None,
                        error_callback: Callable = None) -> AsyncWorker:
    """创建异步工作线程的便捷函数

    Args:
        work_func: 工作函数
        success_callback: 成功回调
        error_callback: 错误回调

    Returns:
        异步工作线程实例
    """
    manager = get_ui_manager()
    return manager.create_worker(work_func, success_callback, error_callback)

def throttle_ui_function(delay: int = 100):
    """UI函数节流装饰器

    Args:
        delay: 节流延迟（毫秒）
    """
    def decorator(func: Callable):
        manager = get_ui_manager()
        return manager.throttle(func, delay)
    return decorator

def debounce_ui_function(delay: int = 300):
    """UI函数防抖装饰器

    Args:
        delay: 防抖延迟（毫秒）
    """
    def decorator(func: Callable):
        manager = get_ui_manager()
        return manager.debounce(func, delay)
    return decorator

# 替换QApplication.processEvents()的便捷函数

def safe_process_events(delay: int = 0):
    """安全的事件处理函数，替换QApplication.processEvents()

    Args:
        delay: 延迟时间（毫秒）
    """
    schedule_ui_update(delay=delay)

def replace_process_events():
    """替换QApplication.processEvents()的使用

    这个函数可以在需要的地方调用，提供更好的UI响应性
    """
    safe_process_events()
