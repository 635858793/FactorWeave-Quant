"""
订单数据模型

定义订单相关的数据结构
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from core.plugin_types import AssetType


class OrderType(Enum):
    """订单类型"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderCategory(Enum):
    """订单类别"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Order:
    """订单模型"""
    order_id: str
    strategy_id: str
    asset_type: AssetType
    stock_code: str
    order_type: OrderType
    order_category: OrderCategory
    order_price: float
    order_quantity: int
    order_status: OrderStatus
    create_time: datetime
    update_time: datetime
    execute_time: Optional[datetime] = None
    filled_quantity: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    error_message: Optional[str] = None
    stop_price: Optional[float] = None
    user_id: str = "system"
    account_id: str = "default"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    contract_multiplier: int = 1
    margin_ratio: float = 0.0
    strike_price: Optional[float] = None
    expiry_date: Optional[datetime] = None
    option_type: Optional[str] = None

    @property
    def remaining_quantity(self) -> int:
        """剩余数量"""
        return self.order_quantity - self.filled_quantity

    @property
    def fill_ratio(self) -> float:
        """成交比例"""
        if self.order_quantity == 0:
            return 0.0
        return self.filled_quantity / self.order_quantity

    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.order_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, 
                                   OrderStatus.REJECTED, OrderStatus.EXPIRED]

    @property
    def is_active(self) -> bool:
        """是否活跃"""
        return self.order_status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, 
                                   OrderStatus.PARTIALLY_FILLED]

    @property
    def total_value(self) -> float:
        """订单总价值"""
        return self.order_price * self.order_quantity

    @property
    def filled_value(self) -> float:
        """已成交价值"""
        return self.filled_price * self.filled_quantity

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'order_id': self.order_id,
            'strategy_id': self.strategy_id,
            'asset_type': self.asset_type.value,
            'stock_code': self.stock_code,
            'order_type': self.order_type.value,
            'order_category': self.order_category.value,
            'order_price': self.order_price,
            'order_quantity': self.order_quantity,
            'order_status': self.order_status.value,
            'create_time': self.create_time.isoformat(),
            'update_time': self.update_time.isoformat(),
            'execute_time': self.execute_time.isoformat() if self.execute_time else None,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'commission': self.commission,
            'error_message': self.error_message,
            'stop_price': self.stop_price,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'tags': self.tags,
            'metadata': self.metadata,
            'contract_multiplier': self.contract_multiplier,
            'margin_ratio': self.margin_ratio,
            'strike_price': self.strike_price,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'option_type': self.option_type
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """从字典创建"""
        return cls(
            order_id=data['order_id'],
            strategy_id=data['strategy_id'],
            asset_type=AssetType(data.get('asset_type', 'stock_a')),
            stock_code=data['stock_code'],
            order_type=OrderType(data['order_type']),
            order_category=OrderCategory(data['order_category']),
            order_price=data['order_price'],
            order_quantity=data['order_quantity'],
            order_status=OrderStatus(data['order_status']),
            create_time=datetime.fromisoformat(data['create_time']),
            update_time=datetime.fromisoformat(data['update_time']),
            execute_time=datetime.fromisoformat(data['execute_time']) if data.get('execute_time') else None,
            filled_quantity=data.get('filled_quantity', 0),
            filled_price=data.get('filled_price', 0.0),
            commission=data.get('commission', 0.0),
            error_message=data.get('error_message'),
            stop_price=data.get('stop_price'),
            user_id=data.get('user_id', 'system'),
            account_id=data.get('account_id', 'default'),
            tags=data.get('tags', []),
            metadata=data.get('metadata', {}),
            contract_multiplier=data.get('contract_multiplier', 1),
            margin_ratio=data.get('margin_ratio', 0.0),
            strike_price=data.get('strike_price'),
            expiry_date=datetime.fromisoformat(data['expiry_date']) if data.get('expiry_date') else None,
            option_type=data.get('option_type')
        )


@dataclass
class OrderRequest:
    """订单请求"""
    strategy_id: str
    asset_type: AssetType
    stock_code: str
    order_type: OrderType
    order_category: OrderCategory
    order_price: float
    order_quantity: int
    stop_price: Optional[float] = None
    user_id: str = "system"
    account_id: str = "default"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    contract_multiplier: int = 1
    margin_ratio: float = 0.0
    strike_price: Optional[float] = None
    expiry_date: Optional[datetime] = None
    option_type: Optional[str] = None

    def validate(self) -> bool:
        """验证订单请求"""
        if self.order_quantity <= 0:
            return False
        if self.order_price <= 0:
            return False
        if self.order_category == OrderCategory.STOP and self.stop_price is None:
            return False
        if self.order_category == OrderCategory.STOP_LIMIT and self.stop_price is None:
            return False
        return True


@dataclass
class OrderFill:
    """订单成交记录"""
    fill_id: str
    order_id: str
    stock_code: str
    fill_price: float
    fill_quantity: int
    fill_time: datetime
    commission: float = 0.0

    @property
    def fill_value(self) -> float:
        """成交价值"""
        return self.fill_price * self.fill_quantity

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'fill_id': self.fill_id,
            'order_id': self.order_id,
            'stock_code': self.stock_code,
            'fill_price': self.fill_price,
            'fill_quantity': self.fill_quantity,
            'fill_time': self.fill_time.isoformat(),
            'commission': self.commission
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderFill':
        """从字典创建"""
        return cls(
            fill_id=data['fill_id'],
            order_id=data['order_id'],
            stock_code=data['stock_code'],
            fill_price=data['fill_price'],
            fill_quantity=data['fill_quantity'],
            fill_time=datetime.fromisoformat(data['fill_time']),
            commission=data.get('commission', 0.0)
        )


@dataclass
class OrderQuery:
    """订单查询条件"""
    strategy_id: Optional[str] = None
    asset_type: Optional[AssetType] = None
    stock_code: Optional[str] = None
    order_type: Optional[OrderType] = None
    order_status: Optional[OrderStatus] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    user_id: Optional[str] = None
    account_id: Optional[str] = None
    limit: int = 100
    offset: int = 0
    sort_by: str = "create_time"
    sort_order: str = "desc"
