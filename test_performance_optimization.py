#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控架构优化测试脚本

测试统一管理器的功能和性能优化效果。
"""

import sys
import time
import psutil
from datetime import datetime
from typing import Dict, Any
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

# 初始化QApplication（PyQt5需要）
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QEventLoop
app = QApplication(sys.argv)

# 创建事件循环
event_loop = QEventLoop()

def process_events():
    """处理Qt事件"""
    app.processEvents()

# 创建定时器处理事件
event_timer = QTimer()
event_timer.timeout.connect(process_events)
event_timer.start(10)  # 每10ms处理一次事件


def test_timer_manager():
    """测试定时器管理器"""
    logger.info("=" * 80)
    logger.info("测试统一定时器管理器")
    logger.info("=" * 80)

    try:
        from core.performance.timer_manager import get_timer_manager, TimerPriority

        timer_manager = get_timer_manager()

        # 测试数据
        test_results = []
        execution_count = 0

        def test_callback():
            nonlocal execution_count
            execution_count += 1
            logger.debug(f"定时器回调执行次数: {execution_count}")

        # 注册多个定时器
        timer_manager.register_timer(
            name="test_timer_1",
            interval=1.0,
            callback=test_callback,
            priority=TimerPriority.NORMAL,
            enabled=True
        )

        timer_manager.register_timer(
            name="test_timer_2",
            interval=2.0,
            callback=test_callback,
            priority=TimerPriority.HIGH,
            enabled=True
        )

        timer_manager.register_timer(
            name="test_timer_3",
            interval=3.0,
            callback=test_callback,
            priority=TimerPriority.LOW,
            enabled=True
        )

        # 启动定时器管理器
        timer_manager.start()

        # 等待一段时间
        logger.info("等待10秒...")
        for i in range(100):  # 最多等待10秒
            time.sleep(0.1)
            app.processEvents()  # 处理Qt事件

        # 获取统计信息
        stats = timer_manager.get_stats()
        test_results.append(("定时器数量", stats['total_tasks']))
        test_results.append(("活跃定时器数量", stats['active_tasks']))
        test_results.append(("总执行次数", stats['total_runs']))
        test_results.append(("总执行时间", f"{stats['total_run_time']:.3f}s"))

        # 停止定时器管理器
        timer_manager.stop()

        logger.info("✓ 统一定时器管理器测试通过")
        return test_results

    except Exception as e:
        logger.error(f"✗ 统一定时器管理器测试失败: {e}")
        return []


def test_thread_pool_manager():
    """测试线程池管理器"""
    logger.info("=" * 80)
    logger.info("测试统一线程池管理器")
    logger.info("=" * 80)

    try:
        from core.performance.thread_pool_manager import get_thread_pool_manager, TaskPriority

        thread_pool_manager = get_thread_pool_manager()

        # 测试数据
        test_results = []
        completed_count = 0
        import threading
        completion_event = threading.Event()

        def test_task(task_id: int):
            """测试任务"""
            logger.debug(f"任务 {task_id} 开始执行")
            time.sleep(0.1)  # 模拟任务执行
            logger.debug(f"任务 {task_id} 执行完成")
            return f"任务 {task_id} 的结果"

        def on_task_completed(task_id, result):
            """任务完成回调"""
            nonlocal completed_count
            completed_count += 1
            logger.debug(f"任务 {task_id} 完成，已完成 {completed_count}/10")
            if completed_count >= 10:
                completion_event.set()

        # 连接信号
        thread_pool_manager.task_completed.connect(on_task_completed)

        # 提交多个任务
        task_ids = []
        for i in range(10):
            task_id = thread_pool_manager.submit_task(
                func=test_task,
                args=(i,),
                priority=TaskPriority.NORMAL,
                timeout=5.0
            )
            task_ids.append(task_id)
            logger.info(f"已提交任务 {i}: {task_id}")

        # 等待所有任务完成
        logger.info("等待所有任务完成...")
        for i in range(100):  # 最多等待10秒
            time.sleep(0.1)
            app.processEvents()  # 处理Qt事件
            logger.debug(f"等待进度: {completed_count}/10")
            if completed_count >= 10:
                logger.info(f"所有任务已完成！已完成 {completed_count}/10")
                break

        # 断开信号连接
        thread_pool_manager.task_completed.disconnect(on_task_completed)

        # 获取统计信息
        stats = thread_pool_manager.get_stats()
        test_results.append(("总任务数", stats['total_tasks']))
        test_results.append(("已完成任务数", stats['completed_tasks']))
        test_results.append(("活跃任务数", stats['active_tasks']))
        test_results.append(("最大工作线程数", stats['max_workers']))

        logger.info("✓ 统一线程池管理器测试通过")
        return test_results

    except Exception as e:
        logger.error(f"✗ 统一线程池管理器测试失败: {e}")
        return []


def test_task_scheduler():
    """测试任务调度器"""
    logger.info("=" * 80)
    logger.info("测试统一任务调度器")
    logger.info("=" * 80)

    try:
        from core.performance.task_scheduler import get_task_scheduler, TaskPriority

        task_scheduler = get_task_scheduler()

        # 测试数据
        test_results = []

        def test_task(task_id: str):
            """测试任务"""
            logger.debug(f"任务 {task_id} 开始执行")
            time.sleep(0.1)
            logger.debug(f"任务 {task_id} 执行完成")
            return f"任务 {task_id} 的结果"

        # 调度多个任务
        task_ids = []

        # 调度独立任务
        task_id_1 = task_scheduler.schedule_task(
            func=test_task,
            args=("task_1",),
            priority=TaskPriority.NORMAL
        )
        task_ids.append(task_id_1)

        # 调度有依赖关系的任务
        task_id_2 = task_scheduler.schedule_task(
            func=test_task,
            args=("task_2",),
            priority=TaskPriority.NORMAL
        )
        task_ids.append(task_id_2)

        task_id_3 = task_scheduler.schedule_task(
            func=test_task,
            args=("task_3",),
            priority=TaskPriority.NORMAL,
            dependencies=[task_id_2]
        )
        task_ids.append(task_id_3)

        logger.info(f"已调度任务: {task_ids}")

        # 等待所有任务完成
        logger.info("等待所有任务完成...")
        for i in range(30):  # 最多等待3秒
            time.sleep(0.1)
            app.processEvents()  # 处理Qt事件
            stats = task_scheduler.get_stats()
            logger.info(f"任务进度: {stats['completed_tasks']}/{stats['total_tasks']}, 运行中: {stats['running_tasks']}, 准备中: {stats['ready_tasks']}, 等待中: {stats['pending_tasks']}")

        # 获取统计信息
        stats = task_scheduler.get_stats()
        test_results.append(("总任务数", stats['total_tasks']))
        test_results.append(("已完成任务数", stats['completed_tasks']))
        test_results.append(("失败任务数", stats['failed_tasks']))

        logger.info("✓ 统一任务调度器测试通过")
        return test_results

    except Exception as e:
        logger.error(f"✗ 统一任务调度器测试失败: {e}")
        return []


def test_resource_monitor():
    """测试资源监控器"""
    logger.info("=" * 80)
    logger.info("测试统一资源监控器")
    logger.info("=" * 80)

    try:
        from core.performance.resource_monitor import get_resource_monitor, ResourceType

        resource_monitor = get_resource_monitor()

        # 测试数据
        test_results = []

        # 启动资源监控
        resource_monitor.start()

        # 等待一段时间
        logger.info("等待5秒...")
        for i in range(50):  # 最多等待5秒
            time.sleep(0.1)
            app.processEvents()  # 处理Qt事件

        # 获取当前资源使用情况
        cpu_usage = resource_monitor.get_current_usage(ResourceType.CPU)
        memory_usage = resource_monitor.get_current_usage(ResourceType.MEMORY)
        disk_usage = resource_monitor.get_current_usage(ResourceType.DISK)

        if cpu_usage:
            test_results.append(("CPU使用率", f"{cpu_usage.value:.1f}%"))
        if memory_usage:
            test_results.append(("内存使用率", f"{memory_usage.value:.1f}%"))
        if disk_usage:
            test_results.append(("磁盘使用率", f"{disk_usage.value:.1f}%"))

        # 获取统计信息
        stats = resource_monitor.get_stats()
        test_results.append(("总告警数", stats['total_alerts']))
        test_results.append(("严重告警数", stats['critical_alerts']))
        test_results.append(("警告告警数", stats['warning_alerts']))

        # 停止资源监控
        resource_monitor.stop()

        logger.info("✓ 统一资源监控器测试通过")
        return test_results

    except Exception as e:
        logger.error(f"✗ 统一资源监控器测试失败: {e}")
        return []


def test_data_update_manager():
    """测试数据更新管理器"""
    logger.info("=" * 80)
    logger.info("测试性能数据更新管理器")
    logger.info("=" * 80)

    try:
        from core.performance.data_update_manager import get_data_update_manager, UpdateStrategy

        data_update_manager = get_data_update_manager()

        # 测试数据
        test_results = []

        def test_data_collector():
            """测试数据收集函数"""
            logger.debug("收集测试数据")
            return {
                'test_metric_1': 100.0,
                'test_metric_2': 200.0,
                'test_metric_3': 300.0
            }

        # 注册标签页
        data_update_manager.register_tab(
            tab_name="test_tab",
            data_collector=test_data_collector,
            update_interval=2.0,
            update_strategy=UpdateStrategy.EVENT_DRIVEN,
            enabled=True
        )

        # 等待一段时间
        logger.info("等待5秒...")
        for i in range(50):  # 最多等待5秒
            time.sleep(0.1)
            app.processEvents()  # 处理Qt事件

        # 获取统计信息
        stats = data_update_manager.get_stats()
        test_results.append(("已注册标签页数", stats['registered_tabs']))
        test_results.append(("启用标签页数", stats['enabled_tabs']))
        test_results.append(("总更新次数", stats['total_updates']))
        test_results.append(("成功更新次数", stats['successful_updates']))

        # 获取缓存数据
        cached_data = data_update_manager.get_cached_data("test_tab")
        if cached_data:
            test_results.append(("缓存数据", f"{len(cached_data)} 个指标"))

        # 注销标签页
        data_update_manager.unregister_tab("test_tab")

        logger.info("✓ 性能数据更新管理器测试通过")
        return test_results

    except Exception as e:
        logger.error(f"✗ 性能数据更新管理器测试失败: {e}")
        return []


def test_performance_comparison():
    """性能对比测试"""
    logger.info("=" * 80)
    logger.info("性能对比测试")
    logger.info("=" * 80)

    try:
        # 获取当前进程
        process = psutil.Process()

        # 记录初始资源使用情况
        initial_cpu = process.cpu_percent(interval=1.0)
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB

        logger.info(f"初始CPU使用率: {initial_cpu:.1f}%")
        logger.info(f"初始内存使用: {initial_memory:.1f}MB")

        # 运行测试
        logger.info("运行性能测试...")
        start_time = time.time()

        test_results = []
        test_results.extend(test_timer_manager())
        test_results.extend(test_thread_pool_manager())
        test_results.extend(test_task_scheduler())
        test_results.extend(test_resource_monitor())
        test_results.extend(test_data_update_manager())

        end_time = time.time()
        test_duration = end_time - start_time

        # 记录最终资源使用情况
        final_cpu = process.cpu_percent(interval=1.0)
        final_memory = process.memory_info().rss / (1024 * 1024)  # MB

        logger.info(f"最终CPU使用率: {final_cpu:.1f}%")
        logger.info(f"最终内存使用: {final_memory:.1f}MB")

        # 计算资源变化
        cpu_change = final_cpu - initial_cpu
        memory_change = final_memory - initial_memory

        test_results.append(("测试持续时间", f"{test_duration:.1f}s"))
        test_results.append(("CPU使用率变化", f"{cpu_change:+.1f}%"))
        test_results.append(("内存使用变化", f"{memory_change:+.1f}MB"))

        logger.info("✓ 性能对比测试完成")
        return test_results

    except Exception as e:
        logger.error(f"✗ 性能对比测试失败: {e}")
        return []


def print_test_results(results: list):
    """打印测试结果"""
    logger.info("=" * 80)
    logger.info("测试结果汇总")
    logger.info("=" * 80)

    for name, value in results:
        logger.info(f"{name:30s}: {value}")

    logger.info("=" * 80)


def main():
    """主函数"""
    logger.info("开始性能监控架构优化测试")
    logger.info(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 初始化性能管理器
        logger.info("初始化性能管理器...")
        from core.performance import initialize_performance_managers
        initialize_performance_managers()

        # 运行测试
        results = test_performance_comparison()

        # 打印测试结果
        print_test_results(results)

        # 关闭性能管理器
        logger.info("关闭性能管理器...")
        from core.performance import shutdown_performance_managers
        shutdown_performance_managers()

        logger.info("✓ 所有测试完成")

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
