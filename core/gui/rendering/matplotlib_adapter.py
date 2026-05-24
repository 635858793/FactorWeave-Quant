#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
matplotlib适配器

为平滑迁移到PyQtGraph提供matplotlib兼容性接口

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import warnings
from loguru import logger

try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib未安装，将使用PyQtGraph作为唯一依赖")

from .pyqtgraph_engine import PyQtGraphEngine, ChartType
from ...events.event_bus import EventBus


class MatplotlibStyle(Enum):
    """matplotlib样式枚举"""
    DEFAULT = "default"
    DARK = "dark"
    TRADING = "trading"
    PROFESSIONAL = "professional"
    MINIMAL = "minimal"


@dataclass
class MatplotlibConfig:
    """matplotlib配置"""
    style: MatplotlibStyle = MatplotlibStyle.DEFAULT
    figure_size: Tuple[int, int] = (12, 8)
    dpi: int = 100
    font_size: int = 10
    line_width: float = 1.5
    color_scheme: str = "default"
    grid_enabled: bool = True
    legend_enabled: bool = True
    theme: str = "light"


class StyleManager:
    """样式管理器"""
    
    # 预定义样式
    STYLES = {
        MatplotlibStyle.DEFAULT: {
            'font.size': 10,
            'axes.titlesize': 12,
            'axes.labelsize': 10,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 9,
            'figure.titlesize': 14,
            'lines.linewidth': 1.5,
            'axes.grid': True,
            'grid.alpha': 0.3
        },
        
        MatplotlibStyle.DARK: {
            'font.size': 10,
            'axes.titlesize': 12,
            'axes.labelsize': 10,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 9,
            'figure.titlesize': 14,
            'lines.linewidth': 1.5,
            'axes.grid': True,
            'grid.alpha': 0.3,
            'axes.facecolor': '#2E2E2E',
            'figure.facecolor': '#2E2E2E',
            'axes.edgecolor': '#FFFFFF',
            'axes.textcolor': '#FFFFFF',
            'xtick.color': '#FFFFFF',
            'ytick.color': '#FFFFFF'
        },
        
        MatplotlibStyle.TRADING: {
            'font.size': 9,
            'axes.titlesize': 11,
            'axes.labelsize': 9,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 8,
            'figure.titlesize': 12,
            'lines.linewidth': 1.0,
            'axes.grid': True,
            'grid.alpha': 0.2,
            'axes.linewidth': 0.8,
            'axes.spines.top': False,
            'axes.spines.right': False
        },
        
        MatplotlibStyle.PROFESSIONAL: {
            'font.size': 10,
            'axes.titlesize': 13,
            'axes.labelsize': 11,
            'xtick.labelsize': 9,
            'ytick.labelsize': 9,
            'legend.fontsize': 10,
            'figure.titlesize': 15,
            'lines.linewidth': 2.0,
            'axes.grid': True,
            'grid.alpha': 0.4,
            'axes.linewidth': 1.2,
            'legend.frameon': True,
            'legend.fancybox': True
        },
        
        MatplotlibStyle.MINIMAL: {
            'font.size': 11,
            'axes.titlesize': 13,
            'axes.labelsize': 11,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.titlesize': 15,
            'lines.linewidth': 2.0,
            'axes.grid': False,
            'axes.spines.top': False,
            'axes.spines.right': False,
            'axes.spines.left': True,
            'axes.spines.bottom': True
        }
    }
    
    @classmethod
    def apply_style(cls, style: MatplotlibStyle, config: MatplotlibConfig):
        """应用样式"""
        if not HAS_MATPLOTLIB:
            return
            
        try:
            # 重置matplotlib参数
            matplotlib.rc_file_defaults()
            
            # 获取样式配置
            style_config = cls.STYLES.get(style, cls.STYLES[MatplotlibStyle.DEFAULT])
            
            # 应用样式
            matplotlib.rc(style_config)
            
            # 应用自定义配置
            if config.figsize:
                matplotlib.rcParams['figure.figsize'] = config.figure_size
            if config.dpi != 100:
                matplotlib.rcParams['figure.dpi'] = config.dpi
            if config.grid_enabled:
                matplotlib.rcParams['axes.grid'] = True
                matplotlib.rcParams['grid.alpha'] = 0.3
            else:
                matplotlib.rcParams['axes.grid'] = False
                
            logger.debug(f"应用matplotlib样式: {style.value}")
            
        except Exception as e:
            logger.error(f"应用matplotlib样式失败: {e}")


class MatplotlibFigure:
    """matplotlib图形封装"""
    
    def __init__(self, config: MatplotlibConfig, style_manager: StyleManager):
        self.config = config
        self.style_manager = style_manager
        self.figure = None
        self.axes = None
        
        if HAS_MATPLOTLIB:
            self._create_figure()
        
    def _create_figure(self):
        """创建图形"""
        try:
            # 应用样式
            self.style_manager.apply_style(self.config.style, self.config)
            
            # 创建图形
            self.figure = plt.figure(
                figsize=self.config.figure_size,
                dpi=self.config.dpi
            )
            
            # 创建子图
            self.axes = self.figure.add_subplot(111)
            
            logger.debug("matplotlib图形创建成功")
            
        except Exception as e:
            logger.error(f"创建matplotlib图形失败: {e}")
            
    def plot_line(self, x_data, y_data, label: str = "", color: str = "blue", 
                  linewidth: float = 1.5, linestyle: str = "-", **kwargs):
        """绘制线图"""
        try:
            if not self.axes:
                logger.warning("matplotlib图形未初始化")
                return
                
            self.axes.plot(x_data, y_data, label=label, color=color, 
                          linewidth=linewidth, linestyle=linestyle, **kwargs)
                          
        except Exception as e:
            logger.error(f"绘制线图失败: {e}")
            
    def plot_scatter(self, x_data, y_data, label: str = "", color: str = "red", 
                    s: int = 20, alpha: float = 0.7, **kwargs):
        """绘制散点图"""
        try:
            if not self.axes:
                logger.warning("matplotlib图形未初始化")
                return
                
            self.axes.scatter(x_data, y_data, label=label, color=color, 
                            s=s, alpha=alpha, **kwargs)
                            
        except Exception as e:
            logger.error(f"绘制散点图失败: {e}")
            
    def plot_bar(self, x_data, height, label: str = "", color: str = "green", 
                alpha: float = 0.7, **kwargs):
        """绘制柱状图"""
        try:
            if not self.axes:
                logger.warning("matplotlib图形未初始化")
                return
                
            self.axes.bar(x_data, height, label=label, color=color, 
                         alpha=alpha, **kwargs)
                         
        except Exception as e:
            logger.error(f"绘制柱状图失败: {e}")
            
    def plot_candlestick(self, ohlc_data, label: str = ""):
        """绘制K线图（向量化批量渲染）"""
        try:
            if not self.axes:
                logger.warning("matplotlib图形未初始化")
                return

            if isinstance(ohlc_data, pd.DataFrame):
                if not all(col in ohlc_data.columns for col in ['open', 'high', 'low', 'close']):
                    raise ValueError("OHLC数据缺少必要字段")

                df = ohlc_data.reset_index(drop=True)
                open_arr = df['open'].values
                close_arr = df['close'].values
                n = len(df)
                x_indices = np.arange(n)
                body_width = 0.6

                is_up = close_arr >= open_arr
                up_mask = is_up
                down_mask = ~is_up

                self.axes.vlines(x_indices[up_mask],
                               df['low'].values[up_mask],
                               df['high'].values[up_mask],
                               color='red', linewidth=0.8)
                self.axes.vlines(x_indices[down_mask],
                               df['low'].values[down_mask],
                               df['high'].values[down_mask],
                               color='green', linewidth=0.8)

                if up_mask.any():
                    self.axes.bar(x_indices[up_mask],
                                  close_arr[up_mask] - open_arr[up_mask],
                                  body_width, bottom=open_arr[up_mask],
                                  color='red', edgecolor='red', linewidth=0.5)

                if down_mask.any():
                    self.axes.bar(x_indices[down_mask],
                                  open_arr[down_mask] - close_arr[down_mask],
                                  body_width, bottom=close_arr[down_mask],
                                  color='green', edgecolor='green', linewidth=0.5)

            logger.debug("matplotlib K线图批量绘制完成")

        except Exception as e:
            logger.error(f"绘制matplotlib K线图失败: {e}")
            
    def set_title(self, title: str, fontsize: int = None):
        """设置标题"""
        try:
            if self.axes:
                fontsize = fontsize or self.config.font_size + 2
                self.axes.set_title(title, fontsize=fontsize)
                
        except Exception as e:
            logger.error(f"设置标题失败: {e}")
            
    def set_xlabel(self, label: str, fontsize: int = None):
        """设置x轴标签"""
        try:
            if self.axes:
                fontsize = fontsize or self.config.font_size
                self.axes.set_xlabel(label, fontsize=fontsize)
                
        except Exception as e:
            logger.error(f"设置x轴标签失败: {e}")
            
    def set_ylabel(self, label: str, fontsize: int = None):
        """设置y轴标签"""
        try:
            if self.axes:
                fontsize = fontsize or self.config.font_size
                self.axes.set_ylabel(label, fontsize=fontsize)
                
        except Exception as e:
            logger.error(f"设置y轴标签失败: {e}")
            
    def set_ylim(self, ymin: float, ymax: float):
        """设置y轴范围"""
        try:
            if self.axes:
                self.axes.set_ylim(ymin, ymax)
                
        except Exception as e:
            logger.error(f"设置y轴范围失败: {e}")
            
    def set_xlim(self, xmin: float, xmax: float):
        """设置x轴范围"""
        try:
            if self.axes:
                self.axes.set_xlim(xmin, xmax)
                
        except Exception as e:
            logger.error(f"设置x轴范围失败: {e}")
            
    def legend(self, loc: str = 'best'):
        """显示图例"""
        try:
            if self.axes and self.config.legend_enabled:
                self.axes.legend(loc=loc)
                
        except Exception as e:
            logger.error(f"显示图例失败: {e}")
            
    def grid(self, enabled: bool = True, alpha: float = 0.3):
        """显示网格"""
        try:
            if self.axes:
                self.axes.grid(enabled, alpha=alpha)
                
        except Exception as e:
            logger.error(f"显示网格失败: {e}")
            
    def tight_layout(self):
        """调整布局"""
        try:
            if self.figure:
                self.figure.tight_layout()
                
        except Exception as e:
            logger.error(f"调整布局失败: {e}")
            
    def save_fig(self, filepath: str, dpi: int = None, format: str = 'png'):
        """保存图形"""
        try:
            if self.figure and filepath:
                dpi = dpi or self.config.dpi
                self.figure.savefig(filepath, dpi=dpi, format=format)
                logger.debug(f"图形保存成功: {filepath}")
                
        except Exception as e:
            logger.error(f"保存图形失败: {e}")
            
    def close(self):
        """关闭图形"""
        try:
            if self.figure:
                plt.close(self.figure)
                
        except Exception as e:
            logger.error(f"关闭图形失败: {e}")


class MatplotlibAdapter:
    """matplotlib适配器"""
    
    def __init__(self, engine: PyQtGraphEngine, event_bus: Optional[EventBus] = None):
        self.engine = engine
        self.event_bus = event_bus
        
        # 配置和样式管理
        self.config = MatplotlibConfig()
        self.style_manager = StyleManager()
        
        # 图形管理器
        self.figures: Dict[str, MatplotlibFigure] = {}
        
        # 兼容性映射
        self.chart_type_mapping = {
            'line': ChartType.LINE_CHART,
            'bar': ChartType.BAR,
            'scatter': ChartType.SCATTER,
            'hist': ChartType.HISTOGRAM,
            'candlestick': ChartType.CANDLESTICK,
            'heatmap': ChartType.HEATMAP,
            'pie': ChartType.PIE,
            'box': ChartType.BOX
        }
        
        logger.info("matplotlib适配器初始化完成")
        
    def create_figure(self, figure_id: str, width: int = 800, height: int = 600) -> Optional[MatplotlibFigure]:
        """创建图形"""
        try:
            if figure_id in self.figures:
                return self.figures[figure_id]
                
            # 创建PyQtGraph图表
            chart_widget = self.engine.create_chart(ChartType.LINE_CHART, width, height)
            
            # 创建matplotlib图形
            matplotlib_figure = MatplotlibFigure(self.config, self.style_manager)
            self.figures[figure_id] = matplotlib_figure
            
            logger.debug(f"创建图形成功: {figure_id}")
            return matplotlib_figure
            
        except Exception as e:
            logger.error(f"创建图形失败 {figure_id}: {e}")
            return None
            
    def plot(self, figure_id: str, chart_type: str, data: Any, **kwargs):
        """通用绘图接口"""
        try:
            # 检查图形是否存在
            if figure_id not in self.figures:
                self.create_figure(figure_id)
                
            # 获取图表类型
            pyqt_graph_type = self.chart_type_mapping.get(chart_type, ChartType.LINE_CHART)
            
            # 根据数据类型处理
            if isinstance(data, pd.DataFrame):
                self._plot_dataframe(figure_id, pyqt_graph_type, data, **kwargs)
            elif isinstance(data, (list, np.ndarray)):
                self._plot_array(figure_id, pyqt_graph_type, data, **kwargs)
            else:
                logger.warning(f"不支持的数据类型: {type(data)}")
                
        except Exception as e:
            logger.error(f"绘图失败 {figure_id}: {e}")
            
    def _plot_dataframe(self, figure_id: str, chart_type: ChartType, df: pd.DataFrame, **kwargs):
        """绘制DataFrame数据"""
        try:
            if figure_id not in self.figures:
                return
                
            matplotlib_figure = self.figures[figure_id]
            
            if chart_type == ChartType.LINE_CHART:
                # 线图：使用第一列作为x轴，其他列作为y轴
                x_col = df.columns[0]
                for y_col in df.columns[1:]:
                    matplotlib_figure.plot_line(df[x_col], df[y_col], label=y_col, **kwargs)
                    
            elif chart_type == ChartType.SCATTER:
                # 散点图：使用前两列
                x_col, y_col = df.columns[0], df.columns[1]
                matplotlib_figure.plot_scatter(df[x_col], df[y_col], **kwargs)
                
            elif chart_type == ChartType.CANDLESTICK:
                # K线图：需要OHLC格式
                if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
                    matplotlib_figure.plot_candlestick(df, **kwargs)
                else:
                    logger.warning("K线图需要OHLC数据格式")
                    
            elif chart_type == ChartType.HISTOGRAM:
                # 直方图：使用数值列
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                for col in numeric_cols:
                    matplotlib_figure.plot_bar(range(len(df)), df[col], label=col, **kwargs)
                    
            else:
                logger.warning(f"不支持的图表类型: {chart_type}")
                
        except Exception as e:
            logger.error(f"绘制DataFrame失败: {e}")
            
    def _plot_array(self, figure_id: str, chart_type: ChartType, data: Union[List, np.ndarray], **kwargs):
        """绘制数组数据"""
        try:
            if figure_id not in self.figures:
                return
                
            matplotlib_figure = self.figures[figure_id]
            
            # 转换为numpy数组
            if isinstance(data, list):
                data = np.array(data)
                
            if chart_type == ChartType.LINE_CHART:
                # 线图：使用索引作为x轴
                x_data = range(len(data))
                matplotlib_figure.plot_line(x_data, data, **kwargs)
                
            elif chart_type == ChartType.SCATTER:
                # 散点图：生成x坐标
                x_data = range(len(data))
                matplotlib_figure.plot_scatter(x_data, data, **kwargs)
                
            elif chart_type == ChartType.BAR:
                # 柱状图：使用索引作为x坐标
                x_data = range(len(data))
                matplotlib_figure.plot_bar(x_data, data, **kwargs)
                
            elif chart_type == ChartType.HISTOGRAM:
                # 直方图：使用数据直方图
                matplotlib_figure.plot_bar(range(len(data)), data, **kwargs)
                
            else:
                logger.warning(f"不支持的图表类型: {chart_type}")
                
        except Exception as e:
            logger.error(f"绘制数组失败: {e}")
            
    def set_style(self, style: MatplotlibStyle):
        """设置样式"""
        try:
            self.config.style = style
            logger.info(f"设置matplotlib样式: {style.value}")
            
        except Exception as e:
            logger.error(f"设置样式失败: {e}")
            
    def set_config(self, config: MatplotlibConfig):
        """设置配置"""
        try:
            self.config = config
            logger.debug("更新matplotlib配置")
            
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
            
    def update_figure(self, figure_id: str, data: Any, **kwargs):
        """更新图形数据"""
        try:
            if figure_id in self.figures:
                # 清除旧数据，重新绘制
                matplotlib_figure = self.figures[figure_id]
                if matplotlib_figure.axes:
                    matplotlib_figure.axes.clear()
                    # 重新绘制
                    self.plot(figure_id, 'line', data, **kwargs)
                    
        except Exception as e:
            logger.error(f"更新图形失败 {figure_id}: {e}")
            
    def save_figure(self, figure_id: str, filepath: str, format: str = 'png', dpi: int = None):
        """保存图形"""
        try:
            if figure_id in self.figures:
                self.figures[figure_id].save_fig(filepath, dpi, format)
                
        except Exception as e:
            logger.error(f"保存图形失败 {figure_id}: {e}")
            
    def close_figure(self, figure_id: str):
        """关闭图形"""
        try:
            if figure_id in self.figures:
                self.figures[figure_id].close()
                del self.figures[figure_id]
                logger.debug(f"关闭图形: {figure_id}")
                
        except Exception as e:
            logger.error(f"关闭图形失败 {figure_id}: {e}")
            
    def close_all(self):
        """关闭所有图形"""
        errors = []
        for figure_id in list(self.figures.keys()):
            try:
                self.close_figure(figure_id)
            except Exception as e:
                errors.append((figure_id, str(e)))
                logger.error(f"关闭图形失败 {figure_id}: {e}")

        if errors:
            logger.warning(f"关闭所有图形完成，{len(errors)}个失败: {errors}")
        else:
            logger.info("关闭所有matplotlib图形")
            
    def get_figure_info(self, figure_id: str) -> Optional[Dict[str, Any]]:
        """获取图形信息"""
        try:
            if figure_id in self.figures:
                matplotlib_figure = self.figures[figure_id]
                return {
                    'id': figure_id,
                    'style': self.config.style.value,
                    'config': {
                        'figure_size': self.config.figure_size,
                        'dpi': self.config.dpi,
                        'font_size': self.config.font_size
                    },
                    'has_axes': matplotlib_figure.axes is not None
                }
                
            return None
            
        except Exception as e:
            logger.error(f"获取图形信息失败 {figure_id}: {e}")
            return None
            
    def migrate_from_matplotlib(self, pyplot_figure, target_figure_id: str):
        """从matplotlib.pyplot图形迁移"""
        try:
            if not HAS_MATPLOTLIB:
                logger.warning("matplotlib未安装，无法执行迁移")
                return
                
            # 创建新的图形
            new_figure = self.create_figure(target_figure_id)
            if not new_figure:
                return
                
            # 复制配置
            if pyplot_figure:
                # 复制样式配置
                new_figure.set_title(pyplot_figure.axes.get_title() if pyplot_figure.axes else "Migration Chart")
                new_figure.set_xlabel(pyplot_figure.axes.get_xlabel() if pyplot_figure.axes else "")
                new_figure.set_ylabel(pyplot_figure.axes.get_ylabel() if pyplot_figure.axes else "")
                
            logger.info(f"从matplotlib成功迁移图形: {target_figure_id}")
            
        except Exception as e:
            logger.error(f"迁移matplotlib图形失败: {e}")


# 导出的公共接口
__all__ = [
    'MatplotlibAdapter',
    'MatplotlibFigure',
    'MatplotlibConfig',
    'MatplotlibStyle',
    'StyleManager'
]