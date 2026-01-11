"""
加密工具
"""

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from typing import Optional
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


def generate_key(password: str = None) -> bytes:
    """
    生成加密密钥
    """
    if password:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    else:
        key = Fernet.generate_key()
    
    return key


def encrypt_data(data: str, key: bytes = None) -> Optional[str]:
    """
    加密数据
    """
    if not settings.DATA_ENCRYPTION_ENABLED:
        return data
    
    try:
        if key is None:
            key = settings.ENCRYPTION_KEY.encode()
        
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(data.encode())
        
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    except Exception as e:
        print(f"加密数据失败: {e}")
        return None


def decrypt_data(encrypted_data: str, key: bytes = None) -> Optional[str]:
    """
    解密数据
    """
    if not settings.DATA_ENCRYPTION_ENABLED:
        return encrypted_data
    
    try:
        if key is None:
            key = settings.ENCRYPTION_KEY.encode()
        
        fernet = Fernet(key)
        decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted_data = fernet.decrypt(decoded_data)
        
        return decrypted_data.decode()
    
    except Exception as e:
        print(f"解密数据失败: {e}")
        return None


def encrypt_field(field_name: str, data: str) -> str:
    """
    加密字段
    """
    if field_name in settings.DATA_ENCRYPTION_FIELDS:
        encrypted = encrypt_data(data)
        return encrypted if encrypted else data
    
    return data


def decrypt_field(field_name: str, data: str) -> str:
    """
    解密字段
    """
    if field_name in settings.DATA_ENCRYPTION_FIELDS:
        decrypted = decrypt_data(data)
        return decrypted if decrypted else data
    
    return data


def hash_data(data: str) -> str:
    """
    哈希数据
    """
    import hashlib
    
    return hashlib.sha256(data.encode()).hexdigest()
