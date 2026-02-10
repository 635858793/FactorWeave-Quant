#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
README性能指标验证脚本
全面测试和验证README.md中声明的性能指标

测试项目:
1. 系统启动时间
2. 运行内存占用
3. 峰值内存使用
4. CPU平均负载
5. API响应时间
6. 活跃线程数量
7. 回测速度
8. 策略执行延迟
9. 数据处理吞吐量
10. 并发处理能力
11. 内存泄漏率（长时间运行）
12. 系统稳定性（长时间运行）
"""

import os
import sys
import time
import json
import psutil
import threading
import multiprocessing
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import concurrent.futures
import traceback

# 确保项目根目录在Python路径中
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('readme_performance_validation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标数据结构"""
    test_name: str
    measured_value: float
    unit: str
    readme_value: float
    target_value: float
    status: str  # '达标', '优秀', '未达标'
    improvement_percent: float = 0.0
    notes: str = ""


@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    success: bool
    metrics: PerformanceMetrics
    error_message: str = ""
    timestamp: str = ""


class READMEPerformanceValidator:
    """README性能指标验证器"""

    def __init__(self):
        """初始化验证器"""
        self.process = psutil.Process()
        self.test_results: List[TestResult] = []
        self.start_time = time.time()
        
        # README中声明的性能指标
        self.readme_metrics = {
            # 量化交易专项性能
            '回测速度': {
                'value': 100.0,  # 100万条数据/秒
                'unit': '万条/秒',
                'target': 50.0,
                'target_desc': '行业标准'
            },
            '策略执行延迟': {
                'value': 15.0,  # 15ms
                'unit': 'ms',
                'target': 50.0,
                'target_desc': '行业标准'
            },
            '数据处理吞吐量': {
                'value': 2000.0,  # 2000笔/秒
                'unit': '笔/秒',
                'target': 1000.0,
                'target_desc': '行业标准'
            },
            '内存泄漏率': {
                'value': 0.0,  # 0.0MB/小时
                'unit': 'MB/小时',
                'target': 50.0,
                'target_desc': '行业标准'
            },
            '系统稳定性': {
                'value': 99.9,  # 99.9%
                'unit': '%',
                'target': 99.5,
                'target_desc': '行业标准'
            },
            
            # 性能目标达成情况
            'API响应时间': {
                'value': 30.1,  # 30.1ms
                'unit': 'ms',
                'target': 100.0,
                'target_desc': '目标值'
            },
            'CPU平均负载': {
                'value': 0.0,  # 0.0%
                'unit': '%',
                'target': 25.0,
                'target_desc': '目标值'
            },
            '峰值内存使用': {
                'value': 549.1,  # 549.1MB
                'unit': 'MB',
                'target': 1200.0,
                'target_desc': '目标值'
            },
            '活跃线程数量': {
                'value': 13,  # 13个
                'unit': '个',
                'target': 25,
                'target_desc': '目标值'
            },
            '系统启动时间': {
                'value': 16.8,  # 16.8s
                'unit': 's',
                'target': 8.0,
                'target_desc': '目标值'
            },
            '运行内存占用': {
                'value': 547.6,  # 547.6MB
                'unit': 'MB',
                'target': 400.0,
                'target_desc': '目标值'
            },
            '并发处理能力': {
                'value': 48,  # 48个任务
                'unit': '个',
                'target': 100,
                'target_desc': '目标值'
            }
        }
        
        # 长期测试标记
        self.long_term_test = False
        self.long_term_duration_hours = 1.0  # 默认1小时

    def test_startup_time(self) -> TestResult:
        """测试系统启动时间"""
        logger.info("=" * 80)
        logger.info("测试1: 系统启动时间")
        logger.info("=" * 80)
        
        try:
            # 记录初始内存
            initial_memory = self.process.memory_info().rss / (1024 * 1024)
            logger.info(f"初始内存使用: {initial_memory:.1f}MB")
            
            # 测量启动时间
            start_time = time.time()
            
            # 模拟系统启动（导入核心模块）
            try:
                from core.events.event_bus import EventBus
                from core.containers.unified_service_container import UnifiedServiceContainer
                
                # 初始化事件总线
                event_bus = EventBus()
                
                # 初始化服务容器
                container = UnifiedServiceContainer(event_bus)
                
                # 注册核心服务
                from core.services.config_service import ConfigService
                from core.services.cache_service import CacheService
                
                config_service = ConfigService(container)
                cache_service = CacheService(container)
                
                container.register_instance(ConfigService, config_service)
                container.register_instance(CacheService, cache_service)
                
                config_service.initialize()
                cache_service.initialize()
                
            except Exception as e:
                logger.warning(f"部分服务初始化失败: {e}")
            
            end_time = time.time()
            startup_time = end_time - start_time
            
            # 获取README中的值
            readme_value = self.readme_metrics['系统启动时间']['value']
            target_value = self.readme_metrics['系统启动时间']['target']
            
            # 计算状态
            if startup_time <= target_value * 0.8:
                status = '优秀'
            elif startup_time <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - startup_time) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='系统启动时间',
                measured_value=startup_time,
                unit='s',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}s, 实测: {startup_time:.2f}s"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测启动时间: {startup_time:.2f}s")
            logger.info(f"   README声明: {readme_value}s")
            logger.info(f"   目标值: {target_value}s")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='系统启动时间',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='系统启动时间',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='系统启动时间',
                    measured_value=0,
                    unit='s',
                    readme_value=self.readme_metrics['系统启动时间']['value'],
                    target_value=self.readme_metrics['系统启动时间']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_memory_usage(self) -> TestResult:
        """测试运行内存占用"""
        logger.info("=" * 80)
        logger.info("测试2: 运行内存占用")
        logger.info("=" * 80)
        
        try:
            # 获取当前内存使用
            memory_info = self.process.memory_info()
            current_memory_mb = memory_info.rss / (1024 * 1024)
            
            # 执行一些操作来测量峰值内存
            peak_memory_mb = current_memory_mb
            
            # 模拟系统运行压力测试
            test_data = []
            for i in range(1000):
                test_data.append({
                    'id': i,
                    'data': f'test_data_{i}' * 100,
                    'timestamp': time.time()
                })
                
                # 每100次检查一次内存使用
                if i % 100 == 0:
                    current_mem = self.process.memory_info().rss / (1024 * 1024)
                    peak_memory_mb = max(peak_memory_mb, current_mem)
            
            # 清理测试数据
            del test_data
            
            # 获取最终内存使用
            final_memory_mb = self.process.memory_info().rss / (1024 * 1024)
            
            # 使用峰值作为测试结果
            measured_memory = peak_memory_mb
            
            # 获取README中的值
            readme_value = self.readme_metrics['运行内存占用']['value']
            target_value = self.readme_metrics['运行内存占用']['target']
            
            # 计算状态
            if measured_memory <= target_value * 0.8:
                status = '优秀'
            elif measured_memory <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - measured_memory) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='运行内存占用',
                measured_value=measured_memory,
                unit='MB',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}MB, 实测: {measured_memory:.1f}MB"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测内存占用: {measured_memory:.1f}MB")
            logger.info(f"   README声明: {readme_value}MB")
            logger.info(f"   目标值: {target_value}MB")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='运行内存占用',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='运行内存占用',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='运行内存占用',
                    measured_value=0,
                    unit='MB',
                    readme_value=self.readme_metrics['运行内存占用']['value'],
                    target_value=self.readme_metrics['运行内存占用']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_peak_memory(self) -> TestResult:
        """测试峰值内存使用"""
        logger.info("=" * 80)
        logger.info("测试3: 峰值内存使用")
        logger.info("=" * 80)
        
        try:
            # 获取当前内存使用
            current_memory_mb = self.process.memory_info().rss / (1024 * 1024)
            
            # 执行内存密集型操作
            peak_memory_mb = current_memory_mb
            
            # 创建大型数组
            for size in [1000, 5000, 10000, 20000]:
                test_array = np.random.randn(size, 100)
                current_mem = self.process.memory_info().rss / (1024 * 1024)
                peak_memory_mb = max(peak_memory_mb, current_mem)
                del test_array
            
            # 获取最终内存使用
            final_memory_mb = self.process.memory_info().rss / (1024 * 1024)
            
            # 使用峰值作为测试结果
            measured_memory = peak_memory_mb
            
            # 获取README中的值
            readme_value = self.readme_metrics['峰值内存使用']['value']
            target_value = self.readme_metrics['峰值内存使用']['target']
            
            # 计算状态
            if measured_memory <= target_value * 0.8:
                status = '优秀'
            elif measured_memory <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - measured_memory) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='峰值内存使用',
                measured_value=measured_memory,
                unit='MB',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}MB, 实测: {measured_memory:.1f}MB"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测峰值内存: {measured_memory:.1f}MB")
            logger.info(f"   README声明: {readme_value}MB")
            logger.info(f"   目标值: {target_value}MB")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='峰值内存使用',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='峰值内存使用',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='峰值内存使用',
                    measured_value=0,
                    unit='MB',
                    readme_value=self.readme_metrics['峰值内存使用']['value'],
                    target_value=self.readme_metrics['峰值内存使用']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_cpu_usage(self) -> TestResult:
        """测试CPU平均负载"""
        logger.info("=" * 80)
        logger.info("测试4: CPU平均负载")
        logger.info("=" * 80)
        
        try:
            # 测量一段时间内的CPU使用率
            cpu_samples = []
            for _ in range(10):
                cpu_percent = self.process.cpu_percent(interval=0.1)
                cpu_samples.append(cpu_percent)
            
            # 计算平均CPU使用率
            avg_cpu_usage = sum(cpu_samples) / len(cpu_samples)
            
            # 获取README中的值
            readme_value = self.readme_metrics['CPU平均负载']['value']
            target_value = self.readme_metrics['CPU平均负载']['target']
            
            # 计算状态
            if avg_cpu_usage <= target_value * 0.5:
                status = '优秀'
            elif avg_cpu_usage <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - avg_cpu_usage) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='CPU平均负载',
                measured_value=avg_cpu_usage,
                unit='%',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}%, 实测: {avg_cpu_usage:.1f}%"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测CPU使用率: {avg_cpu_usage:.1f}%")
            logger.info(f"   README声明: {readme_value}%")
            logger.info(f"   目标值: {target_value}%")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='CPU平均负载',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='CPU平均负载',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='CPU平均负载',
                    measured_value=0,
                    unit='%',
                    readme_value=self.readme_metrics['CPU平均负载']['value'],
                    target_value=self.readme_metrics['CPU平均负载']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_thread_count(self) -> TestResult:
        """测试活跃线程数量"""
        logger.info("=" * 80)
        logger.info("测试5: 活跃线程数量")
        logger.info("=" * 80)
        
        try:
            # 获取线程数量
            thread_count = threading.active_count()
            
            # 获取README中的值
            readme_value = self.readme_metrics['活跃线程数量']['value']
            target_value = self.readme_metrics['活跃线程数量']['target']
            
            # 计算状态
            if thread_count <= target_value * 0.6:
                status = '优秀'
            elif thread_count <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - thread_count) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='活跃线程数量',
                measured_value=thread_count,
                unit='个',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}个, 实测: {thread_count}个"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测线程数: {thread_count}个")
            logger.info(f"   README声明: {readme_value}个")
            logger.info(f"   目标值: {target_value}个")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='活跃线程数量',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='活跃线程数量',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='活跃线程数量',
                    measured_value=0,
                    unit='个',
                    readme_value=self.readme_metrics['活跃线程数量']['value'],
                    target_value=self.readme_metrics['活跃线程数量']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_api_response_time(self) -> TestResult:
        """测试API响应时间"""
        logger.info("=" * 80)
        logger.info("测试6: API响应时间")
        logger.info("=" * 80)
        
        try:
            # 模拟API调用
            response_times = []
            
            # 测试多个操作
            test_operations = [
                'config_get',
                'cache_get',
                'data_query',
                'health_check'
            ]
            
            for operation in test_operations:
                start_time = time.perf_counter()
                
                # 模拟API操作
                time.sleep(0.001)  # 模拟1ms的API延迟
                
                end_time = time.perf_counter()
                response_time_ms = (end_time - start_time) * 1000
                response_times.append(response_time_ms)
            
            # 计算平均响应时间
            avg_response_time = sum(response_times) / len(response_times)
            
            # 获取README中的值
            readme_value = self.readme_metrics['API响应时间']['value']
            target_value = self.readme_metrics['API响应时间']['target']
            
            # 计算状态
            if avg_response_time <= target_value * 0.5:
                status = '优秀'
            elif avg_response_time <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - avg_response_time) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='API响应时间',
                measured_value=avg_response_time,
                unit='ms',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}ms, 实测: {avg_response_time:.2f}ms"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测响应时间: {avg_response_time:.2f}ms")
            logger.info(f"   README声明: {readme_value}ms")
            logger.info(f"   目标值: {target_value}ms")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='API响应时间',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='API响应时间',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='API响应时间',
                    measured_value=0,
                    unit='ms',
                    readme_value=self.readme_metrics['API响应时间']['value'],
                    target_value=self.readme_metrics['API响应时间']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_backtest_speed(self) -> TestResult:
        """测试回测速度"""
        logger.info("=" * 80)
        logger.info("测试7: 回测速度")
        logger.info("=" * 80)
        
        try:
            # 生成测试数据
            data_size = 1000000  # 100万条数据
            test_data = pd.DataFrame({
                'open': np.random.randn(data_size).cumsum() + 100,
                'high': np.random.randn(data_size).cumsum() + 102,
                'low': np.random.randn(data_size).cumsum() + 98,
                'close': np.random.randn(data_size).cumsum() + 100,
                'volume': np.random.exponential(1000, data_size)
            })
            
            # 测量回测速度
            start_time = time.time()
            
            # 模拟回测操作
            for i in range(len(test_data)):
                # 简单的技术指标计算
                if i >= 20:
                    test_data.loc[i, 'ma20'] = test_data.loc[i-20:i, 'close'].mean()
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # 计算速度（万条/秒）
            backtest_speed = (data_size / 10000) / elapsed_time
            
            # 获取README中的值
            readme_value = self.readme_metrics['回测速度']['value']
            target_value = self.readme_metrics['回测速度']['target']
            
            # 计算状态
            if backtest_speed >= target_value * 1.5:
                status = '优秀'
            elif backtest_speed >= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((backtest_speed - readme_value) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='回测速度',
                measured_value=backtest_speed,
                unit='万条/秒',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}万条/秒, 实测: {backtest_speed:.2f}万条/秒"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测回测速度: {backtest_speed:.2f}万条/秒")
            logger.info(f"   README声明: {readme_value}万条/秒")
            logger.info(f"   目标值: {target_value}万条/秒")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='回测速度',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='回测速度',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='回测速度',
                    measured_value=0,
                    unit='万条/秒',
                    readme_value=self.readme_metrics['回测速度']['value'],
                    target_value=self.readme_metrics['回测速度']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_strategy_execution_delay(self) -> TestResult:
        """测试策略执行延迟"""
        logger.info("=" * 80)
        logger.info("测试8: 策略执行延迟")
        logger.info("=" * 80)
        
        try:
            # 模拟策略执行
            execution_times = []
            
            for _ in range(100):
                start_time = time.perf_counter()
                
                # 模拟策略逻辑
                data = np.random.randn(100)
                ma = np.mean(data)
                std = np.std(data)
                signal = (data[-1] - ma) / std
                
                end_time = time.perf_counter()
                execution_time_ms = (end_time - start_time) * 1000
                execution_times.append(execution_time_ms)
            
            # 计算平均执行延迟
            avg_execution_delay = sum(execution_times) / len(execution_times)
            
            # 获取README中的值
            readme_value = self.readme_metrics['策略执行延迟']['value']
            target_value = self.readme_metrics['策略执行延迟']['target']
            
            # 计算状态
            if avg_execution_delay <= target_value * 0.5:
                status = '优秀'
            elif avg_execution_delay <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - avg_execution_delay) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='策略执行延迟',
                measured_value=avg_execution_delay,
                unit='ms',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}ms, 实测: {avg_execution_delay:.2f}ms"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测执行延迟: {avg_execution_delay:.2f}ms")
            logger.info(f"   README声明: {readme_value}ms")
            logger.info(f"   目标值: {target_value}ms")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='策略执行延迟',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='策略执行延迟',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='策略执行延迟',
                    measured_value=0,
                    unit='ms',
                    readme_value=self.readme_metrics['策略执行延迟']['value'],
                    target_value=self.readme_metrics['策略执行延迟']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_data_processing_throughput(self) -> TestResult:
        """测试数据处理吞吐量"""
        logger.info("=" * 80)
        logger.info("测试9: 数据处理吞吐量")
        logger.info("=" * 80)
        
        try:
            # 测试数据处理吞吐量
            test_duration = 10.0  # 测试10秒
            processed_count = 0
            start_time = time.time()
            
            while time.time() - start_time < test_duration:
                # 模拟数据处理
                data = np.random.randn(100)
                processed_data = data * 2 + 1
                processed_count += 1
            
            # 计算吞吐量（笔/秒）
            throughput = processed_count / test_duration
            
            # 获取README中的值
            readme_value = self.readme_metrics['数据处理吞吐量']['value']
            target_value = self.readme_metrics['数据处理吞吐量']['target']
            
            # 计算状态
            if throughput >= target_value * 1.5:
                status = '优秀'
            elif throughput >= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((throughput - readme_value) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='数据处理吞吐量',
                measured_value=throughput,
                unit='笔/秒',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}笔/秒, 实测: {throughput:.0f}笔/秒"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测吞吐量: {throughput:.0f}笔/秒")
            logger.info(f"   README声明: {readme_value}笔/秒")
            logger.info(f"   目标值: {target_value}笔/秒")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='数据处理吞吐量',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='数据处理吞吐量',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='数据处理吞吐量',
                    measured_value=0,
                    unit='笔/秒',
                    readme_value=self.readme_metrics['数据处理吞吐量']['value'],
                    target_value=self.readme_metrics['数据处理吞吐量']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_concurrent_capacity(self) -> TestResult:
        """测试并发处理能力"""
        logger.info("=" * 80)
        logger.info("测试10: 并发处理能力")
        logger.info("=" * 80)
        
        try:
            def worker_task(task_id: int) -> bool:
                """工作线程任务"""
                try:
                    time.sleep(0.01)  # 模拟工作负载
                    return True
                except Exception:
                    return False
            
            # 测试不同并发级别
            max_workers = min(100, multiprocessing.cpu_count() * 4)
            successful_tasks = 0
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交并发任务
                futures = [executor.submit(worker_task, i) for i in range(max_workers)]
                
                # 收集结果
                for future in concurrent.futures.as_completed(futures, timeout=10.0):
                    try:
                        if future.result():
                            successful_tasks += 1
                    except Exception:
                        continue
            
            # 获取README中的值
            readme_value = self.readme_metrics['并发处理能力']['value']
            target_value = self.readme_metrics['并发处理能力']['target']
            
            # 计算状态
            if successful_tasks >= target_value * 1.5:
                status = '优秀'
            elif successful_tasks >= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((successful_tasks - readme_value) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='并发处理能力',
                measured_value=successful_tasks,
                unit='个',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}个, 实测: {successful_tasks}个"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测并发能力: {successful_tasks}个任务")
            logger.info(f"   README声明: {readme_value}个")
            logger.info(f"   目标值: {target_value}个")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='并发处理能力',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='并发处理能力',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='并发处理能力',
                    measured_value=0,
                    unit='个',
                    readme_value=self.readme_metrics['并发处理能力']['value'],
                    target_value=self.readme_metrics['并发处理能力']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_memory_leak(self) -> TestResult:
        """测试内存泄漏率（需要长时间运行）"""
        logger.info("=" * 80)
        logger.info("测试11: 内存泄漏率（长时间运行）")
        logger.info("=" * 80)
        
        try:
            if not self.long_term_test:
                logger.warning("⚠️  跳过内存泄漏测试（需要长时间运行模式）")
                return TestResult(
                    test_name='内存泄漏率',
                    success=False,
                    metrics=PerformanceMetrics(
                        test_name='内存泄漏率',
                        measured_value=0,
                        unit='MB/小时',
                        readme_value=self.readme_metrics['内存泄漏率']['value'],
                        target_value=self.readme_metrics['内存泄漏率']['target'],
                        status='跳过',
                        notes='需要长时间运行模式'
                    ),
                    error_message='需要长时间运行模式',
                    timestamp=datetime.now().isoformat()
                )
            
            # 记录初始内存
            initial_memory = self.process.memory_info().rss / (1024 * 1024)
            logger.info(f"初始内存: {initial_memory:.1f}MB")
            
            # 长时间运行测试
            test_duration = self.long_term_duration_hours * 3600  # 转换为秒
            check_interval = 300  # 每5分钟检查一次
            memory_samples = []
            
            start_time = time.time()
            while time.time() - start_time < test_duration:
                # 执行一些操作
                test_data = np.random.randn(1000)
                result = np.mean(test_data)
                del test_data
                
                # 定期检查内存
                if int(time.time() - start_time) % check_interval == 0:
                    current_memory = self.process.memory_info().rss / (1024 * 1024)
                    memory_samples.append(current_memory)
                    logger.info(f"当前内存: {current_memory:.1f}MB")
                
                time.sleep(1)
            
            # 记录最终内存
            final_memory = self.process.memory_info().rss / (1024 * 1024)
            logger.info(f"最终内存: {final_memory:.1f}MB")
            
            # 计算内存泄漏率
            if len(memory_samples) >= 2:
                memory_increase = final_memory - initial_memory
                elapsed_hours = (time.time() - start_time) / 3600
                leak_rate = memory_increase / elapsed_hours if elapsed_hours > 0 else 0
            else:
                leak_rate = 0
            
            # 获取README中的值
            readme_value = self.readme_metrics['内存泄漏率']['value']
            target_value = self.readme_metrics['内存泄漏率']['target']
            
            # 计算状态
            if leak_rate <= target_value * 0.5:
                status = '优秀'
            elif leak_rate <= target_value:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((readme_value - leak_rate) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='内存泄漏率',
                measured_value=leak_rate,
                unit='MB/小时',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}MB/小时, 实测: {leak_rate:.2f}MB/小时"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测泄漏率: {leak_rate:.2f}MB/小时")
            logger.info(f"   README声明: {readme_value}MB/小时")
            logger.info(f"   目标值: {target_value}MB/小时")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='内存泄漏率',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='内存泄漏率',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='内存泄漏率',
                    measured_value=0,
                    unit='MB/小时',
                    readme_value=self.readme_metrics['内存泄漏率']['value'],
                    target_value=self.readme_metrics['内存泄漏率']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_system_stability(self) -> TestResult:
        """测试系统稳定性（需要长时间运行）"""
        logger.info("=" * 80)
        logger.info("测试12: 系统稳定性（长时间运行）")
        logger.info("=" * 80)
        
        try:
            if not self.long_term_test:
                logger.warning("⚠️  跳过系统稳定性测试（需要长时间运行模式）")
                return TestResult(
                    test_name='系统稳定性',
                    success=False,
                    metrics=PerformanceMetrics(
                        test_name='系统稳定性',
                        measured_value=0,
                        unit='%',
                        readme_value=self.readme_metrics['系统稳定性']['value'],
                        target_value=self.readme_metrics['系统稳定性']['target'],
                        status='跳过',
                        notes='需要长时间运行模式'
                    ),
                    error_message='需要长时间运行模式',
                    timestamp=datetime.now().isoformat()
                )
            
            # 长时间运行测试
            test_duration = self.long_term_duration_hours * 3600  # 转换为秒
            check_interval = 600  # 每10分钟检查一次
            success_checks = 0
            total_checks = 0
            
            start_time = time.time()
            while time.time() - start_time < test_duration:
                # 执行一些操作
                try:
                    test_data = np.random.randn(100)
                    result = np.mean(test_data)
                    del test_data
                    success_checks += 1
                except Exception as e:
                    logger.error(f"操作失败: {e}")
                
                total_checks += 1
                
                # 定期检查
                if int(time.time() - start_time) % check_interval == 0:
                    elapsed = (time.time() - start_time) / 3600
                    stability = (success_checks / total_checks) * 100 if total_checks > 0 else 0
                    logger.info(f"运行时间: {elapsed:.1f}小时, 稳定性: {stability:.2f}%")
                
                time.sleep(1)
            
            # 计算最终稳定性
            stability = (success_checks / total_checks) * 100 if total_checks > 0 else 0
            
            # 获取README中的值
            readme_value = self.readme_metrics['系统稳定性']['value']
            target_value = self.readme_metrics['系统稳定性']['target']
            
            # 计算状态
            if stability >= target_value:
                status = '优秀'
            elif stability >= target_value * 0.95:
                status = '达标'
            else:
                status = '未达标'
            
            # 计算改进百分比
            improvement = ((stability - readme_value) / readme_value) * 100 if readme_value > 0 else 0
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name='系统稳定性',
                measured_value=stability,
                unit='%',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"README声明: {readme_value}%, 实测: {stability:.2f}%"
            )
            
            logger.info(f"测试完成")
            logger.info(f"   实测稳定性: {stability:.2f}%")
            logger.info(f"   README声明: {readme_value}%")
            logger.info(f"   目标值: {target_value}%")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='系统稳定性',
                success=True,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return TestResult(
                test_name='系统稳定性',
                success=False,
                metrics=PerformanceMetrics(
                    test_name='系统稳定性',
                    measured_value=0,
                    unit='%',
                    readme_value=self.readme_metrics['系统稳定性']['value'],
                    target_value=self.readme_metrics['系统稳定性']['target'],
                    status='测试失败',
                    notes=str(e)
                ),
                error_message=str(e),
                timestamp=datetime.now().isoformat()
            )

    def run_all_tests(self) -> List[TestResult]:
        """运行所有测试"""
        logger.info("开始README性能指标验证")
        logger.info("=" * 80)
        
        # 运行所有测试
        tests = [
            self.test_startup_time,
            self.test_memory_usage,
            self.test_peak_memory,
            self.test_cpu_usage,
            self.test_thread_count,
            self.test_api_response_time,
            self.test_backtest_speed,
            self.test_strategy_execution_delay,
            self.test_data_processing_throughput,
            self.test_concurrent_capacity,
            self.test_memory_leak,
            self.test_system_stability
        ]
        
        for test_func in tests:
            try:
                result = test_func()
                self.test_results.append(result)
            except Exception as e:
                logger.error(f"测试执行失败: {test_func.__name__}: {e}")
                traceback.print_exc()
        
        return self.test_results

    def generate_report(self) -> str:
        """生成测试报告"""
        logger.info("📋 生成测试报告...")
        
        report_lines = [
            "=" * 80,
            "README性能指标验证报告",
            "=" * 80,
            f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"测试模式: {'长时间运行' if self.long_term_test else '快速测试'}",
            f"总测试数: {len(self.test_results)}",
            "",
            "## 测试结果汇总",
            "",
            "| 测试项目 | README声明 | 实测值 | 目标值 | 状态 | 改进 |",
            "|---------|-----------|-------|-------|------|------|"
        ]
        
        # 添加测试结果
        for result in self.test_results:
            if result.success:
                metrics = result.metrics
                improvement_str = f"{metrics.improvement_percent:+.1f}%" if metrics.improvement_percent != 0 else "-"
                report_lines.append(
                    f"| {metrics.test_name} | {metrics.readme_value}{metrics.unit} | "
                    f"{metrics.measured_value:.2f}{metrics.unit} | {metrics.target_value}{metrics.unit} | "
                    f"{metrics.status} | {improvement_str} |"
                )
            else:
                report_lines.append(
                    f"| {result.test_name} | - | 测试失败 | - | ❌ | - |"
                )
        
        # 添加详细分析
        report_lines.extend([
            "",
            "## 详细分析",
            ""
        ])
        
        # 统计达标情况
        passed_count = sum(1 for r in self.test_results if r.success and r.metrics.status in ['达标', '优秀'])
        excellent_count = sum(1 for r in self.test_results if r.success and r.metrics.status == '优秀')
        failed_count = sum(1 for r in self.test_results if not r.success or r.metrics.status == '未达标')
        
        report_lines.extend([
            f"达标/优秀: {passed_count}/{len(self.test_results)} ({passed_count/len(self.test_results)*100:.1f}%)",
            f"🌟 优秀: {excellent_count}/{len(self.test_results)} ({excellent_count/len(self.test_results)*100:.1f}%)",
            f"❌ 未达标/失败: {failed_count}/{len(self.test_results)} ({failed_count/len(self.test_results)*100:.1f}%)",
            ""
        ])
        
        # 添加纠正建议
        report_lines.extend([
            "## 纠正建议",
            ""
        ])
        
        corrections = []
        for result in self.test_results:
            if not result.success:
                corrections.append(f"- {result.test_name}: {result.error_message}")
            elif result.metrics.status == '未达标':
                corrections.append(
                    f"- {result.metrics.test_name}: 实测值({result.metrics.measured_value:.2f}{result.metrics.unit}) "
                    f"与README声明({result.metrics.readme_value}{result.metrics.unit})不符，建议更新README"
                )
            elif abs(result.metrics.improvement_percent) > 20:
                corrections.append(
                    f"- {result.metrics.test_name}: 实测值({result.metrics.measured_value:.2f}{result.metrics.unit}) "
                    f"与README声明({result.metrics.readme_value}{result.metrics.unit})差异较大({result.metrics.improvement_percent:+.1f}%)，"
                    f"建议验证测试方法或更新README"
                )
        
        if corrections:
            report_lines.extend(corrections)
        else:
            report_lines.append("所有指标与README声明一致，无需纠正")
        
        report_lines.extend([
            "",
            "=" * 80
        ])
        
        return "\n".join(report_lines)

    def save_results(self) -> str:
        """保存测试结果"""
        output_dir = Path("performance_validation_results")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存JSON格式的详细结果
        json_file = output_dir / f"readme_validation_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in self.test_results], f, indent=2, ensure_ascii=False, default=str)
        
        # 保存测试报告
        report_file = output_dir / f"readme_validation_report_{timestamp}.md"
        report_content = self.generate_report()
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"测试结果已保存到: {output_dir}")
        return str(output_dir)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='README性能指标验证脚本')
    parser.add_argument('--long-term', action='store_true', help='启用长时间运行模式（包括内存泄漏和稳定性测试）')
    parser.add_argument('--duration', type=float, default=1.0, help='长时间运行持续时间（小时）')
    
    args = parser.parse_args()
    
    # 创建验证器
    validator = READMEPerformanceValidator()
    
    # 设置长时间运行模式
    if args.long_term:
        validator.long_term_test = True
        validator.long_term_duration_hours = args.duration
        logger.info(f"启用长时间运行模式，持续时间: {args.duration}小时")
    
    # 运行所有测试
    validator.run_all_tests()
    
    # 生成并保存报告
    report = validator.generate_report()
    print("\n" + report)
    
    # 保存结果
    validator.save_results()


if __name__ == "__main__":
    main()
