"""
IP控制工具
"""

from typing import List, Optional
from ipaddress import ip_address, ip_network
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.config.settings import settings


def is_ip_allowed(ip: str, whitelist: List[str], blacklist: List[str]) -> bool:
    """
    检查IP是否允许访问
    """
    if settings.SECURITY_IP_BLACKLIST_ENABLED:
        if is_ip_in_blacklist(ip, blacklist):
            return False
    
    if settings.SECURITY_IP_WHITELIST_ENABLED:
        if not is_ip_in_whitelist(ip, whitelist):
            return False
    
    return True


def is_ip_in_whitelist(ip: str, whitelist: List[str]) -> bool:
    """
    检查IP是否在白名单中
    """
    if not whitelist:
        return True
    
    try:
        ip_obj = ip_address(ip)
        
        for whitelist_item in whitelist:
            try:
                if "/" in whitelist_item:
                    network = ip_network(whitelist_item, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    if ip == whitelist_item:
                        return True
            except:
                continue
        
        return False
    
    except:
        return False


def is_ip_in_blacklist(ip: str, blacklist: List[str]) -> bool:
    """
    检查IP是否在黑名单中
    """
    if not blacklist:
        return False
    
    try:
        ip_obj = ip_address(ip)
        
        for blacklist_item in blacklist:
            try:
                if "/" in blacklist_item:
                    network = ip_network(blacklist_item, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    if ip == blacklist_item:
                        return True
            except:
                continue
        
        return False
    
    except:
        return False


def validate_ip(ip: str) -> bool:
    """
    验证IP地址
    """
    try:
        ip_address(ip)
        return True
    except:
        return False


def validate_ip_range(ip_range: str) -> bool:
    """
    验证IP范围
    """
    try:
        ip_network(ip_range, strict=False)
        return True
    except:
        return False
