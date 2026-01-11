#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易接口类型定义

定义交易接口的基类和相关枚举，避免循环导入
"""

from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass


class ExecutionStatus(Enum):
    """执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    TIMEOUT = "timeout"
    REJECTED = "rejected"


@dataclass
class ExecutionResult:
    """执行结果"""
    order_id: str
    status: ExecutionStatus
    message: str = ""
    exchange_order_id: Optional[str] = None
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class TradingInterface:
    """交易接口基类"""

    def connect(self) -> bool:
        """连接交易服务器"""
        return True

    def login(self) -> bool:
        """登录交易账户"""
        return True

    def disconnect(self):
        """断开交易连接"""
        pass

    def submit_order(self, order) -> ExecutionResult:
        """提交订单"""
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """取消订单"""
        raise NotImplementedError

    def query_order_status(self, order_id: str) -> ExecutionResult:
        """查询订单状态"""
        raise NotImplementedError

    def query_fund_info(self, account_id: str):
        """查询账户资金信息"""
        raise NotImplementedError

    def query_positions(self, account_id: str):
        """查询账户持仓信息"""
        raise NotImplementedError
