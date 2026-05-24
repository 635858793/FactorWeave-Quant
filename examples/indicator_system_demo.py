#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
指标系统演示脚本
展示如何使用新的指标系统计算各种指标
"""

import os
import sys

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from core.indicator_service import (
    calculate_indicator,
    get_indicator_metadata,
    get_all_indicators_metadata
)
import pandas as pd
import numpy as np
from loguru import logger
from matplotlib.gridspec import GridSpec

try:
    import matplotlib.pyplot as plt
    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False
    plt = None

# 导入指标计算模块

def load_sample_data():
    """加载示例数据"""
    # 尝试加载测试数据，如果不存在则创建随机数据
    try:
        test_data_path = os.path.join(
            parent_dir, 'test', 'fixtures', 'stock_data_100d.csv')
        if os.path.exists(test_data_path):
            df = pd.read_csv(test_data_path)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df
        else:
            logger.warning(f"测试数据文件 {test_data_path} 不存在，将创建随机数据")
    except Exception as e:
        logger.error(f"加载测试数据时发生错误: {str(e)}，将创建随机数据")

    # 创建随机数据
    np.random.seed(42)
    dates = pd.date_range(start='2020-01-01', periods=100)
    close = np.random.random(100) * 100 + 100
    # 模拟价格走势
    for i in range(1, len(close)):
        close[i] = close[i-1] * (1 + (np.random.random() - 0.5) * 0.05)

    high = close * (1 + np.random.random(100) * 0.03)
    low = close * (1 - np.random.random(100) * 0.03)
    open_price = low + np.random.random(100) * (high - low)
    volume = np.random.random(100) * 1000000 + 500000

    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)

    return df

def plot_indicators(df):
    """绘制指标图表"""
    fig = plt.figure(figsize=(12, 10))
    gs = GridSpec(4, 1, figure=fig, height_ratios=[2, 1, 1, 1])

    # 价格图
    ax1 = fig.add_subplot(gs[0])
    ax1.set_title('价格和MA')
    ax1.plot(df.index, df['close'], label='Close')
    if 'MA' in df.columns:
        ax1.plot(df.index, df['MA'], label='MA(20)')
    if 'BBUpper' in df.columns and 'BBMiddle' in df.columns and 'BBLower' in df.columns:
        ax1.plot(df.index, df['BBUpper'], 'r--', label='BB Upper')
        ax1.plot(df.index, df['BBMiddle'], 'g--', label='BB Middle')
        ax1.plot(df.index, df['BBLower'], 'r--', label='BB Lower')
    ax1.legend()
    ax1.grid(True)

    # MACD图
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.set_title('MACD')
    if 'MACD' in df.columns and 'MACDSignal' in df.columns and 'MACDHist' in df.columns:
        ax2.plot(df.index, df['MACD'], label='MACD')
        ax2.plot(df.index, df['MACDSignal'], label='Signal')
        ax2.bar(df.index, df['MACDHist'], label='Histogram', alpha=0.5)
    ax2.legend()
    ax2.grid(True)

    # RSI图
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.set_title('RSI')
    if 'RSI' in df.columns:
        ax3.plot(df.index, df['RSI'], label='RSI(14)')
        ax3.axhline(y=70, color='r', linestyle='--')
        ax3.axhline(y=30, color='g', linestyle='--')
    ax3.legend()
    ax3.grid(True)

    # KDJ图
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    ax4.set_title('KDJ')
    kdj_columns = ['K', 'D', 'J']
    if all(col in df.columns for col in kdj_columns):
        ax4.plot(df.index, df['K'], label='K')
        ax4.plot(df.index, df['D'], label='D')
        ax4.plot(df.index, df['J'], label='J')
    ax4.legend()
    ax4.grid(True)

    plt.tight_layout()
    plt.show()

def main():
    """主函数"""
    logger.info("指标系统演示")
    logger.info("=" * 50)

    # 加载数据
    df = load_sample_data()
    logger.info(f"加载了 {len(df)} 条数据")
    logger.info(df.head())
    logger.info("-" * 50)

    # 获取所有指标元数据
    indicators_meta = get_all_indicators_metadata()
    logger.info(f"系统中共有 {len(indicators_meta)} 个指标")
    for name, meta in indicators_meta.items():
        logger.info(f"- {name}: {meta['display_name']}")
    logger.info("-" * 50)

    # 计算MA指标
    logger.info("计算MA指标...")
    df_ma = calculate_indicator('MA', df, {'timeperiod': 20})
    logger.info(df_ma[['close', 'MA']].head())
    logger.info("-" * 50)

    # 计算MACD指标
    logger.info("计算MACD指标...")
    df_macd = calculate_indicator('MACD', df_ma, {
        'fastperiod': 12,
        'slowperiod': 26,
        'signalperiod': 9
    })

    # 检查MACD列是否存在
    macd_columns = ['MACD', 'MACDSignal', 'MACDHist']
    if all(col in df_macd.columns for col in macd_columns):
        logger.info(df_macd[['close', 'MA'] + macd_columns].head())
    else:
        logger.error("MACD指标计算失败")
        logger.error(df_macd.columns)
    logger.info("-" * 50)

    # 计算RSI指标
    logger.info("计算RSI指标...")
    df_rsi = calculate_indicator('RSI', df_macd, {'timeperiod': 14})

    # 检查RSI列是否存在
    if 'RSI' in df_rsi.columns:
        logger.info(df_rsi[['close', 'MA', 'RSI']].head())
    else:
        logger.error("RSI指标计算失败")
    logger.info("-" * 50)

    # 计算布林带指标
    logger.info("计算布林带指标...")
    df_bbands = calculate_indicator('BBANDS', df_rsi, {
        'timeperiod': 20,
        'nbdevup': 2.0,
        'nbdevdn': 2.0
    })

    # 检查布林带列是否存在
    bbands_columns = ['BBUpper', 'BBMiddle', 'BBLower']
    if all(col in df_bbands.columns for col in bbands_columns):
        logger.info(df_bbands[['close'] + bbands_columns].head())
    else:
        logger.error("布林带指标计算失败")
    logger.info("-" * 50)

    # 计算KDJ指标
    logger.info("计算KDJ指标...")
    df_kdj = calculate_indicator('KDJ', df_bbands, {
        'fastk_period': 9,
        'slowk_period': 3,
        'slowd_period': 3
    })

    # 检查KDJ列是否存在
    kdj_columns = ['K', 'D', 'J']
    if all(col in df_kdj.columns for col in kdj_columns):
        logger.info(df_kdj[['close'] + kdj_columns].head())
    else:
        logger.error("KDJ指标计算失败")
        logger.error("可用的列:", df_kdj.columns)
    logger.info("-" * 50)

    # 绘制指标图表
    if _MPL_AVAILABLE:
        logger.info("绘制指标图表...")
        plot_indicators(df_kdj)
    else:
        logger.warning("matplotlib 不可用，跳过图表绘制")

if __name__ == "__main__":
    main()
