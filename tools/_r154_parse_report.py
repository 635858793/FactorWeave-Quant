#!/usr/bin/env python3
"""R154 子智能体 D: 解析 R51 lint 报告, 提取 P1 violations 全列表"""
import re
import json
from collections import defaultdict, Counter

REPORT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_r51_scan_output.json"

with open(REPORT, "r", encoding="utf-8") as f:
    text = f.read()

# 提取统计
stats = {
    "P1": int(re.search(r"P1 违规数: (\d+)", text).group(1)),
    "P2": int(re.search(r"P2 违规数: (\d+)", text).group(1)),
    "files": int(re.search(r"扫描文件数: (\d+)", text).group(1)),
    "exempt": int(re.search(r"R118 豁免位置数: (\d+)", text).group(1)),
}

# 解析每条 violation
pattern = re.compile(
    r"\[(\d+)\] (P[12]) (\S+?):(\d+) \((.+?)\)\n\s*except: (\S+)\n\s*上下文:\n(.*?)(?=\n\[\d+\]|\Z)",
    re.DOTALL
)
violations = []
for m in pattern.finditer(text):
    idx, sev, file, line, method, exc, ctx = m.groups()
    # 提取 code snippet
    ctx_clean = ctx.strip()
    # 提取 logger 等级
    log_match = re.search(r"(logger\.(debug|info|warning|error))", ctx)
    log_level = log_match.group(2) if log_match else "?"
    # 提取 fallback
    fallback_match = re.search(r"#\s*(.+?)(?=\n\s*#|\n\s*$)", ctx_clean)
    comments = re.findall(r"#\s*([^\n]+)", ctx_clean)
    violations.append({
        "idx": int(idx),
        "severity": sev,
        "file": file,
        "line": int(line),
        "method": method,
        "exception": exc,
        "logger_level": log_level,
        "comments": comments[:3],
        "context": ctx_clean[:200],
    })

print(f"=== R51 lint 报告解析 ===")
print(f"P1: {stats['P1']}, P2: {stats['P2']}, Total: {stats['P1']+stats['P2']}")
print(f"Violations 解析成功: {len(violations)}")
print()

# P1 分组
p1_violations = [v for v in violations if v["severity"] == "P1"]
p2_violations = [v for v in violations if v["severity"] == "P2"]

# 按文件聚合 P1
p1_by_file = Counter(v["file"] for v in p1_violations)
p1_by_module = defaultdict(int)
for v in p1_violations:
    module = v["file"].split("/")[0]
    p1_by_module[module] += 1

print(f"=== P1 按模块分布 ===")
for m, c in p1_by_module.most_common():
    print(f"  {m}: {c}")

print(f"\n=== P1 按文件分布 (Top 30) ===")
for f, c in p1_by_file.most_common(30):
    print(f"  {c:3d} | {f}")

# 保存为 JSON
with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tools\r154_p1_violations.json", "w", encoding="utf-8") as f:
    json.dump({
        "stats": stats,
        "p1_violations": p1_violations,
        "p2_violations": p2_violations,
    }, f, ensure_ascii=False, indent=2)

print(f"\n完整 P1 列表已保存: tools/r154_p1_violations.json")
print(f"P1 总数: {len(p1_violations)}")
print(f"P2 总数: {len(p2_violations)}")
