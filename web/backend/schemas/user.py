"""
用户Schema
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class UserLogin(BaseModel):
    """
    用户登录请求
    """
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")
    two_fa_code: Optional[str] = Field(None, max_length=10, description="双因素认证码")


class UserRegister(BaseModel):
    """
    用户注册请求
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    phone: Optional[str] = Field(None, max_length=20, description="电话")


class TokenResponse(BaseModel):
    """
    Token响应
    """
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(..., description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")


class UserResponse(BaseModel):
    """
    用户响应
    """
    id: int
    username: str
    email: str
    full_name: Optional[str]
    phone: Optional[str]
    is_active: bool
    is_admin: bool
    two_fa_enabled: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """
    用户详情响应
    """
    last_login_at: Optional[datetime]
    last_login_ip: Optional[str]
    failed_login_attempts: int
    locked_until: Optional[datetime]


class UserCreate(BaseModel):
    """
    创建用户请求
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    is_admin: bool = Field(False, description="是否管理员")


class UserUpdate(BaseModel):
    """
    修改用户请求
    """
    email: Optional[EmailStr] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    is_active: Optional[bool] = Field(None, description="是否激活")
    is_admin: Optional[bool] = Field(None, description="是否管理员")


class UserFilter(BaseModel):
    """
    用户过滤参数
    """
    username: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserListResponse(BaseModel):
    """
    用户列表响应
    """
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


class RoleResponse(BaseModel):
    """
    角色响应
    """
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    """
    权限响应
    """
    id: int
    code: str
    name: str
    description: Optional[str]
    module: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
