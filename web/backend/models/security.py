"""
安全模型
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from web.backend.config.database import Base


class IPWhitelist(Base):
    """
    IP白名单模型
    """
    __tablename__ = "ip_whitelist"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    ip_address = Column(String(50), unique=True, index=True, nullable=False, comment="IP地址")
    ip_range = Column(String(100), comment="IP范围")
    description = Column(Text, comment="描述")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class IPBlacklist(Base):
    """
    IP黑名单模型
    """
    __tablename__ = "ip_blacklist"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    ip_address = Column(String(50), unique=True, index=True, nullable=False, comment="IP地址")
    ip_range = Column(String(100), comment="IP范围")
    description = Column(Text, comment="描述")
    reason = Column(Text, comment="原因")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class SecurityAuditLog(Base):
    """
    安全审计日志模型
    """
    __tablename__ = "security_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    user_id = Column(Integer, ForeignKey("users.id"), comment="用户ID")
    username = Column(String(50), comment="用户名")
    action = Column(String(50), nullable=False, comment="操作类型")
    resource_type = Column(String(50), comment="资源类型")
    resource_id = Column(String(50), comment="资源ID")
    ip_address = Column(String(50), comment="IP地址")
    user_agent = Column(Text, comment="User Agent")
    request_method = Column(String(10), comment="请求方法")
    request_path = Column(String(255), comment="请求路径")
    request_params = Column(Text, comment="请求参数")
    response_status = Column(Integer, comment="响应状态")
    response_time = Column(Integer, comment="响应时间(ms)")
    success = Column(Boolean, comment="是否成功")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
