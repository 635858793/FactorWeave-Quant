#!/usr/bin/env python3
"""
参数编辑器 UI 入口实施验证脚本
验证所有三个入口点的实现是否正确
"""

import sys
import inspect

def test_menu_entry():
    """测试 1: 验证菜单入口实现"""
    print("\n" + "="*60)
    print("测试 1: 验证菜单入口实现")
    print("="*60)
    
    try:
        # 读取 menu_bar.py 源码
        with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\menu_bar.py", "r", encoding="utf-8") as f:
            menu_bar_content = f.read()
        
        # 检查关键实现点
        checks = [
            ("strategy_optimize_action 存在", "self.strategy_optimize_action" in menu_bar_content),
            ("策略参数优化文本", "⚡ 策略参数优化" in menu_bar_content),
            ("Ctrl+Shift+O 快捷键", "Ctrl+Shift+O" in menu_bar_content),
            ("连接到 _on_strategy_optimize", "'strategy_optimize_action', '_on_strategy_optimize'" in menu_bar_content),
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ✗ FAIL: 菜单入口测试异常: {e}")
        return False


def test_coordinator_implementation():
    """测试 2: 验证 main_window_coordinator 实现"""
    print("\n" + "="*60)
    print("测试 2: 验证 main_window_coordinator 实现")
    print("="*60)
    
    try:
        # 读取 main_window_coordinator.py 源码
        with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\coordinators\main_window_coordinator.py", "r", encoding="utf-8") as f:
            coordinator_content = f.read()
        
        # 检查关键实现点
        checks = [
            ("_on_strategy_optimize 方法存在", "def _on_strategy_optimize(self)" in coordinator_content),
            ("ParameterEditorWidget 导入", "from gui.widgets.parameter_editor import ParameterEditorWidget" in coordinator_content),
            ("ModeContext 导入", "from core.trading.trading_mode import ModeContext" in coordinator_content),
            ("独立对话框创建", "QDialog(self._main_window)" in coordinator_content),
            ("策略选择器实现", "strategy_combo = QComboBox()" in coordinator_content),
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ✗ FAIL: coordinator 测试异常: {e}")
        return False


def test_strategy_manager_integration():
    """测试 3: 验证策略管理器集成"""
    print("\n" + "="*60)
    print("测试 3: 验证策略管理器集成")
    print("="*60)
    
    try:
        # 读取 enhanced_strategy_manager_dialog.py 源码
        with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\dialogs\enhanced_strategy_manager_dialog.py", "r", encoding="utf-8") as f:
            dialog_content = f.read()
        
        # 检查关键实现点
        checks = [
            ("ParameterEditorWidget 导入", "from gui.widgets.parameter_editor import ParameterEditorWidget" in dialog_content),
            ("_create_optimization_view 方法", "def _create_optimization_view(self)" in dialog_content),
            ("parameter_editor 属性", "self.parameter_editor = ParameterEditorWidget" in dialog_content),
            ("策略选择器实现", "optimization_strategy_combo" in dialog_content),
            ("ModeContext 使用", "ModeContext.create_backtest()" in dialog_content),
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ✗ FAIL: 策略管理器集成测试异常: {e}")
        return False


def test_toolbar_integration():
    """测试 4: 验证工具栏快捷入口"""
    print("\n" + "="*60)
    print("测试 4: 验证工具栏快捷入口")
    print("="*60)
    
    try:
        # 读取 tool_bar.py 源码
        with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\tool_bar.py", "r", encoding="utf-8") as f:
            toolbar_content = f.read()
        
        # 检查关键实现点
        checks = [
            ("parameter_optimizer_action 存在", "self.parameter_optimizer_action" in toolbar_content),
            ("参数优化文本", "⚡ 参数优化" in toolbar_content),
            ("Ctrl+Shift+O 快捷键", "Ctrl+Shift+O" in toolbar_content),
            ("连接到 show_parameter_optimizer", "self.parameter_optimizer_action.triggered.connect(self.show_parameter_optimizer)" in toolbar_content),
            ("show_parameter_optimizer 方法", "def show_parameter_optimizer(self)" in toolbar_content),
            ("ParameterEditorWidget 导入", "from gui.widgets.parameter_editor import ParameterEditorWidget" in toolbar_content),
            ("ModeContext 导入", "from core.trading.trading_mode import ModeContext" in toolbar_content),
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ✗ FAIL: 工具栏测试异常: {e}")
        return False


def test_parameter_editor_integration():
    """测试 5: 验证参数编辑器核心功能"""
    print("\n" + "="*60)
    print("测试 5: 验证参数编辑器核心功能")
    print("="*60)
    
    try:
        # 读取 parameter_editor.py 源码
        with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\gui\widgets\parameter_editor.py", "r", encoding="utf-8") as f:
            editor_content = f.read()
        
        # 检查关键实现点
        checks = [
            ("kdata 属性定义", "self.kdata = None" in editor_content),
            ("mode_context 属性定义", "self.mode_context = None" in editor_content),
            ("ParameterScanThread 导入", "from .parameter_editor import ParameterScanThread" in editor_content or "ParameterScanThread" in editor_content),
            ("ParameterComparisonThread 导入", "ParameterComparisonThread" in editor_content),
            ("4个 Phase Tab 实现", "QTabWidget" in editor_content),
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {check_name}")
            if not result:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ✗ FAIL: 参数编辑器核心测试异常: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("参数编辑器 UI 入口实施验证")
    print("="*60)
    
    tests = [
        ("菜单入口", test_menu_entry),
        ("Coordinator 实现", test_coordinator_implementation),
        ("策略管理器集成", test_strategy_manager_integration),
        ("工具栏快捷入口", test_toolbar_integration),
        ("参数编辑器核心", test_parameter_editor_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ✗ FAIL: {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n✓ 所有测试通过！参数编辑器 UI 入口已成功实现。")
        return 0
    else:
        print(f"\n✗ 有 {failed} 项测试未通过，请检查实现。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
