#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R176-C 详细违规列表提取"""
import json
from pathlib import Path

JSON_PATH = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\.trae\reports\rounds\audit_r176_c_r51_iron_law_5.json")
OUT_MD = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\.trae\reports\rounds\audit_r176_c_violations_detail.md")

data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

lines = []
lines.append("# R176-C R51 #5 违规详细列表")
lines.append("")
lines.append("## 元信息")
lines.append(f"- 工具: {data['metadata']['tool']}")
lines.append(f"- 扫描时间: {data['metadata']['scan_time']}")
lines.append(f"- R175-B 声称总数: {data['metadata']['r175b_claim_total']}")
lines.append(f"- R176-C 实际违规总数 (含 INFO-ONLY): {data['metadata']['actual_violations_total']}")
lines.append(f"- R176-C 实际 P0 违规 (except 块内缺 exc_info): {data['metadata']['p0_violations_in_except']}")
lines.append(f"- 差异: {data['metadata']['discrepancy']:+d}")
lines.append("")

for r in data["results"]:
    f = r["file"]
    lines.append(f"## {f}")
    lines.append("")
    lines.append(f"- 总 logger.warning: **{r['total_warning_calls']}**")
    lines.append(f"- 含 exc_info: {r['with_exc_info']}")
    lines.append(f"- 缺 exc_info (全部): **{r['without_exc_info']}**")
    lines.append(f"- 处于 except 块: {r['in_except_block']}")
    lines.append(f"- **P0 违规 (except 内缺 exc_info): {r['in_except_block_without_exc']}**")
    lines.append("")

    # 列出所有违规
    violations = [c for c in r["calls"] if c["violation"]]
    p0 = [v for v in violations if v["in_except_block"]]
    info_only = [v for v in violations if not v["in_except_block"]]

    if p0:
        lines.append(f"### P0 违规 (except 块内, 必修) — {len(p0)} 条")
        lines.append("")
        lines.append("| L# | 方法 | except行 | except类型 | 消息预览 |")
        lines.append("|:--:|:--|:--:|:--|:--|")
        for v in sorted(p0, key=lambda x: x["line"]):
            msg = v["msg_preview"][:60].replace("|", "\\|")
            lines.append(f"| {v['line']} | `{v['method']}` | L{v['except_line']} | `{v['except_type']}` | `{msg}` |")
        lines.append("")

    if info_only:
        lines.append(f"### INFO-ONLY 警告 (非 except 块, 非严格 R51 #5) — {len(info_only)} 条")
        lines.append("")
        lines.append("| L# | 方法 | 消息预览 |")
        lines.append("|:--:|:--|:--|")
        for v in sorted(info_only, key=lambda x: x["line"]):
            msg = v["msg_preview"][:60].replace("|", "\\|")
            lines.append(f"| {v['line']} | `{v['method']}` | `{msg}` |")
        lines.append("")

OUT_MD.write_text("\n".join(lines), encoding="utf-8")
print(f"报告写入: {OUT_MD}")
print()
# 统计
for r in data["results"]:
    print(f"{r['file']}: P0={r['in_except_block_without_exc']} | INFO={r['without_exc_info']-r['in_except_block_without_exc']} | Total={r['total_warning_calls']}")
