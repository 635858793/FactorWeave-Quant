#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R180-HVD-A Step 4: 物理归档脚本
严格遵循 R6 §6.3 步骤 7-8 (执行前 TDD 基线已完成, R+1 round 已安排)
严禁: rm 直接删除 (R85 教训), 必须 move 到 _archive/
严禁: 物理删除任何 .py 源文件, 仅移动 .bak/.r147_bak/.bak_r161 备份
"""
import sys
import os
import shutil
import json
from pathlib import Path

PROJECT_ROOT = Path("d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui").resolve()
ARCHIVE_ROOT = PROJECT_ROOT / "_archive" / "backups_2026_07_24"

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


def main():
    print("=" * 80)
    print("R180-HVD-A Step 4: 物理归档 (16 个备份文件 -> _archive/backups_2026_07_24/)")
    print("=" * 80)

    # 1. 创建归档目录
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"\n[1/3] 归档目录已创建: {ARCHIVE_ROOT.relative_to(PROJECT_ROOT)}")

    # 2. 移动 16 个文件
    moved = []
    failed = []
    total_size = 0
    print(f"\n[2/3] 开始移动 {len(BACKUP_FILES)} 个文件...")

    for rel in BACKUP_FILES:
        src = PROJECT_ROOT / rel
        if not src.exists():
            print(f"  [SKIP] {rel} (源不存在)")
            failed.append(rel)
            continue

        # 保留子目录结构
        dst = ARCHIVE_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        size = src.stat().st_size
        try:
            shutil.move(str(src), str(dst))
            moved.append({"src": rel, "dst": str(dst.relative_to(PROJECT_ROOT)), "size": size})
            total_size += size
            print(f"  [MOVE] {rel} ({size:>8} bytes)")
        except Exception as e:
            print(f"  [FAIL] {rel}: {type(e).__name__}: {e}")
            failed.append(rel)

    # 3. 验证归档
    print(f"\n[3/3] 归档验证:")
    print(f"  - 移动成功: {len(moved)}/{len(BACKUP_FILES)}")
    print(f"  - 总大小:   {total_size} bytes ({total_size/1024/1024:.2f} MB)")
    print(f"  - 失败:     {len(failed)}")

    # 验证原位置不再含备份文件
    remaining = [r for r in BACKUP_FILES if (PROJECT_ROOT / r).exists()]
    print(f"  - 残留备份: {len(remaining)} (应为 0)")

    # 验证归档目录含 16 个文件
    archived = list(ARCHIVE_ROOT.rglob("*.bak*"))
    print(f"  - 归档文件: {len(archived)} (应 >= 16)")

    # 输出归档清单 JSON
    archive_log = {
        "round": "R180-HVD-A",
        "task": "backup_file_physical_archive",
        "date": "2026-07-24",
        "archive_dir": str(ARCHIVE_ROOT.relative_to(PROJECT_ROOT)),
        "total_moved": len(moved),
        "total_size_bytes": total_size,
        "total_size_str": f"{total_size/1024/1024:.2f} MB",
        "r179_c_estimate": "1.4 MB",
        "r179_c_actual": f"{total_size/1024/1024:.2f} MB",
        "r179_c_diff_pct": f"{(total_size/1466624 - 1)*100:.1f}%",
        "moved": moved,
        "failed": failed,
        "remaining_in_source": remaining,
        "archived_count": len(archived),
    }
    log_path = PROJECT_ROOT / "tests" / "_r180_archive_log.json"
    log_path.write_text(json.dumps(archive_log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[LOG] 归档日志: tests/_r180_archive_log.json")

    return 0 if (len(failed) == 0 and len(remaining) == 0 and len(archived) >= 16) else 1


if __name__ == "__main__":
    sys.exit(main())
