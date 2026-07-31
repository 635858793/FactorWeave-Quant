#!/usr/bin/env python3
"""R175-B 打印 except logger 违规为 markdown 表格"""
import json
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json_path = os.path.join(root, '.audit_r175_b_except_logger.json')
with open(json_path, 'r', encoding='utf-8') as f:
    d = json.load(f)

lines = []
lines.append('# R175-B R51 §7.1 #5 except 块 logger.warning/error 缺 exc_info=True 复检\n')
lines.append(f'\n**总违规**: {d["total_violations"]} 处\n')
lines.append(f'**扫描文件**: {d["file_count"]}/20 个业务关键路径文件\n')
lines.append('\n## 详细违规清单 (按文件)\n')
for p, v in sorted(d['per_file'].items()):
    if not v:
        continue
    lines.append(f'\n### `{p}` ({len(v)} 处)\n')
    lines.append('\n| 行号 | 级别 | 文本 |\n')
    lines.append('|------|------|------|\n')
    for i in v:
        text = i['text'].replace('|', '\\|').replace('\n', ' ')
        lines.append(f'| L{i["line"]} | {i["level"]} | `{text}` |\n')

out_path = os.path.join(root, '.audit_r175_b_except_logger.md')
with open(out_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
sys.stderr.write(f'Saved to {out_path}\n')
sys.stderr.write(f'Total violations: {d["total_violations"]}\n')
sys.stderr.flush()
