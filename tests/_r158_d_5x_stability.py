"""
R158-D 5x 稳定性验证脚本: 验证 R157-A 5+1 服务架构 32 测试稳定性

参考 R156 _r156_5x_stability.py 模板 + R157-B 教训:
- 用归一化 MD5 (去除时间相关字段)
- 5 轮 exit code + passed/failed 100% 一致
- 5 轮全 PASS (0 failed/0 error)
"""
import subprocess
import sys
import hashlib
import re
from pathlib import Path

# Windows GBK console 强制 UTF-8 (R156 教训: emoji 在 GBK 报错)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TEST_FILE = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\test_r157_a_5plus1_logger_exc_info.py"
PYTHON_EXE = r"E:\anaconda3\envs\hikyuu\python.exe"
PROJECT_ROOT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"

results = []
output_log = []
for i in range(1, 6):
    line = f"\n=== Run {i} ==="
    print(line, flush=True)
    output_log.append(line)
    result = subprocess.run(
        [PYTHON_EXE, "-m", "pytest", TEST_FILE,
         "-v", "--tb=no", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=PROJECT_ROOT,
        capture_output=True, text=True, encoding="utf-8"
    )

    output = result.stdout
    # 解析 pytest 汇总行: "32 passed, 15 warnings in 4.12s"
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
    # 也归一化 PASSED 行的 pytest hash (内部 counter)
    output_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]

    results.append({
        "run": i,
        "passed": passed,
        "failed": failed,
        "error": error,
        "skipped": skipped,
        "exit_code": result.returncode,
        "hash": output_hash,
        "normalized": normalized,
    })

    print(f"PASSED: {passed}, FAILED: {failed}, ERROR: {error}, SKIPPED: {skipped}")
    print(f"Exit code: {result.returncode}, Hash: {output_hash}")
    output_log.append(f"PASSED: {passed}, FAILED: {failed}, ERROR: {error}, SKIPPED: {skipped}")
    output_log.append(f"Exit code: {result.returncode}, Hash: {output_hash}")

# 5x 稳定性判定
print("\n" + "=" * 60)
print("R158-D R157-A 5x 稳定性验证结果")
print("=" * 60)

hashes = [r["hash"] for r in results]
hash_consistent = len(set(hashes)) == 1
all_passed = all(r["failed"] == 0 and r["error"] == 0 and r["passed"] > 0 for r in results)
exit_codes = [r["exit_code"] for r in results]
exit_consistent = len(set(exit_codes)) == 1
passed_counts = [r["passed"] for r in results]
passed_consistent = len(set(passed_counts)) == 1

print(f"MD5 一致: {hash_consistent} ({hashes})")
print(f"全 PASSED: {all_passed}")
print(f"Exit code 一致: {exit_consistent} ({exit_codes})")
print(f"Passed 数一致: {passed_consistent} ({passed_counts})")

if hash_consistent and all_passed and exit_consistent and passed_consistent:
    rating = "[100% STABLE]"
else:
    rating = "[UNSTABLE]"
print(f"稳定性评级: {rating}")
print(f"通过用例数: {results[0]['passed'] if results else 0}")

# 5x 详细结果表
print("\n--- 详细结果表 ---")
print(f"{'Run':<4} {'Passed':<8} {'Failed':<7} {'Error':<6} {'Skipped':<8} {'Exit':<5} {'MD5':<10}")
for r in results:
    print(f"{r['run']:<4} {r['passed']:<8} {r['failed']:<7} {r['error']:<6} {r['skipped']:<8} {r['exit_code']:<5} {r['hash']:<10}")

# 写详细结果到文件 (无论结果如何都先写)
try:
    with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\_r158_d_5x_stab_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_log))
        f.write(f"\n\n--- 详细结果表 ---\n")
        f.write(f"{'Run':<4} {'Passed':<8} {'Failed':<7} {'Error':<6} {'Skipped':<8} {'Exit':<5} {'MD5':<10}\n")
        for r in results:
            f.write(f"{r['run']:<4} {r['passed']:<8} {r['failed']:<7} {r['error']:<6} {r['skipped']:<8} {r['exit_code']:<5} {r['hash']:<10}\n")
        f.write(f"\n[{'100% STABLE' if (hash_consistent and all_passed and exit_consistent and passed_consistent) else 'UNSTABLE'}] MD5 一致={hash_consistent} 全 PASSED={all_passed} Exit 一致={exit_consistent} Passed 一致={passed_consistent}\n")
except Exception as e:
    print(f"[WARN] 写结果文件失败: {e}", flush=True)

if not (hash_consistent and all_passed and exit_consistent and passed_consistent):
    print("\n!! 5x 稳定性不通过,需 P0 修复 !!")
    sys.exit(1)
print("\nR158-D R157-A 5x 稳定性验证 PASSED")

