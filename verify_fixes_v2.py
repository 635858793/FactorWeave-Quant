#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证修复后的代码结构

检查:
1. strategy_service.py中的信号生成调用是否已修复
2. AdaptivePandasStrategy是否已添加calculate_performance方法
"""

import re
import sys

def check_strategy_service_signals():
    """检查strategy_service.py中的信号生成调用"""
    print("=" * 60)
    print("检查 strategy_service.py 中的信号生成调用")
    print("=" * 60)
    
    with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\strategy_service.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    issues = []
    
    # 检查是否还有使用两个参数调用generate_signals的地方
    pattern = r"plugin\.generate_signals\([^,]+\s*,\s*[^)]+\)"
    matches = re.findall(pattern, content)
    
    if matches:
        print("❌ 发现仍使用两个参数调用generate_signals:")
        for match in matches:
            print(f"   {match}")
            issues.append(match)
    else:
        print("✅ 未发现使用两个参数调用generate_signals")
    
    # 检查正确的调用模式
    correct_pattern = r"market_data_df\s*=\s*[^.]+\.to_dataframe\(\).*?signals\s*=\s*plugin\.generate_signals\(market_data_df\)"
    if re.search(correct_pattern, content, re.DOTALL):
        print("✅ 发现正确的单参数generate_signals调用模式")
    else:
        print("⚠️ 未发现预期的正确调用模式")
    
    return len(issues) == 0

def check_adaptive_strategy_calculate_performance():
    """检查AdaptivePandasStrategy是否已添加calculate_performance方法"""
    print("\n" + "=" * 60)
    print("检查 AdaptivePandasStrategy.calculate_performance 方法")
    print("=" * 60)
    
    file_path = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\plugins\strategies\adaptive_strategy.py"
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查是否有calculate_performance方法定义
    pattern = r"def calculate_performance\s*\("
    matches = re.findall(pattern, content)
    
    if matches:
        print(f"✅ 发现 {len(matches)} 个calculate_performance方法定义")
        
        # 验证方法内容
        if "PerformanceMetrics" in content:
            print("✅ 方法中包含PerformanceMetrics引用")
        else:
            print("❌ 方法中缺少PerformanceMetrics引用")
            return False
            
        return True
    else:
        print("❌ 未发现calculate_performance方法定义")
        return False

def check_imports():
    """检查必要的导入是否正确"""
    print("\n" + "=" * 60)
    print("检查必要的导入")
    print("=" * 60)
    
    # 检查strategy_extensions中的PerformanceMetrics
    try:
        from core.strategy_extensions import PerformanceMetrics
        print("✅ PerformanceMetrics 可从 core.strategy_extensions 导入")
        return True
    except ImportError as e:
        print(f"❌ 导入PerformanceMetrics失败: {e}")
        return False

def main():
    print("验证策略服务修复")
    print("=" * 60)
    
    results = []
    
    # 检查1: strategy_service.py中的信号生成调用
    results.append(("strategy_service.py 信号生成调用", check_strategy_service_signals()))
    
    # 检查2: AdaptivePandasStrategy.calculate_performance方法
    results.append(("AdaptivePandasStrategy.calculate_performance", check_adaptive_strategy_calculate_performance()))
    
    # 检查3: 必要的导入
    results.append(("PerformanceMetrics 导入", check_imports()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("✅ 所有检查通过！")
        return 0
    else:
        print("❌ 部分检查失败，请查看上述输出")
        return 1

if __name__ == "__main__":
    sys.exit(main())
