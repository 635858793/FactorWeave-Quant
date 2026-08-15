from loguru import logger
"""
左侧面板 - 股票列表

提供股票搜索、筛选和管理功能。
"""

import time
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import asyncio  # Added for asyncio.create_task
import pandas as pd
from pathlib import Path
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QComboBox, QPushButton, QLabel, QFrame,
    QMenu, QMessageBox, QProgressBar, QSplitter, QGroupBox,
    QScrollArea, QListWidget, QListWidgetItem, QAbstractItemView,
    QInputDialog, QSizePolicy, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon, QFont

from .base_panel import BasePanel
from core.events.types import StockSelectedEvent, AssetSelectedEvent, AssetTypeChangedEvent
from core.performance import measure_performance
# 引入服务和类型
from core.services import StockService
from core.services.unified_data_manager import UnifiedDataManager
from core.services.asset_service import AssetService
from core.plugin_types import AssetType
from core.indicators.indicators_algorithm import BUILTIN_INDICATORS



class LeftPanel(BasePanel):
    """
    左侧面板 - 多资产列表

    功能：
    1. 多资产类型选择（股票、加密货币、期货等）
    2. 资产搜索和筛选
    3. 资产列表显示
    4. 收藏管理
    5. 资产信息展示
    """

    # 市场代码到中文名称的映射（支持多资产类型）
    MARKET_NAME_MAP = {
        # A股市场
        'sh': '上海',
        'sz': '深圳',
        'bj': '北交所',
        # 加密货币交易所
        'binance': 'Binance',
        'coinbase': 'Coinbase',
        'okx': 'OKX',
        'huobi': '火币',
        # 期货交易所
        'shfe': '上期所',
        'dce': '大商所',
        'czce': '郑商所',
        'cffex': '中金所',
        'ine': '上能源',
        # 外汇
        'forex': '外汇',
        # 港股
        'hk': '香港',
        # 美股
        'us': '美国',
        'nasdaq': '纳斯达克',
        'nyse': '纽交所',
    }

    def __init__(self,
                 stock_service: StockService,
                 data_manager: UnifiedDataManager,
                 parent,
                 coordinator,
                 **kwargs):
        """初始化左侧面板"""
        self.stock_service = stock_service
        self.data_manager = data_manager

        # 尝试获取资产服务
        self.asset_service = None
        self.multi_asset_enabled = False
        try:
            if hasattr(coordinator, 'service_container'):
                self.asset_service = coordinator.service_container.resolve(AssetService)
                self.multi_asset_enabled = True
                logger.info("多资产支持已启用")
        except Exception as e:
            logger.info(f"ℹ 多资产服务不可用，使用股票模式: {e}")

        # 当前选择的资产类型
        self.current_asset_type = AssetType.STOCK_A
        self.current_market = None
        self._current_selected_stock = None
        self._current_selected_name = None

        # 添加防抖相关属性
        self._selection_timer = None
        self._pending_selection = None
        # 缓存没有数据的股票（有上限，防止内存泄漏）
        self._no_data_cache = set()
        self._no_data_cache_max_size = 2000  # 最大缓存2000条
        # 启动定时清理
        self._cache_cleanup_timer = QTimer()
        self._cache_cleanup_timer.timeout.connect(self._cleanup_no_data_cache)
        self._cache_cleanup_timer.start(300000)  # 每5分钟清理一次

        self.current_stocks = []
        self.favorites = set()
        self.search_timer = QTimer()

        # 初始化指标相关属性
        self.builtin_indicators = []
        self.talib_indicators = []
        self.custom_indicators = []
        self.all_indicators = []

        super().__init__(parent, coordinator, **kwargs)

    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        # 调用父类方法
        super()._register_event_handlers()

        # 注册多屏模式切换事件处理
        from core.events.types import MultiScreenToggleEvent
        self.event_bus.subscribe(MultiScreenToggleEvent, self.on_multi_screen_toggled)

        # 注册资产类型变更事件处理（确保LeftPanel自身也能响应）
        from core.events.types import AssetTypeChangedEvent
        self.event_bus.subscribe(AssetTypeChangedEvent, self._on_own_asset_type_changed)

    def _create_widgets(self) -> None:
        """创建UI组件"""
        # 创建主布局
        main_layout = QVBoxLayout(self._root_frame)
        main_layout.setContentsMargins(10, 10, 10, 10)
        # main_layout.setSpacing(10)

        # 创建资产类型选择区域（如果启用多资产支持）
        if self.multi_asset_enabled:
            self._create_asset_type_selector(main_layout)

        # 创建搜索区域
        self._create_search_area(main_layout)

        # 创建筛选区域
        self._create_filter_area(main_layout)

        # 创建资产列表（原股票列表）
        self._create_asset_list(main_layout)

        # 创建指标列表
        self._create_indicator_section(main_layout)

        # 创建状态栏
        self._create_status_bar(main_layout)

    def _create_asset_type_selector(self, layout: QVBoxLayout) -> None:
        """创建资产类型选择器（支持20+种资产类型）"""
        try:
            asset_type_group = QGroupBox("资产类型")
            asset_type_layout = QVBoxLayout(asset_type_group)

            self.asset_type_combo = QComboBox()

            asset_types = [
                ("📈 A股", AssetType.STOCK_A),
                ("📈 B股", AssetType.STOCK_B),
                ("📈 H股", AssetType.STOCK_H),
                ("📈 美股", AssetType.STOCK_US),
                ("📈 港股", AssetType.STOCK_HK),
                ("指数", AssetType.INDEX),
                ("基金", AssetType.FUND),
                ("债券", AssetType.BOND),
                ("期货", AssetType.FUTURES),
                ("期权", AssetType.OPTION),
                ("权证", AssetType.WARRANT),
                ("商品", AssetType.COMMODITY),
                ("🪙 加密货币", AssetType.CRYPTO),
                ("💱 外汇", AssetType.FOREX),
                ("🏛️ 板块", AssetType.SECTOR),
                ("🏭 行业板块", AssetType.INDUSTRY_SECTOR),
                ("💡 概念板块", AssetType.CONCEPT_SECTOR),
                ("风格板块", AssetType.STYLE_SECTOR),
                ("主题板块", AssetType.THEME_SECTOR),
                ("📈 宏观经济", AssetType.MACRO),
            ]

            for display_name, asset_type in asset_types:
                self.asset_type_combo.addItem(display_name, asset_type)

            self.asset_type_combo.currentTextChanged.connect(self._on_asset_type_changed)

            asset_type_layout.addWidget(self.asset_type_combo)
            layout.addWidget(asset_type_group)

            logger.info("资产类型选择器创建完成，支持20+种资产类型")

        except Exception as e:
            logger.error(f"创建资产类型选择器失败: {e}")

    def _on_asset_type_changed(self, text: str) -> None:
        """资产类型变更处理（UI控件触发）"""
        try:
            # 获取选中的资产类型
            selected_data = self.asset_type_combo.currentData()
            if selected_data:
                old_type = self.current_asset_type
                self.current_asset_type = selected_data

                logger.info(f"资产类型切换: {old_type.value} → {self.current_asset_type.value}")

                # 清空当前选中的股票（资产类型不同，股票也不同）
                self._current_selected_stock = None
                self._current_selected_name = None

                # 发布资产类型变更事件
                event = AssetTypeChangedEvent(
                    old_asset_type=old_type,
                    new_asset_type=self.current_asset_type,
                    source="left_panel"
                )
                self.event_bus.publish(event)
                logger.info(f"已发布资产类型变更事件: {old_type.value} → {self.current_asset_type.value}")

                # 更新市场过滤器
                self._update_market_filters()

                # 重新加载资产列表
                self._reload_asset_list()

                # 同步指标状态到 MiddlePanel
                self._sync_indicators_to_panel()

        except Exception as e:
            logger.error(f"资产类型变更处理失败: {e}")

    def _sync_indicators_to_panel(self) -> None:
        """同步当前指标状态到 MiddlePanel"""
        try:
            selected_indicators = self.get_selected_indicators()
            if selected_indicators:
                logger.info(f"同步指标到MiddlePanel: {selected_indicators}")
                from core.events import IndicatorChangedEvent
                event = IndicatorChangedEvent(
                    selected_indicators=selected_indicators
                )
                event.data['selected_indicators'] = selected_indicators
                self.event_bus.publish(event)
                logger.debug(f"指标同步事件已发布: {selected_indicators}")
        except Exception as e:
            logger.error(f"同步指标失败: {e}")

    def _on_own_asset_type_changed(self, event: 'AssetTypeChangedEvent') -> None:
        """处理资产类型变更事件（响应其他组件发布的事件）"""
        try:
            # 忽略自己发布的事件（避免重复处理）
            if event.source == "left_panel":
                return

            # 同步UI控件状态
            new_type = event.new_asset_type
            old_type = event.old_asset_type

            logger.info(f"收到资产类型变更事件: {old_type.value} → {new_type.value} (来源: {event.source})")

            # 阻塞资产类型选择器信号，防止触发额外处理
            self.asset_type_combo.blockSignals(True)

            # 更新当前资产类型
            self.current_asset_type = new_type

            # 同步更新资产类型选择器UI
            if hasattr(self, 'asset_type_combo'):
                for i in range(self.asset_type_combo.count()):
                    if self.asset_type_combo.itemData(i) == new_type:
                        self.asset_type_combo.setCurrentIndex(i)
                        break

            # 解除信号阻塞
            self.asset_type_combo.blockSignals(False)

            # 清空当前选中的股票
            self._current_selected_stock = None
            self._current_selected_name = None

            # 更新市场过滤器
            self._update_market_filters()

            # 重新加载资产列表
            self._reload_asset_list()

            # 同步指标状态到 MiddlePanel
            self._sync_indicators_to_panel()

        except Exception as e:
            logger.error(f"处理资产类型变更事件失败: {e}")

    def _update_market_filters(self) -> None:
        """根据资产类型更新市场过滤器"""
        try:
            if not hasattr(self, 'market_combo'):
                return

            # 阻止市场选择器信号，防止触发额外加载
            self.market_combo.blockSignals(True)

            # 定义不同资产类型的市场选项
            market_options = {
                AssetType.STOCK_A: ["全部", "上海", "深圳", "创业板", "科创板", "北交所"],
                AssetType.CRYPTO: ["全部", "Binance", "Coinbase", "OKX", "Huobi"],
                AssetType.FUTURES: ["全部", "上期所", "大商所", "郑商所", "中金所"],
                AssetType.FOREX: ["全部", "主要货币对", "次要货币对", "奇异货币对"],
                AssetType.INDEX: ["全部", "A股指数", "港股指数", "美股指数"],
                AssetType.FUND: ["全部", "股票型", "债券型", "混合型", "货币型"]
            }

            options = market_options.get(self.current_asset_type, ["全部"])

            # 更新市场下拉框
            self.market_combo.clear()
            self.market_combo.addItems(options)

            # 解除信号阻塞
            self.market_combo.blockSignals(False)

            logger.debug(f"市场过滤器已更新: {options}")

        except Exception as e:
            logger.error(f"更新市场过滤器失败: {e}")

    def _reload_asset_list(self) -> None:
        """重新加载资产列表（统一入口，支持所有资产类型）"""
        try:
            logger.info(f"开始重新加载资产列表，资产类型: {self.current_asset_type.value}")

            # 获取当前市场过滤
            market = None
            if hasattr(self, 'market_combo'):
                market_text = self.market_combo.currentText()
                if market_text != "全部":
                    market = market_text

            logger.debug(f"当前市场过滤: {market}")

            # 优先使用统一数据管理器加载数据（支持所有资产类型）
            from core.services.unified_data_manager import get_unified_data_manager
            data_manager = get_unified_data_manager()

            if data_manager:
                # 转换资产类型为字符串
                asset_type_str = self.current_asset_type.value.lower()
                logger.debug(f"调用 get_asset_list，asset_type={asset_type_str}, market={market}")
                asset_df = data_manager.get_asset_list(asset_type=asset_type_str, market=market)
                logger.debug(f"返回的DataFrame: {len(asset_df)} 行")

                if not asset_df.empty:
                    # 转换DataFrame为资产列表格式
                    assets = []
                    for _, row in asset_df.iterrows():
                        assets.append({
                            'symbol': row.get('code', ''),
                            'name': row.get('name', ''),
                            'asset_type': self.current_asset_type.value,
                            'market': row.get('market', ''),
                            'industry': row.get('industry', ''),
                            'sector': row.get('sector', ''),
                            'status': row.get('status', 'active')
                        })
                    self._populate_asset_table(assets)
                    self._update_status(f"已加载 {len(assets)} 个{self.current_asset_type.value}资产")
                else:
                    self._clear_asset_list()
                    self._update_status(f"暂无{self.current_asset_type.value}资产数据")
            else:
                # 降级：尝试使用传统方式
                logger.warning("统一数据管理器不可用，尝试传统加载方式")
                if self.current_asset_type == AssetType.STOCK_A:
                    self._load_stock_list_legacy()
                else:
                    self._clear_asset_list()
                    self._update_status("数据管理器不可用")

        except Exception as e:
            logger.error(f"重新加载资产列表失败: {e}")
            self._update_status(f"加载{self.current_asset_type.value}资产失败")

    def _clear_asset_list(self) -> None:
        """清空资产列表"""
        try:
            if hasattr(self, 'stock_tree'):
                self.stock_tree.clear()
            self._update_status("暂无数据")
        except Exception as e:
            logger.error(f"清空资产列表失败: {e}")

    def _populate_asset_table(self, assets: List[Dict[str, Any]]) -> None:
        """填充资产表格"""
        try:
            if not hasattr(self, 'stock_tree'):
                return

            # 清空现有数据
            self.stock_tree.clear()

            # 添加新数据
            for asset in assets:
                item = QTreeWidgetItem()

                # 安全地设置文本，处理NA值
                def safe_text(value):
                    """安全地转换值为字符串，处理pandas NA值"""
                    if value is None:
                        return ''
                    if pd.isna(value):  # 处理pandas NA值
                        return ''
                    return str(value)

                # 获取原始数据
                symbol = safe_text(asset.get('symbol', ''))
                market = safe_text(asset.get('market', '')).lower()
                name = safe_text(asset.get('name', ''))
                industry = safe_text(asset.get('industry', ''))

                # 组合市场编码（如：sz000001）
                market_code = f"{market}{symbol}" if market and symbol else symbol

                # 设置列数据
                item.setText(0, market_code)  # 市场编码（如sz000001）
                item.setText(1, name)         # 名称
                item.setText(2, market.upper() if market else '')  # 市场（大写显示）
                item.setText(3, industry)     # 行业

                # 存储完整的资产信息
                item.setData(0, Qt.UserRole, asset)

                self.stock_tree.addTopLevelItem(item)

            # 更新当前资产列表
            self.current_stocks = assets

            logger.info(f"资产表格已更新: {len(assets)} 条记录")

        except Exception as e:
            logger.error(f"填充资产表格失败: {e}")

    def _load_stock_list_legacy(self) -> None:
        """DuckDB优先方式加载股票列表"""
        try:
            # 使用统一数据管理器的新方法
            from core.services.unified_data_manager import get_unified_data_manager
            data_manager = get_unified_data_manager()

            if data_manager:
                # 获取当前市场过滤
                market = 'all'
                if hasattr(self, 'market_combo'):
                    market_text = self.market_combo.currentText()
                    if market_text != "全部":
                        market = market_text.lower()

                # 使用新的资产列表方法 - 修复：使用当前选中的资产类型而非硬编码的 'stock_a'
                current_asset_type = self.current_asset_type.value.lower()
                stock_df = data_manager.get_asset_list(asset_type=current_asset_type, market=market)

                if not stock_df.empty:
                    # 转换为统一格式
                    assets = []
                    for _, stock in stock_df.iterrows():
                        assets.append({
                            'symbol': stock.get('code', ''),
                            'name': stock.get('name', ''),
                            'asset_type': self.current_asset_type.value,
                            'market': stock.get('market', ''),
                            'industry': stock.get('industry', ''),
                            'sector': stock.get('sector', ''),
                            'status': stock.get('status', 'active')
                        })
                    self._populate_asset_table(assets)
                    self._update_status(f"已加载 {len(assets)} 个{self.current_asset_type.value}资产（来自DuckDB）")
                else:
                    self._clear_asset_list()
                    self._update_status("DuckDB中暂无股票数据，请运行数据导入脚本")
            else:
                self._clear_asset_list()
                self._update_status("统一数据管理器不可用")
        except Exception as e:
            logger.error(f"传统方式加载股票列表失败: {e}")
            self._update_status("加载股票列表失败")

    def _create_search_area(self, parent_layout: QVBoxLayout) -> None:
        """创建搜索区域"""
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(0, 0, 0, 0)

        # 搜索标签
        search_label = QLabel("搜索:")
        search_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入股票代码或名称...")
        self.search_input.setClearButtonEnabled(True)

        # 搜索按钮
        search_btn = QPushButton("搜索")
        search_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 高级搜索按钮
        advanced_search_btn = QPushButton("高级搜索")
        advanced_search_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        advanced_search_btn.clicked.connect(self._show_advanced_search)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        search_layout.addWidget(advanced_search_btn)

        parent_layout.addWidget(search_frame)

        # 保存组件引用
        self.add_widget('search_frame', search_frame)
        self.add_widget('search_input', self.search_input)
        self.add_widget('search_btn', search_btn)

    def _create_filter_area(self, parent_layout: QVBoxLayout) -> None:
        """创建筛选区域"""
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)

        # 市场筛选
        market_label = QLabel("市场:")
        market_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.market_combo = QComboBox()
        self.market_combo.addItems(["全部", "上海", "深圳", "创业板", "科创板"])
        self.market_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 收藏筛选
        self.favorites_btn = QPushButton("收藏")
        self.favorites_btn.setCheckable(True)
        self.favorites_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        filter_layout.addWidget(market_label)
        filter_layout.addWidget(self.market_combo)
        filter_layout.addWidget(self.favorites_btn)
        filter_layout.addStretch()
        filter_layout.addWidget(refresh_btn)

        parent_layout.addWidget(filter_frame)

        # 保存组件引用
        self.add_widget('filter_frame', filter_frame)
        self.add_widget('market_combo', self.market_combo)
        self.add_widget('favorites_btn', self.favorites_btn)
        self.add_widget('refresh_btn', refresh_btn)

    def _create_asset_list(self, parent_layout: QVBoxLayout) -> None:
        """创建资产列表（支持多资产类型）"""
        # 股票列表
        self.stock_tree = QTreeWidget()
        self.stock_tree.setHeaderLabels(["代码", "名称","市场","行业"])
        self.stock_tree.setRootIsDecorated(False)
        # self.stock_tree.setAlternatingRowColors(True)
        self.stock_tree.setSortingEnabled(True)

        # 设置列宽
        self.stock_tree.setColumnWidth(0, 80)   # 代码
        self.stock_tree.setColumnWidth(1, 80)  # 名称
        self.stock_tree.setColumnWidth(2, 40)   # 市场
        self.stock_tree.setColumnWidth(3, 100)  # 行业
        # self.stock_tree.setColumnWidth(4, 60)   # 类型

        # 启用拖拽功能
        self.stock_tree.setDragEnabled(True)
        self.stock_tree.setDragDropMode(QAbstractItemView.DragOnly)

        # 自定义拖拽开始事件
        self.stock_tree.startDrag = lambda action: self._start_drag(action)

        # 启用右键菜单
        self.stock_tree.setContextMenuPolicy(Qt.CustomContextMenu)

        parent_layout.addWidget(self.stock_tree)

        # 保存组件引用
        self.add_widget('stock_tree', self.stock_tree)

    def _start_drag(self, action):
        """自定义拖拽开始事件，设置MIME数据"""
        try:
            item = self.stock_tree.currentItem()
            if not item:
                return

            # 从存储的数据中获取股票信息
            asset_data = item.data(0, Qt.UserRole) or {}
            stock_code = asset_data.get('code', '')  # 纯代码，如 000001
            stock_name = item.text(1)
            market = asset_data.get('market', '')  # 市场前缀，如 sz

            # 组合显示用的完整代码（带市场前缀）
            display_code = f"{market}{stock_code}" if market else stock_code

            # 创建MIME数据
            from PyQt5.QtCore import QMimeData
            from PyQt5.QtGui import QDrag

            mime_data = QMimeData()
            # 设置文本格式，使用带市场前缀的完整代码
            mime_data.setText(f"{display_code} {stock_name}")
            # 设置自定义格式，传递纯代码和市场前缀
            mime_data.setData("application/x-stock-code", stock_code.encode("utf-8"))
            mime_data.setData("application/x-stock-name", stock_name.encode("utf-8"))
            mime_data.setData("application/x-stock-market", market.encode("utf-8"))

            # 创建拖拽对象
            drag = QDrag(self.stock_tree)
            drag.setMimeData(mime_data)

            # 执行拖拽
            drag.exec_(action)

        except Exception as e:
            logger.error(f"开始拖拽时出错: {e}", exc_info=True)

    def _create_status_bar(self, parent_layout: QVBoxLayout) -> None:
        """创建状态栏"""
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666666; font-size: 12px;")

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        # self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 股票数量标签
        self.count_label = QLabel("股票: 0")
        self.count_label.setStyleSheet("color: #666666; font-size: 12px;")

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.count_label)

        parent_layout.addWidget(status_frame)

        # 保存组件引用
        self.add_widget('status_frame', status_frame)
        self.add_widget('status_label', self.status_label)
        self.add_widget('progress_bar', self.progress_bar)
        self.add_widget('count_label', self.count_label)

    def _bind_events(self) -> None:
        """绑定事件"""
        try:
            # 搜索事件
            self.search_input.textChanged.connect(self._on_search_text_changed)
            self.get_widget('search_btn').clicked.connect(
                self._on_search_clicked)

            # 筛选事件
            self.market_combo.currentTextChanged.connect(
                self._on_market_changed)
            self.favorites_btn.toggled.connect(self._on_favorites_toggled)
            self.get_widget('refresh_btn').clicked.connect(
                self._on_refresh_clicked)

            # 股票列表事件
            self.stock_tree.itemClicked.connect(self._on_stock_clicked)
            self.stock_tree.itemDoubleClicked.connect(
                self._on_stock_double_clicked)
            self.stock_tree.customContextMenuRequested.connect(
                self._on_context_menu)

            # 搜索延迟定时器
            self.search_timer.timeout.connect(self._perform_search)
            self.search_timer.setSingleShot(True)

            # 股票选择防抖定时器
            self._selection_timer = QTimer()
            self._selection_timer.timeout.connect(
                self._process_pending_selection)
            self._selection_timer.setSingleShot(True)

            logger.debug("LeftPanel events bound successfully")

        except Exception as e:
            logger.error(f"Failed to bind LeftPanel events: {e}")
            raise

    def _initialize_data(self) -> None:
        """初始化数据"""
        try:
            # 加载初始数据
            self._load_stock_data()

        except Exception as e:
            logger.error(f"Failed to initialize LeftPanel data: {e}")

    @pyqtSlot(str)
    def _on_search_text_changed(self, text: str) -> None:
        """搜索文本变化处理"""
        # 延迟搜索，避免频繁请求
        self.search_timer.stop()
        self.search_timer.start(500)  # 500ms延迟

    @pyqtSlot()
    def _on_search_clicked(self) -> None:
        """搜索按钮点击处理"""
        self._perform_search()

    @pyqtSlot(str)
    def _on_market_changed(self, market: str) -> None:
        """市场筛选变化处理"""
        self._load_stock_data()

    @pyqtSlot(bool)
    def _on_favorites_toggled(self, checked: bool) -> None:
        """收藏筛选切换处理"""
        self._load_stock_data()

    @pyqtSlot()
    def _on_refresh_clicked(self) -> None:
        """刷新按钮点击处理"""
        self._load_stock_data()

    def _is_multi_screen_mode(self) -> bool:
        """
        检查当前是否处于多屏模式

        Returns:
            bool: 如果当前处于多屏模式返回True，否则返回False
        """
        try:
            # 通过协调器获取中间面板
            if self.coordinator:
                middle_panel = self.coordinator.get_panel('middle')
                if middle_panel and hasattr(middle_panel, '_multi_screen_panel'):
                    return middle_panel._multi_screen_panel is not None
            return False
        except Exception as e:
            logger.error(f"检查多屏模式失败: {e}")
            return False

    @pyqtSlot(QTreeWidgetItem, int)
    def _on_stock_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """股票点击处理"""
        # 在多屏模式下，不响应点击事件，只支持拖拽
        if self._is_multi_screen_mode():
            logger.debug("多屏模式下不响应股票点击事件，请使用拖拽功能")
            self.show_message("多屏模式下请拖拽股票到目标图表", level="info")
            return

        if item:
            # 从存储的数据中获取纯代码和市场前缀
            asset_data = item.data(0, Qt.UserRole) or {}
            stock_code = asset_data.get('code', '')  # 纯代码，如 000001
            stock_name = item.text(1)
            market = asset_data.get('market', '')  # 市场前缀，如 sz
            self._debounced_select_stock(stock_code, stock_name, market)

    @pyqtSlot(QTreeWidgetItem, int)
    def _on_stock_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """处理资产双击事件（支持多资产类型）"""
        # 在多屏模式下，不响应双击事件，只支持拖拽
        if self._is_multi_screen_mode():
            logger.debug(f"多屏模式下不响应{self.current_asset_type.value}双击事件，请使用拖拽功能")
            self.show_message(f"多屏模式下请拖拽{self.current_asset_type.value}到目标图表", level="info")
            return

        # 从存储的数据中获取资产信息
        asset_data = item.data(0, Qt.UserRole) or {}
        symbol = asset_data.get('code', '')  # 纯代码，如 000001
        name = item.text(1)
        market = asset_data.get('market', '')  # 市场前缀，如 sz

        # 选择资产
        self._select_asset(symbol, name, market)

    def _select_asset(self, symbol: str, name: str, market: str = "") -> None:
        """选择资产（支持多资产类型）"""
        try:
            logger.info(f"选择资产: {symbol} ({name}) - 类型: {self.current_asset_type.value}")

            period = ''
            time_range = ''
            chart_type = ''
            if self.coordinator:
                middle_panel = self.coordinator.get_panel('middle')
                if middle_panel:
                    period = getattr(middle_panel, '_current_period', '')
                    time_range = getattr(middle_panel, '_current_time_range', '')
                    chart_type = getattr(middle_panel, '_current_chart_type', '')
                    logger.debug(f"从MiddlePanel获取筛选条件: period={period}, time_range={time_range}, chart_type={chart_type}")

            if self.current_asset_type == AssetType.STOCK_A:
                stock_event = StockSelectedEvent(
                    stock_code=symbol,
                    stock_name=name,
                    market=market,
                    asset_type=self.current_asset_type,
                    period=period,
                    time_range=time_range,
                    chart_type=chart_type
                )
                self.event_bus.publish(stock_event)

                asset_event = AssetSelectedEvent(
                    symbol=symbol,
                    name=name,
                    asset_type=self.current_asset_type,
                    market=market,
                    period=period,
                    time_range=time_range,
                    chart_type=chart_type
                )
                self.event_bus.publish(asset_event)

            else:
                asset_event = AssetSelectedEvent(
                    symbol=symbol,
                    name=name,
                    asset_type=self.current_asset_type,
                    market=market,
                    period=period,
                    time_range=time_range,
                    chart_type=chart_type
                )
                self.event_bus.publish(asset_event)

            self._update_status(f"已选择: {symbol} ({name})")

        except Exception as e:
            logger.error(f"选择资产失败: {e}")
            self._update_status("选择资产失败")

    def _on_context_menu(self, position) -> None:
        """右键菜单处理"""
        item = self.stock_tree.itemAt(position)
        if not item:
            return

        # 从存储的数据中获取股票信息
        asset_data = item.data(0, Qt.UserRole) or {}
        stock_code = asset_data.get('code', '')  # 纯代码，如 000001
        stock_name = item.text(1)
        market = asset_data.get('market', '')  # 市场前缀，如 sz

        # 组合显示用的完整代码（带市场前缀）
        display_code = f"{market}{stock_code}" if market else stock_code

        # 创建右键菜单
        menu = QMenu(self.stock_tree)

        # 查看详情
        action = menu.addAction("查看详情")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._show_stock_details(c, n))

        # 添加到收藏/取消收藏
        if stock_code in self.favorites:
            action = menu.addAction("从收藏移除")
            action.triggered.connect(
                lambda c=stock_code: self._remove_from_favorites(c))
        else:
            action = menu.addAction("添加到收藏")
            action.triggered.connect(
                lambda c=stock_code, n=stock_name: self._add_to_favorites(c, n))

        menu.addSeparator()

        # 导出数据
        action = menu.addAction("导出数据")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._export_stock_data(c, n))

        menu.addSeparator()

        # 添加到自选股
        action = menu.addAction("添加到自选股")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._add_to_watchlist(c, n))

        # 添加到投资组合
        action = menu.addAction("添加到投资组合")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._add_to_portfolio(c, n))

        menu.addSeparator()

        # 分析功能
        action = menu.addAction("技术分析")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._analyze_stock(c, n))

        action = menu.addAction("策略回测")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._backtest_stock(c, n))

        menu.addSeparator()

        # 管理功能
        action = menu.addAction("历史数据管理")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._manage_history_data(c, n))

        action = menu.addAction("策略管理")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._manage_strategy(c, n))

        menu.addSeparator()

        # 工具功能
        action = menu.addAction("数据质量检查")
        action.triggered.connect(
            lambda c=stock_code, n=stock_name: self._check_data_quality(c, n))

        action = menu.addAction("计算器")
        action.triggered.connect(lambda: self._show_calculator())

        action = menu.addAction("单位转换器")
        action.triggered.connect(lambda: self._show_converter())

        # 显示菜单
        menu.exec_(self.stock_tree.mapToGlobal(position))

    def _perform_search(self) -> None:
        """执行搜索"""
        search_text = self.search_input.text().strip()
        self._load_stock_data(search_text=search_text)

    def _show_advanced_search(self) -> None:
        """显示高级搜索对话框（非模态）"""
        try:
            # 简化导入路径
            from gui.dialogs.advanced_search_dialog import AdvancedSearchDialog

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            dialog = AdvancedSearchDialog(
                parent=main_window, stock_service=self.stock_service)
            dialog.search_completed.connect(self._on_advanced_search)
            dialog.show()  # 使用 show() 而不是 exec_() 来显示非模态对话框

            logger.info("高级搜索对话框已打开（非模态）")

        except Exception as e:
            logger.error(f"显示高级搜索对话框失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(main_window, "错误", f"无法打开高级搜索对话框: {str(e)}")

    def _on_advanced_search(self, results: List[Dict[str, Any]]) -> None:
        """处理高级搜索结果"""
        try:
            # 更新股票列表显示
            self._update_stock_tree(results)

            logger.info(f"高级搜索完成，找到 {len(results)} 只符合条件的股票")

        except Exception as e:
            logger.error(f"处理高级搜索结果失败: {e}")

    def _export_stock_data(self, stock_code: str, stock_name: str) -> None:
        """导出股票数据"""
        try:
            from PyQt5.QtWidgets import QMessageBox
            import pandas as pd
            from datetime import datetime

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            # 获取股票详细信息
            stock_info = self.stock_service.get_stock_info(stock_code)
            if not stock_info:
                QMessageBox.warning(main_window, "警告",
                                    f"无法获取股票 {stock_name} 的信息")
                return

            # 获取历史数据
            stock_data = self.stock_service.get_stock_data(
                stock_code, period='D', count=100)

            # 准备基本信息
            basic_info = [
                {'项目': '股票代码', '值': stock_code},
                {'项目': '股票名称', '值': stock_name},
                {'项目': '所属市场', '值': stock_info.get('market', '未知')},
                {'项目': '所属行业', '值': stock_info.get('industry', '未知')},
                {'项目': '上市日期', '值': stock_info.get('list_date', '未知')},
                {'项目': '总股本', '值': stock_info.get('total_shares', 0)},
                {'项目': '流通股本', '值': stock_info.get('circulating_shares', 0)}
            ]

            basic_df = pd.DataFrame(basic_info)

            # 准备历史数据
            history_df = stock_data if stock_data is not None and not stock_data.empty else pd.DataFrame()

            # 导出到Excel
            filename = f"stock_{stock_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

            with pd.ExcelWriter(filename) as writer:
                basic_df.to_excel(writer, sheet_name="基本信息", index=False)
                if not history_df.empty:
                    history_df.to_excel(writer, sheet_name="历史数据", index=False)

            QMessageBox.information(main_window, "成功", f"数据已导出到: {filename}")
            logger.info(f"股票数据已导出到: {filename}")

        except Exception as e:
            logger.error(f"导出股票数据失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(main_window, "错误", f"导出数据失败: {e}")

    def _add_to_watchlist(self, stock_code: str, stock_name: str) -> None:
        """添加到自选股"""
        try:
            from PyQt5.QtWidgets import QMessageBox

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            if not stock_code:
                QMessageBox.warning(main_window, "警告", "无效的股票代码")
                return

            # 检查是否已存在于自选股中
            if self.stock_service and hasattr(self.stock_service, 'add_to_favorites'):
                # 检查是否已在自选股中
                favorites = self.stock_service.get_favorites()
                if stock_code in favorites:
                    QMessageBox.information(
                        main_window, "提示", f"股票 {stock_name}({stock_code}) 已在自选股中")
                    return

                # 添加到自选股
                success = self.stock_service.add_to_favorites(stock_code)

                if success:
                    # 更新本地收藏列表
                    self.favorites.add(stock_code)

                    QMessageBox.information(
                        main_window, "成功", f"已添加 {stock_name}({stock_code}) 到自选股")
                    logger.info(f"添加到自选股成功: {stock_name}({stock_code})")

                    # 如果当前正在显示收藏列表，则刷新显示
                    if hasattr(self, 'favorites_btn') and self.favorites_btn.isChecked():
                        self._load_stock_data()
                    else:
                        # 刷新当前股票列表显示，更新收藏状态
                        self._update_stock_tree(self.current_stocks)
                else:
                    QMessageBox.warning(
                        main_window, "失败", f"添加 {stock_name}({stock_code}) 到自选股失败")
                    logger.error(f"添加到自选股失败: {stock_name}({stock_code})")
            else:
                # 当服务不可用时，至少更新本地状态
                self.favorites.add(stock_code)
                self._update_stock_tree(self.current_stocks)
                QMessageBox.information(
                    main_window, "成功", f"已添加 {stock_name}({stock_code}) 到自选股")
                logger.info(f"添加到自选股: {stock_name}({stock_code})")

        except Exception as e:
            logger.error(f"添加到自选股失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(main_window, "错误", f"添加到自选股失败: {e}")

    def _add_to_portfolio(self, stock_code: str, stock_name: str) -> None:
        """添加到投资组合"""
        try:
            from PyQt5.QtWidgets import QMessageBox
            from gui.dialogs.portfolio_dialog import PortfolioDialog

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            if not stock_code:
                QMessageBox.warning(main_window, "警告", "无效的股票代码")
                return

            # 显示投资组合管理对话框
            dialog = PortfolioDialog(parent=main_window)

            # 自动跳转到对应股票（如果已选中组合且持仓中有此股票）
            if hasattr(dialog, 'current_portfolio') and dialog.current_portfolio:
                holdings = dialog.current_portfolio.get('holdings', [])
                for h in holdings:
                    if h.get('code') == stock_code:
                        # 在持仓表格中找到对应行
                        for row in range(dialog.holdings_table.rowCount()):
                            item = dialog.holdings_table.item(row, 0)
                            if item and item.text() == stock_code:
                                dialog.holdings_table.selectRow(row)
                                break
                        break

            # 居中显示
            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info(f"打开投资组合管理对话框: {stock_name}({stock_code})")

        except Exception as e:
            logger.error(f"打开投资组合管理对话框失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(main_window, "错误", f"打开投资组合管理对话框失败: {e}")

    def _analyze_stock(self, stock_code: str, stock_name: str) -> None:
        """技术分析股票"""
        try:
            # 简化导入路径
            from gui.dialogs.technical_analysis_dialog import TechnicalAnalysisDialog

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            # 创建技术分析对话框
            dialog = TechnicalAnalysisDialog(
                main_window, stock_code=stock_code, stock_name=stock_name)

            # 居中显示
            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info(f"Opened technical analysis for stock: {stock_code}")

        except Exception as e:
            logger.error(f"Failed to open technical analysis: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(
                main_window, "错误",
                f"打开技术分析失败: {str(e)}"
            )

    def _backtest_stock(self, stock_code: str, stock_name: str) -> None:
        """策略回测"""
        try:
            from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog

            main_window = self.coordinator.get_main_window() if self.coordinator else None

            dialog = StrategyManagerDialog(main_window)
            if hasattr(dialog, '_switch_view'):
                dialog._switch_view('backtest')

            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info(f"Opened strategy backtest for stock: {stock_code}")

        except Exception as e:
            logger.error(f"Failed to open strategy backtest: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(
                main_window, "错误",
                f"打开策略回测失败: {str(e)}"
            )

    def _manage_history_data(self, stock_code: str, stock_name: str) -> None:
        """历史数据管理"""
        try:
            # 简化导入路径
            from gui.dialogs.history_data_dialog import HistoryDataDialog

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            # 创建历史数据管理对话框
            dialog = HistoryDataDialog(main_window, stock_code=stock_code)

            # 居中显示
            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info(
                f"Opened history data management for stock: {stock_code}")

        except Exception as e:
            logger.error(f"Failed to open history data management: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(
                main_window, "错误",
                f"打开历史数据管理失败: {str(e)}"
            )

    def _manage_strategy(self, stock_code: str, stock_name: str) -> None:
        """策略管理"""
        try:
            from gui.dialogs.strategy_manager_dialog import StrategyManagerDialog

            main_window = self.coordinator.get_main_window() if self.coordinator else None

            dialog = StrategyManagerDialog(main_window)

            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info(f"Opened strategy management for stock: {stock_code}")

        except Exception as e:
            logger.error(f"Failed to open strategy management: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(
                main_window, "错误",
                f"打开策略管理失败: {str(e)}"
            )

    def _update_stock_tree(self, stocks: List[Dict[str, Any]]) -> None:
        """更新股票列表树（从数据库加载已下载的资产）"""
        try:
            self.stock_tree.clear()
            if not stocks:
                self.count_label.setText("股票: 0")
                return

            items = []
            for stock in stocks:
                # 安全地获取字段值
                def safe_text(value):
                    """安全地转换值为字符串,处理pandas NA值"""
                    if value is None:
                        return ''
                    if pd.isna(value):  # 处理pandas NA值
                        return ''
                    return str(value)

                code = safe_text(stock.get('code', ''))
                name = safe_text(stock.get('name', ''))
                market = safe_text(stock.get('market', '')).lower()
                industry = safe_text(stock.get('industry', ''))
                update_time = stock.get('update_time', '未知')

                # 组合市场编码(如:sz000001)
                market_code = f"{market}{code}" if market and code else code

                # 创建树项,包含市场前缀和所有列
                item = QTreeWidgetItem([market_code, name, market.upper() if market else '', industry])

                # 设置Tooltip显示完整信息
                tooltip = f"股票代码: {market_code}\n股票名称: {name}\n市场: {market.upper() if market else '未知'}\n行业: {industry if industry else '未知'}\n更新时间: {update_time}"
                item.setToolTip(0, tooltip)
                item.setToolTip(1, tooltip)
                item.setToolTip(2, tooltip)
                item.setToolTip(3, tooltip)

                # 将完整的股票信息字典存储在item中
                item.setData(0, Qt.UserRole, stock)
                items.append(item)

            self.stock_tree.addTopLevelItems(items)

            # 更新状态显示
            self.count_label.setText(f"股票: {len(stocks)}")

        except Exception as e:
            logger.error(f"更新股票树失败: {e}", exc_info=True)
            self.show_message(f"更新股票列表失败: {e}", 'error')

    def _load_stock_data(self, search_text: str = None) -> None:
        """从数据库加载已下载的股票资产数据"""
        self._show_loading(True)
        self.status_label.setText("正在加载股票列表...")

        try:
            # 从数据库获取已下载的股票列表
            stocks = self._get_stocks_from_database(search_text)

            if stocks:
                logger.info(f"从数据库获取到 {len(stocks)} 只股票")
            else:
                logger.info("数据库中暂无股票数据")

            self._on_data_loaded(stocks)

        except Exception as e:
            logger.error(f"加载股票列表失败: {e}", exc_info=True)
            self._on_data_error(str(e))

    def _get_stocks_from_database(self, search_text: str = None) -> List[Dict[str, Any]]:
        """从数据库获取已下载的股票列表（支持资产分离架构）"""
        try:
            # 获取当前选择的资产类型
            current_asset_type = getattr(self, 'current_asset_type', None)
            if current_asset_type:
                logger.debug(f"查询资产数据库: {current_asset_type.value}")

            # 优先尝试直接从DuckDB文件读取数据（传递资产类型）
            stocks_df = self._direct_query_duckdb_stocks(search_text, current_asset_type)

            if not stocks_df.empty:
                # 转换为标准格式
                stocks = []
                for _, row in stocks_df.iterrows():
                    stock_info = {
                        'code': str(row.get('code', '')),
                        'name': str(row.get('name', '')),
                        'market': str(row.get('market', '')),
                        'industry': str(row.get('industry', '')),
                        'sector': str(row.get('sector', '')),
                        'asset_type': str(row.get('asset_type', 'stock_a')),
                        'update_time': row.get('update_time', '')
                    }

                    # 应用搜索过滤
                    if search_text:
                        search_lower = search_text.lower()
                        if (search_lower not in stock_info['code'].lower() and
                                search_lower not in stock_info['name'].lower()):
                            continue

                    stocks.append(stock_info)

                logger.info(f"从数据库获取股票列表成功: {len(stocks)} 只股票")
                return stocks

            # 备选方案：通过TET框架和DuckDB获取已下载的股票列表
            if hasattr(self.data_manager, '_uni_plugin_manager') and self.data_manager._uni_plugin_manager:
                uni_manager = self.data_manager._uni_plugin_manager

                # 获取市场过滤条件
                market = None
                if hasattr(self, 'market_combo') and self.market_combo:
                    market_text = self.market_combo.currentText()
                    if market_text != "全部":
                        market = market_text

                # 从DuckDB的asset_metadata表查询数据
                stocks_df = self._query_stocks_from_duckdb(uni_manager, market, search_text)

                if not stocks_df.empty:
                    # 转换为标准格式
                    stocks = []
                    for _, row in stocks_df.iterrows():
                        stock_info = {
                            'code': str(row.get('code', '')),
                            'name': str(row.get('name', '')),
                            'market': str(row.get('market', '')),
                            'industry': str(row.get('industry', '')),
                            'sector': str(row.get('sector', '')),
                            'asset_type': str(row.get('asset_type', 'STOCK')),
                            'update_time': row.get('update_time', '')
                        }

                        # 应用搜索过滤
                        if search_text:
                            search_lower = search_text.lower()
                            if (search_lower not in stock_info['code'].lower() and
                                    search_lower not in stock_info['name'].lower()):
                                continue

                        stocks.append(stock_info)

                    logger.info(f"从数据库获取股票列表成功: {len(stocks)} 只股票")
                    return stocks

            logger.debug("无法从数据库获取股票列表")
            return []

        except Exception as e:
            logger.error(f"从数据库获取股票列表失败: {e}")
            return []

    def _direct_query_duckdb_stocks(self, search_text: str = None, asset_type: 'AssetType' = None) -> pd.DataFrame:
        """
        直接查询DuckDB数据库中的股票列表

        Args:
            search_text: 搜索关键词
            asset_type: 资产类型，如果为None则使用当前选择的资产类型

        Returns:
            pd.DataFrame: 查询结果
        """
        try:
            import duckdb

            # 获取数据库路径（传递资产类型）
            db_path = self._get_stock_database_path(asset_type)

            # 检查数据库文件是否存在
            if not Path(db_path).exists():
                logger.debug(f"DuckDB文件不存在: {db_path}")
                return pd.DataFrame()

            # 获取市场过滤条件
            market = None
            if hasattr(self, 'market_combo') and self.market_combo:
                market_text = self.market_combo.currentText()
                if market_text != "全部":
                    market = market_text

            # 构建查询条件
            query_conditions = []

            # 添加资产类型过滤（确保查询结果与选择的资产类型一致）
            # 使用参数化查询防止SQL注入
            if asset_type:
                query_conditions.append("asset_type = ?")

            if market:
                # 根据市场名称映射到数据库中的market字段
                market_mapping = {
                    "上海": "sh",
                    "深圳": "sz",
                    "创业板": "sz",
                    "科创板": "sh",
                    "北交所": "bj"
                }
                db_market = market_mapping.get(market, market.lower())
                query_conditions.append("market = ?")

            # 准备查询参数
            query_params = []
            if asset_type:
                query_params.append(asset_type.value)
            if market:
                query_params.append(db_market)

            if search_text:
                safe_search = search_text.replace('%', '\\%').replace('_', '\\_')
                search_condition = "(symbol LIKE '%' || ? || '%' ESCAPE '\\' OR name LIKE '%' || ? || '%' ESCAPE '\\')"
                query_conditions.append(search_condition)
                query_params.extend([safe_search, safe_search])

            # 修复：从asset_metadata表查询（这是数据导入时保存资产元数据的表）
            # 字段映射：symbol→code（UI使用code字段）
            # 添加industry和sector字段以支持行业列显示
            base_query = "SELECT symbol as code, name, market, industry, sector, asset_type, updated_at as update_time FROM asset_metadata"
                
            if query_conditions:
                adjusted_conditions = []
                for condition in query_conditions:
                    adjusted_condition = condition.replace('code', 'symbol')
                    adjusted_conditions.append(adjusted_condition)
                query = f"{base_query} WHERE {' AND '.join(adjusted_conditions)}"
            else:
                query = base_query

            # 执行查询（带重连重试）
            max_retries = 3
            last_error = None
            for attempt in range(max_retries):
                try:
                    with duckdb.connect(db_path) as conn:
                        table_check = "SHOW TABLES"
                        tables_result = conn.execute(table_check).fetchall()
                        table_names = [table[0] for table in tables_result]

                        if 'asset_metadata' not in table_names:
                            logger.debug("asset_metadata表不存在，可能尚未导入数据")
                            return pd.DataFrame()

                        if query_params:
                            result = conn.execute(query, query_params).df()
                        else:
                            result = conn.execute(query).df()
                        logger.info(f"从asset_metadata表查询成功，返回 {len(result)} 条记录")
                        return result

                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"DuckDB连接/查询失败 (尝试 {attempt+1}/{max_retries}): {e}")
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        logger.error(f"DuckDB重连失败，已尝试 {max_retries} 次: {last_error}")
                        return pd.DataFrame()

        except ImportError:
            logger.debug("duckdb模块不可用")
            return pd.DataFrame()
        except Exception as e:
            logger.debug(f"直接查询DuckDB失败: {e}")
            return pd.DataFrame()

    def _query_stocks_from_duckdb(self, uni_manager, market: str = None, search_text: str = None) -> pd.DataFrame:
        """
        从DuckDB查询股票数据（已废弃，推荐使用 _direct_query_duckdb_stocks）
        
        注意：此方法存在SQL注入风险（asset_type、market参数使用字符串插值），
        建议使用 _direct_query_duckdb_stocks 方法
        """
        logger.warning("_query_stocks_from_duckdb 方法已废弃，请使用 _direct_query_duckdb_stocks")
        try:
            # 获取DuckDB操作接口 - 尝试多种可能的路径
            duckdb_ops = None

            # 方法1: 直接从uni_manager获取
            if hasattr(uni_manager, 'duckdb_operations') and uni_manager.duckdb_operations:
                duckdb_ops = uni_manager.duckdb_operations

            # 方法2: 从data_manager获取
            elif hasattr(self.data_manager, 'enhanced_duckdb_downloader'):
                downloader = self.data_manager.enhanced_duckdb_downloader
                if hasattr(downloader, 'duckdb_operations'):
                    duckdb_ops = downloader.duckdb_operations

            # 方法3: 尝试从其他路径获取
            elif hasattr(self.data_manager, 'duckdb_operations'):
                duckdb_ops = self.data_manager.duckdb_operations

            if not duckdb_ops:
                logger.debug("无法找到DuckDB操作接口，跳过数据库查询")
                return pd.DataFrame()

            # 构建查询条件
            query_conditions = []

            # 添加资产类型过滤
            current_asset_type = getattr(self, 'current_asset_type', None)
            if current_asset_type:
                query_conditions.append(f"asset_type = '{current_asset_type.value}'")

            if market:
                # 根据市场名称映射到数据库中的market字段
                market_mapping = {
                    "上海": "sh",
                    "深圳": "sz",
                    "创业板": "sz",
                    "科创板": "sh",
                    "北交所": "bj"
                }
                db_market = market_mapping.get(market, market.lower())
                query_conditions.append(f"market = '{db_market}'")

            if search_text:
                safe_search = search_text.replace('%', '\\%').replace('_', '\\_')
                search_condition = "(symbol LIKE '%' || ? || '%' ESCAPE '\\' OR name LIKE '%' || ? || '%' ESCAPE '\\')"
                query_conditions.append(search_condition)

            # 修复：从asset_metadata表查询，字段映射symbol→code
            # 添加industry和sector字段以支持行业列显示
            base_query = "SELECT symbol as code, name, market, industry, sector, asset_type, updated_at as update_time FROM asset_metadata"
            if query_conditions:
                query = f"{base_query} WHERE {' AND '.join(query_conditions)}"
            else:
                query = base_query

            query += " ORDER BY symbol"

            # 执行查询
            if hasattr(duckdb_ops, 'query_data'):
                # 使用 query_data 方法（返回 QueryResult）
                # 注意：调整查询条件中的字段名
                adjusted_where = " AND ".join(query_conditions).replace('code', 'symbol') if query_conditions else None

                # 获取当前资产类型的数据库路径
                current_asset_type = getattr(self, 'current_asset_type', None)
                db_path = self._get_stock_database_path(current_asset_type)

                result = duckdb_ops.query_data(
                    table_name="asset_metadata",
                    database_path=db_path,
                    where_clause=adjusted_where,
                    order_by="symbol"
                )

                # QueryResult 对象有 success 属性和 data 属性
                if result and result.success and result.data is not None:
                    return result.data
                else:
                    logger.debug(f"DuckDB查询返回空结果或失败: {result.error_message if result else 'None'}")
            elif hasattr(duckdb_ops, 'execute_query'):
                # 备用方法：直接执行SQL
                current_asset_type = getattr(self, 'current_asset_type', None)
                db_path = self._get_stock_database_path(current_asset_type)

                result = duckdb_ops.execute_query(
                    database_path=db_path,
                    query=query
                )

                # 处理可能的返回格式
                if isinstance(result, dict):
                    if result.get('success') and result.get('data') is not None:
                        return result['data']
                elif hasattr(result, 'success'):
                    if result.success and result.data is not None:
                        return result.data

            logger.debug("DuckDB查询执行失败或asset_metadata表不存在")
            return pd.DataFrame()

        except Exception as e:
            logger.debug(f"DuckDB查询股票数据失败，使用备用数据源: {e}")
            return pd.DataFrame()

    def _get_stock_database_path(self, asset_type: 'AssetType' = None) -> str:
        """
        获取资产数据库路径（支持资产分离架构）

        Args:
            asset_type: 资产类型，如果为None则使用当前选择的资产类型

        Returns:
            str: 数据库文件路径
        """
        try:
            # 确定使用的资产类型
            if asset_type is None:
                asset_type = getattr(self, 'current_asset_type', None)

            if asset_type is None:
                from core.plugin_types import AssetType
                asset_type = AssetType.STOCK_A  # 默认A股

            # 使用资产分离数据库管理器获取正确的数据库路径
            from core.asset_database_manager import get_asset_separated_database_manager
            asset_db_manager = get_asset_separated_database_manager()
            db_path = asset_db_manager.get_database_path(asset_type)

            logger.debug(f"获取资产数据库路径: {asset_type.value} → {db_path}")
            return db_path

        except Exception as e:
            logger.error(f"获取资产数据库路径失败: {e}，使用默认路径")
            # 降级：使用默认路径
            from pathlib import Path
            asset_type_str = asset_type.value.lower() if asset_type else 'stock_a'
            db_path = Path.cwd() / "cache" / "duckdb" / asset_type_str / f"{asset_type_str}_data.duckdb"
            return str(db_path)

    @pyqtSlot(list)
    def _on_data_loaded(self, stocks: List[Dict[str, Any]]) -> None:
        """数据加载成功后的回调"""
        self.current_stocks = stocks
        self.update_stock_list(stocks)
        self._show_loading(False)
        self.status_label.setText("就绪")

    @pyqtSlot(str)
    def _on_data_error(self, error: str) -> None:
        """数据加载失败后的回调"""
        logger.error(f"Stock data loading error: {error}")
        self.show_message(f"加载股票数据失败: {error}", 'error')
        self._show_loading(False)
        self.status_label.setText("数据加载失败")

    def update_stock_list(self, stocks):
        """
        更新股票列表的公共接口
        """
        self._update_stock_tree(stocks)

    def _debounced_select_stock(self, stock_code: str, stock_name: str, market: str = '') -> None:
        """防抖处理股票选择，避免快速点击时重复触发"""
        if self._selection_timer:
            self._selection_timer.stop()

        self._pending_selection = (stock_code, stock_name, market)
        self._selection_timer = QTimer()
        self._selection_timer.setSingleShot(True)
        self._selection_timer.timeout.connect(self._process_pending_selection)
        self._selection_timer.start(10)  # 10ms防抖

    def _process_pending_selection(self) -> None:
        """处理待处理的选择请求"""
        if self._pending_selection:
            code, name, market = self._pending_selection
            self._select_stock(code, name, market)
            self._pending_selection = None

    def _select_stock(self, stock_code: str, stock_name: str, market: str = '') -> None:
        """
        处理股票选择，启动一个异步任务来验证数据并发布事件
        """
        if not stock_code or not str(stock_code).strip():
            logger.error(f"无效的股票代码: {stock_code}")
            self.show_message(f"'{stock_name}' 股票代码无效。", 'error')
            return

        stock_code = str(stock_code).strip()

        logger.info(f"开始处理股票选择: {stock_code} - {stock_name}")

        self._current_selected_stock = stock_code
        self._current_selected_name = stock_name

        if stock_code in self._no_data_cache:
            self.show_message(f"'{stock_name}' 之前已确认无可用数据。", 'warning')
            return

        self.status_label.setText(f"正在加载 {stock_name} 数据...")
        self._show_loading(True)

        period = ''
        time_range = ''
        if self.coordinator:
            middle_panel = self.coordinator.get_panel('middle')
            if middle_panel:
                period = getattr(middle_panel, '_current_period', '')
                time_range = getattr(middle_panel, '_current_time_range', '')
                logger.info(f"[筛选条件] 从MiddlePanel获取: period={period}, time_range={time_range}")

        asyncio.create_task(self._async_select_stock(
            stock_code, stock_name, market, period, time_range))

    async def _async_select_stock(self, stock_code: str, stock_name: str, market: str, period: str = '', time_range: str = '') -> None:
        """
        异步执行数据请求和后续处理（优化：支持多资产类型）
        """
        try:
            data = await self.data_manager.request_data(
                stock_code=stock_code,
                data_type='kdata',
                asset_type=self.current_asset_type,
                period=period,
                time_range=time_range
            )

            QTimer.singleShot(0, lambda data=data, p=period, tr=time_range: self._handle_data_result(
                data, stock_code, stock_name, market, p, tr))

        except Exception as e:
            logger.error(f"处理资产选择时发生异常: {stock_code} ({self.current_asset_type.value}): {e}", exc_info=True)
            QTimer.singleShot(
                0, lambda e=e: self._handle_data_error(e, stock_name))

    def _handle_data_result(self, data: Optional[Dict[str, Any]], stock_code: str, stock_name: str, market: str, period: str = '', time_range: str = '') -> None:
        """在主线程中处理数据结果"""
        try:
            kline_data = None
            if isinstance(data, dict):
                kline_data = data.get('kline_data')
                logger.debug(f"从字典中获取K线数据: {type(kline_data)}")
            else:
                kline_data = data
                logger.debug(f"直接使用data作为K线数据: {type(kline_data)}")

            is_available = kline_data is not None
            if hasattr(kline_data, 'empty'):
                is_available = is_available and not kline_data.empty

            if is_available:
                logger.info(f"数据加载成功: {stock_code}, 发布StockSelectedEvent（包含K线数据）")

                chart_type = ''
                if self.coordinator:
                    middle_panel = self.coordinator.get_panel('middle')
                    if middle_panel:
                        chart_type = getattr(middle_panel, '_current_chart_type', '')
                        if not period:
                            period = getattr(middle_panel, '_current_period', '')
                        if not time_range:
                            time_range = getattr(middle_panel, '_current_time_range', '')
                        logger.info(f"[筛选条件] 发布事件: period={period}, time_range={time_range}, chart_type={chart_type}")

                event = StockSelectedEvent(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    market=market,
                    kline_data=kline_data,
                    asset_type=self.current_asset_type,
                    period=period,
                    time_range=time_range,
                    chart_type=chart_type
                )
                self.event_bus.publish(event)
                self.status_label.setText(f"已选择: {stock_name}")
                logger.debug(f"事件已发布，K线数据行数: {len(kline_data) if hasattr(kline_data, '__len__') else 'N/A'}")
            else:
                logger.warning(f"数据加载成功但无数据: {stock_code}")
                self.show_message(f"'{stock_name}' 暂无可用K线数据。", "warning")
                self._add_to_no_data_cache(stock_code)
                self.status_label.setText(f"数据加载失败: {stock_name}")

        finally:
            self._show_loading(False)

    def _add_to_no_data_cache(self, stock_code: str) -> None:
        """添加到无数据缓存（有上限控制）"""
        if len(self._no_data_cache) >= self._no_data_cache_max_size:
            # 缓存已满，清空一半（删除最早的）
            cache_list = list(self._no_data_cache)
            self._no_data_cache = set(cache_list[:len(cache_list) // 2])
            logger.debug(f"无数据缓存已满，已清理至 {len(self._no_data_cache)} 条")
        self._no_data_cache.add(stock_code)

    def _cleanup_no_data_cache(self) -> None:
        """清理无数据缓存"""
        if self._no_data_cache:
            original_size = len(self._no_data_cache)
            self._no_data_cache.clear()
            logger.debug(f"无数据缓存已清理，释放 {original_size} 条记录")

    def _handle_data_error(self, error: Exception, stock_name: str) -> None:
        """在主线程中处理错误"""
        self.show_message(f"加载'{stock_name}'数据时出错: {error}", 'error')
        self.status_label.setText("数据加载出错")
        self._show_loading(False)

    def show_message(self, message: str, level: str = 'info') -> None:
        """显示消息提示"""
        msg_box = QMessageBox(self._root_frame)
        try:
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText(message)

                # 根据级别设置样式
                if level == 'error':
                    self.status_label.setStyleSheet("color: red;")
                elif level == 'warning':
                    self.status_label.setStyleSheet("color: orange;")
                else:
                    self.status_label.setStyleSheet("color: green;")

                # 3秒后清除消息
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText("就绪"))
        except Exception as e:
            logger.error(f"Failed to show message: {e}")

    def _add_to_favorites(self, stock_code: str, stock_name: str) -> None:
        """添加到收藏"""
        try:
            self.favorites.add(stock_code)
            if self.stock_service:
                self.stock_service.add_to_favorites(stock_code)

            # 刷新显示
            self._update_stock_tree(self.current_stocks)

            self.show_message(f"已添加 {stock_name} 到收藏", 'info')
            logger.info(f"Added to favorites: {stock_code}")

        except Exception as e:
            logger.error(f"Failed to add to favorites: {e}")
            self.show_message(f"添加收藏失败: {e}", 'error')

    def _remove_from_favorites(self, stock_code: str) -> None:
        """从收藏中移除"""
        try:
            self.favorites.discard(stock_code)
            if self.stock_service:
                self.stock_service.remove_from_favorites(stock_code)

            # 刷新显示
            self._update_stock_tree(self.current_stocks)

            self.show_message(f"已从收藏中移除 {stock_code}", 'info')
            logger.info(f"Removed from favorites: {stock_code}")

        except Exception as e:
            logger.error(f"Failed to remove from favorites: {e}")
            self.show_message(f"移除收藏失败: {e}", 'error')

    def _show_stock_details(self, stock_code: str, stock_name: str) -> None:
        """显示股票详情"""
        try:
            # 简化导入路径
            from gui.dialogs.stock_detail_dialog import StockDetailDialog
            from PyQt5.QtWidgets import QMessageBox

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            # 获取股票详细信息
            stock_info = self.stock_service.get_stock_info(
                stock_code) if self.stock_service else {}
            if not stock_info:
                QMessageBox.warning(main_window, "警告",
                                    f"无法获取股票 {stock_name} 的信息")
                return

            # 获取历史数据
            history_data = None
            if self.stock_service:
                history_data = self.stock_service.get_stock_data(
                    stock_code, period='D', count=20)

            # 准备股票数据
            stock_data = dict(stock_info)
            stock_data['code'] = stock_code
            stock_data['name'] = stock_name

            # 添加历史数据
            if history_data is not None and not history_data.empty:
                history_list = []
                for idx, row in history_data.iterrows():
                    history_list.append({
                        'date': str(idx.date()) if hasattr(idx, 'date') else str(idx),
                        'open': float(row.get('open', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'close': float(row.get('close', 0)),
                        'volume': float(row.get('volume', 0))
                    })
                stock_data['history'] = history_list

            # 显示详情对话框
            dialog = StockDetailDialog(stock_data, main_window)
            dialog.exec_()

            logger.info(f"查看股票详情: {stock_name} ({stock_code})")

        except Exception as e:
            logger.error(f"显示股票详情失败: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(main_window, "错误", f"显示股票详情失败: {e}")

    def _show_loading(self, show: bool) -> None:
        """显示/隐藏加载状态"""
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setRange(0, 0)  # 不确定进度
            self.status_label.setText("加载中...")
        else:
            self.progress_bar.setVisible(False)

    def _apply_theme_to_widgets(self, theme: Dict[str, Any]) -> None:
        """应用主题到组件"""
        super()._apply_theme_to_widgets(theme)

        try:
            colors = theme.get('colors', {})

            # 应用到搜索输入框
            if self.search_input:
                self.search_input.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {colors.get('input_bg', '#ffffff')};
                        border: 1px solid {colors.get('border', '#cccccc')};
                        padding: 5px;
                        border-radius: 3px;
                    }}
                """)

            # 应用到股票列表
            if self.stock_tree:
                self.stock_tree.setStyleSheet(f"""
                    QTreeWidget {{
                        background-color: {colors.get('list_bg', '#ffffff')};
                        alternate-background-color: {colors.get('list_alt_bg', '#f5f5f5')};
                        border: 1px solid {colors.get('border', '#cccccc')};
                    }}
                    QTreeWidget::item:selected {{
                        background-color: {colors.get('selection_bg', '#0078d4')};
                        color: {colors.get('selection_fg', '#ffffff')};
                    }}
                """)

        except Exception as e:
            logger.debug(f"Failed to apply theme to LeftPanel widgets: {e}")

    def resizeEvent(self, event):
        """窗口大小改变事件处理"""
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self):
        """更新响应式布局"""
        try:
            window_width = self.width()
            window_height = self.height()

            logger.debug(f"LeftPanel 响应式布局更新: {window_width}x{window_height}")

            # 更新进度条高度
            if hasattr(self, 'progress_bar') and self.progress_bar:
                progress_height = max(8, int(window_height * 0.015))
                self.progress_bar.setFixedHeight(progress_height)

            # 更新按钮宽度（基于窗口宽度的百分比）
            button_width = max(60, int(window_width * 0.15))

            # 更新搜索按钮
            search_btn = self.findChild(QPushButton, "search_btn")
            if search_btn:
                search_btn.setFixedWidth(button_width)

            # 更新高级搜索按钮
            advanced_search_btn = self.findChild(QPushButton, "advanced_search_btn")
            if advanced_search_btn:
                advanced_search_btn.setFixedWidth(int(button_width * 1.3))

            # 更新收藏按钮
            if hasattr(self, 'favorites_btn') and self.favorites_btn:
                self.favorites_btn.setFixedWidth(button_width)

            # 更新刷新按钮
            refresh_btn = self.findChild(QPushButton, "refresh_btn")
            if refresh_btn:
                refresh_btn.setFixedWidth(button_width)

            # 更新市场选择框
            if hasattr(self, 'market_combo') and self.market_combo:
                self.market_combo.setFixedWidth(int(button_width * 1.3))

            # 更新指标类型选择框
            if hasattr(self, 'indicator_type_combo') and self.indicator_type_combo:
                self.indicator_type_combo.setFixedWidth(int(button_width * 1.3))

        except Exception as e:
            logger.error(f"更新响应式布局失败: {e}")

    def _do_dispose(self) -> None:
        """释放资源"""
        try:
            # 停止数据加载线程
            # The data_manager handles its own thread management
            # self.data_loader.quit()

            # 停止定时器
            if hasattr(self, 'search_timer') and self.search_timer:
                self.search_timer.stop()

            if hasattr(self, '_selection_timer') and self._selection_timer:
                self._selection_timer.stop()

            if hasattr(self, '_cache_cleanup_timer') and self._cache_cleanup_timer:
                self._cache_cleanup_timer.stop()

            # 清理缓存
            if hasattr(self, '_no_data_cache') and self._no_data_cache:
                self._no_data_cache.clear()

            if self.event_bus:
                try:
                    from core.events.types import MultiScreenToggleEvent
                    self.event_bus.unsubscribe(MultiScreenToggleEvent, self.on_multi_screen_toggled)
                    self.event_bus.unsubscribe(AssetTypeChangedEvent, self._on_own_asset_type_changed)
                except Exception as e:
                    logger.warning(f"取消事件订阅失败: {e}")

            super()._do_dispose()

            logger.info("Left panel disposed")

        except Exception as e:
            logger.error(f"Error disposing LeftPanel resources: {e}")

    # 事件处理方法
    def on_stock_selected(self, event) -> None:
        """处理股票选择事件"""
        # 更新股票列表鼠标指针样式
        self._update_stock_list_cursor()

    def on_data_update(self, event) -> None:
        """处理数据更新事件"""
        # 刷新股票数据
        self._load_stock_data()

    def on_theme_changed(self, event) -> None:
        """处理主题变化事件"""
        if hasattr(event, 'theme'):
            self.apply_theme(event.theme)

    def _check_data_quality(self, stock_code: str, stock_name: str) -> None:
        """数据质量检查"""
        try:
            # 简化导入路径
            from gui.dialogs.data_quality_dialog import DataQualityDialog

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            # 创建数据质量检查对话框
            dialog = DataQualityDialog(main_window, stock_code=stock_code)

            # 居中显示
            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info(f"Opened data quality check for stock: {stock_code}")

        except Exception as e:
            logger.error(f"Failed to open data quality check: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(
                main_window, "错误",
                f"打开数据质量检查失败: {str(e)}"
            )

    def _show_calculator(self) -> None:
        """显示计算器"""
        try:
            # 简化导入路径
            from gui.dialogs.calculator_dialog import CalculatorDialog

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            # 创建计算器对话框
            dialog = CalculatorDialog(main_window)

            # 居中显示
            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info("Opened calculator")

        except Exception as e:
            logger.error(f"Failed to open calculator: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(
                main_window, "错误",
                f"打开计算器失败: {str(e)}"
            )

    def _show_converter(self) -> None:
        """显示单位转换器"""
        try:
            # 简化导入路径
            from gui.dialogs.converter_dialog import ConverterDialog

            # 获取主窗口作为父窗口
            main_window = self.coordinator.get_main_window() if self.coordinator else None

            # 创建单位转换器对话框
            dialog = ConverterDialog(main_window)

            # 居中显示
            if self.coordinator:
                self.coordinator.center_dialog(dialog, main_window)

            dialog.exec_()

            logger.info("Opened unit converter")

        except Exception as e:
            logger.error(f"Failed to open unit converter: {e}")
            from PyQt5.QtWidgets import QMessageBox
            main_window = self.coordinator.get_main_window() if self.coordinator else None
            QMessageBox.critical(
                main_window, "错误",
                f"打开单位转换器失败: {str(e)}"
            )

    def _create_indicator_section(self, parent_layout: QVBoxLayout) -> None:
        """创建指标列表区域"""
        try:
            # 创建指标组
            indicator_group = QGroupBox("技术指标")
            indicator_layout = QVBoxLayout(indicator_group)
            indicator_layout.setContentsMargins(5, 5, 5, 5)
            indicator_layout.setSpacing(2)

            # 创建指标筛选控件
            self._create_indicator_filters(indicator_layout)

            # 创建指标列表
            self._create_indicator_list(indicator_layout)

            # 创建指标操作按钮
            self._create_indicator_buttons(indicator_layout)

            # 添加到主布局
            parent_layout.addWidget(indicator_group)

            # 初始化指标数据
            self._initialize_indicators()

        except Exception as e:
            logger.error(f"Failed to create indicator section: {e}")

    def _create_indicator_filters(self, parent_layout: QVBoxLayout) -> None:
        """创建指标筛选控件"""
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)

        # 指标类型筛选
        type_label = QLabel("类型:")
        type_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.indicator_type_combo = QComboBox()
        self.indicator_type_combo.addItems(
            ["全部", "趋势类", "震荡类", "成交量类", "ta-lib"])
        self.indicator_type_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 指标搜索
        self.indicator_search = QLineEdit()
        self.indicator_search.setPlaceholderText("搜索指标...")
        self.indicator_search.setClearButtonEnabled(True)

        filter_layout.addWidget(type_label)
        filter_layout.addWidget(self.indicator_type_combo)
        filter_layout.addWidget(self.indicator_search)

        parent_layout.addWidget(filter_frame)

        # 保存组件引用
        self.add_widget('indicator_type_combo', self.indicator_type_combo)
        self.add_widget('indicator_search', self.indicator_search)

    def _create_indicator_list(self, parent_layout: QVBoxLayout) -> None:
        """创建指标列表（多行6列网格布局）"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 创建指标表格（6列网格布局）
        self.indicator_list = QTableWidget()
        self.indicator_list.setColumnCount(6)
        self.indicator_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.indicator_list.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.indicator_list.setShowGrid(True)
        self.indicator_list.setGridStyle(Qt.SolidLine)
        self.indicator_list.verticalHeader().setVisible(False)
        self.indicator_list.horizontalHeader().setVisible(False)
        self.indicator_list.setFocusPolicy(Qt.NoFocus)
        
        # 设置行高和列宽
        self.indicator_list.verticalHeader().setDefaultSectionSize(28)
        for col in range(6):
            self.indicator_list.setColumnWidth(col, 70)
        
        # 设置边框样式
        # self.indicator_list.setStyleSheet("""
        #     QTableWidget {
        #         border: 1px solid #888888;
        #         gridline-color: #CCCCCC;
        #         background-color: #FFFFFF;
        #     }
        #     QTableWidget::item {
        #         padding: 2px;
        #         border: 1px solid #DDDDDD;
        #     }
        #     QTableWidget::item:selected {
        #         background-color: #4A90D9;
        #         color: white;
        #     }
        #     QTableWidget::item:hover {
        #         background-color: #E8F4FC;
        #     }
        # """)
        
        scroll_area.setWidget(self.indicator_list)

        parent_layout.addWidget(scroll_area)

        # 保存组件引用
        self.add_widget('indicator_list', self.indicator_list)

    def _create_indicator_buttons(self, parent_layout: QVBoxLayout) -> None:
        """创建指标操作按钮"""
        # 第一行按钮
        buttons_layout1 = QHBoxLayout()
        buttons_layout1.setSpacing(1)

        manage_btn = QPushButton("管理指标")
        manage_btn.clicked.connect(self._show_indicator_params_dialog)

        save_combo_btn = QPushButton("保存组合")
        save_combo_btn.clicked.connect(self._save_indicator_combination)

        load_combo_btn = QPushButton("加载组合")
        load_combo_btn.clicked.connect(self._load_indicator_combination_dialog)

        buttons_layout1.addWidget(manage_btn)
        buttons_layout1.addWidget(save_combo_btn)
        buttons_layout1.addWidget(load_combo_btn)

        # 第二行按钮
        buttons_layout2 = QHBoxLayout()
        buttons_layout2.setSpacing(1)

        delete_combo_btn = QPushButton("删除组合")
        delete_combo_btn.clicked.connect(
            self._delete_indicator_combination_dialog)

        clear_btn = QPushButton("取消指标")
        clear_btn.clicked.connect(self._clear_all_selected_indicators)

        buttons_layout2.addWidget(delete_combo_btn)
        buttons_layout2.addWidget(clear_btn)

        parent_layout.addLayout(buttons_layout1)
        parent_layout.addLayout(buttons_layout2)

        # 保存组件引用
        self.add_widget('manage_indicator_btn', manage_btn)
        self.add_widget('save_combination_btn', save_combo_btn)
        self.add_widget('load_combination_btn', load_combo_btn)
        self.add_widget('delete_combination_btn', delete_combo_btn)
        self.add_widget('clear_indicators_btn', clear_btn)

    def _initialize_indicators(self) -> None:
        """初始化指标数据"""
        try:
            # 内置指标（R282: 判组唯一来源 BUILTIN_INDICATORS，与 middle_panel 口径一致；
            # CCI/OBV 原在此列为内置，现移出由下方 TA-Lib 动态列表提供 → 统一走 talib 组直算）
            _builtin_types = [
                ('MA', '趋势类'), ('MACD', '趋势类'), ('BOLL', '趋势类'),
                ('RSI', '震荡类'), ('KDJ', '震荡类'),
            ]
            self.builtin_indicators = [
                {"name": name, "type": ind_type}
                for name, ind_type in _builtin_types
                if name in BUILTIN_INDICATORS
            ]

            # 尝试获取ta-lib指标
            try:
                from core.indicators.indicators_algorithm import get_talib_real_indicator_list
                talib_names = get_talib_real_indicator_list()
                self.talib_indicators = [
                    {"name": name, "type": "ta-lib"} for name in talib_names]
            except ImportError:
                logger.warning(
                    "indicators_algo module not found, using default ta-lib indicators")
                self.talib_indicators = [
                    {"name": "SMA", "type": "ta-lib"},
                    {"name": "EMA", "type": "ta-lib"},
                    {"name": "STOCH", "type": "ta-lib"},
                    {"name": "ADX", "type": "ta-lib"},
                ]

            # 自定义指标（预留）
            self.custom_indicators = []

            # 合并所有指标（按名称去重，内置优先：内置与 ta-lib 列表存在 MA/MACD/RSI/CCI 重复）
            seen_names = set()
            merged_indicators = []
            for ind in self.builtin_indicators + self.talib_indicators + self.custom_indicators:
                if ind["name"] not in seen_names:
                    seen_names.add(ind["name"])
                    merged_indicators.append(ind)
            self.all_indicators = merged_indicators

            # 填充指标列表
            self._populate_indicator_list()

            # 绑定指标相关事件
            self._bind_indicator_events()

            logger.debug(f"Initialized {len(self.all_indicators)} indicators")

        except Exception as e:
            logger.error(f"Failed to initialize indicators: {e}")

    def _populate_indicator_list(self) -> None:
        """填充指标列表（多行6列网格布局）"""
        try:
            self.indicator_list.setRowCount(0)
            self.indicator_list.clear()

            # 计算需要的行数（每行6列）
            cols = 6
            total = len(self.all_indicators)
            rows = (total + cols - 1) // cols  # 向上取整

            self.indicator_list.setRowCount(rows)

            for idx, ind in enumerate(self.all_indicators):
                row = idx // cols
                col = idx % cols

                item = QTableWidgetItem(ind["name"])
                item.setData(Qt.UserRole, ind["type"])
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                # R282: 中文名 tooltip（KAMA/MAMA/TEMA 等不再裸英文，悬停可见中文含义）
                try:
                    from core.indicator_adapter import get_talib_chinese_name
                    item.setToolTip(get_talib_chinese_name(ind["name"]))
                except Exception:
                    item.setToolTip(ind["name"])
                self.indicator_list.setItem(row, col, item)

                # 默认选中MA指标
                if ind["name"] == "MA":
                    item.setSelected(True)

        except Exception as e:
            logger.error(f"Failed to populate indicator list: {e}")

    def _bind_indicator_events(self) -> None:
        """绑定指标相关事件"""
        try:
            # 指标类型筛选事件
            self.indicator_type_combo.currentTextChanged.connect(
                self._on_indicator_type_changed)

            # 指标搜索事件
            self.indicator_search.textChanged.connect(
                self._on_indicator_search_changed)

            # 指标选择事件
            self.indicator_list.itemSelectionChanged.connect(
                self._on_indicators_changed)

        except Exception as e:
            logger.error(f"Failed to bind indicator events: {e}")

    @pyqtSlot(str)
    def _on_indicator_type_changed(self, indicator_type: str) -> None:
        """处理指标类型变化"""
        try:
            self._filter_indicator_list(self.indicator_search.text())
        except Exception as e:
            logger.error(f"Failed to handle indicator type change: {e}")

    @pyqtSlot(str)
    def _on_indicator_search_changed(self, text: str) -> None:
        """处理指标搜索变化"""
        try:
            self._filter_indicator_list(text)
        except Exception as e:
            logger.error(f"Failed to handle indicator search change: {e}")

    def _filter_indicator_list(self, search_text: str = "") -> None:
        """过滤指标列表（表格布局版本）"""
        try:
            indicator_type = self.indicator_type_combo.currentText()

            visible_count = 0
            for row in range(self.indicator_list.rowCount()):
                for col in range(self.indicator_list.columnCount()):
                    item = self.indicator_list.item(row, col)
                    if not item:
                        continue
                    
                    indicator_name = item.text()
                    if not indicator_name:
                        continue
                        
                    ind_type = item.data(Qt.UserRole)

                    type_match = (indicator_type == "全部" or ind_type == indicator_type)
                    text_match = (not search_text or search_text.lower() in indicator_name.lower())

                    should_show = type_match and text_match
                    item.setHidden(not should_show)

                    if should_show:
                        visible_count += 1

            logger.debug(
                f"Filtered indicators: type={indicator_type}, search={search_text}, visible={visible_count}")

        except Exception as e:
            logger.error(f"Failed to filter indicator list: {e}")

    @pyqtSlot()
    def _on_indicators_changed(self) -> None:
        """处理指标选择变化"""
        try:
            selected_items = self.indicator_list.selectedItems()
            selected_indicators = [
                item.text() for item in selected_items if item.text() and item.text() != "无可用指标"]

            logger.debug(f"Selected indicators changed: {selected_indicators}")

            # 确保至少选择了一个指标
            if not selected_indicators:
                logger.warning("没有选择任何指标，使用默认指标 MA")
                selected_indicators = ["MA"]
                # 自动选择MA指标
                for row in range(self.indicator_list.rowCount()):
                    for col in range(self.indicator_list.columnCount()):
                        item = self.indicator_list.item(row, col)
                        if item and item.text() == "MA":
                            item.setSelected(True)
                            break

            # 触发指标更新事件
            if self.coordinator and self.coordinator.event_bus:
                from core.events import IndicatorChangedEvent
                logger.info(f"发布指标变化事件，选中指标: {selected_indicators}")
                # 创建事件并确保selected_indicators属性正确设置
                event = IndicatorChangedEvent(
                    selected_indicators=selected_indicators)
                # 同时确保data字典中也包含selected_indicators
                event.data['selected_indicators'] = selected_indicators
                # 发布事件
                self.coordinator.event_bus.publish(event)
                logger.debug(f"指标变化事件已发布: {event.selected_indicators}")
            else:
                logger.warning("无法发布指标变化事件：协调器或事件总线不可用")

        except Exception as e:
            logger.error(
                f"Failed to handle indicators change: {e}", exc_info=True)

    def _show_indicator_params_dialog(self):
        """显示指标参数设置对话框"""
        try:
            selected_indicators = self.get_selected_indicators()
            if not selected_indicators:
                QMessageBox.warning(
                    self._root_frame,  # 使用_root_frame作为父窗口，而不是self.window()
                    "提示",
                    "请先选择要设置参数的指标"
                )
                return

            # 导入对话框类
            try:
                from gui.dialogs.indicator_params_dialog import IndicatorParamsDialog
            except ImportError as e:
                logger.error(f"导入指标参数对话框失败: {e}")
                QMessageBox.warning(
                    self._root_frame,  # 使用_root_frame作为父窗口
                    "功能暂未实现",
                    "指标参数管理功能正在开发中，敬请期待！"
                )
                return

            # 创建对话框实例
            try:
                # 使用self._root_frame作为父窗口，而不是self.window()
                dialog = IndicatorParamsDialog(
                    selected_indicators, self._root_frame)
                logger.debug(f"创建指标参数对话框成功，选中指标: {selected_indicators}")
            except Exception as e:
                logger.error(f"创建指标参数对话框失败: {e}")
                QMessageBox.critical(
                    self._root_frame,  # 使用_root_frame作为父窗口
                    "错误",
                    f"创建指标参数对话框失败: {e}"
                )
                return

            # 连接参数变化信号
            try:
                dialog.params_changed.connect(
                    self._on_indicator_params_changed)
                # 显示对话框
                dialog.exec_()
            except Exception as e:
                logger.error(f"显示指标参数对话框失败: {e}")
                QMessageBox.critical(
                    self._root_frame,  # 使用_root_frame作为父窗口
                    "错误",
                    f"显示指标参数对话框失败: {e}"
                )

        except Exception as e:
            logger.error(f"显示指标参数对话框失败: {e}", exc_info=True)

    def _save_indicator_combination(self) -> None:
        """保存指标组合"""
        try:
            selected_items = self.indicator_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(self._root_frame, "提示", "请先选择要保存的指标")
                return

            name, ok = QInputDialog.getText(
                self._root_frame,
                "保存指标组合",
                "请输入组合名称:",
                QLineEdit.Normal,
                ""
            )

            if not ok or not name:
                return

            # 获取组合描述
            description, ok = QInputDialog.getText(
                self._root_frame,
                "保存指标组合",
                "请输入组合描述（可选）:",
                QLineEdit.Normal,
                ""
            )

            if not ok:
                description = ""

            # 构建指标数据
            indicators = []
            for item in selected_items:
                if item.text() != "无可用指标":
                    indicators.append({
                        "name": item.text(),
                        "type": item.data(Qt.UserRole),
                        "params": {}  # 这里可以扩展参数保存
                    })

            # 保存到指标组合管理器
            from core.indicator_combination_manager import get_combination_manager
            manager = get_combination_manager()

            success = manager.save_combination(
                name=name,
                indicators=indicators,
                description=description,
                tags=["用户自定义"]
            )

            if success:
                QMessageBox.information(
                    self._root_frame, "成功", f"指标组合 '{name}' 保存成功！")
                logger.info(
                    f"Saved indicator combination: {name} with {len(indicators)} indicators")
            else:
                QMessageBox.critical(self._root_frame, "错误", "保存指标组合失败")
                logger.error(f"Failed to save indicator combination: {name}")

        except Exception as e:
            QMessageBox.critical(self._root_frame, "错误",
                                 f"保存指标组合失败:\n{str(e)}")
            logger.error(f"Failed to save indicator combination: {e}")

    def _load_indicator_combination_dialog(self) -> None:
        """加载指标组合对话框"""
        try:
            from gui.dialogs.indicator_combination_dialog import IndicatorCombinationDialog
            dialog = IndicatorCombinationDialog(self._root_frame)

            def on_combination_selected(name, indicators):
                """处理组合选择"""
                try:
                    # 清除当前选择
                    self.indicator_list.clearSelection()

                    # 选择组合中的指标
                    for indicator in indicators:
                        indicator_name = indicator.get('name', '')
                        if indicator_name:
                            for row in range(self.indicator_list.rowCount()):
                                for col in range(self.indicator_list.columnCount()):
                                    item = self.indicator_list.item(row, col)
                                    if item and item.text() == indicator_name:
                                        item.setSelected(True)
                                        break

                    logger.info(f"Loaded indicator combination: {name}")

                    # 手动触发指标选择变化事件，刷新中间面板
                    self._on_indicators_changed()

                except Exception as e:
                    logger.error(f"Failed to apply combination selection: {e}")
                    QMessageBox.critical(
                        self._root_frame,
                        "错误",
                        f"应用组合选择失败:\n{str(e)}"
                    )

            dialog.combination_selected.connect(on_combination_selected)
            dialog.exec_()

        except ImportError:
            QMessageBox.warning(
                self._root_frame,
                "功能暂未实现",
                "指标组合加载功能正在开发中，敬请期待！"
            )
        except Exception as e:
            QMessageBox.critical(
                self._root_frame,
                "错误",
                f"加载指标组合失败:\n{str(e)}"
            )

    def _delete_indicator_combination_dialog(self) -> None:
        """删除指标组合对话框"""
        try:
            # 尝试获取指标组合管理器
            from core.indicator_combination_manager import get_combination_manager
            manager = get_combination_manager()

            # 获取所有组合
            combinations = manager.get_all_combinations()
            if not combinations:
                QMessageBox.information(
                    self._root_frame,
                    "提示",
                    "没有可删除的指标组合"
                )
                return

            # 使用对话框选择要删除的组合
            from PyQt5.QtWidgets import QInputDialog
            combination_names = list(combinations.keys())
            name, ok = QInputDialog.getItem(
                self._root_frame,
                "删除指标组合",
                "请选择要删除的组合:",
                combination_names,
                0,
                False
            )

            if not ok or not name:
                return

            # 确认删除
            reply = QMessageBox.question(
                self._root_frame,
                "确认删除",
                f"确定要删除指标组合 '{name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 从管理器中删除
                success = manager.delete_combination(name)
                if success:
                    QMessageBox.information(
                        self._root_frame,
                        "成功",
                        f"指标组合 '{name}' 已删除"
                    )
                    logger.info(f"Deleted indicator combination: {name}")
                else:
                    QMessageBox.critical(
                        self._root_frame,
                        "错误",
                        f"删除指标组合 '{name}' 失败"
                    )

        except Exception as e:
            logger.error(f"删除指标组合失败: {e}", exc_info=True)
            QMessageBox.critical(
                self._root_frame,
                "错误",
                f"删除指标组合失败: {e}"
            )

    def _clear_all_selected_indicators(self) -> None:
        """清除所有选中的指标"""
        try:
            self.indicator_list.clearSelection()
            logger.debug("Cleared all selected indicators")

        except Exception as e:
            logger.error(f"Failed to clear selected indicators: {e}")

    def get_selected_indicators(self) -> List[str]:
        """获取当前选中的指标列表"""
        try:
            selected_items = self.indicator_list.selectedItems()
            return [item.text() for item in selected_items if item.text() and item.text() != "无可用指标"]
        except Exception as e:
            logger.error(f"Failed to get selected indicators: {e}")
            return []

    def _on_indicator_params_changed(self, params):
        """处理指标参数变化事件"""
        try:
            selected_indicators = self.get_selected_indicators()
            logger.info(f"指标参数已更新: {params}")

            # R245 修复: 原发布 ChartUpdateEvent 并硬塞 data['indicator_params']（该事件无此字段，
            # event_coordinator._on_chart_updated 只打日志）→ 改用 IndicatorChangedEvent（types.py L618-633
            # 自带 indicator_params 字段），由 middle_panel.on_indicator_changed 消费合并用户参数
            # R282: 补齐 coordinator.event_bus 判空（原仅判 coordinator，event_bus 为 None 时静默丢失）
            if self.coordinator and self.coordinator.event_bus:
                from core.events import IndicatorChangedEvent
                event = IndicatorChangedEvent(
                    selected_indicators=selected_indicators,
                    indicator_params=params
                )
                self.coordinator.event_bus.publish(event)
            else:
                logger.warning("无法发布指标参数事件：协调器或事件总线不可用")

        except Exception as e:
            logger.error(f"处理指标参数变化失败: {e}", exc_info=True)

    def _update_stock_list_cursor(self) -> None:
        """
        根据当前模式更新股票列表的鼠标指针样式
        """
        try:
            if self._is_multi_screen_mode():
                # 多屏模式下使用拖拽指针
                self.stock_tree.setCursor(Qt.OpenHandCursor)
                self.show_message("多屏模式：请拖拽股票到目标图表", level="info")
            else:
                # 单屏模式下使用默认指针
                self.stock_tree.setCursor(Qt.ArrowCursor)
        except Exception as e:
            logger.error(f"更新股票列表鼠标指针失败: {e}")

    def on_multi_screen_toggled(self, event=None) -> None:
        """
        处理多屏模式切换事件

        Args:
            event: 多屏模式切换事件对象，如果为None则通过_is_multi_screen_mode方法检测
        """
        try:
            # 如果提供了事件对象，从事件中获取多屏模式状态
            if event and hasattr(event, 'is_multi_screen'):
                is_multi_screen = event.is_multi_screen
            else:
                # 否则通过方法检测
                is_multi_screen = self._is_multi_screen_mode()

            logger.info(f"多屏模式切换: {'开启' if is_multi_screen else '关闭'}")

            # 更新股票列表鼠标指针样式
            self._update_stock_list_cursor()

        except Exception as e:
            logger.error(f"处理多屏模式切换事件失败: {e}")

    def _update_status(self, message: str) -> None:
        """更新状态栏信息"""
        try:
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText(message)
            logger.info(f"LeftPanel状态更新: {message}")
        except Exception as e:
            logger.error(f"更新状态失败: {e}")
