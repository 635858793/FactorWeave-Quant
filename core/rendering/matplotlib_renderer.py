"""
Matplotlib图表渲染器

基于matplotlib的高性能图表渲染器，使用向量化操作优化性能。
继承自BaseChartRenderer，提供K线图、成交量图和线图的高效渲染。
"""

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.collections import PolyCollection
import matplotlib.dates as mdates
from typing import Dict, Any, List

from .base_renderer import BaseChartRenderer


class MatplotlibChartRenderer(BaseChartRenderer):
    """
    Matplotlib图表渲染器
    
    高性能渲染器，使用向量化操作和PolyCollection批量渲染技术。
    主要优化：
    1. 完全向量化numpy操作，避免Python循环
    2. PolyCollection批量渲染，减少绘图调用
    3. 智能的datetime轴处理
    4. 统一的数据验证和错误处理
    """
    
    def __init__(self, enable_logging: bool = True, 
                 enable_performance_monitoring: bool = True):
        super().__init__(enable_logging, enable_performance_monitoring)
        
        self._log("MatplotlibChartRenderer初始化完成", "INFO")
    
    def render_candlesticks(self, ax: Axes, data: pd.DataFrame,
                          style: Dict[str, Any] = None, 
                          x: np.ndarray = None, 
                          use_datetime_axis: bool = True) -> bool:
        """
        高性能K线图渲染（完全向量化实现）
        
        Args:
            ax: matplotlib轴对象
            data: 包含OHLC数据的DataFrame
            style: 样式配置字典
            x: X轴数据坐标
            use_datetime_axis: 是否使用datetime X轴
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        try:
            # 数据验证
            required_columns = ['open', 'high', 'low', 'close']
            if not self._validate_data(data, required_columns):
                return False
            
            merged_style = self._get_merged_style('candlestick', style)
            xvals = self._prepare_datetime_axis(data, use_datetime_axis, x)
            
            # 计算K线宽度
            if use_datetime_axis and len(xvals) > 1:
                avg_interval = np.mean(np.diff(xvals))
                width = max(0.3, avg_interval * 0.6)
            else:
                width = 0.6
            
            # 性能优化：完全向量化的numpy操作
            opens = data['open'].values
            highs = data['high'].values  
            lows = data['low'].values
            closes = data['close'].values
            
            # 涨跌判断
            is_up = closes >= opens
            
            # 性能优化：批量构建K线顶点，使用PolyCollection
            def build_candle_verts(indices, is_up_mask):
                """批量构建K线图顶点"""
                if len(indices) == 0:
                    return np.empty((0, 6, 2))
                
                idx_arr = indices
                n = len(idx_arr)
                verts = np.empty((n, 6, 2), dtype=np.float64)
                
                # 主体矩形顶点 (4个顶点)
                lefts = xvals[idx_arr] - width / 2
                rights = xvals[idx_arr] + width / 2
                
                # 上影线 (2个顶点)
                # 主体矩形
                verts[:, 0, 0] = lefts       # 左下x
                verts[:, 0, 1] = np.where(is_up_mask[idx_arr], opens[idx_arr], closes[idx_arr])  # 左下y
                verts[:, 1, 0] = lefts       # 左上x
                verts[:, 1, 1] = np.where(is_up_mask[idx_arr], closes[idx_arr], opens[idx_arr])  # 左上y
                verts[:, 2, 0] = rights      # 右上x
                verts[:, 2, 1] = np.where(is_up_mask[idx_arr], closes[idx_arr], opens[idx_arr])  # 右上y
                verts[:, 3, 0] = rights      # 右下x
                verts[:, 3, 1] = np.where(is_up_mask[idx_arr], opens[idx_arr], closes[idx_arr])  # 右下y
                
                # 上影线 (从high到max(open, close))
                verts[:, 4, 0] = xvals[idx_arr]         # 上影线x
                verts[:, 4, 1] = highs[idx_arr]         # 上影线y (顶部)
                verts[:, 5, 0] = xvals[idx_arr]         # 上影线x
                verts[:, 5, 1] = np.maximum(opens[idx_arr], closes[idx_arr])  # 上影线y (底部)
                
                return verts
            
            # 分别构建涨跌K线
            up_indices = np.where(is_up)[0]
            down_indices = np.where(~is_up)[0]
            
            verts_up = build_candle_verts(up_indices, is_up)
            verts_down = build_candle_verts(down_indices, is_up)
            
            # 创建PolyCollection并添加到轴
            if len(verts_up) > 0:
                collection_up = PolyCollection(
                    verts_up, 
                    facecolor=merged_style['up_color'], 
                    edgecolor=merged_style['up_edge_color'], 
                    alpha=merged_style['alpha'],
                    linewidths=0.5
                )
                ax.add_collection(collection_up)
            
            if len(verts_down) > 0:
                collection_down = PolyCollection(
                    verts_down, 
                    facecolor=merged_style['down_color'], 
                    edgecolor=merged_style['down_edge_color'], 
                    alpha=merged_style['alpha'],
                    linewidths=0.5
                )
                ax.add_collection(collection_down)
            
            self._log(f"K线图渲染完成: {len(data)}个数据点", "DEBUG")
            return True
            
        except Exception as e:
            self._log(f"K线图渲染失败: {str(e)}", "ERROR")
            return False
    
    def render_volume(self, ax: Axes, data: pd.DataFrame, 
                     style: Dict[str, Any] = None, 
                     x: np.ndarray = None, 
                     use_datetime_axis: bool = True) -> bool:
        """
        高性能成交量图渲染（完全向量化实现）
        
        Args:
            ax: matplotlib轴对象
            data: 包含OHLCV数据的DataFrame
            style: 样式配置字典
            x: X轴数据坐标
            use_datetime_axis: 是否使用datetime X轴
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        try:
            # 数据验证
            required_columns = ['open', 'close', 'volume']
            if not self._validate_data(data, required_columns):
                return False
            
            merged_style = self._get_merged_style('volume', style)
            xvals = self._prepare_datetime_axis(data, use_datetime_axis, x)
            
            # 计算柱状图宽度
            if use_datetime_axis and len(xvals) > 1:
                avg_interval = np.mean(np.diff(xvals))
                bar_width = max(0.3, avg_interval * 0.6)
            else:
                bar_width = 0.3
            
            # 性能优化：完全向量化的numpy操作，避免iterrows()
            volumes = data['volume'].values
            closes = data['close'].values
            opens = data['open'].values
            
            # 向量化计算left和right
            lefts = xvals - bar_width / 2
            rights = xvals + bar_width / 2
            
            # 向量化判断涨跌
            is_up = closes >= opens
            up_indices = np.where(is_up)[0]
            down_indices = np.where(~is_up)[0]
            
            # 性能优化：批量构建成交量柱状图顶点
            def build_volume_verts(indices):
                """批量构建成交量柱状图顶点，返回numpy数组"""
                if len(indices) == 0:
                    return np.empty((0, 4, 2))
                
                idx_arr = indices
                n = len(idx_arr)
                verts = np.empty((n, 4, 2), dtype=np.float64)
                verts[:, 0, 0] = lefts[idx_arr]      # 左下x
                verts[:, 0, 1] = 0                   # 左下y (底部)
                verts[:, 1, 0] = lefts[idx_arr]      # 左上x
                verts[:, 1, 1] = volumes[idx_arr]    # 左上y (顶部)
                verts[:, 2, 0] = rights[idx_arr]     # 右上x
                verts[:, 2, 1] = volumes[idx_arr]    # 右上y (顶部)
                verts[:, 3, 0] = rights[idx_arr]     # 右下x
                verts[:, 3, 1] = 0                   # 右下y (底部)
                return verts
            
            verts_up = build_volume_verts(up_indices)
            verts_down = build_volume_verts(down_indices)
            
            # 创建PolyCollection并添加到轴
            if len(verts_up) > 0:
                collection_up = PolyCollection(
                    verts_up, 
                    facecolor=merged_style['up_color'], 
                    edgecolor='none', 
                    alpha=merged_style['alpha']
                )
                ax.add_collection(collection_up)
            
            if len(verts_down) > 0:
                collection_down = PolyCollection(
                    verts_down, 
                    facecolor=merged_style['down_color'], 
                    edgecolor='none', 
                    alpha=merged_style['alpha']
                )
                ax.add_collection(collection_down)
            
            self._log(f"成交量图渲染完成: {len(data)}个数据点", "DEBUG")
            return True
            
        except Exception as e:
            self._log(f"成交量图渲染失败: {str(e)}", "ERROR")
            return False
    
    def render_line(self, ax: Axes, data: pd.Series, 
                   style: Dict[str, Any] = None) -> bool:
        """
        高性能线图渲染
        
        Args:
            ax: matplotlib轴对象
            data: 要绘制的数据序列
            style: 样式配置字典
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        try:
            # 数据验证
            if not self._validate_data(data):
                return False
            
            merged_style = self._get_merged_style('line', style)
            
            # 使用matplotlib的高性能绘图
            x_data = np.arange(len(data))
            y_data = data.values
            
            ax.plot(x_data, y_data, 
                   color=merged_style['color'],
                   linewidth=merged_style['linewidth'],
                   alpha=merged_style['alpha'])
            
            self._log(f"线图渲染完成: {len(data)}个数据点", "DEBUG")
            return True
            
        except Exception as e:
            self._log(f"线图渲染失败: {str(e)}", "ERROR")
            return False
    
    def render_technical_indicators(self, ax: Axes, data: pd.DataFrame, 
                                  indicators: List[str], 
                                  style: Dict[str, Any] = None) -> bool:
        """
        技术指标渲染
        
        Args:
            ax: matplotlib轴对象
            data: 原始数据DataFrame
            indicators: 要渲染的技术指标列表
            style: 样式配置字典
            
        Returns:
            bool: 渲染成功返回True，失败返回False
        """
        try:
            if not self._validate_data(data):
                return False
            
            merged_style = self._get_merged_style('indicators', style)
            rendered_count = 0
            
            for indicator in indicators:
                try:
                    if indicator.lower() == 'ma':
                        # 移动平均线
                        if 'close' in data.columns:
                            ma20 = data['close'].rolling(window=20).mean()
                            ax.plot(ma20, color=merged_style['ma_color'], 
                                   linewidth=merged_style['linewidth'], alpha=merged_style['alpha'])
                            rendered_count += 1
                    
                    elif indicator.lower() == 'boll':
                        # 布林带
                        if 'close' in data.columns:
                            close = data['close']
                            ma = close.rolling(window=20).mean()
                            std = close.rolling(window=20).std()
                            upper = ma + 2 * std
                            lower = ma - 2 * std
                            
                            ax.plot(upper, color=merged_style['boll_color'], 
                                   linewidth=merged_style['linewidth'], alpha=merged_style['alpha'])
                            ax.plot(lower, color=merged_style['boll_color'], 
                                   linewidth=merged_style['linewidth'], alpha=merged_style['alpha'])
                            rendered_count += 1
                    
                    # TODO: 添加更多技术指标支持
                    
                except Exception as e:
                    self._log(f"渲染技术指标 {indicator} 失败: {str(e)}", "WARNING")
            
            self._log(f"技术指标渲染完成: {rendered_count}个指标", "DEBUG")
            return rendered_count > 0
            
        except Exception as e:
            self._log(f"技术指标渲染失败: {str(e)}", "ERROR")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        获取Matplotlib渲染器能力信息
        
        Returns:
            Dict[str, bool]: 能力标识字典
        """
        base_capabilities = super().get_capabilities()
        matplotlib_capabilities = {
            'webgpu_enabled': False,
            'hardware_acceleration': False,
            'progressive_rendering': False,
            'batch_processing': True,
            'vectorized_operations': True,
            'datetime_axis': True,
            'candlestick_rendering': True,
            'volume_rendering': True,
            'line_rendering': True,
            'technical_indicators': True,
            'matplotlib_compatibility': True
        }
        
        return {**base_capabilities, **matplotlib_capabilities}
    
    def get_renderer_info(self) -> Dict[str, Any]:
        """
        获取Matplotlib渲染器详细信息
        
        Returns:
            Dict[str, Any]: 渲染器信息字典
        """
        base_info = super().get_renderer_info()
        matplotlib_info = {
            'renderer_type': 'MatplotlibChartRenderer',
            'backend': 'matplotlib',
            'performance_optimizations': [
                'vectorized_numpy_operations',
                'polycollection_batch_rendering',
                'efficient_datetime_handling'
            ],
            'supported_chart_types': [
                'candlestick',
                'volume', 
                'line',
                'technical_indicators'
            ]
        }
        
        return {**base_info, **matplotlib_info}