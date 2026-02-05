#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入 core.services.cache_service，看看是否启动性能监控
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=== 开始测试 ===")

# 测试1: 导入 core.services.cache_service
try:
    print("\n1. 导入 core.services.cache_service...")
    from core.services.cache_service import CacheService
    print("✓ core.services.cache_service 导入成功")
except Exception as e:
    print(f"✗ core.services.cache_service 导入失败: {e}")

print("\n=== 测试完成 ===")
