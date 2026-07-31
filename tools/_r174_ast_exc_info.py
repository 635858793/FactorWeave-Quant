"""R174: 用 AST 精确分析 logger.error/warning 缺 exc_info 的位置"""
import ast
from pathlib import Path

files = [
    'core/agents/bettafish_agent.py',
    'core/services/ai_selection_integration_service.py',
]

for f in files:
    source = Path(f).read_text(encoding='utf-8')
    tree = ast.parse(source)
    bad_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Get function name
            func_name = None
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'logger':
                    func_name = node.func.attr
            if func_name not in ('error', 'warning', 'critical'):
                continue
            # Check if exc_info=True keyword arg present
            has_exc_info = False
            for kw in node.keywords:
                if kw.arg == 'exc_info':
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        has_exc_info = True
            if not has_exc_info:
                # Determine context: is this in an except block?
                # Walk up parents - need to find containing node
                bad_calls.append((node.lineno, func_name))
    print(f'=== {f} ===')
    print(f'  AST-detected logger calls without exc_info=True: {len(bad_calls)}')
    for lineno, func in bad_calls[:20]:
        # Get source line
        all_lines = source.split('\n')
        line = all_lines[lineno-1] if lineno-1 < len(all_lines) else ''
        print(f'  L{lineno}: {func} - {line.strip()[:100]}')
