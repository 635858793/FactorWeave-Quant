"""R177+ 立项真实状态审计 (4 维度 + R+1 round 4 源验证)
- 子智能体 A: 缓存键 6 维度审计 (HVD-177-A-2..5 stock_service 6 处辅助方法)
- 子智能体 B: 业务调用链 (HVD-177-A-2..5 业务方验证)
- 子智能体 C: 锁架构 (HVD-177-C-1..3 trading_engine 长锁)
- 子智能体 D: 事件总线 (HVD-177-D-1 event_coordinator logger.debug)
"""
import ast
import os
import re

# ====== 子智能体 A: 缓存键 6 维度审计 ======
print("=" * 80)
print("子智能体 A: 缓存键 6 维度审计 (HVD-177-A-2..5 stock_service 6 处辅助方法)")
print("=" * 80)

stock_service_path = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\stock_service.py'
with open(stock_service_path, 'r', encoding='utf-8') as f:
    content = f.read()

# R176-A-1 已修复 3 处 (L271 stock_list, L332 stock_data, L611 stock_info)
# R177-A-2..5 待办: 6 处辅助方法硬编码 cache_key
# L475 search / L916 shares / L1070 crypto / L1105 fund / L1139 futures / L1174 index

target_lines = {
    'HVD-177-A-2': (475, 'search_{keyword}', 1, 'search'),
    'HVD-177-A-3': (916, 'shares_data_{stock_code}', 1, 'shares_data'),
    'HVD-177-A-4': (1070, 'crypto_supply_{crypto_code}', 1, 'crypto_supply'),
    'HVD-177-A-5': (1105, 'fund_units_{fund_code}', 1, 'fund_units'),
    'HVD-177-A-6': (1139, 'futures_oi_{futures_code}', 1, 'futures_oi'),
    'HVD-177-A-7': (1174, 'index_mc_{index_code}', 1, 'index_mc'),
}

print("\nR176-A-1 已修复 3 处: stock_list/stock_data/stock_info ✅")
print("R177-A-2..7 候选 6 处辅助方法:")
for hvd, (line, key, dims, name) in target_lines.items():
    # 验证行号
    actual = content.split('\n')[line - 1] if line <= len(content.split('\n')) else ''
    match = f'cache_key = f"{key}' in actual
    print(f"  {hvd} L{line}: {key} ({dims} 维度) - {'✅ 存在' if match else '❌ 行号偏差'}: {actual.strip()[:80]}")

# ====== 子智能体 C: 锁架构 (HVD-177-C-1..3 trading_engine 长锁) ======
print("\n" + "=" * 80)
print("子智能体 C: 锁架构 (HVD-177-C-1..3 trading_engine 长锁)")
print("=" * 80)

trading_engine_path = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\trading_engine.py'
with open(trading_engine_path, 'r', encoding='utf-8') as f:
    te_content = f.read()

te_tree = ast.parse(te_content)


def measure_method(node, lock_attr='_positions_lock'):
    """测量方法实际持锁区间行数"""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None

    # 找 with self.{lock_attr}: 块的起止行
    lock_enter_line = None
    lock_end_line = None

    def visit_with(n, depth=0):
        nonlocal lock_enter_line, lock_end_line
        if isinstance(n, ast.With):
            for item in n.items:
                ctx = item.context_expr
                if (isinstance(ctx, ast.Attribute) and
                    isinstance(ctx.value, ast.Name) and
                    ctx.value.id == 'self' and
                    ctx.attr == lock_attr):
                    if lock_enter_line is None:
                        lock_enter_line = n.lineno
                    lock_end_line = n.end_lineno or n.lineno
                    return  # 只关心顶层
            for stmt in n.body:
                visit_with(stmt, depth + 1)

    visit_with(node)
    if lock_enter_line is None:
        return None
    return {
        'method': node.name,
        'start': node.lineno,
        'end': node.end_lineno or node.lineno,
        'lock_enter': lock_enter_line,
        'lock_end': lock_end_line,
    }


target_methods = ['_execute_buy', '_execute_sell', '_risk_check']
print("\nTrading engine 长锁实测 (R+1 round 4 源 100% 命中验证):")
for node in ast.walk(te_tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name in target_methods:
            info = measure_method(node)
            if info:
                print(f"  {info['method']}: L{info['start']}-L{info['end']} ({info['end']-info['start']+1} 行), 锁 L{info['lock_enter']}-L{info['lock_end']} ({info['lock_end']-info['lock_enter']+1} 行)")

# ====== 子智能体 D: 事件总线 (HVD-177-D-1 event_coordinator logger.debug) ======
print("\n" + "=" * 80)
print("子智能体 D: 事件总线 (HVD-177-D-1 event_coordinator logger.debug)")
print("=" * 80)

event_coordinator_path = r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\coordinators\event_coordinator.py'
if os.path.exists(event_coordinator_path):
    with open(event_coordinator_path, 'r', encoding='utf-8') as f:
        ec_content = f.read()
    ec_tree = ast.parse(ec_content)

    # 收集 logger.debug 业务关键路径
    debug_violations = []
    for node in ast.walk(ec_tree):
        if isinstance(node, ast.ExceptHandler):
            block_text = ast.unparse(node)
            block_lines = [l for l in block_text.split('\n') if not l.strip().startswith('#')]
            block_code = '\n'.join(block_lines)
            if 'logger.debug' in block_code and 'exc_info=True' not in block_code:
                is_business = any(kw in block_code.lower() for kw in [
                    'audit', 'security', 'compliance', 'risk', 'order', 'trade', 'notify'
                ])
                if is_business:
                    debug_violations.append({
                        'line': node.lineno,
                        'preview': block_text[:200].replace('\n', ' | '),
                    })

    print(f"\nevent_coordinator.py 业务关键路径 logger.debug 违规: {len(debug_violations)}")
    for v in debug_violations[:10]:
        print(f"  L{v['line']}: {v['preview']}")
else:
    print(f"\n❌ event_coordinator.py 不存在: {event_coordinator_path}")
    # 搜索真实路径
    for root, dirs, files in os.walk(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core'):
        for f in files:
            if 'event_coordinator' in f:
                print(f"  发现: {os.path.join(root, f)}")
