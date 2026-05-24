from loguru import logger
"""
FactorWeave-Quant 指标算法模块
提供技术指标计算功能，支持ta-lib和自定义实现
"""

import numpy as np
import pandas as pd
from functools import lru_cache
import importlib

logger = logger

# 尝试导入ta-lib
try:
    talib = importlib.import_module('talib')
    TALIB_AVAILABLE = True
    logger.info("Ta-lib 库可用")
except ImportError:
    talib = None
    TALIB_AVAILABLE = False
    logger.warning("Ta-lib 库不可用，使用自定义实现")


def get_talib_real_indicator_list():
    """获取Ta-lib指标列表"""
    if TALIB_AVAILABLE and talib:
        try:
            # 返回Ta-lib中的主要指标
            return [
                'SMA', 'EMA', 'WMA', 'DEMA', 'TEMA', 'TRIMA',
                'KAMA', 'MAMA', 'T3',
                'MACD', 'MACDEXT', 'MACDFIX',
                'RSI', 'STOCH', 'STOCHF', 'STOCHRSI',
                'WILLR', 'ADX', 'ADXR', 'APO', 'AROON', 'AROONOSC',
                'BOP', 'CCI', 'CMO', 'DX', 'MFI', 'MINUS_DI',
                'MINUS_DM', 'MOM', 'PLUS_DI', 'PLUS_DM', 'PPO',
                'ROC', 'ROCP', 'ROCR', 'ROCR100', 'TRIX', 'ULTOSC',
                'BBANDS', 'DEMA', 'EMA', 'HT_TRENDLINE', 'KAMA',
                'MA', 'MIDPOINT', 'MIDPRICE', 'SAR', 'SAREXT',
                'SMA', 'T3', 'TEMA', 'TRIMA', 'WMA'
            ]
        except Exception as e:
            logger.error(f"获取Ta-lib指标列表失败: {e}")

    # 返回默认指标列表
    return [
        'SMA', 'EMA', 'MACD', 'RSI', 'STOCH', 'BBANDS',
        'CCI', 'ADX', 'WILLR', 'MOM', 'ROC'
    ]


def get_talib_category():
    """获取Ta-lib指标分类"""
    return {
        'Overlap Studies': [
            'BBANDS', 'DEMA', 'EMA', 'HT_TRENDLINE', 'KAMA', 'MA', 'MAMA',
            'MAVP', 'MIDPOINT', 'MIDPRICE', 'SAR', 'SAREXT', 'SMA', 'T3',
            'TEMA', 'TRIMA', 'WMA'
        ],
        'Momentum Indicators': [
            'ADX', 'ADXR', 'APO', 'AROON', 'AROONOSC', 'BOP', 'CCI', 'CMO',
            'DX', 'MACD', 'MACDEXT', 'MACDFIX', 'MFI', 'MINUS_DI', 'MINUS_DM',
            'MOM', 'PLUS_DI', 'PLUS_DM', 'PPO', 'ROC', 'ROCP', 'ROCR',
            'ROCR100', 'RSI', 'STOCH', 'STOCHF', 'STOCHRSI', 'TRIX', 'ULTOSC', 'WILLR'
        ],
        'Volume Indicators': [
            'AD', 'ADOSC', 'OBV'
        ],
        'Volatility Indicators': [
            'ATR', 'NATR', 'TRANGE'
        ],
        'Price Transform': [
            'AVGPRICE', 'MEDPRICE', 'TYPPRICE', 'WCLPRICE'
        ]
    }

# --- MA ---


def calc_ma(close: pd.Series, n: int) -> pd.Series:
    """计算移动平均线，优先用ta-lib，自动回退pandas实现"""
    try:
        if not isinstance(close, pd.Series):
            raise TypeError("calc_ma: close参数必须为pd.Series类型")
        if TALIB_AVAILABLE and talib:
            return pd.Series(talib.MA(close.values, timeperiod=n), index=close.index, name=f"MA{n}")
        else:
            return close.rolling(window=n).mean().rename(f"MA{n}")
    except Exception as e:
        logger.error(f"计算MA指标失败: {e}")
        return pd.Series([float('nan')] * len(close), index=close.index, name=f"MA{n}")

# --- MACD ---


def calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    try:
        if not isinstance(close, pd.Series):
            raise TypeError("calc_macd: close参数必须为pd.Series类型")

        if TALIB_AVAILABLE and talib:
            macd, macdsignal, macdhist = talib.MACD(
                close.values, fastperiod=fast, slowperiod=slow, signalperiod=signal)
            idx = close.index
            return (pd.Series(macd, index=idx, name="MACD"),
                    pd.Series(macdsignal, index=idx, name="MACD_signal"),
                    pd.Series(macdhist, index=idx, name="MACD_hist"))
        else:
            # 自定义MACD实现
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal).mean()
            histogram = macd - signal_line
            return (macd.rename("MACD"),
                    signal_line.rename("MACD_signal"),
                    histogram.rename("MACD_hist"))
    except Exception as e:
        logger.error(f"计算MACD指标失败: {e}")
        idx = close.index if isinstance(close, pd.Series) else None
        empty_series = pd.Series([float('nan')] * len(close), index=idx)
        return (empty_series.rename("MACD"),
                empty_series.rename("MACD_signal"),
                empty_series.rename("MACD_hist"))

# --- RSI ---


def calc_rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """计算RSI指标"""
    try:
        if not isinstance(close, pd.Series):
            raise TypeError("calc_rsi: close参数必须为pd.Series类型")

        if TALIB_AVAILABLE and talib:
            return pd.Series(talib.RSI(close.values, timeperiod=n), index=close.index, name=f"RSI{n}")
        else:
            # 自定义RSI实现
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/n, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/n, adjust=False).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.rename(f"RSI{n}")
    except Exception as e:
        logger.error(f"计算RSI指标失败: {e}")
        return pd.Series([float('nan')] * len(close), index=close.index, name=f"RSI{n}")

# --- KDJ ---


def calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, m1: int = 3, m2: int = 3):
    """计算KDJ指标"""
    try:
        if TALIB_AVAILABLE and talib:
            k, d = talib.STOCH(high.values, low.values, close.values,
                               fastk_period=n, slowk_period=m1, slowd_period=m2)
            k_series = pd.Series(k, index=close.index, name='K')
            d_series = pd.Series(d, index=close.index, name='D')
            j_series = 3 * k_series - 2 * d_series
            j_series.name = 'J'
            return k_series, d_series, j_series
        else:
            # 自定义KDJ实现
            lowest_low = low.rolling(window=n).min()
            highest_high = high.rolling(window=n).max()
            rsv = 100 * (close - lowest_low) / (highest_high - lowest_low)
            k = rsv.ewm(alpha=1/m1).mean()
            d = k.ewm(alpha=1/m2).mean()
            j = 3 * k - 2 * d
            return k.rename('K'), d.rename('D'), j.rename('J')
    except Exception as e:
        logger.error(f"计算KDJ指标失败: {e}")
        empty_series = pd.Series([float('nan')] * len(close), index=close.index)
        return (empty_series.rename('K'),
                empty_series.rename('D'),
                empty_series.rename('J'))


# 导出函数列表
__all__ = [
    'get_talib_real_indicator_list',
    'get_talib_category',
    'calc_ma',
    'calc_macd',
    'calc_rsi',
    'calc_kdj',
    'TALIB_AVAILABLE'
]