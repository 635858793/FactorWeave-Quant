# ⚠️ 此文件为 legacy 代码，功能已迁移至 core/signal/
# 新代码请使用 from core.signal import ...
# 保留此文件仅用于向后兼容

import numpy as np
import pandas as pd
from loguru import logger

def filter_signals_by_strength(df, signal_col='signal', threshold=0.6, strength_cols=None):
    """
    根据信号强度过滤交易信号

    参数:
        df: 输入DataFrame
        signal_col: 原始信号列名
        threshold: 强度阈值
        strength_cols: 信号强度列名, 如果为None, 默认使用'buy_prob'和'sell_prob'

    返回:
        DataFrame: 过滤后的DataFrame
    """
    result = df.copy()

    # 创建过滤后的信号列
    result['filtered_signal'] = result[signal_col]

    # 如果未指定强度列，使用默认的概率列
    if strength_cols is None:
        if all(col in result.columns for col in ['buy_prob', 'sell_prob']):
            # 基于概率强度过滤信号

            # 买入信号必须有足够强的买入概率
            buy_condition = (result[signal_col] == 1) & (
                result['buy_prob'] < threshold)
            result.loc[buy_condition, 'filtered_signal'] = 0  # 低于阈值，取消买入信号

            # 卖出信号必须有足够强的卖出概率
            sell_condition = (result[signal_col] == -
                              1) & (result['sell_prob'] < threshold)
            result.loc[sell_condition, 'filtered_signal'] = 0  # 低于阈值，取消卖出信号
        else:
            logger.warning("未找到概率列 (buy_prob, sell_prob), 无法按强度过滤信号")
    else:
        # 使用指定的强度列
        if not all(col in result.columns for col in strength_cols):
            print(f"警告: 未找到指定的强度列 {strength_cols}, 无法按强度过滤信号")
        else:
            # 根据指定的强度列过滤信号
            for col in strength_cols:
                # 买入和卖出信号都必须有足够强的强度
                condition = (result[signal_col] != 0) & (
                    result[col] < threshold)
                result.loc[condition, 'filtered_signal'] = 0  # 低于阈值，取消信号

    # 计算过滤掉的信号数量
    filtered_out = sum(result[signal_col] != 0) - \
        sum(result['filtered_signal'] != 0)
    print(f"按强度过滤后，移除了 {filtered_out} 个弱信号")

    return result

def filter_signals_by_market_regime(df, signal_col='signal', regime_col='market_regime'):
    """
    根据市场状态过滤交易信号

    参数:
        df: 输入DataFrame
        signal_col: 原始信号列名
        regime_col: 市场状态列名

    返回:
        DataFrame: 过滤后的DataFrame
    """
    result = df.copy()

    # 检查是否存在市场状态列
    if regime_col not in result.columns:
        print(f"警告: 未找到市场状态列 '{regime_col}', 无法按市场状态过滤信号")
        return result

    # 创建过滤后的信号列
    result['filtered_by_regime'] = result[signal_col]

    # 在熊市中过滤买入信号
    bear_market = result[regime_col] == -1
    result.loc[bear_market & (result[signal_col] == 1),
               'filtered_by_regime'] = 0

    # 在牛市中过滤卖出信号
    bull_market = result[regime_col] == 1
    result.loc[bull_market & (result[signal_col] == -1),
               'filtered_by_regime'] = 0

    # 计算过滤掉的信号数量
    filtered_out = sum(result[signal_col] != 0) - \
        sum(result['filtered_by_regime'] != 0)
    print(f"按市场状态过滤后，移除了 {filtered_out} 个不符合市场状态的信号")

    return result

def filter_signals_by_volatility(df, signal_col='signal', volatility_col='volatility_regime', threshold=1.5):
    """
    根据波动率过滤交易信号

    参数:
        df: 输入DataFrame
        signal_col: 原始信号列名
        volatility_col: 波动率列名
        threshold: 波动率阈值

    返回:
        DataFrame: 过滤后的DataFrame
    """
    result = df.copy()

    # 检查波动率列
    if volatility_col not in result.columns:
        # 如果没有波动率列，尝试计算
        if 'close' in result.columns:
            result['volatility'] = result['close'].pct_change().rolling(
                window=20).std() * np.sqrt(252)
            volatility_col = 'volatility'
        else:
            print("警告: 无法计算波动率，无法按波动率过滤信号")
            return result

    # 创建过滤后的信号列
    result['filtered_by_volatility'] = result[signal_col]

    # 在高波动率环境下，减少交易频率或提高交易门槛
    high_volatility = result[volatility_col] > threshold

    # 在高波动率期间，可以选择性地取消信号或保留更强的信号
    if 'buy_prob' in result.columns and 'sell_prob' in result.columns:
        # 高波动率时，使用更高的阈值
        high_vol_threshold = 0.7  # 更高的阈值

        # 买入信号必须更强才能在高波动率时保留
        buy_condition = high_volatility & (result[signal_col] == 1) & (
            result['buy_prob'] < high_vol_threshold)
        result.loc[buy_condition, 'filtered_by_volatility'] = 0

        # 卖出信号必须更强才能在高波动率时保留
        sell_condition = high_volatility & (
            result[signal_col] == -1) & (result['sell_prob'] < high_vol_threshold)
        result.loc[sell_condition, 'filtered_by_volatility'] = 0
    else:
        # 如果没有概率列，直接过滤高波动率期间的信号
        result.loc[high_volatility & (
            result[signal_col] != 0), 'filtered_by_volatility'] = 0

    # 计算过滤掉的信号数量
    filtered_out = sum(result[signal_col] != 0) - \
        sum(result['filtered_by_volatility'] != 0)
    print(f"按波动率过滤后，移除了 {filtered_out} 个高波动率期间的信号")

    return result

def combine_signal_filters(df, original_signal_col='signal', filter_cols=None):
    """
    组合多个信号过滤器

    参数:
        df: 输入DataFrame
        original_signal_col: 原始信号列名
        filter_cols: 过滤信号列名列表，如果为None，则自动检测

    返回:
        DataFrame: 包含最终合并信号的DataFrame
    """
    result = df.copy()

    # 如果未指定过滤列，查找所有以'filtered_'开头的列
    if filter_cols is None:
        filter_cols = [
            col for col in result.columns if col.startswith('filtered_')]

        if not filter_cols:
            print("警告: 未找到过滤信号列，无法合并信号")
            return result

    # 检查每个过滤列是否存在
    missing_cols = [col for col in filter_cols if col not in result.columns]
    if missing_cols:
        print(f"警告: 以下过滤列不存在: {missing_cols}")
        filter_cols = [col for col in filter_cols if col in result.columns]

        if not filter_cols:
            print("警告: 所有指定的过滤列都不存在，无法合并信号")
            return result

    # 创建一个新列来存储合并后的信号
    result['combined_signal'] = result[original_signal_col]

    # 如果任何一个过滤器过滤掉了信号，最终信号也被过滤掉 - 向量化版本
    combined = result[original_signal_col].values.astype(np.float64)

    for filter_col in filter_cols:
        filter_vals = result[filter_col].values.astype(np.float64)
        combined[filter_vals == 0] = 0

    result['combined_signal'] = combined

    # 计算过滤掉的信号数量
    filtered_out = sum(result[original_signal_col] !=
                       0) - sum(result['combined_signal'] != 0)
    total_signals = sum(result[original_signal_col] != 0)

    if total_signals > 0:
        filter_rate = filtered_out / total_signals * 100
        print(
            f"合并所有过滤器后，保留了 {total_signals - filtered_out} 个信号，过滤掉了 {filtered_out} 个信号 ({filter_rate:.1f}%)")

    return result

def apply_confirmed_reversal_filter(df, signal_col='signal', trend_reversal_col='trend_reversal'):
    """
    应用趋势反转确认过滤器（只在趋势反转点附近保留相应的交易信号）

    参数:
        df: DataFrame，包含交易信号和趋势反转信号
        signal_col: str，信号列名
        trend_reversal_col: str，趋势反转列名

    返回:
        DataFrame: 包含过滤后信号的DataFrame
    """
    if trend_reversal_col not in df.columns:
        raise ValueError(f"DataFrame中缺少趋势反转列: {trend_reversal_col}")

    # 复制DataFrame避免修改原始数据
    result_df = df.copy()

    # 创建趋势反转过滤后的信号列
    result_df['reversal_filtered_signal'] = 0

    # 确定反转点附近的窗口大小
    window_size = 3  # 反转点前后几个交易日

    # 找出所有反转点
    bull_reversal_points = result_df.index[result_df[trend_reversal_col] == 1]
    bear_reversal_points = result_df.index[result_df[trend_reversal_col] == -1]

    # 为每个看涨反转点保留附近的买入信号
    for point in bull_reversal_points:
        point_idx = result_df.index.get_loc(point)

        # 确定窗口范围
        start_idx = max(0, point_idx - window_size)
        end_idx = min(len(result_df) - 1, point_idx + window_size)

        # 查找窗口范围内的买入信号
        window_indices = result_df.index[start_idx:end_idx + 1]
        buy_signals_in_window = result_df.loc[window_indices, signal_col] == 1

        # 保留这些买入信号
        result_df.loc[window_indices[buy_signals_in_window],
                      'reversal_filtered_signal'] = 1

    # 为每个看跌反转点保留附近的卖出信号
    for point in bear_reversal_points:
        point_idx = result_df.index.get_loc(point)

        # 确定窗口范围
        start_idx = max(0, point_idx - window_size)
        end_idx = min(len(result_df) - 1, point_idx + window_size)

        # 查找窗口范围内的卖出信号
        window_indices = result_df.index[start_idx:end_idx + 1]
        sell_signals_in_window = result_df.loc[window_indices,
                                               signal_col] == -1

        # 保留这些卖出信号
        result_df.loc[window_indices[sell_signals_in_window],
                      'reversal_filtered_signal'] = -1

    return result_df
