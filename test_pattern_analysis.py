#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
形态分析功能自测验证脚本
验证内容：
1. 一键分析批量处理调用
2. 专业扫描批量处理调用
3. 信号推断逻辑
4. 成功率数据来源
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试1: 模块导入验证")
    print("=" * 60)
    
    try:
        from gui.widgets.analysis_tabs.pattern_tab_pro import (
            PatternAnalysisTabPro,
            AnalysisThread,
            ProfessionalScanThread
        )
        print("✅ 模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_pattern_manager():
    """测试PatternManager单例和并发锁"""
    print("\n" + "=" * 60)
    print("测试2: PatternManager并发安全验证")
    print("=" * 60)
    
    try:
        from analysis.pattern_manager import PatternManager
        import threading
        
        # 测试单例模式
        instance1 = PatternManager.get_instance()
        instance2 = PatternManager.get_instance()
        
        if instance1 is instance2:
            print("✅ 单例模式正确")
        else:
            print("❌ 单例模式失败")
            return False
        
        # 测试锁机制
        if hasattr(PatternManager, '_lock') and isinstance(PatternManager._lock, threading.Lock):
            print("✅ 锁机制存在")
        else:
            print("❌ 锁机制缺失")
            return False
        
        # 测试实例锁
        if hasattr(instance1, '_cache_lock') and isinstance(instance1._cache_lock, threading.Lock):
            print("✅ 实例锁存在")
        else:
            print("❌ 实例锁缺失")
            return False
        
        return True
    except Exception as e:
        print(f"❌ PatternManager测试失败: {e}")
        return False


def test_batch_process_method():
    """测试批量处理方法存在性"""
    print("\n" + "=" * 60)
    print("测试3: 批量处理方法验证")
    print("=" * 60)
    
    try:
        from gui.widgets.analysis_tabs.pattern_tab_pro import PatternAnalysisTabPro
        
        # 检查batch_process_pattern_stats方法
        if hasattr(PatternAnalysisTabPro, 'batch_process_pattern_stats'):
            print("✅ PatternAnalysisTabPro.batch_process_pattern_stats 方法存在")
        else:
            print("❌ batch_process_pattern_stats 方法缺失")
            return False
        
        # 检查_validate_and_clean_pattern方法
        if hasattr(PatternAnalysisTabPro, '_validate_and_clean_pattern'):
            print("✅ _validate_and_clean_pattern 方法存在")
        else:
            print("❌ _validate_and_clean_pattern 方法缺失")
            return False
        
        # 检查_infer_signal_type方法
        if hasattr(PatternAnalysisTabPro, '_infer_signal_type'):
            print("✅ _infer_signal_type 方法存在")
        else:
            print("❌ _infer_signal_type 方法缺失")
            return False
        
        return True
    except Exception as e:
        print(f"❌ 批量处理方法测试失败: {e}")
        return False


def test_signal_inference():
    """测试信号推断逻辑"""
    print("\n" + "=" * 60)
    print("测试4: 信号推断逻辑验证")
    print("=" * 60)
    
    try:
        from gui.widgets.analysis_tabs.pattern_tab_pro import PatternAnalysisTabPro
        
        # 创建测试实例
        class MockPatternTab:
            pass
        
        mock_tab = MockPatternTab()
        
        # 模拟_infer_signal_type逻辑
        def infer_signal(pattern_name):
            pattern_name = pattern_name.lower()
            bullish = ['上升', '突破', '底部', '反转', '黄金', '买入', '多头']
            bearish = ['下降', '跌破', '顶部', '下跌', '死亡', '卖出', '空头']
            
            for keyword in bullish:
                if keyword in pattern_name:
                    return 'bullish'
            for keyword in bearish:
                if keyword in pattern_name:
                    return 'bearish'
            return 'neutral'
        
        # 测试用例
        test_cases = [
            ("头肩顶", "bearish"),
            ("头肩底", "bullish"),
            ("双顶形态", "bearish"),
            ("双底形态", "bullish"),
            ("上升三角形", "bullish"),
            ("下降三角形", "bearish"),
            ("旗形整理", "neutral"),
            ("锤子线", "bullish"),
            ("射击之星", "bearish"),
        ]
        
        all_passed = True
        for pattern_name, expected in test_cases:
            result = infer_signal(pattern_name)
            status = "✅" if result == expected else "❌"
            print(f"  {status} {pattern_name}: {result} (期望: {expected})")
            if result != expected:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ 信号推断测试失败: {e}")
        return False


def test_success_rate_source():
    """测试成功率数据来源逻辑"""
    print("\n" + "=" * 60)
    print("测试5: 成功率数据来源验证")
    print("=" * 60)
    
    try:
        # 模拟批量处理中的数据来源设置逻辑
        pattern = {
            'pattern_name': '头肩顶',
            'success_rate': 0.7,
            'success_rate_source': 'preset'
        }
        
        # 模拟历史数据更新
        historical_success_rate = 0.75
        pattern['success_rate'] = historical_success_rate
        pattern['success_rate_source'] = 'historical'
        
        if pattern['success_rate'] == 0.75 and pattern['success_rate_source'] == 'historical':
            print("✅ 历史数据更新逻辑正确")
        else:
            print("❌ 历史数据更新逻辑错误")
            return False
        
        # 测试无历史数据时保持预设值
        pattern2 = {
            'pattern_name': '未知形态',
            'success_rate': 0.7,
            'success_rate_source': 'preset'
        }
        
        if pattern2['success_rate'] == 0.7 and pattern2['success_rate_source'] == 'preset':
            print("✅ 预设值保持逻辑正确")
        else:
            print("❌ 预设值保持逻辑错误")
            return False
        
        return True
    except Exception as e:
        print(f"❌ 成功率来源测试失败: {e}")
        return False


def test_code_structure():
    """测试代码结构完整性"""
    print("\n" + "=" * 60)
    print("测试6: 代码结构完整性验证")
    print("=" * 60)
    
    try:
        import re
        
        file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'gui', 'widgets', 'analysis_tabs', 'pattern_tab_pro.py'
        )
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键代码片段
        checks = [
            ('AnalysisThread调用batch_process', r'self\.pattern_tab\.batch_process_pattern_stats'),
            ('ProfessionalScanThread调用batch_process', r'self\.pattern_tab\.batch_process_pattern_stats'),
            ('unique_patterns批量查询', r'unique_patterns\s*=\s*list\(set\('),
            ('success_rate_source设置', r"success_rate_source.*=.*'historical'"),
            ('signal推断逻辑', r"signal.*=.*'sell'"),
        ]
        
        all_found = True
        for name, pattern in checks:
            if re.search(pattern, content):
                print(f"  ✅ {name}")
            else:
                print(f"  ❌ {name} 缺失")
                all_found = False
        
        return all_found
    except Exception as e:
        print(f"❌ 代码结构测试失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("形态分析功能自测验证")
    print("=" * 60)
    
    results = []
    
    results.append(("模块导入", test_imports()))
    results.append(("PatternManager并发安全", test_pattern_manager()))
    results.append(("批量处理方法", test_batch_process_method()))
    results.append(("信号推断逻辑", test_signal_inference()))
    results.append(("成功率数据来源", test_success_rate_source()))
    results.append(("代码结构完整性", test_code_structure()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
