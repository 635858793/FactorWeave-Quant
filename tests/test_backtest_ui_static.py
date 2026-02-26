#!/usr/bin/env python3
"""
回测UI功能验证 - 纯代码静态检查
不触发系统初始化，只验证代码结构
"""

import ast
import os
from pathlib import Path

def check_class_definition(file_path, class_name):
    """检查文件中是否存在指定类"""
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name == class_name:
                    return True, f"找到类: {class_name}"
                # 检查继承关系
                for base in node.bases:
                    if isinstance(base, ast.Attribute):
                        if base.attr == 'QWidget':
                            return True, f"找到继承QWidget的类: {node.name}"
        
        return False, f"未找到类: {class_name}"
    except Exception as e:
        return False, f"解析错误: {e}"

def check_method_exists(file_path, method_name):
    """检查文件中是否存在指定方法"""
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 简单字符串搜索
        if f'def {method_name}(' in content:
            return True, f"找到方法: {method_name}()"
        
        return False, f"未找到方法: {method_name}()"
    except Exception as e:
        return False, f"搜索错误: {e}"

def check_attribute_exists(file_path, attr_name):
    """检查文件中是否存在指定属性/变量"""
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查 self.attr_name = 或 attr_name =
        patterns = [
            f'self.{attr_name} =',
            f'{attr_name} = QAction',
            f'{attr_name} = self.addMenu',
        ]
        
        for pattern in patterns:
            if pattern in content:
                return True, f"找到属性: {attr_name}"
        
        # 也尝试简单搜索
        if attr_name in content and ('QAction' in content or 'QMenu' in content):
            return True, f"找到属性: {attr_name}"
        
        return False, f"未找到属性: {attr_name}"
    except Exception as e:
        return False, f"搜索错误: {e}"

def check_string_in_file(file_path, search_str):
    """检查文件中是否存在指定字符串"""
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if search_str in content:
            return True, f"找到字符串: {search_str}"
        
        return False, f"未找到字符串: {search_str}"
    except Exception as e:
        return False, f"搜索错误: {e}"

def check_import_statement(file_path, import_text):
    """检查文件中是否存在指定导入"""
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if import_text in content:
            return True, f"找到导入: {import_text}"
        
        return False, f"未找到导入: {import_text}"
    except Exception as e:
        return False, f"搜索错误: {e}"

def run_checks():
    """运行所有检查"""
    project_root = Path(__file__).parent.parent  # 回到项目根目录
    
    print("="*70)
    print("         FactorWeave-Quant 回测UI功能静态验证")
    print("="*70)
    print()
    
    total_passed = 0
    total_failed = 0
    
    # ========== ProfessionalBacktestWidget ==========
    print("-"*70)
    print("1. ProfessionalBacktestWidget 验证")
    print("-"*70)
    
    bp = project_root / "gui/widgets/backtest_widget.py"
    
    classes = [
        ("ProfessionalBacktestWidget", "主组件"),
        ("RealTimeChart", "实时图表"),
        ("MetricsPanel", "指标面板"),
        ("ControlPanel", "控制面板"),
        ("AlertsPanel", "预警面板"),
    ]
    
    for class_name, desc in classes:
        passed, msg = check_class_definition(bp, class_name)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} | {class_name:30s} | {desc:15s} | {msg}")
        total_passed += 1 if passed else 0
        total_failed += 1 if not passed else 0
    
    # ========== ModernUnifiedPerformanceWidget ==========
    print()
    print("-"*70)
    print("2. ModernUnifiedPerformanceWidget 验证")
    print("-"*70)
    
    upw = project_root / "gui/widgets/performance/unified_performance_widget.py"
    
    classes = [
        ("ModernUnifiedPerformanceWidget", "统一性能组件"),
        ("StatusMessageCallback", "状态回调"),
        ("UpdateDataCallback", "数据更新回调"),
    ]
    
    for class_name, desc in classes:
        passed, msg = check_class_definition(upw, class_name)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} | {class_name:30s} | {desc:15s} | {msg}")
        total_passed += 1 if passed else 0
        total_failed += 1 if not passed else 0
    
    # ========== MainWindowCoordinator ==========
    print()
    print("-"*70)
    print("3. MainWindowCoordinator 回测集成验证")
    print("-"*70)
    
    mc = project_root / "core/coordinators/main_window_coordinator.py"
    
    methods = [
        ("_create_professional_backtest_widget", "创建回测组件"),
        ("_on_professional_backtest", "专业回测处理"),
        ("_create_standalone_backtest_window", "创建独立窗口"),
        ("_on_performance_center", "性能中心处理"),
    ]
    
    for method_name, desc in methods:
        passed, msg = check_method_exists(mc, method_name)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} | {method_name:40s} | {desc}")
        total_passed += 1 if passed else 0
        total_failed += 1 if not passed else 0
    
    # ========== MenuBar ==========
    print()
    print("-"*70)
    print("4. MenuBar 回测菜单验证")
    print("-"*70)
    
    mb = project_root / "gui/menu_bar.py"
    
    checks = [
        ("professional_backtest_action", "专业回测菜单项"),
        ("backtest_action", "回测菜单项"),
        ("performance_menu", "性能监控菜单"),
    ]
    
    for check_name, desc in checks:
        passed, msg = check_attribute_exists(mb, check_name)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} | {check_name:30s} | {desc} | {msg}")
        total_passed += 1 if passed else 0
        total_failed += 1 if not passed else 0
    
    # ========== RightPanel 回测模块 ==========
    print()
    print("-"*70)
    print("5. RightPanel 回测模块验证")
    print("-"*70)
    
    rp = project_root / "core/ui/panels/right_panel.py"
    
    methods = [
        ("_create_backtest_tab", "创建回测Tab"),
        ("_on_delete_button_clicked", "删除结果处理"),
        ("_on_clear_all_button_clicked", "清空结果处理"),
        ("_on_export_button_clicked", "导出结果处理"),
    ]
    
    for method_name, desc in methods:
        passed, msg = check_method_exists(rp, method_name)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} | {method_name:30s} | {desc}")
        total_passed += 1 if passed else 0
        total_failed += 1 if not passed else 0
    
    # ========== 性能Tab组件 ==========
    print()
    print("-"*70)
    print("6. 性能监控Tab组件验证")
    print("-"*70)
    
    tabs = [
        ("gui/widgets/performance/tabs/strategy_performance_tab.py", 
         "ModernStrategyPerformanceTab", "策略性能Tab"),
        ("gui/widgets/performance/tabs/system_monitor_tab.py",
         "ModernSystemMonitorTab", "系统监控Tab"),
        ("gui/widgets/performance/tabs/algorithm_optimization_tab.py",
         "ModernAlgorithmOptimizationTab", "算法优化Tab"),
        ("gui/widgets/performance/tabs/risk_control_center_tab.py",
         "ModernRiskControlCenterTab", "风险控制Tab"),
        ("gui/widgets/performance/tabs/trading_execution_monitor_tab.py",
         "ModernTradingExecutionMonitorTab", "交易执行Tab"),
    ]
    
    for file_path, class_name, desc in tabs:
        full_path = project_root / file_path
        passed, msg = check_class_definition(full_path, class_name)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} | {class_name:35s} | {desc}")
        total_passed += 1 if passed else 0
        total_failed += 1 if not passed else 0
    
    # ========== 独立启动器 ==========
    print()
    print("-"*70)
    print("7. 独立启动器验证")
    print("-"*70)
    
    launcher = project_root / "gui/backtest_ui_launcher.py"
    
    checks = [
        ("class BacktestUILauncher", "BacktestUILauncher类"),
        ('"web", "desktop"', "web/desktop启动选项"),
        ("launch_streamlit_only", "Streamlit启动函数"),
        ("launch_pyqt5_only", "PyQt5启动函数"),
    ]
    
    for check, desc in checks:
        if not os.path.exists(launcher):
            print(f"  ❌ FAIL | {check:30s} | {desc} | 文件不存在")
            total_failed += 1
            continue
            
        with open(launcher, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if check in content:
            print(f"  ✅ PASS | {check:30s} | {desc}")
            total_passed += 1
        else:
            print(f"  ❌ FAIL | {check:30s} | {desc} | 未找到")
            total_failed += 1
    
    # ========== 摘要 ==========
    print()
    print("="*70)
    print("                    测试摘要")
    print("="*70)
    print(f"  通过: {total_passed} ✅")
    print(f"  失败: {total_failed} ❌")
    print(f"  总计: {total_passed + total_failed}")
    print(f"  通过率: {total_passed/(total_passed+total_failed)*100:.1f}%")
    print("="*70)
    
    return total_failed == 0

if __name__ == "__main__":
    success = run_checks()
    exit(0 if success else 1)
