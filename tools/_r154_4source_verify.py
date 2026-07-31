#!/usr/bin/env python3
"""R154 子智能体 D: 系统化 4 源验证关键 P1 violations"""
import os
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")

# 加载抽样 P1
with open(ROOT / "tools/r154_sampled_p1.json", "r", encoding="utf-8") as f:
    sampled = json.load(f)

# 4 源验证: Read + Grep (跨子目录) + AST + 业务调用链追踪
def read_context(file_rel, line, before=2, after=3):
    """源 1: Read 上下文"""
    full = ROOT / file_rel
    if not full.exists():
        return None
    try:
        with open(full, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        start = max(0, line - 1 - before)
        end = min(len(lines), line - 1 + after + 1)
        return "".join(f"{i+1:4d}| {lines[i].rstrip()}\n" for i in range(start, end))
    except Exception as e:
        return f"READ_ERROR: {e}"

def grep_subdirs(pattern, exclude_dirs={".pytest_cache", "__pycache__", ".git", "node_modules"}):
    """源 2: 跨子目录 Grep"""
    hits = []
    for subdir in ["core", "gui", "services", "trading", "tests", "plugins", "scripts"]:
        base = ROOT / subdir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            parts = set(path.parts)
            if parts & exclude_dirs:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if pattern in content:
                    rel = str(path.relative_to(ROOT)).replace("\\", "/")
                    line_num = content[:content.find(pattern)].count("\n") + 1
                    hits.append(f"{rel}:{line_num}")
            except Exception:
                continue
    return hits

# 加载完整 P1 violations
with open(ROOT / "tools/r154_r51_full.json", "r", encoding="utf-8") as f:
    full_data = json.load(f)
p1_all = [v for v in full_data["violations"] if v["severity"] == "P1"]

# 关键业务路径分类
KEY_BUSINESS = {
    "duckdb": lambda v: "duckdb" in v["file"],
    "trading": lambda v: any(k in v["file"] for k in ["trading", "order", "position", "money_manager"]),
    "risk": lambda v: any(k in v["file"] for k in ["risk_control", "risk_manager", "stop_loss"]),
    "data_import": lambda v: "importdata" in v["file"] or "import_execution" in v["file"],
    "agents": lambda v: "agents/" in v["file"],
    "async": lambda v: "async_management" in v["file"],
    "coordinator": lambda v: "coordinators" in v["file"],
    "service": lambda v: "services/" in v["file"],
    "gui_cleanup": lambda v: v["file"].startswith("gui/") and "cleanup" in v["method"].lower(),
    "db_schema": lambda v: "duckdb_manager" in v["file"] and v["method"] in ["get_connection", "health_check", "close_all_connections"],
}

# 高价值候选筛选 (按业务关键路径)
high_value = []
for v in p1_all:
    for cat, pred in KEY_BUSINESS.items():
        if pred(v):
            high_value.append((cat, v))
            break

print(f"=== 高价值 P1 候选 ===")
print(f"总数: {len(high_value)}")
from collections import Counter
cat_counter = Counter(c for c, _ in high_value)
for c, n in cat_counter.most_common():
    print(f"  {c:20s}: {n}")

# 取代表性 30+ 项 (各 cat 抽样)
sample_by_cat = defaultdict(list)
for cat, v in high_value:
    if len(sample_by_cat[cat]) < 6:  # 每类最多 6 个
        sample_by_cat[cat].append(v)

# 展平
final_sample = []
for cat, items in sample_by_cat.items():
    for v in items:
        final_sample.append((cat, v))

# 确保至少 30 个
if len(final_sample) < 30:
    seen = set((v["file"], v["line"]) for _, v in final_sample)
    for cat, v in high_value:
        if len(final_sample) >= 35:
            break
        if (v["file"], v["line"]) not in seen:
            final_sample.append((cat, v))
            seen.add((v["file"], v["line"]))

print(f"\n=== 最终 4 源验证样本: {len(final_sample)} 项 ===")
print(f"涉及分类: {set(c for c, _ in final_sample)}")

# 执行 4 源验证
results = []
for i, (cat, v) in enumerate(final_sample[:35], 1):
    file_rel = v["file"]
    line = v["line"]
    method = v["method"]

    # 源 1: Read 上下文
    ctx = read_context(file_rel, line)

    # 源 2: Grep 业务调用方 (查 method 名)
    method_name = method if method else ""
    callers = grep_subdirs(method_name) if method_name and not method_name.startswith("__") else []
    # 过滤掉自身文件
    callers = [c for c in callers if not c.startswith(file_rel)]

    # 评估
    result = {
        "idx": i,
        "category": cat,
        "file": file_rel,
        "line": line,
        "method": method,
        "except_class": v["except_class"],
        "read_context": ctx[:400] if ctx else "N/A",
        "callers_count": len(callers),
        "callers_sample": callers[:5],
        "business_impact": "TBD",
        "is_real_p1": "TBD",
        "fix_roi": "TBD",
    }
    results.append(result)

# 保存 4 源验证结果
with open(ROOT / "tools/r154_4source_verification.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 输出概览
print("\n=== 4 源验证结果概览 ===")
for r in results:
    print(f"\n[{r['idx']}] [{r['category']}] {r['file']}:{r['line']} ({r['method']})")
    print(f"  except: {r['except_class']}")
    print(f"  callers (跨子目录): {r['callers_count']}")
    if r["callers_sample"]:
        print(f"  sample: {', '.join(r['callers_sample'][:3])}")

print(f"\n完整 4 源验证结果: tools/r154_4source_verification.json")
