#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最简单的服务注册检查
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 禁用所有日志
import logging
logging.disable(logging.CRITICAL)

# 禁用 loguru
class NullHandler:
    def write(self, message):
        pass
    def flush(self):
        pass

sys.stderr = NullHandler()
sys.stdout = NullHandler()

def main():
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
        results = {
            'SmartRecommendationEngine': container.is_registered(SmartRecommendationEngine),
            'RecommendationModelTrainer': container.is_registered(RecommendationModelTrainer),
            'RecommendationExplanationGenerator': container.is_registered(RecommendationExplanationGenerator),
            'ContinuousLearningManager': container.is_registered(ContinuousLearningManager)
        }
        
        # 输出结果
        for service_name, is_registered in results.items():
            print(f"{service_name}: {is_registered}")
        
        return 0 if all(results.values()) else 1
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())