import numpy as np
import pandas as pd
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False
import warnings
from typing import Dict, Any, Optional
from loguru import logger

def add_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    添加基本技术指标

    参数:
        df: 输入DataFrame

    返回:
        DataFrame: 添加了技术指标的DataFrame
    """
    result = df.copy()

    # 计算移动平均线
    close_data = result['close']
    if not isinstance(close_data, pd.Series):
        close_data = pd.Series(close_data)
    for window in [5, 10, 20, 50, 200]:
        result[f'MA{window}'] = talib.MA(close_data, timeperiod=window, matype=0)

    # 计算MACD
    close_data = result['close']
    if not isinstance(close_data, pd.Series):
        close_data = pd.Series(close_data)
    result['macd'], result['signal_line'], result['macd_hist'] = talib.MACD(
        close_data, fastperiod=12, slowperiod=26, signalperiod=9)

    # 计算RSI
    result['rsi'] = talib.RSI(result['close'], timeperiod=14)

    # 计算布林带
    result['upper_band'], _, result['lower_band'] = talib.BBANDS(
        result['close'], timeperiod=20, nbdevup=2, nbdevdn=2)

    # 计算变动率指标
    result['roc_5'] = result['close'].pct_change(periods=5) * 100
    result['roc_10'] = result['close'].pct_change(periods=10) * 100
    result['roc_20'] = result['close'].pct_change(periods=20) * 100

    # 计算价格与移动平均线偏离率
    result['bias_5'] = (result['close'] / result['MA5'] - 1) * 100
    result['bias_10'] = (result['close'] / result['MA10'] - 1) * 100
    result['bias_20'] = (result['close'] / result['MA20'] - 1) * 100

    # 计算强弱指标KDJ
    low_min = result['low'].rolling(window=9).min()
    high_max = result['high'].rolling(window=9).max()

    # 确保分母不为0
    denom = high_max - low_min
    denom = denom.replace(0, 0.00001)

    result['k_percent'] = 100 * ((result['close'] - low_min) / denom)
    result['k'] = result['k_percent'].ewm(alpha=1/3, adjust=False).mean()
    result['d'] = result['k'].ewm(alpha=1/3, adjust=False).mean()
    result['j'] = 3 * result['k'] - 2 * result['d']

    # 计算成交量指标
    if 'volume' in result.columns:
        result['volume_ma5'] = result['volume'].rolling(window=5).mean()
        result['volume_ma10'] = result['volume'].rolling(window=10).mean()
        result['volume_ratio'] = result['volume'] / result['volume_ma5']

    # 填充NaN值
    result = result.fillna(method='ffill').fillna(0)

    return result

def calculate_base_indicators(df):
    """
    计算基础技术指标

    参数:
        df: 输入DataFrame，包含OHLCV数据

    返回:
        DataFrame: 添加了基础指标的DataFrame
    """
    # 确保索引已排序
    df = df.sort_index()

    # 计算移动平均线
    close_data = df['close']
    if not isinstance(close_data, pd.Series):
        close_data = pd.Series(close_data)
    df['MA5'] = talib.MA(close_data, timeperiod=5, matype=0)
    df['MA10'] = talib.MA(close_data, timeperiod=10, matype=0)
    df['MA20'] = talib.MA(close_data, timeperiod=20, matype=0)
    df['MA60'] = talib.MA(close_data, timeperiod=60, matype=0)

    # 计算量价指标
    df['volume_ma5'] = df['volume'].rolling(window=5).mean()
    df['volume_ma10'] = df['volume'].rolling(window=10).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma5']

    # 计算价格相对位置
    df['price_position'] = (df['close'] - df['close'].rolling(window=20).min()) / \
        (df['close'].rolling(window=20).max() -
         df['close'].rolling(window=20).min())

    # 添加简单的价格变动指标
    df['price_change'] = df['close'].pct_change()
    df['price_change_5d'] = df['close'].pct_change(5)
    df['price_change_10d'] = df['close'].pct_change(10)
    df['price_change_20d'] = df['close'].pct_change(20)

    # 添加波动率指标
    df['volatility_5d'] = df['close'].pct_change().rolling(
        window=5).std() * np.sqrt(5)
    df['volatility_10d'] = df['close'].pct_change().rolling(
        window=10).std() * np.sqrt(10)
    df['volatility_20d'] = df['close'].pct_change().rolling(
        window=20).std() * np.sqrt(20)

    # 添加简单的量价关系指标
    df['volume_price_corr_5d'] = df['close'].rolling(
        window=5).corr(df['volume'])
    df['volume_price_corr_10d'] = df['close'].rolling(
        window=10).corr(df['volume'])

    # 添加布林带指标
    if not isinstance(close_data, pd.Series):
        close_data = pd.Series(close_data)
    df['bbands_upper'], df['bbands_middle'], df['bbands_lower'] = talib.BBANDS(
        close_data, timeperiod=20, nbdevup=2, nbdevdn=2)
    df['bbands_std'] = close_data.rolling(window=20).std()
    df['bbands_width'] = (df['bbands_upper'] - df['bbands_lower']) / df['bbands_middle']

    # 添加移动平均线交叉信号
    df['ma5_cross_ma10'] = ((df['MA5'] > df['MA10']) & (df['MA5'].shift(1) <= df['MA10'].shift(1))).astype(int) - \
                           ((df['MA5'] < df['MA10']) & (df['MA5'].shift(
                               1) >= df['MA10'].shift(1))).astype(int)

    df['ma5_cross_ma20'] = ((df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))).astype(int) - \
                           ((df['MA5'] < df['MA20']) & (df['MA5'].shift(
                               1) >= df['MA20'].shift(1))).astype(int)

    # 添加价格突破指标
    df['price_above_ma20'] = (df['close'] > df['MA20']).astype(int)
    df['price_above_ma60'] = (df['close'] > df['MA60']).astype(int)

    # 添加量能指标
    df['volume_surge'] = (df['volume'] > 1.5 * df['volume_ma5']).astype(int)
    df['volume_shrink'] = (df['volume'] < 0.5 * df['volume_ma5']).astype(int)

    # 计算MACD
    if not isinstance(close_data, pd.Series):
        close_data = pd.Series(close_data)
    df['macd'], df['signal_line'], df['macd_hist'] = talib.MACD(
        close_data, fastperiod=12, slowperiod=26, signalperiod=9)

    # 添加ATR指标 (真实波动幅度)
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    
    # 添加OBV指标 (能量潮)
    df['obv'] = talib.OBV(df['close'], df['volume'])
    
    # 添加CCI指标 (商品通道指数)
    df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=14)

    return df

def create_advanced_nonlinear_features(df):
    """
    创建高级非线性特征

    参数:
        df: 输入DataFrame，包含已计算的基础技术指标

    返回:
        DataFrame: 添加了高级非线性特征的DataFrame
    """
    # 价格波动率相关特征
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    df['log_return_volatility'] = df['log_return'].rolling(window=10).std()

    # 价格与成交量关联特征
    df['price_volume_corr'] = df['close'].rolling(window=20).corr(df['volume'])

    # 指标交叉特征
    df['macd_signal_cross'] = ((df['macd'] > df['signal']) &
                               (df['macd'].shift(1) <= df['signal'].shift(1))).astype(int) - \
        ((df['macd'] < df['signal']) &
         (df['macd'].shift(1) >= df['signal'].shift(1))).astype(int)

    # 价格动量和波动率比率
    df['momentum_volatility_ratio'] = df['momentum_5d'] / df['volatility_5d']

    # 布林带相对位置
    df['bbands_position'] = (df['close'] - df['bbands_lower']) / \
        (df['bbands_upper'] - df['bbands_lower'])

    # 均线形态特征
    if 'MA5' in df.columns and 'MA10' in df.columns and 'MA20' in df.columns:
        df['ma_trend'] = (df['MA5'] > df['MA10']).astype(
            int) + (df['MA10'] > df['MA20']).astype(int)

    # 价格和成交量的加速度（二阶差分）
    df['price_acceleration'] = df['price_change'].diff()
    df['volume_acceleration'] = df['volume_change'].diff()

    # 极端价格变动特征
    if 'volatility_10d' in df.columns:
        df['extreme_up'] = (df['price_change'] > 2 *
                            df['volatility_10d']).astype(int)
        df['extreme_down'] = (df['price_change'] < -2 *
                              df['volatility_10d']).astype(int)

    # 非线性组合特征
    if 'rsi' in df.columns:
        df['rsi_cubed'] = df['rsi'] ** 3 / 10000  # 标准化
        df['rsi_ma_cross'] = ((df['rsi'] > 50) & (df['MA5'] > df['MA20'])).astype(int) - \
            ((df['rsi'] < 50) & (df['MA5'] < df['MA20'])).astype(int)

    # 波动率的变化率
    if 'volatility_10d' in df.columns:
        df['volatility_change'] = df['volatility_10d'].pct_change()

    return df

def create_time_series_features(df):
    """
    创建时间序列特征

    参数:
        df: 输入DataFrame

    返回:
        DataFrame: 添加了时间序列特征的DataFrame
    """
    # 确保索引是日期类型
    if not isinstance(df.index, pd.DatetimeIndex):
        logger.info("警告: 索引不是日期类型，无法创建时间特征")
        return df

    # 提取基本日期特征
    df['day_of_week'] = df.index.dayofweek
    df['day_of_month'] = df.index.day
    df['month'] = df.index.month
    df['quarter'] = df.index.quarter
    df['year'] = df.index.year
    df['is_month_start'] = df.index.is_month_start.astype(int)
    df['is_month_end'] = df.index.is_month_end.astype(int)
    df['is_quarter_start'] = df.index.is_quarter_start.astype(int)
    df['is_quarter_end'] = df.index.is_quarter_end.astype(int)
    df['is_year_start'] = df.index.is_year_start.astype(int)
    df['is_year_end'] = df.index.is_year_end.astype(int)

    # 月度和季度中的位置（0-1范围内）
    days_in_month = df.index.days_in_month
    df['month_progress'] = (df.index.day - 1) / (days_in_month - 1)

    # 季度内的进度
    df['quarter_progress'] = ((df.index.month - 1) %
                              3 * 30 + df.index.day) / 90

    # 年内的进度
    df['year_progress'] = (df.index.dayofyear - 1) / 365

    # 季节性特征（使用正弦和余弦变换以保留周期性）
    # 周内天的循环编码
    df['day_of_week_sin'] = np.sin(2 * np.pi * df.index.dayofweek / 7)
    df['day_of_week_cos'] = np.cos(2 * np.pi * df.index.dayofweek / 7)

    # 月内天的循环编码
    df['day_of_month_sin'] = np.sin(
        2 * np.pi * (df.index.day - 1) / days_in_month)
    df['day_of_month_cos'] = np.cos(
        2 * np.pi * (df.index.day - 1) / days_in_month)

    # 年内月的循环编码
    df['month_sin'] = np.sin(2 * np.pi * (df.index.month - 1) / 12)
    df['month_cos'] = np.cos(2 * np.pi * (df.index.month - 1) / 12)

    # 假日相关特征（简化实现）
    # 实际应用中应考虑真实的假日日历
    df['is_monday'] = (df.index.dayofweek == 0).astype(int)
    df['is_friday'] = (df.index.dayofweek == 4).astype(int)

    # 季节特征
    df['is_spring'] = ((df.index.month >= 3) & (
        df.index.month <= 5)).astype(int)
    df['is_summer'] = ((df.index.month >= 6) & (
        df.index.month <= 8)).astype(int)
    df['is_autumn'] = ((df.index.month >= 9) & (
        df.index.month <= 11)).astype(int)
    df['is_winter'] = ((df.index.month == 12) | (
        df.index.month <= 2)).astype(int)

    return df
