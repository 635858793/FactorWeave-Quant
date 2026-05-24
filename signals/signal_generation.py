# ⚠️ 此文件为 legacy 代码，功能已迁移至 core/signal/
# 新代码请使用 from core.signal import ...
# 保留此文件仅用于向后兼容

import numpy as np
import pandas as pd
from loguru import logger

def generate_enhanced_trading_signals(df):
    """
    根据模型预测生成交易信号

    参数:
        df: 包含预测结果的DataFrame

    返回:
        DataFrame: 添加了交易信号的DataFrame
    """
    # 确保DataFrame有预测结果
    if 'predictions' not in df.columns and 'predicted_signal' not in df.columns:
        raise ValueError("DataFrame中缺少模型预测结果")

    # 使用哪个列作为原始预测
    pred_col = 'predictions' if 'predictions' in df.columns else 'predicted_signal'

    # 创建结果的副本
    result_df = df.copy()

    # 初始设置信号为0（持有）
    result_df['signal'] = 0

    # 优先使用概率进行信号生成（如果有的话）
    if all(col in df.columns for col in ['buy_prob', 'sell_prob']):
        # 定义买入卖出阈值（可调整）
        buy_threshold = 0.6
        sell_threshold = 0.6

        # 生成信号
        result_df['signal'] = 0  # 默认为持有
        result_df.loc[result_df['buy_prob'] >
                      buy_threshold, 'signal'] = 1  # 买入信号
        result_df.loc[result_df['sell_prob'] >
                      sell_threshold, 'signal'] = -1  # 卖出信号
    else:
        # 直接使用分类模型的预测
        result_df['signal'] = result_df[pred_col]

    # 应用信号平滑 - 避免频繁交易
    # 计算信号变化
    result_df['signal_change'] = result_df['signal'].diff().fillna(0)

    # 信号消除 - 当信号持续少于min_hold_periods天时取消信号
    min_hold_periods = 2

    buy_signals = result_df['signal'] == 1
    buy_runs = buy_signals.astype(int).diff().ne(0).cumsum()
    buy_run_lengths = buy_signals.groupby(buy_runs).transform('sum')
    short_buy_mask = buy_signals & (buy_run_lengths < min_hold_periods)
    result_df.loc[short_buy_mask, 'signal'] = 0

    sell_signals = result_df['signal'] == -1
    sell_runs = sell_signals.astype(int).diff().ne(0).cumsum()
    sell_run_lengths = sell_signals.groupby(sell_runs).transform('sum')
    short_sell_mask = sell_signals & (sell_run_lengths < min_hold_periods)
    result_df.loc[short_sell_mask, 'signal'] = 0

    # 应用市场状态过滤（如果有）
    if 'market_state' in result_df.columns:
        # 在熊市中减少买入信号
        bear_market = result_df['market_state'] == -1
        result_df.loc[bear_market & (result_df['signal'] == 1), 'signal'] = 0

        # 在牛市中减少卖出信号
        bull_market = result_df['market_state'] == 1
        result_df.loc[bull_market & (result_df['signal'] == -1), 'signal'] = 0

    signals = result_df['signal'].values
    changed = np.concatenate([[True], signals[1:] != signals[:-1]])
    result_df['trade_signal'] = np.where(changed, signals, 0)
    result_df['position'] = result_df['trade_signal'].replace(0, np.nan).ffill().fillna(0).astype(int)

    return result_df

def optimize_signal_generation(df):
    """
    优化交易信号生成，增加信号质量

    参数:
        df: 输入DataFrame

    返回:
        DataFrame: 优化后的DataFrame
    """
    # 确保DataFrame包含预测概率
    required_cols = ['buy_prob', 'sell_prob', 'hold_prob']
    if not all(col in df.columns for col in required_cols):
        logger.info("缺少概率列，无法优化信号")
        return df

    result_df = df.copy()

    # 设置动态阈值
    # 1. 基于波动率调整阈值
    if 'volatility_20d' in result_df.columns:
        # 计算波动率百分位数
        vol_percentile = result_df['volatility_20d'].rolling(window=60).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1]
        ).fillna(0.5)

        # 高波动率时提高阈值
        base_buy_threshold = 0.55
        base_sell_threshold = 0.55

        # 波动率越高，阈值越高（最高可达0.75）
        result_df['buy_threshold'] = base_buy_threshold + vol_percentile * 0.2
        result_df['sell_threshold'] = base_sell_threshold + \
            vol_percentile * 0.2
    else:
        # 固定阈值
        result_df['buy_threshold'] = 0.6
        result_df['sell_threshold'] = 0.6

    # 2. 基于市场状态调整阈值
    if 'market_state' in result_df.columns:
        # 在牛市中降低买入阈值，提高卖出阈值
        result_df.loc[result_df['market_state'] == 1, 'buy_threshold'] -= 0.05
        result_df.loc[result_df['market_state'] == 1, 'sell_threshold'] += 0.05

        # 在熊市中提高买入阈值，降低卖出阈值
        result_df.loc[result_df['market_state'] == -1, 'buy_threshold'] += 0.05
        result_df.loc[result_df['market_state']
                      == -1, 'sell_threshold'] -= 0.05

    # 3. 基于信号强度生成最终信号
    result_df['optimized_signal'] = 0  # 默认为持有

    # 应用优化阈值
    result_df.loc[result_df['buy_prob'] >
                  result_df['buy_threshold'], 'optimized_signal'] = 1
    result_df.loc[result_df['sell_prob'] >
                  result_df['sell_threshold'], 'optimized_signal'] = -1

    # 4. 信号冲突处理（买入和卖出信号同时满足条件）
    conflicts = (result_df['buy_prob'] > result_df['buy_threshold']) & (
        result_df['sell_prob'] > result_df['sell_threshold'])
    if conflicts.any():
        # 选择概率更高的信号
        stronger_buy = result_df.loc[conflicts,
                                     'buy_prob'] > result_df.loc[conflicts, 'sell_prob']
        result_df.loc[conflicts & stronger_buy, 'optimized_signal'] = 1
        result_df.loc[conflicts & ~stronger_buy, 'optimized_signal'] = -1

    # 5. 应用交易最小间隔
    min_trade_interval = 5  # 最小交易间隔天数

    # 跟踪上次交易日期
    last_trade_idx = -min_trade_interval - 1

    opt_sig_col = result_df.columns.get_loc('optimized_signal')

    sig_mask = result_df.iloc[:, opt_sig_col] != 0
    sig_idxs = np.where(sig_mask)[0]
    if len(sig_idxs) > 0:
        last_trade_idx = -min_trade_interval - 1
        zero_idxs = []
        for idx in sig_idxs:
            if idx - last_trade_idx <= min_trade_interval:
                zero_idxs.append(idx)
            else:
                last_trade_idx = idx
        if zero_idxs:
            result_df.iloc[zero_idxs, opt_sig_col] = 0

    # 6. 应用止损策略
    if 'position' in result_df.columns and 'close' in result_df.columns:
        # 设置止损百分比
        stop_loss_pct = 0.05

        # 遍历数据
        for i in range(1, len(result_df)):
            if result_df['position'].iloc[i-1] == 1:  # 之前是多头
                # 计算价格变动
                price_change = (
                    result_df['close'].iloc[i] / result_df['close'].iloc[i-1]) - 1

                # 如果下跌超过止损线，生成卖出信号
                if price_change < -stop_loss_pct:
                    result_df.iloc[i, opt_sig_col] = -1
                    last_trade_idx = i

    # 计算最终的交易信号和持仓
    result_df['final_signal'] = result_df['optimized_signal']

    # 计算实际的交易信号（只在信号改变时发出交易指令）
    signals = result_df['final_signal'].values
    changed = np.concatenate([[True], signals[1:] != signals[:-1]])
    result_df['trade_signal'] = np.where(changed, signals, 0)
    result_df['position'] = result_df['trade_signal'].replace(0, np.nan).ffill().fillna(0).astype(int)

    return result_df
