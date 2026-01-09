"""
请求签名工具
"""

import hmac
import hashlib
from typing import Dict, Any, Optional
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


def generate_signature(
    api_key: str,
    api_secret: str,
    timestamp: int,
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[str] = None
) -> str:
    """
    生成请求签名
    """
    if not settings.SECURITY_REQUEST_SIGNATURE_ENABLED:
        return ""
    
    payload = f"{method}{path}{timestamp}"
    
    if params:
        sorted_params = sorted(params.items())
        payload += "".join([f"{k}={v}" for k, v in sorted_params])
    
    if body:
        payload += body
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_signature(
    api_key: str,
    api_secret: str,
    timestamp: int,
    method: str,
    path: str,
    signature: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[str] = None
) -> bool:
    """
    验证请求签名
    """
    if not settings.SECURITY_REQUEST_SIGNATURE_ENABLED:
        return True
    
    expected_signature = generate_signature(
        api_key,
        api_secret,
        timestamp,
        method,
        path,
        params,
        body
    )
    
    return hmac.compare_digest(signature, expected_signature)


def generate_timestamp() -> int:
    """
    生成时间戳
    """
    return int(time.time())


def is_timestamp_valid(timestamp: int, max_age: int = 300) -> bool:
    """
    验证时间戳是否有效
    """
    current_time = int(time.time())
    
    return abs(current_time - timestamp) <= max_age
