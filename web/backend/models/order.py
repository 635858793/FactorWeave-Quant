"""
订单模型
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from web.backend.config.database import Base


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


class OrderTemplate(Base):
    """
    订单模板模型
    """
    __tablename__ = "order_templates"
    
    id = Column(Integer, primary_key=True, index=True, comment="模板ID")
    name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(Text, comment="模板描述")
    asset_type = Column(String(50), comment="资产类型")
    account_id = Column(Integer, ForeignKey("accounts.id"), comment="账户ID")
    order_side = Column(SQLEnum(OrderSide), comment="订单方向")
    order_type = Column(SQLEnum(OrderType), comment="订单类型")
    price = Column(Float, comment="价格")
    quantity = Column(Float, comment="数量")
    time_in_force = Column(String(20), comment="有效期")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class OrderGroup(Base):
    """
    订单分组模型
    """
    __tablename__ = "order_groups"
    
    id = Column(Integer, primary_key=True, index=True, comment="分组ID")
    name = Column(String(100), nullable=False, comment="分组名称")
    description = Column(Text, comment="分组描述")
    parent_id = Column(Integer, ForeignKey("order_groups.id"), comment="父分组ID")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Fill(Base):
    """
    成交记录模型
    """
    __tablename__ = "fills"
    
    id = Column(Integer, primary_key=True, index=True, comment="成交ID")
    order_id = Column(String(50), index=True, nullable=False, comment="订单ID")
    fill_id = Column(String(50), unique=True, index=True, nullable=False, comment="成交ID")
    account_id = Column(Integer, ForeignKey("accounts.id"), comment="账户ID")
    asset_type = Column(String(50), comment="资产类型")
    symbol = Column(String(50), comment="代码")
    side = Column(SQLEnum(OrderSide), comment="方向")
    price = Column(Float, nullable=False, comment="成交价格")
    quantity = Column(Float, nullable=False, comment="成交数量")
    commission = Column(Float, comment="手续费")
    fill_time = Column(DateTime(timezone=True), nullable=False, comment="成交时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")


class AnalysisReport(Base):
    """
    分析报告模型
    """
    __tablename__ = "analysis_reports"
    
    id = Column(Integer, primary_key=True, index=True, comment="报告ID")
    report_type = Column(String(50), nullable=False, comment="报告类型")
    period = Column(String(20), comment="分析周期")
    asset_type = Column(String(50), comment="资产类型")
    account_id = Column(Integer, ForeignKey("accounts.id"), comment="账户ID")
    start_time = Column(DateTime(timezone=True), comment="开始时间")
    end_time = Column(DateTime(timezone=True), comment="结束时间")
    report_data = Column(Text, comment="报告数据")
    chart_urls = Column(Text, comment="图表URLs")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")


class DataExport(Base):
    """
    数据导出模型
    """
    __tablename__ = "data_exports"
    
    id = Column(Integer, primary_key=True, index=True, comment="导出ID")
    export_type = Column(String(50), nullable=False, comment="导出类型")
    export_format = Column(String(20), nullable=False, comment="导出格式")
    export_data = Column(Text, comment="导出数据")
    file_path = Column(String(255), comment="文件路径")
    file_size = Column(Integer, comment="文件大小")
    status = Column(String(20), comment="状态")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    completed_at = Column(DateTime(timezone=True), comment="完成时间")
