# 检查 conda hikyuu 环境的 NumPy 版本
import subprocess
import sys

# 使用 conda run 在 hikyuu 环境中运行
result = subprocess.run(
    [sys.executable, "-c", "import numpy; print(numpy.__version__)"],
    capture_output=True,
    text=True,
    env={"PATH": r"E:\anaconda3\envs\hikyuu;E:\anaconda3\envs\hikyuu\Scripts;" + __import__("os").environ.get("PATH", "")}
)

print("stdout:", result.stdout)
print("stderr:", result.stderr)
print("returncode:", result.returncode)
