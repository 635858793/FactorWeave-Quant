"""
R159-D 详细诊断: R158 P0 紧急修复 5x 失败根因追溯
"""
import subprocess
import sys
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui"
PYTHON_EXE = r"E:\anaconda3\envs\hikyuu\python.exe"
TEST_FILE = r"tests\test_r158_p0_emergency_fixes.py"

output_log = []

for i in range(1, 6):
    line = f"\n=== Run {i} (详细输出) ==="
    print(line, flush=True)
    output_log.append(line)

    result = subprocess.run(
        [PYTHON_EXE, "-m", "pytest", TEST_FILE, "-v", "--tb=short",
         "-p", "no:cacheprovider"],
        cwd=PROJECT_ROOT,
        capture_output=True, text=True, encoding="utf-8"
    )

    # 打印测试结果
    for line in result.stdout.split("\n"):
        if "PASSED" in line or "FAILED" in line or "ERROR" in line:
            print(f"  {line}", flush=True)
            output_log.append(f"  {line}")

    # 打印失败 traceback
    if "FAILED" in result.stdout or "ERROR" in result.stdout:
        output_log.append("--- FAILED TRACEBACK ---")
        print("--- FAILED TRACEBACK ---", flush=True)
        for line in result.stdout.split("\n"):
            if "FAILED" in line and "_ _ _" in line or "Error:" in line or "assert" in line.lower():
                print(f"  {line}", flush=True)
                output_log.append(f"  {line}")

    print(f"  exit: {result.returncode}", flush=True)
    output_log.append(f"  exit: {result.returncode}")

# 写日志
with open(Path(PROJECT_ROOT) / "tests" / "_r159_d_p0_emerg_5x.log", "w", encoding="utf-8") as f:
    f.write("\n".join(output_log))
