#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VWAP均值回归策略示例

策略逻辑：
1. 使用VWAP作为价格中枢
2. 当价格偏离VWAP超过阈值时产生信号
3. 期待价格回归到VWAP水平

技术要点：
- 使用vwap字段（成交量加权均价）
- VWAP是机构交易的重要参考价
- 适合日内或短期均值回归策略

作者：FactorWeave-Quant Team
版本：V2.0.4
日期：2025-10-12
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from loguru import logger

try:
    from numba import jit
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    def jit(*args, **kwargs):
        """numba不可用时的空装饰器fallback"""
        return lambda f: f


if _NUMBA_AVAILABLE:
    @jit(nopython=True, cache=True)
    def _vwap_backtest_numba_core(close, buy, sell, hold_period, n):
        """numba加速的回测核心循环

        遍历K线数组，维护持仓状态，生成交易记录。

        Args:
            close: close价格数组 (float64)
            buy: 买入信号布尔数组
            sell: 卖出信号布尔数组
            hold_period: 最大持有周期
            n: 数组长度

        Returns:
            entry_indices: 买入索引数组
            exit_indices: 卖出索引数组
            ret_values: 每笔交易的收益率数组
            pos_arr: 每个bar的持仓状态数组
            trade_count: 实际交易笔数
        """
        max_trades = n
        entry_indices = np.zeros(max_trades, dtype=np.int64)
        exit_indices = np.zeros(max_trades, dtype=np.int64)
        ret_values = np.zeros(max_trades, dtype=np.float64)
        pos_arr = np.zeros(n, dtype=np.int64)

        position = 0
        entry_price = 0.0
        hold_days = 0
        trade_count = 0

        for i in range(n):
            if position == 0 and buy[i]:
                position = 1
                entry_price = close[i]
                hold_days = 0
                entry_indices[trade_count] = i
            elif position == 1:
                hold_days += 1
                if hold_days >= hold_period or sell[i]:
                    exit_price = close[i]
                    ret = (exit_price - entry_price) / entry_price
                    exit_indices[trade_count] = i
                    ret_values[trade_count] = ret
                    trade_count += 1
                    position = 0
                    hold_days = 0

            pos_arr[i] = position

        return entry_indices, exit_indices, ret_values, pos_arr, trade_count


class VWAPMeanReversionStrategy:
    """VWAP均值回归策略"""
    
    def __init__(self, 
                 deviation_threshold: float = 0.02,
                 hold_period: int = 3,
                 use_turnover_filter: bool = True,
                 min_turnover_rate: float = 0.5):
        """
        初始化策略
        
        Args:
            deviation_threshold: 偏离阈值（例如0.02表示2%）
            hold_period: 持有周期（天）
            use_turnover_filter: 是否使用换手率过滤
            min_turnover_rate: 最小换手率（%）
        """
        self.deviation_threshold = deviation_threshold
        self.hold_period = hold_period
        self.use_turnover_filter = use_turnover_filter
        self.min_turnover_rate = min_turnover_rate

    def set_parameters(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
    def validate_vwap_data(self, df: pd.DataFrame) -> bool:
        """
        验证VWAP数据质量
        
        Args:
            df: K线数据
            
        Returns:
            是否通过验证
        """
        # 1. 检查必需列
        required_cols = ['vwap', 'close', 'high', 'low', 'volume', 'amount']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"缺少必需列: {required_cols}")
            return False
        
        # 2. 检查VWAP是否在[low, high]范围内
        valid_vwap = ((df['vwap'] >= df['low']) & (df['vwap'] <= df['high']))
        valid_rate = valid_vwap.sum() / len(df[df['vwap'].notna()])
        
        if valid_rate < 0.9:
            logger.warning(f"VWAP合理性不足: {valid_rate:.1%} < 90%")
            return False
        
        # 3. 验证VWAP计算公式（如果数据完整）
        calculated_vwap = df['amount'] / df['volume'].replace(0, np.nan)
        error = (df['vwap'] - calculated_vwap).abs() / calculated_vwap
        
        if error.mean() > 0.05:  # 允许5%误差（不同数据源可能有差异）
            logger.warning(f"VWAP计算公式验证异常，平均误差: {error.mean():.2%}")
        
        logger.info("VWAP数据验证通过")
        return True
    
    def calculate_vwap_deviation(self, df: pd.DataFrame) -> pd.Series:
        """
        计算价格相对VWAP的偏离度
        
        Args:
            df: K线数据
            
        Returns:
            偏离度序列（正值表示高于VWAP，负值表示低于VWAP）
        """
        deviation = (df['close'] - df['vwap']) / df['vwap']
        return deviation
    
    def apply_liquidity_filter(self, df: pd.DataFrame) -> pd.Series:
        """
        应用流动性过滤
        
        Args:
            df: K线数据
            
        Returns:
            流动性充足的标记（True/False）
        """
        if not self.use_turnover_filter:
            return pd.Series([True] * len(df), index=df.index)
        
        if 'turnover_rate' not in df.columns:
            logger.warning("缺少turnover_rate列，跳过流动性过滤")
            return pd.Series([True] * len(df), index=df.index)
        
        # 换手率 > 最小阈值
        liquid = df['turnover_rate'] > self.min_turnover_rate
        
        liquid_rate = liquid.sum() / len(df)
        logger.info(f"流动性充足的交易日比例: {liquid_rate:.1%}")
        
        return liquid
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            df: K线数据
            
        Returns:
            包含信号的DataFrame
        """
        # 验证数据
        if not self.validate_vwap_data(df):
            logger.warning("VWAP数据验证失败")
            return df
        
        # 计算偏离度
        df['vwap_deviation'] = self.calculate_vwap_deviation(df)
        
        # 应用流动性过滤
        df['is_liquid'] = self.apply_liquidity_filter(df)
        
        # 生成信号
        # 买入信号：价格低于VWAP超过阈值 且 流动性充足
        df['buy_signal'] = (
            (df['vwap_deviation'] < -self.deviation_threshold) &
            df['is_liquid']
        )
        
        # 卖出信号：价格高于VWAP超过阈值 且 流动性充足
        df['sell_signal'] = (
            (df['vwap_deviation'] > self.deviation_threshold) &
            df['is_liquid']
        )
        
        # 统计信号
        buy_count = df['buy_signal'].sum()
        sell_count = df['sell_signal'].sum()
        
        logger.info(f"信号统计:")
        logger.info(f"  买入信号: {buy_count} 次 ({buy_count/len(df):.1%})")
        logger.info(f"  卖出信号: {sell_count} 次 ({sell_count/len(df):.1%})")
        
        return df
    
    def backtest(self, df: pd.DataFrame) -> Dict:
        """
        简单回测（优先使用numba加速，
              若numba不可用则使用纯Python循环）

        Args:
            df: 包含信号的K线数据

        Returns:
            回测结果字典
        """
        if 'buy_signal' not in df.columns:
            df = self.generate_signals(df)

        # 初始化持仓和收益
        df['position'] = 0
        df['returns'] = 0.0

        # 提取numpy数组用于numba加速
        close_arr = df['close'].values
        buy_arr = df['buy_signal'].values.astype(np.bool_)
        sell_arr = df['sell_signal'].values.astype(np.bool_)
        n = len(df)

        if _NUMBA_AVAILABLE:
            logger.info("使用numba加速回测循环")
            entry_indices, exit_indices, ret_values, pos_arr, trade_count = \
                _vwap_backtest_numba_core(close_arr, buy_arr, sell_arr, self.hold_period, n)
            trades = self._build_trades_from_indices(df, entry_indices, exit_indices, ret_values, trade_count)
            for i in range(n):
                df.loc[df.index[i], 'position'] = pos_arr[i]
        else:
            logger.info("numba不可用，使用纯Python循环回测")
            trades = self._backtest_python_loop(df, close_arr, buy_arr, sell_arr, n)

        # 计算策略表现
        total_trades = len([t for t in trades if t['type'] == 'sell'])
        if total_trades > 0:
            avg_return = df[df['returns'] != 0]['returns'].mean()
            win_rate = (df[df['returns'] > 0]['returns'].count() / total_trades)
            total_return = (1 + df['returns']).prod() - 1
        else:
            avg_return = 0
            win_rate = 0
            total_return = 0

        results = {
            'total_trades': total_trades,
            'avg_return': avg_return,
            'win_rate': win_rate,
            'total_return': total_return,
            'trades': trades
        }

        logger.info(f"\n 回测结果:")
        logger.info(f"  总交易次数: {total_trades}")
        logger.info(f"  平均收益: {avg_return:.2%}")
        logger.info(f"  胜率: {win_rate:.1%}")
        logger.info(f"  累计收益: {total_return:.2%}")

        return results

    def _backtest_python_loop(self, df, close_arr, buy_arr, sell_arr, n):
        """纯Python回测循环（numba不可用时的fallback）"""
        trades = []
        position = 0
        entry_price = 0.0
        hold_days = 0

        for i in range(n):
            if position == 0 and buy_arr[i]:
                position = 1
                entry_price = close_arr[i]
                hold_days = 0
                trades.append({
                    'type': 'buy',
                    'date': df.iloc[i]['datetime'],
                    'price': entry_price
                })
            elif position == 1:
                hold_days += 1
                if hold_days >= self.hold_period or sell_arr[i]:
                    exit_price = close_arr[i]
                    ret = (exit_price - entry_price) / entry_price
                    df.loc[df.index[i], 'returns'] = ret
                    trades.append({
                        'type': 'sell',
                        'date': df.iloc[i]['datetime'],
                        'price': exit_price,
                        'return': ret
                    })
                    position = 0
                    hold_days = 0

            df.loc[df.index[i], 'position'] = position

        return trades

    def _build_trades_from_indices(self, df, entry_indices, exit_indices, ret_values, trade_count):
        """将numba核心输出的索引数组转换为交易记录列表"""
        trades = []
        for j in range(trade_count):
            entry_i = entry_indices[j]
            exit_i = exit_indices[j]
            trades.append({
                'type': 'buy',
                'date': df.iloc[entry_i]['datetime'],
                'price': float(df.iloc[entry_i]['close'])
            })
            trades.append({
                'type': 'sell',
                'date': df.iloc[exit_i]['datetime'],
                'price': float(df.iloc[exit_i]['close']),
                'return': float(ret_values[j])
            })
            df.loc[df.index[exit_i], 'returns'] = ret_values[j]
        return trades
    
    def analyze_vwap_pattern(self, df: pd.DataFrame) -> Dict:
        """
        分析VWAP模式
        
        Args:
            df: K线数据
            
        Returns:
            分析结果字典
        """
        # 计算偏离度
        if 'vwap_deviation' not in df.columns:
            df['vwap_deviation'] = self.calculate_vwap_deviation(df)
        
        # 统计分析
        analysis = {
            'mean_deviation': df['vwap_deviation'].mean(),
            'std_deviation': df['vwap_deviation'].std(),
            'max_positive_deviation': df['vwap_deviation'].max(),
            'max_negative_deviation': df['vwap_deviation'].min(),
            'reversion_probability': 0.0
        }
        
        # 计算均值回归概率
        # 定义：偏离超过阈值后，未来N天内价格回归到VWAP
        extreme_deviations = df[df['vwap_deviation'].abs() > self.deviation_threshold]
        
        if len(extreme_deviations) > 0:
            reversion_count = 0
            for idx in extreme_deviations.index:
                # 获取未来N天的数据
                future_data = df.loc[idx:idx+self.hold_period]
                if len(future_data) > 1:
                    # 检查是否回归（偏离度减小）
                    initial_dev = abs(future_data.iloc[0]['vwap_deviation'])
                    final_dev = abs(future_data.iloc[-1]['vwap_deviation'])
                    
                    if final_dev < initial_dev * 0.5:  # 偏离度减少50%以上视为回归
                        reversion_count += 1
            
            analysis['reversion_probability'] = reversion_count / len(extreme_deviations)
        
        logger.info(f"\n🔍 VWAP模式分析:")
        logger.info(f"  平均偏离度: {analysis['mean_deviation']:.2%}")
        logger.info(f"  偏离标准差: {analysis['std_deviation']:.2%}")
        logger.info(f"  最大正偏离: {analysis['max_positive_deviation']:.2%}")
        logger.info(f"  最大负偏离: {analysis['max_negative_deviation']:.2%}")
        logger.info(f"  均值回归概率: {analysis['reversion_probability']:.1%}")
        
        return analysis


# 使用示例
def example_usage():
    """策略使用示例"""
    # 模拟数据
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    
    # 生成模拟的VWAP数据（围绕close波动）
    base_price = 50
    close_prices = base_price + np.cumsum(np.random.randn(100) * 0.5)
    
    df = pd.DataFrame({
        'datetime': dates,
        'close': close_prices,
        'high': close_prices + np.abs(np.random.randn(100) * 0.3),
        'low': close_prices - np.abs(np.random.randn(100) * 0.3),
        'volume': np.random.randint(1000000, 5000000, 100),
        'amount': 0,  # 后续计算
        'vwap': close_prices + np.random.randn(100) * 0.2,  # VWAP围绕close波动
        'turnover_rate': np.random.uniform(0.3, 3.0, 100),  # 换手率0.3-3%
    })
    
    df['amount'] = df['volume'] * df['vwap']
    
    # 创建策略实例
    strategy = VWAPMeanReversionStrategy(
        deviation_threshold=0.02,  # 2%偏离阈值
        hold_period=3,  # 持有3天
        use_turnover_filter=True,  # 使用流动性过滤
        min_turnover_rate=0.5  # 最小换手率0.5%
    )
    
    # 生成信号
    df_with_signals = strategy.generate_signals(df)
    
    # 回测
    results = strategy.backtest(df_with_signals)
    
    # 模式分析
    analysis = strategy.analyze_vwap_pattern(df_with_signals)
    
    print(f"\n策略回测完成!")
    print(f"详细交易记录: {len(results['trades'])} 笔")


if __name__ == "__main__":
    example_usage()

