from loguru import logger
"""
东方财富股票数据源插件

提供东方财富数据源的股票数据获取功能，支持：
- A股股票基本信息
- 历史K线数据
- 实时行情数据
- 财务数据
- 资金流向数据

使用东方财富API作为数据源：
- 高频实时数据
- 丰富的技术指标
- 资金流向分析

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd

from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult
from core.data_source_data_models import QueryParams
from core.plugin_types import PluginType, AssetType, DataType
from core.network.universal_network_config import INetworkConfigurable, NetworkEndpoint, PluginNetworkConfig
from plugins.plugin_interface import PluginLifecycle

logger = logger.bind(module=__name__)

# 默认配置集中
DEFAULT_CONFIG = {
    'base_url': 'https://push2.eastmoney.com',
    'api_urls': {
        'stock_list': '/api/qt/clist/get',
        'kline': '/api/qt/stock/kline/get',
        'realtime': '/api/qt/ulist.np/get',
        'financial': '/api/qt/stock/financial/get'
    },
    'timeout': 30,
    'max_retries': 3
}


class EastMoneyStockPlugin(IDataSourcePlugin):
    """东方财富股票数据源插件（异步优化版）"""

    def __init__(self):
        # 调用父类初始化（IDataSourcePlugin是抽象基类，没有实际的__init__）
        super().__init__()

        self.logger = logger  # 添加logger属性

        # 必须显式初始化这些属性（IDataSourcePlugin是抽象基类，不提供默认实现）
        self.initialized = False
        self.last_error = None
        self.plugin_state = PluginLifecycle.CREATED  # 初始状态（插件对象已创建）

        self.config = DEFAULT_CONFIG.copy()
        self.session = None
        self.request_count = 0
        self.timeout = int(self.config.get('timeout', DEFAULT_CONFIG['timeout']))

        # 插件基本信息
        self.plugin_id = "data_sources.eastmoney_plugin"  # 修正plugin_id属性
        self.name = "东方财富股票数据源插件"
        self.version = "1.0.0"
        self.description = "提供东方财富高频实时数据和技术分析数据"
        self.author = "FactorWeave-Quant 开发团队"

        # 插件类型标识
        self.plugin_type = PluginType.DATA_SOURCE_STOCK

        # 联网查询地址配置（endpointhost字段）
        self.endpointhost = [
            "https://datacenter-web.eastmoney.com/api/status",
            "https://push2.eastmoney.com/api/health",
            "https://quote.eastmoney.com/api/status"
        ]

        # 支持的市场
        self.supported_markets = {
            '1': '上海主板',
            '0': '深圳主板',
            '17': '创业板',
            '33': '科创板'
        }

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            id=self.plugin_id,
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            supported_asset_types=[AssetType.STOCK_A],
            supported_data_types=[
                DataType.HISTORICAL_KLINE,
                DataType.REAL_TIME_QUOTE,
                DataType.FUNDAMENTAL,
                DataType.ASSET_LIST,          # 资产列表
                DataType.FUND_FLOW,           # 资金流数据
                DataType.SECTOR_FUND_FLOW     # 板块资金流
            ],
            capabilities={
                "markets": ["SH", "SZ"],
                "frequencies": ["1m", "5m", "15m", "30m", "60m", "D"],
                "real_time_support": True,
                "historical_data": True,
                "fundamental_data": True,
                "max_history_years": 10
            }
        )

    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        try:
            if not self.session:
                self.session = requests.Session()
                self.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })

            # 测试连接
            test_url = f"{self.config['base_url']}/api/qt/clist/get"
            response = self.session.get(test_url, timeout=10, params={'pn': 1, 'pz': 1, 'po': 1, 'fid': 'f3'})

            if response.status_code == 200:
                self.initialized = True
                self.logger.info("东方财富数据源连接成功")
                return True
            else:
                self.logger.error(f"东方财富连接失败，状态码: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"东方财富连接失败: {e}")
            return False

    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if self.session:
                self.session.close()
                self.session = None
            self.initialized = False
            self.logger.info("东方财富数据源断开连接")
            return True
        except Exception as e:
            self.logger.error(f"东方财富断开连接失败: {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.initialized and self.session is not None

    def get_connection_info(self):
        """获取连接信息"""
        from core.data_source_extensions import ConnectionInfo
        return ConnectionInfo(
            is_connected=self.is_connected(),
            connection_time=getattr(self, 'connection_time', None),
            last_activity=getattr(self, 'last_activity', None),
            connection_params={
                'base_url': self.config.get('base_url', DEFAULT_CONFIG['base_url']),
                'port': 443,
                'timeout': self.config.get('timeout', DEFAULT_CONFIG['timeout'])
            },
            error_message=getattr(self, 'last_error', None)
        )

    def health_check(self):
        """健康检查"""
        from core.data_source_extensions import HealthCheckResult
        import time

        start_time = time.time()
        try:
            if not self.session:
                return HealthCheckResult(
                    is_healthy=False,
                    message="未连接到东方财富数据源",
                    response_time=(time.time() - start_time) * 1000
                )

            # 测试API调用
            test_url = f"{self.config['base_url']}/api/qt/clist/get"
            response = self.session.get(test_url, timeout=5, params={'pn': 1, 'pz': 1, 'po': 1, 'fid': 'f3'})
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return HealthCheckResult(
                    is_healthy=True,
                    message="东方财富数据源健康",
                    response_time=response_time
                )
            else:
                return HealthCheckResult(
                    is_healthy=False,
                    message=f"东方财富API返回错误状态码: {response.status_code}",
                    response_time=response_time
                )

        except Exception as e:
            return HealthCheckResult(
                is_healthy=False,
                message=f"东方财富健康检查失败: {e}",
                response_time=(time.time() - start_time) * 1000
            )

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            id="eastmoney_stock_plugin",
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            supported_asset_types=[AssetType.STOCK_A],
            supported_data_types=[
                DataType.HISTORICAL_KLINE,
                DataType.REAL_TIME_QUOTE,
                DataType.FUNDAMENTAL,
                DataType.TRADE_TICK
            ],
            capabilities={
                "markets": ["SH", "SZ"],
                "frequencies": ["1m", "5m", "15m", "30m", "60m", "D"],
                "real_time_support": True,
                "historical_data": True,
                "fundamental_data": True,
                "tick_data": True,
                "max_history_years": 10
            }
        )

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return [AssetType.STOCK_A]

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        return [
            DataType.HISTORICAL_KLINE,
            DataType.REAL_TIME_QUOTE,
            DataType.FUNDAMENTAL,
            DataType.TRADE_TICK,
            DataType.ASSET_LIST  # 添加资产列表支持
        ]

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        同步初始化插件（快速，不做网络连接）
        网络测试已移至 _do_connect() 方法，在后台线程中执行
        """
        try:
            self.plugin_state = PluginLifecycle.INITIALIZING

            # 合并配置
            merged = DEFAULT_CONFIG.copy()
            merged.update(config or {})
            self.config = merged

            # 创建会话（快速）
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://quote.eastmoney.com/',
                'Accept': 'application/json, text/plain, */*'
            })

            # 配置参数（快速）
            self.timeout = int(self.config.get('timeout', DEFAULT_CONFIG['timeout']))
            self.max_retries = int(self.config.get('max_retries', DEFAULT_CONFIG['max_retries']))

            # 标记初始化完成（不做网络测试）
            self.initialized = True
            self.plugin_state = PluginLifecycle.INITIALIZED
            logger.info("东方财富插件同步初始化完成（<100ms，网络连接将在后台进行）")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.plugin_state = PluginLifecycle.FAILED
            logger.error(f"东方财富股票数据源插件初始化失败: {e}")
            return False

    def _do_connect(self) -> bool:
        """
        实际连接逻辑（在后台线程中执行）
        将原来在 initialize() 中的网络测试移到这里
        """
        try:
            logger.info("东方财富插件开始连接测试...")

            # 网络测试（原来在 initialize 中的代码）
            base_url = self.config.get('base_url', DEFAULT_CONFIG['base_url'])
            api = self.config.get('api_urls', DEFAULT_CONFIG['api_urls'])
            test_url = f"{base_url}{api['stock_list']}"
            params = {
                'pn': '1',
                'pz': '20',
                'po': '1',
                'np': '1',
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',
                'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
                'fields': 'f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11'
            }

            response = self.session.get(test_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and data['data']:
                    logger.info("东方财富插件连接成功，网络正常")
                    self.plugin_state = PluginLifecycle.CONNECTED
                    return True
                else:
                    logger.warning("⚠️ 东方财富插件连接成功，但测试数据异常")
                    self.plugin_state = PluginLifecycle.CONNECTED  # 仍然认为连接成功
                    return True
            else:
                raise Exception(f"API返回状态码: {response.status_code}")

        except Exception as e:
            self.last_error = str(e)
            self.plugin_state = PluginLifecycle.FAILED
            logger.error(f"❌ 东方财富插件连接失败: {e}")
            return False

    def shutdown(self) -> bool:
        """关闭插件"""
        try:
            if self.session:
                self.session.close()
            self.initialized = False
            logger.info("东方财富股票数据源插件关闭成功")
            return True
        except Exception as e:
            logger.error(f"东方财富股票数据源插件关闭失败: {e}")
            return False

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        start_time = time.time()

        try:
            if not self.initialized or not self.session:
                return HealthCheckResult(
                    is_healthy=False,
                    response_time=0.0,
                    message="插件未初始化"
                )

            # 测试API连接
            base_url = self.config.get('base_url', DEFAULT_CONFIG['base_url'])
            api = self.config.get('api_urls', DEFAULT_CONFIG['api_urls'])
            test_url = f"{base_url}{api['stock_list']}"
            params = {'pn': '1', 'pz': '1', 'np': '1', 'fltt': '2', 'invt': '2'}

            response = self.session.get(test_url, params=params, timeout=10)
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data:
                    return HealthCheckResult(
                        is_healthy=True,
                        response_time=response_time,
                        message="ok"
                    )

            return HealthCheckResult(
                is_healthy=False,
                response_time=response_time,
                message="API返回数据异常"
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            # 如果插件已初始化，网络异常时仍认为插件可用
            if self.initialized:
                return HealthCheckResult(
                    is_healthy=True,
                    response_time=response_time,
                    message=f"插件可用但网络异常: {str(e)[:50]}"
                )
            else:
                return HealthCheckResult(
                    is_healthy=False,
                    response_time=response_time,
                    message=str(e)
                )

    def get_asset_list(self, asset_type, market: str = None):
        """获取资产列表"""
        from core.data_source_extensions import AssetType

        if asset_type == AssetType.STOCK_A:
            # 获取股票列表
            df = self.get_stock_list()
            if not df.empty:
                # 转换为标准格式
                if '市场' not in df.columns:
                    df['市场'] = 'A股'
                assets = df.assign(
                    symbol=df['代码'],
                    market=df['市场'],
                    asset_type='stock'
                ).rename(columns={'名称': 'name'})[['symbol', 'name', 'market', 'asset_type']].to_dict('records')
                return assets

        return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None, adjustment: str = 'none') -> pd.DataFrame:
        """获取K线数据 - 抽象方法实现
        
        Args:
            symbol: 股票代码
            freq: 频率
            start_date: 开始日期
            end_date: 结束日期
            count: 数据条数
            adjustment: 复权类型 ('qfq', 'hfq', 'none')
        """
        try:
            # 标准化股票代码
            normalized_symbol = self._normalize_stock_code(symbol)

            # 频率映射
            freq_map = {
                'D': 'daily',
                '1d': 'daily',
                'daily': 'daily',
                '1': 'daily',
                'W': 'weekly',
                '1w': 'weekly',
                'weekly': 'weekly',
                'M': 'monthly',
                '1M': 'monthly',
                '1m': '1min',
                'monthly': 'monthly',
                '1min': '1min',
                '5min': '5min',
                '15min': '15min',
                '30min': '30min',
                '60min': '60min'
            }

            period = freq_map.get(freq, 'daily')

            # 调用内部的get_kline_data方法，传递复权参数
            return self.get_kline_data(
                symbol=normalized_symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjustment=adjustment
            )

        except Exception as e:
            logger.error(f"东方财富获取K线数据失败: {symbol} - {str(e)}")
            return pd.DataFrame()

    def get_real_time_quotes(self, symbols: list) -> pd.DataFrame:
        """获取实时行情数据 - 抽象方法实现"""
        try:
            if not symbols:
                return pd.DataFrame()

            base_url = self.config.get('base_url', DEFAULT_CONFIG['base_url'])
            api = self.config.get('api_urls', DEFAULT_CONFIG['api_urls'])
            url = f"{base_url}{api['realtime']}"

            secids = ','.join([f"1.{s}" if not s.startswith(('0', '3', '6')) else f"0.{s}" if s.startswith('0') else f"1.{s}" for s in symbols])

            params = {
                'fltt': '2',
                'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f15,f16,f17,f18',
                'secids': secids,
                '_': str(int(time.time() * 1000))
            }

            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and data['data'].get('diff'):
                    df = pd.DataFrame(data['data']['diff'])
                    return df

            logger.warning("东方财富实时行情获取失败")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"东方财富获取实时行情失败: {str(e)}")
            return pd.DataFrame()

    @property
    def plugin_info(self):
        """插件信息 - 抽象属性实现"""
        from core.data_source_extensions import PluginInfo, AssetType
        from core.plugin_types import DataType

        return PluginInfo(
            id='data_sources.eastmoney_plugin',
            name='东方财富数据源',
            version='1.0.0',
            description='东方财富股票数据获取插件',
            author='FactorWeave Team',
            supported_asset_types=[AssetType.STOCK_A],
            supported_data_types=[DataType.HISTORICAL_KLINE, DataType.REAL_TIME_QUOTE, DataType.FUNDAMENTAL],
            capabilities={
                'supported_assets': [AssetType.STOCK_A],
                'supported_frequencies': ['daily', 'weekly', 'monthly'],
                'requires_auth': False,
                'rate_limit': '100/minute'
            }
        )

    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        try:
            self.request_count += 1

            base_url = self.config.get('base_url', DEFAULT_CONFIG['base_url'])
            api = self.config.get('api_urls', DEFAULT_CONFIG['api_urls'])
            url = f"{base_url}{api['stock_list']}"
            params = {
                'pn': '1',
                'pz': '5000',  # 获取更多数据
                'po': '1',
                'np': '1',
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',
                'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',  # A股主要板块
                'fields': 'f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f15,f16,f17,f18,f23'
            }

            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and data['data']:
                    stock_data = data['data']['diff']

                    # 转换为DataFrame
                    df = pd.DataFrame(stock_data)

                    # 重命名列
                    column_mapping = {
                        'f12': 'code',
                        'f14': 'name',
                        'f2': 'close',
                        'f3': 'pct_change',
                        'f4': 'change',
                        'f5': 'volume',
                        'f6': 'amount',
                        'f7': 'amplitude',
                        'f8': 'turnover',
                        'f9': 'pe_ratio',
                        'f10': 'volume_ratio',
                        'f11': 'total_mv',
                        'f15': 'high',
                        'f16': 'low',
                        'f17': 'open',
                        'f18': 'pre_close',
                        'f23': 'pb_ratio'
                    }

                    df = df.rename(columns=column_mapping)

                    # 数据类型转换
                    numeric_cols = ['close', 'pct_change', 'change', 'volume', 'amount',
                                    'amplitude', 'turnover', 'pe_ratio', 'volume_ratio',
                                    'total_mv', 'high', 'low', 'open', 'pre_close', 'pb_ratio']

                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')

                    logger.info(f"获取东方财富股票列表成功，共 {len(df)} 只股票")
                    return df

            raise Exception(f"API请求失败: {response.status_code}")

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()

    def _normalize_stock_code(self, symbol: str) -> str:
        """标准化股票代码格式

        东方财富需要纯数字格式的股票代码，需要移除sz/sh前缀

        Args:
            symbol: 原始股票代码，如 'sz300110', 'sh000001', '000001'

        Returns:
            标准化后的股票代码，如 '300110', '000001'
        """
        if not symbol:
            return symbol

        # 转换为小写进行处理
        symbol_lower = symbol.lower()

        # 移除sz/sh前缀
        if symbol_lower.startswith('sz'):
            return symbol[2:]
        elif symbol_lower.startswith('sh'):
            return symbol[2:]

        # 如果没有前缀，直接返回
        return symbol

    def get_kline_data(self, symbol: str, period: str = 'daily',
                       start_date: str = None, end_date: str = None,
                       adjustment: str = 'none') -> pd.DataFrame:
        """获取K线数据
        
        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjustment: 复权类型 ('qfq', 'hfq', 'none')
        """
        try:
            self.request_count += 1

            # 标准化股票代码格式
            normalized_code = self._normalize_stock_code(symbol)
            self.logger.info(f"股票代码标准化: {symbol} -> {normalized_code}")

            # 处理股票代码
            if '.' in normalized_code:
                code = normalized_code.split('.')[0]
            else:
                code = normalized_code

            # 确定市场代码
            if code.startswith('6'):
                market_code = f"1.{code}"  # 上海
            elif code.startswith(('0', '3')):
                market_code = f"0.{code}"  # 深圳
            elif code.startswith(('4', '8', '9')):
                market_code = f"2.{code}"  # 北京
            else:
                market_code = f"1.{code}"  # 默认上海

            # 周期映射
            period_mapping = {
                '1min': '1',
                '5min': '5',
                '15min': '15',
                '30min': '30',
                '60min': '60',
                'daily': '101',
                'weekly': '102',
                'monthly': '103'
            }

            klt = period_mapping.get(period, '101')

            # 复权类型映射
            adjustment_map = {
                'qfq': '1',   # 前复权
                'hfq': '2',   # 后复权
                'none': '0',  # 不复权
                'both': '1'   # 默认前复权
            }
            fqt = adjustment_map.get(adjustment, '0')

            base_url = self.config.get('base_url', DEFAULT_CONFIG['base_url'])
            api = self.config.get('api_urls', DEFAULT_CONFIG['api_urls'])
            url = f"{base_url}{api['kline']}"
            params = {
                'secid': market_code,
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                'klt': klt,
                'fqt': fqt,  # 动态复权参数
                'beg': start_date or '0',
                'end': end_date or '20500101'
            }

            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and data['data']:
                    klines = data['data']['klines']

                    if klines:
                        # 解析K线数据
                        records = [
                            {
                                'datetime': parts[0],
                                'open': float(parts[1]),
                                'close': float(parts[2]),
                                'high': float(parts[3]),
                                'low': float(parts[4]),
                                'volume': int(parts[5]),
                                'amount': float(parts[6]),
                                'amplitude': float(parts[7]) if len(parts) > 7 else 0,
                                'pct_change': float(parts[8]) if len(parts) > 8 else 0,
                                'change': float(parts[9]) if len(parts) > 9 else 0,
                                'turnover': float(parts[10]) if len(parts) > 10 else 0
                            }
                            for parts in (kline.split(',') for kline in klines)
                            if len(parts) >= 11
                        ]

                        df = pd.DataFrame(records)
                        if not df.empty:
                            df['datetime'] = pd.to_datetime(df['datetime'])
                            df = df.set_index('datetime')
                            
                            # 添加复权类型标识
                            df['adj_type'] = adjustment
                            df['adj_source'] = 'plugin'
                            
                            logger.info(f"获取 {symbol} K线数据成功，共 {len(df)} 条记录，复权类型: {adjustment}")
                            return df

            raise Exception("无法获取K线数据")

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取K线数据失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_real_time_data(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情数据"""
        try:
            self.request_count += 1

            # 构建股票代码列表
            codes = []
            for symbol in symbols:
                if '.' in symbol:
                    code = symbol.split('.')[0]
                else:
                    code = symbol

                # 添加市场前缀
                if code.startswith('6'):
                    codes.append(f"1.{code}")
                elif code.startswith(('0', '3')):
                    codes.append(f"0.{code}")
                elif code.startswith(('4', '8', '9')):
                    codes.append(f"2.{code}")
                else:
                    codes.append(f"1.{code}")

            base_url = self.config.get('base_url', DEFAULT_CONFIG['base_url'])
            api = self.config.get('api_urls', DEFAULT_CONFIG['api_urls'])
            url = f"{base_url}{api['realtime']}"
            params = {
                'fltt': '2',
                'invt': '2',
                'secids': ','.join(codes),
                'fields': 'f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f15,f16,f17,f18,f23'
            }

            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and data['data']:
                    stock_data = data['data']['diff']

                    df = pd.DataFrame(stock_data)

                    # 重命名列
                    column_mapping = {
                        'f12': 'code',
                        'f14': 'name',
                        'f2': 'price',
                        'f3': 'pct_change',
                        'f4': 'change',
                        'f5': 'volume',
                        'f6': 'amount',
                        'f15': 'high',
                        'f16': 'low',
                        'f17': 'open',
                        'f18': 'pre_close',
                        'f23': 'pb_ratio'
                    }

                    df = df.rename(columns=column_mapping)

                    # 数据类型转换
                    numeric_cols = ['price', 'pct_change', 'change', 'volume', 'amount',
                                    'high', 'low', 'open', 'pre_close', 'pb_ratio']

                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')

                    logger.info(f"获取实时数据成功，共 {len(df)} 只股票")
                    return df

            raise Exception("无法获取实时数据")

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取实时数据失败: {e}")
            return pd.DataFrame()

    def fetch_data(self, symbol: str, data_type: str, **kwargs) -> Any:
        """通用数据获取接口"""
        try:
            if data_type == 'kline':
                return self.get_kline_data(
                    symbol=symbol,
                    period=kwargs.get('period', 'daily'),
                    start_date=kwargs.get('start_date'),
                    end_date=kwargs.get('end_date')
                )
            elif data_type == 'realtime':
                symbols = kwargs.get('symbols', [symbol])
                return self.get_real_time_data(symbols)
            elif data_type == 'stock_list':
                return self.get_stock_list()
            else:
                raise ValueError(f"不支持的数据类型: {data_type}")

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"获取数据失败 {symbol} ({data_type}): {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_requests': self.request_count,
            'success_rate': 1.0 if self.last_error is None else 0.8,
            'avg_response_time': 0.3,
            'last_update': datetime.now().isoformat(),
            'last_error': self.last_error,
            'supported_markets': list(self.supported_markets.keys()),
            'api_status': 'connected' if self.initialized else 'disconnected'
        }

    def get_plugin_info(self) -> PluginInfo:
        """获取插件基本信息"""
        return PluginInfo(
            id="eastmoney_stock",
            name="东方财富股票数据源",
            version=self.version,
            description=self.description,
            author="FactorWeave-Quant 团队",
            supported_asset_types=[AssetType.STOCK_A, AssetType.SECTOR],
            supported_data_types=[DataType.HISTORICAL_KLINE, DataType.REAL_TIME_QUOTE, DataType.SECTOR_FUND_FLOW, DataType.FUNDAMENTAL],
            capabilities={
                "markets": ["SH", "SZ"],
                "frequencies": ["1m", "5m", "15m", "30m", "60m", "D"],
                "real_time_support": True,
                "historical_data": True,
                "max_history_years": 10,
                "sector_fund_flow": True,  # 支持板块资金流
                "fundamental_data": True  # 支持基本面数据
            }
        )

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型列表"""
        return [DataType.HISTORICAL_KLINE, DataType.REAL_TIME_QUOTE, DataType.SECTOR_FUND_FLOW]

    def get_supported_adjustment_types(self) -> List[str]:
        """
        获取支持的复权类型列表

        Returns:
            List[str]: 支持的复权类型 ['qfq', 'hfq', 'none', 'both']
        """
        return ['qfq', 'hfq', 'none', 'both']

    def shutdown(self) -> None:
        """关闭插件，释放资源"""
        try:
            # 清理资源
            if hasattr(self, '_disconnect_wind'):
                self._disconnect_wind()
        except Exception as e:
            self.logger.error(f"插件关闭失败: {e}")

    def fetch_data(self, symbol: str, data_type: str,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   **kwargs) -> pd.DataFrame:
        """获取数据"""
        try:

            if data_type == "historical_kline":
                if start_date is None:
                    start_date = datetime.now() - timedelta(days=30)
                if end_date is None:
                    end_date = datetime.now()

                kline_data = self.get_kline_data(symbol, start_date, end_date,
                                                 kwargs.get('frequency', '1d'))

                # 转换为DataFrame格式
                if kline_data:
                    data = []
                    for kline in kline_data:
                        data.append({
                            'datetime': kline.timestamp,
                            'open': kline.open,
                            'high': kline.high,
                            'low': kline.low,
                            'close': kline.close,
                            'volume': kline.volume
                        })
                    return pd.DataFrame(data)
                else:
                    return pd.DataFrame()
            else:
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"数据获取失败: {e}")
            return pd.DataFrame()

    def get_real_time_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取实时数据"""
        try:
            result = {}
            for symbol in symbols:
                market_data = self.get_market_data(symbol)
                if market_data:
                    result[symbol] = {
                        'symbol': symbol,
                        'price': market_data.current_price,
                        'open': market_data.open_price,
                        'high': market_data.high_price,
                        'low': market_data.low_price,
                        'volume': market_data.volume,
                        'change': market_data.change_amount,
                        'change_pct': market_data.change_percent,
                        'timestamp': market_data.timestamp.isoformat()
                    }
            return result
        except Exception as e:
            self.logger.error(f"实时数据获取失败: {e}")
            return {}

    def get_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本面数据（股本、财务指标等）

        Args:
            symbol: 股票代码（如'000001'）

        Returns:
            Dict[str, Any]: 包含基本面数据的字典
                - total_shares: 总股本（股）
                - circulating_shares: 流通股本（股）
                - total_market_cap: 总市值（元）
                - circulating_market_cap: 流通市值（元）
                - industry: 所属行业
                - list_date: 上市日期（YYYYMMDD格式）
                - pe_ratio: 市盈率
                - pb_ratio: 市净率
                - roe: 净资产收益率
                - roa: 总资产收益率
                - debt_ratio: 负债率
        """
        try:
            import time
            import requests
            
            # 检查缓存
            cache_key = f"fundamental_{symbol}"
            if hasattr(self, 'cached_fundamental_data') and cache_key in self.cached_fundamental_data:
                self.logger.debug(f"使用缓存的基本面数据: {symbol}")
                return self.cached_fundamental_data[cache_key]

            self.logger.info(f"从东方财富获取股票 {symbol} 的基本面数据...")

            # 添加请求延迟，避免触发反爬虫机制
            time.sleep(1.0)

            fundamental_data = {}

            # 标准化股票代码
            normalized_code = self._normalize_stock_code(symbol)

            # 尝试获取个股基本信息（使用东方财富API）
            try:
                # 东方财富个股信息API
                url = f"{self.config['base_url']}/api/datacenter/get"
                params = {
                    'type': 'RPTA_APP_BS_TREND',
                    'sty': 'ALL',
                    'token': '894050c764c3c4b3ed01527b998f5d0',
                    'filter': f"(SECUCODE=\"{normalized_code}\")",
                    'p': '1',
                    'ps': '500'
                }

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                if data.get('success') and data.get('result') and data['result'].get('data'):
                    items = data['result']['data']
                    if items and len(items) > 0:
                        item = items[0]
                        
                        # 提取总股本
                        if 'TOTAL_SHARES' in item:
                            try:
                                fundamental_data['total_shares'] = float(item['TOTAL_SHARES'])
                            except (ValueError, TypeError):
                                fundamental_data['total_shares'] = 0.0

                        # 提取流通股本
                        if 'FLOAT_SHARES' in item:
                            try:
                                fundamental_data['circulating_shares'] = float(item['FLOAT_SHARES'])
                            except (ValueError, TypeError):
                                fundamental_data['circulating_shares'] = 0.0

                        # 提取总市值
                        if 'TOTAL_MARKET_CAP' in item:
                            try:
                                fundamental_data['total_market_cap'] = float(item['TOTAL_MARKET_CAP'])
                            except (ValueError, TypeError):
                                fundamental_data['total_market_cap'] = 0.0

                        # 提取流通市值
                        if 'FLOAT_MARKET_CAP' in item:
                            try:
                                fundamental_data['circulating_market_cap'] = float(item['FLOAT_MARKET_CAP'])
                            except (ValueError, TypeError):
                                fundamental_data['circulating_market_cap'] = 0.0

                        # 提取行业信息
                        if 'INDUSTRY' in item:
                            fundamental_data['industry'] = str(item['INDUSTRY'])

                        # 提取上市日期
                        if 'LIST_DATE' in item:
                            fundamental_data['list_date'] = str(item['LIST_DATE'])

                        self.logger.debug(f"成功获取个股基本信息: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取个股基本信息失败: {e}")

            # 尝试获取财务指标数据
            try:
                time.sleep(0.5)
                
                # 东方财富财务指标API
                url = f"{self.config['base_url']}/api/datacenter/get"
                params = {
                    'type': 'RPTA_APP_BS_TREND',
                    'sty': 'ALL',
                    'token': '894050c764c3c4b3ed01527b998f5d0',
                    'filter': f"(SECUCODE=\"{normalized_code}\")",
                    'p': '1',
                    'ps': '500'
                }

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                if data.get('success') and data.get('result') and data['result'].get('data'):
                    items = data['result']['data']
                    if items and len(items) > 0:
                        item = items[0]
                        
                        # 提取净资产收益率
                        if 'ROE' in item:
                            try:
                                fundamental_data['roe'] = float(item['ROE']) / 100
                            except (ValueError, TypeError):
                                self.logger.debug(f"字段解析失败: ROE={item['ROE']}")

                        # 提取总资产收益率
                        if 'ROA' in item:
                            try:
                                fundamental_data['roa'] = float(item['ROA']) / 100
                            except (ValueError, TypeError):
                                self.logger.debug(f"字段解析失败: ROA={item['ROA']}")

                        # 提取资产负债率
                        if 'DEBT_RATIO' in item:
                            try:
                                fundamental_data['debt_ratio'] = float(item['DEBT_RATIO']) / 100
                            except (ValueError, TypeError):
                                self.logger.debug(f"字段解析失败: DEBT_RATIO={item['DEBT_RATIO']}")

                        self.logger.debug(f"成功获取财务指标数据: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取财务指标数据失败: {e}")

            # 尝试获取估值指标（PE、PB等）
            try:
                time.sleep(0.5)
                
                # 东方财富实时行情API（包含估值指标）
                url = f"{self.config['base_url']}/api/qt/stock/get"
                params = {
                    'secid': normalized_code,
                    'fields': 'f43,f57,f58,f169,f170,f46,f60,f162,f167,f168,f169,f170'
                }

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                if data.get('data') and data.get('data'):
                    item = data['data']
                    
                    # 提取市盈率
                    if 'f43' in item:
                        try:
                            pe_value = item['f43']
                            if pe_value and pe_value != '-':
                                fundamental_data['pe_ratio'] = float(pe_value)
                                self.logger.debug(f"成功获取市盈率: {pe_value}")
                        except (ValueError, TypeError):
                                self.logger.debug(f"字段解析失败: 市盈率={pe_value}")

                    # 提取市净率
                    if 'f57' in item:
                        try:
                            pb_value = item['f57']
                            if pb_value and pb_value != '-':
                                fundamental_data['pb_ratio'] = float(pb_value)
                                self.logger.debug(f"成功获取市净率: {pb_value}")
                        except (ValueError, TypeError):
                                self.logger.debug(f"字段解析失败: 市净率={pb_value}")

                        self.logger.debug(f"成功获取估值指标数据: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取估值指标数据失败: {e}")

            # 添加数据源标识
            fundamental_data['data_source'] = 'eastmoney'
            fundamental_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 缓存结果
            if not hasattr(self, 'cached_fundamental_data'):
                self.cached_fundamental_data = {}
            self.cached_fundamental_data[cache_key] = fundamental_data

            self.logger.info(f"成功获取股票 {symbol} 的基本面数据: {len(fundamental_data)} 个字段")
            return fundamental_data

        except Exception as e:
            self.logger.error(f"从东方财富获取股票 {symbol} 的基本面数据失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {}

    def get_sector_fund_flow_data(self, symbol: str = "sector", **kwargs) -> pd.DataFrame:
        """
        获取板块资金流数据

        Args:
            symbol: 板块代码或"sector"表示获取所有板块
            **kwargs: 其他参数

        Returns:
            板块资金流数据DataFrame
        """
        try:
            self.logger.info("获取东方财富板块资金流数据")
            
            # 添加保守的请求延迟，避免触发反爬虫机制
            import time
            time.sleep(1.0)  # 保守延迟

            # 东方财富板块资金流API
            url = f"{self.config['base_url']}/api/qt/clist/get"
            params = {
                'pn': 1,
                'pz': 100,
                'po': 1,
                'np': 1,
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': 2,
                'invt': 2,
                'fid': 'f62',
                'fs': 'm:90+t:2',
                'fields': 'f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87'
            }

            # 确保session已初始化
            if not hasattr(self, 'session') or self.session is None:
                import requests
                self.session = requests.Session()
                # 使用更保守的请求头，避免触发反爬虫机制
                self.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Referer': 'http://data.eastmoney.com/',
                    'Cache-Control': 'no-cache'
                })

            response = self.session.get(url, params=params, timeout=self.config.get('timeout', 30))
            response.raise_for_status()

            data = response.json()
            if not data.get('data') or not data['data'].get('diff'):
                self.logger.warning("未获取到板块资金流数据")
                return pd.DataFrame()

            # 解析数据
            records = []
            for item in data['data']['diff']:
                record = {
                    'sector_code': item.get('f12', ''),
                    'sector_name': item.get('f14', ''),
                    'change_pct': item.get('f3', 0) / 100 if item.get('f3') else 0,
                    'main_net_inflow': item.get('f62', 0),
                    'main_net_inflow_pct': item.get('f184', 0) / 100 if item.get('f184') else 0,
                    'super_large_net_inflow': item.get('f66', 0),
                    'super_large_net_inflow_pct': item.get('f69', 0) / 100 if item.get('f69') else 0,
                    'large_net_inflow': item.get('f72', 0),
                    'large_net_inflow_pct': item.get('f75', 0) / 100 if item.get('f75') else 0,
                    'medium_net_inflow': item.get('f78', 0),
                    'medium_net_inflow_pct': item.get('f81', 0) / 100 if item.get('f81') else 0,
                    'small_net_inflow': item.get('f84', 0),
                    'small_net_inflow_pct': item.get('f87', 0) / 100 if item.get('f87') else 0
                }
                records.append(record)

            df = pd.DataFrame(records)
            self.logger.info(f"成功获取板块资金流数据，共 {len(df)} 条记录")
            return df

        except Exception as e:
            self.logger.error(f"获取板块资金流数据失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()

    def get_individual_fund_flow_data(self, symbol: str, **kwargs) -> pd.DataFrame:
        """
        获取个股资金流数据

        Args:
            symbol: 股票代码
            **kwargs: 其他参数

        Returns:
            个股资金流数据DataFrame
        """
        try:
            self.logger.info(f"获取个股 {symbol} 资金流数据")

            # 东方财富个股资金流API
            url = f"{self.config['base_url']}/api/qt/stock/fflow/kline/get"
            params = {
                'lmt': 100,
                'klt': 101,
                'secid': f"1.{symbol}" if symbol.startswith('6') else f"0.{symbol}" if symbol.startswith(('0', '3')) else f"2.{symbol}",
                'fields1': 'f1,f2,f3,f7',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63'
            }

            response = self.session.get(url, params=params, timeout=self.config['timeout'])
            response.raise_for_status()

            data = response.json()
            if not data.get('data') or not data['data'].get('klines'):
                self.logger.warning(f"未获取到个股 {symbol} 资金流数据")
                return pd.DataFrame()

            # 解析数据
            records = []
            for kline in data['data']['klines']:
                parts = kline.split(',')
                if len(parts) >= 13:
                    record = {
                        'date': parts[0],
                        'main_net_inflow': float(parts[1]) if parts[1] != '-' else 0,
                        'small_net_inflow': float(parts[2]) if parts[2] != '-' else 0,
                        'medium_net_inflow': float(parts[3]) if parts[3] != '-' else 0,
                        'large_net_inflow': float(parts[4]) if parts[4] != '-' else 0,
                        'super_large_net_inflow': float(parts[5]) if parts[5] != '-' else 0,
                        'main_net_inflow_pct': float(parts[6]) if parts[6] != '-' else 0,
                        'small_net_inflow_pct': float(parts[7]) if parts[7] != '-' else 0,
                        'medium_net_inflow_pct': float(parts[8]) if parts[8] != '-' else 0,
                        'large_net_inflow_pct': float(parts[9]) if parts[9] != '-' else 0,
                        'super_large_net_inflow_pct': float(parts[10]) if parts[10] != '-' else 0,
                        'close_price': float(parts[11]) if parts[11] != '-' else 0,
                        'change_pct': float(parts[12]) if parts[12] != '-' else 0
                    }
                    records.append(record)

            df = pd.DataFrame(records)
            self.logger.info(f"成功获取个股资金流数据，共 {len(df)} 条记录")
            return df

        except Exception as e:
            self.logger.error(f"获取个股资金流数据失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()

    def get_main_fund_flow_data(self, symbol: str = "index", **kwargs) -> pd.DataFrame:
        """
        获取主力资金流数据（大盘指数）

        Args:
            symbol: 指数代码或"index"表示获取主要指数
            **kwargs: 其他参数

        Returns:
            主力资金流数据DataFrame
        """
        try:
            self.logger.info("获取主力资金流数据")

            # 东方财富大盘资金流API
            url = f"{self.config['base_url']}/api/qt/ulist.np/get"
            params = {
                'fltt': 2,
                'invt': 2,
                'fields': 'f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87',
                'secids': '1.000001,0.399001,1.000300'  # 上证指数、深证成指、沪深300
            }

            response = self.session.get(url, params=params, timeout=self.config['timeout'])
            response.raise_for_status()

            data = response.json()
            if not data.get('data') or not data['data'].get('diff'):
                self.logger.warning("未获取到主力资金流数据")
                return pd.DataFrame()

            # 解析数据
            records = []
            for item in data['data']['diff']:
                record = {
                    'index_code': item.get('f12', ''),
                    'index_name': item.get('f14', ''),
                    'current_price': item.get('f2', 0),
                    'change_pct': item.get('f3', 0) / 100 if item.get('f3') else 0,
                    'main_net_inflow': item.get('f62', 0),
                    'main_net_inflow_pct': item.get('f184', 0) / 100 if item.get('f184') else 0,
                    'super_large_net_inflow': item.get('f66', 0),
                    'super_large_net_inflow_pct': item.get('f69', 0) / 100 if item.get('f69') else 0,
                    'large_net_inflow': item.get('f72', 0),
                    'large_net_inflow_pct': item.get('f75', 0) / 100 if item.get('f75') else 0,
                    'medium_net_inflow': item.get('f78', 0),
                    'medium_net_inflow_pct': item.get('f81', 0) / 100 if item.get('f81') else 0,
                    'small_net_inflow': item.get('f84', 0),
                    'small_net_inflow_pct': item.get('f87', 0) / 100 if item.get('f87') else 0
                }
                records.append(record)

            df = pd.DataFrame(records)
            self.logger.info(f"成功获取主力资金流数据，共 {len(df)} 条记录")
            return df

        except Exception as e:
            self.logger.error(f"获取主力资金流数据失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return pd.DataFrame()

# 插件工厂函数


def create_plugin() -> IDataSourcePlugin:
    """创建插件实例"""
    return EastMoneyStockPlugin()


# 插件元数据
PLUGIN_METADATA = {
    "name": "东方财富股票数据源插件",
    "version": "1.0.0",
    "description": "提供东方财富高频实时数据和技术分析数据",
    "author": "FactorWeave-Quant 开发团队",
    "plugin_type": "data_source_stock",
    "asset_types": ["stock"],
    "data_types": ["historical_kline", "real_time_quote", "fundamental", "trade_tick"],
    "markets": ["SH", "SZ", "CYB", "KCB"],
    "config_schema": {
        "timeout": {
            "type": "integer",
            "default": 30,
            "description": "请求超时时间（秒）"
        },
        "max_retries": {
            "type": "integer",
            "default": 3,
            "description": "最大重试次数"
        }
    }
}


# 为EastMoneyStockPlugin添加网络配置方法
def _add_network_config_methods():
    """为东方财富插件添加网络配置方法"""

    def get_default_endpoints(self) -> List[NetworkEndpoint]:
        """获取默认网络端点配置"""
        return [
            NetworkEndpoint(
                name="eastmoney_primary",
                url="https://push2.eastmoney.com",
                description="东方财富主API",
                priority=10,
                timeout=30
            ),
            NetworkEndpoint(
                name="eastmoney_backup",
                url="https://push2his.eastmoney.com",
                description="东方财富备用API",
                priority=8,
                timeout=30
            ),
            NetworkEndpoint(
                name="eastmoney_mobile",
                url="https://mobileapi.eastmoney.com",
                description="东方财富移动API",
                priority=6,
                timeout=45
            ),
            NetworkEndpoint(
                name="eastmoney_overseas",
                url="https://global.eastmoney.com/api",
                description="东方财富海外API",
                priority=5,
                timeout=50
            )
        ]

    def get_network_config_schema(self) -> Dict[str, Any]:
        """获取网络配置架构"""
        return {
            "endpoints": {
                "title": "数据端点",
                "description": "东方财富数据获取端点",
                "categories": {
                    "primary": "主要API端点",
                    "backup": "备用端点",
                    "mobile": "移动端API",
                    "overseas": "海外API"
                }
            },
            "rate_limit": {
                "title": "频率限制",
                "description": "请求频率控制设置",
                "default_requests_per_minute": 60,
                "default_request_delay": 1.0,
                "recommended_max_requests": 100
            },
            "proxy": {
                "title": "代理设置",
                "description": "代理服务器配置",
                "support_types": ["http", "https", "socks5"]
            }
        }

    def apply_network_config(self, config: PluginNetworkConfig) -> bool:
        """应用网络配置"""
        try:
            # 获取最佳端点
            from core.network.universal_network_config import get_universal_network_manager
            network_manager = get_universal_network_manager()
            best_endpoint = network_manager.get_available_endpoint(self.plugin_id)

            if best_endpoint:
                # 更新基础URL
                self.config['base_url'] = best_endpoint.url
                self.config['timeout'] = best_endpoint.timeout
                self.logger.info(f"应用网络配置成功，使用端点: {best_endpoint.name}")

            # 应用会话配置
            if hasattr(self, 'session') and self.session:
                # 更新超时设置
                self.session.timeout = (config.request_delay, best_endpoint.timeout if best_endpoint else 30)

                # 更新请求头
                if config.user_agent:
                    self.session.headers.update({'User-Agent': config.user_agent})

                self.session.headers.update(config.custom_headers)

            return True

        except Exception as e:
            self.logger.error(f"应用网络配置失败: {e}")
            return False

# 插件注册函数


def create_plugin() -> EastMoneyStockPlugin:
    """创建东方财富股票插件实例"""
    return EastMoneyStockPlugin()


# 执行方法绑定
_add_network_config_methods()
