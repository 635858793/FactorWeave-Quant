"""
通用Schema
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class PaginationRequest(BaseModel):
    """
    分页请求
    """
    page: int = 1
    page_size: int = 20


class PaginationResponse(BaseModel):
    """
    分页响应
    """
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    """
    消息响应
    """
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """
    错误响应
    """
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    """
    健康检查响应
    """
    status: str
    service: str
    version: str
    timestamp: datetime


class MetricsResponse(BaseModel):
    """
    指标响应
    """
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: float
    network_out: float
    request_count: int
    error_count: int
    uptime: float
