"""
分析API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.database import get_db
from web.backend.schemas.analysis import (
    AnalysisFilter, AnalysisReport, ChartRequest, ChartResponse
)
from web.backend.services.analysis_service import AnalysisService
from web.backend.security.jwt import verify_token
from fastapi.security import OAuth2PasswordBearer


router = APIRouter(prefix="/analysis", tags=["分析"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@router.get("/comprehensive", response_model=AnalysisReport)
async def get_comprehensive_analysis(
    period: str = Query("day", description="分析周期"),
    asset_type: Optional[str] = Query(None, description="资产类型"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取综合分析报告
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    filter_params = AnalysisFilter(
        period=period,
        asset_type=asset_type,
        account_id=account_id,
        start_time=start_time,
        end_time=end_time
    )
    
    report = analysis_service.generate_comprehensive_report(filter_params)
    
    return report


@router.get("/execution")
async def get_execution_analysis(
    period: str = Query("day", description="分析周期"),
    asset_type: Optional[str] = Query(None, description="资产类型"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取订单执行分析
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    filter_params = AnalysisFilter(
        period=period,
        asset_type=asset_type,
        account_id=account_id
    )
    
    analysis = analysis_service.analyze_order_execution(filter_params)
    
    return analysis


@router.get("/slippage")
async def get_slippage_analysis(
    period: str = Query("day", description="分析周期"),
    asset_type: Optional[str] = Query(None, description="资产类型"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取滑点分析
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    filter_params = AnalysisFilter(
        period=period,
        asset_type=asset_type,
        account_id=account_id
    )
    
    analysis = analysis_service.analyze_slippage(filter_params)
    
    return analysis


@router.get("/volume")
async def get_volume_analysis(
    period: str = Query("day", description="分析周期"),
    asset_type: Optional[str] = Query(None, description="资产类型"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取成交量分析
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    filter_params = AnalysisFilter(
        period=period,
        asset_type=asset_type,
        account_id=account_id
    )
    
    analysis = analysis_service.analyze_volume(filter_params)
    
    return analysis


@router.get("/efficiency")
async def get_efficiency_analysis(
    period: str = Query("day", description="分析周期"),
    asset_type: Optional[str] = Query(None, description="资产类型"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取订单效率分析
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    filter_params = AnalysisFilter(
        period=period,
        asset_type=asset_type,
        account_id=account_id
    )
    
    analysis = analysis_service.analyze_efficiency(filter_params)
    
    return analysis


@router.post("/charts/execution", response_model=ChartResponse)
async def generate_execution_chart(
    chart_request: ChartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    生成订单执行图表
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    chart_path = analysis_service.generate_execution_chart(chart_request)
    
    if not chart_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="图表生成失败"
        )
    
    return ChartResponse(
        chart_url=f"/charts/{chart_path}",
        chart_type=chart_request.chart_type
    )


@router.post("/charts/slippage", response_model=ChartResponse)
async def generate_slippage_chart(
    chart_request: ChartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    生成滑点分析图表
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    chart_path = analysis_service.generate_slippage_chart(chart_request)
    
    if not chart_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="图表生成失败"
        )
    
    return ChartResponse(
        chart_url=f"/charts/{chart_path}",
        chart_type=chart_request.chart_type
    )


@router.post("/charts/volume", response_model=ChartResponse)
async def generate_volume_chart(
    chart_request: ChartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    生成成交量分析图表
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    chart_path = analysis_service.generate_volume_chart(chart_request)
    
    if not chart_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="图表生成失败"
        )
    
    return ChartResponse(
        chart_url=f"/charts/{chart_path}",
        chart_type=chart_request.chart_type
    )


@router.post("/charts/efficiency", response_model=ChartResponse)
async def generate_efficiency_chart(
    chart_request: ChartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    生成订单效率图表
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    chart_path = analysis_service.generate_efficiency_chart(chart_request)
    
    if not chart_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="图表生成失败"
        )
    
    return ChartResponse(
        chart_url=f"/charts/{chart_path}",
        chart_type=chart_request.chart_type
    )


@router.post("/export/pdf")
async def export_pdf_report(
    chart_request: ChartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    导出PDF报告
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    report_path = analysis_service.export_pdf_report(chart_request)
    
    if not report_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF报告导出失败"
        )
    
    return {
        "message": "PDF报告导出成功",
        "report_url": f"/reports/{report_path}"
    }


@router.post("/export/html")
async def export_html_report(
    chart_request: ChartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    导出HTML报告
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    report_path = analysis_service.export_html_report(chart_request)
    
    if not report_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HTML报告导出失败"
        )
    
    return {
        "message": "HTML报告导出成功",
        "report_url": f"/reports/{report_path}"
    }


@router.post("/export/csv")
async def export_csv_report(
    chart_request: ChartRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    导出CSV报告
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效"
        )
    
    analysis_service = AnalysisService(db)
    
    report_path = analysis_service.export_csv_report(chart_request)
    
    if not report_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CSV报告导出失败"
        )
    
    return {
        "message": "CSV报告导出成功",
        "report_url": f"/reports/{report_path}"
    }
