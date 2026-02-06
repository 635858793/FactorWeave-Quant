#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试任务调度器
"""

import sys
import time
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="DEBUG")

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

# 初始化性能管理器
from core.performance import initialize_performance_managers
initialize_performance_managers()

from core.performance.task_scheduler import get_task_scheduler, TaskPriority

task_scheduler = get_task_scheduler()

# 测试数据
test_results = []

def test_task(task_id: str):
    """测试任务"""
    logger.info(f"任务 {task_id} 开始执行")
    time.sleep(0.1)
    logger.info(f"任务 {task_id} 执行完成")
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
logger.info(f"已调度任务 1: {task_id_1}")

# 调度有依赖关系的任务
task_id_2 = task_scheduler.schedule_task(
    func=test_task,
    args=("task_2",),
    priority=TaskPriority.NORMAL
)
task_ids.append(task_id_2)
logger.info(f"已调度任务 2: {task_id_2}")

task_id_3 = task_scheduler.schedule_task(
    func=test_task,
    args=("task_3",),
    priority=TaskPriority.NORMAL,
    dependencies=[task_id_2]
)
task_ids.append(task_id_3)
logger.info(f"已调度任务 3: {task_id_3}")

logger.info(f"已调度任务: {task_ids}")

# 等待所有任务完成
logger.info("等待所有任务完成...")
for i in range(50):  # 最多等待5秒
    time.sleep(0.1)
    app.processEvents()  # 处理Qt事件
    stats = task_scheduler.get_stats()
    logger.info(f"任务进度: {stats['completed_tasks']}/{stats['total_tasks']}, 运行中: {stats['running_tasks']}, 准备中: {stats['ready_tasks']}, 等待中: {stats['pending_tasks']}")

# 获取统计信息
stats = task_scheduler.get_stats()
logger.info(f"最终统计: 总任务数={stats['total_tasks']}, 已完成任务数={stats['completed_tasks']}, 失败任务数={stats['failed_tasks']}")
