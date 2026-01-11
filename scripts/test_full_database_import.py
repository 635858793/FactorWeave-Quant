#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整导入database_service
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("开始测试完整导入database_service...")

# 步骤1: 导入containers
print("\n1. 导入 core.containers...")
try:
    from core.containers import get_service_container
    print("   ✅ core.containers 导入成功")
except Exception as e:
    print(f"   ❌ core.containers 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤2: 获取服务容器
print("\n2. 获取服务容器...")
try:
    service_container = get_service_container()
    print("   ✅ 服务容器获取成功")
except Exception as e:
    print(f"   ❌ 服务容器获取失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤3: 导入events
print("\n3. 导入 core.events...")
try:
    from core.events import EventBus
    print("   ✅ core.events 导入成功")
except Exception as e:
    print(f"   ❌ core.events 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤4: 导入base_service
print("\n4. 导入 core.services.base_service...")
try:
    from core.services.base_service import BaseService
    print("   ✅ core.services.base_service 导入成功")
except Exception as e:
    print(f"   ❌ core.services.base_service 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤5: 导入plugin_types
print("\n5. 导入 core.plugin_types...")
try:
    from core.plugin_types import AssetType, DataType
    print("   ✅ core.plugin_types 导入成功")
except Exception as e:
    print(f"   ❌ core.plugin_types 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤6: 导入asset_database_manager
print("\n6. 导入 core.asset_database_manager...")
try:
    from core.asset_database_manager import AssetSeparatedDatabaseManager
    print("   ✅ core.asset_database_manager 导入成功")
except Exception as e:
    print(f"   ❌ core.asset_database_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤7: 导入database_service
print("\n7. 导入 core.services.database_service...")
try:
    from core.services.database_service import DatabaseService
    print("   ✅ core.services.database_service 导入成功")
except Exception as e:
    print(f"   ❌ core.services.database_service 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤8: 创建数据库服务实例
print("\n8. 创建数据库服务实例...")
try:
    db_service = DatabaseService(service_container)
    print("   ✅ 数据库服务实例创建成功")
except Exception as e:
    print(f"   ❌ 数据库服务实例创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤9: 初始化数据库服务
print("\n9. 初始化数据库服务...")
try:
    db_service.initialize()
    print("   ✅ 数据库服务初始化成功")
except Exception as e:
    print(f"   ❌ 数据库服务初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ 所有步骤测试通过")
