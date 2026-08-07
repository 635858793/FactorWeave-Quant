from loguru import logger
"""
Yahoo Finance数据源插件示例（V2 对齐）

- 采用 core.data_source_extensions.IDataSourcePlugin 接口
- 移除旧装饰器与旧接口依赖
- 配置通过 initialize(config) 注入
"""

import pandas as pd
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QFormLayout, QPushButton, QTextEdit

from core.data_source_data_models import StockInfo, KlineData, MarketData, QueryParams
from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult, ConnectionInfo
from core.plugin_types import AssetType, DataType, PluginType
from plugins.plugin_interface import PluginLifecycle  # 添加PluginLifecycle导入


class YahooFinanceDataSourcePlugin(IDataSourcePlugin):
    """Yahoo Finance数据源插件"""

    def __init__(self):
        self.plugin_id = "examples.yahoo_finance_datasource"  # 添加plugin_id属性

        # 必须显式初始化这些属性（IDataSourcePlugin是抽象基类，不提供默认实现）
        self.initialized = False
        self.last_error = None
        self.plugin_state = PluginLifecycle.CREATED  # 初始状态（插件对象已创建）

        # 默认配置
        default_config = {
            'api_timeout': 30,
            'retry_count': 3,
            'cache_enabled': True,
            'cache_duration': 300,  # 5分钟
            'rate_limit': 100
        }

        self.config = default_config.copy()
        self._config = default_config.copy()
        self.session = None
        self.base_url = "https://query1.finance.yahoo.com"
        self.request_count = 0

        # 初始化缓存
        self._cache = {}
        self._cache_timestamps = {}

        # 插件类型标识（确保被识别为数据源插件）
        self.plugin_type = PluginType.DATA_SOURCE_STOCK
        self.connection_time = None
        self.last_activity = None
        self.last_error = None
        self.config = {}
        self.has_real_data = False

    def get_plugin_info(self) -> PluginInfo:
        return PluginInfo(
            id="datasource.yahoo_finance",
            name="Yahoo Finance数据源",
            version="1.0.0",
            description="从Yahoo Finance获取股票数据（历史/实时）",
            author="FactorWeave 团队",
            supported_asset_types=[AssetType.STOCK_A],
            supported_data_types=[DataType.HISTORICAL_KLINE, DataType.REAL_TIME_QUOTE],
            capabilities={
                "markets": ["US", "global"],
                "exchanges": ["NYSE", "NASDAQ", "AMEX"],
                "frequencies": ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"],
                "real_time_support": True,
                "historical_data": True,
                "international_markets": True
            }
        )

    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化插件（新接口：使用配置字典）
        """
        try:
            # 合并配置
            merged = self._config.copy()
            merged.update(config or {})
            self.config = merged
            self._config = merged.copy()

            # 创建会话
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "FactorWeave-Quant-YahooFinance/1.0",
                "Accept": "application/json"
            })

            self.initialized = True
            return True
        except Exception as e:
            logger.info(f"Yahoo Finance数据源插件初始化失败: {e}")
            self.last_error = str(e)
            return False

    def cleanup(self) -> None:
        """清理插件资源"""
        pass

    def shutdown(self) -> None:
        """关闭插件，释放资源（新接口要求）"""
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            # 轻量探测：获取服务器时间或简单行情
            url = f"{self.base_url}/v1/finance/trending/US"
            response = requests.get(url, timeout=self.config.get('api_timeout', 30))
            if response.status_code == 200:
                return HealthCheckResult(is_healthy=True, message="API访问正常", response_time=0.0)
            elif response.status_code in [403, 429, 451]:
                # 403: 禁止访问, 429: 请求过多, 451: 地区限制
                # 插件本身是可用的，只是API访问受限
                return HealthCheckResult(is_healthy=True, message=f"插件可用但API受限: {response.status_code}", response_time=0.0)
            else:
                # 其他HTTP错误，插件基本可用但API有问题
                return HealthCheckResult(is_healthy=True, message=f"插件可用但API异常: {response.status_code}", response_time=0.0)
        except Exception as e:
            # 网络异常等，如果插件已初始化则认为基本可用
            if getattr(self, 'initialized', False):
                return HealthCheckResult(is_healthy=True, message=f"插件可用但网络异常: {str(e)}", response_time=0.0)
            else:
                return HealthCheckResult(is_healthy=False, message=str(e), response_time=0.0)

    def get_supported_asset_types(self) -> List[AssetType]:
        return [AssetType.STOCK_A]

    def get_supported_data_types(self) -> List[DataType]:
        return [DataType.HISTORICAL_KLINE, DataType.REAL_TIME_QUOTE]

    def get_data_source_name(self) -> str:
        """获取数据源名称（兼容旧接口）"""
        return "Yahoo Finance"

    # 兼容旧接口的方法保留（不在新路由中直接使用）
    def get_supported_data_types_legacy(self) -> List[str]:
        return ["stock_daily", "stock_intraday", "stock_info", "market_summary"]

    def fetch_data(self, symbol: str, data_type: str,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   **params) -> pd.DataFrame:
        """
        获取数据

        Args:
            symbol: 股票代码
            data_type: 数据类型
            **params: 其他参数

        Returns:
            股票数据DataFrame
        """
        try:
            # 检查缓存
            cache_key = f"{symbol}_{data_type}_{str(params)}"
            if self._config['cache_enabled'] and cache_key in self._cache:
                cache_time, cached_data = self._cache[cache_key]
                if (datetime.now() - cache_time).seconds < self._config['cache_duration']:
                    if self._context:
                        self._context.logger.debug(f"从缓存返回数据: {symbol}")
                    return cached_data

            # 根据数据类型获取数据
            if data_type in ("stock_daily", DataType.HISTORICAL_KLINE.value):
                data = self._fetch_daily_data(symbol, **params)
            elif data_type == "stock_intraday":
                data = self._fetch_intraday_data(symbol, **params)
            elif data_type == "stock_info":
                data = self._fetch_stock_info(symbol, **params)
            elif data_type == "market_summary":
                data = self._fetch_market_summary(**params)
            else:
                raise ValueError(f"不支持的数据类型: {data_type}")

            # 缓存数据
            if self._config['cache_enabled']:
                self._cache[cache_key] = (datetime.now(), data)

            if self._context:
                self._context.logger.info(
                    f"成功获取数据: {symbol} ({data_type})")

            return data

        except Exception as e:
            if self._context:
                self._context.logger.error(
                    f"获取数据失败: {symbol} ({data_type}) - {e}")
            raise

    def get_real_time_data(self, symbols: List[str]) -> Dict[str, Any]:
        """简单的实时数据实现（返回最近收盘价模拟）"""
        try:
            result: Dict[str, Any] = {}
            for sym in symbols:
                # 这里用日线最后一条作为模拟实时
                df = self._fetch_daily_data(sym)
                last = df.iloc[-1]
                result[sym] = {
                    'symbol': sym,
                    'price': float(last['close']),
                    'open': float(last['open']),
                    'high': float(last['high']),
                    'low': float(last['low']),
                    'volume': float(last['volume']),
                    'timestamp': datetime.now().isoformat()
                }
            return result
        except Exception:
            return {}

    def _fetch_daily_data(self, symbol: str, **params) -> pd.DataFrame:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist_params = {'period': '1y', 'interval': '1d'}
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            if start_date:
                hist_params['start'] = start_date
            if end_date:
                hist_params['end'] = end_date
            df = ticker.history(**hist_params)
            if df.empty:
                self.has_real_data = False
                logger.warning(f"Yahoo Finance: 获取 {symbol} 日线数据为空")
                return pd.DataFrame()
            columns_map = {
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            }
            df = df.rename(columns=columns_map)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            self.has_real_data = True
            return df
        except Exception as e:
            self.has_real_data = False
            logger.warning(f"Yahoo Finance: 获取 {symbol} 日线数据失败: {e}")
            return pd.DataFrame()

    def _fetch_intraday_data(self, symbol: str, **params) -> pd.DataFrame:
        try:
            import yfinance as yf
            interval = params.get('interval', '1m')
            ticker = yf.Ticker(symbol)
            hist_params = {'period': '5d', 'interval': interval}
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            if start_date:
                hist_params['start'] = start_date
            if end_date:
                hist_params['end'] = end_date
            df = ticker.history(**hist_params)
            if df.empty:
                self.has_real_data = False
                logger.warning(f"Yahoo Finance: 获取 {symbol} 分钟线数据为空")
                return pd.DataFrame()
            columns_map = {
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            }
            df = df.rename(columns=columns_map)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            self.has_real_data = True
            return df
        except Exception as e:
            self.has_real_data = False
            logger.warning(f"Yahoo Finance: 获取 {symbol} 分钟线数据失败: {e}")
            return pd.DataFrame()

    def _fetch_stock_info(self, symbol: str, **params) -> pd.DataFrame:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info:
                self.has_real_data = False
                logger.warning(f"Yahoo Finance: 获取 {symbol} 股票信息为空")
                return pd.DataFrame()
            data = pd.DataFrame([{
                'symbol': symbol,
                'name': info.get('shortName', info.get('longName', symbol)),
                'sector': info.get('sector', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'dividend_yield': info.get('dividendYield', 0)
            }])
            data.set_index('symbol', inplace=True)
            self.has_real_data = True
            return data
        except Exception as e:
            self.has_real_data = False
            logger.warning(f"Yahoo Finance: 获取 {symbol} 股票信息失败: {e}")
            return pd.DataFrame()

    def _fetch_market_summary(self, **params) -> pd.DataFrame:
        try:
            import yfinance as yf
            indices = ['SPY', 'QQQ', 'IWM', 'DIA']
            summary_data = []
            for symbol in indices:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    summary_data.append({
                        'symbol': symbol,
                        'name': info.get('shortName', info.get('longName', symbol)),
                        'price': info.get('regularMarketPrice', 0),
                        'change': info.get('regularMarketChange', 0),
                        'change_percent': info.get('regularMarketChangePercent', 0),
                        'volume': info.get('regularMarketVolume', 0),
                        'market_cap': info.get('marketCap', 0)
                    })
                except Exception as e:
                    logger.warning(f"Yahoo Finance: 获取 {symbol} 市场摘要失败: {e}")
            if not summary_data:
                self.has_real_data = False
                return pd.DataFrame()
            data = pd.DataFrame(summary_data)
            data.set_index('symbol', inplace=True)
            self.has_real_data = True
            return data
        except Exception as e:
            self.has_real_data = False
            logger.warning(f"Yahoo Finance: 获取市场摘要失败: {e}")
            return pd.DataFrame()

    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式"""
        return {
            'type': 'object',
            'properties': {
                'api_timeout': {
                    'type': 'integer',
                    'minimum': 5,
                    'maximum': 120,
                    'default': 30,
                    'title': 'API超时时间(秒)'
                },
                'retry_count': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 10,
                    'default': 3,
                    'title': '重试次数'
                },
                'cache_enabled': {
                    'type': 'boolean',
                    'default': True,
                    'title': '启用缓存'
                },
                'cache_duration': {
                    'type': 'integer',
                    'minimum': 60,
                    'maximum': 3600,
                    'default': 300,
                    'title': '缓存时长(秒)'
                }
            },
            'required': ['api_timeout', 'retry_count']
        }

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return self._config.copy()

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置"""
        try:
            timeout = config.get('api_timeout', 30)
            retry_count = config.get('retry_count', 3)

            if not isinstance(timeout, int) or timeout < 5 or timeout > 120:
                return False

            if not isinstance(retry_count, int) or retry_count < 0 or retry_count > 10:
                return False

            return True

        except Exception:
            return False

    def on_event(self, event_name: str, *args, **kwargs) -> None:
        """处理事件"""
        if event_name == "market_close" and self._context:
            # 市场收盘时清理缓存
            self._cache.clear()
            self._context.logger.info("Yahoo Finance数据源：市场收盘，清理缓存")

    def _on_market_close(self) -> None:
        """市场收盘事件处理器"""
        if self._context:
            self._context.logger.debug("Yahoo Finance数据源：处理市场收盘事件")

    def test_connection(self) -> Dict[str, Any]:
        """
        测试连接

        Returns:
            测试结果
        """
        try:
            # 尝试获取测试数据
            test_data = self.fetch_data("AAPL", "stock_daily")

            return {
                'success': True,
                'message': '连接成功',
                'data_points': len(test_data)
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'连接失败: {e}',
                'data_points': 0
            }

    def get_available_symbols(self, **params) -> List[str]:
        market = params.get('market', 'US')
        try:
            assets = self.get_asset_list(AssetType.STOCK_A, market)
            symbols = [item['symbol'] for item in assets if item.get('symbol')]
            if not symbols:
                logger.warning(f"Yahoo Finance: 获取可用股票列表为空, market={market}")
            return symbols
        except Exception as e:
            logger.warning(f"Yahoo Finance: 获取可用股票列表失败: {e}")
            return []

    def create_config_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        """创建配置组件"""
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)

        # 基本配置
        config_form = QFormLayout()

        # API超时
        timeout_edit = QLineEdit(str(self._config['api_timeout']))
        config_form.addRow("API超时(秒):", timeout_edit)

        # 重试次数
        retry_edit = QLineEdit(str(self._config['retry_count']))
        config_form.addRow("重试次数:", retry_edit)

        layout.addLayout(config_form)

        # 测试连接按钮
        test_btn = QPushButton("测试连接")
        layout.addWidget(test_btn)

        # 测试结果显示
        result_text = QTextEdit()
        result_text.setMaximumHeight(100)
        result_text.setReadOnly(True)
        layout.addWidget(result_text)

        def test_connection():
            """测试连接"""
            result = self.test_connection()
            if result['success']:
                result_text.setPlainText(f" {result['message']}")
                result_text.setStyleSheet("color: green;")
            else:
                result_text.setPlainText(f" {result['message']}")
                result_text.setStyleSheet("color: red;")

        def save_config():
            """保存配置"""
            try:
                self._config['api_timeout'] = int(timeout_edit.text())
                self._config['retry_count'] = int(retry_edit.text())

                if self._context:
                    self._context.save_plugin_config(
                        self.metadata.name, self._config)

            except ValueError:
                result_text.setPlainText("配置格式错误")
                result_text.setStyleSheet("color: red;")

        test_btn.clicked.connect(test_connection)
        timeout_edit.textChanged.connect(save_config)
        retry_edit.textChanged.connect(save_config)

        return widget

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            id=f"{self.__class__.__name__.lower()}",
            name=getattr(self, 'name', self.__class__.__name__),
            version=getattr(self, 'version', '1.0.0'),
            description=getattr(self, 'description', '数据源插件'),
            author=getattr(self, 'author', 'FactorWeave-Quant Team'),
            supported_asset_types=getattr(self, 'supported_asset_types', [AssetType.STOCK_A]),
            supported_data_types=getattr(self, 'supported_data_types', [DataType.HISTORICAL_KLINE]),
            capabilities={
                "markets": ["SH", "SZ"],
                "frequencies": ["1m", "5m", "15m", "30m", "60m", "D"],
                "real_time_support": True,
                "historical_data": True
            }
        )

    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        try:
            import requests
            test_url = f"{self.base_url}/v1/finance/trending/US"
            response = self.session.get(test_url, timeout=self.config.get('api_timeout', 30))
            # R248: 原实现将 403(地域封锁)/429(限流)/451 误判为成功，
            # 选中此类数据源后所有数据请求必失败（R247"验证过浅"教训的 HTTP 变体）
            if response.status_code == 200:
                self.connection_time = datetime.now()
                self.last_activity = datetime.now()
                logger.info(f"{self.__class__.__name__} 连接成功")
                return True
            else:
                logger.warning(f"{self.__class__.__name__} 连接失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.last_error = str(e)
            return False

    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if self.session:
                self.session.close()
            self.connection_time = None
            logger.info(f"{self.__class__.__name__} 断开连接")
            return True
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        if hasattr(self, 'initialized') and self.initialized:
            return self.initialized
        if self.session and self.connection_time:
            return True
        return False

    def get_connection_info(self):
        """获取连接信息"""
        from core.data_source_extensions import ConnectionInfo
        return ConnectionInfo(
            is_connected=self.is_connected(),
            connection_time=self.connection_time,
            last_activity=self.last_activity,
            connection_params={
                "server_info": "localhost",
                "api_timeout": self.config.get('api_timeout', 30)
            },
            error_message=self.last_error
        )

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        try:
            url = f"{self.base_url}/v1/finance/trending/{market or 'US'}"
            response = self.session.get(url, timeout=self.config.get('api_timeout', 30))
            if response.status_code == 200:
                data = response.json()
                result = []
                for item in data.get('quotes', []):
                    result.append({
                        'symbol': item.get('symbol'),
                        'name': item.get('shortName', item.get('longName', '')),
                        'type': 'stock',
                        'market': market or 'US'
                    })
                return result
            return []
        except Exception as e:
            logger.error(f"获取资产列表失败: {e}")
            return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None) -> pd.DataFrame:
        """获取K线数据"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            params = {'period': '1y', 'interval': freq}
            if start_date:
                params['start'] = start_date
            if end_date:
                params['end'] = end_date
            if count:
                params['count'] = count
            df = ticker.history(**params)
            if not df.empty:
                df = df.reset_index()
                df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            return df
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return pd.DataFrame()

    def get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """获取实时行情"""
        try:
            import yfinance as yf
            result = []
            tickers = yf.Tickers(' '.join(symbols))
            for symbol in symbols:
                try:
                    ticker = tickers.tickers.get(symbol)
                    if ticker:
                        info = ticker.info
                        result.append({
                            'symbol': symbol,
                            'price': info.get('currentPrice', 0),
                            'change': info.get('regularMarketChange', 0),
                            'change_pct': info.get('regularMarketChangePercent', 0),
                            'volume': info.get('volume', 0),
                            'timestamp': datetime.now()
                        })
                except Exception as e:
                    logger.warning(f"获取{symbol}行情失败: {e}")
            return result
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return []
