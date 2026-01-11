"""
系统API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.services.system_service import SystemService
from web.backend.security.jwt import verify_token
from fastapi.security import OAuth2PasswordBearer


router = APIRouter(prefix="/system", tags=["系统"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.get("/info")
async def get_system_info(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取系统信息
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    info = system_service.get_system_info()
    
    return info


@router.get("/health")
async def get_system_health(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取系统健康状态
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    health = system_service.get_system_health()
    
    return health


@router.get("/metrics")
async def get_system_metrics(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取系统指标
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    metrics = system_service.get_system_metrics()
    
    return metrics


@router.get("/config")
async def get_system_config(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取系统配置
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    config = system_service.get_system_config()
    
    return config


@router.put("/config")
async def update_system_config(
    config: Dict[str, Any],
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    更新系统配置
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    updated_config = system_service.update_system_config(config)
    
    return {
        "message": "系统配置更新成功",
        "config": updated_config
    }


@router.post("/restart")
async def restart_system(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    重启系统
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    success = system_service.restart_system()
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统重启失败"
        )
    
    return {"message": "系统重启成功"}


@router.post("/backup")
async def backup_system(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    备份系统
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    backup_path = system_service.backup_system()
    
    if not backup_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统备份失败"
        )
    
    return {
        "message": "系统备份成功",
        "backup_path": backup_path
    }


@router.post("/restore")
async def restore_system(
    backup_path: str,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    恢复系统
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    success = system_service.restore_system(backup_path)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统恢复失败"
        )
    
    return {"message": "系统恢复成功"}


@router.get("/logs")
async def get_system_logs(
    page: int = 1,
    page_size: int = 20,
    level: str = None,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取系统日志
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    logs = system_service.get_system_logs(page, page_size, level)
    
    return logs


@router.delete("/logs")
async def clear_system_logs(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    清除系统日志
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    system_service = SystemService(db)
    success = system_service.clear_system_logs()
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="清除系统日志失败"
        )
    
    return {"message": "系统日志清除成功"}
