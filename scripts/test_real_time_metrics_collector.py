"""
实时指标收集器性能测试脚本
测试实时指标收集器的实际效果
"""

import time
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.performance.real_time_metrics_collector import (
    RealTimeMetricsCollector,
    CollectionConfig,
    CollectionMode,
    MetricPriority
)
from loguru import logger

def test_real_time_metrics_collector():
    """测试实时指标收集器"""
    logger.info("=" * 80)
    logger.info("实时指标收集器性能测试")
    logger.info("=" * 80)
    
    # 创建收集配置
    config = CollectionConfig(
        collection_mode=CollectionMode.ADAPTIVE,
        critical_interval=0.5,  # 关键指标0.5秒收集一次
        high_interval=1.0,  # 高优先级指标1秒收集一次
        medium_interval=2.0,  # 中等优先级指标2秒收集一次
        low_interval=5.0,  # 低优先级指标5秒收集一次
        buffer_size=1000,
        batch_size=50,
        max_collection_time=0.1,
        enable_async_collection=True,
        max_workers=4,
        enable_cpu_details=True,
        enable_memory_details=True,
        enable_disk_details=True,
        enable_network_details=True,
        enable_process_monitoring=True,
        cpu_threshold=90.0,
        memory_threshold=85.0,
        disk_threshold=90.0,
        network_threshold=100.0
    )
    
    # 创建实时指标收集器
    logger.info("\n创建实时指标收集器...")
    collector = RealTimeMetricsCollector(config)
    
    # 测试1：启动收集器
    logger.info("\n" + "=" * 80)
    logger.info("测试1：启动收集器")
    logger.info("=" * 80)
    
    start_time = time.time()
    success = collector.start()
    startup_time = time.time() - start_time
    
    logger.info(f"\n收集器启动结果：{'成功' if success else '失败'}")
    logger.info(f"启动时间：{startup_time:.4f}秒")
    
    if not success:
        logger.error("收集器启动失败，无法继续测试")
        return
    
    # 等待收集器收集一些指标
    logger.info("\n等待5秒，让收集器收集指标...")
    time.sleep(5)
    
    # 测试2：同步收集指标
    logger.info("\n" + "=" * 80)
    logger.info("测试2：同步收集指标")
    logger.info("=" * 80)
    
    start_time = time.time()
    critical_metrics = collector.collect_metrics_sync(MetricPriority.CRITICAL)
    critical_time = time.time() - start_time
    
    start_time = time.time()
    high_metrics = collector.collect_metrics_sync(MetricPriority.HIGH)
    high_time = time.time() - start_time
    
    start_time = time.time()
    medium_metrics = collector.collect_metrics_sync(MetricPriority.MEDIUM)
    medium_time = time.time() - start_time
    
    start_time = time.time()
    all_metrics = collector.collect_metrics_sync()
    all_time = time.time() - start_time
    
    logger.info("\n同步收集结果：")
    logger.info(f"  关键指标（CPU、内存）：{len(critical_metrics)}个，耗时{critical_time:.4f}秒")
    logger.info(f"  高优先级指标（磁盘、网络）：{len(high_metrics)}个，耗时{high_time:.4f}秒")
    logger.info(f"  中等优先级指标（进程）：{len(medium_metrics)}个，耗时{medium_time:.4f}秒")
    logger.info(f"  所有指标：{len(all_metrics)}个，耗时{all_time:.4f}秒")
    
    # 测试3：异步收集指标
    logger.info("\n" + "=" * 80)
    logger.info("测试3：异步收集指标")
    logger.info("=" * 80)
    
    import asyncio
    
    async def test_async_collection():
        start_time = time.time()
        critical_metrics_async = await collector.collect_metrics_async(MetricPriority.CRITICAL)
        critical_time_async = time.time() - start_time
        
        start_time = time.time()
        all_metrics_async = await collector.collect_metrics_async()
        all_time_async = time.time() - start_time
        
        return critical_metrics_async, critical_time_async, all_metrics_async, all_time_async
    
    start_time = time.time()
    critical_metrics_async, critical_time_async, all_metrics_async, all_time_async = asyncio.run(test_async_collection())
    total_async_time = time.time() - start_time
    
    logger.info("\n异步收集结果：")
    logger.info(f"  关键指标（CPU、内存）：{len(critical_metrics_async)}个，耗时{critical_time_async:.4f}秒")
    logger.info(f"  所有指标：{len(all_metrics_async)}个，耗时{all_time_async:.4f}秒")
    logger.info(f"  总异步时间：{total_async_time:.4f}秒")
    
    logger.info("\n性能对比：")
    logger.info(f"  同步收集关键指标：{critical_time:.4f}秒")
    logger.info(f"  异步收集关键指标：{critical_time_async:.4f}秒")
    logger.info(f"  加速比：{critical_time / critical_time_async:.2f}x")
    
    # 测试4：获取当前指标
    logger.info("\n" + "=" * 80)
    logger.info("测试4：获取当前指标")
    logger.info("=" * 80)
    
    start_time = time.time()
    current_metrics = collector.get_current_metrics()
    get_time = time.time() - start_time
    
    logger.info(f"\n获取当前指标：{len(current_metrics)}个，耗时{get_time:.4f}秒")
    
    # 显示一些关键指标
    logger.info("\n关键指标示例：")
    for metric in current_metrics[:10]:
        logger.info(f"  {metric.name}: {metric.value} ({metric.category.name})")
    
    # 测试5：收集统计信息
    logger.info("\n" + "=" * 80)
    logger.info("测试5：收集统计信息")
    logger.info("=" * 80)
    
    stats = collector.get_collection_stats()
    logger.info("\n收集统计信息：")
    logger.info(f"  总收集指标数：{stats['total_metrics_collected']}")
    logger.info(f"  总收集错误数：{stats['total_collection_errors']}")
    logger.info(f"  平均收集时间：{stats['average_collection_time']:.6f}秒")
    logger.info(f"  最后收集时间：{stats['last_collection_time']}")
    logger.info(f"  缓冲区溢出次数：{stats['buffer_overflow_count']}")
    
    # 测试6：停止收集器
    logger.info("\n" + "=" * 80)
    logger.info("测试6：停止收集器")
    logger.info("=" * 80)
    
    start_time = time.time()
    success = collector.stop()
    stop_time = time.time() - start_time
    
    logger.info(f"\n收集器停止结果：{'成功' if success else '失败'}")
    logger.info(f"停止时间：{stop_time:.4f}秒")
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("实时指标收集器性能总结")
    logger.info("=" * 80)
    
    logger.info("\n性能指标：")
    logger.info(f"  启动时间：{startup_time:.4f}秒")
    logger.info(f"  停止时间：{stop_time:.4f}秒")
    logger.info(f"  同步收集关键指标时间：{critical_time:.4f}秒")
    logger.info(f"  异步收集关键指标时间：{critical_time_async:.4f}秒")
    logger.info(f"  异步加速比：{critical_time / critical_time_async:.2f}x")
    logger.info(f"  获取当前指标时间：{get_time:.4f}秒")
    
    logger.info("\n收集统计：")
    logger.info(f"  总收集指标数：{stats['total_metrics_collected']}")
    logger.info(f"  总收集错误数：{stats['total_collection_errors']}")
    logger.info(f"  平均收集时间：{stats['average_collection_time']:.6f}秒")
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    test_real_time_metrics_collector()
