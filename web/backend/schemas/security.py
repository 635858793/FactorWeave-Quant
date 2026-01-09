"""
安全Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SecurityConfigResponse(BaseModel):
    """
    安全配置响应
    """
    id: int
    ip_whitelist_enabled: bool
    ip_blacklist_enabled: bool
    request_signature_enabled: bool
    https_force: bool
    hsts_max_age: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SecurityConfigUpdate(BaseModel):
    """
    更新安全配置请求
    """
    ip_whitelist_enabled: Optional[bool] = Field(None, description="启用IP白名单")
    ip_blacklist_enabled: Optional[bool] = Field(None, description="启用IP黑名单")
    request_signature_enabled: Optional[bool] = Field(None, description="启用请求签名")
    https_force: Optional[bool] = Field(None, description="强制HTTPS")
    hsts_max_age: Optional[int] = Field(None, description="HSTS最大年龄")


class IPWhitelistCreate(BaseModel):
    """
    添加IP白名单请求
    """
    ip_address: str = Field(..., description="IP地址")
    ip_range: Optional[str] = Field(None, description="IP范围")
    description: Optional[str] = Field(None, description="描述")


class IPWhitelistResponse(BaseModel):
    """
    IP白名单响应
    """
    id: int
    ip_address: str
    ip_range: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class IPWhitelistListResponse(BaseModel):
    """
    IP白名单列表响应
    """
    whitelist: List[IPWhitelistResponse]
    total: int
    page: int
    page_size: int


class IPBlacklistCreate(BaseModel):
    """
    添加IP黑名单请求
    """
    ip_address: str = Field(..., description="IP地址")
    ip_range: Optional[str] = Field(None, description="IP范围")
    description: Optional[str] = Field(None, description="描述")
    reason: Optional[str] = Field(None, description="原因")


class IPBlacklistResponse(BaseModel):
    """
    IP黑名单响应
    """
    id: int
    ip_address: str
    ip_range: Optional[str]
    description: Optional[str]
    reason: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class IPBlacklistListResponse(BaseModel):
    """
    IP黑名单列表响应
    """
    blacklist: List[IPBlacklistResponse]
    total: int
    page: int
    page_size: int


class AuditLogResponse(BaseModel):
    """
    审计日志响应
    """
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_method: Optional[str]
    request_path: Optional[str]
    request_params: Optional[str]
    response_status: Optional[int]
    response_time: Optional[int]
    success: Optional[bool]
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """
    审计日志列表响应
    """
    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
