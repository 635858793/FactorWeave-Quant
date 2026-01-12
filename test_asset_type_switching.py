#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试智能推荐面板的资产类型切换
"""

import sys
import asyncio

async def test_asset_type_switching():
    """测试资产类型切换"""
    try:
        from core.services.smart_recommendation_engine import SmartRecommendationEngine, RecommendationType
        from core.plugin_types import AssetType
        from core.services.unified_data_manager import UnifiedDataManager
        
        print("测试智能推荐面板的资产类型切换...")
        print("=" * 60)
        
        # 1. 创建推荐引擎
        print("\n1. 创建推荐引擎...")
        engine = SmartRecommendationEngine()
        print("✅ 推荐引擎创建成功")
        
        # 2. 测试加载不同资产类型的数据
        print("\n2. 测试加载不同资产类型的数据...")
        
        asset_types = [
            AssetType.STOCK_A,
            AssetType.CRYPTO,
            AssetType.FUND,
            AssetType.BOND
        ]
        
        data_manager = UnifiedDataManager()
        
        for asset_type in asset_types:
            asset_type_str = asset_type.value
            print(f"\n   测试资产类型: {asset_type_str}")
            
            # 获取资产列表
            asset_list = data_manager.get_asset_list(asset_type_str)
            print(f"   资产列表数量: {len(asset_list)}")
            
            if asset_list.empty:
                print(f"   ❌ {asset_type_str} 资产列表为空")
                continue
            
            # 添加内容项
            from core.services.smart_recommendation_engine import ContentItem
            
            count = 0
            for idx, asset in asset_list.iterrows():
                asset_code = asset.get('code', '')
                asset_name = asset.get('name', '')
                
                if not asset_code:
                    continue
                
                sector = asset.get('sector') or '未知'
                industry = asset.get('industry') or '未知'
                market = asset.get('market') or '未知'
                
                # 确定推荐类型
                if asset_type_str.startswith('stock'):
                    recommendation_type = RecommendationType.STOCK
                elif asset_type_str == 'crypto':
                    recommendation_type = RecommendationType.CRYPTO
                elif asset_type_str == 'fund':
                    recommendation_type = RecommendationType.FUND
                elif asset_type_str == 'bond':
                    recommendation_type = RecommendationType.BOND
                else:
                    recommendation_type = RecommendationType.STOCK
                
                tags = [str(v) for v in [sector, industry, market] if v and v != '未知']
                categories = [str(v) for v in [market, sector] if v and v != '未知']
                keywords = [str(v) for v in [asset_name, asset_code, industry] if v and v != '未知']
                
                item = ContentItem(
                    item_id=f"{asset_type_str}_{asset_code}",
                    item_type=recommendation_type,
                    title=f"{asset_name} ({asset_code})" if asset_name else asset_code,
                    description=f"行业: {industry} | 板块: {sector}",
                    tags=tags,
                    categories=categories,
                    keywords=keywords,
                    metadata={
                        'code': asset_code,
                        'name': asset_name,
                        'market': market,
                        'sector': sector,
                        'industry': industry,
                        'asset_type': asset_type_str
                    }
                )
                
                engine.add_content_item(item)
                count += 1
                
                if count >= 10:
                    break
            
            print(f"   添加了 {count} 个 {asset_type_str} 内容项")
            print(f"   内容项总数: {len(engine.content_items)}")
        
        # 3. 测试获取不同资产类型的推荐
        print("\n3. 测试获取不同资产类型的推荐...")
        
        for asset_type in asset_types:
            asset_type_str = asset_type.value
            print(f"\n   测试资产类型: {asset_type_str}")
            
            # 确定推荐类型
            if asset_type_str.startswith('stock'):
                recommendation_type = RecommendationType.STOCK
            elif asset_type_str == 'crypto':
                recommendation_type = RecommendationType.CRYPTO
            elif asset_type_str == 'fund':
                recommendation_type = RecommendationType.FUND
            elif asset_type_str == 'bond':
                recommendation_type = RecommendationType.BOND
            else:
                recommendation_type = RecommendationType.STOCK
            
            # 获取推荐
            recommendations = await engine.get_recommendations(
                user_id='test_user',
                recommendation_type=recommendation_type,
                count=5
            )
            
            print(f"   推荐数量: {len(recommendations)}")
            
            if recommendations:
                print(f"   前 3 个推荐:")
                for i, rec in enumerate(recommendations[:3]):
                    print(f"     {i+1}. {rec.title} (分数: {rec.score:.2f})")
            else:
                print(f"   ❌ 推荐为空")
        
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        return 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(test_asset_type_switching()))
