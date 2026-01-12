#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试完整的推荐流程
"""

import sys
import asyncio

async def test_full_recommendation_flow():
    """测试完整的推荐流程"""
    try:
        from core.services.smart_recommendation_engine import SmartRecommendationEngine, RecommendationType
        from core.plugin_types import AssetType
        
        print("测试完整的推荐流程...")
        print("=" * 60)
        
        # 1. 创建推荐引擎
        print("\n1. 创建推荐引擎...")
        engine = SmartRecommendationEngine()
        print("✅ 推荐引擎创建成功")
        
        # 2. 检查内容项数量
        print(f"\n2. 检查内容项数量...")
        print(f"   内容项总数: {len(engine.content_items)}")
        
        # 3. 加载股票数据
        print("\n3. 加载股票数据...")
        from core.services.unified_data_manager import UnifiedDataManager
        data_manager = UnifiedDataManager()
        
        stock_list = data_manager.get_asset_list('stock_a')
        print(f"   股票列表数量: {len(stock_list)}")
        
        if stock_list.empty:
            print("   ❌ 股票列表为空")
            return 1
        
        # 4. 添加内容项
        print("\n4. 添加内容项...")
        from core.services.smart_recommendation_engine import ContentItem
        
        count = 0
        for idx, stock in stock_list.iterrows():
            stock_code = stock.get('code', '')
            stock_name = stock.get('name', '')
            
            if not stock_code:
                continue
            
            sector = stock.get('sector') or '未知'
            industry = stock.get('industry') or '未知'
            market = stock.get('market') or '未知'
            
            tags = [str(v) for v in [sector, industry, market] if v and v != '未知']
            categories = [str(v) for v in [market, sector] if v and v != '未知']
            keywords = [str(v) for v in [stock_name, stock_code, industry] if v and v != '未知']
            
            item = ContentItem(
                item_id=f"stock_{stock_code}",
                item_type=RecommendationType.STOCK,
                title=f"{stock_name} ({stock_code})" if stock_name else stock_code,
                description=f"行业: {industry} | 板块: {sector}",
                tags=tags,
                categories=categories,
                keywords=keywords,
                metadata={
                    'code': stock_code,
                    'name': stock_name,
                    'market': market,
                    'sector': sector,
                    'industry': industry
                }
            )
            
            engine.add_content_item(item)
            count += 1
            
            if count >= 100:
                break
        
        print(f"   添加了 {count} 个内容项")
        print(f"   内容项总数: {len(engine.content_items)}")
        
        # 5. 获取推荐
        print("\n5. 获取推荐...")
        recommendations = await engine.get_recommendations(
            user_id='test_user',
            recommendation_type=RecommendationType.STOCK,
            count=10
        )
        
        print(f"   推荐数量: {len(recommendations)}")
        
        if recommendations:
            print("\n   前 5 个推荐:")
            for i, rec in enumerate(recommendations[:5]):
                print(f"     {i+1}. {rec.title} (分数: {rec.score:.2f})")
        else:
            print("   ❌ 推荐为空")
        
        print("\n" + "=" * 60)
        if len(recommendations) > 0:
            print("✅ 测试完成！推荐流程正常。")
            return 0
        else:
            print("❌ 测试失败！推荐为空。")
            return 1
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(test_full_recommendation_flow()))
