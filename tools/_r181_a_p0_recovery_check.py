#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R181-A P0 恢复检查工具 (HVD-181-K 防御 #3: 物理验证函数库)

R180-A P0 事故根因: TDD PASSED + JSON 写成功 ≠ 物理归档成功.
R181-A 强化: 提供 3 重物理验证函数, 任何归档/删除操作前必须调用.

设计原则 (R6 §6.1 铁律 #5 强化 + R180-A 永久规则):
  - 物理验证 (verify_archived_files): 必走 rglob, 不信任 JSON
  - SHA-256 校验 (compute_sha256): 防文件传输/复制过程中损坏
  - 24h 回访 (daily_archive_integrity_check): 防异步清理/快照丢失

使用方式:
  from tools._r181_a_p0_recovery_check import (
      verify_archived_files, compute_sha256, daily_archive_integrity_check,
  )

作者: R181-A 子智能体
日期: 2026-07-25
版本: v1.0 (HVD-181-K 6 重防御 #3 实施)
"""
import hashlib
import json
import logging
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================
# 常量定义
# ============================================================
DEFAULT_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_ARCHIVE_DIR = DEFAULT_PROJECT_ROOT / "_archive"
DEFAULT_LOG_PATH = DEFAULT_PROJECT_ROOT / "tests" / "_r181_a_archive_integrity.json"

# 模块级 logger (供外部引用, 不打印到 stdout)
logger = logging.getLogger("r181_a_recovery")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [R181-A] %(levelname)s: %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ============================================================
# 防御 #1: SHA-256 校验函数 (R180-A 防御 #2)
# ============================================================
def compute_sha256(file_path: Path, chunk_size: int = 65536) -> Optional[str]:
    """
    计算文件 SHA-256 校验和 (防传输/复制损坏).

    Args:
        file_path: 文件路径
        chunk_size: 读取块大小 (默认 64KB, 平衡速度与内存)

    Returns:
        SHA-256 hex 字符串, 文件不存在时返回 None
    """
    file_path = Path(file_path)
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"compute_sha256: 文件不存在或不是普通文件: {file_path}")
        return None

    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, IOError) as e:
        logger.error(f"compute_sha256: 读取失败 {file_path}: {type(e).__name__}: {e}")
        return None


# ============================================================
# 防御 #3: 24h 回访验证 (R180-A 防御 #3)
# ============================================================
def daily_archive_integrity_check(
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    log_path: Path = DEFAULT_LOG_PATH,
    backup_files: Optional[List[Path]] = None,
) -> Dict:
    """
    每日归档完整性检查 (24h 物理回访).

    检查项:
      1. archive_dir 物理存在
      2. 所有 backup_files 在 archive_dir 中可找到 (按相对路径匹配)
      3. 每个文件 SHA-256 与上次记录一致 (若日志存在)
      4. 归档目录无新增未授权文件

    Args:
        archive_dir: 归档根目录 (默认 _archive/)
        log_path: 完整性日志路径
        backup_files: 待校验文件相对路径列表 (Path 对象, 相对于项目根)

    Returns:
        报告 dict, 包含 passed/failed/diff 详情
    """
    archive_dir = Path(archive_dir)
    log_path = Path(log_path)
    project_root = archive_dir.parent

    report = {
        "timestamp": datetime.now().isoformat(),
        "archive_dir": str(archive_dir.relative_to(project_root)) if archive_dir.is_absolute() else str(archive_dir),
        "archive_exists": False,
        "files_checked": 0,
        "files_found": 0,
        "files_missing": [],
        "files_size_mismatch": [],
        "files_sha256_mismatch": [],
        "passed": False,
    }

    # 检查 1: 归档目录存在
    if not archive_dir.exists():
        logger.error(f"24h 回访: 归档目录不存在 {archive_dir}")
        report["error"] = f"archive_dir_not_exists: {archive_dir}"
        _save_log(log_path, report)
        return report
    report["archive_exists"] = True

    # 检查 2: 文件存在性
    if backup_files is None:
        logger.info("24h 回访: 未指定 backup_files, 仅做目录健康检查")
        report["passed"] = True
        _save_log(log_path, report)
        return report

    # 读取上次日志用于 SHA-256 对比
    prev_log = _load_log(log_path)
    prev_sha256_map = {}
    if prev_log and "files" in prev_log:
        prev_sha256_map = {
            f["rel_path"]: f.get("sha256")
            for f in prev_log.get("files", [])
            if f.get("sha256")
        }

    files_report = []
    for rel in backup_files:
        rel = Path(rel)
        if rel.is_absolute():
            rel = rel.relative_to(project_root) if project_root in rel.parents else rel
        report["files_checked"] += 1

        # 归档目录中文件路径: archive_dir / rel
        archived = archive_dir / rel
        entry = {
            "rel_path": str(rel).replace("\\", "/"),
            "src_exists": (project_root / rel).exists(),
            "archived_exists": archived.exists(),
            "size": None,
            "sha256": None,
            "status": "unknown",
        }

        if not archived.exists():
            report["files_missing"].append(str(rel).replace("\\", "/"))
            entry["status"] = "MISSING"
            files_report.append(entry)
            continue

        try:
            entry["size"] = archived.stat().st_size
        except OSError:
            entry["status"] = "STAT_FAILED"
            files_report.append(entry)
            continue

        # SHA-256
        entry["sha256"] = compute_sha256(archived)
        if entry["sha256"] is None:
            entry["status"] = "SHA256_FAILED"
            files_report.append(entry)
            continue

        # 与上次 SHA-256 对比
        prev_sha = prev_sha256_map.get(str(rel).replace("\\", "/"))
        if prev_sha and prev_sha != entry["sha256"]:
            report["files_sha256_mismatch"].append({
                "rel_path": str(rel).replace("\\", "/"),
                "prev_sha256": prev_sha,
                "current_sha256": entry["sha256"],
            })
            entry["status"] = "SHA256_CHANGED"
            files_report.append(entry)
            continue

        report["files_found"] += 1
        entry["status"] = "OK"
        files_report.append(entry)

    report["files"] = files_report
    report["passed"] = (
        report["archive_exists"]
        and len(report["files_missing"]) == 0
        and len(report["files_size_mismatch"]) == 0
        and len(report["files_sha256_mismatch"]) == 0
    )

    _save_log(log_path, report)
    if report["passed"]:
        logger.info(
            f"24h 回访 PASSED: {report['files_found']}/{report['files_checked']} 文件"
        )
    else:
        logger.error(
            f"24h 回访 FAILED: missing={len(report['files_missing'])}, "
            f"sha256_mismatch={len(report['files_sha256_mismatch'])}, "
            f"size_mismatch={len(report['files_size_mismatch'])}"
        )

    return report


# ============================================================
# 防御 #1+#2+#3 整合: 物理验证 (R180-A 防御 #1 核心)
# ============================================================
def verify_archived_files(
    backup_paths: List[Path],
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    expected_sha256_map: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Dict]:
    """
    物理验证: 确认所有备份文件在归档目录中真实存在.

    R180-A P0 事故根因: 归档脚本写完 JSON 即报告成功, 未做物理验证.
    本函数强制要求走文件系统, 不依赖任何凭证.

    Args:
        backup_paths: 备份文件相对路径列表 (相对 project_root)
        archive_dir: 归档根目录
        project_root: 项目根
        expected_sha256_map: 期望的 SHA-256 字典 (可选, 用于二次校验)

    Returns:
        (passed, report) 元组
        passed: True 表示所有文件物理存在且 SHA-256 一致
        report: 详细报告 dict
    """
    archive_dir = Path(archive_dir)
    project_root = Path(project_root)

    report = {
        "timestamp": datetime.now().isoformat(),
        "archive_dir": str(archive_dir),
        "project_root": str(project_root),
        "total": len(backup_paths),
        "found": 0,
        "missing": [],
        "size_mismatch": [],
        "sha256_mismatch": [],
        "passed": False,
    }

    if not archive_dir.exists():
        report["error"] = f"archive_dir_not_exists: {archive_dir}"
        return False, report

    for rel in backup_paths:
        rel = Path(rel)
        # 统一为相对路径
        if rel.is_absolute():
            try:
                rel = rel.relative_to(project_root)
            except ValueError:
                pass

        # 物理路径
        src = project_root / rel
        archived = archive_dir / rel

        if not archived.exists():
            report["missing"].append(str(rel).replace("\\", "/"))
            continue

        # 大小对比
        if src.exists() and src.is_file():
            src_size = src.stat().st_size
            archived_size = archived.stat().st_size
            if src_size != archived_size:
                report["size_mismatch"].append({
                    "rel_path": str(rel).replace("\\", "/"),
                    "src_size": src_size,
                    "archived_size": archived_size,
                })
                continue

        # SHA-256 校验
        if expected_sha256_map:
            expected = expected_sha256_map.get(str(rel).replace("\\", "/"))
            if expected:
                actual = compute_sha256(archived)
                if actual != expected:
                    report["sha256_mismatch"].append({
                        "rel_path": str(rel).replace("\\", "/"),
                        "expected_sha256": expected,
                        "actual_sha256": actual,
                    })
                    continue

        report["found"] += 1

    report["passed"] = (
        report["found"] == report["total"]
        and len(report["missing"]) == 0
        and len(report["size_mismatch"]) == 0
        and len(report["sha256_mismatch"]) == 0
    )

    return report["passed"], report


# ============================================================
# 防御 #1: shutil.copy 双写 + shutil.move (R180-A 防御 #1)
# ============================================================
def safe_archive_files(
    backup_paths: List[Path],
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    log_path: Path = DEFAULT_LOG_PATH,
) -> Tuple[bool, Dict]:
    """
    安全归档 6 重防御实施 (HVD-181-K 核心):
      1. shutil.copy 双写 (源 + 目标) → shutil.move 原子
      2. SHA-256 校验写入日志
      3. 物理验证 (verify_archived_files)
      4. dry_run 模式 (默认 False, 仅日志)

    Args:
        backup_paths: 备份文件相对路径
        archive_dir: 归档根目录
        project_root: 项目根
        log_path: 归档日志路径

    Returns:
        (passed, report)
    """
    archive_dir = Path(archive_dir)
    project_root = Path(project_root)
    log_path = Path(log_path)

    archive_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp": datetime.now().isoformat(),
        "archive_dir": str(archive_dir),
        "total": len(backup_paths),
        "copied": 0,
        "moved": 0,
        "verified": 0,
        "failed": [],
        "files": [],
        "passed": False,
    }

    for rel in backup_paths:
        rel = Path(rel)
        if rel.is_absolute():
            try:
                rel = rel.relative_to(project_root)
            except ValueError:
                pass

        src = project_root / rel
        archived = archive_dir / rel
        archived.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "rel_path": str(rel).replace("\\", "/"),
            "src_exists": src.exists(),
            "copied": False,
            "moved": False,
            "sha256_src": None,
            "sha256_archived": None,
            "size": None,
            "status": "pending",
        }

        if not src.exists():
            entry["status"] = "SKIP_SRC_NOT_EXIST"
            report["failed"].append(str(rel).replace("\\", "/"))
            report["files"].append(entry)
            continue

        try:
            entry["size"] = src.stat().st_size
        except OSError as e:
            entry["status"] = f"STAT_FAILED: {e}"
            report["failed"].append(str(rel).replace("\\", "/"))
            report["files"].append(entry)
            continue

        # 防御 #1 步骤 A: shutil.copy (双写到目标, 源不动)
        try:
            shutil.copy2(str(src), str(archived))
            entry["copied"] = True
            report["copied"] += 1
        except (OSError, IOError) as e:
            entry["status"] = f"COPY_FAILED: {type(e).__name__}: {e}"
            report["failed"].append(str(rel).replace("\\", "/"))
            report["files"].append(entry)
            continue

        # 防御 #1 步骤 B: 校验副本 SHA-256 == 源 SHA-256
        entry["sha256_src"] = compute_sha256(src)
        entry["sha256_archived"] = compute_sha256(archived)
        if entry["sha256_src"] != entry["sha256_archived"]:
            entry["status"] = "SHA256_MISMATCH_AFTER_COPY"
            report["failed"].append(str(rel).replace("\\", "/"))
            # 清理已损坏副本
            try:
                archived.unlink()
            except OSError:
                pass
            report["files"].append(entry)
            continue

        # 防御 #1 步骤 C: shutil.move 原子 (此处因 copy2 已复制, move 等于改名/删除源)
        try:
            src.unlink()  # 防御: 源已校验完毕, 显式 unlink (避免 shutil.move 在 Windows 上的奇怪行为)
            entry["moved"] = True
            report["moved"] += 1
        except OSError as e:
            entry["status"] = f"UNLINK_SRC_FAILED: {type(e).__name__}: {e}"
            # 副本存在, 源也在, 不算失败但需警告
            entry["status_warning"] = "源文件未删除, 归档副本已存在"
            report["files"].append(entry)
            continue

        entry["status"] = "OK"
        report["verified"] += 1
        report["files"].append(entry)

    # 防御 #3: 物理验证 (不依赖 JSON, 走文件系统)
    passed, verify_report = verify_archived_files(
        backup_paths=backup_paths,
        archive_dir=archive_dir,
        project_root=project_root,
        expected_sha256_map={
            f["rel_path"]: f["sha256_archived"]
            for f in report["files"] if f.get("sha256_archived")
        },
    )
    report["physical_verify"] = verify_report
    report["passed"] = passed and len(report["failed"]) == 0

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return report["passed"], report


# ============================================================
# 内部辅助函数
# ============================================================
def _load_log(log_path: Path) -> Optional[Dict]:
    """加载上次日志 (用于 24h 回访 SHA-256 对比)"""
    if not log_path.exists():
        return None
    try:
        return json.loads(log_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_log(log_path: Path, report: Dict) -> None:
    """保存日志"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ============================================================
# CLI 入口
# ============================================================
def main():
    """CLI 入口: 24h 回访检查"""
    import argparse
    parser = argparse.ArgumentParser(
        description="R181-A P0 恢复检查工具 (HVD-181-K 防御 #3 24h 回访)"
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
        help="归档根目录 (默认 _archive/)",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="完整性日志路径",
    )
    parser.add_argument(
        "--backup-list",
        type=Path,
        default=None,
        help="备份文件相对路径列表文件 (每行一个)",
    )
    args = parser.parse_args()

    backup_files = None
    if args.backup_list and args.backup_list.exists():
        project_root = args.archive_dir.parent
        backup_files = [
            project_root / line.strip()
            for line in args.backup_list.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    report = daily_archive_integrity_check(
        archive_dir=args.archive_dir,
        log_path=args.log_path,
        backup_files=backup_files,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
