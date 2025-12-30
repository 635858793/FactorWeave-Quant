"""
数据模型定义

定义标准的数据结构，用于在不同层之间传递数据。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd

@dataclass
class StockInfo:
    """股票基本信息"""
    code: str                    # 股票代码
    name: str                    # 股票名称
    market: str                  # 市场（sh/sz）
    industry: Optional[str] = None      # 行业
    sector: Optional[str] = None        # 板块
    list_date: Optional[datetime] = None  # 上市日期
    market_cap: Optional[float] = None   # 市值
    pe_ratio: Optional[float] = None     # 市盈率
    pb_ratio: Optional[float] = None     # 市净率
    is_favorite: bool = False           # 是否为自选股

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'market': self.market,
            'industry': self.industry,
            'sector': self.sector,
            'list_date': self.list_date,
            'market_cap': self.market_cap,
            'pe_ratio': self.pe_ratio,
            'pb_ratio': self.pb_ratio
        }

@dataclass
class KlineData:
    """K线数据"""
    stock_code: str              # 股票代码
    period: str                  # 周期（1m/5m/15m/30m/1H/D/W/M）
    data: pd.DataFrame           # K线数据（OHLCV）
    start_date: Optional[datetime] = None  # 开始日期
    end_date: Optional[datetime] = None    # 结束日期
    count: Optional[int] = None           # 数据条数

    def __post_init__(self):
        """数据验证"""
        if self.data is not None and not self.data.empty:
            # 确保必要的列存在
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = [
                col for col in required_columns if col not in self.data.columns]
            if missing_columns:
                raise ValueError(
                    f"Missing required columns: {missing_columns}")

            # 自动设置开始和结束日期
            if self.start_date is None and 'datetime' in self.data.columns:
                self.start_date = self.data['datetime'].min()
            if self.end_date is None and 'datetime' in self.data.columns:
                self.end_date = self.data['datetime'].max()
            if self.count is None:
                self.count = len(self.data)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'stock_code': self.stock_code,
            'period': self.period,
            'data': self.data.to_dict('records') if self.data is not None else [],
            'start_date': self.start_date,
            'end_date': self.end_date,
            'count': self.count
        }

@dataclass
class MarketData:
    """市场数据"""
    date: datetime               # 日期
    index_code: str             # 指数代码
    index_name: str             # 指数名称
    open: float                 # 开盘价
    high: float                 # 最高价
    low: float                  # 最低价
    close: float                # 收盘价
    volume: float               # 成交量
    amount: float               # 成交额
    change: Optional[float] = None       # 涨跌额
    change_pct: Optional[float] = None   # 涨跌幅

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'date': self.date,
            'index_code': self.index_code,
            'index_name': self.index_name,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'change': self.change,
            'change_pct': self.change_pct
        }

@dataclass
class QueryParams:
    """查询参数（✅ 优化：支持多资产类型）"""
    stock_code: str
    period: str = 'D'
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    count: Optional[int] = None
    asset_type: Optional['AssetType'] = None  # ✅ 新增：资产类型（默认None表示股票）

    def validate(self) -> bool:
        """验证参数"""
        if not self.stock_code:
            return False

        # 转换中文期间参数到英文
        self.period = self._normalize_period(self.period)

        if self.period not in ['1m', '5m', '15m', '30m', '1H', 'D', 'W', 'M']:
            return False
        
        # ✅ 验证asset_type（如果提供）
        if self.asset_type is not None:
            from core.plugin_types import AssetType
            if not isinstance(self.asset_type, AssetType):
                return False
        
        return True

    def _normalize_period(self, period: str) -> str:
        """标准化期间参数"""
        period_mapping = {
            '日线': 'D',
            '日': 'D',
            'D': 'D',
            '1d': 'D',
            '周线': 'W',
            '周': 'W',
            'W': 'W',
            '月线': 'M',
            '月': 'M',
            'M': 'M',
            '1分钟': '1m',
            '1分': '1m',
            '1m': '1m',
            '5分钟': '5m',
            '5分': '5m',
            '5m': '5m',
            '15分钟': '15m',
            '15分': '15m',
            '15m': '15m',
            '30分钟': '30m',
            '30分': '30m',
            '30m': '30m',
            '1小时': '1H',
            '小时': '1H',
            '1H': '1H'
        }
        return period_mapping.get(period, period)
