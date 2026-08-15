#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一性能监控组件
现代化统一性能监控界面
"""

import json
import time
from datetime import datetime
from typing import Dict

from PyQt5.QtCore import Qt, QDateTime, QThreadPool, pyqtSlot, QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QLabel, QTabWidget, QStatusBar,
    QSizePolicy, QFileDialog, QFrame
)

from loguru import logger

from core.events import EventBus

# 延迟导入性能监控模块，避免在模块级别导入时卡住
_get_performance_monitor = None
_UnifiedPerformanceMonitor = None

# 延迟导入深度分析框架
_get_advanced_analytics = None
_DeepAnalysisFramework = None
_get_performance_coordinator = None

def _import_performance_monitor():
    """延迟导入性能监控模块"""
    global _get_performance_monitor, _UnifiedPerformanceMonitor, _get_performance_coordinator
    
    if _get_performance_monitor is None:
        from core.performance import get_performance_monitor
        from core.performance.unified_monitor import UnifiedPerformanceMonitor
        from core.services import get_performance_coordinator
        _get_performance_monitor = get_performance_monitor
        _UnifiedPerformanceMonitor = UnifiedPerformanceMonitor
        _get_performance_coordinator = get_performance_coordinator

def _import_deep_analysis():
    """延迟导入深度分析框架"""
    global _get_advanced_analytics, _DeepAnalysisFramework
    
    if _get_advanced_analytics is None:
        try:
            from core.services import get_advanced_analytics
            _get_advanced_analytics = get_advanced_analytics
        except ImportError:
            logger.warning("深度分析框架不可用")

# 延迟导入异步工作线程
_AsyncDataWorker = None
_AsyncStrategyWorker = None
_AsyncDataSignals = None

def _import_async_workers():
    """延迟导入异步工作线程"""
    global _AsyncDataWorker, _AsyncStrategyWorker, _AsyncDataSignals
    
    if _AsyncDataWorker is None:
        from gui.widgets.performance import AsyncDataWorker, AsyncStrategyWorker, AsyncDataSignals
        _AsyncDataWorker = AsyncDataWorker
        _AsyncStrategyWorker = AsyncStrategyWorker
        _AsyncDataSignals = AsyncDataSignals

# 延迟导入标签页组件
_ModernSystemMonitorTab = None
_ModernStrategyPerformanceTab = None
_ModernAlgorithmOptimizationTab = None
_ModernRiskControlCenterTab = None
_ModernTradingExecutionMonitorTab = None
_DataQualityMonitorTab = None

def _import_tabs():
    """延迟导入标签页组件"""
    global _ModernSystemMonitorTab, _ModernStrategyPerformanceTab, _ModernAlgorithmOptimizationTab
    global _ModernRiskControlCenterTab, _ModernTradingExecutionMonitorTab, _DataQualityMonitorTab
    
    if _ModernSystemMonitorTab is None:
        from gui.widgets.performance import (
            ModernSystemMonitorTab,
            ModernStrategyPerformanceTab,
            ModernAlgorithmOptimizationTab,
            ModernRiskControlCenterTab,
            ModernTradingExecutionMonitorTab
        )
        from gui.widgets.enhanced_ui.data_quality_monitor_tab import DataQualityMonitorTab
        _ModernSystemMonitorTab = ModernSystemMonitorTab
        _ModernStrategyPerformanceTab = ModernStrategyPerformanceTab
        _ModernAlgorithmOptimizationTab = ModernAlgorithmOptimizationTab
        _ModernRiskControlCenterTab = ModernRiskControlCenterTab
        _ModernTradingExecutionMonitorTab = ModernTradingExecutionMonitorTab
        _DataQualityMonitorTab = DataQualityMonitorTab

class StatusMessageCallback(QObject):
    """状态消息回调包装类，避免lambda函数导致的内存泄漏"""
    def __init__(self, parent, status_bar):
        super().__init__(parent)
        self.status_bar = status_bar

    def set_ready(self):
        """设置状态为就绪"""
        try:
            if self.status_bar:
                self.status_bar.setText("就绪")
        except Exception as e:
            logger.error(f"设置状态消息失败: {e}")

    def set_text(self, text):
        """设置状态文本"""
        try:
            if self.status_bar:
                self.status_bar.setText(text)
        except Exception as e:
            logger.error(f"设置状态消息失败: {e}")


class UpdateDataCallback(QObject):
    """更新数据回调包装类，避免lambda函数导致的内存泄漏"""
    def __init__(self, parent):
        super().__init__(parent)

    def update_data(self):
        """更新数据"""
        try:
            parent = self.parent()
            if parent:
                parent.update_current_tab_data_async()
        except Exception as e:
            logger.error(f"更新数据回调失败: {e}")


class TaskCounterCallback(QObject):
    """任务计数回调包装类，避免lambda函数导致的内存泄漏"""
    def __init__(self, parent):
        super().__init__(parent)

    def on_task_done(self):
        """任务完成回调"""
        try:
            parent = self.parent()
            if parent:
                parent._active_task_count = max(0, parent._active_task_count - 1)
                logger.debug(f"任务完成，活跃任务数: {parent._active_task_count}")
        except Exception as e:
            logger.error(f"任务计数回调失败: {e}")


class StrategyDataCallback(QObject):
    """策略数据回调包装类，避免lambda函数导致的内存泄漏"""
    def __init__(self, parent, cache_key, current_time):
        super().__init__(parent)
        self.cache_key = cache_key
        self.current_time = current_time

    def on_data_ready(self, data):
        """数据准备就绪回调"""
        try:
            parent = self.parent()
            if parent:
                parent._on_strategy_data_received(data, self.cache_key, self.current_time)
        except Exception as e:
            logger.error(f"策略数据回调失败: {e}")

    def on_finished(self):
        """计算完成回调"""
        try:
            parent = self.parent()
            if parent:
                parent._on_strategy_calculation_finished(self.cache_key, self.current_time)
        except Exception as e:
            logger.error(f"策略计算完成回调失败: {e}")


class ModernUnifiedPerformanceWidget(QWidget):
    """现代化统一性能监控组件 - 专业交易软件风格"""

    def __init__(self, event_bus: EventBus = None, parent=None):
        super().__init__(parent)

        # 设置窗口标志
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint |
                            Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        # 延迟导入性能监控模块
        _import_performance_monitor()
        
        self.monitor = _get_performance_monitor()
        self._event_bus = event_bus
        self.current_tab_index = 0  # 添加当前tab跟踪
        self._data_cache = {}  # 添加数据缓存
        self._last_update_time = {}  # 添加更新时间跟踪

        # 性能优化相关变量
        self._is_dragging = False  # 拖动状态检测
        self._update_paused = False  # 更新暂停标志
        self._last_mouse_move_time = 0  # 最后鼠标移动时间
        self._update_counter = 0  # 更新计数器，用于降频

        # 智能性能监控已移除 - 避免功能重叠
        self.performance_integrator = None
        self._has_smart_monitoring = False

        # 初始化性能监控器
        self.performance_monitor = _UnifiedPerformanceMonitor()
        logger.info("性能监控器初始化完成")

        # 初始化完整版性能协调器（用于高级功能）
        self.performance_coordinator = None
        if _get_performance_coordinator is not None:
            try:
                self.performance_coordinator = _get_performance_coordinator()
                logger.info("完整版性能协调器集成成功")
            except Exception as e:
                logger.warning(f"性能协调器初始化失败: {e}")

        # 初始化深度分析框架
        _import_deep_analysis()
        self.advanced_analytics = None
        if _get_advanced_analytics is not None:
            try:
                self.advanced_analytics = _get_advanced_analytics()
                logger.info("深度分析框架集成成功")
            except Exception as e:
                logger.warning(f"深度分析框架初始化失败: {e}")

        self.performance_integrator = None
        self._has_smart_monitoring = False

        # 延迟导入异步工作线程
        _import_async_workers()
        
        # 初始化异步数据获取
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(2)  # 从4减少到2，减少并发任务数
        self._async_signals = _AsyncDataSignals()
        self._async_signals.data_ready.connect(self._handle_async_data)
        self._async_signals.error_occurred.connect(self._handle_async_error)

        # 信号槽连接跟踪（用于清理）
        self._signal_connections = []

        # 任务计数器，防止线程池任务堆积
        self._active_task_count = 0
        self._max_active_tasks = 2  # 最多同时运行2个任务

        # 缓存外部服务实例，避免重复创建
        self._trading_controller_cache = None
        self._data_manager_cache = None

        # 设置合理的最小窗口尺寸，确保窗口可以缩放
        self.setMinimumSize(1000, 600)

        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 设置objectName，用于样式选择器
        self.setObjectName("main_window")

        # 智能洞察面板（如果可用）
        if self._has_smart_monitoring:
            # 智能性能洞察功能已删除 - 与监控中心功能重叠
            pass

        # 主要内容标签页
        self.tab_widget = self._create_modern_tabs()
        layout.addWidget(self.tab_widget, 1)

        # 现代化状态栏
        self.status_bar = self._create_modern_status_bar()
        layout.addWidget(self.status_bar)

        # 应用现代化样式
        # self._apply_modern_styling()

    def _create_modern_tabs(self):
        """创建现代化标签页"""
        tab_widget = QTabWidget()

        # 添加tab切换监听
        tab_widget.currentChanged.connect(self.on_tab_changed)

        # tab_widget.setStyleSheet("""
        #     QTabWidget::pane {
        #         border: 1px solid #34495e;
        #         background: #2c3e50;
        #         border-radius: 0px 0px 6px 6px;
        #     }
        #     QTabBar::tab {
        #         background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        #             stop: 0 #34495e, stop: 1 #2c3e50);
        #         border: 1px solid #34495e;
        #         border-bottom: none;
        #         border-top-left-radius: 6px;
        #         border-top-right-radius: 6px;
        #         min-width: 25px;
        #         padding: 12px 20px;
        #         margin-right: 2px;
        #         color: #bdc3c7;
        #         font-weight: 500;
        #         font-size: 12px;
        #         height: 11px;
        #     }
        #     QTabBar::tab:selected {
        #         background: #2c3e50;
        #         border-bottom: 1px solid #3498db;
        #         color: #ecf0f1;
        #         font-weight: bold;
        #     }
        #     QTabBar::tab:hover:!selected {
        #         background: #2c3e50;
        #         color: #ecf0f1;
        #     }
        # """)

        # 延迟导入标签页组件
        _import_tabs()

        # 1. 系统监控 - 基础设施监控
        self.system_tab = _ModernSystemMonitorTab()
        tab_widget.addTab(self.system_tab, "🖥️ 系统监控")

        # 2. 策略性能 - 量化策略核心指标
        self.strategy_tab = _ModernStrategyPerformanceTab()
        tab_widget.addTab(self.strategy_tab, "策略性能")

        # 3. 算法优化 - 合并算法性能和自动调优
        self.algorithm_optimization_tab = _ModernAlgorithmOptimizationTab()
        tab_widget.addTab(self.algorithm_optimization_tab, "算法优化")

        # 4. 风险控制中心 - 升级版告警配置，专注风险管理
        self.risk_control_tab = _ModernRiskControlCenterTab()
        tab_widget.addTab(self.risk_control_tab, "🛡️ 风险控制")

        # 5. 交易执行监控 - 量化交易专用，监控执行质量
        self.execution_monitor_tab = _ModernTradingExecutionMonitorTab()
        tab_widget.addTab(self.execution_monitor_tab, "执行监控")

        # 6. 数据质量监控 - 量化交易数据质量保障
        # 从服务容器获取数据质量相关服务
        quality_monitor = None
        report_generator = None
        try:
            from core.containers import get_service_container
            from core.services.enhanced_data_quality_monitor import EnhancedDataQualityMonitor
            from core.services.quality_report_generator import QualityReportGenerator

            service_container = get_service_container()
            if service_container.is_registered(EnhancedDataQualityMonitor):
                quality_monitor = service_container.resolve(EnhancedDataQualityMonitor)
                logger.info("成功获取 EnhancedDataQualityMonitor 实例")
            else:
                logger.warning("EnhancedDataQualityMonitor 未注册")

            if service_container.is_registered(QualityReportGenerator):
                report_generator = service_container.resolve(QualityReportGenerator)
                logger.info("成功获取 QualityReportGenerator 实例")
            else:
                logger.warning("QualityReportGenerator 未注册")
        except Exception as e:
            logger.error(f"获取数据质量服务失败: {e}")

        self.data_quality_tab = _DataQualityMonitorTab(
            quality_monitor=quality_monitor,
            report_generator=report_generator
        )
        tab_widget.addTab(self.data_quality_tab, "数据质量")

        return tab_widget

    def _create_modern_status_bar(self):
        """创建现代化状态栏"""
        status_bar = QStatusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #34495e, stop: 1 #2c3e50);
                border-top: 1px solid #1a252f;
                color: #bdc3c7;
                font-size: 10px;
                padding: 4px;
            }
            QStatusBar::item {
                border: none;
            }
        """)

        self.status_message = QLabel("就绪")
        status_bar.addWidget(self.status_message)

        status_bar.addPermanentWidget(QLabel("｜"))

        self.data_update_time = QLabel("数据更新: " +
                                       QDateTime.currentDateTime().toString("hh:mm:ss"))
        status_bar.addPermanentWidget(self.data_update_time)

        return status_bar

    def _apply_modern_styling(self):
        """应用现代化样式主题"""
        try:
            stylesheet = """
                #main_window {
                    font-family: Segoe UI, Microsoft YaHei UI, sans-serif;
                    font-size: 12px;
                    background: #2c3e50;
                    color: #ecf0f1;
                }
                #main_window QScrollArea {
                    border: none;
                    background: transparent;
                }
            """
            self.setStyleSheet(stylesheet)
            logger.info(f"样式表已应用，长度: {len(stylesheet)}")
            
            # 确保样式表保护机制使用最新的样式表
            if hasattr(self, '_original_stylesheet'):
                self._original_stylesheet = self.styleSheet()
                logger.debug("样式表保护机制已更新最新的样式表")
        except Exception as e:
            logger.error(f"应用样式表失败: {e}")
            logger.warning("将使用默认样式")

    def setup_timer(self):
        """设置定时刷新 - 优化更新策略"""
        # 延迟启动定时器，确保组件完全初始化
        QTimer.singleShot(3000, self._start_refresh_timer)  # 3秒后启动刷新定时器
        QTimer.singleShot(3000, self._start_drag_detect_timer)  # 3秒后启动拖动检测定时器
        QTimer.singleShot(10000, self._start_cleanup_timer)  # 从5秒改为10秒，延迟启动清理定时器  # 5秒后启动定期清理定时器
        # 延迟启动标签页的定时器，确保UI完全准备好
        QTimer.singleShot(3000, self._start_tab_timers)  # 3秒后启动标签页定时器
        logger.debug("定时器已安排延迟启动")

    def _start_cleanup_timer(self):
        """启动定期清理定时器"""
        try:
            if hasattr(self, '_cleanup_timer') and self._cleanup_timer is not None:
                if self._cleanup_timer.isActive():
                    self._cleanup_timer.stop()
                self._cleanup_timer.deleteLater()
            
            self._cleanup_timer = QTimer(self)
            self._cleanup_timer.timeout.connect(self._periodic_cleanup)
            self._cleanup_timer.start(30000)  # 每30秒清理一次
            logger.info("定期清理定时器已启动（30秒间隔）")
        except Exception as e:
            logger.error(f"启动清理定时器失败: {e}")

    def _start_tab_timers(self):
        """启动所有标签页的定时器 - 确保UI完全准备好后再启动"""
        try:
            # 启动系统监控标签页的定时器
            if hasattr(self, 'system_tab') and hasattr(self.system_tab, 'monitoring_timer'):
                if not self.system_tab.monitoring_timer.isActive():
                    self.system_tab.monitoring_timer.start(1000)  # 每秒更新一次
                    logger.info("系统监控标签页定时器已启动")

            # 启动算法优化标签页的定时器
            if hasattr(self, 'algorithm_optimization_tab') and hasattr(self.algorithm_optimization_tab, 'jit_monitoring_timer'):
                if not self.algorithm_optimization_tab.jit_monitoring_timer.isActive():
                    self.algorithm_optimization_tab.jit_monitoring_timer.start(2000)  # 每2秒更新一次
                    logger.info("算法优化标签页定时器已启动")

            # 启动风险控制中心标签页的定时器
            if hasattr(self, 'risk_control_tab') and hasattr(self.risk_control_tab, 'enhanced_risk_monitor'):
                if self.risk_control_tab.enhanced_risk_monitor:
                    self.risk_control_tab.start_enhanced_monitoring()
                    logger.info("风险控制中心标签页定时器已启动")

            logger.info("所有标签页定时器已启动")
        except Exception as e:
            logger.error(f"启动标签页定时器失败: {e}")

    def _periodic_cleanup(self):
        """定期清理累积的资源 - 防止内存泄漏"""
        try:
            # 清理过期的缓存数据（保留最新的20个）
            if len(self._data_cache) > 20:
                keys_to_remove = list(self._data_cache.keys())[:len(self._data_cache) - 20]
                for key in keys_to_remove:
                    del self._data_cache[key]
                logger.debug(f"已清理过期缓存，剩余: {len(self._data_cache)}")

            # 清理过多的信号槽连接（保留最近的100个，从50增加到100）
            if len(self._signal_connections) > 100:
                connections_to_remove = self._signal_connections[:len(self._signal_connections) - 100]
                removed_count = 0
                for conn in connections_to_remove:
                    try:
                        if hasattr(conn, 'disconnect') and not isinstance(conn, type(None)):
                            conn.disconnect()
                            removed_count += 1
                    except Exception as e:
                        logger.debug(f"断开信号槽连接失败: {e}")
                self._signal_connections = self._signal_connections[-100:]
                logger.debug(f"已清理信号槽连接（{removed_count}个），剩余: {len(self._signal_connections)}")

            # 检查活跃任务数量是否异常
            if self._active_task_count > self._max_active_tasks * 2:
                logger.warning(f"活跃任务数量异常: {self._active_task_count}，重置为0")
                self._active_task_count = 0

            # 内存使用监控和保护
            self._check_memory_usage()

        except Exception as e:
            logger.error(f"定期清理失败: {e}")

    def _check_memory_usage(self):
        """检查内存使用情况 - 防止内存泄漏导致崩溃"""
        try:
            import time
            start_time = time.time()
            
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)

            # 记录内存使用情况
            if not hasattr(self, '_memory_usage_history'):
                self._memory_usage_history = []

            self._memory_usage_history.append(memory_mb)
            if len(self._memory_usage_history) > 10:
                self._memory_usage_history.pop(0)

            # 如果内存使用超过阈值，执行紧急清理
            memory_threshold_mb = 8000  # 8GB阈值
            if memory_mb > memory_threshold_mb:
                logger.warning(f"内存使用过高 ({memory_mb:.1f}MB)，执行紧急清理")

                # 强制清理所有缓存
                self._data_cache.clear()
                self._last_update_time.clear()

                # 强制清理信号槽连接
                if hasattr(self, '_signal_connections'):
                    for conn in self._signal_connections:
                        try:
                            if hasattr(conn, 'disconnect'):
                                conn.disconnect()
                        except Exception:
                            pass
                    self._signal_connections.clear()

                # 重置活跃任务计数
                self._active_task_count = 0

                logger.warning(f"紧急清理完成，当前内存: {memory_mb:.1f}MB")

            # 记录内存趋势
            if len(self._memory_usage_history) >= 3:
                avg_memory = sum(self._memory_usage_history) / len(self._memory_usage_history)
                if memory_mb > avg_memory * 1.5:
                    logger.warning(f"内存使用异常增长: 当前 {memory_mb:.1f}MB, 平均 {avg_memory:.1f}MB")
            
            # 记录执行时间
            execution_time = time.time() - start_time
            if execution_time > 0.1:  # 超过100ms记录警告
                logger.warning(f"_check_memory_usage 执行时间: {execution_time:.3f}秒")

        except ImportError:
            # psutil 不可用时跳过内存监控
            pass
        except Exception as e:
            logger.debug(f"内存检查失败: {e}")

    def _start_refresh_timer(self):
        """启动刷新定时器"""
        try:
            if hasattr(self, 'refresh_timer') and self.refresh_timer is not None:
                if self.refresh_timer.isActive():
                    self.refresh_timer.stop()
                self.refresh_timer.deleteLater()
            
            self.refresh_timer = QTimer(self)  # 设置父对象
            self.refresh_timer.timeout.connect(self.update_current_tab_data_async)  # 异步更新当前tab
            self.refresh_timer.start(5000)  # 改为5秒刷新一次，减少系统负载
            logger.info("刷新定时器已启动（5秒间隔）")
        except Exception as e:
            logger.error(f"启动刷新定时器失败: {e}")

    def _start_drag_detect_timer(self):
        """启动拖动检测定时器"""
        try:
            if hasattr(self, 'drag_detect_timer') and self.drag_detect_timer is not None:
                if self.drag_detect_timer.isActive():
                    self.drag_detect_timer.stop()
                self.drag_detect_timer.deleteLater()
            
            self.drag_detect_timer = QTimer(self)  # 设置父对象
            self.drag_detect_timer.timeout.connect(self._check_drag_state)
            self.drag_detect_timer.start(1000)  # 从500ms改为1000ms，减少系统负载
            logger.info("拖动检测定时器已启动（1秒间隔）")
        except Exception as e:
            logger.error(f"启动拖动检测定时器失败: {e}")

    def update_current_tab_data_async(self):
        """异步更新当前显示的tab数据 - 优化版本，添加超时控制"""
        import time
        start_time = time.time()
        
        try:
            # 如果正在拖动，跳过更新
            if self._update_paused or self._is_dragging:
                return

            # 使用计数器降频更新
            self._update_counter += 1
            if self._update_counter % 2 != 0:  # 每2次调用才真正更新一次
                return

            # 添加超时控制，如果执行时间超过1秒，跳过本次更新
            if time.time() - start_time > 1.0:
                logger.warning(f"update_current_tab_data_async 执行时间过长，跳过本次更新")
                return

            current_time = QDateTime.currentDateTime()

            # 根据当前tab索引更新对应数据
            if self.current_tab_index == 0:  # 系统监控
                self._update_system_monitor_tab(current_time)
            elif self.current_tab_index == 1:  # 策略性能
                self._update_strategy_performance_tab(current_time)
            elif self.current_tab_index == 2:  # 算法优化
                self._update_algorithm_optimization_tab(current_time)
            elif self.current_tab_index == 3:  # 风险控制
                self._update_risk_control_tab(current_time)
            elif self.current_tab_index == 4:  # 交易执行监控
                self._update_execution_monitor_tab(current_time)
            elif self.current_tab_index == 5:  # 数据质量监控
                self._update_data_quality_tab(current_time)
            # 健康检查标签页 (index 6) - 按需检查，不需要定时更新

            # 更新状态栏时间
            self.data_update_time.setText("数据更新: " + current_time.toString("hh:mm:ss"))

            # 记录执行时间
            execution_time = time.time() - start_time
            if execution_time > 0.5:
                logger.warning(f"update_current_tab_data_async 执行时间: {execution_time:.3f}秒")

        except Exception as e:
            logger.error(f"异步更新当前tab数据失败: {e}")

    def _update_system_monitor_tab(self, current_time):
        """更新系统监控标签页"""
        try:
            if not hasattr(self, 'system_tab') or not hasattr(self, 'monitor'):
                logger.warning("系统监控组件未初始化，跳过更新")
                return
            
            cache_key = 'system_metrics'
            if self._should_update_cache(cache_key, 3):  # 3秒缓存
                try:
                    system_metrics = self.monitor.system_monitor.collect_metrics()
                    if system_metrics:
                        mapped_metrics = {
                            "CPU使用率": system_metrics.get('cpu_usage', 0),
                            "内存使用率": system_metrics.get('memory_usage', 0),
                            "磁盘使用率": system_metrics.get('disk_usage', 0),
                            "网络吞吐": system_metrics.get('网络吞吐', 0),
                            "进程数量": system_metrics.get('进程数量', 0),
                            "线程数量": system_metrics.get('线程数量', 0),
                            "句柄数量": system_metrics.get('句柄数量', 0),
                            "响应时间": system_metrics.get('响应时间', 0),
                            "内存可用": system_metrics.get('memory_available', 0),
                            "磁盘可用": system_metrics.get('disk_free', 0),
                            "网络发送": system_metrics.get('network_bytes_sent', 0) / (1024**2),
                            "网络接收": system_metrics.get('network_bytes_recv', 0) / (1024**2),
                        }
                        self._data_cache[cache_key] = mapped_metrics
                        self._last_update_time[cache_key] = current_time
                        if hasattr(self, 'system_tab'):
                            self.system_tab.update_data(mapped_metrics)
                except Exception as e:
                    logger.error(f"异步更新系统监控数据失败: {e}")
            else:
                cached_data = self._data_cache.get(cache_key, {})
                if cached_data and hasattr(self, 'system_tab'):
                    self.system_tab.update_data(cached_data)
        except Exception as e:
            logger.error(f"更新系统监控标签页失败: {e}")

    def _update_strategy_performance_tab(self, current_time):
        """更新策略性能标签页"""
        try:
            if not hasattr(self, 'strategy_tab') or not hasattr(self, 'monitor'):
                logger.warning("策略性能组件未初始化，跳过更新")
                return
            
            cache_key = 'strategy_performance'
            if self._should_update_cache(cache_key, 5):  # 5秒缓存
                if self._active_task_count >= self._max_active_tasks:
                    logger.warning(f"活跃任务数量过多 ({self._active_task_count})，跳过本次更新")
                    return

                try:
                    _import_async_workers()
                    worker = _AsyncStrategyWorker(self.monitor, self.strategy_tab)
                    strategy_callback = StrategyDataCallback(self, cache_key, current_time)
                    counter_callback = TaskCounterCallback(self)
                    connection1 = worker.signals.data_ready.connect(strategy_callback.on_data_ready)
                    connection2 = worker.signals.finished.connect(strategy_callback.on_finished)
                    connection3 = worker.signals.finished.connect(counter_callback.on_task_done)
                    connection4 = worker.signals.error_occurred.connect(self._handle_async_error)
                    new_connections = [connection1, connection2, connection3, connection4]

                    max_connections = 500
                    if len(self._signal_connections) >= max_connections:
                        connections_to_remove = self._signal_connections[:len(new_connections)]
                        for conn in connections_to_remove:
                            try:
                                if hasattr(conn, 'disconnect'):
                                    conn.disconnect()
                            except Exception as e:
                                logger.debug(f"断开旧连接失败: {e}")
                        self._signal_connections = self._signal_connections[len(new_connections):]
                        logger.debug(f"已清理过期的信号槽连接，当前数量: {len(self._signal_connections)}")

                    self._signal_connections.extend(new_connections)
                    self._active_task_count += 1
                    self.thread_pool.start(worker)
                except Exception as e:
                    logger.error(f"启动策略性能更新任务失败: {e}")
        except Exception as e:
            logger.error(f"更新策略性能标签页失败: {e}")

    def _update_algorithm_optimization_tab(self, current_time):
        """更新算法优化标签页"""
        try:
            if not hasattr(self, 'algorithm_optimization_tab'):
                logger.warning("算法优化组件未初始化，跳过更新")
                return
            
            cache_key = 'algo_stats'
            if self._should_update_cache(cache_key, 5):  # 5秒缓存
                try:
                    from analysis.pattern_recognition import get_performance_monitor as get_pattern_monitor
                    pattern_monitor = get_pattern_monitor()

                    algo_stats = {}
                    if hasattr(pattern_monitor, 'get_performance_summary'):
                        perf_summary = pattern_monitor.get_performance_summary()
                        algo_stats.update({
                            '计算速度': perf_summary.get('recent_avg_time', 0) * 1000,
                            '准确率': perf_summary.get('recent_success_rate', 0) * 100,
                            '吞吐量': perf_summary.get('total_recognitions', 0),
                            '内存使用': perf_summary.get('memory_usage_mb', 0),
                            '缓存命中率': perf_summary.get('cache_hit_rate', 0) * 100,
                            '错误率': (1 - perf_summary.get('recent_success_rate', 1)) * 100,
                            '平均延迟': perf_summary.get('recent_avg_time', 0) * 1000,
                            '并发处理': 1
                        })
                    else:
                        algo_stats = {
                            '计算速度': 0.0,
                            '准确率': 0.5,
                            '吞吐量': 0,
                            '内存使用': 0,
                            '缓存命中率': 0,
                            '错误率': 0,
                            '平均延迟': 0,
                            '并发处理': 0
                        }

                    combined_data = {
                        'performance_metrics': algo_stats,
                        'tuning_metrics': {
                            '调优进度': 0,
                            '性能提升': 0,
                            '参数空间': 0,
                            '收敛速度': 0,
                            '最优解质量': 0,
                            '迭代次数': 0,
                            '稳定性': 0,
                            '调优效率': 0
                        },
                        'benchmark_metrics': {
                            '当前性能': algo_stats.get('计算速度', 0),
                            '基准性能': 100.0,
                            '性能比率': algo_stats.get('计算速度', 0) / 100.0 * 100,
                            '排名百分位': 75.0,
                            '改进空间': max(0, 100 - algo_stats.get('计算速度', 0)),
                            '稳定性评分': algo_stats.get('缓存命中率', 0),
                            '效率评级': algo_stats.get('准确率', 0),
                            '综合评分': (algo_stats.get('准确率', 0) + algo_stats.get('缓存命中率', 0)) / 2
                        }
                    }

                    self._data_cache[cache_key] = combined_data
                    self.algorithm_optimization_tab.update_data(combined_data)
                    logger.debug(f"算法优化数据已刷新: 计算速度={algo_stats.get('计算速度', 0):.1f}ms")

                except Exception as e:
                    logger.error(f"获取算法优化数据失败: {e}")
                    default_data = {
                        'performance_metrics': {
                            '执行时间': 0, '计算准确率': 0, '内存效率': 0, '并发度': 0,
                            '错误率': 0, '吞吐量': 0, '缓存效率': 0, '算法复杂度': 0
                        },
                        'tuning_metrics': {
                            '调优进度': 0, '性能提升': 0, '参数空间': 0, '收敛速度': 0,
                            '最优解质量': 0, '迭代次数': 0, '稳定性': 0, '调优效率': 0
                        },
                        'benchmark_metrics': {
                            '当前性能': 0, '基准性能': 0, '性能比率': 0, '排名百分位': 0,
                            '改进空间': 0, '稳定性评分': 0, '效率评级': 0, '综合评分': 0
                        }
                    }
                    self._data_cache[cache_key] = default_data
                    self.algorithm_optimization_tab.update_data(default_data)

                self._last_update_time[cache_key] = current_time
            else:
                cached_data = self._data_cache.get(cache_key, {})
                if cached_data:
                    self.algorithm_optimization_tab.update_data(cached_data)
        except Exception as e:
            logger.error(f"更新算法优化标签页失败: {e}")

    def _update_risk_control_tab(self, current_time):
        """更新风险控制标签页"""
        try:
            if not hasattr(self, 'risk_control_tab'):
                logger.warning("风险控制组件未初始化，跳过更新")
                return
            
            cache_key = 'risk_metrics'
            if self._should_update_cache(cache_key, 3):  # 3秒缓存
                try:
                    from core.risk_manager import RiskManager

                    risk_metrics = {}

                    # R268-F2: 原 `risk_manager = None` 使 `if risk_manager.initialized:`
                    # 必然 AttributeError → 异常被吞 → 风控面板恒全 0 占位。
                    # 改用真实 RiskManager 实例 (构造轻量, initialize 加载风险参数)。
                    risk_manager = RiskManager()
                    if risk_manager.initialize():
                        current_positions = getattr(risk_manager, 'current_positions', {})
                        current_equity = getattr(risk_manager, 'current_equity', 0)
                        peak_equity = getattr(risk_manager, 'peak_equity', 0)

                        if current_equity > 0 and peak_equity > 0:
                            drawdown = (peak_equity - current_equity) / peak_equity * 100
                            risk_metrics['最大回撤'] = drawdown
                            risk_metrics['仓位风险'] = sum(current_positions.values()) * 100 if current_positions else 0

                    # R268-F2: 移除 `prof_risk = ProfessionalRiskMetrics()` 实例化后从未使用的死代码

                    if not risk_metrics:
                        risk_metrics = {
                            'VaR(95%)': 0.0,
                            '最大回撤': 0.0,
                            '波动率': 0.0,
                            'Beta系数': 0.0,
                            '夏普比率': 0.0,
                            '仓位风险': 0.0,
                            '市场风险': 0.0,
                            '行业风险': 0.0,
                            '流动性风险': 0.0,
                            '信用风险': 0.0,
                            '操作风险': 0.0,
                            '集中度风险': 0.0
                        }

                    self._data_cache[cache_key] = {'risk_metrics': risk_metrics}
                    self.risk_control_tab.update_data({'risk_metrics': risk_metrics})
                    logger.debug(f"风险控制数据已刷新: VaR={risk_metrics.get('VaR(95%)', 0):.2f}%")

                except Exception as e:
                    logger.error(f"获取风险控制数据失败: {e}")
                    default_risk = {
                        'VaR(95%)': 0, '最大回撤': 0, '波动率': 0, 'Beta系数': 0,
                        '夏普比率': 0, '仓位风险': 0, '市场风险': 0, '行业风险': 0,
                        '流动性风险': 0, '信用风险': 0, '操作风险': 0, '集中度风险': 0
                    }
                    self._data_cache[cache_key] = {'risk_metrics': default_risk}
                    self.risk_control_tab.update_data({'risk_metrics': default_risk})

                self._last_update_time[cache_key] = current_time
            else:
                cached_data = self._data_cache.get(cache_key, {})
                if cached_data:
                    self.risk_control_tab.update_data(cached_data)
        except Exception as e:
            logger.error(f"更新风险控制标签页失败: {e}")

    def _update_execution_monitor_tab(self, current_time):
        """更新交易执行监控标签页"""
        try:
            if not hasattr(self, 'execution_monitor_tab'):
                logger.warning("交易执行监控组件未初始化，跳过更新")
                return
            
            cache_key = 'execution_metrics'
            if self._should_update_cache(cache_key, 2):  # 2秒缓存
                try:
                    if self._trading_controller_cache is None:
                        from core.trading_controller import TradingController
                        from core.containers import get_service_container
                        self._trading_controller_cache = TradingController(get_service_container())
                        logger.info("TradingController 实例已缓存")

                    execution_metrics = {}

                    try:
                        if hasattr(self._trading_controller_cache, 'get_execution_stats'):
                            exec_stats = self._trading_controller_cache.get_execution_stats()
                            execution_metrics.update(exec_stats)
                    except Exception as e:
                        logger.debug(f"交易控制器数据获取失败: {e}")

                    try:
                        trading_manager = None
                        if hasattr(trading_manager, 'get_performance_metrics'):
                            perf_metrics = trading_manager.get_performance_metrics()
                            execution_metrics.update(perf_metrics)
                    except Exception as e:
                        logger.debug(f"交易管理器数据获取失败: {e}")

                    try:
                        from db.complete_database_init import CompleteDatabaseInitializer
                        db_init = CompleteDatabaseInitializer()
                    except Exception as e:
                        logger.debug(f"数据库执行数据获取失败: {e}")

                    if not execution_metrics:
                        execution_metrics = {
                            '平均延迟': 0.0,
                            '成交率': 0.0,
                            '平均滑点': 0.0,
                            '交易成本': 0.0,
                            '市场冲击': 0.0,
                            '执行效率': 0.0,
                            '订单完成率': 0.0,
                            '部分成交率': 0.0,
                            '撤单率': 0.0,
                            'TWAP偏差': 0.0,
                            'VWAP偏差': 0.0,
                            '实施缺口': 0.0
                        }

                    self._data_cache[cache_key] = {'execution_metrics': execution_metrics}
                    self.execution_monitor_tab.update_data({'execution_metrics': execution_metrics})
                    logger.debug(f"交易执行数据已刷新: 成交率={execution_metrics.get('成交率', 0):.1f}%")

                except Exception as e:
                    logger.error(f"获取交易执行数据失败: {e}")

                self._last_update_time[cache_key] = current_time
            else:
                cached_data = self._data_cache.get(cache_key, {})
                if cached_data:
                    self.execution_monitor_tab.update_data(cached_data)
        except Exception as e:
            logger.error(f"更新交易执行监控标签页失败: {e}")

    def _update_data_quality_tab(self, current_time):
        """更新数据质量监控标签页"""
        try:
            cache_key = 'quality_metrics'
            if self._should_update_cache(cache_key, 5):  # 5秒缓存
                try:
                    if self._data_manager_cache is None:
                        from core.services.unified_data_manager import get_unified_data_manager
                        self._data_manager_cache = get_unified_data_manager()
                        logger.info("UnifiedDataManager 实例已缓存")

                    from core.data_source_extensions import HealthCheckResult
                    logger.info("开始获取数据质量指标...")
                    quality_metrics = {}

                    try:
                        data_manager = self._data_manager_cache
                        logger.info(f"数据管理器已获取: {data_manager is not None}")

                        available_sources = data_manager.get_available_data_source_names() if data_manager else []
                        logger.info(f"可用数据源: {available_sources}")

                        if available_sources:
                            total_sources = len(available_sources)
                            connected_sources = total_sources
                            logger.info(f"已连接数据源: {connected_sources}/{total_sources}")
                            if total_sources > 0:
                                quality_metrics['consistency'] = (connected_sources / total_sources) * 0.95
                        else:
                            logger.warning("没有可用数据源")

                        if hasattr(data_manager, 'cache_manager') and data_manager.cache_manager:
                            cache_stats = data_manager.cache_manager.get_statistics()
                            logger.info(f"缓存统计信息: {cache_stats}")
                            if cache_stats:
                                utilization = cache_stats.get('utilization', 0)
                                quality_metrics['uniqueness'] = utilization
                        else:
                            try:
                                from core.containers import get_service_container
                                from core.services.cache_service import CacheService
                                container = get_service_container()
                                if container and container.is_registered(CacheService):
                                    cache_service = container.resolve(CacheService)
                                    if cache_service:
                                        stats = cache_service.get_statistics()
                                        quality_metrics['uniqueness'] = stats.get('utilization', 0.95)
                                        logger.info(f"从CacheService获取缓存统计: {stats}")
                            except Exception as cs_err:
                                logger.warning(f"获取CacheService失败: {cs_err}")
                                quality_metrics['uniqueness'] = 0.95

                    except Exception as e:
                        logger.error(f"统一数据管理器质量数据获取失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

                    try:
                        from core.containers import get_service_container
                        from core.services.unified_data_manager import UnifiedDataManager

                        container = get_service_container()
                        if container and container.is_registered(UnifiedDataManager):
                            unified_data_manager = container.resolve(UnifiedDataManager)
                            uni_plugin_manager = unified_data_manager.get_uni_plugin_manager()

                            if uni_plugin_manager:
                                logger.info(f"插件管理器已获取: {uni_plugin_manager is not None}")

                                plugin_status = uni_plugin_manager.get_plugin_status()
                                logger.info(f"插件状态: {plugin_status}")

                                plugin_center_stats = plugin_status.get('plugin_center', {})
                                tet_engine_stats = plugin_status.get('tet_engine', {})

                                total_plugins = plugin_center_stats.get('total_plugins', 0)
                                active_plugins = plugin_center_stats.get('active_plugins', 0)

                                logger.info(f"插件总数: {total_plugins}, 活跃插件: {active_plugins}")

                                if total_plugins > 0:
                                    healthy_count = active_plugins
                                    total_count = total_plugins
                                    logger.info(f"健康插件数: {healthy_count}/{total_count}")
                                    if total_count > 0:
                                        quality_metrics['completeness'] = (healthy_count / total_count) * 0.95
                                        quality_metrics['accuracy'] = (healthy_count / total_count) * 0.97
                                        quality_metrics['timeliness'] = (healthy_count / total_count) * 0.90
                                else:
                                    logger.warning("没有插件状态数据")
                            else:
                                logger.warning("UniPluginDataManager实例为None")
                        else:
                            logger.warning("UnifiedDataManager未在服务容器中注册")

                    except Exception as e:
                        logger.error(f"FactorWeave-Quant插件质量数据获取失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

                    try:
                        from core.containers import get_service_container
                        from core.services.database_service import DatabaseService

                        container = get_service_container()
                        if container and container.is_registered(DatabaseService):
                            db_service = container.resolve(DatabaseService)
                            if db_service:
                                stats = db_service.get_data_source_stats()
                                if stats and stats.get('total', 0) > 0:
                                    quality_metrics['validity'] = stats.get('active_rate', 0.0)
                                    logger.info(f"从DatabaseService获取数据源统计: {stats}")
                                else:
                                    logger.debug("数据库中没有数据源数据，使用默认值")
                                    quality_metrics['validity'] = 0
                            else:
                                logger.debug("DatabaseService实例为None，使用默认值")
                                quality_metrics['validity'] = 0
                        else:
                            logger.warning("DatabaseService未在服务容器中注册，使用默认值")
                            quality_metrics['validity'] = 0

                    except Exception as e:
                        logger.error(f"DatabaseService数据获取失败: {e}")
                        quality_metrics['validity'] = 0

                    if not quality_metrics:
                        logger.warning("未获取到任何质量数据，使用默认值")
                        logger.debug(f"数据管理器健康状态: {getattr(data_manager, '_health_status', {})}")
                        logger.debug(f"缓存管理器: {hasattr(data_manager, 'cache_manager')}")
                        quality_metrics = {
                            'completeness': 0,
                            'accuracy': 0,
                            'timeliness': 0,
                            'consistency': 0,
                            'validity': 0,
                            'uniqueness': 0
                        }

                    required_metrics = ['completeness', 'accuracy', 'timeliness', 'consistency', 'validity', 'uniqueness']
                    for metric in required_metrics:
                        if metric not in quality_metrics:
                            logger.warning(f"缺少质量指标: {metric}，使用默认值")
                            quality_metrics[metric] = 0

                    self._data_cache[cache_key] = {'quality_metrics': quality_metrics}
                    self.data_quality_tab.update_data({'quality_metrics': quality_metrics})
                    logger.debug(f"数据质量数据已刷新: 完整性={quality_metrics.get('completeness', 0):.1f}%")

                except Exception as e:
                    logger.error(f"获取数据质量数据失败: {e}")

                self._last_update_time[cache_key] = current_time
            else:
                cached_data = self._data_cache.get(cache_key, {})
                if cached_data:
                    self.data_quality_tab.update_data(cached_data)
        except Exception as e:
            logger.error(f"更新数据质量监控标签页失败: {e}")

    def _on_strategy_data_received(self, data: dict, cache_key: str, current_time):
        """ 线程安全修复：在主线程中处理策略数据并更新UI"""
        try:
            if data and 'monitor' in data:
                # 在主线程中安全地更新UI
                monitor = data['monitor']
                if hasattr(self, 'strategy_tab') and self.strategy_tab:
                    # 确保在主线程中调用UI更新
                    self.strategy_tab.update_data(monitor)
                    logger.debug("策略性能UI更新完成（主线程）")
                else:
                    logger.warning("策略标签页不存在，跳过UI更新")
            else:
                logger.debug("收到空的策略数据，跳过UI更新")

            self._last_update_time[cache_key] = current_time

        except Exception as e:
            logger.error(f"处理策略数据失败: {e}")
            # 确保UI状态一致性
            try:
                if hasattr(self, 'strategy_tab') and self.strategy_tab:
                    # 在出错时也要确保UI状态正确
                    pass
            except Exception:
                pass

    def _on_strategy_calculation_finished(self, cache_key: str, current_time):
        """策略计算完成的回调"""
        try:
            logger.debug("策略性能异步计算完成")
        except Exception as e:
            logger.error(f"处理策略计算完成回调失败: {e}")

    def _on_strategy_data_ready(self, cache_key: str, current_time):
        """策略数据异步计算完成的回调（保留兼容性）"""
        try:
            self._last_update_time[cache_key] = current_time
            logger.debug("策略性能数据异步更新完成")
        except Exception as e:
            logger.error(f"处理策略数据完成回调失败: {e}")

    def _check_drag_state(self):
        """检测拖动状态"""
        import time
        start_time = time.time()
        
        current_time = time.time()

        # 如果最近有鼠标移动，认为在拖动
        if current_time - self._last_mouse_move_time < 0.5:  # 500ms内有鼠标移动
            if not self._is_dragging:
                self._is_dragging = True
                self._update_paused = True
                logger.debug("检测到拖动，暂停更新")
        else:
            if self._is_dragging:
                self._is_dragging = False
                self._update_paused = False
                logger.debug("拖动结束，恢复更新")
        
        # 记录执行时间
        execution_time = time.time() - start_time
        if execution_time > 0.01:  # 超过10ms记录警告
            logger.warning(f"_check_drag_state 执行时间: {execution_time:.3f}秒")

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 用于检测拖动"""
        import time
        self._last_mouse_move_time = time.time()
        super().mouseMoveEvent(event)

    def resizeEvent(self, event):
        """窗口大小变化事件 - 暂停更新避免卡顿"""
        self._update_paused = True
        # 延迟恢复更新
        QTimer.singleShot(500, self._resume_updates)
        super().resizeEvent(event)

    def _resume_updates(self):
        """恢复更新"""
        self._update_paused = False

    @pyqtSlot(dict)
    def _handle_async_data(self, data):
        """处理异步获取的数据"""
        try:
            if 'system_metrics' in data:
                cache_key = 'system_metrics'
                self._data_cache[cache_key] = data['system_metrics']
                if self.current_tab_index == 0:  # 只在当前显示系统监控tab时更新UI
                    self.system_tab.update_data(data['system_metrics'])

            elif 'algo_optimization_data' in data:
                cache_key = 'algo_stats'
                self._data_cache[cache_key] = data['algo_optimization_data']
                if self.current_tab_index == 2:  # 算法优化tab (新索引2)
                    self.algorithm_optimization_tab.update_data(data['algo_optimization_data'])

            elif 'risk_metrics' in data:
                cache_key = 'risk_metrics'
                self._data_cache[cache_key] = data
                if self.current_tab_index == 3:  # 风险控制tab (新索引3)
                    self.risk_control_tab.update_data(data)

            elif 'execution_metrics' in data:
                cache_key = 'execution_metrics'
                self._data_cache[cache_key] = data
                if self.current_tab_index == 4:  # 交易执行监控tab (新索引4)
                    self.execution_monitor_tab.update_data(data)

            elif 'quality_metrics' in data:
                cache_key = 'quality_metrics'
                self._data_cache[cache_key] = data
                if self.current_tab_index == 5:  # 数据质量监控tab (新索引5)
                    self.data_quality_tab.update_data(data)

            logger.debug(f" 异步数据处理完成: {data}")

        except Exception as e:
            logger.error(f"处理异步数据失败 ({data}): {e}")

    @pyqtSlot(str)
    def _handle_async_error(self, error_message):
        """处理异步数据获取错误"""
        logger.warning(f" 异步数据获取失败: {error_message}")

    def _should_update_cache(self, cache_key: str, cache_duration_seconds: int) -> bool:
        """检查是否需要更新缓存"""
        if cache_key not in self._last_update_time:
            return True

        last_update = self._last_update_time[cache_key]
        current_time = QDateTime.currentDateTime()

        return last_update.secsTo(current_time) >= cache_duration_seconds

    def update_all_data(self):
        """更新所有数据"""
        # 清空缓存强制更新
        self._data_cache.clear()
        self._last_update_time.clear()
        self.update_current_tab_data_async()

    @pyqtSlot()
    def clear_data(self):
        """清空数据"""
        try:
            if hasattr(self.strategy_tab, 'returns_chart') and self.strategy_tab.returns_chart:
                self.strategy_tab.returns_chart.clear_data()
            if hasattr(self.strategy_tab, 'risk_chart') and self.strategy_tab.risk_chart:
                self.strategy_tab.risk_chart.clear_data()
            self.status_message.setText("数据已清空")
            callback = StatusMessageCallback(self, self.status_message)
            QTimer.singleShot(3000, callback.set_ready)
        except Exception as e:
            logger.error(f"清空数据失败: {e}")

    def closeEvent(self, event):
        """关闭事件 - 立即关闭，异步清理资源"""
        try:
            # 立即接受关闭事件，不等待清理完成
            super().closeEvent(event)
            event.accept()
            logger.info("性能监控窗口关闭事件已接受")

            # 使用 QTimer.singleShot(0) 异步清理资源，避免阻塞关闭
            QTimer.singleShot(0, self._async_cleanup)

        except Exception as e:
            logger.error(f"关闭性能监控窗口失败: {e}")
            event.accept()  # 即使失败也允许关闭

    def _async_cleanup(self):
        """异步清理资源 - 不阻塞窗口关闭，带超时保护"""
        try:
            logger.debug("开始异步清理资源...")

            # 添加超时保护，确保清理不会无限期阻塞
            cleanup_timeout = 2000  # 2秒超时
            start_time = time.time()

            # 停止定时器
            if hasattr(self, 'refresh_timer') and self.refresh_timer.isActive():
                self.refresh_timer.stop()
            if hasattr(self, 'drag_detect_timer') and self.drag_detect_timer.isActive():
                self.drag_detect_timer.stop()
            if hasattr(self, '_style_check_timer') and self._style_check_timer.isActive():
                self._style_check_timer.stop()
            if hasattr(self, '_cleanup_timer') and self._cleanup_timer.isActive():
                self._cleanup_timer.stop()
                logger.debug("定期清理定时器已停止")

            # 停止标签页定时器
            if hasattr(self, 'system_tab') and hasattr(self.system_tab, 'monitoring_timer'):
                if self.system_tab.monitoring_timer.isActive():
                    self.system_tab.monitoring_timer.stop()
                    logger.debug("系统监控标签页定时器已停止")
            if hasattr(self, 'algorithm_optimization_tab') and hasattr(self.algorithm_optimization_tab, 'jit_monitoring_timer'):
                if self.algorithm_optimization_tab.jit_monitoring_timer.isActive():
                    self.algorithm_optimization_tab.jit_monitoring_timer.stop()
                    logger.debug("算法优化标签页定时器已停止")
            if hasattr(self, 'risk_control_tab') and hasattr(self.risk_control_tab, 'enhanced_risk_monitor'):
                if self.risk_control_tab.enhanced_risk_monitor:
                    # 使用非阻塞方式停止监控
                    try:
                        self.risk_control_tab.stop_enhanced_monitoring()
                    except Exception as e:
                        logger.debug(f"停止风险监控失败: {e}")
                    logger.debug("风险控制中心标签页定时器已停止")

            # 检查超时
            if time.time() - start_time > cleanup_timeout:
                logger.warning(f"清理过程超时（{cleanup_timeout}ms），强制退出")
                return

            # 断开所有信号槽连接，避免内存泄漏
            if hasattr(self, '_signal_connections'):
                for connection in self._signal_connections:
                    try:
                        # 检查连接对象是否有 disconnect 方法
                        if hasattr(connection, 'disconnect'):
                            connection.disconnect()
                        # 如果没有 disconnect 方法，说明这不是一个有效的连接对象，跳过
                    except Exception as e:
                        logger.debug(f"断开信号槽连接失败（可能已自动断开）: {e}")
                self._signal_connections.clear()

            # 检查超时
            if time.time() - start_time > cleanup_timeout:
                logger.warning(f"清理过程超时（{cleanup_timeout}ms），强制退出")
                return

            # 清理所有标签页 - 使用超时机制
            if hasattr(self, 'tab_widget'):
                tab_count = self.tab_widget.count()
                for i in range(tab_count):
                    # 检查超时
                    if time.time() - start_time > cleanup_timeout:
                        logger.warning(f"清理过程超时（{cleanup_timeout}ms），强制退出")
                        return
                    
                    tab = self.tab_widget.widget(i)
                    if hasattr(tab, 'cleanup'):
                        try:
                            # 直接调用 cleanup，不使用 QTimer.singleShot
                            tab.cleanup()
                        except Exception as e:
                            logger.debug(f"清理标签页 {i} 失败: {e}")

            # 检查超时
            if time.time() - start_time > cleanup_timeout:
                logger.warning(f"清理过程超时（{cleanup_timeout}ms），强制退出")
                return

            # 清理线程池 - 立即清除，不等待，避免卡顿
            if hasattr(self, 'thread_pool'):
                self.thread_pool.clear()  # 清除所有待处理的任务
                # 不再等待正在运行的任务，直接跳过，避免2秒卡顿

            # 清理缓存的服务实例
            self._trading_controller_cache = None
            self._data_manager_cache = None
            logger.debug("外部服务缓存已清理")

            # 注意：performance_monitor 在此组件中从未被 start()，无需停止
            # 如果未来需要启动监控功能，应在此处添加停止逻辑

            logger.debug("ModernUnifiedPerformanceWidget async cleanup completed")

        except Exception as e:
            logger.error(f"异步清理资源失败: {e}")

    def on_tab_changed(self, index):
        """tab切换时的处理 - 优化性能"""
        self.current_tab_index = index
        logger.debug(f"切换到tab: {index}")

        # 立即异步更新当前tab的数据
        callback = UpdateDataCallback(self)
        QTimer.singleShot(100, callback.update_data)

    def force_update_all_data(self):
        """强制更新所有数据 - 忽略缓存"""
        try:
            # 清空缓存
            self._data_cache.clear()
            self._last_update_time.clear()

            # 强制更新当前tab
            self.update_current_tab_data_async()

            logger.info("强制更新所有数据完成")

        except Exception as e:
            logger.error(f"强制更新失败: {e}")

    def _setup_style_protection(self):
        """ 设置样式表保护机制，防止界面变白"""
        try:
            # 保存原始样式表
            self._original_stylesheet = self.styleSheet()
            
            # 检查样式表是否为空
            if not self._original_stylesheet or len(self._original_stylesheet.strip()) == 0:
                logger.warning("样式表为空，保护机制可能无法正常工作")
            else:
                logger.info(f"样式表保护机制已启动，保存的样式表长度: {len(self._original_stylesheet)}")

            # 设置定时器定期检查样式表
            if hasattr(self, '_style_check_timer') and self._style_check_timer is not None:
                if self._style_check_timer.isActive():
                    self._style_check_timer.stop()
                self._style_check_timer.deleteLater()
            
            self._style_check_timer = QTimer(self)
            self._style_check_timer.timeout.connect(self._check_and_restore_styles)
            self._style_check_timer.start(30000)  # 从5秒改为30秒，减少检查频率  # 每5秒检查一次

            # 保存关键组件的样式
            self._backup_styles = {}
            if hasattr(self, 'tab_widget'):
                self._backup_styles['tab_widget'] = self.tab_widget.styleSheet()
                logger.debug(f"tab_widget 样式表已备份，长度: {len(self._backup_styles['tab_widget'])}")
            if hasattr(self, 'toolbar'):
                self._backup_styles['toolbar'] = self.toolbar.styleSheet()
                logger.debug(f"toolbar 样式表已备份，长度: {len(self._backup_styles['toolbar'])}")
            if hasattr(self, 'status_bar'):
                self._backup_styles['status_bar'] = self.status_bar.styleSheet()
                logger.debug(f"status_bar 样式表已备份，长度: {len(self._backup_styles['status_bar'])}")

            logger.debug("样式表保护机制已启动")

        except Exception as e:
            logger.error(f"设置样式表保护失败: {e}")

    def _check_and_restore_styles(self):
        """检查并恢复样式表 - 优化版本，减少不必要的检查"""
        try:
            # 检查主窗口样式
            current_style = self.styleSheet()
            current_style_length = len(current_style.strip()) if current_style else 0
            
            # 只在样式表完全为空时才认为丢失，避免频繁误判
            if not current_style or len(current_style.strip()) == 0:
                logger.warning("检测到样式表丢失，正在恢复...")
                if self._original_stylesheet:
                    self.setStyleSheet(self._original_stylesheet)
                    logger.info(f"主窗口样式表已恢复，恢复的样式表长度: {len(self._original_stylesheet)}")
                else:
                    logger.error("无法恢复样式表：备份样式表为空")

            # 检查关键组件样式 - 只检查tab_widget，减少检查频率
            if hasattr(self, 'tab_widget') and 'tab_widget' in self._backup_styles:
                component = self.tab_widget
                backup_style = self._backup_styles['tab_widget']
                if component and backup_style:
                    current_component_style = component.styleSheet()
                    # 只在样式表完全为空时才认为丢失
                    if not current_component_style or len(current_component_style.strip()) == 0:
                        component.setStyleSheet(backup_style)
                        logger.info(f"tab_widget 样式表已恢复")

        except Exception as e:
            logger.error(f"检查样式表时出错: {e}")
