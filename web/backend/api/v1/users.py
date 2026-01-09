"""
用户API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListResponse,
    UserFilter, UserDetailResponse, RoleResponse, PermissionResponse
)
from web.backend.services.user_service import UserService
from web.backend.security.jwt import verify_token
from fastapi.security import OAuth2PasswordBearer


router = APIRouter(prefix="/users", tags=["用户"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.get("", response_model=UserListResponse)
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    username: Optional[str] = Query(None, description="用户名"),
    email: Optional[str] = Query(None, description="邮箱"),
    role_id: Optional[int] = Query(None, description="角色ID"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取用户列表
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    filter_params = UserFilter(
        username=username,
        email=email,
        role_id=role_id,
        is_active=is_active
    )
    
    users, total = user_service.get_users(
        page=page,
        page_size=page_size,
        filter_params=filter_params
    )
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取用户详情
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return UserDetailResponse.from_orm(user)


@router.post("", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    创建用户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    created_user = user_service.create_user(user)
    
    return UserResponse.from_orm(created_user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    修改用户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    updated_user = user_service.update_user(user_id, user)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return UserResponse.from_orm(updated_user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    删除用户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    success = user_service.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return {"message": "用户已删除"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    激活用户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    success = user_service.activate_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return {"message": "用户已激活"}


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    禁用用户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    success = user_service.deactivate_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return {"message": "用户已禁用"}


@router.get("/{user_id}/roles", response_model=List[RoleResponse])
async def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取用户角色
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    roles = user_service.get_user_roles(user_id)
    
    return [RoleResponse.from_orm(role) for role in roles]


@router.post("/{user_id}/roles/{role_id}")
async def assign_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    分配角色
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    success = user_service.assign_role(user_id, role_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户或角色不存在"
        )
    
    return {"message": "角色分配成功"}


@router.delete("/{user_id}/roles/{role_id}")
async def revoke_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    撤销角色
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    
    success = user_service.revoke_role(user_id, role_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户或角色不存在"
        )
    
    return {"message": "角色撤销成功"}


@router.get("/{user_id}/permissions", response_model=List[PermissionResponse])
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取用户权限
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    permissions = user_service.get_user_permissions(user_id)
    
    return [PermissionResponse.from_orm(permission) for permission in permissions]


@router.get("/roles", response_model=List[RoleResponse])
async def get_roles(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取所有角色
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    roles = user_service.get_all_roles()
    
    return [RoleResponse.from_orm(role) for role in roles]


@router.get("/roles/{role_id}/permissions", response_model=List[PermissionResponse])
async def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取角色权限
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    user_service = UserService(db)
    permissions = user_service.get_role_permissions(role_id)
    
    return [PermissionResponse.from_orm(permission) for permission in permissions]
