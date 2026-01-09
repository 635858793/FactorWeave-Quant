"""
认证API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.schemas.user import UserLogin, UserRegister, TokenResponse, UserResponse
from web.backend.services.auth_service import AuthService
from web.backend.security.jwt import create_access_token, create_refresh_token, verify_token
from web.backend.security.2fa import verify_2fa_code, generate_2fa_code
from web.backend.security.password import verify_password, hash_password
from web.backend.config.settings import settings


router = APIRouter(prefix="/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.post("/login", response_model=TokenResponse)
async def login(
    user_login: UserLogin,
    db: Session = Depends(get_db)
):
    """
    用户登录
    """
    auth_service = AuthService(db)
    
    user = auth_service.authenticate_user(user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    if settings.TWO_FA_ENABLED and user.two_fa_enabled:
        if not user_login.two_fa_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="需要双因素认证码"
            )
        
        if not verify_2fa_code(user.id, user_login.two_fa_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="双因素认证码错误"
            )
    
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    auth_service.record_login(user.id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/register", response_model=UserResponse)
async def register(
    user_register: UserRegister,
    db: Session = Depends(get_db)
):
    """
    用户注册
    """
    auth_service = AuthService(db)
    
    if auth_service.get_user_by_username(user_register.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    if auth_service.get_user_by_email(user_register.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    if not verify_password_complexity(user_register.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码复杂度不符合要求"
        )
    
    user = auth_service.create_user(user_register)
    
    return UserResponse.from_orm(user)


@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    用户登出
    """
    auth_service = AuthService(db)
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    username = payload.get("sub")
    auth_service.logout_user(username)
    
    return {"message": "登出成功"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    刷新Token
    """
    auth_service = AuthService(db)
    
    payload = verify_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token无效"
        )
    
    username = payload.get("sub")
    user = auth_service.get_user_by_username(username)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用"
        )
    
    access_token = create_access_token(data={"sub": user.username})
    new_refresh_token = create_refresh_token(data={"sub": user.username})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/reset-password")
async def reset_password(
    email: str,
    db: Session = Depends(get_db)
):
    """
    重置密码
    """
    auth_service = AuthService(db)
    
    user = auth_service.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邮箱未注册"
        )
    
    reset_token = auth_service.generate_password_reset_token(user.id)
    
    return {"message": "密码重置邮件已发送", "token": reset_token}


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    修改密码
    """
    auth_service = AuthService(db)
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    username = payload.get("sub")
    user = auth_service.get_user_by_username(username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    if not verify_password_complexity(new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码复杂度不符合要求"
        )
    
    if auth_service.check_password_in_history(user.id, new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与最近使用的密码相同"
        )
    
    auth_service.change_password(user.id, new_password)
    
    return {"message": "密码修改成功"}


@router.post("/2fa/enable")
async def enable_2fa(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    启用双因素认证
    """
    auth_service = AuthService(db)
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    username = payload.get("sub")
    user = auth_service.get_user_by_username(username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    secret = generate_2fa_secret(user.id)
    
    return {"message": "双因素认证已启用", "secret": secret}


@router.post("/2fa/disable")
async def disable_2fa(
    two_fa_code: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    禁用双因素认证
    """
    auth_service = AuthService(db)
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    username = payload.get("sub")
    user = auth_service.get_user_by_username(username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if not verify_2fa_code(user.id, two_fa_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="双因素认证码错误"
        )
    
    auth_service.disable_2fa(user.id)
    
    return {"message": "双因素认证已禁用"}


def verify_password_complexity(password: str) -> bool:
    """
    验证密码复杂度
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False
    
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in password)
    
    return has_upper and has_lower and has_digit and has_special
