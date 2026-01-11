"""
通知模型
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from web.backend.config.database import Base


class Notification(Base):
    """
    通知模型
    """
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    type = Column(String(50), default="info", comment="通知类型: info, warning, error, success")
    channels = Column(JSON, default=lambda: ["in_app"], comment="通知渠道: email, sms, in_app")
    status = Column(String(50), default="pending", comment="状态: pending, sent, failed")
    read = Column(Boolean, default=False, comment="是否已读")
    read_at = Column(DateTime(timezone=True), comment="已读时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    sent_at = Column(DateTime(timezone=True), comment="发送时间")
    
    user = relationship("User", back_populates="notifications")


class NotificationPreference(Base):
    """
    通知偏好设置模型
    """
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, comment="用户ID")
    email_enabled = Column(Boolean, default=True, comment="启用邮件通知")
    sms_enabled = Column(Boolean, default=False, comment="启用短信通知")
    in_app_enabled = Column(Boolean, default=True, comment="启用应用内通知")
    order_notifications = Column(Boolean, default=True, comment="订单通知")
    account_notifications = Column(Boolean, default=True, comment="账户通知")
    system_notifications = Column(Boolean, default=True, comment="系统通知")
    security_notifications = Column(Boolean, default=True, comment="安全通知")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    user = relationship("User", back_populates="notification_preferences")
