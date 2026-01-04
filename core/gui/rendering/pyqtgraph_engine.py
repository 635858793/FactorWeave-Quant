#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyQtGraph渲染引擎
替代matplotlib的高性能实时图表渲染引擎

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFrame
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPen, QBrush
from loguru import logger

from ...events.event_bus import EventBus
from ...events.types import Event, EventType


class ChartType(Enum):
    """图表类型枚举"""
    LINE_CHART = "line_chart"
    CANDLESTICK = "candlestick"
    BAR_CHART = "bar_chart"
    SCATTER_PLOT = "scatter_plot"
    HEATMAP = "heatmap"
    PERFORMANCE_GRAPH = "performance_graph"
    REAL_TIME_CHART = "real_time_chart"
    VOLUME_CHART = "volume_chart"


@dataclass
class ChartConfig:
    """图表配置"""
    chart_type: ChartType
    width: int = 1000
    height: int = 600
    title: str = ""
    x_label: str = "时间"
    y_label: str = "价格"
    auto_range: bool = True
    real_time: bool = False
    update_interval: int = 1000  # 毫秒
    max_data_points: int = 10000
    theme: str = "dark"
    enable_grid: bool = True
    enable_legend: bool = True
    colors: List[str] = field(default_factory=lambda: ['#00BFFF', '#FF6347', '#32CD32', '#FFD700'])
    line_width: float = 2.0
    opacity: float = 1.0


class PyQtGraphChartWidget(QWidget):
    """PyQtGraph图表组件基类"""
    
    def __init__(self, config: ChartConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.data_buffer: List[Dict[str, Any]] = []
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_chart)
        
        self.setup_ui()
        self.setup_chart()
        
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建图表控件
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', self.config.y_label)
        self.plot_widget.setLabel('bottom', self.config.x_label)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)
        
    def setup_chart(self):
        """设置图表样式"""
        if self.config.theme == "dark":
            self.plot_widget.setBackground('#1e1e1e')
        else:
            self.plot_widget.setBackground('white')
            
    def update_chart(self):
        """更新图表数据 - 子类重写"""
        pass
        
    def start_real_time_updates(self):
        """启动实时更新"""
        if self.config.real_time:
            self.update_timer.start(self.config.update_interval)
            
    def stop_real_time_updates(self):
        """停止实时更新"""
        self.update_timer.stop()
        
    def add_data_point(self, data: Dict[str, Any]):
        """添加数据点"""
        self.data_buffer.append(data)
        
        # 控制缓冲区大小
        if len(self.data_buffer) > self.config.max_data_points:
            self.data_buffer = self.data_buffer[-self.config.max_data_points//2:]
            
    def clear_data(self):
        """清空数据"""
        self.data_buffer.clear()


class LineChartWidget(PyQtGraphChartWidget):
    """线图组件"""
    
    def __init__(self, config: ChartConfig, parent=None):
        self.line_plots = {}
        super().__init__(config, parent)
        
    def setup_chart(self):
        """设置线图样式"""
        super().setup_chart()
        
        # 设置初始线条
        colors = self.config.colors
        for i, color in enumerate(colors):
            pen = pg.mkPen(color, width=self.config.line_width)
            plot = self.plot_widget.plot(pen=pen, name=f"线{i+1}")
            self.line_plots[f"line_{i}"] = plot
            
    def update_chart(self):
        """更新线图数据"""
        try:
            if not self.data_buffer:
                return
                
            # 转换数据格式
            for data_point in self.data_buffer:
                for line_name, plot in self.line_plots.items():
                    if line_name in data_point:
                        x_data = []
                        y_data = []
                        
                        # 处理历史数据点
                        for point in self.data_buffer:
                            if line_name in point:
                                x_data.append(point.get('timestamp', 0))
                                y_data.append(point[line_name])
                                
                        if x_data and y_data:
                            plot.setData(x_data, y_data)
                            
            self.data_buffer.clear()  # 清空已处理的数据
            
        except Exception as e:
            logger.error(f"更新线图失败: {e}")


class CandlestickChartWidget(PyQtGraphChartWidget):
    """K线图组件"""
    
    def __init__(self, config: ChartConfig, parent=None):
        self.candlestick_data = None
        self.last_candle_time = None
        super().__init__(config, parent)
        
    def setup_chart(self):
        """设置K线图样式"""
        super().setup_chart()
        
        # 添加移动平均线
        self.ma_lines = {
            'ma5': self.plot_widget.plot(pen=pg.mkPen('#FFD700', width=1), name='MA5'),
            'ma10': self.plot_widget.plot(pen=pg.mkPen('#FF6347', width=1), name='MA10'),
            'ma20': self.plot_widget.plot(pen=pg.mkPen('#00BFFF', width=1), name='MA20')
        }
        
    def update_chart(self):
        """更新K线图数据"""
        try:
            if not self.data_buffer:
                return
                
            for data_point in self.data_buffer:
                if 'ohlc' in data_point:
                    self._update_candlestick(data_point['ohlc'])
                    self._update_indicators(data_point.get('indicators', {}))
                    
            self.data_buffer.clear()
            
        except Exception as e:
            logger.error(f"更新K线图失败: {e}")
            
    def _update_candlestick(self, ohlc_data):
        """更新K线数据"""
        # 这里实现K线绘制逻辑
        # 由于PyQtGraph没有内置的K线图，需要使用多条线组合实现
        pass
        
    def _update_indicators(self, indicators):
        """更新技术指标"""
        for ma_name, ma_line in self.ma_lines.items():
            if ma_name in indicators:
                data = indicators[ma_name]
                if isinstance(data, list) and len(data) >= 2:
                    x_data = [i for i in range(len(data))]
                    ma_line.setData(x_data, data)


class RealTimeChartWidget(PyQtGraphChartWidget):
    """实时图表组件"""
    
    def __init__(self, config: ChartConfig, parent=None):
        self.max_points = config.max_data_points
        self.x_data = []
        self.y_data = []
        super().__init__(config, parent)
        
    def setup_chart(self):
        """设置实时图表样式"""
        super().setup_chart()
        
        # 创建实时数据曲线
        self.curve = self.plot_widget.plot(pen=pg.mkPen('#00FF00', width=2))
        
        # 设置自动滚动
        self.plot_widget.setXRange(0, self.max_points, padding=0)
        
    def update_chart(self):
        """更新实时图表数据"""
        try:
            if not self.data_buffer:
                return
                
            for data_point in self.data_buffer:
                if 'value' in data_point:
                    timestamp = data_point.get('timestamp', datetime.now().timestamp())
                    value = data_point['value']
                    
                    self.x_data.append(timestamp)
                    self.y_data.append(value)
                    
                    # 控制数据点数量
                    if len(self.x_data) > self.max_points:
                        self.x_data = self.x_data[-self.max_points//2:]
                        self.y_data = self.y_data[-self.max_points//2:]
                        
            if self.x_data and self.y_data:
                self.curve.setData(self.x_data, self.y_data)
                
            self.data_buffer.clear()
            
        except Exception as e:
            logger.error(f"更新实时图表失败: {e}")


class PyQtGraphEngine:
    """PyQtGraph渲染引擎"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        self.charts: Dict[str, PyQtGraphChartWidget] = {}
        self.chart_configs: Dict[str, ChartConfig] = {}
        self.app = QApplication.instance()
        
        # 性能监控
        self.render_stats = {
            'total_renders': 0,
            'avg_render_time': 0.0,
            'error_count': 0,
            'last_render_time': datetime.now()
        }
        
        logger.info("PyQtGraph渲染引擎初始化完成")
        
    def create_chart(self, chart_id: str, config: ChartConfig) -> PyQtGraphChartWidget:
        """创建图表"""
        try:
            if config.chart_type == ChartType.LINE_CHART:
                chart = LineChartWidget(config)
            elif config.chart_type == ChartType.CANDLESTICK:
                chart = CandlestickChartWidget(config)
            elif config.chart_type == ChartType.REAL_TIME_CHART:
                chart = RealTimeChartWidget(config)
            else:
                # 默认使用线图
                chart = LineChartWidget(config)
                
            self.charts[chart_id] = chart
            self.chart_configs[chart_id] = config
            
            logger.info(f"创建图表成功: {chart_id}")
            return chart
            
        except Exception as e:
            logger.error(f"创建图表失败 {chart_id}: {e}")
            raise
            
    def update_chart_data(self, chart_id: str, data: Union[Dict[str, Any], List[Dict[str, Any]]]):
        """更新图表数据"""
        try:
            if chart_id not in self.charts:
                logger.warning(f"图表不存在: {chart_id}")
                return
                
            chart = self.charts[chart_id]
            config = self.chart_configs[chart_id]
            
            # 记录渲染开始时间
            start_time = datetime.now()
            
            # 添加数据
            if isinstance(data, dict):
                chart.add_data_point(data)
            elif isinstance(data, list):
                for item in data:
                    chart.add_data_point(item)
                    
            # 如果是实时图表，启动更新
            if config.real_time:
                chart.start_real_time_updates()
                
            # 更新性能统计
            render_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_render_stats(render_time)
            
            # 发送事件
            if self.event_bus:
                event = Event(
                    type=EventType.CHART_DATA_UPDATED,
                    data={
                        'chart_id': chart_id,
                        'data_points': len(data) if isinstance(data, list) else 1,
                        'render_time': render_time
                    }
                )
                self.event_bus.emit(event)
                
        except Exception as e:
            logger.error(f"更新图表数据失败 {chart_id}: {e}")
            self.render_stats['error_count'] += 1
            
    def remove_chart(self, chart_id: str):
        """移除图表"""
        try:
            if chart_id in self.charts:
                chart = self.charts[chart_id]
                chart.stop_real_time_updates()
                del self.charts[chart_id]
                del self.chart_configs[chart_id]
                logger.info(f"移除图表成功: {chart_id}")
                
        except Exception as e:
            logger.error(f"移除图表失败 {chart_id}: {e}")
            
    def get_chart(self, chart_id: str) -> Optional[PyQtGraphChartWidget]:
        """获取图表实例"""
        return self.charts.get(chart_id)
        
    def get_all_charts(self) -> Dict[str, PyQtGraphChartWidget]:
        """获取所有图表"""
        return self.charts.copy()
        
    def _update_render_stats(self, render_time: float):
        """更新渲染统计"""
        self.render_stats['total_renders'] += 1
        
        # 计算平均渲染时间
        total_time = (self.render_stats['avg_render_time'] * 
                     (self.render_stats['total_renders'] - 1) + render_time)
        self.render_stats['avg_render_time'] = total_time / self.render_stats['total_renders']
        self.render_stats['last_render_time'] = datetime.now()
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            **self.render_stats,
            'active_charts': len(self.charts),
            'chart_types': {cid: cfg.chart_type.value for cid, cfg in self.chart_configs.items()},
            'real_time_charts': sum(1 for cfg in self.chart_configs.values() if cfg.real_time)
        }
        
    def clear_all_charts(self):
        """清空所有图表"""
        try:
            for chart_id in list(self.charts.keys()):
                self.remove_chart(chart_id)
            logger.info("清空所有图表完成")
            
        except Exception as e:
            logger.error(f"清空图表失败: {e}")


# 全局引擎实例
_engine_instance = None

def get_pyqtgraph_engine(event_bus: Optional[EventBus] = None) -> PyQtGraphEngine:
    """获取PyQtGraph引擎实例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PyQtGraphEngine(event_bus)
    return _engine_instance

def reset_pyqtgraph_engine():
    """重置PyQtGraph引擎"""
    global _engine_instance
    if _engine_instance:
        _engine_instance.clear_all_charts()
        _engine_instance = None
    logger.info("PyQtGraph引擎已重置")


# 导出的公共接口
__all__ = [
    'PyQtGraphEngine',
    'PyQtGraphChartWidget',
    'LineChartWidget',
    'CandlestickChartWidget', 
    'RealTimeChartWidget',
    'ChartConfig',
    'ChartType',
    'get_pyqtgraph_engine',
    'reset_pyqtgraph_engine'
]