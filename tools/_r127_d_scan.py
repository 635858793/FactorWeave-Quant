"""R127 子智能体 D 扫描脚本: 多账户隔离全局扫描 (4 子目录)"""
import os
import re
from pathlib import Path

# 4 子目录扫描
TARGET_DIRS = ["core", "gui", "plugins", "tests", "strategies", "web", "scripts"]
EXCLUDE_PATTERNS = [r"\.pytest_cache", r"\.codegraph", r"node_modules", r"__pycache__"]

# 模式
PATTERNS = {
    "self.current_positions": r"self\.current_positions\b",
    "self._current_positions": r"self\._current_positions\b",
    "self.positions (AdaptiveStopLoss)": r"self\.positions\b",
    "current_positions (no self)": r"\bcurrent_positions\b",
    "_current_positions_v2": r"_current_positions_v2\b",
    "AdaptiveStopLoss usage": r"AdaptiveStopLoss\b",
    "AccountSwitchedEvent usage": r"AccountSwitchedEvent\b",
    "_current_account_id": r"_current_account_id\b",
    "set_current_account_id": r"set_current_account_id\b",
    "_on_account_switched": r"_on_account_switched\b",
    "_check_position_limit": r"_check_position_limit\b",
    "_check_and_mark_stop_loss": r"_check_and_mark_stop_loss\b",
    "_position_key": r"_position_key\b",
    "stop_loss.positions": r"stop_loss\._|self\.stop_loss\._",
}

results = {}
for pat_name, pat in PATTERNS.items():
    results[pat_name] = []

project_root = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui")

for target_dir in TARGET_DIRS:
    dir_path = project_root / target_dir
    if not dir_path.exists():
        continue

    for py_file in dir_path.rglob("*.py"):
        file_str = str(py_file)
        # 排除
        if any(re.search(p, file_str) for p in EXCLUDE_PATTERNS):
            continue

        try:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"READ ERROR: {py_file}: {e}")
            continue

        rel = py_file.relative_to(project_root).as_posix()
        for pat_name, pat in PATTERNS.items():
            for i, line in enumerate(lines, 1):
                if re.search(pat, line):
                    line_clean = line.rstrip("\n").rstrip("\r")
                    if len(line_clean) > 120:
                        line_clean = line_clean[:117] + "..."
                    results[pat_name].append((rel, i, line_clean))

# 输出到文件
out_file = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r127_d_scan_out.txt"
out_lines = []
for pat_name, hits in results.items():
    out_lines.append(f"\n=== {pat_name}: {len(hits)} hits ===")
    for rel, line_no, line_text in hits[:80]:
        out_lines.append(f"  {rel}:{line_no}: {line_text}")
    if len(hits) > 80:
        out_lines.append(f"  ... (还有 {len(hits) - 80} 个匹配)")

with open(out_file, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))
print(f"结果已写入 {out_file}")
