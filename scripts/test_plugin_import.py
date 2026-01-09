#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试插件接口导入
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_plugin_interface_import():
    """测试插件接口导入"""
    try:
        print("开始测试插件接口导入...")
        
        # 测试导入core.enums.plugin_state
        print("1. 导入 core.enums.plugin_state...")
        from core.enums.plugin_state import PluginLifecycle
        print("   ✅ core.enums.plugin_state 导入成功")
        
        # 测试导入core.plugin_types
        print("2. 导入 core.plugin_types...")
        from core.plugin_types import PluginType, PluginCategory, AssetType, DataType
        print("   ✅ core.plugin_types 导入成功")
        
        # 测试导入plugins.plugin_interface
        print("3. 导入 plugins.plugin_interface...")
        from plugins.plugin_interface import IPlugin, PluginType, PluginCategory, PluginMetadata
        print("   ✅ plugins.plugin_interface 导入成功")
        
        print("✅ 所有导入测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_plugin_interface_import()
    sys.exit(0 if success else 1)
