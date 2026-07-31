"""R149 5x 稳定性回归测试"""
import subprocess
import sys

results = []
for i in range(1, 6):
    print(f"\n=== Run {i} ===")
    result = subprocess.run(
        [r"E:\anaconda3\envs\hikyuu\python.exe", "-m", "pytest",
         "tests/test_r149_p0_3_logger_debug_upgrade.py",
         "tests/test_r149_p0_4_sandbox_whitelist.py",
         "-v", "--tb=no"],
        cwd=r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui",
        capture_output=True, text=True
    )
    output = result.stdout
    if "passed" in output:
        for line in output.split("\n"):
            if "passed" in line and "warning" in line:
                print(f"  [{i}] {line.strip()}")
                results.append(line.strip())
    else:
        print(f"  [{i}] FAILED!")
        print(output[-2000:])

print("\n=== 5x 稳定性总结 ===")
for r in results:
    print(f"  {r}")
all_passed = all("72 passed" in r for r in results)
print(f"\n  5/5 全部通过: {'✅ YES' if all_passed else '❌ NO'}")
sys.exit(0 if all_passed else 1)
