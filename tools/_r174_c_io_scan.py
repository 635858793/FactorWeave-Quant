"""
R174-C 锁内 IO 直接扫描 (基于行号定位, 避免 AST 切片缩进问题)
R104 §12 铁律 #5 严格实施
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Tuple


def find_with_block_ranges(source_lines: List[str], method_start: int, method_end: int) -> List[Dict]:
    """
    在方法体内, 用基于缩进的扫描找出所有 with 块边界
    返回: [{lock, start, end, depth}]
    """
    blocks = []
    in_method = False
    for i in range(method_start - 1, min(method_end, len(source_lines))):
        line = source_lines[i]
        if not in_method and re.match(r'^\s*def\s+', line):
            in_method = True
            continue
        if not in_method:
            continue
        # 找 with self._xxx_lock:
        m = re.match(r'^(\s*)with\s+self\.(\w+)\s*:', line)
        if m:
            indent = len(m.group(1))
            lock = m.group(2)
            if "_lock" in lock or lock == "lock":
                # 找出块结束 (回到同/低缩进)
                block_end = method_end
                for j in range(i + 1, min(method_end, len(source_lines))):
                    next_line = source_lines[j]
                    if next_line.strip() and not next_line.startswith(" " * (indent + 1)):
                        # 检查是否是同缩进 (新语句) 或更低
                        next_indent = len(next_line) - len(next_line.lstrip())
                        if next_indent <= indent:
                            block_end = j
                            break
                blocks.append({
                    "lock": lock,
                    "start": i + 1,
                    "end": block_end,
                    "indent": indent,
                })
    return blocks


def check_io_in_range(source_lines: List[str], start: int, end: int) -> List[Dict]:
    """检查区间内的 IO 调用"""
    io_patterns = [
        "publish", "save_account", "save_position", "save_fund_info",
        "delete_account", "delete_position", "get_accounts", "query_positions",
        "save(", "execute(", "fetch(", "send(", "submit",
        ".save", ".execute", ".fetch", ".send", ".submit", ".delete",
        "trading_interface", "repository.save", "repository.delete", "repository.get",
    ]
    findings = []
    for i in range(start - 1, min(end, len(source_lines))):
        line = source_lines[i]
        for pat in io_patterns:
            if pat in line and "self." in line and "#" not in line.split(pat)[0]:
                findings.append({
                    "line": i + 1,
                    "code": line.strip()[:160],
                    "io_keyword": pat,
                })
                break
    return findings


def main():
    # AccountManager 长锁方法 (L行号)
    am_methods = [
        ("refresh_accounts", 269, 310),
        ("create_account", 372, 427),
        ("update_account", 428, 469),
        ("query_accounts", 485, 529),
        ("delete_account", 530, 562),
        ("create_position", 563, 611),
        ("update_position", 611, 684),
        ("query_positions", 698, 738),
        ("delete_position", 740, 770),
        ("update_fund_info", 772, 815),
        ("freeze_cash", 1164, 1234),
        ("unfreeze_cash", 1235, 1310),
        ("_on_position_updated", 2400, 2565),
        ("_schedule_position_sync", 2589, 2620),
    ]

    # TradingEngine 长锁方法
    te_methods = [
        ("_reduce_pending_position", 580, 656),
        ("add_signal", 760, 825),
        ("execute_signal", 1100, 1150),
        ("_execute_buy", 1232, 1395),
        ("_execute_sell", 1419, 1650),
        ("_risk_check", 1760, 1942),
        ("update_positions", 2307, 2340),
        ("_publish_correlation_warning", 2750, 2880),
    ]

    print("=" * 80)
    print("R174-C 锁内 IO 验证 (R104 §12 铁律 #5 直接行号扫描)")
    print("=" * 80)

    am_path = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading/account_manager.py"
    am_source = Path(am_path).read_text(encoding="utf-8", errors="ignore").split("\n")
    print(f"\n--- AccountManager ({am_path}) ---")
    total_io = 0
    for name, start, end in am_methods:
        blocks = find_with_block_ranges(am_source, start, end)
        for blk in blocks:
            io_findings = check_io_in_range(am_source, blk["start"], blk["end"])
            if io_findings:
                total_io += len(io_findings)
                print(f"\n  ⚠️  {name} (L{start}-L{end})")
                print(f"      锁: {blk['lock']} (L{blk['start']}-L{blk['end']})")
                for io in io_findings:
                    print(f"      L{io['line']} [{io['io_keyword']}]: {io['code']}")
    print(f"\n  AccountManager 锁内 IO 总计: {total_io} 处")

    te_path = "d:/DevelopTool/FreeCode/HIkyuu-UI/hikyuu-ui/core/trading_engine.py"
    te_source = Path(te_path).read_text(encoding="utf-8", errors="ignore").split("\n")
    print(f"\n--- TradingEngine ({te_path}) ---")
    total_io = 0
    for name, start, end in te_methods:
        blocks = find_with_block_ranges(te_source, start, end)
        for blk in blocks:
            io_findings = check_io_in_range(te_source, blk["start"], blk["end"])
            if io_findings:
                total_io += len(io_findings)
                print(f"\n  ⚠️  {name} (L{start}-L{end})")
                print(f"      锁: {blk['lock']} (L{blk['start']}-L{blk['end']})")
                for io in io_findings:
                    print(f"      L{io['line']} [{io['io_keyword']}]: {io['code']}")
    print(f"\n  TradingEngine 锁内 IO 总计: {total_io} 处")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
