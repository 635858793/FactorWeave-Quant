"""
统一渲染器接口定义

提供所有图表渲染器的标准接口，确保系统架构的一致性和可扩展性。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure


class IChartRenderer(ABC):
    """
    统一渲染器接口
    
    定义所有图表渲染器必须实现的核心方法，确保系统架构的一致性。
    支持多种渲染后端（matplotlib、WebGPU等）和不同类型的图表渲染。
    """
    
    @abstractmethod
    def render_candlesticks(self, ax: Axes, data: pd.DataFrame, 
                          style: Dict[str, Any] = None, 
                          x: np.ndarray = None, 
                          use_datetime_axis: bool = True) -> bool:
        """
        渲染K线图（蜡烛图）
        
        Args:
            ax: matplotlib轴对象
            data: 包含OHLC数据的DataFrame
            style: 样式配置字典
            x: X轴数据坐标
            use_datetime_axis: 是否使用datetime X轴
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def render_volume(self, ax: Axes, data: pd.DataFrame, 
                     style: Dict[str, Any] = None, 
                     x: np.ndarray = None, 
                     use_datetime_axis: bool = True) -> bool:
        """
        渲染成交量图
        
        Args:
            ax: matplotlib轴对象
            data: 包含OHLCV数据的DataFrame
            style: 样式配置字典
            x: X轴数据坐标
            use_datetime_axis: 是否使用datetime X轴
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def render_line(self, ax: Axes, data: pd.Series, 
                   style: Dict[str, Any] = None) -> bool:
        """
        渲染线图
        
        Args:
            ax: matplotlib轴对象
            data: 要绘制的数据序列
            style: 样式配置字典
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def render_technical_indicators(self, ax: Axes, data: pd.DataFrame, 
                                  indicators: List[str], 
                                  style: Dict[str, Any] = None) -> bool:
        """
        渲染技术指标
        
        Args:
            ax: matplotlib轴对象
            data: 原始数据DataFrame
            indicators: 要渲染的技术指标列表
            style: 样式配置字典
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def clear_chart(self, ax: Axes) -> bool:
        """
        清空图表内容
        
        Args:
            ax: 要清空的matplotlib轴对象
            
        Returns:
            bool: 清空成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        获取渲染器能力信息
        
        Returns:
            Dict[str, bool]: 能力标识字典，如{
                'webgpu_enabled': True,
                'hardware_acceleration': True,
                'progressive_rendering': True,
                'batch_processing': True,
                'datetime_axis': True
            }
        """
        pass
    
    @abstractmethod
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            Dict[str, Any]: 性能统计字典，包含渲染时间、数据量等信息
        """
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """
        初始化渲染器
        
        Args:
            config: 配置参数字典
            
        Returns:
            bool: 初始化成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """
        清理资源
        
        Returns:
            bool: 清理成功返回True，失败返回False
        """
        pass
    
    @abstractmethod
    def get_renderer_info(self) -> Dict[str, Any]:
        """
        获取渲染器详细信息
        
        Returns:
            Dict[str, Any]: 渲染器信息字典
        """
        pass
