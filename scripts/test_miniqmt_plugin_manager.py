#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 miniqmt_plugin 通过 plugin_manager 加载
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_miniqmt_plugin_via_manager():
    """测试 miniqmt_plugin 通过 plugin_manager 加载"""
    try:
        print("开始测试 miniqmt_plugin 通过 plugin_manager 加载...")
        
        # 导入核心模块
        print("1. 导入核心模块...")
        from core.plugin_types import AssetType, DataType
        from core.plugin_manager import PluginManager
        print("   ✅ 核心模块导入成功")
        
        # 创建插件管理器
        print("2. 创建插件管理器...")
        manager = PluginManager()
        print("   ✅ 插件管理器创建成功")
        
        # 加载 miniqmt_plugin
        print("3. 加载 miniqmt_plugin...")
        plugin_name = "data_sources.stock.miniqmt_plugin"
        plugin_path = project_root / "plugins" / "data_sources" / "stock" / "miniqmt_plugin.py"
        
        success = manager.load_plugin(plugin_name, plugin_path)
        
        if success:
            print("   ✅ miniqmt_plugin 加载成功")
            
            # 检查插件是否在已加载列表中
            if plugin_name in manager.loaded_plugins:
                print(f"   ✅ 插件已注册: {plugin_name}")
                plugin_info = manager.loaded_plugins[plugin_name]
                print(f"   插件信息: {plugin_info}")
            else:
                print(f"   ⚠️  插件未在已加载列表中: {plugin_name}")
            
            return True
        else:
            print("   ❌ miniqmt_plugin 加载失败")
            return False
        
    except Exception as e:
        print(f"\n❌ miniqmt_plugin 加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_miniqmt_plugin_via_manager()
    sys.exit(0 if success else 1)
