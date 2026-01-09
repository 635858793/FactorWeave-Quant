"""
用户服务
"""

from sqlalchemy.orm import Session
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.models.user import User, UserSession
from web.backend.schemas.user import UserCreate, UserUpdate
from web.backend.services.auth_service import AuthService


class UserService:
    """
    用户服务类
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
    
    def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        username: str = None,
        email: str = None,
        is_active: bool = None
    ) -> Tuple[List[User], int]:
        """
        获取用户列表
        """
        return self.auth_service.get_users(skip, limit, username, email, is_active)
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        根据ID获取用户
        """
        return self.auth_service.get_user_by_id(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户
        """
        return self.auth_service.get_user_by_username(username)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        根据邮箱获取用户
        """
        return self.auth_service.get_user_by_email(email)
    
    def create_user(self, user_data: UserCreate) -> User:
        """
        创建用户
        """
        return self.auth_service.create_user(user_data)
    
    def update_user(self, user_id: int, user_data: Dict[str, Any]) -> Optional[User]:
        """
        更新用户信息
        """
        return self.auth_service.update_user(user_id, user_data)
    
    def delete_user(self, user_id: int) -> bool:
        """
        删除用户
        """
        return self.auth_service.delete_user(user_id)
    
    def activate_user(self, user_id: int) -> bool:
        """
        激活用户
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.is_active = True
            user.updated_at = datetime.now()
            self.db.commit()
            return True
        return False
    
    def deactivate_user(self, user_id: int) -> bool:
        """
        停用用户
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.is_active = False
            user.updated_at = datetime.now()
            self.db.commit()
            return True
        return False
    
    def get_user_sessions(self, user_id: int) -> List[UserSession]:
        """
        获取用户会话
        """
        return self.auth_service.get_active_sessions(user_id)
    
    def revoke_user_session(self, user_id: int, token: str) -> bool:
        """
        撤销用户会话
        """
        self.auth_service.revoke_session(token)
        return True
    
    def revoke_all_user_sessions(self, user_id: int) -> bool:
        """
        撤销用户所有会话
        """
        self.auth_service.revoke_all_sessions(user_id)
        return True
    
    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户统计信息
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return {}
        
        sessions = self.get_user_sessions(user_id)
        roles = self.auth_service.get_user_roles(user_id)
        permissions = self.auth_service.get_user_permissions(user_id)
        
        return {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "two_fa_enabled": user.two_fa_enabled,
            "last_login_at": user.last_login_at,
            "last_login_ip": user.last_login_ip,
            "created_at": user.created_at,
            "active_sessions": len(sessions),
            "roles": [role.name for role in roles],
            "permissions": [perm.name for perm in permissions],
            "total_roles": len(roles),
            "total_permissions": len(permissions)
        }
    
    def get_user_activity(
        self,
        user_id: int,
        start_time: datetime = None,
        end_time: datetime = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取用户活动
        """
        logs, total = self.auth_service.get_login_logs(user_id, (page - 1) * page_size, page_size)
        
        return logs, total
    
    def search_users(
        self,
        keyword: str,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[User], int]:
        """
        搜索用户
        """
        query = self.db.query(User).filter(
            (User.username.contains(keyword)) |
            (User.email.contains(keyword)) |
            (User.full_name.contains(keyword))
        )
        
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        return users, total
    
    def get_admin_users(self, skip: int = 0, limit: int = 100) -> Tuple[List[User], int]:
        """
        获取管理员用户
        """
        query = self.db.query(User).filter(User.is_admin == True)
        
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        return users, total
    
    def get_active_users(self, skip: int = 0, limit: int = 100) -> Tuple[List[User], int]:
        """
        获取活跃用户
        """
        query = self.db.query(User).filter(User.is_active == True)
        
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        return users, total
    
    def get_users_with_2fa(self, skip: int = 0, limit: int = 100) -> Tuple[List[User], int]:
        """
        获取启用2FA的用户
        """
        query = self.db.query(User).filter(User.two_fa_enabled == True)
        
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        return users, total
    
    def get_locked_users(self, skip: int = 0, limit: int = 100) -> Tuple[List[User], int]:
        """
        获取被锁定的用户
        """
        query = self.db.query(User).filter(
            User.locked_until != None,
            User.locked_until > datetime.now()
        )
        
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        return users, total
    
    def unlock_user(self, user_id: int) -> bool:
        """
        解锁用户
        """
        user = self.get_user_by_id(user_id)
        if user:
            user.failed_login_attempts = 0
            user.locked_until = None
            user.updated_at = datetime.now()
            self.db.commit()
            return True
        return False
    
    def reset_user_password(self, user_id: int, new_password: str) -> bool:
        """
        重置用户密码
        """
        user = self.get_user_by_id(user_id)
        if user:
            self.auth_service.change_password(user_id, new_password)
            return True
        return False
    
    def get_user_dashboard_data(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户仪表盘数据
        """
        from web.backend.services.order_service import OrderService
        from web.backend.services.account_service import AccountService
        
        order_service = OrderService(self.db)
        account_service = AccountService(self.db)
        
        stats = self.get_user_statistics(user_id)
        
        orders, _ = order_service.get_orders(page=1, page_size=10)
        accounts, _ = account_service.get_accounts(page=1, page_size=10)
        
        return {
            **stats,
            "recent_orders": orders[:5],
            "recent_accounts": accounts[:5]
        }
