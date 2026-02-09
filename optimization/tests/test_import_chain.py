#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入链，找出性能监控系统自动启动的原因
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 开始测试导入链 ===")

# 测试1: 导入 core.events
try:
    print("\n1. 导入 core.events...")
    from core.events import get_event_bus
    print("✓ core.events 导入成功")
except Exception as e:
    print(f"✗ core.events 导入失败: {e}")

# 测试2: 导入 core.metrics.events
try:
    print("\n2. 导入 core.metrics.events...")
    from core.metrics.events import SystemResourceUpdated
    print("✓ core.metrics.events 导入成功")
except Exception as e:
    print(f"✗ core.metrics.events 导入失败: {e}")

# 测试3: 导入 core.containers
try:
    print("\n3. 导入 core.containers...")
    from core.containers import get_service_container
    print("✓ core.containers 导入成功")
except Exception as e:
    print(f"✗ core.containers 导入失败: {e}")

# 测试4: 导入 core.services
try:
    print("\n4. 导入 core.services...")
    from core.services import ConfigService
    print("✓ core.services 导入成功")
except Exception as e:
    print(f"✗ core.services 导入失败: {e}")

# 测试5: 导入 core.services.cache_service
try:
    print("\n5. 导入 core.services.cache_service...")
    from core.services.cache_service import CacheService
    print("✓ core.services.cache_service 导入成功")
except Exception as e:
    print(f"✗ core.services.cache_service 导入失败: {e}")

print("\n=== 测试完成 ===")
