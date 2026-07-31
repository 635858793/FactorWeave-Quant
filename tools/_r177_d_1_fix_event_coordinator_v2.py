"""R177-D-1 修复 v2: 处理跨行 logger.debug 调用
- 找到 logger.debug( 起始行, 跨行追踪到结束行
- 修改 logger.debug → logger.warning
- 在结束行的 `)` 前追加 , exc_info=True
"""
import ast
import os

TARGET = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\coordinators\event_coordinator.py'

with open(TARGET, 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)
violations = []


def visit(node):
    if isinstance(node, ast.ExceptHandler):
        block_text = ast.unparse(node)
        block_lines = [l for l in block_text.split('\n') if not l.strip().startswith('#')]
        block_code = '\n'.join(block_lines)
        if 'logger.debug' in block_code and 'exc_info=True' not in block_code:
            is_business = any(kw in block_code.lower() for kw in [
                'audit', 'compliance', 'risk', 'order', 'trade', 'security', 'notify',
                'update_price', 'cash_frozen', 'cash_unfrozen', 'account_load'
            ])
            if is_business:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        if (isinstance(sub.func.value, ast.Name) and
                            sub.func.value.id == 'logger' and
                            sub.func.attr == 'debug'):
                            violations.append({
                                'line': sub.lineno,
                                'end_line': sub.end_lineno or sub.lineno,
                            })
                            break
    for child in ast.iter_child_nodes(node):
        visit(child)


visit(tree)
print(f"检测到 {len(violations)} 处业务关键路径 logger.debug 违规 (跨行)")

# 批量修复: 修改起始行 logger.debug → logger.warning
# 在结束行的 `)` 前追加 , exc_info=True
sorted_violations = sorted(violations, key=lambda x: -x['line'])
lines = source.split('\n')
fixed_count = 0

for v in sorted_violations:
    start_idx = v['line'] - 1
    end_idx = v['end_line'] - 1

    if start_idx < 0 or end_idx >= len(lines):
        continue

    # 起始行: logger.debug( → logger.warning(
    start_line = lines[start_idx]
    if 'logger.debug(' in start_line and 'logger.warning' not in start_line:
        new_start = start_line.replace('logger.debug(', 'logger.warning(', 1)
        lines[start_idx] = new_start
    else:
        continue

    # 结束行: 找到 `)` 追加 , exc_info=True)
    end_line = lines[end_idx]
    end_stripped = end_line.rstrip()
    if end_stripped.endswith(')'):
        # 检查是否已含 exc_info
        if 'exc_info=True' in end_stripped:
            continue
        new_end = end_stripped[:-1] + ', exc_info=True)'
        lines[end_idx] = new_end + end_line[len(end_stripped):]
        fixed_count += 1
        print(f"  L{v['line']}-L{v['end_line']} 修复: logger.debug → logger.warning + exc_info=True")

# 写回文件
new_source = '\n'.join(lines)
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(new_source)

print(f"\n✅ 已修复 {fixed_count} 处 R177-D-1 业务关键路径 logger.debug 违规")
