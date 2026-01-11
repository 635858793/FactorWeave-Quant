"""
应用配置
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """
    应用设置
    """
    
    APP_NAME: str = "Hikyuu UI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 128
    PASSWORD_HISTORY_COUNT: int = 5
    
    TWO_FA_ENABLED: bool = True
    TWO_FA_ISSUER: str = "Hikyuu UI"
    
    SESSION_TIMEOUT_MINUTES: int = 30
    
    ACCOUNT_LOCK_ENABLED: bool = True
    ACCOUNT_LOCK_MAX_ATTEMPTS: int = 5
    ACCOUNT_LOCK_DURATION_MINUTES: int = 30
    
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "data/logs/app.log"
    
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    DATA_ENCRYPTION_ENABLED: bool = True
    DATA_ENCRYPTION_FIELDS: List[str] = ["password", "api_secret", "two_fa_secret"]
    ENCRYPTION_KEY: str = "your-encryption-key-change-in-production"
    
    SECURITY_IP_WHITELIST_ENABLED: bool = False
    SECURITY_IP_BLACKLIST_ENABLED: bool = False
    SECURITY_REQUEST_SIGNATURE_ENABLED: bool = False
    
    SQL_INJECTION_ENABLED: bool = True
    XSS_ENABLED: bool = True
    CSRF_ENABLED: bool = True
    FILE_UPLOAD_ENABLED: bool = True
    COMMAND_INJECTION_ENABLED: bool = True
    PATH_TRAVERSAL_ENABLED: bool = True
    
    DATABASE_URL: str = "sqlite:///./data/databases/app.db"
    DUCKDB_PATH: str = "data/databases/hikyuu.db"
    
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    
    SMS_API_KEY: str = ""
    SMS_API_SECRET: str = ""
    SMS_API_URL: str = ""
    
    UPLOAD_DIR: str = "data/uploads"
    CHARTS_DIR: str = "data/charts"
    EXPORTS_DIR: str = "data/exports"
    BACKUPS_DIR: str = "data/backups"
    
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [".csv", ".xlsx", ".json", ".txt"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


os.makedirs("data/databases", exist_ok=True)
os.makedirs("data/logs", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)
os.makedirs("data/charts", exist_ok=True)
os.makedirs("data/exports", exist_ok=True)
os.makedirs("data/backups", exist_ok=True)
os.makedirs("reports", exist_ok=True)
os.makedirs("charts", exist_ok=True)
