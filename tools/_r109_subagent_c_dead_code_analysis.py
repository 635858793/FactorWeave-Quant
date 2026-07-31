"""R109 子智能体 C: 死代码深度分析脚本."""
import ast
import os
import sys

def analyze(path):
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    methods = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            methods[node.name] = {'line': node.lineno, 'self_calls': 0}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == 'self':
                    if sub.attr in methods:
                        methods[sub.attr]['self_calls'] += 1
    print(f'\n=== {path} ===')
    print(f'方法总数: {len(methods)}')
    for name, info in sorted(methods.items(), key=lambda x: x[1]['line']):
        if name.startswith('_') and not name.startswith('__'):
            print(f'  L{info["line"]:>5} {name:60} 内部 self 调用 {info["self_calls"]:>2} 次')

if __name__ == '__main__':
    for p in sys.argv[1:]:
        analyze(p)
