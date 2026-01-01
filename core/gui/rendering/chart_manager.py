#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图表管理器

统一管理所有图表组件，提供便捷的图表创建、更新、删除操作

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import uuid
from loguru import logger

from .pyqtgraph_engine import (
    PyQtGraphEngine, ChartConfig, ChartType, get_pyqtgraph_engine
)
from ...containers.service_container import get_service_container
from ...events.event_bus import EventBus
from ...events.types import Event, EventType


@dataclass
class ChartInfo:
    """图表信息"""
    chart_id: str
    chart_type: ChartType
    title: str
    created_at: datetime
    last_updated: datetime
    data_points: int = 0
    is_active: bool = True
    config: Optional[ChartConfig] = None


class ChartManager:
    """图表管理器 - 统一管理所有图表组件"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        self.engine = get_pyqtgraph_engine(event_bus)
        
        # 图表信息存储
        self.chart_registry: Dict[str, ChartInfo] = {}
        self.chart_callbacks: Dict[str, List[Callable]] = {}
        
        # 性能统计
        self.stats = {
            'total_charts_created': 0,
            'active_charts': 0,
            'total_data_updates': 0,
            'avg_creation_time': 0.0,
            'errors': 0
        }
        
        logger.info("图表管理器初始化完成")
        
    def create_line_chart(self, 
                         title: str,
                         width: int = 1000,
                         height: int = 600,
                         colors: Optional[List[str]] = None,
                         real_time: bool = False,
                         update_interval: int = 1000,
                         **kwargs) -> str:
        """创建线图"""
        try:
            start_time = datetime.now()
            
            # 生成唯一图表ID
            chart_id = str(uuid.uuid4())[:8]
            
            # 设置默认颜色
            if colors is None:
                colors = ['#00BFFF', '#FF6347', '#32CD32', '#FFD700', '#9370DB']
                
            # 创建图表配置
            config = ChartConfig(
                chart_type=ChartType.LINE_CHART,
                width=width,
                height=height,
                title=title,
                colors=colors,
                real_time=real_time,
                update_interval=update_interval,
                **kwargs
            )
            
            # 创建图表
            chart = self.engine.create_chart(chart_id, config)
            
            # 注册图表信息
            chart_info = ChartInfo(
                chart_id=chart_id,
                chart_type=ChartType.LINE_CHART,
                title=title,
                created_at=datetime.now(),
                last_updated=datetime.now(),
                config=config
            )
            
            self.chart_registry[chart_id] = chart_info
            self.stats['total_charts_created'] += 1
            self.stats['active_charts'] += 1
            
            # 计算创建时间
            creation_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_avg_creation_time(creation_time)
            
            # 发送事件
            self._emit_chart_event(
                EventType.CHART_CREATED,
                {
                    'chart_id': chart_id,
                    'chart_type': 'line_chart',
                    'title': title,
                    'creation_time': creation_time
                }
            )
            
            logger.info(f"线图创建成功: {chart_id} - {title}")
            return chart_id
            
        except Exception as e:
            logger.error(f"创建线图失败: {e}")
            self.stats['errors'] += 1
            raise
            
    def create_candlestick_chart(self,
                                title: str = "K线图",
                                width: int = 1000,
                                height: int = 600,
                                real_time: bool = False,
                                update_interval: int = 1000,
                                **kwargs) -> str:
        """创建K线图"""
        try:
            start_time = datetime.now()
            
            chart_id = str(uuid.uuid4())[:8]
            
            config = ChartConfig(
                chart_type=ChartType.CANDLESTICK,
                width=width,
                height=height,
                title=title,
                real_time=real_time,
                update_interval=update_interval,
                x_label="时间",
                y_label="价格",
                **kwargs
            )
            
            chart = self.engine.create_chart(chart_id, config)
            
            chart_info = ChartInfo(
                chart_id=chart_id,
                chart_type=ChartType.CANDLESTICK,
                title=title,
                created_at=datetime.now(),
                last_updated=datetime.now(),
                config=config
            )
            
            self.chart_registry[chart_id] = chart_info
            self.stats['total_charts_created'] += 1
            self.stats['active_charts'] += 1
            
            creation_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_avg_creation_time(creation_time)
            
            self._emit_chart_event(
                EventType.CHART_CREATED,
                {
                    'chart_id': chart_id,
                    'chart_type': 'candlestick_chart',
                    'title': title,
                    'creation_time': creation_time
                }
            )
            
            logger.info(f"K线图创建成功: {chart_id} - {title}")
            return chart_id
            
        except Exception as e:
            logger.error(f"创建K线图失败: {e}")
            self.stats['errors'] += 1
            raise
            
    def create_performance_chart(self,
                                title: str = "性能监控",
                                metrics: Optional[List[str]] = None,
                                width: int = 800,
                                height: int = 400,
                                **kwargs) -> str:
        """创建性能监控图表"""
        try:
            if metrics is None:
                metrics = ['cpu_usage', 'memory_usage', 'disk_usage', 'network_io']
                
            start_time = datetime.now()
            
            chart_id = str(uuid.uuid4())[:8]
            
            config = ChartConfig(
                chart_type=ChartType.PERFORMANCE_GRAPH,
                width=width,
                height=height,
                title=title,
                colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'],
                max_data_points=100,
                **kwargs
            )
            
            chart = self.engine.create_chart(chart_id, config)
            
            chart_info = ChartInfo(
                chart_id=chart_id,
                chart_type=ChartType.PERFORMANCE_GRAPH,
                title=title,
                created_at=datetime.now(),
                last_updated=datetime.now(),
                config=config
            )
            
            self.chart_registry[chart_id] = chart_info
            self.stats['total_charts_created'] += 1
            self.stats['active_charts'] += 1
            
            creation_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_avg_creation_time(creation_time)
            
            self._emit_chart_event(
                EventType.CHART_CREATED,
                {
                    'chart_id': chart_id,
                    'chart_type': 'performance_chart',
                    'title': title,
                    'metrics': metrics,
                    'creation_time': creation_time
                }
            )
            
            logger.info(f"性能图表创建成功: {chart_id} - {title}")
            return chart_id
            
        except Exception as e:
            logger.error(f"创建性能图表失败: {e}")
            self.stats['errors'] += 1
            raise
            
    def update_line_chart_data(self, 
                              chart_id: str, 
                              data: Union[Dict[str, Any], List[Dict[str, Any]]],
                              lines: Optional[List[str]] = None):
        """更新线图数据"""
        try:
            if chart_id not in self.chart_registry:
                raise ValueError(f"图表不存在: {chart_id}")
                
            chart_info = self.chart_registry[chart_id]
            if chart_info.chart_type != ChartType.LINE_CHART:
                raise ValueError(f"图表类型不匹配: {chart_id}")
                
            # 处理数据格式
            processed_data = self._process_line_data(data, lines)
            
            # 更新图表数据
            self.engine.update_chart_data(chart_id, processed_data)
            
            # 更新统计信息
            chart_info.last_updated = datetime.now()
            chart_info.data_points += len(processed_data) if isinstance(processed_data, list) else 1
            self.stats['total_data_updates'] += 1
            
            # 执行回调
            self._execute_callbacks(chart_id, 'data_updated', processed_data)
            
            logger.debug(f"线图数据更新成功: {chart_id}")
            
        except Exception as e:
            logger.error(f"更新线图数据失败 {chart_id}: {e}")
            self.stats['errors'] += 1
            
    def update_candlestick_data(self, 
                               chart_id: str, 
                               ohlc_data: Union[Dict[str, Any], List[Dict[str, Any]]],
                               indicators: Optional[Dict[str, Any]] = None):
        """更新K线图数据"""
        try:
            if chart_id not in self.chart_registry:
                raise ValueError(f"图表不存在: {chart_id}")
                
            chart_info = self.chart_registry[chart_id]
            if chart_info.chart_type != ChartType.CANDLESTICK:
                raise ValueError(f"图表类型不匹配: {chart_id}")
                
            # 处理OHLC数据
            processed_data = self._process_ohlc_data(ohlc_data)
            
            # 添加技术指标
            if indicators:
                processed_data['indicators'] = indicators
                
            # 更新图表数据
            self.engine.update_chart_data(chart_id, processed_data)
            
            # 更新统计信息
            chart_info.last_updated = datetime.now()
            chart_info.data_points += 1
            self.stats['total_data_updates'] += 1
            
            # 执行回调
            self._execute_callbacks(chart_id, 'data_updated', processed_data)
            
            logger.debug(f"K线图数据更新成功: {chart_id}")
            
        except Exception as e:
            logger.error(f"更新K线图数据失败 {chart_id}: {e}")
            self.stats['errors'] += 1
            
    def add_callback(self, chart_id: str, callback: Callable, event_type: str = 'data_updated'):
        """添加图表回调函数"""
        try:
            if chart_id not in self.chart_callbacks:
                self.chart_callbacks[chart_id] = []
                
            self.chart_callbacks[chart_id].append({
                'callback': callback,
                'event_type': event_type
            })
            
            logger.debug(f"添加图表回调成功: {chart_id}")
            
        except Exception as e:
            logger.error(f"添加图表回调失败 {chart_id}: {e}")
            
    def remove_chart(self, chart_id: str) -> bool:
        """移除图表"""
        try:
            if chart_id not in self.chart_registry:
                logger.warning(f"图表不存在: {chart_id}")
                return False
                
            # 停止实时更新
            chart = self.engine.get_chart(chart_id)
            if chart:
                chart.stop_real_time_updates()
                
            # 移除引擎中的图表
            self.engine.remove_chart(chart_id)
            
            # 清理注册信息
            del self.chart_registry[chart_id]
            if chart_id in self.chart_callbacks:
                del self.chart_callbacks[chart_id]
                
            self.stats['active_charts'] -= 1
            
            # 发送事件
            self._emit_chart_event(
                EventType.CHART_REMOVED,
                {'chart_id': chart_id}
            )
            
            logger.info(f"移除图表成功: {chart_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除图表失败 {chart_id}: {e}")
            self.stats['errors'] += 1
            return False
            
    def get_chart_info(self, chart_id: str) -> Optional[ChartInfo]:
        """获取图表信息"""
        return self.chart_registry.get(chart_id)
        
    def get_all_chart_ids(self) -> List[str]:
        """获取所有图表ID"""
        return list(self.chart_registry.keys())
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            **self.stats,
            'chart_types': {
                chart_id: info.chart_type.value 
                for chart_id, info in self.chart_registry.items()
            },
            'real_time_charts': sum(
                1 for info in self.chart_registry.values() 
                if info.config and info.config.real_time
            )
        }
        
    def clear_all_charts(self):
        """清空所有图表"""
        try:
            chart_ids = list(self.chart_registry.keys())
            for chart_id in chart_ids:
                self.remove_chart(chart_id)
                
            logger.info("清空所有图表完成")
            
        except Exception as e:
            logger.error(f"清空图表失败: {e}")
            
    def _process_line_data(self, data: Union[Dict[str, Any], List[Dict[str, Any]]], lines: Optional[List[str]]) -> List[Dict[str, Any]]:
        """处理线图数据"""
        if isinstance(data, dict):
            data = [data]
            
        processed_data = []
        for item in data:
            processed_item = item.copy()
            
            # 确保包含时间戳
            if 'timestamp' not in processed_item:
                processed_item['timestamp'] = datetime.now().timestamp()
                
            # 如果指定了线条，只保留相关数据
            if lines:
                filtered_item = {'timestamp': processed_item['timestamp']}
                for line_name in lines:
                    if line_name in processed_item:
                        filtered_item[line_name] = processed_item[line_name]
                processed_item = filtered_item
                
            processed_data.append(processed_item)
            
        return processed_data
        
    def _process_ohlc_data(self, ohlc_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
        """处理OHLC数据"""
        if isinstance(ohlc_data, list):
            # 取最新的K线数据
            latest_data = ohlc_data[-1] if ohlc_data else {}
        else:
            latest_data = ohlc_data
            
        processed_data = {
            'ohlc': {
                'open': latest_data.get('open', 0.0),
                'high': latest_data.get('high', 0.0),
                'low': latest_data.get('low', 0.0),
                'close': latest_data.get('close', 0.0),
                'volume': latest_data.get('volume', 0)
            },
            'timestamp': latest_data.get('timestamp', datetime.now().timestamp())
        }
        
        return processed_data
        
    def _update_avg_creation_time(self, creation_time: float):
        """更新平均创建时间"""
        total_time = (self.stats['avg_creation_time'] * 
                     (self.stats['total_charts_created'] - 1) + creation_time)
        self.stats['avg_creation_time'] = total_time / self.stats['total_charts_created']
        
    def _emit_chart_event(self, event_type: EventType, data: Dict[str, Any]):
        """发送图表事件"""
        try:
            if self.event_bus:
                event = Event(type=event_type, data=data)
                self.event_bus.emit(event)
                
        except Exception as e:
            logger.error(f"发送图表事件失败: {e}")
            
    def _execute_callbacks(self, chart_id: str, event_type: str, data: Any):
        """执行回调函数"""
        try:
            if chart_id in self.chart_callbacks:
                for callback_info in self.chart_callbacks[chart_id]:
                    if callback_info['event_type'] == event_type:
                        callback = callback_info['callback']
                        if callable(callback):
                            callback(data)
                            
        except Exception as e:
            logger.error(f"执行图表回调失败 {chart_id}: {e}")


# 全局图表管理器实例
_chart_manager_instance = None

def get_chart_manager(event_bus: Optional[EventBus] = None) -> ChartManager:
    """获取图表管理器实例"""
    global _chart_manager_instance
    if _chart_manager_instance is None:
        _chart_manager_instance = ChartManager(event_bus)
    return _chart_manager_instance

def reset_chart_manager():
    """重置图表管理器"""
    global _chart_manager_instance
    if _chart_manager_instance:
        _chart_manager_instance.clear_all_charts()
        _chart_manager_instance = None
    logger.info("图表管理器已重置")


# 导出的公共接口
__all__ = [
    'ChartManager',
    'ChartInfo',
    'get_chart_manager',
    'reset_chart_manager'
]