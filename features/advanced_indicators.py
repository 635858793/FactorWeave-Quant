"""
高级技术指标计算模块
提供各种高级技术指标的计算功能
"""

import pandas as pd
import numpy as np
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False
from scipy import stats
from datetime import datetime
from typing import Dict, List, Optional, Any
from utils.data_preprocessing import kdata_preprocess as _kdata_preprocess, validate_kdata
from loguru import logger
from core.indicators.indicators_algorithm import calc_kdj

def calculate_advanced_indicators(df):
    """
    计算高级技术指标

    参数:
        df: 输入DataFrame，包含OHLCV数据

    返回:
        DataFrame: 添加了高级技术指标的DataFrame
    """
    df = _kdata_preprocess(df, context="高级指标")
    if df is None or df.empty:
        return df

    # MACD
    df['macd'], df['signal'], df['macd_hist'] = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)

    # RSI
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)

    # Bollinger Bands
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

    # ATR
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

    # Stochastic Oscillator
    df['stoch_k'], df['stoch_d'] = talib.STOCHF(df['high'], df['low'], df['close'], fastk_period=14, fastd_period=3)

    # Chaikin Money Flow
    clv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
    clv = clv.replace([np.inf, -np.inf], np.nan).fillna(0)
    df['cmf'] = (clv * df['volume']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()

    # OBV (On-Balance Volume)
    df['obv'] = talib.OBV(df['close'], df['volume'])

    # KDJ
    df['kdj_k'], df['kdj_d'], df['kdj_j'] = calc_kdj(df['high'], df['low'], df['close'], n=9, m1=3, m2=3)

    # Williams %R
    df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=14)

    # TRIX
    df['trix'] = talib.TRIX(df['close'], timeperiod=9)

    # CCI (Commodity Channel Index)
    df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=20)

    # ROC (Rate of Change)
    df['roc'] = talib.ROC(df['close'], timeperiod=10)

    # Awesome Oscillator
    median_price = (df['high'] + df['low']) / 2
    df['awesome_oscillator'] = median_price.rolling(window=5).mean() - median_price.rolling(window=34).mean()

    # MFI (Money Flow Index)
    df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)

    return df

ALL_PATTERN_TYPES = [
    "头肩顶", "头肩底", "双顶", "双底", "三角形", "锤子线", "倒锤头", "吞没形态", "启明星", "黄昏星", "三白兵", "三只乌鸦", "十字星", "流星线", "射击之星"
]

def create_pattern_recognition_features(df):
    """
    创建K线形态识别特征

    参数:
        df: 输入DataFrame，包含OHLCV数据

    返回:
        DataFrame: 添加了K线形态特征的DataFrame
    """
    df = _kdata_preprocess(df, context="形态特征")
    if df is None or df.empty:
        return df

    # 确保有必要的列
    required_cols = ['open', 'high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        logger.error("错误: 缺少必要的列 (open, high, low, close)")
        return df

    # 复制DataFrame以避免修改原始数据
    df_new = df.copy()

    # 计算各部分的大小
    df_new['body_size'] = np.abs(df_new['close'] - df_new['open'])
    df_new['upper_shadow'] = df_new['high'] - np.maximum(df_new['open'], df_new['close'])
    df_new['lower_shadow'] = np.minimum(df_new['open'], df_new['close']) - df_new['low']
    df_new['total_range'] = df_new['high'] - df_new['low']

    # 计算相对大小
    df_new['rel_body_size'] = df_new['body_size'] / df_new['total_range']
    df_new['rel_upper_shadow'] = df_new['upper_shadow'] / df_new['total_range']
    df_new['rel_lower_shadow'] = df_new['lower_shadow'] / df_new['total_range']

    # 替换可能的NaN（当极差为0时）
    df_new.replace([np.inf, -np.inf], np.nan, inplace=True)
    df_new.fillna(0, inplace=True)

    # 下降趋势检测（用于锤子线前提条件）
    df_new['is_downtrend'] = ((df_new['close'] < df_new['close'].shift(1)) &
                              (df_new['close'].shift(1) < df_new['close'].shift(2)) &
                              (df_new['close'].shift(2) < df_new['close'].shift(3))).astype(int)

    # 锤子线和上吊线 (小实体，几乎没有上影线，长下影线，在下降趋势中)
    df_new['is_hammer'] = ((df_new['rel_body_size'] < 0.3) &
                           (df_new['rel_upper_shadow'] < 0.1) &
                           (df_new['rel_lower_shadow'] > 0.6) &
                           (df_new['is_downtrend'])).astype(int)

    # 十字星 (极小实体，上下影线均存在)
    df_new['is_doji'] = (df_new['rel_body_size'] < 0.1).astype(int)

    # 蜻蜓十字星：长下影线，几乎无上影线
    df_new['is_dragonfly_doji'] = (df_new['rel_body_size'] < 0.1) & \
                                  (df_new['rel_upper_shadow'] < 0.1) & \
                                  (df_new['rel_lower_shadow'] > 0.6)

    # 墓碑十字星：长上影线，几乎无下影线
    df_new['is_gravestone_doji'] = (df_new['rel_body_size'] < 0.1) & \
                                   (df_new['rel_upper_shadow'] > 0.6) & \
                                   (df_new['rel_lower_shadow'] < 0.1)

    # 长腿十字星：上下影线都较长
    df_new['is_longlegged_doji'] = (df_new['rel_body_size'] < 0.1) & \
                                   (df_new['rel_upper_shadow'] > 0.3) & \
                                   (df_new['rel_lower_shadow'] > 0.3)

    # 吞没形态 (看跌吞没)
    df_new['bearish_engulfing'] = ((df_new['open'] > df_new['close'].shift(1)) &
                                   (df_new['close'] < df_new['open'].shift(1)) &
                                   (df_new['open'] > df_new['open'].shift(1)) &
                                   (df_new['close'] < df_new['close'].shift(1))).astype(int)

    # 吞没形态 (看涨吞没)
    df_new['bullish_engulfing'] = ((df_new['open'] < df_new['close'].shift(1)) &
                                   (df_new['close'] > df_new['open'].shift(1)) &
                                   (df_new['open'] < df_new['open'].shift(1)) &
                                   (df_new['close'] > df_new['close'].shift(1))).astype(int)

    # 启明星 (三日看涨反转形态)
    df_new['morning_star'] = ((df_new['close'].shift(2) < df_new['open'].shift(2)) &  # 第一日阴线
                              (np.abs(df_new['close'].shift(1) - df_new['open'].shift(1)) <
                               df_new['body_size'].shift(2) * 0.3) &  # 第二日小实体
                              (df_new['close'].shift(1) < df_new['close'].shift(2)) &  # 第二日收盘价低于第一日
                              (df_new['close'] > df_new['open']) &  # 第三日阳线
                              (df_new['close'] > (df_new['open'].shift(2) + df_new['close'].shift(2)) / 2)  # 第三日收盘价回补第一日部分
                              ).astype(int)

    # 黄昏星 (三日看跌反转形态)
    df_new['evening_star'] = ((df_new['close'].shift(2) > df_new['open'].shift(2)) &  # 第一日阳线
                              (np.abs(df_new['close'].shift(1) - df_new['open'].shift(1)) <
                               df_new['body_size'].shift(2) * 0.3) &  # 第二日小实体
                              (df_new['close'].shift(1) > df_new['close'].shift(2)) &  # 第二日收盘价高于第一日
                              (df_new['close'] < df_new['open']) &  # 第三日阴线
                              (df_new['close'] < (df_new['open'].shift(2) + df_new['close'].shift(2)) / 2)  # 第三日收盘价回补第一日部分
                              ).astype(int)

    # 三白兵 (三日看涨持续形态)
    df_new['three_white_soldiers'] = ((df_new['close'] > df_new['open']) &  # 今日阳线
                                      (df_new['close'].shift(1) > df_new['open'].shift(1)) &  # 昨日阳线
                                      (df_new['close'].shift(2) > df_new['open'].shift(2)) &  # 前日阳线
                                      (df_new['close'] > df_new['close'].shift(1)) &  # 今日收盘价高于昨日
                                      (df_new['close'].shift(1) > df_new['close'].shift(2)) &  # 昨日收盘价高于前日
                                      (df_new['open'] > df_new['open'].shift(1)) &  # 今日开盘价高于昨日
                                      (df_new['open'].shift(1) > df_new['open'].shift(2))  # 昨日开盘价高于前日
                                      ).astype(int)

    # 三只乌鸦 (三日看跌持续形态)
    df_new['three_black_crows'] = ((df_new['close'] < df_new['open']) &  # 今日阴线
                                   (df_new['close'].shift(1) < df_new['open'].shift(1)) &  # 昨日阴线
                                   (df_new['close'].shift(2) < df_new['open'].shift(2)) &  # 前日阴线
                                   (df_new['close'] < df_new['close'].shift(1)) &  # 今日收盘价低于昨日
                                   (df_new['close'].shift(1) < df_new['close'].shift(2)) &  # 昨日收盘价低于前日
                                   (df_new['open'] < df_new['open'].shift(1)) &  # 今日开盘价低于昨日
                                   (df_new['open'].shift(1) < df_new['open'].shift(2))  # 昨日开盘价低于前日
                                   ).astype(int)

    return df_new

def create_market_regime_features(df):
    """
    创建市场状态特征

    参数:
        df: 输入DataFrame，包含OHLCV数据

    返回:
        DataFrame: 添加了市场状态特征的DataFrame
    """
    df = _kdata_preprocess(df, context="市场状态")
    if df is None or df.empty:
        return df

    # 计算收益率
    df['returns'] = df['close'].pct_change()

    # 波动率 (20日滚动标准差)
    df['volatility_20'] = df['returns'].rolling(window=20).std()

    # 趋势强度 (ADX简化版)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    plus_dm = np.where((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low']),
                       np.maximum(df['high'] - df['high'].shift(), 0), 0)
    minus_dm = np.where((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift()),
                        np.maximum(df['low'].shift() - df['low'], 0), 0)

    plus_di = 100 * pd.Series(plus_dm).rolling(window=14).mean() / true_range.rolling(window=14).mean()
    minus_di = 100 * pd.Series(minus_dm).rolling(window=14).mean() / true_range.rolling(window=14).mean()

    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.rolling(window=14).mean()

    # 市场状态分类
    df['market_regime'] = 'sideways'  # 默认横盘
    df.loc[(df['adx'] > 25) & (plus_di > minus_di), 'market_regime'] = 'uptrend'  # 上升趋势
    df.loc[(df['adx'] > 25) & (plus_di < minus_di), 'market_regime'] = 'downtrend'  # 下降趋势
    df.loc[df['volatility_20'] > df['volatility_20'].rolling(window=60).mean() * 1.5, 'market_regime'] = 'high_volatility'  # 高波动

    # 支撑阻力位
    df['resistance'] = df['high'].rolling(window=20).max()
    df['support'] = df['low'].rolling(window=20).min()

    # 价格相对位置
    df['price_position'] = (df['close'] - df['support']) / (df['resistance'] - df['support'])

    return df

def add_advanced_indicators(df):
    """
    添加所有高级指标的综合函数

    参数:
        df: 输入DataFrame，包含OHLCV数据

    返回:
        DataFrame: 添加了所有高级指标的DataFrame
    """
    df = _kdata_preprocess(df, context="综合指标")
    if df is None or df.empty:
        return df

    # 基础技术指标
    df = calculate_advanced_indicators(df)

    # K线形态特征
    df = create_pattern_recognition_features(df)

    # 市场状态特征
    df = create_market_regime_features(df)

    # 额外的高级指标
    result = df.copy()

    # 计算相对强弱指数 (RSI) - 多周期（若已由talib等计算则跳过）
    rsi_cols_exist = all(f'rsi_{w}' in result.columns and not result[f'rsi_{w}'].isna().all() for w in [6, 14, 21])
    if not rsi_cols_exist:
        for window in [6, 14, 21]:
            delta = result['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            avg_gain = gain.rolling(window=window).mean()
            avg_loss = loss.rolling(window=window).mean()

            avg_loss = avg_loss.replace(0, 0.00001)
            rs = avg_gain / avg_loss

            result[f'rsi_{window}'] = 100 - (100 / (1 + rs))

    # 计算枢轴点
    result['pivot_point'] = (result['high'] + result['low'] + result['close']) / 3
    result['pivot_r1'] = 2 * result['pivot_point'] - result['low']  # 阻力位1
    result['pivot_s1'] = 2 * result['pivot_point'] - result['high']  # 支撑位1

    # 计算MACD - 如果基本指标中未计算
    if 'macd' not in result.columns:
        result['ema12'] = result['close'].ewm(span=12, adjust=False).mean()
        result['ema26'] = result['close'].ewm(span=26, adjust=False).mean()
        result['macd'] = result['ema12'] - result['ema26']
        result['macd_signal'] = result['macd'].ewm(span=9, adjust=False).mean()
        result['macd_hist'] = result['macd'] - result['macd_signal']

    # 计算随机指标 (Stochastic) - 若talib已计算则跳过
    if 'stoch_k' not in result.columns or result['stoch_k'].isna().all():
        window = 14
        low_min = result['low'].rolling(window=window).min()
        high_max = result['high'].rolling(window=window).max()

        denom = high_max - low_min
        denom = denom.replace(0, 0.00001)

        result['stoch_k'] = 100 * ((result['close'] - low_min) / denom)
        result['stoch_d'] = result['stoch_k'].rolling(window=3).mean()

    # 计算威廉指标 (Williams %R) - 若talib已计算则跳过
    if 'williams_r' not in result.columns or result['williams_r'].isna().all():
        window = 14
        low_min = result['low'].rolling(window=window).min()
        high_max = result['high'].rolling(window=window).max()
        denom = high_max - low_min
        denom = denom.replace(0, 0.00001)
        result['williams_r'] = -100 * (high_max - result['close']) / denom

    # 计算布林带 - 若talib已计算则跳过
    if 'bollinger_mid' not in result.columns or result['bollinger_mid'].isna().all():
        window = 20
        mid_band = result['close'].rolling(window=window).mean()
        std_dev = result['close'].rolling(window=window).std()

        result['bollinger_mid'] = mid_band
        result['bollinger_high'] = mid_band + 2 * std_dev
        result['bollinger_low'] = mid_band - 2 * std_dev
        result['bollinger_width'] = (result['bollinger_high'] - result['bollinger_low']) / result['bollinger_mid']

    # 钱德动量摆动指标 (CMO)
    delta = result['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    up_sum = gain.rolling(window=14).sum()
    down_sum = loss.rolling(window=14).sum()

    result['cmo'] = 100 * (up_sum - down_sum) / (up_sum + down_sum)

    # 计算顺势指标 (CCI) - 若talib已计算则跳过
    if 'cci' not in result.columns or result['cci'].isna().all():
        typical_price = (result['high'] + result['low'] + result['close']) / 3
        mean_deviation = abs(typical_price - typical_price.rolling(window=20).mean()).rolling(window=20).mean()

        mean_deviation = mean_deviation.replace(0, 0.00001)

        result['cci'] = (typical_price - typical_price.rolling(window=20).mean()) / (0.015 * mean_deviation)

    # 计算威廉姆累积/派发线 (Williams A/D) - 向量化实现
    tr_denom = result['high'] - result['low']
    close_diff = result['close'].diff()
    is_up = close_diff > 0
    valid_range = tr_denom != 0
    up_contrib = np.where(valid_range, (result['close'] - result['low']) / tr_denom, 0.0)
    down_contrib = np.where(valid_range, (result['close'] - result['high']) / tr_denom, 0.0)
    daily_contrib = np.where(is_up, up_contrib, down_contrib)
    daily_contrib[0] = 0
    result['willad'] = daily_contrib.cumsum()

    # 计算资金流量指标 (MFI) - 若talib已计算则跳过
    if 'volume' in result.columns and ('mfi' not in result.columns or result['mfi'].isna().all()):
        typical_price = (result['high'] + result['low'] + result['close']) / 3
        money_flow = typical_price * result['volume']

        pos_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        neg_flow = money_flow.where(typical_price < typical_price.shift(1), 0)

        pos_flow_sum = pos_flow.rolling(window=14).sum()
        neg_flow_sum = neg_flow.rolling(window=14).sum()

        neg_flow_sum = neg_flow_sum.replace(0, 0.00001)

        money_ratio = pos_flow_sum / neg_flow_sum
        result['mfi'] = 100 - (100 / (1 + money_ratio))

    # 计算相对强度指数 (RSI) 的超买超卖信号
    if 'rsi_14' in result.columns:
        result['rsi_overbought'] = (result['rsi_14'] > 70).astype(int)
        result['rsi_oversold'] = (result['rsi_14'] < 30).astype(int)
    else:
        logger.warning("rsi_14列不存在，跳过超买超卖信号计算，回退到rsi列")
        if 'rsi' in result.columns:
            result['rsi_overbought'] = (result['rsi'] > 70).astype(int)
            result['rsi_oversold'] = (result['rsi'] < 30).astype(int)
        else:
            result['rsi_overbought'] = 0
            result['rsi_oversold'] = 0

    # 计算价格动量变化率
    result['roc_change'] = result['close'].pct_change(periods=10).diff()

    # 填充缺失值
    result = result.fillna(method='ffill').fillna(0)

    return result
