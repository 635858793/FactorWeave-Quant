"""
渲染器抽象基类

提供图表渲染器的通用功能实现，继承自IChartRenderer接口。
支持统一的数据验证、错误处理、性能监控和资源管理。
"""

import os
import time
import traceback
from abc import ABC
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np
from matplotlib.axes import Axes
from loguru import logger
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .interfaces import IChartRenderer


class BaseChartRenderer(IChartRenderer):
    """
    图表渲染器抽象基类
    
    提供所有图表渲染器的通用功能：
    - 数据验证和预处理
    - 错误处理和日志记录
    - 性能监控
    - 样式管理
    - 资源清理
    """
    
    def __init__(self, enable_logging: bool = True, 
                 enable_performance_monitoring: bool = True):
        """
        初始化渲染器基类
        
        Args:
            enable_logging: 是否启用日志记录
            enable_performance_monitoring: 是否启用性能监控
        """
        self.enable_logging = enable_logging
        self.enable_performance_monitoring = enable_performance_monitoring
        
        # 性能统计
        self.performance_stats = {
            'render_calls': 0,
            'total_render_time': 0.0,
            'data_points_processed': 0,
            'errors_count': 0,
            'last_render_time': 0.0,
            'average_render_time': 0.0,
            'max_render_time': 0.0,
            'min_render_time': float('inf')
        }
        
        # 渲染器配置
        self.config = {}
        self.is_initialized = False
        
        # 样式配置
        self.default_styles = self._get_default_styles()
    
    def _get_default_styles(self) -> Dict[str, Any]:
        """获取默认样式配置"""
        return {
            'candlestick': {
                'up_color': '#ff0000',
                'down_color': '#00ff00', 
                'up_edge_color': '#cc0000',
                'down_edge_color': '#008800',
                'alpha': 0.8,
                'width': 0.8
            },
            'volume': {
                'up_color': '#ff4444',
                'down_color': '#44ff44',
                'alpha': 0.6,
                'width': 0.6
            },
            'line': {
                'color': '#0066cc',
                'linewidth': 1.5,
                'alpha': 0.9
            },
            'indicators': {
                'ma_color': '#ffaa00',
                'macd_color': '#aa00ff',
                'rsi_color': '#00aaaa',
                'boll_color': '#aaaa00',
                'linewidth': 1.0,
                'alpha': 0.7
            }
        }
    
    def _log(self, message: str, level: str = "INFO"):
        """内部日志记录方法"""
        if self.enable_logging:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] [{self.__class__.__name__}] {level}: {message}"
            logger.debug(log_message)
    
    def _measure_performance(self, operation_name: str):
        """性能测量装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not self.enable_performance_monitoring:
                    return func(*args, **kwargs)
                
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    success = True
                except Exception as e:
                    self.performance_stats['errors_count'] += 1
                    self._log(f"渲染错误: {str(e)}", "ERROR")
                    self._log(f"错误详情: {traceback.format_exc()}", "DEBUG")
                    raise e
                finally:
                    end_time = time.perf_counter()
                    render_time = end_time - start_time
                    
                    # 更新性能统计
                    self.performance_stats['render_calls'] += 1
                    self.performance_stats['total_render_time'] += render_time
                    self.performance_stats['last_render_time'] = render_time
                    
                    # 计算平均、最大、最小渲染时间
                    calls = self.performance_stats['render_calls']
                    total_time = self.performance_stats['total_render_time']
                    self.performance_stats['average_render_time'] = total_time / calls
                    self.performance_stats['max_render_time'] = max(
                        self.performance_stats['max_render_time'], render_time
                    )
                    if render_time < self.performance_stats['min_render_time']:
                        self.performance_stats['min_render_time'] = render_time
                    
                    self._log(f"{operation_name} 完成，耗时: {render_time:.4f}s", "DEBUG")
                
                return result
            return wrapper
        return decorator
    
    def _validate_data(self, data: Union[pd.DataFrame, pd.Series], 
                      required_columns: List[str] = None) -> bool:
        """
        验证数据格式和完整性
        
        Args:
            data: 要验证的数据
            required_columns: 必需的列名列表
            
        Returns:
            bool: 数据有效返回True，否则返回False
        """
        try:
            if data is None or data.empty:
                self._log("数据为空", "WARNING")
                return False
            
            if required_columns:
                missing_columns = [col for col in required_columns 
                                 if col not in data.columns]
                if missing_columns:
                    self._log(f"缺少必需列: {missing_columns}", "WARNING")
                    return False
            
            # 检查数据类型
            if isinstance(data, pd.DataFrame):
                self.performance_stats['data_points_processed'] += len(data)
            elif isinstance(data, pd.Series):
                self.performance_stats['data_points_processed'] += len(data)
            
            return True
            
        except Exception as e:
            self._log(f"数据验证失败: {str(e)}", "ERROR")
            return False
    
    def _get_merged_style(self, chart_type: str, user_style: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        合并用户样式和默认样式
        
        Args:
            chart_type: 图表类型 ('candlestick', 'volume', 'line', 'indicators')
            user_style: 用户提供的样式
            
        Returns:
            Dict[str, Any]: 合并后的样式
        """
        default_style = self.default_styles.get(chart_type, {})
        if user_style:
            merged_style = {**default_style, **user_style}
        else:
            merged_style = default_style.copy()
        
        return merged_style
    
    def _prepare_datetime_axis(self, data: pd.DataFrame, 
                              use_datetime_axis: bool, 
                              x: np.ndarray = None) -> np.ndarray:
        """
        准备datetime X轴数据
        
        Args:
            data: 数据DataFrame
            use_datetime_axis: 是否使用datetime轴
            x: 预提供的X轴数据
            
        Returns:
            np.ndarray: 处理后的X轴数据
        """
        if x is not None:
            return x
        
        if use_datetime_axis:
            if 'datetime' in data.columns:
                try:
                    datetime_series = pd.to_datetime(data['datetime'])
                    return mdates.date2num(datetime_series)
                except Exception as e:
                    self._log(f"datetime转换失败，使用索引: {e}", "WARNING")
                    return np.arange(len(data))
            elif isinstance(data.index, pd.DatetimeIndex):
                return mdates.date2num(data.index.to_pydatetime())
            else:
                self._log("数据没有datetime索引，使用数字索引", "WARNING")
                return np.arange(len(data))
        else:
            return np.arange(len(data))
    
    def render_candlesticks(self, ax: Axes, data: pd.DataFrame, 
                          style: Dict[str, Any] = None, 
                          x: np.ndarray = None, 
                          use_datetime_axis: bool = True) -> bool:
        """
        渲染K线图的抽象实现（子类需重写具体实现）
        """
        self._log("render_candlesticks方法需要子类实现", "ERROR")
        return False
    
    def render_volume(self, ax: Axes, data: pd.DataFrame, 
                     style: Dict[str, Any] = None, 
                     x: np.ndarray = None, 
                     use_datetime_axis: bool = True) -> bool:
        """
        渲染成交量图的抽象实现（子类需重写具体实现）
        """
        self._log("render_volume方法需要子类实现", "ERROR")
        return False
    
    def render_line(self, ax: Axes, data: pd.Series, 
                   style: Dict[str, Any] = None) -> bool:
        """
        渲染线图的抽象实现（子类需重写具体实现）
        """
        self._log("render_line方法需要子类实现", "ERROR")
        return False
    
    def render_technical_indicators(self, ax: Axes, data: pd.DataFrame, 
                                  indicators: List[str], 
                                  style: Dict[str, Any] = None) -> bool:
        """
        渲染技术指标的抽象实现（子类需重写具体实现）
        """
        self._log("render_technical_indicators方法需要子类实现", "ERROR")
        return False
    
    def clear_chart(self, ax: Axes) -> bool:
        """
        清空图表内容
        
        Args:
            ax: matplotlib轴对象
            
        Returns:
            bool: 清空成功返回True，失败返回False
        """
        try:
            ax.clear()
            self._log("图表已清空", "DEBUG")
            return True
        except Exception as e:
            self._log(f"清空图表失败: {str(e)}", "ERROR")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        获取渲染器能力信息（子类可重写）
        
        Returns:
            Dict[str, bool]: 基础能力标识
        """
        return {
            'datetime_axis': True,
            'performance_monitoring': self.enable_performance_monitoring,
            'error_handling': True,
            'data_validation': True,
            'style_customization': True,
            'multi_chart_types': True
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            Dict[str, Any]: 性能统计字典
        """
        stats = self.performance_stats.copy()
        
        # 如果没有渲染调用，避免除零错误
        if stats['render_calls'] == 0:
            stats['min_render_time'] = 0.0
        
        return stats
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """
        初始化渲染器
        
        Args:
            config: 配置参数字典
            
        Returns:
            bool: 初始化成功返回True，失败返回False
        """
        try:
            if config:
                self.config.update(config)
            
            self.is_initialized = True
            self._log("渲染器初始化完成", "INFO")
            return True
            
        except Exception as e:
            self._log(f"渲染器初始化失败: {str(e)}", "ERROR")
            return False
    
    def cleanup(self) -> bool:
        """
        清理资源
        
        Returns:
            bool: 清理成功返回True，失败返回False
        """
        try:
            # 重置性能统计
            self.performance_stats = {
                'render_calls': 0,
                'total_render_time': 0.0,
                'data_points_processed': 0,
                'errors_count': 0,
                'last_render_time': 0.0,
                'average_render_time': 0.0,
                'max_render_time': 0.0,
                'min_render_time': float('inf')
            }
            
            self.is_initialized = False
            self._log("渲染器资源清理完成", "INFO")
            return True
            
        except Exception as e:
            self._log(f"渲染器清理失败: {str(e)}", "ERROR")
            return False
    
    def get_renderer_info(self) -> Dict[str, Any]:
        """
        获取渲染器详细信息
        
        Returns:
            Dict[str, Any]: 渲染器信息字典
        """
        return {
            'renderer_type': self.__class__.__name__,
            'is_initialized': self.is_initialized,
            'enable_logging': self.enable_logging,
            'enable_performance_monitoring': self.enable_performance_monitoring,
            'config': self.config,
            'performance_stats': self.get_performance_stats(),
            'capabilities': self.get_capabilities()
        }