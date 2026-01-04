from loguru import logger
"""
传统数据源适配器

将基于DataSource基类的传统数据源（东方财富、新浪、同花顺等）
适配为符合IDataSourcePlugin接口的插件，以便集成到TET数据管道中。
"""

import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from abc import ABC

from ..data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult, ConnectionInfo
from ..plugin_types import AssetType, DataType
from ..data_source import DataSource


class LegacyDataSourceAdapter(IDataSourcePlugin):
    """
    传统数据源适配器

    将基于DataSource基类的传统数据源适配为IDataSourcePlugin接口
    """

    def __init__(self, legacy_source: DataSource, source_id: str):
        """
        初始化适配器

        Args:
            legacy_source: 传统数据源实例
            source_id: 数据源标识
        """
        self.legacy_source = legacy_source
        self.source_id = source_id

        # 映射传统数据源类型到新的资产类型 - 支持多资产类型
        self._asset_type_mapping = {
            'eastmoney': [
                AssetType.STOCK_A, AssetType.STOCK_B, AssetType.STOCK_H,
                AssetType.INDEX, AssetType.FUND, AssetType.BOND
            ],
            'sina': [AssetType.STOCK_A],
            'tonghuashun': [AssetType.STOCK_A]
        }

        # 支持的数据类型
        self._supported_data_types = [
            DataType.HISTORICAL_KLINE,
            DataType.REAL_TIME_QUOTE,
            DataType.ASSET_LIST
        ]

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            id=self.source_id,
            name=f"传统数据源-{self.source_id}",
            version="1.0.0",
            description=f"传统{self.source_id}数据源的适配器",
            author="FactorWeave-Quant Team",
            supported_asset_types=self._asset_type_mapping.get(self.source_id, [AssetType.STOCK_A]),
            supported_data_types=self._supported_data_types,
            capabilities={
                "markets": ["SH", "SZ"],
                "frequencies": ["1m", "5m", "15m", "30m", "60m", "D", "W", "M"],
                "real_time_support": True,
                "historical_data": True
            }
        )

    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        try:
            if hasattr(self.legacy_source, 'connect'):
                result = self.legacy_source.connect()
                if result:
                    logger.info(f"传统数据源 {self.source_id} 连接成功")
                else:
                    logger.warning(f"传统数据源 {self.source_id} 连接失败")
                return result
            else:
                # 对于没有connect方法的传统数据源，假设总是连接成功
                logger.info(f"传统数据源 {self.source_id} 假设连接成功（无connect方法）")
                return True
        except Exception as e:
            logger.error(f"传统数据源 {self.source_id} 连接异常: {e}")
            return False

    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if hasattr(self.legacy_source, 'disconnect'):
                result = self.legacy_source.disconnect()
                logger.info(f"传统数据源 {self.source_id} 断开连接")
                return result
            else:
                logger.info(f"传统数据源 {self.source_id} 假设断开成功（无disconnect方法）")
                return True
        except Exception as e:
            logger.error(f"传统数据源 {self.source_id} 断开连接异常: {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        try:
            if hasattr(self.legacy_source, 'is_connected'):
                return self.legacy_source.is_connected()
            elif hasattr(self.legacy_source, '_running'):
                return self.legacy_source._running
            else:
                # 对于没有连接状态检查的传统数据源，假设总是连接
                return True
        except Exception as e:
            logger.error(f"检查传统数据源 {self.source_id} 连接状态异常: {e}")
            return False

    def get_connection_info(self) -> ConnectionInfo:
        """获取连接信息"""
        return ConnectionInfo(
            is_connected=self.is_connected(),
            connection_time=datetime.now(),
            last_activity=datetime.now(),
            connection_params={
                'source_type': str(self.legacy_source.source_type) if hasattr(self.legacy_source, 'source_type') else 'unknown',
                'adapter_type': 'legacy'
            }
        )

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            is_healthy = self.is_connected()
            return HealthCheckResult(
                is_healthy=is_healthy,
                message="传统数据源健康" if is_healthy else "传统数据源不健康",
                response_time=0.0,
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthCheckResult(
                is_healthy=False,
                message=f"健康检查异常: {str(e)}",
                response_time=0.0,
                timestamp=datetime.now()
            )

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        try:
            # 尝试调用传统数据源的股票列表方法
            if hasattr(self.legacy_source, 'get_stock_list'):
                stock_list = self.legacy_source.get_stock_list(market=market)
                if isinstance(stock_list, pd.DataFrame):
                    return stock_list.to_dict('records')
                elif isinstance(stock_list, list):
                    return stock_list
                else:
                    return []
            elif hasattr(self.legacy_source, 'get_all_stocks'):
                stock_list = self.legacy_source.get_all_stocks()
                if isinstance(stock_list, pd.DataFrame):
                    return stock_list.to_dict('records')
                elif isinstance(stock_list, list):
                    return stock_list
                else:
                    return []
            else:
                # 返回空列表，表示不支持股票列表获取
                logger.debug(f"传统数据源 {self.source_id} 不支持获取股票列表")
                return []
        except Exception as e:
            logger.error(f"传统数据源 {self.source_id} 获取资产列表异常: {e}")
            return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None) -> pd.DataFrame:
        """获取K线数据"""
        try:
            # 尝试调用传统数据源的K线数据方法
            if hasattr(self.legacy_source, 'get_kdata'):
                return self.legacy_source.get_kdata(
                    symbol=symbol,
                    freq=freq,
                    start_date=start_date,
                    end_date=end_date,
                    count=count
                )
            elif hasattr(self.legacy_source, 'get_historical_data'):
                return self.legacy_source.get_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                logger.warning(f"传统数据源 {self.source_id} 不支持获取K线数据")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"传统数据源 {self.source_id} 获取K线数据异常: {e}")
            return pd.DataFrame()

    def get_real_time_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情"""
        try:
            # 尝试调用传统数据源的实时行情方法
            if hasattr(self.legacy_source, 'get_real_time_quotes'):
                quotes = self.legacy_source.get_real_time_quotes(symbols)
                if isinstance(quotes, pd.DataFrame):
                    return quotes
                elif isinstance(quotes, dict):
                    return pd.DataFrame([quotes])
                else:
                    return pd.DataFrame()
            elif hasattr(self.legacy_source, 'get_quote'):
                # 单个股票行情获取
                quotes_list = []
                for symbol in symbols:
                    try:
                        quote = self.legacy_source.get_quote(symbol)
                        if quote:
                            quotes_list.append(quote)
                    except Exception as e:
                        logger.warning(f"获取 {symbol} 实时行情失败: {e}")
                        continue
                return pd.DataFrame(quotes_list)
            else:
                logger.warning(f"传统数据源 {self.source_id} 不支持获取实时行情")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"传统数据源 {self.source_id} 获取实时行情异常: {e}")
            return pd.DataFrame()

    def get_supported_frequencies(self) -> List[str]:
        """获取支持的频率列表"""
        return ["1m", "5m", "15m", "30m", "60m", "D", "W", "M"]

    def get_supported_markets(self) -> List[str]:
        """获取支持的市场列表"""
        return ["SH", "SZ"]

    def validate_symbol(self, symbol: str, asset_type: AssetType = None) -> bool:
        """验证交易代码是否有效"""
        # 简单的A股代码验证
        if len(symbol) == 6 and symbol.isdigit():
            return True
        return False

    def normalize_symbol(self, symbol: str, asset_type: AssetType = None) -> str:
        """标准化交易代码"""
        # 移除可能的市场前缀
        if '.' in symbol:
            symbol = symbol.split('.')[0]
        return symbol.zfill(6)  # 确保6位数字

    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式"""
        return {
            'type': 'object',
            'properties': {
                'timeout': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 60,
                    'default': 30,
                    'title': '请求超时时间(秒)'
                }
            }
        }

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """验证配置"""
        return True, ""

    def update_config(self, config: Dict[str, Any]) -> bool:
        """更新配置"""
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "last_request_time": None,
            "uptime": 0.0,
            "adapter_type": "legacy",
            "source_id": self.source_id
        }
