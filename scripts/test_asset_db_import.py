#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入asset_database_manager
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("开始测试导入asset_database_manager...")

# 步骤1: 导入plugin_types
print("\n1. 导入 core.plugin_types...")
try:
    from core.plugin_types import AssetType, DataType
    print("   ✅ core.plugin_types 导入成功")
except Exception as e:
    print(f"   ❌ core.plugin_types 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤2: 导入asset_type_identifier
print("\n2. 导入 core.asset_type_identifier...")
try:
    from core.asset_type_identifier import AssetTypeIdentifier
    print("   ✅ core.asset_type_identifier 导入成功")
except Exception as e:
    print(f"   ❌ core.asset_type_identifier 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤3: 导入duckdb_manager
print("\n3. 导入 core.database.duckdb_manager...")
try:
    from core.database.duckdb_manager import DuckDBConnectionManager
    print("   ✅ core.database.duckdb_manager 导入成功")
except Exception as e:
    print(f"   ❌ core.database.duckdb_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤4: 导入asset_database_manager
print("\n4. 导入 core.asset_database_manager...")
try:
    from core.asset_database_manager import AssetSeparatedDatabaseManager
    print("   ✅ core.asset_database_manager 导入成功")
except Exception as e:
    print(f"   ❌ core.asset_database_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ 所有步骤测试通过")
