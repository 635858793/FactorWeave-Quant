import ast
import re

def analyze_visualization_file(filepath):
    """深度分析 visualization.py 文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = {
        'import_issues': [],
        'undefined_variables': [],
        'type_safety_issues': [],
        'logic_errors': [],
        'code_structure_issues': [],
        'potential_runtime_errors': []
    }
    
    # 解析AST
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"语法错误: {e}")
        return issues
    
    # 收集所有导入
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    
    # 收集所有定义的名称
    defined_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(target, ast.Name):
                defined_names.add(target.id)
    
    # 检查未定义的变量
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        # 检查 Query(-30) 使用
        if 'Query(-30)' in line:
            if 'Query' not in imports and 'Query' not in defined_names:
                issues['undefined_variables'].append({
                    'line': i,
                    'issue': '使用了未导入的Query类',
                    'code': line.strip()
                })
        
        # 检查 top_model_features
        if 'top_model_features' in line:
            if 'top_model_features' not in defined_names:
                issues['undefined_variables'].append({
                    'line': i,
                    'issue': '使用了未定义的变量top_model_features',
                    'code': line.strip()
                })
        
        # 检查 fast_ma.n 和 slow_ma.n 的使用
        if ('fast_ma.n' in line or 'slow_ma.n' in line):
            if 'fast_ma=None, slow_ma=None' in lines[max(0, i-10):i]:
                issues['potential_runtime_errors'].append({
                    'line': i,
                    'issue': '可能访问None对象的属性n',
                    'code': line.strip()
                })
        
        # 检查 pivot_sell 的使用
        if 'pivot_sell' in line:
            if 'pivot_sell = ' not in '\n'.join(lines[:i]):
                issues['undefined_variables'].append({
                    'line': i,
                    'issue': '使用了未定义的变量pivot_sell',
                    'code': line.strip()
                })
    
    # 检查代码结构
    has_class = False
    has_functions = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            has_class = True
        elif isinstance(node, ast.FunctionDef):
            if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) 
                      if isinstance(parent, ast.FunctionDef) and parent.name == node.name):
                has_functions = True
    
    if has_class and has_functions:
        issues['code_structure_issues'].append({
            'issue': '文件中同时存在类定义和独立函数，可能存在设计问题'
        })
    
    return issues

if __name__ == '__main__':
    filepath = 'visualization/visualization.py'
    issues = analyze_visualization_file(filepath)
    
    print("=== Visualization.py 深度分析报告 ===\n")
    
    for issue_type, issue_list in issues.items():
        if issue_list:
            print(f"\n{issue_type.upper().replace('_', ' ')} ({len(issue_list)} 个问题):")
            for issue in issue_list:
                print(f"  行号: {issue.get('line', 'N/A')}")
                print(f"  问题: {issue.get('issue', issue.get('code', 'N/A'))}")
                if 'code' in issue:
                    print(f"  代码: {issue['code']}")
                print()
    
    total_issues = sum(len(lst) for lst in issues.values())
    print(f"\n总计发现 {total_issues} 个问题")
