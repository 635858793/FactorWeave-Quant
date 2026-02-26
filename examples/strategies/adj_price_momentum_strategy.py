#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
复权价格动量策略示例

策略逻辑：
1. 使用复权价格计算真实收益率（避免除权除息影响）
2. 计算20日动量因子
3. 选择动量最强的股票做多

技术要点：
- 使用adj_close而非close计算收益率
- 正确处理除权除息带来的价格跳空
- 基于adj_factor进行数据验证

作者：FactorWeave-Quant Team
版本：V2.0.4
日期：2025-10-12
"""

import pandas as pd
import numpy as np
from typing import List, Dict
from loguru import logger


class AdjPriceMomentumStrategy:
    """复权价格动量策略"""
    
    def __init__(self, lookback_period: int = 20, top_n: int = 10):
        """
        初始化策略
        
        Args:
            lookback_period: 动量计算周期（天）
            top_n: 选择动量最强的N只股票
        """
        self.lookback_period = lookback_period
        self.top_n = top_n
        
    def calculate_momentum(self, df: pd.DataFrame) -> pd.Series:
        """
        计算动量因子
        
        Args:
            df: K线数据，必须包含adj_close列
        
        Returns:
            动量值序列
        """
        # ❌ 错误示例：使用close计算（除权除息会产生虚假负收益）
        # momentum_wrong = (df['close'] - df['close'].shift(self.lookback_period)) / df['close'].shift(self.lookback_period)
        
        # 正确示例：使用adj_close计算真实收益率
        momentum = (df['adj_close'] - df['adj_close'].shift(self.lookback_period)) / df['adj_close'].shift(self.lookback_period)
        
        return momentum
    
    def validate_adj_data(self, df: pd.DataFrame) -> bool:
        """
        验证复权数据质量
        
        Args:
            df: K线数据
            
        Returns:
            是否通过验证
        """
        # 1. 检查必需列
        required_cols = ['adj_close', 'adj_factor', 'close']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"缺少必需列: {required_cols}")
            return False
        
        # 2. 检查adj_close与close的关系
        # adj_close应该 = close * adj_factor（允许小误差）
        calculated_adj = df['close'] * df['adj_factor']
        error = (df['adj_close'] - calculated_adj).abs() / calculated_adj
        
        if error.mean() > 0.01:  # 平均误差>1%
            logger.warning(f"复权价格计算异常，平均误差: {error.mean():.2%}")
            return False
        
        # 3. 检查adj_factor合理性
        if (df['adj_factor'] < 0).any() or (df['adj_factor'] > 100).any():
            logger.warning("复权因子超出合理范围 [0, 100]")
            return False
        
        logger.info("复权数据验证通过")
        return True
    
    def generate_signals(self, stocks_data: Dict[str, pd.DataFrame]) -> List[str]:
        """
        生成交易信号
        
        Args:
            stocks_data: 股票代码 -> K线DataFrame的映射
            
        Returns:
            选中的股票代码列表
        """
        momentum_scores = {}
        
        for symbol, df in stocks_data.items():
            # 验证数据
            if not self.validate_adj_data(df):
                logger.warning(f"跳过 {symbol}：复权数据验证失败")
                continue
            
            # 计算动量
            momentum = self.calculate_momentum(df)
            
            # 使用最新动量值
            if not momentum.empty and not pd.isna(momentum.iloc[-1]):
                momentum_scores[symbol] = momentum.iloc[-1]
        
        # 选择动量最强的股票
        sorted_stocks = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
        selected = [symbol for symbol, score in sorted_stocks[:self.top_n]]
        
        logger.info(f"选择了 {len(selected)} 只动量股票")
        for symbol, score in sorted_stocks[:self.top_n]:
            logger.info(f"  {symbol}: 动量={score:.2%}")
        
        return selected
    
    def analyze_dividend_impact(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        分析分红对价格的影响
        
        Args:
            df: K线数据
            
        Returns:
            包含分红分析的DataFrame
        """
        # 计算复权因子的变化（变化点通常是分红日）
        df['adj_factor_change'] = df['adj_factor'].pct_change()
        
        # 检测除权除息事件（adj_factor变化>0.5%）
        dividend_events = df[df['adj_factor_change'].abs() > 0.005].copy()
        
        if not dividend_events.empty:
            logger.info(f"检测到 {len(dividend_events)} 次除权除息事件:")
            for idx, row in dividend_events.iterrows():
                logger.info(f"  {row['datetime']}: adj_factor={row['adj_factor']:.4f}, 变化={row['adj_factor_change']:.2%}")
        
        return dividend_events


# 使用示例
def example_usage():
    """策略使用示例"""
    # 模拟数据
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    
    # 股票A: 正常涨势
    stock_a = pd.DataFrame({
        'datetime': dates,
        'close': 10 + np.cumsum(np.random.randn(100) * 0.1),
        'adj_factor': [1.0] * 100,
    })
    stock_a['adj_close'] = stock_a['close'] * stock_a['adj_factor']
    
    # 股票B: 期间分红（adj_factor变化）
    stock_b = pd.DataFrame({
        'datetime': dates,
        'close': 20 + np.cumsum(np.random.randn(100) * 0.15),
        'adj_factor': [1.0] * 50 + [0.95] * 50,  # 第50天分红5%
    })
    stock_b['adj_close'] = stock_b['close'] * stock_b['adj_factor']
    
    # 股票C: 下跌
    stock_c = pd.DataFrame({
        'datetime': dates,
        'close': 15 - np.cumsum(np.abs(np.random.randn(100)) * 0.1),
        'adj_factor': [1.0] * 100,
    })
    stock_c['adj_close'] = stock_c['close'] * stock_c['adj_factor']
    
    stocks_data = {
        '000001': stock_a,
        '600519': stock_b,
        '000725': stock_c,
    }
    
    # 创建策略实例
    strategy = AdjPriceMomentumStrategy(lookback_period=20, top_n=2)
    
    # 生成信号
    selected_stocks = strategy.generate_signals(stocks_data)
    
    print(f"\n策略选择: {selected_stocks}")
    
    # 分析分红影响
    print("\n分红分析 - 600519:")
    strategy.analyze_dividend_impact(stocks_data['600519'])


if __name__ == "__main__":
    example_usage()

