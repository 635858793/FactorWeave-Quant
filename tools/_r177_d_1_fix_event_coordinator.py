"""R177-D-1 修复: event_coordinator.py 13 处业务关键路径 logger.debug 升级
- R118 B15 铁律: 业务关键路径 logger.debug 静默吞错违规
- R51 §7.1 #5 强约束升级: 业务关键路径 (审计/合规/风险/订单) 100% exc_info=True
- R+1 round 4 源 100% 命中验证

违规模式 (R142 P0 修复时埋):
- 业务关键路径: ComplianceAuditLogger 不可用 / update_price 失败 / cash_frozen audit log 失败
- 当前: logger.debug(..., _audit_exc) 静默吞错
- 修复: logger.warning(..., _audit_exc, exc_info=True)
"""
import ast
import os

TARGET = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\coordinators\event_coordinator.py'

with open(TARGET, 'r', encoding='utf-8') as f:
    source = f.read()

# 1. AST 严格扫描: 收集所有违规行
tree = ast.parse(source)
violations = []


def visit(node):
    if isinstance(node, ast.ExceptHandler):
        block_text = ast.unparse(node)
        # 移除注释行
        block_lines = [l for l in block_text.split('\n') if not l.strip().startswith('#')]
        block_code = '\n'.join(block_lines)
        if 'logger.debug' in block_code and 'exc_info=True' not in block_code:
            # 业务关键路径: 审计/合规/风险/订单/安全/通知
            is_business = any(kw in block_code.lower() for kw in [
                'audit', 'compliance', 'risk', 'order', 'trade', 'security', 'notify',
                'update_price', 'cash_frozen', 'cash_unfrozen', 'account_load'
            ])
            if is_business:
                # 找 logger.debug 调用的具体行号
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        if (isinstance(sub.func.value, ast.Name) and
                            sub.func.value.id == 'logger' and
                            sub.func.attr == 'debug'):
                            violations.append({
                                'line': sub.lineno,
                                'col': sub.col_offset,
                                'preview': block_text[:200].replace('\n', ' | '),
                            })
                            break
    for child in ast.iter_child_nodes(node):
        visit(child)


visit(tree)
print(f"检测到 {len(violations)} 处业务关键路径 logger.debug 违规")
for v in violations:
    print(f"  L{v['line']}: {v['preview'][:150]}")

# 2. 批量修复: logger.debug → logger.warning + exc_info=True
# 倒序处理, 避免行号偏移
sorted_violations = sorted(violations, key=lambda x: -x['line'])
lines = source.split('\n')
fixed_count = 0

for v in sorted_violations:
    line_idx = v['line'] - 1
    if line_idx < 0 or line_idx >= len(lines):
        continue
    line = lines[line_idx]
    stripped = line.rstrip()

    if 'logger.debug' in line and 'logger.warning' not in line and 'exc_info=True' not in line:
        # 找到 logger.debug( 替换为 logger.warning( 然后在该行末尾追加 , exc_info=True
        new_line = line.replace('logger.debug(', 'logger.warning(', 1)
        # 移除末尾的 `)` 准备追加
        new_stripped = new_line.rstrip()
        if new_stripped.endswith(')'):
            new_line = new_stripped[:-1] + ', exc_info=True)'
            lines[line_idx] = new_line + line[len(new_stripped):]
            fixed_count += 1
            print(f"  L{v['line']} 修复: {stripped[:80]}...")
            print(f"       → {lines[line_idx][:100]}...")

# 3. 写回文件
new_source = '\n'.join(lines)
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(new_source)

print(f"\n✅ 已修复 {fixed_count} 处 R177-D-1 业务关键路径 logger.debug 违规")
print(f"目标文件: {TARGET}")
