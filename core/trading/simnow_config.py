#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SimNow配置模块

提供SimNow模拟交易环境的配置和管理功能
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from loguru import logger


class SimNowEnvironment(Enum):
    """SimNow环境类型"""
    GROUP_1 = "group_1"
    GROUP_2 = "group_2"
    GROUP_3 = "group_3"
    ENV_7X24 = "env_7x24"


@dataclass
class SimNowConfig:
    """SimNow配置"""
    environment: SimNowEnvironment = SimNowEnvironment.GROUP_1
    broker_id: str = "9999"
    app_id: str = "simnow_client_test"
    auth_code: str = "0000000000000000"
    investor_id: str = ""
    password: str = ""
    product_info: str = "simnow_client_test"
    
    trade_front: str = ""
    quote_front: str = ""
    
    def __post_init__(self):
        """根据环境自动填充前置地址"""
        self._update_front_addresses()
    
    def _update_front_addresses(self):
        """更新前置地址"""
        if self.environment == SimNowEnvironment.GROUP_1:
            self.trade_front = "tcp://180.168.146.187:10130"
            self.quote_front = "tcp://180.168.146.187:10131"
        elif self.environment == SimNowEnvironment.GROUP_2:
            self.trade_front = "tcp://180.168.146.187:10132"
            self.quote_front = "tcp://180.168.146.187:10133"
        elif self.environment == SimNowEnvironment.GROUP_3:
            self.trade_front = "tcp://180.168.146.187:10134"
            self.quote_front = "tcp://180.168.146.187:10135"
        elif self.environment == SimNowEnvironment.ENV_7X24:
            self.trade_front = "tcp://180.168.146.187:10201"
            self.quote_front = "tcp://180.168.146.187:10211"
    
    def set_environment(self, environment: SimNowEnvironment):
        """
        设置环境类型
        
        Args:
            environment: 环境类型
        """
        self.environment = environment
        self._update_front_addresses()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'environment': self.environment.value,
            'broker_id': self.broker_id,
            'app_id': self.app_id,
            'auth_code': self.auth_code,
            'investor_id': self.investor_id,
            'password': self.password,
            'product_info': self.product_info,
            'trade_front': self.trade_front,
            'quote_front': self.quote_front
        }


class SimNowAccountCreator:
    """SimNow账户创建工具"""
    
    @staticmethod
    def create_simnow_account(
        investor_id: str,
        password: str,
        environment: SimNowEnvironment = SimNowEnvironment.GROUP_1,
        account_name: str = "SimNow期货账户"
    ):
        """
        创建SimNow账户
        
        Args:
            investor_id: SimNow账号
            password: SimNow密码
            environment: SimNow环境类型
            account_name: 账户名称
            
        Returns:
            Account: 账户对象
        """
        from core.trading.account_models import Account, AccountStatus, TradingInterfaceType
        
        config = SimNowConfig(
            environment=environment,
            investor_id=investor_id,
            password=password
        )
        
        account = Account(
            account_id=f"simnow_{investor_id}",
            account_name=account_name,
            account_type="futures",
            status=AccountStatus.ACTIVE,
            balance=20000000.0,
            available_balance=20000000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=20000000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now(),
            trading_interface_type=TradingInterfaceType.CTP,
            ctp_broker_id=config.broker_id,
            ctp_investor_id=config.investor_id,
            ctp_password=config.password,
            ctp_trade_front=config.trade_front,
            ctp_quote_front=config.quote_front,
            ctp_app_id=config.app_id,
            ctp_auth_code=config.auth_code,
            ctp_product_info=config.product_info
        )
        
        logger.info(f"创建SimNow账户: {account.account_id}, 环境: {environment.value}")
        
        return account
    
    @staticmethod
    def create_simnow_accounts_for_all_environments(
        investor_id: str,
        password: str
    ) -> list:
        """
        为所有环境创建SimNow账户
        
        Args:
            investor_id: SimNow账号
            password: SimNow密码
            
        Returns:
            list: 账户对象列表
        """
        accounts = []
        
        for env in SimNowEnvironment:
            account_name = f"SimNow-{env.value}"
            account = SimNowAccountCreator.create_simnow_account(
                investor_id=investor_id,
                password=password,
                environment=env,
                account_name=account_name
            )
            accounts.append(account)
        
        logger.info(f"创建所有环境的SimNow账户: {len(accounts)} 个")
        
        return accounts


class SimNowEnvironmentInfo:
    """SimNow环境信息"""
    
    ENVIRONMENT_INFO = {
        SimNowEnvironment.GROUP_1: {
            "name": "第一组（推荐）",
            "description": "正式测试环境，与实盘交易时间一致",
            "trade_front": "tcp://180.168.146.187:10130",
            "quote_front": "tcp://180.168.146.187:10131",
            "trading_hours": "与实盘一致",
            "initial_funds": 20000000.0,
            "features": ["支持所有期货品种", "支持期权交易", "实时行情"]
        },
        SimNowEnvironment.GROUP_2: {
            "name": "第二组",
            "description": "备用测试环境",
            "trade_front": "tcp://180.168.146.187:10132",
            "quote_front": "tcp://180.168.146.187:10133",
            "trading_hours": "与实盘一致",
            "initial_funds": 20000000.0,
            "features": ["支持所有期货品种", "支持期权交易", "实时行情"]
        },
        SimNowEnvironment.GROUP_3: {
            "name": "第三组",
            "description": "备用测试环境",
            "trade_front": "tcp://180.168.146.187:10134",
            "quote_front": "tcp://180.168.146.187:10135",
            "trading_hours": "与实盘一致",
            "initial_funds": 20000000.0,
            "features": ["支持所有期货品种", "支持期权交易", "实时行情"]
        },
        SimNowEnvironment.ENV_7X24: {
            "name": "7x24环境",
            "description": "全天候测试环境，非交易时段可用",
            "trade_front": "tcp://180.168.146.187:10201",
            "quote_front": "tcp://180.168.146.187:10211",
            "trading_hours": "交易日16:00-次日09:00，非交易日16:00-次日12:00",
            "initial_funds": 20000000.0,
            "features": ["支持所有期货品种", "支持期权交易", "7x24可用"],
            "notes": [
                "新注册用户需要等待第三个交易日才能使用",
                "账户、资金、持仓与第一套环境上一交易日保持一致",
                "仅供CTP API测试，不提供结算服务"
            ]
        }
    }
    
    @classmethod
    def get_environment_info(cls, environment: SimNowEnvironment) -> dict:
        """
        获取环境信息
        
        Args:
            environment: 环境类型
            
        Returns:
            dict: 环境信息
        """
        return cls.ENVIRONMENT_INFO.get(environment, {})
    
    @classmethod
    def get_all_environments_info(cls) -> dict:
        """
        获取所有环境信息
        
        Returns:
            dict: 所有环境信息
        """
        return cls.ENVIRONMENT_INFO


def get_simnow_config(investor_id: str, password: str, environment: SimNowEnvironment = SimNowEnvironment.GROUP_1) -> SimNowConfig:
    """
    获取SimNow配置
    
    Args:
        investor_id: SimNow账号
        password: SimNow密码
        environment: 环境类型
        
    Returns:
        SimNowConfig: SimNow配置对象
    """
    return SimNowConfig(
        environment=environment,
        investor_id=investor_id,
        password=password
    )


def create_simnow_account_quick(investor_id: str, password: str, environment: SimNowEnvironment = SimNowEnvironment.GROUP_1):
    """
    快速创建SimNow账户
    
    Args:
        investor_id: SimNow账号
        password: SimNow密码
        environment: 环境类型
        
    Returns:
        Account: 账户对象
    """
    return SimNowAccountCreator.create_simnow_account(
        investor_id=investor_id,
        password=password,
        environment=environment
    )
