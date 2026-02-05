#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试导入问题的脚本
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 开始调试导入问题 ===")

# 逐步导入以定位问题
try:
    print("1. 导入标准库...")
    import loguru
    print("✓ loguru 导入成功")
    
    print("\n2. 尝试导入 PyQt5...")
    try:
        from PyQt5.QtWidgets import QApplication
        print("✓ PyQt5 导入成功")
        print(f"  QApplication 实例: {QApplication.instance()}")
    except ImportError as e:
        print(f"✗ PyQt5 导入失败: {e}")
    
    print("\n3. 尝试导入 optimization.optimization_dashboard...")
    try:
        import optimization.optimization_dashboard as od
        print("✓ optimization.optimization_dashboard 导入成功")
        
        print(f"\n4. 检查 GUI_AVAILABLE: {od.GUI_AVAILABLE}")
        print(f"   检查 CHARTS_AVAILABLE: {od.CHARTS_AVAILABLE}")
        
        print("\n5. 检查类是否存在:")
        print(f"  OptimizationDashboardConfig: {hasattr(od, 'OptimizationDashboardConfig')}")
        print(f"  DatabaseConnectionManager: {hasattr(od, 'DatabaseConnectionManager')}")
        print(f"  OptimizationDataManager: {hasattr(od, 'OptimizationDataManager')}")
        print(f"  OptimizationExecutor: {hasattr(od, 'OptimizationExecutor')}")
        print(f"  OptimizationDashboard: {hasattr(od, 'OptimizationDashboard')}")
        print(f"  create_optimization_dashboard: {hasattr(od, 'create_optimization_dashboard')}")
        
    except Exception as e:
        print(f"✗ optimization.optimization_dashboard 导入失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== 调试完成 ===")
    
except Exception as e:
    print(f"✗ 调试过程出错: {e}")
    import traceback
    traceback.print_exc()
