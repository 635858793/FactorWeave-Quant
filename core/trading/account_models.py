#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户管理相关数据模型

定义账户、持仓、资金等数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from decimal import Decimal

from core.plugin_types import AssetType


class InstitutionType(Enum):
    """机构类型"""
    BROKER = "broker"                    # 证券公司
    FUTURES_COMPANY = "futures_company"  # 期货公司
    BANK = "bank"                        # 银行
    INSURANCE = "insurance"              # 保险公司
    FUND_COMPANY = "fund_company"      # 基金公司
    OTHER = "other"                      # 其他机构


class TradingInterfaceType(Enum):
    """交易接口类型"""
    MOCK = "mock"                        # 模拟交易
    CTP = "ctp"                          # CTP接口
    XTP = "xtp"                          # XTP接口
    XTP_PRO = "xtp_pro"                  # XTP Pro接口
    TORA = "tora"                        # TORA接口
    OMS = "oms"                          # OMS接口
    CUSTOM = "custom"                    # 自定义接口
    MINIQMT = "miniqmt"                  # miniQMT接口
    
    # 加密货币交易所
    BINANCE = "binance"                  # 币安
    BINANCE_FUTURES = "binance_futures"  # 币安合约
    OKX = "okx"                          # OKX（欧易）
    OKX_FUTURES = "okx_futures"          # OKX合约
    HUOBI = "huobi"                      # 火币（HTX）
    HUOBI_FUTURES = "huobi_futures"      # 火币合约
    BITGET = "bitget"                    # Bitget
    BYBIT = "bybit"                      # Bybit


class AccountStatus(Enum):
    """账户状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FROZEN = "frozen"
    CLOSED = "closed"


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"


@dataclass
class Account:
    """账户信息"""
    account_id: str
    account_name: str
    account_type: str
    status: AccountStatus
    balance: float
    available_balance: float
    frozen_balance: float
    market_value: float
    total_assets: float
    profit_loss: float
    profit_loss_ratio: float
    create_time: datetime
    update_time: datetime
    user_id: str = "system"
    trading_day: str = ""
    risk_level: str = "normal"
    margin_ratio: float = 0.0
    maintenance_margin: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 机构信息
    institution_name: str = ""              # 机构名称
    institution_type: InstitutionType = InstitutionType.BROKER  # 机构类型
    
    # 交易接口类型
    trading_interface_type: TradingInterfaceType = TradingInterfaceType.MOCK  # 交易接口类型
    
    # CTP交易接口配置（已废弃，建议使用 metadata）
    ctp_broker_id: str = ""
    ctp_investor_id: str = ""
    ctp_password: str = ""
    ctp_trade_front: str = ""
    ctp_quote_front: str = ""
    ctp_app_id: str = ""
    ctp_auth_code: str = ""
    ctp_product_info: str = ""
    
    # XTP交易接口配置（已废弃，建议使用 metadata）
    xtp_account_id: str = ""
    xtp_password: str = ""
    xtp_server_address: str = ""
    xtp_client_id: int = 0
    xtp_software_key: str = ""
    xtp_md_ip: str = ""
    xtp_md_port: int = 0
    xtp_protocol: str = "tcp"
    xtp_buffer_size: int = 0
    xtp_td_ip: str = ""
    xtp_td_port: int = 0
    
    # 币安（Binance）配置
    binance_api_key: str = ""
    binance_secret_key: str = ""
    binance_rest_url: str = "https://api.binance.com"
    binance_ws_url: str = "wss://stream.binance.com:9443"
    
    # 币安合约配置
    binance_futures_api_key: str = ""
    binance_futures_secret_key: str = ""
    binance_futures_rest_url: str = "https://fapi.binance.com"
    binance_futures_ws_url: str = "wss://fstream.binance.com"
    
    # OKX配置
    okx_api_key: str = ""
    okx_secret_key: str = ""
    okx_passphrase: str = ""
    okx_rest_url: str = "https://www.okx.com"
    okx_ws_url: str = "wss://ws.okx.com:8443"
    
    # OKX合约配置
    okx_futures_api_key: str = ""
    okx_futures_secret_key: str = ""
    okx_futures_passphrase: str = ""
    okx_futures_rest_url: str = "https://www.okx.com"
    okx_futures_ws_url: str = "wss://ws.okx.com:8443"
    
    # 火币（Huobi/HTX）配置
    huobi_api_key: str = ""
    huobi_secret_key: str = ""
    huobi_rest_url: str = "https://api.huobi.pro"
    huobi_ws_url: str = "wss://api.huobi.pro/ws"
    
    # 火币合约配置
    huobi_futures_api_key: str = ""
    huobi_futures_secret_key: str = ""
    huobi_futures_rest_url: str = "https://api.hbdm.com"
    huobi_futures_ws_url: str = "wss://api.hbdm.com/ws"
    
    # Bitget配置
    bitget_api_key: str = ""
    bitget_secret_key: str = ""
    bitget_passphrase: str = ""
    bitget_rest_url: str = "https://api.bitget.com"
    bitget_ws_url: str = "wss://ws.bitget.com"
    
    # Bybit配置
    bybit_api_key: str = ""
    bybit_secret_key: str = ""
    bybit_rest_url: str = "https://api.bybit.com"
    bybit_ws_url: str = "wss://stream.bybit.com"
    
    # miniQMT配置
    miniqmt_account_id: str = ""
    miniqmt_password: str = ""
    miniqmt_ip: str = "127.0.0.1"
    miniqmt_port: int = 58610
    
    # 交易接口（已废弃，使用 trading_interface_type 替代）
    trading_interface: str = ""

    @property
    def total_balance(self) -> float:
        """总余额"""
        return self.balance + self.frozen_balance

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'account_id': self.account_id,
            'account_name': self.account_name,
            'account_type': self.account_type,
            'status': self.status.value,
            'balance': self.balance,
            'available_balance': self.available_balance,
            'frozen_balance': self.frozen_balance,
            'market_value': self.market_value,
            'total_assets': self.total_assets,
            'profit_loss': self.profit_loss,
            'profit_loss_ratio': self.profit_loss_ratio,
            'create_time': self.create_time.isoformat(),
            'update_time': self.update_time.isoformat(),
            'user_id': self.user_id,
            'trading_day': self.trading_day,
            'risk_level': self.risk_level,
            'margin_ratio': self.margin_ratio,
            'maintenance_margin': self.maintenance_margin,
            'metadata': self.metadata,
            'institution_name': self.institution_name,
            'institution_type': self.institution_type.value,
            'trading_interface_type': self.trading_interface_type.value,
            'ctp_broker_id': self.ctp_broker_id,
            'ctp_investor_id': self.ctp_investor_id,
            'ctp_password': self.ctp_password,
            'ctp_trade_front': self.ctp_trade_front,
            'ctp_quote_front': self.ctp_quote_front,
            'ctp_app_id': self.ctp_app_id,
            'ctp_auth_code': self.ctp_auth_code,
            'ctp_product_info': self.ctp_product_info,
            'xtp_account_id': self.xtp_account_id,
            'xtp_password': self.xtp_password,
            'xtp_server_address': self.xtp_server_address,
            'xtp_client_id': self.xtp_client_id,
            'xtp_software_key': self.xtp_software_key,
            'xtp_md_ip': self.xtp_md_ip,
            'xtp_md_port': self.xtp_md_port,
            'xtp_protocol': self.xtp_protocol,
            'xtp_buffer_size': self.xtp_buffer_size,
            'xtp_td_ip': self.xtp_td_ip,
            'xtp_td_port': self.xtp_td_port,
            'binance_api_key': self.binance_api_key,
            'binance_secret_key': self.binance_secret_key,
            'binance_rest_url': self.binance_rest_url,
            'binance_ws_url': self.binance_ws_url,
            'binance_futures_api_key': self.binance_futures_api_key,
            'binance_futures_secret_key': self.binance_futures_secret_key,
            'binance_futures_rest_url': self.binance_futures_rest_url,
            'binance_futures_ws_url': self.binance_futures_ws_url,
            'okx_api_key': self.okx_api_key,
            'okx_secret_key': self.okx_secret_key,
            'okx_passphrase': self.okx_passphrase,
            'okx_rest_url': self.okx_rest_url,
            'okx_ws_url': self.okx_ws_url,
            'okx_futures_api_key': self.okx_futures_api_key,
            'okx_futures_secret_key': self.okx_futures_secret_key,
            'okx_futures_passphrase': self.okx_futures_passphrase,
            'okx_futures_rest_url': self.okx_futures_rest_url,
            'okx_futures_ws_url': self.okx_futures_ws_url,
            'huobi_api_key': self.huobi_api_key,
            'huobi_secret_key': self.huobi_secret_key,
            'huobi_rest_url': self.huobi_rest_url,
            'huobi_ws_url': self.huobi_ws_url,
            'huobi_futures_api_key': self.huobi_futures_api_key,
            'huobi_futures_secret_key': self.huobi_futures_secret_key,
            'huobi_futures_rest_url': self.huobi_futures_rest_url,
            'huobi_futures_ws_url': self.huobi_futures_ws_url,
            'bitget_api_key': self.bitget_api_key,
            'bitget_secret_key': self.bitget_secret_key,
            'bitget_passphrase': self.bitget_passphrase,
            'bitget_rest_url': self.bitget_rest_url,
            'bitget_ws_url': self.bitget_ws_url,
            'bybit_api_key': self.bybit_api_key,
            'bybit_secret_key': self.bybit_secret_key,
            'bybit_rest_url': self.bybit_rest_url,
            'bybit_ws_url': self.bybit_ws_url,
            'miniqmt_account_id': self.miniqmt_account_id,
            'miniqmt_password': self.miniqmt_password,
            'miniqmt_ip': self.miniqmt_ip,
            'miniqmt_port': self.miniqmt_port,
            'trading_interface': self.trading_interface
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Account':
        """从字典创建"""
        return cls(
            account_id=data['account_id'],
            account_name=data['account_name'],
            account_type=data['account_type'],
            status=AccountStatus(data['status']),
            balance=data['balance'],
            available_balance=data['available_balance'],
            frozen_balance=data['frozen_balance'],
            market_value=data['market_value'],
            total_assets=data['total_assets'],
            profit_loss=data['profit_loss'],
            profit_loss_ratio=data['profit_loss_ratio'],
            create_time=datetime.fromisoformat(data['create_time']),
            update_time=datetime.fromisoformat(data['update_time']),
            user_id=data.get('user_id', 'system'),
            trading_day=data.get('trading_day', ''),
            risk_level=data.get('risk_level', 'normal'),
            margin_ratio=data.get('margin_ratio', 0.0),
            maintenance_margin=data.get('maintenance_margin', 0.0),
            metadata=data.get('metadata', {}),
            institution_name=data.get('institution_name', ''),
            institution_type=InstitutionType(data.get('institution_type', InstitutionType.BROKER.value)),
            trading_interface_type=TradingInterfaceType(data.get('trading_interface_type', TradingInterfaceType.MOCK.value)),
            ctp_broker_id=data.get('ctp_broker_id', ''),
            ctp_investor_id=data.get('ctp_investor_id', ''),
            ctp_password=data.get('ctp_password', ''),
            ctp_trade_front=data.get('ctp_trade_front', ''),
            ctp_quote_front=data.get('ctp_quote_front', ''),
            ctp_app_id=data.get('ctp_app_id', ''),
            ctp_auth_code=data.get('ctp_auth_code', ''),
            ctp_product_info=data.get('ctp_product_info', ''),
            xtp_account_id=data.get('xtp_account_id', ''),
            xtp_password=data.get('xtp_password', ''),
            xtp_server_address=data.get('xtp_server_address', ''),
            xtp_client_id=data.get('xtp_client_id', 0),
            xtp_software_key=data.get('xtp_software_key', ''),
            xtp_md_ip=data.get('xtp_md_ip', ''),
            xtp_md_port=data.get('xtp_md_port', 0),
            xtp_protocol=data.get('xtp_protocol', 'tcp'),
            xtp_buffer_size=data.get('xtp_buffer_size', 0),
            xtp_td_ip=data.get('xtp_td_ip', ''),
            xtp_td_port=data.get('xtp_td_port', 0),
            binance_api_key=data.get('binance_api_key', ''),
            binance_secret_key=data.get('binance_secret_key', ''),
            binance_rest_url=data.get('binance_rest_url', 'https://api.binance.com'),
            binance_ws_url=data.get('binance_ws_url', 'wss://stream.binance.com:9443'),
            binance_futures_api_key=data.get('binance_futures_api_key', ''),
            binance_futures_secret_key=data.get('binance_futures_secret_key', ''),
            binance_futures_rest_url=data.get('binance_futures_rest_url', 'https://fapi.binance.com'),
            binance_futures_ws_url=data.get('binance_futures_ws_url', 'wss://fstream.binance.com'),
            okx_api_key=data.get('okx_api_key', ''),
            okx_secret_key=data.get('okx_secret_key', ''),
            okx_passphrase=data.get('okx_passphrase', ''),
            okx_rest_url=data.get('okx_rest_url', 'https://www.okx.com'),
            okx_ws_url=data.get('okx_ws_url', 'wss://ws.okx.com:8443'),
            okx_futures_api_key=data.get('okx_futures_api_key', ''),
            okx_futures_secret_key=data.get('okx_futures_secret_key', ''),
            okx_futures_passphrase=data.get('okx_futures_passphrase', ''),
            okx_futures_rest_url=data.get('okx_futures_rest_url', 'https://www.okx.com'),
            okx_futures_ws_url=data.get('okx_futures_ws_url', 'wss://ws.okx.com:8443'),
            huobi_api_key=data.get('huobi_api_key', ''),
            huobi_secret_key=data.get('huobi_secret_key', ''),
            huobi_rest_url=data.get('huobi_rest_url', 'https://api.huobi.pro'),
            huobi_ws_url=data.get('huobi_ws_url', 'wss://api.huobi.pro/ws'),
            huobi_futures_api_key=data.get('huobi_futures_api_key', ''),
            huobi_futures_secret_key=data.get('huobi_futures_secret_key', ''),
            huobi_futures_rest_url=data.get('huobi_futures_rest_url', 'https://api.hbdm.com'),
            huobi_futures_ws_url=data.get('huobi_futures_ws_url', 'wss://api.hbdm.com/ws'),
            bitget_api_key=data.get('bitget_api_key', ''),
            bitget_secret_key=data.get('bitget_secret_key', ''),
            bitget_passphrase=data.get('bitget_passphrase', ''),
            bitget_rest_url=data.get('bitget_rest_url', 'https://api.bitget.com'),
            bitget_ws_url=data.get('bitget_ws_url', 'wss://ws.bitget.com'),
            bybit_api_key=data.get('bybit_api_key', ''),
            bybit_secret_key=data.get('bybit_secret_key', ''),
            bybit_rest_url=data.get('bybit_rest_url', 'https://api.bybit.com'),
            bybit_ws_url=data.get('bybit_ws_url', 'wss://stream.bybit.com'),
            miniqmt_account_id=data.get('miniqmt_account_id', ''),
            miniqmt_password=data.get('miniqmt_password', ''),
            miniqmt_ip=data.get('miniqmt_ip', '127.0.0.1'),
            miniqmt_port=data.get('miniqmt_port', 58610),
            trading_interface=data.get('trading_interface', '')
        )


@dataclass
class Position:
    """持仓信息"""
    position_id: str
    account_id: str
    asset_type: AssetType
    stock_code: str
    stock_name: str
    side: PositionSide
    quantity: int
    available_quantity: int
    open_price: float
    current_price: float
    market_value: float
    cost_price: float
    cost_value: float
    profit_loss: float
    profit_loss_ratio: float
    open_time: datetime
    update_time: datetime
    commission: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_long(self) -> bool:
        """是否为多头持仓"""
        return self.side == PositionSide.LONG

    @property
    def is_short(self) -> bool:
        """是否为空头持仓"""
        return self.side == PositionSide.SHORT

    @property
    def unrealized_pnl(self) -> float:
        """浮动盈亏 = (当前价 - 成本价) * 持仓数量"""
        if self.side == PositionSide.LONG:
            return (self.current_price - self.cost_price) * self.quantity
        return (self.cost_price - self.current_price) * self.quantity

    @property
    def realized_pnl(self) -> float:
        """已实现盈亏（当前记录值与浮动盈亏的差值）"""
        return self.profit_loss - self.unrealized_pnl

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'position_id': self.position_id,
            'account_id': self.account_id,
            'asset_type': self.asset_type.value,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'side': self.side.value,
            'quantity': self.quantity,
            'available_quantity': self.available_quantity,
            'open_price': self.open_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'cost_price': self.cost_price,
            'cost_value': self.cost_value,
            'profit_loss': self.profit_loss,
            'profit_loss_ratio': self.profit_loss_ratio,
            'open_time': self.open_time.isoformat(),
            'update_time': self.update_time.isoformat(),
            'commission': self.commission,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """从字典创建"""
        return cls(
            position_id=data['position_id'],
            account_id=data['account_id'],
            asset_type=AssetType(data['asset_type']),
            stock_code=data['stock_code'],
            stock_name=data['stock_name'],
            side=PositionSide(data['side']),
            quantity=data['quantity'],
            available_quantity=data['available_quantity'],
            open_price=data['open_price'],
            current_price=data['current_price'],
            market_value=data['market_value'],
            cost_price=data['cost_price'],
            cost_value=data['cost_value'],
            profit_loss=data['profit_loss'],
            profit_loss_ratio=data['profit_loss_ratio'],
            open_time=datetime.fromisoformat(data['open_time']),
            update_time=datetime.fromisoformat(data['update_time']),
            commission=data.get('commission', 0.0),
            metadata=data.get('metadata', {})
        )


@dataclass
class FundInfo:
    """资金信息"""
    account_id: str
    total_balance: float
    available_balance: float
    frozen_balance: float
    market_value: float
    total_assets: float
    profit_loss: float
    profit_loss_ratio: float
    margin_used: float
    margin_available: float
    maintenance_margin: float
    update_time: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def margin_ratio(self) -> float:
        """保证金比例"""
        if self.total_assets > 0:
            return self.margin_used / self.total_assets
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'account_id': self.account_id,
            'total_balance': self.total_balance,
            'available_balance': self.available_balance,
            'frozen_balance': self.frozen_balance,
            'market_value': self.market_value,
            'total_assets': self.total_assets,
            'profit_loss': self.profit_loss,
            'profit_loss_ratio': self.profit_loss_ratio,
            'margin_used': self.margin_used,
            'margin_available': self.margin_available,
            'maintenance_margin': self.maintenance_margin,
            'update_time': self.update_time.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FundInfo':
        """从字典创建"""
        return cls(
            account_id=data['account_id'],
            total_balance=data['total_balance'],
            available_balance=data['available_balance'],
            frozen_balance=data['frozen_balance'],
            market_value=data['market_value'],
            total_assets=data['total_assets'],
            profit_loss=data['profit_loss'],
            profit_loss_ratio=data['profit_loss_ratio'],
            margin_used=data['margin_used'],
            margin_available=data['margin_available'],
            maintenance_margin=data['maintenance_margin'],
            update_time=datetime.fromisoformat(data['update_time']),
            metadata=data.get('metadata', {})
        )


@dataclass
class AccountQuery:
    """账户查询条件"""
    account_id: Optional[str] = None
    user_id: Optional[str] = None
    account_type: Optional[str] = None
    status: Optional[AccountStatus] = None
    limit: int = 100
    offset: int = 0
    sort_by: str = "update_time"
    sort_order: str = "desc"


@dataclass
class PositionQuery:
    """持仓查询条件"""
    account_id: Optional[str] = None
    asset_type: Optional[AssetType] = None
    stock_code: Optional[str] = None
    side: Optional[PositionSide] = None
    limit: int = 100
    offset: int = 0
    sort_by: str = "update_time"
    sort_order: str = "desc"
