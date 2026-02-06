#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证卡片白屏问题修复效果
"""

import sys
import os
import re

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_card_style_fix():
    """检查卡片样式修复是否正确"""
    print("=" * 60)
    print("检查卡片白屏问题修复代码")
    print("=" * 60)
    
    # 检查1: ModernMetricCard 是否保存了样式表备份
    print("\n检查1: ModernMetricCard 是否保存了样式表备份")
    card_file = "gui/widgets/performance/components/metric_card.py"
    try:
        with open(card_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'self\._backup_style = self\.styleSheet\(\)'
        if re.search(pattern, content):
            print("✅ ModernMetricCard 正确保存了样式表备份")
            check1_passed = True
        else:
            print("❌ ModernMetricCard 未保存样式表备份")
            check1_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check1_passed = False
    
    # 检查2: ModernMetricCard 的样式表是否包含正确的背景颜色
    print("\n检查2: ModernMetricCard 的样式表是否包含正确的背景颜色")
    try:
        with open(card_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'background: qlineargradient.*#2c3e50.*#34495e'
        if re.search(pattern, content, re.DOTALL):
            print("✅ ModernMetricCard 样式表包含正确的深蓝色渐变背景")
            check2_passed = True
        else:
            print("❌ ModernMetricCard 样式表未包含正确的背景颜色")
            check2_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check2_passed = False
    
    # 检查3: unified_performance_widget 是否添加了卡片样式恢复方法
    print("\n检查3: unified_performance_widget 是否添加了卡片样式恢复方法")
    widget_file = "gui/widgets/performance/unified_performance_widget.py"
    try:
        with open(widget_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'def _restore_card_styles\(self\):'
        if re.search(pattern, content):
            print("✅ unified_performance_widget 添加了卡片样式恢复方法")
            check3_passed = True
        else:
            print("❌ unified_performance_widget 未添加卡片样式恢复方法")
            check3_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check3_passed = False
    
    # 检查4: _check_and_restore_styles 是否调用了卡片样式恢复
    print("\n检查4: _check_and_restore_styles 是否调用了卡片样式恢复")
    try:
        with open(widget_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'def _check_and_restore_styles\(self\):.*?self\._restore_card_styles\(\)'
        if re.search(pattern, content, re.DOTALL):
            print("✅ _check_and_restore_styles 正确调用了卡片样式恢复")
            check4_passed = True
        else:
            print("❌ _check_and_restore_styles 未调用卡片样式恢复")
            check4_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check4_passed = False
    
    # 检查5: _restore_card_styles 是否正确实现了卡片样式恢复逻辑
    print("\n检查5: _restore_card_styles 是否正确实现了卡片样式恢复逻辑")
    try:
        with open(widget_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否导入了ModernMetricCard
        pattern1 = r'from gui\.widgets\.performance\.components\.metric_card import ModernMetricCard'
        # 检查是否使用findChildren查找卡片
        pattern2 = r'cards = self\.findChildren\(ModernMetricCard\)'
        # 检查是否恢复样式表
        pattern3 = r'card\.setStyleSheet\(card\._backup_style\)'
        
        if re.search(pattern1, content) and re.search(pattern2, content) and re.search(pattern3, content):
            print("✅ _restore_card_styles 正确实现了卡片样式恢复逻辑")
            check5_passed = True
        else:
            print("❌ _restore_card_styles 未正确实现卡片样式恢复逻辑")
            if not re.search(pattern1, content):
                print("   - 未导入ModernMetricCard")
            if not re.search(pattern2, content):
                print("   - 未使用findChildren查找卡片")
            if not re.search(pattern3, content):
                print("   - 未恢复样式表")
            check5_passed = False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        check5_passed = False
    
    # 总结
    print("\n" + "=" * 60)
    all_passed = check1_passed and check2_passed and check3_passed and check4_passed and check5_passed
    if all_passed:
        print("✅ 所有检查通过！卡片白屏问题修复代码正确！")
        print("\n修复说明：")
        print("1. ModernMetricCard在init_ui中保存了样式表备份")
        print("2. unified_performance_widget添加了_restore_card_styles方法")
        print("3. _check_and_restore_styles每5秒调用一次_restore_card_styles")
        print("4. _restore_card_styles递归查找所有ModernMetricCard实例")
        print("5. 检查并恢复所有卡片组件的样式表")
        print("\n这样可以防止卡片背景变成白色的问题！")
    else:
        print("❌ 部分检查未通过，请检查代码")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = check_card_style_fix()
    sys.exit(0 if success else 1)
