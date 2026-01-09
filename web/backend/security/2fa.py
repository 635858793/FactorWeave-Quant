"""
双因素认证工具
"""

import pyotp
import qrcode
from io import BytesIO
import base64
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


def generate_2fa_secret(user_id: int) -> str:
    """
    生成双因素认证密钥
    """
    secret = pyotp.random_base32()
    
    return secret


def generate_2fa_qrcode(user_id: int, username: str, secret: str) -> str:
    """
    生成双因素认证二维码
    """
    totp = pyotp.TOTP(secret)
    
    provisioning_uri = totp.provisioning_uri(
        name=username,
        issuer_name=settings.TWO_FA_ISSUER
    )
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"


def verify_2fa_code(user_id: int, code: str) -> bool:
    """
    验证双因素认证码
    """
    from web.backend.models.user import User
    from web.backend.config.database import get_duckdb_manager
    
    duckdb_manager = get_duckdb_manager()
    
    query = "SELECT two_fa_secret FROM users WHERE id = :user_id"
    params = {"user_id": user_id}
    
    result = duckdb_manager.execute_query(query, params)
    
    if not result:
        return False
    
    secret = result[0].get("two_fa_secret")
    
    if not secret:
        return False
    
    totp = pyotp.TOTP(secret)
    
    return totp.verify(code, valid_window=1)


def generate_2fa_backup_codes(count: int = 10) -> list:
    """
    生成双因素认证备份码
    """
    import secrets
    
    backup_codes = []
    
    for _ in range(count):
        code = secrets.token_hex(4)
        backup_codes.append(code.upper())
    
    return backup_codes


def verify_2fa_backup_code(user_id: int, code: str) -> bool:
    """
    验证双因素认证备份码
    """
    from web.backend.models.user import User
    from web.backend.config.database import get_duckdb_manager
    
    duckdb_manager = get_duckdb_manager()
    
    query = "SELECT backup_codes FROM user_2fa WHERE user_id = :user_id"
    params = {"user_id": user_id}
    
    result = duckdb_manager.execute_query(query, params)
    
    if not result:
        return False
    
    backup_codes = result[0].get("backup_codes")
    
    if not backup_codes:
        return False
    
    codes = backup_codes.split(",")
    
    if code.upper() in codes:
        codes.remove(code.upper())
        
        new_backup_codes = ",".join(codes)
        
        query = "UPDATE user_2fa SET backup_codes = :backup_codes WHERE user_id = :user_id"
        params = {"backup_codes": new_backup_codes, "user_id": user_id}
        
        duckdb_manager.execute_query(query, params)
        
        return True
    
    return False
