#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接检查服务注册状态
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置环境变量禁用日志
os.environ['LOGURU_LEVEL'] = 'CRITICAL'

def main():
    print("开始检查服务注册...")
    
    try:
        from core.containers import get_service_container
        from core.services.service_bootstrap import ServiceBootstrap
        from core.services.recommendation_model_trainer import RecommendationModelTrainer
        from core.services.recommendation_explanation_generator import RecommendationExplanationGenerator
        from core.services.smart_recommendation_engine import SmartRecommendationEngine
        from core.ai.continuous_learning_manager import ContinuousLearningManager
        
        print("正在引导服务...")
        bootstrap = ServiceBootstrap()
        bootstrap.bootstrap()
        print("服务引导完成")
        
        # 获取服务容器
        container = get_service_container()
        
        # 检查服务注册状态
        print("\n检查服务注册状态:")
        
        services = [
            ('SmartRecommendationEngine', SmartRecommendationEngine),
            ('RecommendationModelTrainer', RecommendationModelTrainer),
            ('RecommendationExplanationGenerator', RecommendationExplanationGenerator),
            ('ContinuousLearningManager', ContinuousLearningManager)
        ]
        
        all_registered = True
        for service_name, service_type in services:
            is_registered = container.is_registered(service_type)
            status = "[OK]" if is_registered else "[FAIL]"
            print(f"{status} {service_name}: {'已注册' if is_registered else '未注册'}")
            if not is_registered:
                all_registered = False
        
        if not all_registered:
            print("\n部分服务未注册，尝试解析服务...")
        
        # 尝试解析服务
        print("\n尝试解析服务:")
        
        try:
            engine = container.resolve(SmartRecommendationEngine)
            print("[OK] SmartRecommendationEngine 解析成功")
            print(f"     explanation_generator: {engine.explanation_generator is not None}")
        except Exception as e:
            print(f"[FAIL] SmartRecommendationEngine 解析失败: {e}")
        
        try:
            trainer = container.resolve(RecommendationModelTrainer)
            print("[OK] RecommendationModelTrainer 解析成功")
            print(f"     recommendation_engine: {trainer.recommendation_engine is not None}")
            print(f"     continuous_learning_manager: {trainer.continuous_learning_manager is not None}")
        except Exception as e:
            print(f"[FAIL] RecommendationModelTrainer 解析失败: {e}")
        
        try:
            generator = container.resolve(RecommendationExplanationGenerator)
            print("[OK] RecommendationExplanationGenerator 解析成功")
        except Exception as e:
            print(f"[FAIL] RecommendationExplanationGenerator 解析失败: {e}")
        
        try:
            clm = container.resolve(ContinuousLearningManager)
            print("[OK] ContinuousLearningManager 解析成功")
        except Exception as e:
            print(f"[FAIL] ContinuousLearningManager 解析失败: {e}")
        
        print("\n检查完成!")
        return 0 if all_registered else 1
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())