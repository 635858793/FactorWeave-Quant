"""
静态回归测试脚本

测试修复后的功能（不运行时创建实例）：
1. MainWindowCoordinator 编译
2. panel_padding 配置存在
3. MiddlePanel 编译
4. 没有 get_stock_list 方法
"""

import ast
import sys

def test_main_window_coordinator_compilation():
    """测试 MainWindowCoordinator 编译"""
    print("\n测试 1: MainWindowCoordinator 编译")
    
    try:
        with open('core/coordinators/main_window_coordinator.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        ast.parse(code)
        print("✓ MainWindowCoordinator 编译成功")
        return True
    except SyntaxError as e:
        print(f"✗ MainWindowCoordinator 编译失败: {e}")
        return False

def test_middle_panel_compilation():
    """测试 MiddlePanel 编译"""
    print("\n测试 2: MiddlePanel 编译")
    
    try:
        with open('core/ui/panels/middle_panel.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        ast.parse(code)
        print("✓ MiddlePanel 编译成功")
        return True
    except SyntaxError as e:
        print(f"✗ MiddlePanel 编译失败: {e}")
        return False

def test_single_init_method():
    """测试只有一个 __init__ 方法"""
    print("\n测试 3: MainWindowCoordinator 只有一个 __init__ 方法")
    
    try:
        with open('core/coordinators/main_window_coordinator.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        tree = ast.parse(code)
        
        # 找到 MainWindowCoordinator 类
        main_window_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'MainWindowCoordinator':
                main_window_class = node
                break
        
        if main_window_class is None:
            print("✗ 未找到 MainWindowCoordinator 类")
            return False
        
        # 检查 MainWindowCoordinator 类的直接 __init__ 方法（不包括嵌套类）
        init_methods = []
        for node in main_window_class.body:
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                init_methods.append(node.lineno)
        
        print(f"  MainWindowCoordinator 中找到 {len(init_methods)} 个 __init__ 方法")
        for lineno in init_methods:
            print(f"    - 第 {lineno} 行")
        
        if len(init_methods) == 1:
            print("✓ MainWindowCoordinator 只有一个 __init__ 方法")
            return True
        else:
            print(f"✗ MainWindowCoordinator 有 {len(init_methods)} 个 __init__ 方法（应该只有1个）")
            return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

def test_panel_padding_exists():
    """测试 panel_padding 配置存在"""
    print("\n测试 4: panel_padding 配置存在")
    
    try:
        with open('core/coordinators/main_window_coordinator.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        if "'panel_padding'" in code or '"panel_padding"' in code:
            print("✓ panel_padding 配置存在")
            
            # 检查是否被注释
            lines = code.split('\n')
            for i, line in enumerate(lines, 1):
                if "'panel_padding'" in line or '"panel_padding"' in line:
                    if line.strip().startswith('#'):
                        print(f"  警告: panel_padding 在第 {i} 行被注释")
                        return False
                    else:
                        print(f"  panel_padding 在第 {i} 行启用")
                        return True
        else:
            print("✗ panel_padding 配置不存在")
            return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

def test_no_get_stock_list_call():
    """测试没有调用 get_stock_list"""
    print("\n测试 5: 没有 get_stock_list 调用")
    
    try:
        with open('core/ui/panels/middle_panel.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        if 'get_stock_list' in code:
            print("✗ middle_panel.py 中仍有 get_stock_list 调用")
            
            # 显示所有出现的位置
            lines = code.split('\n')
            for i, line in enumerate(lines, 1):
                if 'get_stock_list' in line:
                    print(f"  第 {i} 行: {line.strip()}")
            
            return False
        else:
            print("✓ middle_panel.py 中没有 get_stock_list 调用")
            return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

def test_type_annotations():
    """测试类型注解存在"""
    print("\n测试 6: __init__ 方法有类型注解")
    
    try:
        with open('core/coordinators/main_window_coordinator.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                # 检查参数是否有类型注解
                has_annotations = any(arg.annotation is not None for arg in node.args.args)
                
                if has_annotations:
                    print("✓ __init__ 方法有类型注解")
                    return True
                else:
                    print("✗ __init__ 方法没有类型注解")
                    return False
        
        print("✗ 未找到 __init__ 方法")
        return False
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("开始静态回归测试")
    print("="*60)
    
    tests = [
        ("MainWindowCoordinator 编译", test_main_window_coordinator_compilation),
        ("MiddlePanel 编译", test_middle_panel_compilation),
        ("只有一个 __init__ 方法", test_single_init_method),
        ("panel_padding 配置存在", test_panel_padding_exists),
        ("没有 get_stock_list 调用", test_no_get_stock_list_call),
        ("__init__ 方法有类型注解", test_type_annotations),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ 测试 '{test_name}' 发生异常: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("回归测试结果汇总")
    print("="*60)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-"*60)
    print(f"总计: {len(results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print("-"*60)
    
    if failed == 0:
        print("\n✓✓✓ 所有静态回归测试通过 ✓✓✓")
        sys.exit(0)
    else:
        print(f"\n✗✗✗ 有 {failed} 个测试失败 ✗✗✗")
        sys.exit(1)
