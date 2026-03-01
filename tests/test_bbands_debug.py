"""
布林带关系验证调试脚本
"""
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.indicator_service import calculate_indicator

np.random.seed(42)
dates = pd.date_range(start='2023-01-01', periods=500, freq='D')

base_price = 50.0
prices = []
for i in range(500):
    change = np.random.normal(0.001, 0.02)
    base_price = base_price * (1 + change)
    prices.append(base_price)

data = pd.DataFrame({
    'datetime': dates,
    'close': prices,
    'high': [p * 1.02 for p in prices],
    'low': [p * 0.98 for p in prices],
    'volume': [1000000] * 500
})
data.set_index('datetime', inplace=True)

result = calculate_indicator('BBANDS', data, timeperiod=20, nbdevup=2, nbdevdn=2)

if isinstance(result, pd.DataFrame):
    upper = result.get('BBUpper', pd.Series())
    middle = result.get('BBMiddle', pd.Series())
    lower = result.get('BBLower', pd.Series())
    
    print("布林带关系检查:")
    print(f"  上轨 > 中轨: {(upper > middle).sum()}/{len(upper)}")
    print(f"  中轨 > 下轨: {(middle > lower).sum()}/{len(middle)}")
    print(f"  上轨 > 下轨: {(upper > lower).sum()}/{len(upper)}")
    
    violations_upper_middle = (upper <= middle).sum()
    violations_middle_lower = (middle <= lower).sum()
    
    print(f"\n违规统计:")
    print(f"  上轨 <= 中轨: {violations_upper_middle} 次")
    print(f"  中轨 <= 下轨: {violations_middle_lower} 次")
    
    if violations_upper_middle > 0:
        print("\n上轨 <= 中轨的位置:")
        violations = result[upper <= middle]
        print(violations.head(10))
    
    print("\n前10行数据:")
    print(result.head(10))
    
    print("\n后10行数据:")
    print(result.tail(10))
