#!/usr/bin/env python3
"""
策略执行引擎

提供高性能的策略执行、缓存管理和结果存储功能
集成数据库存储，使用系统统一组件
"""

import time
import hashlib
import threading
from typing import Dict, List, Optional, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

# 使用系统统一组件
from core.system_adapters import get_config, get_performance_monitor
from .base_strategy import BaseStrategy, StrategySignal
from .strategy_registry import get_strategy_registry, StrategyRegistry
from .strategy_factory import get_strategy_factory
from core.performance import measure_performance

class StrategyEngine:
    """策略执行引擎"""

    def __init__(self, registry: StrategyRegistry = None, max_workers: int = None, cache_size: int = 1000, cache_ttl: int = 3600):
        """
        初始化策略执行引擎

        Args:
            registry: 策略注册器（可选，如果不提供则使用全局单例）
            max_workers: 最大工作线程数
            cache_size: 缓存大小（已弃用，使用统一缓存）
            cache_ttl: 缓存过期时间（已弃用，使用统一缓存）
        """
        self.logger = logger.bind(module=__name__)
        self.config = get_config()
        self.performance_monitor = get_performance_monitor()
        
        if registry is None:
            self.registry = get_strategy_registry()
        else:
            self.registry = registry

        self.database_service = None
        self._database_service_initialized = False

        engine_config = self.config.get('strategy_engine', {})
        self.max_workers = max_workers or engine_config.get('max_workers', 4)

        self._unified_cache_adapter = self._get_unified_cache_adapter()
        
        if self._unified_cache_adapter is not None:
            self.cache = self._unified_cache_adapter
            self.logger.info("使用统一缓存服务")
        else:
            from core.adapters.legacy_cache_adapter import StrategyCacheAdapter
            from core.services.cache_service import CacheService
            _fallback_cache = CacheService()
            _fallback_cache.initialize()
            self.cache = StrategyCacheAdapter(_fallback_cache, "strategy_fallback")
            self.logger.warning("统一缓存服务不可用，使用回退缓存")

        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        self._execution_stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_execution_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self._stats_lock = threading.Lock()
        self._strategy_update_lock = threading.RLock()

        self.logger.info(f"策略执行引擎初始化完成: max_workers={self.max_workers}")

    def _get_unified_cache_adapter(self):
        """获取统一缓存适配器"""
        try:
            from core.services.unified_cache_provider import get_strategy_cache
            return get_strategy_cache()
        except ImportError:
            self.logger.debug("统一缓存服务不可用，使用本地缓存")
            return None

    def _ensure_database_service(self):
        """确保DatabaseService已初始化"""
        if self._database_service_initialized:
            return
            
        try:
            from core.containers.service_container import get_service_container
            from core.services.database_service import DatabaseService
            container = get_service_container()
            self.database_service = container.resolve(DatabaseService)
            if self.database_service is not None:
                self._database_service_initialized = True
                self.logger.info("成功获取DatabaseService")
        except Exception as e:
            self.logger.warning(f"无法获取DatabaseService: {e}")
            self.database_service = None

    def execute_strategy(self, strategy_name: str, data: pd.DataFrame,
                         use_cache: bool = True, save_to_db: bool = True) -> Tuple[List[StrategySignal], Dict[str, Any]]:
        """
        执行单个策略

        Args:
            strategy_name: 策略名称
            data: 市场数据
            use_cache: 是否使用缓存
            save_to_db: 是否保存到数据库

        Returns:
            (信号列表, 执行信息)
        """
        start_time = time.time()
        execution_info = {
            'strategy_name': strategy_name,
            'start_time': datetime.now(),
            'success': False,
            'error_message': None,
            'execution_time': 0.0,
            'cache_hit': False,
            'signals_count': 0
        }

        try:
            # 生成数据哈希用于缓存
            data_hash = self._generate_data_hash(data)
            cache_key = f"{strategy_name}:{data_hash}"

            # 尝试从缓存获取结果
            if use_cache:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    execution_info['cache_hit'] = True
                    execution_info['success'] = True
                    execution_info['signals_count'] = len(cached_result)
                    execution_info['execution_time'] = time.time() - start_time

                    self._update_stats('cache_hit')
                    self.logger.debug(f"缓存命中: {strategy_name}")
                    return cached_result, execution_info

            # 使用策略工厂创建策略实例 - 转移职责到StrategyFactory
            # 使用RLock保护策略创建与执行，防止热更新时的并发读写
            with self._strategy_update_lock:
                factory = get_strategy_factory()
                strategy_instance = factory.create_strategy(strategy_name)
                if strategy_instance is None:
                    raise ValueError(f"策略不存在或创建失败: {strategy_name}")

                # 验证数据
                required_columns = strategy_instance.get_required_columns()
                missing_columns = [
                    col for col in required_columns if col not in data.columns]
                if missing_columns:
                    raise ValueError(f"缺少必需的数据列: {missing_columns}")

                # 执行策略
                with self.performance_monitor.measure_time(f"strategy_execution_{strategy_name}"):
                    signals = strategy_instance.generate_signals(data)

            # 验证信号
            if not isinstance(signals, list):
                raise ValueError("策略必须返回信号列表")

            # 缓存结果 - 传递策略名称用于分组管理
            if use_cache:
                # 根据策略重要性设置优先级（可根据实际情况调整）
                priority = 5  # 默认优先级
                if strategy_name in ['default_momentum', 'default_reversion']:
                    priority = 8  # 内置策略优先级更高
                
                self.cache.put(cache_key, signals, strategy_name=strategy_name, priority=priority)

            # 更新执行信息
            execution_info['success'] = True
            execution_info['signals_count'] = len(signals)
            execution_info['execution_time'] = time.time() - start_time

            # 保存到数据库
            if save_to_db:
                try:
                    self._ensure_database_service()
                    if self.database_service:
                        # 获取策略ID
                        all_strategies = self.database_service.list_strategies()
                        strategy_id = None
                        for s in all_strategies:
                            if s['name'] == strategy_name:
                                strategy_id = s['id']
                                break

                        if strategy_id:
                            execution_data = {
                                'strategy_id': strategy_id,
                                'execution_time': datetime.now(),
                                'data_hash': data_hash,
                                'signals_count': len(signals),
                                'execution_duration': execution_info['execution_time'],
                                'success': True,
                                'performance_metrics': self._calculate_performance_metrics(signals)
                            }
                            self.database_service.save_execution_result(execution_data)
                except Exception as e:
                    self.logger.warning(f"保存执行结果到数据库失败: {e}")

            # 更新统计
            self._update_stats('success', execution_info['execution_time'])

            self.logger.info(
                f"策略执行成功: {strategy_name}, 信号数: {len(signals)}, 耗时: {execution_info['execution_time']:.3f}s")
            return signals, execution_info

        except Exception as e:
            execution_info['success'] = False
            execution_info['error_message'] = str(e)
            execution_info['execution_time'] = time.time() - start_time

            # 保存失败记录到数据库
            if save_to_db:
                try:
                    self._ensure_database_service()
                    if self.database_service:
                        # 获取策略ID
                        all_strategies = self.database_service.list_strategies()
                        strategy_id = None
                        for s in all_strategies:
                            if s['name'] == strategy_name:
                                strategy_id = s['id']
                                break

                        if strategy_id:
                            data_hash = self._generate_data_hash(data)
                            execution_data = {
                                'strategy_id': strategy_id,
                                'execution_time': datetime.now(),
                                'data_hash': data_hash,
                                'signals_count': 0,
                                'execution_duration': execution_info['execution_time'],
                                'success': False,
                                'error_message': str(e)
                            }
                            self.database_service.save_execution_result(execution_data)
                except Exception as db_e:
                    self.logger.warning(f"保存失败记录到数据库失败: {db_e}")

            # 更新统计
            self._update_stats('failure', execution_info['execution_time'])

            self.logger.error(f"策略执行失败: {strategy_name}, 错误: {e}")
            return [], execution_info

    def execute_strategies_batch(self, strategy_names: List[str], data: pd.DataFrame,
                                 use_cache: bool = True, save_to_db: bool = True) -> Dict[str, Tuple[List[StrategySignal], Dict[str, Any]]]:
        """
        批量执行策略

        Args:
            strategy_names: 策略名称列表
            data: 市场数据
            use_cache: 是否使用缓存
            save_to_db: 是否保存到数据库

        Returns:
            策略名称到(信号列表, 执行信息)的映射
        """
        self.logger.info(f"开始批量执行策略: {len(strategy_names)}个策略")

        results = {}
        futures = {}

        # 提交执行任务
        for strategy_name in strategy_names:
            future = self.executor.submit(
                self.execute_strategy,
                strategy_name,
                data,
                use_cache,
                save_to_db
            )
            futures[future] = strategy_name

        # 收集结果
        for future in as_completed(futures):
            strategy_name = futures[future]
            try:
                signals, execution_info = future.result()
                results[strategy_name] = (signals, execution_info)
            except Exception as e:
                self.logger.error(f"批量执行策略失败 {strategy_name}: {e}")
                results[strategy_name] = ([], {
                    'strategy_name': strategy_name,
                    'success': False,
                    'error_message': str(e),
                    'execution_time': 0.0
                })

        self.logger.info(f"批量执行策略完成: {len(results)}个结果")
        return results

    @measure_performance("StrategyEngine.execute_strategies_parallel")
    def execute_strategies_parallel(self, strategies_data: List[Tuple[str, pd.DataFrame]],
                                    use_cache: bool = True, save_to_db: bool = True) -> Dict[str, Tuple[List[StrategySignal], Dict[str, Any]]]:
        """
        并行执行不同数据的策略

        Args:
            strategies_data: (策略名称, 数据)元组列表
            use_cache: 是否使用缓存
            save_to_db: 是否保存到数据库

        Returns:
            策略名称到(信号列表, 执行信息)的映射
        """
        self.logger.info(f"开始并行执行策略: {len(strategies_data)}个任务")

        results = {}
        futures = {}

        # 提交执行任务
        for strategy_name, data in strategies_data:
            future = self.executor.submit(
                self.execute_strategy,
                strategy_name,
                data,
                use_cache,
                save_to_db
            )
            futures[future] = strategy_name

        # 收集结果
        for future in as_completed(futures):
            strategy_name = futures[future]
            try:
                signals, execution_info = future.result()
                results[strategy_name] = (signals, execution_info)
            except Exception as e:
                self.logger.error(f"并行执行策略失败 {strategy_name}: {e}")
                results[strategy_name] = ([], {
                    'strategy_name': strategy_name,
                    'success': False,
                    'error_message': str(e),
                    'execution_time': 0.0
                })

        self.logger.info(f"并行执行策略完成: {len(results)}个结果")
        return results

    def get_execution_history(self, strategy_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取策略执行历史

        Args:
            strategy_name: 策略名称
            limit: 返回记录数限制

        Returns:
            执行历史列表
        """
        try:
            self._ensure_database_service()
            if not self.database_service:
                return []

            # 先根据策略名称查找策略ID
            all_strategies = self.database_service.list_strategies()
            strategy_id = None
            for s in all_strategies:
                if s['name'] == strategy_name:
                    strategy_id = s['id']
                    break

            if not strategy_id:
                self.logger.warning(f"未找到策略: {strategy_name}")
                return []

            return self.database_service.get_execution_history(strategy_id, limit)
        except Exception as e:
            self.logger.error(f"获取执行历史失败 {strategy_name}: {e}")
            return []

    def clear_cache(self, strategy_name: Optional[str] = None):
        """
        清理缓存

        Args:
            strategy_name: 策略名称，None表示清理所有缓存
        """
        if strategy_name is None:
            self.cache.clear()
            self.logger.info("已清理所有策略缓存")
        else:
            # 使用改进后的方法清理特定策略的缓存
            self.cache.invalidate_by_strategy(strategy_name)
            self.logger.info(f"已清理策略缓存: {strategy_name}")

    def get_engine_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        with self._stats_lock:
            stats = self._execution_stats.copy()

        # 添加缓存统计
        stats['cache'] = self.cache.get_stats()

        # 计算平均执行时间
        if stats['total_executions'] > 0:
            stats['average_execution_time'] = stats['total_execution_time'] / \
                stats['total_executions']
        else:
            stats['average_execution_time'] = 0.0

        # 计算成功率
        if stats['total_executions'] > 0:
            stats['success_rate'] = stats['successful_executions'] / \
                stats['total_executions']
        else:
            stats['success_rate'] = 0.0

        # 添加线程池信息
        stats['thread_pool'] = {
            'max_workers': self.max_workers,
            'active_threads': self.executor._threads.__len__() if hasattr(self.executor, '_threads') else 0
        }

        return stats

    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """获取可用策略列表（委托给StrategyFactory）

        Returns:
            List[Dict]: 策略列表，每个dict包含name和id
        """
        try:
            factory = get_strategy_factory()
            strategy_names = factory.get_available_strategies()

            # 转换为 {name, id} 格式
            result = []
            for name in strategy_names:
                metadata = factory.get_strategy_metadata(name)
                if metadata:
                    result.append({
                        'name': name,
                        'id': metadata.get('id', name),
                        'category': metadata.get('category', 'custom'),
                        'description': metadata.get('description', '')
                    })
                else:
                    result.append({'name': name, 'id': name})

            self.logger.debug(f"获取可用策略列表: {len(result)} 个")
            return result
        except Exception as e:
            self.logger.error(f"获取可用策略列表失败: {e}")
            return []

    def get_strategy_instance(self, strategy_name: str) -> Optional[BaseStrategy]:
        """获取策略实例（委托给StrategyFactory）

        Args:
            strategy_name: 策略名称

        Returns:
            BaseStrategy: 策略实例
        """
        try:
            factory = get_strategy_factory()
            strategy = factory.create_strategy(strategy_name)
            if strategy is None:
                self.logger.warning(f"策略不存在或创建失败: {strategy_name}")
            return strategy
        except Exception as e:
            self.logger.error(f"获取策略实例失败 {strategy_name}: {e}")
            return None

    def update_strategy_params(self, strategy_name: str, params: Dict[str, Any]) -> bool:
        """
        热更新策略参数（使用RLock保护并发安全）

        Args:
            strategy_name: 策略名称
            params: 参数字典

        Returns:
            bool: 更新是否成功
        """
        with self._strategy_update_lock:
            try:
                factory = get_strategy_factory()
                strategy = factory.create_strategy(strategy_name)
                if strategy is None:
                    self.logger.warning(f"策略不存在，无法热更新参数: {strategy_name}")
                    return False

                if hasattr(strategy, 'update_params'):
                    strategy.update_params(params)
                elif hasattr(strategy, 'set_params'):
                    strategy.set_params(params)
                else:
                    for key, value in params.items():
                        if hasattr(strategy, key):
                            setattr(strategy, key, value)

                self.logger.info(f"策略参数热更新成功: {strategy_name}, params={params}")
                return True

            except Exception as e:
                self.logger.error(f"策略参数热更新失败 {strategy_name}: {e}")
                return False

    def shutdown(self, wait: bool = True):
        """
        关闭执行引擎

        Args:
            wait: 是否等待正在执行的任务完成
        """
        self.logger.info("正在关闭策略执行引擎...")

        # 关闭线程池
        self.executor.shutdown(wait=wait)

        # 清理缓存
        self.cache.clear()

        self.logger.info("策略执行引擎已关闭")

    def _generate_data_hash(self, data: pd.DataFrame) -> str:
        """生成数据哈希"""
        try:
            # 使用数据的形状、列名和部分数据生成哈希
            hash_content = f"{data.shape}_{list(data.columns)}_{data.head().to_string()}_{data.tail().to_string()}"
            return hashlib.md5(hash_content.encode()).hexdigest()
        except Exception as e:
            self.logger.warning(f"生成数据哈希失败: {e}")
            return str(hash(str(data.shape) + str(list(data.columns))))

    def _calculate_performance_metrics(self, signals: List[StrategySignal]) -> Dict[str, Any]:
        """计算性能指标，字段与PerformanceMetrics数据类对齐"""
        if not signals:
            return {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'total_return': 0.0, 'annual_return': 0.0,
                'sharpe_ratio': 0.0, 'max_drawdown': 0.0,
                'win_rate': 0.0, 'profit_factor': 0.0,
                'avg_win': 0.0, 'avg_loss': 0.0,
                'signal_count': 0, 'buy_signals': 0, 'sell_signals': 0,
            }

        try:
            buy_signals = [s for s in signals if s.signal_type.value == 'BUY']
            sell_signals = [s for s in signals if s.signal_type.value == 'SELL']
            hold_signals = [s for s in signals if s.signal_type.value not in ('BUY', 'SELL')]

            total_trades = len(buy_signals) + len(sell_signals)
            buy_prices = [s.price for s in buy_signals if s.price > 0]
            sell_prices = [s.price for s in sell_signals if s.price > 0]
            buy_confidences = [s.confidence for s in buy_signals]
            sell_confidences = [s.confidence for s in sell_signals]

            avg_buy_price = np.mean(buy_prices) if buy_prices else 0.0
            avg_sell_price = np.mean(sell_prices) if sell_prices else 0.0
            avg_buy_confidence = np.mean(buy_confidences) if buy_confidences else 0.0
            avg_sell_confidence = np.mean(sell_confidences) if sell_confidences else 0.0

            sorted_signals = sorted(signals, key=lambda s: s.timestamp)
            buy_queue = []
            returns = []
            for s in sorted_signals:
                if s.signal_type.value == 'BUY' and s.price > 0:
                    buy_queue.append(s.price)
                elif s.signal_type.value == 'SELL' and s.price > 0:
                    if buy_queue:
                        buy_price = buy_queue.pop(0)
                        r = (s.price - buy_price) / buy_price
                        returns.append(r)
            paired_trades = len(returns)

            winning_trades = sum(1 for r in returns if r > 0)
            losing_trades = sum(1 for r in returns if r <= 0)

            total_return = sum(returns) if returns else 0.0
            avg_return = total_return / len(returns) if returns else 0.0

            if returns:
                avg_win = sum(r for r in returns if r > 0) / winning_trades if winning_trades > 0 else 0.0
                avg_loss = sum(r for r in returns if r <= 0) / losing_trades if losing_trades > 0 else 0.0
            else:
                avg_win = 0.0
                avg_loss = 0.0

            gross_profit = sum(r for r in returns if r > 0) if returns else 0.0
            gross_loss = abs(sum(r for r in returns if r <= 0)) if returns else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)

            win_rate = winning_trades / len(returns) if returns else 0.0

            peak = 0.0
            cumulative = 0.0
            max_drawdown = 0.0
            for r in returns:
                cumulative += r
                peak = max(peak, cumulative)
                drawdown = peak - cumulative
                max_drawdown = max(max_drawdown, drawdown)

            return_std = float(np.std(returns)) if len(returns) > 1 else 0.0
            sharpe_ratio = (avg_return / return_std) if return_std > 0 else 0.0

            metrics = {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'total_return': round(total_return, 6),
                'annual_return': round(total_return * (252 / max(len(returns), 1)), 6),
                'sharpe_ratio': round(sharpe_ratio, 4),
                'max_drawdown': round(max_drawdown, 6),
                'win_rate': round(win_rate, 4),
                'profit_factor': round(profit_factor, 4) if profit_factor != float('inf') else -1.0,
                'avg_win': round(avg_win, 6),
                'avg_loss': round(avg_loss, 6),
                'signal_count': len(signals),
                'buy_signals': len(buy_signals),
                'sell_signals': len(sell_signals),
                'hold_signals': len(hold_signals),
                'avg_buy_price': round(avg_buy_price, 4),
                'avg_sell_price': round(avg_sell_price, 4),
                'avg_buy_confidence': round(avg_buy_confidence, 4),
                'avg_sell_confidence': round(avg_sell_confidence, 4),
            }

            return metrics

        except Exception as e:
            self.logger.warning(f"计算性能指标失败: {e}")
            return {
                'total_trades': len(signals), 'winning_trades': 0, 'losing_trades': 0,
                'total_return': 0.0, 'annual_return': 0.0,
                'sharpe_ratio': 0.0, 'max_drawdown': 0.0,
                'win_rate': 0.0, 'profit_factor': 0.0,
                'avg_win': 0.0, 'avg_loss': 0.0,
                'signal_count': len(signals), 'error': str(e),
            }

    def _update_stats(self, result_type: str, execution_time: float = 0.0):
        """更新统计信息"""
        with self._stats_lock:
            self._execution_stats['total_executions'] += 1
            self._execution_stats['total_execution_time'] += execution_time

            if result_type == 'success':
                self._execution_stats['successful_executions'] += 1
            elif result_type == 'failure':
                self._execution_stats['failed_executions'] += 1
            elif result_type == 'cache_hit':
                self._execution_stats['cache_hits'] += 1
            elif result_type == 'cache_miss':
                self._execution_stats['cache_misses'] += 1

# 全局单例实例
_strategy_engine = None
_engine_lock = threading.Lock()

def get_strategy_engine() -> StrategyEngine:
    """获取策略执行引擎单例"""
    global _strategy_engine

    if _strategy_engine is None:
        with _engine_lock:
            if _strategy_engine is None:
                _strategy_engine = StrategyEngine()

    return _strategy_engine

def initialize_strategy_engine(max_workers: int = None, cache_size: int = 1000,
                               cache_ttl: int = 3600) -> StrategyEngine:
    """初始化策略执行引擎"""
    global _strategy_engine

    with _engine_lock:
        _strategy_engine = StrategyEngine(max_workers, cache_size, cache_ttl)

    return _strategy_engine
