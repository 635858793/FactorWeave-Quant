"""
模型训练和优化模块
"""

# 延迟导入以避免循环依赖和导入问题
def __getattr__(name):
    if name == 'build_deep_learning_model':
        from .deep_learning import build_deep_learning_model
        return build_deep_learning_model
    elif name == 'evaluate_ml_model':
        from .model_evaluation import evaluate_ml_model
        return evaluate_ml_model
    elif name == 'TENSORFLOW_AVAILABLE':
        from .deep_learning import TENSORFLOW_AVAILABLE
        return TENSORFLOW_AVAILABLE
    elif name in dir():
        return globals()[name]
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
