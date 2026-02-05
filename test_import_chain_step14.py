#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导入链 - 检查 core.trading.interfaces.ctp_trading_interface 的导入链
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

logger.info("开始测试导入链...")

# 逐步导入模块
logger.info("1. 导入 core.trading.order_models...")
try:
    from core.trading.order_models import Order, OrderStatus
    logger.info("✓ core.trading.order_models 导入完成")
except Exception as e:
    logger.error(f"✗ core.trading.order_models 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("2. 导入 core.trading.trading_types...")
try:
    from core.trading.trading_types import ExecutionResult, ExecutionStatus, TradingInterface
    logger.info("✓ core.trading.trading_types 导入完成")
except Exception as e:
    logger.error(f"✗ core.trading.trading_types 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("3. 导入 core.trading.interfaces.ctp_config...")
try:
    from core.trading.interfaces.ctp_config import CTPConfig, get_ctp_config
    logger.info("✓ core.trading.interfaces.ctp_config 导入完成")
except Exception as e:
    logger.error(f"✗ core.trading.interfaces.ctp_config 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("4. 导入 core.events...")
try:
    from core.events import EventBus, EVENT_BUS_AVAILABLE
    logger.info("✓ core.events 导入完成")
except Exception as e:
    logger.error(f"✗ core.events 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("5. 导入 core.trading.interfaces.ctp_trading_interface...")
try:
    import core.trading.interfaces.ctp_trading_interface
    logger.info("✓ core.trading.interfaces.ctp_trading_interface 导入完成")
except Exception as e:
    logger.error(f"✗ core.trading.interfaces.ctp_trading_interface 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger.info("导入链测试完成")
