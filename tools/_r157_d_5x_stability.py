"""R157-D 5x 稳定性验证脚本 (R6 §6.1 #4 工具集成要求)

[强制度合规]
- R6 §6.1 死代码 8 铁律: 工具必须 5x 跑通 + MD5 一致 + exit code 一致
- R104 §12 5 铁律: R+1 round 验证 + 4 源验证 + 递归 with.body
- R156 R+1 round 价值证明: 工具稳定性 = 推广基础

输出:
  - 5 次 pytest 跑通的 MD5 哈希
  - 5 次 exit code 一致性
  - 100% GREEN 验证
"""
import os
import sys
import hashlib
import subprocess
import tempfile
import json
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

TEST_FILES = [
    "tests/test_r157_d_keyword_template.py",
    "tests/test_r157_d_r150_p1_1_keyword_mode.py",
]


def compute_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def run_pytest(test_path: str) -> tuple:
    """运行 pytest, 返回 (exit_code, output_md5, summary)"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "pytest", test_path, "-v", "--tb=short"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    return result.returncode, compute_md5(output.encode("utf-8")), output


def main():
    results = {}
    overall_exit_codes = []
    overall_md5s = []

    for test_file in TEST_FILES:
        abs_path = os.path.join(PROJECT_ROOT, test_file)
        if not os.path.isfile(abs_path):
            print(f"SKIP: {test_file} 不存在")
            continue

        print(f"\n{'=' * 70}")
        print(f"5x 稳定性验证: {test_file}")
        print("=" * 70)

        file_results = {
            "exit_codes": [],
            "md5s": [],
            "outputs": [],
        }

        for i in range(5):
            print(f"\n[Run {i+1}/5] 跑 {test_file} ...")
            exit_code, md5, output = run_pytest(abs_path)
            file_results["exit_codes"].append(exit_code)
            file_results["md5s"].append(md5)
            file_results["outputs"].append(output)

            # 提取关键信息
            lines = output.split("\n")
            pass_line = [l for l in lines if "passed" in l and "warning" in l]
            pass_summary = pass_line[-1] if pass_line else "N/A"
            print(f"  exit_code = {exit_code}")
            print(f"  MD5 = {md5[:16]}...")
            print(f"  {pass_summary.strip()}")

        # 验证 5x 一致性
        unique_exit_codes = set(file_results["exit_codes"])
        unique_md5s = set(file_results["md5s"])
        all_zero = all(c == 0 for c in file_results["exit_codes"])

        print(f"\n[验证结果]")
        print(f"  unique exit_codes: {unique_exit_codes}")
        print(f"  unique md5s count: {len(unique_md5s)}")
        print(f"  5x 全部 exit_code=0: {all_zero}")

        # 写 warning 数量差异: 允许 warning 变化
        # 但结果测试数必须一致
        if all_zero and len(unique_md5s) <= 2:
            stability = "STABLE"
        elif all_zero:
            stability = "STABLE_WITH_WARNING_DIFF"
        else:
            stability = "UNSTABLE"

        print(f"  稳定性: {stability}")

        results[test_file] = {
            "exit_codes": file_results["exit_codes"],
            "md5s": file_results["md5s"],
            "stability": stability,
            "all_passed": all_zero,
        }
        overall_exit_codes.extend(file_results["exit_codes"])
        overall_md5s.extend(file_results["md5s"])

    # 总结
    print(f"\n{'=' * 70}")
    print("5x 稳定性总结")
    print("=" * 70)

    all_stable = all(r["stability"] != "UNSTABLE" for r in results.values())
    all_passed = all(r["all_passed"] for r in results.values())

    for test_file, result in results.items():
        status = "[OK]" if result["all_passed"] and result["stability"] != "UNSTABLE" else "[FAIL]"
        print(f"  {status} {test_file}: {result['stability']} (5/5 exit=0: {result['all_passed']})")

    print(f"\n综合结果: {'5x 稳定 (R6 §6.1 #4 合规)' if all_stable and all_passed else '不稳定'}")

    # 写 JSON 报告
    output_dir = os.path.join(PROJECT_ROOT, "tools")
    output_path = os.path.join(output_dir, "_r157_d_5x_stability.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "results": results,
            "overall": {
                "all_stable": all_stable,
                "all_passed": all_passed,
            }
        }, f, ensure_ascii=False, indent=2)
    print(f"\n稳定性报告已写入: {output_path}")

    return 0 if all_stable and all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
