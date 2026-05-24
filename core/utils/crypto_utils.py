"""
加密工具模块

提供数据加密和解密功能，使用cryptography库的Fernet对称加密。
用于保护账户等敏感信息。

功能：
- 对称加密/解密
- 密钥管理（从环境变量或配置文件读取）
- 密钥生成和保存
"""

import os
import base64
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger


class CryptoUtils:
    """
    加密工具类
    
    使用Fernet对称加密算法保护敏感数据。
    """

    _instance: Optional['CryptoUtils'] = None
    _fernet: Optional[Fernet] = None
    _key_file: Path = Path("config/encryption_key.key")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._fernet is None:
            self._initialize_encryption()

    def _initialize_encryption(self):
        """初始化加密"""
        try:
            # 尝试从环境变量获取密钥
            env_key = os.environ.get('HIKYUU_ENCRYPTION_KEY')
            if env_key:
                key = env_key.encode()
                self._fernet = Fernet(key)
                logger.info("从环境变量加载加密密钥")
                return

            # 尝试从密钥文件加载
            if self._key_file.exists():
                with open(self._key_file, 'rb') as f:
                    key = f.read()
                self._fernet = Fernet(key)
                logger.info("从密钥文件加载加密密钥")
                return

            # 生成新密钥
            key = Fernet.generate_key()
            self._fernet = Fernet(key)
            
            # 保存密钥到文件
            self._key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._key_file, 'wb') as f:
                f.write(key)
            
            logger.warning("⚠️  生成了新的加密密钥并保存到: {}".format(self._key_file))
            logger.warning("⚠️  请妥善保管此密钥文件，丢失后无法解密数据！")

        except Exception as e:
            logger.error(f"初始化加密失败: {e}")
            raise

    def encrypt(self, plaintext: str) -> str:
        """
        加密文本
        
        Args:
            plaintext: 明文
            
        Returns:
            str: 加密后的文本（Base64编码）
        """
        if not plaintext:
            return ""
        
        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"加密失败: {e}")
            raise

    def decrypt(self, ciphertext: str) -> str:
        """
        解密文本
        
        Args:
            ciphertext: 密文（Base64编码）
            
        Returns:
            str: 解密后的明文
        """
        if not ciphertext:
            return ""
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"解密失败: {e}")
            raise

    def encrypt_dict_field(self, data: dict, field_name: str) -> dict:
        """
        加密字典中的指定字段
        
        Args:
            data: 数据字典
            field_name: 要加密的字段名
            
        Returns:
            dict: 加密后的字典
        """
        if field_name in data and data[field_name]:
            data[field_name] = self.encrypt(data[field_name])
        return data

    def decrypt_dict_field(self, data: dict, field_name: str) -> dict:
        """
        解密字典中的指定字段
        
        Args:
            data: 数据字典
            field_name: 要解密的字段名
            
        Returns:
            dict: 解密后的字典
        """
        if field_name in data and data[field_name]:
            data[field_name] = self.decrypt(data[field_name])
        return data

    def encrypt_account_data(self, account_data: dict) -> dict:
        """
        加密账户数据中的敏感字段
        
        Args:
            account_data: 账户数据字典
            
        Returns:
            dict: 加密后的账户数据
        """
        sensitive_fields = [
            'ctp_password',
            'ctp_auth_code',
            'xtp_password',
            'miniqmt_password',
            'binance_secret_key',
            'binance_futures_secret_key',
            'okx_secret_key',
            'okx_passphrase',
            'okx_futures_secret_key',
            'okx_futures_passphrase',
            'huobi_secret_key',
            'huobi_futures_secret_key',
            'bitget_secret_key',
            'bitget_passphrase',
            'bybit_secret_key',
        ]

        for field in sensitive_fields:
            self.encrypt_dict_field(account_data, field)

        return account_data

    def decrypt_account_data(self, account_data: dict) -> dict:
        """
        解密账户数据中的敏感字段
        
        Args:
            account_data: 账户数据字典
            
        Returns:
            dict: 解密后的账户数据
        """
        sensitive_fields = [
            'ctp_password',
            'ctp_auth_code',
            'xtp_password',
            'miniqmt_password',
            'binance_secret_key',
            'binance_futures_secret_key',
            'okx_secret_key',
            'okx_passphrase',
            'okx_futures_secret_key',
            'okx_futures_passphrase',
            'huobi_secret_key',
            'huobi_futures_secret_key',
            'bitget_secret_key',
            'bitget_passphrase',
            'bybit_secret_key',
        ]
        
        for field in sensitive_fields:
            self.decrypt_dict_field(account_data, field)
        
        return account_data


# 全局实例
_crypto_utils: Optional[CryptoUtils] = None


def get_crypto_utils() -> CryptoUtils:
    """
    获取加密工具实例（单例模式）
    
    Returns:
        CryptoUtils: 加密工具实例
    """
    global _crypto_utils
    if _crypto_utils is None:
        _crypto_utils = CryptoUtils()
    return _crypto_utils


def encrypt_text(plaintext: str) -> str:
    """
    加密文本（便捷函数）
    
    Args:
        plaintext: 明文
        
    Returns:
        str: 加密后的文本
    """
    return get_crypto_utils().encrypt(plaintext)


def decrypt_text(ciphertext: str) -> str:
    """
    解密文本（便捷函数）
    
    Args:
        ciphertext: 密文
        
    Returns:
        str: 解密后的明文
    """
    return get_crypto_utils().decrypt(ciphertext)
