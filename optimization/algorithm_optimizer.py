from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能算法优化器
使用遗传算法、贝叶斯优化等方法自动优化形态识别算法
"""

from analysis.pattern_base import PatternConfig
from analysis.pattern_manager import PatternManager
from optimization.version_manager import VersionManager
import random
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional, Callable
from datetime import datetime
import json
import re
import traceback
from dataclasses import dataclass

# 导入性能指标类
from core.strategy_extensions import TradingPerformanceMetrics

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PerformanceEvaluator:
    """性能评估器"""

    def __init__(self, debug_mode: bool = False, pattern_manager: PatternManager = None):
        self.debug_mode = debug_mode
        self.pattern_manager = pattern_manager or PatternManager()

    def create_test_datasets(self, *args, **kwargs):
        """创建测试数据集"""
        # 简单的测试数据集创建逻辑
        return []

    def _convert_patterns_to_signals(self, pattern_results: List['PatternResult'], data: pd.DataFrame) -> pd.DataFrame:
        """
        将形态识别结果转换为交易信号

        Args:
            pattern_results: 形态识别结果列表
            data: K线数据

        Returns:
            包含交易信号的DataFrame
        """
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0  # 0: 无信号, 1: 买入, -1: 卖出

        signal_col = signals.columns.get_loc('signal')
        signal_values = signals.iloc[:, signal_col].values.astype(float)

        pattern_indices = set()
        for result in pattern_results:
            if result.index < len(signals):
                if result.signal_type.value == 'buy':
                    signal_values[result.index] = 1
                    pattern_indices.add(result.index)
                elif result.signal_type.value == 'sell':
                    signal_values[result.index] = -1
                    pattern_indices.add(result.index)

        current_position = 0
        holding_periods = 0
        max_holding_periods = 5

        for i in range(len(signals)):
            if i in pattern_indices:
                signal = signal_values[i]
                
                if signal == 1 and current_position == 0:
                    current_position = 1
                    holding_periods = 0
                elif signal == -1 and current_position == 1:
                    current_position = 0
                    holding_periods = 0
            elif current_position == 1:
                holding_periods += 1
                if holding_periods >= max_holding_periods:
                    signal_values[i] = -1
                    current_position = 0
                    holding_periods = 0

        signals.iloc[:, signal_col] = signal_values
        return signals

    def evaluate_algorithm(self, pattern_name: str, test_datasets: List[pd.DataFrame],
                         pattern_config: 'PatternConfig' = None) -> TradingPerformanceMetrics:
        """
        评估算法性能

        Args:
            pattern_name: 形态名称
            test_datasets: 测试数据集列表
            pattern_config: 可选的形态配置，如果提供则使用此配置而不是从数据库获取

        Returns:
            性能指标
        """
        try:
            # 获取形态配置（如果未提供）
            if pattern_config is None:
                pattern_config = self.pattern_manager.get_pattern_by_name(pattern_name)
                if not pattern_config:
                    logger.warning(f"未找到形态配置: {pattern_name}")
                    return self._create_default_metrics()
            else:
                logger.debug(f"使用提供的形态配置: {pattern_config.name}")

            # 创建形态识别器
            from analysis.pattern_recognition import PatternRecognizer
            recognizer = PatternRecognizer(pattern_config)

            # 评估所有测试数据集
            all_results = []
            all_confidences = []
            all_signals = []

            # 尝试使用回测评估
            try:
                # 合并所有测试数据集
                combined_data = pd.concat(test_datasets, ignore_index=True)
                combined_data = combined_data.reset_index(drop=True)

                # 识别形态
                results = recognizer.recognize(combined_data)
                all_results.extend(results)

                # 收集置信度和信号
                for result in results:
                    all_confidences.append(result.confidence)
                    all_signals.append(result.signal_type.value)

                # 转换为交易信号
                signals = self._convert_patterns_to_signals(results, combined_data)

                # 合并信号和价格数据
                backtest_data = combined_data.copy()
                backtest_data['signal'] = signals['signal']

                # 使用回测系统评估
                from backtest.unified_backtest_engine import UnifiedBacktestEngine
                # 强制使用标准引擎，因为形态识别结果转换为交易信号后，交易信号的数量通常较少
                # 标准引擎功能完整，能够计算所有性能指标，适合小数据集
                engine = UnifiedBacktestEngine(use_vectorized_engine=False, auto_select_engine=False)

                # 运行回测
                backtest_results = engine.run_backtest(backtest_data)

                # 从engine.metrics中获取性能指标
                if engine.metrics is None:
                    logger.warning("回测引擎未计算性能指标，使用置信度评估")
                    raise Exception("回测引擎未计算性能指标")

                # 提取性能指标
                total_return = engine.metrics.total_return
                annual_return = engine.metrics.annualized_return
                sharpe_ratio = engine.metrics.sharpe_ratio
                max_drawdown = engine.metrics.max_drawdown
                win_rate = engine.metrics.win_rate
                profit_factor = engine.metrics.profit_factor
                total_trades = len(engine.trades) if hasattr(engine, 'trades') and engine.trades else 0
                winning_trades = sum(1 for trade in engine.trades if hasattr(trade, 'pnl') and trade.pnl > 0) if hasattr(engine, 'trades') and engine.trades else 0
                losing_trades = total_trades - winning_trades
                avg_win = 0.0
                avg_loss = 0.0

                # 计算盈亏比
                if hasattr(engine, 'trades') and engine.trades:
                    wins = [trade.pnl for trade in engine.trades if hasattr(trade, 'pnl') and trade.pnl > 0]
                    losses = [abs(trade.pnl) for trade in engine.trades if hasattr(trade, 'pnl') and trade.pnl < 0]
                    avg_win = np.mean(wins) if wins else 0.0
                    avg_loss = np.mean(losses) if losses else 0.0

                # 计算置信度相关指标
                avg_confidence = np.mean(all_confidences) if all_confidences else 0.0
                std_confidence = np.std(all_confidences) if all_confidences else 0.0
                min_confidence = np.min(all_confidences) if all_confidences else 0.0
                max_confidence = np.max(all_confidences) if all_confidences else 0.0

                # 计算信号分布
                signal_counts = {}
                for signal in all_signals:
                    signal_counts[signal] = signal_counts.get(signal, 0) + 1

                # 计算overall_score（基于回测结果）
                overall_score = self._calculate_overall_score_from_backtest(
                    total_return, sharpe_ratio, max_drawdown, win_rate
                )

                # 创建性能指标
                metrics = TradingPerformanceMetrics(
                    total_return=total_return,
                    annual_return=annual_return,
                    sharpe_ratio=sharpe_ratio,
                    max_drawdown=max_drawdown,
                    win_rate=win_rate,
                    profit_factor=profit_factor,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=losing_trades,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    start_date=datetime.now(),
                    end_date=datetime.now(),
                    equity_curve=backtest_results.get('equity', None),
                    drawdown_curve=None,  # 暂时设为None，因为engine.metrics中没有drawdown_curve
                    metadata={
                        'pattern_name': pattern_name,
                        'avg_confidence': avg_confidence,
                        'std_confidence': std_confidence,
                        'min_confidence': min_confidence,
                        'max_confidence': max_confidence,
                        'signal_counts': signal_counts,
                        'test_datasets_count': len(test_datasets),
                        'total_patterns': len(all_results)
                    },
                    overall_score=overall_score
                )

                logger.info(f"算法 {pattern_name} 评估完成（回测评估）:")
                logger.info(f"  识别数量: {len(all_results)}")
                logger.info(f"  总收益率: {total_return:.3f}")
                logger.info(f"  夏普比率: {sharpe_ratio:.3f}")
                logger.info(f"  最大回撤: {max_drawdown:.3f}")
                logger.info(f"  胜率: {win_rate:.3f}")
                logger.info(f"  Overall Score: {overall_score:.3f}")

                return metrics

            except Exception as e:
                logger.warning(f"回测评估失败，使用置信度评估: {e}")
                # 回退到置信度评估
                pass

            # 置信度评估（回退方案）
            for i, test_data in enumerate(test_datasets):
                if test_data is None or test_data.empty:
                    logger.warning(f"测试数据集 {i} 为空，跳过")
                    continue

                try:
                    # 识别形态
                    results = recognizer.recognize(test_data)
                    all_results.extend(results)

                    # 收集置信度和信号
                    for result in results:
                        all_confidences.append(result.confidence)
                        all_signals.append(result.signal_type.value)

                    logger.debug(f"测试数据集 {i}: 识别到 {len(results)} 个形态")

                except Exception as e:
                    logger.error(f"测试数据集 {i} 评估失败: {e}")
                    continue

            # 计算性能指标
            if not all_results:
                logger.warning(f"未识别到任何形态，返回默认指标")
                return self._create_default_metrics()

            # 计算置信度相关指标
            avg_confidence = np.mean(all_confidences)
            std_confidence = np.std(all_confidences)
            min_confidence = np.min(all_confidences)
            max_confidence = np.max(all_confidences)

            # 计算信号分布
            signal_counts = {}
            for signal in all_signals:
                signal_counts[signal] = signal_counts.get(signal, 0) + 1

            # 计算overall_score
            overall_score = self._calculate_overall_score(
                avg_confidence, std_confidence, len(all_results), len(test_datasets)
            )

            # 创建性能指标
            metrics = TradingPerformanceMetrics(
                total_return=0.0,
                annual_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=len(all_results),
                winning_trades=signal_counts.get('buy', 0),
                losing_trades=signal_counts.get('sell', 0),
                avg_win=avg_confidence,
                avg_loss=std_confidence,
                start_date=datetime.now(),
                end_date=datetime.now(),
                equity_curve=None,
                drawdown_curve=None,
                metadata={
                    'pattern_name': pattern_name,
                    'avg_confidence': avg_confidence,
                    'std_confidence': std_confidence,
                    'min_confidence': min_confidence,
                    'max_confidence': max_confidence,
                    'signal_counts': signal_counts,
                    'test_datasets_count': len(test_datasets),
                    'total_patterns': len(all_results)
                },
                overall_score=overall_score
            )

            logger.info(f"算法 {pattern_name} 评估完成（置信度评估）:")
            logger.info(f"  识别数量: {len(all_results)}")
            logger.info(f"  平均置信度: {avg_confidence:.3f}")
            logger.info(f"  置信度标准差: {std_confidence:.3f}")
            logger.info(f"  Overall Score: {overall_score:.3f}")

            return metrics

        except Exception as e:
            logger.error(f"算法评估失败: {e}")
            logger.error(traceback.format_exc())
            return self._create_default_metrics()

    def _calculate_overall_score(self, avg_confidence: float, std_confidence: float,
                                 pattern_count: int, dataset_count: int) -> float:
        """
        计算overall_score

        Args:
            avg_confidence: 平均置信度
            std_confidence: 置信度标准差
            pattern_count: 识别的形态数量
            dataset_count: 测试数据集数量

        Returns:
            overall_score
        """
        # 基于置信度的评分（0-1）
        confidence_score = avg_confidence

        # 基于置信度稳定性的评分（标准差越小，评分越高）
        stability_score = 1.0 - min(std_confidence, 1.0)

        # 基于识别数量的评分（每个数据集至少识别1个形态）
        density_score = min(pattern_count / max(dataset_count, 1), 1.0)

        # 综合评分（加权平均）
        overall_score = (
            0.5 * confidence_score +
            0.3 * stability_score +
            0.2 * density_score
        )

        return overall_score

    def _calculate_overall_score_from_backtest(self, total_return: float, sharpe_ratio: float,
                                               max_drawdown: float, win_rate: float) -> float:
        """
        基于回测结果计算overall_score

        Args:
            total_return: 总收益率
            sharpe_ratio: 夏普比率
            max_drawdown: 最大回撤
            win_rate: 胜率

        Returns:
            overall_score
        """
        # 基于收益率的评分（0-1）
        return_score = min(max(total_return, 0) / 0.5, 1.0)

        # 基于夏普比率的评分（0-1）
        sharpe_score = min(max(sharpe_ratio, 0) / 2.0, 1.0)

        # 基于最大回撤的评分（回撤越小，评分越高）
        drawdown_score = 1.0 - min(abs(max_drawdown), 1.0)

        # 基于胜率的评分（0-1）
        win_rate_score = win_rate

        # 综合评分（加权平均）
        overall_score = (
            0.3 * return_score +
            0.3 * sharpe_score +
            0.2 * drawdown_score +
            0.2 * win_rate_score
        )

        return overall_score

    def _create_default_metrics(self) -> TradingPerformanceMetrics:
        """创建默认的性能指标"""
        return TradingPerformanceMetrics(
            total_return=0.0,
            annual_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_win=0.0,
            avg_loss=0.0,
            start_date=datetime.now(),
            end_date=datetime.now(),
            equity_curve=None,
            drawdown_curve=None,
            metadata={},
            overall_score=0.0
        )


@dataclass
class OptimizationConfig:
    """优化配置"""
    method: str = "genetic"  # genetic, bayesian, random, gradient
    max_iterations: int = 50
    population_size: int = 20
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    target_metric: str = "overall_score"
    min_improvement: float = 0.05
    timeout_minutes: int = 30
    parallel_workers: int = 4


class AlgorithmOptimizer:
    """智能算法优化器"""

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.pattern_manager = PatternManager()
        self.version_manager = VersionManager()
        self.evaluator = PerformanceEvaluator(debug_mode, self.pattern_manager)

        # 优化历史
        self.optimization_history = []

    def optimize_algorithm(self, pattern_name: str,
                           config: OptimizationConfig = None,
                           test_datasets: List[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        优化指定形态的算法

        Args:
            pattern_name: 形态名称
            config: 优化配置
            test_datasets: 测试数据集

        Returns:
            优化结果
        """
        if config is None:
            config = OptimizationConfig()

        logger.info(f" 开始优化算法: {pattern_name}")
        logger.info(f" 优化方法: {config.method}")
        logger.info(f"目标指标: {config.target_metric}")

        # 获取当前算法配置
        pattern_config = self.pattern_manager.get_pattern_by_name(pattern_name)
        if not pattern_config:
            raise ValueError(f"未找到形态配置: {pattern_name}")

        # 创建测试数据集（如果没有提供）
        if test_datasets is None:
            test_datasets = self.evaluator.create_test_datasets(
                pattern_name, count=5)

        # 评估基准性能
        baseline_metrics = self.evaluator.evaluate_algorithm(
            pattern_name, test_datasets
        )

        logger.info(f"基准性能: {baseline_metrics.overall_score:.3f}")

        # 开始优化日志
        session_id = self.version_manager.db_manager.start_optimization_log(
            pattern_name=pattern_name,
            optimization_method=config.method,
            initial_version_id=0,  # 需要获取当前版本ID
            config=config.__dict__
        )

        try:
            # 根据优化方法选择优化策略
            if config.method == "genetic":
                result = self._genetic_optimization(
                    pattern_name, pattern_config, config, test_datasets, baseline_metrics
                )
            elif config.method == "bayesian":
                result = self._bayesian_optimization(
                    pattern_name, pattern_config, config, test_datasets, baseline_metrics
                )
            elif config.method == "random":
                result = self._random_optimization(
                    pattern_name, pattern_config, config, test_datasets, baseline_metrics
                )
            elif config.method == "gradient":
                result = self._gradient_optimization(
                    pattern_name, pattern_config, config, test_datasets, baseline_metrics
                )
            else:
                raise ValueError(f"不支持的优化方法: {config.method}")

            # 更新优化日志
            self.version_manager.db_manager.update_optimization_log(
                session_id=session_id,
                status="completed",
                final_version_id=result.get('best_version_id'),
                iterations=result.get('iterations', 0),
                best_score=result.get('best_score', 0),
                improvement_percentage=result.get('improvement_percentage', 0),
                optimization_log=json.dumps(result.get('optimization_log', []))
            )

            logger.info("优化完成！")
            logger.info(f"性能提升: {result.get('improvement_percentage', 0):.3f}%")

            return result

        except Exception as e:
            # 更新优化日志为失败状态
            self.version_manager.db_manager.update_optimization_log(
                session_id=session_id,
                status="failed",
                error_message=str(e)
            )
            raise e

    def _genetic_optimization(self, pattern_name: str, pattern_config,
                              config: OptimizationConfig, test_datasets: List[pd.DataFrame],
                              baseline_metrics: TradingPerformanceMetrics) -> Dict[str, Any]:
        """遗传算法优化"""
        logger.info("使用遗传算法优化...")

        # 初始化种群
        population = self._initialize_population(
            pattern_config, config.population_size)

        best_individual = None
        best_score = baseline_metrics.overall_score
        optimization_log = []

        for generation in range(config.max_iterations):
            logger.info(f"  第 {generation + 1}/{config.max_iterations} 代")

            # 评估种群
            fitness_scores = []
            for individual in population:
                try:
                    # 创建临时算法配置
                    temp_config = self._create_temp_config(
                        pattern_config, individual)

                    # 评估性能
                    metrics = self._evaluate_individual(
                        temp_config, test_datasets)
                    score = getattr(metrics, config.target_metric, 0)
                    fitness_scores.append(score)

                    # 更新最佳个体
                    if score > best_score:
                        best_score = score
                        best_individual = individual.copy()

                        logger.info(f"   发现更好的解: {score:.3f}")

                except Exception as e:
                    if self.debug_mode:
                        logger.info(f"     个体评估失败: {e}")
                    fitness_scores.append(0.0)

            # 记录当代最佳
            generation_best = max(fitness_scores) if fitness_scores else 0
            optimization_log.append({
                "generation": generation + 1,
                "best_score": generation_best,
                "avg_score": np.mean(fitness_scores) if fitness_scores else 0,
                "population_diversity": self._calculate_diversity(population)
            })

            # 检查收敛条件
            if generation_best - baseline_metrics.overall_score < config.min_improvement:
                if generation > 10:  # 至少运行10代
                    logger.info(f"     收敛，提前停止")
                    break

            # 选择、交叉、变异
            population = self._evolve_population(
                population, fitness_scores, config
            )

        # 保存最佳版本
        best_version_id = None
        if best_individual:
            best_version_id = self._save_optimized_version(
                pattern_name, pattern_config, best_individual,
                f"遗传算法优化 - 第{len(optimization_log)}代", best_score
            )

        improvement_percentage = 0.0
        if baseline_metrics.overall_score > 0:
            improvement_percentage = (
                best_score - baseline_metrics.overall_score) / baseline_metrics.overall_score * 100

        return {
            "method": "genetic",
            "best_score": best_score,
            "baseline_score": baseline_metrics.overall_score,
            "improvement_percentage": improvement_percentage,
            "iterations": len(optimization_log),
            "best_version_id": best_version_id,
            "optimization_log": optimization_log
        }

    def _bayesian_optimization(self, pattern_name: str, pattern_config,
                               config: OptimizationConfig, test_datasets: List[pd.DataFrame],
                               baseline_metrics: TradingPerformanceMetrics) -> Dict[str, Any]:
        """启发式参数搜索（基于探索-利用）"""
        logger.info("使用启发式参数搜索（基于探索-利用）...")

        # 启发式参数搜索实现
        # 使用探索-利用平衡策略（非标准GP+EI贝叶斯优化）

        best_individual = None
        best_score = baseline_metrics.overall_score
        optimization_log = []

        # 参数空间定义
        param_space = self._define_parameter_space(pattern_config)

        # 启发式搜索参数
        exploration_rate = 0.5  # 探索率
        exploitation_rate = 0.5  # 利用率
        local_search_radius = 0.15  # 局部搜索半径
        diversity_bonus = 0.1  # 多样性奖励

        # 历史记录
        history = []

        for iteration in range(config.max_iterations):
            logger.info(f"  第 {iteration + 1}/{config.max_iterations} 次迭代")

            # 改进的采样策略
            if iteration < 3:
                # 前几次随机采样，建立初始模型
                individual = self._random_sample_parameters(param_space)
            else:
                # 基于历史结果选择有希望的区域
                if np.random.random() < exploration_rate:
                    # 探索阶段：全局随机采样
                    individual = self._random_sample_parameters(param_space)
                else:
                    # 利用阶段：基于历史结果采样
                    individual = self._bayesian_sample_parameters_improved(
                        param_space, history, exploitation_rate, local_search_radius, diversity_bonus)

            try:
                # 评估参数组合
                temp_config = self._create_temp_config(
                    pattern_config, individual)
                metrics = self._evaluate_individual(temp_config, test_datasets)
                score = getattr(metrics, config.target_metric, 0)

                # 记录结果
                optimization_log.append({
                    "iteration": iteration + 1,
                    "parameters": individual,
                    "score": score
                })

                # 更新历史
                history.append({'params': individual.copy(), 'score': score})
                if len(history) > 20:
                    history.pop(0)

                # 更新最佳结果
                if score > best_score:
                    best_score = score
                    best_individual = individual.copy()
                    logger.info(f"   发现更好的解: {score:.3f}")

            except Exception as e:
                if self.debug_mode:
                    logger.info(f"     参数评估失败: {e}")
                optimization_log.append({
                    "iteration": iteration + 1,
                    "parameters": individual,
                    "score": 0.0,
                    "error": str(e)
                })

        # 保存最佳版本
        best_version_id = None
        if best_individual:
            best_version_id = self._save_optimized_version(
                pattern_name, pattern_config, best_individual,
                f"启发式参数搜索（探索-利用） - {len(optimization_log)}次迭代", best_score
            )

        improvement_percentage = 0.0
        if baseline_metrics.overall_score > 0:
            improvement_percentage = (
                best_score - baseline_metrics.overall_score) / baseline_metrics.overall_score * 100

        return {
            "method": "bayesian",
            "best_score": best_score,
            "baseline_score": baseline_metrics.overall_score,
            "improvement_percentage": improvement_percentage,
            "iterations": len(optimization_log),
            "best_version_id": best_version_id,
            "optimization_log": optimization_log
        }

    def _random_optimization(self, pattern_name: str, pattern_config,
                             config: OptimizationConfig, test_datasets: List[pd.DataFrame],
                             baseline_metrics: TradingPerformanceMetrics) -> Dict[str, Any]:
        """随机搜索优化（改进版）"""
        logger.info("使用随机搜索优化（改进版）...")

        best_individual = None
        best_score = baseline_metrics.overall_score
        optimization_log = []

        param_space = self._define_parameter_space(pattern_config)

        # 改进的随机搜索参数
        exploration_rate = 0.7  # 探索率
        exploitation_rate = 0.3  # 利用率
        local_search_radius = 0.1  # 局部搜索半径
        diversity_threshold = 0.5  # 多样性阈值

        # 历史最优解
        history = []

        for iteration in range(config.max_iterations):
            logger.info(f"  第 {iteration + 1}/{config.max_iterations} 次尝试")

            # 改进的采样策略
            if iteration == 0 or np.random.random() < exploration_rate:
                # 探索阶段：全局随机采样
                individual = self._random_sample_parameters(param_space)
            else:
                # 利用阶段：局部搜索或历史最优
                if history and np.random.random() < exploitation_rate:
                    # 从历史最优解中选择一个进行局部搜索
                    best_in_history = max(history, key=lambda x: x['score'])
                    individual = self._local_search(best_in_history['params'], param_space, local_search_radius)
                else:
                    # 全局随机采样
                    individual = self._random_sample_parameters(param_space)

            try:
                temp_config = self._create_temp_config(
                    pattern_config, individual)
                metrics = self._evaluate_individual(temp_config, test_datasets)
                score = getattr(metrics, config.target_metric, 0)

                optimization_log.append({
                    "iteration": iteration + 1,
                    "parameters": individual,
                    "score": score
                })

                # 更新历史
                history.append({'params': individual.copy(), 'score': score})
                if len(history) > 10:
                    history.pop(0)

                if score > best_score:
                    best_score = score
                    best_individual = individual.copy()
                    logger.info(f"   发现更好的解: {score:.3f}")

            except Exception as e:
                if self.debug_mode:
                    logger.info(f"     参数评估失败: {e}")

        # 保存最佳版本
        best_version_id = None
        if best_individual:
            best_version_id = self._save_optimized_version(
                pattern_name, pattern_config, best_individual,
                f"随机搜索优化(改进版) - {len(optimization_log)}次尝试", best_score
            )

        improvement_percentage = 0.0
        if baseline_metrics.overall_score > 0:
            improvement_percentage = (
                best_score - baseline_metrics.overall_score) / baseline_metrics.overall_score * 100

        return {
            "method": "random",
            "best_score": best_score,
            "baseline_score": baseline_metrics.overall_score,
            "improvement_percentage": improvement_percentage,
            "iterations": len(optimization_log),
            "best_version_id": best_version_id,
            "optimization_log": optimization_log
        }

    def _local_search(self, center_params: Dict[str, Any], param_space: Dict[str, Dict], radius: float) -> Dict[str, Any]:
        """局部搜索
        
        Args:
            center_params: 中心参数
            param_space: 参数空间
            radius: 搜索半径
            
        Returns:
            局部搜索后的参数
        """
        local_params = center_params.copy()
        
        for param_name, param_value in center_params.items():
            if param_name in param_space:
                param_range = param_space[param_name]
                min_val = param_range.get('min', 0.0)
                max_val = param_range.get('max', 1.0)
                
                # 在中心参数附近进行局部搜索
                delta = (max_val - min_val) * radius
                new_value = param_value + np.random.uniform(-delta, delta)
                
                # 确保在参数范围内
                local_params[param_name] = max(min_val, min(max_val, new_value))
        
        return local_params

    def _gradient_optimization(self, pattern_name: str, pattern_config,
                               config: OptimizationConfig, test_datasets: List[pd.DataFrame],
                               baseline_metrics: TradingPerformanceMetrics) -> Dict[str, Any]:
        """梯度优化（基于scipy.optimize.minimize L-BFGS-B）"""
        from scipy.optimize import minimize

        logger.info("↑ 使用scipy.optimize.minimize (L-BFGS-B) 梯度优化...")

        current_params = self._extract_numeric_parameters(pattern_config)
        param_names = list(current_params.keys())
        x0 = np.array([current_params[name] for name in param_names], dtype=float)
        bounds = [(0.001, 100.0) for _ in param_names]
        best_score = baseline_metrics.overall_score
        optimization_log = []

        def objective(x):
            params = {name: float(x[i]) for i, name in enumerate(param_names)}
            score = self._evaluate_params(pattern_config, params, test_datasets, config.target_metric)
            optimization_log.append({
                "iteration": len(optimization_log) + 1,
                "parameters": params.copy(),
                "score": score,
                "method": "L-BFGS-B"
            })
            return -score

        logger.info(f"  初始参数: {current_params}")
        logger.info(f"  基准评分: {best_score:.3f}")

        result = minimize(
            objective,
            x0,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': config.max_iterations, 'disp': False}
        )

        optimized_params = {name: float(result.x[i]) for i, name in enumerate(param_names)}
        optimized_score = -result.fun if result.success else best_score

        if result.success and optimized_score > best_score:
            best_score = optimized_score
        else:
            optimized_params = current_params

        logger.info(f"  优化完成: success={result.success}, nit={result.nit}, nfev={result.nfev}, 最佳评分={best_score:.3f}")

        best_version_id = self._save_optimized_version(
            pattern_name, pattern_config, optimized_params,
            f"scipy L-BFGS-B优化 - {len(optimization_log)}次迭代", best_score
        )

        improvement_percentage = 0.0
        if baseline_metrics.overall_score > 0:
            improvement_percentage = (
                best_score - baseline_metrics.overall_score) / baseline_metrics.overall_score * 100

        return {
            "method": "scipy_L-BFGS-B",
            "best_score": best_score,
            "baseline_score": baseline_metrics.overall_score,
            "improvement_percentage": improvement_percentage,
            "iterations": len(optimization_log),
            "best_version_id": best_version_id,
            "optimization_log": optimization_log,
            "scipy_result": {
                "success": result.success,
                "nit": result.nit,
                "nfev": result.nfev,
                "message": result.message
            }
        }

    def _initialize_population(self, pattern_config, population_size: int) -> List[Dict[str, Any]]:
        """初始化遗传算法种群"""
        population = []
        param_space = self._define_parameter_space(pattern_config)

        for _ in range(population_size):
            individual = self._random_sample_parameters(param_space)
            population.append(individual)

        return population

    def _define_parameter_space(self, pattern_config) -> Dict[str, Dict[str, Any]]:
        """定义参数搜索空间"""
        param_space = {}

        # 从算法代码中提取可优化的参数
        if pattern_config.parameters:
            for param_name, param_value in pattern_config.parameters.items():
                if isinstance(param_value, (int, float)):
                    param_space[param_name] = {
                        "type": "numeric",
                        "min": param_value * 0.5,
                        "max": param_value * 2.0,
                        "current": param_value
                    }
                elif isinstance(param_value, bool):
                    param_space[param_name] = {
                        "type": "boolean",
                        "current": param_value
                    }

        # 添加通用的形态识别参数
        param_space.update({
            "confidence_threshold": {
                "type": "numeric",
                "min": 0.1,
                "max": 0.9,
                "current": pattern_config.confidence_threshold
            },
            "min_body_ratio": {
                "type": "numeric",
                "min": 0.1,
                "max": 0.8,
                "current": 0.3
            },
            "shadow_ratio_threshold": {
                "type": "numeric",
                "min": 1.5,
                "max": 4.0,
                "current": 2.0
            }
        })

        return param_space

    def _random_sample_parameters(self, param_space: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """随机采样参数"""
        individual = {}

        for param_name, param_info in param_space.items():
            if param_info["type"] == "numeric":
                value = random.uniform(param_info["min"], param_info["max"])
                individual[param_name] = value
            elif param_info["type"] == "boolean":
                individual[param_name] = random.choice([True, False])

        return individual

    def _bayesian_sample_parameters(self, param_space: Dict[str, Dict[str, Any]],
                                    history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """基于贝叶斯优化采样参数（简化版本）"""
        # 这是一个简化的实现，实际应用中应该使用专业的贝叶斯优化库

        if len(history) < 3:
            return self._random_sample_parameters(param_space)

        # 找到历史最佳参数
        best_entry = max(history, key=lambda x: x.get("score", 0))
        best_params = best_entry.get("parameters", {})

        # 在最佳参数附近采样
        individual = {}
        for param_name, param_info in param_space.items():
            if param_info["type"] == "numeric":
                if param_name in best_params:
                    # 在最佳值附近添加噪声
                    best_value = best_params[param_name]
                    noise_scale = (param_info["max"] - param_info["min"]) * 0.1
                    value = best_value + random.gauss(0, noise_scale)
                    value = max(param_info["min"], min(
                        param_info["max"], value))
                else:
                    value = random.uniform(
                        param_info["min"], param_info["max"])
                individual[param_name] = value
            elif param_info["type"] == "boolean":
                if param_name in best_params:
                    # 80%概率保持最佳值
                    if random.random() < 0.8:
                        individual[param_name] = best_params[param_name]
                    else:
                        individual[param_name] = not best_params[param_name]
                else:
                    individual[param_name] = random.choice([True, False])

        return individual

    def _bayesian_sample_parameters_improved(self, param_space: Dict[str, Dict[str, Any]],
                                           history: List[Dict[str, Any]],
                                           exploitation_rate: float,
                                           local_search_radius: float,
                                           diversity_bonus: float) -> Dict[str, Any]:
        """改进的贝叶斯采样参数
        
        Args:
            param_space: 参数空间
            history: 历史记录
            exploitation_rate: 利用率
            local_search_radius: 局部搜索半径
            diversity_bonus: 多样性奖励
            
        Returns:
            采样的参数
        """
        if len(history) < 3:
            return self._random_sample_parameters(param_space)

        # 找到历史最佳参数
        best_entry = max(history, key=lambda x: x.get("score", 0))
        best_params = best_entry.get("params", {})

        # 计算多样性奖励
        diversity_scores = {}
        for i, entry in enumerate(history):
            diversity_score = 0.0
            for j, other_entry in enumerate(history):
                if i != j:
                    # 计算参数之间的距离
                    distance = 0.0
                    for param_name, param_info in param_space.items():
                        if param_info["type"] == "numeric":
                            val1 = entry["params"].get(param_name, 0)
                            val2 = other_entry["params"].get(param_name, 0)
                            param_range = param_info["max"] - param_info["min"]
                            if param_range > 0:
                                distance += abs(val1 - val2) / param_range
                    diversity_score += distance
            diversity_scores[i] = diversity_score

        # 选择采样策略
        if np.random.random() < exploitation_rate:
            # 利用阶段：基于历史结果采样
            if np.random.random() < 0.7:
                # 在最佳参数附近采样
                individual = {}
                for param_name, param_info in param_space.items():
                    if param_info["type"] == "numeric":
                        if param_name in best_params:
                            best_value = best_params[param_name]
                            noise_scale = (param_info["max"] - param_info["min"]) * local_search_radius
                            value = best_value + np.random.normal(0, noise_scale)
                            value = max(param_info["min"], min(param_info["max"], value))
                        else:
                            value = np.random.uniform(param_info["min"], param_info["max"])
                        individual[param_name] = value
                    elif param_info["type"] == "boolean":
                        if param_name in best_params:
                            if np.random.random() < 0.8:
                                individual[param_name] = best_params[param_name]
                            else:
                                individual[param_name] = not best_params[param_name]
                        else:
                            individual[param_name] = np.random.choice([True, False])
            else:
                # 基于多样性奖励采样
                max_diversity_idx = max(diversity_scores.keys(), key=lambda x: diversity_scores[x])
                diversity_entry = history[max_diversity_idx]
                individual = diversity_entry["params"].copy()
        else:
            # 探索阶段：全局随机采样
            individual = self._random_sample_parameters(param_space)

        return individual

    def _create_temp_config(self, base_config, parameters: Dict[str, Any]):
        """创建临时配置"""
        from dataclasses import replace
        # 使用dataclass的replace方法创建一个新的对象
        temp_config = replace(base_config, parameters=parameters)
        return temp_config

    def _evaluate_individual(self, config, test_datasets: List[pd.DataFrame]) -> TradingPerformanceMetrics:
        """评估个体性能"""
        # 直接使用提供的配置进行评估
        return self.evaluator.evaluate_algorithm(
            config.english_name, test_datasets, pattern_config=config
        )

    def _evaluate_params(self, pattern_config, parameters: Dict[str, Any],
                         test_datasets: List[pd.DataFrame], target_metric: str) -> float:
        """评估参数组合"""
        try:
            temp_config = self._create_temp_config(pattern_config, parameters)
            metrics = self._evaluate_individual(temp_config, test_datasets)
            return getattr(metrics, target_metric, 0)
        except Exception:
            return 0.0

    def _evolve_population(self, population: List[Dict[str, Any]],
                           fitness_scores: List[float],
                           config: OptimizationConfig) -> List[Dict[str, Any]]:
        """进化种群"""
        new_population = []

        # 精英保留
        elite_count = max(1, int(config.population_size * 0.1))
        elite_indices = sorted(range(len(fitness_scores)),
                               key=lambda i: fitness_scores[i], reverse=True)[:elite_count]

        for idx in elite_indices:
            new_population.append(population[idx].copy())

        # 生成新个体
        while len(new_population) < config.population_size:
            # 选择父母
            parent1 = self._tournament_selection(population, fitness_scores)
            parent2 = self._tournament_selection(population, fitness_scores)

            # 交叉
            if random.random() < config.crossover_rate:
                child1, child2 = self._crossover(parent1, parent2)
            else:
                child1, child2 = parent1.copy(), parent2.copy()

            # 变异
            if random.random() < config.mutation_rate:
                child1 = self._mutate(child1)
            if random.random() < config.mutation_rate:
                child2 = self._mutate(child2)

            new_population.extend([child1, child2])

        return new_population[:config.population_size]

    def _tournament_selection(self, population: List[Dict[str, Any]],
                              fitness_scores: List[float], tournament_size: int = 3) -> Dict[str, Any]:
        """锦标赛选择"""
        tournament_indices = random.sample(range(len(population)),
                                           min(tournament_size, len(population)))
        best_idx = max(tournament_indices, key=lambda i: fitness_scores[i])
        return population[best_idx].copy()

    def _crossover(self, parent1: Dict[str, Any], parent2: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """交叉操作"""
        child1 = parent1.copy()
        child2 = parent2.copy()

        # 对每个参数进行交叉
        for key in parent1.keys():
            if random.random() < 0.5:
                child1[key], child2[key] = child2[key], child1[key]

        return child1, child2

    def _mutate(self, individual: Dict[str, Any]) -> Dict[str, Any]:
        """变异操作"""
        mutated = individual.copy()

        for key, value in mutated.items():
            if random.random() < 0.1:  # 10%的参数发生变异
                if isinstance(value, float):
                    # 高斯变异
                    noise = random.gauss(0, abs(value) * 0.1 + 0.01)
                    mutated[key] = max(0.01, value + noise)
                elif isinstance(value, bool):
                    mutated[key] = not value

        return mutated

    def _calculate_diversity(self, population: List[Dict[str, Any]]) -> float:
        """计算种群多样性"""
        if len(population) < 2:
            return 0.0

        # 简化的多样性计算
        total_distance = 0
        count = 0

        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                distance = self._calculate_individual_distance(
                    population[i], population[j])
                total_distance += distance
                count += 1

        return total_distance / count if count > 0 else 0.0

    def _calculate_individual_distance(self, ind1: Dict[str, Any], ind2: Dict[str, Any]) -> float:
        """计算个体间距离"""
        distance = 0.0
        common_keys = set(ind1.keys()) & set(ind2.keys())

        for key in common_keys:
            val1, val2 = ind1[key], ind2[key]
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                distance += abs(val1 - val2)
            elif isinstance(val1, bool) and isinstance(val2, bool):
                distance += 0 if val1 == val2 else 1

        return distance

    def _extract_numeric_parameters(self, pattern_config) -> Dict[str, float]:
        """提取数值参数"""
        numeric_params = {}

        if pattern_config.parameters:
            for key, value in pattern_config.parameters.items():
                if isinstance(value, (int, float)):
                    numeric_params[key] = float(value)

        # 添加默认参数
        numeric_params.update({
            "confidence_threshold": pattern_config.confidence_threshold,
            "min_body_ratio": 0.3,
            "shadow_ratio_threshold": 2.0
        })

        return numeric_params

    def _save_optimized_version(self, pattern_name: str, base_config,
                                optimized_params: Dict[str, Any],
                                description: str, score: float) -> int:
        """保存优化后的版本"""
        # 生成优化后的算法代码
        optimized_code = self._generate_optimized_code(
            base_config, optimized_params)

        # 保存版本
        version_id = self.version_manager.save_version(
            pattern_id=0,  # 需要获取正确的pattern_id
            pattern_name=pattern_name,
            algorithm_code=optimized_code,
            parameters=optimized_params,
            description=description,
            optimization_method="auto_optimization",
            created_by="auto_optimization"
        )

        return version_id

    def _generate_optimized_code(self, base_config, optimized_params: Dict[str, Any]) -> str:
        """生成优化后的算法代码"""
        # 这里需要实现代码生成逻辑
        # 简化版本：返回原始代码并更新参数

        original_code = base_config.algorithm_code

        # 替换参数值
        optimized_code = original_code
        for param_name, param_value in optimized_params.items():
            # 简单的字符串替换（实际应该使用AST解析）
            pattern = f"{param_name}\\s*=\\s*[\\d\\.]+|{param_name}\\s*=\\s*True|{param_name}\\s*=\\s*False"
            replacement = f"{param_name} = {param_value}"
            optimized_code = re.sub(pattern, replacement, optimized_code)

        return optimized_code


def create_algorithm_optimizer(debug_mode: bool = False) -> AlgorithmOptimizer:
    """创建算法优化器实例"""
    return AlgorithmOptimizer(debug_mode=debug_mode)


if __name__ == "__main__":
    # 测试算法优化器
    optimizer = create_algorithm_optimizer(debug_mode=True)

    # 创建优化配置
    config = OptimizationConfig(
        method="genetic",
        max_iterations=10,
        population_size=5
    )

    # 优化锤头线算法
    result = optimizer.optimize_algorithm("hammer", config)

    logger.info(f"\n优化结果:")
    logger.info(f"  方法: {result['method']}")
    logger.info(f"  最佳评分: {result['best_score']:.3f}")
    logger.info(f"  基准评分: {result['baseline_score']:.3f}")
    logger.info(f"  性能提升: {result['improvement_percentage']:.3f}%")
    logger.info(f"  迭代次数: {result['iterations']}")
    logger.info(f"  最佳版本ID: {result['best_version_id']}")
