#!/usr/bin/env python3
"""
R173-D 精细化 ORPHAN_PUB/SUB 扫描脚本 v2
改进:
1. 提取事件类名 (e.g. MyEvent(...) -> MyEvent)
2. 过滤 Qt Signal emit (e.g. self.signals.error.emit)
3. 限定 obj 为 event bus 模式 (bus, event_bus, _event_bus, _bus, eb, _eb, _eventBus 等)
4. 区分: 字符串事件 vs 枚举事件 vs 类事件
"""
import ast
import os
import re
import sys
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")
SCAN_DIRS = ["core", "gui", "web", "tests", "scripts", "components", "plugins", "models", "strategies", "backtest", "analysis", "utils", "data", "db", "config", "features", "optimization", "evaluation"]

# 跳过目录
SKIP_DIRS = {".git", ".codegraph", ".serena", ".claude", ".memory", ".mypy_cache", "__pycache__", ".cache", "docs", "icons", "QSSTheme", "drawio", "nginx", "node_modules", "venv", ".venv", "env", "resources", "data/cache", "data/databases"}

# event bus 对象的常见命名 (obj= 前缀)
EVENT_BUS_OBJ_NAMES = {
    "bus", "event_bus", "_event_bus", "_bus", "eb", "_eb",
    "self.bus", "self.event_bus", "self._event_bus", "self._bus", "self.eb", "self._eb",
    "eventBus", "self.eventBus", "_eventBus", "self._eventBus",
}

# 已知非 event bus 的常见 Qt Signal 名
QT_SIGNAL_NAMES = {
    "error", "warning", "info", "success", "failed", "completed", "progress",
    "data_ready", "started", "stopped", "finished", "message", "status",
    "log", "update", "changed", "clicked", "pressed", "released", "triggered",
    "toggled", "selected", "double_clicked", "text_changed", "value_changed",
    "current_changed", "row_changed", "cell_changed", "item_changed",
    "data_changed", "state_changed", "visibility_changed", "size_changed",
    "position_changed", "range_changed", "focus_changed", "enabled_changed",
    "results_ready", "task_completed", "request_completed", "operation_completed",
}

PUB_SET = defaultdict(list)
SUB_SET = defaultdict(list)


def should_skip_dir(dirname: str) -> bool:
    if dirname in SKIP_DIRS:
        return True
    if dirname.startswith(".") and dirname not in {".audit", ".audit_r143", ".audit_r146", ".audit_r152", ".audit_r155", ".audit_r161"}:
        return True
    return False


def get_obj_name(node: ast.AST) -> str:
    """获取调用对象名 (e.g. self.bus.publish -> self.bus)"""
    if isinstance(node, ast.Attribute):
        return ast.unparse(node)
    elif isinstance(node, ast.Name):
        return node.id
    return ""


def is_event_bus_obj(obj_name: str) -> bool:
    """判断是否是 event bus 对象"""
    obj_lower = obj_name.lower()
    if "signal" in obj_lower:
        return False
    if obj_name in EVENT_BUS_OBJ_NAMES:
        return True
    if "event_bus" in obj_lower or "eventbus" in obj_lower:
        return True
    if obj_lower in {"bus", "eb"}:
        return True
    if obj_lower.endswith(".bus") or obj_lower.endswith(".eb"):
        return True
    return False


def is_qt_signal(obj_name: str) -> bool:
    """判断是否是 Qt Signal 调用"""
    obj_lower = obj_name.lower()
    if "signal" in obj_lower:
        return True
    last_part = obj_name.split(".")[-1]
    if last_part in QT_SIGNAL_NAMES:
        # 需要进一步判断上下文, 但作为启发式
        return True
    return False


def extract_event_name(node: ast.AST) -> Tuple[str, str]:
    """
    提取事件名
    返回: (event_name, event_type) 其中 event_type 是 'string' | 'enum' | 'class' | 'unknown'
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, "string"
    if isinstance(node, ast.Name):
        return node.id, "class"
    if isinstance(node, ast.Attribute):
        # EventType.SOMETHING
        return ast.unparse(node), "enum"
    if isinstance(node, ast.Call):
        # MyEvent(...) - 提取类名
        if isinstance(node.func, ast.Name):
            return node.func.id, "class"
        elif isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func), "class"
    return ast.unparse(node), "unknown"


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

        # 过滤: 只保留 event bus 调用
        if not is_event_bus_obj(obj_name):
            continue
        # 过滤: Qt Signal
        if is_qt_signal(obj_name):
            continue

        if not node.args:
            continue
        first_arg = node.args[0]
        event_name, event_type = extract_event_name(first_arg)
        if not event_name or event_type == "unknown":
            continue

        line_no = node.lineno
        entry = f"{rel_path}:{line_no}"

        if method_name in ("publish", "publish_async", "emit"):
            PUB_SET[event_name].append({"file": entry, "type": event_type, "obj": obj_name})
        else:
            SUB_SET[event_name].append({"file": entry, "type": event_type, "obj": obj_name})


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

    out_path = ROOT / ".trae/reports/rounds/_r173_d_orphan_scan_v2.json"
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

    if orphan_pub:
        print("\n=== ORPHAN_PUB ===")
        for k in sorted(orphan_pub):
            types = set(e["type"] for e in PUB_SET[k])
            print(f"  [{','.join(types)}] {k} (publish x {len(PUB_SET[k])}):")
            for entry in PUB_SET[k][:3]:
                print(f"    {entry['file']}")
            if len(PUB_SET[k]) > 3:
                print(f"    ... and {len(PUB_SET[k]) - 3} more")

    if orphan_sub:
        print("\n=== ORPHAN_SUB ===")
        for k in sorted(orphan_sub):
            types = set(e["type"] for e in SUB_SET[k])
            print(f"  [{','.join(types)}] {k} (subscribe x {len(SUB_SET[k])}):")
            for entry in SUB_SET[k][:3]:
                print(f"    {entry['file']}")
            if len(SUB_SET[k]) > 3:
                print(f"    ... and {len(SUB_SET[k]) - 3} more")


if __name__ == "__main__":
    main()
