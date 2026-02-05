#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证白屏问题修复效果 - 代码检查版本
"""

import sys
import os
import re

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_code_fix():
    """检查代码修复是否正确"""
    print("=" * 60)
    print("检查白屏问题修复代码")
    print("=" * 60)
    
    # 读取 unified_performance_widget.py 文件
    file_path = "gui/widgets/performance/unified_performance_widget.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查1: _apply_modern_styling 方法是否更新了 _original_stylesheet
        print("\n检查1: _apply_modern_styling 方法是否更新了 _original_stylesheet")
        pattern = r'def _apply_modern_styling\(self\):.*?if hasattr\(self, \'_original_stylesheet\'\):.*?self\._original_stylesheet = self\.styleSheet\(\)'
        if re.search(pattern, content, re.DOTALL):
            print("✅ _apply_modern_styling 方法正确更新了 _original_stylesheet")
            check1_passed = True
        else:
            print("❌ _apply_modern_styling 方法未更新 _original_stylesheet")
            check1_passed = False
        
        # 检查2: _setup_style_protection 方法是否保存了 _original_stylesheet
        print("\n检查2: _setup_style_protection 方法是否保存了 _original_stylesheet")
        pattern = r'def _setup_style_protection\(self\):.*?self\._original_stylesheet = self\.styleSheet\(\)'
        if re.search(pattern, content, re.DOTALL):
            print("✅ _setup_style_protection 方法正确保存了 _original_stylesheet")
            check2_passed = True
        else:
            print("❌ _setup_style_protection 方法未保存 _original_stylesheet")
            check2_passed = False
        
        # 检查3: _check_and_restore_styles 方法是否使用 _original_stylesheet 恢复样式
        print("\n检查3: _check_and_restore_styles 方法是否使用 _original_stylesheet 恢复样式")
        pattern = r'def _check_and_restore_styles\(self\):.*?if self\._original_stylesheet:.*?self\.setStyleSheet\(self\._original_stylesheet\)'
        if re.search(pattern, content, re.DOTALL):
            print("✅ _check_and_restore_styles 方法正确使用 _original_stylesheet 恢复样式")
            check3_passed = True
        else:
            print("❌ _check_and_restore_styles 方法未使用 _original_stylesheet 恢复样式")
            check3_passed = False
        
        # 检查4: 样式表是否包含正确的背景颜色
        print("\n检查4: 样式表是否包含正确的背景颜色")
        pattern = r'background: #2c3e50'
        if re.search(pattern, content):
            print("✅ 样式表包含正确的背景颜色 #2c3e50（深蓝色）")
            check4_passed = True
        else:
            print("❌ 样式表未包含正确的背景颜色")
            check4_passed = False
        
        # 检查5: 调用顺序是否正确
        print("\n检查5: 调用顺序是否正确")
        # 查找 _setup_style_protection 和 _apply_modern_styling 的调用位置
        setup_pos = content.find('self._setup_style_protection()')
        apply_pos = content.find('self._apply_modern_styling()')
        
        if setup_pos != -1 and apply_pos != -1:
            if setup_pos < apply_pos:
                print("✅ 调用顺序正确：_setup_style_protection 在 _apply_modern_styling 之前")
                print("   并且 _apply_modern_styling 会更新 _original_stylesheet")
                check5_passed = True
            else:
                print("❌ 调用顺序不正确")
                check5_passed = False
        else:
            print("❌ 未找到方法调用")
            check5_passed = False
        
        # 总结
        print("\n" + "=" * 60)
        all_passed = check1_passed and check2_passed and check3_passed and check4_passed and check5_passed
        if all_passed:
            print("✅ 所有检查通过！白屏问题修复代码正确！")
            print("\n修复说明：")
            print("1. _setup_style_protection() 先被调用，初始化 _original_stylesheet")
            print("2. _apply_modern_styling() 后被调用，设置样式表并更新 _original_stylesheet")
            print("3. _check_and_restore_styles() 每5秒检查一次，如果样式表丢失则恢复")
            print("4. 确保 _original_stylesheet 始终保存最新的样式表")
            print("\n这样可以防止背景变成白色的问题！")
        else:
            print("❌ 部分检查未通过，请检查代码")
        print("=" * 60)
        
        return all_passed
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = check_code_fix()
    sys.exit(0 if success else 1)
