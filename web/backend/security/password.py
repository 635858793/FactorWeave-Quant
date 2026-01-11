"""
密码工具
"""

from passlib.context import CryptContext
from typing import Optional
import secrets
import string
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    哈希密码
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_password(length: int = 12) -> str:
    """
    生成随机密码
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    return password


def check_password_strength(password: str) -> dict:
    """
    检查密码强度
    """
    score = 0
    feedback = []
    
    if len(password) >= settings.PASSWORD_MIN_LENGTH:
        score += 20
    else:
        feedback.append(f"密码长度至少{settings.PASSWORD_MIN_LENGTH}位")
    
    if len(password) <= settings.PASSWORD_MAX_LENGTH:
        score += 10
    else:
        feedback.append(f"密码长度最多{settings.PASSWORD_MAX_LENGTH}位")
    
    if any(c.isupper() for c in password):
        score += 20
    else:
        feedback.append("密码应包含大写字母")
    
    if any(c.islower() for c in password):
        score += 20
    else:
        feedback.append("密码应包含小写字母")
    
    if any(c.isdigit() for c in password):
        score += 15
    else:
        feedback.append("密码应包含数字")
    
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in password):
        score += 15
    else:
        feedback.append("密码应包含特殊字符")
    
    if score >= 90:
        strength = "very_strong"
    elif score >= 70:
        strength = "strong"
    elif score >= 50:
        strength = "medium"
    elif score >= 30:
        strength = "weak"
    else:
        strength = "very_weak"
    
    return {
        "score": score,
        "strength": strength,
        "feedback": feedback
    }
