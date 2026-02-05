#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证样式表继承问题修复效果
"""

import sys
import os
import re

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_style_inheritance_fix():
    """检查样式表继承问题修复是否正确"""
    print("=" * 60)
    print("检查样式表继承问题修复代码")
    print("=" * 60)
    
    # 检查1: 主窗口是否设置了objectName
    print("\n检查1: 主窗口是否设置了objectName")
    widget_file = "gui/widgets/performance/unified_performance_widget.py"
    try:
        with open(widget_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'self\.setObjectName\("main_window"\)'
        if re.search(pattern, content):
            print("✅ 主窗口正确设置了objectName为'main_window'")
            check1_passed = True
        else:
            print("❌ 主窗口未设置objectName")
            check1_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check1_passed = False
    
    # 检查2: 主窗口样式表是否使用了objectName选择器
    print("\n检查2: 主窗口样式表是否使用了objectName选择器")
    try:
        with open(widget_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否使用了 #main_window 选择器
        pattern1 = r'#main_window\s*\{'
        # 检查是否不再使用通用的 QWidget 选择器
        pattern2 = r'QWidget\s*\{'
        
        if re.search(pattern1, content):
            print("✅ 主窗口样式表使用了 #main_window 选择器")
            check2a_passed = True
        else:
            print("❌ 主窗口样式表未使用 #main_window 选择器")
            check2a_passed = False
        
        # 检查是否还有通用的 QWidget 选择器（在样式表字符串中）
        style_pattern = r'self\.setStyleSheet\(""".*?QWidget\s*\{.*?"""'
        if not re.search(style_pattern, content, re.DOTALL):
            print("✅ 主窗口样式表不再使用通用的 QWidget 选择器")
            check2b_passed = True
        else:
            print("❌ 主窗口样式表仍然使用通用的 QWidget 选择器")
            check2b_passed = False
        
        check2_passed = check2a_passed and check2b_passed
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check2_passed = False
    
    # 检查3: ModernMetricCard 是否移除了样式表备份
    print("\n检查3: ModernMetricCard 是否移除了样式表备份")
    card_file = "gui/widgets/performance/components/metric_card.py"
    try:
        with open(card_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'self\._backup_style = self\.styleSheet\(\)'
        if not re.search(pattern, content):
            print("✅ ModernMetricCard 已移除样式表备份")
            check3_passed = True
        else:
            print("❌ ModernMetricCard 仍然保留样式表备份")
            check3_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check3_passed = False
    
    # 检查4: unified_performance_widget 是否移除了卡片样式恢复方法
    print("\n检查4: unified_performance_widget 是否移除了卡片样式恢复方法")
    try:
        with open(widget_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'def _restore_card_styles\(self\):'
        if not re.search(pattern, content):
            print("✅ unified_performance_widget 已移除卡片样式恢复方法")
            check4_passed = True
        else:
            print("❌ unified_performance_widget 仍然保留卡片样式恢复方法")
            check4_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check4_passed = False
    
    # 检查5: _check_and_restore_styles 是否移除了卡片样式恢复调用
    print("\n检查5: _check_and_restore_styles 是否移除了卡片样式恢复调用")
    try:
        with open(widget_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'self\._restore_card_styles\(\)'
        if not re.search(pattern, content):
            print("✅ _check_and_restore_styles 已移除卡片样式恢复调用")
            check5_passed = True
        else:
            print("❌ _check_and_restore_styles 仍然调用卡片样式恢复")
            check5_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check5_passed = False
    
    # 总结
    print("\n" + "=" * 60)
    all_passed = check1_passed and check2_passed and check3_passed and check4_passed and check5_passed
    if all_passed:
        print("✅ 所有检查通过！样式表继承问题修复代码正确！")
        print("\n修复说明：")
        print("1. 主窗口设置了objectName为'main_window'")
        print("2. 主窗口样式表使用了 #main_window 选择器")
        print("3. 主窗口样式表不再使用通用的 QWidget 选择器")
        print("4. ModernMetricCard 移除了样式表备份")
        print("5. unified_performance_widget 移除了卡片样式恢复方法")
        print("\n这样可以避免主窗口样式表影响子组件！")
        print("代码框架更干净，没有不必要的兜底代码！")
    else:
        print("❌ 部分检查未通过，请检查代码")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = check_style_inheritance_fix()
    sys.exit(0 if success else 1)
