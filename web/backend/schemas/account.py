"""
账户Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AccountCreate(BaseModel):
    """
    创建账户请求
    """
    account_name: str = Field(..., min_length=1, max_length=100, description="账户名称")
    account_type: str = Field(..., description="账户类型")
    institution: str = Field(..., description="机构")
    account_code: str = Field(..., description="账户代码")


class AccountUpdate(BaseModel):
    """
    修改账户请求
    """
    account_name: Optional[str] = Field(None, min_length=1, max_length=100, description="账户名称")
    account_type: Optional[str] = Field(None, description="账户类型")
    institution: Optional[str] = Field(None, description="机构")
    account_code: Optional[str] = Field(None, description="账户代码")
    is_active: Optional[bool] = Field(None, description="是否激活")


class AccountResponse(BaseModel):
    """
    账户响应
    """
    id: int
    account_name: str
    account_type: str
    institution: str
    account_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AccountDetailResponse(AccountResponse):
    """
    账户详情响应
    """
    total_balance: Optional[float]
    available_balance: Optional[float]
    frozen_balance: Optional[float]
    market_value: Optional[float]
    total_asset: Optional[float]
    profit_loss: Optional[float]
    profit_loss_ratio: Optional[float]


class AccountFilter(BaseModel):
    """
    账户过滤参数
    """
    institution: Optional[str] = None
    account_type: Optional[str] = None
    status: Optional[str] = None


class AccountListResponse(BaseModel):
    """
    账户列表响应
    """
    accounts: List[AccountResponse]
    total: int
    page: int
    page_size: int


class PositionResponse(BaseModel):
    """
    持仓响应
    """
    id: int
    account_id: int
    asset_type: str
    symbol: str
    side: str
    quantity: float
    available_quantity: float
    avg_price: float
    current_price: float
    market_value: float
    profit_loss: float
    profit_loss_ratio: float
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    """
    余额响应
    """
    id: int
    account_id: int
    total_balance: float
    available_balance: float
    frozen_balance: float
    market_value: float
    total_asset: float
    profit_loss: float
    profit_loss_ratio: float
    updated_at: datetime
    
    class Config:
        from_attributes = True
