"""
形态识别功能单元测试
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_test_kdata(length=100):
    """创建测试用K线数据"""
    dates = [datetime.now() - timedelta(days=i) for i in range(length-1, -1, -1)]
    
    np.random.seed(42)
    base_price = 100
    prices = base_price + np.cumsum(np.random.randn(length) * 2)
    
    data = {
        'date': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, length)
    }
    
    df = pd.DataFrame(data)
    df.set_index('date', inplace=True)
    return df


def test_pattern_manager():
    """测试PatternManager"""
    print("\n=== 测试 PatternManager ===")
    
    from analysis.pattern_manager import PatternManager
    
    pm = PatternManager()
    
    # 测试获取所有形态
    all_patterns = pm.get_all_patterns(active_only=True)
    print(f"获取到 {len(all_patterns)} 个激活的形态")
    
    # 测试按类别获取
    categories = pm.get_categories()
    print(f"获取到 {len(categories)} 个类别: {categories}")
    
    # 测试获取单个形态配置
    test_patterns = ['pennant', 'expanding_triangle', 'flag']
    for pattern_name in test_patterns:
        config = pm.get_pattern_config(pattern_name)
        if config:
            print(f"  找到形态: {pattern_name} -> {config.name} ({config.english_name})")
        else:
            print(f"  未找到形态: {pattern_name}")
    
    return pm


def test_pattern_recognition(pm):
    """测试形态识别器"""
    print("\n=== 测试形态识别器 ===")
    
    from analysis.pattern_recognition import EnhancedPatternRecognizer
    
    # 创建测试数据
    kdata = create_test_kdata(100)
    print(f"测试K线数据: {len(kdata)} 根")
    
    # 创建识别器
    recognizer = EnhancedPatternRecognizer(debug_mode=True)
    
    # 测试指定形态类型
    pattern_types = ['pennant', 'expanding_triangle', 'flag', 'rising_wedge', 'falling_wedge']
    print(f"\n识别形态: {pattern_types}")
    
    # 执行识别
    results = recognizer.identify_patterns(
        kdata,
        confidence_threshold=0.5,
        pattern_types=pattern_types
    )
    
    print(f"识别结果: 发现 {len(results)} 个形态")
    
    for r in results[:5]:
        print(f"  - {getattr(r, 'pattern_type', 'unknown')}: 置信度={r.confidence:.2f}")
    
    return results


def test_pattern_algorithm():
    """测试形态算法"""
    print("\n=== 测试形态算法执行 ===")
    
    from analysis.pattern_manager import PatternManager
    
    pm = PatternManager()
    
    # 获取一个形态配置
    config = pm.get_pattern_config('pennant')
    if not config:
        print("未找到 pennant 形态配置")
        return
    
    print(f"形态: {config.name} ({config.english_name})")
    print(f"  algorithm_code: {config.algorithm_code[:100] if config.algorithm_code else 'None'}...")
    
    # 创建测试数据
    kdata = create_test_kdata(50)
    
    # 尝试执行算法
    if config.algorithm_code:
        try:
            from analysis.pattern_base import PatternAlgorithmFactory
            recognizer = PatternAlgorithmFactory.create(config)
            
            if recognizer:
                results = recognizer.recognize(kdata)
                print(f"算法执行成功，返回 {len(results)} 个结果")
            else:
                print("无法创建识别器")
        except Exception as e:
            print(f"算法执行失败: {e}")
    else:
        print("该形态没有算法代码")


if __name__ == '__main__':
    print("=" * 50)
    print("形态识别功能单元测试")
    print("=" * 50)
    
    # 测试1: PatternManager
    pm = test_pattern_manager()
    
    # 测试2: 形态识别器
    results = test_pattern_recognition(pm)
    
    # 测试3: 形态算法
    test_pattern_algorithm()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
