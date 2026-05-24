# core/metrics/resource_service.py
import threading
import time
import psutil
from typing import Optional

from core.metrics.events import SystemResourceUpdated
from core.events.event_bus import EventBus
from core.config import config_manager
from loguru import logger

class SystemResourceService:
    """一个后台服务，定期监控并发布系统资源（CPU、内存、磁盘）使用情况。"""

    def __init__(self, event_bus: EventBus, interval: Optional[float] = None):
        """
        初始化系统资源服务。

        :param event_bus: 事件总线实例。
        :param interval: 监控间隔（秒）。如果为None，则从配置中读取。
        """
        self.event_bus = event_bus
        # 优先使用传入的interval，否则从配置中心获取，最后使用默认值
        self._interval = interval or config_manager.get(
            'monitoring.resource_interval', 1.0)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.logger = logger.bind(module=self.__class__.__name__)
    def start(self):
        """启动后台监控线程。"""
        if self._thread is not None and self._thread.is_alive():
            return  # 服务已在运行

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("系统资源监控服务已启动。")

    def _run(self):
        """监控循环，定期采集并发布资源数据。"""
        while not self._stop_event.is_set():
            try:
                # 采集数据
                cpu_percent = psutil.cpu_percent()
                memory_info = psutil.virtual_memory()
                # 获取磁盘使用情况 - 跨平台兼容
                try:
                    import os
                    from pathlib import Path
                    if os.name == 'nt':  # Windows系统
                        try:
                            disk_usage = psutil.disk_usage('C:\\')
                            disk_percent = disk_usage.percent
                        except (OSError, ValueError) as e:
                            # 如果C盘不可用，尝试获取当前工作目录所在磁盘
                            try:
                                current_drive = Path.cwd().anchor
                                disk_usage = psutil.disk_usage(current_drive)
                                disk_percent = disk_usage.percent
                            except Exception:
                                disk_percent = 0.0
                                self.logger.debug(f"磁盘使用率获取失败，使用默认值")
                    else:  # Unix/Linux系统
                        try:
                            disk_usage = psutil.disk_usage('/')
                            disk_percent = disk_usage.percent
                        except Exception:
                            disk_percent = 0.0
                            self.logger.debug("磁盘使用率获取失败，使用默认值")
                except Exception as e:
                    # 如果所有方法都失败，使用默认值
                    disk_percent = 0.0
                    self.logger.debug(f"磁盘使用率监控暂时不可用: {str(e)}")

                # 创建事件
                event = SystemResourceUpdated(
                    cpu_percent=cpu_percent,
                    memory_percent=memory_info.percent,
                    disk_percent=disk_percent,
                )

                # 发布事件
                self.event_bus.publish(event)

            except Exception as e:
                try:
                    logger.info(f"资源监控线程错误: {str(e)}")
                except Exception:
                    logger.info(f"资源监控线程错误: {type(e).__name__}")
                import traceback
                traceback.print_exc()

            # 等待下一个间隔
            self._stop_event.wait(self._interval)

    def dispose(self):
        """停止后台监控线程。"""
        if self._thread is not None and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("系统资源监控线程未能在5秒内停止")
            else:
                logger.info("系统资源监控服务已停止。")
