#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_r251_akshare_verify.py - AKShare插件分钟线支持验证脚本（mock 模式，不访问网络）

验证内容：
1. 分钟频率映射正确（'60m'→'60'、'1H'→'60'、'1m'→'1'、'5min'→'5'、'15'→'15'）
2. 分钟分支调用 ak.stock_zh_a_hist_min_em（symbol 无市场后缀、日期格式 'YYYY-MM-DD 09:30:00'、adjust 透传）
3. 输出列标准化正确（DatetimeIndex + open/high/low/close/volume/amount/avg_price + adj_type）
4. capabilities 声明完整（frequencies 8种 + historical_data=True）
5. 日线分支回归（仍走 ak.stock_zh_a_hist，period='daily'，YYYYMMDD 日期格式）

运行: python tests/_r251_akshare_verify.py
"""
import os
import sys
from unittest import mock

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 关闭全局请求限流，避免每次调用额外 sleep，加快测试
from plugins.data_sources.utils.retry_helper import set_global_rate_limit
set_global_rate_limit(0)

from plugins.data_sources.stock.akshare_plugin import AKSharePlugin


def make_minute_df():
    """构造模拟 akshare stock_zh_a_hist_min_em 返回的 DataFrame（中文列名，含'时间'列）"""
    return pd.DataFrame({
        '时间': ['2024-01-02 09:30:00', '2024-01-02 09:31:00', '2024-01-02 09:32:00'],
        '开盘': ['10.00', '10.10', '10.20'],
        '收盘': ['10.20', '10.30', '10.15'],
        '最高': ['10.40', '10.50', '10.35'],
        '最低': ['9.90', '10.00', '10.05'],
        '成交量': ['1000', '1200', '900'],
        '成交额': ['10200.0', '12360.0', '9180.0'],
        '均价': ['10.10', '10.20', '10.18'],
    })


def make_daily_df():
    """构造模拟 akshare stock_zh_a_hist 返回的 DataFrame（日线中文列名，含'日期'列）"""
    return pd.DataFrame({
        '日期': ['2024-01-02', '2024-01-03'],
        '开盘': ['10.00', '10.20'],
        '收盘': ['10.20', '10.30'],
        '最高': ['10.40', '10.50'],
        '最低': ['9.90', '10.00'],
        '成交量': ['100000', '120000'],
        '成交额': ['1020000.0', '1236000.0'],
        '振幅': ['5.00', '4.90'],
        '涨跌幅': ['2.00', '0.98'],
        '涨跌额': ['0.20', '0.10'],
        '换手率': ['0.50', '0.60'],
    })


def check_minute_freq_mapping(plugin):
    """验证分钟频率映射与参数传递：'60m' → period='60'"""
    captured = {}

    def fake_min_em(**kwargs):
        captured.update(kwargs)
        return make_minute_df()

    with mock.patch('akshare.stock_zh_a_hist_min_em', side_effect=fake_min_em):
        df = plugin.get_kdata(
            symbol='600000.SH', freq='60m',
            start_date='2024-01-01', end_date='2024-01-05', adjustment='qfq'
        )

    assert captured.get('period') == '60', f"60m 应映射为 period='60'，实际: {captured.get('period')}"
    assert captured.get('symbol') == '600000', f"symbol 应去除市场后缀为 600000，实际: {captured.get('symbol')}"
    assert captured.get('start_date') == '2024-01-01 09:30:00', \
        f"start_date 应为 '2024-01-01 09:30:00'，实际: {captured.get('start_date')}"
    assert captured.get('end_date') == '2024-01-05 09:30:00', \
        f"end_date 应为 '2024-01-05 09:30:00'，实际: {captured.get('end_date')}"
    assert captured.get('adjust') == 'qfq', f"adjust 应为 qfq，实际: {captured.get('adjust')}"
    print("  [PASS] 60m → period='60'，symbol/日期/adjust 参数传递正确")

    return df


def check_minute_branch_called(plugin):
    """验证 1m/5min/1H/15 等映射并确认分钟分支被调用"""
    for freq, expect in [('5min', '5'), ('1m', '1'), ('1H', '60'), ('15', '15')]:
        called = {}

        def fake_min_em(**kwargs):
            called['period'] = kwargs['period']
            return make_minute_df()

        with mock.patch('akshare.stock_zh_a_hist_min_em', side_effect=fake_min_em):
            plugin.get_kdata(symbol='000001', freq=freq)
        assert called.get('period') == expect, f"{freq} 应映射为 period='{expect}'，实际: {called.get('period')}"
        print(f"  [PASS] {freq} → period='{expect}'（分钟分支被调用）")


def check_minute_output_normalized(df):
    """验证分钟线输出列标准化"""
    assert isinstance(df.index, pd.DatetimeIndex), "输出索引应为 DatetimeIndex"
    assert df.index.name == 'datetime', f"索引名应为 datetime，实际: {df.index.name}"
    expected_cols = {'open', 'high', 'low', 'close', 'volume', 'amount', 'avg_price', 'adj_type', 'adj_source'}
    assert expected_cols.issubset(df.columns), f"输出缺少标准列，实际列: {list(df.columns)}"
    for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
        assert pd.api.types.is_numeric_dtype(df[col]), f"列 {col} 应为数值类型"
    assert df['adj_type'].iloc[0] == 'qfq', "adj_type 应标记 qfq"
    assert len(df) == 3, f"应保留 3 条记录，实际: {len(df)}"
    print("  [PASS] 分钟线输出标准化：DatetimeIndex + open/high/low/close/volume/amount/avg_price + adj_type")


def check_capabilities(plugin):
    """验证 capabilities 声明完整"""
    caps = plugin.get_capabilities()
    assert caps.get('frequencies') == ['1m', '5m', '15m', '30m', '60m', 'D', 'W', 'M'], \
        f"frequencies 应为 8 种周期，实际: {caps.get('frequencies')}"
    assert caps.get('historical_data') is True, "historical_data 应为 True"
    print(f"  [PASS] capabilities: frequencies={caps['frequencies']}, historical_data={caps['historical_data']}")


def check_daily_regression(plugin):
    """日线分支回归：仍走 ak.stock_zh_a_hist 且 period='daily'、YYYYMMDD 日期格式"""
    captured = {}

    def fake_hist(**kwargs):
        captured.update(kwargs)
        return make_daily_df()

    with mock.patch('akshare.stock_zh_a_hist', side_effect=fake_hist):
        df = plugin.get_kdata(symbol='000001', freq='D', start_date='2024-01-01', end_date='2024-01-05')

    assert captured.get('period') == 'daily', f"D 应映射为 period='daily'，实际: {captured.get('period')}"
    assert captured.get('start_date') == '20240101', f"日线日期应为 YYYYMMDD，实际: {captured.get('start_date')}"
    assert isinstance(df.index, pd.DatetimeIndex), "日线输出索引应为 DatetimeIndex"
    assert {'open', 'high', 'low', 'close', 'volume', 'amount'}.issubset(df.columns), \
        f"日线输出缺少标准列，实际列: {list(df.columns)}"
    print("  [PASS] 日线分支回归：period='daily'，YYYYMMDD 日期格式，输出标准化未受影响")


def main():
    plugin = AKSharePlugin()
    plugin.initialize({})

    print("[1] 分钟频率映射与参数传递")
    df = check_minute_freq_mapping(plugin)

    print("[2] 分钟分支调用与多频率映射")
    check_minute_branch_called(plugin)

    print("[3] 分钟线输出列标准化")
    check_minute_output_normalized(df)

    print("[4] capabilities 声明")
    check_capabilities(plugin)

    print("[5] 日线分支回归")
    check_daily_regression(plugin)

    print("\n=== 全部 PASS: AKShare 插件分钟线支持验证通过 ===")


if __name__ == '__main__':
    main()
