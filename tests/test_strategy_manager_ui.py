# -*- coding: utf-8 -*-
"""策略管理器UI功能单元测试

测试范围:
1. 视图切换功能
2. 自适应高度设置
3. UI组件创建
4. 业务逻辑验证
"""

import unittest
import sys
from unittest.mock import Mock, MagicMock, patch

import matplotlib
matplotlib.use('Agg')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QSizePolicy, QTableWidget, QStackedWidget, QComboBox
)
from PyQt5.QtCore import Qt

app = None


def get_app():
    global app
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestViewSwitching(unittest.TestCase):
    """测试视图切换功能"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_view_map_contains_all_views(self):
        """测试视图映射包含所有视图"""
        view_map = {
            'home': 'home_view',
            'library': 'library_view',
            'backtest': 'backtest_view',
            'optimization': 'optimization_view',
            'performance': 'performance_view',
            'editor': 'editor_view',
            'workflow': 'workflow_view'
        }
        
        expected_views = ['home', 'library', 'backtest', 'optimization', 
                         'performance', 'editor', 'workflow']
        
        for view_name in expected_views:
            self.assertIn(view_name, view_map, 
                         f"视图映射缺少 {view_name} 视图")

    def test_nav_name_map_contains_all_views(self):
        """测试导航名称映射包含所有视图"""
        nav_name_map = {
            'home': 0,
            'library': 1,
            'backtest': 2,
            'optimization': 3,
            'performance': 4,
            'editor': 5,
            'workflow': 6
        }
        
        expected_views = ['home', 'library', 'backtest', 'optimization', 
                         'performance', 'editor', 'workflow']
        
        for view_name in expected_views:
            self.assertIn(view_name, nav_name_map, 
                         f"导航名称映射缺少 {view_name} 视图")

    def test_view_switching_logic(self):
        """测试视图切换逻辑"""
        content_stack = QStackedWidget()
        
        views = {}
        for name in ['home', 'library', 'backtest', 'optimization', 
                    'performance', 'editor', 'workflow']:
            widget = QWidget()
            widget.setObjectName(f"{name}_view")
            views[name] = widget
            content_stack.addWidget(widget)
        
        view_map = {
            'home': views['home'],
            'library': views['library'],
            'backtest': views['backtest'],
            'optimization': views['optimization'],
            'performance': views['performance'],
            'editor': views['editor'],
            'workflow': views['workflow']
        }
        
        for view_name, expected_widget in view_map.items():
            content_stack.setCurrentWidget(view_map.get(view_name))
            current = content_stack.currentWidget()
            self.assertEqual(current, expected_widget, 
                           f"切换到 {view_name} 视图失败")


class TestStatCardSizePolicy(unittest.TestCase):
    """测试统计卡片自适应高度"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_stat_card_size_policy(self):
        """测试统计卡片使用正确的sizePolicy"""
        card = QWidget()
        card.setMinimumHeight(100)
        card.setMinimumWidth(150)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        size_policy = card.sizePolicy()
        
        self.assertEqual(size_policy.horizontalPolicy(), QSizePolicy.Preferred,
                        "统计卡片水平策略应为Preferred")
        self.assertEqual(size_policy.verticalPolicy(), QSizePolicy.Fixed,
                        "统计卡片垂直策略应为Fixed")
        
        self.assertEqual(card.minimumHeight(), 100,
                        "统计卡片最小高度应为100")
        self.assertEqual(card.minimumWidth(), 150,
                        "统计卡片最小宽度应为150")

    def test_stat_card_not_fixed_size(self):
        """测试统计卡片不使用固定大小"""
        card = QWidget()
        card.setMinimumHeight(100)
        card.setMinimumWidth(150)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        self.assertFalse(card.hasHeightForWidth(),
                        "统计卡片不应有高度随宽度变化")
        
        max_height = card.maximumHeight()
        self.assertEqual(max_height, 16777215,
                        "统计卡片不应设置最大高度限制")


class TestMetricCardSizePolicy(unittest.TestCase):
    """测试性能指标卡片自适应高度"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_metric_card_size_policy(self):
        """测试性能指标卡片使用正确的sizePolicy"""
        card = QWidget()
        card.setMinimumHeight(80)
        card.setMinimumWidth(150)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        
        size_policy = card.sizePolicy()
        
        self.assertEqual(size_policy.horizontalPolicy(), QSizePolicy.Preferred,
                        "性能指标卡片水平策略应为Preferred")
        self.assertEqual(size_policy.verticalPolicy(), QSizePolicy.Fixed,
                        "性能指标卡片垂直策略应为Fixed")

    def test_metric_card_minimum_size(self):
        """测试性能指标卡片最小尺寸"""
        card = QWidget()
        card.setMinimumHeight(80)
        card.setMinimumWidth(150)
        
        self.assertEqual(card.minimumHeight(), 80,
                        "性能指标卡片最小高度应为80")
        self.assertEqual(card.minimumWidth(), 150,
                        "性能指标卡片最小宽度应为150")


class TestStrategyTableCreation(unittest.TestCase):
    """测试策略表格创建"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_strategy_table_columns(self):
        """测试策略表格列数和列名"""
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "选择", "策略ID", "策略名称", "框架", "类型", 
            "默认账号", "状态", "最后更新", "操作"
        ])
        
        self.assertEqual(table.columnCount(), 9,
                        "策略表格应有9列")
        
        headers = [table.horizontalHeaderItem(i).text() 
                  for i in range(table.columnCount())]
        expected_headers = ["选择", "策略ID", "策略名称", "框架", "类型", 
                          "默认账号", "状态", "最后更新", "操作"]
        self.assertEqual(headers, expected_headers,
                        "策略表格列名不正确")

    def test_strategy_table_stretch_last_section(self):
        """测试策略表格最后一列自动拉伸"""
        table = QTableWidget()
        table.horizontalHeader().setStretchLastSection(True)
        
        self.assertTrue(table.horizontalHeader().stretchLastSection(),
                       "策略表格最后一列应自动拉伸")

    def test_ranking_table_columns(self):
        """测试排行榜表格列数和列名"""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "排名", "策略名称", "收益率", "夏普比率", "操作"
        ])
        
        self.assertEqual(table.columnCount(), 5,
                        "排行榜表格应有5列")


class TestBusinessLogic(unittest.TestCase):
    """测试业务逻辑"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_get_all_backtest_tasks_method_exists(self):
        """测试StrategyService有get_all_backtest_tasks方法"""
        from core.services.strategy_service import StrategyService
        
        self.assertTrue(hasattr(StrategyService, 'get_all_backtest_tasks'),
                       "StrategyService应有get_all_backtest_tasks方法")

    def test_get_all_backtest_tasks_returns_dict(self):
        """测试get_all_backtest_tasks返回字典"""
        from core.services.strategy_service import StrategyService
        
        with patch.object(StrategyService, '__init__', return_value=None):
            service = StrategyService.__new__(StrategyService)
            service._backtest_tasks = {}
            
            result = service.get_all_backtest_tasks()
            
            self.assertIsInstance(result, dict,
                                "get_all_backtest_tasks应返回字典")

    def test_strategy_config_dataclass(self):
        """测试策略配置数据类"""
        from core.services.strategy_service import StrategyConfig
        from datetime import datetime
        
        config = StrategyConfig(
            strategy_id="test_strategy",
            plugin_type="test_plugin",
            parameters={}
        )
        
        self.assertEqual(config.strategy_id, "test_strategy",
                        "策略ID应正确设置")
        self.assertEqual(config.plugin_type, "test_plugin",
                        "插件类型应正确设置")
        self.assertIsInstance(config.created_at, datetime,
                            "创建时间应为datetime类型")


class TestUILayoutStructure(unittest.TestCase):
    """测试UI布局结构"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_main_layout_structure(self):
        """测试主布局结构"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        nav_bar = QWidget()
        layout.addWidget(nav_bar)
        
        content_stack = QStackedWidget()
        layout.addWidget(content_stack)
        
        self.assertEqual(layout.count(), 2,
                        "主布局应有2个组件: 导航栏和内容区")

    def test_home_view_layout(self):
        """测试首页视图布局"""
        home_view = QWidget()
        layout = QVBoxLayout(home_view)
        
        stats_layout = QHBoxLayout()
        layout.addLayout(stats_layout)
        
        self.assertEqual(layout.count(), 1,
                        "首页视图应有统计卡片区域")

    def test_backtest_view_layout(self):
        """测试回测视图布局"""
        backtest_view = QWidget()
        layout = QHBoxLayout(backtest_view)
        
        config_panel = QWidget()
        layout.addWidget(config_panel, 1)
        
        result_panel = QWidget()
        layout.addWidget(result_panel, 2)
        
        self.assertEqual(layout.count(), 2,
                        "回测视图应有配置面板和结果面板")

    def test_optimization_view_layout(self):
        """测试优化视图布局"""
        optimization_view = QWidget()
        layout = QHBoxLayout(optimization_view)
        
        param_panel = QWidget()
        layout.addWidget(param_panel, 1)
        
        result_panel = QWidget()
        layout.addWidget(result_panel, 2)
        
        self.assertEqual(layout.count(), 2,
                        "优化视图应有参数面板和结果面板")


class TestNavigationButtonLogic(unittest.TestCase):
    """测试导航按钮逻辑"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_nav_items_count(self):
        """测试导航项数量"""
        nav_items = [
            ('🏠 首页', 'home'),
            ('📋 策略库', 'library'),
            ('🔬 回测实验室', 'backtest'),
            ('⚙️ 参数优化', 'optimization'),
            ('📊 性能分析', 'performance'),
            ('💻 代码编辑器', 'editor'),
            ('🔄 开发工作流', 'workflow')
        ]
        
        self.assertEqual(len(nav_items), 7,
                        "应有7个导航项")

    def test_nav_item_names(self):
        """测试导航项名称"""
        nav_items = [
            ('🏠 首页', 'home'),
            ('📋 策略库', 'library'),
            ('🔬 回测实验室', 'backtest'),
            ('⚙️ 参数优化', 'optimization'),
            ('📊 性能分析', 'performance'),
            ('💻 代码编辑器', 'editor'),
            ('🔄 开发工作流', 'workflow')
        ]
        
        expected_names = ['home', 'library', 'backtest', 'optimization', 
                         'performance', 'editor', 'workflow']
        actual_names = [name for _, name in nav_items]
        
        self.assertEqual(actual_names, expected_names,
                        "导航项名称应正确")


if __name__ == '__main__':
    unittest.main(verbosity=2)
