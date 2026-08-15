"""
Baostock数据源插件

基于Baostock(证券宝)免费开源数据平台实现的A股历史数据源插件。
提供A股历史K线数据（日/周/月/5/15/30/60分钟线），支持前复权/后复权/不复权。

官方文档: https://www.baostock.com
pip install baostock

作者: FactorWeave-Quant团队
版本: 1.0.0
"""

import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

import pandas as pd

from loguru import logger
from core.data_source_extensions import (
    IDataSourcePlugin, PluginInfo, ConnectionInfo, HealthCheckResult
)
from core.plugin_types import AssetType, DataType, PluginType

try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False
    logger.warning("baostock 未安装，Baostock数据源插件将以不可用模式运行（请执行 pip install baostock）")


class BaostockPlugin(IDataSourcePlugin):
    """
    Baostock数据源插件

    定位：A股历史K线批量下载源（日/周/月/5/15/30/60分钟线，支持复权）。
    不适合实时行情（Baostock 为收盘后批量更新模式），get_real_time_quotes 返回空。
    """

    plugin_id = "data_sources.stock.baostock_plugin"

    # 频率映射：系统频率 -> Baostock frequency (d=日, w=周, m=月, 5/15/30/60=分钟)
    _FREQ_MAP = {
        "D": "d", "d": "d", "daily": "d",
        "W": "w", "w": "w", "weekly": "w",
        "M": "m", "m": "m", "monthly": "m",
        "5min": "5", "5m": "5", "5": "5",
        "15min": "15", "15m": "15", "15": "15",
        "30min": "30", "30m": "30", "30": "30",
        "60min": "60", "60m": "60", "60": "60",
        "1H": "60", "1h": "60",
        "1min": None, "1m": None,  # Baostock 不提供1分钟线
    }

    # 复权映射：系统复权类型 -> Baostock adjustflag (3=不复权, 1=后复权, 2=前复权)
    _ADJ_MAP = {
        "none": "3", "": "3", None: "3",
        "qfq": "2", "前复权": "2",
        "hfq": "1", "后复权": "1",
    }

    # 分钟线字段（官方：分钟线不包含指数）
    _MINUTE_FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"
    # 日/周/月线字段（官方三套字段集，见 https://www.baostock.com/mainContent?file=stockKData.md）
    # 日线：含 preclose/tradestatus/isST
    _DAILY_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,isST"
    # 周/月线：官方明确不含 preclose/tradestatus/isST（传入 preclose 会报 10004012）
    _WEEKLY_MONTHLY_FIELDS = "date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg"

    def __init__(self):
        self.plugin_name = "Baostock数据源"
        self._is_connected_flag = False
        self._connection_info = None
        self._last_connection_time = None
        self._login_error = None

        # 性能统计
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "last_request_time": None
        }

        # 请求间隔控制（Baostock 对高频请求有限流）
        self._min_request_interval = 0.1
        self._last_request_time = 0.0

        self.logger = logger.bind(plugin=self.plugin_id)
        self.logger.info("Baostock数据源插件初始化完成")

    # ========================================================================
    # 插件基本信息
    # ========================================================================

    def get_version(self) -> str:
        """获取插件版本"""
        return "1.0.0"

    def get_description(self) -> str:
        """获取插件描述"""
        return "Baostock(证券宝)数据源插件，提供A股历史K线数据（日/周/月/5/15/30/60分钟线），支持前复权/后复权"

    def get_author(self) -> str:
        """获取插件作者"""
        return "FactorWeave-Quant团队"

    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        return [AssetType.STOCK_A]

    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型（不声明实时行情，Baostock 无实时数据）"""
        return [
            DataType.HISTORICAL_KLINE,
            DataType.ASSET_LIST,
        ]

    def get_supported_adjustment_types(self) -> List[str]:
        """获取支持的复权类型"""
        return ["none", "qfq", "hfq"]

    def get_capabilities(self) -> Dict[str, Any]:
        """获取插件能力"""
        return {
            "markets": ["SH", "SZ"],
            "frequencies": ["D", "W", "M", "5min", "15min", "30min", "60min"],
            "real_time_support": False,        # 无实时行情
            "historical_data": True,
            "adjustment": ["none", "qfq", "hfq"],
            "max_kline_count": 10000,          # 单次查询建议上限
            "rate_limit": "30 requests/60s",
            "data_delay": "日线T日17:30入库；分钟线T日20:30入库",
            "supported_exchanges": ["SSE", "SZSE"],
            "special_features": ["免费", "无需注册", "支持复权", "历史K线批量下载"]
        }

    def get_priority(self) -> int:
        """获取插件优先级（数值越小优先级越高，用于TET路由）"""
        return 40

    def get_weight(self) -> float:
        """获取插件权重"""
        return 1.0

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息（方法形式，兼容部分调用方）"""
        return PluginInfo(
            id=self.plugin_id,
            name=self.plugin_name,
            chinese_name="Baostock数据源",
            version=self.get_version(),
            description=self.get_description(),
            author=self.get_author(),
            supported_asset_types=self.get_supported_asset_types(),
            supported_data_types=self.get_supported_data_types(),
            capabilities={
                **self.get_capabilities(),
                'plugin_type': PluginType.DATA_SOURCE,
                'priority': self.get_priority(),
                'weight': self.get_weight()
            }
        )

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息（property 形式，IDataSourcePlugin 接口要求）"""
        return self.get_plugin_info()

    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """插件初始化"""
        try:
            if config:
                self.logger.debug(f"Baostock插件初始化配置: {config}")
            return True
        except Exception as e:
            self.logger.error(f"Baostock插件初始化失败: {e}")
            return False

    # ========================================================================
    # 连接管理
    # ========================================================================

    def _login_with_timeout(self, timeout: float = 15.0):
        """带超时保护的 baostock login

        baostock SDK 底层 socket 未设置超时(_apply_socket_timeout 仅在登录成功后生效),
        网络半开/服务端挂起时 bs.login() 可能无限阻塞, 导致整个数据管道挂起。
        此处将 login 放入独立线程并限时等待, 超时则放弃本次登录并返回 None。
        """
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(bs.login)
        try:
            lg = future.result(timeout=timeout)
            return lg
        except concurrent.futures.TimeoutError:
            self.logger.error(f"[NET] Baostock login 超过 {timeout}s 未完成, 放弃本次连接")
            return None
        except Exception as e:
            self.logger.error(f"[NET] Baostock login 异常: {type(e).__name__}: {e}")
            return None
        finally:
            # 不等待可能仍卡住的登录线程, 避免阻塞主流程
            executor.shutdown(wait=False)

    def connect(self, **kwargs) -> bool:
        """连接Baostock数据源"""
        t0 = time.time()
        try:
            if not BAOSTOCK_AVAILABLE:
                self.logger.error("baostock SDK 未安装，无法连接")
                return False

            self.logger.info("[NET] Baostock login 发起...")
            lg = self._login_with_timeout()
            elapsed = time.time() - t0
            if lg is None:
                # login 超时/异常, 不产生可用的 login 返回值
                self._is_connected_flag = False
                self._login_error = "login 超时/异常"
                self.logger.error(
                    f"[NET] Baostock连接失败(login超时/异常) (耗时 {elapsed:.2f}s, "
                    f"请检查网络能否访问 public-api.baostock.com:10030)"
                )
                return False
            if lg.error_code == '0':
                self._is_connected_flag = True
                self._last_connection_time = datetime.now()
                self._login_error = None
                self._connection_info = self._create_connection_info()
                self._apply_socket_timeout()
                self.logger.info(f"[NET] Baostock连接成功 (login耗时 {elapsed:.2f}s)")
                return True
            else:
                self._is_connected_flag = False
                self._login_error = f"{lg.error_code}: {lg.error_msg}"
                self.logger.error(
                    f"[NET] Baostock连接失败: {self._login_error} (耗时 {elapsed:.2f}s, "
                    f"请检查网络能否访问 public-api.baostock.com:10030)"
                )
                return False

        except Exception as e:
            self._is_connected_flag = False
            self.logger.error(
                f"[NET] Baostock连接异常: {type(e).__name__}: {e} "
                f"(耗时 {time.time()-t0:.2f}s; login 建连失败 baostock 库可能抛 NameError)"
            )
            return False

    def disconnect(self) -> bool:
        """断开Baostock数据源"""
        try:
            if BAOSTOCK_AVAILABLE:
                bs.logout()
            self._is_connected_flag = False
            self._connection_info = None
            self.logger.info("Baostock数据源断开连接成功")
            return True
        except Exception as e:
            self.logger.error(f"Baostock数据源断开连接失败: {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._is_connected_flag

    def get_connection_info(self) -> ConnectionInfo:
        """获取连接信息"""
        if self._connection_info:
            return self._connection_info
        return self._create_connection_info()

    def _create_connection_info(self) -> ConnectionInfo:
        """创建连接信息"""
        return ConnectionInfo(
            is_connected=self._is_connected_flag,
            connection_time=self._last_connection_time,
            last_activity=self._last_connection_time,
            connection_params={
                "source_id": self.plugin_id,
                "name": self.plugin_name,
                "sdk_available": BAOSTOCK_AVAILABLE,
                "login_error": self._login_error,
                "data_mode": "历史K线批量下载（收盘后更新）"
            }
        )

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            if not BAOSTOCK_AVAILABLE:
                return HealthCheckResult(
                    is_healthy=False,
                    message="baostock SDK 未安装",
                    details={"sdk_available": False, "timestamp": datetime.now()}
                )
            return HealthCheckResult(
                is_healthy=True,
                message="Baostock数据源正常",
                details={"sdk_available": True, "timestamp": datetime.now()}
            )
        except Exception as e:
            return HealthCheckResult(
                is_healthy=False,
                message=f"Baostock健康检查异常: {e}",
                details={"error": str(e), "timestamp": datetime.now()}
            )

    # ========================================================================
    # 数据获取
    # ========================================================================

    def get_kline_data(self, symbol: str, start_date: str = None, end_date: str = None,
                       period: str = "D", count: int = None,
                       data_source: str = None, adjustment: str = 'none',
                       market: str = None) -> pd.DataFrame:
        """TET框架 get_kline_data 调用入口（含复权参数）"""
        return self.get_kdata(
            symbol=symbol,
            freq=period,
            start_date=start_date,
            end_date=end_date,
            count=count,
            adjustment=adjustment
        )

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None,
                  adjustment: str = 'none') -> pd.DataFrame:
        """获取K线数据

        Args:
            symbol: 股票代码（如 '600000'、'600000.SH'、'000001.SZ'）
            freq: 频率（'D'/'W'/'M'/'5min'/'15min'/'30min'/'60min'）
            start_date: 开始日期（格式 'YYYY-MM-DD' 或 'YYYYMMDD'）
            end_date: 结束日期（格式 'YYYY-MM-DD' 或 'YYYYMMDD'）
            count: 数据条数（可选，超出时取尾部 count 条）
            adjustment: 复权类型（'none'/'qfq'/'hfq'）

        Returns:
            pd.DataFrame: 标准化K线数据（datetime, open, high, low, close, volume, amount）
        """
        if not BAOSTOCK_AVAILABLE:
            self.logger.warning("baostock SDK 不可用，无法获取K线数据")
            return pd.DataFrame()

        self._stats["total_requests"] += 1
        start_time = time.time()

        try:
            # 频率映射
            bs_freq = self._FREQ_MAP.get(freq)
            if bs_freq is None:
                self.logger.warning(f"Baostock不支持频率: {freq}（支持 D/W/M/5/15/30/60分钟）")
                return pd.DataFrame()

            # 复权映射
            bs_adj = self._ADJ_MAP.get(adjustment, "3")

            # 代码格式转换：600000.SH -> sh.600000
            bs_code = self._convert_symbol(symbol)
            if not bs_code:
                self.logger.warning(f"Baostock无法识别股票代码: {symbol}")
                return pd.DataFrame()

            # 日期格式转换 -> YYYY-MM-DD
            bs_start = self._format_date(start_date)
            bs_end = self._format_date(end_date)

            # 字段选择：分钟线/日线/周月线三套官方字段集（周月线不含 preclose，传错报 10004012）
            is_minute = bs_freq in ("5", "15", "30", "60")
            is_weekly_monthly = bs_freq in ("w", "m")
            if is_minute:
                fields = self._MINUTE_FIELDS
            elif is_weekly_monthly:
                fields = self._WEEKLY_MONTHLY_FIELDS
            else:
                fields = self._DAILY_FIELDS

            self.logger.info(
                f"[NET] Baostock查询K线开始: code={bs_code} freq={bs_freq} adjust={bs_adj} "
                f"range={bs_start}~{bs_end} fields={fields} | 请求发起"
            )

            # 查询（会话可能超时，异常时尝试重新登录一次）
            rs = self._query_with_relogin(bs_code, fields, bs_start, bs_end, bs_freq, bs_adj)

            if rs is None:
                return pd.DataFrame()

            # 检查查询结果 error_code（非 0 时可能是业务错误，区别于无数据）
            query_ec = str(getattr(rs, "error_code", "0"))
            query_em = str(getattr(rs, "error_msg", ""))

            # 收集结果
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                if query_ec != "0":
                    self.logger.warning(
                        f"Baostock返回错误(无数据): {symbol} freq={freq} error_code={query_ec} "
                        f"error_msg={query_em} range={bs_start}~{bs_end}"
                    )
                else:
                    self.logger.warning(
                        f"Baostock未返回{symbol}的K线数据 (freq={freq}, range={bs_start}~{bs_end}, "
                        f"耗时 {time.time()-start_time:.2f}s; 可能是停牌/退市/无交易日数据)"
                    )
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 标准化列名与数据类型
            df = self._standardize_kline_df(df, is_minute)

            # 限制条数
            if count and len(df) > count:
                df = df.tail(count)

            # 复权标记
            df['adj_type'] = adjustment
            df['adj_source'] = 'plugin'

            elapsed = time.time() - start_time
            self._stats["successful_requests"] += 1
            self._stats["avg_response_time"] = elapsed
            self.logger.info(
                f"Baostock成功获取{symbol}的K线数据: {len(df)}条, 复权: {adjustment}, 耗时: {elapsed:.2f}s"
            )
            if is_minute and elapsed > 10:
                self.logger.warning(
                    f"[NET] Baostock分钟线查询耗时 {elapsed:.2f}s（>10s），"
                    f"可能是区间过大导致服务端响应慢，建议缩短查询区间/减少步长"
                )
            return df

        except Exception as e:
            self._stats["failed_requests"] += 1
            self.logger.error(f"Baostock获取K线数据失败 {symbol} (freq={freq}): {type(e).__name__}: {e}")
            return pd.DataFrame()

    def get_real_time_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情（Baostock不支持，返回空DataFrame）"""
        self.logger.warning("Baostock不提供实时行情数据，请使用其他实时数据源")
        return pd.DataFrame()

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表（A股股票列表，通过 query_all_stock）"""
        if not BAOSTOCK_AVAILABLE:
            self.logger.warning("baostock SDK 不可用，无法获取资产列表")
            return []

        try:
            if asset_type != AssetType.STOCK_A:
                self.logger.warning(f"Baostock仅支持A股资产列表: {asset_type}")
                return []

            rs = self._query_with_relogin_all_stock()
            if rs is None:
                return []

            # 检查 error_code：query_all_stock 返回非 0 时 get_data() 为空，需明确记录
            rs_ec = str(getattr(rs, "error_code", "0"))
            rs_em = str(getattr(rs, "error_msg", ""))
            if rs_ec != "0":
                self.logger.error(
                    f"Baostock query_all_stock 返回错误: error_code={rs_ec} error_msg={rs_em}"
                )
                return []

            # 手动遍历替代 rs.get_data()：SDK 内部 get_data() 使用已废弃的 DataFrame.append
            # （baostock/data/resultset.py:146），pandas >= 2.0 已移除，会抛 AttributeError
            stock_rows = []
            while rs.error_code == '0' and rs.next():
                stock_rows.append(rs.get_row_data())
            if not stock_rows:
                self.logger.warning("Baostock未返回股票列表 (query_all_stock 成功但结果为空，可能是非交易日)")
                return []
            stock_df = pd.DataFrame(stock_rows, columns=rs.fields)
            if stock_df is None or stock_df.empty:
                self.logger.warning("Baostock未返回股票列表 (query_all_stock 成功但结果为空，可能是非交易日)")
                return []

            asset_list = []
            for _, row in stock_df.iterrows():
                code = str(row.get('code', ''))
                code_name = str(row.get('code_name', ''))
                trade_status = str(row.get('tradeStatus', ''))
                if not code:
                    continue
                # 转换: sh.600000 -> 600000.SH
                symbol = self._convert_to_standard_symbol(code)
                if not symbol:
                    continue
                asset_list.append({
                    'symbol': symbol,
                    'code': code.split('.')[-1],
                    'name': code_name,
                    'market': 'SH' if code.startswith('sh') else 'SZ',
                    'asset_type': 'STOCK',
                    'trade_status': trade_status,
                })

            self.logger.info(f"Baostock获取资产列表成功: {len(asset_list)} 个股票")
            return asset_list

        except Exception as e:
            self.logger.error(f"Baostock获取资产列表失败: {e}")
            return []

    def fetch_data(self, symbol: str, data_type: str, **params) -> Any:
        """获取数据的统一接口（兼容 PluginCenter 的 duck typing 判定）"""
        try:
            if data_type in (DataType.ASSET_LIST.value, "asset_list"):
                asset_type = params.get('asset_type', AssetType.STOCK_A)
                market = params.get('market')
                return self.get_asset_list(asset_type, market)
            elif data_type in (DataType.HISTORICAL_KLINE.value, "historical_kline", "kline", "get_kline_data"):
                freq = params.get('freq', params.get('period', 'D'))
                start_date = params.get('start_date')
                end_date = params.get('end_date')
                count = params.get('count')
                adjustment = params.get('adjustment', 'none')
                return self.get_kdata(symbol, freq, start_date, end_date, count, adjustment)
            elif data_type in (DataType.REAL_TIME_QUOTE.value, "real_time_quote"):
                symbols = params.get('symbols', [symbol])
                return self.get_real_time_quotes(symbols)
            else:
                raise ValueError(f"Baostock不支持的数据类型: {data_type}")
        except Exception as e:
            self.logger.error(f"Baostock fetch_data失败: {e}")
            raise

    def perform_health_check(self) -> HealthCheckResult:
        """执行健康检查（兼容调用方）"""
        return self.health_check()

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _query_with_relogin(self, code: str, fields: str, start_date: str,
                            end_date: str, frequency: str, adjustflag: str):
        """执行查询，遇到网络类错误/会话超时自动重新登录后重试一次

        官方错误码（baostock/common/contants.py）：
          0         成功
          10001001  未登录/会话失效（you don't login.）
          10002007  网络接收错误
          10002008  网络接收超时
          10002002  网络连接失败
          10004006  参数错误
          10004012  字段参数错误（如周/月线传 preclose）
          10004016  交易条数超过上限
        """
        t0 = time.time()

        def _do_query():
            return bs.query_history_k_data_plus(
                code, fields,
                start_date=start_date, end_date=end_date,
                frequency=frequency, adjustflag=adjustflag
            )

        def _is_network_error(ec: str) -> bool:
            """网络/会话类错误码（重登录重试有效），参数错误不重试"""
            return ec in ("10001001", "10002002", "10002007", "10002008", "10002009", "10001002")

        # 首次查询
        try:
            rs = _do_query()
        except Exception as e:
            self.logger.warning(f"[NET] Baostock查询异常（首次，准备重登录重试）: code={code} freq={frequency} err={e}")
            rs = None

        if rs is not None:
            ec = str(getattr(rs, "error_code", "0"))
            em = str(getattr(rs, "error_msg", ""))
            if ec == "0":
                self.logger.debug(f"[NET] Baostock查询成功: code={code} freq={frequency} 耗时 {time.time()-t0:.2f}s")
                return rs
            if not _is_network_error(ec):
                # 参数/业务类错误：重试无意义，直接返回并记录
                self.logger.error(
                    f"[NET] Baostock查询业务错误(不重试): code={code} freq={frequency} "
                    f"error_code={ec} error_msg={em} 耗时 {time.time()-t0:.2f}s"
                )
                return rs
            self.logger.warning(
                f"[NET] Baostock网络/会话错误(准备重登录重试): code={code} freq={frequency} "
                f"error_code={ec} error_msg={em} 耗时 {time.time()-t0:.2f}s"
            )

        # 网络类错误或异常：重新登录后重试一次
        try:
            bs.logout()
        except Exception:
            pass
        try:
            self.logger.info(f"[NET] Baostock重新登录... code={code} freq={frequency}")
            lg = self._login_with_timeout()
        except Exception as e:
            self.logger.error(f"[NET] Baostock重新登录异常: {e}")
            return None
        if lg is None:
            # login 超时/异常
            self.logger.error(f"[NET] Baostock重新登录超时/异常, 放弃重试: code={code} freq={frequency}")
            return None
        if lg.error_code != '0':
            self.logger.error(f"[NET] Baostock重新登录失败: {lg.error_code}: {lg.error_msg}")
            return None
        self.logger.info(f"[NET] Baostock重新登录成功，重发查询: code={code} freq={frequency}")

        try:
            rs = _do_query()
        except Exception as e:
            self.logger.error(f"[NET] Baostock重试查询异常: code={code} freq={frequency} err={e}")
            return None

        ec = str(getattr(rs, "error_code", "?"))
        em = str(getattr(rs, "error_msg", ""))
        self.logger.info(
            f"[NET] Baostock重试查询结果: code={code} freq={frequency} "
            f"error_code={ec} error_msg={em} 耗时 {time.time()-t0:.2f}s"
        )
        return rs

    def _apply_socket_timeout(self, timeout: float = 30.0):
        """给 baostock SDK 底层 socket 设置超时，防止 recv 无限阻塞

        baostock 的 SocketUtil.send_msg（util/socketutil.py）对 socket 未设置 timeout，
        服务端挂起时 recv 会无限阻塞（如限流/断连半开状态）。此处强制设置超时，
        超时后 socket.timeout 抛给 SDK 捕获并转为 error_code=10002007（网络接收错误），
        插件 _is_network_error() 会将其识别为网络错误并触发重登录重试。
        """
        try:
            import baostock.common.context as bs_context
            sock = getattr(bs_context, "default_socket", None)
            if sock is not None:
                sock.settimeout(timeout)
                self.logger.debug(f"[NET] Baostock socket 超时已设置为 {timeout}s")
            else:
                self.logger.warning("[NET] 未找到 baostock default_socket，无法设置超时")
        except Exception as e:
            self.logger.warning(f"[NET] 设置 baostock socket 超时失败(非致命): {type(e).__name__}: {e}")

    def _query_with_relogin_all_stock(self):
        """获取全部股票列表，遇到会话超时自动重连"""
        t0 = time.time()

        def _do_query():
            return bs.query_all_stock()

        try:
            rs = _do_query()
        except Exception as e:
            self.logger.warning(f"[NET] Baostock query_all_stock 异常（首次，准备重登录重试）: {e}")
            rs = None

        if rs is not None:
            ec = str(getattr(rs, "error_code", "0"))
            em = str(getattr(rs, "error_msg", ""))
            if ec == "0":
                self.logger.debug(f"[NET] Baostock query_all_stock 成功 耗时 {time.time()-t0:.2f}s")
                return rs
            if ec not in ("10001001", "10002002", "10002007", "10002008"):
                self.logger.error(
                    f"[NET] Baostock query_all_stock 业务错误(不重试): error_code={ec} "
                    f"error_msg={em} 耗时 {time.time()-t0:.2f}s"
                )
                return rs
            self.logger.warning(
                f"[NET] Baostock query_all_stock 网络/会话错误(准备重登录重试): "
                f"error_code={ec} error_msg={em} 耗时 {time.time()-t0:.2f}s"
            )

        # 网络类错误或异常：重新登录后重试一次
        try:
            bs.logout()
        except Exception:
            pass
        try:
            self.logger.info("[NET] Baostock query_all_stock 触发重新登录...")
            lg = bs.login()
        except Exception as e:
            self.logger.error(f"[NET] Baostock重新登录异常: {e}")
            return None
        if lg.error_code != '0':
            self.logger.error(f"[NET] Baostock重新登录失败: {lg.error_code}: {lg.error_msg}")
            return None
        self.logger.info("[NET] Baostock重新登录成功，重发 query_all_stock")
        try:
            rs = _do_query()
        except Exception as e:
            self.logger.error(f"[NET] Baostock query_all_stock 重试异常: {e}")
            return None
        ec = str(getattr(rs, "error_code", "?"))
        em = str(getattr(rs, "error_msg", ""))
        self.logger.info(
            f"[NET] Baostock query_all_stock 重试结果: error_code={ec} error_msg={em} "
            f"耗时 {time.time()-t0:.2f}s"
        )
        return rs

    def _convert_symbol(self, symbol: str) -> Optional[str]:
        """将标准股票代码转换为Baostock格式（sh./sz.前缀）"""
        symbol = (symbol or '').strip()
        if not symbol:
            return None

        code = symbol
        market = None

        # 带市场后缀格式: 600000.SH / 000001.SZ
        if '.' in symbol:
            parts = symbol.split('.')
            code = parts[0]
            suffix = parts[-1].upper()
            if suffix in ('SH', 'SZ'):
                market = suffix

        code = code.strip()

        # 根据代码规则推断市场（Baostock仅支持沪深A股）
        if market is None:
            if code.startswith(('60', '68', '9')):
                market = 'SH'
            elif code.startswith(('00', '30', '20')):
                market = 'SZ'
            else:
                return None

        prefix = 'sh' if market == 'SH' else 'sz'
        return f"{prefix}.{code}"

    def _convert_to_standard_symbol(self, bs_code: str) -> Optional[str]:
        """将Baostock代码（sh.600000）转换为标准格式（600000.SH）"""
        if not bs_code or '.' not in bs_code:
            return None
        prefix, code = bs_code.split('.', 1)
        market = 'SH' if prefix.lower() == 'sh' else 'SZ'
        return f"{code}.{market}"

    def _format_date(self, date_input) -> Optional[str]:
        """将各种日期格式转换为Baostock要求的YYYY-MM-DD格式"""
        if date_input is None or date_input == '':
            return None

        if isinstance(date_input, datetime):
            return date_input.strftime('%Y-%m-%d')

        if isinstance(date_input, str):
            date_str = date_input.strip()
            # 匹配 YYYY-MM-DD 或 YYYYMMDD
            match = re.search(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})', date_str)
            if match:
                year, month, day = match.groups()
                return f'{year}-{month}-{day}'
        return None

    def _standardize_kline_df(self, df: pd.DataFrame, is_minute: bool) -> pd.DataFrame:
        """标准化K线DataFrame列名与数据类型"""
        # 构造 datetime 列
        if is_minute and 'time' in df.columns and 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], errors='coerce')
        elif 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
        else:
            df['datetime'] = pd.NaT

        # 数值列转换
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 保留标准列
        keep_cols = ['datetime'] + [c for c in numeric_cols if c in df.columns]
        df = df[keep_cols].copy()

        # 过滤无效行
        df = df.dropna(subset=['datetime'])

        # 排序并去重
        df = df.sort_values('datetime').drop_duplicates(subset='datetime', keep='last')

        # 设置索引
        df.set_index('datetime', inplace=True)

        return df


# 插件注册（兼容加载器）
def create_plugin() -> BaostockPlugin:
    """创建插件实例"""
    return BaostockPlugin()


# 用于兼容性的别名
BaostockDataSourcePlugin = BaostockPlugin
