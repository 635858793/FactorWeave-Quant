"""
账户API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.schemas.account import (
    AccountCreate, AccountUpdate, AccountResponse, AccountListResponse,
    AccountFilter, AccountDetailResponse, PositionResponse, BalanceResponse
)
from web.backend.services.account_service import AccountService
from web.backend.security.jwt import verify_token
from fastapi.security import OAuth2PasswordBearer


router = APIRouter(prefix="/accounts", tags=["账户"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.get("", response_model=AccountListResponse)
async def get_accounts(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    institution: Optional[str] = Query(None, description="机构"),
    account_type: Optional[str] = Query(None, description="账户类型"),
    status: Optional[str] = Query(None, description="账户状态"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取账户列表
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    
    filter_params = AccountFilter(
        institution=institution,
        account_type=account_type,
        status=status
    )
    
    accounts, total = account_service.get_accounts(
        page=page,
        page_size=page_size,
        filter_params=filter_params
    )
    
    return AccountListResponse(
        accounts=accounts,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{account_id}", response_model=AccountDetailResponse)
async def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取账户详情
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    account = account_service.get_account_by_id(account_id)
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账户不存在"
        )
    
    return AccountDetailResponse.from_orm(account)


@router.post("", response_model=AccountResponse)
async def create_account(
    account: AccountCreate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    创建账户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    
    created_account = account_service.create_account(account)
    
    return AccountResponse.from_orm(created_account)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    account: AccountUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    修改账户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    
    updated_account = account_service.update_account(account_id, account)
    
    if not updated_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账户不存在"
        )
    
    return AccountResponse.from_orm(updated_account)


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    删除账户
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    
    success = account_service.delete_account(account_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账户不存在"
        )
    
    return {"message": "账户已删除"}


@router.post("/{account_id}/test")
async def test_account_connection(
    account_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    测试账户连接
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    
    success, message = account_service.test_connection(account_id)
    
    return {
        "success": success,
        "message": message
    }


@router.get("/{account_id}/positions", response_model=List[PositionResponse])
async def get_account_positions(
    account_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取账户持仓信息
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    positions = account_service.get_positions(account_id)
    
    return [PositionResponse.from_orm(position) for position in positions]


@router.get("/{account_id}/balance", response_model=BalanceResponse)
async def get_account_balance(
    account_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取账户余额信息
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    account_service = AccountService(db)
    balance = account_service.get_balance(account_id)
    
    return BalanceResponse.from_orm(balance)
