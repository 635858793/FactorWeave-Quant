#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化仪表板
提供实时监控、性能对比、历史记录和系统状态的可视化界面
"""

from loguru import logger
from optimization.algorithm_optimizer import PerformanceEvaluator
import pandas as pd
import sqlite3

from analysis.pattern_manager import PatternManager
from optimization.database_schema import OptimizationDatabaseManager
from optimization.version_manager import VersionManager
from optimization.auto_tuner import AlgorithmAutoTuner
from core.database.unified_sqlite_access import UnifiedSQLiteAccess
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import threading
import time
from abc import ABC, abstractmethod

# GUI和图表库导入
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
        QGroupBox, QFormLayout, QProgressBar, QTextEdit, QSplitter,
        QTreeWidget, QTreeWidgetItem, QHeaderView, QComboBox, QSpinBox,
        QCheckBox, QSlider, QFrame, QScrollArea, QGridLayout, QMessageBox
    )
    from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
    from PyQt5.QtGui import QFont, QColor, QPalette

    # 核心组件导入
    from core.events import EventBus
    from core.events.event_bus import get_event_bus
    from core.metrics.events import SystemResourceUpdated
    from core.containers import get_service_container, ServiceContainer
    from core.services import ConfigService
    from core.services.cache_service import CacheService

    # 图表库 - 延迟导入，避免在QApplication创建前导入
    CHARTS_AVAILABLE = False
    matplotlib_imported = False

    GUI_AVAILABLE = True
except ImportError:
    logger.info("PyQt5 未安装，仪表板功能将受限")
    GUI_AVAILABLE = False
    CHARTS_AVAILABLE = False

# 再次确保核心事件类型在全局范围内可用

# 导入优化系统组件
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PerformanceChart(QWidget):
    """性能对比图表 - 基于统一图表服务的高性能实现"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 尝试使用统一图表服务
        try:
            from core.services.unified_chart_service import get_unified_chart_service
            from gui.widgets.chart_widget import ChartWidget

            # 创建图表控件
            self.chart_widget = ChartWidget(self)
            layout.addWidget(self.chart_widget)

            # 配置图表
            self.setup_chart()

            self.unified_chart_available = True

        except ImportError:
            # 降级到matplotlib实现 - 延迟导入
            global CHARTS_AVAILABLE, matplotlib_imported
            if not matplotlib_imported:
                try:
                    import matplotlib.pyplot as plt
                    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
                    from matplotlib.figure import Figure
                    import matplotlib.dates as mdates
                    CHARTS_AVAILABLE = True
                    matplotlib_imported = True
                    logger.info("matplotlib导入成功")
                except ImportError as e:
                    logger.warning(f"matplotlib导入失败: {e}")
                    CHARTS_AVAILABLE = False
                    matplotlib_imported = False
            
            if CHARTS_AVAILABLE:
                self.figure = Figure(figsize=(10, 6))
                self.canvas = FigureCanvas(self.figure)
                layout.addWidget(self.canvas)
                self.axes = self.figure.add_subplot(111)
                self.figure.tight_layout()
                self.unified_chart_available = False
            else:
                # 完全降级
                self.fallback_label = QLabel("图表服务不可用")
                self.fallback_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(self.fallback_label)
                self.unified_chart_available = False

    def setup_chart(self):
        """设置图表配置"""
        if not hasattr(self, 'chart_widget'):
            return

        try:
            # 获取统一图表服务
            from core.services.unified_chart_service import get_unified_chart_service
            chart_service = get_unified_chart_service()

            # 配置图表类型
            if hasattr(self.chart_widget, 'set_chart_type'):
                self.chart_widget.set_chart_type('line')

            # 应用主题
            if chart_service and hasattr(chart_service, 'apply_theme'):
                chart_service.apply_theme(self.chart_widget, 'dark')

            # 启用优化
            if hasattr(self.chart_widget, 'enable_cache'):
                self.chart_widget.enable_cache(True)
            if hasattr(self.chart_widget, 'enable_async_rendering'):
                self.chart_widget.enable_async_rendering(True)

        except ImportError as e:
            logger.info(f"图表配置失败: 无法导入统一图表服务 - {e}")
            logger.info("请检查 core.services.unified_chart_service 模块是否存在")
        except Exception as e:
            logger.info(f"图表配置失败: {e}")
            import traceback
            logger.info(f"详细错误信息: {traceback.format_exc()}")

    def plot_performance_history(self, pattern_name: str, history_data: List[Dict]):
        """绘制性能历史图表"""
        if self.unified_chart_available and hasattr(self, 'chart_widget'):
            # 使用统一图表服务
            self._plot_with_unified_service(
                pattern_name, history_data, 'history')
        elif hasattr(self, 'axes'):
            # 使用matplotlib降级实现
            self._plot_with_matplotlib(pattern_name, history_data, 'history')
        else:
            # 完全降级
            logger.info(f"无法绘制性能历史图表: {pattern_name}")

    def _plot_with_unified_service(self, pattern_name: str, data: any, chart_type: str):
        """使用统一图表服务绘制"""
        try:
            if chart_type == 'history':
                self._plot_history_with_unified_service(pattern_name, data)
            elif chart_type == 'comparison':
                self._plot_comparison_with_unified_service(data)
            else:
                logger.info(f"未知的图表类型: {chart_type}")

        except Exception as e:
            logger.info(f"统一图表服务绘制失败: {e}")
            # 降级到matplotlib
            if hasattr(self, 'axes'):
                if chart_type == 'history':
                    self._plot_with_matplotlib(pattern_name, data, chart_type)
                elif chart_type == 'comparison':
                    self._plot_comparison_with_matplotlib(data)

    def _plot_history_with_unified_service(self, pattern_name: str, history_data: List[Dict]):
        """使用统一图表服务绘制历史数据"""
        if not history_data:
            # 显示无数据提示
            self.chart_widget.show_message(f"暂无 {pattern_name} 的性能数据")
            return

        # 提取数据
        timestamps = []
        scores = []

        for item in history_data:
            if item.get('test_time'):
                try:
                    timestamp = datetime.fromisoformat(
                        item['test_time'].replace('Z', '+00:00'))
                    timestamps.append(timestamp)
                    scores.append(item.get('overall_score', 0))
                except Exception as e:
                    logger.info(f"解析时间戳失败: {e}")
                    continue

        if not timestamps or not scores:
            self.chart_widget.show_message("数据格式错误")
            return

        # 创建DataFrame
        df = pd.DataFrame({
            'timestamp': timestamps,
            'score': scores
        })
        df.set_index('timestamp', inplace=True)

        # 更新图表数据
        self.chart_widget.update_data(df)
        self.chart_widget.set_title(f'{pattern_name} 性能历史')

        # 添加标注
        if timestamps and scores:
            latest_score = scores[-1]
            self.chart_widget.add_annotation(
                timestamps[-1], latest_score,
                f'最新: {latest_score:.3f}'
            )

    def _plot_comparison_with_unified_service(self, comparison_data: Dict[str, List[float]]):
        """使用统一图表服务绘制对比数据"""
        if not comparison_data:
            self.chart_widget.show_message("暂无对比数据")
            return

        # 提取数据
        patterns = list(comparison_data.keys())
        scores = [comparison_data[pattern][-1] if comparison_data[pattern] else 0
                  for pattern in patterns]

        # 创建DataFrame
        df = pd.DataFrame({
            'pattern': patterns,
            'score': scores
        })

        # 设置图表类型为柱状图
        self.chart_widget.set_chart_type('bar')

        # 更新图表数据
        self.chart_widget.update_data(df)
        self.chart_widget.set_title('形态性能对比')

        # 添加数值标签
        for pattern, score in zip(patterns, scores):
            self.chart_widget.add_annotation(
                pattern, score, f'{score:.3f}'
            )

    def _plot_with_matplotlib(self, pattern_name: str, history_data: List[Dict], chart_type: str):
        """使用matplotlib降级实现"""
        if not hasattr(self, 'axes'):
            return

        self.axes.clear()

        if not history_data:
            self.axes.text(0.5, 0.5, f"暂无 {pattern_name} 的性能数据",
                           ha='center', va='center', transform=self.axes.transAxes)
            if hasattr(self, 'canvas'):
                self.canvas.draw()
            return

        # 提取数据
        timestamps = [datetime.fromisoformat(item['test_time'].replace('Z', '+00:00'))
                      for item in history_data if item.get('test_time')]
        scores = [item.get('overall_score', 0) for item in history_data]

        if not timestamps or not scores:
            self.axes.text(0.5, 0.5, "数据格式错误",
                           ha='center', va='center', transform=self.axes.transAxes)
            if hasattr(self, 'canvas'):
                self.canvas.draw()
            return

        # 绘制折线图
        self.axes.plot(timestamps, scores, 'b-o', linewidth=2, markersize=6)
        self.axes.set_title(f'{pattern_name} 性能历史',
                            fontsize=14, fontweight='bold')
        self.axes.set_xlabel('时间')
        self.axes.set_ylabel('综合评分')
        self.axes.grid(True, alpha=0.3)

        # 格式化x轴 - 延迟导入matplotlib
        global CHARTS_AVAILABLE, matplotlib_imported
        if not matplotlib_imported:
            try:
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
                from matplotlib.figure import Figure
                import matplotlib.dates as mdates
                CHARTS_AVAILABLE = True
                matplotlib_imported = True
                logger.info("matplotlib导入成功")
            except ImportError as e:
                logger.warning(f"matplotlib导入失败: {e}")
                CHARTS_AVAILABLE = False
                matplotlib_imported = False
        
        if CHARTS_AVAILABLE:
            self.axes.xaxis.set_major_formatter(
                mdates.DateFormatter('%m-%d %H:%M'))
            self.axes.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            self.figure.autofmt_xdate()

        # 添加最新分数标注
        if timestamps and scores:
            latest_score = scores[-1]
            self.axes.annotate(f'最新: {latest_score:.3f}',
                               xy=(timestamps[-1], latest_score),
                               xytext=(10, 10), textcoords='offset points',
                               bbox=dict(boxstyle='round,pad=0.3',
                                         facecolor='yellow', alpha=0.7),
                               arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

        if hasattr(self, 'canvas'):
            self.canvas.draw()

    def plot_comparison(self, comparison_data: Dict[str, List[float]]):
        """绘制多形态性能对比"""
        if self.unified_chart_available and hasattr(self, 'chart_widget'):
            # 使用统一图表服务
            self._plot_with_unified_service(
                'comparison', comparison_data, 'comparison')
        elif hasattr(self, 'axes'):
            # 使用matplotlib降级实现
            self._plot_comparison_with_matplotlib(comparison_data)
        else:
            # 完全降级
            logger.info("无法绘制性能对比图表")

    def _plot_comparison_with_matplotlib(self, comparison_data: Dict[str, List[float]]):
        """使用matplotlib绘制对比图表"""
        if not hasattr(self, 'axes'):
            return

        self.axes.clear()

        patterns = list(comparison_data.keys())
        scores = [comparison_data[pattern][-1] if comparison_data[pattern] else 0
                  for pattern in patterns]

        # 创建柱状图
        bars = self.axes.bar(patterns, scores, color='skyblue', alpha=0.7)

        # 添加数值标签
        for bar, score in zip(bars, scores):
            height = bar.get_height()
            self.axes.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                           f'{score:.3f}', ha='center', va='bottom')

        self.axes.set_title('形态性能对比', fontsize=14, fontweight='bold')
        self.axes.set_ylabel('综合评分')
        self.axes.set_ylim(0, 1.0)
        self.axes.grid(True, alpha=0.3)

        # 旋转x轴标签
        self.axes.tick_params(axis='x', rotation=45)

        if hasattr(self, 'canvas'):
            self.canvas.draw()


class DatabaseConnectionManager:
    """数据库连接管理器 - 管理数据库连接的生命周期"""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        """初始化连接管理器
        
        Args:
            db_path: 数据库文件路径
            max_connections: 最大连接数
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self._connections = []
        self._lock = threading.Lock()
        self._in_use = set()
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接
        
        Returns:
            数据库连接对象
        """
        with self._lock:
            # 尝试从池中获取空闲连接
            for conn in self._connections:
                if conn not in self._in_use:
                    self._in_use.add(conn)
                    return conn
            
            # 如果没有空闲连接且未达到最大连接数，创建新连接
            if len(self._connections) < self.max_connections:
                conn = sqlite3.connect(self.db_path)
                self._connections.append(conn)
                self._in_use.add(conn)
                return conn
            
            # 如果达到最大连接数，等待并重试
            return self._wait_for_connection()
    
    def _wait_for_connection(self) -> sqlite3.Connection:
        """等待可用连接"""
        import time
        max_wait = 5  # 最大等待5秒
        waited = 0
        
        while waited < max_wait:
            for conn in self._connections:
                if conn not in self._in_use:
                    self._in_use.add(conn)
                    return conn
            time.sleep(0.1)
            waited += 0.1
        
        # 如果超时，创建临时连接
        logger.warning("连接池已满，创建临时连接")
        return sqlite3.connect(self.db_path)
    
    def release_connection(self, conn: sqlite3.Connection):
        """释放数据库连接
        
        Args:
            conn: 要释放的连接
        """
        with self._lock:
            if conn in self._in_use:
                self._in_use.remove(conn)
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"关闭数据库连接失败: {e}")
            self._connections.clear()
            self._in_use.clear()
    
    def __enter__(self):
        """上下文管理器入口"""
        self._current_conn = self.get_connection()
        return self._current_conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release_connection(self._current_conn)
        return False


class OptimizationDataManager:
    """优化数据管理器 - 负责数据加载和缓存"""
    
    def __init__(self, 
                 db_manager: OptimizationDatabaseManager,
                 pattern_manager: PatternManager,
                 auto_tuner: AlgorithmAutoTuner,
                 cache_service: CacheService = None,
                 cache_ttl: timedelta = timedelta(minutes=5)):
        """初始化数据管理器
        
        Args:
            db_manager: 数据库管理器
            pattern_manager: 形态管理器
            auto_tuner: 算法自动调优器
            cache_service: 缓存服务（可选）
            cache_ttl: 缓存过期时间
        """
        self.db_manager = db_manager
        self.pattern_manager = pattern_manager
        self.auto_tuner = auto_tuner
        self.cache_service = cache_service
        self.cache_ttl = cache_ttl
        self._cache_keys = {
            'optimization_history': 'optimization:history',
            'version_info': 'optimization:version',
            'pattern_list': 'optimization:patterns',
            'optimization_stats': 'optimization:stats'
        }
        
        # 数据库连接管理器（使用连接池）
        self.db_connection_manager = DatabaseConnectionManager(
            db_path=db_manager.db_path,
            max_connections=5
        )
    
    def load_optimization_history(self) -> List[tuple]:
        """加载优化历史（带缓存）"""
        cache_key = self._cache_keys['optimization_history']
        
        if self.cache_service:
            cached_data = self.cache_service.get(cache_key)
            if cached_data is not None:
                logger.debug("从缓存加载优化历史")
                return cached_data
        
        with self.db_connection_manager as db_conn:
            cursor = db_conn.cursor()
            cursor.execute('''
                SELECT pattern_name, start_time, end_time, optimization_method,
                       status, improvement_percentage, best_score, iterations
                FROM optimization_logs
                ORDER BY start_time DESC
                LIMIT 100
            ''')
            records = cursor.fetchall()
        
        if self.cache_service:
            self.cache_service.set(cache_key, records, ttl=self.cache_ttl)
            logger.debug("优化历史已缓存")
        
        return records
    
    def load_version_info(self) -> dict:
        """加载版本信息（带缓存）"""
        cache_key = self._cache_keys['version_info']
        
        if self.cache_service:
            cached_data = self.cache_service.get(cache_key)
            if cached_data is not None:
                logger.debug("从缓存加载版本信息")
                return cached_data
        
        stats = self.db_manager.get_optimization_statistics()
        
        with self.db_connection_manager as db_conn:
            cursor = db_conn.cursor()
            cursor.execute('''
                SELECT av.pattern_name, av.version_number, av.created_time,
                       av.best_score, av.status, av.description
                FROM algorithm_versions av
                WHERE av.status = 'active'
                ORDER BY av.created_time DESC
                LIMIT 50
            ''')
            records = cursor.fetchall()
        
        version_data = {
            'stats': stats,
            'records': records
        }
        
        if self.cache_service:
            self.cache_service.set(cache_key, version_data, ttl=self.cache_ttl)
            logger.debug("版本信息已缓存")
        
        return version_data
    
    def load_pattern_list(self) -> List[str]:
        """加载形态列表（带缓存）"""
        cache_key = self._cache_keys['pattern_list']
        
        if self.cache_service:
            cached_data = self.cache_service.get(cache_key)
            if cached_data is not None:
                logger.debug("从缓存加载形态列表")
                return cached_data
        
        patterns = self.pattern_manager.get_all_patterns()
        pattern_names = [p.english_name for p in patterns if p.is_active]
        
        if self.cache_service:
            self.cache_service.set(cache_key, pattern_names, ttl=self.cache_ttl)
            logger.debug("形态列表已缓存")
        
        return pattern_names
    
    def load_optimization_statistics(self) -> dict:
        """加载优化统计（带缓存）"""
        cache_key = self._cache_keys['optimization_stats']
        
        if self.cache_service:
            cached_data = self.cache_service.get(cache_key)
            if cached_data is not None:
                logger.debug("从缓存加载优化统计")
                return cached_data
        
        stats = self.db_manager.get_optimization_statistics()
        
        if self.cache_service:
            self.cache_service.set(cache_key, stats, ttl=self.cache_ttl)
            logger.debug("优化统计已缓存")
        
        return stats
    
    def load_all_data(self) -> dict:
        """加载所有数据"""
        return {
            'history': self.load_optimization_history(),
            'version': self.load_version_info(),
            'patterns': self.load_pattern_list(),
            'stats': self.load_optimization_statistics()
        }
    
    def invalidate_cache(self, cache_type: str = 'all'):
        """使缓存失效
        
        Args:
            cache_type: 缓存类型 ('all', 'history', 'version', 'patterns', 'stats')
        """
        if not self.cache_service:
            return
        
        cache_keys = {
            'all': list(self._cache_keys.values()),
            'history': [self._cache_keys['optimization_history']],
            'version': [self._cache_keys['version_info']],
            'patterns': [self._cache_keys['pattern_list']],
            'stats': [self._cache_keys['optimization_stats']]
        }
        
        keys_to_invalidate = cache_keys.get(cache_type, [])
        for key in keys_to_invalidate:
            self.cache_service.delete(key)
            logger.debug(f"缓存已失效: {key}")


class OptimizationDataLoader(QThread):
    """优化数据加载线程 - 异步加载数据以避免阻塞UI"""
    
    data_loaded = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, data_manager: OptimizationDataManager):
        """初始化数据加载器
        
        Args:
            data_manager: 数据管理器
        """
        super().__init__()
        self.data_manager = data_manager
        self._should_stop = False
    
    def run(self):
        """异步加载数据"""
        try:
            if self._should_stop:
                return
            
            # 加载所有数据
            data = self.data_manager.load_all_data()
            
            if self._should_stop:
                return
            
            # 发送数据加载完成信号
            self.data_loaded.emit(data)
            
        except Exception as e:
            logger.error(f"数据加载失败: {e}")
            self.error_occurred.emit(f"数据加载失败: {e}")
    
    def stop(self):
        """停止数据加载"""
        self._should_stop = True
    
    def invalidate_cache(self, cache_type: str = 'all'):
        """使缓存失效
        
        Args:
            cache_type: 缓存类型 ('all', 'history', 'version', 'patterns', 'stats')
        """
        self.data_manager.invalidate_cache(cache_type)


class OptimizationDashboardConfig:
    """优化仪表板配置管理器"""
    
    DEFAULT_CONFIG = {
        'window': {
            'width': 1400,
            'height': 900,
            'x': 100,
            'y': 100
        },
        'cache': {
            'ttl_minutes': 5
        },
        'data': {
            'history_limit': 100,
            'version_limit': 50,
            'performance_limit': 20
        },
        'optimization': {
            'max_iterations': 30,
            'population_size': 15,
            'performance_threshold': 0.7,
            'improvement_target': 0.1
        }
    }
    
    def __init__(self, config_service: Any = None):
        """初始化配置管理器
        
        Args:
            config_service: 配置服务（可选）
        """
        self.config_service = config_service
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载配置"""
        config = {}
        
        # 深拷贝默认配置
        for key, value in self.DEFAULT_CONFIG.items():
            config[key] = value.copy() if isinstance(value, dict) else value
        
        # 从配置服务加载
        if self.config_service:
            try:
                window_width = self.config_service.get('optimization.dashboard.width', config['window']['width'])
                window_height = self.config_service.get('optimization.dashboard.height', config['window']['height'])
                window_x = self.config_service.get('optimization.dashboard.x', config['window']['x'])
                window_y = self.config_service.get('optimization.dashboard.y', config['window']['y'])
                
                config['window']['width'] = window_width
                config['window']['height'] = window_height
                config['window']['x'] = window_x
                config['window']['y'] = window_y
                
                cache_ttl = self.config_service.get('optimization.dashboard.cache_ttl', config['cache']['ttl_minutes'])
                config['cache']['ttl_minutes'] = cache_ttl
                
                history_limit = self.config_service.get('optimization.dashboard.history_limit', config['data']['history_limit'])
                version_limit = self.config_service.get('optimization.dashboard.version_limit', config['data']['version_limit'])
                performance_limit = self.config_service.get('optimization.dashboard.performance_limit', config['data']['performance_limit'])
                
                config['data']['history_limit'] = history_limit
                config['data']['version_limit'] = version_limit
                config['data']['performance_limit'] = performance_limit
                
                logger.debug("从配置服务加载仪表板配置")
            except Exception as e:
                logger.warning(f"加载配置失败，使用默认值: {e}")
        
        return config
    
    def get_window_geometry(self) -> tuple:
        """获取窗口几何信息"""
        return (
            self._config['window']['x'],
            self._config['window']['y'],
            self._config['window']['width'],
            self._config['window']['height']
        )
    
    def get_cache_ttl(self) -> timedelta:
        """获取缓存过期时间"""
        return timedelta(minutes=self._config['cache']['ttl_minutes'])
    
    def get_data_limits(self) -> dict:
        """获取数据限制"""
        return self._config['data'].copy()
    
    def get_optimization_config(self) -> dict:
        """获取优化配置"""
        return self._config['optimization'].copy()
    
    def save_window_geometry(self, x: int, y: int, width: int, height: int):
        """保存窗口几何信息"""
        self._config['window']['x'] = x
        self._config['window']['y'] = y
        self._config['window']['width'] = width
        self._config['window']['height'] = height
        
        if self.config_service:
            try:
                self.config_service.set('optimization.dashboard.width', width)
                self.config_service.set('optimization.dashboard.height', height)
                self.config_service.set('optimization.dashboard.x', x)
                self.config_service.set('optimization.dashboard.y', y)
                logger.debug("窗口几何信息已保存")
            except Exception as e:
                logger.warning(f"保存窗口几何信息失败: {e}")


class OptimizationExecutor:
    """优化执行器 - 负责执行优化任务和处理结果"""
    
    def __init__(self, auto_tuner: AlgorithmAutoTuner, 
                 dashboard: 'OptimizationDashboard'):
        """初始化优化执行器
        
        Args:
            auto_tuner: 算法自动调优器
            dashboard: 仪表板实例
        """
        self.auto_tuner = auto_tuner
        self.dashboard = dashboard
    
    def execute_one_click_optimize(self):
        """执行一键优化"""
        self.dashboard.log_message("启动一键优化...")
        self.dashboard.progress_label.setText("正在优化...")
        self.dashboard.progress_bar.setValue(0)
        
        def run_optimization():
            try:
                config = self.dashboard.dashboard_config.get_optimization_config()
                result = self.auto_tuner.one_click_optimize(
                    optimization_method="genetic",
                    max_iterations=config.get('max_iterations', 20)
                )
                
                self._handle_optimization_result(result, "一键优化")
                
            except Exception as e:
                self.dashboard.log_message(f" 一键优化失败: {e}")
                self.dashboard.progress_label.setText("优化失败")
        
        threading.Thread(target=run_optimization, daemon=True).start()
    
    def execute_smart_optimize(self):
        """执行智能优化"""
        self.dashboard.log_message("启动智能优化...")
        self.dashboard.progress_label.setText("智能分析中...")
        
        def run_smart_optimization():
            try:
                config = self.dashboard.dashboard_config.get_optimization_config()
                result = self.auto_tuner.smart_optimize(
                    performance_threshold=config.get('performance_threshold', 0.7),
                    improvement_target=config.get('improvement_target', 0.1)
                )
                
                if result.get("status") == "no_optimization_needed":
                    self.dashboard.log_message("所有形态性能都达到要求，无需优化")
                    self.dashboard.progress_label.setText("智能优化完成")
                else:
                    self._handle_optimization_result(result, "智能优化")
                
            except Exception as e:
                self.dashboard.log_message(f" 智能优化失败: {e}")
                self.dashboard.progress_label.setText("优化失败")
        
        threading.Thread(target=run_smart_optimization, daemon=True).start()
    
    def execute_pattern_optimize(self, pattern_name: str):
        """执行单个形态优化
        
        Args:
            pattern_name: 形态名称
        """
        self.dashboard.log_message(f" 开始优化形态: {pattern_name}")
        self.dashboard.progress_label.setText(f"正在优化 {pattern_name}...")
        
        def run_single_optimization():
            try:
                from optimization.algorithm_optimizer import OptimizationConfig
                
                config = self.dashboard.dashboard_config.get_optimization_config()
                opt_config = OptimizationConfig(
                    method="genetic",
                    max_iterations=config.get('max_iterations', 30),
                    population_size=config.get('population_size', 15)
                )
                
                result = self.auto_tuner.optimizer.optimize_algorithm(
                    pattern_name=pattern_name,
                    config=opt_config
                )
                
                improvement = result.get("improvement_percentage", 0)
                self.dashboard.log_message(
                    f" {pattern_name} 优化完成！性能提升: {improvement:.3f}%")
                self.dashboard.progress_label.setText("优化完成")
                
                # 使缓存失效并刷新数据
                self.dashboard.invalidate_cache('all')
                self.dashboard.refresh_all_data()
                
            except Exception as e:
                self.dashboard.log_message(f" {pattern_name} 优化失败: {e}")
                self.dashboard.progress_label.setText("优化失败")
        
        threading.Thread(target=run_single_optimization, daemon=True).start()
    
    def _handle_optimization_result(self, result: dict, optimize_type: str):
        """处理优化结果
        
        Args:
            result: 优化结果
            optimize_type: 优化类型
        """
        summary = result.get("summary", {})
        self.dashboard.log_message(f" {optimize_type}完成！")
        self.dashboard.log_message(f"   总任务数: {summary.get('total_tasks', 0)}")
        self.dashboard.log_message(
            f"   成功任务数: {summary.get('successful_tasks', 0)}")
        self.dashboard.log_message(
            f"   平均改进: {summary.get('average_improvement', 0):.3f}%")
        
        self.dashboard.progress_bar.setValue(100)
        self.dashboard.progress_label.setText("优化完成")
        
        # 使缓存失效
        self.dashboard.invalidate_cache('all')
        # 刷新数据
        self.dashboard.refresh_all_data()


class DashboardEventManager:
    """仪表板事件管理器 - 统一管理仪表板的各种事件"""
    
    def __init__(self, event_bus: EventBus, dashboard: 'OptimizationDashboard'):
        """初始化事件管理器
        
        Args:
            event_bus: 事件总线
            dashboard: 仪表板实例
        """
        self.event_bus = event_bus
        self.dashboard = dashboard
        self._subscribed_events = []
    
    def subscribe_all_events(self):
        """订阅所有需要的事件"""
        self._subscribe_system_events()
        self._subscribe_optimization_events()
        self._subscribe_data_events()
        logger.debug("所有事件已订阅")
    
    def _subscribe_system_events(self):
        """订阅系统事件"""
        # 订阅系统资源更新事件
        self.event_bus.subscribe(
            SystemResourceUpdated, self._handle_resource_update)
        self._subscribed_events.append(SystemResourceUpdated)
    
    def _subscribe_optimization_events(self):
        """订阅优化事件"""
        # 这里可以添加更多优化相关的事件订阅
        pass
    
    def _subscribe_data_events(self):
        """订阅数据事件"""
        # 这里可以添加更多数据相关的事件订阅
        pass
    
    def _handle_resource_update(self, event: SystemResourceUpdated):
        """处理系统资源更新事件"""
        stats = {
            "cpu_percent": event.cpu_percent,
            "memory_percent": event.memory_percent,
        }
        self.dashboard.stats_updated.emit(stats)
    
    def publish_optimization_started(self, pattern_name: str, optimize_type: str):
        """发布优化开始事件
        
        Args:
            pattern_name: 形态名称
            optimize_type: 优化类型
        """
        # 这里可以发布自定义的优化开始事件
        logger.debug(f"优化开始: {pattern_name} ({optimize_type})")
    
    def publish_optimization_completed(self, pattern_name: str, optimize_type: str, result: dict):
        """发布优化完成事件
        
        Args:
            pattern_name: 形态名称
            optimize_type: 优化类型
            result: 优化结果
        """
        # 这里可以发布自定义的优化完成事件
        logger.debug(f"优化完成: {pattern_name} ({optimize_type})")
    
    def publish_data_refreshed(self, data_type: str):
        """发布数据刷新事件
        
        Args:
            data_type: 数据类型
        """
        # 这里可以发布自定义的数据刷新事件
        logger.debug(f"数据已刷新: {data_type}")
    
    def unsubscribe_all_events(self):
        """取消订阅所有事件"""
        for event_type in self._subscribed_events:
            try:
                self.event_bus.unsubscribe(event_type)
            except Exception as e:
                logger.warning(f"取消订阅事件失败: {e}")
        self._subscribed_events.clear()
        logger.debug("所有事件已取消订阅")


class OptimizationDashboard(QMainWindow if GUI_AVAILABLE else object):
    """优化仪表板主窗口"""

    # 添加一个信号，用于跨线程安全地更新UI
    stats_updated = pyqtSignal(dict)

    def __init__(self, 
                 event_bus: EventBus,
                 auto_tuner: AlgorithmAutoTuner = None,
                 version_manager: VersionManager = None,
                 evaluator: PerformanceEvaluator = None,
                 pattern_manager: PatternManager = None,
                 db_manager: OptimizationDatabaseManager = None,
                 config_service: Any = None,
                 cache_service: CacheService = None):
        """初始化
        
        Args:
            event_bus: 事件总线
            auto_tuner: 算法自动调优器（可选，如果为None则创建）
            version_manager: 版本管理器（可选，如果为None则创建）
            evaluator: 性能评估器（可选，如果为None则创建）
            pattern_manager: 形态管理器（可选，如果为None则创建）
            db_manager: 数据库管理器（可选，如果为None则创建）
            config_service: 配置服务（可选，如果为None则创建）
            cache_service: 缓存服务（可选，如果为None则创建）
        """
        if not GUI_AVAILABLE:
            logger.info("GUI不可用，仪表板将以命令行模式运行")
            return

        super().__init__()

        # 核心组件（支持依赖注入）
        self.auto_tuner = auto_tuner or AlgorithmAutoTuner(debug_mode=True)
        self.version_manager = version_manager or VersionManager()
        self.evaluator = evaluator or PerformanceEvaluator(debug_mode=True)
        self.pattern_manager = pattern_manager or PatternManager()
        self.db_manager = db_manager or OptimizationDatabaseManager()
        self.config_service = config_service
        self.cache_service = cache_service

        self._event_bus = event_bus
        self._optimization_thread = None

        # 配置管理器（集中管理配置）
        self.dashboard_config = OptimizationDashboardConfig(config_service)

        # 数据管理器（分离数据加载和缓存职责）
        self.data_manager = OptimizationDataManager(
            db_manager=self.db_manager,
            pattern_manager=self.pattern_manager,
            auto_tuner=self.auto_tuner,
            cache_service=self.cache_service,
            cache_ttl=self.dashboard_config.get_cache_ttl()
        )

        # 数据
        self.current_pattern = None
        self.performance_history = {}

        # 优化执行器（分离优化执行职责）
        self.optimizer_executor = OptimizationExecutor(
            auto_tuner=self.auto_tuner,
            dashboard=self
        )

        # 事件管理器（统一管理事件）
        self.event_manager = DashboardEventManager(event_bus, self)

        # 从配置加载窗口大小
        x, y, width, height = self.dashboard_config.get_window_geometry()
        self.setGeometry(x, y, width, height)

        self.setWindowTitle("FactorWeave-Quant 形态识别优化仪表板")
        self.init_ui()
        
        # 连接信号
        self.stats_updated.connect(self._update_ui_with_stats)
        
        # 订阅所有事件
        self.event_manager.subscribe_all_events()

    def _subscribe_to_events(self):
        """订阅所有需要的事件（已废弃，使用event_manager.subscribe_all_events）"""
        pass

    def init_ui(self):
        """初始化用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # 左侧面板
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 1)

        # 右侧面板
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 3)

        # 初始化时刷新所有数据
        self.refresh_all_data()

    def create_left_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # 系统状态组
        status_group = QGroupBox("系统状态")
        status_layout = QFormLayout()

        self.cpu_label = QLabel("N/A")
        self.memory_label = QLabel("N/A")
        self.active_tasks_label = QLabel("0")
        self.total_versions_label = QLabel("0")

        status_layout.addRow("CPU使用率:", self.cpu_label)
        status_layout.addRow("内存使用率:", self.memory_label)
        status_layout.addRow("活跃任务:", self.active_tasks_label)
        status_layout.addRow("总版本数:", self.total_versions_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 快速操作组
        actions_group = QGroupBox("快速操作")
        actions_layout = QVBoxLayout()

        self.one_click_btn = QPushButton("一键优化所有形态")
        self.one_click_btn.clicked.connect(self.one_click_optimize)
        actions_layout.addWidget(self.one_click_btn)

        self.smart_optimize_btn = QPushButton("智能优化")
        self.smart_optimize_btn.clicked.connect(self.smart_optimize)
        actions_layout.addWidget(self.smart_optimize_btn)

        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.clicked.connect(self.refresh_all_data)
        actions_layout.addWidget(self.refresh_btn)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        # 形态选择组
        pattern_group = QGroupBox("形态选择")
        pattern_layout = QVBoxLayout()

        self.pattern_combo = QComboBox()
        self.pattern_combo.currentTextChanged.connect(self.on_pattern_changed)
        pattern_layout.addWidget(self.pattern_combo)

        self.pattern_optimize_btn = QPushButton("优化选中形态")
        self.pattern_optimize_btn.clicked.connect(
            self.optimize_selected_pattern)
        pattern_layout.addWidget(self.pattern_optimize_btn)

        pattern_group.setLayout(pattern_layout)
        layout.addWidget(pattern_group)

        # 优化进度组
        progress_group = QGroupBox("优化进度")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        layout.addStretch()
        return panel

    def create_right_panel(self) -> QWidget:
        """创建右侧主面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 性能监控标签页
        self.performance_tab = self.create_performance_tab()
        self.tab_widget.addTab(self.performance_tab, "性能监控")

        # 优化历史标签页
        self.history_tab = self.create_history_tab()
        self.tab_widget.addTab(self.history_tab, "优化历史")

        # 版本管理标签页
        self.version_tab = self.create_version_tab()
        self.tab_widget.addTab(self.version_tab, "版本管理")

        # 系统日志标签页
        self.log_tab = self.create_log_tab()
        self.tab_widget.addTab(self.log_tab, "系统日志")

        return panel

    def create_performance_tab(self) -> QWidget:
        """创建性能监控标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        # 性能图表 - 延迟导入matplotlib
        global CHARTS_AVAILABLE, matplotlib_imported
        if not matplotlib_imported:
            try:
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
                from matplotlib.figure import Figure
                import matplotlib.dates as mdates
                CHARTS_AVAILABLE = True
                matplotlib_imported = True
                logger.info("matplotlib导入成功")
            except ImportError as e:
                logger.warning(f"matplotlib导入失败: {e}")
                CHARTS_AVAILABLE = False
                matplotlib_imported = False
        
        if CHARTS_AVAILABLE:
            self.performance_chart = PerformanceChart()
            layout.addWidget(self.performance_chart)
        else:
            chart_placeholder = QLabel("图表功能需要安装 matplotlib")
            chart_placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(chart_placeholder)

        # 性能指标表格
        metrics_group = QGroupBox("当前性能指标")
        metrics_layout = QVBoxLayout()

        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(2)
        self.metrics_table.setHorizontalHeaderLabels(["指标", "数值"])
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        metrics_layout.addWidget(self.metrics_table)

        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        return tab

    def create_history_tab(self) -> QWidget:
        """创建优化历史标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "形态名称", "开始时间", "结束时间", "优化方法",
            "状态", "性能提升", "最佳评分", "迭代次数"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.history_table)

        return tab

    def create_version_tab(self) -> QWidget:
        """创建版本管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        # 版本统计
        stats_group = QGroupBox("版本统计")
        stats_layout = QGridLayout()

        self.total_patterns_label = QLabel("0")
        self.active_versions_label = QLabel("0")
        self.avg_improvement_label = QLabel("0%")

        stats_layout.addWidget(QLabel("总形态数:"), 0, 0)
        stats_layout.addWidget(self.total_patterns_label, 0, 1)
        stats_layout.addWidget(QLabel("活跃版本:"), 0, 2)
        stats_layout.addWidget(self.active_versions_label, 0, 3)
        stats_layout.addWidget(QLabel("平均提升:"), 1, 0)
        stats_layout.addWidget(self.avg_improvement_label, 1, 1)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 版本列表
        self.version_table = QTableWidget()
        self.version_table.setColumnCount(6)
        self.version_table.setHorizontalHeaderLabels([
            "形态名称", "版本号", "创建时间", "优化方法", "性能评分", "状态"
        ])
        self.version_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.version_table)

        return tab

    def create_log_tab(self) -> QWidget:
        """创建系统日志标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        # 日志控制
        control_layout = QHBoxLayout()

        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        control_layout.addWidget(self.auto_scroll_check)

        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        control_layout.addWidget(self.clear_log_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)

        return tab

    def _update_ui_with_stats(self, stats: Dict[str, Any]):
        """使用收集到的统计信息更新UI标签 (槽函数)"""
        cpu_percent = stats.get("cpu_percent", 0)
        self.cpu_label.setText(f"{cpu_percent:.2f}%")

        mem_percent = stats.get("memory_percent", 0)
        self.memory_label.setText(f"{mem_percent:.2f}%")

        # 优化统计数据现在从数据库中定期刷新，而不是从监控线程获取
        # 可以在 refresh_all_data 中更新

    def refresh_all_data(self):
        """刷新所有数据（异步）"""
        # 停止之前的数据加载器
        if hasattr(self, '_data_loader') and self._data_loader and self._data_loader.isRunning():
            self._data_loader.stop()
            self._data_loader.wait()
        
        # 创建并启动新的数据加载器（带缓存）
        self._data_loader = OptimizationDataLoader(
            data_manager=self.data_manager
        )
        
        # 连接信号
        self._data_loader.data_loaded.connect(self._on_data_loaded)
        self._data_loader.error_occurred.connect(self._on_data_load_error)
        
        # 启动异步加载
        self._data_loader.start()
        self.log_message("正在异步加载数据...")
    
    def invalidate_cache(self, cache_type: str = 'all'):
        """使缓存失效
        
        Args:
            cache_type: 缓存类型 ('all', 'history', 'version', 'patterns', 'stats')
        """
        self.data_manager.invalidate_cache(cache_type)
        self.log_message(f"缓存已失效: {cache_type}")
    
    def _on_data_loaded(self, data: dict):
        """数据加载完成回调"""
        try:
            # 更新优化历史
            if 'history' in data:
                self._update_history_table(data['history'])
            
            # 更新版本信息
            if 'version' in data:
                self._update_version_info(data['version'])
            
            # 更新形态列表
            if 'patterns' in data:
                self._update_pattern_list(data['patterns'])
            
            # 更新优化统计
            if 'stats' in data:
                self._update_optimization_stats(data['stats'])
            
            self.log_message("数据加载完成")
            
        except Exception as e:
            self.log_message(f"更新UI失败: {e}", "error")
    
    def _on_data_load_error(self, error_msg: str):
        """数据加载错误回调"""
        self.log_message(error_msg, "error")
    
    def _update_history_table(self, records: List[tuple]):
        """更新历史表格"""
        self.history_table.setRowCount(len(records))
        
        for i, record in enumerate(records):
            for j, value in enumerate(record):
                if value is None:
                    value = "N/A"
                # 性能提升和最佳评分
                elif j in [5, 6] and isinstance(value, (int, float)):
                    value = f"{value:.3f}"
                
                self.history_table.setItem(
                    i, j, QTableWidgetItem(str(value)))
    
    def _update_version_info(self, version_data: dict):
        """更新版本信息"""
        stats = version_data.get('stats', {})
        records = version_data.get('records', [])
        
        # 更新统计标签
        self.total_patterns_label.setText(str(len(self.pattern_combo)))
        self.active_versions_label.setText(str(stats.get('active_versions', 0)))
        
        avg_improvement = stats.get('avg_improvement', 0)
        self.avg_improvement_label.setText(f"{avg_improvement:.3f}%")
        
        # 更新版本表格
        self.version_table.setRowCount(len(records))
        
        for i, record in enumerate(records):
            for j, value in enumerate(record):
                if j == 3 and value is not None:  # 性能评分
                    value = f"{value:.3f}"
                elif j == 4:  # 状态
                    value = "激活" if value == "active" else "未激活"
                elif value is None:
                    value = "N/A"
                self.version_table.setItem(
                    i, j, QTableWidgetItem(str(value)))
    
    def _update_pattern_list(self, pattern_names: List[str]):
        """更新形态列表"""
        current_text = self.pattern_combo.currentText()
        self.pattern_combo.clear()
        self.pattern_combo.addItems(pattern_names)
        
        # 恢复之前的选择
        if current_text in pattern_names:
            self.pattern_combo.setCurrentText(current_text)
        elif pattern_names:
            self.pattern_combo.setCurrentIndex(0)
    
    def _update_optimization_stats(self, stats: dict):
        """更新优化统计"""
        self.total_versions_label.setText(str(stats.get('total_versions', 'N/A')))
        self.active_tasks_label.setText(str(len(self.auto_tuner.running_tasks)))
        self.total_patterns_label.setText(str(len(self.pattern_combo)))
        self.active_versions_label.setText(str(stats.get('active_versions', 'N/A')))
        self.avg_improvement_label.setText(f"{stats.get('avg_improvement', 'N/A')}%")

    def refresh_pattern_list(self):
        """刷新形态列表"""
        try:
            pattern_names = self.data_manager.load_pattern_list()
            self._update_pattern_list(pattern_names)
        except Exception as e:
            self.log_message(f" 刷新形态列表失败: {e}")

    def refresh_optimization_history(self):
        """刷新优化历史"""
        try:
            records = self.data_manager.load_optimization_history()
            self._update_history_table(records)
        except Exception as e:
            self.log_message(f" 刷新优化历史失败: {e}")

    def refresh_version_info(self):
        """刷新版本信息"""
        try:
            version_data = self.data_manager.load_version_info()
            self._update_version_info(version_data)
        except Exception as e:
            self.log_message(f" 刷新版本信息失败: {e}")

    def refresh_performance_data(self, pattern_name: str):
        """刷新性能数据"""
        try:
            # 获取性能历史
            history = self.db_manager.get_performance_history(
                pattern_name, limit=20)

            # 更新图表
            if CHARTS_AVAILABLE and hasattr(self, 'performance_chart'):
                self.performance_chart.plot_performance_history(
                    pattern_name, history)

            # 更新性能指标表格
            if history:
                latest = history[0]
                metrics = [
                    ("综合评分", f"{latest.get('overall_score', 0):.3f}"),
                    ("信号质量", f"{latest.get('signal_quality', 0):.3f}"),
                    ("平均置信度", f"{latest.get('confidence_avg', 0):.3f}"),
                    ("执行时间", f"{latest.get('execution_time', 0):.3f}秒"),
                    ("识别形态数", str(latest.get('patterns_found', 0))),
                    ("鲁棒性", f"{latest.get('robustness_score', 0):.3f}"),
                    ("参数敏感性", f"{latest.get('parameter_sensitivity', 0):.3f}")
                ]

                self.metrics_table.setRowCount(len(metrics))
                for i, (name, value) in enumerate(metrics):
                    self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
                    self.metrics_table.setItem(i, 1, QTableWidgetItem(value))

        except Exception as e:
            self.log_message(f" 刷新性能数据失败: {e}")

    def on_pattern_changed(self, pattern_name: str):
        """形态选择改变"""
        if pattern_name:
            self.current_pattern = pattern_name
            self.refresh_performance_data(pattern_name)
            self.log_message(f"切换到形态: {pattern_name}")

    def one_click_optimize(self):
        """一键优化所有形态"""
        self.optimizer_executor.execute_one_click_optimize()

    def smart_optimize(self):
        """智能优化"""
        self.optimizer_executor.execute_smart_optimize()

    def optimize_selected_pattern(self):
        """优化选中的形态"""
        pattern_name = self.pattern_combo.currentText()
        if not pattern_name:
            self.log_message("请先选择要优化的形态")
            return
        
        self.optimizer_executor.execute_pattern_optimize(pattern_name)

    def log_message(self, message: str, level: str = "info"):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [{level.upper()}] {message}"

        self.log_text.append(formatted_message)

        # 自动滚动到底部
        if self.auto_scroll_check.isChecked():
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        # 同时输出到控制台
        if level == "error":
            logger.error(formatted_message)
        elif level == "warning":
            logger.warning(formatted_message)
        else:
            logger.info(formatted_message)

    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.log_message("日志已清空")

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.log_message("正在关闭优化仪表板...")
        
        # 取消订阅所有事件
        self.event_manager.unsubscribe_all_events()
        
        # 保存窗口几何信息
        geometry = self.geometry()
        self.dashboard_config.save_window_geometry(
            geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )
        
        # 停止数据加载器
        if hasattr(self, '_data_loader') and self._data_loader and self._data_loader.isRunning():
            self._data_loader.stop()
            self._data_loader.wait()
        
        # 关闭数据库连接池
        if hasattr(self, 'data_manager') and hasattr(self.data_manager, 'db_connection_manager'):
            self.data_manager.db_connection_manager.close_all()
        
        if self._optimization_thread and self._optimization_thread.isRunning():
            reply = QMessageBox.question(self, '确认退出',
                                         "优化仍在进行中，确定要退出吗？",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._optimization_thread.requestInterruption()
                self._optimization_thread.quit()
                if not self._optimization_thread.wait(5000):
                    logger.warning("优化线程未能在5秒内退出，强制终止")
                    self._optimization_thread.terminate()
                    self._optimization_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# 全局仪表板实例，确保只有一个
_dashboard_instance = None
_dashboard_lock = threading.Lock()


def create_optimization_dashboard(event_bus: EventBus, 
                              service_container: Optional[ServiceContainer] = None) -> OptimizationDashboard:
    """创建并返回优化仪表板的单例
    
    Args:
        event_bus: 事件总线
        service_container: 服务容器（可选，如果提供则使用依赖注入）
    
    Returns:
        OptimizationDashboard实例
    """
    global _dashboard_instance
    with _dashboard_lock:
        if _dashboard_instance is None:
            # 如果提供了服务容器，尝试从容器中获取依赖
            if service_container:
                try:
                    auto_tuner = service_container.try_resolve(AlgorithmAutoTuner)
                    version_manager = service_container.try_resolve(VersionManager)
                    evaluator = service_container.try_resolve(PerformanceEvaluator)
                    pattern_manager = service_container.try_resolve(PatternManager)
                    db_manager = service_container.try_resolve(OptimizationDatabaseManager)
                    config_service = service_container.try_resolve(ConfigService)
                    cache_service = service_container.try_resolve(CacheService)
                    
                    _dashboard_instance = OptimizationDashboard(
                        event_bus=event_bus,
                        auto_tuner=auto_tuner,
                        version_manager=version_manager,
                        evaluator=evaluator,
                        pattern_manager=pattern_manager,
                        db_manager=db_manager,
                        config_service=config_service,
                        cache_service=cache_service
                    )
                except Exception as e:
                    logger.warning(f"依赖注入失败，使用默认创建: {e}")
                    _dashboard_instance = OptimizationDashboard(event_bus=event_bus)
            else:
                _dashboard_instance = OptimizationDashboard(event_bus=event_bus)
    return _dashboard_instance


def run_dashboard():
    """运行仪表板应用"""
    if not GUI_AVAILABLE:
        logger.info("GUI不可用，无法启动仪表板")
        return

    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 创建仪表板
    dashboard = create_optimization_dashboard(get_event_bus())
    dashboard.show()

    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_dashboard()
