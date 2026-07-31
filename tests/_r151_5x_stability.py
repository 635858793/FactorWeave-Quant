"""
R151 5x 稳定性回归测试脚本
- 测试: test_r150_p1_1_risk_control_exc_info + test_r150_p1_1_unified_engine_logger_warning + test_r151_p1_1_dynamic_risk_logger_warning
- 5 次运行, 100% 稳定 PASSED 才算通过
"""
import subprocess
import sys

results = []
for i in range(1, 6):
    print(f"\n=== Run {i} ===")
    result = subprocess.run(
        [r"E:\anaconda3\envs\hikyuu\python.exe", "-m", "pytest",
         "tests/test_r150_p1_1_risk_control_exc_info.py",
         "tests/test_r150_p1_1_unified_engine_logger_warning.py",
         "tests/test_r151_p1_1_dynamic_risk_logger_warning.py",
         "-v", "--tb=no", "-q"],
        cwd=r"d:\\DevelopTool\\FreeCode\\HIkyuu-UI\\hikyuu-ui",
        capture_output=True, text=True
    )
    output = result.stdout + result.stderr
    # 提取 passed/failed 数字
    passed = 0
    failed = 0
    for line in output.split("\n"):
        if "passed" in line and "warning" in line:
            parts = line.split()
            for j, p in enumerate(parts):
                if p == "passed," and j > 0:
                    try:
                        passed = int(parts[j-1])
                    except (ValueError, IndexError):
                        pass
                if p == "failed," and j > 0:
                    try:
                        failed = int(parts[j-1])
                    except (ValueError, IndexError):
                        pass
        if "failed" in line and "passed" not in line and "warning" not in line:
            parts = line.split()
            for j, p in enumerate(parts):
                if p == "failed" and j > 0:
                    try:
                        failed = int(parts[j-1])
                    except (ValueError, IndexError):
                        pass

    stability = "[OK]" if result.returncode == 0 and failed == 0 else "[FAIL]"
    print(f"Run {i}: PASSED={passed} FAILED={failed} Return={result.returncode} {stability}")
    results.append({"run": i, "passed": passed, "failed": failed, "returncode": result.returncode, "stability": stability})

# 汇总
print("\n" + "=" * 60)
print("R151 5x 稳定性回归汇总")
print("=" * 60)
total_passed = sum(r["passed"] for r in results)
total_failed = sum(r["failed"] for r in results)
all_stable = all(r["stability"] == "[OK]" for r in results)
print(f"总通过: {total_passed}")
print(f"总失败: {total_failed}")
print(f"5x 稳定性: {'[OK] 100% 稳定' if all_stable else '[FAIL] 不稳定'}")
print(f"综合评级: {'[GREEN] GREEN' if all_stable and total_failed == 0 else '[RED] RED'}")
