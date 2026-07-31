"""
R155-C 锁架构审计工具 V2
R104 §12 铁律 #3+#5 严格应用

修复 V1 问题: 用 self._lock (ast.Attribute) 而非 _lock (ast.Name)
"""
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def get_lock_name_from_context(expr) -> str:
    """从 with context_expr 提取锁名 (支持 self._lock 和 module._lock)"""
    if isinstance(expr, ast.Attribute):
        # self._lock → "_lock"
        return expr.attr
    elif isinstance(expr, ast.Name):
        return expr.id
    elif isinstance(expr, ast.Call):
        return get_lock_name_from_context(expr.func)
    return "?"


class LockArchAuditorV2(ast.NodeVisitor):
    """锁架构审计 V2 - 完整 Attribute 支持"""

    def __init__(self, filepath: str, target_locks: Set[str] = None):
        self.filepath = filepath
        self.target_locks = target_locks or set()
        self.violations: List[Dict] = []
        self.method_locks: Dict[str, int] = {}
        self.class_locks: Dict[str, Set[str]] = {}
        self.current_class = None
        self.current_method = None

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.class_locks[node.name] = set()
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_method = self.current_method
        self.current_method = node.name
        with_blocks = self._collect_with_blocks(node.body)
        self._analyze_with_chain(with_blocks, parent_locks=set(), method_node=node)
        locks_in_method = set()
        for wb in with_blocks:
            for item in wb.items:
                ln = get_lock_name_from_context(item.context_expr)
                if ln in self.target_locks:
                    locks_in_method.add(ln)
        if locks_in_method:
            self.method_locks[f"{self.current_class}.{node.name}"] = len(locks_in_method)
            for ln in locks_in_method:
                self.class_locks.setdefault(self.current_class, set()).add(ln)
        self.current_method = old_method

    def _collect_with_blocks(self, stmts: List[ast.stmt]) -> List[ast.With]:
        """递归收集 with 块 (R104 §12 铁律 #3 严禁 ast.walk 扁平化)"""
        result = []
        for stmt in stmts:
            if isinstance(stmt, ast.With):
                result.append(stmt)
                result.extend(self._collect_with_blocks(stmt.body))
            elif isinstance(stmt, ast.Try):
                for sub_stmt in stmt.body:
                    result.extend(self._collect_with_blocks([sub_stmt]))
                for sub_stmt in stmt.orelse:
                    result.extend(self._collect_with_blocks([sub_stmt]))
                for sub_stmt in stmt.finalbody:
                    result.extend(self._collect_with_blocks([sub_stmt]))
            elif isinstance(stmt, ast.If):
                for sub_stmt in stmt.body:
                    result.extend(self._collect_with_blocks([sub_stmt]))
                for sub_stmt in stmt.orelse:
                    result.extend(self._collect_with_blocks([sub_stmt]))
            elif isinstance(stmt, (ast.For, ast.While)):
                for sub_stmt in stmt.body:
                    result.extend(self._collect_with_blocks([sub_stmt]))
                for sub_stmt in stmt.orelse:
                    result.extend(self._collect_with_blocks([sub_stmt]))
        return result

    def _analyze_with_chain(self, with_blocks: List[ast.With],
                             parent_locks: Set[str], method_node: ast.FunctionDef):
        for wb in with_blocks:
            current_locks = parent_locks.copy()
            for item in wb.items:
                lock_name = get_lock_name_from_context(item.context_expr)
                if lock_name in self.target_locks:
                    if lock_name in parent_locks:
                        self.violations.append({
                            "type": "SAME_LOCK_NESTED",
                            "file": self.filepath,
                            "method": f"{self.current_class}.{self.current_method}",
                            "lock": lock_name,
                            "line": wb.lineno,
                            "severity": "P0",
                            "description": f"同方法内 {lock_name} 嵌套 (R100-F-P1-1 #8 铁律违反)"
                        })
                    else:
                        current_locks.add(lock_name)
            # R104 §12 铁律 #3: 递归进入 with.body
            inner_with_blocks = self._collect_with_blocks(wb.body)
            self._analyze_with_chain(inner_with_blocks, current_locks, method_node)
            # 长锁检测
            block_lines = self._count_block_lines(wb)
            if block_lines > 15:
                new_lock = ""
                for item in wb.items:
                    ln = get_lock_name_from_context(item.context_expr)
                    if ln in self.target_locks and ln not in parent_locks:
                        new_lock = ln
                        break
                self.violations.append({
                    "type": "LONG_LOCK",
                    "file": self.filepath,
                    "method": f"{self.current_class}.{self.current_method}",
                    "lock": new_lock or "?",
                    "line": wb.lineno,
                    "block_lines": block_lines,
                    "severity": "P1",
                    "description": f"长锁持锁 {block_lines} 行 (R100-F-P1-1 持锁 P99 < 1ms 目标)"
                })

    def _count_block_lines(self, with_node: ast.With) -> int:
        if not with_node.body:
            return 0
        first = with_node.body[0].lineno
        last = with_node.body[-1].end_lineno or with_node.body[-1].lineno
        return last - first + 1


def audit_file_v2(filepath: str, target_locks: Set[str] = None) -> Dict:
    if target_locks is None:
        target_locks = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except (UnicodeDecodeError, FileNotFoundError, PermissionError):
        return {"file": filepath, "error": "cannot read"}
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return {"file": filepath, "error": f"SyntaxError: {e}"}
    auditor = LockArchAuditorV2(filepath, target_locks)
    auditor.visit(tree)
    return {
        "file": filepath,
        "violations": auditor.violations,
        "method_locks": auditor.method_locks,
        "class_locks": auditor.class_locks,
    }


def auto_detect_locks(filepath: str) -> Set[str]:
    """自动检测文件中所有 self._xxx_lock 锁名"""
    import re
    locks = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # 找 self._xxx_lock = threading.XXXLock() 模式
        pattern = re.compile(r'self\.(_[a-zA-Z_][a-zA-Z0-9_]*_lock)\s*=\s*(?:threading\.)?(?:R?Lock)\(')
        for m in pattern.finditer(content):
            locks.add(m.group(1))
    except (UnicodeDecodeError, FileNotFoundError, PermissionError):
        pass
    return locks


if __name__ == "__main__":
    # 完整审计关键模块
    critical_files = [
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/events/event_bus.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/trading_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/market_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/notification_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/auto_training_pipeline.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/model_training_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/database_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/cache_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/data_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/services/network_service.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading_engine.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/plugin_manager.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/risk_manager.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/ai/config_impact_analyzer.py",
        "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/ai/config_recommendation_engine.py",
    ]
    summary = []
    for f in critical_files:
        locks = auto_detect_locks(f)
        result = audit_file_v2(f, locks)
        if "error" in result:
            print(f"\n=== {f} ===\nERROR: {result['error']}")
            continue
        n_same = sum(1 for v in result["violations"] if v["type"] == "SAME_LOCK_NESTED")
        n_long = sum(1 for v in result["violations"] if v["type"] == "LONG_LOCK")
        print(f"\n=== {os.path.basename(f)} ===")
        print(f"  锁数: {len(locks)} | 锁列表: {sorted(locks)}")
        print(f"  类: {list(result['class_locks'].keys())}")
        print(f"  持锁方法数: {len(result['method_locks'])}")
        print(f"  P0 锁嵌套: {n_same} | P1 长锁: {n_long}")
        # 列出关键 violations
        for v in result["violations"][:8]:
            print(f"  [{v['severity']}] {v['type']} @ L{v['line']} in {v['method']} ({v['lock']}): {v['description']}")
        summary.append({
            "file": os.path.basename(f),
            "locks": sorted(locks),
            "P0_nested": n_same,
            "P1_long": n_long,
            "n_violations": len(result["violations"]),
        })
    print("\n\n=== 总览 ===")
    for s in summary:
        print(f"{s['file']}: 锁 {len(s['locks'])} 把, P0={s['P0_nested']}, P1={s['P1_long']}, 共 {s['n_violations']} violations")
