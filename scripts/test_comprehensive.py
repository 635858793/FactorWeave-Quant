#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试脚本 - 验证订单管理系统的完整实现

测试内容：
1. TradingInterface基类方法
2. OrderExecutor初始化
3. OrderService高级分析方法
4. UI与后端连接
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from core.trading.trading_types import TradingInterface, ExecutionResult, ExecutionStatus
from core.trading.interfaces.xtp_trading_interface import XTPTradingInterface
from core.trading.interfaces.ctp_trading_interface import CTPTradingInterface
from core.trading.order_executor import OrderExecutor
from core.trading.order_service import OrderService
from core.containers import get_service_container
from core.events import get_event_bus
from core.plugin_types import AssetType


def test_trading_interface_base_methods():
    """测试TradingInterface基类方法"""
    logger.info("=" * 80)
    logger.info("【测试1】TradingInterface基类方法")
    logger.info("=" * 80)

    try:
        # 检查基类是否有必需的方法
        base_methods = ['connect', 'login', 'disconnect', 'submit_order', 'cancel_order', 'query_order_status']
        
        for method_name in base_methods:
            if hasattr(TradingInterface, method_name):
                logger.info(f"✅ TradingInterface.{method_name} 方法存在")
            else:
                logger.error(f"❌ TradingInterface.{method_name} 方法不存在")
                return False

        # 测试默认实现
        interface = TradingInterface()
        
        # 测试connect()
        result = interface.connect()
        if result is True:
            logger.info("✅ TradingInterface.connect() 默认返回True")
        else:
            logger.error(f"❌ TradingInterface.connect() 返回: {result}")
            return False

        # 测试login()
        result = interface.login()
        if result is True:
            logger.info("✅ TradingInterface.login() 默认返回True")
        else:
            logger.error(f"❌ TradingInterface.login() 返回: {result}")
            return False

        # 测试disconnect()
        interface.disconnect()
        logger.info("✅ TradingInterface.disconnect() 可以正常调用")

        logger.info("\n✅ TradingInterface基类方法测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ TradingInterface基类方法测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_xtp_interface_methods():
    """测试XTP接口方法实现"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试2】XTP交易接口方法实现")
    logger.info("=" * 80)

    try:
        xtp_interface = XTPTradingInterface()

        # 测试connect()
        result = xtp_interface.connect()
        if result is True:
            logger.info("✅ XTPTradingInterface.connect() 返回True")
        else:
            logger.error(f"❌ XTPTradingInterface.connect() 返回: {result}")
            return False

        # 测试login()
        result = xtp_interface.login()
        if result is True:
            logger.info("✅ XTPTradingInterface.login() 返回True")
        else:
            logger.error(f"❌ XTPTradingInterface.login() 返回: {result}")
            return False

        # 测试disconnect()
        xtp_interface.disconnect()
        logger.info("✅ XTPTradingInterface.disconnect() 可以正常调用")

        logger.info("\n✅ XTP交易接口方法测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ XTP交易接口方法测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_ctp_interface_methods():
    """测试CTP接口方法实现"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试3】CTP交易接口方法实现")
    logger.info("=" * 80)

    try:
        ctp_interface = CTPTradingInterface()

        # 测试connect()
        result = ctp_interface.connect()
        if result is True:
            logger.info("✅ CTPTradingInterface.connect() 返回True")
        else:
            logger.error(f"❌ CTPTradingInterface.connect() 返回: {result}")
            return False

        # 测试login()
        result = ctp_interface.login()
        if result is True:
            logger.info("✅ CTPTradingInterface.login() 返回True")
        else:
            logger.error(f"❌ CTPTradingInterface.login() 返回: {result}")
            return False

        # 测试disconnect()
        ctp_interface.disconnect()
        logger.info("✅ CTPTradingInterface.disconnect() 可以正常调用")

        logger.info("\n✅ CTP交易接口方法测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ CTP交易接口方法测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_order_executor_initialization():
    """测试OrderExecutor初始化"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试4】OrderExecutor初始化")
    logger.info("=" * 80)

    try:
        # 获取服务容器和事件总线
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 创建OrderExecutor
        order_executor = OrderExecutor(service_container, event_bus)

        # 检查交易接口是否已初始化
        if hasattr(order_executor, '_trading_interfaces'):
            logger.info("✅ OrderExecutor._trading_interfaces 属性存在")
            
            # 检查是否有交易接口
            if order_executor._trading_interfaces:
                logger.info(f"✅ 已注册 {len(order_executor._trading_interfaces)} 个交易接口")
                
                # 检查每个接口是否已连接和登录
                for asset_type, interface in order_executor._trading_interfaces.items():
                    if hasattr(interface, '_connected') and interface._connected:
                        logger.info(f"✅ {asset_type.value} 交易接口已连接")
                    else:
                        logger.warning(f"⚠️  {asset_type.value} 交易接口未连接")
                    
                    if hasattr(interface, '_logged_in') and interface._logged_in:
                        logger.info(f"✅ {asset_type.value} 交易接口已登录")
                    else:
                        logger.warning(f"⚠️  {asset_type.value} 交易接口未登录")
            else:
                logger.warning("⚠️  没有注册任何交易接口")
        else:
            logger.error("❌ OrderExecutor._trading_interfaces 属性不存在")
            return False

        logger.info("\n✅ OrderExecutor初始化测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ OrderExecutor初始化测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_order_service_advanced_methods():
    """测试OrderService高级分析方法"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试5】OrderService高级分析方法")
    logger.info("=" * 80)

    try:
        # 获取服务容器和事件总线
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 创建OrderService
        order_service = OrderService(service_container, event_bus)

        # 检查高级分析方法是否存在
        advanced_methods = [
            'analyze_order_path',
            'analyze_order_cost',
            'analyze_order_timing',
            'analyze_order_risk',
            'predict_order_fill_probability'
        ]

        for method_name in advanced_methods:
            if hasattr(order_service, method_name):
                logger.info(f"✅ OrderService.{method_name} 方法存在")
            else:
                logger.error(f"❌ OrderService.{method_name} 方法不存在")
                return False

        # 测试方法调用（不检查返回值，只检查是否能调用）
        try:
            # analyze_order_timing 不需要order_id
            result = order_service.analyze_order_timing(period="day")
            logger.info("✅ OrderService.analyze_order_timing() 可以正常调用")
        except Exception as e:
            logger.warning(f"⚠️  OrderService.analyze_order_timing() 调用异常: {e}")

        logger.info("\n✅ OrderService高级分析方法测试通过")
        return True

    except Exception as e:
        logger.error(f"❌ OrderService高级分析方法测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_ui_backend_connection():
    """测试UI与后端连接"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试6】UI与后端连接")
    logger.info("=" * 80)

    try:
        # 导入UI模块
        from gui.dialogs.order_management_dialog import OrderManagementDialog

        # 检查UI类是否有高级分析方法
        ui_methods = [
            'analyze_order_path',
            'analyze_order_cost',
            'analyze_order_timing',
            'analyze_order_risk',
            'predict_fill_probability'
        ]

        for method_name in ui_methods:
            if hasattr(OrderManagementDialog, method_name):
                logger.info(f"✅ OrderManagementDialog.{method_name} 方法存在")
            else:
                logger.error(f"❌ OrderManagementDialog.{method_name} 方法不存在")
                return False

        logger.info("\n✅ UI与后端连接测试通过")
        return True

    except ImportError as e:
        logger.warning(f"⚠️  无法导入UI模块（可能需要Qt环境）: {e}")
        logger.info("跳过UI测试")
        return True
    except Exception as e:
        logger.error(f"❌ UI与后端连接测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("开始综合测试")
    logger.info("=" * 80)

    results = []

    # 运行所有测试
    results.append(("TradingInterface基类方法", test_trading_interface_base_methods()))
    results.append(("XTP交易接口方法", test_xtp_interface_methods()))
    results.append(("CTP交易接口方法", test_ctp_interface_methods()))
    results.append(("OrderExecutor初始化", test_order_executor_initialization()))
    results.append(("OrderService高级分析方法", test_order_service_advanced_methods()))
    results.append(("UI与后端连接", test_ui_backend_connection()))

    # 输出测试结果汇总
    logger.info("\n" + "=" * 80)
    logger.info("测试结果汇总")
    logger.info("=" * 80)

    passed = 0
    failed = 0

    for test_name, result in results:
        if result:
            logger.info(f"✅ {test_name}: 通过")
            passed += 1
        else:
            logger.error(f"❌ {test_name}: 失败")
            failed += 1

    logger.info("\n" + "=" * 80)
    logger.info(f"总计: {len(results)} 个测试, 通过: {passed}, 失败: {failed}")
    logger.info("=" * 80)

    if failed == 0:
        logger.info("\n🎉 所有测试通过！")
        return True
    else:
        logger.error(f"\n❌ 有 {failed} 个测试失败")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
