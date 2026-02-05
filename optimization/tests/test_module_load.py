#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 importlib 导入模块以避免执行模块级别的代码
"""

import sys
import os
import importlib.util

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 使用 importlib 加载模块 ===")

module_path = os.path.join(os.path.dirname(__file__), '..', 'optimization_dashboard.py')
print(f"模块路径: {module_path}")

try:
    spec = importlib.util.spec_from_file_location("optimization_dashboard", module_path)
    if spec and spec.loader:
        print("✓ 成功创建模块规范")
        
        module = importlib.util.module_from_spec(spec)
        print("✓ 成功创建模块对象")
        
        # 不执行模块，只检查规范
        print("\n模块规范信息:")
        print(f"  名称: {spec.name}")
        print(f"  原点: {spec.origin}")
        print(f"  加载器: {spec.loader}")
        
        print("\n=== 模块加载测试完成 ===")
    else:
        print("✗ 无法创建模块规范")
        
except Exception as e:
    print(f"✗ 模块加载失败: {e}")
    import traceback
    traceback.print_exc()
