"""R159-D R+1 round: R159-B/C 综合检查 + 写入结果文件"""
import sys
import os
from pathlib import Path

os.chdir(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui")
sys.path.insert(0, r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests')

# 重新加载模块
import importlib.util

# 加载 R159-B
spec = importlib.util.spec_from_file_location("r159_b", r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\test_r159_b_hvd_158b_silent_except.py")
m_b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m_b)

# 加载 R159-C
spec2 = importlib.util.spec_from_file_location("r159_c", r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\test_r159_hvd_158c_logger_debug_upgrade.py")
m_c = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(m_c)

results = []
results.append("=" * 70)
results.append("R159-D R+1 round 假修复鉴别: R159-A/B/C 综合验证")
results.append("=" * 70)
results.append("")

# R159-B 详细
results.append("## R159-B 详细验证")
files_b = [
    "core/trading/order_executor.py",
    "core/trading/order_service.py",
    "core/trading/order_monitor.py",
]

for rel in files_b:
    full = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui") / rel
    r = m_b.check_r159_hvd_158b_exc_info(str(full))
    results.append(f"## {rel}")
    results.append(f"   R159 HVD-158-B markers: {r['r159_b_markers']}")
    results.append(f"   r159_b_upgrades_checked: {r['r159_b_upgrades_checked']}")
    results.append(f"   r159_b_without_exc_info: {r['r159_b_without_exc_info']}")
    if r['syntax_error']:
        results.append(f"   SYNTAX ERROR: {r['syntax_error']}")
    results.append("")

# R159-C 详细
results.append("=" * 70)
results.append("## R159-C 详细执行 (5 TDD)")
results.append("=" * 70)

tests_c = [
    ("TDD-1 marker count", m_c.test_tdd_1_marker_count),
    ("TDD-2 exc_info compliance", m_c.test_tdd_2_exc_info_compliance),
    ("TDD-3 no syntax error", m_c.test_tdd_3_no_syntax_error),
    ("TDD-4 residual business debug", m_c.test_tdd_4_residual_business_debug),
    ("TDD-5 business event coverage", m_c.test_tdd_5_business_event_coverage),
]

for name, func in tests_c:
    results.append(f"\n--- {name} ---")
    try:
        func()
        results.append(f"  [PASSED]")
    except AssertionError as e:
        results.append(f"  [FAILED] {e}")
    except Exception as e:
        results.append(f"  [ERROR] {e}")

# 写文件
output_path = r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\tests\_r159_d_r159_inspect_full.txt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(results))

print(f"结果已写入: {output_path}")
print(f"行数: {len(results)}")
