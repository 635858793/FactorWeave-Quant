"""
账户模型
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from web.backend.config.database import Base


class Account(Base):
    """
    账户模型
    """
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True, comment="账户ID")
    account_name = Column(String(100), nullable=False, comment="账户名称")
    account_type = Column(String(50), comment="账户类型")
    institution = Column(String(100), comment="机构")
    account_code = Column(String(50), comment="账户代码")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class AccountGroup(Base):
    """
    账户分组模型
    """
    __tablename__ = "account_groups"
    
    id = Column(Integer, primary_key=True, index=True, comment="分组ID")
    name = Column(String(100), nullable=False, comment="分组名称")
    description = Column(Text, comment="分组描述")
    parent_id = Column(Integer, ForeignKey("account_groups.id"), comment="父分组ID")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Position(Base):
    """
    持仓模型
    """
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True, comment="持仓ID")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, comment="账户ID")
    asset_type = Column(String(50), comment="资产类型")
    symbol = Column(String(50), comment="代码")
    side = Column(String(20), comment="方向")
    quantity = Column(Float, comment="数量")
    available_quantity = Column(Float, comment="可用数量")
    avg_price = Column(Float, comment="平均价格")
    current_price = Column(Float, comment="当前价格")
    market_value = Column(Float, comment="市值")
    profit_loss = Column(Float, comment="盈亏")
    profit_loss_ratio = Column(Float, comment="盈亏比例")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Balance(Base):
    """
    余额模型
    """
    __tablename__ = "balances"
    
    id = Column(Integer, primary_key=True, index=True, comment="余额ID")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, comment="账户ID")
    total_balance = Column(Float, comment="总余额")
    available_balance = Column(Float, comment="可用余额")
    frozen_balance = Column(Float, comment="冻结余额")
    market_value = Column(Float, comment="市值")
    total_asset = Column(Float, comment="总资产")
    profit_loss = Column(Float, comment="盈亏")
    profit_loss_ratio = Column(Float, comment="盈亏比例")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
