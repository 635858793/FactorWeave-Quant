"""
通知Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class NotificationCreate(BaseModel):
    """
    创建通知请求
    """
    user_id: int = Field(..., description="用户ID")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    type: str = Field("info", description="通知类型: info, warning, error, success")
    channels: Optional[List[str]] = Field(["in_app"], description="通知渠道: email, sms, in_app")


class NotificationResponse(BaseModel):
    """
    通知响应
    """
    id: int
    user_id: int
    title: str
    content: str
    type: str
    channels: List[str]
    status: str
    read: bool
    read_at: Optional[datetime]
    created_at: datetime
    sent_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """
    通知列表响应
    """
    notifications: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    unread_count: int


class NotificationPreferenceCreate(BaseModel):
    """
    创建通知偏好设置请求
    """
    email_enabled: Optional[bool] = Field(True, description="启用邮件通知")
    sms_enabled: Optional[bool] = Field(False, description="启用短信通知")
    in_app_enabled: Optional[bool] = Field(True, description="启用应用内通知")
    order_notifications: Optional[bool] = Field(True, description="订单通知")
    account_notifications: Optional[bool] = Field(True, description="账户通知")
    system_notifications: Optional[bool] = Field(True, description="系统通知")
    security_notifications: Optional[bool] = Field(True, description="安全通知")


class NotificationPreferenceResponse(BaseModel):
    """
    通知偏好设置响应
    """
    id: int
    user_id: int
    email_enabled: bool
    sms_enabled: bool
    in_app_enabled: bool
    order_notifications: bool
    account_notifications: bool
    system_notifications: bool
    security_notifications: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class NotificationStatsResponse(BaseModel):
    """
    通知统计响应
    """
    total: int
    unread: int
    read: int
    by_type: dict
    recent_notifications: List[NotificationResponse]
