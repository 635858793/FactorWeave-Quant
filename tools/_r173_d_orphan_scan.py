#!/usr/bin/env python3
"""
R173-D 全项目 ORPHAN_PUB/SUB 扫描脚本
扫描范围: core/ + gui/ + web/ + tests/ + scripts/ + 主项目文件
目标: 找出所有 publish/subscribe 调用, 计算差集 (ORPHAN)
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

# 跳过文件
SKIP_FILES = set()

# 输出
PUB_SET = defaultdict(list)  # event_name -> [file:line]
SUB_SET = defaultdict(list)  # event_name -> [file:line]


def should_skip_dir(dirname: str) -> bool:
    """判断是否跳过目录"""
    if dirname in SKIP_DIRS:
        return True
    if dirname.startswith(".") and dirname not in {".audit", ".audit_r143", ".audit_r146", ".audit_r152", ".audit_r155", ".audit_r161"}:
        return True
    return False


def is_event_bus_call(node: ast.Call) -> Tuple[str, str]:
    """
    识别 event_bus.publish/subscribe 调用, 返回 (method, event_arg)
    method: 'publish' or 'subscribe' or 'unsubscribe' or ''
    event_arg: 事件名 (str) or 事件类名 (str) or ''
    """
    func = node.func
    method_name = ""
    if isinstance(func, ast.Attribute):
        method_name = func.attr
    elif isinstance(func, ast.Name):
        method_name = func.id
    else:
        return "", ""

    if method_name not in ("publish", "subscribe", "unsubscribe", "publish_async", "subscribe_async", "subscribe_once", "on", "off", "emit", "listen", "add_listener", "remove_listener"):
        return "", ""

    # 提取第一个参数 (事件名/事件类)
    if not node.args:
        return method_name, ""

    first_arg = node.args[0]
    event_name = ""

    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        event_name = first_arg.value
    elif isinstance(first_arg, ast.Name):
        event_name = first_arg.id
    elif isinstance(first_arg, ast.Attribute):
        event_name = ast.unparse(first_arg)
    elif isinstance(first_arg, ast.Call):
        # 函数调用返回事件类, 例如 EventType.X
        event_name = ast.unparse(first_arg)

    return method_name, event_name


def scan_file(filepath: Path):
    """扫描单个 Python 文件"""
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return

    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            method, event = is_event_bus_call(node)
            if not method or not event:
                continue
            # 排除 self.publish 这种 (虽然 publish/subscribe 是方法)
            # 进一步判断 func 的对象名 (e.g. bus.publish / self.bus.publish)
            func = node.func
            obj_name = ""
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                obj_name = func.value.id
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
                obj_name = ast.unparse(func.value)

            line_no = node.lineno
            entry = f"{rel_path}:{line_no} (obj={obj_name})"

            if method in ("publish", "publish_async", "emit"):
                PUB_SET[event].append(entry)
            elif method in ("subscribe", "subscribe_async", "subscribe_once", "on", "listen", "add_listener"):
                SUB_SET[event].append(entry)
            elif method in ("unsubscribe", "off", "remove_listener"):
                # 不计
                pass


def main():
    files_scanned = 0
    for scan_dir in SCAN_DIRS:
        dir_path = ROOT / scan_dir
        if not dir_path.exists():
            continue
        for root, dirs, files in os.walk(dir_path):
            # 过滤目录
            dirs[:] = [d for d in dirs if not should_skip_dir(d)]
            for f in files:
                if not f.endswith(".py"):
                    continue
                if f in SKIP_FILES:
                    continue
                fp = Path(root) / f
                scan_file(fp)
                files_scanned += 1

    # 额外扫描根目录 .py
    for f in ROOT.iterdir():
        if f.suffix == ".py" and f.is_file():
            scan_file(f)
            files_scanned += 1

    # 计算 ORPHAN
    pub_keys = set(PUB_SET.keys())
    sub_keys = set(SUB_SET.keys())

    orphan_pub = pub_keys - sub_keys  # 有发布无订阅
    orphan_sub = sub_keys - pub_keys  # 有订阅无发布
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
        "all_pub": {k: PUB_SET[k] for k in sorted(pub_keys)},
        "all_sub": {k: SUB_SET[k] for k in sorted(sub_keys)},
    }

    out_path = ROOT / ".trae/reports/rounds/_r173_d_orphan_scan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Files scanned: {files_scanned}")
    print(f"Publish unique events: {len(pub_keys)}")
    print(f"Subscribe unique events: {len(sub_keys)}")
    print(f"Matched: {len(matched)}")
    print(f"ORPHAN_PUB (有发布无订阅): {len(orphan_pub)}")
    print(f"ORPHAN_SUB (有订阅无发布): {len(orphan_sub)}")
    print(f"\nFull result saved to: {out_path}")

    # 打印详细 ORPHAN
    if orphan_pub:
        print("\n=== ORPHAN_PUB (有发布无订阅) ===")
        for k in sorted(orphan_pub):
            print(f"  {k} (publish x {len(PUB_SET[k])}):")
            for entry in PUB_SET[k][:5]:
                print(f"    {entry}")
            if len(PUB_SET[k]) > 5:
                print(f"    ... and {len(PUB_SET[k]) - 5} more")

    if orphan_sub:
        print("\n=== ORPHAN_SUB (有订阅无发布) ===")
        for k in sorted(orphan_sub):
            print(f"  {k} (subscribe x {len(SUB_SET[k])}):")
            for entry in SUB_SET[k][:5]:
                print(f"    {entry}")
            if len(SUB_SET[k]) > 5:
                print(f"    ... and {len(SUB_SET[k]) - 5} more")


if __name__ == "__main__":
    main()
