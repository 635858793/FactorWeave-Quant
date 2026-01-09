"""
认证中间件
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.security.jwt import verify_token
from web.backend.services.user_service import UserService
from web.backend.config.database import get_duckdb_manager


security = HTTPBearer()


async def auth_middleware(
    request: Request,
    call_next
):
    """
    认证中间件
    """
    try:
        authorization: Optional[str] = request.headers.get("Authorization")
        
        if authorization:
            token = authorization.replace("Bearer ", "")
            
            payload = verify_token(token)
            
            if payload:
                username = payload.get("sub")
                
                duckdb_manager = get_duckdb_manager()
                user_service = UserService(duckdb_manager)
                
                user = user_service.get_user_by_username(username)
                
                if user and user.is_active:
                    request.state.user = user
        
        response = await call_next(request)
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败"
        )
