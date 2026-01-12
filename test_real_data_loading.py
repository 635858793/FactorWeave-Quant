#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试智能推荐面板的真实数据加载
"""

import sys
import asyncio

async def test_real_data_loading():
    """测试真实数据加载"""
    try:
        from core.services.smart_recommendation_engine import SmartRecommendationEngine, RecommendationType
        from core.plugin_types import AssetType
        
        print("测试智能推荐面板的真实数据加载...")
        print("=" * 60)
        
        # 1. 创建推荐引擎
        print("\n1. 创建推荐引擎...")
        engine = SmartRecommendationEngine()
        print("✅ 推荐引擎创建成功")
        
        # 2. 测试加载策略数据
        print("\n2. 测试加载策略数据...")
        try:
            from core.containers import get_service_container
            container = get_service_container()
            strategy_service = container.get('StrategyService')
            
            if strategy_service:
                # 获取所有策略配置
                strategy_configs = strategy_service.get_all_strategy_configs()
                print(f"   策略配置数量: {len(strategy_configs)}")
                
                if strategy_configs:
                    print(f"   前 3 个策略配置:")
                    for i, config in enumerate(strategy_configs[:3]):
                        name = config.metadata.get('name', config.strategy_id)
                        print(f"     {i+1}. {name} ({config.strategy_id})")
                
                # 获取所有策略模板
                strategy_templates = strategy_service.get_all_templates()
                print(f"   策略模板数量: {len(strategy_templates)}")
                
                if strategy_templates:
                    print(f"   前 3 个策略模板:")
                    for i, template in enumerate(strategy_templates[:3]):
                        print(f"     {i+1}. {template.name} ({template.template_id})")
                
                # 添加策略内容项
                from core.services.smart_recommendation_engine import ContentItem
                count = 0
                for config in strategy_configs:
                    name = config.metadata.get('name', config.strategy_id)
                    description = config.metadata.get('description', f"策略类型: {config.plugin_type}")
                    tags = config.tags or [config.plugin_type]
                    categories = config.metadata.get('categories', ['交易策略'])
                    keywords = [name, config.strategy_id, config.plugin_type]
                    
                    item = ContentItem(
                        item_id=f"strategy_config_{config.strategy_id}",
                        item_type=RecommendationType.STRATEGY,
                        title=name,
                        description=description,
                        tags=tags,
                        categories=categories,
                        keywords=keywords,
                        metadata={
                            'strategy_id': config.strategy_id,
                            'plugin_type': config.plugin_type,
                            'enabled': config.enabled,
                            'source': 'strategy_config'
                        }
                    )
                    
                    engine.add_content_item(item)
                    count += 1
                
                for template in strategy_templates:
                    name = template.name
                    description = template.description
                    tags = template.tags or [template.category]
                    categories = [template.category]
                    keywords = [name, template.template_id, template.plugin_type]
                    
                    item = ContentItem(
                        item_id=f"strategy_template_{template.template_id}",
                        item_type=RecommendationType.STRATEGY,
                        title=name,
                        description=description,
                        tags=tags,
                        categories=categories,
                        keywords=keywords,
                        metadata={
                            'template_id': template.template_id,
                            'plugin_type': template.plugin_type,
                            'category': template.category,
                            'is_builtin': template.is_builtin,
                            'source': 'strategy_template'
                        }
                    )
                    
                    engine.add_content_item(item)
                    count += 1
                
                print(f"   添加了 {count} 个策略内容项")
            else:
                print("   ❌ 无法获取StrategyService")
        except Exception as e:
            print(f"   ❌ 加载策略数据失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. 测试加载指标数据
        print("\n3. 测试加载指标数据...")
        try:
            indicator_service = container.get('EnhancedIndicatorService')
            
            if indicator_service:
                # 获取所有指标
                indicators = indicator_service.get_all_indicators()
                print(f"   指标数量: {len(indicators)}")
                
                if indicators:
                    print(f"   前 3 个指标:")
                    for i, indicator in enumerate(indicators[:3]):
                        name = indicator.get('display_name', indicator.get('name', 'Unknown'))
                        print(f"     {i+1}. {name}")
                
                # 添加指标内容项
                count = 0
                for indicator in indicators:
                    name = indicator.get('display_name', indicator.get('name', 'Unknown'))
                    description = indicator.get('description', '技术指标')
                    tags = indicator.get('tags', [])
                    categories = indicator.get('categories', ['技术指标'])
                    keywords = [name, indicator.get('name', '')]
                    
                    item = ContentItem(
                        item_id=f"indicator_{indicator['name']}",
                        item_type=RecommendationType.INDICATOR,
                        title=name,
                        description=description,
                        tags=tags,
                        categories=categories,
                        keywords=keywords,
                        metadata={
                            'indicator_name': indicator['name'],
                            'category': indicator.get('category', ''),
                            'is_builtin': indicator.get('is_builtin', False),
                            'source': 'indicator_service'
                        }
                    )
                    
                    engine.add_content_item(item)
                    count += 1
                
                print(f"   添加了 {count} 个指标内容项")
            else:
                print("   ❌ 无法获取EnhancedIndicatorService")
        except Exception as e:
            print(f"   ❌ 加载指标数据失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 4. 测试获取推荐
        print("\n4. 测试获取推荐...")
        print(f"   内容项总数: {len(engine.content_items)}")
        
        # 获取策略推荐
        strategy_recommendations = await engine.get_recommendations(
            user_id='test_user',
            recommendation_type=RecommendationType.STRATEGY,
            count=5
        )
        print(f"   策略推荐数量: {len(strategy_recommendations)}")
        
        if strategy_recommendations:
            print(f"   前 3 个策略推荐:")
            for i, rec in enumerate(strategy_recommendations[:3]):
                print(f"     {i+1}. {rec.title} (分数: {rec.score:.2f})")
        
        # 获取指标推荐
        indicator_recommendations = await engine.get_recommendations(
            user_id='test_user',
            recommendation_type=RecommendationType.INDICATOR,
            count=5
        )
        print(f"   指标推荐数量: {len(indicator_recommendations)}")
        
        if indicator_recommendations:
            print(f"   前 3 个指标推荐:")
            for i, rec in enumerate(indicator_recommendations[:3]):
                print(f"     {i+1}. {rec.title} (分数: {rec.score:.2f})")
        
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        return 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(test_real_data_loading()))
