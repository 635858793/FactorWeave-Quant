# -*- coding: utf-8 -*-
"""腾讯分时数据源插件 (R295-T1.3 / R295-插件化)

本文件是**独立数据源插件** (腾讯分时), 由 TET 插件框架注册与调度:

- PluginManager.load_all_plugins 扫描 plugins/data_sources/stock/*_plugin.py,
  本文件类名 TencentStockPlugin 与基类名 IDataSourcePlugin 均含 "Plugin",
  可被 _find_plugin_class (core/plugin_manager.py L2106-2190) 识别。
- UDM.discover_and_register_data_source_plugins → register_data_source_plugin
  注册到 TET 路由器, plugin_id = data_sources.stock.tencent_plugin,
  priority=50 (低优先级: 数字越大优先级越低, 通达信 priority=1 优先)。
- 作为通达信分时的降级源: TET 管道 failover (core/tet_data_pipeline.py
  L599-685) 按 router.get_prioritized_sources 顺序依次尝试, 第一个返回
  非空 DataFrame 即成功; 通达信返回空/异常/超时 → 自动尝试本插件
  (failover 由框架完成, 插件间隔离, 本插件不感知其他源)。

背景: R293 调研结论 (project_memory R293) —— 腾讯财经提供
- qt.gtimg.cn 快照 (3s 轮询)
- web.ifzq.gtimg.cn 当日分时 (含均价)

HTTP 接口 (实测协议):
  GET https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh600000
  响应: {"code":0,"data":{"sh600000":{"data":{
            "data":[["0931","10.00","1000","10000"], ...],
            "date":"20260814"}}}}

行格式 (实测): 响应 data.{code}.data.data 为**空格分隔字符串列表**
  "0930 9.14 5105 4665970.00" → [时间HHMM, 价格, 成交量(手), 成交额(元)]
注: 实测 vol/amount 为**累计值** (15:28/15:29/15:30 三行 vol 相同),
内部转为每分钟增量与 pytdx 逐分钟语义对齐。
返回 DataFrame 与 tongdaxin_plugin.get_minute_time_data 格式一致:
  index=datetime (分钟时刻), 列 [price, vol, amount]
失败/异常返回空 DataFrame, 不抛异常 (降级源静默失败)。
"""

import logging
from datetime import datetime

import pandas as pd
import requests

from core.data_source_extensions import (
    IDataSourcePlugin,
    PluginInfo,
    HealthCheckResult,
    ConnectionInfo,
)
from core.plugin_types import PluginType, AssetType, DataType

logger = logging.getLogger(__name__)

# 腾讯分时接口
_TENCENT_MINUTE_URL = "https://web.ifzq.gtimg.cn/appstock/app/minute/query"
# 请求超时 (秒)
_REQUEST_TIMEOUT = 10

# 沪市前缀: 60/68 开头 (上证A股/科创板); 深市: 000/001/002/300 (主板/中小板/创业板)
_SH_PREFIXES = ('60', '68')
_SZ_PREFIXES = ('00', '01', '30')


class TencentIntradayProvider:
    """腾讯分时数据提供器 (pytdx 降级源, 纯 HTTP 数据获取层)"""

    @classmethod
    def fetch_intraday(cls, symbol: str, date: str = None) -> pd.DataFrame:
        """获取当日 (或指定交易日) 分时数据

        Args:
            symbol: 股票代码 (600000 / 600000.SH / sh600000 均可)
            date: 交易日 YYYYMMDD (或 YYYY-MM-DD), 默认接口返回的交易日

        Returns:
            pd.DataFrame: index=datetime (分钟时刻), 列 [price, vol, amount];
            成功时 attrs['prev_close'] 携带昨收 (腾讯行情 qt 字段 [4],
            实测交叉验证: 600000 昨收 9.18 = 当前价 9.10 - 涨跌 -0.08,
            见 _parse_prev_close; R295-VWAP V-02 分时图昨收精确化),
            昨收缺失/异常时无该 attr。
            失败/空数据返回空 DataFrame (不抛异常)
        """
        try:
            market, code = cls._normalize_symbol(symbol)
            url = f"{_TENCENT_MINUTE_URL}?code={market}{code}"
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()

            payload = resp.json()
            rows, trade_date = cls._parse_payload(payload, market + code)
            if not rows:
                logger.warning("腾讯分时响应无数据: %s", symbol)
                return pd.DataFrame()

            base_date = cls._normalize_date(date) or trade_date or \
                datetime.now().strftime('%Y%m%d')

            records = []
            for hhmm, price_raw, vol_raw, amount_raw in rows:
                try:
                    ts = datetime.strptime(f"{base_date}{hhmm}", '%Y%m%d%H%M')
                except (ValueError, TypeError):
                    continue
                try:
                    price = float(price_raw)
                except (TypeError, ValueError):
                    continue
                try:
                    vol = float(vol_raw)
                except (TypeError, ValueError):
                    vol = 0.0
                amount = None
                if amount_raw not in (None, ''):
                    try:
                        amount = float(amount_raw)
                    except (TypeError, ValueError):
                        amount = None
                # amount 接口未提供时用 price*vol 近似
                if amount is None:
                    amount = round(price * vol, 2)
                records.append({'datetime': ts, 'price': price,
                                'vol': vol, 'amount': amount})

            if not records:
                return pd.DataFrame()
            df = pd.DataFrame(records)
            df = df.set_index('datetime').sort_index()
            # 去重: 部分响应含 0930/0931 重复时段或集合竞价重复点, 保留后值
            df = df[~df.index.duplicated(keep='last')]
            # 实测腾讯 vol/amount 为累计值 → 转为每分钟增量 (非累计序列原样保留)
            if not df.empty:
                df['vol'] = cls._cumulative_to_delta(df['vol'].tolist())
                df['amount'] = cls._cumulative_to_delta(df['amount'].tolist())
                df['amount'] = df['amount'].round(2)
            # R295-插件化: 按 A股 240 分钟契约裁剪 (与 tongdaxin
            # get_minute_time_data 对齐, 见 tongdaxin_plugin._generate_intraday_timestamps)
            # 仅保留 09:31-11:30 与 13:01-15:00 时刻, 丢弃 09:30/13:00/15:01-15:30
            # 等非标准时刻 (实测 2026-08-16 响应 267 行, 非标准时刻共 27 个:
            # 0930 竞价 1 个 + 1300 1 个 + 1506-1530 25 个; 标准时刻 1501-1505 缺失)。
            # 注意: 裁剪必须在累计值→增量转换**之后**, 否则 09:31 的增量会丢失
            # 09:30 累计基线 (09:31 增量 = 09:31 累计 - 09:30 累计)。
            if not df.empty:
                hour = df.index.hour
                minute = df.index.minute
                morning = ((hour == 9) & (minute >= 31)) | (hour == 10) | \
                    ((hour == 11) & (minute <= 30))
                afternoon = ((hour == 13) & (minute >= 1)) | (hour == 14) | \
                    ((hour == 15) & (minute == 0))
                df = df[morning | afternoon]
            # R295-VWAP V-02: 昨收精确化 —— 解析行情 qt 字段 [4] 昨收并挂载到
            # df.attrs, 供上层 _convert_intraday_to_kline 透传 prev_close 列
            # (渲染侧昨收参考线优先读此值, 不再退化为分时首价近似)。
            # attrs 在 set_index/sort_index/去重/增量转换/裁剪等操作后仍保留,
            # 但赋值放在全部 DataFrame 操作之后最稳妥 (pandas 1.1+ 语义)。
            prev_close = cls._parse_prev_close(payload, market + code)
            if prev_close is not None:
                df.attrs['prev_close'] = prev_close
            logger.info("腾讯分时获取成功: %s %s %d 点", symbol, base_date, len(df))
            return df

        except Exception as e:
            logger.warning("腾讯分时接口调用失败 %s: %s", symbol, e)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    @staticmethod
    def _cumulative_to_delta(series: list) -> list:
        """累计值序列 → 每分钟增量; 非单调 (非累计) 序列原样返回

        实测腾讯 vol/amount 为到该分钟为止的累计值 (末段多行相同),
        逐分钟契约需增量; 若序列含下降 (非累计) 则视为逐分钟数据原样返回。
        """
        if len(series) < 2:
            return series
        if any(b < a - 1e-9 for a, b in zip(series, series[1:])):
            return series
        out = [series[0]]
        for i in range(1, len(series)):
            out.append(max(0.0, series[i] - series[i - 1]))
        return out
    @staticmethod
    def _normalize_symbol(symbol: str) -> tuple:
        """归一化股票代码 → (市场前缀, 6位代码)

        支持 600000 / 600000.SH / sh600000 / 600000.SH 等写法。
        规则: 6/68 开头 → sh, 00/01/30 开头 → sz, 其余默认 sz。
        """
        s = str(symbol).strip().upper().replace('.SH', '').replace('.SZ', '')
        s = s.replace('SH', '').replace('SZ', '')
        if not s:
            return 'sh', '000000'
        code = s[-6:]
        if s[:2] in ('SH', 'SZ'):
            return s[:2].lower(), code
        if code.startswith(_SH_PREFIXES):
            return 'sh', code
        if code.startswith(_SZ_PREFIXES):
            return 'sz', code
        return 'sz', code

    @staticmethod
    def _normalize_date(date: str) -> str:
        """日期归一化为 YYYYMMDD; 非法输入返回 None"""
        if not date:
            return None
        s = str(date).strip()
        if len(s) == 8 and s.isdigit():
            return s
        try:
            return datetime.strptime(s[:10], '%Y-%m-%d').strftime('%Y%m%d')
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_payload(payload: dict, code: str) -> tuple:
        """解析腾讯分时 JSON → (行列表, 交易日)

        行: (hhmm, price, vol, amount); 行格式异常/字段不足时跳过。
        兼容两种实际格式 (实测为空格分隔字符串):
          - "0930 9.14 5105 4665970.00" (空格分隔字符串)
          - ["0931", "10.00", "1000", "10000"] (list)
        """
        try:
            node = payload['data'][code]['data']
            trade_date = node.get('date')
            raw_rows = node.get('data') or []
        except (KeyError, TypeError):
            return [], None

        rows = []
        for item in raw_rows:
            if isinstance(item, str):
                parts = item.split()
                if len(parts) < 4:
                    continue
                rows.append((parts[0], parts[1], parts[2], parts[3]))
            elif isinstance(item, (list, tuple)) and len(item) >= 4:
                rows.append((str(item[0]), item[1], item[2], item[3]))
            else:
                continue
        return rows, trade_date

    @staticmethod
    def _parse_prev_close(payload: dict, code: str):
        """解析腾讯行情 qt 列表中的昨收 (字段 [4]) → float / None

        分时接口响应 data.{code}.qt.{code} 为腾讯行情标准字段数组:
          [0]=?, [1]=名称, [2]=代码, [3]=当前价, [4]=昨收, [5]=今开,
          [31]=涨跌, [32]=涨跌幅
        实测交叉验证 (600000, 2026-08-14): 昨收 9.18, 当前价 9.10,
        涨跌 [31]=-0.08 → 9.10-9.18=-0.08 ✓, 涨跌幅 [32]=-0.87% ✓。
        字段缺失/索引越界/非数值 → None (调用方静默降级, 不抛异常)。
        (R295-VWAP V-02: 分时图昨收精确化, 昨收参考线数据源)
        """
        try:
            qt = payload['data'][code]['qt'][code]
            if isinstance(qt, (list, tuple)) and len(qt) > 4:
                return float(qt[4])
        except (KeyError, TypeError, ValueError, IndexError):
            pass
        return None


class TencentStockPlugin(IDataSourcePlugin):
    """腾讯股票数据源插件 (分时降级源, 低优先级)

    仅声明 INTRADAY_DATA 能力 (router._supports_data_type 依 supported_data_types
    过滤, 只把分时请求路由到本插件); 其余数据类型返回空, 不参与路由。
    """

    def __init__(self):
        # 调用父类初始化 (IDataSourcePlugin 无自定义 __init__, 兼容 super().__init__())
        super().__init__()

        # 插件基本信息
        self.plugin_id = "data_sources.tencent_plugin"
        self.name = "腾讯股票数据源"
        self.version = "1.0.0"
        self.description = "提供A股分时数据，基于腾讯财经HTTP接口，作为通达信分时的降级源"
        self.author = "FactorWeave-Quant 开发团队"

        # 插件类型标识
        self.plugin_type = PluginType.DATA_SOURCE_STOCK

        # 低优先级: 数字越大优先级越低 (router.register_data_source L405),
        # 通达信 priority=1 优先, 本插件仅 failover 兜底
        self.priority = 50
        self.weight = 1.0

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            id="tencent_stock_plugin",
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            supported_asset_types=[AssetType.STOCK_A],
            supported_data_types=[DataType.INTRADAY_DATA],
            capabilities={
                "markets": ["SH", "SZ"],
                "frequencies": ["1m"],
                "real_time_support": True,
                "historical_data": False,
            },
            chinese_name="腾讯股票数据源",
        )

    def get_plugin_info(self) -> PluginInfo:
        """获取插件信息 (方法形式, PluginManager.load_plugin L1744 检测用)"""
        return self.plugin_info

    def connect(self, **kwargs) -> bool:
        """连接数据源: HTTP 无状态 → 连接恒成功"""
        return True

    def disconnect(self) -> bool:
        """断开连接: HTTP 无状态 → 恒成功"""
        return True

    def is_connected(self) -> bool:
        """检查连接状态: HTTP 无状态 → 恒可用"""
        return True

    def get_connection_info(self) -> ConnectionInfo:
        """获取连接信息"""
        return ConnectionInfo(
            is_connected=True,
            connection_time=datetime.now(),
            last_activity=datetime.now(),
            connection_params={"endpoint": "web.ifzq.gtimg.cn"},
            error_message=None,
        )

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        return HealthCheckResult(
            is_healthy=True,
            message="HTTP 无状态数据源，健康检查通过",
        )

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> list:
        """不声明 ASSET_LIST 能力, 仅防接口调用兜底"""
        return []

    def get_kdata(self, symbol: str, freq: str = "D", start_date=None,
                  end_date=None, count=None, **kwargs) -> pd.DataFrame:
        """不声明 HISTORICAL_KLINE 能力, 仅防接口调用兜底"""
        return pd.DataFrame()

    def get_real_time_quotes(self, symbols) -> pd.DataFrame:
        """不声明 REAL_TIME_QUOTE 能力, 仅防接口调用兜底"""
        return pd.DataFrame()

    def get_minute_time_data(self, symbol: str, date: str = None) -> pd.DataFrame:
        """获取分时数据 (委托 TencentIntradayProvider 纯 HTTP 层)

        Args:
            symbol: 股票代码 (600000 / 600000.SH / sh600000 均可)
            date: 交易日 YYYYMMDD (或 YYYY-MM-DD), 默认接口返回的交易日

        Returns:
            pd.DataFrame: index=datetime (分钟时刻), 列 [price, vol, amount]
            失败/空数据返回空 DataFrame (不抛异常)
        """
        try:
            return TencentIntradayProvider.fetch_intraday(symbol, date)
        except Exception as e:
            logger.warning("腾讯分时数据获取失败 %s: %s", symbol, e)
            return pd.DataFrame()

    def fetch_data(self, symbol: str, data_type: str,
                   start_date=None, end_date=None, **kwargs) -> pd.DataFrame:
        """通用数据获取接口 (TET 管道 _extract_from_source else 兜底调用)

        Args:
            symbol: 股票代码
            data_type: 数据类型字符串 (DataType 枚举 value, 如 'intraday_data')
            start_date: 开始日期 (分时仅支持 date, 未使用)
            end_date: 结束日期 (未使用)
            **kwargs: date=YYYYMMDD 等额外参数

        Returns:
            pd.DataFrame: 分时数据; 其他数据类型返回空 DataFrame
        """
        if data_type in ('minute_time', 'intraday', 'intraday_data'):
            return self.get_minute_time_data(symbol, date=kwargs.get('date'))
        logger.debug("腾讯插件不支持数据类型: %s", data_type)
        return pd.DataFrame()

    def get_supported_data_types(self) -> list:
        """仅声明分时数据类型"""
        return [DataType.INTRADAY_DATA]


def create_plugin() -> IDataSourcePlugin:
    """创建插件实例"""
    return TencentStockPlugin()


# 插件元数据 (PluginManager metadata 兼容)
PLUGIN_METADATA = {
    "name": "腾讯股票数据源插件",
    "version": "1.0.0",
    "description": "提供A股分时数据，基于腾讯财经HTTP接口，作为通达信分时的降级源",
    "author": "FactorWeave-Quant 开发团队",
    "plugin_type": "data_source_stock",
    "asset_types": ["stock"],
    "data_types": ["intraday_data"],
    "markets": ["SH", "SZ"],
}
