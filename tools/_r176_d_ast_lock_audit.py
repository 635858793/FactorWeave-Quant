"""
R176-D 锁审计 AST 检测脚本 (R104 §12 #3 #5 强制)
- 嵌套检测: AST 递归 with.body (非 ast.walk 扁平化)
- 长锁检测: AST unparse 验证方法体, 统计锁内代码行数
- 4 锁独立策略合规 (R100-F-P1-1)

R162 教训: 验证每个 L 行号准确 (R176-B 报告 100% 命中)
"""
import ast
import json
import sys
from pathlib import Path

# 配置
PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
TARGETS = {
    "trading_engine": PROJECT_ROOT / "core" / "trading_engine.py",
    "trading_service": PROJECT_ROOT / "core" / "services" / "trading_service.py",
    "order_executor": PROJECT_ROOT / "core" / "trading" / "order_executor.py",
    "account_manager": PROJECT_ROOT / "core" / "trading" / "account_manager.py",
}

# 4 锁独立策略: R100-F-P1-1
INDEPENDENT_LOCKS = {
    "_lock", "_stats_lock", "_futures_lock", "_history_lock",
    "_positions_lock", "_pending_lock", "_position_lock", "_order_lock",
    "_account_lock", "_state_lock", "_cache_lock", "_risk_lock",
    "_portfolio_lock", "_correlation_lock",
}


def get_lock_name_from_withitem(item):
    """从 with.items[0].context_expr 提取锁名"""
    if isinstance(item.context_expr, ast.Name):
        return item.context_expr.id
    if isinstance(item.context_expr, ast.Attribute):
        # 处理 self._lock_name 形式
        if isinstance(item.context_expr.value, ast.Name):
            return item.context_expr.attr
    return None


def find_all_with_blocks_in_method(method_node):
    """递归遍历方法体, 收集所有 with 块 (含嵌套)

    R104 §12 #3: 必须递归进入 with.body, 不能 ast.walk 扁平化
    """
    with_blocks = []

    def visit(stmts, parent_locks=set(), depth=0):
        for stmt in stmts:
            if isinstance(stmt, ast.With):
                # 提取锁名
                current_locks = set()
                for item in stmt.items:
                    lock_name = get_lock_name_from_withitem(item)
                    if lock_name:
                        current_locks.add(lock_name)

                all_locks = parent_locks | current_locks

                # 检查嵌套
                nested_in = parent_locks & current_locks
                if nested_in:
                    with_blocks.append({
                        "type": "NESTED",
                        "line_start": stmt.lineno,
                        "line_end": _find_with_end(stmt),
                        "lock": list(current_locks)[0] if current_locks else None,
                        "nested_in": list(nested_in),
                        "depth": depth,
                    })
                else:
                    with_blocks.append({
                        "type": "TOP_LEVEL",
                        "line_start": stmt.lineno,
                        "line_end": _find_with_end(stmt),
                        "lock": list(current_locks)[0] if current_locks else None,
                        "nested_in": [],
                        "depth": depth,
                    })

                # 递归进入 with.body
                visit(stmt.body, all_locks, depth + 1)
            elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
                # 递归进入控制流
                if hasattr(stmt, 'body'):
                    visit(stmt.body, parent_locks, depth)
                if hasattr(stmt, 'orelse') and stmt.orelse:
                    visit(stmt.orelse, parent_locks, depth)
                if hasattr(stmt, 'finalbody') and stmt.finalbody:
                    visit(stmt.finalbody, parent_locks, depth)
                if hasattr(stmt, 'handlers'):
                    for handler in stmt.handlers:
                        if handler.body:
                            visit(handler.body, parent_locks, depth)

    visit(method_node.body)
    return with_blocks


def _find_with_end(with_node):
    """找到 with 块的结束行号 (递归 body+orelse+finalbody)"""
    end = with_node.lineno
    for stmt in with_node.body:
        if hasattr(stmt, 'end_lineno') and stmt.end_lineno:
            end = max(end, stmt.end_lineno)
        elif hasattr(stmt, 'lineno'):
            end = max(end, stmt.lineno)
    if hasattr(with_node, 'end_lineno') and with_node.end_lineno:
        return with_node.end_lineno
    return end


def find_target_methods(tree, target_names):
    """查找目标方法 (按方法名匹配)"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_names:
            found.append(node)
    return found


def analyze_method(method_node, lock_filter=None):
    """分析方法中的 with 块 + 嵌套 + 行数"""
    with_blocks = find_all_with_blocks_in_method(method_node)

    # 过滤锁 (只关注指定锁)
    if lock_filter:
        with_blocks = [b for b in with_blocks if b["lock"] in lock_filter]

    # 统计锁内行数 (针对 TOP_LEVEL)
    lock_size_info = []
    for wb in with_blocks:
        if wb["type"] == "TOP_LEVEL":
            size = wb["line_end"] - wb["line_start"] + 1
            lock_size_info.append({
                "lock": wb["lock"],
                "line_start": wb["line_start"],
                "line_end": wb["line_end"],
                "size": size,
                "nested": False,
            })
        else:
            lock_size_info.append({
                "lock": wb["lock"],
                "line_start": wb["line_start"],
                "line_end": wb["line_end"],
                "size": wb["line_end"] - wb["line_start"] + 1,
                "nested": True,
                "nested_in": wb["nested_in"],
            })

    return lock_size_info


def ast_unparse_method(method_node):
    """AST unparse 验证方法体 (R104 §12 #5 铁律)"""
    try:
        return ast.unparse(method_node)
    except Exception as e:
        return f"UNPARSE_FAILED: {e}"


def check_independent_lock_compliance(method_node):
    """检查 4 锁独立策略合规 (R100-F-P1-1)

    铁律: 禁止在 with self._lock 块内嵌套 with self._xxx_lock (其他锁)
    """
    violations = []

    def visit_with_block(with_node, parent_lock, depth=0):
        for item in with_node.items:
            current_lock = get_lock_name_from_withitem(item)
            if not current_lock:
                continue
            if current_lock in INDEPENDENT_LOCKS and parent_lock and current_lock != parent_lock:
                # 嵌套独立锁,违规
                violations.append({
                    "parent_lock": parent_lock,
                    "nested_lock": current_lock,
                    "line": with_node.lineno,
                    "depth": depth,
                })
        # 递归 body
        for stmt in with_node.body:
            if isinstance(stmt, ast.With):
                for item in stmt.items:
                    parent = get_lock_name_from_withitem(item)
                    if parent:
                        visit_with_block(stmt, parent, depth + 1)
                # 递归内部 with
                for sub_stmt in stmt.body:
                    if isinstance(sub_stmt, ast.With):
                        for sub_item in sub_stmt.items:
                            sub_parent = get_lock_name_from_withitem(sub_item)
                            if sub_parent:
                                visit_with_block(sub_stmt, sub_parent, depth + 1)

    for node in ast.walk(method_node):
        if isinstance(node, ast.With):
            for item in node.items:
                lock_name = get_lock_name_from_withitem(item)
                if lock_name in INDEPENDENT_LOCKS:
                    visit_with_block(node, lock_name, 0)

    return violations


# =================== 主程序 ===================
results = {}

for label, file_path in TARGETS.items():
    if not file_path.exists():
        results[label] = {"error": f"FILE_NOT_EXISTS: {file_path}"}
        continue

    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    results[label] = {
        "file": str(file_path.relative_to(PROJECT_ROOT)),
        "lines": len(source.splitlines()),
    }

# 重点方法名
methods_to_check = {
    "trading_engine": ["_execute_buy", "_execute_sell", "_risk_check",
                       "_reduce_pending_position", "add_pending_position"],
    "trading_service": ["_update_position_from_trade"],
    "order_executor": ["submit_order"],
    "account_manager": ["unfreeze_cash", "freeze_cash"],
}

for label, file_path in TARGETS.items():
    if not file_path.exists():
        continue

    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    method_names = methods_to_check.get(label, [])
    methods = find_target_methods(tree, set(method_names))

    methods_info = []
    for m in methods:
        with_blocks = analyze_method(m)
        unparsed = ast_unparse_method(m)
        violations = check_independent_lock_compliance(m)
        methods_info.append({
            "name": m.name,
            "line_start": m.lineno,
            "line_end": m.end_lineno,
            "size": m.end_lineno - m.lineno + 1,
            "with_blocks": with_blocks,
            "unparse_size": len(unparsed),
            "independent_lock_violations": violations,
        })

    results[label]["methods"] = methods_info


# =================== 输出报告 ===================
print("=" * 80)
print("R176-D AST 锁审计报告 (R104 §12 #3 #5 + R100-F-P1-1 + R110-P0-2)")
print("=" * 80)

for label, info in results.items():
    if "error" in info:
        print(f"\n[{label}] ❌ {info['error']}")
        continue

    print(f"\n[{label}] {info['file']} (总 {info['lines']} 行)")
    for m in info.get("methods", []):
        long_lock_warn = ""
        for wb in m["with_blocks"]:
            if wb["size"] >= 30:
                long_lock_warn += f"  ⚠️  长锁 {wb['lock']} L{wb['line_start']}-{wb['line_end']} ({wb['size']} 行)"
                if wb.get("nested"):
                    long_lock_warn += f" [NESTED in {wb['nested_in']}]"

        nested_warn = ""
        if m["independent_lock_violations"]:
            nested_warn = f"  ❌ 4锁独立违规: {len(m['independent_lock_violations'])} 处"

        print(f"  - {m['name']} (L{m['line_start']}-{m['line_end']}, {m['size']} 行){long_lock_warn}{nested_warn}")

# 保存 JSON
output_file = PROJECT_ROOT / ".trae" / "reports" / "rounds" / "_r176_d_ast_lock_audit.json"
output_file.parent.mkdir(parents=True, exist_ok=True)
output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(f"\n\n详细结果已保存: {output_file}")
