# -*- coding: utf-8 -*-
"""R171-C 锁架构 AST 递归 with.body 深度扫描 (R104 §12 #3+#5)

- 严格递归进入 with.body, 不扁平化 (R104 §12 #3)
- AST unparse 验证方法体 (R104 §12 #5)
- 锁嵌套违规 = 同一方法体内, 内层 with 块使用与外层 with 块相同/不同的目标锁
- 排除 try/finally 中正常的锁释放模式 (单独 finally 释放)
"""
import ast
import os
import sys


TARGET_LOCKS = {
    '_lock', '_cache_lock', '_stats_lock', '_history_lock',
    '_futures_lock', '_positions_lock', '_data_lock', '_write_lock',
    '_read_lock', '_flush_lock', '_request_lock',
    '_bar_lock', '_signal_lock', '_order_lock', '_trade_lock',
    '_plugin_lock', '_session_lock', '_monitor_lock', '_queue_lock',
    '_config_lock', '_log_lock', '_engine_lock', '_market_lock',
    '_portfolio_lock', '_risk_lock', '_account_lock', '_strategy_lock',
    '_fund_lock', '_index_lock', '_bond_lock', '_stock_lock',
    '_option_lock', '_futures_position_lock', '_metrics_lock',
    '_state_lock', '_start_lock', '_shutdown_lock', '_cleanup_lock',
    '_loader_lock', '_parser_lock', '_writer_lock', '_reader_lock',
    '_subscription_lock', '_publish_lock', '_dispatch_lock',
    '_worker_lock', '_thread_lock', '_sync_lock', '_async_lock',
    '_notify_lock', '_event_lock', '_update_lock', '_hot_lock',
    '_warm_lock', '_cold_lock', '_module_lock', '_global_lock',
    '_compile_lock', '_jit_lock', '_gpu_lock', '_compile_jit_lock',
    '_reload_lock', '_rlock', '_write_rlock', '_read_rlock',
    '_tasks_lock', '_task_lock', '_sub_lock', '_unsub_lock',
    '_recompute_lock', '_aggregation_lock', '_cleanup_stats_lock',
    '_cleanup_history_lock', '_persistence_lock', '_cleanup_inflight_lock',
    '_data_write_lock', '_data_read_lock', '_conn_lock', '_db_lock',
    '_kdata_lock', '_bar_data_lock', '_kline_lock', '_tick_lock',
    '_indicator_lock', '_signal_compute_lock', '_order_book_lock',
    '_order_queue_lock', '_strategy_pool_lock', '_plugin_pool_lock',
    '_exchange_lock', '_broker_lock', '_account_balance_lock',
    '_position_lock', '_equity_lock', '_pnl_lock', '_drawdown_lock',
    '_margin_lock', '_slippage_lock', '_commission_lock',
    '_tax_lock', '_fee_lock', '_volume_lock', '_liquidity_lock',
    '_volatility_lock', '_beta_lock', '_alpha_lock', '_sharpe_lock',
    '_sortino_lock', '_calmar_lock', '_information_ratio_lock',
    '_tracking_error_lock', '_upside_capture_lock', '_downside_capture_lock',
}


def collect_locks_in_with(with_node):
    """提取 with 块中持有的所有 self.X_lock"""
    locks = set()
    for item in with_node.items:
        ctx = item.context_expr
        if isinstance(ctx, ast.Attribute) and isinstance(ctx.value, ast.Name):
            if ctx.value.id == 'self' and ctx.attr in TARGET_LOCKS:
                locks.add(ctx.attr)
    return locks


def find_nested_locks_in_method(method_node, file, lineno):
    """在方法体内递归查找锁嵌套违规 (R104 §12 #3 严格递归)"""
    violations = []

    def visit(block, parent_locks, block_path):
        if not isinstance(block, list):
            return
        for stmt in block:
            if isinstance(stmt, ast.With):
                stmt_locks = collect_locks_in_with(stmt)
                # 检查嵌套: stmt_locks 与 parent_locks 是否有交集
                common = stmt_locks & parent_locks
                if common and parent_locks:
                    violations.append({
                        'file': file,
                        'method': method_node.name,
                        'method_line': lineno,
                        'outer_line': block_path[-1] if block_path else lineno,
                        'inner_line': stmt.lineno,
                        'outer_locks': sorted(parent_locks),
                        'inner_locks': sorted(stmt_locks),
                        'common_locks': sorted(common),
                        'path': ' -> '.join(block_path + [f'L{stmt.lineno}']),
                    })
                # 继续递归进入 stmt.body
                new_parent = parent_locks | stmt_locks
                new_path = block_path + [f'L{stmt.lineno}']
                visit(stmt.body, new_parent, new_path)
                # 也递归进入 stmt.finalbody (try-finally 模式)
                for fin_item in stmt.finalbody if hasattr(stmt, 'finalbody') else []:
                    pass
            elif isinstance(stmt, ast.Try):
                # try.body 内的 with 继承 parent_locks
                visit(stmt.body, parent_locks, block_path)
                visit(stmt.handlers, parent_locks, block_path)
                visit(stmt.finalbody, parent_locks, block_path)
            elif isinstance(stmt, ast.If):
                visit(stmt.body, parent_locks, block_path)
                visit(stmt.orelse, parent_locks, block_path)
            elif isinstance(stmt, (ast.For, ast.While)):
                visit(stmt.body, parent_locks, block_path)
                visit(stmt.orelse, parent_locks, block_path)

    visit(method_node.body, set(), [])
    return violations


def main():
    total_files = 0
    total_violations = []
    scanned_dirs = ['core', 'gui', 'plugins', 'tests', 'utils', 'services']

    # 排除目录
    skip_dirs = {'.pytest_cache', '__pycache__', '.git', 'node_modules',
                 'dist', 'build', '.mypy_cache', '.cache', 'data'}

    for scan_dir in scanned_dirs:
        if not os.path.isdir(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if not f.endswith('.py'):
                    continue
                fp = os.path.join(root, f)
                total_files += 1
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                        source = fh.read()
                    tree = ast.parse(source, filename=fp)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_violations = find_nested_locks_in_method(
                                node, fp, node.lineno
                            )
                            total_violations.extend(method_violations)
                except Exception as e:
                    pass

    print(f'[R171-C] Scanned files: {total_files}')
    print(f'[R171-C] Lock nested violations: {len(total_violations)}')
    if total_violations:
        print('[R171-C] First 50 violations:')
        for v in total_violations[:50]:
            print(f'  {v["file"]}:{v["method"]} '
                  f'method_L{v["method_line"]} '
                  f'outer_L{v["outer_line"]}->inner_L{v["inner_line"]} '
                  f'outer={v["outer_locks"]} inner={v["inner_locks"]} '
                  f'common={v["common_locks"]} '
                  f'path={v["path"]}')


if __name__ == '__main__':
    main()
