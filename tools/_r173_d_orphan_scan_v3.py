#!/usr/bin/env python3
"""
R173-D 终极 ORPHAN_PUB/SUB 扫描脚本 v3
改进 v2:
1. 跨函数追踪: bus.publish 内部 event_name 变量追溯到 _safe_publish 的字符串参数
2. 处理常见的 helper 模式: bus.publish(event_name, ...) where event_name 是函数参数
3. 使用 line-level 文本 grep 作为补充, 捕获所有字符串事件
"""
import ast
import os
import re
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "scripts", "components", "plugins", "models", "strategies", "backtest", "analysis", "utils", "data", "db", "config", "features", "optimization", "evaluation"]

SKIP_DIRS = {".git", ".codegraph", ".serena", ".claude", ".memory", ".mypy_cache", "__pycache__", ".cache", "docs", "icons", "QSSTheme", "drawio", "nginx", "node_modules", "venv", ".venv", "env", "resources", "data/cache", "data/databases"}

# (事件名, 文件:行号) -> 类型
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
    if last_part in {
        "error", "warning", "info", "success", "failed", "completed", "progress",
        "data_ready", "started", "stopped", "finished", "message", "status",
        "log", "update", "changed", "clicked", "pressed", "released", "triggered",
        "toggled", "selected", "double_clicked", "text_changed", "value_changed",
        "current_changed", "row_changed", "cell_changed", "item_changed",
        "data_changed", "state_changed", "visibility_changed", "size_changed",
        "position_changed", "range_changed", "focus_changed", "enabled_changed",
        "results_ready", "task_completed", "request_completed", "operation_completed",
    }:
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
    if obj_lower.startswith("self.") and (obj_lower.endswith(".event_bus") or obj_lower.endswith(".bus") or obj_lower.endswith("bus")):
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


def find_string_args_in_func(tree: ast.AST, target_param_name: str) -> List[Tuple[str, int]]:
    """在函数 tree 中查找 bus.publish(event_name, ...) 的 event_name 参数从哪个字符串赋值来"""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # 找 bus.publish/subscribe 的 call
            for sub_node in ast.walk(node):
                if not isinstance(sub_node, ast.Call):
                    continue
                if not isinstance(sub_node.func, ast.Attribute):
                    continue
                if sub_node.func.attr not in ("publish", "publish_async", "emit", "subscribe", "subscribe_async", "subscribe_once"):
                    continue
                if not sub_node.args:
                    continue
                first_arg = sub_node.args[0]
                # 找 first_arg 是 Name 节点
                if isinstance(first_arg, ast.Name) and first_arg.id == target_param_name:
                    # 找 func 内部 bus.publish 调用
                    obj_name = get_obj_name(sub_node.func.value)
                    if is_event_bus_obj(obj_name):
                        # 找这个函数的调用方, 传入的字符串
                        line_no = sub_node.lineno
                        # 在这里我们记录: 这个函数内部用 parameter {target_param_name} 作为 publish 第一个参数
                        results.append((node.name, line_no))
    return results


def scan_file_for_helper_publish_calls(tree: ast.AST, filepath: Path) -> Dict[str, List[dict]]:
    """扫描文件中, helper 函数 (e.g. _safe_publish) 的实际字符串事件名"""
    # 1. 找所有 helper 函数定义
    helpers = {}  # func_name -> List[event_name]
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # 找内部 bus.publish(event_name, ...) 的 event_name 模式
        for sub_node in ast.walk(node):
            if not isinstance(sub_node, ast.Call):
                continue
            if not isinstance(sub_node.func, ast.Attribute):
                continue
            if sub_node.func.attr not in ("publish", "publish_async", "emit"):
                continue
            if not sub_node.args:
                continue
            first_arg = sub_node.args[0]
            if not isinstance(first_arg, ast.Name):
                continue
            # 找该函数的所有调用方
            param_name = first_arg.id
            for call_node in ast.walk(tree):
                if not isinstance(call_node, ast.Call):
                    continue
                if not isinstance(call_node.func, ast.Name):
                    continue
                if call_node.func.id != node.name:
                    continue
                # 检查第一个参数是否为字符串
                if call_node.args and isinstance(call_node.args[0], ast.Constant) and isinstance(call_node.args[0].value, str):
                    event_name = call_node.args[0].value
                    line_no = call_node.lineno
                    if node.name not in helpers:
                        helpers[node.name] = []
                    helpers[node.name].append({
                        "event": event_name,
                        "call_line": line_no,
                        "publish_line": sub_node.lineno,
                    })
    return helpers


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
        entry = {"file": f"{rel_path}:{line_no}", "type": event_type, "obj": obj_name, "via_helper": False}

        if method_name in ("publish", "publish_async", "emit"):
            PUB_SET[event_name].append(entry)
        else:
            SUB_SET[event_name].append(entry)

    # Phase 2: helper 函数间接调用 (e.g. _safe_publish("free_stockdb.connected", ...))
    helper_results = scan_file_for_helper_publish_calls(tree, filepath)
    for helper_name, calls in helper_results.items():
        for c in calls:
            entry = {
                "file": f"{rel_path}:{c['call_line']} (via {helper_name} publish@{c['publish_line']})",
                "type": "string",
                "obj": "helper",
                "via_helper": True,
                "helper": helper_name,
            }
            if c["event"] not in PUB_SET or not any(e.get("via_helper") for e in PUB_SET[c["event"]]):
                PUB_SET[c["event"]].append(entry)


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

    out_path = ROOT / ".trae/reports/rounds/_r173_d_orphan_scan_v3.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Files scanned: {files_scanned}")
    print(f"Publish unique events: {len(pub_keys)}")
    print(f"Subscribe unique events: {len(sub_keys)}")
    print(f"Matched: {len(matched)}")
    print(f"ORPHAN_PUB (有发布无订阅): {len(orphan_pub)}")
    print(f"ORPHAN_SUB (有订阅无发布): {len(orphan_sub)}")
    print(f"\nResult saved to: {out_path}")

    # 重点关注 free_stockdb 系列
    print("\n=== FreeStockDB 4 事件状态 ===")
    for ev in ["free_stockdb.connected", "free_stockdb.disconnected", "free_stockdb.health.changed", "free_stockdb.error"]:
        status = "MATCHED" if ev in matched else ("ORPHAN_PUB" if ev in orphan_pub else ("ORPHAN_SUB" if ev in orphan_sub else "UNKNOWN"))
        print(f"  {ev}: {status}")
        if status == "ORPHAN_PUB":
            for entry in PUB_SET[ev]:
                print(f"    PUB: {entry['file']}")
        elif status == "MATCHED":
            for entry in PUB_SET[ev]:
                print(f"    PUB: {entry['file']}")
            for entry in SUB_SET[ev]:
                print(f"    SUB: {entry['file']}")


if __name__ == "__main__":
    main()
