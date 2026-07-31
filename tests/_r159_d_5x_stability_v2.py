"""
R159-D 5x 稳定性验证 V2: 详细输出 (避免 PowerShell 截断)
每个套件跑 5 次, 写详细日志到单独文件
"""
import subprocess
import sys
import hashlib
import re
import json
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"
PYTHON_EXE = r"E:\anaconda3\envs\hikyuu\python.exe"

TEST_SUITES = [
    ("R159-A TOP 5 P0 exc_info", r"tests\test_r159_a_top5_exc_info_batch_fix.py", 21),
    ("R158 真修复 TDD", r"tests\test_r158_true_fix_tdd.py", 9),
    ("R158 HVD TDD 基线", r"tests\test_r158_d_hvd_tdd_baseline.py", 12),
    ("R158 P0 紧急修复", r"tests\test_r158_p0_emergency_fixes.py", 11),
]

all_results = {}
overall_stable = True

for suite_name, test_path, expected in TEST_SUITES:
    suite_runs = []
    full_test_names = []

    for run_idx in range(1, 6):
        result = subprocess.run(
            [PYTHON_EXE, "-m", "pytest", test_path, "-v", "--tb=line",
             "-p", "no:cacheprovider"],
            cwd=PROJECT_ROOT,
            capture_output=True, text=True, encoding="utf-8"
        )

        # 解析测试结果
        passed_count = len(re.findall(r"PASSED", result.stdout))
        failed_count = len(re.findall(r"FAILED", result.stdout))
        error_count = len(re.findall(r"ERROR", result.stdout))
        skipped_count = len(re.findall(r"SKIPPED", result.stdout))

        # 解析测试名
        for line in result.stdout.split("\n"):
            m = re.match(r"^tests/test.*?::(\S+)\s+(PASSED|FAILED|ERROR)", line)
            if m:
                full_test_names.append((m.group(1), m.group(2)))

        # 归一化
        normalized = re.sub(r"in \d+\.\d+s", "in X.XXs", result.stdout)
        output_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]

        suite_runs.append({
            "run": run_idx,
            "passed": passed_count,
            "failed": failed_count,
            "error": error_count,
            "skipped": skipped_count,
            "exit_code": result.returncode,
            "hash": output_hash,
        })

    # 稳定性判定
    hashes = [r["hash"] for r in suite_runs]
    hash_consistent = len(set(hashes)) == 1
    all_passed = all(r["failed"] == 0 and r["error"] == 0 and r["passed"] > 0 for r in suite_runs)
    exit_codes = [r["exit_code"] for r in suite_runs]
    exit_consistent = len(set(exit_codes)) == 1
    passed_counts = [r["passed"] for r in suite_runs]
    passed_consistent = len(set(passed_counts)) == 1
    count_match = all(p == expected for p in passed_counts)

    is_stable = hash_consistent and all_passed and exit_consistent and passed_consistent and count_match
    if not is_stable:
        overall_stable = False

    all_results[suite_name] = {
        "expected": expected,
        "runs": suite_runs,
        "hash_consistent": hash_consistent,
        "all_passed": all_passed,
        "exit_consistent": exit_consistent,
        "passed_consistent": passed_consistent,
        "count_match": count_match,
        "is_stable": is_stable,
        "hash": hashes[0] if hashes else "",
        "test_names_count": len(full_test_names),
    }

# 写结果
output_path = Path(PROJECT_ROOT) / "tests" / "_r159_d_5x_stab_v2.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "overall_stable": overall_stable,
        "suites": all_results,
    }, f, ensure_ascii=False, indent=2)

print(f"结果写入: {output_path}")
print(f"\n{'='*60}")
print(f"R159-D 5x 稳定性综合评级")
print(f"{'='*60}")
for name, data in all_results.items():
    status = "[STABLE]" if data["is_stable"] else "[UNSTABLE]"
    print(f"  {name}: expected={data['expected']}, passed={data['runs'][0]['passed']}, "
          f"hash={data['hash']}, {status}")
print(f"\n综合: {'[100% STABLE]' if overall_stable else '[部分不稳定]'}")
print(f"总测试: {sum(d['expected'] for d in all_results.values())}")
