#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R197-A 4 源验证 - 窗口验证修复行"""
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 3 个待二次验证的修复位置 (跨行 logger 调用)
fixes = [
    ("core/webgpu/pipeline_optimizer.py", 290),
    ("core/advanced_optimization/performance/thread_monitor.py", 326),
    ("core/ui/panels/base_panel.py", 186),
]

print("=" * 80)
print("R+1 round 4 源验证 1 改进版 - 窗口验证 (修复行 + 后续 2 行)")
print("=" * 80)

for file_path, line in fixes:
    p = PROJECT_ROOT / file_path
    content = p.read_text(encoding="utf-8", errors="ignore")
    lines = content.split("\n")
    # 读取 line-1, line, line+1 三行作为窗口
    start = max(0, line - 2)
    end = min(len(lines), line + 2)
    window = lines[start:end]
    window_str = "\n".join(window)
    has_exc_info = "exc_info=True" in window_str
    has_r197 = "R197-A" in window_str
    status = "PASS" if has_exc_info else "FAIL"
    marker = "[OK]" if status == "PASS" else "[X]"
    print(f"{marker} {file_path}:L{line} status={status}")
    print(f"    exc_info=True: {has_exc_info}")
    print(f"    R197-A 注释: {has_r197}")
    print(f"    窗口内容:")
    for i, l in enumerate(window, start=line - 1):
        print(f"      L{i}: {l.strip()[:120]}")
    print()
