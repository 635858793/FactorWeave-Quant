"""
R147 子智能体 B - 4 源验证工具 v1
- 扫描指定文件的 except 块, 统计含/不含 exc_info 的数量
- 跨 5 子目录验证 (cache_service / ctp_trading_interface / order_executor)
"""
import ast
import sys
from pathlib import Path

LOGGER_METHODS = {'error', 'warning', 'warn', 'info', 'debug', 'exception', 'critical', 'trace'}


def scan_file(filepath: str) -> dict:
    """AST 扫描文件, 返回 except 块统计"""
    src = Path(filepath).read_text(encoding='utf-8')
    tree = ast.parse(src)

    stats = {
        'file': filepath,
        'total_excepts': 0,
        'with_logger': 0,
        'with_exc_info': 0,
        'with_logger_no_exc_info_lines': [],
    }

    def has_exc_info_kw(call):
        return any(
            kw.arg == 'exc_info' and isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in call.keywords
        )

    def is_logger_call(node):
        return (
            isinstance(node.func, ast.Attribute) and
            node.func.attr in LOGGER_METHODS
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            stats['total_excepts'] += 1
            for sub in ast.walk(node):
                if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                    call = sub.value
                    if is_logger_call(call):
                        stats['with_logger'] += 1
                        if has_exc_info_kw(call):
                            stats['with_exc_info'] += 1
                        else:
                            stats['with_logger_no_exc_info_lines'].append(sub.lineno)

    return stats


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python _r147_b_scan_v1.py <file1> [file2] ...")
        sys.exit(1)

    grand_total = {'total': 0, 'with_logger': 0, 'with_exc_info': 0, 'violations': []}

    for fp in sys.argv[1:]:
        if not Path(fp).exists():
            print(f"[NOT FOUND] {fp}")
            continue
        stats = scan_file(fp)
        violations_count = len(stats['with_logger_no_exc_info_lines'])

        print(f"\n=== {fp} ===")
        print(f"  Total ExceptHandler:    {stats['total_excepts']}")
        print(f"  With logger call:       {stats['with_logger']}")
        print(f"  With exc_info=True:     {stats['with_exc_info']}")
        print(f"  WITHOUT exc_info:       {violations_count}")

        if violations_count > 0 and violations_count <= 60:
            print(f"  Violation lines:        {stats['with_logger_no_exc_info_lines']}")
        elif violations_count > 60:
            print(f"  Violation lines (first 30): {stats['with_logger_no_exc_info_lines'][:30]}")
            print(f"  Violation lines (last 10): {stats['with_logger_no_exc_info_lines'][-10:]}")

        grand_total['total'] += stats['total_excepts']
        grand_total['with_logger'] += stats['with_logger']
        grand_total['with_exc_info'] += stats['with_exc_info']
        grand_total['violations'].extend(
            [(fp, ln) for ln in stats['with_logger_no_exc_info_lines']]
        )

    print(f"\n========== GRAND TOTAL ==========")
    print(f"  Total ExceptHandler:    {grand_total['total']}")
    print(f"  With logger call:       {grand_total['with_logger']}")
    print(f"  With exc_info=True:     {grand_total['with_exc_info']}")
    print(f"  WITHOUT exc_info:       {len(grand_total['violations'])}")
    print(f"  Coverage:               {grand_total['with_exc_info']*100.0/max(grand_total['with_logger'],1):.1f}%")
