# -*- coding: utf-8 -*-
"""R295 分钟线数据体系 G4 第一步: 通达信分时数据源接口 (TDD)

背景: R293-分钟线完整数据体系方案 (项目记忆 R293-G4) —— 实时分时推荐方案 B =
扩展 tongdaxin_plugin get_minute_time_data (复用连接池/健康检查) + 图表 QTimer
3-5s 轮询 + 分时分支优先实时数据回退 1min 聚合 + 降级由 TET 插件框架 failover 完成。
本文件为第一步数据源层: pytdx get_minute_time_data 封装。

pytdx 接口约束 (pytdx/parser/get_minute_time_data.py 实证):
- get_minute_time_data(market, code) 仅返回 price/vol 两字段, 无 datetime/amount
- 时刻序列需客户端生成 (A股 240 分钟: 09:31-11:30 + 13:01-15:00)
- 均价线(VWAP)需上层用 vol + amount 计算, 故 amount = price*vol 近似保留

运行: E:\\anaconda3\\envs\\hikyuu\\python.exe -m pytest tests/test_r295_minute_source.py -q
"""

import pandas as pd
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from plugins.data_sources.stock.tongdaxin_plugin import TongdaxinStockPlugin


@pytest.fixture
def plugin():
    """构造真实插件实例 (连接池关闭, 全部网络层 mock, 离线安全)"""
    # 抑制 __init__ L768 启动的后台联网线程 (TdxServerInit), 保证测试无外部依赖
    with patch.object(TongdaxinStockPlugin, '_start_background_server_init'):
        p = TongdaxinStockPlugin()
    p.use_connection_pool = False
    p.api_client = MagicMock()
    p._ensure_connection = MagicMock(return_value=True)
    return p


def _make_raw_minute_data(n=240, price=10.0, vol=1000):
    """构造 pytdx 原始分时返回: 仅 price/vol 两字段的 dict 列表"""
    return [{'price': price, 'vol': vol} for _ in range(n)]


@pytest.mark.unit
class TestGenerateIntradayTimestamps:
    """时刻序列生成: A股 240 分钟 (09:31-11:30 + 13:01-15:00)"""

    def test_total_240_points(self):
        ts = TongdaxinStockPlugin._generate_intraday_timestamps('20260814')
        assert len(ts) == 240

    def test_first_point_0931(self):
        ts = TongdaxinStockPlugin._generate_intraday_timestamps('20260814')
        assert ts[0] == datetime(2026, 8, 14, 9, 31)

    def test_last_point_1500(self):
        ts = TongdaxinStockPlugin._generate_intraday_timestamps('20260814')
        assert ts[-1] == datetime(2026, 8, 14, 15, 0)

    def test_afternoon_starts_1301(self):
        ts = TongdaxinStockPlugin._generate_intraday_timestamps('20260814')
        assert ts[120] == datetime(2026, 8, 14, 13, 1)


@pytest.mark.unit
class TestGetMinuteTimeData:
    """get_minute_time_data 主接口"""

    def test_sh_market_mapping(self, plugin):
        """600xxx 沪市 -> market=1"""
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data()
        df = plugin.get_minute_time_data('600000')
        plugin.api_client.get_minute_time_data.assert_called_once_with(1, '600000')
        assert len(df) == 240

    def test_sz_market_mapping(self, plugin):
        """000xxx 深市 -> market=0"""
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data()
        df = plugin.get_minute_time_data('000001')
        plugin.api_client.get_minute_time_data.assert_called_once_with(0, '000001')

    def test_dataframe_format(self, plugin):
        """返回 DataFrame: DatetimeIndex + price/vol/amount 三列, amount=price*vol"""
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data(price=12.5, vol=2000)
        df = plugin.get_minute_time_data('600000')
        assert list(df.columns) == ['price', 'vol', 'amount']
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.iloc[0]['price'] == 12.5
        assert df.iloc[0]['vol'] == 2000
        assert df.iloc[0]['amount'] == 12.5 * 2000

    def test_empty_returns_empty_df(self, plugin):
        """pytdx 返回空/None (停牌/未开盘) -> 空 DataFrame, 不抛异常
        (降级由 TET 插件框架 failover 到腾讯独立插件完成)
        """
        plugin.api_client.get_minute_time_data.return_value = None
        df = plugin.get_minute_time_data('600000')
        assert df.empty

    def test_history_date_uses_history_api(self, plugin):
        """传 date 走 get_history_minute_time_data 历史分时"""
        plugin.api_client.get_history_minute_time_data.return_value = _make_raw_minute_data(n=100)
        df = plugin.get_minute_time_data('600000', date='20260813')
        plugin.api_client.get_history_minute_time_data.assert_called_once_with(1, '600000', '20260813')
        assert len(df) == 100


@pytest.mark.unit
class TestFetchDataBranch:
    """fetch_data 通用入口 minute_time/intraday 分支"""

    def test_minute_time_branch(self, plugin):
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data()
        df = plugin.fetch_data('600000', 'minute_time')
        assert len(df) == 240

    def test_intraday_alias_branch(self, plugin):
        plugin.api_client.get_minute_time_data.return_value = _make_raw_minute_data()
        df = plugin.fetch_data('600000', 'intraday')
        assert len(df) == 240

    def test_history_via_fetch_data(self, plugin):
        plugin.api_client.get_history_minute_time_data.return_value = _make_raw_minute_data(n=100)
        df = plugin.fetch_data('600000', 'minute_time', **{'date': '20260813'})
        assert len(df) == 100
