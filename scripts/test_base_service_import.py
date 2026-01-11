#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入base_service
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("开始测试导入base_service...")

# 步骤1: 导入events
print("\n1. 导入 core.events...")
try:
    from core.events import EventBus
    print("   ✅ core.events 导入成功")
except Exception as e:
    print(f"   ❌ core.events 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤2: 导入base_service
print("\n2. 导入 core.services.base_service...")
try:
    from core.services.base_service import BaseService
    print("   ✅ core.services.base_service 导入成功")
except Exception as e:
    print(f"   ❌ core.services.base_service 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ 所有步骤测试通过")
