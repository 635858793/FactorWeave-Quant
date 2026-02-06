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

# 测试2: 导入 core.enums.plugin_state
try:
    print("\n2. 导入 core.enums.plugin_state...")
    from core.enums.plugin_state import PluginLifecycle
    print("✓ core.enums.plugin_state 导入成功")
except Exception as e:
    print(f"✗ core.enums.plugin_state 导入失败: {e}")

# 测试3: 导入 core.plugin_types
try:
    print("\n3. 导入 core.plugin_types...")
    from core.plugin_types import PluginType, PluginCategory
    print("✓ core.plugin_types 导入成功")
except Exception as e:
    print(f"✗ core.plugin_types 导入失败: {e}")

# 测试4: 导入 plugins.plugin_interface
try:
    print("\n4. 导入 plugins.plugin_interface...")
    from plugins.plugin_interface import IPlugin
    print("✓ plugins.plugin_interface 导入成功")
except Exception as e:
    print(f"✗ plugins.plugin_interface 导入失败: {e}")

# 测试5: 导入 core.plugin_manager
try:
    print("\n5. 导入 core.plugin_manager...")
    from core.plugin_manager import PluginManager
    print("✓ core.plugin_manager 导入成功")
except Exception as e:
    print(f"✗ core.plugin_manager 导入失败: {e}")

print("\n=== 测试完成 ===")
