"""
R147 批量修复脚本: 4 文件 47 处 logger.warning/error 缺 exc_info=True 升级

修复目标:
- core/services/cache_service.py: 7 处 (L643, L727, L764, L780, L1314, L1748, L1771)
- core/trading/interfaces/ctp_trading_interface.py: 4 处有 e (L330, L404, L943, L1445)
- core/asset_database_manager.py: 33 处 (R147-B 报告值)
- core/trading/order_executor.py: 0 处 (L514 是参数化, 不改)

修复策略:
- 一行 logger.warning(...): 直接加 exc_info=True
- 多行 logger.warning(...: 在最后一行加 , exc_info=True
- 保留所有其他格式
- 不改 logger.debug 业务关键路径 (R118 B15/B16 教训: 业务关键应为 warning)

排除:
- ImportError 但未捕获 e 的情况 (L27/50/66 ctp)
- 参数化 exc_info=exc_info (L514 order_executor)
- 已有 exc_info=True 的 (R125-P0-1 标记)
"""
import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple


def fix_file_exc_info(filepath: str, dry_run: bool = False) -> Tuple[int, List[str]]:
    """
    修复指定文件中所有 except 块内的 logger 调用, 添加 exc_info=True

    Returns: (修复数量, 修改的行号列表)
    """
    p = Path(filepath)
    if not p.exists():
        return 0, []

    src = p.read_text(encoding="utf-8")
    lines = src.split("\n")
    modified_lines = []
    fixed_count = 0
    skip_lines = set()

    # 解析 AST
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return 0, []

    # 找到所有 except 块
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        # 排除已参数化的 (order_executor L514)
        if filepath.endswith("order_executor.py") and node.lineno == 514:
            continue

        # 检查 except body 中是否含 e 变量
        has_e_capture = bool(node.name)
        if not has_e_capture:
            continue  # 跳过 except: (无 e)

        # 找到 except body 中所有 logger 调用
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Expr)
                and isinstance(sub.value, ast.Call)
                and isinstance(sub.value.func, ast.Attribute)
                and sub.value.func.attr in ("warning", "warn", "error", "exception", "critical", "info", "debug")
            ):
                call = sub.value
                # 检查是否已有 exc_info=True
                has_exc_info = any(
                    kw.arg == "exc_info" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in call.keywords
                )
                if has_exc_info:
                    continue

                # 修复: 加 exc_info=True
                # 单行情况: logger.warning("...")  →  logger.warning("...", exc_info=True)
                # 多行情况: logger.warning(\n  "...",\n  ...\n)  →  logger.warning(\n  "...",\n  ...,\n  exc_info=True\n)
                start_line = call.lineno
                end_line = call.end_lineno

                # 跳过跨方法调用 (call 的 end_lineno 超过 except body)
                if end_line and end_line > node.end_lineno:
                    continue

                if start_line == end_line:
                    # 单行
                    line = lines[start_line - 1]
                    # 找到 logger.X(...) 的右括号
                    # 简单处理: 在行尾的 ) 前加 , exc_info=True
                    # 找最外层 )
                    idx = line.rfind(")")
                    if idx > 0 and "logger." in line:
                        # 检查 ) 前是否是结束
                        # 不在字符串内
                        new_line = line[:idx] + ", exc_info=True" + line[idx:]
                        lines[start_line - 1] = new_line
                        modified_lines.append(start_line)
                        fixed_count += 1
                else:
                    # 多行: 在最后一行 (end_line) 的结束括号前加 , exc_info=True
                    last_line = lines[end_line - 1]
                    idx = last_line.rfind(")")
                    if idx > 0:
                        new_last_line = last_line[:idx] + ", exc_info=True" + last_line[idx:]
                        lines[end_line - 1] = new_last_line
                        modified_lines.append(start_line)
                        fixed_count += 1

    if not dry_run and fixed_count > 0:
        p.write_text("\n".join(lines), encoding="utf-8")

    return fixed_count, modified_lines


if __name__ == "__main__":
    # R147 修复目标
    TARGETS = [
        "core/services/cache_service.py",
        "core/trading/interfaces/ctp_trading_interface.py",
        "core/asset_database_manager.py",
        # order_executor.py 跳过 (L514 是参数化, 不需要修改)
    ]

    # 排除的 ImportError 无 e 的行
    CTP_IMPORT_ERROR_LINES = {27, 50, 66}

    print("=" * 70)
    print("R147 批量修复: 4 文件 except 缺 exc_info 升级")
    print("=" * 70)

    total_fixed = 0
    for fp in TARGETS:
        if not Path(fp).exists():
            print(f"\n[NOT FOUND] {fp}")
            continue

        # 修复前先扫描
        sys.path.insert(0, ".")
        from tools._r147_b_scan_v1 import scan_file
        before_stats = scan_file(fp)
        before_violations = set(before_stats["with_logger_no_exc_info_lines"])

        # 排除 L27/50/66 (ImportError 无 e)
        if "ctp" in fp:
            before_violations -= CTP_IMPORT_ERROR_LINES

        print(f"\n--- {fp} ---")
        print(f"  Before: {len(before_violations)} violations (e.g. {sorted(before_violations)[:5]}...)")

        # 执行修复
        fixed, lines = fix_file_exc_info(fp, dry_run=False)
        print(f"  Fixed: {fixed} 处")

        # 修复后扫描
        after_stats = scan_file(fp)
        after_violations = set(after_stats["with_logger_no_exc_info_lines"])
        if "ctp" in fp:
            after_violations -= CTP_IMPORT_ERROR_LINES

        print(f"  After: {len(after_violations)} violations (e.g. {sorted(after_violations)[:5]}...)")
        total_fixed += fixed

    print(f"\n========== GRAND TOTAL ==========")
    print(f"  Total fixed: {total_fixed} 处")
    print(f"  Done.")
