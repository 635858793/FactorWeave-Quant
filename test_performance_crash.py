#!/usr/bin/env python3
"""
测试性能监控中心崩溃问题
模拟打开性能监控中心的过程，定位崩溃原因
"""

import sys
import os
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")
logger.add("logs/test_performance_crash.log", rotation="10 MB", retention="7 days", level="DEBUG")

def test_performance_widget_creation():
    """测试性能监控窗口创建"""
    logger.info("=" * 80)
    logger.info("测试性能监控窗口创建")
    logger.info("=" * 80)

    try:
        # 1. 导入必要的模块
        logger.info("1. 导入必要的模块...")
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.modern_performance_widget import show_modern_performance_monitor

        # 2. 创建QApplication
        logger.info("2. 创建QApplication...")
        app = QApplication(sys.argv)
        logger.info("✓ QApplication创建成功")

        # 3. 尝试创建性能监控窗口
        logger.info("3. 创建性能监控窗口...")
        try:
            performance_widget = show_modern_performance_monitor()
            logger.info("✓ 性能监控窗口创建成功")
        except Exception as e:
            logger.error(f"✗ 性能监控窗口创建失败: {e}")
            logger.error(traceback.format_exc())
            return False

        # 4. 检查窗口是否正常
        if performance_widget is None:
            logger.error("✗ 性能监控窗口为None")
            return False

        logger.info(f"✓ 性能监控窗口类型: {type(performance_widget).__name__}")
        logger.info(f"✓ 窗口标题: {performance_widget.windowTitle()}")
        logger.info(f"✓ 窗口大小: {performance_widget.width()}x{performance_widget.height()}")

        # 5. 检查标签页
        logger.info("5. 检查标签页...")
        if hasattr(performance_widget, 'tab_widget'):
            tab_count = performance_widget.tab_widget.count()
            logger.info(f"✓ 标签页数量: {tab_count}")
            for i in range(tab_count):
                tab_name = performance_widget.tab_widget.tabText(i)
                logger.info(f"  - 标签页 {i}: {tab_name}")
        else:
            logger.warning("✗ 窗口没有tab_widget属性")

        # 6. 检查定时器
        logger.info("6. 检查定时器...")
        timers = []
        if hasattr(performance_widget, 'refresh_timer'):
            timers.append(('refresh_timer', performance_widget.refresh_timer.isActive(), performance_widget.refresh_timer.interval()))
        if hasattr(performance_widget, 'drag_detect_timer'):
            timers.append(('drag_detect_timer', performance_widget.drag_detect_timer.isActive(), performance_widget.drag_detect_timer.interval()))
        if hasattr(performance_widget, '_cleanup_timer'):
            timers.append(('_cleanup_timer', performance_widget._cleanup_timer.isActive(), performance_widget._cleanup_timer.interval()))

        for name, is_active, interval in timers:
            status = "运行中" if is_active else "已停止"
            logger.info(f"  - {name}: {status}, 间隔: {interval}ms")

        # 7. 检查系统监控标签页
        logger.info("7. 检查系统监控标签页...")
        if hasattr(performance_widget, 'system_tab'):
            system_tab = performance_widget.system_tab
            logger.info(f"✓ 系统监控标签页类型: {type(system_tab).__name__}")

            # 检查定时器
            if hasattr(system_tab, 'monitoring_timer'):
                is_active = system_tab.monitoring_timer.isActive()
                interval = system_tab.monitoring_timer.interval()
                logger.info(f"  - monitoring_timer: {'运行中' if is_active else '已停止'}, 间隔: {interval}ms")

            # 检查线程池
            if hasattr(system_tab, 'executor'):
                logger.info(f"  - executor: {system_tab.executor}")
                logger.info(f"  - executor._max_workers: {system_tab.executor._max_workers}")
        else:
            logger.warning("✗ 窗口没有system_tab属性")

        # 8. 检查算法优化标签页
        logger.info("8. 检查算法优化标签页...")
        if hasattr(performance_widget, 'algorithm_optimization_tab'):
            algo_tab = performance_widget.algorithm_optimization_tab
            logger.info(f"✓ 算法优化标签页类型: {type(algo_tab).__name__}")

            # 检查定时器
            if hasattr(algo_tab, 'jit_monitoring_timer'):
                is_active = algo_tab.jit_monitoring_timer.isActive()
                interval = algo_tab.jit_monitoring_timer.interval()
                logger.info(f"  - jit_monitoring_timer: {'运行中' if is_active else '已停止'}, 间隔: {interval}ms")

            # 检查线程池
            if hasattr(algo_tab, 'executor'):
                logger.info(f"  - executor: {algo_tab.executor}")
                logger.info(f"  - executor._max_workers: {algo_tab.executor._max_workers}")
        else:
            logger.warning("✗ 窗口没有algorithm_optimization_tab属性")

        # 9. 测试窗口显示（不进入事件循环）
        logger.info("9. 测试窗口显示...")
        try:
            performance_widget.show()
            logger.info("✓ 窗口显示成功")

            # 强制刷新UI
            app.processEvents()
            logger.info("✓ UI刷新成功")

            # 等待一段时间，观察是否有崩溃
            logger.info("10. 等待3秒，观察是否有崩溃...")
            import time
            time.sleep(3)

            logger.info("✓ 3秒等待完成，没有崩溃")

        except Exception as e:
            logger.error(f"✗ 窗口显示失败: {e}")
            logger.error(traceback.format_exc())
            return False

        # 11. 测试窗口关闭
        logger.info("11. 测试窗口关闭...")
        try:
            performance_widget.close()
            logger.info("✓ 窗口关闭成功")

            # 强制刷新UI
            app.processEvents()
            logger.info("✓ UI刷新成功")

        except Exception as e:
            logger.error(f"✗ 窗口关闭失败: {e}")
            logger.error(traceback.format_exc())
            return False

        logger.info("=" * 80)
        logger.info("✓ 性能监控窗口测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

def test_with_full_system():
    """测试完整的系统启动"""
    logger.info("=" * 80)
    logger.info("测试完整系统启动")
    logger.info("=" * 80)

    try:
        # 1. 初始化核心组件
        logger.info("1. 初始化核心组件...")
        from core.containers import get_service_container
        from core.events import get_event_bus
        from core.services.service_bootstrap import bootstrap_services

        service_container = get_service_container()
        event_bus = get_event_bus()
        logger.info("✓ 核心组件初始化成功")

        # 2. 引导服务
        logger.info("2. 引导服务...")
        if not bootstrap_services():
            logger.error("✗ 服务引导失败")
            return False
        logger.info("✓ 服务引导成功")

        # 3. 测试性能监控窗口创建
        logger.info("3. 测试性能监控窗口创建...")
        result = test_performance_widget_creation()
        if not result:
            logger.error("✗ 性能监控窗口测试失败")
            return False

        logger.info("=" * 80)
        logger.info("✓ 完整系统测试通过")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"✗ 完整系统测试失败: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("开始测试性能监控中心崩溃问题...")

    # 先测试简单的窗口创建
    result1 = test_performance_widget_creation()

    if result1:
        logger.info("简单测试通过，继续测试完整系统...")
        result2 = test_with_full_system()

        if result2:
            logger.info("所有测试通过！")
            sys.exit(0)
        else:
            logger.error("完整系统测试失败")
            sys.exit(1)
    else:
        logger.error("简单测试失败")
        sys.exit(1)
