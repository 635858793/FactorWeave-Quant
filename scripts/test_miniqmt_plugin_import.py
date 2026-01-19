#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 miniqmt_plugin 模块加载（不实例化）
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_miniqmt_plugin_import():
    """测试 miniqmt_plugin 模块导入"""
    try:
        print("开始测试 miniqmt_plugin 模块导入...")
        
        # 导入必要的模块
        print("1. 导入核心模块...")
        from core.plugin_types import AssetType, DataType
        print("   ✅ 核心模块导入成功")
        
        # 导入插件模块
        print("2. 导入 miniqmt_plugin 模块...")
        import plugins.data_sources.stock.miniqmt_plugin as miniqmt_plugin
        print("   ✅ miniqmt_plugin 模块导入成功")
        
        # 测试配置类
        print("3. 测试配置类...")
        config = miniqmt_plugin.MiniQMTConfig()
        print(f"   支持的数据类型: {config.supported_data_types}")
        print(f"   支持的资产类型: {config.supported_asset_types}")
        
        # 验证 DataType 枚举值是否正确
        print("4. 验证 DataType 枚举值...")
        expected_types = [
            DataType.REAL_TIME_QUOTE,
            DataType.TICK_DATA,
            DataType.HISTORICAL_KLINE,
            DataType.LEVEL2_DATA
        ]
        
        for expected_type in expected_types:
            if expected_type in config.supported_data_types:
                print(f"   ✅ {expected_type.name} 存在")
            else:
                print(f"   ❌ {expected_type.name} 不存在")
                return False
        
        # 验证没有 KLINE_DATA
        print("5. 验证 KLINE_DATA 不存在...")
        try:
            _ = DataType.KLINE_DATA
            print("   ❌ DataType.KLINE_DATA 不应该存在")
            return False
        except AttributeError:
            print("   ✅ DataType.KLINE_DATA 正确地不存在")
        
        # 测试插件类存在
        print("6. 验证插件类存在...")
        plugin_class = miniqmt_plugin.MiniQMTPlugin
        print(f"   插件类: {plugin_class.__name__}")
        print("   ✅ 插件类存在")
        
        print("\n✅ miniqmt_plugin 模块加载测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ miniqmt_plugin 模块加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_miniqmt_plugin_import()
    sys.exit(0 if success else 1)
