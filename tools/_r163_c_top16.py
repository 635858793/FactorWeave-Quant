"""R163-C: 简化版分析 - 直接读取 JSON 并输出"""
import json
import sys

PROJECT_ROOT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"

with open(PROJECT_ROOT + r"\tools\_r163_c_scan_result.json", encoding="utf-8") as f:
    data = json.load(f)

out = []
out.append("=" * 70)
out.append("R163-C: 全项目 logger.exc_info 缺失扫描 (4 子目录: core/gui/web/tests)")
out.append("=" * 70)
out.append("")
out.append("Summary (已排除 R145/R161/R162/R163-A 闭环文件):")
for p, s in data["summary"].items():
    out.append(f"  {p}: {s['files']} files, {s['total_violations']} except missing, "
               f"missing={s['missing_exc_info']}, optional-dep={s['optional_import']}")
out.append("")
out.append(f"Total missing: {data['total_missing']}")
out.append("")

# TOP files
file_counts = []
for p in ["P0", "P1", "P2", "P3"]:
    for f in data["results_by_file"].get(p, []):
        cnt = sum(1 for v in f["violations"]
                  if not v.get("is_optional_import") and v["logger_calls"])
        file_counts.append((f["file"], cnt, p))

file_counts.sort(key=lambda x: -x[1])
out.append("=" * 70)
out.append("TOP 30 files by missing count:")
out.append("=" * 70)
for i, (f, c, p) in enumerate(file_counts[:30], 1):
    out.append(f"  {i:2d}. {p} {c:4d}  {f}")
out.append("")

# TOP 16
top16 = file_counts[:16]
top16_sum = sum(c for _, c, _ in top16)
out.append(f"TOP 16 file 总 missing: {top16_sum}")
out.append(f"vs R160-D 估值 867: 偏差 {top16_sum - 867} ({(top16_sum - 867) / 867 * 100:+.1f}%)")
out.append("")

# Subdir
out.append("=" * 70)
out.append("按子目录分布:")
out.append("=" * 70)
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
    out.append(f"  {sd}: {cnt} missing")

# 写入文件
with open(PROJECT_ROOT + r"\tools\_r163_c_top_analysis.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print("Wrote to _r163_c_top_analysis.txt")
print(f"Lines: {len(out)}")
