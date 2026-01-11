"""
安全配置
"""

from typing import List, Optional


class SecurityConfig:
    """
    安全配置
    """
    
    def __init__(self):
        self.ip_whitelist_enabled: bool = False
        self.ip_blacklist_enabled: bool = False
        self.request_signature_enabled: bool = False
        self.https_force: bool = False
        self.hsts_max_age: int = 31536000
        
        self.sql_injection_enabled: bool = True
        self.xss_enabled: bool = True
        self.csrf_enabled: bool = True
        self.file_upload_enabled: bool = True
        self.command_injection_enabled: bool = True
        self.path_traversal_enabled: bool = True


security_config = SecurityConfig()
