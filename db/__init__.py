"""
数据库模型包
"""

import sys
from pathlib import Path

# 添加models目录到Python路径
models_dir = Path(__file__).parent / 'models'
if str(models_dir) not in sys.path:
    sys.path.insert(0, str(models_dir))

from llm_config_models import LLMConfigManager, get_llm_config_manager

__all__ = [
    'LLMConfigManager',
    'get_llm_config_manager',
]
