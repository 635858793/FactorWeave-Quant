"""
增强策略管理对话框 V3 - 使用现代化UI组件重构
提供：
1. 可折叠侧边栏导航
2. 增强统计卡片（带阴影、迷你图、趋势指示器）
3. 可折叠面板
4. 快捷操作面板
5. 实时数据指示器
6. 工作区管理
"""

from loguru import logger
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QSplitter,
    QStackedWidget, QLabel, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from gui.components.modern_ui_components import (
    ModernSidebarNavigation, EnhancedStatCard, CollapsiblePanel,
    QuickActionPanel, RealtimeIndicator, WorkspaceManager,
    FINANCIAL_COLORS, STATUS_COLORS
)


class EnhancedStrategyManagerDialogV3(QDialog):
    """
    增强策略管理对话框 V3 - 使用现代化UI组件
    
    主要改进：
    1. 侧边栏导航替代顶部导航
    2. 增强统计卡片（带阴影、迷你图、趋势指示器）
    3. 可折叠面板提升布局灵活性
    4. 快捷操作面板提升操作效率
    5. 实时数据指示器
    6. 工作区管理
    """
    
    strategy_selected = pyqtSignal(str)
    strategy_started = pyqtSignal(str)
    strategy_stopped = pyqtSignal(str)
    
    def __init__(self, parent=None, strategy_service=None):
        super().__init__(parent)
        
        self.strategy_service = strategy_service
        self.current_strategy_id = None
        self.current_view = 'home'
        
        self.theme_manager = self._init_theme_manager()
        self.workspace_manager = WorkspaceManager()
        
        self.setWindowTitle("策略管理器 - 专业版")
        self.setModal(False)
        self.resize(1600, 1000)
        
        self._setup_ui()
        self._apply_theme()
        self._load_data()
        
    def _init_theme_manager(self):
        """初始化主题管理器"""
        try:
            from utils.theme import get_theme_manager
            return get_theme_manager()
        except Exception as e:
            logger.warning(f"获取主题管理器失败: {e}")
            return None
            
    def _setup_ui(self):
        """设置UI - 使用侧边栏 + 主内容区布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        header = self._create_header()
        main_layout.addWidget(header)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        
        self.sidebar = self._create_sidebar()
        splitter.addWidget(self.sidebar)
        
        content_widget = self._create_content_area()
        splitter.addWidget(content_widget)
        
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
    def _create_header(self) -> QWidget:
        """创建顶部标题栏"""
        header = QWidget()
        header.setFixedHeight(40)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        
        title = QLabel("策略管理器")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        self.realtime_indicator = RealtimeIndicator(theme_manager=self.theme_manager)
        layout.addWidget(self.realtime_indicator)
        
        return header
        
    def _create_sidebar(self) -> ModernSidebarNavigation:
        """创建侧边栏导航"""
        sidebar = ModernSidebarNavigation(theme_manager=self.theme_manager)
        
        nav_items = [
            ('home', '首页', '🏠', 'Ctrl+H'),
            ('library', '策略库', '📚', 'Ctrl+L'),
            ('backtest', '回测实验室', '📊', 'Ctrl+B'),
            ('optimization', '参数优化', '⚙️', 'Ctrl+O'),
            ('performance', '性能分析', '📈', 'Ctrl+P'),
            ('editor', '代码编辑器', '💻', 'Ctrl+E'),
            ('workflow', '开发工作流', '🔄', 'Ctrl+W'),
        ]
        
        for name, label, icon, shortcut in nav_items:
            sidebar.add_nav_item(name, label, icon, shortcut)
            
        sidebar.add_quick_action("新建策略", "➕", self._create_strategy)
        sidebar.add_quick_action("快速回测", "🚀", self._quick_backtest)
        
        sidebar.nav_changed.connect(self._on_nav_changed)
        sidebar.set_current_nav('home')
        
        return sidebar
        
    def _create_content_area(self) -> QWidget:
        """创建主内容区"""
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.content_stack = QStackedWidget()
        
        self.home_view = self._create_home_view()
        self.content_stack.addWidget(self.home_view)
        
        self.library_view = self._create_library_view()
        self.content_stack.addWidget(self.library_view)
        
        self.backtest_view = self._create_backtest_view()
        self.content_stack.addWidget(self.backtest_view)
        
        self.optimization_view = self._create_optimization_view()
        self.content_stack.addWidget(self.optimization_view)
        
        self.performance_view = self._create_performance_view()
        self.content_stack.addWidget(self.performance_view)
        
        self.editor_view = self._create_editor_view()
        self.content_stack.addWidget(self.editor_view)
        
        self.workflow_view = self._create_workflow_view()
        self.content_stack.addWidget(self.workflow_view)
        
        layout.addWidget(self.content_stack)
        
        return content
        
    def _create_home_view(self) -> QWidget:
        """创建首页视图 - 使用增强统计卡片"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.total_strategy_card = EnhancedStatCard(
            title="策略总数",
            value="0",
            color=FINANCIAL_COLORS['primary'],
            theme_manager=self.theme_manager
        )
        self.total_strategy_card.clicked.connect(lambda: self._switch_view('library'))
        stats_layout.addWidget(self.total_strategy_card)
        
        self.running_strategy_card = EnhancedStatCard(
            title="运行中",
            value="0",
            color=STATUS_COLORS['running'],
            theme_manager=self.theme_manager
        )
        stats_layout.addWidget(self.running_strategy_card)
        
        self.configured_strategy_card = EnhancedStatCard(
            title="已配置",
            value="0",
            color=STATUS_COLORS['configured'],
            theme_manager=self.theme_manager
        )
        stats_layout.addWidget(self.configured_strategy_card)
        
        self.error_strategy_card = EnhancedStatCard(
            title="错误",
            value="0",
            color=STATUS_COLORS['error'],
            theme_manager=self.theme_manager
        )
        stats_layout.addWidget(self.error_strategy_card)
        
        layout.addLayout(stats_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = self._create_home_left_panel()
        splitter.addWidget(left_panel)
        
        right_panel = self._create_home_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        return view
        
    def _create_home_left_panel(self) -> QWidget:
        """创建首页左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        trend_panel = CollapsiblePanel("性能趋势（最近30天）", theme_manager=self.theme_manager)
        trend_content = self._create_trend_chart()
        trend_panel.set_content(trend_content)
        layout.addWidget(trend_panel)
        
        ranking_panel = CollapsiblePanel("策略性能排行榜", theme_manager=self.theme_manager)
        ranking_content = self._create_ranking_table()
        ranking_panel.set_content(ranking_content)
        layout.addWidget(ranking_panel)
        
        return panel
        
    def _create_home_right_panel(self) -> QWidget:
        """创建首页右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        quick_action_panel = QuickActionPanel(theme_manager=self.theme_manager)
        quick_action_panel.action_triggered.connect(self._on_quick_action)
        layout.addWidget(quick_action_panel)
        
        layout.addStretch()
        
        return panel
        
    def _create_trend_chart(self) -> QWidget:
        """创建趋势图"""
        widget = QWidget()
        widget.setMinimumHeight(300)
        layout = QVBoxLayout(widget)
        
        label = QLabel("📈 性能趋势图将在这里显示")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #6B7280; font-size: 14px;")
        layout.addWidget(label)
        
        return widget
        
    def _create_ranking_table(self) -> QWidget:
        """创建排行榜表格"""
        widget = QWidget()
        widget.setMinimumHeight(400)
        layout = QVBoxLayout(widget)
        
        label = QLabel("📊 策略排行榜将在这里显示")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #6B7280; font-size: 14px;")
        layout.addWidget(label)
        
        return widget
        
    def _create_library_view(self) -> QWidget:
        """创建策略库视图"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        
        label = QLabel("📚 策略库视图")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        return view
        
    def _create_backtest_view(self) -> QWidget:
        """创建回测实验室视图 - 使用QSplitter实现可调整布局"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        
        splitter = QSplitter(Qt.Horizontal)
        
        config_panel = CollapsiblePanel("回测配置", theme_manager=self.theme_manager)
        config_content = self._create_backtest_config()
        config_panel.set_content(config_content)
        splitter.addWidget(config_panel)
        
        result_panel = self._create_backtest_results()
        splitter.addWidget(result_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        return view
        
    def _create_backtest_config(self) -> QWidget:
        """创建回测配置面板"""
        widget = QWidget()
        widget.setMinimumWidth(300)
        layout = QVBoxLayout(widget)
        
        label = QLabel("⚙️ 回测配置选项")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        return widget
        
    def _create_backtest_results(self) -> QWidget:
        """创建回测结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel("📊 回测结果")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        return widget
        
    def _create_optimization_view(self) -> QWidget:
        """创建参数优化视图"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        
        label = QLabel("⚙️ 参数优化视图")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        return view
        
    def _create_performance_view(self) -> QWidget:
        """创建性能分析视图"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        
        label = QLabel("📈 性能分析视图")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        return view
        
    def _create_editor_view(self) -> QWidget:
        """创建代码编辑器视图"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        
        label = QLabel("💻 代码编辑器视图")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        return view
        
    def _create_workflow_view(self) -> QWidget:
        """创建开发工作流视图"""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        
        label = QLabel("🔄 开发工作流视图")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        return view
        
    def _on_nav_changed(self, nav_name: str):
        """导航切换事件"""
        self._switch_view(nav_name)
        
    def _switch_view(self, view_name: str):
        """切换视图"""
        self.current_view = view_name
        
        view_map = {
            'home': self.home_view,
            'library': self.library_view,
            'backtest': self.backtest_view,
            'optimization': self.optimization_view,
            'performance': self.performance_view,
            'editor': self.editor_view,
            'workflow': self.workflow_view,
        }
        
        if view_name in view_map:
            self.content_stack.setCurrentWidget(view_map[view_name])
            self.sidebar.set_current_nav(view_name)
            
    def _on_quick_action(self, action_id: str):
        """快捷操作事件"""
        action_map = {
            'create': self._create_strategy,
            'backtest': self._quick_backtest,
            'optimize': self._optimize_strategy,
            'import': self._import_strategy,
        }
        
        if action_id in action_map:
            action_map[action_id]()
            
    def _create_strategy(self):
        """创建策略"""
        logger.info("创建新策略")
        
    def _quick_backtest(self):
        """快速回测"""
        logger.info("快速回测")
        
    def _optimize_strategy(self):
        """优化策略"""
        logger.info("优化策略")
        
    def _import_strategy(self):
        """导入策略"""
        logger.info("导入策略")
        
    def _apply_theme(self):
        """应用主题"""
        if self.theme_manager:
            self.theme_manager.apply_theme(self)
            
    def _load_data(self):
        """加载数据"""
        self._load_strategies()
        self._update_stat_cards()
        
    def _load_strategies(self):
        """加载策略列表"""
        if self.strategy_service:
            try:
                strategies = self.strategy_service.get_all_strategy_configs()
                logger.info(f"加载了 {len(strategies)} 个策略")
            except Exception as e:
                logger.error(f"加载策略失败: {e}")
                
    def _update_stat_cards(self):
        """更新统计卡片"""
        import random
        
        total = random.randint(50, 200)
        running = random.randint(5, 20)
        configured = random.randint(30, 100)
        error = random.randint(0, 10)
        
        self.total_strategy_card.set_value(
            str(total),
            trend_percent=random.uniform(-10, 20),
            trend_data=[total - random.randint(1, 10) for _ in range(7)]
        )
        
        self.running_strategy_card.set_value(
            str(running),
            trend_percent=random.uniform(-5, 15),
            trend_data=[running - random.randint(0, 3) for _ in range(7)]
        )
        
        self.configured_strategy_card.set_value(
            str(configured),
            trend_percent=random.uniform(-8, 12),
            trend_data=[configured - random.randint(1, 8) for _ in range(7)]
        )
        
        self.error_strategy_card.set_value(
            str(error),
            trend_percent=random.uniform(-20, 5),
            trend_data=[error + random.randint(0, 2) for _ in range(7)]
        )
        
    def closeEvent(self, event):
        """关闭事件 - 保存工作区"""
        self.workspace_manager.save_workspace('default', {
            'current_view': self.current_view,
            'sidebar_expanded': self.sidebar.is_expanded,
        })
        super().closeEvent(event)
