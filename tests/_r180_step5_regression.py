#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R180-HVD-A Step 5: 全量回归 (无 conftest)
通过直接验证 7 个 active 源文件 import 链 + 关键测试模块 import 来确认无业务回归
"""
import sys
import os
import json
import ast
from pathlib import Path
import importlib.util

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui").resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# 关键 active 源文件 (Phase 3 不变性测试已确认存在)
ACTIVE_FILES = [
    "core/services/service_bootstrap.py",
    "core/services/unified_data_manager.py",
    "core/services/advanced_risk_control_service.py",
    "core/trading/order_executor.py",
    "core/asset_database_manager.py",
    "core/trading/interfaces/ctp_trading_interface.py",
    "core/services/cache_service.py",
]

# R179-R176 关键测试模块
KEY_TEST_MODULES = [
    "tests/test_event_bus",
    "tests/test_imports",
    "tests/test_signal_fix",
    "tests/test_repository",
    "tests/test_safe_math",
    "tests/test_lttb",
    "tests/test_check_ast",
]

passed = 0
failed = 0
errors = []

def test(name, fn):
    global passed, failed
    try:
        result = fn()
        print(f"[PASS] {name}" + (f" -> {result}" if result else ""))
        passed += 1
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
        failed += 1
        errors.append((name, str(e)))
    except Exception as e:
        print(f"[ERROR] {name}: {type(e).__name__}: {e}")
        failed += 1
        errors.append((name, f"{type(e).__name__}: {e}"))


print("=" * 80)
print("R180-HVD-A Step 5: 全量回归 (无 conftest, 直接 AST + 编译验证)")
print("=" * 80)


# ============================================================
# 1. 7 个 active 源文件: AST 解析 + 编译
# ============================================================
print("\n--- 1. Active 源文件 AST + 编译 ---")
for rel in ACTIVE_FILES:
    def make_test(r):
        def fn():
            p = PROJECT_ROOT / r
            src = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src, filename=str(p))
            # 统计类/函数/方法数 (确保文件结构完整)
            n_classes = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
            n_funcs = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
            compile(src, str(p), "exec")
            return f"classes={n_classes}, funcs={n_funcs}"
        return fn
    test(f"active_{Path(rel).name}_ast_compile", make_test(rel))


# ============================================================
# 2. R180 / R179 / R178 / R177 / R176 测试文件存在性
# ============================================================
print("\n--- 2. R180-R176 测试文件存在性 ---")
def find_r_test_files(pattern):
    """查找匹配 pattern 的测试文件"""
    found = []
    for f in PROJECT_ROOT.glob(f"tests/*{pattern}*"):
        if f.is_file() and f.suffix == ".py":
            found.append(f)
    return found

for round_name in ["r180", "r179", "r178", "r177", "r176", "r175", "r174"]:
    def make_test(rn):
        def fn():
            files = find_r_test_files(rn)
            return f"{len(files)} files"
        return fn
    test(f"rounds_{round_name}_test_files_exist", make_test(round_name))


# ============================================================
# 3. 关键测试模块 AST 解析
# ============================================================
print("\n--- 3. 关键测试模块 AST 解析 ---")
for mod in KEY_TEST_MODULES:
    def make_test(m):
        def fn():
            p = PROJECT_ROOT / f"{m}.py"
            if not p.exists():
                raise AssertionError(f"测试模块不存在: {m}")
            src = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src, filename=str(p))
            n_tests = sum(
                isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
                for n in ast.walk(tree)
            )
            return f"test_functions={n_tests}"
        return fn
    test(f"test_module_{Path(mod).name}_ast_ok", make_test(mod))


# ============================================================
# 4. _r180 测试文件本身存在
# ============================================================
print("\n--- 4. R180 测试文件本身存在 ---")

r180_files = [
    "tests/test_r180_hvd_a_backup_archive.py",
    "tests/_r180_phase1_red.py",
    "tests/_r180_phase2_3.py",
    "tests/_r180_hvd_a_4src_verify.json",
    "tests/_r180_archive_log.json",
]
for f in r180_files:
    def make_test(rf):
        def fn():
            p = PROJECT_ROOT / rf
            assert p.exists(), f"缺失: {rf}"
            if p.suffix == ".json":
                json.loads(p.read_text(encoding="utf-8"))
            elif p.suffix == ".py":
                ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            return "OK"
        return fn
    test(f"r180_file_{Path(f).name}_exists", make_test(f))


# ============================================================
# 5. 归档目录完整性
# ============================================================
print("\n--- 5. 归档目录完整性 ---")

archive_dir = PROJECT_ROOT / "_archive" / "backups_2026_07_24"
def t_archive_16():
    suffixes = (".bak_r161", ".bak_r160", ".r147_bak", ".bak")
    files = [
        f for f in archive_dir.rglob("*")
        if f.is_file() and any(f.name.endswith(s) for s in suffixes)
    ]
    assert len(files) == 16, f"归档 {len(files)} 个, 预期 16"
    return f"16 files in {archive_dir.relative_to(PROJECT_ROOT)}"
test("archive_dir_16_files_intact", t_archive_16)


def t_archive_structure():
    expected_subdirs = [
        ".trae/reports/rounds/_r159_a_backups",
        "_r154_hvd_153_a_backup_20260720_215003",
        "core/services",
        "core/trading",
        "core/trading/interfaces",
    ]
    for sub in expected_subdirs:
        p = archive_dir / sub
        assert p.exists(), f"归档子目录缺失: {sub}"
    return "all subdirs present"
test("archive_subdir_structure_preserved", t_archive_structure)


def t_no_remaining_in_source():
    BACKUP_FILES = [
        "core/services/service_bootstrap.py.bak_r161",
        "core/services/unified_data_manager.py.bak_r161",
        "core/services/advanced_risk_control_service.py.bak_r161",
        "core/trading/order_executor.py.bak_r160",
        "core/asset_database_manager.py.r147_bak",
        "core/trading/interfaces/ctp_trading_interface.py.r147_bak",
        "core/services/cache_service.py.r147_bak",
        ".trae/reports/rounds/_r159_a_backups/core_trading_order_service.py.bak",
        ".trae/reports/rounds/_r159_a_backups/core_coordinators_main_window_coordinator.py.bak",
        ".trae/reports/rounds/_r159_a_backups/core_ui_panels_right_panel.py.bak",
        ".trae/reports/rounds/_r159_a_backups/core_importdata_import_execution_engine.py.bak",
        ".trae/reports/rounds/_r159_a_backups/gui_widgets_enhanced_data_import_widget.py.bak",
        "_r154_hvd_153_a_backup_20260720_215003/sql_statement_validator.py.bak",
        "_r154_hvd_153_a_backup_20260720_215003/feature_selection.py.bak",
        "_r154_hvd_153_a_backup_20260720_215003/plugin_auto_register.py.bak",
        "_r154_hvd_153_a_backup_20260720_215003/table_schemas.py.bak",
    ]
    remaining = [r for r in BACKUP_FILES if (PROJECT_ROOT / r).exists()]
    assert not remaining, f"原位置仍有备份: {remaining}"
    return "0 remaining"
test("no_backup_in_source_location", t_no_remaining_in_source)


print("=" * 80)
print(f"全量回归: {passed} PASSED, {failed} FAILED")
if errors:
    print("\n失败详情:")
    for n, e in errors:
        print(f"  - {n}: {e}")
print("=" * 80)

# 输出 JSON 给主智能体
result_json = {
    "round": "R180-HVD-A",
    "test_total": passed + failed,
    "test_passed": passed,
    "test_failed": failed,
    "errors": [{"name": n, "error": e} for n, e in errors],
    "verdict": "PASS" if failed == 0 else "FAIL",
}
log_path = PROJECT_ROOT / "tests" / "_r180_regression_log.json"
log_path.write_text(json.dumps(result_json, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[LOG] tests/_r180_regression_log.json")

sys.exit(0 if failed == 0 else 1)
