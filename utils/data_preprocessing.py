from loguru import logger
"""
数据预处理工具模块
统一处理K线数据的预处理逻辑，避免重复代码
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Union, Any

# 日志系统已迁移到Loguru
# 直接使用 logger.info(), logger.error() 等方法

def kdata_preprocess(df: Union[pd.DataFrame, Any], context: str = "分析") -> Optional[pd.DataFrame]:
    """
    K线数据预处理：检查并修正所有关键字段，统一处理datetime字段

    Args:
        df: 输入数据，可以是DataFrame或其他格式
        context: 处理上下文，用于日志记录

    Returns:
        pd.DataFrame: 预处理后的标准化DataFrame，如果处理失败返回None
    """
    # 使用全局logger

    # 如果不是DataFrame，尝试转换或直接返回
    if not isinstance(df, pd.DataFrame):
        if df is None:
            logger.warning(f"[{context}] 输入数据为None")
            return None

        # 尝试转换为DataFrame
        try:
            if hasattr(df, '__iter__') and not isinstance(df, str):
                df = pd.DataFrame(df)
            else:
                logger.warning(f"[{context}] 无法将输入数据转换为DataFrame")
                return None
        except Exception as e:
            logger.error(f"[{context}] 数据转换失败: {str(e)}")
            return None

    if df.empty:
        logger.warning(f"[{context}] 输入DataFrame为空")
        return df

    # 创建副本避免修改原数据
    df = df.copy()

    # 处理datetime字段
    has_datetime = False
    datetime_in_index = False

    # 检查datetime是否在索引中
    if isinstance(df.index, pd.DatetimeIndex):
        has_datetime = True
        datetime_in_index = True
    elif hasattr(df.index, 'name') and df.index.name in ['datetime', 'date', 'time']:
        try:
            df.index = pd.to_datetime(df.index)
            has_datetime = True
            datetime_in_index = True
        except Exception:
            pass

    # 检查datetime是否在列中
    datetime_cols = ['datetime', 'date', 'time', 'timestamp']
    datetime_col_name = None
    for col in datetime_cols:
        if col in df.columns:
            datetime_col_name = col
            has_datetime = True
            break

    # 如果datetime不存在，尝试推断或创建
    if not has_datetime:
        if len(df.index) > 0 and not isinstance(df.index, pd.RangeIndex):
            try:
                # 尝试将索引转换为datetime
                df.index = pd.to_datetime(df.index)
                has_datetime = True
                datetime_in_index = True
                logger.info(f"[{context}] 从索引推断datetime字段")
            except Exception:
                pass

        if not has_datetime:
            # 完全没有datetime信息，创建默认时间序列
            logger.warning(f"[{context}] 缺少datetime字段，自动补全")
            df['datetime'] = pd.date_range(
                start='2023-01-01', periods=len(df), freq='D')
            datetime_col_name = 'datetime'
            has_datetime = True

    # 标准化datetime处理
    if datetime_col_name and not datetime_in_index:
        # datetime在列中，转换为datetime类型并设置为索引
        try:
            df[datetime_col_name] = pd.to_datetime(df[datetime_col_name])
            df = df.set_index(datetime_col_name)
            datetime_in_index = True
        except Exception as e:
            logger.warning(f"[{context}] datetime列转换失败: {str(e)}")
    elif datetime_in_index and 'datetime' not in df.columns:
        # datetime在索引中，复制到列中以保持兼容性
        df['datetime'] = df.index

    # 确保索引名称为datetime
    if datetime_in_index and df.index.name != 'datetime':
        df.index.name = 'datetime'

    # 检查和补全必要字段
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        logger.warning(f"[{context}] 缺少字段: {missing_cols}，自动补全")

        for col in missing_cols:
            if col == 'volume':
                df[col] = 0.0
            elif col in ['open', 'high', 'low']:
                # 用收盘价填充其他价格字段
                if 'close' in df.columns:
                    df[col] = df['close']
                else:
                    df[col] = 1.0  # 默认价格
            elif col == 'close':
                # 如果连收盘价都没有，尝试用其他价格字段
                for price_col in ['open', 'high', 'low']:
                    if price_col in df.columns:
                        df[col] = df[price_col]
                        break
                else:
                    df[col] = 1.0  # 默认价格

    # 数据类型转换和清洗
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            # 转换为数值类型
            df[col] = pd.to_numeric(df[col], errors='coerce')

            # 检查异常值
            before_count = len(df)

            # 移除负值和NaN
            if col == 'volume':
                df = df[df[col].notna() & (df[col] >= 0)]
            else:  # 价格字段
                df = df[df[col].notna() & (df[col] > 0)]

            after_count = len(df)
            if after_count < before_count:
                logger.info(
                    f"[{context}] 已过滤{before_count-after_count}行{col}异常数据")

    # 检查价格逻辑关系
    if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        # 修正价格逻辑错误：high应该是最高价，low应该是最低价
        df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
        df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)

    # 最终检查
    if df.empty:
        logger.warning(f"[{context}] 数据预处理后为空")
        return df

    # 添加code字段（如果不存在）
    if 'code' not in df.columns:
        df['code'] = ''

    # 添加amount字段（如果不存在）
    if 'amount' not in df.columns and 'close' in df.columns and 'volume' in df.columns:
        df['amount'] = df['close'] * df['volume']

    # 按时间排序
    if datetime_in_index:
        df = df.sort_index()
    elif 'datetime' in df.columns:
        df = df.sort_values('datetime')

    # 移除重复行
    initial_len = len(df)
    if datetime_in_index:
        df = df[~df.index.duplicated(keep='last')]
    elif 'datetime' in df.columns:
        df = df.drop_duplicates(subset=['datetime'], keep='last')

    if len(df) < initial_len:
        logger.info(f"[{context}] 移除了{initial_len - len(df)}行重复数据")

    logger.debug(f"[{context}] 数据预处理完成，共{len(df)}行数据")
    return df

def validate_kdata(df: pd.DataFrame, context: str = "验证") -> bool:
    """
    验证K线数据的有效性

    Args:
        df: 待验证的DataFrame
        context: 验证上下文

    Returns:
        bool: 数据是否有效
    """
    # 使用全局logger

    if df is None or df.empty:
        logger.warning(f"[{context}] 数据为空")
        return False

    # 检查必要列
    required_columns = ['open', 'high', 'low', 'close']
    missing_columns = [
        col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.warning(f"[{context}] 缺少必要列: {missing_columns}")
        return False

    # 检查数据量
    if len(df) < 2:
        logger.warning(f"[{context}] 数据量不足，至少需要2行数据")
        return False

    # 检查价格数据有效性
    for col in required_columns:
        if df[col].isna().all():
            logger.warning(f"[{context}] {col}列全部为空")
            return False

        if (df[col] <= 0).any():
            logger.warning(f"[{context}] {col}列存在非正数值")
            return False

    logger.debug(f"[{context}] 数据验证通过")
    return True

def standardize_stock_code(code: str) -> str:
    """
    标准化股票代码格式

    Args:
        code: 原始股票代码

    Returns:
        str: 标准化后的股票代码
    """
    if not code or not isinstance(code, str):
        return ''

    code = code.strip().upper()

    # 如果已经有市场前缀，直接返回
    if code.startswith(('SH', 'SZ', 'BJ', 'HK', 'US')):
        return code.lower()

    # 根据代码规则添加市场前缀
    if code.startswith('6'):
        return f'sh{code}'
    elif code.startswith(('0', '3')):
        return f'sz{code}'
    elif code.startswith('8') or code.startswith('43') or code.startswith('9'):
        return f'bj{code}'
    else:
        # 默认深圳市场
        return f'sz{code}'

def calculate_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算基础技术指标

    Args:
        df: K线数据DataFrame

    Returns:
        pd.DataFrame: 包含基础指标的DataFrame
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    try:
        # 移动平均线
        for period in [5, 10, 20, 60]:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()

        # 避免除零
        avg_loss = avg_loss.replace(0, 0.00001)
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # 布林带
        ma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        df['boll_upper'] = ma20 + 2 * std20
        df['boll_lower'] = ma20 - 2 * std20
        df['boll_mid'] = ma20

    except Exception as e:
        # 使用全局logger
        logger.error(f"计算基础指标失败: {str(e)}")

    return df

# 向后兼容的函数别名
def _kdata_preprocess(df, context="分析"):
    """向后兼容的函数别名"""
    return kdata_preprocess(df, context)
