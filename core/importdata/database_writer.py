import threading
import time
from typing import Any, Dict, List
from queue import Queue, Empty
import pandas as pd

from loguru import logger


class DatabaseWriterThread(threading.Thread):
    """
    数据库写入线程（单线程模式）

    解决DuckDB并发写入死锁问题：
    - 所有工作线程将数据放入无锁队列
    - 本线程单独消费队列，串行写入数据库
    - 完全避免写锁竞争
    """

    def __init__(self):
        super().__init__(name="DatabaseWriter", daemon=True)

        self.write_queue = Queue(maxsize=5000)

        self._merge_buffer: Dict[str, List[pd.DataFrame]] = {}
        self._merge_lock = threading.RLock()

        self._stop_event = threading.Event()
        self._stopped = False

        self._total_writes = 0
        self._failed_writes = 0
        # 修复：补充真实记录数统计（落库成功/失败的记录条数），供监控面板计算真实速度
        self._total_records = 0
        self._failed_records = 0
        self._queue_peak = 0
        self._stats_lock = threading.RLock()

        self._batch_threshold_normal = 5
        self._batch_threshold_medium = 3
        self._batch_threshold_urgent = 1
        self._queue_size_threshold_urgent = 100
        self._queue_size_threshold_medium = 50
        self._flush_timeout_normal = 2.0
        self._flush_timeout_medium = 1.0
        self._flush_timeout_urgent = 0.5
        self._buffer_timestamps: Dict[str, float] = {}
        self._buffer_data_types: Dict[str, Any] = {}

        self._failed_tasks: List = []
        self._max_retry_queue = 200

        from ..asset_database_manager import AssetSeparatedDatabaseManager
        self._asset_manager = AssetSeparatedDatabaseManager()

        logger.info("DatabaseWriterThread 初始化完成")

    def put_write_task(self, task, timeout: float = 5.0) -> bool:
        try:
            queue_size_before = self.write_queue.qsize()
            put_start_time = time.time()

            if queue_size_before > self.write_queue.maxsize * 0.8:
                logger.warning(f"⚠️  [队列接近满载] 当前队列大小: {queue_size_before}/{self.write_queue.maxsize}，可能影响写入性能")

            self.write_queue.put(task, timeout=timeout)

            put_duration = time.time() - put_start_time
            queue_size_after = self.write_queue.qsize()

            if put_duration > 0.5:
                logger.warning(f"⚠️  [队列阻塞] 入队耗时:{put_duration:.2f}秒 | 队列大小:{queue_size_before}→{queue_size_after} | buffer_key:{task.buffer_key}")

            with self._stats_lock:
                current_size = self.write_queue.qsize()
                if current_size > self._queue_peak:
                    self._queue_peak = current_size

            return True
        except Exception as e:
            # R292 修复：失败日志补充写线程存活状态，便于定位"队列无人消费"
            # （写线程已死但引擎未重建）与"队列满载"两类静默丢数据场景。
            try:
                writer_alive = self.is_alive()
            except Exception:
                writer_alive = False
            logger.error(f"放入写入任务失败: {e} | 队列大小:{self.write_queue.qsize()} | 写入线程存活:{writer_alive}")
            return False

    def run(self):
        logger.info("DatabaseWriterThread 启动")

        last_timeout_check = time.time()

        while not self._stop_event.is_set() or not self.write_queue.empty():
            task = None
            try:
                current_time = time.time()
                queue_size = self.write_queue.qsize()
                check_interval = 0.5 if queue_size > self._queue_size_threshold_urgent else 1.0
                if current_time - last_timeout_check >= check_interval:
                    self._check_and_flush_timeout_buffers()
                    last_timeout_check = current_time

                try:
                    task = self.write_queue.get(timeout=1.0)
                except Empty:
                    self._check_and_flush_timeout_buffers()
                    last_timeout_check = time.time()
                    continue

                try:
                    success = self._write_task_to_database(task)
                    with self._stats_lock:
                        if success:
                            self._total_writes += 1
                        else:
                            self._failed_writes += 1
                except Exception as e:
                    # 修复：写入任务抛出异常时，也必须计入失败并保证 task_done() 被调用，
                    # 否则 queue.join() 会永久阻塞，且统计失真
                    logger.error(f"写入任务异常: {e}", exc_info=True)
                    if task is not None:
                        self._failed_tasks.append(task)
                        if len(self._failed_tasks) > self._max_retry_queue:
                            oldest = self._failed_tasks.pop(0)
                            stock_code = oldest.buffer_key if hasattr(oldest, 'buffer_key') else 'unknown'
                            logger.warning(f"重试队列已满，丢弃最旧任务: {stock_code}")
                    with self._stats_lock:
                        self._failed_writes += 1
                finally:
                    # 修复：无论成功/失败/异常都必须调用 task_done()
                    self.write_queue.task_done()

            except Exception as e:
                logger.error(f"写入任务失败: {e}", exc_info=True)
                if task is not None:
                    self._failed_tasks.append(task)
                    if len(self._failed_tasks) > self._max_retry_queue:
                        oldest = self._failed_tasks.pop(0)
                        stock_code = oldest.buffer_key if hasattr(oldest, 'buffer_key') else 'unknown'
                        logger.warning(f"重试队列已满，丢弃最旧任务: {stock_code}")

        self._flush_merge_buffer()

        logger.info(f"DatabaseWriterThread 停止 (总写入:{self._total_writes}, 失败:{self._failed_writes})")
        self._stopped = True

    def _check_and_flush_timeout_buffers(self):
        try:
            current_time = time.time()
            queue_size = self.write_queue.qsize()
            if queue_size > self._queue_size_threshold_urgent:
                flush_timeout = self._flush_timeout_urgent
            elif queue_size > self._queue_size_threshold_medium:
                flush_timeout = self._flush_timeout_medium
            else:
                flush_timeout = self._flush_timeout_normal

            with self._merge_lock:
                buffers_to_flush = []
                for buffer_key, timestamp in list(self._buffer_timestamps.items()):
                    if current_time - timestamp >= flush_timeout:
                        if buffer_key in self._merge_buffer and self._merge_buffer[buffer_key]:
                            buffers_to_flush.append(buffer_key)

                for buffer_key in buffers_to_flush:
                    try:
                        parts = buffer_key.split('_', 1)
                        if len(parts) >= 1:
                            from ..plugin_types import AssetType, DataType
                            asset_type_str = parts[0]
                            asset_type = AssetType(asset_type_str)
                            data_type = self._buffer_data_types.get(buffer_key, DataType.HISTORICAL_KLINE)

                            self._flush_buffer_key(buffer_key, asset_type, data_type)
                            if buffer_key in self._buffer_timestamps:
                                del self._buffer_timestamps[buffer_key]
                            if buffer_key in self._buffer_data_types:
                                del self._buffer_data_types[buffer_key]
                    except Exception as e:
                        logger.debug(f"刷新超时缓冲区失败: {buffer_key}, {e}")
        except Exception as e:
            logger.debug(f"检查超时缓冲区失败: {e}")

    def _write_task_to_database(self, task) -> bool:
        try:
            queue_size = self.write_queue.qsize()
            if queue_size > self._queue_size_threshold_urgent:
                current_batch_threshold = self._batch_threshold_urgent
            elif queue_size > self._queue_size_threshold_medium:
                current_batch_threshold = self._batch_threshold_medium
            else:
                current_batch_threshold = self._batch_threshold_normal

            with self._merge_lock:
                if task.buffer_key not in self._merge_buffer:
                    self._merge_buffer[task.buffer_key] = []
                    self._buffer_timestamps[task.buffer_key] = time.time()

                self._merge_buffer[task.buffer_key].append(task.data)
                self._buffer_timestamps[task.buffer_key] = time.time()
                self._buffer_data_types[task.buffer_key] = task.data_type

                if len(self._merge_buffer[task.buffer_key]) >= current_batch_threshold:
                    result = self._flush_buffer_key(task.buffer_key, task.asset_type, task.data_type)
                    if task.buffer_key in self._buffer_timestamps:
                        del self._buffer_timestamps[task.buffer_key]
                    return result

            return True

        except Exception as e:
            logger.error(f"写入任务失败: {task.buffer_key}, {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _flush_buffer_key(self, buffer_key: str, asset_type: Any, data_type: Any) -> bool:
        try:
            if buffer_key not in self._merge_buffer or not self._merge_buffer[buffer_key]:
                return True

            data_list = self._merge_buffer[buffer_key]

            if len(data_list) == 1:
                combined_data = data_list[0]
            else:
                combined_data = pd.concat(data_list, ignore_index=True, sort=False)

            record_count = len(combined_data)
            logger.info(f"[写入线程] 写入: {buffer_key}, {record_count}条记录 (合并{len(data_list)}个DataFrame)")

            write_start_time = time.time()
            success = self._asset_manager.store_standardized_data(
                data=combined_data,
                asset_type=asset_type,
                data_type=data_type
            )
            write_duration = time.time() - write_start_time

            if success:
                write_speed = record_count / write_duration if write_duration > 0 else 0
                logger.info(f"[写入线程] 写入成功: {buffer_key}, {record_count}条记录, 耗时: {write_duration:.2f}秒, 速度: {write_speed:.1f}条/秒")
                del self._merge_buffer[buffer_key]
                with self._stats_lock:
                    self._total_records += record_count
            else:
                # 修复：写入失败时也必须清空缓冲区，
                # 否则旧数据残留与新数据合并会造成重复写入（数据重复），
                # 或反复失败导致缓冲区无限增长（内存泄漏）
                logger.error(f"❌ [写入线程] 写入失败: {buffer_key}, 丢弃 {record_count}条记录 (待任务级重试)")
                del self._merge_buffer[buffer_key]
                with self._stats_lock:
                    self._failed_records += record_count

            return success

        except Exception as e:
            logger.error(f"刷新缓冲区失败: {buffer_key}, {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _flush_merge_buffer(self):
        logger.info("刷新所有合并缓冲区...")

        with self._merge_lock:
            for buffer_key in list(self._merge_buffer.keys()):
                if self._merge_buffer[buffer_key]:
                    try:
                        parts = buffer_key.split('_', 1)
                        logger.debug(f"[_flush_merge_buffer] buffer_key={buffer_key}, parts={parts}")
                        if len(parts) >= 1:
                            from ..plugin_types import AssetType, DataType
                            asset_type_str = parts[0]
                            if len(parts) > 1:
                                if parts[1].startswith('a_'):
                                    asset_type_str = "stock_a"
                                elif parts[1].startswith('b_'):
                                    asset_type_str = "stock_b"
                                elif parts[1].startswith('h_') and not parts[1].startswith('hk_'):
                                    asset_type_str = "stock_h"
                                elif parts[1].startswith('hk_'):
                                    asset_type_str = "stock_hk"
                                elif parts[1].startswith('us_'):
                                    asset_type_str = "stock_us"
                            logger.debug(f"[_flush_merge_buffer] parsed asset_type_str={asset_type_str}")
                            asset_type = AssetType(asset_type_str)
                            data_type = DataType.HISTORICAL_KLINE

                            self._flush_buffer_key(buffer_key, asset_type, data_type)
                    except Exception as e:
                        logger.error(f"刷新缓冲区失败: {buffer_key}, {e}")
                        import traceback
                        logger.error(traceback.format_exc())

    def stop(self, wait: bool = True, timeout: float = 30.0):
        logger.info(f"停止DatabaseWriterThread (wait={wait}, queue_size={self.write_queue.qsize()})")

        self._stop_event.set()

        if wait:
            try:
                start_time = time.time()
                while not self.write_queue.empty() and (time.time() - start_time) < timeout:
                    logger.debug(f"等待队列清空... ({self.write_queue.qsize()}个任务)")
                    time.sleep(0.5)

                self.join(timeout=5.0)

                self._flush_merge_buffer()
                logger.debug(f"DatabaseWriterThread已停止，buffer已刷新")
            except Exception as e:
                logger.error(f"停止写入线程失败: {e}")
                self._flush_merge_buffer()

    def get_stats(self) -> Dict[str, Any]:
        with self._stats_lock:
            with self._merge_lock:
                merge_buffer_size = sum(len(buffer_list) for buffer_list in self._merge_buffer.values())

            return {
                'queue_size': self.write_queue.qsize(),
                'queue_peak': self._queue_peak,
                'total_writes': self._total_writes,
                'failed_writes': self._failed_writes,
                'total_records': self._total_records,
                'failed_records': self._failed_records,
                'merge_buffer_size': merge_buffer_size,
                'is_stopped': self._stopped
            }
