from loguru import logger
"""
渐进式加载管理器模块
提供分阶段数据加载和优先级管理功能
"""

import asyncio
import os
import threading
import time
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty, PriorityQueue
from concurrent.futures import ThreadPoolExecutor, Future
import pandas as pd
from utils.trace_context import get_trace_id, set_trace_id
from core.performance import measure_performance

logger = logger

class LoadingStage(Enum):
    """加载阶段"""
    CRITICAL = 1    # 关键数据（基础K线）
    HIGH = 2        # 高优先级（成交量、基础指标）
    NORMAL = 3      # 普通优先级（常用指标）
    LOW = 4         # 低优先级（高级指标）
    BACKGROUND = 5  # 后台加载（历史数据）

@dataclass
class LoadingTask:
    """加载任务"""
    id: str
    stage: LoadingStage
    loader_func: Callable
    data_params: Dict[str, Any]
    callback: Optional[Callable] = None
    created_time: float = field(default_factory=time.time)
    delay_ms: int = 0  # 延迟执行时间（毫秒）
    priority_within_stage: int = 0  # 阶段内优先级（数字越小优先级越高）

    def __lt__(self, other):
        """支持优先级队列排序"""
        if self.stage.value != other.stage.value:
            return self.stage.value < other.stage.value
        if self.priority_within_stage != other.priority_within_stage:
            return self.priority_within_stage < other.priority_within_stage
        return self.created_time < other.created_time

class ProgressiveLoadingManager:
    """渐进式加载管理器"""

    def __init__(self, max_workers: int = os.cpu_count() * 2, enable_delays: bool = True):
        """
        初始化渐进式加载管理器

        Args:
            max_workers: 最大工作线程数
            enable_delays: 是否启用阶段延迟
        """
        self.max_workers = max_workers
        self.enable_delays = enable_delays

        # 加载队列（使用优先级队列）
        self.task_queue = PriorityQueue()
        
        # 修复：使用信号机制实现立即唤醒（替代超时轮询）
        self.task_available = threading.Event()  # 任务可用信号
        self.shutdown_event = threading.Event()  # 关闭信号

        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers,
                                           thread_name_prefix="ProgressiveLoader")

        # 运行状态
        self.is_running = False
        self.worker_threads = []
        self.active_tasks = {}
        self.active_tasks_lock = threading.Lock()

        # 阶段延迟配置（毫秒）
        self.stage_delays = {
            LoadingStage.CRITICAL: 0,      # 立即加载
            LoadingStage.HIGH: 5,        # 5ms后
            LoadingStage.NORMAL: 10,      # 10ms后
            LoadingStage.LOW: 20,         # 20ms后
            LoadingStage.BACKGROUND: 30   # 30ms后
        }

        # 根据设备性能调整延迟
        self._adjust_delays_for_device()

        # 加载统计
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0,
            'stage_stats': {stage.name: {'submitted': 0, 'completed': 0, 'failed': 0}
                            for stage in LoadingStage}
        }

        # 加载失败回调
        self.loading_failed_callbacks = []

        # 加载完成回调
        self.loading_completed_callbacks = []

        # 锁
        self.stats_lock = threading.Lock()

        logger.info(f"ProgressiveLoadingManager初始化完成 - 工作线程数: {max_workers}")

    def _adjust_delays_for_device(self):
        """根据设备性能调整加载延迟"""
        try:
            import psutil

            # 根据CPU和内存情况调整
            cpu_count = psutil.cpu_count(logical=True) or 8  # 物理核心数
            memory_gb = psutil.virtual_memory().total / (1024**3)  # 总内存GB

            logger.info(f"检测到设备配置: CPU核心数={cpu_count}, 内存={memory_gb:.1f}GB")

            # 低配设备增加延迟
            if cpu_count < 4 or memory_gb < 8:
                factor = 1.0
                logger.info("检测到低配设备，增加加载延迟")
            # 高配设备减少延迟
            elif cpu_count >= 8 and memory_gb >= 16:
                factor = 0.5
                logger.info("检测到高配设备，减少加载延迟")
            else:
                factor = 0.7
                logger.info("检测到中配设备，使用默认加载延迟")

            # 调整所有阶段的延迟
            for stage in self.stage_delays:
                if stage != LoadingStage.CRITICAL:  # 关键阶段始终保持0延迟
                    self.stage_delays[stage] = int(
                        self.stage_delays[stage] * factor)

            logger.info(f"调整后的加载延迟: {self.stage_delays}")

        except Exception as e:
            logger.warning(f"无法根据设备性能调整延迟: {e}")

    def start(self):
        """启动加载管理器"""
        if self.is_running:
            return

        self.is_running = True

        # 启动工作线程
        for i in range(self.max_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"ProgressiveLoader-{i}",
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)

        logger.info(f"ProgressiveLoadingManager已启动 - {self.max_workers}个工作线程")

    def stop(self):
        """停止加载管理器"""
        if not self.is_running:
            return

        self.is_running = False
        
        # 修复：使用信号机制唤醒所有工作线程
        self.shutdown_event.set()
        self.task_available.set()  # 唤醒所有等待的线程

        # 等待所有队列清空
        try:
            # 等待队列清空或超时（最多等待3秒）
            wait_time = 0
            max_wait_time = 3.0
            while not self.task_queue.empty() and wait_time < max_wait_time:
                time.sleep(0.1)
                wait_time += 0.1

            # 取消所有活动任务
            with self.active_tasks_lock:
                for task_id, future in list(self.active_tasks.items()):
                    if future and not future.done():
                        future.cancel()
                self.active_tasks.clear()

        except Exception as e:
            logger.error(f"停止加载管理器时出错: {e}")

        # 等待工作线程退出
        for thread in self.worker_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)  # 最多等待1秒
        
        self.worker_threads.clear()

        # 关闭线程池
        self.executor.shutdown(wait=False)
        
        # 清理信号
        self.task_available.clear()
        self.shutdown_event.clear()

        logger.info("ProgressiveLoadingManager已停止")

    def _worker_loop(self):
        """工作线程主循环 - 使用信号机制实现立即唤醒"""
        while self.is_running:
            try:
                # 修复：使用信号机制替代超时轮询，实现立即唤醒
                # 等待任务可用信号（无超时，实现真正的立即唤醒）
                # 使用1.0秒安全超时仅用于定期检查is_running状态，防止线程永远阻塞
                self.task_available.wait(timeout=1.0)
                
                # 检查是否收到关闭信号
                if self.shutdown_event.is_set() or not self.is_running:
                    logger.debug("工作线程收到关闭信号，退出循环")
                    break
                
                # 尝试获取任务（可能多个线程被唤醒，但只有一个能获取到任务）
                task = None
                try:
                    # 立即获取任务，不阻塞
                    task = self.task_queue.get_nowait()
                except Empty:
                    # 队列为空，清除信号（防止重复唤醒）
                    # 这可能发生在多个线程被唤醒但只有一个获取到任务的情况
                    self.task_available.clear()
                    continue
                
                # 如果队列还有任务，保持信号设置（唤醒其他等待的线程）
                if self.task_queue.empty():
                    self.task_available.clear()
                
                # 应用阶段延迟
                if self.enable_delays:
                    delay = task.delay_ms
                    if delay == 0:  # 如果没有指定延迟，使用阶段默认延迟
                        delay = self.stage_delays.get(task.stage, 0)

                    if delay > 0:
                        time.sleep(delay / 1000.0)

                # 处理任务
                self._process_loading_task(task)

                self.task_queue.task_done()

            except Exception as e:
                logger.error(f"加载管理器工作线程处理任务时出错: {e}")
                # 发生异常时，短暂休眠避免CPU占用过高
                time.sleep(0.01)

    @measure_performance("ProgressiveLoadingManager._process_loading_task")
    def _process_loading_task(self, task: LoadingTask):
        set_trace_id(get_trace_id())
        """处理加载任务"""
        start_time = time.time()

        # 提交到线程池执行
        future = self.executor.submit(self._execute_task, task)

        # 记录活动任务
        with self.active_tasks_lock:
            self.active_tasks[task.id] = future

    @measure_performance("ProgressiveLoadingManager._execute_task")
    def _execute_task(self, task: LoadingTask):
        set_trace_id(get_trace_id())
        """执行加载任务"""
        start_time = time.time()

        try:
            # 如果data_params是None，跳过执行
            if task.data_params is None:
                logger.warning(f"跳过加载任务 {task.id}: 数据参数为空")
                return None

            # 执行加载函数
            if isinstance(task.data_params, dict):
                # 如果是字典，作为关键字参数传递
                result = task.loader_func(**task.data_params)
            else:
                # 否则作为位置参数传递
                result = task.loader_func(task.data_params)

            # 调用回调函数
            if task.callback:
                try:
                    task.callback(result)
                except Exception as e:
                    logger.error(f"加载任务 {task.id} 回调执行失败: {e}")

            # 更新成功统计
            with self.stats_lock:
                self.stats['completed_tasks'] += 1
                self.stats['stage_stats'][task.stage.name]['completed'] += 1

            # 调用加载完成回调
            self._notify_loading_completed(task.id, task.stage)

            logger.debug(
                f"加载任务 {task.id} ({task.stage.name}) 完成 - 耗时: {time.time() - start_time:.4f}s")

            return result

        except Exception as e:
            # 更新失败统计
            with self.stats_lock:
                self.stats['failed_tasks'] += 1
                self.stats['stage_stats'][task.stage.name]['failed'] += 1

            logger.error(f"加载任务 {task.id} ({task.stage.name}) 失败: {e}")

            # 调用加载失败回调
            self._notify_loading_failed(task.id, str(e), task.stage)

            return None

        finally:
            # 从活动任务中移除
            with self.active_tasks_lock:
                self.active_tasks.pop(task.id, None)

    def _notify_loading_failed(self, task_id: str, error_msg: str, stage: LoadingStage):
        """通知加载失败"""
        for callback in self.loading_failed_callbacks:
            try:
                callback(task_id, error_msg, stage)
            except Exception as e:
                logger.error(f"执行加载失败回调时出错: {e}")

    def _notify_loading_completed(self, task_id: str, stage: LoadingStage):
        """通知加载完成"""
        for callback in self.loading_completed_callbacks:
            try:
                callback(task_id, stage)
            except Exception as e:
                logger.error(f"执行加载完成回调时出错: {e}")

    def register_loading_failed_callback(self, callback: Callable):
        """注册加载失败回调"""
        if callback not in self.loading_failed_callbacks:
            self.loading_failed_callbacks.append(callback)
            return True
        return False

    def register_loading_completed_callback(self, callback: Callable):
        """注册加载完成回调"""
        if callback not in self.loading_completed_callbacks:
            self.loading_completed_callbacks.append(callback)
            return True
        return False

    def load_chart_progressive(self, chart_widget, kdata, indicators):
        """渐进式加载图表"""
        # 第一阶段：立即显示框架
        if hasattr(chart_widget, 'show_loading_skeleton'):
            chart_widget.show_loading_skeleton()

        # 更新图表框架
        if hasattr(chart_widget, 'update_chart_frame'):
            chart_widget.update_chart_frame()

        # 分阶段加载
        try:
            # 第一阶段：基础K线数据（关键阶段）
            self._load_chart_stage(chart_widget, kdata,
                                   indicators, "basic_kdata")

            # 第二阶段：成交量数据（高优先级）
            self._load_chart_stage(chart_widget, kdata, indicators, "volume")

            # 第三阶段：基础指标（普通优先级）
            self._load_chart_stage(chart_widget, kdata,
                                   indicators, "basic_indicators")

            # 第四阶段：高级指标（低优先级）
            self._load_chart_stage(chart_widget, kdata,
                                   indicators, "advanced_indicators")

            # 第五阶段：装饰元素（后台加载）
            self._load_chart_stage(chart_widget, kdata,
                                   indicators, "decorations")

            return True
        except Exception as e:
            logger.error(f"渐进式加载图表失败: {e}")

            # 回退到同步加载
            self._load_chart_sync(chart_widget, kdata, indicators)

            return False

    def _load_chart_stage(self, chart_widget, kdata, indicators, stage_name):
        """加载图表的特定阶段"""
        try:
            # 添加详细日志
            logger.info(f"加载图表阶段 {stage_name}: kdata类型={type(kdata)}")

            # 验证kdata是否有效
            if kdata is None:
                logger.warning(f"跳过加载阶段 {stage_name}: K线数据为空")
                return

            if not isinstance(kdata, pd.DataFrame):
                logger.warning(f"跳过加载阶段 {stage_name}: K线数据类型错误: {type(kdata)}")
                return

            if kdata.empty:
                logger.warning(f"跳过加载阶段 {stage_name}: K线数据为空DataFrame")
                return

            # 验证必要的列
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [
                col for col in required_columns if col not in kdata.columns]
            if missing_columns and (stage_name == "basic_kdata" or stage_name == "volume"):
                logger.warning(
                    f"跳过加载阶段 {stage_name}: K线数据缺少必要列: {missing_columns}")
                return

            # 记录数据信息
            logger.info(
                f"加载阶段 {stage_name}: kdata形状={kdata.shape}, 列={list(kdata.columns)}")

            # 检查chart_widget
            if chart_widget is None:
                logger.warning(f"跳过加载阶段 {stage_name}: 图表控件为空")
                return

            # 基础K线数据（关键阶段）
            if stage_name == "basic_kdata":
                # 基础K线数据（关键阶段）
                has_update_basic_kdata = hasattr(
                    chart_widget, 'update_basic_kdata')
                logger.info(
                    f"图表控件是否有update_basic_kdata方法: {has_update_basic_kdata}")

                loader_func = chart_widget.update_basic_kdata if has_update_basic_kdata else chart_widget.update_chart
                data_params = kdata if has_update_basic_kdata else {
                    "kdata": kdata}

                logger.info(
                    f"提交基础K线数据加载任务: loader_func={loader_func.__name__}, data_params类型={type(data_params)}")

                self.submit_loading_task(
                    task_id=f"chart_basic_kdata_{id(kdata)}",
                    loader_func=loader_func,
                    data_params=data_params,
                    stage=LoadingStage.CRITICAL
                )
            # 成交量数据（高优先级）
            elif stage_name == "volume":
                # 成交量数据（高优先级）
                has_update_volume = hasattr(chart_widget, 'update_volume')
                logger.info(f"图表控件是否有update_volume方法: {has_update_volume}")

                loader_func = chart_widget.update_volume if has_update_volume else lambda x: None

                logger.info(
                    f"提交成交量数据加载任务: loader_func={loader_func.__name__ if hasattr(loader_func, '__name__') else 'lambda'}")

                self.submit_loading_task(
                    task_id=f"chart_volume_{id(kdata)}",
                    loader_func=loader_func,
                    data_params=kdata,
                    stage=LoadingStage.HIGH
                )
            # 基础指标（普通优先级）
            elif stage_name == "basic_indicators":
                # 基础指标（普通优先级）
                basic_indicators = {k: v for k, v in indicators.items(
                ) if self._is_high_priority_indicator(k)}
                logger.info(f"提交基础指标加载任务: 指标数量={len(basic_indicators)}")
                self._update_indicators_by_priority(
                    chart_widget, kdata, basic_indicators, LoadingStage.NORMAL)
            # 高级指标（低优先级）
            elif stage_name == "advanced_indicators":
                # 高级指标（低优先级）
                advanced_indicators = {k: v for k, v in indicators.items(
                ) if not self._is_high_priority_indicator(k)}
                logger.info(f"提交高级指标加载任务: 指标数量={len(advanced_indicators)}")
                self._update_indicators_by_priority(
                    chart_widget, kdata, advanced_indicators, LoadingStage.LOW)
            # 装饰元素（后台加载）
            elif stage_name == "decorations":
                # 装饰元素（后台加载）
                if hasattr(chart_widget, 'update_decorations'):
                    logger.info("提交装饰元素加载任务")
                    self.submit_loading_task(
                        task_id=f"chart_decorations_{id(kdata)}",
                        loader_func=chart_widget.update_decorations,
                        data_params={"kdata": kdata},
                        stage=LoadingStage.BACKGROUND
                    )
        except Exception as e:
            logger.error(f"加载图表阶段 {stage_name} 失败: {str(e)}", exc_info=True)

    def _load_chart_sync(self, chart_widget, kdata, indicators):
        """同步加载图表（作为渐进式加载的回退方案）"""
        try:
            # 一次性更新图表
            if hasattr(chart_widget, 'update_chart'):
                chart_widget.update_chart({
                    'kdata': kdata,
                    'indicators': indicators
                })
            logger.info("已回退到同步图表加载")
        except Exception as e:
            logger.error(f"同步加载图表失败: {e}")
            # 显示错误消息
            if hasattr(chart_widget, 'show_error'):
                chart_widget.show_error(f"加载图表失败: {e}")

    def _update_indicators_by_priority(self, chart_widget, kdata, indicators, priority):
        """按优先级更新指标"""
        if not indicators or not hasattr(chart_widget, 'update_indicators'):
            return

        # 提交指标更新任务
        self.submit_loading_task(
            task_id=f"chart_indicators_{priority.name}_{id(kdata)}",
            loader_func=chart_widget.update_indicators,
            data_params={"kdata": kdata, "indicators": indicators},
            stage=priority
        )

    def _is_high_priority_indicator(self, indicator):
        """判断是否为高优先级指标"""
        # 常用基础指标优先级高
        high_priority_indicators = {
            'MA', 'EMA', 'MACD', 'KDJ', 'RSI', 'BOLL', 'VOL',
            'ma', 'ema', 'macd', 'kdj', 'rsi', 'boll', 'vol'
        }

        # 检查指标名称是否在高优先级列表中
        for name in high_priority_indicators:
            if name in indicator.upper():
                return True

        return False

    def submit_loading_task(self, task_id: str, loader_func: Callable, data_params: Dict[str, Any],
                            stage: LoadingStage = LoadingStage.NORMAL,
                            callback: Optional[Callable] = None,
                            delay_ms: int = 0,
                            priority_within_stage: int = 0) -> bool:
        """
        提交加载任务

        Args:
            task_id: 任务ID
            loader_func: 加载函数
            data_params: 数据参数
            stage: 加载阶段
            callback: 回调函数
            delay_ms: 延迟执行时间（毫秒）
            priority_within_stage: 阶段内优先级

        Returns:
            是否成功提交
        """
        if not self.is_running:
            logger.warning("加载管理器未启动，无法提交任务")
            return False

        # 创建加载任务
        task = LoadingTask(
            id=task_id,
            stage=stage,
            loader_func=loader_func,
            data_params=data_params,
            callback=callback,
            delay_ms=delay_ms,
            priority_within_stage=priority_within_stage
        )

        try:
            # 添加到队列
            self.task_queue.put(task)
            
            # 修复：使用信号机制立即唤醒工作线程
            self.task_available.set()

            # 更新统计
            with self.stats_lock:
                self.stats['total_tasks'] += 1
                self.stats['stage_stats'][stage.name]['submitted'] += 1

            logger.debug(f"提交加载任务: {task_id} ({stage.name})")
            return True
        except Exception as e:
            logger.error(f"提交加载任务失败: {e}")
            return False

    def cancel_task(self, task_id: str) -> bool:
        """
        取消加载任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        # 检查是否在活动任务中
        with self.active_tasks_lock:
            if task_id in self.active_tasks:
                future = self.active_tasks[task_id]
                if future and not future.done():
                    cancelled = future.cancel()
                    if cancelled:
                        # 更新统计
                        with self.stats_lock:
                            self.stats['cancelled_tasks'] += 1
                        logger.debug(f"已取消加载任务: {task_id}")
                    return cancelled

        # 任务不在活动任务中，可能在队列中或已完成
        logger.debug(f"无法取消任务 {task_id}，任务可能不存在或已完成")
        return False

    def preload_data(self, symbols: List[str], data_loader: Callable,
                     callback: Optional[Callable] = None) -> int:
        """
        预加载数据

        Args:
            symbols: 股票代码列表
            data_loader: 数据加载函数
            callback: 回调函数

        Returns:
            成功提交的任务数量
        """
        if not symbols or not data_loader:
            return 0

        submitted = 0
        for i, symbol in enumerate(symbols):
            # 创建任务ID
            task_id = f"preload_{symbol}_{int(time.time())}"

            # 计算优先级（列表前面的优先级高）
            priority = i

            # 提交任务
            success = self.submit_loading_task(
                task_id=task_id,
                loader_func=data_loader,
                data_params={"symbol": symbol},
                stage=LoadingStage.BACKGROUND,  # 预加载使用后台阶段
                callback=callback,
                priority_within_stage=priority
            )

            if success:
                submitted += 1

        logger.info(f"已提交 {submitted} 个预加载任务")
        return submitted

    def get_loading_status(self) -> Dict[str, Any]:
        """获取加载状态"""
        with self.stats_lock:
            stats = self.stats.copy()

        # 获取活动任务数
        with self.active_tasks_lock:
            active_tasks = len(self.active_tasks)

        # 计算队列任务数
        queue_size = self.task_queue.qsize()

        status = {
            'is_running': self.is_running,
            'active_tasks': active_tasks,
            'queue_size': queue_size,
            'stats': stats,
            'stage_delays': {stage.name: delay for stage, delay in self.stage_delays.items()}
        }

        return status

    def clear_stage_queue(self, stage: LoadingStage = None):
        """
        清空指定阶段的任务队列

        Args:
            stage: 要清空的阶段，如果为None则清空所有阶段
        """
        if stage is None:
            # 清空整个队列
            cleared_count = 0
            while not self.task_queue.empty():
                try:
                    self.task_queue.get_nowait()
                    self.task_queue.task_done()
                    cleared_count += 1
                except Empty:
                    break
            
            # 修复：清空队列后清除信号
            if cleared_count > 0:
                self.task_available.clear()
                logger.info(f"已清空所有阶段的任务队列，清除 {cleared_count} 个任务")
        else:
            # 清空指定阶段的任务
            # 由于PriorityQueue不支持按条件删除，我们需要创建一个新队列
            new_queue = PriorityQueue()
            cleared_count = 0
            kept_count = 0

            # 移动所有不属于指定阶段的任务到新队列
            while not self.task_queue.empty():
                try:
                    task = self.task_queue.get_nowait()
                    if task.stage != stage:
                        new_queue.put(task)
                        kept_count += 1
                    else:
                        cleared_count += 1
                    self.task_queue.task_done()
                except Empty:
                    break

            # 替换队列
            self.task_queue = new_queue
            
            # 修复：如果新队列有任务，设置信号；否则清除信号
            if not self.task_queue.empty():
                self.task_available.set()
            else:
                self.task_available.clear()
            
            logger.info(f"已清空 {stage.name} 阶段的任务队列，清除 {cleared_count} 个任务，保留 {kept_count} 个任务")

    def cancel_all_tasks(self):
        """取消所有任务"""
        # 清空队列
        self.clear_stage_queue()

        # 取消所有活动任务
        with self.active_tasks_lock:
            for task_id, future in list(self.active_tasks.items()):
                if future and not future.done():
                    future.cancel()

            # 更新统计
            with self.stats_lock:
                self.stats['cancelled_tasks'] += len(self.active_tasks)

            # 清空活动任务
            self.active_tasks.clear()

        logger.info("已取消所有任务")

    def set_stage_delay(self, stage: LoadingStage, delay_ms: int):
        """设置阶段延迟"""
        self.stage_delays[stage] = max(0, delay_ms)
        logger.debug(f"已设置 {stage.name} 阶段延迟为 {delay_ms}ms")

    def get_stage_delays(self) -> Dict[str, int]:
        """获取阶段延迟"""
        return {stage.name: delay for stage, delay in self.stage_delays.items()}

    def reset_stats(self):
        """重置统计信息"""
        with self.stats_lock:
            self.stats = {
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'cancelled_tasks': 0,
                'stage_stats': {stage.name: {'submitted': 0, 'completed': 0, 'failed': 0}
                                for stage in LoadingStage}
            }
        logger.debug("已重置统计信息")

# 全局实例
_progressive_loader = None

def get_progressive_loader() -> ProgressiveLoadingManager:
    """获取全局渐进式加载管理器实例"""
    global _progressive_loader
    if _progressive_loader is None:
        _progressive_loader = ProgressiveLoadingManager()
        _progressive_loader.start()
    return _progressive_loader

def initialize_progressive_loader(max_workers: int = os.cpu_count() * 2, enable_delays: bool = True):
    """初始化全局渐进式加载管理器"""
    global _progressive_loader
    if _progressive_loader is not None:
        _progressive_loader.stop()
    _progressive_loader = ProgressiveLoadingManager(max_workers, enable_delays)
    _progressive_loader.start()
    return _progressive_loader

def shutdown_progressive_loader():
    """关闭全局渐进式加载管理器"""
    global _progressive_loader
    if _progressive_loader is not None:
        _progressive_loader.stop()
        _progressive_loader = None

# 便捷函数
def load_progressive(task_id: str, loader_func: Callable, data_params: Dict[str, Any],
                     stage: LoadingStage = LoadingStage.NORMAL,
                     callback: Optional[Callable] = None) -> bool:
    """渐进式加载便捷函数"""
    return get_progressive_loader().submit_loading_task(task_id, loader_func, data_params, stage, callback)

def load_chart_progressive(chart_widget, kdata, indicators, stages=None) -> bool:
    """渐进式加载图表便捷函数
    
    Args:
        chart_widget: 图表控件
        kdata: K线数据
        indicators: 指标数据
        stages: 加载阶段配置（可选，当前版本忽略此参数，保持向后兼容）
    
    Returns:
        是否成功提交任务
    """
    # stages参数保留用于向后兼容，但当前实现不使用
    if stages is not None:
        logger.debug(f"load_chart_progressive收到stages参数（已忽略，保持向后兼容）: {stages}")
    return get_progressive_loader().load_chart_progressive(chart_widget, kdata, indicators)
