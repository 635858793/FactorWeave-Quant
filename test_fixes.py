#!/usr/bin/env python3
"""测试修复的错误"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("测试1: PerformanceAutoTuner debug_mode 参数")
try:
    from core.performance.unified_monitor import PerformanceAutoTuner
    tuner = PerformanceAutoTuner(debug_mode=True)
    print(f"✓ PerformanceAutoTuner(debug_mode=True) 创建成功")
    print(f"  debug_mode 属性: {tuner.debug_mode}")
    
    tuner2 = PerformanceAutoTuner(debug_mode=False)
    print(f"✓ PerformanceAutoTuner(debug_mode=False) 创建成功")
    print(f"  debug_mode 属性: {tuner2.debug_mode}")
    
    tuner3 = PerformanceAutoTuner()
    print(f"✓ PerformanceAutoTuner() 创建成功")
    print(f"  debug_mode 属性: {tuner3.debug_mode}")
    
    result = tuner.smart_optimize(performance_threshold=0.8, improvement_target=0.1)
    print(f"✓ smart_optimize 方法调用成功")
    print(f"  结果: {result}")
    
except Exception as e:
    print(f"✗ PerformanceAutoTuner 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n测试2: 数据库 created_by 列")
try:
    from optimization.database_schema import DatabaseSchema
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db_schema = DatabaseSchema(db_path)
        db_schema.init_tables()
        
        print(f"✓ 数据库初始化成功")
        
        conn = db_schema.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(algorithm_versions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"  algorithm_versions 表列: {columns}")
        
        if 'created_by' in columns:
            print(f"✓ created_by 列存在")
        else:
            print(f"✗ created_by 列不存在")
        
        conn.close()
        
        version_id = db_schema.save_algorithm_version(
            pattern_id=1,
            pattern_name="test_pattern",
            algorithm_code="test code",
            parameters={},
            description="test version",
            optimization_method="manual",
            created_by="test_user"
        )
        
        print(f"✓ 保存版本成功，ID: {version_id}")
        
        versions = db_schema.get_algorithm_versions("test_pattern")
        print(f"✓ 获取版本列表成功，数量: {len(versions)}")
        
        if versions:
            version = versions[0]
            print(f"  版本数据: {version}")
            if 'created_by' in version:
                print(f"✓ created_by 字段存在: {version['created_by']}")
            else:
                print(f"✗ created_by 字段不存在")
        
except Exception as e:
    print(f"✗ 数据库测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n测试3: VersionManager created_by 参数")
try:
    from optimization.version_manager import VersionManager
    from dataclasses import dataclass
    from typing import Optional
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test2.db")
        vm = VersionManager(db_path)
        
        print(f"✓ VersionManager 创建成功")
        
        version_id = vm.save_version(
            pattern_id=1,
            pattern_name="test_pattern2",
            algorithm_code="test code 2",
            parameters={},
            description="test version 2",
            optimization_method="manual",
            created_by="test_user2"
        )
        
        print(f"✓ 保存版本成功，ID: {version_id}")
        
        versions = vm.get_versions("test_pattern2")
        print(f"✓ 获取版本列表成功，数量: {len(versions)}")
        
        if versions:
            version = versions[0]
            print(f"  版本 created_by: {version.created_by}")
            if version.created_by == "test_user2":
                print(f"✓ created_by 值正确")
            else:
                print(f"✗ created_by 值不正确: {version.created_by}")
        
except Exception as e:
    print(f"✗ VersionManager 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n所有测试完成")
