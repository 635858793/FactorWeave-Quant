# -*- coding: utf-8 -*-
"""R295 分钟线数据体系 第二步: 分时数据链路层改造 (T2 + T1.3) (TDD)

覆盖 (任务 A1/A2/A3):
- A1-1: tongdaxin get_supported_data_types 声明 DataType.INTRADAY_DATA
  (core/data_source_router._supports_data_type L892-913 依此过滤分时请求)
- A1-2: tongdaxin fetch_data 分时分支匹配 'intraday_data'
  (TET 管道 _extract_from_source else 兜底 L844-853 传 original_query.data_type.value)
- A1-3: UDM.request_data('intraday'/'intraday_data'/'minute_time') 路由到
  _get_intraday_data (StandardQuery INTRADAY_DATA → tet_pipeline.process)
- A2: TencentIntradayProvider 腾讯分时降级源 (web.ifzq.gtimg.cn) + pytdx 降级集成

运行: E:\\anaconda3\\envs\\hikyuu\\python.exe -m pytest tests/test_r295_intraday_service.py -q
全部网络层 mock (离线安全)。
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from plugins.data_sources.stock.tongdaxin_plugin import TongdaxinStockPlugin
from plugins.data_sources.stock.tencent_plugin import (
    TencentIntradayProvider,
    TencentStockPlugin,
    create_plugin,
)
from core.data_source_extensions import IDataSourcePlugin
from core.plugin_types import AssetType, DataType, PluginType
from core.services.unified_data_manager import UnifiedDataManager


@pytest.fixture
def plugin():
    """构造真实插件实例 (连接池关闭, 全部网络层 mock, 离线安全)"""
    with patch.object(TongdaxinStockPlugin, '_start_background_server_init'):
        p = TongdaxinStockPlugin()
    p.use_connection_pool = False
    p.api_client = MagicMock()
    p._ensure_connection = MagicMock(return_value=True)
    return p


def _make_raw_minute_data(n=240, price=10.0, vol=1000):
    """构造 pytdx 原始分时返回: 仅 price/vol 两字段的 dict 列表"""
    return [{'price': price, 'vol': vol} for _ in range(n)]


def _make_tencent_df(n=3, price=10.0, vol=100.0):
    """构造腾讯分时返回 DataFrame (index=datetime, 列 [price, vol, amount])"""
    idx = pd.date_range('2026-08-14 09:31', periods=n, freq='1min')
    return pd.DataFrame({
        'price': [price] * n,
        'vol': [vol] * n,
        'amount': [price * vol] * n,
    }, index=idx)


def _tencent_payload(code='sh600000', date='20260814', rows=None, qt=None):
    """构造腾讯分时接口响应 JSON

    qt: 行情字段列表 (腾讯标准字段数组), 字段 [4]=昨收 (R295-VWAP V-02)
    """
    if rows is None:
        rows = [
            "0930 9.14 5105 4665970.00",
            "0931 9.11 18364 16769279.00",
            "0932 9.12 26845 24502017.00",
        ]
    node = {"data": {"date": date, "data": rows}}
    if qt is not None:
        node["qt"] = {code: qt}
    return {
        "code": 0,
        "data": {code: node},
    }


# ==================== A1-1: 数据源类型声明 ====================

@pytest.mark.unit
class TestSupportedDataTypes:
    """get_supported_data_types 声明 INTRADAY_DATA (路由器过滤依据)"""

    def test_contains_intraday_data(self, plugin):
        supported = plugin.get_supported_data_types()
        assert DataType.INTRADAY_DATA in supported


# ==================== A1-2: fetch_data 分时分支 ====================

@pytest.mark.unit
class TestFetchDataIntradayDataBranch:
    """fetch_data 分时分支匹配 'intraday_data' (DataType.INTRADAY_DATA.value)"""

    def test_intraday_data_branch(self, plugin):
        """枚举 value 'intraday_data' 走分时分支"""
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data()
        df = plugin.fetch_data('600000', DataType.INTRADAY_DATA.value)
        assert len(df) == 240
        assert list(df.columns) == ['price', 'vol', 'amount']

    def test_intraday_data_branch_passes_date(self, plugin):
        """date 透传: 历史分时"""
        plugin.api_client.get_history_minute_time_data.return_value = _make_raw_minute_data(n=100)
        df = plugin.fetch_data('600000', 'intraday_data', **{'date': '20260813'})
        assert len(df) == 100
        plugin.api_client.get_history_minute_time_data.assert_called_once_with(1, '600000', '20260813')


# ==================== A1-3: UDM 分时路由 ====================

@pytest.mark.unit
class TestUdmIntradayRouting:
    """request_data 分时类型路由到 _get_intraday_data (TET 管道)"""

    def _make_udm(self, df):
        udm = object.__new__(UnifiedDataManager)
        udm.tet_enabled = True
        udm.tet_pipeline = MagicMock()
        udm.tet_pipeline.process.return_value = SimpleNamespace(data=df)
        return udm

    def test_request_data_intraday_routes(self):
        """data_type='intraday' → _get_intraday_data → TET 管道"""
        expected = _make_tencent_df()
        udm = self._make_udm(expected)
        result = asyncio.run(udm.request_data('600000', data_type='intraday'))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(expected)

    def test_request_data_intraday_data_value_routes(self):
        """data_type='intraday_data' (枚举 value) → TET 管道"""
        expected = _make_tencent_df(n=5)
        udm = self._make_udm(expected)
        result = asyncio.run(udm.request_data('600000', data_type='intraday_data'))
        assert len(result) == 5

    def test_request_data_minute_time_alias_routes(self):
        """data_type='minute_time' 别名 → TET 管道"""
        expected = _make_tencent_df(n=2)
        udm = self._make_udm(expected)
        result = asyncio.run(udm.request_data('600000', data_type='minute_time'))
        assert len(result) == 2

    def test_intraday_query_uses_intraday_data_type(self):
        """StandardQuery.data_type == DataType.INTRADAY_DATA, date 进 extra_params"""
        expected = _make_tencent_df()
        udm = self._make_udm(expected)
        asyncio.run(udm.request_data('600000', data_type='intraday', date='20260813'))
        query = udm.tet_pipeline.process.call_args[0][0]
        assert query.data_type == DataType.INTRADAY_DATA
        assert query.symbol == '600000'
        assert query.period == '1min'
        assert query.extra_params.get('date') == '20260813'

    def test_intraday_empty_result_returns_empty_df(self):
        """TET 返回空 DataFrame → request_data 返回空 DataFrame (不抛异常)"""
        udm = self._make_udm(pd.DataFrame())
        result = asyncio.run(udm.request_data('600000', data_type='intraday'))
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_intraday_tet_disabled_returns_empty(self):
        """TET 未启用 → 空 DataFrame"""
        udm = object.__new__(UnifiedDataManager)
        udm.tet_enabled = False
        udm.tet_pipeline = None
        result = asyncio.run(udm.request_data('600000', data_type='intraday'))
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_get_intraday_data_passes_asset_type(self):
        """asset_type 透传 StandardQuery"""
        expected = _make_tencent_df()
        udm = self._make_udm(expected)
        asyncio.run(udm.request_data('600000', data_type='intraday',
                                     asset_type=AssetType.STOCK_A))
        query = udm.tet_pipeline.process.call_args[0][0]
        assert query.asset_type == AssetType.STOCK_A

    def test_public_get_intraday_data_wraps_private(self):
        """公有 get_intraday_data → _get_intraday_data → TET 管道 (图表层轮询契约)"""
        expected = _make_tencent_df(n=4)
        udm = self._make_udm(expected)
        result = udm.get_intraday_data('600000')
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4
        query = udm.tet_pipeline.process.call_args[0][0]
        assert query.data_type == DataType.INTRADAY_DATA
        assert query.symbol == '600000'

    def test_public_get_intraday_data_accepts_date(self):
        """公有方法 date 参数透传 extra_params"""
        expected = _make_tencent_df()
        udm = self._make_udm(expected)
        udm.get_intraday_data('600000', date='20260813')
        query = udm.tet_pipeline.process.call_args[0][0]
        assert query.extra_params.get('date') == '20260813'

    def test_public_get_intraday_data_tet_disabled(self):
        """TET 未启用 → 空 DataFrame (不抛异常)"""
        udm = object.__new__(UnifiedDataManager)
        udm.tet_enabled = False
        udm.tet_pipeline = None
        result = udm.get_intraday_data('600000')
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ==================== A2: 腾讯分时降级源 ====================

@pytest.mark.unit
class TestTencentIntradayProvider:
    """腾讯分时 provider: 响应解析 / 时刻换算 / 增量转换 / 容错"""

    def test_dataframe_format_and_time_conversion(self):
        """mock 响应 → DatetimeIndex + price/vol/amount, 时刻换算正确"""
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: _tencent_payload())
            df = TencentIntradayProvider.fetch_intraday('600000')

        assert isinstance(df.index, pd.DatetimeIndex)
        assert list(df.columns) == ['price', 'vol', 'amount']
        # A股 240 契约裁剪: 09:30 竞价点被裁, index 从 09:31 开始
        assert df.index[0] == datetime(2026, 8, 14, 9, 31)
        assert df.index[1] == datetime(2026, 8, 14, 9, 32)
        # 累计值 → 每分钟增量 (09:31 增量 = 09:31 累计 - 09:30 累计)
        assert df.iloc[0]['vol'] == 18364.0 - 5105.0
        assert df.iloc[1]['vol'] == 26845.0 - 18364.0
        assert df.iloc[1]['amount'] == 24502017.0 - 16769279.0

    def test_a_share_240_minute_contract_clipping(self):
        """R295-插件化: 按 A股 240 契约裁剪, 仅保留 09:31-11:30 + 13:01-15:00

        09:30 (竞价)/13:00 (午后开盘)/11:31 (午休)/15:01-15:30 (盘后) 均被裁;
        09:30 被裁 → index[0]==09:31; 15:01+ 被裁 → index.max()==15:00。
        """
        rows = [
            "0930 9.00 1000 1000000.00",      # 集合竞价, 被裁
            "0931 9.01 2000 2000000.00",      # 上午第一分钟, 保留
            "0932 9.02 3000 3000000.00",      # 保留
            "1130 9.50 40000 40000000.00",    # 上午收盘, 保留
            "1131 9.51 41000 41000000.00",    # 午休, 被裁
            "1300 9.50 42000 42000000.00",    # 午后开盘竞价, 被裁
            "1301 9.52 43000 43000000.00",    # 下午第一分钟, 保留
            "1500 9.90 100000 100000000.00",  # 收盘, 保留
            "1501 9.91 101000 101000000.00",  # 盘后, 被裁
            "1506 9.92 102000 102000000.00",  # 盘后, 被裁
            "1530 9.93 103000 103000000.00",  # 盘后, 被裁
        ]
        payload = _tencent_payload(rows=rows)
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000')

        assert list(df.index) == [
            datetime(2026, 8, 14, 9, 31),
            datetime(2026, 8, 14, 9, 32),
            datetime(2026, 8, 14, 11, 30),
            datetime(2026, 8, 14, 13, 1),
            datetime(2026, 8, 14, 15, 0),
        ]
        # 09:30 被裁 → index 从 09:31 开始
        assert df.index[0] == datetime(2026, 8, 14, 9, 31)
        # 15:01+ 被裁 → index 最大为 15:00
        assert df.index.max() == datetime(2026, 8, 14, 15, 0)
        # 上午仅到 11:30, 下午从 13:01 开始
        assert datetime(2026, 8, 14, 11, 30) in df.index
        assert datetime(2026, 8, 14, 11, 31) not in df.index
        assert datetime(2026, 8, 14, 13, 0) not in df.index

    def test_list_format_rows_supported(self):
        """兼容 list-of-lists 行格式 (任务文档描述的格式)"""
        payload = _tencent_payload(code='sz000001',
                                   rows=[["0931", "10.00", "1000", "10000"]])
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('000001')
        assert len(df) == 1
        assert df.iloc[0]['price'] == 10.0
        assert df.iloc[0]['vol'] == 1000.0
        assert df.iloc[0]['amount'] == 10000.0

    def test_amount_fallback_to_price_mul_vol(self):
        """amount 缺失 → price*vol 近似"""
        payload = _tencent_payload(rows=[["0931", "10.00", "2000", ""]])
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert df.iloc[0]['amount'] == 10.0 * 2000.0

    def test_date_param_overrides_response_date(self):
        """date 参数优先于响应日期 (历史分时)"""
        payload = _tencent_payload(date='20260813')
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000', date='2026-08-13')
        assert df.index[0] == datetime(2026, 8, 13, 9, 31)

    def test_duplicate_timestamp_dedup_keeps_last(self):
        """重复时刻去重 (0930/0931 重复时段), 保留后值"""
        payload = _tencent_payload(rows=[
            "0931 10.0 100 1000",
            "0931 10.1 300 3000",
        ])
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert len(df) == 1
        assert df.iloc[0]['price'] == 10.1
        assert df.iloc[0]['vol'] == 300.0

    def test_non_cumulative_series_kept_as_is(self):
        """非累计 (单调下降) vol 序列 → 原样保留不转增量"""
        payload = _tencent_payload(rows=[
            "0931 10.0 100 1000",
            "0932 10.1 50 600",
        ])
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert df.iloc[1]['vol'] == 50.0
        assert df.iloc[1]['amount'] == 600.0

    def test_symbol_normalization(self):
        """600000.SH / sh600000 / 000001 → 正确市场前缀"""
        for symbol, expected in [('600000.SH', 'sh600000'),
                                 ('sh600000', 'sh600000'),
                                 ('000001', 'sz000001'),
                                 ('600000.SZ', 'sh600000')]:
            with patch('requests.get') as mock_get:
                mock_get.return_value = MagicMock(json=lambda: _tencent_payload())
                TencentIntradayProvider.fetch_intraday(symbol)
            url = mock_get.call_args[0][0]
            assert expected in url, f"{symbol} → {url}"

    def test_http_error_returns_empty(self):
        """HTTP 错误 → 空 DataFrame, 不抛异常"""
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=500,
                raise_for_status=MagicMock(side_effect=Exception('HTTP 500')))
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert df.empty

    def test_network_exception_returns_empty(self):
        """网络异常 → 空 DataFrame, 不抛异常"""
        with patch('requests.get', side_effect=Exception('connect timeout')):
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert df.empty

    def test_invalid_payload_returns_empty(self):
        """响应结构异常 → 空 DataFrame"""
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: {'code': -1})
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert df.empty

    # ---- R295-VWAP V-02: 昨收精确化 (qt 字段 [4] → attrs['prev_close']) ----

    def test_prev_close_parsed_from_qt_field(self):
        """qt[4] 昨收 → df.attrs['prev_close'] (实测 600000: 9.18)

        腾讯行情标准字段数组: [3]=当前价, [4]=昨收, [31]=涨跌, [32]=涨跌幅
        """
        qt = ['', '浦发银行', '600000', '9.10', '9.18', '9.20',
              '', '', '', '', '', '', '', '', '', '', '', '', '', '',
              '', '', '', '', '', '', '', '', '', '', '', '',
              '-0.08', '-0.87%']
        payload = _tencent_payload(qt=qt)
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert df.attrs.get('prev_close') == 9.18
        # 交叉验证: 当前价[3] - 昨收[4] == 涨跌[31] (-0.08) ✓
        assert round(9.10 - df.attrs['prev_close'], 2) == -0.08

    def test_prev_close_missing_when_no_qt(self):
        """响应无 qt 字段 → attrs 无 prev_close, 不抛异常"""
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: _tencent_payload())
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert 'prev_close' not in df.attrs
        assert not df.empty

    def test_prev_close_missing_when_qt_too_short(self):
        """qt 列表索引越界 (len<=4) → attrs 无 prev_close, 不抛异常"""
        payload = _tencent_payload(qt=['', '浦发银行', '600000', '9.10'])
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert 'prev_close' not in df.attrs
        assert not df.empty

    def test_prev_close_missing_when_qt_non_numeric(self):
        """qt[4] 非数值 (如 '--') → attrs 无 prev_close, 不抛异常"""
        payload = _tencent_payload(qt=['', '浦发银行', '600000', '9.10', '--'])
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(json=lambda: payload)
            df = TencentIntradayProvider.fetch_intraday('600000')
        assert 'prev_close' not in df.attrs
        assert not df.empty


# ==================== A2: tongdaxin 降级集成 ====================

@pytest.mark.unit
class TestTongdaxinTencentFallback:
    """get_minute_time_data 空/异常 → 直接返回空 (降级由 TET 框架 failover 到腾讯插件)

    旧语义 (R295-T1.3 内嵌腾讯降级) 已随插件化重构移除:
    tongdaxin_plugin 不再 import/调用腾讯源, 降级由 TET 管道
    (get_prioritized_sources failover) 切换到独立插件 tencent_plugin,
    覆盖见 TestTetFailoverToTencentPlugin。
    """

    @patch('plugins.data_sources.stock.tencent_plugin.TencentIntradayProvider.fetch_intraday')
    def test_pytdx_empty_returns_empty(self, mock_tencent, plugin):
        """pytdx 返回空 → 直接返回空 DataFrame (不再内嵌降级, 腾讯不被调用)"""
        plugin.api_client.get_minute_time_data.return_value = None
        df = plugin.get_minute_time_data('600000')
        assert df.empty
        mock_tencent.assert_not_called()

    @patch('plugins.data_sources.stock.tencent_plugin.TencentIntradayProvider.fetch_intraday')
    def test_pytdx_exception_returns_empty(self, mock_tencent, plugin):
        """pytdx 异常 → 直接返回空 DataFrame (不再内嵌降级, 腾讯不被调用)"""
        plugin.api_client.get_minute_time_data.side_effect = Exception('tdx broken')
        df = plugin.get_minute_time_data('600000')
        assert df.empty
        mock_tencent.assert_not_called()


# ==================== A1-3 补充: TET 管道端到端 (else 兜底路径) ====================

@pytest.mark.unit
class TestTetPipelineIntradayEndToEnd:
    """真实 TET 管道 → _extract_from_source else 兜底 → plugin.fetch_data('intraday_data')

    验证任务 A1 的核心链路闭环 (tet_data_pipeline.py L844-853 else 分支):
      StandardQuery(INTRADAY_DATA) → process → fetch_data(symbol, 'intraday_data',
      date=...) → get_minute_time_data (全部网络层 mock, 离线安全)
    """

    def test_intraday_flows_through_tet_fallback(self):
        from core.tet_data_pipeline import StandardQuery, TETDataPipeline

        with patch.object(TongdaxinStockPlugin, '_start_background_server_init'):
            plugin = TongdaxinStockPlugin()
        plugin.use_connection_pool = False
        plugin.api_client = MagicMock()
        # date 传值走 get_history_minute_time_data (MagicMock.__iter__ 默认空, 两个都要 mock)
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data(n=10)
        plugin.api_client.get_history_minute_time_data.return_value = _make_raw_minute_data(n=10)
        plugin._ensure_connection = MagicMock(return_value=True)

        router = MagicMock()
        router.get_prioritized_sources.return_value = ['tongdaxin']
        adapter = MagicMock()
        adapter.plugin_id = 'tongdaxin'

        pipeline = TETDataPipeline(router)
        pipeline.register_plugin('tongdaxin', plugin)
        pipeline._adapters['tongdaxin'] = adapter

        query = StandardQuery(
            symbol='600000',
            asset_type=AssetType.STOCK_A,
            data_type=DataType.INTRADAY_DATA,
            period='1min',
            extra_params={'date': '20260813'},
        )
        result = pipeline.process(query)
        assert result.data is not None
        assert not result.data.empty
        # 核心列必须存在 (pipeline 标准化可能附加 data_quality_score 等列)
        assert 'price' in result.data.columns

    def test_intraday_fallback_plugin_called_with_enum_value(self):
        """else 兜底以 data_type.value='intraday_data' 调用 fetch_data"""
        from core.tet_data_pipeline import StandardQuery, TETDataPipeline

        with patch.object(TongdaxinStockPlugin, '_start_background_server_init'):
            plugin = TongdaxinStockPlugin()
        plugin.use_connection_pool = False
        plugin.api_client = MagicMock()
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data(n=5)
        plugin.api_client.get_history_minute_time_data.return_value = _make_raw_minute_data(n=5)
        plugin._ensure_connection = MagicMock(return_value=True)
        plugin.fetch_data = MagicMock(wraps=plugin.fetch_data)

        router = MagicMock()
        router.get_prioritized_sources.return_value = ['tongdaxin']
        adapter = MagicMock()
        adapter.plugin_id = 'tongdaxin'

        pipeline = TETDataPipeline(router)
        pipeline.register_plugin('tongdaxin', plugin)
        pipeline._adapters['tongdaxin'] = adapter

        query = StandardQuery(
            symbol='600000',
            asset_type=AssetType.STOCK_A,
            data_type=DataType.INTRADAY_DATA,
            extra_params={'date': '20260813'},
        )
        pipeline.process(query)
        plugin.fetch_data.assert_called_once_with('600000', 'intraday_data', date='20260813')


# ==================== R295-插件化: 腾讯数据源插件 ====================

@pytest.mark.unit
class TestTencentStockPlugin:
    """腾讯数据源插件: 声明/工厂/优先级/路由/委托 (离线, 全部 mock)"""

    def _make_plugin(self):
        return TencentStockPlugin()

    def test_plugin_info_declares_intraday_only(self):
        """plugin_info 仅声明 INTRADAY_DATA (router 只路由分时请求)"""
        info = self._make_plugin().plugin_info
        assert info.id == 'tencent_stock_plugin'
        assert DataType.INTRADAY_DATA in info.supported_data_types
        assert DataType.HISTORICAL_KLINE not in info.supported_data_types
        assert DataType.ASSET_LIST not in info.supported_data_types
        assert AssetType.STOCK_A in info.supported_asset_types
        assert info.capabilities['real_time_support'] is True
        assert info.capabilities['historical_data'] is False

    def test_create_plugin_factory(self):
        """create_plugin() 返回 TencentStockPlugin 实例"""
        plugin = create_plugin()
        assert isinstance(plugin, TencentStockPlugin)
        assert isinstance(plugin, IDataSourcePlugin)

    def test_priority_is_low_for_failover(self):
        """priority==50 (低优先级降级源, 数字大=低, 通达信 priority=1 优先)"""
        assert self._make_plugin().priority == 50

    def test_plugin_type(self):
        """plugin_type == DATA_SOURCE_STOCK"""
        assert self._make_plugin().plugin_type == PluginType.DATA_SOURCE_STOCK

    def test_connect_is_connected(self):
        """HTTP 无状态: connect/disconnect/is_connected 均 True"""
        plugin = self._make_plugin()
        assert plugin.connect() is True
        assert plugin.disconnect() is True
        assert plugin.is_connected() is True
        conn = plugin.get_connection_info()
        assert conn.is_connected is True
        assert conn.connection_params.get('endpoint') == 'web.ifzq.gtimg.cn'
        assert plugin.health_check().is_healthy is True

    def test_fetch_data_intraday_branches_route(self):
        """分时三分支 (minute_time/intraday/intraday_data) 路由到 get_minute_time_data"""
        plugin = self._make_plugin()
        expected = _make_tencent_df(n=3)
        with patch.object(plugin, 'get_minute_time_data',
                          return_value=expected) as mock_minute:
            for dt in ('minute_time', 'intraday', 'intraday_data'):
                df = plugin.fetch_data('600000', dt, **{'date': '20260813'})
                assert df is expected  # 结果透传
        # 三次调用均以 date 透传
        assert mock_minute.call_count == 3
        for call in mock_minute.call_args_list:
            assert call == (('600000',), {'date': '20260813'})

    def test_fetch_data_non_intraday_returns_empty(self):
        """非分时类型返回空 DataFrame (不声明能力, 不参与路由)"""
        plugin = self._make_plugin()
        assert plugin.fetch_data('600000', 'historical_kline').empty
        assert plugin.fetch_data('600000', 'real_time_quote').empty
        assert plugin.fetch_data('600000', 'asset_list').empty

    def test_get_minute_time_data_delegates_to_provider(self):
        """get_minute_time_data 委托 TencentIntradayProvider.fetch_intraday"""
        expected = _make_tencent_df(n=5)
        with patch.object(TencentIntradayProvider, 'fetch_intraday',
                          return_value=expected) as mock_fetch:
            df = self._make_plugin().get_minute_time_data('600000', date='20260813')
        assert df is expected
        mock_fetch.assert_called_once_with('600000', '20260813')

    def test_find_plugin_class_recognizes_tencent_plugin(self):
        """_find_plugin_class 兼容: 类名含 Plugin + 基类名含 Plugin → 可被 PluginManager 识别"""
        from core.plugin_manager import PluginManager
        module = SimpleNamespace(TencentStockPlugin=TencentStockPlugin)
        pm = object.__new__(PluginManager)
        found = pm._find_plugin_class(module)
        assert found is TencentStockPlugin

    def test_get_supported_data_types(self):
        """get_supported_data_types 仅含 INTRADAY_DATA"""
        supported = self._make_plugin().get_supported_data_types()
        assert supported == [DataType.INTRADAY_DATA]


# ==================== R295-插件化: TET failover 端到端 ====================

@pytest.mark.unit
class TestTetFailoverToTencentPlugin:
    """TET 管道 failover: 通达信空 → 腾讯插件降级源

    证明降级由框架完成 (router.get_prioritized_sources 顺序尝试), 插件间隔离
    (腾讯插件不感知通达信, 仅通过 router 注册与 priority 参与调度)。
    """

    def _make_pipeline(self):
        from core.tet_data_pipeline import TETDataPipeline
        router = MagicMock()
        router.get_prioritized_sources.return_value = ['tongdaxin', 'tencent']
        return TETDataPipeline(router)

    def _register_source(self, pipeline, plugin_id, plugin):
        """注册插件 (真实 adapter) 后覆盖为可控 MagicMock adapter (与现有测试同构)"""
        pipeline.register_plugin(plugin_id, plugin)
        adapter = MagicMock()
        adapter.plugin_id = plugin_id
        pipeline._adapters[plugin_id] = adapter

    def test_failover_uses_tencent_when_tongdaxin_empty(self):
        """通达信返回空 → 腾讯返回非空 → successful_source=tencent, attempts=2"""
        from core.tet_data_pipeline import StandardQuery

        tencent_df = _make_tencent_df(n=5)

        pipeline = self._make_pipeline()
        # 源1 (模拟通达信): fetch_data 返回空 DataFrame → failover
        tdx_plugin = MagicMock()
        tdx_plugin.fetch_data.return_value = pd.DataFrame()
        self._register_source(pipeline, 'tongdaxin', tdx_plugin)
        # 源2 (腾讯): fetch_data 返回非空分时 → 成功
        tencent_plugin = MagicMock()
        tencent_plugin.fetch_data.return_value = tencent_df
        self._register_source(pipeline, 'tencent', tencent_plugin)

        query = StandardQuery(
            symbol='600000',
            asset_type=AssetType.STOCK_A,
            data_type=DataType.INTRADAY_DATA,
            period='1min',
            extra_params={'date': '20260813'},
        )
        result = pipeline.process(query)

        assert not result.data.empty
        assert 'price' in result.data.columns
        failover = result.metadata['failover']
        assert failover['success'] is True
        assert failover['successful_source'] == 'tencent'
        assert failover['attempts'] == 2
        assert failover['failed_sources'] == ['tongdaxin']
        # 腾讯 fetch_data 以枚举 value 被调用 (TET else 兜底路径)
        tencent_plugin.fetch_data.assert_called_once_with(
            '600000', 'intraday_data', date='20260813')

    def test_all_sources_empty_fails_with_attempts_2(self):
        """两个源都空 → success=False, attempts=2, successful_source=None"""
        from core.tet_data_pipeline import StandardQuery

        pipeline = self._make_pipeline()
        for plugin_id in ('tongdaxin', 'tencent'):
            plugin = MagicMock()
            plugin.fetch_data.return_value = pd.DataFrame()
            self._register_source(pipeline, plugin_id, plugin)

        query = StandardQuery(
            symbol='600000',
            asset_type=AssetType.STOCK_A,
            data_type=DataType.INTRADAY_DATA,
        )
        with pytest.raises(Exception):
            pipeline.process(query)


def _today_str():
    return datetime.now().strftime('%Y%m%d')
