"""
CORS中间件
"""

from fastapi import Request
from starlette.middleware.cors import CORSMiddleware
from typing import List, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


class CORSMiddleware(CORSMiddleware):
    """
    CORS中间件
    """
    
    def __init__(
        self,
        app,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        allow_credentials: bool = False,
        expose_headers: List[str] = None,
        max_age: int = 600
    ):
        super().__init__(
            app,
            allow_origins=allow_origins or settings.CORS_ORIGINS,
            allow_methods=allow_methods or settings.CORS_ALLOW_METHODS,
            allow_headers=allow_headers or settings.CORS_ALLOW_HEADERS,
            allow_credentials=allow_credentials or settings.CORS_ALLOW_CREDENTIALS,
            expose_headers=expose_headers,
            max_age=max_age
        )
