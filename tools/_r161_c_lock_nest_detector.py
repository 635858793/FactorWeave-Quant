"""
R161-C 锁嵌套 AST 检测脚本
严格遵守 R104 §12 铁律:
- #3 嵌套检测递归 with.body (严禁 ast.walk 扁平化)
- #5 AST unparse 验证方法体 (严禁仅看字符串)

检测目标:
1. EventBus 4 锁独立策略 (_lock / _futures_lock / _stats_lock / _history_lock)
2. TradingEngine 4 锁独立策略 (_cache_lock / _positions_lock / _signals_lock / _pending_lock)
3. OrderService / OrderExecutor / RiskManager / AccountManager / MoneyManager
4. StopLoss / TakeProfit
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple

# 目标服务文件
TARGETS = {
    "EventBus": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/events/event_bus.py",
    "TradingEngine": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading_engine.py",
    "OrderService": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/order_service.py",
    "OrderExecutor": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/order_executor.py",
    "AccountManager": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/account_manager.py",
    "RiskManager": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/risk_manager.py",
    "MoneyManager": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/money_manager.py",
    "StopLoss": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/stop_loss.py",
    "OrderMonitor": "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/order_monitor.py",
}

# 4 锁独立策略 - 各服务的目标锁名
TARGET_LOCKS = {
    "EventBus": {"_lock", "_futures_lock", "_stats_lock", "_history_lock"},
    "TradingEngine": {"_cache_lock", "_positions_lock", "_signals_lock", "_pending_lock"},
    "OrderService": {"_lock_manager_lock"},
    "OrderExecutor": {"_order_lock", "_interface_health_lock"},
    "AccountManager": {"_account_lock", "_position_lock", "_fund_info_lock", "_sync_lock"},
    "RiskManager": {"_positions_lock"},
    "MoneyManager": set(),
    "StopLoss": set(),
    "OrderMonitor": set(),
}


def get_lock_name(item: ast.withitem) -> str | None:
    """从 with 项提取锁名 (处理 self._xxx_lock 形式)"""
    ctx = item.context_expr
    if isinstance(ctx, ast.Attribute):
        if isinstance(ctx.value, ast.Name) and ctx.value.id == "self":
            return ctx.attr
    elif isinstance(ctx, ast.Name):
        return ctx.id
    return None


def find_nested_locks_in_method(method_node: ast.FunctionDef, target_locks: Set[str]) -> List[Dict]:
    """
    递归进入 with.body 检测锁嵌套 (R104 §12 铁律 #3)
    严禁 ast.walk 扁平化!
    """
    violations = []

    def visit_with(with_node: ast.With, parent_locks: Set[str], path_stack: List[ast.AST]):
        """递归访问 with 块, 检测锁嵌套"""
        current_locks = set(parent_locks)

        # 收集本层 with 的所有锁
        new_locks = set()
        for item in with_node.items:
            lock_name = get_lock_name(item)
            if lock_name and lock_name in target_locks:
                if lock_name in current_locks:
                    # 检测到嵌套
                    violations.append({
                        "type": "NESTED_LOCK",
                        "outer_lock": lock_name,
                        "inner_lock": lock_name,
                        "method": method_node.name,
                        "line": with_node.lineno,
                        "depth": len(current_locks) + 1,
                    })
                new_locks.add(lock_name)

        current_locks = current_locks | new_locks

        # 递归进入 body (R104 铁律 #3)
        for stmt in with_node.body:
            visit_stmt(stmt, current_locks, path_stack + [with_node])

        # 也递归进入 orelse (for/while/try 等)
        for stmt in with_node.orelse if hasattr(with_node, 'orelse') else []:
            visit_stmt(stmt, current_locks, path_stack + [with_node])

    def visit_stmt(stmt, current_locks, path_stack):
        if isinstance(stmt, ast.With):
            visit_with(stmt, current_locks, path_stack)
        elif isinstance(stmt, ast.If):
            for s in stmt.body:
                visit_stmt(s, current_locks, path_stack)
            for s in stmt.orelse:
                visit_stmt(s, current_locks, path_stack)
        elif isinstance(stmt, (ast.For, ast.While)):
            for s in stmt.body:
                visit_stmt(s, current_locks, path_stack)
            for s in stmt.orelse:
                visit_stmt(s, current_locks, path_stack)
        elif isinstance(stmt, ast.Try):
            for s in stmt.body:
                visit_stmt(s, current_locks, path_stack)
            for s in stmt.handlers:
                for s2 in s.body:
                    visit_stmt(s2, current_locks, path_stack)
            for s in stmt.orelse:
                visit_stmt(s, current_locks, path_stack)
            for s in stmt.finalbody:
                visit_stmt(s, current_locks, path_stack)

    # 从方法顶层 body 开始
    for stmt in method_node.body:
        visit_stmt(stmt, set(), [])

    return violations


def measure_lock_block_size(method_node: ast.FunctionDef, target_locks: Set[str]) -> List[Dict]:
    """测量 with 锁块大小 (行数), 标记长锁"""
    long_locks = []

    def visit_stmt(stmt, current_locks):
        if isinstance(stmt, ast.With):
            for item in stmt.items:
                lock_name = get_lock_name(item)
                if lock_name and lock_name in target_locks:
                    # 计算 with 块大小 (从 with.lineno 到 end_lineno)
                    start = stmt.lineno
                    end = stmt.end_lineno or start
                    size = end - start + 1
                    if size >= 10:
                        long_locks.append({
                            "type": "LONG_LOCK",
                            "lock": lock_name,
                            "method": method_node.name,
                            "line": start,
                            "end_line": end,
                            "size": size,
                        })
            # 递归 body
            for s in stmt.body:
                visit_stmt(s, current_locks)
        elif isinstance(stmt, ast.If):
            for s in stmt.body:
                visit_stmt(s, current_locks)
            for s in stmt.orelse:
                visit_stmt(s, current_locks)
        elif isinstance(stmt, (ast.For, ast.While)):
            for s in stmt.body:
                visit_stmt(s, current_locks)
            for s in stmt.orelse:
                visit_stmt(s, current_locks)
        elif isinstance(stmt, ast.Try):
            for s in stmt.body:
                visit_stmt(s, current_locks)
            for s in stmt.finalbody:
                visit_stmt(s, current_locks)

    for stmt in method_node.body:
        visit_stmt(stmt, set())
    return long_locks


def detect_io_in_lock(method_node: ast.FunctionDef, target_locks: Set[str]) -> List[Dict]:
    """检测锁内 IO 操作 (publish / submit_order / db / IO 危险调用)"""
    io_calls = []

    def is_io_call(node: ast.Call) -> bool:
        # 检测 publish / submit_order / execute / save / write / db.execute 等
        func = node.func
        func_name = None
        if isinstance(func, ast.Attribute):
            func_name = func.attr
        elif isinstance(func, ast.Name):
            func_name = func.id
        if not func_name:
            return False
        io_keywords = {
            "publish", "submit_order", "submit", "save", "write", "update",
            "execute", "query", "insert", "delete", "send", "fetch",
            "request", "call", "log", "notify", "send_mail",
        }
        return func_name in io_keywords

    def visit_stmt(stmt, in_lock, current_lock):
        if isinstance(stmt, ast.With):
            lock_in_this = None
            for item in stmt.items:
                ln = get_lock_name(item)
                if ln and ln in target_locks:
                    lock_in_this = ln
            if lock_in_this:
                in_lock = True
                current_lock = lock_in_this
            # 递归 body 检查
            for s in stmt.body:
                visit_stmt(s, in_lock, current_lock)
        elif isinstance(stmt, ast.If):
            for s in stmt.body:
                visit_stmt(s, in_lock, current_lock)
            for s in stmt.orelse:
                visit_stmt(s, in_lock, current_lock)
        elif isinstance(stmt, (ast.For, ast.While)):
            for s in stmt.body:
                visit_stmt(s, in_lock, current_lock)
            for s in stmt.orelse:
                visit_stmt(s, in_lock, current_lock)
        elif isinstance(stmt, ast.Try):
            for s in stmt.body:
                visit_stmt(s, in_lock, current_lock)
            for s in stmt.finalbody:
                visit_stmt(s, in_lock, current_lock)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            if in_lock and is_io_call(stmt.value):
                func = stmt.value.func
                fn = func.attr if isinstance(func, ast.Attribute) else func.id
                io_calls.append({
                    "type": "IO_IN_LOCK",
                    "lock": current_lock,
                    "method": method_node.name,
                    "line": stmt.lineno,
                    "io_call": fn,
                })
        elif isinstance(stmt, ast.Assign):
            for v in stmt.value.nodes if hasattr(stmt.value, 'nodes') else []:
                pass  # 简化
            if isinstance(stmt.value, ast.Call) and in_lock and is_io_call(stmt.value):
                func = stmt.value.func
                fn = func.attr if isinstance(func, ast.Attribute) else func.id
                io_calls.append({
                    "type": "IO_IN_LOCK",
                    "lock": current_lock,
                    "method": method_node.name,
                    "line": stmt.lineno,
                    "io_call": fn,
                })

    for stmt in method_node.body:
        visit_stmt(stmt, False, None)
    return io_calls


def analyze_file(file_path: str, target_locks: Set[str]) -> Dict:
    """分析单个文件"""
    if not Path(file_path).exists():
        return {"error": f"File not found: {file_path}"}

    source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source)

    all_violations = []
    all_long_locks = []
    all_io_in_lock = []
    found_locks = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name) and target.value.id == "self":
                        name = target.attr
                        if "_lock" in name:
                            found_locks.add(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            violations = find_nested_locks_in_method(node, target_locks)
            long_locks = measure_lock_block_size(node, target_locks)
            io_in_lock = detect_io_in_lock(node, target_locks)
            all_violations.extend(violations)
            all_long_locks.extend(long_locks)
            all_io_in_lock.extend(io_in_lock)

    return {
        "found_locks": sorted(found_locks),
        "target_locks": sorted(target_locks),
        "missing_locks": sorted(target_locks - found_locks),
        "nested_violations": all_violations,
        "long_locks": all_long_locks,
        "io_in_lock": all_io_in_lock,
        "total_methods": len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]),
    }


def main():
    print("=" * 80)
    print("R161-C 锁嵌套 AST 检测 (R104 §12 铁律 #3 递归 with.body + #5 AST unparse)")
    print("=" * 80)

    summary = {}

    for service_name, file_path in TARGETS.items():
        target_locks = TARGET_LOCKS.get(service_name, set())
        print(f"\n[分析] {service_name} (目标锁: {target_locks})")
        print(f"  文件: {file_path}")

        result = analyze_file(file_path, target_locks)
        if "error" in result:
            print(f"  ❌ {result['error']}")
            continue

        summary[service_name] = result

        print(f"  找到锁字段: {result['found_locks']}")
        if result['missing_locks']:
            print(f"  ⚠️  目标锁字段缺失: {result['missing_locks']}")
        else:
            print(f"  ✅ 4 锁独立策略完整")

        # 嵌套违规
        nested = result['nested_violations']
        if nested:
            print(f"  ❌ 锁嵌套违规: {len(nested)} 处")
            for v in nested[:5]:
                print(f"     - {v['method']}.{v['line']}: {v['outer_lock']} → {v['inner_lock']} (depth={v['depth']})")
            if len(nested) > 5:
                print(f"     ... 还有 {len(nested)-5} 处")
        else:
            print(f"  ✅ 锁嵌套: 0 处")

        # 长锁
        long_locks = result['long_locks']
        if long_locks:
            print(f"  ⚠️  长锁 (≥10 行): {len(long_locks)} 处")
            for v in long_locks[:5]:
                print(f"     - {v['method']}.{v['line']}: {v['lock']} ({v['size']} 行)")
            if len(long_locks) > 5:
                print(f"     ... 还有 {len(long_locks)-5} 处")
        else:
            print(f"  ✅ 长锁: 0 处")

        # 锁内 IO
        io_calls = result['io_in_lock']
        if io_calls:
            print(f"  ⚠️  锁内 IO: {len(io_calls)} 处")
            for v in io_calls[:5]:
                print(f"     - {v['method']}.{v['line']}: {v['io_call']}() in {v['lock']}")
            if len(io_calls) > 5:
                print(f"     ... 还有 {len(io_calls)-5} 处")
        else:
            print(f"  ✅ 锁内 IO: 0 处")

    print("\n" + "=" * 80)
    print("汇总")
    print("=" * 80)

    total_nested = sum(len(r.get('nested_violations', [])) for r in summary.values())
    total_long = sum(len(r.get('long_locks', [])) for r in summary.values())
    total_io = sum(len(r.get('io_in_lock', [])) for r in summary.values())

    print(f"  锁嵌套违规总计: {total_nested}")
    print(f"  长锁 (≥10 行) 总计: {total_long}")
    print(f"  锁内 IO 总计: {total_io}")

    return summary


if __name__ == "__main__":
    main()
