#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R200 全量回归测试 - 执行所有 R194-R200 测试"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
TESTS_DIR = PROJECT_ROOT / "tests"

# 收集所有 R-N 测试文件
test_files = sorted(TESTS_DIR.glob("test_r1[9]*.py")) + sorted(TESTS_DIR.glob("test_r2*.py"))
test_files = [f for f in test_files if "_r2" not in str(f)]  # 排除 _r2 (这是脚本)
test_files = sorted(set(test_files), key=lambda x: x.name)

print(f"找到 {len(test_files)} 个测试文件")
total_passed = 0
total_failed = 0
total_skipped = 0
total_errors = 0
failed_files = []

for test_file in test_files:
    print(f"\n--- {test_file.name} ---")
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", str(test_file), "-v", "--tb=short", "-q"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr
        # 提取最后的总结
        for line in output.split("\n"):
            if "passed" in line and ("warning" in line or "skipped" in line or "failed" in line):
                print(f"  {line.strip()}")
                # 解析数字
                import re
                m = re.search(r"(\d+)\s*passed", line)
                if m:
                    total_passed += int(m.group(1))
                m = re.search(r"(\d+)\s*failed", line)
                if m:
                    total_failed += int(m.group(1))
                m = re.search(r"(\d+)\s*skipped", line)
                if m:
                    total_skipped += int(m.group(1))
                m = re.search(r"(\d+)\s*error", line)
                if m:
                    total_errors += int(m.group(1))
                break
        if "FAILED" in output or "ERROR" in output:
            failed_files.append(test_file.name)
            # 提取失败信息
            for line in output.split("\n"):
                if "FAILED" in line or "ERROR" in line:
                    print(f"    {line.strip()}")
    except Exception as e:
        print(f"  ERROR: {e}")
        failed_files.append(test_file.name)

print(f"\n\n========== R200 全量回归汇总 ==========")
print(f"  Total Passed: {total_passed}")
print(f"  Total Failed: {total_failed}")
print(f"  Total Skipped: {total_skipped}")
print(f"  Total Errors: {total_errors}")
print(f"  Failed Files: {len(failed_files)}")
for f in failed_files:
    print(f"    - {f}")
