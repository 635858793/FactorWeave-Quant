"""
R159-D 5x 稳定性验证脚本: 验证 R159-A 21 测试 + R158 32 测试稳定性

参考 R158-D _r158_d_5x_stability.py 模板:
- 用归一化 MD5 (去除时间相关字段)
- 5 轮 exit code + passed/failed 100% 一致
- 5 轮全 PASS (0 failed/0 error)
- 多文件分别验证: R159-A (21) + R158 真修复 (9) + R158 HVD 基线 (12) + R158 P0 紧急 (11) = 53 测试
"""
import subprocess
import sys
import hashlib
import re
from pathlib import Path

# Windows GBK console 强制 UTF-8 (R156 教训: emoji 在 GBK 报错)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"
PYTHON_EXE = r"E:\anaconda3\envs\hikyuu\python.exe"

# 4 个核心测试套件: R159-A + R158 (3 子套件) = 53 测试
TEST_SUITES = [
    ("R159-A TOP 5 P0 exc_info", r"tests\test_r159_a_top5_exc_info_batch_fix.py", 21),
    ("R158 真修复 TDD", r"tests\test_r158_true_fix_tdd.py", 9),
    ("R158 HVD TDD 基线", r"tests\test_r158_d_hvd_tdd_baseline.py", 12),
    ("R158 P0 紧急修复", r"tests\test_r158_p0_emergency_fixes.py", 11),
]

# 输出日志
output_log_path = Path(PROJECT_ROOT) / "tests" / "_r159_d_5x_stab_results.txt"
output_log_lines = []


def run_one_test(test_path: str):
    """跑单个测试套件, 返回 (passed, failed, error, skipped, exit_code, hash)"""
    result = subprocess.run(
        [PYTHON_EXE, "-m", "pytest", test_path, "-v", "--tb=no", "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=PROJECT_ROOT,
        capture_output=True, text=True, encoding="utf-8"
    )

    output = result.stdout
    summary_match = re.search(r"(\d+)\s+passed", output)
    failed_match = re.search(r"(\d+)\s+failed", output)
    error_match = re.search(r"(\d+)\s+error", output)
    skipped_match = re.search(r"(\d+)\s+skipped", output)

    passed = int(summary_match.group(1)) if summary_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    error = int(error_match.group(1)) if error_match else 0
    skipped = int(skipped_match.group(1)) if skipped_match else 0

    # 归一化: 去除时间相关字段
    normalized = re.sub(r"in \d+\.\d+s", "in X.XXs", output)
    output_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]

    return passed, failed, error, skipped, result.returncode, output_hash


def verify_suite(suite_name: str, test_path: str, expected_count: int) -> dict:
    """对单个测试套件跑 5 轮, 验证稳定性"""
    print(f"\n{'='*60}")
    print(f"测试套件: {suite_name} (预期 {expected_count} 测试)")
    print(f"{'='*60}")
    output_log_lines.append(f"\n{'='*60}")
    output_log_lines.append(f"测试套件: {suite_name} (预期 {expected_count} 测试)")
    output_log_lines.append(f"{'='*60}")

    results = []
    for i in range(1, 6):
        passed, failed, error, skipped, exit_code, hash_val = run_one_test(test_path)
        run_str = f"  Run {i}: PASSED={passed}, FAILED={failed}, ERROR={error}, SKIPPED={skipped}, exit={exit_code}, hash={hash_val}"
        print(run_str, flush=True)
        output_log_lines.append(run_str)
        results.append({
            "run": i, "passed": passed, "failed": failed, "error": error,
            "skipped": skipped, "exit_code": exit_code, "hash": hash_val
        })

    # 稳定性判定
    hashes = [r["hash"] for r in results]
    hash_consistent = len(set(hashes)) == 1
    all_passed = all(r["failed"] == 0 and r["error"] == 0 and r["passed"] > 0 for r in results)
    exit_codes = [r["exit_code"] for r in results]
    exit_consistent = len(set(exit_codes)) == 1
    passed_counts = [r["passed"] for r in results]
    passed_consistent = len(set(passed_counts)) == 1
    count_match = all(p == expected_count for p in passed_counts)

    is_stable = hash_consistent and all_passed and exit_consistent and passed_consistent and count_match

    print(f"  MD5 一致: {hash_consistent} ({hashes})")
    print(f"  全 PASSED: {all_passed}")
    print(f"  Exit code 一致: {exit_consistent} ({exit_codes})")
    print(f"  Passed 数一致: {passed_consistent} ({passed_counts})")
    print(f"  Passed == 预期: {count_match}")
    print(f"  稳定性评级: {'[100% STABLE]' if is_stable else '[UNSTABLE]'}")
    output_log_lines.append(f"  MD5 一致: {hash_consistent} ({hashes})")
    output_log_lines.append(f"  全 PASSED: {all_passed}")
    output_log_lines.append(f"  Exit code 一致: {exit_consistent} ({exit_codes})")
    output_log_lines.append(f"  Passed 数一致: {passed_consistent} ({passed_counts})")
    output_log_lines.append(f"  Passed == 预期: {count_match}")
    output_log_lines.append(f"  稳定性评级: {'[100% STABLE]' if is_stable else '[UNSTABLE]'}")

    return {
        "suite": suite_name,
        "test_path": test_path,
        "expected": expected_count,
        "results": results,
        "hash_consistent": hash_consistent,
        "all_passed": all_passed,
        "exit_consistent": exit_consistent,
        "passed_consistent": passed_consistent,
        "count_match": count_match,
        "is_stable": is_stable,
        "hash": hashes[0] if hashes else "",
    }


# 主流程
all_results = []
for suite_name, test_path, expected in TEST_SUITES:
    res = verify_suite(suite_name, test_path, expected)
    all_results.append(res)

# 综合判定
print(f"\n{'='*60}")
print(f"R159-D 综合 5x 稳定性评级")
print(f"{'='*60}")
output_log_lines.append(f"\n{'='*60}")
output_log_lines.append(f"R159-D 综合 5x 稳定性评级")
output_log_lines.append(f"{'='*60}")

total_stable = sum(1 for r in all_results if r["is_stable"])
total_suites = len(all_results)
total_tests = sum(r["expected"] for r in all_results)
print(f"稳定套件数: {total_stable}/{total_suites}")
print(f"总测试数: {total_tests}")
print(f"综合评级: {'[100% STABLE]' if total_stable == total_suites else '[部分不稳定]'}")
output_log_lines.append(f"稳定套件数: {total_stable}/{total_suites}")
output_log_lines.append(f"总测试数: {total_tests}")
output_log_lines.append(f"综合评级: {'[100% STABLE]' if total_stable == total_suites else '[部分不稳定]'}")

# 详细结果表
print(f"\n--- 详细结果表 ---")
print(f"{'Suite':<25} {'Expected':<10} {'Passed':<8} {'MD5':<10} {'Stable'}")
output_log_lines.append(f"\n--- 详细结果表 ---")
output_log_lines.append(f"{'Suite':<25} {'Expected':<10} {'Passed':<8} {'MD5':<10} {'Stable'}")
for r in all_results:
    line = f"{r['suite']:<25} {r['expected']:<10} {r['results'][0]['passed']:<8} {r['hash']:<10} {r['is_stable']}"
    print(line)
    output_log_lines.append(line)

# 写结果到文件
with open(output_log_path, "w", encoding="utf-8") as f:
    f.write("\n".join(output_log_lines))

print(f"\n结果已写入: {output_log_path}")
