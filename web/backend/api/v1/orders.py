"""
订单API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse, OrderListResponse,
    OrderFilter, OrderDetailResponse, FillResponse
)
from web.backend.services.order_service import OrderService
from web.backend.security.jwt import verify_token
from fastapi.security import OAuth2PasswordBearer


router = APIRouter(prefix="/orders", tags=["订单"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.get("", response_model=OrderListResponse)
async def get_orders(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    asset_type: Optional[str] = Query(None, description="资产类型"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    status: Optional[str] = Query(None, description="订单状态"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取订单列表
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    
    filter_params = OrderFilter(
        asset_type=asset_type,
        account_id=account_id,
        status=status,
        start_time=start_time,
        end_time=end_time
    )
    
    orders, total = order_service.get_orders(
        page=page,
        page_size=page_size,
        filter_params=filter_params
    )
    
    return OrderListResponse(
        orders=orders,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取订单详情
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    order = order_service.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    
    return OrderDetailResponse.from_orm(order)


@router.post("", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    创建订单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    
    created_order = order_service.create_order(order)
    
    return OrderResponse.from_orm(created_order)


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    order: OrderUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    修改订单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    
    updated_order = order_service.update_order(order_id, order)
    
    if not updated_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    
    return OrderResponse.from_orm(updated_order)


@router.delete("/{order_id}")
async def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    取消订单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    
    success = order_service.cancel_order(order_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    
    return {"message": "订单已取消"}


@router.post("/batch/cancel")
async def batch_cancel_orders(
    order_ids: List[str],
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    批量取消订单
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    
    success_count, failed_count = order_service.batch_cancel_orders(order_ids)
    
    return {
        "message": f"成功取消{success_count}个订单，失败{failed_count}个",
        "success_count": success_count,
        "failed_count": failed_count
    }


@router.get("/{order_id}/fills", response_model=List[FillResponse])
async def get_order_fills(
    order_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取订单成交记录
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    fills = order_service.get_order_fills(order_id)
    
    return [FillResponse.from_orm(fill) for fill in fills]


@router.get("/{order_id}/analysis")
async def get_order_analysis(
    order_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取订单分析报告
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    order_service = OrderService(db)
    analysis = order_service.get_order_analysis(order_id)
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单分析不存在"
        )
    
    return analysis
