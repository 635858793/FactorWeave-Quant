"""
订单Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    """
    订单状态枚举
    """
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderSide(str, Enum):
    """
    订单方向枚举
    """
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """
    订单类型枚举
    """
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderCreate(BaseModel):
    """
    创建订单请求
    """
    account_id: int = Field(..., description="账户ID")
    asset_type: str = Field(..., description="资产类型")
    symbol: str = Field(..., description="代码")
    side: OrderSide = Field(..., description="方向")
    order_type: OrderType = Field(..., description="订单类型")
    quantity: float = Field(..., gt=0, description="数量")
    price: Optional[float] = Field(None, gt=0, description="价格")
    stop_price: Optional[float] = Field(None, gt=0, description="止损价格")
    time_in_force: Optional[str] = Field("GTC", description="有效期")
    remark: Optional[str] = Field(None, description="备注")


class OrderUpdate(BaseModel):
    """
    修改订单请求
    """
    quantity: Optional[float] = Field(None, gt=0, description="数量")
    price: Optional[float] = Field(None, gt=0, description="价格")
    stop_price: Optional[float] = Field(None, gt=0, description="止损价格")
    remark: Optional[str] = Field(None, description="备注")


class OrderResponse(BaseModel):
    """
    订单响应
    """
    order_id: str
    account_id: int
    asset_type: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    stop_price: Optional[float]
    filled_quantity: float
    avg_fill_price: Optional[float]
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OrderDetailResponse(OrderResponse):
    """
    订单详情响应
    """
    account_name: Optional[str]
    institution: Optional[str]
    time_in_force: Optional[str]
    remark: Optional[str]
    commission: Optional[float]
    profit_loss: Optional[float]
    profit_loss_ratio: Optional[float]


class OrderFilter(BaseModel):
    """
    订单过滤参数
    """
    asset_type: Optional[str] = None
    account_id: Optional[int] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class OrderListResponse(BaseModel):
    """
    订单列表响应
    """
    orders: List[OrderResponse]
    total: int
    page: int
    page_size: int


class FillResponse(BaseModel):
    """
    成交记录响应
    """
    id: int
    fill_id: str
    order_id: str
    account_id: int
    asset_type: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    commission: Optional[float]
    fill_time: datetime
    
    class Config:
        from_attributes = True
