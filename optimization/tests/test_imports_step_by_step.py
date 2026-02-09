#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的测试脚本，直接测试类定义
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 开始测试 ===")

# 测试1: 导入核心模块
try:
    print("\n1. 导入核心模块...")
    from core.events import get_event_bus
    print("✓ core.events 导入成功")
except Exception as e:
    print(f"✗ core.events 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 测试2: 导入优化模块
try:
    print("\n2. 导入优化模块...")
    from optimization.algorithm_optimizer import PerformanceEvaluator
    print("✓ optimization.algorithm_optimizer 导入成功")
except Exception as e:
    print(f"✗ optimization.algorithm_optimizer 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 测试3: 导入数据库模块
try:
    print("\n3. 导入数据库模块...")
    from optimization.database_schema import OptimizationDatabaseManager
    print("✓ optimization.database_schema 导入成功")
except Exception as e:
    print(f"✗ optimization.database_schema 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 测试4: 导入版本管理模块
try:
    print("\n4. 导入版本管理模块...")
    from optimization.version_manager import VersionManager
    print("✓ optimization.version_manager 导入成功")
except Exception as e:
    print(f"✗ optimization.version_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 测试5: 导入自动调优模块
try:
    print("\n5. 导入自动调优模块...")
    from optimization.auto_tuner import AlgorithmAutoTuner
    print("✓ optimization.auto_tuner 导入成功")
except Exception as e:
    print(f"✗ optimization.auto_tuner 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试完成 ===")
