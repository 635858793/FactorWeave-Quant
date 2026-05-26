#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
震荡类指标
包含MACD、RSI、KDJ等震荡类指标的计算函数
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

def calculate_macd(df: pd.DataFrame, fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9) -> pd.DataFrame:
    """
    计算MACD指标

    参数:
        df: 包含close列的DataFrame
        fastperiod: 快速EMA周期
        slowperiod: 慢速EMA周期
        signalperiod: 信号线周期

    返回:
        DataFrame: 添加了MACD、MACDSignal、MACDHist列的DataFrame
    """
    result = df.copy()
    try:
        close = df['close']

        if TALIB_AVAILABLE:
            macd, macdsignal, macdhist = talib.MACD(
                close.values,
                fastperiod=fastperiod,
                slowperiod=slowperiod,
                signalperiod=signalperiod
            )
            result['MACD'] = pd.Series(macd, index=close.index)
            result['MACDSignal'] = pd.Series(macdsignal, index=close.index)
            result['MACDHist'] = pd.Series(macdhist, index=close.index)
        else:
            # 使用pandas实现
            exp1 = close.ewm(span=fastperiod, adjust=False).mean()
            exp2 = close.ewm(span=slowperiod, adjust=False).mean()
            macd = exp1 - exp2
            macdsignal = macd.ewm(span=signalperiod, adjust=False).mean()
            macdhist = macd - macdsignal

            result['MACD'] = macd
            result['MACDSignal'] = macdsignal
            result['MACDHist'] = macdhist

    except Exception as e:
        # 返回全NaN
        for col in ['MACD', 'MACDSignal', 'MACDHist']:
            result[col] = pd.Series([float('nan')] * len(df), index=df.index)

    return result

def calculate_rsi(df: pd.DataFrame, timeperiod: int = 14) -> pd.DataFrame:
    """
    计算RSI指标

    参数:
        df: 包含close列的DataFrame
        timeperiod: 计算周期

    返回:
        DataFrame: 添加了RSI列的DataFrame
    """
    result = df.copy()
    try:
        close = df['close']

        if TALIB_AVAILABLE:
            rsi = talib.RSI(close.values, timeperiod=timeperiod)
            result['RSI'] = pd.Series(rsi, index=close.index)
        else:
            # 使用pandas实现
            delta = close.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            avg_gain = gain.ewm(alpha=1/timeperiod, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/timeperiod, adjust=False).mean()

            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))

            result['RSI'] = rsi

    except Exception as e:
        # 返回全NaN
        result['RSI'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result

def calculate_kdj(df: pd.DataFrame, fastk_period: int = 9, slowk_period: int = 3, slowd_period: int = 3) -> pd.DataFrame:
    """
    计算KDJ指标（委托给统一实现core.indicators.indicators_algorithm.calc_kdj_dataframe）

    参数:
        df: 包含high、low、close列的DataFrame
        fastk_period: RSV周期
        slowk_period: K值平滑周期
        slowd_period: D值平滑周期

    返回:
        DataFrame: 添加了K、D、J列的DataFrame
    """
    from core.indicators.indicators_algorithm import calc_kdj_dataframe
    return calc_kdj_dataframe(df, n=fastk_period, m1=slowk_period, m2=slowd_period)

def calculate_cci(df: pd.DataFrame, timeperiod: int = 14) -> pd.DataFrame:
    """
    计算CCI指标

    参数:
        df: 包含high、low、close列的DataFrame
        timeperiod: 计算周期

    返回:
        DataFrame: 添加了CCI列的DataFrame
    """
    result = df.copy()
    try:
        high = df['high']
        low = df['low']
        close = df['close']

        if TALIB_AVAILABLE:
            cci = talib.CCI(high.values, low.values,
                            close.values, timeperiod=timeperiod)
            result['CCI'] = pd.Series(cci, index=close.index)
        else:
            tp = (high + low + close) / 3
            tp_arr = tp.values
            ma = tp.rolling(window=timeperiod).mean()
            windows = np.lib.stride_tricks.sliding_window_view(tp_arr, timeperiod)
            wm = windows.mean(axis=1)
            mad = np.abs(windows - wm[:, np.newaxis]).mean(axis=1)
            md = np.full(len(tp_arr), np.nan)
            md[timeperiod - 1:] = mad
            md = pd.Series(md, index=tp.index)
            cci = (tp - ma) / (0.015 * md.replace(0, np.nan))
            result['CCI'] = cci

    except Exception as e:
        # 返回全NaN
        result['CCI'] = pd.Series([float('nan')] * len(df), index=df.index)

    return result

def calculate_stoch(df: pd.DataFrame, fastk_period: int = 5, slowk_period: int = 3, slowd_period: int = 3,
                    slowk_matype: int = 0, slowd_matype: int = 0) -> pd.DataFrame:
    """
    计算STOCH(随机指标)

    参数:
        df: 包含high、low、close列的DataFrame
        fastk_period: K值周期
        slowk_period: K值平滑周期
        slowk_matype: K值平滑类型
        slowd_period: D值周期
        slowd_matype: D值平滑类型

    返回:
        DataFrame: 添加了SlowK、SlowD列的DataFrame
    """
    result = df.copy()
    try:
        high = df['high']
        low = df['low']
        close = df['close']

        if TALIB_AVAILABLE:
            slowk, slowd = talib.STOCH(
                high.values,
                low.values,
                close.values,
                fastk_period=fastk_period,
                slowk_period=slowk_period,
                slowk_matype=slowk_matype,
                slowd_period=slowd_period,
                slowd_matype=slowd_matype
            )
            result['SlowK'] = pd.Series(slowk, index=close.index)
            result['SlowD'] = pd.Series(slowd, index=close.index)
        else:
            # 使用pandas实现
            # 计算最高价和最低价的滚动窗口
            low_min = low.rolling(window=fastk_period).min()
            high_max = high.rolling(window=fastk_period).max()

            # 计算FastK
            denom = high_max - low_min
            fastk = pd.Series(np.nan, index=close.index)
            nonzero_mask = denom != 0
            fastk[nonzero_mask] = 100 * ((close[nonzero_mask] - low_min[nonzero_mask]) / denom[nonzero_mask])

            # 计算SlowK (FastK的移动平均)
            if slowk_matype == 0:  # SMA
                slowk = fastk.rolling(window=slowk_period).mean()
            else:  # 默认使用SMA
                slowk = fastk.rolling(window=slowk_period).mean()

            # 计算SlowD (SlowK的移动平均)
            if slowd_matype == 0:  # SMA
                slowd = slowk.rolling(window=slowd_period).mean()
            else:  # 默认使用SMA
                slowd = slowk.rolling(window=slowd_period).mean()

            result['SlowK'] = slowk
            result['SlowD'] = slowd

    except Exception as e:
        # 返回全NaN
        for col in ['SlowK', 'SlowD']:
            result[col] = pd.Series([float('nan')] * len(df), index=df.index)

    return result
