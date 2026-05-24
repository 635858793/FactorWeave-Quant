#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复验证测试脚本（简化版）

使用语法检查和文件验证来避免完整导入的崩溃问题
"""

import sys
import os
import ast
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, test_name: str, detail: str = ""):
        self.passed.append((test_name, detail))
    
    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
    
    def add_warning(self, test_name: str, warning: str):
        self.warnings.append((test_name, warning))
    
    def print_report(self):
        print("\n" + "="*80)
        print("修复验证测试报告")
        print("="*80)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"项目路径: {project_root}")
        print("="*80)
        
        if self.passed:
            print(f"\n✅ 通过的测试 ({len(self.passed)}):")
            print("-" * 80)
            for name, detail in self.passed:
                print(f"  ✓ {name}")
                if detail:
                    print(f"    {detail}")
        
        if self.warnings:
            print(f"\n⚠️  警告 ({len(self.warnings)}):")
            print("-" * 80)
            for name, warning in self.warnings:
                print(f"  ⚠ {name}")
                print(f"    {warning}")
        
        if self.failed:
            print(f"\n❌ 失败的测试 ({len(self.failed)}):")
            print("-" * 80)
            for name, error in self.failed:
                print(f"  ✗ {name}")
                print(f"    错误: {error}")
        
        print("\n" + "="*80)
        total = len(self.passed) + len(self.failed)
        print(f"测试总结: {len(self.passed)}/{total} 通过, {len(self.failed)}/{total} 失败, {len(self.warnings)} 警告")
        
        if self.failed:
            print("状态: ❌ 部分测试失败")
        elif self.warnings:
            print("状态: ⚠️  全部通过,但有警告")
        else:
            print("状态: ✅ 全部通过")
        print("="*80 + "\n")
        
        return len(self.failed) == 0


def verify_file_exists(file_path: str) -> bool:
    """验证文件是否存在"""
    path = project_root / file_path
    exists = path.exists()
    if exists:
        print(f"  ✓ 文件存在: {file_path}")
    else:
        print(f"  ✗ 文件不存在: {file_path}")
    return exists


def verify_class_in_file(file_path: str, class_name: str) -> bool:
    """验证文件中是否定义了指定的类"""
    path = project_root / file_path
    if not path.exists():
        print(f"  ✗ 文件不存在: {file_path}")
        return False
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                print(f"  ✓ 找到类定义: {class_name} (位于 {file_path}:{node.lineno})")
                return True
        
        print(f"  ✗ 未找到类定义: {class_name} (在 {file_path})")
        return False
    except Exception as e:
        print(f"  ✗ 解析文件失败: {file_path} - {e}")
        return False


def verify_function_in_file(file_path: str, function_name: str) -> bool:
    """验证文件中是否定义了指定的函数"""
    path = project_root / file_path
    if not path.exists():
        print(f"  ✗ 文件不存在: {file_path}")
        return False
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                print(f"  ✓ 找到函数定义: {function_name} (位于 {file_path}:{node.lineno})")
                return True
        
        print(f"  ✗ 未找到函数定义: {function_name} (在 {file_path})")
        return False
    except Exception as e:
        print(f"  ✗ 解析文件失败: {file_path} - {e}")
        return False


def verify_no_qtwidgets_animation_import(file_path: str) -> bool:
    """验证没有从 PyQt5.QtWidgets 错误导入动画类"""
    path = project_root / file_path
    if not path.exists():
        print(f"  ✗ 文件不存在: {file_path}")
        return False
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        has_error = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and 'QtWidgets' in node.module:
                    for alias in node.names:
                        if alias.name in ['QPropertyAnimation', 'QEasingCurve']:
                            print(f"  ✗ 错误导入: {alias.name} 从 {node.module} 导入")
                            has_error = True
        
        if not has_error:
            print(f"  ✓ 导入检查通过: {file_path}")
        
        return not has_error
    except Exception as e:
        print(f"  ✗ 解析文件失败: {file_path} - {e}")
        return False


def test_coordinators(result: TestResult):
    """测试1: 验证所有 Coordinator 导入"""
    print("\n" + "="*80)
    print("测试 1: 验证 Coordinator 文件与类定义")
    print("="*80)
    
    coordinators = {
        'core/coordinators/panel_coordinator.py': 'PanelCoordinator',
        'core/coordinators/event_coordinator.py': 'EventCoordinator',
        'core/coordinators/dialog_coordinator.py': 'DialogCoordinator',
        'core/coordinators/theme_coordinator.py': 'ThemeCoordinator',
        'core/coordinators/main_window_coordinator.py': 'MainWindowCoordinator',
    }
    
    for file_path, class_name in coordinators.items():
        file_exists = verify_file_exists(file_path)
        class_exists = verify_class_in_file(file_path, class_name)
        no_bad_import = verify_no_qtwidgets_animation_import(file_path)
        
        if file_exists and class_exists and no_bad_import:
            result.add_pass(f"{class_name}", f"文件存在, 类定义正确, 导入检查通过")
        else:
            result.add_fail(f"{class_name}", f"验证失败")
    
    # 验证 __init__.py
    init_path = 'core/coordinators/__init__.py'
    if verify_file_exists(init_path):
        try:
            with open(project_root / init_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            all_coordinators = ['PanelCoordinator', 'EventCoordinator', 'DialogCoordinator', 'ThemeCoordinator', 'MainWindowCoordinator']
            all_present = all(name in content for name in all_coordinators)
            
            if all_present:
                result.add_pass("coordinators.__init__", "所有协调器已正确导出")
                print("  ✓ __init__.py 包含所有协调器导出")
            else:
                result.add_fail("coordinators.__init__", "缺少部分协调器导出")
                print("  ✗ __init__.py 缺少部分协调器导出")
        except Exception as e:
            result.add_fail("coordinators.__init__", str(e))


def test_dialogs(result: TestResult):
    """测试2: 验证新的对话框导入"""
    print("\n" + "="*80)
    print("测试 2: 验证对话框文件与类定义")
    print("="*80)
    
    dialogs = {
        'gui/dialogs/strategy_manager_dialog.py': 'StrategyManagerDialog',
        'gui/dialogs/plugin_manager_dialog_unified.py': 'PluginManagerDialogUnified',
        'gui/dialogs/data_management_dialog_unified.py': 'UnifiedDataManagementDialog',
        'gui/dialogs/base_dialog.py': 'BaseDialog',
    }
    
    for file_path, class_name in dialogs.items():
        file_exists = verify_file_exists(file_path)
        class_exists = verify_class_in_file(file_path, class_name)
        no_bad_import = verify_no_qtwidgets_animation_import(file_path)
        
        if file_exists and class_exists and no_bad_import:
            result.add_pass(f"{class_name}", f"文件存在, 类定义正确, 导入检查通过")
        else:
            result.add_fail(f"{class_name}", f"验证失败")
    
    # 验证 __init__.py
    init_path = 'gui/dialogs/__init__.py'
    if verify_file_exists(init_path):
        try:
            with open(project_root / init_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            all_dialogs = ['StrategyManagerDialog', 'PluginManagerDialogUnified', 'UnifiedDataManagementDialog', 'BaseDialog']
            all_present = all(name in content for name in all_dialogs)
            
            if all_present:
                result.add_pass("dialogs.__init__", "所有对话框已正确导出")
                print("  ✓ __init__.py 包含所有对话框导出")
            else:
                result.add_fail("dialogs.__init__", "缺少部分对话框导出")
                print("  ✗ __init__.py 缺少部分对话框导出")
        except Exception as e:
            result.add_fail("dialogs.__init__", str(e))


def test_unified_sqlite_access(result: TestResult):
    """测试3: 验证 UnifiedSQLiteAccess 导入"""
    print("\n" + "="*80)
    print("测试 3: 验证 UnifiedSQLiteAccess 文件与定义")
    print("="*80)
    
    file_path = 'core/database/unified_sqlite_access.py'
    
    if verify_file_exists(file_path):
        class_exists = verify_class_in_file(file_path, 'UnifiedSQLiteAccess')
        get_db_exists = verify_function_in_file(file_path, 'get_db')
        execute_query_exists = verify_function_in_file(file_path, 'execute_query')
        execute_write_exists = verify_function_in_file(file_path, 'execute_write')
        
        if class_exists and get_db_exists and execute_query_exists and execute_write_exists:
            result.add_pass("UnifiedSQLiteAccess", "类定义及便捷函数均正确")
        else:
            result.add_fail("UnifiedSQLiteAccess", "部分定义缺失")


def test_order_executor(result: TestResult):
    """测试4: 验证 order_executor 导入"""
    print("\n" + "="*80)
    print("测试 4: 验证 order_executor 文件与定义")
    print("="*80)
    
    file_path = 'core/trading/order_executor.py'
    
    if verify_file_exists(file_path):
        class_exists = verify_class_in_file(file_path, 'OrderExecutor')
        mock_exists = verify_class_in_file(file_path, 'MockTradingInterface')
        
        if class_exists and mock_exists:
            result.add_pass("OrderExecutor", "类定义正确")
        else:
            result.add_fail("OrderExecutor", "类定义缺失")
    
    # 验证 order_models
    models_path = 'core/trading/order_models.py'
    if verify_file_exists(models_path):
        models = ['Order', 'OrderType', 'OrderStatus', 'OrderCategory']
        all_exist = True
        for model in models:
            if not verify_class_in_file(models_path, model):
                all_exist = False
        
        if all_exist:
            result.add_pass("order_models", "所有订单模型定义正确")
        else:
            result.add_fail("order_models", "部分模型定义缺失")


def test_db_utils(result: TestResult):
    """测试5: 验证 db_utils 导入"""
    print("\n" + "="*80)
    print("测试 5: 验证 db_utils 文件与定义")
    print("="*80)
    
    # 测试 core.services.db_utils
    file_path = 'core/services/db_utils.py'
    if verify_file_exists(file_path):
        configure_exists = verify_function_in_file(file_path, 'configure_connection')
        create_exists = verify_function_in_file(file_path, 'create_configured_connection')
        
        if configure_exists and create_exists:
            result.add_pass("core.services.db_utils", "函数定义正确")
        else:
            result.add_fail("core.services.db_utils", "函数定义缺失")
    
    # 测试 core.utils.database_utils
    utils_path = 'core/utils/database_utils.py'
    if verify_file_exists(utils_path):
        functions = ['validate_stock_code', 'format_stock_code', 'get_market_code', 
                     'build_insert_query', 'build_update_query', 'optimize_database']
        all_exist = True
        for func in functions:
            if not verify_function_in_file(utils_path, func):
                all_exist = False
        
        if all_exist:
            result.add_pass("core.utils.database_utils", "所有工具函数定义正确")
        else:
            result.add_fail("core.utils.database_utils", "部分函数定义缺失")


def main():
    """主测试函数"""
    print("\n" + "🔍" * 40)
    print("开始修复验证测试...")
    print("🔍" * 40)
    
    result = TestResult()
    
    test_coordinators(result)
    test_dialogs(result)
    test_unified_sqlite_access(result)
    test_order_executor(result)
    test_db_utils(result)
    
    success = result.print_report()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
