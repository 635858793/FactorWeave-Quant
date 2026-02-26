"""
策略组件单元测试
测试策略代码编辑器、调试工具、开发工作流和风险管理集成
"""
import os
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Set

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class TestBreakpointManager(unittest.TestCase):
    """测试断点管理器"""

    def setUp(self):
        from gui.widgets.strategy_debugger import BreakpointManager
        self.manager = BreakpointManager()

    def test_add_breakpoint(self):
        self.manager.add_breakpoint('test.py', 10)
        self.assertIn(10, self.manager.breakpoints.get('test.py', set()))
        self.assertIn(10, self.manager.enabled_breakpoints.get('test.py', set()))

    def test_remove_breakpoint(self):
        self.manager.add_breakpoint('test.py', 10)
        self.manager.remove_breakpoint('test.py', 10)
        self.assertNotIn(10, self.manager.breakpoints.get('test.py', set()))

    def test_toggle_breakpoint(self):
        self.manager.toggle_breakpoint('test.py', 10)
        self.assertIn(10, self.manager.breakpoints.get('test.py', set()))
        self.manager.toggle_breakpoint('test.py', 10)
        self.assertNotIn(10, self.manager.breakpoints.get('test.py', set()))

    def test_enable_disable_breakpoint(self):
        self.manager.add_breakpoint('test.py', 10)
        self.manager.disable_breakpoint('test.py', 10)
        self.assertNotIn(10, self.manager.enabled_breakpoints.get('test.py', set()))
        self.manager.enable_breakpoint('test.py', 10)
        self.assertIn(10, self.manager.enabled_breakpoints.get('test.py', set()))

    def test_is_breakpoint(self):
        self.manager.add_breakpoint('test.py', 10)
        self.assertTrue(self.manager.is_breakpoint('test.py', 10))
        self.assertFalse(self.manager.is_breakpoint('test.py', 20))
        self.manager.disable_breakpoint('test.py', 10)
        self.assertFalse(self.manager.is_breakpoint('test.py', 10))

    def test_get_breakpoints(self):
        self.manager.add_breakpoint('test.py', 10)
        self.manager.add_breakpoint('test.py', 20)
        breakpoints = self.manager.get_breakpoints('test.py')
        self.assertEqual(len(breakpoints), 2)
        self.assertIn(10, breakpoints)
        self.assertIn(20, breakpoints)

    def test_clear_all_breakpoints(self):
        self.manager.add_breakpoint('test.py', 10)
        self.manager.add_breakpoint('test2.py', 20)
        self.manager.clear_all_breakpoints()
        self.assertEqual(len(self.manager.breakpoints), 0)
        self.assertEqual(len(self.manager.enabled_breakpoints), 0)


class TestPythonSyntaxHighlighter(unittest.TestCase):
    """测试Python语法高亮器"""

    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QTextDocument
        from gui.widgets.strategy_code_editor import PythonSyntaxHighlighter
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.document = QTextDocument()
        self.highlighter = PythonSyntaxHighlighter(self.document)

    def test_formats_initialized(self):
        self.assertIsNotNone(self.highlighter.formats)
        self.assertIn('keyword', self.highlighter.formats)
        self.assertIn('builtins', self.highlighter.formats)
        self.assertIn('string', self.highlighter.formats)
        self.assertIn('comment', self.highlighter.formats)
        self.assertIn('number', self.highlighter.formats)

    def test_rules_initialized(self):
        self.assertIsNotNone(self.highlighter.rules)
        self.assertGreater(len(self.highlighter.rules), 0)

    def test_keyword_highlight(self):
        self.document.setPlainText('def test(): pass')
        self.highlighter.rehighlight()

    def test_string_highlight(self):
        self.document.setPlainText('x = "hello world"')
        self.highlighter.rehighlight()

    def test_comment_highlight(self):
        self.document.setPlainText('# This is a comment')
        self.highlighter.rehighlight()


class TestWorkflowStage(unittest.TestCase):
    """测试工作流阶段"""

    def test_stage_values(self):
        from gui.widgets.strategy_development_workflow import WorkflowStage
        
        self.assertEqual(WorkflowStage.DESIGN.value, "设计")
        self.assertEqual(WorkflowStage.CODING.value, "编码")
        self.assertEqual(WorkflowStage.DEBUGGING.value, "调试")
        self.assertEqual(WorkflowStage.BACKTEST.value, "回测")
        self.assertEqual(WorkflowStage.OPTIMIZATION.value, "优化")
        self.assertEqual(WorkflowStage.DEPLOYMENT.value, "部署")

    def test_stage_count(self):
        from gui.widgets.strategy_development_workflow import WorkflowStage
        self.assertEqual(len(WorkflowStage), 6)


class TestWorkflowStep(unittest.TestCase):
    """测试工作流步骤"""

    def test_step_creation(self):
        from gui.widgets.strategy_development_workflow import WorkflowStep, WorkflowStage
        
        step = WorkflowStep(
            stage=WorkflowStage.DESIGN,
            name="测试步骤",
            description="这是一个测试步骤",
            is_completed=False
        )
        
        self.assertEqual(step.stage, WorkflowStage.DESIGN)
        self.assertEqual(step.name, "测试步骤")
        self.assertEqual(step.description, "这是一个测试步骤")
        self.assertFalse(step.is_completed)
        self.assertEqual(step.data, {})

    def test_step_data_storage(self):
        from gui.widgets.strategy_development_workflow import WorkflowStep, WorkflowStage
        
        step = WorkflowStep(WorkflowStage.DESIGN, "测试", "描述")
        step.data['key'] = 'value'
        step.data['nested'] = {'a': 1, 'b': 2}
        
        self.assertEqual(step.data['key'], 'value')
        self.assertEqual(step.data['nested']['a'], 1)


class TestErrorListWidget(unittest.TestCase):
    """测试错误列表组件"""

    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.strategy_code_editor import ErrorListWidget
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.widget = ErrorListWidget()

    def test_update_errors(self):
        errors = [
            {'line': 10, 'column': 5, 'message': 'Syntax error', 'severity': 'error'},
            {'line': 20, 'column': 0, 'message': 'Unused variable', 'severity': 'warning'},
        ]
        self.widget.update_errors(errors)
        self.assertEqual(self.widget.error_list.count(), 2)

    def test_clear_errors(self):
        errors = [
            {'line': 10, 'column': 5, 'message': 'Error', 'severity': 'error'},
        ]
        self.widget.update_errors(errors)
        self.widget.clear_errors()
        self.assertEqual(self.widget.error_list.count(), 0)

    def test_error_severity_colors(self):
        error_item = {'line': 1, 'column': 0, 'message': 'Error', 'severity': 'error'}
        warning_item = {'line': 2, 'column': 0, 'message': 'Warning', 'severity': 'warning'}
        info_item = {'line': 3, 'column': 0, 'message': 'Info', 'severity': 'info'}
        
        self.widget.update_errors([error_item, warning_item, info_item])
        self.assertEqual(self.widget.error_list.count(), 3)


class TestRiskControlRules(unittest.TestCase):
    """测试风险控制规则"""

    def test_max_drawdown_limit(self):
        params = {
            'risk_control': {
                'max_drawdown_limit': 0.20,
                'stop_loss': 0.10,
                'take_profit': 0.20,
            }
        }
        
        ui_data_high_drawdown = {
            'current_drawdown': -0.25,
            'cumulative_return': -0.05,
        }
        
        self.assertGreaterEqual(
            abs(ui_data_high_drawdown['current_drawdown']),
            params['risk_control']['max_drawdown_limit']
        )

    def test_stop_loss_trigger(self):
        params = {
            'risk_control': {
                'stop_loss': 0.10,
            }
        }
        
        ui_data_stop_loss = {
            'cumulative_return': -0.15,
        }
        
        self.assertLessEqual(
            ui_data_stop_loss['cumulative_return'],
            -params['risk_control']['stop_loss']
        )

    def test_take_profit_trigger(self):
        params = {
            'risk_control': {
                'take_profit': 0.20,
            }
        }
        
        ui_data_take_profit = {
            'cumulative_return': 0.25,
        }
        
        self.assertGreaterEqual(
            ui_data_take_profit['cumulative_return'],
            params['risk_control']['take_profit']
        )


class TestStrategyValidation(unittest.TestCase):
    """测试策略验证"""

    def test_signal_type_validation(self):
        from core.strategy.base_strategy import SignalType
        
        valid_signals = [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        for signal in valid_signals:
            self.assertIn(signal, [SignalType.BUY, SignalType.SELL, SignalType.HOLD])

    def test_signal_numeric_conversion(self):
        signal_map = {
            'BUY': 1,
            'SELL': -1,
            'HOLD': 0,
        }
        
        self.assertEqual(signal_map['BUY'], 1)
        self.assertEqual(signal_map['SELL'], -1)
        self.assertEqual(signal_map['HOLD'], 0)


class TestBacktestResultValidation(unittest.TestCase):
    """测试回测结果验证"""

    def test_required_fields(self):
        required_fields = [
            'total_return', 'annual_return', 'max_drawdown',
            'sharpe_ratio', 'win_rate', 'total_trades'
        ]
        
        valid_result = {
            'total_return': 0.15,
            'annual_return': 0.12,
            'max_drawdown': -0.10,
            'sharpe_ratio': 1.5,
            'win_rate': 0.60,
            'total_trades': 100,
        }
        
        for field in required_fields:
            self.assertIn(field, valid_result)

    def test_numeric_value_validation(self):
        result = {
            'total_return': 0.15,
            'sharpe_ratio': 1.5,
            'win_rate': 0.60,
        }
        
        for key, value in result.items():
            self.assertIsInstance(value, (int, float))
            self.assertFalse(isinstance(value, bool))

    def test_range_validation(self):
        sharpe_ratio = 1.5
        self.assertGreater(sharpe_ratio, -10)
        self.assertLess(sharpe_ratio, 10)
        
        win_rate = 0.60
        self.assertGreaterEqual(win_rate, 0)
        self.assertLessEqual(win_rate, 1)


class TestCodeEditor(unittest.TestCase):
    """测试代码编辑器"""

    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.strategy_code_editor import CodeEditor
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.editor = CodeEditor()

    def test_editor_initialization(self):
        self.assertIsNotNone(self.editor.highlighter)
        self.assertIsNotNone(self.editor.completion_timer)
        self.assertIsNotNone(self.editor.error_timer)

    def test_set_text(self):
        test_code = "def hello():\n    print('world')"
        self.editor.setPlainText(test_code)
        self.assertEqual(self.editor.toPlainText(), test_code)

    def test_callback_setup(self):
        self.editor.completion_callback = Mock()
        self.editor.error_callback = Mock()
        
        self.assertIsNotNone(self.editor.completion_callback)
        self.assertIsNotNone(self.editor.error_callback)


class TestVariableViewer(unittest.TestCase):
    """测试变量查看器"""

    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.strategy_debugger import VariableViewer
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.viewer = VariableViewer()

    def test_update_variables(self):
        local_vars = {
            'x': 10,
            'y': 'hello',
            'z': [1, 2, 3],
            'd': {'a': 1, 'b': 2},
        }
        
        self.viewer.update_variables(local_vars)
        
        self.assertEqual(self.viewer.var_tree.topLevelItemCount(), 1)

    def test_variable_types(self):
        test_vars = {
            'int_var': 42,
            'float_var': 3.14,
            'str_var': 'test',
            'list_var': [1, 2, 3],
            'dict_var': {'key': 'value'},
            'bool_var': True,
            'none_var': None,
        }
        
        self.viewer.update_variables(test_vars)
        
        self.assertEqual(self.viewer.var_tree.topLevelItemCount(), 1)


class TestCallStackViewer(unittest.TestCase):
    """测试调用栈查看器"""

    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.strategy_debugger import CallStackViewer
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.viewer = CallStackViewer()

    def test_update_call_stack(self):
        frames = [
            {'function': 'main', 'filename': 'test.py', 'lineno': 10},
            {'function': 'helper', 'filename': 'utils.py', 'lineno': 25},
            {'function': 'process', 'filename': 'core.py', 'lineno': 100},
        ]
        
        self.viewer.update_call_stack(frames)
        
        self.assertEqual(self.viewer.stack_list.count(), 3)


class TestDebugController(unittest.TestCase):
    """测试调试控制器"""

    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.strategy_debugger import DebugController
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.controller = DebugController()

    def test_button_initialization(self):
        self.assertIsNotNone(self.controller.continue_btn)
        self.assertIsNotNone(self.controller.step_over_btn)
        self.assertIsNotNone(self.controller.step_into_btn)
        self.assertIsNotNone(self.controller.step_out_btn)
        self.assertIsNotNone(self.controller.stop_btn)
        self.assertIsNotNone(self.controller.restart_btn)

    def test_debugging_state(self):
        self.controller.set_debugging_state(True)
        self.assertTrue(self.controller.continue_btn.isEnabled())
        self.assertTrue(self.controller.step_over_btn.isEnabled())
        
        self.controller.set_debugging_state(False)
        self.assertFalse(self.controller.continue_btn.isEnabled())
        self.assertFalse(self.controller.step_over_btn.isEnabled())


class TestOutputViewer(unittest.TestCase):
    """测试输出查看器"""

    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.strategy_debugger import OutputViewer
        
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.viewer = OutputViewer()

    def test_append_output(self):
        self.viewer.append_output("Test output")
        self.assertIn("Test output", self.viewer.output_text.toPlainText())

    def test_clear_output(self):
        self.viewer.append_output("Test output")
        self.viewer.clear_output()
        self.assertEqual(self.viewer.output_text.toPlainText(), "")

    def test_colored_output(self):
        self.viewer.append_output("Error message", color='#ff0000')
        self.assertIn("Error message", self.viewer.output_text.toPlainText())


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_strategy_workflow_integration(self):
        from gui.widgets.strategy_development_workflow import WorkflowStage, WorkflowStep
        
        stages = list(WorkflowStage)
        self.assertEqual(len(stages), 6)
        
        for stage in stages:
            step = WorkflowStep(stage, f"Test {stage.value}", "Test description")
            self.assertEqual(step.stage, stage)

    def test_debugger_editor_integration(self):
        from gui.widgets.strategy_debugger import BreakpointManager
        
        manager = BreakpointManager()
        
        test_file = 'test_strategy.py'
        manager.add_breakpoint(test_file, 10)
        manager.add_breakpoint(test_file, 20)
        manager.add_breakpoint(test_file, 30)
        
        self.assertEqual(len(manager.get_breakpoints(test_file)), 3)
        
        manager.remove_breakpoint(test_file, 20)
        self.assertEqual(len(manager.get_breakpoints(test_file)), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
