from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动调优器
提供一键优化、批量优化和智能调度功能
"""

from analysis.pattern_manager import PatternManager
from optimization.database_schema import OptimizationDatabaseManager
from optimization.version_manager import VersionManager
from optimization.algorithm_optimizer import AlgorithmOptimizer, OptimizationConfig, PerformanceEvaluator
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class TuningTask:
    """调优任务"""
    pattern_name: str
    priority: int = 5  # 1-10，数字越小优先级越高
    config: OptimizationConfig = None
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class AlgorithmAutoTuner:
    """策略自动调优器"""

    def __init__(self, max_workers: int = os.cpu_count() * 2, debug_mode: bool = False):
        self.max_workers = max_workers
        self.debug_mode = debug_mode

        # 核心组件
        self.optimizer = AlgorithmOptimizer(debug_mode)
        self.evaluator = PerformanceEvaluator(debug_mode)
        self.version_manager = VersionManager()
        self.pattern_manager = PatternManager()
        self.db_manager = OptimizationDatabaseManager()

        # 任务管理
        self.task_queue: List[TuningTask] = []
        self.running_tasks: Dict[str, TuningTask] = {}
        self.completed_tasks: List[TuningTask] = []

        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.is_running = False

        # 回调函数
        self.progress_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None

    def one_click_optimize(self, pattern_names: List[str] = None,
                           optimization_method: str = "genetic",
                           max_iterations: int = 20) -> Dict[str, Any]:
        """
        一键优化指定形态或所有形态

        Args:
            pattern_names: 要优化的形态名称列表，None表示优化所有形态
            optimization_method: 优化方法
            max_iterations: 最大迭代次数

        Returns:
            优化结果摘要
        """
        logger.info("启动一键优化...")

        # 获取要优化的形态列表
        if pattern_names is None:
            pattern_names = self._get_all_pattern_names()

        logger.info(f" 待优化形态: {len(pattern_names)}个")

        # 创建优化配置
        config = OptimizationConfig(
            method=optimization_method,
            max_iterations=max_iterations,
            population_size=10,  # 一键优化使用较小的种群
            timeout_minutes=15   # 每个形态最多15分钟
        )

        # 添加优化任务
        tasks = []
        for i, pattern_name in enumerate(pattern_names):
            task = TuningTask(
                pattern_name=pattern_name,
                priority=i + 1,  # 按顺序设置优先级
                config=config
            )
            tasks.append(task)
            self.add_task(task)

        # 开始批量优化
        results = self.run_batch_optimization()

        # 生成优化报告
        report = self._generate_optimization_report(results)

        logger.info("一键优化完成！")
        return report

    def smart_optimize(self, performance_threshold: float = 0.7,
                       improvement_target: float = 0.1) -> Dict[str, Any]:
        """
        智能优化：自动识别需要优化的形态并进行优化

        Args:
            performance_threshold: 性能阈值，低于此值的形态将被优化
            improvement_target: 改进目标，期望的性能提升比例

        Returns:
            优化结果
        """
        logger.info("启动智能优化...")

        # 评估所有形态的当前性能
        pattern_names = self._get_all_pattern_names()
        performance_scores = {}

        logger.info("评估当前性能...")
        for pattern_name in pattern_names:
            try:
                test_datasets = self.evaluator.create_test_datasets(
                    pattern_name, count=3)
                metrics = self.evaluator.evaluate_algorithm(
                    pattern_name, test_datasets)
                performance_scores[pattern_name] = metrics.overall_score

                if self.debug_mode:
                    logger.info(f"  {pattern_name}: {metrics.overall_score:.3f}")

            except Exception as e:
                if self.debug_mode:
                    logger.info(f"  {pattern_name}: 评估失败 - {e}")
                performance_scores[pattern_name] = 0.0

        # 识别需要优化的形态
        patterns_to_optimize = [
            name for name, score in performance_scores.items()
            if score < performance_threshold
        ]

        logger.info(f"识别到 {len(patterns_to_optimize)} 个需要优化的形态")

        if not patterns_to_optimize:
            return {
                "status": "no_optimization_needed",
                "message": "所有形态性能都达到阈值要求",
                "performance_scores": performance_scores
            }

        # 按性能分数排序，优先优化性能最差的
        patterns_to_optimize.sort(key=lambda x: performance_scores[x])

        # 创建智能优化配置
        smart_configs = self._create_smart_configs(
            patterns_to_optimize, performance_scores)

        # 添加优化任务
        for pattern_name, config in smart_configs.items():
            task = TuningTask(
                pattern_name=pattern_name,
                priority=1,  # 智能优化高优先级
                config=config
            )
            self.add_task(task)

        # 执行优化
        results = self.run_batch_optimization()

        # 生成智能优化报告
        report = self._generate_smart_optimization_report(
            results, performance_scores, improvement_target
        )

        return report

    def add_task(self, task: TuningTask):
        """添加优化任务"""
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda t: t.priority)  # 按优先级排序

        if self.debug_mode:
            logger.info(f" 添加任务: {task.pattern_name} (优先级: {task.priority})")

    def run_batch_optimization(self) -> List[Dict[str, Any]]:
        """运行批量优化"""
        if not self.task_queue:
            return []

        logger.info(f"开始批量优化，共 {len(self.task_queue)} 个任务")

        self.is_running = True
        results = []

        try:
            # 提交任务到线程池
            future_to_task = {}

            for task in self.task_queue[:self.max_workers]:  # 限制并发数
                future = self.executor.submit(self._run_single_task, task)
                future_to_task[future] = task
                task.status = "running"
                task.start_time = datetime.now()
                self.running_tasks[task.pattern_name] = task

            # 等待任务完成
            for future in as_completed(future_to_task):
                task = future_to_task[future]

                try:
                    result = future.result()
                    task.result = result
                    task.status = "completed"
                    task.end_time = datetime.now()
                    results.append(result)

                    if self.debug_mode:
                        logger.info(f" 任务完成: {task.pattern_name}")

                    # 调用完成回调
                    if self.completion_callback:
                        self.completion_callback(task)

                except Exception as e:
                    task.error_message = str(e)
                    task.status = "failed"
                    task.end_time = datetime.now()

                    if self.debug_mode:
                        logger.info(f" 任务失败: {task.pattern_name} - {e}")

                # 移除运行中的任务
                if task.pattern_name in self.running_tasks:
                    del self.running_tasks[task.pattern_name]

                # 添加到完成列表
                self.completed_tasks.append(task)

                # 启动下一个任务（如果有）
                remaining_tasks = [
                    t for t in self.task_queue if t.status == "pending"]
                if remaining_tasks and len(self.running_tasks) < self.max_workers:
                    next_task = remaining_tasks[0]
                    future = self.executor.submit(
                        self._run_single_task, next_task)
                    future_to_task[future] = next_task
                    next_task.status = "running"
                    next_task.start_time = datetime.now()
                    self.running_tasks[next_task.pattern_name] = next_task

        finally:
            self.is_running = False
            self.task_queue.clear()

        logger.info(f" 批量优化完成，成功 {len(results)} 个任务")
        return results

    def _run_single_task(self, task: TuningTask) -> Dict[str, Any]:
        """运行单个优化任务"""
        try:
            # 更新进度
            task.progress = 0.1
            if self.progress_callback:
                self.progress_callback(task)

            # 执行优化
            result = self.optimizer.optimize_algorithm(
                pattern_name=task.pattern_name,
                config=task.config
            )

            # 更新进度
            task.progress = 1.0
            if self.progress_callback:
                self.progress_callback(task)

            return result

        except Exception as e:
            task.error_message = str(e)
            raise e

    def schedule_optimization(self, pattern_name: str,
                              schedule_time: datetime,
                              config: OptimizationConfig = None) -> bool:
        """调度优化任务"""
        if schedule_time <= datetime.now():
            raise ValueError("调度时间必须在未来")

        # 保存到数据库
        conn = self.db_manager.db_path
        # 这里可以实现定时任务的数据库存储

        logger.info(f"[TIME] 已调度优化任务: {pattern_name} 在 {schedule_time}")
        return True

    def get_optimization_status(self) -> Dict[str, Any]:
        """获取优化状态"""
        try:
            # 获取活跃的优化任务
            active_count = 0
            completed_count = 0
            failed_count = 0

            # 检查线程池状态
            if hasattr(self, 'executor') and self.executor:
                # 统计正在运行的任务
                active_count = len(
                    [f for f in self.optimization_futures if not f.done()])
                completed_count = len(
                    [f for f in self.optimization_futures if f.done() and not f.exception()])
                failed_count = len(
                    [f for f in self.optimization_futures if f.done() and f.exception()])

            # 获取数据库中的统计信息
            db_stats = self.db_manager.get_optimization_statistics()

            return {
                "active_optimizations": active_count,
                "completed_optimizations": completed_count,
                "failed_optimizations": failed_count,
                "total_versions": db_stats.get("total_versions", 0),
                "active_versions": db_stats.get("active_versions", 0),
                "avg_improvement": db_stats.get("avg_improvement", 0),
                "system_status": "running" if active_count > 0 else "idle",
                "last_update": datetime.now().isoformat()
            }

        except Exception as e:
            if self.debug_mode:
                logger.info(f" 获取优化状态失败: {e}")

            return {
                "active_optimizations": 0,
                "completed_optimizations": 0,
                "failed_optimizations": 0,
                "total_versions": 0,
                "active_versions": 0,
                "avg_improvement": 0,
                "system_status": "error",
                "error": str(e),
                "last_update": datetime.now().isoformat()
            }

    def get_status(self) -> Dict[str, Any]:
        """获取自动调优状态 - get_optimization_status的别名，用于兼容性"""
        status = self.get_optimization_status()
        # 重新映射字段名以匹配import_execution_engine期望的格式
        return {
            "active_tasks": status.get("active_optimizations", 0),
            "completed_tasks": status.get("completed_optimizations", 0),
            "failed_tasks": status.get("failed_optimizations", 0),
            "total_improvement": status.get("avg_improvement", 0),
            "system_status": status.get("system_status", "idle"),
            "last_update": status.get("last_update", datetime.now().isoformat()),
            # 保留原有字段
            **status
        }

    def cancel_task(self, pattern_name: str) -> bool:
        """取消优化任务"""
        # 取消待执行的任务
        for task in self.task_queue:
            if task.pattern_name == pattern_name and task.status == "pending":
                task.status = "cancelled"
                self.task_queue.remove(task)
                return True

        # 对于正在运行的任务，这里需要实现中断机制
        if pattern_name in self.running_tasks:
            # 实际实现中需要更复杂的中断逻辑
            logger.info(f"  正在运行的任务无法立即取消: {pattern_name}")
            return False

        return False

    def _get_all_pattern_names(self) -> List[str]:
        """获取所有形态名称"""
        try:
            patterns = self.pattern_manager.get_all_patterns()
            return [p.english_name for p in patterns if p.is_active]
        except Exception as e:
            if self.debug_mode:
                logger.info(f"获取形态列表失败: {e}")
            return []

    def _create_smart_configs(self, patterns: List[str],
                              performance_scores: Dict[str, float]) -> Dict[str, OptimizationConfig]:
        """为不同形态创建智能优化配置"""
        configs = {}

        for pattern_name in patterns:
            score = performance_scores.get(pattern_name, 0.5)

            # 根据当前性能调整优化强度
            if score < 0.3:
                # 性能很差，使用强化优化
                config = OptimizationConfig(
                    method="genetic",
                    max_iterations=50,
                    population_size=30,
                    mutation_rate=0.15,
                    timeout_minutes=45
                )
            elif score < 0.5:
                # 性能一般，使用标准优化
                config = OptimizationConfig(
                    method="genetic",
                    max_iterations=30,
                    population_size=20,
                    mutation_rate=0.1,
                    timeout_minutes=30
                )
            else:
                # 性能尚可，使用轻度优化
                config = OptimizationConfig(
                    method="bayesian",
                    max_iterations=20,
                    population_size=10,
                    timeout_minutes=20
                )

            configs[pattern_name] = config

        return configs

    def _generate_optimization_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成优化报告"""
        if not results:
            return {"status": "no_results", "message": "没有优化结果"}

        total_tasks = len(results)
        successful_tasks = len(
            [r for r in results if r.get("improvement_percentage", 0) > 0])

        improvements = [r.get("improvement_percentage", 0) for r in results]
        avg_improvement = sum(improvements) / \
            len(improvements) if improvements else 0

        best_improvement = max(improvements) if improvements else 0
        best_pattern = None
        for result in results:
            if result.get("improvement_percentage", 0) == best_improvement:
                best_pattern = result.get("pattern_name", "unknown")
                break

        report = {
            "summary": {
                "total_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "success_rate": successful_tasks / total_tasks * 100,
                "average_improvement": avg_improvement,
                "best_improvement": best_improvement,
                "best_pattern": best_pattern
            },
            "details": results,
            "recommendations": self._generate_recommendations(results)
        }

        return report

    def _generate_smart_optimization_report(self, results: List[Dict[str, Any]],
                                            baseline_scores: Dict[str, float],
                                            improvement_target: float) -> Dict[str, Any]:
        """生成智能优化报告"""
        report = self._generate_optimization_report(results)

        # 添加智能分析
        achieved_targets = 0
        for result in results:
            pattern_name = result.get("pattern_name", "")
            improvement = result.get("improvement_percentage", 0) / 100
            if improvement >= improvement_target:
                achieved_targets += 1

        report["smart_analysis"] = {
            "baseline_performance": baseline_scores,
            "improvement_target": improvement_target * 100,
            "targets_achieved": achieved_targets,
            "target_achievement_rate": achieved_targets / len(results) * 100 if results else 0
        }

        return report

    def _generate_recommendations(self, results: List[Dict[str, Any]]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        if not results:
            return ["没有优化结果可供分析"]

        # 分析优化效果
        improvements = [r.get("improvement_percentage", 0) for r in results]
        avg_improvement = sum(improvements) / len(improvements)

        if avg_improvement < 5:
            recommendations.append("整体优化效果有限，建议检查算法基础逻辑或增加训练数据")
        elif avg_improvement > 20:
            recommendations.append("优化效果显著，建议将优化后的版本部署到生产环境")

        # 分析优化方法效果
        methods = {}
        for result in results:
            method = result.get("method", "unknown")
            improvement = result.get("improvement_percentage", 0)
            if method not in methods:
                methods[method] = []
            methods[method].append(improvement)

        best_method = max(methods.keys(), key=lambda m: sum(
            methods[m])/len(methods[m])) if methods else None
        if best_method:
            recommendations.append(f"'{best_method}' 方法效果最佳，建议优先使用")

        # 识别问题形态
        poor_performers = [
            r.get("pattern_name", "unknown")
            for r in results
            if r.get("improvement_percentage", 0) < 2
        ]

        if poor_performers:
            recommendations.append(
                f"以下形态优化效果不佳，需要人工检查: {', '.join(poor_performers[:3])}")

        return recommendations

    def set_progress_callback(self, callback: Callable[[TuningTask], None]):
        """设置进度回调函数"""
        self.progress_callback = callback

    def set_completion_callback(self, callback: Callable[[TuningTask], None]):
        """设置完成回调函数"""
        self.completion_callback = callback

    def export_optimization_history(self, export_path: str) -> bool:
        """导出优化历史"""
        try:
            history = {
                "export_time": datetime.now().isoformat(),
                "completed_tasks": [
                    {
                        "pattern_name": task.pattern_name,
                        "start_time": task.start_time.isoformat() if task.start_time else None,
                        "end_time": task.end_time.isoformat() if task.end_time else None,
                        "status": task.status,
                        "result": task.result,
                        "error_message": task.error_message
                    }
                    for task in self.completed_tasks
                ]
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            logger.info(f" 优化历史已导出到: {export_path}")
            return True

        except Exception as e:
            logger.info(f" 导出失败: {e}")
            return False


def create_auto_tuner(max_workers: int = 4, debug_mode: bool = False) -> AlgorithmAutoTuner:
    """创建自动调优器实例"""
    return AlgorithmAutoTuner(max_workers=max_workers, debug_mode=debug_mode)


if __name__ == "__main__":
    # 测试自动调优器
    tuner = create_auto_tuner(max_workers=2, debug_mode=True)

    # 测试一键优化（仅优化几个形态）
    test_patterns = ["hammer", "doji"]

    logger.info("测试一键优化...")
    result = tuner.one_click_optimize(
        pattern_names=test_patterns,
        optimization_method="random",  # 使用快速的随机优化进行测试
        max_iterations=5
    )

    logger.info(f"\n优化报告:")
    logger.info(f"  总任务数: {result['summary']['total_tasks']}")
    logger.info(f"  成功任务数: {result['summary']['successful_tasks']}")
    logger.info(f"  平均改进: {result['summary']['average_improvement']:.3f}%")
    logger.info(f"  最佳改进: {result['summary']['best_improvement']:.3f}%")
    logger.info(f"  最佳形态: {result['summary']['best_pattern']}")

    logger.info(f"\n 建议:")
    for rec in result['recommendations']:
        logger.info(f"  - {rec}")
