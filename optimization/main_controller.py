#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
形态识别算法优化系统主控制器
提供统一的入口点和命令行界面
"""

from analysis.pattern_manager import PatternManager
from optimization.optimization_dashboard import OptimizationDashboard, run_dashboard
from optimization.ui_integration import UIIntegration, create_ui_integration
from optimization.database_schema import OptimizationDatabaseManager
from optimization.algorithm_optimizer import AlgorithmOptimizer, PerformanceEvaluator
from optimization.version_manager import VersionManager
from optimization.auto_tuner import AlgorithmAutoTuner, OptimizationConfig
import sys
import os
import argparse
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入优化系统组件

class OptimizationController:
    """优化系统主控制器"""

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode

        # 初始化核心组件
        self.auto_tuner = AlgorithmAutoTuner(debug_mode=debug_mode)
        self.version_manager = VersionManager()
        self.evaluator = PerformanceEvaluator(debug_mode)
        self.optimizer = AlgorithmOptimizer(debug_mode)
        self.pattern_manager = PatternManager()
        self.db_manager = OptimizationDatabaseManager()
        self.ui_integration = UIIntegration(debug_mode)

        print("FactorWeave-Quant 形态识别算法优化系统")
        print("=" * 50)

    def run_command_line(self, args):
        """运行命令行模式"""
        if args.command == "status":
            self.show_system_status()

        elif args.command == "list":
            self.list_patterns()

        elif args.command == "evaluate":
            self.evaluate_pattern(args.pattern, args.datasets)

        elif args.command == "optimize":
            self.optimize_pattern(args.pattern, args.method, args.iterations)

        elif args.command == "batch_optimize":
            self.batch_optimize(args.method, args.iterations)

        elif args.command == "smart_optimize":
            self.smart_optimize(args.threshold, args.target)

        elif args.command == "versions":
            self.show_versions(args.pattern)

        elif args.command == "activate":
            self.activate_version(args.pattern, args.version)

        elif args.command == "rollback":
            self.rollback_version(args.pattern, args.version)

        elif args.command == "export":
            self.export_data(args.pattern, args.output)

        elif args.command == "dashboard":
            self.launch_dashboard()

        elif args.command == "init":
            self.initialize_system()

        else:
            print(f" 未知命令: {args.command}")
            self.show_help()

    def show_system_status(self):
        """显示系统状态"""
        print("系统状态")
        print("-" * 30)

        try:
            # 获取优化统计
            stats = self.db_manager.get_optimization_statistics()

            print(f"总版本数: {stats.get('total_versions', 0)}")
            print(f"活跃版本数: {stats.get('active_versions', 0)}")
            print(f"平均性能提升: {stats.get('avg_improvement', 0):.3f}%")

            # 优化任务统计
            task_stats = stats.get('optimization_tasks', {})
            if task_stats:
                print("\n优化任务统计:")
                for status, count in task_stats.items():
                    print(f"  {status}: {count}")

            # 最佳性能形态
            top_performers = stats.get('top_performers', [])
            if top_performers:
                print("\n最佳性能形态:")
                for performer in top_performers[:5]:
                    print(
                        f"  {performer['pattern']}: {performer['score']:.3f}")

            # 当前运行状态
            tuner_status = self.auto_tuner.get_optimization_status()
            print(f"\n当前活跃优化任务: {tuner_status['active_optimizations']}")

        except Exception as e:
            print(f" 获取系统状态失败: {e}")

    def list_patterns(self):
        """列出所有形态"""
        print("形态列表")
        print("-" * 30)

        try:
            patterns = self.pattern_manager.get_all_patterns()

            print(f"总计: {len(patterns)} 个形态")
            print()

            for i, pattern in enumerate(patterns, 1):
                status = " 激活" if pattern.is_active else "未激活"
                print(
                    f"{i:2d}. {pattern.english_name:20s} ({pattern.name}) - {status}")

                # 显示最新性能
                try:
                    history = self.db_manager.get_performance_history(
                        pattern.english_name, limit=1)
                    if history:
                        latest = history[0]
                        score = latest.get('overall_score', 0)
                        print(f"     最新评分: {score:.3f}")
                except:
                    pass

        except Exception as e:
            print(f" 获取形态列表失败: {e}")

    def evaluate_pattern(self, pattern_name: str, dataset_count: int = 3):
        """评估形态性能"""
        if not pattern_name:
            print("请指定要评估的形态名称")
            return

        print(f"评估形态: {pattern_name}")
        print("-" * 30)

        try:
            # 创建测试数据集
            test_datasets = self.evaluator.create_test_datasets(
                pattern_name, count=dataset_count)

            # 执行评估
            metrics = self.evaluator.evaluate_algorithm(
                pattern_name, test_datasets)

            # 显示结果
            print(f"综合评分: {metrics.overall_score:.3f}")
            print(f"信号质量: {metrics.signal_quality:.3f}")
            print(f"平均置信度: {metrics.confidence_avg:.3f}")
            print(f"执行时间: {metrics.execution_time:.3f}秒")
            print(f"识别形态数: {metrics.patterns_found}")
            print(f"鲁棒性: {metrics.robustness_score:.3f}")
            print(f"参数敏感性: {metrics.parameter_sensitivity:.3f}")

        except Exception as e:
            print(f" 评估失败: {e}")

    def optimize_pattern(self, pattern_name: str, method: str = "genetic", iterations: int = 30):
        """优化单个形态"""
        if not pattern_name:
            print("请指定要优化的形态名称")
            return

        print(f" 优化形态: {pattern_name}")
        print(f"优化方法: {method}")
        print(f"最大迭代次数: {iterations}")
        print("-" * 30)

        try:
            # 创建优化配置
            config = OptimizationConfig(
                method=method,
                max_iterations=iterations,
                population_size=20,
                timeout_minutes=30
            )

            # 执行优化
            result = self.optimizer.optimize_algorithm(pattern_name, config)

            # 显示结果
            print(f" 优化完成！")
            print(f"基准评分: {result['baseline_score']:.3f}")
            print(f"最佳评分: {result['best_score']:.3f}")
            print(f"性能提升: {result['improvement_percentage']:.3f}%")
            print(f"迭代次数: {result['iterations']}")
            print(f"最佳版本ID: {result.get('best_version_id', 'N/A')}")

        except Exception as e:
            print(f" 优化失败: {e}")

    def batch_optimize(self, method: str = "genetic", iterations: int = 20):
        """批量优化所有形态"""
        print("批量优化所有形态")
        print(f"优化方法: {method}")
        print(f"最大迭代次数: {iterations}")
        print("-" * 30)

        try:
            result = self.auto_tuner.one_click_optimize(
                optimization_method=method,
                max_iterations=iterations
            )

            summary = result.get("summary", {})
            print(f" 批量优化完成！")
            print(f"总任务数: {summary.get('total_tasks', 0)}")
            print(f"成功任务数: {summary.get('successful_tasks', 0)}")
            print(f"成功率: {summary.get('success_rate', 0):.1f}%")
            print(f"平均改进: {summary.get('average_improvement', 0):.3f}%")
            print(f"最佳改进: {summary.get('best_improvement', 0):.3f}%")
            print(f"最佳形态: {summary.get('best_pattern', 'N/A')}")

            # 显示建议
            recommendations = result.get("recommendations", [])
            if recommendations:
                print("\n 优化建议:")
                for rec in recommendations:
                    print(f"  - {rec}")

        except Exception as e:
            print(f" 批量优化失败: {e}")

    def smart_optimize(self, threshold: float = 0.7, target: float = 0.1):
        """智能优化"""
        print("智能优化")
        print(f"性能阈值: {threshold}")
        print(f"改进目标: {target * 100:.1f}%")
        print("-" * 30)

        try:
            result = self.auto_tuner.smart_optimize(
                performance_threshold=threshold,
                improvement_target=target
            )

            if result.get("status") == "no_optimization_needed":
                print("所有形态性能都达到要求，无需优化")

                # 显示性能分数
                scores = result.get("performance_scores", {})
                if scores:
                    print("\n当前性能分数:")
                    for pattern, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                        print(f"  {pattern}: {score:.3f}")
            else:
                summary = result.get("summary", {})
                print(f" 智能优化完成！")
                print(f"优化形态数: {summary.get('total_tasks', 0)}")
                print(f"成功任务数: {summary.get('successful_tasks', 0)}")
                print(f"平均改进: {summary.get('average_improvement', 0):.3f}%")

                # 智能分析结果
                smart_analysis = result.get("smart_analysis", {})
                if smart_analysis:
                    print(
                        f"目标达成率: {smart_analysis.get('target_achievement_rate', 0):.1f}%")

        except Exception as e:
            print(f" 智能优化失败: {e}")

    def show_versions(self, pattern_name: str):
        """显示形态版本"""
        if not pattern_name:
            print("请指定形态名称")
            return

        print(f" {pattern_name} 版本历史")
        print("-" * 50)

        try:
            versions = self.version_manager.get_versions(
                pattern_name, limit=10)

            if not versions:
                print("暂无版本记录")
                return

            print(f"{'版本号':<8} {'创建时间':<20} {'优化方法':<12} {'状态':<8} {'评分':<8}")
            print("-" * 60)

            for version in versions:
                status = " 激活" if version.is_active else "未激活"
                score = "N/A"
                if version.performance_metrics:
                    score = f"{version.performance_metrics.overall_score:.3f}"

                print(f"{version.version_number:<8} {version.created_time[:19]:<20} "
                      f"{version.optimization_method:<12} {status:<8} {score:<8}")

        except Exception as e:
            print(f" 获取版本信息失败: {e}")

    def activate_version(self, pattern_name: str, version_number: int):
        """激活指定版本"""
        if not pattern_name or version_number is None:
            print("请指定形态名称和版本号")
            return

        print(f"激活版本: {pattern_name} v{version_number}")

        try:
            success = self.version_manager.rollback_to_version(
                pattern_name, version_number)

            if success:
                print(f" 版本 {version_number} 已激活")
            else:
                print(f" 激活失败")

        except Exception as e:
            print(f" 激活版本失败: {e}")

    def rollback_version(self, pattern_name: str, version_number: int):
        """回滚到指定版本"""
        self.activate_version(pattern_name, version_number)

    def export_data(self, pattern_name: str = None, output_path: str = None):
        """导出数据"""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"exports/optimization_export_{timestamp}.json"

        # 确保导出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        print(f" 导出数据到: {output_path}")

        try:
            export_data = {
                "export_time": datetime.now().isoformat(),
                "system_stats": self.db_manager.get_optimization_statistics(),
                "patterns": []
            }

            # 获取形态列表
            patterns = self.pattern_manager.get_all_patterns()
            pattern_names = [p.english_name for p in patterns if p.is_active]

            if pattern_name:
                pattern_names = [
                    pattern_name] if pattern_name in pattern_names else []

            # 导出每个形态的数据
            for name in pattern_names:
                pattern_data = {
                    "name": name,
                    "versions": [],
                    "performance_history": []
                }

                # 版本信息
                versions = self.version_manager.get_versions(name, limit=5)
                for version in versions:
                    version_info = {
                        "version_number": version.version_number,
                        "created_time": version.created_time,
                        "optimization_method": version.optimization_method,
                        "is_active": version.is_active,
                        "description": version.description
                    }

                    if version.performance_metrics:
                        version_info["performance"] = {
                            "overall_score": version.performance_metrics.overall_score,
                            "signal_quality": version.performance_metrics.signal_quality,
                            "confidence_avg": version.performance_metrics.confidence_avg
                        }

                    pattern_data["versions"].append(version_info)

                # 性能历史
                history = self.db_manager.get_performance_history(
                    name, limit=10)
                pattern_data["performance_history"] = history

                export_data["patterns"].append(pattern_data)

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f" 导出完成，包含 {len(export_data['patterns'])} 个形态的数据")

        except Exception as e:
            print(f" 导出失败: {e}")

    def launch_dashboard(self):
        """启动仪表板"""
        print("启动优化仪表板...")

        try:
            run_dashboard()
        except Exception as e:
            print(f" 启动仪表板失败: {e}")

    def initialize_system(self):
        """初始化系统"""
        print("初始化优化系统...")

        try:
            # 初始化数据库
            self.db_manager.init_tables()

            # 检查形态管理器
            patterns = self.pattern_manager.get_all_patterns()
            print(f" 发现 {len(patterns)} 个形态")

            # 检查现有版本
            stats = self.db_manager.get_optimization_statistics()
            print(f" 现有版本数: {stats.get('total_versions', 0)}")

            print("系统初始化完成")

        except Exception as e:
            print(f" 系统初始化失败: {e}")

    def show_help(self):
        """显示帮助信息"""
        help_text = """
 HiKyuu 形态识别算法优化系统

可用命令:
  status              - 显示系统状态
  list                - 列出所有形态
  evaluate <pattern>  - 评估形态性能
  optimize <pattern>  - 优化单个形态
  batch_optimize      - 批量优化所有形态
  smart_optimize      - 智能优化
  versions <pattern>  - 显示形态版本历史
  activate <pattern> <version> - 激活指定版本
  export [pattern]    - 导出数据
  dashboard           - 启动图形界面仪表板
  init                - 初始化系统

示例:
  python main_controller.py evaluate hammer
  python main_controller.py optimize doji --method genetic --iterations 50
  python main_controller.py batch_optimize --method bayesian
  python main_controller.py dashboard
        """
        print(help_text)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="FactorWeave-Quant 形态识别算法优化系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 基本参数
    parser.add_argument("command", nargs="?", default="help",
                        help="要执行的命令")
    parser.add_argument("pattern", nargs="?",
                        help="形态名称")
    parser.add_argument("version", nargs="?", type=int,
                        help="版本号")

    # 可选参数
    parser.add_argument("--method", default="genetic",
                        choices=["genetic", "bayesian", "random", "gradient"],
                        help="优化方法")
    parser.add_argument("--iterations", type=int, default=30,
                        help="最大迭代次数")
    parser.add_argument("--datasets", type=int, default=3,
                        help="测试数据集数量")
    parser.add_argument("--threshold", type=float, default=0.7,
                        help="智能优化性能阈值")
    parser.add_argument("--target", type=float, default=0.1,
                        help="智能优化改进目标")
    parser.add_argument("--output", help="导出文件路径")
    parser.add_argument("--debug", action="store_true",
                        help="启用调试模式")

    args = parser.parse_args()

    # 特殊处理帮助命令
    if args.command in ["help", "--help", "-h"]:
        controller = OptimizationController()
        controller.show_help()
        return

    # 创建控制器并执行命令
    try:
        controller = OptimizationController(debug_mode=args.debug)
        controller.run_command_line(args)

    except KeyboardInterrupt:
        print("\n  操作被用户中断")
    except Exception as e:
        print(f" 执行失败: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
