"""
R176 阶段: 8 项 P1 长锁精准测量 (R104 §12 铁律 #3+#5)
用整文件 AST 解析, 然后查找特定方法名
"""
import ast
from pathlib import Path

target_files = {
    'handle_order_fill (order_executor)': ('core/trading/order_executor.py', 'OrderExecutor', 'handle_order_fill'),
    'on_bar_close (enhanced_risk_monitor)': ('core/risk_monitoring/enhanced_risk_monitor.py', 'EnhancedRiskMonitor', 'on_bar_close'),
    '_on_position_updated (account_manager)': ('core/trading/account_manager.py', 'AccountManager', '_on_position_updated'),
    'execute_order (trading_service)': ('core/services/trading_service.py', 'TradingService', 'execute_order'),
    '_execute_buy (trading_engine)': ('core/trading_engine.py', 'TradingEngine', '_execute_buy'),
    '_execute_sell (trading_engine)': ('core/trading_engine.py', 'TradingEngine', '_execute_sell'),
    '_risk_check (trading_engine)': ('core/trading_engine.py', 'TradingEngine', '_risk_check'),
    '_reduce_pending_position (trading_engine)': ('core/trading_engine.py', 'TradingEngine', '_reduce_pending_position'),
}

# IO 关键字
IO_KEYWORDS = {
    "publish", "submit_order", "submit", "save", "write", "update",
    "execute", "query", "insert", "delete", "send", "fetch",
    "request", "call", "log", "notify", "send_mail", "broadcast",
    "sync_account_positions", "sync_data", "send_message", "send_request",
}

for name, (path, class_name, method_name) in target_files.items():
    print(f"  File: {path} Method: {class_name}.{method_name}")
    src = Path(path).read_text(encoding='utf-8', errors='ignore').split('\n')
    try:
        tree = ast.parse(Path(path).read_text(encoding='utf-8', errors='ignore'))
    except SyntaxError as e:
        print(f"  语法错误: {e}")
        continue

    # 查找方法 (全局首个匹配)
    target_method = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            target_method = node
            break
    if not target_method:
        print(f"  Method {class_name}.{method_name} not found")
        continue

    start = target_method.lineno
    end = target_method.end_lineno or target_method.lineno
    print(f"  Method range: L{start}-L{end} (Total {end-start+1} lines)")

    # R104 §12 铁律 #3: 递归 with.body
    def visit_with(node, depth=0):
        results = []
        if isinstance(node, ast.With):
            for item in node.items:
                if (isinstance(item.context_expr, ast.Attribute) and
                    isinstance(item.context_expr.value, ast.Name) and
                    item.context_expr.value.id == 'self'):
                    lock_name = item.context_expr.attr
                    if '_lock' in lock_name or 'Lock' in lock_name:
                        ls = node.lineno
                        le = node.end_lineno or node.lineno
                        size = le - ls + 1
                        io_hits = []
                        for line in src[ls-1:le]:
                            for kw in IO_KEYWORDS:
                                if f"{kw}(" in line and "self." in line:
                                    io_hits.append(f"{kw}()")
                                    break
                        results.append({
                            'lock': lock_name,
                            'line_start': ls,
                            'line_end': le,
                            'size': size,
                            'depth': depth,
                            'nested': depth > 0,
                            'io_hits': io_hits,
                        })
            for stmt in node.body:
                results.extend(visit_with(stmt, depth+1))
            for stmt in (node.orelse or []):
                results.extend(visit_with(stmt, depth+1))
        elif isinstance(node, ast.If):
            for stmt in node.body:
                results.extend(visit_with(stmt, depth))
            for stmt in node.orelse:
                results.extend(visit_with(stmt, depth))
        elif isinstance(node, (ast.For, ast.While)):
            for stmt in node.body:
                results.extend(visit_with(stmt, depth))
            for stmt in node.orelse:
                results.extend(visit_with(stmt, depth))
        elif isinstance(node, ast.Try):
            for stmt in node.body:
                results.extend(visit_with(stmt, depth))
            for h in node.handlers:
                for stmt in h.body:
                    results.extend(visit_with(stmt, depth))
            for stmt in (node.orelse or []):
                results.extend(visit_with(stmt, depth))
            for stmt in node.finalbody:
                results.extend(visit_with(stmt, depth))
        return results

    locks = visit_with(target_method)
    if not locks:
        print(f"  No lock block found")
    for lock in locks:
        nest_str = " [NESTED]" if lock['nested'] else ""
        io_str = f" IO={lock['io_hits']}" if lock['io_hits'] else ""
        print(f"  L{lock['line_start']}-L{lock['line_end']} {lock['lock']} ({lock['size']} lines, depth={lock['depth']}){nest_str}{io_str}")
    print()
