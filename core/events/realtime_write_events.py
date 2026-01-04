"""
实时写入事件定义

定义了数据导入过程中的实时写入相关事件。
这些事件用于驱动UI更新、监控报告、错误处理等。
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from datetime import datetime
from .types import BaseEvent


@dataclass
class WriteStartedEvent(BaseEvent):
    """
    实时写入开始事件
    
    当开始对数据进行实时写入时发布此事件。
    """
    task_id: str = ""
    task_name: str = ""
    symbols: list = field(default_factory=list)
    total_records: int = 0
    event_type: str = "write_started"
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'task_name': self.task_name,
            'symbols': self.symbols,
            'total_records': self.total_records
        })


@dataclass
class WriteProgressEvent(BaseEvent):
    """
    实时写入进度事件
    
    在写入过程中定期发布此事件，包含进度信息和统计数据。
    """
    task_id: str = ""
    symbol: str = ""
    progress: float = 0.0
    written_count: int = 0
    total_count: int = 0
    write_speed: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    status: str = "writing"
    event_type: str = "write_progress"
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'symbol': self.symbol,
            'progress': self.progress,
            'written_count': self.written_count,
            'total_count': self.total_count,
            'write_speed': self.write_speed,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'status': self.status
        })


@dataclass
class WriteCompletedEvent(BaseEvent):
    """
    实时写入完成事件
    
    当所有数据写入完成时发布此事件。
    """
    task_id: str = ""
    total_symbols: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_records: int = 0
    duration: float = 0.0
    average_speed: float = 0.0
    event_type: str = "write_completed"
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'total_symbols': self.total_symbols,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'total_records': self.total_records,
            'duration': self.duration,
            'average_speed': self.average_speed
        })


@dataclass
class WriteErrorEvent(BaseEvent):
    """
    实时写入错误事件
    
    当写入过程中发生错误时发布此事件。
    """
    task_id: str = ""
    symbol: str = ""
    error: str = ""
    error_type: str = ""
    retry_count: int = 0
    error_details: Dict[str, Any] = field(default_factory=dict)
    event_type: str = "write_error"
    
    def __post_init__(self):
        super().__post_init__()
        self.data.update({
            'task_id': self.task_id,
            'symbol': self.symbol,
            'error': self.error,
            'error_type': self.error_type,
            'retry_count': self.retry_count,
            'error_details': self.error_details
        })
