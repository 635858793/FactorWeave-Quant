#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R180-HVD-A Phase 1 RED 阶段直接 Python 执行 (避免 conftest 钩子干扰)
"""
import sys
import os
import shutil
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui").resolve()

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


# Phase 1: RED 阶段
def t_01_count():
    actual = sum(1 for r in BACKUP_FILES if (PROJECT_ROOT / r).exists())
    assert actual == 16, f"实际 {actual} 个, 任务描述说 13 个 (R110-C 反例)"

def t_02_exist():
    missing = [r for r in BACKUP_FILES if not (PROJECT_ROOT / r).exists()]
    assert not missing, f"备份文件缺失: {missing}"

def t_03_archive_dir():
    archive = PROJECT_ROOT / "_archive" / "backups_2026_07_24"
    if archive.exists():
        shutil.rmtree(archive, ignore_errors=True)
    assert not archive.exists(), "归档目录不应存在"

def t_04_size():
    total = sum((PROJECT_ROOT / r).stat().st_size for r in BACKUP_FILES if (PROJECT_ROOT / r).exists())
    assert 2_400_000 < total < 2_800_000, f"总大小 {total} bytes 超出预期"

def t_05_active():
    for r in ACTIVE_SOURCE_FILES:
        p = PROJECT_ROOT / r
        assert p.exists(), f"active 源文件缺失: {r}"
        assert p.stat().st_size > 0, f"active 源文件为空: {r}"

def t_06_json():
    p = PROJECT_ROOT / "tests" / "_r180_hvd_a_4src_verify.json"
    assert p.exists(), "4 源验证 JSON 缺失"

def t_07_all_dead():
    p = PROJECT_ROOT / "tests" / "_r180_hvd_a_4src_verify.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for r in data["results"]:
        assert r["is_truly_dead"], f"{r['file']} 非死代码"
        assert r["src2_grep_refs"] == 0, f"{r['file']} 有业务引用"
        assert r["src3_codegraph_hits"] == 0, f"{r['file']} 有 import 引用"

print("=" * 80)
print("R180-HVD-A Phase 1 RED 阶段测试")
print("=" * 80)
test("01_backup_count_is_16_not_13", t_01_count)
test("02_all_backup_files_physically_exist", t_02_exist)
test("03_archive_dir_not_exists_before_archive", t_03_archive_dir)
test("04_total_size_about_2_57_mb", t_04_size)
test("05_active_source_files_intact", t_05_active)
test("06_4src_verify_json_exists", t_06_json)
test("07_all_truly_dead_in_json", t_07_all_dead)

print("=" * 80)
print(f"Phase 1 RED: {passed} PASSED, {failed} FAILED")
if errors:
    print("\n失败详情:")
    for n, e in errors:
        print(f"  - {n}: {e}")
print("=" * 80)
sys.exit(0 if failed == 0 else 1)
