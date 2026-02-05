#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 importlib 执行模块加载
"""

import sys
import os
import importlib.util

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 使用 importlib 加载并执行模块 ===")

module_path = os.path.join(os.path.dirname(__file__), '..', 'optimization_dashboard.py')
print(f"模块路径: {module_path}")

try:
    spec = importlib.util.spec_from_file_location("optimization_dashboard", module_path)
    if spec and spec.loader:
        print("✓ 成功创建模块规范")
        
        module = importlib.util.module_from_spec(spec)
        print("✓ 成功创建模块对象")
        
        # 执行模块加载
        print("\n开始执行模块加载...")
        spec.loader.exec_module(module)
        print("✓ 模块加载成功")
        
        # 检查模块属性
        print("\n模块属性:")
        print(f"  GUI_AVAILABLE: {getattr(module, 'GUI_AVAILABLE', '未定义')}")
        print(f"  CHARTS_AVAILABLE: {getattr(module, 'CHARTS_AVAILABLE', '未定义')}")
        
        print("\n检查类是否存在:")
        print(f"  OptimizationDashboardConfig: {hasattr(module, 'OptimizationDashboardConfig')}")
        print(f"  DatabaseConnectionManager: {hasattr(module, 'DatabaseConnectionManager')}")
        print(f"  OptimizationDataManager: {hasattr(module, 'OptimizationDataManager')}")
        print(f"  OptimizationExecutor: {hasattr(module, 'OptimizationExecutor')}")
        print(f"  OptimizationDashboard: {hasattr(module, 'OptimizationDashboard')}")
        print(f"  create_optimization_dashboard: {hasattr(module, 'create_optimization_dashboard')}")
        
        print("\n=== 模块加载测试完成 ===")
    else:
        print("✗ 无法创建模块规范")
        
except Exception as e:
    print(f"✗ 模块加载失败: {e}")
    import traceback
    traceback.print_exc()
