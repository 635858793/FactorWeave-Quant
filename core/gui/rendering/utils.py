#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
渲染引擎工具模块

提供图表渲染系统的基础工具函数和辅助类

作者: FactorWeave-Quant团队
版本: 1.0
"""

import os
import sys
import json
import pickle
from utils.safe_pickle import safe_load
import traceback
import time
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from functools import wraps, lru_cache
from pathlib import Path
import threading
from contextlib import contextmanager
import warnings
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from loguru import logger

# 渲染引擎相关导入
from .pyqtgraph_engine import ChartType


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class PerformanceMetrics:
    """性能指标"""
    name: str
    value: float
    unit: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    category: str = "general"
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category,
            'description': self.description
        }


@dataclass
class SystemInfo:
    """系统信息"""
    python_version: str
    platform: str
    architecture: str
    cpu_count: int
    memory_total: int
    memory_available: int
    gpu_info: List[str] = field(default_factory=list)
    display_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'python_version': self.python_version,
            'platform': self.platform,
            'architecture': self.architecture,
            'cpu_count': self.cpu_count,
            'memory_total': self.memory_total,
            'memory_available': self.memory_available,
            'gpu_info': self.gpu_info,
            'display_info': self.display_info
        }


class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self._lock = threading.Lock()
        
    def add_metric(self, metric: PerformanceMetrics):
        """添加性能指标"""
        with self._lock:
            self.metrics.append(metric)
            
    def get_metrics(self, category: Optional[str] = None, 
                   name: Optional[str] = None) -> List[PerformanceMetrics]:
        """获取性能指标"""
        with self._lock:
            filtered_metrics = self.metrics.copy()
            
            if category:
                filtered_metrics = [m for m in filtered_metrics if m.category == category]
                
            if name:
                filtered_metrics = [m for m in filtered_metrics if m.name == name]
                
            return filtered_metrics
            
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        with self._lock:
            if not self.metrics:
                return {}
                
            total_count = len(self.metrics)
            categories = set(m.category for m in self.metrics)
            
            summary = {
                'total_metrics': total_count,
                'categories': list(categories),
                'latest_timestamp': max(m.timestamp for m in self.metrics).isoformat(),
                'oldest_timestamp': min(m.timestamp for m in self.metrics).isoformat()
            }
            
            # 按类别统计
            category_stats = {}
            for category in categories:
                category_metrics = [m for m in self.metrics if m.category == category]
                category_stats[category] = {
                    'count': len(category_metrics),
                    'avg_value': np.mean([m.value for m in category_metrics]),
                    'min_value': min([m.value for m in category_metrics]),
                    'max_value': max([m.value for m in category_metrics])
                }
                
            summary['category_stats'] = category_stats
            return summary
            
    def clear(self):
        """清空指标"""
        with self._lock:
            self.metrics.clear()


def profile_execution(func: Callable = None, *, category: str = "execution", 
                     name: str = None):
    """执行时间分析装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = None
            error = None
            
            try:
                result = f(*args, **kwargs)
            except Exception as e:
                error = e
                raise
            finally:
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                
                # 添加到性能分析器
                profiler = get_profiler()
                metric_name = name or f"{f.__module__}.{f.__name__}"
                metric = PerformanceMetrics(
                    name=metric_name,
                    value=execution_time,
                    unit="seconds",
                    category=category,
                    description=f"Function execution time"
                )
                profiler.add_metric(metric)
                
                logger.debug(f"执行分析: {metric_name} - {execution_time:.4f}s")
                
            return result
        return wrapper
    
    if func is None:
        return decorator
    return decorator(func)


# 全局性能分析器实例
_profiler = PerformanceProfiler()


def get_profiler() -> PerformanceProfiler:
    """获取全局性能分析器"""
    return _profiler


def get_system_info() -> SystemInfo:
    """获取系统信息"""
    try:
        import psutil
        
        # 基本系统信息
        python_version = sys.version
        platform = sys.platform
        architecture = os.environ.get('PROCESSOR_ARCHITECTURE', 'unknown')
        
        # CPU信息
        cpu_count = psutil.cpu_count()
        
        # 内存信息
        memory = psutil.virtual_memory()
        memory_total = memory.total
        memory_available = memory.available
        
        # GPU信息
        gpu_info = []
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_info.append(f"{gpu.name} ({gpu.memoryTotal}MB)")
        except ImportError:
            pass
            
        # 显示信息
        display_info = {}
        try:
            import PyQt5.QtWidgets
            app = PyQt5.QtWidgets.QApplication.instance()
            if app:
                display_info = {
                    'screen_count': app.desktop().screenCount(),
                    'screen_size': {
                        'width': app.desktop().screen().width(),
                        'height': app.desktop().screen().height()
                    }
                }
        except Exception:
            pass
            
        return SystemInfo(
            python_version=python_version,
            platform=platform,
            architecture=architecture,
            cpu_count=cpu_count,
            memory_total=memory_total,
            memory_available=memory_available,
            gpu_info=gpu_info,
            display_info=display_info
        )
        
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return SystemInfo(
            python_version=sys.version,
            platform=sys.platform,
            architecture=os.environ.get('PROCESSOR_ARCHITECTURE', 'unknown'),
            cpu_count=1,
            memory_total=0,
            memory_available=0
        )


@contextmanager
def performance_monitor(category: str, name: str):
    """性能监控上下文管理器"""
    start_time = time.perf_counter()
    profiler = get_profiler()
    
    try:
        yield
    finally:
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        metric = PerformanceMetrics(
            name=name,
            value=duration,
            unit="seconds",
            category=category,
            description=f"Context manager execution time"
        )
        profiler.add_metric(metric)


class ConfigurationManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "chart_config.json"):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
        # 默认配置
        self.default_config = {
            'rendering': {
                'default_width': 800,
                'default_height': 600,
                'antialias': True,
                'background_color': '#ffffff',
                'grid_color': '#e0e0e0'
            },
            'performance': {
                'max_points': 5000,
                'batch_size': 1000,
                'cache_size': 100,
                'optimization_level': 'medium'
            },
            'interaction': {
                'enable_zoom': True,
                'enable_pan': True,
                'enable_hover': True,
                'tooltip_delay': 500
            },
            'real_time': {
                'update_interval': 100,
                'max_buffer_size': 1000,
                'enable_animation': True
            }
        }
        
        self.load_config()
        
    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"配置文件加载成功: {self.config_file}")
            else:
                self.config = self.default_config.copy()
                self.save_config()
                logger.info("使用默认配置")
                
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = self.default_config.copy()
            
    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"配置文件保存成功: {self.config_file}")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self._lock:
            keys = key.split('.')
            value = self.config
            
            try:
                for k in keys:
                    value = value[k]
                return value
            except (KeyError, TypeError):
                return default
                
    def set(self, key: str, value: Any):
        """设置配置值"""
        with self._lock:
            keys = key.split('.')
            config = self.config
            
            # 导航到父级
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
                
            # 设置值
            config[keys[-1]] = value
            
    def reset_to_default(self):
        """重置为默认配置"""
        with self._lock:
            self.config = self.default_config.copy()
            self.save_config()
            
    def export_config(self, file_path: str):
        """导出配置"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"配置导出成功: {file_path}")
            
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            
    def import_config(self, file_path: str):
        """导入配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
                
            # 合并配置
            self.config.update(imported_config)
            self.save_config()
            logger.info(f"配置导入成功: {file_path}")
            
        except Exception as e:
            logger.error(f"导入配置失败: {e}")


class DataValidator:
    """数据验证器"""
    
    @staticmethod
    def validate_ohlc_data(data: pd.DataFrame) -> Tuple[bool, List[str]]:
        """验证OHLC数据"""
        errors = []
        
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            errors.append(f"缺少必需列: {missing_columns}")
            
        # 验证数据类型
        for col in required_columns:
            if col in data.columns:
                if not pd.api.types.is_numeric_dtype(data[col]):
                    errors.append(f"列 {col} 必须为数值类型")
                    
        # 验证逻辑关系
        if 'high' in data.columns and 'low' in data.columns:
            invalid_rows = data['high'] < data['low']
            if invalid_rows.any():
                errors.append(f"存在high < low的数据行: {invalid_rows.sum()}条")
                
        if all(col in data.columns for col in required_columns):
            # 验证OHLC逻辑
            invalid_open = data['open'] > data['high'] if 'open' in data.columns else False
            invalid_open2 = data['open'] < data['low'] if 'open' in data.columns else False
            invalid_close = data['close'] > data['high'] if 'close' in data.columns else False
            invalid_close2 = data['close'] < data['low'] if 'close' in data.columns else False
            
            total_invalid = (invalid_open | invalid_open2 | invalid_close | invalid_close2).sum()
            if total_invalid > 0:
                errors.append(f"存在OHLC逻辑错误的数据行: {total_invalid}条")
                
        return len(errors) == 0, errors
        
    @staticmethod
    def validate_time_series(data: pd.DataFrame, time_column: str = 'time') -> Tuple[bool, List[str]]:
        """验证时间序列数据"""
        errors = []
        
        if time_column not in data.columns:
            errors.append(f"缺少时间列: {time_column}")
        else:
            # 检查时间格式
            try:
                pd.to_datetime(data[time_column])
            except Exception as e:
                errors.append(f"时间格式无效: {e}")
                
            # 检查时间顺序
            try:
                time_series = pd.to_datetime(data[time_column])
                if not time_series.is_monotonic_increasing:
                    errors.append("时间序列不单调递增")
            except Exception:
                pass
                
        return len(errors) == 0, errors
        
    @staticmethod
    def validate_numeric_data(data: pd.DataFrame, columns: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
        """验证数值数据"""
        errors = []
        
        if columns is None:
            numeric_columns = data.select_dtypes(include=[np.number]).columns.tolist()
        else:
            numeric_columns = [col for col in columns if col in data.columns]
            
        if not numeric_columns:
            errors.append("未找到数值列")
        else:
            for col in numeric_columns:
                # 检查NaN值
                nan_count = data[col].isna().sum()
                if nan_count > 0:
                    errors.append(f"列 {col} 包含 {nan_count} 个NaN值")
                    
                # 检查无穷大值
                inf_count = np.isinf(data[col]).sum()
                if inf_count > 0:
                    errors.append(f"列 {col} 包含 {inf_count} 个无穷大值")
                    
        return len(errors) == 0, errors


class ChartStyleHelper:
    """图表样式助手"""
    
    # 预定义颜色方案
    color_schemes = {
        'default': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'],
        'professional': ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E'],
        'trading': ['#00ff00', '#ff0000', '#0000ff', '#ffff00', '#ff00ff'],
        'dark': ['#4A90E2', '#F5A623', '#7ED321', '#D0021B', '#9013FE'],
        'bright': ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'],
        'monochrome': ['#2C3E50', '#34495E', '#7F8C8D', '#95A5A6', '#BDC3C7']
    }
    
    # 字体配置
    font_configs = {
        'default': {'family': 'Arial', 'size': 12, 'weight': 'normal'},
        'title': {'family': 'Arial', 'size': 16, 'weight': 'bold'},
        'axis': {'family': 'Arial', 'size': 10, 'weight': 'normal'},
        'legend': {'family': 'Arial', 'size': 9, 'weight': 'normal'}
    }
    
    @classmethod
    def get_color_scheme(cls, scheme_name: str = 'default') -> List[str]:
        """获取颜色方案"""
        return cls.color_schemes.get(scheme_name, cls.color_schemes['default'])
        
    @classmethod
    def get_font_config(cls, font_type: str = 'default') -> Dict[str, Any]:
        """获取字体配置"""
        return cls.font_configs.get(font_type, cls.font_configs['default'])
        
    @classmethod
    def generate_contrast_colors(cls, base_color: str, count: int = 5) -> List[str]:
        """生成对比色"""
        try:
            import matplotlib.colors as mcolors
            
            base_rgb = mcolors.hex2color(base_color)
            colors = []
            
            for i in range(count):
                # 调整亮度
                factor = 0.3 + (i * 0.1)
                color = tuple(min(1.0, c * factor) for c in base_rgb)
                colors.append(mcolors.rgb2hex(color))
                
            return colors
            
        except Exception as e:
            logger.error(f"生成对比色失败: {e}")
            return cls.color_schemes['default'][:count]


class FileHandler:
    """文件处理器"""
    
    @staticmethod
    def save_chart_data(data: Dict[str, Any], file_path: str, format: str = 'json'):
        """保存图表数据"""
        try:
            if format.lower() == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            elif format.lower() == 'pickle':
                with open(file_path, 'wb') as f:
                    pickle.dump(data, f)
            else:
                raise ValueError(f"不支持的文件格式: {format}")
                
            logger.info(f"图表数据保存成功: {file_path}")
            
        except Exception as e:
            logger.error(f"保存图表数据失败: {e}")
            raise
            
    @staticmethod
    def load_chart_data(file_path: str, format: str = 'json') -> Dict[str, Any]:
        """加载图表数据"""
        try:
            if format.lower() == 'json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif format.lower() == 'pickle':
                with open(file_path, 'rb') as f:
                    return safe_load(f)
            else:
                raise ValueError(f"不支持的文件格式: {format}")
                
        except Exception as e:
            logger.error(f"加载图表数据失败: {e}")
            raise
            
    @staticmethod
    def export_chart_config(config: Dict[str, Any], file_path: str):
        """导出图表配置"""
        try:
            # 添加元信息
            export_data = {
                'metadata': {
                    'export_time': datetime.now().isoformat(),
                    'version': '1.0',
                    'format': 'chart_config'
                },
                'config': config
            }
            
            FileHandler.save_chart_data(export_data, file_path, 'json')
            logger.info(f"图表配置导出成功: {file_path}")
            
        except Exception as e:
            logger.error(f"导出图表配置失败: {e}")
            raise


class ChartTypeHelper:
    """图表类型助手"""
    
    @staticmethod
    def get_recommended_chart_type(data_type: str, data_shape: Tuple[int, ...] = None) -> ChartType:
        """获取推荐图表类型"""
        data_type = data_type.lower()
        
        if data_type in ['ohlc', 'ohlcv', 'candlestick']:
            return ChartType.CANDLESTICK
        elif data_type in ['time_series', 'timeseries']:
            return ChartType.LINE_CHART
        elif data_type in ['categorical', 'category']:
            return ChartType.BAR_CHART
        elif data_type in ['scatter', 'correlation']:
            return ChartType.SCATTER_PLOT
        else:
            # 根据数据形状推测
            if data_shape and len(data_shape) == 2:
                if data_shape[1] >= 4:  # 可能是OHLC数据
                    return ChartType.CANDLESTICK
                elif data_shape[1] == 2:  # XY数据
                    return ChartType.SCATTER_PLOT
            return ChartType.LINE_CHART
            
    @staticmethod
    def validate_chart_type_for_data(chart_type: ChartType, data: pd.DataFrame) -> Tuple[bool, List[str]]:
        """验证图表类型是否适合数据"""
        errors = []
        
        if chart_type == ChartType.CANDLESTICK:
            required_cols = ['open', 'high', 'low', 'close']
            missing_cols = [col for col in required_cols if col not in data.columns]
            if missing_cols:
                errors.append(f"K线图需要列: {missing_cols}")
                
        elif chart_type in [ChartType.LINE_CHART, ChartType.SCATTER_PLOT]:
            if data.empty:
                errors.append("线图和散点图需要非空数据")
                
        elif chart_type == ChartType.BAR_CHART:
            if 'category' not in data.columns:
                errors.append("柱状图需要category列")
                
        return len(errors) == 0, errors


@lru_cache(maxsize=128)
def get_cached_system_info() -> Dict[str, Any]:
    """获取缓存的系统信息"""
    return get_system_info().to_dict()


# 导出的工具函数
__all__ = [
    'PerformanceProfiler',
    'PerformanceMetrics',
    'SystemInfo',
    'profile_execution',
    'get_profiler',
    'get_system_info',
    'performance_monitor',
    'ConfigurationManager',
    'DataValidator',
    'ChartStyleHelper',
    'FileHandler',
    'ChartTypeHelper',
    'get_cached_system_info',
    'LogLevel'
]