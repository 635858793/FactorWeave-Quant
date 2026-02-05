"""
AsyncIOManager性能测试脚本
测试AsyncIOManager的实际效果
"""

import asyncio
import time
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from backtest.async_io_manager import AsyncIOManager, SmartDataCache
from loguru import logger

def generate_test_data(size_mb: int = 10) -> bytes:
    """生成测试数据"""
    data = np.random.rand(size_mb * 1024 * 1024 // 8).astype(np.float64)
    return data.tobytes()

def test_sync_io(file_path: Path, data: bytes, iterations: int = 10) -> dict:
    """测试同步IO性能"""
    logger.info(f"测试同步IO性能，文件：{file_path}")
    
    write_times = []
    read_times = []
    
    for i in range(iterations):
        # 写入测试
        start_time = time.time()
        with open(file_path, 'wb') as f:
            f.write(data)
        write_time = time.time() - start_time
        write_times.append(write_time)
        
        # 读取测试
        start_time = time.time()
        with open(file_path, 'rb') as f:
            read_data = f.read()
        read_time = time.time() - start_time
        read_times.append(read_time)
    
    return {
        'write_avg': np.mean(write_times),
        'write_std': np.std(write_times),
        'read_avg': np.mean(read_times),
        'read_std': np.std(read_times),
        'total_time': sum(write_times) + sum(read_times)
    }

async def test_async_io(async_manager: AsyncIOManager, file_path: Path, data: bytes, iterations: int = 10) -> dict:
    """测试异步IO性能"""
    logger.info(f"测试异步IO性能，文件：{file_path}")
    
    write_times = []
    read_times = []
    
    for i in range(iterations):
        # 写入测试
        start_time = time.time()
        await async_manager.write_file_async(file_path, data)
        write_time = time.time() - start_time
        write_times.append(write_time)
        
        # 读取测试
        start_time = time.time()
        read_data = await async_manager.read_file_async(file_path)
        read_time = time.time() - start_time
        read_times.append(read_time)
    
    return {
        'write_avg': np.mean(write_times),
        'write_std': np.std(write_times),
        'read_avg': np.mean(read_times),
        'read_std': np.std(read_times),
        'total_time': sum(write_times) + sum(read_times)
    }

def test_cache_performance(cache: SmartDataCache, num_items: int = 1000) -> dict:
    """测试缓存性能"""
    logger.info(f"测试缓存性能，项目数：{num_items}")
    
    # 生成测试数据
    test_data = {
        f'key_{i}': np.random.rand(1000).astype(np.float64)
        for i in range(num_items)
    }
    
    # 写入测试
    start_time = time.time()
    for key, data in test_data.items():
        cache.put(key, data)
    write_time = time.time() - start_time
    
    # 读取测试（第一次，缓存未命中）
    start_time = time.time()
    for key in test_data.keys():
        data = cache.get(key)
    read_time_first = time.time() - start_time
    
    # 读取测试（第二次，缓存命中）
    start_time = time.time()
    for key in test_data.keys():
        data = cache.get(key)
    read_time_second = time.time() - start_time
    
    stats = cache.get_stats()
    
    return {
        'write_time': write_time,
        'read_time_first': read_time_first,
        'read_time_second': read_time_second,
        'speedup': read_time_first / read_time_second if read_time_second > 0 else 0,
        'stats': stats
    }

def test_batch_io(async_manager: AsyncIOManager, num_files: int = 50, file_size_mb: int = 1) -> dict:
    """测试批量IO性能"""
    logger.info(f"测试批量IO性能，文件数：{num_files}，文件大小：{file_size_mb}MB")
    
    # 创建测试目录
    test_dir = Path(__file__).parent / 'test_batch_io'
    test_dir.mkdir(exist_ok=True)
    
    # 生成测试文件
    test_files = []
    for i in range(num_files):
        file_path = test_dir / f'test_file_{i}.bin'
        data = generate_test_data(file_size_mb)
        test_files.append((file_path, data))
    
    # 测试同步批量读取
    start_time = time.time()
    sync_results = {}
    for file_path, data in test_files:
        with open(file_path, 'wb') as f:
            f.write(data)
        with open(file_path, 'rb') as f:
            sync_results[str(file_path)] = f.read()
    sync_time = time.time() - start_time
    
    # 测试异步批量读取
    start_time = time.time()
    async_results = async_manager.batch_read_files([fp for fp, _ in test_files])
    async_time = time.time() - start_time
    
    # 清理测试文件
    for file_path, _ in test_files:
        if file_path.exists():
            file_path.unlink()
    
    return {
        'sync_time': sync_time,
        'async_time': async_time,
        'speedup': sync_time / async_time if async_time > 0 else 0
    }

async def main():
    """主测试函数"""
    logger.info("=" * 80)
    logger.info("AsyncIOManager性能测试")
    logger.info("=" * 80)
    
    # 创建测试目录
    test_dir = Path(__file__).parent / 'test_async_io'
    test_dir.mkdir(exist_ok=True)
    
    # 生成测试数据
    test_data = generate_test_data(10)  # 10MB
    
    # 测试1：同步IO vs 异步IO
    logger.info("\n" + "=" * 80)
    logger.info("测试1：同步IO vs 异步IO")
    logger.info("=" * 80)
    
    sync_file = test_dir / 'test_sync.bin'
    async_file = test_dir / 'test_async.bin'
    
    sync_results = test_sync_io(sync_file, test_data, iterations=10)
    
    async_manager = AsyncIOManager(max_workers=4, cache_size=1000)
    async_results = await test_async_io(async_manager, async_file, test_data, iterations=10)
    
    logger.info("\n同步IO结果：")
    logger.info(f"  写入平均时间：{sync_results['write_avg']:.4f}秒")
    logger.info(f"  读取平均时间：{sync_results['read_avg']:.4f}秒")
    logger.info(f"  总时间：{sync_results['total_time']:.4f}秒")
    
    logger.info("\n异步IO结果：")
    logger.info(f"  写入平均时间：{async_results['write_avg']:.4f}秒")
    logger.info(f"  读取平均时间：{async_results['read_avg']:.4f}秒")
    logger.info(f"  总时间：{async_results['total_time']:.4f}秒")
    
    logger.info("\n性能对比：")
    logger.info(f"  写入加速比：{sync_results['write_avg'] / async_results['write_avg']:.2f}x")
    logger.info(f"  读取加速比：{sync_results['read_avg'] / async_results['read_avg']:.2f}x")
    logger.info(f"  总加速比：{sync_results['total_time'] / async_results['total_time']:.2f}x")
    
    # 测试2：缓存性能
    logger.info("\n" + "=" * 80)
    logger.info("测试2：缓存性能")
    logger.info("=" * 80)
    
    cache = SmartDataCache(max_memory_mb=100)
    cache_results = test_cache_performance(cache, num_items=1000)
    
    logger.info("\n缓存结果：")
    logger.info(f"  写入时间：{cache_results['write_time']:.4f}秒")
    logger.info(f"  第一次读取时间（缓存未命中）：{cache_results['read_time_first']:.4f}秒")
    logger.info(f"  第二次读取时间（缓存命中）：{cache_results['read_time_second']:.4f}秒")
    logger.info(f"  加速比：{cache_results['speedup']:.2f}x")
    logger.info(f"  缓存统计：{cache_results['stats']}")
    
    # 测试3：批量IO性能
    logger.info("\n" + "=" * 80)
    logger.info("测试3：批量IO性能")
    logger.info("=" * 80)
    
    batch_results = test_batch_io(async_manager, num_files=50, file_size_mb=1)
    
    logger.info("\n批量IO结果：")
    logger.info(f"  同步批量IO时间：{batch_results['sync_time']:.4f}秒")
    logger.info(f"  异步批量IO时间：{batch_results['async_time']:.4f}秒")
    logger.info(f"  加速比：{batch_results['speedup']:.2f}x")
    
    # 获取AsyncIOManager统计信息
    logger.info("\n" + "=" * 80)
    logger.info("AsyncIOManager统计信息")
    logger.info("=" * 80)
    
    cache_stats = async_manager.get_cache_stats()
    logger.info(f"  缓存大小：{cache_stats['cache_size']}/{cache_stats['max_cache_size']}")
    logger.info(f"  命中率：{cache_stats['hit_rate']:.2%}")
    logger.info(f"  总命中次数：{cache_stats['total_hits']}")
    logger.info(f"  总未命中次数：{cache_stats['total_misses']}")
    logger.info(f"  IO操作次数：{cache_stats['io_operations']}")
    logger.info(f"  异步操作次数：{cache_stats['async_operations']}")
    
    # 清理
    async_manager.cleanup()
    cache.clear()
    
    # 清理测试目录
    if test_dir.exists():
        for file in test_dir.iterdir():
            file.unlink()
        test_dir.rmdir()
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
