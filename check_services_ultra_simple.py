import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 完全禁用日志
os.environ['LOGURU_LEVEL'] = 'CRITICAL'
os.environ['LOGURU_DISABLE'] = '1'

import logging
logging.basicConfig(level=logging.CRITICAL, force=True)

try:
    from core.containers import get_service_container
    from core.services.service_bootstrap import ServiceBootstrap
    from core.services.recommendation_model_trainer import RecommendationModelTrainer
    from core.services.recommendation_explanation_generator import RecommendationExplanationGenerator
    from core.services.smart_recommendation_engine import SmartRecommendationEngine
    from core.ai.continuous_learning_manager import ContinuousLearningManager
    
    bootstrap = ServiceBootstrap()
    bootstrap.bootstrap()
    
    container = get_service_container()
    
    results = {
        'SmartRecommendationEngine': container.is_registered(SmartRecommendationEngine),
        'RecommendationModelTrainer': container.is_registered(RecommendationModelTrainer),
        'RecommendationExplanationGenerator': container.is_registered(RecommendationExplanationGenerator),
        'ContinuousLearningManager': container.is_registered(ContinuousLearningManager)
    }
    
    for service_name, is_registered in results.items():
        print(f"{service_name}: {is_registered}")
    
    sys.exit(0 if all(results.values()) else 1)
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)