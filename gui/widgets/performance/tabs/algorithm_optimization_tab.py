#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法优化标签页 - 合并算法性能和自动调优功能
现代化算法优化监控界面，专为量化交易优化
"""

from typing import Dict
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QGridLayout,
    QGroupBox, QPushButton, QProgressBar, QLabel, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer
from gui.widgets.performance.components.metric_card import ModernMetricCard
from gui.widgets.performance.components.performance_chart import ModernPerformanceChart
from loguru import logger

# 延迟导入主题管理器，避免在模块级别导入时崩溃
THEME_MANAGER_AVAILABLE = False
get_theme_manager = None

def _import_theme_manager():
    """延迟导入主题管理器"""
    global THEME_MANAGER_AVAILABLE, get_theme_manager
    if not THEME_MANAGER_AVAILABLE:
        try:
            from utils.theme import get_theme_manager as _get_theme_manager
            get_theme_manager = _get_theme_manager
            THEME_MANAGER_AVAILABLE = True
            logger.info("主题管理器模块导入成功")
        except Exception as e:
            logger.warning(f"导入主题管理器失败: {e}")

# AutoJIT导入（延迟导入以避免循环依赖）
def get_auto_jit_summary():
    try:
        from backtest.auto_jit_decorator import get_auto_jit_summary as _get_auto_jit_summary
        return _get_auto_jit_summary()
    except ImportError:
        return None

def get_auto_jit_functions():
    try:
        from backtest.auto_jit_decorator import get_auto_jit_functions as _get_auto_jit_functions
        return _get_auto_jit_functions()
    except ImportError:
        return None

def get_auto_jit_stats():
    try:
        from backtest.auto_jit_decorator import get_auto_jit_stats as _get_auto_jit_stats
        return _get_auto_jit_stats()
    except ImportError:
        return None

def enable_auto_jit():
    try:
        from backtest.auto_jit_decorator import enable_auto_jit as _enable_auto_jit
        _enable_auto_jit()
        return True
    except ImportError:
        return False

def disable_auto_jit():
    try:
        from backtest.auto_jit_decorator import disable_auto_jit as _disable_auto_jit
        _disable_auto_jit()
        return True
    except ImportError:
        return False

def is_auto_jit_enabled():
    try:
        from backtest.auto_jit_decorator import is_auto_jit_enabled as _is_auto_jit_enabled
        return _is_auto_jit_enabled()
    except ImportError:
        return False

class ModernAlgorithmOptimizationTab(QWidget):
    """现代化算法优化标签页 - 合并算法性能和自动调优"""

    def __init__(self):
        super().__init__()
        self.optimization_progress = 0

        # JIT性能监控相关属性
        self.jit_compile_count = 0
        self.jit_compile_time = 0.0
        self.jit_performance_boost = 0.0
        self.active_threads = 0
        self.jit_enabled = True  # JIT优化启用状态

        # 异步数据收集和模块缓存
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="AlgorithmMonitor")
        self._module_cache = {}  # 缓存导入的模块
        self.jit_monitoring_timer = QTimer()
        self.jit_monitoring_timer.timeout.connect(self._collect_jit_data_async)

        # 延迟导入并初始化主题管理器
        _import_theme_manager()
        self.theme_manager = None
        if THEME_MANAGER_AVAILABLE:
            try:
                self.theme_manager = get_theme_manager()
                self.theme_manager.theme_changed.connect(self._on_theme_changed)
            except Exception as e:
                logger.warning(f"获取ThemeManager失败: {e}")

        self.init_ui()

        # 不在初始化时启动定时器，延迟到UI完全准备好后再启动
        # self.jit_monitoring_timer.start(2000)  # 每2秒更新一次

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 创建子标签页
        self.tab_widget = QTabWidget()

        # 算法性能子标签页
        self.performance_tab = self._create_performance_tab()
        self.tab_widget.addTab(self.performance_tab, "算法性能")

        # JIT性能监控子标签页
        self.jit_tab = self._create_jit_performance_tab()
        self.tab_widget.addTab(self.jit_tab, "JIT性能监控")

        # 自动调优子标签页
        self.tuning_tab = self._create_tuning_tab()
        self.tab_widget.addTab(self.tuning_tab, "自动调优")

        # 性能基准子标签页
        self.benchmark_tab = self._create_benchmark_tab()
        self.tab_widget.addTab(self.benchmark_tab, "性能基准")

        layout.addWidget(self.tab_widget)

    def _create_performance_tab(self):
        """创建算法性能子标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # 算法性能指标卡片
        cards_frame = QFrame()
        cards_frame.setMinimumHeight(100)
        cards_frame.setMaximumHeight(120)
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setContentsMargins(2, 2, 2, 2)
        cards_layout.setSpacing(2)

        self.performance_cards = {}
        performance_metrics = [
            ("执行时间", "#3498db", 0, 0),
            ("计算准确率", "#27ae60", 0, 1),
            ("内存效率", "#f39c12", 0, 2),
            ("并发度", "#9b59b6", 0, 3),
            ("错误率", "#e74c3c", 0, 4),
            ("吞吐量", "#1abc9c", 0, 5),
            ("缓存效率", "#e67e22", 0, 6),
            ("算法复杂度", "#95a5a6", 0, 7),
        ]

        for name, color, row, col in performance_metrics:
            unit = "ms" if "时间" in name else "%" if "率" in name or "效率" in name else "ops/s" if "吞吐量" in name else ""
            card = ModernMetricCard(name, "0", unit, color)
            self.performance_cards[name] = card
            cards_layout.addWidget(card, row, col)

        layout.addWidget(cards_frame)

        # 算法性能趋势图
        self.performance_chart = ModernPerformanceChart("算法性能趋势", "line")
        self.performance_chart.setMinimumHeight(200)  # 减少最小高度，更灵活
        layout.addWidget(self.performance_chart, 1)

        return tab

    def _create_jit_performance_tab(self):
        """创建JIT性能监控子标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        cards_frame = QFrame()
        cards_frame.setMinimumHeight(110)
        cards_frame.setMaximumHeight(140)
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setContentsMargins(2, 2, 2, 2)
        cards_layout.setSpacing(2)

        self.jit_cards = {}
        jit_metrics = [
            ("JIT编译次数", "#3498db", 0, 0),
            ("编译总时间", "#e74c3c", 0, 1),
            ("性能提升", "#27ae60", 0, 2),
            ("活跃线程", "#f39c12", 0, 3),
            ("编译状态", "#9b59b6", 0, 4),
            ("缓存命中", "#1abc9c", 0, 5),
            ("优化等级", "#e67e22", 0, 6),
            ("执行效率", "#95a5a6", 0, 7),
            ("JIT函数数", "#8e44ad", 1, 0),
            ("JIT调用次数", "#17a2b8", 1, 1),
            ("AutoJIT函数数", "#9b59b6", 1, 2),
            ("AutoJIT总调用", "#3498db", 1, 3),
            ("AutoJIT调用", "#27ae60", 1, 4),
            ("原始调用", "#e74c3c", 1, 5),
            ("AutoJIT使用率", "#f39c12", 1, 6),
            ("AutoJIT状态", "#1abc9c", 1, 7),
        ]

        for name, color, row, col in jit_metrics:
            if "时间" in name:
                unit = "ms"
            elif "提升" in name or "命中" in name or "效率" in name or "使用率" in name:
                unit = "%"
            elif "次数" in name or "线程" in name or "等级" in name or "调用" in name:
                unit = ""
            else:
                unit = ""

            card = ModernMetricCard(name, "0", unit, color)
            self.jit_cards[name] = card
            cards_layout.addWidget(card, row, col)

        layout.addWidget(cards_frame)

        # JIT控制面板
        control_group = QGroupBox("JIT编译控制")
        control_layout = QHBoxLayout(control_group)

        self.jit_enable_btn = QPushButton("禁用JIT优化")
        self.jit_enable_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")

        self.jit_enable_btn.clicked.connect(self._toggle_jit_optimization)
        control_layout.addWidget(self.jit_enable_btn)

        self.jit_clear_cache_btn = QPushButton("清理JIT缓存")
        self.jit_clear_cache_btn.clicked.connect(self._clear_jit_cache)
        control_layout.addWidget(self.jit_clear_cache_btn)

        self.autojit_enable_btn = QPushButton("禁用AutoJIT")
        self.autojit_enable_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")
        self.autojit_enable_btn.clicked.connect(self._toggle_autojit_optimization)
        control_layout.addWidget(self.autojit_enable_btn)

        control_layout.addStretch()
        layout.addWidget(control_group)

        # JIT性能趋势图
        self.jit_chart = ModernPerformanceChart("JIT编译性能趋势", "line")
        self.jit_chart.setMinimumHeight(200)  # 减少最小高度，更灵活
        layout.addWidget(self.jit_chart, 1)
        return tab

    def _create_tuning_tab(self):
        """创建自动调优子标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 调优控制面板
        control_group = QGroupBox("调优控制")
        control_layout = QHBoxLayout()

        self.start_tuning_btn = QPushButton("开始调优")
        self.start_tuning_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; }")

        self.start_tuning_btn.clicked.connect(self.start_optimization)
        control_layout.addWidget(self.start_tuning_btn)

        self.stop_tuning_btn = QPushButton("停止调优")
        self.stop_tuning_btn.clicked.connect(self.stop_optimization)
        self.stop_tuning_btn.setEnabled(False)
        control_layout.addWidget(self.stop_tuning_btn)

        control_layout.addStretch()

        # 调优进度
        self.progress_label = QLabel("调优进度: 0%")
        control_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        control_layout.addWidget(self.progress_bar)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 调优指标卡片 - 一行显示
        cards_frame = QFrame()
        cards_frame.setMinimumHeight(50)  # 减少最小高度，更灵活
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setContentsMargins(2, 2, 2, 2)
        cards_layout.setSpacing(2)

        self.tuning_cards = {}
        tuning_metrics = [
            ("调优进度", "#3498db", 0, 0),
            ("性能提升", "#27ae60", 0, 1),
            ("参数空间", "#f39c12", 0, 2),
            ("收敛速度", "#9b59b6", 0, 3),
            ("最优解质量", "#1abc9c", 0, 4),
            ("迭代次数", "#e67e22", 0, 5),
            ("稳定性", "#2ecc71", 0, 6),
            ("调优效率", "#e74c3c", 0, 7),
        ]

        for name, color, row, col in tuning_metrics:
            unit = "%" if name in ["调优进度", "性能提升", "稳定性", "调优效率"] else "次" if "次数" in name else ""
            card = ModernMetricCard(name, "0", unit, color)
            self.tuning_cards[name] = card
            cards_layout.addWidget(card, row, col)

        layout.addWidget(cards_frame)

        # 调优历史图表
        self.tuning_chart = ModernPerformanceChart("调优历史", "line")
        self.tuning_chart.setMinimumHeight(200)  # 减少最小高度，更灵活
        layout.addWidget(self.tuning_chart, 1)

        return tab

    def _create_benchmark_tab(self):
        """创建性能基准子标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 基准对比指标
        benchmark_group = QGroupBox("性能基准对比")
        benchmark_layout = QGridLayout()

        self.benchmark_cards = {}
        benchmark_metrics = [
            ("当前性能", "#3498db", 0, 0),
            ("基准性能", "#95a5a6", 0, 1),
            ("性能比率", "#27ae60", 0, 2),
            ("排名百分位", "#f39c12", 0, 3),
            ("改进空间", "#e67e22", 0, 4),
            ("稳定性评分", "#9b59b6", 0, 5),
            ("效率评级", "#1abc9c", 0, 6),
            ("综合评分", "#2ecc71", 0, 7),
        ]

        for name, color, row, col in benchmark_metrics:
            unit = "%" if "比率" in name or "百分位" in name or "空间" in name else "分" if "评分" in name or "评级" in name else ""
            card = ModernMetricCard(name, "0", unit, color)
            self.benchmark_cards[name] = card
            benchmark_layout.addWidget(card, row, col)

        benchmark_group.setLayout(benchmark_layout)
        layout.addWidget(benchmark_group)

        # 基准对比图表
        self.benchmark_chart = ModernPerformanceChart("性能基准对比", "bar")
        self.benchmark_chart.setMinimumHeight(250)
        layout.addWidget(self.benchmark_chart, 1)

        return tab

    def update_performance_data(self, performance_metrics: Dict[str, float]):
        """更新算法性能数据"""
        try:
            # 使用 QTimer.singleShot 确保在主线程中更新UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_performance_ui_in_main_thread(performance_metrics))

        except Exception as e:
            logger.error(f"更新算法性能数据失败: {e}")

    def _update_performance_ui_in_main_thread(self, performance_metrics: Dict[str, float]):
        """在主线程中更新性能UI"""
        try:
            for name, value in performance_metrics.items():
                if name in self.performance_cards:
                    if value == 0:
                        self.performance_cards[name].update_value("暂无数据", "neutral")
                    else:
                        # 根据指标类型判断趋势
                        if name in ["计算准确率", "内存效率", "并发度", "吞吐量", "缓存效率"]:
                            trend = "up" if value > 80 else "neutral" if value > 50 else "down"
                        else:  # 执行时间、错误率等，越低越好
                            trend = "down" if value > 80 else "neutral" if value > 50 else "up"

                        self.performance_cards[name].update_value(f"{value:.1f}", trend)

            # 更新图表
            for name, value in performance_metrics.items():
                if name in ["执行时间", "计算准确率", "吞吐量"] and value > 0:
                    self.performance_chart.add_data_point(name, value)

        except Exception as e:
            logger.error(f"在主线程中更新性能UI失败: {e}")

    def update_tuning_data(self, tuning_metrics: Dict[str, float]):
        """更新自动调优数据"""
        try:
            # 使用 QTimer.singleShot 确保在主线程中更新UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_tuning_ui_in_main_thread(tuning_metrics))

        except Exception as e:
            logger.error(f"更新自动调优数据失败: {e}")

    def _update_tuning_ui_in_main_thread(self, tuning_metrics: Dict[str, float]):
        """在主线程中更新调优UI"""
        try:
            for name, value in tuning_metrics.items():
                if name in self.tuning_cards:
                    if value == 0:
                        self.tuning_cards[name].update_value("暂无数据", "neutral")
                    else:
                        # 大部分调优指标，数值越高越好
                        trend = "up" if value > 70 else "neutral" if value > 40 else "down"

                        if name == "迭代次数":
                            self.tuning_cards[name].update_value(f"{int(value)}", trend)
                        else:
                            self.tuning_cards[name].update_value(f"{value:.1f}", trend)

            # 更新进度
            progress = tuning_metrics.get("调优进度", 0)
            self.optimization_progress = progress
            self.progress_bar.setValue(int(progress))
            self.progress_label.setText(f"调优进度: {progress:.1f}%")

            # 更新图表
            for name, value in tuning_metrics.items():
                if name in ["调优进度", "性能提升", "收敛速度"] and value > 0:
                    self.tuning_chart.add_data_point(name, value)

        except Exception as e:
            logger.error(f"在主线程中更新调优UI失败: {e}")

    def update_benchmark_data(self, benchmark_metrics: Dict[str, float]):
        """更新性能基准数据"""
        try:
            # 使用 QTimer.singleShot 确保在主线程中更新UI
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_benchmark_ui_in_main_thread(benchmark_metrics))

        except Exception as e:
            logger.error(f"更新性能基准数据失败: {e}")

    def _update_benchmark_ui_in_main_thread(self, benchmark_metrics: Dict[str, float]):
        """在主线程中更新基准UI"""
        try:
            for name, value in benchmark_metrics.items():
                if name in self.benchmark_cards:
                    if value == 0:
                        self.benchmark_cards[name].update_value("暂无数据", "neutral")
                    else:
                        # 根据指标类型判断趋势
                        if name in ["性能比率", "排名百分位", "稳定性评分", "效率评级", "综合评分"]:
                            trend = "up" if value > 80 else "neutral" if value > 60 else "down"
                        else:
                            trend = "neutral"

                        self.benchmark_cards[name].update_value(f"{value:.1f}", trend)

            # 更新基准对比图表
            chart_data = {
                "当前性能": benchmark_metrics.get("当前性能", 0),
                "基准性能": benchmark_metrics.get("基准性能", 0),
                "目标性能": benchmark_metrics.get("当前性能", 0) * 1.2  # 目标提升20%
            }

            for name, value in chart_data.items():
                if value > 0:
                    self.benchmark_chart.add_data_point(name, value)

        except Exception as e:
            logger.error(f"在主线程中更新基准UI失败: {e}")

    def start_optimization(self):
        """开始自动调优"""
        try:
            self.start_tuning_btn.setEnabled(False)
            self.stop_tuning_btn.setEnabled(True)
            logger.info("开始算法自动调优")

            # 这里应该调用实际的调优服务
            # 暂时模拟调优过程

        except Exception as e:
            logger.error(f"启动自动调优失败: {e}")

    def stop_optimization(self):
        """停止自动调优"""
        try:
            self.start_tuning_btn.setEnabled(True)
            self.stop_tuning_btn.setEnabled(False)
            logger.info("停止算法自动调优")

        except Exception as e:
            logger.error(f"停止自动调优失败: {e}")

    def update_data(self, data: Dict[str, any]):
        """统一数据更新接口"""
        try:
            # 根据数据类型分发到不同的更新方法
            if 'performance_metrics' in data:
                self.update_performance_data(data['performance_metrics'])

            if 'tuning_metrics' in data:
                self.update_tuning_data(data['tuning_metrics'])

            if 'benchmark_metrics' in data:
                self.update_benchmark_data(data['benchmark_metrics'])

        except Exception as e:
            logger.error(f"更新算法优化数据失败: {e}")

    def _get_cached_module(self, module_name):
        """获取缓存的模块，避免重复导入"""
        if module_name not in self._module_cache:
            try:
                if module_name == "backtest.jit_optimizer":
                    from backtest.jit_optimizer import jit_optimizer
                    self._module_cache[module_name] = jit_optimizer
                else:
                    self._module_cache[module_name] = None
            except ImportError:
                self._module_cache[module_name] = None
        return self._module_cache[module_name]

    def _collect_jit_data_async(self):
        """异步收集JIT数据，避免UI卡死"""
        try:
            # 提交后台任务
            future = self.executor.submit(self._collect_jit_data)
            # 设置回调，在主线程中更新UI
            future.add_done_callback(self._on_jit_data_collected)
        except Exception as e:
            logger.error(f"提交异步JIT数据收集任务失败: {e}")

    def _collect_jit_data(self):
        """在后台线程中收集JIT数据"""
        try:
            data = {}

            # 获取活跃线程数（快速操作）
            data['active_threads'] = threading.active_count()

            # 尝试获取JIT优化器数据
            jit_optimizer = self._get_cached_module("backtest.jit_optimizer")
            if jit_optimizer and hasattr(jit_optimizer, 'get_stats'):
                try:
                    jit_stats = jit_optimizer.get_stats()
                    data['jit_stats'] = jit_stats
                    data['jit_available'] = True

                    # 获取其他JIT相关数据
                    if hasattr(jit_optimizer, 'get_cache_stats'):
                        data['cache_stats'] = jit_optimizer.get_cache_stats()
                    if hasattr(jit_optimizer, 'get_optimization_level'):
                        data['optimization_level'] = jit_optimizer.get_optimization_level()
                    if hasattr(jit_optimizer, 'get_execution_efficiency'):
                        data['execution_efficiency'] = jit_optimizer.get_execution_efficiency()
                    if hasattr(jit_optimizer, 'get_jit_usage'):
                        data['jit_usage'] = jit_optimizer.get_jit_usage()

                except Exception as e:
                    logger.warning(f"获取JIT统计失败: {e}")
                    data['jit_available'] = False
            else:
                data['jit_available'] = False

            # 尝试获取AutoJIT数据
            autojit_summary = get_auto_jit_summary()
            if autojit_summary:
                data['autojit_available'] = True
                data['autojit_summary'] = autojit_summary
                data['autojit_functions'] = get_auto_jit_functions()
                data['autojit_stats'] = get_auto_jit_stats()
                data['autojit_enabled'] = is_auto_jit_enabled()
            else:
                data['autojit_available'] = False

            return data

        except Exception as e:
            logger.error(f"后台JIT数据收集失败: {e}")
            return None

    def _on_jit_data_collected(self, future):
        """JIT数据收集完成的回调，在主线程中更新UI"""
        try:
            # 获取结果，设置超时避免阻塞
            data = future.result(timeout=0.5)  # 500ms超时
            if data is None:
                self._show_jit_no_data()
                return

            self._update_jit_stats_with_data(data)

        except TimeoutError:
            logger.warning("JIT数据收集超时")
            self._show_jit_no_data()
        except Exception as e:
            logger.error(f"处理收集的JIT数据失败: {e}")
            self._show_jit_no_data()

    def _update_jit_stats_with_data(self, data):
        """使用收集的数据更新JIT统计"""
        try:
            # 更新活跃线程（总是可用）
            self.active_threads = data.get('active_threads', 0)
            if "活跃线程" in self.jit_cards:
                trend = "up" if self.active_threads > 5 else "neutral"
                self.jit_cards["活跃线程"].update_value(str(self.active_threads), trend)

            # 处理JIT数据
            if data.get('jit_available', False):
                jit_stats = data.get('jit_stats', {})
                if jit_stats:
                    self.jit_compile_count = jit_stats.get('compile_count', 0)
                    self.jit_compile_time = jit_stats.get('compile_time', 0.0)
                    self.jit_performance_boost = jit_stats.get('performance_boost', 0.0)

                # 更新JIT指标卡片
                if "JIT编译次数" in self.jit_cards:
                    self.jit_cards["JIT编译次数"].update_value(str(self.jit_compile_count), "neutral")

                if "编译总时间" in self.jit_cards:
                    self.jit_cards["编译总时间"].update_value(f"{self.jit_compile_time:.1f}", "neutral")

                if "性能提升" in self.jit_cards:
                    trend = "up" if self.jit_performance_boost > 50 else "neutral"
                    self.jit_cards["性能提升"].update_value(f"{self.jit_performance_boost:.1f}", trend)

                if "编译状态" in self.jit_cards:
                    status = "活跃" if self.jit_compile_count > 0 else "空闲"
                    self.jit_cards["编译状态"].update_value(status, "neutral")

                # 处理缓存统计
                cache_stats = data.get('cache_stats')
                if "缓存命中" in self.jit_cards:
                    if cache_stats:
                        cache_hit = cache_stats.get('hit_rate', 0.0)
                        trend = "up" if cache_hit > 80 else "neutral"
                        self.jit_cards["缓存命中"].update_value(f"{cache_hit:.1f}", trend)
                    else:
                        self.jit_cards["缓存命中"].update_value("--", "neutral")

                # 处理优化等级
                opt_level = data.get('optimization_level')
                if "优化等级" in self.jit_cards:
                    if opt_level is not None:
                        self.jit_cards["优化等级"].update_value(f"O{opt_level}", "neutral")
                    else:
                        self.jit_cards["优化等级"].update_value("--", "neutral")

                # 处理执行效率
                efficiency = data.get('execution_efficiency')
                if "执行效率" in self.jit_cards:
                    if efficiency is not None:
                        trend = "up" if efficiency > 85 else "neutral"
                        self.jit_cards["执行效率"].update_value(f"{efficiency:.1f}", trend)
                    else:
                        self.jit_cards["执行效率"].update_value("--", "neutral")

                # 处理JIT使用情况
                jit_usage = data.get('jit_usage')
                if jit_usage:
                    # 更新JIT函数数
                    if "JIT函数数" in self.jit_cards:
                        functions_count = len(jit_usage.get('functions', []))
                        self.jit_cards["JIT函数数"].update_value(str(functions_count), "neutral")

                    # 更新JIT调用次数
                    if "JIT调用次数" in self.jit_cards:
                        total_calls = jit_usage.get('total_calls', 0)
                        trend = "up" if total_calls > 100 else "neutral"
                        self.jit_cards["JIT调用次数"].update_value(str(total_calls), trend)

                    # 更新最常用函数
                    if "最常用函数" in self.jit_cards:
                        most_used_name = jit_usage.get('most_used_name', '--')
                        most_used_count = jit_usage.get('most_used_count', 0)
                        self.jit_cards["最常用函数"].update_value(f"{most_used_name}({most_used_count})", "neutral")

                    # 更新最近使用
                    if "最近使用" in self.jit_cards:
                        last_used_name = jit_usage.get('last_used_name', '--')
                        self.jit_cards["最近使用"].update_value(last_used_name, "neutral")

                # 更新JIT性能图表
                if hasattr(self, 'jit_chart'):
                    self.jit_chart.add_data_point("性能提升", self.jit_performance_boost)
                    self.jit_chart.add_data_point("编译时间", self.jit_compile_time)
                    self.jit_chart.add_data_point("活跃线程", self.active_threads * 10)  # 放大显示

            # 处理AutoJIT数据
            if data.get('autojit_available', False):
                autojit_summary = data.get('autojit_summary', {})
                if autojit_summary:
                    if "AutoJIT函数数" in self.jit_cards:
                        total_functions = autojit_summary.get('total_functions', 0)
                        self.jit_cards["AutoJIT函数数"].update_value(str(total_functions), "neutral")

                    if "AutoJIT总调用" in self.jit_cards:
                        total_calls = autojit_summary.get('total_calls', 0)
                        trend = "up" if total_calls > 100 else "neutral"
                        self.jit_cards["AutoJIT总调用"].update_value(str(total_calls), trend)

                    if "AutoJIT调用" in self.jit_cards:
                        jit_calls = autojit_summary.get('jit_calls', 0)
                        self.jit_cards["AutoJIT调用"].update_value(str(jit_calls), "neutral")

                    if "原始调用" in self.jit_cards:
                        original_calls = autojit_summary.get('original_calls', 0)
                        self.jit_cards["原始调用"].update_value(str(original_calls), "neutral")

                    if "AutoJIT使用率" in self.jit_cards:
                        usage_rate = autojit_summary.get('jit_usage_rate', 0.0)
                        trend = "up" if usage_rate > 80 else "neutral"
                        self.jit_cards["AutoJIT使用率"].update_value(f"{usage_rate:.1f}", trend)

                    if "AutoJIT状态" in self.jit_cards:
                        enabled = autojit_summary.get('jit_enabled', False)
                        status = "启用" if enabled else "禁用"
                        self.jit_cards["AutoJIT状态"].update_value(status, "up" if enabled else "down")
            else:
                autojit_metrics = ["AutoJIT函数数", "AutoJIT总调用", "AutoJIT调用", "原始调用", "AutoJIT使用率", "AutoJIT状态"]
                for metric_name in autojit_metrics:
                    if metric_name in self.jit_cards:
                        self.jit_cards[metric_name].update_value("--", "neutral")

        except Exception as e:
            logger.error(f"更新JIT统计失败: {e}")
            self._show_jit_no_data()

    def _show_jit_no_data(self):
        """显示JIT无数据状态"""
        jit_metrics = ["JIT编译次数", "编译总时间", "性能提升", "编译状态", "缓存命中", "优化等级", "执行效率"]
        for metric_name in jit_metrics:
            if metric_name in self.jit_cards:
                self.jit_cards[metric_name].update_value("--", "neutral")
        # 活跃线程数据来自系统，仍然可以显示
        if "活跃线程" in self.jit_cards:
            self.jit_cards["活跃线程"].update_value(str(self.active_threads), "neutral")

    def _toggle_jit_optimization(self):
        """切换JIT优化状态"""
        try:
            current_text = self.jit_enable_btn.text()
            if "启用" in current_text:
                self.jit_enable_btn.setText("禁用JIT优化")
                self.jit_enable_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")
                self.jit_enabled = True
                logger.info("JIT优化已启用")
                
                # 尝试启用JIT优化器
                try:
                    from backtest.jit_optimizer import jit_optimizer
                    if hasattr(jit_optimizer, 'enable'):
                        jit_optimizer.enable()
                except ImportError:
                    pass
            else:
                self.jit_enable_btn.setText("启用JIT优化")
                self.jit_enable_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; }")
                self.jit_enabled = False
                logger.info("JIT优化已禁用")
                
                # 尝试禁用JIT优化器
                try:
                    from backtest.jit_optimizer import jit_optimizer
                    if hasattr(jit_optimizer, 'disable'):
                        jit_optimizer.disable()
                except ImportError:
                    pass
        except Exception as e:
            logger.error(f"切换JIT优化状态失败: {e}")

    def _clear_jit_cache(self):
        """清理JIT缓存"""
        try:
            # 重置JIT统计
            self.jit_compile_count = 0
            self.jit_compile_time = 0.0
            self.jit_performance_boost = 0.0

            # 尝试清理真实的JIT缓存
            try:
                from backtest.jit_optimizer import jit_optimizer
                if hasattr(jit_optimizer, 'clear_cache'):
                    jit_optimizer.clear_cache()
            except ImportError:
                pass

            logger.info("JIT缓存已清理")
        except Exception as e:
            logger.error(f"清理JIT缓存失败: {e}")

    def _toggle_autojit_optimization(self):
        """切换AutoJIT优化状态"""
        try:
            current_text = self.autojit_enable_btn.text()
            if "启用" in current_text:
                self.autojit_enable_btn.setText("禁用AutoJIT")
                self.autojit_enable_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")
                logger.info("AutoJIT优化已启用")
                
                # 启用AutoJIT
                if enable_auto_jit():
                    logger.info("AutoJIT已成功启用")
                else:
                    logger.warning("AutoJIT启用失败")
            else:
                self.autojit_enable_btn.setText("启用AutoJIT")
                self.autojit_enable_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; }")
                logger.info("AutoJIT优化已禁用")
                
                # 禁用AutoJIT
                if disable_auto_jit():
                    logger.info("AutoJIT已成功禁用")
                else:
                    logger.warning("AutoJIT禁用失败")
        except Exception as e:
            logger.error(f"切换AutoJIT优化状态失败: {e}")

    def _on_theme_changed(self):
        """主题变化回调"""
        try:
            # 更新所有卡片的主题样式
            if hasattr(self, 'cards'):
                for card in self.cards.values():
                    if hasattr(card, 'update_theme'):
                        card.update_theme()
            
            # 更新图表主题
            if hasattr(self, 'performance_chart') and hasattr(self.performance_chart, 'update_theme'):
                self.performance_chart.update_theme()
                
            logger.debug("算法优化标签页主题已更新")
        except Exception as e:
            logger.error(f"更新算法优化标签页主题失败: {e}")

    def cleanup(self):
        """清理资源 - 优化性能，避免卡顿"""
        try:
            if hasattr(self, 'jit_monitoring_timer') and self.jit_monitoring_timer:
                try:
                    self.jit_monitoring_timer.stop()
                except Exception as e:
                    logger.debug(f"停止JIT监控定时器失败: {e}")

            # 关闭线程池 - 使用非阻塞关闭
            if hasattr(self, 'executor') and self.executor:
                try:
                    self.executor.shutdown(wait=False)
                    logger.debug("算法优化监控线程池已关闭")
                except Exception as e:
                    logger.debug(f"关闭线程池失败: {e}")

        except Exception as e:
            logger.debug(f"清理算法优化资源失败: {e}")
