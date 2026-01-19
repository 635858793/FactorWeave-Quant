#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 miniqmt_plugin 加载
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_miniqmt_plugin():
    """测试 miniqmt_plugin 加载"""
    try:
        print("开始测试 miniqmt_plugin 加载...")
        
        # 导入必要的模块
        print("1. 导入核心模块...")
        from core.plugin_types import AssetType, DataType
        print("   ✅ 核心模块导入成功")
        
        # 导入插件
        print("2. 导入 miniqmt_plugin...")
        from plugins.data_sources.stock.miniqmt_plugin import MiniQMTPlugin, MiniQMTConfig
        print("   ✅ miniqmt_plugin 导入成功")
        
        # 测试配置
        print("3. 测试配置...")
        config = MiniQMTConfig()
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
        
        # 测试插件实例化
        print("5. 测试插件实例化...")
        plugin = MiniQMTPlugin()
        print(f"   插件ID: {plugin.plugin_id}")
        print(f"   插件名称: {plugin.plugin_name}")
        print("   ✅ 插件实例化成功")
        
        print("\n✅ miniqmt_plugin 加载测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ miniqmt_plugin 加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_miniqmt_plugin()
    sys.exit(0 if success else 1)
