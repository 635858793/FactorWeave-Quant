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


# 渲染判组唯一来源（R282 统一 left_panel/middle_panel 判组口径）：
# 这些指标在 indicator_mixin 有专门渲染分支（MA/MACD/RSI/BOLL + 本地 KDJ），
# 其余一律走 TA-Lib 通用分支（talib 组）。
# 注意：CCI/OBV 不在此列（R242 起有意改走 talib 组 + TA-Lib 直算），
# left_panel 的 UI 分组（type）与渲染判组无关，事件只传递指标名。
BUILTIN_INDICATORS = frozenset({'MA', 'MACD', 'RSI', 'BOLL', 'KDJ'})


def get_talib_real_indicator_list():
    """获取Ta-lib指标列表（动态枚举：TA-Lib支持哪些图表指标就展示哪些，随TA-Lib版本自动扩展）

    R264 由硬编码46个改为动态枚举 talib.get_functions()：
    - 排除形态识别（CDL*，由形态识别系统处理）
    - 排除不适合图表叠加的非分析类（数学运算/数学变换/统计/周期/价格变换/MAVP）
    保留 Overlap/Momentum/Volume/Volatility/部分统计类 = 图表指标全集（约59个）。
    计算端 TALIB_OUTPUT_MAP（unified_indicator_service.py）已同步覆盖该全集，
    新增TA-Lib函数时：若属于保留类会自动进入列表，计算端补一行输出映射即可。
    """
    if TALIB_AVAILABLE and talib:
        try:
            # 不适合图表叠加的指标（Math/Stat/Cycle/PriceTransform/MAVP）
            excluded = {
                # Math Operators（数值运算，非行情分析指标）
                'ADD', 'DIV', 'MAX', 'MAXINDEX', 'MIN', 'MININDEX', 'MINMAX',
                'MINMAXINDEX', 'MULT', 'SUB', 'SUM',
                # Math Transform（数学变换）
                'ACOS', 'ASIN', 'ATAN', 'CEIL', 'COS', 'COSH', 'EXP', 'FLOOR',
                'LN', 'LOG10', 'SIN', 'SINH', 'SQRT', 'TAN', 'TANH',
                # Statistic Functions（统计类保留 LINEARREG*/STDDEV/TSF/VAR，排除双输入 BETA/CORREL）
                'BETA', 'CORREL',
                # Cycle Indicators（周期类，HT_TRENDLINE 已在 Overlap 中保留）
                'HT_DCPERIOD', 'HT_DCPHASE', 'HT_PHASOR', 'HT_SINE', 'HT_TRENDMODE',
                # Price Transform（价格变换，非分析指标）
                'AVGPRICE', 'MEDPRICE', 'TYPPRICE', 'WCLPRICE',
                # MAVP 需要周期数组参数，UI 无法配置
                'MAVP',
            }
            return [f for f in talib.get_functions()
                    if not f.startswith('CDL') and f not in excluded]
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
    """
    统一的KDJ指标计算函数（优先使用ta-lib，自动回退纯pandas实现）

    参数:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        n: RSV计算周期（默认9）
        m1: K值平滑周期（默认3）
        m2: D值平滑周期（默认3）

    返回:
        Tuple[pd.Series, pd.Series, pd.Series]: (K, D, J) 序列
    """
    try:
        if TALIB_AVAILABLE and talib:
            k, d = talib.STOCH(high.values.astype('float64'),
                               low.values.astype('float64'),
                               close.values.astype('float64'),
                               fastk_period=n, slowk_period=m1, slowd_period=m2)
            k_series = pd.Series(k, index=close.index, name='K')
            d_series = pd.Series(d, index=close.index, name='D')
            j_series = 3 * k_series - 2 * d_series
            j_series.name = 'J'
            return k_series, d_series, j_series
        else:
            lowest_low = low.rolling(window=n).min()
            highest_high = high.rolling(window=n).max()
            denom = highest_high - lowest_low
            rsv = pd.Series(50.0, index=close.index)
            nonzero_mask = denom != 0
            rsv[nonzero_mask] = 100 * ((close[nonzero_mask] - lowest_low[nonzero_mask]) / denom[nonzero_mask])
            k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
            d = k.ewm(alpha=1 / m2, adjust=False).mean()
            j = 3 * k - 2 * d
            return k.rename('K'), d.rename('D'), j.rename('J')
    except Exception as e:
        logger.error(f"计算KDJ指标失败: {e}")
        empty_series = pd.Series([float('nan')] * len(close), index=close.index)
        return (empty_series.rename('K'),
                empty_series.rename('D'),
                empty_series.rename('J'))


def calc_kdj_dataframe(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """
    统一的KDJ指标计算函数 - DataFrame输入/输出版本
    内部调用calc_kdj实现

    参数:
        df: 包含high、low、close列的DataFrame
        n: RSV计算周期（默认9）
        m1: K值平滑周期（默认3）
        m2: D值平滑周期（默认3）

    返回:
        DataFrame: 原始df加K、D、J列
    """
    k, d, j = calc_kdj(df['high'], df['low'], df['close'], n=n, m1=m1, m2=m2)
    result = df.copy()
    result['K'] = k
    result['D'] = d
    result['J'] = j
    return result


def calc_kdj_dict(high: pd.Series, low: pd.Series, close: pd.Series,
                  window: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> dict:
    """
    统一的KDJ指标计算函数 - 字典输出版本
    内部调用calc_kdj实现

    参数:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        window: RSV计算周期（默认9）
        k_smooth: K值平滑周期（默认3）
        d_smooth: D值平滑周期（默认3）

    返回:
        Dict[str, pd.Series]: {'K': ..., 'D': ..., 'J': ...}
    """
    k, d, j = calc_kdj(high, low, close, n=window, m1=k_smooth, m2=d_smooth)
    return {'K': k, 'D': d, 'J': j}


# 导出函数列表
__all__ = [
    'get_talib_real_indicator_list',
    'get_talib_category',
    'calc_ma',
    'calc_macd',
    'calc_rsi',
    'calc_kdj',
    'calc_kdj_dataframe',
    'calc_kdj_dict',
    'TALIB_AVAILABLE'
]