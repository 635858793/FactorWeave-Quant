"""
完善监控和分析系统
- 实时监控
- 预警功能
- 自动化报告生成
- 性能预测
"""

import sys
import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import deque, defaultdict
import json
import threading
import time
import warnings

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PerformancePredictor:
    """性能预测器"""
    
    def __init__(self, window_size=20):
        self.window_size = window_size
        self.history = defaultdict(lambda: deque(maxlen=window_size))
        
    def add_observation(self, method: str, improvement: float, time: float):
        """添加观测数据
        
        Args:
            method: 优化方法
            improvement: 性能提升
            time: 优化时间
        """
        self.history[method].append({
            'improvement': improvement,
            'time': time,
            'timestamp': datetime.now()
        })
    
    def predict_improvement(self, method: str, iterations: int) -> float:
        """预测性能提升
        
        Args:
            method: 优化方法
            iterations: 迭代次数
            
        Returns:
            预测的性能提升
        """
        if method not in self.history or len(self.history[method]) < 3:
            return 0.0
        
        # 获取历史数据
        data = list(self.history[method])
        
        # 计算平均性能提升
        avg_improvement = np.mean([d['improvement'] for d in data])
        
        # 计算性能提升与迭代次数的关系
        # 假设性能提升与迭代次数的对数成正比
        base_iterations = 10  # 基准迭代次数
        predicted_improvement = avg_improvement * np.log(iterations) / np.log(base_iterations)
        
        return predicted_improvement
    
    def predict_time(self, method: str, iterations: int) -> float:
        """预测优化时间
        
        Args:
            method: 优化方法
            iterations: 迭代次数
            
        Returns:
            预测的优化时间
        """
        if method not in self.history or len(self.history[method]) < 3:
            return 0.0
        
        # 获取历史数据
        data = list(self.history[method])
        
        # 计算平均时间
        avg_time = np.mean([d['time'] for d in data])
        
        # 假设时间与迭代次数成正比
        base_iterations = 10  # 基准迭代次数
        predicted_time = avg_time * iterations / base_iterations
        
        return predicted_time


class AlertManager:
    """预警管理器"""
    
    def __init__(self):
        self.alerts = deque(maxlen=100)
        self.alert_thresholds = {
            'low_improvement': -5.0,  # 性能提升过低
            'high_time': 300.0,  # 优化时间过长（秒）
            'low_success_rate': 0.8,  # 成功率过低
            'high_failure_rate': 0.2,  # 失败率过高
            'stagnation': 5  # 连续无改善次数
        }
        
        # 统计数据
        self.stats = defaultdict(lambda: {
            'total': 0,
            'success': 0,
            'failure': 0,
            'consecutive_no_improvement': 0
        })
    
    def check_alerts(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查预警
        
        Args:
            result: 优化结果
            
        Returns:
            预警列表
        """
        alerts = []
        method = result.get('method', 'unknown')
        
        # 更新统计数据
        self.stats[method]['total'] += 1
        if result.get('success', False):
            self.stats[method]['success'] += 1
            improvement = result.get('improvement_percentage', 0)
            if improvement <= 0:
                self.stats[method]['consecutive_no_improvement'] += 1
            else:
                self.stats[method]['consecutive_no_improvement'] = 0
        else:
            self.stats[method]['failure'] += 1
        
        # 检查性能提升过低
        if result.get('success', False):
            improvement = result.get('improvement_percentage', 0)
            if improvement < self.alert_thresholds['low_improvement']:
                alert = {
                    'type': 'low_improvement',
                    'severity': 'warning',
                    'method': method,
                    'message': f"性能提升过低: {improvement:.3f}% < {self.alert_thresholds['low_improvement']:.3f}%",
                    'timestamp': datetime.now().isoformat()
                }
                alerts.append(alert)
                self.alerts.append(alert)
                logger.warning(f"[预警] {alert['message']}")
        
        # 检查优化时间过长
        optimization_time = result.get('optimization_time', 0)
        if optimization_time > self.alert_thresholds['high_time']:
            alert = {
                'type': 'high_time',
                'severity': 'warning',
                'method': method,
                'message': f"优化时间过长: {optimization_time:.3f}秒 > {self.alert_thresholds['high_time']:.3f}秒",
                'timestamp': datetime.now().isoformat()
            }
            alerts.append(alert)
            self.alerts.append(alert)
            logger.warning(f"[预警] {alert['message']}")
        
        # 检查成功率过低
        total = self.stats[method]['total']
        if total >= 10:
            success_rate = self.stats[method]['success'] / total
            if success_rate < self.alert_thresholds['low_success_rate']:
                alert = {
                    'type': 'low_success_rate',
                    'severity': 'critical',
                    'method': method,
                    'message': f"成功率过低: {success_rate:.3f} < {self.alert_thresholds['low_success_rate']:.3f}",
                    'timestamp': datetime.now().isoformat()
                }
                alerts.append(alert)
                self.alerts.append(alert)
                logger.error(f"[预警] {alert['message']}")
        
        # 检查连续无改善
        consecutive_no_improvement = self.stats[method]['consecutive_no_improvement']
        if consecutive_no_improvement >= self.alert_thresholds['stagnation']:
            alert = {
                'type': 'stagnation',
                'severity': 'warning',
                'method': method,
                'message': f"连续{consecutive_no_improvement}次无改善，可能陷入局部最优",
                'timestamp': datetime.now().isoformat()
            }
            alerts.append(alert)
            self.alerts.append(alert)
            logger.warning(f"[预警] {alert['message']}")
        
        return alerts
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取最近的预警
        
        Args:
            hours: 时间范围（小时）
            
        Returns:
            预警列表
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = []
        
        for alert in self.alerts:
            alert_time = datetime.fromisoformat(alert['timestamp'])
            if alert_time >= cutoff_time:
                recent_alerts.append(alert)
        
        return recent_alerts
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息
        """
        stats = {}
        for method, data in self.stats.items():
            total = data['total']
            if total > 0:
                stats[method] = {
                    'total': total,
                    'success': data['success'],
                    'failure': data['failure'],
                    'success_rate': data['success'] / total,
                    'failure_rate': data['failure'] / total,
                    'consecutive_no_improvement': data['consecutive_no_improvement']
                }
        
        return stats


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_daily_report(self, data: List[Dict[str, Any]]) -> str:
        """生成日报
        
        Args:
            data: 优化数据
            
        Returns:
            报告文件路径
        """
        # 转换为DataFrame
        df = pd.DataFrame(data)
        
        # 生成报告
        report = []
        report.append("# 优化器日报")
        report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 总体统计
        report.append("\n## 总体统计")
        report.append(f"总优化次数: {len(df)}")
        report.append(f"成功次数: {len(df[df['success'] == True])}")
        report.append(f"失败次数: {len(df[df['success'] == False])}")
        
        # 按方法统计
        report.append("\n## 按方法统计")
        for method in df['method'].unique():
            method_df = df[df['method'] == method]
            report.append(f"\n### {method}")
            report.append(f"  总次数: {len(method_df)}")
            report.append(f"  成功率: {method_df['success'].mean():.3f}")
            report.append(f"  平均性能提升: {method_df['improvement_percentage'].mean():.3f}%")
            report.append(f"  平均优化时间: {method_df['optimization_time'].mean():.3f}秒")
        
        # 性能对比
        report.append("\n## 性能对比")
        successful_df = df[df['success'] == True]
        for method in successful_df['method'].unique():
            method_df = successful_df[successful_df['method'] == method]
            report.append(f"{method:12s}: 平均提升={method_df['improvement_percentage'].mean():.3f}%, 平均时间={method_df['optimization_time'].mean():.3f}秒")
        
        # 保存报告
        report_text = "\n".join(report)
        filename = f"daily_report_{datetime.now().strftime('%Y%m%d')}.md"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        logger.info(f"日报已生成: {filepath}")
        return filepath
    
    def generate_weekly_report(self, data: List[Dict[str, Any]]) -> str:
        """生成周报
        
        Args:
            data: 优化数据
            
        Returns:
            报告文件路径
        """
        # 转换为DataFrame
        df = pd.DataFrame(data)
        
        # 生成报告
        report = []
        report.append("# 优化器周报")
        report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 总体统计
        report.append("\n## 总体统计")
        report.append(f"总优化次数: {len(df)}")
        report.append(f"成功次数: {len(df[df['success'] == True])}")
        report.append(f"失败次数: {len(df[df['success'] == False])}")
        
        # 按方法统计
        report.append("\n## 按方法统计")
        for method in df['method'].unique():
            method_df = df[df['method'] == method]
            report.append(f"\n### {method}")
            report.append(f"  总次数: {len(method_df)}")
            report.append(f"  成功率: {method_df['success'].mean():.3f}")
            report.append(f"  平均性能提升: {method_df['improvement_percentage'].mean():.3f}%")
            report.append(f"  性能提升标准差: {method_df['improvement_percentage'].std():.3f}%")
            report.append(f"  最大性能提升: {method_df['improvement_percentage'].max():.3f}%")
            report.append(f"  最小性能提升: {method_df['improvement_percentage'].min():.3f}%")
            report.append(f"  平均优化时间: {method_df['optimization_time'].mean():.3f}秒")
        
        # 趋势分析
        report.append("\n## 趋势分析")
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        daily_stats = df.groupby(['date', 'method']).agg({
            'improvement_percentage': 'mean',
            'optimization_time': 'mean',
            'success': 'mean'
        }).reset_index()
        
        for method in df['method'].unique():
            method_daily = daily_stats[daily_stats['method'] == method]
            if len(method_daily) > 1:
                # 计算趋势
                improvements = method_daily['improvement_percentage'].values
                trend = np.polyfit(range(len(improvements)), improvements, 1)[0]
                trend_str = "上升" if trend > 0 else "下降"
                report.append(f"{method:12s}: 趋势={trend_str} ({trend:.6f}%/天)")
        
        # 保存报告
        report_text = "\n".join(report)
        filename = f"weekly_report_{datetime.now().strftime('%Y%m%d')}.md"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        logger.info(f"周报已生成: {filepath}")
        return filepath


class EnhancedOptimizationMonitor:
    """增强的优化器监控"""
    
    def __init__(self, max_history=1000):
        self.max_history = max_history
        self.optimization_history = deque(maxlen=max_history)
        self.performance_history = defaultdict(lambda: deque(maxlen=100))
        self.lock = threading.Lock()
        
        # 性能预测器
        self.predictor = PerformancePredictor()
        
        # 预警管理器
        self.alert_manager = AlertManager()
        
        # 报告生成器
        self.report_generator = ReportGenerator()
        
        # 性能基准
        self.performance_baselines = {
            'genetic': {'avg_improvement': 15.0, 'avg_time': 20.0},
            'bayesian': {'avg_improvement': 10.0, 'avg_time': 5.0},
            'random': {'avg_improvement': 12.0, 'avg_time': 5.0},
            'gradient': {'avg_improvement': 10.0, 'avg_time': 40.0}
        }
        
        # 实时监控线程
        self.monitoring_thread = None
        self.monitoring_active = False
        
        # 自动报告生成线程
        self.report_thread = None
        self.report_active = False
    
    def record_optimization(self, result: Dict[str, Any]):
        """记录优化结果
        
        Args:
            result: 优化结果
        """
        with self.lock:
            # 添加时间戳
            result['timestamp'] = datetime.now().isoformat()
            
            # 添加到历史记录
            self.optimization_history.append(result)
            
            # 添加到性能历史
            method = result.get('method', 'unknown')
            if result.get('success', False):
                self.performance_history[method].append({
                    'improvement': result.get('improvement_percentage', 0),
                    'time': result.get('optimization_time', 0),
                    'timestamp': result['timestamp']
                })
                
                # 添加到预测器
                self.predictor.add_observation(
                    method,
                    result.get('improvement_percentage', 0),
                    result.get('optimization_time', 0)
                )
            
            # 检查预警
            alerts = self.alert_manager.check_alerts(result)
            
            logger.info(f"记录优化结果: {method}, 成功={result.get('success', False)}, "
                       f"提升={result.get('improvement_percentage', 0):.3f}%, "
                       f"时间={result.get('optimization_time', 0):.3f}秒, "
                       f"预警={len(alerts)}")
    
    def predict_performance(self, method: str, iterations: int) -> Dict[str, float]:
        """预测性能
        
        Args:
            method: 优化方法
            iterations: 迭代次数
            
        Returns:
            预测结果
        """
        predicted_improvement = self.predictor.predict_improvement(method, iterations)
        predicted_time = self.predictor.predict_time(method, iterations)
        
        return {
            'method': method,
            'iterations': iterations,
            'predicted_improvement': predicted_improvement,
            'predicted_time': predicted_time
        }
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取最近的预警
        
        Args:
            hours: 时间范围（小时）
            
        Returns:
            预警列表
        """
        return self.alert_manager.get_recent_alerts(hours)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息
        """
        return self.alert_manager.get_statistics()
    
    def generate_daily_report(self) -> str:
        """生成日报
        
        Returns:
            报告文件路径
        """
        with self.lock:
            data = list(self.optimization_history)
            return self.report_generator.generate_daily_report(data)
    
    def generate_weekly_report(self) -> str:
        """生成周报
        
        Returns:
            报告文件路径
        """
        with self.lock:
            data = list(self.optimization_history)
            return self.report_generator.generate_weekly_report(data)
    
    def start_monitoring(self, interval_seconds=60):
        """启动实时监控
        
        Args:
            interval_seconds: 监控间隔（秒）
        """
        if self.monitoring_active:
            logger.warning("监控已在运行中")
            return
        
        self.monitoring_active = True
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    # 获取统计信息
                    stats = self.get_statistics()
                    
                    # 获取最近预警
                    recent_alerts = self.get_recent_alerts(hours=1)
                    
                    # 输出监控信息
                    logger.info(f"[实时监控] 总优化次数: {sum(s['total'] for s in stats.values())}, "
                               f"最近预警: {len(recent_alerts)}")
                    
                    # 等待下一次监控
                    time.sleep(interval_seconds)
                    
                except Exception as e:
                    logger.error(f"监控异常: {e}")
                    time.sleep(interval_seconds)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info(f"实时监控已启动，间隔: {interval_seconds}秒")
    
    def stop_monitoring(self):
        """停止实时监控"""
        if not self.monitoring_active:
            logger.warning("监控未运行")
            return
        
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("实时监控已停止")
    
    def start_auto_report(self, daily_hour=9, weekly_day=0):
        """启动自动报告生成
        
        Args:
            daily_hour: 每日报告生成时间（小时）
            weekly_day: 每周报告生成时间（星期，0=周一）
        """
        if self.report_active:
            logger.warning("自动报告已在运行中")
            return
        
        self.report_active = True
        
        def report_loop():
            while self.report_active:
                try:
                    now = datetime.now()
                    
                    # 生成日报
                    if now.hour == daily_hour and now.minute == 0:
                        self.generate_daily_report()
                    
                    # 生成周报
                    if now.weekday() == weekly_day and now.hour == daily_hour and now.minute == 0:
                        self.generate_weekly_report()
                    
                    # 等待下一次检查
                    time.sleep(60)
                    
                except Exception as e:
                    logger.error(f"自动报告生成异常: {e}")
                    time.sleep(60)
        
        self.report_thread = threading.Thread(target=report_loop, daemon=True)
        self.report_thread.start()
        logger.info(f"自动报告生成已启动，日报时间: {daily_hour}:00, 周报时间: 周{weekly_day + 1} {daily_hour}:00")
    
    def stop_auto_report(self):
        """停止自动报告生成"""
        if not self.report_active:
            logger.warning("自动报告未运行")
            return
        
        self.report_active = False
        if self.report_thread:
            self.report_thread.join(timeout=5)
        
        logger.info("自动报告生成已停止")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """获取监控状态
        
        Returns:
            监控状态
        """
        return {
            'monitoring_active': self.monitoring_active,
            'report_active': self.report_active,
            'total_optimizations': len(self.optimization_history),
            'recent_alerts': len(self.get_recent_alerts(hours=1)),
            'statistics': self.get_statistics()
        }


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("增强的监控和分析系统")
    logger.info("=" * 80)
    
    # 创建监控器
    monitor = EnhancedOptimizationMonitor()
    
    # 启动实时监控
    monitor.start_monitoring(interval_seconds=30)
    
    # 启动自动报告生成
    monitor.start_auto_report(daily_hour=9, weekly_day=0)
    
    # 模拟一些优化结果
    logger.info("\n模拟优化结果...")
    for i in range(10):
        result = {
            'method': np.random.choice(['genetic', 'bayesian', 'random', 'gradient']),
            'success': np.random.random() > 0.1,
            'best_score': np.random.uniform(0.3, 0.8),
            'baseline_score': np.random.uniform(0.3, 0.7),
            'improvement_percentage': np.random.uniform(-2.0, 20.0),
            'optimization_time': np.random.uniform(1.0, 50.0),
            'iterations': np.random.randint(3, 20)
        }
        monitor.record_optimization(result)
        time.sleep(1)
    
    # 获取监控状态
    status = monitor.get_monitoring_status()
    logger.info(f"\n监控状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    # 预测性能
    logger.info("\n性能预测:")
    for method in ['genetic', 'bayesian', 'random', 'gradient']:
        prediction = monitor.predict_performance(method, 20)
        logger.info(f"{method:12s}: 预测提升={prediction['predicted_improvement']:.3f}%, "
                   f"预测时间={prediction['predicted_time']:.3f}秒")
    
    # 生成报告
    logger.info("\n生成报告...")
    daily_report = monitor.generate_daily_report()
    logger.info(f"日报: {daily_report}")
    
    # 停止监控
    logger.info("\n停止监控...")
    monitor.stop_monitoring()
    monitor.stop_auto_report()
    
    logger.info("\n" + "=" * 80)
    logger.info("测试完成")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
