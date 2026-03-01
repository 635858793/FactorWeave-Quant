# -*- coding: utf-8 -*-
"""策略编辑、运行、调试功能单元测试

测试范围:
1. 策略代码编辑器功能
2. 策略调试器功能
3. 策略开发工作流功能
4. 策略管理器回测功能
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime

import matplotlib
matplotlib.use('Agg')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QTableWidget, QStackedWidget, QComboBox,
    QPlainTextEdit, QDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

app = None


def get_app():
    global app
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestStrategyCodeEditor(unittest.TestCase):
    """测试策略代码编辑器"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_code_editor_initialization(self):
        """测试代码编辑器初始化"""
        from gui.widgets.strategy_code_editor import StrategyCodeEditor
        
        editor = StrategyCodeEditor()
        
        self.assertIsNotNone(editor.code_editor, "代码编辑器应初始化")
        self.assertIsNone(editor.current_file, "当前文件应为None")
        self.assertIsNotNone(editor.is_modified, "修改标志应初始化")

    def test_code_editor_signals(self):
        """测试代码编辑器信号"""
        from gui.widgets.strategy_code_editor import StrategyCodeEditor
        
        editor = StrategyCodeEditor()
        
        self.assertTrue(hasattr(editor, 'code_saved'), "应有code_saved信号")
        self.assertTrue(hasattr(editor, 'code_executed'), "应有code_executed信号")

    def test_code_editor_toolbar_actions(self):
        """测试代码编辑器工具栏动作"""
        from gui.widgets.strategy_code_editor import StrategyCodeEditor
        
        editor = StrategyCodeEditor()
        
        self.assertTrue(hasattr(editor, '_new_file'), "应有新建文件方法")
        self.assertTrue(hasattr(editor, '_open_file'), "应有打开文件方法")
        self.assertTrue(hasattr(editor, '_save_file'), "应有保存文件方法")
        self.assertTrue(hasattr(editor, '_run_code'), "应有运行代码方法")
        self.assertTrue(hasattr(editor, '_format_code'), "应有格式化代码方法")
        self.assertTrue(hasattr(editor, '_check_code'), "应有检查代码方法")
        self.assertTrue(hasattr(editor, '_open_debugger'), "应有打开调试器方法")

    def test_run_code_emits_signal(self):
        """测试运行代码发射信号"""
        from gui.widgets.strategy_code_editor import StrategyCodeEditor
        
        editor = StrategyCodeEditor()
        
        test_code = "print('hello')"
        editor.code_editor.setPlainText(test_code)
        
        signal_received = []
        
        def on_code_executed(code):
            signal_received.append(code)
        
        editor.code_executed.connect(on_code_executed)
        editor._run_code()
        
        self.assertEqual(len(signal_received), 1, "应发射一次信号")
        self.assertEqual(signal_received[0], test_code, "信号应包含代码内容")

    def test_syntax_highlighter_exists(self):
        """测试语法高亮器存在"""
        from gui.widgets.strategy_code_editor import PythonSyntaxHighlighter
        
        self.assertTrue(hasattr(PythonSyntaxHighlighter, '__init__'),
                       "PythonSyntaxHighlighter应有__init__方法")

    def test_error_list_widget_exists(self):
        """测试错误列表组件存在"""
        from gui.widgets.strategy_code_editor import ErrorListWidget
        
        self.assertTrue(hasattr(ErrorListWidget, 'error_clicked'),
                       "ErrorListWidget应有error_clicked信号")

    def test_code_outline_widget_exists(self):
        """测试代码大纲组件存在"""
        from gui.widgets.strategy_code_editor import CodeOutlineWidget
        
        self.assertTrue(hasattr(CodeOutlineWidget, 'outline_item_clicked'),
                       "CodeOutlineWidget应有outline_item_clicked信号")


class TestStrategyDebugger(unittest.TestCase):
    """测试策略调试器"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_debugger_initialization(self):
        """测试调试器初始化"""
        from gui.widgets.strategy_debugger import StrategyDebugger
        
        debugger = StrategyDebugger()
        
        self.assertIsNotNone(debugger.breakpoint_manager, "断点管理器应初始化")
        self.assertFalse(debugger.is_debugging, "调试状态应为False")
        self.assertIsNone(debugger.current_file, "当前文件应为None")

    def test_debugger_signals(self):
        """测试调试器信号"""
        from gui.widgets.strategy_debugger import StrategyDebugger
        
        debugger = StrategyDebugger()
        
        self.assertTrue(hasattr(debugger, 'debug_started'), "应有debug_started信号")
        self.assertTrue(hasattr(debugger, 'debug_stopped'), "应有debug_stopped信号")
        self.assertTrue(hasattr(debugger, 'breakpoint_hit'), "应有breakpoint_hit信号")

    def test_debugger_methods(self):
        """测试调试器方法"""
        from gui.widgets.strategy_debugger import StrategyDebugger
        
        debugger = StrategyDebugger()
        
        self.assertTrue(hasattr(debugger, '_start_debug'), "应有开始调试方法")
        self.assertTrue(hasattr(debugger, '_stop_debug'), "应有停止调试方法")
        self.assertTrue(hasattr(debugger, '_step_over'), "应有单步跳过方法")
        self.assertTrue(hasattr(debugger, '_step_into'), "应有单步进入方法")
        self.assertTrue(hasattr(debugger, '_step_out'), "应有单步退出方法")
        self.assertTrue(hasattr(debugger, '_continue'), "应有继续方法")

    def test_breakpoint_manager(self):
        """测试断点管理器"""
        from gui.widgets.strategy_debugger import BreakpointManager
        
        manager = BreakpointManager()
        
        self.assertTrue(hasattr(manager, 'toggle_breakpoint'), "应有切换断点方法")
        self.assertTrue(hasattr(manager, 'is_breakpoint'), "应有检查断点方法")
        self.assertTrue(hasattr(manager, 'get_breakpoints'), "应有获取断点方法")
        self.assertTrue(hasattr(manager, 'clear_all_breakpoints'), "应有清除所有断点方法")

    def test_breakpoint_manager_operations(self):
        """测试断点管理器操作"""
        from gui.widgets.strategy_debugger import BreakpointManager
        
        manager = BreakpointManager()
        
        manager.toggle_breakpoint('test.py', 10)
        self.assertTrue(manager.is_breakpoint('test.py', 10), "断点应已设置")
        
        manager.toggle_breakpoint('test.py', 10)
        self.assertFalse(manager.is_breakpoint('test.py', 10), "断点应已取消")

    def test_debug_controller_signals(self):
        """测试调试控制器信号"""
        from gui.widgets.strategy_debugger import DebugController
        
        controller = DebugController()
        
        self.assertTrue(hasattr(controller, 'continue_clicked'), "应有continue_clicked信号")
        self.assertTrue(hasattr(controller, 'step_over_clicked'), "应有step_over_clicked信号")
        self.assertTrue(hasattr(controller, 'step_into_clicked'), "应有step_into_clicked信号")
        self.assertTrue(hasattr(controller, 'step_out_clicked'), "应有step_out_clicked信号")
        self.assertTrue(hasattr(controller, 'stop_clicked'), "应有stop_clicked信号")
        self.assertTrue(hasattr(controller, 'restart_clicked'), "应有restart_clicked信号")

    def test_load_code(self):
        """测试加载代码"""
        from gui.widgets.strategy_debugger import StrategyDebugger
        
        debugger = StrategyDebugger()
        test_code = "print('test')"
        
        debugger.load_code(test_code, 'test.py')
        
        self.assertEqual(debugger.code_editor.toPlainText(), test_code, "代码应正确加载")
        self.assertEqual(debugger.current_file, 'test.py', "当前文件应正确设置")


class TestStrategyDevelopmentWorkflow(unittest.TestCase):
    """测试策略开发工作流"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_workflow_initialization(self):
        """测试工作流初始化"""
        from gui.widgets.strategy_development_workflow import StrategyDevelopmentWorkflow, WorkflowStage
        
        workflow = StrategyDevelopmentWorkflow()
        
        self.assertEqual(workflow.current_stage, WorkflowStage.DESIGN, "初始阶段应为DESIGN")

    def test_workflow_signals(self):
        """测试工作流信号"""
        from gui.widgets.strategy_development_workflow import StrategyDevelopmentWorkflow
        
        workflow = StrategyDevelopmentWorkflow()
        
        self.assertTrue(hasattr(workflow, 'workflow_completed'), "应有workflow_completed信号")
        self.assertTrue(hasattr(workflow, 'stage_changed'), "应有stage_changed信号")

    def test_workflow_stages(self):
        """测试工作流阶段"""
        from gui.widgets.strategy_development_workflow import WorkflowStage
        
        stages = list(WorkflowStage)
        
        self.assertIn(WorkflowStage.DESIGN, stages, "应包含DESIGN阶段")
        self.assertIn(WorkflowStage.CODING, stages, "应包含CODING阶段")
        self.assertIn(WorkflowStage.DEBUGGING, stages, "应包含DEBUGGING阶段")
        self.assertIn(WorkflowStage.BACKTEST, stages, "应包含BACKTEST阶段")
        self.assertIn(WorkflowStage.OPTIMIZATION, stages, "应包含OPTIMIZATION阶段")
        self.assertIn(WorkflowStage.DEPLOYMENT, stages, "应包含DEPLOYMENT阶段")

    def test_workflow_steps_structure(self):
        """测试工作流步骤结构"""
        from gui.widgets.strategy_development_workflow import StrategyDevelopmentWorkflow, WorkflowStage
        
        workflow = StrategyDevelopmentWorkflow()
        
        for stage in WorkflowStage:
            self.assertIn(stage, workflow.steps, f"应包含{stage}阶段的步骤")
            self.assertGreater(len(workflow.steps[stage]), 0, f"{stage}阶段应有步骤")


class TestStrategyServiceIntegration(unittest.TestCase):
    """测试策略服务集成"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_strategy_service_methods(self):
        """测试策略服务方法"""
        from core.services.strategy_service import StrategyService
        
        self.assertTrue(hasattr(StrategyService, 'run_backtest'), "应有run_backtest方法")
        self.assertTrue(hasattr(StrategyService, 'get_all_strategy_configs'), "应有get_all_strategy_configs方法")
        self.assertTrue(hasattr(StrategyService, 'get_all_backtest_tasks'), "应有get_all_backtest_tasks方法")

    def test_strategy_config_dataclass(self):
        """测试策略配置数据类"""
        from core.services.strategy_service import StrategyConfig
        
        config = StrategyConfig(
            strategy_id="test_strategy",
            plugin_type="factorweave",
            parameters={"param1": 10}
        )
        
        self.assertEqual(config.strategy_id, "test_strategy", "策略ID应正确")
        self.assertEqual(config.plugin_type, "factorweave", "插件类型应正确")
        self.assertEqual(config.parameters["param1"], 10, "参数应正确")

    def test_backtest_status_enum(self):
        """测试回测状态枚举"""
        from core.services.strategy_service import BacktestStatus
        
        self.assertTrue(hasattr(BacktestStatus, 'PENDING'), "应有PENDING状态")
        self.assertTrue(hasattr(BacktestStatus, 'RUNNING'), "应有RUNNING状态")
        self.assertTrue(hasattr(BacktestStatus, 'COMPLETED'), "应有COMPLETED状态")
        self.assertTrue(hasattr(BacktestStatus, 'FAILED'), "应有FAILED状态")


class TestCodeExecution(unittest.TestCase):
    """测试代码执行功能"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_code_execution_with_valid_strategy(self):
        """测试有效策略代码执行"""
        valid_code = '''
class MyStrategy:
    def generate_signals(self, data):
        return []
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(valid_code)
            temp_file = f.name
        
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("temp_strategy", temp_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            strategy_found = False
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and hasattr(obj, 'generate_signals'):
                    strategy_found = True
                    break
            
            self.assertTrue(strategy_found, "应找到策略类")
        finally:
            os.unlink(temp_file)

    def test_code_execution_with_syntax_error(self):
        """测试语法错误代码执行"""
        invalid_code = '''
class MyStrategy:
    def generate_signals(self, data
        return []
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(invalid_code)
            temp_file = f.name
        
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("temp_strategy", temp_file)
            module = importlib.util.module_from_spec(spec)
            
            with self.assertRaises(SyntaxError):
                spec.loader.exec_module(module)
        finally:
            os.unlink(temp_file)


class TestBacktestConfiguration(unittest.TestCase):
    """测试回测配置"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_strategy_context_creation(self):
        """测试策略上下文创建"""
        from core.strategy_extensions import StrategyContext, TimeFrame
        
        context = StrategyContext(
            symbol="000001.SZ",
            timeframe=TimeFrame.DAY_1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=100000.0
        )
        
        self.assertEqual(context.symbol, "000001.SZ", "股票代码应正确")
        self.assertEqual(context.initial_capital, 100000.0, "初始资金应正确")

    def test_standard_market_data_creation(self):
        """测试标准市场数据创建"""
        import pandas as pd
        from core.strategy_extensions import StandardMarketData
        
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        data = {
            'open': [10.0] * 10,
            'high': [11.0] * 10,
            'low': [9.0] * 10,
            'close': [10.5] * 10,
            'volume': [1000000] * 10
        }
        df = pd.DataFrame(data, index=dates)
        
        market_data = StandardMarketData(
            symbol="000001.SZ",
            datetime=dates,
            open=df['open'].values,
            high=df['high'].values,
            low=df['low'].values,
            close=df['close'].values,
            volume=df['volume'].values
        )
        
        self.assertEqual(market_data.symbol, "000001.SZ", "股票代码应正确")
        self.assertEqual(len(market_data.datetime), 10, "数据长度应正确")


class TestDialogIntegration(unittest.TestCase):
    """测试对话框集成 - 使用源代码分析避免Qt/matplotlib冲突"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def _get_methods_from_source(self, file_path: str, class_name: str):
        """从源代码文件中提取类方法"""
        import re
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = rf'class {class_name}.*?(?=class\s|\Z)'
        class_match = re.search(pattern, content, re.DOTALL)
        if not class_match:
            return []
        
        class_content = class_match.group(0)
        method_pattern = r'def\s+(\w+)\s*\('
        methods = re.findall(method_pattern, class_content)
        return methods

    def test_dialog_has_code_editor_view(self):
        """测试对话框包含代码编辑器视图"""
        methods = self._get_methods_from_source(
            'gui/dialogs/enhanced_strategy_manager_dialog.py',
            'EnhancedStrategyManagerDialog'
        )
        self.assertIn('_create_editor_view', methods,
                     "应有创建编辑器视图方法")

    def test_dialog_has_workflow_view(self):
        """测试对话框包含工作流视图"""
        methods = self._get_methods_from_source(
            'gui/dialogs/enhanced_strategy_manager_dialog.py',
            'EnhancedStrategyManagerDialog'
        )
        self.assertIn('_create_workflow_view', methods,
                     "应有创建工作流视图方法")

    def test_dialog_has_backtest_view(self):
        """测试对话框包含回测视图"""
        methods = self._get_methods_from_source(
            'gui/dialogs/enhanced_strategy_manager_dialog.py',
            'EnhancedStrategyManagerDialog'
        )
        self.assertIn('_create_backtest_view', methods,
                     "应有创建回测视图方法")

    def test_dialog_has_code_execution_callback(self):
        """测试对话框包含代码执行回调"""
        methods = self._get_methods_from_source(
            'gui/dialogs/enhanced_strategy_manager_dialog.py',
            'EnhancedStrategyManagerDialog'
        )
        self.assertIn('_on_code_executed', methods,
                     "应有代码执行回调方法")

    def test_dialog_has_backtest_method(self):
        """测试对话框包含回测方法"""
        methods = self._get_methods_from_source(
            'gui/dialogs/enhanced_strategy_manager_dialog.py',
            'EnhancedStrategyManagerDialog'
        )
        self.assertIn('_run_backtest', methods,
                     "应有运行回测方法")
        self.assertIn('_run_backtest_async', methods,
                     "应有异步运行回测方法")


class TestVariableViewer(unittest.TestCase):
    """测试变量查看器"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_variable_viewer_initialization(self):
        """测试变量查看器初始化"""
        from gui.widgets.strategy_debugger import VariableViewer
        
        viewer = VariableViewer()
        
        self.assertTrue(hasattr(viewer, 'update_variables'), "应有update_variables方法")

    def test_variable_viewer_update(self):
        """测试变量查看器更新"""
        from gui.widgets.strategy_debugger import VariableViewer
        
        viewer = VariableViewer()
        
        local_vars = {'x': 1, 'y': 2}
        global_vars = {'z': 3}
        
        viewer.update_variables(local_vars, global_vars)


class TestCallStackViewer(unittest.TestCase):
    """测试调用栈查看器"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_call_stack_viewer_initialization(self):
        """测试调用栈查看器初始化"""
        from gui.widgets.strategy_debugger import CallStackViewer
        
        viewer = CallStackViewer()
        
        self.assertTrue(hasattr(viewer, 'frame_clicked'), "应有frame_clicked信号")


class TestBreakpointListWidget(unittest.TestCase):
    """测试断点列表组件"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_breakpoint_list_initialization(self):
        """测试断点列表初始化"""
        from gui.widgets.strategy_debugger import BreakpointListWidget
        
        widget = BreakpointListWidget()
        
        self.assertTrue(hasattr(widget, 'breakpoint_clicked'), "应有breakpoint_clicked信号")
        self.assertTrue(hasattr(widget, 'breakpoint_toggled'), "应有breakpoint_toggled信号")
        self.assertTrue(hasattr(widget, 'breakpoint_removed'), "应有breakpoint_removed信号")


if __name__ == '__main__':
    unittest.main(verbosity=2)
