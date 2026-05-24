#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图表工厂

提供标准化的图表创建接口，支持配置驱动的图表生成

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from .pyqtgraph_engine import PyQtGraphEngine, ChartType, PyQtGraphChartWidget, ChartConfig
from .chart_manager import ChartManager
from .performance_optimizer import ChartPerformanceOptimizer, PerformanceConfig
from .matplotlib_adapter import MatplotlibAdapter, MatplotlibConfig
from .data_adapter import DataAdapter, DataSchema, DataFormat
from ...events.event_bus import EventBus


class ChartStyle(Enum):
    """图表样式枚举"""
    MODERN = "modern"
    CLASSIC = "classic"
    DARK = "dark"
    TRADING = "trading"
    PROFESSIONAL = "professional"
    MINIMAL = "minimal"


class ChartTheme(Enum):
    """图表主题枚举"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


@dataclass
class RendererConfig:
    """渲染器图表配置（区别于 pyqtgraph_engine.ChartConfig）"""
    # 基本配置
    chart_type: ChartType = ChartType.LINE_CHART
    width: int = 800
    height: int = 600
    title: str = ""
    
    # 样式配置
    style: ChartStyle = ChartStyle.MODERN
    theme: ChartTheme = ChartTheme.AUTO
    colors: List[str] = field(default_factory=lambda: ['#1f77b4', '#ff7f0e', '#2ca02c'])
    
    # 数据配置
    data_schema: str = "numerical"
    x_column: str = "x"
    y_column: str = "y"
    
    # 性能配置
    max_points: int = 5000
    enable_animation: bool = True
    real_time: bool = False
    
    # 交互配置
    interactive: bool = True
    zoomable: bool = True
    pannable: bool = True
    selectable: bool = True
    
    # 显示配置
    show_grid: bool = True
    show_legend: bool = True
    show_tooltip: bool = True
    show_crosshair: bool = True
    
    # 特殊配置
    financial: bool = False  # 金融图表专用
    real_time_buffer: int = 1000
    update_interval: int = 1000  # 毫秒


@dataclass
class ChartCreationRequest:
    """图表创建请求"""
    config: RendererConfig
    data: Optional[Union[pd.DataFrame, dict, list]] = None
    callbacks: Dict[str, callable] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChartFactory:
    """图表工厂"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        
        # 核心组件
        self.pyqtgraph_engine = None
        self.chart_manager = None
        self.performance_optimizer = None
        self.matplotlib_adapter = None
        self.data_adapter = None
        
        # 图表模板缓存
        self.chart_templates: Dict[str, RendererConfig] = {}
        
        # 统计信息
        self.creation_stats = {
            'total_created': 0,
            'by_type': {t.value: 0 for t in ChartType},
            'by_style': {s.value: 0 for s in ChartStyle},
            'average_creation_time': 0.0
        }
        
        logger.info("图表工厂初始化完成")
        
    def initialize(self, pyqtgraph_engine: PyQtGraphEngine, chart_manager: ChartManager,
                  performance_optimizer: ChartPerformanceOptimizer,
                  matplotlib_adapter: MatplotlibAdapter, data_adapter: DataAdapter):
        """初始化工厂组件"""
        try:
            self.pyqtgraph_engine = pyqtgraph_engine
            self.chart_manager = chart_manager
            self.performance_optimizer = performance_optimizer
            self.matplotlib_adapter = matplotlib_adapter
            self.data_adapter = data_adapter
            
            # 注册预定义图表模板
            self._register_default_templates()
            
            logger.info("图表工厂组件初始化完成")
            
        except Exception as e:
            logger.error(f"初始化图表工厂失败: {e}")
            
    def _register_default_templates(self):
        """注册预定义图表模板"""
        try:
            # 金融K线图模板
            kline_template = RendererConfig(
                chart_type=ChartType.CANDLESTICK,
                title="金融K线图",
                style=ChartStyle.TRADING,
                theme=ChartTheme.DARK,
                financial=True,
                show_grid=True,
                show_legend=True,
                data_schema="ohlcv",
                real_time=True
            )
            self.chart_templates["kline"] = kline_template
            
            # 性能监控图表模板
            performance_template = RendererConfig(
                chart_type=ChartType.LINE_CHART,
                title="性能监控",
                style=ChartStyle.PROFESSIONAL,
                theme=ChartTheme.AUTO,
                real_time=True,
                real_time_buffer=500,
                update_interval=500,
                show_grid=True,
                show_tooltip=True
            )
            self.chart_templates["performance"] = performance_template
            
            # 实时数据图表模板
            realtime_template = RendererConfig(
                chart_type=ChartType.LINE_CHART,
                title="实时数据",
                style=ChartStyle.MODERN,
                theme=ChartTheme.AUTO,
                real_time=True,
                interactive=True,
                show_grid=False,
                show_tooltip=True
            )
            self.chart_templates["realtime"] = realtime_template
            
            # 历史数据图表模板
            historical_template = RendererConfig(
                chart_type=ChartType.LINE_CHART,
                title="历史数据",
                style=ChartStyle.CLASSIC,
                theme=ChartTheme.LIGHT,
                interactive=True,
                zoomable=True,
                pannable=True,
                show_grid=True,
                show_legend=True
            )
            self.chart_templates["historical"] = historical_template
            
            logger.debug("预定义图表模板注册完成")
            
        except Exception as e:
            logger.error(f"注册图表模板失败: {e}")
            
    def create_chart(self, request: ChartCreationRequest) -> Optional[str]:
        """创建图表"""
        try:
            start_time = datetime.now()
            
            # 验证必要组件
            if not all([self.pyqtgraph_engine, self.chart_manager, self.data_adapter]):
                logger.error("图表工厂组件未初始化")
                return None
                
            config = request.config
            chart_id = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # 应用数据标准化
            if request.data is not None:
                normalized_data = self.data_adapter.normalize_data(request.data, config.data_schema)
                if normalized_data is None:
                    logger.error(f"数据标准化失败: {config.data_schema}")
                    return None
                chart_data = self.data_adapter.convert_chart_data(normalized_data, config.chart_type)
            else:
                chart_data = {}
                
            # 根据图表类型创建图表
            chart_widget = self._create_chart_widget(config, chart_data)
            if not chart_widget:
                logger.error(f"创建图表组件失败: {config.chart_type}")
                return None
                
            # 应用样式配置
            self._apply_chart_style(chart_widget, config)
            
            # 注册到图表管理器
            self.chart_manager.register_chart(chart_id, chart_widget, config)
            
            # 设置性能优化
            if self.performance_optimizer:
                chart_widget.setProperty('performance_config', {
                    'max_points': config.max_points,
                    'real_time': config.real_time,
                    'real_time_buffer': config.real_time_buffer
                })
                
            # 设置回调函数
            if request.callbacks:
                for event, callback in request.callbacks.items():
                    chart_widget.connect_callback(event, callback)
                    
            # 发送创建事件
            if self.event_bus:
                event = {
                    'type': 'chart_created',
                    'chart_id': chart_id,
                    'config': config.__dict__,
                    'creation_time': (datetime.now() - start_time).total_seconds()
                }
                
            # 更新统计信息
            creation_time = (datetime.now() - start_time).total_seconds()
            self._update_stats(chart_id, config, creation_time)
            
            logger.info(f"图表创建成功: {chart_id} ({creation_time:.3f}s)")
            return chart_id
            
        except Exception as e:
            logger.error(f"创建图表失败: {e}")
            return None
            
    def _create_chart_widget(self, config: RendererConfig, chart_data: Dict[str, Any]) -> Optional[PyQtGraphChartWidget]:
        """创建图表组件"""
        try:
            chart_id = f"widget_{datetime.now().strftime('%f')}"
            engine_config = ChartConfig(
                chart_type=config.chart_type,
                width=config.width,
                height=config.height,
                title=config.title,
                real_time=config.real_time,
                update_interval=config.update_interval,
                max_data_points=config.max_points,
                theme="dark" if config.theme == ChartTheme.DARK else "light",
                enable_grid=config.show_grid,
                enable_legend=config.show_legend,
            )
            chart_widget = self.pyqtgraph_engine.create_chart(chart_id, engine_config)
            if chart_data:
                chart_widget.set_data(chart_data)
            return chart_widget

        except Exception as e:
            logger.error(f"创建图表组件失败: {e}")
            return None
            
    def _apply_chart_style(self, chart_widget: PyQtGraphChartWidget, config: RendererConfig):
        """应用图表样式"""
        try:
            # 主题设置
            if config.theme == ChartTheme.DARK:
                chart_widget.set_dark_theme()
            elif config.theme == ChartTheme.LIGHT:
                chart_widget.set_light_theme()
            elif config.theme == ChartTheme.AUTO:
                # 自动检测系统主题
                try:
                    import os
                    is_dark = os.environ.get('QT_QPA_PLATFORM', '').lower() == 'wayland'
                    chart_widget.set_dark_theme() if is_dark else chart_widget.set_light_theme()
                except Exception:
                    chart_widget.set_light_theme()
                    
            # 样式设置
            if config.style == ChartStyle.TRADING:
                chart_widget.set_trading_style()
            elif config.style == ChartStyle.PROFESSIONAL:
                chart_widget.set_professional_style()
            elif config.style == ChartStyle.MINIMAL:
                chart_widget.set_minimal_style()
                
            # 显示选项
            chart_widget.show_grid(config.show_grid)
            chart_widget.show_legend(config.show_legend)
            chart_widget.show_tooltip(config.show_tooltip)
            chart_widget.show_crosshair(config.show_crosshair)
            
            # 交互选项
            chart_widget.set_interactive(config.interactive)
            chart_widget.set_zoomable(config.zoomable)
            chart_widget.set_pannable(config.pannable)
            chart_widget.set_selectable(config.selectable)
            
            # 动画设置
            if config.enable_animation:
                chart_widget.enable_animation()
                
        except Exception as e:
            logger.error(f"应用图表样式失败: {e}")
            
    def create_from_template(self, template_name: str, data: Optional[Union[pd.DataFrame, dict, list]] = None,
                           callbacks: Dict[str, callable] = None) -> Optional[str]:
        """从模板创建图表"""
        try:
            if template_name not in self.chart_templates:
                logger.error(f"未找到图表模板: {template_name}")
                return None
                
            template_config = self.chart_templates[template_name]
            
            # 如果提供了新数据，更新模板配置
            if data is not None and hasattr(data, 'shape'):
                # DataFrame数据，调整列配置
                if isinstance(data, pd.DataFrame):
                    if len(data.columns) >= 2:
                        template_config.x_column = data.columns[0]
                        template_config.y_column = data.columns[1]
                        
            request = ChartCreationRequest(
                config=template_config,
                data=data,
                callbacks=callbacks or {}
            )
            
            return self.create_chart(request)
            
        except Exception as e:
            logger.error(f"从模板创建图表失败: {e}")
            return None
            
    def create_kline_chart(self, ohlc_data: pd.DataFrame, title: str = "K线图") -> Optional[str]:
        """创建K线图快捷方法"""
        try:
            config = RendererConfig(
                chart_type=ChartType.CANDLESTICK,
                title=title,
                style=ChartStyle.TRADING,
                theme=ChartTheme.DARK,
                financial=True,
                data_schema="ohlcv",
                real_time=False
            )
            
            if 'volume' not in ohlc_data.columns:
                ohlc_data['volume'] = 0
                
            request = ChartCreationRequest(config=config, data=ohlc_data)
            return self.create_chart(request)
            
        except Exception as e:
            logger.error(f"创建K线图失败: {e}")
            return None
            
    def create_performance_chart(self, metric_data: pd.DataFrame, title: str = "性能监控") -> Optional[str]:
        """创建性能图表快捷方法"""
        try:
            template_name = "performance"
            if template_name in self.chart_templates:
                template_config = self.chart_templates[template_name]
                template_config.title = title
                
                request = ChartCreationRequest(config=template_config, data=metric_data)
                return self.create_chart(request)
            else:
                logger.error("性能图表模板不存在")
                return None
                
        except Exception as e:
            logger.error(f"创建性能图表失败: {e}")
            return None
            
    def create_realtime_chart(self, data_source: str, buffer_size: int = 1000) -> Optional[str]:
        """创建实时图表快捷方法"""
        try:
            template_name = "realtime"
            if template_name in self.chart_templates:
                template_config = self.chart_templates[template_name]
                template_config.real_time_buffer = buffer_size
                
                request = ChartCreationRequest(config=template_config)
                chart_id = self.create_chart(request)
                
                # 如果有数据源，设置数据流
                if chart_id and hasattr(self.chart_manager, 'start_data_stream'):
                    self.chart_manager.start_data_stream(chart_id, data_source, buffer_size)
                    
                return chart_id
            else:
                logger.error("实时图表模板不存在")
                return None
                
        except Exception as e:
            logger.error(f"创建实时图表失败: {e}")
            return None
            
    def clone_chart(self, source_chart_id: str, new_title: str = None) -> Optional[str]:
        """克隆图表"""
        try:
            source_chart = self.chart_manager.get_chart(source_chart_id)
            if not source_chart:
                logger.error(f"源图表不存在: {source_chart_id}")
                return None
                
            # 复制配置
            source_config = getattr(source_chart, 'config', None)
            if source_config:
                new_config = RendererConfig(
                    chart_type=source_config.chart_type,
                    width=source_config.width,
                    height=source_config.height,
                    title=new_title or f"{source_config.title} - 副本",
                    style=source_config.style,
                    theme=source_config.theme,
                    data_schema=source_config.data_schema
                )
                
                request = ChartCreationRequest(config=new_config)
                return self.create_chart(request)
            else:
                logger.error("源图表配置不存在")
                return None
                
        except Exception as e:
            logger.error(f"克隆图表失败: {e}")
            return None
            
    def register_template(self, name: str, config: RendererConfig):
        """注册自定义模板"""
        try:
            self.chart_templates[name] = config
            logger.info(f"注册图表模板: {name}")
            
        except Exception as e:
            logger.error(f"注册模板失败: {e}")
            
    def get_template_list(self) -> List[str]:
        """获取模板列表"""
        return list(self.chart_templates.keys())
        
    def get_template_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取模板信息"""
        if name in self.chart_templates:
            config = self.chart_templates[name]
            return {
                'name': name,
                'chart_type': config.chart_type.value,
                'title': config.title,
                'style': config.style.value,
                'theme': config.theme.value,
                'real_time': config.real_time,
                'financial': config.financial
            }
        return None
        
    def _update_stats(self, chart_id: str, config: RendererConfig, creation_time: float):
        """更新统计信息"""
        try:
            self.creation_stats['total_created'] += 1
            self.creation_stats['by_type'][config.chart_type.value] += 1
            self.creation_stats['by_style'][config.style.value] += 1
            
            # 更新平均创建时间
            current_avg = self.creation_stats['average_creation_time']
            total_charts = self.creation_stats['total_created']
            new_avg = (current_avg * (total_charts - 1) + creation_time) / total_charts
            self.creation_stats['average_creation_time'] = new_avg
            
        except Exception as e:
            logger.error(f"更新统计信息失败: {e}")
            
    def get_creation_stats(self) -> Dict[str, Any]:
        """获取创建统计信息"""
        return self.creation_stats.copy()
        
    def validate_config(self, config: RendererConfig) -> Tuple[bool, List[str]]:
        """验证图表配置"""
        errors = []

        # 基本配置验证
        if config.width <= 0 or config.height <= 0:
            errors.append("图表尺寸必须大于0")

        if config.max_points <= 0:
            errors.append("最大数据点必须大于0")

        # 数据配置验证
        if config.data_schema not in self.data_adapter.get_schema_list():
            errors.append(f"未知的数据模式: {config.data_schema}")

        # 图表类型验证
        if config.chart_type not in ChartType:
            errors.append(f"不支持的图表类型: {config.chart_type}")

        return len(errors) == 0, errors

    def cleanup_resources(self):
        """清理所有渲染资源（用于后端切换或应用退出）"""
        logger.info("开始清理渲染资源...")

        try:
            if self.chart_manager:
                self.chart_manager.clear_all_charts()
        except Exception as e:
            logger.error(f"清理图表管理器失败: {e}")

        try:
            if self.matplotlib_adapter:
                self.matplotlib_adapter.close_all()
        except Exception as e:
            logger.error(f"清理matplotlib适配器失败: {e}")

        try:
            if self.pyqtgraph_engine:
                self.pyqtgraph_engine.clear_all_charts()
        except Exception as e:
            logger.error(f"清理pyqtgraph引擎失败: {e}")

        logger.info("渲染资源清理完成")

    def switch_backend(self, target: str) -> bool:
        """切换渲染后端"""
        valid_backends = ('matplotlib', 'pyqtgraph')
        if target not in valid_backends:
            logger.error(f"不支持的后端: {target}，有效选项: {valid_backends}")
            return False

        logger.info(f"切换渲染后端: -> {target}")

        try:
            self.cleanup_resources()

            if target == 'matplotlib':
                if self.matplotlib_adapter is None:
                    logger.error("matplotlib适配器未初始化")
                    return False
                logger.info("已切换到matplotlib渲染后端")
            elif target == 'pyqtgraph':
                if self.pyqtgraph_engine is None:
                    logger.error("pyqtgraph引擎未初始化")
                    return False
                logger.info("已切换到pyqtgraph渲染后端")

            return True

        except Exception as e:
            logger.error(f"切换后端失败: {e}")
            return False


# 导出的公共接口
__all__ = [
    'ChartFactory',
    'RendererConfig',
    'ChartCreationRequest',
    'ChartStyle',
    'ChartTheme'
]