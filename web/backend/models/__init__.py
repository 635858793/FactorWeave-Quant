"""
数据库模型
"""

from web.backend.config.database import Base as DatabaseBase

# 所有模型都继承自 DatabaseBase
# 这里我们重新导出 Base 以便使用
Base = DatabaseBase

from web.backend.models import user, order, account, security, notification

__all__ = ["Base", "user", "order", "account", "security", "notification"]
