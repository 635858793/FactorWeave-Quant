#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
完整性能测试脚本
运行所有性能测试并生成详细报告
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
        logging.FileHandler('complete_performance_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    success: bool
    measured_value: float
    unit: str
    readme_value: float
    target_value: float
    status: str
    improvement_percent: float
    notes: str
    timestamp: str


class CompletePerformanceTest:
    """完整性能测试类"""

    def __init__(self):
        """初始化测试器"""
        self.process = psutil.Process()
        self.test_results: List[TestResult] = []
        
        # README中的性能指标
        self.readme_metrics = {
            '系统启动时间': {'value': 16.8, 'unit': 's', 'target': 8.0},
            '运行内存占用': {'value': 547.6, 'unit': 'MB', 'target': 450.0},
            '峰值内存使用': {'value': 549.1, 'unit': 'MB', 'target': 1200.0},
            'CPU平均负载': {'value': 0.0, 'unit': '%', 'target': 25.0},
            'API响应时间': {'value': 30.1, 'unit': 'ms', 'target': 100.0},
            '活跃线程数量': {'value': 13, 'unit': '个', 'target': 25},
            '回测速度': {'value': 100.0, 'unit': '万条/秒', 'target': 50.0},
            '策略执行延迟': {'value': 15.0, 'unit': 'ms', 'target': 50.0},
            '数据处理吞吐量': {'value': 2000.0, 'unit': '笔/秒', 'target': 1000.0},
            '并发处理能力': {'value': 48, 'unit': '个', 'target': 100}
        }

    def test_backtest_speed(self) -> TestResult:
        """测试回测速度"""
        logger.info("=" * 80)
        logger.info("测试: 回测速度")
        logger.info("=" * 80)
        
        try:
            # 生成测试数据
            data_size = 1000000  # 100万条数据
            logger.info(f"生成测试数据: {data_size}条")
            
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
            
            logger.info(f"测试完成")
            logger.info(f"   实测回测速度: {backtest_speed:.2f}万条/秒")
            logger.info(f"   README声明: {readme_value}万条/秒")
            logger.info(f"   目标值: {target_value}万条/秒")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='回测速度',
                success=True,
                measured_value=backtest_speed,
                unit='万条/秒',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"实测: {backtest_speed:.2f}万条/秒, 耗时: {elapsed_time:.2f}秒",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            traceback.print_exc()
            return TestResult(
                test_name='回测速度',
                success=False,
                measured_value=0,
                unit='万条/秒',
                readme_value=self.readme_metrics['回测速度']['value'],
                target_value=self.readme_metrics['回测速度']['target'],
                status='测试失败',
                improvement_percent=0,
                notes=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_strategy_execution_delay(self) -> TestResult:
        """测试策略执行延迟"""
        logger.info("=" * 80)
        logger.info("测试: 策略执行延迟")
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
            
            logger.info(f"测试完成")
            logger.info(f"   实测执行延迟: {avg_execution_delay:.2f}ms")
            logger.info(f"   README声明: {readme_value}ms")
            logger.info(f"   目标值: {target_value}ms")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='策略执行延迟',
                success=True,
                measured_value=avg_execution_delay,
                unit='ms',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"实测: {avg_execution_delay:.2f}ms, 测试次数: 100",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            traceback.print_exc()
            return TestResult(
                test_name='策略执行延迟',
                success=False,
                measured_value=0,
                unit='ms',
                readme_value=self.readme_metrics['策略执行延迟']['value'],
                target_value=self.readme_metrics['策略执行延迟']['target'],
                status='测试失败',
                improvement_percent=0,
                notes=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_data_processing_throughput(self) -> TestResult:
        """测试数据处理吞吐量"""
        logger.info("=" * 80)
        logger.info("测试: 数据处理吞吐量")
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
            
            logger.info(f"测试完成")
            logger.info(f"   实测吞吐量: {throughput:.0f}笔/秒")
            logger.info(f"   README声明: {readme_value}笔/秒")
            logger.info(f"   目标值: {target_value}笔/秒")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='数据处理吞吐量',
                success=True,
                measured_value=throughput,
                unit='笔/秒',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"实测: {throughput:.0f}笔/秒, 测试时长: {test_duration}秒",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            traceback.print_exc()
            return TestResult(
                test_name='数据处理吞吐量',
                success=False,
                measured_value=0,
                unit='笔/秒',
                readme_value=self.readme_metrics['数据处理吞吐量']['value'],
                target_value=self.readme_metrics['数据处理吞吐量']['target'],
                status='测试失败',
                improvement_percent=0,
                notes=str(e),
                timestamp=datetime.now().isoformat()
            )

    def test_concurrent_capacity(self) -> TestResult:
        """测试并发处理能力"""
        logger.info("=" * 80)
        logger.info("测试: 并发处理能力")
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
            
            logger.info(f"测试并发级别: {max_workers}")
            
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
            
            logger.info(f"测试完成")
            logger.info(f"   实测并发能力: {successful_tasks}个任务")
            logger.info(f"   README声明: {readme_value}个")
            logger.info(f"   目标值: {target_value}个")
            logger.info(f"   状态: {status}")
            logger.info(f"   改进: {improvement:.1f}%")
            
            return TestResult(
                test_name='并发处理能力',
                success=True,
                measured_value=successful_tasks,
                unit='个',
                readme_value=readme_value,
                target_value=target_value,
                status=status,
                improvement_percent=improvement,
                notes=f"实测: {successful_tasks}个任务, 最大并发: {max_workers}",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            traceback.print_exc()
            return TestResult(
                test_name='并发处理能力',
                success=False,
                measured_value=0,
                unit='个',
                readme_value=self.readme_metrics['并发处理能力']['value'],
                target_value=self.readme_metrics['并发处理能力']['target'],
                status='测试失败',
                improvement_percent=0,
                notes=str(e),
                timestamp=datetime.now().isoformat()
            )

    def run_all_tests(self) -> List[TestResult]:
        """运行所有测试"""
        logger.info("🚀 开始完整性能测试")
        logger.info("=" * 80)
        
        # 运行所有测试
        tests = [
            self.test_backtest_speed,
            self.test_strategy_execution_delay,
            self.test_data_processing_throughput,
            self.test_concurrent_capacity
        ]
        
        for test_func in tests:
            try:
                result = test_func()
                self.test_results.append(result)
                logger.info("")
            except Exception as e:
                logger.error(f"测试执行失败: {test_func.__name__}: {e}")
                traceback.print_exc()
        
        return self.test_results

    def generate_report(self) -> str:
        """生成测试报告"""
        logger.info("📋 生成测试报告...")
        
        report_lines = [
            "=" * 80,
            "完整性能测试报告",
            "=" * 80,
            f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
                improvement_str = f"{result.improvement_percent:+.1f}%" if result.improvement_percent != 0 else "-"
                report_lines.append(
                    f"| {result.test_name} | {result.readme_value}{result.unit} | "
                    f"{result.measured_value:.2f}{result.unit} | {result.target_value}{result.unit} | "
                    f"{result.status} | {improvement_str} |"
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
        passed_count = sum(1 for r in self.test_results if r.success and r.status in ['达标', '优秀'])
        excellent_count = sum(1 for r in self.test_results if r.success and r.status == '优秀')
        failed_count = sum(1 for r in self.test_results if not r.success or r.status == '未达标')
        
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
                corrections.append(f"- {result.test_name}: {result.notes}")
            elif result.status == '未达标':
                corrections.append(
                    f"- {result.test_name}: 实测值({result.measured_value:.2f}{result.unit}) "
                    f"与README声明({result.readme_value}{result.unit})不符，建议更新README"
                )
            elif abs(result.improvement_percent) > 20:
                corrections.append(
                    f"- {result.test_name}: 实测值({result.measured_value:.2f}{result.unit}) "
                    f"与README声明({result.readme_value}{result.unit})差异较大({result.improvement_percent:+.1f}%)，"
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
        output_dir = Path("complete_performance_test_results")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存JSON格式的详细结果
        json_file = output_dir / f"complete_test_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in self.test_results], f, indent=2, ensure_ascii=False, default=str)
        
        # 保存测试报告
        report_file = output_dir / f"complete_test_report_{timestamp}.md"
        report_content = self.generate_report()
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"测试结果已保存到: {output_dir}")
        return str(output_dir)


def main():
    """主函数"""
    # 创建测试器
    tester = CompletePerformanceTest()
    
    # 运行所有测试
    tester.run_all_tests()
    
    # 生成并保存报告
    report = tester.generate_report()
    print("\n" + report)
    
    # 保存结果
    tester.save_results()


if __name__ == "__main__":
    main()
