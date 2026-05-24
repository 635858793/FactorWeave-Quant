"""
数据格式化工具模块

提供数值、日期、K线数据等格式化功能，所有外部导入均受 ImportError 保护。
"""

from loguru import logger

try:
    import numpy as np
except ImportError:
    np = None
    logger.warning("formatting_utils: numpy 不可用，部分功能受限")

try:
    import pandas as pd
except ImportError:
    pd = None
    logger.warning("formatting_utils: pandas 不可用，部分功能受限")

try:
    from datetime import datetime, timedelta
except ImportError:
    datetime = None
    timedelta = None

try:
    from functools import lru_cache
except ImportError:
    def lru_cache(*args, **kwargs):
        return lambda f: f


@lru_cache(maxsize=256)
def format_price(price, decimals=2):
    """格式化价格"""
    if price is None:
        return "--"
    try:
        return f"{float(price):.{decimals}f}"
    except (ValueError, TypeError):
        return str(price)


@lru_cache(maxsize=256)
def format_percentage(value, decimals=2):
    """格式化百分比"""
    if value is None:
        return "--"
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)


@lru_cache(maxsize=256)
def format_volume(volume):
    """格式化成交量"""
    if volume is None:
        return "--"
    try:
        v = float(volume)
        if v >= 1e8:
            return f"{v / 1e8:.2f}亿"
        elif v >= 1e4:
            return f"{v / 1e4:.2f}万"
        else:
            return f"{v:.0f}"
    except (ValueError, TypeError):
        return str(volume)


@lru_cache(maxsize=256)
def format_amount(amount, decimals=2):
    """格式化金额"""
    if amount is None:
        return "--"
    try:
        a = float(amount)
        if abs(a) >= 1e8:
            return f"{a / 1e8:.{decimals}f}亿"
        elif abs(a) >= 1e4:
            return f"{a / 1e4:.{decimals}f}万"
        else:
            return f"{a:.{decimals}f}"
    except (ValueError, TypeError):
        return str(amount)


def format_datetime(dt, fmt="%Y-%m-%d %H:%M:%S"):
    """格式化日期时间"""
    if dt is None:
        return "--"
    try:
        if isinstance(dt, str):
            return dt
        if hasattr(dt, 'strftime'):
            return dt.strftime(fmt)
        return str(dt)
    except Exception:
        return str(dt)


@lru_cache(maxsize=256)
def format_ratio(ratio, decimals=4):
    """格式化比率"""
    if ratio is None:
        return "--"
    try:
        return f"{float(ratio):.{decimals}f}"
    except (ValueError, TypeError):
        return str(ratio)


def format_kline_columns(df):
    """标准化K线DataFrame列名"""
    if pd is None or df is None:
        return df
    if not isinstance(df, pd.DataFrame):
        return df
    try:
        column_mapping = {
            'date': 'datetime',
            'time': 'datetime',
            'trade_date': 'datetime',
            'vol': 'volume',
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns and v not in df.columns})
    except Exception as e:
        logger.warning(f"formatting_utils: K线列名标准化失败: {e}")
    return df


def format_dataframe_preview(df, max_rows=10, max_cols=None):
    """生成DataFrame预览字符串"""
    if pd is None or df is None:
        return "数据不可用"
    try:
        if not isinstance(df, pd.DataFrame):
            return str(df)
        cols = df.columns[:max_cols] if max_cols else df.columns
        preview = df[cols].head(max_rows)
        return preview.to_string(index=True)
    except Exception as e:
        logger.warning(f"formatting_utils: DataFrame预览生成失败: {e}")
        return str(df)