"""R163-C: 读取 JSON 扫描结果, 输出 TOP 16 文件清单 + 优先级分类"""
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

with open(PROJECT_ROOT / "tools" / "_r163_c_scan_result.json", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 70)
print("R163-C: 全项目 logger.exc_info 缺失扫描 (4 子目录: core/gui/web/tests)")
print("=" * 70)
print()
print("Summary (4 子目录, 已排除 19+ R145/R161/R162/R163-A 闭环文件):")
for p, s in data["summary"].items():
    print(f"  {p}: {s['files']} files, {s['total_violations']} except missing, "
          f"missing={s['missing_exc_info']}, optional-dep={s['optional_import']}")
print()
print(f"Total missing: {data['total_missing']}")
print(f"  其中 optional-dep ImportError (R85 反例, 不修): "
      f"{sum(s['optional_import'] for s in data['summary'].values())}")
print()

# TOP files by missing count
file_counts = []
for p in ["P0", "P1", "P2", "P3"]:
    for f in data["results_by_file"].get(p, []):
        cnt = sum(1 for v in f["violations"]
                  if not v.get("is_optional_import") and v["logger_calls"])
        file_counts.append((f["file"], cnt, p))

file_counts.sort(key=lambda x: -x[1])
print("=" * 70)
print("TOP 30 files by missing count:")
print("=" * 70)
for i, (f, c, p) in enumerate(file_counts[:30], 1):
    print(f"  {i:2d}. {p} {c:4d}  {f}")
print()

# TOP 16 file sum
top16 = file_counts[:16]
top16_sum = sum(c for _, c, _ in top16)
print(f"TOP 16 file 总 missing: {top16_sum}")
print(f"vs R160-D 估值 867: 偏差 {top16_sum - 867} 处 ({(top16_sum - 867) / 867 * 100:+.1f}%)")
print()

# 详细输出每个 TOP 16 文件的所有 missing 行号
print("=" * 70)
print("TOP 16 文件详细 missing 行号 (file:line 列表)")
print("=" * 70)
for i, (fname, _, p) in enumerate(top16, 1):
    file_data = None
    for fp in data["results_by_file"].get(p, []):
        if fp["file"] == fname:
            file_data = fp
            break
    if not file_data:
        continue
    missing_lines = []
    for v in file_data["violations"]:
        if v.get("is_optional_import"):
            continue
        for lc in v["logger_calls"]:
            missing_lines.append((lc["line"], lc["method"]))
    missing_lines.sort()
    print(f"\n{i}. {fname} ({p}, {len(missing_lines)} 处)")
    # 仅显示前 10 个行号
    for line, method in missing_lines[:10]:
        print(f"   L{line}: logger.{method}")
    if len(missing_lines) > 10:
        print(f"   ... + {len(missing_lines) - 10} more")

# 统计每个子目录的分布
print()
print("=" * 70)
print("按子目录分布:")
print("=" * 70)
subdir_counts = {"core": 0, "gui": 0, "web": 0, "tests": 0}
for f, c, p in file_counts:
    rel = f.replace("\\", "/")
    if rel.startswith("core/"):
        subdir_counts["core"] += c
    elif rel.startswith("gui/"):
        subdir_counts["gui"] += c
    elif rel.startswith("web/"):
        subdir_counts["web"] += c
    elif rel.startswith("tests/") or "/tests/" in rel:
        subdir_counts["tests"] += c
for sd, cnt in subdir_counts.items():
    print(f"  {sd}: {cnt} missing")

# 统计 P0 业务核心
print()
print("=" * 70)
print("P0 业务核心文件 + 缺失数 (按 file:line 列表):")
print("=" * 70)
p0_files = [f for f, c, p in file_counts if p == "P0"]
p0_total = sum(c for _, c, _ in file_counts if p == "P0")
print(f"P0 总文件: {len(p0_files)}, 总 missing: {p0_total}")
print()
for fname in p0_files[:20]:
    file_data = None
    for fp in data["results_by_file"].get("P0", []):
        if fp["file"] == fname:
            file_data = fp
            break
    if not file_data:
        continue
    missing_lines = []
    for v in file_data["violations"]:
        if v.get("is_optional_import"):
            continue
        for lc in v["logger_calls"]:
            missing_lines.append((lc["line"], lc["method"]))
    missing_lines.sort()
    print(f"  {fname} ({len(missing_lines)} 处)")
    for line, method in missing_lines[:5]:
        print(f"    L{line}: logger.{method}")
    if len(missing_lines) > 5:
        print(f"    ... + {len(missing_lines) - 5} more")
