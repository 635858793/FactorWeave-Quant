import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO")

from analysis.pattern_recognition import EnhancedPatternRecognizer

def generate_test_kdata(num_bars=100):
    """生成测试K线数据，包含一些常见的形态特征"""
    np.random.seed(42)
    
    dates = pd.date_range(start='2024-01-01', periods=num_bars, freq='D')
    
    base_price = 100
    prices = [base_price]
    
    for i in range(1, num_bars):
        if i < 20:
            trend = 0.3
        elif i < 40:
            trend = -0.2
        elif i < 50:
            trend = 0.5
        else:
            trend = -0.1
        
        change = np.random.normal(trend, 1.5)
        new_price = prices[-1] + change
        prices.append(max(new_price, 10))
    
    prices = np.array(prices)
    
    kdata = pd.DataFrame({
        'datetime': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, num_bars)),
        'high': prices * (1 + np.random.uniform(0.01, 0.03, num_bars)),
        'low': prices * (1 - np.random.uniform(0.01, 0.03, num_bars)),
        'close': prices,
        'volume': np.random.uniform(1000000, 5000000, num_bars)
    })
    
    kdata.set_index('datetime', inplace=True)
    return kdata

def test_pattern_recognition():
    """测试形态识别功能"""
    print("=" * 60)
    print("形态识别自动验证测试")
    print("=" * 60)
    
    print("\n[1] 生成测试K线数据...")
    kdata = generate_test_kdata(100)
    print(f"    K线数据: {len(kdata)} 根")
    
    print("\n[2] 创建形态识别器...")
    recognizer = EnhancedPatternRecognizer(debug_mode=True)
    
    pattern_types = ['pennant', 'expanding_triangle', 'flag', 'rising_wedge', 'falling_wedge']
    print(f"    测试形态: {pattern_types}")
    
    thresholds = [0.3, 0.4, 0.5, 0.6]
    
    for threshold in thresholds:
        print(f"\n[3] 测试置信度阈值: {threshold:.0%}")
        patterns = recognizer.identify_patterns(
            kdata,
            confidence_threshold=threshold,
            pattern_types=pattern_types
        )
        print(f"    识别结果: {len(patterns)} 个形态")
        
        for p in patterns[:5]:
            print(f"      - {p.pattern_name}: {p.confidence:.1%}")
    
    print("\n[4] 测试不限制形态类型...")
    patterns = recognizer.identify_patterns(
        kdata,
        confidence_threshold=0.3,
        pattern_types=None
    )
    print(f"    识别结果: {len(patterns)} 个形态")
    
    for p in patterns[:5]:
        print(f"      - {p.pattern_name}: {p.confidence:.1%}")
    
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)

if __name__ == "__main__":
    test_pattern_recognition()
