#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法优化器性能分析脚本

分析AlgorithmOptimizer的性能，包括：
1. 性能指标分析
2. 优化方法对比
3. 参数敏感性分析
4. 收敛性分析
5. 可视化报告
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import seaborn as sns

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self, data_file: str = "ALGORITHM_OPTIMIZER_TEST_REPORT.json"):
        """初始化分析器
        
        Args:
            data_file: 数据文件路径
        """
        self.data_file = data_file
        self.data = self._load_data()
        logger.info(f"性能分析器初始化成功，加载了 {len(self.data)} 条记录")
    
    def _load_data(self) -> List[Dict]:
        """加载数据
        
        Returns:
            数据列表
        """
        if not os.path.exists(self.data_file):
            logger.warning(f"数据文件不存在: {self.data_file}")
            return []
        
        with open(self.data_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        return report.get('test_results', [])
    
    def analyze_performance_metrics(self) -> Dict[str, Any]:
        """分析性能指标
        
        Returns:
            性能指标分析结果
        """
        if not self.data:
            return {}
        
        # 转换为DataFrame
        df = pd.DataFrame(self.data)
        
        # 只分析成功的优化
        df_success = df[df['success'] == True]
        
        if df_success.empty:
            return {}
        
        # 计算性能指标
        metrics = {
            'total_count': len(df),
            'success_count': len(df_success),
            'success_rate': len(df_success) / len(df) if len(df) > 0 else 0,
            'avg_improvement': df_success['improvement_percentage'].mean(),
            'std_improvement': df_success['improvement_percentage'].std(),
            'min_improvement': df_success['improvement_percentage'].min(),
            'max_improvement': df_success['improvement_percentage'].max(),
            'avg_time': df_success['optimization_time'].mean(),
            'std_time': df_success['optimization_time'].std(),
            'min_time': df_success['optimization_time'].min(),
            'max_time': df_success['optimization_time'].max()
        }
        
        logger.info(f"性能指标分析:")
        logger.info(f"  总优化次数: {metrics['total_count']}")
        logger.info(f"  成功次数: {metrics['success_count']}")
        logger.info(f"  成功率: {metrics['success_rate']:.3f}")
        logger.info(f"  平均性能提升: {metrics['avg_improvement']:.3f}%")
        logger.info(f"  平均优化时间: {metrics['avg_time']:.3f}秒")
        
        return metrics
    
    def compare_optimization_methods(self) -> Dict[str, Any]:
        """对比优化方法
        
        Returns:
            优化方法对比结果
        """
        if not self.data:
            return {}
        
        # 转换为DataFrame
        df = pd.DataFrame(self.data)
        
        # 只分析成功的优化
        df_success = df[df['success'] == True]
        
        if df_success.empty:
            return {}
        
        # 按方法分组
        methods = df_success.groupby('method')
        
        comparison = {}
        for method, group in methods:
            comparison[method] = {
                'count': len(group),
                'avg_improvement': group['improvement_percentage'].mean(),
                'std_improvement': group['improvement_percentage'].std(),
                'min_improvement': group['improvement_percentage'].min(),
                'max_improvement': group['improvement_percentage'].max(),
                'avg_time': group['optimization_time'].mean(),
                'std_time': group['optimization_time'].std(),
                'min_time': group['optimization_time'].min(),
                'max_time': group['optimization_time'].max()
            }
            
            logger.info(f"{method} 优化方法:")
            logger.info(f"  优化次数: {comparison[method]['count']}")
            logger.info(f"  平均性能提升: {comparison[method]['avg_improvement']:.3f}%")
            logger.info(f"  平均优化时间: {comparison[method]['avg_time']:.3f}秒")
        
        return comparison
    
    def analyze_parameter_sensitivity(self) -> Dict[str, Any]:
        """分析参数敏感性
        
        Returns:
            参数敏感性分析结果
        """
        if not self.data:
            return {}
        
        # 转换为DataFrame
        df = pd.DataFrame(self.data)
        
        # 只分析成功的优化
        df_success = df[df['success'] == True]
        
        if df_success.empty:
            return {}
        
        # 分析迭代次数对性能的影响
        if 'iterations' in df_success.columns:
            iterations_groups = df_success.groupby('iterations')
            
            sensitivity = {}
            for iterations, group in iterations_groups:
                sensitivity[iterations] = {
                    'count': len(group),
                    'avg_improvement': group['improvement_percentage'].mean(),
                    'std_improvement': group['improvement_percentage'].std(),
                    'avg_time': group['optimization_time'].mean()
                }
                
                logger.info(f"迭代次数 {iterations}:")
                logger.info(f"  优化次数: {sensitivity[iterations]['count']}")
                logger.info(f"  平均性能提升: {sensitivity[iterations]['avg_improvement']:.3f}%")
                logger.info(f"  平均优化时间: {sensitivity[iterations]['avg_time']:.3f}秒")
            
            return sensitivity
        
        return {}
    
    def visualize_performance(self, output_dir: str = "performance_analysis"):
        """可视化性能
        
        Args:
            output_dir: 输出目录
        """
        if not self.data:
            logger.warning("没有数据可用于可视化")
            return
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 转换为DataFrame
        df = pd.DataFrame(self.data)
        
        # 只分析成功的优化
        df_success = df[df['success'] == True]
        
        if df_success.empty:
            logger.warning("没有成功的优化可用于可视化")
            return
        
        # 设置图表风格
        sns.set_style("whitegrid")
        
        # 1. 性能提升对比
        plt.figure(figsize=(12, 6))
        sns.boxplot(data=df_success, x='method', y='improvement_percentage')
        plt.title('优化方法性能提升对比')
        plt.xlabel('优化方法')
        plt.ylabel('性能提升 (%)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'improvement_comparison.png'), dpi=300)
        plt.close()
        
        # 2. 优化时间对比
        plt.figure(figsize=(12, 6))
        sns.boxplot(data=df_success, x='method', y='optimization_time')
        plt.title('优化方法时间对比')
        plt.xlabel('优化方法')
        plt.ylabel('优化时间 (秒)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'time_comparison.png'), dpi=300)
        plt.close()
        
        # 3. 性能提升 vs 优化时间
        plt.figure(figsize=(12, 6))
        sns.scatterplot(data=df_success, x='optimization_time', y='improvement_percentage', hue='method', s=100)
        plt.title('性能提升 vs 优化时间')
        plt.xlabel('优化时间 (秒)')
        plt.ylabel('性能提升 (%)')
        plt.legend(title='优化方法')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'improvement_vs_time.png'), dpi=300)
        plt.close()
        
        # 4. 迭代次数 vs 性能提升
        if 'iterations' in df_success.columns:
            plt.figure(figsize=(12, 6))
            sns.boxplot(data=df_success, x='iterations', y='improvement_percentage')
            plt.title('迭代次数 vs 性能提升')
            plt.xlabel('迭代次数')
            plt.ylabel('性能提升 (%)')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'iterations_vs_improvement.png'), dpi=300)
            plt.close()
        
        logger.info(f"可视化图表已保存到：{output_dir}")
    
    def generate_report(self, output_file: str = "performance_analysis_report.json"):
        """生成分析报告
        
        Args:
            output_file: 输出文件路径
        """
        report = {
            'report_time': datetime.now().isoformat(),
            'data_file': self.data_file,
            'performance_metrics': self.analyze_performance_metrics(),
            'method_comparison': self.compare_optimization_methods(),
            'parameter_sensitivity': self.analyze_parameter_sensitivity()
        }
        
        # 保存报告
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"分析报告已保存到：{output_file}")
        
        # 生成可视化
        output_dir = os.path.splitext(output_file)[0]
        self.visualize_performance(output_dir)
        
        return report


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("算法优化器性能分析")
    logger.info("=" * 80)
    
    # 创建分析器
    analyzer = PerformanceAnalyzer()
    
    # 分析性能指标
    logger.info("\n分析性能指标...")
    metrics = analyzer.analyze_performance_metrics()
    
    # 对比优化方法
    logger.info("\n对比优化方法...")
    comparison = analyzer.compare_optimization_methods()
    
    # 分析参数敏感性
    logger.info("\n分析参数敏感性...")
    sensitivity = analyzer.analyze_parameter_sensitivity()
    
    # 生成报告
    logger.info("\n生成分析报告...")
    report = analyzer.generate_report()
    
    logger.info("\n" + "=" * 80)
    logger.info("分析完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
