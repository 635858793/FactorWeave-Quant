"""
UI改进功能单元测试
测试文件大纲、断点列表、风险指标图表等功能
"""
import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import matplotlib
matplotlib.use('Agg')

from PyQt5.QtWidgets import QApplication, QListWidgetItem
from PyQt5.QtCore import Qt


class TestCodeOutlineWidget(unittest.TestCase):
    """测试代码大纲组件"""

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        from gui.widgets.strategy_code_editor import CodeOutlineWidget
        self.outline_widget = CodeOutlineWidget()

    def test_init_ui(self):
        """测试UI初始化"""
        self.assertIsNotNone(self.outline_widget.outline_tree)
        self.assertEqual(self.outline_widget._outline_items, [])

    def test_update_outline_with_class(self):
        """测试类定义的大纲解析"""
        code = '''
class MyStrategy:
    def __init__(self):
        pass
    
    def generate_signals(self, data):
        return data
'''
        self.outline_widget.update_outline(code)
        
        self.assertGreater(self.outline_widget.outline_tree.count(), 0)
        
        found_class = False
        found_method = False
        for i in range(self.outline_widget.outline_tree.count()):
            item = self.outline_widget.outline_tree.item(i)
            text = item.text()
            if 'MyStrategy' in text:
                found_class = True
            if 'generate_signals' in text:
                found_method = True
        
        self.assertTrue(found_class, "应该找到类定义")
        self.assertTrue(found_method, "应该找到方法定义")

    def test_update_outline_with_imports(self):
        """测试导入语句的大纲解析"""
        code = '''
import pandas as pd
import numpy as np
from core.strategy import BaseStrategy
'''
        self.outline_widget.update_outline(code)
        
        self.assertGreater(self.outline_widget.outline_tree.count(), 0)

    def test_update_outline_empty_code(self):
        """测试空代码的大纲解析"""
        self.outline_widget.update_outline('')
        self.assertEqual(self.outline_widget.outline_tree.count(), 0)

    def test_outline_item_click(self):
        """测试大纲项点击"""
        code = '''
class TestClass:
    def test_method(self):
        pass
'''
        self.outline_widget.update_outline(code)
        
        clicked_line = []
        def on_click(line):
            clicked_line.append(line)
        
        self.outline_widget.outline_item_clicked.connect(on_click)
        
        if self.outline_widget.outline_tree.count() > 0:
            item = self.outline_widget.outline_tree.item(0)
            self.outline_widget._on_item_clicked(item)
            self.assertEqual(len(clicked_line), 1)

    def test_clear_outline(self):
        """测试清除大纲"""
        code = 'class TestClass: pass'
        self.outline_widget.update_outline(code)
        self.assertGreater(self.outline_widget.outline_tree.count(), 0)
        
        self.outline_widget.clear_outline()
        self.assertEqual(self.outline_widget.outline_tree.count(), 0)


class TestBreakpointListWidget(unittest.TestCase):
    """测试断点列表面板"""

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        from gui.widgets.strategy_debugger import BreakpointListWidget
        self.bp_widget = BreakpointListWidget()

    def test_init_ui(self):
        """测试UI初始化"""
        self.assertIsNotNone(self.bp_widget.bp_list)
        self.assertEqual(self.bp_widget._breakpoints_data, [])

    def test_update_breakpoints(self):
        """测试更新断点列表"""
        breakpoints = {
            '/path/to/file1.py': {10, 20, 30},
            '/path/to/file2.py': {5, 15}
        }
        enabled_breakpoints = {
            '/path/to/file1.py': {10, 20},
            '/path/to/file2.py': {5}
        }
        
        self.bp_widget.update_breakpoints(breakpoints, enabled_breakpoints)
        
        self.assertEqual(self.bp_widget.bp_list.count(), 5)
        self.assertEqual(len(self.bp_widget._breakpoints_data), 5)

    def test_breakpoint_enable_disable_state(self):
        """测试断点启用/禁用状态显示"""
        breakpoints = {'/path/to/file.py': {10, 20}}
        enabled_breakpoints = {'/path/to/file.py': {10}}
        
        self.bp_widget.update_breakpoints(breakpoints, enabled_breakpoints)
        
        enabled_count = 0
        disabled_count = 0
        for i in range(self.bp_widget.bp_list.count()):
            item = self.bp_widget.bp_list.item(i)
            text = item.text()
            if text.startswith('🟢'):
                enabled_count += 1
            elif text.startswith('⚪'):
                disabled_count += 1
        
        self.assertEqual(enabled_count, 1)
        self.assertEqual(disabled_count, 1)

    def test_breakpoint_click_signal(self):
        """测试断点点击信号"""
        breakpoints = {'/path/to/file.py': {10}}
        enabled_breakpoints = {'/path/to/file.py': {10}}
        
        self.bp_widget.update_breakpoints(breakpoints, enabled_breakpoints)
        
        clicked_data = []
        def on_click(file_path, line):
            clicked_data.append((file_path, line))
        
        self.bp_widget.breakpoint_clicked.connect(on_click)
        
        item = self.bp_widget.bp_list.item(0)
        self.bp_widget._on_breakpoint_clicked(item)
        
        self.assertEqual(len(clicked_data), 1)
        self.assertEqual(clicked_data[0][0], '/path/to/file.py')
        self.assertEqual(clicked_data[0][1], 10)

    def test_breakpoint_remove(self):
        """测试断点删除"""
        breakpoints = {'/path/to/file.py': {10}}
        enabled_breakpoints = {'/path/to/file.py': {10}}
        
        self.bp_widget.update_breakpoints(breakpoints, enabled_breakpoints)
        
        removed_data = []
        def on_remove(file_path, line):
            removed_data.append((file_path, line))
        
        self.bp_widget.breakpoint_removed.connect(on_remove)
        
        item = self.bp_widget.bp_list.item(0)
        self.bp_widget.bp_list.setCurrentItem(item)
        self.bp_widget._remove_selected()
        
        self.assertEqual(len(removed_data), 1)


class TestRiskMetricsHistory(unittest.TestCase):
    """测试风险指标历史记录（不依赖UI）"""

    def test_risk_metrics_history_logic(self):
        """测试风险指标历史记录逻辑"""
        max_history_points = 50
        history = []
        
        for i in range(60):
            risk_metrics = {
                'var_95': 0.01 * i,
                'cvar_95': 0.02 * i,
                'max_drawdown': 0.03 * i,
                'volatility': 0.04 * i,
                'sharpe_ratio': i * 0.1
            }
            history.append(risk_metrics.copy())
            if len(history) > max_history_points:
                history.pop(0)
        
        self.assertEqual(len(history), 50)
        self.assertEqual(history[0]['var_95'], 0.10)
        self.assertEqual(history[-1]['var_95'], 0.59)

    def test_risk_metrics_values(self):
        """测试风险指标值计算"""
        risk_metrics = {
            'var_95': 0.05,
            'cvar_95': 0.08,
            'max_drawdown': 0.15,
            'volatility': 0.20,
            'sharpe_ratio': 1.5
        }
        
        var_values = risk_metrics.get('var_95', 0) * 100
        cvar_values = risk_metrics.get('cvar_95', 0) * 100
        drawdown_values = risk_metrics.get('max_drawdown', 0) * 100
        sharpe_values = risk_metrics.get('sharpe_ratio', 0)
        
        self.assertEqual(var_values, 5.0)
        self.assertEqual(cvar_values, 8.0)
        self.assertEqual(drawdown_values, 15.0)
        self.assertEqual(sharpe_values, 1.5)


class TestStrategyCodeEditorOutline(unittest.TestCase):
    """测试策略代码编辑器大纲功能"""

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_outline_parsing_patterns(self):
        """测试大纲解析模式"""
        import re
        
        class_pattern = re.compile(r'^(\s*)class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:\(]')
        function_pattern = re.compile(r'^(\s*)def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        import_pattern = re.compile(r'^(\s*)(import|from)\s+')
        
        class_line = 'class MyStrategy:'
        func_line = '    def generate_signals(self, data):'
        import_line = 'import pandas as pd'
        
        class_match = class_pattern.match(class_line)
        self.assertIsNotNone(class_match)
        self.assertEqual(class_match.group(2), 'MyStrategy')
        
        func_match = function_pattern.match(func_line)
        self.assertIsNotNone(func_match)
        self.assertEqual(func_match.group(2), 'generate_signals')
        
        import_match = import_pattern.match(import_line)
        self.assertIsNotNone(import_match)

    def test_outline_navigation_logic(self):
        """测试大纲导航逻辑"""
        lines = ['line1', 'line2', 'line3', 'line4', 'line5']
        
        target_line = 3
        if 1 <= target_line <= len(lines):
            line_content = lines[target_line - 1]
            self.assertEqual(line_content, 'line3')


class TestBreakpointManagerIntegration(unittest.TestCase):
    """测试断点管理器集成"""

    def setUp(self):
        from gui.widgets.strategy_debugger import BreakpointManager
        self.bp_manager = BreakpointManager()

    def test_add_remove_breakpoints(self):
        """测试添加和删除断点"""
        self.bp_manager.add_breakpoint('/test/file.py', 10)
        self.assertTrue(self.bp_manager.is_breakpoint('/test/file.py', 10))
        
        self.bp_manager.remove_breakpoint('/test/file.py', 10)
        self.assertFalse(self.bp_manager.is_breakpoint('/test/file.py', 10))

    def test_enable_disable_breakpoints(self):
        """测试启用和禁用断点"""
        self.bp_manager.add_breakpoint('/test/file.py', 10)
        
        self.bp_manager.disable_breakpoint('/test/file.py', 10)
        self.assertFalse(self.bp_manager.is_breakpoint('/test/file.py', 10))
        
        self.bp_manager.enable_breakpoint('/test/file.py', 10)
        self.assertTrue(self.bp_manager.is_breakpoint('/test/file.py', 10))

    def test_toggle_breakpoint(self):
        """测试切换断点状态"""
        self.bp_manager.toggle_breakpoint('/test/file.py', 10)
        self.assertTrue(self.bp_manager.is_breakpoint('/test/file.py', 10))
        
        self.bp_manager.toggle_breakpoint('/test/file.py', 10)
        self.assertFalse(self.bp_manager.is_breakpoint('/test/file.py', 10))

    def test_get_breakpoints(self):
        """测试获取断点列表"""
        self.bp_manager.add_breakpoint('/test/file.py', 10)
        self.bp_manager.add_breakpoint('/test/file.py', 20)
        self.bp_manager.add_breakpoint('/test/file.py', 30)
        
        breakpoints = self.bp_manager.get_breakpoints('/test/file.py')
        self.assertEqual(len(breakpoints), 3)
        self.assertIn(10, breakpoints)
        self.assertIn(20, breakpoints)
        self.assertIn(30, breakpoints)

    def test_clear_all_breakpoints(self):
        """测试清除所有断点"""
        self.bp_manager.add_breakpoint('/test/file1.py', 10)
        self.bp_manager.add_breakpoint('/test/file2.py', 20)
        
        self.bp_manager.clear_all_breakpoints()
        
        self.assertEqual(len(self.bp_manager.breakpoints), 0)
        self.assertEqual(len(self.bp_manager.enabled_breakpoints), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
