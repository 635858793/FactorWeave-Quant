#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
成交量类指标
包含OBV等成交量类指标的计算函数
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

def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算能量潮(OBV)指标

    参数:
        df: 包含close和volume列的DataFrame

    返回:
        DataFrame: 添加了OBV列的DataFrame
    """
    result = df.copy()
    try:
        close = df['close']
        volume = df['volume']

        if TALIB_AVAILABLE:
            obv = talib.OBV(close.values, volume.values)
            result['OBV'] = pd.Series(obv, index=close.index)
        else:
            close_diff = close.diff().fillna(0)

            # 计算OBV (向量化): OBV = cumsum(sign(Δclose) * volume)
            volume_arr = volume.values
            obv_values = (np.sign(close_diff.values) * volume_arr).cumsum()
            obv = pd.Series(obv_values, index=close.index)

            result['OBV'] = obv

    except Exception as e:
        # 返回全NaN
        result['OBV'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result

def calculate_ad(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算A/D线(Accumulation/Distribution Line)

    参数:
        df: 包含high、low、close和volume列的DataFrame

    返回:
        DataFrame: 添加了AD列的DataFrame
    """
    result = df.copy()
    try:
        high = df['high']
        low = df['low']
        close = df['close']
        volume = df['volume']

        if TALIB_AVAILABLE:
            result['AD'] = pd.Series(
                talib.AD(high.values, low.values, close.values, volume.values),
                index=close.index
            )
        else:
            # 使用pandas实现
            clv = ((close - low) - (high - close)) / \
                (high - low).replace(0, 1e-10)
            ad = (clv * volume).cumsum()

            result['AD'] = ad

    except Exception as e:
        # 返回全NaN
        result['AD'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result

def calculate_cmf(df: pd.DataFrame, timeperiod: int = 20) -> pd.DataFrame:
    """
    计算CMF(Chaikin Money Flow)

    参数:
        df: 包含high、low、close和volume列的DataFrame
        timeperiod: 计算周期

    返回:
        DataFrame: 添加了CMF列的DataFrame
    """
    result = df.copy()
    try:
        high = df['high']
        low = df['low']
        close = df['close']
        volume = df['volume']

        # 计算资金流量乘数(Money Flow Multiplier)
        mfm = ((close - low) - (high - close)) / (high - low).replace(0, 1e-10)

        # 计算资金流量(Money Flow Volume)
        mfv = mfm * volume

        # 计算Chaikin Money Flow
        cmf = mfv.rolling(window=timeperiod).sum(
        ) / volume.rolling(window=timeperiod).sum().replace(0, 1e-10)

        result['CMF'] = cmf

    except Exception as e:
        # 返回全NaN
        result['CMF'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result
