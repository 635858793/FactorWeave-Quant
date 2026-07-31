"""
R158 5x 稳定性测试: 验证 R158 3 项真修复的稳定性

R104 §12 铁律 #1: R+1 round 独立验证
R6 §6.3 步骤 6: 物理删除/新 HVD 立项前 TDD 回归测试基线
R158 R+1 round 价值证明: 5x 稳定性 MD5 hash 一致性

目标: 5 轮 exit code 全 0, 5 轮 output MD5 hash 完全一致
"""
import subprocess
import sys
import hashlib
import os
from pathlib import Path

CWD = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"
PYTHON = r"E:\anaconda3\envs\hikyuu\python.exe"

results = []

print("=" * 70)
print("R158 5x 稳定性测试 (5 runs of test_r158_true_fix_tdd.py)")
print("=" * 70)

for i in range(1, 6):
    print(f"\n=== Run {i}/5 ===")
    result = subprocess.run(
        [PYTHON, "-m", "pytest", "tests/test_r158_true_fix_tdd.py", "-v", "--tb=no", "-q", "--no-header"],
        cwd=CWD,
        capture_output=True,
        text=True,
        timeout=120,
    )

    output = result.stdout
    # 解析 pytest output: "9 passed, 1 warning in 0.41s"
    import re
    passed_match = re.search(r'(\d+)\s+passed', output)
    failed_match = re.search(r'(\d+)\s+failed', output)
    error_match = re.search(r'(\d+)\s+error', output)
    skipped_match = re.search(r'(\d+)\s+skipped', output)

    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    error = int(error_match.group(1)) if error_match else 0
    skipped = int(skipped_match.group(1)) if skipped_match else 0

    # 排除 timing 部分, MD5 只 hash 测试结果
    output_for_hash = re.sub(r'in \d+\.\d+s', 'in X.XXs', output)
    output_hash = hashlib.md5(output_for_hash.encode("utf-8")).hexdigest()[:8]

    results.append({
        "run": i,
        "passed": passed,
        "failed": failed,
        "error": error,
        "skipped": skipped,
        "exit_code": result.returncode,
        "hash": output_hash,
    })

    print(f"  PASSED: {passed}, FAILED: {failed}, ERROR: {error}, SKIPPED: {skipped}")
    print(f"  Exit code: {result.returncode}, MD5: {output_hash}")

print("\n" + "=" * 70)
print("R158 5x 稳定性测试结果汇总")
print("=" * 70)

all_zero = all(r["exit_code"] == 0 for r in results)
all_same_hash = len(set(r["hash"] for r in results)) == 1
all_passed = all(r["failed"] == 0 and r["error"] == 0 for r in results)

print(f"\n| Run | Passed | Failed | Error | Exit | MD5     |")
print(f"|-----|--------|--------|-------|------|---------|")
for r in results:
    print(f"| {r['run']:3} | {r['passed']:6} | {r['failed']:6} | {r['error']:5} | {r['exit_code']:4} | {r['hash']:7} |")

print(f"\n[结果评估]")
print(f"  全部 exit code 0: {'✅ PASS' if all_zero else '❌ FAIL'}")
print(f"  全部 MD5 hash 一致: {'✅ PASS' if all_same_hash else '❌ FAIL'}")
print(f"  0 FAILED + 0 ERROR: {'✅ PASS' if all_passed else '❌ FAIL'}")

if all_zero and all_same_hash and all_passed:
    print(f"\n🎉 R158 5x 稳定性测试 100% STABLE")
    sys.exit(0)
else:
    print(f"\n❌ R158 5x 稳定性测试失败")
    sys.exit(1)
