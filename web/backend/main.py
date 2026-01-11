"""
FastAPI主应用
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend.config.settings import settings
from web.backend.config.database import init_db
from web.backend.api.v1 import auth, orders, accounts, analysis, users, system, security, notifications, websocket
from web.backend.middleware.auth import auth_middleware
from web.backend.middleware.cors import CORSMiddleware as CustomCORSMiddleware
from web.backend.middleware.rate_limit import rate_limit_middleware
from web.backend.services.audit_service import AuditService
from web.backend.config.database import get_duckdb_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    print("应用启动中...")
    
    init_db()
    
    print("应用启动完成")
    
    yield
    
    print("应用关闭中...")
    
    print("应用关闭完成")


app = FastAPI(
    title=settings.APP_NAME,
    description="Hikyuu UI Web Interface",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


app.add_middleware(GZipMiddleware, minimum_size=1000)


app.middleware("http")(auth_middleware)
app.middleware("http")(rate_limit_middleware)


app.include_router(auth.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")


@app.get("/")
async def root():
    """
    根路径
    """
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """
    健康检查
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    验证异常处理
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    通用异常处理
    """
    duckdb_manager = get_duckdb_manager()
    audit_service = AuditService(duckdb_manager)
    
    user = getattr(request.state, "user", None)
    
    audit_service.create_audit_log(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action="error",
        resource_type="system",
        resource_id=None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_method=request.method,
        request_path=str(request.url.path),
        request_params=str(request.query_params),
        response_status=500,
        response_time=None,
        success=False,
        error_message=str(exc)
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "服务器内部错误",
            "error": str(exc) if settings.DEBUG else "Internal Server Error"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "web.backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
