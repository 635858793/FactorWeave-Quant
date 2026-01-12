#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试修复后的资产列表获取功能
"""

import sys
import os

def test_asset_list_retrieval():
    """测试资产列表获取功能"""
    try:
        print("测试资产列表获取功能...")
        print("=" * 60)
        
        # 导入必要的模块
        from core.services.unified_data_manager import UnifiedDataManager
        
        # 直接实例化 UnifiedDataManager
        data_manager = UnifiedDataManager()
        
        print("✅ UnifiedDataManager 初始化成功")
        
        # 测试获取 A 股列表
        print("\n测试获取 A 股列表...")
        stock_list = data_manager.get_asset_list('stock_a')
        
        if stock_list.empty:
            print("❌ A 股列表为空")
            return 1
        
        print(f"✅ 成功获取 A 股列表: {len(stock_list)} 只股票")
        
        # 显示前 5 只股票
        print("\n前 5 只股票:")
        print(stock_list.head())
        
        # 检查数据完整性
        required_columns = ['code', 'name', 'market', 'industry', 'sector']
        missing_columns = [col for col in required_columns if col not in stock_list.columns]
        
        if missing_columns:
            print(f"\n⚠️ 缺少必要的列: {missing_columns}")
        else:
            print("\n✅ 数据完整性检查通过")
        
        # 测试获取其他资产类型
        print("\n测试获取其他资产类型列表...")
        asset_types = ['stock_b', 'stock_h', 'stock_hk', 'stock_us', 'crypto', 'fund', 'bond']
        
        for asset_type in asset_types:
            try:
                asset_list = data_manager.get_asset_list(asset_type)
                if not asset_list.empty:
                    print(f"✅ {asset_type}: {len(asset_list)} 个资产")
                else:
                    print(f"⚠️ {asset_type}: 无数据")
            except Exception as e:
                print(f"❌ {asset_type}: 获取失败 - {e}")
        
        print("\n" + "=" * 60)
        print("测试完成！")
        return 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(test_asset_list_retrieval())
