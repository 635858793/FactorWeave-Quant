#!/usr/bin/env python3
"""
架构性能优化器测试脚本

测试ArchitecturePerformanceOptimizer的实际效果，包括：
1. 性能指标收集
2. 性能优化执行
3. 性能目标验证
4. 性能报告生成
"""

import sys
import time
import json
import traceback
from pathlib import Path
from loguru import logger
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")

from optimization.architecture_performance_optimizer import (
    ArchitecturePerformanceOptimizer,
    PerformanceTarget,
    PerformanceResult,
    OptimizationResult
)


def test_architecture_performance_optimizer():
    """测试架构性能优化器"""
    logger.info("=" * 80)
    logger.info("架构性能优化器测试")
    logger.info("=" * 80)
    
    # 初始化变量
    optimizer = None
    metrics = {}
    optimization_results = []
    validation_results = []
    report = ""
    
    # 测试1：初始化优化器
    logger.info("\n" + "=" * 80)
    logger.info("测试1：初始化优化器")
    logger.info("=" * 80)
    
    try:
        start_time = time.time()
        optimizer = ArchitecturePerformanceOptimizer(project_root)
        init_time = time.time() - start_time
        
        logger.info(f"\n优化器初始化时间：{init_time:.4f}秒")
        logger.info(f"项目根目录：{optimizer.project_root}")
        logger.info(f"性能目标数量：{len(optimizer.performance_targets)}")
        logger.info(f"性能目标列表：")
        for target_name, target in optimizer.performance_targets.items():
            critical = "关键" if target.critical else "可选"
            logger.info(f"  - {target.name}: {target.target_value} {target.unit} ({critical})")
        
    except Exception as e:
        logger.error(f"优化器初始化失败：{e}")
        logger.error(traceback.format_exc())
        return
    
    # 测试2：收集性能指标
    logger.info("\n" + "=" * 80)
    logger.info("测试2：收集性能指标")
    logger.info("=" * 80)
    
    try:
        start_time = time.time()
        metrics = optimizer.collect_current_performance_metrics()
        collection_time = time.time() - start_time
        
        logger.info(f"\n性能指标收集时间：{collection_time:.4f}秒")
        
        if 'collection_time' in metrics:
            logger.info(f"指标收集时间：{metrics['collection_time']}")
        
        if 'system_info' in metrics:
            sys_info = metrics['system_info']
            logger.info(f"\n系统信息：")
            logger.info(f"  CPU核心数：{sys_info.get('cpu_count', 'N/A')}")
            logger.info(f"  总内存：{sys_info.get('memory_total', 'N/A'):.2f}GB")
            logger.info(f"  Python版本：{sys_info.get('python_version', 'N/A')}")
            logger.info(f"  平台：{sys_info.get('platform', 'N/A')}")
        
        if 'startup_metrics' in metrics:
            startup_metrics = metrics['startup_metrics']
            logger.info(f"\n启动性能指标：")
            logger.info(f"  总导入时间：{startup_metrics.get('total_import_time', 'N/A'):.4f}秒")
            logger.info(f"  容器初始化时间：{startup_metrics.get('container_init_time', 'N/A'):.4f}秒")
            logger.info(f"  引导时间：{startup_metrics.get('bootstrap_time', 'N/A'):.4f}秒")
            logger.info(f"  总启动时间：{startup_metrics.get('total_startup_time', 'N/A'):.4f}秒")
        
        if 'memory_metrics' in metrics:
            memory_metrics = metrics['memory_metrics']
            logger.info(f"\n内存使用指标：")
            logger.info(f"  RSS内存：{memory_metrics.get('rss_mb', 'N/A'):.2f}MB")
            logger.info(f"  VMS内存：{memory_metrics.get('vms_mb', 'N/A'):.2f}MB")
            logger.info(f"  内存百分比：{memory_metrics.get('percent', 'N/A'):.2f}%")
            logger.info(f"  可用内存：{memory_metrics.get('available_mb', 'N/A'):.2f}MB")
        
        if 'service_metrics' in metrics:
            service_metrics = metrics['service_metrics']
            logger.info(f"\n服务性能指标：")
            if 'resolution_times' in service_metrics:
                logger.info(f"  服务解析时间：")
                for service_name, times in service_metrics['resolution_times'].items():
                    logger.info(f"    {service_name}:")
                    logger.info(f"      平均：{times['average']:.4f}秒")
                    logger.info(f"      最小：{times['min']:.4f}秒")
                    logger.info(f"      最大：{times['max']:.4f}秒")
        
        if 'architecture_metrics' in metrics:
            arch_metrics = metrics['architecture_metrics']
            logger.info(f"\n架构指标：")
            logger.info(f"  服务数量：{arch_metrics.get('service_count', 'N/A')}")
            logger.info(f"  Manager数量：{arch_metrics.get('manager_count', 'N/A')}")
            logger.info(f"  复杂度分数：{arch_metrics.get('complexity_score', 'N/A'):.2f}")
        
    except Exception as e:
        logger.error(f"性能指标收集失败：{e}")
        logger.error(traceback.format_exc())
    
    # 测试3：运行性能优化
    logger.info("\n" + "=" * 80)
    logger.info("测试3：运行性能优化")
    logger.info("=" * 80)
    
    try:
        start_time = time.time()
        optimization_results = optimizer.run_performance_optimizations()
        optimization_time = time.time() - start_time
        
        logger.info(f"\n性能优化执行时间：{optimization_time:.4f}秒")
        logger.info(f"执行的优化数量：{len(optimization_results)}")
        
        if optimization_results:
            logger.info(f"\n优化结果：")
            for result in optimization_results:
                logger.info(f"\n{result.optimization_name}:")
                logger.info(f"  优化前：{result.before_value:.4f}")
                logger.info(f"  优化后：{result.after_value:.4f}")
                logger.info(f"  改进百分比：{result.improvement_percent:.2f}%")
                logger.info(f"  成功：{result.success}")
                logger.info(f"  描述：{result.description}")
        else:
            logger.warning("没有执行任何优化")
        
    except Exception as e:
        logger.error(f"性能优化执行失败：{e}")
        logger.error(traceback.format_exc())
    
    # 测试4：验证性能目标
    logger.info("\n" + "=" * 80)
    logger.info("测试4：验证性能目标")
    logger.info("=" * 80)
    
    try:
        start_time = time.time()
        validation_results = optimizer.validate_performance_targets()
        validation_time = time.time() - start_time
        
        logger.info(f"\n性能目标验证时间：{validation_time:.4f}秒")
        
        if validation_results:
            logger.info(f"\n验证结果：")
            passed_count = 0
            failed_count = 0
            for result in validation_results:
                status = "✅ 通过" if result.passed else "❌ 失败"
                logger.info(f"\n{result.name}: {status}")
                logger.info(f"  目标值：{result.target_value:.2f} {result.unit}")
                logger.info(f"  测量值：{result.measured_value:.2f} {result.unit}")
                
                if result.passed:
                    passed_count += 1
                else:
                    failed_count += 1
            
            logger.info(f"\n总计：{passed_count}个通过，{failed_count}个失败")
        else:
            logger.warning("没有验证结果")
        
    except Exception as e:
        logger.error(f"性能目标验证失败：{e}")
        logger.error(traceback.format_exc())
    
    # 测试5：生成性能报告
    logger.info("\n" + "=" * 80)
    logger.info("测试5：生成性能报告")
    logger.info("=" * 80)
    
    try:
        start_time = time.time()
        report = optimizer.generate_performance_report()
        report_time = time.time() - start_time
        
        logger.info(f"\n性能报告生成时间：{report_time:.4f}秒")
        logger.info(f"\n性能报告：")
        logger.info(report)
        
    except Exception as e:
        logger.error(f"性能报告生成失败：{e}")
        logger.error(traceback.format_exc())
    
    # 测试6：保存性能报告
    logger.info("\n" + "=" * 80)
    logger.info("测试6：保存性能报告")
    logger.info("=" * 80)
    
    try:
        report_file = project_root / "ARCHITECTURE_PERFORMANCE_OPTIMIZER_TEST_REPORT.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"\n性能报告已保存到：{report_file}")
        
    except Exception as e:
        logger.error(f"性能报告保存失败：{e}")
        logger.error(traceback.format_exc())
    
    # 测试7：运行完整性能分析
    logger.info("\n" + "=" * 80)
    logger.info("测试7：运行完整性能分析")
    logger.info("=" * 80)
    
    try:
        start_time = time.time()
        result = optimizer.run_complete_performance_analysis()
        analysis_time = time.time() - start_time
        
        logger.info(f"\n完整性能分析时间：{analysis_time:.4f}秒")
        
        if result:
            logger.info(f"\n分析结果：")
            logger.info(f"  成功：{result.get('success', False)}")
            
            if 'summary' in result:
                summary = result['summary']
                logger.info(f"\n  总结：")
                logger.info(f"    关键目标通过数：{summary.get('critical_targets_passed', 0)}/{summary.get('total_critical_targets', 0)}")
                logger.info(f"    总体通过率：{summary.get('overall_pass_rate', 0):.1f}%")
                logger.info(f"    性能分数：{summary.get('performance_score', 0):.1f}/100")
            
            if 'recommendations' in result:
                recommendations = result['recommendations']
                logger.info(f"\n  建议：")
                for recommendation in recommendations:
                    logger.info(f"    - {recommendation}")
        else:
            logger.warning("没有分析结果")
        
    except Exception as e:
        logger.error(f"完整性能分析失败：{e}")
        logger.error(traceback.format_exc())
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("架构性能优化器测试总结")
    logger.info("=" * 80)
    
    logger.info("\n测试结果：")
    logger.info(f"  优化器初始化时间：{init_time:.4f}秒")
    logger.info(f"  性能指标收集时间：{collection_time:.4f}秒")
    logger.info(f"  性能优化执行时间：{optimization_time:.4f}秒")
    logger.info(f"  性能目标验证时间：{validation_time:.4f}秒")
    logger.info(f"  性能报告生成时间：{report_time:.4f}秒")
    logger.info(f"  完整性能分析时间：{analysis_time:.4f}秒")
    
    logger.info("\n性能指标：")
    if 'startup_metrics' in metrics:
        startup_time = metrics['startup_metrics'].get('total_startup_time', 0)
        logger.info(f"  启动时间：{startup_time:.4f}秒")
    
    if 'memory_metrics' in metrics:
        memory_usage = metrics['memory_metrics'].get('rss_mb', 0)
        logger.info(f"  内存使用：{memory_usage:.2f}MB")
    
    logger.info("\n优化结果：")
    if optimization_results:
        total_improvement = sum(r.improvement_percent for r in optimization_results)
        logger.info(f"  执行的优化数量：{len(optimization_results)}")
        logger.info(f"  总改进百分比：{total_improvement:.2f}%")
        logger.info(f"  平均改进百分比：{total_improvement / len(optimization_results):.2f}%")
    
    logger.info("\n验证结果：")
    if validation_results:
        passed_count = sum(1 for r in validation_results if r.passed)
        failed_count = sum(1 for r in validation_results if not r.passed)
        logger.info(f"  通过的目标数量：{passed_count}")
        logger.info(f"  失败的目标数量：{failed_count}")
        logger.info(f"  通过率：{passed_count / len(validation_results) * 100:.1f}%")
    
    logger.info("\n测试完成！")


if __name__ == "__main__":
    try:
        test_architecture_performance_optimizer()
    except Exception as e:
        logger.error(f"测试失败：{e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
