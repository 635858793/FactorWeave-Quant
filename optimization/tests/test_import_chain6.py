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

# 测试1: 导入 core.loguru_config
try:
    print("\n1. 导入 core.loguru_config...")
    from core.loguru_config import initialize_loguru
    print("✓ core.loguru_config 导入成功")
except Exception as e:
    print(f"✗ core.loguru_config 导入失败: {e}")

# 测试2: 导入 core.plugin_manager
try:
    print("\n2. 导入 core.plugin_manager...")
    from core.plugin_manager import PluginManager
    print("✓ core.plugin_manager 导入成功")
except Exception as e:
    print(f"✗ core.plugin_manager 导入失败: {e}")

# 测试3: 导入 core.services.tensorflow_gpu_manager
try:
    print("\n3. 导入 core.services.tensorflow_gpu_manager...")
    from core.services.tensorflow_gpu_manager import TensorFlowGPUManager
    print("✓ core.services.tensorflow_gpu_manager 导入成功")
except Exception as e:
    print(f"✗ core.services.tensorflow_gpu_manager 导入失败: {e}")

# 测试4: 导入 core.services.base_service
try:
    print("\n4. 导入 core.services.base_service...")
    from core.services.base_service import BaseService
    print("✓ core.services.base_service 导入成功")
except Exception as e:
    print(f"✗ core.services.base_service 导入失败: {e}")

print("\n=== 测试完成 ===")
