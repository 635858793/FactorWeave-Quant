"""
Redis配置
"""

from typing import Optional
import redis
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend.config.settings import settings


_redis_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """
    获取Redis客户端
    """
    global _redis_client
    
    if not settings.REDIS_ENABLED:
        return None
    
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            
            _redis_client.ping()
            
        except Exception as e:
            print(f"Redis连接失败: {e}")
            _redis_client = None
    
    return _redis_client


def close_redis():
    """
    关闭Redis连接
    """
    global _redis_client
    
    if _redis_client:
        _redis_client.close()
        _redis_client = None
