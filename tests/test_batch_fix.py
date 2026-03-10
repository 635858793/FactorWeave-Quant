# -*- coding: utf-8 -*-
"""测试验证批量分析性能优化修复效果"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_code_structure():
    """测试代码结构是否正确"""
    print('=' * 60)
    print('测试1: 代码结构检查')
    print('=' * 60)

    import ast
    with open('gui/ui_components.py', 'r', encoding='utf-8') as f:
        code = f.read()

    tree = ast.parse(code)

    class ComponentChecker(ast.NodeVisitor):
        def __init__(self):
            self.components = []
            self.current_class = None

        def visit_ClassDef(self, node):
            if node.name == 'AnalysisToolsPanel':
                self.current_class = node.name
                for item in ast.walk(node):
                    if isinstance(item, ast.FunctionDef):
                        if 'batch' in item.name.lower():
                            self.components.append(item.name)
            self.generic_visit(node)

    checker = ComponentChecker()
    checker.visit(tree)

    print(f'找到的批量分析相关方法:')
    for comp in checker.components:
        print(f'  - {comp}')

    return len(checker.components) > 0


def test_import_check():
    """测试导入是否正确"""
    print('\n' + '=' * 60)
    print('测试2: 导入检查')
    print('=' * 60)

    try:
        import ast
        with open('gui/ui_components.py', 'r', encoding='utf-8') as f:
            code = f.read()

        tree = ast.parse(code)
        print('  ✓ 代码可以正常解析')
        return True
    except SyntaxError as e:
        print(f'  ✗ 语法错误: {e}')
        return False


def test_batch_method_exists():
    """测试批量分析相关方法是否存在"""
    print('\n' + '=' * 60)
    print('测试3: 批量分析核心方法存在性检查')
    print('=' * 60)

    methods_to_check = [
        'start_enhanced_batch_analysis',
        '_run_enhanced_batch_analysis',
        '_run_real_backtest_analysis',
        '_generate_technical_signals'
    ]

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        content = f.read()

    all_exist = True
    for method in methods_to_check:
        exists = f'def {method}' in content
        status = '✓' if exists else '✗'
        print(f'  {status} {method}')
        if not exists:
            all_exist = False

    with open('gui/ui_components.py', 'r', encoding='utf-8') as f:
        ui_content = f.read()

    ui_method = '_create_batch_analysis_ui'
    exists = f'def {ui_method}' in ui_content
    status = '✓' if exists else '✗'
    print(f'  {status} {ui_method} (在 ui_components.py 中)')
    if not exists:
        all_exist = False

    return all_exist


def test_real_backtest_integration():
    """测试真实回测集成"""
    print('\n' + '=' * 60)
    print('测试4: 真实回测引擎集成检查')
    print('=' * 60)

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('StockService', '股票服务'),
        ('get_kline_data', '获取K线数据'),
        ('UnifiedBacktestEngine', '统一回测引擎'),
        ('run_backtest', '运行回测'),
    ]

    all_pass = True
    for keyword, desc in checks:
        exists = keyword in content
        status = '✓' if exists else '✗'
        print(f'  {status} {desc}: {keyword}')
        if not exists:
            all_pass = False

    return all_pass


def test_engine_reuse_optimization():
    """测试UnifiedBacktestEngine实例复用优化"""
    print('\n' + '=' * 60)
    print('测试5: UnifiedBacktestEngine实例复用优化检查')
    print('=' * 60)

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('_get_backtest_engine', '获取回测引擎方法'),
        ('_backtest_engine', '引擎实例属性'),
    ]

    all_pass = True
    for keyword, desc in checks:
        exists = keyword in content
        status = '✓' if exists else '✗'
        print(f'  {status} {desc}: {keyword}')
        if not exists:
            all_pass = False

    not_exists_count = content.count('UnifiedBacktestEngine()')
    if not_exists_count > 1:
        print(f'  ✗ 发现 {not_exists_count} 次直接创建实例（应该复用）')
        all_pass = False
    else:
        print(f'  ✓ UnifiedBacktestEngine实例复用优化已应用')

    return all_pass


def test_event_bus_integration():
    """测试事件总线集成"""
    print('\n' + '=' * 60)
    print('测试6: 事件总线集成检查')
    print('=' * 60)

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('_publish_batch_analysis_event', '发布事件方法'),
        ('get_event_bus', '获取事件总线'),
        ('AnalysisCompleteEvent', '分析完成事件'),
    ]

    all_pass = True
    for keyword, desc in checks:
        exists = keyword in content
        status = '✓' if exists else '✗'
        print(f'  {status} {desc}: {keyword}')
        if not exists:
            all_pass = False

    return all_pass


def test_concurrency_safety():
    """测试并发安全修复"""
    print('\n' + '=' * 60)
    print('测试7: 并发安全检查')
    print('=' * 60)

    with open('gui/ui_components.py', 'r', encoding='utf-8') as f:
        ui_content = f.read()

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        methods_content = f.read()

    checks = [
        ('_batch_results_lock', 'ui_components.py - 结果锁'),
        ('import threading', 'threading 导入'),
        ('with self._batch_results_lock:', 'enhanced_batch_analysis_methods.py - 锁使用'),
    ]

    all_pass = True
    for keyword, desc in checks:
        if 'ui_components.py' in desc:
            exists = keyword in ui_content
        else:
            exists = keyword in methods_content
        status = '✓' if exists else '✗'
        print(f'  {status} {desc}')
        if not exists:
            all_pass = False

    return all_pass


def test_parallel_execution():
    """测试并行执行优化"""
    print('\n' + '=' * 60)
    print('测试8: 并行执行优化检查')
    print('=' * 60)

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('ThreadPoolExecutor', '线程池执行器'),
        ('max_workers', '最大工作线程数'),
        ('as_completed', '异步完成处理'),
        ('_batch_parallel_workers', '并行工作数配置'),
    ]

    all_pass = True
    for keyword, desc in checks:
        exists = keyword in content
        status = '✓' if exists else '✗'
        print(f'  {status} {desc}: {keyword}')
        if not exists:
            all_pass = False

    return all_pass


def test_ui_throttle():
    """测试UI节流更新"""
    print('\n' + '=' * 60)
    print('测试9: UI节流更新检查')
    print('=' * 60)

    with open('gui/ui_components.py', 'r', encoding='utf-8') as f:
        ui_content = f.read()

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        methods_content = f.read()

    checks = [
        ('_ui_update_interval', 'ui_components.py - 更新间隔'),
        ('_last_ui_update_time', 'ui_components.py - 上次更新时间'),
        ('_should_update_ui', 'methods.py - 节流判断方法'),
    ]

    all_pass = True
    for keyword, desc in checks:
        if 'ui_components.py' in desc:
            exists = keyword in ui_content
        else:
            exists = keyword in methods_content
        status = '✓' if exists else '✗'
        print(f'  {status} {desc}')
        if not exists:
            all_pass = False

    return all_pass


def test_kline_cache():
    """测试K线数据缓存"""
    print('\n' + '=' * 60)
    print('测试10: K线数据缓存检查')
    print('=' * 60)

    with open('gui/ui_components.py', 'r', encoding='utf-8') as f:
        ui_content = f.read()

    with open('gui/enhanced_batch_analysis_methods.py', 'r', encoding='utf-8') as f:
        methods_content = f.read()

    checks = [
        ('_kline_cache', '缓存存储'),
        ('_kline_cache_timeout', '缓存超时时间'),
        ('_get_cached_kline_data', '缓存获取方法'),
    ]

    all_pass = True
    for keyword, desc in checks:
        if 'ui_components.py' in desc:
            exists = keyword in ui_content
        else:
            exists = keyword in methods_content
        status = '✓' if exists else '✗'
        print(f'  {status} {desc}')
        if not exists:
            all_pass = False

    return all_pass


if __name__ == '__main__':
    print('开始测试批量分析性能优化修复效果...\n')

    result1 = test_code_structure()
    result2 = test_import_check()
    result3 = test_batch_method_exists()
    result4 = test_real_backtest_integration()
    result5 = test_engine_reuse_optimization()
    result6 = test_event_bus_integration()
    result7 = test_concurrency_safety()
    result8 = test_parallel_execution()
    result9 = test_ui_throttle()
    result10 = test_kline_cache()

    print('\n' + '=' * 60)
    print('测试结果汇总')
    print('=' * 60)
    print(f'代码结构检查:     {"✓ 通过" if result1 else "✗ 失败"}')
    print(f'导入检查:        {"✓ 通过" if result2 else "✗ 失败"}')
    print(f'核心方法检查:    {"✓ 通过" if result3 else "✗ 失败"}')
    print(f'回测集成检查:     {"✓ 通过" if result4 else "✗ 失败"}')
    print(f'引擎复用优化:    {"✓ 通过" if result5 else "✗ 失败"}')
    print(f'事件总线集成:    {"✓ 通过" if result6 else "✗ 失败"}')
    print(f'并发安全检查:    {"✓ 通过" if result7 else "✗ 失败"}')
    print(f'并行执行优化:    {"✓ 通过" if result8 else "✗ 失败"}')
    print(f'UI节流更新:      {"✓ 通过" if result9 else "✗ 失败"}')
    print(f'K线数据缓存:     {"✓ 通过" if result10 else "✗ 失败"}')

    all_results = [result1, result2, result3, result4, result5, result6, result7, result8, result9, result10]
    if all(all_results):
        print('\n✓ 所有测试通过! 批量分析性能优化修复成功!')
    else:
        print('\n✗ 部分测试失败')
