"""R127 子智能体 D: 直接执行 R127 必修 3 项测试并写文件"""
import subprocess
import sys

# 用 conda 环境下的 python
result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "tests/test_r125_p0_6_7_8_multi_account_isolation.py",
     "tests/test_r120_p0_1_set_current_account_id.py",
     "tests/test_r126_p0_mandatory_4items.py",
     "tests/test_r127_p0_mandatory_3items.py",
     "tests/test_r127_hvd68_a_b_base_service_inheritance.py",
     "tests/test_r127_hvd128_guard.py",
     "-v", "--tb=line"],
    cwd="d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui",
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="ignore",
    timeout=300
)

out_file = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/_r127_d_pytest.txt"
with open(out_file, "w", encoding="utf-8") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n=== EXIT CODE ===\n{result.returncode}\n")

print(f"Done: exit_code={result.returncode}")
print(f"STDOUT last 30 lines:")
for line in result.stdout.split("\n")[-30:]:
    print(line)
