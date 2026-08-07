"""
新浪数据源插件

基于FactorWeave-Quant标准插件模板实现的新浪数据源插件，
提供股票实时行情和历史数据。

作者: FactorWeave-Quant团队
版本: 1.0.0
日期: 2024-09-17
"""

import re
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from urllib.parse import quote

from loguru import logger
from plugins.templates.standard_data_source_plugin import (
    StandardDataSourcePlugin, PluginConfig,
    PluginConnectionError, PluginDataQualityError
)
from core.plugin_types import AssetType, DataType


class SinaConfig(PluginConfig):
    """新浪插件配置"""

    def __init__(self):
        super().__init__()
        self.api_endpoint = "http://hq.sinajs.cn"
        self.quote_endpoint = "http://hq.sinajs.cn/list="
        self.kline_endpoint = "https://finance.sina.com.cn/realstock/company"

        # 新浪特定配置
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://finance.sina.com.cn/',
            'Accept': 'text/javascript, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }

        # 市场前缀映射
        self.market_prefix_map = {
            "SH": "sh",      # 上海A股
            "SZ": "sz",      # 深圳A股
            "BJ": "bj",      # 北京A股
            "HK": "rt_hk",   # 港股
            "US": "gb_"      # 美股
        }

        # 支持的市场和频率
        self.supported_markets = ["SH", "SZ", "HK", "US"]
        self.supported_frequencies = ["D"]  # 新浪主要支持日线数据

        # 请求限制
        self.rate_limit_requests = 100
        self.rate_limit_period = 60
        self.timeout = 10
        self.retry_count = 2


class SinaPlugin(StandardDataSourcePlugin):
    """
    新浪数据源插件

    提供股票、指数的实时行情数据，以及有限的历史数据支持
    """

    def __init__(self):
        """初始化新浪插件"""
        config = SinaConfig()
        super().__init__(
            plugin_id="sina",
            plugin_name="新浪数据源",
            config=config
        )

        # 会话管理
        self._session = None
        self._last_request_time = 0
        self._request_count = 0
        self._rate_limit_reset_time = time.time()

        # 股票代码缓存
        self._stock_codes = {}
        self._stock_codes_loaded = False

        self.logger.info("新浪数据源插件初始化完成")

    # 插件基本信息
    def get_version(self) -> str:
        """获取插件版本"""
        return "1.0.0"

    def get_description(self) -> str:
        """获取插件描述"""
        return "新浪数据源插件，提供A股、港股、美股的实时行情数据"

    def get_author(self) -> str:
        """获取插件作者"""
        return "FactorWeave-Quant团队 <factorweave@example.com>"

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return [
            AssetType.STOCK_A,      # 股票
            AssetType.INDEX       # 指数
        ]

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        return [
            DataType.REAL_TIME_QUOTE,     # 实时行情（主要功能）
            DataType.ASSET_LIST,          # 资产列表（真实API获取）
            DataType.HISTORICAL_KLINE,    # 历史K线（有限支持，仅当日）
            DataType.FUND_FLOW           # 资金流数据（真实API获取）
        ]

    def get_capabilities(self) -> Dict[str, Any]:
        """获取插件能力"""
        return {
            "markets": self.config.supported_markets,
            "frequencies": self.config.supported_frequencies,
            "real_time_support": True,
            "historical_data": True,  # 有限支持
            "max_symbols_per_request": 100,
            "max_kline_count": 250,   # 新浪历史数据有限
            "rate_limit": f"{self.config.rate_limit_requests} requests/{self.config.rate_limit_period}s",
            "data_delay": "实时（约15秒延迟）",
            "supported_exchanges": ["SSE", "SZSE", "HKEX", "NYSE", "NASDAQ"],
            "special_features": ["多市场支持", "港股美股行情", "快速实时数据"]
        }

    def get_priority(self) -> int:
        """获取插件优先级"""
        return 30  # 中等偏低优先级（主要用于实时行情）

    def get_weight(self) -> float:
        """获取插件权重"""
        return 0.9  # 略低权重，历史数据支持有限

    def get_plugin_info(self):
        """获取插件信息"""
        from core.data_source_extensions import PluginInfo
        from core.plugin_types import AssetType, DataType

        return PluginInfo(
            id="data_sources.sina_plugin",
            name="新浪财经数据源",
            version="2.0.0",
            description="新浪财经数据源插件，专注于实时行情数据",
            author="FactorWeave-Quant Team",
            supported_asset_types=[AssetType.STOCK_A, AssetType.INDEX],
            supported_data_types=self.get_supported_data_types(),
            capabilities={
                'real_time': True,
                'historical': False,  # 仅支持当日数据
                'fund_flow': True,
                'asset_list': True,
                'rate_limit': 200,  # 每分钟请求数
                'cache_enabled': True,
                'primary_strength': 'real_time_quotes'
            }
        )

    # 连接管理
    def _internal_connect(self, **kwargs) -> bool:
        """内部连接实现"""
        try:
            # 创建会话
            self._session = requests.Session()
            self._session.headers.update(self.config.headers)

            # 配置重试策略
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            retry_strategy = Retry(
                total=self.config.retry_count,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            )

            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

            # 测试连接 - 获取上证指数
            test_url = f"{self.config.quote_endpoint}sh000001"
            response = self._session.get(test_url, timeout=self.config.timeout)

            if response.status_code == 200:
                content = response.text
                if 'sh000001' in content and len(content) > 50:
                    self.logger.info("新浪数据源连接测试成功")
                    return True
                else:
                    self.logger.error("新浪数据源连接测试失败：返回数据异常")
                    return False
            else:
                self.logger.error(f"新浪数据源连接测试失败：HTTP {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"新浪数据源连接失败: {e}")
            return False

    def _internal_disconnect(self) -> bool:
        """内部断开连接实现"""
        try:
            if self._session:
                self._session.close()
                self._session = None

            # 清理缓存
            self._stock_codes.clear()
            self._stock_codes_loaded = False

            self.logger.info("新浪数据源断开连接成功")
            return True

        except Exception as e:
            self.logger.error(f"新浪数据源断开连接失败: {e}")
            return False

    def _test_connection(self) -> bool:
        """连接可用性数据级验证 (R259 覆写基类钩子): HTTP GET sh000001 指数"""
        try:
            if not self._session:
                return False
            test_url = f"{self.config.quote_endpoint}sh000001"
            response = self._session.get(test_url, timeout=self.config.timeout)
            if response.status_code == 200:
                content = response.text
                return 'sh000001' in content and len(content) > 50
            return False
        except Exception as e:
            self.logger.error(f"新浪数据源连接验证异常: {e}")
            return False

    # IDataSourcePlugin接口实现
    def fetch_data(self, symbol: str, data_type: str, **params) -> Any:
        """获取数据的统一接口"""
        try:
            if data_type == DataType.ASSET_LIST:
                asset_type = params.get('asset_type', AssetType.STOCK_A)
                market = params.get('market')
                return self._internal_get_asset_list(asset_type, market)
            elif data_type == DataType.HISTORICAL_KLINE:
                freq = params.get('freq', 'D')
                start_date = params.get('start_date')
                end_date = params.get('end_date')
                count = params.get('count')
                return self._internal_get_kdata(symbol, freq, start_date, end_date, count)
            elif data_type == DataType.REAL_TIME_QUOTE:
                symbols = params.get('symbols', [symbol])
                return self._internal_get_real_time_quotes(symbols)
            elif data_type == DataType.FUND_FLOW:
                return self._internal_get_fund_flow_data(symbol, **params)
            else:
                raise ValueError(f"不支持的数据类型: {data_type}")
        except Exception as e:
            self.logger.error(f"fetch_data失败: {e}")
            raise

    # 数据获取实现
    def _internal_get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        try:
            asset_list = []

            if asset_type == AssetType.STOCK_A:
                asset_list = self._get_stock_list(market)
            elif asset_type == AssetType.INDEX:
                asset_list = self._get_index_list(market)
            else:
                self.logger.warning(f"不支持的资产类型: {asset_type}")
                return []

            self.logger.info(f"获取资产列表成功: {asset_type.value}, 数量: {len(asset_list)}")
            return asset_list

        except Exception as e:
            self.logger.error(f"获取资产列表失败: {e}")
            raise PluginDataQualityError(f"获取{asset_type.value}列表失败: {str(e)}")

    def _internal_get_kdata(self, symbol: str, freq: str = "D",
                            start_date: str = None, end_date: str = None,
                            count: int = None) -> pd.DataFrame:
        """获取K线数据（有限支持）"""
        try:
            # 新浪的历史数据支持有限，主要通过实时行情获取当日数据
            self.logger.warning("新浪数据源对历史K线数据支持有限，建议使用其他数据源")

            # 仅返回当日的简单数据
            quote_data = self._internal_get_real_time_quotes([symbol])
            if not quote_data:
                return pd.DataFrame()

            quote = quote_data[0]
            current_date = datetime.now().strftime('%Y-%m-%d')

            # 构建简单的日线数据
            df = pd.DataFrame({
                'datetime': [pd.to_datetime(current_date)],
                'open': [quote.get('open', quote.get('price', 0))],
                'high': [quote.get('high', quote.get('price', 0))],
                'low': [quote.get('low', quote.get('price', 0))],
                'close': [quote.get('price', 0)],
                'volume': [quote.get('volume', 0)]
            })

            df.set_index('datetime', inplace=True)

            self.logger.debug(f"获取K线数据（当日）: {symbol}")
            return df

        except Exception as e:
            self.logger.error(f"获取K线数据失败: {symbol} - {e}")
            raise

    def _internal_get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """获取实时行情"""
        try:
            if not symbols:
                return []

            # 限制单次请求的符号数量
            max_symbols = self.get_capabilities()["max_symbols_per_request"]
            if len(symbols) > max_symbols:
                self.logger.warning(f"请求符号数量({len(symbols)})超过限制({max_symbols})，将截取前{max_symbols}个")
                symbols = symbols[:max_symbols]

            # 转换符号格式
            sina_symbols = []
            for symbol in symbols:
                sina_symbol = self._convert_to_sina_symbol(symbol)
                if sina_symbol:
                    sina_symbols.append(sina_symbol)

            if not sina_symbols:
                raise ValueError("没有有效的股票代码")

            # 构建请求URL
            symbols_str = ','.join(sina_symbols)
            url = f"{self.config.quote_endpoint}{symbols_str}"

            # 执行请求
            response = self._make_rate_limited_request(url)

            if response.status_code != 200:
                raise PluginConnectionError(f"API请求失败: HTTP {response.status_code}")

            # 解析响应
            content = response.text
            quotes = self._parse_sina_quotes(content, symbols)

            self.logger.debug(f"获取实时行情成功，数量: {len(quotes)}")
            return quotes

        except Exception as e:
            self.logger.error(f"获取实时行情失败: {e}")
            raise

    # 辅助方法
    def _convert_to_sina_symbol(self, symbol: str) -> str:
        """将标准股票代码转换为新浪格式"""
        try:
            if '.' in symbol:
                code, market = symbol.split('.')
                market = market.upper()

                if market in self.config.market_prefix_map:
                    prefix = self.config.market_prefix_map[market]
                    return f"{prefix}{code}"
            else:
                # 根据代码规则判断市场
                if symbol.startswith('00') or symbol.startswith('30'):
                    return f"sz{symbol}"  # 深圳
                elif symbol.startswith('60') or symbol.startswith('68'):
                    return f"sh{symbol}"  # 上海
                elif symbol.startswith(('4', '8', '9')):
                    return f"bj{symbol}"  # 北京
                else:
                    return f"sh{symbol}"  # 默认上海

            return None

        except Exception as e:
            self.logger.error(f"转换股票代码失败: {symbol} - {e}")
            return None

    def _parse_sina_quotes(self, content: str, original_symbols: List[str]) -> List[Dict[str, Any]]:
        """解析新浪行情数据"""
        quotes = []

        try:
            # 按行分割数据
            lines = content.strip().split('\n')

            for i, line in enumerate(lines):
                if not line or 'hq_str_' not in line:
                    continue

                # 提取股票代码和数据
                match = re.search(r'hq_str_(\w+)="([^"]*)"', line)
                if not match:
                    continue

                sina_symbol = match.group(1)
                data_str = match.group(2)

                if not data_str:
                    continue

                # 解析数据字段
                fields = data_str.split(',')
                if len(fields) < 30:  # A股数据至少30个字段
                    continue

                # 获取原始symbol
                original_symbol = original_symbols[i] if i < len(original_symbols) else self._convert_from_sina_symbol(sina_symbol)

                # 构建行情数据
                quote = self._build_quote_from_fields(fields, original_symbol, sina_symbol)
                if quote:
                    quotes.append(quote)

            return quotes

        except Exception as e:
            self.logger.error(f"解析新浪行情数据失败: {e}")
            return []

    def _build_quote_from_fields(self, fields: List[str], original_symbol: str, sina_symbol: str) -> Dict[str, Any]:
        """从字段数组构建行情数据"""
        try:
            if len(fields) < 30:
                return None

            # A股数据格式
            quote = {
                'symbol': original_symbol,
                'code': self._extract_code_from_symbol(original_symbol),
                'name': fields[0],
                'open': float(fields[1]) if fields[1] else 0.0,
                'pre_close': float(fields[2]) if fields[2] else 0.0,
                'price': float(fields[3]) if fields[3] else 0.0,
                'high': float(fields[4]) if fields[4] else 0.0,
                'low': float(fields[5]) if fields[5] else 0.0,
                'volume': int(fields[8]) if fields[8] else 0,
                'amount': float(fields[9]) if fields[9] else 0.0,
                'timestamp': f"{fields[30]} {fields[31]}" if len(fields) > 31 and fields[30] and fields[31] else datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'market': self._get_market_from_sina_symbol(sina_symbol)
            }

            # 计算涨跌额和涨跌幅
            if quote['price'] and quote['pre_close']:
                quote['change'] = quote['price'] - quote['pre_close']
                quote['change_pct'] = (quote['change'] / quote['pre_close']) * 100 if quote['pre_close'] != 0 else 0.0
            else:
                quote['change'] = 0.0
                quote['change_pct'] = 0.0

            return quote

        except Exception as e:
            self.logger.error(f"构建行情数据失败: {e}")
            return None

    def _convert_from_sina_symbol(self, sina_symbol: str) -> str:
        """将新浪格式转换回标准格式"""
        try:
            if sina_symbol.startswith('sh'):
                return f"{sina_symbol[2:]}.SH"
            elif sina_symbol.startswith('sz'):
                return f"{sina_symbol[2:]}.SZ"
            elif sina_symbol.startswith('rt_hk'):
                return f"{sina_symbol[5:]}.HK"
            elif sina_symbol.startswith('gb_'):
                return f"{sina_symbol[3:]}.US"
            else:
                return sina_symbol

        except Exception:
            return sina_symbol

    def _extract_code_from_symbol(self, symbol: str) -> str:
        """从symbol中提取代码"""
        if '.' in symbol:
            return symbol.split('.')[0]
        return symbol

    def _get_market_from_sina_symbol(self, sina_symbol: str) -> str:
        """从新浪符号获取市场"""
        if sina_symbol.startswith('sh'):
            return 'SH'
        elif sina_symbol.startswith('sz'):
            return 'SZ'
        elif sina_symbol.startswith('rt_hk'):
            return 'HK'
        elif sina_symbol.startswith('gb_'):
            return 'US'
        else:
            return 'SH'  # 默认

    def _get_stock_list(self, market: str = None) -> List[Dict[str, Any]]:
        """获取股票列表（使用真实API，支持分页获取所有股票）"""
        stocks = []

        try:
            # 使用新浪真实的股票列表API
            url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

            page = 1
            max_pages = 100  # 设置最大页数限制，避免无限循环
            start_time = time.time()  # 记录开始时间

            self.logger.info("开始分页获取股票列表...")

            while page <= max_pages:
                params = {
                    'page': page,
                    'num': 100,  # 新浪API限制每页最多100条
                    'sort': 'symbol',
                    'asc': 1,
                    'node': 'hs_a'  # A股市场
                }

                try:
                    response = self._session.get(url, params=params, timeout=self.config.timeout)
                    if response.status_code != 200:
                        self.logger.error(f"获取股票列表第{page}页失败: HTTP {response.status_code}")
                        break

                    import json
                    data = json.loads(response.text)

                    if not isinstance(data, list):
                        self.logger.error(f"第{page}页股票列表数据格式异常")
                        break

                    # 如果返回空数据，说明已经获取完所有数据
                    if not data:
                        self.logger.info(f"第{page}页无数据，股票列表获取完成")
                        break

                    page_stocks = 0
                    for item in data:
                        if not isinstance(item, dict) or 'symbol' not in item:
                            continue

                        # 解析股票信息
                        symbol = item.get('symbol', '')
                        code = item.get('code', '')
                        name = item.get('name', '')

                        # 确定市场
                        stock_market = 'SH' if symbol.startswith('sh') else 'SZ'

                        # 市场过滤
                        if market and stock_market != market:
                            continue

                        stocks.append({
                            'symbol': f"{code}.{stock_market}",
                            'code': code,
                            'name': name,
                            'market': stock_market,
                            'asset_type': 'STOCK',
                            'trade': item.get('trade', 0),  # 当前价格
                            'changepercent': item.get('changepercent', 0),  # 涨跌幅
                            'volume': item.get('volume', 0)  # 成交量
                        })
                        page_stocks += 1

                    # 每10页输出一次进度，减少日志开销
                    if page % 10 == 0 or page <= 5:
                        self.logger.debug(f"第{page}页获取股票 {page_stocks}/{len(data)} 个（市场过滤: {market or 'ALL'}）")
                    page += 1

                except Exception as page_error:
                    self.logger.error(f"获取第{page}页股票列表失败: {page_error}")
                    break

            elapsed_time = time.time() - start_time
            self.logger.info(f"股票列表获取完成: 总计 {len(stocks)} 个股票（共获取 {page-1} 页，耗时 {elapsed_time:.2f}秒）")
            return stocks

        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return []

    def _get_index_list(self, market: str = None) -> List[Dict[str, Any]]:
        """获取指数列表（使用真实API，支持分页获取所有指数）"""
        indices = []

        try:
            # 新浪指数列表API
            url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

            page = 1
            max_pages = 50  # 指数数量相对较少，限制页数

            self.logger.info("开始分页获取指数列表...")

            while page <= max_pages:
                params = {
                    'page': page,
                    'num': 100,  # 新浪API限制每页最多100条
                    'sort': 'symbol',
                    'asc': 1,
                    'node': 'zhishu_A'  # A股指数
                }

                try:
                    response = self._session.get(url, params=params, timeout=self.config.timeout)
                    if response.status_code != 200:
                        self.logger.warning(f"获取指数列表第{page}页失败: HTTP {response.status_code}")
                        break

                    import json
                    data = json.loads(response.text)

                    if not isinstance(data, list):
                        self.logger.warning(f"第{page}页指数列表数据格式异常")
                        break

                    # 如果返回空数据，说明已经获取完所有数据
                    if not data:
                        self.logger.info(f"第{page}页无数据，指数列表获取完成")
                        break

                    page_indices = 0
                    for item in data:
                        if not isinstance(item, dict) or 'symbol' not in item:
                            continue

                        # 解析指数信息
                        symbol = item.get('symbol', '')
                        code = item.get('code', '')
                        name = item.get('name', '')

                        # 确定市场
                        index_market = 'SH' if symbol.startswith('sh') else 'SZ'

                        # 市场过滤
                        if market and index_market != market:
                            continue

                        indices.append({
                            'symbol': f"{code}.{index_market}",
                            'code': code,
                            'name': name,
                            'market': index_market,
                            'asset_type': 'INDEX',
                            'trade': item.get('trade', 0),
                            'changepercent': item.get('changepercent', 0)
                        })
                        page_indices += 1

                    self.logger.debug(f"第{page}页获取指数 {page_indices}/{len(data)} 个（市场过滤: {market or 'ALL'}）")
                    page += 1

                except Exception as page_error:
                    self.logger.error(f"获取第{page}页指数列表失败: {page_error}")
                    break

            # 如果没有获取到数据，使用主要指数
            if not indices:
                self.logger.info("未获取到指数数据，使用主要指数")
                return self._get_major_indices(market)

            self.logger.info(f"指数列表获取完成: 总计 {len(indices)} 个指数（共获取 {page-1} 页）")
            return indices

        except Exception as e:
            self.logger.error(f"获取指数列表失败: {e}，使用主要指数")
            return self._get_major_indices(market)

    def _get_major_indices(self, market: str = None) -> List[Dict[str, Any]]:
        """获取主要指数（备用方案）"""
        major_indices = [
            {'code': '000001', 'name': '上证指数', 'market': 'SH'},
            {'code': '399001', 'name': '深证成指', 'market': 'SZ'},
            {'code': '399006', 'name': '创业板指', 'market': 'SZ'},
            {'code': '000300', 'name': '沪深300', 'market': 'SH'},
            {'code': '000016', 'name': '上证50', 'market': 'SH'}
        ]

        indices = []
        for idx in major_indices:
            if market is None or idx['market'] == market:
                indices.append({
                    'symbol': f"{idx['code']}.{idx['market']}",
                    'code': idx['code'],
                    'name': idx['name'],
                    'market': idx['market'],
                    'asset_type': 'INDEX'
                })
        return indices

    def _make_rate_limited_request(self, url: str, params: Dict = None) -> requests.Response:
        """执行频率限制的请求"""
        current_time = time.time()

        # 重置频率限制计数器
        if current_time - self._rate_limit_reset_time >= self.config.rate_limit_period:
            self._request_count = 0
            self._rate_limit_reset_time = current_time

        # 检查频率限制
        if self._request_count >= self.config.rate_limit_requests:
            sleep_time = self.config.rate_limit_period - (current_time - self._rate_limit_reset_time)
            if sleep_time > 0:
                self.logger.debug(f"达到频率限制，等待 {sleep_time:.1f} 秒")
                time.sleep(sleep_time)
                self._request_count = 0
                self._rate_limit_reset_time = time.time()

        # 请求间隔控制
        time_since_last = current_time - self._last_request_time
        if time_since_last < 0.2:  # 最小200ms间隔
            time.sleep(0.2 - time_since_last)

        # 执行请求
        try:
            if params:
                response = self._session.get(url, params=params, timeout=self.config.timeout)
            else:
                response = self._session.get(url, timeout=self.config.timeout)
            self._request_count += 1
            self._last_request_time = time.time()
            return response

        except requests.RequestException as e:
            self.logger.error(f"请求失败: {url} - {e}")
            raise PluginConnectionError(f"网络请求失败: {str(e)}")

    def _internal_get_fund_flow_data(self, symbol: str, **params) -> pd.DataFrame:
        """获取资金流数据（使用真实API）"""
        try:
            # 转换为新浪股票代码格式
            sina_symbol = self._convert_to_sina_symbol(symbol)
            if not sina_symbol:
                self.logger.error(f"无法转换股票代码: {symbol}")
                return pd.DataFrame()

            # 资金流数据API
            url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs"
            params_dict = {
                'daima': sina_symbol,
                'num': params.get('days', 20)
            }

            response = self._session.get(url, params=params_dict, timeout=self.config.timeout)
            if response.status_code != 200:
                self.logger.error(f"资金流API请求失败: HTTP {response.status_code}")
                return pd.DataFrame()

            # 新浪返回的是JSON格式
            content = response.text
            if content and content != 'null':
                try:
                    import json
                    data = json.loads(content)

                    if not isinstance(data, list):
                        self.logger.warning(f"资金流数据格式异常: {symbol}")
                        return pd.DataFrame()

                    fund_flow_data = []
                    for item in data:
                        if isinstance(item, dict):
                            try:
                                # 新的数据格式：字典类型
                                fund_flow_data.append({
                                    'date': item.get('opendate', ''),
                                    'close_price': float(item.get('trade', 0)) if item.get('trade') else 0,
                                    'change_ratio': float(item.get('changeratio', 0)) if item.get('changeratio') else 0,
                                    'turnover': float(item.get('turnover', 0)) if item.get('turnover') else 0,
                                    'net_amount': float(item.get('netamount', 0)) if item.get('netamount') else 0,
                                    'ratio_amount': float(item.get('ratioamount', 0)) if item.get('ratioamount') else 0,
                                    'main_net_inflow': float(item.get('r0_net', 0)) if item.get('r0_net') else 0,
                                    'main_ratio': float(item.get('r0_ratio', 0)) if item.get('r0_ratio') else 0
                                })
                            except (ValueError, TypeError) as e:
                                self.logger.warning(f"解析资金流数据行失败: {item} - {e}")
                                continue

                    if fund_flow_data:
                        df = pd.DataFrame(fund_flow_data)
                        df['date'] = pd.to_datetime(df['date'])
                        df.set_index('date', inplace=True)

                        self.logger.info(f"获取资金流数据成功: {symbol}, 数量: {len(df)}")
                        return df

                except json.JSONDecodeError as e:
                    self.logger.error(f"解析资金流JSON数据失败: {e}")

            self.logger.warning(f"资金流数据为空: {symbol}")
            return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"获取资金流数据失败: {symbol} - {e}")
            return pd.DataFrame()

    # 注意：新浪财经不提供真正的基本面数据（PE、PB等）API
    # etag.php接口返回的仍然是行情数据格式，不是基本面数据
    # 因此已删除该功能，以避免误导用户


# 插件注册
def create_plugin() -> SinaPlugin:
    """创建插件实例"""
    return SinaPlugin()


# 用于兼容性的别名
SinaDataSourcePlugin = SinaPlugin
