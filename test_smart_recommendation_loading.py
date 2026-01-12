#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试智能推荐面板的数据加载
"""

import sys

def test_smart_recommendation_loading():
    """测试智能推荐面板的数据加载"""
    try:
        from core.services.unified_data_manager import UnifiedDataManager
        from core.services.smart_recommendation_engine import ContentItem, RecommendationType
        
        print("测试智能推荐面板的数据加载...")
        print("=" * 60)
        
        # 初始化数据管理器
        data_manager = UnifiedDataManager()
        print("✅ UnifiedDataManager 初始化成功")
        
        # 获取股票列表
        print("\n获取股票列表...")
        stock_list = data_manager.get_asset_list('stock_a')
        
        if stock_list.empty:
            print("❌ 股票列表为空")
            return 1
        
        print(f"✅ 成功获取股票列表: {len(stock_list)} 只股票")
        
        # 创建内容项
        print("\n创建内容项...")
        content_items = []
        count = 0
        
        for idx, stock in stock_list.iterrows():
            stock_code = stock.get('code', '')
            stock_name = stock.get('name', '')
            
            if not stock_code:
                continue
            
            # 过滤None值和空字符串，确保所有值都是有效字符串
            sector = stock.get('sector') or '未知'
            industry = stock.get('industry') or '未知'
            market = stock.get('market') or '未知'
            
            # 确保tags、categories、keywords中没有None或空字符串
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
            
            content_items.append(item)
            count += 1
            
            # 限制数量避免过多
            if count >= 100:
                break
        
        print(f"✅ 成功创建 {len(content_items)} 个内容项")
        
        # 显示前 5 个内容项
        print("\n前 5 个内容项:")
        for i, item in enumerate(content_items[:5]):
            print(f"  {i+1}. {item.title}")
            print(f"     描述: {item.description}")
            print(f"     标签: {item.tags}")
        
        print("\n" + "=" * 60)
        print("✅ 测试完成！智能推荐面板应该能够正常显示数据了。")
        return 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(test_smart_recommendation_loading())
