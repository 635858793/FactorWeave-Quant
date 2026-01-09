"""
认证服务
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.models.user import (
    User, UserSession, UserPasswordHistory, UserLoginLog, Role, Permission, UserRole, RolePermission
)
from web.backend.schemas.user import UserCreate, UserRegister
from web.backend.security.password import hash_password, verify_password
from web.backend.security.2fa import generate_2fa_secret, verify_2fa_code
from web.backend.security.jwt import create_access_token, create_refresh_token
from web.backend.config.settings import settings


class AuthService:
    """
    认证服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        验证用户
        """
        user = self.get_user_by_username(username)
        
        if not user:
            return None
        
        if not verify_password(password, user.password_hash):
            self.record_failed_login(user)
            return None
        
        if settings.ACCOUNT_LOCK_ENABLED:
            if user.locked_until and user.locked_until > datetime.now():
                return None
        
        if not user.is_active:
            return None
        
        self.reset_failed_login(user)
        return user
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户
        """
        return self.db.query(User).filter(User.username == username).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        根据邮箱获取用户
        """
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        根据ID获取用户
        """
        return self.db.query(User).filter(User.id == user_id).first()
    
    def create_user(self, user_data: UserCreate) -> User:
        """
        创建用户
        """
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            full_name=user_data.full_name,
            phone=user_data.phone,
            is_admin=user_data.is_admin
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def record_login(self, user_id: int, ip_address: str = None, user_agent: str = None):
        """
        记录登录
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login_at = datetime.now()
            user.last_login_ip = ip_address
            self.db.commit()
        
        login_log = UserLoginLog(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            login_time=datetime.now(),
            status="success"
        )
        
        self.db.add(login_log)
        self.db.commit()
    
    def logout_user(self, username: str):
        """
        用户登出
        """
        user = self.get_user_by_username(username)
        if user:
            now = datetime.now()
            sessions = self.db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.expires_at > now
            ).all()
            
            for session in sessions:
                session.expires_at = now
            
            self.db.commit()
    
    def generate_password_reset_token(self, user_id: int) -> str:
        """
        生成密码重置Token
        """
        import secrets
        
        token = secrets.token_urlsafe(32)
        
        user = self.get_user_by_id(user_id)
        if user:
            user.password_reset_token = token
            user.password_reset_expires = datetime.now() + timedelta(hours=1)
            self.db.commit()
        
        return token
    
    def change_password(self, user_id: int, new_password: str):
        """
        修改密码
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.password_hash = hash_password(new_password)
            self.db.commit()
            
            self.record_password_history(user_id, new_password)
    
    def record_password_history(self, user_id: int, password: str):
        """
        记录密码历史
        """
        history = UserPasswordHistory(
            user_id=user_id,
            password_hash=hash_password(password)
        )
        
        self.db.add(history)
        self.db.commit()
        
        histories = self.db.query(UserPasswordHistory).filter(
            UserPasswordHistory.user_id == user_id
        ).order_by(UserPasswordHistory.created_at.desc()).all()
        
        if len(histories) > settings.PASSWORD_HISTORY_COUNT:
            for old_history in histories[settings.PASSWORD_HISTORY_COUNT:]:
                self.db.delete(old_history)
            
            self.db.commit()
    
    def check_password_in_history(self, user_id: int, password: str) -> bool:
        """
        检查密码是否在历史记录中
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        histories = self.db.query(UserPasswordHistory).filter(
            UserPasswordHistory.user_id == user_id
        ).order_by(UserPasswordHistory.created_at.desc()).limit(settings.PASSWORD_HISTORY_COUNT).all()
        
        for history in histories:
            if verify_password(password, history.password_hash):
                return True
        
        return False
    
    def record_failed_login(self, user: User):
        """
        记录失败登录
        """
        user.failed_login_attempts += 1
        
        if settings.ACCOUNT_LOCK_ENABLED and user.failed_login_attempts >= settings.ACCOUNT_LOCK_MAX_ATTEMPTS:
            user.locked_until = datetime.now() + timedelta(minutes=settings.ACCOUNT_LOCK_DURATION_MINUTES)
        
        self.db.commit()
    
    def reset_failed_login(self, user: User):
        """
        重置失败登录次数
        """
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.commit()
    
    def enable_2fa(self, user_id: int) -> str:
        """
        启用双因素认证
        """
        user = self.get_user_by_id(user_id)
        if user:
            secret = generate_2fa_secret(user_id)
            user.two_fa_enabled = True
            user.two_fa_secret = secret
            self.db.commit()
            
            return secret
        
        return None
    
    def disable_2fa(self, user_id: int):
        """
        禁用双因素认证
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.two_fa_enabled = False
            user.two_fa_secret = None
            self.db.commit()
    
    def create_session(self, user_id: int, token: str, ip_address: str = None, user_agent: str = None) -> UserSession:
        """
        创建会话
        """
        session = UserSession(
            user_id=user_id,
            token=token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now() + timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def validate_session(self, token: str) -> Optional[User]:
        """
        验证会话
        """
        session = self.db.query(UserSession).filter(
            UserSession.token == token,
            UserSession.expires_at > datetime.now()
        ).first()
        
        if session:
            return self.get_user_by_id(session.user_id)
        
        return None
    
    def revoke_session(self, token: str):
        """
        撤销会话
        """
        session = self.db.query(UserSession).filter(UserSession.token == token).first()
        if session:
            session.expires_at = datetime.now()
            self.db.commit()
    
    def revoke_all_sessions(self, user_id: int):
        """
        撤销用户所有会话
        """
        sessions = self.db.query(UserSession).filter(UserSession.user_id == user_id).all()
        for session in sessions:
            session.expires_at = datetime.now()
        
        self.db.commit()
    
    def get_active_sessions(self, user_id: int) -> List[UserSession]:
        """
        获取活跃会话
        """
        return self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.expires_at > datetime.now()
        ).all()
    
    def create_role(self, name: str, description: str = None) -> Role:
        """
        创建角色
        """
        role = Role(
            name=name,
            description=description
        )
        
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        
        return role
    
    def get_role_by_name(self, name: str) -> Optional[Role]:
        """
        根据名称获取角色
        """
        return self.db.query(Role).filter(Role.name == name).first()
    
    def get_all_roles(self) -> List[Role]:
        """
        获取所有角色
        """
        return self.db.query(Role).all()
    
    def assign_role_to_user(self, user_id: int, role_id: int):
        """
        为用户分配角色
        """
        existing = self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        ).first()
        
        if not existing:
            user_role = UserRole(user_id=user_id, role_id=role_id)
            self.db.add(user_role)
            self.db.commit()
    
    def remove_role_from_user(self, user_id: int, role_id: int):
        """
        移除用户角色
        """
        user_role = self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        ).first()
        
        if user_role:
            self.db.delete(user_role)
            self.db.commit()
    
    def get_user_roles(self, user_id: int) -> List[Role]:
        """
        获取用户角色
        """
        return self.db.query(Role).join(UserRole).filter(
            UserRole.user_id == user_id
        ).all()
    
    def create_permission(self, name: str, description: str = None) -> Permission:
        """
        创建权限
        """
        permission = Permission(
            name=name,
            description=description
        )
        
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        
        return permission
    
    def assign_permission_to_role(self, role_id: int, permission_id: int):
        """
        为角色分配权限
        """
        existing = self.db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id
        ).first()
        
        if not existing:
            role_permission = RolePermission(role_id=role_id, permission_id=permission_id)
            self.db.add(role_permission)
            self.db.commit()
    
    def remove_permission_from_role(self, role_id: int, permission_id: int):
        """
        移除角色权限
        """
        role_permission = self.db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id
        ).first()
        
        if role_permission:
            self.db.delete(role_permission)
            self.db.commit()
    
    def get_role_permissions(self, role_id: int) -> List[Permission]:
        """
        获取角色权限
        """
        return self.db.query(Permission).join(RolePermission).filter(
            RolePermission.role_id == role_id
        ).all()
    
    def get_user_permissions(self, user_id: int) -> List[Permission]:
        """
        获取用户权限
        """
        return self.db.query(Permission).join(RolePermission).join(UserRole).filter(
            UserRole.user_id == user_id
        ).distinct().all()
    
    def has_permission(self, user_id: int, permission_name: str) -> bool:
        """
        检查用户是否有权限
        """
        permissions = self.get_user_permissions(user_id)
        return any(p.name == permission_name for p in permissions)
    
    def get_all_permissions(self) -> List[Permission]:
        """
        获取所有权限
        """
        return self.db.query(Permission).all()
    
    def get_users(self, skip: int = 0, limit: int = 100, username: str = None, email: str = None, is_active: bool = None) -> tuple:
        """
        获取用户列表
        """
        query = self.db.query(User)
        
        if username:
            query = query.filter(User.username.contains(username))
        
        if email:
            query = query.filter(User.email.contains(email))
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        return users, total
    
    def update_user(self, user_id: int, user_data: dict) -> Optional[User]:
        """
        更新用户信息
        """
        user = self.get_user_by_id(user_id)
        if user:
            for key, value in user_data.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)
            
            user.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(user)
        
        return user
    
    def delete_user(self, user_id: int) -> bool:
        """
        删除用户
        """
        user = self.get_user_by_id(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()
            return True
        
        return False
    
    def get_login_logs(self, user_id: int = None, skip: int = 0, limit: int = 100) -> tuple:
        """
        获取登录日志
        """
        query = self.db.query(UserLoginLog)
        
        if user_id:
            query = query.filter(UserLoginLog.user_id == user_id)
        
        total = query.count()
        logs = query.order_by(UserLoginLog.login_time.desc()).offset(skip).limit(limit).all()
        
        return logs, total
