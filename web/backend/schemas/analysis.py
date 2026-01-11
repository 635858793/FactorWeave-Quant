"""
分析Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class AnalysisFilter(BaseModel):
    """
    分析过滤参数
    """
    period: str = Field("day", description="分析周期")
    asset_type: Optional[str] = Field(None, description="资产类型")
    account_id: Optional[int] = Field(None, description="账户ID")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")


class ChartRequest(BaseModel):
    """
    图表请求
    """
    chart_type: str = Field(..., description="图表类型")
    period: str = Field("day", description="分析周期")
    asset_type: Optional[str] = Field(None, description="资产类型")
    account_id: Optional[int] = Field(None, description="账户ID")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")


class ChartResponse(BaseModel):
    """
    图表响应
    """
    chart_url: str
    chart_type: str


class AnalysisReport(BaseModel):
    """
    分析报告
    """
    report_time: str
    period: str
    summary: Dict[str, Any]
    execution_analysis: Dict[str, Any]
    slippage_analysis: Dict[str, Any]
    volume_analysis: Dict[str, Any]
    efficiency_analysis: Dict[str, Any]
    recommendations: List[str]
