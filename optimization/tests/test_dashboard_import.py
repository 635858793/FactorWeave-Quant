#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入 optimization_dashboard.py
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 开始测试导入 optimization_dashboard ===")

try:
    print("\n正在导入 optimization.optimization_dashboard...")
    import optimization.optimization_dashboard as od
    print("✓ optimization.optimization_dashboard 导入成功")
    
    print(f"\nGUI_AVAILABLE: {od.GUI_AVAILABLE}")
    print(f"CHARTS_AVAILABLE: {od.CHARTS_AVAILABLE}")
    
    print("\n检查类是否存在:")
    print(f"  OptimizationDashboardConfig: {hasattr(od, 'OptimizationDashboardConfig')}")
    print(f"  DatabaseConnectionManager: {hasattr(od, 'DatabaseConnectionManager')}")
    print(f"  OptimizationDataManager: {hasattr(od, 'OptimizationDataManager')}")
    print(f"  OptimizationExecutor: {hasattr(od, 'OptimizationExecutor')}")
    print(f"  OptimizationDashboard: {hasattr(od, 'OptimizationDashboard')}")
    print(f"  create_optimization_dashboard: {hasattr(od, 'create_optimization_dashboard')}")
    
    print("\n=== 测试成功完成 ===")
    
except Exception as e:
    print(f"\n✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    print("\n=== 测试失败 ===")
