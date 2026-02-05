"""
性能基准测试脚本
测试性能基准测试的实际效果
"""

import time
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 添加tests目录到Python路径
tests_dir = project_root / 'tests'
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from performance.performance_baseline_test import PerformanceBaselineTest
from loguru import logger

def test_performance_baseline():
    """测试性能基准测试"""
    logger.info("=" * 80)
    logger.info("性能基准测试")
    logger.info("=" * 80)
    
    # 创建性能基线测试实例
    baseline_test = PerformanceBaselineTest()
    
    # 运行性能基准测试
    logger.info("\n运行性能基准测试...")
    result = baseline_test.run_performance_benchmark()
    
    # 生成性能报告
    logger.info("\n" + "=" * 80)
    logger.info("性能基准测试报告")
    logger.info("=" * 80)
    
    report = baseline_test.generate_performance_report(result)
    logger.info(report)
    
    # 保存报告到文件
    report_file = Path(__file__).parent / 'PERFORMANCE_BASELINE_TEST_REPORT.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"\n报告已保存到：{report_file}")
    
    # 分析结果
    logger.info("\n" + "=" * 80)
    logger.info("性能基准测试分析")
    logger.info("=" * 80)
    
    logger.info("\n当前性能指标：")
    logger.info(f"  启动时间：{result.current_metrics.startup_time:.2f}秒")
    logger.info(f"  内存使用：{result.current_metrics.memory_usage_mb:.1f}MB")
    logger.info(f"  峰值内存：{result.current_metrics.memory_peak_mb:.1f}MB")
    logger.info(f"  CPU使用率：{result.current_metrics.cpu_usage_percent:.1f}%")
    logger.info(f"  响应时间：{result.current_metrics.response_time_ms:.2f}ms")
    logger.info(f"  并发能力：{result.current_metrics.concurrent_capacity}个任务")
    logger.info(f"  线程数量：{result.current_metrics.thread_count}个")
    
    logger.info("\n相对历史基线的改进：")
    if result.improvement_percent:
        for metric, improvement in result.improvement_percent.items():
            direction = "提升" if improvement > 0 else "退步"
            logger.info(f"  {metric}：{direction} {abs(improvement):.1f}%")
    
    logger.info("\n性能目标达成情况：")
    logger.info(f"  整体目标：{'[达成]' if result.meets_target else '[未达成]'}")
    logger.info(f"  目标描述：{result.target_description}")
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)
    
    return result

if __name__ == "__main__":
    test_performance_baseline()
