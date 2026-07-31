"""R157-D pytest 完整输出 + 错误分析"""
import subprocess
import sys

env = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
result = subprocess.run(
    [r"E:\anaconda3\envs\hikyuu\python.exe", "-m", "pytest",
     "tests/", "-k", "not slow", "-p", "no:cacheprovider", "-p", "no:asyncio",
     "--no-header", "-q", "--tb=line",
     "-p", "no:warnings",
     "-rfE",  # report failed/errored
     ],
    capture_output=True, text=True,
    cwd=r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui",
    env=env,
    timeout=600,
)

# Save all output
with open(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\_r157_d_full.log", "w", encoding="utf-8") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)

print("=== STDOUT (last 2000 chars) ===")
print(result.stdout[-2000:])
print()
print("=== STDERR (last 2000 chars) ===")
print(result.stderr[-2000:])
print()
print(f"=== Exit Code: {result.returncode} ===")
