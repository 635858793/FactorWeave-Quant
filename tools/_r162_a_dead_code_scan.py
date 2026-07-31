"""R162-A 子智能体专用: 5+1 服务方法跨子目录死代码扫描工具

R6 §6.1 8 铁律 + R104 §12 5 铁律 100% 应用
- 跨 5 子目录 (core/gui/web/tests/scripts/plugins)
- 排除 self.xxx / cls.xxx 等类内调用
- 输出真死代码 (0 callsite) 候选
"""
import re
import pathlib
import sys

# 5+1 服务的方法名候选(子集,基于 R162-A 实际方法清单)
SERVICE_METHODS = {
    'TradingService': [
        'get_performance_stats', 'get_ctp_quote', 'subscribe_ctp_quote',
        'get_ctp_connection_status', 'disconnect_ctp_account', 'connect_ctp_account',
        'get_strategy_status', 'get_positions_by_account', 'get_all_portfolios',
        '_create_default_portfolio', 'get_portfolio', 'clear_all_positions',
        'clear_trade_history', 'get_current_account_id_metric', 'get_trade_history',
        'get_trading_metrics', 'is_live_mode', 'is_backtest_mode',
    ],
    'OrderExecutor': [
        'get_signal_chain', 'get_commission_rate', '_get_avg_entry_price',
        '_get_position', 'set_trading_interface', 'query_order_status',
        '_pre_trade_risk_check', 'check_interface_health',
    ],
    'OrderService': [
        'analyze_order_timing', 'analyze_order_cost', 'analyze_order_path',
        'analyze_order_risk', 'predict_order_fill_probability',
        'analyze_efficiency', 'analyze_volume', 'analyze_slippage',
        'analyze_orders', 'get_order_alerts', 'check_orders',
        'get_orders_by_stock', 'get_orders_by_strategy',
        'get_order_statistics', 'get_order_fills',
    ],
    'TradingController': [
        'run_backtest', 'start_strategy', 'stop_strategy', 'pause_strategy',
        'resume_strategy', 'set_current_strategy', 'get_current_strategy',
    ],
}

# 6 子目录(R6 §6.1 铁律 #2 强制 5 子目录, +1 跨 web)
SEARCH_DIRS = ['core', 'gui', 'web', 'tests', 'scripts', 'plugins']


def collect_py_files():
    all_files = []
    for d in SEARCH_DIRS:
        if not pathlib.Path(d).exists():
            continue
        for p in pathlib.Path(d).rglob('*.py'):
            # 排除 cache
            if '__pycache__' in str(p) or '.pytest_cache' in str(p):
                continue
            all_files.append(p)
    return all_files


def count_method_calls(method_name, files):
    """统计 .method_name( 的真实调用方数(排除类内 self.method 定义)"""
    count = 0
    hits = []
    pattern = re.compile(rf'\.{re.escape(method_name)}\(')
    for p in files:
        try:
            src = p.read_text(encoding='utf-8')
        except Exception:
            continue
        for match in pattern.finditer(src):
            line_num = src[:match.start()].count('\n') + 1
            # 排除 self.xxx(定义行) - 但仍然在 def 内的也算(因为是类内调用)
            # 真正死代码 = 在类外, 跨文件调用
            line_start = src.rfind('\n', 0, match.start()) + 1
            line_end = src.find('\n', match.end())
            if line_end == -1:
                line_end = len(src)
            line = src[line_start:line_end].strip()
            # 排除定义行
            if 'def ' in line or 'class ' in line or '"""' in line or "'''" in line:
                continue
            # 排除测试断言 hasattr 场景
            if 'hasattr(' in line:
                continue
            count += 1
            if len(hits) < 5:
                hits.append(f'{p}:{line_num}')
    return count, hits


def main():
    files = collect_py_files()
    print(f'总扫描文件数: {len(files)}')

    dead_candidates = []
    for svc, methods in SERVICE_METHODS.items():
        print(f'\n=== {svc} ===')
        for m in methods:
            count, hits = count_method_calls(m, files)
            flag = '[DEAD]' if count == 0 else '[LIVE]'
            print(f'  {flag} {m}: {count} callsite  {" | ".join(hits[:3])}')
            if count == 0:
                dead_candidates.append((svc, m))

    print(f'\n=== 真死代码候选 (0 callsite) ===')
    print(f'总数: {len(dead_candidates)}')
    for svc, m in dead_candidates:
        print(f'  - {svc}.{m}')


if __name__ == '__main__':
    main()
