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

def test_filter():
    print("=" * 60)
    print("测试筛选逻辑")
    print("=" * 60)
    
    kdata = generate_test_kdata(100)
    recognizer = EnhancedPatternRecognizer(debug_mode=False)
    
    pattern_types = ['pennant', 'flag']
    patterns = recognizer.identify_patterns(
        kdata,
        confidence_threshold=0.3,
        pattern_types=pattern_types
    )
    
    print(f"\n识别到 {len(patterns)} 个形态")
    
    pattern_dicts = []
    for p in patterns[:10]:
        if hasattr(p, 'to_dict'):
            d = p.to_dict()
        else:
            d = p
        pattern_dicts.append(d)
        
        print(f"\n形态: {d.get('pattern_name', 'N/A')}")
        print(f"  字段: {list(d.keys())}")
        print(f"  confidence: {d.get('confidence')}")
        print(f"  success_rate: {d.get('success_rate')}")
        print(f"  risk_level: {d.get('risk_level')}")
    
    print("\n" + "=" * 60)
    print("测试筛选: min_conf=0.6, min_success=0.6")
    print("=" * 60)
    
    filters = {
        'min_confidence': 0.6,
        'max_confidence': 1.0,
        'min_success_rate': 0.6,
        'max_success_rate': 1.0,
        'risk_level': '全部'
    }
    
    filtered = []
    for p in pattern_dicts:
        confidence = p.get('confidence', 0.5)
        success_rate = p.get('success_rate', 0.7)
        
        conf_ok = confidence >= 0.6 and confidence <= 1.0
        succ_ok = success_rate >= 0.6 and success_rate <= 1.0
        
        if conf_ok and succ_ok:
            filtered.append(p)
        else:
            print(f"  过滤: {p.get('pattern_name')}, conf={confidence:.2f}, succ={success_rate:.2f}")
    
    print(f"\n筛选后剩余: {len(filtered)} / {len(pattern_dicts)}")

if __name__ == "__main__":
    test_filter()
