"""
自动JIT装饰器模块
提供自动JIT优化功能，支持装饰器和自动发现机制
"""

import functools
import inspect
import time
import threading
from typing import Callable, Any, Dict, List, Optional, Tuple
from numba import njit
import numpy as np
import logging

logger = logging.getLogger(__name__)


class AutoJIT:
    """自动JIT优化装饰器类
    
    提供@auto_jit装饰器，自动为函数添加JIT优化功能
    支持运行时切换JIT优化，自动收集性能统计
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._jit_enabled = True
        self._jit_functions: Dict[str, Dict] = {}
        self._performance_stats: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        
        logger.info("AutoJIT装饰器系统已初始化")
    
    def enable_jit(self):
        """启用JIT优化"""
        with self._lock:
            self._jit_enabled = True
            logger.info("AutoJIT优化已启用")
    
    def disable_jit(self):
        """禁用JIT优化"""
        with self._lock:
            self._jit_enabled = False
            logger.info("AutoJIT优化已禁用")
    
    def is_jit_enabled(self) -> bool:
        """检查JIT优化是否启用"""
        with self._lock:
            return self._jit_enabled
    
    def register_function(self, name: str, original_func: Callable, jit_func: Callable, 
                          description: str = "", category: str = "general"):
        """注册JIT函数
        
        Args:
            name: 函数名称
            original_func: 原始函数
            jit_func: JIT优化后的函数
            description: 函数描述
            category: 函数分类
        """
        with self._lock:
            self._jit_functions[name] = {
                'original': original_func,
                'jit': jit_func,
                'description': description,
                'category': category,
                'call_count': 0,
                'total_time': 0.0,
                'jit_time': 0.0,
                'original_time': 0.0
            }
            
            if not name in self._performance_stats:
                self._performance_stats[name] = {
                    'calls': 0,
                    'jit_calls': 0,
                    'original_calls': 0,
                    'total_time': 0.0,
                    'jit_time': 0.0,
                    'original_time': 0.0,
                    'last_call_time': None
                }
            
            logger.info(f"已注册JIT函数: {name} ({category})")
    
    def get_function(self, name: str) -> Optional[Callable]:
        """获取函数（自动选择JIT或原始版本）
        
        Args:
            name: 函数名称
            
        Returns:
            函数，如果不存在则返回None
        """
        with self._lock:
            if name not in self._jit_functions:
                return None
            
            if self._jit_enabled:
                return self._jit_functions[name]['jit']
            else:
                return self._jit_functions[name]['original']
    
    def get_all_functions(self) -> Dict[str, Dict]:
        """获取所有注册的函数"""
        with self._lock:
            return self._jit_functions.copy()
    
    def get_performance_stats(self) -> Dict[str, Dict]:
        """获取性能统计信息"""
        with self._lock:
            return self._performance_stats.copy()
    
    def record_call(self, name: str, is_jit: bool, execution_time: float):
        """记录函数调用
        
        Args:
            name: 函数名称
            is_jit: 是否使用JIT版本
            execution_time: 执行时间
        """
        with self._lock:
            if name not in self._performance_stats:
                return
            
            stats = self._performance_stats[name]
            stats['calls'] += 1
            stats['total_time'] += execution_time
            stats['last_call_time'] = time.time()
            
            if is_jit:
                stats['jit_calls'] += 1
                stats['jit_time'] += execution_time
            else:
                stats['original_calls'] += 1
                stats['original_time'] += execution_time
    
    def get_summary(self) -> Dict[str, Any]:
        """获取JIT使用摘要"""
        with self._lock:
            total_calls = sum(s['calls'] for s in self._performance_stats.values())
            total_jit_calls = sum(s['jit_calls'] for s in self._performance_stats.values())
            total_original_calls = sum(s['original_calls'] for s in self._performance_stats.values())
            
            jit_usage_rate = (total_jit_calls / total_calls * 100) if total_calls > 0 else 0
            
            return {
                'total_functions': len(self._jit_functions),
                'total_calls': total_calls,
                'jit_calls': total_jit_calls,
                'original_calls': total_original_calls,
                'jit_usage_rate': jit_usage_rate,
                'jit_enabled': self._jit_enabled
            }


# 全局AutoJIT实例
auto_jit_instance = AutoJIT()


def auto_jit(
    name: Optional[str] = None,
    description: str = "",
    category: str = "general",
    cache: bool = True,
    fastmath: bool = True,
    parallel: bool = False
):
    """自动JIT优化装饰器
    
    使用方法:
        @auto_jit()
        def my_function(x, y):
            return x + y
        
        @auto_jit(name="my_func", description="My function", category="math")
        def my_function(x, y):
            return x + y
    
    Args:
        name: 函数名称（可选，默认使用函数名）
        description: 函数描述
        category: 函数分类
        cache: 是否启用Numba缓存
        fastmath: 是否启用快速数学运算
        parallel: 是否启用并行计算
    
    Returns:
        装饰后的函数
    """
    def decorator(func: Callable) -> Callable:
        # 获取函数名称
        func_name = name if name is not None else func.__name__
        
        # 创建JIT版本
        try:
            jit_func = njit(cache=cache, fastmath=fastmath, parallel=parallel)(func)
            jit_created = True
        except Exception as e:
            logger.warning(f"无法为函数 {func_name} 创建JIT版本: {e}")
            jit_func = func
            jit_created = False
        
        # 注册函数
        auto_jit_instance.register_function(
            name=func_name,
            original_func=func,
            jit_func=jit_func,
            description=description,
            category=category
        )
        
        # 创建包装函数
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取函数（自动选择JIT或原始版本）
            selected_func = auto_jit_instance.get_function(func_name)
            
            if selected_func is None:
                selected_func = func
            
            # 执行函数并记录性能
            start_time = time.time()
            try:
                result = selected_func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # 记录调用
                is_jit = (selected_func == jit_func) and jit_created
                auto_jit_instance.record_call(func_name, is_jit, execution_time)
                
                return result
            except Exception as e:
                logger.error(f"函数 {func_name} 执行失败: {e}")
                raise
        
        # 添加元数据
        wrapper._auto_jit_info = {
            'name': func_name,
            'description': description,
            'category': category,
            'jit_created': jit_created
        }
        
        return wrapper
    
    return decorator


def auto_jit_array(
    name: Optional[str] = None,
    description: str = "",
    category: str = "array",
    cache: bool = True,
    fastmath: bool = True,
    parallel: bool = True
):
    """自动JIT优化装饰器（数组操作专用）
    
    专门用于处理NumPy数组操作的JIT优化装饰器
    默认启用并行计算
    
    Args:
        name: 函数名称（可选，默认使用函数名）
        description: 函数描述
        category: 函数分类
        cache: 是否启用Numba缓存
        fastmath: 是否启用快速数学运算
        parallel: 是否启用并行计算
    
    Returns:
        装饰后的函数
    """
    return auto_jit(
        name=name,
        description=description,
        category=category,
        cache=cache,
        fastmath=fastmath,
        parallel=parallel
    )


def auto_jit_loop(
    name: Optional[str] = None,
    description: str = "",
    category: str = "loop",
    cache: bool = True,
    fastmath: bool = True,
    parallel: bool = False
):
    """自动JIT优化装饰器（循环密集型专用）
    
    专门用于处理循环密集型操作的JIT优化装饰器
    
    Args:
        name: 函数名称（可选，默认使用函数名）
        description: 函数描述
        category: 函数分类
        cache: 是否启用Numba缓存
        fastmath: 是否启用快速数学运算
        parallel: 是否启用并行计算
    
    Returns:
        装饰后的函数
    """
    return auto_jit(
        name=name,
        description=description,
        category=category,
        cache=cache,
        fastmath=fastmath,
        parallel=parallel
    )


def discover_and_register(module_name: str, pattern: str = "calculate_") -> List[str]:
    """自动发现并注册模块中的函数
    
    Args:
        module_name: 模块名称
        pattern: 函数名匹配模式
    
    Returns:
        注册的函数名称列表
    """
    import importlib
    
    registered = []
    
    try:
        module = importlib.import_module(module_name)
        
        # 遍历模块中的所有函数
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # 检查函数名是否匹配模式
            if pattern in name.lower():
                # 检查函数是否已经有auto_jit装饰器
                if hasattr(obj, '_auto_jit_info'):
                    logger.info(f"函数 {name} 已有auto_jit装饰器，跳过")
                    continue
                
                # 尝试创建JIT版本
                try:
                    # 自动添加装饰器
                    decorated_func = auto_jit(name=name, category="auto_discovered")(obj)
                    
                    # 替换模块中的函数
                    setattr(module, name, decorated_func)
                    
                    registered.append(name)
                    logger.info(f"自动发现并注册函数: {name}")
                except Exception as e:
                    logger.warning(f"无法为函数 {name} 创建JIT版本: {e}")
    
    except ImportError as e:
        logger.error(f"无法导入模块 {module_name}: {e}")
    
    return registered


def get_auto_jit_summary() -> Dict[str, Any]:
    """获取AutoJIT系统摘要"""
    return auto_jit_instance.get_summary()


def get_auto_jit_functions() -> Dict[str, Dict]:
    """获取所有AutoJIT函数"""
    return auto_jit_instance.get_all_functions()


def get_auto_jit_stats() -> Dict[str, Dict]:
    """获取AutoJIT性能统计"""
    return auto_jit_instance.get_performance_stats()


def enable_auto_jit():
    """启用AutoJIT优化"""
    auto_jit_instance.enable_jit()


def disable_auto_jit():
    """禁用AutoJIT优化"""
    auto_jit_instance.disable_jit()


def is_auto_jit_enabled() -> bool:
    """检查AutoJIT优化是否启用"""
    return auto_jit_instance.is_jit_enabled()
