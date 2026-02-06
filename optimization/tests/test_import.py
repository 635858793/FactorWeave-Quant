#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的导入测试脚本
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 开始导入测试 ===")

try:
    print("正在导入 optimization.optimization_dashboard...")
    import optimization.optimization_dashboard as od
    print("✓ 模块导入成功")
    
    print("\n检查类是否存在:")
    print(f"  OptimizationDashboardConfig: {hasattr(od, 'OptimizationDashboardConfig')}")
    print(f"  DatabaseConnectionManager: {hasattr(od, 'DatabaseConnectionManager')}")
    print(f"  OptimizationDataManager: {hasattr(od, 'OptimizationDataManager')}")
    print(f"  OptimizationExecutor: {hasattr(od, 'OptimizationExecutor')}")
    print(f"  OptimizationDashboard: {hasattr(od, 'OptimizationDashboard')}")
    print(f"  create_optimization_dashboard: {hasattr(od, 'create_optimization_dashboard')}")
    
    print("\n=== 导入测试完成 ===")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()
