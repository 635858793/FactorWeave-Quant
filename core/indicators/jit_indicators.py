"""
JIT加速的技术指标计算
统一的技术指标JIT优化模块，提供高性能的技术指标计算
"""

import numpy as np
from numba import njit, prange
from typing import Tuple, Dict, Any
import hashlib
import time

# 指标缓存
_indicator_cache = {}
_cache_lock = None
try:
    import threading
    _cache_lock = threading.Lock()
except ImportError:
    _cache_lock = None

def _get_cache_key(data: 'np.ndarray', indicator_type: str, params: Dict[str, Any]) -> str:
    """生成缓存键"""
    data_hash = hashlib.md5(data.tobytes()).hexdigest()
    params_str = str(sorted(params.items()))
    return f"{indicator_type}_{data_hash}_{params_str}"

def _get_from_cache(cache_key: str) -> Any:
    """从缓存获取结果"""
    if _cache_lock is None:
        return _indicator_cache.get(cache_key)
    
    with _cache_lock:
        return _indicator_cache.get(cache_key)

def _set_cache(cache_key: str, value: Any):
    """设置缓存"""
    if _cache_lock is None:
        _indicator_cache[cache_key] = value
        return
    
    with _cache_lock:
        _indicator_cache[cache_key] = value

def clear_indicator_cache():
    """清理指标缓存"""
    if _cache_lock is None:
        _indicator_cache.clear()
        return
    
    with _cache_lock:
        _indicator_cache.clear()

def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    if _cache_lock is None:
        return {
            'cache_size': len(_indicator_cache),
            'cache_enabled': False
        }
    
    with _cache_lock:
        return {
            'cache_size': len(_indicator_cache),
            'cache_enabled': True
        }

@njit(cache=True, fastmath=True)
def calculate_sma_jit(prices: 'np.ndarray', period: int) -> 'np.ndarray':
    """
    计算简单移动平均（JIT优化版）
    Args:
        prices: 价格数组
        period: 计算周期

    Returns:
        移动平均数组
    """
    n = len(prices)
    sma = np.zeros(n, dtype=np.float64)
    
    for i in range(period - 1, n):
        sma[i] = np.mean(prices[i - period + 1:i + 1])
    
    return sma

@njit(cache=True, fastmath=True)
def calculate_ema_jit(prices: 'np.ndarray', period: int) -> 'np.ndarray':
    """
    计算指数移动平均（JIT优化版）
    Args:
        prices: 价格数组
        period: 计算周期

    Returns:
        指数移动平均数组
    """
    n = len(prices)
    ema = np.zeros(n, dtype=np.float64)
    multiplier = 2.0 / (period + 1.0)
    
    ema[0] = prices[0]
    for i in range(1, n):
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]
    
    return ema

@njit(cache=True, fastmath=True)
def calculate_rsi_jit(prices: 'np.ndarray', period: int = 14) -> 'np.ndarray':
    """
    计算RSI指标（JIT优化版）
    Args:
        prices: 价格数组
        period: 计算周期

    Returns:
        RSI数组
    """
    n = len(prices)
    rsi = np.zeros(n, dtype=np.float64)
    
    if n < period + 1:
        return rsi
    
    # 计算价格变化
    deltas = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        deltas[i] = prices[i] - prices[i - 1]
    
    # 计算涨跌
    gains = np.zeros(n, dtype=np.float64)
    losses = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        if deltas[i] > 0:
            gains[i] = deltas[i]
            losses[i] = 0.0
        else:
            gains[i] = 0.0
            losses[i] = -deltas[i]
    
    # 计算平均涨跌
    avg_gains = np.zeros(n, dtype=np.float64)
    avg_losses = np.zeros(n, dtype=np.float64)
    
    for i in range(period, n):
        avg_gains[i] = np.mean(gains[i - period + 1:i + 1])
        avg_losses[i] = np.mean(losses[i - period + 1:i + 1])
    
    # 计算RSI
    for i in range(period, n):
        if avg_losses[i] == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gains[i] / avg_losses[i]
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi

@njit(cache=True, fastmath=True)
def calculate_macd_jit(prices: 'np.ndarray', fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple['np.ndarray', 'np.ndarray', 'np.ndarray']:
    """
    计算MACD指标（JIT优化版）
    Args:
        prices: 价格数组
        fast_period: 快速EMA周期
        slow_period: 慢速EMA周期
        signal_period: 信号线周期

    Returns:
        (MACD, Signal, Histogram)
    """
    # 计算快速EMA
    fast_ema = calculate_ema_jit(prices, fast_period)
    
    # 计算慢速EMA
    slow_ema = calculate_ema_jit(prices, slow_period)
    
    # 计算MACD线
    macd = fast_ema - slow_ema
    
    # 计算信号线
    signal = calculate_ema_jit(macd, signal_period)
    
    # 计算柱状图
    histogram = macd - signal
    
    return macd, signal, histogram

@njit(cache=True, fastmath=True)
def calculate_bollinger_bands_jit(prices: 'np.ndarray', period: int = 20, num_std: float = 2.0) -> Tuple['np.ndarray', 'np.ndarray', 'np.ndarray']:
    """
    计算布林带（JIT优化版）
    Args:
        prices: 价格数组
        period: 计算周期
        num_std: 标准差倍数

    Returns:
        (Upper, Middle, Lower)
    """
    n = len(prices)
    upper = np.zeros(n, dtype=np.float64)
    middle = np.zeros(n, dtype=np.float64)
    lower = np.zeros(n, dtype=np.float64)
    
    for i in range(period - 1, n):
        window = prices[i - period + 1:i + 1]
        middle[i] = np.mean(window)
        std = np.std(window)
        upper[i] = middle[i] + num_std * std
        lower[i] = middle[i] - num_std * std
    
    return upper, middle, lower

@njit(cache=True, fastmath=True)
def calculate_atr_jit(high: 'np.ndarray', low: 'np.ndarray', close: 'np.ndarray', period: int = 14) -> 'np.ndarray':
    """
    计算平均真实波幅（JIT优化版）
    Args:
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        period: 计算周期

    Returns:
        ATR数组
    """
    n = len(close)
    atr = np.zeros(n, dtype=np.float64)
    
    for i in range(1, n):
        tr1 = high[i] - low[i]
        tr2 = abs(high[i] - close[i - 1])
        tr3 = abs(low[i] - close[i - 1])
        tr = max(tr1, tr2, tr3)
        
        if i < period:
            atr[i] = tr
        else:
            atr[i] = (atr[i - 1] * (period - 1) + tr) / period
    
    return atr

@njit(cache=True, fastmath=True, parallel=True)
def calculate_stochastic_jit(high: 'np.ndarray', low: 'np.ndarray', close: 'np.ndarray', k_period: int = 14, d_period: int = 3, smooth_period: int = 3) -> Tuple['np.ndarray', 'np.ndarray']:
    """
    计算随机指标（JIT优化版）
    Args:
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        k_period: K值周期
        d_period: D值周期
        smooth_period: 平滑周期

    Returns:
        (K, D)
    """
    n = len(close)
    k = np.zeros(n, dtype=np.float64)
    d = np.zeros(n, dtype=np.float64)
    
    for i in range(k_period - 1, n):
        window_high = np.max(high[i - k_period + 1:i + 1])
        window_low = np.min(low[i - k_period + 1:i + 1])
        
        if window_high == window_low:
            k[i] = 100.0
        else:
            k[i] = 100.0 * (close[i] - window_low) / (window_high - window_low)
    
    for i in range(d_period - 1, n):
        d[i] = np.mean(k[i - d_period + 1:i + 1])
    
    return k, d

@njit(cache=True, fastmath=True)
def calculate_williams_r_jit(high: 'np.ndarray', low: 'np.ndarray', close: 'np.ndarray', period: int = 14) -> 'np.ndarray':
    """
    计算威廉指标（JIT优化版）
    Args:
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        period: 计算周期

    Returns:
        Williams %R数组
    """
    n = len(close)
    williams_r = np.zeros(n, dtype=np.float64)
    
    for i in range(period - 1, n):
        window_high = np.max(high[i - period + 1:i + 1])
        window_low = np.min(low[i - period + 1:i + 1])
        
        if window_high == window_low:
            williams_r[i] = -100.0
        else:
            williams_r[i] = -100.0 * (window_high - close[i]) / (window_high - window_low)
    
    return williams_r

@njit(cache=True, fastmath=True, parallel=True)
def batch_calculate_indicators_jit(prices: 'np.ndarray', high: 'np.ndarray', low: 'np.ndarray', close: 'np.ndarray', indicators: list) -> Dict[str, 'np.ndarray']:
    """
    批量计算技术指标（JIT优化版）
    Args:
        prices: 价格数组
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        indicators: 要计算的指标列表

    Returns:
        包含所有计算结果的字典
    """
    results = {}
    
    if 'sma' in indicators:
        results['sma'] = calculate_sma_jit(prices, 20)
    
    if 'ema' in indicators:
        results['ema'] = calculate_ema_jit(prices, 20)
    
    if 'rsi' in indicators:
        results['rsi'] = calculate_rsi_jit(prices, 14)
    
    if 'macd' in indicators:
        macd, signal, hist = calculate_macd_jit(prices)
        results['macd'] = macd
        results['macd_signal'] = signal
        results['macd_hist'] = hist
    
    if 'bollinger' in indicators:
        upper, middle, lower = calculate_bollinger_bands_jit(prices)
        results['bb_upper'] = upper
        results['bb_middle'] = middle
        results['bb_lower'] = lower
    
    if 'atr' in indicators:
        results['atr'] = calculate_atr_jit(high, low, close)
    
    if 'stochastic' in indicators:
        k, d = calculate_stochastic_jit(high, low, close)
        results['stoch_k'] = k
        results['stoch_d'] = d
    
    if 'williams_r' in indicators:
        results['williams_r'] = calculate_williams_r_jit(high, low, close)
    
    return results

def calculate_sma_with_cache(prices: 'np.ndarray', period: int = 20, use_cache: bool = True) -> 'np.ndarray':
    """
    计算简单移动平均（带缓存）

    Args:
        prices: 价格数组
        period: 计算周期
        use_cache: 是否使用缓存

    Returns:
        移动平均数组
    """
    if use_cache:
        cache_key = _get_cache_key(prices, 'sma', {'period': period})
        cached_result = _get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
    
    result = calculate_sma_jit(prices, period)
    
    if use_cache:
        _set_cache(cache_key, result)
    
    return result

def calculate_rsi_with_cache(prices: 'np.ndarray', period: int = 14, use_cache: bool = True) -> 'np.ndarray':
    """
    计算RSI指标（带缓存版）
    Args:
        prices: 价格数组
        period: 计算周期
        use_cache: 是否使用缓存

    Returns:
        RSI数组
    """
    if use_cache:
        cache_key = _get_cache_key(prices, 'rsi', {'period': period})
        cached_result = _get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
    
    result = calculate_rsi_jit(prices, period)
    
    if use_cache:
        _set_cache(cache_key, result)
    
    return result

def calculate_macd_with_cache(prices: 'np.ndarray', fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, use_cache: bool = True) -> Tuple['np.ndarray', 'np.ndarray', 'np.ndarray']:
    """
    计算MACD指标（带缓存版）
    Args:
        prices: 价格数组
        fast_period: 快速EMA周期
        slow_period: 慢速EMA周期
        signal_period: 信号线周期
        use_cache: 是否使用缓存

    Returns:
        (MACD, Signal, Histogram)
    """
    if use_cache:
        cache_key = _get_cache_key(prices, 'macd', {'fast': fast_period, 'slow': slow_period, 'signal': signal_period})
        cached_result = _get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
    
    result = calculate_macd_jit(prices, fast_period, slow_period, signal_period)
    
    if use_cache:
        _set_cache(cache_key, result)
    
    return result

def benchmark_indicators_performance(prices: 'np.ndarray', high: 'np.ndarray', low: 'np.ndarray', close: 'np.ndarray', iterations: int = 100) -> Dict[str, float]:
    """
    基准测试JIT加速的性能提升

    Args:
        prices: 价格数组
        high: 最高价数组
        low: 最低价数组
        close: 收盘价数组
        iterations: 测试迭代次数

    Returns:
        性能提升统计
    """
    import time
    
    # 测试RSI
    start = time.time()
    for _ in range(iterations):
        _ = calculate_rsi_jit(prices, 14)
    jit_time = time.time() - start
    
    # 测试MACD
    start = time.time()
    for _ in range(iterations):
        _ = calculate_macd_jit(prices)
    macd_jit_time = time.time() - start
    
    return {
        'rsi_jit_time': jit_time,
        'macd_jit_time': macd_jit_time,
        'iterations': iterations
    }
