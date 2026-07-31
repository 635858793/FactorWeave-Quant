"""R176-B-3 批量修复 risk_rule_manager.py 18 处 R51 #5 违规
- 严格应用 R174 §6.4 AST 严格扫描器 v2 必杀技
- 移除注释行后再检测,避免误报
- 批量追加 exc_info=True 到 logger.error/warning 后
"""
import ast
import os
import re

TARGET = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\risk_rule_manager.py'

# 1. Read 源文件
with open(TARGET, 'r', encoding='utf-8') as f:
    source = f.read()

# 2. 解析 AST, 找到所有 ExceptHandler 块内的 logger.warning/error/exception 调用
tree = ast.parse(source)

# 收集所有 (行号, 函数名, 当前 logger 调用) 违规
violations = []


def visit(node, current_func=None):
    if isinstance(node, ast.FunctionDef):
        current_func = node.name
    if isinstance(node, ast.ExceptHandler):
        # 收集该 except 块内的 logger.warning/error/exception 调用行
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == 'logger':
                    log_func_name = func.attr
                    if log_func_name in ('warning', 'error', 'exception'):
                        # 检查是否带 exc_info=True
                        has_exc_info = any(
                            isinstance(kw.value, ast.Constant) and kw.value.value is True
                            for kw in sub.keywords
                        )
                        if not has_exc_info:
                            violations.append({
                                'line': sub.lineno,
                                'func_name': current_func,
                                'log_func': log_func_name,
                                'col': sub.col_offset,
                            })
    for child in ast.iter_child_nodes(node):
        visit(child, current_func)


visit(tree)

print(f"检测到 {len(violations)} 处 R51 #5 违规")
for v in violations:
    print(f"  L{v['line']} {v['func_name']}.{v['log_func']} (col {v['col']})")

# 3. 批量处理: 找到 logger.warning/error/exception 调用, 追加 exc_info=True
# 使用行号倒序处理, 避免行号偏移
sorted_violations = sorted(violations, key=lambda x: -x['line'])

lines = source.split('\n')
fixed_count = 0

for v in sorted_violations:
    line_idx = v['line'] - 1  # 0-based
    if line_idx < 0 or line_idx >= len(lines):
        continue
    line = lines[line_idx]

    # 检查该行是否已经有 exc_info=True
    if 'exc_info=True' in line:
        print(f"  L{v['line']} 已含 exc_info=True, 跳过")
        continue

    # 找到 logger 调用, 判断该调用是否以 `)` 结尾 (参数列表闭合)
    # 三种模式:
    # 1. logger.error(f"...") → 改为 logger.error(f"...", exc_info=True)
    # 2. logger.error(   f"...") 跨行 → 找到闭合 `)` 追加
    # 3. logger.error("text") → 改为 logger.error("text", exc_info=True)
    # 4. logger.error() → 改为 logger.error(exc_info=True)

    # 简化处理: 如果行以 `)` 结尾, 在 `)` 前加 `, exc_info=True`
    stripped = line.rstrip()
    if stripped.endswith(')'):
        # 找到 `)` 的位置
        # 倒数第 1 个 `)` 之前加 `, exc_info=True`
        new_line = stripped[:-1] + ', exc_info=True)'
        lines[line_idx] = new_line + line[len(stripped):]
        fixed_count += 1
        print(f"  L{v['line']} 修复: {stripped} -> {new_line}")
    else:
        # 多行调用, 找下一个以 `)` 结尾的行
        # 在该行末尾添加 `, exc_info=True`
        # 实际上风险规则文件都是单行调用, 这里跳过
        print(f"  L{v['line']} 跨行调用, 跳过 (需手动处理): {line}")

# 4. 写回文件
new_source = '\n'.join(lines)
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(new_source)

print(f"\n✅ 已修复 {fixed_count} 处 R51 #5 违规")
print(f"目标文件: {TARGET}")
