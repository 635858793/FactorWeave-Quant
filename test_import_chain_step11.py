#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入链 - 检查循环导入
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

logger.info("开始测试导入链...")

# 逐步导入模块
logger.info("1. 导入 core.events...")
try:
    from core.events import EventBus, get_event_bus, BaseEvent
    logger.info("✓ core.events 导入完成")
except Exception as e:
    logger.error(f"✗ core.events 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("2. 导入 core.containers...")
try:
    from core.containers import ServiceContainer, get_service_container
    logger.info("✓ core.containers 导入完成")
except Exception as e:
    logger.error(f"✗ core.containers 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("3. 导入 core.containers.service_registry...")
try:
    from core.containers.service_registry import ServiceScope
    logger.info("✓ core.containers.service_registry 导入完成")
except Exception as e:
    logger.error(f"✗ core.containers.service_registry 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("4. 导入 core.coordinators.base_coordinator...")
try:
    from core.coordinators.base_coordinator import BaseCoordinator
    logger.info("✓ core.coordinators.base_coordinator 导入完成")
except Exception as e:
    logger.error(f"✗ core.coordinators.base_coordinator 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("导入链测试完成")
