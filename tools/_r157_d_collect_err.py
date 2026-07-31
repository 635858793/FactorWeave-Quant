"""R157-D pytest collection 错误分析脚本"""
import subprocess
import sys

env = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
result = subprocess.run(
    [r"E:\anaconda3\envs\hikyuu\python.exe", "-m", "pytest",
     "tests/", "-k", "not slow", "-p", "no:cacheprovider",
     "--co", "--no-header", "--tb=line"],
    capture_output=True, text=True,
    cwd=r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui",
    env=env,
    timeout=300,
)

# Show summary
print("=== STDOUT TAIL ===")
print(result.stdout[-3000:])
print()
print("=== STDERR TAIL ===")
print(result.stderr[-3000:])
print()
print(f"=== Exit Code: {result.returncode} ===")
