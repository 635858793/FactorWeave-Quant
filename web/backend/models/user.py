"""
用户模型
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from web.backend.config.database import Base


class User(Base):
    """
    用户模型
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, comment="用户ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    full_name = Column(String(100), comment="全名")
    phone = Column(String(20), comment="电话")
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_admin = Column(Boolean, default=False, comment="是否管理员")
    two_fa_enabled = Column(Boolean, default=False, comment="是否启用双因素认证")
    two_fa_secret = Column(String(255), comment="双因素认证密钥")
    failed_login_attempts = Column(Integer, default=0, comment="失败登录次数")
    locked_until = Column(DateTime, comment="锁定直到")
    last_login_at = Column(DateTime, comment="最后登录时间")
    last_login_ip = Column(String(50), comment="最后登录IP")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    password_history = relationship("UserPasswordHistory", back_populates="user", cascade="all, delete-orphan")
    login_logs = relationship("UserLoginLog", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    notification_preferences = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Role(Base):
    """
    角色模型
    """
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True, comment="角色ID")
    name = Column(String(50), unique=True, index=True, nullable=False, comment="角色名称")
    description = Column(Text, comment="角色描述")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class Permission(Base):
    """
    权限模型
    """
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True, comment="权限ID")
    code = Column(String(100), unique=True, index=True, nullable=False, comment="权限代码")
    name = Column(String(100), nullable=False, comment="权限名称")
    description = Column(Text, comment="权限描述")
    module = Column(String(50), comment="模块")
    resource = Column(String(50), comment="资源")
    action = Column(String(50), comment="操作")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    roles = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class UserRole(Base):
    """
    用户角色关联模型
    """
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, comment="角色ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 关系
    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")


class RolePermission(Base):
    """
    角色权限关联模型
    """
    __tablename__ = "role_permissions"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, comment="角色ID")
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, comment="权限ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 关系
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")


class UserSession(Base):
    """
    用户会话模型
    """
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True, comment="会话ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    token = Column(String(255), unique=True, index=True, nullable=False, comment="Token")
    refresh_token = Column(String(255), unique=True, index=True, comment="Refresh Token")
    ip_address = Column(String(50), comment="IP地址")
    user_agent = Column(Text, comment="User Agent")
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="过期时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 关系
    user = relationship("User", back_populates="sessions")


class User2FA(Base):
    """
    用户双因素认证模型
    """
    __tablename__ = "user_2fa"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, comment="用户ID")
    secret = Column(String(255), nullable=False, comment="密钥")
    backup_codes = Column(Text, comment="备份码")
    enabled = Column(Boolean, default=False, comment="是否启用")
    verified = Column(Boolean, default=False, comment="是否验证")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class UserPasswordHistory(Base):
    """
    用户密码历史模型
    """
    __tablename__ = "user_password_history"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    
    # 关系
    user = relationship("User", back_populates="password_history")


class UserLoginLog(Base):
    """
    用户登录日志模型
    """
    __tablename__ = "user_login_logs"
    
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    ip_address = Column(String(50), comment="IP地址")
    user_agent = Column(Text, comment="User Agent")
    login_time = Column(DateTime(timezone=True), server_default=func.now(), comment="登录时间")
    logout_time = Column(DateTime(timezone=True), comment="登出时间")
    status = Column(String(20), comment="状态")
    failure_reason = Column(Text, comment="失败原因")
    
    # 关系
    user = relationship("User", back_populates="login_logs")
