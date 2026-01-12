#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试智能推荐面板的模型训练按钮和推荐理由功能
"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_service_registration():
    """测试服务注册"""
    print("=" * 60)
    print("测试 1: 服务注册")
    print("=" * 60)
    
    try:
        from core.containers import get_service_container
        from core.services.service_bootstrap import ServiceBootstrap
        from core.services.recommendation_model_trainer import RecommendationModelTrainer
        from core.services.recommendation_explanation_generator import RecommendationExplanationGenerator
        from core.services.smart_recommendation_engine import SmartRecommendationEngine
        from core.ai.continuous_learning_manager import ContinuousLearningManager
        
        # 引导服务
        bootstrap = ServiceBootstrap()
        bootstrap.bootstrap()
        
        # 获取服务容器
        container = get_service_container()
        
        # 检查服务注册状态
        services = [
            ('SmartRecommendationEngine', SmartRecommendationEngine),
            ('RecommendationModelTrainer', RecommendationModelTrainer),
            ('RecommendationExplanationGenerator', RecommendationExplanationGenerator),
            ('ContinuousLearningManager', ContinuousLearningManager)
        ]
        
        all_registered = True
        for service_name, service_type in services:
            is_registered = container.is_registered(service_type)
            status = "[OK] 已注册" if is_registered else "[FAIL] 未注册"
            print(f"{service_name}: {status}")
            if not is_registered:
                all_registered = False
        
        return all_registered
    except Exception as e:
        print(f"测试服务注册失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_trainer_initialization():
    """测试模型训练器初始化"""
    print("=" * 60)
    print("测试 2: 模型训练器初始化")
    print("=" * 60)
    
    try:
        from core.containers import get_service_container
        from core.services.recommendation_model_trainer import RecommendationModelTrainer
        
        container = get_service_container()
        
        if not container.is_registered(RecommendationModelTrainer):
            print("[FAIL] RecommendationModelTrainer 未注册")
            return False
        
        model_trainer = container.resolve(RecommendationModelTrainer)
        
        # 检查模型训练器是否正确初始化
        checks = [
            ('recommendation_engine', hasattr(model_trainer, 'recommendation_engine')),
            ('continuous_learning_manager', hasattr(model_trainer, 'continuous_learning_manager')),
            ('models', hasattr(model_trainer, 'models')),
            ('model_configs', hasattr(model_trainer, 'model_configs')),
            ('training_jobs', hasattr(model_trainer, 'training_jobs')),
            ('train', hasattr(model_trainer, 'train'))
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            status = "[OK]" if check_result else "[FAIL]"
            print(f"{status} {check_name}: {'存在' if check_result else '不存在'}")
            if not check_result:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"测试模型训练器初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_explanation_generator_initialization():
    """测试推荐理由生成器初始化"""
    print("=" * 60)
    print("测试 3: 推荐理由生成器初始化")
    print("=" * 60)
    
    try:
        from core.containers import get_service_container
        from core.services.recommendation_explanation_generator import RecommendationExplanationGenerator
        
        container = get_service_container()
        
        if not container.is_registered(RecommendationExplanationGenerator):
            print("[FAIL] RecommendationExplanationGenerator 未注册")
            return False
        
        explanation_generator = container.resolve(RecommendationExplanationGenerator)
        
        # 检查推荐理由生成器是否正确初始化
        checks = [
            ('_explanation_templates', hasattr(explanation_generator, '_explanation_templates')),
            ('generate_explanation', hasattr(explanation_generator, 'generate_explanation'))
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            status = "[OK]" if check_result else "[FAIL]"
            print(f"{status} {check_name}: {'存在' if check_result else '不存在'}")
            if not check_result:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"测试推荐理由生成器初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_recommendation_engine_integration():
    """测试推荐引擎集成"""
    print("=" * 60)
    print("测试 4: 推荐引擎集成")
    print("=" * 60)
    
    try:
        from core.containers import get_service_container
        from core.services.smart_recommendation_engine import SmartRecommendationEngine
        from core.services.recommendation_explanation_generator import RecommendationExplanationGenerator
        
        container = get_service_container()
        
        if not container.is_registered(SmartRecommendationEngine):
            print("[FAIL] SmartRecommendationEngine 未注册")
            return False
        
        if not container.is_registered(RecommendationExplanationGenerator):
            print("[FAIL] RecommendationExplanationGenerator 未注册")
            return False
        
        recommendation_engine = container.resolve(SmartRecommendationEngine)
        explanation_generator = container.resolve(RecommendationExplanationGenerator)
        
        # 检查推荐引擎是否正确设置了推荐理由生成器
        if recommendation_engine.explanation_generator is None:
            print("[FAIL] 推荐引擎的 explanation_generator 为 None")
            return False
        
        if recommendation_engine.explanation_generator != explanation_generator:
            print("[FAIL] 推荐引擎的 explanation_generator 不是注册的实例")
            return False
        
        print("[OK] 推荐引擎的 explanation_generator 已正确设置")
        
        # 测试推荐理由生成
        from core.services.smart_recommendation_engine import Recommendation, RecommendationReason, AssetType
        test_recommendation = Recommendation(
            user_id="test_user",
            item_id="test_item",
            item_type="stock_a",
            score=0.8,
            reason=RecommendationReason.SIMILAR_USERS,
            title="测试股票",
            description="这是一个测试股票",
            explanation="测试解释",
            confidence=0.7,
            asset_type=AssetType.STOCK_A
        )
        
        explanation = explanation_generator.generate_explanation(test_recommendation)
        print(f"[OK] 生成的推荐理由: {explanation}")
        
        return True
    except Exception as e:
        print(f"测试推荐引擎集成失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_smart_recommendation_panel_creation():
    """测试智能推荐面板创建"""
    print("=" * 60)
    print("测试 5: 智能推荐面板创建")
    print("=" * 60)
    
    try:
        from core.containers import get_service_container
        from core.services.recommendation_model_trainer import RecommendationModelTrainer
        from core.services.smart_recommendation_engine import SmartRecommendationEngine
        from gui.widgets.enhanced_ui.smart_recommendation_panel import SmartRecommendationPanel
        
        container = get_service_container()
        
        # 获取服务
        recommendation_engine = None
        model_trainer = None
        
        try:
            recommendation_engine = container.resolve(SmartRecommendationEngine)
            print("[OK] 成功获取 SmartRecommendationEngine 服务")
        except Exception as e:
            print(f"[WARN] 无法获取 SmartRecommendationEngine 服务: {e}")
        
        try:
            model_trainer = container.resolve(RecommendationModelTrainer)
            print("[OK] 成功获取 RecommendationModelTrainer 服务")
        except Exception as e:
            print(f"[WARN] 无法获取 RecommendationModelTrainer 服务: {e}")
        
        # 创建智能推荐面板
        panel = SmartRecommendationPanel(
            recommendation_engine=recommendation_engine,
            model_trainer=model_trainer
        )
        
        # 检查面板是否正确初始化
        checks = [
            ('recommendation_engine', panel.recommendation_engine is not None),
            ('model_trainer', panel.model_trainer is not None),
            ('train_model_btn', hasattr(panel, 'train_model_btn'))
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            status = "[OK]" if check_result else "[FAIL]"
            print(f"{status} {check_name}: {'已设置' if check_result else '未设置'}")
            if not check_result:
                all_passed = False
        
        # 检查模型训练按钮状态
        if hasattr(panel, 'train_model_btn'):
            is_enabled = panel.train_model_btn.isEnabled()
            print(f"[OK] 模型训练按钮状态: {'可用' if is_enabled else '不可用'}")
        
        return all_passed
    except Exception as e:
        print(f"测试智能推荐面板创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("开始测试智能推荐面板修复...")
    print("")
    
    results = []
    
    # 测试 1: 服务注册
    results.append(("服务注册", test_service_registration()))
    print("")
    
    # 测试 2: 模型训练器初始化
    results.append(("模型训练器初始化", test_model_trainer_initialization()))
    print("")
    
    # 测试 3: 推荐理由生成器初始化
    results.append(("推荐理由生成器初始化", test_explanation_generator_initialization()))
    print("")
    
    # 测试 4: 推荐引擎集成
    results.append(("推荐引擎集成", test_recommendation_engine_integration()))
    print("")
    
    # 测试 5: 智能推荐面板创建
    results.append(("智能推荐面板创建", test_smart_recommendation_panel_creation()))
    print("")
    
    # 输出测试结果摘要
    print("=" * 60)
    print("测试结果摘要")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS] 通过" if result else "[FAIL] 失败"
        print(f"{status} - {test_name}")
    
    print("")
    print(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("所有测试通过!")
        return 0
    else:
        print(f"{total - passed} 个测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())