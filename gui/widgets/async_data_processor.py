import os
import psutil
import threading
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
import time
# 已替换为新的导入

from core.indicator_service import calculate_indicator, get_indicator_metadata, get_all_indicators_metadata
from loguru import logger

class AsyncDataProcessor(QObject):
    """异步数据处理器，处理大数据量的计算和渲染"""

    # 定义信号
    calculation_progress = pyqtSignal(int, str)  # 进度信号
    calculation_complete = pyqtSignal(dict)  # 计算完成信号
    calculation_error = pyqtSignal(str)  # 错误信号
    performance_metrics = pyqtSignal(dict)  # 性能指标信号

    def __init__(self, max_workers: int = None):
        super().__init__()

        # 动态设置线程池大小 - 优化算法
        if max_workers is None:
            cpu_count = os.cpu_count() or 4
            # 根据CPU核心数和内存大小智能设置
            memory_gb = psutil.virtual_memory().total / (1024**3)

            if memory_gb >= 16:
                # 16GB以上内存，可以使用更多线程
                max_workers = min(cpu_count * 2, 16)
            elif memory_gb >= 8:
                # 8-16GB内存，适中的线程数
                max_workers = min(cpu_count + 2, 8)
            else:
                # 8GB以下内存，保守的线程数
                max_workers = min(cpu_count, 4)

        self.max_workers = max_workers
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

        # 动态调整分块大小 - 优化算法
        self._chunk_size = self._calculate_optimal_chunk_size()
        self._cache = {}  # 计算结果缓存
        self._cache_lock = threading.Lock()

        # 性能监控 - 增强统计
        self._processing_stats = {
            'total_processed': 0,
            'avg_processing_time': 0,
            'cache_hit_rate': 0,
            'last_update': None,
            'memory_usage': 0,
            'cpu_usage': 0
        }

    def _calculate_optimal_chunk_size(self) -> int:
        """根据系统资源动态计算最优分块大小"""
        memory_gb = psutil.virtual_memory().total / (1024**3)

        if memory_gb >= 16:
            return 2000  # 大内存系统，使用更大的块
        elif memory_gb >= 8:
            return 1500  # 中等内存
        else:
            return 1000  # 小内存系统，使用较小的块

    def process_data(self, data: pd.DataFrame, indicators: List[str], params: Dict[str, Any]):
        """异步处理数据和计算指标

        Args:
            data: K线数据
            indicators: 需要计算的指标列表
            params: 指标参数
        """
        start_time = time.time()

        try:
            # 检查数据大小，决定是否需要分块处理
            if len(data) <= self._chunk_size:
                # 小数据集，直接处理
                self._process_small_dataset(data, indicators, params)
            else:
                # 大数据集，分块处理
                self._process_large_dataset(data, indicators, params)

        except Exception as e:
            self.calculation_error.emit(str(e))
        finally:
            # 更新性能统计
            processing_time = time.time() - start_time
            self._update_performance_stats(processing_time)

    def _process_small_dataset(self, data: pd.DataFrame, indicators: List[str], params: Dict[str, Any]):
        """处理小数据集（无需分块）"""
        try:
            self.calculation_progress.emit(10, "开始计算指标...")

            results = {}
            total_indicators = len(indicators)

            # 并行计算所有指标 - 优化线程池使用
            with ThreadPoolExecutor(max_workers=min(self.max_workers, total_indicators)) as executor:
                futures = []
                for i, indicator in enumerate(indicators):
                    future = executor.submit(
                        self._calculate_indicator,
                        data,
                        indicator,
                        params.get(indicator, {})
                    )
                    futures.append((indicator, future))

                # 收集结果
                for i, (indicator, future) in enumerate(futures):
                    try:
                        progress = int(10 + (80 * (i + 1) / total_indicators))
                        self.calculation_progress.emit(
                            progress, f"计算指标: {indicator}")

                        result = future.result()
                        if isinstance(result, tuple):
                            for j, name in enumerate([f"{indicator}_{j}" for j in range(len(result))]):
                                results[name] = result[j]
                        else:
                            results[indicator] = result
                    except Exception as e:
                        self.calculation_error.emit(
                            f"计算指标 {indicator} 失败: {str(e)}")

            self.calculation_progress.emit(100, "计算完成")
            self.calculation_complete.emit(results)

        except Exception as e:
            self.calculation_error.emit(f"小数据集处理失败: {str(e)}")

    def _process_large_dataset(self, data: pd.DataFrame, indicators: List[str], params: Dict[str, Any]):
        """处理大数据集（需要分块）"""
        try:
            # 将数据分块
            chunks = self._split_data(data)
            total_chunks = len(chunks)

            self.calculation_progress.emit(5, f"数据分为 {total_chunks} 块进行处理...")

            # 创建异步任务
            futures = []
            for i, chunk in enumerate(chunks):
                future = self.thread_pool.submit(
                    self._process_chunk,
                    chunk,
                    indicators,
                    params,
                    i,
                    total_chunks
                )
                futures.append(future)

            # 收集结果
            results = {}
            for future in as_completed(futures):
                try:
                    chunk_result = future.result()
                    results.update(chunk_result)
                except Exception as e:
                    self.calculation_error.emit(f"数据分块处理异常: {str(e)}")

            # 合并结果
            self.calculation_progress.emit(95, "合并计算结果...")
            final_results = self._merge_results(results, data.index)
            self.calculation_complete.emit(final_results)

        except Exception as e:
            self.calculation_error.emit(str(e))

    def _split_data(self, data: pd.DataFrame) -> List[pd.DataFrame]:
        """将数据分块处理

        Args:
            data: 原始数据

        Returns:
            数据块列表
        """
        if len(data) <= self._chunk_size:
            return [data]

        chunks = []
        for i in range(0, len(data), self._chunk_size):
            chunk = data.iloc[i:i + self._chunk_size].copy()
            chunks.append(chunk)
        return chunks

    def _process_chunk(self, chunk: pd.DataFrame, indicators: List[str],
                       params: Dict[str, Any], chunk_idx: int, total_chunks: int) -> Dict[str, pd.Series]:
        """处理数据块

        Args:
            chunk: 数据块
            indicators: 指标列表
            params: 参数字典
            chunk_idx: 块索引
            total_chunks: 总块数

        Returns:
            计算结果字典
        """
        try:
            results = {}

            for indicator in indicators:
                try:
                    # 计算指标
                    result = self._calculate_indicator(
                        chunk,
                        indicator,
                        params.get(indicator, {})
                    )

                    # 存储结果
                    if isinstance(result, tuple):
                        for j, value in enumerate(result):
                            key = f"{indicator}_{j}_chunk_{chunk_idx}"
                            results[key] = value
                    else:
                        key = f"{indicator}_chunk_{chunk_idx}"
                        results[key] = result

                except Exception as e:
                    # 记录错误但继续处理其他指标
                    logger.info(f"计算指标 {indicator} 在块 {chunk_idx} 中失败: {str(e)}")
                    continue

            return results

        except Exception as e:
            logger.info(f"处理数据块 {chunk_idx} 失败: {str(e)}")
            return {}

    def _calculate_indicator(self, data: pd.DataFrame, indicator: str, params: Dict[str, Any]) -> Any:
        """计算单个指标

        Args:
            data: K线数据
            indicator: 指标名称
            params: 指标参数

        Returns:
            计算结果
        """
        try:
            # 生成缓存键
            cache_key = f"{indicator}_{hash(str(params))}_{len(data)}"

            # 检查缓存
            with self._cache_lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]

            # 使用新的指标服务计算（模块级函数为 **params 签名，需关键字传参）
            result = calculate_indicator(indicator, data, **params)

            # 缓存结果
            with self._cache_lock:
                self._cache[cache_key] = result

            return result

        except Exception as e:
            # 如果新指标服务失败，尝试使用传统方法
            try:
                # 这里可以添加传统指标计算的兜底逻辑
                return self._calculate_traditional_indicator(data, indicator, params)
            except Exception:
                raise Exception(f"指标 {indicator} 计算失败: {str(e)}")

    def _calculate_traditional_indicator(self, data: pd.DataFrame, indicator: str, params: Dict[str, Any]) -> Any:
        """传统指标计算方法（兜底）"""
        # 这里可以实现一些基本的指标计算作为兜底
        if indicator.upper() == 'MA':
            period = params.get('timeperiod', 5)
            return data['close'].rolling(window=period).mean()
        elif indicator.upper() == 'MACD':
            # 简单的MACD计算
            exp1 = data['close'].ewm(span=12).mean()
            exp2 = data['close'].ewm(span=26).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9).mean()
            histogram = macd - signal
            return macd, signal, histogram
        else:
            raise Exception(f"不支持的指标: {indicator}")

    def _merge_results(self, results: Dict[str, Dict[str, pd.Series]],
                       original_index: pd.Index) -> Dict[str, pd.Series]:
        """合并分块计算结果

        Args:
            results: 分块结果字典
            original_index: 原始索引

        Returns:
            合并后的结果
        """
        try:
            merged_results = {}

            # 按指标名称分组
            indicator_groups = {}
            for key, value in results.items():
                # 解析键名，提取指标名称
                if '_chunk_' in key:
                    indicator_name = key.split('_chunk_')[0]
                    if indicator_name not in indicator_groups:
                        indicator_groups[indicator_name] = []
                    indicator_groups[indicator_name].append(value)

            # 合并每个指标的结果
            for indicator_name, chunks in indicator_groups.items():
                try:
                    # 将所有块合并
                    merged_series = pd.concat(chunks, ignore_index=True)
                    # 重新设置索引
                    merged_series.index = original_index[:len(merged_series)]
                    merged_results[indicator_name] = merged_series
                except Exception as e:
                    logger.info(f"合并指标 {indicator_name} 失败: {str(e)}")
                    continue

            return merged_results

        except Exception as e:
            logger.info(f"合并结果失败: {str(e)}")
            return {}

    def clear_cache(self):
        """清除缓存"""
        with self._cache_lock:
            self._cache.clear()

    def _update_performance_stats(self, processing_time: float):
        """更新性能统计信息"""
        try:
            self._processing_stats['total_processed'] += 1

            # 更新平均处理时间
            if self._processing_stats['avg_processing_time'] == 0:
                self._processing_stats['avg_processing_time'] = processing_time
            else:
                total_time = (self._processing_stats['avg_processing_time'] *
                              (self._processing_stats['total_processed'] - 1) + processing_time)
                self._processing_stats['avg_processing_time'] = total_time / \
                    self._processing_stats['total_processed']

            # 更新缓存命中率
            if self._processing_stats['total_processed'] > 0:
                cache_hits = sum(1 for _ in self._cache.values())
                self._processing_stats['cache_hit_rate'] = cache_hits / \
                    self._processing_stats['total_processed']

            # 更新系统资源使用情况
            self._processing_stats['memory_usage'] = psutil.virtual_memory(
            ).percent
            self._processing_stats['cpu_usage'] = psutil.cpu_percent()
            self._processing_stats['last_update'] = time.time()

            # 发送性能指标信号
            self.performance_metrics.emit(self._processing_stats.copy())

        except Exception as e:
            logger.info(f"更新性能统计失败: {str(e)}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息

        Returns:
            性能统计字典
        """
        return self._processing_stats.copy()

    def cancel_all_tasks(self):
        """取消所有任务"""
        try:
            # 关闭线程池
            self.thread_pool.shutdown(wait=True, cancel_futures=True)

            # 重新创建线程池
            self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)

        except Exception as e:
            logger.info(f"取消任务失败: {str(e)}")

    def __del__(self):
        """析构函数，确保线程池正确关闭"""
        try:
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=True)
        except Exception:
            pass
