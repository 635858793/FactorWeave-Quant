from loguru import logger
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd


@dataclass
class WriteTask:
    """数据库写入任务"""
    buffer_key: str  # 缓冲区键（asset_type_task_id）
    data: pd.DataFrame  # 待写入数据
    asset_type: Any  # 资产类型
    data_type: Any  # 数据类型
    priority: int = 0  # 优先级（暂未使用）


class TaskExecutionStatus(Enum):
    """任务执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskExecutionResult:
    """任务执行结果"""
    task_id: str
    status: TaskExecutionStatus
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_time: float = 0.0
    processed_symbols_list: List[str] = field(default_factory=list)

    @property
    def progress(self) -> float:
        """计算进度百分比"""
        if self.total_records == 0:
            return 0.0
        return (self.processed_records / self.total_records) * 100

    @property
    def success(self) -> bool:
        """判断任务是否成功完成"""
        return self.status == TaskExecutionStatus.COMPLETED and self.failed_records == 0

    @property
    def progress_percentage(self) -> float:
        """进度百分比（兼容属性）"""
        return self.progress
