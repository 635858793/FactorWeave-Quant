"""R163-C: 输出每个 TOP 文件的详细 file:line 列表 + P0 业务核心详细"""
import json
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

with open(PROJECT_ROOT / "tools" / "_r163_c_scan_result.json", encoding="utf-8") as f:
    data = json.load(f)

# 收集所有 P0 文件的详细 file:line
p0_files_data = []
for f in data["results_by_file"].get("P0", []):
    missing_lines = []
    for v in f["violations"]:
        if v.get("is_optional_import"):
            continue
        for lc in v["logger_calls"]:
            missing_lines.append({
                "line": lc["line"],
                "method": lc["method"],
                "except_line": v["line"],
                "except_type": v["except_type"],
            })
    missing_lines.sort(key=lambda x: x["line"])
    p0_files_data.append({
        "file": f["file"],
        "count": len(missing_lines),
        "lines": missing_lines,
    })

p0_files_data.sort(key=lambda x: -x["count"])

# TOP 16 详情
file_counts = []
for p in ["P0", "P1", "P2", "P3"]:
    for f in data["results_by_file"].get(p, []):
        cnt = sum(1 for v in f["violations"]
                  if not v.get("is_optional_import") and v["logger_calls"])
        file_counts.append((f["file"], cnt, p))
file_counts.sort(key=lambda x: -x[1])
top16 = file_counts[:16]

# 输出 P0 完整列表
out = []
out.append("=" * 70)
out.append("P0 业务核心文件 (570 处 missing, 30 文件)")
out.append("=" * 70)
for pfd in p0_files_data:
    out.append(f"\n## {pfd['file']} ({pfd['count']} 处 missing)")
    for line_info in pfd["lines"]:
        out.append(f"  L{line_info['line']}: logger.{line_info['method']} "
                   f"(except {line_info['except_type']} @ L{line_info['except_line']})")

with open(PROJECT_ROOT / "tools" / "_r163_c_p0_detail.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"P0 detail written: {len(p0_files_data)} files")
print(f"Total P0 missing: {sum(p['count'] for p in p0_files_data)}")

# TOP 16 详细列表
out2 = []
out2.append("=" * 70)
out2.append("TOP 16 文件详细 (1154 处 missing)")
out2.append("=" * 70)

for i, (fname, _, p) in enumerate(top16, 1):
    # 找文件数据
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
    out2.append(f"\n## {i}. {fname} ({p}, {len(missing_lines)} 处)")
    for line, method in missing_lines:
        out2.append(f"  L{line}: logger.{method}")

with open(PROJECT_ROOT / "tools" / "_r163_c_top16_detail.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out2))

print(f"TOP 16 detail written: {len(top16)} files")
print(f"Total TOP 16 missing: {sum(c for _, c, _ in top16)}")
