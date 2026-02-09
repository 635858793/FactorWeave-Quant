"""
实时写入服务实现

核心实时写入业务逻辑服务，负责协调数据写入过程。
基于现有ImportExecutionEngine和AssetSeparatedDatabaseManager增强。
"""

import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import pandas as pd
from loguru import logger

from core.services.realtime_write_interfaces import IRealtimeWriteService
from core.services.realtime_write_config import RealtimeWriteConfig, WriteStrategy
from core.events.realtime_write_events import (
    WriteStartedEvent, WriteProgressEvent, WriteCompletedEvent, WriteErrorEvent
)
from core.events import get_event_bus


@dataclass
class WriteTaskState:
    """写入任务状态"""
    task_id: str
    status: str                    # running, paused, completed, failed
    total_symbols: int
    written_symbols: int = 0
    success_count: int = 0
    failure_count: int = 0
    start_time: datetime = None
    pause_time: Optional[datetime] = None
    total_records: int = 0
    written_records: int = 0
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()


class RealtimeWriteService(IRealtimeWriteService):
    """
    实时写入服务实现
    
    负责协调数据写入过程，包括：
    - 数据写入控制
    - 进度跟踪
    - 事件发布
    - 错误处理
    """
    
    def __init__(self, config: RealtimeWriteConfig = None):
        """
        初始化实时写入服务
        
        Args:
            config: 写入配置
        """
        try:
            self.config = config or RealtimeWriteConfig()
            self.config.validate()
            
            self.event_bus = get_event_bus()
            if self.event_bus is None:
                logger.warning("EventBus未初始化，使用None")
            
            # 任务状态管理
            self.tasks: Dict[str, WriteTaskState] = {}
            self.task_lock = threading.Lock()
            
            # 导入必要的数据库管理器
            self.asset_manager = None
            self._initialize_asset_manager()
            
            # 批量写入缓冲区
            self._batch_buffer: Dict[str, pd.DataFrame] = {}
            self._batch_lock = threading.Lock()
            
            # 性能监控数据
            self._performance_stats: Dict[str, Dict[str, float]] = {}
            
            # 内存监控数据
            self._memory_stats: Dict[str, float] = {}
            
            logger.info(f"RealtimeWriteService初始化完成，配置: {self.config.to_dict()}")
        except Exception as init_error:
            logger.error(f"RealtimeWriteService初始化失败: {init_error}")
            raise
    
    def _initialize_asset_manager(self):
        """初始化资产数据库管理器"""
        try:
            from core.asset_database_manager import AssetSeparatedDatabaseManager
            self.asset_manager = AssetSeparatedDatabaseManager()
            logger.debug("资产数据库管理器初始化成功")
        except Exception as e:
            logger.error(f"资产数据库管理器初始化失败: {e}")
    
    def start_write(self, task_id: str, config: Dict[str, Any] = None) -> bool:
        """开始实时写入任务"""
        try:
            with self.task_lock:
                if task_id in self.tasks:
                    logger.warning(f"任务 {task_id} 已存在")
                    return False
                
                # 创建任务状态
                state = WriteTaskState(
                    task_id=task_id,
                    status="running",
                    total_symbols=0
                )
                self.tasks[task_id] = state
            
            logger.info(f"开始实时写入任务: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动写入任务失败: {e}")
            return False
    
    def write_data(self, symbol: str, data: pd.DataFrame,
                   asset_type: str = "STOCK_A", data_source: str = "unknown") -> bool:
        """
        写入数据
        
        Args:
            symbol: 股票代码
            data: 数据DataFrame
            asset_type: 资产类型
            data_source: 数据来源
            
        Returns:
            是否写入成功
        """
        if data is None or data.empty:
            logger.warning(f"数据为空，跳过写入: {symbol}")
            return False
        
        if not data_source or data_source == 'unknown':
            logger.warning(f"data_source 为空或无效: {data_source}，symbol: {symbol}")
        
        try:
            start_time = time.time()
            
            # 检查是否启用实时写入
            if not self.config.enabled:
                logger.debug(f"实时写入已禁用，跳过写入: {symbol}")
                return False
            
            # 根据写入策略选择写入方式
            if self.config.write_strategy == WriteStrategy.BATCH:
                return self._write_batch_mode(symbol, data, asset_type, data_source, start_time)
            elif self.config.write_strategy == WriteStrategy.REALTIME:
                return self._write_realtime_mode(symbol, data, asset_type, data_source, start_time)
            elif self.config.write_strategy == WriteStrategy.ADAPTIVE:
                return self._write_adaptive_mode(symbol, data, asset_type, data_source, start_time)
            else:
                logger.warning(f"未知的写入策略: {self.config.write_strategy}，使用实时模式")
                return self._write_realtime_mode(symbol, data, asset_type, data_source, start_time)
                
        except Exception as e:
            logger.error(f"写入数据失败 {symbol}: {e}，data_source: {data_source}")
            return False
    
    def _write_batch_mode(self, symbol: str, data: pd.DataFrame,
                        asset_type: str, data_source: str, start_time: float) -> bool:
        """
        批量写入模式
        
        累积数据到batch_size条后一次性写入
        """
        try:
            with self._batch_lock:
                # 将数据添加到缓冲区
                if symbol not in self._batch_buffer:
                    self._batch_buffer[symbol] = []
                
                self._batch_buffer[symbol].append(data)
                
                # 计算缓冲区总记录数
                total_records = sum(len(df) for df in self._batch_buffer[symbol])
                
                # 检查是否达到批量大小
                if total_records >= self.config.batch_size:
                    # 合并所有数据
                    merged_data = pd.concat(self._batch_buffer[symbol], ignore_index=True)
                    
                    # 清空缓冲区
                    self._batch_buffer[symbol] = []
                    
                    # 执行写入
                    success = self._execute_write(symbol, merged_data, asset_type, data_source, start_time, total_records)
                    
                    if success:
                        logger.info(f"批量写入 {symbol}: {total_records} 条记录，策略: 批量")
                    
                    return success
                else:
                    logger.debug(f"数据已缓冲 {symbol}: {total_records}/{self.config.batch_size} 条记录")
                    return True
                    
        except Exception as e:
            logger.error(f"批量写入失败 {symbol}: {e}")
            return False
    
    def _write_realtime_mode(self, symbol: str, data: pd.DataFrame,
                           asset_type: str, data_source: str, start_time: float) -> bool:
        """
        实时写入模式
        
        每条数据立即写入
        """
        return self._execute_write(symbol, data, asset_type, data_source, start_time, len(data))
    
    def _write_adaptive_mode(self, symbol: str, data: pd.DataFrame,
                          asset_type: str, data_source: str, start_time: float) -> bool:
        """
        自适应写入模式
        
        根据写入速度自动调整策略
        """
        try:
            # 获取历史性能统计
            stats = self._performance_stats.get(symbol, {})
            avg_speed = stats.get('avg_speed', 0)
            
            # 如果平均速度低于阈值，使用批量模式
            if avg_speed > 0 and avg_speed < self.config.performance_warning_threshold:
                logger.debug(f"写入速度较低 ({avg_speed:.0f}条/秒)，使用批量模式: {symbol}")
                return self._write_batch_mode(symbol, data, asset_type, data_source, start_time)
            else:
                logger.debug(f"写入速度正常 ({avg_speed:.0f}条/秒)，使用实时模式: {symbol}")
                return self._write_realtime_mode(symbol, data, asset_type, data_source, start_time)
                
        except Exception as e:
            logger.error(f"自适应写入失败 {symbol}: {e}")
            return False
    
    def _execute_write(self, symbol: str, data: pd.DataFrame,
                     asset_type: str, data_source: str, start_time: float, record_count: int) -> bool:
        """
        执行写入（包含性能和内存监控）
        
        Args:
            symbol: 股票代码
            data: 数据DataFrame
            asset_type: 资产类型
            data_source: 数据来源
            start_time: 开始时间
            record_count: 记录数
            
        Returns:
            是否写入成功
        """
        try:
            # 性能监控：记录开始时间
            if self.config.enable_performance_monitoring:
                write_start = time.time()
            
            # 内存监控：记录开始内存
            if self.config.enable_memory_monitoring:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # 使用资产数据库管理器写入数据
            if self.asset_manager:
                from core.plugin_types import AssetType, DataType
                
                # 转换资产类型
                asset_type_enum = self._convert_asset_type(asset_type)
                
                # 确保数据中包含 data_source 列
                data_to_write = data.copy()
                if 'data_source' not in data_to_write.columns:
                    data_to_write['data_source'] = data_source
                
                # 写入数据
                success = self.asset_manager.store_standardized_data(
                    data=data_to_write,
                    asset_type=asset_type_enum,
                    data_type=DataType.HISTORICAL_KLINE
                )
                
                if success:
                    # 性能监控：计算并记录性能
                    if self.config.enable_performance_monitoring:
                        write_time = time.time() - write_start
                        write_speed = record_count / write_time if write_time > 0 else 0
                        
                        # 更新性能统计
                        if symbol not in self._performance_stats:
                            self._performance_stats[symbol] = {}
                        self._performance_stats[symbol]['last_write_time'] = write_time
                        self._performance_stats[symbol]['last_write_speed'] = write_speed
                        self._performance_stats[symbol]['avg_speed'] = (
                            self._performance_stats[symbol].get('avg_speed', 0) * 0.9 + write_speed * 0.1
                        )
                        
                        logger.info(f"写入 {symbol}: {record_count} 条记录，耗时 {write_time:.2f}秒，速度 {write_speed:.0f}条/秒")
                    
                    # 内存监控：计算并记录内存使用
                    if self.config.enable_memory_monitoring:
                        memory_after = process.memory_info().rss / 1024 / 1024  # MB
                        memory_delta = memory_after - memory_before
                        
                        # 更新内存统计
                        self._memory_stats[symbol] = memory_after
                        
                        logger.debug(f"内存使用 {symbol}: {memory_before:.2f}MB -> {memory_after:.2f}MB (delta: {memory_delta:.2f}MB)")
                    
                    return True
                else:
                    logger.error(f"写入 {symbol} 失败，data_source: {data_source}")
                    return False
            else:
                logger.error("资产数据库管理器未初始化")
                return False
                
        except Exception as e:
            logger.error(f"写入数据失败 {symbol}: {e}，data_source: {data_source}")
            return False
    
    def flush_batch_buffer(self, symbol: Optional[str] = None) -> bool:
        """
        刷新批量写入缓冲区
        
        Args:
            symbol: 股票代码，如果为None则刷新所有
            
        Returns:
            是否刷新成功
        """
        try:
            with self._batch_lock:
                if symbol:
                    # 刷新指定股票的缓冲区
                    if symbol in self._batch_buffer and self._batch_buffer[symbol]:
                        merged_data = pd.concat(self._batch_buffer[symbol], ignore_index=True)
                        self._batch_buffer[symbol] = []
                        
                        if not merged_data.empty:
                            success = self._execute_write(symbol, merged_data, "STOCK_A", "flush", time.time(), len(merged_data))
                            if success:
                                logger.info(f"刷新缓冲区 {symbol}: {len(merged_data)} 条记录")
                            return success
                else:
                    # 刷新所有缓冲区
                    for sym, buffer_list in self._batch_buffer.items():
                        if buffer_list:
                            merged_data = pd.concat(buffer_list, ignore_index=True)
                            self._batch_buffer[sym] = []
                            
                            if not merged_data.empty:
                                success = self._execute_write(sym, merged_data, "STOCK_A", "flush", time.time(), len(merged_data))
                                if success:
                                    logger.info(f"刷新缓冲区 {sym}: {len(merged_data)} 条记录")
                    return True
                    
        except Exception as e:
            logger.error(f"刷新缓冲区失败: {e}")
            return False
    
    def pause_write(self, task_id: str) -> bool:
        """暂停写入任务"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    logger.warning(f"任务 {task_id} 不存在")
                    return False
                
                state = self.tasks[task_id]
                if state.status != "running":
                    logger.warning(f"任务 {task_id} 未在运行中")
                    return False
                
                state.status = "paused"
                state.pause_time = datetime.now()
                
                logger.info(f"任务 {task_id} 已暂停")
                return True
                
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False
    
    def resume_write(self, task_id: str) -> bool:
        """恢复写入任务"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    logger.warning(f"任务 {task_id} 不存在")
                    return False
                
                state = self.tasks[task_id]
                if state.status != "paused":
                    logger.warning(f"任务 {task_id} 未被暂停")
                    return False
                
                state.status = "running"
                state.pause_time = None
                
                logger.info(f"任务 {task_id} 已恢复")
                return True
                
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            return False
    
    def cancel_write(self, task_id: str) -> bool:
        """取消写入任务"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    logger.warning(f"任务 {task_id} 不存在")
                    return False
                
                state = self.tasks[task_id]
                state.status = "cancelled"
                
                logger.info(f"任务 {task_id} 已取消")
                return True
                
        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return False
    
    def complete_write(self, task_id: str) -> bool:
        """完成写入任务"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    logger.warning(f"任务 {task_id} 不存在")
                    return False
                
                state = self.tasks[task_id]
                state.status = "completed"
                
                # 计算统计信息
                duration = (datetime.now() - state.start_time).total_seconds()
                avg_speed = state.written_records / duration if duration > 0 else 0
                
                # 发布完成事件
                event = WriteCompletedEvent(
                    task_id=task_id,
                    total_symbols=state.total_symbols,
                    success_count=state.success_count,
                    failure_count=state.failure_count,
                    total_records=state.written_records,
                    duration=duration,
                    average_speed=avg_speed
                )
                self.event_bus.publish(event)
                
                logger.info(f"任务 {task_id} 已完成: "
                          f"总符号数={state.total_symbols}, "
                          f"成功={state.success_count}, "
                          f"失败={state.failure_count}, "
                          f"总记录数={state.written_records}, "
                          f"平均速度={avg_speed:.0f}条/秒")
                
                return True
                
        except Exception as e:
            logger.error(f"完成任务失败: {e}")
            return False
    
    def handle_error(self, task_id: str, error: Exception) -> bool:
        """处理写入错误"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    logger.warning(f"任务 {task_id} 不存在")
                    return False
                
                state = self.tasks[task_id]
                state.failure_count += 1
                
                # 发布错误事件
                event = WriteErrorEvent(
                    task_id=task_id,
                    symbol="unknown",
                    error=str(error),
                    error_type=type(error).__name__,
                    error_details={
                        'timestamp': datetime.now().isoformat(),
                        'state': {
                            'total_symbols': state.total_symbols,
                            'written_symbols': state.written_symbols,
                            'written_records': state.written_records
                        }
                    }
                )
                self.event_bus.publish(event)
                
                logger.error(f"任务 {task_id} 写入错误: {error}")
                return True
                
        except Exception as e:
            logger.error(f"处理错误失败: {e}")
            return False
    
    def get_task_state(self, task_id: str) -> Optional[WriteTaskState]:
        """获取任务状态"""
        with self.task_lock:
            return self.tasks.get(task_id)
    
    def _convert_asset_type(self, asset_type_str: str):
        """将字符串资产类型转换为枚举"""
        try:
            from core.plugin_types import AssetType
            
            # 如果已经是字符串，尝试转换
            if isinstance(asset_type_str, str):
                # 处理映射
                mapping = {
                    "STOCK_A": AssetType.STOCK_A,
                    "STOCK_US": AssetType.STOCK_US,
                    "CRYPTO": AssetType.CRYPTO,
                    "FUTURES": AssetType.FUTURES,
                    "STOCK_HK": AssetType.STOCK_HK,
                }
                return mapping.get(asset_type_str, AssetType.STOCK_A)
            else:
                return asset_type_str
        except Exception as e:
            logger.warning(f"资产类型转换失败，使用默认值: {e}")
            from core.plugin_types import AssetType
            return AssetType.STOCK_A
