"""
R156 5x 稳定性验证脚本: 验证 P0-B1 + P0-B2 修复稳定可重现

R156 R+1 round 价值证明: 5x 稳定性 + exit code 一致 + 0 FAILED/ERROR
"""
import subprocess
import sys
import hashlib
import re
from pathlib import Path

# Windows GBK console 强制 UTF-8 (R156 教训: emoji 在 GBK 报错)
import io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

results = []
for i in range(1, 6):
    print(f"\n=== Run {i} ===")
    result = subprocess.run(
        [r"E:\anaconda3\envs\hikyuu\python.exe", "-m", "pytest",
         "tests/test_r156_p0_5plus1_logger_warning_exc_info.py",
         "-v", "--tb=no", "-q",
         "--no-header"],
        cwd=r"d:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui",
        capture_output=True, text=True
    )

    output = result.stdout
    # 解析 pytest 汇总行: "18 passed, 14 warnings in 8.47s"
    summary_match = re.search(r"(\d+)\s+passed", output)
    failed_match = re.search(r"(\d+)\s+failed", output)
    error_match = re.search(r"(\d+)\s+error", output)
    skipped_match = re.search(r"(\d+)\s+skipped", output)

    passed = int(summary_match.group(1)) if summary_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    error = int(error_match.group(1)) if error_match else 0
    skipped = int(skipped_match.group(1)) if skipped_match else 0

    # 计算输出 hash (去除时间相关字段)
    normalized = re.sub(r"in \d+\.\d+s", "in X.XXs", output)
    output_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]

    results.append({
        "run": i,
        "passed": passed,
        "failed": failed,
        "error": error,
        "skipped": skipped,
        "exit_code": result.returncode,
        "hash": output_hash,
    })

    print(f"PASSED: {passed}, FAILED: {failed}, ERROR: {error}, SKIPPED: {skipped}")
    print(f"Exit code: {result.returncode}, Hash: {output_hash}")

# 5x 稳定性判定
print("\n" + "=" * 60)
print("R156 5x 稳定性验证结果")
print("=" * 60)

hashes = [r["hash"] for r in results]
hash_consistent = len(set(hashes)) == 1
all_passed = all(r["failed"] == 0 and r["error"] == 0 and r["passed"] > 0 for r in results)
exit_codes = [r["exit_code"] for r in results]
exit_consistent = len(set(exit_codes)) == 1

print(f"MD5 一致: {hash_consistent} ({hashes})")
print(f"全 PASSED: {all_passed}")
print(f"Exit code 一致: {exit_consistent} ({exit_codes})")
rating = "[100% STABLE]" if (hash_consistent and all_passed and exit_consistent) else "[UNSTABLE]"
print(f"稳定性评级: {rating}")
print(f"通过用例数: {results[0]['passed'] if results else 0}/{results[0]['passed'] + results[0]['failed'] + results[0]['error'] + results[0]['skipped'] if results else 0}")

if not (hash_consistent and all_passed and exit_consistent):
    sys.exit(1)
print("\nR156 5x 稳定性验证 PASSED")
