from loguru import logger
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

# 使用系统统一组件
from core.adapters import get_config, get_performance_monitor
from .base_strategy import BaseStrategy, StrategySignal
from .strategy_registry import get_strategy_registry
from .strategy_database import get_strategy_database_manager
from .strategy_factory import get_strategy_factory
from core.performance import measure_performance

class StrategyCache:
    """策略缓存管理器 - 支持细粒度缓存控制"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 默认缓存过期时间（秒）
        """
        self.logger = logger.bind(module=__name__)
        self.max_size = max_size
        self.default_ttl = ttl_seconds

        # 缓存存储 - 支持按策略分组
        self._cache: Dict[str, Dict[str, Any]] = {}  # key -> {value, timestamp, ttl, strategy_name, priority}
        self._access_times: Dict[str, float] = {}  # key -> last access time
        self._strategy_groups: Dict[str, List[str]] = {}  # strategy_name -> [keys]
        self._lock = threading.RLock()

        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._strategy_stats: Dict[str, Dict[str, int]] = {}  # strategy_name -> {hits, misses, size}

        self.logger.debug(f"策略缓存初始化: max_size={max_size}, default_ttl={ttl_seconds}s")

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                self._update_strategy_stat(key, 'misses')
                return None

            # 检查是否过期
            cache_entry = self._cache[key]
            if time.time() - cache_entry['timestamp'] > cache_entry['ttl']:
                self._remove_key(key)
                self._misses += 1
                self._update_strategy_stat(key, 'misses')
                return None

            # 更新访问时间
            self._access_times[key] = time.time()
            self._hits += 1
            self._update_strategy_stat(key, 'hits')

            return cache_entry['value']

    def put(self, key: str, value: Any, strategy_name: str = None, ttl: int = None, priority: int = 0):
        """存储缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            strategy_name: 策略名称（用于分组管理）
            ttl: 缓存过期时间（秒），None使用默认值
            priority: 缓存优先级（0-10，值越大优先级越高）
        """
        with self._lock:
            current_time = time.time()
            cache_ttl = ttl or self.default_ttl

            # 检查缓存大小限制
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            # 存储缓存
            self._cache[key] = {
                'value': value,
                'timestamp': current_time,
                'ttl': cache_ttl,
                'strategy_name': strategy_name,
                'priority': priority
            }
            self._access_times[key] = current_time
            
            # 更新策略分组
            if strategy_name:
                if strategy_name not in self._strategy_groups:
                    self._strategy_groups[strategy_name] = []
                if key not in self._strategy_groups[strategy_name]:
                    self._strategy_groups[strategy_name].append(key)
            
            # 更新策略统计
            self._update_strategy_stat(key, 'size')

    def invalidate(self, key: str):
        """使单个缓存键失效"""
        with self._lock:
            self._remove_key(key)

    def invalidate_by_strategy(self, strategy_name: str):
        """使指定策略的所有缓存失效"""
        with self._lock:
            if strategy_name in self._strategy_groups:
                keys_to_remove = self._strategy_groups[strategy_name].copy()
                for key in keys_to_remove:
                    self._remove_key(key)
                del self._strategy_groups[strategy_name]
                self.logger.debug(f"已清理策略缓存: {strategy_name} ({len(keys_to_remove)}项)")

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self._strategy_groups.clear()
            self._reset_stats()
            self.logger.debug("策略缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """获取详细缓存统计信息"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            # 计算策略级别的统计
            strategy_stats = {}
            for strategy_name, stats in self._strategy_stats.items():
                strategy_total = stats.get('hits', 0) + stats.get('misses', 0)
                strategy_hit_rate = stats['hits'] / strategy_total if strategy_total > 0 else 0
                strategy_stats[strategy_name] = {
                    'hits': stats.get('hits', 0),
                    'misses': stats.get('misses', 0),
                    'total_requests': strategy_total,
                    'hit_rate': strategy_hit_rate,
                    'size': stats.get('size', 0)
                }

            return {
                'global': {
                    'size': len(self._cache),
                    'max_size': self.max_size,
                    'hits': self._hits,
                    'misses': self._misses,
                    'total_requests': total_requests,
                    'hit_rate': hit_rate,
                    'evictions': self._evictions,
                    'default_ttl': self.default_ttl
                },
                'by_strategy': strategy_stats,
                'strategy_groups': {k: len(v) for k, v in self._strategy_groups.items()}
            }

    def _remove_key(self, key: str):
        """移除缓存键并更新相关数据结构"""
        if key in self._cache:
            # 从策略分组中移除
            cache_entry = self._cache[key]
            strategy_name = cache_entry.get('strategy_name')
            if strategy_name and strategy_name in self._strategy_groups:
                if key in self._strategy_groups[strategy_name]:
                    self._strategy_groups[strategy_name].remove(key)
                # 如果分组为空，删除分组
                if not self._strategy_groups[strategy_name]:
                    del self._strategy_groups[strategy_name]
            
            # 移除缓存和访问时间
            del self._cache[key]
            self._access_times.pop(key, None)
            
            # 更新策略统计
            self._update_strategy_stat(key, 'remove')

    def _evict_lru(self):
        """移除最近最少使用的缓存项，考虑优先级"""
        if not self._access_times:
            return

        # 按优先级和访问时间排序，优先保留高优先级和最近访问的项
        sorted_keys = sorted(
            self._access_times.keys(),
            key=lambda k: (self._cache[k]['priority'], self._access_times[k]),
            reverse=True
        )
        
        # 移除优先级最低且最久未访问的项
        if sorted_keys:
            lru_key = sorted_keys[-1]
            self._remove_key(lru_key)
            self._evictions += 1
            self.logger.debug(f"LRU淘汰缓存项: {lru_key}, 优先级: {self._cache.get(lru_key, {}).get('priority', 0)}")

    def _update_strategy_stat(self, key: str, stat_type: str):
        """更新策略统计信息"""
        if key in self._cache:
            strategy_name = self._cache[key].get('strategy_name')
            if strategy_name:
                if strategy_name not in self._strategy_stats:
                    self._strategy_stats[strategy_name] = {'hits': 0, 'misses': 0, 'size': 0}
                
                if stat_type == 'hits':
                    self._strategy_stats[strategy_name]['hits'] += 1
                elif stat_type == 'misses':
                    self._strategy_stats[strategy_name]['misses'] += 1
                elif stat_type == 'size':
                    self._strategy_stats[strategy_name]['size'] += 1
                elif stat_type == 'remove':
                    self._strategy_stats[strategy_name]['size'] = max(0, self._strategy_stats[strategy_name]['size'] - 1)

    def _reset_stats(self):
        """重置统计信息"""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._strategy_stats.clear()

    def get_strategy_cache_size(self, strategy_name: str) -> int:
        """获取指定策略的缓存大小"""
        with self._lock:
            return len(self._strategy_groups.get(strategy_name, []))

    def warmup_cache(self, keys_values: Dict[str, Any], strategy_name: str = None, ttl: int = None):
        """缓存预热 - 批量添加缓存项
        
        Args:
            keys_values: 键值对字典
            strategy_name: 策略名称
            ttl: 缓存过期时间
        """
        with self._lock:
            for key, value in keys_values.items():
                self.put(key, value, strategy_name, ttl)
            self.logger.debug(f"缓存预热完成: 添加 {len(keys_values)} 项")

    def preload_strategy_cache(self, strategy_name: str, data: Dict[str, Any], ttl: int = None):
        """预加载指定策略的缓存
        
        Args:
            strategy_name: 策略名称
            data: 要预加载的数据
            ttl: 缓存过期时间
        """
        self.warmup_cache(data, strategy_name, ttl)
        self.logger.debug(f"策略缓存预加载完成: {strategy_name}, 添加 {len(data)} 项")

class StrategyEngine:
    """策略执行引擎"""

    def __init__(self, max_workers: int = None, cache_size: int = 1000, cache_ttl: int = 3600):
        """
        初始化策略执行引擎

        Args:
            max_workers: 最大工作线程数
            cache_size: 缓存大小
            cache_ttl: 缓存过期时间（秒）
        """
        self.logger = logger.bind(module=__name__)
        self.config = get_config()
        self.performance_monitor = get_performance_monitor()
        self.registry = get_strategy_registry()
        self.db_manager = get_strategy_database_manager()

        # 从配置获取参数，避免硬编码
        engine_config = self.config.get('strategy_engine', {})
        self.max_workers = max_workers or engine_config.get('max_workers', 4)

        # 初始化组件
        self.cache = StrategyCache(cache_size, cache_ttl)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # 执行统计
        self._execution_stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_execution_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self._stats_lock = threading.Lock()

        self.logger.info(f"策略执行引擎初始化完成: max_workers={self.max_workers}")

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
                    self.db_manager.save_execution_result(
                        strategy_name=strategy_name,
                        data_hash=data_hash,
                        signals=signals,
                        execution_time=execution_info['execution_time'],
                        success=True,
                        performance_metrics=self._calculate_performance_metrics(
                            signals)
                    )
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
                    data_hash = self._generate_data_hash(data)
                    self.db_manager.save_execution_result(
                        strategy_name=strategy_name,
                        data_hash=data_hash,
                        signals=[],
                        execution_time=execution_info['execution_time'],
                        success=False,
                        error_message=str(e)
                    )
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
            return self.db_manager.get_execution_history(strategy_name, limit)
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
        """计算性能指标"""
        if not signals:
            return {}

        try:
            buy_signals = [s for s in signals if s.signal_type.value == 'BUY']
            sell_signals = [
                s for s in signals if s.signal_type.value == 'SELL']

            metrics = {
                'total_signals': len(signals),
                'buy_signals': len(buy_signals),
                'sell_signals': len(sell_signals),
                'average_confidence': sum(s.confidence for s in signals) / len(signals),
                'max_confidence': max(s.confidence for s in signals),
                'min_confidence': min(s.confidence for s in signals)
            }

            # 计算价格统计
            if signals:
                prices = [s.price for s in signals]
                metrics.update({
                    'average_price': sum(prices) / len(prices),
                    'max_price': max(prices),
                    'min_price': min(prices)
                })

            return metrics

        except Exception as e:
            self.logger.warning(f"计算性能指标失败: {e}")
            return {}

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
