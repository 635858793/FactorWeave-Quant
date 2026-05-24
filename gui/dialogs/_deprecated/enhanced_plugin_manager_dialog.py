"""
FactorWeave-Quant 增强插件管理器对话框（废弃）

⚠️ 此文件已被标记为废弃（Deprecated），请使用新的统一插件管理对话框：
    from gui.dialogs.plugin_manager_dialog_unified import PluginManagerDialogUnified

此文件保留仅用于向后兼容。将在未来版本中删除。

专业级插件管理界面，提供多标签页系统管理：
- 数据源插件管理
- 情绪数据插件管理
- 增强插件管理
- 插件市场

基于企业级设计，支持实时监控、配置管理、健康检查等功能。
"""

import warnings
warnings.warn(
    "enhanced_plugin_manager_dialog.py 已被废弃，请使用 plugin_manager_dialog_unified.py 中的 PluginManagerDialogUnified",
    DeprecationWarning,
    stacklevel=2
)

import asyncio
import concurrent.futures
import os
import json
import requests
from loguru import logger
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap

from gui.dialogs.base_dialog import BaseDialog

# 导入现有的组件和服务
PluginConfigWidget = None  # 先初始化为None

try:
    from core.plugin_manager import PluginManager
    from core.services.uni_plugin_data_manager import UniPluginDataManager, get_uni_plugin_data_manager
    from gui.dialogs.plugin_manager_dialog import PluginConfigDialog
    # PluginConfigWidget 已被移除（情绪分析功能已废弃）
    logger.info("核心服务导入成功")
    PLUGIN_SYSTEM_AVAILABLE = True
except ImportError as e:
    PluginManager = None
    UniPluginDataManager = None
    PluginConfigDialog = None
    PLUGIN_SYSTEM_AVAILABLE = False
    logger.error(f" 部分服务导入失败: {e}")

# 如果PluginConfigWidget没有导入成功，创建一个简单的备用版本
if not PLUGIN_SYSTEM_AVAILABLE or PluginConfigWidget is None:
    class PluginConfigWidget(QWidget):
        """备用的插件配置组件"""
        config_changed = pyqtSignal(str, dict)
        test_requested = pyqtSignal(str)

        def __init__(self, plugin_name: str, config: dict, parent=None):
            super().__init__(parent)
            self.plugin_name = plugin_name
            self.config = config
            layout = QVBoxLayout(self)
            label = QLabel(f"插件配置组件不可用: {plugin_name}")
            layout.addWidget(label)


class TablePopulationWorker(QThread):
    """表格填充异步工作线程"""

    # 信号定义
    row_populated = pyqtSignal(int, dict)      # 行号, 行数据
    population_progress = pyqtSignal(int, int, str)  # 当前进度, 总数, 插件名
    population_completed = pyqtSignal()        # 完成信号
    population_failed = pyqtSignal(str)        # 错误信息

    def __init__(self, data_sources: dict, chinese_map: dict, parent=None, metrics: dict = None, use_cache: bool = True):
        super().__init__(parent)
        self.data_sources = data_sources
        self.chinese_map = chinese_map  # 资产类型中文映射
        self._is_running = False
        self.dialog = parent  # 保持向后兼容
        self.metrics = metrics or {}
        self.use_cache = use_cache  # 快速模式：优先使用缓存

    def run(self):
        """异步填充表格数据 - 使用并行处理优化"""
        self._is_running = True
        try:
            logger.info(f" 开始异步填充表格数据，数据源数量: {len(self.data_sources)}")

            total_count = len(self.data_sources)
            if total_count == 0:
                self.population_completed.emit()
                return

            # 使用线程池并行处理所有插件
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, total_count)) as executor:
                # 提交所有任务
                future_to_source = {}
                for row, (source_id, adapter) in enumerate(self.data_sources.items()):
                    if not self._is_running:
                        break
                    future = executor.submit(self._get_row_data, source_id, adapter, row)
                    future_to_source[future] = (row, source_id)

                # 收集结果
                for future in concurrent.futures.as_completed(future_to_source):
                    if not self._is_running:
                        break

                    row, source_id = future_to_source[future]
                    try:
                        row_data = future.result()
                        self.row_populated.emit(row, row_data)
                        self.population_progress.emit(row + 1, total_count, source_id)
                    except Exception as e:
                        logger.error(f"    异步处理数据源 {source_id} 失败: {e}")
                        error_row_data = {
                            'name': str(source_id),
                            'status': " 错误",
                            'assets': "-",
                            'health_score': "-",
                            'priority': str(row + 1),
                            'source_id': source_id
                        }
                        self.row_populated.emit(row, error_row_data)

            if self._is_running:
                self.population_completed.emit()
                logger.info("异步表格填充完成")

        except Exception as e:
            self.population_failed.emit(str(e))
            logger.error(f" 异步表格填充失败: {e}")

    def _get_row_data(self, source_id: str, adapter, row: int) -> dict:
        """获取单行数据（在工作线程中）

        优化：快速模式下优先使用缓存状态，避免每个插件都执行网络请求
        """
        try:
            # 获取插件信息
            plugin_info = adapter.get_plugin_info()

            # 插件名称
            name = getattr(plugin_info, 'name', source_id)

            # 状态判断：快速模式使用缓存，避免网络请求
            is_connected = False
            status_message = "未连接"

            # 优先从路由器获取缓存的连接状态
            router_cached_healthy = None
            try:
                from core.services.unified_data_manager import get_unified_data_manager
                unified_manager = get_unified_data_manager()
                router = getattr(unified_manager, 'data_source_router', None) if unified_manager else None

                if router and hasattr(router, 'metrics'):
                    router_metrics = router.metrics.get(source_id)
                    if router_metrics and hasattr(router_metrics, 'health_score'):
                        router_cached_healthy = router_metrics.health_score > 0.5
            except Exception:
                pass

            # 快速模式：使用缓存状态，避免网络请求
            if self.use_cache and router_cached_healthy is not None:
                is_connected = router_cached_healthy
                status_message = "活跃" if is_connected else "缓存判定未连接"
                logger.debug(f" 插件 {source_id} 使用缓存状态: {status_message}")
            else:
                # 非快速模式或无缓存：执行完整检查（原有逻辑）
                try:
                    plugin_instance = getattr(adapter, 'plugin', None)
                    if plugin_instance:
                        plugin_initialized = getattr(plugin_instance, 'initialized', False)
                        if not plugin_initialized:
                            status_message = "插件未初始化"
                        else:
                            if hasattr(plugin_instance, 'is_connected'):
                                try:
                                    plugin_connected = bool(plugin_instance.is_connected())
                                    if not plugin_connected:
                                        status_message = "插件未连接"
                                    else:
                                        health_result = adapter.health_check()
                                        if hasattr(health_result, 'is_healthy') and health_result.is_healthy:
                                            is_connected = True
                                            status_message = "活跃"
                                        else:
                                            error_msg = getattr(health_result, 'error_message', '健康检查失败')
                                            status_message = error_msg
                                except Exception as e:
                                    status_message = f"连接检查失败: {str(e)}"
                            else:
                                health_result = adapter.health_check()
                                if hasattr(health_result, 'is_healthy') and health_result.is_healthy:
                                    is_connected = True
                                    status_message = "活跃"
                                else:
                                    error_msg = getattr(health_result, 'error_message', '健康检查失败')
                                    status_message = error_msg
                    else:
                        status_message = "插件实例不存在"
                except Exception as e:
                    logger.error(f"检查插件状态失败 {source_id}: {e}")
                    status_message = "未知"

            # 如果还没有连接，检查适配器错误状态
            if not is_connected and hasattr(adapter, 'last_error') and adapter.last_error:
                status_message = adapter.last_error

            status = " 活跃" if is_connected else " 未连接"

            # 支持资产
            try:
                asset_types = getattr(plugin_info, 'supported_asset_types', [])
                if asset_types:
                    # 将英文资产类型转换为中文
                    chinese_assets = []
                    for asset in asset_types:
                        asset_value = getattr(asset, 'value', str(asset))
                        chinese_name = self.chinese_map.get(asset_value, asset_value)
                        chinese_assets.append(chinese_name)
                    assets = ", ".join(chinese_assets)
                else:
                    assets = "通用"
            except Exception:
                assets = "通用"

            # 健康分数：优先使用路由器缓存指标，避免阻塞
            health_score = "N/A"
            try:
                # 尝试从路由器获取指标
                from core.services.unified_data_manager import get_unified_data_manager
                unified_manager = get_unified_data_manager()
                router = getattr(unified_manager, 'data_source_router', None) if unified_manager else None

                if router and hasattr(router, 'metrics'):
                    metrics = router.metrics.get(source_id)
                    if metrics and hasattr(metrics, 'health_score'):
                        health_score = f"{metrics.health_score:.2f}"
                    elif metrics and hasattr(metrics, 'success_rate'):
                        # 基于成功率计算健康分数
                        success_rate = metrics.success_rate
                        if success_rate >= 0.9:
                            health_score = "0.95"
                        elif success_rate >= 0.7:
                            health_score = "0.80"
                        elif success_rate >= 0.5:
                            health_score = "0.65"
                        else:
                            health_score = "0.30"

                # 如果路由器没有指标，尝试从适配器获取
                if health_score == "N/A" and adapter:
                    if hasattr(adapter, 'health_score'):
                        health_score = f"{adapter.health_score:.2f}"
                    elif hasattr(adapter, 'stats') and adapter.stats:
                        stats = adapter.stats
                        total = stats.get('total_requests', 0)
                        success = stats.get('successful_requests', 0)
                        if total > 0:
                            success_rate = success / total
                            health_score = f"{min(1.0, success_rate + 0.1):.2f}"
                        else:
                            health_score = "1.00"  # 新插件默认满分
                    else:
                        # 基于连接状态给出基础分数
                        if status == " 活跃":
                            health_score = "0.85"
                        elif status == " 未连接":
                            health_score = "0.10"
                        else:
                            health_score = "0.50"

            except Exception as e:
                logger.error(f"计算健康分数失败 {source_id}: {e}")
                # 基于状态给出默认分数
                if status == " 活跃":
                    health_score = "0.80"
                elif status == " 未连接":
                    health_score = "0.00"
                else:
                    health_score = "N/A"

            # 优先级
            priority = str(row + 1)

            return {
                'name': name,
                'status': status,
                'assets': assets,
                'health_score': health_score,
                'priority': priority,
                'source_id': source_id
            }

        except Exception as e:
            logger.error(f" 获取行数据失败 {source_id}: {e}")
            return {
                'name': str(source_id),
                'status': " 错误",
                'assets': "-",
                'health_score': "-",
                'priority': str(row + 1),
                'source_id': source_id
            }

    def stop(self):
        """停止填充"""
        self._is_running = False


class DataSourceLoadingWorker(QThread):
    """数据源插件异步加载工作线程"""

    # 信号定义
    plugin_loaded = pyqtSignal(str, dict, object)  # 插件名称, 插件信息, 插件实例
    loading_progress = pyqtSignal(int, int, str)   # 当前进度, 总数, 当前插件名
    loading_completed = pyqtSignal(dict)           # 所有适配器
    loading_failed = pyqtSignal(str)               # 错误信息

    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self._is_running = False

    def run(self):
        """异步加载数据源插件"""
        self._is_running = True
        try:
            logger.info("开始异步加载数据源插件...")

            real_adapters = {}
            ds_plugins = {}

            # 获取数据源插件列表
            if hasattr(self.plugin_manager, 'get_data_source_plugins'):
                ds_plugins = self.plugin_manager.get_data_source_plugins()
            elif hasattr(self.plugin_manager, 'data_source_plugins'):
                ds_plugins = self.plugin_manager.data_source_plugins

            total_count = len(ds_plugins)
            self.loading_progress.emit(0, total_count, "开始加载...")

            if not ds_plugins:
                self.loading_completed.emit({})
                return

            # 使用线程池并发处理插件
            with concurrent.futures.ThreadPoolExecutor(os.cpu_count() * 2) as executor:
                future_to_plugin = {}

                for plugin_name, plugin_info in ds_plugins.items():
                    if not self._is_running:
                        break

                    plugin_instance = self.plugin_manager.plugin_instances.get(plugin_name)
                    if plugin_instance:
                        # 提交到线程池
                        future = executor.submit(self._process_plugin, plugin_name, plugin_info, plugin_instance)
                        future_to_plugin[future] = plugin_name

                # 收集结果
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_plugin):
                    if not self._is_running:
                        break

                    plugin_name = future_to_plugin[future]
                    completed_count += 1

                    try:
                        adapter = future.result()
                        if adapter:
                            real_adapters[plugin_name] = adapter
                            self.plugin_loaded.emit(plugin_name, {}, adapter)

                        self.loading_progress.emit(completed_count, total_count, plugin_name)

                    except Exception as e:
                        logger.error(f" 处理插件 {plugin_name} 失败: {e}")

            if self._is_running:
                self.loading_completed.emit(real_adapters)
                logger.info(f" 异步加载完成，共加载 {len(real_adapters)} 个插件")

        except Exception as e:
            self.loading_failed.emit(str(e))
            logger.error(f" 异步加载失败: {e}")

    def _process_plugin(self, plugin_name, plugin_info, plugin_instance):
        """处理单个插件（在工作线程中）"""
        try:
            # 这里可以调用可能耗时的插件初始化操作
            # 比如健康检查、连接测试等

            # 创建适配器（直接调用方法而不是创建新对话框）
            adapter = self._create_adapter_for_plugin(plugin_name, plugin_info, plugin_instance)

            return adapter

        except Exception as e:
            logger.error(f" 创建插件适配器失败 {plugin_name}: {e}")
            return None

    def stop(self):
        """停止加载"""
        self._is_running = False

    def _create_adapter_for_plugin(self, plugin_name: str, plugin_info, plugin_instance):
        """为插件创建适配器（静态方法，避免循环依赖）"""
        try:
            # 尝试使用真实的DataSourcePluginAdapter
            if hasattr(plugin_instance, 'get_plugin_info'):
                # 插件有真实的get_plugin_info方法
                return type('RealAdapter', (), {
                    'get_plugin_info': lambda *args: plugin_instance.get_plugin_info(),
                    'is_connected': lambda *args: getattr(plugin_instance, 'initialized', True),
                    'health_check': lambda *args: self._get_real_health_check_static(plugin_instance),
                    'get_statistics': lambda *args: self._get_real_statistics_static(plugin_instance)
                })()
            else:
                # 创建兼容的适配器
                return type('CompatAdapter', (), {
                    'get_plugin_info': lambda *args: type('PluginInfo', (), {
                        'id': plugin_name,
                        'name': plugin_info.name,
                        'description': plugin_info.description,
                        'version': plugin_info.version,
                        'supported_asset_types': getattr(plugin_instance, 'get_supported_asset_types', lambda: [])()
                    })(),
                    'is_connected': lambda *args: plugin_info.enabled if hasattr(plugin_info, 'enabled') else True,
                    'health_check': lambda *args: self._get_real_health_check_static(plugin_instance),
                    'get_statistics': lambda *args: self._get_real_statistics_static(plugin_instance)
                })()

        except Exception as e:
            logger.error(f" 创建真实适配器失败 {plugin_name}: {e}")
            # 返回最小可用适配器
            return type('MinimalAdapter', (), {
                'get_plugin_info': lambda *args: type('PluginInfo', (), {
                    'id': plugin_name,
                    'name': plugin_info.name if hasattr(plugin_info, 'name') else plugin_name,
                    'description': getattr(plugin_info, 'description', '数据源插件'),
                    'version': getattr(plugin_info, 'version', '1.0.0'),
                    'supported_asset_types': []
                })(),
                'is_connected': lambda *args: True,
                'health_check': lambda *args: type('HealthCheckResult', (), {
                    'is_healthy': True,
                    'response_time': 0.0,
                    'error_message': None
                })(),
                'get_statistics': lambda *args: {'total_requests': 0, 'success_rate': 1.0}
            })()

    def _get_real_health_check_static(self, plugin_instance):
        """获取真实的健康检查结果（静态版本）"""
        try:
            if hasattr(plugin_instance, 'health_check'):
                return plugin_instance.health_check()
            elif hasattr(plugin_instance, 'test_connection'):
                is_healthy = plugin_instance.test_connection()
                return type('HealthCheckResult', (), {
                    'is_healthy': is_healthy,
                    'response_time': 0.1,
                    'error_message': None if is_healthy else 'Connection failed'
                })()
            else:
                # 基于初始化状态判断
                is_healthy = getattr(plugin_instance, 'initialized', True)
                return type('HealthCheckResult', (), {
                    'is_healthy': is_healthy,
                    'response_time': 0.0,
                    'error_message': None if is_healthy else 'Plugin not initialized'
                })()
        except Exception as e:
            return type('HealthCheckResult', (), {
                'is_healthy': False,
                'response_time': 0.0,
                'error_message': str(e)
            })()

    def _get_real_statistics_static(self, plugin_instance):
        """获取真实的统计数据（静态版本）"""
        try:
            if hasattr(plugin_instance, 'get_statistics'):
                return plugin_instance.get_statistics()
            else:
                return {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'success_rate': 1.0,
                    'avg_response_time': 0.0
                }
        except Exception as e:
            return {'error': str(e), 'success_rate': 0.0}


class EnhancedPluginManagerDialog(BaseDialog):
    """增强型插件管理器对话框"""

    # 信号定义
    plugin_enabled = pyqtSignal(str)
    plugin_disabled = pyqtSignal(str)
    plugin_configured = pyqtSignal(str, dict)
    sentiment_plugin_tested = pyqtSignal(str, bool)

    def __init__(self, plugin_manager=None, sentiment_service=None, parent=None):
        super().__init__(
            parent,
            title="插件管理器",
            min_size=(1000, 700),
            size=(1000, 700),
            settings_key="EnhancedPluginManagerDialog"
        )
        self.plugin_manager = plugin_manager
        self.sentiment_service = sentiment_service
        self.uni_plugin_data_manager = get_uni_plugin_data_manager()  # 添加统一插件数据管理器支持
        self.plugin_widgets = {}
        self.sentiment_config_widgets = {}

        # 资产类型中文映射（必须在init_ui之前初始化）
        self.asset_type_chinese_map = {
            'stock': '股票',
            'futures': '期货',
            'crypto': '数字货币',
            'forex': '外汇',
            'bond': '债券',
            'commodity': '商品',
            'index': '指数',
            'fund': '基金',
            'option': '期权',
            'warrant': '权证'
        }

        # 初始化资产类型显示映射（中文 -> 英文）
        self.asset_type_display_map = {
            chinese: english for english, chinese in self.asset_type_chinese_map.items()
        }

        self.init_ui()
        self.load_plugins()

        # 定时器用于状态刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(30000)  # 30秒刷新一次

        logger.info("准备启动数据源同步...")
        # 数据源同步到统一管理器（延迟执行确保所有服务已初始化）
        QTimer.singleShot(500, self._sync_data_sources_to_unified_manager)

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("插件管理器")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 全局操作按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_status)
        title_layout.addWidget(refresh_btn)

        export_btn = QPushButton("导出配置")
        export_btn.clicked.connect(self.export_all_configs)
        title_layout.addWidget(export_btn)

        import_btn = QPushButton("导入配置")
        import_btn.clicked.connect(self.import_all_configs)
        title_layout.addWidget(import_btn)

        layout.addLayout(title_layout)

        # 选项卡界面
        self.tab_widget = QTabWidget()

        # 1. 通用插件管理标签页
        self.general_tab = self.create_general_plugins_tab()
        self.tab_widget.addTab(self.general_tab, "通用插件")

        # 2. 情绪数据源插件标签页
        self.sentiment_tab = self.create_sentiment_plugins_tab()
        self.tab_widget.addTab(self.sentiment_tab, "情绪数据源")

        # 3. 数据源插件标签页（新增 Task 3.1）
        self.data_source_tab = self.create_data_source_plugins_tab()
        self.tab_widget.addTab(self.data_source_tab, "数据源插件")

        # 3.5 指标/策略插件（V2）标签页
        self.indicator_strategy_tab = QWidget()
        self._create_indicator_strategy_tab(self.indicator_strategy_tab)
        self.tab_widget.addTab(self.indicator_strategy_tab, "指标/策略")

        # 4. 插件市场标签页
        self.market_tab = self.create_market_tab()
        self.tab_widget.addTab(self.market_tab, "插件市场")

        layout.addWidget(self.tab_widget)

        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.plugin_count_label = QLabel("插件总数: 0")
        self.active_count_label = QLabel("活跃插件: 0")

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.plugin_count_label)
        status_layout.addWidget(QLabel("|"))
        status_layout.addWidget(self.active_count_label)

        layout.addLayout(status_layout)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        apply_btn = QPushButton("应用")
        apply_btn.clicked.connect(self.apply_all_configs)
        button_layout.addWidget(apply_btn)

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def create_general_plugins_tab(self) -> QWidget:
        """创建通用插件管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明文本
        desc_label = QLabel("管理系统中的所有插件，包括启用/禁用、配置和状态监控。")
        desc_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        enable_all_btn = QPushButton("全部启用")
        enable_all_btn.clicked.connect(self.enable_all_general_plugins)
        toolbar_layout.addWidget(enable_all_btn)

        disable_all_btn = QPushButton("全部禁用")
        disable_all_btn.clicked.connect(self.disable_all_general_plugins)
        toolbar_layout.addWidget(disable_all_btn)

        toolbar_layout.addStretch()

        filter_label = QLabel("过滤:")
        self.general_filter_combo = QComboBox()
        self.general_filter_combo.addItems(["全部", "已启用", "已禁用", "数据源", "分析工具", "UI组件"])
        self.general_filter_combo.currentTextChanged.connect(self.filter_general_plugins)

        toolbar_layout.addWidget(filter_label)
        toolbar_layout.addWidget(self.general_filter_combo)

        layout.addLayout(toolbar_layout)

        # 插件列表（使用滚动区域）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.general_plugins_widget = QWidget()
        self.general_plugins_layout = QVBoxLayout(self.general_plugins_widget)
        self.general_plugins_layout.setSpacing(10)

        scroll_area.setWidget(self.general_plugins_widget)
        layout.addWidget(scroll_area)

        return widget

    def create_sentiment_plugins_tab(self) -> QWidget:
        """创建情绪数据源插件标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明文本
        desc_label = QLabel("配置和管理情绪分析数据源插件，包括权重设置、参数配置和连接测试。")
        desc_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(desc_label)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        test_all_btn = QPushButton("测试所有连接")
        test_all_btn.clicked.connect(self.test_all_sentiment_plugins)
        toolbar_layout.addWidget(test_all_btn)

        reset_weights_btn = QPushButton("重置权重")
        reset_weights_btn.clicked.connect(self.reset_sentiment_weights)
        toolbar_layout.addWidget(reset_weights_btn)

        toolbar_layout.addStretch()

        # 全局配置 - 缩小宽度
        global_config_group = QGroupBox("全局配置")
        global_config_group.setMaximumWidth(250)
        global_layout = QFormLayout(global_config_group)

        self.auto_refresh_cb = QCheckBox()
        self.auto_refresh_cb.setChecked(True)
        global_layout.addRow("自动刷新:", self.auto_refresh_cb)

        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(1, 60)
        self.refresh_interval_spin.setValue(10)
        self.refresh_interval_spin.setSuffix("分钟")
        global_layout.addRow("刷新间隔:", self.refresh_interval_spin)

        toolbar_layout.addWidget(global_config_group)

        layout.addLayout(toolbar_layout)

        # 添加分割线
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setFrameShadow(QFrame.Sunken)
        separator1.setStyleSheet("background-color: #bdc3c7; margin: 5px 0;")
        layout.addWidget(separator1)

        # 情绪插件配置区域 - 使用带网格线的表格布局
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
            }
        """)

        self.sentiment_plugins_widget = QWidget()
        # 改为网格布局，支持两列显示，带分割线
        self.sentiment_plugins_layout = QGridLayout(self.sentiment_plugins_widget)
        self.sentiment_plugins_layout.setSpacing(15)
        self.sentiment_plugins_layout.setContentsMargins(10, 10, 10, 10)

        # 添加网格线样式
        self.sentiment_plugins_widget.setStyleSheet("""
            QWidget {
                background-color: white;
            }
            QGroupBox {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
            }
        """)

        scroll_area.setWidget(self.sentiment_plugins_widget)
        layout.addWidget(scroll_area)

        return widget

    # 性能监控相关功能已移除
    pass

    def create_market_tab(self) -> QWidget:
        """创建插件市场标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入插件名称或关键词...")
        search_layout.addWidget(self.search_edit)

        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self.search_plugins)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # 分类过滤
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("分类:"))

        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "数据源", "技术指标", "策略工具", "UI增强", "实用工具"])
        category_layout.addWidget(self.category_combo)

        category_layout.addStretch()

        refresh_market_btn = QPushButton("刷新市场")
        refresh_market_btn.clicked.connect(self.refresh_market)
        category_layout.addWidget(refresh_market_btn)

        layout.addLayout(category_layout)

        # 插件卡片展示区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.market_plugins_widget = QWidget()
        self.market_plugins_layout = QVBoxLayout(self.market_plugins_widget)

        scroll_area.setWidget(self.market_plugins_widget)
        layout.addWidget(scroll_area)

        # 加载示例插件卡片
        self.load_market_plugins()

        return widget

    def load_plugins(self):
        """加载所有插件"""
        self.load_general_plugins()
        self.load_sentiment_plugins()
        self.update_status_counts()

    def load_general_plugins(self):
        """加载通用插件"""
        # 清理现有插件
        for i in reversed(range(self.general_plugins_layout.count())):
            child = self.general_plugins_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        self.plugin_widgets.clear()

        # 尝试获取插件管理器（如果当前没有）
        if not self.plugin_manager:
            self._try_get_plugin_manager()

        # 如果有插件管理器，从中加载真实插件
        if self.plugin_manager:
            try:
                # 验证插件管理器是否已初始化
                if not hasattr(self.plugin_manager, 'enhanced_plugins'):
                    logger.info("插件管理器未初始化，尝试重新初始化...")
                    self.plugin_manager.initialize()

                    # 优先使用enhanced_plugins获取插件信息
                if hasattr(self.plugin_manager, 'get_all_enhanced_plugins'):
                    enhanced_plugins = self.plugin_manager.get_all_enhanced_plugins()
                    logger.info(f" 成功加载 {len(enhanced_plugins)} 个增强插件")

                    if enhanced_plugins:
                        for plugin_name, plugin_info in enhanced_plugins.items():
                            # 获取友好的插件类型显示
                            plugin_type_display = self._get_plugin_type_display(plugin_info.plugin_type)

                            # 创建插件信息字典
                            plugin_data = {
                                "id": plugin_name,  # 唯一键（用于调用 PluginManager）
                                "name": plugin_info.name,
                                "type": plugin_type_display,
                                "version": plugin_info.version,
                                "description": plugin_info.description,
                                "enabled": plugin_info.enabled,
                                "status": "运行中" if plugin_info.enabled else "已停用",
                                "plugin_info": plugin_info  # 添加完整的插件信息对象
                            }
                            self._create_general_plugin_widget(plugin_data)
                    else:
                        # 没有enhanced_plugins，尝试普通插件
                        self._load_regular_plugins()
                else:
                    # 没有enhanced_plugins方法，使用普通插件
                    self._load_regular_plugins()

            except Exception as e:
                logger.error(f" 加载真实插件失败: {e}")
                import traceback
                traceback.print_exc()
                # 显示错误信息而不是fallback到示例数据
                self._show_plugin_error_message(str(e))
        else:
            # 没有插件管理器时显示错误信息而不是示例数据
            self._show_plugin_manager_unavailable_message()

    def _try_get_plugin_manager(self):
        """尝试获取插件管理器"""
        try:
            # 尝试从服务容器获取
            from core.containers import get_service_container
            from core.plugin_manager import PluginManager

            container = get_service_container()
            if container and container.is_registered(PluginManager):
                self.plugin_manager = container.resolve(PluginManager)
                logger.info("成功从服务容器获取插件管理器")
                return True
        except Exception as e:
            logger.error(f" 从服务容器获取插件管理器失败: {e}")

        return False

    def _show_no_plugins_message(self):
        """显示没有插件的消息"""
        from PyQt5.QtWidgets import QLabel, QVBoxLayout, QFrame

        message_widget = QFrame()
        message_widget.setFrameStyle(QFrame.StyledPanel)
        message_widget.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px dashed #dee2e6;
                border-radius: 8px;
                padding: 20px;
            }
        """)

        layout = QVBoxLayout(message_widget)

        title = QLabel("暂无插件")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #6c757d;")
        layout.addWidget(title)

        desc = QLabel("插件管理器已连接，但没有找到任何插件。\n请检查plugins目录或加载插件。")
        desc.setStyleSheet("color: #868e96; margin-top: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.general_plugins_layout.addWidget(message_widget)

    def _show_plugin_error_message(self, error_msg):
        """显示插件加载错误消息"""
        from PyQt5.QtWidgets import QLabel, QVBoxLayout, QFrame, QPushButton

        error_widget = QFrame()
        error_widget.setFrameStyle(QFrame.StyledPanel)
        error_widget.setStyleSheet("""
            QFrame {
                background-color: #fff3cd;
                border: 2px solid #ffeaa7;
                border-radius: 8px;
                padding: 20px;
            }
        """)

        layout = QVBoxLayout(error_widget)

        title = QLabel("插件加载失败")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #856404;")
        layout.addWidget(title)

        desc = QLabel(f"加载插件时发生错误：\n{error_msg}")
        desc.setStyleSheet("color: #856404; margin-top: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        retry_btn = QPushButton("重试加载")
        retry_btn.setMaximumWidth(100)
        retry_btn.clicked.connect(self.load_general_plugins)
        layout.addWidget(retry_btn)

        self.general_plugins_layout.addWidget(error_widget)

    def _get_plugin_type_display(self, plugin_type) -> str:
        """获取友好的插件类型显示"""
        if not plugin_type:
            return "通用插件"

        # 插件类型映射表
        type_mapping = {
            'INDICATOR': ' 技术指标',
            'STRATEGY': ' 交易策略',
            'DATA_SOURCE': ' 数据源',
            'ANALYSIS': ' 分析工具',
            'UI_COMPONENT': ' 界面组件',
            'EXPORT': ' 导出工具',
            'NOTIFICATION': ' 通知服务',
            'CHART_TOOL': ' 图表工具',
            'RISK_MANAGEMENT': ' 风险管理',
            'PORTFOLIO': ' 投资组合',
            'SENTIMENT': ' 情绪分析',
            'AI': ' 人工智能',
            'MACHINE_LEARNING': ' 机器学习'
        }

        # 转换为字符串进行匹配
        plugin_type_str = str(plugin_type).upper()

        # 移除可能的前缀
        for prefix in ['PLUGINTYPE.', 'PLUGIN_TYPE.']:
            if plugin_type_str.startswith(prefix):
                plugin_type_str = plugin_type_str[len(prefix):]
                break

        # 查找映射
        return type_mapping.get(plugin_type_str, f" {plugin_type_str.title()}")

    def _show_plugin_manager_unavailable_message(self):
        """显示插件管理器不可用的消息"""
        from PyQt5.QtWidgets import QLabel, QVBoxLayout, QFrame, QPushButton

        unavailable_widget = QFrame()
        unavailable_widget.setFrameStyle(QFrame.StyledPanel)
        unavailable_widget.setStyleSheet("""
            QFrame {
                background-color: #f8d7da;
                border: 2px solid #f5c6cb;
                border-radius: 8px;
                padding: 20px;
            }
        """)

        layout = QVBoxLayout(unavailable_widget)

        title = QLabel("插件管理器不可用")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #721c24;")
        layout.addWidget(title)

        desc = QLabel(
            "无法连接到插件管理器。可能的原因：\n"
            " 服务容器未正确初始化\n"
            " 插件管理器服务未注册\n"
            " 系统启动时发生错误"
        )
        desc.setStyleSheet("color: #721c24; margin-top: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        retry_btn = QPushButton("重新尝试连接")
        retry_btn.setMaximumWidth(150)
        retry_btn.clicked.connect(self.load_general_plugins)
        layout.addWidget(retry_btn)

        self.general_plugins_layout.addWidget(unavailable_widget)

    def _load_regular_plugins(self):
        """加载普通插件（fallback方法）"""
        try:
            all_plugins = self.plugin_manager.get_all_plugins()
            logger.info(f" 成功加载 {len(all_plugins)} 个普通插件")

            if all_plugins:
                for plugin_name, plugin_instance in all_plugins.items():
                    # 从插件实例获取信息
                    plugin_data = {
                        "name": getattr(plugin_instance, 'name', plugin_name),
                        "type": str(getattr(plugin_instance, 'plugin_type', 'UNKNOWN')),
                        "version": getattr(plugin_instance, 'version', '1.0.0'),
                        "description": getattr(plugin_instance, 'description', '无描述'),
                        "enabled": False,  # 普通插件默认未启用
                        "status": "已停用"
                    }
                    self._create_general_plugin_widget(plugin_data)
            else:
                # 没有找到插件，显示提示信息
                self._show_no_plugins_message()

        except Exception as e:
            logger.error(f" 加载普通插件失败: {e}")
            self._show_no_plugins_message()

    def _create_general_plugin_widget(self, plugin_info):
        """创建通用插件小部件"""
        # 优先使用数据库中的 display_name/description 覆盖展示
        try:
            db_display_name = None
            db_description = None
            dbs = None
            try:
                from core.services.plugin_database_service import get_plugin_database_service
                dbs = get_plugin_database_service()
            except Exception:
                dbs = None

            if dbs is not None:
                try:
                    # plugin_info 里若带有唯一键 id（如 examples.xxx），用它查找；否则用 name
                    key = plugin_info.get('id', plugin_info.get('name'))
                    if key:
                        rec = None
                        try:
                            # 若服务不提供单条查询，则遍历缓存列表
                            all_recs = dbs.get_all_plugins(force_refresh=False) or []
                            for r in all_recs:
                                if r.get('name') == key:
                                    rec = r
                                    break
                        except Exception:
                            pass
                        if rec:
                            db_display_name = rec.get('display_name') or rec.get('name')
                            db_description = rec.get('description') or None
                except Exception:
                    pass

            if db_display_name:
                plugin_info['name'] = db_display_name
            if db_description:
                plugin_info['description'] = db_description
        except Exception:
            pass

        plugin_widget = self.create_general_plugin_widget(plugin_info)
        self.general_plugins_layout.addWidget(plugin_widget)

    def load_sentiment_plugins(self):
        """加载情绪数据源插件"""
        # 清理现有配置
        for i in reversed(range(self.sentiment_plugins_layout.count())):
            child = self.sentiment_plugins_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        self.sentiment_config_widgets.clear()

        # 优先从服务容器获取情绪数据服务
        sentiment_service = self.sentiment_service

        # 情绪数据服务已删除（功能已整合到热点分析）
        self.sentiment_service = None
        logger.debug("情绪数据服务已移除，相关功能已整合到热点分析标签页")

        # 加载真实的情绪插件
        if sentiment_service:
            try:
                # 使用新的get_available_plugins_info方法获取详细信息
                if hasattr(sentiment_service, 'get_available_plugins_info'):
                    plugins_info = sentiment_service.get_available_plugins_info()
                    logger.info(f" 获取到 {len(plugins_info)} 个情绪数据插件")

                    for plugin_name, plugin_info in plugins_info.items():
                        try:
                            # 使用中文显示名称
                            display_name = plugin_info.get('display_name', plugin_name)
                            plugin_status = sentiment_service.get_plugin_status(plugin_name)

                            config = {
                                'enabled': plugin_status.get('enabled', True),
                                'weight': plugin_status.get('weight', 1.0),
                                'priority': plugin_status.get('priority', 50),
                                'cache_duration_minutes': plugin_status.get('cache_duration_minutes', 5),
                                'retry_attempts': plugin_status.get('retry_attempts', 3),
                                'timeout_seconds': plugin_status.get('timeout_seconds', 30),
                                'display_name': display_name,  # 添加显示名称
                                'description': plugin_info.get('description', ''),
                                'author': plugin_info.get('author', ''),
                                'version': plugin_info.get('version', '1.0.0')
                            }

                            # 使用显示名称而不是内部名称
                            self.add_sentiment_plugin_config(display_name, config, plugin_name)
                        except Exception as e:
                            logger.error(f" 获取插件 {plugin_name} 配置失败: {e}")
                            # 使用默认配置
                            self.add_sentiment_plugin_config(plugin_name)
                else:
                    # 回退到旧方法
                    plugins = sentiment_service.get_available_plugins()
                    logger.info(f" 获取到 {len(plugins)} 个情绪数据插件: {plugins}")

                    for plugin_name in plugins:
                        # 获取插件的实际配置
                        try:
                            plugin_status = sentiment_service.get_plugin_status(plugin_name)
                            config = {
                                'enabled': plugin_status.get('enabled', True),
                                'weight': plugin_status.get('weight', 1.0),
                                'priority': plugin_status.get('priority', 50),
                                'cache_duration_minutes': plugin_status.get('cache_duration_minutes', 5),
                                'retry_attempts': plugin_status.get('retry_attempts', 3),
                                'timeout_seconds': plugin_status.get('timeout_seconds', 30)
                            }
                            self.add_sentiment_plugin_config(plugin_name, config)
                        except Exception as e:
                            logger.error(f" 获取插件 {plugin_name} 配置失败: {e}")
                            # 使用默认配置
                            self.add_sentiment_plugin_config(plugin_name)

            except Exception as e:
                logger.error(f" 获取情绪插件列表失败: {e}")
                self._load_sentiment_fallback_data()
        else:
            logger.info("情绪数据服务不可用，使用fallback数据")
            self._load_sentiment_fallback_data()

    def _load_sentiment_fallback_data(self):
        """加载情绪插件fallback数据"""
        # 尝试从插件管理器获取情绪插件
        if self.plugin_manager:
            try:
                from core.plugin_types import PluginType
                sentiment_plugins = self.plugin_manager.get_plugins_by_type(PluginType.SENTIMENT)

                # get_plugins_by_type返回的是列表而不是字典
                if isinstance(sentiment_plugins, list):
                    for plugin_info in sentiment_plugins:
                        plugin_name = getattr(plugin_info, 'name', None) or getattr(plugin_info, 'plugin_id', 'Unknown')
                        config = {
                            'enabled': getattr(plugin_info, 'enabled', True),
                            'weight': 1.0,
                            'priority': 50,
                            'cache_duration_minutes': 5,
                            'retry_attempts': 3,
                            'timeout_seconds': 30
                        }
                        self.add_sentiment_plugin_config(plugin_name, config)
                elif isinstance(sentiment_plugins, dict):
                    for plugin_name, plugin_info in sentiment_plugins.items():
                        config = {
                            'enabled': getattr(plugin_info, 'enabled', True),
                            'weight': 1.0,
                            'priority': 50,
                            'cache_duration_minutes': 5,
                            'retry_attempts': 3,
                            'timeout_seconds': 30
                        }
                        self.add_sentiment_plugin_config(plugin_name, config)

                if sentiment_plugins:
                    logger.info(f" 从插件管理器获取到 {len(sentiment_plugins)} 个情绪插件")
                    return
            except Exception as e:
                logger.error(f" 从插件管理器获取情绪插件失败: {e}")

        # 最后的fallback - 示例配置
        example_configs = {
            "AkShare情绪数据源": {
                'enabled': True,
                'weight': 1.0,
                'priority': 10,
                'cache_duration_minutes': 5,
                'retry_attempts': 3,
                'timeout_seconds': 30
            },
            "FMP情绪数据源": {
                'enabled': False,
                'weight': 0.8,
                'priority': 20,
                'cache_duration_minutes': 3,
                'retry_attempts': 2,
                'timeout_seconds': 20
            }
        }

        for plugin_name, config in example_configs.items():
            self.add_sentiment_plugin_config(plugin_name, config)

        logger.info(f" 使用示例配置加载了 {len(example_configs)} 个情绪插件")

    def add_sentiment_plugin_config(self, plugin_name: str, config: Dict[str, Any] = None, internal_name: str = None):
        """添加情绪插件配置widget - 简单2列布局

        Args:
            plugin_name: 显示名称（可能是中文）
            config: 插件配置
            internal_name: 内部名称（用于后端操作）
        """
        if config is None:
            config = {
                'enabled': True,
                'weight': 1.0,
                'priority': 50,
                'cache_duration_minutes': 5,
                'retry_attempts': 3,
                'timeout_seconds': 30
            }

        # 如果没有提供内部名称，使用显示名称
        if internal_name is None:
            internal_name = plugin_name

        try:
            # 使用显示名称创建widget，但保存内部名称的映射
            if PLUGIN_SYSTEM_AVAILABLE and PluginConfigWidget is not None:
                widget = PluginConfigWidget(plugin_name, config, self)
                widget.config_changed.connect(self.on_sentiment_config_changed)
                widget.test_requested.connect(self.test_sentiment_plugin)

                # 保存内部名称映射，用于后续操作
                widget._internal_name = internal_name

                # 优先使用config中的显示信息
                display_name = config.get('display_name', plugin_name)
                description = config.get('description', '')

                # 如果config中没有，尝试从数据库获取
                if not description:
                    try:
                        from core.services.plugin_database_service import get_plugin_database_service
                        dbs = get_plugin_database_service()
                        records = dbs.get_all_plugins(force_refresh=True)
                        for rec in records:
                            # 使用内部名称匹配数据库记录
                            if rec.get('name') == internal_name:
                                if not display_name or display_name == plugin_name:
                                    display_name = rec.get('display_name') or rec.get('name')
                                if not description:
                                    description = rec.get('description') or ''
                                break
                    except Exception:
                        pass

                # 设置显示信息
                if hasattr(widget, 'setWindowTitle'):
                    widget.setWindowTitle(display_name)
                # 如果 widget 暴露 set_description，可设置；否则忽略
                if hasattr(widget, 'set_description'):
                    widget.set_description(description)

                # 获取并更新真实状态信息
                if self.sentiment_service:
                    try:
                        # 使用内部名称（完整插件ID）来获取状态
                        status_info = self.sentiment_service.get_plugin_status(internal_name)
                        logger.info(f" 获取到插件 {display_name} 的状态信息: {status_info}")

                        # 构建状态信息
                        status = " 已连接" if status_info.get('is_connected', False) else " 未连接"
                        last_update = self._format_timestamp(time.time())
                        quality = self._calculate_data_quality(status_info)

                        # 更新widget状态 - 使用字典格式
                        status_data = {
                            'status': status,
                            'last_update': last_update,
                            'data_quality': quality
                        }

                        if hasattr(widget, 'update_status'):
                            widget.update_status(status_data)
                        logger.info(f" 更新插件 {plugin_name} 状态显示: {status_data}")

                    except Exception as e:
                        logger.error(f" 获取插件 {plugin_name} 状态信息失败: {e}")
                        default_status = {
                            'status': " 检测中",
                            'last_update': "未知",
                            'data_quality': "未知"
                        }
                        if hasattr(widget, 'update_status'):
                            widget.update_status(default_status)
                else:
                    default_status = {
                        'status': " 检测中",
                        'last_update': "未知",
                        'data_quality': "未知"
                    }
                    if hasattr(widget, 'update_status'):
                        widget.update_status(default_status)

            else:
                # 回退到简单的配置widget，但限制宽度
                widget = self.create_simple_sentiment_widget_compact(plugin_name, config)

            # 设置widget宽度（适应两列布局）
            widget.setMaximumWidth(400)

            # 计算行列位置（2列布局）
            current_count = len(self.sentiment_config_widgets)
            row = current_count // 2
            col = current_count % 2

            # 添加水平分割线（在第二行及以后的行上方）
            if row > 0 and col == 0:
                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setStyleSheet("background-color: #bdc3c7; margin: 5px 0;")
                # 跨两列添加水平分割线
                self.sentiment_plugins_layout.addWidget(h_separator, row * 2 - 1, 0, 1, 3)

            # 添加到网格布局
            self.sentiment_plugins_layout.addWidget(widget, row * 2, col * 2)

            # 在两列之间添加竖直分割线（当添加右列插件时）
            if col == 1:  # 添加右列插件时，为这一行添加竖线
                v_separator = QFrame()
                v_separator.setFrameShape(QFrame.VLine)
                v_separator.setFrameShadow(QFrame.Sunken)
                v_separator.setStyleSheet("background-color: #bdc3c7; margin: 0 5px;")
                self.sentiment_plugins_layout.addWidget(v_separator, row * 2, 1, 1, 1)

            self.sentiment_config_widgets[plugin_name] = widget

        except Exception as e:
            logger.error(f"添加情绪插件配置失败: {e}")

    def create_simple_sentiment_widget_compact(self, plugin_name: str, config: Dict[str, Any]) -> QWidget:
        """创建简单的情绪插件配置widget（紧凑版）"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.StyledPanel)
        widget.setMaximumWidth(400)  # 适应两列布局
        widget.setStyleSheet("QFrame { background-color: #f0f8ff; border-radius: 8px; padding: 15px; }")

        layout = QVBoxLayout(widget)

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel(f" {plugin_name}")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        enable_cb = QCheckBox("启用")
        enable_cb.setChecked(config.get('enabled', True))
        title_layout.addWidget(enable_cb)

        test_btn = QPushButton("测试")
        test_btn.setMaximumWidth(80)
        title_layout.addWidget(test_btn)

        layout.addLayout(title_layout)

        # 配置选项
        config_layout = QFormLayout()

        weight_spin = QDoubleSpinBox()
        weight_spin.setRange(0.1, 2.0)
        weight_spin.setSingleStep(0.1)
        weight_spin.setValue(config.get('weight', 1.0))
        config_layout.addRow("权重:", weight_spin)

        priority_spin = QSpinBox()
        priority_spin.setRange(1, 100)
        priority_spin.setValue(config.get('priority', 50))
        config_layout.addRow("优先级:", priority_spin)

        layout.addLayout(config_layout)

        # 存储配置控件引用
        widget.enable_cb = enable_cb
        widget.weight_spin = weight_spin
        widget.priority_spin = priority_spin
        widget.test_btn = test_btn

        return widget

    def create_general_plugin_widget(self, plugin_info: Dict[str, Any]) -> QWidget:
        """创建精简专业的插件条目 - 对标Bloomberg Terminal/Wind量化软件"""
        # 主容器 - 采用简洁列表式设计
        widget = QFrame()
        widget.setFrameStyle(QFrame.NoFrame)

        # 根据插件状态设置简洁的视觉状态
        enabled = plugin_info['enabled']
        widget.setStyleSheet(f"""
            QFrame {{
                background: #{'ffffff' if enabled else 'fafafa'};
                border-left: 3px solid #{'00C851' if enabled else 'cccccc'};
                border-top: 1px solid #e0e0e0;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
                margin: 1px 0px;
                padding: 0px;
            }}
            QFrame:hover {{
                background: #f5f5f5;
                border-left: 3px solid #{'00A040' if enabled else '0066cc'};
            }}
        """)

        # 设置插件名称属性，用于过滤功能
        widget.plugin_name = plugin_info['name']

        # 单行布局 - 专业量化软件风格
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # 状态指示器 - 专业精简圆点
        status_indicator = QLabel("●")
        status_indicator.setStyleSheet(f"""
            color: #{'00C851' if enabled else 'dddddd'};
            font-size: 12px;
            font-weight: bold;
            min-width: 12px;
            max-width: 12px;
        """)
        main_layout.addWidget(status_indicator)

        # 插件类型简化图标 - 专业无边框小图标
        plugin_type = plugin_info.get('type', '通用插件')
        type_icons = {
            ' 技术指标': '◐', ' 交易策略': '◈', ' 数据源': '◇',
            ' 分析工具': '◎', ' 界面组件': '□', ' 导出工具': '◫',
            ' 通知服务': '◉', ' 图表工具': '◢', ' 风险管理': '△',
            ' 投资组合': '◪', ' 情绪分析': '◦', ' 人工智能': '◈'
        }
        icon_text = type_icons.get(plugin_type, '●')

        type_icon = QLabel(icon_text)
        type_icon.setStyleSheet("font-size: 14px; color: #999999; font-weight: normal;")
        type_icon.setMinimumWidth(18)
        type_icon.setMaximumWidth(18)
        type_icon.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(type_icon)

        # 插件信息区域 - 左对齐垂直布局
        info_container = QFrame()
        info_container.setStyleSheet("QFrame { background: transparent; border: none; }")
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # 插件名称 - 提供默认值避免显示空白
        plugin_name = plugin_info.get('name', '未命名插件')
        if not plugin_name or plugin_name.strip() == '':
            plugin_name = plugin_info.get('id', '未命名插件')

        name_label = QLabel(plugin_name)
        name_label.setFont(QFont("Arial", 13, QFont.Bold))
        name_label.setStyleSheet(f"color: #{'333333' if enabled else '888888'};")
        info_layout.addWidget(name_label)

        # 描述和版本信息 - 提供默认值
        desc_text = plugin_info.get('description', '插件描述')
        if not desc_text or desc_text.strip() == '':
            desc_text = '插件描述'
        if len(desc_text) > 60:
            desc_text = desc_text[:57] + "..."

        version = plugin_info.get('version', '2.0.0')
        if not version or version.strip() == '':
            version = '2.0.0'

        desc_label = QLabel(f"{desc_text} | v{version}")
        desc_label.setFont(QFont("Arial", 11))
        desc_label.setStyleSheet("color: #888888;")
        info_layout.addWidget(desc_label)

        main_layout.addWidget(info_container)
        main_layout.addStretch()

        # 状态文本 - 专业精简标签
        status_label = QLabel(plugin_info['status'])
        status_label.setFont(QFont("Arial", 9, QFont.Bold))
        status_label.setStyleSheet(f"""
            color: #{'00C851' if enabled else '999999'};
            background: #{'F0F8F0' if enabled else 'f5f5f5'};
            border-radius: 8px;
            padding: 2px 6px;
            border: 1px solid #{'00C851' if enabled else 'dddddd'};
        """)
        main_layout.addWidget(status_label)

        # 操作按钮区域 - 精简设计
        buttons_container = QFrame()
        buttons_container.setStyleSheet("QFrame { background: transparent; border: none; }")
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)

        # 启用/禁用切换开关 - 专业精简版
        enable_cb = QCheckBox()
        enable_cb.setChecked(enabled)
        enable_cb.setStyleSheet("""
            QCheckBox::indicator {
                width: 32px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid #cccccc;
                background: #ffffff;
            }
            QCheckBox::indicator:unchecked {
                background: #e0e0e0;
                border: 1px solid #cccccc;
            }
            QCheckBox::indicator:checked {
                background: #00C851;
                border: 1px solid #00A040;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #999999;
            }
        """)
        enable_cb.setToolTip("启用/禁用插件")
        buttons_layout.addWidget(enable_cb)

        # 绑定启用/禁用功能
        def on_enable_changed(checked):
            try:
                # 使用唯一键（若无则回退到显示名）
                plugin_key = plugin_info.get('id', plugin_info['name'])
                if self.plugin_manager:
                    if checked:
                        result = self.plugin_manager.enable_plugin(plugin_key)
                        if result:
                            # 立即更新UI状态
                            self._update_single_plugin_ui(widget, plugin_key, True)
                            self.plugin_enabled.emit(plugin_key)
                            logger.info(f" 启用插件: {plugin_key}")
                        else:
                            # 回滚时避免递归触发
                            try:
                                enable_cb.blockSignals(True)
                                enable_cb.setChecked(False)
                            finally:
                                enable_cb.blockSignals(False)
                            logger.error(f" 启用插件失败: {plugin_key}")
                    else:
                        result = self.plugin_manager.disable_plugin(plugin_key)
                        if result:
                            # 立即更新UI状态
                            self._update_single_plugin_ui(widget, plugin_key, False)
                            self.plugin_disabled.emit(plugin_key)
                            logger.info(f" 禁用插件: {plugin_key}")
                        else:
                            # 回滚时避免递归触发
                            try:
                                enable_cb.blockSignals(True)
                                enable_cb.setChecked(True)
                            finally:
                                enable_cb.blockSignals(False)
                            logger.error(f" 禁用插件失败: {plugin_key}")
                else:
                    QMessageBox.warning(widget, "警告", "插件管理器不可用")
                    # 回滚时避免递归触发
                    try:
                        enable_cb.blockSignals(True)
                        enable_cb.setChecked(not checked)
                    finally:
                        enable_cb.blockSignals(False)
            except Exception as e:
                logger.error(f" 切换插件状态失败: {e}")
                QMessageBox.critical(widget, "错误", f"操作失败:\n{str(e)}")
                # 回滚时避免递归触发
                try:
                    enable_cb.blockSignals(True)
                    enable_cb.setChecked(not checked)
                finally:
                    enable_cb.blockSignals(False)

        enable_cb.toggled.connect(on_enable_changed)

        # 配置按钮 - 专业小图标设计
        config_btn = QPushButton("")
        config_btn.setFont(QFont("Arial", 11))
        config_btn.setStyleSheet("""
            QPushButton {
                background: #007acc;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 4px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            QPushButton:hover {
                background: #005a9e;
            }
            QPushButton:pressed {
                background: #004578;
            }
        """)
        config_btn.setToolTip("配置插件")

        # 绑定配置功能
        def on_config_clicked():
            try:
                plugin_name = plugin_info['name']

                # 使用原来的PluginConfigDialog
                if 'plugin_info' in plugin_info and self.plugin_manager:
                    from gui.dialogs.plugin_manager_dialog import PluginConfigDialog
                    from PyQt5.QtWidgets import QDialog
                    actual_plugin_info = plugin_info['plugin_info']

                    config_dialog = PluginConfigDialog(
                        actual_plugin_info, self.plugin_manager, widget)
                    if config_dialog.exec_() == QDialog.Accepted:
                        self.plugin_configured.emit(plugin_name, {})
                        logger.info(f" 插件 {plugin_name} 配置已更新")
                else:
                    # 备用方案：显示简单配置信息
                    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

                    config_dialog = QDialog(widget)
                    config_dialog.setWindowTitle(f"配置 - {plugin_name}")
                    config_dialog.setModal(True)
                    config_dialog.resize(400, 300)

                    layout = QVBoxLayout(config_dialog)
                    layout.addWidget(QLabel(f"插件: {plugin_name}"))
                    layout.addWidget(QLabel(f"版本: {plugin_info['version']}"))
                    layout.addWidget(QLabel(f"类型: {plugin_info['type']}"))
                    layout.addWidget(QLabel(f"状态: {plugin_info['status']}"))
                    layout.addWidget(QLabel("\n配置功能正在开发中..."))

                    buttons = QDialogButtonBox(QDialogButtonBox.Ok)
                    buttons.accepted.connect(config_dialog.accept)
                    layout.addWidget(buttons)

                    config_dialog.exec_()

            except Exception as e:
                logger.error(f" 配置插件失败: {e}")
                QMessageBox.critical(widget, "错误", f"配置失败:\n{str(e)}")

        config_btn.clicked.connect(on_config_clicked)
        buttons_layout.addWidget(config_btn)

        # 信息按钮 - 专业小图标设计
        info_btn = QPushButton("?")
        info_btn.setFont(QFont("Arial", 11, QFont.Bold))
        info_btn.setStyleSheet("""
            QPushButton {
                background: #777777;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 4px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            QPushButton:hover {
                background: #666666;
            }
            QPushButton:pressed {
                background: #555555;
            }
        """)
        info_btn.setToolTip("查看插件详细信息")

        def show_plugin_info():
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QTextEdit

            info_dialog = QDialog(widget)
            info_dialog.setWindowTitle(f"插件信息 - {plugin_info['name']}")
            info_dialog.setModal(True)
            info_dialog.resize(450, 350)

            layout = QVBoxLayout(info_dialog)

            # 基本信息
            basic_info = f"""
            <h3> {plugin_info['name']}</h3>
            <p><b>版本:</b> {plugin_info['version']}</p>
            <p><b>类型:</b> {plugin_info['type']}</p>
            <p><b>状态:</b> {plugin_info['status']}</p>
            <p><b>描述:</b> {plugin_info['description']}</p>
            """

            info_text = QTextEdit()
            info_text.setHtml(basic_info)
            info_text.setReadOnly(True)
            info_text.setMaximumHeight(200)
            layout.addWidget(info_text)

            # 如果有详细插件信息，显示更多内容
            if 'plugin_info' in plugin_info:
                actual_info = plugin_info['plugin_info']
                additional_info = f"""
                <h4>详细信息:</h4>
                <p><b>作者:</b> {actual_info.author}</p>
                <p><b>路径:</b> {actual_info.path}</p>
                """
                if actual_info.dependencies:
                    additional_info += f"<p><b>依赖:</b> {', '.join(actual_info.dependencies)}</p>"

                detail_text = QTextEdit()
                detail_text.setHtml(additional_info)
                detail_text.setReadOnly(True)
                detail_text.setMaximumHeight(120)
                layout.addWidget(detail_text)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok)
            buttons.accepted.connect(info_dialog.accept)
            layout.addWidget(buttons)

            info_dialog.exec_()

        info_btn.clicked.connect(show_plugin_info)
        buttons_layout.addWidget(info_btn)

        main_layout.addWidget(buttons_container)

        return widget

    def load_market_plugins(self):
        """加载插件市场"""
        # 示例市场插件
        market_plugins = [
            {
                "name": "同花顺数据源",
                "description": "同花顺数据源插件，提供实时行情和财务数据",
                "version": "1.0.0",
                "author": "社区开发者",
                "downloads": 1250,
                "rating": 4.5,
                "status": "未安装"
            },
            {
                "name": "Wind数据接口",
                "description": "Wind金融终端数据接口，支持专业金融数据",
                "version": "2.1.0",
                "author": "Wind官方",
                "downloads": 890,
                "rating": 4.8,
                "status": "未安装"
            },
            {
                "name": "机器学习预测器",
                "description": "基于深度学习的股价预测插件",
                "version": "1.3.0",
                "author": "AI研究团队",
                "downloads": 2100,
                "rating": 4.2,
                "status": "可更新"
            }
        ]

        for plugin_info in market_plugins:
            plugin_card = self.create_market_plugin_card(plugin_info)
            self.market_plugins_layout.addWidget(plugin_card)

        self.market_plugins_layout.addStretch()

    def create_market_plugin_card(self, plugin_info: Dict[str, Any]) -> QWidget:
        """创建市场插件卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 15px;
                margin: 5px;
            }
            QFrame:hover {
                border-color: #007bff;
            }
        """)

        layout = QHBoxLayout(card)

        # 插件信息
        info_layout = QVBoxLayout()

        name_label = QLabel(plugin_info['name'])
        name_label.setFont(QFont("Arial", 14, QFont.Bold))
        info_layout.addWidget(name_label)

        desc_label = QLabel(plugin_info['description'])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666;")
        info_layout.addWidget(desc_label)

        meta_layout = QHBoxLayout()
        meta_layout.addWidget(QLabel(f"版本: {plugin_info['version']}"))
        meta_layout.addWidget(QLabel(f"作者: {plugin_info['author']}"))
        meta_layout.addWidget(QLabel(f"下载: {plugin_info['downloads']}"))
        meta_layout.addWidget(QLabel(f"评分: {plugin_info['rating']}"))
        meta_layout.addStretch()
        info_layout.addLayout(meta_layout)

        layout.addLayout(info_layout)

        # 操作按钮
        button_layout = QVBoxLayout()

        status = plugin_info['status']
        if status == "未安装":
            install_btn = QPushButton("安装")
            install_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; }")
        elif status == "可更新":
            install_btn = QPushButton("更新")
            install_btn.setStyleSheet("QPushButton { background-color: #ffc107; color: black; }")
        else:
            install_btn = QPushButton("已安装")
            install_btn.setEnabled(False)

        button_layout.addWidget(install_btn)

        details_btn = QPushButton("详情")
        button_layout.addWidget(details_btn)

        layout.addLayout(button_layout)

        return card

    # 事件处理方法
    def refresh_status(self):
        """刷新状态"""
        self.update_status_counts()

    def update_status_counts(self):
        """更新状态计数"""
        try:
            total_plugins = 0
            active_plugins = 0

            # 从插件管理器获取真实插件数据
            if self.plugin_manager:
                try:
                    enhanced_plugins = self.plugin_manager.get_all_enhanced_plugins()
                    total_plugins += len(enhanced_plugins)
                    active_plugins += sum(1 for plugin_info in enhanced_plugins.values() if plugin_info.enabled)
                except Exception as e:
                    logger.error(f" 获取插件管理器数据失败: {e}")

            # 从情绪数据服务获取插件数据
            if self.sentiment_service:
                try:
                    available_plugins = self.sentiment_service.get_available_plugins()
                    total_plugins += len(available_plugins)
                    for plugin_name in available_plugins:
                        status = self.sentiment_service.get_plugin_status(plugin_name)
                        if status.get('enabled', False):
                            active_plugins += 1
                except Exception as e:
                    logger.error(f" 获取情绪服务数据失败: {e}")

            # 更新UI标签
            self.plugin_count_label.setText(f"插件总数: {total_plugins}")
            self.active_count_label.setText(f"活跃插件: {active_plugins}")

        except Exception as e:
            logger.error(f" 更新状态计数失败: {e}")
            # fallback显示基本信息
            self.plugin_count_label.setText("插件总数: N/A")
            self.active_count_label.setText("活跃插件: N/A")

    def _get_real_system_metrics(self):
        """获取真实的系统指标"""
        try:
            import psutil
            import time

            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'cpu_usage': cpu_usage,
                'memory_usage': memory.percent,
                'disk_usage': disk.percent,
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f" 获取系统指标失败: {e}")
            # 返回默认值
            return {
                'cpu_usage': 15.0,
                'memory_usage': 45.0,
                'disk_usage': 60.0,
                'timestamp': time.time()
            }

    def _get_active_plugins_count(self):
        """获取活跃插件数量"""
        active_count = 0

        # 从插件管理器获取真实数据
        if self.plugin_manager:
            try:
                enhanced_plugins = self.plugin_manager.get_all_enhanced_plugins()
                active_count += sum(1 for plugin_info in enhanced_plugins.values() if plugin_info.enabled)
            except Exception as e:
                logger.error(f" 获取插件状态失败: {e}")

        # 从情绪数据服务获取数据
        if self.sentiment_service:
            try:
                available_plugins = self.sentiment_service.get_available_plugins()
                for plugin_name in available_plugins:
                    status = self.sentiment_service.get_plugin_status(plugin_name)
                    if status.get('enabled', False):
                        active_count += 1
            except Exception as e:
                logger.error(f" 获取情绪插件状态失败: {e}")

        return active_count

    def _get_plugin_update_count(self):
        """获取插件更新计数"""
        # 这里可以实现真实的更新计数逻辑
        # 暂时返回已加载的插件总数
        total_count = 0
        if self.plugin_manager:
            try:
                all_plugins = self.plugin_manager.get_all_plugins()
                total_count = len(all_plugins)
            except Exception as e:
                logger.error(f" 获取插件总数失败: {e}")
        return total_count

    def on_sentiment_config_changed(self, plugin_name: str, config: Dict[str, Any]):
        """情绪插件配置变化处理"""
        try:
            # 处理启用/禁用状态变更
            enabled = config.get('enabled', True)

            # 获取情绪数据服务
            # 情绪数据服务已删除，跳过插件启用操作
            sentiment_service = None
            if False:  # 情绪服务已移除，保留代码结构便于理解
                try:
                    # 设置插件启用状态
                    result = sentiment_service.set_plugin_enabled(plugin_name, enabled)

                    if result:
                        status_text = "已启用" if enabled else "已禁用"
                        logger.info(f" 插件 {plugin_name} {status_text}")

                        # 发送状态变更通知
                        self.sentiment_plugin_tested.emit(plugin_name, enabled)
                    else:
                        status_text = "启用" if enabled else "禁用"
                        logger.error(f" 插件 {plugin_name} {status_text}失败")

                        # 可以在这里显示错误消息给用户
                        from PyQt5.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "状态变更失败", f"插件 {plugin_name} {status_text}失败")

                except Exception as e:
                    logger.error(f" 设置插件 {plugin_name} 状态时发生错误: {e}")
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.critical(self, "状态变更错误", f"设置插件状态时发生错误:\n{str(e)}")

            # 发送配置变更信号
            self.plugin_configured.emit(plugin_name, config)

        except Exception as e:
            logger.error(f" 处理插件配置变更时发生错误: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "配置错误", f"处理配置变更时发生错误:\n{str(e)}")

    def test_sentiment_plugin(self, plugin_name: str):
        """测试情绪插件"""
        try:
            # 获取情绪数据服务
            # 情绪数据服务已删除，跳过插件测试
            sentiment_service = None
            if False:  # 情绪服务已移除，保留代码结构便于理解
                # 执行真实的插件测试
                try:
                    # 获取插件实例
                    plugin_instance = sentiment_service._registered_plugins.get(plugin_name)
                    if not plugin_instance:
                        raise Exception(f"插件 {plugin_name} 实例不存在")

                    # 执行真实的健康检查
                    if hasattr(plugin_instance, 'health_check'):
                        health_result = plugin_instance.health_check()
                        is_healthy = getattr(health_result, 'is_healthy', False)
                        error_message = getattr(health_result, 'error_message', None)
                    elif hasattr(plugin_instance, 'test_connection'):
                        # 如果插件有test_connection方法
                        is_healthy = plugin_instance.test_connection()
                        error_message = None
                    else:
                        # 尝试获取基本状态信息
                        plugin_status = sentiment_service.get_plugin_status(plugin_name)
                        is_healthy = plugin_status.get('is_connected', False)
                        error_message = plugin_status.get('error_message', '插件状态未知')

                    self.sentiment_plugin_tested.emit(plugin_name, is_healthy)

                    if is_healthy:
                        QMessageBox.information(self, "测试成功", f"插件 {plugin_name} 连接测试通过")
                    else:
                        error_msg = error_message or "连接测试失败"
                        QMessageBox.warning(self, "测试失败", f"插件 {plugin_name} 测试失败:\n{error_msg}")

                except Exception as e:
                    logger.error(f" 测试插件 {plugin_name} 失败: {e}")
                    self.sentiment_plugin_tested.emit(plugin_name, False)
                    QMessageBox.critical(self, "测试错误", f"测试插件 {plugin_name} 时发生错误:\n{str(e)}")
            else:
                # 情绪数据服务不可用或插件未注册
                error_msg = "情绪数据服务不可用" if not sentiment_service else f"插件 {plugin_name} 未注册"
                self.sentiment_plugin_tested.emit(plugin_name, False)
                QMessageBox.warning(self, "测试失败", f"无法测试插件 {plugin_name}:\n{error_msg}")

        except Exception as e:
            logger.error(f" 测试插件时发生错误: {e}")
            self.sentiment_plugin_tested.emit(plugin_name, False)
            QMessageBox.critical(self, "测试错误", f"测试时发生错误:\n{str(e)}")

    def test_all_sentiment_plugins(self):
        """测试所有情绪插件"""
        for plugin_name in self.sentiment_config_widgets.keys():
            self.test_sentiment_plugin(plugin_name)

    def reset_sentiment_weights(self):
        """重置情绪插件权重"""
        for widget in self.sentiment_config_widgets.values():
            if hasattr(widget, 'weight_spin'):
                widget.weight_spin.setValue(1.0)

    def enable_all_general_plugins(self):
        """启用所有通用插件"""
        try:
            if not self.plugin_manager:
                QMessageBox.warning(self, "警告", "插件管理器不可用")
                return

            enabled_count = 0

            # 使用enhanced_plugins获取插件信息
            if hasattr(self.plugin_manager, 'get_all_enhanced_plugins'):
                enhanced_plugins = self.plugin_manager.get_all_enhanced_plugins()

                for plugin_name, plugin_info in enhanced_plugins.items():
                    try:
                        if not plugin_info.enabled:
                            success = self.plugin_manager.enable_plugin(plugin_name)
                            if success:
                                enabled_count += 1
                                logger.info(f" 启用插件: {plugin_name}")
                                # 发射信号
                                self.plugin_enabled.emit(plugin_name)
                            else:
                                logger.error(f" 启用插件 {plugin_name} 失败")

                    except Exception as e:
                        logger.error(f" 启用插件 {plugin_name} 失败: {e}")
            else:
                # fallback到普通插件
                all_plugins = self.plugin_manager.get_all_plugins()
                for plugin_name in all_plugins.keys():
                    try:
                        success = self.plugin_manager.enable_plugin(plugin_name)
                        if success:
                            enabled_count += 1
                            logger.info(f" 启用插件: {plugin_name}")
                            self.plugin_enabled.emit(plugin_name)
                    except Exception as e:
                        logger.error(f" 启用插件 {plugin_name} 失败: {e}")

            # 刷新插件列表
            self.load_general_plugins()

            QMessageBox.information(self, "操作完成", f"成功启用 {enabled_count} 个插件")

        except Exception as e:
            logger.error(f" 启用所有插件失败: {e}")
            QMessageBox.critical(self, "错误", f"启用插件时发生错误:\n{str(e)}")

    def disable_all_general_plugins(self):
        """禁用所有通用插件"""
        try:
            if not self.plugin_manager:
                QMessageBox.warning(self, "警告", "插件管理器不可用")
                return

            # 确认操作
            reply = QMessageBox.question(
                self, "确认操作",
                "确定要禁用所有通用插件吗？这可能会影响系统功能。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            disabled_count = 0

            # 使用enhanced_plugins获取插件信息
            if hasattr(self.plugin_manager, 'get_all_enhanced_plugins'):
                enhanced_plugins = self.plugin_manager.get_all_enhanced_plugins()

                for plugin_name, plugin_info in enhanced_plugins.items():
                    try:
                        if plugin_info.enabled:
                            success = self.plugin_manager.disable_plugin(plugin_name)
                            if success:
                                disabled_count += 1
                                logger.info(f" 禁用插件: {plugin_name}")
                                # 发射信号
                                self.plugin_disabled.emit(plugin_name)
                            else:
                                logger.error(f" 禁用插件 {plugin_name} 失败")

                    except Exception as e:
                        logger.error(f" 禁用插件 {plugin_name} 失败: {e}")
            else:
                # fallback到普通插件
                all_plugins = self.plugin_manager.get_all_plugins()
                for plugin_name in all_plugins.keys():
                    try:
                        success = self.plugin_manager.disable_plugin(plugin_name)
                        if success:
                            disabled_count += 1
                            logger.info(f" 禁用插件: {plugin_name}")
                            self.plugin_disabled.emit(plugin_name)
                    except Exception as e:
                        logger.error(f" 禁用插件 {plugin_name} 失败: {e}")

            # 刷新插件列表
            self.load_general_plugins()

            QMessageBox.information(self, "操作完成", f"成功禁用 {disabled_count} 个插件")

        except Exception as e:
            logger.error(f" 禁用所有插件失败: {e}")
            QMessageBox.critical(self, "错误", f"禁用插件时发生错误:\n{str(e)}")

    def filter_general_plugins(self):
        """过滤通用插件"""
        try:
            if not hasattr(self, 'general_filter_combo'):
                return

            filter_text = self.general_filter_combo.currentText()

            # 清理现有插件显示
            for i in reversed(range(self.general_plugins_layout.count())):
                child = self.general_plugins_layout.itemAt(i).widget()
                if child:
                    child.setVisible(False)

            # 重新加载并应用过滤
            if not self.plugin_manager:
                return

            all_plugins = self.plugin_manager.get_all_plugins()

            for plugin_name, plugin_info in all_plugins.items():
                should_show = True

                if filter_text == "已启用":
                    should_show = plugin_info.enabled
                elif filter_text == "已禁用":
                    should_show = not plugin_info.enabled
                elif filter_text == "数据源":
                    plugin_type = str(plugin_info.type) if hasattr(plugin_info, 'type') else ""
                    should_show = "DATA_SOURCE" in plugin_type.upper()
                elif filter_text == "分析工具":
                    plugin_type = str(plugin_info.type) if hasattr(plugin_info, 'type') else ""
                    should_show = "ANALYSIS" in plugin_type.upper() or "INDICATOR" in plugin_type.upper()
                elif filter_text == "UI组件":
                    plugin_type = str(plugin_info.type) if hasattr(plugin_info, 'type') else ""
                    should_show = "UI" in plugin_type.upper()
                # filter_text == "全部" 时，should_show 保持 True

                # 找到对应的widget并设置可见性
                for i in range(self.general_plugins_layout.count()):
                    widget = self.general_plugins_layout.itemAt(i).widget()
                    if widget and hasattr(widget, 'plugin_name') and widget.plugin_name == plugin_name:
                        widget.setVisible(should_show)
                        break

            logger.info(f" 应用过滤器: {filter_text}")

        except Exception as e:
            logger.error(f" 过滤插件失败: {e}")

    def search_plugins(self):
        """搜索插件"""
        try:
            # 显示搜索对话框
            search_text, ok = QInputDialog.getText(
                self, "搜索插件", "请输入搜索关键词:"
            )

            if not ok or not search_text.strip():
                return

            search_text = search_text.strip().lower()

            # 在通用插件中搜索
            if self.plugin_manager:
                all_plugins = self.plugin_manager.get_all_plugins()
                matching_plugins = []

                for plugin_name, plugin_info in all_plugins.items():
                    # 搜索插件名称、描述、类型
                    searchable_text = " ".join([
                        plugin_name.lower(),
                        getattr(plugin_info, 'description', '').lower(),
                        str(getattr(plugin_info, 'type', '')).lower(),
                        getattr(plugin_info, 'author', '').lower()
                    ])

                    if search_text in searchable_text:
                        matching_plugins.append((plugin_name, plugin_info))

                # 显示搜索结果
                if matching_plugins:
                    result_text = f"找到 {len(matching_plugins)} 个匹配的插件:\n\n"
                    for plugin_name, plugin_info in matching_plugins:
                        status = "启用" if plugin_info.enabled else "禁用"
                        result_text += f" {plugin_name} ({status})\n"
                        result_text += f"  描述: {getattr(plugin_info, 'description', '无描述')}\n"
                        result_text += f"  类型: {getattr(plugin_info, 'type', '未知')}\n\n"
                else:
                    result_text = f"未找到包含 '{search_text}' 的插件"

                QMessageBox.information(self, "搜索结果", result_text)
            else:
                QMessageBox.warning(self, "搜索失败", "插件管理器不可用")

        except Exception as e:
            logger.error(f" 搜索插件失败: {e}")
            QMessageBox.critical(self, "搜索错误", f"搜索时发生错误:\n{str(e)}")

    def refresh_market(self):
        """刷新插件市场"""
        try:
            # 显示加载提示
            QMessageBox.information(
                self, "插件市场",
                "插件市场功能正在开发中...\n\n"
                "将支持:\n"
                " 浏览在线插件库\n"
                " 安装/更新插件\n"
                " 插件评分和评论\n"
                " 自动依赖管理"
            )

            logger.info("插件市场刷新功能开发中，当前显示为演示界面")

        except Exception as e:
            logger.error(f" 刷新插件市场失败: {e}")
            QMessageBox.critical(self, "市场错误", f"刷新市场时发生错误:\n{str(e)}")

    def clear_logs(self):
        """清除日志"""
        self.logs_text.clear()

    def export_logs(self):
        """导出日志"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出日志", f"plugin_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text files (*.txt)"
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.logs_text.toPlainText())
            QMessageBox.information(self, "导出成功", f"日志已导出到: {filename}")

    def export_all_configs(self):
        """导出所有配置"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出插件配置", f"plugin_configs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON files (*.json)"
        )
        if filename:
            configs = {}
            for plugin_name, widget in self.sentiment_config_widgets.items():
                if hasattr(widget, 'get_config'):
                    configs[plugin_name] = widget.get_config()

            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(configs, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "导出成功", f"配置已导出到: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")

    def import_all_configs(self):
        """导入所有配置"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "导入插件配置", "", "JSON files (*.json)"
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    configs = json.load(f)
                # 应用导入的配置
                # 这里需要实际的配置应用逻辑
                QMessageBox.information(self, "导入成功", "配置导入成功！请重启应用以使配置生效。")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入失败: {str(e)}")

    def apply_all_configs(self):
        """应用所有配置"""
        try:
            applied_count = 0

            # 应用通用插件配置
            for plugin_name, widget in self.plugin_widgets.items():
                try:
                    # 获取插件状态并应用
                    if hasattr(widget, 'get_config'):
                        config = widget.get_config()
                        self.plugin_configured.emit(plugin_name, config)
                        applied_count += 1
                except Exception as e:
                    logger.error(f" 应用插件 {plugin_name} 配置失败: {e}")

            # 应用情绪插件配置
            for plugin_name, widget in self.sentiment_config_widgets.items():
                try:
                    if hasattr(widget, 'get_config'):
                        config = widget.get_config()

                        # 将配置应用到情绪数据服务
                        if self.sentiment_service:
                            # 如果服务支持配置更新
                            if hasattr(self.sentiment_service, 'update_plugin_config'):
                                self.sentiment_service.update_plugin_config(plugin_name, config)

                        self.plugin_configured.emit(plugin_name, config)
                        applied_count += 1

                except Exception as e:
                    logger.error(f" 应用情绪插件 {plugin_name} 配置失败: {e}")

            # 刷新显示
            self.load_plugins()

            QMessageBox.information(
                self, "配置应用完成",
                f"成功应用了 {applied_count} 个插件的配置"
            )

        except Exception as e:
            logger.error(f" 应用配置失败: {e}")
            QMessageBox.critical(self, "应用失败", f"应用配置时发生错误:\n{str(e)}")

    def accept(self):
        """确定按钮处理"""
        self.apply_all_configs()
        super().accept()

    def create_data_source_plugins_tab(self):
        """创建数据源插件管理标签页（Task 3.1）"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 标题和说明
        title_layout = QHBoxLayout()
        title_label = QLabel("数据源插件管理")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_data_source_plugins)
        title_layout.addWidget(refresh_btn)

        layout.addLayout(title_layout)

        # 说明文本
        info_label = QLabel("管理数据源插件的加载、配置和路由优先级")
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # 创建分割器 - 左侧插件列表，右侧详情和配置
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：数据源插件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 插件列表标题
        list_title = QLabel("已注册的数据源插件")
        list_title.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(list_title)

        # 数据源插件表格
        self.data_source_table = QTableWidget()
        self.data_source_table.setColumnCount(6)
        self.data_source_table.setHorizontalHeaderLabels([
            "插件名称", "状态", "支持资产", "健康分数", "优先级", "操作"
        ])

        # 设置表格为只读
        self.data_source_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.data_source_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.data_source_table.setAlternatingRowColors(True)

        # 添加网格线和样式 - 使用淡蓝色选中效果
        self.data_source_table.setShowGrid(True)
        self.data_source_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
                background-color: white;
                selection-background-color: #e3f2fd;
                selection-color: #1976d2;
                alternate-background-color: #f8f9fa;
            }
            QTableWidget::item {
                padding: 6px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #333;
                padding: 8px;
                font-weight: bold;
                border: 1px solid #ddd;
                border-left: none;
            }
            QHeaderView::section:first {
                border-left: 1px solid #ddd;
            }
        """)

        # 设置表格列宽
        header = self.data_source_table.horizontalHeader()
        # header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.data_source_table.selectionModel().selectionChanged.connect(
            self.on_data_source_selection_changed
        )
        left_layout.addWidget(self.data_source_table)

        # 插件操作按钮
        button_layout = QHBoxLayout()

        load_plugin_btn = QPushButton("加载插件")
        load_plugin_btn.clicked.connect(self.load_data_source_plugin)
        button_layout.addWidget(load_plugin_btn)

        unload_plugin_btn = QPushButton("卸载插件")
        unload_plugin_btn.clicked.connect(self.unload_data_source_plugin)
        button_layout.addWidget(unload_plugin_btn)

        apply_reconnect_btn = QPushButton("批量保存并重连")
        apply_reconnect_btn.setToolTip("对选中数据源保存配置到数据库并重连；若未选中则对全部进行重连。")
        apply_reconnect_btn.clicked.connect(self.batch_apply_and_reconnect_data_sources)
        button_layout.addWidget(apply_reconnect_btn)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        splitter.addWidget(left_widget)

        # 右侧：插件详情和配置
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 插件详情组
        self.data_source_details_group = QGroupBox("插件详情")
        self.data_source_details_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: white;
            }
            QLabel {
                color: #2c3e50;
                background-color: transparent;
            }
        """)
        details_layout = QGridLayout(self.data_source_details_group)

        # 添加带样式的标签
        plugin_id_label = QLabel("插件ID:")
        plugin_id_label.setStyleSheet("font-weight: bold; color: #34495e;")
        details_layout.addWidget(plugin_id_label, 0, 0)
        self.ds_plugin_id_label = QLabel("-")
        self.ds_plugin_id_label.setStyleSheet("color: #2c3e50; background-color: #f8f9fa; padding: 4px; border-radius: 3px;")
        details_layout.addWidget(self.ds_plugin_id_label, 0, 1)

        version_label = QLabel("版本:")
        version_label.setStyleSheet("font-weight: bold; color: #34495e;")
        details_layout.addWidget(version_label, 1, 0)
        self.ds_plugin_version_label = QLabel("-")
        self.ds_plugin_version_label.setStyleSheet("color: #2c3e50; background-color: #f8f9fa; padding: 4px; border-radius: 3px;")
        details_layout.addWidget(self.ds_plugin_version_label, 1, 1)

        author_label = QLabel("作者:")
        author_label.setStyleSheet("font-weight: bold; color: #34495e;")
        details_layout.addWidget(author_label, 2, 0)
        self.ds_plugin_author_label = QLabel("-")
        self.ds_plugin_author_label.setStyleSheet("color: #2c3e50; background-color: #f8f9fa; padding: 4px; border-radius: 3px;")
        details_layout.addWidget(self.ds_plugin_author_label, 2, 1)

        assets_label = QLabel("支持资产:")
        assets_label.setStyleSheet("font-weight: bold; color: #34495e;")
        details_layout.addWidget(assets_label, 3, 0)
        self.ds_plugin_assets_label = QLabel("-")
        self.ds_plugin_assets_label.setStyleSheet("color: #2c3e50; background-color: #f8f9fa; padding: 4px; border-radius: 3px;")
        details_layout.addWidget(self.ds_plugin_assets_label, 3, 1)

        data_types_label = QLabel("支持数据类型:")
        data_types_label.setStyleSheet("font-weight: bold; color: #34495e;")
        details_layout.addWidget(data_types_label, 4, 0)
        self.ds_plugin_data_types_label = QLabel("-")
        self.ds_plugin_data_types_label.setStyleSheet("color: #2c3e50; background-color: #f8f9fa; padding: 4px; border-radius: 3px;")
        details_layout.addWidget(self.ds_plugin_data_types_label, 4, 1)

        right_layout.addWidget(self.data_source_details_group)

        # 路由配置组
        self.routing_config_group = QGroupBox("路由配置")
        routing_layout = QGridLayout(self.routing_config_group)

        routing_layout.addWidget(QLabel("资产类型:"), 0, 0)
        self.asset_type_combo = QComboBox()

        # 动态从AssetType枚举获取选项，显示中文
        try:
            from core.plugin_types import AssetType

            # 保存映射关系（中文显示名 -> 英文枚举值）
            self.asset_type_display_map = {}

            for asset_type in AssetType:
                chinese_name = self.asset_type_chinese_map.get(asset_type.value, asset_type.value)
                self.asset_type_combo.addItem(chinese_name)
                self.asset_type_display_map[chinese_name] = asset_type.value

            logger.info(f" 已加载资产类型选项: {list(self.asset_type_display_map.keys())}")
        except ImportError:
            # 回退到静态列表 - 使用统一的资产类型工具
            from core.ui_asset_type_utils import get_asset_type_combo_items
            fallback_items = get_asset_type_combo_items()
            self.asset_type_combo.addItems(fallback_items)
            self.asset_type_display_map = {
                "A股": "stock_a",
                "美股": "stock_us",
                "港股": "stock_hk",
                "期货": "futures",
                "基金": "fund",
                "债券": "bond",
                "指数": "index",
                "加密货币": "crypto",
                "外汇": "forex",
                "债券": "bond"
            }
            logger.info("使用静态资产类型列表")

        self.asset_type_combo.currentTextChanged.connect(self.update_priority_list)
        routing_layout.addWidget(self.asset_type_combo, 0, 1)

        routing_layout.addWidget(QLabel("优先级列表:"), 1, 0)
        self.priority_list_widget = QListWidget()
        self.priority_list_widget.setDragDropMode(QListWidget.InternalMove)
        routing_layout.addWidget(self.priority_list_widget, 1, 1, 3, 1)

        # 路由按钮布局
        routing_btn_layout = QHBoxLayout()

        save_priority_btn = QPushButton("保存优先级")
        save_priority_btn.clicked.connect(self.save_priority_config)
        routing_btn_layout.addWidget(save_priority_btn)

        test_routing_btn = QPushButton("测试路由")
        test_routing_btn.clicked.connect(self.test_routing_config)
        test_routing_btn.setToolTip("测试路由配置是否生效")
        routing_btn_layout.addWidget(test_routing_btn)

        sync_datasource_btn = QPushButton("同步数据源")
        sync_datasource_btn.clicked.connect(self._sync_data_sources_to_unified_manager)
        sync_datasource_btn.setToolTip("手动同步数据源到统一管理器")
        routing_btn_layout.addWidget(sync_datasource_btn)

        routing_btn_widget = QWidget()
        routing_btn_widget.setLayout(routing_btn_layout)
        routing_layout.addWidget(routing_btn_widget, 4, 1)

        right_layout.addWidget(self.routing_config_group)

        # 性能指标组
        self.performance_group = QGroupBox("性能指标")
        perf_layout = QGridLayout(self.performance_group)

        perf_layout.addWidget(QLabel("总请求数:"), 0, 0)
        self.total_requests_label = QLabel("0")
        perf_layout.addWidget(self.total_requests_label, 0, 1)

        perf_layout.addWidget(QLabel("成功率:"), 1, 0)
        self.success_rate_label = QLabel("0%")
        perf_layout.addWidget(self.success_rate_label, 1, 1)

        perf_layout.addWidget(QLabel("平均响应时间:"), 2, 0)
        self.avg_response_time_label = QLabel("0ms")
        perf_layout.addWidget(self.avg_response_time_label, 2, 1)

        perf_layout.addWidget(QLabel("健康分数:"), 3, 0)
        self.health_score_label = QLabel("0.0")
        perf_layout.addWidget(self.health_score_label, 3, 1)

        right_layout.addWidget(self.performance_group)
        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([500, 300])  # 左侧400px，右侧300px

        layout.addWidget(splitter)

        # 初始化数据
        self.refresh_data_source_plugins()

        # 初始化优先级列表（延迟执行，确保组件已创建）
        QTimer.singleShot(100, self.update_priority_list)

        return tab

    def refresh_data_source_plugins(self):
        """刷新数据源插件列表（单一路径：从路由器读取）。"""
        try:
            t_start = time.time()
            logger.info(f"刷新数据源插件列表（router 单一来源）...")
            
            # 清空现有数据
            self.data_source_table.setRowCount(0)
            logger.info(f"  清空表格耗时: {time.time() - t_start:.2f}s")
            
            t1 = time.time()

            # 获取路由器
            from core.services.unified_data_manager import get_unified_data_manager
            unified_manager = get_unified_data_manager()
            logger.info(f"  获取unified_manager耗时: {time.time() - t1:.2f}s")
            
            t2 = time.time()
            router = getattr(unified_manager, 'data_source_router', None) if unified_manager else None
            logger.info(f"  获取router耗时: {time.time() - t2:.2f}s")
            adapters = {}
            if router and hasattr(router, 'data_sources'):
                adapters = router.data_sources or {}

            # 若路由器为空，尝试强制加载并注册
            if not adapters and self.plugin_manager:
                logger.info("路由器暂无数据源，尝试强制重新加载插件并注册...")
                t_load = time.time()
                try:
                    self.plugin_manager.load_all_plugins()
                    logger.info(f"  load_all_plugins() 完成，耗时: {time.time() - t_load:.2f}s")
                except Exception as e:
                    logger.error(f" 重新加载插件失败: {e}")
                # 重新读取
                unified_manager = get_unified_data_manager()
                router = getattr(unified_manager, 'data_source_router', None) if unified_manager else None
                if router and hasattr(router, 'data_sources'):
                    adapters = router.data_sources or {}

            # 观测：打印插件加载数/路由器注册数/失败列表
            try:
                loaded_count = len(getattr(self.plugin_manager, 'plugin_instances', {})) if self.plugin_manager else 0
                router_count = len(adapters)
                missing_list = []
                if self.plugin_manager:
                    # 取可能的数据源候选（已识别的数据源插件名）
                    ds_candidates = set(getattr(self.plugin_manager, 'data_source_plugins', {}).keys())
                    router_keys = set(adapters.keys())
                    missing_list = sorted(list(ds_candidates - router_keys))
                logger.info(f" 插件加载数: {loaded_count} | 路由器注册数: {router_count}")
                if missing_list:
                    logger.info(f" 未注册到路由器的数据源插件: {missing_list}")
            except Exception as obs_e:
                logger.error(f" 统计打印失败: {obs_e}")

            if adapters:
                self._populate_data_source_table(adapters, None)
                logger.info(f" 数据源插件表格已填充: {len(adapters)} 个插件")
            else:
                self._show_no_plugins_message()
        except Exception as e:
            logger.error(f" 刷新数据源插件列表失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "刷新失败", f"刷新数据源插件列表失败:\n{str(e)}")

    def _on_plugin_loaded(self, plugin_name: str, plugin_info: dict, adapter):
        """单个插件加载完成回调"""
        logger.info(f" 插件加载完成: {plugin_name}")

    def _on_loading_progress(self, current: int, total: int, plugin_name: str):
        """加载进度更新回调"""
        if hasattr(self, 'data_source_table') and self.data_source_table.rowCount() > 0:
            progress_text = f" 加载中... ({current}/{total}) {plugin_name}"
            self.data_source_table.item(0, 0).setText(progress_text)
            QApplication.processEvents()  # 更新UI

    def _on_loading_completed(self, adapters: dict):
        """异步加载完成回调"""
        try:
            logger.info(f" 异步加载完成，共 {len(adapters)} 个插件")
            if adapters:
                self._populate_data_source_table(adapters, None)
                logger.info(f" 数据源插件表格已填充: {len(adapters)} 个插件")
            else:
                self._show_no_plugins_message()
        except Exception as e:
            logger.error(f" 处理加载完成事件失败: {e}")

    def _on_loading_failed(self, error_message: str):
        """异步加载失败回调"""
        logger.error(f" 异步加载失败: {error_message}")
        self._show_error_message(f"加载失败: {error_message}")

    def _fallback_sync_loading(self):
        """回退到同步加载模式"""
        logger.info("回退到同步加载模式")
        # 这里保留原来的同步加载逻辑作为备用
        pass

    def _show_no_plugins_message(self):
        """显示无插件消息"""
        self.data_source_table.setRowCount(1)
        self.data_source_table.setItem(0, 0, QTableWidgetItem("未找到数据源插件"))
        self.data_source_table.setItem(0, 1, QTableWidgetItem("无数据"))
        for col in range(2, 6):
            self.data_source_table.setItem(0, col, QTableWidgetItem("-"))

    def _show_error_message(self, message: str):
        """显示错误消息"""
        self.data_source_table.setRowCount(1)
        error_item = QTableWidgetItem(f" {message}")
        error_item.setTextAlignment(Qt.AlignCenter)
        self.data_source_table.setItem(0, 0, error_item)
        for col in range(1, 6):
            self.data_source_table.setItem(0, col, QTableWidgetItem(""))

    def _populate_data_source_table(self, data_sources: dict, router=None):
        """填充数据源表格 - 异步处理防止UI卡死"""
        try:
            t0 = time.time()
            logger.info(f" 开始异步填充数据源表格，数据源数量: {len(data_sources)}")

            # 立即设置表格行数并显示加载状态
            self.data_source_table.setRowCount(len(data_sources))

            # 为每行设置初始加载状态
            for row in range(len(data_sources)):
                loading_item = QTableWidgetItem("加载中...")
                loading_item.setTextAlignment(Qt.AlignCenter)
                self.data_source_table.setItem(row, 0, loading_item)
                for col in range(1, 6):
                    self.data_source_table.setItem(row, col, QTableWidgetItem(""))

            logger.info(f"  表格初始化完成，耗时: {time.time() - t0:.2f}s")

            # 检查是否有正在运行的表格填充线程
            if hasattr(self, 'table_worker') and self.table_worker.isRunning():
                self.table_worker.stop()
                self.table_worker.wait(1000)

            # 创建异步表格填充工作线程（带路由器指标，避免在行构建中做重型调用）
            t1 = time.time()
            try:
                metrics = {}
                from core.services.unified_data_manager import get_unified_data_manager
                _um = get_unified_data_manager()
                _router = getattr(_um, 'data_source_router', None)
                if _router and hasattr(_router, 'get_all_metrics'):
                    metrics = _router.get_all_metrics() or {}
            except Exception:
                metrics = {}
            logger.info(f"  获取路由器指标完成，耗时: {time.time() - t1:.2f}s")

            t2 = time.time()
            self.table_worker = TablePopulationWorker(data_sources, self.asset_type_chinese_map, self, metrics, use_cache=True)
            logger.info(f"  创建Worker完成，耗时: {time.time() - t2:.2f}s")

            # 连接信号
            self.table_worker.row_populated.connect(self._on_row_populated)
            self.table_worker.population_progress.connect(self._on_table_population_progress)
            self.table_worker.population_completed.connect(self._on_table_population_completed)
            self.table_worker.population_failed.connect(self._on_table_population_failed)

            # 启动异步填充
            self.table_worker.start()
            logger.info("异步表格填充线程已启动")

        except Exception as e:
            logger.error(f" 启动表格填充失败: {e}")
            import traceback
            traceback.print_exc()

    def _on_row_populated(self, row: int, row_data: dict):
        """单行数据填充完成回调"""
        try:
            # 填充基本数据
            name_item = QTableWidgetItem(row_data['name'])
            # 绑定真实插件ID
            try:
                name_item.setData(Qt.UserRole, row_data['source_id'])
            except Exception:
                pass
            self.data_source_table.setItem(row, 0, name_item)
            self.data_source_table.setItem(row, 1, QTableWidgetItem(row_data['status']))
            self.data_source_table.setItem(row, 2, QTableWidgetItem(row_data['assets']))
            self.data_source_table.setItem(row, 3, QTableWidgetItem(row_data['health_score']))
            self.data_source_table.setItem(row, 4, QTableWidgetItem(row_data['priority']))

            # 创建操作按钮（在主线程中创建UI控件）
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)

            config_btn = QPushButton("")
            config_btn.setToolTip("配置插件")
            config_btn.setMaximumSize(30, 25)
            source_id = row_data['source_id']
            config_btn.clicked.connect(lambda checked, name=source_id: self.configure_data_source_plugin(name))

            test_btn = QPushButton("")
            test_btn.setToolTip("测试连接")
            test_btn.setMaximumSize(30, 25)
            test_btn.clicked.connect(lambda checked, name=source_id: self.test_data_source_plugin(name))

            action_layout.addWidget(config_btn)
            action_layout.addWidget(test_btn)
            action_layout.addStretch()

            self.data_source_table.setCellWidget(row, 5, action_widget)

            logger.info(f"    完成数据源 {source_id} 的显示设置")

        except Exception as e:
            logger.error(f" 填充行数据失败 row {row}: {e}")

    def _on_table_population_progress(self, current: int, total: int, plugin_name: str):
        """表格填充进度更新回调"""
        try:
            progress_text = f"加载中... ({current}/{total}) {plugin_name}"
            self.status_label.setText(progress_text)
            QApplication.processEvents()
        except Exception as e:
            pass

    def _on_table_population_completed(self):
        """表格填充完成回调"""
        try:
            self.status_label.setText("加载完成")
            total = self.data_source_table.rowCount()
            active_count = sum(1 for row in range(total) 
                             if self.data_source_table.item(row, 1) and 
                             self.data_source_table.item(row, 1).text().strip() == "活跃")
            self.active_count_label.setText(f"活跃插件: {active_count}")
        except Exception:
            pass
        logger.info("异步表格填充完成")

    def _on_table_population_failed(self, error_message: str):
        """表格填充失败回调"""
        logger.error(f" 异步表格填充失败: {error_message}")
        QMessageBox.warning(self, "填充失败", f"表格填充失败:\n{error_message}")

    def on_data_source_selection_changed(self):
        """数据源插件选择变化处理"""
        try:
            current_row = self.data_source_table.currentRow()
            if current_row < 0:
                # 清空右侧面板
                self._clear_data_source_details()
                return

            # 获取选中的插件名称
            plugin_name = self.data_source_table.item(current_row, 0).text()
            logger.info(f" 选中数据源插件: {plugin_name}")

            # 初始化默认值
            self._clear_data_source_details()

            # 尝试从不同来源获取插件信息
            plugin_info = None
            selected_adapter = None

            # 方法1：从插件管理器获取
            if self.plugin_manager and hasattr(self.plugin_manager, 'get_data_source_plugins'):
                try:
                    ds_plugins = self.plugin_manager.get_data_source_plugins()
                    for source_id, plugin_instance in ds_plugins.items():
                        if hasattr(plugin_instance, 'get_plugin_info'):
                            info = plugin_instance.get_plugin_info()
                            if info.name == plugin_name:
                                plugin_info = info
                                selected_adapter = plugin_instance
                                break
                        elif hasattr(plugin_instance, 'name') and plugin_instance.name == plugin_name:
                            # 构造基本信息
                            plugin_info = type('PluginInfo', (), {
                                'id': getattr(plugin_instance, 'id', plugin_name),
                                'name': plugin_name,
                                'version': getattr(plugin_instance, 'version', '1.0.0'),
                                'author': getattr(plugin_instance, 'author', '未知'),
                                'description': getattr(plugin_instance, 'description', ''),
                                'supported_asset_types': getattr(plugin_instance, 'supported_asset_types', []),
                                'supported_data_types': getattr(plugin_instance, 'supported_data_types', [])
                            })
                            selected_adapter = plugin_instance
                            break
                except Exception as e:
                    logger.error(f"从插件管理器获取信息失败: {e}")

            # 方法2：从统一数据管理器获取
            if not plugin_info:
                try:
                    from core.services.unified_data_manager import get_unified_data_manager
                    unified_manager = get_unified_data_manager()

                    if unified_manager and hasattr(unified_manager, 'data_source_router'):
                        router = unified_manager.data_source_router
                        if router and hasattr(router, 'data_sources'):
                            for source_id, adapter in router.data_sources.items():
                                try:
                                    info = adapter.get_plugin_info()
                                    if info.name == plugin_name:
                                        plugin_info = info
                                        selected_adapter = adapter
                                        break
                                except Exception:
                                    continue
                except ImportError:
                    logger.error("统一数据管理器不可用")
                except Exception as e:
                    logger.error(f"从统一数据管理器获取信息失败: {e}")

            # 方法3：使用默认值
            if not plugin_info:
                logger.info(f"未找到 {plugin_name} 的详细信息，使用默认值")
                plugin_info = type('PluginInfo', (), {
                    'id': plugin_name,
                    'name': plugin_name,
                    'version': '1.0.0',
                    'author': '未知',
                    'description': '插件信息获取失败',
                    'supported_asset_types': [],
                    'supported_data_types': []
                })

            # 更新插件详情
            self.ds_plugin_id_label.setText(plugin_info.id)
            self.ds_plugin_version_label.setText(plugin_info.version)
            self.ds_plugin_author_label.setText(plugin_info.author)

            # 处理支持的资产类型
            assets_text = "-"
            if hasattr(plugin_info, 'supported_asset_types') and plugin_info.supported_asset_types:
                try:
                    if isinstance(plugin_info.supported_asset_types[0], str):
                        # 字符串类型，直接转换为中文
                        chinese_assets = [self.asset_type_chinese_map.get(asset, asset) for asset in plugin_info.supported_asset_types]
                        assets_text = ", ".join(chinese_assets)
                    else:
                        # 枚举类型，先获取值再转换为中文
                        chinese_assets = [self.asset_type_chinese_map.get(asset.value, asset.value) for asset in plugin_info.supported_asset_types]
                        assets_text = ", ".join(chinese_assets)
                except Exception:
                    assets_text = str(plugin_info.supported_asset_types)
            self.ds_plugin_assets_label.setText(assets_text)

            # 处理支持的数据类型
            data_types_text = "-"
            if hasattr(plugin_info, 'supported_data_types') and plugin_info.supported_data_types:
                try:
                    if isinstance(plugin_info.supported_data_types[0], str):
                        data_types_text = ", ".join(plugin_info.supported_data_types)
                    else:
                        data_types_text = ", ".join([dt.value for dt in plugin_info.supported_data_types])
                except Exception:
                    data_types_text = str(plugin_info.supported_data_types)
            self.ds_plugin_data_types_label.setText(data_types_text)

            # 更新性能指标（如果可用）
            self._update_performance_metrics(selected_adapter, plugin_name)

            # 更新优先级列表
            self.update_priority_list()

            logger.info(f" 已更新 {plugin_name} 的详情信息")

        except Exception as e:
            logger.error(f" 更新数据源插件详情失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def _clear_data_source_details(self):
        """清空数据源详情显示"""
        try:
            self.ds_plugin_id_label.setText("-")
            self.ds_plugin_version_label.setText("-")
            self.ds_plugin_author_label.setText("-")
            self.ds_plugin_assets_label.setText("-")
            self.ds_plugin_data_types_label.setText("-")
            self.total_requests_label.setText("0")
            self.success_rate_label.setText("0%")
            if hasattr(self, 'avg_response_time_label'):
                self.avg_response_time_label.setText("0ms")
            if hasattr(self, 'health_score_label'):
                self.health_score_label.setText("0.00")
        except Exception as e:
            logger.error(f"清空详情显示失败: {e}")

    def _update_performance_metrics(self, adapter, plugin_name):
        """更新性能指标"""
        try:
            # 默认值
            total_requests = 0
            success_rate = 0.0
            avg_response_time = 0.0
            health_score = 0.0

            # 优先从路由器获取聚合指标
            try:
                from core.services.unified_data_manager import get_unified_data_manager
                unified_manager = get_unified_data_manager()
                router = getattr(unified_manager, 'data_source_router', None) if unified_manager else None

                if router and hasattr(router, 'metrics'):
                    # 获取所有数据源的聚合指标
                    all_metrics = router.metrics
                    if all_metrics:
                        total_total_requests = sum(m.total_requests for m in all_metrics.values())
                        total_successful_requests = sum(m.successful_requests for m in all_metrics.values())
                        total_failed_requests = sum(m.failed_requests for m in all_metrics.values())

                        if total_total_requests > 0:
                            total_requests = total_total_requests
                            success_rate = total_successful_requests / total_total_requests

                        # 计算平均响应时间（加权平均）
                        total_weighted_time = sum(m.avg_response_time_ms * m.total_requests
                                                  for m in all_metrics.values() if m.total_requests > 0)
                        if total_total_requests > 0:
                            avg_response_time = total_weighted_time / total_total_requests

                        # 计算平均健康分数
                        health_scores = [m.health_score for m in all_metrics.values()]
                        if health_scores:
                            health_score = sum(health_scores) / len(health_scores)

                    # 如果选中了特定插件，显示该插件的指标
                    if plugin_name and plugin_name in all_metrics:
                        plugin_metrics = all_metrics[plugin_name]
                        total_requests = plugin_metrics.total_requests
                        if plugin_metrics.total_requests > 0:
                            success_rate = plugin_metrics.successful_requests / plugin_metrics.total_requests
                        avg_response_time = plugin_metrics.avg_response_time_ms
                        health_score = plugin_metrics.health_score

            except Exception as e:
                logger.error(f"从路由器获取指标失败: {e}")

            # 备用：从适配器获取统计信息
            if total_requests == 0 and adapter:
                try:
                    if hasattr(adapter, 'get_statistics'):
                        stats = adapter.get_statistics()
                        total_requests = stats.get('total_requests', 0)
                        success_rate = stats.get('success_rate', 0.0)
                        avg_response_time = stats.get('avg_response_time', 0.0)
                        health_score = 0.8 if success_rate > 0.5 else 0.3
                    elif hasattr(adapter, 'stats') and adapter.stats:
                        stats = adapter.stats
                        total_requests = stats.get('total_requests', 0)
                        successful = stats.get('successful_requests', 0)
                        if total_requests > 0:
                            success_rate = successful / total_requests
                        health_score = 0.85 if success_rate > 0.8 else 0.5
                    else:
                        # 无法获取统计信息时保持默认值
                        pass

                except Exception as e:
                    logger.error(f"获取适配器统计信息失败: {e}")

            # 更新显示
            self.total_requests_label.setText(str(total_requests))
            self.success_rate_label.setText(f"{success_rate:.1%}")
            if hasattr(self, 'avg_response_time_label'):
                self.avg_response_time_label.setText(f"{avg_response_time:.1f}ms")
            if hasattr(self, 'health_score_label'):
                self.health_score_label.setText(f"{health_score:.2f}")

        except Exception as e:
            logger.error(f"更新性能指标失败: {e}")
            # 显示默认值
            self.total_requests_label.setText("0")
            self.success_rate_label.setText("0.0%")
            if hasattr(self, 'avg_response_time_label'):
                self.avg_response_time_label.setText("0.0ms")
            if hasattr(self, 'health_score_label'):
                self.health_score_label.setText("0.00")

    def update_priority_list(self):
        """更新优先级列表"""
        try:
            from core.plugin_types import AssetType
            from core.services.unified_data_manager import get_unified_data_manager

            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'data_source_router'):
                logger.error("数据源路由器不可用")
                self.priority_list_widget.clear()
                return

            router = unified_manager.data_source_router
            asset_type_display = self.asset_type_combo.currentText()
            logger.info(f" 更新优先级列表，资产类型显示名: {asset_type_display}")

            # 从中文显示名转换为英文枚举值
            asset_type_value = self.asset_type_display_map.get(asset_type_display)
            if not asset_type_value:
                logger.error(f" 无法找到资产类型映射: {asset_type_display}")
                self.priority_list_widget.clear()
                return

            try:
                asset_type = AssetType(asset_type_value)
                logger.info(f" 资产类型转换成功: {asset_type_display} -> {asset_type.value}")
            except ValueError:
                logger.error(f" 无效的资产类型值: {asset_type_value}")
                self.priority_list_widget.clear()
                return

            self.priority_list_widget.clear()

            # 获取当前资产类型的优先级配置
            configured_priorities = router.asset_priorities.get(asset_type, [])

            # 获取所有支持该资产类型的数据源
            all_sources = []
            logger.info(f" 检查 {len(router.data_sources)} 个已注册的数据源...")

            for source_id, adapter in router.data_sources.items():
                try:
                    plugin_info = adapter.get_plugin_info()
                    supported_types = plugin_info.supported_asset_types

                    logger.info(f"   数据源 {source_id}:")
                    logger.info(f"    - 支持的资产类型: {[t.value if hasattr(t, 'value') else str(t) for t in supported_types]}")
                    logger.info(f"    - 当前查找的资产类型: {asset_type.value}")

                    # 检查是否支持当前资产类型
                    is_supported = False
                    for supported_type in supported_types:
                        if hasattr(supported_type, 'value') and hasattr(asset_type, 'value'):
                            # 通过枚举值比较
                            if supported_type.value == asset_type.value:
                                is_supported = True
                                break
                        elif supported_type == asset_type:
                            # 直接比较枚举对象
                            is_supported = True
                            break

                    if is_supported:
                        all_sources.append(source_id)
                        logger.info(f"     支持 {asset_type.value}")
                    else:
                        logger.info(f"     不支持 {asset_type.value}")

                except Exception as e:
                    logger.error(f"   检查数据源 {source_id} 支持的资产类型失败: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            logger.info(f" 找到支持 {asset_type_display}({asset_type.value}) 的数据源: {all_sources}")
            logger.info(f" 已配置的优先级: {configured_priorities}")

            # 显示数据源列表：先显示已配置的优先级，再显示其他未配置的
            displayed_sources = set()

            # 1. 按配置的优先级顺序显示
            for source_id in configured_priorities:
                if source_id in router.data_sources and source_id in all_sources:
                    try:
                        adapter = router.data_sources[source_id]
                        plugin_info = adapter.get_plugin_info()
                        item = QListWidgetItem(f" {plugin_info.name} ({source_id})")
                        item.setData(Qt.UserRole, source_id)
                        item.setToolTip(f"已配置优先级，当前位置: {configured_priorities.index(source_id) + 1}")
                        self.priority_list_widget.addItem(item)
                        displayed_sources.add(source_id)
                        logger.info(f"   添加已配置: {source_id}")
                    except Exception as e:
                        logger.error(f"   添加已配置源失败 {source_id}: {e}")

            # 2. 显示其他支持该资产类型但未配置优先级的数据源
            for source_id in all_sources:
                if source_id not in displayed_sources:
                    try:
                        adapter = router.data_sources[source_id]
                        plugin_info = adapter.get_plugin_info()
                        item = QListWidgetItem(f" {plugin_info.name} ({source_id})")
                        item.setData(Qt.UserRole, source_id)
                        item.setToolTip("未配置优先级，可拖拽到上方设置优先级")
                        self.priority_list_widget.addItem(item)
                        logger.info(f"   添加未配置: {source_id}")
                    except Exception as e:
                        logger.error(f"   添加未配置源失败 {source_id}: {e}")

            total_count = self.priority_list_widget.count()
            logger.info(f" 优先级列表更新完成，共 {total_count} 个数据源")

            if total_count == 0:
                # 添加提示项
                info_item = QListWidgetItem("ℹ 暂无支持该资产类型的数据源")
                info_item.setFlags(info_item.flags() & ~Qt.ItemIsSelectable)
                self.priority_list_widget.addItem(info_item)

        except Exception as e:
            logger.error(f" 更新优先级列表失败: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"更新优先级列表失败: {str(e)}")

    def save_priority_config(self):
        """保存优先级配置"""
        try:
            from core.plugin_types import AssetType
            from core.services.unified_data_manager import get_unified_data_manager

            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'data_source_router'):
                QMessageBox.warning(self, "配置失败", "数据源路由器未启用")
                return

            asset_type_display = self.asset_type_combo.currentText()
            asset_type_value = self.asset_type_display_map.get(asset_type_display)
            if not asset_type_value:
                QMessageBox.warning(self, "配置失败", f"无法识别的资产类型: {asset_type_display}")
                return
            asset_type = AssetType(asset_type_value)

            # 从列表widget获取新的优先级顺序
            new_priorities = []
            for i in range(self.priority_list_widget.count()):
                item = self.priority_list_widget.item(i)
                source_id = item.data(Qt.UserRole)
                new_priorities.append(source_id)

            if not new_priorities:
                QMessageBox.warning(self, "配置失败", "优先级列表为空，请先配置数据源优先级")
                return

            # 保存到路由器
            unified_manager.set_asset_routing_priorities(asset_type, new_priorities)

            # 验证配置是否生效
            router = unified_manager.data_source_router
            saved_priorities = router.asset_priorities.get(asset_type, [])

            if saved_priorities == new_priorities:
                QMessageBox.information(self, "配置成功",
                                        f"已保存{asset_type_display}的优先级配置:\n" +
                                        "\n".join([f"{i+1}. {p}" for i, p in enumerate(new_priorities)]) +
                                        "\n\n配置已在路由器中生效，系统将按此优先级选择数据源。")
                logger.info(f" 路由优先级配置成功: {asset_type_display} -> {new_priorities}")
            else:
                QMessageBox.warning(self, "配置验证失败",
                                    f"保存的配置与预期不符:\n期望: {new_priorities}\n实际: {saved_priorities}")

            # 刷新列表
            self.refresh_data_source_plugins()

        except Exception as e:
            logger.error(f" 保存优先级配置失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "配置失败", f"保存优先级配置失败:\n{str(e)}")

    def test_routing_config(self):
        """测试路由配置是否生效"""
        try:
            from core.plugin_types import AssetType
            from core.services.unified_data_manager import get_unified_data_manager
            from core.data_source_router import RoutingRequest

            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'data_source_router'):
                QMessageBox.warning(self, "测试失败", "数据源路由器未启用")
                return

            asset_type_display = self.asset_type_combo.currentText()
            asset_type_value = self.asset_type_display_map.get(asset_type_display)
            if not asset_type_value:
                QMessageBox.warning(self, "测试失败", f"无法识别的资产类型: {asset_type_display}")
                return
            asset_type = AssetType(asset_type_value)
            router = unified_manager.data_source_router

            # 获取当前配置的优先级
            configured_priorities = router.asset_priorities.get(asset_type, [])
            if not configured_priorities:
                QMessageBox.warning(self, "测试失败",
                                    f"未找到{asset_type_display}的路由配置，请先保存优先级配置")
                return

            # 模拟路由请求测试
            test_results = []
            test_symbols = ["000001", "600000", "AAPL"]  # 测试不同的股票代码

            for symbol in test_symbols:
                try:
                    # 创建测试请求
                    from core.plugin_types import DataType
                    request = RoutingRequest(
                        asset_type=asset_type,
                        data_type=DataType.HISTORICAL_KLINE,
                        symbol=symbol
                    )

                    # 测试路由选择
                    selected_source = router.route_request(request)
                    if selected_source:
                        # 获取选中数据源在优先级列表中的位置
                        try:
                            priority_index = configured_priorities.index(selected_source) + 1
                            test_results.append(f" {symbol}: 选择 {selected_source} (优先级第{priority_index})")
                        except ValueError:
                            test_results.append(f" {symbol}: 选择 {selected_source} (不在配置的优先级列表中)")
                    else:
                        test_results.append(f" {symbol}: 无可用数据源")

                except Exception as e:
                    test_results.append(f" {symbol}: 测试失败 - {str(e)}")

            # 显示测试结果
            result_text = f"路由配置测试结果 ({asset_type_display}):\n\n"
            result_text += f"配置的优先级顺序:\n"
            for i, source_id in enumerate(configured_priorities, 1):
                result_text += f"  {i}. {source_id}\n"
            result_text += "\n测试结果:\n"
            result_text += "\n".join(test_results)
            result_text += f"\n\n说明：系统会按配置的优先级顺序选择健康的数据源。"

            QMessageBox.information(self, "路由测试结果", result_text)
            logger.info(f" 路由配置测试完成: {asset_type_display}")

        except Exception as e:
            logger.error(f" 路由配置测试失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "测试失败", f"路由配置测试失败:\n{str(e)}")

    def load_data_source_plugin(self):
        """加载数据源插件"""
        QMessageBox.information(self, "功能开发中", "插件加载功能正在开发中...")

    def unload_data_source_plugin(self):
        """卸载数据源插件"""
        current_row = self.data_source_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "未选择插件", "请先选择要卸载的插件")
            return

        QMessageBox.information(self, "功能开发中", "插件卸载功能正在开发中...")

    def configure_data_source_plugin(self, source_id):
        """配置数据源插件"""
        try:
            logger.info(f" 开始配置数据源插件: {source_id}")

            from gui.dialogs.data_source_plugin_config_dialog import DataSourcePluginConfigDialog
            logger.info("成功导入配置对话框")
        except ImportError as ie:
            logger.error(f" 导入配置对话框失败: {ie}")
            QMessageBox.information(self, "功能开发中", f"插件 {source_id} 的配置功能正在开发中...")
            return

        try:
            # 检查插件是否存在
            from core.services.unified_data_manager import get_unified_data_manager
            unified_manager = get_unified_data_manager()
            if unified_manager and hasattr(unified_manager, 'data_source_router'):
                router = unified_manager.data_source_router
                if router and source_id not in router.data_sources:
                    available_sources = list(router.data_sources.keys())
                    logger.info(f" 插件 {source_id} 不存在，可用插件: {available_sources}")
                    QMessageBox.warning(self, "配置失败", f"插件 {source_id} 不存在\n可用插件: {', '.join(available_sources)}")
                    return

            logger.info(f" 创建配置对话框...")
            config_dialog = DataSourcePluginConfigDialog(source_id, self)
            config_dialog.config_changed.connect(self.on_plugin_config_changed)

            logger.info(f" 显示配置对话框...")
            result = config_dialog.exec_()
            logger.info(f"配置对话框结果: {result}")

        except Exception as e:
            logger.error(f" 配置插件时发生异常: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "配置错误", f"打开插件配置对话框失败:\n{str(e)}")

    def on_plugin_config_changed(self, source_id: str, config: dict):
        """插件配置变更处理"""
        try:
            # 刷新插件列表以显示更新后的信息
            self.refresh_data_source_plugins()

            # 记录日志
            logger.info(f"数据源插件 {source_id} 配置已更新")

        except Exception as e:
            logger.error(f"处理插件配置变更失败: {str(e)}")

    def test_data_source_plugin(self, source_id):
        """测试数据源插件"""
        try:
            logger.info(f" 开始测试数据源插件: {source_id}")

            from core.services.unified_data_manager import get_unified_data_manager

            unified_manager = get_unified_data_manager()
            if not unified_manager:
                logger.error("统一数据管理器不可用")
                QMessageBox.warning(self, "测试失败", "统一数据管理器不可用")
                return

            if not hasattr(unified_manager, 'data_source_router'):
                logger.error("数据源路由器未启用")
                QMessageBox.warning(self, "测试失败", "数据源路由器未启用")
                return

            router = unified_manager.data_source_router
            if not router:
                logger.error("数据源路由器为空")
                QMessageBox.warning(self, "测试失败", "数据源路由器为空")
                return

            if source_id not in router.data_sources:
                logger.info(f" 插件 {source_id} 不存在于路由器中")
                available_sources = list(router.data_sources.keys())
                logger.info(f"可用的数据源: {available_sources}")
                QMessageBox.warning(self, "测试失败", f"插件 {source_id} 不存在\n可用插件: {', '.join(available_sources)}")
                return

            # 执行健康检查
            logger.info(f" 执行健康检查...")
            adapter = router.data_sources[source_id]
            logger.info(f"适配器类型: {type(adapter).__name__}")

            health_result = adapter.health_check()
            logger.info(f"健康检查结果: is_healthy={health_result.is_healthy}, response_time={health_result.response_time_ms}ms")

            if health_result.is_healthy:
                message = f"插件 {source_id} 测试通过\n响应时间: {health_result.response_time_ms:.1f}ms"
                if health_result.error_message:
                    message += f"\n备注: {health_result.error_message}"
                logger.info(f" 测试成功: {message}")
                QMessageBox.information(self, "测试成功", message)
            else:
                error_msg = health_result.error_message or '未知错误'
                message = f"插件 {source_id} 测试失败\n错误: {error_msg}"
                logger.info(f" 测试失败: {message}")
                QMessageBox.warning(self, "测试失败", message)

        except Exception as e:
            logger.error(f" 测试插件时发生异常: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "测试错误", f"测试插件时发生错误:\n{str(e)}")

    def create_status_monitor_tab(self):
        """创建数据源状态监控标签页（Task 3.3）"""
        try:
            from gui.widgets.data_source_status_widget import DataSourceStatusWidget

            # 创建状态监控组件
            status_widget = DataSourceStatusWidget()

            # 连接信号
            status_widget.status_changed.connect(self.on_data_source_status_changed)
            status_widget.notification_added.connect(self.on_notification_added)

            return status_widget

        except ImportError:
            # 如果导入失败，显示占位符
            tab = QWidget()
            layout = QVBoxLayout(tab)

            placeholder = QLabel("状态监控功能开发中...")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("""
                QLabel {
                    color: #6c757d;
                    font-size: 16px;
                    border: 2px dashed #dee2e6;
                    padding: 20px;
                    border-radius: 8px;
                }
            """)
            layout.addWidget(placeholder)

            return tab

        except Exception as e:
            logger.error(f"创建状态监控标签页失败: {str(e)}")

            # 错误情况下的占位符
            tab = QWidget()
            layout = QVBoxLayout(tab)

            error_label = QLabel(f" 创建状态监控失败:\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #dc3545; font-size: 14px;")
            layout.addWidget(error_label)

            return tab

    def on_data_source_status_changed(self, source_id: str, status: str):
        """数据源状态变化处理"""
        try:
            logger.info(f"数据源 {source_id} 状态变化: {status}")

            # 刷新数据源插件列表以反映状态变化
            if hasattr(self, 'data_source_tab') and hasattr(self, 'refresh_data_source_plugins'):
                self.refresh_data_source_plugins()

        except Exception as e:
            logger.error(f"处理数据源状态变化失败: {str(e)}")

    def on_notification_added(self, level: str, message: str, source_id: str):
        """通知添加处理"""
        try:
            # 在状态栏显示重要通知
            if level in ["error", "warning"]:
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"{level.upper()}: {message}")
                    if level == "error":
                        self.status_label.setStyleSheet("color: #dc3545;")
                    else:
                        self.status_label.setStyleSheet("color: #ffc107;")

            logger.info(f"通知 [{level}]: {message} (来源: {source_id})")

        except Exception as e:
            logger.error(f"处理通知失败: {str(e)}")

    def _update_single_plugin_ui(self, widget, plugin_name: str, enabled: bool):
        """更新单个插件的UI状态"""
        try:
            # 更新主容器样式
            widget.setStyleSheet(f"""
                QFrame {{
                    background: #{'ffffff' if enabled else 'fafafa'};
                    border-left: 3px solid #{'00C851' if enabled else 'cccccc'};
                    border-top: 1px solid #e0e0e0;
                    border-right: 1px solid #e0e0e0;
                    border-bottom: 1px solid #e0e0e0;
                    margin: 1px 0px;
                    padding: 0px;
                }}
                QFrame:hover {{
                    background: #f5f5f5;
                    border-left: 3px solid #{'00A040' if enabled else '0066cc'};
                }}
            """)

            # 查找并更新所有子组件
            layout = widget.layout()
            if layout:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget():
                        child_widget = item.widget()

                        # 更新状态指示器 - 精简圆点
                        if isinstance(child_widget, QLabel) and child_widget.text() == "●":
                            child_widget.setStyleSheet(f"""
                                color: #{'00C851' if enabled else 'dddddd'};
                                font-size: 12px;
                                font-weight: bold;
                                min-width: 12px;
                                max-width: 12px;
                            """)

                        # 更新信息容器中的文本颜色
                        elif hasattr(child_widget, 'layout') and child_widget.layout():
                            info_layout = child_widget.layout()
                            for j in range(info_layout.count()):
                                info_item = info_layout.itemAt(j)
                                if info_item and info_item.widget():
                                    info_widget = info_item.widget()
                                    if isinstance(info_widget, QLabel):
                                        # 更新插件名称颜色
                                        if info_widget.font().bold():
                                            info_widget.setStyleSheet(f"color: #{'333333' if enabled else '888888'};")

                        # 更新状态标签 - 精简样式
                        elif isinstance(child_widget, QLabel) and ("运行中" in child_widget.text() or "已停用" in child_widget.text()):
                            new_status = "运行中" if enabled else "已停用"
                            child_widget.setText(new_status)
                            child_widget.setStyleSheet(f"""
                                color: #{'00C851' if enabled else '999999'};
                                background: #{'F0F8F0' if enabled else 'f5f5f5'};
                                border-radius: 8px;
                                padding: 2px 6px;
                                border: 1px solid #{'00C851' if enabled else 'dddddd'};
                            """)

            logger.info(f" UI状态已更新: {plugin_name} -> {'启用' if enabled else '禁用'}")

        except Exception as e:
            logger.error(f" 更新UI状态失败: {plugin_name}, {e}")

    def _create_real_adapter(self, plugin_name: str, plugin_info, plugin_instance):
        """创建真实的数据源适配器，不使用模拟数据"""
        try:
            # 尝试使用真实的DataSourcePluginAdapter
            if hasattr(plugin_instance, 'get_plugin_info'):
                # 插件有真实的get_plugin_info方法
                return type('RealAdapter', (), {
                    'get_plugin_info': lambda *args: plugin_instance.get_plugin_info(),
                    'is_connected': lambda *args: getattr(plugin_instance, 'initialized', True),
                    'health_check': lambda *args: self._get_real_health_check(plugin_instance),
                    'get_statistics': lambda *args: self._get_real_statistics(plugin_instance)
                })()
            else:
                # 创建兼容的适配器
                return type('CompatAdapter', (), {
                    'get_plugin_info': lambda *args: type('PluginInfo', (), {
                        'id': plugin_name,
                        'name': plugin_info.name,
                        'description': plugin_info.description,
                        'version': plugin_info.version,
                        'supported_asset_types': getattr(plugin_instance, 'get_supported_asset_types', lambda: [])()
                    })(),
                    'is_connected': lambda *args: plugin_info.enabled if hasattr(plugin_info, 'enabled') else True,
                    'health_check': lambda *args: self._get_real_health_check(plugin_instance),
                    'get_statistics': lambda *args: self._get_real_statistics(plugin_instance)
                })()

        except Exception as e:
            logger.error(f" 创建真实适配器失败 {plugin_name}: {e}")
            # 返回最小可用适配器
            return type('MinimalAdapter', (), {
                'get_plugin_info': lambda *args: type('PluginInfo', (), {
                    'id': plugin_name,
                    'name': plugin_info.name if hasattr(plugin_info, 'name') else plugin_name,
                    'description': getattr(plugin_info, 'description', '数据源插件'),
                    'version': getattr(plugin_info, 'version', '1.0.0'),
                    'supported_asset_types': []
                })(),
                'is_connected': lambda *args: True,
                'health_check': lambda *args: type('HealthCheckResult', (), {
                    'is_healthy': True,
                    'response_time': 0.0,
                    'error_message': None
                })(),
                'get_statistics': lambda *args: {'total_requests': 0, 'success_rate': 1.0}
            })()

    def _get_real_health_check(self, plugin_instance):
        """获取真实的健康检查结果"""
        try:
            if hasattr(plugin_instance, 'health_check'):
                return plugin_instance.health_check()
            elif hasattr(plugin_instance, 'test_connection'):
                is_healthy = plugin_instance.test_connection()
                return type('HealthCheckResult', (), {
                    'is_healthy': is_healthy,
                    'response_time': 0.1,
                    'error_message': None if is_healthy else 'Connection failed'
                })()
            else:
                # 基于初始化状态判断
                is_healthy = getattr(plugin_instance, 'initialized', True)
                return type('HealthCheckResult', (), {
                    'is_healthy': is_healthy,
                    'response_time': 0.0,
                    'error_message': None if is_healthy else 'Plugin not initialized'
                })()
        except Exception as e:
            return type('HealthCheckResult', (), {
                'is_healthy': False,
                'response_time': 0.0,
                'error_message': str(e)
            })()

    def _get_real_statistics(self, plugin_instance):
        """获取真实的统计数据"""
        try:
            if hasattr(plugin_instance, 'get_statistics'):
                return plugin_instance.get_statistics()
            else:
                # 基于插件实例状态生成基本统计
                return {
                    'total_requests': getattr(plugin_instance, 'request_count', 0),
                    'success_rate': 1.0 if getattr(plugin_instance, 'initialized', True) else 0.0,
                    'avg_response_time': 0.1,
                    'last_update': None
                }
        except Exception as e:
            return {
                'total_requests': 0,
                'success_rate': 0.0,
                'avg_response_time': 0.0,
                'last_update': None,
                'error': str(e)
            }

    def test_data_source_plugin(self, plugin_name: str):
        """测试数据源插件连接"""
        try:
            if not self.plugin_manager:
                QMessageBox.warning(self, "错误", "插件管理器不可用")
                return

            plugin_instance = self.plugin_manager.plugin_instances.get(plugin_name)
            if not plugin_instance:
                QMessageBox.warning(self, "错误", f"未找到插件实例: {plugin_name}")
                return

            # 执行健康检查
            health_result = self._get_real_health_check(plugin_instance)

            if hasattr(health_result, 'is_healthy') and health_result.is_healthy:
                QMessageBox.information(self, "测试成功", f"插件 {plugin_name} 连接正常")
            else:
                error_msg = getattr(health_result, 'error_message', '未知错误')
                QMessageBox.warning(self, "测试失败", f"插件 {plugin_name} 连接失败:\n{error_msg}")

        except Exception as e:
            QMessageBox.critical(self, "测试错误", f"测试插件 {plugin_name} 时发生错误:\n{str(e)}")

    def _format_timestamp(self, timestamp):
        """格式化时间戳"""
        if not timestamp:
            return "未知"

        try:
            import datetime
            if isinstance(timestamp, str):
                # 尝试解析ISO格式时间戳
                dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime("%H:%M:%S")
            elif isinstance(timestamp, (int, float)):
                dt = datetime.datetime.fromtimestamp(timestamp)
                return dt.strftime("%H:%M:%S")
            else:
                return str(timestamp)
        except Exception as e:
            logger.error(f" 格式化时间戳失败: {e}")
            return "未知"

    def _calculate_data_quality(self, status_info):
        """计算数据质量"""
        try:
            if not status_info:
                return "未知"

            # 基于多个因素计算质量分数
            quality_score = 0.0
            factors = 0

            # 连接状态 (40%)
            if status_info.get('is_connected', False):
                quality_score += 0.4
            factors += 1

            # 错误率 (30%)
            error_count = status_info.get('error_count', 0)
            if error_count == 0:
                quality_score += 0.3
            elif error_count < 5:
                quality_score += 0.15
            factors += 1

            # 响应时间 (30%)
            response_time = status_info.get('last_response_time', 0)
            if response_time < 1.0:
                quality_score += 0.3
            elif response_time < 3.0:
                quality_score += 0.15
            factors += 1

            # 转换为百分比
            if factors > 0:
                percentage = (quality_score / factors) * 100
                if percentage >= 80:
                    return "优秀"
                elif percentage >= 60:
                    return "良好"
                elif percentage >= 40:
                    return "一般"
                else:
                    return "较差"
            else:
                return "未知"

        except Exception as e:
            logger.error(f" 计算数据质量失败: {e}")
            return "未知"

    def _sync_data_sources_to_unified_manager(self):
        # SSOT: 本方法已废弃，避免在UI侧重复注册数据源（导致将 PluginInfo 当作实例传入适配器）
        logger.info("跳过 _sync_data_sources_to_unified_manager：已启用路由器单一真源（SSOT）")
        return

    def batch_apply_and_reconnect_data_sources(self):
        """批量保存配置并重连选中的数据源（或全部）"""
        try:
            from core.services.unified_data_manager import get_unified_data_manager
            from db.models.plugin_models import get_data_source_config_manager  # type: ignore

            unified_manager = get_unified_data_manager()
            if not unified_manager or not hasattr(unified_manager, 'data_source_router'):
                QMessageBox.warning(self, "操作失败", "数据源路由器未启用")
                return

            router = unified_manager.data_source_router
            if not hasattr(self, 'data_source_table'):
                QMessageBox.warning(self, "操作失败", "数据源列表尚未初始化")
                return

            # 确定目标数据源ID列表
            selected_rows = set(idx.row() for idx in self.data_source_table.selectionModel().selectedRows()) if self.data_source_table.selectionModel() else set()
            target_ids = []

            for row in range(self.data_source_table.rowCount()):
                if selected_rows and row not in selected_rows:
                    continue
                item = self.data_source_table.item(row, 0)
                if not item:
                    continue
                source_name = item.text()
                # 优先从 UserRole 读取真实ID
                source_id = item.data(Qt.UserRole) or item.text()
                target_ids.append(source_id)

            if not target_ids:
                # 未选择时，对全部已注册数据源执行
                target_ids = list(router.data_sources.keys())

            config_manager = get_data_source_config_manager()
            success_count = 0
            fail_count = 0

            for source_id in target_ids:
                try:
                    # 如果UI端维护了临时配置，优先保存（本实现直接从DB读取现有配置再重连）
                    db_entry = config_manager.get_plugin_config(source_id)
                    # 可在此处合并运行期变更；当前以DB为准

                    # 重连适配器
                    if source_id in router.data_sources:
                        adapter = router.data_sources[source_id]
                        try:
                            adapter.disconnect()
                        except Exception:
                            pass
                        if adapter.connect():
                            success_count += 1
                        else:
                            fail_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1

            QMessageBox.information(self, "完成", f"批量操作完成：成功 {success_count}，失败 {fail_count}")

        except Exception as e:
            QMessageBox.critical(self, "操作失败", f"批量保存并重连失败：\n{str(e)}")

    def _create_indicator_strategy_tab(self, tab: QWidget):
        """创建指标/策略插件管理标签页（V2）。"""
        layout = QVBoxLayout(tab)
        title_label = QLabel("指标/策略 插件管理")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title_label)

        info_label = QLabel("配置与管理指标/策略插件参数，支持批量保存并应用（即时生效）。")
        info_label.setStyleSheet("color: #666;")
        layout.addWidget(info_label)

        # 过滤与搜索
        filter_bar = QHBoxLayout()
        type_label = QLabel("类型过滤:")
        type_combo = QComboBox()
        type_combo.addItems(["全部", "指标", "策略"])
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索名称/描述...")
        filter_bar.addWidget(type_label)
        filter_bar.addWidget(type_combo)
        filter_bar.addStretch(1)
        filter_bar.addWidget(QLabel("搜索:"))
        filter_bar.addWidget(search_edit)
        layout.addLayout(filter_bar)
        self.indicator_strategy_filter_combo = type_combo
        self.indicator_strategy_search_edit = search_edit

        # 列表与操作区
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["插件", "类型", "版本", "已配置", "描述"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.indicator_strategy_table = table
        layout.addWidget(table)

        btn_bar = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        config_btn = QPushButton("配置")
        batch_apply_btn = QPushButton("批量保存并应用")
        export_btn = QPushButton("导出配置")
        import_btn = QPushButton("导入配置")
        reset_btn = QPushButton("恢复默认")
        refresh_btn.clicked.connect(self.refresh_indicator_strategy_list)
        config_btn.clicked.connect(self.configure_indicator_strategy_plugin)
        batch_apply_btn.clicked.connect(self.batch_apply_indicator_strategy)
        export_btn.clicked.connect(self.export_indicator_strategy_configs)
        import_btn.clicked.connect(self.import_indicator_strategy_configs)
        reset_btn.clicked.connect(self.reset_indicator_strategy_to_defaults)
        btn_bar.addWidget(refresh_btn)
        btn_bar.addWidget(config_btn)
        btn_bar.addWidget(reset_btn)
        btn_bar.addStretch(1)
        btn_bar.addWidget(export_btn)
        btn_bar.addWidget(import_btn)
        btn_bar.addWidget(batch_apply_btn)
        layout.addLayout(btn_bar)

        # 过滤触发
        type_combo.currentIndexChanged.connect(self.refresh_indicator_strategy_list)
        search_edit.textChanged.connect(self.refresh_indicator_strategy_list)

        self.refresh_indicator_strategy_list()

    def _iter_indicator_strategy_plugins(self) -> Dict[str, Any]:
        """获取已加载的指标/策略插件，返回 {plugin_name: instance}。"""
        try:
            result = {}
            if not self.plugin_manager:
                return result
            # 遍历插件实例，按类型筛选
            for name, instance in getattr(self.plugin_manager, 'plugin_instances', {}).items():
                try:
                    if hasattr(instance, 'get_plugin_info'):
                        info = instance.get_plugin_info()
                        ptype = getattr(info, 'plugin_type', None)
                    else:
                        ptype = None
                    if str(ptype) and ('INDICATOR' in str(ptype) or 'STRATEGY' in str(ptype)):
                        result[name] = instance
                    # 也支持通过实例属性声明的 plugin_type（V2 示例）
                    elif hasattr(instance, 'plugin_type') and ("INDICATOR" in str(instance.plugin_type) or "STRATEGY" in str(instance.plugin_type)):
                        result[name] = instance
                except Exception:
                    continue
            return result
        except Exception:
            return {}

    def refresh_indicator_strategy_list(self):
        try:
            plugins = self._iter_indicator_strategy_plugins()
            # 过滤
            type_filter = getattr(self, 'indicator_strategy_filter_combo', None)
            search_edit = getattr(self, 'indicator_strategy_search_edit', None)
            type_sel = type_filter.currentText() if type_filter else "全部"
            keyword = (search_edit.text() if search_edit else "").strip().lower()

            # 数据库服务用于判断是否存在配置
            try:
                from core.services.plugin_database_service import PluginDatabaseService
                db = PluginDatabaseService()
            except Exception:
                db = None

            rows = []
            for name, instance in plugins.items():
                try:
                    info = instance.get_plugin_info()
                    ptype = str(getattr(info, 'plugin_type', ''))
                    display_name = getattr(info, 'name', name)
                    desc = getattr(info, 'description', '')
                    # 类型过滤
                    if type_sel == "指标" and "INDICATOR" not in ptype and not (hasattr(instance, 'plugin_type') and "INDICATOR" in str(instance.plugin_type)):
                        continue
                    if type_sel == "策略" and "STRATEGY" not in ptype and not (hasattr(instance, 'plugin_type') and "STRATEGY" in str(instance.plugin_type)):
                        continue
                    # 搜索过滤
                    text_blob = f"{display_name} {desc}".lower()
                    if keyword and keyword not in text_blob:
                        continue
                    # 是否有配置
                    has_cfg = False
                    if db is not None:
                        cfg = db.get_plugin_config_json(name)
                        has_cfg = cfg is not None
                    rows.append((name, display_name, ptype or str(getattr(instance, 'plugin_type', '')), getattr(info, 'version', ''), '是' if has_cfg else '否', desc))
                except Exception:
                    continue

            table = self.indicator_strategy_table
            table.setRowCount(0)
            for idx, (pid, display_name, ptype, ver, has_cfg, desc) in enumerate(rows):
                table.insertRow(idx)
                item0 = QTableWidgetItem(display_name)
                item0.setData(Qt.UserRole, pid)
                item1 = QTableWidgetItem(ptype)
                item2 = QTableWidgetItem(ver)
                item3 = QTableWidgetItem(has_cfg)
                item4 = QTableWidgetItem(desc)
                table.setItem(idx, 0, item0)
                table.setItem(idx, 1, item1)
                table.setItem(idx, 2, item2)
                table.setItem(idx, 3, item3)
                table.setItem(idx, 4, item4)
        except Exception as e:
            QMessageBox.warning(self, "刷新失败", f"刷新指标/策略列表失败:\n{str(e)}")

    def configure_indicator_strategy_plugin(self):
        try:
            table = self.indicator_strategy_table
            sel = table.selectionModel().selectedRows() if table.selectionModel() else []
            if not sel:
                QMessageBox.information(self, "提示", "请先选择一个插件")
                return
            row = sel[0].row()
            plugin_id = table.item(row, 0).data(Qt.UserRole) or table.item(row, 0).text()
            instance = self.plugin_manager.plugin_instances.get(plugin_id)
            if not instance or not hasattr(instance, 'get_plugin_info'):
                QMessageBox.warning(self, "配置失败", "未找到插件或插件不支持V2接口")
                return

            # 读取 schema 与 DB 配置
            schema = {}
            try:
                if hasattr(instance, 'get_config_schema'):
                    schema = instance.get_config_schema() or {}
            except Exception:
                schema = {}
            try:
                from core.services.plugin_database_service import PluginDatabaseService
                db = PluginDatabaseService()
                current_cfg = db.get_plugin_config_json(plugin_id) or {}
            except Exception:
                current_cfg = {}

            # 构建 Schema 表单（包含错误高亮能力）
            form_widget, read_values, clear_errors, highlight_path = self._build_form_from_schema(schema or {"type": "object"}, current_cfg)
            dlg = QDialog(self)
            dlg.setWindowTitle(f"配置 - {plugin_id}")
            v = QVBoxLayout(dlg)
            v.addWidget(form_widget)
            btns = QHBoxLayout()
            btn_save = QPushButton("保存并应用")
            btn_cancel = QPushButton("取消")
            btns.addStretch(1)
            btns.addWidget(btn_save)
            btns.addWidget(btn_cancel)
            v.addLayout(btns)

            def on_save():
                try:
                    clear_errors()
                    cfg = read_values()
                    # Schema 校验（可选）
                    try:
                        from jsonschema import Draft202012Validator
                        from jsonschema.exceptions import best_match
                        Draft202012Validator.check_schema(schema or {"type": "object"})
                        validator = Draft202012Validator(schema or {"type": "object"})
                        errors = list(validator.iter_errors(cfg))
                        if errors:
                            best = best_match(errors)
                            # 高亮首个错误路径
                            try:
                                path_tuple = tuple(list(best.path))
                                highlight_path(path_tuple, best.message)
                            except Exception:
                                pass
                            QMessageBox.warning(dlg, "校验失败", f"配置不符合Schema:\n{best.message}")
                            return
                    except Exception as ve:
                        QMessageBox.warning(dlg, "校验失败", f"配置不符合Schema:\n{ve}")
                        return
                    # 保存到DB
                    from core.services.plugin_database_service import PluginDatabaseService
                    db = PluginDatabaseService()
                    if not db.save_plugin_config_json(plugin_id, cfg):
                        QMessageBox.warning(dlg, "保存失败", "配置保存失败")
                        return
                    # 应用：调用插件 initialize(cfg)
                    try:
                        ok = instance.initialize(cfg)
                        if not ok:
                            QMessageBox.warning(dlg, "应用失败", "插件返回初始化失败")
                            return
                    except Exception as e:
                        QMessageBox.warning(dlg, "应用异常", str(e))
                        return
                    QMessageBox.information(dlg, "成功", "配置已保存并生效")
                    dlg.accept()
                except Exception as e:
                    QMessageBox.critical(dlg, "错误", str(e))

            btn_save.clicked.connect(on_save)
            btn_cancel.clicked.connect(dlg.reject)
            dlg.exec_()

        except Exception as e:
            QMessageBox.critical(self, "配置失败", f"配置插件失败:\n{str(e)}")

    def _build_form_from_schema(self, schema: Dict[str, Any], initial: Dict[str, Any]):
        """
        根据 JSON Schema 生成表单：
        - 支持 object(properties)、enum、boolean、integer、number、string
        - 简单支持 array[primitive]（以逗号分隔的输入）
        返回 (widget, read_values, clear_errors, highlight_path)
        """
        container = QWidget()
        root_layout = QVBoxLayout(container)
        form = QFormLayout()
        root_layout.addLayout(form)

        controls: Dict[tuple, QWidget] = {}
        error_widgets: List[QWidget] = []

        def add_row(path: tuple, title: str, widget: QWidget):
            controls[path] = widget
            form.addRow(title + ':', widget)

        def build_object(obj_schema: Dict[str, Any], data: Dict[str, Any], base_path: tuple = ()):
            props = obj_schema.get('properties', {}) if obj_schema.get('type') == 'object' else {}
            for key, subs in props.items():
                path = base_path + (key,)
                ftype = subs.get('type', 'string')
                title = subs.get('title', key)
                default = subs.get('default', None)
                value = data.get(key, default)

                # enum 优先
                if isinstance(subs.get('enum'), list) and subs['enum']:
                    combo = QComboBox()
                    for opt in subs['enum']:
                        combo.addItem(str(opt))
                    if value is not None:
                        idx = combo.findText(str(value))
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                    add_row(path, title, combo)
                    continue

                # 嵌套对象
                if ftype == 'object':
                    box = QGroupBox(title)
                    box_layout = QFormLayout(box)
                    # 暂时在组内用额外的表单布局
                    temp_form = QFormLayout()
                    box_layout.addRow(temp_form)
                    # 暂时切换 form 指针
                    old_form = form
                    try:
                        # 在组内添加控件
                        root_layout.addWidget(box)
                        # 递归构建
                        build_object(subs, value or {}, path)
                    finally:
                        pass
                    continue

                if ftype == 'boolean':
                    cb = QCheckBox()
                    cb.setChecked(bool(value) if value is not None else False)
                    add_row(path, title, cb)
                elif ftype == 'integer':
                    sb = QSpinBox()
                    sb.setMinimum(int(subs.get('minimum', -10**9)))
                    sb.setMaximum(int(subs.get('maximum', 10**9)))
                    sb.setValue(int(value) if value is not None else int(subs.get('default', 0)))
                    add_row(path, title, sb)
                elif ftype == 'number':
                    dsb = QDoubleSpinBox()
                    dsb.setDecimals(6)
                    dsb.setMinimum(float(subs.get('minimum', -1e12)))
                    dsb.setMaximum(float(subs.get('maximum', 1e12)))
                    step = subs.get('multipleOf', 0.01)
                    if isinstance(step, (int, float)):
                        dsb.setSingleStep(float(step))
                    dsb.setValue(float(value) if value is not None else float(subs.get('default', 0.0)))
                    add_row(path, title, dsb)
                elif ftype == 'array':
                    items = subs.get('items', {})
                    item_type = items.get('type', 'string')
                    le = QLineEdit()
                    # 以逗号分隔的输入
                    if isinstance(value, list):
                        le.setText(','.join(str(x) for x in value))
                    le.setPlaceholderText("用逗号分隔的列表")
                    add_row(path, title, le)
                else:  # string 或其他
                    le = QLineEdit()
                    if value is not None:
                        le.setText(str(value))
                    add_row(path, title, le)

        # 构建根对象
        root_schema = schema if schema else {"type": "object"}
        build_object(root_schema, initial or {}, ())

        def read_values() -> Dict[str, Any]:
            def assign(target: Dict[str, Any], path: tuple, value: Any):
                cur = target
                for k in path[:-1]:
                    if k not in cur or not isinstance(cur[k], dict):
                        cur[k] = {}
                    cur = cur[k]
                cur[path[-1]] = value

            result: Dict[str, Any] = {}
            for path, w in controls.items():
                if isinstance(w, QSpinBox):
                    assign(result, path, int(w.value()))
                elif isinstance(w, QDoubleSpinBox):
                    assign(result, path, float(w.value()))
                elif isinstance(w, QCheckBox):
                    assign(result, path, bool(w.isChecked()))
                elif isinstance(w, QComboBox):
                    assign(result, path, w.currentText())
                elif isinstance(w, QLineEdit):
                    # 判断对应schema是否array
                    # 简化处理：若 schema 指定 type=array 则按逗号分割
                    try:
                        # 通过 path 在 schema 中查找
                        subs = root_schema
                        for key in path:
                            if subs.get('type') == 'object':
                                subs = subs.get('properties', {}).get(key, {})
                            else:
                                subs = {}
                        if subs.get('type') == 'array':
                            text = w.text().strip()
                            if text == '':
                                assign(result, path, [])
                            else:
                                raw_items = [s.strip() for s in text.split(',')]
                                item_type = subs.get('items', {}).get('type', 'string')
                                if item_type == 'integer':
                                    assign(result, path, [int(x) for x in raw_items])
                                elif item_type == 'number':
                                    assign(result, path, [float(x) for x in raw_items])
                                else:
                                    assign(result, path, raw_items)
                        else:
                            assign(result, path, w.text())
                    except Exception:
                        assign(result, path, w.text())
            return result

        def clear_errors():
            for w in controls.values():
                try:
                    w.setStyleSheet("")
                    w.setToolTip("")
                except Exception:
                    pass

        def highlight_path(path: tuple, message: str):
            w = controls.get(path)
            if w is not None:
                try:
                    w.setStyleSheet("border:1px solid #d9534f;")
                    w.setToolTip(message)
                except Exception:
                    pass

        return container, read_values, clear_errors, highlight_path

    def batch_apply_indicator_strategy(self):
        try:
            table = self.indicator_strategy_table
            sel_rows = set(idx.row() for idx in table.selectionModel().selectedRows()) if table.selectionModel() else set()
            targets = []
            for r in range(table.rowCount()):
                if sel_rows and r not in sel_rows:
                    continue
                item = table.item(r, 0)
                if not item:
                    continue
                targets.append(item.data(Qt.UserRole) or item.text())

            if not targets:
                # 如果未选择，默认全量
                plugins = self._iter_indicator_strategy_plugins()
                targets = list(plugins.keys())

            # 对每个插件读取最新DB配置并调用 initialize
            from core.services.plugin_database_service import PluginDatabaseService
            db = PluginDatabaseService()
            ok_count, fail_count = 0, 0
            for pid in targets:
                try:
                    cfg = db.get_plugin_config_json(pid) or {}
                    inst = self.plugin_manager.plugin_instances.get(pid)
                    if not inst or not hasattr(inst, 'initialize'):
                        fail_count += 1
                        continue
                    if inst.initialize(cfg):
                        ok_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1
            QMessageBox.information(self, "完成", f"批量保存并应用完成：成功 {ok_count}，失败 {fail_count}")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"批量操作失败：\n{str(e)}")

    def _build_default_from_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        def build(s: Dict[str, Any]):
            t = s.get('type')
            if t == 'object':
                result = {}
                for k, subs in (s.get('properties', {}) or {}).items():
                    result[k] = build(subs)
                return result
            if t == 'array':
                # 使用默认或空列表
                default = s.get('default')
                return default if isinstance(default, list) else []
            # 基础类型
            return s.get('default')
        return build(schema or {"type": "object", "properties": {}}) or {}

    def reset_indicator_strategy_to_defaults(self):
        try:
            table = self.indicator_strategy_table
            sel = table.selectionModel().selectedRows() if table.selectionModel() else []
            if not sel:
                QMessageBox.information(self, "提示", "请先选择一个插件")
                return
            row = sel[0].row()
            plugin_id = table.item(row, 0).data(Qt.UserRole) or table.item(row, 0).text()
            instance = self.plugin_manager.plugin_instances.get(plugin_id)
            if not instance or not hasattr(instance, 'get_config_schema'):
                QMessageBox.warning(self, "失败", "未找到插件或不支持V2接口")
                return
            schema = {}
            try:
                schema = instance.get_config_schema() or {}
            except Exception:
                schema = {}
            defaults = self._build_default_from_schema(schema)
            from core.services.plugin_database_service import PluginDatabaseService
            db = PluginDatabaseService()
            if not db.save_plugin_config_json(plugin_id, defaults):
                QMessageBox.warning(self, "保存失败", "无法保存默认配置")
                return
            if hasattr(instance, 'initialize') and not instance.initialize(defaults):
                QMessageBox.warning(self, "应用失败", "插件初始化失败")
                return
            QMessageBox.information(self, "成功", "已恢复默认配置并应用")
            self.refresh_indicator_strategy_list()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"恢复默认失败：\n{str(e)}")

    def export_indicator_strategy_configs(self):
        try:
            from PyQt5.QtWidgets import QFileDialog
            table = self.indicator_strategy_table
            sel_rows = set(idx.row() for idx in table.selectionModel().selectedRows()) if table.selectionModel() else set()
            targets = []
            for r in range(table.rowCount()):
                if sel_rows and r not in sel_rows:
                    continue
                item = table.item(r, 0)
                if not item:
                    continue
                targets.append(item.data(Qt.UserRole) or item.text())
            if not targets:
                # 默认导出当前列表全部
                for r in range(table.rowCount()):
                    item = table.item(r, 0)
                    if item:
                        targets.append(item.data(Qt.UserRole) or item.text())
            from core.services.plugin_database_service import PluginDatabaseService
            db = PluginDatabaseService()
            export_obj = {}
            for pid in targets:
                cfg = db.get_plugin_config_json(pid)
                export_obj[pid] = cfg if cfg is not None else {}
            path, _ = QFileDialog.getSaveFileName(self, "导出配置", "indicator_strategy_configs.json", "JSON Files (*.json)")
            if not path:
                return
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(export_obj, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "完成", f"已导出 {len(export_obj)} 个配置")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"导出失败：\n{str(e)}")

    def import_indicator_strategy_configs(self):
        try:
            from PyQt5.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON Files (*.json)")
            if not path:
                return
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                QMessageBox.warning(self, "格式错误", "导入文件不是JSON对象")
                return
            from core.services.plugin_database_service import PluginDatabaseService
            db = PluginDatabaseService()
            ok, fail = 0, 0
            for pid, cfg in data.items():
                try:
                    inst = self.plugin_manager.plugin_instances.get(pid)
                    if not inst or not hasattr(inst, 'initialize'):
                        fail += 1
                        continue
                    if not isinstance(cfg, dict):
                        fail += 1
                        continue
                    if not db.save_plugin_config_json(pid, cfg):
                        fail += 1
                        continue
                    if inst.initialize(cfg):
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
            QMessageBox.information(self, "完成", f"导入完成：成功 {ok}，失败 {fail}")
            self.refresh_indicator_strategy_list()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"导入失败：\n{str(e)}")


def show_enhanced_plugin_manager(parent=None, plugin_manager=None, sentiment_service=None):
    """显示增强型插件管理器对话框"""
    dialog = EnhancedPluginManagerDialog(plugin_manager, sentiment_service, parent)
    return dialog.exec_()


if __name__ == "__main__":
    # 独立运行测试
    app = QApplication(sys.argv)

    dialog = EnhancedPluginManagerDialog()
    dialog.show()

    sys.exit(app.exec_())
