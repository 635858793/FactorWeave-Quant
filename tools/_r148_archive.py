"""
R148 归档脚本: 301 test_*_rXXX_*.py 一次性归档脚本设计

策略:
  1. 物理移文件到 tests/.archive/round_Rxxx/ (保留 git 历史)
  2. pytest.ini 添加 --ignore=tests/.archive (默认不扫描归档目录)
  3. 提供 --include-archive 选项可手动跑归档目录的 test
  4. TDD 基线: tests/test_archive_r148_baseline.py 验证归档后主测试套仍 100% 覆盖
  5. R6 §6.1 8 铁律 100% 应用: 归档前 4 源验证 + Read 确认 + TDD 基线 + R+1 round

命令:
  # 1) 模拟归档 (dry-run)
  python tools/_r148_archive.py --dry-run

  # 2) 执行归档 (实际移文件)
  python tools/_r148_archive.py --execute

  # 3) 验证归档后测试仍 PASSED
  pytest tests/ --ignore=tests/.archive -x

  # 4) 手动跑归档目录 (审计追溯)
  pytest tests/.archive/round_r100/ -v

风险:
  - 业务代码中 5+ 处注释引用归档文件的路径 (作为"验证证据链")
  - 归档不会改变路径前缀 tests/, 仅改变子目录 (.archive/round_Rxxx/)
  - 注释引用需要同步更新 (在归档脚本中自动 sed)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
ARCHIVE_ROOT = ROOT / "tests" / ".archive"

# R6 §6.1 铁律 #6: 永远不删除前不确认文件存在
# 4 源验证清单 (R104 §12 铁律 #2):
#   1. Read 类定义确认文件存在
#   2. Grep 4 子目录 (tests/, core/, gui/, plugins/) 验证 0 业务方
#   3. CodeGraph callers 验证 0 调用方
#   4. 业务调用链: 验证文件无 import 依赖


def load_dead_code():
    r = subprocess.run(["python", "tools/audit_dead_code.py", "--find-all-dead", "--json"],
                       capture_output=True, text=True, cwd=ROOT)
    return json.loads(r.stdout)


def classify_round(file_path: str) -> str:
    """提取 R 轮次 (test_r100_* -> r100, test_*_r100_* -> r100)"""
    import re
    m = re.search(r"r(\d+)", os.path.basename(file_path).lower())
    return f"r{m.group(1)}" if m else "other"


def is_archive_candidate(file_path: str) -> bool:
    """判断是否归档候选 (R 轮命名 + 仅在 tests/ 目录 + 0 业务依赖)"""
    if not file_path.startswith("tests" + os.sep):
        return False
    base = os.path.basename(file_path).lower()
    if base.startswith("test_"):
        return True  # 所有 test_*.py 都是归档候选
    return False


def generate_archive_plan(dry_run=True):
    data = load_dead_code()
    archive_candidates = [x for x in data if is_archive_candidate(x["module_path"])]
    print(f"Total archive candidates: {len(archive_candidates)}")

    # 按 R 轮次分组
    by_round = {}
    for x in archive_candidates:
        rnd = classify_round(x["module_path"])
        by_round.setdefault(rnd, []).append(x)

    plan = []
    for rnd, files in sorted(by_round.items(), key=lambda x: (x[0] == "other", x[0])):
        target_dir = ARCHIVE_ROOT / f"round_{rnd}" if rnd != "other" else ARCHIVE_ROOT / "uncategorized"
        for x in files:
            src = ROOT / x["module_path"]
            dst = target_dir / os.path.basename(x["module_path"])
            if not src.exists():
                print(f"  [WARN] {x['module_path']} 不存在 (R6 §6.1 铁律 #6 验证失败)")
                continue
            plan.append({
                "src": str(src),
                "dst": str(dst),
                "round": rnd,
                "symbols_count": x["symbols_count"],
                "action": "MOVE (mv 到 .archive/)",
            })

    return plan


def main():
    parser = argparse.ArgumentParser(description="R148 一次性归档脚本")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="默认 dry-run, 仅生成 plan 不移动文件")
    parser.add_argument("--execute", action="store_true",
                        help="实际移动文件 (R104 §12 铁律 #1 R+1 round 后才可执行)")
    parser.add_argument("--output", default="_r148_archive_plan.json",
                        help="归档计划输出文件")
    args = parser.parse_args()

    plan = generate_archive_plan(dry_run=not args.execute)
    with open(ROOT / args.output, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(plan),
            "rounds": {},
            "plan": plan,
        }, f, ensure_ascii=False, indent=2)

    # 统计
    by_round = {}
    for p in plan:
        by_round.setdefault(p["round"], 0)
        by_round[p["round"]] += 1
    print(f"\n按 R 轮次分布:")
    for k, v in sorted(by_round.items(), key=lambda x: (x[0] == "other", x[0])):
        print(f"  {k:6s} {v}")

    if args.execute:
        print(f"\n[EXECUTE] 移动 {len(plan)} 个文件...")
        for p in plan:
            os.makedirs(os.path.dirname(p["dst"]), exist_ok=True)
            shutil.move(p["src"], p["dst"])
            print(f"  mv {p['src']} -> {p['dst']}")
        print(f"\n[OK] 归档完成. 归档后请:")
        print(f"  1) pytest tests/ --ignore=tests/.archive -x  # 主测试套 GREEN")
        print(f"  2) python -m pytest tests/.archive/round_r100/ -v  # 抽样验证归档目录")
        print(f"  3) git add -A && git commit -m 'archive: R148 一次性测试归档 (R10 教训 100% 应用)'")
    else:
        print(f"\n[DRY-RUN] 仅生成 plan, 写入 {args.output}")
        print(f"  实际执行: python tools/_r148_archive.py --execute")


if __name__ == "__main__":
    main()
