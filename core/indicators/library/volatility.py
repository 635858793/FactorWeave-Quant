#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
波动性类指标
包含ATR等波动性类指标的计算函数
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
import importlib

# 尝试导入TA-Lib
try:
    talib = importlib.import_module('talib')
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False

def calculate_atr(df: pd.DataFrame, timeperiod: int = 14) -> pd.DataFrame:
    """
    计算ATR(Average True Range)指标

    参数:
        df: 包含high、low、close列的DataFrame
        timeperiod: 计算周期

    返回:
        DataFrame: 添加了ATR列的DataFrame
    """
    result = df.copy()
    try:
        high = df['high']
        low = df['low']
        close = df['close']

        if TALIB_AVAILABLE:
            result['ATR'] = pd.Series(
                talib.ATR(high.values, low.values,
                          close.values, timeperiod=timeperiod),
                index=close.index
            )
        else:
            # 使用pandas实现
            # 计算真实范围(True Range)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)

            # 计算ATR
            atr = tr.ewm(alpha=1.0/timeperiod, adjust=False).mean()

            result['ATR'] = atr

    except Exception as e:
        # 返回全NaN
        result['ATR'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result

def calculate_natr(df: pd.DataFrame, timeperiod: int = 14) -> pd.DataFrame:
    """
    计算NATR(Normalized Average True Range)指标

    参数:
        df: 包含high、low、close列的DataFrame
        timeperiod: 计算周期

    返回:
        DataFrame: 添加了NATR列的DataFrame
    """
    result = df.copy()
    try:
        high = df['high']
        low = df['low']
        close = df['close']

        if TALIB_AVAILABLE:
            result['NATR'] = pd.Series(
                talib.NATR(high.values, low.values,
                           close.values, timeperiod=timeperiod),
                index=close.index
            )
        else:
            # 使用pandas实现
            # 计算真实范围(True Range)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)

            # 计算ATR
            atr = tr.ewm(alpha=1.0/timeperiod, adjust=False).mean()

            natr = 100 * atr / close.replace(0, np.nan)

            result['NATR'] = natr

    except Exception as e:
        # 返回全NaN
        result['NATR'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result

def calculate_stddev(df: pd.DataFrame, timeperiod: int = 5, nbdev: float = 1.0) -> pd.DataFrame:
    """
    计算价格标准差

    参数:
        df: 包含close列的DataFrame
        timeperiod: 计算周期
        nbdev: 标准差倍数

    返回:
        DataFrame: 添加了STDDEV列的DataFrame
    """
    result = df.copy()
    try:
        close = df['close']

        if TALIB_AVAILABLE:
            result['STDDEV'] = pd.Series(
                talib.STDDEV(close.values, timeperiod=timeperiod, nbdev=nbdev),
                index=close.index
            )
        else:
            # 使用pandas实现
            stddev = close.rolling(window=timeperiod).std() * nbdev

            result['STDDEV'] = stddev

    except Exception as e:
        # 返回全NaN
        result['STDDEV'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result
