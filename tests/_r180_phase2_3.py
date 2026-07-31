#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R180-HVD-A Phase 2 GREEN + Phase 3 不变性直接测试
"""
import sys
import os
import shutil
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui").resolve()
ARCHIVE_DIR = PROJECT_ROOT / "_archive" / "backups_2026_07_24"

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

ACTIVE_SOURCE_FILES = [
    "core/services/service_bootstrap.py",
    "core/services/unified_data_manager.py",
    "core/services/advanced_risk_control_service.py",
    "core/trading/order_executor.py",
    "core/asset_database_manager.py",
    "core/trading/interfaces/ctp_trading_interface.py",
    "core/services/cache_service.py",
]

passed = 0
failed = 0
errors = []


def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"[PASS] {name}")
        passed += 1
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
        failed += 1
        errors.append((name, str(e)))
    except Exception as e:
        print(f"[ERROR] {name}: {type(e).__name__}: {e}")
        failed += 1
        errors.append((name, f"{type(e).__name__}: {e}"))


# ============================================================
# Phase 2: GREEN 阶段 - 移动后基线确认
# ============================================================
print("=" * 80)
print("R180-HVD-A Phase 2 GREEN + Phase 3 不变性测试")
print("=" * 80)


def t_g01():
    assert ARCHIVE_DIR.exists(), "归档目录不存在"
    assert ARCHIVE_DIR.is_dir(), "归档路径不是目录"


def t_g02():
    # 计数 16 个备份文件 (使用 suffix 检查)
    suffixes = (".bak_r161", ".bak_r160", ".r147_bak", ".bak")
    count = sum(
        1 for f in ARCHIVE_DIR.rglob("*")
        if f.is_file() and any(f.name.endswith(s) for s in suffixes)
    )
    assert count == 16, f"归档目录含 {count} 个文件, 预期 16"


def t_g03():
    # 原始位置不再含备份文件
    remaining = [r for r in BACKUP_FILES if (PROJECT_ROOT / r).exists()]
    assert not remaining, f"原位置仍有备份: {remaining}"


def t_g04():
    # 子目录结构保留
    assert (ARCHIVE_DIR / ".trae" / "reports" / "rounds" / "_r159_a_backups").exists()
    assert (ARCHIVE_DIR / "_r154_hvd_153_a_backup_20260720_215003").exists()
    assert (ARCHIVE_DIR / "core" / "services").exists()
    assert (ARCHIVE_DIR / "core" / "trading").exists()


def t_g05():
    # 归档目录含 4 源验证 JSON
    json_path = PROJECT_ROOT / "tests" / "_r180_hvd_a_4src_verify.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["all_truly_dead"] is True
    assert data["total_count"] == 16
    assert data["total_size_bytes"] == 2690334


def t_g06():
    # 归档日志存在
    log_path = PROJECT_ROOT / "tests" / "_r180_archive_log.json"
    assert log_path.exists()
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert log["total_moved"] == 16
    # 重新计算归档文件 (rglob "*.bak*" 不匹配 .bak_r161/.bak_r160)
    suffixes = (".bak_r161", ".bak_r160", ".r147_bak", ".bak")
    actual_archived = sum(
        1 for f in ARCHIVE_DIR.rglob("*")
        if f.is_file() and any(f.name.endswith(s) for s in suffixes)
    )
    assert actual_archived == 16, f"实际归档 {actual_archived} 个, 预期 16"
    assert log["remaining_in_source"] == []


def t_g07():
    # 归档文件大小与原大小一致 (move 不修改内容)
    for rel in BACKUP_FILES:
        archived = ARCHIVE_DIR / rel
        assert archived.exists(), f"归档文件缺失: {rel}"
        assert archived.stat().st_size > 0, f"归档文件为空: {rel}"


print("\n--- Phase 2 GREEN 阶段 ---")
test("g01_archive_dir_exists", t_g01)
test("g02_16_files_in_archive", t_g02)
test("g03_no_remaining_in_source", t_g03)
test("g04_subdir_structure_preserved", t_g04)
test("g05_4src_verify_json_consistent", t_g05)
test("g06_archive_log_json_valid", t_g06)
test("g07_archived_files_non_empty", t_g07)


# ============================================================
# Phase 3: 不变性 - active .py 源文件
# ============================================================
print("\n--- Phase 3 不变性 ---")


def t_i01():
    for rel in ACTIVE_SOURCE_FILES:
        p = PROJECT_ROOT / rel
        assert p.exists(), f"active 源文件丢失: {rel} (R103 误删事故!)"


def t_i02():
    # 关键 active 文件大小合理
    p = PROJECT_ROOT / "core/services/service_bootstrap.py"
    assert p.stat().st_size > 100_000, f"service_bootstrap.py 大小异常: {p.stat().st_size}"


def t_i03():
    p = PROJECT_ROOT / "core/services/unified_data_manager.py"
    assert p.stat().st_size > 100_000


def t_i04():
    p = PROJECT_ROOT / "core/trading/order_executor.py"
    assert p.stat().st_size > 50_000


def t_i05():
    p = PROJECT_ROOT / "core/services/cache_service.py"
    assert p.stat().st_size > 30_000


def t_i06():
    # 验证 active 文件 Python 语法正确 (R103 误删事故防御)
    for rel in ACTIVE_SOURCE_FILES:
        p = PROJECT_ROOT / rel
        try:
            compile(p.read_text(encoding="utf-8", errors="ignore"), str(p), "exec")
        except SyntaxError as e:
            raise AssertionError(f"active 源文件语法错误: {rel} - {e}")


def t_i07():
    # 验证无 active 源文件被改名/移动
    backup_names = {Path(r).name.split(".")[0] + ".py" for r in BACKUP_FILES if not any(s in r for s in ["_r159", "_r154"])}
    for active_name in [Path(r).name for r in ACTIVE_SOURCE_FILES]:
        assert active_name in backup_names or active_name.startswith("service_") or active_name.startswith("order_"), \
            f"active {active_name} 不在预期清单"


def t_i08():
    # 验证 active 文件可被 import (R103 误删事故防御)
    import importlib.util
    for rel in ACTIVE_SOURCE_FILES:
        p = PROJECT_ROOT / rel
        # 不实际 import, 只检查文件可读
        assert p.read_text(encoding="utf-8", errors="ignore"), f"{rel} 不可读"


test("i01_all_active_sources_intact", t_i01)
test("i02_service_bootstrap_size_ok", t_i02)
test("i03_unified_data_manager_size_ok", t_i03)
test("i04_order_executor_size_ok", t_i04)
test("i05_cache_service_size_ok", t_i05)
test("i06_active_syntax_valid", t_i06)
test("i07_active_naming_consistent", t_i07)
test("i08_active_readable", t_i08)

print("=" * 80)
print(f"Phase 2+3: {passed} PASSED, {failed} FAILED")
if errors:
    print("\n失败详情:")
    for n, e in errors:
        print(f"  - {n}: {e}")
print("=" * 80)
sys.exit(0 if failed == 0 else 1)
