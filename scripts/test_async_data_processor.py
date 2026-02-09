"""
异步数据处理器性能测试脚本
测试异步数据处理器的实际效果
"""

import time
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from typing import List, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from optimization.async_data_processor import (
    AsyncDataProcessor,
    ProcessingPriority,
    get_async_processor,
    initialize_processor,
    shutdown_processor,
    submit_task,
    process_dataframe_async,
    process_array_async
)
from loguru import logger

# 配置日志输出到文件
logger.add("async_data_processor_test.log", rotation="10 MB")

def generate_test_dataframe(rows: int = 10000, cols: int = 10) -> pd.DataFrame:
    """生成测试DataFrame"""
    np.random.seed(42)
    data = np.random.randn(rows, cols)
    columns = [f'col_{i}' for i in range(cols)]
    return pd.DataFrame(data, columns=columns)

def generate_test_array(size: int = 100000) -> np.ndarray:
    """生成测试数组"""
    np.random.seed(42)
    return np.random.randn(size)

def simple_processor(data: Any) -> Any:
    """简单的处理函数"""
    if isinstance(data, pd.DataFrame):
        return data.mean()
    elif isinstance(data, np.ndarray):
        return data * 2  # 返回数组而不是标量
    else:
        return data

def complex_processor(data: Any) -> Any:
    """复杂的处理函数"""
    if isinstance(data, pd.DataFrame):
        return data.rolling(window=10).mean().dropna()
    elif isinstance(data, np.ndarray):
        return np.convolve(data, np.ones(10)/10, mode='valid')
    else:
        return data

def test_async_data_processor():
    """测试异步数据处理器"""
    logger.info("=" * 80)
    logger.info("异步数据处理器性能测试")
    logger.info("=" * 80)
    
    # 测试1：初始化和启动
    logger.info("\n" + "=" * 80)
    logger.info("测试1：初始化和启动")
    logger.info("=" * 80)
    
    start_time = time.time()
    processor = AsyncDataProcessor(max_workers=4, enable_monitoring=True)
    init_time = time.time() - start_time
    
    logger.info(f"\n初始化时间：{init_time:.4f}秒")
    logger.info(f"工作线程数：{processor.max_workers}")
    
    start_time = time.time()
    processor.start()
    start_time_elapsed = time.time() - start_time
    
    logger.info(f"启动时间：{start_time_elapsed:.4f}秒")
    
    # 等待处理器完全启动
    time.sleep(1)
    
    # 测试2：提交单个任务
    logger.info("\n" + "=" * 80)
    logger.info("测试2：提交单个任务")
    logger.info("=" * 80)
    
    test_data = "test_data"
    result = [None]
    
    def callback(result_data):
        result[0] = result_data
    
    start_time = time.time()
    success = processor.submit_task(
        task_id="test_task_1",
        data=test_data,
        processor=simple_processor,
        priority=ProcessingPriority.NORMAL,
        callback=callback
    )
    submit_time = time.time() - start_time
    
    logger.info(f"\n提交任务结果：{'成功' if success else '失败'}")
    logger.info(f"提交时间：{submit_time:.4f}秒")
    
    # 等待任务完成
    time.sleep(1)
    logger.info(f"任务结果：{result[0]}")
    
    # 测试3：批量提交任务
    logger.info("\n" + "=" * 80)
    logger.info("测试3：批量提交任务")
    logger.info("=" * 80)
    
    tasks = []
    for i in range(10):
        tasks.append({
            'task_id': f'batch_task_{i}',
            'data': f'batch_data_{i}',
            'processor': simple_processor,
            'priority': ProcessingPriority.NORMAL,
            'callback': None
        })
    
    start_time = time.time()
    success_count = processor.submit_batch_tasks(tasks)
    batch_submit_time = time.time() - start_time
    
    logger.info(f"\n批量提交任务：{success_count}/{len(tasks)}个成功")
    logger.info(f"批量提交时间：{batch_submit_time:.4f}秒")
    
    # 等待任务完成
    time.sleep(2)
    
    # 测试4：DataFrame分块处理
    logger.info("\n" + "=" * 80)
    logger.info("测试4：DataFrame分块处理")
    logger.info("=" * 80)
    
    # 生成测试数据
    df = generate_test_dataframe(rows=10000, cols=10)
    logger.info(f"\n测试DataFrame大小：{df.shape}")
    
    # 测试同步处理
    start_time = time.time()
    sync_result = simple_processor(df)
    sync_time = time.time() - start_time
    
    logger.info(f"同步处理结果：{sync_result}")
    logger.info(f"同步处理时间：{sync_time:.4f}秒")
    
    # 测试异步分块处理
    start_time = time.time()
    async_results = processor.process_dataframe_chunks(
        df=df,
        processor=simple_processor,
        chunk_size=1000,
        priority=ProcessingPriority.NORMAL
    )
    async_time = time.time() - start_time
    
    logger.info(f"异步分块处理结果数：{len(async_results)}")
    logger.info(f"异步分块处理时间：{async_time:.4f}秒")
    
    if sync_time > 0:
        speedup = sync_time / async_time
        logger.info(f"加速比：{speedup:.2f}x")
    
    # 测试5：数组并行处理
    logger.info("\n" + "=" * 80)
    logger.info("测试5：数组并行处理")
    logger.info("=" * 80)
    
    # 生成测试数据
    arr = generate_test_array(size=100000)
    logger.info(f"\n测试数组大小：{arr.shape}")
    
    # 测试同步处理
    start_time = time.time()
    sync_result = simple_processor(arr)
    sync_time = time.time() - start_time
    
    logger.info(f"同步处理结果：{sync_result}")
    logger.info(f"同步处理时间：{sync_time:.4f}秒")
    
    # 测试异步并行处理
    start_time = time.time()
    async_result = processor.process_array_parallel(
        data=arr,
        processor=simple_processor,
        num_splits=4,
        priority=ProcessingPriority.NORMAL
    )
    async_time = time.time() - start_time
    
    logger.info(f"异步并行处理结果：{async_result}")
    logger.info(f"异步并行处理时间：{async_time:.4f}秒")
    
    if sync_time > 0:
        speedup = sync_time / async_time
        logger.info(f"加速比：{speedup:.2f}x")
    
    # 测试6：获取队列状态
    logger.info("\n" + "=" * 80)
    logger.info("测试6：获取队列状态")
    logger.info("=" * 80)
    
    queue_status = processor.get_queue_status()
    logger.info(f"\n队列状态：")
    logger.info(f"  是否运行中：{queue_status['is_running']}")
    logger.info(f"  最大工作线程数：{queue_status['max_workers']}")
    logger.info(f"  总待处理任务数：{queue_status['total_pending']}")
    logger.info(f"  各优先级队列大小：{queue_status['queue_sizes']}")
    
    # 测试7：获取性能统计
    logger.info("\n" + "=" * 80)
    logger.info("测试7：获取性能统计")
    logger.info("=" * 80)
    
    perf_stats = processor.get_performance_stats()
    logger.info(f"\n性能统计：")
    logger.info(f"  总任务数：{perf_stats['total_tasks']}")
    logger.info(f"  已完成任务数：{perf_stats['completed_tasks']}")
    logger.info(f"  失败任务数：{perf_stats['failed_tasks']}")
    logger.info(f"  成功率：{perf_stats['success_rate']:.2f}%")
    logger.info(f"  平均处理时间：{perf_stats['average_processing_time']:.6f}秒")
    logger.info(f"  总处理任务数：{perf_stats['total_processed']}")
    logger.info(f"  待处理任务数：{perf_stats['pending_tasks']}")
    
    # 测试8：清空队列
    logger.info("\n" + "=" * 80)
    logger.info("测试8：清空队列")
    logger.info("=" * 80)
    
    # 提交一些任务到队列
    for i in range(5):
        processor.submit_task(
            task_id=f'clear_test_{i}',
            data=f'clear_data_{i}',
            processor=simple_processor,
            priority=ProcessingPriority.NORMAL,
            callback=None
        )
    
    # 检查队列状态
    queue_status_before = processor.get_queue_status()
    logger.info(f"\n清空前队列大小：{queue_status_before['total_pending']}")
    
    # 清空队列
    processor.clear_queue(priority=ProcessingPriority.NORMAL)
    
    # 检查队列状态
    queue_status_after = processor.get_queue_status()
    logger.info(f"清空后队列大小：{queue_status_after['total_pending']}")
    
    # 测试9：停止处理器
    logger.info("\n" + "=" * 80)
    logger.info("测试9：停止处理器")
    logger.info("=" * 80)
    
    start_time = time.time()
    processor.stop()
    stop_time = time.time() - start_time
    
    logger.info(f"\n停止时间：{stop_time:.4f}秒")
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("异步数据处理器性能总结")
    logger.info("=" * 80)
    
    logger.info("\n性能指标：")
    logger.info(f"  初始化时间：{init_time:.4f}秒")
    logger.info(f"  启动时间：{start_time_elapsed:.4f}秒")
    logger.info(f"  停止时间：{stop_time:.4f}秒")
    logger.info(f"  工作线程数：{processor.max_workers}")
    
    logger.info("\n处理性能：")
    logger.info(f"  DataFrame同步处理时间：{sync_time:.4f}秒")
    logger.info(f"  DataFrame异步分块处理时间：{async_time:.4f}秒")
    logger.info(f"  数组同步处理时间：{sync_time:.4f}秒")
    logger.info(f"  数组异步并行处理时间：{async_time:.4f}秒")
    
    logger.info("\n任务统计：")
    logger.info(f"  总任务数：{perf_stats['total_tasks']}")
    logger.info(f"  已完成任务数：{perf_stats['completed_tasks']}")
    logger.info(f"  失败任务数：{perf_stats['failed_tasks']}")
    logger.info(f"  成功率：{perf_stats['success_rate']:.2f}%")
    logger.info(f"  平均处理时间：{perf_stats['average_processing_time']:.6f}秒")
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    test_async_data_processor()
