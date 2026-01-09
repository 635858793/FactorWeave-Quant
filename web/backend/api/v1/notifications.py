"""
通知API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.schemas.notification import (
    NotificationCreate, NotificationResponse, NotificationListResponse,
    NotificationPreferenceCreate, NotificationPreferenceResponse,
    NotificationStatsResponse
)
from web.backend.services.notification_service import NotificationService
from web.backend.security.jwt import verify_token
from fastapi.security import OAuth2PasswordBearer


router = APIRouter(prefix="/notifications", tags=["通知"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """
    获取当前用户ID
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    return payload.get("user_id")


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_read: Optional[bool] = Query(None, description="是否已读"),
    notification_type: Optional[str] = Query(None, description="通知类型"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取通知列表
    """
    notification_service = NotificationService(db)
    
    notifications, total, unread_count = notification_service.get_notifications(
        user_id=user_id,
        page=page,
        page_size=page_size,
        is_read=is_read,
        notification_type=notification_type
    )
    
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count
    )


@router.get("/stats", response_model=NotificationStatsResponse)
async def get_notification_stats(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取通知统计
    """
    notification_service = NotificationService(db)
    stats = notification_service.get_notification_stats(user_id)
    
    return NotificationStatsResponse(
        total=stats["total"],
        unread=stats["unread"],
        read=stats["read"],
        by_type=stats["by_type"],
        recent_notifications=stats["recent_notifications"]
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取通知详情
    """
    notification_service = NotificationService(db)
    notification = notification_service.get_notification_by_id(notification_id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    if notification.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该通知"
        )
    
    return NotificationResponse.from_orm(notification)


@router.post("", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    创建通知
    """
    notification_service = NotificationService(db)
    
    # 确保用户只能为自己创建通知
    notification_data.user_id = user_id
    
    notification = notification_service.send_notification(notification_data)
    
    return NotificationResponse.from_orm(notification)


@router.put("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    标记通知为已读
    """
    notification_service = NotificationService(db)
    
    success = notification_service.mark_as_read(notification_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    return {"message": "通知已标记为已读"}


@router.put("/read-all")
async def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    标记所有通知为已读
    """
    notification_service = NotificationService(db)
    
    count = notification_service.mark_all_as_read(user_id)
    
    return {
        "message": f"已标记 {count} 条通知为已读",
        "count": count
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    删除通知
    """
    notification_service = NotificationService(db)
    
    success = notification_service.delete_notification(notification_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    return {"message": "通知已删除"}


@router.delete("/all")
async def delete_all_notifications(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    删除所有通知
    """
    notification_service = NotificationService(db)
    
    count = notification_service.delete_all_notifications(user_id)
    
    return {
        "message": f"已删除 {count} 条通知",
        "count": count
    }


@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_notification_preferences(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取通知偏好设置
    """
    notification_service = NotificationService(db)
    preference = notification_service.get_user_preferences(user_id)
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知偏好设置不存在"
        )
    
    return NotificationPreferenceResponse.from_orm(preference)


@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def update_notification_preferences(
    preferences: NotificationPreferenceCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    更新通知偏好设置
    """
    notification_service = NotificationService(db)
    
    updated_preference = notification_service.update_user_preferences(user_id, preferences)
    
    return NotificationPreferenceResponse.from_orm(updated_preference)
