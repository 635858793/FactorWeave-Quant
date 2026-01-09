#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试逐步导入
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("开始测试逐步导入...")

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

# 步骤3: 导入database_service
print("\n3. 导入 core.services.database_service...")
try:
    from core.services.database_service import DatabaseService
    print("   ✅ core.services.database_service 导入成功")
except Exception as e:
    print(f"   ❌ core.services.database_service 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤4: 创建数据库服务实例
print("\n4. 创建数据库服务实例...")
try:
    db_service = DatabaseService(service_container)
    print("   ✅ 数据库服务实例创建成功")
except Exception as e:
    print(f"   ❌ 数据库服务实例创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤5: 初始化数据库服务
print("\n5. 初始化数据库服务...")
try:
    db_service.initialize()
    print("   ✅ 数据库服务初始化成功")
except Exception as e:
    print(f"   ❌ 数据库服务初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤6: 导入events
print("\n6. 导入 core.events...")
try:
    from core.events import EventBus
    print("   ✅ core.events 导入成功")
except Exception as e:
    print(f"   ❌ core.events 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤7: 创建事件总线
print("\n7. 创建事件总线...")
try:
    event_bus = EventBus()
    print("   ✅ 事件总线创建成功")
except Exception as e:
    print(f"   ❌ 事件总线创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤8: 导入account_repository
print("\n8. 导入 core.trading.account_repository...")
try:
    from core.trading.account_repository import AccountRepository
    print("   ✅ core.trading.account_repository 导入成功")
except Exception as e:
    print(f"   ❌ core.trading.account_repository 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤9: 创建账户仓储
print("\n9. 创建账户仓储...")
try:
    repository = AccountRepository(service_container, event_bus)
    print("   ✅ 账户仓储创建成功")
except Exception as e:
    print(f"   ❌ 账户仓储创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ 所有步骤测试通过")
