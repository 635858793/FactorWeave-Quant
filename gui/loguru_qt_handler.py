"""
纯Loguru的Qt UI处理器
完全替代原有的Qt信号机制，使用Loguru原生方案
"""

from loguru import logger
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
from PyQt5.QtWidgets import QApplication
import queue
import threading
import time
from typing import Dict, Any, Optional

class LoguruQtHandler(QObject):
    """纯Loguru的Qt UI处理器 - 替代BaseLogManager的Qt信号"""

    # 保持与原有系统兼容的信号接口
    log_received = pyqtSignal(str, str, str)  # message, level, timestamp
    error_occurred = pyqtSignal(str, str)     # error_message, traceback
    performance_alert = pyqtSignal(str)       # alert_message

    def __init__(self):
        super().__init__()
        self.message_queue = queue.Queue(maxsize=10000)
        self.is_active = True
        self._mutex = QMutex()

        # 统计信息
        self.stats = {
            "messages_processed": 0,
            "messages_dropped": 0,
            "queue_overflows": 0,
            "last_process_time": 0
        }

        self.setup_loguru_sink()
        # 延迟定时器设置，等待QApplication和事件循环准备好
        self.timer = None

    def setup_loguru_sink(self):
        """设置Loguru sink用于UI显示"""

        def ui_sink(message):
            """UI专用sink - 将消息放入队列异步处理"""
            if not self.is_active:
                return

            record = message.record

            # 过滤掉性能日志，避免UI刷屏
            if "performance" in record.get("extra", {}):
                # 只处理性能警报
                if record["level"].name in ["WARNING", "ERROR"]:
                    self._handle_performance_alert(record)
                return

            # 准备UI消息数据
            ui_message = {
                "message": record["message"],
                "level": record["level"].name,
                "timestamp": record["time"].strftime("%H:%M:%S.%f")[:-3],  # 毫秒精度
                "module": record.get("name", ""),
                "function": record.get("function", ""),
                "line": record.get("line", ""),
                "extra": record.get("extra", {})
            }

            # 特殊处理错误信息
            if record["level"].name == "ERROR":
                self._handle_error_message(ui_message, record)

            # 将消息加入队列
            try:
                self.message_queue.put_nowait(ui_message)
            except queue.Full:
                # 队列满时丢弃最旧的消息
                try:
                    self.message_queue.get_nowait()
                    self.message_queue.put_nowait(ui_message)
                    self.stats["queue_overflows"] += 1
                except queue.Empty:
                    pass

        # 添加UI专用sink
        self.sink_id = logger.add(
            ui_sink,
            level="DEBUG",
            enqueue=False,  # UI更新需要同步处理
            catch=False     # 不捕获异常，让其传播
        )

    def _handle_performance_alert(self, record):
        """处理性能警报"""
        alert_message = f"性能警报: {record['message']}"
        self.performance_alert.emit(alert_message)

    def _handle_error_message(self, ui_message: Dict[str, Any], record):
        """处理错误消息的特殊逻辑"""
        error_message = ui_message["message"]

        # 提取异常信息
        exception_info = ""
        if record.get("exception"):
            exception_info = str(record["exception"])

        # 发射错误信号
        self.error_occurred.emit(error_message, exception_info)

    def setup_processing_timer(self):
        """设置定时器处理UI更新队列"""
        if self.timer is not None:
            return  # 避免重复创建

        self.timer = QTimer()
        self.timer.timeout.connect(self.process_message_queue)
        self.timer.start(33)  # 30fps更新频率，平衡实时性和性能

    def process_message_queue(self):
        """批量处理消息队列，优化UI性能"""
        if not self.is_active:
            return

        start_time = time.perf_counter()
        messages_processed = 0
        max_messages_per_batch = 50  # 限制每批处理数量，避免UI阻塞

        with QMutexLocker(self._mutex):
            while (not self.message_queue.empty() and
                   messages_processed < max_messages_per_batch):
                try:
                    ui_message = self.message_queue.get_nowait()

                    # 发射Qt信号
                    self.log_received.emit(
                        ui_message["message"],
                        ui_message["level"],
                        ui_message["timestamp"]
                    )

                    messages_processed += 1
                    self.stats["messages_processed"] += 1

                except queue.Empty:
                    break

        # 更新统计信息
        self.stats["last_process_time"] = time.perf_counter() - start_time

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态信息"""
        return {
            "queue_size": self.message_queue.qsize(),
            "max_size": self.message_queue.maxsize,
            "is_active": self.is_active,
            "stats": self.stats.copy()
        }

    def pause(self):
        """暂停消息处理"""
        self.is_active = False
        logger.debug("LoguruQtHandler 已暂停")

    def resume(self):
        """恢复消息处理"""
        self.is_active = True
        logger.debug("LoguruQtHandler 已恢复")

    def clear_queue(self):
        """清空消息队列"""
        with QMutexLocker(self._mutex):
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except queue.Empty:
                    break
        logger.debug("LoguruQtHandler 队列已清空")

    def shutdown(self):
        """关闭处理器"""
        self.is_active = False
        try:
            if hasattr(self, 'timer') and self.timer is not None:
                self.timer.stop()
        except RuntimeError:
            pass  # QTimer已被删除

        try:
            if hasattr(self, 'sink_id'):
                logger.remove(self.sink_id)
        except:
            pass  # 忽略移除错误

        self.clear_queue()
        logger.debug("LoguruQtHandler 已关闭")

    def __del__(self):
        """析构函数"""
        try:
            self.shutdown()
        except:
            pass  # 忽略析构错误

class LoguruQtSignalBridge:
    """Loguru Qt信号桥接器 - 提供便捷的信号连接"""

    def __init__(self):
        self.handler = LoguruQtHandler()

        # 便捷的信号访问
        self.log_message = self.handler.log_received
        self.error_occurred = self.handler.error_occurred
        self.performance_alert = self.handler.performance_alert

    def connect_log_widget(self, log_widget):
        """连接到日志显示组件"""
        if hasattr(log_widget, 'add_log_entry'):
            self.log_message.connect(log_widget.add_log_entry)
        elif hasattr(log_widget, 'on_log_received'):
            self.log_message.connect(log_widget.on_log_received)
        else:
            logger.warning("日志组件没有标准的接收方法")

    def connect_error_handler(self, error_handler):
        """连接到错误处理器"""
        if hasattr(error_handler, 'on_error_occurred'):
            self.error_occurred.connect(error_handler.on_error_occurred)

    def connect_performance_monitor(self, performance_monitor):
        """连接到性能监控器"""
        if hasattr(performance_monitor, 'on_performance_alert'):
            self.performance_alert.connect(performance_monitor.on_performance_alert)

    def get_handler(self) -> LoguruQtHandler:
        """获取底层处理器"""
        return self.handler

# 全局Qt处理器实例 - 使用延迟初始化避免Qt事件循环问题
qt_handler = None
qt_bridge = None

def get_qt_handler() -> Optional[LoguruQtHandler]:
    """获取全局Qt处理器，延迟初始化"""
    global qt_handler
    
    # 检查QApplication是否存在
    if QApplication.instance() is None:
        logger.warning("QApplication未初始化，无法创建Qt日志处理器")
        return None
    
    if qt_handler is None:
        qt_handler = LoguruQtHandler()
    return qt_handler

def get_qt_bridge() -> LoguruQtSignalBridge:
    """获取全局Qt信号桥接器，延迟初始化"""
    global qt_bridge
    if qt_bridge is None:
        qt_bridge = LoguruQtSignalBridge()
    return qt_bridge
