#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法优化器监控脚本

监控AlgorithmOptimizer在生产环境中的表现，包括：
1. 监控优化器的性能
2. 记录优化结果
3. 分析性能趋势
4. 检测异常情况
5. 生成报告
"""

import sys
import os
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from collections import defaultdict, deque

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")


class OptimizationMonitor:
    """优化器监控类"""
    
    def __init__(self, max_history=1000):
        """初始化监控器
        
        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history
        self.optimization_history = deque(maxlen=max_history)
        self.performance_history = defaultdict(lambda: deque(maxlen=100))
        self.anomaly_history = deque(maxlen=100)
        self.lock = threading.Lock()
        
        # 性能基准
        self.performance_baselines = {
            'genetic': {'avg_improvement': 15.0, 'avg_time': 20.0},
            'bayesian': {'avg_improvement': 10.0, 'avg_time': 5.0},
            'random': {'avg_improvement': 12.0, 'avg_time': 5.0},
            'gradient': {'avg_improvement': 10.0, 'avg_time': 40.0}
        }
        
        # 异常阈值
        self.anomaly_thresholds = {
            'min_improvement': -5.0,  # 最小性能提升
            'max_time': 300.0,  # 最大优化时间（秒）
            'min_success_rate': 0.8  # 最小成功率
        }
        
        logger.info("优化器监控器初始化成功")
    
    def record_optimization(self, result: Dict[str, Any]):
        """记录优化结果
        
        Args:
            result: 优化结果字典
        """
        with self.lock:
            # 添加时间戳
            result['timestamp'] = datetime.now().isoformat()
            
            # 添加到历史记录
            self.optimization_history.append(result)
            
            # 更新性能历史
            method = result.get('method', 'unknown')
            if method in self.performance_baselines:
                improvement = result.get('improvement_percentage', 0)
                optimization_time = result.get('optimization_time', 0)
                
                self.performance_history[method].append({
                    'timestamp': result['timestamp'],
                    'improvement': improvement,
                    'time': optimization_time
                })
            
            # 检测异常
            self._check_anomalies(result)
            
            logger.info(f"记录优化结果: {method}, 性能提升: {result.get('improvement_percentage', 0):.3f}%")
    
    def _check_anomalies(self, result: Dict[str, Any]):
        """检测异常情况
        
        Args:
            result: 优化结果字典
        """
        anomalies = []
        
        # 检查性能提升
        improvement = result.get('improvement_percentage', 0)
        if improvement < self.anomaly_thresholds['min_improvement']:
            anomalies.append({
                'type': 'low_improvement',
                'value': improvement,
                'threshold': self.anomaly_thresholds['min_improvement'],
                'message': f"性能提升过低: {improvement:.3f}% < {self.anomaly_thresholds['min_improvement']:.3f}%"
            })
        
        # 检查优化时间
        optimization_time = result.get('optimization_time', 0)
        if optimization_time > self.anomaly_thresholds['max_time']:
            anomalies.append({
                'type': 'high_time',
                'value': optimization_time,
                'threshold': self.anomaly_thresholds['max_time'],
                'message': f"优化时间过长: {optimization_time:.3f}s > {self.anomaly_thresholds['max_time']:.3f}s"
            })
        
        # 检查成功率
        method = result.get('method', 'unknown')
        if method in self.performance_history:
            history = list(self.performance_history[method])
            if len(history) >= 10:
                success_count = sum(1 for h in history if h.get('improvement', 0) > 0)
                success_rate = success_count / len(history)
                
                if success_rate < self.anomaly_thresholds['min_success_rate']:
                    anomalies.append({
                        'type': 'low_success_rate',
                        'value': success_rate,
                        'threshold': self.anomaly_thresholds['min_success_rate'],
                        'message': f"成功率过低: {success_rate:.3f} < {self.anomaly_thresholds['min_success_rate']:.3f}"
                    })
        
        # 记录异常
        if anomalies:
            for anomaly in anomalies:
                anomaly['timestamp'] = result['timestamp']
                anomaly['method'] = method
                self.anomaly_history.append(anomaly)
                logger.warning(f"检测到异常: {anomaly['message']}")
    
    def get_performance_summary(self, method: Optional[str] = None) -> Dict[str, Any]:
        """获取性能摘要
        
        Args:
            method: 优化方法，如果为None则返回所有方法的摘要
            
        Returns:
            性能摘要字典
        """
        with self.lock:
            if method:
                if method not in self.performance_history:
                    return {}
                
                history = list(self.performance_history[method])
                if not history:
                    return {}
                
                improvements = [h.get('improvement', 0) for h in history]
                times = [h.get('time', 0) for h in history]
                
                return {
                    'method': method,
                    'count': len(history),
                    'avg_improvement': np.mean(improvements),
                    'std_improvement': np.std(improvements),
                    'min_improvement': np.min(improvements),
                    'max_improvement': np.max(improvements),
                    'avg_time': np.mean(times),
                    'std_time': np.std(times),
                    'min_time': np.min(times),
                    'max_time': np.max(times)
                }
            else:
                summary = {}
                for method in self.performance_history.keys():
                    summary[method] = self.get_performance_summary(method)
                return summary
    
    def get_anomaly_summary(self) -> Dict[str, Any]:
        """获取异常摘要
        
        Returns:
            异常摘要字典
        """
        with self.lock:
            if not self.anomaly_history:
                return {}
            
            anomalies = list(self.anomaly_history)
            
            # 按类型分组
            by_type = defaultdict(list)
            for anomaly in anomalies:
                by_type[anomaly['type']].append(anomaly)
            
            # 按方法分组
            by_method = defaultdict(list)
            for anomaly in anomalies:
                by_method[anomaly.get('method', 'unknown')].append(anomaly)
            
            return {
                'total_count': len(anomalies),
                'by_type': {k: len(v) for k, v in by_type.items()},
                'by_method': {k: len(v) for k, v in by_method.items()},
                'recent_anomalies': anomalies[-10:] if len(anomalies) > 10 else anomalies
            }
    
    def generate_report(self, output_file: str = "optimization_monitor_report.json"):
        """生成监控报告
        
        Args:
            output_file: 输出文件路径
        """
        with self.lock:
            report = {
                'report_time': datetime.now().isoformat(),
                'total_optimizations': len(self.optimization_history),
                'performance_summary': self.get_performance_summary(),
                'anomaly_summary': self.get_anomaly_summary(),
                'recent_optimizations': list(self.optimization_history)[-20:] if len(self.optimization_history) > 20 else list(self.optimization_history)
            }
            
            # 保存报告
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"监控报告已保存到：{output_file}")
            
            # 打印摘要
            self._print_summary(report)
            
            return report
    
    def _print_summary(self, report: Dict[str, Any]):
        """打印摘要
        
        Args:
            report: 报告字典
        """
        logger.info("\n" + "=" * 80)
        logger.info("优化器监控报告")
        logger.info("=" * 80)
        
        logger.info(f"\n总优化次数: {report['total_optimizations']}")
        
        # 性能摘要
        logger.info("\n性能摘要:")
        for method, summary in report['performance_summary'].items():
            if summary:
                logger.info(f"  {method}:")
                logger.info(f"    优化次数: {summary['count']}")
                logger.info(f"    平均性能提升: {summary['avg_improvement']:.3f}%")
                logger.info(f"    平均优化时间: {summary['avg_time']:.3f}秒")
        
        # 异常摘要
        anomaly_summary = report['anomaly_summary']
        if anomaly_summary:
            logger.info(f"\n异常摘要:")
            logger.info(f"  总异常次数: {anomaly_summary['total_count']}")
            logger.info(f"  按类型分组: {anomaly_summary['by_type']}")
            logger.info(f"  按方法分组: {anomaly_summary['by_method']}")
        
        logger.info("\n" + "=" * 80)
    
    def clear_history(self):
        """清空历史记录"""
        with self.lock:
            self.optimization_history.clear()
            self.performance_history.clear()
            self.anomaly_history.clear()
            logger.info("历史记录已清空")


def simulate_optimization(monitor: OptimizationMonitor, method: str, pattern: str = "hammer"):
    """模拟优化过程
    
    Args:
        monitor: 监控器
        method: 优化方法
        pattern: 形态名称
    """
    # 模拟优化结果
    np.random.seed(int(time.time()))
    
    # 基于性能基准生成随机结果
    baseline = monitor.performance_baselines.get(method, {'avg_improvement': 10.0, 'avg_time': 10.0})
    
    # 添加随机变化
    improvement = np.random.normal(baseline['avg_improvement'], 5.0)
    optimization_time = np.random.normal(baseline['avg_time'], 2.0)
    
    # 确保时间为正数
    optimization_time = max(1.0, optimization_time)
    
    # 模拟结果
    result = {
        'method': method,
        'pattern': pattern,
        'success': improvement > 0,
        'best_score': 0.3 + improvement / 100.0,
        'baseline_score': 0.3,
        'improvement_percentage': improvement,
        'iterations': np.random.randint(3, 10),
        'optimization_time': optimization_time
    }
    
    # 记录优化结果
    monitor.record_optimization(result)
    
    return result


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("算法优化器监控测试")
    logger.info("=" * 80)
    
    # 创建监控器
    monitor = OptimizationMonitor(max_history=1000)
    
    # 模拟优化过程
    logger.info("\n模拟优化过程...")
    
    methods = ['genetic', 'bayesian', 'random', 'gradient']
    patterns = ['hammer', 'doji']
    
    # 模拟50次优化
    for i in range(50):
        method = np.random.choice(methods)
        pattern = np.random.choice(patterns)
        
        result = simulate_optimization(monitor, method, pattern)
        
        # 每10次优化生成一次报告
        if (i + 1) % 10 == 0:
            logger.info(f"\n已完成 {i + 1} 次优化")
            monitor.generate_report(f"optimization_monitor_report_{i + 1}.json")
        
        # 模拟优化时间
        time.sleep(0.1)
    
    # 生成最终报告
    logger.info("\n生成最终报告...")
    monitor.generate_report("optimization_monitor_report_final.json")
    
    logger.info("\n" + "=" * 80)
    logger.info("监控测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
