"""R157-D pytest 完整输出 + 错误分析 - 修复 sys.stderr 关闭问题"""
import subprocess
import sys
import os

env = os.environ.copy()
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"

# Use 2>&1 with text mode
result = subprocess.run(
    [r"E:\anaconda3\envs\hikyuu\python.exe", "-m", "pytest",
     "tests/", "-k", "not slow", "-p", "no:cacheprovider", "-p", "no:asyncio", "-p", "no:zarr",
     "--co", "--no-header", "--tb=long", "-v",
     ],
    capture_output=True, text=True,
    cwd=r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui",
    env=env,
    timeout=300,
)

# Save all output
with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\_r157_d_co_full.log", "w", encoding="utf-8") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)

# Find error lines
print("=== Lines mentioning ERROR or ! ===")
all_lines = result.stdout.split("\n") + result.stderr.split("\n")
for i, line in enumerate(all_lines):
    if line.startswith("!") or "ERROR collecting" in line or "ERROR " in line:
        print(f"L{i}: {line}")

print()
print(f"=== Exit Code: {result.returncode} ===")
print(f"=== STDOUT len: {len(result.stdout)} ===")
print(f"=== STDERR len: {len(result.stderr)} ===")
