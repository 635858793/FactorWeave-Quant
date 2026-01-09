#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTP交易接口配置

管理CTP交易接口的配置信息
"""

from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class CTPConfig:
    """CTP配置"""
    
    # 交易前置地址
    trade_front: str = ""
    
    # 行情前置地址
    quote_front: str = ""
    
    # 期货公司代码
    broker_id: str = ""
    
    # 投资者代码
    investor_id: str = ""
    
    # 密码
    password: str = ""
    
    # 应用ID（用于认证）
    app_id: str = ""
    
    # 认证码
    auth_code: str = ""
    
    # 产品信息
    product_info: str = ""
    
    # 是否使用模拟模式
    use_simulation: bool = True


# 默认配置（模拟模式）
DEFAULT_CTP_CONFIG = CTPConfig(
    trade_front="",
    quote_front="",
    broker_id="",
    investor_id="",
    password="",
    app_id="",
    auth_code="",
    product_info="",
    use_simulation=True
)


# 配置管理器
class CTPConfigManager:
    """CTP配置管理器"""
    
    def __init__(self):
        self._configs: Dict[str, CTPConfig] = {}
        self._default_config = DEFAULT_CTP_CONFIG
    
    def register_config(self, name: str, config: CTPConfig):
        """
        注册配置
        
        Args:
            name: 配置名称
            config: 配置对象
        """
        self._configs[name] = config
    
    def get_config(self, name: str = "default") -> CTPConfig:
        """
        获取配置
        
        Args:
            name: 配置名称
            
        Returns:
            CTPConfig: 配置对象
        """
        if name in self._configs:
            return self._configs[name]
        return self._default_config
    
    def set_default_config(self, config: CTPConfig):
        """
        设置默认配置
        
        Args:
            config: 配置对象
        """
        self._default_config = config
    
    def load_from_dict(self, config_dict: Dict[str, any]) -> CTPConfig:
        """
        从字典加载配置
        
        Args:
            config_dict: 配置字典
            
        Returns:
            CTPConfig: 配置对象
        """
        return CTPConfig(
            trade_front=config_dict.get('trade_front', ''),
            quote_front=config_dict.get('quote_front', ''),
            broker_id=config_dict.get('broker_id', ''),
            investor_id=config_dict.get('investor_id', ''),
            password=config_dict.get('password', ''),
            app_id=config_dict.get('app_id', ''),
            auth_code=config_dict.get('auth_code', ''),
            product_info=config_dict.get('product_info', ''),
            use_simulation=config_dict.get('use_simulation', True)
        )


# 全局配置管理器实例
ctp_config_manager = CTPConfigManager()


def get_ctp_config(name: str = "default") -> CTPConfig:
    """
    获取CTP配置
    
    Args:
        name: 配置名称
        
    Returns:
        CTPConfig: 配置对象
    """
    return ctp_config_manager.get_config(name)


def register_ctp_config(name: str, config: CTPConfig):
    """
    注册CTP配置
    
    Args:
        name: 配置名称
        config: 配置对象
    """
    ctp_config_manager.register_config(name, config)
