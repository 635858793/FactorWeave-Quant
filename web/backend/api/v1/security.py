"""
安全API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.schemas.security import (
    SecurityConfigResponse, SecurityConfigUpdate,
    IPWhitelistCreate, IPWhitelistResponse, IPWhitelistListResponse,
    IPBlacklistCreate, IPBlacklistResponse, IPBlacklistListResponse,
    AuditLogResponse, AuditLogListResponse
)
from web.backend.services.security_service import SecurityService
from web.backend.services.audit_service import AuditService
from web.backend.security.jwt import verify_token
from fastapi.security import OAuth2PasswordBearer


router = APIRouter(prefix="/security", tags=["安全"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.get("/config", response_model=SecurityConfigResponse)
async def get_security_config(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取安全配置
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    config = security_service.get_security_config()
    
    return SecurityConfigResponse.from_orm(config)


@router.put("/config", response_model=SecurityConfigResponse)
async def update_security_config(
    config: SecurityConfigUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    更新安全配置
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    updated_config = security_service.update_security_config(config)
    
    return SecurityConfigResponse.from_orm(updated_config)


@router.get("/ip-whitelist", response_model=IPWhitelistListResponse)
async def get_ip_whitelist(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    ip_address: Optional[str] = Query(None, description="IP地址"),
    description: Optional[str] = Query(None, description="描述"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取IP白名单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    whitelist, total = security_service.get_ip_whitelist(
        page=page,
        page_size=page_size,
        ip_address=ip_address,
        description=description,
        is_active=is_active
    )
    
    return IPWhitelistListResponse(
        whitelist=whitelist,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/ip-whitelist", response_model=IPWhitelistResponse)
async def add_ip_whitelist(
    ip_whitelist: IPWhitelistCreate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    添加IP白名单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    created_whitelist = security_service.add_ip_whitelist(ip_whitelist)
    
    return IPWhitelistResponse.from_orm(created_whitelist)


@router.delete("/ip-whitelist/{whitelist_id}")
async def remove_ip_whitelist(
    whitelist_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    移除IP白名单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    success = security_service.remove_ip_whitelist(whitelist_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP白名单不存在"
        )
    
    return {"message": "IP白名单已移除"}


@router.get("/ip-blacklist", response_model=IPBlacklistListResponse)
async def get_ip_blacklist(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    ip_address: Optional[str] = Query(None, description="IP地址"),
    description: Optional[str] = Query(None, description="描述"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取IP黑名单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    blacklist, total = security_service.get_ip_blacklist(
        page=page,
        page_size=page_size,
        ip_address=ip_address,
        description=description,
        is_active=is_active
    )
    
    return IPBlacklistListResponse(
        blacklist=blacklist,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/ip-blacklist", response_model=IPBlacklistResponse)
async def add_ip_blacklist(
    ip_blacklist: IPBlacklistCreate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    添加IP黑名单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    created_blacklist = security_service.add_ip_blacklist(ip_blacklist)
    
    return IPBlacklistResponse.from_orm(created_blacklist)


@router.delete("/ip-blacklist/{blacklist_id}")
async def remove_ip_blacklist(
    blacklist_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    移除IP黑名单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    success = security_service.remove_ip_blacklist(blacklist_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP黑名单不存在"
        )
    
    return {"message": "IP黑名单已移除"}


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    action: Optional[str] = Query(None, description="操作类型"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取审计日志
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    logs, total = security_service.get_audit_logs(
        page=page,
        page_size=page_size,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time
    )
    
    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/audit-logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取审计日志详情
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    log = security_service.get_audit_log_by_id(log_id)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审计日志不存在"
        )
    
    return AuditLogResponse.from_orm(log)


@router.post("/audit-logs/export")
async def export_audit_logs(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    format: str = "csv",
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    导出审计日志
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    export_path = security_service.export_audit_logs(
        start_time=start_time,
        end_time=end_time,
        format=format
    )
    
    if not export_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="审计日志导出失败"
        )
    
    return {
        "message": "审计日志导出成功",
        "export_path": export_path
    }


@router.post("/scan")
async def security_scan(
    scan_type: str = "full",
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    安全扫描
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    
    scan_result = security_service.security_scan(scan_type)
    
    return scan_result


@router.get("/summary")
async def get_security_summary(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取安全摘要
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    security_service = SecurityService(db)
    summary = security_service.get_security_summary()
    
    return summary


@router.get("/audit/summary")
async def get_audit_summary(
    days: int = Query(30, ge=1, le=365, description="天数"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取审计摘要
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    audit_service = AuditService(db)
    summary = audit_service.get_audit_summary(days)
    
    return summary


@router.get("/audit/user-activity/{user_id}")
async def get_user_activity(
    user_id: int,
    days: int = Query(30, ge=1, le=365, description="天数"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取用户活动统计
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    audit_service = AuditService(db)
    activity = audit_service.get_user_activity(user_id, days)
    
    return activity


@router.get("/audit/resource-activity/{resource_type}")
async def get_resource_activity(
    resource_type: str,
    days: int = Query(30, ge=1, le=365, description="天数"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取资源活动统计
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    audit_service = AuditService(db)
    activity = audit_service.get_resource_activity(resource_type, days)
    
    return activity


@router.get("/audit/security-events")
async def get_security_events(
    days: int = Query(7, ge=1, le=30, description="天数"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取安全事件
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    audit_service = AuditService(db)
    events = audit_service.get_security_events(days)
    
    return events


@router.get("/audit/trend")
async def get_audit_trend(
    days: int = Query(30, ge=1, le=365, description="天数"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取趋势数据
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    audit_service = AuditService(db)
    trend = audit_service.get_trend_data(days)
    
    return trend


@router.delete("/audit/delete-old")
async def delete_old_audit_logs(
    days: int = Query(90, ge=1, le=365, description="保留天数"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    删除旧审计日志
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    audit_service = AuditService(db)
    deleted = audit_service.delete_old_logs(days)
    
    return {
        "message": f"已删除 {deleted} 条旧审计日志",
        "deleted_count": deleted
    }
