"""
限流中间件
"""

from fastapi import Request, HTTPException, status
from collections import defaultdict
from typing import Dict
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


class RateLimiter:
    """
    限流器
    """
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """
        检查是否允许访问
        """
        now = time.time()
        
        self.requests[key] = [
            timestamp for timestamp in self.requests[key]
            if timestamp > now - window
        ]
        
        if len(self.requests[key]) >= limit:
            return False
        
        self.requests[key].append(now)
        return True


rate_limiter = RateLimiter()


async def rate_limit_middleware(
    request: Request,
    call_next
):
    """
    限流中间件
    """
    if not settings.RATE_LIMIT_ENABLED:
        response = await call_next(request)
        return response
    
    client_ip = request.client.host
    user_id = getattr(request.state, "user", None)
    
    if user_id:
        key = f"user:{user_id.id}"
    else:
        key = f"ip:{client_ip}"
    
    if not rate_limiter.is_allowed(
        key,
        settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
        60
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试"
        )
    
    response = await call_next(request)
    return response
