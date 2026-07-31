#!/usr/bin/env python3
"""
R173-D 终极 ORPHAN_PUB/SUB 扫描脚本 v4
改进 v3:
1. 处理 tuple/list 模式: trading_events = [('event.name', handler), ...]
2. 处理 for-loop 模式: for event_name, handler in events: bus.subscribe(event_name, handler)
3. 使用 line-level 文本 grep 作为 fallback
4. 双轨检测: AST + Grep 文本
"""
import ast
import os
import re
import json
import sys
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "scripts", "components", "plugins", "models", "strategies", "backtest", "analysis", "utils", "data", "db", "config", "features", "optimization", "evaluation"]

SKIP_DIRS = {".git", ".codegraph", ".serena", ".claude", ".memory", ".mypy_cache", "__pycache__", ".cache", "docs", "icons", "QSSTheme", "drawio", "nginx", "node_modules", "venv", ".venv", "env", "resources", "data/cache", "data/databases"}

# 已知的非 event bus 信号名
QT_SIGNAL_NAMES = {
    "error", "warning", "info", "success", "failed", "completed", "progress",
    "data_ready", "started", "stopped", "finished", "message", "status",
    "log", "update", "changed", "clicked", "pressed", "released", "triggered",
    "toggled", "selected", "double_clicked", "text_changed", "value_changed",
}

PUB_SET: Dict[str, List[dict]] = defaultdict(list)
SUB_SET: Dict[str, List[dict]] = defaultdict(list)


def should_skip_dir(dirname: str) -> bool:
    if dirname in SKIP_DIRS:
        return True
    if dirname.startswith(".") and dirname not in {".audit", ".audit_r143", ".audit_r146", ".audit_r152", ".audit_r155", ".audit_r161"}:
        return True
    return False


def get_obj_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return ast.unparse(node)
    elif isinstance(node, ast.Name):
        return node.id
    return ""


def is_qt_signal(obj_name: str) -> bool:
    obj_lower = obj_name.lower()
    if "signal" in obj_lower:
        return True
    last_part = obj_name.split(".")[-1]
    if last_part in QT_SIGNAL_NAMES:
        return True
    return False


def is_event_bus_obj(obj_name: str) -> bool:
    obj_lower = obj_name.lower()
    if "signal" in obj_lower:
        return False
    if obj_lower in {"bus", "eb", "event_bus", "_event_bus", "_bus", "_eb", "eventbus", "_eventbus"}:
        return True
    if obj_lower.endswith(".bus") or obj_lower.endswith(".eb"):
        return True
    if obj_lower.endswith(".event_bus") or obj_lower.endswith(".eventbus"):
        return True
    if "event_bus" in obj_lower or "eventbus" in obj_lower:
        return True
    return False


def extract_event_name(node: ast.AST) -> Tuple[str, str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, "string"
    if isinstance(node, ast.Name):
        return node.id, "class"
    if isinstance(node, ast.Attribute):
        return ast.unparse(node), "enum"
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id, "class"
        elif isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func), "class"
    return ast.unparse(node), "unknown"


def extract_strings_from_tuple_list(node: ast.AST) -> List[str]:
    """从 [(string, handler), ...] 列表中提取所有字符串字面量"""
    strings = []
    if isinstance(node, ast.List) or isinstance(node, ast.Tuple):
        for elt in node.elts:
            if isinstance(elt, (ast.List, ast.Tuple)) and len(elt.elts) >= 1:
                first = elt.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    strings.append(first.value)
    return strings


def scan_file(filepath: Path):
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return

    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")

    # Phase 1: 直接的 bus.publish/subscribe 调用
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        method_name = func.attr
        if method_name not in ("publish", "publish_async", "emit", "subscribe", "subscribe_async", "subscribe_once", "on", "listen", "add_listener"):
            continue
        obj_name = get_obj_name(func.value)
        if not is_event_bus_obj(obj_name):
            continue
        if is_qt_signal(obj_name):
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        event_name, event_type = extract_event_name(first_arg)
        if not event_name or event_type == "unknown":
            continue
        line_no = node.lineno
        entry = {"file": f"{rel_path}:{line_no}", "type": event_type, "obj": obj_name}
        if method_name in ("publish", "publish_async", "emit"):
            PUB_SET[event_name].append(entry)
        else:
            SUB_SET[event_name].append(entry)

    # Phase 2: helper 函数 (e.g. _safe_publish)
    for func_node in ast.walk(tree):
        if not isinstance(func_node, ast.FunctionDef):
            continue
        for sub_node in ast.walk(func_node):
            if not isinstance(sub_node, ast.Call):
                continue
            if not isinstance(sub_node.func, ast.Attribute):
                continue
            if sub_node.func.attr not in ("publish", "publish_async", "emit", "subscribe", "subscribe_async", "subscribe_once"):
                continue
            if not sub_node.args:
                continue
            first_arg = sub_node.args[0]
            if not isinstance(first_arg, ast.Name):
                continue
            param_name = first_arg.id
            obj_name = get_obj_name(sub_node.func.value)
            if not is_event_bus_obj(obj_name):
                continue
            # 找该函数的所有调用方
            for call_node in ast.walk(tree):
                if not isinstance(call_node, ast.Call):
                    continue
                if not isinstance(call_node.func, ast.Name):
                    continue
                if call_node.func.id != func_node.name:
                    continue
                if call_node.args and isinstance(call_node.args[0], ast.Constant) and isinstance(call_node.args[0].value, str):
                    event_name = call_node.args[0].value
                    line_no = call_node.lineno
                    entry = {"file": f"{rel_path}:{line_no} (via {func_node.name})", "type": "string", "obj": "helper"}
                    if sub_node.func.attr in ("publish", "publish_async", "emit"):
                        PUB_SET[event_name].append(entry)
                    else:
                        SUB_SET[event_name].append(entry)

    # Phase 3.5: 变量引用的 tuple/list 模式
    # 模式: trading_events = [('event.name', handler), ...]
    #       for event_name, handler in trading_events: bus.subscribe(event_name, handler)
    for func_node in ast.walk(tree):
        if not isinstance(func_node, ast.FunctionDef):
            continue
        # 收集 func 内所有 List/Tuple 赋值给变量
        var_to_strings = {}  # var_name -> List[(string, line_no)]
        for stmt in ast.walk(func_node):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                var_name = stmt.targets[0].id
                strings = extract_strings_from_tuple_list(stmt.value)
                if strings:
                    var_to_strings[var_name] = [(s, stmt.lineno) for s in strings]

        # 找 for loops
        for stmt in ast.walk(func_node):
            if not isinstance(stmt, ast.For):
                continue
            if not isinstance(stmt.target, ast.Tuple) or len(stmt.target.elts) < 2:
                continue
            first_target = stmt.target.elts[0]
            if not isinstance(first_target, ast.Name):
                continue
            param_name = first_target.id
            # 检查 iter 是 Name (引用之前定义的变量)
            if not isinstance(stmt.iter, ast.Name):
                continue
            var_name = stmt.iter.id
            if var_name not in var_to_strings:
                continue
            strings = [s for s, _ in var_to_strings[var_name]]
            # 找 for body 中的 bus.subscribe/publish
            for body_node in ast.walk(stmt):
                if not isinstance(body_node, ast.Call):
                    continue
                if not isinstance(body_node.func, ast.Attribute):
                    continue
                if body_node.func.attr not in ("subscribe", "subscribe_async", "subscribe_once", "publish", "publish_async"):
                    continue
                obj_name = get_obj_name(body_node.func.value)
                if not is_event_bus_obj(obj_name):
                    continue
                if not body_node.args:
                    continue
                first_arg = body_node.args[0]
                if isinstance(first_arg, ast.Name) and first_arg.id == param_name:
                    for s, src_line in var_to_strings[var_name]:
                        line_no = stmt.lineno
                        entry = {"file": f"{rel_path}:{line_no} (var-ref pattern: {var_name}@{src_line} in {func_node.name})", "type": "string", "obj": obj_name}
                        if body_node.func.attr in ("subscribe", "subscribe_async", "subscribe_once"):
                            SUB_SET[s].append(entry)
                        else:
                            PUB_SET[s].append(entry)

    # Phase 4: Grep 模式 - 直接扫描 bus.subscribe/publish 的字符串字面量
    for line_no, line in enumerate(source.split("\n"), start=1):
        line_stripped = line.strip()
        if 'subscribe(' not in line_stripped and 'publish(' not in line_stripped:
            continue
        # 找字符串字面量
        m = re.search(r'\.subscribe\s*\(\s*[\'"]([^\'"]+)[\'"]', line)
        if m:
            event = m.group(1)
            if event not in SUB_SET or len([e for e in SUB_SET[event] if e.get('via_grep')]) == 0:
                SUB_SET[event].append({
                    "file": f"{rel_path}:{line_no}",
                    "type": "string",
                    "obj": "grep",
                    "via_grep": True,
                })
        m = re.search(r'\.publish\s*\(\s*[\'"]([^\'"]+)[\'"]', line)
        if m:
            event = m.group(1)
            if event not in PUB_SET or len([e for e in PUB_SET[event] if e.get('via_grep')]) == 0:
                PUB_SET[event].append({
                    "file": f"{rel_path}:{line_no}",
                    "type": "string",
                    "obj": "grep",
                    "via_grep": True,
                })


def main():
    files_scanned = 0
    for scan_dir in SCAN_DIRS:
        dir_path = ROOT / scan_dir
        if not dir_path.exists():
            continue
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not should_skip_dir(d)]
            for f in files:
                if not f.endswith(".py"):
                    continue
                fp = Path(root) / f
                scan_file(fp)
                files_scanned += 1

    for f in ROOT.iterdir():
        if f.suffix == ".py" and f.is_file():
            scan_file(f)
            files_scanned += 1

    pub_keys = set(PUB_SET.keys())
    sub_keys = set(SUB_SET.keys())
    orphan_pub = pub_keys - sub_keys
    orphan_sub = sub_keys - pub_keys
    matched = pub_keys & sub_keys

    result = {
        "files_scanned": files_scanned,
        "publish_total_events": len(pub_keys),
        "subscribe_total_events": len(sub_keys),
        "matched_events": len(matched),
        "ORPHAN_PUB_count": len(orphan_pub),
        "ORPHAN_SUB_count": len(orphan_sub),
        "ORPHAN_PUB": {k: PUB_SET[k] for k in sorted(orphan_pub)},
        "ORPHAN_SUB": {k: SUB_SET[k] for k in sorted(orphan_sub)},
        "matched": {k: {"pub": PUB_SET[k], "sub": SUB_SET[k]} for k in sorted(matched)},
    }

    out_path = ROOT / ".trae/reports/rounds/_r173_d_orphan_scan_v4.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Files scanned: {files_scanned}")
    print(f"Publish unique events: {len(pub_keys)}")
    print(f"Subscribe unique events: {len(sub_keys)}")
    print(f"Matched: {len(matched)}")
    print(f"ORPHAN_PUB: {len(orphan_pub)}")
    print(f"ORPHAN_SUB: {len(orphan_sub)}")
    print(f"\nResult saved to: {out_path}")

    # 关键事件核验
    print("\n=== 关键事件核验 ===")
    for ev in [
        "bettafish.sentiment.analysis.completed",
        "order_fill_saved",
        "free_stockdb.connected",
        "free_stockdb.disconnected",
        "free_stockdb.health.changed",
        "free_stockdb.error",
    ]:
        if ev in matched:
            status = "MATCHED ✓"
        elif ev in orphan_pub:
            status = "ORPHAN_PUB (真无订阅)"
        elif ev in orphan_sub:
            status = "ORPHAN_SUB (真无发布)"
        else:
            status = "NOT_FOUND"
        print(f"  {ev}: {status}")
        if ev in PUB_SET:
            for entry in PUB_SET[ev]:
                print(f"    PUB: {entry['file']}")
        if ev in SUB_SET:
            for entry in SUB_SET[ev]:
                print(f"    SUB: {entry['file']}")


if __name__ == "__main__":
    main()
